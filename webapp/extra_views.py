from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from inventory.models import Customer, SKU
from access.services import require_role
from sales.models import CustomerPrice
from sales.services import set_customer_price
from .forms import money_input
from .views import context, failure


@login_required
def pricing(request):
    require_role(request.user,["admin"])
    if request.method == "POST":
        try:
            set_customer_price(customer=get_object_or_404(Customer,pk=request.POST["customer"]),
                sku=get_object_or_404(SKU,pk=request.POST["sku"]),price_paise=money_input(request.POST["price"]),
                label=request.POST["label"],actor=request.user)
            messages.success(request,"Customer price saved; existing order prices stay frozen.")
            return redirect("pricing")
        except (ValidationError,KeyError,ValueError) as error:
            failure(request,error)
    return render(request,"pricing.html",context(request,customers=Customer.objects.all(),skus=SKU.objects.select_related("item"),prices=CustomerPrice.objects.select_related("customer","sku__item")))


@login_required
def customer_prices(request,pk):
    from django.http import JsonResponse
    from sales.services import prices_for_customer
    from .templatetags.display import money
    rows=prices_for_customer(get_object_or_404(Customer,pk=pk),request.user)
    return JsonResponse({"products":[{"id":row["sku_id"],"name":f'{row["name"]} · INR {money(row["price_paise"])} · {row["label"]}'} for row in rows]})


@login_required
def batches(request):
    from django.utils import timezone
    from inventory.models import Item
    from inventory.services import lot_balances, set_reorder_level, reorder_alerts
    require_role(request.user,["admin","production","accountant","owner"])
    if request.method=="POST":
        try:
            set_reorder_level(item=get_object_or_404(Item,pk=request.POST["item"]),minimum_quantity=int(request.POST["minimum"]),actor=request.user)
            return redirect("batches")
        except (ValidationError,ValueError,KeyError) as error: failure(request,error)
    return render(request,"batches.html",context(request,lots=lot_balances(),alerts=reorder_alerts(),items=Item.objects.filter(category="raw"),as_of=timezone.localdate()))


@login_required
def visits(request):
    from extensions.services import record_visit, visits_for
    rows=visits_for(request.user)
    if request.method=="POST":
        try:
            record_visit(customer=get_object_or_404(Customer,pk=request.POST["customer"]),route=request.POST["route"],note=request.POST.get("note",""),
                request_key=request.POST["request_key"],actor=request.user,consent=request.POST.get("consent")=="on",
                latitude=request.POST.get("latitude") or None,longitude=request.POST.get("longitude") or None)
            return redirect("visits")
        except (ValidationError,ValueError,KeyError) as error: failure(request,error)
    return render(request,"visits.html",context(request,visits=rows,customers=Customer.objects.all()))


@login_required
def mock_documents(request,pk):
    from django.http import HttpResponse
    from sales.models import Invoice
    from extensions.models import MockSubmission
    from extensions.services import create_mock_document, exact_json
    require_role(request.user,["admin","accountant","owner"])
    invoice=get_object_or_404(Invoice,pk=pk)
    if request.method=="POST":
        try:
            create_mock_document(invoice=invoice,kind=request.POST["kind"],actor=request.user,
                vehicle=request.POST.get("vehicle") or "TN00DEMO0000",distance_km=int(request.POST.get("distance") or 1))
            return redirect("mock_documents",pk=pk)
        except (ValidationError,ValueError,KeyError) as error: failure(request,error)
    if request.GET.get("download"):
        document=get_object_or_404(MockSubmission,invoice=invoice,kind=request.GET["download"])
        payload='{"mock":true,"request":'+document.request_json+',"response":'+exact_json(document.response)+'}'
        response=HttpResponse(payload,content_type="application/json")
        response["Content-Disposition"]=f'attachment; filename="MOCK-{document.kind}-{invoice.pk}.json"'
        return response
    return render(request,"mock_documents.html",context(request,invoice=invoice,documents=MockSubmission.objects.filter(invoice=invoice)))


@login_required
def tally_download(request):
    from datetime import date
    from django.http import HttpResponse
    from django.utils import timezone
    from reporting.services import tally_export
    try:
        end=date.fromisoformat(request.GET.get("end") or str(timezone.localdate()))
        start=date.fromisoformat(request.GET.get("start") or str(end.replace(day=1)))
        output=tally_export(start,end,request.user)
    except (ValidationError,ValueError) as error:
        return HttpResponse(str(error),status=400)
    return HttpResponse(output,content_type="application/zip",headers={"Content-Disposition":'attachment; filename="tally-demo.zip"'})
