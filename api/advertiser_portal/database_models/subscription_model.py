"""Subscription models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class SubscriptionPlan(AdvertiserPortalBaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ['monthly_price']
    def __str__(self):
        return self.name


class Subscription(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='active', db_index=True)
    started_at = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-started_at']
    def __str__(self):
        return f"{self.advertiser_id} — {self.plan.name}"


class SubscriptionUsage(AdvertiserPortalBaseModel):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usage_records')
    period_start = models.DateField()
    spend_used = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    class Meta:
        unique_together = [['subscription', 'period_start']]
    def __str__(self):
        return f"Usage {self.subscription_id} {self.period_start}"


class SubscriptionInvoice(AdvertiserPortalBaseModel):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='open')
    due_date = models.DateField()
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"SubInvoice {self.invoice_number}"
