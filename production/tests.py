from datetime import date
from fractions import Fraction
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from inventory.models import (BOM, BOMLine, FactoryControl, Item, Posting, Recipe,
                              RecipeLine, StockMovement, Supplier)
from inventory.seed import seed_benchmark
from inventory.services import post_receipt, reconcile_stock, stock_summary, weighted_average
from .models import ProductionEvent, ProductionLine, ProductionRun, Overhead, ToleranceChange
from .services import (create_run, issue_run, complete_run, add_overhead, issue_value,
                       set_tolerance, variance, run_report)
from .test_fixtures import add_500g_bom

DAY = date(2026, 11, 19)
RAW = {"FLOUR": 40000, "OIL": 10500, "SPICE": 1200}
PACK = {"POUCH": 194, "CARTON": 9}


class ProductionTests(TestCase):
    def setUp(self):
        seed_benchmark()
        self.actor = get_user_model().objects.get(username="benchmark-seed")
        self.supplier = Supplier.objects.get(code="FLOUR-SUPPLIER")
        self.bom = BOM.objects.get(sku__item__code="MURUKKU200")
        post_receipt(kind="purchase", request_key="flour-step-1", document_date=DAY,
            lines=[(Item.objects.get(code="FLOUR"), 60000, 270000)], actor=self.actor, supplier=self.supplier)
        self.run = create_run(bom=self.bom, batches=1, request_key="run-1", document_date=DAY, actor=self.actor)

    # Use the same service calls the future screens will use.
    def issue(self, actual=None):
        return issue_run(run=self.run, actual=RAW if actual is None else actual, request_key="issue-1", actor=self.actor)

    def complete(self, actual=None, good=188):
        return complete_run(run=self.run, actual=PACK if actual is None else actual, good_packets=good,
                            damaged={"POUCH": 6}, request_key="complete-1", actor=self.actor)

    def finish(self):
        self.issue()
        self.complete()

    def test_benchmark_production_and_late_overhead(self):
        self.issue()
        self.assertEqual(stock_summary()["FLOUR"]["quantity"], 120000)
        self.assertEqual(stock_summary()["POUCH"]["quantity"], 500)
        self.assertEqual(stock_summary()["MURUKKU200"]["quantity"], 50)
        self.complete()
        self.assertEqual({k: v["quantity"] for k, v in reconcile_stock().items()},
            dict(FLOUR=120000, OIL=19500, SPICE=3800, POUCH=306, CARTON=21, MURUKKU200=238))
        before = list(StockMovement.objects.order_by("pk").values_list("pk", "quantity", "value_paise"))
        initial = run_report(self.run)
        self.assertEqual(initial["materials_paise"], 405500)
        fg_line = ProductionLine.objects.get(event__kind="complete", item=self.run.output_item)
        self.assertEqual(fg_line.value_paise, 405500)
        for key, label, value in [("labour", "Labour", 120000), ("power", "Gas/power", 60000)]:
            add_overhead(run=self.run, label=label, amount_paise=value, request_key=key, document_date=DAY, actor=self.actor)
        report = run_report(self.run)
        self.assertEqual(report["total_paise"], 585500)
        self.assertEqual(report["cost_per_packet_paise"], Fraction(585500, 188))
        self.assertEqual(report["display_cost_paise"], 3114)
        self.assertEqual(report["yield"], {"ratio": Fraction(-6, 100), "flagged": True})
        self.assertEqual(report["consumption"]["OIL"]["ratio"], Fraction(5, 100))
        self.assertTrue(report["consumption"]["OIL"]["flagged"])
        self.assertTrue(report["consumption"]["CARTON"]["flagged"])
        self.assertEqual(report["consumption"]["CARTON"]["ratio"], Fraction(-1, 10))
        self.assertEqual(report["consumption"]["POUCH"]["ratio"], Fraction(-3, 100))
        self.assertFalse(report["consumption"]["POUCH"]["flagged"])
        self.assertEqual(report["unclassified_shortfall"], 12)
        self.assertEqual(report["damaged_packaging"], {"POUCH": 6})
        self.assertEqual(report["fg_valuation_basis"], "materials-only")
        self.assertEqual(before, list(StockMovement.objects.order_by("pk").values_list("pk", "quantity", "value_paise")))
        self.assertIsNone(stock_summary()["MURUKKU200"]["value_paise"])
        self.assertEqual(stock_summary()["MURUKKU200"]["valuation_basis"], "materials-only")
        reconcile_stock()

    def test_tolerance_retroactive_and_strict_boundary(self):
        self.finish()
        self.assertFalse(run_report(self.run)["consumption"]["POUCH"]["flagged"])
        movements = list(StockMovement.objects.values_list("pk", "quantity", "value_paise"))
        self.assertEqual(set_tolerance(basis_points=200, actor=self.actor), 200)
        self.assertTrue(run_report(self.run)["consumption"]["POUCH"]["flagged"])
        self.assertFalse(variance(98, 100, 200)["flagged"])
        self.assertEqual(variance(1, 0, 200), {"ratio": None, "flagged": False})
        self.assertEqual(ToleranceChange.objects.count(), 1)
        set_tolerance(basis_points=200, actor=self.actor)
        self.assertEqual(ToleranceChange.objects.count(), 1)
        self.assertEqual(movements, list(StockMovement.objects.values_list("pk", "quantity", "value_paise")))

    def test_negative_raw_and_packaging_stock_rejected(self):
        before = stock_summary()
        with self.assertRaises(ValidationError):
            self.issue({**RAW, "FLOUR": 160001})
        self.assertEqual(stock_summary(), before)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, "draft")
        self.issue()
        before = stock_summary()
        with self.assertRaises(ValidationError):
            self.complete({**PACK, "POUCH": 501})
        self.assertEqual(stock_summary(), before)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, "issued")

    def test_issue_rollback_after_first_movement(self):
        before = stock_summary()
        sequence = FactoryControl.objects.get(pk=1).last_sequence
        real_create = StockMovement.objects.create
        calls = 0

        def fail_second(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("mid-issue failure")
            return real_create(**kwargs)

        with patch("production.services.StockMovement.objects.create", side_effect=fail_second):
            with self.assertRaisesMessage(RuntimeError, "mid-issue failure"):
                self.issue()
        self.assertEqual(calls, 2)
        self.assertEqual(ProductionLine.objects.count(), 0)
        self.assertEqual(ProductionEvent.objects.count(), 0)
        self.assertEqual(stock_summary(), before)
        self.assertEqual(FactoryControl.objects.get(pk=1).last_sequence, sequence)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, "draft")
        self.issue()
        reconcile_stock()

    def test_completion_rollback_on_fg_insert(self):
        self.issue()
        before = stock_summary()
        sequence = FactoryControl.objects.get(pk=1).last_sequence
        real_create = StockMovement.objects.create

        def fail_output(**kwargs):
            if kwargs["quantity"] > 0:
                raise RuntimeError("FG failure")
            return real_create(**kwargs)

        with patch("production.services.StockMovement.objects.create", side_effect=fail_output):
            with self.assertRaisesMessage(RuntimeError, "FG failure"):
                self.complete()
        self.assertEqual(stock_summary(), before)
        self.assertFalse(ProductionEvent.objects.filter(kind="complete").exists())
        self.assertEqual(FactoryControl.objects.get(pk=1).last_sequence, sequence)
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, "issued")
        self.assertIsNone(self.run.good_packets)
        self.complete()
        reconcile_stock()

    def test_retries_and_invalid_transitions(self):
        self.assertEqual(create_run(bom=self.bom, batches=1, request_key="run-1", document_date=DAY, actor=self.actor).pk, self.run.pk)
        with self.assertRaises(ValidationError):
            create_run(bom=self.bom, batches=2, request_key="run-1", document_date=DAY, actor=self.actor)
        with self.assertRaises(ValidationError):
            self.complete()
        posting = self.issue()
        self.assertEqual(self.issue().pk, posting.pk)
        with self.assertRaises(ValidationError):
            self.issue({**RAW, "OIL": 10000})
        posting = self.complete()
        self.assertEqual(self.complete().pk, posting.pk)
        with self.assertRaises(ValidationError):
            self.complete(good=189)
        self.assertEqual(ProductionEvent.objects.count(), 2)

    def test_run_snapshots_survive_master_edits(self):
        RecipeLine.objects.filter(recipe=self.bom.recipe, item__code="FLOUR").update(quantity=1000)
        BOMLine.objects.filter(bom=self.bom, item__code="POUCH").update(quantity=1)
        BOM.objects.filter(pk=self.bom.pk).update(expected_packets=10, version=2)
        Recipe.objects.filter(pk=self.bom.recipe_id).update(version=2)
        self.run.refresh_from_db()
        self.assertEqual((self.run.bom_version, self.run.recipe_version), (1, 1))
        self.finish()
        report = run_report(self.run)
        self.assertEqual(report["expected_packets"], 200)
        self.assertEqual(report["consumption"]["FLOUR"]["planned"], 40000)
        self.assertEqual(report["consumption"]["POUCH"]["planned"], 200)

    def test_500g_sku_shares_recipe_not_packaging(self):
        self.finish()
        bom500 = add_500g_bom(self.bom.recipe, self.actor, self.supplier, DAY)
        self.assertEqual(bom500.recipe_id, self.bom.recipe_id)
        run500 = create_run(bom=bom500, batches=1, request_key="run-500", document_date=DAY, actor=self.actor)
        issue_run(run=run500, actual={**RAW, "OIL": 10000}, request_key="issue-500", actor=self.actor)
        complete_run(run=run500, actual={"POUCH500": 80, "CARTON": 4}, good_packets=80,
                     damaged={}, request_key="complete-500", actor=self.actor)
        report = run_report(run500)
        self.assertEqual(report["expected_packets"], 80)
        self.assertEqual(report["yield"]["ratio"], 0)
        self.assertEqual(report["consumption"]["FLOUR"]["planned"], 40000)
        self.assertNotIn("POUCH", report["consumption"])
        self.assertEqual(stock_summary()["MURUKKU500"]["quantity"], 80)
        self.assertEqual(stock_summary()["MURUKKU200"]["quantity"], 238)
        self.assertEqual(stock_summary()["POUCH500"]["quantity"], 20)
        reconcile_stock()

    def test_one_gram_residual_and_full_depletion(self):
        # 3 g worth 10 paise: issue 1 g for 3p -> 2 g/7p; next 1 g costs 4p -> 1 g/3p.
        item = Item.objects.create(code="ROUNDING", name="Rounding ingredient", category="raw", base_unit="g")
        post_receipt(kind="purchase", request_key="rounding-stock", document_date=DAY,
                     actor=self.actor, supplier=self.supplier, lines=[(item, 3, 10)])
        recipe = Recipe.objects.create(code="ROUNDING", version=1)
        RecipeLine.objects.create(recipe=recipe, item=item, quantity=1)
        bom = BOM.objects.create(sku=self.bom.sku, version=2, recipe=recipe, expected_packets=1)
        for index, (quantity, value, cost) in enumerate([(2, 7, 3), (1, 3, 4), (0, 0, 3)]):
            run = create_run(bom=bom, batches=1, request_key=f"round-{index}", document_date=DAY, actor=self.actor)
            issue_run(run=run, actual={"ROUNDING": 1}, request_key=f"round-issue-{index}", actor=self.actor)
            self.assertEqual(stock_summary()["ROUNDING"], {"quantity": quantity, "value_paise": value})
            self.assertEqual(run_report(run)["materials_paise"], cost)
            if index == 0:
                self.assertEqual(weighted_average(item), Fraction(7, 2))
        self.assertIsNone(weighted_average(item))
        self.assertEqual(issue_value(2, 2, 7), 7)
        reconcile_stock()

    def test_zero_output_zero_usage_and_unknown_cost(self):
        self.issue()
        complete_run(run=self.run, actual={"POUCH": 0, "CARTON": 0}, good_packets=0,
                     damaged={}, request_key="zero-output", actor=self.actor)
        report = run_report(self.run)
        self.assertIsNone(report["cost_per_packet_paise"])
        self.assertEqual(report["materials_paise"], 343500)
        self.assertEqual(stock_summary()["MURUKKU200"]["quantity"], 50)
        self.assertEqual(issue_value(0, 0, None), 0)
        with self.assertRaises(ValidationError):
            issue_value(1, 2, None)
        with self.assertRaises(ValidationError):
            issue_value(1.5, 2, 3)
        reconcile_stock()

    def test_overhead_retry_and_authorization(self):
        args = dict(run=self.run, label="Labour", amount_paise=120000, request_key="labour", document_date=DAY, actor=self.actor)
        with self.assertRaises(ValidationError):
            add_overhead(**args)
        self.finish()
        first = add_overhead(**args)
        self.assertEqual(add_overhead(**args).pk, first.pk)
        with self.assertRaises(ValidationError):
            add_overhead(**{**args, "amount_paise": 1})
        self.assertEqual(Overhead.objects.count(), 1)
        user = get_user_model().objects.create_user(username="unauthorized")
        with self.assertRaises(PermissionDenied):
            create_run(bom=self.bom, batches=1, request_key="no", document_date=DAY, actor=user)
        with self.assertRaises(PermissionDenied):
            set_tolerance(basis_points=200, actor=user)
        with self.assertRaises(ValidationError):
            set_tolerance(basis_points=10001, actor=self.actor)

    def test_invalid_payloads_and_stage_categories(self):
        for actual in ({"FLOUR": 1}, {**RAW, "SPICE": -1}, {**RAW, "OIL": True}):
            with self.assertRaises(ValidationError):
                self.issue(actual)
        self.issue()
        with self.assertRaises(ValidationError):
            complete_run(run=self.run, actual=PACK, good_packets=188, damaged={"POUCH": 195},
                         request_key="invalid", actor=self.actor)
        BOMLine.objects.filter(bom=self.bom, item__code="POUCH").update(item=Item.objects.get(code="FLOUR"))
        with self.assertRaises(ValidationError):
            create_run(bom=self.bom, batches=1, request_key="bad-bom", document_date=DAY, actor=self.actor)
        self.assertFalse(ProductionRun.objects.filter(request_key="bad-bom").exists())
