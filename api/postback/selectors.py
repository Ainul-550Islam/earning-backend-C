"""
selectors.py – Data selectors for postback module.

Provides comprehensive selector functionality including:
- Data query selectors
- Business logic selectors
- Analytics selectors
- Performance-optimized selectors
"""
import logging
from typing import Dict, List, Optional, Any, Union, Type
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Expression, FloatField
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason
from .querysets import PostbackLogQuerySet, PostbackInsightQuerySet, NetworkPostbackConfigQuerySet

logger = logging.getLogger(__name__)


class BaseSelector:
    """
    Base selector class.
    
    Provides common selector functionality that can be
    extended for specific data selection needs.
    """
    
    def __init__(self, model_class: Type[models.Model]):
        self.model_class = model_class
        self.queryset = model_class.objects.all()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_queryset(self) -> models.QuerySet:
        """Get base queryset."""
        return self.queryset
    
    def filter_by_date_range(self, start_date: datetime, end_date: datetime) -> 'BaseSelector':
        """
        Filter by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model_class, 'created_at'):
            self.queryset = self.queryset.filter(created_at__gte=start_date, created_at__lte=end_date)
        elif hasattr(self.model_class, 'received_at'):
            self.queryset = self.queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        elif hasattr(self.model_class, 'date'):
            self.queryset = self.queryset.filter(date__gte=start_date.date(), date__lte=end_date.date())
        
        return self
    
    def filter_by_user(self, user) -> 'BaseSelector':
        """
        Filter by user.
        
        Args:
            user: User instance
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model_class, 'resolved_user'):
            self.queryset = self.queryset.filter(resolved_user=user)
        
        return self
    
    def filter_by_status(self, status: Union[str, List[str]]) -> 'BaseSelector':
        """
        Filter by status.
        
        Args:
            status: Status or list of statuses
            
        Returns:
            Self for chaining
        """
        if hasattr(self.model_class, 'status'):
            if isinstance(status, list):
                self.queryset = self.queryset.filter(status__in=status)
            else:
                self.queryset = self.queryset.filter(status=status)
        
        return self
    
    def limit(self, count: int) -> 'BaseSelector':
        """
        Limit results.
        
        Args:
            count: Number of results to return
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset[:count]
        return self
    
    def order_by(self, *fields) -> 'BaseSelector':
        """
        Order results.
        
        Args:
            *fields: Fields to order by
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.order_by(*fields)
        return self
    
    def first(self) -> Optional[models.Model]:
        """Get first result."""
        try:
            return self.queryset.first()
        except self.model_class.DoesNotExist:
            return None
    
    def all(self) -> List[models.Model]:
        """Get all results."""
        return list(self.queryset)
    
    def count(self) -> int:
        """Get result count."""
        return self.queryset.count()
    
    def exists(self) -> bool:
        """Check if results exist."""
        return self.queryset.exists()


