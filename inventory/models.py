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


class Recipe(models.Model):
    code = models.CharField(max_length=40)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="unique_recipe_version")]


class RecipeLine(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recipe", "item"], name="unique_recipe_item"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="positive_recipe_quantity"),
        ]


class BOM(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT)

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
    tolerance_bps = models.PositiveIntegerField(default=300)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="single_factory")]


class Source(models.Model):
    request_key = models.CharField(max_length=100, unique=True)
    document_date = models.DateField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class OpeningStock(Source):
    lot_details = models.JSONField(default=dict)


class PurchaseReceipt(Source):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    lot_details = models.JSONField(default=dict)


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


class Adjustment(Source):
    reason = models.TextField()
    reversed_run = models.OneToOneField("production.ProductionRun", null=True, on_delete=models.PROTECT)
    payload = models.JSONField()


class AdjustmentLine(SourceLine):
    quantity = models.BigIntegerField()
    value_paise = models.BigIntegerField(null=True)
    document = models.ForeignKey(Adjustment, related_name="lines", on_delete=models.PROTECT)


# Exactly one typed foreign key makes each ledger source structurally traceable.
def one_source(names):
    condition = Q()
    for selected in names:
        condition |= Q(**{name+"__isnull": name != selected for name in names})
    return condition


class Posting(models.Model):
    adjustment = models.OneToOneField(Adjustment, null=True, on_delete=models.PROTECT)
    dispatch = models.OneToOneField("sales.Dispatch", null=True, on_delete=models.PROTECT)
    production = models.OneToOneField("production.ProductionEvent", null=True, on_delete=models.PROTECT)
    sequence = models.PositiveBigIntegerField(unique=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    opening = models.OneToOneField(OpeningStock, null=True, on_delete=models.PROTECT)
    purchase = models.OneToOneField(PurchaseReceipt, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=one_source(["opening","purchase","production","dispatch","adjustment"]), name="posting_one_source")]


class StockMovement(models.Model):
    adjustment_line = models.OneToOneField(AdjustmentLine, null=True, on_delete=models.PROTECT)
    dispatch_line = models.OneToOneField("sales.DispatchLine", null=True, on_delete=models.PROTECT)
    production_line = models.OneToOneField("production.ProductionLine", null=True, on_delete=models.PROTECT)
    posting = models.ForeignKey(Posting, on_delete=models.PROTECT, related_name="movements")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.BigIntegerField()
    value_paise = models.BigIntegerField(null=True)
    opening_line = models.OneToOneField(OpeningLine, null=True, on_delete=models.PROTECT)
    purchase_line = models.OneToOneField(PurchaseLine, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name="nonzero_movement"),
            models.CheckConstraint(condition=one_source(["opening_line","purchase_line","production_line","dispatch_line","adjustment_line"]), name="movement_one_source_line"),
        ]


class StockLot(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    code = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item","code"],name="unique_item_lot")]


class LotAllocation(models.Model):
    movement = models.ForeignKey(StockMovement,related_name="allocations",on_delete=models.PROTECT)
    lot = models.ForeignKey(StockLot,related_name="allocations",on_delete=models.PROTECT)
    quantity = models.BigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["movement","lot"],name="unique_movement_lot"),
                       models.CheckConstraint(condition=~Q(quantity=0),name="nonzero_lot_quantity")]


class ReorderLevel(models.Model):
    item = models.OneToOneField(Item,on_delete=models.PROTECT)
    minimum_quantity = models.PositiveBigIntegerField()
