"""
PROMOTION_MARKETING/loyalty_reward.py — Loyalty & Points Reward System
========================================================================
System:
  - Every purchase earns points (1 BDT = 1 point by default)
  - Points redeemable at checkout (100 points = 10 BDT discount)
  - Tier system: Silver → Gold → Platinum based on lifetime spend
  - Points expire after 365 days
  - Bonus points for reviews, referrals, first purchase
"""
from __future__ import annotations
import logging
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
POINTS_PER_BDT       = 1        # 1 BDT spent = 1 point
REDEMPTION_RATE      = 10       # 100 points = 10 BDT  (i.e. 1 point = 0.10 BDT)
POINTS_EXPIRY_DAYS   = 365
MIN_REDEEM_POINTS    = 100
MAX_REDEEM_PERCENT   = 20       # max 20% of order total can be paid with points

TIER_THRESHOLDS = {             # lifetime spend in BDT
    "silver":   Decimal("5000"),
    "gold":     Decimal("20000"),
    "platinum": Decimal("50000"),
}
TIER_BONUS_MULTIPLIERS = {
    "bronze":   Decimal("1.0"),
    "silver":   Decimal("1.25"),
    "gold":     Decimal("1.5"),
    "platinum": Decimal("2.0"),
}

# ── Models ────────────────────────────────────────────────────────────────────
class LoyaltyAccount(models.Model):
    tenant         = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                        related_name="loyalty_accounts_tenant")
    user           = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                           related_name="loyalty_account")
    points_balance = models.PositiveIntegerField(default=0)
    lifetime_points= models.PositiveIntegerField(default=0)
    lifetime_spend  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    tier            = models.CharField(max_length=10, default="bronze",
                                        choices=[("bronze","Bronze"),("silver","Silver"),
                                                 ("gold","Gold"),("platinum","Platinum")])
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_loyalty_account"

    def __str__(self):
        return f"{self.user.username} | {self.tier} | {self.points_balance} pts"

    @property
    def points_value_bdt(self) -> Decimal:
        return Decimal(self.points_balance) / REDEMPTION_RATE

    def get_tier(self) -> str:
        for tier, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if self.lifetime_spend >= threshold:
                return tier
        return "bronze"


class LoyaltyTransaction(models.Model):
    TYPE_CHOICES = [
        ("earn",     "Points Earned"),
        ("redeem",   "Points Redeemed"),
        ("expire",   "Points Expired"),
        ("bonus",    "Bonus Points"),
        ("referral", "Referral Bonus"),
        ("review",   "Review Bonus"),
        ("adjustment","Admin Adjustment"),
    ]
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="loyalty_transactions_tenant")
    account     = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE,
                                     related_name="transactions")
    tx_type     = models.CharField(max_length=15, choices=TYPE_CHOICES)
    points      = models.IntegerField()           # positive=earn, negative=redeem/expire
    balance_after= models.IntegerField(default=0)
    description  = models.CharField(max_length=255, blank=True)
    order_id     = models.IntegerField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_loyalty_transaction"
        ordering  = ["-created_at"]


