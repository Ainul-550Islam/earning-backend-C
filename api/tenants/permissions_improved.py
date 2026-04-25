"""
Tenant Permissions - Improved Version with Enhanced Security

This module contains comprehensive permission classes for tenant management
with advanced security features, role-based access control, and audit logging.
"""

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class BaseTenantPermission(permissions.BasePermission):
    """
    Base permission class for tenant-related permissions.
    
    Provides common functionality for tenant permission checks
    including caching and audit logging.
    """
    
    def get_tenant_from_request(self, request):
        """Extract tenant from request."""
        # Try to get tenant from middleware
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            # Try to get tenant from headers
            tenant_slug = request.META.get('HTTP_X_TENANT_SLUG')
            tenant_domain = request.META.get('HTTP_X_TENANT_DOMAIN')
            
            if tenant_slug:
                from .models_improved import Tenant
                tenant = Tenant.objects.filter(
                    slug=tenant_slug,
                    is_active=True,
                    is_deleted=False
                ).first()
            elif tenant_domain:
                from .models_improved import Tenant
                tenant = Tenant.objects.filter(
                    domain=tenant_domain,
                    is_active=True,
                    is_deleted=False
                ).first()
        
        return tenant
    
    def get_user_from_request(self, request):
        """Get authenticated user from request."""
        return getattr(request, 'user', None)
    
    def log_permission_check(self, request, action, result, tenant=None, user=None):
        """Log permission check for audit purposes."""
        try:
            from .models_improved import TenantAuditLog
            
            if tenant:
                tenant.audit_log(
                    action=f'permission_check_{action}',
                    details={
                        'result': result,
                        'endpoint': request.path,
                        'method': request.method,
                        'ip_address': self.get_client_ip(request),
                    },
                    user=user or self.get_user_from_request(request)
                )
        except Exception as e:
            logger.error(f"Failed to log permission check: {e}")
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def check_rate_limit(self, request, tenant, limit_key, max_requests=100):
        """Check rate limiting for tenant operations."""
        try:
            cache_key = f"rate_limit:{limit_key}:{tenant.id}:{self.get_client_ip(request)}"
            
            # Get current count
            count = cache.get(cache_key, 0)
            
            if count >= max_requests:
                return False
            
            # Increment count
            cache.set(cache_key, count + 1, timeout=3600)  # 1 hour
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Allow on error


class IsTenantOwner(BaseTenantPermission):
    """
    Permission class to check if user is the owner of the tenant.
    
    Only allows tenant owners to access their own tenant resources.
    """
    
    message = _("You must be the tenant owner to access this resource.")
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific object."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from object
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'tenant_owner', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        # Direct tenant object
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        # Object with tenant relationship
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        # Object with owner relationship (User model)
        if hasattr(obj, 'tenant') or hasattr(obj, 'owned_tenants'):
            if hasattr(obj, 'owned_tenants'):
                # User object - get first owned tenant
                return obj.owned_tenants.first()
        
        return None
    
    def has_permission(self, request, view):
        """Check if user has permission for the view."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'tenant_owner', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner


class IsTenantMember(BaseTenantPermission):
    """
    Permission class to check if user is a member of the tenant.
    
    Allows tenant owners and members to access tenant resources.
    """
    
    message = _("You must be a member of the tenant to access this resource.")
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific object."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from object
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return False
        
        # Check if user is owner
        if tenant.owner == user:
            return True
        
        # Check if user is a member (you may need to implement this logic)
        # This assumes you have a tenant membership system
        is_member = self.is_user_member(user, tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'tenant_member', 
            is_member, 
            tenant, 
            user
        )
        
        return is_member
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        return None
    
    def is_user_member(self, user, tenant):
        """Check if user is a member of the tenant."""
        # This is a placeholder - implement based on your membership model
        # For now, only owners are considered members
        return tenant.owner == user
    
    def has_permission(self, request, view):
        """Check if user has permission for the view."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is owner
        if tenant.owner == user:
            return True
        
        # Check if user is a member
        is_member = self.is_user_member(user, tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'tenant_member', 
            is_member, 
            tenant, 
            user
        )
        
        return is_member


