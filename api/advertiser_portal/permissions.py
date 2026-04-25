"""
Advertiser Portal Permissions

This module contains permission classes for the advertiser portal
including role-based permissions and object-level permissions.
"""

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from .models.advertiser import Advertiser


class IsAuthenticated(permissions.BasePermission):
    """Allow access only to authenticated users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsAdminUser(permissions.BasePermission):
    """Allow access only to admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


class IsStaffUser(permissions.BasePermission):
    """Allow access only to staff users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsAdvertiserUser(permissions.BasePermission):
    """Allow access only to advertiser users."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            Advertiser.objects.get(user=request.user)
            return True
        except Advertiser.DoesNotExist:
            return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow access only to object owners or read-only access."""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        if hasattr(obj, 'advertiser'):
            return obj.advertiser.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'advertiser_id'):
            try:
                advertiser = Advertiser.objects.get(id=obj.advertiser_id)
                return advertiser.user == request.user
            except Advertiser.DoesNotExist:
                return False
        
        return False


class IsAdvertiserOrReadOnly(permissions.BasePermission):
    """Allow access only to advertisers or read-only access."""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to advertisers
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            if hasattr(obj, 'advertiser'):
                return obj.advertiser == advertiser
            elif hasattr(obj, 'advertiser_id'):
                return obj.advertiser_id == advertiser.id
            elif hasattr(obj, 'offer') and hasattr(obj.offer, 'advertiser'):
                return obj.offer.advertiser == advertiser
            elif hasattr(obj, 'campaign') and hasattr(obj.campaign, 'advertiser'):
                return obj.campaign.advertiser == advertiser
                
        except Advertiser.DoesNotExist:
            pass
        
        return False


class IsOwner(permissions.BasePermission):
    """Allow access only to object owners."""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'advertiser'):
            return obj.advertiser.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'advertiser_id'):
            try:
                advertiser = Advertiser.objects.get(id=obj.advertiser_id)
                return advertiser.user == request.user
            except Advertiser.DoesNotExist:
                return False
        
        return False


class IsVerifiedAdvertiser(permissions.BasePermission):
    """Allow access only to verified advertisers."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            return advertiser.verification_status == 'verified'
        except Advertiser.DoesNotExist:
            return False


class IsActiveAdvertiser(permissions.BasePermission):
    """Allow access only to active advertisers."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            return advertiser.is_active
        except Advertiser.DoesNotExist:
            return False


class CanCreateCampaign(permissions.BasePermission):
    """Allow access only to users who can create campaigns."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Check if advertiser is verified and active
            if not (advertiser.is_active and advertiser.verification_status == 'verified'):
                return False
            
            # Check if advertiser has sufficient balance
            if hasattr(advertiser, 'wallet') and advertiser.wallet:
                return advertiser.wallet.balance > 0
            
            return True
            
        except Advertiser.DoesNotExist:
            return False


class CanManageBilling(permissions.BasePermission):
    """Allow access only to users who can manage billing."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only verified advertisers can manage billing
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class CanViewReports(permissions.BasePermission):
    """Allow access only to users who can view reports."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only active advertisers can view reports
            return advertiser.is_active
            
        except Advertiser.DoesNotExist:
            return False


class CanManageOffers(permissions.BasePermission):
    """Allow access only to users who can manage offers."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only verified advertisers can manage offers
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class CanManageTracking(permissions.BasePermission):
    """Allow access only to users who can manage tracking."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only active advertisers can manage tracking
            return advertiser.is_active
            
        except Advertiser.DoesNotExist:
            return False


class IsObjectOwnerOrAdmin(permissions.BasePermission):
    """Allow access only to object owners or admin users."""
    
    def has_object_permission(self, request, view, obj):
        # Admin users have access to everything
        if request.user.is_superuser:
            return True
        
        # Check if user is the owner
        if hasattr(obj, 'advertiser'):
            return obj.advertiser.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'advertiser_id'):
            try:
                advertiser = Advertiser.objects.get(id=obj.advertiser_id)
                return advertiser.user == request.user
            except Advertiser.DoesNotExist:
                return False
        
        return False


