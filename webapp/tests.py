from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User, Group
from inventory.seed import seed_benchmark
from inventory.models import SKU, Customer, BOM, Posting
from sales.services import submit_order
from production.services import create_run
from .forms import money_input
from django.core.exceptions import ValidationError


class ScreenTests(TestCase):
    def setUp(self):
        seed_benchmark()
        self.admin=User.objects.get(username="benchmark-seed")
        self.client.force_login(self.admin)

    def test_main_screens_and_run(self):
        for url in ["/","/orders/","/production/","/stock/","/stock/FLOUR/",f"/sources/{Posting.objects.first().pk}/"]:
            self.assertEqual(self.client.get(url).status_code,200,url)
        run=create_run(bom=BOM.objects.first(),batches=1,request_key="r",document_date=date(2026,11,19),actor=self.admin)
        self.assertEqual(self.client.get(f"/production/{run.pk}/").status_code,200)
        order=submit_order(customer=Customer.objects.first(),quantities={SKU.objects.first().pk:1},request_key="o",document_date=date(2026,11,19),actor=self.admin)
        self.assertEqual(self.client.get(f"/orders/{order.pk}/").status_code,200)
        self.assertContains(self.client.get("/orders/"),'name="viewport"')

    def test_salesman_denied_production_and_other_order(self):
        order=submit_order(customer=Customer.objects.first(),quantities={SKU.objects.first().pk:1},request_key="o",document_date=date(2026,11,19),actor=self.admin)
        user=User.objects.create_user("mobile")
        user.groups.add(Group.objects.get_or_create(name="salesman")[0])
        self.client.force_login(user)
        self.assertEqual(self.client.get("/production/").status_code,403)
        self.assertEqual(self.client.get(f"/orders/{order.pk}/").status_code,403)
        self.assertEqual(self.client.get("/orders/").status_code,200)
        self.client.logout()
        self.assertEqual(self.client.get("/stock/").status_code,302)

    def test_exact_money_entry(self):
        self.assertEqual(money_input("187.50"),18750)
        for value in ["1.001","nan","-1"]:
            with self.assertRaises(ValidationError): money_input(value)


class PDFTests(TestCase):
    def test_pdf_snapshots_currency_and_access(self):
        from io import BytesIO
        from pypdf import PdfReader
        from sales.tests import prepare, DAY
        from sales.services import approve_order, invoice_order
        from .services import invoice_pdf
        actor=prepare()
        order=submit_order(customer=Customer.objects.get(code="A"),quantities={SKU.objects.first().pk:150},request_key="pdf",document_date=DAY,actor=actor)
        approve_order(order,actor)
        invoice=invoice_order(order,actor,DAY)
        content=PdfReader(BytesIO(invoice_pdf(invoice,actor))).pages[0].extract_text()
        for expected in ["\u20b9","7,875.00","187.50",invoice.number,"33AAAAA0000A1Z0"]:
            self.assertIn(expected,content)
        other=User.objects.create_user("other-pdf")
        other.groups.add(Group.objects.get_or_create(name="salesman")[0])
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/invoices/{invoice.pk}/pdf/").status_code,403)


class OfflineTests(TestCase):
    def test_sync_retry_owner_and_server_price(self):
        from .services import sync_offline_order
        from django.core.exceptions import PermissionDenied
        from sales.models import Order
        seed_benchmark()
        user=User.objects.create_user('offline-sales')
        user.groups.add(Group.objects.get_or_create(name='salesman')[0])
        payload={'user_id':user.pk,'customer':Customer.objects.first().pk,'quantities':{str(SKU.objects.first().pk):12},'date':'2026-11-19','request_key':'offline-key'}
        first=sync_offline_order(payload,user)
        self.assertEqual(sync_offline_order(payload,user).pk,first.pk)
        self.assertEqual(Order.objects.count(),1)
        self.assertEqual(first.lines.get().price_paise,5000)
        with self.assertRaises(PermissionDenied): sync_offline_order({**payload,'user_id':0},user)
        with self.assertRaises(ValidationError): sync_offline_order({**payload,'quantities':{str(SKU.objects.first().pk):13}},user)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/offline/catalog/').status_code,200)
        self.assertEqual(self.client.post('/offline/sync/',payload,content_type='application/json').status_code,200)
        self.assertEqual(self.client.get('/offline/sync/').status_code,405)
        self.assertEqual(self.client.get('/offline/').status_code,200)
        self.assertEqual(self.client.get('/service-worker.js').status_code,200)

    def test_csrf_and_read_only_role(self):
        from django.test import Client
        from access.seed import seed_logins
        seed_benchmark()
        seed_logins()
        user=User.objects.get(username='accountant')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/offline/catalog/').status_code,403)
        self.assertEqual(self.client.post('/orders/',{}).status_code,403)
        self.assertEqual(self.client.post('/production/',{}).status_code,403)
        client=Client(enforce_csrf_checks=True)
        client.force_login(User.objects.get(username='salesman_a'))
        self.assertEqual(client.post('/offline/sync/',{},content_type='application/json').status_code,403)
