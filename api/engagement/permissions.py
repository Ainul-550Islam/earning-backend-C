# engagement/permissions.py
"""
Custom permissions for engagement system.
Includes user permissions, tenant permissions, and feature-specific permissions.
"""
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied

from .choices import USER_STATUS_CHOICES
from .dependencies import is_feature_enabled


class IsEngagementUser(permissions.BasePermission):
    """
    Permission to check if user is an engagement user.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and
            hasattr(request.user, 'is_engagement_user') and
            request.user.is_engagement_user
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow only owners to edit objects.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object
        return hasattr(obj, 'user') and obj.user == request.user


class IsTenantOwner(permissions.BasePermission):
    """
    Permission to check if user owns the tenant.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Superusers can access any tenant
        if request.user.is_superuser:
            return True
        
        # Check if user is tenant owner
        return (
            hasattr(request.user, 'tenant') and
            hasattr(request.user.tenant, 'owner') and
            request.user.tenant.owner == request.user
        )


class IsTenantMember(permissions.BasePermission):
    """
    Permission to check if user is a member of the tenant.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Superusers can access any tenant
        if request.user.is_superuser:
            return True
        
        # Check if user belongs to tenant
        return (
            hasattr(request.user, 'tenant') and
            request.user.tenant is not None
        )


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission to check if user is a tenant admin.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Superusers can access any tenant
        if request.user.is_superuser:
            return True
        
        # Check if user is tenant admin
        return (
            hasattr(request.user, 'tenant') and
            hasattr(request.user, 'tenant_role') and
            request.user.tenant_role in ['admin', 'owner']
        )


class IsActiveUser(permissions.BasePermission):
    """
    Permission to check if user is active.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'status', 'active') == 'active'
        )


class IsPremiumUser(permissions.BasePermission):
    """
    Permission to check if user has premium subscription.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'has_premium', False)
        )


class HasBetaAccess(permissions.BasePermission):
    """
    Permission to check if user has beta access.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'has_beta_access', False)
        )


class CanCheckIn(permissions.BasePermission):
    """
    Permission to check if user can check in today.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has already checked in today
        from .models.checkin import DailyCheckIn
        from datetime import date
        
        today = date.today()
        already_checked_in = DailyCheckIn.objects.filter(
            user=request.user, 
            date=today
        ).exists()
        
        return not already_checked_in


class CanSpin(permissions.BasePermission):
    """
    Permission to check if user can spin today.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has spins remaining today
        from .models.spinwheel import SpinWheel
        from .constants import SPIN_MAX_PER_DAY
        from datetime import date
        
        today = date.today()
        spins_today = SpinWheel.objects.filter(
            user=request.user,
            spun_at__date=today
        ).count()
        
        return spins_today < SPIN_MAX_PER_DAY


class CanCompleteQuest(permissions.BasePermission):
    """
    Permission to check if user can complete a quest.
    """
    
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        
        # Check if user owns the quest
        if hasattr(obj, 'user') and obj.user != request.user:
            return False
        
        # Check if quest is in completable state
        if hasattr(obj, 'status'):
            return obj.status in ['available', 'active']
        
        return True


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow admins to edit, others to read only.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsOwnerOrTenantAdmin(permissions.BasePermission):
    """
    Permission to allow owners or tenant admins to edit objects.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Check if user is owner
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        # Check if user is tenant admin
        if (
            hasattr(request.user, 'tenant_role') and
            request.user.tenant_role in ['admin', 'owner']
        ):
            return True
        
        # Superusers can edit anything
        return request.user.is_superuser


class FeatureEnabled(permissions.BasePermission):
    """
    Permission to check if a feature is enabled.
    """
    
    def __init__(self, feature_name):
        self.feature_name = feature_name
    
    def has_permission(self, request, view):
        return is_feature_enabled(self.feature_name)


class TimeBasedPermission(permissions.BasePermission):
    """
    Permission that allows access only during certain time periods.
    """
    
    def __init__(self, start_hour=0, end_hour=23):
        self.start_hour = start_hour
        self.end_hour = end_hour
    
    def has_permission(self, request, view):
        from datetime import datetime
        
        current_hour = datetime.now().hour
        return self.start_hour <= current_hour <= self.end_hour


class RateLimitPermission(permissions.BasePermission):
    """
    Permission that checks rate limits.
    """
    
    def __init__(self, limit=100, period=3600, scope='user'):
        self.limit = limit
        self.period = period
        self.scope = scope
    
    def has_permission(self, request, view):
        from django.core.cache import cache
        
        # Generate cache key
        if self.scope == 'user' and request.user.is_authenticated:
            identifier = f"user_{request.user.id}"
        else:
            identifier = f"ip_{request.META.get('REMOTE_ADDR', 'unknown')}"
        
        cache_key = f"rate_limit:{view.__class__.__name__}:{identifier}"
        
        # Check current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= self.limit:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, self.period)
        
        return True


class ContentModerationPermission(permissions.BasePermission):
    """
    Permission for content moderation.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Superusers and staff can moderate
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check if user has moderation role
        return getattr(request.user, 'is_moderator', False)


