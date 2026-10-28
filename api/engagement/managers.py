# engagement/managers.py
"""
Custom model managers for engagement system.
Provides optimized queries and common operations.
"""
from django.db.models import Max
from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, Prefetch
from django.db.models.functions import Coalesce, TruncDate, TruncHour
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.cache import cache

from .choices import QUEST_STATUS_CHOICES, ACHIEVEMENT_STATUS_CHOICES


class EngagementQuerySet(models.QuerySet):
    """
    Base queryset for engagement models with common methods.
    """
    
    def active(self):
        """Filter for active objects."""
        return self.filter(is_active=True)
    
    def for_user(self, user):
        """Filter for specific user."""
        return self.filter(user=user)
    
    def for_tenant(self, tenant):
        """Filter for specific tenant."""
        if tenant:
            return self.filter(tenant=tenant)
        return self
    
    def created_today(self):
        """Filter for objects created today."""
        today = timezone.now().date()
        return self.filter(created_at__date=today)
    
    def created_this_week(self):
        """Filter for objects created this week."""
        week_ago = timezone.now() - timedelta(days=7)
        return self.filter(created_at__gte=week_ago)
    
    def created_this_month(self):
        """Filter for objects created this month."""
        month_ago = timezone.now() - timedelta(days=30)
        return self.filter(created_at__gte=month_ago)
    
    def with_stats(self):
        """Add common statistical annotations."""
        return self.annotate(
            total_count=Count('id'),
            avg_value=Avg('value') if hasattr(self.model, 'value') else Count('id')
        )
    
    def cached(self, timeout=300):
        """Cache queryset results."""
        cache_key = f"qs_{self.model.__name__}_{hash(str(self.query))}"
        result = cache.get(cache_key)
        if result is None:
            result = list(self)
            cache.set(cache_key, result, timeout)
        return result


