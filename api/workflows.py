"""FastAPI transport for native SQLAlchemy services and exact workspace responses."""

import json
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from functools import wraps
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from api import reporting as reports
from api.native import now, required_integer
from .main import current_user
from . import queries

router = APIRouter(prefix="/api/workspace")


@router.get("/translations")
def translations(user=Depends(current_user)):
    return json.loads(
        (Path(__file__).resolve().parent.parent / "frontend/src/translations.json").read_text(encoding="utf-8")
    )


# All exact numeric business values cross JSON as strings; identifiers remain strings too.
def wire(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Fraction):
        return {
            "numerator": str(value.numerator),
            "denominator": str(value.denominator),
        }
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    raise TypeError(f"Unsupported response type: {type(value).__name__}")


# Services own transactions; the transport normalizes invalid business inputs.
def domain(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, KeyError, TypeError) as error:
            raise HTTPException(400, str(error))
        except IntegrityError:
            raise HTTPException(409, "Record conflicts with an existing entry.")

    return wrapped


def integer(value):
    return required_integer(value)


@router.post("/offline/sync")
@domain
def offline_sync(payload: dict, user=Depends(current_user)):
    from api.sales.services import command as sales_command

    if integer(payload["user_id"]) != user["id"]:
        raise HTTPException(403, "Sign in as the user who captured this order.")
    return {
        "id": str(sales_command("order.create", payload, user, payload["request_key"]))
    }


@router.get("/catalog")
@domain
def catalog(user=Depends(current_user)):
    return wire({**queries.read("catalog", user), "reports": reports.REPORTS})


@router.get("/accounts")
@domain
def accounts(user=Depends(current_user)):
    from api.accounts.services import accounts as list_accounts
    return wire(list_accounts(user))


@router.get("/dashboard")
@domain
def dashboard(user=Depends(current_user)):
    return wire(reports.dashboard(user, now().date()))


@router.get("/orders")
@domain
def orders(user=Depends(current_user)):
    return wire(queries.read("orders", user))


@router.get("/orders/{pk}")
@domain
def order(pk: int, user=Depends(current_user)):
    return wire(queries.order_detail(pk, user))


@router.get("/production")
@domain
def runs(user=Depends(current_user)):
    return wire(queries.read("runs", user))


@router.get("/receipts")
@domain
def receipts(user=Depends(current_user)):
    return wire(queries.read("receipts", user))


@router.get("/production/{pk}")
@domain
def run(pk: int, user=Depends(current_user)):
    return wire(queries.read("run", user, pk))


@router.get("/batches")
@domain
def batches(user=Depends(current_user)):
    return wire(queries.read("batches", user))


@router.get("/recall/{lot_id}")
@domain
def recall(lot_id: int, user=Depends(current_user)):
    return wire(queries.recall(lot_id, user))


@router.get("/visits")
@domain
def visits(user=Depends(current_user)):
    return wire(queries.read("visits", user))


@router.get("/prices/{customer_id}")
@domain
def prices(customer_id: int, user=Depends(current_user)):
    return wire(queries.read("prices", user, customer_id))


@router.get("/reports/{kind}")
@domain
def report(
    kind: str, start: date, end: date, format: str = "json", user=Depends(current_user)
):
    if kind == "tally":
        return Response(
            reports.tally_export(start, end, user),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="tally-demo.zip"'},
        )
    table = reports.report_table(kind, start, end, user)
    if format == "csv":
        return Response(
            reports.csv_bytes(table),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
        )
    if format == "pdf":
        from api.pdf import table_pdf

        return Response(
            table_pdf(table),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{kind}.pdf"'},
        )
    return wire(table)


@router.get("/invoices/{pk}/pdf")
@domain
def invoice_pdf(pk: int, user=Depends(current_user)):
    from api.pdf import invoice_pdf as render_pdf

    return Response(
        render_pdf(pk, user),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{pk}.pdf"'},
    )


@router.get("/sources/{pk}")
@domain
def source(pk: int, user=Depends(current_user)):
    return wire(queries.read("source", user, pk))


@router.get("/audit")
@domain
def audit_history(user=Depends(current_user)):
    return wire(queries.read("audit", user))


class Command(BaseModel):
    action: str
    request_key: str = Field(min_length=1, max_length=100)
    data: dict


# Commands call existing atomic services; no transport route writes stock or balances directly.
@router.post("/commands")
@domain
def command(body: Command, user=Depends(current_user)):
    d = body.data
    action = body.action
    key = body.request_key
    day = date.fromisoformat(d.get("date") or str(now().date()))
    if action.startswith("order."):
        from api.sales.services import command as sales_command

        return {
            "ok": True,
            "id": str(sales_command(action, {**d, "date": str(day)}, user, key)),
        }
    if action in ("adjustment", "production.reverse"):
        from api.inventory.corrections import command as correction_command

        return {
            "ok": True,
            "id": str(correction_command(action, {**d, "date": str(day)}, user, key)),
        }
    if action == "receipt":
        from api.inventory.services import post_receipt

        return {"ok": True, "id": str(post_receipt({**d, "date": str(day)}, user, key))}
    if action in (
        "production.create",
        "production.issue",
        "production.complete",
        "production.overhead",
        "production.edit",
        "tolerance",
    ):
        from api.production import services as native_production

        values = {**d, "date": str(day)}
        if action == "production.create":
            identifier = native_production.create_run(values, user, key)
        elif action in ("production.issue", "production.complete"):
            identifier = native_production.post_event(
                action.split(".")[1], values, user, key
            )
        elif action == "production.overhead":
            identifier = native_production.add_overhead(values, user, key)
        elif action == "production.edit":
            identifier = native_production.edit_run(values, user)
        else:
            identifier = native_production.set_tolerance(values, user)
        return {"ok": True, "id": str(identifier)}
    if action in ("reorder", "price", "visit", "mock"):
        from api.extensions import command as extension_command

        result = extension_command(action, d, user, key)
        return result if action == "mock" else {"ok": True, "id": str(result)}
    if action in ("quality", "run.loss_note", "collection.followup"):
        from api import factory_actions

        service = {"quality": factory_actions.quality,
                   "run.loss_note": factory_actions.loss_note,
                   "collection.followup": factory_actions.followup}[action]
        identifier = service(d, user) if action == "quality" else service(d, user, key)
        return {"ok": True, "id": str(identifier)}
    if action in ("account.create", "account.active", "account.reset"):
        from api.accounts import services as account_services
        service = {"account.create": account_services.create,
                   "account.active": account_services.set_active,
                   "account.reset": account_services.reset}[action]
        return {"ok": True, "id": str(service(d, user))}
    if action in ("master.item", "master.customer", "master.supplier", "master.product", "master.bom"):
        from api.masters import services as master_services
        service = {"master.item": master_services.item,
                   "master.customer": master_services.customer,
                   "master.supplier": master_services.supplier,
                   "master.product": master_services.product,
                   "master.bom": master_services.bom}[action]
        return {"ok": True, "id": str(service(d, user))}
    raise ValueError("Unknown action.")
