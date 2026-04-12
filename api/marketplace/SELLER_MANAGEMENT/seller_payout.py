"""
SELLER_MANAGEMENT/seller_payout.py — Seller Payout Management
"""
from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone
from api.marketplace.models import SellerPayout, SellerProfile
from api.marketplace.enums import PayoutStatus
from api.marketplace.constants import MIN_PAYOUT_AMOUNT


def pending_payouts(tenant):
    return SellerPayout.objects.filter(tenant=tenant, status=PayoutStatus.PENDING).select_related("seller")


def seller_payout_history(seller: SellerProfile, limit: int = 50):
    return SellerPayout.objects.filter(seller=seller).order_by("-created_at")[:limit]


def seller_payout_summary(seller: SellerProfile) -> dict:
    qs = SellerPayout.objects.filter(seller=seller)
    return {
        "total_paid":    str(qs.filter(status=PayoutStatus.COMPLETED).aggregate(t=Sum("amount"))["t"] or 0),
        "pending":       str(qs.filter(status=PayoutStatus.PENDING).aggregate(t=Sum("amount"))["t"] or 0),
        "processing":    str(qs.filter(status=PayoutStatus.PROCESSING).aggregate(t=Sum("amount"))["t"] or 0),
        "total_payouts": qs.count(),
        "last_payout_date": qs.filter(status=PayoutStatus.COMPLETED).order_by("-created_at").values_list("created_at",flat=True).first(),
    }


def can_request_payout(seller: SellerProfile, amount: Decimal) -> dict:
    """Check if a seller is eligible to request a payout."""
    if seller.status != "active":
        return {"eligible": False, "reason": f"Account is {seller.status}"}
    if amount < MIN_PAYOUT_AMOUNT:
        return {"eligible": False, "reason": f"Minimum payout: {MIN_PAYOUT_AMOUNT} BDT"}
    if amount > seller.total_revenue:
        return {"eligible": False, "reason": "Insufficient balance"}

    # Check no pending payout already
    pending = SellerPayout.objects.filter(
        seller=seller, status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING]
    ).exists()
    if pending:
        return {"eligible": False, "reason": "A payout is already in progress"}

    # Check verification
    if not hasattr(seller, "verification") or seller.verification.status != "verified":
        return {"eligible": False, "reason": "Account not verified. Complete KYC first."}

    return {"eligible": True, "reason": ""}


def create_payout_request(seller: SellerProfile, amount: Decimal, method: str, account_number: str, note: str = "") -> SellerPayout:
    """Create a manual payout request from seller."""
    check = can_request_payout(seller, amount)
    if not check["eligible"]:
        raise ValueError(check["reason"])

    return SellerPayout.objects.create(
        tenant=seller.tenant,
        seller=seller,
        amount=amount,
        method=method,
        account_number=account_number,
        status=PayoutStatus.PENDING,
        balance_before=seller.total_revenue,
        balance_after=seller.total_revenue - amount,
        note=note or "Manual payout request",
    )


def mark_payout_completed(payout: SellerPayout, reference_id: str, processed_by=None) -> SellerPayout:
    payout.status        = PayoutStatus.COMPLETED
    payout.reference_id  = reference_id
    payout.processed_at  = timezone.now()
    payout.processed_by  = processed_by
    payout.save()
    return payout


def mark_payout_failed(payout: SellerPayout, reason: str) -> SellerPayout:
    payout.status = PayoutStatus.FAILED
    payout.note   = f"FAILED: {reason}"
    payout.save(update_fields=["status","note"])
    return payout