class DailyCheckInManager(models.Manager):
    """
    Manager for DailyCheckIn model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def today_for_user(self, user):
        """Get today's check-in for user."""
        today = timezone.now().date()
        return self.get_queryset().filter(user=user, date=today).first()
    
    def streak_for_user(self, user):
        """Get current streak for user."""
        latest = self.get_queryset().filter(user=user).order_by('-date').first()
        return latest.consecutive_days if latest else 0
    
    def total_checkins_for_user(self, user):
        """Get total check-ins for user."""
        return self.get_queryset().filter(user=user).count()
    
    def checkins_in_period(self, start_date, end_date=None, user=None):
        """Get check-ins within a period."""
        queryset = self.get_queryset().filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset
    
    def top_streaks(self, limit=10, tenant=None):
        """Get users with highest streaks."""
        queryset = self.get_queryset().values('user__username', 'user__id')
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        return queryset.annotate(
            max_streak=Max('consecutive_days')
        ).order_by('-max_streak')[:limit]
    
    def daily_stats(self, date=None, tenant=None):
        """Get daily statistics."""
        if not date:
            date = timezone.now().date()
        
        queryset = self.get_queryset().filter(date=date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        return queryset.aggregate(
            total_checkins=Count('id'),
            unique_users=Count('user', distinct=True),
            avg_streak=Avg('consecutive_days'),
            total_coins=Sum('coins_earned'),
            total_xp=Sum('xp_earned'),
            bonus_claimed=Count('id', filter=Q(bonus_claimed=True)),
            shield_used=Count('id', filter=Q(streak_shield_used=True))
        )


class SpinWheelManager(models.Manager):
    """
    Manager for SpinWheel model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def today_for_user(self, user):
        """Get today's spins for user."""
        today = timezone.now().date()
        return self.get_queryset().filter(user=user, spun_at__date=today)
    
    def remaining_today(self, user):
        """Get remaining spins for user today."""
        from .constants import SPIN_MAX_PER_DAY
        today_count = self.today_for_user(user).count()
        return max(0, SPIN_MAX_PER_DAY - today_count)
    
    def can_spin(self, user):
        """Check if user can spin today."""
        return self.remaining_today(user) > 0
    
    def total_spins_for_user(self, user):
        """Get total spins for user."""
        return self.get_queryset().filter(user=user).count()
    
    def spins_in_period(self, start_date, end_date=None, user=None):
        """Get spins within a period."""
        queryset = self.get_queryset().filter(spun_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(spun_at__date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset
    
    def daily_stats(self, date=None, tenant=None):
        """Get daily spin statistics."""
        if not date:
            date = timezone.now().date()
        
        queryset = self.get_queryset().filter(spun_at__date=date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        return queryset.aggregate(
            total_spins=Count('id'),
            unique_users=Count('user', distinct=True),
            total_coins_won=Sum('coins_won'),
            total_xp_earned=Sum('xp_earned'),
            boosted_spins=Count('id', filter=Q(is_boosted=True)),
            avg_coins_per_spin=Avg('coins_won')
        )
    
    def top_winners(self, date=None, limit=10, tenant=None):
        """Get top coin winners for a date."""
        if not date:
            date = timezone.now().date()
        
        queryset = self.get_queryset().filter(spun_at__date=date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        return queryset.values('user__username', 'user__id').annotate(
            total_coins=Sum('coins_won'),
            total_spins=Count('id')
        ).order_by('-total_coins')[:limit]


class UserAchievementManager(models.Manager):
    """
    Manager for UserAchievement model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def for_user(self, user):
        """Get achievements for user."""
        return self.get_queryset().filter(user=user).select_related('achievement')
    
    def unlocked_for_user(self, user):
        """Get unlocked achievements for user."""
        return self.for_user(user).filter(unlocked_at__isnull=False)
    
    def locked_for_user(self, user):
        """Get locked achievements for user."""
        return self.for_user(user).filter(unlocked_at__isnull=True)
    
    def progress_for_user(self, user):
        """Get achievement progress for user."""
        return self.for_user(user).annotate(
            progress=Coalesce(F('progress'), 0),
            is_unlocked=Count('id', filter=Q(unlocked_at__isnull=False))
        )
    
    def by_difficulty(self, user, difficulty=None):
        """Get achievements by difficulty."""
        queryset = self.for_user(user)
        if difficulty:
            queryset = queryset.filter(achievement__difficulty=difficulty)
        return queryset
    
    def recently_unlocked(self, user, days=7):
        """Get recently unlocked achievements."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.unlocked_for_user(user).filter(unlocked_at__gte=cutoff)
    
    def achievement_stats(self, user):
        """Get achievement statistics for user."""
        achievements = self.for_user(user)
        return achievements.aggregate(
            total_achievements=Count('id'),
            unlocked_count=Count('id', filter=Q(unlocked_at__isnull=False)),
            locked_count=Count('id', filter=Q(unlocked_at__isnull=True)),
            total_progress=Sum('progress'),
            avg_progress=Avg('progress')
        )


class UserQuestManager(models.Manager):
    """
    Manager for UserQuest model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def for_user(self, user):
        """Get quests for user."""
        return self.get_queryset().filter(user=user).select_related('quest')
    
    def active_for_user(self, user):
        """Get active quests for user."""
        return self.for_user(user).filter(status__in=['available', 'active'])
    
    def completed_for_user(self, user):
        """Get completed quests for user."""
        return self.for_user(user).filter(status='completed')
    
    def expired_for_user(self, user):
        """Get expired quests for user."""
        return self.for_user(user).filter(
            status='expired',
            expires_at__lt=timezone.now()
        )
    
    def expiring_soon(self, user, hours=24):
        """Get quests expiring soon."""
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.active_for_user(user).filter(
            expires_at__lte=cutoff,
            expires_at__gt=timezone.now()
        )
    
    def by_type(self, user, quest_type=None):
        """Get quests by type."""
        queryset = self.for_user(user)
        if quest_type:
            queryset = queryset.filter(quest__type=quest_type)
        return queryset
    
    def daily_quests(self, user):
        """Get daily quests for user."""
        return self.by_type(user, 'daily')
    
    def weekly_quests(self, user):
        """Get weekly quests for user."""
        return self.by_type(user, 'weekly')
    
    def quest_stats(self, user):
        """Get quest statistics for user."""
        quests = self.for_user(user)
        return quests.aggregate(
            total_quests=Count('id'),
            available_count=Count('id', filter=Q(status='available')),
            active_count=Count('id', filter=Q(status='active')),
            completed_count=Count('id', filter=Q(status='completed')),
            expired_count=Count('id', filter=Q(status='expired')),
            completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
        )


class LeaderboardManager(models.Manager):
    """
    Manager for Leaderboard model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def for_date(self, date):
        """Get leaderboard for specific date."""
        return self.get_queryset().filter(date=date)
    
    def for_season(self, season):
        """Get leaderboard for specific season."""
        return self.get_queryset().filter(season=season)
    
    def top_players(self, date=None, limit=100, season=None):
        """Get top players for date or season."""
        queryset = self.get_queryset()
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            # Default to today
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.select_related('user').order_by('rank')[:limit]
    
    def user_rank(self, user, date=None, season=None):
        """Get user's rank for date or season."""
        queryset = self.get_queryset().filter(user=user)
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        entry = queryset.first()
        return entry.rank if entry else None
    
    def around_user(self, user, date=None, count=5, season=None):
        """Get entries around user's rank."""
        user_rank = self.user_rank(user, date, season)
        if not user_rank:
            return []
        
        start_rank = max(1, user_rank - count)
        end_rank = user_rank + count
        
        queryset = self.get_queryset()
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.filter(rank__gte=start_rank, rank__lte=end_rank).select_related('user')
    
    def prize_distribution_stats(self, date=None, season=None):
        """Get prize distribution statistics."""
        queryset = self.get_queryset()
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        
        return queryset.aggregate(
            total_players=Count('id'),
            rewarded_players=Count('id', filter=Q(reward_distributed=True)),
            total_coins_distributed=Sum('total_coins_earned'),
            avg_coins_per_player=Avg('total_coins_earned'),
            top_10_percent_share=Sum('total_coins_earned', filter=Q(rank__lte=10))
        )


class FeedItemManager(models.Manager):
    """
    Manager for FeedItem model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def for_user(self, user):
        """Get feed items for user."""
        return self.get_queryset().filter(user=user)
    
    def from_friends(self, user):
        """Get feed items from user's friends."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get user's friends
        friend_ids = User.objects.filter(
            Q(friendships_received__user=user, friendships_received__status='active') |
            Q(friendships_sent__user=user, friendships_sent__status='active')
        ).values_list('id', flat=True)
        
        return self.get_queryset().filter(user_id__in=friend_ids)
    
    def by_type(self, feed_type):
        """Get feed items by type."""
        return self.get_queryset().filter(feed_type=feed_type)
    
    def recent(self, hours=24):
        """Get recent feed items."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(created_at__gte=cutoff)
    
    def with_engagement(self):
        """Get feed items with engagement counts."""
        return self.get_queryset().annotate(
            likes_count=Count('likes', distinct=True),
            comments_count=Count('comments', distinct=True)
        ).select_related('user')
    
    def viral(self, min_likes=10, hours=24):
        """Get viral feed items."""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(
            created_at__gte=cutoff
        ).annotate(
            likes_count=Count('likes', distinct=True)
        ).filter(likes_count__gte=min_likes)


class ShopPurchaseManager(models.Manager):
    """
    Manager for ShopPurchase model.
    """
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)
    
    def for_user(self, user):
        """Get purchases for user."""
        return self.get_queryset().filter(user=user).select_related('item')
    
    def by_status(self, status):
        """Get purchases by status."""
        return self.get_queryset().filter(status=status)
    
    def by_item_type(self, item_type):
        """Get purchases by item type."""
        return self.get_queryset().filter(item__type=item_type)
    
    def recent(self, days=30):
        """Get recent purchases."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(purchased_at__gte=cutoff)
    
    def spending_stats(self, user=None, days=30):
        """Get spending statistics."""
        queryset = self.get_queryset()
        
        if user:
            queryset = queryset.filter(user=user)
        
        cutoff = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(purchased_at__gte=cutoff)
        
        return queryset.aggregate(
            total_purchases=Count('id'),
            total_coins_spent=Sum('coins_spent'),
            avg_purchase_value=Avg('coins_spent'),
            unique_items=Count('item', distinct=True)
        )
    
    def popular_items(self, days=30, limit=10):
        """Get most popular items."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(
            purchased_at__gte=cutoff
        ).values('item__name', 'item__type').annotate(
            purchase_count=Count('id'),
            total_revenue=Sum('coins_spent')
        ).order_by('-purchase_count')[:limit]


# ── Custom Manager Mixins ─────────────────────────────────────────────────────

class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by tenant.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Note: This would need to be implemented with thread-local storage
        # or request context to get current tenant
        return queryset


class CacheableManager(models.Manager):
    """
    Manager with built-in caching capabilities.
    """
    
    def get_cached(self, cache_key, timeout=300, **kwargs):
        """Get cached result or execute query."""
        result = cache.get(cache_key)
        if result is None:
            result = self.get(**kwargs)
            cache.set(cache_key, result, timeout)
        return result
    
    def filter_cached(self, cache_key, timeout=300, **kwargs):
        """Get cached filtered result or execute query."""
        result = cache.get(cache_key)
        if result is None:
            result = list(self.filter(**kwargs))
            cache.set(cache_key, result, timeout)
        return result


class SoftDeleteManager(models.Manager):
    """
    Manager for soft-delete models.
    """
    
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """Include deleted objects."""
        return super().get_queryset()
    
    def deleted_only(self):
        """Only deleted objects."""
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def delete(self, *args, **kwargs):
        """Soft delete instead of hard delete."""
        return self.update(deleted_at=timezone.now())
