"""
tasks/middleware/tenant_isolation.py
Tenant Isolation Middleware for SaaS Multi-Tenancy
"""
import logging
from typing import Dict, Any, Optional
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)

class TenantIsolationMiddleware:
    """
    Comprehensive tenant isolation middleware for SaaS platform.
    Ensures data separation and tenant context validation.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request with tenant isolation."""
        try:
            # Extract and validate tenant
            tenant_id = self._extract_tenant_id(request)
            
            if not tenant_id:
                return self._no_tenant_response()
            
            # Validate tenant exists and is active
            if not self._validate_tenant(tenant_id):
                return self._invalid_tenant_response(tenant_id)
            
            # Add tenant context to request
            request.tenant_id = tenant_id
            request.tenant_context = self._build_tenant_context(tenant_id)
            
            # Add tenant filtering
            self._apply_tenant_filtering(request, tenant_id)
            
            # Log tenant access for audit
            self._log_tenant_access(request, tenant_id)
            
            return None
            
        except Exception as e:
            logger.error(f"[TenantIsolation] Error: {e}")
            return JsonResponse({
                'error': 'Tenant processing failed',
                'error_code': 'TENANT_ERROR'
            }, status=500)
    
    def _extract_tenant_id(self, request) -> Optional[str]:
        """Extract tenant ID from multiple sources."""
        # Priority 1: Header (most secure)
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            return tenant_id.strip()
        
        # Priority 2: Subdomain
        host = request.get_host()
        if host and '.' in host:
            parts = host.split('.')
            if len(parts) >= 2:
                possible_tenant = parts[0]
                if possible_tenant not in ['www', 'api', 'app']:
                    return possible_tenant
        
        # Priority 3: URL parameter
        if hasattr(request, 'GET'):
            tenant_id = request.GET.get('tenant_id')
            if tenant_id:
                return tenant_id.strip()
        
        # Priority 4: User's default tenant
        if hasattr(request, 'user') and request.user.is_authenticated:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(pk=request.user.id)
            if hasattr(user, 'default_tenant_id'):
                return user.default_tenant_id
        
        return None
    
    def _validate_tenant(self, tenant_id: str) -> bool:
        """Validate tenant exists and is active."""
        try:
            from tenants.models import Tenant
            return Tenant.objects.filter(
                id=tenant_id,
                is_active=True,
                is_suspended=False
            ).exists()
        except Exception:
            return False
    
    def _build_tenant_context(self, tenant_id: str) -> Dict[str, Any]:
        """Build comprehensive tenant context."""
        try:
            from tenants.models import Tenant
            from django.core.cache import cache
            
            # Try cache first
            cache_key = f"tenant_context_{tenant_id}"
            context = cache.get(cache_key)
            
            if not context:
                tenant = Tenant.objects.get(id=tenant_id)
                context = {
                    'tenant_id': tenant_id,
                    'tenant_name': tenant.name,
                    'tenant_slug': tenant.slug,
                    'is_active': tenant.is_active,
                    'is_suspended': tenant.is_suspended,
                    'settings': tenant.settings or {},
                    'created_at': tenant.created_at.isoformat(),
                    'subscription_plan': tenant.subscription_plan or 'basic',
                    'resource_limits': tenant.resource_limits or {},
                    'features': tenant.features or [],
                }
                
                # Cache for 5 minutes
                cache.set(cache_key, context, timeout=300)
            
            return context
            
        except Exception as e:
            logger.error(f"[TenantIsolation] Error building context: {e}")
            return {'tenant_id': tenant_id}
    
    def _apply_tenant_filtering(self, request, tenant_id: str) -> None:
        """Apply tenant filtering to request context."""
        # This will be used by views to filter querysets
        request.tenant_filter = {
            'tenant_id': tenant_id,
            'applied_at': timezone.now().isoformat()
        }
    
    def _log_tenant_access(self, request, tenant_id: str) -> None:
        """Log tenant access for security audit."""
        try:
            access_log = {
                'tenant_id': tenant_id,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'client_ip': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'path': request.path,
                'method': request.method,
                'timestamp': timezone.now().isoformat(),
                'success': True
            }
            
            # Store in security audit log
            from django.core.cache import cache
            cache.set(
                f"tenant_access_{tenant_id}_{int(timezone.now().timestamp())}",
                access_log,
                timeout=86400  # 24 hours
            )
            
        except Exception as e:
            logger.error(f"[TenantIsolation] Error logging access: {e}")
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    def _no_tenant_response(self) -> JsonResponse:
        """Return response for missing tenant."""
        return JsonResponse({
            'error': 'Tenant ID required',
            'error_code': 'TENANT_REQUIRED',
            'details': {
                'message': 'Please provide tenant ID in X-Tenant-ID header or tenant_id parameter',
                'supported_methods': [
                    'Header: X-Tenant-ID: tenant123',
                    'Subdomain: tenant123.yourapp.com',
                    'Parameter: ?tenant_id=tenant123'
                ]
            }
        }, status=400)
    
    def _invalid_tenant_response(self, tenant_id: str) -> JsonResponse:
        """Return response for invalid tenant."""
        return JsonResponse({
            'error': 'Invalid tenant',
            'error_code': 'INVALID_TENANT',
            'details': {
                'tenant_id': tenant_id,
                'message': 'Tenant not found or suspended'
            }
        }, status=403)


class TenantQuerySetMixin:
    """
    Mixin for views to automatically apply tenant filtering.
    """
    
    def get_queryset(self):
        """
        Automatically filter queryset by tenant.
        """
        queryset = super().get_queryset()
        
        # Apply tenant filtering if available
        if hasattr(self.request, 'tenant_filter'):
            tenant_id = self.request.tenant_filter['tenant_id']
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset


class TenantPermissionMixin:
    """
    Mixin for tenant-specific permission checks.
    """
    
    def check_tenant_permission(self, permission: str) -> bool:
        """Check if user has permission for current tenant."""
        if not hasattr(self.request, 'tenant_context'):
            return False
        
        tenant_context = self.request.tenant_context
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Check tenant-specific permissions
        tenant_permissions = tenant_context.get('permissions', {})
        user_permissions = user.get_all_permissions()
        
        return permission in user_permissions and permission in tenant_permissions
