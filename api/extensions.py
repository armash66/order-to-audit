"""Native customer pricing, reorder settings, consented visits and exercise-only mock exports."""

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy import select
from api import database
from api.native import (
    authorize,
    required_integer,
    factory_lock,
    table,
    insert_row,
    audit,
    now,
)
from api.sales.services import get_row, change, invoice_lines


def coordinate(value, limit):
    if isinstance(value, (float, bool)):
        raise ValueError("Supply coordinates as decimal text.")
    try:
        number = Decimal(value)
        if not number.is_finite() or abs(number) > limit:
            raise ValueError("Invalid GPS coordinate.")
        return int((number * 1000000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Invalid GPS coordinate.") from error


# Decimal number tokens are emitted directly, never through binary floating point.
def exact_json(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite JSON amount.")
        return format(value, "f")
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                json.dumps(key) + ":" + exact_json(item) for key, item in value.items()
            )
            + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(exact_json(item) for item in value) + "]"
    if isinstance(value, float):
        raise ValueError("Binary floats are not accepted in mock documents.")
    return json.dumps(value, ensure_ascii=False)


def visit(conn, data, user, key):
    customer = get_row(conn, "inventory_customer", data["customer"])
    consent = data.get("consent", False)
    if type(consent) is not bool:
        raise ValueError("Consent must be explicit.")
    route = data["route"]
    if not route.strip() or len(route) > 100:
        raise ValueError("Route of at most 100 characters required.")
    lat = data.get("latitude") or None
    lon = data.get("longitude") or None
    if (lat is not None or lon is not None) and not consent:
        raise ValueError("GPS capture requires explicit consent.")
    lat = coordinate(lat, 90) if lat is not None else None
    lon = coordinate(lon, 180) if lon is not None else None
    if (lat is None) != (lon is None):
        raise ValueError("Both GPS coordinates are required.")
    values = {
        "customer_id": customer["id"],
        "route": route,
        "note": data.get("note", ""),
        "actor_id": user["id"],
        "gps_consent": consent,
        "latitude_microdegrees": lat,
        "longitude_microdegrees": lon,
    }
    target = table(conn, "extensions_visit")
    old = (
        conn.execute(select(target).where(target.c.request_key == key))
        .mappings()
        .first()
    )
    if old:
        if any(old[field] != value for field, value in values.items()):
            raise ValueError("Visit retry conflicts.")
        return old["id"]
    identifier = insert_row(
        conn, "extensions_visit", request_key=key, visited_at=now(), **values
    )
    audit(
        conn,
        user,
        "visit.record",
        "extensions.Visit",
        identifier,
        {},
        {"customer": customer["id"], "route": route, "gps_consent": consent},
    )
    return identifier


# Fictional snapshots produce deterministic MOCK identifiers; no government endpoint is contacted.
def mock(conn, data, user):
    invoice = get_row(conn, "sales_invoice", data["invoice"])
    kind = data["kind"]
    if kind not in ("e_invoice", "e_waybill"):
        raise ValueError("Choose a supported mock document.")
    distance = required_integer(data.get("distance", "1"), 1)
    vehicle = data.get("vehicle", "TN00DEMO0000")
    if distance > 10000 or not vehicle.strip():
        raise ValueError("Vehicle and reasonable distance required.")
    if invoice["status"] != "posted":
        raise ValueError("Only posted invoices can produce mock documents.")
    rupees = lambda value: Decimal(value) / 100
    items = []
    for index, line in enumerate(invoice_lines(conn, invoice["id"]), 1):
        items.append(
            {
                "SlNo": str(index),
                "PrdDesc": line["description"],
                "IsServc": "N",
                "HsnCd": line["hsn"],
                "Qty": line["quantity"],
                "Unit": "PCS",
                "UnitPrice": rupees(line["price_paise"]),
                "TotAmt": rupees(line["taxable_paise"]),
                "AssAmt": rupees(line["taxable_paise"]),
                "GstRt": 5,
                "CgstAmt": rupees(line["cgst_paise"]),
                "SgstAmt": rupees(line["sgst_paise"]),
                "IgstAmt": rupees(line["igst_paise"]),
                "TotItemVal": rupees(
                    sum(
                        line[field]
                        for field in (
                            "taxable_paise",
                            "cgst_paise",
                            "sgst_paise",
                            "igst_paise",
                        )
                    )
                ),
            }
        )
    payload = {
        "Version": "1.1",
        "TxnDtls": {
            "TaxSch": "GST",
            "SupTyp": "B2B" if invoice["customer_gstin"] else "B2C",
        },
        "DocDtls": {
            "Typ": "INV",
            "No": invoice["number"],
            "Dt": invoice["document_date"].strftime("%d/%m/%Y"),
        },
        "SellerDtls": {
            "Gstin": "33AAAAA0000A1Z0",
            "LglNm": "Demo Snack Factory",
            "Addr1": "Dummy factory address",
            "Loc": "Chennai",
            "Pin": 600001,
            "Stcd": "33",
        },
        "BuyerDtls": {
            "Gstin": invoice["customer_gstin"] or "URP",
            "LglNm": invoice["customer_name"],
            "Pos": invoice["supply_state"],
            "Addr1": "Dummy customer address",
            "Loc": "Demo city",
            "Pin": 600001 if invoice["supply_state"] == "33" else 560001,
            "Stcd": invoice["supply_state"],
        },
        "ItemList": items,
        "ValDtls": {
            label: rupees(invoice[field])
            for label, field in [
                ("AssVal", "taxable_paise"),
                ("CgstVal", "cgst_paise"),
                ("SgstVal", "sgst_paise"),
                ("IgstVal", "igst_paise"),
                ("TotInvVal", "total_paise"),
            ]
        },
    }
    if kind == "e_waybill":
        payload["EwbDtls"] = {
            "TransMode": "1",
            "Distance": distance,
            "VehNo": vehicle,
            "VehType": "R",
        }
    request = exact_json(payload)
    target = table(conn, "extensions_mocksubmission")
    old = (
        conn.execute(
            select(target).where(
                target.c.invoice_id == invoice["id"], target.c.kind == kind
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_json"] != request:
            raise ValueError("Mock document already exists with different inputs.")
        return {"mock": True, "request_json": request, "response": old["response"]}
    reference = "MOCK-" + hashlib.sha256(request.encode("utf-8")).hexdigest()
    response = {
        "mock": True,
        "status": "ACCEPTED_BY_LOCAL_MOCK",
        "reference": reference,
        "notice": "Fictional GSTIN, HSN and addresses. No government registration or transport authorization.",
        "Irn" if kind == "e_invoice" else "EwbNo": reference,
    }
    identifier = insert_row(
        conn,
        "extensions_mocksubmission",
        invoice_id=invoice["id"],
        kind=kind,
        actor_id=user["id"],
        created_at=now(),
        request_json=request,
        response=response,
    )
    audit(
        conn,
        user,
        "mock.create",
        "extensions.MockSubmission",
        identifier,
        {},
        {"kind": kind, "reference": reference},
    )
    return {"mock": True, "request_json": request, "response": response}


def command(action, data, user, key):
    authorize(user, ["admin", "salesman"] if action == "visit" else ["admin"])
    if not key:
        raise ValueError("Request key required.")
    with database.transaction() as conn:
        factory_lock(conn)
        if action == "visit":
            return visit(conn, data, user, key)
        if action == "mock":
            return mock(conn, data, user)
        if action == "price":
            customer = get_row(conn, "inventory_customer", data["customer"])
            sku = get_row(conn, "inventory_sku", data["sku"])
            values = {
                "price_paise": required_integer(data["price_paise"], 0),
                "label": data["label"],
            }
            if not values["label"].strip():
                raise ValueError("Price or scheme description required.")
            name = "sales_customerprice"
            source = "sales.CustomerPrice"
            target = table(conn, name)
            match = {"customer_id": customer["id"], "sku_id": sku["id"]}
            old = (
                conn.execute(
                    select(target).where(
                        target.c.customer_id == customer["id"],
                        target.c.sku_id == sku["id"],
                    )
                )
                .mappings()
                .first()
            )
            before = {field: old[field] for field in values} if old else {}
            after = values
            event = "price.edit"
        elif action == "reorder":
            item = get_row(conn, "inventory_item", data["item"])
            if item["category"] != "raw":
                raise ValueError("Reorder alerts are for raw materials.")
            values = {"minimum_quantity": required_integer(data["minimum"], 0)}
            name = "inventory_reorderlevel"
            source = "inventory.ReorderLevel"
            target = table(conn, name)
            match = {"item_id": item["id"]}
            old = (
                conn.execute(select(target).where(target.c.item_id == item["id"]))
                .mappings()
                .first()
            )
            before = {"minimum": old["minimum_quantity"]} if old else {}
            after = {"minimum": values["minimum_quantity"]}
            event = "reorder.edit"
        else:
            raise ValueError("Unknown extension action.")
        if old:
            identifier = old["id"]
            change(conn, name, identifier, **values)
        else:
            identifier = insert_row(conn, name, **match, **values)
        audit(conn, user, event, source, identifier, before, after)
        return identifier