class IsActiveTenant(BaseTenantPermission):
    """
    Permission class to check if tenant is active.
    
    Only allows access to active tenants that are not deleted.
    """
    
    message = _("This tenant is not active.")
    
    def has_object_permission(self, request, view, obj):
        """Check if tenant is active for specific object."""
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return True  # No tenant to check
        
        is_active = tenant.is_active and not tenant.is_deleted
        
        # Log permission check
        self.log_permission_check(
            request, 
            'active_tenant', 
            is_active, 
            tenant
        )
        
        return is_active
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        return None
    
    def has_permission(self, request, view):
        """Check if tenant is active for the view."""
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to check
        
        is_active = tenant.is_active and not tenant.is_deleted
        
        # Log permission check
        self.log_permission_check(
            request, 
            'active_tenant', 
            is_active, 
            tenant
        )
        
        return is_active


class IsNotSuspended(BaseTenantPermission):
    """
    Permission class to check if tenant is not suspended.
    
    Only allows access to tenants that are not suspended.
    """
    
    message = _("This tenant is suspended.")
    
    def has_object_permission(self, request, view, obj):
        """Check if tenant is not suspended for specific object."""
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return True  # No tenant to check
        
        is_not_suspended = not tenant.is_suspended
        
        # Log permission check
        self.log_permission_check(
            request, 
            'not_suspended', 
            is_not_suspended, 
            tenant
        )
        
        return is_not_suspended
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        return None
    
    def has_permission(self, request, view):
        """Check if tenant is not suspended for the view."""
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to check
        
        is_not_suspended = not tenant.is_suspended
        
        # Log permission check
        self.log_permission_check(
            request, 
            'not_suspended', 
            is_not_suspended, 
            tenant
        )
        
        return is_not_suspended


class HasValidSubscription(BaseTenantPermission):
    """
    Permission class to check if tenant has valid subscription.
    
    Only allows access to tenants with active subscriptions or trials.
    """
    
    message = _("Your subscription is not active.")
    
    def has_object_permission(self, request, view, obj):
        """Check if tenant has valid subscription for specific object."""
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return True  # No tenant to check
        
        has_valid_subscription = self.check_subscription(tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'valid_subscription', 
            has_valid_subscription, 
            tenant
        )
        
        return has_valid_subscription
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        return None
    
    def check_subscription(self, tenant):
        """Check if tenant has valid subscription."""
        try:
            billing = tenant.get_billing()
            return billing.is_active
        except Exception:
            return False
    
    def has_permission(self, request, view):
        """Check if tenant has valid subscription for the view."""
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to check
        
        has_valid_subscription = self.check_subscription(tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'valid_subscription', 
            has_valid_subscription, 
            tenant
        )
        
        return has_valid_subscription


class IsSuperAdminOrTenantOwner(BaseTenantPermission):
    """
    Combined permission class for superadmins or tenant owners.
    
    Allows superadmins to access all tenants and owners to access their own.
    """
    
    message = _("You must be a super admin or tenant owner to access this resource.")
    
    def has_object_permission(self, request, view, obj):
        """Check if user is superadmin or tenant owner."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from object
        tenant = self.get_tenant_from_object(obj)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'superadmin_or_owner', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner
    
    def get_tenant_from_object(self, obj):
        """Extract tenant from object."""
        if hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            return obj
        
        if hasattr(obj, 'tenant'):
            return obj.tenant
        
        return None
    
    def has_permission(self, request, view):
        """Check if user is superadmin or tenant owner."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'superadmin_or_owner', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner


