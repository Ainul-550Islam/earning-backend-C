from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsInventoryOwner(BasePermission):
    """Allow access only to the owner of a UserInventory record."""
    message = "You do not own this inventory entry."

    def has_object_permission(self, request, view, obj):
        from .models import UserInventory
        if isinstance(obj, UserInventory):
            return obj.user == request.user
        return False


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class CanManageInventory(BasePermission):
    """Staff permission for full inventory management."""
    def has_permission(self, request, view):
        return bool(request.user and (request.user.is_staff or request.user.is_superuser))


class CanAwardItems(BasePermission):
    """
    Staff or service accounts (authenticated users with is_staff) can award items.
    Extend to check a specific permission if finer-grained control is needed.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)
