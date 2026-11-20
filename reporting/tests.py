from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied
from sales.tests import prepare, DAY
from inventory.models import Customer, SKU
from sales.services import submit_order, approve_order, invoice_order, record_payment, credit_invoice
from .services import REPORTS, report_table, csv_bytes, table_pdf, dashboard


class ReportTests(TestCase):
    def setUp(self):
        self.actor=prepare()
        order=submit_order(customer=Customer.objects.get(code="A"),quantities={SKU.objects.first().pk:150},request_key="report",document_date=DAY,actor=self.actor)
        approve_order(order,self.actor)
        self.invoice=invoice_order(order,self.actor,DAY)
        record_payment(invoice=self.invoice,amount_paise=400000,request_key="pay-report",document_date=DAY,actor=self.actor)

    def test_all_exports_and_dashboard(self):
        self.client.force_login(self.actor)
        for kind in REPORTS:
            table=report_table(kind,DAY,date(2026,12,31),self.actor)
            self.assertTrue(csv_bytes(table).startswith(b'\xef\xbb\xbf'))
            self.assertTrue(table_pdf(table).startswith(b'%PDF'))
            self.assertEqual(self.client.get('/reports/',{'report':kind}).status_code,200)
        self.assertEqual(dashboard(self.actor,DAY)['outstanding'],387500)
        self.assertIn('7,500.00',str(report_table('gst',DAY,DAY,self.actor)['rows']))
        self.assertEqual(report_table('sales',date(2026,11,20),date(2026,11,20),self.actor)['rows'],[])

    def test_ageing_boundaries_and_future_payments(self):
        for cutoff,index in [(DAY,5),(date(2026,12,19),6),(date(2026,12,20),7)]:
            row=report_table('ageing',DAY,cutoff,self.actor)['rows'][0]
            self.assertEqual(row[index],'3,875.00')
        record_payment(invoice=self.invoice,amount_paise=10000,request_key="future",document_date=date(2027,1,1),actor=self.actor)
        self.assertEqual(report_table('ageing',DAY,date(2026,12,20),self.actor)['rows'][0][4],'3,875.00')

    def test_salesman_scope_and_csv_formula(self):
        other=User.objects.create_user('report-sales')
        other.groups.add(Group.objects.get_or_create(name='salesman')[0])
        self.assertEqual(report_table('customers',DAY,DAY,other)['rows'],[])
        with self.assertRaises(PermissionDenied): report_table('sales',DAY,DAY,other)
        self.assertIn(b"'=SUM",csv_bytes({'headers':['name'],'rows':[['=SUM(A1)']]}))

    def test_credit_uses_event_date(self):
        order=submit_order(customer=Customer.objects.get(code='B'),quantities={SKU.objects.first().pk:1},request_key='credit-report',document_date=DAY,actor=self.actor)
        approve_order(order,self.actor)
        invoice=invoice_order(order,self.actor,DAY)
        credit_invoice(invoice,'wrong order',self.actor,date(2026,11,20))
        rows=report_table('sales',date(2026,11,20),date(2026,11,20),self.actor)['rows']
        self.assertEqual(rows[0][-1],'-52.50')


class BenchmarkTests(TestCase):
    def test_all_nine_steps_and_repeatability(self):
        from .benchmark import run_benchmark
        from inventory.models import Posting
        for _ in range(2):
            results=run_benchmark()
            self.assertTrue(all(row[3] for row in results),[row for row in results if not row[3]])
            for label,expected,actual,passed in results:
                self.assertEqual(expected,actual,label)
            # Read XML decimal text directly, never importing spreadsheet floats into money/quantity arithmetic.
            from pathlib import Path
            from zipfile import ZipFile
            from xml.etree import ElementTree as ET
            from decimal import Decimal
            ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            with ZipFile(Path(__file__).resolve().parent.parent/'docs/benchmark.xlsx') as archive:
                root=ET.fromstring(archive.read('xl/worksheets/sheet3.xml'))
            actuals={label:actual for label,expected,actual,passed in results}
            for row in root.findall('.//m:sheetData/m:row',ns)[1:]:
                cells={''.join(filter(str.isalpha,c.attrib['r'])):c for c in row.findall('m:c',ns)}
                step=''.join(cells['A'].itertext())
                expected=[int(Decimal(cells[column].find('m:v',ns).text)*scale) for column,scale in zip('CDEFGH',[1000,1000,1000,1,1,1])]
                self.assertEqual(actuals[step+' stock (g/ml/piece)'],expected)
        self.assertEqual(Posting.objects.count(),0)

    def test_seed_logins_are_idempotent(self):
        from access.seed import seed_logins
        seed_logins()
        before=User.objects.get(username='admin').password
        seed_logins()
        self.assertEqual(User.objects.get(username='admin').password,before)
        self.assertTrue(User.objects.get(username='production').check_password('DemoPass123!'))
