# engagement/services/checkin_service.py
import logging
from datetime import date, timedelta
from django.db import transaction
from .coin_service import CoinService
from .xp_service import XPService
from ..models.checkin import DailyCheckIn
from ..constants import CHECKIN_BASE_COINS, CHECKIN_MAX_STREAK_BONUS, XP_PER_CHECKIN
from ..exceptions import AlreadyCheckedInError

logger = logging.getLogger(__name__)


class CheckInService:

    @classmethod
    @transaction.atomic
    def process(cls, user, tenant=None) -> dict:
        """
        Perform today's check-in for `user`.
        Raises AlreadyCheckedInError if already done today.
        Returns a rich result dict.
        """
        today = date.today()

        if DailyCheckIn.objects.filter(user=user, date=today).exists():
            raise AlreadyCheckedInError()

        # ── Streak calculation ───────────────────────────────────────────────
        yesterday      = today - timedelta(days=1)
        yesterday_ci   = DailyCheckIn.objects.filter(user=user, date=yesterday).first()

        # Check for streak_shield in inventory and detect streak breaking
        shield_used    = False
        prev_ci        = None  # Initialize prev_ci to avoid NameError
        old_streak     = 0
        
        # Get previous streak for streak broken detection
        latest_checkin = DailyCheckIn.objects.filter(user=user).order_by("-date").first()
        if latest_checkin and latest_checkin.date != yesterday:
            old_streak = latest_checkin.consecutive_days
        
        if not yesterday_ci:
            two_days_ago = today - timedelta(days=2)
            prev_ci = DailyCheckIn.objects.filter(user=user, date=two_days_ago).first()
            if prev_ci:
                shield_used = cls._consume_streak_shield(user)

        consecutive = (yesterday_ci.consecutive_days + 1) if yesterday_ci else (
            (prev_ci.consecutive_days + 1) if (not yesterday_ci and shield_used) else 1
        )
        
        # Fire streak_broken_signal if streak was broken and not protected by shield
        if old_streak > 1 and consecutive == 1 and not shield_used:
            cls._fire_streak_broken_signal(user, old_streak)

        # ── Coin calculation ─────────────────────────────────────────────────
        multiplier   = min(consecutive, CHECKIN_MAX_STREAK_BONUS)
        coins_earned = CHECKIN_BASE_COINS * multiplier
        xp_earned    = XP_PER_CHECKIN + (5 * (multiplier - 1))  # bonus XP for streaks

        # ── Persist ─────────────────────────────────────────────────────────
        checkin = DailyCheckIn.objects.create(
            user             = user,
            tenant           = tenant or getattr(user, "tenant", None),
            date             = today,
            coins_earned     = coins_earned,
            xp_earned        = xp_earned,
            consecutive_days = consecutive,
            streak_shield_used = shield_used,
            note             = f"Day {consecutive} bonus!" if consecutive > 1 else "Welcome back!",
        )

        # ── Side effects ─────────────────────────────────────────────────────
        new_balance = CoinService.add(user, coins_earned, source="checkin", ref_id=str(checkin.pk))
        xp_result   = XPService.grant(user, xp_earned, source="checkin", ref_id=str(checkin.pk))

        logger.info(
            "CheckIn user=%s streak=%d coins=+%s xp=+%d level=%d→%d",
            user.pk, consecutive, coins_earned, xp_earned,
            xp_result["old_level"], xp_result["new_level"],
        )

        return {
            "checkin":         checkin,
            "coins_earned":    float(coins_earned),
            "xp_earned":       xp_earned,
            "consecutive_days": consecutive,
            "streak_shield_used": shield_used,
            "new_balance":     float(new_balance),
            "leveled_up":      xp_result["leveled_up"],
            "new_level":       xp_result["new_level"],
            "level_pct":       xp_result["level_pct"],
            "message":         checkin.note,
        }

    @staticmethod
    def stats(user) -> dict:
        """Aggregated check-in stats for a user."""
        qs = DailyCheckIn.objects.filter(user=user)
        latest = qs.order_by("-date").first()
        return {
            "total_checkins":  qs.count(),
            "current_streak":  latest.consecutive_days if latest else 0,
            "last_checkin":    latest.date.isoformat() if latest else None,
            "checked_in_today": latest.date == date.today() if latest else False,
        }

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _consume_streak_shield(user) -> bool:
        """Return True and decrement inventory if user has a streak shield."""
        try:
            from ..models.shop import UserInventory, ShopItem
            item = ShopItem.objects.filter(type="streak_shield", is_active=True).first()
            if not item:
                return False
            inv = UserInventory.objects.select_for_update().filter(
                user=user, item=item, quantity__gt=0
            ).first()
            if inv:
                inv.quantity -= 1
                inv.save(update_fields=["quantity"])
                return True
        except Exception as exc:
            logger.warning("Streak shield check failed: %s", exc)
        return False

    @staticmethod
    def _fire_streak_broken_signal(user, old_streak: int):
        """Fire the streak_broken_signal when a user's streak is broken."""
        try:
            from ..signals import streak_broken_signal
            streak_broken_signal.send(
                sender=user.__class__,
                user=user,
                old_streak=old_streak,
            )
            logger.info("Streak broken signal fired for user %s (old streak: %d)", user.pk, old_streak)
        except Exception as exc:
            logger.warning("Failed to fire streak_broken_signal for user %s: %s", user.pk, exc)
