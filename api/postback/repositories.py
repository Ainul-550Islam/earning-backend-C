"""
repositories.py – Repository pattern implementation for postback module.

Provides comprehensive repository functionality including:
- Data access layer
- Business logic separation
- Caching and performance optimization
- Transaction management
"""
from django.db.models import When
import logging
from typing import Dict, List, Optional, Any, Union, Type
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseRepository:
    """
    Base repository class.
    
    Provides common repository functionality that can be
    extended for specific data access needs.
    """
    
    def __init__(self, model_class: Type[models.Model]):
        self.model_class = model_class
        self.queryset = model_class.objects.all()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_by_id(self, pk: Any) -> Optional[models.Model]:
        """
        Get model instance by primary key.
        
        Args:
            pk: Primary key
            
        Returns:
            Model instance or None
        """
        try:
            return self.queryset.get(pk=pk)
        except self.model_class.DoesNotExist:
            return None
    
    def get_all(self) -> List[models.Model]:
        """
        Get all model instances.
        
        Returns:
            List of model instances
        """
        return list(self.queryset.all())
    
    def create(self, **kwargs) -> models.Model:
        """
        Create new model instance.
        
        Args:
            **kwargs: Model fields
            
        Returns:
            Created model instance
        """
        return self.queryset.create(**kwargs)
    
    def update(self, instance: models.Model, **kwargs) -> models.Model:
        """
        Update model instance.
        
        Args:
            instance: Model instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated model instance
        """
        for field, value in kwargs.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        
        instance.save()
        return instance
    
    def delete(self, instance: models.Model) -> bool:
        """
        Delete model instance.
        
        Args:
            instance: Model instance to delete
            
        Returns:
            True if deleted
        """
        instance.delete()
        return True
    
    def count(self) -> int:
        """Get total count of instances."""
        return self.queryset.count()
    
    def exists(self, **filters) -> bool:
        """
        Check if instance exists with filters.
        
        Args:
            **filters: Filter conditions
            
        Returns:
            True if exists
        """
        return self.queryset.filter(**filters).exists()
    
    def filter(self, **filters) -> 'BaseRepository':
        """
        Filter queryset.
        
        Args:
            **filters: Filter conditions
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.filter(**filters)
        return self
    
    def exclude(self, **filters) -> 'BaseRepository':
        """
        Exclude from queryset.
        
        Args:
            **filters: Exclude conditions
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.exclude(**filters)
        return self
    
    def order_by(self, *fields) -> 'BaseRepository':
        """
        Order queryset.
        
        Args:
            *fields: Fields to order by
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset.order_by(*fields)
        return self
    
    def limit(self, count: int) -> 'BaseRepository':
        """
        Limit queryset.
        
        Args:
            count: Number of results
            
        Returns:
            Self for chaining
        """
        self.queryset = self.queryset[:count]
        return self
    
    def first(self) -> Optional[models.Model]:
        """Get first result."""
        return self.queryset.first()
    
    def last(self) -> Optional[models.Model]:
        """Get last result."""
        return self.queryset.last()


class PostbackLogRepository(BaseRepository):
    """
    Repository for PostbackLog model.
    
    Provides specialized data access methods for postback logs
    with business logic and caching.
    """
    
    def __init__(self):
        super().__init__(PostbackLog)
    
    def by_network(self, network_key: str) -> List[PostbackLog]:
        """
        Get postbacks by network key.
        
        Args:
            network_key: Network key
            
        Returns:
            List of postback logs
        """
        return list(self.queryset.filter(network__network_key=network_key))
    
    def by_lead_id(self, lead_id: str) -> List[PostbackLog]:
        """
        Get postbacks by lead ID.
        
        Args:
            lead_id: Lead ID
            
        Returns:
            List of postback logs
        """
        return list(self.queryset.filter(lead_id=lead_id))
    
    def by_status(self, status: Union[str, List[str]]) -> List[PostbackLog]:
        """
        Get postbacks by status.
        
        Args:
            status: Status or list of statuses
            
        Returns:
            List of postback logs
        """
        if isinstance(status, list):
            return list(self.queryset.filter(status__in=status))
        else:
            return list(self.queryset.filter(status=status))
    
    def by_user(self, user: User) -> List[PostbackLog]:
        """
        Get postbacks by user.
        
        Args:
            user: User instance
            
        Returns:
            List of postback logs
        """
        return list(self.queryset.filter(resolved_user=user))
    
    def by_date_range(self, start_date: datetime, end_date: datetime) -> List[PostbackLog]:
        """
        Get postbacks by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of postback logs
        """
        return list(self.queryset.filter(
            received_at__gte=start_date,
            received_at__lte=end_date
        ))
    
    def recent(self, days: int = 7) -> List[PostbackLog]:
        """
        Get recent postbacks.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent postback logs
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        return list(self.queryset.filter(received_at__gte=cutoff_date))
    
    def today(self) -> List[PostbackLog]:
        """Get today's postbacks."""
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return list(self.queryset.filter(received_at__gte=today_start))
    
    def rewarded(self) -> List[PostbackLog]:
        """Get rewarded postbacks."""
        return list(self.queryset.filter(status='rewarded'))
    
    def rejected(self) -> List[PostbackLog]:
        """Get rejected postbacks."""
        return list(self.queryset.filter(status='rejected'))
    
    def failed(self) -> List[PostbackLog]:
        """Get failed postbacks."""
        return list(self.queryset.filter(status='failed'))
    
    def by_payout_range(self, min_payout: Decimal = None, max_payout: Decimal = None) -> List[PostbackLog]:
        """
        Get postbacks by payout range.
        
        Args:
            min_payout: Minimum payout
            max_payout: Maximum payout
            
        Returns:
            List of postback logs
        """
        queryset = self.queryset
        
        if min_payout is not None:
            queryset = queryset.filter(payout__gte=min_payout)
        
        if max_payout is not None:
            queryset = queryset.filter(payout__lte=max_payout)
        
        return list(queryset)
    
    def duplicates(self, network_key: str = None) -> List[Dict[str, Any]]:
        """
        Get duplicate postbacks.
        
        Args:
            network_key: Network key filter
            
        Returns:
            List of duplicate postback information
        """
        queryset = self.queryset.values('lead_id', 'network__network_key').annotate(
            duplicate_count=models.Count('id')
        ).filter(duplicate_count__gt=1)
        
        if network_key:
            queryset = queryset.filter(network__network_key=network_key)
        
        return list(queryset)
    
    def search(self, query: str) -> List[PostbackLog]:
        """
        Search postbacks.
        
        Args:
            query: Search query
            
        Returns:
            List of matching postback logs
        """
        from django.db.models import Q
        
        search_query = Q()
        
        # Search in extracted fields
        search_query |= Q(extracted_fields__icontains=query)
        
        # Search in raw payload
        search_query |= Q(raw_payload__icontains=query)
        
        # Search in text fields
        search_query |= Q(lead_id__icontains=query)
        search_query |= Q(offer_id__icontains=query)
        search_query |= Q(source_ip__icontains=query)
        
        return list(self.queryset.filter(search_query))
    
    def get_statistics(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Get postback statistics.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Statistics dictionary
        """
        queryset = self.queryset
        
        if start_date and end_date:
            queryset = queryset.filter(received_at__gte=start_date, received_at__lte=end_date)
        elif start_date:
            queryset = queryset.filter(received_at__gte=start_date)
        
        return queryset.aggregate(
            total_count=models.Count('id'),
            rewarded_count=models.Count(
                models.Case(
                    When(status='rewarded', then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            rejected_count=models.Count(
                models.Case(
                    When(status='rejected', then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            failed_count=models.Count(
                models.Case(
                    When(status='failed', then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            total_payout=models.Sum('payout'),
            avg_payout=models.Avg('payout'),
            max_payout=models.Max('payout'),
            min_payout=models.Min('payout'),
        )
    
    def create_with_integrity(self, **kwargs) -> PostbackLog:
        """
        Create postback with integrity hash.
        
        Args:
            **kwargs: Postback fields
            
        Returns:
            Created postback log
        """
        with transaction.atomic():
            postback = self.create(**kwargs)
            
            # Generate integrity hash
            postback.generate_integrity_hash()
            postback.save(update_fields=['integrity_hash'])
            
            return postback
    
    def bulk_create_with_integrity(self, postback_data_list: List[Dict[str, Any]]) -> List[PostbackLog]:
        """
        Bulk create postbacks with integrity hashes.
        
        Args:
            postback_data_list: List of postback data
            
        Returns:
            List of created postback logs
        """
        with transaction.atomic():
            postbacks = []
            
            for data in postback_data_list:
                postback = self.create(**data)
                postback.generate_integrity_hash()
                postback.save(update_fields=['integrity_hash'])
                postbacks.append(postback)
            
            return postbacks
    
    def get_cached_by_id(self, pk: Any, timeout: int = 300) -> Optional[PostbackLog]:
        """
        Get postback by ID with caching.
        
        Args:
            pk: Primary key
            timeout: Cache timeout
            
        Returns:
            Cached postback log or None
        """
        cache_key = f"postback_log_{pk}"
        cached_postback = cache.get(cache_key)
        
        if cached_postback is not None:
            return cached_postback
        
        postback = self.get_by_id(pk)
        if postback:
            cache.set(cache_key, postback, timeout)
        
        return postback
    
    def invalidate_cache(self, pk: Any):
        """
        Invalidate cache for postback.
        
        Args:
            pk: Primary key
        """
        cache_key = f"postback_log_{pk}"
        cache.delete(cache_key)


class PostbackInsightRepository(BaseRepository):
    """
    Repository for PostbackInsight model.
    
    Provides specialized data access methods for postback insights
    with analytics and reporting capabilities.
    """
    
    def __init__(self):
        super().__init__(PostbackInsight)
    
    def by_network(self, network_key: str) -> List[PostbackInsight]:
        """
        Get insights by network key.
        
        Args:
            network_key: Network key
            
        Returns:
            List of insights
        """
        return list(self.queryset.filter(network__network_key=network_key))
    
    def by_date_range(self, start_date: datetime.date, end_date: datetime.date) -> List[PostbackInsight]:
        """
        Get insights by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of insights
        """
        return list(self.queryset.filter(date__gte=start_date, date__lte=end_date))
    
    def recent(self, days: int = 30) -> List[PostbackInsight]:
        """
        Get recent insights.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent insights
        """
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return list(self.queryset.filter(date__gte=cutoff_date))
    
    def with_anomalies(self) -> List[PostbackInsight]:
        """Get insights with anomalies."""
        return list(self.queryset.filter(anomaly_detected=True))
    
    def healthy(self, min_score: float = 70.0) -> List[PostbackInsight]:
        """
        Get healthy insights.
        
        Args:
            min_score: Minimum health score
            
        Returns:
            List of healthy insights
        """
        return list(self.queryset.filter(health_score__gte=min_score))
    
    def unhealthy(self, max_score: float = 50.0) -> List[PostbackInsight]:
        """
        Get unhealthy insights.
        
        Args:
            max_score: Maximum health score
            
        Returns:
            List of unhealthy insights
        """
        return list(self.queryset.filter(health_score__lte=max_score))
    
    def by_health_score_range(self, min_score: float = None, max_score: float = None) -> List[PostbackInsight]:
        """
        Get insights by health score range.
        
        Args:
            min_score: Minimum health score
            max_score: Maximum health score
            
        Returns:
            List of insights
        """
        queryset = self.queryset
        
        if min_score is not None:
            queryset = queryset.filter(health_score__gte=min_score)
        
        if max_score is not None:
            queryset = queryset.filter(health_score__lte=max_score)
        
        return list(queryset)
    
    def get_network_performance_summary(self, network_key: str, days: int = 30) -> Dict[str, Any]:
        """
        Get network performance summary.
        
        Args:
            network_key: Network key
            days: Number of days to analyze
            
        Returns:
            Performance summary
        """
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        insights = self.queryset.filter(
            network__network_key=network_key,
            date__gte=cutoff_date
        )
        
        return insights.aggregate(
            total_days=models.Count('date'),
            avg_health_score=models.Avg('health_score'),
            total_received=models.Sum('received_count'),
            total_rewarded=models.Sum('rewarded_count'),
            total_rejected=models.Sum('rejected_count'),
            total_payout=models.Sum('total_payout'),
            anomaly_days=models.Count(
                models.Case(
                    When(anomaly_detected=True, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
        )
    
    def get_health_score_distribution(self) -> Dict[str, Any]:
        """Get health score distribution."""
        return self.queryset.aggregate(
            excellent=models.Count(
                models.Case(
                    When(health_score__gte=90, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            good=models.Count(
                models.Case(
                    When(health_score__gte=70, health_score__lt=90, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            fair=models.Count(
                models.Case(
                    When(health_score__gte=50, health_score__lt=70, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
            poor=models.Count(
                models.Case(
                    When(health_score__lt=50, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
        )
    
    def get_anomaly_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Get anomaly analysis.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Anomaly analysis
        """
        cutoff_date = timezone.now().date() - timedelta(days=days)
        
        insights = self.queryset.filter(
            date__gte=cutoff_date,
            anomaly_detected=True
        )
        
        return insights.aggregate(
            anomaly_count=models.Count('id'),
            avg_health_during_anomaly=models.Avg('health_score'),
            most_common_anomaly_type=models.StringAgg(
                'anomaly_details__type',
                delimiter=','
            ),
        )
    
    def get_cached_by_id(self, pk: Any, timeout: int = 300) -> Optional[PostbackInsight]:
        """
        Get insight by ID with caching.
        
        Args:
            pk: Primary key
            timeout: Cache timeout
            
        Returns:
            Cached insight or None
        """
        cache_key = f"postback_insight_{pk}"
        cached_insight = cache.get(cache_key)
        
        if cached_insight is not None:
            return cached_insight
        
        insight = self.get_by_id(pk)
        if insight:
            cache.set(cache_key, insight, timeout)
        
        return insight


class NetworkPostbackConfigRepository(BaseRepository):
    """
    Repository for NetworkPostbackConfig model.
    
    Provides specialized data access methods for network configurations
    with management and monitoring capabilities.
    """
    
    def __init__(self):
        super().__init__(NetworkPostbackConfig)
    
    def active(self) -> List[NetworkPostbackConfig]:
        """Get active networks."""
        return list(self.queryset.filter(is_active=True))
    
    def inactive(self) -> List[NetworkPostbackConfig]:
        """Get inactive networks."""
        return list(self.queryset.filter(is_active=False))
    
    def by_signature_algorithm(self, algorithm: str) -> List[NetworkPostbackConfig]:
        """
        Get networks by signature algorithm.
        
        Args:
            algorithm: Signature algorithm
            
        Returns:
            List of networks
        """
        return list(self.queryset.filter(signature_algorithm=algorithm))
    
    def by_ip_whitelist(self, ip_address: str) -> List[NetworkPostbackConfig]:
        """
        Get networks that have IP in whitelist.
        
        Args:
            ip_address: IP address
            
        Returns:
            List of networks
        """
        return list(self.queryset.filter(ip_whitelist__contains=[ip_address]))
    
    def requiring_field(self, field_name: str) -> List[NetworkPostbackConfig]:
        """
        Get networks requiring specific field.
        
        Args:
            field_name: Field name
            
        Returns:
            List of networks
        """
        return list(self.queryset.filter(required_fields__contains=[field_name]))
    
    def by_throttle_rate(self, throttle_rate: str) -> List[NetworkPostbackConfig]:
        """
        Get networks by custom throttle rate.
        
        Args:
            throttle_rate: Throttle rate
            
        Returns:
            List of networks
        """
        return list(self.queryset.filter(custom_throttle_rate=throttle_rate))
    
    def search(self, query: str) -> List[NetworkPostbackConfig]:
        """
        Search network configurations.
        
        Args:
            query: Search query
            
        Returns:
            List of matching networks
        """
        from django.db.models import Q
        
        return list(self.queryset.filter(
            Q(network_key__icontains=query) | Q(name__icontains=query)
        ))
    
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get performance metrics for networks.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Performance metrics
        """
        # This would integrate with analytics system
        return {
            'total_networks': self.count(),
            'active_networks': len(self.active()),
            'inactive_networks': len(self.inactive()),
            'recent_activity': 'Would include recent activity metrics',
        }
    
    def get_cached_by_id(self, pk: Any, timeout: int = 300) -> Optional[NetworkPostbackConfig]:
        """
        Get network config by ID with caching.
        
        Args:
            pk: Primary key
            timeout: Cache timeout
            
        Returns:
            Cached network config or None
        """
        cache_key = f"network_config_{pk}"
        cached_config = cache.get(cache_key)
        
        if cached_config is not None:
            return cached_config
        
        config = self.get_by_id(pk)
        if config:
            cache.set(cache_key, config, timeout)
        
        return config


# Repository factory
class RepositoryFactory:
    """Factory for creating repository instances."""
    
    @staticmethod
    def create_postback_log_repository() -> PostbackLogRepository:
        """Create postback log repository."""
        return PostbackLogRepository()
    
    @staticmethod
    def create_postback_insight_repository() -> PostbackInsightRepository:
        """Create postback insight repository."""
        return PostbackInsightRepository()
    
    @staticmethod
    def create_network_config_repository() -> NetworkPostbackConfigRepository:
        """Create network config repository."""
        return NetworkPostbackConfigRepository()
    
    @staticmethod
    def create_repository(model_class: Type[models.Model]) -> BaseRepository:
        """Create repository for model class."""
        if model_class == PostbackLog:
            return RepositoryFactory.create_postback_log_repository()
        elif model_class == PostbackInsight:
            return RepositoryFactory.create_postback_insight_repository()
        elif model_class == NetworkPostbackConfig:
            return RepositoryFactory.create_network_config_repository()
        else:
            return BaseRepository(model_class)


# Global repository instances
postback_log_repository = RepositoryFactory.create_postback_log_repository()
postback_insight_repository = RepositoryFactory.create_postback_insight_repository()
network_config_repository = RepositoryFactory.create_network_config_repository()


# Convenience functions
def get_postback_log_repository() -> PostbackLogRepository:
    """Get postback log repository."""
    return postback_log_repository


def get_postback_insight_repository() -> PostbackInsightRepository:
    """Get postback insight repository."""
    return postback_insight_repository


def get_network_config_repository() -> NetworkPostbackConfigRepository:
    """Get network config repository."""
    return network_config_repository


# Repository utilities
def create_repository(model_class: Type[models.Model]) -> BaseRepository:
    """Create repository for model class."""
    return RepositoryFactory.create_repository(model_class)


def with_transaction(func):
    """
    Decorator for executing function within a transaction.
    
    Args:
        func: Function to execute
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)
    
    return wrapper


