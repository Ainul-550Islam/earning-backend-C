"""
Gamification Mixins — Django mixins for gamification module.

This module provides reusable Django mixins for gamification functionality,
including model mixins, view mixins, and utility mixins.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Union

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.gamification.exceptions import GamificationServiceError
from api.gamification.models import (
    UserAchievement, UserBadge, Streak, LevelConfig
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model Mixins
# ---------------------------------------------------------------------------

class TimestampMixin(models.Model):
    """Mixin to add timestamp fields to models."""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class UUIDMixin(models.Model):
    """Mixin to add UUID primary key to models."""
    
    id = models.UUIDField(primary_key=True, editable=False)
    
    class Meta:
        abstract = True


class TenantMixin(models.Model):
    """Mixin to add tenant support to models."""
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )
    
    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """Mixin to add metadata JSON field to models."""
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        abstract = True


class ChecksumMixin(models.Model):
    """Mixin to add checksum field for data integrity."""
    
    checksum = models.CharField(max_length=64, blank=True)
    
    class Meta:
        abstract = True
    
    def calculate_checksum(self) -> str:
        """Calculate checksum for the model instance."""
        import hashlib
        
        # Get all field values except checksum itself
        fields = []
        for field in self._meta.fields:
            if field.name != 'checksum':
                value = getattr(self, field.name)
                if value is not None:
                    fields.append(str(value))
        
        # Create checksum
        checksum_data = '|'.join(fields)
        return hashlib.sha256(checksum_data.encode()).hexdigest()
    
    def save(self, *args, **kwargs) -> None:
        """Save with checksum calculation."""
        self.checksum = self.calculate_checksum()
        super().save(*args, **kwargs)


class GamificationUserMixin(models.Model):
    """Mixin to add gamification user relationship."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )
    
    class Meta:
        abstract = True


class PointsMixin(models.Model):
    """Mixin to add points field and validation."""
    
    points = models.IntegerField(default=0)
    
    class Meta:
        abstract = True
    
    def clean(self) -> None:
        """Validate points field."""
        if self.points < 0:
            from django.core.exceptions import ValidationError
            raise ValidationError("Points cannot be negative")


# ---------------------------------------------------------------------------
# View Mixins
# ---------------------------------------------------------------------------

