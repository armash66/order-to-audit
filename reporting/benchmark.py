from datetime import date
from fractions import Fraction
from copy import deepcopy
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from inventory.seed import seed_benchmark
from inventory.models import Item, SKU, Customer, Supplier, BOM, Posting, FactoryControl
from inventory.services import post_receipt, reconcile_stock, weighted_average
from production.services import create_run, issue_run, complete_run, add_overhead, run_report
from sales.services import submit_order, approve_order, invoice_order, dispatch_invoice, stock_check, record_payment, outstanding, available_stock
from .services import REPORTS, report_table, csv_bytes, table_pdf

DAY = date(2026,11,19)
CODES = ["FLOUR","OIL","SPICE","POUCH","CARTON","MURUKKU200"]


# All scenario writes use real services; rollback makes the seeded exercise repeatable.
@transaction.atomic
def run_benchmark(persist=False):
    seed_benchmark()
    FactoryControl.objects.select_for_update().get(pk=1)
    if Posting.objects.exclude(opening__isnull=False).exists():
        raise ValidationError("Benchmark requires opening-only data. Use a separate fresh Compose project; never reset operational data.")
    actor=User.objects.get(username="benchmark-seed")
    salesmen=[]
    for name in ("salesman_a","salesman_b"):
        user,_=User.objects.get_or_create(username=name)
        user.groups.add(Group.objects.get_or_create(name="salesman")[0])
        salesmen.append(user)
    results=[]
    def check(label, expected, actual):
        results.append((label,deepcopy(expected),deepcopy(actual),expected==actual))
    def balance(step, quantities, reserved=0):
        values=available_stock()
        check(step+" stock (g/ml/piece)",quantities,[values[code]["quantity"] for code in CODES])
        fg=values["MURUKKU200"]
        check(step+" reserved/available",[reserved,quantities[-1]-reserved],[fg["reserved"],fg["available"]])
        reconcile_stock()
    balance("0",[100000,30000,5000,500,30,50])
    post_receipt(kind="purchase",request_key="benchmark-purchase",document_date=DAY,actor=actor,supplier=Supplier.objects.get(code="FLOUR-SUPPLIER"),lines=[(Item.objects.get(code="FLOUR"),60000,270000)])
    balance("1",[160000,30000,5000,500,30,50])
    check("1 flour paise/kg",Fraction(8625,2),weighted_average(Item.objects.get(code="FLOUR"))*1000)
    run=create_run(bom=BOM.objects.get(sku__item__code="MURUKKU200"),batches=1,request_key="benchmark-run",document_date=DAY,actor=actor)
    issue_run(run=run,actual={"FLOUR":40000,"OIL":10500,"SPICE":1200},request_key="benchmark-issue",actor=actor)
    balance("2",[120000,19500,3800,500,30,50])
    complete_run(run=run,actual={"POUCH":194,"CARTON":9},good_packets=188,damaged={"POUCH":6},request_key="benchmark-complete",actor=actor)
    stock=[120000,19500,3800,306,21,238]
    balance("3",stock)
    report=run_report(run)
    check("3 yield",Fraction(-6,100),report["yield"]["ratio"])
    check("3 oil",Fraction(5,100),report["consumption"]["OIL"]["ratio"])
    check("3 flags yield/oil/carton/pouch",[True,True,True,False],[report["yield"]["flagged"],*[report["consumption"][code]["flagged"] for code in ("OIL","CARTON","POUCH")]])
    sku=SKU.objects.get(item__code="MURUKKU200")
    order=submit_order(customer=Customer.objects.get(code="A"),quantities={sku.pk:150},request_key="benchmark-a",document_date=DAY,actor=salesmen[0])
    balance("4",stock)
    approve_order(order,actor)
    balance("5a",stock,150)
    invoice=invoice_order(order,actor,DAY)
    balance("5b",stock,150)
    check("5b invoice paise",[750000,18750,18750,787500],[invoice.taxable_paise,invoice.cgst_paise,invoice.sgst_paise,invoice.total_paise])
    dispatch_invoice(invoice,actor,DAY)
    stock[-1]=88
    balance("5c",stock)
    b=submit_order(customer=Customer.objects.get(code="B"),quantities={sku.pk:120},request_key="benchmark-b",document_date=DAY,actor=salesmen[1])
    check("6 shortage",32,stock_check(b,actor)[0]["shortage"])
    try:
        approve_order(b,actor)
        check("6 approval rejected",True,False)
    except ValidationError:
        check("6 approval rejected",True,True)
    balance("6",stock)
    record_payment(invoice=invoice,amount_paise=400000,request_key="benchmark-payment",document_date=DAY,actor=actor)
    check("7 outstanding paise",387500,outstanding(invoice))
    balance("7",stock)
    for key,label,amount in [("labour","Labour",120000),("gas","Gas/power",60000)]:
        add_overhead(run=run,label=label,amount_paise=amount,request_key="benchmark-"+key,document_date=DAY,actor=actor)
    report=run_report(run)
    check("8 materials/run paise",[405500,585500],[report["materials_paise"],report["total_paise"]])
    check("8 cost paise exact",Fraction(585500,188),report["cost_per_packet_paise"])
    check("8 displayed cost paise",3114,report["display_cost_paise"])
    balance("8",stock)
    # Stock uses posting time, so cover today's posting month as well as fixture dates.
    end=max(date(2026,11,30),timezone.localdate())
    for kind in REPORTS:
        table=report_table(kind,date(2026,11,1),end,actor)
        check("9 "+kind+" CSV/PDF",True,bool(csv_bytes(table)) and table_pdf(table).startswith(b"%PDF"))
    check("9 customer sales",[["Demo Retailer A","150","7,500.00"]],report_table("customers",DAY,DAY,actor)["rows"])
    for cutoff,index in [(date(2026,12,19),6),(date(2026,12,20),7)]:
        check("9 ageing "+str(cutoff),"3,875.00",report_table("ageing",DAY,cutoff,actor)["rows"][0][index])
    balance("9",stock)
    if not persist or not all(row[3] for row in results):
        transaction.set_rollback(True)
    return results
