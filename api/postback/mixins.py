"""
mixins.py – Reusable mixins for postback module.

Provides comprehensive mixins for Django models, views,
and other components to extend functionality.
"""
from rest_framework import serializers
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class TimestampMixin(models.Model):
    """
    Mixin that adds timestamp fields to models.
    
    Provides created_at and updated_at fields with automatic
    timestamp management.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        abstract = True


class UUIDMixin(models.Model):
    """
    Mixin that adds UUID primary key to models.
    
    Provides UUID primary key with automatic generation
    for global uniqueness.
    """
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    class Meta:
        abstract = True


class TenantMixin(models.Model):
    """
    Mixin that adds tenant support to models.
    
    Provides tenant field for multi-tenancy support
    with automatic tenant filtering.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(class)s_set"
    )
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """
    Mixin that adds soft delete functionality to models.
    
    Provides deleted_at field and methods for soft deletion
    with automatic filtering of deleted records.
    """
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Soft delete the record."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore the soft deleted record."""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class IntegrityHashMixin(models.Model):
    """
    Mixin that adds integrity hash functionality to models.
    
    Provides integrity_hash field and methods for generating
    and verifying SHA-256 integrity hashes.
    """
    integrity_hash = models.CharField(max_length=64, db_index=True, blank=True)
    
    class Meta:
        abstract = True
    
    def generate_integrity_hash(self) -> str:
        """Generate SHA-256 integrity hash for the model instance."""
        import hashlib
        
        # Get relevant fields for hashing
        hash_fields = self._get_hash_fields()
        
        # Create hash string
        hash_parts = []
        for field in hash_fields:
            value = getattr(self, field)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, 'id'):
                value = str(value.id)
            hash_parts.append(f"{field}:{value}")
        
        hash_string = "|".join(hash_parts)
        
        # Generate SHA-256 hash
        hash_object = hashlib.sha256(hash_string.encode())
        return hash_object.hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify the integrity hash."""
        current_hash = self.generate_integrity_hash()
        return current_hash == self.integrity_hash
    
    def update_integrity_hash(self):
        """Update the integrity hash."""
        self.integrity_hash = self.generate_integrity_hash()
        self.save(update_fields=['integrity_hash'])
    
    def _get_hash_fields(self) -> List[str]:
        """Get list of fields to include in integrity hash."""
        # Override in subclasses to specify which fields to hash
        return [field.name for field in self._meta.fields if field.name != 'integrity_hash']


class CacheMixin:
    """
    Mixin that adds caching functionality to models.
    
    Provides methods for caching model instances and
    cache invalidation.
    """
    
    CACHE_TIMEOUT = 3600  # 1 hour default
    
    @classmethod
    def get_cached(cls, pk: Any, timeout: int = None) -> Optional['CacheMixin']:
        """Get cached model instance."""
        timeout = timeout or cls.CACHE_TIMEOUT
        cache_key = f"{cls.__name__.lower()}_{pk}"
        
        instance = cache.get(cache_key)
        if instance is None:
            try:
                instance = cls.objects.get(pk=pk)
                cache.set(cache_key, instance, timeout)
            except cls.DoesNotExist:
                return None
        
        return instance
    
    def cache_instance(self, timeout: int = None):
        """Cache the model instance."""
        timeout = timeout or self.CACHE_TIMEOUT
        cache_key = f"{self.__class__.__name__.lower()}_{self.pk}"
        cache.set(cache_key, self, timeout)
    
    def invalidate_cache(self):
        """Invalidate cached model instance."""
        cache_key = f"{self.__class__.__name__.lower()}_{self.pk}"
        cache.delete(cache_key)
    
    @classmethod
    def invalidate_cache_for_pk(cls, pk: Any):
        """Invalidate cache for specific primary key."""
        cache_key = f"{cls.__name__.lower()}_{pk}"
        cache.delete(cache_key)


class AuditMixin(models.Model):
    """
    Mixin that adds audit fields to models.
    
    Provides created_by, updated_by, and version fields
    for audit trail functionality.
    """
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated"
    )
    version = models.PositiveIntegerField(default=1)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to handle audit fields."""
        # Increment version
        if self.pk:  # Existing record
            self.version += 1
        
        # Set updated_by if not provided
        if 'updated_by' not in kwargs and hasattr(self, '_updated_by_user'):
            self.updated_by = self._updated_by_user
        
        super().save(*args, **kwargs)
    
    def set_created_by(self, user: User):
        """Set the created_by user."""
        self.created_by = user
        self._updated_by_user = user


