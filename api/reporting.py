"""Auditor reports from immutable snapshots and ledger posting times using SQLAlchemy."""

import csv
from io import StringIO
from fractions import Fraction
from fastapi import HTTPException
from sqlalchemy import text
from api import database
from api.native import authorize, factory_lock, now, round_paise, balance
from api.queries import rows
from api.sales.services import outstanding, available, get_row
from api.production.services import run_report
from api.pdf import money, table_pdf

REPORTS = {
    "sales": "Sales register",
    "customers": "Customer-wise sales",
    "products": "Product-wise sales",
    "gst": "GST summary",
    "purchases": "Purchase register",
    "stock": "Stock summary",
    "ledger": "Stock ledger",
    "production": "Production consumption and yield",
    "collections": "Payments and collections",
    "ageing": "Outstanding and ageing",
    "customer_ageing": "Customer outstanding and ageing",
}
TAX_FIELDS = ("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise")


def percent(ratio):
    if ratio is None:
        return "N/A"
    value = round_paise(Fraction(ratio) * 10000)
    return ("-" if value < 0 else "+") + f"{abs(value)//100}.{abs(value)%100:02d}%"


# Credits and returns are separate dated events; posted invoice snapshots remain unchanged.
def sales_events(conn, start, end, user):
    own = not user["is_staff"] and "salesman" in user["roles"]
    invoices = rows(
        conn,
        """SELECT i.*,o.customer_id,c.code AS customer_code FROM sales_invoice i
        JOIN sales_order o ON o.id=i.order_id JOIN inventory_customer c ON c.id=o.customer_id
        WHERE i.status<>'draft' AND (:own=FALSE OR o.actor_id=:actor)""",
        own=own,
        actor=user["id"],
    )
    events = []
    for invoice in invoices:
        invoice["lines"] = rows(
            conn,
            "SELECT * FROM sales_invoiceline WHERE invoice_id=:id ORDER BY id",
            id=invoice["id"],
        )
        if start <= invoice["document_date"] <= end:
            events.append((invoice["document_date"], invoice, 1))
        for credit in rows(
            conn,
            "SELECT * FROM sales_creditnote WHERE invoice_id=:id AND document_date BETWEEN :start AND :end",
            id=invoice["id"],
            start=start,
            end=end,
        ):
            events.append((credit["document_date"], invoice, -1))
        for note in rows(
            conn,
            "SELECT * FROM sales_salesreturn WHERE invoice_id=:id AND document_date BETWEEN :start AND :end",
            id=invoice["id"],
            start=start,
            end=end,
        ):
            lines = rows(
                conn,
                """SELECT l.*,i.description FROM sales_returnline l JOIN sales_invoiceline i ON i.id=l.invoice_line_id
                WHERE l.document_id=:id ORDER BY l.id""",
                id=note["id"],
            )
            snapshot = {
                **invoice,
                "number": f"RETURN-{note['id']} / {invoice['number']}",
                "total_paise": note["amount_paise"],
                "lines": lines,
                **{field: sum(line[field] for line in lines) for field in TAX_FIELDS},
            }
            events.append((note["document_date"], snapshot, -1))
    return sorted(events, key=lambda event: (event[0], event[1]["id"], -event[2]))


