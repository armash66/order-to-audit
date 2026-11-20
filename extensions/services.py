import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from access.services import require_role, audit
from inventory.models import FactoryControl
from inventory.services import require_integer
from sales.models import Invoice
from .models import Visit, MockSubmission


# GPS input is decimal text; stored millionths of a degree avoid binary-coordinate drift.
def coordinate(value, limit):
    if isinstance(value,float): raise ValidationError("Supply coordinates as decimal text.")
    try:
        result=Decimal(value)
        if not result.is_finite() or abs(result)>limit: raise ValueError()
        return int((result*1000000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,TypeError) as error:
        raise ValidationError("Invalid GPS coordinate.") from error


@transaction.atomic
def record_visit(*, customer, route, note, request_key, actor, consent=False, latitude=None, longitude=None):
    require_role(actor,["admin","salesman"])
    if type(consent) is not bool: raise ValidationError("Consent must be explicit.")
    if not request_key or not route.strip() or len(route)>100: raise ValidationError("Route and request key required.")
    if (latitude is not None or longitude is not None) and not consent:
        raise ValidationError("GPS capture requires explicit consent.")
    lat=coordinate(latitude,90) if latitude is not None else None
    lon=coordinate(longitude,180) if longitude is not None else None
    if (lat is None)!=(lon is None): raise ValidationError("Both GPS coordinates are required.")
    values=dict(customer=customer,route=route,note=note,actor=actor,gps_consent=consent,
                latitude_microdegrees=lat,longitude_microdegrees=lon)
    FactoryControl.objects.select_for_update().get(pk=1)
    old=Visit.objects.filter(request_key=request_key).first()
    if old:
        if any(getattr(old,key)!=value for key,value in values.items()): raise ValidationError("Visit retry conflicts.")
        return old
    visit=Visit.objects.create(request_key=request_key,**values)
    audit(actor,"visit.record",visit,{}, {"customer":customer.pk,"route":route,"gps_consent":consent})
    return visit


def visits_for(actor):
    require_role(actor,["admin","salesman","accountant","owner"])
    visits=Visit.objects.select_related("customer","actor").order_by("-visited_at")
    if not actor.is_staff and actor.groups.filter(name="salesman").exists(): visits=visits.filter(actor=actor)
    return visits


# Emit exact JSON number tokens for Decimal amounts, never converting through float.
def exact_json(value):
    if isinstance(value,Decimal):
        if not value.is_finite(): raise ValidationError("Non-finite JSON amount.")
        return format(value,'f')
    if isinstance(value,dict): return '{'+','.join(json.dumps(key)+':'+exact_json(item) for key,item in value.items())+'}'
    if isinstance(value,list): return '['+','.join(exact_json(item) for item in value)+']'
    if isinstance(value,float): raise ValidationError("Binary floats are not accepted in mock documents.")
    return json.dumps(value,ensure_ascii=False)


# The adapter produces exercise-only documents and deterministic MOCK references; no API is contacted.
@transaction.atomic
def create_mock_document(*, invoice, kind, actor, vehicle="TN00DEMO0000", distance_km=1):
    require_role(actor,["admin"])
    if kind not in ("e_invoice","e_waybill"): raise ValidationError("Choose a supported mock document.")
    require_integer(distance_km,1)
    if distance_km>10000 or not vehicle.strip(): raise ValidationError("Vehicle and reasonable distance required.")
    FactoryControl.objects.select_for_update().get(pk=1)
    invoice=Invoice.objects.get(pk=invoice.pk)
    if invoice.status!="posted": raise ValidationError("Only posted invoices can produce mock documents.")
    rupees=lambda paise: Decimal(paise)/100
    payload={"Version":"1.1","TxnDtls":{"TaxSch":"GST","SupTyp":"B2B" if invoice.customer_gstin else "B2C"},
        "DocDtls":{"Typ":"INV","No":invoice.number,"Dt":invoice.document_date.strftime('%d/%m/%Y')},
        "SellerDtls":{"Gstin":"33AAAAA0000A1Z0","LglNm":"Demo Snack Factory","Addr1":"Dummy factory address","Loc":"Chennai","Pin":600001,"Stcd":"33"},
        "BuyerDtls":{"Gstin":invoice.customer_gstin or "URP","LglNm":invoice.customer_name,"Pos":invoice.supply_state,"Addr1":"Dummy customer address","Loc":"Demo city","Pin":600001 if invoice.supply_state=="33" else 560001,"Stcd":invoice.supply_state},
        "ItemList":[{"SlNo":str(index),"PrdDesc":line.description,"IsServc":"N","HsnCd":line.hsn,"Qty":line.quantity,"Unit":"PCS",
            "UnitPrice":rupees(line.price_paise),"TotAmt":rupees(line.taxable_paise),"AssAmt":rupees(line.taxable_paise),"GstRt":5,
            "CgstAmt":rupees(line.cgst_paise),"SgstAmt":rupees(line.sgst_paise),"IgstAmt":rupees(line.igst_paise),
            "TotItemVal":rupees(line.taxable_paise+line.cgst_paise+line.sgst_paise+line.igst_paise)} for index,line in enumerate(invoice.lines.all(),1)],
        "ValDtls":{"AssVal":rupees(invoice.taxable_paise),"CgstVal":rupees(invoice.cgst_paise),"SgstVal":rupees(invoice.sgst_paise),"IgstVal":rupees(invoice.igst_paise),"TotInvVal":rupees(invoice.total_paise)}}
    if kind=="e_waybill": payload["EwbDtls"]={"TransMode":"1","Distance":distance_km,"VehNo":vehicle,"VehType":"R"}
    request_json=exact_json(payload)
    old=MockSubmission.objects.filter(invoice=invoice,kind=kind).first()
    if old:
        if old.request_json!=request_json: raise ValidationError("Mock document already exists with different inputs.")
        return old
    digest=hashlib.sha256(request_json.encode('utf-8')).hexdigest()
    response={"mock":True,"status":"ACCEPTED_BY_LOCAL_MOCK","reference":"MOCK-"+digest,
              "notice":"Fictional GSTIN, HSN and addresses. No government registration or transport authorization."}
    response["Irn" if kind=="e_invoice" else "EwbNo"]="MOCK-"+digest
    submission=MockSubmission.objects.create(invoice=invoice,kind=kind,actor=actor,request_json=request_json,response=response)
    audit(actor,"mock.create",submission,{}, {"kind":kind,"reference":response["reference"]})
    return submission
