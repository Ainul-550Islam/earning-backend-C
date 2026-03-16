"""
Messaging Permissions
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsChatParticipant(BasePermission):
    """Allow access only if the requesting user is a participant of the chat."""

    def has_object_permission(self, request, view, obj) -> bool:
        from .models import ChatParticipant
        if request.user and request.user.is_staff:
            return True
        return ChatParticipant.objects.filter(
            chat=obj, user=request.user, left_at__isnull=True
        ).exists()


class IsStaffOrReadOwn(BasePermission):
    """
    Staff users can do anything.
    Regular users can only read/write their own objects (obj.user == request.user).
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return hasattr(obj, "user") and obj.user_id == request.user.pk
