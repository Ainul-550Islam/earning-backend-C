"""
Tenant Middleware - Improved Version with Enhanced Security and Features

This module contains comprehensive middleware for tenant management
with advanced security, proper request handling, and extensive functionality.
"""

import logging
import json
from typing import Optional, Dict, Any
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
import hashlib
import hmac

from .models_improved import Tenant
from .permissions_improved import BaseTenantPermission
from .services_improved import tenant_security_service

logger = logging.getLogger(__name__)

User = get_user_model()


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to identify and set the current tenant for requests.
    
    This middleware handles tenant identification from various sources
    including subdomains, headers, and URL parameters.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.tenant_cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 300)
        super().__init__(get_response)
    
    def process_request(self, request):
        """Identify and set tenant for the request."""
        tenant = None
        
        # Try different methods to identify tenant
        tenant = self._get_tenant_from_subdomain(request)
        if not tenant:
            tenant = self._get_tenant_from_header(request)
        if not tenant:
            tenant = self._get_tenant_from_url(request)
        if not tenant:
            tenant = self._get_tenant_from_session(request)
        
        # Set tenant on request
        if tenant:
            request.tenant = tenant
            request.tenant_id = str(tenant.id)
            
            # Add tenant context to template
            if hasattr(request, 'context'):
                request.context['tenant'] = tenant
        else:
            # Set default tenant if configured
            default_tenant_id = getattr(settings, 'DEFAULT_TENANT_ID', None)
            if default_tenant_id:
                try:
                    default_tenant = Tenant.objects.get(id=default_tenant_id)
                    request.tenant = default_tenant
                    request.tenant_id = str(default_tenant.id)
                except Tenant.DoesNotExist:
                    pass
    
    def _get_tenant_from_subdomain(self, request) -> Optional[Tenant]:
        """Get tenant from subdomain."""
        host = request.get_host()
        
        # Extract subdomain
        parts = host.split('.')
        if len(parts) > 2:
            subdomain = parts[0]
            
            # Cache key
            cache_key = f'tenant_subdomain_{subdomain}'
            tenant = cache.get(cache_key)
            
            if not tenant:
                try:
                    tenant = Tenant.objects.get(
                        slug=subdomain,
                        is_active=True,
                        is_deleted=False
                    )
                    cache.set(cache_key, tenant, self.tenant_cache_timeout)
                except Tenant.DoesNotExist:
                    cache.set(cache_key, None, self.tenant_cache_timeout)  # Cache negative result
            
            return tenant
        
        return None
    
    def _get_tenant_from_header(self, request) -> Optional[Tenant]:
        """Get tenant from HTTP headers."""
        # Try different header names
        header_names = [
            'HTTP_X_TENANT_SLUG',
            'HTTP_X_TENANT_ID',
            'HTTP_TENANT_SLUG',
            'HTTP_TENANT_ID',
            'X-Tenant-Slug',
            'X-Tenant-ID',
            'Tenant-Slug',
            'Tenant-ID'
        ]
        
        for header_name in header_names:
            tenant_value = request.META.get(header_name)
            if tenant_value:
                # Try to get by slug first, then by ID
                tenant = self._get_tenant_by_identifier(tenant_value)
                if tenant:
                    return tenant
        
        return None
    
    def _get_tenant_from_url(self, request) -> Optional[Tenant]:
        """Get tenant from URL parameters."""
        # Check for tenant slug in URL
        if hasattr(request, 'resolver_match') and request.resolver_match:
            kwargs = request.resolver_match.kwargs
            
            # Look for common tenant parameter names
            tenant_params = ['tenant_slug', 'tenant', 'slug', 'tenant_id']
            
            for param in tenant_params:
                if param in kwargs:
                    tenant_value = kwargs[param]
                    tenant = self._get_tenant_by_identifier(tenant_value)
                    if tenant:
                        return tenant
        
        return None
    
    def _get_tenant_from_session(self, request) -> Optional[Tenant]:
        """Get tenant from session."""
        if hasattr(request, 'session') and 'tenant_id' in request.session:
            tenant_id = request.session['tenant_id']
            
            cache_key = f'tenant_session_{tenant_id}'
            tenant = cache.get(cache_key)
            
            if not tenant:
                try:
                    tenant = Tenant.objects.get(
                        id=tenant_id,
                        is_active=True,
                        is_deleted=False
                    )
                    cache.set(cache_key, tenant, self.tenant_cache_timeout)
                except Tenant.DoesNotExist:
                    # Clear invalid tenant from session
                    del request.session['tenant_id']
                    cache.set(cache_key, None, self.tenant_cache_timeout)
            
            return tenant
        
        return None
    
    def _get_tenant_by_identifier(self, identifier: str) -> Optional[Tenant]:
        """Get tenant by identifier (slug or ID)."""
        cache_key = f'tenant_identifier_{identifier}'
        tenant = cache.get(cache_key)
        
        if not tenant:
            try:
                # Try to get by slug first
                tenant = Tenant.objects.get(
                    slug=identifier,
                    is_active=True,
                    is_deleted=False
                )
            except Tenant.DoesNotExist:
                try:
                    # Try to get by ID
                    tenant = Tenant.objects.get(
                        id=identifier,
                        is_active=True,
                        is_deleted=False
                    )
                except Tenant.DoesNotExist:
                    tenant = None
            
            cache.set(cache_key, tenant, self.tenant_cache_timeout)
        
        return tenant