class PostbackLogSelector(BaseSelector):
    """
    Selector for PostbackLog model.
    
    Provides specialized selection methods for postback logs
    with performance optimization and business logic.
    """
    
    def __init__(self):
        super().__init__(PostbackLog)
        self.queryset = PostbackLogQuerySet(self.model_class, using=self._db)
    
    def by_network(self, network_key: str) -> 'PostbackLogSelector':
        """
        Filter by network key.
        
        Args:
            network_key: Network key
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_network(network_key)
        return self
    
    def by_lead_id(self, lead_id: str) -> 'PostbackLogSelector':
        """
        Filter by lead ID.
        
        Args:
            lead_id: Lead ID
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.filter(lead_id=lead_id)
        return self
    
    def by_ip_address(self, ip_address: str) -> 'PostbackLogSelector':
        """
        Filter by IP address.
        
        Args:
            ip_address: IP address
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.filter(source_ip=ip_address)
        return self
    
    def by_payout_range(self, min_payout: Decimal = None, max_payout: Decimal = None) -> 'PostbackLogSelector':
        """
        Filter by payout range.
        
        Args:
            min_payout: Minimum payout
            max_payout: Maximum payout
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.with_payout_range(min_payout, max_payout)
        return self
    
    def rewarded(self) -> 'PostbackLogSelector':
        """Filter rewarded postbacks."""
        self.queryset = self.queryset.rewarded()
        return self
    
    def rejected(self) -> 'PostbackLogSelector':
        """Filter rejected postbacks."""
        self.queryset = self.queryset.rejected()
        return self
    
    def failed(self) -> 'PostbackLogSelector':
        """Filter failed postbacks."""
        self.queryset = self.queryset.failed()
        return self
    
    def recent(self, days: int = 7) -> 'PostbackLogSelector':
        """
        Filter recent postbacks.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.recent(days)
        return self
    
    def today(self) -> 'PostbackLogSelector':
        """Filter today's postbacks."""
        self.queryset = self.queryset.today()
        return self
    
    def this_week(self) -> 'PostbackLogSelector':
        """Filter this week's postbacks."""
        self.queryset = self.queryset.this_week()
        return self
    
    def this_month(self) -> 'PostbackLogSelector':
        """Filter this month's postbacks."""
        self.queryset = self.queryset.this_month()
        return self
    
    def duplicates(self) -> 'PostbackLogSelector':
        """Filter duplicate postbacks."""
        self.queryset = self.queryset.duplicates()
        return self
    
    def anomalies(self) -> 'PostbackLogSelector':
        """Filter anomalous postbacks."""
        self.queryset = self.queryset.anomalies()
        return self
    
    def search(self, query: str) -> 'PostbackLogSelector':
        """
        Search postback logs.
        
        Args:
            query: Search query
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.search(query)
        return self
    
    def with_conversion_rates(self) -> 'PostbackLogSelector':
        """Annotate with conversion rates."""
        self.queryset = self.queryset.with_conversion_rates()
        return self
    
    def hourly_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get hourly statistics.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Hourly statistics
        """
        return list(self.queryset.hourly_stats(hours))
    
    def daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Daily statistics
        """
        return list(self.queryset.daily_stats(days))
    
    def top_networks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top networks by postback count.
        
        Args:
            limit: Number of networks to return
            
        Returns:
            Top networks data
        """
        return list(self.queryset.top_networks(limit))
    
    def top_offers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top offers by postback count.
        
        Args:
            limit: Number of offers to return
            
        Returns:
            Top offers data
        """
        return list(self.queryset.top_offers(limit))
    
    def performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return self.queryset.performance_metrics()
    
    def by_rejection_reason(self, reason: str) -> 'PostbackLogSelector':
        """
        Filter by rejection reason.
        
        Args:
            reason: Rejection reason
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.filter(rejection_reason=reason)
        return self
    
    def high_value(self, min_payout: Decimal = Decimal('50.00')) -> 'PostbackLogSelector':
        """
        Filter high-value postbacks.
        
        Args:
            min_payout: Minimum payout threshold
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.filter(payout__gte=min_payout)
        return self
    
    def with_analytics_data(self) -> 'PostbackLogSelector':
        """Annotate with analytics data."""
        self.queryset = self.queryset.with_network_stats()
        return self


class PostbackInsightSelector(BaseSelector):
    """
    Selector for PostbackInsight model.
    
    Provides specialized selection methods for postback insights
    with analytics and reporting capabilities.
    """
    
    def __init__(self):
        super().__init__(PostbackInsight)
        self.queryset = PostbackInsightQuerySet(self.model_class, using=self._db)
    
    def by_network(self, network_key: str) -> 'PostbackInsightSelector':
        """
        Filter by network key.
        
        Args:
            network_key: Network key
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_network(network_key)
        return self
    
    def by_health_score_range(self, min_score: float = None, max_score: float = None) -> 'PostbackInsightSelector':
        """
        Filter by health score range.
        
        Args:
            min_score: Minimum health score
            max_score: Maximum health score
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_health_score_range(min_score, max_score)
        return self
    
    def recent(self, days: int = 30) -> 'PostbackInsightSelector':
        """
        Filter recent insights.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.recent(days)
        return self
    
    def with_anomalies(self) -> 'PostbackInsightSelector':
        """Filter insights with anomalies."""
        self.queryset = self.queryset.with_anomalies()
        return self
    
    def healthy(self, min_score: float = 70.0) -> 'PostbackInsightSelector':
        """
        Filter healthy insights.
        
        Args:
            min_score: Minimum health score
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.healthy(min_score)
        return self
    
    def unhealthy(self, max_score: float = 50.0) -> 'PostbackInsightSelector':
        """
        Filter unhealthy insights.
        
        Args:
            max_score: Maximum health score
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.unhealthy(max_score)
        return self
    
    def with_performance_trends(self, days: int = 30) -> 'PostbackInsightSelector':
        """
        Filter insights with performance trends.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.with_performance_trends(days)
        return self
    
    def top_performing_networks(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get top performing networks.
        
        Args:
            limit: Number of networks to return
            days: Number of days to analyze
            
        Returns:
            Top performing networks data
        """
        return list(self.queryset.top_performing_networks(limit, days))
    
    def worst_performing_networks(self, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get worst performing networks.
        
        Args:
            limit: Number of networks to return
            days: Number of days to analyze
            
        Returns:
            Worst performing networks data
        """
        return list(self.queryset.worst_performing_networks(limit, days))
    
    def monthly_summary(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Get monthly summary.
        
        Args:
            year: Year to analyze
            month: Month to analyze
            
        Returns:
            Monthly summary data
        """
        return self.queryset.monthly_summary(year, month)
    
    def weekly_summary(self, weeks: int = 4) -> List[Dict[str, Any]]:
        """
        Get weekly summary.
        
        Args:
            weeks: Number of weeks to analyze
            
        Returns:
            Weekly summary data
        """
        return list(self.queryset.weekly_summary(weeks))
    
    def health_score_distribution(self) -> Dict[str, Any]:
        """Get health score distribution."""
        return self.queryset.health_score_distribution()
    
    def anomaly_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze anomalies.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Anomaly analysis data
        """
        return self.queryset.anomaly_analysis(days)
    
    def performance_comparison(self, period1_days: int, period2_days: int) -> Dict[str, Any]:
        """
        Compare performance between two periods.
        
        Args:
            period1_days: First period in days
            period2_days: Second period in days
            
        Returns:
            Performance comparison data
        """
        return self.queryset.performance_comparison(period1_days, period2_days)
    
    def by_date_range(self, start_date: datetime.date, end_date: datetime.date) -> 'PostbackInsightSelector':
        """
        Filter by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_date_range(start_date, end_date)
        return self


class NetworkPostbackConfigSelector(BaseSelector):
    """
    Selector for NetworkPostbackConfig model.
    
    Provides specialized selection methods for network configurations
    with management and analytics capabilities.
    """
    
    def __init__(self):
        super().__init__(NetworkPostbackConfig)
        self.queryset = NetworkPostbackConfigQuerySet(self.model_class, using=self._db)
    
    def active(self) -> 'NetworkPostbackConfigSelector':
        """Filter active networks."""
        self.queryset = self.queryset.active()
        return self
    
    def inactive(self) -> 'NetworkPostbackConfigSelector':
        """Filter inactive networks."""
        self.queryset = self.queryset.inactive()
        return self
    
    def by_signature_algorithm(self, algorithm: str) -> 'NetworkPostbackConfigSelector':
        """
        Filter by signature algorithm.
        
        Args:
            algorithm: Signature algorithm
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_signature_algorithm(algorithm)
        return self
    
    def with_postback_stats(self) -> 'NetworkPostbackConfigSelector':
        """Annotate with postback statistics."""
        self.queryset = self.queryset.with_postback_stats()
        return self
    
    def with_performance_metrics(self, days: int = 30) -> 'NetworkPostbackConfigSelector':
        """
        Annotate with performance metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.with_performance_metrics(days)
        return self
    
    def by_ip_whitelist(self, ip_address: str) -> 'NetworkPostbackConfigSelector':
        """
        Filter networks that have IP in whitelist.
        
        Args:
            ip_address: IP address
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_ip_whitelist(ip_address)
        return self
    
    def requiring_field(self, field_name: str) -> 'NetworkPostbackConfigSelector':
        """
        Filter networks that require a specific field.
        
        Args:
            field_name: Field name
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.requiring_field(field_name)
        return self
    
    def by_throttle_rate(self, throttle_rate: str) -> 'NetworkPostbackConfigSelector':
        """
        Filter by custom throttle rate.
        
        Args:
            throttle_rate: Throttle rate
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.by_throttle_rate(throttle_rate)
        return self
    
    def search(self, query: str) -> 'NetworkPostbackConfigSelector':
        """
        Search network configurations.
        
        Args:
            query: Search query
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.search(query)
        return self
    
    def top_performing(self, limit: int = 10, days: int = 30) -> 'NetworkPostbackConfigSelector':
        """
        Filter top performing networks.
        
        Args:
            limit: Number of networks to return
            days: Number of days to analyze
            
        Returns:
            Self for chaining
        """
        networks = self.queryset.top_performing(limit, days)
        network_keys = [network['network_key'] for network in networks]
        self.queryset = self.queryset.filter(network_key__in=network_keys)
        return self
    
    def low_performing(self, limit: int = 10, days: int = 30) -> 'NetworkPostbackConfigSelector':
        """
        Filter low performing networks.
        
        Args:
            limit: Number of networks to return
            days: Number of days to analyze
            
        Returns:
            Self for chaining
        """
        networks = self.queryset.low_performing(limit, days)
        network_keys = [network['network_key'] for network in networks]
        self.queryset = self.queryset.filter(network_key__in=network_keys)
        return self
    
    def with_anomaly_count(self, days: int = 30) -> 'NetworkPostbackConfigSelector':
        """
        Annotate with anomaly count.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.with_anomaly_count(days)
        return self
    
    def by_max_payout_range(self, min_payout: Decimal = None, max_payout: Decimal = None) -> 'NetworkPostbackConfigSelector':
        """
        Filter by max payout range.
        
        Args:
            min_payout: Minimum max payout
            max_payout: Maximum max payout
            
        Returns:
            Self for chaining
        """
        queryset = self.queryset
        
        if min_payout is not None:
            queryset = queryset.filter(max_payout__gte=min_payout)
        
        if max_payout is not None:
            queryset = queryset.filter(max_payout__lte=max_payout)
        
        self.queryset = queryset
        return self


class SelectorFactory:
    """
    Factory for creating selector instances.
    
    Provides centralized selector creation with
    caching and performance optimization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._selector_cache = {}
    
    def get_postback_log_selector(self) -> PostbackLogSelector:
        """Get postback log selector."""
        return PostbackLogSelector()
    
    def get_postback_insight_selector(self) -> PostbackInsightSelector:
        """Get postback insight selector."""
        return PostbackInsightSelector()
    
    def get_network_config_selector(self) -> NetworkPostbackConfigSelector:
        """Get network config selector."""
        return NetworkPostbackConfigSelector()
    
    def create_selector(self, model_class: Type[models.Model]) -> BaseSelector:
        """
        Create selector for model class.
        
        Args:
            model_class: Model class
            
        Returns:
            Selector instance
        """
        if model_class == PostbackLog:
            return self.get_postback_log_selector()
        elif model_class == PostbackInsight:
            return self.get_postback_insight_selector()
        elif model_class == NetworkPostbackConfig:
            return self.get_network_config_selector()
        else:
            return BaseSelector(model_class)


# Global selector factory instance
selector_factory = SelectorFactory()


# Convenience functions
def select_postback_logs() -> PostbackLogSelector:
    """Get postback log selector."""
    return selector_factory.get_postback_log_selector()


def select_postback_insights() -> PostbackInsightSelector:
    """Get postback insight selector."""
    return selector_factory.get_postback_insight_selector()


def select_network_configs() -> NetworkPostbackConfigSelector:
    """Get network config selector."""
    return selector_factory.get_network_config_selector()


def create_selector(model_class: Type[models.Model]) -> BaseSelector:
    """Create selector for model class."""
    return selector_factory.create_selector(model_class)


# Advanced selector functions
def select_recent_postbacks(days: int = 7, status: str = None) -> List[PostbackLog]:
    """
    Select recent postbacks.
    
    Args:
        days: Number of days to look back
        status: Status filter
        
    Returns:
        List of postback logs
    """
    selector = select_postback_logs()
    
    if status:
        selector = selector.filter_by_status(status)
    
    return selector.recent(days).all()


def select_network_performance(network_key: str, days: int = 30) -> Dict[str, Any]:
    """
    Select network performance data.
    
    Args:
        network_key: Network key
        days: Number of days to analyze
        
    Returns:
        Network performance data
    """
    # Get postback logs for the network
    postbacks = (select_postback_logs()
                 .by_network(network_key)
                 .recent(days)
                 .performance_metrics())
    
    # Get insights for the network
    insights = (select_postback_insights()
                .by_network(network_key)
                .recent(days)
                .all())
    
    return {
        'network_key': network_key,
        'period_days': days,
        'postback_metrics': postbacks,
        'insights': insights,
    }


def select_anomaly_insights(days: int = 30) -> List[PostbackInsight]:
    """
    Select insights with anomalies.
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of insights with anomalies
    """
    return (select_postback_insights()
            .with_anomalies()
            .recent(days)
            .all())


def select_top_networks_by_health(limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
    """
    Select top networks by health score.
    
    Args:
        limit: Number of networks to return
        days: Number of days to analyze
        
    Returns:
        List of top networks
    """
    return (select_postback_insights()
            .top_performing_networks(limit, days))


def select_user_postback_activity(user, days: int = 30) -> List[PostbackLog]:
    """
    Select user's postback activity.
    
    Args:
        user: User instance
        days: Number of days to look back
        
    Returns:
        List of user's postback logs
    """
    return (select_postback_logs()
            .filter_by_user(user)
            .recent(days)
            .all())


# Selector utilities
def optimize_selector_query(selector: BaseSelector, select_related: List[str] = None, 
                          prefetch_related: List[str] = None) -> BaseSelector:
    """
    Optimize selector query.
    
    Args:
        selector: Selector instance
        select_related: Fields for select_related
        prefetch_related: Fields for prefetch_related
        
    Returns:
        Optimized selector
    """
    if select_related:
        selector.queryset = selector.queryset.select_related(*select_related)
    
    if prefetch_related:
        selector.queryset = selector.queryset.prefetch_related(*prefetch_related)
    
    return selector


def cache_selector_result(selector: BaseSelector, cache_key: str, timeout: int = 300) -> List[models.Model]:
    """
    Cache selector result.
    
    Args:
        selector: Selector instance
        cache_key: Cache key
        timeout: Cache timeout
        
    Returns:
        Cached results
    """
    # Try to get from cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Execute query
    result = selector.all()
    
    # Cache result
    cache.set(cache_key, result, timeout)
    
    return result


# Selector analytics
def get_selector_usage_statistics() -> Dict[str, Any]:
    """
    Get selector usage statistics.
    
    Returns:
        Selector usage statistics
    """
    return {
        'postback_log_selector_calls': 0,  # This would track actual usage
        'postback_insight_selector_calls': 0,
        'network_config_selector_calls': 0,
        'total_queries_executed': 0,
        'cache_hit_rate': 0.0,
    }


# Selector health check
def check_selector_health() -> Dict[str, Any]:
    """
    Check selector system health.
    
    Returns:
        Health status
    """
    health_status = {
        'overall': 'healthy',
        'selectors': {},
        'issues': [],
    }
    
    # Test postback log selector
    try:
        selector = select_postback_logs()
        count = selector.limit(1).count()
        health_status['selectors']['postback_log'] = 'healthy'
    except Exception as e:
        health_status['selectors']['postback_log'] = 'error'
        health_status['issues'].append(f"Postback log selector error: {str(e)}")
    
    # Test postback insight selector
    try:
        selector = select_postback_insights()
        count = selector.limit(1).count()
        health_status['selectors']['postback_insight'] = 'healthy'
    except Exception as e:
        health_status['selectors']['postback_insight'] = 'error'
        health_status['issues'].append(f"Postback insight selector error: {str(e)}")
    
    # Test network config selector
    try:
        selector = select_network_configs()
        count = selector.limit(1).count()
        health_status['selectors']['network_config'] = 'healthy'
    except Exception as e:
        health_status['selectors']['network_config'] = 'error'
        health_status['issues'].append(f"Network config selector error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
