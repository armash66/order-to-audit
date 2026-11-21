from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from access.services import require_role
from inventory.models import SKU, Customer, Supplier, Item, BOM, StockMovement, PurchaseReceipt
from inventory.services import post_receipt, to_base_units, stock_summary
from production.models import ProductionRun
from production.services import create_run, issue_run, complete_run, add_overhead, run_report, edit_run_draft, set_tolerance
from sales.models import Order, Invoice
from sales.services import (submit_order, stock_check, approve_order, reject_order, invoice_order, dispatch_invoice,
                            record_payment, outstanding, credit_invoice, order_for_actor, edit_order, edit_invoice_draft,
                            return_goods, dispatch_remaining)
from .forms import money_input


def context(request, **values):
    if request.GET.get("lang") in ("en","ta","hi","mr"):
        request.session["floor_language"]=request.GET["lang"]
    roles = set(request.user.groups.values_list("name", flat=True))
    staff = request.user.is_staff
    return dict(values, floor_language=request.session.get("floor_language","en"), is_admin=staff or "admin" in roles, is_production=staff or bool(roles & {"admin","production"}),
                is_sales=staff or bool(roles & {"admin","salesman"}), is_reports=staff or bool(roles & {"admin","accountant","owner"}),
                is_stock=staff or bool(roles & {"admin","production","accountant","owner"}), today=timezone.localdate(), request_key=str(uuid4()))


def failure(request, error):
    messages.error(request, "; ".join(error.messages) if isinstance(error,ValidationError) else str(error))


@login_required
def home(request):
    require_role(request.user,["salesman","admin","production","accountant","owner"])
    if request.user.is_staff or request.user.groups.filter(name__in=["admin","owner","accountant"]).exists():
        from reporting.services import dashboard
        summary=dashboard(request.user,timezone.localdate())
        for item in Item.objects.all():
            summary['stock'][item.code].update(unit=item.base_unit,name=item.name)
        return render(request,"dashboard.html",context(request,dashboard=summary))
    return render(request,"home.html",context(request))


@login_required
def orders(request):
    require_role(request.user,["salesman","admin","accountant","owner"])
    if request.method == "POST":
        require_role(request.user,["salesman","admin"])
        try:
            sku_ids=request.POST.getlist("sku")
            quantities=request.POST.getlist("quantity")
            if len(sku_ids)!=len(quantities) or len(sku_ids)!=len(set(sku_ids)):
                raise ValidationError("Select each product once.")
            order=submit_order(customer=get_object_or_404(Customer,pk=request.POST["customer"]),
                quantities={int(k):int(v) for k,v in zip(sku_ids,quantities)},request_key=request.POST["request_key"],
                document_date=timezone.localdate(),actor=request.user)
            return redirect("order",pk=order.pk)
        except (ValidationError,ValueError,KeyError) as error: failure(request,error)
    rows=Order.objects.select_related("customer","actor").order_by("-pk")
    if not request.user.is_staff and request.user.groups.filter(name="salesman").exists(): rows=rows.filter(actor=request.user)
    from django.db.models import Q
    query=request.GET.get("q","").strip()
    status=request.GET.get("status","")
    statuses=["submitted","approved","invoiced","dispatched","rejected"]
    if status in statuses: rows=rows.filter(status=status)
    if query:
        matches=Q(customer__name__icontains=query)|Q(customer__code__icontains=query)
        if query.isdecimal(): matches |= Q(pk=int(query))
        rows=rows.filter(matches)
    return render(request,"orders.html",context(request,orders=rows,query=query,selected_status=status,statuses=statuses,customers=Customer.objects.all(),skus=SKU.objects.select_related("item")))


