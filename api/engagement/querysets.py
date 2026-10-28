# engagement/querysets.py
"""
Custom querysets for engagement system.
Provides optimized queries and common query operations.
"""
from django.db.models import Case
from django.db.models import Max
from django.db.models import Min
from django.db.models import When
from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, Prefetch, OuterRef, Subquery, Exists, Window
from django.db.models.functions import Coalesce, TruncDate, TruncHour, TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import datetime, date, timedelta

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import UserQuest, Quest
from .models.achievement import UserAchievement, Achievement
from .models.shop import ShopPurchase, ShopItem, UserInventory
from .models.leaderboard import Leaderboard, LeaderboardSeason
from .models.social import FeedItem, Friendship
from .models.notification import Notification
from .models.referral import Referral
from .models.xp import UserXP


class EngagementQuerySet(models.QuerySet):
    """Base queryset for engagement models with common methods."""
    
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
    
    def with_user_stats(self):
        """Add user statistics annotations."""
        return self.annotate(
            total_count=Count('id'),
            avg_value=Avg('value') if hasattr(self.model, 'value') else Count('id')
        )
    
    def order_by_recent(self):
        """Order by most recent."""
        return self.order_by('-created_at')


class CheckInQuerySet(EngagementQuerySet):
    """QuerySet for DailyCheckIn model."""
    
    def today_for_user(self, user):
        """Get today's check-in for user."""
        today = timezone.now().date()
        return self.filter(user=user, date=today)
    
    def streak_for_user(self, user):
        """Get current streak for user."""
        latest = self.filter(user=user).order_by('-date').first()
        return latest.consecutive_days if latest else 0
    
    def total_checkins_for_user(self, user):
        """Get total check-ins for user."""
        return self.filter(user=user).count()
    
    def checkins_in_period(self, start_date, end_date=None, user=None):
        """Get check-ins within a period."""
        queryset = self.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset
    
    def with_streak_stats(self):
        """Add streak statistics."""
        return self.annotate(
            max_streak=models.Max('consecutive_days'),
            avg_streak=models.Avg('consecutive_days'),
            total_checkins=models.Count('id')
        )
    
    def by_month(self, user=None):
        """Group check-ins by month."""
        queryset = self.annotate(
            month=TruncMonth('date')
        )
        if user:
            queryset = queryset.filter(user=user)
        
        return queryset.values('month').annotate(
            checkins=Count('id'),
            unique_users=Count('user', distinct=True) if not user else Count('id'),
            total_coins=Sum('coins_earned'),
            total_xp=Sum('xp_earned')
        ).order_by('month')
    
    def recent_for_user(self, user, days=30):
        """Get recent check-ins for user."""
        cutoff = timezone.now().date() - timedelta(days=days)
        return self.filter(user=user, date__gte=cutoff).order_by('-date')


class SpinWheelQuerySet(EngagementQuerySet):
    """QuerySet for SpinWheel model."""
    
    def today_for_user(self, user):
        """Get today's spins for user."""
        today = timezone.now().date()
        return self.filter(user=user, spun_at__date=today)
    
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
        return self.filter(user=user).count()
    
    def spins_in_period(self, start_date, end_date=None, user=None):
        """Get spins within a period."""
        queryset = self.filter(spun_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(spun_at__date__lte=end_date)
        if user:
            queryset = queryset.filter(user=user)
        return queryset
    
    def with_spin_stats(self):
        """Add spin statistics."""
        return self.annotate(
            total_spins=Count('id'),
            total_coins_won=Sum('coins_won'),
            total_xp_earned=Sum('xp_earned'),
            avg_coins_per_spin=Avg('coins_won'),
            boosted_spins=Count('id', filter=Q(is_boosted=True))
        )
    
    def big_wins(self, min_coins=50):
        """Get spins with big wins."""
        return self.filter(coins_won__gte=min_coins)
    
    def boosted_spins(self):
        """Get boosted spins."""
        return self.filter(is_boosted=True)
    
    def by_hour(self, user=None):
        """Group spins by hour."""
        queryset = self.annotate(
            hour=TruncHour('spun_at')
        )
        if user:
            queryset = queryset.filter(user=user)
        
        return queryset.values('hour').annotate(
            spins=Count('id'),
            total_coins=Sum('coins_won'),
            total_xp=Sum('xp_earned')
        ).order_by('hour')


class UserQuestQuerySet(EngagementQuerySet):
    """QuerySet for UserQuest model."""
    
    def active_for_user(self, user):
        """Get active quests for user."""
        return self.filter(user=user, status__in=['available', 'active'])
    
    def completed_for_user(self, user):
        """Get completed quests for user."""
        return self.filter(user=user, status='completed')
    
    def expired_for_user(self, user):
        """Get expired quests for user."""
        return self.filter(
            user=user,
            status='expired',
            expires_at__lt=timezone.now()
        )
    
    def expiring_soon(self, user, hours=24):
        """Get quests expiring soon."""
        cutoff = timezone.now() + timedelta(hours=hours)
        return self.filter(
            user=user,
            status__in=['available', 'active'],
            expires_at__lte=cutoff,
            expires_at__gt=timezone.now()
        )
    
    def by_type(self, user, quest_type=None):
        """Get quests by type."""
        queryset = self.filter(user=user)
        if quest_type:
            queryset = queryset.filter(quest__type=quest_type)
        return queryset
    
    def with_progress_stats(self):
        """Add progress statistics."""
        return self.annotate(
            total_quests=Count('id'),
            available_count=Count('id', filter=Q(status='available')),
            active_count=Count('id', filter=Q(status='active')),
            completed_count=Count('id', filter=Q(status='completed')),
            expired_count=Count('id', filter=Q(status='expired')),
            completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
        )
    
    def near_completion(self, user, threshold=0.8):
        """Get quests near completion."""
        return self.filter(
            user=user,
            status__in=['available', 'active'],
            progress__gte=F('quest__required_progress') * threshold
        )


class UserAchievementQuerySet(EngagementQuerySet):
    """QuerySet for UserAchievement model."""
    
    def unlocked_for_user(self, user):
        """Get unlocked achievements for user."""
        return self.filter(user=user, unlocked_at__isnull=False).select_related('achievement')
    
    def locked_for_user(self, user):
        """Get locked achievements for user."""
        return self.filter(user=user, unlocked_at__isnull=True).select_related('achievement')
    
    def progress_for_user(self, user):
        """Get achievement progress for user."""
        return self.filter(user=user).annotate(
            progress=Coalesce(F('progress'), 0),
            is_unlocked=Count('id', filter=Q(unlocked_at__isnull=False))
        ).select_related('achievement')
    
    def by_difficulty(self, user, difficulty=None):
        """Get achievements by difficulty."""
        queryset = self.filter(user=user).select_related('achievement')
        if difficulty:
            queryset = queryset.filter(achievement__difficulty=difficulty)
        return queryset
    
    def recently_unlocked(self, user, days=7):
        """Get recently unlocked achievements."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.unlocked_for_user(user).filter(unlocked_at__gte=cutoff)
    
    def with_achievement_stats(self):
        """Add achievement statistics."""
        return self.select_related('achievement').annotate(
            total_achievements=Count('id'),
            unlocked_count=Count('id', filter=Q(unlocked_at__isnull=False)),
            locked_count=Count('id', filter=Q(unlocked_at__isnull=True)),
            total_progress=Sum('progress'),
            avg_progress=Avg('progress')
        )


class ShopPurchaseQuerySet(EngagementQuerySet):
    """QuerySet for ShopPurchase model."""
    
    def for_user(self, user):
        """Get purchases for user."""
        return self.filter(user=user).select_related('item')
    
    def by_status(self, status):
        """Get purchases by status."""
        return self.filter(status=status)
    
    def by_item_type(self, item_type):
        """Get purchases by item type."""
        return self.filter(item__type=item_type)
    
    def recent(self, days=30):
        """Get recent purchases."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_at__gte=cutoff)
    
    def with_purchase_stats(self):
        """Add purchase statistics."""
        return self.select_related('item').annotate(
            total_purchases=Count('id'),
            total_coins_spent=Sum('coins_spent'),
            avg_purchase_value=Avg('coins_spent'),
            unique_items=Count('item', distinct=True)
        )
    
    def by_month(self, user=None):
        """Group purchases by month."""
        queryset = self.annotate(
            month=TruncMonth('purchased_at')
        )
        if user:
            queryset = queryset.filter(user=user)
        
        return queryset.values('month').annotate(
            purchases=Count('id'),
            total_coins_spent=Sum('coins_spent'),
            avg_purchase_value=Avg('coins_spent'),
            unique_items=Count('item', distinct=True)
        ).order_by('month')
    
    def popular_items(self, days=30, limit=10):
        """Get most popular items."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_at__gte=cutoff).values('item__name', 'item__type').annotate(
            purchase_count=Count('id'),
            total_revenue=Sum('coins_spent')
        ).order_by('-purchase_count')[:limit]


class LeaderboardQuerySet(EngagementQuerySet):
    """QuerySet for Leaderboard model."""
    
    def for_date(self, date):
        """Get leaderboard for specific date."""
        return self.filter(date=date)
    
    def for_season(self, season):
        """Get leaderboard for specific season."""
        return self.filter(season=season)
    
    def top_players(self, date=None, limit=100, season=None):
        """Get top players for date or season."""
        queryset = self.select_related('user')
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.order_by('rank')[:limit]
    
    def user_rank(self, user, date=None, season=None):
        """Get user's rank for date or season."""
        queryset = self.filter(user=user)
        
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
        
        queryset = self.select_related('user')
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.filter(rank__gte=start_rank, rank__lte=end_rank)
    
    def with_rank_stats(self):
        """Add rank statistics."""
        return self.annotate(
            total_players=Count('id'),
            rewarded_players=Count('id', filter=Q(reward_distributed=True)),
            total_coins_distributed=Sum('total_coins_earned'),
            avg_coins_per_player=Avg('total_coins_earned'),
            top_10_percent_share=Sum('total_coins_earned', filter=Q(rank__lte=10))
        )


class NotificationQuerySet(EngagementQuerySet):
    """QuerySet for Notification model."""
    
    def for_user(self, user):
        """Get notifications for user."""
        return self.filter(user=user)
    
    def unread_for_user(self, user):
        """Get unread notifications for user."""
        return self.filter(user=user, is_read=False)
    
    def by_type(self, notification_type):
        """Get notifications by type."""
        return self.filter(type=notification_type)
    
    def recent(self, days=30):
        """Get recent notifications."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)
    
    def with_read_stats(self):
        """Add read statistics."""
        return self.annotate(
            total_notifications=Count('id'),
            unread_count=Count('id', filter=Q(is_read=False)),
            read_count=Count('id', filter=Q(is_read=True))
        )


class FriendshipQuerySet(EngagementQuerySet):
    """QuerySet for Friendship model."""
    
    def for_user(self, user):
        """Get friendships for user (both sent and received)."""
        return self.filter(
            Q(user=user) | Q(friend=user)
        ).distinct()
    
    def active_for_user(self, user):
        """Get active friendships for user."""
        return self.for_user(user).filter(status='active')
    
    def pending_for_user(self, user):
        """Get pending friendships for user."""
        return self.for_user(user).filter(status='pending')
    
    def friends_of_user(self, user):
        """Get friends of user."""
        return self.active_for_user(user).annotate(
            friend_id=Case(
                When(user=user, then=F('friend_id')),
                default=F('user_id')
            )
        ).values('friend_id')


class ReferralQuerySet(EngagementQuerySet):
    """QuerySet for Referral model."""
    
    def for_referrer(self, user):
        """Get referrals made by user."""
        return self.filter(referrer=user)
    
    def for_referred(self, user):
        """Get referrals where user is referred."""
        return self.filter(referred=user)
    
    def by_status(self, status):
        """Get referrals by status."""
        return self.filter(status=status)
    
    def successful_for_user(self, user):
        """Get successful referrals for user."""
        return self.for_referrer(user).filter(status__in=['confirmed', 'rewarded'])
    
    def with_referral_stats(self):
        """Add referral statistics."""
        return self.annotate(
            total_referrals=Count('id'),
            successful_referrals=Count('id', filter=Q(status__in=['confirmed', 'rewarded'])),
            pending_referrals=Count('id', filter=Q(status='pending')),
            conversion_rate=Count('id', filter=Q(status__in=['confirmed', 'rewarded'])) * 100.0 / Count('id')
        )


class UserXPQuerySet(EngagementQuerySet):
    """QuerySet for UserXP model."""
    
    def for_user(self, user):
        """Get XP record for user."""
        return self.filter(user=user)
    
    def by_level(self, level):
        """Get users at specific level."""
        return self.filter(level=level)
    
    def by_level_range(self, min_level, max_level):
        """Get users in level range."""
        return self.filter(level__gte=min_level, level__lte=max_level)
    
    def top_xp(self, limit=100):
        """Get users with highest XP."""
        return self.order_by('-total_xp')[:limit]
    
    def with_level_stats(self):
        """Add level statistics."""
        return self.annotate(
            total_users=Count('id'),
            avg_level=Avg('level'),
            max_level=Max('level'),
            min_level=Min('level'),
            total_xp=Sum('total_xp'),
            avg_xp=Avg('total_xp')
        )


# ── Advanced QuerySets ─────────────────────────────────────────────────────

class AnalyticsQuerySet(EngagementQuerySet):
    """Advanced analytics queryset."""
    
    def with_time_series(self, period='day'):
        """Add time series annotations."""
        if period == 'hour':
            return self.annotate(period=TruncHour('created_at'))
        elif period == 'day':
            return self.annotate(period=TruncDay('created_at'))
        elif period == 'week':
            return self.annotate(period=TruncWeek('created_at'))
        elif period == 'month':
            return self.annotate(period=TruncMonth('created_at'))
        else:
            return self.annotate(period=TruncDay('created_at'))
    
    def with_growth_metrics(self, previous_period_days=30):
        """Add growth metrics."""
        from django.db.models import Subquery, OuterRef
        
        # Get current period data
        current_period = timezone.now() - timedelta(days=previous_period_days)
        current_queryset = self.filter(created_at__gte=current_period)
        
        # Get previous period data
        previous_period = current_period - timedelta(days=previous_period_days)
        previous_queryset = self.filter(created_at__gte=previous_period, created_at__lt=current_period)
        
        return self.annotate(
            current_count=Subquery(current_queryset.values('id')[:1]),
            previous_count=Subquery(previous_queryset.values('id')[:1]),
            growth_rate=Subquery(current_queryset.values('id')[:1]) - Subquery(previous_queryset.values('id')[:1])
        )
    
    def with_percentiles(self, field, percentiles=[25, 50, 75, 90, 95, 99]):
        """Add percentile calculations."""
        from django.db.models import Window, F
        from django.db.models.functions import PercentRank
        
        return self.annotate(
            percentile_rank=Window(
                expression=PercentRank(F(field)),
                order_by=F(field)
            )
        )


# ── Custom Manager Classes ─────────────────────────────────────────────────────

class EngagementManager(models.Manager):
    """Manager with engagement querysets."""
    
    def get_queryset(self):
        return EngagementQuerySet(self.model, using=self._db)


class CheckInManager(EngagementManager):
    """Manager for DailyCheckIn with custom queryset."""
    
    def get_queryset(self):
        return CheckInQuerySet(self.model, using=self._db)


class SpinWheelManager(EngagementManager):
    """Manager for SpinWheel with custom queryset."""
    
    def get_queryset(self):
        return SpinWheelQuerySet(self.model, using=self._db)


class UserQuestManager(EngagementManager):
    """Manager for UserQuest with custom queryset."""
    
    def get_queryset(self):
        return UserQuestQuerySet(self.model, using=self._db)


class UserAchievementManager(EngagementManager):
    """Manager for UserAchievement with custom queryset."""
    
    def get_queryset(self):
        return UserAchievementQuerySet(self.model, using=self._db)


class ShopPurchaseManager(EngagementManager):
    """Manager for ShopPurchase with custom queryset."""
    
    def get_queryset(self):
        return ShopPurchaseQuerySet(self.model, using=self._db)


class LeaderboardManager(EngagementManager):
    """Manager for Leaderboard with custom queryset."""
    
    def get_queryset(self):
        return LeaderboardQuerySet(self.model, using=self._db)


class NotificationManager(EngagementManager):
    """Manager for Notification with custom queryset."""
    
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)


class FriendshipManager(EngagementManager):
    """Manager for Friendship with custom queryset."""
    
    def get_queryset(self):
        return FriendshipQuerySet(self.model, using=self._db)


class ReferralManager(EngagementManager):
    """Manager for Referral with custom queryset."""
    
    def get_queryset(self):
        return ReferralQuerySet(self.model, using=self._db)


class UserXPManager(EngagementManager):
    """Manager for UserXP with custom queryset."""
    
    def get_queryset(self):
        return UserXPQuerySet(self.model, using=self._db)


# ── QuerySet Utilities ─────────────────────────────────────────────────────

class QuerySetUtils:
    """Utility functions for querysets."""
    
    @staticmethod
    def get_date_range_filter(field, start_date, end_date=None):
        """Get date range filter."""
        filter_kwargs = {f"{field}__gte": start_date}
        if end_date:
            filter_kwargs[f"{field}__lte"] = end_date
        return Q(**filter_kwargs)
    
    @staticmethod
    def get_user_filter(user_field='user'):
        """Get user filter."""
        return Q(**{user_field: user}) if user else Q()
    
    @staticmethod
    def get_tenant_filter(tenant_field='tenant'):
        """Get tenant filter."""
        return Q(**{tenant_field: tenant}) if tenant else Q()
    
    @staticmethod
    def annotate_user_stats(queryset, prefix=''):
        """Annotate user statistics."""
        return queryset.annotate(
            **{f"{prefix}total_count": Count('id')},
            **{f"{prefix}avg_value": Avg('value') if hasattr(queryset.model, 'value') else Count('id')}
        )
    
    @staticmethod
    def annotate_time_series(queryset, field='created_at', period='day'):
        """Annotate time series data."""
        if period == 'hour':
            return queryset.annotate(**{f"{period}": TruncHour(field)})
        elif period == 'day':
            return queryset.annotate(**{f"{period}": TruncDay(field)})
        elif period == 'week':
            return queryset.annotate(**{f"{period}": TruncWeek(field)})
        elif period == 'month':
            return queryset.annotate(**{f"{period}": TruncMonth(field)})
        else:
            return queryset.annotate(**{f"{period}": TruncDay(field)})
    
    @staticmethod
    def get_window_function(queryset, field, function='Avg', window=None):
        """Get window function annotation."""
        if window is None:
            return queryset.annotate(**{f"{function}_{field}": function(field)})
        else:
            return queryset.annotate(**{f"{function}_{field}": Window(function(field), order_by=window)})


# ── Bulk Operations ─────────────────────────────────────────────────────

class BulkOperationsMixin:
    """Mixin for bulk operations."""
    
    def bulk_create_with_stats(self, objs):
        """Bulk create with statistics."""
        created_objs = self.bulk_create(objs)
        return {
            'created_count': len(created_objs),
            'objects': created_objs
        }
    
    def bulk_update_with_stats(self, objs, fields):
        """Bulk update with statistics."""
        updated_count = self.bulk_update(objs, fields)
        return {
            'updated_count': updated_count
        }
    
    def bulk_delete_with_stats(self):
        """Bulk delete with statistics."""
        deleted_count, _ = self.delete()
        return {
            'deleted_count': deleted_count
        }


# ── QuerySet Mixins ─────────────────────────────────────────────────────

class TenantAwareQuerySet(EngagementQuerySet):
    """QuerySet mixin for tenant-aware queries."""
    
    def for_tenant(self, tenant):
        """Filter for specific tenant."""
        if tenant:
            return self.filter(tenant=tenant)
        return self


class UserAwareQuerySet(EngagementQuerySet):
    """QuerySet mixin for user-aware queries."""
    
    def for_user(self, user):
        """Filter for specific user."""
        if user:
            return self.filter(user=user)
        return self


class DateRangeQuerySet(EngagementQuerySet):
    """QuerySet mixin for date range queries."""
    
    def in_date_range(self, start_date, end_date=None):
        """Filter objects in date range."""
        queryset = self.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        return queryset
    
    def in_datetime_range(self, start_datetime, end_datetime=None):
        """Filter objects in datetime range."""
        queryset = self.filter(created_at__gte=start_datetime)
        if end_datetime:
            queryset = queryset.filter(created_at__lte=end_datetime)
        return queryset


class StatsQuerySet(EngagementQuerySet):
    """QuerySet mixin for statistics."""
    
    def with_stats(self):
        """Add basic statistics."""
        return self.annotate(
            total_count=Count('id'),
            avg_value=Avg('value') if hasattr(self.model, 'value') else 0,
            sum_value=Sum('value') if hasattr(self.model, 'value') else 0
        )
    
    def by_period(self, period='day'):
        """Group by time period."""
        if period == 'hour':
            return self.annotate(period=TruncHour('created_at'))
        elif period == 'day':
            return self.annotate(period=TruncDay('created_at'))
        elif period == 'week':
            return self.annotate(period=TruncWeek('created_at'))
        elif period == 'month':
            return self.annotate(period=TruncMonth('created_at'))
        else:
            return self.annotate(period=TruncDay('created_at'))
    
    def group_by_period(self, period='day'):
        """Group results by time period."""
        annotated = self.by_period(period)
        return annotated.values('period').annotate(
            count=Count('id'),
            avg_value=Avg('value') if hasattr(self.model, 'value') else 0,
            sum_value=Sum('value') if hasattr(self.model, 'value') else 0
        ).order_by('period')
