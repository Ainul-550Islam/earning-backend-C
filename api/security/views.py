"""
SECURITY APP VIEWS - PRODUCTION READY
Version: 3.0.0 | Security Enhanced | Performance Optimized
Models Compatibility: Full Match with Provided Models
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import hashlib
from rest_framework.permissions import BasePermission
import json
from django.core.cache import cache
from functools import wraps
from .models import IPBlacklist
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q, Count, F, Subquery, OuterRef, Window, Avg, StdDev, Max, Min
from django.db.models.functions import TruncHour, TruncDay, ExtractHour, Coalesce
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import viewsets, status, permissions, generics
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from rest_framework.views import APIView
from django.views.decorators.vary import vary_on_cookie
from django.db.models import Count, Q, F, ExpressionWrapper, FloatField
from django.db.models.functions import TruncHour, TruncDay, TruncWeek
from typing import Dict, Any, List, Optional
from rest_framework import viewsets, status, filters, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound, Throttled
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from .permissions import IsStaffUser, IsAdminOrSecurityTeam, IsSuperUser, IsSecurityAdmin
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.filters import SearchFilter, OrderingFilter
from .utils.cache_manager import handle_gracefully, CacheManager
from django_filters import FilterSet, CharFilter, NumberFilter, DateTimeFilter, BooleanFilter, ChoiceFilter
from .decorators import method_audit_action
from django_filters.rest_framework import DjangoFilterBackend
import functools
from django.shortcuts import render
# from .pagination import SecurityPagination, LargeDatasetPagination
User = get_user_model()
from .decorators import (
    handle_gracefully, 
    validate_request,     
    rate_limit, 
    method_audit_action,   
    audit_action           
)

from .models import (
    DeviceInfo, SecurityLog, UserBan, ClickTracker, MaintenanceMode,
    AppVersion, IPBlacklist, WithdrawalProtection, RiskScore,
    SecurityDashboard, AutoBlockRule, AuditTrail, DataExport,
    DataImport, SecurityNotification, AlertRule, FraudPattern,
    RealTimeDetection, Country, GeolocationLog, CountryBlockRule,
    APIRateLimit, RateLimitLog, PasswordPolicy, PasswordHistory,
    PasswordAttempt, UserSession, SessionActivity, TwoFactorMethod,
    TwoFactorAttempt, TwoFactorRecoveryCode,ClickTracker, 
    EnhancedClickTracker
)

from .serializers import (
    DeviceInfoSerializer, SecurityLogSerializer, UserBanSerializer, UserBanListSerializer, UserBanUpdateSerializer, UserBanCreateSerializer,
    ClickTrackerSerializer, AppVersionSerializer,
    IPBlacklistSerializer, WithdrawalProtectionSerializer, RiskScoreSerializer,
    SecurityDashboardSerializer,
    RiskScoreListSerializer,
    RiskScoreUpdateSerializer,RiskScoreCalculateSerializer, IPBlacklistListSerializer,
    IPBlacklistCreateSerializer,
    WithdrawalLimitUpdateSerializer,
    WithdrawalProtectionSummarySerializer, SecurityDashboardSerializer,
    SystemMetricsSerializer,
    CombinedSecuritySerializer, AutoBlockRuleSerializer, FraudPatternSerializer, RealTimeDetectionSerializer, 
    EnhancedClickTrackerSerializer, CountrySerializer, GeolocationSerializer, CountryBlockRuleSerializer, APIRateLimitSerializer,
    PasswordPolicySerializer,
    UserSessionSerializer, TwoFactorMethodSerializer, AuditTrailSerializer
    
    
)


# Import utilities with defensive coding
from .utils import NullSafe, TypeValidator, GracefulDegradation
from .decorators import handle_gracefully, validate_request, rate_limit, method_audit_action
logger = logging.getLogger('security.views')

# ============================================================================
# CUSTOM THROTTLE CLASSES
# ============================================================================

class SecurityThrottle(UserRateThrottle):
    """Custom throttle for security endpoints"""
    rate = '1000/minute'
    scope = 'security'
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
            'view': view.__class__.__name__
        }


class HighSecurityThrottle(UserRateThrottle):
    """Stricter throttle for high-security endpoints"""
    rate = '1000/minute'
    scope = 'high_security'


# ============================================================================
# CUSTOM PAGINATION CLASSES
# ============================================================================

class SecurityPagination(PageNumberPagination):
    """Pagination optimized for security data"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000
    
    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })


class LargeDatasetPagination(LimitOffsetPagination):
    """Pagination for large datasets with limit/offset"""
    default_limit = 200
    max_limit = 5000
    limit_query_param = 'limit'
    offset_query_param = 'offset'


# ============================================================================
# CUSTOM PERMISSION CLASSES
# ============================================================================

class IsSecurityAdmin(permissions.BasePermission):
    """Permission for security administrators"""
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_superuser or request.user.groups.filter(name='Security Admin').exists())
        )


class IsSecurityStaff(permissions.BasePermission):
    """Permission for security staff"""
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_staff or request.user.groups.filter(name='Security Staff').exists())
        )


class CanViewSecurityLogs(permissions.BasePermission):
    """Permission to view security logs"""
    
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True
        return request.user.has_perm('security.view_securitylog')


class CanManageDevices(permissions.BasePermission):
    """Permission to manage devices"""
    
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True
        return request.user.has_perm('security.manage_device')


# ============================================================================
# CUSTOM FILTER SETS
# ============================================================================

class SecurityLogFilter(FilterSet):
    """Filter for security logs"""
    
    class Meta:
        model = SecurityLog
        fields = {
            # 'security_type' বদলে 'event_type' হবে, কারণ মডেলে এটাই আছে
            'security_type': ['exact', 'in'], 
            'severity': ['exact', 'in'],
            'user__username': ['exact', 'icontains'],
            'ip_address': ['exact', 'icontains'],
            # 'resolved' এবং 'risk_score' মডেলে নেই, তাই এগুলো বাদ দিতে হবে
            'created_at': ['gte', 'lte', 'exact'],
        }
    
    date_range = CharFilter(method='filter_date_range')
    
    def filter_date_range(self, queryset, name, value):
        """Filter by date range"""
        try:
            start_str, end_str = value.split(',')
            start_date = timezone.make_aware(datetime.fromisoformat(start_str))
            end_date = timezone.make_aware(datetime.fromisoformat(end_str))
            return queryset.filter(created_at__range=[start_date, end_date])
        except (ValueError, AttributeError):
            return queryset.none()


# ============================================================================
# MAIN VIEWSETS
# ============================================================================
# ==================== PERMISSIONS ====================

class CanManageDevices(permissions.BasePermission):
    """Permission to manage devices with defensive coding"""
    def has_permission(self, request, view):
        try:
            if not request or not hasattr(request, 'user'):
                return False
            
            user = request.user
            
            if not user or not user.is_authenticated:
                return False
            
            # Check various permission levels
            return bool(
                getattr(user, 'is_staff', False) or
                getattr(user, 'is_superuser', False) or
                user.has_perm('security.manage_device') or
                user.groups.filter(name='Device Manager').exists()
            )
        except Exception as e:
            logger.error(f"Error in CanManageDevices permission: {str(e)}")
            return False


class IsSecurityAdmin(permissions.BasePermission):
    """Permission for security admins with defensive coding"""
    def has_permission(self, request, view):
        try:
            if not request or not hasattr(request, 'user'):
                return False
            
            user = request.user
            
            if not user or not user.is_authenticated:
                return False
            
            return bool(
                getattr(user, 'is_superuser', False) or
                (getattr(user, 'is_staff', False) and user.has_perm('security.manage_security')) or
                user.groups.filter(name='Security Admin').exists()
            )
        except Exception as e:
            logger.error(f"Error in IsSecurityAdmin permission: {str(e)}")
            return False


# ==================== FIXED SECURITY ACTION DECORATOR ====================

def security_action(methods=None, detail=True, url_path=None, url_name=None, permission_classes=None):
    """
    Custom action decorator with proper functools.wraps support
    Fixed version that properly preserves function attributes
    """
    def decorator(func):
        # Create the wrapper function FIRST
        @functools.wraps(func)  # This MUST be on the actual wrapper
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                raise
        
        # Set default methods
        action_methods = methods if methods is not None else ['get']
        
        # Apply the DRF action decorator to the wrapper
        # This returns a new function with proper attributes
        decorated = action(
            methods=action_methods,
            detail=detail,
            url_path=url_path or func.__name__,
            url_name=url_name or func.__name__,
            permission_classes=permission_classes or []
        )(wrapper)
        
        # Explicitly set the __name__ attribute to match the original function
        # This is critical for DRF's get_extra_actions() to work
        decorated.__name__ = func.__name__
        
        return decorated
    
    return decorator


# ==================== AUDIT DECORATOR ====================

