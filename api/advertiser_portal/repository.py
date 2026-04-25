"""
Repository Module

This module provides the foundational repository layer for the Advertiser Portal,
implementing enterprise-grade data access patterns comparable to Google Ads API,
Facebook Marketing API, and other industry-leading platforms.

Features:
- Enterprise-grade data access with optimization
- High-performance query execution with caching
- Comprehensive error handling and logging
- Type-safe Python code with full annotations
- Scalable architecture for enterprise deployment
"""

from typing import Optional, List, Dict, Any, Union, Tuple, TypeVar, Generic, Type
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time
import asyncio
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import logging
from functools import wraps, lru_cache
from abc import ABC, abstractmethod

from django.db import transaction, connection, connections, DatabaseError
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg, F, Window, Max, Min, Prefetch, OuterRef, Subquery, Exists
from django.db.models.functions import Coalesce, RowNumber, Lead, Lag, Trunc, TruncDate, TruncHour
from django.db.models.expressions import RawSQL, Case, When, Value
from django.db.transaction import atomic, savepoint, savepoint_commit, savepoint_rollback
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction as django_transaction
from django.db.backends.utils import CursorWrapper

from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

# Import all 42 models from the MODELS directory
from api.advertiser_portal.models.advertiser import (
    Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
)
from api.advertiser_portal.models.campaign import (
    AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
)
from api.advertiser_portal.models.offer import (
    AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
)
from api.advertiser_portal.models.tracking import (
    TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain
)
from api.advertiser_portal.models.billing import (
    AdvertiserWallet, AdvertiserTransaction, AdvertiserDeposit, 
    AdvertiserInvoice, CampaignSpend, BillingAlert
)
from api.advertiser_portal.models.reporting import (
    AdvertiserReport, CampaignReport, PublisherBreakdown, 
    GeoBreakdown, CreativePerformance
)
from api.advertiser_portal.models.fraud_protection import (
    ConversionQualityScore, AdvertiserFraudConfig, InvalidClickLog, 
    ClickFraudSignal, OfferQualityScore, RoutingBlacklist
)
from api.advertiser_portal.models.notification import (
    AdvertiserNotification, AdvertiserAlert, NotificationTemplate
)
from api.advertiser_portal.models.ml import (
    UserJourneyStep, NetworkPerformanceCache, MLModel, MLPrediction
)

User = get_user_model()

# Type variables for generic repositories
T = TypeVar('T', bound=AdvertiserPortalBaseModel)
ModelType = TypeVar('ModelType', bound=AdvertiserPortalBaseModel)

# Configure logging with enterprise standards
logger = logging.getLogger(__name__)


@dataclass
class QueryConfig:
    """Configuration class for database queries."""
    
    # Performance settings
    max_results: int = 1000
    timeout_seconds: int = 30
    use_cache: bool = True
    cache_timeout: int = 300
    
    # Query optimization
    use_select_related: bool = True
    use_prefetch_related: bool = True
    use_only: bool = False
    use_defer: bool = False
    
    # Database settings
    use_read_replica: bool = True
    force_index: Optional[str] = None
    optimize_for: str = 'speed'  # 'speed' or 'memory'
    
    # Pagination
    page: Optional[int] = None
    page_size: int = 20
    offset: Optional[int] = None
    limit: Optional[int] = None
    
    # Sorting
    order_by: Optional[List[str]] = None
    order_by_raw: Optional[str] = None
    
    # Filtering
    filters: Dict[str, Any] = field(default_factory=dict)
    exclude: Dict[str, Any] = field(default_factory=dict)
    search: Optional[str] = None
    search_fields: Optional[List[str]] = None
    
    # Aggregation
    aggregate: Optional[Dict[str, str]] = None
    annotate: Optional[Dict[str, Any]] = None
    
    def validate(self) -> None:
        """Validate query configuration."""
        if self.max_results < 1:
            raise ValueError("max_results must be greater than 0")
        
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be greater than 0")
        
        if self.page and self.page < 1:
            raise ValueError("page must be greater than 0")
        
        if self.page_size < 1 or self.page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000")
        
        if self.offset and self.offset < 0:
            raise ValueError("offset must be non-negative")
        
        if self.limit and self.limit < 1:
            raise ValueError("limit must be greater than 0")


@dataclass
class BulkOperationConfig:
    """Configuration for bulk operations."""
    
    # Batch settings
    batch_size: int = 1000
    max_batch_size: int = 10000
    
    # Performance settings
    use_bulk_create: bool = True
    use_bulk_update: bool = True
    use_bulk_delete: bool = True
    ignore_conflicts: bool = False
    
    # Transaction settings
    use_transaction: bool = True
    transaction_isolation: str = 'READ_COMMITTED'
    
    # Validation settings
    validate_individual: bool = True
    skip_validation: bool = False
    
    def validate(self) -> None:
        """Validate bulk operation configuration."""
        if self.batch_size < 1 or self.batch_size > self.max_batch_size:
            raise ValueError(f"batch_size must be between 1 and {self.max_batch_size}")


