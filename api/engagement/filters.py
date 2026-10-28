# engagement/filters.py
"""
Custom Django filters for engagement system.
Includes model filters, API filters, and utility filter functions.
"""
import django_filters
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework import filters

from .models.checkin import DailyCheckIn
from .models.spinwheel import SpinWheel
from .models.achievement import UserAchievement, Achievement
from .models.quest import UserQuest, Quest
from .models.leaderboard import Leaderboard, LeaderboardSeason
from .models.social import FeedItem, Friendship
from .models.shop import ShopPurchase, ShopItem
from .choices import (
    QUEST_STATUS_CHOICES, ACHIEVEMENT_DIFFICULTY_CHOICES,
    SHOP_ITEM_TYPE_CHOICES, NOTIFICATION_TYPE_CHOICES
)


class DailyCheckInFilter(django_filters.FilterSet):
    """
    Filter for DailyCheckIn model.
    """
    date = django_filters.DateFilter(field_name='date', lookup_expr='exact')
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    user = django_filters.NumberFilter(field_name='user__id')
    streak_min = django_filters.NumberFilter(method='filter_streak_min')
    streak_max = django_filters.NumberFilter(method='filter_streak_max')
    coins_min = django_filters.NumberFilter(method='filter_coins_min')
    coins_max = django_filters.NumberFilter(method='filter_coins_max')
    has_bonus = django_filters.BooleanFilter(method='filter_has_bonus')
    shield_used = django_filters.BooleanFilter(field_name='streak_shield_used')
    
    class Meta:
        model = DailyCheckIn
        fields = ['user', 'date', 'streak_shield_used', 'bonus_claimed', 'reward_claimed']
    
    def filter_streak_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(consecutive_days__gte=value)
        return queryset
    
    def filter_streak_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(consecutive_days__lte=value)
        return queryset
    
    def filter_coins_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_earned__gte=value)
        return queryset
    
    def filter_coins_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_earned__lte=value)
        return queryset
    
    def filter_has_bonus(self, queryset, name, value):
        if value is True:
            return queryset.filter(bonus_claimed=True)
        elif value is False:
            return queryset.filter(bonus_claimed=False)
        return queryset


class SpinWheelFilter(django_filters.FilterSet):
    """
    Filter for SpinWheel model.
    """
    spun_at = django_filters.DateTimeFilter(field_name='spun_at', lookup_expr='exact')
    spun_at_from = django_filters.DateTimeFilter(field_name='spun_at', lookup_expr='gte')
    spun_at_to = django_filters.DateTimeFilter(field_name='spun_at', lookup_expr='lte')
    user = django_filters.NumberFilter(field_name='user__id')
    coins_min = django_filters.NumberFilter(method='filter_coins_min')
    coins_max = django_filters.NumberFilter(method='filter_coins_max')
    is_boosted = django_filters.BooleanFilter(field_name='is_boosted')
    outcome_idx = django_filters.NumberFilter(field_name='outcome_idx')
    today_only = django_filters.BooleanFilter(method='filter_today_only')
    
    class Meta:
        model = SpinWheel
        fields = ['user', 'is_boosted', 'outcome_idx']
    
    def filter_coins_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_won__gte=value)
        return queryset
    
    def filter_coins_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_won__lte=value)
        return queryset
    
    def filter_today_only(self, queryset, name, value):
        if value is True:
            today = timezone.now().date()
            return queryset.filter(spun_at__date=today)
        return queryset


class UserAchievementFilter(django_filters.FilterSet):
    """
    Filter for UserAchievement model.
    """
    user = django_filters.NumberFilter(field_name='user__id')
    achievement = django_filters.NumberFilter(field_name='achievement__id')
    difficulty = django_filters.ChoiceFilter(
        field_name='achievement__difficulty',
        choices=ACHIEVEMENT_DIFFICULTY_CHOICES
    )
    unlocked_from = django_filters.DateTimeFilter(field_name='unlocked_at', lookup_expr='gte')
    unlocked_to = django_filters.DateTimeFilter(field_name='unlocked_at', lookup_expr='lte')
    is_unlocked = django_filters.BooleanFilter(method='filter_is_unlocked')
    achievement_type = django_filters.ChoiceFilter(
        field_name='achievement__type',
        choices=[('streak', 'Streak'), ('total', 'Total'), ('level', 'Level'), ('social', 'Social')]
    )
    
    class Meta:
        model = UserAchievement
        fields = ['user', 'achievement', 'unlocked_at']
    
    def filter_is_unlocked(self, queryset, name, value):
        if value is True:
            return queryset.filter(unlocked_at__isnull=False)
        elif value is False:
            return queryset.filter(unlocked_at__isnull=True)
        return queryset


