"""
api/ad_networks/abstracts.py
Abstract base classes for ad networks module
SaaS-ready with tenant support
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD

logger = logging.getLogger(__name__)
User = get_user_model()


class TenantModel(models.Model):
    """
    Abstract base model with tenant support
    """
    
    tenant_id = models.CharField(
        max_length=50,
        default='default',
        db_index=True,
        help_text="Tenant identifier for multi-tenancy"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant_id', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to ensure tenant_id is set"""
        if not self.tenant_id:
            self.tenant_id = 'default'
        super().save(*args, **kwargs)


class TimestampedModel(models.Model):
    """
    Abstract base model with timestamps
    """
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]


class SoftDeleteModel(models.Model):
    """
    Abstract base model with soft delete
    """
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this record is active"
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deletion timestamp"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['is_active', 'deleted_at']),
        ]
    
    def delete(self, using=None, keep_parents=False):
        """Override delete to implement soft delete"""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Perform hard delete"""
        super().delete(using=using, keep_parents=keep_parents)


class FraudDetectionModel(models.Model):
    """
    Abstract base model with fraud detection
    """
    
    fraud_score = models.FloatField(
        default=0.0,
        help_text="Fraud detection score (0-100)"
    )
    
    is_fraudulent = models.BooleanField(
        default=False,
        help_text="Whether this record is flagged as fraudulent"
    )
    
    fraud_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="List of fraud indicators"
    )
    
    fraud_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fraud review timestamp"
    )
    
    fraud_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_fraud_reviews',
        help_text="User who reviewed the fraud flag"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['fraud_score', 'is_fraudulent']),
            models.Index(fields=['fraud_reviewed_at']),
        ]
    
    def update_fraud_score(self, score: float, indicators: List[str] = None):
        """Update fraud score and indicators"""
        self.fraud_score = min(score, 100.0)
        self.is_fraudulent = self.fraud_score >= FRAUD_SCORE_THRESHOLD
        
        if indicators:
            self.fraud_indicators = list(set(self.fraud_indicators + indicators))
        
        self.save(update_fields=['fraud_score', 'is_fraudulent', 'fraud_indicators'])
    
    def mark_as_reviewed(self, reviewed_by: User, is_fraudulent: bool = None):
        """Mark record as reviewed for fraud"""
        self.fraud_reviewed_at = timezone.now()
        self.fraud_reviewed_by = reviewed_by
        
        if is_fraudulent is not None:
            self.is_fraudulent = is_fraudulent
        
        self.save(update_fields=['fraud_reviewed_at', 'fraud_reviewed_by', 'is_fraudulent'])


class TrackingModel(models.Model):
    """
    Abstract base model with tracking capabilities
    """
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    
    referrer_url = models.URLField(
        blank=True,
        help_text="Referrer URL"
    )
    
    session_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Session identifier"
    )
    
    location_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Geographic location data"
    )
    
    device_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Device information"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['session_id']),
        ]


class StatusModel(models.Model):
    """
    Abstract base model with status tracking
    """
    
    status = models.CharField(
        max_length=50,
        default='active',
        db_index=True,
        help_text="Status of the record"
    )
    
    status_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last status change timestamp"
    )
    
    status_changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_status_changes',
        help_text="User who changed the status"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['status', 'status_changed_at']),
        ]
    
    def change_status(self, new_status: str, changed_by: User = None):
        """Change status with tracking"""
        old_status = self.status
        self.status = new_status
        self.status_changed_at = timezone.now()
        self.status_changed_by = changed_by
        self.save(update_fields=['status', 'status_changed_at', 'status_changed_by'])
        
        logger.info(
            f"Status changed for {self.__class__.__name__} {self.id}: "
            f"{old_status} -> {new_status}"
        )


class VersionedModel(models.Model):
    """
    Abstract base model with version tracking
    """
    
    version = models.PositiveIntegerField(
        default=1,
        help_text="Version number"
    )
    
    version_notes = models.TextField(
        blank=True,
        help_text="Version change notes"
    )
    
    version_created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Version creation timestamp"
    )
    
    version_created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_versions',
        help_text="User who created this version"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['version', 'version_created_at']),
        ]
    
    def create_new_version(self, notes: str = None, created_by: User = None):
        """Create a new version"""
        self.version += 1
        self.version_notes = notes or f"Version {self.version}"
        self.version_created_at = timezone.now()
        self.version_created_by = created_by
        self.save(update_fields=['version', 'version_notes', 'version_created_at', 'version_created_by'])


class AuditableModel(models.Model):
    """
    Abstract base model with audit trail
    """
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        help_text="User who created this record"
    )
    
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified',
        help_text="User who last modified this record"
    )
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['modified_by', 'updated_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Override save to track modifier"""
        from django.contrib.auth import get_user_model
        
        # Get current user from thread local
        current_user = getattr(self, '_current_user', None)
        if current_user and current_user.is_authenticated:
            if not self.pk:  # Creating
                self.created_by = current_user
            self.modified_by = current_user
        
        super().save(*args, **kwargs)


