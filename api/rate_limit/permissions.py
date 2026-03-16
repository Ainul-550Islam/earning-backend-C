from rest_framework import permissions


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