class MetadataMixin(models.Model):
    """
    Mixin that adds metadata field to models.
    
    Provides JSON metadata field for storing additional
    flexible data.
    """
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key."""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self.metadata[key] = value
        self.save(update_fields=['metadata'])
    
    def update_metadata(self, updates: Dict[str, Any]):
        """Update multiple metadata values."""
        self.metadata.update(updates)
        self.save(update_fields=['metadata'])
    
    def delete_metadata(self, key: str):
        """Delete metadata value."""
        if key in self.metadata:
            del self.metadata[key]
            self.save(update_fields=['metadata'])


class StatusMixin(models.Model):
    """
    Mixin that adds status field to models.
    
    Provides status field with status management methods.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('archived', 'Archived'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )
    
    class Meta:
        abstract = True
    
    def is_active(self) -> bool:
        """Check if status is active."""
        return self.status == 'active'
    
    def is_inactive(self) -> bool:
        """Check if status is inactive."""
        return self.status == 'inactive'
    
    def is_pending(self) -> bool:
        """Check if status is pending."""
        return self.status == 'pending'
    
    def is_archived(self) -> bool:
        """Check if status is archived."""
        return self.status == 'archived'
    
    def activate(self):
        """Set status to active."""
        self.status = 'active'
        self.save(update_fields=['status'])
    
    def deactivate(self):
        """Set status to inactive."""
        self.status = 'inactive'
        self.save(update_fields=['status'])
    
    def archive(self):
        """Set status to archived."""
        self.status = 'archived'
        self.save(update_fields=['status'])


class ViewMixin:
    """
    Mixin that adds common functionality to Django views.
    
    Provides methods for common view operations including
    logging, error handling, and response formatting.
    """
    
    def log_request(self, request, message: str = None):
        """Log request information."""
        logger.info(f"{message or 'Request'}: {request.method} {request.path} from {request.META.get('REMOTE_ADDR')}")
    
    def log_error(self, request, error: Exception, message: str = None):
        """Log error information."""
        logger.error(f"{message or 'Error'}: {str(error)} - {request.method} {request.path}")
    
    def format_response(self, data: Any, status: int = 200, message: str = None) -> Dict[str, Any]:
        """Format response data."""
        response = {
            'status': status,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }
        
        if message:
            response['message'] = message
        
        return response
    
    def format_error_response(self, error: Exception, status: int = 500, message: str = None) -> Dict[str, Any]:
        """Format error response."""
        return self.format_response(
            data={'error': str(error)},
            status=status,
            message=message or 'An error occurred'
        )


