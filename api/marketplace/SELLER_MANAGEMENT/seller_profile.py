"""
SELLER_MANAGEMENT/seller_profile.py — Seller Profile Management
================================================================
"""
from django.db import transaction
from api.marketplace.models import SellerProfile
from api.marketplace.utils import unique_slugify


@transaction.atomic
def create_seller_profile(user, tenant, store_name: str, phone: str, **kwargs) -> SellerProfile:
    slug = unique_slugify(SellerProfile, store_name)
    return SellerProfile.objects.create(
        user=user, tenant=tenant,
        store_name=store_name, store_slug=slug, phone=phone,
        status="pending", **kwargs
    )


def get_seller_by_user(user, tenant) -> SellerProfile:
    return SellerProfile.objects.filter(user=user, tenant=tenant).first()


def get_seller_by_slug(slug: str, tenant) -> SellerProfile:
    try:
        return SellerProfile.objects.get(store_slug=slug, tenant=tenant)
    except SellerProfile.DoesNotExist:
        return None


def update_store_info(seller: SellerProfile, **data) -> SellerProfile:
    """Update seller's public store information."""
    allowed_fields = [
        "store_name","store_description","store_banner","store_logo",
        "store_url","city","district","address","country",
    ]
    for field in allowed_fields:
        if field in data:
            setattr(seller, field, data[field])
    seller.save()
    return seller


def update_business_details(seller: SellerProfile, **data) -> SellerProfile:
    """Update legal/business information."""
    allowed_fields = ["business_type","business_name","trade_license","tin_number","phone"]
    for field in allowed_fields:
        if field in data:
            setattr(seller, field, data[field])
    seller.save()
    return seller


def get_active_sellers(tenant, limit: int = None, featured_only: bool = False):
    qs = SellerProfile.objects.filter(tenant=tenant, status="active")
    if featured_only:
        qs = qs.filter(is_featured=True)
    qs = qs.order_by("-average_rating","-total_sales")
    return qs[:limit] if limit else qs


def suspend_seller(seller: SellerProfile, reason: str, suspended_by=None) -> SellerProfile:
    seller.status = "suspended"
    seller.save(update_fields=["status"])
    from api.marketplace.WEBHOOKS.seller_webhook import on_seller_suspended
    try:
        on_seller_suspended(seller)
    except Exception:
        pass
    return seller


def activate_seller(seller: SellerProfile) -> SellerProfile:
    seller.status = "active"
    seller.save(update_fields=["status"])
    from api.marketplace.WEBHOOKS.seller_webhook import on_seller_verified
    try:
        on_seller_verified(seller)
    except Exception:
        pass
    return seller


def seller_public_profile(seller: SellerProfile) -> dict:
    return {
        "store_name":      seller.store_name,
        "store_slug":      seller.store_slug,
        "store_logo":      seller.store_logo.url if seller.store_logo else None,
        "store_banner":    seller.store_banner.url if seller.store_banner else None,
        "store_description": seller.store_description,
        "city":            seller.city,
        "country":         seller.country,
        "average_rating":  str(seller.average_rating),
        "total_reviews":   seller.total_reviews,
        "total_sales":     seller.total_sales,
        "member_since":    seller.created_at.strftime("%B %Y"),
        "response_rate":   str(seller.response_rate) + "%",
    }


def update_response_rate(seller: SellerProfile):
    """Recalculate seller response rate based on dispute messages."""
    from api.marketplace.DISPUTE_RESOLUTION.dispute_model import Dispute, DisputeMessage
    from django.db.models import Count
    disputes = Dispute.objects.filter(against_seller=seller)
    if not disputes.exists():
        return
    responded = disputes.filter(messages__role="seller").distinct().count()
    rate = round(responded / disputes.count() * 100, 1)
    SellerProfile.objects.filter(pk=seller.pk).update(response_rate=rate)