@login_required
def order_detail(request,pk):
    order=order_for_actor(get_object_or_404(Order,pk=pk),request.user)
    if request.method == "POST":
        require_role(request.user,["admin"])
        try:
            action=request.POST["action"]
            day=date.fromisoformat(request.POST.get("date") or str(timezone.localdate()))
            invoice=Invoice.objects.filter(order=order).first()
            if action=="approve": approve_order(order,request.user)
            elif action=="reject": reject_order(order,request.POST.get("reason",""),request.user)
            elif action=="invoice": invoice_order(order,request.user,day)
            elif action=="draft": invoice_order(order,request.user,day,draft=True)
            elif action=="edit_invoice": edit_invoice_draft(invoice,day,request.user)
            elif action=="dispatch": dispatch_invoice(invoice,request.user,day)
            elif action=="partial_dispatch":
                quantities={row["item_id"]:int(request.POST.get(f"ship_{row['item_id']}",0)) for row in dispatch_remaining(invoice)}
                dispatch_invoice(invoice,request.user,day,quantities={key:value for key,value in quantities.items() if value},request_key=request.POST["request_key"])
            elif action=="return":
                quantities={row["item_id"]:int(request.POST.get(f"return_{row['item_id']}",0)) for row in dispatch_remaining(invoice)}
                return_goods(invoice=invoice,quantities={key:value for key,value in quantities.items() if value},reason=request.POST["reason"],request_key=request.POST["request_key"],document_date=day,actor=request.user)
            elif action=="payment": record_payment(invoice=invoice,amount_paise=money_input(request.POST["amount"]),request_key=request.POST["request_key"],document_date=day,actor=request.user)
            elif action=="credit": credit_invoice(invoice,request.POST.get("reason",""),request.user,day)
            elif action=="edit": edit_order(order,{str(l.pk):[int(request.POST[f"qty_{l.pk}"]),money_input(request.POST[f"price_{l.pk}"])] for l in order.lines.all()},request.user)
            else: raise ValidationError("Unknown action.")
            messages.success(request,"Action recorded.")
            return redirect("order",pk=pk)
        except (ValidationError,ValueError,KeyError,AttributeError) as error: failure(request,error)
    order.refresh_from_db()
    invoice=Invoice.objects.filter(order=order).first()
    suggestions=[]
    if request.user.is_staff or request.user.groups.filter(name="admin").exists():
        from production.services import suggest_production
        for line in order.lines.select_related("sku__item"):
            if BOM.objects.filter(sku=line.sku).exists():
                suggestions.append(suggest_production(sku=line.sku,actor=request.user))
    return render(request,"order.html",context(request,suggestions=suggestions,order=order,lines=order.lines.select_related("sku__item"),checks=stock_check(order,request.user),invoice=invoice,due=outstanding(invoice) if invoice else None,fulfilment=dispatch_remaining(invoice) if invoice else []))


@login_required
def production(request):
    require_role(request.user,["admin","production"])
    if request.method=="POST":
        try:
            action=request.POST["action"]
            day=date.fromisoformat(request.POST.get("date") or str(timezone.localdate()))
            if action=="create":
                expiry=date.fromisoformat(request.POST["output_expiry"]) if request.POST.get("output_expiry") else None
                run=create_run(bom=get_object_or_404(BOM,pk=request.POST["bom"]),batches=int(request.POST["batches"]),request_key=request.POST["request_key"],document_date=day,actor=request.user,output_expiry=expiry)
                return redirect("run",pk=run.pk)
            if action=="receipt":
                item=get_object_or_404(Item,pk=request.POST["item"])
                quantity=to_base_units(item,request.POST["unit"],Decimal(request.POST["quantity"]))
                post_receipt(kind="purchase",request_key=request.POST["request_key"],document_date=day,actor=request.user,
                    supplier=get_object_or_404(Supplier,pk=request.POST["supplier"]),lines=[(item,quantity,money_input(request.POST["value"]))],
                    lot_details={item.code:{"code":request.POST.get("batch_code"),"expiry":request.POST.get("expiry")}} if request.POST.get("batch_code") or request.POST.get("expiry") else None)
                messages.success(request,"Receipt posted.")
                return redirect("production")
        except (ValidationError,ValueError,KeyError,InvalidOperation,ObjectDoesNotExist) as error: failure(request,error)
    return render(request,"production.html",context(request,runs=ProductionRun.objects.select_related("output_item").order_by("-pk"),boms=BOM.objects.select_related("sku__item"),items=Item.objects.exclude(category="finished"),suppliers=Supplier.objects.all()))


@login_required
def run_detail(request,pk):
    require_role(request.user,["admin","production"])
    run=get_object_or_404(ProductionRun,pk=pk)
    if request.method=="POST":
        try:
            action=request.POST["action"]
            if action in ("issue","complete"):
                stage="raw" if action=="issue" else "packaging"
                actual={s.item.code:int(request.POST[f"actual_{s.item_id}"]) for s in run.standards.filter(stage=stage).select_related("item")}
                if action=="issue": issue_run(run=run,actual=actual,request_key=request.POST["request_key"],actor=request.user)
                else:
                    damaged={s.item.code:int(request.POST.get(f"damage_{s.item_id}","0")) for s in run.standards.filter(stage=stage).select_related("item")}
                    complete_run(run=run,actual=actual,good_packets=int(request.POST["good_packets"]),damaged=damaged,request_key=request.POST["request_key"],actor=request.user)
            elif action=="overhead": add_overhead(run=run,label=request.POST["label"],amount_paise=money_input(request.POST["amount"]),request_key=request.POST["request_key"],document_date=timezone.localdate(),actor=request.user)
            elif action=="edit": edit_run_draft(run,int(request.POST["batches"]),request.user)
            elif action=="reverse":
                from inventory.services import reverse_run
                reverse_run(run=run,reason=request.POST["reason"],request_key=request.POST["request_key"],document_date=timezone.localdate(),actor=request.user)
            elif action=="tolerance": set_tolerance(basis_points=money_input(request.POST["tolerance"]),actor=request.user)
            else: raise ValidationError("Unknown action.")
            return redirect("run",pk=pk)
        except (ValidationError,ValueError,KeyError,InvalidOperation) as error: failure(request,error)
    run.refresh_from_db()
    return render(request,"run.html",context(request,run=run,report=run_report(run),raw=run.standards.filter(stage="raw").select_related("item"),packaging=run.standards.filter(stage="packaging").select_related("item")))


