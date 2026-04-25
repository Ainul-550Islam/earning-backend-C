# api/publisher_tools/payment_settlement/dispute_resolution.py
"""Dispute Resolution — Invoice and payment dispute handling."""
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class PaymentDispute(TimeStampedModel):
    """Payment or invoice dispute record।"""
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="publisher_tools_dispute_tenant", db_index=True)
    DISPUTE_TYPES = [
        ("invoice_amount","Invoice Amount Incorrect"),("payment_not_received","Payment Not Received"),
        ("ivt_deduction","IVT Deduction Dispute"),("missing_earnings","Missing Earnings"),
        ("bank_details","Wrong Bank Details"),("other","Other"),
    ]
    STATUS_CHOICES = [
        ("open","Open"),("under_review","Under Review"),("resolved","Resolved"),
        ("rejected","Rejected"),("escalated","Escalated"),
    ]
    publisher        = models.ForeignKey("publisher_tools.Publisher", on_delete=models.CASCADE, related_name="disputes", db_index=True)
    invoice          = models.ForeignKey("publisher_tools.PublisherInvoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="disputes")
    dispute_type     = models.CharField(max_length=30, choices=DISPUTE_TYPES, default="invoice_amount")
    title            = models.CharField(max_length=300)
    description      = models.TextField()
    disputed_amount  = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    evidence_urls    = models.JSONField(default=list, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    assigned_to      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    resolution       = models.TextField(blank=True)
    resolution_amount= models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    priority         = models.CharField(max_length=10, choices=[("low","Low"),("medium","Medium"),("high","High")], default="medium")
    sla_deadline     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "publisher_tools_payment_disputes"
        verbose_name = _("Payment Dispute")
        verbose_name_plural = _("Payment Disputes")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publisher", "status"], name='idx_publisher_status_1597'),
            models.Index(fields=["status", "sla_deadline"], name='idx_status_sla_deadline_1598'),
        ]

    def __str__(self):
        return f"Dispute: {self.publisher.publisher_id} — {self.dispute_type} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.sla_deadline:
            from datetime import timedelta
            days = {"high": 2, "medium": 5, "low": 10}.get(self.priority, 5)
            self.sla_deadline = timezone.now() + timedelta(days=days)
        super().save(*args, **kwargs)

    @transaction.atomic
    def resolve(self, resolution: str, amount=None, resolved_by=None):
        self.status = "resolved"
        self.resolution = resolution
        self.resolution_amount = amount
        self.resolved_at = timezone.now()
        self.assigned_to = resolved_by
        self.save()
        return self

    @property
    def is_overdue(self):
        return bool(self.sla_deadline and timezone.now() > self.sla_deadline and self.status in ("open","under_review"))

    @property
    def age_days(self):
        return (timezone.now() - self.created_at).days
