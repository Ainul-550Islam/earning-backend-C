"""
api/kyc/payout_integration.py
==============================
KYC integration bridge for api.payout_queue.

HOW IT WORKS
------------
services.add_payout_items() calls is_user_kyc_verified(user_id) for every
user in a payout batch when PAYOUT_KYC_CHECK_ENABLED=True.

If ANY user is not verified, the entire add_payout_items() call is rejected
with a PayoutQueueError — no items are created.

REQUIREMENTS
------------
This file assumes your KYC model looks approximately like:

    class KYCProfile(models.Model):
        user       = models.OneToOneField(User, on_delete=models.CASCADE)
        status     = models.CharField(max_length=20, choices=KYCStatus.choices)
        expires_at = models.DateTimeField(null=True, blank=True)
        ...

    class KYCStatus(models.TextChoices):
        VERIFIED   = "VERIFIED"
        PENDING    = "PENDING"
        REJECTED   = "REJECTED"
        EXPIRED    = "EXPIRED"

If your KYC model differs, update the query in is_user_kyc_verified() below.

DISABLE IN DEVELOPMENT
-----------------------
In your .env or settings/local.py:
    PAYOUT_KYC_CHECK_ENABLED=False

DO NOT disable in production — required for Bangladesh Bank BFIU compliance.
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


def is_user_kyc_verified(user_id: Any) -> bool:
    """
    Returns True if the user has passed KYC verification and the
    verification has not expired.

    Called by: api.payout_queue.services.add_payout_items()

    Args:
        user_id: PK of the User to check.

    Returns:
        True if KYC status is VERIFIED and not expired.
        False if KYCProfile does not exist, status is not VERIFIED,
        or the verification has expired.
    """
    if user_id is None:
        logger.warning("is_user_kyc_verified: user_id is None — returning False")
        return False

    try:
        from api.kyc.models import KYCProfile
    except ImportError as exc:
        logger.error(
            "is_user_kyc_verified: cannot import api.kyc.models: %s. "
            "Returning False (payout blocked).",
            exc,
        )
        return False

    try:
        profile = KYCProfile.objects.select_related("user").get(user_id=user_id)
    except KYCProfile.DoesNotExist:
        logger.info(
            "is_user_kyc_verified: no KYCProfile for user_id=%s — not verified.",
            user_id,
        )
        return False
    except Exception as exc:
        logger.error(
            "is_user_kyc_verified: DB error for user_id=%s: %s — returning False.",
            user_id, exc,
        )
        return False

    # Status check — adjust "VERIFIED" to match your KYCStatus choices
    if str(getattr(profile, "status", "") or "").upper() != "VERIFIED":
        logger.info(
            "is_user_kyc_verified: user_id=%s status=%s — not verified.",
            user_id, profile.status,
        )
        return False

    # Expiry check (if your model has expires_at)
    expires_at = getattr(profile, "expires_at", None)
    if expires_at is not None and expires_at <= timezone.now():
        logger.warning(
            "is_user_kyc_verified: user_id=%s KYC expired at %s.",
            user_id, expires_at,
        )
        return False

    logger.debug("is_user_kyc_verified: user_id=%s — VERIFIED ✅", user_id)
    return True


def get_kyc_status(user_id: Any) -> str:
    """
    Returns the KYC status string for a user, or "NOT_FOUND" if none exists.

    Useful for debugging and admin views. Not called by payout_queue directly.

    Returns one of: "VERIFIED", "PENDING", "REJECTED", "EXPIRED", "NOT_FOUND"
    """
    if user_id is None:
        return "NOT_FOUND"
    try:
        from api.kyc.models import KYCProfile
        profile = KYCProfile.objects.get(user_id=user_id)
        expires_at = getattr(profile, "expires_at", None)
        if profile.status == "VERIFIED" and expires_at and expires_at <= timezone.now():
            return "EXPIRED"
        return profile.status
    except Exception:
        return "NOT_FOUND"