# ── Service ───────────────────────────────────────────────────────────────────
class LoyaltyService:

    @classmethod
    @transaction.atomic
    def get_or_create_account(cls, user, tenant) -> LoyaltyAccount:
        acc, _ = LoyaltyAccount.objects.get_or_create(user=user, tenant=tenant)
        return acc

    @classmethod
    @transaction.atomic
    def earn_points(cls, user, tenant, order_amount: Decimal, order_id: int,
                    description: str = "") -> int:
        acc = cls.get_or_create_account(user, tenant)
        tier_multiplier = TIER_BONUS_MULTIPLIERS.get(acc.tier, Decimal("1.0"))
        base_points = int(order_amount * POINTS_PER_BDT)
        bonus_points = int(base_points * (tier_multiplier - 1))
        total_points = base_points + bonus_points

        acc.points_balance  += total_points
        acc.lifetime_points += total_points
        acc.lifetime_spend  += order_amount
        old_tier = acc.tier
        acc.tier = acc.get_tier()
        acc.save()

        expires_at = timezone.now() + timedelta(days=POINTS_EXPIRY_DAYS)
        LoyaltyTransaction.objects.create(
            tenant=tenant, account=acc, tx_type="earn",
            points=total_points, balance_after=acc.points_balance,
            description=description or f"Order #{order_id} | {base_points} base + {bonus_points} {acc.tier} bonus",
            order_id=order_id, expires_at=expires_at,
        )
        if old_tier != acc.tier:
            logger.info("[Loyalty] %s upgraded: %s → %s", user.username, old_tier, acc.tier)
        logger.info("[Loyalty] Earned %s pts for user %s (order #%s)", total_points, user.username, order_id)
        return total_points

    @classmethod
    @transaction.atomic
    def redeem_points(cls, user, tenant, points: int, order_id: int) -> Decimal:
        if points < MIN_REDEEM_POINTS:
            raise ValueError(f"Minimum redemption: {MIN_REDEEM_POINTS} points")
        acc = cls.get_or_create_account(user, tenant)
        if acc.points_balance < points:
            raise ValueError(f"Insufficient points: {acc.points_balance} available, {points} requested")

        discount_bdt = Decimal(points) / REDEMPTION_RATE
        acc.points_balance -= points
        acc.save(update_fields=["points_balance"])

        LoyaltyTransaction.objects.create(
            tenant=tenant, account=acc, tx_type="redeem",
            points=-points, balance_after=acc.points_balance,
            description=f"Redeemed {points} pts = {discount_bdt} BDT off Order #{order_id}",
            order_id=order_id,
        )
        logger.info("[Loyalty] Redeemed %s pts for %s BDT (user %s)", points, discount_bdt, user.username)
        return discount_bdt

    @classmethod
    def max_redeemable_points(cls, user, tenant, order_amount: Decimal) -> int:
        try:
            acc = LoyaltyAccount.objects.get(user=user, tenant=tenant)
        except LoyaltyAccount.DoesNotExist:
            return 0
        max_discount = order_amount * MAX_REDEEM_PERCENT / 100
        max_from_discount = int(max_discount * REDEMPTION_RATE)
        return min(acc.points_balance, max_from_discount)

    @classmethod
    @transaction.atomic
    def award_bonus(cls, user, tenant, points: int, reason: str, tx_type: str = "bonus"):
        acc = cls.get_or_create_account(user, tenant)
        acc.points_balance  += points
        acc.lifetime_points += points
        acc.save(update_fields=["points_balance", "lifetime_points"])
        LoyaltyTransaction.objects.create(
            tenant=tenant, account=acc, tx_type=tx_type,
            points=points, balance_after=acc.points_balance,
            description=reason,
            expires_at=timezone.now() + timedelta(days=POINTS_EXPIRY_DAYS),
        )

    @classmethod
    @transaction.atomic
    def expire_old_points(cls, tenant) -> int:
        now = timezone.now()
        expired_txns = LoyaltyTransaction.objects.filter(
            tenant=tenant, tx_type="earn", expires_at__lte=now, points__gt=0
        ).select_related("account")
        total_expired = 0
        for txn in expired_txns:
            acc = txn.account
            if acc.points_balance >= txn.points:
                acc.points_balance -= txn.points
                acc.save(update_fields=["points_balance"])
                LoyaltyTransaction.objects.create(
                    tenant=tenant, account=acc, tx_type="expire",
                    points=-txn.points, balance_after=acc.points_balance,
                    description=f"Expired points from {txn.created_at.strftime('%Y-%m-%d')}",
                )
                total_expired += txn.points
            txn.points = 0
            txn.save(update_fields=["points"])
        return total_expired

    @classmethod
    def get_summary(cls, user, tenant) -> dict:
        try:
            acc = LoyaltyAccount.objects.get(user=user, tenant=tenant)
            return {
                "points_balance":   acc.points_balance,
                "points_value_bdt": str(acc.points_value_bdt),
                "lifetime_points":  acc.lifetime_points,
                "lifetime_spend":   str(acc.lifetime_spend),
                "tier":             acc.tier,
                "next_tier":        cls._next_tier(acc),
            }
        except LoyaltyAccount.DoesNotExist:
            return {"points_balance": 0, "tier": "bronze"}

    @staticmethod
    def _next_tier(acc: LoyaltyAccount) -> dict:
        order = ["bronze","silver","gold","platinum"]
        idx = order.index(acc.tier)
        if idx == len(order) - 1:
            return {"name": "platinum", "spend_needed": 0}
        next_t = order[idx + 1]
        spend_needed = TIER_THRESHOLDS[next_t] - acc.lifetime_spend
        return {"name": next_t, "spend_needed": str(max(0, spend_needed))}

