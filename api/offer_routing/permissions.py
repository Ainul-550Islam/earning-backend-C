"""
Custom Permissions for Offer Routing System
"""

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from .choices import UserSegmentType, ActionType, PermissionLevel


class IsRouteOwner(permissions.BasePermission):
    """Permission to check if user owns the route."""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user.tenant
        return False


class IsOfferOwner(permissions.BasePermission):
    """Permission to check if user owns the offer."""
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user.tenant
        return False


class CanManageRoutes(permissions.BasePermission):
    """Permission to manage routes."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_routes'))
        )


class CanManageOffers(permissions.BasePermission):
    """Permission to manage offers."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_offers'))
        )


class CanViewAnalytics(permissions.BasePermission):
    """Permission to view analytics."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.view_analytics'))
        )


class CanManageABTests(permissions.BasePermission):
    """Permission to manage A/B tests."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_ab_tests'))
        )


class CanManagePersonalization(permissions.BasePermission):
    """Permission to manage personalization."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_personalization'))
        )


class CanManageCaps(permissions.BasePermission):
    """Permission to manage caps."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_caps'))
        )


class CanManageFallbacks(permissions.BasePermission):
    """Permission to manage fallback rules."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             request.user.has_perm('offer_routing.manage_fallbacks'))
        )


class IsTenantAdmin(permissions.BasePermission):
    """Permission to check if user is tenant admin."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or 
             getattr(request.user, 'is_tenant_admin', False))
        )


class HasValidSubscription(permissions.BasePermission):
    """Permission to check if user has valid subscription."""
    
    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        
        if not request.user.is_authenticated:
            return False
        
        # Check if user's tenant has active subscription
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return False
        
        return getattr(tenant, 'is_subscription_active', False)


class IsInUserSegment(permissions.BasePermission):
    """Permission to check if user is in specific segment."""
    
    def __init__(self, segment_type, segment_value=None):
        self.segment_type = segment_type
        self.segment_value = segment_value
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if self.segment_type == UserSegmentType.TIER:
            return self._check_tier_segment(request.user)
        elif self.segment_type == UserSegmentType.NEW_USER:
            return self._check_new_user_segment(request.user)
        elif self.segment_type == UserSegmentType.ACTIVE_USER:
            return self._check_active_user_segment(request.user)
        elif self.segment_type == UserSegmentType.PREMIUM_USER:
            return self._check_premium_user_segment(request.user)
        
        return False
    
    def _check_tier_segment(self, user):
        """Check if user is in specific tier."""
        if self.segment_value is None:
            return True
        
        user_tier = getattr(user, 'tier', None)
        return user_tier == self.segment_value
    
    def _check_new_user_segment(self, user):
        """Check if user is new."""
        if self.segment_value is None:
            return True
        
        from django.utils import timezone
        days_since_signup = (timezone.now() - user.date_joined).days
        return days_since_signup <= (self.segment_value or 30)
    
    def _check_active_user_segment(self, user):
        """Check if user is active."""
        if self.segment_value is None:
            return True
        
        # This would depend on your activity tracking
        # For now, return True as placeholder
        return True
    
    def _check_premium_user_segment(self, user):
        """Check if user is premium."""
        if self.segment_value is None:
            return True
        
        user_tier = getattr(user, 'tier', None)
        return user_tier == 'premium'


class HasActionPermission(permissions.BasePermission):
    """Permission to check if user has specific action permission."""
    
    def __init__(self, action_type):
        self.action_type = action_type
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        permission_map = {
            ActionType.SHOW: 'offer_routing.show_offers',
            ActionType.HIDE: 'offer_routing.hide_offers',
            ActionType.BOOST: 'offer_routing.boost_offers',
            ActionType.CAP: 'offer_routing.cap_offers',
        }
        
        required_permission = permission_map.get(self.action_type)
        if not required_permission:
            return False
        
        return request.user.has_perm(required_permission)


class IsWithinRateLimit(permissions.BasePermission):
    """Permission to check if user is within rate limits."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        # Check rate limiting logic here
        # This would integrate with your rate limiting system
        return True


class CanAccessPublicRouting(permissions.BasePermission):
    """Permission for public routing endpoints."""
    
    def has_permission(self, request, view):
        # Public routing endpoints should be accessible with API key
        api_key = request.META.get('HTTP_X_API_KEY')
        return api_key is not None


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission to allow read access to anyone, write access to owners."""
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user.tenant
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class HasValidAPIKey(permissions.BasePermission):
    """Permission to check for valid API key."""
    
    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return False
        
        # Validate API key against your system
        # This would check against your API key models
        return True


