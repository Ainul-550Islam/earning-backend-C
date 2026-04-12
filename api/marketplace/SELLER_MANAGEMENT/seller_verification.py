"""
SELLER_MANAGEMENT/seller_verification.py — Seller KYC & Verification
"""
from django.db import transaction
from django.utils import timezone
from api.marketplace.models import SellerVerification, SellerProfile
from api.marketplace.enums import VerificationStatus


def get_or_create_verification(seller: SellerProfile) -> SellerVerification:
    ver, _ = SellerVerification.objects.get_or_create(
        seller=seller, defaults={"tenant": seller.tenant, "status": VerificationStatus.UNVERIFIED}
    )
    return ver


def submit_kyc(seller: SellerProfile, nid_number: str = "", **docs) -> SellerVerification:
    """Submit KYC documents for verification."""
    ver = get_or_create_verification(seller)
    if nid_number:
        ver.nid_number = nid_number
    for field, value in docs.items():
        if hasattr(ver, field):
            setattr(ver, field, value)
    ver.status = VerificationStatus.PENDING
    ver.save()
    return ver


def get_verification_status(seller: SellerProfile) -> dict:
    ver = get_or_create_verification(seller)
    return {
        "status":     ver.status,
        "nid_number": ver.nid_number,
        "nid_front":  bool(ver.nid_front),
        "nid_back":   bool(ver.nid_back),
        "selfie":     bool(ver.selfie),
        "reviewed_at":ver.reviewed_at.isoformat() if ver.reviewed_at else None,
        "rejection_reason": ver.rejection_reason,
        "documents_complete": all([ver.nid_front, ver.nid_back, ver.selfie]),
    }


@transaction.atomic
def approve_verification(seller: SellerProfile, admin_user) -> SellerVerification:
    ver = get_or_create_verification(seller)
    ver.approve(reviewed_by=admin_user)
    from api.marketplace.WEBHOOKS.seller_webhook import on_seller_verified
    try:
        on_seller_verified(seller)
    except Exception:
        pass
    return ver


@transaction.atomic
def reject_verification(seller: SellerProfile, admin_user, reason: str) -> SellerVerification:
    ver = get_or_create_verification(seller)
    ver.reject(reviewed_by=admin_user, reason=reason)
    return ver


def pending_verifications(tenant) -> list:
    return list(
        SellerVerification.objects.filter(
            seller__tenant=tenant, status=VerificationStatus.PENDING
        ).select_related("seller","seller__user").order_by("created_at")
    )


def verification_stats(tenant) -> dict:
    qs = SellerVerification.objects.filter(seller__tenant=tenant)
    return {
        "total":      qs.count(),
        "pending":    qs.filter(status=VerificationStatus.PENDING).count(),
        "verified":   qs.filter(status=VerificationStatus.VERIFIED).count(),
        "rejected":   qs.filter(status=VerificationStatus.REJECTED).count(),
        "unverified": qs.filter(status=VerificationStatus.UNVERIFIED).count(),
    }
