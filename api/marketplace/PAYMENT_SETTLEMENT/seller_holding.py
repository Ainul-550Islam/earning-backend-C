"""
PAYMENT_SETTLEMENT/seller_holding.py — Seller Balance Holding & Ledger
"""
from decimal import Decimal
from django.db import models
from django.conf import settings


class SellerLedger(models.Model):
    """Double-entry style ledger for seller earnings."""
    ENTRY_TYPES = [
        ("credit","Credit — Earnings"),
        ("debit", "Debit — Payout/Fee"),
        ("hold",  "Hold — Escrow"),
        ("release","Release — From Escrow"),
    ]
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="seller_ledger_tenant")
    seller      = models.ForeignKey("marketplace.SellerProfile", on_delete=models.CASCADE,
                                     related_name="ledger_entries")
    entry_type  = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference   = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_seller_ledger"
        ordering  = ["-created_at"]


def get_seller_balance(seller) -> dict:
    from api.marketplace.models import EscrowHolding, SellerPayout
    from api.marketplace.enums import EscrowStatus, PayoutStatus
    from django.db.models import Sum

    escrow_holding = EscrowHolding.objects.filter(
        seller=seller, status=EscrowStatus.HOLDING
    ).aggregate(t=Sum("net_amount"))["t"] or Decimal("0")

    pending_payout = SellerPayout.objects.filter(
        seller=seller, status=PayoutStatus.PENDING
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    return {
        "available_balance":    str(seller.total_revenue),
        "escrow_holding":       str(escrow_holding),
        "pending_payout":       str(pending_payout),
        "total_earned":         str(seller.total_revenue + escrow_holding),
    }


def add_ledger_entry(seller, entry_type: str, amount: Decimal,
                     reference: str = "", description: str = ""):
    balance = Decimal(seller.total_revenue)
    if entry_type == "credit":
        balance += amount
    elif entry_type == "debit":
        balance -= amount
    SellerLedger.objects.create(
        tenant=seller.tenant, seller=seller,
        entry_type=entry_type, amount=amount,
        balance_after=balance, reference=reference, description=description,
    )