class CanManageUsers(BaseTenantPermission):
    """
    Permission class to check if user can manage tenant users.
    
    Only allows tenant owners and superadmins to manage users.
    """
    
    message = _("You don't have permission to manage users.")
    
    def has_permission(self, request, view):
        """Check if user can manage users."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers can manage all users
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'manage_users', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner


class CanManageBilling(BaseTenantPermission):
    """
    Permission class to check if user can manage billing.
    
    Only allows tenant owners and superadmins to manage billing.
    """
    
    message = _("You don't have permission to manage billing.")
    
    def has_permission(self, request, view):
        """Check if user can manage billing."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers can manage all billing
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        is_owner = tenant.owner == user
        
        # Log permission check
        self.log_permission_check(
            request, 
            'manage_billing', 
            is_owner, 
            tenant, 
            user
        )
        
        return is_owner


class CanViewAnalytics(BaseTenantPermission):
    """
    Permission class to check if user can view analytics.
    
    Allows tenant owners, superadmins, and users with analytics permissions.
    """
    
    message = _("You don't have permission to view analytics.")
    
    def has_permission(self, request, view):
        """Check if user can view analytics."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers can view all analytics
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if user is the owner
        if tenant.owner == user:
            return True
        
        # Check if analytics is enabled for tenant
        try:
            settings = tenant.get_settings()
            if not settings.enable_analytics:
                return False
        except Exception:
            return False
        
        # Check if user has analytics permission (you may need to implement this)
        has_permission = self.has_analytics_permission(user, tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'view_analytics', 
            has_permission, 
            tenant, 
            user
        )
        
        return has_permission
    
    def has_analytics_permission(self, user, tenant):
        """Check if user has analytics permission."""
        # This is a placeholder - implement based on your permission system
        # For now, only owners can view analytics
        return tenant.owner == user


class CanAccessAPI(BaseTenantPermission):
    """
    Permission class to check if user can access API.
    
    Checks if API access is enabled for tenant and user has permission.
    """
    
    message = _("API access is not enabled for this tenant.")
    
    def has_permission(self, request, view):
        """Check if user can access API."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers can always access API
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if API access is enabled
        try:
            settings = tenant.get_settings()
            if not settings.enable_api_access:
                return False
        except Exception:
            return False
        
        # Check rate limiting
        if not self.check_rate_limit(request, tenant, 'api_access', 1000):
            return False
        
        # Check if user has API access permission
        has_permission = self.has_api_permission(user, tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'api_access', 
            has_permission, 
            tenant, 
            user
        )
        
        return has_permission
    
    def has_api_permission(self, user, tenant):
        """Check if user has API permission."""
        # This is a placeholder - implement based on your permission system
        # For now, owners and members can access API
        if tenant.owner == user:
            return True
        
        # Check if user is a member
        return self.is_user_member(user, tenant)
    
    def is_user_member(self, user, tenant):
        """Check if user is a member of the tenant."""
        # This is a placeholder - implement based on your membership model
        return tenant.owner == user


class TenantFeaturePermission(BaseTenantPermission):
    """
    Permission class to check if tenant has specific feature enabled.
    
    Checks if a specific feature is enabled for the tenant.
    """
    
    def __init__(self, feature_name):
        self.feature_name = feature_name
        self.message = _(f"The {feature_name} feature is not enabled for this tenant.")
    
    def has_permission(self, request, view):
        """Check if tenant has feature enabled."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers bypass feature checks
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return False
        
        # Check if feature is enabled
        has_feature = tenant.has_feature(self.feature_name)
        
        # Log permission check
        self.log_permission_check(
            request, 
            f'feature_{self.feature_name}', 
            has_feature, 
            tenant, 
            user
        )
        
        return has_feature


class TenantRateLimitPermission(BaseTenantPermission):
    """
    Permission class to check rate limiting for tenant operations.
    
    Implements rate limiting based on tenant and user.
    """
    
    def __init__(self, max_requests=100, window_minutes=60):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        self.message = _(f"Rate limit exceeded. Maximum {max_requests} requests per {window_minutes} minutes.")
    
    def has_permission(self, request, view):
        """Check rate limit."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers bypass rate limits
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to rate limit
        
        # Check rate limit
        if not self.check_rate_limit(request, tenant, 'general', self.max_requests):
            return False
        
        return True