class IsStaffOrOwner(permissions.BasePermission):
    """Allow access only to staff users or object owners."""
    
    def has_object_permission(self, request, view, obj):
        # Staff users have access to everything
        if request.user.is_staff:
            return True
        
        # Check if user is the owner
        if hasattr(obj, 'advertiser'):
            return obj.advertiser.user == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'advertiser_id'):
            try:
                advertiser = Advertiser.objects.get(id=obj.advertiser_id)
                return advertiser.user == request.user
            except Advertiser.DoesNotExist:
                return False
        
        return False


class HasValidSubscription(permissions.BasePermission):
    """Allow access only to users with valid subscription."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Check if advertiser has valid subscription
            if hasattr(advertiser, 'subscription'):
                subscription = advertiser.subscription
                return subscription.is_active and subscription.expires_at > timezone.now()
            
            # If no subscription model, assume all verified advertisers have access
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class IsInSameTenant(permissions.BasePermission):
    """Allow access only to users in the same tenant."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            user_advertiser = Advertiser.objects.get(user=request.user)
            
            if hasattr(obj, 'advertiser'):
                return obj.advertiser.tenant == user_advertiser.tenant
            elif hasattr(obj, 'advertiser_id'):
                try:
                    obj_advertiser = Advertiser.objects.get(id=obj.advertiser_id)
                    return obj_advertiser.tenant == user_advertiser.tenant
                except Advertiser.DoesNotExist:
                    return False
            elif hasattr(obj, 'tenant'):
                return obj.tenant == user_advertiser.tenant
            
        except Advertiser.DoesNotExist:
            pass
        
        return False


class CanAccessSensitiveData(permissions.BasePermission):
    """Allow access only to users who can access sensitive data."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and staff users can access sensitive data
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only verified advertisers can access sensitive data
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class CanManageFraudDetection(permissions.BasePermission):
    """Allow access only to users who can manage fraud detection."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only admin and staff users can manage fraud detection
        return request.user.is_superuser or request.user.is_staff


class CanManageMLModels(permissions.BasePermission):
    """Allow access only to users who can manage ML models."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only admin and staff users can manage ML models
        return request.user.is_superuser or request.user.is_staff


class CanAccessAPI(permissions.BasePermission):
    """Allow access only to users who can access the API."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Check if advertiser has API access enabled
            if hasattr(advertiser, 'api_access_enabled'):
                return advertiser.api_access_enabled
            
            # Default to True for verified advertisers
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class HasValidAPIKey(permissions.BasePermission):
    """Allow access only to users with valid API key."""
    
    def has_permission(self, request, view):
        # Check for API key in headers
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return False
        
        try:
            advertiser = Advertiser.objects.get(api_key=api_key)
            return advertiser.is_active and advertiser.verification_status == 'verified'
        except Advertiser.DoesNotExist:
            return False


class IsReadOnlyOrAdmin(permissions.BasePermission):
    """Allow read-only access to anyone, write access only to admins."""
    
    def has_permission(self, request, view):
        # Read-only methods are allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write methods require admin access
        return request.user and request.user.is_superuser


class IsReadOnlyOrStaff(permissions.BasePermission):
    """Allow read-only access to anyone, write access only to staff."""
    
    def has_permission(self, request, view):
        # Read-only methods are allowed for anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write methods require staff access
        return request.user and request.user.is_staff


class CanAccessAnalytics(permissions.BasePermission):
    """Allow access only to users who can access analytics."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only active advertisers can access analytics
            return advertiser.is_active
            
        except Advertiser.DoesNotExist:
            return False


class CanManageNotifications(permissions.BasePermission):
    """Allow access only to users who can manage notifications."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Only verified advertisers can manage notifications
            return advertiser.verification_status == 'verified'
            
        except Advertiser.DoesNotExist:
            return False


