# api/cms/services_new/LeaderboardService.py
"""
Leaderboard + Streak Service — Professional grade.
bulk_update for rank refresh, atomic streak update, cache-backed.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import F, Q
from django.core.cache import cache

logger = logging.getLogger(__name__)


class LeaderboardService:

    # ── Score Update ──────────────────────────────────────────────

    @staticmethod
    def update_score(user, amount: Decimal,
                     category: str = 'earnings',
                     period_type: str = 'weekly') -> bool:
        """Add to user's score. Called after every reward. Atomic."""
        from api.cms.models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry
        try:
            period = LeaderboardPeriod.get_active(period_type)
            if not period:
                period = LeaderboardService._create_current_period(period_type)

            entry, _ = LeaderboardEntry.objects.get_or_create(
                period=period, user=user, category=category,
                defaults={'score': 0, 'score_usd': 0, 'score_coins': 0},
            )

            if category == 'earnings':
                LeaderboardEntry.objects.filter(pk=entry.pk).update(
                    score=F('score') + amount,
                    score_usd=F('score_usd') + amount,
                )
            elif category == 'coins':
                LeaderboardEntry.objects.filter(pk=entry.pk).update(
                    score=F('score') + amount,
                    score_coins=F('score_coins') + amount,
                )
            elif category == 'offers':
                LeaderboardEntry.objects.filter(pk=entry.pk).update(
                    score=F('score') + 1,
                    offers_count=F('offers_count') + 1,
                )

            # Invalidate leaderboard cache
            cache.delete(f"leaderboard_top_{period_type}_{category}")
            return True

        except Exception as e:
            logger.error(f"[Leaderboard] update_score error: {e}")
            return False

    @staticmethod
    def _create_current_period(period_type: str):
        from api.cms.models_new.leaderboard import LeaderboardPeriod
        import datetime
        today = timezone.now().date()
        if period_type == 'daily':
            start = today
        elif period_type == 'weekly':
            start = today - datetime.timedelta(days=today.weekday())
        elif period_type == 'monthly':
            start = today.replace(day=1)
        else:
            start = datetime.date(2020, 1, 1)
        period, _ = LeaderboardPeriod.objects.get_or_create(
            period_type=period_type, start_date=start,
            defaults={'is_active': True}
        )
        return period

    # ── Rank Refresh (bulk_update) ────────────────────────────────

    @staticmethod
    def refresh_ranks(period_type: str = 'weekly',
                      category: str = 'earnings') -> int:
        """
        Recalculate ranks for all entries.
        Uses bulk_update for efficiency — one DB write for all ranks.
        """
        from api.cms.models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry
        period = LeaderboardPeriod.get_active(period_type)
        if not period:
            return 0

        entries = list(
            LeaderboardEntry.objects
            .filter(period=period, category=category)
            .order_by('-score')
            .select_related('user')
        )
        # Assign ranks in Python, then bulk_update
        for i, entry in enumerate(entries, 1):
            entry.rank = i

        # Single DB write for all ranks (professional pattern)
        LeaderboardEntry.objects.bulk_update(entries, ['rank'], batch_size=500)

        # Rebuild cache
        cache_key = f"leaderboard_top_{period_type}_{category}"
        top_data = [{
            'rank': e.rank,
            'username': e.user.username,
            'score': float(e.score),
            'score_usd': float(e.score_usd),
            'score_coins': float(e.score_coins),
            'offers_count': e.offers_count,
        } for e in entries[:10]]
        cache.set(cache_key, top_data, 3600)

        logger.info(f"[Leaderboard] Ranks refreshed: {len(entries)} entries ({period_type}/{category})")
        return len(entries)

    # ── Queries ───────────────────────────────────────────────────

    @staticmethod
    def get_top(period_type: str = 'weekly', category: str = 'earnings',
                limit: int = 10) -> List[Dict]:
        """Get top N from cache, fallback to DB."""
        cache_key = f"leaderboard_top_{period_type}_{category}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached[:limit]

        from api.cms.models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry
        period = LeaderboardPeriod.get_active(period_type)
        if not period:
            return []

        entries = (
            LeaderboardEntry.objects
            .filter(period=period, category=category, rank__gt=0)
            .select_related('user')
            .order_by('rank')[:limit]
        )
        result = [{
            'rank': e.rank,
            'username': e.user.username,
            'score': float(e.score),
            'score_usd': float(e.score_usd),
            'score_coins': float(e.score_coins),
            'offers_count': e.offers_count,
        } for e in entries]
        cache.set(cache_key, result, 3600)
        return result

    @staticmethod
    def get_user_rank(user, period_type: str = 'weekly',
                      category: str = 'earnings') -> Dict:
        """Get user's current rank across all period/category combinations."""
        from api.cms.models_new.leaderboard import LeaderboardPeriod, LeaderboardEntry
        period = LeaderboardPeriod.get_active(period_type)
        if not period:
            return {'rank': 0, 'score': 0, 'period_type': period_type, 'category': category}
        try:
            entry = LeaderboardEntry.objects.get(
                period=period, user=user, category=category
            )
            return {
                'rank': entry.rank,
                'score': float(entry.score),
                'score_usd': float(entry.score_usd),
                'score_coins': float(entry.score_coins),
                'period_type': period_type,
                'category': category,
                'offers_count': entry.offers_count,
            }
        except LeaderboardEntry.DoesNotExist:
            return {'rank': 0, 'score': 0, 'period_type': period_type, 'category': category}

    @staticmethod
    def get_all_ranks(user) -> Dict[str, Dict]:
        """Get user's rank across all periods and categories at once."""
        from api.cms.models_new.leaderboard import LeaderboardEntry, LeaderboardPeriod
        active_periods = LeaderboardPeriod.objects.filter(is_active=True).values('id', 'period_type')
        period_map = {p['id']: p['period_type'] for p in active_periods}
        entries = (
            LeaderboardEntry.objects
            .filter(user=user, period_id__in=period_map.keys())
            .values('period_id', 'category', 'rank', 'score', 'score_coins', 'score_usd')
        )
        result = {}
        for e in entries:
            pt = period_map.get(e['period_id'], 'unknown')
            key = f"{pt}_{e['category']}"
            result[key] = {
                'rank': e['rank'], 'score': float(e['score']),
                'score_usd': float(e['score_usd']), 'score_coins': float(e['score_coins']),
            }
        return result


