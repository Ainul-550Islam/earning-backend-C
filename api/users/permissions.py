from rest_framework.permissions import BasePermission, SAFE_METHODS


# ==========================================
# Custom Permissions
# ==========================================

class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        return obj.user == request.user


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class IsVerifiedUser(BasePermission):
    """
    Allows access only to verified users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_verified)


# ==========================================
# Alias for backward compatibility
# ==========================================

# Existing permissions (keep for compatibility)
class IsOwnerOrAdmin(IsAdminUser):
    """Alias for IsAdminUser"""
    pass


class IsVerified(IsVerifiedUser):
    """Alias for IsVerifiedUser"""
    pass