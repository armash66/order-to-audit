from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from weasyprint import HTML
from sales.services import order_for_actor


# Render only frozen invoice snapshots after checking the requesting user's scope.
def invoice_pdf(invoice, actor):
    order_for_actor(invoice.order, actor)
    if invoice.status == "draft":
        raise ValidationError("Post the invoice before exporting it.")
    html = render_to_string("invoice_pdf.html", {"invoice": invoice})
    return HTML(string=html).write_pdf()


# Cached catalogs are advisory; the server prices orders and verifies the original user.
def sync_offline_order(payload, actor):
    from datetime import date
    from django.core.exceptions import PermissionDenied
    from access.services import require_role
    from inventory.models import Customer
    from sales.services import submit_order
    require_role(actor,["admin","salesman"])
    if payload.get("user_id") != actor.pk:
        raise PermissionDenied("Sign in as the user who captured this order.")
    try:
        quantities={int(key):value for key,value in payload["quantities"].items()}
        customer=Customer.objects.get(pk=payload["customer"])
        day=date.fromisoformat(payload["date"])
        key=payload["request_key"]
    except (KeyError,TypeError,ValueError,Customer.DoesNotExist) as error:
        raise ValidationError("Invalid offline order.") from error
    return submit_order(customer=customer,quantities=quantities,request_key=key,document_date=day,actor=actor)
