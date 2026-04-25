# earning_backend/api/notifications/permissions.py
"""
Custom permission classes for notification endpoints.
"""
from rest_framework.permissions import BasePermission, IsAdminUser, SAFE_METHODS


class IsNotificationOwner(BasePermission):
    """Allow access only to the owner of the notification."""
    message = 'You do not have permission to access this notification.'

    def has_object_permission(self, request, view, obj):
        user = getattr(obj, 'user', None)
        if user is None:
            user = getattr(obj, 'notification', None)
            user = getattr(user, 'user', None) if user else None
        return user == request.user or request.user.is_staff


class IsOwnerOrReadOnly(BasePermission):
    """Owner can write; others get read-only."""
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(obj, 'user', None)
        return user == request.user or request.user.is_staff


class IsAdminOrReadOnly(BasePermission):
    """Admin can write; authenticated users get read-only."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff


class CanManageCampaigns(BasePermission):
    """Permission to create/manage notification campaigns."""
    message = 'Only staff members can manage notification campaigns.'

    def has_permission(self, request, view):
        return request.user and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return request.user and request.user.is_staff


class CanManageDevices(BasePermission):
    """User can manage their own devices; admin can manage any."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.is_staff


class CanViewAnalytics(BasePermission):
    """Staff-only analytics access."""
    message = 'Analytics are only available to staff members.'

    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsNotFatigued(BasePermission):
    """
    Block notification creation if user is currently fatigued
    (too many notifications today/this week).
    Only applies to non-critical notifications.
    """
    message = 'You have received too many notifications today. Please try again tomorrow.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False

        # Check priority from request data
        priority = request.data.get('priority', 'medium') if hasattr(request, 'data') else 'medium'
        if priority in ('critical', 'urgent'):
            return True

        try:
            from notifications.services.FatigueService import fatigue_service
            return not fatigue_service.is_fatigued(request.user, priority=priority)
        except Exception:
            return True  # Don't block on error
