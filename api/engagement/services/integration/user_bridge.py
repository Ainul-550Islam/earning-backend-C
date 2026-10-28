# engagement/services/integration/user_bridge.py
"""
UserBridge
==========
Engagement → api.users bridge.

Provides safe access to user profile, tier, KYC status, country,
and other user data that engagement needs without importing users models.
"""

import logging
from typing import Optional

logger = logging.getLogger("engagement.integration.user")


class UserBridge:
    """
    Read/write user profile data from engagement context.
    All methods are safe — return defaults if users app is unavailable.
    """

    @staticmethod
    def get_country_code(user) -> str:
        """Get ISO country code for GEO multipliers."""
        for attr in ("country_code", "country", "profile__country_code"):
            try:
                parts = attr.split("__")
                obj = user
                for part in parts:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                if obj and isinstance(obj, str) and len(obj) == 2:
                    return obj.upper()
            except Exception:
                pass

        # Try profile model
        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).first()
            if profile:
                return getattr(profile, "country_code", "") or ""
        except Exception:
            pass

        return ""

    @staticmethod
    def get_tier(user) -> str:
        """Get user tier: 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond'"""
        for attr in ("tier", "membership_tier", "level_tier"):
            val = getattr(user, attr, None)
            if val:
                return str(val).lower()

        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).values("tier").first()
            if profile:
                return profile.get("tier", "bronze")
        except Exception:
            pass

        return "bronze"

    @staticmethod
    def is_kyc_verified(user) -> bool:
        """Check if user has passed KYC verification."""
        for attr in ("is_kyc_verified", "kyc_verified", "is_verified"):
            val = getattr(user, attr, None)
            if val is not None:
                return bool(val)

        try:
            from api.kyc.models import KYCApplication
            return KYCApplication.objects.filter(
                user=user, status="approved"
            ).exists()
        except Exception:
            pass

        return False

    @staticmethod
    def get_display_name(user) -> str:
        """Get the best display name for a user."""
        for attr in ("username", "display_name", "full_name", "first_name"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return f"User#{user.pk}"

    @staticmethod
    def get_avatar_url(user) -> Optional[str]:
        """Get user's avatar URL for leaderboard/social display."""
        for attr in ("avatar_url", "avatar", "profile_picture"):
            val = getattr(user, attr, None)
            if val:
                try:
                    return val.url if hasattr(val, "url") else str(val)
                except Exception:
                    pass

        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).first()
            if profile and profile.avatar:
                return profile.avatar.url
        except Exception:
            pass

        return None

    @staticmethod
    def get_timezone(user) -> str:
        """Get user's timezone for streak calculations."""
        for attr in ("timezone", "user_timezone", "tz"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return "UTC"

    @staticmethod
    def get_registration_date(user):
        """Get user registration date."""
        for attr in ("date_joined", "created_at", "registered_at"):
            val = getattr(user, attr, None)
            if val:
                return val
        return None

    @staticmethod
    def is_active(user) -> bool:
        """Check if user account is active."""
        return bool(getattr(user, "is_active", True))

    @staticmethod
    def is_banned(user) -> bool:
        """Check if user is banned from engagement features."""
        for attr in ("is_banned", "is_blocked", "is_suspended"):
            val = getattr(user, attr, None)
            if val is not None:
                return bool(val)
        return False

    @staticmethod
    def get_referrer(user) -> Optional[object]:
        """Get the user who referred this user."""
        # Try api.referral
        try:
            from api.referral.models import Referral
            ref = Referral.objects.filter(referee=user).select_related("referrer").first()
            if ref:
                return ref.referrer
        except Exception:
            pass

        # Try engagement referral model
        try:
            from api.engagement.models.referral import Referral as EngReferral
            ref = EngReferral.objects.filter(referee=user).select_related("referrer").first()
            if ref:
                return ref.referrer
        except Exception:
            pass

        return None

    @staticmethod
    def get_profile_summary(user) -> dict:
        """
        Full profile summary for engagement dashboard.
        Aggregates data from users, kyc, referral apps.
        """
        return {
            "user_id": user.pk,
            "username": UserBridge.get_display_name(user),
            "country_code": UserBridge.get_country_code(user),
            "tier": UserBridge.get_tier(user),
            "is_kyc_verified": UserBridge.is_kyc_verified(user),
            "is_active": UserBridge.is_active(user),
            "is_banned": UserBridge.is_banned(user),
            "avatar_url": UserBridge.get_avatar_url(user),
            "timezone": UserBridge.get_timezone(user),
            "registration_date": UserBridge.get_registration_date(user),
        }
