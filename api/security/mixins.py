"""
Security Mixins Module
Reusable Django mixins for security functionality
"""

import logging
from datetime import datetime, timedelta
from django.conf import settings
from .permissions import IsSecurityAdmin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from typing import Dict, Any, Optional, List

from .utils import SecurityUtils, RateLimiter
from .models import SecurityLog, UserSession, RiskScore

User = get_user_model()
logger = logging.getLogger('security.mixins')


class SecurityAuditMixin:
    """Mixin for adding security audit logging to models"""
    
    def save(self, *args, **kwargs):
        """Override save to add audit logging"""
        # Check if this is a new object or update
        is_new = self.pk is None
        
        # Get old values if updating
        old_values = {}
        if not is_new:
            try:
                old_obj = self.__class__.objects.get(pk=self.pk)
                old_values = {
                    field.name: getattr(old_obj, field.name)
                    for field in self._meta.fields
                }
            except self.__class__.DoesNotExist:
                pass
        
        # Call the original save method
        super().save(*args, **kwargs)
        
        # Log the change
        self._log_security_change(is_new, old_values)
    
    def delete(self, *args, **kwargs):
        """Override delete to add audit logging"""
        # Log before deletion
        self._log_security_deletion()
        
        # Call the original delete method
        super().delete(*args, **kwargs)
    
    def _log_security_change(self, is_new: bool, old_values: Dict[str, Any]):
        """Log security-related changes"""
        try:
            # Get current user from thread local (set by middleware)
            current_user = getattr(self, '_current_user', None)
            
            if is_new:
                action = 'created'
                description = f'{self.__class__.__name__} created'
                metadata = {'new_values': self._get_model_values()}
            else:
                action = 'updated'
                changes = self._get_changes(old_values)
                if not changes:
                    return  # No changes to log
                
                description = f'{self.__class__.__name__} updated'
                metadata = {'changes': changes}
            
            # Create security log
            SecurityLog.objects.create(
                user=current_user,
                security_type=f'{self.__class__.__name__.lower()}_{action}',
                severity='medium',
                description=description,
                metadata={
                    **metadata,
                    'model': self.__class__.__name__,
                    'pk': self.pk
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging security change: {e}")
    
    def _log_security_deletion(self):
        """Log security-related deletions"""
        try:
            current_user = getattr(self, '_current_user', None)
            
            SecurityLog.objects.create(
                user=current_user,
                security_type=f'{self.__class__.__name__.lower()}_deleted',
                severity='high',
                description=f'{self.__class__.__name__} deleted',
                metadata={
                    'model': self.__class__.__name__,
                    'pk': self.pk,
                    'deleted_values': self._get_model_values()
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging security deletion: {e}")
    
    def _get_changes(self, old_values: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Get changes between old and new values"""
        changes = {}
        current_values = self._get_model_values()
        
        for field, old_value in old_values.items():
            new_value = current_values.get(field)
            if old_value != new_value:
                changes[field] = {
                    'old': str(old_value),
                    'new': str(new_value)
                }
        
        return changes
    
    def _get_model_values(self) -> Dict[str, Any]:
        """Get all model field values"""
        return {
            field.name: getattr(self, field.name)
            for field in self._meta.fields
        }


class RateLimitMixin:
    """Mixin for adding rate limiting to views"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limit_config = getattr(self, 'rate_limit_config', {})
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add rate limiting"""
        # Get rate limit configuration
        limit = self.rate_limit_config.get('limit', 100)
        window = self.rate_limit_config.get('window', 3600)  # 1 hour default
        identifier = self._get_rate_limit_identifier(request)
        
        # Check rate limit
        if RateLimiter.is_rate_limited(identifier, limit, window):
            return self._rate_limit_exceeded_response(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _get_rate_limit_identifier(self, request) -> str:
        """Get identifier for rate limiting"""
        # Use user ID if authenticated, otherwise IP
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        else:
            return f"ip:{SecurityUtils.get_client_ip(request)}"
    
    def _rate_limit_exceeded_response(self, request):
        """Response when rate limit is exceeded"""
        if hasattr(request, 'is_ajax') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.'
            }, status=429)
        
        return Response({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)


class SecurityHeadersMixin:
    """Mixin for adding security headers to responses"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add security headers"""
        response = super().dispatch(request, *args, **kwargs)
        
        # Add security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
        }
        
        for header, value in security_headers.items():
            response[header] = value
        
        return response


class SessionValidationMixin:
    """Mixin for validating user sessions"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to validate session"""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if session is still valid
        if not self._is_session_valid(request):
            return self._invalid_session_response(request)
        
        # Update session activity
        self._update_session_activity(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _is_session_valid(self, request) -> bool:
        """Check if user session is valid"""
        try:
            # Check session timeout
            session_timeout = getattr(request.user, 'session_timeout', 30)  # 30 minutes default
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                last_activity_time = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                if timezone.now() - last_activity_time > timedelta(minutes=session_timeout):
                    return False
            
            # Check concurrent sessions limit
            max_sessions = getattr(request.user, 'max_concurrent_sessions', 3)
            active_sessions = UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).count()
            
            if active_sessions > max_sessions:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False
    
    def _invalid_session_response(self, request):
        """Response for invalid session"""
        if hasattr(request, 'is_ajax') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Session expired',
                'message': 'Your session has expired. Please log in again.'
            }, status=401)
        
        # For regular requests, redirect to login
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    def _update_session_activity(self, request):
        """Update session activity timestamp"""
        try:
            request.session['last_activity'] = timezone.now().isoformat()
            request.session.save()
            
            # Update user session record
            session_key = request.session.session_key
            UserSession.objects.filter(
                user=request.user,
                session_key=session_key,
                is_active=True
            ).update(last_activity=timezone.now())
            
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")


class RiskAssessmentMixin:
    """Mixin for assessing user risk"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to assess user risk"""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        # Assess user risk
        risk_score = self._assess_user_risk(request)
        
        # Block high-risk users
        if risk_score > 80:
            return self._high_risk_response(request)
        
        # Add risk score to request for use by views
        request.risk_score = risk_score
        
        return super().dispatch(request, *args, **kwargs)
    
    def _assess_user_risk(self, request) -> float:
        """Assess user risk score"""
        try:
            # Get or create risk score
            risk_score_obj, created = RiskScore.objects.get_or_create(
                user=request.user,
                defaults={'current_score': 50}
            )
            
            # Update risk factors
            risk_factors = []
            
            # Check for suspicious factors
            ip_address = SecurityUtils.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # IP-based risk
            if not SecurityUtils.is_private_ip(ip_address):
                risk_factors.append('external_ip')
                risk_score_obj.current_score += 10
            
            # Time-based risk
            current_hour = timezone.now().hour
            if current_hour < 6 or current_hour > 22:
                risk_factors.append('unusual_time')
                risk_score_obj.current_score += 5
            
            # Session-based risk
            active_sessions = UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).count()
            
            if active_sessions > 2:
                risk_factors.append('multiple_sessions')
                risk_score_obj.current_score += 10
            
            # Update risk score
            risk_score_obj.risk_factors = risk_factors
            risk_score_obj.save()
            
            return risk_score_obj.current_score
            
        except Exception as e:
            logger.error(f"Error assessing user risk: {e}")
            return 50  # Default medium risk
    
    def _high_risk_response(self, request):
        """Response for high-risk users"""
        if hasattr(request, 'is_ajax') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Your account has been flagged for suspicious activity. Please contact support.'
            }, status=403)
        
        from django.shortcuts import render
        return render(request, 'security/high_risk_blocked.html', status=403)


