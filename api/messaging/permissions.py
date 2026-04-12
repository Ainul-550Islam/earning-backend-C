"""
Messaging Permissions — Complete permission classes for all roles.
"""
from __future__ import annotations
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsChatParticipant(BasePermission):
    """Allow access only if the user is an active participant of the chat."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user and request.user.is_staff:
            return True
        from .models import ChatParticipant
        return ChatParticipant.objects.filter(
            chat=obj, user=request.user, left_at__isnull=True
        ).exists()


class IsStaffOrReadOwn(BasePermission):
    """Staff = full access. Others = read/write own objects only."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return hasattr(obj, "user") and obj.user_id == request.user.pk


class IsMessageSender(BasePermission):
    """Only the message sender (or staff) can edit/delete."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        return hasattr(obj, "sender") and obj.sender_id == request.user.pk


class IsChatAdminOrOwner(BasePermission):
    """Only chat ADMIN or OWNER role (or staff) can perform this action."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        from .models import ChatParticipant
        participant = ChatParticipant.objects.filter(
            chat=obj, user=request.user, left_at__isnull=True
        ).first()
        if not participant:
            return False
        return participant.role in ("ADMIN", "OWNER")


class IsThreadOwnerOrAgent(BasePermission):
    """Support thread: owner (user who created) or assigned agent or staff."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        # Thread owner
        if hasattr(obj, "user") and obj.user_id == request.user.pk:
            return True
        # Assigned agent
        if hasattr(obj, "assigned_agent") and obj.assigned_agent_id == request.user.pk:
            return True
        return False


class IsAffiliateOrManager(BasePermission):
    """
    For AffiliateConversationThread:
    - Affiliate can read/write their own thread
    - Manager can read/write threads assigned to them
    - Staff can do anything
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        if hasattr(obj, "affiliate_id") and obj.affiliate_id == request.user.pk:
            return True
        if hasattr(obj, "manager_id") and obj.manager_id == request.user.pk:
            return True
        return False


class IsNotificationRecipient(BasePermission):
    """Only the notification recipient can read/mark it."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return hasattr(obj, "recipient") and obj.recipient_id == request.user.pk


class IsMediaOwner(BasePermission):
    """Only the media uploader (or staff) can manage their uploads."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        return hasattr(obj, "uploaded_by") and obj.uploaded_by_id == request.user.pk


class IsChannelAdmin(BasePermission):
    """Only channel admins (or staff) can post/manage announcement channels."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        from .models import ChannelMember
        member = ChannelMember.objects.filter(
            channel=obj, user=request.user, is_admin=True
        ).first()
        return member is not None


class IsSupportAgent(BasePermission):
    """Only staff members can act as support agents."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsDeviceOwner(BasePermission):
    """Only the device token owner can manage their tokens."""

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return hasattr(obj, "user") and obj.user_id == request.user.pk
