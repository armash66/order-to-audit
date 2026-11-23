"""Nine PS steps through native services; a single outer transaction rolls back by default."""

from datetime import date
from fractions import Fraction
from sqlalchemy import text
from api import database, reporting
from api.seed import seed_benchmark
from api.services import user_by_name
from api.native import factory_lock, now, balance
from api.inventory.services import post_receipt
from api.production.services import create_run, post_event, add_overhead, run_report
from api.sales.services import command, available, get_row, outstanding
from api.queries import rows, order_detail
from api.reconciliation import reconcile


class RollbackBenchmark(Exception):
    pass


def run_benchmark(persist=False):
    results = []

    def check(label, expected, actual):
        results.append((label, expected, actual, expected == actual))

    try:
        with database.transaction() as conn:
            seed_benchmark()
            factory_lock(conn)
            if conn.execute(
                text(
                    "SELECT id FROM inventory_posting WHERE opening_id IS NULL LIMIT 1"
                )
            ).first():
                raise ValueError(
                    "Benchmark requires opening-only data. Use a separate fresh Compose project."
                )
            user = user_by_name(conn, "admin")
            a = user_by_name(conn, "salesman_a")
            b = user_by_name(conn, "salesman_b")
            day = "2026-11-19"
            start = date(2026, 11, 1)
            end = max(date(2026, 11, 30), now().date())
            items = {
                item["code"]: item["id"]
                for item in rows(conn, "SELECT id,code FROM inventory_item")
            }
            supplier = rows(
                conn, "SELECT id FROM inventory_supplier WHERE code='FLOUR-SUPPLIER'"
            )[0]["id"]
            sku = rows(
                conn,
                "SELECT id FROM inventory_sku WHERE item_id=:id",
                id=items["MURUKKU200"],
            )[0]["id"]
            bom = rows(
                conn,
                "SELECT id FROM inventory_bom WHERE sku_id=:id AND version=1",
                id=sku,
            )[0]["id"]
            customers = {
                row["code"]: row["id"]
                for row in rows(conn, "SELECT id,code FROM inventory_customer")
            }

            def balances(step, expected, reserved=0):
                actual = reconcile()
                codes = ["FLOUR", "OIL", "SPICE", "POUCH", "CARTON", "MURUKKU200"]
                check(
                    step + " stock (g/ml/piece)",
                    expected,
                    [actual[code]["quantity"] for code in codes],
                )
                stock = available(conn, items["MURUKKU200"])
                check(
                    step + " reserved/available",
                    [reserved, expected[-1] - reserved],
                    [actual["MURUKKU200"]["quantity"] - stock, stock],
                )

            def sale(action, data, actor=user, key=None):
                return command(
                    action, {**data, "date": day}, actor, key or "benchmark-" + action
                )

            balances("0", [100000, 30000, 5000, 500, 30, 50])
            post_receipt(
                {
                    "supplier": supplier,
                    "date": day,
                    "lines": [
                        {
                            "item": items["FLOUR"],
                            "quantity": "60",
                            "unit": "kg",
                            "value_paise": 270000,
                        }
                    ],
                },
                user,
                "benchmark-purchase",
            )
            balances("1", [160000, 30000, 5000, 500, 30, 50])
            quantity, value = balance(conn, items["FLOUR"])
            check(
                "1 flour paise/kg", Fraction(8625, 2), Fraction(value * 1000, quantity)
            )
            run = create_run(
                {"bom": bom, "batches": 1, "date": day}, user, "benchmark-run"
            )
            post_event(
                "issue",
                {"id": run, "actual": {
                    "FLOUR": {"quantity": "40", "unit": "kg"},
                    "OIL": {"quantity": "10.5", "unit": "L"},
                    "SPICE": {"quantity": "1.2", "unit": "kg"},
                }},
                user,
                "benchmark-issue",
            )
            balances("2", [120000, 19500, 3800, 500, 30, 50])
            post_event(
                "complete",
                {
                    "id": run,
                    "actual": {"POUCH": 194, "CARTON": 9},
                    "good_packets": 188,
                    "damaged": {"POUCH": 6},
                },
                user,
                "benchmark-complete",
            )
            stock = [120000, 19500, 3800, 306, 21, 238]
            balances("3", stock)
            report = run_report(run, user)
            check("3 yield", Fraction(-6, 100), report["yield"]["ratio"])
            check("3 oil", Fraction(5, 100), report["consumption"]["OIL"]["ratio"])
            check(
                "3 flags yield/oil/carton/pouch",
                [True, True, True, False],
                [
                    report["yield"]["flagged"],
                    *[
                        report["consumption"][code]["flagged"]
                        for code in ("OIL", "CARTON", "POUCH")
                    ],
                ],
            )
            order = sale(
                "order.create",
                {"customer": customers["A"], "quantities": {str(sku): 150}},
                a,
                "benchmark-a",
            )
            balances("4", stock)
            sale("order.approve", {"id": order})
            balances("5a", stock, 150)
            invoice_id = sale("order.invoice", {"id": order})
            balances("5b", stock, 150)
            invoice = get_row(conn, "sales_invoice", invoice_id)
            check(
                "5b invoice paise",
                [750000, 18750, 18750, 787500],
                [
                    invoice[field]
                    for field in (
                        "taxable_paise",
                        "cgst_paise",
                        "sgst_paise",
                        "total_paise",
                    )
                ],
            )
            sale("order.dispatch", {"id": order})
            stock = [*stock[:-1], 88]
            balances("5c", stock)
            other = sale(
                "order.create",
                {"customer": customers["B"], "quantities": {str(sku): 120}},
                b,
                "benchmark-b",
            )
            check("6 shortage", 32, order_detail(other, user)["stock"][0]["shortage"])
            try:
                sale("order.approve", {"id": other})
                check("6 approval rejected", True, False)
            except ValueError:
                check("6 approval rejected", True, True)
            balances("6", stock)
            sale("order.payment", {"id": order, "amount_paise": 400000})
            check("7 outstanding paise", 387500, outstanding(conn, invoice))
            balances("7", stock)
            for key, label, amount in [
                ("labour", "Labour", 120000),
                ("gas", "Gas/power", 60000),
            ]:
                add_overhead(
                    {"id": run, "label": label, "amount_paise": amount, "date": day},
                    user,
                    "benchmark-" + key,
                )
            report = run_report(run, user)
            check(
                "8 materials/run paise",
                [405500, 585500],
                [report["materials_paise"], report["total_paise"]],
            )
            check(
                "8 cost paise exact",
                Fraction(585500, 188),
                report["cost_per_packet_paise"],
            )
            check("8 displayed cost paise", 3114, report["display_cost_paise"])
            balances("8", stock)
            for kind in reporting.REPORTS:
                report = reporting.report_table(kind, start, end, user)
                check(
                    "9 " + kind + " CSV/PDF",
                    True,
                    bool(reporting.csv_bytes(report))
                    and reporting.table_pdf(report).startswith(b"%PDF"),
                )
            check(
                "9 customer sales",
                [["Demo Retailer A", "150", "7,500.00"]],
                reporting.report_table(
                    "customers", date.fromisoformat(day), date.fromisoformat(day), user
                )["rows"],
            )
            for cutoff, index in [(date(2026, 12, 19), 6), (date(2026, 12, 20), 7)]:
                check(
                    "9 ageing " + str(cutoff),
                    "3,875.00",
                    reporting.report_table("ageing", start, cutoff, user)["rows"][0][
                        index
                    ],
                )
            balances("9", stock)
            if not persist or not all(row[3] for row in results):
                raise RollbackBenchmark()
    except RollbackBenchmark:
        pass
    return results