class IpWhitelistMixin:
    """Mixin for IP whitelist validation"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_ips = getattr(self, 'allowed_ips', [])
        self.allowed_networks = getattr(self, 'allowed_networks', [])
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check IP whitelist"""
        client_ip = SecurityUtils.get_client_ip(request)
        
        if not self._is_ip_allowed(client_ip):
            return self._ip_blocked_response(request, client_ip)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed"""
        try:
            # Check specific IPs
            if ip in self.allowed_ips:
                return True
            
            # Check network ranges
            import ipaddress
            for network in self.allowed_networks:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(network):
                    return True
            
            # Allow private IPs by default
            if SecurityUtils.is_private_ip(ip):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking IP whitelist: {e}")
            return False
    
    def _ip_blocked_response(self, request, ip: str):
        """Response for blocked IPs"""
        # Log the blocked attempt
        SecurityLog.objects.create(
            security_type='ip_blocked',
            severity='high',
            description=f'IP {ip} blocked by whitelist',
            metadata={
                'ip_address': ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'path': request.path
            }
        )
        
        if hasattr(request, 'is_ajax') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Your IP address is not allowed to access this resource.'
            }, status=403)
        
        from django.shortcuts import render
        return render(request, 'security/ip_blocked.html', {'ip': ip}, status=403)


class SecurityLoggingMixin:
    """Mixin for comprehensive security logging"""
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add logging"""
        # Log request start
        self._log_security_request(request)
        
        try:
            response = super().dispatch(request, *args, **kwargs)
            
            # Log successful response
            self._log_security_response(request, response)
            
            return response
            
        except Exception as e:
            # Log error
            self._log_security_error(request, e)
            raise
    
    def _log_security_request(self, request):
        """Log incoming request"""
        try:
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='api_request',
                severity='info',
                description=f'{request.method} {request.path}',
                metadata={
                    'method': request.method,
                    'path': request.path,
                    'ip_address': SecurityUtils.get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'query_params': dict(request.GET)
                }
            )
        except Exception as e:
            logger.error(f"Error logging security request: {e}")
    
    def _log_security_response(self, request, response):
        """Log successful response"""
        try:
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='api_response',
                severity='info',
                description=f'{request.method} {request.path} - {response.status_code}',
                metadata={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'ip_address': SecurityUtils.get_client_ip(request)
                }
            )
        except Exception as e:
            logger.error(f"Error logging security response: {e}")
    
    def _log_security_error(self, request, error):
        """Log error"""
        try:
            SecurityLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                security_type='api_error',
                severity='error',
                description=f'{request.method} {request.path} - {str(error)}',
                metadata={
                    'method': request.method,
                    'path': request.path,
                    'error': str(error),
                    'ip_address': SecurityUtils.get_client_ip(request)
                }
            )
        except Exception as e:
            logger.error(f"Error logging security error: {e}")


class IsOwnerOrSecurityAdmin(BasePermission):
    """Permission class for object owners or security admins"""
    
    def has_object_permission(self, request, view, obj):
        # Security admins can access everything
        if request.user.is_staff or getattr(request.user, 'is_security_admin', False):
            return True
        
        # Check if user is owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object itself is the user
        if isinstance(obj, User):
            return obj == request.user
        
        return False


# Export all mixins and permissions
__all__ = [
    'SecurityAuditMixin',
    'RateLimitMixin',
    'SecurityHeadersMixin',
    'SessionValidationMixin',
    'RiskAssessmentMixin',
    'IpWhitelistMixin',
    'SecurityLoggingMixin',
    'IsSecurityAdmin',
    'IsOwnerOrSecurityAdmin'
]