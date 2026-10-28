"""
querysets.py – Custom QuerySets for postback module.

Provides comprehensive QuerySet functionality including:
- Enhanced filtering methods
- Analytics and aggregation methods
- Performance-optimized queries
- Custom query utilities
"""
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Case
from django.db.models import ExpressionWrapper
from django.db.models import IntegerField
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import TruncWeek
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Expression, FloatField
from django.utils import timezone
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason

logger = logging.getLogger(__name__)


class PostbackLogQuerySet(models.QuerySet):
    """
    Custom QuerySet for PostbackLog model.
    
    Provides specialized query methods for postback logs
    with performance optimization and analytics capabilities.
    """
    
    def active(self):
        """Get active postback logs."""
        return self.filter(status__in=[PostbackStatus.RECEIVED, PostbackStatus.REWARDED])
    
    def rewarded(self):
        """Get rewarded postback logs."""
        return self.filter(status=PostbackStatus.REWARDED)
    
    def rejected(self):
        """Get rejected postback logs."""
        return self.filter(status=PostbackStatus.REJECTED)
    
    def failed(self):
        """Get failed postback logs."""
        return self.filter(status=PostbackStatus.FAILED)
    
    def by_network(self, network_key: str):
        """Filter by network key."""
        return self.filter(network__network_key=network_key)
    
    def by_user(self, user):
        """Filter by resolved user."""
        return self.filter(resolved_user=user)
    
    def by_status(self, status: Union[str, List[str]]):
        """Filter by status."""
        if isinstance(status, list):
            return self.filter(status__in=status)
        return self.filter(status=status)
    
    def by_date_range(self, start_date: datetime, end_date: datetime):
        """Filter by date range."""
        return self.filter(received_at__gte=start_date, received_at__lte=end_date)
    
    def recent(self, days: int = 7):
        """Get recent postback logs."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(received_at__gte=cutoff_date)
    
    def today(self):
        """Get today's postback logs."""
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(received_at__gte=today_start)
    
    def this_week(self):
        """Get this week's postback logs."""
        week_start = timezone.now() - timedelta(days=timezone.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(received_at__gte=week_start)
    
    def this_month(self):
        """Get this month's postback logs."""
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.filter(received_at__gte=month_start)
    
    def with_payout_range(self, min_payout: Decimal = None, max_payout: Decimal = None):
        """Filter by payout range."""
        queryset = self
        
        if min_payout is not None:
            queryset = queryset.filter(payout__gte=min_payout)
        
        if max_payout is not None:
            queryset = queryset.filter(payout__lte=max_payout)
        
        return queryset
    
    def by_ip_address(self, ip_address: str):
        """Filter by IP address."""
        return self.filter(source_ip=ip_address)
    
    def by_lead_id(self, lead_id: str):
        """Filter by lead ID."""
        return self.filter(lead_id=lead_id)
    
    def by_offer_id(self, offer_id: str):
        """Filter by offer ID."""
        return self.filter(offer_id=offer_id)
    
    def duplicates(self):
        """Get duplicate postback logs."""
        from django.db.models import Count
        
        return self.values('lead_id', 'network').annotate(
            duplicate_count=Count('id')
        ).filter(duplicate_count__gt=1)
    
    def anomalies(self):
        """Get anomalous postback logs."""
        # High payout anomalies
        high_payout = self.annotate(
            avg_payout=Avg('payout')
        ).filter(payout__gt=F('avg_payout') * 3)
        
        # Failed postbacks with high payout
        failed_high_payout = self.filter(
            status=PostbackStatus.FAILED,
            payout__gt=50
        )
        
        # Rejected due to suspicious reasons
        suspicious_rejections = self.filter(
            status=PostbackStatus.REJECTED,
            rejection_reason__in=[
                RejectionReason.SUSPICIOUS_ACTIVITY,
                RejectionReason.FRAUD_DETECTED,
                RejectionReason.IP_BLOCKED,
            ]
        )
        
        return high_payout.union(failed_high_payout).union(suspicious_rejections).distinct()
    
    def search(self, query: str):
        """Search postback logs."""
        if not query:
            return self.none()
        
        # Search in multiple fields
        search_query = Q()
        
        # Search in extracted fields (JSON)
        if self.model._meta.get_field('extracted_fields'):
            search_query |= Q(extracted_fields__icontains=query)
        
        # Search in raw payload (JSON)
        if self.model._meta.get_field('raw_payload'):
            search_query |= Q(raw_payload__icontains=query)
        
        # Search in text fields
        search_query |= Q(lead_id__icontains=query)
        search_query |= Q(offer_id__icontains=query)
        search_query |= Q(source_ip__icontains=query)
        
        return self.filter(search_query)
    
    def with_network_stats(self):
        """Annotate with network statistics."""
        return self.annotate(
            network_total_count=Count('network__postbacklog'),
            network_rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            network_total_payout=Sum('payout'),
        )
    
    def with_conversion_rates(self):
        """Annotate with conversion rates."""
        return self.annotate(
            total_count=Count('id'),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        ).annotate(
            conversion_rate=ExpressionWrapper(
                F('rewarded_count') * 100.0 / F('total_count'),
                output_field=FloatField(),
            )
        )
    
    def hourly_stats(self, hours: int = 24):
        """Get hourly statistics."""
        from django.db.models import TruncHour
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        return self.filter(
            received_at__gte=cutoff_time
        ).annotate(
            hour=TruncHour('received_at')
        ).values('hour').annotate(
            count=Count('id'),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum('payout'),
            avg_payout=Avg('payout'),
        ).order_by('hour')
    
    def daily_stats(self, days: int = 30):
        """Get daily statistics."""
        from django.db.models import TruncDay
        
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.filter(
            received_at__date__gte=cutoff_date
        ).annotate(
            day=TruncDay('received_at')
        ).values('day').annotate(
            count=Count('id'),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum('payout'),
            avg_payout=Avg('payout'),
        ).order_by('day')
    
    def top_networks(self, limit: int = 10):
        """Get top networks by postback count."""
        return self.values('network__network_key', 'network__name').annotate(
            count=Count('id'),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum('payout'),
        ).order_by('-count')[:limit]
    
    def top_offers(self, limit: int = 10):
        """Get top offers by postback count."""
        return self.values('offer_id').annotate(
            count=Count('id'),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum('payout'),
        ).order_by('-count')[:limit]
    
    def performance_metrics(self):
        """Get performance metrics."""
        return self.aggregate(
            total_count=Count('id'),
            received_count=Count(
                Case(
                    When(status=PostbackStatus.RECEIVED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            rewarded_count=Count(
                Case(
                    When(status=PostbackStatus.REWARDED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            rejected_count=Count(
                Case(
                    When(status=PostbackStatus.REJECTED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            failed_count=Count(
                Case(
                    When(status=PostbackStatus.FAILED, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum('payout'),
            avg_payout=Avg('payout'),
            max_payout=Max('payout'),
            min_payout=Min('payout'),
        )
    
    def cached_count(self, timeout: int = 300):
        """Get cached count."""
        cache_key = f"postbacklog_count_{hash(str(self.query))}"
        
        count = cache.get(cache_key)
        if count is None:
            count = self.count()
            cache.set(cache_key, count, timeout)
        
        return count
    
    def bulk_update_status(self, status: str, ids: List[str]):
        """Bulk update status for given IDs."""
        return self.filter(id__in=ids).update(status=status)


class PostbackInsightQuerySet(models.QuerySet):
    """
    Custom QuerySet for PostbackInsight model.
    
    Provides specialized query methods for postback insights
    with analytics and reporting capabilities.
    """
    
    def by_network(self, network_key: str):
        """Filter by network key."""
        return self.filter(network__network_key=network_key)
    
    def by_date_range(self, start_date: datetime.date, end_date: datetime.date):
        """Filter by date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)
    
    def recent(self, days: int = 30):
        """Get recent insights."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return self.filter(date__gte=cutoff_date)
    
    def with_anomalies(self):
        """Get insights with anomalies."""
        return self.filter(anomaly_detected=True)
    
    def healthy(self, min_score: float = 70.0):
        """Get healthy insights."""
        return self.filter(health_score__gte=min_score)
    
    def unhealthy(self, max_score: float = 50.0):
        """Get unhealthy insights."""
        return self.filter(health_score__lte=max_score)
    
    def by_health_score_range(self, min_score: float = None, max_score: float = None):
        """Filter by health score range."""
        queryset = self
        
        if min_score is not None:
            queryset = queryset.filter(health_score__gte=min_score)
        
        if max_score is not None:
            queryset = queryset.filter(health_score__lte=max_score)
        
        return queryset
    
    def with_performance_trends(self, days: int = 30):
        """Get insights with performance trends."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.filter(date__gte=cutoff_date).annotate(
            prev_day_health=Avg('health_score'),
        ).order_by('date')
    
    def top_performing_networks(self, limit: int = 10, days: int = 30):
        """Get top performing networks."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.filter(date__gte=cutoff_date).values('network__network_key', 'network__name').annotate(
            avg_health_score=Avg('health_score'),
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_payout=Sum('total_payout'),
            conversion_rate=Avg('rewarded_count') * 100.0 / Avg('received_count'),
        ).order_by('-avg_health_score')[:limit]
    
    def worst_performing_networks(self, limit: int = 10, days: int = 30):
        """Get worst performing networks."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.filter(date__gte=cutoff_date).values('network__network_key', 'network__name').annotate(
            avg_health_score=Avg('health_score'),
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_payout=Sum('total_payout'),
            conversion_rate=Avg('rewarded_count') * 100.0 / Avg('received_count'),
        ).order_by('avg_health_score')[:limit]
    
    def monthly_summary(self, year: int = None, month: int = None):
        """Get monthly summary."""
        if year and month:
            start_date = datetime(year, month, 1).date()
            if month == 12:
                end_date = datetime(year + 1, 1, 1).date()
            else:
                end_date = datetime(year, month + 1, 1).date()
        else:
            start_date = timezone.now().date().replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1)
        
        return self.filter(date__gte=start_date, date__lt=end_date).aggregate(
            total_days=Count('date'),
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_rejected=Sum('rejected_count'),
            total_payout=Sum('total_payout'),
            avg_health_score=Avg('health_score'),
            anomaly_days=Count(
                Case(
                    When(anomaly_detected=True, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        )
    
    def weekly_summary(self, weeks: int = 4):
        """Get weekly summary."""
        cutoff_date = timezone.now().date() - timedelta(weeks=weeks)
        
        return self.filter(date__gte=cutoff_date).annotate(
            week=TruncWeek('date')
        ).values('week').annotate(
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_rejected=Sum('rejected_count'),
            total_payout=Sum('total_payout'),
            avg_health_score=Avg('health_score'),
            anomaly_count=Count(
                Case(
                    When(anomaly_detected=True, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        ).order_by('week')
    
    def health_score_distribution(self):
        """Get health score distribution."""
        return self.aggregate(
            excellent=Count(Case(When(health_score__gte=90, then=1), output_field=IntegerField())),
            good=Count(Case(When(health_score__gte=70, health_score__lt=90, then=1), output_field=IntegerField())),
            fair=Count(Case(When(health_score__gte=50, health_score__lt=70, then=1), output_field=IntegerField())),
            poor=Count(Case(When(health_score__lt=50, then=1), output_field=IntegerField())),
        )
    
    def anomaly_analysis(self, days: int = 30):
        """Analyze anomalies."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.filter(date__gte=cutoff_date, anomaly_detected=True).aggregate(
            anomaly_count=Count('id'),
            avg_health_during_anomaly=Avg('health_score'),
            most_common_anomaly_type=ArrayAgg('anomaly_details__type'),
        )
    
    def performance_comparison(self, period1_days: int, period2_days: int):
        """Compare performance between two periods."""
        period1_end = timezone.now().date()
        period1_start = period1_end - timedelta(days=period1_days)
        
        period2_end = period1_start
        period2_start = period2_end - timedelta(days=period2_days)
        
        period1_stats = self.filter(date__gte=period1_start, date__lt=period1_end).aggregate(
            avg_health=Avg('health_score'),
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_payout=Sum('total_payout'),
        )
        
        period2_stats = self.filter(date__gte=period2_start, date__lt=period2_end).aggregate(
            avg_health=Avg('health_score'),
            total_received=Sum('received_count'),
            total_rewarded=Sum('rewarded_count'),
            total_payout=Sum('total_payout'),
        )
        
        return {
            'period1': period1_stats,
            'period2': period2_stats,
            'health_change': period1_stats['avg_health'] - period2_stats['avg_health'],
            'received_change': period1_stats['total_received'] - period2_stats['total_received'],
            'rewarded_change': period1_stats['total_rewarded'] - period2_stats['total_rewarded'],
            'payout_change': period1_stats['total_payout'] - period2_stats['total_payout'],
        }


class NetworkPostbackConfigQuerySet(models.QuerySet):
    """
    Custom QuerySet for NetworkPostbackConfig model.
    
    Provides specialized query methods for network configurations
    with filtering and management capabilities.
    """
    
    def active(self):
        """Get active network configurations."""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Get inactive network configurations."""
        return self.filter(is_active=False)
    
    def by_signature_algorithm(self, algorithm: str):
        """Filter by signature algorithm."""
        return self.filter(signature_algorithm=algorithm)
    
    def with_postback_stats(self):
        """Annotate with postback statistics."""
        from django.db.models import Subquery, OuterRef
        
        # Get latest insight for each network
        latest_insight = PostbackInsight.objects.filter(
            network=OuterRef('pk')
        ).order_by('-date')[:1]
        
        return self.annotate(
            latest_insight_date=Subquery(latest_insight.values('date')),
            latest_health_score=Subquery(latest_insight.values('health_score')),
            total_postbacks=Count('postbacklog'),
            active_postbacks=Count(
                Case(
                    When(postbacklog__status__in=[PostbackStatus.RECEIVED, PostbackStatus.REWARDED], then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
        )
    
    def with_performance_metrics(self, days: int = 30):
        """Annotate with performance metrics."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.annotate(
            recent_insights=Count(
                Case(
                    When(postbackinsight__date__gte=cutoff_date, then=1),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            avg_health_score=Avg(
                Case(
                    When(postbackinsight__date__gte=cutoff_date, then=F('postbackinsight__health_score')),
                    output_field=FloatField(),
                )
            ),
            total_received=Sum(
                Case(
                    When(postbackinsight__date__gte=cutoff_date, then=F('postbackinsight__received_count')),
                    output_field=IntegerField(),
                )
            ),
            total_rewarded=Sum(
                Case(
                    When(postbackinsight__date__gte=cutoff_date, then=F('postbackinsight__rewarded_count')),
                    output_field=IntegerField(),
                )
            ),
            total_payout=Sum(
                Case(
                    When(postbackinsight__date__gte=cutoff_date, then=F('postbackinsight__total_payout')),
                    output_field=FloatField(),
                )
            ),
        )
    
    def by_ip_whitelist(self, ip_address: str):
        """Filter networks that have IP in whitelist."""
        return self.filter(ip_whitelist__contains=[ip_address])
    
    def requiring_field(self, field_name: str):
        """Filter networks that require a specific field."""
        return self.filter(required_fields__contains=[field_name])
    
    def by_throttle_rate(self, throttle_rate: str):
        """Filter by custom throttle rate."""
        return self.filter(custom_throttle_rate=throttle_rate)
    
    def search(self, query: str):
        """Search network configurations."""
        if not query:
            return self.none()
        
        return self.filter(
            Q(network_key__icontains=query) |
            Q(name__icontains=query)
        )
    
    def top_performing(self, limit: int = 10, days: int = 30):
        """Get top performing networks."""
        return self.with_performance_metrics(days).filter(
            recent_insights__gt=0
        ).order_by('-avg_health_score')[:limit]
    
    def low_performing(self, limit: int = 10, days: int = 30):
        """Get low performing networks."""
        return self.with_performance_metrics(days).filter(
            recent_insights__gt=0
        ).order_by('avg_health_score')[:limit]
    
    def with_anomaly_count(self, days: int = 30):
        """Annotate with anomaly count."""
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        return self.annotate(
            anomaly_count=Count(
                Case(
                    When(
                        postbackinsight__date__gte=cutoff_date,
                        postbackinsight__anomaly_detected=True,
                        then=1
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
        )
    
    def bulk_activate(self, network_keys: List[str]):
        """Bulk activate networks."""
        return self.filter(network_key__in=network_keys).update(is_active=True)
    
    def bulk_deactivate(self, network_keys: List[str]):
        """Bulk deactivate networks."""
        return self.filter(network_key__in=network_keys).update(is_active=False)


# Custom QuerySet manager
class PostbackLogManager(models.Manager):
    """Manager for PostbackLog with custom QuerySet."""
    
    def get_queryset(self):
        return PostbackLogQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()
    
    def rewarded(self):
        return self.get_queryset().rewarded()
    
    def rejected(self):
        return self.get_queryset().rejected()
    
    def failed(self):
        return self.get_queryset().failed()
    
    def by_network(self, network_key: str):
        return self.get_queryset().by_network(network_key)
    
    def by_user(self, user):
        return self.get_queryset().by_user(user)
    
    def recent(self, days: int = 7):
        return self.get_queryset().recent(days)
    
    def search(self, query: str):
        return self.get_queryset().search(query)
    
    def performance_metrics(self):
        return self.get_queryset().performance_metrics()
    
    def cached_count(self, timeout: int = 300):
        return self.get_queryset().cached_count(timeout)


class PostbackInsightManager(models.Manager):
    """Manager for PostbackInsight with custom QuerySet."""
    
    def get_queryset(self):
        return PostbackInsightQuerySet(self.model, using=self._db)
    
    def by_network(self, network_key: str):
        return self.get_queryset().by_network(network_key)
    
    def recent(self, days: int = 30):
        return self.get_queryset().recent(days)
    
    def with_anomalies(self):
        return self.get_queryset().with_anomalies()
    
    def healthy(self, min_score: float = 70.0):
        return self.get_queryset().healthy(min_score)
    
    def top_performing_networks(self, limit: int = 10, days: int = 30):
        return self.get_queryset().top_performing_networks(limit, days)
    
    def monthly_summary(self, year: int = None, month: int = None):
        return self.get_queryset().monthly_summary(year, month)


class NetworkPostbackConfigManager(models.Manager):
    """Manager for NetworkPostbackConfig with custom QuerySet."""
    
    def get_queryset(self):
        return NetworkPostbackConfigQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()
    
    def inactive(self):
        return self.get_queryset().inactive()
    
    def with_postback_stats(self):
        return self.get_queryset().with_postback_stats()
    
    def with_performance_metrics(self, days: int = 30):
        return self.get_queryset().with_performance_metrics(days)
    
    def search(self, query: str):
        return self.get_queryset().search(query)
    
    def top_performing(self, limit: int = 10, days: int = 30):
        return self.get_queryset().top_performing(limit, days)


# QuerySet utilities
def get_queryset_statistics() -> Dict[str, Any]:
    """Get QuerySet statistics."""
    return {
        'postback_log_count': PostbackLog.objects.count(),
        'postback_insight_count': PostbackInsight.objects.count(),
        'network_config_count': NetworkPostbackConfig.objects.count(),
        'active_networks': NetworkPostbackConfig.objects.active().count(),
        'recent_postbacks': PostbackLog.objects.recent(days=7).count(),
        'postbacks_today': PostbackLog.objects.today().count(),
    }


def optimize_queryset_performance(queryset, select_related=None, prefetch_related=None):
    """
    Optimize queryset performance with select_related and prefetch_related.
    
    Args:
        queryset: QuerySet to optimize
        select_related: Fields for select_related
        prefetch_related: Fields for prefetch_related
        
    Returns:
        Optimized QuerySet
    """
    if select_related:
        queryset = queryset.select_related(*select_related)
    
    if prefetch_related:
        queryset = queryset.prefetch_related(*prefetch_related)
    
    return queryset


def cache_queryset_result(queryset, cache_key: str, timeout: int = 300):
    """
    Cache queryset result.
    
    Args:
        queryset: QuerySet to cache
        cache_key: Cache key
        timeout: Cache timeout
        
    Returns:
        Cached result
    """
    result = cache.get(cache_key)
    
    if result is None:
        result = list(queryset)
        cache.set(cache_key, result, timeout)
    
    return result


# Bulk operations
def bulk_create_with_integrity(queryset, objects):
    """
    Bulk create objects with integrity hash generation.
    
    Args:
        queryset: QuerySet
        objects: Objects to create
        
    Returns:
        Created objects
    """
    with transaction.atomic():
        # Generate integrity hashes
        for obj in objects:
            if hasattr(obj, 'generate_integrity_hash'):
                obj.generate_integrity_hash()
        
        return queryset.bulk_create(objects)


def bulk_update_with_timestamp(queryset, field_updates: Dict[str, Any]):
    """
    Bulk update with timestamp update.
    
    Args:
        queryset: QuerySet
        field_updates: Fields to update
        
    Returns:
        Number of updated rows
    """
    field_updates['updated_at'] = timezone.now()
    return queryset.bulk_update(field_updates.keys(), field_updates.values())
