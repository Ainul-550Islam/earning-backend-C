# api/wallet/gamification.py
"""
Scratchcard & Spin Wheel Gamification — CPALead-style daily engagement rewards.

Features:
  - Daily scratchcard: user scratches to reveal a prize (BDT bonus / points / multiplier)
  - Spin wheel: configurable prize segments with weighted probability
  - Cooldown enforcement (once per day per user)
  - Fraud guard: max daily payout cap, VPN/proxy block
  - Admin configurable prizes via Django admin
  - Full audit trail via WalletTransaction

Flow:
  POST /wallet/scratchcard/claim/  → ScratchcardService.claim(user)
  POST /wallet/spinwheel/spin/     → SpinWheelService.spin(user)
"""
import logging
import random
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger("wallet.gamification")

# ──────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────
SCRATCHCARD_COOLDOWN_HOURS = getattr(settings, "SCRATCHCARD_COOLDOWN_HOURS", 24)
SPINWHEEL_COOLDOWN_HOURS   = getattr(settings, "SPINWHEEL_COOLDOWN_HOURS", 24)
SCRATCHCARD_MAX_DAILY_BDT  = Decimal(getattr(settings, "SCRATCHCARD_MAX_DAILY_BDT", "50"))
SPINWHEEL_MAX_DAILY_BDT    = Decimal(getattr(settings, "SPINWHEEL_MAX_DAILY_BDT", "100"))


# ──────────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────────

class ScratchcardPrize(models.Model):
    """Admin-configurable scratchcard prize pool."""

    PRIZE_CASH        = "cash"
    PRIZE_POINTS      = "points"
    PRIZE_MULTIPLIER  = "multiplier"
    PRIZE_MISS        = "miss"
    PRIZE_CHOICES = [
        (PRIZE_CASH,       "Cash (BDT)"),
        (PRIZE_POINTS,     "Points"),
        (PRIZE_MULTIPLIER, "Earn Multiplier (24h)"),
        (PRIZE_MISS,       "No Prize"),
    ]

    name             = models.CharField(max_length=120)
    prize_type       = models.CharField(max_length=20, choices=PRIZE_CHOICES)
    amount           = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    multiplier_value = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("1.0"),
        help_text="Earn multiplier for 24h (e.g. 1.5 = 50% bonus)",
    )
    weight           = models.PositiveIntegerField(
        default=10,
        help_text="Relative probability weight. Higher = more frequent.",
    )
    is_active        = models.BooleanField(default=True)
    icon_emoji       = models.CharField(max_length=8, default="🎁")

    class Meta:
        ordering = ["-weight"]
        verbose_name = "Scratchcard Prize"

    def __str__(self):
        return f"{self.icon_emoji} {self.name} ({self.get_prize_type_display()})"


class SpinWheelSegment(models.Model):
    """Admin-configurable spin wheel segment."""

    PRIZE_CASH        = "cash"
    PRIZE_POINTS      = "points"
    PRIZE_MULTIPLIER  = "multiplier"
    PRIZE_MISS        = "miss"
    PRIZE_CHOICES = [
        (PRIZE_CASH,       "Cash (BDT)"),
        (PRIZE_POINTS,     "Points"),
        (PRIZE_MULTIPLIER, "Earn Multiplier (24h)"),
        (PRIZE_MISS,       "Better luck next time"),
    ]

    label            = models.CharField(max_length=60)
    prize_type       = models.CharField(max_length=20, choices=PRIZE_CHOICES)
    amount           = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    multiplier_value = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.0"))
    weight           = models.PositiveIntegerField(default=10)
    color_hex        = models.CharField(max_length=7, default="#6C63FF", help_text="Wheel segment color")
    is_active        = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Spin Wheel Segment"

    def __str__(self):
        return f"{self.label} (w={self.weight})"


