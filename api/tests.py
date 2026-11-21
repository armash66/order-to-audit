"""Endpoint benchmark against Django's isolated PostgreSQL test database."""

import os
from uuid import uuid4
from django.test import TransactionTestCase
from django.conf import settings
from sqlalchemy import create_engine, inspect
from fastapi.testclient import TestClient
from inventory.seed import seed_benchmark
from access.seed import seed_logins
from inventory.services import reconcile_stock
from inventory.models import Item, SKU, Customer, BOM, Supplier, FactoryControl


class APIWorkflowTests(TransactionTestCase):
    def setUp(self):
        from api import database
        from api.main import app

        self.database = database
        self.original = database.engine
        database.engine = create_engine(
            self.original.url.set(database=settings.DATABASES["default"]["NAME"])
        )
        if not inspect(database.engine).has_table('factory_qualityhold'):
            from alembic.migration import MigrationContext
            from alembic.operations import Operations
            from importlib import import_module
            with database.engine.begin() as conn:
                with Operations.context(MigrationContext.configure(conn)):
                    import_module('api.migrations.versions.0002_factory_actions').upgrade()
        FactoryControl.objects.get_or_create(pk=1)
        seed_benchmark()
        seed_logins()
        self.client = TestClient(app)
        self.headers = {}
        for name in [
            "admin",
            "production",
            "salesman_a",
            "salesman_b",
            "accountant",
            "owner",
        ]:
            response = self.client.post(
                "/api/login",
                json={
                    "username": name,
                    "password": os.environ.get("DEMO_PASSWORD", "DemoPass123!"),
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.headers[name] = {
                "Authorization": "Bearer " + response.json()["access_token"]
            }

    def tearDown(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from importlib import import_module
        with self.database.engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                import_module('api.migrations.versions.0002_factory_actions').downgrade()
        self.client.close()
        self.database.engine.dispose()
        self.database.engine = self.original

    def command(self, action, data, role="admin", key=None, status=200):
        response = self.client.post(
            "/api/workspace/commands",
            headers=self.headers[role],
            json={"action": action, "data": data, "request_key": key or str(uuid4())},
        )
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def get(self, path, role="admin"):
        response = self.client.get("/api/workspace" + path, headers=self.headers[role])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_nine_steps_through_fastapi(self):
        ids = {item.code: str(item.pk) for item in Item.objects.all()}
        self.command(
            "receipt",
            {
                "supplier": str(Supplier.objects.first().pk),
                "date": "2026-11-19",
                "lines": [
                    {"item": ids["FLOUR"], "quantity": "60000", "value_paise": "270000"}
                ],
            },
            "production",
        )
        run = self.command(
            "production.create",
            {"bom": str(BOM.objects.first().pk), "batches": "1", "date": "2026-11-19"},
            "production",
        )["id"]
        key = str(uuid4())
        issue = {
            "id": run,
            "actual": {"FLOUR": "40000", "OIL": "10500", "SPICE": "1200"},
        }
        self.command("production.issue", issue, "production", key)
        self.command("production.issue", issue, "production", key)
        self.command(
            "production.complete",
            {
                "id": run,
                "actual": {"POUCH": "194", "CARTON": "9"},
                "damaged": {"POUCH": "6", "CARTON": "0"},
                "good_packets": "188",
            },
            "production",
        )
        sku = str(SKU.objects.first().pk)
        order = self.command(
            "order.create",
            {
                "customer": str(Customer.objects.get(code="A").pk),
                "quantities": {sku: "150"},
                "date": "2026-11-19",
            },
            "salesman_a",
        )["id"]
        self.command("order.approve", {"id": order})
        self.command("order.invoice", {"id": order, "date": "2026-11-19"})
        info = self.get("/orders/" + order)
        self.assertEqual(info["invoice"]["total_paise"], "787500")
        self.assertEqual(info["invoice"]["cgst_paise"], "18750")
        self.assertEqual(info["stock"][0]["available"], "88")
        self.command("order.dispatch", {"id": order, "quantities": {}}, status=400)
        response = self.client.get("/api/stock", headers=self.headers["admin"])
        self.assertEqual(
            next(
                row["quantity"]
                for row in response.json()
                if row["code"] == "MURUKKU200"
            ),
            "238",
        )
        key = str(uuid4())
        self.command("order.dispatch", {"id": order, "date": "2026-11-19"}, key=key)
        self.command("order.dispatch", {"id": order, "date": "2026-11-19"}, key=key)
        other = self.command(
            "order.create",
            {
                "customer": str(Customer.objects.get(code="B").pk),
                "quantities": {sku: "120"},
                "date": "2026-11-19",
            },
            "salesman_b",
        )["id"]
        self.assertEqual(self.get("/orders/" + other)["stock"][0]["shortage"], "32")
        plan = self.get("/orders/" + other)["suggestions"][0]
        self.assertEqual((plan["uncovered"], plan["required_batches"], plan["blocked"]), ("32", "1", False))
        self.assertEqual(next(row for row in plan["inputs"] if row["item"] == "POUCH")["shortage"], "0")
        self.command("order.approve", {"id": other}, status=400)
        self.command(
            "order.payment",
            {"id": order, "amount_paise": "400000", "date": "2026-11-19"},
        )
        self.assertEqual(
            self.get("/orders/" + order)["invoice"]["outstanding"], "387500"
        )
        for label, amount in [("Labour", "120000"), ("Gas/power", "60000")]:
            self.command(
                "production.overhead",
                {
                    "id": run,
                    "label": label,
                    "amount_paise": amount,
                    "date": "2026-11-19",
                },
            )
        report = self.get("/production/" + run)["report"]
        self.assertEqual(report["total_paise"], "585500")
        self.assertEqual(report["display_cost_paise"], "3114")
        self.assertTrue(report["yield"]["flagged"])
        self.assertFalse(report["consumption"]["POUCH"]["flagged"])
        from reporting.services import REPORTS

        for kind in REPORTS:
            actual = self.get(
                f"/reports/{kind}?start=2026-11-01&end=2026-11-30", "accountant"
            )
            from reporting.services import report_table as legacy_report
            from django.contrib.auth.models import User
            from datetime import date
            from api.workflows import wire

            expected = wire(
                legacy_report(
                    kind,
                    date(2026, 11, 1),
                    date(2026, 11, 30),
                    User.objects.get(username="accountant"),
                )
            )
            if kind == "ledger":
                for row in expected["rows"]:
                    row[3] = "/api/workspace" + row[3].rstrip("/")
            self.assertEqual(actual, expected, kind)
        for day, column in [("2026-12-19", 6), ("2026-12-20", 7)]:
            ageing = self.get(
                f"/reports/ageing?start=2026-11-01&end={day}", "accountant"
            )
            self.assertEqual(ageing["rows"][0][column], "3,875.00")
        from io import BytesIO
        from zipfile import ZipFile
        from decimal import Decimal
        from xml.etree.ElementTree import fromstring

        tally = self.client.get(
            "/api/workspace/reports/tally?start=2026-11-01&end=2026-11-30",
            headers=self.headers["accountant"],
        )
        self.assertEqual(
            tally.status_code, 200, tally.text if tally.status_code != 200 else ""
        )
        with ZipFile(BytesIO(tally.content)) as archive:
            vouchers = fromstring(archive.read("vouchers.xml")).findall(".//VOUCHER")
            self.assertEqual(len(vouchers), 5)
            for voucher in vouchers:
                self.assertEqual(
                    sum(
                        Decimal(element.text)
                        for element in voucher.findall(".//AMOUNT")
                    ),
                    0,
                )
        for path in ["/dashboard", "/batches", "/visits", "/catalog"]:
            self.get(path)
        invoice = info["invoice"]["id"]
        self.assertTrue(
            self.client.get(
                f"/api/workspace/invoices/{invoice}/pdf", headers=self.headers["admin"]
            ).content.startswith(b"%PDF")
        )
        self.assertEqual(reconcile_stock()["FLOUR"]["quantity"], 120000)

    def test_permissions_and_invalid_numbers(self):
        self.assertEqual(self.get("/catalog", "salesman_a")["boms"], [])
        self.assertEqual(
            self.client.get(
                "/api/stock", headers=self.headers["salesman_a"]
            ).status_code,
            403,
        )
        self.command(
            "order.create",
            {
                "customer": str(Customer.objects.first().pk),
                "quantities": {str(SKU.objects.first().pk): 1.2},
            },
            "salesman_a",
            status=400,
        )
        self.command("tolerance", {"basis_points": "200"}, "accountant", status=403)
        self.assertEqual(self.client.get("/api/workspace/catalog").status_code, 401)

    def test_native_receipt_concurrent_retry_and_rollback(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        from api.services import user_by_name
        from api.inventory import services
        from inventory.models import StockMovement, PurchaseReceipt

        with self.database.engine.connect() as conn:
            user = user_by_name(conn, "production")
        flour = Item.objects.get(code="FLOUR")
        data = {
            "supplier": str(Supplier.objects.first().pk),
            "date": "2026-11-19",
            "lines": [
                {"item": str(flour.pk), "quantity": "60000", "value_paise": "270000"}
            ],
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: services.post_receipt(data, user, "concurrent-native"),
                    range(2),
                )
            )
        self.assertEqual(results[0], results[1])
        self.assertEqual(
            PurchaseReceipt.objects.filter(request_key="concurrent-native").count(), 1
        )
        self.assertEqual(reconcile_stock()["FLOUR"]["quantity"], 160000)
        before = StockMovement.objects.count()
        sequence = FactoryControl.objects.get(pk=1).last_sequence
        original = services.movement

        def fail_after_movement(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("Simulated failure after movement and lot writes")

        with patch.object(services, "movement", side_effect=fail_after_movement):
            with self.assertRaises(RuntimeError):
                services.post_receipt(data, user, "native-failure")
        self.assertFalse(
            PurchaseReceipt.objects.filter(request_key="native-failure").exists()
        )
        self.assertEqual(StockMovement.objects.count(), before)
        self.assertEqual(FactoryControl.objects.get(pk=1).last_sequence, sequence)
        reconcile_stock()

    def test_native_rounding_and_batch_retry(self):
        from fractions import Fraction
        from api.native import round_paise, issue_value

        self.assertEqual(round_paise(Fraction(5, 2)), 3)
        self.assertEqual(round_paise(Fraction(-5, 2)), -3)
        self.assertEqual(issue_value(1, 3, 10), 3)
        self.assertEqual(issue_value(1, 2, 7), 4)
        self.assertEqual(issue_value(1, 1, 3), 3)
        self.assertEqual(issue_value(40000, 160000, 690000), 172500)
        data = {
            "supplier": str(Supplier.objects.first().pk),
            "lines": [
                {
                    "item": str(Item.objects.get(code="FLOUR").pk),
                    "quantity": "1000",
                    "value_paise": "4500",
                }
            ],
            "lots": {"FLOUR": {"code": "NATIVE-LOT", "expiry": "2027-01-01"}},
        }
        self.command("receipt", data, key="native-lot")
        changed = {
            **data,
            "lots": {"FLOUR": {"code": "NATIVE-LOT", "expiry": "2027-02-01"}},
        }
        self.command("receipt", changed, key="native-lot", status=400)
        self.command("receipt", changed, key="new-native-key", status=400)
        reconcile_stock()

    def test_native_production_rollback_and_zero_usage(self):
        from unittest.mock import patch
        from api.production import services
        from api.services import user_by_name
        from production.models import ProductionRun, ProductionEvent
        from inventory.models import StockMovement

        with self.database.engine.connect() as conn:
            user = user_by_name(conn, "production")
        run = self.command(
            "production.create",
            {"bom": str(BOM.objects.first().pk), "batches": "1"},
            "production",
        )["id"]
        data = {"id": run, "actual": {"FLOUR": 40000, "OIL": 10500, "SPICE": 1200}}
        original = services.append_line
        before = StockMovement.objects.count()
        sequence = FactoryControl.objects.get(pk=1).last_sequence

        def fail_after_line(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("Failure after production movement")

        with patch.object(services, "append_line", side_effect=fail_after_line):
            with self.assertRaises(RuntimeError):
                services.post_event("issue", data, user, "failed-native-issue")
        self.assertFalse(ProductionEvent.objects.filter(run_id=run).exists())
        self.assertEqual(ProductionRun.objects.get(pk=run).state, "draft")
        self.assertEqual(StockMovement.objects.count(), before)
        self.assertEqual(FactoryControl.objects.get(pk=1).last_sequence, sequence)
        self.command(
            "production.issue",
            {**data, "actual": {**data["actual"], "FLOUR": 100001}},
            "production",
            status=400,
        )
        self.command(
            "production.issue", {**data, "actual": []}, "production", status=400
        )
        self.command("production.issue", data, "production", key="native-valid-issue")
        self.command(
            "production.complete",
            {"id": run, "actual": {"POUCH": 0, "CARTON": 0}, "good_packets": 0},
            "production",
        )
        report = self.get("/production/" + run)["report"]
        self.assertIsNone(report["cost_per_packet_paise"])
        self.assertEqual(report["consumption"]["POUCH"]["actual"], "0")
        self.assertEqual(reconcile_stock()["MURUKKU200"]["quantity"], 50)

    def test_native_shared_recipe_and_tolerance(self):
        from datetime import date
        from django.contrib.auth.models import User
        from production.test_fixtures import add_500g_bom
        from api.production.services import variance

        bom = BOM.objects.first()
        run = self.command(
            "production.create", {"bom": str(bom.pk), "batches": "1"}, "production"
        )["id"]
        self.command("production.edit", {"id": run, "batches": "2"}, "production")
        self.assertEqual(
            self.get("/production/" + run)["report"]["expected_packets"], "400"
        )
        self.command("production.edit", {"id": run, "batches": "1"}, "production")
        raw = {"FLOUR": "40000", "OIL": "10500", "SPICE": "1200"}
        self.command("production.issue", {"id": run, "actual": raw}, "production")
        self.command(
            "production.complete",
            {
                "id": run,
                "actual": {"POUCH": "194", "CARTON": "9"},
                "good_packets": "188",
                "damaged": {"POUCH": "6"},
            },
            "production",
        )
        self.assertFalse(
            self.get("/production/" + run)["report"]["consumption"]["POUCH"]["flagged"]
        )
        self.command("tolerance", {"basis_points": "200"})
        self.assertTrue(
            self.get("/production/" + run)["report"]["consumption"]["POUCH"]["flagged"]
        )
        self.assertFalse(variance(98, 100, 200)["flagged"])
        self.command(
            "production.edit", {"id": run, "batches": "2"}, "production", status=400
        )
        overhead = {"id": run, "label": "Labour", "amount_paise": "120000"}
        self.command("production.overhead", overhead, key="native-overhead")
        self.command("production.overhead", overhead, key="native-overhead")
        self.command(
            "production.overhead",
            {**overhead, "amount_paise": "120001"},
            key="native-overhead",
            status=400,
        )
        bom500 = add_500g_bom(
            bom.recipe,
            User.objects.get(username="admin"),
            Supplier.objects.first(),
            date(2026, 11, 19),
        )
        other = self.command(
            "production.create", {"bom": str(bom500.pk), "batches": "1"}, "production"
        )["id"]
        self.command(
            "production.issue",
            {"id": other, "actual": {**raw, "OIL": "10000"}},
            "production",
        )
        self.command(
            "production.complete",
            {
                "id": other,
                "actual": {"POUCH500": "80", "CARTON": "4"},
                "good_packets": "80",
            },
            "production",
        )
        report = self.get("/production/" + other)["report"]
        self.assertEqual(report["expected_packets"], "80")
        self.assertEqual(report["consumption"]["FLOUR"]["planned"], "40000")
        self.assertNotIn("POUCH", report["consumption"])
        balances = reconcile_stock()
        self.assertEqual(balances["MURUKKU500"]["quantity"], 80)
        self.assertEqual(balances["MURUKKU200"]["quantity"], 238)

    def test_native_sales_concurrent_approval_and_tax(self):
        from concurrent.futures import ThreadPoolExecutor
        from api.sales import services
        from api.services import user_by_name

        self.assertEqual(services.line_tax(20, False), (1, 1, 0))
        self.assertEqual(services.line_tax(10, True), (0, 0, 1))
        sku = str(SKU.objects.first().pk)
        data = {
            "customer": str(Customer.objects.get(code="A").pk),
            "quantities": {sku: "40"},
            "date": "2026-11-19",
        }
        first = self.command("order.create", data, "salesman_a", key="order-retry")[
            "id"
        ]
        self.assertEqual(
            self.command("order.create", data, "salesman_a", key="order-retry")["id"],
            first,
        )
        self.command(
            "order.create",
            {**data, "quantities": {sku: "41"}},
            "salesman_a",
            key="order-retry",
            status=400,
        )
        second = self.command("order.create", data, "salesman_b")["id"]
        with self.database.engine.connect() as conn:
            user = user_by_name(conn, "admin")

        def approve(identifier):
            try:
                services.command(
                    "order.approve",
                    {"id": identifier, "date": "2026-11-19"},
                    user,
                    str(uuid4()),
                )
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(approve, [first, second]))
        self.assertEqual(sorted(results), [False, True])
        from sales.models import Order

        self.assertEqual(Order.objects.filter(status="approved").count(), 1)
        self.assertEqual(
            self.client.get(
                "/api/workspace/orders/" + first, headers=self.headers["salesman_b"]
            ).status_code,
            403,
        )
        self.command("order.approve", {"id": first}, "salesman_a", status=403)
        winner = first if results[0] else second
        self.command("order.reject", {"id": winner, "reason": "Customer cancelled"})
        with self.database.engine.connect() as conn:
            self.assertEqual(services.available(conn, SKU.objects.first().item_id), 50)

    def test_native_sales_drafts_partial_dispatch_payment_credit(self):
        from sales.models import OrderLine, InvoiceSequence

        sku = SKU.objects.first()

        def new_order(customer="A", quantity="10"):
            identifier = self.command(
                "order.create",
                {
                    "customer": str(Customer.objects.get(code=customer).pk),
                    "quantities": {str(sku.pk): quantity},
                },
            )["id"]
            self.command("order.approve", {"id": identifier})
            return identifier

        order = new_order()
        line = OrderLine.objects.get(order_id=order)
        self.command(
            "order.edit", {"id": order, "lines": {str(line.pk): ["10", "5010"]}}
        )
        self.assertEqual(self.get("/orders/" + order)["status"], "submitted")
        self.command("order.approve", {"id": order})
        self.command(
            "order.invoice", {"id": order, "draft": True, "date": "2026-11-19"}
        )
        self.assertFalse(InvoiceSequence.objects.exists())
        self.command("order.edit_invoice", {"id": order, "date": "2026-11-20"})
        self.command("order.invoice", {"id": order, "date": "2026-11-20"})
        invoice = self.get("/orders/" + order)["invoice"]
        self.assertEqual(invoice["number"], "2026-27/00001")
        self.command("order.edit_invoice", {"id": order}, status=400)
        self.command(
            "order.dispatch", {"id": order, "quantities": {str(sku.item_id): "4"}}
        )
        self.assertEqual(self.get("/orders/" + order)["status"], "invoiced")
        self.assertEqual(reconcile_stock()["MURUKKU200"]["quantity"], 46)
        self.command(
            "order.dispatch",
            {"id": order, "quantities": {str(sku.item_id): "7"}},
            status=400,
        )
        self.command("order.dispatch", {"id": order})
        self.assertEqual(self.get("/orders/" + order)["status"], "dispatched")
        self.command(
            "order.payment", {"id": order, "amount_paise": "1000"}, key="native-payment"
        )
        self.command(
            "order.payment", {"id": order, "amount_paise": "1000"}, key="native-payment"
        )
        self.command(
            "order.payment", {"id": order, "amount_paise": "999999"}, status=400
        )
        self.command("order.credit", {"id": order, "reason": "No"}, status=400)
        other = new_order("B")
        self.command("order.invoice", {"id": other})
        self.assertEqual(self.get("/orders/" + other)["invoice"]["igst_paise"], "2500")
        self.command("order.credit", {"id": other, "reason": "Cancelled"})
        self.assertEqual(self.get("/orders/" + other)["invoice"]["outstanding"], "0")
        self.assertEqual(self.get("/orders/" + other)["status"], "rejected")

    def test_native_corrections_restore_lots_and_return_residuals(self):
        from inventory.models import StockMovement
        from inventory.services import reconcile_lots
        from sales.models import OrderLine, ReturnLine
        from production.models import ProductionRun

        run = self.command(
            "production.create",
            {"bom": str(BOM.objects.first().pk), "batches": "1"},
            "production",
        )["id"]
        self.command(
            "production.issue",
            {"id": run, "actual": {"FLOUR": "40000", "OIL": "10500", "SPICE": "1200"}},
            "production",
        )
        self.command(
            "production.complete",
            {
                "id": run,
                "actual": {"POUCH": "194", "CARTON": "9"},
                "good_packets": "188",
            },
            "production",
        )
        reversal = {"id": run, "reason": "Recorded in error"}
        self.command("production.reverse", reversal, key="native-reversal")
        count = StockMovement.objects.count()
        self.command("production.reverse", reversal, key="native-reversal")
        self.assertEqual(StockMovement.objects.count(), count)
        self.assertEqual(ProductionRun.objects.get(pk=run).state, "reversed")
        self.assertEqual(reconcile_stock()["FLOUR"]["quantity"], 100000)
        self.assertEqual(self.get("/production/" + run)["report"]["total_paise"], "0")
        sku = SKU.objects.first()
        order = self.command(
            "order.create",
            {
                "customer": str(Customer.objects.get(code="A").pk),
                "quantities": {str(sku.pk): "3"},
            },
        )["id"]
        line = OrderLine.objects.get(order_id=order)
        self.command("order.edit", {"id": order, "lines": {str(line.pk): ["3", "20"]}})
        self.command("order.approve", {"id": order})
        self.command("order.invoice", {"id": order})
        self.command("order.dispatch", {"id": order})
        for index in range(3):
            data = {
                "id": order,
                "quantities": {str(sku.item_id): "1"},
                "reason": "Sealed returned packets",
            }
            self.command("order.return", data, key=f"native-return-{index}")
            self.command("order.return", data, key=f"native-return-{index}")
        self.assertEqual(
            sum(ReturnLine.objects.values_list("cgst_paise", flat=True)), 2
        )
        self.assertEqual(
            sum(ReturnLine.objects.values_list("sgst_paise", flat=True)), 2
        )
        self.assertEqual(self.get("/orders/" + order)["invoice"]["outstanding"], "0")
        self.command("order.return", data, status=400)
        self.assertEqual(reconcile_stock()["MURUKKU200"]["quantity"], 50)
        reconcile_lots()

    def test_native_adjustment_and_reversal_dependency_guard(self):
        from inventory.services import reconcile_lots

        run = self.command(
            "production.create",
            {"bom": str(BOM.objects.first().pk), "batches": "1"},
            "production",
        )["id"]
        self.command(
            "production.issue",
            {"id": run, "actual": {"FLOUR": "40000", "OIL": "10500", "SPICE": "1200"}},
            "production",
        )
        flour = Item.objects.get(code="FLOUR")
        adjustment = {
            "item": str(flour.pk),
            "quantity": "-1",
            "reason": "Measured loss",
        }
        self.command("adjustment", adjustment, key="native-adjustment")
        self.command("adjustment", adjustment, key="native-adjustment")
        self.command(
            "production.reverse", {"id": run, "reason": "Correction"}, status=400
        )
        self.assertEqual(reconcile_stock()["FLOUR"]["quantity"], 59999)
        self.command(
            "adjustment",
            {**adjustment, "quantity": "1", "value_paise": "4"},
            key="native-adjustment",
            status=400,
        )
        self.command("adjustment", {**adjustment, "quantity": "1", "value_paise": "4"})
        self.command("adjustment", {**adjustment, "quantity": "-999999"}, status=400)
        self.command("adjustment", adjustment, "production", status=403)
        reconcile_lots()

    def test_native_extensions_offline_and_pdf(self):
        from io import BytesIO
        from pypdf import PdfReader
        from extensions.models import Visit, MockSubmission
        from inventory.models import ReorderLevel

        sku = SKU.objects.first()
        customer = Customer.objects.get(code="A")
        self.command(
            "price",
            {
                "customer": str(customer.pk),
                "sku": str(sku.pk),
                "price_paise": "4321",
                "label": "Demo scheme",
            },
        )
        self.assertEqual(
            self.get("/prices/" + str(customer.pk), "salesman_a")[0]["price_paise"],
            "4321",
        )
        flour = Item.objects.get(code="FLOUR")
        self.command("reorder", {"item": str(flour.pk), "minimum": "110000"})
        self.assertEqual(ReorderLevel.objects.get(item=flour).minimum_quantity, 110000)
        self.command("reorder", {"item": str(sku.item_id), "minimum": "1"}, status=400)
        visit = {
            "customer": str(customer.pk),
            "route": "Demo route",
            "consent": True,
            "latitude": "19.1234565",
            "longitude": "73.1234565",
        }
        self.command("visit", visit, "salesman_a", key="native-visit")
        self.command("visit", visit, "salesman_a", key="native-visit")
        self.assertEqual(
            Visit.objects.get(request_key="native-visit").latitude_microdegrees,
            19123457,
        )
        self.command("visit", {**visit, "consent": False}, "salesman_a", status=400)
        self.command("visit", {**visit, "latitude": 19.1}, "salesman_a", status=400)
        self.assertEqual(self.get("/visits", "salesman_b"), [])
        payload = {
            "customer": str(customer.pk),
            "quantities": {str(sku.pk): "2"},
            "date": "2026-11-19",
            "request_key": "native-offline",
            "user_id": self.get("/catalog", "salesman_a")["user_id"],
        }
        response = self.client.post(
            "/api/workspace/offline/sync",
            headers=self.headers["salesman_a"],
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()["id"]
        self.assertEqual(
            self.client.post(
                "/api/workspace/offline/sync",
                headers=self.headers["salesman_b"],
                json=payload,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.get("/orders/" + order)["lines"][0]["price_paise"], "4321"
        )
        self.command("order.approve", {"id": order})
        self.command("order.invoice", {"id": order, "draft": True})
        invoice = self.get("/orders/" + order)["invoice"]["id"]
        url = f"/api/workspace/invoices/{invoice}/pdf"
        self.assertEqual(
            self.client.get(url, headers=self.headers["admin"]).status_code, 400
        )
        self.command("order.invoice", {"id": order})
        pdf = self.client.get(url, headers=self.headers["salesman_a"])
        self.assertEqual(pdf.status_code, 200)
        content = "".join(
            page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages
        )
        self.assertIn("₹", content)
        self.assertIn("90.74", content)
        self.assertEqual(
            self.client.get(url, headers=self.headers["salesman_b"]).status_code, 403
        )
        for kind in ["e_invoice", "e_waybill"]:
            first = self.command("mock", {"invoice": invoice, "kind": kind})
            self.assertTrue(first["response"]["reference"].startswith("MOCK-"))
            self.assertIn("43.21", first["request_json"])
            self.assertEqual(
                self.command("mock", {"invoice": invoice, "kind": kind}), first
            )
        self.assertEqual(MockSubmission.objects.count(), 2)
        pdf = self.client.get(
            "/api/workspace/reports/sales?start=2026-11-01&end=2026-11-30&format=pdf",
            headers=self.headers["accountant"],
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_audit_history_and_source_drilldown_are_role_scoped(self):
        from inventory.models import StockMovement

        self.command(
            "receipt",
            {"supplier": str(Supplier.objects.first().pk), "lines": [
                {"item": str(Item.objects.get(code="FLOUR").pk), "quantity": "1000", "value_paise": "4500"}
            ]},
            "production",
        )
        order = self.command("order.create", {
            "customer": str(Customer.objects.get(code="A").pk),
            "quantities": {str(SKU.objects.first().pk): "2"},
        }, "salesman_a")["id"]
        self.command("order.approve", {"id": order})
        history = self.get("/audit", "accountant")
        approval = next(row for row in history if row["action"] == "order.approve")
        self.assertEqual(approval["actor"], "admin")
        self.assertEqual(approval["before"]["status"], "submitted")
        self.assertEqual(approval["after"]["status"], "approved")
        self.assertEqual(self.client.get("/api/workspace/audit", headers=self.headers["salesman_a"]).status_code, 403)
        movement = StockMovement.objects.filter(item__code="FLOUR").order_by("-pk").first()
        source = self.get(f"/sources/{movement.posting_id}", "accountant")
        self.assertEqual(source["lines"][0]["quantity"], "1000")
        self.assertEqual(self.client.get(f"/api/workspace/sources/{movement.posting_id}", headers=self.headers["salesman_a"]).status_code, 403)

    def test_quality_hold_blocks_approval_without_changing_ledger(self):
        from inventory.models import StockMovement
        lot = next(r for r in self.get("/batches")["lots"] if r["category"] == "finished")
        movements = StockMovement.objects.count()
        self.command("quality", {"lot": lot["id"], "status": "held", "reason": "Seal inspection"}, "production")
        held = next(r for r in self.get("/batches")["lots"] if r["id"] == lot["id"])
        self.assertEqual((held["quantity"], held["quality_status"]), ("50", "held"))
        order = self.command("order.create", {"customer": str(Customer.objects.get(code="A").pk),
            "quantities": {str(SKU.objects.first().pk): "1"}}, "salesman_a")["id"]
        self.assertEqual(self.get("/orders/" + order)["stock"][0]["available"], "0")
        self.command("order.approve", {"id": order}, status=400)
        self.command("quality", {"lot": lot["id"], "status": "released", "reason": "Passed inspection"}, "production")
        self.command("order.approve", {"id": order})
        self.assertEqual(StockMovement.objects.count(), movements)
        self.command("quality", {"lot": lot["id"], "status": "held", "reason": "No"}, "salesman_a", status=403)

    def test_offline_sync_accepts_two_skus_once(self):
        second_item = Item.objects.create(code="OFFLINE500", name="Offline 500 g test SKU",
                                          category="finished", base_unit="piece")
        second_sku = SKU.objects.create(item=second_item, pack_size_g=500,
                                        price_paise=12500, hsn="99999999")
        payload = {"customer": str(Customer.objects.get(code="A").pk),
                   "quantities": {str(SKU.objects.exclude(pk=second_sku.pk).first().pk): "2",
                                  str(second_sku.pk): "3"},
                   "request_key": "two-skus", "date": "2026-11-19",
                   "user_id": self.get("/catalog", "salesman_a")["user_id"]}
        response = self.client.post("/api/workspace/offline/sync", headers=self.headers["salesman_a"], json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        again = self.client.post("/api/workspace/offline/sync", headers=self.headers["salesman_a"], json=payload)
        self.assertEqual(again.json(), response.json())
        order = self.get("/orders/" + response.json()["id"], "salesman_a")
        self.assertEqual({line["quantity"] for line in order["lines"]}, {"2", "3"})

    def test_recall_follows_input_lot_to_customer_dispatch(self):
        run = self.command("production.create", {"bom": str(BOM.objects.first().pk), "batches": "1"}, "production")["id"]
        self.command("production.issue", {"id": run,
            "actual": {"FLOUR": "40000", "OIL": "10000", "SPICE": "1200"}}, "production")
        self.command("production.complete", {"id": run,
            "actual": {"POUCH": "200", "CARTON": "10"}, "good_packets": "200"}, "production")
        order = self.command("order.create", {"customer": str(Customer.objects.get(code="A").pk),
            "quantities": {str(SKU.objects.first().pk): "60"}}, "salesman_a")["id"]
        self.command("order.approve", {"id": order})
        self.command("order.invoice", {"id": order})
        self.command("order.dispatch", {"id": order})
        flour = next(r for r in self.get("/batches")["lots"] if r["item"] == "Flour")
        trace = self.get("/recall/" + flour["id"], "accountant")
        self.assertIn(run, trace["production_run_ids"])
        self.assertTrue(trace["finished_lots"])
        self.assertIn("document", self.get("/sources/" + trace["movements"][0]["posting_id"], "accountant"))
        self.assertEqual(trace["dispatches"][0]["customer"], "Demo Retailer A")
        self.assertEqual(self.client.get("/api/workspace/recall/" + flour["id"], headers=self.headers["salesman_a"]).status_code, 403)

    def test_shortage_plan_shows_two_batches_and_missing_inputs(self):
        run = self.command("production.create", {"bom": str(BOM.objects.first().pk), "batches": "1"}, "production")["id"]
        self.command("production.issue", {"id": run,
            "actual": {"FLOUR": "40000", "OIL": "10500", "SPICE": "1200"}}, "production")
        self.command("production.complete", {"id": run,
            "actual": {"POUCH": "194", "CARTON": "9"}, "damaged": {"POUCH": "6"},
            "good_packets": "188"}, "production")
        order = self.command("order.create", {"customer": str(Customer.objects.get(code="B").pk),
            "quantities": {str(SKU.objects.first().pk): "488"}}, "salesman_b")["id"]
        plan = self.get("/orders/" + order)["suggestions"][0]
        self.assertEqual((plan["uncovered"], plan["required_batches"], plan["feasible_batches"], plan["blocked"]),
                         ("250", "2", "1", True))
        self.assertEqual(next(r for r in plan["inputs"] if r["item"] == "OIL")["shortage"], "500")
        self.assertEqual(next(r for r in plan["inputs"] if r["item"] == "POUCH")["shortage"], "94")

    def test_loss_explanation_and_collection_followup_are_idempotent(self):
        from inventory.models import StockMovement
        run = self.command("production.create", {"bom": str(BOM.objects.first().pk), "batches": "1"}, "production")["id"]
        self.command("production.issue", {"id": run,
            "actual": {"FLOUR": "40000", "OIL": "10000", "SPICE": "1200"}}, "production")
        self.command("production.complete", {"id": run,
            "actual": {"POUCH": "194", "CARTON": "9"}, "damaged": {"POUCH": "6"},
            "good_packets": "188"}, "production")
        before = StockMovement.objects.count()
        note = {"run": run, "reason": "Unclassified yield loss", "note": "Investigate frying time"}
        first = self.command("run.loss_note", note, "production", key="loss-1")
        self.assertEqual(self.command("run.loss_note", note, "production", key="loss-1"), first)
        self.assertEqual(self.get("/production/" + run, "production")["loss_notes"][0]["reason"], note["reason"])
        self.assertEqual(StockMovement.objects.count(), before)
        order = self.command("order.create", {"customer": str(Customer.objects.get(code="A").pk),
            "quantities": {str(SKU.objects.first().pk): "2"}}, "salesman_a")["id"]
        self.command("order.approve", {"id": order})
        self.command("order.invoice", {"id": order})
        invoice = self.get("/orders/" + order)["invoice"]["id"]
        from datetime import timedelta
        from api.native import now
        followup = {"invoice": invoice, "note": "Retailer asked for a call",
                    "next_contact": str(now().date() + timedelta(days=3))}
        self.command("collection.followup", followup, key="follow-1")
        self.command("collection.followup", followup, key="follow-1")
        self.assertEqual(len(self.get("/orders/" + order)["invoice"]["followups"]), 1)
        self.assertEqual(self.get("/dashboard")["due_followups"], [])
        due = {**followup, "next_contact": str(now().date())}
        self.command("collection.followup", due, key="follow-2")
        self.assertEqual(self.get("/dashboard")["due_followups"][0]["customer"], "Demo Retailer A")
        self.command("collection.followup", followup, "salesman_a", status=403)
