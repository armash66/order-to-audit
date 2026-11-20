import csv
from io import StringIO
from datetime import date
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from weasyprint import HTML
from access.services import require_role
from inventory.models import FactoryControl, Item, StockMovement, PurchaseReceipt
from production.models import ProductionRun
from production.services import run_report
from sales.models import Invoice, CreditNote, Payment, Order
from sales.services import outstanding
from webapp.templatetags.display import money, percent

REPORTS = {
    "sales": "Sales register", "customers": "Customer-wise sales", "products": "Product-wise sales",
    "gst": "GST summary", "purchases": "Purchase register", "stock": "Stock summary",
    "ledger": "Stock ledger", "production": "Production consumption and yield",
    "collections": "Payments and collections", "ageing": "Outstanding and ageing",
}


# Credit events reverse invoice snapshots on the credit date, including historical ranges.
def sales_events(start, end, actor):
    own = not actor.is_staff and actor.groups.filter(name="salesman").exists()
    invoices = Invoice.objects.exclude(status="draft").select_related("order")
    if own:
        invoices = invoices.filter(order__actor=actor)
    events = [(invoice.document_date, invoice, 1) for invoice in invoices.filter(document_date__range=(start,end))]
    for credit in CreditNote.objects.filter(invoice__in=invoices, document_date__range=(start,end)).select_related("invoice"):
        events.append((credit.document_date, credit.invoice, -1))
    return sorted(events, key=lambda row: (row[0], row[1].pk, -row[2]))


