# engagement/services/spin_service.py
import random
import logging
from decimal import Decimal
from django.db import transaction
from .coin_service import CoinService
from .xp_service import XPService
from ..models.spinwheel import SpinWheel
from ..constants import SPIN_OUTCOMES, XP_PER_SPIN
from ..exceptions import MaxSpinsReachedError

logger = logging.getLogger(__name__)


class SpinService:

    @classmethod
    @transaction.atomic
    def spin(cls, user, tenant=None) -> dict:
        """
        Execute one spin for `user`.
        Raises MaxSpinsReachedError if daily limit reached.
        Returns a rich result dict.
        """
        if not SpinWheel.can_spin(user):
            raise MaxSpinsReachedError()

        # Check for spin boost (doubles the outcome)
        boost_active = cls._is_boost_active(user)

        # ── Weighted random outcome ──────────────────────────────────────────
        coins_won, outcome_idx = cls._roll(boost_active)

        spin = SpinWheel.objects.create(
            user        = user,
            tenant      = tenant or getattr(user, "tenant", None),
            coins_won   = coins_won,
            xp_earned   = XP_PER_SPIN,
            outcome_idx = outcome_idx,
            is_boosted  = boost_active,
        )

        new_balance = CoinService.add(user, coins_won, source="spin", ref_id=str(spin.pk))
        XPService.grant(user, XP_PER_SPIN, source="spin", ref_id=str(spin.pk))

        remaining = SpinWheel.remaining_today(user)

        logger.info("Spin user=%s won=%s boost=%s remaining=%d", user.pk, coins_won, boost_active, remaining)

        return {
            "spin":           spin,
            "coins_won":      float(coins_won),
            "xp_earned":      XP_PER_SPIN,
            "is_boosted":     boost_active,
            "new_balance":    float(new_balance),
            "spins_remaining": remaining,
            "outcome_idx":    outcome_idx,
            "message":        f"You won {coins_won} coins{'  (2× boost!)' if boost_active else '!'}",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _roll(boosted: bool = False):
        """Return (coins_won, outcome_index)."""
        total_weight = sum(w for _, w in SPIN_OUTCOMES)
        r = random.randint(1, total_weight)
        cumulative = 0
        for idx, (coins, weight) in enumerate(SPIN_OUTCOMES):
            cumulative += weight
            if r <= cumulative:
                final = coins * 2 if boosted else coins
                return Decimal(str(final)), idx
        coins, _ = SPIN_OUTCOMES[-1]
        return Decimal(str(coins)), len(SPIN_OUTCOMES) - 1

    @staticmethod
    def _is_boost_active(user) -> bool:
        """Check if user has an active spin boost item in inventory."""
        try:
            from django.utils import timezone
            from ..models.shop import UserInventory, ShopItem
            item = ShopItem.objects.filter(type="spin_boost", is_active=True).first()
            if not item:
                return False
            inv = UserInventory.objects.filter(
                user=user, item=item, quantity__gt=0,
            ).exclude(expires_at__lt=timezone.now()).first()
            return inv is not None
        except Exception as exc:
            logger.warning("Spin boost check failed for user %s: %s", user.pk, exc)
            return False

    @staticmethod
    def history(user, limit: int = 20) -> list:
        return list(
            SpinWheel.objects.filter(user=user).order_by("-spun_at")[:limit]
            .values("coins_won", "spun_at", "is_boosted", "outcome_idx")
        )
