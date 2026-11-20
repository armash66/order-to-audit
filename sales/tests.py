from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from inventory.models import FactoryControl, SKU, Customer, Supplier, Item, BOM, StockMovement
from inventory.seed import seed_benchmark
from inventory.services import post_receipt, reconcile_stock
from production.services import create_run, issue_run, complete_run
from .models import Order, Dispatch, Payment
from .services import (submit_order, approve_order, reject_order, invoice_order, dispatch_invoice,
                       record_payment, outstanding, credit_invoice, stock_check, available_stock, line_tax)

DAY = date(2026, 11, 19)


# Shared test fixture reaches 238 packets through actual receipt and production services.
def prepare():
    FactoryControl.objects.get_or_create(pk=1)
    seed_benchmark()
    actor = get_user_model().objects.get(username="benchmark-seed")
    post_receipt(kind="purchase", request_key="flour", document_date=DAY, actor=actor,
        supplier=Supplier.objects.first(), lines=[(Item.objects.get(code="FLOUR"), 60000, 270000)])
    run = create_run(bom=BOM.objects.first(), batches=1, request_key="run", document_date=DAY, actor=actor)
    issue_run(run=run, actual={"FLOUR":40000,"OIL":10500,"SPICE":1200}, request_key="issue", actor=actor)
    complete_run(run=run, actual={"POUCH":194,"CARTON":9}, good_packets=188, damaged={"POUCH":6}, request_key="complete", actor=actor)
    return actor


class SalesTests(TestCase):
    def setUp(self):
        self.actor = prepare()
        self.order = submit_order(customer=Customer.objects.get(code="A"), quantities={SKU.objects.first().pk:150}, request_key="a", document_date=DAY, actor=self.actor)

    def test_benchmark_reservations_dispatch_payment(self):
        approve_order(self.order,self.actor)
        balance = available_stock()["MURUKKU200"]
        self.assertEqual((balance["quantity"],balance["reserved"],balance["available"]),(238,150,88))
        invoice=invoice_order(self.order,self.actor,DAY)
        self.assertEqual((invoice.taxable_paise,invoice.cgst_paise,invoice.sgst_paise,invoice.total_paise),(750000,18750,18750,787500))
        self.assertEqual(available_stock()["MURUKKU200"]["quantity"],238)
        dispatch=dispatch_invoice(invoice,self.actor,DAY)
        self.assertEqual(dispatch_invoice(invoice,self.actor,DAY).pk,dispatch.pk)
        balance=available_stock()["MURUKKU200"]
        self.assertEqual((balance["quantity"],balance["reserved"],balance["available"]),(88,0,88))
        b=submit_order(customer=Customer.objects.get(code="B"),quantities={SKU.objects.first().pk:120},request_key="b",document_date=DAY,actor=self.actor)
        self.assertEqual(stock_check(b,self.actor)[0]["shortage"],32)
        with self.assertRaises(ValidationError): approve_order(b,self.actor)
        record_payment(invoice=invoice,amount_paise=400000,request_key="pay",document_date=DAY,actor=self.actor)
        record_payment(invoice=invoice,amount_paise=400000,request_key="pay",document_date=DAY,actor=self.actor)
        self.assertEqual(Payment.objects.count(),1)
        self.assertEqual(outstanding(invoice),387500)
        reconcile_stock()

    def test_draft_has_no_receivable_or_credit_and_unknown_product_rolls_back(self):
        approve_order(self.order,self.actor)
        invoice=invoice_order(self.order,self.actor,DAY,draft=True)
        self.assertEqual(outstanding(invoice),0)
        with self.assertRaises(ValidationError): credit_invoice(invoice,"draft",self.actor,DAY)
        invoice=invoice_order(self.order,self.actor,DAY)
        self.assertEqual(outstanding(invoice,date(2026,11,18)),0)
        count=Order.objects.count()
        with self.assertRaises(ValidationError):
            submit_order(customer=self.order.customer,quantities={999999:1},request_key="bad-sku",document_date=DAY,actor=self.actor)
        self.assertEqual(Order.objects.count(),count)

    def test_half_paise_and_interstate_fy(self):
        self.assertEqual(line_tax(20,False),(1,1,0))
        self.assertEqual(line_tax(10,True),(0,0,1))
        b=submit_order(customer=Customer.objects.get(code="B"),quantities={SKU.objects.first().pk:1},request_key="b",document_date=DAY,actor=self.actor)
        approve_order(b,self.actor)
        invoice=invoice_order(b,self.actor,date(2027,4,1))
        self.assertEqual((invoice.cgst_paise,invoice.sgst_paise,invoice.igst_paise),(0,0,250))
        self.assertEqual(invoice.number,"2027-28/00001")

    def test_credit_and_rejection_release_reservation(self):
        approve_order(self.order,self.actor)
        invoice=invoice_order(self.order,self.actor,DAY)
        credit_invoice(invoice,"wrong customer",self.actor,DAY)
        self.assertEqual(outstanding(invoice),0)
        self.assertEqual(available_stock()["MURUKKU200"]["available"],238)
        with self.assertRaises(ValidationError): dispatch_invoice(invoice,self.actor,DAY)
        other=submit_order(customer=Customer.objects.first(),quantities={SKU.objects.first().pk:10},request_key="other",document_date=DAY,actor=self.actor)
        approve_order(other,self.actor)
        reject_order(other,"duplicate order",self.actor)
        self.assertEqual(available_stock()["MURUKKU200"]["reserved"],0)

    def test_paid_credit_and_changed_retry_rejected(self):
        with self.assertRaises(ValidationError):
            submit_order(customer=self.order.customer,quantities={SKU.objects.first().pk:151},request_key="a",document_date=DAY,actor=self.actor)
        approve_order(self.order,self.actor)
        invoice=invoice_order(self.order,self.actor,DAY)
        record_payment(invoice=invoice,amount_paise=1,request_key="p",document_date=DAY,actor=self.actor)
        with self.assertRaises(ValidationError): credit_invoice(invoice,"paid",self.actor,DAY)


class ApprovalConcurrencyTests(TransactionTestCase):
    def test_competing_approvals_do_not_overreserve(self):
        actor=prepare()
        orders=[submit_order(customer=Customer.objects.first(),quantities={SKU.objects.first().pk:150},request_key=str(i),document_date=DAY,actor=actor) for i in range(2)]
        barrier=Barrier(2)
        def approve(pk):
            close_old_connections()
            try:
                user=get_user_model().objects.get(pk=actor.pk)
                order=Order.objects.get(pk=pk)
                barrier.wait(timeout=10)
                try:
                    approve_order(order,user)
                    return True
                except ValidationError:
                    return False
            finally: connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(approve,[o.pk for o in orders]))
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(available_stock()["MURUKKU200"]["reserved"],150)
