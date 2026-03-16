from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from .models import UserSubscription


class IsSubscriptionOwner(BasePermission):
    """Allow access only to the owner of the subscription."""
    message = "You do not own this subscription."

    def has_object_permission(self, request, view, obj):
        if isinstance(obj, UserSubscription):
            return obj.user == request.user
        # For payment objects check via subscription
        if hasattr(obj, "subscription"):
            return obj.subscription.user == request.user
        return False


class HasActiveSubscription(BasePermission):
    """Deny access if the user has no active or trialing subscription."""
    message = "An active subscription is required to access this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return UserSubscription.objects.has_active_subscription(request.user)


class IsAdminOrReadOnly(BasePermission):
    """Admins have full access; others get read-only."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class CanManageSubscriptions(BasePermission):
    """Staff members can manage any subscription."""
    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_superuser)


class IsOwnerOrAdmin(BasePermission):
    """Allow if owner or staff."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if isinstance(obj, UserSubscription):
            return obj.user == request.user
        if hasattr(obj, "subscription"):
            return obj.subscription.user == request.user
        return False