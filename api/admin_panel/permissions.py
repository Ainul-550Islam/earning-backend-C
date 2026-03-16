from rest_framework.permissions import BasePermission
from rest_framework import permissions
from api.users.models import UserProfile 


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


class IsModeratorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'moderator']
    
    from rest_framework import permissions

class IsProfileOwner(permissions.BasePermission):
    """Permission to only allow owners of a profile to edit it"""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the profile owner or admin
        return obj.user == request.user or request.user.is_staff


class IsVerifiedUser(permissions.BasePermission):
    """Permission to only allow verified users"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin users bypass verification
        if request.user.is_staff:
            return True
        
        # Check if user has profile and is verified
        if hasattr(request.user, 'profile'):
            return request.user.profile.email_verified and request.user.profile.is_active
        return False


class IsPremiumUser(permissions.BasePermission):
    """Permission to only allow premium users"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin users bypass premium check
        if request.user.is_staff:
            return True
        
        # Check if user has premium profile
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_premium
        return False


class IsAffiliateUser(permissions.BasePermission):
    """Permission to only allow affiliate users"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has affiliate profile
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_affiliate
        return False


class CanWithdraw(permissions.BasePermission):
    """Permission to check if user can withdraw"""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            return (
                profile.is_active and 
                profile.phone_verified and 
                profile.identity_verified and
                profile.available_balance > 0
            )
        return False


class ProfileAccessPermission(permissions.BasePermission):
    """Custom permission for profile access"""
    
    def has_permission(self, request, view):
        # Allow registration
        if view.action == 'create':
            return True
        
        # Allow list only for admin
        if view.action == 'list':
            return request.user.is_authenticated and request.user.is_staff
        
        # For other actions, require authentication
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin can do anything
        if request.user.is_staff:
            return True
        
        # Profile owner can view and edit their own profile
        if obj.user == request.user:
            return request.method in ['GET', 'PUT', 'PATCH']
        
        # Others can only view public info
        return request.method in permissions.SAFE_METHODS


class ReferralAccessPermission(permissions.BasePermission):
    """Permission for referral access"""
    
    def has_permission(self, request, view):
        # Only authenticated users can access referral endpoints
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # User can only access their own referrals
        return obj.user == request.user or request.user.is_staff
    
    
    from rest_framework import permissions

class IsSystemAdmin(permissions.BasePermission):
    """Permission to only allow system administrators"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.is_staff
        )


class ReadOnlyDuringMaintenance(permissions.BasePermission):
    """Allow read-only access during maintenance mode"""
    
    def has_permission(self, request, view):
        from .models import SystemSettings
        
        settings = SystemSettings.get_settings()
        
        if settings.maintenance_mode:
            # During maintenance, only allow GET, HEAD, OPTIONS
            return request.method in permissions.SAFE_METHODS
        
        return True


class CanManageSystemSettings(permissions.BasePermission):
    """Permission to manage system settings"""
    
    def has_permission(self, request, view):
        # Only superusers can manage system settings
        return request.user.is_authenticated and request.user.is_superuser


class CanManageNotifications(permissions.BasePermission):
    """Permission to manage site notifications"""
    
    def has_permission(self, request, view):
        # Staff users can manage notifications
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.is_staff
        )


class CanViewSettings(permissions.BasePermission):
    """Permission to view system settings"""
    
    def has_permission(self, request, view):
        # All authenticated users can view settings
        return request.user.is_authenticated


class SystemAccessPermission(permissions.BasePermission):
    """Custom permission for system endpoints"""
    
    def has_permission(self, request, view):
        # Public endpoints
        if view.action in ['current_settings', 'active_notifications', 'get_content']:
            return True
        
        # Settings management - superusers only
        if view.action in ['update_settings', 'test_email', 'test_sms']:
            return request.user.is_authenticated and request.user.is_superuser
        
        # Notification management - staff users
        if view.action in ['list', 'create', 'update', 'destroy']:
            return request.user.is_authenticated and request.user.is_staff
        
        # Default to authenticated users
        return request.user.is_authenticated