# One locked snapshot keeps multi-query totals consistent with concurrent posting.
@transaction.atomic
def report_table(kind, start, end, actor):
    require_role(actor, ["admin","accountant","owner","salesman"])
    if kind not in REPORTS or start > end:
        raise ValidationError("Choose a report and a valid date range.")
    if not actor.is_staff and actor.groups.filter(name="salesman").exists() and kind != "customers":
        raise PermissionDenied("Salesmen may read their own customer sales only.")
    FactoryControl.objects.select_for_update().get(pk=1)
    rows = []
    if kind in ("sales","customers","products","gst"):
        events = sales_events(start,end,actor)
        if kind == "sales":
            headers = ["Date","Invoice","Event","Customer","Taxable INR","CGST INR","SGST INR","IGST INR","Total INR"]
            for day, invoice, sign in events:
                rows.append([str(day),invoice.number,"Invoice" if sign==1 else "Credit",invoice.customer_name,
                    *[money(sign*getattr(invoice,field)) for field in ("taxable_paise","cgst_paise","sgst_paise","igst_paise","total_paise")]])
        elif kind == "gst":
            headers = ["GSTR-1 category","GSTR-3B field","Taxable INR","CGST INR","SGST INR","IGST INR"]
            totals = {}
            for _, invoice, sign in events:
                category = "B2B (Table 4)" if invoice.customer_gstin else "B2C (Table 7, exercise scope)"
                values = totals.setdefault(category,[0,0,0,0])
                for index,field in enumerate(("taxable_paise","cgst_paise","sgst_paise","igst_paise")):
                    values[index] += sign*getattr(invoice,field)
            rows = [[key,"3.1(a) outward taxable",*[money(value) for value in values]] for key,values in sorted(totals.items())]
        else:
            headers = ["Customer" if kind=="customers" else "Product","Packets","Taxable INR"]
            totals = {}
            for _, invoice, sign in events:
                for line in invoice.lines.all():
                    key = invoice.customer_name if kind=="customers" else line.description
                    values = totals.setdefault(key,[0,0])
                    values[0] += sign*line.quantity
                    values[1] += sign*line.taxable_paise
            rows = [[key,str(values[0]),money(values[1])] for key,values in sorted(totals.items())]
    elif kind == "purchases":
        headers = ["Date","Receipt","Supplier","Item","Quantity (base)","Unit","Value INR"]
        for receipt in PurchaseReceipt.objects.filter(document_date__range=(start,end)).select_related("supplier"):
            for line in receipt.lines.select_related("item"):
                rows.append([str(receipt.document_date),str(receipt.pk),receipt.supplier.name,line.item.code,str(line.quantity),line.item.base_unit,money(line.value_paise)])
    elif kind in ("stock","ledger"):
        movements = StockMovement.objects.select_related("posting","item").order_by("posting__sequence","pk")
        if kind == "ledger":
            headers = ["Sequence","Posting time","Document date","Source URL","Item","Quantity (base)","Unit","Value INR"]
            for movement in movements.filter(posting__posted_at__date__range=(start,end)):
                posting = movement.posting
                source = posting.opening or posting.purchase or posting.production or posting.dispatch or posting.adjustment
                rows.append([str(posting.sequence),posting.posted_at.isoformat(),str(source.document_date),f"/sources/{posting.pk}/",movement.item.code,str(movement.quantity),movement.item.base_unit,"Unknown" if movement.value_paise is None else money(movement.value_paise)])
        else:
            headers = ["Item","Category","Unit","Opening","Change","Closing","Closing value INR","Valuation basis"]
            for item in Item.objects.all():
                opening=change=value=0
                for movement in movements.filter(item=item,posting__posted_at__date__lte=end):
                    from django.utils.timezone import localdate
                    if localdate(movement.posting.posted_at) < start: opening += movement.quantity
                    else: change += movement.quantity
                    value = None if value is None or movement.value_paise is None else value+movement.value_paise
                rows.append([item.code,item.category,item.base_unit,str(opening),str(change),str(opening+change),"Unknown" if value is None else money(value),"Materials-only" if item.category=="finished" else "Weighted average"])
    elif kind == "production":
        headers = ["Run","Date","State","Expected","Good","Yield","Unclassified shortfall","Damaged packaging","Materials INR","Overhead INR","Cost/packet INR","Consumption / alerts"]
        for run in ProductionRun.objects.filter(document_date__range=(start,end)):
            report = run_report(run)
            details = "; ".join(f"{code}: {v['actual']}/{v['planned']} {percent(v['ratio'])} {'FLAG' if v['flagged'] else ''}" for code,v in report["consumption"].items())
            rows.append([str(run.pk),str(run.document_date),run.state,str(run.expected_packets),str(run.good_packets or 0),percent(report["yield"]["ratio"]),str(report["unclassified_shortfall"]),str(report["damaged_packaging"]),money(report["materials_paise"]),money(report["overhead_paise"]),money(report["cost_per_packet_paise"]) if report["cost_per_packet_paise"] is not None else "N/A",details])
    elif kind == "collections":
        headers = ["Date","Payment","Invoice","Customer","Collected INR"]
        for payment in Payment.objects.filter(document_date__range=(start,end)).select_related("invoice"):
            rows.append([str(payment.document_date),str(payment.pk),payment.invoice.number,payment.invoice.customer_name,money(payment.amount_paise)])
    else:
        headers = ["Customer","Invoice","Due date","Original INR","Outstanding INR","Current","1-30","31-60","61-90","91+"]
        for invoice in Invoice.objects.exclude(status="draft").filter(document_date__lte=end):
            due = outstanding(invoice,end)
            if not due: continue
            days = (end-invoice.document_date).days
            index = 0 if days<=0 else 1 if days<=30 else 2 if days<=60 else 3 if days<=90 else 4
            buckets = [0]*5
            buckets[index] = due
            rows.append([invoice.customer_name,invoice.number,str(invoice.document_date),money(invoice.total_paise),money(due),*[money(value) for value in buckets]])
    return {"title": REPORTS[kind], "headers": headers, "rows": rows, "start": start, "end": end}


# BOM-prefixed CSV preserves UTF-8 in Excel; formula-like user labels are escaped.
def csv_bytes(table):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    for row in [table["headers"],*table["rows"]]:
        writer.writerow(["'"+str(value) if str(value).startswith(("=","+","@","\t","\r")) else str(value) for value in row])
    return stream.getvalue().encode("utf-8-sig")


def table_pdf(table):
    return HTML(string=render_to_string("report_pdf.html",table)).write_pdf()


@transaction.atomic
def dashboard(actor, today):
    require_role(actor,["admin","owner","accountant"])
    FactoryControl.objects.select_for_update().get(pk=1)
    from inventory.services import stock_summary
    runs = [run_report(run) for run in ProductionRun.objects.filter(state="completed")]
    return {"orders_today":Order.objects.filter(document_date=today).count(),"stock":stock_summary(),
        "outstanding":sum(outstanding(invoice,today) for invoice in Invoice.objects.exclude(status="draft").filter(document_date__lte=today)),
        "flagged_runs":sum(any(value["flagged"] for value in report["consumption"].values()) or report["yield"]["flagged"] for report in runs),
        "run_cost":sum(report["total_paise"] for report in runs)}