class DataExportPermission(permissions.BasePermission):
    """
    Permission for data export operations.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Users can export their own data
        if view.action == 'export' and hasattr(request.user, 'id'):
            return True
        
        # Admins can export any data
        return request.user.is_staff or request.user.is_superuser


class AnalyticsPermission(permissions.BasePermission):
    """
    Permission for analytics access.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Users can access their own analytics
        if hasattr(view, 'user_analytics') and view.user_analytics:
            return True
        
        # Admins and tenant admins can access all analytics
        return (
            request.user.is_staff or
            getattr(request.user, 'tenant_role', None) in ['admin', 'owner']
        )


class WebhookPermission(permissions.BasePermission):
    """
    Permission for webhook operations.
    """
    
    def has_permission(self, request, view):
        # Webhook endpoints need special handling
        if request.path.startswith('/engagement/webhooks/'):
            # Allow POST requests from external services
            if request.method == 'POST':
                return True
            
            # Only authenticated users can manage webhooks
            return request.user.is_authenticated and request.user.is_staff
        
        return True


class SocialPermission(permissions.BasePermission):
    """
    Permission for social features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has social features enabled
        return getattr(request.user, 'social_enabled', True)


class ReferralPermission(permissions.BasePermission):
    """
    Permission for referral features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has referral features enabled
        return getattr(request.user, 'referral_enabled', True)


class ShopPermission(permissions.BasePermission):
    """
    Permission for shop features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has shop access
        shop_enabled = getattr(request.user, 'shop_enabled', True)
        
        # Check age restrictions for certain items
        if hasattr(view, 'age_restricted') and view.age_restricted:
            user_age = getattr(request.user, 'age', 0)
            if user_age < 18:
                return False
        
        return shop_enabled


class AchievementPermission(permissions.BasePermission):
    """
    Permission for achievement features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has achievement features enabled
        return getattr(request.user, 'achievements_enabled', True)


class LeaderboardPermission(permissions.BasePermission):
    """
    Permission for leaderboard features.
    """
    
    def has_permission(self, request, view):
        # Leaderboard is generally public
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write operations require authentication
        return request.user.is_authenticated


class GuildPermission(permissions.BasePermission):
    """
    Permission for guild features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has guild features enabled
        return getattr(request.user, 'guilds_enabled', True)


class BattlePassPermission(permissions.BasePermission):
    """
    Permission for battle pass features.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user has battle pass features enabled
        return getattr(request.user, 'battle_pass_enabled', True)


# ── Permission Mixins ───────────────────────────────────────────────────────

class TenantAwarePermissionMixin:
    """
    Mixin for views that need tenant-aware permissions.
    """
    
    def get_permissions(self):
        permissions = super().get_permissions()
        
        # Add tenant permission if user is authenticated
        if self.request.user.is_authenticated:
            permissions.append(IsTenantMember())
        
        return permissions


class OwnerAwarePermissionMixin:
    """
    Mixin for views that need owner-aware permissions.
    """
    
    def get_permissions(self):
        permissions = super().get_permissions()
        
        # Add owner permission for non-safe methods
        if self.request.method not in permissions.SAFE_METHODS:
            permissions.append(IsOwnerOrReadOnly())
        
        return permissions


class FeatureAwarePermissionMixin:
    """
    Mixin for views that need feature-aware permissions.
    """
    
    def get_permissions(self):
        permissions = super().get_permissions()
        
        # Add feature permission if specified
        if hasattr(self, 'required_feature'):
            permissions.append(FeatureEnabled(self.required_feature))
        
        return permissions


# ── Custom Permission Classes ─────────────────────────────────────────────────

class EngagementPermission(permissions.BasePermission):
    """
    Base permission class for engagement system.
    """
    
    def has_permission(self, request, view):
        # Basic authentication check
        if not request.user.is_authenticated:
            return False
        
        # Check user status
        if getattr(request.user, 'status', 'active') != 'active':
            return False
        
        # Check tenant membership
        if hasattr(request.user, 'tenant') and request.user.tenant is None:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Basic ownership check
        if hasattr(obj, 'user') and obj.user != request.user:
            return False
        
        # Tenant ownership check
        if hasattr(obj, 'tenant') and hasattr(request.user, 'tenant'):
            if obj.tenant != request.user.tenant:
                return False
        
        return True


class AdminEngagementPermission(permissions.BasePermission):
    """
    Permission for admin-level engagement operations.
    """
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (
                request.user.is_superuser or
                request.user.is_staff or
                getattr(request.user, 'tenant_role', None) in ['admin', 'owner']
            )
        )


class PublicEngagementPermission(permissions.BasePermission):
    """
    Permission for public engagement endpoints.
    """
    
    def has_permission(self, request, view):
        # Public endpoints are accessible to everyone
        return True
    
    def has_object_permission(self, request, view, obj):
        # For public endpoints, only allow safe methods
        return request.method in permissions.SAFE_METHODS
