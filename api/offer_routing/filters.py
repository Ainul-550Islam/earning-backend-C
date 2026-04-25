"""
Custom Filters for Offer Routing System
"""

import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from .models import (
    OfferRoute, RouteCondition, GeoRouteRule, DeviceRouteRule,
    UserSegmentRule, TimeRouteRule, BehaviorRouteRule,
    OfferScore, RoutingABTest, FallbackRule,
    UserOfferCap, RoutingDecisionLog
)
from .choices import (
    RouteConditionType, RouteOperator, ActionType,
    UserSegmentType, DeviceType, OSType, BrowserType,
    CapType, FallbackType, ABTestVariant,
    OfferStatus, RoutingPriority
)


class OfferRouteFilter(django_filters.FilterSet):
    """Filter for offer routes."""
    
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    priority = django_filters.NumberFilter()
    tenant = django_filters.NumberFilter(field_name='tenant__id')
    
    class Meta:
        model = OfferRoute
        fields = ['name', 'description', 'is_active', 'priority', 'tenant']
        ordering = ['priority', 'name']


class RouteConditionFilter(django_filters.FilterSet):
    """Filter for route conditions."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    condition_type = django_filters.ChoiceFilter(choices=RouteConditionType.CHOICES)
    operator = django_filters.ChoiceFilter(choices=RouteOperator.CHOICES)
    field_name = django_filters.CharFilter(lookup_expr='icontains')
    value = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = RouteCondition
        fields = ['route', 'condition_type', 'operator', 'field_name', 'value']
        ordering = ['route', 'condition_type', 'field_name']


class GeoRuleFilter(django_filters.FilterSet):
    """Filter for geographic routing rules."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    country = django_filters.CharFilter(lookup_expr='icontains')
    region = django_filters.CharFilter(lookup_expr='icontains')
    city = django_filters.CharFilter(lookup_expr='icontains')
    is_include = django_filters.BooleanFilter()
    
    class Meta:
        model = GeoRouteRule
        fields = ['route', 'country', 'region', 'city', 'is_include']
        ordering = ['route', 'country', 'region']


class DeviceRuleFilter(django_filters.FilterSet):
    """Filter for device routing rules."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    device_type = django_filters.ChoiceFilter(choices=DeviceType.CHOICES)
    os_type = django_filters.ChoiceFilter(choices=OSType.CHOICES)
    browser = django_filters.ChoiceFilter(choices=BrowserType.CHOICES)
    is_include = django_filters.BooleanFilter()
    
    class Meta:
        model = DeviceRouteRule
        fields = ['route', 'device_type', 'os_type', 'browser', 'is_include']
        ordering = ['route', 'device_type', 'os_type']


class UserSegmentFilter(django_filters.FilterSet):
    """Filter for user segment rules."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    segment_type = django_filters.ChoiceFilter(choices=UserSegmentType.CHOICES)
    value = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = UserSegmentRule
        fields = ['route', 'segment_type', 'value']
        ordering = ['route', 'segment_type']


class TimeRuleFilter(django_filters.FilterSet):
    """Filter for time-based routing rules."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    day_of_week = django_filters.NumberFilter()
    hour_from = django_filters.NumberFilter()
    hour_to = django_filters.NumberFilter()
    timezone = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = TimeRouteRule
        fields = ['route', 'day_of_week', 'hour_from', 'hour_to', 'timezone']
        ordering = ['route', 'day_of_week', 'hour_from']


class BehaviorRuleFilter(django_filters.FilterSet):
    """Filter for behavioral routing rules."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    event_type = django_filters.CharFilter(lookup_expr='icontains')
    min_count = django_filters.NumberFilter()
    window_days = django_filters.NumberFilter()
    
    class Meta:
        model = BehaviorRouteRule
        fields = ['route', 'event_type', 'min_count', 'window_days']
        ordering = ['route', 'event_type', 'min_count']


class OfferScoreFilter(django_filters.FilterSet):
    """Filter for offer scores."""
    
    offer = django_filters.NumberFilter(field_name='offer__id')
    user = django_filters.NumberFilter(field_name='user__id')
    score_min = django_filters.NumberFilter()
    score_max = django_filters.NumberFilter()
    scored_at_from = django_filters.DateTimeFilter()
    scored_at_to = django_filters.DateTimeFilter()
    
    class Meta:
        model = OfferScore
        fields = ['offer', 'user', 'score', 'scored_at']
        ordering = ['-scored_at', 'score']