class QueryOptimizer:
    """Enterprise query optimizer for performance enhancement."""
    
    @staticmethod
    def optimize_queryset(queryset, config: QueryConfig):
        """Optimize queryset based on configuration."""
        
        # Apply select_related for performance
        if config.use_select_related and hasattr(queryset.model, '_select_related_fields'):
            queryset = queryset.select_related(*queryset.model._select_related_fields)
        
        # Apply prefetch_related for performance
        if config.use_prefetch_related and hasattr(queryset.model, '_prefetch_related_fields'):
            queryset = queryset.prefetch_related(*queryset.model._prefetch_related_fields)
        
        # Apply only() for field limiting
        if config.use_only and hasattr(queryset.model, '_default_fields'):
            queryset = queryset.only(*queryset.model._default_fields)
        
        # Apply defer() for field exclusion
        if config.use_defer and hasattr(queryset.model, '_defer_fields'):
            queryset = queryset.defer(*queryset.model._defer_fields)
        
        # Apply filters
        if config.filters:
            queryset = queryset.filter(**config.filters)
        
        # Apply exclusions
        if config.exclude:
            queryset = queryset.exclude(**config.exclude)
        
        # Apply search
        if config.search and config.search_fields:
            search_q = Q()
            for field in config.search_fields:
                search_q |= Q(**{f"{field}__icontains": config.search})
            queryset = queryset.filter(search_q)
        
        # Apply annotations
        if config.annotate:
            queryset = queryset.annotate(**config.annotate)
        
        # Apply ordering
        if config.order_by:
            queryset = queryset.order_by(*config.order_by)
        elif config.order_by_raw:
            queryset = queryset.order_by(config.order_by_raw)
        
        # Apply limits
        if config.limit:
            queryset = queryset[:config.limit]
        
        # Apply offset
        if config.offset:
            queryset = queryset[config.offset:]
        
        return queryset
    
    @staticmethod
    def get_optimized_connection(read_only: bool = False) -> connection:
        """Get optimized database connection."""
        if read_only and 'read_replica' in connections:
            return connections['read_replica']
        return connection
    
    @staticmethod
    def add_query_hints(query: str, config: QueryConfig) -> str:
        """Add database-specific query hints."""
        engine = settings.DATABASES['default']['ENGINE']
        
        if 'postgresql' in engine:
            hints = []
            
            # Add index hint if specified
            if config.force_index:
                hints.append(f"/*+ INDEX_SCAN({config.force_index}) */")
            
            # Add optimization hint
            if config.optimize_for == 'speed':
                hints.append("/*+ FAST */")
            elif config.optimize_for == 'memory':
                hints.append("/*+ MEMORY */")
            
            if hints:
                query = " ".join(hints) + " " + query
        
        return query


class CacheManager:
    """Enterprise cache manager for query results."""
    
    @staticmethod
    def build_cache_key(model_class: Type, operation: str, **kwargs) -> str:
        """Build cache key for query."""
        key_parts = [
            'advertiser_portal',
            model_class.__name__.lower(),
            operation,
            str(hash(json.dumps(kwargs, sort_keys=True)))
        ]
        return ":".join(key_parts)
    
    @staticmethod
    def get_cached_result(cache_key: str) -> Optional[Any]:
        """Get cached result."""
        return cache.get(cache_key)
    
    @staticmethod
    def set_cached_result(cache_key: str, data: Any, timeout: int = 300) -> None:
        """Set cached result."""
        cache.set(cache_key, data, timeout=timeout)
    
    @staticmethod
    def invalidate_cache(pattern: str) -> None:
        """Invalidate cache entries matching pattern."""
        # This is a simplified implementation
        # In production, use Redis pattern matching
        keys_to_delete = []
        for key in cache.keys():
            if pattern in key:
                keys_to_delete.append(key)
        
        if keys_to_delete:
            cache.delete_many(keys_to_delete)
    
    @staticmethod
    def get_or_set(cache_key: str, factory_func, timeout: int = 300) -> Any:
        """Get from cache or set from factory function."""
        result = cache.get(cache_key)
        if result is None:
            result = factory_func()
            cache.set(cache_key, result, timeout=timeout)
        return result


