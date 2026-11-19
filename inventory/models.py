from django.conf import settings
from django.db import models
from django.db.models import Q


class Item(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=12, choices=[(x, x) for x in ("raw", "packaging", "finished")])
    base_unit = models.CharField(max_length=8, choices=[(x, x) for x in ("g", "ml", "piece")])


class UnitConversion(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    unit = models.CharField(max_length=16)
    numerator = models.PositiveIntegerField()
    denominator = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "unit"], name="unique_item_unit"),
            models.CheckConstraint(condition=Q(numerator__gt=0, denominator__gt=0), name="positive_conversion"),
        ]


class SKU(models.Model):
    item = models.OneToOneField(Item, on_delete=models.PROTECT)
    pack_size_g = models.PositiveIntegerField()
    price_paise = models.PositiveBigIntegerField()
    hsn = models.CharField(max_length=8)


class Supplier(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)


class Customer(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    state_code = models.CharField(max_length=2)
    gstin = models.CharField(max_length=15)


class BOM(models.Model):
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    expected_packets = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["sku", "version"], name="unique_bom_version")]


class BOMLine(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["bom", "item"], name="unique_bom_item")]


class FactoryControl(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    last_sequence = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="single_factory")]


class Source(models.Model):
    request_key = models.CharField(max_length=100, unique=True)
    document_date = models.DateField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class OpeningStock(Source):
    pass


class PurchaseReceipt(Source):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)


class SourceLine(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveBigIntegerField()
    value_paise = models.PositiveBigIntegerField(null=True)

    class Meta:
        abstract = True


class OpeningLine(SourceLine):
    document = models.ForeignKey(OpeningStock, on_delete=models.PROTECT, related_name="lines")

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="opening_positive_quantity")]


class PurchaseLine(SourceLine):
    document = models.ForeignKey(PurchaseReceipt, on_delete=models.PROTECT, related_name="lines")

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0, value_paise__isnull=False), name="purchase_quantity_value")]


class Posting(models.Model):
    sequence = models.PositiveBigIntegerField(unique=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    opening = models.OneToOneField(OpeningStock, null=True, on_delete=models.PROTECT)
    purchase = models.OneToOneField(PurchaseReceipt, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(opening__isnull=False, purchase__isnull=True) | Q(opening__isnull=True, purchase__isnull=False)), name="posting_one_source")]


class StockMovement(models.Model):
    posting = models.ForeignKey(Posting, on_delete=models.PROTECT, related_name="movements")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.BigIntegerField()
    value_paise = models.BigIntegerField(null=True)
    opening_line = models.OneToOneField(OpeningLine, null=True, on_delete=models.PROTECT)
    purchase_line = models.OneToOneField(PurchaseLine, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name="nonzero_movement"),
            models.CheckConstraint(condition=(Q(opening_line__isnull=False, purchase_line__isnull=True) | Q(opening_line__isnull=True, purchase_line__isnull=False)), name="movement_one_source_line"),
        ]
