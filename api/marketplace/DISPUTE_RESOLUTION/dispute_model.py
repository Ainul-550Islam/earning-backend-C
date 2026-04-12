"""
DISPUTE_RESOLUTION/dispute_model.py — Full Dispute Domain Models
=================================================================
Entities:
  Dispute          — main dispute record (Buyer vs Seller)
  DisputeMessage   — conversation thread
  DisputeEvidence  — files/images submitted by either party
  DisputeArbitration — admin's verdict record

State machine:
  OPEN → UNDER_REVIEW → ESCALATED → RESOLVED_BUYER | RESOLVED_SELLER
  OPEN → CLOSED (seller refunds voluntarily)
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from api.marketplace.models import Order, OrderItem, RefundRequest
from api.marketplace.enums import DisputeStatus, DisputeType
from api.tenants.models import Tenant


class Dispute(models.Model):
    tenant      = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                    related_name="marketplace_disputes_tenant")
    order       = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="disputes")
    order_item  = models.ForeignKey(OrderItem, on_delete=models.CASCADE,
                                    related_name="disputes", null=True, blank=True)
    raised_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="marketplace_disputes_raised")
    against_seller = models.ForeignKey("marketplace.SellerProfile", on_delete=models.SET_NULL,
                                       null=True, related_name="disputes_against")

    dispute_type  = models.CharField(max_length=30, choices=DisputeType.choices)
    description   = models.TextField(default='')
    status        = models.CharField(max_length=25, choices=DisputeStatus.choices,
                                     default=DisputeStatus.OPEN, db_index=True)

    # Resolution
    resolution_note = models.TextField(blank=True)
    resolved_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name="marketplace_disputes_resolved")
    resolved_at     = models.DateTimeField(null=True, blank=True)

    # Linked refund (created only after arbitration)
    refund_request  = models.OneToOneField(RefundRequest, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name="dispute")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label  = "marketplace"
        db_table   = "marketplace_dispute"
        ordering   = ["-created_at"]
        indexes    = [models.Index(fields=["order", "status"])]

    def __str__(self):
        return f"Dispute#{self.pk} | {self.order.order_number} | {self.status}"


class DisputeMessage(models.Model):
    """Threaded conversation between buyer, seller, and admin."""
    tenant   = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                  related_name="marketplace_dispute_messages_tenant")
    dispute  = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="messages")
    sender   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="marketplace_dispute_messages")
    role     = models.CharField(max_length=10,
                                choices=[("buyer","Buyer"),("seller","Seller"),("admin","Admin")])
    body     = models.TextField(default='')
    is_internal = models.BooleanField(default=False, help_text="Admin-only note")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_dispute_message"
        ordering  = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.body[:60]}"


class DisputeEvidence(models.Model):
    """File evidence (photos, invoices) submitted by buyer or seller."""
    tenant   = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                  related_name="marketplace_dispute_evidence_tenant")
    dispute  = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="evidences")
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role     = models.CharField(max_length=10, choices=[("buyer","Buyer"),("seller","Seller")])
    file     = models.FileField(upload_to="marketplace/disputes/evidence/")
    caption  = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_dispute_evidence"


class DisputeArbitration(models.Model):
    """Admin verdict record. RefundRequest is created ONLY when verdict = buyer_wins."""
    tenant   = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True,
                                  related_name="marketplace_dispute_arbitration_tenant")
    dispute  = models.OneToOneField(Dispute, on_delete=models.CASCADE, related_name="arbitration")
    admin    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, related_name="marketplace_arbitrations")
    verdict  = models.CharField(
        max_length=20,
        choices=[
            ("buyer_wins",  "Buyer Wins — Full Refund"),
            ("seller_wins", "Seller Wins — Release Escrow"),
            ("partial",     "Partial Refund"),
        ]
    )
    refund_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100,
                                         help_text="Used for partial verdict (0-100)")
    reason   = models.TextField(default='')
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_dispute_arbitration"

    def __str__(self):
        return f"Arbitration for Dispute#{self.dispute_id} → {self.verdict}"