class StreakService:

    @staticmethod
    @db_transaction.atomic
    def record_earn(user) -> Dict[str, Any]:
        """
        Record earn and update streak. Atomic + select_for_update.
        Returns streak info and any milestone bonus.
        """
        from api.cms.models_new.leaderboard import EarningStreak, StreakMilestone

        streak, created = EarningStreak.objects.select_for_update().get_or_create(
            user=user,
            defaults={'current_streak': 0, 'longest_streak': 0}
        )
        old_count = streak.current_streak
        new_count = streak.update_streak()

        bonus = None
        # Check if hit milestone (only if streak increased)
        if new_count > old_count:
            milestone = StreakMilestone.objects.filter(
                streak_days=new_count, is_active=True
            ).first()
            if milestone:
                bonus = StreakService._award_milestone(user, milestone)

        # Invalidate user streak cache
        cache.delete(f"user_streak_{user.id}")

        return {
            'current_streak': new_count,
            'longest_streak': streak.longest_streak,
            'multiplier': float(streak.streak_bonus_multiplier),
            'is_active_today': streak.is_active_today(),
            'is_new_milestone': bonus is not None,
            'milestone_bonus': bonus,
        }

    @staticmethod
    def _award_milestone(user, milestone) -> Dict:
        awarded = False
        if milestone.bonus_coins > 0:
            try:
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                awarded = VirtualCurrencyService.award_coins(
                    user=user,
                    amount=milestone.bonus_coins,
                    reason=f"Streak milestone: {milestone.streak_days} days — {milestone.title}",
                    tx_type='earn_bonus',
                )
            except Exception as e:
                logger.warning(f"[Streak] Milestone award failed: {e}")
        try:
            from api.cms.services_new.NotificationService import NotificationService
            NotificationService.notify_streak_milestone(
                user=user,
                days=milestone.streak_days,
                title=milestone.title,
                bonus=float(milestone.bonus_coins),
            )
        except Exception:
            pass
        return {
            'days': milestone.streak_days,
            'coins': float(milestone.bonus_coins),
            'title': milestone.title,
            'awarded': awarded,
        }

    @staticmethod
    def get_streak_info(user) -> Dict:
        """Get streak info, cached per user."""
        cache_key = f"user_streak_{user.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        from api.cms.models_new.leaderboard import EarningStreak
        try:
            s = EarningStreak.objects.get(user=user)
            result = {
                'current_streak': s.current_streak,
                'longest_streak': s.longest_streak,
                'multiplier': float(s.streak_bonus_multiplier),
                'last_earn_date': str(s.last_earn_date) if s.last_earn_date else None,
                'is_active_today': s.is_active_today(),
                'total_streak_days': s.total_streak_days,
            }
        except EarningStreak.DoesNotExist:
            result = {
                'current_streak': 0, 'longest_streak': 0,
                'multiplier': 1.0, 'last_earn_date': None,
                'is_active_today': False, 'total_streak_days': 0,
            }
        cache.set(cache_key, result, 300)
        return result

    @staticmethod
    def reset_broken_streaks() -> int:
        """
        Reset streaks for users who didn't earn yesterday.
        Efficient: bulk_update instead of per-user saves.
        """
        from api.cms.models_new.leaderboard import EarningStreak
        import datetime
        yesterday = timezone.now().date() - datetime.timedelta(days=1)

        # Find broken streaks
        broken = list(
            EarningStreak.objects.filter(
                current_streak__gt=0
            ).exclude(
                last_earn_date__gte=yesterday
            )
        )
        for s in broken:
            s.current_streak = 0
            s.streak_bonus_multiplier = Decimal('1.0')

        if broken:
            EarningStreak.objects.bulk_update(
                broken, ['current_streak', 'streak_bonus_multiplier'], batch_size=500
            )

        logger.info(f"[Streak] Reset {len(broken)} broken streaks")
        return len(broken)

    @staticmethod
    def get_upcoming_milestones(user, limit: int = 3) -> List[Dict]:
        """Get next streak milestones for user motivation."""
        from api.cms.models_new.leaderboard import EarningStreak, StreakMilestone
        try:
            s = EarningStreak.objects.get(user=user)
            current = s.current_streak
        except EarningStreak.DoesNotExist:
            current = 0

        milestones = StreakMilestone.objects.filter(
            streak_days__gt=current, is_active=True
        ).order_by('streak_days')[:limit]
        return [{
            'streak_days': m.streak_days,
            'days_away': m.streak_days - current,
            'bonus_coins': float(m.bonus_coins),
            'title': m.title,
        } for m in milestones]
