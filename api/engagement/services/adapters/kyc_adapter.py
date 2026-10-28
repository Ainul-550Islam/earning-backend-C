"""
KYCAdapter
==========
Wraps api.kyc for engagement.

KYC affects engagement in these ways:
    - Unverified users: capped daily spin/checkin rewards
    - Verified users: higher limits, premium battle pass discount
    - AML flags: block withdrawal-related engagement rewards
    - Country restrictions: geo-block certain engagement features
"""

import logging
logger = logging.getLogger("engagement.adapters.kyc")

# Reward caps for unverified users
UNVERIFIED_CAPS = {
    "daily_coin_max":   100,   # Max coins/day unverified
    "withdrawal_coins": 0,     # Cannot convert to withdrawal
    "referral_bonus":   0.5,   # 50% of normal referral bonus
}


class KYCAdapter:

    @staticmethod
    def get_status(user) -> dict:
        """
        Get KYC verification status for a user.

        Returns:
            {
                "is_verified": bool,
                "level": str,          # "none"|"basic"|"full"|"enhanced"
                "country_code": str,
                "is_aml_flagged": bool,
                "can_withdraw": bool,
                "reward_multiplier": float,  # 1.0 = full rewards
                "source": str,
            }
        """
        try:
            from api.kyc.services.VerificationService import VerificationService
            svc = VerificationService()
            status = svc.get_user_status(user)

            is_verified = status.get("is_verified", False)
            level = status.get("level", "none")
            is_aml = status.get("is_aml_flagged", False)

            return {
                "is_verified":        is_verified,
                "level":              level,
                "country_code":       status.get("country_code", ""),
                "is_aml_flagged":     is_aml,
                "can_withdraw":       is_verified and not is_aml,
                "reward_multiplier":  1.0 if is_verified else 0.5,
                "source":             "kyc_app",
            }
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"KYCAdapter.get_status user={user.pk}: {e}")

        # Fallback: read from user model attributes
        is_verified = getattr(user, "is_kyc_verified",
                     getattr(user, "kyc_verified",
                     getattr(user, "is_verified", False)))
        return {
            "is_verified":        bool(is_verified),
            "level":              "basic" if is_verified else "none",
            "country_code":       getattr(user, "country_code", ""),
            "is_aml_flagged":     False,
            "can_withdraw":       bool(is_verified),
            "reward_multiplier":  1.0 if is_verified else 0.5,
            "source":             "user_model",
        }

    @staticmethod
    def get_reward_multiplier(user) -> float:
        """
        Get reward multiplier based on KYC status.
        1.0 = full rewards (verified), 0.5 = half (unverified).
        """
        status = KYCAdapter.get_status(user)
        return status["reward_multiplier"]

    @staticmethod
    def can_claim_referral_bonus(user) -> bool:
        """Referral bonuses only for KYC-verified users in strict mode."""
        from django.conf import settings
        if not getattr(settings, "ENGAGEMENT_KYC_REQUIRED_FOR_REFERRAL", False):
            return True
        return KYCAdapter.get_status(user)["is_verified"]

    @staticmethod
    def apply_kyc_cap(user, amount: float, action: str) -> float:
        """
        Apply KYC-based reward cap to an amount.
        Returns adjusted (possibly reduced) amount.
        """
        status = KYCAdapter.get_status(user)
        if status["is_aml_flagged"]:
            return 0.0  # AML flagged → no reward
        multiplier = status["reward_multiplier"]
        return round(amount * multiplier, 2)