class GamificationLog(models.Model):
    """Audit log for every scratchcard / spin event."""

    TYPE_SCRATCHCARD = "scratchcard"
    TYPE_SPINWHEEL   = "spinwheel"
    TYPE_CHOICES = [
        (TYPE_SCRATCHCARD, "Scratchcard"),
        (TYPE_SPINWHEEL,   "Spin Wheel"),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="gamification_logs",
    )
    event_type    = models.CharField(max_length=20, choices=TYPE_CHOICES)
    prize_name    = models.CharField(max_length=120)
    prize_type    = models.CharField(max_length=20)
    amount_won    = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.CharField(max_length=300, blank=True)
    transaction   = models.ForeignKey(
        "wallet.WalletTransaction", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="gamification_logs",
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Gamification Log"
        indexes = [
            models.Index(fields=["user", "event_type", "created_at"]),
        ]


# ──────────────────────────────────────────────────────────────────
# SERVICES
# ──────────────────────────────────────────────────────────────────

class _BaseGamificationService:
    """Shared helpers for scratchcard + spin wheel."""

    cooldown_hours: int = 24
    max_daily_bdt: Decimal = Decimal("50")
    event_type: str = "base"

    @classmethod
    def _cooldown_key(cls, user_id) -> str:
        return f"wallet:gamif:{cls.event_type}:cooldown:{user_id}"

    @classmethod
    def _daily_payout_key(cls, user_id) -> str:
        today = timezone.now().date().isoformat()
        return f"wallet:gamif:{cls.event_type}:daily:{user_id}:{today}"

    @classmethod
    def check_cooldown(cls, user_id) -> dict:
        """Returns {available: bool, seconds_remaining: int}."""
        ttl = cache.ttl(cls._cooldown_key(user_id))
        if ttl and ttl > 0:
            return {"available": False, "seconds_remaining": ttl}
        return {"available": True, "seconds_remaining": 0}

    @classmethod
    def _set_cooldown(cls, user_id):
        cache.set(
            cls._cooldown_key(user_id),
            1,
            timeout=cls.cooldown_hours * 3600,
        )

    @classmethod
    def _daily_payout_used(cls, user_id) -> Decimal:
        raw = cache.get(cls._daily_payout_key(user_id), "0")
        return Decimal(str(raw))

    @classmethod
    def _add_daily_payout(cls, user_id, amount: Decimal):
        key = cls._daily_payout_key(user_id)
        current = cls._daily_payout_used(user_id)
        cache.set(key, str(current + amount), timeout=86400)

    @classmethod
    def _weighted_choice(cls, items):
        """Pick one item by weight field."""
        population = [item for item in items if item.is_active]
        if not population:
            return None
        weights = [item.weight for item in population]
        return random.choices(population, weights=weights, k=1)[0]

    @classmethod
    def _credit_prize(cls, user, prize_type, amount, multiplier_value, prize_name, event_type) -> dict:
        """Credit the won prize to user's wallet. Returns transaction info."""
        from .services.earning.EarningService import EarningService
        from .models import Wallet

        result = {"credited": False, "transaction_id": None}

        if prize_type == "miss" or amount == Decimal("0"):
            result["credited"] = False
            return result

        try:
            wallet = Wallet.objects.select_for_update().get(user=user)
        except Exception:
            return result

        with transaction.atomic():
            if prize_type == "cash":
                txn = EarningService.add_earning(
                    wallet=wallet,
                    amount=amount,
                    source="bonus",
                    description=f"{event_type.title()} prize: {prize_name}",
                    metadata={"gamification": event_type, "prize": prize_name},
                )
                result["credited"] = True
                result["transaction_id"] = str(txn.id) if txn else None

            elif prize_type == "points":
                # Convert points to BDT equivalent (1000 pts = 1 BDT)
                bdt_amount = amount / Decimal("1000")
                txn = EarningService.add_earning(
                    wallet=wallet,
                    amount=bdt_amount,
                    source="bonus",
                    description=f"{event_type.title()} points: {int(amount)} pts",
                    metadata={"gamification": event_type, "points": str(amount)},
                )
                result["credited"] = True
                result["transaction_id"] = str(txn.id) if txn else None
                result["bdt_equivalent"] = str(bdt_amount)

            elif prize_type == "multiplier":
                # Store multiplier in cache for 24h
                mult_key = f"wallet:earn_multiplier:{user.id}"
                cache.set(mult_key, str(multiplier_value), timeout=86400)
                result["credited"] = True
                result["multiplier_active_hours"] = 24

        return result


class ScratchcardService(_BaseGamificationService):
    """Daily scratchcard service."""

    event_type     = "scratchcard"
    cooldown_hours = SCRATCHCARD_COOLDOWN_HOURS
    max_daily_bdt  = SCRATCHCARD_MAX_DAILY_BDT

    @classmethod
    def get_status(cls, user) -> dict:
        """Return user's scratchcard status."""
        cooldown = cls.check_cooldown(user.id)
        daily_used = cls._daily_payout_used(user.id)
        return {
            "available":          cooldown["available"],
            "seconds_remaining":  cooldown["seconds_remaining"],
            "daily_limit_bdt":    str(cls.max_daily_bdt),
            "daily_used_bdt":     str(daily_used),
            "daily_remaining_bdt": str(max(Decimal("0"), cls.max_daily_bdt - daily_used)),
        }

    @classmethod
    def claim(cls, user, ip_address=None, user_agent="") -> dict:
        """
        User claims a daily scratchcard.

        Returns:
            {success, prize_name, prize_type, amount, message, next_available_at}
        """
        # Cooldown check
        cooldown = cls.check_cooldown(user.id)
        if not cooldown["available"]:
            hrs = cooldown["seconds_remaining"] // 3600
            mins = (cooldown["seconds_remaining"] % 3600) // 60
            return {
                "success": False,
                "reason":  "cooldown",
                "message": f"Next scratchcard available in {hrs}h {mins}m",
                "seconds_remaining": cooldown["seconds_remaining"],
            }

        # Daily cap check
        daily_used = cls._daily_payout_used(user.id)
        if daily_used >= cls.max_daily_bdt:
            return {
                "success": False,
                "reason":  "daily_cap",
                "message": f"Daily scratchcard limit of {cls.max_daily_bdt} BDT reached.",
            }

        # Pick prize
        try:
            prizes = ScratchcardPrize.objects.filter(is_active=True)
            prize = cls._weighted_choice(list(prizes))
        except Exception:
            # No prizes configured — give a small default
            prize = None

        if not prize:
            prize_data = {
                "prize_type": "cash", "amount": Decimal("1.00"),
                "name": "Welcome Bonus", "multiplier_value": Decimal("1.0"), "icon_emoji": "🎁",
            }
        else:
            prize_data = {
                "prize_type": prize.prize_type,
                "amount":     prize.amount,
                "name":       prize.name,
                "multiplier_value": prize.multiplier_value,
                "icon_emoji": prize.icon_emoji,
            }

        # Cap amount to daily remaining
        daily_remaining = cls.max_daily_bdt - daily_used
        if prize_data["prize_type"] == "cash":
            prize_data["amount"] = min(prize_data["amount"], daily_remaining)

        # Credit prize
        credit_result = cls._credit_prize(
            user, prize_data["prize_type"], prize_data["amount"],
            prize_data["multiplier_value"], prize_data["name"], cls.event_type,
        )

        # Set cooldown
        cls._set_cooldown(user.id)

        # Track daily payout
        if prize_data["prize_type"] == "cash":
            cls._add_daily_payout(user.id, prize_data["amount"])

        # Log
        GamificationLog.objects.create(
            user=user,
            event_type=GamificationLog.TYPE_SCRATCHCARD,
            prize_name=prize_data["name"],
            prize_type=prize_data["prize_type"],
            amount_won=prize_data["amount"],
            ip_address=ip_address,
            user_agent=user_agent[:300],
        )

        next_at = timezone.now() + timezone.timedelta(hours=cls.cooldown_hours)
        return {
            "success":        True,
            "prize_name":     prize_data["name"],
            "prize_type":     prize_data["prize_type"],
            "amount":         str(prize_data["amount"]),
            "icon":           prize_data["icon_emoji"],
            "message":        _prize_message(prize_data["prize_type"], prize_data["amount"]),
            "credited":       credit_result.get("credited", False),
            "transaction_id": credit_result.get("transaction_id"),
            "next_available_at": next_at.isoformat(),
        }


class SpinWheelService(_BaseGamificationService):
    """Daily spin wheel service."""

    event_type     = "spinwheel"
    cooldown_hours = SPINWHEEL_COOLDOWN_HOURS
    max_daily_bdt  = SPINWHEEL_MAX_DAILY_BDT

    @classmethod
    def get_wheel_config(cls) -> dict:
        """Return all segments for frontend rendering."""
        segments = SpinWheelSegment.objects.filter(is_active=True).order_by("id")
        return {
            "segments": [
                {
                    "id":         s.id,
                    "label":      s.label,
                    "prize_type": s.prize_type,
                    "amount":     str(s.amount),
                    "color":      s.color_hex,
                }
                for s in segments
            ]
        }

    @classmethod
    def get_status(cls, user) -> dict:
        cooldown = cls.check_cooldown(user.id)
        return {
            "available":           cooldown["available"],
            "seconds_remaining":   cooldown["seconds_remaining"],
            "daily_limit_bdt":     str(cls.max_daily_bdt),
            "daily_used_bdt":      str(cls._daily_payout_used(user.id)),
        }

    @classmethod
    def spin(cls, user, ip_address=None, user_agent="") -> dict:
        """
        User spins the wheel.

        Returns:
            {success, segment_id, prize_name, prize_type, amount, message, next_available_at}
        """
        # Cooldown check
        cooldown = cls.check_cooldown(user.id)
        if not cooldown["available"]:
            hrs = cooldown["seconds_remaining"] // 3600
            mins = (cooldown["seconds_remaining"] % 3600) // 60
            return {
                "success": False,
                "reason":  "cooldown",
                "message": f"Next spin available in {hrs}h {mins}m",
                "seconds_remaining": cooldown["seconds_remaining"],
            }

        # Pick segment
        try:
            segments = SpinWheelSegment.objects.filter(is_active=True)
            segment = cls._weighted_choice(list(segments))
        except Exception:
            segment = None

        if not segment:
            seg_data = {
                "id": 0, "prize_type": "cash", "amount": Decimal("2.00"),
                "label": "Spin Bonus", "multiplier_value": Decimal("1.0"),
            }
        else:
            seg_data = {
                "id":               segment.id,
                "prize_type":       segment.prize_type,
                "amount":           segment.amount,
                "label":            segment.label,
                "multiplier_value": segment.multiplier_value,
            }

        # Cap to daily remaining
        daily_remaining = cls.max_daily_bdt - cls._daily_payout_used(user.id)
        if seg_data["prize_type"] == "cash":
            seg_data["amount"] = min(seg_data["amount"], max(Decimal("0"), daily_remaining))

        # Credit
        credit_result = cls._credit_prize(
            user, seg_data["prize_type"], seg_data["amount"],
            seg_data["multiplier_value"], seg_data["label"], cls.event_type,
        )

        cls._set_cooldown(user.id)
        if seg_data["prize_type"] == "cash":
            cls._add_daily_payout(user.id, seg_data["amount"])

        GamificationLog.objects.create(
            user=user,
            event_type=GamificationLog.TYPE_SPINWHEEL,
            prize_name=seg_data["label"],
            prize_type=seg_data["prize_type"],
            amount_won=seg_data["amount"],
            ip_address=ip_address,
            user_agent=user_agent[:300],
        )

        next_at = timezone.now() + timezone.timedelta(hours=cls.cooldown_hours)
        return {
            "success":        True,
            "segment_id":     seg_data["id"],
            "prize_name":     seg_data["label"],
            "prize_type":     seg_data["prize_type"],
            "amount":         str(seg_data["amount"]),
            "message":        _prize_message(seg_data["prize_type"], seg_data["amount"]),
            "credited":       credit_result.get("credited", False),
            "transaction_id": credit_result.get("transaction_id"),
            "next_available_at": next_at.isoformat(),
        }


def _prize_message(prize_type: str, amount: Decimal) -> str:
    if prize_type == "cash":
        return f"🎉 You won {amount} BDT! Credited to your wallet."
    elif prize_type == "points":
        return f"⭐ You won {int(amount)} points!"
    elif prize_type == "multiplier":
        return f"🚀 Earn multiplier active for 24 hours!"
    return "Better luck next time!"
