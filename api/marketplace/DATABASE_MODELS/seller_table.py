"""
DATABASE_MODELS/seller_table.py — Seller Table Reference & Queries
"""
from api.marketplace.models import SellerProfile, SellerVerification, SellerPayout, CommissionConfig
from api.marketplace.enums import SellerStatus, VerificationStatus, PayoutStatus
from django.db.models import Sum, Count, Avg


def get_seller_by_id(seller_id: int, tenant=None) -> SellerProfile:
    qs = SellerProfile.objects.select_related("user","verification")
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.get(pk=seller_id)


def active_sellers_count(tenant) -> int:
    return SellerProfile.objects.filter(tenant=tenant, status=SellerStatus.ACTIVE).count()


def sellers_awaiting_kyc(tenant) -> list:
    return list(
        SellerVerification.objects.filter(
            seller__tenant=tenant, status=VerificationStatus.PENDING
        ).select_related("seller__user").order_by("created_at")
    )


def top_sellers_by_revenue(tenant, limit: int = 10) -> list:
    return list(
        SellerProfile.objects.filter(tenant=tenant, status=SellerStatus.ACTIVE)
        .order_by("-total_revenue")[:limit]
        .values("store_name","total_revenue","average_rating","total_sales")
    )


def pending_payout_total(tenant) -> str:
    agg = SellerPayout.objects.filter(
        tenant=tenant, status=PayoutStatus.PENDING
    ).aggregate(t=Sum("amount"))
    return str(agg["t"] or 0)


__all__ = [
    "SellerProfile","SellerVerification","SellerPayout","CommissionConfig",
    "get_seller_by_id","active_sellers_count","sellers_awaiting_kyc",
    "top_sellers_by_revenue","pending_payout_total",
]
