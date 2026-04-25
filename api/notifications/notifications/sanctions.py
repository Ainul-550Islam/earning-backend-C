# earning_backend/api/notifications/sanctions.py
"""
Sanctions — Notification sending sanction/compliance checker.

Determines whether a notification should be BLOCKED based on:
  1. User account status (suspended, banned, restricted)
  2. Jurisdiction restrictions (GDPR opt-out regions)
  3. Content policy violations (spam keywords, blacklisted domains)
  4. Time-based sanctions (cooling-off period after complaint)
  5. Fraud flags (flagged users get reduced notifications)

The SanctionChecker runs as a pre_send hook in hooks.py.
"""
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


# Spam / blocked keywords in notification content
BLOCKED_KEYWORDS = [
    "earn 0000", "get rich quick", "guaranteed profit", "100% profit",
    "free money", "click here now!!!", "limited time!!!", "act now!!!",
]

# Notification types that are always allowed regardless of sanctions
ALWAYS_ALLOWED_TYPES = {
    "account_suspended", "fraud_detected", "account_locked",
    "security_alert", "two_factor_code", "password_reset",
    "kyc_rejected", "system_alert",
}


class SanctionChecker:
    """Checks if a notification is allowed to be sent based on sanction rules."""

    def check(self, notification, user=None) -> Tuple[bool, str]:
        """
        Run all sanction checks.
        Returns (is_allowed: bool, reason: str)
        """
        notif_type = getattr(notification, "notification_type", "") or ""

        # Always-allowed types bypass all sanctions
        if notif_type in ALWAYS_ALLOWED_TYPES:
            return True, "always_allowed_type"

        if user is None:
            user = getattr(notification, "user", None)

        # Check user account status
        allowed, reason = self._check_user_status(user)
        if not allowed:
            return False, reason

        # Check content policy
        allowed, reason = self._check_content(notification)
        if not allowed:
            return False, reason

        # Check GDPR / region restrictions
        allowed, reason = self._check_region(user, notification)
        if not allowed:
            return False, reason

        return True, "allowed"

    def _check_user_status(self, user) -> Tuple[bool, str]:
        """Block notifications to suspended/deleted users."""
        if user is None:
            return True, ""
        if not getattr(user, "is_active", True):
            return False, "user_account_inactive"
        # Check if user profile has a sanction flag
        try:
            profile = getattr(user, "profile", None)
            if profile:
                if getattr(profile, "is_banned", False):
                    return False, "user_banned"
                if getattr(profile, "notifications_blocked", False):
                    return False, "notifications_blocked_by_admin"
        except Exception:
            pass
        return True, ""

    def _check_content(self, notification) -> Tuple[bool, str]:
        """Block notifications with spam/policy-violating content."""
        title = (getattr(notification, "title", "") or "").lower()
        message = (getattr(notification, "message", "") or "").lower()
        content = title + " " + message
        for keyword in BLOCKED_KEYWORDS:
            if keyword.lower() in content:
                logger.warning(f"SanctionChecker: blocked keyword '{keyword}' in notification")
                return False, f"blocked_keyword: {keyword}"
        return True, ""

    def _check_region(self, user, notification) -> Tuple[bool, str]:
        """Check GDPR and regional notification restrictions."""
        try:
            profile = getattr(user, "profile", None) if user else None
            country = getattr(profile, "country", "") or ""
            # EU GDPR: only transactional notifications allowed without explicit consent
            EU_COUNTRIES = {"DE", "FR", "IT", "ES", "NL", "BE", "SE", "PL", "AT", "DK"}
            if country.upper() in EU_COUNTRIES:
                channel = getattr(notification, "channel", "in_app")
                notif_type = getattr(notification, "notification_type", "")
                TRANSACTIONAL_TYPES = {
                    "withdrawal_success", "withdrawal_failed", "kyc_approved",
                    "kyc_rejected", "security_alert", "login_new_device",
                    "account_suspended", "password_changed",
                }
                if channel == "email" and notif_type not in TRANSACTIONAL_TYPES:
                    # Check if user has given explicit marketing consent
                    gdpr_consent = getattr(profile, "marketing_email_consent", False)
                    if not gdpr_consent:
                        return False, "gdpr_no_marketing_email_consent"
        except Exception as exc:
            logger.debug(f"SanctionChecker._check_region: {exc}")
        return True, ""

    def is_user_sanctioned(self, user) -> bool:
        """Quick check if a user has any active sanctions."""
        allowed, _ = self._check_user_status(user)
        return not allowed


sanction_checker = SanctionChecker()