def cache_repository_result(cache_key_prefix: str, timeout: int = 300):
    """
    Decorator for caching repository results.
    
    Args:
        cache_key_prefix: Cache key prefix
        timeout: Cache timeout
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{cache_key_prefix}_{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


# Repository health check
def check_repository_health() -> Dict[str, Any]:
    """Check repository system health."""
    health_status = {
        'overall': 'healthy',
        'repositories': {},
        'issues': [],
    }
    
    # Test postback log repository
    try:
        repo = get_postback_log_repository()
        count = repo.count()
        health_status['repositories']['postback_log'] = 'healthy'
    except Exception as e:
        health_status['repositories']['postback_log'] = 'error'
        health_status['issues'].append(f"Postback log repository error: {str(e)}")
    
    # Test postback insight repository
    try:
        repo = get_postback_insight_repository()
        count = repo.count()
        health_status['repositories']['postback_insight'] = 'healthy'
    except Exception as e:
        health_status['repositories']['postback_insight'] = 'error'
        health_status['issues'].append(f"Postback insight repository error: {str(e)}")
    
    # Test network config repository
    try:
        repo = get_network_config_repository()
        count = repo.count()
        health_status['repositories']['network_config'] = 'healthy'
    except Exception as e:
        health_status['repositories']['network_config'] = 'error'
        health_status['issues'].append(f"Network config repository error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
