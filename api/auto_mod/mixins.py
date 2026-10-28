# =============================================================================
# auto_mod/mixins.py
# =============================================================================

"""
Mixins for auto moderation system.
Provides reusable functionality for models, views, and other components.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

from .exceptions import ModerationError

logger = logging.getLogger(__name__)

User = get_user_model()


class TimestampMixin(models.Model):
    """Mixin for timestamp fields."""
    
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Update timestamp")
    
    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Mixin for soft delete functionality."""
    
    deleted_at = models.DateTimeField(null=True, blank=True, help_text="Deletion timestamp")
    is_deleted = models.BooleanField(default=False, help_text="Is deleted")
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Soft delete the object."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore the soft deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class UUIDMixin(models.Model):
    """Mixin for UUID primary key."""
    
    id = models.UUIDField(primary_key=True, editable=False, help_text="Unique identifier")
    
    class Meta:
        abstract = True


class TenantMixin(models.Model):
    """Mixin for multi-tenant support."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        help_text="Tenant identifier"
    )
    
    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """Mixin for metadata field."""
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata"
    )
    
    class Meta:
        abstract = True


class AuditMixin(models.Model):
    """Mixin for audit trail."""
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        help_text="Created by"
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        help_text="Updated by"
    )
    
    class Meta:
        abstract = True


class VersionMixin(models.Model):
    """Mixin for version tracking."""
    
    version = models.PositiveIntegerField(default=1, help_text="Version number")
    version_notes = models.TextField(blank=True, help_text="Version notes")
    
    class Meta:
        abstract = True
    
    def increment_version(self, notes: str = ""):
        """Increment version number."""
        self.version += 1
        self.version_notes = notes
        self.save()


class CacheMixin:
    """Mixin for caching functionality."""
    
    cache_timeout = 300  # 5 minutes
    cache_prefix = ""
    
    def get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key."""
        parts = [self.cache_prefix]
        parts.extend(str(arg) for arg in args)
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    def get_from_cache(self, key: str) -> Any:
        """Get value from cache."""
        try:
            return cache.get(key)
        except Exception as exc:
            logger.error(f"Get from cache failed: {exc}")
            return None
    
    def set_cache(self, key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache."""
        try:
            timeout = timeout or self.cache_timeout
            return cache.set(key, value, timeout)
        except Exception as exc:
            logger.error(f"Set cache failed: {exc}")
            return False
    
    def delete_cache(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            return cache.delete(key)
        except Exception as exc:
            logger.error(f"Delete cache failed: {exc}")
            return False


class ValidationMixin:
    """Mixin for validation functionality."""
    
    def validate_required_fields(self, fields: List[str]) -> List[str]:
        """Validate required fields."""
        missing_fields = []
        
        for field in fields:
            if not hasattr(self, field) or getattr(self, field) is None:
                missing_fields.append(field)
        
        return missing_fields
    
    def validate_field_types(self, field_types: Dict[str, type]) -> List[str]:
        """Validate field types."""
        invalid_fields = []
        
        for field, expected_type in field_types.items():
            if hasattr(self, field):
                value = getattr(self, field)
                if value is not None and not isinstance(value, expected_type):
                    invalid_fields.append(field)
        
        return invalid_fields
    
    def validate_field_values(self, field_values: Dict[str, Any]) -> List[str]:
        """Validate field values."""
        invalid_fields = []
        
        for field, validator in field_values.items():
            if hasattr(self, field):
                value = getattr(self, field)
                if value is not None and not validator(value):
                    invalid_fields.append(field)
        
        return invalid_fields


class SerializationMixin:
    """Mixin for serialization functionality."""
    
    def to_dict(self, exclude_fields: List[str] = None) -> Dict[str, Any]:
        """Convert object to dictionary."""
        exclude_fields = exclude_fields or []
        result = {}
        
        for field in self._meta.fields:
            if field.name not in exclude_fields:
                value = getattr(self, field.name)
                
                # Handle different field types
                if isinstance(field, models.DateTimeField):
                    result[field.name] = value.isoformat() if value else None
                elif isinstance(field, models.ForeignKey):
                    result[field.name] = str(value.pk) if value else None
                elif isinstance(field, models.JSONField):
                    result[field.name] = value or {}
                else:
                    result[field.name] = value
        
        return result
    
    def to_json(self, exclude_fields: List[str] = None) -> str:
        """Convert object to JSON."""
        import json
        return json.dumps(self.to_dict(exclude_fields), default=str)


class QuerySetMixin:
    """Mixin for QuerySet functionality."""
    
    def active(self):
        """Get active objects."""
        return self.filter(is_deleted=False)
    
    def deleted(self):
        """Get deleted objects."""
        return self.filter(is_deleted=True)
    
    def recent(self, days: int = 7):
        """Get recent objects."""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)
    
    def by_user(self, user_id: Union[str, int]):
        """Get objects by user."""
        return self.filter(user_id=user_id)
    
    def by_tenant(self, tenant_id: Union[str, int]):
        """Get objects by tenant."""
        return self.filter(tenant_id=tenant_id)


class ManagerMixin:
    """Mixin for Model Manager functionality."""
    
    def get_queryset(self):
        """Get custom queryset."""
        queryset = super().get_queryset()
        if hasattr(self.model, 'is_deleted'):
            return queryset.filter(is_deleted=False)
        return queryset
    
    def active(self):
        """Get active objects."""
        return self.get_queryset().filter(is_deleted=False)
    
    def deleted(self):
        """Get deleted objects."""
        return self.get_queryset().filter(is_deleted=True)


class ViewMixin:
    """Mixin for View functionality."""
    
    def get_user_from_request(self, request):
        """Get user from request."""
        return getattr(request, 'user', None)
    
    def get_tenant_from_request(self, request):
        """Get tenant from request."""
        return getattr(request, 'tenant', None)
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def log_request(self, request, action: str = "request"):
        """Log request information."""
        try:
            log_data = {
                'action': action,
                'method': request.method,
                'path': request.path,
                'user_id': str(self.get_user_from_request(request).id) if self.get_user_from_request(request) else None,
                'ip_address': self.get_client_ip(request),
                'timestamp': timezone.now().isoformat(),
            }
            logger.info(f"Request log: {log_data}")
        except Exception as exc:
            logger.error(f"Log request failed: {exc}")


class SerializerMixin:
    """Mixin for Serializer functionality."""
    
    def get_user_from_context(self, context):
        """Get user from serializer context."""
        return context.get('request', {}).get('user')
    
    def get_tenant_from_context(self, context):
        """Get tenant from serializer context."""
        return context.get('request', {}).get('tenant')
    
    def validate_user_permissions(self, user, permissions: List[str]):
        """Validate user permissions."""
        if not user or not user.is_authenticated:
            raise ModerationError("Authentication required")
        
        for permission in permissions:
            if not user.has_perm(permission):
                raise ModerationError(f"Permission denied: {permission}")
    
    def enrich_data_with_context(self, data, context):
        """Enrich data with context information."""
        user = self.get_user_from_context(context)
        tenant = self.get_tenant_from_context(context)
        
        enriched_data = data.copy()
        
        if user:
            enriched_data['created_by'] = user.id
        
        if tenant:
            enriched_data['tenant'] = tenant.id
        
        return enriched_data


class TaskMixin:
    """Mixin for Task functionality."""
    
    def get_task_config(self, task_name: str) -> Dict[str, Any]:
        """Get task configuration."""
        return getattr(settings, f'AUTO_MOD_TASK_{task_name.upper()}', {})
    
    def log_task_start(self, task_name: str, task_id: str, **kwargs):
        """Log task start."""
        logger.info(f"Task {task_name} ({task_id}) started with args: {kwargs}")
    
    def log_task_success(self, task_name: str, task_id: str, result: Any = None):
        """Log task success."""
        logger.info(f"Task {task_name} ({task_id}) completed successfully")
        if result:
            logger.debug(f"Task result: {result}")
    
    def log_task_failure(self, task_name: str, task_id: str, error: Exception):
        """Log task failure."""
        logger.error(f"Task {task_name} ({task_id}) failed: {error}")
    
    def retry_task(self, task_name: str, task_id: str, retry_count: int, max_retries: int) -> bool:
        """Check if task should be retried."""
        return retry_count < max_retries


class APIResponseMixin:
    """Mixin for API response functionality."""
    
    def success_response(self, data: Any = None, message: str = "Success", 
                       status_code: int = 200) -> Dict[str, Any]:
        """Create success response."""
        return {
            'success': True,
            'message': message,
            'data': data,
            'status_code': status_code,
            'timestamp': timezone.now().isoformat(),
        }
    
    def error_response(self, message: str, errors: List[str] = None, 
                      status_code: int = 400) -> Dict[str, Any]:
        """Create error response."""
        return {
            'success': False,
            'message': message,
            'errors': errors or [],
            'status_code': status_code,
            'timestamp': timezone.now().isoformat(),
        }
    
    def paginated_response(self, data: List[Any], page: int, page_size: int, 
                          total_count: int) -> Dict[str, Any]:
        """Create paginated response."""
        total_pages = (total_count + page_size - 1) // page_size
        
        return {
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_previous': page > 1,
            },
            'timestamp': timezone.now().isoformat(),
        }


class PermissionMixin:
    """Mixin for permission functionality."""
    
    def has_permission(self, user, permission: str) -> bool:
        """Check if user has permission."""
        if not user or not user.is_authenticated:
            return False
        return user.has_perm(permission)
    
    def has_any_permission(self, user, permissions: List[str]) -> bool:
        """Check if user has any of the permissions."""
        if not user or not user.is_authenticated:
            return False
        return any(user.has_perm(perm) for perm in permissions)
    
    def has_all_permissions(self, user, permissions: List[str]) -> bool:
        """Check if user has all permissions."""
        if not user or not user.is_authenticated:
            return False
        return all(user.has_perm(perm) for perm in permissions)
    
    def is_staff_or_admin(self, user) -> bool:
        """Check if user is staff or admin."""
        return user.is_authenticated and (user.is_staff or user.is_superuser)


class CacheKeyMixin:
    """Mixin for cache key generation."""
    
    def generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key."""
        import hashlib
        
        parts = [prefix]
        parts.extend(str(arg) for arg in args)
        
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}:{value}")
        
        key_string = "|".join(parts)
        hash_value = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{prefix}:{hash_value}"
    
    def get_user_cache_key(self, user_id: Union[str, int], suffix: str = "") -> str:
        """Get user-specific cache key."""
        return self.generate_cache_key(f"user_{user_id}", suffix)
    
    def get_tenant_cache_key(self, tenant_id: Union[str, int], suffix: str = "") -> str:
        """Get tenant-specific cache key."""
        return self.generate_cache_key(f"tenant_{tenant_id}", suffix)


class RateLimitMixin:
    """Mixin for rate limiting functionality."""
    
    def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """
        Check rate limit.
        
        Args:
            key: Rate limit key
            limit: Request limit
            window: Time window in seconds
            
        Returns:
            True if rate limit is not exceeded
        """
        try:
            current_count = cache.get(key, 0)
            
            if current_count >= limit:
                return False
            
            # Increment counter
            cache.set(key, current_count + 1, timeout=window)
            return True
            
        except Exception as exc:
            logger.error(f"Rate limit check failed: {exc}")
            return True  # Fail open
    
    def get_rate_limit_headers(self, key: str, limit: int, window: int) -> Dict[str, str]:
        """Get rate limit headers."""
        try:
            current_count = cache.get(key, 0)
            remaining = max(0, limit - current_count)
            reset_time = cache.ttl(key) or window
            
            return {
                'X-RateLimit-Limit': str(limit),
                'X-RateLimit-Remaining': str(remaining),
                'X-RateLimit-Reset': str(reset_time),
            }
        except Exception as exc:
            logger.error(f"Get rate limit headers failed: {exc}")
            return {}


# Initialize logging
logger.info("Mixins module initialized with reusable functionality")
