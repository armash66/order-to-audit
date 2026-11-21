"""PDF rendering from frozen SQLAlchemy snapshots; no Django template dependency."""

from html import escape
from fractions import Fraction
from weasyprint import HTML
from fastapi import HTTPException
from api import database
from api.native import authorize, factory_lock, round_paise
from api.sales.services import get_row, invoice_lines


def money(paise):
    value = round_paise(Fraction(paise))
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 100)
    return f"{sign}{whole:,}.{fraction:02d}"


# All source text is escaped before interpolation; rendering never resolves user-provided URLs.
def table_html(headers, rows):
    head = "".join(f"<th>{escape(str(value))}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(title, content, landscape=False):
    css = (
        "@page{size:A4 "
        + ("landscape" if landscape else "portrait")
        + ";margin:16mm}body{font:11px 'DejaVu Sans';color:#18263b}h1{font-size:21px}table{width:100%;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #ddd;text-align:left}thead{display:table-header-group}tr{break-inside:avoid}"
    )
    html = f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><h1>{escape(title)}</h1>{content}</body></html>'
    return HTML(string=html).write_pdf()


def table_pdf(report):
    return render(
        report["title"],
        f"<p>{escape(str(report['start']))} to {escape(str(report['end']))}</p>"
        + table_html(report["headers"], report["rows"]),
        landscape=True,
    )


# Permission scope is checked before copying the immutable invoice snapshot for rendering.
def invoice_pdf(identifier, user):
    authorize(user, ["admin", "salesman", "accountant", "owner"])
    with database.transaction() as conn:
        factory_lock(conn)
        invoice = get_row(conn, "sales_invoice", identifier)
        order = get_row(conn, "sales_order", invoice["order_id"])
        if (
            not user["is_staff"]
            and "salesman" in user["roles"]
            and order["actor_id"] != user["id"]
        ):
            raise HTTPException(403, "You can only access your own orders.")
        if invoice["status"] == "draft":
            raise ValueError("Post the invoice before exporting it.")
        lines = invoice_lines(conn, identifier)
    rows = [
        [
            line["description"],
            line["hsn"],
            line["quantity"],
            *[
                money(line[field])
                for field in (
                    "price_paise",
                    "taxable_paise",
                    "cgst_paise",
                    "sgst_paise",
                    "igst_paise",
                )
            ],
        ]
        for line in lines
    ]
    content = "<p>Demo Snack Factory · Tamil Nadu (33)<br>Supplier GSTIN: 33AAAAA0000A1Z0 (dummy identity)</p>"
    content += (
        f"<p>Date: {invoice['document_date']} · Status: {escape(invoice['status'])}</p>"
    )
    content += f"<h2>{escape(invoice['customer_name'])}</h2><p>GSTIN: {escape(invoice['customer_gstin'] or 'Unregistered')}<br>Place of supply: {escape(invoice['supply_state'])}</p>"
    content += table_html(
        ["Product", "HSN", "Qty", "Rate ₹", "Taxable ₹", "CGST ₹", "SGST ₹", "IGST ₹"],
        rows,
    )
    content += "<p>GST: 5% (intrastate 2.5% CGST + 2.5% SGST; interstate 5% IGST).</p>"
    content += (
        "<p>"
        + " · ".join(
            f"{label} ₹{money(invoice[field])}"
            for label, field in [
                ("Taxable", "taxable_paise"),
                ("CGST", "cgst_paise"),
                ("SGST", "sgst_paise"),
                ("IGST", "igst_paise"),
            ]
        )
        + "</p>"
    )
    content += f"<h2>Total ₹{money(invoice['total_paise'])}</h2><p>Internship demonstration. All identities and HSN data are fictional.</p>"
    return render("Tax invoice " + invoice["number"], content)