class TenantSecurityMiddleware(MiddlewareMixin):
    """
    Middleware for tenant security checks and monitoring.
    
    This middleware handles security checks including rate limiting,
    IP whitelisting, and security event logging.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.security_service = tenant_security_service
        super().__init__(get_response)
    
    def process_request(self, request):
        """Perform security checks on the request."""
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Get tenant if available
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Check rate limiting
            if not self._check_rate_limit(request, tenant, client_ip):
                return self._rate_limit_response(request)
            
            # Check IP whitelist if enabled
            if getattr(settings, 'TENANT_IP_WHITELIST_ENABLED', False):
                if not self._check_ip_whitelist(request, tenant, client_ip):
                    return self._ip_blocked_response(request)
            
            # Check business hours if enabled
            if getattr(settings, 'TENANT_BUSINESS_HOURS_ENABLED', False):
                if not self._check_business_hours(request, tenant):
                    return self._business_hours_response(request)
            
            # Log security event
            self._log_security_event(request, tenant, client_ip)
        
        return None
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def _check_rate_limit(self, request, tenant: Tenant, client_ip: str) -> bool:
        """Check if request is within rate limits."""
        # Get rate limit configuration
        max_requests = getattr(settings, 'TENANT_RATE_LIMIT_REQUESTS', 1000)
        window_minutes = getattr(settings, 'TENANT_RATE_LIMIT_WINDOW', 60)
        
        # Check rate limit
        return self.security_service.check_rate_limit(
            tenant, 'general', client_ip, max_requests
        )
    
    def _check_ip_whitelist(self, request, tenant: Tenant, client_ip: str) -> bool:
        """Check if IP is whitelisted for tenant."""
        # Get IP whitelist from tenant settings
        try:
            settings = tenant.get_settings()
            ip_whitelist = getattr(settings, 'ip_whitelist', [])
            
            if not ip_whitelist:
                return True  # No whitelist configured
            
            return client_ip in ip_whitelist
        except:
            return True  # Allow on error
    
    def _check_business_hours(self, request, tenant: Tenant) -> bool:
        """Check if current time is within business hours."""
        try:
            settings = tenant.get_settings()
            business_hours = getattr(settings, 'business_hours', {})
            
            if not business_hours:
                return True  # No business hours configured
            
            current_time = timezone.now()
            current_hour = current_time.hour
            current_weekday = current_time.weekday()  # 0 = Monday, 6 = Sunday
            
            # Check if current day is enabled
            day_enabled = business_hours.get('days', {}).get(str(current_weekday), True)
            if not day_enabled:
                return False
            
            # Check if current hour is within business hours
            start_hour = business_hours.get('start_hour', 9)
            end_hour = business_hours.get('end_hour', 17)
            
            return start_hour <= current_hour < end_hour
        except:
            return True  # Allow on error
    
    def _log_security_event(self, request, tenant: Tenant, client_ip: str):
        """Log security event for monitoring."""
        try:
            # Get user if authenticated
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                user_identifier = user.email
            else:
                user_identifier = 'anonymous'
            
            # Log security event
            self.security_service.log_security_event(
                tenant,
                'request_access',
                {
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'user_identifier': user_identifier,
                },
                user if user and user.is_authenticated else None
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    def _rate_limit_response(self, request) -> JsonResponse:
        """Return rate limit exceeded response."""
        return JsonResponse({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'code': 'RATE_LIMIT_EXCEEDED'
        }, status=429)
    
    def _ip_blocked_response(self, request) -> JsonResponse:
        """Return IP blocked response."""
        return JsonResponse({
            'error': 'Access denied',
            'message': 'Your IP address is not allowed to access this resource.',
            'code': 'IP_BLOCKED'
        }, status=403)
    
    def _business_hours_response(self, request) -> JsonResponse:
        """Return business hours response."""
        return JsonResponse({
            'error': 'Access denied',
            'message': 'Access is only allowed during business hours.',
            'code': 'BUSINESS_HOURS'
        }, status=403)


class TenantContextMiddleware(MiddlewareMixin):
    """
    Middleware to add tenant context to requests and templates.
    
    This middleware adds tenant-specific context to make tenant
    information available throughout the application.
    """
    
    def process_request(self, request):
        """Add tenant context to request."""
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Add tenant context to request
            request.tenant_context = {
                'id': str(tenant.id),
                'name': tenant.name,
                'slug': tenant.slug,
                'domain': tenant.domain,
                'plan': tenant.plan,
                'status': tenant.status,
                'is_active': tenant.is_active,
                'primary_color': tenant.primary_color,
                'secondary_color': tenant.secondary_color,
                'logo_url': tenant.get_logo_url(request),
                'timezone': tenant.timezone,
                'currency_code': tenant.currency_code,
                'country_code': tenant.country_code,
            }
            
            # Add feature flags
            try:
                settings = tenant.get_settings()
                request.tenant_context['features'] = {
                    'enable_referral': settings.enable_referral,
                    'enable_offerwall': settings.enable_offerwall,
                    'enable_kyc': settings.enable_kyc,
                    'enable_leaderboard': settings.enable_leaderboard,
                    'enable_chat': settings.enable_chat,
                    'enable_push_notifications': settings.enable_push_notifications,
                    'enable_analytics': settings.enable_analytics,
                    'enable_api_access': settings.enable_api_access,
                }
            except:
                request.tenant_context['features'] = {}
            
            # Add billing information
            try:
                billing = tenant.get_billing()
                request.tenant_context['billing'] = {
                    'status': billing.status,
                    'is_active': billing.is_active,
                    'is_past_due': billing.is_past_due,
                    'trial_active': tenant.is_trial_active,
                    'trial_days_remaining': tenant.days_until_trial_expires,
                    'user_limit': tenant.max_users,
                    'user_limit_reached': tenant.is_user_limit_reached(),
                }
            except:
                request.tenant_context['billing'] = {}
    
    def process_template_response(self, request, response):
        """Add tenant context to template response."""
        if hasattr(response, 'context_data'):
            tenant_context = getattr(request, 'tenant_context', {})
            if tenant_context:
                response.context_data['tenant'] = tenant_context
        
        return response


class TenantAuditMiddleware(MiddlewareMixin):
    """
    Middleware to audit tenant-related requests.
    
    This middleware logs important tenant-related requests for
    security and compliance purposes.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.audit_exempt_paths = getattr(settings, 'TENANT_AUDIT_EXEMPT_PATHS', [
            '/health/',
            '/static/',
            '/media/',
            '/favicon.ico',
        ])
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Audit the request after response is generated."""
        # Skip audit for exempt paths
        if any(request.path.startswith(path) for path in self.audit_exempt_paths):
            return response
        
        # Only audit tenant-related requests
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return response
        
        # Only audit certain response codes
        if response.status_code not in [200, 201, 400, 401, 403, 404, 500]:
            return response
        
        try:
            # Log audit entry
            self._audit_request(request, response, tenant)
        except Exception as e:
            logger.error(f"Failed to audit request: {e}")
        
        return response
    
    def _audit_request(self, request, response, tenant: Tenant):
        """Audit the request."""
        # Get user information
        user = getattr(request, 'user', None)
        user_email = 'anonymous'
        if user and user.is_authenticated:
            user_email = user.email
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Determine audit action based on request
        action = self._get_audit_action(request, response)
        
        # Create audit log entry
        tenant.audit_log(
            action=action,
            details={
                'path': request.path,
                'method': request.method,
                'status_code': response.status_code,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_size': len(str(request.body)) if hasattr(request, 'body') else 0,
                'response_size': len(response.content) if hasattr(response, 'content') else 0,
            },
            user=user if user and user.is_authenticated else None
        )
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def _get_audit_action(self, request, response) -> str:
        """Determine audit action based on request and response."""
        method = request.method
        path = request.path
        
        # Determine action based on HTTP method and path
        if method == 'GET':
            if '/admin/' in path:
                return 'admin_access'
            elif '/api/' in path:
                return 'api_access'
            else:
                return 'page_access'
        elif method == 'POST':
            if '/api/' in path:
                return 'api_create'
            else:
                return 'form_submit'
        elif method == 'PUT' or method == 'PATCH':
            return 'api_update'
        elif method == 'DELETE':
            return 'api_delete'
        else:
            return 'request_access'


class TenantMaintenanceMiddleware(MiddlewareMixin):
    """
    Middleware to handle tenant maintenance mode.
    
    This middleware checks if a tenant is in maintenance mode
    and returns appropriate responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.maintenance_exempt_paths = getattr(settings, 'TENANT_MAINTENANCE_EXEMPT_PATHS', [
            '/health/',
            '/maintenance/',
            '/admin/',
        ])
        super().__init__(get_response)
    
    def process_request(self, request):
        """Check if tenant is in maintenance mode."""
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            return None
        
        # Skip maintenance check for exempt paths
        if any(request.path.startswith(path) for path in self.maintenance_exempt_paths):
            return None
        
        # Check if tenant is in maintenance mode
        try:
            settings = tenant.get_settings()
            if getattr(settings, 'maintenance_mode', False):
                return self._maintenance_response(request, tenant)
        except:
            pass
        
        return None
    
    def _maintenance_response(self, request, tenant) -> JsonResponse:
        """Return maintenance mode response."""
        return JsonResponse({
            'error': 'Maintenance mode',
            'message': 'This tenant is currently under maintenance. Please try again later.',
            'code': 'MAINTENANCE_MODE',
            'tenant': tenant.name
        }, status=503)


