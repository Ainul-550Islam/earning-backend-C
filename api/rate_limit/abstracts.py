# api/rate_limit/abstracts.py
"""
Abstract base classes for rate limit module.

Provides abstract models and base classes for inheritance.
"""
from django.http import HttpResponse

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from api.tenants.models import TenantModel

logger = logging.getLogger(__name__)
User = get_user_model()


class AbstractRateLimitModel(TenantModel):
    """
    Abstract base model for rate limit related models.
    """
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True
    
    def clean(self):
        """Validate model data."""
        super().clean()
        self.validate_business_rules()
    
    def validate_business_rules(self):
        """Validate business-specific rules."""
        pass
    
    def soft_delete(self):
        """Soft delete the record."""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def restore(self):
        """Restore soft deleted record."""
        self.is_active = True
        self.save(update_fields=['is_active'])


class AbstractConfigurableModel(AbstractRateLimitModel):
    """
    Abstract model for configurable rate limit entities.
    """
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    config = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any):
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
        self.save(update_fields=['config'])
    
    def validate_business_rules(self):
        """Validate configuration rules."""
        super().validate_business_rules()
        
        if not self.name:
            raise ValidationError({'name': 'Name is required'})
        
        if len(self.name) > 100:
            raise ValidationError({'name': 'Name cannot exceed 100 characters'})


class AbstractUserTrackingModel(AbstractRateLimitModel):
    """
    Abstract model for user tracking.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_set'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        abstract = True
    
    def get_identifier(self) -> str:
        """
        Get unique identifier for tracking.
        
        Returns:
            Identifier string
        """
        if self.user:
            return f"user:{self.user.id}"
        elif self.ip_address:
            return f"ip:{self.ip_address}"
        else:
            return f"anonymous:{self.id}"
    
    def validate_business_rules(self):
        """Validate user tracking rules."""
        super().validate_business_rules()
        
        if not self.user and not self.ip_address:
            raise ValidationError('Either user or IP address must be specified')


class AbstractTimeSeriesModel(AbstractRateLimitModel):
    """
    Abstract model for time series data.
    """
    
    timestamp = models.DateTimeField(default=timezone.now)
    date = models.DateField(db_index=True)
    hour = models.IntegerField(default=0)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['date', 'hour']),
            models.Index(fields=['timestamp']),
        ]
    
    def save(self, *args, **kwargs):
        """Set date and hour before saving."""
        if self.timestamp:
            self.date = self.timestamp.date()
            self.hour = self.timestamp.hour
        super().save(*args, **kwargs)
    
    @classmethod
    def get_time_range_data(cls, start_date, end_date):
        """
        Get data for date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            QuerySet
        """
        return cls.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('timestamp')


class AbstractMetricModel(AbstractTimeSeriesModel):
    """
    Abstract model for metric data.
    """
    
    value = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, default='count')
    tags = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True
    
    def get_tag_value(self, key: str, default: Any = None) -> Any:
        """Get tag value."""
        return self.tags.get(key, default)
    
    def set_tag_value(self, key: str, value: Any):
        """Set tag value."""
        self.tags[key] = value
        self.save(update_fields=['tags'])


class AbstractRateLimitService(ABC):
    """
    Abstract base class for rate limiting services.
    """
    
    @abstractmethod
    def check_rate_limit(self, identifier: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if identifier is within rate limits.
        
        Args:
            identifier: Unique identifier (user ID, IP, etc.)
            config: Rate limit configuration
            
        Returns:
            Result dictionary with is_allowed, remaining, etc.
        """
        pass
    
    @abstractmethod
    def reset_rate_limit(self, identifier: str, config: Dict[str, Any]) -> bool:
        """
        Reset rate limit for identifier.
        
        Args:
            identifier: Unique identifier
            config: Rate limit configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_current_usage(self, identifier: str, config: Dict[str, Any]) -> int:
        """
        Get current usage for identifier.
        
        Args:
            identifier: Unique identifier
            config: Rate limit configuration
            
        Returns:
            Current usage count
        """
        pass


class AbstractStorageBackend(ABC):
    """
    Abstract base class for storage backends.
    """
    
    @abstractmethod
    def store(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Store value with optional TTL.
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def retrieve(self, key: str) -> Any:
        """
        Retrieve value by key.
        
        Args:
            key: Storage key
            
        Returns:
            Stored value or None
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete value by key.
        
        Args:
            key: Storage key
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def increment(self, key: str, amount: int = 1, ttl: int = None) -> int:
        """
        Increment counter value.
        
        Args:
            key: Storage key
            amount: Amount to increment
            ttl: Time to live in seconds
            
        Returns:
            New value after increment
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Storage key
            
        Returns:
            True if key exists, False otherwise
        """
        pass


class AbstractAnalyticsService(ABC):
    """
    Abstract base class for analytics services.
    """
    
    @abstractmethod
    def track_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Track analytics event.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        pass
    
    @abstractmethod
    def generate_report(self, start_date: str, end_date: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate analytics report.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filters: Optional filters
            
        Returns:
            Report data
        """
        pass
    
    @abstractmethod
    def get_metrics(self, metric_names: List[str], time_range: str = '24h') -> Dict[str, Any]:
        """
        Get specific metrics.
        
        Args:
            metric_names: List of metric names
            time_range: Time range (1h, 24h, 7d, 30d)
            
        Returns:
            Metrics data
        """
        pass


class AbstractNotificationService(ABC):
    """
    Abstract base class for notification services.
    """
    
    @abstractmethod
    def send_notification(self, message: str, recipients: List[str], 
                         severity: str = 'info', context: Dict[str, Any] = None) -> bool:
        """
        Send notification to recipients.
        
        Args:
            message: Notification message
            recipients: List of recipient identifiers
            severity: Severity level (info, warning, error, critical)
            context: Additional context
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def send_bulk_notification(self, notifications: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Send multiple notifications in bulk.
        
        Args:
            notifications: List of notification dictionaries
            
        Returns:
            Results dictionary with success/failure counts
        """
        pass


class AbstractAbuseDetector(ABC):
    """
    Abstract base class for abuse detection.
    """
    
    @abstractmethod
    def analyze_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze request for abuse patterns.
        
        Args:
            request_data: Request data to analyze
            
        Returns:
            Analysis results
        """
        pass
    
    @abstractmethod
    def detect_patterns(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect abuse patterns from logs.
        
        Args:
            logs: List of log entries
            
        Returns:
            List of detected patterns
        """
        pass
    
    @abstractmethod
    def calculate_risk_score(self, entity_data: Dict[str, Any]) -> int:
        """
        Calculate risk score for entity.
        
        Args:
            entity_data: Entity data (user, IP, etc.)
            
        Returns:
            Risk score (0-100)
        """
        pass


class AbstractRateLimitAlgorithm(ABC):
    """
    Abstract base class for rate limiting algorithms.
    """
    
    @abstractmethod
    def is_allowed(self, key: str, limit: int, window: int, 
                   current_time: int = None) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed using algorithm.
        
        Args:
            key: Unique key for rate limiting
            limit: Maximum requests allowed
            window: Time window in seconds
            current_time: Current timestamp (optional)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        pass
    
    @abstractmethod
    def reset(self, key: str) -> bool:
        """
        Reset rate limit for key.
        
        Args:
            key: Rate limit key
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_stats(self, key: str) -> Dict[str, Any]:
        """
        Get statistics for key.
        
        Args:
            key: Rate limit key
            
        Returns:
            Statistics dictionary
        """
        pass


class AbstractRateLimitStrategy(ABC):
    """
    Abstract base class for rate limiting strategies.
    """
    
    @abstractmethod
    def apply_strategy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply rate limiting strategy.
        
        Args:
            context: Request context
            
        Returns:
            Modified context with strategy results
        """
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get strategy priority (lower number = higher priority).
        
        Returns:
            Priority value
        """
        pass
    
    @abstractmethod
    def is_applicable(self, context: Dict[str, Any]) -> bool:
        """
        Check if strategy is applicable to context.
        
        Args:
            context: Request context
            
        Returns:
            True if applicable, False otherwise
        """
        pass


class AbstractRateLimitMiddleware(ABC):
    """
    Abstract base class for rate limiting middleware.
    """
    
    @abstractmethod
    def process_request(self, request) -> Optional[HttpResponse]:
        """
        Process incoming request.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response if rate limited, None otherwise
        """
        pass
    
    @abstractmethod
    def process_response(self, request, response) -> HttpResponse:
        """
        Process outgoing response.
        
        Args:
            request: HTTP request
            response: HTTP response
            
        Returns:
            Modified HTTP response
        """
        pass


class AbstractRateLimitView(ABC):
    """
    Abstract base class for rate limiting views.
    """
    
    @abstractmethod
    def get_rate_limit_config(self) -> Dict[str, Any]:
        """
        Get rate limit configuration for view.
        
        Returns:
            Configuration dictionary
        """
        pass
    
    @abstractmethod
    def handle_rate_limit_exceeded(self, request) -> HttpResponse:
        """
        Handle rate limit exceeded.
        
        Args:
            request: HTTP request
            
        Returns:
            HTTP response
        """
        pass
    
    @abstractmethod
    def get_identifier(self, request) -> str:
        """
        Get identifier for rate limiting.
        
        Args:
            request: HTTP request
            
        Returns:
            Identifier string
        """
        pass


# Export abstract classes
__all__ = [
    'AbstractRateLimitModel',
    'AbstractConfigurableModel',
    'AbstractUserTrackingModel',
    'AbstractTimeSeriesModel',
    'AbstractMetricModel',
    'AbstractRateLimitService',
    'AbstractStorageBackend',
    'AbstractAnalyticsService',
    'AbstractNotificationService',
    'AbstractAbuseDetector',
    'AbstractRateLimitAlgorithm',
    'AbstractRateLimitStrategy',
    'AbstractRateLimitMiddleware',
    'AbstractRateLimitView'
]