class UserQuestFilter(django_filters.FilterSet):
    """
    Filter for UserQuest model.
    """
    user = django_filters.NumberFilter(field_name='user__id')
    quest = django_filters.NumberFilter(field_name='quest__id')
    status = django_filters.ChoiceFilter(choices=QUEST_STATUS_CHOICES)
    quest_type = django_filters.ChoiceFilter(
        field_name='quest__type',
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('special', 'Special')]
    )
    created_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    completed_from = django_filters.DateTimeFilter(field_name='completed_at', lookup_expr='gte')
    completed_to = django_filters.DateTimeFilter(field_name='completed_at', lookup_expr='lte')
    expires_soon = django_filters.BooleanFilter(method='filter_expires_soon')
    
    class Meta:
        model = UserQuest
        fields = ['user', 'quest', 'status', 'created_at', 'completed_at']
    
    def filter_expires_soon(self, queryset, name, value):
        if value is True:
            soon = timezone.now() + timedelta(hours=24)
            return queryset.filter(
                expires_at__lte=soon,
                expires_at__gt=timezone.now(),
                status__in=['available', 'active']
            )
        return queryset


class LeaderboardFilter(django_filters.FilterSet):
    """
    Filter for Leaderboard model.
    """
    date = django_filters.DateFilter(field_name='date', lookup_expr='exact')
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    season = django_filters.NumberFilter(field_name='season__id')
    rank_min = django_filters.NumberFilter(method='filter_rank_min')
    rank_max = django_filters.NumberFilter(method='filter_rank_max')
    coins_min = django_filters.NumberFilter(method='filter_coins_min')
    coins_max = django_filters.NumberFilter(method='filter_coins_max')
    xp_min = django_filters.NumberFilter(method='filter_xp_min')
    xp_max = django_filters.NumberFilter(method='filter_xp_max')
    rewarded = django_filters.BooleanFilter(field_name='reward_distributed')
    
    class Meta:
        model = Leaderboard
        fields = ['date', 'season', 'rank', 'reward_distributed']
    
    def filter_rank_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(rank__gte=value)
        return queryset
    
    def filter_rank_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(rank__lte=value)
        return queryset
    
    def filter_coins_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(total_coins_earned__gte=value)
        return queryset
    
    def filter_coins_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(total_coins_earned__lte=value)
        return queryset
    
    def filter_xp_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(total_xp_earned__gte=value)
        return queryset
    
    def filter_xp_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(total_xp_earned__lte=value)
        return queryset


class FeedItemFilter(django_filters.FilterSet):
    """
    Filter for FeedItem model.
    """
    user = django_filters.NumberFilter(field_name='user__id')
    feed_type = django_filters.ChoiceFilter(
        choices=[('achievement', 'Achievement'), ('level_up', 'Level Up'), ('streak_milestone', 'Streak Milestone')]
    )
    created_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    has_likes = django_filters.BooleanFilter(method='filter_has_likes')
    has_comments = django_filters.BooleanFilter(method='filter_has_comments')
    
    class Meta:
        model = FeedItem
        fields = ['user', 'feed_type', 'created_at']
    
    def filter_has_likes(self, queryset, name, value):
        if value is True:
            return queryset.filter(likes_count__gt=0)
        elif value is False:
            return queryset.filter(likes_count=0)
        return queryset
    
    def filter_has_comments(self, queryset, name, value):
        if value is True:
            return queryset.filter(comments_count__gt=0)
        elif value is False:
            return queryset.filter(comments_count=0)
        return queryset


class ShopPurchaseFilter(django_filters.FilterSet):
    """
    Filter for ShopPurchase model.
    """
    user = django_filters.NumberFilter(field_name='user__id')
    item = django_filters.NumberFilter(field_name='item__id')
    item_type = django_filters.ChoiceFilter(
        field_name='item__type',
        choices=SHOP_ITEM_TYPE_CHOICES
    )
    status = django_filters.ChoiceFilter(
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')]
    )
    purchased_from = django_filters.DateTimeFilter(field_name='purchased_at', lookup_expr='gte')
    purchased_to = django_filters.DateTimeFilter(field_name='purchased_at', lookup_expr='lte')
    amount_min = django_filters.NumberFilter(method='filter_amount_min')
    amount_max = django_filters.NumberFilter(method='filter_amount_max')
    
    class Meta:
        model = ShopPurchase
        fields = ['user', 'item', 'status', 'purchased_at']
    
    def filter_amount_min(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_spent__gte=value)
        return queryset
    
    def filter_amount_max(self, queryset, name, value):
        if value is not None:
            return queryset.filter(coins_spent__lte=value)
        return queryset


# ── Custom Filter Backends ─────────────────────────────────────────────────────