@login_required
def stock(request):
    require_role(request.user,["admin","production","accountant","owner"])
    if request.method == "POST":
        from inventory.services import adjust_stock
        try:
            adjust_stock(item=get_object_or_404(Item,pk=request.POST["item"]),quantity=int(request.POST["quantity"]),value_paise=money_input(request.POST["value"]) if request.POST.get("value") else None,reason=request.POST["reason"],request_key=request.POST["request_key"],document_date=timezone.localdate(),actor=request.user)
            return redirect("stock")
        except (ValidationError,ValueError,KeyError,InvalidOperation) as error: failure(request,error)
    balances=stock_summary()
    for item in Item.objects.all():
        balances[item.code].update(unit=item.base_unit,category=item.category,name=item.name)
    return render(request,"stock.html",context(request,balances=balances,items=Item.objects.all()))


@login_required
def ledger(request,code):
    require_role(request.user,["admin","production","accountant","owner"])
    item=get_object_or_404(Item,code=code)
    movements=StockMovement.objects.filter(item=item).select_related("posting","posting__production","posting__dispatch").order_by("posting__sequence","pk")
    return render(request,"ledger.html",context(request,item=item,movements=movements))


@login_required
def source_document(request,pk):
    require_role(request.user,["admin","production","accountant","owner"])
    from inventory.models import Posting
    posting=get_object_or_404(Posting,pk=pk)
    source=posting.opening or posting.purchase or posting.production or posting.dispatch or posting.adjustment
    return render(request,"source.html",context(request,posting=posting,source=source,lines=source.lines.select_related("item")))


@login_required
def download_invoice(request, pk):
    from django.http import HttpResponse
    from .services import invoice_pdf
    invoice=get_object_or_404(Invoice,pk=pk)
    try:
        data=invoice_pdf(invoice,request.user)
    except ValidationError as error:
        return HttpResponse(str(error),status=400)
    response=HttpResponse(data,content_type="application/pdf")
    response["Content-Disposition"]=f'attachment; filename="invoice-{invoice.pk}.pdf"'
    return response


@login_required
def reports(request):
    from django.http import HttpResponse
    from reporting.services import REPORTS, report_table, csv_bytes, table_pdf
    own = not request.user.is_staff and request.user.groups.filter(name="salesman").exists()
    choices = {"customers":REPORTS["customers"]} if own else REPORTS
    kind=request.GET.get("report","customers" if own else "sales")
    try:
        end=date.fromisoformat(request.GET.get("end",str(timezone.localdate())))
        start=date.fromisoformat(request.GET.get("start",str(end.replace(day=1))))
        table=report_table(kind,start,end,request.user)
    except (ValueError,ValidationError) as error:
        return HttpResponse(str(error),status=400)
    output=request.GET.get("format")
    if output in ("csv","pdf"):
        data=csv_bytes(table) if output=="csv" else table_pdf(table)
        response=HttpResponse(data,content_type="text/csv; charset=utf-8" if output=="csv" else "application/pdf")
        response["Content-Disposition"]=f'attachment; filename="{kind}.{output}"'
        return response
    return render(request,"reports.html",context(request,reports=choices,kind=kind,table=table))


def offline_shell(request):
    return render(request,"offline.html")


def service_worker(request):
    from django.http import HttpResponse
    from django.conf import settings
    return HttpResponse((settings.BASE_DIR/"static/service-worker.js").read_text(encoding="utf-8"),content_type="application/javascript",headers={"Cache-Control":"no-cache"})


@login_required
def offline_catalog(request):
    from django.http import JsonResponse
    from django.middleware.csrf import get_token
    from .templatetags.display import money
    from sales.services import prices_for_customer
    require_role(request.user,["admin","salesman"])
    response=JsonResponse({"user_id":request.user.pk,"username":request.user.username,"csrf":get_token(request),
        "customers":list(Customer.objects.values("id","name")),
        "customer_prices":{str(customer.pk):[{"id":row["sku_id"],"name":f'{row["name"]} INR {money(row["price_paise"])} · {row["label"]}'} for row in prices_for_customer(customer,request.user)] for customer in Customer.objects.all()},
        "skus":[{"id":sku.pk,"name":sku.item.name+" INR "+money(sku.price_paise)} for sku in SKU.objects.select_related("item")]})
    response["Cache-Control"]="no-store"
    return response


@login_required
def offline_sync(request):
    import json
    from django.http import JsonResponse, HttpResponseNotAllowed
    from .services import sync_offline_order
    if request.method != "POST": return HttpResponseNotAllowed(["POST"])
    try:
        payload=json.loads(request.body)
        if not isinstance(payload,dict): raise ValidationError("Order object required.")
        order=sync_offline_order(payload,request.user)
    except (ValidationError,ValueError,TypeError) as error:
        return JsonResponse({"error":str(error)},status=400)
    return JsonResponse({"order_id":order.pk,"status":order.status})
