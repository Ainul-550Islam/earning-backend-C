# api/wallet/reward_tiers.py
"""
RewardTier & PrizePool — CPALead-style tiered rewards and prize pool system.

RewardTier:  User reaches earning milestone → unlocks reward (bonus BDT, badge, multiplier).
PrizePool:   Time-boxed competition. Top earners split a pool at deadline.

Flow:
  EarningService.credit() → RewardTierService.check_milestones(wallet)
    → if milestone crossed → credit bonus + fire BonusGranted event
  PrizePoolService.tick() (Celery beat) → check deadline → distribute pool
"""
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger("wallet.reward_tiers")


# ════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════

class RewardTier(models.Model):
    """
    A milestone-based reward. When a user's lifetime earnings
    cross `threshold_amount`, they receive `bonus_amount` BDT
    plus an optional earn-rate multiplier for the next N days.
    """

    REWARD_TYPE_BONUS      = "bonus"
    REWARD_TYPE_MULTIPLIER = "multiplier"
    REWARD_TYPE_BADGE      = "badge"
    REWARD_TYPE_CHOICES    = [
        (REWARD_TYPE_BONUS,      "Cash Bonus"),
        (REWARD_TYPE_MULTIPLIER, "Earn Multiplier"),
        (REWARD_TYPE_BADGE,      "Badge / Title"),
    ]

    tenant           = models.ForeignKey(
        "tenants.Tenant", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reward_tiers",
    )
    name             = models.CharField(max_length=120, unique=True)
    description      = models.TextField(blank=True)
    reward_type      = models.CharField(
        max_length=12, choices=REWARD_TYPE_CHOICES, default=REWARD_TYPE_BONUS,
    )
    threshold_amount = models.DecimalField(
        max_digits=20, decimal_places=8,
        help_text="Lifetime total_earned required to unlock this tier (BDT)",
    )
    bonus_amount     = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0"),
        help_text="One-time BDT bonus credited on milestone",
    )
    multiplier       = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("1.0000"),
        help_text="Earn multiplier applied for multiplier_days after unlock",
    )
    multiplier_days  = models.PositiveSmallIntegerField(
        default=0, help_text="How many days the multiplier lasts (0 = permanent)",
    )
    badge_label      = models.CharField(max_length=60, blank=True)
    is_active        = models.BooleanField(default=True, db_index=True)
    sort_order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_rewardtier"
        ordering  = ["threshold_amount"]

    def __str__(self) -> str:
        return f"{self.name} | ≥{self.threshold_amount} BDT → +{self.bonus_amount}"


class UserRewardTier(models.Model):
    """Records which RewardTiers a user has already unlocked (prevents double-credit)."""

    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="unlocked_reward_tiers",
    )
    tier       = models.ForeignKey(
        RewardTier, on_delete=models.CASCADE, related_name="user_unlocks",
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)
    txn_id      = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label    = "wallet"
        db_table     = "wallet_userrewardtier"
        unique_together = [("user", "tier")]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.tier.name}"


