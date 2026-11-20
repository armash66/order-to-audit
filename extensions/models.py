from django.conf import settings
from django.db import models
from inventory.models import Customer
from sales.models import Invoice


class Visit(models.Model):
    request_key = models.CharField(max_length=100,unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer,on_delete=models.PROTECT)
    route = models.CharField(max_length=100)
    note = models.TextField(blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)
    gps_consent = models.BooleanField(default=False)
    latitude_microdegrees = models.IntegerField(null=True)
    longitude_microdegrees = models.IntegerField(null=True)


class MockSubmission(models.Model):
    invoice = models.ForeignKey(Invoice,on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    request_json = models.TextField()
    response = models.JSONField()

    class Meta:
        constraints=[models.UniqueConstraint(fields=["invoice","kind"],name="unique_invoice_mock")]