class CanAccessRoute(permissions.BasePermission):
    """Permission to check if user can access specific route."""
    
    def __init__(self, route_permission_level=PermissionLevel.READ):
        self.route_permission_level = route_permission_level
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        # Check user's permission level for routes
        user_route_permission = getattr(request.user, 'route_permission_level', PermissionLevel.READ)
        return user_route_permission >= self.route_permission_level


class IsInTimeWindow(permissions.BasePermission):
    """Permission to check if request is within time window."""
    
    def __init__(self, start_hour=None, end_hour=None, timezone='UTC'):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.timezone = timezone
    
    def has_permission(self, request, view):
        if self.start_hour is None or self.end_hour is None:
            return True
        
        from django.utils import timezone as django_timezone
        from datetime import datetime
        import pytz
        
        current_time = django_timezone.now()
        if self.timezone != 'UTC':
            tz = pytz.timezone(self.timezone)
            current_time = current_time.astimezone(tz)
        
        current_hour = current_time.hour
        return self.start_hour <= current_hour <= self.end_hour


class HasFeatureFlag(permissions.BasePermission):
    """Permission to check if feature flag is enabled."""
    
    def __init__(self, feature_flag):
        self.feature_flag = feature_flag
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        # Check feature flag for user's tenant
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return False
        
        # This would check against your feature flag system
        return getattr(tenant, f'feature_{self.feature_flag}', False)


class IsSecureConnection(permissions.BasePermission):
    """Permission to check for secure connection."""
    
    def has_permission(self, request, view):
        return request.is_secure()


class CanManageSystem(permissions.BasePermission):
    """Permission for system-wide management."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_staff and
            request.user.has_perm('offer_routing.manage_system')
        )


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """Permission to allow read access to anyone, write to authenticated."""
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or request.user.is_authenticated


class HasValidTenant(permissions.BasePermission):
    """Permission to check if user has valid tenant."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        return hasattr(request.user, 'tenant') and request.user.tenant is not None


class CanAccessAnalytics(permissions.BasePermission):
    """Permission to access analytics data."""
    
    def __init__(self, analytics_level='basic'):
        self.analytics_level = analytics_level
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_staff:
            return True
        
        # Check user's analytics permission level
        user_analytics_level = getattr(request.user, 'analytics_level', 'none')
        level_hierarchy = {'none': 0, 'basic': 1, 'advanced': 2, 'admin': 3}
        
        return level_hierarchy.get(user_analytics_level, 0) >= level_hierarchy.get(self.analytics_level, 0)


# Permission factory functions
def HasRoutePermission(action):
    """Factory to create route-specific permissions."""
    class HasRoutePermissionClass(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user.is_authenticated:
                return False
            
            if request.user.is_staff:
                return True
            
            permission_map = {
                'view': 'offer_routing.view_routes',
                'create': 'offer_routing.create_routes',
                'update': 'offer_routing.update_routes',
                'delete': 'offer_routing.delete_routes',
                'test': 'offer_routing.test_routes',
            }
            
            required_permission = permission_map.get(action)
            if not required_permission:
                return False
            
            return request.user.has_perm(required_permission)
    
    return HasRoutePermissionClass


def HasOfferPermission(action):
    """Factory to create offer-specific permissions."""
    class HasOfferPermissionClass(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user.is_authenticated:
                return False
            
            if request.user.is_staff:
                return True
            
            permission_map = {
                'view': 'offer_routing.view_offers',
                'create': 'offer_routing.create_offers',
                'update': 'offer_routing.update_offers',
                'delete': 'offer_routing.delete_offers',
                'assign': 'offer_routing.assign_offers',
            }
            
            required_permission = permission_map.get(action)
            if not required_permission:
                return False
            
            return request.user.has_perm(required_permission)
    
    return HasOfferPermissionClass


def HasAnalyticsPermission(action):
    """Factory to create analytics-specific permissions."""
    class HasAnalyticsPermissionClass(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user.is_authenticated:
                return False
            
            if request.user.is_staff:
                return True
            
            permission_map = {
                'view': 'offer_routing.view_analytics',
                'export': 'offer_routing.export_analytics',
                'configure': 'offer_routing.configure_analytics',
            }
            
            required_permission = permission_map.get(action)
            if not required_permission:
                return False
            
            return request.user.has_perm(required_permission)
    
    return HasAnalyticsPermissionClass