class SerializerMixin:
    """
    Mixin that adds common functionality to DRF serializers.
    
    Provides methods for common serializer operations including
    validation enhancement and field manipulation.
    """
    
    def validate_metadata(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata field."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        
        # Add any custom metadata validation here
        return value
    
    def get_field_display_value(self, field_name: str) -> str:
        """Get display value for choice field."""
        if hasattr(self.instance, f'get_{field_name}_display'):
            return getattr(self.instance, f'get_{field_name}_display')()
        return getattr(self.instance, field_name, '')
    
    def enhance_validation_data(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance validated data with additional processing."""
        # Add any custom data enhancement here
        return validated_data


class QuerySetMixin(models.QuerySet):
    """
    Mixin that adds common functionality to model querysets.
    
    Provides methods for common queryset operations including
    filtering, ordering, and aggregation.
    """
    
    def active(self):
        """Filter by active status."""
        return self.filter(status='active')
    
    def inactive(self):
        """Filter by inactive status."""
        return self.filter(status='inactive')
    
    def recent(self, days: int = 7):
        """Filter by recent records."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)
    
    def for_tenant(self, tenant):
        """Filter by tenant."""
        return self.filter(tenant=tenant)
    
    def with_metadata(self, key: str, value: Any = None):
        """Filter by metadata key/value."""
        if value is None:
            return self.filter(metadata__has_key=key)
        return self.filter(**{f"metadata__{key}": value})


class ManagerMixin(models.Manager):
    """
    Mixin that adds common functionality to model managers.
    
    Provides methods for common manager operations including
    caching and bulk operations.
    """
    
    def get_queryset(self):
        """Get custom queryset with mixins."""
        return QuerySetMixin(self.model, using=self._db)
    
    def active(self):
        """Get active records."""
        return self.get_queryset().active()
    
    def inactive(self):
        """Get inactive records."""
        return self.get_queryset().inactive()
    
    def recent(self, days: int = 7):
        """Get recent records."""
        return self.get_queryset().recent(days)
    
    def for_tenant(self, tenant):
        """Get records for tenant."""
        return self.get_queryset().for_tenant(tenant)
    
    def bulk_create_with_cache(self, objs, batch_size=None, ignore_conflicts=False):
        """Bulk create with cache invalidation."""
        result = super().bulk_create(objs, batch_size, ignore_conflicts)
        
        # Invalidate cache for created objects
        for obj in objs:
            if hasattr(obj, 'invalidate_cache'):
                obj.invalidate_cache()
        
        return result


class APIResponseMixin:
    """
    Mixin that adds common API response functionality.
    
    Provides methods for standardizing API responses including
    error handling and pagination.
    """
    
    def success_response(self, data: Any = None, message: str = None) -> Dict[str, Any]:
        """Create success response."""
        return {
            'success': True,
            'data': data,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }
    
    def error_response(self, message: str, code: str = None, details: Any = None) -> Dict[str, Any]:
        """Create error response."""
        return {
            'success': False,
            'error': {
                'message': message,
                'code': code,
                'details': details,
            },
            'timestamp': timezone.now().isoformat(),
        }
    
    def paginated_response(self, data: List[Any], page: int, per_page: int, total: int) -> Dict[str, Any]:
        """Create paginated response."""
        return {
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page,
            },
            'timestamp': timezone.now().isoformat(),
        }


class LoggingMixin:
    """
    Mixin that adds enhanced logging functionality.
    
    Provides methods for structured logging with context
    and performance monitoring.
    """
    
    def log_with_context(self, level: str, message: str, **context):
        """Log message with context."""
        log_data = {
            'message': message,
            'timestamp': timezone.now().isoformat(),
            'component': self.__class__.__name__,
            **context
        }
        
        getattr(logger, level.lower())(f"{message} - {log_data}")
    
    def log_performance(self, operation: str, duration: float, **context):
        """Log performance metrics."""
        self.log_with_context(
            'info',
            f"Performance: {operation}",
            operation=operation,
            duration=duration,
            **context
        )
    
    def log_error_with_context(self, error: Exception, **context):
        """Log error with context."""
        self.log_with_context(
            'error',
            f"Error: {str(error)}",
            error_type=type(error).__name__,
            error_message=str(error),
            **context
        )


# Combined mixins for common use cases
class StandardModelMixin(UUIDMixin, TimestampMixin, IntegrityHashMixin, CacheMixin, MetadataMixin):
    """
    Combined mixin for standard model functionality.
    
    Includes UUID primary key, timestamps, integrity hashing,
    caching, and metadata support.
    """
    
    class Meta:
        abstract = True


class AuditedModelMixin(StandardModelMixin, AuditMixin, StatusMixin):
    """
    Combined mixin for audited model functionality.
    
    Includes all standard model functionality plus audit
    trail and status management.
    """
    
    class Meta:
        abstract = True


class TenantModelMixin(AuditedModelMixin, TenantMixin):
    """
    Combined mixin for tenant-aware model functionality.
    
    Includes all audited model functionality plus tenant
    support for multi-tenancy.
    """
    
    class Meta:
        abstract = True