# One factory lock covers all report queries, including current-tolerance production costing.
def report_table(kind, start, end, user):
    authorize(user, ["admin", "accountant", "owner", "salesman"])
    if kind not in REPORTS or start > end:
        raise ValueError("Choose a report and valid date range.")
    if not user["is_staff"] and "salesman" in user["roles"] and kind != "customers":
        raise HTTPException(403, "Salesmen may read their own customer sales only.")
    with database.transaction() as conn:
        factory_lock(conn)
        result = []
        if kind in ("sales", "customers", "products", "gst"):
            events = sales_events(conn, start, end, user)
            if kind == "sales":
                headers = [
                    "Date",
                    "Invoice",
                    "Event",
                    "Customer",
                    "Taxable INR",
                    "CGST INR",
                    "SGST INR",
                    "IGST INR",
                    "Total INR",
                ]
                result = [
                    [
                        str(day),
                        invoice["number"],
                        "Invoice" if sign == 1 else "Credit",
                        invoice["customer_name"],
                        *[
                            money(sign * invoice[field])
                            for field in (*TAX_FIELDS, "total_paise")
                        ],
                    ]
                    for day, invoice, sign in events
                ]
            elif kind == "gst":
                headers = [
                    "GSTR-1 category",
                    "GSTR-3B field",
                    "Taxable INR",
                    "CGST INR",
                    "SGST INR",
                    "IGST INR",
                ]
                totals = {}
                for _, invoice, sign in events:
                    category = (
                        "B2B (Table 4)"
                        if invoice["customer_gstin"]
                        else "B2C (Table 7, exercise scope)"
                    )
                    values = totals.setdefault(category, [0] * 4)
                    for index, field in enumerate(TAX_FIELDS):
                        values[index] += sign * invoice[field]
                result = [
                    [key, "3.1(a) outward taxable", *[money(value) for value in values]]
                    for key, values in sorted(totals.items())
                ]
            else:
                headers = [
                    "Customer" if kind == "customers" else "Product",
                    "Packets",
                    "Taxable INR",
                ]
                totals = {}
                for _, invoice, sign in events:
                    for line in invoice["lines"]:
                        key = (
                            invoice["customer_name"]
                            if kind == "customers"
                            else line["description"]
                        )
                        values = totals.setdefault(key, [0, 0])
                        values[0] += sign * line["quantity"]
                        values[1] += sign * line["taxable_paise"]
                result = [
                    [key, str(values[0]), money(values[1])]
                    for key, values in sorted(totals.items())
                ]
        elif kind == "purchases":
            headers = [
                "Date",
                "Receipt",
                "Supplier",
                "Item",
                "Quantity (base)",
                "Unit",
                "Value INR",
            ]
            for row in rows(
                conn,
                """SELECT p.id,p.document_date,s.name,i.code,i.base_unit,l.quantity,l.value_paise
                FROM inventory_purchasereceipt p JOIN inventory_supplier s ON s.id=p.supplier_id JOIN inventory_purchaseline l ON l.document_id=p.id
                JOIN inventory_item i ON i.id=l.item_id WHERE p.document_date BETWEEN :start AND :end ORDER BY p.id,l.id""",
                start=start,
                end=end,
            ):
                result.append(
                    [
                        str(row["document_date"]),
                        str(row["id"]),
                        row["name"],
                        row["code"],
                        str(row["quantity"]),
                        row["base_unit"],
                        money(row["value_paise"]),
                    ]
                )
        elif kind in ("stock", "ledger"):
            movements = rows(
                conn,
                """SELECT m.*,p.sequence,p.posted_at,i.code,i.base_unit,
                COALESCE(o.document_date,r.document_date,e.document_date,d.document_date,a.document_date) AS document_date
                FROM inventory_stockmovement m JOIN inventory_posting p ON p.id=m.posting_id JOIN inventory_item i ON i.id=m.item_id
                LEFT JOIN inventory_openingstock o ON o.id=p.opening_id LEFT JOIN inventory_purchasereceipt r ON r.id=p.purchase_id
                LEFT JOIN production_productionevent e ON e.id=p.production_id LEFT JOIN sales_dispatch d ON d.id=p.dispatch_id
                LEFT JOIN inventory_adjustment a ON a.id=p.adjustment_id ORDER BY p.sequence,m.id""",
            )
            if kind == "ledger":
                headers = [
                    "Sequence",
                    "Posting time",
                    "Document date",
                    "Source URL",
                    "Item",
                    "Quantity (base)",
                    "Unit",
                    "Value INR",
                ]
                for row in movements:
                    if start <= row["posted_at"].astimezone(now().tzinfo).date() <= end:
                        result.append(
                            [
                                str(row["sequence"]),
                                row["posted_at"].isoformat(),
                                str(row["document_date"]),
                                f"/api/workspace/sources/{row['posting_id']}",
                                row["code"],
                                str(row["quantity"]),
                                row["base_unit"],
                                (
                                    "Unknown"
                                    if row["value_paise"] is None
                                    else money(row["value_paise"])
                                ),
                            ]
                        )
            else:
                headers = [
                    "Item",
                    "Category",
                    "Unit",
                    "Opening",
                    "Change",
                    "Closing",
                    "Closing value INR",
                    "Valuation basis",
                ]
                for item in rows(conn, "SELECT * FROM inventory_item ORDER BY id"):
                    opening = change = value = 0
                    for row in movements:
                        day = row["posted_at"].astimezone(now().tzinfo).date()
                        if row["item_id"] != item["id"] or day > end:
                            continue
                        if day < start:
                            opening += row["quantity"]
                        else:
                            change += row["quantity"]
                        value = (
                            None
                            if value is None or row["value_paise"] is None
                            else value + row["value_paise"]
                        )
                    result.append(
                        [
                            item["code"],
                            item["category"],
                            item["base_unit"],
                            str(opening),
                            str(change),
                            str(opening + change),
                            "Unknown" if value is None else money(value),
                            (
                                "Materials-only"
                                if item["category"] == "finished"
                                else "Weighted average"
                            ),
                        ]
                    )
        elif kind == "production":
            headers = [
                "Run",
                "Date",
                "State",
                "Expected",
                "Good",
                "Yield",
                "Unclassified shortfall",
                "Damaged packaging",
                "Materials INR",
                "Overhead INR",
                "Cost/packet INR",
                "Consumption / alerts",
            ]
            for run in rows(
                conn,
                "SELECT * FROM production_productionrun WHERE document_date BETWEEN :start AND :end ORDER BY id",
                start=start,
                end=end,
            ):
                report = run_report(run["id"], user, conn)
                details = "; ".join(
                    f"{code}: {value['actual']}/{value['planned']} {percent(value['ratio'])} {'FLAG' if value['flagged'] else ''}"
                    for code, value in report["consumption"].items()
                )
                result.append(
                    [
                        str(run["id"]),
                        str(run["document_date"]),
                        run["state"],
                        str(run["expected_packets"]),
                        str(run["good_packets"] or 0),
                        percent(report["yield"]["ratio"]),
                        str(report["unclassified_shortfall"]),
                        str(report["damaged_packaging"]),
                        money(report["materials_paise"]),
                        money(report["overhead_paise"]),
                        (
                            money(report["cost_per_packet_paise"])
                            if report["cost_per_packet_paise"] is not None
                            else "N/A"
                        ),
                        details,
                    ]
                )
        elif kind == "collections":
            headers = ["Date", "Payment", "Invoice", "Customer", "Collected INR"]
            result = [
                [
                    str(row["document_date"]),
                    str(row["id"]),
                    row["number"],
                    row["customer_name"],
                    money(row["amount_paise"]),
                ]
                for row in rows(
                    conn,
                    """SELECT p.*,i.number,i.customer_name FROM sales_payment p JOIN sales_invoice i ON i.id=p.invoice_id
                WHERE p.document_date BETWEEN :start AND :end ORDER BY p.id""",
                    start=start,
                    end=end,
                )
            ]
        else:
            headers = [
                "Customer",
                "Invoice",
                "Due date",
                "Original INR",
                "Outstanding INR",
                "Current",
                "1-30",
                "31-60",
                "61-90",
                "91+",
            ]
            customers = {}
            invoices = rows(
                conn,
                """SELECT i.*,c.id AS customer_id,c.code AS customer_code,c.name FROM sales_invoice i
                JOIN sales_order o ON o.id=i.order_id JOIN inventory_customer c ON c.id=o.customer_id
                WHERE i.status<>'draft' AND i.document_date<=:end ORDER BY i.id""",
                end=end,
            )
            for invoice in invoices:
                due = outstanding(conn, invoice, end)
                if not due:
                    continue
                days = (end - invoice["document_date"]).days
                index = (
                    0
                    if days <= 0 or due < 0
                    else (
                        1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4
                    )
                )
                buckets = [0] * 5
                buckets[index] = due
                result.append(
                    [
                        invoice["customer_name"],
                        invoice["number"],
                        str(invoice["document_date"]),
                        money(invoice["total_paise"]),
                        money(due),
                        *[money(value) for value in buckets],
                    ]
                )
                total = customers.setdefault(
                    invoice["customer_id"],
                    {
                        "code": invoice["customer_code"],
                        "name": invoice["name"],
                        "due": 0,
                        "buckets": [0] * 5,
                    },
                )
                total["due"] += due
                total["buckets"][index] += due
            if kind == "customer_ageing":
                headers = [
                    "Customer code",
                    "Customer",
                    "Outstanding INR",
                    "Current",
                    "1-30",
                    "31-60",
                    "61-90",
                    "91+",
                ]
                result = [
                    [
                        value["code"],
                        value["name"],
                        money(value["due"]),
                        *[money(amount) for amount in value["buckets"]],
                    ]
                    for value in customers.values()
                ]
        return {
            "title": REPORTS[kind],
            "headers": headers,
            "rows": result,
            "start": start,
            "end": end,
        }