class BaseRepository(Generic[ModelType], ABC):
    """
    Abstract base repository implementing enterprise-grade data access patterns.
    
    This class provides the foundation for all repository operations with
    security, performance, and scalability features comparable to
    Google Ads API and other industry-leading platforms.
    """
    
    def __init__(self, model_class: Type[ModelType]):
        """Initialize repository with model class."""
        self.model_class = model_class
        self.query_optimizer = QueryOptimizer()
        self.cache_manager = CacheManager()
    
    @property
    def model_name(self) -> str:
        """Get model name."""
        return self.model_class.__name__
    
    def get_queryset(self, config: Optional[QueryConfig] = None):
        """Get base queryset for the model."""
        config = config or QueryConfig()
        
        # Get optimized connection
        connection = self.query_optimizer.get_optimized_connection(read_only=True)
        
        # Get base queryset
        queryset = self.model_class.objects.using(connection).all()
        
        # Apply soft delete filter if model supports it
        if hasattr(self.model_class, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        
        # Apply status filter if model supports it
        if hasattr(self.model_class, 'status'):
            queryset = queryset.filter(status='active')
        
        return queryset
    
    def get_by_id(self, id: Union[UUID, str], config: Optional[QueryConfig] = None) -> Optional[ModelType]:
        """Get model instance by ID."""
        try:
            config = config or QueryConfig()
            
            # Build cache key
            cache_key = self.cache_manager.build_cache_key(
                self.model_class, 'get_by_id', id=str(id)
            )
            
            # Try cache first
            if config.use_cache:
                cached_result = self.cache_manager.get_cached_result(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Apply optimization
            queryset = self.query_optimizer.optimize_queryset(queryset, config)
            
            # Get instance
            instance = queryset.get(id=id)
            
            # Cache result
            if config.use_cache:
                self.cache_manager.set_cached_result(
                    cache_key, instance, config.cache_timeout
                )
            
            return instance
            
        except self.model_class.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting {self.model_name} by ID {id}: {str(e)}")
            raise RepositoryError(f"Failed to get {self.model_name}: {str(e)}")
    
    def get_by_uuid(self, uuid: UUID, config: Optional[QueryConfig] = None) -> Optional[ModelType]:
        """Get model instance by UUID."""
        return self.get_by_id(uuid, config)
    
    def get_all(self, config: Optional[QueryConfig] = None) -> List[ModelType]:
        """Get all model instances."""
        try:
            config = config or QueryConfig()
            
            # Build cache key
            cache_key = self.cache_manager.build_cache_key(
                self.model_class, 'get_all', **config.__dict__
            )
            
            # Try cache first
            if config.use_cache:
                cached_result = self.cache_manager.get_cached_result(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Apply optimization
            queryset = self.query_optimizer.optimize_queryset(queryset, config)
            
            # Apply limit
            if config.max_results:
                queryset = queryset[:config.max_results]
            
            # Get results
            results = list(queryset)
            
            # Cache result
            if config.use_cache:
                self.cache_manager.set_cached_result(
                    cache_key, results, config.cache_timeout
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting all {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to get all {self.model_name}: {str(e)}")
    
    def filter(self, config: QueryConfig) -> List[ModelType]:
        """Filter model instances based on configuration."""
        try:
            # Build cache key
            cache_key = self.cache_manager.build_cache_key(
                self.model_class, 'filter', **config.__dict__
            )
            
            # Try cache first
            if config.use_cache:
                cached_result = self.cache_manager.get_cached_result(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Apply optimization
            queryset = self.query_optimizer.optimize_queryset(queryset, config)
            
            # Apply pagination
            if config.page:
                paginator = Paginator(queryset, config.page_size)
                try:
                    page = paginator.page(config.page)
                    results = list(page.object_list)
                except (EmptyPage, PageNotAnInteger):
                    results = []
            else:
                # Apply limit and offset
                if config.offset:
                    queryset = queryset[config.offset:]
                if config.limit:
                    queryset = queryset[:config.limit]
                
                results = list(queryset)
            
            # Cache result
            if config.use_cache:
                self.cache_manager.set_cached_result(
                    cache_key, results, config.cache_timeout
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Error filtering {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to filter {self.model_name}: {str(e)}")
    
    def count(self, config: Optional[QueryConfig] = None) -> int:
        """Count model instances."""
        try:
            config = config or QueryConfig()
            
            # Build cache key
            cache_key = self.cache_manager.build_cache_key(
                self.model_class, 'count', **config.__dict__
            )
            
            # Try cache first
            if config.use_cache:
                cached_result = self.cache_manager.get_cached_result(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Apply filters
            if config.filters:
                queryset = queryset.filter(**config.filters)
            
            if config.exclude:
                queryset = queryset.exclude(**config.exclude)
            
            # Count
            count = queryset.count()
            
            # Cache result
            if config.use_cache:
                self.cache_manager.set_cached_result(
                    cache_key, count, config.cache_timeout
                )
            
            return count
            
        except Exception as e:
            logger.error(f"Error counting {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to count {self.model_name}: {str(e)}")
    
    def exists(self, id: Union[UUID, str], config: Optional[QueryConfig] = None) -> bool:
        """Check if model instance exists."""
        try:
            config = config or QueryConfig()
            
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Check existence
            return queryset.filter(id=id).exists()
            
        except Exception as e:
            logger.error(f"Error checking {self.model_name} existence: {str(e)}")
            return False
    
    def create(self, data: Dict[str, Any], config: Optional[QueryConfig] = None) -> ModelType:
        """Create new model instance."""
        try:
            config = config or QueryConfig()
            
            # Validate data
            self._validate_data(data)
            
            # Create instance
            instance = self.model_class.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Created {self.model_name} with ID {instance.id}")
            return instance
            
        except Exception as e:
            logger.error(f"Error creating {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to create {self.model_name}: {str(e)}")
    
    def update(self, instance: ModelType, data: Dict[str, Any], config: Optional[QueryConfig] = None) -> ModelType:
        """Update model instance."""
        try:
            config = config or QueryConfig()
            
            # Validate data
            self._validate_data(data, update=True)
            
            # Update instance
            for field, value in data.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            
            instance.save()
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Updated {self.model_name} with ID {instance.id}")
            return instance
            
        except Exception as e:
            logger.error(f"Error updating {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to update {self.model_name}: {str(e)}")
    
    def delete(self, instance: ModelType, soft_delete: bool = True, config: Optional[QueryConfig] = None) -> bool:
        """Delete model instance."""
        try:
            config = config or QueryConfig()
            
            if soft_delete and hasattr(instance, 'soft_delete'):
                instance.soft_delete()
            else:
                instance.delete()
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Deleted {self.model_name} with ID {instance.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to delete {self.model_name}: {str(e)}")
    
    def bulk_create(self, data_list: List[Dict[str, Any]], config: Optional[BulkOperationConfig] = None) -> List[ModelType]:
        """Bulk create model instances."""
        try:
            config = config or BulkOperationConfig()
            config.validate()
            
            # Validate data
            if config.validate_individual:
                for data in data_list:
                    self._validate_data(data)
            
            # Create instances
            instances = []
            if config.use_bulk_create:
                instances = self.model_class.objects.bulk_create(
                    [self.model_class(**data) for data in data_list],
                    batch_size=config.batch_size,
                    ignore_conflicts=config.ignore_conflicts
                )
            else:
                for data in data_list:
                    instance = self.model_class.objects.create(**data)
                    instances.append(instance)
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Bulk created {len(instances)} {self.model_name} instances")
            return instances
            
        except Exception as e:
            logger.error(f"Error bulk creating {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to bulk create {self.model_name}: {str(e)}")
    
    def bulk_update(self, instances: List[ModelType], fields: List[str], config: Optional[BulkOperationConfig] = None) -> int:
        """Bulk update model instances."""
        try:
            config = config or BulkOperationConfig()
            config.validate()
            
            # Update instances
            if config.use_bulk_update:
                updated_count = self.model_class.objects.bulk_update(
                    instances, fields, batch_size=config.batch_size
                )
            else:
                updated_count = 0
                for instance in instances:
                    instance.save()
                    updated_count += 1
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Bulk updated {updated_count} {self.model_name} instances")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error bulk updating {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to bulk update {self.model_name}: {str(e)}")
    
    def bulk_delete(self, instances: List[ModelType], soft_delete: bool = True, config: Optional[BulkOperationConfig] = None) -> int:
        """Bulk delete model instances."""
        try:
            config = config or BulkOperationConfig()
            config.validate()
            
            # Delete instances
            if soft_delete and hasattr(self.model_class, 'soft_delete'):
                for instance in instances:
                    instance.soft_delete()
                deleted_count = len(instances)
            elif config.use_bulk_delete:
                deleted_count = self.model_class.objects.bulk_delete(instances, batch_size=config.batch_size)
            else:
                deleted_count = 0
                for instance in instances:
                    instance.delete()
                    deleted_count += 1
            
            # Invalidate cache
            self._invalidate_cache_pattern()
            
            logger.info(f"Bulk deleted {deleted_count} {self.model_name} instances")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error bulk deleting {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to bulk delete {self.model_name}: {str(e)}")
    
    def aggregate(self, config: QueryConfig) -> Dict[str, Any]:
        """Perform aggregation on model instances."""
        try:
            # Get queryset
            queryset = self.get_queryset(config)
            
            # Apply filters
            if config.filters:
                queryset = queryset.filter(**config.filters)
            
            # Apply aggregation
            if config.aggregate:
                result = queryset.aggregate(**config.aggregate)
            else:
                result = {}
            
            return result
            
        except Exception as e:
            logger.error(f"Error aggregating {self.model_name}: {str(e)}")
            raise RepositoryError(f"Failed to aggregate {self.model_name}: {str(e)}")
    
    def _validate_data(self, data: Dict[str, Any], update: bool = False) -> None:
        """Validate data for create/update operations."""
        # This can be overridden by subclasses
        pass
    
    def _invalidate_cache_pattern(self) -> None:
        """Invalidate cache patterns for this model."""
        pattern = f"*{self.model_name.lower()}*"
        self.cache_manager.invalidate_cache(pattern)
    
    @contextmanager
    def transaction(self, isolation: str = 'READ_COMMITTED'):
        """Context manager for database transactions."""
        try:
            with django_transaction.atomic():
                yield
        except Exception as e:
            logger.error(f"Transaction failed for {self.model_name}: {str(e)}")
            raise


class AdvertiserRepository(BaseRepository[Advertiser]):
    """Repository for Advertiser model with specialized queries."""
    
    def __init__(self):
        super().__init__(Advertiser)
    
    def get_by_user(self, user: User, config: Optional[QueryConfig] = None) -> Optional[Advertiser]:
        """Get advertiser by user."""
        try:
            config = config or QueryConfig()
            config.filters = config.filters or {}
            config.filters['user'] = user
            
            advertisers = self.filter(config)
            return advertisers[0] if advertisers else None
            
        except Exception as e:
            logger.error(f"Error getting advertiser by user {user.id}: {str(e)}")
            raise RepositoryError(f"Failed to get advertiser by user: {str(e)}")
    
    def get_verified_advertisers(self, config: Optional[QueryConfig] = None) -> List[Advertiser]:
        """Get verified advertisers."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['is_verified'] = True
        
        return self.filter(config)
    
    def get_active_advertisers(self, config: Optional[QueryConfig] = None) -> List[Advertiser]:
        """Get active advertisers."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['status'] = 'active'
        
        return self.filter(config)
    
    def search_advertisers(self, query: str, config: Optional[QueryConfig] = None) -> List[Advertiser]:
        """Search advertisers by company name or email."""
        config = config or QueryConfig()
        config.search = query
        config.search_fields = ['company_name', 'contact_email', 'user__email']
        
        return self.filter(config)
    
    def get_advertisers_by_industry(self, industry: str, config: Optional[QueryConfig] = None) -> List[Advertiser]:
        """Get advertisers by industry."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['industry'] = industry
        
        return self.filter(config)


class CampaignRepository(BaseRepository[Campaign]):
    """Repository for Campaign model with specialized queries."""
    
    def __init__(self):
        super().__init__(Campaign)
    
    def get_by_advertiser(self, advertiser: Advertiser, config: Optional[QueryConfig] = None) -> List[Campaign]:
        """Get campaigns by advertiser."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['advertiser'] = advertiser
        
        return self.filter(config)
    
    def get_active_campaigns(self, config: Optional[QueryConfig] = None) -> List[Campaign]:
        """Get active campaigns."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['status'] = 'active'
        
        return self.filter(config)
    
    def get_campaigns_by_objective(self, objective: str, config: Optional[QueryConfig] = None) -> List[Campaign]:
        """Get campaigns by objective."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['objective'] = objective
        
        return self.filter(config)
    
    def get_campaigns_with_performance(self, config: Optional[QueryConfig] = None) -> List[Dict[str, Any]]:
        """Get campaigns with performance metrics."""
        config = config or QueryConfig()
        config.annotate = {
            'ctr': Case(
                When(impressions__gt=0, then=F('clicks') * 100.0 / F('impressions')),
                default=Value(0.0)
            ),
            'cpc': Case(
                When(clicks__gt=0, then=F('current_spend') / F('clicks')),
                default=Value(0.0)
            ),
            'conversion_rate': Case(
                When(clicks__gt=0, then=F('conversions') * 100.0 / F('clicks')),
                default=Value(0.0)
            )
        }
        
        campaigns = self.filter(config)
        return [
            {
                'id': str(campaign.id),
                'name': campaign.name,
                'status': campaign.status,
                'impressions': campaign.impressions,
                'clicks': campaign.clicks,
                'conversions': campaign.conversions,
                'current_spend': float(campaign.current_spend),
                'ctr': float(campaign.ctr) if hasattr(campaign, 'ctr') else 0.0,
                'cpc': float(campaign.cpc) if hasattr(campaign, 'cpc') else 0.0,
                'conversion_rate': float(campaign.conversion_rate) if hasattr(campaign, 'conversion_rate') else 0.0,
            }
            for campaign in campaigns
        ]


class CreativeRepository(BaseRepository[Creative]):
    """Repository for Creative model with specialized queries."""
    
    def __init__(self):
        super().__init__(Creative)
    
    def get_by_campaign(self, campaign: Campaign, config: Optional[QueryConfig] = None) -> List[Creative]:
        """Get creatives by campaign."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['campaign'] = campaign
        
        return self.filter(config)
    
    def get_approved_creatives(self, config: Optional[QueryConfig] = None) -> List[Creative]:
        """Get approved creatives."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['is_approved'] = True
        
        return self.filter(config)
    
    def get_creatives_by_type(self, creative_type: str, config: Optional[QueryConfig] = None) -> List[Creative]:
        """Get creatives by type."""
        config = config or QueryConfig()
        config.filters = config.filters or {}
        config.filters['type'] = creative_type
        
        return self.filter(config)


# Export main repository classes
__all__ = [
    'QueryConfig',
    'BulkOperationConfig',
    'QueryOptimizer',
    'CacheManager',
    'BaseRepository',
    'AdvertiserRepository',
    'CampaignRepository',
    'CreativeRepository',
]
        """
        Get all instances.
        
        Args:
            include_deleted: Whether to include soft-deleted instances
            
        Returns:
            QuerySet of instances
        """
        queryset = self.model.objects.all()
        if not include_deleted and hasattr(self.model, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset
    
    def filter(self, **kwargs) -> models.QuerySet:
        """
        Filter instances by criteria.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            Filtered QuerySet
        """
        queryset = self.model.objects.all()
        if hasattr(self.model, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset.filter(**kwargs)
    
    def create(self, **kwargs) -> models.Model:
        """
        Create new instance.
        
        Args:
            **kwargs: Instance data
            
        Returns:
            Created instance
        """
        return self.model.objects.create(**kwargs)
    
    def update(self, instance: models.Model, **kwargs) -> models.Model:
        """
        Update instance.
        
        Args:
            instance: Instance to update
            **kwargs: Update data
            
        Returns:
            Updated instance
        """
        for field, value in kwargs.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        instance.save()
        return instance
    
    def delete(self, instance: models.Model, soft_delete: bool = True) -> None:
        """
        Delete instance.
        
        Args:
            instance: Instance to delete
            soft_delete: Whether to perform soft delete
        """
        if soft_delete and hasattr(instance, 'soft_delete'):
            instance.soft_delete()
        else:
            instance.delete()
    
    def bulk_create(self, instances: List[models.Model]) -> List[models.Model]:
        """
        Bulk create instances.
        
        Args:
            instances: List of instances to create
            
        Returns:
            Created instances
        """
        return self.model.objects.bulk_create(instances)
    
    def bulk_update(self, instances: List[models.Model], fields: List[str]) -> int:
        """
        Bulk update instances.
        
        Args:
            instances: List of instances to update
            fields: Fields to update
            
        Returns:
            Number of updated instances
        """
        return self.model.objects.bulk_update(instances, fields)
    
    def count(self, **kwargs) -> int:
        """
        Count instances matching criteria.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            Count of instances
        """
        queryset = self.model.objects.all()
        if hasattr(self.model, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        if kwargs:
            queryset = queryset.filter(**kwargs)
        return queryset.count()
    
    def exists(self, **kwargs) -> bool:
        """
        Check if instance exists matching criteria.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            True if instance exists
        """
        queryset = self.model.objects.all()
        if hasattr(self.model, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        if kwargs:
            queryset = queryset.filter(**kwargs)
        return queryset.exists()


class AdvertiserRepository(BaseRepository):
    """Repository for Advertiser model operations."""
    
    model = Advertiser
    
    def get_by_user(self, user) -> Optional[Advertiser]:
        """Get advertiser by user."""
        try:
            return Advertiser.objects.get(user=user, is_deleted=False)
        except Advertiser.DoesNotExist:
            return None
    
    def get_by_api_key(self, api_key: str) -> Optional[Advertiser]:
        """Get advertiser by API key."""
        try:
            return Advertiser.objects.get(api_key=api_key, is_deleted=False)
        except Advertiser.DoesNotExist:
            return None
    
    def get_by_company_name(self, company_name: str) -> Optional[Advertiser]:
        """Get advertiser by company name."""
        try:
            return Advertiser.objects.get(company_name=company_name, is_deleted=False)
        except Advertiser.DoesNotExist:
            return None
    
    def get_verified_advertisers(self) -> models.QuerySet:
        """Get all verified advertisers."""
        return Advertiser.objects.filter(
            is_verified=True,
            is_deleted=False
        )
    
    def get_pending_verification(self) -> models.QuerySet:
        """Get advertisers pending verification."""
        return Advertiser.objects.filter(
            is_verified=False,
            status=StatusEnum.PENDING.value,
            is_deleted=False
        )
    
    def get_by_industry(self, industry: str) -> models.QuerySet:
        """Get advertisers by industry."""
        return Advertiser.objects.filter(
            industry=industry,
            is_deleted=False
        )
    
    def get_active_advertisers(self) -> models.QuerySet:
        """Get active advertisers."""
        return Advertiser.objects.filter(
            status=StatusEnum.ACTIVE.value,
            is_verified=True,
            is_deleted=False
        )
    
    def get_advertiser_stats(self, advertiser_id: UUID) -> Dict[str, Any]:
        """Get comprehensive advertiser statistics."""
        try:
            advertiser = self.get_by_id(advertiser_id)
            if not advertiser:
                return {}
            
            # Campaign statistics
            campaign_stats = Campaign.objects.filter(
                advertiser=advertiser,
                is_deleted=False
            ).aggregate(
                total_campaigns=Count('id'),
                active_campaigns=Count('id', filter=Q(status=StatusEnum.ACTIVE.value)),
                total_budget=Sum('total_budget'),
                current_spend=Sum('current_spend'),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions')
            )
            
            # Financial statistics
            billing_stats = AdvertiserCredit.objects.filter(
                advertiser=advertiser
            ).aggregate(
                total_credit=Sum('amount'),
                credit_count=Count('id')
            )
            
            return {
                'advertiser_id': str(advertiser.id),
                'company_name': advertiser.company_name,
                'status': advertiser.status,
                'is_verified': advertiser.is_verified,
                'created_at': advertiser.created_at.isoformat(),
                **campaign_stats,
                **billing_stats
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def search_advertisers(self, query: str, filters: Optional[Dict[str, Any]] = None) -> models.QuerySet:
        """
        Search advertisers by query string.
        
        Args:
            query: Search query
            filters: Additional filters
            
        Returns:
            Filtered QuerySet
        """
        queryset = Advertiser.objects.filter(is_deleted=False)
        
        if query:
            queryset = queryset.filter(
                Q(company_name__icontains=query) |
                Q(contact_email__icontains=query) |
                Q(website__icontains=query) |
                Q(industry__icontains=query)
            )
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'industry' in filters:
                queryset = queryset.filter(industry=filters['industry'])
            if 'is_verified' in filters:
                queryset = queryset.filter(is_verified=filters['is_verified'])
        
        return queryset.distinct()


class CampaignRepository(BaseRepository):
    """Repository for Campaign model operations."""
    
    model = Campaign
    
    def get_by_advertiser(self, advertiser: Advertiser) -> models.QuerySet:
        """Get campaigns by advertiser."""
        return Campaign.objects.filter(
            advertiser=advertiser,
            is_deleted=False
        )
    
    def get_active_campaigns(self) -> models.QuerySet:
        """Get all active campaigns."""
        return Campaign.objects.filter(
            status=StatusEnum.ACTIVE.value,
            is_deleted=False
        )
    
    def get_campaigns_by_objective(self, objective: str) -> models.QuerySet:
        """Get campaigns by objective."""
        return Campaign.objects.filter(
            objective=objective,
            is_deleted=False
        )
    
    def get_campaigns_by_date_range(self, start_date: date, end_date: date) -> models.QuerySet:
        """Get campaigns within date range."""
        return Campaign.objects.filter(
            start_date__lte=end_date,
            Q(end_date__gte=start_date) | Q(end_date__isnull=True),
            is_deleted=False
        )
    
    def get_campaigns_with_budget_remaining(self) -> models.QuerySet:
        """Get campaigns with remaining budget."""
        return Campaign.objects.filter(
            status=StatusEnum.ACTIVE.value,
            current_spend__lt=F('total_budget'),
            is_deleted=False
        )
    
    def get_campaign_performance_summary(self, campaign_ids: Optional[List[UUID]] = None) -> Dict[str, Any]:
        """Get performance summary for campaigns."""
        queryset = Campaign.objects.filter(is_deleted=False)
        
        if campaign_ids:
            queryset = queryset.filter(id__in=campaign_ids)
        
        return queryset.aggregate(
            total_campaigns=Count('id'),
            active_campaigns=Count('id', filter=Q(status=StatusEnum.ACTIVE.value)),
            total_budget=Sum('total_budget'),
            current_spend=Sum('current_spend'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            avg_ctr=Avg('ctr'),
            avg_cpc=Avg('cpc'),
            avg_conversion_rate=Avg('conversion_rate')
        )
    
    def get_top_performing_campaigns(self, metric: str = 'conversions', limit: int = 10) -> models.QuerySet:
        """Get top performing campaigns by metric."""
        order_field = f'-{metric}'
        return Campaign.objects.filter(
            is_deleted=False
        ).order_by(order_field)[:limit]
    
    def search_campaigns(self, query: str, advertiser_id: Optional[UUID] = None) -> models.QuerySet:
        """Search campaigns by query string."""
        queryset = Campaign.objects.filter(is_deleted=False)
        
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        return queryset.distinct()


class CreativeRepository(BaseRepository):
    """Repository for Creative model operations."""
    
    model = Creative
    
    def get_by_campaign(self, campaign: Campaign) -> models.QuerySet:
        """Get creatives by campaign."""
        return Creative.objects.filter(
            campaign=campaign,
            is_deleted=False
        )
    
    def get_approved_creatives(self) -> models.QuerySet:
        """Get all approved creatives."""
        return Creative.objects.filter(
            is_approved=True,
            status=StatusEnum.ACTIVE.value,
            is_deleted=False
        )
    
    def get_creatives_by_type(self, creative_type: str) -> models.QuerySet:
        """Get creatives by type."""
        return Creative.objects.filter(
            type=creative_type,
            is_deleted=False
        )
    
    def get_pending_approval(self) -> models.QuerySet:
        """Get creatives pending approval."""
        return Creative.objects.filter(
            is_approved=False,
            status=StatusEnum.PENDING.value,
            is_deleted=False
        )
    
    def get_creative_performance_stats(self, creative_id: UUID) -> Dict[str, Any]:
        """Get performance statistics for creative."""
        try:
            creative = self.get_by_id(creative_id)
            if not creative:
                return {}
            
            return {
                'creative_id': str(creative.id),
                'name': creative.name,
                'type': creative.type,
                'status': creative.status,
                'is_approved': creative.is_approved,
                'impressions': creative.impressions,
                'clicks': creative.clicks,
                'conversions': creative.conversions,
                'ctr': float(creative.ctr),
                'cpc': float(creative.cpc),
                'conversion_rate': float(creative.conversion_rate),
                'created_at': creative.created_at.isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_top_performing_creatives(self, metric: str = 'ctr', limit: int = 10) -> models.QuerySet:
        """Get top performing creatives by metric."""
        order_field = f'-{metric}'
        return Creative.objects.filter(
            is_approved=True,
            is_deleted=False
        ).order_by(order_field)[:limit]


class TargetingRepository(BaseRepository):
    """Repository for Targeting model operations."""
    
    model = Targeting
    
    def get_by_campaign(self, campaign: Campaign) -> Optional[Targeting]:
        """Get targeting by campaign."""
        try:
            return Targeting.objects.get(campaign=campaign, is_deleted=False)
        except Targeting.DoesNotExist:
            return None
    
    def get_targeting_by_geo(self, countries: List[str]) -> models.QuerySet:
        """Get targeting by countries."""
        return Targeting.objects.filter(
            geo_targeting__countries__overlap=countries,
            is_deleted=False
        )
    
    def get_targeting_by_device(self, device_types: List[str]) -> models.QuerySet:
        """Get targeting by device types."""
        return Targeting.objects.filter(
            device_targeting__device_types__overlap=device_types,
            is_deleted=False
        )
    
    def get_targeting_by_demographics(self, age_min: Optional[int] = None, 
                                   age_max: Optional[int] = None,
                                   genders: Optional[List[str]] = None) -> models.QuerySet:
        """Get targeting by demographics."""
        queryset = Targeting.objects.filter(is_deleted=False)
        
        if age_min is not None:
            queryset = queryset.filter(age_min__gte=age_min)
        if age_max is not None:
            queryset = queryset.filter(age_max__lte=age_max)
        if genders:
            queryset = queryset.filter(genders__overlap=genders)
        
        return queryset


class AnalyticsRepository(BaseRepository):
    """Repository for analytics data operations."""
    
    def get_impression_stats(self, start_date: date, end_date: date, 
                           advertiser_id: Optional[UUID] = None,
                           campaign_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get impression statistics."""
        queryset = Campaign.objects.filter(is_deleted=False)
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        if campaign_id:
            queryset = queryset.filter(id=campaign_id)
        
        return queryset.aggregate(
            total_impressions=Sum('impressions'),
            unique_impressions=Sum('impressions'),  # Would need separate tracking
            avg_impressions_per_campaign=Avg('impressions')
        )
    
    def get_click_stats(self, start_date: date, end_date: date,
                       advertiser_id: Optional[UUID] = None,
                       campaign_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get click statistics."""
        queryset = Campaign.objects.filter(is_deleted=False)
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        if campaign_id:
            queryset = queryset.filter(id=campaign_id)
        
        return queryset.aggregate(
            total_clicks=Sum('clicks'),
            unique_clicks=Sum('clicks'),  # Would need separate tracking
            avg_clicks_per_campaign=Avg('clicks'),
            avg_ctr=Avg('ctr')
        )
    
    def get_conversion_stats(self, start_date: date, end_date: date,
                           advertiser_id: Optional[UUID] = None,
                           campaign_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get conversion statistics."""
        queryset = Campaign.objects.filter(is_deleted=False)
        
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        if campaign_id:
            queryset = queryset.filter(id=campaign_id)
        
        return queryset.aggregate(
            total_conversions=Sum('conversions'),
            unique_conversions=Sum('conversions'),  # Would need separate tracking
            avg_conversions_per_campaign=Avg('conversions'),
            avg_conversion_rate=Avg('conversion_rate'),
            total_cost=Sum('current_spend'),
            avg_cpa=Avg('cpa')
        )
    
    def get_time_series_data(self, metric: str, start_date: date, end_date: date,
                           granularity: str = 'daily') -> List[Dict[str, Any]]:
        """Get time series data for a metric."""
        # This would typically involve a separate analytics table with time-based data
        # For now, returning empty list as placeholder
        return []
    
    def get_geographic_performance(self, start_date: date, end_date: date,
                                  advertiser_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """Get performance data by geographic location."""
        # This would involve joining with geo-targeting data
        # For now, returning empty list as placeholder
        return []


class BillingRepository(BaseRepository):
    """Repository for billing and payment operations."""
    
    def get_invoices_by_advertiser(self, advertiser: Advertiser) -> models.QuerySet:
        """Get invoices by advertiser."""
        return Invoice.objects.filter(advertiser=advertiser).order_by('-created_at')
    
    def get_pending_invoices(self) -> models.QuerySet:
        """Get all pending invoices."""
        return Invoice.objects.filter(status=StatusEnum.PENDING.value)
    
    def get_overdue_invoices(self) -> models.QuerySet:
        """Get overdue invoices."""
        return Invoice.objects.filter(
            status=StatusEnum.PENDING.value,
            due_date__lt=timezone.now().date()
        )
    
    def get_payment_methods_by_advertiser(self, advertiser: Advertiser) -> models.QuerySet:
        """Get payment methods by advertiser."""
        return PaymentMethod.objects.filter(
            advertiser=advertiser,
            is_active=True
        )
    
    def get_transactions_by_advertiser(self, advertiser: Advertiser) -> models.QuerySet:
        """Get transactions by advertiser."""
        return PaymentTransaction.objects.filter(advertiser=advertiser).order_by('-created_at')
    
    def get_billing_summary(self, advertiser_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get billing summary."""
        queryset = Invoice.objects.all()
        if advertiser_id:
            queryset = queryset.filter(advertiser_id=advertiser_id)
        
        return queryset.aggregate(
            total_invoices=Count('id'),
            pending_invoices=Count('id', filter=Q(status=StatusEnum.PENDING.value)),
            total_amount=Sum('total_amount'),
            total_paid=Sum('total_amount', filter=Q(status=StatusEnum.ACTIVE.value)),
            total_outstanding=Sum('total_amount', filter=Q(status=StatusEnum.PENDING.value))
        )
    
    def get_monthly_revenue(self, year: int, month: int) -> Decimal:
        """Get monthly revenue."""
        return PaymentTransaction.objects.filter(
            status='completed',
            created_at__year=year,
            created_at__month=month
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')


class FraudDetectionRepository(BaseRepository):
    """Repository for fraud detection operations."""
    
    def get_suspicious_activities(self, start_date: date, end_date: date) -> models.QuerySet:
        """Get suspicious activities within date range."""
        return FraudLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('-created_at')
    
    def get_fraud_by_type(self, fraud_type: str) -> models.QuerySet:
        """Get fraud logs by type."""
        return FraudLog.objects.filter(fraud_type=fraud_type).order_by('-created_at')
    
    def get_blocked_ips(self) -> models.QuerySet:
        """Get blocked IP addresses."""
        return IPBlacklist.objects.filter(is_active=True)
    
    def get_fraud_stats(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get fraud statistics."""
        return FraudLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).aggregate(
            total_fraud_attempts=Count('id'),
            blocked_attempts=Count('id', filter=Q(action_taken='blocked')),
            flagged_attempts=Count('id', filter=Q(action_taken='flagged')),
            unique_ips=Count('ip_address', distinct=True),
            unique_users=Count('user_id', distinct=True)
        )


# Repository Factory for easy access
class RepositoryFactory:
    """Factory class for creating repository instances."""
    
    _repositories = {
        'advertiser': AdvertiserRepository,
        'campaign': CampaignRepository,
        'creative': CreativeRepository,
        'targeting': TargetingRepository,
        'analytics': AnalyticsRepository,
        'billing': BillingRepository,
        'fraud': FraudDetectionRepository,
    }
    
    @classmethod
    def get_repository(cls, name: str) -> BaseRepository:
        """
        Get repository instance by name.
        
        Args:
            name: Repository name
            
        Returns:
            Repository instance
        """
        if name not in cls._repositories:
            raise ValueError(f"Unknown repository: {name}")
        
        return cls._repositories[name]()
    
    @classmethod
    def register_repository(cls, name: str, repository_class: type) -> None:
        """
        Register a new repository.
        
        Args:
            name: Repository name
            repository_class: Repository class
        """
        cls._repositories[name] = repository_class