class GamificationContextMixin:
    """Mixin to add gamification context to views."""
    
    def get_gamification_context(self) -> Dict[str, Any]:
        """Get gamification context for templates."""
        if not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
            return {}
        
        try:
            user = self.request.user
            
            # Get user's gamification stats
            total_points = UserAchievement.objects.filter(
                user=user, is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
            
            # Get user's current level
            level = LevelConfig.get_level_for_points(total_points)
            current_level = level.level_number if level else 1
            
            # Get user's badges count
            badges_count = UserBadge.objects.filter(user=user).count()
            
            # Get user's achievements count
            achievements_count = UserAchievement.objects.filter(
                user=user, is_awarded=True
            ).count()
            
            # Get user's streak
            streak = Streak.objects.filter(user=user).first()
            streak_days = streak.current_days if streak else 0
            streak_active = streak.is_active if streak else False
            
            return {
                'total_points': total_points,
                'current_level': current_level,
                'badges_count': badges_count,
                'achievements_count': achievements_count,
                'streak_days': streak_days,
                'streak_active': streak_active,
            }
            
        except Exception as e:
            logger.error(f"Error getting gamification context: {e}")
            return {}


class CacheMixin:
    """Mixin to add caching functionality to views."""
    
    cache_timeout = 300  # 5 minutes
    cache_key_prefix = "gamification"
    
    def get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key."""
        key_parts = [self.cache_key_prefix]
        
        # Add view name
        if hasattr(self, '__class__'):
            key_parts.append(self.__class__.__name__)
        
        # Add user ID if available
        if hasattr(self, 'request') and hasattr(self.request, 'user'):
            if self.request.user.is_authenticated:
                key_parts.append(str(self.request.user.id))
        
        # Add arguments
        key_parts.extend(str(arg) for arg in args)
        
        # Add keyword arguments
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        return ':'.join(key_parts)
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """Get data from cache."""
        return cache.get(key)
    
    def set_cached_data(self, key: str, data: Any, timeout: Optional[int] = None) -> None:
        """Set data in cache."""
        cache.set(key, data, timeout or self.cache_timeout)
    
    def invalidate_cache(self, key: str) -> None:
        """Invalidate cache entry."""
        cache.delete(key)


class UserFilterMixin:
    """Mixin to filter data by current user."""
    
    def get_queryset(self):
        """Filter queryset by current user if not staff."""
        queryset = super().get_queryset()
        
        if hasattr(self, 'request') and hasattr(self.request, 'user'):
            if not self.request.user.is_staff:
                queryset = queryset.filter(user=self.request.user)
        
        return queryset


class PermissionMixin:
    """Mixin to check custom permissions."""
    
    required_permissions = []
    
    def check_permissions(self) -> bool:
        """Check if user has required permissions."""
        if not hasattr(self, 'request') or not hasattr(self.request, 'user'):
            return False
        
        user = self.request.user
        
        if not user.is_authenticated:
            return False
        
        # Staff users have all permissions
        if user.is_staff:
            return True
        
        # Check required permissions
        for permission in self.required_permissions:
            if not user.has_perm(permission):
                return False
        
        return True
    
    def dispatch(self, request, *args, **kwargs):
        """Dispatch with permission check."""
        if not self.check_permissions():
            return JsonResponse(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Utility Mixins
# ---------------------------------------------------------------------------

class LoggingMixin:
    """Mixin to add logging functionality."""
    
    def log_action(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an action."""
        logger.info(f"Action: {action} - Details: {details or {}}")
    
    def log_error(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an error."""
        logger.error(f"Error: {error} - Details: {details or {}}")
    
    def log_warning(self, warning: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning."""
        logger.warning(f"Warning: {warning} - Details: {details or {}}")


class ValidationMixin:
    """Mixin to add validation functionality."""
    
    def validate_data(self, data: Dict[str, Any], rules: Dict[str, Any]) -> List[str]:
        """Validate data against rules."""
        errors = []
        
        for field, rule in rules.items():
            value = data.get(field)
            
            # Required field validation
            if rule.get('required', False) and value is None:
                errors.append(f"{field} is required")
                continue
            
            if value is None:
                continue
            
            # Type validation
            expected_type = rule.get('type')
            if expected_type and not isinstance(value, expected_type):
                errors.append(f"{field} must be of type {expected_type.__name__}")
                continue
            
            # Length validation
            min_length = rule.get('min_length')
            max_length = rule.get('max_length')
            if isinstance(value, (str, list)):
                if min_length and len(value) < min_length:
                    errors.append(f"{field} must be at least {min_length} characters/items")
                if max_length and len(value) > max_length:
                    errors.append(f"{field} cannot exceed {max_length} characters/items")
            
            # Range validation
            min_value = rule.get('min_value')
            max_value = rule.get('max_value')
            if isinstance(value, (int, float)):
                if min_value is not None and value < min_value:
                    errors.append(f"{field} must be at least {min_value}")
                if max_value is not None and value > max_value:
                    errors.append(f"{field} cannot exceed {max_value}")
        
        return errors


class ResponseMixin:
    """Mixin to standardize API responses."""
    
    def success_response(self, data: Any = None, message: str = None) -> Response:
        """Create success response."""
        response_data = {
            'success': True,
            'data': data,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    def error_response(self, message: str, errors: List[str] = None, 
                      status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Create error response."""
        response_data = {
            'success': False,
            'error': message,
            'errors': errors or [],
            'timestamp': timezone.now().isoformat()
        }
        return Response(response_data, status=status_code)
    
    def validation_error_response(self, errors: List[str]) -> Response:
        """Create validation error response."""
        return self.error_response(
            "Validation failed",
            errors,
            status.HTTP_400_BAD_REQUEST
        )


# ---------------------------------------------------------------------------
# API View Mixins
# ---------------------------------------------------------------------------

class GamificationAPIViewMixin(APIView, ResponseMixin, LoggingMixin):
    """Mixin for gamification API views."""
    
    def handle_exception(self, exc):
        """Handle exceptions consistently."""
        if isinstance(exc, GamificationServiceError):
            return self.error_response(str(exc))
        
        logger.exception("Unexpected error in API view")
        return self.error_response(
            "Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class GamificationListModelMixin:
    """Mixin for list views with pagination and filtering."""
    
    pagination_class = None
    filter_backends = []
    
    def get_paginated_response(self, data):
        """Get paginated response."""
        if self.pagination_class:
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(self.get_queryset())
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(data, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Combined Mixins
# ---------------------------------------------------------------------------

class GamificationModelMixin(UUIDMixin, TimestampMixin, MetadataMixin, ChecksumMixin):
    """Combined mixin for gamification models."""
    
    class Meta:
        abstract = True


class GamificationUserModelMixin(GamificationModelMixin, GamificationUserMixin):
    """Combined mixin for user-related gamification models."""
    
    class Meta:
        abstract = True


class GamificationPointsModelMixin(GamificationUserModelMixin, PointsMixin):
    """Combined mixin for points-related gamification models."""
    
    class Meta:
        abstract = True


class GamificationViewMixin(GamificationContextMixin, CacheMixin, UserFilterMixin, 
                           PermissionMixin, LoggingMixin, ValidationMixin, ResponseMixin):
    """Combined mixin for gamification views."""
    
    class Meta:
        abstract = True


class GamificationAPIView(GamificationContextMixin, CacheMixin, UserFilterMixin,
                          PermissionMixin, ValidationMixin,
                          GamificationAPIViewMixin):
    """Combined API view with all gamification mixins."""

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def apply_mixins(base_class: Type, *mixins: Type) -> Type:
    """Apply mixins to a base class."""
    for mixin in mixins:
        base_class = type(base_class.__name__, (mixin, base_class), {})
    return base_class


def create_gamification_model(*mixins: Type) -> Type:
    """Create a gamification model with specified mixins."""
    base_mixins = [GamificationModelMixin]
    all_mixins = base_mixins + list(mixins)
    
    class NewModel(models.Model, *all_mixins):
        class Meta:
            abstract = True
    
    return NewModel


def create_gamification_view(*mixins: Type) -> Type:
    """Create a gamification view with specified mixins."""
    base_mixins = [GamificationViewMixin]
    all_mixins = base_mixins + list(mixins)
    
    class NewView(APIView, *all_mixins):
        pass
    
    return NewView


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------

class ExampleGamificationModel(GamificationUserModelMixin):
    """Example model using gamification mixins."""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    class Meta:
        abstract = True  # Set to False in actual implementation


class ExampleGamificationView(GamificationAPIView):
    """Example view using gamification mixins."""
    
    required_permissions = ['gamification.view_example']
    
    def get(self, request, *args, **kwargs):
        """Example GET method."""
        self.log_action("Example view accessed")
        
        # Get cached data
        cache_key = self.get_cache_key("example")
        cached_data = self.get_cached_data(cache_key)
        
        if cached_data:
            return self.success_response(cached_data)
        
        # Process data
        data = {"message": "Hello from gamification view"}
        
        # Cache the result
        self.set_cached_data(cache_key, data)
        
        return self.success_response(data)


# Initialize logging
logger.info("Gamification mixins module initialized")
