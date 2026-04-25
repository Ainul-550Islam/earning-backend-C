"""
Custom Permissions for Tenant Management System

This module contains custom permission classes for tenant management operations
including tenant-level permissions, feature-based permissions, and role-based access control.
"""

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from ..models.core import Tenant


class IsTenantOwner(permissions.BasePermission):
    """
    Permission class to check if user is the owner of the tenant.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return tenant.owner == request.user or request.user.is_staff


class IsTenantMember(permissions.BasePermission):
    """
    Permission class to check if user is a member of the tenant.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        # Check if user is owner
        if tenant.owner == request.user:
            return True
        
        # Check if user is staff
        if request.user.is_staff:
            return True
        
        # Check if user is in tenant members (if you have a member relationship)
        # This would require a TenantMember model or similar
        return False


class IsActiveTenant(permissions.BasePermission):
    """
    Permission class to check if tenant is active.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return True
        
        return tenant.is_active and not tenant.is_deleted


class IsNotSuspended(permissions.BasePermission):
    """
    Permission class to check if tenant is not suspended.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return True
        
        return not tenant.is_suspended


class HasValidSubscription(permissions.BasePermission):
    """
    Permission class to check if tenant has valid subscription.
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return True
        
        # Check if tenant has active billing
        if hasattr(tenant, 'billing'):
            billing = tenant.billing
            if billing:
                return billing.status in ['active', 'trial']
        
        return True


class CanManageTenant(permissions.BasePermission):
    """
    Permission class to check if user can manage tenant operations.
    """
    
    def has_permission(self, request, view):
        # Staff users can manage all tenants
        if request.user.is_staff:
            return True
        
        # Check if user has tenant management permission
        return request.user.has_perm('tenants.manage_tenant')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can manage all tenants
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return tenant.owner == request.user


class CanManageBilling(permissions.BasePermission):
    """
    Permission class to check if user can manage billing operations.
    """
    
    def has_permission(self, request, view):
        # Staff users can manage all billing
        if request.user.is_staff:
            return True
        
        # Check if user has billing management permission
        return request.user.has_perm('tenants.manage_billing')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can manage all billing
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        else:
            return False
        
        return tenant.owner == request.user


class CanManageSecurity(permissions.BasePermission):
    """
    Permission class to check if user can manage security operations.
    """
    
    def has_permission(self, request, view):
        # Staff users can manage all security
        if request.user.is_staff:
            return True
        
        # Check if user has security management permission
        return request.user.has_perm('tenants.manage_security')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can manage all security
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        else:
            return False
        
        return tenant.owner == request.user


class CanManageAnalytics(permissions.BasePermission):
    """
    Permission class to check if user can manage analytics operations.
    """
    
    def has_permission(self, request, view):
        # Staff users can manage all analytics
        if request.user.is_staff:
            return True
        
        # Check if user has analytics management permission
        return request.user.has_perm('tenants.manage_analytics')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can manage all analytics
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        else:
            return False
        
        return tenant.owner == request.user


class CanViewAnalytics(permissions.BasePermission):
    """
    Permission class to check if user can view analytics.
    """
    
    def has_permission(self, request, view):
        # Staff users can view all analytics
        if request.user.is_staff:
            return True
        
        # Check if user has analytics view permission
        return request.user.has_perm('tenants.view_analytics')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can view all analytics
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        else:
            return False
        
        return tenant.owner == request.user


class CanManageAPIKeys(permissions.BasePermission):
    """
    Permission class to check if user can manage API keys.
    """
    
    def has_permission(self, request, view):
        # Staff users can manage all API keys
        if request.user.is_staff:
            return True
        
        # Check if user has API key management permission
        return request.user.has_perm('tenants.manage_api_keys')
    
    def has_object_permission(self, request, view, obj):
        # Staff users can manage all API keys
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        else:
            return False
        
        return tenant.owner == request.user


class HasFeatureAccess(permissions.BasePermission):
    """
    Permission class to check if tenant has access to a specific feature.
    """
    
    def __init__(self, feature_name):
        self.feature_name = feature_name
    
    def has_permission(self, request, view):
        # Staff users always have access
        if request.user.is_staff:
            return True
        
        # Get tenant from request (assuming it's set in middleware)
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Check if tenant has the required feature
        return self._check_feature_access(tenant, self.feature_name)
    
    def has_object_permission(self, request, view, obj):
        # Staff users always have access
        if request.user.is_staff:
            return True
        
        # Get tenant from object
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return self._check_feature_access(tenant, self.feature_name)
    
    def _check_feature_access(self, tenant, feature_name):
        """Check if tenant has access to the specified feature."""
        # This would depend on your feature flag system
        # For now, return True as a placeholder
        return True


class IsReseller(permissions.BasePermission):
    """
    Permission class to check if user is a reseller.
    """
    
    def has_permission(self, request, view):
        # Staff users are considered resellers
        if request.user.is_staff:
            return True
        
        # Check if user has reseller permission
        return request.user.has_perm('tenants.is_reseller')


class CanManageResellers(permissions.BasePermission):
    """
    Permission class to check if user can manage resellers.
    """
    
    def has_permission(self, request, view):
        # Only staff users can manage resellers
        return request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission class to check if user is owner or request is read-only.
    """
    
    def has_permission(self, request, view):
        # Allow read-only access to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions require owner or staff
        return request.user.is_authenticated and (
            request.user.is_staff or 
            request.user.has_perm('tenants.manage_tenant')
        )
    
    def has_object_permission(self, request, view, obj):
        # Read-only access is allowed for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions require owner or staff
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return (request.user.is_staff or tenant.owner == request.user)


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Permission class to check if user is authenticated or request is read-only.
    """
    
    def has_permission(self, request, view):
        # Allow read-only access to anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions require authentication
        return request.user.is_authenticated


class HasValidAPIKey(permissions.BasePermission):
    """
    Permission class to check if request has valid API key.
    """
    
    def has_permission(self, request, view):
        # Skip API key check for staff users
        if request.user.is_staff:
            return True
        
        # Check for API key in request headers
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return False
        
        # Validate API key (this would depend on your API key system)
        return self._validate_api_key(api_key)
    
    def _validate_api_key(self, api_key):
        """Validate API key."""
        # This would involve checking against your API key database
        # For now, return False as a placeholder
        return False


class IsWithinRateLimit(permissions.BasePermission):
    """
    Permission class to check if request is within rate limits.
    """
    
    def has_permission(self, request, view):
        # Staff users bypass rate limits
        if request.user.is_staff:
            return True
        
        # Get tenant from request
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return True  # Skip rate limit check if no tenant
        
        # Check rate limits based on tenant plan
        return self._check_rate_limit(request, tenant)
    
    def _check_rate_limit(self, request, tenant):
        """Check if request is within rate limits."""
        # This would involve checking against your rate limiting system
        # For now, return True as a placeholder
        return True


class HasValidSubscriptionTier(permissions.BasePermission):
    """
    Permission class to check if tenant has valid subscription tier.
    """
    
    def __init__(self, required_tier='basic'):
        self.required_tier = required_tier
    
    def has_permission(self, request, view):
        # Staff users bypass tier checks
        if request.user.is_staff:
            return True
        
        # Get tenant from request
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        return self._check_subscription_tier(tenant, self.required_tier)
    
    def has_object_permission(self, request, view, obj):
        # Staff users bypass tier checks
        if request.user.is_staff:
            return True
        
        # Get tenant from object
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return self._check_subscription_tier(tenant, self.required_tier)
    
    def _check_subscription_tier(self, tenant, required_tier):
        """Check if tenant has required subscription tier."""
        # This would depend on your tier system
        # For now, return True as a placeholder
        return True


class CanAccessResource(permissions.BasePermission):
    """
    Permission class to check if user can access a specific resource type.
    """
    
    def __init__(self, resource_type):
        self.resource_type = resource_type
    
    def has_permission(self, request, view):
        # Staff users can access all resources
        if request.user.is_staff:
            return True
        
        # Check if user has permission for this resource type
        permission_name = f'tenants.access_{self.resource_type}'
        return request.user.has_perm(permission_name)
    
    def has_object_permission(self, request, view, obj):
        # Staff users can access all resources
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return tenant.owner == request.user


class IsSuperUserOrReadOnly(permissions.BasePermission):
    """
    Permission class to check if user is superuser or request is read-only.
    """
    
    def has_permission(self, request, view):
        # Allow read-only access to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions require superuser
        return request.user.is_superuser


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission class to check if user is tenant admin.
    """
    
    def has_permission(self, request, view):
        # Staff users are considered tenant admins
        if request.user.is_staff:
            return True
        
        # Check if user has tenant admin permission
        return request.user.has_perm('tenants.tenant_admin')
    
    def has_object_permission(self, request, view, obj):
        # Staff users are considered tenant admins
        if request.user.is_staff:
            return True
        
        # Check if user is tenant owner
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return False
        
        return tenant.owner == request.user


