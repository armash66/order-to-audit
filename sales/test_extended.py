from fractions import Fraction
from django.core.exceptions import ValidationError
from django.test import TestCase
from inventory.models import Customer, SKU
from inventory.services import reconcile_stock
from sales.tests import prepare, DAY
from sales.models import ReturnLine
from sales.services import (submit_order, approve_order, invoice_order, dispatch_invoice, available_stock,
                            return_goods, outstanding, record_payment, set_customer_price, prices_for_customer)
from reporting.services import report_table


class ExtendedSalesTests(TestCase):
    def setUp(self):
        self.actor=prepare()
        self.customer=Customer.objects.get(code="A")
        self.sku=SKU.objects.first()

    def test_customer_price_snapshot(self):
        set_customer_price(customer=self.customer,sku=self.sku,price_paise=4500,label="Retail scheme",actor=self.actor)
        order=submit_order(customer=self.customer,quantities={self.sku.pk:1},request_key="priced",document_date=DAY,actor=self.actor)
        set_customer_price(customer=self.customer,sku=self.sku,price_paise=4000,label="New scheme",actor=self.actor)
        self.assertEqual((order.lines.get().price_paise,order.lines.get().price_label),(4500,"Retail scheme"))
        self.assertEqual(prices_for_customer(self.customer,self.actor)[0]['price_paise'],4000)

    def test_partial_dispatch_returns_and_retry(self):
        order=submit_order(customer=self.customer,quantities={self.sku.pk:150},request_key="partial",document_date=DAY,actor=self.actor)
        approve_order(order,self.actor)
        invoice=invoice_order(order,self.actor,DAY)
        args=dict(quantities={self.sku.item_id:60},request_key="ship60")
        first=dispatch_invoice(invoice,self.actor,DAY,**args)
        self.assertEqual(dispatch_invoice(invoice,self.actor,DAY,**args).pk,first.pk)
        balance=available_stock()[self.sku.item.code]
        self.assertEqual((balance['quantity'],balance['reserved'],balance['available']),(178,90,88))
        with self.assertRaises(ValidationError): dispatch_invoice(invoice,self.actor,DAY,quantities={self.sku.item_id:91},request_key="too-many")
        dispatch_invoice(invoice,self.actor,DAY)
        record_payment(invoice=invoice,amount_paise=787500,request_key="paid",document_date=DAY,actor=self.actor)
        args=dict(invoice=invoice,quantities={self.sku.item_id:20},reason="Sealed surplus",request_key="return20",document_date=DAY,actor=self.actor)
        note=return_goods(**args)
        self.assertEqual(return_goods(**args).pk,note.pk)
        self.assertEqual(outstanding(invoice),-105000)
        self.assertEqual(reconcile_stock()[self.sku.item.code]['quantity'],108)
        self.assertEqual(available_stock()[self.sku.item.code]['reserved'],0)
        self.assertIn('-1,050.00',str(report_table('sales',DAY,DAY,self.actor)['rows']))
        with self.assertRaises(ValidationError): return_goods(**{**args,'quantities':{self.sku.item_id:131},'request_key':'too-many'})

    def test_return_tax_residual(self):
        set_customer_price(customer=self.customer,sku=self.sku,price_paise=20,label="Rounding fixture",actor=self.actor)
        order=submit_order(customer=self.customer,quantities={self.sku.pk:3},request_key="tiny",document_date=DAY,actor=self.actor)
        approve_order(order,self.actor)
        invoice=invoice_order(order,self.actor,DAY)
        dispatch_invoice(invoice,self.actor,DAY)
        for index in range(3):
            return_goods(invoice=invoice,quantities={self.sku.item_id:1},reason="Sealed return",request_key=f"tiny-{index}",document_date=DAY,actor=self.actor)
        self.assertEqual(outstanding(invoice),0)
        self.assertEqual(sum(ReturnLine.objects.values_list('cgst_paise',flat=True)),invoice.cgst_paise)
