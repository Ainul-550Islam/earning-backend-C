"""
api/ad_networks/permissions.py
Custom permissions for ad networks module
SaaS-ready with tenant support
"""

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
import logging

from api.ad_networks.models import AdNetwork, Offer, UserOfferEngagement, OfferConversion
from api.ad_networks.choices import NetworkStatus, OfferStatus

logger = logging.getLogger(__name__)


class IsAdNetworkAdmin(permissions.BasePermission):
    """
    Permission to check if user is ad network admin
    """
    
    def has_permission(self, request, view):
        """
        Check if user has ad network admin permission
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user is staff
        if not request.user.is_staff:
            return False
        
        # Check specific permission
        return request.user.has_perm('ad_networks.manage_networks')
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission for specific object
        """
        if not self.has_permission(request, view):
            return False
        
        # Superusers have all permissions
        if request.user.is_superuser:
            return True
        
        # Check tenant ownership if object has tenant
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id != obj.tenant_id:
                return False
        
        # Network-specific permissions
        if isinstance(obj, AdNetwork):
            return self._has_network_permission(request.user, obj)
        
        return True
    
    def _has_network_permission(self, user, network):
        """
        Check if user has permission for specific network
        """
        # Check if user is network owner
        if hasattr(network, 'owner') and network.owner == user:
            return True
        
        # Check if user is in network admin group
        if user.groups.filter(name='ad_network_admins').exists():
            return True
        
        # Check specific network permission
        return user.has_perm(f'ad_networks.manage_network_{network.id}')


class IsVerifiedPublisher(permissions.BasePermission):
    """
    Permission to check if user is a verified publisher
    """
    
    def has_permission(self, request, view):
        """
        Check if user is verified publisher
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user is active
        if not request.user.is_active:
            return False
        
        # Check if user is verified
        if hasattr(request.user, 'profile'):
            return getattr(request.user.profile, 'is_verified', False)
        
        # Check user verification status
        return getattr(request.user, 'is_verified', False)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission for specific object
        """
        if not self.has_permission(request, view):
            return False
        
        # Check if user owns the object
        if hasattr(obj, 'user'):
            if obj.user == request.user:
                return True
        
        # Check if user is in the same tenant
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id != obj.tenant_id:
                return False
        
        # For offers, check if user can access based on network
        if isinstance(obj, Offer):
            return self._can_access_offer(request.user, obj)
        
        # For engagements, check if user owns the engagement
        if isinstance(obj, UserOfferEngagement):
            return obj.user == request.user
        
        # For conversions, check if user owns the conversion
        if isinstance(obj, OfferConversion):
            return obj.engagement.user == request.user
        
        return False
    
    def _can_access_offer(self, user, offer):
        """
        Check if user can access specific offer
        """
        # Check if offer is active
        if offer.status != OfferStatus.ACTIVE:
            return False
        
        # Check if network is active
        if offer.ad_network and not offer.ad_network.is_active:
            return False
        
        # Check user's country eligibility
        if hasattr(user, 'profile') and hasattr(user.profile, 'country'):
            user_country = user.profile.country.upper()
            offer_countries = offer.countries or []
            
            if offer_countries and user_country not in offer_countries:
                return False
        
        # Check user's device eligibility
        if hasattr(user, 'profile') and hasattr(user.profile, 'device_type'):
            user_device = user.profile.device_type.lower()
            offer_device = offer.device_type.lower()
            
            if offer_device != 'any' and user_device != offer_device:
                return False
        
        return True


class CanAccessOfferwall(permissions.BasePermission):
    """
    Permission to check if user can access offerwall
    """
    
    def has_permission(self, request, view):
        """
        Check if user can access offerwall
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user is active
        if not request.user.is_active:
            return False
        
        # Check if user has offerwall access permission
        return request.user.has_perm('ad_networks.access_offerwall')
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific offerwall
        """
        if not self.has_permission(request, view):
            return False
        
        # Check if offerwall is active
        if hasattr(obj, 'is_active') and not obj.is_active:
            return False
        
        # Check tenant access
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id != obj.tenant_id:
                return False
        
        # Check if user is in allowed countries
        if hasattr(obj, 'countries') and obj.countries:
            if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'country'):
                user_country = request.user.profile.country.upper()
                if user_country not in obj.countries:
                    return False
        
        return True


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow only owners to edit objects
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is owner or request is read-only
        """
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check for other ownership patterns
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission to check if user is tenant admin
    """
    
    def has_permission(self, request, view):
        """
        Check if user is tenant admin
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user is staff
        if not request.user.is_staff:
            return False
        
        # Check tenant admin permission
        return request.user.has_perm('tenants.manage_tenant')
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is admin for object's tenant
        """
        if not self.has_permission(request, view):
            return False
        
        # Superusers have all permissions
        if request.user.is_superuser:
            return True
        
        # Check if object has tenant
        if not hasattr(obj, 'tenant_id'):
            return True
        
        # Check if user is admin for the tenant
        user_tenant_id = getattr(request.user, 'tenant_id', None)
        if not user_tenant_id:
            return False
        
        if user_tenant_id != obj.tenant_id:
            return False
        
        # Check tenant admin group membership
        return request.user.groups.filter(name='tenant_admins').exists()


