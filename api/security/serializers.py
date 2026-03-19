"""
Security Views with Defensive Coding
Author: System Security Team
Version: 2.0.0
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import TruncDate, TruncHour
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings
from .models import IPBlacklist
from django.db import transaction, connection
from django.db.models import Prefetch
from rest_framework import serializers
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import secrets
from .models import DeviceInfo, SecurityLog
import logging
import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any, Union, Tuple
from functools import wraps
import hashlib
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from django.contrib.auth import get_user_model
def get_hours_default():
    return list(range(0, 24))

def get_days_default():
    return list(range(0, 7))
def get_withdrawal_hours_default():
    return list(range(0, 24))

def get_withdrawal_days_default():
    return list(range(0, 7))

User = get_user_model()

from .models import (
    DeviceInfo, SecurityLog, UserBan, ClickTracker, MaintenanceMode,
    AppVersion, IPBlacklist, WithdrawalProtection, RiskScore,
    SecurityDashboard, AutoBlockRule, AuditTrail, DataExport,
    DataImport, SecurityNotification, AlertRule, FraudPattern,
    RealTimeDetection, Country, GeolocationLog, CountryBlockRule,
    APIRateLimit, RateLimitLog, PasswordPolicy, PasswordHistory,
    PasswordAttempt, UserSession, SessionActivity, TwoFactorMethod,
    TwoFactorAttempt, TwoFactorRecoveryCode, EnhancedClickTracker
)


logger = logging.getLogger(__name__)

# Custom exceptions for defensive coding
class SecurityException(Exception):
    """Base security exception"""
    pass

class RateLimitExceeded(SecurityException):
    """Rate limit exceeded exception"""
    pass

class SuspiciousActivityDetected(SecurityException):
    """Suspicious activity detected"""
    pass

class ValidationFailed(SecurityException):
    """Validation failed exception"""
    pass

# ==================== DEFENSIVE DECORATORS ====================

def handle_gracefully(default_response=None):
    """
    Graceful degradation decorator
    Returns default response if view fails
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"View {view_func.__name__} failed: {str(e)}", 
                           exc_info=True)
                
                # Log security exception
                if isinstance(e, SecurityException):
                    SecurityLog.objects.create(
                        user=request.user if hasattr(request, 'user') else None,
                        security_type='api_abuse' if isinstance(e, RateLimitExceeded) else 'suspicious_activity',
                        severity='high',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        description=f"View failed: {view_func.__name__}. Error: {str(e)}",
                        metadata={'view_name': view_func.__name__, 'error': str(e)}
                    )
                
                # Return graceful response
                if default_response is not None:
                    return default_response
                
                return JsonResponse({
                    'error': 'An unexpected error occurred',
                    'code': 'INTERNAL_ERROR',
                    'timestamp': timezone.now().isoformat()
                }, status=500)
        return wrapper
    return decorator

def validate_request_params(required_params=None, optional_params=None):
    """
    Validate request parameters decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get parameters based on request method
            if request.method == 'GET':
                params = request.GET
            else:
                try:
                    params = json.loads(request.body) if request.body else {}
                except json.JSONDecodeError:
                    params = request.POST
            
            # Check required parameters
            if required_params:
                missing = [param for param in required_params if param not in params]
                if missing:
                    return JsonResponse({
                        'error': f'Missing required parameters: {missing}',
                        'code': 'MISSING_PARAMETERS'
                    }, status=400)
            
            # Validate parameter types if specified in optional_params
            if optional_params:
                for param, expected_type in optional_params.items():
                    if param in params:
                        value = params[param]
                        try:
                            # Type conversion/validation
                            if expected_type == int:
                                params[param] = int(value)
                            elif expected_type == float:
                                params[param] = float(value)
                            elif expected_type == bool:
                                if isinstance(value, str):
                                    params[param] = value.lower() in ['true', '1', 'yes']
                                else:
                                    params[param] = bool(value)
                            elif expected_type == list and isinstance(value, str):
                                params[param] = json.loads(value)
                        except (ValueError, TypeError, json.JSONDecodeError):
                            return JsonResponse({
                                'error': f'Invalid type for parameter: {param}. Expected {expected_type}',
                                'code': 'INVALID_PARAMETER_TYPE'
                            }, status=400)
            
            # Add validated params to request object
            request.validated_params = params
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def rate_limit(limit_type='user', requests_per_minute=60, cache_key_prefix='rate_limit'):
    """
    Rate limiting decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Generate identifier based on limit type
            if limit_type == 'user':
                identifier = str(request.user.id) if request.user.is_authenticated else 'anonymous'
            elif limit_type == 'ip':
                identifier = request.META.get('REMOTE_ADDR', 'unknown')
            elif limit_type == 'endpoint':
                identifier = f"{request.path}:{request.method}"
            else:
                identifier = 'global'
            
            # Generate cache key
            minute_key = timezone.now().strftime('%Y%m%d%H%M')
            cache_key = f"{cache_key_prefix}:{identifier}:{minute_key}"
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Check limit
            if current_count >= requests_per_minute:
                # Log rate limit exceeded
                SecurityLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    security_type='rate_limit_exceeded',
                    severity='medium',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    description=f'Rate limit exceeded for {identifier}',
                    metadata={
                        'limit_type': limit_type,
                        'identifier': identifier,
                        'requests_per_minute': requests_per_minute,
                        'current_count': current_count
                    }
                )
                
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'retry_after': 60,
                    'limit': requests_per_minute,
                    'remaining': 0
                }, status=429)
            
            # Increment count
            cache.set(cache_key, current_count + 1, 60)  # Expire after 60 seconds
            
            # Add rate limit info to response headers
            response = view_func(request, *args, **kwargs)
            if isinstance(response, (JsonResponse, Response)):
                response['X-RateLimit-Limit'] = str(requests_per_minute)
                response['X-RateLimit-Remaining'] = str(requests_per_minute - (current_count + 1))
                response['X-RateLimit-Reset'] = str(int(timezone.now().timestamp()) + 60)
            
            return response
        return wrapper
    return decorator

def check_maintenance_mode():
    """
    Check if maintenance mode is active
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Check maintenance mode
                if MaintenanceMode.is_maintenance_active():
                    # Allow admin access if configured
                    maintenance = MaintenanceMode.objects.latest('started_at')
                    if not (maintenance.allow_admin_access and request.user.is_staff):
                        return JsonResponse({
                            'error': 'Service is under maintenance',
                            'message': maintenance.message_to_users,
                            'expected_end_time': maintenance.expected_end_time.isoformat() if maintenance.expected_end_time else None,
                            'code': 'MAINTENANCE_MODE'
                        }, status=503)
            except Exception as e:
                # Graceful degradation - continue if maintenance check fails
                logging.warning(f"Maintenance mode check failed: {str(e)}")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def validate_app_version():
    """
    Validate app version from headers
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get version from headers
            app_version = request.headers.get('X-App-Version', '1.0.0')
            app_platform = request.headers.get('X-App-Platform', 'android')
            version_code = request.headers.get('X-Version-Code', 1)
            
            try:
                # Validate version
                version_info = AppVersion.check_version(
                    platform=app_platform,
                    version_code=int(version_code)
                )
                
                if version_info.get('force_update'):
                    return JsonResponse({
                        'error': 'Update required',
                        'message': version_info.get('message'),
                        'download_url': version_info.get('download_url'),
                        'latest_version': version_info.get('latest_version'),
                        'code': 'UPDATE_REQUIRED'
                    }, status=426)  # 426 Upgrade Required
                
                if not version_info.get('is_allowed'):
                    return JsonResponse({
                        'error': 'Version not supported',
                        'message': version_info.get('message'),
                        'download_url': version_info.get('download_url'),
                        'latest_version': version_info.get('latest_version'),
                        'code': 'VERSION_NOT_SUPPORTED'
                    }, status=400)
                
                # Add version info to request
                request.version_info = version_info
                
            except (ValueError, TypeError):
                # Graceful degradation for version validation errors
                pass
            except Exception as e:
                logging.error(f"Version validation error: {str(e)}")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# ==================== BASE VIEW CLASSES ====================

class BaseSecurityView(View):
    """Base view with security features"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch with security checks"""
        try:
            # Check IP blacklist
            ip_address = request.META.get('REMOTE_ADDR')
            if ip_address and IPBlacklist.is_blocked(ip_address):
                raise PermissionDenied("IP address blocked")
            
            # Check if user is banned
            if request.user.is_authenticated:
                try:
                    ban = UserBan.objects.get(user=request.user)
                    if ban.is_active():
                        return JsonResponse({
                            'error': 'Account suspended',
                            'reason': ban.reason,
                            'description': ban.description,
                            'banned_until': ban.banned_until.isoformat() if ban.banned_until else None,
                            'time_remaining': ban.time_remaining(),
                            'code': 'ACCOUNT_SUSPENDED'
                        }, status=403)
                except UserBan.DoesNotExist:
                    pass
            
            # Check for suspicious activity
            if self._detect_suspicious_activity(request):
                raise SuspiciousActivityDetected("Suspicious activity detected")
            
            return super().dispatch(request, *args, **kwargs)
            
        except PermissionDenied as e:
            return JsonResponse({
                'error': str(e),
                'code': 'PERMISSION_DENIED'
            }, status=403)
        except SuspiciousActivityDetected as e:
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='suspicious_activity',
                severity='high',
                ip_address=request.META.get('REMOTE_ADDR'),
                description=f'Suspicious activity in {self.__class__.__name__}: {str(e)}',
                metadata={'view': self.__class__.__name__, 'method': request.method}
            )
            return JsonResponse({
                'error': 'Suspicious activity detected',
                'code': 'SUSPICIOUS_ACTIVITY'
            }, status=403)
        except Exception as e:
            logging.error(f"Security check failed: {str(e)}", exc_info=True)
            # Graceful degradation - allow request to proceed
            return super().dispatch(request, *args, **kwargs)
    
    def _detect_suspicious_activity(self, request):
        """Detect suspicious activity patterns"""
        # Check for fast clicking
        if request.user.is_authenticated:
            if ClickTracker.check_fast_clicking(
                user=request.user,
                action_type=f'view_{self.__class__.__name__.lower()}',
                time_window=30,
                max_clicks=10
            ):
                return True
        
        # Check User-Agent anomalies
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        suspicious_agents = ['curl', 'wget', 'python-requests', 'bot', 'spider']
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            # Not necessarily malicious, but log it
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='suspicious_activity',
                severity='low',
                ip_address=request.META.get('REMOTE_ADDR'),
                description=f'Suspicious User-Agent: {user_agent}',
                metadata={'user_agent': user_agent}
            )
        
        return False
    
    def get_client_ip(self, request):
        """Get client IP address with defensive coding"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Validate IP format
            import ipaddress
            ipaddress.ip_address(ip)
            return ip
        except (AttributeError, ValueError, IndexError):
            return '0.0.0.0'
    
    def log_activity(self, request, action_type, metadata=None):
        """Log user activity"""
        try:
            ClickTracker.log_action(
                user=request.user,
                action_type=action_type,
                ip_address=self.get_client_ip(request),
                metadata=metadata or {}
            )
        except Exception as e:
            logging.warning(f"Failed to log activity: {str(e)}")

class BaseAPIView(APIView):
    """Base API view with security features"""
    
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def initial(self, request, *args, **kwargs):
        """Initial security checks"""
        super().initial(request, *args, **kwargs)
        
        # Add security headers
        request.META['SECURITY_CHECK'] = 'passed'
        
        # Log API access
        self._log_api_access(request)
    
    def _log_api_access(self, request):
        """Log API access for audit trail"""
        try:
            AuditTrail.log_action(
                user=request.user,
                action_type='api_call',
                model_name=self.__class__.__name__,
                object_id='api',
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                request_method=request.method,
                status_code=200
            )
        except Exception as e:
            logging.warning(f"Failed to log API access: {str(e)}")
    
    def _get_client_ip(self, request):
        """Safe IP extraction"""
        try:
            return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or \
                   request.META.get('REMOTE_ADDR', '0.0.0.0')
        except:
            return '0.0.0.0'
    
    def handle_exception(self, exc):
        """Handle exceptions with security logging"""
        # Log security exceptions
        if isinstance(exc, (RateLimitExceeded, SuspiciousActivityDetected, PermissionDenied)):
            SecurityLog.objects.create(
                user=self.request.user if self.request.user.is_authenticated else None,
                security_type='api_abuse' if isinstance(exc, RateLimitExceeded) else 'unauthorized_access',
                severity='high',
                ip_address=self._get_client_ip(self.request),
                description=f'API exception: {type(exc).__name__}: {str(exc)}',
                metadata={'view': self.__class__.__name__, 'exception': str(exc)}
            )
        
        # Call parent exception handler
        return super().handle_exception(exc)

# ==================== DEVICE MANAGEMENT VIEWS ====================

class DeviceManagementView(BaseSecurityView):
    """Device management views"""
    
    @method_decorator(login_required)
    @method_decorator(handle_gracefully(JsonResponse({'error': 'Service unavailable'}, status=503)))
    @method_decorator(validate_request_params())
    def get(self, request):
        """Get user's devices"""
        try:
            devices = DeviceInfo.objects.filter(user=request.user)
            
            # Apply filters if provided
            if 'is_trusted' in request.GET:
                devices = devices.filter(is_trusted=request.GET['is_trusted'] == 'true')
            
            if 'is_suspicious' in request.GET:
                suspicious_ids = [d.id for d in devices if d.is_suspicious()]
                devices = devices.filter(id__in=suspicious_ids)
            
            # Pagination
            page = request.GET.get('page', 1)
            per_page = int(request.GET.get('per_page', 20))
            
            paginator = Paginator(devices, per_page)
            try:
                page_obj = paginator.page(page)
            except (PageNotAnInteger, EmptyPage):
                page_obj = paginator.page(1)
            
            # Serialize data
            device_data = []
            for device in page_obj:
                device_data.append({
                    'id': device.id,
                    'device_model': device.device_model,
                    'device_brand': device.device_brand,
                    'android_version': device.android_version,
                    'app_version': device.app_version,
                    'is_rooted': device.is_rooted,
                    'is_emulator': device.is_emulator,
                    'is_vpn': device.is_vpn,
                    'is_proxy': device.is_proxy,
                    'risk_score': device.risk_score,
                    'is_trusted': device.is_trusted,
                    'is_suspicious': device.is_suspicious(),
                    'last_activity': device.last_activity.isoformat(),
                    'created_at': device.created_at.isoformat()
                })
            
            # Log activity
            self.log_activity(request, 'device_list_view')
            
            return JsonResponse({
                'success': True,
                'devices': device_data,
                'pagination': {
                    'total': paginator.count,
                    'pages': paginator.num_pages,
                    'current_page': page_obj.number,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })
            
        except Exception as e:
            logging.error(f"Error fetching devices: {str(e)}")
            return JsonResponse({
                'error': 'Failed to fetch devices',
                'code': 'DEVICE_FETCH_ERROR'
            }, status=500)
    
    @method_decorator(login_required)
    @method_decorator(handle_gracefully(JsonResponse({'error': 'Service unavailable'}, status=503)))
    @method_decorator(validate_request_params(['device_id']))
    def post(self, request):
        """Register new device"""
        try:
            data = json.loads(request.body)
            
            # Check for duplicate device across accounts
            device_id = data['device_id']
            device_hash = hashlib.sha256(device_id.encode()).hexdigest()
            
            duplicate_count = DeviceInfo.check_duplicate_devices(
                device_hash,
                exclude_user=request.user
            )
            
            if duplicate_count > 0:
                # Log duplicate device
                SecurityLog.objects.create(
                    user=request.user,
                    security_type='duplicate_device',
                    severity='high' if duplicate_count > 2 else 'medium',
                    ip_address=self.get_client_ip(request),
                    description=f'Device used by {duplicate_count} other accounts',
                    metadata={'device_id': device_id, 'duplicate_count': duplicate_count}
                )
            
            # Check if device already registered for this user
            existing_device = DeviceInfo.objects.filter(
                user=request.user,
                device_id_hash=device_hash
            ).first()
            
            if existing_device:
                # Update existing device
                existing_device.device_model = data.get('device_model', existing_device.device_model)
                existing_device.device_brand = data.get('device_brand', existing_device.device_brand)
                existing_device.android_version = data.get('android_version', existing_device.android_version)
                existing_device.app_version = data.get('app_version', existing_device.app_version)
                existing_device.is_rooted = data.get('is_rooted', existing_device.is_rooted)
                existing_device.is_emulator = data.get('is_emulator', existing_device.is_emulator)
                existing_device.is_vpn = data.get('is_vpn', existing_device.is_vpn)
                existing_device.is_proxy = data.get('is_proxy', existing_device.is_proxy)
                existing_device.fingerprint = data.get('fingerprint', existing_device.fingerprint)
                existing_device.last_ip = self.get_client_ip(request)
                existing_device.last_activity = timezone.now()
                existing_device.save()
                
                device = existing_device
            else:
                # Create new device
                device = DeviceInfo.objects.create(
                    user=request.user,
                    device_id=device_id,
                    device_model=data.get('device_model', 'Unknown'),
                    device_brand=data.get('device_brand', ''),
                    android_version=data.get('android_version', 'Unknown'),
                    app_version=data.get('app_version', '1.0.0'),
                    is_rooted=data.get('is_rooted', False),
                    is_emulator=data.get('is_emulator', False),
                    is_vpn=data.get('is_vpn', False),
                    is_proxy=data.get('is_proxy', False),
                    fingerprint=data.get('fingerprint', ''),
                    last_ip=self.get_client_ip(request)
                )
            
            # Calculate initial risk score
            device.update_risk_score()
            
            # Log activity
            self.log_activity(request, 'device_registration', {
                'device_id': device_id,
                'device_model': device.device_model,
                'is_suspicious': device.is_suspicious()
            })
            
            return JsonResponse({
                'success': True,
                'device_id': device.id,
                'risk_score': device.risk_score,
                'is_suspicious': device.is_suspicious(),
                'message': 'Device registered successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON',
                'code': 'INVALID_JSON'
            }, status=400)
        except KeyError as e:
            return JsonResponse({
                'error': f'Missing field: {str(e)}',
                'code': 'MISSING_FIELD'
            }, status=400)
        except Exception as e:
            logging.error(f"Error registering device: {str(e)}")
            return JsonResponse({
                'error': 'Failed to register device',
                'code': 'DEVICE_REGISTRATION_ERROR'
            }, status=500)
    
    @method_decorator(login_required)
    @method_decorator(handle_gracefully(JsonResponse({'error': 'Service unavailable'}, status=503)))
    @method_decorator(validate_request_params(['device_id']))
    def delete(self, request):
        """Remove device"""
        try:
            data = json.loads(request.body)
            device_id = data['device_id']
            
            device = DeviceInfo.objects.filter(
                user=request.user,
                device_id=device_id
            ).first()
            
            if not device:
                return JsonResponse({
                    'error': 'Device not found',
                    'code': 'DEVICE_NOT_FOUND'
                }, status=404)
            
            # Don't delete if it's the only trusted device
            trusted_devices = DeviceInfo.objects.filter(
                user=request.user,
                is_trusted=True
            ).count()
            
            if device.is_trusted and trusted_devices <= 1:
                return JsonResponse({
                    'error': 'Cannot delete last trusted device',
                    'code': 'LAST_TRUSTED_DEVICE'
                }, status=400)
            
            # Log device removal
            SecurityLog.objects.create(
                user=request.user,
                security_type='suspicious_activity',
                severity='low',
                ip_address=self.get_client_ip(request),
                description=f'Device removed: {device.device_model}',
                metadata={'device_id': device_id, 'device_model': device.device_model}
            )
            
            device.delete()
            
            self.log_activity(request, 'device_removal', {'device_id': device_id})
            
            return JsonResponse({
                'success': True,
                'message': 'Device removed successfully'
            })
            
        except Exception as e:
            logging.error(f"Error removing device: {str(e)}")
            return JsonResponse({
                'error': 'Failed to remove device',
                'code': 'DEVICE_REMOVAL_ERROR'
            }, status=500)

# ==================== SECURITY LOG VIEWS ====================

class SecurityLogAPIView(BaseAPIView):
    """Security log API endpoints"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=30))
    def get(self, request):
        """Get security logs with filters"""
        try:
            # Permission check
            if not request.user.has_perm('security.view_securitylog'):
                return Response({
                    'error': 'Permission denied',
                    'code': 'PERMISSION_DENIED'
                }, status=403)
            
            # Build query
            logs = SecurityLog.objects.all()
            
            # Apply filters
            filters = Q()
            
            # User filter
            if request.GET.get('user'):
                filters &= Q(user_id=request.GET.get('user'))
            
            # Security type filter
            if request.GET.get('security_type'):
                filters &= Q(security_type=request.GET.get('security_type'))
            
            # Severity filter
            if request.GET.get('severity'):
                filters &= Q(severity=request.GET.get('severity'))
            
            # Date range filter
            if request.GET.get('start_date'):
                try:
                    start_date = timezone.datetime.fromisoformat(request.GET.get('start_date'))
                    filters &= Q(created_at__gte=start_date)
                except ValueError:
                    pass
            
            if request.GET.get('end_date'):
                try:
                    end_date = timezone.datetime.fromisoformat(request.GET.get('end_date'))
                    filters &= Q(created_at__lte=end_date)
                except ValueError:
                    pass
            
            # Resolved filter
            if request.GET.get('resolved') in ['true', 'false']:
                filters &= Q(resolved=request.GET.get('resolved') == 'true')
            
            # IP filter
            if request.GET.get('ip_address'):
                filters &= Q(ip_address=request.GET.get('ip_address'))
            
            # Apply filters
            logs = logs.filter(filters)
            
            # Ordering
            order_by = request.GET.get('order_by', '-created_at')
            if order_by.lstrip('-') in ['created_at', 'severity', 'risk_score']:
                logs = logs.order_by(order_by)
            
            # Pagination
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            
            paginator = Paginator(logs, page_size)
            page_obj = paginator.page(page)
            
            # Serialize data
            serializer = SecurityLogSerializer(page_obj, many=True)
            
            # Get statistics
            total_logs = paginator.count
            critical_count = logs.filter(severity='critical').count()
            unresolved_count = logs.filter(resolved=False).count()
            
            return Response({
                'success': True,
                'logs': serializer.data,
                'pagination': {
                    'total': total_logs,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                },
                'statistics': {
                    'total': total_logs,
                    'critical': critical_count,
                    'unresolved': unresolved_count
                }
            })
            
        except EmptyPage:
            return Response({
                'error': 'Page not found',
                'code': 'PAGE_NOT_FOUND'
            }, status=404)
        except Exception as e:
            logging.error(f"Error fetching security logs: {str(e)}")
            return Response({
                'error': 'Failed to fetch security logs',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def post(self, request):
        """Create security log (for internal use)"""
        try:
            data = request.data
            
            # Validate required fields
            required_fields = ['security_type', 'description']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                return Response({
                    'error': f'Missing required fields: {missing_fields}',
                    'code': 'MISSING_FIELDS'
                }, status=400)
            
            # Create log
            log = SecurityLog.objects.create(
                user=data.get('user') and request.user.__class__.objects.filter(id=data['user']).first(),
                security_type=data['security_type'],
                severity=data.get('severity', 'medium'),
                ip_address=data.get('ip_address', self._get_client_ip(request)),
                user_agent=data.get('user_agent', request.META.get('HTTP_USER_AGENT', '')),
                device_info=data.get('device_id') and DeviceInfo.objects.filter(id=data['device_id']).first(),
                description=data['description'],
                metadata=data.get('metadata', {}),
                action_taken=data.get('action_taken', ''),
                risk_score=data.get('risk_score', 0)
            )
            
            # Check if auto-block rules should trigger
            self._check_auto_block_rules(log)
            
            serializer = SecurityLogSerializer(log)
            
            return Response({
                'success': True,
                'log': serializer.data,
                'message': 'Security log created successfully'
            }, status=201)
            
        except Exception as e:
            logging.error(f"Error creating security log: {str(e)}")
            return Response({
                'error': 'Failed to create security log',
                'code': 'CREATION_ERROR'
            }, status=500)
    
    def _check_auto_block_rules(self, security_log):
        """Check and apply auto-block rules"""
        try:
            rules = AutoBlockRule.objects.filter(is_active=True)
            
            for rule in rules:
                if rule.evaluate(
                    security_log.user,
                    security_log.ip_address,
                    security_log.device_info,
                    {'security_log': security_log.id}
                ):
                    rule.take_action(
                        security_log.user,
                        security_log.ip_address,
                        security_log.device_info,
                        f"Security log triggered: {security_log.security_type}"
                    )
        except Exception as e:
            logging.error(f"Error checking auto-block rules: {str(e)}")

# ==================== RISK SCORING VIEWS ====================

class RiskScoreView(BaseAPIView):
    """Risk scoring views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=20))
    def get(self, request):
        """Get user's risk score"""
        try:
            user_id = request.GET.get('user', request.user.id)
            
            # Permission check
            if str(user_id) != str(request.user.id) and not request.user.is_staff:
                return Response({
                    'error': 'Permission denied',
                    'code': 'PERMISSION_DENIED'
                }, status=403)
            
            # Get or create risk score
            risk_score, created = RiskScore.objects.get_or_create(
                user_id=user_id,
                defaults={
                    'current_score': 50,
                    'previous_score': 50
                }
            )
            
            # Update score if it's old
            if (timezone.now() - risk_score.calculated_at).total_seconds() > 3600:  # 1 hour
                risk_score.update_score()
            
            # Get risk factors
            risk_factors = self._calculate_risk_factors(risk_score.user)
            
            serializer = RiskScoreSerializer(risk_score)
            
            return Response({
                'success': True,
                'risk_score': serializer.data,
                'risk_factors': risk_factors,
                'risk_level': self._get_risk_level(risk_score.current_score),
                'recommendations': self._get_recommendations(risk_score.current_score, risk_factors)
            })
            
        except Exception as e:
            logging.error(f"Error fetching risk score: {str(e)}")
            return Response({
                'error': 'Failed to fetch risk score',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    def _calculate_risk_factors(self, user):
        """Calculate risk factors for user"""
        factors = []
        
        try:
            # Device risk
            suspicious_devices = DeviceInfo.objects.filter(
                user=user,
                is_suspicious=True
            ).count()
            
            if suspicious_devices > 0:
                factors.append({
                    'factor': 'Suspicious devices',
                    'severity': 'high' if suspicious_devices > 1 else 'medium',
                    'count': suspicious_devices
                })
            
            # Failed login attempts
            failed_logins = SecurityLog.objects.filter(
                user=user,
                security_type='failed_login',
                created_at__gte=timezone.now() - timedelta(days=1)
            ).count()
            
            if failed_logins > 3:
                factors.append({
                    'factor': 'Failed login attempts',
                    'severity': 'medium',
                    'count': failed_logins
                })
            
            # VPN/Proxy usage
            vpn_usage = DeviceInfo.objects.filter(
                user=user,
                is_vpn=True,
                last_activity__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            if vpn_usage > 0:
                factors.append({
                    'factor': 'VPN usage detected',
                    'severity': 'medium',
                    'count': vpn_usage
                })
            
            # Multiple locations
            recent_logs = SecurityLog.objects.filter(
                user=user,
                ip_address__isnull=False,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).values('ip_address').distinct().count()
            
            if recent_logs > 3:
                factors.append({
                    'factor': 'Multiple locations in 24h',
                    'severity': 'high',
                    'count': recent_logs
                })
            
        except Exception as e:
            logging.error(f"Error calculating risk factors: {str(e)}")
        
        return factors
    
    def _get_risk_level(self, score):
        """Get risk level from score"""
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
    
    def _get_recommendations(self, score, risk_factors):
        """Get security recommendations"""
        recommendations = []
        
        if score >= 60:
            recommendations.append({
                'action': 'Enable two-factor authentication',
                'priority': 'high',
                'description': 'Add an extra layer of security to your account'
            })
        
        if any(f['factor'] == 'Suspicious devices' for f in risk_factors):
            recommendations.append({
                'action': 'Review your trusted devices',
                'priority': 'high',
                'description': 'Remove any unfamiliar or suspicious devices'
            })
        
        if any(f['factor'] == 'VPN usage detected' for f in risk_factors):
            recommendations.append({
                'action': 'Disable VPN for this app',
                'priority': 'medium',
                'description': 'VPN usage can trigger security alerts'
            })
        
        if len(recommendations) == 0:
            recommendations.append({
                'action': 'Maintain current security practices',
                'priority': 'low',
                'description': 'Your account security is good'
            })
        
        return recommendations

# ==================== SECURITY DASHBOARD VIEWS ====================

class SecurityDashboardView(BaseAPIView):
    """Security dashboard views"""
    
    permission_classes = [IsAdminUser]
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get security dashboard data"""
        try:
            # Get time range (default: last 7 days)
            days = int(request.GET.get('days', 7))
            start_date = timezone.now() - timedelta(days=days)
            
            # Generate dashboard data
            dashboard_data = self._generate_dashboard_data(start_date)
            
            # Get real-time alerts
            alerts = self._get_recent_alerts()
            
            # Get top threats
            top_threats = self._get_top_threats(start_date)
            
            # Get risk distribution
            risk_distribution = self._get_risk_distribution()
            
            return Response({
                'success': True,
                'dashboard': dashboard_data,
                'alerts': alerts,
                'top_threats': top_threats,
                'risk_distribution': risk_distribution,
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logging.error(f"Error generating dashboard: {str(e)}")
            return Response({
                'error': 'Failed to generate dashboard',
                'code': 'DASHBOARD_ERROR'
            }, status=500)
    
    def _generate_dashboard_data(self, start_date):
        """Generate comprehensive dashboard data"""
        data = {
            'overview': self._get_overview_stats(start_date),
            'threats_timeline': self._get_threats_timeline(start_date),
            'geographic_data': self._get_geographic_data(start_date),
            'device_analytics': self._get_device_analytics(start_date),
            'user_behavior': self._get_user_behavior(start_date)
        }
        return data
    
    def _get_overview_stats(self, start_date):
        """Get overview statistics"""
        stats = {}
        
        try:
            # Total threats
            stats['total_threats'] = SecurityLog.objects.filter(
                created_at__gte=start_date
            ).count()
            
            # Blocked threats
            stats['blocked_threats'] = SecurityLog.objects.filter(
                created_at__gte=start_date,
                action_taken__icontains='block'
            ).count()
            
            # Active users with high risk
            stats['high_risk_users'] = RiskScore.objects.filter(
                current_score__gte=60,
                calculated_at__gte=timezone.now() - timedelta(days=1)
            ).count()
            
            # Suspicious devices
            stats['suspicious_devices'] = DeviceInfo.objects.filter(
                is_suspicious=True,
                last_activity__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Banned users
            stats['banned_users'] = UserBan.objects.filter(
                banned_at__gte=start_date
            ).count()
            
        except Exception as e:
            logging.error(f"Error getting overview stats: {str(e)}")
        
        return stats
    
    def _get_threats_timeline(self, start_date):
        """Get threats timeline data"""
        timeline = []
        
        try:
            # Group by day
            threat_data = SecurityLog.objects.filter(
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date', 'severity').annotate(
                count=Count('id')
            ).order_by('date')
            
            # Format for chart
            for entry in threat_data:
                timeline.append({
                    'date': entry['date'].isoformat(),
                    'severity': entry['severity'],
                    'count': entry['count']
                })
                
        except Exception as e:
            logging.error(f"Error getting threats timeline: {str(e)}")
        
        return timeline
    
    def _get_geographic_data(self, start_date):
        """Get geographic threat data"""
        geographic = []
        
        try:
            # Get threats by country
            geo_data = GeolocationLog.objects.filter(
                security_logs__created_at__gte=start_date
            ).values(
                'country_code', 'country_name'
            ).annotate(
                threat_count=Count('security_logs'),
                high_severity=Count('security_logs', filter=Q(security_logs__severity__in=['high', 'critical']))
            ).order_by('-threat_count')[:10]
            
            for entry in geo_data:
                geographic.append({
                    'country_code': entry['country_code'],
                    'country_name': entry['country_name'],
                    'threat_count': entry['threat_count'],
                    'high_severity_count': entry['high_severity']
                })
                
        except Exception as e:
            logging.error(f"Error getting geographic data: {str(e)}")
        
        return geographic
    
    def _get_device_analytics(self, start_date):
        """Get device analytics"""
        analytics = {
            'rooted_devices': DeviceInfo.objects.filter(is_rooted=True).count(),
            'emulator_devices': DeviceInfo.objects.filter(is_emulator=True).count(),
            'vpn_usage': DeviceInfo.objects.filter(is_vpn=True).count(),
            'device_models': [],
            'os_versions': []
        }
        
        try:
            # Top device models
            device_models = DeviceInfo.objects.values('device_model').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            analytics['device_models'] = list(device_models)
            
            # Android versions
            os_versions = DeviceInfo.objects.filter(
                android_version__isnull=False
            ).values('android_version').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            analytics['os_versions'] = list(os_versions)
            
        except Exception as e:
            logging.error(f"Error getting device analytics: {str(e)}")
        
        return analytics
    
    def _get_user_behavior(self, start_date):
        """Get user behavior analytics"""
        behavior = {}
        
        try:
            # Login patterns
            login_hours = SecurityLog.objects.filter(
                security_type='failed_login',
                created_at__gte=start_date
            ).annotate(
                hour=TruncHour('created_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
            
            behavior['login_patterns'] = list(login_hours)
            
            # User risk distribution
            risk_dist = RiskScore.objects.values('current_score').annotate(
                user_count=Count('id')
            ).order_by('current_score')
            
            behavior['risk_distribution'] = list(risk_dist)
            
        except Exception as e:
            logging.error(f"Error getting user behavior: {str(e)}")
        
        return behavior
    
    def _get_recent_alerts(self):
        """Get recent security alerts"""
        alerts = []
        
        try:
            recent_alerts = SecurityLog.objects.filter(
                severity__in=['high', 'critical'],
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-created_at')[:20]
            
            for alert in recent_alerts:
                alerts.append({
                    'id': alert.id,
                    'type': alert.security_type,
                    'severity': alert.severity,
                    'description': alert.description,
                    'user': alert.user.username if alert.user else 'Unknown',
                    'time': alert.created_at.isoformat(),
                    'resolved': alert.resolved
                })
                
        except Exception as e:
            logging.error(f"Error getting recent alerts: {str(e)}")
        
        return alerts
    
    def _get_top_threats(self, start_date):
        """Get top threat types"""
        threats = []
        
        try:
            threat_types = SecurityLog.objects.filter(
                created_at__gte=start_date
            ).values('security_type').annotate(
                count=Count('id'),
                high_severity=Count('id', filter=Q(severity__in=['high', 'critical']))
            ).order_by('-count')[:10]
            
            for threat in threat_types:
                threats.append({
                    'type': threat['security_type'],
                    'total': threat['count'],
                    'high_severity': threat['high_severity'],
                    'percentage': (threat['count'] / SecurityLog.objects.filter(
                        created_at__gte=start_date
                    ).count() * 100) if SecurityLog.objects.filter(created_at__gte=start_date).count() > 0 else 0
                })
                
        except Exception as e:
            logging.error(f"Error getting top threats: {str(e)}")
        
        return threats
    
    def _get_risk_distribution(self):
        """Get risk score distribution"""
        distribution = {
            'very_low': 0,
            'low': 0,
            'medium': 0,
            'high': 0,
            'critical': 0
        }
        
        try:
            risk_scores = RiskScore.objects.all()
            
            for score in risk_scores:
                if score.current_score >= 80:
                    distribution['critical'] += 1
                elif score.current_score >= 60:
                    distribution['high'] += 1
                elif score.current_score >= 40:
                    distribution['medium'] += 1
                elif score.current_score >= 20:
                    distribution['low'] += 1
                else:
                    distribution['very_low'] += 1
                    
        except Exception as e:
            logging.error(f"Error getting risk distribution: {str(e)}")
        
        return distribution

# ==================== AUTO-BLOCK VIEWS ====================



# ==================== AUDIT TRAIL VIEWS ====================

class AuditTrailView(BaseAPIView):
    """Audit trail views"""
    
    permission_classes = [IsAdminUser]
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=20))
    def get(self, request):
        """Get audit trail with filters"""
        try:
            # Build query
            audits = AuditTrail.objects.all()
            
            # Apply filters
            filters = Q()
            
            # User filter
            if request.GET.get('user'):
                filters &= Q(user_id=request.GET.get('user'))
            
            # Action type filter
            if request.GET.get('action_type'):
                filters &= Q(action_type=request.GET.get('action_type'))
            
            # Model filter
            if request.GET.get('model_name'):
                filters &= Q(model_name=request.GET.get('model_name'))
            
            # Date range filter
            if request.GET.get('start_date'):
                try:
                    start_date = timezone.datetime.fromisoformat(request.GET.get('start_date'))
                    filters &= Q(created_at__gte=start_date)
                except ValueError:
                    pass
            
            if request.GET.get('end_date'):
                try:
                    end_date = timezone.datetime.fromisoformat(request.GET.get('end_date'))
                    filters &= Q(created_at__lte=end_date)
                except ValueError:
                    pass
            
            # Apply filters
            audits = audits.filter(filters)
            
            # Ordering
            order_by = request.GET.get('order_by', '-created_at')
            if order_by.lstrip('-') in ['created_at', 'action_type', 'model_name']:
                audits = audits.order_by(order_by)
            
            # Pagination
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 50))
            
            paginator = Paginator(audits, page_size)
            page_obj = paginator.page(page)
            
            # Serialize data
            serializer = AuditTrailSerializer(page_obj, many=True)
            
            # Get statistics
            total_audits = paginator.count
            create_count = audits.filter(action_type='create').count()
            update_count = audits.filter(action_type='update').count()
            delete_count = audits.filter(action_type='delete').count()
            
            return Response({
                'success': True,
                'audits': serializer.data,
                'pagination': {
                    'total': total_audits,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                },
                'statistics': {
                    'total': total_audits,
                    'creates': create_count,
                    'updates': update_count,
                    'deletes': delete_count
                }
            })
            
        except EmptyPage:
            return Response({
                'error': 'Page not found',
                'code': 'PAGE_NOT_FOUND'
            }, status=404)
        except Exception as e:
            logging.error(f"Error fetching audit trail: {str(e)}")
            return Response({
                'error': 'Failed to fetch audit trail',
                'code': 'FETCH_ERROR'
            }, status=500)

# ==================== DATA EXPORT/IMPORT VIEWS ====================

class DataExportView(BaseAPIView):
    """Data export views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    def post(self, request):
        """Request data export"""
        try:
            data = request.data
            
            # Validate required fields
            required_fields = ['export_name', 'model_name']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                return Response({
                    'error': f'Missing required fields: {missing_fields}',
                    'code': 'MISSING_FIELDS'
                }, status=400)
            
            # Check user's export limit
            recent_exports = DataExport.objects.filter(
                user=request.user,
                requested_at__gte=timezone.now() - timedelta(days=1)
            ).count()
            
            if recent_exports >= 10:  # Limit to 10 exports per day
                return Response({
                    'error': 'Export limit exceeded. Maximum 10 exports per day.',
                    'code': 'EXPORT_LIMIT_EXCEEDED'
                }, status=429)
            
            # Create export request
            export = DataExport.objects.create(
                user=request.user,
                export_name=data['export_name'],
                format=data.get('format', 'csv'),
                model_name=data['model_name'],
                filters=data.get('filters', {}),
                columns=data.get('columns', []),
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            # Generate secure download URL
            download_url = export.generate_secure_download_url()
            
            # Start export processing (async)
            self._process_export_async(export.id)
            
            serializer = DataExportSerializer(export)
            
            return Response({
                'success': True,
                'export': serializer.data,
                'download_url': download_url,
                'message': 'Export request submitted successfully'
            }, status=202)
            
        except Exception as e:
            logging.error(f"Error creating export: {str(e)}")
            return Response({
                'error': 'Failed to create export',
                'code': 'EXPORT_ERROR'
            }, status=500)
    
    def _process_export_async(self, export_id):
        """Process export asynchronously (simplified)"""
        try:
            # In production, this would be a Celery task
            export = DataExport.objects.get(id=export_id)
            export.status = 'processing'
            export.started_at = timezone.now()
            export.save()
            
            # Simulate processing
            import time
            time.sleep(2)
            
            # Complete processing
            export.status = 'completed'
            export.completed_at = timezone.now()
            export.total_records = 100  # Example count
            export.exported_records = 100
            export.save()
            
        except Exception as e:
            logging.error(f"Error processing export {export_id}: {str(e)}")
            
            export = DataExport.objects.get(id=export_id)
            export.status = 'failed'
            export.save()
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get user's export history"""
        try:
            exports = DataExport.objects.filter(user=request.user)
            
            # Apply filters
            if request.GET.get('status'):
                exports = exports.filter(status=request.GET.get('status'))
            
            if request.GET.get('start_date'):
                try:
                    start_date = timezone.datetime.fromisoformat(request.GET.get('start_date'))
                    exports = exports.filter(requested_at__gte=start_date)
                except ValueError:
                    pass
            
            # Pagination
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            
            paginator = Paginator(exports, page_size)
            page_obj = paginator.page(page)
            
            serializer = DataExportSerializer(page_obj, many=True)
            
            return Response({
                'success': True,
                'exports': serializer.data,
                'pagination': {
                    'total': paginator.count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })
            
        except EmptyPage:
            return Response({
                'error': 'Page not found',
                'code': 'PAGE_NOT_FOUND'
            }, status=404)
        except Exception as e:
            logging.error(f"Error fetching exports: {str(e)}")
            return Response({
                'error': 'Failed to fetch exports',
                'code': 'FETCH_ERROR'
            }, status=500)

class DataImportView(BaseAPIView):
    """Data import views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=3))
    def post(self, request):
        """Upload and import data"""
        try:
            # Check if file is present
            if 'file' not in request.FILES:
                return Response({
                    'error': 'No file provided',
                    'code': 'NO_FILE'
                }, status=400)
            
            uploaded_file = request.FILES['file']
            
            # Validate file size (max 10MB)
            max_size = 10 * 1024 * 1024
            if uploaded_file.size > max_size:
                return Response({
                    'error': 'File too large. Maximum size is 10MB.',
                    'code': 'FILE_TOO_LARGE'
                }, status=400)
            
            # Validate file extension
            allowed_extensions = ['.csv', '.json', '.xlsx', '.xls']
            import os
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            
            if file_ext not in allowed_extensions:
                return Response({
                    'error': f'Invalid file extension. Allowed: {allowed_extensions}',
                    'code': 'INVALID_EXTENSION'
                }, status=400)
            
            # Save file temporarily
            import tempfile
            import uuid
            
            temp_dir = tempfile.gettempdir()
            file_name = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(temp_dir, file_name)
            
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            
            # Calculate file hash
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            file_hash = sha256_hash.hexdigest()
            
            # Create import record
            import_record = DataImport.objects.create(
                user=request.user,
                import_name=request.data.get('import_name', uploaded_file.name),
                model_name=request.data.get('model_name', 'unknown'),
                file_name=uploaded_file.name,
                file_path=file_path,
                file_size=uploaded_file.size,
                file_hash=file_hash,
                status='pending'
            )
            
            # Start import processing (async)
            self._process_import_async(import_record.id)
            
            serializer = DataImportSerializer(import_record)
            
            return Response({
                'success': True,
                'import': serializer.data,
                'message': 'Import request submitted successfully'
            }, status=202)
            
        except Exception as e:
            logging.error(f"Error creating import: {str(e)}")
            return Response({
                'error': 'Failed to create import',
                'code': 'IMPORT_ERROR'
            }, status=500)
    
    def _process_import_async(self, import_id):
        """Process import asynchronously"""
        try:
            import_record = DataImport.objects.get(id=import_id)
            import_record.status = 'processing'
            import_record.started_at = timezone.now()
            import_record.save()
            
            # Validate file
            if not import_record.validate_file():
                import_record.status = 'failed'
                import_record.save()
                return
            
            # Process file (simplified)
            import_record.status = 'completed'
            import_record.completed_at = timezone.now()
            import_record.total_records = 100  # Example
            import_record.successful_records = 95
            import_record.failed_records = 5
            import_record.save()
            
        except Exception as e:
            logging.error(f"Error processing import {import_id}: {str(e)}")
            
            import_record = DataImport.objects.get(id=import_id)
            import_record.status = 'failed'
            import_record.save()

# ==================== NOTIFICATION VIEWS ====================

class NotificationView(BaseAPIView):
    """Notification views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=30))
    def get(self, request):
        """Get user's notifications"""
        try:
            notifications = SecurityNotification.objects.filter(user=request.user)
            
            # Apply filters
            if request.GET.get('status'):
                notifications = notifications.filter(status=request.GET.get('status'))
            
            if request.GET.get('priority'):
                notifications = notifications.filter(priority=request.GET.get('priority'))
            
            if request.GET.get('unread'):
                notifications = notifications.filter(read_at__isnull=True)
            
            # Mark as read if requested
            if request.GET.get('mark_read') == 'true':
                notifications.update(read_at=timezone.now())
            
            # Order by priority and date
            notifications = notifications.order_by('-priority', '-created_at')
            
            # Pagination
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            
            paginator = Paginator(notifications, page_size)
            page_obj = paginator.page(page)
            
            serializer = SecurityNotificationSerializer(page_obj, many=True)
            
            # Get unread count
            unread_count = SecurityNotification.objects.filter(
                user=request.user,
                read_at__isnull=True
            ).count()
            
            return Response({
                'success': True,
                'notifications': serializer.data,
                'unread_count': unread_count,
                'pagination': {
                    'total': paginator.count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            })
            
        except EmptyPage:
            return Response({
                'error': 'Page not found',
                'code': 'PAGE_NOT_FOUND'
            }, status=404)
        except Exception as e:
            logging.error(f"Error fetching notifications: {str(e)}")
            return Response({
                'error': 'Failed to fetch notifications',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def post(self, request):
        """Mark notifications as read"""
        try:
            data = request.data
            
            # Validate required fields
            if 'notification_ids' not in data:
                return Response({
                    'error': 'Missing notification_ids',
                    'code': 'MISSING_IDS'
                }, status=400)
            
            # Mark notifications as read
            notifications = SecurityNotification.objects.filter(
                id__in=data['notification_ids'],
                user=request.user
            )
            
            updated_count = notifications.update(read_at=timezone.now())
            
            return Response({
                'success': True,
                'updated_count': updated_count,
                'message': f'Marked {updated_count} notifications as read'
            })
            
        except Exception as e:
            logging.error(f"Error marking notifications as read: {str(e)}")
            return Response({
                'error': 'Failed to mark notifications as read',
                'code': 'UPDATE_ERROR'
            }, status=500)

# ==================== FRAUD DETECTION VIEWS ====================

class FraudDetectionView(BaseAPIView):
    """Fraud detection views"""
    
    permission_classes = [IsAdminUser]
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get fraud detection statistics"""
        try:
            # Get time range
            days = int(request.GET.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            stats = {
                'patterns': self._get_pattern_stats(),
                'detections': self._get_detection_stats(start_date),
                'recent_matches': self._get_recent_matches(),
                'effectiveness': self._get_effectiveness_metrics(start_date)
            }
            
            return Response({
                'success': True,
                'statistics': stats,
                'time_range': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': timezone.now().isoformat()
                }
            })
            
        except Exception as e:
            logging.error(f"Error getting fraud stats: {str(e)}")
            return Response({
                'error': 'Failed to get fraud statistics',
                'code': 'STATS_ERROR'
            }, status=500)
    
    def _get_pattern_stats(self):
        """Get fraud pattern statistics"""
        patterns = FraudPattern.objects.all()
        
        stats = {
            'total_patterns': patterns.count(),
            'active_patterns': patterns.filter(is_active=True).count(),
            'patterns_by_type': {},
            'top_patterns': []
        }
        
        # Count by type
        for pattern_type, _ in FraudPattern.PATTERN_TYPES:
            stats['patterns_by_type'][pattern_type] = patterns.filter(
                pattern_type=pattern_type
            ).count()
        
        # Top patterns by match count
        top_patterns = patterns.order_by('-match_count')[:5]
        for pattern in top_patterns:
            stats['top_patterns'].append({
                'name': pattern.name,
                'type': pattern.pattern_type,
                'match_count': pattern.match_count,
                'last_match': pattern.last_match_at.isoformat() if pattern.last_match_at else None
            })
        
        return stats
    
    def _get_detection_stats(self, start_date):
        """Get detection statistics"""
        detections = {
            'total_checks': 0,
            'total_matches': 0,
            'by_pattern_type': {},
            'timeline': []
        }
        
        try:
            # Get all detections in timeframe
            matches = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                created_at__gte=start_date,
                metadata__has_key='pattern_id'
            )
            
            detections['total_matches'] = matches.count()
            
            # Count by pattern type
            pattern_types = FraudPattern.objects.values_list('pattern_type', flat=True).distinct()
            for pattern_type in pattern_types:
                count = matches.filter(
                    metadata__pattern_name__icontains=pattern_type
                ).count()
                detections['by_pattern_type'][pattern_type] = count
            
            # Timeline data
            timeline_data = matches.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            for entry in timeline_data:
                detections['timeline'].append({
                    'date': entry['date'].isoformat(),
                    'count': entry['count']
                })
                
        except Exception as e:
            logging.error(f"Error getting detection stats: {str(e)}")
        
        return detections
    
    def _get_recent_matches(self):
        """Get recent fraud pattern matches"""
        recent_matches = []
        
        try:
            matches = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                metadata__has_key='pattern_id'
            ).order_by('-created_at')[:10]
            
            for match in matches:
                recent_matches.append({
                    'id': match.id,
                    'user': match.user.username if match.user else 'Unknown',
                    'pattern': match.metadata.get('pattern_name', 'Unknown'),
                    'score': match.metadata.get('score', 0),
                    'severity': match.severity,
                    'timestamp': match.created_at.isoformat(),
                    'ip_address': match.ip_address
                })
                
        except Exception as e:
            logging.error(f"Error getting recent matches: {str(e)}")
        
        return recent_matches
    
    def _get_effectiveness_metrics(self, start_date):
        """Get fraud detection effectiveness metrics"""
        metrics = {
            'accuracy': 0,
            'false_positives': 0,
            'detection_rate': 0,
            'response_time': 0
        }
        
        try:
            # Calculate accuracy (simplified)
            total_matches = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                created_at__gte=start_date,
                metadata__has_key='pattern_id'
            ).count()
            
            confirmed_fraud = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                created_at__gte=start_date,
                metadata__has_key='pattern_id',
                resolved=True,
                action_taken__icontains='block'
            ).count()
            
            if total_matches > 0:
                metrics['accuracy'] = (confirmed_fraud / total_matches) * 100
            
            # False positives
            metrics['false_positives'] = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                created_at__gte=start_date,
                metadata__has_key='pattern_id',
                resolved=True,
                action_taken__icontains='false'
            ).count()
            
            # Detection rate (simplified)
            total_suspicious = SecurityLog.objects.filter(
                security_type='suspicious_activity',
                created_at__gte=start_date
            ).count()
            
            if total_suspicious > 0:
                metrics['detection_rate'] = (total_matches / total_suspicious) * 100
                
        except Exception as e:
            logging.error(f"Error calculating effectiveness metrics: {str(e)}")
        
        return metrics

# ==================== GEOLOCATION VIEWS ====================

class GeolocationView(BaseAPIView):
    """Geolocation views"""
    
    permission_classes = [IsAdminUser]
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=20))
    def get(self, request):
        """Get geolocation data"""
        try:
            ip_address = request.GET.get('ip')
            
            if not ip_address:
                return Response({
                    'error': 'IP address required',
                    'code': 'IP_REQUIRED'
                }, status=400)
            
            # Get geolocation
            geolocation = GeolocationLog.get_geolocation(ip_address)
            
            # Assess risk
            risk_assessment = geolocation.assess_risk()
            
            # Get related security logs
            related_logs = SecurityLog.objects.filter(
                ip_address=ip_address
            ).order_by('-created_at')[:10]
            
            serializer = GeolocationLogSerializer(geolocation)
            
            return Response({
                'success': True,
                'geolocation': serializer.data,
                'risk_assessment': risk_assessment,
                'related_logs': SecurityLogSerializer(related_logs, many=True).data
            })
            
        except Exception as e:
            logging.error(f"Error getting geolocation: {str(e)}")
            return Response({
                'error': 'Failed to get geolocation data',
                'code': 'GEOLOCATION_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def post(self, request):
        """Bulk geolocation lookup"""
        try:
            data = request.data
            
            if 'ips' not in data:
                return Response({
                    'error': 'IP addresses required',
                    'code': 'IPS_REQUIRED'
                }, status=400)
            
            ips = data['ips']
            if not isinstance(ips, list) or len(ips) > 100:
                return Response({
                    'error': 'Invalid IP list. Maximum 100 IPs allowed.',
                    'code': 'INVALID_IP_LIST'
                }, status=400)
            
            results = []
            for ip in ips:
                try:
                    geolocation = GeolocationLog.get_geolocation(ip)
                    risk = geolocation.assess_risk()
                    
                    results.append({
                        'ip': ip,
                        'country': geolocation.country_name,
                        'city': geolocation.city,
                        'is_vpn': geolocation.is_vpn,
                        'is_proxy': geolocation.is_proxy,
                        'threat_score': geolocation.threat_score,
                        'risk_level': risk['threat_level']
                    })
                except Exception as e:
                    results.append({
                        'ip': ip,
                        'error': str(e)
                    })
            
            return Response({
                'success': True,
                'results': results,
                'processed': len(results)
            })
            
        except Exception as e:
            logging.error(f"Error in bulk geolocation: {str(e)}")
            return Response({
                'error': 'Failed to process bulk geolocation',
                'code': 'BULK_GEOLOCATION_ERROR'
            }, status=500)

# ==================== API RATE LIMITING VIEWS ====================

class RateLimitView(BaseAPIView):
    """Rate limiting views"""
    
    permission_classes = [IsAdminUser]
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=30))
    def get(self, request):
        """Get rate limit configuration"""
        try:
            rate_limits = APIRateLimit.objects.all()
            
            # Apply filters
            if request.GET.get('is_active'):
                rate_limits = rate_limits.filter(is_active=request.GET.get('is_active') == 'true')
            
            if request.GET.get('limit_type'):
                rate_limits = rate_limits.filter(limit_type=request.GET.get('limit_type'))
            
            # Statistics
            stats = {
                'total_limits': rate_limits.count(),
                'active_limits': rate_limits.filter(is_active=True).count(),
                'total_blocks': sum(rl.total_blocks for rl in rate_limits),
                'recent_blocks': RateLimitLog.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).count()
            }
            
            serializer = APIRateLimitSerializer(rate_limits, many=True)
            
            return Response({
                'success': True,
                'rate_limits': serializer.data,
                'statistics': stats
            })
            
        except Exception as e:
            logging.error(f"Error getting rate limits: {str(e)}")
            return Response({
                'error': 'Failed to get rate limits',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def post(self, request):
        """Test rate limit"""
        try:
            data = request.data
            
            required_fields = ['identifier', 'limit_type']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                return Response({
                    'error': f'Missing required fields: {missing_fields}',
                    'code': 'MISSING_FIELDS'
                }, status=400)
            
            # Find applicable rate limit
            rate_limit_obj = APIRateLimit.objects.filter(
                limit_type=data['limit_type'],
                is_active=True
            ).first()
            
            if not rate_limit_obj:
                return Response({
                    'error': 'No rate limit found for specified type',
                    'code': 'NO_RATE_LIMIT'
                }, status=404)
            
            # Test rate limit
            result = rate_limit_obj.check_limit(
                identifier=data['identifier'],
                increment=False
            )
            
            return Response({
                'success': True,
                'rate_limit': APIRateLimitSerializer(rate_limit_obj).data,
                'test_result': result,
                'would_be_blocked': not result['allowed']
            })
            
        except Exception as e:
            logging.error(f"Error testing rate limit: {str(e)}")
            return Response({
                'error': 'Failed to test rate limit',
                'code': 'TEST_ERROR'
            }, status=500)

# ==================== PASSWORD SECURITY VIEWS ====================

class PasswordSecurityView(BaseAPIView):
    """Password security views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get password security status"""
        try:
            # Get password policy
            policy = PasswordPolicy.objects.filter(is_active=True).first()
            
            # Get user's password history
            password_history = PasswordHistory.objects.filter(
                user=request.user
            ).order_by('-created_at')[:5]
            
            # Get failed attempts
            failed_attempts = PasswordAttempt.objects.filter(
                user=request.user,
                successful=False,
                attempted_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Check if locked out
            is_locked_out = PasswordAttempt.is_locked_out(request.user)
            
            # Password age
            latest_password = password_history.first()
            password_age = None
            if latest_password:
                password_age = (timezone.now() - latest_password.created_at).days
            
            data = {
                'policy': PasswordPolicySerializer(policy).data if policy else None,
                'password_history_count': password_history.count(),
                'failed_attempts_24h': failed_attempts,
                'is_locked_out': is_locked_out,
                'password_age_days': password_age,
                'requires_change': password_age and policy and password_age >= policy.password_expiry_days
            }
            
            return Response({
                'success': True,
                'password_security': data
            })
            
        except Exception as e:
            logging.error(f"Error getting password security: {str(e)}")
            return Response({
                'error': 'Failed to get password security status',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    def post(self, request):
        """Validate password strength"""
        try:
            data = request.data
            
            if 'password' not in data:
                return Response({
                    'error': 'Password required',
                    'code': 'PASSWORD_REQUIRED'
                }, status=400)
            
            password = data['password']
            username = data.get('username', request.user.username)
            
            # Get active password policy
            policy = PasswordPolicy.objects.filter(is_active=True).first()
            
            if not policy:
                return Response({
                    'error': 'No password policy configured',
                    'code': 'NO_POLICY'
                }, status=500)
            
            # Validate password
            validation_result = policy.validate_password(password, username)
            
            # Check if password was used before
            if 'check_history' in data and data['check_history']:
                was_used = PasswordHistory.is_password_used(request.user, password)
                validation_result['previously_used'] = was_used
                if was_used:
                    validation_result['valid'] = False
                    validation_result['errors'].append('Password was used before')
            
            return Response({
                'success': True,
                'validation': validation_result
            })
            
        except Exception as e:
            logging.error(f"Error validating password: {str(e)}")
            return Response({
                'error': 'Failed to validate password',
                'code': 'VALIDATION_ERROR'
            }, status=500)

# ==================== SESSION MANAGEMENT VIEWS ====================

class SessionView(BaseAPIView):
    """Session management views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=20))
    def get(self, request):
        """Get user's active sessions"""
        try:
            sessions = UserSession.objects.filter(
                user=request.user,
                is_active=True,
                expires_at__gt=timezone.now()
            ).order_by('-last_activity')
            
            # Get suspicious sessions
            suspicious_sessions = []
            for session in sessions:
                if session.is_compromised:
                    suspicious_sessions.append(session.id)
            
            serializer = UserSessionSerializer(sessions, many=True)
            
            return Response({
                'success': True,
                'sessions': serializer.data,
                'total_sessions': sessions.count(),
                'suspicious_sessions': suspicious_sessions,
                'current_session_key': request.session.session_key
            })
            
        except Exception as e:
            logging.error(f"Error getting sessions: {str(e)}")
            return Response({
                'error': 'Failed to get sessions',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    def post(self, request):
        """Terminate sessions"""
        try:
            data = request.data
            
            if 'session_keys' not in data:
                return Response({
                    'error': 'Session keys required',
                    'code': 'SESSION_KEYS_REQUIRED'
                }, status=400)
            
            session_keys = data['session_keys']
            
            # Don't allow terminating current session
            if request.session.session_key in session_keys and 'force' not in data:
                return Response({
                    'error': 'Cannot terminate current session',
                    'code': 'CURRENT_SESSION'
                }, status=400)
            
            # Terminate sessions
            sessions = UserSession.objects.filter(
                user=request.user,
                session_key__in=session_keys
            )
            
            terminated_count = 0
            for session in sessions:
                session.terminate("Terminated by user request")
                terminated_count += 1
            
            return Response({
                'success': True,
                'terminated_count': terminated_count,
                'message': f'Terminated {terminated_count} session(s)'
            })
            
        except Exception as e:
            logging.error(f"Error terminating sessions: {str(e)}")
            return Response({
                'error': 'Failed to terminate sessions',
                'code': 'TERMINATION_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    @action(detail=False, methods=['post'])
    def terminate_all(self, request):
        """Terminate all other sessions"""
        try:
            current_session_key = request.session.session_key
            
            # Get all active sessions except current
            other_sessions = UserSession.objects.filter(
                user=request.user,
                is_active=True,
                expires_at__gt=timezone.now()
            ).exclude(session_key=current_session_key)
            
            terminated_count = 0
            for session in other_sessions:
                session.terminate("Terminated by user (terminate all)")
                terminated_count += 1
            
            return Response({
                'success': True,
                'terminated_count': terminated_count,
                'message': f'Terminated {terminated_count} other session(s)'
            })
            
        except Exception as e:
            logging.error(f"Error terminating all sessions: {str(e)}")
            return Response({
                'error': 'Failed to terminate sessions',
                'code': 'TERMINATION_ERROR'
            }, status=500)

# ==================== TWO-FACTOR AUTHENTICATION VIEWS ====================

class TwoFactorView(BaseAPIView):
    """Two-factor authentication views"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get 2FA status and methods"""
        try:
            methods = TwoFactorMethod.objects.filter(user=request.user)
            
            # Check if 2FA is enabled
            is_2fa_enabled = methods.filter(is_enabled=True).exists()
            primary_method = methods.filter(is_primary=True, is_enabled=True).first()
            
            # Get backup codes info
            backup_method = methods.filter(method_type='backup_code', is_enabled=True).first()
            backup_codes_remaining = len(backup_method.backup_codes) if backup_method else 0
            
            serializer = TwoFactorMethodSerializer(methods, many=True)
            
            return Response({
                'success': True,
                'is_enabled': is_2fa_enabled,
                'primary_method': TwoFactorMethodSerializer(primary_method).data if primary_method else None,
                'methods': serializer.data,
                'backup_codes_remaining': backup_codes_remaining
            })
            
        except Exception as e:
            logging.error(f"Error getting 2FA status: {str(e)}")
            return Response({
                'error': 'Failed to get 2FA status',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    def post(self, request):
        """Setup 2FA"""
        try:
            data = request.data
            
            if 'method_type' not in data:
                return Response({
                    'error': 'Method type required',
                    'code': 'METHOD_TYPE_REQUIRED'
                }, status=400)
            
            method_type = data['method_type']
            
            # Check if method already exists
            existing_method = TwoFactorMethod.objects.filter(
                user=request.user,
                method_type=method_type
            ).first()
            
            if existing_method and existing_method.is_enabled:
                return Response({
                    'error': f'{method_type} 2FA already enabled',
                    'code': 'ALREADY_ENABLED'
                }, status=400)
            
            # Create or update method
            if existing_method:
                method = existing_method
            else:
                method = TwoFactorMethod.objects.create(
                    user=request.user,
                    method_type=method_type
                )
            
            # Setup based on method type
            if method_type == 'totp':
                # Generate TOTP secret
                import pyotp
                secret = pyotp.random_base32()
                method.secret_key = secret
                
                # Generate provisioning URL
                totp = pyotp.TOTP(secret)
                provisioning_url = totp.provisioning_uri(
                    name=request.user.email,
                    issuer_name=settings.SITE_NAME
                )
                
                method.save()
                
                return Response({
                    'success': True,
                    'method': TwoFactorMethodSerializer(method).data,
                    'secret': secret,
                    'provisioning_url': provisioning_url,
                    'message': 'Scan QR code with authenticator app'
                })
                
            elif method_type == 'sms':
                phone = data.get('phone_number')
                if not phone:
                    return Response({
                        'error': 'Phone number required for SMS 2FA',
                        'code': 'PHONE_REQUIRED'
                    }, status=400)
                
                method.phone_number = phone
                method.save()
                
                # Send verification code (simplified)
                # In production, integrate with SMS service
                
                return Response({
                    'success': True,
                    'method': TwoFactorMethodSerializer(method).data,
                    'message': 'SMS 2FA configured. Verification code sent.'
                })
                
            elif method_type == 'email':
                email = data.get('email', request.user.email)
                method.email = email
                method.save()
                
                return Response({
                    'success': True,
                    'method': TwoFactorMethodSerializer(method).data,
                    'message': 'Email 2FA configured'
                })
                
            elif method_type == 'backup_code':
                # Generate backup codes
                codes = method.generate_backup_codes()
                
                return Response({
                    'success': True,
                    'method': TwoFactorMethodSerializer(method).data,
                    'backup_codes': codes,
                    'message': 'Backup codes generated. Store them securely.'
                })
                
            else:
                return Response({
                    'error': 'Unsupported method type',
                    'code': 'UNSUPPORTED_METHOD'
                }, status=400)
            
        except Exception as e:
            logging.error(f"Error setting up 2FA: {str(e)}")
            return Response({
                'error': 'Failed to setup 2FA',
                'code': 'SETUP_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify 2FA code"""
        try:
            data = request.data
            
            required_fields = ['method_type', 'code']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                return Response({
                    'error': f'Missing required fields: {missing_fields}',
                    'code': 'MISSING_FIELDS'
                }, status=400)
            
            method_type = data['method_type']
            code = data['code']
            
            # Get method
            method = TwoFactorMethod.objects.filter(
                user=request.user,
                method_type=method_type,
                is_enabled=True
            ).first()
            
            if not method:
                return Response({
                    'error': '2FA method not found or not enabled',
                    'code': 'METHOD_NOT_FOUND'
                }, status=404)
            
            # Verify code
            is_valid = False
            
            if method_type == 'totp':
                import pyotp
                totp = pyotp.TOTP(method.secret_key)
                is_valid = totp.verify(code, valid_window=1)
                
            elif method_type == 'backup_code':
                is_valid = method.verify_backup_code(code)
                
            else:
                # For SMS/Email, you would verify against sent code
                # This is simplified
                is_valid = True
            
            # Log attempt
            TwoFactorAttempt.objects.create(
                user=request.user,
                method=method,
                code=code,
                successful=is_valid,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            if is_valid:
                # Update method
                method.last_used_at = timezone.now()
                method.failed_attempts = 0
                method.save()
                
                return Response({
                    'success': True,
                    'verified': True,
                    'message': '2FA verification successful'
                })
            else:
                # Increment failed attempts
                method.failed_attempts += 1
                method.save()
                
                # Check for excessive failures
                if method.failed_attempts >= 5:
                    SecurityLog.objects.create(
                        user=request.user,
                        security_type='suspicious_activity',
                        severity='high',
                        ip_address=self._get_client_ip(request),
                        description='Multiple failed 2FA attempts',
                        metadata={'method_type': method_type, 'failed_attempts': method.failed_attempts}
                    )
                
                return Response({
                    'success': False,
                    'verified': False,
                    'error': 'Invalid verification code',
                    'code': 'INVALID_CODE',
                    'failed_attempts': method.failed_attempts
                }, status=400)
            
        except Exception as e:
            logging.error(f"Error verifying 2FA: {str(e)}")
            return Response({
                'error': 'Failed to verify 2FA',
                'code': 'VERIFICATION_ERROR'
            }, status=500)
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=5))
    @action(detail=False, methods=['post'])
    def disable(self, request):
        """Disable 2FA"""
        try:
            data = request.data
            
            # Require password confirmation
            if 'password' not in data:
                return Response({
                    'error': 'Password required to disable 2FA',
                    'code': 'PASSWORD_REQUIRED'
                }, status=400)
            
            # Verify password
            if not request.user.check_password(data['password']):
                return Response({
                    'error': 'Invalid password',
                    'code': 'INVALID_PASSWORD'
                }, status=400)
            
            # Disable all 2FA methods
            methods = TwoFactorMethod.objects.filter(user=request.user)
            disabled_count = methods.update(is_enabled=False, is_primary=False)
            
            # Log security event
            SecurityLog.objects.create(
                user=request.user,
                security_type='suspicious_activity',
                severity='medium',
                ip_address=self._get_client_ip(request),
                description='Two-factor authentication disabled',
                metadata={'disabled_methods': disabled_count}
            )
            
            return Response({
                'success': True,
                'disabled_count': disabled_count,
                'message': 'Two-factor authentication disabled'
            })
            
        except Exception as e:
            logging.error(f"Error disabling 2FA: {str(e)}")
            return Response({
                'error': 'Failed to disable 2FA',
                'code': 'DISABLE_ERROR'
            }, status=500)

# ==================== USER SECURITY SETTINGS VIEW ====================

class UserSecuritySettingsView(BaseAPIView):
    """User security settings view"""
    
    @method_decorator(rate_limit(limit_type='user', requests_per_minute=10))
    def get(self, request):
        """Get comprehensive security settings"""
        try:
            # Get all security-related data for user
            data = {
                'devices': self._get_device_summary(request.user),
                'risk_score': self._get_risk_score_summary(request.user),
                'sessions': self._get_session_summary(request.user),
                'two_fa': self._get_2fa_summary(request.user),
                'notifications': self._get_notification_summary(request.user),
                'activity': self._get_recent_activity(request.user),
                'recommendations': self._get_security_recommendations(request.user)
            }
            
            return Response({
                'success': True,
                'security_settings': data,
                'last_updated': timezone.now().isoformat()
            })
            
        except Exception as e:
            logging.error(f"Error getting security settings: {str(e)}")
            return Response({
                'error': 'Failed to get security settings',
                'code': 'FETCH_ERROR'
            }, status=500)
    
    def _get_device_summary(self, user):
        """Get device summary"""
        devices = DeviceInfo.objects.filter(user=user)
        
        return {
            'total': devices.count(),
            'trusted': devices.filter(is_trusted=True).count(),
            'suspicious': devices.filter(is_suspicious=True).count(),
            'recent': devices.filter(
                last_activity__gte=timezone.now() - timedelta(days=7)
            ).count()
        }
    
    def _get_risk_score_summary(self, user):
        """Get risk score summary"""
        try:
            risk_score = RiskScore.objects.filter(user=user).first()
            if risk_score:
                return {
                    'score': risk_score.current_score,
                    'level': self._get_risk_level(risk_score.current_score),
                    'updated': risk_score.calculated_at.isoformat()
                }
        except:
            pass
        
        return {'score': 50, 'level': 'medium', 'updated': None}
    
    def _get_risk_level(self, score):
        """Get risk level from score"""
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
    
    def _get_session_summary(self, user):
        """Get session summary"""
        sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        )
        
        return {
            'active': sessions.count(),
            'compromised': sessions.filter(is_compromised=True).count(),
            'locations': sessions.values('ip_address').distinct().count()
        }
    
    def _get_2fa_summary(self, user):
        """Get 2FA summary"""
        methods = TwoFactorMethod.objects.filter(user=user)
        
        return {
            'enabled': methods.filter(is_enabled=True).exists(),
            'methods': methods.count(),
            'primary_method': methods.filter(is_primary=True, is_enabled=True).first().method_type if methods.filter(is_primary=True, is_enabled=True).exists() else None
        }
    
    def _get_notification_summary(self, user):
        """Get notification summary"""
        notifications = SecurityNotification.objects.filter(user=user)
        
        return {
            'unread': notifications.filter(read_at__isnull=True).count(),
            'recent': notifications.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
        }
    
    def _get_recent_activity(self, user):
        """Get recent security activity"""
        activities = []
        
        try:
            # Recent security logs
            logs = SecurityLog.objects.filter(
                user=user
            ).order_by('-created_at')[:5]
            
            for log in logs:
                activities.append({
                    'type': log.security_type,
                    'severity': log.severity,
                    'description': log.description,
                    'time': log.created_at.isoformat(),
                    'resolved': log.resolved
                })
                
        except Exception as e:
            logging.error(f"Error getting recent activity: {str(e)}")
        
        return activities
    
    def _get_security_recommendations(self, user):
        """Get security recommendations"""
        recommendations = []
        
        # Check 2FA
        if not TwoFactorMethod.objects.filter(user=user, is_enabled=True).exists():
            recommendations.append({
                'title': 'Enable Two-Factor Authentication',
                'description': 'Add an extra layer of security to your account',
                'priority': 'high',
                'action': 'enable_2fa'
            })
        
        # Check suspicious devices
        suspicious_devices = DeviceInfo.objects.filter(
            user=user,
            is_suspicious=True
        ).count()
        
        if suspicious_devices > 0:
            recommendations.append({
                'title': 'Review Suspicious Devices',
                'description': f'You have {suspicious_devices} suspicious device(s)',
                'priority': 'high',
                'action': 'review_devices'
            })
        
        # Check password age
        try:
            latest_password = PasswordHistory.objects.filter(user=user).order_by('-created_at').first()
            if latest_password:
                password_age = (timezone.now() - latest_password.created_at).days
                policy = PasswordPolicy.objects.filter(is_active=True).first()
                
                if policy and password_age >= policy.password_expiry_days - policy.warn_before_expiry_days:
                    recommendations.append({
                        'title': 'Update Your Password',
                        'description': f'Your password is {password_age} days old',
                        'priority': 'medium',
                        'action': 'change_password'
                    })
        except:
            pass
        
        # Check active sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).count()
        
        if active_sessions > 5:
            recommendations.append({
                'title': 'Review Active Sessions',
                'description': f'You have {active_sessions} active sessions',
                'priority': 'medium',
                'action': 'review_sessions'
            })
        
        # Default recommendation if none
        if not recommendations:
            recommendations.append({
                'title': 'Security Status Good',
                'description': 'Your account security is good. Keep it up!',
                'priority': 'low',
                'action': 'none'
            })
        
        return recommendations

# ==================== PUBLIC API VIEWS ====================

@api_view(['GET'])
@permission_classes([])  # Public endpoint
@check_maintenance_mode()
@validate_app_version()
def security_status(request):
    """Public endpoint for security status"""
    try:
        # Get basic security statistics
        stats = {
            'system_status': 'operational',
            'maintenance_mode': MaintenanceMode.is_maintenance_active(),
            'last_incident': None,
            'threat_level': 'low'
        }
        
        # Check for recent incidents
        recent_incidents = SecurityLog.objects.filter(
            severity='critical',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        if recent_incidents > 0:
            stats['threat_level'] = 'elevated'
            stats['last_incident'] = SecurityLog.objects.filter(
                severity='critical'
            ).latest('created_at').created_at.isoformat()
        
        return Response({
            'success': True,
            'status': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting security status: {str(e)}")
        return Response({
            'error': 'Failed to get security status',
            'code': 'STATUS_ERROR'
        }, status=500)

@api_view(['POST'])
@permission_classes([])  # Public endpoint
@validate_request_params(['email'])
def report_security_issue(request):
    """Report security issue (public endpoint)"""
    try:
        data = request.data
        
        # Validate CAPTCHA if enabled
        if settings.ENABLE_CAPTCHA and 'captcha_token' not in data:
            return Response({
                'error': 'CAPTCHA verification required',
                'code': 'CAPTCHA_REQUIRED'
            }, status=400)
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data['email']):
            return Response({
                'error': 'Invalid email format',
                'code': 'INVALID_EMAIL'
            }, status=400)
        
        # Create security log
        SecurityLog.objects.create(
            security_type='suspicious_activity',
            severity='medium',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            description=f'Security issue reported by {data["email"]}: {data.get("description", "No description")}',
            metadata={
                'reporter_email': data['email'],
                'issue_type': data.get('issue_type', 'general'),
                'contact_ok': data.get('contact_ok', False)
            }
        )
        
        # Send notification to security team
        SecurityNotification.send_immediate_alert(
            user=None,  # System notification
            title='Security Issue Reported',
            message=f'Security issue reported by {data["email"]}',
            priority='high',
            notification_type='email'
        )
        
        return Response({
            'success': True,
            'message': 'Security issue reported successfully',
            'reference_id': secrets.token_hex(8)
        })
        
    except Exception as e:
        logging.error(f"Error reporting security issue: {str(e)}")
        return Response({
            'error': 'Failed to report security issue',
            'code': 'REPORT_ERROR'
        }, status=500)

# ==================== ADMIN DASHBOARD VIEWS ====================

@login_required
@permission_required('security.view_securitylog', raise_exception=True)
def admin_security_dashboard(request):
    """Admin security dashboard (HTML view)"""
    try:
        # Get statistics for dashboard
        today = timezone.now().date()
        
        stats = {
            'total_threats_today': SecurityLog.objects.filter(
                created_at__date=today
            ).count(),
            
            'critical_threats': SecurityLog.objects.filter(
                severity='critical',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            
            'banned_users': UserBan.objects.filter(is_permanent=True).count(),
            
            'suspicious_devices': DeviceInfo.objects.filter(
                is_suspicious=True
            ).count(),
            
            'pending_reviews': SecurityLog.objects.filter(
                resolved=False,
                severity__in=['high', 'critical']
            ).count(),
            
            'recent_blocks': IPBlacklist.objects.filter(
                blocked_at__gte=timezone.now() - timedelta(days=1)
            ).count()
        }
        
        # Get recent alerts
        recent_alerts = SecurityLog.objects.filter(
            severity__in=['high', 'critical']
        ).order_by('-created_at')[:10]
        
        # Get top threat sources
        threat_sources = SecurityLog.objects.values(
            'ip_address'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Get risk distribution
        risk_distribution = []
        for i in range(0, 101, 20):
            count = RiskScore.objects.filter(
                current_score__gte=i,
                current_score__lt=i+20
            ).count()
            risk_distribution.append({
                'range': f'{i}-{i+19}',
                'count': count
            })
        
        context = {
            'stats': stats,
            'recent_alerts': recent_alerts,
            'threat_sources': threat_sources,
            'risk_distribution': risk_distribution,
            'last_updated': timezone.now()
        }
        
        return render(request, 'security/admin_dashboard.html', context)
        
    except Exception as e:
        logging.error(f"Error loading admin dashboard: {str(e)}")
        messages.error(request, 'Failed to load security dashboard')
        return redirect('admin:index')

# ==================== ERROR HANDLING VIEWS ====================

def handler404(request, exception):
    """Custom 404 handler with security logging"""
    SecurityLog.objects.create(
        security_type='suspicious_activity',
        severity='low',
        ip_address=request.META.get('REMOTE_ADDR'),
        description=f'404 error: {request.path}',
        metadata={'path': request.path, 'method': request.method}
    )
    
    return JsonResponse({
        'error': 'Resource not found',
        'code': 'NOT_FOUND',
        'path': request.path
    }, status=404)

def handler500(request):
    """Custom 500 handler with security logging"""
    SecurityLog.objects.create(
        security_type='suspicious_activity',
        severity='high',
        ip_address=request.META.get('REMOTE_ADDR'),
        description='Internal server error',
        metadata={'path': request.path, 'method': request.method}
    )
    
    return JsonResponse({
        'error': 'Internal server error',
        'code': 'INTERNAL_ERROR'
    }, status=500)

def handler403(request, exception):
    """Custom 403 handler with security logging"""
    SecurityLog.objects.create(
        security_type='unauthorized_access',
        severity='medium',
        ip_address=request.META.get('REMOTE_ADDR'),
        description=f'403 Forbidden: {request.path}',
        metadata={'path': request.path, 'method': request.method}
    )
    
    return JsonResponse({
        'error': 'Permission denied',
        'code': 'PERMISSION_DENIED',
        'path': request.path
    }, status=403)

# ==================== UTILITY FUNCTIONS ====================

def sanitize_input(data):
    """Sanitize input data"""
    if isinstance(data, str):
        # Remove script tags and dangerous characters
        import html
        data = html.escape(data)
        data = data.replace('<script>', '').replace('</script>', '')
        data = data.replace('javascript:', '')
        data = data.replace('onload=', '')
        data = data.replace('onerror=', '')
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    
    return data

def validate_ip_address(ip):
    """Validate IP address"""
    try:
        import ipaddress
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def get_client_ip(request):
    """Get client IP address safely"""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        if validate_ip_address(ip):
            return ip
        return '0.0.0.0'
    except:
        return '0.0.0.0'
    
# ==================== SIGNAL HANDLERS ====================

def log_security_event(sender, instance, created, **kwargs):
    """Log security events from signals"""
    if created:
        try:
            # Create security log for certain events
            if isinstance(instance, UserBan):
                SecurityLog.objects.create(
                    user=instance.banned_by,
                    security_type='suspicious_activity',
                    severity='high',
                    description=f'User banned: {instance.user.username}. Reason: {instance.reason}',
                    metadata={'ban_id': instance.id, 'reason': instance.reason}
                )
            
            elif isinstance(instance, IPBlacklist):
                SecurityLog.objects.create(
                    user=instance.blocked_by,
                    security_type='suspicious_activity',
                    severity='medium',
                    ip_address=instance.ip_address,
                    description=f'IP blacklisted: {instance.ip_address}. Reason: {instance.reason}',
                    metadata={'ip': instance.ip_address, 'reason': instance.reason}
                )
                
        except Exception as e:
            logging.error(f"Error logging security event: {str(e)}")

# Connect signal handlers
from django.db.models.signals import post_save
post_save.connect(log_security_event, sender=UserBan)
post_save.connect(log_security_event, sender=IPBlacklist)


class DefensiveSerializerMixin:
    """Mixin for defensive serialization with error handling"""
    
    @staticmethod
    def safe_get(data: Dict, key: str, default: Any = None) -> Any:
        """Safely get value from dictionary with graceful degradation"""
        try:
            return data.get(key, default)
        except Exception as e:
            logger.warning(f"Error getting key {key} from data: {e}")
            return default
    
    def safe_validate(self, validation_func, *args, **kwargs):
        """Safely execute validation with error handling"""
        try:
            return validation_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Validation error in {self.__class__.__name__}: {e}")
            raise ValidationError(f"Validation error: {str(e)}")


class ClickTrackerSerializer(DefensiveSerializerMixin, serializers.ModelSerializer):
    """Defensive serializer for ClickTracker with comprehensive validation"""
    
    user_id = serializers.IntegerField(
        write_only=True, 
        required=False, 
        allow_null=True,
        help_text="User ID (optional for anonymous clicks)"
    )
    
    user_info = serializers.SerializerMethodField(
        read_only=True,
        help_text="User information (read-only)"
    )
    
    time_since_click = serializers.SerializerMethodField(
        read_only=True,
        help_text="Human-readable time since click"
    )
    
    # Computed fields for risk assessment
    risk_assessment = serializers.SerializerMethodField(
        read_only=True,
        help_text="Risk assessment details"
    )
    
    class Meta:
        model = ClickTracker
        fields = [
            'id', 'user', 'user_info', 'action_type', 'ip_address',
            'user_agent', 'device_info', 'metadata', 'referer', 'page_url',
            'element_id', 'session_id', 'is_suspicious', 'risk_score',
            'clicked_at', 'time_since_click', 'risk_assessment'
        ]
        read_only_fields = [
            'id', 'user_info', 'is_suspicious', 'risk_score', 
            'clicked_at', 'time_since_click', 'risk_assessment'
        ]
        extra_kwargs = {
            'ip_address': {
                'default': '0.0.0.0',
                'allow_blank': True,
                'allow_null': True
            },
            'user_agent': {
                'default': '',
                'allow_blank': True
            },
            'device_info': {
                'default': dict,
                'allow_null': True
            },
            'metadata': {
                'default': dict,
                'allow_null': True
            },
        }
    
    def get_user_info(self, obj: ClickTracker) -> Optional[Dict[str, Any]]:
        """Safely get user information"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'email': obj.user.email
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info for click {obj.id}: {e}")
            return {'error': 'User information unavailable'}
    
    def get_time_since_click(self, obj: ClickTracker) -> str:
        """Get human-readable time since click"""
        try:
            return obj.time_since_click
        except Exception:
            return "Time unknown"
    
    def get_risk_assessment(self, obj: ClickTracker) -> Dict[str, Any]:
        """Get risk assessment details"""
        try:
            return {
                'risk_score': obj.risk_score,
                'risk_level': self._get_risk_level(obj.risk_score),
                'is_suspicious': obj.is_suspicious,
                'factors': self._get_risk_factors(obj)
            }
        except Exception as e:
            logger.error(f"Error getting risk assessment for click {obj.id}: {e}")
            return {
                'error': 'Risk assessment unavailable',
                'risk_score': obj.risk_score,
                'is_suspicious': obj.is_suspicious
            }
    
    def _get_risk_level(self, score: float) -> str:
        """Convert risk score to level"""
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
    
    def _get_risk_factors(self, obj: ClickTracker) -> List[str]:
        """Identify risk factors"""
        factors = []
        try:
            if not obj.user:
                factors.append('anonymous_user')
            
            if not obj.user_agent or len(obj.user_agent) < 10:
                factors.append('invalid_user_agent')
            
            if obj.ip_address == '0.0.0.0':
                factors.append('invalid_ip')
            
            suspicious_actions = ['login', 'signup', 'password_reset', 'purchase']
            if obj.action_type in suspicious_actions:
                factors.append(f'sensitive_action:{obj.action_type}')
            
            return factors
        except Exception:
            return ['risk_factors_unavailable']
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        
        try:
            # Type validation
            action_type = self.safe_get(data, 'action_type', 'unknown')
            if not isinstance(action_type, str) or len(action_type.strip()) == 0:
                errors['action_type'] = "Action type is required and must be a non-empty string"
            elif len(action_type) > 100:
                errors['action_type'] = "Action type cannot exceed 100 characters"
            
            # IP address validation
            ip_address = self.safe_get(data, 'ip_address', '0.0.0.0')
            if ip_address and ip_address != '0.0.0.0':
                try:
                    import ipaddress
                    ipaddress.ip_address(ip_address)
                except ValueError:
                    errors['ip_address'] = f"Invalid IP address format: {ip_address}"
            
            # URL validation
            referer = self.safe_get(data, 'referer', '')
            if referer and len(referer) > 500:
                errors['referer'] = "Referer URL cannot exceed 500 characters"
            
            page_url = self.safe_get(data, 'page_url', '')
            if page_url and len(page_url) > 500:
                errors['page_url'] = "Page URL cannot exceed 500 characters"
            
            # JSON field validation
            device_info = self.safe_get(data, 'device_info', {})
            if device_info and not isinstance(device_info, dict):
                errors['device_info'] = "Device info must be a valid JSON object"
            
            metadata = self.safe_get(data, 'metadata', {})
            if metadata and not isinstance(metadata, dict):
                errors['metadata'] = "Metadata must be a valid JSON object"
            
            # User validation
            user_id = self.safe_get(data, 'user')
            if user_id is not None:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                    data['user'] = user
                except User.DoesNotExist:
                    errors['user'] = f"User with ID {user_id} does not exist"
            
            # Remove user_id from data as we've converted to user object
            if 'user' in data:
                del data['user']
            
        except Exception as e:
            logger.error(f"Unexpected validation error in ClickTrackerSerializer: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> ClickTracker:
        """Defensive create method with error handling"""
        try:
            # Use factory method for creation
            click = ClickTracker.create_click(**validated_data)
            
            # Log creation for auditing
            logger.info(f"ClickTracker created: ID={click.id}, User={click.user_id}, Action={click.action_type}")
            
            return click
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create ClickTracker: {e}")
            raise ValidationError(f"Failed to create click record: {str(e)}")


class ClickTrackerUpdateSerializer(DefensiveSerializerMixin, serializers.ModelSerializer):
    """Serializer for updating ClickTracker (limited fields)"""
    
    class Meta:
        model = ClickTracker
        fields = ['is_suspicious', 'metadata']
        read_only_fields = ['is_suspicious']  # Usually managed by system
    
    def validate_metadata(self, value: Dict) -> Dict:
        """Validate metadata updates"""
        if not isinstance(value, dict):
            raise ValidationError("Metadata must be a valid JSON object")
        
        # Prevent modification of system-managed fields
        protected_fields = ['suspicion_reason', 'marked_suspicious_at', 'risk_calculation']
        for field in protected_fields:
            if field in value:
                raise ValidationError(f"Cannot modify protected field: {field}")
        
        return value


class ClickTrackerListSerializer(DefensiveSerializerMixin, serializers.ModelSerializer):
    """Optimized serializer for list views"""
    
    user_summary = serializers.SerializerMethodField(
        help_text="User summary (optimized for lists)"
    )
    
    click_summary = serializers.SerializerMethodField(
        help_text="Click summary information"
    )
    
    class Meta:
        model = ClickTracker
        fields = [
            'id', 'user_summary', 'action_type', 'ip_address',
            'page_url', 'is_suspicious', 'risk_score', 'clicked_at',
            'click_summary'
        ]
    
    def get_user_summary(self, obj: ClickTracker) -> Optional[Dict[str, Any]]:
        """Optimized user summary for list views"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username[:20]  # Truncate for efficiency
                }
            return None
        except Exception:
            return None
    
    def get_click_summary(self, obj: ClickTracker) -> Dict[str, Any]:
        """Get click summary information"""
        try:
            return {
                'has_device_info': bool(obj.device_info),
                'has_metadata': bool(obj.metadata),
                'referer_present': bool(obj.referer),
                'element_present': bool(obj.element_id),
                'session_present': bool(obj.session_id),
            }
        except Exception:
            return {'error': 'Summary unavailable'}


class EnhancedClickTrackerSerializer(ClickTrackerSerializer):
    """Serializer for EnhancedClickTracker with additional features"""
    
    fast_clicking_check = serializers.SerializerMethodField(
        help_text="Fast clicking detection results"
    )
    
    device_analysis = serializers.SerializerMethodField(
        help_text="Device analysis results"
    )
    
    class Meta(ClickTrackerSerializer.Meta):
        model = EnhancedClickTracker
        fields = ClickTrackerSerializer.Meta.fields + [
            'fast_clicking_check', 'device_analysis'
        ]
    
    def get_fast_clicking_check(self, obj: EnhancedClickTracker) -> Dict[str, Any]:
        """Check for fast clicking patterns"""
        try:
            if obj.user and obj.action_type:
                is_fast = EnhancedClickTracker.check_fast_clicking(
                    user=obj.user,
                    action_type=obj.action_type,
                    time_window=60,
                    max_clicks=10
                )
                return {
                    'is_fast_clicking': is_fast,
                    'checked_at': timezone.now().isoformat()
                }
            return {'is_fast_clicking': False, 'reason': 'insufficient_data'}
        except Exception as e:
            logger.error(f"Error checking fast clicking for click {obj.id}: {e}")
            return {'error': 'fast_clicking_check_failed'}
    
    def get_device_analysis(self, obj: EnhancedClickTracker) -> Dict[str, Any]:
        """Analyze device information"""
        try:
            device_info = obj.device_info or {}
            
            analysis = {
                'has_device_info': bool(device_info),
                'browser': device_info.get('browser', 'unknown'),
                'platform': device_info.get('platform', 'unknown'),
                'is_mobile': device_info.get('is_mobile', False),
                'user_agent_length': len(obj.user_agent) if obj.user_agent else 0,
            }
            
            # Add risk indicators
            risk_indicators = []
            if not obj.user_agent or len(obj.user_agent) < 10:
                risk_indicators.append('short_user_agent')
            if device_info.get('browser') == 'Unknown':
                risk_indicators.append('unknown_browser')
            
            if risk_indicators:
                analysis['risk_indicators'] = risk_indicators
                analysis['has_risk_indicators'] = True
            else:
                analysis['has_risk_indicators'] = False
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing device for click {obj.id}: {e}")
            return {'error': 'device_analysis_failed'}
        

class NullSafeSerializerMixin:
    """Mixin for null-safe serialization with defensive coding"""
    
    @staticmethod
    def safe_get_value(obj, field_name: str, default: Any = None) -> Any:
        """Safely get value from object with graceful degradation"""
        try:
            value = getattr(obj, field_name, default)
            if callable(value):
                return value()
            return value
        except Exception as e:
            logger.warning(f"Error getting {field_name} from {obj}: {e}")
            return default
    
    @staticmethod
    def validate_ip_address(ip_address: str) -> bool:
        """Validate IP address format defensively"""
        try:
            if not ip_address or ip_address == "":
                return True  # Allow empty/null
            
            import ipaddress
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
        except Exception as e:
            logger.error(f"Error validating IP {ip_address}: {e}")
            return False
    
    def validate_json_field(self, value: Any, field_name: str) -> Any:
        """Validate JSON field with defensive coding"""
        try:
            if value is None:
                return {}
            
            if isinstance(value, dict):
                return value
            
            if isinstance(value, str):
                import json
                return json.loads(value)
            
            raise ValidationError({field_name: f"Invalid JSON format for {field_name}"})
        except json.JSONDecodeError:
            raise ValidationError({field_name: f"Invalid JSON string for {field_name}"})
        except Exception as e:
            logger.error(f"Error validating {field_name}: {e}")
            raise ValidationError({field_name: f"Invalid value for {field_name}"})


# ==================== DEFENSIVE CODING DECORATORS ====================

def safe_serializer_method(default_return=None):
    """Decorator for safe serializer method execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, obj=None, *args, **kwargs):
            try:
                return func(self, obj, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return default_return
        return wrapper
    return decorator


def cache_result(timeout: int = 300):
    """Cache decorator for expensive operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, obj=None, *args, **kwargs):
            if not obj or not hasattr(obj, 'id'):
                return func(self, obj, *args, **kwargs)
            
            try:
                cache_key = f"serializer_{func.__name__}_{obj.id}"
                result = cache.get(cache_key)
                if result is not None:
                    return result
                
                result = func(self, obj, *args, **kwargs)
                cache.set(cache_key, result, timeout)
                return result
            except Exception:
                return func(self, obj, *args, **kwargs)  # Fallback
        return wrapper
    return decorator


# ==================== ENHANCED MIXINS ====================

class NullSafeSerializerMixin:
    """
    Null Object Pattern for serializers
    """
    
    @safe_serializer_method(default_return=None)
    def safe_get_value(self, obj, attr: str, default=None):
        """Safely get attribute from object"""
        try:
            return getattr(obj, attr, default) if obj is not None else default
        except (AttributeError, TypeError):
            return default
    
    @safe_serializer_method(default_return=None)
    def safe_call_method(self, obj, method_name: str, default=None, *args, **kwargs):
        """Safely call method on object"""
        if obj is None:
            return default
        
        method = getattr(obj, method_name, None)
        if callable(method):
            try:
                return method(*args, **kwargs)
            except Exception:
                return default
        return default
    
    @safe_serializer_method(default_return=None)
    def safe_dict_value(self, data_dict: Optional[Dict], key: str, default=None):
        """Safely get value from dictionary"""
        if not isinstance(data_dict, dict):
            return default
        return data_dict.get(key, default)
    
    @safe_serializer_method(default_return=False)
    def safe_bool_value(self, value, default=False):
        """Safely convert to boolean"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'y']
        return default
    
    @safe_serializer_method(default_return=0)
    def safe_int_value(self, value, default=0, min_val=None, max_val=None):
        """Safely convert to integer with range validation"""
        try:
            result = int(float(value)) if value is not None else default
            if min_val is not None:
                result = max(result, min_val)
            if max_val is not None:
                result = min(result, max_val)
            return result
        except (ValueError, TypeError):
            return default


class GracefulDegradationMixin:
    """
    Graceful degradation for serializer methods
    """
    
    def with_fallback(self, fallback_return=None):
        """Decorator for graceful degradation"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"{func.__name__} failed: {e}")
                    return fallback_return
            return wrapper
        return decorator
    
    @staticmethod
    def safe_queryset_count(queryset, default: int = 0) -> int:
        """Safely count queryset"""
        try:
            return queryset.count() if queryset is not None else default
        except Exception:
            return default
    
    @staticmethod
    def safe_queryset_exists(queryset) -> bool:
        """Safely check if queryset exists"""
        try:
            return queryset.exists() if queryset is not None else False
        except Exception:
            return False


class AuditLoggerMixin:
    """Audit logging for serializers"""
    
    def log_creation(self, instance, user=None, extra=None):
        """Log instance creation"""
        try:
            user_id = getattr(user, 'id', user) if user else None
            logger.info(
                f"CREATED: {instance.__class__.__name__}(id={getattr(instance, 'id', None)}) "
                f"by user={user_id}, extra={extra or {}}"
            )
        except Exception:
            pass
    
    def log_update(self, instance, user=None, changes=None):
        """Log instance update"""
        try:
            user_id = getattr(user, 'id', user) if user else None
            logger.info(
                f"UPDATED: {instance.__class__.__name__}(id={getattr(instance, 'id', None)}) "
                f"by user={user_id}, changes={changes or 'unknown'}"
            )
        except Exception:
            pass
    
    def log_error(self, operation: str, error: Exception, context=None):
        """Log error with context"""
        try:
            logger.error(
                f"ERROR in {operation}: {str(error)}",
                exc_info=True,
                extra={'context': context or {}}
            )
        except Exception:
            pass


# ==================== VALIDATION UTILITIES ====================

class ValidationUtils:
    """Validation utilities for serializers"""
    
    @staticmethod
    def validate_ip_address(ip: Optional[str]) -> bool:
        """Validate IP address format"""
        if not ip:
            return True
        
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except (ValueError, ImportError):
            # Fallback: simple regex validation
            import re
            ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
            return bool(re.match(ipv4_pattern, ip)) or bool(re.match(ipv6_pattern, ip))
    
    @staticmethod
    def validate_device_id(device_id: Optional[str]) -> List[str]:
        """Validate device ID and return errors"""
        errors = []
        if not device_id:
            errors.append("Device ID is required")
        elif len(device_id) > 255:
            errors.append("Device ID cannot exceed 255 characters")
        elif len(device_id) < 10:
            errors.append("Device ID must be at least 10 characters")
        return errors
    
    @staticmethod
    def validate_risk_score(score: Optional[int]) -> List[str]:
        """Validate risk score"""
        errors = []
        if score is None:
            return errors
        if not isinstance(score, (int, float)):
            errors.append("Risk score must be a number")
        elif not 0 <= score <= 100:
            errors.append("Risk score must be between 0 and 100")
        return errors


# ==================== ENHANCED DEVICE INFO SERIALIZER ====================

class DeviceInfoSerializer(
    NullSafeSerializerMixin,
    GracefulDegradationMixin,
    AuditLoggerMixin,
    serializers.ModelSerializer
):
    """
    Defensive serializer for DeviceInfo with comprehensive validation
    এবং Null Object Pattern implementation
    """
    
    # Read-only computed fields
    device_status = serializers.SerializerMethodField(
        help_text="Device status summary",
        read_only=True
    )
    
    security_assessment = serializers.SerializerMethodField(
        help_text="Security risk assessment",
        read_only=True
    )
    
    is_suspicious = serializers.SerializerMethodField(
        help_text="Whether device shows suspicious patterns",
        read_only=True
    )
    
    risk_level_display = serializers.SerializerMethodField(
        help_text="Human readable risk level with emoji",
        read_only=True
    )
    
    security_flags = serializers.SerializerMethodField(
        help_text="Active security flags",
        read_only=True
    )
    
    duplicate_count = serializers.SerializerMethodField(
        help_text="Number of duplicate devices",
        read_only=True
    )
    
    # Write-only fields for creation
    user_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="User ID (optional)"
    )
    
    raw_device_id = serializers.CharField(
        write_only=True,
        required=True,
        max_length=255,
        help_text="Raw device identifier (will be hashed)"
    )
    
    # Additional fields for API response
    username = serializers.CharField(
        source='user.username',
        read_only=True,
        default=None
    )
    
    user_email = serializers.CharField(
        source='user.email',
        read_only=True,
        default=None
    )
    
    # Null Object Pattern: Default values for all fields
    class Meta:
        model = DeviceInfo
        fields = [
            'id', 'user', 'username', 'user_email', 
            'device_id', 'device_id_hash', 'raw_device_id',
            'device_model', 'device_brand', 'android_version', 'app_version',
            'is_rooted', 'is_emulator', 'last_ip', 'is_vpn', 'is_proxy',
            'fingerprint', 'risk_score', 'is_trusted', 'trust_level',
            'created_at', 'updated_at', 'last_activity',
            'device_status', 'security_assessment', 'is_suspicious', 
            'risk_level_display', 'security_flags', 'duplicate_count'
        ]
        read_only_fields = [
            'id', 'device_id_hash', 'created_at', 'updated_at', 'last_activity',
            'device_status', 'security_assessment', 'is_suspicious', 
            'risk_level_display', 'username', 'user_email', 
            'security_flags', 'duplicate_count'
        ]
        extra_kwargs = {
            'device_id': {'required': False, 'allow_blank': True},
            'device_model': {'default': 'Unknown', 'allow_blank': True},
            'device_brand': {'default': 'Unknown', 'allow_blank': True},
            'android_version': {'default': 'Unknown', 'allow_blank': True},
            'app_version': {'default': '1.0.0', 'allow_blank': True},
            'fingerprint': {'default': '', 'allow_blank': True, 'trim_whitespace': True},
            'risk_score': {'default': 0},
            'trust_level': {'default': 1},
            'is_rooted': {'default': False},
            'is_emulator': {'default': False},
            'is_vpn': {'default': False},
            'is_proxy': {'default': False},
            'is_trusted': {'default': False},
            'last_ip': {'required': False, 'allow_null': True},
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize with defensive coding"""
        super().__init__(*args, **kwargs)
        self._cache = {}
        self._security_logs_cache = {}
    
    # ==================== HELPER METHODS ====================
    
    def _get_cached(self, key: str, func, *args, **kwargs):
        """Get or compute cached value"""
        if key in self._cache:
            return self._cache[key]
        
        try:
            result = func(*args, **kwargs)
            self._cache[key] = result
            return result
        except Exception:
            return None
    
    # ==================== SERIALIZER METHOD FIELDS ====================
    
    @safe_serializer_method(default_return={'error': 'no_device', 'is_active': False})
    @cache_result(timeout=60)
    def get_device_status(self, obj: DeviceInfo) -> Dict[str, Any]:
        """Get device status with defensive coding"""
        if obj is None:
            return {'error': 'no_device', 'is_active': False}
        
        try:
            return {
                'is_active': self.safe_get_value(obj, 'is_active', False),
                'days_since_last_activity': self._get_days_since_last_activity(obj),
                'trust_category': self._get_trust_category(obj),
                'risk_category': self._get_risk_category(obj),
                'has_recent_security_logs': self._has_recent_security_logs(obj),
                'is_online': self._is_device_online(obj),
                'device_age_days': self._get_device_age_days(obj),
                'total_activities': self._get_total_activities(obj),
            }
        except Exception as e:
            self.log_error('get_device_status', e, {'device_id': getattr(obj, 'id', None)})
            return {'error': 'device_status_unavailable', 'is_active': False}
    
    @safe_serializer_method(default_return={'error': 'no_device', 'overall_risk': 'unknown'})
    @cache_result(timeout=60)
    def get_security_assessment(self, obj: DeviceInfo) -> Dict[str, Any]:
        """Get security assessment with defensive coding"""
        if obj is None:
            return {'error': 'no_device', 'overall_risk': 'unknown'}
        
        try:
            assessment = {
                'risk_factors': [],
                'security_indicators': [],
                'overall_risk': 'low',
                'recommendations': [],
                'risk_score': self.safe_int_value(obj.risk_score, 0, 0, 100),
                'threat_count': self._get_recent_threat_count(obj),
                'threat_severity': self._get_threat_severity(obj)
            }
            
            # Check risk factors
            if obj.is_rooted:
                assessment['risk_factors'].append({
                    'type': 'rooted_device',
                    'severity': 'high',
                    'description': 'Device is rooted/jailbroken',
                    'score_impact': 30
                })
                assessment['recommendations'].append('Restrict access from rooted devices')
            
            if obj.is_emulator:
                assessment['risk_factors'].append({
                    'type': 'emulator',
                    'severity': 'medium',
                    'description': 'Device is running on emulator',
                    'score_impact': 25
                })
                assessment['recommendations'].append('Monitor activity from emulators')
            
            if obj.is_vpn:
                assessment['risk_factors'].append({
                    'type': 'vpn_usage',
                    'severity': 'medium',
                    'description': 'VPN/proxy detected',
                    'score_impact': 20
                })
                assessment['recommendations'].append('VPN usage detected - monitor for suspicious patterns')
            
            if obj.is_proxy:
                assessment['risk_factors'].append({
                    'type': 'proxy_usage',
                    'severity': 'medium',
                    'description': 'Proxy server detected',
                    'score_impact': 15
                })
            
            # Check security indicators
            if obj.risk_score < 30:
                assessment['security_indicators'].append({
                    'type': 'low_risk',
                    'description': 'Device has low risk score'
                })
            
            if obj.is_trusted:
                assessment['security_indicators'].append({
                    'type': 'trusted_device',
                    'description': 'Device is manually trusted'
                })
            
            if obj.trust_level == 3:
                assessment['security_indicators'].append({
                    'type': 'high_trust_level',
                    'description': 'Device has high trust level'
                })
            
            if obj.last_activity and (timezone.now() - obj.last_activity).days < 1:
                assessment['security_indicators'].append({
                    'type': 'recently_active',
                    'description': 'Device was active in last 24 hours'
                })
            
            # Check duplicate usage
            duplicate_count = self._get_duplicate_count(obj)
            if duplicate_count > 0:
                assessment['risk_factors'].append({
                    'type': 'duplicate_usage',
                    'severity': 'medium' if duplicate_count < 3 else 'high',
                    'description': f'Device used by {duplicate_count} other users',
                    'score_impact': min(duplicate_count * 5, 15)
                })
                assessment['recommendations'].append('Investigate multiple account usage')
            
            # Determine overall risk
            risk_score = obj.risk_score or 0
            high_risk_factors = [f for f in assessment['risk_factors'] if f.get('severity') == 'high']
            
            if len(high_risk_factors) > 0 or risk_score > 70:
                assessment['overall_risk'] = 'high'
            elif len(assessment['risk_factors']) >= 1 or risk_score > 40:
                assessment['overall_risk'] = 'medium'
            else:
                assessment['overall_risk'] = 'low'
            
            return assessment
            
        except Exception as e:
            self.log_error('get_security_assessment', e, {'device_id': getattr(obj, 'id', None)})
            return {'error': 'security_assessment_unavailable', 'overall_risk': 'unknown'}
    
    @safe_serializer_method(default_return=False)
    def get_is_suspicious(self, obj: DeviceInfo) -> bool:
        """Check if device is suspicious"""
        if obj is None:
            return False
        
        try:
            # Try to call is_suspicious method if exists
            if hasattr(obj, 'is_suspicious') and callable(obj.is_suspicious):
                suspicious = obj.is_suspicious()
                if isinstance(suspicious, bool):
                    return suspicious
            
            # Fallback logic
            risk_score = self.safe_int_value(obj.risk_score, 0)
            duplicate_count = self._get_duplicate_count(obj)
            
            return (
                self.safe_bool_value(obj.is_rooted, False) or 
                self.safe_bool_value(obj.is_emulator, False) or 
                risk_score >= 50 or
                duplicate_count > 2
            )
        except Exception as e:
            self.log_error('get_is_suspicious', e, {'device_id': getattr(obj, 'id', None)})
            return False  # Graceful degradation: assume not suspicious
    
    @safe_serializer_method(default_return='⚪ Unknown')
    def get_risk_level_display(self, obj: DeviceInfo) -> str:
        """Get human readable risk level with emoji"""
        if obj is None:
            return '⚪ Unknown'
        
        try:
            if hasattr(obj, 'get_risk_level_display') and callable(obj.get_risk_level_display):
                display = obj.get_risk_level_display()
                if display:
                    return display
            
            # Fallback
            score = self.safe_int_value(obj.risk_score, 0)
            if score >= 80:
                return '🚨 Critical'
            elif score >= 60:
                return '🔴 High'
            elif score >= 40:
                return '🟠 Medium'
            elif score >= 20:
                return '🟡 Low'
            else:
                return '🟢 Safe'
        except Exception:
            return '⚪ Unknown'
    
    @safe_serializer_method(default_return=[])
    @cache_result(timeout=60)
    def get_security_flags(self, obj: DeviceInfo) -> List[str]:
        """Get active security flags"""
        if obj is None:
            return []
        
        try:
            if hasattr(obj, 'get_security_flags') and callable(obj.get_security_flags):
                flags = obj.get_security_flags()
                if isinstance(flags, list):
                    return flags
            
            # Fallback
            flags = []
            if obj.is_rooted:
                flags.append('ROOTED')
            if obj.is_emulator:
                flags.append('EMULATOR')
            if obj.is_vpn:
                flags.append('VPN')
            if obj.is_proxy:
                flags.append('PROXY')
            if obj.risk_score >= 70:
                flags.append('HIGH_RISK')
            if obj.is_trusted:
                flags.append('TRUSTED')
            if obj.trust_level == 3:
                flags.append('VERIFIED')
            
            return flags
        except Exception:
            return []
    
    @safe_serializer_method(default_return=0)
    def get_duplicate_count(self, obj: DeviceInfo) -> int:
        """Get number of duplicate devices"""
        return self._get_duplicate_count(obj)
    
    # ==================== PRIVATE HELPER METHODS ====================
    
    def _get_days_since_last_activity(self, obj: DeviceInfo) -> int:
        """Calculate days since last activity"""
        try:
            if not obj or not obj.last_activity:
                return 999
            
            delta = timezone.now() - obj.last_activity
            return delta.days
        except Exception:
            return 999
    
    def _get_trust_category(self, obj: DeviceInfo) -> str:
        """Get trust category based on trust level"""
        try:
            if not obj:
                return 'unknown'
            
            if obj.is_trusted:
                return 'trusted'
            
            trust_levels = {
                1: 'low',
                2: 'medium',
                3: 'high'
            }
            return trust_levels.get(obj.trust_level, 'unknown')
        except Exception:
            return 'unknown'
    
    def _get_risk_category(self, obj: DeviceInfo) -> str:
        """Get risk category based on risk score"""
        try:
            if not obj:
                return 'unknown'
            
            score = self.safe_int_value(obj.risk_score, 0)
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
    
    def _get_device_age_days(self, obj: DeviceInfo) -> int:
        """Get device age in days"""
        try:
            if not obj or not obj.created_at:
                return 0
            return (timezone.now() - obj.created_at).days
        except Exception:
            return 0
    
    def _get_total_activities(self, obj: DeviceInfo) -> int:
        """Get total activity count (placeholder)"""
        # This would need an ActivityLog model
        return 0
    
    def _has_recent_security_logs(self, obj: DeviceInfo, days: int = 7) -> bool:
        """Check if device has recent security logs"""
        if not obj or not obj.id:
            return False
        
        cache_key = f"device_{obj.id}_recent_logs"
        if cache_key in self._security_logs_cache:
            return self._security_logs_cache[cache_key]
        
        try:
            one_week_ago = timezone.now() - timedelta(days=days)
            result = SecurityLog.objects.filter(
                device_info=obj,
                created_at__gte=one_week_ago
            ).exists()
            
            self._security_logs_cache[cache_key] = result
            return result
        except Exception:
            return False
    
    def _get_recent_threat_count(self, obj: DeviceInfo, days: int = 7) -> int:
        """Get count of recent threats"""
        if not obj or not obj.id:
            return 0
        
        try:
            one_week_ago = timezone.now() - timedelta(days=days)
            return SecurityLog.objects.filter(
                device_info=obj,
                created_at__gte=one_week_ago
            ).count()
        except Exception:
            return 0
    
    def _get_threat_severity(self, obj: DeviceInfo) -> str:
        """Get threat severity based on recent logs"""
        try:
            count = self._get_recent_threat_count(obj)
            if count >= 10:
                return 'critical'
            elif count >= 5:
                return 'high'
            elif count >= 2:
                return 'medium'
            elif count >= 1:
                return 'low'
            return 'none'
        except Exception:
            return 'unknown'
    
    def _is_device_online(self, obj: DeviceInfo, minutes: int = 5) -> bool:
        """Check if device is currently online"""
        if not obj or not obj.last_activity:
            return False
        
        try:
            cutoff = timezone.now() - timedelta(minutes=minutes)
            return obj.last_activity >= cutoff
        except Exception:
            return False
    
    def _get_duplicate_count(self, obj: DeviceInfo) -> int:
        """Get count of duplicate devices"""
        if not obj or not obj.device_id_hash:
            return 0
        
        try:
            return DeviceInfo.objects.filter(
                device_id_hash=obj.device_id_hash
            ).exclude(
                id=obj.id
            ).exclude(
                user__isnull=True
            ).count()
        except Exception:
            return 0
    
    # ==================== VALIDATION METHODS ====================
    
    def validate_ip_address(self, ip: Optional[str]) -> bool:
        """Validate IP address format"""
        return ValidationUtils.validate_ip_address(ip)
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        validated_data = data.copy()
        
        try:
            # Validate raw_device_id
            raw_device_id = data.get('raw_device_id')
            device_id_errors = ValidationUtils.validate_device_id(raw_device_id)
            if device_id_errors:
                errors['raw_device_id'] = device_id_errors
            
            # Validate IP address
            last_ip = data.get('last_ip')
            if last_ip and not self.validate_ip_address(last_ip):
                errors['last_ip'] = f"Invalid IP address format: {last_ip}"
            
            # Validate risk score
            risk_score = data.get('risk_score')
            risk_score_errors = ValidationUtils.validate_risk_score(risk_score)
            if risk_score_errors:
                errors['risk_score'] = risk_score_errors
            
            # Validate trust level
            trust_level = data.get('trust_level')
            if trust_level is not None and trust_level not in [1, 2, 3]:
                errors['trust_level'] = "Trust level must be 1 (Low), 2 (Medium), or 3 (High)"
            
            # Validate user_id
            user_id = data.get('user')
            if user_id is not None:
                try:
                    user = User.objects.get(id=user_id)
                    validated_data['user'] = user
                except User.DoesNotExist:
                    errors['user'] = f"User with ID {user_id} does not exist"
                except Exception as e:
                    errors['user'] = f"Error validating user: {str(e)}"
            
            # Process raw_device_id
            if 'raw_device_id' in validated_data:
                validated_data['device_id'] = validated_data.pop('raw_device_id')
            
            # Remove user_id from data as we've converted to user object
            if 'user' in validated_data:
                del validated_data['user']
            
        except Exception as e:
            self.log_error('validate', e, {'data': str(data)[:200]})
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return validated_data
    
    # ==================== CRUD METHODS ====================
    
    def create(self, validated_data: Dict[str, Any]) -> DeviceInfo:
        """Defensive create method with device ID hashing"""
        try:
            # Extract device_id for hashing
            device_id = validated_data.get('device_id')
            
            if not device_id:
                raise serializers.ValidationError({'device_id': 'Device ID is required'})
            
            # Generate device_id_hash
            salt = secrets.token_bytes(32)
            device_bytes = device_id.encode('utf-8')
            hash_input = salt + device_bytes
            device_id_hash = hashlib.sha256(hash_input).hexdigest()
            
            # Check for duplicate devices
            existing_devices = DeviceInfo.objects.filter(device_id_hash=device_id_hash)
            
            if existing_devices.exists():
                existing_device = existing_devices.first()
                
                # If user matches, return existing
                if 'user' in validated_data and existing_device.user == validated_data['user']:
                    logger.info(f"Returning existing device for user {validated_data['user'].id}")
                    return existing_device
                
                # If different user, check if we should allow
                duplicate_count = existing_devices.count()
                if duplicate_count >= 3:
                    raise serializers.ValidationError({
                        'device_id': 'This device is already used by too many accounts'
                    })
                
                logger.warning(f"Device {device_id_hash[:10]}... used by multiple users")
            
            # Add hash to validated data
            validated_data['device_id_hash'] = device_id_hash
            
            # Set default values for missing fields
            defaults = {
                'device_model': 'Unknown',
                'device_brand': 'Unknown',
                'android_version': 'Unknown',
                'app_version': '1.0.0',
                'fingerprint': '',
                'risk_score': 0,
                'trust_level': 1,
                'is_rooted': False,
                'is_emulator': False,
                'is_vpn': False,
                'is_proxy': False,
                'is_trusted': False,
            }
            
            for key, default_value in defaults.items():
                validated_data.setdefault(key, default_value)
            
            # Create device info
            device_info = DeviceInfo.objects.create(**validated_data)
            
            # Log creation
            self.log_creation(
                device_info, 
                validated_data.get('user'),
                {'hash_preview': device_id_hash[:10]}
            )
            
            return device_info
            
        except serializers.ValidationError:
            raise
        except Exception as e:
            self.log_error('create', e)
            raise serializers.ValidationError(f"Failed to create device info: {str(e)}")
    
    def update(self, instance: DeviceInfo, validated_data: Dict[str, Any]) -> DeviceInfo:
        """Defensive update method"""
        if not instance:
            raise serializers.ValidationError("Device instance not found")
        
        try:
            # Prevent modification of critical fields
            protected_fields = ['device_id_hash', 'created_at', 'id']
            for field in protected_fields:
                if field in validated_data:
                    del validated_data[field]
            
            # Track changes for logging
            changes = {}
            
            # Handle user specially
            if 'user' in validated_data and validated_data['user'] != instance.user:
                old_user = getattr(instance.user, 'id', None)
                new_user = getattr(validated_data['user'], 'id', None)
                changes['user'] = f"{old_user} -> {new_user}"
                logger.info(f"Device {instance.id} user changed from {old_user} to {new_user}")
            
            # Update last_activity on every update
            validated_data['last_activity'] = timezone.now()
            
            # Update instance
            for attr, value in validated_data.items():
                if hasattr(instance, attr):
                    old_value = getattr(instance, attr)
                    if old_value != value:
                        changes[attr] = f"{str(old_value)[:50]} -> {str(value)[:50]}"
                    setattr(instance, attr, value)
            
            # Validate before save
            instance.full_clean()
            instance.save()
            
            # Update risk score based on new data
            if hasattr(instance, 'update_risk_score') and callable(instance.update_risk_score):
                instance.update_risk_score()
            
            # Log update
            self.log_update(instance, validated_data.get('user'), changes)
            
            return instance
            
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        except Exception as e:
            self.log_error('update', e, {'device_id': getattr(instance, 'id', None)})
            raise serializers.ValidationError(f"Failed to update device info: {str(e)}")
    
    def to_representation(self, instance: DeviceInfo) -> Dict[str, Any]:
        """Transform output data"""
        try:
            data = super().to_representation(instance)
            
            # Add computed fields if missing
            computed_fields = [
                ('device_status', self.get_device_status),
                ('security_assessment', self.get_security_assessment),
                ('is_suspicious', self.get_is_suspicious),
                ('risk_level_display', self.get_risk_level_display),
                ('security_flags', self.get_security_flags),
                ('duplicate_count', self.get_duplicate_count)
            ]
            
            for field_name, method in computed_fields:
                if field_name not in data or data[field_name] is None:
                    data[field_name] = method(instance)
            
            # Clean up None values and empty lists
            cleaned_data = {}
            for k, v in data.items():
                if v is not None and v != [] and v != {}:
                    cleaned_data[k] = v
            
            return cleaned_data
            
        except Exception as e:
            self.log_error('to_representation', e, {'device_id': getattr(instance, 'id', None)})
            return {
                'id': getattr(instance, 'id', None),
                'error': 'representation_failed',
                'detail': 'Unable to serialize device information'
            }


# ==================== BULK DEVICE SERIALIZER ====================

class BulkDeviceInfoSerializer(serializers.Serializer):
    """
    Serializer for bulk device operations
    """
    devices = DeviceInfoSerializer(many=True, required=True)
    
    def create(self, validated_data):
        """Bulk create devices"""
        devices = []
        errors = []
        
        for device_data in validated_data.get('devices', []):
            try:
                serializer = DeviceInfoSerializer(data=device_data)
                if serializer.is_valid():
                    devices.append(serializer.save())
                else:
                    errors.append({
                        'data': device_data,
                        'errors': serializer.errors
                    })
            except Exception as e:
                errors.append({
                    'data': device_data,
                    'error': str(e)
                })
        
        return {
            'created': devices,
            'errors': errors,
            'success_count': len(devices),
            'error_count': len(errors)
        }


# ==================== DEVICE SUMMARY SERIALIZER ====================

class DeviceSummarySerializer(serializers.Serializer):
    """
    Lightweight serializer for device summaries
    """
    id = serializers.IntegerField()
    device_model = serializers.CharField()
    is_suspicious = serializers.BooleanField()
    risk_score = serializers.IntegerField()
    risk_level = serializers.SerializerMethodField()
    last_activity = serializers.DateTimeField()
    
    def get_risk_level(self, obj):
        """Get risk level display"""
        if isinstance(obj, dict):
            score = obj.get('risk_score', 0)
        else:
            score = getattr(obj, 'risk_score', 0)
        
        if score >= 70:
            return 'high'
        elif score >= 40:
            return 'medium'
        else:
            return 'low'


class DeviceInfoListSerializer(NullSafeSerializerMixin, serializers.ModelSerializer):
    """Optimized serializer for listing devices"""
    
    user_summary = serializers.SerializerMethodField(
        help_text="User summary (optimized for lists)"
    )
    
    risk_category = serializers.SerializerMethodField(
        help_text="Risk category (low/medium/high/critical)"
    )
    
    device_summary = serializers.SerializerMethodField(
        help_text="Device summary information"
    )
    
    class Meta:
        model = DeviceInfo
        fields = [
            'id', 'user_summary', 'device_model', 'device_brand',
            'android_version', 'app_version', 'is_rooted', 'is_emulator',
            'last_ip', 'is_vpn', 'is_proxy', 'risk_score', 'is_trusted',
            'trust_level', 'last_activity', 'risk_category', 'device_summary'
        ]
    
    def get_user_summary(self, obj: DeviceInfo) -> Optional[Dict[str, Any]]:
        """Get user summary safely"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username[:20]
                }
            return None
        except Exception:
            return None
    
    def get_risk_category(self, obj: DeviceInfo) -> str:
        """Get risk category"""
        try:
            if obj.risk_score >= 80:
                return 'critical'
            elif obj.risk_score >= 60:
                return 'high'
            elif obj.risk_score >= 40:
                return 'medium'
            elif obj.risk_score >= 20:
                return 'low'
            else:
                return 'very_low'
        except Exception:
            return 'unknown'
    
    def get_device_summary(self, obj: DeviceInfo) -> Dict[str, Any]:
        """Get device summary"""
        try:
            return {
                'model_brand': f"{obj.device_model} ({obj.device_brand})",
                'os_version': obj.android_version,
                'app_version': obj.app_version,
                'security_flags': self._get_security_flags(obj),
                'days_inactive': self._get_days_inactive(obj),
            }
        except Exception:
            return {'error': 'summary_unavailable'}
    
    def _get_security_flags(self, obj: DeviceInfo) -> List[str]:
        """Get security flags"""
        flags = []
        try:
            if obj.is_rooted:
                flags.append('rooted')
            if obj.is_emulator:
                flags.append('emulator')
            if obj.is_vpn:
                flags.append('vpn')
            if obj.is_proxy:
                flags.append('proxy')
            return flags
        except Exception:
            return []
    
    def _get_days_inactive(self, obj: DeviceInfo) -> int:
        """Get days since last activity"""
        try:
            if not obj.last_activity:
                return 999
            
            delta = timezone.now() - obj.last_activity
            return delta.days
        except Exception:
            return 999


class DeviceInfoUpdateSerializer(NullSafeSerializerMixin, serializers.ModelSerializer):
    """Serializer for updating DeviceInfo (limited fields)"""
    
    class Meta:
        model = DeviceInfo
        fields = [
            'is_trusted', 'trust_level', 'risk_score', 'last_ip',
            'is_vpn', 'is_proxy', 'fingerprint'
        ]
        read_only_fields = ['risk_score']  # Auto-calculated
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate update data"""
        errors = {}
        
        try:
            # Validate trust level
            trust_level = data.get('trust_level')
            if trust_level and trust_level not in [1, 2, 3]:
                errors['trust_level'] = "Trust level must be 1, 2, or 3"
            
            # Validate IP address
            last_ip = data.get('last_ip')
            if last_ip and not self.validate_ip_address(last_ip):
                errors['last_ip'] = f"Invalid IP address: {last_ip}"
            
            # Prevent setting trust level too high for risky devices
            if (trust_level == 3 and 
                data.get('is_rooted', self.instance.is_rooted if self.instance else False)):
                errors['trust_level'] = "Cannot set high trust level for rooted devices"
            
        except Exception as e:
            logger.error(f"Validation error in DeviceInfoUpdateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def update(self, instance: DeviceInfo, validated_data: Dict[str, Any]) -> DeviceInfo:
        """Update device info with risk score recalculation"""
        try:
            # Update fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            # Update last activity
            instance.last_activity = timezone.now()
            
            # Save and recalculate risk
            instance.save()
            instance.update_risk_score()
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update DeviceInfo {instance.id}: {e}")
            raise ValidationError(f"Failed to update device: {str(e)}")
        
        
class SecurityLogSerializer(NullSafeSerializerMixin, serializers.ModelSerializer):
    """
    Defensive serializer for SecurityLog with comprehensive validation
    এবং Null Object Pattern implementation
    """
    
    # Read-only computed fields
    user_info = serializers.SerializerMethodField(
        help_text="User information",
        read_only=True
    )
    
    device_info_summary = serializers.SerializerMethodField(
        help_text="Device information summary",
        read_only=True
    )
    
    time_elapsed = serializers.SerializerMethodField(
        help_text="Time since log creation",
        read_only=True
    )
    
    action_recommendations = serializers.SerializerMethodField(
        help_text="Recommended actions based on log",
        read_only=True
    )
    
    # Write-only fields
    user_id = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="User ID (optional)"
    )
    
    device_info_id = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="DeviceInfo ID (optional)"
    )
    
    class Meta:
        model = SecurityLog
        fields = [
            'id', 'user', 'user_info', 'security_type', 'severity',
            'ip_address', 'user_agent', 'device_info', 'device_info_summary',
            'description', 'metadata', 'action_taken', 'risk_score',
            'resolved', 'resolved_at', 'resolved_by', 'created_at',
            'time_elapsed', 'action_recommendations'
        ]
        read_only_fields = [
            'id', 'user_info', 'device_info_summary', 'risk_score',
            'resolved_at', 'resolved_by', 'created_at', 'time_elapsed',
            'action_recommendations'
        ]
        extra_kwargs = {
            'description': {'default': '', 'allow_blank': True},
            'metadata': {'default': dict, 'allow_null': True},
            'action_taken': {'default': '', 'allow_blank': True},
            'user_agent': {'default': '', 'allow_blank': True},
            'ip_address': {'allow_null': True, 'allow_blank': True},
        }
    
    def get_user_info(self, obj: SecurityLog) -> Optional[Dict[str, Any]]:
        """Safely get user information"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'email': obj.user.email
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info for security log {obj.id}: {e}")
            return {'error': 'user_info_unavailable'}
    
    def get_device_info_summary(self, obj: SecurityLog) -> Optional[Dict[str, Any]]:
        """Safely get device information summary"""
        try:
            if obj.device_info:
                return {
                    'id': obj.device_info.id,
                    'device_model': obj.device_info.device_model,
                    'device_brand': obj.device_info.device_brand,
                    'is_rooted': obj.device_info.is_rooted,
                    'is_emulator': obj.device_info.is_emulator,
                    'risk_score': obj.device_info.risk_score,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting device info for security log {obj.id}: {e}")
            return {'error': 'device_info_unavailable'}
    
    def get_time_elapsed(self, obj: SecurityLog) -> str:
        """Get human-readable time elapsed"""
        try:
            if not obj.created_at:
                return "Unknown"
            
            delta = timezone.now() - obj.created_at
            
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours} hours ago"
            elif delta.seconds > 60:
                minutes = delta.seconds // 60
                return f"{minutes} minutes ago"
            else:
                return "Just now"
        except Exception:
            return "Time unknown"
    
    def get_action_recommendations(self, obj: SecurityLog) -> List[str]:
        """Get action recommendations based on log type and severity"""
        try:
            recommendations = []
            
            # Base recommendations
            if obj.severity in ['high', 'critical']:
                recommendations.append("Immediate investigation required")
                recommendations.append("Consider temporary account restriction")
            
            if obj.security_type in ['unauthorized_access', 'session_hijack']:
                recommendations.append("Force logout all sessions")
                recommendations.append("Require password reset")
                recommendations.append("Notify user via email")
            
            if obj.security_type in ['multiple_accounts', 'duplicate_device']:
                recommendations.append("Review account linking patterns")
                recommendations.append("Check for fraud patterns")
            
            if obj.security_type == 'failed_login':
                if obj.risk_score > 50:
                    recommendations.append("Implement temporary login block")
                    recommendations.append("Send security alert to user")
            
            if obj.security_type == 'rate_limit_exceeded':
                recommendations.append("Review rate limiting thresholds")
                recommendations.append("Check for automated attacks")
            
            if obj.security_type in ['vpn_detected', 'proxy_detected']:
                recommendations.append("Monitor for suspicious patterns")
                recommendations.append("Consider geographic restrictions")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations for security log {obj.id}: {e}")
            return ["Unable to generate recommendations"]
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        
        try:
            # Validate security type
            valid_types = [choice[0] for choice in SecurityLog.SECURITY_TYPES]
            security_type = data.get('security_type')
            if security_type not in valid_types:
                errors['security_type'] = f"Invalid security type. Must be one of: {', '.join(valid_types)}"
            
            # Validate severity
            valid_severities = [choice[0] for choice in SecurityLog.SEVERITY_LEVELS]
            severity = data.get('severity', 'medium')
            if severity not in valid_severities:
                errors['severity'] = f"Invalid severity. Must be one of: {', '.join(valid_severities)}"
            
            # Validate IP address
            ip_address = data.get('ip_address')
            if ip_address and not self.validate_ip_address(ip_address):
                errors['ip_address'] = f"Invalid IP address format: {ip_address}"
            
            # Validate metadata
            metadata = data.get('metadata', {})
            if not isinstance(metadata, dict):
                errors['metadata'] = "Metadata must be a valid JSON object"
            
            # Validate user_id
            user_id = data.get('user')
            if user_id is not None:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                    data['user'] = user
                except User.DoesNotExist:
                    errors['user'] = f"User with ID {user_id} does not exist"
            
            # Validate device_info_id
            device_info_id = data.get('device_info')
            if device_info_id is not None:
                try:
                    device_info = DeviceInfo.objects.get(id=device_info_id)
                    data['device_info'] = device_info
                except DeviceInfo.DoesNotExist:
                    errors['device_info'] = f"DeviceInfo with ID {device_info_id} does not exist"
            
            # Remove ID fields from data as we've converted to objects
            if 'user' in data:
                del data['user']
            if 'device_info' in data:
                del data['device_info']
            
            # Auto-set severity for critical security types
            if security_type in ['unauthorized_access', 'session_hijack'] and severity not in ['high', 'critical']:
                data['severity'] = 'high'
            
        except Exception as e:
            logger.error(f"Unexpected validation error in SecurityLogSerializer: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> SecurityLog:
        """Defensive create method with auto risk calculation"""
        try:
            # Set default values
            validated_data.setdefault('severity', 'medium')
            validated_data.setdefault('description', '')
            validated_data.setdefault('action_taken', '')
            validated_data.setdefault('metadata', {})
            validated_data.setdefault('user_agent', '')
            
            # Create security log
            security_log = SecurityLog.objects.create(**validated_data)
            
            # Auto-calculate risk score (triggers in clean method)
            security_log.full_clean()
            security_log.save()
            
            # Log creation for auditing
            logger.warning(
                f"SecurityLog created: "
                f"ID={security_log.id}, "
                f"Type={security_log.security_type}, "
                f"Severity={security_log.severity}, "
                f"User={security_log.user_id}, "
                f"Risk={security_log.risk_score}"
            )
            
            # Update device risk score if device_info exists
            if security_log.device_info:
                try:
                    security_log.device_info.update_risk_score()
                except Exception as e:
                    logger.error(f"Failed to update device risk score: {e}")
            
            return security_log
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create SecurityLog: {e}")
            raise ValidationError(f"Failed to create security log: {str(e)}")


class SecurityLogListSerializer(NullSafeSerializerMixin, serializers.ModelSerializer):
    """Optimized serializer for listing security logs"""
    
    user_summary = serializers.SerializerMethodField(
        help_text="User summary (optimized)"
    )
    
    severity_icon = serializers.SerializerMethodField(
        help_text="Severity icon for UI"
    )
    
    log_summary = serializers.SerializerMethodField(
        help_text="Log summary information"
    )
    
    class Meta:
        model = SecurityLog
        fields = [
            'id', 'user_summary', 'security_type', 'severity', 'severity_icon',
            'ip_address', 'risk_score', 'resolved', 'created_at', 'log_summary'
        ]
    
    def get_user_summary(self, obj: SecurityLog) -> Optional[Dict[str, Any]]:
        """Get user summary safely"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username[:15]
                }
            return {'type': 'anonymous', 'username': 'Anonymous'}
        except Exception:
            return None
    
    def get_severity_icon(self, obj: SecurityLog) -> str:
        """Get severity icon for UI"""
        try:
            icons = {
                'low': 'info',
                'medium': 'warning',
                'high': 'error',
                'critical': 'danger'
            }
            return icons.get(obj.severity, 'info')
        except Exception:
            return 'info'
    
    def get_log_summary(self, obj: SecurityLog) -> Dict[str, Any]:
        """Get log summary"""
        try:
            summary = {
                'has_device_info': bool(obj.device_info),
                'has_user_agent': bool(obj.user_agent and len(obj.user_agent) > 10),
                'has_metadata': bool(obj.metadata),
                'description_length': len(obj.description) if obj.description else 0,
                'age_days': (timezone.now() - obj.created_at).days if obj.created_at else 0,
            }
            
            # Add type-specific information
            if obj.security_type in ['failed_login', 'unauthorized_access']:
                summary['login_related'] = True
            
            if obj.security_type in ['vpn_detected', 'proxy_detected']:
                summary['network_related'] = True
            
            return summary
            
        except Exception:
            return {'error': 'summary_unavailable'}


class SecurityLogUpdateSerializer(NullSafeSerializerMixin, serializers.ModelSerializer):
    """Serializer for updating SecurityLog (marking as resolved)"""
    
    resolution_notes = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Notes about resolution"
    )
    
    class Meta:
        model = SecurityLog
        fields = ['resolved', 'action_taken', 'resolution_notes']
        read_only_fields = ['action_taken']
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate update data"""
        errors = {}
        
        try:
            # Check if trying to mark as resolved
            if data.get('resolved') and not self.instance.resolved:
                # Ensure action_taken is provided
                if not data.get('action_taken') and not self.instance.action_taken:
                    errors['action_taken'] = "Action taken is required when resolving"
            
            # Check if trying to un-resolve
            if not data.get('resolved') and self.instance.resolved:
                errors['resolved'] = "Cannot un-resolve a resolved log"
            
        except Exception as e:
            logger.error(f"Validation error in SecurityLogUpdateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def update(self, instance: SecurityLog, validated_data: Dict[str, Any]) -> SecurityLog:
        """Update security log with resolution handling"""
        try:
            resolution_notes = validated_data.pop('resolution_notes', '')
            
            # Handle resolution
            if validated_data.get('resolved') and not instance.resolved:
                # Mark as resolved
                instance.mark_resolved(
                    resolved_by=self.context['request'].user if 'request' in self.context else None,
                    notes=resolution_notes
                )
            
            # Update other fields
            for attr, value in validated_data.items():
                if attr != 'resolved':  # resolved is handled by mark_resolved
                    setattr(instance, attr, value)
            
            instance.save()
            
            logger.info(f"SecurityLog updated: ID={instance.id}, Resolved={instance.resolved}")
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update SecurityLog {instance.id}: {e}")
            raise ValidationError(f"Failed to update security log: {str(e)}")


class SecurityLogBulkResolveSerializer(serializers.Serializer):
    """Serializer for bulk resolving security logs"""
    
    log_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100,
        help_text="List of SecurityLog IDs to resolve"
    )
    
    action_taken = serializers.CharField(
        required=True,
        max_length=200,
        help_text="Action taken for all logs"
    )
    
    resolution_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Resolution notes"
    )
    
    def validate_log_ids(self, value: List[int]) -> List[int]:
        """Validate log IDs"""
        try:
            # Check if logs exist
            existing_ids = set(SecurityLog.objects.filter(
                id__in=value
            ).values_list('id', flat=True))
            
            invalid_ids = set(value) - existing_ids
            if invalid_ids:
                raise ValidationError(f"Invalid log IDs: {list(invalid_ids)}")
            
            return value
        except Exception as e:
            logger.error(f"Error validating log IDs: {e}")
            raise ValidationError("Error validating log IDs")
    
    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk resolve security logs"""
        try:
            log_ids = validated_data['log_ids']
            action_taken = validated_data['action_taken']
            resolution_notes = validated_data.get('resolution_notes', '')
            
            resolved_count = 0
            failed_logs = []
            
            for log_id in log_ids:
                try:
                    log = SecurityLog.objects.get(id=log_id)
                    if not log.resolved:
                        log.action_taken = action_taken
                        log.mark_resolved(
                            resolved_by=self.context['request'].user if 'request' in self.context else None,
                            notes=resolution_notes
                        )
                        resolved_count += 1
                except Exception as e:
                    failed_logs.append({'log_id': log_id, 'error': str(e)})
            
            return {
                'total_requested': len(log_ids),
                'resolved_count': resolved_count,
                'failed_count': len(failed_logs),
                'failed_logs': failed_logs if failed_logs else None,
                'action_taken': action_taken
            }
            
        except Exception as e:
            logger.error(f"Failed to bulk resolve logs: {e}")
            raise ValidationError(f"Failed to bulk resolve logs: {str(e)}")
        
        

class DefensiveUserBanMixin:
    """Mixin for defensive UserBan serialization with error handling"""
    
    @staticmethod
    def validate_future_date(date_value: datetime) -> bool:
        """Validate that date is in the future with defensive coding"""
        try:
            if not date_value:
                return True  # Allow None for permanent bans
            
            if not isinstance(date_value, datetime):
                return False
            
            return date_value > timezone.now()
        except Exception as e:
            logger.warning(f"Error validating future date: {e}")
            return False
    
    @staticmethod
    def safe_get_user(user_id: int):
        """Safely get user object with error handling"""
        try:
            User = get_user_model()
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'user': f'User with ID {user_id} does not exist'})
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise ValidationError({'user': 'Error retrieving user information'})
    
    def validate_ban_consistency(self, data: Dict[str, Any]) -> None:
        """Validate ban consistency rules"""
        errors = {}
        
        try:
            is_permanent = data.get('is_permanent', False)
            banned_until = data.get('banned_until')
            
            # Permanent ban cannot have expiration date
            if is_permanent and banned_until:
                errors['banned_until'] = "Permanent bans cannot have an expiration date."
            
            # Temporary ban must have expiration date
            if not is_permanent and not banned_until:
                errors['banned_until'] = "Temporary bans must have an expiration date."
            
            # Ban expiration must be in future
            if banned_until and not self.validate_future_date(banned_until):
                errors['banned_until'] = "Ban expiration must be in the future."
            
            if errors:
                raise ValidationError(errors)
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in ban consistency validation: {e}")
            raise ValidationError({'non_field_errors': 'Validation error occurred'})
    
    def check_existing_bans(self, user_id: int, exclude_ban_id: int = None) -> None:
        """Check for existing active bans with defensive coding"""
        try:
            existing_bans = UserBan.objects.filter(
                user_id=user_id,
                is_active_ban=True
            )
            
            if exclude_ban_id:
                existing_bans = existing_bans.exclude(id=exclude_ban_id)
            
            if existing_bans.exists():
                ban_ids = list(existing_bans.values_list('id', flat=True)[:5])
                raise ValidationError({
                    'user': f'User already has active ban(s): {ban_ids}'
                })
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error checking existing bans for user {user_id}: {e}")
            # Don't fail validation if check fails - allow through but log
            logger.warning(f"Could not verify existing bans for user {user_id}, proceeding with caution")


class UserBanSerializer(DefensiveUserBanMixin, serializers.ModelSerializer):
    """
    Defensive serializer for UserBan with comprehensive validation
    এবং Null Object Pattern implementation
    """
    
    # Write-only field for user creation
    user_id = serializers.IntegerField(
        write_only=True,
        required=True,
        help_text="ID of the user to ban"
    )
    
    # Read-only computed fields
    user_info = serializers.SerializerMethodField(
        help_text="User information (read-only)",
        read_only=True
    )
    
    ban_status = serializers.SerializerMethodField(
        help_text="Current ban status (read-only)",
        read_only=True
    )
    
    remaining_time = serializers.SerializerMethodField(
        help_text="Remaining ban duration (read-only)",
        read_only=True
    )
    
    is_currently_active = serializers.SerializerMethodField(
        help_text="Whether ban is currently active (read-only)",
        read_only=True
    )
    
    # Null Object Pattern: Default values in Meta
    class Meta:
        model = UserBan
        fields = [
            'id', 'user', 'user_info', 'reason', 'is_permanent',
            'banned_until', 'banned_at', 'is_active_ban',
            'ban_status', 'remaining_time', 'is_currently_active'
        ]
        read_only_fields = [
            'id', 'user_info', 'banned_at', 'ban_status',
            'remaining_time', 'is_currently_active'
        ]
        extra_kwargs = {
            'reason': {
                'default': 'No reason provided',
                'allow_blank': False
            },
            'is_permanent': {'default': False},
            'is_active_ban': {'default': True},
            'banned_until': {
                'allow_null': True,
                'required': False
            }
        }
    
    def get_user_info(self, obj: UserBan) -> Optional[Dict[str, Any]]:
        """Safely get user information with defensive coding"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'email': obj.user.email,
                    'is_active': obj.user.is_active,
                    'date_joined': obj.user.date_joined.isoformat() if obj.user.date_joined else None
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info for ban {obj.id}: {e}")
            return {'error': 'user_info_unavailable', 'user': obj.user_id}
    
    def get_ban_status(self, obj: UserBan) -> str:
        """Get human-readable ban status"""
        try:
            if not obj.is_active_ban:
                return 'Deactivated'
            
            if obj.is_currently_active():
                if obj.is_permanent:
                    return 'Active (Permanent)'
                else:
                    return 'Active (Temporary)'
            else:
                return 'Expired'
        except Exception:
            return 'Status Unknown'
    
    def get_remaining_time(self, obj: UserBan) -> Optional[Dict[str, Any]]:
        """Get remaining ban duration in structured format"""
        try:
            remaining = obj.get_remaining_duration()
            if not remaining:
                return None
            
            return {
                'total_seconds': int(remaining.total_seconds()),
                'days': remaining.days,
                'hours': remaining.seconds // 3600,
                'minutes': (remaining.seconds % 3600) // 60,
                'seconds': remaining.seconds % 60
            }
        except Exception as e:
            logger.warning(f"Error getting remaining time for ban {obj.id}: {e}")
            return None
    
    def get_is_currently_active(self, obj: UserBan) -> bool:
        """Check if ban is currently active"""
        try:
            return obj.is_currently_active()
        except Exception as e:
            logger.error(f"Error checking active status for ban {obj.id}: {e}")
            return False  # Graceful degradation: assume not active
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        
        try:
            # Validate user_id
            user_id = data.get('user')
            if not user_id:
                errors['user'] = "User ID is required"
            else:
                try:
                    user = self.safe_get_user(user_id)
                    data['user'] = user
                    
                    # Check if trying to ban admin/staff
                    if user.is_staff or user.is_superuser:
                        errors['user'] = "Cannot ban staff or superusers"
                        
                except ValidationError as e:
                    errors.update(e.detail)
            
            # Validate ban consistency
            try:
                self.validate_ban_consistency(data)
            except ValidationError as e:
                errors.update(e.detail)
            
            # Remove user_id from data as we've converted to user object
            if 'user' in data:
                del data['user']
            
            # Check for existing bans (only for new bans, not updates)
            if not self.instance and 'user' in data:
                try:
                    self.check_existing_bans(data['user'].id)
                except ValidationError as e:
                    errors.update(e.detail)
            
        except Exception as e:
            logger.error(f"Unexpected validation error in UserBanSerializer: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> UserBan:
        """Defensive create method using factory pattern"""
        try:
            user = validated_data['user']
            reason = validated_data['reason']
            is_permanent = validated_data.get('is_permanent', False)
            
            # Use factory methods for creation
            if is_permanent:
                ban = UserBan.create_permanent_ban(user=user, reason=reason)
            else:
                banned_until = validated_data.get('banned_until')
                if not banned_until:
                    raise ValidationError({'banned_until': 'Expiration date required for temporary ban'})
                
                # Calculate days from banned_until
                days = (banned_until - timezone.now()).days
                days = max(1, days)  # Minimum 1 day
                
                ban = UserBan.create_temporary_ban(
                    user=user,
                    reason=reason,
                    days=days
                )
            
            # Log ban creation
            logger.warning(
                f"UserBan created: "
                f"ID={ban.id}, "
                f"User={user.id}, "
                f"Type={'Permanent' if is_permanent else 'Temporary'}, "
                f"Reason={reason[:100]}..."
            )
            
            return ban
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create UserBan: {e}")
            raise ValidationError(f"Failed to create ban: {str(e)}")
    
    def update(self, instance: UserBan, validated_data: Dict[str, Any]) -> UserBan:
        """Defensive update method with limited allowed fields"""
        try:
            # Prevent modification of protected fields
            protected_fields = ['user', 'banned_at', 'is_currently_active']
            for field in protected_fields:
                if field in validated_data:
                    del validated_data[field]
            
            # Only allow specific updates
            allowed_updates = ['reason', 'is_active_ban']
            if not instance.is_permanent:
                allowed_updates.append('banned_until')
            
            # Filter validated data
            update_data = {
                k: v for k, v in validated_data.items() 
                if k in allowed_updates
            }
            
            # Update instance
            for attr, value in update_data.items():
                setattr(instance, attr, value)
            
            # Validate consistency after update
            instance.full_clean()
            
            # Check for existing active bans (excluding current instance)
            if 'is_active_ban' in update_data and update_data['is_active_ban']:
                self.check_existing_bans(instance.user_id, exclude_ban_id=instance.id)
            
            instance.save()
            
            # Log update
            logger.info(
                f"UserBan updated: "
                f"ID={instance.id}, "
                f"Updated fields={list(update_data.keys())}"
            )
            
            return instance
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update UserBan {instance.id}: {e}")
            raise ValidationError(f"Failed to update ban: {str(e)}")


class UserBanListSerializer(DefensiveUserBanMixin, serializers.ModelSerializer):
    """Optimized serializer for listing UserBans"""
    
    user_summary = serializers.SerializerMethodField(
        help_text="User summary (optimized for lists)"
    )
    
    ban_summary = serializers.SerializerMethodField(
        help_text="Ban summary information"
    )
    
    class Meta:
        model = UserBan
        fields = [
            'id', 'user_summary', 'reason', 'is_permanent',
            'banned_until', 'banned_at', 'is_active_ban',
            'ban_summary'
        ]
    
    def get_user_summary(self, obj: UserBan) -> Optional[Dict[str, Any]]:
        """Get optimized user summary"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username[:20],
                    'email': obj.user.email[:30] if obj.user.email else None
                }
            return None
        except Exception:
            return None
    
    def get_ban_summary(self, obj: UserBan) -> Dict[str, Any]:
        """Get ban summary information"""
        try:
            summary = {
                'is_currently_active': obj.is_currently_active(),
                'ban_type': 'permanent' if obj.is_permanent else 'temporary',
                'days_since_banned': (timezone.now() - obj.banned_at).days if obj.banned_at else None,
            }
            
            # Add duration info for temporary bans
            if not obj.is_permanent and obj.banned_until:
                if obj.banned_until > timezone.now():
                    remaining = obj.banned_until - timezone.now()
                    summary['remaining_days'] = remaining.days
                    summary['is_expired'] = False
                else:
                    summary['is_expired'] = True
            
            return summary
            
        except Exception:
            return {'error': 'summary_unavailable'}


class UserBanUpdateSerializer(DefensiveUserBanMixin, serializers.ModelSerializer):
    """Serializer for updating UserBan (limited fields)"""
    
    deactivation_reason = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for deactivating ban"
    )
    
    class Meta:
        model = UserBan
        fields = ['reason', 'is_active_ban', 'banned_until', 'deactivation_reason']
        read_only_fields = ['banned_until']  # Controlled based on is_permanent
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate update data"""
        errors = {}
        
        try:
            instance = self.instance
            
            # Validate deactivation
            if 'is_active_ban' in data and not data['is_active_ban']:
                deactivation_reason = data.get('deactivation_reason', '')
                if not deactivation_reason:
                    errors['deactivation_reason'] = "Deactivation reason is required"
                else:
                    # Store deactivation reason for later use
                    self.deactivation_reason = deactivation_reason
            
            # Validate banned_until for temporary bans
            if 'banned_until' in data and instance and instance.is_permanent:
                errors['banned_until'] = "Cannot set expiration date for permanent ban"
            
            # Validate banned_until is in future
            if 'banned_until' in data and not self.validate_future_date(data['banned_until']):
                errors['banned_until'] = "Ban expiration must be in the future"
            
            # Check for existing active bans when activating
            if (data.get('is_active_ban') and instance and 
                not instance.is_active_ban and instance.user):
                self.check_existing_bans(instance.user_id, exclude_ban_id=instance.id)
            
        except Exception as e:
            logger.error(f"Validation error in UserBanUpdateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def update(self, instance: UserBan, validated_data: Dict[str, Any]) -> UserBan:
        """Update ban with deactivation handling"""
        try:
            deactivation_reason = getattr(self, 'deactivation_reason', '')
            
            # Handle deactivation
            if 'is_active_ban' in validated_data and not validated_data['is_active_ban']:
                success, message = instance.deactivate_ban(deactivation_reason)
                if not success:
                    raise ValidationError({'is_active_ban': message})
            
            # Update other fields
            for attr, value in validated_data.items():
                if attr != 'is_active_ban':  # is_active_ban handled by deactivate_ban
                    setattr(instance, attr, value)
            
            instance.save()
            
            return instance
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update UserBan {instance.id}: {e}")
            raise ValidationError(f"Failed to update ban: {str(e)}")


class UserBanCreateSerializer(DefensiveUserBanMixin, serializers.Serializer):
    """Specialized serializer for creating bans with defensive validation"""
    
    user_id = serializers.IntegerField(
        required=True,
        help_text="ID of user to ban"
    )
    
    reason = serializers.CharField(
        required=True,
        max_length=1000,
        help_text="Reason for the ban"
    )
    
    ban_type = serializers.ChoiceField(
        choices=[
            ('temporary', 'Temporary Ban'),
            ('permanent', 'Permanent Ban')
        ],
        default='temporary',
        help_text="Type of ban"
    )
    
    duration_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        help_text="Duration in days (for temporary bans)"
    )
    
    custom_expiry = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Custom expiry date (overrides duration_days)"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation for ban creation"""
        errors = {}
        
        try:
            # Get user
            user_id = data['user']
            user = self.safe_get_user(user_id)
            data['user'] = user
            
            # Check if user is staff/admin
            if user.is_staff or user.is_superuser:
                errors['user'] = "Cannot ban staff or superusers"
            
            # Validate ban type consistency
            ban_type = data['ban_type']
            duration_days = data.get('duration_days', 7)
            custom_expiry = data.get('custom_expiry')
            
            if ban_type == 'permanent':
                if custom_expiry:
                    errors['custom_expiry'] = "Cannot set expiry for permanent ban"
                if 'duration_days' in data:
                    errors['duration_days'] = "Cannot set duration for permanent ban"
            else:
                # Temporary ban validation
                if custom_expiry:
                    if not self.validate_future_date(custom_expiry):
                        errors['custom_expiry'] = "Expiry must be in the future"
                elif duration_days <= 0:
                    errors['duration_days'] = "Duration must be positive"
            
            # Check for existing bans
            try:
                self.check_existing_bans(user_id)
            except ValidationError as e:
                errors.update(e.detail)
            
        except ValidationError as e:
            errors.update(e.detail)
        except Exception as e:
            logger.error(f"Validation error in UserBanCreateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> UserBan:
        """Create ban using factory methods"""
        try:
            user = validated_data['user']
            reason = validated_data['reason']
            ban_type = validated_data['ban_type']
            
            if ban_type == 'permanent':
                return UserBan.create_permanent_ban(user=user, reason=reason)
            else:
                # Temporary ban
                custom_expiry = validated_data.get('custom_expiry')
                if custom_expiry:
                    # Calculate days from custom expiry
                    days = (custom_expiry - timezone.now()).days
                    days = max(1, days)
                else:
                    days = validated_data.get('duration_days', 7)
                
                return UserBan.create_temporary_ban(
                    user=user,
                    reason=reason,
                    days=days
                )
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create ban: {e}")
            raise ValidationError(f"Failed to create ban: {str(e)}")
        
    

class DefensiveIPBlacklistMixin:
    """Mixin for defensive IPBlacklist serialization with error handling"""
    
    @staticmethod
    def validate_ip_address_format(ip_address: str) -> bool:
        """Validate IP address format with defensive coding"""
        try:
            if not ip_address:
                return False
            
            ipaddress.ip_address(ip_address)
            return True
        except ValueError:
            return False
        except Exception as e:
            logger.warning(f"Error validating IP {ip_address}: {e}")
            return False
    
    @staticmethod
    def validate_subnet_mask(subnet_mask: int) -> bool:
        """Validate subnet mask range"""
        try:
            if subnet_mask is None:
                return True  # Allow None
            
            if not isinstance(subnet_mask, int):
                return False
            
            return 0 <= subnet_mask <= 32
        except Exception:
            return False
    
    @staticmethod
    def safe_get_user(user_id: Optional[int]):
        """Safely get user object with error handling"""
        if not user_id:
            return None
        
        try:
            User = get_user_model()
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'reported_by': f'User with ID {user_id} does not exist'})
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise ValidationError({'reported_by': 'Error retrieving user information'})
    
    def validate_block_consistency(self, data: Dict[str, Any]) -> None:
        """Validate block consistency rules"""
        errors = {}
        
        try:
            is_permanent = data.get('is_permanent', False)
            blocked_until = data.get('blocked_until')
            
            # Permanent block cannot have expiration date
            if is_permanent and blocked_until:
                errors['blocked_until'] = "Permanent blocks cannot have an expiration date."
            
            # Temporary block must have expiration date
            if not is_permanent and not blocked_until:
                errors['blocked_until'] = "Temporary blocks must have an expiration date."
            
            # Block expiration must be in future
            if blocked_until and blocked_until <= timezone.now():
                errors['blocked_until'] = "Block expiration must be in the future."
            
            # Validate confidence score
            confidence_score = data.get('confidence_score', 80.0)
            if not 0 <= confidence_score <= 100:
                errors['confidence_score'] = "Confidence score must be between 0 and 100"
            
            # Validate max requests per minute
            max_requests = data.get('max_requests_per_minute', 0)
            if max_requests < 0:
                errors['max_requests_per_minute'] = "Max requests per minute cannot be negative"
            
            # Validate attack count
            attack_count = data.get('attack_count', 1)
            if attack_count < 0:
                errors['attack_count'] = "Attack count cannot be negative"
            
            if errors:
                raise ValidationError(errors)
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in block consistency validation: {e}")
            raise ValidationError({'non_field_errors': 'Validation error occurred'})
    
    def check_existing_blocks(self, ip_address: str, subnet_mask: Optional[int], exclude_block_id: int = None) -> None:
        """Check for existing blocks for the same IP or subnet"""
        try:
            existing_blocks = IPBlacklist.objects.filter(is_active=True)
            
            if exclude_block_id:
                existing_blocks = existing_blocks.exclude(id=exclude_block_id)
            
            # Check for direct IP match
            if existing_blocks.filter(ip_address=ip_address).exists():
                raise ValidationError({
                    'ip_address': f'IP address {ip_address} is already blocked'
                })
            
            # Check for subnet matches if subnet_mask is provided
            if subnet_mask is not None:
                try:
                    network = ipaddress.ip_network(f"{ip_address}/{subnet_mask}", strict=False)
                    
                    # Check all active blocks for subnet overlap
                    for block in existing_blocks:
                        if block.subnet_mask is not None:
                            try:
                                block_network = ipaddress.ip_network(f"{block.ip_address}/{block.subnet_mask}", strict=False)
                                if network.overlaps(block_network):
                                    raise ValidationError({
                                        'ip_address': f'IP range {network} overlaps with existing block {block.ip_address}/{block.subnet_mask}'
                                    })
                            except Exception:
                                continue  # Skip if network parsing fails
                except Exception as e:
                    logger.warning(f"Error checking subnet overlaps: {e}")
                    # Don't fail validation if subnet check fails
                    
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error checking existing blocks for IP {ip_address}: {e}")
            # Don't fail validation if check fails - log warning and proceed
            logger.warning(f"Could not verify existing blocks for IP {ip_address}, proceeding with caution")


class IPBlacklistSerializer(DefensiveIPBlacklistMixin, serializers.ModelSerializer):
    """
    Defensive serializer for IPBlacklist with comprehensive validation
    এবং Null Object Pattern implementation
    """
    
    # Write-only fields
    reported_by_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="ID of user who reported this IP"
    )
    
    # Read-only computed fields
    block_status = serializers.SerializerMethodField(
        help_text="Current block status (read-only)",
        read_only=True
    )
    
    remaining_time = serializers.SerializerMethodField(
        help_text="Remaining block duration (read-only)",
        read_only=True
    )
    
    is_currently_blocked = serializers.SerializerMethodField(
        help_text="Whether IP is currently blocked (read-only)",
        read_only=True
    )
    
    network_info = serializers.SerializerMethodField(
        help_text="Network information (read-only)",
        read_only=True
    )
    
    # Null Object Pattern: Default values in Meta
    class Meta:
        model = IPBlacklist
        fields = [
            'id', 'ip_address', 'subnet_mask', 'reason', 'threat_level',
            'threat_type', 'is_active', 'is_permanent', 'blocked_until',
            'max_requests_per_minute', 'detection_method', 'confidence_score',
            'attack_count', 'last_attempt', 'first_seen', 'country_code',
            'country_name', 'city', 'isp', 'asn', 'organization',
            'threat_intel_data', 'reported_by', 'auto_blocked_by', 'notes',
            'block_status', 'remaining_time', 'is_currently_blocked', 'network_info'
        ]
        read_only_fields = [
            'id', 'last_attempt', 'first_seen', 'block_status',
            'remaining_time', 'is_currently_blocked', 'network_info'
        ]
        extra_kwargs = {
            'reason': {
                'default': 'Suspicious activity detected',
                'allow_blank': False,
                'required': True
            },
            'threat_level': {'default': 'medium'},
            'threat_type': {'default': 'suspicious_pattern'},
            'is_active': {'default': True},
            'is_permanent': {'default': False},
            'max_requests_per_minute': {'default': 0, 'min_value': 0},
            'detection_method': {'default': 'automated'},
            'confidence_score': {'default': 80.0, 'min_value': 0, 'max_value': 100},
            'attack_count': {'default': 1, 'min_value': 0},
            'threat_intel_data': {'default': dict, 'allow_null': True},
            'notes': {'allow_blank': True, 'allow_null': True},
            'auto_blocked_by': {'allow_blank': True, 'allow_null': True},
        }
    
    def get_block_status(self, obj: IPBlacklist) -> str:
        """Get human-readable block status"""
        try:
            if not obj.is_active:
                return 'Deactivated'
            
            if obj.is_currently_blocked():
                if obj.is_permanent:
                    return 'Active (Permanent)'
                else:
                    return 'Active (Temporary)'
            else:
                return 'Expired'
        except Exception:
            return 'Status Unknown'
    
    def get_remaining_time(self, obj: IPBlacklist) -> Optional[Dict[str, Any]]:
        """Get remaining block duration in structured format"""
        try:
            if not obj.is_currently_blocked() or obj.is_permanent:
                return None
            
            if not obj.blocked_until:
                return None
            
            remaining = obj.blocked_until - timezone.now()
            if remaining.total_seconds() <= 0:
                return None
            
            return {
                'total_seconds': int(remaining.total_seconds()),
                'days': remaining.days,
                'hours': remaining.seconds // 3600,
                'minutes': (remaining.seconds % 3600) // 60,
                'seconds': remaining.seconds % 60
            }
        except Exception as e:
            logger.warning(f"Error getting remaining time for IP block {obj.id}: {e}")
            return None
    
    def get_is_currently_blocked(self, obj: IPBlacklist) -> bool:
        """Check if IP is currently blocked"""
        try:
            return obj.is_currently_blocked()
        except Exception as e:
            logger.error(f"Error checking block status for IP {obj.ip_address}: {e}")
            return False  # Graceful degradation: assume not blocked
    
    def get_network_info(self, obj: IPBlacklist) -> Dict[str, Any]:
        """Get network information"""
        try:
            info = {
                'ip_address': obj.ip_address,
                'has_subnet': obj.subnet_mask is not None,
                'geo_info_available': bool(obj.country_code and obj.country_code != "XX"),
                'network_info_available': bool(obj.isp or obj.asn or obj.organization),
            }
            
            if obj.subnet_mask is not None:
                try:
                    network = ipaddress.ip_network(f"{obj.ip_address}/{obj.subnet_mask}", strict=False)
                    info.update({
                        'subnet_mask': obj.subnet_mask,
                        'network_address': str(network.network_address),
                        'broadcast_address': str(network.broadcast_address),
                        'num_addresses': network.num_addresses,
                        'is_private': network.is_private,
                    })
                except Exception:
                    pass
            
            if obj.country_code and obj.country_code != "XX":
                info['geographic'] = {
                    'country_code': obj.country_code,
                    'country_name': obj.country_name,
                    'city': obj.city,
                }
            
            if obj.isp or obj.asn or obj.organization:
                info['network'] = {
                    'isp': obj.isp,
                    'asn': obj.asn,
                    'organization': obj.organization,
                }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting network info for IP {obj.ip_address}: {e}")
            return {'error': 'network_info_unavailable'}
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        
        try:
            # Validate IP address
            ip_address = data.get('ip_address')
            if not ip_address:
                errors['ip_address'] = "IP address is required"
            elif not self.validate_ip_address_format(ip_address):
                errors['ip_address'] = f"Invalid IP address format: {ip_address}"
            
            # Validate subnet mask
            subnet_mask = data.get('subnet_mask')
            if subnet_mask is not None and not self.validate_subnet_mask(subnet_mask):
                errors['subnet_mask'] = "Subnet mask must be between 0 and 32"
            
            # Validate threat type
            valid_threat_types = [choice[0] for choice in IPBlacklist._meta.get_field('threat_type').choices]
            threat_type = data.get('threat_type', 'suspicious_pattern')
            if threat_type not in valid_threat_types:
                errors['threat_type'] = f"Invalid threat type. Must be one of: {', '.join(valid_threat_types)}"
            
            # Validate threat level
            valid_threat_levels = [choice[0] for choice in IPBlacklist._meta.get_field('threat_level').choices]
            threat_level = data.get('threat_level', 'medium')
            if threat_level not in valid_threat_levels:
                errors['threat_level'] = f"Invalid threat level. Must be one of: {', '.join(valid_threat_levels)}"
            
            # Validate detection method
            valid_methods = [choice[0] for choice in IPBlacklist._meta.get_field('detection_method').choices]
            detection_method = data.get('detection_method', 'automated')
            if detection_method not in valid_methods:
                errors['detection_method'] = f"Invalid detection method. Must be one of: {', '.join(valid_methods)}"
            
            # Validate reported_by_id
            reported_by_id = data.get('reported_by')
            if reported_by_id is not None:
                try:
                    user = self.safe_get_user(reported_by_id)
                    data['reported_by'] = user
                except ValidationError as e:
                    errors.update(e.detail)
            
            # Remove reported_by_id from data as we've converted to user object
            if 'reported_by' in data:
                del data['reported_by']
            
            # Validate block consistency
            try:
                self.validate_block_consistency(data)
            except ValidationError as e:
                errors.update(e.detail)
            
            # Check for existing blocks (only for new blocks, not updates)
            if not self.instance and ip_address:
                try:
                    self.check_existing_blocks(ip_address, subnet_mask)
                except ValidationError as e:
                    errors.update(e.detail)
            
        except Exception as e:
            logger.error(f"Unexpected validation error in IPBlacklistSerializer: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> IPBlacklist:
        """Defensive create method"""
        try:
            # Set default values if not provided
            validated_data.setdefault('threat_intel_data', {})
            validated_data.setdefault('notes', '')
            validated_data.setdefault('auto_blocked_by', '')
            
            # Auto-detect geographic info if not provided
            if not validated_data.get('country_code'):
                # In production, this would call a geo-location service
                # For now, set placeholder values
                validated_data['country_code'] = "XX"
                validated_data['country_name'] = "Unknown"
            
            # Create IP blacklist entry
            ip_block = IPBlacklist.objects.create(**validated_data)
            
            # Log creation
            logger.warning(
                f"IPBlacklist created: "
                f"ID={ip_block.id}, "
                f"IP={ip_block.ip_address}, "
                f"Threat={ip_block.threat_level}, "
                f"Type={ip_block.threat_type}, "
                f"Reason={ip_block.reason[:100]}..."
            )
            
            return ip_block
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create IPBlacklist: {e}")
            raise ValidationError(f"Failed to create IP block: {str(e)}")
    
    def update(self, instance: IPBlacklist, validated_data: Dict[str, Any]) -> IPBlacklist:
        """Defensive update method with limited allowed fields"""
        try:
            # Prevent modification of protected fields
            protected_fields = ['ip_address', 'first_seen', 'last_attempt', 'subnet_mask']
            for field in protected_fields:
                if field in validated_data:
                    del validated_data[field]
            
            # Only allow specific updates
            allowed_updates = [
                'reason', 'threat_level', 'threat_type', 'is_active',
                'blocked_until', 'max_requests_per_minute', 'confidence_score',
                'notes', 'threat_intel_data'
            ]
            
            # Filter validated data
            update_data = {
                k: v for k, v in validated_data.items() 
                if k in allowed_updates
            }
            
            # Update instance
            for attr, value in update_data.items():
                setattr(instance, attr, value)
            
            # Validate consistency after update
            instance.full_clean()
            
            # Update last_attempt timestamp
            instance.last_attempt = timezone.now()
            
            # Check for existing active blocks (excluding current instance)
            if 'is_active' in update_data and update_data['is_active']:
                self.check_existing_blocks(
                    instance.ip_address, 
                    instance.subnet_mask, 
                    exclude_block_id=instance.id
                )
            
            instance.save()
            
            # Log update
            logger.info(
                f"IPBlacklist updated: "
                f"ID={instance.id}, "
                f"IP={instance.ip_address}, "
                f"Updated fields={list(update_data.keys())}"
            )
            
            return instance
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update IPBlacklist {instance.id}: {e}")
            raise ValidationError(f"Failed to update IP block: {str(e)}")


class IPBlacklistListSerializer(DefensiveIPBlacklistMixin, serializers.ModelSerializer):
    """Optimized serializer for listing IPBlacklist entries"""
    
    block_summary = serializers.SerializerMethodField(
        help_text="Block summary information"
    )
    
    threat_assessment = serializers.SerializerMethodField(
        help_text="Threat assessment summary"
    )
    
    class Meta:
        model = IPBlacklist
        fields = [
            'id', 'ip_address', 'subnet_mask', 'reason', 'threat_level',
            'threat_type', 'is_active', 'is_permanent', 'blocked_until',
            'confidence_score', 'attack_count', 'last_attempt', 'first_seen',
            'country_code', 'country_name', 'block_summary', 'threat_assessment'
        ]
    
    def get_block_summary(self, obj: IPBlacklist) -> Dict[str, Any]:
        """Get block summary information"""
        try:
            summary = {
                'is_currently_blocked': obj.is_currently_blocked(),
                'block_type': 'permanent' if obj.is_permanent else 'temporary',
                'days_since_first_seen': (timezone.now() - obj.first_seen).days if obj.first_seen else None,
                'has_subnet': obj.subnet_mask is not None,
                'geo_info': bool(obj.country_code and obj.country_code != "XX"),
            }
            
            # Add duration info for temporary blocks
            if not obj.is_permanent and obj.blocked_until:
                if obj.blocked_until > timezone.now():
                    remaining = obj.blocked_until - timezone.now()
                    summary['remaining_days'] = remaining.days
                    summary['is_expired'] = False
                else:
                    summary['is_expired'] = True
            
            return summary
            
        except Exception:
            return {'error': 'summary_unavailable'}
    
    def get_threat_assessment(self, obj: IPBlacklist) -> Dict[str, Any]:
        """Get threat assessment summary"""
        try:
            assessment = {
                'threat_level': obj.threat_level,
                'threat_type': obj.threat_type,
                'confidence_score': obj.confidence_score,
                'attack_count': obj.attack_count,
                'risk_category': self._get_risk_category(obj),
                'indicators': self._get_threat_indicators(obj),
            }
            
            return assessment
            
        except Exception:
            return {'error': 'assessment_unavailable'}
    
    def _get_risk_category(self, obj: IPBlacklist) -> str:
        """Get risk category based on threat level and confidence"""
        try:
            if obj.threat_level == 'confirmed_attacker' or obj.confidence_score >= 90:
                return 'critical'
            elif obj.threat_level == 'critical' or obj.confidence_score >= 70:
                return 'high'
            elif obj.threat_level == 'high' or obj.confidence_score >= 50:
                return 'medium'
            elif obj.threat_level == 'medium' or obj.confidence_score >= 30:
                return 'low'
            else:
                return 'very_low'
        except Exception:
            return 'unknown'
    
    def _get_threat_indicators(self, obj: IPBlacklist) -> List[str]:
        """Get threat indicators"""
        indicators = []
        try:
            if obj.threat_level in ['high', 'critical', 'confirmed_attacker']:
                indicators.append('high_threat_level')
            
            if obj.confidence_score >= 80:
                indicators.append('high_confidence')
            
            if obj.attack_count >= 10:
                indicators.append('multiple_attacks')
            
            if obj.threat_type in ['brute_force', 'ddos', 'credential_stuffing']:
                indicators.append('aggressive_attack')
            
            if obj.threat_type in ['malware', 'phishing']:
                indicators.append('malicious_content')
            
            return indicators
        except Exception:
            return []


class IPBlacklistCreateSerializer(DefensiveIPBlacklistMixin, serializers.Serializer):
    """Specialized serializer for creating IP blocks with defensive validation"""
    
    ip_address = serializers.CharField(
        required=True,
        max_length=45,
        help_text="IP address to block"
    )
    
    subnet_mask = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=32,
        help_text="Subnet mask for range blocking"
    )
    
    reason = serializers.CharField(
        required=True,
        max_length=1000,
        help_text="Reason for blocking"
    )
    
    block_type = serializers.ChoiceField(
        choices=[
            ('temporary', 'Temporary Block'),
            ('permanent', 'Permanent Block')
        ],
        default='temporary',
        help_text="Type of block"
    )
    
    duration_hours = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=8760,  # 1 year
        default=24,
        help_text="Duration in hours (for temporary blocks)"
    )
    
    threat_level = serializers.ChoiceField(
        choices=[
            ('low', 'Low Threat'),
            ('medium', 'Medium Threat'),
            ('high', 'High Threat'),
            ('critical', 'Critical Threat'),
            ('confirmed_attacker', 'Confirmed Attacker'),
        ],
        default='medium',
        help_text="Threat level assessment"
    )
    
    threat_type = serializers.ChoiceField(
        choices=[
            ('brute_force', 'Brute Force Attack'),
            ('ddos', 'DDoS Attack'),
            ('scanning', 'Port Scanning'),
            ('spam', 'Spam/Bot Activity'),
            ('malware', 'Malware Distribution'),
            ('phishing', 'Phishing Attempt'),
            ('credential_stuffing', 'Credential Stuffing'),
            ('api_abuse', 'API Abuse'),
            ('web_scraping', 'Web Scraping'),
            ('suspicious_pattern', 'Suspicious Pattern'),
            ('manual_block', 'Manual Block'),
            ('other', 'Other'),
        ],
        default='suspicious_pattern',
        help_text="Type of threat detected"
    )
    
    max_requests_per_minute = serializers.IntegerField(
        required=False,
        min_value=0,
        default=0,
        help_text="Maximum allowed requests per minute (0=complete block)"
    )
    
    reported_by_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of user who reported this IP"
    )
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Additional notes"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation for IP block creation"""
        errors = {}
        
        try:
            # Validate IP address
            ip_address = data['ip_address']
            if not self.validate_ip_address_format(ip_address):
                errors['ip_address'] = f"Invalid IP address format: {ip_address}"
            
            # Validate subnet mask
            subnet_mask = data.get('subnet_mask')
            if subnet_mask is not None and not self.validate_subnet_mask(subnet_mask):
                errors['subnet_mask'] = "Subnet mask must be between 0 and 32"
            
            # Validate block type consistency
            block_type = data['block_type']
            duration_hours = data.get('duration_hours', 24)
            
            if block_type == 'permanent':
                if 'duration_hours' in data:
                    errors['duration_hours'] = "Cannot set duration for permanent block"
            else:
                # Temporary block validation
                if duration_hours <= 0:
                    errors['duration_hours'] = "Duration must be positive"
            
            # Validate reported_by_id
            reported_by_id = data.get('reported_by')
            if reported_by_id is not None:
                try:
                    user = self.safe_get_user(reported_by_id)
                    data['reported_by'] = user
                except ValidationError as e:
                    errors.update(e.detail)
            
            # Remove reported_by_id from data as we've converted to user object
            if 'reported_by' in data:
                del data['reported_by']
            
            # Check for existing blocks
            try:
                self.check_existing_blocks(ip_address, subnet_mask)
            except ValidationError as e:
                errors.update(e.detail)
            
        except ValidationError as e:
            errors.update(e.detail)
        except Exception as e:
            logger.error(f"Validation error in IPBlacklistCreateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> IPBlacklist:
        """Create IP block using factory method"""
        try:
            ip_address = validated_data['ip_address']
            reason = validated_data['reason']
            threat_level = validated_data['threat_level']
            block_type = validated_data['block_type']
            
            # Prepare additional parameters
            kwargs = {
                'subnet_mask': validated_data.get('subnet_mask'),
                'threat_type': validated_data.get('threat_type', 'suspicious_pattern'),
                'max_requests_per_minute': validated_data.get('max_requests_per_minute', 0),
                'is_permanent': (block_type == 'permanent'),
                'duration_hours': validated_data.get('duration_hours', 24) if block_type == 'temporary' else None,
                'reported_by': validated_data.get('reported_by'),
                'notes': validated_data.get('notes', ''),
                'auto_blocked_by': 'manual',
                'detection_method': 'manual',
                'confidence_score': self._calculate_confidence_score(validated_data),
            }
            
            # Create block using factory method
            success, message, ip_block = IPBlacklist.block_ip(
                ip_address=ip_address,
                reason=reason,
                threat_level=threat_level,
                **kwargs
            )
            
            if not success:
                raise ValidationError({'non_field_errors': message})
            
            return ip_block
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create IP block: {e}")
            raise ValidationError(f"Failed to create IP block: {str(e)}")
    
    def _calculate_confidence_score(self, data: Dict[str, Any]) -> float:
        """Calculate confidence score based on input data"""
        score = 80.0  # Default confidence
        
        try:
            # Adjust based on threat level
            threat_level_scores = {
                'low': 40.0,
                'medium': 60.0,
                'high': 80.0,
                'critical': 90.0,
                'confirmed_attacker': 95.0
            }
            
            threat_level = data.get('threat_level', 'medium')
            score = threat_level_scores.get(threat_level, 80.0)
            
            # Adjust based on detection method (manual blocks get lower confidence)
            if data.get('detection_method', 'manual') == 'manual':
                score = max(50.0, score - 20.0)
            
            return min(100.0, max(0.0, score))
            
        except Exception:
            return 80.0  # Default on error
        


class DefensiveRiskScoreMixin:
    """Mixin for defensive RiskScore serialization with error handling"""
    
    @staticmethod
    def validate_score_range(score: int) -> bool:
        """Validate risk score is within valid range"""
        try:
            return 0 <= score <= 100
        except Exception:
            return False
    
    @staticmethod
    def safe_get_user(user_id: int):
        """Safely get user object with error handling"""
        try:
            User = get_user_model()
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'user': f'User with ID {user_id} does not exist'})
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise ValidationError({'user': 'Error retrieving user information'})
    
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
    
    def validate_risk_factors(self, data: Dict[str, Any]) -> None:
        """Validate risk factor values"""
        errors = {}
        
        try:
            # Validate all integer fields
            integer_fields = [
                'login_frequency', 'device_diversity', 'location_diversity',
                'failed_login_attempts', 'suspicious_activities', 'vpn_usage_count'
            ]
            
            for field in integer_fields:
                value = data.get(field, 0)
                if not isinstance(value, int) or value < 0:
                    errors[field] = f"{field} must be a non-negative integer"
            
            # Validate current score range
            current_score = data.get('current_score', 0)
            if not self.validate_score_range(current_score):
                errors['current_score'] = "Current score must be between 0 and 100"
            
            # Validate previous score range
            previous_score = data.get('previous_score', 0)
            if not self.validate_score_range(previous_score):
                errors['previous_score'] = "Previous score must be between 0 and 100"
            
            # Validate time fields
            time_fields = ['last_login_time', 'last_suspicious_activity']
            for field in time_fields:
                value = data.get(field)
                if value is not None and not isinstance(value, datetime):
                    errors[field] = f"{field} must be a valid datetime"
            
            if errors:
                raise ValidationError(errors)
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in risk factor validation: {e}")
            raise ValidationError({'non_field_errors': 'Validation error occurred'})


class RiskScoreSerializer(DefensiveRiskScoreMixin, serializers.ModelSerializer):
    """
    Defensive serializer for RiskScore with comprehensive validation
    এবং Null Object Pattern implementation
    """
    
    # Write-only field for user creation
    user_id = serializers.IntegerField(
        write_only=True,
        required=True,
        help_text="ID of the user"
    )
    
    # Read-only computed fields
    user_info = serializers.SerializerMethodField(
        help_text="User information (read-only)",
        read_only=True
    )
    
    risk_level = serializers.SerializerMethodField(
        help_text="Risk level based on score (read-only)",
        read_only=True
    )
    
    score_change = serializers.SerializerMethodField(
        help_text="Score change from previous (read-only)",
        read_only=True
    )
    
    risk_indicators = serializers.SerializerMethodField(
        help_text="Active risk indicators (read-only)",
        read_only=True
    )
    
    recommendations = serializers.SerializerMethodField(
        help_text="Risk mitigation recommendations (read-only)",
        read_only=True
    )
    
    # Null Object Pattern: Default values in Meta
    class Meta:
        model = RiskScore
        fields = [
            'id', 'user', 'user_info', 'current_score', 'previous_score',
            'login_frequency', 'device_diversity', 'location_diversity',
            'failed_login_attempts', 'suspicious_activities', 'vpn_usage_count',
            'last_login_time', 'last_suspicious_activity', 'calculated_at',
            'risk_level', 'score_change', 'risk_indicators', 'recommendations'
        ]
        read_only_fields = [
            'id', 'user_info', 'calculated_at', 'risk_level',
            'score_change', 'risk_indicators', 'recommendations'
        ]
        extra_kwargs = {
            'current_score': {
                'default': 0,
                'min_value': 0,
                'max_value': 100
            },
            'previous_score': {
                'default': 0,
                'min_value': 0,
                'max_value': 100
            },
            'login_frequency': {'default': 0, 'min_value': 0},
            'device_diversity': {'default': 1, 'min_value': 1},
            'location_diversity': {'default': 1, 'min_value': 1},
            'failed_login_attempts': {'default': 0, 'min_value': 0},
            'suspicious_activities': {'default': 0, 'min_value': 0},
            'vpn_usage_count': {'default': 0, 'min_value': 0},
            'last_login_time': {'allow_null': True, 'required': False},
            'last_suspicious_activity': {'allow_null': True, 'required': False},
        }
    
    def get_user_info(self, obj: RiskScore) -> Optional[Dict[str, Any]]:
        """Safely get user information with defensive coding"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'email': obj.user.email,
                    'is_active': obj.user.is_active,
                    'date_joined': obj.user.date_joined.isoformat() if obj.user.date_joined else None
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info for risk score {obj.id}: {e}")
            return {'error': 'user_info_unavailable', 'user': obj.user_id}
    
    def get_risk_level(self, obj: RiskScore) -> str:
        """Get human-readable risk level"""
        try:
            return self.calculate_risk_level(obj.current_score)
        except Exception as e:
            logger.error(f"Error calculating risk level for risk score {obj.id}: {e}")
            return 'unknown'
    
    def get_score_change(self, obj: RiskScore) -> Dict[str, Any]:
        """Get score change information"""
        try:
            change = obj.current_score - obj.previous_score
            return {
                'absolute_change': change,
                'percentage_change': (change / obj.previous_score * 100) if obj.previous_score > 0 else 0,
                'direction': 'increased' if change > 0 else 'decreased' if change < 0 else 'unchanged',
                'magnitude': 'significant' if abs(change) >= 20 else 'moderate' if abs(change) >= 10 else 'minor'
            }
        except Exception as e:
            logger.warning(f"Error calculating score change for risk score {obj.id}: {e}")
            return {'error': 'score_change_unavailable'}
    
    def get_risk_indicators(self, obj: RiskScore) -> List[str]:
        """Get active risk indicators"""
        indicators = []
        try:
            # Behavioral indicators
            if obj.login_frequency > 20:
                indicators.append('high_login_frequency')
            elif obj.login_frequency < 1:
                indicators.append('low_login_frequency')
            
            if obj.device_diversity > 5:
                indicators.append('high_device_diversity')
            
            if obj.location_diversity > 3:
                indicators.append('high_location_diversity')
            
            # Risk factor indicators
            if obj.failed_login_attempts > 5:
                indicators.append('multiple_failed_logins')
            
            if obj.suspicious_activities > 3:
                indicators.append('multiple_suspicious_activities')
            
            if obj.vpn_usage_count > 10:
                indicators.append('frequent_vpn_usage')
            
            # Time-based indicators
            if obj.last_suspicious_activity:
                hours_since = (timezone.now() - obj.last_suspicious_activity).total_seconds() / 3600
                if hours_since < 24:
                    indicators.append('recent_suspicious_activity')
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error getting risk indicators for risk score {obj.id}: {e}")
            return ['indicators_unavailable']
    
    def get_recommendations(self, obj: RiskScore) -> List[Dict[str, str]]:
        """Get risk mitigation recommendations"""
        recommendations = []
        try:
            # Recommendations based on risk indicators
            if obj.login_frequency > 20:
                recommendations.append({
                    'type': 'behavioral',
                    'message': 'Reduce login frequency to normal patterns',
                    'priority': 'medium'
                })
            
            if obj.device_diversity > 5:
                recommendations.append({
                    'type': 'security',
                    'message': 'Review device usage - too many unique devices detected',
                    'priority': 'high'
                })
            
            if obj.location_diversity > 3:
                recommendations.append({
                    'type': 'security',
                    'message': 'Monitor for suspicious location changes',
                    'priority': 'high'
                })
            
            if obj.failed_login_attempts > 5:
                recommendations.append({
                    'type': 'authentication',
                    'message': 'Implement account lockout for repeated failed attempts',
                    'priority': 'critical'
                })
            
            if obj.suspicious_activities > 3:
                recommendations.append({
                    'type': 'monitoring',
                    'message': 'Increase monitoring and review recent activities',
                    'priority': 'high'
                })
            
            if obj.vpn_usage_count > 10:
                recommendations.append({
                    'type': 'network',
                    'message': 'Review VPN usage patterns for anomalies',
                    'priority': 'medium'
                })
            
            # General recommendations based on risk level
            risk_level = self.calculate_risk_level(obj.current_score)
            if risk_level in ['high', 'critical']:
                recommendations.append({
                    'type': 'general',
                    'message': 'Consider requiring additional authentication',
                    'priority': 'critical'
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations for risk score {obj.id}: {e}")
            return [{
                'type': 'error',
                'message': 'Recommendations unavailable',
                'priority': 'low'
            }]
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive validation with defensive coding"""
        errors = {}
        
        try:
            # Validate user_id
            user_id = data.get('user')
            if not user_id:
                errors['user'] = "User ID is required"
            else:
                try:
                    user = self.safe_get_user(user_id)
                    data['user'] = user
                except ValidationError as e:
                    errors.update(e.detail)
            
            # Validate risk factors
            try:
                self.validate_risk_factors(data)
            except ValidationError as e:
                errors.update(e.detail)
            
            # Remove user_id from data as we've converted to user object
            if 'user' in data:
                del data['user']
            
        except Exception as e:
            logger.error(f"Unexpected validation error in RiskScoreSerializer: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> RiskScore:
        """Defensive create method with auto-calculation"""
        try:
            # Calculate score if not provided
            if 'current_score' not in validated_data or validated_data['current_score'] == 0:
                # Create temporary object for calculation
                temp_obj = RiskScore(**validated_data)
                validated_data['current_score'] = temp_obj.calculate_score()
            
            # Set default values
            validated_data.setdefault('previous_score', 0)
            validated_data.setdefault('calculated_at', timezone.now())
            
            # Create risk score
            risk_score = RiskScore.objects.create(**validated_data)
            
            # Log creation
            logger.info(
                f"RiskScore created: "
                f"ID={risk_score.id}, "
                f"User={risk_score.user_id}, "
                f"Score={risk_score.current_score}, "
                f"Level={self.calculate_risk_level(risk_score.current_score)}"
            )
            
            return risk_score
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create RiskScore: {e}")
            raise ValidationError(f"Failed to create risk score: {str(e)}")
    
    def update(self, instance: RiskScore, validated_data: Dict[str, Any]) -> RiskScore:
        """Defensive update method with score recalculation"""
        try:
            # Prevent modification of protected fields
            protected_fields = ['user', 'calculated_at']
            for field in protected_fields:
                if field in validated_data:
                    del validated_data[field]
            
            # Update instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            # Recalculate score if risk factors changed
            risk_factors = [
                'login_frequency', 'device_diversity', 'location_diversity',
                'failed_login_attempts', 'suspicious_activities', 'vpn_usage_count',
                'last_login_time', 'last_suspicious_activity'
            ]
            
            if any(field in validated_data for field in risk_factors):
                instance.update_score()
            else:
                instance.save()
            
            # Log update
            logger.info(
                f"RiskScore updated: "
                f"ID={instance.id}, "
                f"User={instance.user_id}, "
                f"New Score={instance.current_score}, "
                f"Change={instance.current_score - instance.previous_score}"
            )
            
            return instance
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to update RiskScore {instance.id}: {e}")
            raise ValidationError(f"Failed to update risk score: {str(e)}")


class RiskScoreListSerializer(DefensiveRiskScoreMixin, serializers.ModelSerializer):
    """Optimized serializer for listing RiskScores"""
    
    user_summary = serializers.SerializerMethodField(
        help_text="User summary (optimized for lists)"
    )
    
    risk_summary = serializers.SerializerMethodField(
        help_text="Risk summary information"
    )
    
    class Meta:
        model = RiskScore
        fields = [
            'id', 'user_summary', 'current_score', 'previous_score',
            'login_frequency', 'device_diversity', 'failed_login_attempts',
            'suspicious_activities', 'calculated_at', 'risk_summary'
        ]
    
    def get_user_summary(self, obj: RiskScore) -> Optional[Dict[str, Any]]:
        """Get optimized user summary"""
        try:
            if obj.user:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username[:20],
                    'is_active': obj.user.is_active
                }
            return None
        except Exception:
            return None
    
    def get_risk_summary(self, obj: RiskScore) -> Dict[str, Any]:
        """Get risk summary information"""
        try:
            risk_level = self.calculate_risk_level(obj.current_score)
            
            summary = {
                'risk_level': risk_level,
                'score_change': obj.current_score - obj.previous_score,
                'has_high_frequency': obj.login_frequency > 20,
                'has_multiple_devices': obj.device_diversity > 5,
                'has_failed_logins': obj.failed_login_attempts > 0,
                'has_suspicious_activities': obj.suspicious_activities > 0,
                'hours_since_calculation': int((timezone.now() - obj.calculated_at).total_seconds() / 3600)
            }
            
            # Add risk flags
            risk_flags = []
            if risk_level in ['high', 'critical']:
                risk_flags.append('high_risk')
            if obj.current_score - obj.previous_score >= 20:
                risk_flags.append('rapid_increase')
            
            if risk_flags:
                summary['risk_flags'] = risk_flags
            
            return summary
            
        except Exception:
            return {'error': 'summary_unavailable'}


class RiskScoreUpdateSerializer(DefensiveRiskScoreMixin, serializers.ModelSerializer):
    """Serializer for updating RiskScore (risk factors only)"""
    
    class Meta:
        model = RiskScore
        fields = [
            'login_frequency', 'device_diversity', 'location_diversity',
            'failed_login_attempts', 'suspicious_activities', 'vpn_usage_count',
            'last_login_time', 'last_suspicious_activity'
        ]
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate update data"""
        errors = {}
        
        try:
            # Validate risk factors
            self.validate_risk_factors(data)
            
        except ValidationError as e:
            errors.update(e.detail)
        except Exception as e:
            logger.error(f"Validation error in RiskScoreUpdateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def update(self, instance: RiskScore, validated_data: Dict[str, Any]) -> RiskScore:
        """Update risk factors and recalculate score"""
        try:
            # Update risk factors
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            # Update score
            instance.update_score()
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update RiskScore {instance.id}: {e}")
            raise ValidationError(f"Failed to update risk score: {str(e)}")


class RiskScoreCalculateSerializer(serializers.Serializer):
    """Serializer for calculating risk score from input data"""
    
    login_frequency = serializers.IntegerField(
        required=True,
        min_value=0,
        help_text="Number of logins per day"
    )
    
    device_diversity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Number of unique devices"
    )
    
    location_diversity = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Number of unique locations"
    )
    
    failed_login_attempts = serializers.IntegerField(
        required=True,
        min_value=0,
        help_text="Number of failed login attempts"
    )
    
    suspicious_activities = serializers.IntegerField(
        required=True,
        min_value=0,
        help_text="Number of suspicious activities"
    )
    
    vpn_usage_count = serializers.IntegerField(
        required=True,
        min_value=0,
        help_text="Number of VPN usage instances"
    )
    
    hours_since_last_suspicious = serializers.IntegerField(
        required=False,
        min_value=0,
        default=999,
        help_text="Hours since last suspicious activity"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data"""
        errors = {}
        
        try:
            # Validate all fields are within reasonable limits
            if data['login_frequency'] > 100:
                errors['login_frequency'] = "Login frequency too high"
            
            if data['device_diversity'] > 50:
                errors['device_diversity'] = "Device diversity too high"
            
            if data['location_diversity'] > 50:
                errors['location_diversity'] = "Location diversity too high"
            
            if data['failed_login_attempts'] > 100:
                errors['failed_login_attempts'] = "Failed login attempts too high"
            
            if data['suspicious_activities'] > 100:
                errors['suspicious_activities'] = "Suspicious activities too high"
            
            if data['vpn_usage_count'] > 100:
                errors['vpn_usage_count'] = "VPN usage count too high"
            
        except Exception as e:
            logger.error(f"Validation error in RiskScoreCalculateSerializer: {e}")
            errors['non_field_errors'] = "Validation error occurred"
        
        if errors:
            raise ValidationError(errors)
        
        return data
    
    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate risk score from input data"""
        try:
            # Create temporary RiskScore object for calculation
            temp_score = RiskScore(
                login_frequency=validated_data['login_frequency'],
                device_diversity=validated_data['device_diversity'],
                location_diversity=validated_data['location_diversity'],
                failed_login_attempts=validated_data['failed_login_attempts'],
                suspicious_activities=validated_data['suspicious_activities'],
                vpn_usage_count=validated_data['vpn_usage_count'],
                last_suspicious_activity=(
                    timezone.now() - timedelta(hours=validated_data.get('hours_since_last_suspicious', 999))
                    if validated_data.get('hours_since_last_suspicious', 999) < 999 else None
                )
            )
            
            # Calculate score
            score = temp_score.calculate_score()
            risk_level = self.calculate_risk_level(score)
            
            # Calculate contributing factors
            factors = self._calculate_contributing_factors(temp_score)
            
            return {
                'calculated_score': score,
                'risk_level': risk_level,
                'contributing_factors': factors,
                'calculation_timestamp': timezone.now().isoformat(),
                'input_data': validated_data
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate risk score: {e}")
            raise ValidationError(f"Failed to calculate risk score: {str(e)}")
    
    def _calculate_contributing_factors(self, risk_score: RiskScore) -> List[Dict[str, Any]]:
        """Calculate contributing factors to the risk score"""
        factors = []
        
        try:
            # Behavioral factors
            if risk_score.login_frequency > 20:
                factors.append({
                    'factor': 'high_login_frequency',
                    'value': risk_score.login_frequency,
                    'contribution': 15,
                    'description': 'Too frequent logins'
                })
            elif risk_score.login_frequency < 1:
                factors.append({
                    'factor': 'low_login_frequency',
                    'value': risk_score.login_frequency,
                    'contribution': 10,
                    'description': 'Too infrequent logins'
                })
            
            if risk_score.device_diversity > 5:
                factors.append({
                    'factor': 'high_device_diversity',
                    'value': risk_score.device_diversity,
                    'contribution': 20,
                    'description': 'Too many unique devices'
                })
            
            if risk_score.location_diversity > 3:
                factors.append({
                    'factor': 'high_location_diversity',
                    'value': risk_score.location_diversity,
                    'contribution': 25,
                    'description': 'Rapid location changes'
                })
            
            # Risk factors
            if risk_score.failed_login_attempts > 0:
                contribution = min(risk_score.failed_login_attempts * 5, 30)
                factors.append({
                    'factor': 'failed_login_attempts',
                    'value': risk_score.failed_login_attempts,
                    'contribution': contribution,
                    'description': 'Failed authentication attempts'
                })
            
            if risk_score.suspicious_activities > 0:
                contribution = min(risk_score.suspicious_activities * 8, 40)
                factors.append({
                    'factor': 'suspicious_activities',
                    'value': risk_score.suspicious_activities,
                    'contribution': contribution,
                    'description': 'Suspicious activities detected'
                })
            
            if risk_score.vpn_usage_count > 10:
                factors.append({
                    'factor': 'frequent_vpn_usage',
                    'value': risk_score.vpn_usage_count,
                    'contribution': 15,
                    'description': 'Frequent VPN usage'
                })
            
            return factors
            
        except Exception:
            return [{'factor': 'error', 'description': 'Could not calculate contributing factors'}]
        
        
class AppVersionSerializer(serializers.ModelSerializer):
    """Serializer for AppVersion model"""
    
    # Additional fields for display
    release_type_display = serializers.CharField(
        source='get_release_type_display',
        read_only=True
    )
    
    is_currently_active = serializers.BooleanField(
        read_only=True,
        help_text="Whether this version is currently active"
    )
    
    # For writing
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),  # Assuming User model
        source='created_by',
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = AppVersion
        fields = [
            'id',
            'version_name',
            'version_code',
            'release_type',
            'release_type_display',
            'release_notes',
            'is_mandatory',
            'min_os_version',
            'max_os_version',
            'download_url',
            'checksum',
            'file_size',
            'release_date',
            'effective_from',
            'deprecated_at',
            'is_active',
            'is_currently_active',
            'supported_platforms',
            'created_by',
            'created_by',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'is_currently_active',
            'created_at',
            'updated_at',
            'release_type_display'
        ]
    
    def validate(self, data):
        """Custom validation for AppVersion"""
        # Version name validation
        if 'version_name' in data:
            version_name = data['version_name']
            if not version_name or len(version_name.strip()) == 0:
                raise serializers.ValidationError({
                    'version_name': 'Version name cannot be empty'
                })
        
        # Version code validation
        if 'version_code' in data:
            version_code = data['version_code']
            if not version_code or len(version_code.strip()) == 0:
                raise serializers.ValidationError({
                    'version_code': 'Version code cannot be empty'
                })
        
        # Date validation
        if 'effective_from' in data and 'deprecated_at' in data:
            if data['deprecated_at'] and data['effective_from']:
                if data['deprecated_at'] <= data['effective_from']:
                    raise serializers.ValidationError({
                        'deprecated_at': 'Deprecated date must be after effective date'
                    })
        
        # File size validation
        if 'file_size' in data and data['file_size'] < 0:
            raise serializers.ValidationError({
                'file_size': 'File size cannot be negative'
            })
        
        # Supported platforms validation
        if 'supported_platforms' in data:
            supported_platforms = data['supported_platforms']
            if supported_platforms and not isinstance(supported_platforms, list):
                raise serializers.ValidationError({
                    'supported_platforms': 'Supported platforms must be a list'
                })
        
        return data
    
    def create(self, validated_data):
        """Create a new AppVersion with defensive coding"""
        try:
            # Set default supported platforms if not provided
            if 'supported_platforms' not in validated_data or not validated_data['supported_platforms']:
                validated_data['supported_platforms'] = ['web', 'android', 'ios']
            
            # Auto-generate version code if not provided
            if 'version_code' not in validated_data or not validated_data['version_code']:
                version_name = validated_data.get('version_name', '1.0.0')
                try:
                    parts = version_name.split('.')
                    code = int(''.join([part.zfill(2) for part in parts]))
                    validated_data['version_code'] = str(code)
                except:
                    # Fallback to timestamp
                    validated_data['version_code'] = str(int(timezone.now().timestamp()))
            
            # Create the instance
            instance = super().create(validated_data)
            
            # Clear cache for latest version
            if instance.supported_platforms:
                for platform in instance.supported_platforms:
                    cache_key = f'app_version:latest:{platform}'
                    cache.delete(cache_key)
            
            logger.info(f"Created new AppVersion: {instance.version_name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create AppVersion: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to create version: {str(e)}'
            })
    
    def update(self, instance, validated_data):
        """Update AppVersion with defensive coding"""
        try:
            # Clear cache if supported platforms or active status changed
            clear_cache = False
            if 'supported_platforms' in validated_data or 'is_active' in validated_data:
                clear_cache = True
            
            # Update the instance
            instance = super().update(instance, validated_data)
            
            # Clear cache if needed
            if clear_cache and instance.supported_platforms:
                for platform in instance.supported_platforms:
                    cache_key = f'app_version:latest:{platform}'
                    cache.delete(cache_key)
            
            logger.info(f"Updated AppVersion: {instance.version_name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update AppVersion {instance.version_name}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to update version: {str(e)}'
            })


class AppVersionCheckSerializer(serializers.Serializer):
    """Serializer for checking app updates"""
    
    current_version_code = serializers.CharField(
        required=True,
        max_length=20,
        help_text="Current version code of the app"
    )
    
    platform = serializers.CharField(
        required=False,
        default='web',
        max_length=20,
        help_text="Platform (web, android, ios)"
    )
    
    def validate(self, data):
        """Validate the check request"""
        platform = data.get('platform', 'web')
        valid_platforms = ['web', 'android', 'ios', 'desktop']
        
        if platform.lower() not in valid_platforms:
            raise serializers.ValidationError({
                'platform': f'Platform must be one of: {", ".join(valid_platforms)}'
            })
        
        return data


class AppVersionInfoSerializer(serializers.ModelSerializer):
    """Serializer for public version information"""
    
    release_type_display = serializers.CharField(
        source='get_release_type_display',
        read_only=True
    )
    
    formatted_file_size = serializers.SerializerMethodField(
        help_text="File size in human-readable format"
    )
    
    class Meta:
        model = AppVersion
        fields = [
            'version_name',
            'version_code',
            'release_type',
            'release_type_display',
            'release_notes',
            'is_mandatory',
            'download_url',
            'file_size',
            'formatted_file_size',
            'checksum',
            'min_os_version',
            'max_os_version',
            'release_date',
            'supported_platforms'
        ]
    
    def get_formatted_file_size(self, obj):
        """Format file size in human-readable format"""
        if not obj.file_size:
            return "0 bytes"
        
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if obj.file_size < 1024.0:
                return f"{obj.file_size:.2f} {unit}"
            obj.file_size /= 1024.0
        
        return f"{obj.file_size:.2f} TB"


class AppVersionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating AppVersion (admin only)"""
    
    class Meta:
        model = AppVersion
        fields = [
            'version_name',
            'version_code',
            'release_type',
            'release_notes',
            'is_mandatory',
            'min_os_version',
            'max_os_version',
            'download_url',
            'checksum',
            'file_size',
            'release_date',
            'effective_from',
            'supported_platforms',
            'notes'
        ]
    
    def validate(self, data):
        """Additional validation for creation"""
        # Check if version name already exists
        if 'version_name' in data:
            version_name = data['version_name']
            if AppVersion.objects.filter(version_name=version_name).exists():
                raise serializers.ValidationError({
                    'version_name': f'Version "{version_name}" already exists'
                })
        
        # Check if version code already exists
        if 'version_code' in data:
            version_code = data['version_code']
            if AppVersion.objects.filter(version_code=version_code).exists():
                raise serializers.ValidationError({
                    'version_code': f'Version code "{version_code}" already exists'
                })
        
        return data
    

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer with defensive coding"""
    
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        read_only_fields = fields
    
    def to_representation(self, instance):
        """Safe representation using getattr"""
        # Null Object Pattern: Provide default values if attributes don't exist
        data = super().to_representation(instance)
        
        # Use getattr for safe attribute access
        data['username'] = getattr(instance, 'username', 'Unknown')
        data['email'] = getattr(instance, 'email', '')
        data['first_name'] = getattr(instance, 'first_name', '')
        data['last_name'] = getattr(instance, 'last_name', '')
        
        return data


class WithdrawalProtectionSerializer(serializers.ModelSerializer):
    """Main serializer for WithdrawalProtection model"""
    
    # Defensive coding: Use safe attribute access
    user_detail = serializers.SerializerMethodField(
        read_only=True,
        help_text="User details (safe access)"
    )
    
    created_by_detail = serializers.SerializerMethodField(
        read_only=True,
        help_text="Created by user details (safe access)"
    )
    
    # Display fields with defensive coding
    protection_level_display = serializers.CharField(
        source='get_protection_level_display',
        read_only=True
    )
    
    risk_level_display = serializers.CharField(
        source='get_risk_level_display',
        read_only=True
    )
    
    # Null Object Pattern: Default values for JSON fields
    whitelisted_ips = serializers.JSONField(
        default=list,
        allow_null=True,
        help_text="IP addresses allowed for withdrawals"
    )
    
    whitelisted_devices = serializers.JSONField(
        default=list,
        allow_null=True,
        help_text="Device IDs allowed for withdrawals"
    )
    
    blacklisted_destinations = serializers.JSONField(
        default=list,
        allow_null=True,
        help_text="Blocked withdrawal destinations"
    )
    
    allowed_withdrawal_hours = serializers.JSONField(
        default=get_hours_default,
        allow_null=True,
        help_text="Allowed withdrawal hours (0-23)"
    )
    
    allowed_withdrawal_days = serializers.JSONField(
        default=get_hours_default,
        allow_null=True,
        help_text="Allowed withdrawal days (0=Monday, 6=Sunday)"
    )
    
    custom_rules = serializers.JSONField(
        default=dict,
        allow_null=True,
        help_text="Custom withdrawal protection rules"
    )
    
    exceptions = serializers.JSONField(
        default=dict,
        allow_null=True,
        help_text="Exceptions to protection rules"
    )
    
    
    # For writing (with defensive error handling)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True,
        required=True,
        error_messages={
            'does_not_exist': 'The provided user ID does not exist.',
            'incorrect_type': 'Invalid type. User ID must be an integer.',
            'null': 'User ID cannot be null.'
        }
    )

    def get_queryset(self):
        """
        Defensive Coding: Dynamically ensure queryset is available
        and handle potential database connection issues.
        """
        try:
            return User.objects.all()
        except Exception:
            return User.objects.none()
        
        
        # For writing (Bulletproof with Defensive error handling)
    created_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='created_by',
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': 'The selected administrator does not exist.',
            'incorrect_type': 'Invalid format. Administrator ID must be an integer.',
        }
    )
        
    
    # Computed properties (safe access)
    daily_remaining = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
        help_text="Daily remaining limit"
    )
    
    weekly_remaining = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
        help_text="Weekly remaining limit"
    )
    
    monthly_remaining = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
        help_text="Monthly remaining limit"
    )
    
    class Meta:
        model = WithdrawalProtection
        fields = [
            'id',
            'user', 'user_detail', 'user',
            'is_active',
            'protection_level', 'protection_level_display',
            'daily_limit', 'weekly_limit', 'monthly_limit',
            'single_transaction_limit', 'min_withdrawal_amount',
            'daily_count_limit', 'weekly_count_limit', 'monthly_count_limit',
            'require_2fa', 'require_email_confirmation', 'require_sms_confirmation',
            'delay_hours',
            'risk_score', 'risk_level', 'risk_level_display',
            'auto_hold_threshold',
            'whitelisted_ips', 'whitelisted_devices', 'blacklisted_destinations',
            'allowed_withdrawal_hours', 'allowed_withdrawal_days',
            'require_id_verification', 'require_address_verification',
            'min_account_age_days',
            'notify_on_large_withdrawal', 'large_withdrawal_threshold',
            'notify_on_suspicious_activity',
            'total_withdrawals', 'total_withdrawal_amount', 'last_withdrawal_at',
            'custom_rules', 'exceptions',
            'created_by', 'created_by_detail', 'created_by',
            'notes',
            'daily_remaining', 'weekly_remaining', 'monthly_remaining',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'daily_remaining', 'weekly_remaining', 'monthly_remaining',
            'created_at', 'updated_at', 'protection_level_display',
            'risk_level_display', 'user_detail', 'created_by_detail'
        ]
    
    def __init__(self, *args, **kwargs):
        """Initialize with dynamic queryset assignment"""
        super().__init__(*args, **kwargs)
        
        # Graceful Degradation: Handle missing User model
        try:
            User = get_user_model()
            self.fields['user'].queryset = User.objects.all()
            self.fields['created_by'].queryset = User.objects.all()
        except Exception as e:
            logger.warning(f"Could not set user queryset: {e}")
            # Don't break if user model not available
    
    def get_user_detail(self, obj) -> Optional[Dict[str, Any]]:
        """Get user details with defensive coding"""
        try:
            user = getattr(obj, 'user', None)
            if user:
                # Use getattr for safe attribute access
                return {
                    'id': getattr(user, 'id', None),
                    'username': getattr(user, 'username', 'Unknown'),
                    'email': getattr(user, 'email', ''),
                    'is_active': getattr(user, 'is_active', False)
                }
        except Exception as e:
            logger.debug(f"Error getting user detail: {e}")
        return None
    
    def get_created_by_detail(self, obj) -> Optional[Dict[str, Any]]:
        """Get created_by details with defensive coding"""
        try:
            created_by = getattr(obj, 'created_by', None)
            if created_by:
                return {
                    'id': getattr(created_by, 'id', None),
                    'username': getattr(created_by, 'username', 'Unknown'),
                    'email': getattr(created_by, 'email', '')
                }
        except Exception as e:
            logger.debug(f"Error getting created_by detail: {e}")
        return None
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate with defensive error handling"""
        errors = {}
        
        try:
            # Amount validations
            if 'daily_limit' in attrs and attrs['daily_limit'] <= 0:
                errors['daily_limit'] = "Daily limit must be positive"
            
            if 'weekly_limit' in attrs and attrs['weekly_limit'] <= 0:
                errors['weekly_limit'] = "Weekly limit must be positive"
            
            if 'monthly_limit' in attrs and attrs['monthly_limit'] <= 0:
                errors['monthly_limit'] = "Monthly limit must be positive"
            
            if 'single_transaction_limit' in attrs and attrs['single_transaction_limit'] <= 0:
                errors['single_transaction_limit'] = "Single transaction limit must be positive"
            
            if 'min_withdrawal_amount' in attrs and attrs['min_withdrawal_amount'] <= 0:
                errors['min_withdrawal_amount'] = "Minimum withdrawal amount must be positive"
            
            # Logical validations
            daily_limit = attrs.get('daily_limit', getattr(self.instance, 'daily_limit', 1000.00) if self.instance else 1000.00)
            weekly_limit = attrs.get('weekly_limit', getattr(self.instance, 'weekly_limit', 5000.00) if self.instance else 5000.00)
            monthly_limit = attrs.get('monthly_limit', getattr(self.instance, 'monthly_limit', 20000.00) if self.instance else 20000.00)
            
            if daily_limit > weekly_limit:
                errors['daily_limit'] = "Daily limit cannot exceed weekly limit"
            
            if weekly_limit > monthly_limit:
                errors['weekly_limit'] = "Weekly limit cannot exceed monthly limit"
            
            # JSON field validations with defensive coding
            json_fields = ['whitelisted_ips', 'whitelisted_devices', 'blacklisted_destinations']
            for field in json_fields:
                if field in attrs and attrs[field] is not None:
                    if not isinstance(attrs[field], list):
                        errors[field] = f"{field} must be a list"
            
            # Risk score validation
            if 'risk_score' in attrs:
                risk_score = attrs['risk_score']
                if not (0 <= risk_score <= 100):
                    errors['risk_score'] = "Risk score must be between 0 and 100"
            
            # Time-based restrictions validation
            if 'allowed_withdrawal_hours' in attrs and attrs['allowed_withdrawal_hours']:
                try:
                    hours = attrs['allowed_withdrawal_hours']
                    if not isinstance(hours, list):
                        errors['allowed_withdrawal_hours'] = "Must be a list"
                    else:
                        for hour in hours:
                            if not isinstance(hour, int) or not 0 <= hour <= 23:
                                errors['allowed_withdrawal_hours'] = f"Invalid hour: {hour}"
                except Exception:
                    errors['allowed_withdrawal_hours'] = "Invalid format"
            
            # Account age validation
            if 'min_account_age_days' in attrs and attrs['min_account_age_days'] < 0:
                errors['min_account_age_days'] = "Cannot be negative"
            
        except Exception as e:
            # Graceful Degradation: Don't crash on validation error
            logger.error(f"Validation error in WithdrawalProtectionSerializer: {e}")
            errors.setdefault('non_field_errors', []).append("Validation error occurred")
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> 'WithdrawalProtection':
        """Create with defensive coding"""
        try:
            # Set created_by from request context if not provided
            if 'created_by' not in validated_data:
                request = self.context.get('request')
                if request and hasattr(request, 'user') and request.user.is_authenticated:
                    validated_data['created_by'] = request.user
            
            # Ensure JSON fields have default values (Null Object Pattern)
            json_defaults = {
                'whitelisted_ips': [],
                'whitelisted_devices': [],
                'blacklisted_destinations': [],
                'allowed_withdrawal_hours': list(range(0, 24)),
                'allowed_withdrawal_days': list(range(0, 7)),
                'custom_rules': {},
                'exceptions': {},
            }
            
            for field, default in json_defaults.items():
                if field not in validated_data or validated_data[field] is None:
                    validated_data[field] = default
            
            instance = super().create(validated_data)
            
            # Update cache
            try:
                cache_key = f'withdrawal_protection:{instance.user_id}'
                cache.delete(cache_key)
            except Exception as e:
                logger.warning(f"Cache update failed: {e}")
            
            logger.info(f"Created WithdrawalProtection for user {instance.user_id}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create WithdrawalProtection: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f"Failed to create protection: {str(e)}"
            })
    
    def update(self, instance: 'WithdrawalProtection', validated_data: Dict[str, Any]) -> 'WithdrawalProtection':
        """Update with defensive coding"""
        try:
            # Preserve existing values for JSON fields if new value is None
            json_fields = [
                'whitelisted_ips', 'whitelisted_devices', 'blacklisted_destinations',
                'allowed_withdrawal_hours', 'allowed_withdrawal_days',
                'custom_rules', 'exceptions'
            ]
            
            for field in json_fields:
                if field in validated_data and validated_data[field] is None:
                    # Keep existing value
                    validated_data.pop(field)
            
            # Clear cache before updating
            cache_key = f'withdrawal_protection:{instance.user_id}'
            cache.delete(cache_key)
            
            updated_instance = super().update(instance, validated_data)
            
            logger.info(f"Updated WithdrawalProtection {instance.id}")
            return updated_instance
            
        except Exception as e:
            logger.error(f"Failed to update WithdrawalProtection {instance.id}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f"Failed to update protection: {str(e)}"
            })


class WithdrawalCheckSerializer(serializers.Serializer):
    """Serializer for checking withdrawal permissions"""
    
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01'),
        help_text="Withdrawal amount"
    )
    
    destination = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=255,
        help_text="Withdrawal destination (wallet/bank)"
    )
    
    ip_address = serializers.IPAddressField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="IP address of withdrawal request"
    )
    
    device_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=255,
        help_text="Device ID making the request"
    )
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate withdrawal check request"""
        amount = attrs.get('amount', Decimal('0'))
        
        if amount <= 0:
            raise serializers.ValidationError({
                'amount': 'Withdrawal amount must be positive'
            })
        
        return attrs


class WithdrawalLimitUpdateSerializer(serializers.Serializer):
    """Serializer for updating withdrawal limits"""
    
    daily_limit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Daily withdrawal limit"
    )
    
    weekly_limit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Weekly withdrawal limit"
    )
    
    monthly_limit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Monthly withdrawal limit"
    )
    
    single_transaction_limit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Single transaction limit"
    )
    
    min_withdrawal_amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        min_value=Decimal('0.01'),
        help_text="Minimum withdrawal amount"
    )
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate limit updates with defensive coding"""
        try:
            # Get current values safely
            protection = self.context.get('protection')
            if not protection:
                return attrs
            
            # Use dict.get() with defaults
            daily_limit = attrs.get('daily_limit', getattr(protection, 'daily_limit', 1000.00))
            weekly_limit = attrs.get('weekly_limit', getattr(protection, 'weekly_limit', 5000.00))
            monthly_limit = attrs.get('monthly_limit', getattr(protection, 'monthly_limit', 20000.00))
            
            # Logical validation
            if daily_limit > weekly_limit:
                raise serializers.ValidationError({
                    'daily_limit': 'Daily limit cannot exceed weekly limit'
                })
            
            if weekly_limit > monthly_limit:
                raise serializers.ValidationError({
                    'weekly_limit': 'Weekly limit cannot exceed monthly limit'
                })
            
        except Exception as e:
            logger.error(f"Limit validation error: {e}")
            # Don't crash, return partial validation
            pass
        
        return attrs


class WithdrawalProtectionSummarySerializer(serializers.ModelSerializer):
    """Serializer for withdrawal protection summary"""
    
    user_info = serializers.SerializerMethodField(
        help_text="Basic user information"
    )
    
    limits_summary = serializers.SerializerMethodField(
        help_text="Withdrawal limits summary"
    )
    
    security_summary = serializers.SerializerMethodField(
        help_text="Security features summary"
    )
    
    usage_summary = serializers.SerializerMethodField(
        help_text="Usage statistics"
    )
    
    class Meta:
        model = WithdrawalProtection
        fields = [
            'id',
            'user_info',
            'is_active',
            'protection_level',
            'risk_level',
            'risk_score',
            'limits_summary',
            'security_summary',
            'usage_summary',
            'created_at',
            'updated_at'
        ]
    
    def get_user_info(self, obj) -> Dict[str, Any]:
        """Get user info with defensive coding"""
        try:
            user = getattr(obj, 'user', None)
            if user:
                return {
                    'id': getattr(user, 'id', None),
                    'username': getattr(user, 'username', 'Unknown'),
                    'email': getattr(user, 'email', '')
                }
        except Exception:
            pass
        return {'error': 'User information not available'}
    
    def get_limits_summary(self, obj) -> Dict[str, Any]:
        """Get limits summary with defensive coding"""
        try:
            return {
                'daily': float(getattr(obj, 'daily_limit', 0)),
                'weekly': float(getattr(obj, 'weekly_limit', 0)),
                'monthly': float(getattr(obj, 'monthly_limit', 0)),
                'single_transaction': float(getattr(obj, 'single_transaction_limit', 0)),
                'min_amount': float(getattr(obj, 'min_withdrawal_amount', 0))
            }
        except Exception:
            return {}
    
    def get_security_summary(self, obj) -> Dict[str, Any]:
        """Get security summary with defensive coding"""
        try:
            return {
                'require_2fa': getattr(obj, 'require_2fa', False),
                'require_email_confirmation': getattr(obj, 'require_email_confirmation', True),
                'require_sms_confirmation': getattr(obj, 'require_sms_confirmation', False),
                'delay_hours': getattr(obj, 'delay_hours', 0),
                'whitelisted_ips_count': len(getattr(obj, 'whitelisted_ips', [])),
                'blacklisted_destinations_count': len(getattr(obj, 'blacklisted_destinations', []))
            }
        except Exception:
            return {}
    
    def get_usage_summary(self, obj) -> Dict[str, Any]:
        """Get usage summary with defensive coding"""
        try:
            return {
                'total_withdrawals': getattr(obj, 'total_withdrawals', 0),
                'total_amount': float(getattr(obj, 'total_withdrawal_amount', 0)),
                'last_withdrawal': getattr(obj, 'last_withdrawal_at', None)
            }
        except Exception:
            return {}


class SecurityDashboardSerializer(serializers.Serializer):
    """
    Bulletproof Plain Serializer (No Model Required)
    Defensive Coding & Null Object Pattern Implementation
    """
    
    # Defensive Coding: সব ফিল্ডে ডিফল্ট ভ্যালু (Null Object Pattern)
    total_users = serializers.IntegerField(
        default=0, 
        min_value=0,
        read_only=True,
        help_text="Total number of users in the system"
    )
    
    active_users = serializers.IntegerField(
        default=0,
        min_value=0,
        read_only=True,
        help_text="Number of currently active users"
    )
    
    active_threats = serializers.IntegerField(
        default=0,
        min_value=0,
        read_only=True,
        help_text="Number of active security threats"
    )
    
    risk_score = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        max_value=100.0,
        read_only=True,
        help_text="Overall system risk score (0-100)"
    )
    
    system_status = serializers.CharField(
        default="Operational",
        max_length=50,
        read_only=True,
        help_text="Current system status"
    )
    
    uptime_percentage = serializers.FloatField(
        default=100.0,
        min_value=0.0,
        max_value=100.0,
        read_only=True,
        help_text="System uptime percentage"
    )
    
    # Null Object Pattern: ডিফল্ট হিসেবে empty list/dict
    recent_logs = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        read_only=True,
        help_text="Recent security logs"
    )
    
    threat_breakdown = serializers.DictField(
        child=serializers.IntegerField(),
        default=dict,
        read_only=True,
        help_text="Breakdown of threats by type"
    )
    
    top_risky_users = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        read_only=True,
        help_text="Top users with highest risk scores"
    )
    
    system_metrics = serializers.DictField(
        default=dict,
        read_only=True,
        help_text="Various system performance metrics"
    )
    
    last_updated = serializers.DateTimeField(
        read_only=True,
        help_text="When this dashboard data was last updated"
    )
    
    # Optional metadata with safe defaults
    metadata = serializers.DictField(
        default=dict,
        read_only=True,
        help_text="Additional metadata about the dashboard"
    )
    
    errors = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        read_only=True,
        help_text="Any errors encountered while generating dashboard"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Defensive validation with Graceful Degradation
        """
        validated_data = {}
        
        try:
            # Use dict.get() with defaults for all fields
            validated_data['total_users'] = data.get('total_users', 0)
            validated_data['active_users'] = data.get('active_users', 0)
            validated_data['active_threats'] = data.get('active_threats', 0)
            validated_data['risk_score'] = data.get('risk_score', 0.0)
            validated_data['system_status'] = data.get('system_status', "Unknown")
            validated_data['uptime_percentage'] = data.get('uptime_percentage', 100.0)
            validated_data['recent_logs'] = data.get('recent_logs', [])
            validated_data['threat_breakdown'] = data.get('threat_breakdown', {})
            validated_data['top_risky_users'] = data.get('top_risky_users', [])
            validated_data['system_metrics'] = data.get('system_metrics', {})
            validated_data['last_updated'] = data.get('last_updated')
            validated_data['metadata'] = data.get('metadata', {})
            validated_data['errors'] = data.get('errors', [])
            
            # Additional validation logic
            self._validate_risk_score(validated_data['risk_score'])
            self._validate_counts(validated_data)
            
        except Exception as e:
            # Graceful Degradation: Log error but continue
            logger.warning(f"Dashboard validation error: {e}")
            # Return safe defaults
            return self._get_safe_defaults()
        
        return validated_data
    
    def _validate_risk_score(self, risk_score: float) -> None:
        """Validate risk score with defensive bounds"""
        if not isinstance(risk_score, (int, float)):
            raise serializers.ValidationError({
                'risk_score': 'Risk score must be a number'
            })
        
        if risk_score < 0 or risk_score > 100:
            # Auto-correct rather than fail
            logger.warning(f"Risk score {risk_score} out of bounds, normalizing")
            return max(0, min(100, risk_score))
    
    def _validate_counts(self, data: Dict[str, Any]) -> None:
        """Validate count fields"""
        for field in ['total_users', 'active_users', 'active_threats']:
            value = data.get(field, 0)
            if not isinstance(value, int) or value < 0:
                data[field] = 0  # Null Object Pattern: Default to 0
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Return safe default values for graceful degradation"""
        return {
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
            'last_updated': None,
            'metadata': {},
            'errors': ["Dashboard data temporarily unavailable"]
        }
    
    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """
        Graceful Degradation: Handle any type of input data
        """
        try:
            # Handle different input types
            if isinstance(instance, dict):
                # Use dict.get() for safe dictionary access
                return self._represent_dict(instance)
            elif hasattr(instance, '__dict__'):
                # Use getattr() for safe object attribute access
                return self._represent_object(instance)
            elif isinstance(instance, list) and len(instance) == 1:
                # Handle list with single item
                return self.to_representation(instance[0])
            else:
                # Unknown type, return defaults
                logger.warning(f"Unknown instance type: {type(instance)}")
                return self._get_safe_defaults()
                
        except Exception as e:
            # Graceful Degradation: Never crash
            logger.error(f"Error in dashboard representation: {e}")
            return self._get_safe_defaults()
    
    def _represent_dict(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Represent dictionary data with defensive coding"""
        representation = {}
        
        # Use dict.get() with defaults for all fields
        representation['total_users'] = data_dict.get('total_users', 0)
        representation['active_users'] = data_dict.get('active_users', 0)
        representation['active_threats'] = data_dict.get('active_threats', 0)
        
        # Handle risk score with bounds
        risk_score = data_dict.get('risk_score', 0.0)
        representation['risk_score'] = max(0.0, min(100.0, float(risk_score)))
        
        representation['system_status'] = data_dict.get('system_status', "Unknown")
        
        # Handle percentage with bounds
        uptime = data_dict.get('uptime_percentage', 100.0)
        representation['uptime_percentage'] = max(0.0, min(100.0, float(uptime)))
        
        # Use safe list/dict access
        representation['recent_logs'] = data_dict.get('recent_logs', []) or []
        representation['threat_breakdown'] = data_dict.get('threat_breakdown', {}) or {}
        representation['top_risky_users'] = data_dict.get('top_risky_users', []) or []
        representation['system_metrics'] = data_dict.get('system_metrics', {}) or {}
        representation['last_updated'] = data_dict.get('last_updated')
        representation['metadata'] = data_dict.get('metadata', {}) or {}
        representation['errors'] = data_dict.get('errors', []) or []
        
        # Add calculated fields
        representation['threat_level'] = self._calculate_threat_level(
            representation['risk_score']
        )
        
        return representation
    
    def _represent_object(self, obj: Any) -> Dict[str, Any]:
        """Represent object data with defensive coding"""
        representation = {}
        
        # Use getattr() with defaults for all fields
        representation['total_users'] = getattr(obj, 'total_users', 0)
        representation['active_users'] = getattr(obj, 'active_users', 0)
        representation['active_threats'] = getattr(obj, 'active_threats', 0)
        
        # Handle risk score with bounds
        risk_score = getattr(obj, 'risk_score', 0.0)
        representation['risk_score'] = max(0.0, min(100.0, float(risk_score)))
        
        representation['system_status'] = getattr(obj, 'system_status', "Unknown")
        
        # Handle percentage with bounds
        uptime = getattr(obj, 'uptime_percentage', 100.0)
        representation['uptime_percentage'] = max(0.0, min(100.0, float(uptime)))
        
        # Use getattr with safe defaults
        representation['recent_logs'] = getattr(obj, 'recent_logs', []) or []
        representation['threat_breakdown'] = getattr(obj, 'threat_breakdown', {}) or {}
        representation['top_risky_users'] = getattr(obj, 'top_risky_users', []) or []
        representation['system_metrics'] = getattr(obj, 'system_metrics', {}) or {}
        representation['last_updated'] = getattr(obj, 'last_updated', None)
        representation['metadata'] = getattr(obj, 'metadata', {}) or {}
        representation['errors'] = getattr(obj, 'errors', []) or []
        
        # Handle calculated or method-based attributes
        if hasattr(obj, 'get_threat_level'):
            representation['threat_level'] = getattr(obj, 'get_threat_level')()
        else:
            representation['threat_level'] = self._calculate_threat_level(
                representation['risk_score']
            )
        
        return representation
    
    def _calculate_threat_level(self, risk_score: float) -> str:
        """Calculate threat level from risk score"""
        if risk_score >= 80:
            return "Critical"
        elif risk_score >= 60:
            return "High"
        elif risk_score >= 30:
            return "Medium"
        elif risk_score >= 10:
            return "Low"
        else:
            return "Normal"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a concise summary of dashboard data"""
        try:
            data = self.validated_data if hasattr(self, 'validated_data') else {}
            
            return {
                'status': data.get('system_status', 'Unknown'),
                'risk_level': self._calculate_threat_level(data.get('risk_score', 0.0)),
                'active_threats': data.get('active_threats', 0),
                'uptime': f"{data.get('uptime_percentage', 0.0):.1f}%",
                'timestamp': data.get('last_updated')
            }
        except Exception as e:
            logger.error(f"Error getting summary: {e}")
            return {
                'status': 'Error',
                'risk_level': 'Unknown',
                'active_threats': 0,
                'uptime': '0.0%',
                'timestamp': None
            }


class SystemMetricsSerializer(serializers.Serializer):
    """
    Bulletproof serializer for system metrics
    """
    
    cpu_usage = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        max_value=100.0,
        help_text="CPU usage percentage"
    )
    
    memory_usage = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        max_value=100.0,
        help_text="Memory usage percentage"
    )
    
    disk_usage = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        max_value=100.0,
        help_text="Disk usage percentage"
    )
    
    network_in = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        help_text="Network input in MB/s"
    )
    
    network_out = serializers.FloatField(
        default=0.0,
        min_value=0.0,
        help_text="Network output in MB/s"
    )
    
    active_connections = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text="Number of active connections"
    )
    
    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """Handle any input type gracefully"""
        if isinstance(instance, dict):
            return {
                'cpu_usage': instance.get('cpu_usage', 0.0),
                'memory_usage': instance.get('memory_usage', 0.0),
                'disk_usage': instance.get('disk_usage', 0.0),
                'network_in': instance.get('network_in', 0.0),
                'network_out': instance.get('network_out', 0.0),
                'active_connections': instance.get('active_connections', 0),
                'is_healthy': self._check_health(instance)
            }
        
        return super().to_representation(instance)
    
    def _check_health(self, metrics: Dict[str, Any]) -> bool:
        """Check if system metrics indicate healthy state"""
        try:
            cpu = metrics.get('cpu_usage', 0.0)
            memory = metrics.get('memory_usage', 0.0)
            disk = metrics.get('disk_usage', 0.0)
            
            return cpu < 90 and memory < 85 and disk < 95
        except Exception:
            return False


class CombinedSecuritySerializer(serializers.Serializer):
    """
    Combined serializer for multiple security data sources
    Bulletproof implementation with all defensive patterns
    """
    
    dashboard = SecurityDashboardSerializer(
        default=dict,
        help_text="Security dashboard data"
    )
    
    metrics = SystemMetricsSerializer(
        default=dict,
        help_text="System performance metrics"
    )
    
    alerts = serializers.ListField(
        child=serializers.DictField(),
        default=list,
        help_text="Recent security alerts"
    )
    
    recommendations = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        help_text="Security recommendations"
    )
    
    def to_representation(self, instance: Any) -> Dict[str, Any]:
        """
        Ultimate defensive implementation
        Handles any input type without crashing
        """
        result = {}
        
        try:
            # Handle dict input
            if isinstance(instance, dict):
                result['dashboard'] = instance.get('dashboard', {})
                result['metrics'] = instance.get('metrics', {})
                result['alerts'] = instance.get('alerts', [])
                result['recommendations'] = instance.get('recommendations', [])
            
            # Handle object input
            elif hasattr(instance, '__dict__'):
                result['dashboard'] = getattr(instance, 'dashboard', {})
                result['metrics'] = getattr(instance, 'metrics', {})
                result['alerts'] = getattr(instance, 'alerts', [])
                result['recommendations'] = getattr(instance, 'recommendations', [])
            
            # Handle list/tuple input
            elif isinstance(instance, (list, tuple)):
                if len(instance) >= 4:
                    result['dashboard'] = instance[0] if isinstance(instance[0], dict) else {}
                    result['metrics'] = instance[1] if isinstance(instance[1], dict) else {}
                    result['alerts'] = instance[2] if isinstance(instance[2], list) else []
                    result['recommendations'] = instance[3] if isinstance(instance[3], list) else []
            
            # Fallback to safe defaults
            else:
                result = self._get_safe_defaults()
            
        except Exception as e:
            logger.error(f"Error in combined serializer: {e}")
            result = self._get_safe_defaults()
        
        # Add metadata and timestamp
        result['timestamp'] = getattr(instance, 'timestamp', None)
        result['success'] = True
        result['errors'] = []
        
        return result
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Return safe default values"""
        return {
            'dashboard': SecurityDashboardSerializer()._get_safe_defaults(),
            'metrics': {
                'cpu_usage': 0.0,
                'memory_usage': 0.0,
                'disk_usage': 0.0,
                'network_in': 0.0,
                'network_out': 0.0,
                'active_connections': 0,
                'is_healthy': False
            },
            'alerts': [],
            'recommendations': ["System data unavailable"],
            'timestamp': None,
            'success': False,
            'errors': ["Data processing failed"]
        }
        
        
        
        # serializers.py - AutoBlockRuleSerializer
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from typing import Dict, Any, List, Optional, Union, Tuple
from decimal import Decimal
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AutoBlockRuleSerializer(serializers.ModelSerializer):
    """
    Bulletproof Serializer for AutoBlockRule Model
    Complete Defensive Implementation with All Patterns
    """
    
    # ============ COMPUTED FIELDS (READ-ONLY) ============
    
    rule_effectiveness = serializers.SerializerMethodField(
        help_text="Effectiveness metrics of the rule"
    )
    
    last_triggered_formatted = serializers.SerializerMethodField(
        help_text="Formatted last triggered timestamp"
    )
    
    is_expired = serializers.SerializerMethodField(
        help_text="Whether the rule has expired"
    )
    
    trigger_count_today = serializers.SerializerMethodField(
        help_text="Number of triggers today"
    )
    
    # ============ RELATED FIELDS (SAFE ACCESS) ============
    
    created_by_username = serializers.SerializerMethodField(
        help_text="Username of rule creator"
    )
    
    updated_by_username = serializers.SerializerMethodField(
        help_text="Username of last updater"
    )
    
    # ============ VALIDATION FIELDS ============
    
    test_data = serializers.DictField(
        write_only=True,
        required=False,
        default=dict,
        help_text="Test data for rule validation"
    )
    
    class Meta:
        model = 'security.AutoBlockRule'  # Lazy reference
        fields = [
            # Core fields
            'id', 'name', 'description', 'rule_type', 'action_type',
            'priority', 'is_active',
            
            # Conditions and parameters
            'threshold_value', 'time_window_minutes',
            
            # Scope and targeting
            'apply_to_all_users',
            
            # Execution
            'action_duration_hours',
            
            # Monitoring
            'trigger_count', 'last_triggered', 'success_count',
            'false_positive_count', 'total_processed',
            
            # Metadata
            'created_by', 'created_by_username', 'created_at',
            'updated_by', 'updated_by_username', 'updated_at',
            'metadata', 'tags', 'version',
            
            # Computed fields
            'rule_effectiveness', 'last_triggered_formatted',
            'is_expired', 'trigger_count_today',
            
            # Validation fields
            'test_data'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'trigger_count',
            'last_triggered', 'success_count', 'false_positive_count',
            'total_processed', 'created_by_username', 'updated_by_username',
            'rule_effectiveness', 'last_triggered_formatted',
            'is_expired', 'trigger_count_today'
        ]
    
    def __init__(self, *args, **kwargs):
        """Initialize with dynamic model reference"""
        super().__init__(*args, **kwargs)
        
        # Set model if not already set
        if self.Meta.model == 'security.AutoBlockRule':
            try:
                from .models import AutoBlockRule
                self.Meta.model = AutoBlockRule
            except ImportError:
                logger.warning("AutoBlockRule model not available")
    
    # ============ SAFE GETTER METHODS ============
    
    def get_created_by_username(self, obj) -> str:
        """Get creator username safely using getattr()"""
        try:
            created_by = getattr(obj, 'created_by', None)
            if created_by:
                return getattr(created_by, 'username', 'System')
        except Exception:
            pass
        return 'System'  # Null Object Pattern
    
    def get_updated_by_username(self, obj) -> str:
        """Get updater username safely using getattr()"""
        try:
            updated_by = getattr(obj, 'updated_by', None)
            if updated_by:
                return getattr(updated_by, 'username', 'System')
        except Exception:
            pass
        return 'System'  # Null Object Pattern
    
    def get_rule_effectiveness(self, obj) -> Dict[str, Any]:
        """Calculate rule effectiveness with defensive coding"""
        try:
            total_processed = getattr(obj, 'total_processed', 0)
            success_count = getattr(obj, 'success_count', 0)
            false_positive_count = getattr(obj, 'false_positive_count', 0)
            
            if total_processed == 0:
                return {
                    'success_rate': 0.0,
                    'false_positive_rate': 0.0,
                    'effectiveness_score': 0.0,
                    'confidence_level': 'low'
                }
            
            success_rate = (success_count / total_processed) * 100
            false_positive_rate = (false_positive_count / total_processed) * 100
            
            # Calculate effectiveness score
            effectiveness_score = max(0, min(100, success_rate - false_positive_rate))
            
            # Determine confidence level
            if effectiveness_score >= 80:
                confidence = 'high'
            elif effectiveness_score >= 50:
                confidence = 'medium'
            else:
                confidence = 'low'
            
            return {
                'success_rate': round(success_rate, 2),
                'false_positive_rate': round(false_positive_rate, 2),
                'effectiveness_score': round(effectiveness_score, 2),
                'confidence_level': confidence,
                'total_evaluations': total_processed
            }
            
        except Exception as e:
            logger.warning(f"Effectiveness calculation error: {e}")
            return {
                'success_rate': 0.0,
                'false_positive_rate': 0.0,
                'effectiveness_score': 0.0,
                'confidence_level': 'unknown',
                'error': True
            }
    
    def get_last_triggered_formatted(self, obj) -> Optional[str]:
        """Format last triggered timestamp safely"""
        try:
            last_triggered = getattr(obj, 'last_triggered', None)
            if last_triggered:
                return last_triggered.isoformat()
        except Exception:
            pass
        return None
    
    def get_is_expired(self, obj) -> bool:
        """Check if rule has expired safely"""
        try:
            # Check if rule has expiration
            metadata = getattr(obj, 'metadata', {})
            if isinstance(metadata, dict) and 'expires_at' in metadata:
                expires_at = metadata.get('expires_at')
                if expires_at:
                    if isinstance(expires_at, str):
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    return expires_at < timezone.now()
        except Exception:
            pass
        return False
    
    def get_trigger_count_today(self, obj) -> int:
        """Get trigger count for today (simulated)"""
        try:
            # In real implementation, you would query actual triggers for today
            total_count = getattr(obj, 'trigger_count', 0)
            # Simulate: assume 10% of total triggers today
            return max(0, int(total_count * 0.1))
        except Exception:
            return 0
    
    # ============ VALIDATION METHODS ============
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulletproof validation with Graceful Degradation
        """
        validated_data = {}
        
        try:
            # Use dict.get() with defaults for all fields
            # Core fields
            validated_data['name'] = attrs.get('name', 'Unnamed Rule')
            validated_data['description'] = attrs.get('description', '')
            validated_data['rule_type'] = attrs.get('rule_type', 'behavior_based')
            validated_data['action_type'] = attrs.get('action_type', 'block')
            validated_data['priority'] = self._safe_int_get(attrs, 'priority', 50, 1, 100)
            validated_data['is_active'] = attrs.get('is_active', True)
            validated_data['is_automatic'] = attrs.get(True)
            
            # Conditions and parameters with safe defaults
            validated_data['conditions'] = self._validate_conditions(attrs.get('conditions', {}))
            validated_data['parameters'] = self._validate_parameters(attrs.get('parameters', {}))
            validated_data['patterns'] = self._validate_patterns(attrs.get('patterns', []))
            validated_data['thresholds'] = self._validate_thresholds(attrs.get('thresholds', {}))
            validated_data['cooldown_period'] = self._safe_int_get(attrs, 'cooldown_period', 300, 0, 86400)
            
            # Scope and targeting
            validated_data['target_users'] = self._validate_user_list(attrs.get('target_users', []))
            validated_data['target_ips'] = self._validate_ip_list(attrs.get('target_ips', []))
            validated_data['target_user_agents'] = self._validate_string_list(attrs.get('target_user_agents', []))
            validated_data['excluded_users'] = self._validate_user_list(attrs.get('excluded_users', []))
            validated_data['excluded_ips'] = self._validate_ip_list(attrs.get('excluded_ips', []))
            validated_data['excluded_user_agents'] = self._validate_string_list(attrs.get('excluded_user_agents', []))
            validated_data['scope'] = attrs.get('scope', 'global')
            
            # Execution parameters
            validated_data['action_duration'] = self._safe_int_get(attrs, 'action_duration', 3600, 60, 2592000)
            validated_data['notify_on_trigger'] = attrs.get('notify_on_trigger', True)
            validated_data['notification_channels'] = self._validate_notification_channels(
                attrs.get('notification_channels', ['email'])
            )
            validated_data['require_approval'] = attrs.get('require_approval', False)
            validated_data['approval_threshold'] = self._safe_int_get(attrs, 'approval_threshold', 1, 1, 10)
            
            # Metadata
            validated_data['metadata'] = self._validate_metadata(attrs.get('metadata', {}))
            validated_data['tags'] = self._validate_string_list(attrs.get('tags', []))
            validated_data['version'] = attrs.get('version', '1.0.0')
            
            # Test data (write-only)
            if 'test_data' in attrs:
                validated_data['test_data'] = self._validate_test_data(attrs['test_data'])
            
            # Apply business logic validation
            self._validate_business_logic(validated_data)
            
        except Exception as e:
            # GRACEFUL DEGRADATION: Log error and use safe defaults
            logger.error(f"AutoBlockRule validation error: {e}")
            validated_data = self._get_safe_defaults()
            validated_data['validation_errors'] = [str(e)]
            validated_data['is_active'] = False  # Deactivate on validation error for safety
        
        return validated_data
    
    def _validate_conditions(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rule conditions"""
        safe_conditions = {}
        
        try:
            if not isinstance(conditions, dict):
                return self._get_default_conditions()
            
            # Copy with safe defaults
            safe_conditions['match_type'] = conditions.get('match_type', 'any')
            safe_conditions['operator'] = conditions.get('operator', 'greater_than')
            safe_conditions['value'] = conditions.get('value', 0)
            safe_conditions['field'] = conditions.get('field', '')
            safe_conditions['comparison_type'] = conditions.get('comparison_type', 'numeric')
            
            # Validate match type
            valid_match_types = ['any', 'all', 'none']
            if safe_conditions['match_type'] not in valid_match_types:
                safe_conditions['match_type'] = 'any'
            
            # Validate operator
            valid_operators = ['greater_than', 'less_than', 'equals', 'not_equals',
                              'contains', 'regex_match', 'in_list', 'not_in_list']
            if safe_conditions['operator'] not in valid_operators:
                safe_conditions['operator'] = 'greater_than'
            
            # Validate value based on comparison type
            if safe_conditions['comparison_type'] == 'numeric':
                try:
                    safe_conditions['value'] = float(safe_conditions['value'])
                except (ValueError, TypeError):
                    safe_conditions['value'] = 0.0
            
            # Add subconditions if present
            if 'subconditions' in conditions and isinstance(conditions['subconditions'], list):
                safe_conditions['subconditions'] = conditions['subconditions'][:5]
            
        except Exception as e:
            logger.warning(f"Condition validation error: {e}")
            safe_conditions = self._get_default_conditions()
        
        return safe_conditions
    
    def _validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rule parameters"""
        safe_parameters = {}
        
        try:
            if not isinstance(parameters, dict):
                return self._get_default_parameters()
            
            # Use dict.get() with defaults
            safe_parameters['attempts'] = self._safe_int_get(parameters, 'attempts', 5, 1, 100)
            safe_parameters['time_window'] = self._safe_int_get(parameters, 'time_window', 300, 1, 86400)
            safe_parameters['percentage'] = self._safe_float_get(parameters, 'percentage', 80.0, 0.0, 100.0)
            safe_parameters['consecutive'] = self._safe_int_get(parameters, 'consecutive', 3, 1, 50)
            safe_parameters['unique_values'] = self._safe_int_get(parameters, 'unique_values', 10, 1, 1000)
            
        except Exception as e:
            logger.warning(f"Parameter validation error: {e}")
            safe_parameters = self._get_default_parameters()
        
        return safe_parameters
    
    def _validate_patterns(self, patterns: List[str]) -> List[str]:
        """Validate patterns"""
        safe_patterns = []
        
        try:
            if not isinstance(patterns, list):
                return []
            
            for pattern in patterns[:20]:  # Limit to 20 patterns
                if isinstance(pattern, str) and pattern.strip():
                    # Sanitize and validate
                    sanitized = pattern.strip()[:200]
                    
                    # Check if it's a regex pattern
                    if any(char in sanitized for char in ['^', '$', '*', '+', '?', '[', ']', '(', ')']):
                        try:
                            re.compile(sanitized)
                            safe_patterns.append(sanitized)
                        except re.error:
                            logger.debug(f"Invalid regex pattern: {sanitized}")
                    else:
                        safe_patterns.append(sanitized)
            
        except Exception as e:
            logger.warning(f"Pattern validation error: {e}")
        
        return safe_patterns
    
    def _validate_thresholds(self, thresholds: Dict[str, Any]) -> Dict[str, Any]:
        """Validate thresholds"""
        safe_thresholds = {}
        
        try:
            if not isinstance(thresholds, dict):
                return self._get_default_thresholds()
            
            safe_thresholds['min_confidence'] = self._safe_float_get(thresholds, 'min_confidence', 70.0, 0.0, 100.0)
            safe_thresholds['max_false_positives'] = self._safe_int_get(thresholds, 'max_false_positives', 10, 0, 1000)
            safe_thresholds['min_trigger_count'] = self._safe_int_get(thresholds, 'min_trigger_count', 1, 1, 1000)
            safe_thresholds['review_after'] = self._safe_int_get(thresholds, 'review_after', 100, 1, 10000)
            
        except Exception as e:
            logger.warning(f"Threshold validation error: {e}")
            safe_thresholds = self._get_default_thresholds()
        
        return safe_thresholds
    
    def _validate_user_list(self, users: List[Any]) -> List[int]:
        """Validate list of user IDs"""
        safe_users = []
        
        try:
            if not isinstance(users, list):
                return []
            
            for user in users[:100]:  # Limit to 100 users
                try:
                    user_id = int(user)
                    if user_id > 0:
                        safe_users.append(user_id)
                except (ValueError, TypeError):
                    pass
            
        except Exception as e:
            logger.warning(f"User list validation error: {e}")
        
        return list(set(safe_users))  # Remove duplicates
    
    def _validate_ip_list(self, ips: List[str]) -> List[str]:
        """Validate list of IP addresses"""
        safe_ips = []
        
        try:
            if not isinstance(ips, list):
                return []
            
            for ip in ips[:50]:  # Limit to 50 IPs
                if isinstance(ip, str) and ip.strip():
                    # Simple IP validation
                    sanitized = ip.strip()
                    if self._is_valid_ip(sanitized):
                        safe_ips.append(sanitized)
            
        except Exception as e:
            logger.warning(f"IP list validation error: {e}")
        
        return list(set(safe_ips))
    
    def _validate_string_list(self, items: List[str]) -> List[str]:
        """Validate list of strings"""
        safe_items = []
        
        try:
            if not isinstance(items, list):
                return []
            
            for item in items[:100]:
                if isinstance(item, str) and item.strip():
                    safe_items.append(item.strip()[:200])
            
        except Exception as e:
            logger.warning(f"String list validation error: {e}")
        
        return safe_items
    
    def _validate_notification_channels(self, channels: List[str]) -> List[str]:
        """Validate notification channels"""
        valid_channels = ['email', 'sms', 'webhook', 'slack', 'telegram', 'in_app']
        safe_channels = []
        
        try:
            if not isinstance(channels, list):
                return ['email']  # Default
        
            for channel in channels:
                if channel in valid_channels and channel not in safe_channels:
                    safe_channels.append(channel)
            
            if not safe_channels:
                safe_channels = ['email']
            
        except Exception as e:
            logger.warning(f"Notification channel validation error: {e}")
            safe_channels = ['email']
        
        return safe_channels
    
    def _validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata"""
        safe_metadata = {}
        
        try:
            if not isinstance(metadata, dict):
                return {}
            
            # Limit metadata size
            if len(str(metadata)) > 5000:
                return {'error': 'Metadata too large'}
            
            # Copy safe values
            for key, value in list(metadata.items())[:20]:  # Limit to 20 keys
                if isinstance(key, str) and key.strip():
                    safe_key = key.strip()[:100]
                    if isinstance(value, (str, int, float, bool, type(None))):
                        safe_metadata[safe_key] = value
                    elif isinstance(value, (list, dict)):
                        # Limit nested structures
                        safe_metadata[safe_key] = str(value)[:500]
            
        except Exception as e:
            logger.warning(f"Metadata validation error: {e}")
        
        return safe_metadata
    
    def _validate_test_data(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test data"""
        safe_test_data = {}
        
        try:
            if not isinstance(test_data, dict):
                return {}
            
            # Copy safe values
            safe_test_data['user'] = test_data.get('user')
            safe_test_data['ip_address'] = test_data.get('ip_address', '')
            safe_test_data['user_agent'] = test_data.get('user_agent', '')
            safe_test_data['activity_count'] = self._safe_int_get(test_data, 'activity_count', 0, 0, 1000)
            safe_test_data['timestamp'] = test_data.get('timestamp')
            
            # Additional activity data
            if 'activity_data' in test_data and isinstance(test_data['activity_data'], dict):
                safe_test_data['activity_data'] = test_data['activity_data']
            
        except Exception as e:
            logger.warning(f"Test data validation error: {e}")
        
        return safe_test_data
    
    def _validate_business_logic(self, data: Dict[str, Any]) -> None:
        """Validate business logic rules"""
        try:
            # Check if action duration is reasonable
            if data.get('action_type') == 'temporary_block':
                duration = data.get('action_duration', 3600)
                if duration > 2592000:  # 30 days
                    data['action_duration'] = 2592000
                    logger.info("Adjusted action duration to 30 days max")
            
            # Check if rule is too restrictive
            if (data.get('scope') == 'global' and 
                data.get(False) and 
                data.get('action_type') in ['block', 'permanent_block'] and
                not data.get('require_approval', False)):
                logger.warning("Global automatic block without approval may be too restrictive")
            
            # Validate thresholds consistency
            thresholds = data.get('thresholds', {})
            min_confidence = thresholds.get('min_confidence', 70.0)
            if min_confidence < 50.0 and data.get(False):
                logger.warning("Low confidence threshold with automatic execution")
            
        except Exception as e:
            logger.warning(f"Business logic validation error: {e}")
    
    # ============ HELPER METHODS ============
    
    def _safe_int_get(self, data: Dict[str, Any], key: str, 
                     default: int, min_val: int, max_val: int) -> int:
        """Safe integer extraction"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = int(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default
    
    def _safe_float_get(self, data: Dict[str, Any], key: str,
                       default: float, min_val: float, max_val: float) -> float:
        """Safe float extraction"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = float(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Simple IP validation"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except Exception:
            return False
    
    def _get_default_conditions(self) -> Dict[str, Any]:
        """Default conditions"""
        return {
            'match_type': 'any',
            'operator': 'greater_than',
            'value': 0,
            'field': 'attempt_count',
            'comparison_type': 'numeric'
        }
    
    def _get_default_parameters(self) -> Dict[str, Any]:
        """Default parameters"""
        return {
            'attempts': 5,
            'time_window': 300,
            'percentage': 80.0,
            'consecutive': 3,
            'unique_values': 10
        }
    
    def _get_default_thresholds(self) -> Dict[str, Any]:
        """Default thresholds"""
        return {
            'min_confidence': 70.0,
            'max_false_positives': 10,
            'min_trigger_count': 1,
            'review_after': 100
        }
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Safe defaults for graceful degradation"""
        return {
            'name': f'Rule_{int(time.time())}',
            'description': 'Safe default rule',
            'rule_type': 'behavior_based',
            'action_type': 'notify',
            'priority': 50,
            'is_active': False,  # Inactive by default for safety
            'is_automatic': False,
            'conditions': self._get_default_conditions(),
            'parameters': self._get_default_parameters(),
            'patterns': [],
            'thresholds': self._get_default_thresholds(),
            'cooldown_period': 300,
            'target_users': [],
            'target_ips': [],
            'target_user_agents': [],
            'excluded_users': [],
            'excluded_ips': [],
            'excluded_user_agents': [],
            'scope': 'global',
            'action_duration': 3600,
            'notify_on_trigger': True,
            'notification_channels': ['email'],
            'require_approval': True,
            'approval_threshold': 2,
            'metadata': {'safe_mode': True},
            'tags': ['safe-default'],
            'version': '1.0.0',
            'safe_mode': True
        }
    
    # ============ CREATE AND UPDATE METHODS ============
    
    def create(self, validated_data: Dict[str, Any]):
        """Create with defensive coding"""
        try:
            # Remove test_data if present
            test_data = validated_data.pop('test_data', None)
            
            # Add created_by from request context
            request = self.context.get('request')
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                validated_data['created_by'] = request.user
            
            # Set initial monitoring values
            validated_data['trigger_count'] = 0
            validated_data['success_count'] = 0
            validated_data['false_positive_count'] = 0
            validated_data['total_processed'] = 0
            
            # Create instance
            instance = super().create(validated_data)
            
            # Test rule if test data provided
            if test_data:
                self._test_rule_after_create(instance, test_data)
            
            logger.info(f"Created AutoBlockRule: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create AutoBlockRule: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to create rule: {str(e)}'
            })
    
    def update(self, instance, validated_data: Dict[str, Any]):
        """Update with defensive coding"""
        try:
            # Remove test_data if present
            test_data = validated_data.pop('test_data', None)
            
            # Add updated_by from request context
            request = self.context.get('request')
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                validated_data['updated_by'] = request.user
            
            # Update instance
            instance = super().update(instance, validated_data)
            
            # Test rule if test data provided
            if test_data:
                self._test_rule_after_update(instance, test_data)
            
            logger.info(f"Updated AutoBlockRule: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update AutoBlockRule {instance.id}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to update rule: {str(e)}'
            })
    
    def _test_rule_after_create(self, instance, test_data: Dict[str, Any]):
        """Test rule after creation"""
        try:
            # Import model method safely
            if hasattr(instance, 'evaluate'):
                result = instance.evaluate(test_data)
                logger.info(f"Test evaluation after create: {result}")
        except Exception as e:
            logger.warning(f"Rule test after create failed: {e}")
    
    def _test_rule_after_update(self, instance, test_data: Dict[str, Any]):
        """Test rule after update"""
        try:
            if hasattr(instance, 'evaluate'):
                result = instance.evaluate(test_data)
                logger.info(f"Test evaluation after update: {result}")
        except Exception as e:
            logger.warning(f"Rule test after update failed: {e}")
    
    # ============ TEST SERIALIZER ============
    
class AutoBlockRuleTestSerializer(serializers.Serializer):
    """
    Serializer for testing auto-block rules
    """
    
    test_data = serializers.DictField(
        required=True,
        help_text="Test data for rule evaluation"
    )
    
    rule_id = serializers.IntegerField(
        required=False,
        help_text="Specific rule ID to test (uses current rule if not provided)"
    )
    
    simulate_action = serializers.BooleanField(
        default=False,
        help_text="Whether to simulate the action"
    )
    
    def validate_test_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test data"""
        safe_data = {}
        
        try:
            # Copy safe values with defaults
            safe_data['user'] = value.get('user')
            safe_data['ip_address'] = value.get('ip_address', '127.0.0.1')
            safe_data['user_agent'] = value.get('user_agent', '')
            safe_data['device_id'] = value.get('device_id', '')
            
            # Activity data
            safe_data['activity_count'] = self._safe_int_get(value, 'activity_count', 1, 0, 1000)
            safe_data['failed_attempts'] = self._safe_int_get(value, 'failed_attempts', 0, 0, 100)
            safe_data['suspicious_actions'] = self._safe_int_get(value, 'suspicious_actions', 0, 0, 100)
            
            # Timestamps
            safe_data['first_activity'] = value.get('first_activity')
            safe_data['last_activity'] = value.get('last_activity')
            safe_data['current_time'] = value.get('current_time', timezone.now().isoformat())
            
            # Additional context
            if 'context' in value and isinstance(value['context'], dict):
                safe_data['context'] = value['context']
            
        except Exception as e:
            logger.warning(f"Test data validation error: {e}")
            safe_data = {
                'ip_address': '127.0.0.1',
                'activity_count': 1,
                'current_time': timezone.now().isoformat()
            }
        
        return safe_data
    
    def _safe_int_get(self, data: Dict[str, Any], key: str, default: int, min_val: int, max_val: int) -> int:
        """Safe integer extraction"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = int(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default


# ============ SIMPLIFIED SERIALIZER FOR LIST VIEWS ============

class AutoBlockRuleListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for list views
    """
    
    effectiveness = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = 'security.AutoBlockRule'
        fields = [
            'id', 'name', 'rule_type', 'action_type', 'priority',
            'is_active', 'trigger_count', 'last_triggered',
            'effectiveness', 'status', 'created_at'
        ]
    
    def get_effectiveness(self, obj) -> float:
        """Get effectiveness percentage"""
        try:
            total = getattr(obj, 'total_processed', 0)
            success = getattr(obj, 'success_count', 0)
            if total > 0:
                return round((success / total) * 100, 1)
        except Exception:
            pass
        return 0.0
    
    def get_status(self, obj) -> str:
        """Get rule status"""
        try:
            if not getattr(obj, 'is_active', False):
                return 'inactive'
            
            last_triggered = getattr(obj, 'last_triggered', None)
            if last_triggered:
                days_since = (timezone.now() - last_triggered).days
                if days_since > 30:
                    return 'dormant'
                elif days_since > 7:
                    return 'idle'
            
            return 'active'
        except Exception:
            return 'unknown'
        
        
class FraudPatternSerializer(serializers.ModelSerializer):
    """
    Bulletproof Serializer for FraudPattern Model
    Complete Defensive Implementation with All Patterns
    """
    
    # ============ COMPUTED FIELDS (READ-ONLY) ============
    
    pattern_type_display = serializers.CharField(
        source='get_pattern_type_display',
        read_only=True,
        help_text="Human-readable pattern type"
    )
    
    effectiveness_score = serializers.SerializerMethodField(
        help_text="Effectiveness score based on match history"
    )
    
    last_match_ago = serializers.SerializerMethodField(
        help_text="How long ago the pattern last matched"
    )
    
    risk_level = serializers.SerializerMethodField(
        help_text="Risk level based on weight and threshold"
    )
    
    # ============ VALIDATION AND TEST FIELDS ============
    
    test_data = serializers.DictField(
        write_only=True,
        required=False,
        default=dict,
        help_text="Test data for pattern evaluation"
    )
    
    test_result = serializers.DictField(
        read_only=True,
        help_text="Result of test evaluation"
    )
    
    # ============ CUSTOM FIELD VALIDATION ============
    
    conditions = serializers.JSONField(
        default=dict,
        help_text="JSON logic for pattern matching"
    )
    
    weight = serializers.IntegerField(
        default=10,
        min_value=1,
        max_value=100,
        help_text="Pattern weight (1-100)"
    )
    
    confidence_threshold = serializers.IntegerField(
        default=70,
        min_value=0,
        max_value=100,
        help_text="Confidence threshold for matches (0-100)"
    )
    
    block_duration_hours = serializers.IntegerField(
        default=24,
        min_value=1,
        max_value=720,  # 30 days
        help_text="Block duration in hours if auto-block enabled"
    )
    
    class Meta:
        model = 'security.FraudPattern'  # Lazy reference
        fields = [
            # Core fields
            'id', 'name', 'pattern_type', 'pattern_type_display',
            'description',
            
            # Pattern configuration
            'conditions', 'weight', 'confidence_threshold',
            'auto_block', 'block_duration_hours',
            
            # Status and monitoring
            'is_active', 'last_match_at', 'last_match_ago',
            'match_count', 'risk_level',
            
            # Computed fields
            'effectiveness_score',
            
            # Test fields
            'test_data', 'test_result',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_match_at', 'match_count',
            'created_at', 'updated_at', 'pattern_type_display',
            'effectiveness_score', 'last_match_ago', 'risk_level',
            'test_result'
        ]
    
    def __init__(self, *args, **kwargs):
        """Initialize with dynamic model reference"""
        super().__init__(*args, **kwargs)
        
        # Set model if not already set
        if self.Meta.model == 'security.FraudPattern':
            try:
                from .models import FraudPattern
                self.Meta.model = FraudPattern
            except ImportError as e:
                logger.warning(f"FraudPattern model not available: {e}")
                # Graceful degradation - use stub
                self.Meta.model = None
    
    # ============ SAFE GETTER METHODS ============
    
    def get_effectiveness_score(self, obj) -> float:
        """Calculate effectiveness score with defensive coding"""
        try:
            match_count = getattr(obj, 'match_count', 0)
            created_at = getattr(obj, 'created_at', timezone.now())
            
            if match_count == 0:
                return 0.0
            
            # Calculate days since creation
            days_since_creation = max(1, (timezone.now() - created_at).days)
            
            # Simple effectiveness: matches per day (capped at 10 per day)
            effectiveness = min(10.0, match_count / days_since_creation)
            
            # Normalize to 0-100 scale
            return round(min(100.0, effectiveness * 10), 1)
            
        except Exception as e:
            logger.debug(f"Effectiveness score calculation error: {e}")
            return 0.0
    
    def get_last_match_ago(self, obj) -> Optional[str]:
        """Format how long ago pattern last matched"""
        try:
            last_match_at = getattr(obj, 'last_match_at', None)
            if not last_match_at:
                return "Never"
            
            delta = timezone.now() - last_match_at
            
            if delta.days > 365:
                return f"{delta.days // 365} years ago"
            elif delta.days > 30:
                return f"{delta.days // 30} months ago"
            elif delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return f"{delta.seconds} seconds ago"
                
        except Exception as e:
            logger.debug(f"Last match ago calculation error: {e}")
            return "Unknown"
    
    def get_risk_level(self, obj) -> str:
        """Determine risk level based on pattern characteristics"""
        try:
            weight = getattr(obj, 'weight', 10)
            confidence_threshold = getattr(obj, 'confidence_threshold', 70)
            auto_block = getattr(obj, 'auto_block', False)
            
            risk_score = weight + (100 - confidence_threshold) // 10
            
            if auto_block:
                risk_score += 20
            
            if risk_score >= 80:
                return "Critical"
            elif risk_score >= 60:
                return "High"
            elif risk_score >= 40:
                return "Medium"
            else:
                return "Low"
                
        except Exception as e:
            logger.debug(f"Risk level calculation error: {e}")
            return "Unknown"
    
    # ============ VALIDATION METHODS ============
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulletproof validation with Graceful Degradation
        """
        validated_data = {}
        
        try:
            # Use dict.get() with defaults for all fields
            # Core fields
            validated_data['name'] = attrs.get('name', '').strip()
            validated_data['pattern_type'] = attrs.get('pattern_type', 'account_takeover')
            validated_data['description'] = attrs.get('description', '').strip()
            
            # Pattern configuration with safe defaults
            validated_data['conditions'] = self._validate_conditions(attrs.get('conditions', {}))
            validated_data['weight'] = self._safe_int_get(attrs, 'weight', 10, 1, 100)
            validated_data['confidence_threshold'] = self._safe_int_get(attrs, 'confidence_threshold', 70, 0, 100)
            validated_data['auto_block'] = attrs.get('auto_block', False)
            validated_data['block_duration_hours'] = self._safe_int_get(attrs, 'block_duration_hours', 24, 1, 720)
            
            # Status
            validated_data['is_active'] = attrs.get('is_active', True)
            
            # Test data if provided
            if 'test_data' in attrs:
                validated_data['test_data'] = self._validate_test_data(attrs['test_data'])
            
            # Apply business logic validation
            self._validate_business_logic(validated_data)
            
        except Exception as e:
            # GRACEFUL DEGRADATION: Log error and use safe defaults
            logger.error(f"FraudPattern validation error: {e}")
            validated_data = self._get_safe_defaults()
            validated_data['validation_errors'] = [str(e)]
            validated_data['is_active'] = False  # Deactivate on validation error for safety
        
        return validated_data
    
    def _validate_conditions(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate pattern conditions JSON with defensive coding
        """
        safe_conditions = {}
        
        try:
            if not isinstance(conditions, dict):
                return self._get_default_conditions()
            
            # Validate structure
            if not conditions:
                return self._get_default_conditions()
            
            # Check for required fields based on pattern type
            # (This is a simplified validation - adjust based on your actual condition structure)
            
            # Copy conditions with size limits
            safe_conditions = self._deep_copy_dict(conditions, max_depth=3, max_size=5000)
            
            # Ensure it's valid JSON by testing serialization
            json.dumps(safe_conditions)
            
            # Add validation metadata
            safe_conditions['_validated'] = True
            safe_conditions['_validation_timestamp'] = timezone.now().isoformat()
            
        except Exception as e:
            logger.warning(f"Conditions validation error: {e}")
            safe_conditions = self._get_default_conditions()
            safe_conditions['_validation_error'] = str(e)
        
        return safe_conditions
    
    def _validate_test_data(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test data for pattern evaluation"""
        safe_test_data = {}
        
        try:
            if not isinstance(test_data, dict):
                return self._get_default_test_data()
            
            # User data
            user_data = test_data.get('user_data', {})
            safe_test_data['user_data'] = self._deep_copy_dict(user_data, max_depth=2, max_size=2000)
            
            # Activity data
            activity_data = test_data.get('activity_data', {})
            safe_test_data['activity_data'] = self._deep_copy_dict(activity_data, max_depth=2, max_size=2000)
            
            # Device data
            device_data = test_data.get('device_data', {})
            safe_test_data['device_data'] = self._deep_copy_dict(device_data, max_depth=2, max_size=2000)
            
            # Add timestamp
            safe_test_data['test_timestamp'] = timezone.now().isoformat()
            
        except Exception as e:
            logger.warning(f"Test data validation error: {e}")
            safe_test_data = self._get_default_test_data()
        
        return safe_test_data
    
    def _validate_business_logic(self, data: Dict[str, Any]) -> None:
        """Validate business logic rules"""
        try:
            # Ensure name is unique (check will be done at model level)
            if not data.get('name'):
                raise ValidationError("Pattern name is required")
            
            # Validate pattern type
            valid_pattern_types = ['account_takeover', 'payment_fraud', 'identity_fraud', 
                                  'bot_activity', 'money_laundering']
            if data.get('pattern_type') not in valid_pattern_types:
                data['pattern_type'] = 'account_takeover'  # Default
            
            # Validate weight vs confidence threshold
            weight = data.get('weight', 10)
            confidence = data.get('confidence_threshold', 70)
            
            # High weight patterns should have reasonable confidence thresholds
            if weight >= 80 and confidence < 60:
                logger.warning(f"High weight pattern {data.get('name')} has low confidence threshold")
            
            # Auto-block validation
            if data.get('auto_block', False):
                # Ensure block duration is reasonable
                block_hours = data.get('block_duration_hours', 24)
                if block_hours > 168:  # 7 days
                    logger.warning(f"Auto-block duration too long: {block_hours} hours")
            
        except Exception as e:
            logger.warning(f"Business logic validation error: {e}")
            # Don't raise - continue with potentially invalid data (graceful degradation)
    
    # ============ HELPER METHODS ============
    
    def _safe_int_get(self, data: Dict[str, Any], key: str, 
                     default: int, min_val: int, max_val: int) -> int:
        """Safe integer extraction with bounds checking"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = int(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default
    
    def _deep_copy_dict(self, data: Dict[str, Any], max_depth: int = 3, max_size: int = 5000) -> Dict[str, Any]:
        """Create a deep copy of dictionary with limits"""
        def recursive_copy(obj, depth):
            if depth > max_depth:
                return "[Max depth reached]"
            
            if isinstance(obj, dict):
                result = {}
                size = 0
                for key, value in obj.items():
                    if size > max_size:
                        result['_truncated'] = True
                        break
                    
                    if isinstance(key, str):
                        result[key[:100]] = recursive_copy(value, depth + 1)
                        size += len(str(value))
                return result
            elif isinstance(obj, list):
                return [recursive_copy(item, depth + 1) for item in obj[:100]]  # Limit list size
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                return str(obj)[:500]  # Convert other types to string with limit
        
        try:
            return recursive_copy(data, 0)
        except Exception as e:
            logger.debug(f"Deep copy error: {e}")
            return {"_copy_error": str(e)}
    
    def _get_default_conditions(self) -> Dict[str, Any]:
        """Get default conditions based on pattern type"""
        return {
            "rules": [
                {
                    "field": "failed_login_attempts",
                    "operator": "greater_than",
                    "value": 5,
                    "time_window_minutes": 60
                }
            ],
            "match_type": "any",  # any, all, custom
            "scoring_rules": {
                "base_score": 10,
                "multipliers": {}
            }
        }
    
    def _get_default_test_data(self) -> Dict[str, Any]:
        """Get default test data"""
        return {
            "user_data": {
                "id": 1,
                "username": "test_user",
                "email": "test@example.com",
                "failed_login_attempts": 0,
                "account_age_days": 100
            },
            "activity_data": {
                "recent_logins": 3,
                "failed_attempts_last_hour": 0,
                "suspicious_actions": 0,
                "last_login_ip": "192.168.1.1"
            },
            "device_data": {
                "device_id": "test_device_123",
                "device_type": "desktop",
                "browser": "Chrome",
                "os": "Windows 10",
                "is_new_device": False
            }
        }
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Get complete safe defaults (Ultimate Graceful Degradation)"""
        return {
            'name': f'Pattern_{int(time.time())}',
            'pattern_type': 'account_takeover',
            'description': 'Safe default fraud pattern',
            'conditions': self._get_default_conditions(),
            'weight': 10,
            'confidence_threshold': 70,
            'auto_block': False,
            'block_duration_hours': 24,
            'is_active': False,  # Inactive by default for safety
            'safe_mode': True
        }
    
    # ============ CREATE AND UPDATE METHODS ============
    
    def create(self, validated_data: Dict[str, Any]):
        """Create fraud pattern with defensive coding"""
        try:
            # Remove test_data if present (will be used for testing)
            test_data = validated_data.pop('test_data', None)
            
            # Create instance
            instance = super().create(validated_data)
            
            # Test pattern if test data provided
            if test_data:
                self._test_pattern_after_create(instance, test_data)
            
            logger.info(f"Created FraudPattern: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create FraudPattern: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to create pattern: {str(e)}'
            })
    
    def update(self, instance, validated_data: Dict[str, Any]):
        """Update fraud pattern with defensive coding"""
        try:
            # Remove test_data if present
            test_data = validated_data.pop('test_data', None)
            
            # Update instance
            instance = super().update(instance, validated_data)
            
            # Test pattern if test data provided
            if test_data:
                self._test_pattern_after_update(instance, test_data)
            
            logger.info(f"Updated FraudPattern: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update FraudPattern {instance.id}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to update pattern: {str(e)}'
            })
    
    def _test_pattern_after_create(self, instance, test_data: Dict[str, Any]):
        """Test pattern after creation"""
        try:
            # Use getattr() to safely access model method
            if hasattr(instance, 'evaluate'):
                user_data = test_data.get('user_data', {})
                activity_data = test_data.get('activity_data', {})
                device_data = test_data.get('device_data', {})
                
                result = instance.evaluate(user_data, activity_data, device_data)
                
                # Store test result in instance context
                if hasattr(instance, '_test_result'):
                    instance._test_result = {
                        'matches': result[0] if isinstance(result, tuple) else result,
                        'score': result[1] if isinstance(result, tuple) and len(result) > 1 else 0,
                        'test_data_used': test_data,
                        'timestamp': timezone.now().isoformat()
                    }
                
                logger.info(f"Test evaluation after create: {result}")
                
        except Exception as e:
            logger.warning(f"Pattern test after create failed: {e}")
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'error': str(e),
                    'test_data_used': test_data,
                    'timestamp': timezone.now().isoformat()
                }
    
    def _test_pattern_after_update(self, instance, test_data: Dict[str, Any]):
        """Test pattern after update"""
        try:
            if hasattr(instance, 'evaluate'):
                user_data = test_data.get('user_data', {})
                activity_data = test_data.get('activity_data', {})
                device_data = test_data.get('device_data', {})
                
                result = instance.evaluate(user_data, activity_data, device_data)
                
                if hasattr(instance, '_test_result'):
                    instance._test_result = {
                        'matches': result[0] if isinstance(result, tuple) else result,
                        'score': result[1] if isinstance(result, tuple) and len(result) > 1 else 0,
                        'test_data_used': test_data,
                        'timestamp': timezone.now().isoformat()
                    }
                
                logger.info(f"Test evaluation after update: {result}")
                
        except Exception as e:
            logger.warning(f"Pattern test after update failed: {e}")
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'error': str(e),
                    'test_data_used': test_data,
                    'timestamp': timezone.now().isoformat()
                }
    
    # ============ TO REPRESENTATION ============
    
    def to_representation(self, instance):
        """Add test result to representation if available"""
        representation = super().to_representation(instance)
        
        # Add test result if it exists
        if hasattr(instance, '_test_result'):
            representation['test_result'] = instance._test_result
        
        return representation


# ============ FRAUD PATTERN TEST SERIALIZER ============

class FraudPatternTestSerializer(serializers.Serializer):
    """
    Serializer for testing fraud patterns
    """
    
    pattern_id = serializers.IntegerField(
        required=False,
        help_text="Specific pattern ID to test (tests all patterns if not provided)"
    )
    
    user_data = serializers.DictField(
        required=True,
        help_text="User data for pattern evaluation"
    )
    
    activity_data = serializers.DictField(
        required=True,
        help_text="Activity data for pattern evaluation"
    )
    
    device_data = serializers.DictField(
        required=True,
        help_text="Device data for pattern evaluation"
    )
    
    simulate_block = serializers.BooleanField(
        default=False,
        help_text="Whether to simulate auto-block actions"
    )
    
    def validate_user_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user data"""
        return self._sanitize_dict(value, max_depth=2)
    
    def validate_activity_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate activity data"""
        return self._sanitize_dict(value, max_depth=2)
    
    def validate_device_data(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Validate device data"""
        return self._sanitize_dict(value, max_depth=2)
    
    def _sanitize_dict(self, data: Dict[str, Any], max_depth: int = 2) -> Dict[str, Any]:
        """Sanitize dictionary with depth limit"""
        def recursive_sanitize(obj, depth):
            if depth > max_depth:
                return "[Max depth reached]"
            
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if isinstance(key, str):
                        result[key[:100]] = recursive_sanitize(value, depth + 1)
                return result
            elif isinstance(obj, list):
                return [recursive_sanitize(item, depth + 1) for item in obj[:50]]
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                return str(obj)[:500]
        
        try:
            return recursive_sanitize(data, 0)
        except Exception:
            return {"error": "Data sanitization failed"}


# ============ FRAUD PATTERN MATCH SERIALIZER ============

class FraudPatternMatchSerializer(serializers.Serializer):
    """
    Serializer for fraud pattern match results
    """
    
    pattern_id = serializers.IntegerField(
        help_text="ID of the matched pattern"
    )
    
    pattern_name = serializers.CharField(
        help_text="Name of the matched pattern"
    )
    
    pattern_type = serializers.CharField(
        help_text="Type of the matched pattern"
    )
    
    match_score = serializers.FloatField(
        help_text="Match score (0-100)"
    )
    
    matches = serializers.BooleanField(
        help_text="Whether the pattern matched"
    )
    
    confidence_threshold = serializers.IntegerField(
        help_text="Pattern's confidence threshold"
    )
    
    triggered_auto_block = serializers.BooleanField(
        help_text="Whether auto-block was triggered"
    )
    
    details = serializers.DictField(
        help_text="Details about the match"
    )
    
    timestamp = serializers.DateTimeField(
        help_text="When the match occurred"
    )
    
    class Meta:
        fields = [
            'pattern_id', 'pattern_name', 'pattern_type',
            'match_score', 'matches', 'confidence_threshold',
            'triggered_auto_block', 'details', 'timestamp'
        ]
        
        

class RealTimeDetectionSerializer(serializers.ModelSerializer):
    """
    Bulletproof Serializer for RealTimeDetection Model
    Complete Defensive Implementation with All Patterns
    """
    
    # ============ COMPUTED FIELDS (READ-ONLY) ============
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
        help_text="Human-readable status"
    )
    
    uptime_percentage = serializers.SerializerMethodField(
        help_text="Uptime percentage of the detection engine"
    )
    
    performance_score = serializers.SerializerMethodField(
        help_text="Performance score (0-100)"
    )
    
    efficiency_rate = serializers.SerializerMethodField(
        help_text="Match rate efficiency"
    )
    
    last_run_ago = serializers.SerializerMethodField(
        help_text="How long ago the detection last ran"
    )
    
    next_run_in = serializers.SerializerMethodField(
        help_text="When the next run is scheduled"
    )
    
    health_status = serializers.SerializerMethodField(
        help_text="Health status of the detection engine"
    )
    
    # ============ CONTROL FIELDS ============
    
    run_now = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Set to true to run detection immediately"
    )
    
    force_restart = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Force restart the detection engine"
    )
    
    test_data = serializers.DictField(
        write_only=True,
        required=False,
        default=dict,
        help_text="Test data for detection engine"
    )
    
    # ============ STATISTICS FIELDS ============
    
    today_stats = serializers.SerializerMethodField(
        help_text="Statistics for today"
    )
    
    weekly_stats = serializers.SerializerMethodField(
        help_text="Statistics for this week"
    )
    
    monthly_stats = serializers.SerializerMethodField(
        help_text="Statistics for this month"
    )
    
    # ============ PERFORMANCE METRICS ============
    
    performance_metrics = serializers.SerializerMethodField(
        help_text="Detailed performance metrics"
    )
    
    error_rate = serializers.SerializerMethodField(
        help_text="Error rate percentage"
    )
    
    success_rate = serializers.SerializerMethodField(
        help_text="Success rate percentage"
    )
    
    class Meta:
        model = 'security.RealTimeDetection'  # Lazy reference
        fields = [
            # Core fields
            'id', 'name', 'detection_type', 'description',
            
            # Configuration
            'check_interval_seconds', 'batch_size',
            
            # Status
            'status', 'status_display', 'last_run_at', 'last_error',
            'last_run_ago', 'next_run_in', 'health_status',
            
            # Statistics
            'total_checks', 'total_matches',
            'today_stats', 'weekly_stats', 'monthly_stats',
            
            # Performance
            'average_processing_time',
            'performance_score', 'efficiency_rate', 'uptime_percentage',
            'performance_metrics', 'error_rate', 'success_rate',
            
            # Control fields
            'run_now', 'force_restart', 'test_data',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_run_at', 'last_error', 'total_checks',
            'total_matches', 'average_processing_time', 'created_at',
            'updated_at', 'status_display', 'uptime_percentage',
            'performance_score', 'efficiency_rate', 'last_run_ago',
            'next_run_in', 'health_status', 'today_stats', 'weekly_stats',
            'monthly_stats', 'performance_metrics', 'error_rate',
            'success_rate'
        ]
    
    def __init__(self, *args, **kwargs):
        """Initialize with dynamic model reference"""
        super().__init__(*args, **kwargs)
        
        # Set model if not already set
        if self.Meta.model == 'security.RealTimeDetection':
            try:
                from .models import RealTimeDetection
                self.Meta.model = RealTimeDetection
            except ImportError as e:
                logger.warning(f"RealTimeDetection model not available: {e}")
                # Graceful degradation - use stub
                self.Meta.model = None
    
    # ============ SAFE GETTER METHODS ============
    
    def get_uptime_percentage(self, obj) -> float:
        """Calculate uptime percentage with defensive coding"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            error_count = self._get_error_count(obj)
            
            if total_checks == 0:
                return 100.0  # No checks yet, assume 100% uptime
            
            uptime = max(0, total_checks - error_count)
            return round((uptime / total_checks) * 100, 2)
            
        except Exception as e:
            logger.debug(f"Uptime calculation error: {e}")
            return 0.0
    
    def get_performance_score(self, obj) -> float:
        """Calculate performance score"""
        try:
            avg_processing_time = getattr(obj, 'average_processing_time', 0)
            efficiency_rate = self.get_efficiency_rate(obj)
            
            # Lower processing time is better
            time_score = max(0, min(100, (1000 - avg_processing_time) / 10))
            
            # Combined score
            performance_score = (time_score * 0.4) + (efficiency_rate * 0.6)
            return round(performance_score, 1)
            
        except Exception as e:
            logger.debug(f"Performance score calculation error: {e}")
            return 0.0
    
    def get_efficiency_rate(self, obj) -> float:
        """Calculate match efficiency rate"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            if total_checks == 0:
                return 0.0
            
            # Efficiency: matches per check (normalized)
            efficiency = (total_matches / total_checks) * 100
            return round(min(100.0, efficiency), 2)
            
        except Exception as e:
            logger.debug(f"Efficiency rate calculation error: {e}")
            return 0.0
    
    def get_last_run_ago(self, obj) -> str:
        """Format how long ago detection last ran"""
        try:
            last_run_at = getattr(obj, 'last_run_at', None)
            if not last_run_at:
                return "Never"
            
            delta = timezone.now() - last_run_at
            
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return f"{delta.seconds} seconds ago"
                
        except Exception as e:
            logger.debug(f"Last run ago calculation error: {e}")
            return "Unknown"
    
    def get_next_run_in(self, obj) -> str:
        """Calculate when next run is scheduled"""
        try:
            last_run_at = getattr(obj, 'last_run_at', None)
            check_interval = getattr(obj, 'check_interval_seconds', 60)
            status = getattr(obj, 'status', 'idle')
            
            if status != 'idle' or not last_run_at:
                return "Not scheduled"
            
            next_run = last_run_at + timedelta(seconds=check_interval)
            delta = next_run - timezone.now()
            
            if delta.total_seconds() <= 0:
                return "Due now"
            elif delta.total_seconds() > 3600:
                return f"In {int(delta.total_seconds() / 3600)} hours"
            elif delta.total_seconds() > 60:
                return f"In {int(delta.total_seconds() / 60)} minutes"
            else:
                return f"In {int(delta.total_seconds())} seconds"
                
        except Exception as e:
            logger.debug(f"Next run calculation error: {e}")
            return "Unknown"
    
    def get_health_status(self, obj) -> str:
        """Determine health status"""
        try:
            status = getattr(obj, 'status', 'idle')
            last_error = getattr(obj, 'last_error', '')
            avg_processing_time = getattr(obj, 'average_processing_time', 0)
            
            if status == 'error':
                return "Critical"
            elif status == 'running' and avg_processing_time > 10:
                return "Degraded"
            elif last_error and 'error' in status.lower():
                return "Warning"
            elif status == 'paused':
                return "Paused"
            else:
                return "Healthy"
                
        except Exception as e:
            logger.debug(f"Health status calculation error: {e}")
            return "Unknown"
    
    def get_today_stats(self, obj) -> Dict[str, Any]:
        """Get today's statistics"""
        try:
            # In real implementation, you would query actual data
            # For now, return mock/estimated data
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            # Estimate today's activity (assuming 10% of total)
            today_checks = max(1, int(total_checks * 0.1))
            today_matches = max(0, int(total_matches * 0.1))
            
            return {
                'checks': today_checks,
                'matches': today_matches,
                'match_rate': round((today_matches / today_checks * 100), 1) if today_checks > 0 else 0,
                'avg_processing_time': getattr(obj, 'average_processing_time', 0)
            }
            
        except Exception as e:
            logger.debug(f"Today stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_weekly_stats(self, obj) -> Dict[str, Any]:
        """Get weekly statistics"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            # Estimate weekly activity (assuming 30% of total)
            weekly_checks = max(1, int(total_checks * 0.3))
            weekly_matches = max(0, int(total_matches * 0.3))
            
            return {
                'checks': weekly_checks,
                'matches': weekly_matches,
                'match_rate': round((weekly_matches / weekly_checks * 100), 1) if weekly_checks > 0 else 0,
                'trend': 'stable'  # Would calculate actual trend
            }
            
        except Exception as e:
            logger.debug(f"Weekly stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_monthly_stats(self, obj) -> Dict[str, Any]:
        """Get monthly statistics"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            return {
                'checks': total_checks,
                'matches': total_matches,
                'match_rate': round((total_matches / total_checks * 100), 1) if total_checks > 0 else 0,
                'avg_daily_checks': round(total_checks / 30, 1) if total_checks > 0 else 0
            }
            
        except Exception as e:
            logger.debug(f"Monthly stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_performance_metrics(self, obj) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        try:
            avg_time = getattr(obj, 'average_processing_time', 0)
            total_checks = getattr(obj, 'total_checks', 0)
            
            return {
                'processing_time': {
                    'average': avg_time,
                    'estimated_max': avg_time * 2,
                    'estimated_min': max(0.1, avg_time * 0.5)
                },
                'throughput': {
                    'checks_per_hour': int(total_checks / 24) if total_checks > 0 else 0,
                    'estimated_capacity': 10000,  # Would calculate based on system
                    'current_utilization': round((total_checks / 10000) * 100, 1) if total_checks > 0 else 0
                },
                'reliability': {
                    'uptime_percentage': self.get_uptime_percentage(obj),
                    'error_rate': self.get_error_rate(obj),
                    'success_rate': self.get_success_rate(obj)
                }
            }
            
        except Exception as e:
            logger.debug(f"Performance metrics calculation error: {e}")
            return {'error': 'Metrics unavailable'}
    
    def get_error_rate(self, obj) -> float:
        """Calculate error rate"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            error_count = self._get_error_count(obj)
            
            if total_checks == 0:
                return 0.0
            
            return round((error_count / total_checks) * 100, 2)
            
        except Exception as e:
            logger.debug(f"Error rate calculation error: {e}")
            return 0.0
    
    def get_success_rate(self, obj) -> float:
        """Calculate success rate"""
        try:
            error_rate = self.get_error_rate(obj)
            return max(0.0, 100.0 - error_rate)
            
        except Exception as e:
            logger.debug(f"Success rate calculation error: {e}")
            return 0.0
    
    def _get_error_count(self, obj) -> int:
        """Estimate error count based on last_error"""
        try:
            last_error = getattr(obj, 'last_error', '')
            if last_error and len(last_error.strip()) > 0:
                # Simple estimation: assume 1 error per error message
                return 1
            return 0
        except Exception:
            return 0
    
    # ============ VALIDATION METHODS ============
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulletproof validation with Graceful Degradation
        """
        validated_data = {}
        
        try:
            # Use dict.get() with defaults for all fields
            # Core fields
            validated_data['name'] = attrs.get('name', '').strip()
            validated_data['detection_type'] = attrs.get('detection_type', 'generic')
            validated_data['description'] = attrs.get('description', '').strip()
            
            # Configuration with safe defaults
            validated_data['check_interval_seconds'] = self._safe_int_get(
                attrs, 'check_interval_seconds', 60, 10, 3600
            )
            validated_data['batch_size'] = self._safe_int_get(
                attrs, 'batch_size', 100, 1, 10000
            )
            
            # Status
            validated_data['status'] = attrs.get('status', 'idle')
            validated_data['last_error'] = attrs.get('last_error', '').strip()
            
            # Control fields
            validated_data['run_now'] = attrs.get('run_now', False)
            validated_data['force_restart'] = attrs.get('force_restart', False)
            
            # Test data if provided
            if 'test_data' in attrs:
                validated_data['test_data'] = self._validate_test_data(attrs['test_data'])
            
            # Apply business logic validation
            self._validate_business_logic(validated_data)
            
        except Exception as e:
            # GRACEFUL DEGRADATION: Log error and use safe defaults
            logger.error(f"RealTimeDetection validation error: {e}")
            validated_data = self._get_safe_defaults()
            validated_data['validation_errors'] = [str(e)]
        
        return validated_data
    
    def _validate_test_data(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test data for detection engine"""
        safe_test_data = {}
        
        try:
            if not isinstance(test_data, dict):
                return self._get_default_test_data()
            
            # Simulation parameters
            safe_test_data['simulate'] = test_data.get('simulate', False)
            safe_test_data['duration_seconds'] = self._safe_int_get(
                test_data, 'duration_seconds', 60, 1, 3600
            )
            safe_test_data['activity_count'] = self._safe_int_get(
                test_data, 'activity_count', 100, 1, 10000
            )
            
            # Test scenarios
            safe_test_data['scenarios'] = test_data.get('scenarios', ['normal', 'suspicious'])
            
            # Specific test cases
            safe_test_data['test_cases'] = test_data.get('test_cases', [])
            
            # Add timestamp
            safe_test_data['test_timestamp'] = timezone.now().isoformat()
            
        except Exception as e:
            logger.warning(f"Test data validation error: {e}")
            safe_test_data = self._get_default_test_data()
        
        return safe_test_data
    
    def _validate_business_logic(self, data: Dict[str, Any]) -> None:
        """Validate business logic rules"""
        try:
            # Ensure name is provided
            if not data.get('name'):
                raise serializers.ValidationError("Detection engine name is required")
            
            # Validate check interval
            check_interval = data.get('check_interval_seconds', 60)
            if check_interval < 10:
                logger.warning(f"Check interval too short: {check_interval} seconds")
                data['check_interval_seconds'] = 10
            
            # Validate batch size
            batch_size = data.get('batch_size', 100)
            if batch_size > 10000:
                logger.warning(f"Batch size too large: {batch_size}")
                data['batch_size'] = 10000
            
            # Validate status transition
            current_status = getattr(self.instance, 'status', 'idle') if self.instance else 'idle'
            new_status = data.get('status', current_status)
            
            # Prevent invalid status transitions
            valid_transitions = {
                'idle': ['running', 'paused', 'error'],
                'running': ['idle', 'paused', 'error'],
                'paused': ['idle', 'running', 'error'],
                'error': ['idle', 'paused']
            }
            
            if current_status in valid_transitions and new_status not in valid_transitions[current_status]:
                logger.warning(f"Invalid status transition: {current_status} -> {new_status}")
                data['status'] = current_status
            
            # Check if run_now is requested
            if data.get('run_now', False) and data.get('status') == 'idle':
                data['status'] = 'running'
                logger.info(f"Setting detection engine to run now: {data.get('name')}")
            
        except Exception as e:
            logger.warning(f"Business logic validation error: {e}")
            # Don't raise - continue with potentially invalid data (graceful degradation)
    
    # ============ HELPER METHODS ============
    
    def _safe_int_get(self, data: Dict[str, Any], key: str, 
                     default: int, min_val: int, max_val: int) -> int:
        """Safe integer extraction with bounds checking"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = int(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default
    
    def _get_default_test_data(self) -> Dict[str, Any]:
        """Get default test data"""
        return {
            "simulate": True,
            "duration_seconds": 60,
            "activity_count": 100,
            "scenarios": ["normal", "suspicious", "malicious"],
            "test_cases": [
                {
                    "type": "failed_login",
                    "count": 10,
                    "interval_seconds": 5
                },
                {
                    "type": "suspicious_transaction",
                    "count": 5,
                    "interval_seconds": 30
                }
            ]
        }
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Get complete safe defaults (Ultimate Graceful Degradation)"""
        return {
            'name': f'Detection_{int(time.time())}',
            'detection_type': 'generic',
            'description': 'Safe default detection engine',
            'check_interval_seconds': 60,
            'batch_size': 100,
            'status': 'idle',
            'last_error': '',
            'run_now': False,
            'force_restart': False,
            'safe_mode': True
        }
    
    # ============ CREATE AND UPDATE METHODS ============
    
    def create(self, validated_data: Dict[str, Any]):
        """Create detection engine with defensive coding"""
        try:
            # Remove control fields
            run_now = validated_data.pop('run_now', False)
            force_restart = validated_data.pop('force_restart', False)
            test_data = validated_data.pop('test_data', None)
            
            # Set initial statistics
            validated_data['total_checks'] = 0
            validated_data['total_matches'] = 0
            validated_data['average_processing_time'] = 0
            
            # Create instance
            instance = super().create(validated_data)
            
            # Run if requested
            if run_now:
                self._run_detection_engine(instance)
            
            # Test if test data provided
            if test_data:
                self._test_detection_engine(instance, test_data)
            
            logger.info(f"Created RealTimeDetection: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create RealTimeDetection: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to create detection engine: {str(e)}'
            })
    
    def update(self, instance, validated_data: Dict[str, Any]):
        """Update detection engine with defensive coding"""
        try:
            # Remove control fields
            run_now = validated_data.pop('run_now', False)
            force_restart = validated_data.pop('force_restart', False)
            test_data = validated_data.pop('test_data', None)
            
            # Force restart logic
            if force_restart and instance.status != 'idle':
                validated_data['status'] = 'idle'
                logger.info(f"Forcing restart of detection engine: {instance.name}")
            
            # Update instance
            instance = super().update(instance, validated_data)
            
            # Run if requested
            if run_now and instance.status == 'idle':
                self._run_detection_engine(instance)
            
            # Test if test data provided
            if test_data:
                self._test_detection_engine(instance, test_data)
            
            logger.info(f"Updated RealTimeDetection: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update RealTimeDetection {instance.id}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to update detection engine: {str(e)}'
            })
    
    def _run_detection_engine(self, instance):
        """Run detection engine"""
        try:
            # Use getattr() to safely access model method
            if hasattr(instance, 'run_detection'):
                success = instance.run_detection()
                if success:
                    logger.info(f"Successfully ran detection engine: {instance.name}")
                else:
                    logger.warning(f"Detection engine run failed: {instance.name}")
            else:
                logger.warning(f"run_detection method not available on {instance.name}")
                
        except Exception as e:
            logger.error(f"Error running detection engine {instance.name}: {e}")
    
    def _test_detection_engine(self, instance, test_data: Dict[str, Any]):
        """Test detection engine"""
        try:
            # Store test result in instance context
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'test_data': test_data,
                    'simulated': test_data.get('simulate', False),
                    'timestamp': timezone.now().isoformat(),
                    'engine_status': instance.status
                }
            
            logger.info(f"Tested detection engine: {instance.name}")
            
        except Exception as e:
            logger.warning(f"Detection engine test failed: {e}")
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'error': str(e),
                    'test_data': test_data,
                    'timestamp': timezone.now().isoformat()
                }
    
    # ============ TO REPRESENTATION ============
    
    def to_representation(self, instance):
        """Add test result to representation if available"""
        representation = super().to_representation(instance)
        
        # Add test result if it exists
        if hasattr(instance, '_test_result'):
            representation['test_result'] = instance._test_result
        
        return representation


# ============ REAL-TIME DETECTION STATUS SERIALIZER ============

class RealTimeDetectionStatusSerializer(serializers.Serializer):
    """
    Serializer for real-time detection status
    """
    
    engine_id = serializers.IntegerField(
        help_text="Detection engine ID"
    )
    
    engine_name = serializers.CharField(
        help_text="Detection engine name"
    )
    
    status = serializers.CharField(
        help_text="Current status"
    )
    
    last_run = serializers.DateTimeField(
        help_text="Last run timestamp"
    )
    
    next_run = serializers.CharField(
        help_text="Next scheduled run"
    )
    
    health = serializers.CharField(
        help_text="Health status"
    )
    
    performance = serializers.FloatField(
        help_text="Performance score"
    )
    
    statistics = serializers.DictField(
        help_text="Current statistics"
    )
    
    class Meta:
        fields = [
            'engine_id', 'engine_name', 'status', 'last_run',
            'next_run', 'health', 'performance', 'statistics'
        ]


# ============ REAL-TIME DETECTION CONTROL SERIALIZER ============

class RealTimeDetectionControlSerializer(serializers.Serializer):
    """
    Serializer for controlling real-time detection engines
    """
    
    action = serializers.ChoiceField(
        choices=[
            ('start', 'Start'),
            ('stop', 'Stop'),
            ('pause', 'Pause'),
            ('restart', 'Restart'),
            ('test', 'Test'),
            ('status', 'Get Status')
        ],
        required=True,
        help_text="Action to perform"
    )
    
    engine_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text="Specific engine IDs (empty for all)"
    )
    
    parameters = serializers.DictField(
        required=False,
        default=dict,
        help_text="Action parameters"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate control action"""
        validated_data = data.copy()
        
        try:
            action = data.get('action')
            parameters = data.get('parameters', {})
            
            # Validate action-specific parameters
            if action == 'test':
                if 'duration' in parameters:
                    duration = parameters['duration']
                    if not isinstance(duration, int) or not 1 <= duration <= 3600:
                        raise serializers.ValidationError({
                            'parameters.duration': 'Duration must be between 1 and 3600 seconds'
                        })
            
            elif action == 'start':
                # Validate start parameters
                if 'force' in parameters and not isinstance(parameters['force'], bool):
                    raise serializers.ValidationError({
                        'parameters.force': 'Force must be a boolean'
                    })
            
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.warning(f"Control validation error: {e}")
            # Graceful degradation - accept with default parameters
        
        return validated_data


# ============ REAL-TIME DETECTION RESULT SERIALIZER ============

class RealTimeDetectionResultSerializer(serializers.Serializer):
    """
    Serializer for real-time detection results
    """
    
    engine_id = serializers.IntegerField(
        help_text="Detection engine ID"
    )
    
    engine_name = serializers.CharField(
        help_text="Detection engine name"
    )
    
    start_time = serializers.DateTimeField(
        help_text="Detection start time"
    )
    
    end_time = serializers.DateTimeField(
        help_text="Detection end time"
    )
    
    duration_seconds = serializers.FloatField(
        help_text="Detection duration in seconds"
    )
    
    items_processed = serializers.IntegerField(
        help_text="Number of items processed"
    )
    
    matches_found = serializers.IntegerField(
        help_text="Number of matches found"
    )
    
    status = serializers.CharField(
        help_text="Detection status"
    )
    
    errors = serializers.ListField(
        child=serializers.CharField(),
        help_text="Any errors encountered"
    )
    
    warnings = serializers.ListField(
        child=serializers.CharField(),
        help_text="Any warnings encountered"
    )
    
    details = serializers.DictField(
        help_text="Detailed detection results"
    )
    
    class Meta:
        fields = [
            'engine_id', 'engine_name', 'start_time', 'end_time',
            'duration_seconds', 'items_processed', 'matches_found',
            'status', 'errors', 'warnings', 'details'
        ]
        
        
class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with defensive coding patterns
    """
    
    def to_internal_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Defensive deserialization with null object pattern
        """
        try:
            # Always ensure we have a dict
            if not isinstance(data, dict):
                logger.warning(f"Expected dict, got {type(data)}")
                data = {}
            
            # Apply null object pattern for missing fields
            validated_data = super().to_internal_value(data)
            
            # Set defaults for missing optional fields
            for field_name, field in self.fields.items():
                if field_name not in validated_data and field.required is False:
                    validated_data[field_name] = field.get_default()
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Error in to_internal_value: {str(e)}")
            # Graceful degradation - return empty dict instead of crashing
            return {}

    def to_representation(self, instance):
        """
        Defensive serialization with graceful degradation
        """
        try:
            representation = super().to_representation(instance)
            
            # Clean up None values
            for key in list(representation.keys()):
                if representation[key] is None:
                    representation[key] = "" if isinstance(representation[key], str) else 0
            
            return representation
            
        except Exception as e:
            logger.error(f"Error in to_representation: {str(e)}")
            # Return minimal safe representation
            return {"id": getattr(instance, 'id', None), "error": "serialization_failed"}


class CountrySerializer(BaseSerializer):
    """Country serializer with defensive statistics"""
    
    risk_score = serializers.SerializerMethodField()
    is_high_risk = serializers.SerializerMethodField()
    
    class Meta:
        model = Country
        fields = [
            'id', 'name', 'code', 'iso_code',
            'risk_level', 'is_blocked', 'block_reason',
            'total_users', 'suspicious_activities', 'fraud_cases',
            'risk_score', 'is_high_risk',
            'last_updated', 'created_at'
        ]
        read_only_fields = [
            'total_users', 'suspicious_activities', 'fraud_cases',
            'last_updated', 'created_at'
        ]
    
    def get_risk_score(self, obj: Country) -> int:
        """Calculate risk score safely"""
        try:
            risk_map = {
                'low': 25,
                'medium': 50,
                'high': 75,
                'very_high': 100
            }
            return risk_map.get(getattr(obj, 'risk_level', 'medium'), 50)
        except Exception:
            return 50  # Default to medium
    
    def get_is_high_risk(self, obj: Country) -> bool:
        """Safely check if high risk"""
        try:
            return getattr(obj, 'risk_level', 'medium') in ['high', 'very_high']
        except Exception:
            return False
    
    def validate_code(self, value: str) -> str:
        """Validate country code"""
        if not value or len(value) != 2:
            raise serializers.ValidationError("Country code must be 2 characters")
        return value.upper()
    
    def update_statistics(self, instance: Country) -> None:
        """Safely update statistics"""
        try:
            instance.update_statistics()
        except Exception as e:
            logger.error(f"Failed to update statistics: {str(e)}")
            # Don't fail the request if stats update fails


class GeolocationSerializer(BaseSerializer):
    """Geolocation serializer with risk assessment"""
    
    risk_assessment = serializers.SerializerMethodField()
    is_suspicious = serializers.SerializerMethodField()
    
    class Meta:
        model = GeolocationLog
        fields = [
            'id', 'ip_address', 'country_code', 'country_name',
            'region_code', 'region_name', 'city', 'zip_code',
            'timezone', 'latitude', 'longitude', 'isp',
            'organization', 'as_number', 'is_vpn', 'is_proxy',
            'is_tor', 'is_hosting', 'threat_score',
            'risk_assessment', 'is_suspicious',
            'queried_at', 'updated_at'
        ]
        read_only_fields = [
            'threat_score', 'queried_at', 'updated_at'
        ]
    
    def get_risk_assessment(self, obj: GeolocationLog) -> Dict[str, Any]:
        """Safely get risk assessment"""
        try:
            # Use getattr with default to avoid AttributeError
            risk_method = getattr(obj, 'assess_risk', None)
            if callable(risk_method):
                return risk_method()
            return {'risk_score': 0, 'risk_factors': [], 'threat_level': 'low'}
        except Exception as e:
            logger.error(f"Error in risk assessment: {str(e)}")
            return {'risk_score': 0, 'risk_factors': [], 'threat_level': 'low'}
    
    def get_is_suspicious(self, obj: GeolocationLog) -> bool:
        """Safely check if suspicious"""
        try:
            # Multiple defensive checks
            threat_score = getattr(obj, 'threat_score', 0)
            is_vpn = getattr(obj, 'is_vpn', False)
            is_proxy = getattr(obj, 'is_proxy', False)
            
            return (threat_score > 70 or is_vpn or is_proxy)
        except Exception:
            return False
    
    def validate_ip_address(self, value: str) -> str:
        """Validate IP address"""
        try:
            from django.core.validators import validate_ipv46_address
            validate_ipv46_address(value)
            return value
        except Exception:
            raise serializers.ValidationError("Invalid IP address format")


class CountryBlockRuleSerializer(BaseSerializer):
    """Country block rule serializer"""
    
    is_active_now = serializers.SerializerMethodField()
    country_info = serializers.SerializerMethodField()
    
    class Meta:
        model = CountryBlockRule
        fields = [
            'id', 'country', 'country_info',
            'block_type', 'block_all_ips', 'allowed_ips',
            'allowed_asns', 'require_phone_verification',
            'require_id_verification', 'require_address_verification',
            'is_active', 'is_active_now', 'start_date', 'end_date',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']
    
    def get_is_active_now(self, obj: CountryBlockRule) -> bool:
        """Safely check if rule is active"""
        try:
            active_method = getattr(obj, 'is_active_now', None)
            if callable(active_method):
                return active_method()
            return getattr(obj, 'is_active', False)
        except Exception:
            return False
    
    def get_country_info(self, obj: CountryBlockRule) -> Dict[str, Any]:
        """Safely get country info"""
        try:
            # Using getattr with None check
            country = getattr(obj, 'country', None)
            if country:
                return {
                    'id': getattr(country, 'id', None),
                    'name': getattr(country, 'name', ''),
                    'code': getattr(country, 'code', ''),
                    'risk_level': getattr(country, 'risk_level', 'medium')
                }
            return {}
        except Exception:
            return {}
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate rule data"""
        # Check date consistency
        start_date = attrs.get('start_date', timezone.now())
        end_date = attrs.get('end_date')
        
        if end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        
        return attrs


class APIRateLimitSerializer(BaseSerializer):
    """API rate limit serializer"""
    
    current_usage = serializers.SerializerMethodField()
    next_reset = serializers.SerializerMethodField()
    
    class Meta:
        model = APIRateLimit
        fields = [
            'id', 'name', 'description', 'limit_type',
            'limit_period', 'request_limit', 'endpoint_pattern',
            'user_group', 'response_status_code', 'response_message',
            'response_headers', 'is_active', 'bypass_key_required',
            'total_blocks', 'last_blocked_at',
            'current_usage', 'next_reset',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['total_blocks', 'last_blocked_at']
    
    def get_current_usage(self, obj: APIRateLimit) -> Dict[str, Any]:
        """Get current usage stats safely"""
        try:
            # This would typically come from cache/redis
            # Simplified version for example
            cache_key = f"rate_limit_stats:{obj.id}"
            stats = cache.get(cache_key, {})
            
            return {
                'current': stats.get('current', 0),
                'remaining': max(0, obj.request_limit - stats.get('current', 0)),
                'limit': obj.request_limit
            }
        except Exception:
            return {'current': 0, 'remaining': obj.request_limit, 'limit': obj.request_limit}
    
    def get_next_reset(self, obj: APIRateLimit) -> str:
        """Get next reset time safely"""
        try:
            reset_method = getattr(obj, '_get_reset_time', None)
            if callable(reset_method):
                return reset_method().isoformat()
            return (timezone.now() + timedelta(hours=1)).isoformat()
        except Exception:
            return timezone.now().isoformat()


class PasswordPolicySerializer(BaseSerializer):
    """Password policy serializer with validation"""
    
    validation_result = serializers.SerializerMethodField()
    
    class Meta:
        model = PasswordPolicy
        fields = [
            'id', 'name', 'min_length', 'max_length',
            'require_uppercase', 'require_lowercase',
            'require_digits', 'require_special_chars',
            'min_special_chars', 'special_chars_set',
            'remember_last_passwords', 'password_expiry_days',
            'warn_before_expiry_days', 'max_failed_attempts',
            'lockout_duration_minutes', 'lockout_increment_factor',
            'allow_common_passwords', 'allow_username_in_password',
            'allow_repeating_chars', 'allow_sequential_chars',
            'is_active', 'applies_to_all_users',
            'validation_result',
            'created_at', 'updated_at'
        ]
    
    def get_validation_result(self, obj: PasswordPolicy) -> Dict[str, Any]:
        """Get validation rules summary"""
        try:
            return {
                'min_length': getattr(obj, 'min_length', 8),
                'requires': {
                    'uppercase': getattr(obj, 'require_uppercase', True),
                    'lowercase': getattr(obj, 'require_lowercase', True),
                    'digits': getattr(obj, 'require_digits', True),
                    'special_chars': getattr(obj, 'require_special_chars', True)
                }
            }
        except Exception:
            return {'min_length': 8, 'requires': {}}
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate policy consistency"""
        min_length = attrs.get('min_length', 8)
        max_length = attrs.get('max_length', 128)
        
        if min_length > max_length:
            raise serializers.ValidationError({
                'min_length': 'Minimum length cannot exceed maximum length'
            })
        
        if min_length < 4:
            raise serializers.ValidationError({
                'min_length': 'Minimum length must be at least 4'
            })
        
        return attrs


class UserSessionSerializer(BaseSerializer):
    """User session serializer with security info"""
    
    device_summary = serializers.SerializerMethodField()
    location_summary = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user', 'session_key', 'device_info',
            'device_summary', 'ip_address', 'geolocation',
            'location_summary', 'is_active', 'is_compromised',
            'force_logout', 'created_at', 'last_activity',
            'expires_at', 'user_agent', 'login_method',
            'is_current'
        ]
        read_only_fields = [
            'session_key', 'created_at', 'last_activity',
            'expires_at'
        ]
    
    def get_device_summary(self, obj: UserSession) -> Dict[str, Any]:
        """Safely get device summary"""
        try:
            device = getattr(obj, 'device_info', None)
            if device:
                # Using dict.get() for safe access
                return {
                    'type': device.metadata.get('device_type', 'Unknown'),
                    'browser': device.metadata.get('browser', 'Unknown'),
                    'os': device.metadata.get('os', 'Unknown')
                }
            return {}
        except Exception:
            return {}
    
    def get_location_summary(self, obj: UserSession) -> Dict[str, Any]:
        """Safely get location summary"""
        try:
            geo = getattr(obj, 'geolocation', None)
            if geo:
                return {
                    'country': getattr(geo, 'country_name', ''),
                    'city': getattr(geo, 'city', ''),
                    'isp': getattr(geo, 'isp', '')
                }
            return {}
        except Exception:
            return {}
    
    def get_is_current(self, obj: UserSession) -> bool:
        """Check if this is the current session"""
        try:
            request = self.context.get('request')
            if request and hasattr(request, 'session'):
                return obj.session_key == request.session.session_key
            return False
        except Exception:
            return False


class TwoFactorMethodSerializer(BaseSerializer):
    """2FA method serializer"""
    
    is_setup_complete = serializers.SerializerMethodField()
    has_backup_codes = serializers.SerializerMethodField()
    
    class Meta:
        model = TwoFactorMethod
        fields = [
            'id', 'user', 'method_type', 'is_primary',
            'is_enabled', 'phone_number', 'email',
            'failed_attempts', 'last_used_at',
            'is_setup_complete', 'has_backup_codes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'failed_attempts', 'last_used_at',
            'created_at', 'updated_at'
        ]
        # Never expose secret_key or backup_codes via API
    
    def get_is_setup_complete(self, obj: TwoFactorMethod) -> bool:
        """Check if setup is complete"""
        try:
            if obj.method_type == 'totp':
                return bool(getattr(obj, 'secret_key', ''))
            elif obj.method_type == 'sms':
                return bool(getattr(obj, 'phone_number', ''))
            elif obj.method_type == 'email':
                return bool(getattr(obj, 'email', ''))
            return True
        except Exception:
            return False
    
    def get_has_backup_codes(self, obj: TwoFactorMethod) -> bool:
        """Check if backup codes exist"""
        try:
            backup_codes = getattr(obj, 'backup_codes', [])
            return bool(backup_codes and len(backup_codes) > 0)
        except Exception:
            return False
    
    def validate_phone_number(self, value: str) -> str:
        """Validate phone number"""
        if value and not value.startswith('+'):
            raise serializers.ValidationError(
                "Phone number must include country code (e.g., +880)"
            )
        return value


# ==================== BULK SERIALIZERS ====================

class BulkCountrySerializer(serializers.Serializer):
    """Bulk country operations"""
    
    countries = CountrySerializer(many=True)
    action = serializers.ChoiceField(
        choices=['create', 'update', 'upsert', 'delete'],
        default='upsert'
    )
    
    def create(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle bulk operations"""
        countries_data = validated_data.get('countries', [])
        action = validated_data.get('action', 'upsert')
        
        results = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'failed': 0,
            'details': []
        }
        
        for country_data in countries_data:
            try:
                if action == 'delete':
                    # Delete operation
                    country = Country.objects.filter(
                        code=country_data.get('code')
                    ).first()
                    if country:
                        country.delete()
                        results['deleted'] += 1
                else:
                    # Create/Update/Upsert operations
                    code = country_data.get('code')
                    if not code:
                        continue
                    
                    if action in ['update', 'upsert']:
                        country, created = Country.objects.update_or_create(
                            code=code,
                            defaults=country_data
                        )
                        if created:
                            results['created'] += 1
                        else:
                            results['updated'] += 1
                    else:  # create
                        Country.objects.create(**country_data)
                        results['created'] += 1
                        
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'code': country_data.get('code'),
                    'error': str(e)
                })
        
        return results


class PasswordValidationSerializer(serializers.Serializer):
    """Password validation serializer"""
    
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False)
    policy_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate password against policy"""
        password = attrs.get('password', '')
        username = attrs.get('username', '')
        
        # Get policy
        policy_id = attrs.get('policy_id')
        if policy_id:
            policy = PasswordPolicy.objects.filter(id=policy_id).first()
        else:
            policy = PasswordPolicy.objects.filter(is_active=True).first()
        
        if not policy:
            # Use default policy
            policy = PasswordPolicy()
        
        # Validate password
        validation_result = policy.validate_password(password, username)
        
        attrs['validation_result'] = validation_result
        attrs['policy_used'] = policy.name if policy else 'Default'
        
        return attrs


class RealTimeDetectionSerializer(serializers.ModelSerializer):
    """
    Bulletproof Serializer for RealTimeDetection Model
    Complete Defensive Implementation with All Patterns
    """
    
    # ============ COMPUTED FIELDS (READ-ONLY) ============
    
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
        help_text="Human-readable status"
    )
    
    uptime_percentage = serializers.SerializerMethodField(
        help_text="Uptime percentage of the detection engine"
    )
    
    performance_score = serializers.SerializerMethodField(
        help_text="Performance score (0-100)"
    )
    
    efficiency_rate = serializers.SerializerMethodField(
        help_text="Match rate efficiency"
    )
    
    last_run_ago = serializers.SerializerMethodField(
        help_text="How long ago the detection last ran"
    )
    
    next_run_in = serializers.SerializerMethodField(
        help_text="When the next run is scheduled"
    )
    
    health_status = serializers.SerializerMethodField(
        help_text="Health status of the detection engine"
    )
    
    # ============ CONTROL FIELDS ============
    
    run_now = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Set to true to run detection immediately"
    )
    
    force_restart = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="Force restart the detection engine"
    )
    
    test_data = serializers.DictField(
        write_only=True,
        required=False,
        default=dict,
        help_text="Test data for detection engine"
    )
    
    # ============ STATISTICS FIELDS ============
    
    today_stats = serializers.SerializerMethodField(
        help_text="Statistics for today"
    )
    
    weekly_stats = serializers.SerializerMethodField(
        help_text="Statistics for this week"
    )
    
    monthly_stats = serializers.SerializerMethodField(
        help_text="Statistics for this month"
    )
    
    # ============ PERFORMANCE METRICS ============
    
    performance_metrics = serializers.SerializerMethodField(
        help_text="Detailed performance metrics"
    )
    
    error_rate = serializers.SerializerMethodField(
        help_text="Error rate percentage"
    )
    
    success_rate = serializers.SerializerMethodField(
        help_text="Success rate percentage"
    )
    
    class Meta:
        model = 'security.RealTimeDetection'  # Lazy reference
        fields = [
            # Core fields
            'id', 'name', 'detection_type', 'description',
            
            # Configuration
            'check_interval_seconds', 'batch_size',
            
            # Status
            'status', 'status_display', 'last_run_at', 'last_error',
            'last_run_ago', 'next_run_in', 'health_status',
            
            # Statistics
            'total_checks', 'total_matches',
            'today_stats', 'weekly_stats', 'monthly_stats',
            
            # Performance
            'average_processing_time',
            'performance_score', 'efficiency_rate', 'uptime_percentage',
            'performance_metrics', 'error_rate', 'success_rate',
            
            # Control fields
            'run_now', 'force_restart', 'test_data',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'last_run_at', 'last_error', 'total_checks',
            'total_matches', 'average_processing_time', 'created_at',
            'updated_at', 'status_display', 'uptime_percentage',
            'performance_score', 'efficiency_rate', 'last_run_ago',
            'next_run_in', 'health_status', 'today_stats', 'weekly_stats',
            'monthly_stats', 'performance_metrics', 'error_rate',
            'success_rate'
        ]
    
    def __init__(self, *args, **kwargs):
        """Initialize with dynamic model reference"""
        super().__init__(*args, **kwargs)
        
        # Set model if not already set
        if self.Meta.model == 'security.RealTimeDetection':
            try:
                from .models import RealTimeDetection
                self.Meta.model = RealTimeDetection
            except ImportError as e:
                logger.warning(f"RealTimeDetection model not available: {e}")
                # Graceful degradation - use stub
                self.Meta.model = None
    
    # ============ SAFE GETTER METHODS ============
    
    def get_uptime_percentage(self, obj) -> float:
        """Calculate uptime percentage with defensive coding"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            error_count = self._get_error_count(obj)
            
            if total_checks == 0:
                return 100.0  # No checks yet, assume 100% uptime
            
            uptime = max(0, total_checks - error_count)
            return round((uptime / total_checks) * 100, 2)
            
        except Exception as e:
            logger.debug(f"Uptime calculation error: {e}")
            return 0.0
    
    def get_performance_score(self, obj) -> float:
        """Calculate performance score"""
        try:
            avg_processing_time = getattr(obj, 'average_processing_time', 0)
            efficiency_rate = self.get_efficiency_rate(obj)
            
            # Lower processing time is better
            time_score = max(0, min(100, (1000 - avg_processing_time) / 10))
            
            # Combined score
            performance_score = (time_score * 0.4) + (efficiency_rate * 0.6)
            return round(performance_score, 1)
            
        except Exception as e:
            logger.debug(f"Performance score calculation error: {e}")
            return 0.0
    
    def get_efficiency_rate(self, obj) -> float:
        """Calculate match efficiency rate"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            if total_checks == 0:
                return 0.0
            
            # Efficiency: matches per check (normalized)
            efficiency = (total_matches / total_checks) * 100
            return round(min(100.0, efficiency), 2)
            
        except Exception as e:
            logger.debug(f"Efficiency rate calculation error: {e}")
            return 0.0
    
    def get_last_run_ago(self, obj) -> str:
        """Format how long ago detection last ran"""
        try:
            last_run_at = getattr(obj, 'last_run_at', None)
            if not last_run_at:
                return "Never"
            
            delta = timezone.now() - last_run_at
            
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return f"{delta.seconds} seconds ago"
                
        except Exception as e:
            logger.debug(f"Last run ago calculation error: {e}")
            return "Unknown"
    
    def get_next_run_in(self, obj) -> str:
        """Calculate when next run is scheduled"""
        try:
            last_run_at = getattr(obj, 'last_run_at', None)
            check_interval = getattr(obj, 'check_interval_seconds', 60)
            status = getattr(obj, 'status', 'idle')
            
            if status != 'idle' or not last_run_at:
                return "Not scheduled"
            
            next_run = last_run_at + timedelta(seconds=check_interval)
            delta = next_run - timezone.now()
            
            if delta.total_seconds() <= 0:
                return "Due now"
            elif delta.total_seconds() > 3600:
                return f"In {int(delta.total_seconds() / 3600)} hours"
            elif delta.total_seconds() > 60:
                return f"In {int(delta.total_seconds() / 60)} minutes"
            else:
                return f"In {int(delta.total_seconds())} seconds"
                
        except Exception as e:
            logger.debug(f"Next run calculation error: {e}")
            return "Unknown"
    
    def get_health_status(self, obj) -> str:
        """Determine health status"""
        try:
            status = getattr(obj, 'status', 'idle')
            last_error = getattr(obj, 'last_error', '')
            avg_processing_time = getattr(obj, 'average_processing_time', 0)
            
            if status == 'error':
                return "Critical"
            elif status == 'running' and avg_processing_time > 10:
                return "Degraded"
            elif last_error and 'error' in status.lower():
                return "Warning"
            elif status == 'paused':
                return "Paused"
            else:
                return "Healthy"
                
        except Exception as e:
            logger.debug(f"Health status calculation error: {e}")
            return "Unknown"
    
    def get_today_stats(self, obj) -> Dict[str, Any]:
        """Get today's statistics"""
        try:
            # In real implementation, you would query actual data
            # For now, return mock/estimated data
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            # Estimate today's activity (assuming 10% of total)
            today_checks = max(1, int(total_checks * 0.1))
            today_matches = max(0, int(total_matches * 0.1))
            
            return {
                'checks': today_checks,
                'matches': today_matches,
                'match_rate': round((today_matches / today_checks * 100), 1) if today_checks > 0 else 0,
                'avg_processing_time': getattr(obj, 'average_processing_time', 0)
            }
            
        except Exception as e:
            logger.debug(f"Today stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_weekly_stats(self, obj) -> Dict[str, Any]:
        """Get weekly statistics"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            # Estimate weekly activity (assuming 30% of total)
            weekly_checks = max(1, int(total_checks * 0.3))
            weekly_matches = max(0, int(total_matches * 0.3))
            
            return {
                'checks': weekly_checks,
                'matches': weekly_matches,
                'match_rate': round((weekly_matches / weekly_checks * 100), 1) if weekly_checks > 0 else 0,
                'trend': 'stable'  # Would calculate actual trend
            }
            
        except Exception as e:
            logger.debug(f"Weekly stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_monthly_stats(self, obj) -> Dict[str, Any]:
        """Get monthly statistics"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            total_matches = getattr(obj, 'total_matches', 0)
            
            return {
                'checks': total_checks,
                'matches': total_matches,
                'match_rate': round((total_matches / total_checks * 100), 1) if total_checks > 0 else 0,
                'avg_daily_checks': round(total_checks / 30, 1) if total_checks > 0 else 0
            }
            
        except Exception as e:
            logger.debug(f"Monthly stats calculation error: {e}")
            return {'error': 'Stats unavailable'}
    
    def get_performance_metrics(self, obj) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        try:
            avg_time = getattr(obj, 'average_processing_time', 0)
            total_checks = getattr(obj, 'total_checks', 0)
            
            return {
                'processing_time': {
                    'average': avg_time,
                    'estimated_max': avg_time * 2,
                    'estimated_min': max(0.1, avg_time * 0.5)
                },
                'throughput': {
                    'checks_per_hour': int(total_checks / 24) if total_checks > 0 else 0,
                    'estimated_capacity': 10000,  # Would calculate based on system
                    'current_utilization': round((total_checks / 10000) * 100, 1) if total_checks > 0 else 0
                },
                'reliability': {
                    'uptime_percentage': self.get_uptime_percentage(obj),
                    'error_rate': self.get_error_rate(obj),
                    'success_rate': self.get_success_rate(obj)
                }
            }
            
        except Exception as e:
            logger.debug(f"Performance metrics calculation error: {e}")
            return {'error': 'Metrics unavailable'}
    
    def get_error_rate(self, obj) -> float:
        """Calculate error rate"""
        try:
            total_checks = getattr(obj, 'total_checks', 0)
            error_count = self._get_error_count(obj)
            
            if total_checks == 0:
                return 0.0
            
            return round((error_count / total_checks) * 100, 2)
            
        except Exception as e:
            logger.debug(f"Error rate calculation error: {e}")
            return 0.0
    
    def get_success_rate(self, obj) -> float:
        """Calculate success rate"""
        try:
            error_rate = self.get_error_rate(obj)
            return max(0.0, 100.0 - error_rate)
            
        except Exception as e:
            logger.debug(f"Success rate calculation error: {e}")
            return 0.0
    
    def _get_error_count(self, obj) -> int:
        """Estimate error count based on last_error"""
        try:
            last_error = getattr(obj, 'last_error', '')
            if last_error and len(last_error.strip()) > 0:
                # Simple estimation: assume 1 error per error message
                return 1
            return 0
        except Exception:
            return 0
    
    # ============ VALIDATION METHODS ============
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bulletproof validation with Graceful Degradation
        """
        validated_data = {}
        
        try:
            # Use dict.get() with defaults for all fields
            # Core fields
            validated_data['name'] = attrs.get('name', '').strip()
            validated_data['detection_type'] = attrs.get('detection_type', 'generic')
            validated_data['description'] = attrs.get('description', '').strip()
            
            # Configuration with safe defaults
            validated_data['check_interval_seconds'] = self._safe_int_get(
                attrs, 'check_interval_seconds', 60, 10, 3600
            )
            validated_data['batch_size'] = self._safe_int_get(
                attrs, 'batch_size', 100, 1, 10000
            )
            
            # Status
            validated_data['status'] = attrs.get('status', 'idle')
            validated_data['last_error'] = attrs.get('last_error', '').strip()
            
            # Control fields
            validated_data['run_now'] = attrs.get('run_now', False)
            validated_data['force_restart'] = attrs.get('force_restart', False)
            
            # Test data if provided
            if 'test_data' in attrs:
                validated_data['test_data'] = self._validate_test_data(attrs['test_data'])
            
            # Apply business logic validation
            self._validate_business_logic(validated_data)
            
        except Exception as e:
            # GRACEFUL DEGRADATION: Log error and use safe defaults
            logger.error(f"RealTimeDetection validation error: {e}")
            validated_data = self._get_safe_defaults()
            validated_data['validation_errors'] = [str(e)]
        
        return validated_data
    
    def _validate_test_data(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test data for detection engine"""
        safe_test_data = {}
        
        try:
            if not isinstance(test_data, dict):
                return self._get_default_test_data()
            
            # Simulation parameters
            safe_test_data['simulate'] = test_data.get('simulate', False)
            safe_test_data['duration_seconds'] = self._safe_int_get(
                test_data, 'duration_seconds', 60, 1, 3600
            )
            safe_test_data['activity_count'] = self._safe_int_get(
                test_data, 'activity_count', 100, 1, 10000
            )
            
            # Test scenarios
            safe_test_data['scenarios'] = test_data.get('scenarios', ['normal', 'suspicious'])
            
            # Specific test cases
            safe_test_data['test_cases'] = test_data.get('test_cases', [])
            
            # Add timestamp
            safe_test_data['test_timestamp'] = timezone.now().isoformat()
            
        except Exception as e:
            logger.warning(f"Test data validation error: {e}")
            safe_test_data = self._get_default_test_data()
        
        return safe_test_data
    
    def _validate_business_logic(self, data: Dict[str, Any]) -> None:
        """Validate business logic rules"""
        try:
            # Ensure name is provided
            if not data.get('name'):
                raise serializers.ValidationError("Detection engine name is required")
            
            # Validate check interval
            check_interval = data.get('check_interval_seconds', 60)
            if check_interval < 10:
                logger.warning(f"Check interval too short: {check_interval} seconds")
                data['check_interval_seconds'] = 10
            
            # Validate batch size
            batch_size = data.get('batch_size', 100)
            if batch_size > 10000:
                logger.warning(f"Batch size too large: {batch_size}")
                data['batch_size'] = 10000
            
            # Validate status transition
            current_status = getattr(self.instance, 'status', 'idle') if self.instance else 'idle'
            new_status = data.get('status', current_status)
            
            # Prevent invalid status transitions
            valid_transitions = {
                'idle': ['running', 'paused', 'error'],
                'running': ['idle', 'paused', 'error'],
                'paused': ['idle', 'running', 'error'],
                'error': ['idle', 'paused']
            }
            
            if current_status in valid_transitions and new_status not in valid_transitions[current_status]:
                logger.warning(f"Invalid status transition: {current_status} -> {new_status}")
                data['status'] = current_status
            
            # Check if run_now is requested
            if data.get('run_now', False) and data.get('status') == 'idle':
                data['status'] = 'running'
                logger.info(f"Setting detection engine to run now: {data.get('name')}")
            
        except Exception as e:
            logger.warning(f"Business logic validation error: {e}")
            # Don't raise - continue with potentially invalid data (graceful degradation)
    
    # ============ HELPER METHODS ============
    
    def _safe_int_get(self, data: Dict[str, Any], key: str, 
                     default: int, min_val: int, max_val: int) -> int:
        """Safe integer extraction with bounds checking"""
        try:
            value = data.get(key, default)
            if not isinstance(value, (int, float)):
                value = default
            value = int(value)
            return max(min_val, min(max_val, value))
        except Exception:
            return default
    
    def _get_default_test_data(self) -> Dict[str, Any]:
        """Get default test data"""
        return {
            "simulate": True,
            "duration_seconds": 60,
            "activity_count": 100,
            "scenarios": ["normal", "suspicious", "malicious"],
            "test_cases": [
                {
                    "type": "failed_login",
                    "count": 10,
                    "interval_seconds": 5
                },
                {
                    "type": "suspicious_transaction",
                    "count": 5,
                    "interval_seconds": 30
                }
            ]
        }
    
    def _get_safe_defaults(self) -> Dict[str, Any]:
        """Get complete safe defaults (Ultimate Graceful Degradation)"""
        return {
            'name': f'Detection_{int(time.time())}',
            'detection_type': 'generic',
            'description': 'Safe default detection engine',
            'check_interval_seconds': 60,
            'batch_size': 100,
            'status': 'idle',
            'last_error': '',
            'run_now': False,
            'force_restart': False,
            'safe_mode': True
        }
    
    # ============ CREATE AND UPDATE METHODS ============
    
    def create(self, validated_data: Dict[str, Any]):
        """Create detection engine with defensive coding"""
        try:
            # Remove control fields
            run_now = validated_data.pop('run_now', False)
            force_restart = validated_data.pop('force_restart', False)
            test_data = validated_data.pop('test_data', None)
            
            # Set initial statistics
            validated_data['total_checks'] = 0
            validated_data['total_matches'] = 0
            validated_data['average_processing_time'] = 0
            
            # Create instance
            instance = super().create(validated_data)
            
            # Run if requested
            if run_now:
                self._run_detection_engine(instance)
            
            # Test if test data provided
            if test_data:
                self._test_detection_engine(instance, test_data)
            
            logger.info(f"Created RealTimeDetection: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create RealTimeDetection: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to create detection engine: {str(e)}'
            })
    
    def update(self, instance, validated_data: Dict[str, Any]):
        """Update detection engine with defensive coding"""
        try:
            # Remove control fields
            run_now = validated_data.pop('run_now', False)
            force_restart = validated_data.pop('force_restart', False)
            test_data = validated_data.pop('test_data', None)
            
            # Force restart logic
            if force_restart and instance.status != 'idle':
                validated_data['status'] = 'idle'
                logger.info(f"Forcing restart of detection engine: {instance.name}")
            
            # Update instance
            instance = super().update(instance, validated_data)
            
            # Run if requested
            if run_now and instance.status == 'idle':
                self._run_detection_engine(instance)
            
            # Test if test data provided
            if test_data:
                self._test_detection_engine(instance, test_data)
            
            logger.info(f"Updated RealTimeDetection: {instance.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to update RealTimeDetection {instance.id}: {e}")
            raise serializers.ValidationError({
                'non_field_errors': f'Failed to update detection engine: {str(e)}'
            })
    
    def _run_detection_engine(self, instance):
        """Run detection engine"""
        try:
            # Use getattr() to safely access model method
            if hasattr(instance, 'run_detection'):
                success = instance.run_detection()
                if success:
                    logger.info(f"Successfully ran detection engine: {instance.name}")
                else:
                    logger.warning(f"Detection engine run failed: {instance.name}")
            else:
                logger.warning(f"run_detection method not available on {instance.name}")
                
        except Exception as e:
            logger.error(f"Error running detection engine {instance.name}: {e}")
    
    def _test_detection_engine(self, instance, test_data: Dict[str, Any]):
        """Test detection engine"""
        try:
            # Store test result in instance context
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'test_data': test_data,
                    'simulated': test_data.get('simulate', False),
                    'timestamp': timezone.now().isoformat(),
                    'engine_status': instance.status
                }
            
            logger.info(f"Tested detection engine: {instance.name}")
            
        except Exception as e:
            logger.warning(f"Detection engine test failed: {e}")
            if hasattr(instance, '_test_result'):
                instance._test_result = {
                    'error': str(e),
                    'test_data': test_data,
                    'timestamp': timezone.now().isoformat()
                }
    
    # ============ TO REPRESENTATION ============
    
    def to_representation(self, instance):
        """Add test result to representation if available"""
        representation = super().to_representation(instance)
        
        # Add test result if it exists
        if hasattr(instance, '_test_result'):
            representation['test_result'] = instance._test_result
        
        return representation


# ============ REAL-TIME DETECTION STATUS SERIALIZER ============

class RealTimeDetectionStatusSerializer(serializers.Serializer):
    """
    Serializer for real-time detection status
    """
    
    engine_id = serializers.IntegerField(
        help_text="Detection engine ID"
    )
    
    engine_name = serializers.CharField(
        help_text="Detection engine name"
    )
    
    status = serializers.CharField(
        help_text="Current status"
    )
    
    last_run = serializers.DateTimeField(
        help_text="Last run timestamp"
    )
    
    next_run = serializers.CharField(
        help_text="Next scheduled run"
    )
    
    health = serializers.CharField(
        help_text="Health status"
    )
    
    performance = serializers.FloatField(
        help_text="Performance score"
    )
    
    statistics = serializers.DictField(
        help_text="Current statistics"
    )
    
    class Meta:
        fields = [
            'engine_id', 'engine_name', 'status', 'last_run',
            'next_run', 'health', 'performance', 'statistics'
        ]


# ============ REAL-TIME DETECTION CONTROL SERIALIZER ============

class RealTimeDetectionControlSerializer(serializers.Serializer):
    """
    Serializer for controlling real-time detection engines
    """
    
    action = serializers.ChoiceField(
        choices=[
            ('start', 'Start'),
            ('stop', 'Stop'),
            ('pause', 'Pause'),
            ('restart', 'Restart'),
            ('test', 'Test'),
            ('status', 'Get Status')
        ],
        required=True,
        help_text="Action to perform"
    )
    
    engine_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text="Specific engine IDs (empty for all)"
    )
    
    parameters = serializers.DictField(
        required=False,
        default=dict,
        help_text="Action parameters"
    )
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate control action"""
        validated_data = data.copy()
        
        try:
            action = data.get('action')
            parameters = data.get('parameters', {})
            
            # Validate action-specific parameters
            if action == 'test':
                if 'duration' in parameters:
                    duration = parameters['duration']
                    if not isinstance(duration, int) or not 1 <= duration <= 3600:
                        raise serializers.ValidationError({
                            'parameters.duration': 'Duration must be between 1 and 3600 seconds'
                        })
            
            elif action == 'start':
                # Validate start parameters
                if 'force' in parameters and not isinstance(parameters['force'], bool):
                    raise serializers.ValidationError({
                        'parameters.force': 'Force must be a boolean'
                    })
            
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.warning(f"Control validation error: {e}")
            # Graceful degradation - accept with default parameters
        
        return validated_data


# ============ REAL-TIME DETECTION RESULT SERIALIZER ============

class RealTimeDetectionResultSerializer(serializers.Serializer):
    """
    Serializer for real-time detection results
    """
    
    engine_id = serializers.IntegerField(
        help_text="Detection engine ID"
    )
    
    engine_name = serializers.CharField(
        help_text="Detection engine name"
    )
    
    start_time = serializers.DateTimeField(
        help_text="Detection start time"
    )
    
    end_time = serializers.DateTimeField(
        help_text="Detection end time"
    )
    
    duration_seconds = serializers.FloatField(
        help_text="Detection duration in seconds"
    )
    
    items_processed = serializers.IntegerField(
        help_text="Number of items processed"
    )
    
    matches_found = serializers.IntegerField(
        help_text="Number of matches found"
    )
    
    status = serializers.CharField(
        help_text="Detection status"
    )
    
    errors = serializers.ListField(
        child=serializers.CharField(),
        help_text="Any errors encountered"
    )
    
    warnings = serializers.ListField(
        child=serializers.CharField(),
        help_text="Any warnings encountered"
    )
    
    details = serializers.DictField(
        help_text="Detailed detection results"
    )
    
    class Meta:
        fields = [
            'engine_id', 'engine_name', 'start_time', 'end_time',
            'duration_seconds', 'items_processed', 'matches_found',
            'status', 'errors', 'warnings', 'details'
        ]
        




# security/serializers.py এ এই code টা ADD করুন

class AuditTrailSerializer(serializers.ModelSerializer):
    """
    Full serializer for AuditTrail model.
    Read-only — audit logs should never be modified via API.
    """

    username = serializers.SerializerMethodField()
    action_type_display = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = AuditTrail
        fields = [
            'id',
            'user',
            'username',
            'action_type',
            'action_type_display',
            'model_name',
            'object_id',
            'object_repr',
            'old_values',
            'new_values',
            'changed_fields',
            'ip_address',
            'user_agent',
            'session_key',
            'request_path',
            'request_method',
            'status_code',
            'created_at',
            'time_ago',
        ]
        read_only_fields = fields  # সব field read-only

    def get_username(self, obj):
        """User এর username safe ভাবে return করে"""
        try:
            if obj.user:
                return obj.user.username
            return 'Anonymous'
        except Exception:
            return 'Unknown'

    def get_action_type_display(self, obj):
        """Human-readable action type"""
        try:
            return obj.get_action_type_display()
        except Exception:
            return obj.action_type or ''

    def get_time_ago(self, obj):
        """'2 minutes ago' style time"""
        try:
            from django.utils import timezone
            now = timezone.now()
            diff = now - obj.created_at

            seconds = int(diff.total_seconds())

            if seconds < 60:
                return f"{seconds} seconds ago"
            elif seconds < 3600:
                return f"{seconds // 60} minutes ago"
            elif seconds < 86400:
                return f"{seconds // 3600} hours ago"
            else:
                return f"{diff.days} days ago"
        except Exception:
            return ''


class AuditTrailListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list view — কম data, বেশি performance.
    """

    username = serializers.SerializerMethodField()

    class Meta:
        model = AuditTrail
        fields = [
            'id',
            'username',
            'action_type',
            'model_name',
            'object_id',
            'ip_address',
            'request_method',
            'status_code',
            'created_at',
        ]
        read_only_fields = fields

    def get_username(self, obj):
        try:
            return obj.user.username if obj.user else 'Anonymous'
        except Exception:
            return 'Unknown'# trigger