class CacheableModel(models.Model):
    """
    Abstract base model with caching capabilities
    """
    
    cache_timeout = 300  # 5 minutes default
    
    class Meta:
        abstract = True
    
    def get_cache_key(self, suffix: str = '') -> str:
        """Generate cache key for this instance"""
        class_name = self.__class__.__name__.lower()
        return f"{class_name}_{self.id}_{self.tenant_id}_{suffix}"
    
    def cache_data(self, data: Any, suffix: str = '', timeout: int = None):
        """Cache data for this instance"""
        cache_key = self.get_cache_key(suffix)
        timeout = timeout or self.cache_timeout
        cache.set(cache_key, data, timeout)
    
    def get_cached_data(self, suffix: str = '') -> Any:
        """Get cached data for this instance"""
        cache_key = self.get_cache_key(suffix)
        return cache.get(cache_key)
    
    def clear_cache(self, suffixes: List[str] = None):
        """Clear cached data for this instance"""
        if suffixes:
            for suffix in suffixes:
                cache_key = self.get_cache_key(suffix)
                cache.delete(cache_key)
        else:
            # Clear all cache keys for this instance
            cache_key_pattern = self.get_cache_key('*')
            # This would use your cache backend's pattern matching
            cache.delete(cache_key_pattern)


class AbstractOfferProcessor(ABC):
    """
    Abstract base class for offer processors
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def process_offer(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process offer data"""
        pass
    
    @abstractmethod
    def validate_offer(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate offer data"""
        pass
    
    @abstractmethod
    def transform_offer(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform offer data to standard format"""
        pass


class AbstractFraudDetector(ABC):
    """
    Abstract base class for fraud detectors
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data for fraud"""
        pass
    
    @abstractmethod
    def calculate_score(self, indicators: List[str]) -> float:
        """Calculate fraud score from indicators"""
        pass
    
    @abstractmethod
    def get_risk_level(self, score: float) -> str:
        """Get risk level from score"""
        pass


class AbstractRewardCalculator(ABC):
    """
    Abstract base class for reward calculators
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def calculate_base_reward(self, offer_data: Dict[str, Any]) -> Decimal:
        """Calculate base reward amount"""
        pass
    
    @abstractmethod
    def apply_multipliers(self, base_amount: Decimal, 
                         user_data: Dict[str, Any]) -> Decimal:
        """Apply user-specific multipliers"""
        pass
    
    @abstractmethod
    def apply_bonuses(self, amount: Decimal, 
                     context: Dict[str, Any]) -> Decimal:
        """Apply bonus amounts"""
        pass


class AbstractNetworkClient(ABC):
    """
    Abstract base class for network clients
    """
    
    def __init__(self, network_config: Dict[str, Any], tenant_id: str = None):
        self.config = network_config
        self.tenant_id = tenant_id or 'default'
        self.is_authenticated = False
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with network"""
        pass
    
    @abstractmethod
    def get_offers(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get offers from network"""
        pass
    
    @abstractmethod
    def get_offer_details(self, offer_id: str) -> Dict[str, Any]:
        """Get specific offer details"""
        pass
    
    @abstractmethod
    def post_conversion(self, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post conversion to network"""
        pass
    
    @abstractmethod
    def get_statistics(self, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Get network statistics"""
        pass


class AbstractNotificationSender(ABC):
    """
    Abstract base class for notification senders
    """
    
    def __init__(self, config: Dict[str, Any], tenant_id: str = None):
        self.config = config
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def send_notification(self, recipient: Union[str, User], 
                        message: str, data: Dict[str, Any] = None) -> bool:
        """Send notification"""
        pass
    
    @abstractmethod
    def send_bulk_notification(self, recipients: List[Union[str, User]], 
                             message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send bulk notification"""
        pass
    
    @abstractmethod
    def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """Get message delivery status"""
        pass


class AbstractAnalyticsProcessor(ABC):
    """
    Abstract base class for analytics processors
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def process_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process analytics event"""
        pass
    
    @abstractmethod
    def generate_report(self, report_type: str, 
                       filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate analytics report"""
        pass
    
    @abstractmethod
    def get_metrics(self, metric_type: str, 
                   time_period: str = '24h') -> Dict[str, Any]:
        """Get specific metrics"""
        pass


class AbstractExportHandler(ABC):
    """
    Abstract base class for export handlers
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def export_data(self, data: List[Dict[str, Any]], 
                   format: str, fields: List[str] = None) -> bytes:
        """Export data to specified format"""
        pass
    
    @abstractmethod
    def get_filename(self, export_type: str, format: str) -> str:
        """Generate filename for export"""
        pass
    
    @abstractmethod
    def validate_export_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate export request"""
        pass


class AbstractWebhookHandler(ABC):
    """
    Abstract base class for webhook handlers
    """
    
    def __init__(self, webhook_config: Dict[str, Any], tenant_id: str = None):
        self.config = webhook_config
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        pass
    
    @abstractmethod
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook"""
        pass
    
    @abstractmethod
    def get_supported_events(self) -> List[str]:
        """Get list of supported webhook events"""
        pass


class AbstractCacheManager(ABC):
    """
    Abstract base class for cache managers
    """
    
    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id or 'default'
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass
    
    @abstractmethod
    def clear_pattern(self, pattern: str) -> int:
        """Clear cache keys matching pattern"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        pass


# Combined abstract models
class BaseAdNetworkModel(TenantModel, TimestampedModel, SoftDeleteModel, 
                         AuditableModel, CacheableModel):
    """
    Combined abstract model for ad networks
    """
    
    class Meta:
        abstract = True


class BaseOfferModel(TenantModel, TimestampedModel, StatusModel, 
                    FraudDetectionModel, CacheableModel):
    """
    Combined abstract model for offers
    """
    
    class Meta:
        abstract = True


class BaseUserActivityModel(TenantModel, TimestampedModel, TrackingModel, 
                           FraudDetectionModel):
    """
    Combined abstract model for user activities
    """
    
    class Meta:
        abstract = True


class BaseTransactionModel(TenantModel, TimestampedModel, StatusModel, 
                          AuditableModel):
    """
    Combined abstract model for transactions
    """
    
    class Meta:
        abstract = True


# Export all abstract classes
__all__ = [
    # Abstract models
    'TenantModel',
    'TimestampedModel',
    'SoftDeleteModel',
    'FraudDetectionModel',
    'TrackingModel',
    'StatusModel',
    'VersionedModel',
    'AuditableModel',
    'CacheableModel',
    
    # Combined abstract models
    'BaseAdNetworkModel',
    'BaseOfferModel',
    'BaseUserActivityModel',
    'BaseTransactionModel',
    
    # Abstract processors
    'AbstractOfferProcessor',
    'AbstractFraudDetector',
    'AbstractRewardCalculator',
    'AbstractNetworkClient',
    'AbstractNotificationSender',
    'AbstractAnalyticsProcessor',
    'AbstractExportHandler',
    'AbstractWebhookHandler',
    'AbstractCacheManager'
]