class TenantCorsMiddleware(MiddlewareMixin):
    """
    Middleware to handle CORS for tenant-specific requests.
    
    This middleware adds CORS headers based on tenant configuration.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Add CORS headers based on tenant configuration."""
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            return response
        
        try:
            settings = tenant.get_settings()
            cors_origins = getattr(settings, 'cors_origins', [])
            
            if cors_origins:
                origin = request.META.get('HTTP_ORIGIN', '')
                
                # Check if origin is allowed
                if origin in cors_origins or '*' in cors_origins:
                    response['Access-Control-Allow-Origin'] = origin
                    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Tenant-Slug, X-Tenant-ID'
                    response['Access-Control-Allow-Credentials'] = 'true'
                    response['Access-Control-Max-Age'] = '86400'
        except:
            pass
        
        return response


class TenantCacheMiddleware(MiddlewareMixin):
    """
    Middleware to handle tenant-specific caching.
    
    This middleware adds cache headers and handles cache invalidation
    for tenant-specific content.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_response(self, request, response):
        """Add cache headers based on tenant configuration."""
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            return response
        
        try:
            settings = tenant.get_settings()
            cache_timeout = getattr(settings, 'cache_timeout', 300)
            
            # Add cache headers for successful GET requests
            if request.method == 'GET' and response.status_code == 200:
                response['Cache-Control'] = f'public, max-age={cache_timeout}'
                response['Vary'] = 'Accept, Accept-Encoding, X-Tenant-Slug'
                
                # Add ETag if not present
                if 'ETag' not in response:
                    content = response.content
                    etag = f'"{hashlib.md5(content).hexdigest()}"'
                    response['ETag'] = etag
        except:
            pass
        
        return response


# Middleware factory for easy configuration
def get_tenant_middleware():
    """
    Get the complete tenant middleware stack.
    
    Returns:
        List of middleware classes in order
    """
    return [
        TenantMiddleware,
        TenantSecurityMiddleware,
        TenantContextMiddleware,
        TenantMaintenanceMiddleware,
        TenantCorsMiddleware,
        TenantCacheMiddleware,
        TenantAuditMiddleware,
    ]


# Individual middleware exports
__all__ = [
    'TenantMiddleware',
    'TenantSecurityMiddleware',
    'TenantContextMiddleware',
    'TenantAuditMiddleware',
    'TenantMaintenanceMiddleware',
    'TenantCorsMiddleware',
    'TenantCacheMiddleware',
    'get_tenant_middleware',
]