class PrizePool(models.Model):
    """
    Time-boxed competition. Users earn points by completing offers.
    At deadline, the pool is split among top N earners.

    Distribution strategies:
      rank_based  → fixed BDT per rank (1st=500, 2nd=300, 3rd=200, ...)
      proportional → split proportionally by points earned
      winner_takes → 100% to #1
    """

    STRATEGY_RANK_BASED    = "rank_based"
    STRATEGY_PROPORTIONAL  = "proportional"
    STRATEGY_WINNER_TAKES  = "winner_takes"
    STRATEGY_CHOICES       = [
        (STRATEGY_RANK_BASED,   "Rank-Based Prizes"),
        (STRATEGY_PROPORTIONAL, "Proportional Split"),
        (STRATEGY_WINNER_TAKES, "Winner Takes All"),
    ]

    STATUS_ACTIVE     = "active"
    STATUS_DISTRIBUTING = "distributing"
    STATUS_COMPLETED  = "completed"
    STATUS_CANCELLED  = "cancelled"
    STATUS_CHOICES    = [
        (STATUS_ACTIVE,       "Active"),
        (STATUS_DISTRIBUTING, "Distributing"),
        (STATUS_COMPLETED,    "Completed"),
        (STATUS_CANCELLED,    "Cancelled"),
    ]

    tenant           = models.ForeignKey(
        "tenants.Tenant", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="prize_pools",
    )
    pool_id          = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title            = models.CharField(max_length=200)
    description      = models.TextField(blank=True)

    total_prize      = models.DecimalField(
        max_digits=20, decimal_places=8,
        help_text="Total BDT in the prize pool",
    )
    currency         = models.CharField(max_length=10, default="BDT")

    strategy         = models.CharField(
        max_length=14, choices=STRATEGY_CHOICES, default=STRATEGY_RANK_BASED,
    )
    rank_prizes      = models.JSONField(
        default=list,
        help_text='For rank_based: [{"rank":1,"amount":"500"}, {"rank":2,"amount":"300"}]',
    )
    max_winners      = models.PositiveSmallIntegerField(
        default=10, help_text="Top N users receive prizes",
    )

    starts_at        = models.DateTimeField(default=timezone.now)
    ends_at          = models.DateTimeField(db_index=True)
    distributed_at   = models.DateTimeField(null=True, blank=True)

    status           = models.CharField(
        max_length=14, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True,
    )
    total_participants = models.PositiveIntegerField(default=0)

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "wallet"
        db_table  = "wallet_prizepool"
        ordering  = ["-ends_at"]
        indexes   = [
            models.Index(fields=["status", "ends_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} | {self.total_prize} {self.currency} | {self.status}"

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return self.status == self.STATUS_ACTIVE and self.starts_at <= now <= self.ends_at


class PrizePoolEntry(models.Model):
    """Leaderboard entry: user's points earned during a prize pool period."""

    pool       = models.ForeignKey(PrizePool, on_delete=models.CASCADE, related_name="entries")
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="prize_entries",
    )
    wallet     = models.ForeignKey(
        "wallet.Wallet", on_delete=models.SET_NULL, null=True, related_name="prize_entries",
    )
    points     = models.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    rank       = models.PositiveIntegerField(null=True, blank=True)
    prize_won  = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0"),
    )
    txn_id     = models.CharField(max_length=64, blank=True)
    joined_at  = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label    = "wallet"
        db_table     = "wallet_prizepoolentry"
        unique_together = [("pool", "user")]
        ordering     = ["-points"]
        indexes      = [
            models.Index(fields=["pool", "-points"]),
            models.Index(fields=["user", "pool"]),
        ]

    def __str__(self) -> str:
        return f"Pool={self.pool_id} User={self.user_id} pts={self.points}"


# ════════════════════════════════════════════════════════════════
# SERVICES
# ════════════════════════════════════════════════════════════════

class RewardTierService:
    """Check and award RewardTier milestones after every credit."""

    @classmethod
    def check_milestones(cls, wallet) -> list:
        """
        Called after a credit. Checks if user has crossed any new
        RewardTier thresholds. Credits bonus and records unlock.

        Returns list of newly unlocked tier names.
        """
        newly_unlocked = []
        user = wallet.user

        already_unlocked = set(
            UserRewardTier.objects.filter(user=user).values_list("tier_id", flat=True)
        )

        eligible = RewardTier.objects.filter(
            is_active=True,
            threshold_amount__lte=wallet.total_earned,
        ).exclude(id__in=already_unlocked).order_by("threshold_amount")

        for tier in eligible:
            with transaction.atomic():
                # Re-check inside lock to prevent race
                if UserRewardTier.objects.filter(user=user, tier=tier).exists():
                    continue

                # Record unlock first
                unlock = UserRewardTier.objects.create(user=user, tier=tier)

                # Credit bonus if applicable
                if tier.bonus_amount > Decimal("0"):
                    try:
                        from .services.core.WalletService import WalletService
                        from .choices import TransactionType
                        txn = WalletService.credit(
                            wallet=wallet,
                            amount=tier.bonus_amount,
                            txn_type=TransactionType.BONUS,
                            description=f"Reward tier unlocked: {tier.name}",
                            reference_id=str(tier.pk),
                            reference_type="reward_tier",
                            skip_multipliers=True,
                        )
                        unlock.txn_id = str(txn.txn_id)
                        unlock.save(update_fields=["txn_id"])
                    except Exception as e:
                        logger.error(f"RewardTier bonus credit failed tier={tier.pk}: {e}")

            newly_unlocked.append(tier.name)
            logger.info(
                f"RewardTier unlocked: user={user.pk} tier={tier.name} "
                f"bonus={tier.bonus_amount}"
            )

        return newly_unlocked


class PrizePoolService:
    """Manage prize pool lifecycle: entry, leaderboard, distribution."""

    @staticmethod
    def add_points(pool_id: str, user, wallet, points: Decimal) -> None:
        """Add points to user's entry in a live prize pool (upsert)."""
        try:
            pool = PrizePool.objects.get(pool_id=pool_id, status=PrizePool.STATUS_ACTIVE)
        except PrizePool.DoesNotExist:
            return

        if not pool.is_live:
            return

        entry, created = PrizePoolEntry.objects.get_or_create(
            pool=pool, user=user,
            defaults={"wallet": wallet, "points": Decimal("0")},
        )
        PrizePoolEntry.objects.filter(pk=entry.pk).update(
            points=models.F("points") + points
        )
        if created:
            PrizePool.objects.filter(pk=pool.pk).update(
                total_participants=models.F("total_participants") + 1
            )

    @classmethod
    def distribute(cls, pool_id: str) -> dict:
        """
        Distribute prize pool to top earners. Called by Celery beat.
        Returns {"distributed": int, "total_paid": str}
        """
        try:
            pool = PrizePool.objects.select_for_update().get(
                pool_id=pool_id, status=PrizePool.STATUS_ACTIVE
            )
        except PrizePool.DoesNotExist:
            return {"error": "Pool not found or not active"}

        with transaction.atomic():
            pool.status = PrizePool.STATUS_DISTRIBUTING
            pool.save(update_fields=["status"])

            top_entries = (
                PrizePoolEntry.objects
                .filter(pool=pool)
                .order_by("-points")
                .select_related("wallet")[:pool.max_winners]
            )

            total_paid = Decimal("0")
            distributed = 0

            for rank_idx, entry in enumerate(top_entries, start=1):
                prize = cls._calc_prize(pool, rank_idx, entry.points, top_entries)
                if prize <= Decimal("0") or not entry.wallet:
                    continue

                try:
                    from .services.core.WalletService import WalletService
                    from .choices import TransactionType
                    txn = WalletService.credit(
                        wallet=entry.wallet,
                        amount=prize,
                        txn_type=TransactionType.BONUS,
                        description=f"Prize pool: {pool.title} (Rank #{rank_idx})",
                        reference_id=str(pool.pool_id),
                        reference_type="prize_pool",
                        skip_multipliers=True,
                    )
                    PrizePoolEntry.objects.filter(pk=entry.pk).update(
                        rank=rank_idx,
                        prize_won=prize,
                        txn_id=str(txn.txn_id),
                    )
                    total_paid += prize
                    distributed += 1
                except Exception as e:
                    logger.error(f"Prize credit failed pool={pool_id} rank={rank_idx}: {e}")

            pool.status        = PrizePool.STATUS_COMPLETED
            pool.distributed_at = timezone.now()
            pool.save(update_fields=["status", "distributed_at"])

        logger.info(f"PrizePool distributed: pool={pool_id} winners={distributed} total={total_paid}")
        return {"distributed": distributed, "total_paid": str(total_paid)}

    @staticmethod
    def _calc_prize(pool: PrizePool, rank: int, points: Decimal, all_entries) -> Decimal:
        """Calculate prize for a given rank based on pool strategy."""
        if pool.strategy == PrizePool.STRATEGY_RANK_BASED:
            for rp in pool.rank_prizes:
                if rp.get("rank") == rank:
                    return Decimal(str(rp.get("amount", "0")))
            return Decimal("0")

        if pool.strategy == PrizePool.STRATEGY_WINNER_TAKES_ALL:
            return pool.total_prize if rank == 1 else Decimal("0")

        # Proportional
        total_pts = sum(e.points for e in all_entries) or Decimal("1")
        return (points / total_pts * pool.total_prize).quantize(Decimal("0.00000001"))

    @staticmethod
    def leaderboard(pool_id: str, limit: int = 20) -> list:
        """Return current leaderboard for a pool."""
        return list(
            PrizePoolEntry.objects
            .filter(pool__pool_id=pool_id)
            .order_by("-points")
            .values("user_id", "points", "rank", "prize_won")[:limit]
        )