def csv_bytes(report):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    for row in [report["headers"], *report["rows"]]:
        writer.writerow(
            [
                (
                    "'" + str(value)
                    if str(value).startswith(("=", "+", "@", "\t", "\r"))
                    else str(value)
                )
                for value in row
            ]
        )
    return stream.getvalue().encode("utf-8-sig")


def dashboard(user, today):
    authorize(user, ["admin", "owner", "accountant"])
    with database.transaction() as conn:
        factory_lock(conn)
        products = {}
        reports = []
        stock = {}
        alerts = []
        for run in rows(
            conn,
            "SELECT r.*,b.sku_id,s.price_paise,i.name FROM production_productionrun r JOIN inventory_bom b ON b.id=r.bom_id JOIN inventory_sku s ON s.id=b.sku_id JOIN inventory_item i ON i.id=r.output_item_id WHERE r.state='completed'",
        ):
            report = run_report(run["id"], user, conn)
            reports.append(report)
            product = products.setdefault(
                run["sku_id"],
                {
                    "name": run["name"],
                    "sku": run["sku_id"],
                    "cost": 0,
                    "good": 0,
                    "price": run["price_paise"],
                },
            )
            product["cost"] += report["total_paise"]
            product["good"] += run["good_packets"]
        for product in products.values():
            product["unit_cost"] = (
                Fraction(product["cost"], product["good"]) if product["good"] else None
            )
            price = product.pop("price")
            product["margin"] = (
                price - product["unit_cost"]
                if product["unit_cost"] is not None
                else None
            )
        for item in rows(conn, "SELECT * FROM inventory_item ORDER BY id"):
            quantity, value = balance(conn, item["id"])
            stock[item["code"]] = {"quantity": quantity, "value_paise": value}
            if item["category"] == "finished":
                stock[item["code"]]["valuation_basis"] = "materials-only"
        for level in rows(
            conn,
            "SELECT r.*,i.name FROM inventory_reorderlevel r JOIN inventory_item i ON i.id=r.item_id",
        ):
            quantity = available(conn, level["item_id"])
            if quantity <= level["minimum_quantity"]:
                alerts.append(
                    {
                        "item": level["item_id"],
                        "available": quantity,
                        "minimum": level["minimum_quantity"],
                    }
                )
        return {
            "orders_today": conn.execute(
                text("SELECT COUNT(*) FROM sales_order WHERE document_date=:today"),
                {"today": today},
            ).scalar_one(),
            "stock": stock,
            "outstanding": sum(
                outstanding(conn, invoice, today)
                for invoice in rows(
                    conn,
                    "SELECT * FROM sales_invoice WHERE status<>'draft' AND document_date<=:today",
                    today=today,
                )
            ),
            "flagged_runs": sum(
                any(value["flagged"] for value in report["consumption"].values())
                or report["yield"]["flagged"]
                for report in reports
            ),
            "run_cost": sum(report["total_paise"] for report in reports),
            "products": list(products.values()),
            "reorder_alerts": alerts,
            "due_followups": [
                followup for followup in rows(conn, """SELECT
                    f.invoice_id,f.next_contact,f.note,c.name AS customer,v.number AS invoice
                    FROM (SELECT DISTINCT ON (invoice_id) invoice_id,next_contact,note
                        FROM factory_collectionfollowup ORDER BY invoice_id,id DESC) f
                    JOIN sales_invoice v ON v.id=f.invoice_id
                    JOIN sales_order o ON o.id=v.order_id JOIN inventory_customer c ON c.id=o.customer_id
                    WHERE f.next_contact<=:today ORDER BY f.next_contact,f.invoice_id""", today=today)
                if outstanding(conn, get_row(conn, "sales_invoice", followup["invoice_id"]), today) > 0
            ],
        }