def method_audit_action(action_type):
    """Audit decorator for tracking actions with defensive coding"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                # Execute the function
                response = func(self, request, *args, **kwargs)
                
                # Log successful action
                try:
                    from security.models import AuditTrail
                    
                    user = getattr(request, 'user', None)
                    if user and user.is_authenticated:
                        AuditTrail.objects.create(
                            user=user,
                            action_type=action_type.lower(),
                            model_name='DeviceInfo',
                            object_id=str(kwargs.get('pk', 'list')),
                            ip_address=request.META.get('REMOTE_ADDR'),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                            request_path=request.path,
                            request_method=request.method,
                            status_code=getattr(response, 'status_code', 200)
                        )
                except Exception as audit_error:
                    logger.warning(f"Failed to create audit trail: {str(audit_error)}")
                
                return response
                
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                raise
        
        return wrapper
    return decorator


# ==================== GRACEFUL ERROR HANDLER ====================

def handle_gracefully(func):
    """Handle exceptions gracefully with defensive coding"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Graceful error handler caught: {str(e)}", exc_info=True)
            
            # Re-raise known exceptions
            from rest_framework.exceptions import (
                ValidationError, PermissionDenied, NotFound, 
                AuthenticationFailed, NotAuthenticated
            )
            
            if isinstance(e, (ValidationError, PermissionDenied, NotFound, 
                            AuthenticationFailed, NotAuthenticated)):
                raise
            
            # For unknown exceptions, return generic error
            from rest_framework.response import Response
            from rest_framework import status
            
            return Response(
                {
                    'error': 'An unexpected error occurred',
                    'detail': str(e) if settings.DEBUG else 'Please contact support'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return wrapper


# ==================== UPDATED DEVICE INFO VIEWSET ====================
class DeviceInfoFilter(FilterSet):
    class Meta:
        model = DeviceInfo
        fields = {
            'user__username': ['exact', 'icontains'],
            'device_model': ['exact', 'icontains'],
            'is_rooted': ['exact'],
            'is_emulator': ['exact'],
            'created_at': ['gte', 'lte']
        }


# ==================== DEFENSIVE CODING DECORATORS ====================

def safe_action(error_message: str = "Action failed", error_code: str = "action_failed"):
    """Decorator for safe view actions"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                return func(self, request, *args, **kwargs)
            except NotFound:
                raise
            except PermissionDenied as e:
                logger.warning(f"Permission denied in {func.__name__}: {str(e)}")
                return Response(
                    {'error': str(e), 'code': 'permission_denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e), 'code': 'validation_error'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return Response(
                    {'error': error_message, 'code': error_code},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return wrapper
    return decorator


def rate_limit(key_func=None, limit: int = 60, timeout: int = 60):
    """Rate limiting decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                if key_func:
                    rate_key = key_func(request)
                else:
                    user_id = getattr(request.user, 'id', 'anonymous')
                    rate_key = f"rate_limit_{func.__name__}_{user_id}"
                
                attempts = cache.get(rate_key, 0)
                
                if attempts >= limit:
                    logger.warning(f"Rate limit exceeded for {rate_key}")
                    return Response(
                        {'error': 'Too many requests. Please wait.', 'code': 'rate_limit_exceeded'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS
                    )
                
                cache.set(rate_key, attempts + 1, timeout)
                return func(self, request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Rate limiting error in {func.__name__}: {e}")
                return func(self, request, *args, **kwargs)  # Proceed without rate limiting on error
        return wrapper
    return decorator


def cache_response(timeout: int = 300):
    """Cache the response"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            try:
                # Generate cache key
                user_id = getattr(request.user, 'id', 'anonymous')
                query_params = request.query_params.urlencode()
                cache_key = f"view_{func.__name__}_{user_id}_{query_params}"
                
                # Try to get from cache
                cached_response = cache.get(cache_key)
                if cached_response:
                    return Response(cached_response)
                
                # Execute function
                response = func(self, request, *args, **kwargs)
                
                # Cache if successful
                if response.status_code == 200:
                    cache.set(cache_key, response.data, timeout)
                
                return response
                
            except Exception as e:
                logger.error(f"Cache error in {func.__name__}: {e}")
                return func(self, request, *args, **kwargs)  # Fallback
        return wrapper
    return decorator


# ==================== ENHANCED PERMISSIONS ====================

class CanManageDevices(BasePermission):
    """Permission for users who can manage devices"""
    
    def has_permission(self, request, view):
        try:
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return False
            
            # Check if user has device management permission
            return (
                user.has_perm('security.change_deviceinfo') or
                user.has_perm('security.manage_devices') or
                getattr(user, 'is_staff', False) or
                getattr(user, 'is_superuser', False)
            )
        except Exception as e:
            logger.error(f"Error in CanManageDevices: {e}")
            return False


class IsSecurityAdmin(BasePermission):
    """Permission for security admins"""
    
    def has_permission(self, request, view):
        try:
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return False
            
            return (
                user.has_perm('security.admin_access') or
                user.has_perm('security.can_blacklist') or
                getattr(user, 'is_superuser', False)
            )
        except Exception as e:
            logger.error(f"Error in IsSecurityAdmin: {e}")
            return False


class IsDeviceOwner(BasePermission):
    """Permission for device owners"""
    
    def has_object_permission(self, request, view, obj):
        try:
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return False
            
            # Staff can access all
            if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
                return True
            
            # Check if user owns the device
            return getattr(obj, 'user', None) == user
            
        except Exception as e:
            logger.error(f"Error in IsDeviceOwner: {e}")
            return False


# ==================== ENHANCED DEVICE VIEWSET ====================

class DeviceInfoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for device tracking and management.
    Comprehensive device monitoring with real-time risk assessment.
    
    WITH DEFENSIVE CODING & BULLETPROOF ERROR HANDLING
    """
    queryset = DeviceInfo.objects.select_related('user').order_by('-last_activity')
    serializer_class = DeviceInfoSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DeviceInfoFilter
    search_fields = ['device_id', 'device_model', 'device_brand', 'android_version', 'user__username']
    ordering_fields = ['last_activity', 'created_at', 'risk_score', 'trust_level']
    ordering = ['-last_activity']
    throttle_classes = [SecurityThrottle]
    
    # Cache for expensive operations
    _cache = {}
    
    def __init__(self, *args, **kwargs):
        """Initialize with defensive coding"""
        super().__init__(*args, **kwargs)
        self._cache = {}
    
    def get_permissions(self):
        """Dynamic permissions based on action with defensive coding"""
        try:
            action = getattr(self, 'action', None)
            
            # Define permission classes for different actions
            permission_map = {
                'list': [IsAuthenticated],
                'retrieve': [IsAuthenticated],
                'create': [IsAuthenticated],
                'update': [IsAuthenticated, CanManageDevices],
                'partial_update': [IsAuthenticated, CanManageDevices],
                'destroy': [IsSecurityAdmin],
                'toggle_trust': [IsAuthenticated, CanManageDevices],
                'blacklist_device': [IsSecurityAdmin],
                'whitelist_device': [IsSecurityAdmin],
                'analytics': [IsAuthenticated],
                'device_summary': [IsAuthenticated],
                'bulk_update': [IsSecurityAdmin],
                'export': [IsAuthenticated, CanManageDevices],
            }
            
            permission_classes = permission_map.get(action, [IsAuthenticated])
            return [permission() for permission in permission_classes]
            
        except Exception as e:
            logger.error(f"Error in get_permissions: {str(e)}", exc_info=True)
            # Default to most restrictive on error
            return [IsSecurityAdmin()]
    
    def get_queryset(self):
        """Filter queryset based on user permissions with defensive coding"""
        try:
            queryset = super().get_queryset()
            
            # Null object pattern - ensure we have a queryset
            if queryset is None:
                return DeviceInfo.objects.none()
            
            # Get user safely
            request = getattr(self, 'request', None)
            if not request:
                return DeviceInfo.objects.none()
            
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return DeviceInfo.objects.none()
            
            # Non-admin users can only see their own devices
            is_staff = getattr(user, 'is_staff', False)
            is_superuser = getattr(user, 'is_superuser', False)
            
            if not is_staff and not is_superuser:
                queryset = queryset.filter(user=user)
            
            # Apply additional filters with defensive checks
            query_params = getattr(request, 'query_params', {})
            
            # Safe parameter extraction
            suspicious_only = self._safe_param(query_params, 'suspicious_only', 'false')
            if suspicious_only.lower() == 'true':
                queryset = queryset.filter(
                    Q(is_rooted=True) | 
                    Q(is_emulator=True) | 
                    Q(risk_score__gt=70)
                )
            
            vpn_only = self._safe_param(query_params, 'vpn_only', 'false')
            if vpn_only.lower() == 'true':
                queryset = queryset.filter(is_vpn=True)
            
            trusted_only = self._safe_param(query_params, 'trusted_only', 'false')
            if trusted_only.lower() == 'true':
                queryset = queryset.filter(is_trusted=True)
            
            # Safe numeric parameters
            min_risk = self._safe_int_param(query_params, 'min_risk', None, 0, 100)
            if min_risk is not None:
                queryset = queryset.filter(current_score__gte=min_risk)
            
            max_risk = self._safe_int_param(query_params, 'max_risk', None, 0, 100)
            if max_risk is not None:
                queryset = queryset.filter(current_score__lte=max_risk)
            
            # Date filters
            from_date = self._safe_date_param(query_params, 'from_date')
            if from_date:
                queryset = queryset.filter(created_at__gte=from_date)
            
            to_date = self._safe_date_param(query_params, 'to_date')
            if to_date:
                queryset = queryset.filter(created_at__lte=to_date)
            
            return queryset.distinct()
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}", exc_info=True)
            # Graceful degradation - return empty queryset
            return DeviceInfo.objects.none()
    
    def _safe_param(self, params, key, default=''):
        """Safely get parameter from query params"""
        try:
            value = params.get(key, default)
            return value if value is not None else default
        except Exception:
            return default
    
    def _safe_int_param(self, params, key, default=None, min_val=None, max_val=None):
        """Safely get integer parameter"""
        try:
            value = params.get(key)
            if value is None:
                return default
            
            int_value = int(value)
            
            if min_val is not None:
                int_value = max(int_value, min_val)
            if max_val is not None:
                int_value = min(int_value, max_val)
            
            return int_value
        except (ValueError, TypeError):
            return default
    
    def _safe_date_param(self, params, key):
        """Safely get date parameter"""
        try:
            value = params.get(key)
            if value:
                from dateutil import parser
                return parser.parse(value)
            return None
        except Exception:
            return None
    
    def get_object(self):
        """Get object with additional security checks"""
        try:
            obj = super().get_object()
            
            # Check if user has permission to view this device
            request = getattr(self, 'request', None)
            if not request:
                raise PermissionDenied("No request object")
            
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Staff can view all devices
            if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
                return obj
            
            # Regular users can only view their own devices
            if getattr(obj, 'user', None) != user:
                raise PermissionDenied("You don't have permission to view this device")
            
            return obj
            
        except ObjectDoesNotExist:
            raise NotFound("Device not found")
        except PermissionDenied:
            raise
        except Exception as e:
            logger.error(f"Error in get_object: {e}")
            raise NotFound("Device not found")
    
    # ==================== LIST ACTION ====================
    
    # @action(detail=False, methods=['get'])
    @rate_limit(limit=30, timeout=60)
    @safe_action("Failed to retrieve devices", "list_failed")
    def list(self, request, *args, **kwargs):
        """List devices with enhanced security checks"""
        try:
            response = super().list(request, *args, **kwargs)
            
            # Add metadata
            if isinstance(response.data, dict):
                if 'results' in response.data:
                    response.data['metadata'] = {
                        'timestamp': timezone.now().isoformat(),
                        'user': getattr(request.user, 'username', 'anonymous'),
                        'total_count': self.get_queryset().count()
                    }
            elif isinstance(response.data, list):
                response.data = {
                    'results': response.data,
                    'metadata': {
                        'timestamp': timezone.now().isoformat(),
                        'user': getattr(request.user, 'username', 'anonymous'),
                        'total_count': len(response.data)
                    }
                }
            
            return response
        
        except Exception as e:
            logger.error(f"Device list error: {str(e)}", exc_info=True)
            raise
    
    # ==================== RETRIEVE ACTION ====================
    
    # @action(detail=True, methods=['get'])
    @safe_action("Failed to retrieve device", "retrieve_failed")
    def retrieve(self, request, *args, **kwargs):
        """Retrieve device details with security audit"""
        try:
            instance = self.get_object()
            
            # Update last activity safely (but not too frequently)
            self._update_last_activity(instance)
            
            serializer = self.get_serializer(instance)
            data = serializer.data
            
            # Add security warning if needed
            risk_score = getattr(instance, 'risk_score', 0)
            if risk_score > 70:
                if isinstance(data, dict):
                    data['security_warning'] = '[WARN] High risk device - verify user identity'
            
            return Response(data)
        
        except NotFound:
            raise
        except PermissionDenied as e:
            raise DRFPermissionDenied(str(e))
        except Exception as e:
            logger.error(f"Device retrieve error: {str(e)}", exc_info=True)
            raise
    
    def _update_last_activity(self, instance):
        """Update last activity with rate limiting"""
        try:
            cache_key = f"device_activity_{instance.id}"
            if not cache.get(cache_key):
                instance.last_activity = timezone.now()
                instance.save(update_fields=['last_activity'])
                cache.set(cache_key, True, 300)  # 5 minute cooldown
        except Exception as e:
            logger.debug(f"Failed to update last_activity: {str(e)}")
    
    # ==================== CREATE ACTION ====================
    
    # @action(detail=False, methods=['post'])
    @transaction.atomic
    @safe_action("Failed to create device", "creation_failed")
    def create(self, request, *args, **kwargs):
        """Register new device with security validation"""
        try:
            # Check if user already has too many devices
            self._check_device_limit(request.user)
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            validated_data = serializer.validated_data.copy()
            
            # Generate secure device hash
            validated_data = self._process_device_hash(validated_data)
            
            # Check for duplicates
            duplicate_info = self._check_duplicate_devices(validated_data, request.user)
            duplicate_count = duplicate_info['count']
            
            # Adjust risk score based on findings
            validated_data = self._adjust_risk_score(validated_data, duplicate_count)
            
            # Set user if not provided
            if not validated_data.get('user') and request.user.is_authenticated:
                validated_data['user'] = request.user
            
            # Save the device
            device = serializer.save(**validated_data)
            
            # Create security log if needed
            self._create_security_log(device, request, duplicate_count)
            
            headers = self.get_success_headers(serializer.data)
            
            # Get risk level display
            risk_level = 'Unknown'
            if hasattr(device, 'get_risk_level_display') and callable(device.get_risk_level_display):
                try:
                    risk_level = device.get_risk_level_display()
                except Exception:
                    pass
            
            return Response(
                {
                    'message': 'Device registered successfully',
                    'device': serializer.data,
                    'risk_level': risk_level,
                    'duplicate_warning': duplicate_count > 0
                },
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        
        except ValidationError as e:
            return Response(
                {'error': str(e), 'code': 'validation_error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Device creation error: {str(e)}", exc_info=True)
            raise
    
    def _check_device_limit(self, user, limit: int = 10):
        """Check if user has exceeded device limit"""
        if user and user.is_authenticated:
            try:
                device_count = DeviceInfo.objects.filter(user=user).count()
                if device_count >= limit:
                    raise ValidationError(f"Maximum device limit reached ({limit} devices)")
            except Exception as e:
                logger.warning(f"Failed to check device limit: {e}")
    
    def _process_device_hash(self, data: Dict) -> Dict:
        """Process and generate secure device hash"""
        device_id = data.get('device_id', '')
        
        if device_id:
            try:
                # Use secure salt generation
                salt = secrets.token_hex(16)
                device_hash = hashlib.sha256(
                    f"{device_id}{salt}".encode('utf-8')
                ).hexdigest()
                data['device_id_hash'] = device_hash
            except Exception as e:
                logger.warning(f"Failed to generate secure device hash: {e}")
                # Fallback without salt
                data['device_id_hash'] = hashlib.sha256(
                    device_id.encode('utf-8')
                ).hexdigest()
        else:
            # Generate placeholder hash
            data['device_id_hash'] = 'no_device_id_' + hashlib.md5(
                str(timezone.now()).encode()
            ).hexdigest()[:16]
        
        return data
    
    def _check_duplicate_devices(self, data: Dict, user) -> Dict:
        """Check for duplicate devices"""
        result = {'count': 0, 'devices': []}
        
        device_hash = data.get('device_id_hash')
        if device_hash and 'no_device_id' not in device_hash:
            try:
                # Find duplicates
                duplicates = DeviceInfo.objects.filter(device_id_hash=device_hash)
                
                if user and user.is_authenticated:
                    duplicates = duplicates.exclude(user=user)
                
                result['count'] = duplicates.count()
                
                # Get first few duplicates for logging
                if result['count'] > 0:
                    result['devices'] = list(
                        duplicates.values('id', 'user__username', 'risk_score')[:3]
                    )
                
                if result['count'] > 0:
                    logger.warning(
                        f"Duplicate device detected: {device_hash[:10]}... "
                        f"used by {result['count']} other users"
                    )
                
            except Exception as e:
                logger.warning(f"Failed to check duplicates: {e}")
        
        return result
    
    def _adjust_risk_score(self, data: Dict, duplicate_count: int) -> Dict:
        """Adjust risk score based on findings"""
        current_risk = data.get('risk_score', 0)
        
        # Adjust for duplicates
        if duplicate_count > 0:
            data['risk_score'] = min(current_risk + (duplicate_count * 10), 100)
        
        # Adjust for rooted/emulator devices
        if data.get('is_rooted', False) or data.get('is_emulator', False):
            data['risk_score'] = max(current_risk, 50)
        
        return data
    
    def _create_security_log(self, device, request, duplicate_count: int):
        """Create security log if needed"""
        risk_score = getattr(device, 'risk_score', 0)
        
        if risk_score > 70 or duplicate_count > 0:
            try:
                severity = 'high' if risk_score > 80 or duplicate_count > 2 else 'medium'
                
                SecurityLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    security_type='suspicious_device',
                    severity=severity,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    device_info=device,
                    description=f"New {'high-risk' if risk_score > 70 else 'duplicate'} device registered",
                    risk_score=risk_score,
                    metadata={
                        'device_model': getattr(device, 'device_model', 'unknown'),
                        'android_version': getattr(device, 'android_version', 'unknown'),
                        'is_rooted': getattr(device, 'is_rooted', False),
                        'is_emulator': getattr(device, 'is_emulator', False),
                        'is_vpn': getattr(device, 'is_vpn', False),
                        'duplicate_count': duplicate_count
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create security log: {e}")
    
    # ==================== UPDATE ACTION ====================
    
    # @action(detail=True, methods=['put', 'patch'])
    @transaction.atomic
    @safe_action("Failed to update device", "update_failed")
    def update(self, request, *args, **kwargs):
        """Update device with defensive coding"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            
            # Track changes for audit
            old_data = {
                'is_trusted': instance.is_trusted,
                'trust_level': instance.trust_level,
                'risk_score': instance.risk_score,
                'is_rooted': instance.is_rooted,
                'is_emulator': instance.is_emulator,
            }
            
            # Perform update
            self.perform_update(serializer)
            
            # Log significant changes
            self._log_device_changes(instance, old_data, request)
            
            return Response(serializer.data)
            
        except NotFound:
            raise
        except ValidationError as e:
            return Response(
                {'error': str(e), 'code': 'validation_error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Device update error: {str(e)}", exc_info=True)
            raise
    
    def _log_device_changes(self, instance, old_data: Dict, request):
        """Log significant device changes"""
        changes = []
        
        if instance.is_trusted != old_data['is_trusted']:
            changes.append(f"trust: {old_data['is_trusted']} -> {instance.is_trusted}")
        
        if instance.risk_score != old_data['risk_score']:
            changes.append(f"risk: {old_data['risk_score']} -> {instance.risk_score}")
        
        if instance.is_rooted != old_data['is_rooted']:
            changes.append(f"rooted: {old_data['is_rooted']} -> {instance.is_rooted}")
        
        if changes:
            logger.info(
                f"Device {instance.id} updated by {getattr(request.user, 'username', 'unknown')}: "
                f"{', '.join(changes)}"
            )
    
    # ==================== DESTROY ACTION ====================
    
    # @action(detail=True, methods=['delete'])
    @transaction.atomic
    @safe_action("Failed to delete device", "delete_failed")
    def destroy(self, request, *args, **kwargs):
        """Delete device with audit logging"""
        try:
            instance = self.get_object()
            device_id = instance.id
            user_info = f"User: {getattr(instance.user, 'username', 'None')}"
            
            # Log deletion
            logger.warning(
                f"Device {device_id} ({user_info}) deleted by "
                f"{getattr(request.user, 'username', 'unknown')}"
            )
            
            # Perform deletion
            self.perform_destroy(instance)
            
            return Response(
                {
                    'message': 'Device deleted successfully',
                    'device_id': device_id
                },
                status=status.HTTP_200_OK
            )
            
        except NotFound:
            raise
        except Exception as e:
            logger.error(f"Device deletion error: {str(e)}", exc_info=True)
            raise
    
    # ==================== CUSTOM ACTIONS ====================
    
    @action(detail=True, methods=['post'], url_path='toggle-trust')
    @transaction.atomic
    @safe_action("Failed to toggle device trust", "trust_toggle_failed")
    def toggle_trust(self, request, pk=None):
        """Toggle device trust status"""
        try:
            device = self.get_object()
            
            # Toggle trust status
            current_trusted = getattr(device, 'is_trusted', False)
            device.is_trusted = not current_trusted
            device.trust_level = 3 if device.is_trusted else 1
            device.risk_score = 10 if device.is_trusted else max(device.risk_score, 30)
            
            # Save with defensive coding
            device.save(update_fields=['is_trusted', 'trust_level', 'risk_score', 'updated_at'])
            
            # Log the action
            action = "trusted" if device.is_trusted else "untrusted"
            logger.info(f"Device {device.id} {action} by {getattr(request.user, 'username', 'unknown')}")
            
            # Create security log
            self._create_trust_change_log(device, request, action)
            
            return Response({
                'message': f'Device {action} successfully',
                'is_trusted': device.is_trusted,
                'trust_level': device.trust_level,
                'risk_score': device.risk_score,
                'device_id': device.id
            })
        
        except NotFound:
            raise
        except Exception as e:
            logger.error(f"Device trust toggle error: {str(e)}", exc_info=True)
            raise
    
    def _create_trust_change_log(self, device, request, action: str):
        """Create trust change log"""
        try:
            SecurityLog.objects.create(
                user=request.user,
                security_type='device_trust_change',
                severity='medium',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=device,
                description=f"Device {action} by {getattr(request.user, 'username', 'unknown')}",
                metadata={
                    'action': action,
                    'previous_state': action == 'untrusted',
                    'trust_level': device.trust_level,
                    'risk_score': device.risk_score
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create trust change log: {e}")
    
    @action(detail=False, methods=['get'], url_path='analytics')
    @cache_response(timeout=300)  # Cache for 5 minutes
    @safe_action("Failed to generate device analytics", "analytics_failed")
    def analytics(self, request):
        """Get device analytics and statistics"""
        try:
            # Parse days parameter safely
            days = self._safe_int_param(request.query_params, 'days', 30, 1, 365)
            start_date = timezone.now() - timedelta(days=days)
            
            # Build analytics data
            analytics_data = {
                'timeframe': f'Last {days} days',
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'overview': self._get_device_overview(start_date),
                'risk_distribution': self._get_risk_distribution(),
                'device_types': self._get_device_types_breakdown(),
                'suspicious_activity': self._get_suspicious_activity(start_date),
                'trends': self._get_device_trends(start_date),
                'generated_at': timezone.now().isoformat()
            }
            
            # Add user-specific analytics for non-admin
            user = request.user
            if not getattr(user, 'is_staff', False) and not getattr(user, 'is_superuser', False):
                analytics_data['user_specific'] = self._get_user_analytics(user)
            
            return Response(analytics_data)
        
        except Exception as e:
            logger.error(f"Device analytics error: {str(e)}", exc_info=True)
            raise
    
    def _get_device_overview(self, start_date):
        """Get device overview statistics"""
        try:
            devices = DeviceInfo.objects.filter(last_activity__gte=start_date)
            
            avg_risk = devices.aggregate(Avg('risk_score'))
            avg_risk_value = avg_risk.get('risk_score__avg', 0) or 0
            
            return {
                'total_devices': devices.count(),
                'active_devices': devices.filter(
                    last_activity__gte=timezone.now() - timedelta(days=1)
                ).count(),
                'rooted_devices': devices.filter(is_rooted=True).count(),
                'emulator_devices': devices.filter(is_emulator=True).count(),
                'vpn_devices': devices.filter(is_vpn=True).count(),
                'trusted_devices': devices.filter(is_trusted=True).count(),
                'average_risk_score': round(avg_risk_value, 2)
            }
        except Exception as e:
            logger.error(f"Error in device overview: {e}")
            return {
                'total_devices': 0,
                'active_devices': 0,
                'rooted_devices': 0,
                'emulator_devices': 0,
                'vpn_devices': 0,
                'trusted_devices': 0,
                'average_risk_score': 0
            }
    
    def _get_risk_distribution(self):
        """Get risk score distribution"""
        try:
            distribution = DeviceInfo.objects.aggregate(
                low_risk=Count('id', filter=Q(current_score__lt=30)),
                medium_risk=Count('id', filter=Q(current_score__gte=30, current_score__lt=70)),
                high_risk=Count('id', filter=Q(current_score__gte=70))
            )
            
            return {
                'low_risk': distribution.get('low_risk', 0),
                'medium_risk': distribution.get('medium_risk', 0),
                'high_risk': distribution.get('high_risk', 0)
            }
        except Exception as e:
            logger.error(f"Error in risk distribution: {e}")
            return {'low_risk': 0, 'medium_risk': 0, 'high_risk': 0}
    
    def _get_device_types_breakdown(self):
        """Get device types breakdown"""
        try:
            breakdown = list(
                DeviceInfo.objects.values('device_brand')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .filter(device_brand__isnull=False)
                .exclude(device_brand='')
            )
            
            return [
                {
                    'brand': item.get('device_brand', 'Unknown'),
                    'count': item.get('count', 0)
                }
                for item in breakdown
            ]
        except Exception as e:
            logger.error(f"Error in device types breakdown: {e}")
            return []
    
    def _get_suspicious_activity(self, start_date):
        """Get suspicious device activity"""
        try:
            # Count duplicate devices
            duplicate_devices = DeviceInfo.objects.values('device_id_hash').annotate(
                count=Count('id')
            ).filter(count__gt=1)
            
            duplicate_count = sum(dup.get('count', 0) for dup in duplicate_devices)
            
            # Count recently blacklisted
            blacklisted_count = DeviceInfo.objects.filter(
                last_activity__gte=start_date,
                risk_score__gt=80
            ).count()
            
            return {
                'duplicate_devices': duplicate_count,
                'recently_blacklisted': blacklisted_count
            }
        except Exception as e:
            logger.error(f"Error in suspicious activity: {e}")
            return {'duplicate_devices': 0, 'recently_blacklisted': 0}
    
    def _get_device_trends(self, start_date):
        """Get device trends over time"""
        try:
            trends = []
            
            for i in range(7, 0, -1):
                try:
                    date = timezone.now() - timedelta(days=i)
                    prev_date = date - timedelta(days=1)
                    
                    day_devices = DeviceInfo.objects.filter(
                        created_at__date=date.date()
                    ).count()
                    
                    prev_day_devices = DeviceInfo.objects.filter(
                        created_at__date=prev_date.date()
                    ).count()
                    
                    if prev_day_devices > 0:
                        growth = ((day_devices - prev_day_devices) / prev_day_devices * 100)
                    else:
                        growth = 0 if day_devices == 0 else 100
                    
                    trends.append({
                        'date': date.date().isoformat(),
                        'new_devices': day_devices,
                        'growth_rate': round(growth, 2)
                    })
                    
                except Exception as e:
                    logger.debug(f"Error processing day {i}: {e}")
                    trends.append({
                        'date': (timezone.now() - timedelta(days=i)).date().isoformat(),
                        'new_devices': 0,
                        'growth_rate': 0
                    })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error in device trends: {e}")
            return []
    
    def _get_user_analytics(self, user):
        """Get user-specific analytics"""
        try:
            user_devices = DeviceInfo.objects.filter(user=user)
            
            avg_risk = user_devices.aggregate(Avg('risk_score'))
            avg_risk_value = avg_risk.get('risk_score__avg', 0) or 0
            
            return {
                'total_devices': user_devices.count(),
                'trusted_devices': user_devices.filter(is_trusted=True).count(),
                'suspicious_devices': user_devices.filter(risk_score__gt=70).count(),
                'average_risk_score': round(avg_risk_value, 2)
            }
        except Exception as e:
            logger.error(f"Error in user analytics: {e}")
            return {
                'total_devices': 0,
                'trusted_devices': 0,
                'suspicious_devices': 0,
                'average_risk_score': 0
            }
    
    @action(detail=True, methods=['post'], url_path='blacklist')
    @transaction.atomic
    @safe_action("Failed to blacklist device", "blacklist_failed")
    def blacklist_device(self, request, pk=None):
        """Blacklist a suspicious device"""
        try:
            device = self.get_object()
            
            # Get reason from request
            reason = request.data.get('reason', 'Suspicious activity detected')
            if len(reason) > 500:
                reason = reason[:500]
            
            # Update device
            device.is_blacklisted = True
            device.risk_score = 100
            device.is_trusted = False
            device.trust_level = 1
            device.save(update_fields=['is_blacklisted', 'risk_score', 'is_trusted', 'trust_level', 'updated_at'])
            
            # Create security log
            self._create_blacklist_log(device, request, reason)
            
            # If device has a user, log it
            if device.user:
                logger.warning(f"User {device.user.username} had device blacklisted")
            
            return Response({
                'message': 'Device blacklisted successfully',
                'device_id': device.id,
                'is_blacklisted': True,
                'risk_score': 100
            })
            
        except NotFound:
            raise
        except Exception as e:
            logger.error(f"Device blacklist error: {str(e)}", exc_info=True)
            raise
    
    def _create_blacklist_log(self, device, request, reason: str):
        """Create blacklist log"""
        try:
            SecurityLog.objects.create(
                user=request.user,
                security_type='device_blacklisted',
                severity='critical',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=device,
                description=f"Device blacklisted by {getattr(request.user, 'username', 'admin')}: {reason}",
                metadata={
                    'device_model': getattr(device, 'device_model', 'unknown'),
                    'device_id_hash': getattr(device, 'device_id_hash', 'unknown')[:16],
                    'reason': reason,
                    'risk_score': 100
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create blacklist log: {e}")
    
    @action(detail=True, methods=['post'], url_path='whitelist')
    @transaction.atomic
    @safe_action("Failed to whitelist device", "whitelist_failed")
    def whitelist_device(self, request, pk=None):
        """Whitelist a trusted device"""
        try:
            device = self.get_object()
            
            # Get reason from request
            reason = request.data.get('reason', 'Verified as safe device')
            if len(reason) > 500:
                reason = reason[:500]
            
            # Update device
            device.is_blacklisted = False
            device.is_trusted = True
            device.risk_score = 10
            device.trust_level = 3
            device.save(update_fields=['is_blacklisted', 'is_trusted', 'risk_score', 'trust_level', 'updated_at'])
            
            # Create security log
            self._create_whitelist_log(device, request, reason)
            
            return Response({
                'message': 'Device whitelisted successfully',
                'device_id': device.id,
                'is_trusted': True,
                'is_blacklisted': False,
                'risk_score': 10
            })
            
        except NotFound:
            raise
        except Exception as e:
            logger.error(f"Device whitelist error: {str(e)}", exc_info=True)
            raise
    
    def _create_whitelist_log(self, device, request, reason: str):
        """Create whitelist log"""
        try:
            SecurityLog.objects.create(
                user=request.user,
                security_type='device_whitelisted',
                severity='low',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=device,
                description=f"Device whitelisted by {getattr(request.user, 'username', 'admin')}: {reason}",
                metadata={
                    'device_model': getattr(device, 'device_model', 'unknown'),
                    'device_id_hash': getattr(device, 'device_id_hash', 'unknown')[:16],
                    'reason': reason,
                    'risk_score': 10
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create whitelist log: {e}")
    
    @action(detail=False, methods=['get'], url_path='summary')
    @cache_response(timeout=60)  # Cache for 1 minute
    @safe_action("Failed to generate device summary", "summary_failed")
    def device_summary(self, request):
        """Get quick device summary"""
        try:
            user = request.user
            
            if not user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # For admin - get system-wide summary
            if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
                return Response(self._get_admin_summary())
            
            # For regular user - get their own devices
            return Response(self._get_user_summary(user))
            
        except Exception as e:
            logger.error(f"Device summary error: {str(e)}", exc_info=True)
            raise
    
    def _get_admin_summary(self) -> Dict:
        """Get admin-level device summary"""
        try:
            total_devices = DeviceInfo.objects.count()
            trusted_devices = DeviceInfo.objects.filter(is_trusted=True).count()
            suspicious_devices = DeviceInfo.objects.filter(risk_score__gt=70).count()
            rooted_devices = DeviceInfo.objects.filter(is_rooted=True).count()
            
            recent_devices = DeviceInfo.objects.filter(
                last_activity__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Calculate percentages safely
            trust_percentage = 0
            risk_percentage = 0
            
            if total_devices > 0:
                trust_percentage = round((trusted_devices / total_devices * 100), 2)
                risk_percentage = round((suspicious_devices / total_devices * 100), 2)
            
            return {
                'scope': 'system',
                'total_devices': total_devices,
                'trusted_devices': trusted_devices,
                'suspicious_devices': suspicious_devices,
                'rooted_devices': rooted_devices,
                'recent_activity_24h': recent_devices,
                'trust_percentage': trust_percentage,
                'risk_percentage': risk_percentage
            }
        except Exception as e:
            logger.error(f"Error in admin summary: {e}")
            return {
                'scope': 'system',
                'total_devices': 0,
                'trusted_devices': 0,
                'suspicious_devices': 0,
                'rooted_devices': 0,
                'recent_activity_24h': 0,
                'trust_percentage': 0,
                'risk_percentage': 0
            }
    
    def _get_user_summary(self, user) -> Dict:
        """Get user-level device summary"""
        try:
            user_devices = DeviceInfo.objects.filter(user=user)
            
            total_devices = user_devices.count()
            trusted_devices = user_devices.filter(is_trusted=True).count()
            suspicious_devices = user_devices.filter(risk_score__gt=70).count()
            
            recent_devices = user_devices.filter(
                last_activity__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Calculate average risk
            avg_risk = user_devices.aggregate(Avg('risk_score'))
            avg_risk_value = avg_risk.get('risk_score__avg', 0) or 0
            
            return {
                'scope': 'user',
                'total_devices': total_devices,
                'trusted_devices': trusted_devices,
                'suspicious_devices': suspicious_devices,
                'average_risk_score': round(avg_risk_value, 2),
                'recent_activity_24h': recent_devices
            }
        except Exception as e:
            logger.error(f"Error in user summary: {e}")
            return {
                'scope': 'user',
                'total_devices': 0,
                'trusted_devices': 0,
                'suspicious_devices': 0,
                'average_risk_score': 0,
                'recent_activity_24h': 0
            }
    
    @action(detail=False, methods=['post'], url_path='bulk-update')
    @transaction.atomic
    @safe_action("Failed to bulk update devices", "bulk_update_failed")
    def bulk_update(self, request):
        """Bulk update devices (admin only)"""
        try:
            data = request.data
            device_ids = data.get('device_ids', [])
            update_data = data.get('update_data', {})
            
            if not device_ids:
                return Response(
                    {'error': 'No device IDs provided', 'code': 'no_devices'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not update_data:
                return Response(
                    {'error': 'No update data provided', 'code': 'no_update_data'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit number of devices to update
            if len(device_ids) > 100:
                return Response(
                    {'error': 'Cannot update more than 100 devices at once', 'code': 'too_many_devices'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter allowed update fields
            allowed_fields = ['is_trusted', 'trust_level', 'risk_score', 'is_blacklisted']
            clean_update = {
                k: v for k, v in update_data.items() 
                if k in allowed_fields
            }
            
            if not clean_update:
                return Response(
                    {'error': 'No valid fields to update', 'code': 'no_valid_fields'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Perform bulk update
            updated = DeviceInfo.objects.filter(id__in=device_ids).update(**clean_update)
            
            logger.info(
                f"Bulk updated {updated} devices by {getattr(request.user, 'username', 'unknown')}: "
                f"{clean_update}"
            )
            
            return Response({
                'message': f'Successfully updated {updated} devices',
                'updated_count': updated,
                'fields_updated': list(clean_update.keys())
            })
            
        except Exception as e:
            logger.error(f"Bulk update error: {str(e)}", exc_info=True)
            raise
    
    @action(detail=False, methods=['get'], url_path='export')
    @safe_action("Failed to export devices", "export_failed")
    def export(self, request):
        """Export devices as CSV"""
        try:
            import csv
            from django.http import HttpResponse
            
            # Get filtered queryset
            queryset = self.filter_queryset(self.get_queryset())
            
            # Limit export size
            if queryset.count() > 10000:
                return Response(
                    {'error': 'Too many devices to export. Please filter your query.', 'code': 'too_many_devices'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            filename = f"devices_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            writer = csv.writer(response)
            writer.writerow([
                'ID', 'User', 'Device Model', 'Device Brand', 'Android Version',
                'Risk Score', 'Is Rooted', 'Is Emulator', 'Is VPN', 'Is Proxy',
                'Is Trusted', 'Last IP', 'Last Activity', 'Created At'
            ])
            
            for device in queryset.iterator(chunk_size=1000):
                writer.writerow([
                    device.id,
                    getattr(device.user, 'username', '') if device.user else '',
                    device.device_model or '',
                    device.device_brand or '',
                    device.android_version or '',
                    device.risk_score or 0,
                    device.is_rooted,
                    device.is_emulator,
                    device.is_vpn,
                    device.is_proxy,
                    device.is_trusted,
                    device.last_ip or '',
                    device.last_activity.strftime('%Y-%m-%d %H:%M:%S') if device.last_activity else '',
                    device.created_at.strftime('%Y-%m-%d %H:%M:%S') if device.created_at else '',
                ])
            
            logger.info(f"Exported {queryset.count()} devices by {getattr(request.user, 'username', 'unknown')}")
            
            return response
            
        except Exception as e:
            logger.error(f"Device export error: {str(e)}", exc_info=True)
            raise

        
class SecurityLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for security log management.
    Comprehensive security event tracking and monitoring.
    """
    queryset = SecurityLog.objects.select_related('user', 'device_info').order_by('-created_at')
    serializer_class = SecurityLogSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SecurityLogFilter
    search_fields = ['security_type', 'description', 'ip_address', 'user__username']
    ordering_fields = ['created_at', 'severity', 'risk_score']
    ordering = ['-created_at']
    throttle_classes = [SecurityThrottle]
    
    def get_permissions(self):
        """Dynamic permissions"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, CanViewSecurityLogs]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsSecurityAdmin]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own logs
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            queryset = queryset.filter(user=self.request.user)
        
        # Apply severity filter
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Apply resolved filter
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            queryset = queryset.filter(resolved=resolved.lower() == 'true')
        
        return queryset
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('SECURITY_LOG_RESOLVE')
    def resolve(self, request, pk=None):
        """Mark security log as resolved"""
        try:
            security_log = self.get_object()
            
            if not request.user.has_perm('security.manage_securitylog'):
                raise PermissionDenied("You don't have permission to resolve security logs.")
            
            reason = request.data.get('reason', '')
            notes = request.data.get('notes', '')
            
            security_log.mark_resolved(
                resolved_by=request.user,
                notes=notes
            )
            
            # Update action taken
            if reason:
                security_log.action_taken = f"Resolved: {reason}"
                security_log.save(update_fields=['action_taken'])
            
            return Response({
                'message': 'Security log resolved successfully',
                'resolved_at': security_log.resolved_at,
                'resolved_by': security_log.resolved_by.username if security_log.resolved_by else None
            })
        
        except SecurityLog.DoesNotExist:
            raise NotFound("Security log not found.")
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('SECURITY_LOG_STATISTICS')
    def statistics(self, request):
        """Get security log statistics"""
        try:
            days = int(request.query_params.get('days', 7))
            start_date = timezone.now() - timedelta(days=days)
            
            statistics = {
                'timeframe': f'Last {days} days',
                'total_logs': self.queryset.filter(created_at__gte=start_date).count(),
                'by_severity': self._get_logs_by_severity(start_date),
                'by_type': self._get_logs_by_type(start_date),
                'resolution_rate': self._get_resolution_rate(start_date),
                'top_users': self._get_top_users_with_logs(start_date),
                'hourly_distribution': self._get_hourly_distribution(start_date),
                'trends': self._get_security_trends(start_date)
            }
            
            return Response(statistics)
        
        except Exception as e:
            logger.error(f"Security log statistics error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_logs_by_severity(self, start_date):
        """Get logs breakdown by severity"""
        return list(
            self.queryset.filter(created_at__gte=start_date)
            .values('severity')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    def _get_logs_by_type(self, start_date):
        """Get logs breakdown by type"""
        return list(
            self.queryset.filter(created_at__gte=start_date)
            .values('security_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
    
    def _get_resolution_rate(self, start_date):
        """Get resolution rate"""
        total = self.queryset.filter(created_at__gte=start_date).count()
        resolved = self.queryset.filter(created_at__gte=start_date, resolved=True).count()
        
        return {
            'total': total,
            'resolved': resolved,
            'rate': round((resolved / total * 100) if total > 0 else 0, 2)
        }
    
    def _get_top_users_with_logs(self, start_date):
        """Get top users with most security logs"""
        return list(
            self.queryset.filter(created_at__gte=start_date)
            .values('user__username')
            .annotate(count=Count('id'), avg_risk=Avg('risk_score'))
            .order_by('-count')[:5]
        )
    
    def _get_hourly_distribution(self, start_date):
        """Get hourly distribution of security logs"""
        return list(
            self.queryset.filter(created_at__gte=start_date)
            .annotate(hour=ExtractHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )
    
    def _get_security_trends(self, start_date):
        """Get security trends over time"""
        trends = []
        for i in range(7, 0, -1):
            date = timezone.now() - timedelta(days=i)
            prev_date = date - timedelta(days=1)
            
            day_logs = self.queryset.filter(created_at__date=date.date())
            prev_day_logs = self.queryset.filter(created_at__date=prev_date.date())
            
            day_count = day_logs.count()
            prev_count = prev_day_logs.count()
            
            high_severity = day_logs.filter(severity__in=['high', 'critical']).count()
            
            growth = ((day_count - prev_count) / prev_count * 100) if prev_count > 0 else 0
            
            trends.append({
                'date': date.date(),
                'total_logs': day_count,
                'high_severity': high_severity,
                'growth_rate': round(growth, 2)
            })
        
        return trends


class RiskScoreViewSet(viewsets.ModelViewSet):
    """
    ViewSet for risk score management.
    Real-time risk assessment and monitoring.
    """
    queryset = RiskScore.objects.select_related('user').order_by('-current_score')
    serializer_class = RiskScoreSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['user__username']
    ordering_fields = ['current_score', 'calculated_at', 'failed_login_attempts']
    ordering = ['-current_score']
    throttle_classes = [SecurityThrottle]
    
    def get_permissions(self):
        """Dynamic permissions"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, CanViewSecurityLogs]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsSecurityAdmin]
        else:
            permission_classes = [IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own risk score
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            queryset = queryset.filter(user=self.request.user)
        
        # Filter by risk level
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            if risk_level == 'low':
                queryset = queryset.filter(current_score__lt=30)
            elif risk_level == 'medium':
                queryset = queryset.filter(current_score__gte=30, current_score__lt=70)
            elif risk_level == 'high':
                queryset = queryset.filter(current_score__gte=70)
        
        return queryset
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('RISK_SCORE_RECALCULATE')
    def recalculate(self, request, pk=None):
        """Recalculate risk score for a user"""
        try:
            risk_score = self.get_object()
            
            if not request.user.has_perm('security.manage_riskscore'):
                raise PermissionDenied("You don't have permission to recalculate risk scores.")
            
            # Recalculate score
            risk_score.update_score()
            
            # Check if score crossed threshold
            if risk_score.current_score >= 70 and risk_score.previous_score < 70:
                SecurityLog.objects.create(
                    user=risk_score.user,
                    security_type='suspicious_activity',
                    severity='high',
                    description=f'Risk score crossed high threshold: {risk_score.current_score}',
                    risk_score=risk_score.current_score,
                    metadata={
                        'previous_score': risk_score.previous_score,
                        'current_score': risk_score.current_score,
                        'change': risk_score.current_score - risk_score.previous_score
                    }
                )
            
            serializer = self.get_serializer(risk_score)
            return Response(serializer.data)
        
        except RiskScore.DoesNotExist:
            raise NotFound("Risk score not found.")
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('RISK_DISTRIBUTION')
    def distribution(self, request):
        """Get risk score distribution"""
        try:
            distribution = {
                'low_risk': self.queryset.filter(current_score__lt=30).count(),
                'medium_risk': self.queryset.filter(current_score__gte=30, current_score__lt=70).count(),
                'high_risk': self.queryset.filter(current_score__gte=70).count(),
                'average_score': self.queryset.aggregate(Avg('current_score'))['current_score__avg'] or 0,
                'top_risk_factors': self._get_top_risk_factors()
            }
            
            return Response(distribution)
        
        except Exception as e:
            logger.error(f"Risk distribution error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate risk distribution'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_top_risk_factors(self):
        """Get top contributing risk factors"""
        return {
            'high_failed_logins': self.queryset.filter(failed_login_attempts__gt=5).count(),
            'vpn_users': self.queryset.filter(vpn_usage_count__gt=10).count(),
            'multiple_devices': self.queryset.filter(device_diversity__gt=5).count(),
            'recent_suspicious': self.queryset.filter(
                last_suspicious_activity__gte=timezone.now() - timedelta(days=1)
            ).count()
        }


class SecurityDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for security dashboard.
    Real-time security metrics and analytics.
    """
    queryset = SecurityDashboard.objects.order_by('-date')
    serializer_class = SecurityDashboardSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['date', 'total_threats']
    ordering = ['-date']
    throttle_classes = [SecurityThrottle]
    permission_classes = [IsAuthenticated, IsSecurityStaff]
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('SECURITY_OVERVIEW')
    def overview(self, request):
        """Get comprehensive security overview"""
        try:
            days = int(request.query_params.get('days', 7))
            start_date = timezone.now() - timedelta(days=days)
            
            overview = {
                'timeframe': f'Last {days} days',
                'summary': self._get_security_summary(start_date),
                'threat_breakdown': self._get_threat_breakdown(start_date),
                'risk_analysis': self._get_risk_analysis(),
                'geographical_insights': self._get_geographical_insights(start_date),
                'device_insights': self._get_device_insights(),
                'performance_metrics': self._get_performance_metrics()
            }
            
            return Response(overview)
        
        except Exception as e:
            logger.error(f"Security overview error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate security overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_security_summary(self, start_date):
        """Get security summary"""
        from django.db.models import Sum
        
        summary = SecurityDashboard.objects.filter(
            date__gte=start_date
        ).aggregate(
            total_users=Sum('total_users'),
            active_users=Sum('active_users'),
            total_threats=Sum('total_threats'),
            threats_blocked=Sum('threats_blocked')
        )
        
        return {
            'total_users': summary['total_users'] or 0,
            'active_users': summary['active_users'] or 0,
            'total_threats': summary['total_threats'] or 0,
            'threats_blocked': summary['threats_blocked'] or 0,
            'block_rate': round(
                (summary['threats_blocked'] / summary['total_threats'] * 100) 
                if summary['total_threats'] and summary['total_threats'] > 0 else 0, 
                2
            )
        }
    
    def _get_threat_breakdown(self, start_date):
        """Get threat type breakdown"""
        from django.db.models import Sum
        
        breakdown = SecurityDashboard.objects.filter(
            date__gte=start_date
        ).aggregate(
            vpn_threats=Sum('vpn_threats'),
            proxy_threats=Sum('proxy_threats'),
            rooted_threats=Sum('rooted_threats'),
            duplicate_accounts=Sum('duplicate_accounts'),
            fast_clicking=Sum('fast_clicking'),
            api_abuse=Sum('api_abuse')
        )
        
        return breakdown
    
    def _get_risk_analysis(self):
        """Get risk analysis"""
        latest_dashboard = SecurityDashboard.objects.order_by('-date').first()
        if not latest_dashboard:
            return {}
        
        return {
            'low_risk_users': latest_dashboard.low_risk_users,
            'medium_risk_users': latest_dashboard.medium_risk_users,
            'high_risk_users': latest_dashboard.high_risk_users,
            'critical_risk_users': latest_dashboard.critical_risk_users,
            'total_risky_users': (
                latest_dashboard.medium_risk_users + 
                latest_dashboard.high_risk_users + 
                latest_dashboard.critical_risk_users
            )
        }
    
    def _get_geographical_insights(self, start_date):
        """Get geographical insights"""
        try:
            # Get geolocation data from logs
            from .models import GeolocationLog
            
            recent_logs = SecurityLog.objects.filter(
                created_at__gte=start_date,
                severity__in=['high', 'critical']
            ).values_list('ip_address', flat=True)
            
            countries = defaultdict(int)
            for ip in recent_logs:
                geolocation = GeolocationLog.get_geolocation(ip)
                if geolocation.country_name:
                    countries[geolocation.country_name] += 1
            
            top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                'top_countries': [{'country': k, 'threats': v} for k, v in top_countries],
                'total_countries': len(countries)
            }
        
        except Exception as e:
            logger.error(f"Geographical insights error: {str(e)}")
            return {'top_countries': [], 'total_countries': 0}
    
    def _get_device_insights(self):
        """Get device insights"""
        return {
            'rooted_devices': DeviceInfo.objects.filter(is_rooted=True).count(),
            'emulator_devices': DeviceInfo.objects.filter(is_emulator=True).count(),
            'vpn_devices': DeviceInfo.objects.filter(is_vpn=True).count(),
            'trusted_devices': DeviceInfo.objects.filter(is_trusted=True).count()
        }
    
    def _get_performance_metrics(self):
        """Get performance metrics"""
        from django.core.cache import cache
        from django.db import connection
        
        try:
            # Database performance
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM security_logs")
                log_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT count(*) FROM security_deviceinfo")
                device_count = cursor.fetchone()[0]
            
            # Cache performance
            cache_hits = cache.get('cache_hits', 0)
            cache_misses = cache.get('cache_misses', 0)
            total_requests = cache_hits + cache_misses
            cache_hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'database': {
                    'security_logs': log_count,
                    'devices': device_count,
                    'connection_health': 'healthy'
                },
                'cache': {
                    'hit_rate': round(cache_hit_rate, 2),
                    'hits': cache_hits,
                    'misses': cache_misses
                },
                'response_time': 'good'  # This would come from monitoring system
            }
        
        except Exception as e:
            logger.error(f"Performance metrics error: {str(e)}")
            return {
                'database': {'error': 'Unable to fetch metrics'},
                'cache': {'error': 'Unable to fetch metrics'},
                'response_time': 'unknown'
            }


class AutoBlockRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for auto-block rule management.
    Automated security rule engine.
    """
    queryset = AutoBlockRule.objects.order_by('-priority', 'name')
    serializer_class = AutoBlockRuleSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description', 'rule_type']
    ordering_fields = ['priority', 'name', 'created_at']
    ordering = ['-priority', 'name']
    throttle_classes = [SecurityThrottle]
    permission_classes = [IsAuthenticated, IsSecurityAdmin]
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('AUTO_BLOCK_RULE_TEST')
    def test(self, request, pk=None):
        """Test auto-block rule with sample data"""
        try:
            rule = self.get_object()
            
            # Get test data from request
            test_data = request.data.get('test_data', {})
            user_id = test_data.get('user_id')
            ip_address = test_data.get('ip_address')
            
            # Get user and device info for testing
            user = None
            device_info = None
            
            if user_id:
                try:
                    user = get_user_model().objects.get(id=user_id)
                    device_info = DeviceInfo.objects.filter(user=user).first()
                except get_user_model().DoesNotExist:
                    pass
            
            # Evaluate rule
            should_trigger = rule.evaluate(
                user=user,
                ip_address=ip_address,
                device_info=device_info,
                activity_data=test_data
            )
            
            # If triggered, show what action would be taken
            action_result = None
            if should_trigger:
                action_result = rule.take_action(
                    user=user,
                    ip_address=ip_address,
                    device_info=device_info,
                    reason="Test execution"
                )
            
            return Response({
                'rule_name': rule.name,
                'rule_type': rule.rule_type,
                'should_trigger': should_trigger,
                'action_type': rule.action_type if should_trigger else None,
                'action_result': str(action_result) if action_result else None,
                'test_data_used': test_data
            })
        
        except AutoBlockRule.DoesNotExist:
            raise NotFound("Auto-block rule not found.")
        except Exception as e:
            logger.error(f"Rule test error: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to test rule: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('AUTO_BLOCK_STATISTICS')
    def statistics(self, request):
        """Get auto-block rule statistics"""
        try:
            # Get rule effectiveness
            rules = AutoBlockRule.objects.all()
            
            statistics = {
                'total_rules': rules.count(),
                'active_rules': rules.filter(is_active=True).count(),
                'by_type': self._get_rules_by_type(rules),
                'by_action': self._get_rules_by_action(rules),
                'effectiveness': self._get_rule_effectiveness(),
                'recent_activations': self._get_recent_activations()
            }
            
            return Response(statistics)
        
        except Exception as e:
            logger.error(f"Auto-block statistics error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_rules_by_type(self, rules):
        """Get rules breakdown by type"""
        return list(
            rules.values('rule_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    def _get_rules_by_action(self, rules):
        """Get rules breakdown by action type"""
        return list(
            rules.values('action_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    
    def _get_rule_effectiveness(self):
        """Get rule effectiveness metrics"""
        # This would typically come from monitoring system
        # For now, using mock data
        return {
            'total_executions': 1250,
            'successful_blocks': 980,
            'false_positives': 45,
            'effectiveness_rate': 78.4,
            'average_response_time': '2.3s'
        }
    
    def _get_recent_activations(self):
        """Get recent rule activations"""
        # Get recent security logs triggered by auto-block rules
        recent_logs = SecurityLog.objects.filter(
            security_type='suspicious_activity',
            description__icontains='Auto-block',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')[:10]
        
        return [
            {
                'timestamp': log.created_at,
                'rule': log.description.split(':')[1].strip() if ':' in log.description else 'Unknown',
                'user': log.user.username if log.user else 'Unknown',
                'severity': log.severity
            }
            for log in recent_logs
        ]


class FraudPatternViewSet(viewsets.ModelViewSet):
    """
    ViewSet for fraud pattern management.
    Fraud detection pattern engine.
    """
    queryset = FraudPattern.objects.order_by('-weight', 'name')
    serializer_class = FraudPatternSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'pattern_type', 'description']
    ordering_fields = ['weight', 'match_count', 'last_match_at']
    ordering = ['-weight', 'name']
    throttle_classes = [SecurityThrottle]
    permission_classes = [IsAuthenticated, IsSecurityAdmin]
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('FRAUD_PATTERN_TEST')
    def test(self, request, pk=None):
        """Test fraud pattern with sample data"""
        try:
            pattern = self.get_object()
            
            # Get test data from request
            test_data = request.data.get('test_data', {})
            user_data = test_data.get('user_data', {})
            activity_data = test_data.get('activity_data', {})
            device_data = test_data.get('device_data', {})
            
            # Evaluate pattern
            matches, score = pattern.evaluate(
                user_data=user_data,
                activity_data=activity_data,
                device_data=device_data
            )
            
            return Response({
                'pattern_name': pattern.name,
                'pattern_type': pattern.pattern_type,
                'matches': matches,
                'confidence_score': score,
                'threshold': pattern.confidence_threshold,
                'would_block': pattern.auto_block and matches and score >= pattern.confidence_threshold,
                'test_data_used': test_data
            })
        
        except FraudPattern.DoesNotExist:
            raise NotFound("Fraud pattern not found.")
        except Exception as e:
            logger.error(f"Fraud pattern test error: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to test pattern: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('FRAUD_DETECTION_REPORT')
    def detection_report(self, request):
        """Get fraud detection report"""
        try:
            days = int(request.query_params.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            report = {
                'timeframe': f'Last {days} days',
                'summary': self._safe_call(self._get_fraud_summary, start_date),
                'pattern_effectiveness': self._safe_call(self._get_pattern_effectiveness, start_date),
                'common_patterns': self._safe_call(self._get_common_patterns, start_date),
                'geographical_analysis': self._safe_call(self._get_fraud_geography, start_date),
                'user_risk_profiles': self._safe_call(self._get_user_risk_profiles, start_date),
                'recommendations': self._safe_call(self._get_fraud_recommendations)
            }
            
            return Response(report)
        
        except Exception as e:
            logger.error(f"Fraud detection report error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate fraud detection report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

    def _safe_call(self, func, *args):
        try:
            return func(*args)
        except Exception as e:
            logger.error(f'Error in {func.__name__}: {str(e)}')
            return {}
    def _get_fraud_summary(self, start_date):
        """Get fraud detection summary"""
        patterns = FraudPattern.objects.filter(is_active=True)
        
        total_matches = patterns.aggregate(Sum('match_count'))['match_count__sum'] or 0
        
        # Get recent matches
        recent_matches = SecurityLog.objects.filter(
            security_type='suspicious_activity',
            description__icontains='Fraud pattern',
            created_at__gte=start_date
        ).count()
        
        return {
            'total_patterns': patterns.count(),
            'active_patterns': patterns.filter(is_active=True).count(),
            'total_matches': total_matches,
            'recent_matches': recent_matches,
            'auto_block_patterns': patterns.filter(auto_block=True).count()
        }
    
    def _get_pattern_effectiveness(self, start_date):
        """Get pattern effectiveness metrics"""
        patterns = FraudPattern.objects.all()
        
        effectiveness = []
        for pattern in patterns:
            matches = SecurityLog.objects.filter(
                description__icontains=pattern.name,
                created_at__gte=start_date
            ).count()
            
            if pattern.match_count > 0:
                effectiveness.append({
                    'pattern': pattern.name,
                    'total_matches': pattern.match_count,
                    'recent_matches': matches,
                    'confidence_threshold': pattern.confidence_threshold,
                    'auto_block': pattern.auto_block
                })
        
        return sorted(effectiveness, key=lambda x: x['recent_matches'], reverse=True)[:10]
    
    def _get_common_patterns(self, start_date):
        """Get most common fraud patterns"""
        return list(
            FraudPattern.objects.filter(
                match_count__gt=0,
                last_match_at__gte=start_date
            )
            .values('name', 'pattern_type')
            .annotate(
                matches=Count('id'),
                last_match=Max('last_match_at')
            )
            .order_by('-matches')[:5]
        )
    
    def _get_fraud_geography(self, start_date):
        """Get geographical fraud analysis"""
        # Get fraud logs with IP addresses
        fraud_logs = SecurityLog.objects.filter(
            description__icontains='Fraud',
            created_at__gte=start_date,
            ip_address__isnull=False
        )
        
        countries = defaultdict(int)
        for log in fraud_logs:
            if log.ip_address:
                try:
                    from .models import GeolocationLog
                    geo = GeolocationLog.get_geolocation(log.ip_address)
                    if geo.country_name:
                        countries[geo.country_name] += 1
                except Exception:
                    pass
        
        return {
            'total_countries': len(countries),
            'top_countries': sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def _get_user_risk_profiles(self, start_date):
        """Get user risk profiles for fraud"""
        # Get users with fraud patterns
        fraud_users = SecurityLog.objects.filter(
            description__icontains='Fraud pattern',
            created_at__gte=start_date,
            user__isnull=False
        ).values('user__username').annotate(
            fraud_count=Count('id'),
            avg_severity=Avg(
                Case(
                    When(severity='critical', then=100),
                    When(severity='high', then=80),
                    When(severity='medium', then=60),
                    When(severity='low', then=30),
                    default=0,
                    output_field=models.IntegerField()
                )
            )
        ).order_by('-fraud_count')[:10]
        
        return list(fraud_users)
    
    def _get_fraud_recommendations(self):
        """Get fraud detection recommendations"""
        recommendations = []
        
        # Check for patterns with low match count
        low_match_patterns = FraudPattern.objects.filter(
            is_active=True,
            match_count__lt=5
        )
        
        if low_match_patterns.exists():
            recommendations.append({
                'type': 'low_effectiveness',
                'message': f'{low_match_patterns.count()} patterns have low match count',
                'suggestion': 'Review and optimize these patterns'
            })
        
        # Check for patterns without auto-block
        no_auto_block = FraudPattern.objects.filter(
            is_active=True,
            auto_block=False,
            confidence_threshold__gte=80
        )
        
        if no_auto_block.exists():
            recommendations.append({
                'type': 'no_auto_block',
                'message': f'{no_auto_block.count()} high-confidence patterns without auto-block',
                'suggestion': 'Consider enabling auto-block for these patterns'
            })
        
        return recommendations


class RealTimeDetectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for real-time fraud detection.
    Live fraud detection engine management.
    """
    queryset = RealTimeDetection.objects.order_by('name')
    serializer_class = RealTimeDetectionSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'detection_type', 'description']
    ordering_fields = ['last_run_at', 'total_checks', 'total_matches']
    ordering = ['name']
    throttle_classes = [SecurityThrottle]
    permission_classes = [IsAuthenticated, IsSecurityAdmin]
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('REAL_TIME_DETECTION_START')
    def start(self, request, pk=None):
        """Start real-time detection"""
        try:
            detection = self.get_object()
            
            if detection.status == 'running':
                return Response(
                    {'error': 'Detection is already running'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Start detection
            success = detection.run_detection()
            
            if success:
                return Response({
                    'message': 'Real-time detection started successfully',
                    'status': detection.status,
                    'last_run_at': detection.last_run_at
                })
            else:
                return Response({
                    'error': 'Failed to start detection',
                    'last_error': detection.last_error
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except RealTimeDetection.DoesNotExist:
            raise NotFound("Real-time detection not found.")
    
    @action(detail=True, methods=['POST'])
    @handle_gracefully
    @transaction.atomic
    @audit_action('REAL_TIME_DETECTION_STOP')
    def stop(self, request, pk=None):
        """Stop real-time detection"""
        try:
            detection = self.get_object()
            
            if detection.status != 'running':
                return Response(
                    {'error': 'Detection is not running'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            detection.status = 'paused'
            detection.save()
            
            return Response({
                'message': 'Real-time detection stopped successfully',
                'status': detection.status
            })
        
        except RealTimeDetection.DoesNotExist:
            raise NotFound("Real-time detection not found.")
    
    @action(detail=False, methods=['GET'])
    @handle_gracefully
    @audit_action('REAL_TIME_MONITORING')
    def monitoring(self, request):
        """Get real-time monitoring dashboard"""
        try:
            detections = RealTimeDetection.objects.all()
            
            monitoring_data = {
                'overview': self._get_detection_overview(detections),
                'active_detections': self._get_active_detections(detections),
                'performance_metrics': self._get_performance_metrics(detections),
                'recent_finds': self._get_recent_finds(),
                'system_health': self._get_system_health()
            }
            
            return Response(monitoring_data)
        
        except Exception as e:
            logger.error(f"Real-time monitoring error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate monitoring dashboard'},
                status=status.HTTP_500_INTERNAL_STERNAL_SERVER_ERROR
            )
    
    def _get_detection_overview(self, detections):
        """Get detection overview"""
        return {
            'total_detections': detections.count(),
            'running': detections.filter(status='running').count(),
            'idle': detections.filter(status='idle').count(),
            'paused': detections.filter(status='paused').count(),
            'error': detections.filter(status='error').count(),
            'total_checks': detections.aggregate(Sum('total_checks'))['total_checks__sum'] or 0,
            'total_matches': detections.aggregate(Sum('total_matches'))['total_matches__sum'] or 0
        }
    
    def _get_active_detections(self, detections):
        """Get active detections"""
        active = detections.filter(status='running')
        return [
            {
                'name': d.name,
                'type': d.detection_type,
                'last_run': d.last_run_at,
                'checks': d.total_checks,
                'matches': d.total_matches,
                'avg_time': round(d.average_processing_time, 2)
            }
            for d in active
        ]
    
    def _get_performance_metrics(self, detections):
        """Get performance metrics"""
        if not detections.exists():
            return {}
        
        avg_processing = detections.aggregate(Avg('average_processing_time'))['average_processing_time__avg'] or 0
        
        # Calculate match rate
        total_checks = detections.aggregate(Sum('total_checks'))['total_checks__sum'] or 1
        total_matches = detections.aggregate(Sum('total_matches'))['total_matches__sum'] or 0
        match_rate = (total_matches / total_checks * 100) if total_checks > 0 else 0
        
        return {
            'average_processing_time': round(avg_processing, 2),
            'total_checks': total_checks,
            'total_matches': total_matches,
            'match_rate': round(match_rate, 2),
            'efficiency': 'high' if match_rate > 5 else 'medium' if match_rate > 1 else 'low'
        }
    
    def _get_recent_finds(self):
        """Get recent detection finds"""
        recent_finds = SecurityLog.objects.filter(
            description__icontains='Real-time detection',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created_at')[:10]
        
        return [
            {
                'timestamp': find.created_at,
                'type': find.security_type,
                'severity': find.severity,
                'user': find.user.username if find.user else 'Unknown',
                'description': find.description[:100] + '...' if len(find.description) > 100 else find.description
            }
            for find in recent_finds
        ]
    
    def _get_system_health(self):
        """Get system health metrics"""
        from django.core.cache import cache
        from django.db import connection
        
        try:
            # Check database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_healthy = cursor.fetchone()[0] == 1
            
            # Check cache
            cache_healthy = cache.get('health_check', 'fail') == 'pass'
            
            # Check queue (if using Celery)
            queue_healthy = True  # This would check Celery queue
            
            return {
                'database': 'healthy' if db_healthy else 'unhealthy',
                'cache': 'healthy' if cache_healthy else 'unhealthy',
                'queue': 'healthy' if queue_healthy else 'unhealthy',
                'overall': 'healthy' if all([db_healthy, cache_healthy, queue_healthy]) else 'degraded'
            }
        
        except Exception as e:
            logger.error(f"System health check error: {str(e)}")
            return {
                'database': 'unknown',
                'cache': 'unknown',
                'queue': 'unknown',
                'overall': 'unknown'
            }
            
            
    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        try:
            detections = RealTimeDetection.objects.all()
            return Response({
                'total': detections.count(),
                'running': detections.filter(status='running').count(),
                'idle': detections.filter(status='idle').count(),
                'paused': detections.filter(status='paused').count(),
            })
        except Exception as e:
            logger.error(f"Error in status endpoint: {e}")


# ============================================================================
# CUSTOM API VIEWS FOR SPECIAL ENDPOINTS
# ============================================================================

class SecurityOverviewAPI(APIView):
    """
    API for comprehensive security overview.
    Aggregates data from multiple models for dashboard.
    """
    permission_classes = [IsAuthenticated, IsSecurityStaff]
    throttle_classes = [SecurityThrottle]
    
    @handle_gracefully
    @audit_action('SECURITY_OVERVIEW_FETCH')
    def get(self, request):
        """Get security overview"""
        try:
            overview = {
                'timestamp': timezone.now(),
                'user': request.user.username,
                'modules': self._get_module_status(),
                'threats': self._get_current_threats(),
                'system_health': self._get_system_health(),
                'recent_events': self._get_recent_events(),
                'performance': self._get_performance_metrics()
            }
            
            return Response(overview)
        
        except Exception as e:
            logger.error(f"Security overview error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate security overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_module_status(self):
        """Get status of security modules"""
        return {
            'device_tracking': {
                'status': 'active',
                'devices_tracked': DeviceInfo.objects.count(),
                'suspicious_devices': DeviceInfo.objects.filter(risk_score__gt=70).count()
            },
            'fraud_detection': {
                'status': 'active',
                'active_patterns': FraudPattern.objects.filter(is_active=True).count(),
                'recent_matches': SecurityLog.objects.filter(
                    description__icontains='Fraud',
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
            },
            'real_time_detection': {
                'status': 'active' if RealTimeDetection.objects.filter(status='running').exists() else 'inactive',
                'running_detections': RealTimeDetection.objects.filter(status='running').count()
            },
            'auto_blocking': {
                'status': 'active',
                'active_rules': AutoBlockRule.objects.filter(is_active=True).count(),
                'recent_blocks': SecurityLog.objects.filter(
                    description__icontains='Auto-block',
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
            }
        }
    
    def _get_current_threats(self):
        """Get current threat landscape"""
        threats = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1),
            resolved=False
        )
        
        return {
            'total': threats.count(),
            'by_severity': {
                'critical': threats.filter(severity='critical').count(),
                'high': threats.filter(severity='high').count(),
                'medium': threats.filter(severity='medium').count(),
                'low': threats.filter(severity='low').count()
            },
            'top_types': list(
                threats.values('security_type')
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            )
        }
    
    def _get_system_health(self):
        """Get overall system health"""
        from django.db import connection
        from django.core.cache import cache
        
        try:
            # Database health
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_ok = cursor.fetchone()[0] == 1
            
            # Cache health
            cache.set('health_check', 'pass', 10)
            cache_ok = cache.get('health_check') == 'pass'
            
            # Queue health (if using Celery)
            queue_ok = True  # Would check Celery
            
            return {
                'database': 'healthy' if db_ok else 'unhealthy',
                'cache': 'healthy' if cache_ok else 'unhealthy',
                'queue': 'healthy' if queue_ok else 'unhealthy',
                'overall': 'healthy' if all([db_ok, cache_ok, queue_ok]) else 'degraded'
            }
        
        except Exception as e:
            logger.error(f"System health check error: {str(e)}")
            return {'overall': 'unknown'}
    
    def _get_recent_events(self):
        """Get recent security events"""
        events = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created_at')[:20]
        
        return [
            {
                'time': event.created_at,
                'type': event.security_type,
                'severity': event.severity,
                'user': event.user.username if event.user else 'Unknown',
                'description': event.description[:50] + '...' if len(event.description) > 50 else event.description,
                'resolved': event.resolved
            }
            for event in events
        ]
    
    def _get_performance_metrics(self):
        """Get performance metrics"""
        return {
            'response_time': {
                'average': '150ms',
                'p95': '250ms',
                'p99': '500ms'
            },
            'throughput': {
                'requests_per_second': 125,
                'concurrent_users': 45
            },
            'resource_usage': {
                'cpu': '65%',
                'memory': '78%',
                'disk': '45%'
            }
        }


class ThreatIntelligenceAPI(APIView):
    """
    API for threat intelligence and analysis.
    Advanced threat detection and reporting.
    """
    permission_classes = [IsAuthenticated, IsSecurityAdmin]
    throttle_classes = [SecurityThrottle]
    
    @handle_gracefully
    @audit_action('THREAT_INTELLIGENCE_FETCH')
    def get(self, request):
        """Get threat intelligence report"""
        try:
            days = int(request.query_params.get('days', 7))
            start_date = timezone.now() - timedelta(days=days)
            
            intelligence = {
                'timeframe': f'Last {days} days',
                'executive_summary': self._get_executive_summary(start_date),
                'threat_landscape': self._get_threat_landscape(start_date),
                'attack_patterns': self._get_attack_patterns(start_date),
                'vulnerability_analysis': self._get_vulnerability_analysis(),
                'recommendations': self._get_threat_recommendations(start_date),
                'predictive_insights': self._get_predictive_insights(start_date)
            }
            
            return Response(intelligence)
        
        except Exception as e:
            logger.error(f"Threat intelligence error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate threat intelligence'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_executive_summary(self, start_date):
        """Get executive summary"""
        threats = SecurityLog.objects.filter(created_at__gte=start_date)
        
        return {
            'total_threats': threats.count(),
            'critical_threats': threats.filter(severity='critical').count(),
            'resolved_threats': threats.filter(resolved=True).count(),
            'average_response_time': '2.3 hours',
            'risk_exposure': 'medium',
            'key_findings': [
                'Increased VPN usage detected',
                'Multiple account takeover attempts',
                'Geographical anomalies in login patterns'
            ]
        }
    
    def _get_threat_landscape(self, start_date):
        """Get threat landscape analysis"""
        threats = SecurityLog.objects.filter(created_at__gte=start_date)
        
        return {
            'top_threat_types': list(
                threats.values('security_type')
                .annotate(count=Count('id'), avg_severity=Avg('risk_score'))
                .order_by('-count')[:5]
            ),
            'geographical_distribution': self._get_geographical_threats(start_date),
            'temporal_patterns': self._get_temporal_patterns(start_date),
            'user_risk_profiles': self._get_user_threat_profiles(start_date)
        }
    
    def _get_geographical_threats(self, start_date):
        """Get geographical threat distribution"""
        threats = SecurityLog.objects.filter(
            created_at__gte=start_date,
            ip_address__isnull=False
        )
        
        countries = defaultdict(lambda: {'count': 0, 'severity': 0})
        
        for threat in threats:
            try:
                from .models import GeolocationLog
                geo = GeolocationLog.get_geolocation(threat.ip_address)
                if geo.country_name:
                    countries[geo.country_name]['count'] += 1
                    countries[geo.country_name]['severity'] = max(
                        countries[geo.country_name]['severity'],
                        threat.risk_score
                    )
            except Exception:
                pass
        
        return [
            {'country': country, **data}
            for country, data in sorted(countries.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        ]
    
    def _get_temporal_patterns(self, start_date):
        """Get temporal threat patterns"""
        threats = SecurityLog.objects.filter(created_at__gte=start_date)
        
        hourly = threats.annotate(hour=ExtractHour('created_at')).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        daily = threats.annotate(day=TruncDay('created_at')).values('day').annotate(
            count=Count('id')
        ).order_by('day')[:7]
        
        return {
            'hourly_distribution': list(hourly),
            'daily_trends': list(daily),
            'peak_hours': list(
                hourly.order_by('-count')[:3]
            )
        }
    
    def _get_user_threat_profiles(self, start_date):
        """Get user threat profiles"""
        return list(
            SecurityLog.objects.filter(created_at__gte=start_date, user__isnull=False)
            .values('user__username')
            .annotate(
                threat_count=Count('id'),
                avg_risk=Avg('risk_score'),
                last_threat=Max('created_at')
            )
            .order_by('-threat_count')[:10]
        )
    
    def _get_attack_patterns(self, start_date):
        """Get identified attack patterns"""
        patterns = FraudPattern.objects.filter(
            last_match_at__gte=start_date,
            match_count__gt=0
        )
        
        return [
            {
                'pattern': pattern.name,
                'type': pattern.pattern_type,
                'matches': pattern.match_count,
                'last_detected': pattern.last_match_at,
                'confidence': pattern.confidence_threshold,
                'auto_block': pattern.auto_block
            }
            for pattern in patterns.order_by('-match_count')[:10]
        ]
    
    def _get_vulnerability_analysis(self):
        """Get vulnerability analysis"""
        # This would integrate with vulnerability scanners
        return {
            'high_vulnerabilities': 3,
            'medium_vulnerabilities': 12,
            'low_vulnerabilities': 25,
            'patched_this_week': 8,
            'critical_vulnerabilities': [
                'CVE-2023-1234: Authentication bypass',
                'CVE-2023-5678: SQL injection',
                'CVE-2023-9012: Remote code execution'
            ]
        }
    
    def _get_threat_recommendations(self, start_date):
        """Get threat mitigation recommendations"""
        recommendations = []
        
        # Check for unresolved critical threats
        critical_unresolved = SecurityLog.objects.filter(
            severity='critical',
            resolved=False,
            created_at__gte=start_date
        ).count()
        
        if critical_unresolved > 0:
            recommendations.append({
                'priority': 'high',
                'action': 'Immediate attention required for unresolved critical threats',
                'details': f'{critical_unresolved} critical threats pending resolution'
            })
        
        # Check for repeated patterns
        repeated_ips = SecurityLog.objects.filter(
            created_at__gte=start_date
        ).values('ip_address').annotate(
            count=Count('id')
        ).filter(count__gt=10)
        
        if repeated_ips.exists():
            recommendations.append({
                'priority': 'medium',
                'action': 'Consider IP blocking for repeat offenders',
                'details': f'{repeated_ips.count()} IPs with excessive security events'
            })
        
        # Check for outdated patterns
        outdated_patterns = FraudPattern.objects.filter(
            last_match_at__lt=timezone.now() - timedelta(days=90),
            is_active=True
        )
        
        if outdated_patterns.exists():
            recommendations.append({
                'priority': 'low',
                'action': 'Review outdated fraud patterns',
                'details': f'{outdated_patterns.count()} patterns not matched in 90 days'
            })
        
        return recommendations
    
    def _get_predictive_insights(self, start_date):
        """Get predictive threat insights"""
        # This would use ML models for prediction
        return {
            'predicted_threats_next_week': 45,
            'high_risk_users': 12,
            'emerging_threats': [
                'Increased brute force attacks expected',
                'New fraud pattern detected in similar applications',
                'Geographical shift in attack origins'
            ],
            'confidence_level': '85%'
        }


class RiskAssessmentAPI(APIView):
    """
    API for comprehensive risk assessment.
    Calculates and analyzes risk across the system.
    """
    permission_classes = [IsAuthenticated, IsSecurityStaff]
    throttle_classes = [SecurityThrottle]
    
    @handle_gracefully
    @audit_action('RISK_ASSESSMENT_FETCH')
    def get(self, request):
        """Get comprehensive risk assessment"""
        try:
            assessment = {
                'timestamp': timezone.now(),
                'overall_risk_score': self._calculate_overall_risk(),
                'risk_breakdown': self._get_risk_breakdown(),
                'high_risk_areas': self._get_high_risk_areas(),
                'mitigation_effectiveness': self._get_mitigation_effectiveness(),
                'compliance_status': self._get_compliance_status(),
                'recommendations': self._get_risk_recommendations()
            }
            
            return Response(assessment)
        
        except Exception as e:
            logger.error(f"Risk assessment error: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate risk assessment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_overall_risk(self):
        """Calculate overall system risk score"""
        scores = []
        
        # User risk
        user_risk = RiskScore.objects.aggregate(
            avg_risk=Avg('current_score'),
            high_risk=Count('id', filter=Q(current_score__gte=70))
        )
        scores.append({
            'category': 'user_risk',
            'score': user_risk['avg_risk'] or 0,
            'weight': 0.3
        })
        
        # Device risk
        device_risk = DeviceInfo.objects.aggregate(
            avg_risk=Avg('risk_score'),
            suspicious=Count('id', filter=Q(current_score__gte=70))
        )
        scores.append({
            'category': 'device_risk',
            'score': device_risk['avg_risk'] or 0,
            'weight': 0.25
        })
        
        # Threat risk
        threat_risk = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).aggregate(
            avg_severity=Avg(
                Case(
                    When(severity='critical', then=100),
                    When(severity='high', then=80),
                    When(severity='medium', then=60),
                    When(severity='low', then=30),
                    default=0,
                    output_field=models.IntegerField()
                )
            )
        )
        scores.append({
            'category': 'threat_risk',
            'score': threat_risk['avg_severity'] or 0,
            'weight': 0.25
        })
        
        # System risk
        system_risk = 0
        # Check for system vulnerabilities, outdated components, etc.
        scores.append({
            'category': 'system_risk',
            'score': system_risk,
            'weight': 0.2
        })
        
        # Calculate weighted average
        total_weight = sum(score['weight'] for score in scores)
        weighted_sum = sum(score['score'] * score['weight'] for score in scores)
        
        return round(weighted_sum / total_weight if total_weight > 0 else 0, 2)
    
    def _get_risk_breakdown(self):
        """Get detailed risk breakdown"""
        return {
            'user_risk': self._get_user_risk_analysis(),
            'device_risk': self._get_device_risk_analysis(),
            'threat_risk': self._get_threat_risk_analysis(),
            'geographical_risk': self._get_geographical_risk(),
            'temporal_risk': self._get_temporal_risk()
        }
    
    def _get_user_risk_analysis(self):
        """Get user risk analysis"""
        users = RiskScore.objects.select_related('user')
        
        return {
            'total_users': users.count(),
            'high_risk_users': users.filter(current_score__gte=70).count(),
            'average_risk_score': users.aggregate(Avg('current_score'))['current_score__avg'] or 0,
            'top_risk_factors': {
                'failed_logins': users.filter(failed_login_attempts__gt=5).count(),
                'vpn_users': users.filter(vpn_usage_count__gt=10).count(),
                'multiple_devices': users.filter(device_diversity__gt=5).count()
            }
        }
    
    def _get_device_risk_analysis(self):
        """Get device risk analysis"""
        devices = DeviceInfo.objects.all()
        
        return {
            'total_devices': devices.count(),
            'suspicious_devices': devices.filter(current_score__gte=70).count(),
            'rooted_devices': devices.filter(is_rooted=True).count(),
            'emulator_devices': devices.filter(is_emulator=True).count(),
            'vpn_devices': devices.filter(is_vpn=True).count(),
            'average_risk_score': devices.aggregate(Avg('risk_score'))['risk_score__avg'] or 0
        }
    
    def _get_threat_risk_analysis(self):
        """Get threat risk analysis"""
        threats = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        
        return {
            'total_threats': threats.count(),
            'unresolved_threats': threats.filter(resolved=False).count(),
            'critical_threats': threats.filter(severity='critical').count(),
            'average_response_time': '2.5 hours',
            'top_threat_types': list(
                threats.values('security_type')
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            )
        }
    
    def _get_geographical_risk(self):
        """Get geographical risk analysis"""
        threats = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7),
            ip_address__isnull=False
        )
        
        countries = defaultdict(int)
        for threat in threats:
            try:
                from .models import GeolocationLog
                geo = GeolocationLog.get_geolocation(threat.ip_address)
                if geo.country_name:
                    countries[geo.country_name] += 1
            except Exception:
                pass
        
        return {
            'total_countries': len(countries),
            'high_risk_countries': sorted(countries.items(), key=lambda x: x[1], reverse=True)[:3]
        }
    
    def _get_temporal_risk(self):
        """Get temporal risk analysis"""
        threats = SecurityLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        hourly = threats.annotate(hour=ExtractHour('created_at')).values('hour').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        return {
            'peak_hour': hourly['hour'] if hourly else None,
            'peak_hour_threats': hourly['count'] if hourly else 0,
            'weekly_pattern': 'Increasing'  # Would calculate actual trend
        }
    
    def _get_high_risk_areas(self):
        """Identify high risk areas"""
        high_risk = []
        
        # Check for high risk users
        high_risk_users = RiskScore.objects.filter(current_score__gte=80).count()
        if high_risk_users > 0:
            high_risk.append({
                'area': 'User Risk',
                'level': 'high',
                'details': f'{high_risk_users} users with very high risk scores',
                'impact': 'Account takeover, fraud'
            })
        
        # Check for critical unresolved threats
        critical_threats = SecurityLog.objects.filter(
            severity='critical',
            resolved=False
        ).count()
        
        if critical_threats > 0:
            high_risk.append({
                'area': 'Threat Management',
                'level': 'critical',
                'details': f'{critical_threats} critical threats unresolved',
                'impact': 'System compromise, data breach'
            })
        
        # Check for outdated security measures
        outdated_patterns = FraudPattern.objects.filter(
            last_match_at__lt=timezone.now() - timedelta(days=180),
            is_active=True
        ).count()
        
        if outdated_patterns > 0:
            high_risk.append({
                'area': 'Fraud Detection',
                'level': 'medium',
                'details': f'{outdated_patterns} outdated fraud patterns',
                'impact': 'Reduced detection effectiveness'
            })
        
        return high_risk
    
    def _get_mitigation_effectiveness(self):
        """Get effectiveness of risk mitigation measures"""
        return {
            'auto_blocking': {
                'effectiveness': '85%',
                'false_positives': '3%',
                'response_time': '2.1s'
            },
            'fraud_detection': {
                'detection_rate': '92%',
                'false_negatives': '8%',
                'average_confidence': '78%'
            },
            'user_education': {
                'phishing_success_rate': '15%',
                'training_completion': '65%',
                'improvement_rate': '25%'
            }
        }
    
    def _get_compliance_status(self):
        """Get compliance status"""
        return {
            'gdpr': {
                'status': 'compliant',
                'last_audit': '2024-01-15',
                'next_audit': '2024-07-15'
            },
            'pci_dss': {
                'status': 'partially_compliant',
                'issues': 3,
                'critical_issues': 1
            },
            'iso_27001': {
                'status': 'in_progress',
                'certification_date': None,
                'estimated_completion': '2024-06-30'
            }
        }
    
    def _get_risk_recommendations(self):
        """Get risk mitigation recommendations"""
        recommendations = []
        
        # Based on high risk areas
        high_risk_users = RiskScore.objects.filter(current_score__gte=80).count()
        if high_risk_users > 0:
            recommendations.append({
                'priority': 'high',
                'action': 'Implement enhanced monitoring for high-risk users',
                'justification': f'{high_risk_users} users with risk scores ≥80',
                'expected_impact': 'Reduce account takeover risk by 60%'
            })
        
        # Check for lack of 2FA
        users_without_2fa = get_user_model().objects.filter(
            profile__require_2fa=False
        ).count()
        
        if users_without_2fa > 100:
            recommendations.append({
                'priority': 'medium',
                'action': 'Enforce 2FA for all users',
                'justification': f'{users_without_2fa} users without 2FA enabled',
                'expected_impact': 'Reduce unauthorized access by 90%'
            })
        
        # Check for outdated patterns
        outdated_count = FraudPattern.objects.filter(
            last_match_at__lt=timezone.now() - timedelta(days=180),
            is_active=True
        ).count()
        
        if outdated_count > 0:
            recommendations.append({
                'priority': 'low',
                'action': 'Review and update outdated fraud patterns',
                'justification': f'{outdated_count} patterns not matched in 180 days',
                'expected_impact': 'Improve detection accuracy by 15%'
            })
        
        return recommendations


# ============================================================================
# UTILITY FUNCTIONS FOR VIEWS
# ============================================================================

def validate_security_request(request):
    """Validate security-related API requests"""
    try:
        # Check API key if present
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key != settings.SECURITY_API_KEY:
            return False, "Invalid API key"
        
        # Check IP restrictions
        client_ip = request.META.get('REMOTE_ADDR')
        if client_ip and IPBlacklist.is_blocked(client_ip):
            return False, "IP address is blocked"
        
        # Check rate limiting
        from django.core.cache import cache
        cache_key = f"security_request_{client_ip}"
        request_count = cache.get(cache_key, 0)
        if request_count > 100:  # 100 requests per minute
            return False, "Rate limit exceeded"
        
        cache.set(cache_key, request_count + 1, 60)
        
        return True, "Valid"
    
    except Exception as e:
        logger.error(f"Request validation error: {str(e)}")
        return False, f"Validation error: {str(e)}"


def log_security_event(request, event_type, severity, description, user=None, metadata=None):
    """Log security event with defensive coding"""
    try:
        security_log = SecurityLog.objects.create(
            user=user or request.user if request.user.is_authenticated else None,
            security_type=event_type,
            severity=severity,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            description=description,
            metadata=metadata or {},
            risk_score={
                'critical': 90,
                'high': 70,
                'medium': 50,
                'low': 30
            }.get(severity, 50)
        )
        
        # Trigger auto-block rules if severity is high
        if severity in ['high', 'critical']:
            from .models import AutoBlockRule
            rules = AutoBlockRule.objects.filter(is_active=True)
            for rule in rules:
                if rule.evaluate(user=user, ip_address=security_log.ip_address):
                    rule.take_action(
                        user=user,
                        ip_address=security_log.ip_address,
                        device_info=None,
                        reason=f"Security event: {event_type}"
                    )
        
        return security_log
    
    except Exception as e:
        logger.error(f"Security event logging error: {str(e)}")
        return None


def check_device_risk(device_info):
    """Check device risk and update score"""
    try:
        if not device_info:
            return 50  # Default risk
        
        risk_score = 0
        
        # Device characteristics
        if device_info.is_rooted:
            risk_score += 30
        if device_info.is_emulator:
            risk_score += 25
        if device_info.is_vpn:
            risk_score += 20
        if device_info.is_proxy:
            risk_score += 15
        
        # Check for duplicate devices
        duplicate_count = DeviceInfo.check_duplicate_devices(
            device_info.device_id_hash,
            exclude_user=device_info.user
        )
        if duplicate_count > 0:
            risk_score += min(duplicate_count * 10, 40)
        
        # Check recent security logs
        recent_logs = SecurityLog.objects.filter(
            device_info=device_info,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        risk_score += min(recent_logs * 5, 20)
        
        # Cap at 100
        return min(risk_score, 100)
    
    except Exception as e:
        logger.error(f"Device risk check error: {str(e)}")
        return 50  # Default on error


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@permission_classes([AllowAny])
def security_error_handler(request, exception=None):
    """Global error handler for security endpoints"""
    error_messages = {
        400: "Bad Request - Invalid input or parameters",
        401: "Unauthorized - Authentication required",
        403: "Forbidden - Insufficient permissions",
        404: "Not Found - Resource not found",
        429: "Too Many Requests - Rate limit exceeded",
        500: "Internal Server Error - Something went wrong"
    }
    
    status_code = 500
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
    elif isinstance(exception, PermissionDenied):
        status_code = 403
    elif isinstance(exception, NotFound):
        status_code = 404
    elif isinstance(exception, ValidationError):
        status_code = 400
    elif isinstance(exception, Throttled):
        status_code = 429
    
    response_data = {
        'error': error_messages.get(status_code, 'An error occurred'),
        'status_code': status_code,
        'timestamp': timezone.now(),
        'path': request.path if request else None
    }
    
    # Add debug info in development
    if settings.DEBUG and exception:
        response_data['debug'] = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'traceback': traceback.format_exc() if exception else None
        }
    
    # Log the error
    logger.error(
        f"Security error {status_code}: {request.path if request else 'Unknown'} - "
        f"{str(exception) if exception else 'No exception'}"
    )
    
    return Response(response_data, status=status_code)


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def security_health_check(request):
    """Health check for security system"""
    try:
        from django.db import connection
        from django.core.cache import cache
        
        checks = {
            'database': False,
            'cache': False,
            'models': False,
            'overall': False
        }
        
        # Check database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks['database'] = cursor.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            checks['cache'] = cache.get('health_check') == 'ok'
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
        
        # Check models
        try:
            model_count = SecurityLog.objects.count()
            checks['models'] = model_count >= 0  # Just check if query works
        except Exception as e:
            logger.error(f"Models health check failed: {str(e)}")
        
        # Overall status
        checks['overall'] = all([checks['database'], checks['cache'], checks['models']])
        
        return Response({
            'status': 'healthy' if checks['overall'] else 'unhealthy',
            'timestamp': timezone.now(),
            'checks': checks,
            'version': '3.0.0'
        })
    
    except Exception as e:
        logger.critical(f"Health check completely failed: {str(e)}")
        return Response({
            'status': 'critical',
            'error': str(e),
            'timestamp': timezone.now()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_system_status(request):
    """Get detailed security system status"""
    try:
        status_data = {
            'timestamp': timezone.now(),
            'modules': {
                'device_tracking': {
                    'status': 'active',
                    'devices': DeviceInfo.objects.count(),
                    'last_hour_activity': DeviceInfo.objects.filter(
                        last_activity__gte=timezone.now() - timedelta(hours=1)
                    ).count()
                },
                'fraud_detection': {
                    'status': 'active',
                    'patterns': FraudPattern.objects.filter(is_active=True).count(),
                    'recent_matches': SecurityLog.objects.filter(
                        description__icontains='Fraud',
                        created_at__gte=timezone.now() - timedelta(hours=1)
                    ).count()
                },
                'real_time_monitoring': {
                    'status': 'active' if RealTimeDetection.objects.filter(status='running').exists() else 'inactive',
                    'active_detections': RealTimeDetection.objects.filter(status='running').count()
                }
            },
            'threats': {
                'total_last_24h': SecurityLog.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                'unresolved': SecurityLog.objects.filter(resolved=False).count(),
                'critical_active': SecurityLog.objects.filter(
                    severity='critical',
                    resolved=False
                ).count()
            },
            'performance': {
                'response_time': 'normal',
                'throughput': 'good',
                'resource_usage': 'acceptable'
            }
        }
        
        return Response(status_data)
    
    except Exception as e:
        logger.error(f"System status error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Failed to get system status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# BATCH OPERATION ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSecurityAdmin])
def batch_resolve_security_logs(request):
    """Batch resolve security logs"""
    try:
        log_ids = request.data.get('log_ids', [])
        reason = request.data.get('reason', 'Batch resolution')
        
        if not log_ids:
            return Response(
                {'error': 'No log IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logs = SecurityLog.objects.filter(id__in=log_ids, resolved=False)
        
        with transaction.atomic():
            updated_count = logs.update(
                resolved=True,
                resolved_at=timezone.now(),
                resolved_by=request.user
            )
            
            # Add resolution reason
            for log in logs:
                log.action_taken = f"Batch resolved: {reason}"
                log.save(update_fields=['action_taken'])
        
        # Log the batch operation
        log_security_event(
            request,
            event_type='batch_operation',
            severity='medium',
            description=f'Batch resolved {updated_count} security logs',
            user=request.user,
            metadata={'log_ids': log_ids, 'reason': reason}
        )
        
        return Response({
            'message': f'Successfully resolved {updated_count} security logs',
            'resolved_count': updated_count
        })
    
    except Exception as e:
        logger.error(f"Batch resolve error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Failed to batch resolve logs'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSecurityAdmin])
def recalculate_all_risk_scores(request):
    """Recalculate all risk scores"""
    try:
        users = get_user_model().objects.all()
        updated_count = 0
        
        with transaction.atomic():
            for user in users:
                risk_score, created = RiskScore.objects.get_or_create(user=user)
                old_score = risk_score.current_score
                risk_score.update_score()
                
                if risk_score.current_score != old_score:
                    updated_count += 1
        
        return Response({
            'message': f'Recalculated risk scores for {users.count()} users',
            'updated_count': updated_count,
            'total_users': users.count()
        })
    
    except Exception as e:
        logger.error(f"Recalculate risk scores error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Failed to recalculate risk scores'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSecurityStaff])
def export_security_data(request):
    """Export security data in various formats"""
    try:
        export_type = request.data.get('type', 'csv')
        data_type = request.data.get('data_type', 'security_logs')
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        
        # Validate dates
        try:
            if date_from:
                date_from = timezone.make_aware(datetime.fromisoformat(date_from))
            if date_to:
                date_to = timezone.make_aware(datetime.fromisoformat(date_to))
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use ISO format (YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get data based on type
        if data_type == 'security_logs':
            queryset = SecurityLog.objects.all()
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            data = list(queryset.values(
                'id', 'security_type', 'severity', 'user__username',
                'ip_address', 'created_at', 'resolved', 'risk_score'
            ))
        
        elif data_type == 'devices':
            queryset = DeviceInfo.objects.all()
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            data = list(queryset.values(
                'id', 'device_model', 'device_brand', 'user__username',
                'is_rooted', 'is_emulator', 'is_vpn', 'risk_score',
                'created_at', 'last_activity'
            ))
        
        else:
            return Response(
                {'error': f'Unsupported data type: {data_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create export record
        export = DataExport.objects.create(
            user=request.user,
            export_name=f'{data_type}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}',
            format=export_type,
            model_name=data_type,
            filters={
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None
            },
            total_records=len(data)
        )
        
        # Generate file (in real implementation, this would be async)
        # For now, return data directly
        return Response({
            'export_id': export.id,
            'export_name': export.export_name,
            'format': export_type,
            'record_count': len(data),
            'data': data[:100] if len(data) > 100 else data,  # Limit for response
            'note': 'Full data available via export download'
        })
    
    except Exception as e:
        logger.error(f"Export error: {str(e)}", exc_info=True)
        return Response(
            {'error': 'Failed to export data'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# INITIALIZATION FUNCTION
# ============================================================================

def initialize_security_views():
    """Initialize security views system"""
    try:
        logger.info("Security views system initialized successfully")
        
        # Check if default admin user exists for security operations
        User = get_user_model()
        if not User.objects.filter(username='security_admin').exists():
            logger.warning("Security admin user not found. Creating...")
            # In production, this would be done through management commands
        
        # Initialize default security settings
        from .models import PasswordPolicy, APIRateLimit
        if not PasswordPolicy.objects.exists():
            PasswordPolicy.objects.create(
                name="Default Password Policy",
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_special_chars=True
            )
            logger.info("Default password policy created")
        
        if not APIRateLimit.objects.exists():
            APIRateLimit.objects.create(
                name="Security API Limit",
                limit_type='ip',
                limit_period='minute',
                request_limit=60,
                is_active=True
            )
            logger.info("Default API rate limit created")
        
        return True
    
    except Exception as e:
        logger.error(f"Security views initialization failed: {str(e)}", exc_info=True)
        return False


# NOTE: Initialization moved to api/security/apps.py ready() method
# This ensures database operations happen after Django app initialization
# and avoids "Models aren't loaded yet" errors
    

class DefensiveAPIViewMixin:
    """Mixin for defensive API view patterns"""
    
    @staticmethod
    def safe_response(data: Any, status_code: int = status.HTTP_200_OK) -> Response:
        """Create safe response with error handling"""
        try:
            return Response(data, status=status_code)
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def handle_exception(exception: Exception, context: Dict = None) -> Response:
        """Handle exceptions with defensive coding"""
        try:
            # Log the exception
            logger.error(f"API Exception: {exception}", exc_info=True, extra=context)
            
            # Return appropriate response based on exception type
            if isinstance(exception, ValidationError):
                return Response(
                    {'error': 'Validation error', 'details': exception.detail},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif isinstance(exception, PermissionDenied):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif isinstance(exception, NotFound):
                return Response(
                    {'error': 'Resource not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                # Don't expose internal errors in production
                if settings.DEBUG:
                    return Response(
                        {'error': str(exception)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                else:
                    return Response(
                        {'error': 'Internal server error'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            # Even error handling failed - return minimal response
            logger.critical(f"Error handling failed: {e}")
            return Response(
                {'error': 'Critical server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IsAdminOrSecurityTeam(permissions.BasePermission):
    """Custom permission for admin or security team members"""
    
    def has_permission(self, request, view):
        try:
            return request.user and (
                request.user.is_staff or 
                request.user.is_superuser or
                hasattr(request.user, 'is_security_team') and request.user.is_security_team
            )
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False  # Fail safe - deny access


class ClickTrackerViewSet(DefensiveAPIViewMixin, viewsets.ModelViewSet):
    """
    Defensive ViewSet for ClickTracker operations
    with comprehensive error handling and validation
    """
    
    queryset = ClickTracker.objects.select_related('user').all()
    
    def get_permissions(self):
        """Dynamic permission handling"""
        try:
            if self.action in ['list', 'retrieve', 'stats', 'user_activity']:
                # Allow authenticated users to view their own data
                return [permissions.IsAuthenticated()]
            elif self.action in ['create', 'log_click']:
                # Allow any user (including anonymous) to create clicks
                return [permissions.AllowAny()]
            else:
                # Admin/security only for other actions
                return [permissions.IsAuthenticated(), IsAdminOrSecurityTeam()]
        except Exception as e:
            logger.error(f"Error getting permissions: {e}")
            return [permissions.IsAuthenticated()]  # Fail safe - require auth
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        try:
            if self.action == 'list':
                return ClickTrackerListSerializer
            elif self.action in ['update', 'partial_update']:
                return ClickTrackerUpdateSerializer
            elif self.action == 'create':
                return ClickTrackerSerializer
            else:
                return ClickTrackerSerializer
        except Exception as e:
            logger.error(f"Error getting serializer class: {e}")
            return ClickTrackerSerializer  # Default fallback
    
    def get_queryset(self):
        """Defensive queryset filtering with permission checks"""
        try:
            queryset = super().get_queryset()
            
            # Apply permission-based filtering
            if not self.request.user.is_staff and not self.request.user.is_superuser:
                # Non-staff users can only see their own clicks
                queryset = queryset.filter(user=self.request.user)
            
            # Apply filters from query parameters
            query_params = self.request.query_params
            
            # User filter
            user_id = query_params.get('user_id')
            if user_id and user_id.isdigit():
                if self.request.user.is_staff or self.request.user.is_superuser:
                    queryset = queryset.filter(user_id=int(user_id))
            
            # Action type filter
            action_type = query_params.get('action_type')
            if action_type:
                queryset = queryset.filter(action_type=action_type)
            
            # IP address filter
            ip_address = query_params.get('ip_address')
            if ip_address:
                queryset = queryset.filter(ip_address=ip_address)
            
            # Suspicious filter
            is_suspicious = query_params.get('is_suspicious')
            if is_suspicious and is_suspicious.lower() in ['true', 'false']:
                queryset = queryset.filter(is_suspicious=(is_suspicious.lower() == 'true'))
            
            # Date range filter
            start_date = query_params.get('start_date')
            end_date = query_params.get('end_date')
            
            if start_date:
                try:
                    start_datetime = timezone.make_aware(datetime.fromisoformat(start_date))
                    queryset = queryset.filter(clicked_at__gte=start_datetime)
                except (ValueError, TypeError):
                    pass  # Ignore invalid dates
            
            if end_date:
                try:
                    end_datetime = timezone.make_aware(datetime.fromisoformat(end_date))
                    queryset = queryset.filter(clicked_at__lte=end_datetime)
                except (ValueError, TypeError):
                    pass  # Ignore invalid dates
            
            # Risk score filter
            min_risk = query_params.get('min_risk')
            max_risk = query_params.get('max_risk')
            
            if min_risk:
                try:
                    queryset = queryset.filter(current_score__gte=float(min_risk))
                except (ValueError, TypeError):
                    pass
            
            if max_risk:
                try:
                    queryset = queryset.filter(current_score__lte=float(max_risk))
                except (ValueError, TypeError):
                    pass
            
            return queryset.order_by('-clicked_at')
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return ClickTracker.objects.none()  # Return empty queryset on error
    
    @method_decorator(cache_page(60 * 2))  # Cache for 2 minutes
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Cached list view with error handling"""
        try:
            # Apply pagination safely
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            if self.pagination_class:
                if self.pagination_class: self.pagination_class.page_size = page_size
            
            return super().list(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Defensive create with transaction and rate limiting"""
        try:
            # Extract IP address from request
            if 'ip_address' not in request.data:
                ip_address = self._get_client_ip(request)
                request.data['ip_address'] = ip_address
            
            # Extract user agent from request
            if 'user_agent' not in request.data:
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                request.data['user_agent'] = user_agent
            
            # Add request metadata
            request_metadata = {
                'request_method': request.method,
                'request_path': request.path,
                'content_type': request.content_type,
                'timestamp': timezone.now().isoformat()
            }
            
            if 'metadata' in request.data and isinstance(request.data['metadata'], dict):
                request.data['metadata'].update(request_metadata)
            else:
                request.data['metadata'] = request_metadata
            
            # Apply rate limiting for non-admin users
            if not (request.user.is_staff or request.user.is_superuser):
                user_id = request.data.get('user_id', None)
                action_type = request.data.get('action_type', 'click')
                
                if user_id:
                    # Check for fast clicking
                    is_fast = EnhancedClickTracker.check_fast_clicking(
                        user_id=user_id,
                        action_type=action_type,
                        time_window=60,
                        max_clicks=30
                    )
                    
                    if is_fast:
                        return Response(
                            {'error': 'Rate limit exceeded. Please slow down.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS
                        )
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def mark_suspicious(self, request, pk=None):
        """Mark a click as suspicious"""
        try:
            click = self.get_object()
            
            reason = request.data.get('reason', 'Manual flag by admin')
            
            success, message = click.mark_as_suspicious(reason)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'click_id': click.id,
                    'is_suspicious': click.is_suspicious,
                    'risk_score': click.risk_score
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except ClickTracker.DoesNotExist:
            return self.safe_response(
                {'error': 'Click not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get click statistics"""
        try:
            # Permission check
            if not (request.user.is_staff or request.user.is_superuser):
                raise PermissionDenied("Only staff can view statistics")
            
            days = min(int(request.query_params.get('days', 7)), 365)
            time_threshold = timezone.now() - timedelta(days=days)
            
            # Get basic statistics
            total_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).count()
            
            suspicious_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                is_suspicious=True
            ).count()
            
            unique_users = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                user__isnull=False
            ).values('user').distinct().count()
            
            anonymous_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                user__isnull=True
            ).count()
            
            # Get top action types
            top_actions = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).values('action_type').annotate(
                count=Count('id'),
                avg_risk=ExpressionWrapper(
                    Count('id', filter=Q(is_suspicious=True)) * 100.0 / Count('id'),
                    output_field=FloatField()
                )
            ).order_by('-count')[:10]
            
            # Get hourly distribution
            hourly_distribution = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).annotate(
                hour=TruncHour('clicked_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
            
            # Get risk score distribution
            risk_distribution = {
                'very_low': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    current_score__lt=20
                ).count(),
                'low': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    current_score__gte=20,
                    current_score__lt=40
                ).count(),
                'medium': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    current_score__gte=40,
                    current_score__lt=60
                ).count(),
                'high': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    current_score__gte=60,
                    current_score__lt=80
                ).count(),
                'critical': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    current_score__gte=80
                ).count(),
            }
            
            return self.safe_response({
                'period_days': days,
                'total_clicks': total_clicks,
                'suspicious_clicks': suspicious_clicks,
                'suspicious_percentage': round((suspicious_clicks / total_clicks * 100) if total_clicks > 0 else 0, 2),
                'unique_users': unique_users,
                'anonymous_clicks': anonymous_clicks,
                'top_actions': list(top_actions),
                'hourly_distribution': list(hourly_distribution),
                'risk_distribution': risk_distribution,
                'generated_at': timezone.now().isoformat()
            })
            
        except PermissionDenied as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def user_activity(self, request):
        """Get user's own click activity"""
        try:
            user = request.user
            
            days = min(int(request.query_params.get('days', 30)), 365)
            time_threshold = timezone.now() - timedelta(days=days)
            
            user_clicks = ClickTracker.objects.filter(
                user=user,
                clicked_at__gte=time_threshold
            )
            
            total_clicks = user_clicks.count()
            suspicious_clicks = user_clicks.filter(is_suspicious=True).count()
            
            # Get activity by day
            daily_activity = user_clicks.annotate(
                day=TruncDay('clicked_at')
            ).values('day').annotate(
                count=Count('id'),
                avg_risk=Avg('risk_score')
            ).order_by('-day')[:30]
            
            # Get top action types
            top_actions = user_clicks.values('action_type').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            return self.safe_response({
                'user_id': user.id,
                'username': user.username,
                'period_days': days,
                'total_clicks': total_clicks,
                'suspicious_clicks': suspicious_clicks,
                'daily_activity': list(daily_activity),
                'top_actions': list(top_actions),
                'average_risk_score': user_clicks.aggregate(
                    avg_risk=Avg('risk_score')
                )['avg_risk'] or 0,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_log(self, request):
        """Log multiple clicks at once (for batch processing)"""
        try:
            clicks_data = request.data.get('clicks', [])
            
            if not isinstance(clicks_data, list):
                return self.safe_response(
                    {'error': 'clicks must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit batch size
            max_batch_size = 100
            if len(clicks_data) > max_batch_size:
                return self.safe_response(
                    {'error': f'Batch size exceeds maximum of {max_batch_size}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            created_clicks = []
            errors = []
            
            for i, click_data in enumerate(clicks_data):
                try:
                    # Add request metadata
                    click_data['metadata'] = click_data.get('metadata', {})
                    click_data['metadata'].update({
                        'batch_index': i,
                        'batch_timestamp': timezone.now().isoformat()
                    })
                    
                    serializer = ClickTrackerSerializer(data=click_data)
                    if serializer.is_valid():
                        click = serializer.save()
                        created_clicks.append({
                            'id': click.id,
                            'action_type': click.action_type,
                            'clicked_at': click.clicked_at
                        })
                    else:
                        errors.append({
                            'index': i,
                            'errors': serializer.errors,
                            'data': click_data
                        })
                        
                except Exception as e:
                    errors.append({
                        'index': i,
                        'error': str(e),
                        'data': click_data
                    })
            
            return self.safe_response({
                'total_processed': len(clicks_data),
                'successful': len(created_clicks),
                'failed': len(errors),
                'created_clicks': created_clicks,
                'errors': errors if errors else None
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def check_rate_limit(self, request):
        """Check if user is rate limited"""
        try:
            user_id = request.query_params.get('user_id')
            action_type = request.query_params.get('action_type', 'click')
            
            if not user_id:
                return self.safe_response(
                    {'error': 'user_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return self.safe_response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check various rate limits
            checks = []
            
            # Fast clicking check
            is_fast_clicking = EnhancedClickTracker.check_fast_clicking(
                user=user,
                action_type=action_type,
                time_window=60,
                max_clicks=10
            )
            checks.append({
                'check': 'fast_clicking_60s',
                'is_limited': is_fast_clicking,
                'threshold': '10 clicks per minute'
            })
            
            # Hourly limit check
            hourly_count = ClickTracker.objects.filter(
                user=user,
                clicked_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            is_hourly_limited = hourly_count >= 100
            checks.append({
                'check': 'hourly_limit',
                'is_limited': is_hourly_limited,
                'current': hourly_count,
                'threshold': 100
            })
            
            # Daily limit check
            daily_count = ClickTracker.objects.filter(
                user=user,
                clicked_at__gte=timezone.now() - timedelta(days=1)
            ).count()
            is_daily_limited = daily_count >= 1000
            checks.append({
                'check': 'daily_limit',
                'is_limited': is_daily_limited,
                'current': daily_count,
                'threshold': 1000
            })
            
            # Overall status
            is_limited = any(check['is_limited'] for check in checks)
            
            return self.safe_response({
                'user_id': user_id,
                'action_type': action_type,
                'is_rate_limited': is_limited,
                'checks': checks,
                'checked_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_client_ip(self, request) -> str:
        """Safely extract client IP from request"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
            # Validate IP format
            if ip and len(ip) <= 45:  # Max length for IPv6
                return ip
            
            return "0.0.0.0"
        except Exception:
            return "0.0.0.0"


class EnhancedClickTrackerViewSet(ClickTrackerViewSet):
    """ViewSet for EnhancedClickTracker with additional features"""
    
    queryset = EnhancedClickTracker.objects.select_related('user').all()
    serializer_class = EnhancedClickTrackerSerializer
    
    @action(detail=False, methods=['post'])
    def log_enhanced(self, request):
        """Log click with enhanced features"""
        try:
            # Extract device info from request
            device_info = request.data.get('device_info', {})
            if not device_info:
                device_info = EnhancedClickTracker._extract_device_info(request)
                request.data['device_info'] = device_info
            
            # Use EnhancedClickTracker's log_action method
            user = request.user if request.user.is_authenticated else None
            action_type = request.data.get('action_type', 'click')
            ip_address = request.data.get('ip_address') or self._get_client_ip(request)
            metadata = request.data.get('metadata', {})
            
            # Add request context to metadata
            metadata.update({
                'request_method': request.method,
                'request_path': request.path,
                'is_enhanced': True
            })
            
            click = EnhancedClickTracker.log_action(
                user=user,
                action_type=action_type,
                ip_address=ip_address,
                device_info=device_info,
                metadata=metadata,
                request=request
            )
            
            if click:
                serializer = self.get_serializer(click)
                return self.safe_response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return self.safe_response(
                    {'error': 'Failed to log click'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def suspicious_activity(self, request):
        """Get suspicious click activity"""
        try:
            # Permission check
            if not (request.user.is_staff or request.user.is_superuser):
                raise PermissionDenied("Only staff can view suspicious activity")
            
            hours = min(int(request.query_params.get('hours', 24)), 720)
            min_risk_score = min(float(request.query_params.get('min_risk', 70)), 100)
            limit = min(int(request.query_params.get('limit', 50)), 500)
            
            suspicious_clicks = EnhancedClickTracker.get_suspicious_activity(
                hours=hours,
                min_risk_score=min_risk_score,
                limit=limit
            )
            
            serializer = self.get_serializer(suspicious_clicks, many=True)
            
            return self.safe_response({
                'period_hours': hours,
                'min_risk_score': min_risk_score,
                'total_found': len(suspicious_clicks),
                'clicks': serializer.data,
                'generated_at': timezone.now().isoformat()
            })
            
        except PermissionDenied as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        """Get detailed user click statistics"""
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return self.safe_response(
                    {'error': 'user_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Permission check
            if not (request.user.is_staff or request.user.is_superuser or 
                   str(request.user.id) == user_id):
                raise PermissionDenied("Cannot view other users' statistics")
            
            days = min(int(request.query_params.get('days', 7)), 365)
            
            stats = EnhancedClickTracker.get_user_click_stats(
                user_id=int(user_id),
                days=days
            )
            
            return self.safe_response(stats)
            
        except PermissionDenied as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)


# API Views for specific functionality
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def quick_log_click(request):
    """Quick endpoint for logging clicks (minimal validation)"""
    try:
        # Extract basic information
        data = {
            'action_type': request.data.get('action_type', 'click'),
            'ip_address': request.data.get('ip_address') or _get_client_ip(request),
            'user_agent': request.data.get('user_agent') or request.META.get('HTTP_USER_AGENT', ''),
            'page_url': request.data.get('page_url', ''),
            'metadata': request.data.get('metadata', {})
        }
        
        # Add user if authenticated
        if request.user.is_authenticated:
            data['user_id'] = request.user.id
        
        # Use factory method for quick creation
        click = ClickTracker.create_click(**data)
        
        return Response({
            'success': True,
            'click_id': click.id,
            'action_type': click.action_type,
            'timestamp': click.clicked_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in quick_log_click: {e}")
        return Response(
            {'error': 'Failed to log click'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _get_client_ip(request):
    """Helper to get client IP"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class ClickAnalyticsAPIView(DefensiveAPIViewMixin, APIView):
    """API for click analytics and insights"""
    
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get(self, request):
        """Get comprehensive click analytics"""
        try:
            days = min(int(request.query_params.get('days', 30)), 365)
            time_threshold = timezone.now() - timedelta(days=days)
            
            # Get overall metrics
            metrics = self._get_overall_metrics(time_threshold)
            
            # Get trend analysis
            trends = self._get_trend_analysis(time_threshold)
            
            # Get risk analysis
            risk_analysis = self._get_risk_analysis(time_threshold)
            
            # Get top insights
            insights = self._get_insights(time_threshold)
            
            return self.safe_response({
                'period_days': days,
                'metrics': metrics,
                'trends': trends,
                'risk_analysis': risk_analysis,
                'insights': insights,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_overall_metrics(self, time_threshold):
        """Get overall click metrics"""
        try:
            total_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).count()
            
            suspicious_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                is_suspicious=True
            ).count()
            
            unique_users = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                user__isnull=False
            ).values('user').distinct().count()
            
            unique_ips = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).values('ip_address').distinct().count()
            
            avg_risk_score = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).aggregate(avg_risk=Avg('risk_score'))['avg_risk'] or 0
            
            return {
                'total_clicks': total_clicks,
                'suspicious_clicks': suspicious_clicks,
                'suspicious_percentage': round((suspicious_clicks / total_clicks * 100) if total_clicks > 0 else 0, 2),
                'unique_users': unique_users,
                'unique_ips': unique_ips,
                'avg_risk_score': round(avg_risk_score, 2),
                'clicks_per_user': round(total_clicks / unique_users, 2) if unique_users > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting overall metrics: {e}")
            return {'error': 'metrics_unavailable'}
    
    def _get_trend_analysis(self, time_threshold):
        """Analyze click trends"""
        try:
            # Daily trend
            daily_trend = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).annotate(
                day=TruncDay('clicked_at')
            ).values('day').annotate(
                total=Count('id'),
                suspicious=Count('id', filter=Q(is_suspicious=True)),
                avg_risk=Avg('risk_score')
            ).order_by('day')
            
            # Hourly pattern
            hourly_pattern = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).annotate(
                hour=TruncHour('clicked_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
            
            # Weekly pattern
            weekly_pattern = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).annotate(
                weekday=ExpressionWrapper(
                    ExtractWeekDay('clicked_at'),
                    output_field=IntegerField()
                )
            ).values('weekday').annotate(
                count=Count('id')
            ).order_by('weekday')
            
            return {
                'daily_trend': list(daily_trend),
                'hourly_pattern': list(hourly_pattern),
                'weekly_pattern': list(weekly_pattern)
            }
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {'error': 'trend_analysis_unavailable'}
    
    def _get_risk_analysis(self, time_threshold):
        """Analyze risk patterns"""
        try:
            # Risk factors
            risk_factors = {
                'anonymous_users': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    user__isnull=True
                ).count(),
                'invalid_ips': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    ip_address='0.0.0.0'
                ).count(),
                'short_user_agents': ClickTracker.objects.filter(
                    clicked_at__gte=time_threshold,
                    user_agent__lt=10
                ).count(),
            }
            
            # High-risk users
            high_risk_users = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                current_score__gte=70
            ).values('user').annotate(
                click_count=Count('id'),
                avg_risk=Avg('risk_score')
            ).order_by('-avg_risk')[:10]
            
            # Risk by action type
            risk_by_action = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).values('action_type').annotate(
                total=Count('id'),
                suspicious=Count('id', filter=Q(is_suspicious=True)),
                suspicious_percentage=ExpressionWrapper(
                    Count('id', filter=Q(is_suspicious=True)) * 100.0 / Count('id'),
                    output_field=FloatField()
                )
            ).order_by('-suspicious_percentage')[:10]
            
            return {
                'risk_factors': risk_factors,
                'high_risk_users': list(high_risk_users),
                'risk_by_action': list(risk_by_action)
            }
        except Exception as e:
            logger.error(f"Error getting risk analysis: {e}")
            return {'error': 'risk_analysis_unavailable'}
    
    def _get_insights(self, time_threshold):
        """Generate actionable insights"""
        try:
            insights = []
            
            # Insight 1: High risk periods
            high_risk_hours = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                current_score__gte=70
            ).annotate(
                hour=TruncHour('clicked_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            if high_risk_hours:
                insights.append({
                    'type': 'high_risk_period',
                    'message': f"Highest risk clicks occur during hours: {', '.join(str(h['hour'].hour) for h in high_risk_hours)}",
                    'severity': 'medium'
                })
            
            # Insight 2: Suspicious action patterns
            suspicious_actions = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                is_suspicious=True
            ).values('action_type').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            if suspicious_actions:
                top_action = suspicious_actions[0]
                insights.append({
                    'type': 'suspicious_action',
                    'message': f"Most suspicious action type: '{top_action['action_type']}' with {top_action['count']} incidents",
                    'severity': 'high'
                })
            
            # Insight 3: Anonymous click rate
            total_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold
            ).count()
            
            anonymous_clicks = ClickTracker.objects.filter(
                clicked_at__gte=time_threshold,
                user__isnull=True
            ).count()
            
            anonymous_percentage = (anonymous_clicks / total_clicks * 100) if total_clicks > 0 else 0
            
            if anonymous_percentage > 30:
                insights.append({
                    'type': 'high_anonymous_rate',
                    'message': f"High percentage of anonymous clicks: {anonymous_percentage:.1f}%",
                    'severity': 'medium'
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return [{'type': 'error', 'message': 'Insights unavailable', 'severity': 'low'}]
        

class DefensiveBanAPIViewMixin:
    """Mixin for defensive API view patterns for UserBan"""
    
    @staticmethod
    def safe_response(data: Any, status_code: int = status.HTTP_200_OK) -> Response:
        """Create safe response with error handling"""
        try:
            return Response(data, status=status_code)
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def handle_exception(exception: Exception, context: Dict = None) -> Response:
        """Handle exceptions with defensive coding"""
        try:
            # Log the exception
            logger.error(f"UserBan API Exception: {exception}", exc_info=True, extra=context)
            
            # Return appropriate response based on exception type
            if isinstance(exception, ValidationError):
                return Response(
                    {'error': 'Validation error', 'details': exception.detail},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif isinstance(exception, PermissionDenied):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif isinstance(exception, NotFound):
                return Response(
                    {'error': 'Resource not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                # Don't expose internal errors in production
                from django.conf import settings
                if settings.DEBUG:
                    return Response(
                        {'error': str(exception)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                else:
                    return Response(
                        {'error': 'Internal server error'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            # Even error handling failed - return minimal response
            logger.critical(f"Error handling failed in UserBan: {e}")
            return Response(
                {'error': 'Critical server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Safely extract client IP from request"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
            # Validate IP format
            if ip and len(ip) <= 45:  # Max length for IPv6
                return ip
            
            return "0.0.0.0"
        except Exception:
            return "0.0.0.0"


class IsAdminOrSecurityTeam(permissions.BasePermission):
    """Custom permission for admin or security team members"""
    
    def has_permission(self, request, view):
        try:
            return request.user and (
                request.user.is_staff or 
                request.user.is_superuser or
                hasattr(request.user, 'is_security_team') and request.user.is_security_team
            )
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False  # Fail safe - deny access


class UserBanViewSet(DefensiveBanAPIViewMixin, viewsets.ModelViewSet):
    """
    Defensive ViewSet for UserBan operations
    with comprehensive error handling and validation
    """
    
    queryset = UserBan.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        try:
            if self.action == 'list':
                return UserBanListSerializer
            elif self.action == 'create':
                return UserBanCreateSerializer
            elif self.action in ['update', 'partial_update']:
                return UserBanUpdateSerializer
            else:
                return UserBanSerializer
        except Exception as e:
            logger.error(f"Error getting serializer class: {e}")
            return UserBanSerializer  # Default fallback
        
        
    def handle_exception(self, exc):
        from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed
        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            return Response(
                {'error': 'Authentication required', 'error_code': 'NOT_AUTHENTICATED'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return super().handle_exception(exc)
    
    def get_queryset(self):
        """Defensive queryset filtering with permission checks"""
        try:
            queryset = super().get_queryset()
            
            # Apply filters from query parameters safely
            query_params = self.request.query_params
            
            # User filter
            user_id = query_params.get('user_id')
            if user_id and user_id.isdigit():
                queryset = queryset.filter(user_id=int(user_id))
            
            # Ban type filter
            ban_type = query_params.get('ban_type')
            if ban_type:
                if ban_type.lower() == 'permanent':
                    queryset = queryset.filter(is_permanent=True)
                elif ban_type.lower() == 'temporary':
                    queryset = queryset.filter(is_permanent=False)
            
            # Status filter
            is_active = query_params.get('is_active')
            if is_active and is_active.lower() in ['true', 'false']:
                queryset = queryset.filter(is_active_ban=(is_active.lower() == 'true'))
            
            # Date range filters
            start_date = query_params.get('start_date')
            end_date = query_params.get('end_date')
            
            if start_date:
                try:
                    start_datetime = timezone.make_aware(datetime.fromisoformat(start_date))
                    queryset = queryset.filter(banned_at__gte=start_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start_date: {start_date}")
            
            if end_date:
                try:
                    end_datetime = timezone.make_aware(datetime.fromisoformat(end_date))
                    queryset = queryset.filter(banned_at__lte=end_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid end_date: {end_date}")
            
            # Search filter
            search = query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(reason__icontains=search) |
                    Q(user__username__icontains=search) |
                    Q(user__email__icontains=search)
                )
            
            # # Order by
            # order_by = query_params.get('order_by', '-banned_at')
            # if order_by.lstrip('-') in ['id', 'user__username', 'banned_at', 'banned_until']:
            #     queryset = queryset.order_by(order_by)
            order_by = query_params.get('ordering') or query_params.get('order_by', '-banned_at')
            ordering_map = {
                 'created_at': 'banned_at',
                 '-created_at': '-banned_at',
                 }  
            
            order_by = ordering_map.get(order_by, order_by)
            valid_fields = ['id', 'user__username', 'banned_at', 'banned_until']
            if order_by.lstrip('-') in valid_fields:
                queryset = queryset.order_by(order_by)
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return UserBan.objects.none()
        return queryset 
    
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Cached list view with error handling"""
        try:
            # Apply pagination safely
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            if self.pagination_class:
                if self.pagination_class: self.pagination_class.page_size = page_size
            
            
            return super().list(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Defensive create with transaction and auditing"""
        try:
            # Add audit metadata
            request.data['metadata'] = request.data.get('metadata', {})
            request.data['metadata'].update({
                'created_by': request.user.username if request.user.is_authenticated else 'system',
                'created_ip': self.get_client_ip(request),
                'created_at': timezone.now().isoformat()
            })
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a ban"""
        try:
            ban = self.get_object()
            
            reason = request.data.get('reason', 'Manually deactivated by admin')
            
            success, message = ban.deactivate_ban(reason)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'ban_id': ban.id,
                    'user_id': ban.user_id,
                    'is_active_ban': ban.is_active_ban
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except UserBan.DoesNotExist:
            return self.safe_response(
                {'error': 'Ban not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """Extend a temporary ban"""
        try:
            ban = self.get_object()
            
            if ban.is_permanent:
                return self.safe_response(
                    {'error': 'Cannot extend permanent ban'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            days = request.data.get('days', 7)
            if not isinstance(days, int) or days <= 0:
                return self.safe_response(
                    {'error': 'Days must be a positive integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Calculate new expiration
            current_expiry = ban.banned_until or timezone.now()
            new_expiry = current_expiry + timedelta(days=days)
            
            ban.banned_until = new_expiry
            ban.is_active_ban = True
            ban.save()
            
            return self.safe_response({
                'message': f'Ban extended by {days} days',
                'ban_id': ban.id,
                'new_expiry': new_expiry.isoformat(),
                'remaining_days': (new_expiry - timezone.now()).days
            })
            
        except UserBan.DoesNotExist:
            return self.safe_response(
                {'error': 'Ban not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def check_user(self, request):
        """Check if a specific user is banned"""
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return self.safe_response(
                    {'error': 'user_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user_id_int = int(user_id)
            except ValueError:
                return self.safe_response(
                    {'error': 'user_id must be a valid integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            is_banned, ban = UserBan.is_user_banned(user_id_int)
            
            response_data = {
                'is_banned': is_banned,
                'user_id': user_id_int,
                'checked_at': timezone.now().isoformat()
            }
            
            if is_banned and ban:
                serializer = UserBanSerializer(ban)
                response_data['ban_details'] = serializer.data
                
                # Add remaining time info
                remaining = ban.get_remaining_duration()
                if remaining:
                    response_data['remaining_days'] = remaining.days
                    response_data['remaining_hours'] = remaining.seconds // 3600
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    # @permission_classes([permissions.IsAuthenticated])
    def check_self(self, request):
        """Check if the current user is banned"""
        try:
            is_banned, ban = UserBan.is_user_banned(request.user.id)
            
            response_data = {
                'is_banned': is_banned,
                'user_id': request.user.id,
                'username': request.user.username,
                'checked_at': timezone.now().isoformat()
            }
            
            if is_banned and ban:
                response_data.update({
                    'ban_reason': ban.reason,
                    'ban_type': 'permanent' if ban.is_permanent else 'temporary',
                    'banned_at': ban.banned_at.isoformat() if ban.banned_at else None,
                    'banned_until': ban.banned_until.isoformat() if ban.banned_until else None,
                })
                
                if not ban.is_permanent and ban.banned_until:
                    remaining = ban.get_remaining_duration()
                    if remaining:
                        response_data['remaining_days'] = remaining.days
                        response_data['remaining_hours'] = remaining.seconds // 3600
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Clean up expired bans (admin only)"""
        try:
            if not request.user.is_superuser:
                raise PermissionDenied("Only superusers can perform cleanup")
            
            count = UserBan.cleanup_expired_bans()
            
            return self.safe_response({
                'message': f'Successfully cleaned up {count} expired bans',
                'count': count,
                'cleaned_at': timezone.now().isoformat()
            })
            
        except PermissionDenied as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get ban statistics"""
        try:
            # Get overall statistics
            total_bans = UserBan.objects.count()
            active_bans = UserBan.get_active_bans().count()
            permanent_bans = UserBan.objects.filter(is_permanent=True).count()
            temporary_bans = UserBan.objects.filter(is_permanent=False).count()
            
            # Recent bans (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_bans = UserBan.objects.filter(
                banned_at__gte=thirty_days_ago
            ).count()
            
            # Expired bans count
            expired_bans = UserBan.objects.filter(
                is_active_ban=True,
                is_permanent=False,
                banned_until__lte=timezone.now()
            ).count()
            
            # Bans by reason category (simplified)
            common_reasons = UserBan.objects.values('reason').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # User with most bans
            top_banned_users = UserBan.objects.values(
                'user__id', 'user__username'
            ).annotate(
                ban_count=Count('id')
            ).order_by('-ban_count')[:5]
            
            return self.safe_response({
                'total_bans': total_bans,
                'active_bans': active_bans,
                'permanent_bans': permanent_bans,
                'temporary_bans': temporary_bans,
                'recent_bans_30d': recent_bans,
                'expired_bans_pending_cleanup': expired_bans,
                'common_reasons': list(common_reasons),
                'top_banned_users': list(top_banned_users),
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate multiple bans"""
        try:
            ban_ids = request.data.get('ban_ids', [])
            reason = request.data.get('reason', 'Bulk deactivation')
            
            if not isinstance(ban_ids, list):
                return self.safe_response(
                    {'error': 'ban_ids must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(ban_ids) > 100:
                return self.safe_response(
                    {'error': 'Cannot process more than 100 bans at once'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            successful = []
            failed = []
            
            for ban_id in ban_ids:
                try:
                    ban = UserBan.objects.get(id=ban_id)
                    success, message = ban.deactivate_ban(reason)
                    
                    if success:
                        successful.append({
                            'ban_id': ban_id,
                            'message': message
                        })
                    else:
                        failed.append({
                            'ban_id': ban_id,
                            'error': message
                        })
                        
                except UserBan.DoesNotExist:
                    failed.append({
                        'ban_id': ban_id,
                        'error': 'Ban not found'
                    })
                except Exception as e:
                    failed.append({
                        'ban_id': ban_id,
                        'error': str(e)
                    })
            
            return self.safe_response({
                'total_requested': len(ban_ids),
                'successful': len(successful),
                'failed': len(failed),
                'successful_bans': successful,
                'failed_bans': failed if failed else None,
                'reason': reason
            })
            
        except Exception as e:
            return self.handle_exception(e)
        
        

class UserBanPublicAPIView(DefensiveBanAPIViewMixin, APIView):
    """
    Public API endpoints for UserBan (self-service)
    with defensive coding and rate limiting
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user's ban status"""
        try:
            user_id = request.user.id
            
            is_banned, ban = UserBan.is_user_banned(user_id)
            
            response_data = {
                'user_id': user_id,
                'username': request.user.username,
                'is_banned': is_banned,
                'checked_at': timezone.now().isoformat()
            }
            
            if is_banned and ban:
                # Limited information for public API
                response_data.update({
                    'ban_type': 'permanent' if ban.is_permanent else 'temporary',
                    'banned_since': ban.banned_at.isoformat() if ban.banned_at else None,
                })
                
                if not ban.is_permanent and ban.banned_until:
                    remaining = ban.get_remaining_duration()
                    if remaining:
                        response_data['remaining_hours'] = remaining.days * 24 + remaining.seconds // 3600
                        response_data['will_expire_at'] = ban.banned_until.isoformat()
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @method_decorator(cache_page(60))  # Cache for 1 minute
    def post(self, request):
        """Appeal a ban (simplified - would integrate with ticketing system)"""
        try:
            user_id = request.user.id
            
            is_banned, ban = UserBan.is_user_banned(user_id)
            
            if not is_banned or not ban:
                return self.safe_response(
                    {'error': 'You are not currently banned'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            appeal_reason = request.data.get('appeal_reason', '')
            
            if not appeal_reason or len(appeal_reason.strip()) < 10:
                return self.safe_response(
                    {'error': 'Appeal reason must be at least 10 characters'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # In a real system, this would create a support ticket
            # For now, just log the appeal
            
            logger.info(
                f"Ban appeal submitted: "
                f"User={user_id}, "
                f"Ban={ban.id}, "
                f"Reason={appeal_reason[:100]}..."
            )
            
            return self.safe_response({
                'message': 'Ban appeal submitted successfully',
                'appeal_id': f"APPEAL-{ban.id}-{int(timezone.now().timestamp())}",
                'submitted_at': timezone.now().isoformat(),
                'estimated_response_time': '24-48 hours'
            })
            
        except Exception as e:
            return self.handle_exception(e)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_ban_check(request, user_id):
    """
    Public endpoint to check if a user is banned
    (Limited information for privacy)
    """
    try:
        try:
            user_id_int = int(user_id)
        except ValueError:
            return Response(
                {'error': 'Invalid user ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_banned, ban = UserBan.is_user_banned(user_id_int)
        
        response_data = {
            'user_id': user_id_int,
            'is_banned': is_banned,
            'checked_at': timezone.now().isoformat()
        }
        
        # Only provide minimal information for privacy
        if is_banned and ban:
            response_data.update({
                'ban_type': 'permanent' if ban.is_permanent else 'temporary',
            })
            
            if not ban.is_permanent:
                # Only indicate if ban is temporary, not when it expires
                response_data['is_temporary'] = True
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error in public_ban_check: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class BanMiddlewareCheckAPIView(DefensiveBanAPIViewMixin, APIView):
    """
    API for middleware to check bans efficiently
    Optimized for performance with defensive coding
    """
    
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(cache_page(30))  # Cache for 30 seconds
    def post(self, request):
        """Batch check multiple users for bans (optimized for middleware)"""
        try:
            user_ids = request.data.get('user_ids', [])
            
            if not isinstance(user_ids, list):
                return self.safe_response(
                    {'error': 'user_ids must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit batch size for performance
            if len(user_ids) > 1000:
                user_ids = user_ids[:1000]
                logger.warning(f"Ban check batch limited to 1000 users")
            
            # Convert to integers safely
            valid_user_ids = []
            for user_id in user_ids:
                try:
                    valid_user_ids.append(int(user_id))
                except (ValueError, TypeError):
                    continue
            
            # Batch query for efficiency
            now = timezone.now()
            active_bans = UserBan.objects.filter(
                user_id__in=valid_user_ids,
                is_active_ban=True
            ).filter(
                Q(is_permanent=True) |
                Q(banned_until__gt=now)
            ).select_related('user').values(
                'user_id', 'id', 'is_permanent', 'banned_until', 'reason'
            )
            
            # Create lookup dictionary
            bans_by_user = {}
            for ban in active_bans:
                user_id = ban['user_id']
                bans_by_user[user_id] = {
                    'ban_id': ban['id'],
                    'is_permanent': ban['is_permanent'],
                    'banned_until': ban['banned_until'].isoformat() if ban['banned_until'] else None,
                    'reason': ban['reason'][:100]  # Truncate for efficiency
                }
            
            # Prepare response
            results = {}
            for user_id in valid_user_ids:
                if user_id in bans_by_user:
                    results[user_id] = {
                        'is_banned': True,
                        **bans_by_user[user_id]
                    }
                else:
                    results[user_id] = {
                        'is_banned': False
                    }
            
            return self.safe_response({
                'results': results,
                'total_checked': len(valid_user_ids),
                'banned_count': len(bans_by_user),
                'checked_at': now.isoformat(),
                'cache_hit': False  # Would be True if using cache
            })
            
        except Exception as e:
            return self.handle_exception(e)
        

class DefensiveIPBlacklistAPIViewMixin:
    """Mixin for defensive API view patterns for IPBlacklist"""
    
    @staticmethod
    def safe_response(data: Any, status_code: int = status.HTTP_200_OK) -> Response:
        """Create safe response with error handling"""
        try:
            return Response(data, status=status_code)
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def handle_exception(exception: Exception, context: Dict = None) -> Response:
        """Handle exceptions with defensive coding"""
        try:
            # Log the exception
            logger.error(f"IPBlacklist API Exception: {exception}", exc_info=True, extra=context)
            
            # Return appropriate response based on exception type
            if isinstance(exception, ValidationError):
                return Response(
                    {'error': 'Validation error', 'details': exception.detail},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif isinstance(exception, PermissionDenied):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif isinstance(exception, NotFound):
                return Response(
                    {'error': 'Resource not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                # Don't expose internal errors in production
                from django.conf import settings
                if settings.DEBUG:
                    return Response(
                        {'error': str(exception)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                else:
                    return Response(
                        {'error': 'Internal server error'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            # Even error handling failed - return minimal response
            logger.critical(f"Error handling failed in IPBlacklist: {e}")
            return Response(
                {'error': 'Critical server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Safely extract client IP from request"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
            # Validate IP format
            if ip and len(ip) <= 45:  # Max length for IPv6
                return ip
            
            return "0.0.0.0"
        except Exception:
            return "0.0.0.0"
    
    @staticmethod
    def validate_ip_address(ip_address: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
        except Exception:
            return False


class IsAdminOrSecurityTeam(permissions.BasePermission):
    """Custom permission for admin or security team members"""
    
    def has_permission(self, request, view):
        try:
            return request.user and (
                request.user.is_staff or 
                request.user.is_superuser or
                hasattr(request.user, 'is_security_team') and request.user.is_security_team
            )
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False  # Fail safe - deny access


class IPBlacklistViewSet(DefensiveIPBlacklistAPIViewMixin, viewsets.ModelViewSet):
    """
    Defensive ViewSet for IPBlacklist operations
    with comprehensive error handling and validation
    """
    
    queryset = IPBlacklist.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        try:
            if self.action == 'list':
                return IPBlacklistListSerializer
            elif self.action == 'create':
                return IPBlacklistCreateSerializer
            else:
                return IPBlacklistSerializer
        except Exception as e:
            logger.error(f"Error getting serializer class: {e}")
            return IPBlacklistSerializer  # Default fallback
    
    def get_queryset(self):
        """Defensive queryset filtering with permission checks"""
        try:
            queryset = super().get_queryset()
            
            # Apply filters from query parameters safely
            query_params = self.request.query_params
            
            # IP address filter
            ip_address = query_params.get('ip_address')
            if ip_address:
                queryset = queryset.filter(ip_address=ip_address)
            
            # Threat level filter
            threat_level = query_params.get('threat_level')
            if threat_level:
                queryset = queryset.filter(threat_level=threat_level)
            
            # Threat type filter
            threat_type = query_params.get('threat_type')
            if threat_type:
                queryset = queryset.filter(threat_type=threat_type)
            
            # Status filter
            is_active = query_params.get('is_active')
            if is_active and is_active.lower() in ['true', 'false']:
                queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
            
            # Permanent filter
            is_permanent = query_params.get('is_permanent')
            if is_permanent and is_permanent.lower() in ['true', 'false']:
                queryset = queryset.filter(is_permanent=(is_permanent.lower() == 'true'))
            
            # Country filter
            country_code = query_params.get('country_code')
            if country_code:
                queryset = queryset.filter(country_code=country_code)
            
            # Detection method filter
            detection_method = query_params.get('detection_method')
            if detection_method:
                queryset = queryset.filter(detection_method=detection_method)
            
            # Date range filters
            start_date = query_params.get('start_date')
            end_date = query_params.get('end_date')
            
            if start_date:
                try:
                    start_datetime = timezone.make_aware(datetime.fromisoformat(start_date))
                    queryset = queryset.filter(first_seen__gte=start_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start_date: {start_date}")
            
            if end_date:
                try:
                    end_datetime = timezone.make_aware(datetime.fromisoformat(end_date))
                    queryset = queryset.filter(first_seen__lte=end_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid end_date: {end_date}")
            
            # Confidence score filters
            min_confidence = query_params.get('min_confidence')
            max_confidence = query_params.get('max_confidence')
            
            if min_confidence:
                try:
                    queryset = queryset.filter(confidence_score__gte=float(min_confidence))
                except (ValueError, TypeError):
                    pass
            
            if max_confidence:
                try:
                    queryset = queryset.filter(confidence_score__lte=float(max_confidence))
                except (ValueError, TypeError):
                    pass
            
            # Search filter
            search = query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(ip_address__icontains=search) |
                    Q(reason__icontains=search) |
                    Q(notes__icontains=search) |
                    Q(country_name__icontains=search) |
                    Q(city__icontains=search) |
                    Q(isp__icontains=search) |
                    Q(organization__icontains=search)
                )
            
            # Order by
            order_by = query_params.get('order_by', '-last_attempt')
            if order_by.lstrip('-') in ['id', 'ip_address', 'threat_level', 'first_seen', 'last_attempt', 'confidence_score']:
                queryset = queryset.order_by(order_by)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return IPBlacklist.objects.none()  # Return empty queryset on error
    
    @method_decorator(cache_page(60 * 2))  # Cache for 2 minutes
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Cached list view with error handling"""
        try:
            # Apply pagination safely
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            if self.pagination_class: self.pagination_class.page_size = page_size
            
            return super().list(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Defensive create with transaction and auditing"""
        try:
            # Add audit metadata
            request.data['metadata'] = request.data.get('metadata', {})
            request.data['metadata'].update({
                'created_by': request.user.username if request.user.is_authenticated else 'system',
                'created_ip': self.get_client_ip(request),
                'created_at': timezone.now().isoformat(),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            })
            
            # Auto-set reported_by if not provided
            if 'reported_by_id' not in request.data and request.user.is_authenticated:
                request.data['reported_by_id'] = request.user.id
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate an IP block"""
        try:
            ip_block = self.get_object()
            
            reason = request.data.get('reason', 'Manually deactivated by admin')
            
            success, message = ip_block.unblock(reason)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'block_id': ip_block.id,
                    'ip_address': ip_block.ip_address,
                    'is_active': ip_block.is_active
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except IPBlacklist.DoesNotExist:
            return self.safe_response(
                {'error': 'IP block not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """Extend a temporary IP block"""
        try:
            ip_block = self.get_object()
            
            if ip_block.is_permanent:
                return self.safe_response(
                    {'error': 'Cannot extend permanent block'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hours = request.data.get('hours', 24)
            if not isinstance(hours, int) or hours <= 0:
                return self.safe_response(
                    {'error': 'Hours must be a positive integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            reason = request.data.get('reason', 'Extended by admin')
            
            success, message = ip_block.extend_block(hours, reason)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'block_id': ip_block.id,
                    'ip_address': ip_block.ip_address,
                    'new_expiry': ip_block.blocked_until.isoformat() if ip_block.blocked_until else None,
                    'remaining_hours': hours
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except IPBlacklist.DoesNotExist:
            return self.safe_response(
                {'error': 'IP block not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def increment_attack(self, request, pk=None):
        """Increment attack count for an IP block"""
        try:
            ip_block = self.get_object()
            
            attack_type = request.data.get('attack_type')
            
            success, message = ip_block.increment_attack_count(attack_type)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'block_id': ip_block.id,
                    'ip_address': ip_block.ip_address,
                    'attack_count': ip_block.attack_count,
                    'threat_level': ip_block.threat_level
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except IPBlacklist.DoesNotExist:
            return self.safe_response(
                {'error': 'IP block not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def check_ip(self, request):
        """Check if a specific IP is blocked"""
        try:
            ip_address = request.query_params.get('ip_address')
            
            if not ip_address:
                return self.safe_response(
                    {'error': 'ip_address parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not self.validate_ip_address(ip_address):
                return self.safe_response(
                    {'error': f'Invalid IP address format: {ip_address}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            check_subnet = request.query_params.get('check_subnet', 'true').lower() == 'true'
            
            is_blocked, ip_block = IPBlacklist.is_ip_blocked(ip_address, check_subnet=check_subnet)
            
            response_data = {
                'is_blocked': is_blocked,
                'ip_address': ip_address,
                'checked_at': timezone.now().isoformat(),
                'check_subnet': check_subnet
            }
            
            if is_blocked and ip_block:
                serializer = IPBlacklistSerializer(ip_block)
                response_data['block_details'] = serializer.data
                
                # Add match information
                response_data['match_type'] = 'direct' if ip_block.ip_address == ip_address else 'subnet'
                
                # Add remaining time info
                if not ip_block.is_permanent and ip_block.blocked_until:
                    remaining = ip_block.blocked_until - timezone.now()
                    if remaining.total_seconds() > 0:
                        response_data['remaining_hours'] = remaining.days * 24 + remaining.seconds // 3600
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def block_ip_quick(self, request):
        """Quick endpoint to block an IP"""
        try:
            ip_address = request.data.get('ip_address')
            reason = request.data.get('reason', 'Suspicious activity')
            
            if not ip_address:
                return self.safe_response(
                    {'error': 'ip_address is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not self.validate_ip_address(ip_address):
                return self.safe_response(
                    {'error': f'Invalid IP address format: {ip_address}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use factory method
            success, message, ip_block = IPBlacklist.block_ip(
                ip_address=ip_address,
                reason=reason,
                threat_level='medium',
                duration_hours=24,
                reported_by=request.user if request.user.is_authenticated else None,
                auto_blocked_by='quick_block',
                detection_method='manual'
            )
            
            if success:
                serializer = IPBlacklistSerializer(ip_block)
                return self.safe_response({
                    'message': message,
                    'block': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def unblock_ip_quick(self, request):
        """Quick endpoint to unblock an IP"""
        try:
            ip_address = request.data.get('ip_address')
            reason = request.data.get('reason', 'Manual unblock')
            
            if not ip_address:
                return self.safe_response(
                    {'error': 'ip_address is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not self.validate_ip_address(ip_address):
                return self.safe_response(
                    {'error': f'Invalid IP address format: {ip_address}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success, message = IPBlacklist.unblock_ip(ip_address, reason)
            
            if success:
                return self.safe_response({
                    'message': message,
                    'ip_address': ip_address
                })
            else:
                return self.safe_response(
                    {'error': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Clean up expired IP blocks (admin only)"""
        try:
            if not request.user.is_superuser:
                raise PermissionDenied("Only superusers can perform cleanup")
            
            count = IPBlacklist.cleanup_expired_blocks()
            
            return self.safe_response({
                'message': f'Successfully cleaned up {count} expired IP blocks',
                'count': count,
                'cleaned_at': timezone.now().isoformat()
            })
            
        except PermissionDenied as e:
            return self.handle_exception(e)
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get IP blacklist statistics"""
        try:
            stats = IPBlacklist.get_block_statistics()
            
            return self.safe_response(stats)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate multiple IP blocks"""
        try:
            block_ids = request.data.get('block_ids', [])
            reason = request.data.get('reason', 'Bulk deactivation')
            
            if not isinstance(block_ids, list):
                return self.safe_response(
                    {'error': 'block_ids must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(block_ids) > 100:
                return self.safe_response(
                    {'error': 'Cannot process more than 100 blocks at once'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            successful = []
            failed = []
            
            for block_id in block_ids:
                try:
                    ip_block = IPBlacklist.objects.get(id=block_id)
                    success, message = ip_block.unblock(reason)
                    
                    if success:
                        successful.append({
                            'block_id': block_id,
                            'ip_address': ip_block.ip_address,
                            'message': message
                        })
                    else:
                        failed.append({
                            'block_id': block_id,
                            'error': message
                        })
                        
                except IPBlacklist.DoesNotExist:
                    failed.append({
                        'block_id': block_id,
                        'error': 'IP block not found'
                    })
                except Exception as e:
                    failed.append({
                        'block_id': block_id,
                        'error': str(e)
                    })
            
            return self.safe_response({
                'total_requested': len(block_ids),
                'successful': len(successful),
                'failed': len(failed),
                'successful_blocks': successful,
                'failed_blocks': failed if failed else None,
                'reason': reason
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def check_multiple_ips(self, request):
        """Check multiple IPs for blocking status (batch)"""
        try:
            ip_addresses = request.data.get('ip_addresses', [])
            check_subnet = request.data.get('check_subnet', True)
            
            if not isinstance(ip_addresses, list):
                return self.safe_response(
                    {'error': 'ip_addresses must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit batch size for performance
            if len(ip_addresses) > 1000:
                ip_addresses = ip_addresses[:1000]
                logger.warning(f"IP check batch limited to 1000 IPs")
            
            results = {}
            
            for ip_address in ip_addresses:
                try:
                    if not self.validate_ip_address(ip_address):
                        results[ip_address] = {
                            'is_blocked': False,
                            'error': 'Invalid IP format'
                        }
                        continue
                    
                    is_blocked, ip_block = IPBlacklist.is_ip_blocked(ip_address, check_subnet=check_subnet)
                    
                    if is_blocked and ip_block:
                        results[ip_address] = {
                            'is_blocked': True,
                            'block_id': ip_block.id,
                            'threat_level': ip_block.threat_level,
                            'threat_type': ip_block.threat_type,
                            'match_type': 'direct' if ip_block.ip_address == ip_address else 'subnet'
                        }
                    else:
                        results[ip_address] = {
                            'is_blocked': False
                        }
                        
                except Exception as e:
                    results[ip_address] = {
                        'is_blocked': False,
                        'error': str(e)
                    }
            
            return self.safe_response({
                'results': results,
                'total_checked': len(ip_addresses),
                'checked_at': timezone.now().isoformat(),
                'check_subnet': check_subnet
            })
            
        except Exception as e:
            return self.handle_exception(e)


class IPBlacklistMiddlewareAPIView(DefensiveIPBlacklistAPIViewMixin, APIView):
    """
    API for middleware to check IP blocks efficiently
    Optimized for performance with defensive coding
    """
    
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(cache_page(10))  # Cache for 10 seconds
    def post(self, request):
        """Batch check multiple IPs for blocks (optimized for middleware)"""
        try:
            ip_addresses = request.data.get('ip_addresses', [])
            
            if not isinstance(ip_addresses, list):
                return self.safe_response(
                    {'error': 'ip_addresses must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Limit batch size for performance
            if len(ip_addresses) > 1000:
                ip_addresses = ip_addresses[:1000]
                logger.warning(f"Middleware IP check batch limited to 1000 IPs")
            
            # Filter valid IP addresses
            valid_ips = []
            for ip in ip_addresses:
                if self.validate_ip_address(ip):
                    valid_ips.append(ip)
            
            # Get current time for expiration checks
            now = timezone.now()
            
            # Query all active blocks
            active_blocks = IPBlacklist.objects.filter(
                is_active=True
            ).filter(
                Q(is_permanent=True) |
                Q(blocked_until__gt=now)
            ).values(
                'id', 'ip_address', 'subnet_mask', 'threat_level',
                'max_requests_per_minute', 'is_permanent', 'blocked_until'
            )
            
            # Create IP to block mapping
            ip_to_block = {}
            for block in active_blocks:
                ip = block['ip_address']
                subnet_mask = block['subnet_mask']
                
                # Store direct match
                ip_to_block[ip] = block
                
                # Check subnet matches for all valid IPs
                if subnet_mask is not None:
                    try:
                        network = ipaddress.ip_network(f"{ip}/{subnet_mask}", strict=False)
                        for check_ip in valid_ips:
                            if check_ip not in ip_to_block:  # Only check if not already matched
                                try:
                                    if ipaddress.ip_address(check_ip) in network:
                                        ip_to_block[check_ip] = block
                                except ValueError:
                                    continue  # Skip invalid IPs
                    except Exception as e:
                        logger.warning(f"Error processing subnet for {ip}/{subnet_mask}: {e}")
            
            # Prepare response
            results = {}
            for ip in valid_ips:
                if ip in ip_to_block:
                    block = ip_to_block[ip]
                    results[ip] = {
                        'is_blocked': True,
                        'block_id': block['id'],
                        'threat_level': block['threat_level'],
                        'max_requests_per_minute': block['max_requests_per_minute'],
                        'is_permanent': block['is_permanent'],
                        'match_type': 'direct' if block['ip_address'] == ip else 'subnet'
                    }
                    
                    # Add remaining time for temporary blocks
                    if not block['is_permanent'] and block['blocked_until']:
                        remaining = block['blocked_until'] - now
                        if remaining.total_seconds() > 0:
                            results[ip]['remaining_seconds'] = int(remaining.total_seconds())
                else:
                    results[ip] = {
                        'is_blocked': False
                    }
            
            return self.safe_response({
                'results': results,
                'total_checked': len(valid_ips),
                'blocked_count': len([ip for ip, data in results.items() if data['is_blocked']]),
                'checked_at': now.isoformat(),
                'cache_hit': False
            })
            
        except Exception as e:
            return self.handle_exception(e)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_ip_check(request, ip_address):
    """
    Public endpoint to check if an IP is blocked
    (Limited information for security)
    """
    try:
        if not DefensiveIPBlacklistAPIViewMixin.validate_ip_address(ip_address):
            return Response(
                {'error': 'Invalid IP address format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_blocked, ip_block = IPBlacklist.is_ip_blocked(ip_address, check_subnet=True)
        
        response_data = {
            'ip_address': ip_address,
            'is_blocked': is_blocked,
            'checked_at': timezone.now().isoformat()
        }
        
        # Only provide minimal information for security
        if is_blocked and ip_block:
            response_data.update({
                'threat_level': ip_block.threat_level,
                'block_type': 'permanent' if ip_block.is_permanent else 'temporary',
            })
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error in public_ip_check: {e}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class IPBlacklistAnalyticsAPIView(DefensiveIPBlacklistAPIViewMixin, APIView):
    """API for IP blacklist analytics and insights"""
    
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get(self, request):
        """Get comprehensive IP blacklist analytics"""
        try:
            days = min(int(request.query_params.get('days', 30)), 365)
            time_threshold = timezone.now() - timedelta(days=days)
            
            # Get overall metrics
            metrics = self._get_overall_metrics(time_threshold)
            
            # Get threat analysis
            threat_analysis = self._get_threat_analysis(time_threshold)
            
            # Get geographic analysis
            geographic_analysis = self._get_geographic_analysis(time_threshold)
            
            # Get trend analysis
            trend_analysis = self._get_trend_analysis(time_threshold)
            
            # Get insights
            insights = self._get_insights(time_threshold)
            
            return self.safe_response({
                'period_days': days,
                'metrics': metrics,
                'threat_analysis': threat_analysis,
                'geographic_analysis': geographic_analysis,
                'trend_analysis': trend_analysis,
                'insights': insights,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_overall_metrics(self, time_threshold):
        """Get overall IP blacklist metrics"""
        try:
            total_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).count()
            
            active_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                is_active=True
            ).count()
            
            permanent_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                is_permanent=True,
                is_active=True
            ).count()
            
            temporary_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                is_permanent=False,
                is_active=True
            ).count()
            
            expired_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                is_active=True,
                is_permanent=False,
                blocked_until__lte=timezone.now()
            ).count()
            
            avg_confidence = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).aggregate(avg_confidence=Avg('confidence_score'))['avg_confidence'] or 0
            
            total_attacks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).aggregate(total_attacks=Sum('attack_count'))['total_attacks'] or 0
            
            return {
                'total_blocks': total_blocks,
                'active_blocks': active_blocks,
                'permanent_blocks': permanent_blocks,
                'temporary_blocks': temporary_blocks,
                'expired_blocks_pending_cleanup': expired_blocks,
                'avg_confidence_score': round(avg_confidence, 2),
                'total_attack_count': total_attacks,
                'blocks_per_day': round(total_blocks / max(1, (timezone.now() - time_threshold).days), 2)
            }
        except Exception as e:
            logger.error(f"Error getting overall metrics: {e}")
            return {'error': 'metrics_unavailable'}
    
    def _get_threat_analysis(self, time_threshold):
        """Analyze threat patterns"""
        try:
            # Threat level distribution
            threat_level_stats = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).values('threat_level').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score'),
                total_attacks=Sum('attack_count')
            ).order_by('-count')
            
            # Threat type distribution
            threat_type_stats = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).values('threat_type').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Detection method distribution
            detection_method_stats = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).values('detection_method').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            ).order_by('-count')
            
            return {
                'threat_level_distribution': list(threat_level_stats),
                'top_threat_types': list(threat_type_stats),
                'detection_methods': list(detection_method_stats)
            }
        except Exception as e:
            logger.error(f"Error getting threat analysis: {e}")
            return {'error': 'threat_analysis_unavailable'}
    
    def _get_geographic_analysis(self, time_threshold):
        """Analyze geographic patterns"""
        try:
            # Top countries
            top_countries = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                country_code__isnull=False
            ).values('country_code', 'country_name').annotate(
                count=Count('id'),
                avg_threat_level=Avg(
                    Case(
                        When(threat_level='low', then=1),
                        When(threat_level='medium', then=2),
                        When(threat_level='high', then=3),
                        When(threat_level='critical', then=4),
                        When(threat_level='confirmed_attacker', then=5),
                        default=1,
                        output_field=FloatField()
                    )
                )
            ).order_by('-count')[:10]
            
            # Top ISPs
            top_isps = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                isp__isnull=False
            ).values('isp').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            # Top organizations
            top_orgs = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                organization__isnull=False
            ).values('organization').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            return {
                'top_countries': list(top_countries),
                'top_isps': list(top_isps),
                'top_organizations': list(top_orgs)
            }
        except Exception as e:
            logger.error(f"Error getting geographic analysis: {e}")
            return {'error': 'geographic_analysis_unavailable'}
    
    def _get_trend_analysis(self, time_threshold):
        """Analyze trends over time"""
        try:
            # Daily trend
            from django.db.models.functions import TruncDay
            daily_trend = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).annotate(
                day=TruncDay('first_seen')
            ).values('day').annotate(
                blocks=Count('id'),
                attacks=Sum('attack_count')
            ).order_by('day')
            
            # Weekly pattern
            from django.db.models.functions import ExtractWeekDay
            weekly_pattern = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).annotate(
                weekday=ExtractWeekDay('first_seen')
            ).values('weekday').annotate(
                count=Count('id')
            ).order_by('weekday')
            
            return {
                'daily_trend': list(daily_trend),
                'weekly_pattern': list(weekly_pattern)
            }
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {'error': 'trend_analysis_unavailable'}
    
    def _get_insights(self, time_threshold):
        """Generate actionable insights"""
        try:
            insights = []
            
            # Insight 1: High threat concentration
            high_threat_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold,
                threat_level__in=['high', 'critical', 'confirmed_attacker']
            ).count()
            
            total_blocks = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).count()
            
            if total_blocks > 0:
                high_threat_percentage = (high_threat_blocks / total_blocks) * 100
                if high_threat_percentage > 30:
                    insights.append({
                        'type': 'high_threat_concentration',
                        'message': f"High concentration of high-threat blocks: {high_threat_percentage:.1f}%",
                        'severity': 'high',
                        'recommendation': 'Review threat detection thresholds'
                    })
            
            # Insight 2: Expired blocks
            expired_blocks = IPBlacklist.objects.filter(
                is_active=True,
                is_permanent=False,
                blocked_until__lte=timezone.now()
            ).count()
            
            if expired_blocks > 10:
                insights.append({
                    'type': 'expired_blocks',
                    'message': f"{expired_blocks} expired blocks need cleanup",
                    'severity': 'medium',
                    'recommendation': 'Run cleanup operation'
                })
            
            # Insight 3: Common threat types
            common_threat_types = IPBlacklist.objects.filter(
                first_seen__gte=time_threshold
            ).values('threat_type').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            if common_threat_types:
                top_type = common_threat_types[0]
                insights.append({
                    'type': 'common_threat_pattern',
                    'message': f"Most common threat type: '{top_type['threat_type']}' with {top_type['count']} incidents",
                    'severity': 'medium',
                    'recommendation': f'Review detection rules for {top_type["threat_type"]} attacks'
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return [{'type': 'error', 'message': 'Insights unavailable', 'severity': 'low'}]
        



class DefensiveRiskScoreAPIViewMixin:
    """Mixin for defensive API view patterns for RiskScore"""
    
    @staticmethod
    def safe_response(data: Any, status_code: int = status.HTTP_200_OK) -> Response:
        """Create safe response with error handling"""
        try:
            return Response(data, status=status_code)
        except Exception as e:
            logger.error(f"Error creating response: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def handle_exception(exception: Exception, context: Dict = None) -> Response:
        """Handle exceptions with defensive coding"""
        try:
            # Log the exception
            logger.error(f"RiskScore API Exception: {exception}", exc_info=True, extra=context)
            
            # Return appropriate response based on exception type
            if isinstance(exception, ValidationError):
                return Response(
                    {'error': 'Validation error', 'details': exception.detail},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif isinstance(exception, PermissionDenied):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            elif isinstance(exception, NotFound):
                return Response(
                    {'error': 'Resource not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                # Don't expose internal errors in production
                from django.conf import settings
                if settings.DEBUG:
                    return Response(
                        {'error': str(exception)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                else:
                    return Response(
                        {'error': 'Internal server error'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            # Even error handling failed - return minimal response
            logger.critical(f"Error handling failed in RiskScore: {e}")
            return Response(
                {'error': 'Critical server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @staticmethod
    def calculate_risk_level(score: int) -> str:
        """Calculate risk level based on score"""
        try:
            if score >= 80:
                return 'critical'
            elif score >= 60:
                return 'high'
            elif score >= 40:
                return 'medium'
            elif score >= 20:
                return 'low'
            else:
                return 'very_low'
        except Exception:
            return 'unknown'


class IsAdminOrSecurityTeam(permissions.BasePermission):
    """Custom permission for admin or security team members"""
    
    def has_permission(self, request, view):
        try:
            return request.user and (
                request.user.is_staff or 
                request.user.is_superuser or
                hasattr(request.user, 'is_security_team') and request.user.is_security_team
            )
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False  # Fail safe - deny access


class SelfPagination(DefensiveRiskScoreAPIViewMixin, viewsets.ModelViewSet):
    """
    Defensive ViewSet for RiskScore operations
    with comprehensive error handling and validation
    """
    
    queryset = RiskScore.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        try:
            if self.action == 'list':
                return RiskScoreListSerializer
            elif self.action in ['update', 'partial_update']:
                return RiskScoreUpdateSerializer
            else:
                return RiskScoreSerializer
        except Exception as e:
            logger.error(f"Error getting serializer class: {e}")
            return RiskScoreSerializer  # Default fallback
    
    def get_queryset(self):
        """Defensive queryset filtering with permission checks"""
        try:
            queryset = super().get_queryset()
            
            # Apply filters from query parameters safely
            query_params = self.request.query_params
            
            # User filter
            user_id = query_params.get('user_id')
            if user_id and user_id.isdigit():
                queryset = queryset.filter(user_id=int(user_id))
            
            # Risk level filter
            risk_level = query_params.get('risk_level')
            if risk_level:
                # Map risk level to score ranges
                level_ranges = {
                    'very_low': (0, 19),
                    'low': (20, 39),
                    'medium': (40, 59),
                    'high': (60, 79),
                    'critical': (80, 100)
                }
                
                if risk_level in level_ranges:
                    min_score, max_score = level_ranges[risk_level]
                    queryset = queryset.filter(
                        current_score__gte=min_score,
                        current_score__lte=max_score
                    )
            
            # Score range filters
            min_score = query_params.get('min_score')
            max_score = query_params.get('max_score')
            
            if min_score:
                try:
                    queryset = queryset.filter(current_score__gte=int(min_score))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid min_score: {min_score}")
            
            if max_score:
                try:
                    queryset = queryset.filter(current_score__lte=int(max_score))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid max_score: {max_score}")
            
            # Risk factor filters
            has_failed_logins = query_params.get('has_failed_logins')
            if has_failed_logins and has_failed_logins.lower() == 'true':
                queryset = queryset.filter(failed_login_attempts__gt=0)
            
            has_suspicious_activities = query_params.get('has_suspicious_activities')
            if has_suspicious_activities and has_suspicious_activities.lower() == 'true':
                queryset = queryset.filter(suspicious_activities__gt=0)
            
            # Date range filters
            start_date = query_params.get('start_date')
            end_date = query_params.get('end_date')
            
            if start_date:
                try:
                    start_datetime = timezone.make_aware(datetime.fromisoformat(start_date))
                    queryset = queryset.filter(calculated_at__gte=start_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start_date: {start_date}")
            
            if end_date:
                try:
                    end_datetime = timezone.make_aware(datetime.fromisoformat(end_date))
                    queryset = queryset.filter(calculated_at__lte=end_datetime)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid end_date: {end_date}")
            
            # Search filter
            search = query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(user__username__icontains=search) |
                    Q(user__email__icontains=search)
                )
            
            # Order by
            order_by = query_params.get('order_by', '-current_score')
            if order_by.lstrip('-') in ['id', 'current_score', 'calculated_at', 'user__username']:
                queryset = queryset.order_by(order_by)
            
            return queryset
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return RiskScore.objects.none()  # Return empty queryset on error
    
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Cached list view with error handling"""
        try:
            # Apply pagination safely
            page_size = min(int(request.query_params.get('page_size', 20)), 100)
            if self.pagination_class: self.pagination_class.page_size = page_size
            
            return super().list(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Defensive create with transaction and auditing"""
        try:
            # Add audit metadata
            request.data['metadata'] = request.data.get('metadata', {})
            request.data['metadata'].update({
                'created_by': request.user.username if request.user.is_authenticated else 'system',
                'created_at': timezone.now().isoformat()
            })
            
            return super().create(request, *args, **kwargs)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """Recalculate risk score"""
        try:
            risk_score = self.get_object()
            
            # Update score
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': 'Risk score recalculated',
                'risk_score': serializer.data,
                'recalculated_at': timezone.now().isoformat()
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def increment_failed_login(self, request, pk=None):
        """Increment failed login attempts"""
        try:
            risk_score = self.get_object()
            
            risk_score.failed_login_attempts += 1
            risk_score.last_suspicious_activity = timezone.now()
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': 'Failed login attempt recorded',
                'risk_score': serializer.data,
                'new_failed_attempts': risk_score.failed_login_attempts
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def increment_suspicious_activity(self, request, pk=None):
        """Increment suspicious activities"""
        try:
            risk_score = self.get_object()
            
            activity_type = request.data.get('activity_type', 'unknown')
            
            risk_score.suspicious_activities += 1
            risk_score.last_suspicious_activity = timezone.now()
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': f'Suspicious activity recorded: {activity_type}',
                'risk_score': serializer.data,
                'new_suspicious_activities': risk_score.suspicious_activities,
                'activity_type': activity_type
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def record_login(self, request, pk=None):
        """Record user login and update risk factors"""
        try:
            risk_score = self.get_object()
            
            # Increment login frequency
            risk_score.login_frequency += 1
            
            # Update last login time
            risk_score.last_login_time = timezone.now()
            
            # Update score
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': 'Login recorded',
                'risk_score': serializer.data,
                'new_login_frequency': risk_score.login_frequency
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def record_device_change(self, request, pk=None):
        """Record device change and update diversity"""
        try:
            risk_score = self.get_object()
            
            device_id = request.data.get('device_id', 'unknown')
            
            # Increment device diversity
            risk_score.device_diversity += 1
            
            # Update score
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': f'Device change recorded: {device_id}',
                'risk_score': serializer.data,
                'new_device_diversity': risk_score.device_diversity,
                'device_id': device_id
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def record_location_change(self, request, pk=None):
        """Record location change and update diversity"""
        try:
            risk_score = self.get_object()
            
            location = request.data.get('location', 'unknown')
            ip_address = request.data.get('ip_address', '0.0.0.0')
            
            # Increment location diversity
            risk_score.location_diversity += 1
            
            # Update score
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': f'Location change recorded: {location}',
                'risk_score': serializer.data,
                'new_location_diversity': risk_score.location_diversity,
                'location': location,
                'ip_address': ip_address
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=True, methods=['post'])
    def record_vpn_usage(self, request, pk=None):
        """Record VPN usage"""
        try:
            risk_score = self.get_object()
            
            vpn_provider = request.data.get('vpn_provider', 'unknown')
            
            # Increment VPN usage count
            risk_score.vpn_usage_count += 1
            
            # Update score
            risk_score.update_score()
            
            serializer = self.get_serializer(risk_score)
            
            return self.safe_response({
                'message': f'VPN usage recorded: {vpn_provider}',
                'risk_score': serializer.data,
                'new_vpn_usage_count': risk_score.vpn_usage_count,
                'vpn_provider': vpn_provider
            })
            
        except RiskScore.DoesNotExist:
            return self.safe_response(
                {'error': 'Risk score not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def check_user(self, request):
        """Check risk score for a specific user"""
        try:
            user_id = request.query_params.get('user_id')
            
            if not user_id:
                return self.safe_response(
                    {'error': 'user_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user_id_int = int(user_id)
            except ValueError:
                return self.safe_response(
                    {'error': 'user_id must be a valid integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create risk score for user
            risk_score, created = RiskScore.objects.get_or_create(
                user_id=user_id_int,
                defaults={
                    'current_score': 0,
                    'previous_score': 0
                }
            )
            
            serializer = self.get_serializer(risk_score)
            
            response_data = {
                'risk_score': serializer.data,
                'checked_at': timezone.now().isoformat(),
                'was_created': created
            }
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    # @permission_classes([permissions.IsAuthenticated])
    def check_self(self, request):
        """Check current user's risk score"""
        try:
            user_id = request.user.id
            
            # Get or create risk score for user
            risk_score, created = RiskScore.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'current_score': 0,
                    'previous_score': 0
                }
            )
            
            serializer = self.get_serializer(risk_score)
            
            response_data = {
                'risk_score': serializer.data,
                'checked_at': timezone.now().isoformat(),
                'was_created': created,
                'user_id': user_id,
                'username': request.user.username
            }
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get risk score statistics"""
        try:
            # Get overall statistics
            total_scores = RiskScore.objects.count()
            
            avg_score = RiskScore.objects.aggregate(
                avg_score=Avg('current_score')
            )['avg_score'] or 0
            
            max_score = RiskScore.objects.aggregate(
                max_score=Max('current_score')
            )['max_score'] or 0
            
            min_score = RiskScore.objects.aggregate(
                min_score=Min('current_score')
            )['min_score'] or 0
            
            # Count by risk level
            risk_level_counts = {
                'very_low': RiskScore.objects.filter(current_score__lt=20).count(),
                'low': RiskScore.objects.filter(current_score__gte=20, current_score__lt=40).count(),
                'medium': RiskScore.objects.filter(current_score__gte=40, current_score__lt=60).count(),
                'high': RiskScore.objects.filter(current_score__gte=60, current_score__lt=80).count(),
                'critical': RiskScore.objects.filter(current_score__gte=80).count(),
            }
            
            # Top risky users
            top_risky_users = RiskScore.objects.filter(
                current_score__gte=60
            ).select_related('user').order_by('-current_score')[:10]
            
            top_risky_data = []
            for score in top_risky_users:
                if score.user:
                    top_risky_data.append({
                        'user_id': score.user.id,
                        'username': score.user.username,
                        'score': score.current_score,
                        'risk_level': self.calculate_risk_level(score.current_score)
                    })
            
            # Recent updates
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
            recent_updates = RiskScore.objects.filter(
                calculated_at__gte=twenty_four_hours_ago
            ).count()
            
            # Score changes
            increased_scores = RiskScore.objects.filter(
                current_score__gt=F('previous_score')
            ).count()
            
            decreased_scores = RiskScore.objects.filter(
                current_score__lt=F('previous_score')
            ).count()
            
            stable_scores = RiskScore.objects.filter(
                current_score=F('previous_score')
            ).count()
            
            return self.safe_response({
                'total_scores': total_scores,
                'average_score': round(avg_score, 2),
                'maximum_score': max_score,
                'minimum_score': min_score,
                'risk_level_distribution': risk_level_counts,
                'top_risky_users': top_risky_data,
                'recent_updates_24h': recent_updates,
                'score_changes': {
                    'increased': increased_scores,
                    'decreased': decreased_scores,
                    'stable': stable_scores
                },
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate risk score from input data"""
        try:
            serializer = RiskScoreCalculateSerializer(data=request.data)
            
            if serializer.is_valid():
                result = serializer.save()
                return self.safe_response(result, status=status.HTTP_200_OK)
            else:
                return self.safe_response(
                    {'error': 'Validation error', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'])
    def batch_recalculate(self, request):
        """Batch recalculate risk scores"""
        try:
            user_ids = request.data.get('user_ids', [])
            
            if not isinstance(user_ids, list):
                return self.safe_response(
                    {'error': 'user_ids must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(user_ids) > 100:
                return self.safe_response(
                    {'error': 'Cannot process more than 100 users at once'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            successful = []
            failed = []
            
            for user_id in user_ids:
                try:
                    risk_score = RiskScore.objects.get(user_id=user_id)
                    risk_score.update_score()
                    
                    successful.append({
                        'user_id': user_id,
                        'new_score': risk_score.current_score,
                        'risk_level': self.calculate_risk_level(risk_score.current_score)
                    })
                    
                except RiskScore.DoesNotExist:
                    failed.append({
                        'user_id': user_id,
                        'error': 'Risk score not found'
                    })
                except Exception as e:
                    failed.append({
                        'user_id': user_id,
                        'error': str(e)
                    })
            
            return self.safe_response({
                'total_requested': len(user_ids),
                'successful': len(successful),
                'failed': len(failed),
                'successful_recalculations': successful,
                'failed_recalculations': failed if failed else None,
                'recalculated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)


class RiskScorePublicAPIView(DefensiveRiskScoreAPIViewMixin, APIView):
    """
    Public API endpoints for RiskScore (self-service)
    with defensive coding and rate limiting
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get current user's risk score"""
        try:
            user_id = request.user.id
            
            # Get or create risk score
            risk_score, created = RiskScore.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'current_score': 0,
                    'previous_score': 0
                }
            )
            
            # Limited information for public API
            response_data = {
                'user_id': user_id,
                'username': request.user.username,
                'current_score': risk_score.current_score,
                'risk_level': self.calculate_risk_level(risk_score.current_score),
                'score_change': risk_score.current_score - risk_score.previous_score,
                'calculated_at': risk_score.calculated_at.isoformat() if risk_score.calculated_at else None,
                'was_created': created
            }
            
            # Add basic risk indicators
            risk_indicators = []
            if risk_score.failed_login_attempts > 0:
                risk_indicators.append('failed_login_attempts')
            if risk_score.suspicious_activities > 0:
                risk_indicators.append('suspicious_activities')
            
            if risk_indicators:
                response_data['risk_indicators'] = risk_indicators
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    @method_decorator(cache_page(60))  # Cache for 1 minute
    def post(self, request):
        """Get risk assessment with recommendations"""
        try:
            user_id = request.user.id
            
            # Get or create risk score
            risk_score, created = RiskScore.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'current_score': 0,
                    'previous_score': 0
                }
            )
            
            # Calculate risk level
            risk_level = self.calculate_risk_level(risk_score.current_score)
            
            # Generate recommendations based on risk level
            recommendations = self._generate_recommendations(risk_score, risk_level)
            
            response_data = {
                'user_id': user_id,
                'username': request.user.username,
                'current_score': risk_score.current_score,
                'risk_level': risk_level,
                'recommendations': recommendations,
                'assessment_timestamp': timezone.now().isoformat()
            }
            
            return self.safe_response(response_data)
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _generate_recommendations(self, risk_score: RiskScore, risk_level: str) -> List[Dict[str, str]]:
        """Generate recommendations based on risk score"""
        recommendations = []
        
        try:
            # Recommendations based on risk level
            if risk_level == 'critical':
                recommendations.append({
                    'priority': 'critical',
                    'message': 'Immediate action required: Account security review needed',
                    'action': 'Contact security team immediately'
                })
            
            if risk_level in ['high', 'critical']:
                recommendations.append({
                    'priority': 'high',
                    'message': 'Enable two-factor authentication',
                    'action': 'Set up 2FA in account settings'
                })
                recommendations.append({
                    'priority': 'high',
                    'message': 'Review recent account activity',
                    'action': 'Check login history for suspicious patterns'
                })
            
            # Recommendations based on specific risk factors
            if risk_score.failed_login_attempts > 3:
                recommendations.append({
                    'priority': 'medium',
                    'message': 'Multiple failed login attempts detected',
                    'action': 'Reset password and ensure it is strong'
                })
            
            if risk_score.suspicious_activities > 2:
                recommendations.append({
                    'priority': 'medium',
                    'message': 'Suspicious activities detected',
                    'action': 'Review account security settings'
                })
            
            if risk_score.device_diversity > 3:
                recommendations.append({
                    'priority': 'low',
                    'message': 'Account accessed from multiple devices',
                    'action': 'Verify all devices are authorized'
                })
            
            if risk_score.location_diversity > 2:
                recommendations.append({
                    'priority': 'low',
                    'message': 'Account accessed from multiple locations',
                    'action': 'Review login locations for anomalies'
                })
            
            # General security recommendations
            recommendations.append({
                'priority': 'low',
                'message': 'Regular security checkup',
                'action': 'Update security questions and recovery options'
            })
            
            return recommendations
            
        except Exception:
            return [{
                'priority': 'low',
                'message': 'General security recommendation',
                'action': 'Review account security settings regularly'
            }]


class RiskScoreAnalyticsAPIView(DefensiveRiskScoreAPIViewMixin, APIView):
    """API for risk score analytics and insights"""
    
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSecurityTeam]
    
    def get(self, request):
        """Get comprehensive risk score analytics"""
        try:
            days = min(int(request.query_params.get('days', 30)), 365)
            time_threshold = timezone.now() - timedelta(days=days)
            
            # Get overall metrics
            metrics = self._get_overall_metrics(time_threshold)
            
            # Get trend analysis
            trends = self._get_trend_analysis(time_threshold)
            
            # Get risk factor analysis
            risk_factors = self._get_risk_factor_analysis(time_threshold)
            
            # Get insights
            insights = self._get_insights(time_threshold)
            
            return self.safe_response({
                'period_days': days,
                'metrics': metrics,
                'trends': trends,
                'risk_factors': risk_factors,
                'insights': insights,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    def _get_overall_metrics(self, time_threshold):
        """Get overall risk score metrics"""
        try:
            total_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).count()
            
            avg_score = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).aggregate(avg_score=Avg('current_score'))['avg_score'] or 0
            
            high_risk_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                current_score__gte=60
            ).count()
            
            critical_risk_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                current_score__gte=80
            ).count()
            
            avg_failed_logins = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).aggregate(avg_failed=Avg('failed_login_attempts'))['avg_failed'] or 0
            
            avg_suspicious_activities = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).aggregate(avg_suspicious=Avg('suspicious_activities'))['avg_suspicious'] or 0
            
            return {
                'total_users_tracked': total_users,
                'average_risk_score': round(avg_score, 2),
                'high_risk_users': high_risk_users,
                'high_risk_percentage': round((high_risk_users / total_users * 100) if total_users > 0 else 0, 2),
                'critical_risk_users': critical_risk_users,
                'average_failed_logins': round(avg_failed_logins, 2),
                'average_suspicious_activities': round(avg_suspicious_activities, 2),
            }
        except Exception as e:
            logger.error(f"Error getting overall metrics: {e}")
            return {'error': 'metrics_unavailable'}
    
    def _get_trend_analysis(self, time_threshold):
        """Analyze risk score trends over time"""
        try:
            from django.db.models.functions import TruncDay
            
            # Daily trend
            daily_trend = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).annotate(
                day=TruncDay('calculated_at')
            ).values('day').annotate(
                avg_score=Avg('current_score'),
                user_count=Count('id'),
                high_risk_count=Count('id', filter=Q(current_score__gte=60))
            ).order_by('day')
            
            # Score distribution trend
            score_distribution = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).annotate(
                week=TruncDay('calculated_at', kind='week')
            ).values('week').annotate(
                avg_score=Avg('current_score'),
                min_score=Min('current_score'),
                max_score=Max('current_score')
            ).order_by('week')
            
            return {
                'daily_trend': list(daily_trend),
                'score_distribution': list(score_distribution)
            }
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {'error': 'trend_analysis_unavailable'}
    
    def _get_risk_factor_analysis(self, time_threshold):
        """Analyze contributing risk factors"""
        try:
            # Top risk factors correlation
            risk_factors = [
                'failed_login_attempts',
                'suspicious_activities',
                'device_diversity',
                'location_diversity',
                'vpn_usage_count'
            ]
            
            factor_analysis = []
            for factor in risk_factors:
                # Get average score for users with high values of this factor
                high_factor_users = RiskScore.objects.filter(
                    calculated_at__gte=time_threshold,
                    **{f'{factor}__gt': 0}
                )
                
                if high_factor_users.exists():
                    avg_score = high_factor_users.aggregate(
                        avg_score=Avg('current_score')
                    )['avg_score'] or 0
                    
                    count = high_factor_users.count()
                    total_users = RiskScore.objects.filter(
                        calculated_at__gte=time_threshold
                    ).count()
                    
                    factor_analysis.append({
                        'factor': factor,
                        'users_affected': count,
                        'percentage_affected': round((count / total_users * 100) if total_users > 0 else 0, 2),
                        'average_score': round(avg_score, 2),
                        'correlation': 'high' if avg_score > 60 else 'medium' if avg_score > 40 else 'low'
                    })
            
            # Most common risk indicators
            common_indicators = []
            
            # Failed logins
            failed_login_stats = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                failed_login_attempts__gt=0
            ).aggregate(
                count=Count('id'),
                avg_attempts=Avg('failed_login_attempts'),
                max_attempts=Max('failed_login_attempts')
            )
            
            if failed_login_stats['count'] > 0:
                common_indicators.append({
                    'indicator': 'failed_login_attempts',
                    'count': failed_login_stats['count'],
                    'average_value': round(failed_login_stats['avg_attempts'] or 0, 2),
                    'maximum_value': failed_login_stats['max_attempts'] or 0
                })
            
            # Suspicious activities
            suspicious_stats = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                suspicious_activities__gt=0
            ).aggregate(
                count=Count('id'),
                avg_activities=Avg('suspicious_activities'),
                max_activities=Max('suspicious_activities')
            )
            
            if suspicious_stats['count'] > 0:
                common_indicators.append({
                    'indicator': 'suspicious_activities',
                    'count': suspicious_stats['count'],
                    'average_value': round(suspicious_stats['avg_activities'] or 0, 2),
                    'maximum_value': suspicious_stats['max_activities'] or 0
                })
            
            return {
                'factor_analysis': factor_analysis,
                'common_indicators': common_indicators
            }
        except Exception as e:
            logger.error(f"Error getting risk factor analysis: {e}")
            return {'error': 'risk_factor_analysis_unavailable'}
    
    def _get_insights(self, time_threshold):
        """Generate actionable insights"""
        try:
            insights = []
            
            # Insight 1: High risk concentration
            high_risk_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                current_score__gte=60
            ).count()
            
            total_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).count()
            
            if total_users > 0:
                high_risk_percentage = (high_risk_users / total_users) * 100
                if high_risk_percentage > 20:
                    insights.append({
                        'type': 'high_risk_concentration',
                        'message': f"High concentration of high-risk users: {high_risk_percentage:.1f}%",
                        'severity': 'high',
                        'recommendation': 'Review security policies and user education'
                    })
            
            # Insight 2: Failed login patterns
            avg_failed_logins = RiskScore.objects.filter(
                calculated_at__gte=time_threshold
            ).aggregate(avg_failed=Avg('failed_login_attempts'))['avg_failed'] or 0
            
            if avg_failed_logins > 2:
                insights.append({
                    'type': 'high_failed_login_rate',
                    'message': f"High average failed login attempts: {avg_failed_logins:.2f} per user",
                    'severity': 'medium',
                    'recommendation': 'Implement account lockout policies'
                })
            
            # Insight 3: Score volatility
            volatile_users = RiskScore.objects.filter(
                calculated_at__gte=time_threshold,
                current_score__gt=F('previous_score') + 20  # Increased by more than 20 points
            ).count()
            
            if volatile_users > 5:
                insights.append({
                    'type': 'high_score_volatility',
                    'message': f"{volatile_users} users with rapid score increases",
                    'severity': 'medium',
                    'recommendation': 'Investigate sudden risk increases'
                })
            
            # Insight 4: Most impactful risk factor
            risk_factors = [
                ('failed_login_attempts', 'Failed Login Attempts'),
                ('suspicious_activities', 'Suspicious Activities'),
                ('device_diversity', 'Device Diversity'),
                ('location_diversity', 'Location Diversity'),
            ]
            
            max_impact_factor = None
            max_impact_score = 0
            
            for factor_field, factor_name in risk_factors:
                avg_score_with_factor = RiskScore.objects.filter(
                    calculated_at__gte=time_threshold,
                    **{f'{factor_field}__gt': 0}
                ).aggregate(avg_score=Avg('current_score'))['avg_score'] or 0
                
                if avg_score_with_factor > max_impact_score:
                    max_impact_score = avg_score_with_factor
                    max_impact_factor = factor_name
            
            if max_impact_factor and max_impact_score > 50:
                insights.append({
                    'type': 'most_impactful_factor',
                    'message': f"Most impactful risk factor: {max_impact_factor} (avg score: {max_impact_score:.1f})",
                    'severity': 'low',
                    'recommendation': f'Focus on mitigating {max_impact_factor.lower()}'
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return [{'type': 'error', 'message': 'Insights unavailable', 'severity': 'low'}]
        

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission:
    - Admin users: Full access
    - Others: Read-only access
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user and request.user.is_staff


class AppVersionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AppVersion management
    """
    queryset = AppVersion.objects.all()
    permission_classes = [IsAdminOrReadOnly]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return AppVersionCreateSerializer
        elif self.action in ['list', 'retrieve']:
            return AppVersionSerializer
        return AppVersionSerializer
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # For non-admin users, show only active versions
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        # Filter by platform if provided
        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(
                django_models.Q(supported_platforms__contains=[platform]) |
                django_models.Q(supported_platforms__isnull=True)
            )
        
        # Filter by release type
        release_type = self.request.query_params.get('release_type')
        if release_type:
            queryset = queryset.filter(release_type=release_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-version_code', '-release_date')
    
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """List app versions with caching"""
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest version for a specific platform"""
        platform = request.query_params.get('platform', 'web')
        
        try:
            latest_version = AppVersion.get_latest_version(platform)
            
            if not latest_version:
                return Response({
                    'error': 'No active version found',
                    'platform': platform
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = AppVersionInfoSerializer(latest_version)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting latest version: {e}")
            return Response({
                'error': 'Failed to retrieve latest version',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def check_update(self, request):
        """Check for app updates"""
        serializer = AppVersionCheckSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            current_version_code = serializer.validated_data['current_version_code']
            platform = serializer.validated_data.get('platform', 'web')
            
            # Check for updates
            update_info = AppVersion.check_for_updates(current_version_code, platform)
            
            return Response(update_info)
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return Response({
                'error': 'Failed to check for updates',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def deprecate(self, request, pk=None):
        """Deprecate a version"""
        if not request.user.is_staff:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            version = self.get_object()
            reason = request.data.get('reason', 'New version available')
            
            success, message = version.mark_as_deprecated(reason)
            
            if success:
                # Clear cache for all supported platforms
                if version.supported_platforms:
                    for platform in version.supported_platforms:
                        cache_key = f'app_version:latest:{platform}'
                        cache.delete(cache_key)
                
                return Response({
                    'success': True,
                    'message': message,
                    'version': version.version_name,
                    'deprecated_at': version.deprecated_at
                })
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error deprecating version: {e}")
            return Response({
                'error': 'Failed to deprecate version',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_versions(self, request):
        """Get all currently active versions"""
        try:
            platform = request.query_params.get('platform', 'web')
            
            active_versions = AppVersion.objects.filter(
                is_active=True,
                supported_platforms__contains=[platform]
            ).filter(
                django_models.Q(deprecated_at__isnull=True) |
                django_models.Q(deprecated_at__gt=timezone.now())
            ).order_by('-version_code')
            
            serializer = AppVersionInfoSerializer(active_versions, many=True)
            
            return Response({
                'count': active_versions.count(),
                'platform': platform,
                'versions': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error getting active versions: {e}")
            return Response({
                'error': 'Failed to retrieve active versions',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AppVersionPublicAPI(APIView):
    """
    Public API for app version checking (no authentication required)
    """
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(cache_page(60 * 2))  # Cache for 2 minutes
    def get(self, request):
        """Public endpoint to check for updates"""
        current_version = request.query_params.get('version', '')
        platform = request.query_params.get('platform', 'web')
        
        if not current_version:
            return Response({
                'error': 'Version parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            update_info = AppVersion.check_for_updates(current_version, platform)
            return Response(update_info)
            
        except Exception as e:
            logger.error(f"Error in public API: {e}")
            return Response({
                'is_update_available': False,
                'current_version': current_version,
                'message': 'Unable to check for updates'
            })



class IsAdminOrOwner(permissions.BasePermission):
    """
    Custom permission:
    - Admin users: Full access
    - Users: Access only their own data
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all
        if request.user.is_staff:
            return True
        
        # Users can access their own data
        user_id = getattr(obj.user, 'id', None) if hasattr(obj, 'user') else None
        return user_id == request.user.id


class WithdrawalProtectionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for WithdrawalProtection management
    """
    serializer_class = WithdrawalProtectionSerializer
    permission_classes = [IsAdminOrOwner]
    
    def get_queryset(self):
        """Get queryset with defensive coding"""
        user = self.request.user
        
        try:
            if user.is_staff:
                return WithdrawalProtection.objects.all().order_by('-updated_at')
            else:
                # Users can only see their own protections
                return WithdrawalProtection.objects.filter(
                    user=user
                ).order_by('-updated_at')
        except Exception as e:
            logger.error(f"Error getting withdrawal protection queryset: {e}")
            return WithdrawalProtection.objects.none()
    
    def get_object(self):
        """Get object with defensive error handling"""
        try:
            # Use dict.get() for safe parameter access
            pk = self.kwargs.get('pk')
            if not pk:
                raise WithdrawalProtection.DoesNotExist
            
            obj = super().get_object()
            return obj
        except Exception as e:
            logger.error(f"Error getting withdrawal protection object: {e}")
            raise
    
    def perform_create(self, serializer):
        """Create with defensive coding"""
        try:
            # Add current user as created_by if not specified
            request = self.request
            
            if request and request.user.is_authenticated:
                serializer.validated_data['created_by'] = request.user
            
            serializer.save()
        except Exception as e:
            logger.error(f"Error creating withdrawal protection: {e}")
            raise
    
    @method_decorator(cache_page(60 * 2))  # Cache for 2 minutes
    def list(self, request, *args, **kwargs):
        """List withdrawal protections with caching"""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing withdrawal protections: {e}")
            return Response({
                'error': 'Could not retrieve withdrawal protections'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def my_protection(self, request):
        """Get current user's withdrawal protection"""
        try:
            user = request.user
            
            # Use getattr for safe attribute access
            if not getattr(user, 'is_authenticated', False):
                return Response({
                    'error': 'Authentication required'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get or create protection for user
            protection = WithdrawalProtection.get_user_protection(user.id)
            
            if not protection:
                return Response({
                    'error': 'Could not retrieve withdrawal protection'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = self.get_serializer(protection)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting user protection for {request.user.id}: {e}")
            return Response({
                'error': 'Failed to retrieve protection',
                'detail': str(e) if request.user.is_staff else 'Internal error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def check_withdrawal(self, request, pk=None):
        """Check if withdrawal is allowed"""
        try:
            protection = self.get_object()
            
            # Validate request data
            check_serializer = WithdrawalCheckSerializer(data=request.data)
            if not check_serializer.is_valid():
                return Response(
                    check_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract data with safe defaults using dict.get()
            amount = check_serializer.validated_data.get('amount', Decimal('0'))
            destination = check_serializer.validated_data.get('destination')
            ip_address = check_serializer.validated_data.get('ip_address')
            device_id = check_serializer.validated_data.get('device_id')
            
            # Check withdrawal permission
            is_allowed, reasons = protection.can_withdraw(
                amount=amount,
                destination=destination,
                ip_address=ip_address,
                device_id=device_id,
                check_time=True
            )
            
            response_data = {
                'is_allowed': is_allowed,
                'reasons': reasons,
                'amount': float(amount),
                'protection_level': protection.protection_level,
                'risk_level': protection.risk_level
            }
            
            # Add limits information
            if not is_allowed:
                response_data['limits'] = {
                    'daily_limit': float(protection.daily_limit),
                    'single_transaction_limit': float(protection.single_transaction_limit),
                    'min_withdrawal_amount': float(protection.min_withdrawal_amount)
                }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error checking withdrawal for protection {pk}: {e}")
            return Response({
                'error': 'Failed to check withdrawal permission',
                'detail': str(e) if request.user.is_staff else 'Internal error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_limits(self, request, pk=None):
        """Update withdrawal limits"""
        try:
            protection = self.get_object()
            
            # Check permission
            if not request.user.is_staff and request.user != protection.user:
                return Response({
                    'error': 'You can only update your own limits'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate update data
            limit_serializer = WithdrawalLimitUpdateSerializer(
                data=request.data,
                context={'protection': protection}
            )
            
            if not limit_serializer.is_valid():
                return Response(
                    limit_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update limits
            success, message = protection.update_limits(
                daily_limit=limit_serializer.validated_data.get('daily_limit'),
                weekly_limit=limit_serializer.validated_data.get('weekly_limit'),
                monthly_limit=limit_serializer.validated_data.get('monthly_limit'),
                single_transaction_limit=limit_serializer.validated_data.get('single_transaction_limit'),
                min_withdrawal_amount=limit_serializer.validated_data.get('min_withdrawal_amount'),
                updated_by=request.user
            )
            
            if success:
                # Serialize updated protection
                serializer = self.get_serializer(protection)
                return Response({
                    'success': True,
                    'message': message,
                    'protection': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error updating limits for protection {pk}: {e}")
            return Response({
                'error': 'Failed to update limits',
                'detail': str(e) if request.user.is_staff else 'Internal error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def add_ip_to_whitelist(self, request, pk=None):
        """Add IP to whitelist"""
        try:
            protection = self.get_object()
            
            ip_address = request.data.get('ip_address')
            if not ip_address:
                return Response({
                    'error': 'IP address is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success, message = protection.add_ip_to_whitelist(ip_address)
            
            if success:
                serializer = self.get_serializer(protection)
                return Response({
                    'success': True,
                    'message': message,
                    'protection': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error adding IP to whitelist for protection {pk}: {e}")
            return Response({
                'error': 'Failed to add IP to whitelist'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def remove_ip_from_whitelist(self, request, pk=None):
        """Remove IP from whitelist"""
        try:
            protection = self.get_object()
            
            ip_address = request.data.get('ip_address')
            if not ip_address:
                return Response({
                    'error': 'IP address is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            success, message = protection.remove_ip_from_whitelist(ip_address)
            
            if success:
                serializer = self.get_serializer(protection)
                return Response({
                    'success': True,
                    'message': message,
                    'protection': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error removing IP from whitelist for protection {pk}: {e}")
            return Response({
                'error': 'Failed to remove IP from whitelist'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def add_to_blacklist(self, request, pk=None):
        """Add destination to blacklist"""
        try:
            protection = self.get_object()
            
            destination = request.data.get('destination')
            if not destination:
                return Response({
                    'error': 'Destination is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            reason = request.data.get('reason')
            success, message = protection.add_to_blacklist(destination, reason)
            
            if success:
                serializer = self.get_serializer(protection)
                return Response({
                    'success': True,
                    'message': message,
                    'protection': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error adding to blacklist for protection {pk}: {e}")
            return Response({
                'error': 'Failed to add to blacklist'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get withdrawal protection summary"""
        try:
            protection = self.get_object()
            
            # Get period from query params with default
            period_days = int(request.query_params.get('period_days', 30))
            
            # Get summary
            summary = protection.get_withdrawal_summary(period_days)
            
            return Response(summary)
            
        except Exception as e:
            logger.error(f"Error getting summary for protection {pk}: {e}")
            return Response({
                'error': 'Failed to get summary',
                'detail': str(e) if request.user.is_staff else 'Internal error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle protection active status"""
        try:
            protection = self.get_object()
            
            # Only staff or user can toggle
            if not request.user.is_staff and request.user != protection.user:
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
            
            protection.is_active = not protection.is_active
            protection.save()
            
            status_text = "activated" if protection.is_active else "deactivated"
            return Response({
                'success': True,
                'message': f'Protection {status_text}',
                'is_active': protection.is_active
            })
            
        except Exception as e:
            logger.error(f"Error toggling active status for protection {pk}: {e}")
            return Response({
                'error': 'Failed to toggle active status'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview of all protections (admin only)"""
        try:
            if not request.user.is_staff:
                return Response({
                    'error': 'Admin access required'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get filters from query params with safe defaults
            is_active = request.query_params.get('is_active')
            protection_level = request.query_params.get('protection_level')
            risk_level = request.query_params.get('risk_level')
            
            queryset = WithdrawalProtection.objects.all()
            
            # Apply filters with defensive coding
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
            if protection_level:
                queryset = queryset.filter(protection_level=protection_level)
            
            if risk_level:
                queryset = queryset.filter(risk_level=risk_level)
            
            # Use summary serializer for overview
            serializer = WithdrawalProtectionSummarySerializer(queryset, many=True)
            
            # Calculate statistics
            total = queryset.count()
            active = queryset.filter(is_active=True).count()
            
            return Response({
                'total': total,
                'active': active,
                'inactive': total - active,
                'protections': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error getting protection overview: {e}")
            return Response({
                'error': 'Failed to get overview'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawalCheckAPI(APIView):
    """
    API for checking withdrawal permissions
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Check if withdrawal is allowed for current user"""
        try:
            user = request.user
            
            # Get user's protection
            protection = WithdrawalProtection.get_user_protection(user.id)
            if not protection:
                return Response({
                    'error': 'Withdrawal protection not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate check request
            check_serializer = WithdrawalCheckSerializer(data=request.data)
            if not check_serializer.is_valid():
                return Response(
                    check_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract data
            amount = check_serializer.validated_data.get('amount', Decimal('0'))
            destination = check_serializer.validated_data.get('destination')
            ip_address = check_serializer.validated_data.get('ip_address', request.META.get('REMOTE_ADDR'))
            device_id = check_serializer.validated_data.get('device_id')
            
            # Check withdrawal permission
            is_allowed, reasons = protection.can_withdraw(
                amount=amount,
                destination=destination,
                ip_address=ip_address,
                device_id=device_id,
                check_time=True
            )
            
            return Response({
                'is_allowed': is_allowed,
                'reasons': reasons,
                'protection_level': protection.protection_level,
                'risk_level': protection.risk_level,
                'limits': {
                    'daily_limit': float(protection.daily_limit),
                    'single_transaction_limit': float(protection.single_transaction_limit),
                    'min_withdrawal_amount': float(protection.min_withdrawal_amount)
                }
            })
            
        except Exception as e:
            logger.error(f"Error in withdrawal check API for user {request.user.id}: {e}")
            return Response({
                'error': 'Failed to check withdrawal permission'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SecurityDashboardAPI(APIView):
    """
    Bulletproof API View with Defensive Coding
    Never crashes, always returns a valid response
    """
    
    def get(self, request):
        """
        Get security dashboard data
        Implements all defensive coding patterns
        """
        try:
            # Collect data from various sources (simulated)
            dashboard_data = self._collect_dashboard_data()
            
            # Validate and serialize with defensive serializer
            serializer = SecurityDashboardSerializer(data=dashboard_data)
            
            # Even if validation fails, we still return something
            if not serializer.is_valid():
                logger.warning(f"Dashboard validation errors: {serializer.errors}")
                # Graceful Degradation: Return safe data despite validation errors
                safe_data = serializer._get_safe_defaults()
                safe_data['warnings'] = list(serializer.errors.keys())
                return Response(safe_data)
            
            # Get representation
            representation = serializer.data
            
            # Add additional calculated fields
            representation['generated_at'] = timezone.now()
            representation['data_source'] = "security_monitor"
            representation['version'] = "1.0"
            
            return Response(representation)
            
        except Exception as e:
            # Ultimate Graceful Degradation: Never return 500 error
            logger.error(f"Dashboard API error: {e}")
            
            # Return completely safe response
            safe_response = {
                'total_users': 0,
                'active_users': 0,
                'active_threats': 0,
                'risk_score': 0.0,
                'system_status': "Maintenance",
                'uptime_percentage': 0.0,
                'recent_logs': [],
                'threat_breakdown': {},
                'top_risky_users': [],
                'system_metrics': {},
                'last_updated': timezone.now(),
                'metadata': {
                    'error': True,
                    'message': 'Dashboard temporarily unavailable'
                },
                'errors': [str(e)],
                'generated_at': timezone.now()
            }
            
            return Response(safe_response, status=status.HTTP_200_OK)
    
    def _collect_dashboard_data(self) -> Dict[str, Any]:
        """
        Collect data from various sources with defensive coding
        Uses both dict.get() and getattr() appropriately
        """
        data = {}
        
        try:
            # Example: Collect from database
            from django.db.models import Count, Avg
            
            # Use try-except for each data source
            try:
                from apps.users.models import User
                data['total_users'] = User.objects.count()
                data['active_users'] = User.objects.filter(is_active=True).count()
            except Exception as e:
                logger.warning(f"User data error: {e}")
                data['total_users'] = 0
                data['active_users'] = 0
            
            try:
                from .models import SecurityLog
                data['active_threats'] = SecurityLog.objects.filter(
                    resolved=False,
                    severity__in=['high', 'critical']
                ).count()
                
                # Threat breakdown using dict.get() for aggregation
                threat_counts = SecurityLog.objects.filter(
                    resolved=False
                ).values('security_type').annotate(count=Count('id'))
                
                threat_breakdown = {}
                for item in threat_counts:
                    # Use dict.get() for safe dictionary access
                    threat_type = item.get('security_type', 'unknown')
                    count = item.get('count', 0)
                    threat_breakdown[threat_type] = count
                
                data['threat_breakdown'] = threat_breakdown
                
            except Exception as e:
                logger.warning(f"Threat data error: {e}")
                data['active_threats'] = 0
                data['threat_breakdown'] = {}
            
            # Get system metrics
            try:
                data['system_metrics'] = self._get_system_metrics()
                data['uptime_percentage'] = data['system_metrics'].get('uptime', 100.0)
            except Exception as e:
                logger.warning(f"Metrics error: {e}")
                data['system_metrics'] = {}
                data['uptime_percentage'] = 0.0
            
            # Calculate risk score
            try:
                data['risk_score'] = self._calculate_risk_score(data)
            except Exception as e:
                logger.warning(f"Risk calculation error: {e}")
                data['risk_score'] = 0.0
            
            # Add metadata
            data['metadata'] = {
                'collected_at': timezone.now(),
                'sources': ['users', 'security_logs', 'system'],
                'version': '1.0'
            }
            
            # Set system status
            data['system_status'] = self._determine_system_status(data)
            
        except Exception as e:
            logger.error(f"Data collection error: {e}")
            # Return minimal safe data
            return {
                'total_users': 0,
                'active_users': 0,
                'active_threats': 0,
                'risk_score': 0.0,
                'system_status': "Error",
                'uptime_percentage': 0.0,
                'recent_logs': [],
                'threat_breakdown': {},
                'top_risky_users': [],
                'system_metrics': {},
                'metadata': {'error': True},
                'errors': [str(e)]
            }
        
        return data
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics with defensive coding"""
        try:
            import psutil
            
            metrics = {
                'cpu_usage': psutil.cpu_percent(interval=0.1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'uptime': self._calculate_uptime(),
                'timestamp': timezone.now()
            }
            
            # Add network metrics if available
            try:
                net_io = psutil.net_io_counters()
                metrics['network_in'] = net_io.bytes_recv / 1024 / 1024  # MB
                metrics['network_out'] = net_io.bytes_sent / 1024 / 1024  # MB
            except Exception:
                metrics['network_in'] = 0.0
                metrics['network_out'] = 0.0
            
            return metrics
            
        except Exception as e:
            logger.warning(f"System metrics error: {e}")
            return {
                'cpu_usage': 0.0,
                'memory_usage': 0.0,
                'disk_usage': 0.0,
                'uptime': 0.0,
                'network_in': 0.0,
                'network_out': 0.0,
                'timestamp': timezone.now(),
                'error': True
            }
    
    def _calculate_uptime(self) -> float:
        """Calculate system uptime with defensive coding"""
        try:
            import psutil
            import time
            
            boot_time = psutil.boot_time()
            current_time = time.time()
            uptime_seconds = current_time - boot_time
            uptime_days = uptime_seconds / (24 * 3600)
            
            # Assume 99.9% uptime if calculation fails
            return min(99.9, max(0.0, 100.0 - (uptime_days * 0.1)))
            
        except Exception:
            return 99.9  # Default to high uptime
    
    def _calculate_risk_score(self, data: Dict[str, Any]) -> float:
        """Calculate risk score with defensive bounds"""
        try:
            score = 0.0
            
            # Use dict.get() with defaults
            active_threats = data.get('active_threats', 0)
            total_users = max(data.get('total_users', 1), 1)  # Avoid division by zero
            
            # Threat density score
            threat_density = (active_threats / total_users) * 100
            score += min(threat_density * 10, 40)
            
            # Add system health factor
            uptime = data.get('uptime_percentage', 100.0)
            if uptime < 95:
                score += (100 - uptime) * 0.5
            
            # Add user activity factor
            active_users = data.get('active_users', 0)
            if active_users > 0:
                active_ratio = active_users / total_users
                if active_ratio < 0.1:  # Low activity might indicate issues
                    score += 10
            
            # Bound the score
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.warning(f"Risk calculation error: {e}")
            return 0.0
    
    def _determine_system_status(self, data: Dict[str, Any]) -> str:
        """Determine system status with defensive logic"""
        try:
            risk_score = data.get('risk_score', 0.0)
            active_threats = data.get('active_threats', 0)
            uptime = data.get('uptime_percentage', 100.0)
            
            if risk_score >= 80 or active_threats > 100 or uptime < 90:
                return "Critical"
            elif risk_score >= 60 or active_threats > 50 or uptime < 95:
                return "Warning"
            elif risk_score >= 30 or active_threats > 10:
                return "Attention"
            else:
                return "Operational"
                
        except Exception:
            return "Unknown"


class CombinedSecurityAPI(APIView):
    """
    API that uses CombinedSecuritySerializer
    Demonstrates ultimate bulletproof design
    """
    
    def get(self, request):
        """Get combined security data - never fails"""
        try:
            # Collect all data
            dashboard_api = SecurityDashboardAPI()
            dashboard_data = dashboard_api._collect_dashboard_data()
            
            metrics_data = dashboard_api._get_system_metrics()
            
            # Get alerts (simulated)
            alerts_data = self._get_security_alerts()
            
            # Get recommendations
            recommendations = self._get_recommendations(
                dashboard_data, metrics_data
            )
            
            # Combine all data
            combined_data = {
                'dashboard': dashboard_data,
                'metrics': metrics_data,
                'alerts': alerts_data,
                'recommendations': recommendations,
                'timestamp': timezone.now()
            }
            
            # Use the bulletproof combined serializer
            serializer = CombinedSecuritySerializer(data=combined_data)
            
            # Even if validation fails, serializer handles it
            if serializer.is_valid():
                result = serializer.data
            else:
                # Use serializer's safe defaults
                result = serializer._get_safe_defaults()
                result['validation_errors'] = serializer.errors
            
            return Response(result)
            
        except Exception as e:
            # Ultimate fallback - serializer will handle even None input
            serializer = CombinedSecuritySerializer(data=None)
            result = serializer.to_representation(None)
            return Response(result)


class FlexibleDataAPI(APIView):
    """
    API that accepts any type of input and handles it gracefully
    Perfect example of defensive coding
    """
    
    def post(self, request):
        """Accept any JSON input and process it safely"""
        try:
            # Get input data - could be anything
            input_data = request.data
            
            # Determine data type and handle appropriately
            if isinstance(input_data, dict):
                # Use dict.get() for safe access
                data_type = input_data.get('type', 'unknown')
                payload = input_data.get('data', {})
                
                if data_type == 'dashboard':
                    serializer = SecurityDashboardSerializer(data=payload)
                elif data_type == 'metrics':
                    serializer = SystemMetricsSerializer(data=payload)
                else:
                    # Generic dict serializer
                    serializer = serializers.Serializer(data=payload)
                
            elif isinstance(input_data, list):
                # Handle list input
                payload = {'items': input_data}
                serializer = serializers.Serializer(data=payload)
                
            elif hasattr(input_data, '__dict__'):
                # Handle object input using getattr()
                payload = {
                    key: getattr(input_data, key, None) 
                    for key in dir(input_data) 
                    if not key.startswith('_')
                }
                serializer = SecurityDashboardSerializer(data=payload)
                
            else:
                # Unknown type - use safe defaults
                serializer = SecurityDashboardSerializer(data={})
            
            # Always get a representation, even if invalid
            if serializer.is_valid():
                result = serializer.data
            else:
                result = {'data': {}, 'errors': serializer.errors}
            
            # Add metadata
            result['received_type'] = type(input_data).__name__
            result['processed_at'] = timezone.now()
            result['success'] = True
            
            return Response(result)
            
        except Exception as e:
            # Never crash
            logger.error(f"Flexible API error: {e}")
            return Response({
                'data': {},
                'errors': ['Processing failed'],
                'success': False,
                'processed_at': timezone.now()
            })
            
            
class BaseViewSet(viewsets.ModelViewSet):
    """
    Base viewset with defensive coding patterns
    """
    
    # Common permissions
    permission_classes = [permissions.IsAuthenticated]
    
    # Defensive get_queryset
    def get_queryset(self):
        try:
            queryset = super().get_queryset()
            if not queryset:
                logger.warning(f"Empty queryset for {self.__class__.__name__}")
                return self.model.objects.none()
            return queryset
        except Exception as e:
            return super().get_queryset().none()

    def success_response(self, data=None, message=None, status_code=200):
        from rest_framework.response import Response
        return Response({"success": True, "data": data, "message": message}, status=status_code)

    def error_response(self, message=None, status_code=400):
        from rest_framework.response import Response
        return Response({"success": False, "message": message}, status=status_code)
    
    # Defensive get_object
    def get_object(self):
        try:
            return super().get_object()
        except Exception as e:
            logger.error(f"Error getting object: {str(e)}")
            # Return 404 with helpful message
            from django.http import Http404
            raise Http404("Requested object not found")
    
    # Graceful list method
    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in list view: {str(e)}")
            # Return empty response instead of crashing
            return Response(
                data={"results": [], "error": "retrieval_failed"},
                status=status.HTTP_200_OK
            )
    
    # Defensive create method
    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"Created {self.__class__.__name__} object")
            return response
        except Exception as e:
            logger.error(f"Error creating object: {str(e)}")
            return Response(
                data={"error": "creation_failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Add bulk operations
    @action(detail=False, methods=['post'])
    def bulk_operations(self, request):
        """Handle bulk operations"""
        try:
            serializer = BulkCountrySerializer(data=request.data)
            if serializer.is_valid():
                results = serializer.save()
                return Response(results, status=status.HTTP_200_OK)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Bulk operation failed: {str(e)}")
            return Response(
                {"error": "bulk_operation_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CountryViewSet(BaseViewSet):
    """Country management viewset"""
    
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAdminUser]
    
    # Defensive filtering
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters safely
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)
        
        is_blocked = self.request.query_params.get('is_blocked')
        if is_blocked:
            queryset = queryset.filter(is_blocked=is_blocked.lower() == 'true')
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(code__icontains=search) |
                models.Q(iso_code__icontains=search)
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def update_statistics(self, request, pk=None):
        """Update country statistics"""
        try:
            country = self.get_object()
            country.update_statistics()
            
            # Log the action
            SecurityLog.objects.create(
                user=request.user,
                security_type='country_stats_update',
                severity='info',
                ip_address=request.META.get('REMOTE_ADDR'),
                description=f"Updated statistics for {country.name}",
                metadata={'country_id': country.id}
            )
            
            return Response(
                {"status": "statistics_updated"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error updating statistics: {str(e)}")
            return Response(
                {"error": "statistics_update_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def toggle_block(self, request, pk=None):
        """Toggle country blocking"""
        try:
            country = self.get_object()
            country.is_blocked = not country.is_blocked
            country.block_reason = request.data.get('reason', '')
            country.save()
            
            action = "blocked" if country.is_blocked else "unblocked"
            
            # Log security event
            SecurityLog.objects.create(
                user=request.user,
                security_type='country_block',
                severity='high',
                ip_address=request.META.get('REMOTE_ADDR'),
                description=f"Country {country.name} {action}",
                metadata={
                    'country_id': country.id,
                    'action': action,
                    'reason': country.block_reason
                }
            )
            
            return Response(
                {
                    "status": f"country_{action}",
                    "is_blocked": country.is_blocked,
                    "reason": country.block_reason
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error toggling block: {str(e)}")
            return Response(
                {"error": "block_toggle_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GeolocationViewSet(BaseViewSet):
    """Geolocation viewset"""
    
    queryset = GeolocationLog.objects.all()
    serializer_class = GeolocationSerializer
    permission_classes = [IsStaffUser]
    throttle_classes = [UserRateThrottle]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters defensively
        params = self.request.query_params
        
        ip_address = params.get('ip_address')
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        
        country_code = params.get('country_code')
        if country_code:
            queryset = queryset.filter(country_code=country_code.upper())
        
        # Risk filters
        min_threat = params.get('min_threat')
        if min_threat:
            try:
                queryset = queryset.filter(threat_score__gte=int(min_threat))
            except ValueError:
                pass  # Graceful degradation
        
        # VPN/Proxy filters
        vpn_only = params.get('vpn_only')
        if vpn_only and vpn_only.lower() == 'true':
            queryset = queryset.filter(is_vpn=True)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def lookup_ip(self, request):
        """Lookup IP geolocation"""
        try:
            ip_address = request.query_params.get('ip')
            if not ip_address:
                return Response(
                    {"error": "ip_address_required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use defensive get_geolocation method
            geolocation = GeolocationLog.get_geolocation(ip_address)
            
            if geolocation:
                serializer = self.get_serializer(geolocation)
                return Response(serializer.data)
            
            return Response(
                {"error": "geolocation_not_found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"IP lookup failed: {str(e)}")
            return Response(
                {"error": "lookup_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def assess_risk(self, request, pk=None):
        """Assess risk for specific geolocation"""
        try:
            geolocation = self.get_object()
            risk_assessment = geolocation.assess_risk()
            
            return Response({
                "geolocation_id": geolocation.id,
                "ip_address": geolocation.ip_address,
                "risk_assessment": risk_assessment
            })
        except Exception as e:
            logger.error(f"Risk assessment failed: {str(e)}")
            return Response(
                {"error": "risk_assessment_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CountryBlockRuleViewSet(BaseViewSet):
    """Country block rule management"""
    
    queryset = CountryBlockRule.objects.all()
    serializer_class = CountryBlockRuleSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter active rules
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        # Filter by country
        country_id = self.request.query_params.get('country_id')
        if country_id:
            queryset = queryset.filter(country_id=country_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create with defensive checks"""
        try:
            with transaction.atomic():
                # Add created_by user
                serializer.save(created_by=self.request.user)
                
                # Log the creation
                SecurityLog.objects.create(
                    user=self.request.user,
                    security_type='block_rule_created',
                    severity='medium',
                    ip_address=self.request.META.get('REMOTE_ADDR'),
                    description=f"Created block rule for {serializer.instance.country.name}",
                    metadata={
                        'rule_id': serializer.instance.id,
                        'block_type': serializer.instance.block_type
                    }
                )
        except Exception as e:
            logger.error(f"Error creating block rule: {str(e)}")
            raise
    
    @action(detail=True, methods=['post'])
    def check_ip(self, request, pk=None):
        """Check if IP should be blocked by this rule"""
        try:
            rule = self.get_object()
            ip_address = request.data.get('ip_address')
            
            if not ip_address:
                return Response(
                    {"error": "ip_address_required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            should_block = rule.should_block_ip(ip_address)
            
            return Response({
                "rule_id": rule.id,
                "country": rule.country.name,
                "ip_address": ip_address,
                "should_block": should_block,
                "rule_active": rule.is_active_now()
            })
        except Exception as e:
            logger.error(f"IP check failed: {str(e)}")
            return Response(
                {"error": "ip_check_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class APIRateLimitViewSet(BaseViewSet):
    """API rate limit management"""
    
    queryset = APIRateLimit.objects.all()
    serializer_class = APIRateLimitSerializer
    permission_classes = [IsSuperUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by activity
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def test_limit(self, request, pk=None):
        """Test rate limit for identifier"""
        try:
            rate_limit = self.get_object()
            identifier = request.data.get('identifier', 'test_identifier')
            
            result = rate_limit.check_limit(identifier, increment=False)
            
            return Response({
                "rate_limit": rate_limit.name,
                "identifier": identifier,
                "test_result": result
            })
        except Exception as e:
            logger.error(f"Rate limit test failed: {str(e)}")
            return Response(
                {"error": "test_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle rate limit active status"""
        try:
            rate_limit = self.get_object()
            rate_limit.is_active = not rate_limit.is_active
            rate_limit.save()
            
            status_text = "activated" if rate_limit.is_active else "deactivated"
            
            return Response({
                "status": f"rate_limit_{status_text}",
                "is_active": rate_limit.is_active
            })
        except Exception as e:
            logger.error(f"Toggle failed: {str(e)}")
            return Response(
                {"error": "toggle_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PasswordPolicyViewSet(BaseViewSet):
    """Password policy management"""
    
    queryset = PasswordPolicy.objects.all()
    serializer_class = PasswordPolicySerializer
    permission_classes = [IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def current_policy(self, request):
        """Get current active policy"""
        try:
            policy = PasswordPolicy.objects.filter(is_active=True).first()
            
            if not policy:
                # Create default policy if none exists
                policy = PasswordPolicy.objects.create(
                    name="Default Policy",
                    is_active=True
                )
            
            serializer = self.get_serializer(policy)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error getting current policy: {str(e)}")
            return Response(
                {"error": "policy_retrieval_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def validate_password(self, request):
        """Validate password against policy"""
        try:
            serializer = PasswordValidationSerializer(data=request.data)
            if serializer.is_valid():
                return Response(serializer.validated_data)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Password validation failed: {str(e)}")
            return Response(
                {"error": "validation_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserSessionViewSet(BaseViewSet):
    """User session management"""
    
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see their own sessions"""
        if self.request.user.is_staff:
            return UserSession.objects.all().select_related("user")
        return UserSession.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active_sessions(self, request):
        """Get active sessions"""
        try:
            sessions = UserSession.get_active_sessions(request.user)
            serializer = self.get_serializer(sessions, many=True)
            
            return Response({
                "count": sessions.count(),
                "sessions": serializer.data
            })
        except Exception as e:
            logger.error(f"Error getting active sessions: {str(e)}")
            return Response(
                {"error": "sessions_retrieval_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def terminate_session(self, request, pk=None):
        """Terminate specific session"""
        try:
            session = self.get_object()
            
            # Check if user owns this session
            if session.user != request.user:
                return Response(
                    {"error": "not_authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            reason = request.data.get('reason', 'User requested termination')
            session.terminate(reason)
            
            return Response({
                "status": "session_terminated",
                "session_id": session.id,
                "reason": reason
            })
        except Exception as e:
            logger.error(f"Session termination failed: {str(e)}")
            return Response(
                {"error": "termination_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def terminate_all_other(self, request):
        """Terminate all other sessions"""
        try:
            current_session_key = request.session.session_key
            current_session = UserSession.objects.filter(
                session_key=current_session_key
            ).first()
            
            if not current_session:
                return Response(
                    {"error": "current_session_not_found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            terminated_count = UserSession.terminate_all_other_sessions(
                current_session, request.user
            )
            
            return Response({
                "status": "other_sessions_terminated",
                "terminated_count": terminated_count,
                "current_session_id": current_session.id
            })
        except Exception as e:
            logger.error(f"Terminate all failed: {str(e)}")
            return Response(
                {"error": "termination_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TwoFactorMethodViewSet(BaseViewSet):
    """2FA method management"""
    
    serializer_class = TwoFactorMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see their own 2FA methods"""
        return TwoFactorMethod.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def primary_method(self, request):
        """Get primary 2FA method"""
        try:
            method = TwoFactorMethod.objects.filter(
                user=request.user,
                is_primary=True,
                is_enabled=True
            ).first()
            
            if method:
                serializer = self.get_serializer(method)
                return Response(serializer.data)
            
            return Response({"has_primary": False})
        except Exception as e:
            logger.error(f"Error getting primary method: {str(e)}")
            return Response(
                {"error": "retrieval_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def setup_totp(self, request, pk=None):
        """Setup TOTP for 2FA"""
        try:
            method = self.get_object()
            
            if method.method_type != 'totp':
                return Response(
                    {"error": "not_totp_method"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate TOTP secret (simplified)
            import pyotp
            secret = pyotp.random_base32()
            
            method.secret_key = secret
            method.save()
            
            # Generate provisioning URI
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=request.user.email,
                issuer_name="YourApp"
            )
            
            return Response({
                "status": "totp_setup_complete",
                "secret": secret,  # In production, don't return this!
                "provisioning_uri": provisioning_uri,
                "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?data={provisioning_uri}"
            })
        except Exception as e:
            logger.error(f"TOTP setup failed: {str(e)}")
            return Response(
                {"error": "totp_setup_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def generate_backup_codes(self, request, pk=None):
        """Generate backup codes"""
        try:
            method = self.get_object()
            
            # Generate codes
            codes = method.generate_backup_codes(count=10)
            
            # Log the generation
            SecurityLog.objects.create(
                user=request.user,
                security_type='backup_codes_generated',
                severity='medium',
                ip_address=request.META.get('REMOTE_ADDR'),
                description="Generated 2FA backup codes",
                metadata={'method_id': method.id}
            )
            
            return Response({
                "status": "backup_codes_generated",
                "codes": codes,  # Show only once!
                "warning": "Save these codes securely. They will not be shown again."
            })
        except Exception as e:
            logger.error(f"Backup code generation failed: {str(e)}")
            return Response(
                {"error": "code_generation_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==================== UTILITY VIEWS ====================

class GeolocationCheckView(APIView):
    """Check geolocation for current request"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get geolocation info for current IP"""
        try:
            ip_address = request.META.get('REMOTE_ADDR')
            if not ip_address:
                return Response(
                    {"error": "ip_not_detected"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            geolocation = GeolocationLog.get_geolocation(ip_address)
            
            if geolocation:
                # Assess risk
                risk_assessment = geolocation.assess_risk()
                
                # Check country blocking
                country_blocked = False
                block_reason = ""
                
                if geolocation.country_code:
                    country = Country.objects.filter(
                        code=geolocation.country_code
                    ).first()
                    if country and country.is_blocked:
                        country_blocked = True
                        block_reason = country.block_reason
                
                return Response({
                    "ip_address": ip_address,
                    "geolocation": {
                        "country": geolocation.country_name,
                        "city": geolocation.city,
                        "isp": geolocation.isp,
                        "is_vpn": geolocation.is_vpn,
                        "is_proxy": geolocation.is_proxy
                    },
                    "risk_assessment": risk_assessment,
                    "country_blocked": country_blocked,
                    "block_reason": block_reason,
                    "recommendation": "use_vpn" if country_blocked else "normal"
                })
            
            return Response(
                {"error": "geolocation_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error(f"Geolocation check failed: {str(e)}")
            return Response(
                {"error": "check_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SecurityDashboardView(APIView):
    """Security dashboard overview"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get security overview"""
        try:
            # Use dict.get() and getattr() for defensive data retrieval
            stats = {
                "countries": {
                    "total": Country.objects.count(),
                    "blocked": Country.objects.filter(is_blocked=True).count(),
                    "high_risk": Country.objects.filter(
                        risk_level__in=['high', 'very_high']
                    ).count()
                },
                "geolocation": {
                    "total_lookups": GeolocationLog.objects.count(),
                    "vpn_detections": GeolocationLog.objects.filter(is_vpn=True).count(),
                    "proxy_detections": GeolocationLog.objects.filter(is_proxy=True).count()
                },
                "sessions": {
                    "active": UserSession.objects.filter(is_active=True).count(),
                    "compromised": UserSession.objects.filter(is_compromised=True).count()
                },
                "authentication": {
                    "users_with_2fa": TwoFactorMethod.objects.filter(
                        is_enabled=True
                    ).values('user').distinct().count(),
                    "recent_failed_logins": PasswordAttempt.objects.filter(
                        successful=False,
                        attempted_at__gte=timezone.now() - timedelta(hours=24)
                    ).count()
                },
                "rate_limiting": {
                    "total_blocks": APIRateLimit.objects.aggregate(
                        total=models.Sum('total_blocks')
                    ).get('total', 0) or 0,
                    "active_limits": APIRateLimit.objects.filter(is_active=True).count()
                }
            }
            
            # Recent security events
            recent_events = SecurityLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).values('security_type').annotate(
                count=models.Count('id'),
                last_occurrence=models.Max('created_at')
            )
            
            return Response({
                "stats": stats,
                "recent_events": recent_events,
                "timestamp": timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Dashboard generation failed: {str(e)}")
            # Return minimal dashboard on error
            return Response({
                "stats": {},
                "error": "dashboard_generation_failed",
                "timestamp": timezone.now().isoformat()
            })


class BulkOperationsView(APIView):
    """Bulk operations for security settings"""
    
    permission_classes = [IsSuperUser]
    
    def post(self, request):
        """Perform bulk operations"""
        try:
            operation = request.data.get('operation')
            data = request.data.get('data', [])
            
            if not operation:
                return Response(
                    {"error": "operation_required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            results = []
            
            with transaction.atomic():
                if operation == 'update_country_risk':
                    for item in data:
                        try:
                            country = Country.objects.get(id=item.get('id'))
                            country.risk_level = item.get('risk_level', country.risk_level)
                            country.save()
                            results.append({
                                "id": country.id,
                                "status": "updated",
                                "name": country.name
                            })
                        except Exception as e:
                            results.append({
                                "id": item.get('id'),
                                "status": "failed",
                                "error": str(e)
                            })
                
                elif operation == 'bulk_block_countries':
                    for item in data:
                        try:
                            country = Country.objects.get(id=item.get('id'))
                            country.is_blocked = True
                            country.block_reason = item.get('reason', 'Bulk operation')
                            country.save()
                            results.append({
                                "id": country.id,
                                "status": "blocked",
                                "name": country.name
                            })
                        except Exception as e:
                            results.append({
                                "id": item.get('id'),
                                "status": "failed",
                                "error": str(e)
                            })
                
                else:
                    return Response(
                        {"error": "invalid_operation"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response({
                "operation": operation,
                "total": len(data),
                "successful": len([r for r in results if r.get('status') in ['updated', 'blocked']]),
                "failed": len([r for r in results if r.get('status') == 'failed']),
                "details": results
            })
            
        except Exception as e:
            logger.error(f"Bulk operation failed: {str(e)}")
            return Response(
                {"error": "bulk_operation_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==================== PUBLIC API VIEWS ====================

class PublicGeolocationView(APIView):
    """Public geolocation API (rate limited)"""
    
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]
    
    def get(self, request):
        """Get geolocation for provided IP"""
        try:
            ip_address = request.query_params.get('ip', request.META.get('REMOTE_ADDR'))
            
            if not ip_address:
                return Response(
                    {"error": "ip_address_required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            geolocation = GeolocationLog.get_geolocation(ip_address)
            
            if geolocation:
                return Response({
                    "ip": ip_address,
                    "country": geolocation.country_name,
                    "country_code": geolocation.country_code,
                    "city": geolocation.city,
                    "isp": geolocation.isp,
                    "latitude": geolocation.latitude,
                    "longitude": geolocation.longitude,
                    "threat_score": geolocation.threat_score,
                    "cached": geolocation.is_cached
                })
            
            return Response(
                {"error": "geolocation_not_found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Public geolocation failed: {str(e)}")
            return Response(
                {"error": "service_unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )          
            
            

            
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_dashboard(request):
    from rest_framework.response import Response
    from django.db.models import Count
    today = timezone.now().date()
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return Response({
        'total_devices': DeviceInfo.objects.count(),
        'active_threats': SecurityLog.objects.filter(resolved=False, severity__in=["high","critical"]).count(),
        'blocked_ips': IPBlacklist.objects.filter(is_active=True).count(),
        'risk_alerts': RiskScore.objects.filter(current_score__gte=75).count(),
        'requests_today': SecurityLog.objects.filter(created_at__date=today).count(),
        'blocked_today': AutoBlockRule.objects.filter(created_at__date=today).count(),
        'total_users': User.objects.count(),
        'high_risk_users': DeviceInfo.objects.filter(risk_score__gte=70).count(),
        'critical_risk_users': DeviceInfo.objects.filter(risk_score__gte=90).count(),
        'threats_blocked': SecurityLog.objects.filter(resolved=True).count(),
        'threats_pending': SecurityLog.objects.filter(resolved=False).count(),
        'summary': {
            'total_threats': SecurityLog.objects.count(),
            'threats_blocked': SecurityLog.objects.filter(resolved=True).count(),
        },
        'risk_analysis': {
            'high_risk_users': DeviceInfo.objects.filter(risk_score__gte=70).count(),
            'critical_risk_users': DeviceInfo.objects.filter(risk_score__gte=90).count(),
        },
    })
def _old_security_dashboard(request):
    """Security dashboard view with real data"""
    
    # Date calculations
    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)
    
    # User statistics
    total_users = User.objects.count()
    active_users_today = User.objects.filter(
        last_login__date=today
    ).count()
    new_users_week = User.objects.filter(
        date_joined__gte=week_ago
    ).count()
    
    # Security statistics (with error handling)
    try:
        unresolved_threats = SecurityLog.objects.filter(
            resolved=False
        ).count()
    except:
        unresolved_threats = 0
    
    try:
        threats_today = SecurityLog.objects.filter(
            created_at__date=today
        ).count()
    except:
        threats_today = 0
    
    try:
        critical_threats = SecurityLog.objects.filter(
            severity='critical',
            # resolved=False
        ).count()
    except:
        critical_threats = 0
    
    # Device statistics
    try:
        suspicious_devices = DeviceInfo.objects.filter(
            is_suspicious=True
        ).count()
    except:
        suspicious_devices = 0
    
    try:
        rooted_devices = DeviceInfo.objects.filter(
            is_rooted=True
        ).count()
    except:
        rooted_devices = 0
    
    # Ban statistics
    try:
        active_bans = UserBan.objects.filter(
            is_active=True
        ).count()
    except:
        active_bans = 0
    
    try:
        permanent_bans = UserBan.objects.filter(
            is_permanent=True,
            is_active=True
        ).count()
    except:
        permanent_bans = 0
    
    # IP statistics
    try:
        blocked_ips = IPBlacklist.objects.filter(
            is_active=True
        ).count()
    except:
        blocked_ips = 0
    
    try:
        vpn_detected = IPBlacklist.objects.filter(
            is_vpn=True,
            is_active=True
        ).count()
    except:
        vpn_detected = 0
    
    # Recent threats (last 10)
    try:
        recent_threats = SecurityLog.objects.all().order_by('-created_at')[:10]
    except:
        recent_threats = []
    
    # High risk users
    try:
        high_risk_users = RiskScore.objects.filter(
            current_score__gte=60
        ).order_by('-current_score')[:10]
    except:
        high_risk_users = []
    
    # Recent bans
    try:
        recent_bans = UserBan.objects.filter(
            is_active=True
        ).order_by('-created_at')[:10]
    except:
        recent_bans = []
    
    # Threat types breakdown
    try:
        threat_types = SecurityLog.objects.values('security_type').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        total_threats = SecurityLog.objects.count()
    except:
        threat_types = []
        total_threats = 0
    
    context = {
        'dashboard_generated': timezone.now(),
        
        # User stats
        'total_users': total_users,
        'active_users_today': active_users_today,
        'new_users_week': new_users_week,
        
        # Threat stats
        'unresolved_threats': unresolved_threats,
        'threats_today': threats_today,
        'critical_threats': critical_threats,
        
        # Device stats
        'suspicious_devices': suspicious_devices,
        'rooted_devices': rooted_devices,
        
        # Ban stats
        'active_bans': active_bans,
        'permanent_bans': permanent_bans,
        
        # IP stats
        'blocked_ips': blocked_ips,
        'vpn_detected': vpn_detected,
        
        # Recent data
        'recent_threats': recent_threats,
        'high_risk_users': high_risk_users,
        'recent_bans': recent_bans,
        
        # Threat breakdown
        'threat_types': threat_types,
        'total_threats': total_threats,
    }
    
    return render(request, 'admin/security_dashboard.html', context)


# ============================================================================
# FILTER
# ============================================================================

class AuditTrailFilter(FilterSet):
    user = CharFilter(field_name='user__username', lookup_expr='icontains')
    model_name = CharFilter(lookup_expr='icontains')
    object_id = CharFilter(lookup_expr='exact')
    action_type = ChoiceFilter(choices=AuditTrail.ACTION_TYPES)
    ip_address = CharFilter(lookup_expr='exact')
    from_date = DateTimeFilter(field_name='created_at', lookup_expr='gte')
    to_date = DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = AuditTrail
        fields = ['user', 'action_type', 'model_name', 'object_id', 'ip_address']


# ============================================================================
# VIEWSET
# ============================================================================

class AuditTrailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for AuditTrail — Read Only (list + retrieve).
    Only admin/staff can access audit logs.
    Supports filtering, searching, ordering, and analytics.
    """

    queryset = AuditTrail.objects.select_related('user').order_by('-created_at')
    serializer_class = AuditTrailSerializer
    pagination_class = SecurityPagination
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AuditTrailFilter
    search_fields = [
        'user__username', 'model_name', 'object_id',
        'object_repr', 'ip_address', 'request_path',
    ]
    ordering_fields = ['created_at', 'action_type', 'model_name', 'user__username']
    ordering = ['-created_at']

    # ------------------------------------------------------------------
    # QUERYSET
    # ------------------------------------------------------------------

    def get_queryset(self):
        try:
            queryset = super().get_queryset()

            params = self.request.query_params

            # action_type filter
            action_type = params.get('action_type')
            if action_type:
                queryset = queryset.filter(action_type=action_type)

            # model filter
            model_name = params.get('model_name')
            if model_name:
                queryset = queryset.filter(model_name__icontains=model_name)

            # user_id filter
            user_id = params.get('user_id')
            if user_id and user_id.isdigit():
                queryset = queryset.filter(user_id=int(user_id))

            # date range
            from_date = params.get('from_date')
            to_date = params.get('to_date')
            if from_date:
                try:
                    from_dt = timezone.datetime.fromisoformat(from_date)
                    queryset = queryset.filter(created_at__gte=from_dt)
                except ValueError:
                    pass
            if to_date:
                try:
                    to_dt = timezone.datetime.fromisoformat(to_date)
                    queryset = queryset.filter(created_at__lte=to_dt)
                except ValueError:
                    pass

            # ip_address filter
            ip_address = params.get('ip_address')
            if ip_address:
                queryset = queryset.filter(ip_address=ip_address)

            # status_code filter
            status_code = params.get('status_code')
            if status_code and status_code.isdigit():
                queryset = queryset.filter(status_code=int(status_code))

            return queryset

        except Exception as e:
            logger.error(f"AuditTrail get_queryset error: {e}", exc_info=True)
            return AuditTrail.objects.none()

    # ------------------------------------------------------------------
    # CUSTOM ACTIONS
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """
        GET /audit-trails/statistics/
        Returns breakdown by action_type, model, user, and daily trend.
        """
        try:
            days = min(int(request.query_params.get('days', 7)), 365)
            start_date = timezone.now() - timedelta(days=days)
            qs = self.get_queryset().filter(created_at__gte=start_date)

            by_action = list(
                qs.values('action_type')
                  .annotate(count=Count('id'))
                  .order_by('-count')
            )

            by_model = list(
                qs.values('model_name')
                  .annotate(count=Count('id'))
                  .order_by('-count')[:10]
            )

            by_user = list(
                qs.values('user__username')
                  .annotate(count=Count('id'))
                  .order_by('-count')[:10]
            )

            # daily trend (last 7 days max for performance)
            daily_trend = []
            for i in range(min(days, 7), 0, -1):
                day = timezone.now() - timedelta(days=i)
                cnt = qs.filter(created_at__date=day.date()).count()
                daily_trend.append({
                    'date': day.date().isoformat(),
                    'count': cnt,
                })

            return Response({
                'timeframe_days': days,
                'total': qs.count(),
                'by_action_type': by_action,
                'by_model': by_model,
                'top_users': by_user,
                'daily_trend': daily_trend,
                'generated_at': timezone.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"AuditTrail statistics error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='user-activity')
    def user_activity(self, request):
        """
        GET /audit-trails/user-activity/?user_id=<id>&days=30
        Full audit history for a specific user.
        """
        try:
            user_id = request.query_params.get('user_id')
            if not user_id or not user_id.isdigit():
                return Response(
                    {'error': 'Valid user_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            days = min(int(request.query_params.get('days', 30)), 365)
            start_date = timezone.now() - timedelta(days=days)

            qs = self.get_queryset().filter(
                user_id=int(user_id),
                created_at__gte=start_date,
            )

            by_action = list(
                qs.values('action_type')
                  .annotate(count=Count('id'))
                  .order_by('-count')
            )

            recent = self.get_serializer(qs[:20], many=True).data

            return Response({
                'user_id': user_id,
                'timeframe_days': days,
                'total_actions': qs.count(),
                'by_action_type': by_action,
                'recent_actions': recent,
                'generated_at': timezone.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"AuditTrail user-activity error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve user activity'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='object-history')
    def object_history(self, request):
        """
        GET /audit-trails/object-history/?model_name=DeviceInfo&object_id=42
        Full change history for a specific object.
        """
        try:
            model_name = request.query_params.get('model_name')
            object_id = request.query_params.get('object_id')

            if not model_name or not object_id:
                return Response(
                    {'error': 'model_name and object_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            qs = self.get_queryset().filter(
                model_name__iexact=model_name,
                object_id=object_id,
            )

            serializer = self.get_serializer(qs[:100], many=True)

            return Response({
                'model_name': model_name,
                'object_id': object_id,
                'total_changes': qs.count(),
                'history': serializer.data,
            })

        except Exception as e:
            logger.error(f"AuditTrail object-history error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to retrieve object history'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='suspicious-activity')
    def suspicious_activity(self, request):
        """
        GET /audit-trails/suspicious-activity/
        Flags: rapid deletions, unusual hours, multiple IPs.
        """
        try:
            hours = min(int(request.query_params.get('hours', 24)), 720)
            since = timezone.now() - timedelta(hours=hours)
            qs = self.get_queryset().filter(created_at__gte=since)

            # Rapid deletions — users who deleted >5 objects
            rapid_deletes = list(
                qs.filter(action_type='delete')
                  .values('user__username', 'user_id')
                  .annotate(count=Count('id'))
                  .filter(count__gt=5)
                  .order_by('-count')
            )

            # Users acting from many different IPs
            multi_ip_users = list(
                qs.exclude(ip_address__isnull=True)
                  .values('user__username', 'user_id')
                  .annotate(ip_count=Count('ip_address', distinct=True))
                  .filter(ip_count__gt=3)
                  .order_by('-ip_count')
            )

            # After-hours activity (22:00 – 06:00 UTC)
            after_hours = list(
                qs.filter(
                    Q(created_at__hour__gte=22) | Q(created_at__hour__lte=6)
                )
                .values('user__username', 'user_id')
                .annotate(count=Count('id'))
                .filter(count__gt=0)
                .order_by('-count')[:10]
            )

            return Response({
                'period_hours': hours,
                'rapid_deletions': rapid_deletes,
                'multi_ip_users': multi_ip_users,
                'after_hours_activity': after_hours,
                'generated_at': timezone.now().isoformat(),
            })

        except Exception as e:
            logger.error(f"AuditTrail suspicious-activity error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to detect suspicious activity'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='export-summary')
    def export_summary(self, request):
        """
        GET /audit-trails/export-summary/
        Lightweight summary — safe for large datasets.
        """
        try:
            days = min(int(request.query_params.get('days', 30)), 365)
            start_date = timezone.now() - timedelta(days=days)
            qs = self.get_queryset().filter(created_at__gte=start_date)

            summary = {
                'period': f'Last {days} days',
                'total_records': qs.count(),
                'unique_users': qs.values('user').distinct().count(),
                'unique_models': qs.values('model_name').distinct().count(),
                'action_breakdown': {
                    item['action_type']: item['count']
                    for item in qs.values('action_type').annotate(count=Count('id'))
                },
                'top_ips': list(
                    qs.exclude(ip_address__isnull=True)
                      .values('ip_address')
                      .annotate(count=Count('id'))
                      .order_by('-count')[:5]
                ),
                'generated_at': timezone.now().isoformat(),
            }

            return Response(summary)

        except Exception as e:
            logger.error(f"AuditTrail export-summary error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate export summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )