# engagement/selectors.py
"""
Selector pattern implementation for engagement system.
Provides query logic separation from models and services.
"""
from django.db.models import F
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncHour
from django.db.models.functions import TruncMonth
from django.db.models.functions import TruncWeek
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from django.db.models import Q, QuerySet, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, date, timedelta

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.quest import UserQuest, Quest
from .models.achievement import UserAchievement, Achievement
from .models.shop import ShopItem, ShopPurchase
from .models.leaderboard import Leaderboard
from .models.social import FeedItem
from .models.notification import Notification
from .models.referral import Referral


class BaseSelector(ABC):
    """Base selector class for engagement system."""
    
    def __init__(self, queryset: QuerySet):
        self.queryset = queryset
    
    @abstractmethod
    def filter(self, **kwargs) -> 'BaseSelector':
        """Apply filters to queryset."""
        pass
    
    @abstractmethod
    def execute(self) -> QuerySet:
        """Execute the query and return results."""
        pass
    
    def first(self):
        """Get first result."""
        return self.queryset.first()
    
    def count(self):
        """Get count of results."""
        return self.queryset.count()
    
    def exists(self):
        """Check if results exist."""
        return self.queryset.exists()


class CheckInSelector(BaseSelector):
    """Selector for DailyCheckIn model."""
    
    def filter(self, user=None, date=None, date_from=None, date_to=None, 
                streak_min=None, streak_max=None, coins_min=None, coins_max=None,
                bonus_claimed=None, shield_used=None, tenant=None) -> 'CheckInSelector':
        """Apply filters to check-in queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if date:
            self.queryset = self.queryset.filter(date=date)
        
        if date_from:
            self.queryset = self.queryset.filter(date__gte=date_from)
        
        if date_to:
            self.queryset = self.queryset.filter(date__lte=date_to)
        
        if streak_min is not None:
            self.queryset = self.queryset.filter(consecutive_days__gte=streak_min)
        
        if streak_max is not None:
            self.queryset = self.queryset.filter(consecutive_days__lte=streak_max)
        
        if coins_min is not None:
            self.queryset = self.queryset.filter(coins_earned__gte=coins_min)
        
        if coins_max is not None:
            self.queryset = self.queryset.filter(coins_earned__lte=coins_max)
        
        if bonus_claimed is not None:
            self.queryset = self.queryset.filter(bonus_claimed=bonus_claimed)
        
        if shield_used is not None:
            self.queryset = self.queryset.filter(streak_shield_used=shield_used)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def today_for_user(self, user) -> QuerySet:
        """Get today's check-in for user."""
        return self.filter(user=user, date=date.today()).execute()
    
    def streak_for_user(self, user) -> int:
        """Get current streak for user."""
        latest = self.filter(user=user).execute().order_by('-date').first()
        return latest.consecutive_days if latest else 0
    
    def total_checkins_for_user(self, user) -> int:
        """Get total check-ins for user."""
        return self.filter(user=user).count()
    
    def checkins_in_period(self, start_date, end_date=None, user=None) -> QuerySet:
        """Get check-ins within a period."""
        return self.filter(user=user, date_from=start_date, date_to=end_date).execute()
    
    def with_streak_stats(self) -> QuerySet:
        """Add streak statistics."""
        return self.execute().annotate(
            max_streak=Count('consecutive_days'),
            avg_streak=Avg('consecutive_days'),
            total_checkins=Count('id')
        )
    
    def by_month(self, user=None) -> QuerySet:
        """Group check-ins by month."""
        filtered = self.filter(user=user)
        return filtered.execute().annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            checkins=Count('id'),
            unique_users=Count('user', distinct=True) if not user else Count('id'),
            total_coins=Sum('coins_earned'),
            total_xp=Sum('xp_earned')
        ).order_by('month')
    
    def recent_for_user(self, user, days=30) -> QuerySet:
        """Get recent check-ins for user."""
        cutoff = timezone.now().date() - timedelta(days=days)
        return self.filter(user=user, date_from=cutoff).execute().order_by('-date')
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class SpinWheelSelector(BaseSelector):
    """Selector for SpinWheel model."""
    
    def filter(self, user=None, spun_at_from=None, spun_at_to=None, 
                coins_min=None, coins_max=None, xp_min=None, xp_max=None,
                is_boosted=None, outcome_idx=None, today_only=None, tenant=None) -> 'SpinWheelSelector':
        """Apply filters to spin queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if spun_at_from:
            self.queryset = self.queryset.filter(spun_at__gte=spun_at_from)
        
        if spun_at_to:
            self.queryset = self.queryset.filter(spun_at__lte=spun_at_to)
        
        if coins_min is not None:
            self.queryset = self.queryset.filter(coins_won__gte=coins_min)
        
        if coins_max is not None:
            self.queryset = self.queryset.filter(coins_won__lte=coins_max)
        
        if xp_min is not None:
            self.queryset = self.queryset.filter(xp_earned__gte=xp_min)
        
        if xp_max is not None:
            self.queryset = self.queryset.filter(xp_earned__lte=xp_max)
        
        if is_boosted is not None:
            self.queryset = self.queryset.filter(is_boosted=is_boosted)
        
        if outcome_idx is not None:
            self.queryset = self.queryset.filter(outcome_idx=outcome_idx)
        
        if today_only:
            today = timezone.now().date()
            self.queryset = self.queryset.filter(spun_at__date=today)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def today_for_user(self, user) -> QuerySet:
        """Get today's spins for user."""
        today = timezone.now().date()
        return self.filter(user=user, spun_at_from=today).execute()
    
    def remaining_today(self, user) -> int:
        """Get remaining spins for user today."""
        from .constants import SPIN_MAX_PER_DAY
        
        today_count = self.today_for_user(user).count()
        return max(0, SPIN_MAX_PER_DAY - today_count)
    
    def total_spins_for_user(self, user) -> int:
        """Get total spins for user."""
        return self.filter(user=user).count()
    
    def spins_in_period(self, start_date, end_date=None, user=None) -> QuerySet:
        """Get spins within a period."""
        return self.filter(user=user, spun_at_from=start_date, spun_at_to=end_date).execute()
    
    def with_spin_stats(self) -> QuerySet:
        """Add spin statistics."""
        return self.execute().annotate(
            total_spins=Count('id'),
            total_coins_won=Sum('coins_won'),
            total_xp_earned=Sum('xp_earned'),
            avg_coins_per_spin=Avg('coins_won'),
            boosted_spins=Count('id', filter=Q(is_boosted=True))
        )
    
    def big_wins(self, min_coins=50) -> QuerySet:
        """Get spins with big wins."""
        return self.filter(coins_min=min_coins).execute()
    
    def boosted_spins(self) -> QuerySet:
        """Get boosted spins."""
        return self.filter(is_boosted=True).execute()
    
    def by_hour(self, user=None) -> QuerySet:
        """Group spins by hour."""
        filtered = self.filter(user=user)
        return filtered.execute().annotate(
            hour=TruncHour('spun_at')
        ).values('hour').annotate(
            spins=Count('id'),
            total_coins=Sum('coins_won'),
            total_xp=Sum('xp_earned')
        ).order_by('hour')
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class UserQuestSelector(BaseSelector):
    """Selector for UserQuest model."""
    
    def filter(self, user=None, quest=None, status=None, quest_type=None,
                created_from=None, created_to=None, completed_from=None,
                completed_to=None, expires_soon=None, tenant=None) -> 'UserQuestSelector':
        """Apply filters to user quest queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if quest:
            self.queryset = self.queryset.filter(quest=quest)
        
        if status:
            self.queryset = self.queryset.filter(status=status)
        
        if quest_type:
            self.queryset = self.queryset.filter(quest__type=quest_type)
        
        if created_from:
            self.queryset = self.queryset.filter(created_at__gte=created_from)
        
        if created_to:
            self.queryset = self.queryset.filter(created_at__lte=created_to)
        
        if completed_from:
            self.queryset = self.queryset.filter(completed_at__gte=completed_from)
        
        if completed_to:
            self.queryset = self.queryset.filter(completed_at__lte=completed_to)
        
        if expires_soon:
            cutoff = timezone.now() + timedelta(hours=24)
            self.queryset = self.queryset.filter(
                expires_at__lte=cutoff,
                expires_at__gt=timezone.now(),
                status__in=['available', 'active']
            )
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def active_for_user(self, user) -> QuerySet:
        """Get active quests for user."""
        return self.filter(user=user, status__in=['available', 'active']).execute()
    
    def completed_for_user(self, user) -> QuerySet:
        """Get completed quests for user."""
        return self.filter(user=user, status='completed').execute()
    
    def expired_for_user(self, user) -> QuerySet:
        """Get expired quests for user."""
        return self.filter(
            user=user,
            status='expired',
            expires_at__lt=timezone.now()
        ).execute()
    
    def expiring_soon(self, user, hours=24) -> QuerySet:
        """Get quests expiring soon."""
        return self.filter(user=user, expires_soon=True).execute()
    
    def by_type(self, user, quest_type=None) -> QuerySet:
        """Get quests by type."""
        return self.filter(user=user, quest_type=quest_type).execute()
    
    def with_progress_stats(self) -> QuerySet:
        """Add progress statistics."""
        return self.execute().annotate(
            total_quests=Count('id'),
            available_count=Count('id', filter=Q(status='available')),
            active_count=Count('id', filter=Q(status='active')),
            completed_count=Count('id', filter=Q(status='completed')),
            expired_count=Count('id', filter=Q(status='expired')),
            completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
        )
    
    def near_completion(self, user, threshold=0.8) -> QuerySet:
        """Get quests near completion."""
        return self.filter(
            user=user,
            status__in=['available', 'active'],
            progress__gte=F('quest__required_progress') * threshold
        ).execute()
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class UserAchievementSelector(BaseSelector):
    """Selector for UserAchievement model."""
    
    def filter(self, user=None, achievement=None, difficulty=None,
                unlocked_from=None, unlocked_to=None, tenant=None) -> 'UserAchievementSelector':
        """Apply filters to user achievement queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if achievement:
            self.queryset = self.queryset.filter(achievement=achievement)
        
        if difficulty:
            self.queryset = self.queryset.filter(achievement__difficulty=difficulty)
        
        if unlocked_from:
            self.queryset = self.queryset.filter(unlocked_at__gte=unlocked_from)
        
        if unlocked_to:
            self.queryset = self.queryset.filter(unlocked_at__lte=unlocked_to)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def unlocked_for_user(self, user) -> QuerySet:
        """Get unlocked achievements for user."""
        return self.filter(user=user).execute().filter(unlocked_at__isnull=False).select_related('achievement')
    
    def locked_for_user(self, user) -> QuerySet:
        """Get locked achievements for user."""
        return self.filter(user=user).execute().filter(unlocked_at__isnull=True).select_related('achievement')
    
    def progress_for_user(self, user) -> QuerySet:
        """Get achievement progress for user."""
        return self.filter(user=user).execute().annotate(
            progress=Coalesce(F('progress'), 0),
            is_unlocked=Count('id', filter=Q(unlocked_at__isnull=False))
        ).select_related('achievement')
    
    def by_difficulty(self, user, difficulty=None) -> QuerySet:
        """Get achievements by difficulty."""
        return self.filter(user=user).execute().select_related('achievement').filter(
            achievement__difficulty=difficulty
        )
    
    def recently_unlocked(self, user, days=7) -> QuerySet:
        """Get recently unlocked achievements."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.unlocked_for_user(user).filter(unlocked_at__gte=cutoff)
    
    def with_achievement_stats(self) -> QuerySet:
        """Add achievement statistics."""
        return self.execute().select_related('achievement').annotate(
            total_achievements=Count('id'),
            unlocked_count=Count('id', filter=Q(unlocked_at__isnull=False)),
            locked_count=Count('id', filter=Q(unlocked_at__isnull=True)),
            total_progress=Sum('progress'),
            avg_progress=Avg('progress')
        )
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class ShopPurchaseSelector(BaseSelector):
    """Selector for ShopPurchase model."""
    
    def filter(self, user=None, item=None, status=None, item_type=None,
                purchased_from=None, purchased_to=None, amount_min=None,
                amount_max=None, tenant=None) -> 'ShopPurchaseSelector':
        """Apply filters to shop purchase queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if item:
            self.queryset = self.queryset.filter(item=item)
        
        if status:
            self.queryset = self.queryset.filter(status=status)
        
        if item_type:
            self.queryset = self.queryset.filter(item__type=item_type)
        
        if purchased_from:
            self.queryset = self.queryset.filter(purchased_at__gte=purchased_from)
        
        if purchased_to:
            self.queryset = self.queryset.filter(purchased_at__lte=purchased_to)
        
        if amount_min is not None:
            self.queryset = self.queryset.filter(coins_spent__gte=amount_min)
        
        if amount_max is not None:
            self.queryset = self.queryset.filter(coins_spent__lte=amount_max)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def for_user(self, user) -> QuerySet:
        """Get purchases for user."""
        return self.filter(user=user).execute().select_related('item')
    
    def by_status(self, status) -> QuerySet:
        """Get purchases by status."""
        return self.filter(status=status).execute()
    
    def by_item_type(self, item_type) -> QuerySet:
        """Get purchases by item type."""
        return self.filter(item_type=item_type).execute()
    
    def recent(self, days=30) -> QuerySet:
        """Get recent purchases."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_from=cutoff).execute()
    
    def with_purchase_stats(self) -> QuerySet:
        """Add purchase statistics."""
        return self.execute().select_related('item').annotate(
            total_purchases=Count('id'),
            total_coins_spent=Sum('coins_spent'),
            avg_purchase_value=Avg('coins_spent'),
            unique_items=Count('item', distinct=True)
        )
    
    def by_month(self, user=None) -> QuerySet:
        """Group purchases by month."""
        filtered = self.filter(user=user)
        return filtered.execute().annotate(
            month=TruncMonth('purchased_at')
        ).values('month').annotate(
            purchases=Count('id'),
            total_coins_spent=Sum('coins_spent'),
            avg_purchase_value=Avg('coins_spent'),
            unique_items=Count('item', distinct=True)
        ).order_by('month')
    
    def popular_items(self, days=30, limit=10) -> QuerySet:
        """Get most popular items."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(purchased_from=cutoff).execute().values('item__name', 'item__type').annotate(
            purchase_count=Count('id'),
            total_revenue=Sum('coins_spent')
        ).order_by('-purchase_count')[:limit]
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class LeaderboardSelector(BaseSelector):
    """Selector for Leaderboard model."""
    
    def filter(self, user=None, date=None, season=None, rank_min=None,
                rank_max=None, coins_min=None, coins_max=None, xp_min=None,
                xp_max=None, rewarded=None, tenant=None) -> 'LeaderboardSelector':
        """Apply filters to leaderboard queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if date:
            self.queryset = self.queryset.filter(date=date)
        
        if season:
            self.queryset = self.queryset.filter(season=season)
        
        if rank_min is not None:
            self.queryset = self.queryset.filter(rank__gte=rank_min)
        
        if rank_max is not None:
            self.queryset = self.queryset.filter(rank__lte=rank_max)
        
        if coins_min is not None:
            self.queryset = self.queryset.filter(total_coins_earned__gte=coins_min)
        
        if coins_max is not None:
            self.queryset = self.queryset.filter(total_coins_earned__lte=coins_max)
        
        if xp_min is not None:
            self.queryset = self.queryset.filter(total_xp_earned__gte=xp_min)
        
        if xp_max is not None:
            self.queryset = self.queryset.filter(total_xp_earned__lte=xp_max)
        
        if rewarded is not None:
            self.queryset = self.queryset.filter(reward_distributed=rewarded)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def for_date(self, date) -> QuerySet:
        """Get leaderboard for specific date."""
        return self.filter(date=date).execute()
    
    def for_season(self, season) -> QuerySet:
        """Get leaderboard for specific season."""
        return self.filter(season=season).execute()
    
    def top_players(self, date=None, limit=100, season=None) -> QuerySet:
        """Get top players for date or season."""
        queryset = self.execute().select_related('user')
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.order_by('rank')[:limit]
    
    def user_rank(self, user, date=None, season=None) -> int:
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
    
    def around_user(self, user, date=None, count=5, season=None) -> QuerySet:
        """Get entries around user's rank."""
        user_rank = self.user_rank(user, date, season)
        if not user_rank:
            return []
        
        start_rank = max(1, user_rank - count)
        end_rank = user_rank + count
        
        queryset = self.execute().select_related('user')
        
        if date:
            queryset = queryset.filter(date=date)
        elif season:
            queryset = queryset.filter(season=season)
        else:
            queryset = queryset.filter(date=timezone.now().date())
        
        return queryset.filter(rank__gte=start_rank, rank__lte=end_rank)
    
    def with_rank_stats(self) -> QuerySet:
        """Add rank statistics."""
        return self.execute().annotate(
            total_players=Count('id'),
            rewarded_players=Count('id', filter=Q(reward_distributed=True)),
            total_coins_distributed=Sum('total_coins_earned'),
            avg_coins_per_player=Avg('total_coins_earned'),
            top_10_percent_share=Sum('total_coins_earned', filter=Q(rank__lte=10))
        )
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class NotificationSelector(BaseSelector):
    """Selector for Notification model."""
    
    def filter(self, user=None, notification_type=None, is_read=None,
                created_from=None, created_to=None, tenant=None) -> 'NotificationSelector':
        """Apply filters to notification queryset."""
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if notification_type:
            self.queryset = self.queryset.filter(type=notification_type)
        
        if is_read is not None:
            self.queryset = self.queryset.filter(is_read=is_read)
        
        if created_from:
            self.queryset = self.queryset.filter(created_at__gte=created_from)
        
        if created_to:
            self.queryset = self.queryset.filter(created_at__lte=created_to)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def for_user(self, user) -> QuerySet:
        """Get notifications for user."""
        return self.filter(user=user).execute()
    
    def unread_for_user(self, user) -> QuerySet:
        """Get unread notifications for user."""
        return self.filter(user=user, is_read=False).execute()
    
    def by_type(self, notification_type) -> QuerySet:
        """Get notifications by type."""
        return self.filter(notification_type=notification_type).execute()
    
    def recent(self, days=30) -> QuerySet:
        """Get recent notifications."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_from=cutoff).execute()
    
    def with_read_stats(self) -> QuerySet:
        """Add read statistics."""
        return self.execute().annotate(
            total_notifications=Count('id'),
            unread_count=Count('id', filter=Q(is_read=False)),
            read_count=Count('id', filter=Q(is_read=True))
        )
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


# ── Selector Factory ─────────────────────────────────────────────────────

class SelectorFactory:
    """Factory for creating selector instances."""
    
    @staticmethod
    def create_selector(model_class, queryset=None):
        """Create selector instance for model class."""
        if queryset is None:
            queryset = model_class.objects.all()
        
        selector_map = {
            DailyCheckIn: CheckInSelector,
            SpinWheel: SpinWheelSelector,
            UserQuest: UserQuestSelector,
            UserAchievement: UserAchievementSelector,
            ShopPurchase: ShopPurchaseSelector,
            Leaderboard: LeaderboardSelector,
            Notification: NotificationSelector,
        }
        
        selector_class = selector_map.get(model_class)
        if selector_class:
            return selector_class(queryset)
        
        raise ValueError(f"No selector found for model {model_class.__name__}")
    
    @staticmethod
    def create_checkin_selector(queryset=None):
        """Create check-in selector."""
        return CheckInSelector(queryset or DailyCheckIn.objects.all())
    
    @staticmethod
    def create_spin_selector(queryset=None):
        """Create spin selector."""
        return SpinWheelSelector(queryset or SpinWheel.objects.all())
    
    @staticmethod
    def create_quest_selector(queryset=None):
        """Create quest selector."""
        return UserQuestSelector(queryset or UserQuest.objects.all())
    
    @staticmethod
    def create_achievement_selector(queryset=None):
        """Create achievement selector."""
        return UserAchievementSelector(queryset or UserAchievement.objects.all())
    
    @staticmethod
    def create_shop_selector(queryset=None):
        """Create shop selector."""
        return ShopPurchaseSelector(queryset or ShopPurchase.objects.all())
    
    @staticmethod
    def create_leaderboard_selector(queryset=None):
        """Create leaderboard selector."""
        return LeaderboardSelector(queryset or Leaderboard.objects.all())
    
    @staticmethod
    def create_notification_selector(queryset=None):
        """Create notification selector."""
        return NotificationSelector(queryset or Notification.objects.all())


# ── Selector Utilities ─────────────────────────────────────────────────────

class SelectorUtils:
    """Utility functions for selectors."""
    
    @staticmethod
    def build_date_range_filter(field, start_date, end_date=None):
        """Build date range filter."""
        filter_kwargs = {f"{field}__gte": start_date}
        if end_date:
            filter_kwargs[f"{field}__lte"] = end_date
        return Q(**filter_kwargs)
    
    @staticmethod
    def build_user_filter(user_field='user'):
        """Build user filter."""
        return Q(**{user_field: user}) if user else Q()
    
    @staticmethod
    def build_tenant_filter(tenant_field='tenant'):
        """Build tenant filter."""
        return Q(**{tenant_field: tenant}) if tenant else Q()
    
    @staticmethod
    def apply_pagination(queryset, page=1, page_size=20):
        """Apply pagination to queryset."""
        offset = (page - 1) * page_size
        return queryset[offset:offset + page_size]
    
    @staticmethod
    def apply_ordering(queryset, order_by='-created_at'):
        """Apply ordering to queryset."""
        return queryset.order_by(order_by)
    
    @staticmethod
    def apply_select_related(queryset, *fields):
        """Apply select_related to queryset."""
        return queryset.select_related(*fields)
    
    @staticmethod
    def apply_prefetch_related(queryset, *fields):
        """Apply prefetch_related to queryset."""
        return queryset.prefetch_related(*fields)
    
    @staticmethod
    def apply_annotations(queryset, **annotations):
        """Apply annotations to queryset."""
        return queryset.annotate(**annotations)
    
    @staticmethod
    def apply_aggregation(queryset, aggregation_func, field):
        """Apply aggregation to queryset."""
        return queryset.aggregate(**{field: aggregation_func(field)})


# ── Advanced Selectors ─────────────────────────────────────────────────────

class AnalyticsSelector(BaseSelector):
    """Selector for analytics data."""
    
    def filter(self, event_type=None, user=None, tenant=None,
                date_from=None, date_to=None, **kwargs) -> 'AnalyticsSelector':
        """Apply filters to analytics data."""
        if event_type:
            self.queryset = self.queryset.filter(event_type=event_type)
        
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        if date_from:
            self.queryset = self.queryset.filter(created_at__date__gte=date_from)
        
        if date_to:
            self.queryset = self.queryset.filter(created_at__date__lte=date_to)
        
        return self
    
    def by_period(self, period='day'):
        """Group by time period."""
        if period == 'hour':
            return self.execute().annotate(period=TruncHour('created_at'))
        elif period == 'day':
            return self.execute().annotate(period=TruncDay('created_at'))
        elif period == 'week':
            return self.execute().annotate(period=TruncWeek('created_at'))
        elif period == 'month':
            return self.execute().annotate(period=TruncMonth('created_at'))
        else:
            return self.execute().annotate(period=TruncDay('created_at'))
    
    def execute(self) -> QuerySet:
        """Execute the query."""
        return self.queryset


class SearchSelector(BaseSelector):
    """Selector for search operations."""
    
    def filter(self, query=None, models=None, user=None, tenant=None,
                **kwargs) -> 'SearchSelector':
        """Apply search filters."""
        if query:
            # Build search query
            search_fields = self._get_search_fields(models)
            q_objects = []
            
            for field in search_fields:
                q_objects.append(Q(**{f"{field}__icontains": query}))
            
            combined_q = Q()
            for q_obj in q_objects:
                combined_q |= q_obj
            
            self.queryset = self.queryset.filter(combined_q)
        
        if user:
            self.queryset = self.queryset.filter(user=user)
        
        if tenant:
            self.queryset = self.queryset.filter(tenant=tenant)
        
        return self
    
    def _get_search_fields(self, models):
        """Get search fields for models."""
        search_fields = {
            'checkins': ['user__username', 'note'],
            'spins': ['user__username'],
            'quests': ['user__username', 'quest__name', 'quest__description'],
            'achievements': ['user__username', 'achievement__name', 'achievement__description'],
            'shop_items': ['name', 'description'],
            'shop_purchases': ['user__username', 'item__name'],
            'leaderboard': ['user__username'],
            'feed_items': ['user__username', 'title', 'body'],
            'notifications': ['title', 'body'],
            'referrals': ['referrer__username', 'referred__username', 'referral_code'],
        }
        
        all_fields = []
        if models:
            for model in models:
                if model in search_fields:
                    all_fields.extend(search_fields[model])
        else:
            for model_fields in search_fields.values():
                all_fields.extend(model_fields)
        
        return all_fields
    
    def execute(self) -> QuerySet:
        """Execute the search query."""
        return self.queryset


# ── Composite Selectors ─────────────────────────────────────────────────────

class CompositeSelector:
    """Composite selector for combining multiple queries."""
    
    def __init__(self, selectors):
        self.selectors = selectors
    
    def execute(self):
        """Execute all selectors and return combined results."""
        results = {}
        
        for name, selector in self.selectors.items():
            results[name] = selector.execute()
        
        return results
    
    def count(self):
        """Get total count across all selectors."""
        total_count = 0
        
        for selector in self.selectors.values():
            total_count += selector.count()
        
        return total_count
    
    def exists(self):
        """Check if any results exist across all selectors."""
        return any(selector.exists() for selector in self.selectors.values())


class UserEngagementCompositeSelector(CompositeSelector):
    """Composite selector for user engagement data."""
    
    def __init__(self, user, tenant=None):
        # Create individual selectors
        checkin_selector = SelectorFactory.create_checkin_selector()
        spin_selector = SelectorFactory.create_spin_selector()
        quest_selector = SelectorFactory.create_quest_selector()
        achievement_selector = SelectorFactory.create_achievement_selector()
        shop_selector = SelectorFactory.create_shop_selector()
        notification_selector = SelectorFactory.create_notification_selector()
        
        # Apply user filter to all selectors
        checkin_selector.filter(user=user, tenant=tenant)
        spin_selector.filter(user=user, tenant=tenant)
        quest_selector.filter(user=user, tenant=tenant)
        achievement_selector.filter(user=user, tenant=tenant)
        shop_selector.filter(user=user, tenant=tenant)
        notification_selector.filter(user=user, tenant=tenant)
        
        super().__init__({
            'checkins': checkin_selector,
            'spins': spin_selector,
            'quests': quest_selector,
            'achievements': achievement_selector,
            'purchases': shop_selector,
            'notifications': notification_selector,
        })
    
    def get_summary_stats(self):
        """Get summary statistics for user engagement."""
        results = self.execute()
        
        summary = {
            'total_checkins': results['checkins'].count(),
            'total_spins': results['spins'].count(),
            'total_quests': results['quests'].count(),
            'total_achievements': results['achievements'].count(),
            'total_purchases': results['purchases'].count(),
            'unread_notifications': results['notifications'].filter(is_read=False).count(),
        }
        
        return summary