class HasValidTrial(permissions.BasePermission):
    """
    Permission class to check if tenant has valid trial.
    """
    
    def has_permission(self, request, view):
        # Staff users bypass trial checks
        if request.user.is_staff:
            return True
        
        # Get tenant from request
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return True  # Skip trial check if no tenant
        
        return self._check_trial_status(tenant)
    
    def has_object_permission(self, request, view, obj):
        # Staff users bypass trial checks
        if request.user.is_staff:
            return True
        
        # Get tenant from object
        if hasattr(obj, 'tenant'):
            tenant = obj.tenant
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Tenant':
            tenant = obj
        else:
            return True
        
        return self._check_trial_status(tenant)
    
    def _check_trial_status(self, tenant):
        """Check if tenant has valid trial."""
        # This would depend on your trial system
        # For now, return True as a placeholder
        return True


# Permission class factory for creating feature-based permissions
def HasFeature(feature_name):
    """
    Factory function to create feature-based permission class.
    """
    class HasFeaturePermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if request.user.is_staff:
                return True
            
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return False
            
            # Check if tenant has the feature
            return tenant.has_feature(feature_name)
        
        def has_object_permission(self, request, view, obj):
            if request.user.is_staff:
                return True
            
            if hasattr(obj, 'tenant'):
                tenant = obj.tenant
            else:
                return False
            
            return tenant.has_feature(feature_name)
    
    return HasFeaturePermission


# Permission class factory for creating tier-based permissions
def HasTier(minimum_tier='basic'):
    """
    Factory function to create tier-based permission class.
    """
    class HasTierPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if request.user.is_staff:
                return True
            
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                return False
            
            # Check if tenant meets minimum tier requirement
            return tenant.meets_tier_requirement(minimum_tier)
        
        def has_object_permission(self, request, view, obj):
            if request.user.is_staff:
                return True
            
            if hasattr(obj, 'tenant'):
                tenant = obj.tenant
            else:
                return False
            
            return tenant.meets_tier_requirement(minimum_tier)
    
    return HasTierPermission
