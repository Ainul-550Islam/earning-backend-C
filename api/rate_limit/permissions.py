from rest_framework import permissions
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q


class IsAdminOrRateLimitManager(permissions.BasePermission):
    """
    Permission to allow admin or rate limit manager users
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return False
        
        # Admin users have all permissions
        if request.user.is_superuser:
            return True
        
        # Check if user is in rate limit manager group
        return request.user.groups.filter(name='rate_limit_managers').exists()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class CanManageUserRateLimits(permissions.BasePermission):
    """
    Permission to manage user rate limits
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin and managers can manage all users
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can manage their own rate limit profile
        if view.action in ['retrieve', 'update', 'partial_update']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can only manage their own profile
        return obj.user == request.user


class CanManageRateLimitConfigs(permissions.BasePermission):
    """
    Permission to manage rate limit configurations
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Only admin and rate limit managers can manage configs
        return (request.user.is_superuser or 
                request.user.groups.filter(name='rate_limit_managers').exists())
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class CanViewRateLimitLogs(permissions.BasePermission):
    """
    Permission to view rate limit logs
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin and managers can view all logs
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can view their own logs
        if view.action in ['list', 'retrieve']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can only view their own logs
        return obj.user == request.user


class CanManageAbuseReports(permissions.BasePermission):
    """
    Permission to manage abuse reports
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin and managers can manage all abuse reports
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can create abuse reports and view their own
        if view.action in ['create', 'list', 'retrieve']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can only view their own abuse reports
        return obj.user == request.user


class CanManageIPBlocks(permissions.BasePermission):
    """
    Permission to manage IP blocks
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Only admin and rate limit managers can manage IP blocks
        return (request.user.is_superuser or 
                request.user.groups.filter(name='rate_limit_managers').exists())
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class CanViewRateLimitInsights(permissions.BasePermission):
    """
    Permission to view rate limit insights
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin and managers can view all insights
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can view general insights
        if view.action in ['list', 'retrieve']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can view non-sensitive insights
        return True


class CanManageRateLimitExceptions(permissions.BasePermission):
    """
    Permission to manage rate limit exceptions
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Admin and managers can manage all exceptions
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can view their own exceptions
        if view.action in ['list', 'retrieve']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Users can only view their own exceptions
        return obj.user == request.user


class IsPremiumUser(permissions.BasePermission):
    """
    Permission to check if user has premium rate limit access
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile = UserRateLimitProfile.objects.get(user=request.user)
            
            # Check if premium status is active
            if profile.is_premium:
                if profile.premium_until and timezone.now() > profile.premium_until:
                    return False  # Premium expired
                return True
            
        except UserRateLimitProfile.DoesNotExist:
            pass
        
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class HasLowSuspicionScore(permissions.BasePermission):
    """
    Permission to check if user has low suspicion score
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile = UserRateLimitProfile.objects.get(user=request.user)
            
            # Allow access if suspicion score is below threshold
            return profile.suspicion_score < 50
            
        except UserRateLimitProfile.DoesNotExist:
            return True  # No profile means no suspicion score
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsNotIPBlocked(permissions.BasePermission):
    """
    Permission to check if user's IP is not blocked
    """
    
    def has_permission(self, request, view):
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        if not ip:
            return False
        
        try:
            from api.rate_limit.services.IPBlockService import IPBlockService
            ip_block_service = IPBlockService()
            is_blocked, _ = ip_block_service.is_ip_blocked(ip)
            
            return not is_blocked
            
        except Exception:
            return True  # Allow access if check fails
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class CanExportRateLimitData(permissions.BasePermission):
    """
    Permission to export rate limit data
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Only admin and rate limit managers can export data
        return (request.user.is_superuser or 
                request.user.groups.filter(name='rate_limit_managers').exists())
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class HasValidRateLimitException(permissions.BasePermission):
    """
    Permission to check if user has valid rate limit exception
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            from api.rate_limit.models import RateLimitException
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Check for valid exception
            exceptions = RateLimitException.objects.filter(
                Q(user=request.user) | Q(ip_address=ip),
                is_active=True
            )
            
            for exception in exceptions:
                if exception.applies_to_request(request.user, ip, request.path):
                    return True
            
        except Exception:
            pass
        
        return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsOwnerOrRateLimitManager(permissions.BasePermission):
    """
    Permission to allow owners or rate limit managers
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Check if object has a user field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object is a user profile
        if hasattr(obj, 'profile') or hasattr(obj, 'user_profile'):
            return getattr(obj, 'user', getattr(obj, 'profile', None)) == request.user
        
        return False


class CanInvestigateAbuse(permissions.BasePermission):
    """
    Permission to investigate abuse reports
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Only admin and rate limit managers can investigate abuse
        return (request.user.is_superuser or 
                request.user.groups.filter(name='rate_limit_managers').exists())
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsWithinRateLimits(permissions.BasePermission):
    """
    Permission to check if user is within rate limits
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        try:
            from api.rate_limit.services.RateLimitService import RateLimitService
            rate_limit_service = RateLimitService()
            
            # Check if user is within limits
            result = rate_limit_service.check_request(request)
            return result.get('is_allowed', False)
            
        except Exception:
            return True  # Allow access if check fails
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)