# Accounting-only export balances every voucher in paise before serializing decimal text.
def tally_export(start, end, user):
    from io import BytesIO
    from zipfile import ZipFile
    from xml.etree.ElementTree import Element, SubElement, tostring
    from uuid import uuid5, NAMESPACE_URL

    authorize(user, ["admin", "accountant", "owner"])
    if start > end:
        raise ValueError("Invalid export date range.")

    def envelope(report):
        root = Element("ENVELOPE")
        SubElement(SubElement(root, "HEADER"), "TALLYREQUEST").text = "Import Data"
        data = SubElement(SubElement(root, "BODY"), "IMPORTDATA")
        SubElement(SubElement(data, "REQUESTDESC"), "REPORTNAME").text = report
        return root, SubElement(data, "REQUESTDATA")

    masters, master_data = envelope("All Masters")
    vouchers, voucher_data = envelope("Vouchers")

    def voucher(day, kind, reference, entries):
        if sum(amount for _, amount in entries) != 0:
            raise ValueError("Unbalanced accounting voucher.")
        identity = str(uuid5(NAMESPACE_URL, "order-to-audit/" + reference))
        element = SubElement(
            SubElement(voucher_data, "TALLYMESSAGE"),
            "VOUCHER",
            {"VCHTYPE": kind, "ACTION": "Create", "REMOTEID": identity},
        )
        for tag, value in {
            "DATE": day.strftime("%Y%m%d"),
            "GUID": identity,
            "VOUCHERTYPENAME": kind,
            "VOUCHERNUMBER": reference,
            "PERSISTEDVIEW": "Accounting Voucher View",
            "ISINVOICE": "No",
            "NARRATION": "Order-to-Audit fictional demonstration",
        }.items():
            SubElement(element, tag).text = value
        for name, amount in entries:
            if not amount:
                continue
            entry = SubElement(element, "ALLLEDGERENTRIES.LIST")
            SubElement(entry, "LEDGERNAME").text = name
            SubElement(entry, "ISDEEMEDPOSITIVE").text = "Yes" if amount < 0 else "No"
            SubElement(entry, "AMOUNT").text = money(amount).replace(",", "")

    with database.transaction() as conn:
        factory_lock(conn)
        ledgers = {
            "OTA Sales": "Sales Accounts",
            "OTA Purchases": "Purchase Accounts",
            "OTA Overheads": "Indirect Expenses",
            "OTA Accrued Costs": "Current Liabilities",
            "OTA Cash": "Cash-in-Hand",
            **{
                f"OTA Output {tax}": "Duties & Taxes"
                for tax in ("CGST", "SGST", "IGST")
            },
        }
        ledgers.update(
            {
                f"Customer {row['code']}": "Sundry Debtors"
                for row in rows(conn, "SELECT code FROM inventory_customer ORDER BY id")
            }
        )
        ledgers.update(
            {
                f"Supplier {row['code']}": "Sundry Creditors"
                for row in rows(conn, "SELECT code FROM inventory_supplier ORDER BY id")
            }
        )
        for name, parent in ledgers.items():
            ledger = SubElement(
                SubElement(master_data, "TALLYMESSAGE"),
                "LEDGER",
                {"NAME": name, "ACTION": "Create"},
            )
            SubElement(ledger, "NAME").text = name
            SubElement(ledger, "PARENT").text = parent
        for day, invoice, sign in sales_events(conn, start, end, user):
            entries = [
                (
                    f"Customer {invoice['customer_code']}",
                    -sign * invoice["total_paise"],
                ),
                ("OTA Sales", sign * invoice["taxable_paise"]),
            ]
            entries.extend(
                (f"OTA Output {tax}", sign * invoice[tax.lower() + "_paise"])
                for tax in ("CGST", "SGST", "IGST")
            )
            voucher(
                day,
                "Sales" if sign == 1 else "Credit Note",
                ("SALE-" if sign == 1 else "CREDIT-") + invoice["number"],
                entries,
            )
        for row in rows(
            conn,
            """SELECT p.id,p.document_date,s.code,SUM(l.value_paise) AS amount FROM inventory_purchasereceipt p
            JOIN inventory_supplier s ON s.id=p.supplier_id JOIN inventory_purchaseline l ON l.document_id=p.id
            WHERE p.document_date BETWEEN :start AND :end GROUP BY p.id,s.code ORDER BY p.id""",
            start=start,
            end=end,
        ):
            amount = int(row["amount"])
            voucher(
                row["document_date"],
                "Purchase",
                f"PURCHASE-{row['id']}",
                [("OTA Purchases", -amount), (f"Supplier {row['code']}", amount)],
            )
        for row in rows(
            conn,
            """SELECT p.*,c.code FROM sales_payment p JOIN sales_invoice i ON i.id=p.invoice_id
            JOIN sales_order o ON o.id=i.order_id JOIN inventory_customer c ON c.id=o.customer_id
            WHERE p.document_date BETWEEN :start AND :end ORDER BY p.id""",
            start=start,
            end=end,
        ):
            voucher(
                row["document_date"],
                "Receipt",
                f"PAYMENT-{row['id']}",
                [
                    ("OTA Cash", -row["amount_paise"]),
                    (f"Customer {row['code']}", row["amount_paise"]),
                ],
            )
        for row in rows(
            conn,
            "SELECT * FROM production_overhead WHERE document_date BETWEEN :start AND :end ORDER BY id",
            start=start,
            end=end,
        ):
            voucher(
                row["document_date"],
                "Journal",
                f"OVERHEAD-{row['id']}",
                [
                    ("OTA Overheads", -row["amount_paise"]),
                    ("OTA Accrued Costs", row["amount_paise"]),
                ],
            )
        for row in rows(
            conn,
            """SELECT a.id,a.document_date,SUM(o.amount_paise) AS amount FROM inventory_adjustment a
            JOIN production_overhead o ON o.run_id=a.reversed_run_id WHERE a.document_date BETWEEN :start AND :end
            GROUP BY a.id ORDER BY a.id""",
            start=start,
            end=end,
        ):
            amount = int(row["amount"])
            voucher(
                row["document_date"],
                "Journal",
                f"REVERSE-COST-{row['id']}",
                [("OTA Overheads", amount), ("OTA Accrued Costs", -amount)],
            )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "masters.xml", tostring(masters, encoding="utf-8", xml_declaration=True)
        )
        archive.writestr(
            "vouchers.xml", tostring(vouchers, encoding="utf-8", xml_declaration=True)
        )
        archive.writestr(
            "README.txt",
            "Import masters.xml then vouchers.xml into a separate demo Tally company. Accounting-only export; no input GST is invented. XML structure and balanced entries are tested; a real Tally import has not been run. Avoid importing overlapping ranges twice. Sources: https://help.tallysolutions.com/sample-xml/",
        )
    return output.getvalue()