class ABTestFilter(django_filters.FilterSet):
    """Filter for A/B tests."""
    
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    started_at_from = django_filters.DateTimeFilter()
    started_at_to = django_filters.DateTimeFilter()
    tenant = django_filters.NumberFilter(field_name='tenant__id')
    
    class Meta:
        model = RoutingABTest
        fields = ['name', 'is_active', 'started_at', 'tenant']
        ordering = ['-started_at', 'name']


class FallbackRuleFilter(django_filters.FilterSet):
    """Filter for fallback rules."""
    
    name = django_filters.CharFilter(lookup_expr='icontains')
    priority = django_filters.NumberFilter()
    fallback_type = django_filters.ChoiceFilter(choices=FallbackType.CHOICES)
    tenant = django_filters.NumberFilter(field_name='tenant__id')
    
    class Meta:
        model = FallbackRule
        fields = ['name', 'priority', 'fallback_type', 'tenant']
        ordering = ['priority', 'name']


class OfferCapFilter(django_filters.FilterSet):
    """Filter for offer caps."""
    
    offer = django_filters.NumberFilter(field_name='offer__id')
    user = django_filters.NumberFilter(field_name='user__id')
    cap_type = django_filters.ChoiceFilter(choices=CapType.CHOICES)
    current_count = django_filters.NumberFilter()
    reset_at_from = django_filters.DateTimeFilter()
    reset_at_to = django_filters.DateTimeFilter()
    
    class Meta:
        model = UserOfferCap
        fields = ['offer', 'user', 'cap_type', 'current_count', 'reset_at']
        ordering = ['-reset_at', 'offer', 'cap_type']


class RoutingDecisionFilter(django_filters.FilterSet):
    """Filter for routing decisions."""
    
    user = django_filters.NumberFilter(field_name='user__id')
    route = django_filters.NumberFilter(field_name='route__id')
    offer = django_filters.NumberFilter(field_name='offer__id')
    reason = django_filters.ChoiceFilter(choices=[
        ('route_match', 'Route Match'),
        ('condition_evaluation', 'Condition Evaluation'),
        ('score_calculation', 'Score Calculation'),
        ('personalization', 'Personalization'),
        ('cap_enforcement', 'Cap Enforcement'),
        ('fallback', 'Fallback'),
        ('ab_test', 'A/B Test'),
        ('cache_hit', 'Cache Hit')
    ])
    created_at_from = django_filters.DateTimeFilter()
    created_at_to = django_filters.DateTimeFilter()
    cache_hit = django_filters.BooleanFilter()
    
    class Meta:
        model = RoutingDecisionLog
        fields = ['user', 'route', 'offer', 'reason', 'created_at', 'cache_hit']
        ordering = ['-created_at', 'user', 'route']


class AdvancedRouteFilter(django_filters.FilterSet):
    """Advanced filter for complex route queries."""
    
    # Base filters
    name = django_filters.CharFilter(method='filter_name')
    description = django_filters.CharFilter(method='filter_description')
    is_active = django_filters.BooleanFilter(method='filter_active')
    priority_min = django_filters.NumberFilter(method='filter_priority_min')
    priority_max = django_filters.NumberFilter(method='filter_priority_max')
    
    # Date range filters
    created_at_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    updated_at_from = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')
    updated_at_to = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    # Tenant filter
    tenant = django_filters.NumberFilter(field_name='tenant__id')
    
    class Meta:
        model = OfferRoute
        fields = ['name', 'description', 'is_active', 'priority', 'created_at', 'updated_at', 'tenant']
        ordering = ['priority', 'name', 'created_at']
    
    def filter_name(self, queryset, name, value):
        """Filter by name with case-insensitive search."""
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))
    
    def filter_description(self, queryset, name, value):
        """Filter by description with case-insensitive search."""
        if not value:
            return queryset
        return queryset.filter(description__icontains=value)
    
    def filter_active(self, queryset, name, value):
        """Filter by active status."""
        if value is None:
            return queryset
        return queryset.filter(is_active=value)
    
    def filter_priority_min(self, queryset, name, value):
        """Filter by minimum priority."""
        if value is None:
            return queryset
        return queryset.filter(priority__gte=value)
    
    def filter_priority_max(self, queryset, name, value):
        """Filter by maximum priority."""
        if value is None:
            return queryset
        return queryset.filter(priority__lte=value)


