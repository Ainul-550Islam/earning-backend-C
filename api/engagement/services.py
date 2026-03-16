# engagement/services.py
from django.db.models import Sum, F
from django.utils import timezone
from datetime import date, timedelta
import random
import logging
from .models import DailyCheckIn, SpinWheel, Leaderboard, LeaderboardReward

logger = logging.getLogger(__name__)


class EngagementService:

    @staticmethod
    def _add_coins(user, amount):
        """Safely add coins using F() to avoid race conditions"""
        try:
            type(user).objects.filter(pk=user.pk).update(
                coin_balance=F('coin_balance') + amount
            )
            user.refresh_from_db()
        except Exception:
            try:
                user.wallet.balance += amount
                user.wallet.save()
            except Exception as e:
                logger.error(f"Failed to add coins to user {user.pk}: {e}")

    @staticmethod
    def process_daily_checkin(user):
        today = date.today()
        if DailyCheckIn.objects.filter(user=user, date=today).exists():
            return None, "Already checked in today"

        yesterday = today - timedelta(days=1)
        yesterday_checkin = DailyCheckIn.objects.filter(user=user, date=yesterday).first()
        consecutive_days = (yesterday_checkin.consecutive_days + 1) if yesterday_checkin else 1

        coins = 5 * min(consecutive_days, 7)

        checkin = DailyCheckIn.objects.create(
            user=user,
            date=today,
            coins_earned=coins,
            consecutive_days=consecutive_days,
        )

        # FIX 1: F() expression prevents race condition on concurrent requests
        EngagementService._add_coins(user, coins)

        return checkin, f"Day {consecutive_days} bonus: {coins} coins!"

    @staticmethod
    def spin_wheel(user):
        if not SpinWheel.can_spin(user):
            return None, "Maximum spins reached for today"

        outcomes = [(1,50),(2,25),(5,15),(10,8),(50,2)]
        total_weight = sum(w for _, w in outcomes)
        rand = random.randint(1, total_weight)
        coins_won, cumulative = 1, 0
        for coins, weight in outcomes:
            cumulative += weight
            if rand <= cumulative:
                coins_won = coins
                break

        spin = SpinWheel.objects.create(user=user, coins_won=coins_won)

        # FIX 1: F() expression
        EngagementService._add_coins(user, coins_won)

        return spin, f"You won {coins_won} coins!"

    @staticmethod
    def update_leaderboard():
        today = date.today()
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # FIX 2: guarded import — won't crash if EarningTask app missing
        try:
            from api.models import EarningTask
            users_earnings = (
                EarningTask.objects
                .filter(completed_at__date=today)
                .values('user')
                .annotate(total_earned=Sum('coins_earned'))
                .order_by('-total_earned')
            )
        except ImportError:
            logger.warning("EarningTask not found — leaderboard skipped")
            return 0

        Leaderboard.objects.filter(date=today).delete()

        for idx, entry in enumerate(users_earnings[:100], 1):
            try:
                user = User.objects.get(id=entry['user'])
                Leaderboard.objects.create(
                    user=user, date=today,
                    total_coins_earned=entry['total_earned'],
                    rank=idx,
                )
            except User.DoesNotExist:
                continue  # FIX 3: skip deleted users

        return users_earnings.count()

    @staticmethod
    def distribute_daily_rewards():
        yesterday = date.today() - timedelta(days=1)
        for entry in Leaderboard.objects.filter(date=yesterday, rank__lte=10):
            reward = LeaderboardReward.objects.filter(rank=entry.rank).first()
            if reward:
                EngagementService._add_coins(entry.user, reward.reward_coins)