class TenantIPWhitelistPermission(BaseTenantPermission):
    """
    Permission class to check if IP address is whitelisted for tenant.
    
    Only allows access from whitelisted IP addresses.
    """
    
    message = _("Your IP address is not whitelisted for this tenant.")
    
    def has_permission(self, request, view):
        """Check if IP is whitelisted."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers bypass IP whitelist
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to check
        
        # Get client IP
        client_ip = self.get_client_ip(request)
        
        # Check if IP is whitelisted
        is_whitelisted = self.is_ip_whitelisted(client_ip, tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'ip_whitelist', 
            is_whitelisted, 
            tenant, 
            user
        )
        
        return is_whitelisted
    
    def is_ip_whitelisted(self, ip, tenant):
        """Check if IP is whitelisted for tenant."""
        # This is a placeholder - implement based on your IP whitelist system
        # For now, allow all IPs
        return True


class TenantBusinessHoursPermission(BaseTenantPermission):
    """
    Permission class to check if access is within business hours.
    
    Only allows access during configured business hours.
    """
    
    message = _("Access is only allowed during business hours.")
    
    def has_permission(self, request, view):
        """Check if current time is within business hours."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers bypass business hours check
        if user.is_superuser:
            return True
        
        # Get tenant from request
        tenant = self.get_tenant_from_request(request)
        
        if not tenant:
            return True  # No tenant to check
        
        # Check if current time is within business hours
        is_business_hours = self.is_within_business_hours(tenant)
        
        # Log permission check
        self.log_permission_check(
            request, 
            'business_hours', 
            is_business_hours, 
            tenant, 
            user
        )
        
        return is_business_hours
    
    def is_within_business_hours(self, tenant):
        """Check if current time is within business hours."""
        # This is a placeholder - implement based on your business hours configuration
        # For now, allow all times
        return True


# Combined permission classes
class TenantOwnerOrSuperAdmin(IsSuperAdminOrTenantOwner):
    """Alias for IsSuperAdminOrTenantOwner."""
    pass


class TenantMemberOrSuperAdmin(IsTenantMember):
    """Modified to allow superadmins."""
    
    def has_permission(self, request, view):
        """Check if user is superadmin or tenant member."""
        user = self.get_user_from_request(request)
        
        if not user or user.is_anonymous:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        return super().has_permission(request, view)


class ActiveTenantOwnerOrSuperAdmin(IsSuperAdminOrTenantOwner, IsActiveTenant):
    """Combined permission for active tenant owners or superadmins."""
    pass


class ValidSubscriptionTenantOwnerOrSuperAdmin(IsSuperAdminOrTenantOwner, HasValidSubscription):
    """Combined permission for valid subscription tenant owners or superadmins."""
    pass


class FullTenantPermission(IsSuperAdminOrTenantOwner, IsActiveTenant, IsNotSuspended, HasValidSubscription):
    """Full permission check for tenant access."""
    pass


# Feature-specific permissions
class ReferralFeaturePermission(TenantFeaturePermission):
    """Permission for referral feature."""
    def __init__(self):
        super().__init__('enable_referral')


class OfferwallFeaturePermission(TenantFeaturePermission):
    """Permission for offerwall feature."""
    def __init__(self):
        super().__init__('enable_offerwall')


class KYCFeaturePermission(TenantFeaturePermission):
    """Permission for KYC feature."""
    def __init__(self):
        super().__init__('enable_kyc')


class LeaderboardFeaturePermission(TenantFeaturePermission):
    """Permission for leaderboard feature."""
    def __init__(self):
        super().__init__('enable_leaderboard')


class ChatFeaturePermission(TenantFeaturePermission):
    """Permission for chat feature."""
    def __init__(self):
        super().__init__('enable_chat')


class PushNotificationFeaturePermission(TenantFeaturePermission):
    """Permission for push notification feature."""
    def __init__(self):
        super().__init__('enable_push_notifications')


class AnalyticsFeaturePermission(TenantFeaturePermission):
    """Permission for analytics feature."""
    def __init__(self):
        super().__init__('enable_analytics')
