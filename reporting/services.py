import csv
from io import StringIO
from datetime import date
from fractions import Fraction
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from weasyprint import HTML
from access.services import require_role
from inventory.models import FactoryControl, Item, StockMovement, PurchaseReceipt
from production.models import ProductionRun
from production.services import run_report
from sales.models import Invoice, CreditNote, Payment, Order, SalesReturn
from sales.services import outstanding
from webapp.templatetags.display import money, percent

REPORTS = {
    "sales": "Sales register", "customers": "Customer-wise sales", "products": "Product-wise sales",
    "gst": "GST summary", "purchases": "Purchase register", "stock": "Stock summary",
    "ledger": "Stock ledger", "production": "Production consumption and yield",
    "collections": "Payments and collections", "ageing": "Outstanding and ageing",
    "customer_ageing": "Customer outstanding and ageing",
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
    for note in SalesReturn.objects.filter(invoice__in=invoices,document_date__range=(start,end)).select_related("invoice__order"):
        lines=[SimpleNamespace(description=line.invoice_line.description,quantity=line.quantity,taxable_paise=line.taxable_paise)
               for line in note.lines.select_related("invoice_line")]
        totals={field:sum(note.lines.values_list(field,flat=True)) for field in ("taxable_paise","cgst_paise","sgst_paise","igst_paise")}
        snapshot=SimpleNamespace(pk=note.invoice_id,number=f"RETURN-{note.pk} / {note.invoice.number}",
            customer_name=note.invoice.customer_name,customer_gstin=note.invoice.customer_gstin,
            total_paise=note.amount_paise,order=note.invoice.order,lines=SimpleNamespace(all=lambda rows=lines:rows),**totals)
        events.append((note.document_date,snapshot,-1))
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
        customers = {}
        for invoice in Invoice.objects.exclude(status="draft").filter(document_date__lte=end).select_related("order__customer"):
            due = outstanding(invoice,end)
            if not due: continue
            days = (end-invoice.document_date).days
            index = 0 if days<=0 or due<0 else 1 if days<=30 else 2 if days<=60 else 3 if days<=90 else 4
            buckets = [0]*5
            buckets[index] = due
            rows.append([invoice.customer_name,invoice.number,str(invoice.document_date),money(invoice.total_paise),money(due),*[money(value) for value in buckets]])
            total = customers.setdefault(invoice.order.customer_id, {"code": invoice.order.customer.code, "name": invoice.order.customer.name, "due": 0, "buckets": [0]*5})
            total["due"] += due
            total["buckets"][index] += due
        if kind == "customer_ageing":
            headers = ["Customer code","Customer","Outstanding INR","Current","1-30","31-60","61-90","91+"]
            rows = [[value["code"],value["name"],money(value["due"]),*[money(amount) for amount in value["buckets"]]] for value in customers.values()]
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
    from inventory.services import stock_summary, reorder_alerts
    runs = []
    products = {}
    for run in ProductionRun.objects.filter(state="completed").select_related("bom__sku__item"):
        report = run_report(run)
        runs.append(report)
        product = products.setdefault(run.bom.sku_id, {"name": run.output_item.name, "sku": run.bom.sku, "cost": 0, "good": 0})
        product["cost"] += report["total_paise"]
        product["good"] += run.good_packets
    for product in products.values():
        product["unit_cost"] = Fraction(product["cost"], product["good"]) if product["good"] else None
        product["margin"] = product["sku"].price_paise - product["unit_cost"] if product["unit_cost"] is not None else None
    return {"orders_today":Order.objects.filter(document_date=today).count(),"stock":stock_summary(),
        "outstanding":sum(outstanding(invoice,today) for invoice in Invoice.objects.exclude(status="draft").filter(document_date__lte=today)),
        "flagged_runs":sum(any(value["flagged"] for value in report["consumption"].values()) or report["yield"]["flagged"] for report in runs),
        "run_cost":sum(report["total_paise"] for report in runs), "products": list(products.values()), "reorder_alerts":reorder_alerts()}


# Tally accounting vouchers balance in paise; inventory remains in this application's ledger.
@transaction.atomic
def tally_export(start, end, actor):
    from io import BytesIO
    from zipfile import ZipFile
    from xml.etree.ElementTree import Element, SubElement, tostring
    from uuid import uuid5, NAMESPACE_URL
    from inventory.models import Customer, Supplier, Adjustment
    from production.models import Overhead
    require_role(actor,["admin","accountant","owner"])
    if start>end: raise ValidationError("Invalid export date range.")
    FactoryControl.objects.select_for_update().get(pk=1)

    def envelope(report):
        root=Element("ENVELOPE")
        SubElement(SubElement(root,"HEADER"),"TALLYREQUEST").text="Import Data"
        data=SubElement(SubElement(root,"BODY"),"IMPORTDATA")
        SubElement(SubElement(data,"REQUESTDESC"),"REPORTNAME").text=report
        return root,SubElement(data,"REQUESTDATA")

    masters,master_data=envelope("All Masters")
    ledgers={"OTA Sales":"Sales Accounts","OTA Purchases":"Purchase Accounts","OTA Overheads":"Indirect Expenses",
             "OTA Accrued Costs":"Current Liabilities","OTA Cash":"Cash-in-Hand",
             **{f"OTA Output {tax}":"Duties & Taxes" for tax in ("CGST","SGST","IGST")}}
    ledgers.update({f"Customer {customer.code}":"Sundry Debtors" for customer in Customer.objects.all()})
    ledgers.update({f"Supplier {supplier.code}":"Sundry Creditors" for supplier in Supplier.objects.all()})
    for name,parent in ledgers.items():
        ledger=SubElement(SubElement(master_data,"TALLYMESSAGE"),"LEDGER",{"NAME":name,"ACTION":"Create"})
        SubElement(ledger,"NAME").text=name
        SubElement(ledger,"PARENT").text=parent
    vouchers,voucher_data=envelope("Vouchers")

    def voucher(day,kind,reference,entries):
        if sum(amount for _,amount in entries)!=0: raise ValidationError("Unbalanced accounting voucher.")
        identity=str(uuid5(NAMESPACE_URL,"order-to-audit/"+reference))
        element=SubElement(SubElement(voucher_data,"TALLYMESSAGE"),"VOUCHER",{"VCHTYPE":kind,"ACTION":"Create","REMOTEID":identity})
        for tag,value in {"DATE":day.strftime('%Y%m%d'),"GUID":identity,"VOUCHERTYPENAME":kind,"VOUCHERNUMBER":reference,
                          "PERSISTEDVIEW":"Accounting Voucher View","ISINVOICE":"No","NARRATION":"Order-to-Audit fictional demonstration"}.items():
            SubElement(element,tag).text=value
        for name,amount in entries:
            if not amount: continue
            entry=SubElement(element,"ALLLEDGERENTRIES.LIST")
            SubElement(entry,"LEDGERNAME").text=name
            SubElement(entry,"ISDEEMEDPOSITIVE").text="Yes" if amount<0 else "No"
            SubElement(entry,"AMOUNT").text=money(amount).replace(',','')

    for day,invoice,sign in sales_events(start,end,actor):
        entries=[(f"Customer {invoice.order.customer.code}",-sign*invoice.total_paise),("OTA Sales",sign*invoice.taxable_paise)]
        entries.extend((f"OTA Output {tax}",sign*getattr(invoice,tax.lower()+"_paise")) for tax in ("CGST","SGST","IGST"))
        voucher(day,"Sales" if sign==1 else "Credit Note",("SALE-" if sign==1 else "CREDIT-")+invoice.number,entries)
    for receipt in PurchaseReceipt.objects.filter(document_date__range=(start,end)).select_related("supplier"):
        amount=sum(receipt.lines.values_list("value_paise",flat=True))
        voucher(receipt.document_date,"Purchase",f"PURCHASE-{receipt.pk}",[("OTA Purchases",-amount),(f"Supplier {receipt.supplier.code}",amount)])
    for payment in Payment.objects.filter(document_date__range=(start,end)).select_related("invoice__order__customer"):
        voucher(payment.document_date,"Receipt",f"PAYMENT-{payment.pk}",[("OTA Cash",-payment.amount_paise),(f"Customer {payment.invoice.order.customer.code}",payment.amount_paise)])
    for overhead in Overhead.objects.filter(document_date__range=(start,end)):
        voucher(overhead.document_date,"Journal",f"OVERHEAD-{overhead.pk}",[("OTA Overheads",-overhead.amount_paise),("OTA Accrued Costs",overhead.amount_paise)])
    for reversal in Adjustment.objects.filter(reversed_run__isnull=False,document_date__range=(start,end)):
        amount=sum(reversal.reversed_run.overheads.values_list('amount_paise',flat=True))
        if amount: voucher(reversal.document_date,"Journal",f"REVERSE-COST-{reversal.pk}",[("OTA Overheads",amount),("OTA Accrued Costs",-amount)])
    output=BytesIO()
    with ZipFile(output,'w') as archive:
        archive.writestr('masters.xml',tostring(masters,encoding='utf-8',xml_declaration=True))
        archive.writestr('vouchers.xml',tostring(vouchers,encoding='utf-8',xml_declaration=True))
        archive.writestr('README.txt','Import masters.xml then vouchers.xml into a separate demo Tally company. Accounting-only export; no input GST is invented. Check the import log before using totals. XML structure and balanced entries are tested; a real Tally import has not been run. Avoid importing overlapping ranges twice. Sources: https://help.tallysolutions.com/sample-xml/')
    return output.getvalue()
