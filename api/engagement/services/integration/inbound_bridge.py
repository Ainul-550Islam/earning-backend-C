# engagement/services/integration/inbound_bridge.py
"""
EngagementBridge (Inbound)
==========================
Public API that OTHER apps use to interact with engagement.

Other apps import ONLY this — never engagement internals.

Usage from any other app:
    from api.engagement.services.integration import EngagementBridge

    # Award coins for completing a task
    EngagementBridge.award_task_coins(user, amount=50, task_id="task-123")

    # Award coins for a wallet deposit
    EngagementBridge.award_deposit_bonus(user, deposit_amount=Decimal("100"))

    # Notify engagement that user signed up via referral
    EngagementBridge.on_user_signup(user, referral_code="EARN1234")

    # Get user's engagement summary for profile page
    summary = EngagementBridge.get_user_summary(user)
"""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("engagement.integration.inbound")


class EngagementBridge:
    """
    Inbound bridge — called BY other apps, not by engagement itself.
    Single stable API surface that won't break when engagement internals change.
    """

    # ── Called by: tasks app, offer_inventory, promotions ────────────────────

    @staticmethod
    def award_task_coins(user, amount: float, task_id: str = "",
                          task_title: str = "", ip_address: str = None) -> dict:
        """
        Award coins when user completes an earning task (offer, survey, etc.)
        Triggers: wallet credit + referral commission + notifications.
        """
        from decimal import Decimal as D
        try:
            from api.engagement.services.coin_service import CoinService
            from api.engagement.services.integration.referral_bridge import ReferralBridge

            amt = D(str(amount))
            result = CoinService.add(
                user, amt,
                source="task",
                reference_id=task_id,
                description=f"Task reward: {task_title or task_id}",
                ip_address=ip_address,
            )

            # Referral commission
            ReferralBridge.on_coins_earned(user, amt, source="task")

            # Quest progress
            try:
                from api.engagement.services.quest_service import QuestService
                QuestService.record_action(user, "task", increment=1)
            except Exception:
                pass

            return {"success": True, "coins_credited": float(amt), "new_balance": float(result)}
        except Exception as e:
            logger.error(f"EngagementBridge.award_task_coins user={user.pk}: {e}")
            return {"success": False, "error": str(e)}

    # ── Called by: wallet app ─────────────────────────────────────────────────

    @staticmethod
    def award_deposit_bonus(user, deposit_amount: Decimal,
                             deposit_txn_id: str = "") -> dict:
        """
        Award engagement bonus coins when user makes a wallet deposit.
        Bonus = 5% of deposit amount (configurable).
        """
        try:
            from django.conf import settings
            pct = Decimal(str(getattr(settings, "ENGAGEMENT_DEPOSIT_BONUS_PCT", "5")))
            bonus = (deposit_amount * pct / 100).quantize(Decimal("0.01"))
            if bonus <= 0:
                return {"success": True, "bonus": 0}

            from api.engagement.services.coin_service import CoinService
            result = CoinService.add(
                user, bonus,
                source="deposit_bonus",
                reference_id=deposit_txn_id,
                description=f"Deposit bonus ({pct}%)",
            )
            return {"success": True, "bonus": float(bonus), "new_balance": float(result)}
        except Exception as e:
            logger.error(f"EngagementBridge.award_deposit_bonus user={user.pk}: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def on_withdrawal_completed(user, amount: Decimal) -> dict:
        """
        Called when user withdraws money. Updates engagement stats.
        Triggers referral commission on withdrawal (if configured).
        """
        try:
            from api.engagement.services.integration.referral_bridge import ReferralBridge
            ReferralBridge.on_withdrawal(user, amount)

            # Quest/achievement progress
            try:
                from api.engagement.services.quest_service import QuestService
                QuestService.record_action(user, "withdrawal", increment=1)
            except Exception:
                pass

            return {"success": True}
        except Exception as e:
            logger.error(f"EngagementBridge.on_withdrawal_completed user={user.pk}: {e}")
            return {"success": False, "error": str(e)}

    # ── Called by: users app ──────────────────────────────────────────────────

    @staticmethod
    def on_user_signup(user, referral_code: str = "", ip_address: str = None) -> dict:
        """
        Called when a new user signs up.
        - Creates XP record
        - Processes referral code
        - Awards signup bonus
        - Sends welcome notification
        """
        results = {}

        # Create XP record
        try:
            from api.engagement.services.xp_service import XPService
            XPService.get_or_create(user)
            results["xp_created"] = True
        except Exception as e:
            results["xp_created"] = False
            logger.warning(f"EngagementBridge.on_signup xp creation user={user.pk}: {e}")

        # Process referral code
        if referral_code:
            try:
                from api.engagement.services.integration.referral_bridge import ReferralBridge
                ref_result = ReferralBridge.on_signup_with_code(user, referral_code)
                results["referral"] = ref_result
            except Exception as e:
                results["referral"] = {"success": False, "error": str(e)}

        # Award signup bonus
        try:
            from django.conf import settings
            bonus = Decimal(str(getattr(settings, "ENGAGEMENT_SIGNUP_BONUS", "10")))
            if bonus > 0:
                from api.engagement.services.coin_service import CoinService
                CoinService.add(user, bonus, source="signup_bonus",
                                description="Welcome bonus!")
                results["signup_bonus"] = float(bonus)
        except Exception as e:
            logger.warning(f"EngagementBridge.on_signup bonus user={user.pk}: {e}")

        # Welcome notification
        try:
            from api.engagement.services.integration.notification_bridge import NotificationBridge
            NotificationBridge.send_custom(
                user, "checkin_reward",
                title="Welcome to the Rewards Hub! 🎉",
                body="Check in daily, spin the wheel, and earn coins!",
            )
        except Exception:
            pass

        return results

    @staticmethod
    def on_user_profile_updated(user) -> dict:
        """
        Called when user updates profile (country, tier change, etc.)
        Syncs engagement data that depends on profile.
        """
        try:
            from api.engagement.services.integration.wallet_bridge import WalletBridge
            WalletBridge.sync_balance(user)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Called by: referral app ───────────────────────────────────────────────

    @staticmethod
    def award_referral_commission(
        user, commission_amount: Decimal,
        referee_username: str = "", level: int = 1,
    ) -> dict:
        """
        Award referral commission coins to a user.
        Called by referral app when commission is calculated.
        """
        try:
            from api.engagement.services.coin_service import CoinService
            from api.engagement.services.integration.notification_bridge import NotificationBridge

            result = CoinService.add(
                user, commission_amount,
                source="referral",
                description=f"Referral commission L{level}: {referee_username}",
            )
            NotificationBridge.referral_commission(
                user, referee_username, float(commission_amount), level
            )
            return {"success": True, "coins_credited": float(commission_amount)}
        except Exception as e:
            logger.error(f"EngagementBridge.award_referral_commission user={user.pk}: {e}")
            return {"success": False, "error": str(e)}

    # ── Read API: used by profile, admin, analytics ───────────────────────────

    @staticmethod
    def get_user_summary(user) -> dict:
        """
        Full engagement summary for a user.
        Called by profile page, admin panel, analytics.
        """
        summary = {
            "user_id": user.pk,
            "coin_balance": 0.0,
            "level": 1,
            "total_xp": 0,
            "checkin_streak": 0,
            "total_checkins": 0,
            "spins_today": 0,
            "achievements_count": 0,
            "guild": None,
            "referral_code": None,
            "leaderboard_rank": None,
            "battle_pass_tier": 0,
            "prestige_level": 0,
        }

        try:
            from api.engagement.services.integration.wallet_bridge import WalletBridge
            summary["coin_balance"] = float(WalletBridge.get_balance(user))
        except Exception:
            summary["coin_balance"] = float(getattr(user, "coin_balance", 0))

        try:
            from api.engagement.models.xp import UserXP
            xp = UserXP.objects.filter(user=user).first()
            if xp:
                summary["level"] = xp.level
                summary["total_xp"] = xp.total_xp
        except Exception:
            pass

        try:
            from api.engagement.models.checkin import DailyCheckIn
            from datetime import date
            last = DailyCheckIn.objects.filter(user=user).order_by("-date").first()
            if last:
                summary["checkin_streak"] = last.consecutive_days
            summary["total_checkins"] = DailyCheckIn.objects.filter(user=user).count()
        except Exception:
            pass

        try:
            from api.engagement.models.spinwheel import SpinWheel
            from datetime import date
            summary["spins_today"] = SpinWheel.objects.filter(
                user=user, spun_at__date=date.today()
            ).count()
        except Exception:
            pass

        try:
            from api.engagement.models.achievement import UserAchievement
            summary["achievements_count"] = UserAchievement.objects.filter(
                user=user
            ).count()
        except Exception:
            pass

        try:
            from api.engagement.models.guild import GuildMember
            member = GuildMember.objects.filter(
                user=user, status="active"
            ).select_related("guild").first()
            if member:
                summary["guild"] = {
                    "id": member.guild.pk,
                    "name": member.guild.name,
                    "role": member.role,
                }
        except Exception:
            pass

        try:
            from api.engagement.services.integration.referral_bridge import ReferralBridge
            summary["referral_code"] = ReferralBridge.get_referral_code(user)
        except Exception:
            pass

        try:
            from api.engagement.models.leaderboard import Leaderboard
            from datetime import date
            lb = Leaderboard.objects.filter(
                user=user, date=date.today()
            ).first()
            if lb:
                summary["leaderboard_rank"] = lb.rank
        except Exception:
            pass

        try:
            from api.engagement.models.battle_pass import UserBattlePass
            ubp = UserBattlePass.objects.filter(user=user).order_by("-id").first()
            if ubp:
                summary["battle_pass_tier"] = ubp.current_tier
        except Exception:
            pass

        try:
            from api.engagement.models.prestige import UserPrestige
            up = UserPrestige.objects.filter(user=user).first()
            if up:
                summary["prestige_level"] = up.level
        except Exception:
            pass

        return summary

    @staticmethod
    def get_leaderboard(date=None, limit: int = 100) -> list:
        """
        Get leaderboard for external apps (analytics, admin).
        """
        try:
            from api.engagement.services.leaderboard_service import LeaderboardService
            from datetime import date as _date
            entries = LeaderboardService.get_leaderboard(date or _date.today(), limit=limit)
            return [
                {
                    "rank": e.rank,
                    "user_id": e.user_id,
                    "username": str(e.user),
                    "total_coins_earned": float(e.total_coins_earned or 0),
                }
                for e in entries
            ]
        except Exception as e:
            logger.error(f"EngagementBridge.get_leaderboard: {e}")
            return []

    @staticmethod
    def award_admin_coins(user, amount: Decimal, reason: str = "",
                           admin_user=None) -> dict:
        """
        Admin manually awards coins to a user.
        Called from admin panel or management commands.
        """
        try:
            from api.engagement.services.coin_service import CoinService
            result = CoinService.add(
                user, amount,
                source="admin",
                description=reason or "Admin credit",
            )
            logger.info(
                f"EngagementBridge.award_admin_coins: user={user.pk} "
                f"amount={amount} by admin={getattr(admin_user, 'pk', 'system')}"
            )
            return {"success": True, "new_balance": float(result)}
        except Exception as e:
            logger.error(f"EngagementBridge.award_admin_coins user={user.pk}: {e}")
            return {"success": False, "error": str(e)}