class HasNetworkAccess(permissions.BasePermission):
    """
    Permission to check if user has access to specific network
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has access to specific network
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if network is active
        if isinstance(obj, AdNetwork) and not obj.is_active:
            return False
        
        # Check if user has explicit network permission
        if isinstance(obj, AdNetwork):
            network_perm = f'ad_networks.access_network_{obj.network_type}'
            if request.user.has_perm(network_perm):
                return True
        
        # Check if user is network admin
        if request.user.groups.filter(name='network_admins').exists():
            return True
        
        # Check tenant-based access
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id == obj.tenant_id:
                return True
        
        return False


class CanManageOffers(permissions.BasePermission):
    """
    Permission to check if user can manage offers
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage offers
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user has offer management permission
        return request.user.has_perm('ad_networks.manage_offers')
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific offer
        """
        if not self.has_permission(request, view):
            return False
        
        # Check if user owns the offer's network
        if isinstance(obj, Offer) and obj.ad_network:
            network_perm = f'ad_networks.manage_network_{obj.ad_network.network_type}'
            if request.user.has_perm(network_perm):
                return True
        
        # Check tenant ownership
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id == obj.tenant_id:
                return True
        
        return False


class CanViewAnalytics(permissions.BasePermission):
    """
    Permission to check if user can view analytics
    """
    
    def has_permission(self, request, view):
        """
        Check if user can view analytics
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user has analytics permission
        return request.user.has_perm('ad_networks.view_analytics')
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can view analytics for specific object
        """
        if not self.has_permission(request, view):
            return False
        
        # Check tenant ownership
        if hasattr(obj, 'tenant_id') and obj.tenant_id:
            user_tenant_id = getattr(request.user, 'tenant_id', None)
            if user_tenant_id != obj.tenant_id:
                return False
        
        # Check if user can access the network's analytics
        if isinstance(obj, AdNetwork):
            network_perm = f'ad_networks.analytics_network_{obj.network_type}'
            return request.user.has_perm(network_perm)
        
        return True


class IsSuperUserOrReadOnly(permissions.BasePermission):
    """
    Permission to allow only superusers to write
    """
    
    def has_permission(self, request, view):
        """
        Check if user is superuser or request is read-only
        """
        # Read permissions are allowed for any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions are only allowed to superusers
        return request.user.is_superuser


class HasValidSubscription(permissions.BasePermission):
    """
    Permission to check if user has valid subscription
    """
    
    def has_permission(self, request, view):
        """
        Check if user has valid subscription
        """
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user is active
        if not request.user.is_active:
            return False
        
        # Check subscription status
        if hasattr(request.user, 'subscription'):
            subscription = request.user.subscription
            return (
                subscription.is_active and 
                not subscription.is_expired and
                subscription.plan_features.get('ad_networks', False)
            )
        
        # Check if user has subscription permission
        return request.user.has_perm('ad_networks.has_subscription')


# ==================== PERMISSION UTILITIES ====================

def check_tenant_permission(user, obj, permission_name):
    """
    Check if user has permission for object in their tenant
    """
    if isinstance(user, AnonymousUser):
        return False
    
    # Check if user belongs to the same tenant
    if not hasattr(obj, 'tenant_id'):
        return True
    
    user_tenant_id = getattr(user, 'tenant_id', None)
    if not user_tenant_id or user_tenant_id != obj.tenant_id:
        return False
    
    # Check the specific permission
    return user.has_perm(f'ad_networks.{permission_name}')


def check_network_ownership(user, network):
    """
    Check if user owns or has access to network
    """
    if isinstance(user, AnonymousUser):
        return False
    
    # Direct ownership
    if hasattr(network, 'owner') and network.owner == user:
        return True
    
    # Network admin group
    if user.groups.filter(name='network_admins').exists():
        return True
    
    # Specific permission
    return user.has_perm(f'ad_networks.manage_network_{network.network_type}')


def check_offer_eligibility(user, offer):
    """
    Check if user is eligible for offer
    """
    if isinstance(user, AnonymousUser):
        return False
    
    # Check if user is verified (if required)
    if offer.requires_verification and not getattr(user, 'is_verified', False):
        return False
    
    # Check if user has already completed the offer
    if UserOfferEngagement.objects.filter(
        user=user,
        offer=offer,
        status__in=['completed', 'approved']
    ).exists():
        return False
    
    # Check daily limit
    from api.ad_networks.models import OfferDailyLimit
    daily_limit = OfferDailyLimit.objects.filter(
        user=user,
        offer=offer
    ).first()
    
    if daily_limit and daily_limit.is_limit_reached:
        return False
    
    # Check geographic restrictions
    if hasattr(user, 'profile') and hasattr(user.profile, 'country'):
        user_country = user.profile.country.upper()
        offer_countries = offer.countries or []
        
        if offer_countries and user_country not in offer_countries:
            return False
    
    # Check device restrictions
    if hasattr(user, 'profile') and hasattr(user.profile, 'device_type'):
        user_device = user.profile.device_type.lower()
        offer_device = offer.device_type.lower()
        
        if offer_device != 'any' and user_device != offer_device:
            return False
    
    return True


def can_perform_fraud_analysis(user):
    """
    Check if user can perform fraud analysis
    """
    if isinstance(user, AnonymousUser):
        return False
    
    # Check if user is staff
    if not user.is_staff:
        return False
    
    # Check fraud analysis permission
    return user.has_perm('ad_networks.analyze_fraud')


def can_export_data(user, data_type='offers'):
    """
    Check if user can export data
    """
    if isinstance(user, AnonymousUser):
        return False
    
    # Check export permission
    export_perm = f'ad_networks.export_{data_type}'
    return user.has_perm(export_perm)


# ==================== PERMISSION MIXINS ====================

class TenantPermissionMixin:
    """
    Mixin to add tenant permission checking to views
    """
    
    def get_tenant_permissions(self, user):
        """
        Get user's permissions for current tenant
        """
        if hasattr(user, 'tenant_id') and user.tenant_id:
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            
            # Get ad networks content type
            content_type = ContentType.objects.get(
                app_label='ad_networks',
                model='adnetwork'
            )
            
            # Get user's permissions for this tenant
            return Permission.objects.filter(
                user=user,
                content_type=content_type
            ).values_list('codename', flat=True)
        
        return []


class NetworkPermissionMixin:
    """
    Mixin to add network-specific permission checking
    """
    
    def check_network_permission(self, user, network, permission_suffix):
        """
        Check if user has specific permission for network
        """
        if isinstance(user, AnonymousUser):
            return False
        
        permission_name = f'ad_networks.{permission_suffix}_{network.network_type}'
        return user.has_perm(permission_name)


# ==================== CUSTOM PERMISSION CLASSES ====================

class DynamicPermission(permissions.BasePermission):
    """
    Dynamic permission based on request attributes
    """
    
    def __init__(self, permission_func=None):
        self.permission_func = permission_func
    
    def has_permission(self, request, view):
        """
        Check permission using dynamic function
        """
        if not self.permission_func:
            return False
        
        return self.permission_func(request, view)
    
    def has_object_permission(self, request, view, obj):
        """
        Check object permission using dynamic function
        """
        if not self.permission_func:
            return False
        
        return self.permission_func(request, view, obj)


class ConditionalPermission(permissions.BasePermission):
    """
    Permission that applies conditionally
    """
    
    def __init__(self, condition_func=None, permission_class=None):
        self.condition_func = condition_func
        self.permission_class = permission_class or permissions.IsAuthenticated
    
    def has_permission(self, request, view):
        """
        Check condition first, then permission
        """
        if self.condition_func and not self.condition_func(request, view):
            return False
        
        permission_instance = self.permission_class()
        return permission_instance.has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        """
        Check condition first, then object permission
        """
        if self.condition_func and not self.condition_func(request, view):
            return False
        
        permission_instance = self.permission_class()
        return permission_instance.has_object_permission(request, view, obj)