class PerformanceStatsFilter(django_filters.FilterSet):
    """Filter for performance statistics."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    date_from = django_filters.DateTimeFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='date', lookup_expr='lte')
    impressions_min = django_filters.NumberFilter(field_name='impressions', lookup_expr='gte')
    impressions_max = django_filters.NumberFilter(field_name='impressions', lookup_expr='lte')
    conversions_min = django_filters.NumberFilter(field_name='conversions', lookup_expr='gte')
    conversions_max = django_filters.NumberFilter(field_name='conversions', lookup_expr='lte')
    revenue_min = django_filters.NumberFilter(field_name='revenue', lookup_expr='gte')
    revenue_max = django_filters.NumberFilter(field_name='revenue', lookup_expr='lte')
    
    class Meta:
        model = RoutePerformanceStat
        fields = ['route', 'date', 'impressions', 'conversions', 'revenue']
        ordering = ['-date', 'route']


class UserBehaviorFilter(django_filters.FilterSet):
    """Filter for user behavior analysis."""
    
    user = django_filters.NumberFilter(field_name='user__id')
    event_type = django_filters.ChoiceFilter(choices=[
        ('page_view', 'Page View'),
        ('click', 'Click'),
        ('purchase', 'Purchase'),
        ('add_to_cart', 'Add to Cart'),
        ('search', 'Search'),
        ('login', 'Login'),
        ('signup', 'Signup')
    ])
    created_at_from = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_at_to = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = RoutingDecisionLog
        fields = ['user', 'event_type', 'created_at']
        ordering = ['-created_at', 'user']


class ConversionRateFilter(django_filters.FilterSet):
    """Filter for conversion rate analysis."""
    
    route = django_filters.NumberFilter(field_name='route__id')
    conversion_rate_min = django_filters.NumberFilter(method='filter_conversion_rate_min')
    conversion_rate_max = django_filters.NumberFilter(method='filter_conversion_rate_max')
    date_from = django_filters.DateTimeFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateTimeFilter(field_name='date', lookup_expr='lte')
    
    class Meta:
        model = RoutePerformanceStat
        fields = ['route', 'conversion_rate', 'date']
        ordering = ['-date', 'conversion_rate']
    
    def filter_conversion_rate_min(self, queryset, name, value):
        """Filter by minimum conversion rate."""
        if value is None:
            return queryset
        return queryset.filter(conversions__gte=F('impressions') * (value / 100))
    
    def filter_conversion_rate_max(self, queryset, name, value):
        """Filter by maximum conversion rate."""
        if value is None:
            return queryset
        return queryset.filter(conversions__lte=F('impressions') * (value / 100))


class CachePerformanceFilter(django_filters.FilterSet):
    """Filter for cache performance metrics."""
    
    cache_hit_rate_min = django_filters.NumberFilter(method='filter_cache_hit_rate_min')
    cache_hit_rate_max = django_filters.NumberFilter(method='filter_cache_hit_rate_max')
    avg_response_time_min = django_filters.NumberFilter(method='filter_avg_response_time_min')
    avg_response_time_max = django_filters.NumberFilter(method='filter_avg_response_time_max')
    
    class Meta:
        model = RoutingDecisionLog
        fields = ['cache_hit', 'response_time_ms']
        ordering = ['-created_at']
    
    def filter_cache_hit_rate_min(self, queryset, name, value):
        """Filter by minimum cache hit rate."""
        if value is None:
            return queryset
        return queryset.filter(cache_hit=True).count() / queryset.count() >= (value / 100)
    
    def filter_cache_hit_rate_max(self, queryset, name, value):
        """Filter by maximum cache hit rate."""
        if value is None:
            return queryset
        return queryset.filter(cache_hit=True).count() / queryset.count() <= (value / 100)
    
    def filter_avg_response_time_min(self, queryset, name, value):
        """Filter by minimum average response time."""
        if value is None:
            return queryset
        return queryset.filter(response_time_ms__gte=value)
    
    def filter_avg_response_time_max(self, queryset, name, value):
        """Filter by maximum average response time."""
        if value is None:
            return queryset
        return queryset.filter(response_time_ms__lte=value)


class TenantRouteFilter(django_filters.FilterSet):
    """Filter for tenant-specific routes."""
    
    tenant = django_filters.NumberFilter(field_name='tenant__id')
    is_active = django_filters.BooleanFilter()
    has_conditions = django_filters.BooleanFilter(method='filter_has_conditions')
    has_actions = django_filters.BooleanFilter(method='filter_has_actions')
    offer_count_min = django_filters.NumberFilter(method='filter_offer_count_min')
    offer_count_max = django_filters.NumberFilter(method='filter_offer_count_max')
    
    class Meta:
        model = OfferRoute
        fields = ['tenant', 'is_active', 'has_conditions', 'has_actions', 'offer_count']
        ordering = ['priority', 'name']
    
    def filter_has_conditions(self, queryset, name, value):
        """Filter routes that have conditions."""
        if value is None:
            return queryset
        if value:
            return queryset.filter(conditions__isnull=False).distinct()
        else:
            return queryset.filter(conditions__isnull=True).distinct()
    
    def filter_has_actions(self, queryset, name, value):
        """Filter routes that have actions."""
        if value is None:
            return queryset
        if value:
            return queryset.filter(actions__isnull=False).distinct()
        else:
            return queryset.filter(actions__isnull=True).distinct()
    
    def filter_offer_count_min(self, queryset, name, value):
        """Filter by minimum number of offers."""
        if value is None:
            return queryset
        return queryset.annotate(offer_count=Count('offers')).filter(offer_count__gte=value)
    
    def filter_offer_count_max(self, queryset, name, value):
        """Filter by maximum number of offers."""
        if value is None:
            return queryset
        return queryset.annotate(offer_count=Count('offers')).filter(offer_count__lte=value)


# Custom filter methods
def filter_by_date_range(queryset, field_name, start_date, end_date):
    """Filter queryset by date range."""
    if start_date and end_date:
        return queryset.filter(**{
            f'{field_name}__gte': start_date,
            f'{field_name}__lte': end_date
        })
    elif start_date:
        return queryset.filter(**{f'{field_name}__gte': start_date})
    elif end_date:
        return queryset.filter(**{f'{field_name}__lte': end_date})
    return queryset


def filter_by_score_range(queryset, min_score, max_score):
    """Filter queryset by score range."""
    if min_score is not None:
        queryset = queryset.filter(score__gte=min_score)
    if max_score is not None:
        queryset = queryset.filter(score__lte=max_score)
    return queryset


def filter_by_user_segment(queryset, user_id, segment_type):
    """Filter queryset by user segment."""
    from .models import UserSegmentRule
    
    if not user_id or not segment_type:
        return queryset
    
    # Get user's segment value for the given type
    try:
        segment_rule = UserSegmentRule.objects.filter(
            route__is_active=True,
            segment_type=segment_type
        ).first()
        
        if not segment_rule:
            return queryset
        
        # This would implement actual segment evaluation logic
        # For now, return queryset as is
        return queryset
    except Exception:
        return queryset


def filter_by_device_info(queryset, device_type, os_type, browser):
    """Filter queryset by device information."""
    if device_type:
        queryset = queryset.filter(device_type=device_type)
    if os_type:
        queryset = queryset.filter(os_type=os_type)
    if browser:
        queryset = queryset.filter(browser=browser)
    
    return queryset


def filter_by_geo_location(queryset, country, region, city):
    """Filter queryset by geographic location."""
    if country:
        queryset = queryset.filter(country=country)
    if region:
        queryset = queryset.filter(region=region)
    if city:
        queryset = queryset.filter(city=city)
    
    return queryset


def filter_by_time_window(queryset, current_hour, day_of_week):
    """Filter queryset by time window."""
    from .models import TimeRouteRule
    
    if not current_hour:
        return queryset
    
    # Get time-based rules
    time_rules = TimeRouteRule.objects.filter(is_active=True)
    
    for rule in time_rules:
        if rule.matches_time(current_hour, day_of_week):
            # Apply rule logic (would be more complex in real implementation)
            pass
    
    return queryset


def filter_by_behavior_pattern(queryset, user_id, event_type, min_count, window_days):
    """Filter queryset by behavioral pattern."""
    if not user_id:
        return queryset
    
    # This would implement actual behavioral pattern matching
    # For now, return queryset as is
    return queryset


def apply_performance_filters(queryset, min_impressions, min_conversions, min_revenue):
    """Apply performance-based filters."""
    if min_impressions:
        queryset = queryset.filter(impressions__gte=min_impressions)
    if min_conversions:
        queryset = queryset.filter(conversions__gte=min_conversions)
    if min_revenue:
        queryset = queryset.filter(revenue__gte=min_revenue)
    
    return queryset


def get_top_performing_routes(queryset, metric='conversions', limit=10):
    """Get top performing routes by metric."""
    return queryset.order_by(f'-{metric}')[:limit]


def get_underperforming_routes(queryset, metric='conversions', threshold=0.01):
    """Get underperforming routes below threshold."""
    return queryset.filter(**{f'{metric}__lt': threshold})


def filter_by_ab_test_status(queryset, is_active=None, has_winner=None):
    """Filter A/B tests by status."""
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if has_winner is not None:
        queryset = queryset.filter(winner_declared_at__isnull=not has_winner)
    
    return queryset


def filter_by_fallback_priority(queryset, min_priority=None, max_priority=None):
    """Filter fallback rules by priority range."""
    if min_priority:
        queryset = queryset.filter(priority__gte=min_priority)
    if max_priority:
        queryset = queryset.filter(priority__lte=max_priority)
    
    return queryset.order_by('priority')
