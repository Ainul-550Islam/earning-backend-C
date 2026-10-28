# engagement/services/integration/referral_bridge.py
"""
ReferralBridge
==============
Engagement → api.referral bridge.

When engagement awards coins (check-in, spin, quest, achievement, etc.),
referral commission must propagate up the referral tree.

This bridge calls api.referral.INTEGRATION_SYSTEM.bridge.ReferralBridge
so the referrer chain gets their cut automatically.

Also handles:
    - Registering a new referral when referee completes first engagement action
    - Querying referral stats for the dashboard
    - Generating / validating referral codes via referral app
"""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("engagement.integration.referral")


class ReferralBridge:
    """
    Engagement → Referral bridge.
    All methods are no-ops if api.referral is not installed.
    """

    @staticmethod
    def _get_bridge():
        """Get the referral system bridge. Returns None if unavailable."""
        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import (
                ReferralBridge as SysReferralBridge,
            )
            return SysReferralBridge()
        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"ReferralBridge: cannot load referral bridge: {e}")
            return None

    # ── Outbound: engagement tells referral about user earnings ──────────────

    @staticmethod
    def on_coins_earned(user, amount: Decimal, source: str, task=None) -> dict:
        """
        Notify referral system that user earned coins.
        Triggers commission calculation for all referrer ancestors.

        Call this after EVERY successful coin credit in engagement.

        Args:
            user:   The user who earned coins
            amount: Coin amount earned
            source: 'checkin' | 'spin' | 'quest' | 'achievement' | etc.
            task:   Optional task object (for task-completion flow)

        Returns:
            {"processed": bool, "commissions": int, "reason": str}
        """
        if not amount or float(amount) <= 0:
            return {"processed": False, "reason": "zero_amount"}

        bridge = ReferralBridge._get_bridge()
        if bridge is None:
            return {"processed": False, "reason": "referral_app_unavailable"}

        try:
            result = bridge.on_task_earned(
                user=user,
                task=task,
                amount=float(amount),
                completion=None,
                source=source,
                metadata={"engagement_source": source},
            )
            logger.debug(
                f"ReferralBridge.on_coins_earned: user={user.pk} "
                f"amount={amount} source={source} result={result}"
            )
            return result
        except Exception as e:
            logger.error(
                f"ReferralBridge.on_coins_earned FAILED user={user.pk}: {e}"
            )
            return {"processed": False, "reason": str(e)}

    @staticmethod
    def on_signup_with_code(new_user, referral_code: str) -> dict:
        """
        Register a new user as referred via code.
        Called from engagement referral endpoint when referee registers.

        Returns:
            {"success": bool, "referrer_id": int | None, "bonus_credited": bool}
        """
        if not referral_code:
            return {"success": False, "reason": "no_code"}

        bridge = ReferralBridge._get_bridge()
        if bridge is None:
            # Fallback: use engagement's own referral service
            try:
                from api.engagement.services.referral_service import ReferralService
                return ReferralService.process_signup(new_user, referral_code)
            except Exception as e:
                return {"success": False, "reason": str(e)}

        try:
            result = bridge.on_signup(new_user=new_user, referral_code=referral_code)
            logger.info(
                f"ReferralBridge.on_signup: user={new_user.pk} "
                f"code={referral_code} result={result}"
            )
            return result
        except Exception as e:
            logger.error(
                f"ReferralBridge.on_signup FAILED user={new_user.pk} "
                f"code={referral_code}: {e}"
            )
            return {"success": False, "reason": str(e)}

    @staticmethod
    def on_withdrawal(user, amount: Decimal) -> dict:
        """
        Notify referral system about a withdrawal.
        Some referral programs calculate commission on withdrawals.
        """
        bridge = ReferralBridge._get_bridge()
        if bridge is None:
            return {"processed": False, "reason": "referral_app_unavailable"}

        try:
            return bridge.on_withdrawal(user=user, amount=float(amount))
        except Exception as e:
            logger.warning(f"ReferralBridge.on_withdrawal user={user.pk}: {e}")
            return {"processed": False, "reason": str(e)}

    # ── Inbound: engagement queries referral data ─────────────────────────────

    @staticmethod
    def get_referral_code(user) -> Optional[str]:
        """
        Get the user's referral code.
        Tries api.referral first, then engagement's own model.
        """
        # Try api.referral
        try:
            from api.referral.models import ReferralCode
            obj = ReferralCode.objects.filter(user=user, is_active=True).first()
            if obj:
                return obj.code
        except Exception:
            pass

        # Fallback: engagement referral service
        try:
            from api.engagement.services.referral_service import ReferralService
            return ReferralService.generate_code(user)
        except Exception as e:
            logger.error(f"ReferralBridge.get_referral_code user={user.pk}: {e}")
            return None

    @staticmethod
    def get_referral_stats(user) -> dict:
        """
        Get referral stats for the engagement dashboard.
        Returns combined data from api.referral + engagement models.
        """
        stats = {
            "referral_code": None,
            "total_referrals": 0,
            "active_referrals": 0,
            "total_commission_earned": 0.0,
            "pending_commission": 0.0,
            "referral_url": None,
        }

        # Get code
        stats["referral_code"] = ReferralBridge.get_referral_code(user)

        # Try api.referral for stats
        try:
            from api.referral.models import Referral, ReferralCommission
            referrals = Referral.objects.filter(referrer=user)
            stats["total_referrals"] = referrals.count()
            stats["active_referrals"] = referrals.filter(status="active").count()

            from django.db.models import Sum
            commission = ReferralCommission.objects.filter(
                beneficiary=user
            ).aggregate(
                total=Sum("amount"),
                pending=Sum("amount", filter={"status": "pending"}),
            )
            stats["total_commission_earned"] = float(commission["total"] or 0)
            stats["pending_commission"] = float(commission["pending"] or 0)
        except Exception:
            # Fallback: engagement referral models
            try:
                from api.engagement.models.referral import Referral
                from django.db.models import Sum
                referrals = Referral.objects.filter(referrer=user)
                stats["total_referrals"] = referrals.count()
                stats["active_referrals"] = referrals.filter(status="rewarded").count()
            except Exception:
                pass

        # Build referral URL
        if stats["referral_code"]:
            try:
                from django.conf import settings
                base = getattr(settings, "FRONTEND_URL", "https://app.example.com")
                stats["referral_url"] = f"{base}/join?ref={stats['referral_code']}"
            except Exception:
                pass

        return stats

    @staticmethod
    def validate_code(code: str) -> Optional[object]:
        """
        Validate a referral code. Returns the referrer User or None.
        """
        if not code:
            return None

        # Try api.referral
        try:
            from api.referral.models import ReferralCode
            obj = ReferralCode.objects.filter(code=code, is_active=True).first()
            if obj:
                return obj.user
        except Exception:
            pass

        # Fallback: engagement Referral model
        try:
            from api.engagement.models.referral import Referral
            obj = Referral.objects.filter(referral_code=code).first()
            if obj:
                return obj.referrer
        except Exception:
            pass

        return None
