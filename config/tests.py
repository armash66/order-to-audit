from io import BytesIO

from django.db import connection
from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader
from weasyprint import HTML


class StartupTests(SimpleTestCase):
    def test_startup_page(self):
        response = self.client.get("/login/")
        self.assertContains(response, "Order-to-Audit")
        self.assertContains(response, "Sign in")


class DatabaseTests(TestCase):
    # Exercise the actual PostgreSQL test database, not an SQLite substitute.
    def test_postgresql_connection(self):
        self.assertEqual(connection.vendor, "postgresql")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone(), (1,))


class PdfDependencyTests(SimpleTestCase):
    # Render in memory and extract text to catch a lost rupee symbol.
    def test_one_line_rupee_pdf(self):
        pdf = HTML(string='<p style="font-family: DejaVu Sans">Smoke check: ₹1</p>').write_pdf()
        self.assertTrue(pdf.startswith(b"%PDF-"))
        reader = PdfReader(BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)
        self.assertIn("Smoke check: ₹1", reader.pages[0].extract_text())