class EngagementFilterBackend(filters.BaseFilterBackend):
    """
    Custom filter backend for engagement system.
    Adds common filtering capabilities.
    """
    
    def filter_queryset(self, request, queryset, view):
        """
        Filter queryset based on request parameters.
        """
        # Filter by tenant if available
        if hasattr(request.user, 'tenant') and request.user.tenant:
            queryset = queryset.filter(tenant=request.user.tenant)
        
        # Filter by user if not admin
        if not request.user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=request.user)
        
        # Apply date range filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                if hasattr(queryset.model, 'created_at'):
                    queryset = queryset.filter(created_at__date__gte=date_from)
                elif hasattr(queryset.model, 'date'):
                    queryset = queryset.filter(date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                if hasattr(queryset.model, 'created_at'):
                    queryset = queryset.filter(created_at__date__lte=date_to)
                elif hasattr(queryset.model, 'date'):
                    queryset = queryset.filter(date__lte=date_to)
            except ValueError:
                pass
        
        return queryset


class SearchFilter(filters.SearchFilter):
    """
    Enhanced search filter for engagement models.
    """
    
    def get_search_terms(self, request):
        """
        Get search terms from request.
        """
        params = request.query_params.get(self.search_param, '')
        return params.split(',')

    def filter_queryset(self, request, queryset, view):
        """
        Filter queryset using search terms.
        """
        search_fields = self.get_search_fields(view)
        search_terms = self.get_search_terms(request)
        
        if not search_fields or not search_terms:
            return queryset
        
        conditions = Q()
        for search_term in search_terms:
            for field in search_fields:
                conditions |= Q(**{f"{field}__icontains": search_term})
        
        return queryset.filter(conditions).distinct()


class OrderingFilter(filters.OrderingFilter):
    """
    Enhanced ordering filter for engagement models.
    """
    
    def get_valid_fields(self, queryset, view, context=None):
        """
        Get valid fields for ordering.
        """
        valid_fields = super().get_valid_fields(queryset, view, context)
        
        # Add common ordering fields
        common_fields = [
            'created_at',
            'updated_at',
            'id',
        ]
        
        for field in common_fields:
            if hasattr(queryset.model, field):
                valid_fields.append((field, field))
        
        return valid_fields


# ── Utility Filter Functions ───────────────────────────────────────────────────

def filter_by_date_range(queryset, date_field, start_date, end_date):
    """
    Filter queryset by date range.
    """
    if start_date:
        queryset = queryset.filter(**{f"{date_field}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{date_field}__lte": end_date})
    return queryset


def filter_by_user_queryset(queryset, user, allow_staff=False):
    """
    Filter queryset by user with staff option.
    """
    if allow_staff and user.is_staff:
        return queryset
    return queryset.filter(user=user)


def filter_by_tenant_queryset(queryset, tenant):
    """
    Filter queryset by tenant.
    """
    if tenant and hasattr(queryset.model, 'tenant'):
        return queryset.filter(tenant=tenant)
    return queryset


def filter_active_objects(queryset, active_field='is_active'):
    """
    Filter for only active objects.
    """
    if hasattr(queryset.model, active_field):
        return queryset.filter(**{active_field: True})
    return queryset


def filter_with_annotations(queryset, annotations=None):
    """
    Add annotations to queryset.
    """
    if annotations:
        queryset = queryset.annotate(**annotations)
    return queryset


# ── Filter Mixins ───────────────────────────────────────────────────────────

class TenantFilterMixin:
    """
    Mixin for views that need tenant filtering.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if hasattr(user, 'tenant') and user.tenant:
            queryset = queryset.filter(tenant=user.tenant)
        
        return queryset


class UserFilterMixin:
    """
    Mixin for views that need user filtering.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=user)
        
        return queryset


class DateRangeFilterMixin:
    """
    Mixin for views that need date range filtering.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = filter_by_date_range(queryset, 'created_at', date_from, None)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = filter_by_date_range(queryset, 'created_at', None, date_to)
            except ValueError:
                pass
        
        return queryset


class ActiveFilterMixin:
    """
    Mixin for views that need active object filtering.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return filter_active_objects(queryset)


# ── Combined Filter Classes ───────────────────────────────────────────────────

class EngagementFilterMixin(
    TenantFilterMixin,
    UserFilterMixin,
    DateRangeFilterMixin,
    ActiveFilterMixin
):
    """
    Combined filter mixin for engagement views.
    """
    pass


class AnalyticsFilterMixin:
    """
    Mixin for analytics views with enhanced filtering.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Add period-based filtering
        period = self.request.query_params.get('period', 'daily')
        if period == 'today':
            queryset = queryset.filter(created_at__date=timezone.now().date())
        elif period == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(created_at__gte=week_ago)
        elif period == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            queryset = queryset.filter(created_at__gte=month_ago)
        
        return queryset
