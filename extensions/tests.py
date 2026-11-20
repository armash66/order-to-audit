import json
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError, PermissionDenied
from inventory.models import Customer, SKU
from sales.tests import prepare, DAY
from sales.services import submit_order, approve_order, invoice_order
from reporting.services import tally_export
from .services import record_visit, visits_for, create_mock_document, exact_json


class ExtensionTests(TestCase):
    def setUp(self):
        self.actor=prepare()
        self.customer=Customer.objects.get(code='A')
        order=submit_order(customer=self.customer,quantities={SKU.objects.first().pk:150},request_key='exports',document_date=DAY,actor=self.actor)
        approve_order(order,self.actor)
        self.invoice=invoice_order(order,self.actor,DAY)

    def test_visit_consent_retry_and_ownership(self):
        salesman=User.objects.create_user('route-a')
        salesman.groups.add(Group.objects.get_or_create(name='salesman')[0])
        args=dict(customer=self.customer,route='North market',note='Reorder visit',request_key='visit1',actor=salesman)
        with self.assertRaises(ValidationError): record_visit(**args,latitude='13.0827',longitude='80.2707')
        visit=record_visit(**args,consent=True,latitude='13.0827',longitude='80.2707')
        self.assertEqual(visit.latitude_microdegrees,13082700)
        self.assertEqual(record_visit(**args,consent=True,latitude='13.0827',longitude='80.2707').pk,visit.pk)
        other=User.objects.create_user('route-b')
        other.groups.add(Group.objects.get(name='salesman'))
        self.assertEqual(visits_for(other).count(),0)
        self.assertEqual(visits_for(self.actor).count(),1)
        with self.assertRaises(ValidationError): record_visit(**{**args,'request_key':'bad'},consent=True,latitude='91',longitude='80')

    def test_mock_exact_amounts_idempotency_and_permissions(self):
        for kind in ('e_invoice','e_waybill'):
            document=create_mock_document(invoice=self.invoice,kind=kind,actor=self.actor)
            payload=json.loads(document.request_json,parse_float=Decimal)
            self.assertEqual(payload['ValDtls']['TotInvVal'],Decimal('7875'))
            self.assertEqual(payload['ValDtls']['CgstVal'],Decimal('187.50'))
            self.assertTrue(document.response['mock'])
            self.assertTrue(document.response['reference'].startswith('MOCK-'))
            self.assertEqual(create_mock_document(invoice=self.invoice,kind=kind,actor=self.actor).pk,document.pk)
            self.client.force_login(self.actor)
            download=self.client.get(f'/invoices/{self.invoice.pk}/mock/?download={kind}').json(parse_float=Decimal)
            self.assertTrue(download['mock'])
            self.assertTrue(download['response']['reference'].startswith('MOCK-'))
            self.assertEqual(download['request']['ValDtls']['TotInvVal'],Decimal('7875'))
        with self.assertRaises(ValidationError): create_mock_document(invoice=self.invoice,kind='e_waybill',actor=self.actor,distance_km=2)
        readonly=User.objects.create_user('export-reader')
        readonly.groups.add(Group.objects.get_or_create(name='accountant')[0])
        with self.assertRaises(PermissionDenied): create_mock_document(invoice=self.invoice,kind='e_invoice',actor=readonly)
        with self.assertRaises(ValidationError): exact_json({'amount':1.5})

    def test_tally_vouchers_balance_and_date_filter(self):
        with ZipFile(BytesIO(tally_export(DAY,DAY,self.actor))) as archive:
            masters=ET.fromstring(archive.read('masters.xml'))
            vouchers=ET.fromstring(archive.read('vouchers.xml'))
        self.assertEqual(masters.find('.//REPORTNAME').text,'All Masters')
        self.assertGreater(len(vouchers.findall('.//VOUCHER')),0)
        for voucher in vouchers.findall('.//VOUCHER'):
            amounts=[Decimal(entry.find('AMOUNT').text) for entry in voucher.findall('ALLLEDGERENTRIES.LIST')]
            self.assertEqual(sum(amounts),0)
        self.assertIn('-7875.00',ET.tostring(vouchers,encoding='unicode'))
        with ZipFile(BytesIO(tally_export(DAY+timedelta(days=1),DAY+timedelta(days=1),self.actor))) as archive:
            self.assertEqual(ET.fromstring(archive.read('vouchers.xml')).findall('.//VOUCHER'),[])

    def test_extension_screens_and_tamil_session(self):
        self.client.force_login(self.actor)
        for url in ['/pricing/','/batches/','/visits/',f'/invoices/{self.invoice.pk}/mock/','/reports/tally/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        response=self.client.get('/production/?lang=ta')
        self.assertContains(response,'உற்பத்திப் பணித்தளம்')
        self.assertContains(response,'மூலப்பொருட்களைப் பெறு')
        from production.models import ProductionRun
        response=self.client.get(f'/production/{ProductionRun.objects.first().pk}/')
        self.assertContains(response,'திட்டம் மற்றும் உண்மையான பயன்பாடு')
        self.assertContains(self.client.get('/production/?lang=en'),'Production workspace')
