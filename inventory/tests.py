from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from fractions import Fraction
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from .models import (FactoryControl, Item, OpeningStock, PurchaseReceipt, PurchaseLine,
                     Posting, StockMovement, Supplier, BOMLine)
from .seed import seed_benchmark
from .services import (post_receipt, reconcile_stock, round_paise, stock_summary,
                       to_base_units, weighted_average, require_integer)


# Build the section 5 step-1 request without adding it to the opening seed.
def purchase_arguments():
    return dict(kind="purchase", request_key="purchase-1", document_date=date(2026, 11, 19),
                actor=get_user_model().objects.get(username="benchmark-seed"),
                supplier=Supplier.objects.get(code="FLOUR-SUPPLIER"),
                lines=[(Item.objects.get(code="FLOUR"), 60000, 270000)])


class StockTests(TestCase):
    def setUp(self):
        seed_benchmark()

    def test_opening_and_purchase_benchmark(self):
        self.assertEqual(OpeningStock.objects.count(), 1)
        self.assertEqual(BOMLine.objects.count(), 5)
        self.assertEqual(stock_summary()["FLOUR"]["quantity"], 100000)
        post_receipt(**purchase_arguments())
        self.assertEqual({k: v["quantity"] for k, v in reconcile_stock().items()},
                         dict(FLOUR=160000, OIL=30000, SPICE=5000, POUCH=500, CARTON=30, MURUKKU200=50))
        flour = Item.objects.get(code="FLOUR")
        self.assertEqual(stock_summary()["FLOUR"]["value_paise"], 690000)
        self.assertEqual(weighted_average(flour), Fraction(69, 16))
        self.assertEqual(round_paise(weighted_average(flour) * 40000), 172500)
        self.assertIsNone(weighted_average(Item.objects.get(code="MURUKKU200")))

    def test_exact_conversion_and_rounding(self):
        self.assertEqual(to_base_units(Item.objects.get(code="OIL"), "L", Decimal("10.5")), 10500)
        self.assertEqual(to_base_units(Item.objects.get(code="MURUKKU200"), "carton", 2), 40)
        self.assertEqual(to_base_units(Item.objects.get(code="FLOUR"), "g", 12), 12)
        for value, expected in [(Fraction(5, 2), 3), (Fraction(-5, 2), -3), (Fraction(249, 100), 2)]:
            self.assertEqual(round_paise(value), expected)
        for value in (1.2, True, -1):
            with self.assertRaises(ValidationError):
                require_integer(value)
        with self.assertRaises(ValidationError):
            round_paise(1.5)
        for value in (Decimal("0.0001"), 1.5, -1):
            with self.assertRaises(ValidationError):
                to_base_units(Item.objects.get(code="FLOUR"), "kg", value)

    def test_duplicate_and_changed_retry(self):
        args = purchase_arguments()
        first = post_receipt(**args)
        self.assertEqual(post_receipt(**args).pk, first.pk)
        self.assertEqual(PurchaseReceipt.objects.count(), 1)
        args["lines"] = [(args["lines"][0][0], 60001, 270000)]
        with self.assertRaises(ValidationError):
            post_receipt(**args)
        self.assertEqual(stock_summary()["FLOUR"]["quantity"], 160000)

    def test_seed_repeat_and_conflict(self):
        seed_benchmark()
        self.assertEqual(StockMovement.objects.count(), 6)
        post_receipt(**purchase_arguments())
        seed_benchmark()
        self.assertEqual(StockMovement.objects.count(), 7)
        Item.objects.filter(code="FLOUR").update(name="Changed")
        with self.assertRaises(ValidationError):
            seed_benchmark()

    def test_no_late_opening_or_float_or_unknown_purchase(self):
        args = purchase_arguments()
        for quantity, value in [(1.5, 100), (1, None), (1, 2.5), (0, 100)]:
            args["lines"] = [(Item.objects.get(code="FLOUR"), quantity, value)]
            with self.assertRaises(ValidationError):
                post_receipt(**args)
        args = purchase_arguments()
        args.update(kind="opening", supplier=None)
        with self.assertRaises(ValidationError):
            post_receipt(**args)
        self.assertEqual(StockMovement.objects.count(), 6)

    def test_permission_and_older_document_date(self):
        args = purchase_arguments()
        args["actor"] = get_user_model().objects.create_user(username="salesman")
        with self.assertRaises(PermissionDenied):
            post_receipt(**args)
        args = purchase_arguments()
        args["document_date"] = date(2020, 1, 1)
        self.assertEqual(post_receipt(**args).sequence, 2)
        self.assertEqual(Posting.objects.get(sequence=1).movements.count(), 6)

    def test_movement_immutability(self):
        movement = StockMovement.objects.first()
        for operation in (lambda: StockMovement.objects.filter(pk=movement.pk).update(quantity=9),
                          lambda: StockMovement.objects.filter(pk=movement.pk).delete()):
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    operation()
        reconcile_stock()

    def test_reconciliation_detects_source_tampering(self):
        post_receipt(**purchase_arguments())
        # Service freezing is intentionally not a database source-document trigger.
        PurchaseLine.objects.update(quantity=1)
        with self.assertRaises(ValidationError):
            reconcile_stock()

    def test_reconciliation_detects_report_bug(self):
        with patch("inventory.services.stock_summary", return_value={}):
            with self.assertRaises(ValidationError):
                reconcile_stock()


class PostingTransactionTests(TransactionTestCase):
    def setUp(self):
        # TransactionTestCase flush removes data-migration rows between tests.
        FactoryControl.objects.get_or_create(pk=1)
        seed_benchmark()

    def test_concurrent_duplicate_requests(self):
        barrier = Barrier(2)

        # Each worker uses a distinct connection and waits before attempting the lock.
        def worker():
            close_old_connections()
            try:
                args = purchase_arguments()
                barrier.wait(timeout=10)
                return post_receipt(**args).pk
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(PurchaseReceipt.objects.count(), 1)
        self.assertEqual(stock_summary()["FLOUR"]["quantity"], 160000)
        reconcile_stock()

    def test_mid_post_failure_rolls_back_everything(self):
        args = purchase_arguments()
        args["lines"].append((Item.objects.get(code="OIL"), 1000, 14000))
        original_create = StockMovement.objects.create
        calls = 0

        # Fail after a real movement insert, not merely during pre-validation.
        def fail_second(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Injected mid-post failure")
            return original_create(**kwargs)

        with patch("inventory.services.StockMovement.objects.create", side_effect=fail_second):
            with self.assertRaisesMessage(RuntimeError, "Injected mid-post failure"):
                post_receipt(**args)
        self.assertEqual(calls, 2)
        self.assertEqual(PurchaseReceipt.objects.count(), 0)
        self.assertEqual(PurchaseLine.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 6)
        self.assertEqual(FactoryControl.objects.get(pk=1).last_sequence, 1)
        self.assertEqual(Posting.objects.count(), 1)
        reconcile_stock()
        self.assertEqual(post_receipt(**args).sequence, 2)
