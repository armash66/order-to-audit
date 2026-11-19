from django.conf import settings
from django.utils import timezone
from django.db import models
from django.db.models import Q
from inventory.models import BOM, Item, Source


class ProductionRun(Source):
    bom = models.ForeignKey(BOM, on_delete=models.PROTECT)
    bom_version = models.PositiveIntegerField()
    recipe_version = models.PositiveIntegerField()
    batches = models.PositiveIntegerField()
    expected_packets = models.PositiveIntegerField()
    output_item = models.ForeignKey(Item, on_delete=models.PROTECT)
    state = models.CharField(max_length=12, default="draft", choices=[(s, s) for s in ("draft", "issued", "completed")])
    good_packets = models.PositiveIntegerField(null=True)


class RunStandard(models.Model):
    run = models.ForeignKey(ProductionRun, related_name="standards", on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    stage = models.CharField(max_length=12, choices=[("raw", "raw"), ("packaging", "packaging")])
    quantity = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "item"], name="unique_run_standard")]


class ProductionEvent(Source):
    run = models.ForeignKey(ProductionRun, related_name="events", on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=[("issue", "issue"), ("complete", "complete")])
    payload = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "kind"], name="unique_run_event")]


class ProductionLine(models.Model):
    event = models.ForeignKey(ProductionEvent, related_name="lines", on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.BigIntegerField()
    value_paise = models.BigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "item"], name="unique_event_item")]


class Overhead(Source):
    posted_at = models.DateTimeField(default=timezone.now, editable=False)
    run = models.ForeignKey(ProductionRun, related_name="overheads", on_delete=models.PROTECT)
    label = models.CharField(max_length=100)
    amount_paise = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount_paise__gt=0), name="positive_overhead")]


class ToleranceChange(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    before_bps = models.PositiveIntegerField()
    after_bps = models.PositiveIntegerField()
    changed_at = models.DateTimeField(auto_now_add=True)
