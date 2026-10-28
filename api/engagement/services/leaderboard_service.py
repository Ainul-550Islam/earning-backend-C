# engagement/services/leaderboard_service.py
import logging
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Sum
from .coin_service import CoinService
from ..models.leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason

logger = logging.getLogger(__name__)

LEADERBOARD_SIZE = 100


class LeaderboardService:

    # ── Rebuild daily snapshot ────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def rebuild_daily(cls, target_date=None, tenant=None) -> int:
        """
        Delete and rebuild the leaderboard snapshot for `target_date`.
        Returns number of entries written.
        Called by Celery beat task.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        target_date = target_date or date.today()

        # Try EarningTask first (existing pattern), fallback to coin transactions
        entries = cls._fetch_daily_earnings(target_date, tenant)
        if not entries:
            return 0

        Leaderboard.objects.filter(date=target_date, tenant=tenant).delete()

        rows = []
        for idx, entry in enumerate(entries[:LEADERBOARD_SIZE], 1):
            try:
                user = User.objects.get(pk=entry["user"])
                rows.append(Leaderboard(
                    user               = user,
                    tenant             = tenant,
                    date               = target_date,
                    total_coins_earned = entry["total_earned"],
                    rank               = idx,
                ))
            except User.DoesNotExist:
                continue

        Leaderboard.objects.bulk_create(rows, ignore_conflicts=True)
        logger.info("Leaderboard rebuilt for %s: %d entries", target_date, len(rows))
        return len(rows)

    # ── Distribute rewards ────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def distribute_rewards(cls, target_date=None, tenant=None) -> int:
        """
        Distribute leaderboard rewards for yesterday.
        Returns number of users rewarded.
        """
        target_date   = target_date or (date.today() - timedelta(days=1))
        entries        = Leaderboard.objects.filter(
            date=target_date,
            rank__lte=10,
            reward_distributed=False,
            tenant=tenant,
        )
        rewarded = 0
        for entry in entries:
            reward = LeaderboardReward.objects.filter(
                rank=entry.rank,
                season_type="daily",
                tenant=tenant,
            ).first()
            if reward:
                CoinService.add(entry.user, reward.reward_coins, source="leaderboard_reward",
                                ref_id=str(entry.pk))
                entry.reward_distributed = True
                entry.save(update_fields=["reward_distributed"])
                rewarded += 1

        logger.info("Leaderboard rewards distributed for %s: %d users", target_date, rewarded)
        return rewarded

    # ── Public read helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_leaderboard(target_date=None, tenant=None, limit: int = 50) -> list:
        target_date = target_date or date.today()
        return list(
            Leaderboard.objects.filter(date=target_date, tenant=tenant)
            .select_related("user")
            .order_by("rank")[:limit]
        )

    @staticmethod
    def get_user_rank(user, target_date=None, tenant=None):
        target_date = target_date or date.today()
        try:
            return Leaderboard.objects.get(user=user, date=target_date, tenant=tenant).rank
        except Leaderboard.DoesNotExist:
            return None

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fetch_daily_earnings(target_date, tenant):
        try:
            from api.models import EarningTask
            qs = EarningTask.objects.filter(completed_at__date=target_date)
            if tenant:
                qs = qs.filter(tenant=tenant)
            return list(
                qs.values("user")
                .annotate(total_earned=Sum("coins_earned"))
                .order_by("-total_earned")
            )
        except ImportError:
            pass

        # Fallback: sum SpinWheel + DailyCheckIn coins for the day
        from ..models.spinwheel import SpinWheel
        from ..models.checkin import DailyCheckIn
        from django.contrib.auth import get_user_model
        from django.db.models import Value
        from django.db.models.functions import Coalesce

        User = get_user_model()
        user_ids = set(
            SpinWheel.objects.filter(spun_at__date=target_date).values_list("user_id", flat=True)
        ) | set(
            DailyCheckIn.objects.filter(date=target_date).values_list("user_id", flat=True)
        )

        results = []
        for uid in user_ids:
            spin_coins = SpinWheel.objects.filter(
                user_id=uid, spun_at__date=target_date
            ).aggregate(s=Sum("coins_won"))["s"] or 0
            ci_coins = DailyCheckIn.objects.filter(
                user_id=uid, date=target_date
            ).aggregate(s=Sum("coins_earned"))["s"] or 0
            results.append({"user": uid, "total_earned": spin_coins + ci_coins})

        results.sort(key=lambda x: x["total_earned"], reverse=True)
        return results