class IsSystemAdmin(permissions.BasePermission):
    """Allow access only to system administrators."""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (
                request.user.is_superuser or 
                (request.user.is_staff and hasattr(request.user, 'is_system_admin') and request.user.is_system_admin)
            )
        )


class HasPermissionLevel(permissions.BasePermission):
    """Allow access based on permission level."""
    
    def __init__(self, required_level):
        self.required_level = required_level
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users have all permissions
        if request.user.is_superuser:
            return True
        
        try:
            advertiser = Advertiser.objects.get(user=request.user)
            
            # Check permission level based on verification status
            if self.required_level == 'basic':
                return advertiser.is_active
            elif self.required_level == 'verified':
                return advertiser.verification_status == 'verified'
            elif self.required_level == 'premium':
                return (
                    advertiser.verification_status == 'verified' and 
                    hasattr(advertiser, 'subscription_level') and 
                    advertiser.subscription_level in ['premium', 'enterprise']
                )
            elif self.required_level == 'enterprise':
                return (
                    advertiser.verification_status == 'verified' and 
                    hasattr(advertiser, 'subscription_level') and 
                    advertiser.subscription_level == 'enterprise'
                )
            
        except Advertiser.DoesNotExist:
            pass
        
        return False


# Permission utility functions
def get_advertiser_permissions(user):
    """Get all permissions for an advertiser user."""
    permissions = []
    
    if not user or not user.is_authenticated:
        return permissions
    
    try:
        advertiser = Advertiser.objects.get(user=user)
        
        # Base permissions
        if advertiser.is_active:
            permissions.append('is_active')
        
        if advertiser.verification_status == 'verified':
            permissions.append('is_verified')
            permissions.append('can_create_campaign')
            permissions.append('can_manage_billing')
            permissions.append('can_manage_offers')
        
        # API access
        if hasattr(advertiser, 'api_access_enabled') and advertiser.api_access_enabled:
            permissions.append('can_access_api')
        
        # Subscription-based permissions
        if hasattr(advertiser, 'subscription_level'):
            if advertiser.subscription_level in ['premium', 'enterprise']:
                permissions.append('premium_features')
            if advertiser.subscription_level == 'enterprise':
                permissions.append('enterprise_features')
        
    except Advertiser.DoesNotExist:
        pass
    
    return permissions


def has_permission(user, permission):
    """Check if user has a specific permission."""
    return permission in get_advertiser_permissions(user)


def check_permission_level(user, required_level):
    """Check if user has required permission level."""
    permission_class = HasPermissionLevel(required_level)
    return permission_class.has_permission(None, None)


# Export all permission classes
__all__ = [
    'IsAuthenticated',
    'IsAdminUser',
    'IsStaffUser',
    'IsAdvertiserUser',
    'IsOwnerOrReadOnly',
    'IsAdvertiserOrReadOnly',
    'IsOwner',
    'IsVerifiedAdvertiser',
    'IsActiveAdvertiser',
    'CanCreateCampaign',
    'CanManageBilling',
    'CanViewReports',
    'CanManageOffers',
    'CanManageTracking',
    'IsObjectOwnerOrAdmin',
    'IsStaffOrOwner',
    'HasValidSubscription',
    'IsInSameTenant',
    'CanAccessSensitiveData',
    'CanManageFraudDetection',
    'CanManageMLModels',
    'CanAccessAPI',
    'HasValidAPIKey',
    'IsReadOnlyOrAdmin',
    'IsReadOnlyOrStaff',
    'CanAccessAnalytics',
    'CanManageNotifications',
    'IsSystemAdmin',
    'HasPermissionLevel',
    'get_advertiser_permissions',
    'has_permission',
    'check_permission_level',
]
