from django.db import models
from inventory.models import Source, Customer, SKU, Item


class Order(Source):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, default="submitted")
    rejection_reason = models.TextField(blank=True)
    submitted_payload = models.JSONField()


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.PROTECT)
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    quantity = models.PositiveBigIntegerField()
    price_paise = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "sku"], name="unique_order_sku")]


class Invoice(Source):
    order = models.OneToOneField(Order, related_name="invoice", on_delete=models.PROTECT)
    number = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=12, default="posted")
    customer_name = models.CharField(max_length=120)
    customer_gstin = models.CharField(max_length=15)
    supply_state = models.CharField(max_length=2)
    taxable_paise = models.PositiveBigIntegerField()
    cgst_paise = models.PositiveBigIntegerField()
    sgst_paise = models.PositiveBigIntegerField()
    igst_paise = models.PositiveBigIntegerField()
    total_paise = models.PositiveBigIntegerField()


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.PROTECT)
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    description = models.CharField(max_length=120)
    hsn = models.CharField(max_length=8)
    quantity = models.PositiveBigIntegerField()
    price_paise = models.PositiveBigIntegerField()
    taxable_paise = models.PositiveBigIntegerField()
    cgst_paise = models.PositiveBigIntegerField()
    sgst_paise = models.PositiveBigIntegerField()
    igst_paise = models.PositiveBigIntegerField()


class InvoiceSequence(models.Model):
    financial_year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)


class Dispatch(Source):
    invoice = models.OneToOneField(Invoice, related_name="dispatch", on_delete=models.PROTECT)


class DispatchLine(models.Model):
    document = models.ForeignKey(Dispatch, related_name="lines", on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.BigIntegerField()
    value_paise = models.BigIntegerField(null=True)


class Payment(Source):
    invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.PROTECT)
    amount_paise = models.PositiveBigIntegerField()


class CreditNote(Source):
    invoice = models.OneToOneField(Invoice, related_name="credit_note", on_delete=models.PROTECT)
    reason = models.TextField()
    amount_paise = models.PositiveBigIntegerField()
