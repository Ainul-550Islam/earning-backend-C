"""
Messaging ViewSets — DRF ViewSets. All mutations go through service layer.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .choices import SupportThreadStatus, SupportThreadPriority
from .exceptions import (
    MessagingError,
    ChatNotFoundError,
    ChatAccessDeniedError,
    ChatArchivedError,
    MessageNotFoundError,
    MessageDeletedError,
    BroadcastNotFoundError,
    BroadcastStateError,
    BroadcastSendError,
    SupportThreadNotFoundError,
    SupportThreadClosedError,
    SupportThreadLimitError,
    UserNotFoundError,
    RateLimitError,
)
from .filters import ChatFilter, BroadcastFilter, SupportThreadFilter, UserInboxFilter
from .models import InternalChat, ChatMessage, AdminBroadcast, SupportThread, UserInbox
from .permissions import IsChatParticipant, IsStaffOrReadOwn
from .serializers import (
    InternalChatSerializer,
    InternalChatListSerializer,
    ChatMessageSerializer,
    SendMessageSerializer,
    AdminBroadcastSerializer,
    SupportThreadSerializer,
    CreateSupportThreadSerializer,
    SupportMessageSerializer,
    UserInboxSerializer,
)
from . import services

logger = logging.getLogger(__name__)


def _error_response(exc: Exception, http_status: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )


# ---------------------------------------------------------------------------
# InternalChat ViewSet
# ---------------------------------------------------------------------------

class InternalChatViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ChatFilter

    def get_queryset(self):
        return (
            InternalChat.objects.for_user(self.request.user.pk)
            .with_last_message()
            .with_participants()
        )

    def get_serializer_class(self):
        if self.action == "list":
            return InternalChatListSerializer
        return InternalChatSerializer

    def list(self, request: Request) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer = InternalChatListSerializer(
            page or qs, many=True, context={"request": request}
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request: Request, pk: Any = None) -> Response:
        try:
            chat = InternalChat.objects.get(pk=pk)
            services._assert_chat_participant(chat, request.user.pk)
        except InternalChat.DoesNotExist:
            return _error_response(
                ChatNotFoundError(f"Chat {pk} not found."), status.HTTP_404_NOT_FOUND
            )
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        serializer = InternalChatSerializer(chat, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="direct")
    def create_direct(self, request: Request) -> Response:
        """Create or retrieve a direct chat with another user."""
        other_user_id = request.data.get("user_id")
        if not other_user_id:
            return Response({"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            chat = services.create_direct_chat(request.user.pk, other_user_id)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        serializer = InternalChatSerializer(chat, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="group")
    def create_group(self, request: Request) -> Response:
        """Create a new group chat."""
        name = request.data.get("name", "")
        member_ids = request.data.get("member_ids", [])
        try:
            chat = services.create_group_chat(
                creator_id=request.user.pk,
                name=name,
                member_ids=member_ids,
            )
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        serializer = InternalChatSerializer(chat, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request: Request, pk: Any = None) -> Response:
        """Get paginated messages for a chat."""
        limit = min(int(request.query_params.get("limit", 20)), 200)
        before_id = request.query_params.get("before_id")
        try:
            msgs = services.get_chat_messages(
                chat_id=pk,
                requester_id=request.user.pk,
                limit=limit,
                before_id=before_id,
            )
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except MessagingError as exc:
            return _error_response(exc)
        serializer = ChatMessageSerializer(msgs, many=True)
        return Response({"results": serializer.data, "count": len(msgs)})

    @action(detail=True, methods=["post"], url_path="send")
    def send_message(self, request: Request, pk: Any = None) -> Response:
        """Send a message to a chat."""
        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            message = services.send_chat_message(
                chat_id=pk,
                sender_id=request.user.pk,
                content=data.get("content", ""),
                message_type=data.get("message_type"),
                attachments=data.get("attachments", []),
                reply_to_id=data.get("reply_to_id"),
                metadata=data.get("metadata", {}),
            )
        except RateLimitError as exc:
            return _error_response(exc, status.HTTP_429_TOO_MANY_REQUESTS)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except (ChatAccessDeniedError,) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except (ChatArchivedError, MessagingError) as exc:
            return _error_response(exc)
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="messages/(?P<message_id>[^/.]+)")
    def delete_message(self, request: Request, pk: Any = None, message_id: Any = None) -> Response:
        try:
            message = services.delete_chat_message(
                message_id=message_id, requester_id=request.user.pk
            )
        except MessageNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except MessageDeletedError as exc:
            return _error_response(exc)
        return Response(ChatMessageSerializer(message).data)


# ---------------------------------------------------------------------------
# AdminBroadcast ViewSet
# ---------------------------------------------------------------------------

class AdminBroadcastViewSet(viewsets.ModelViewSet):
    serializer_class = AdminBroadcastSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_class = BroadcastFilter

    def get_queryset(self):
        return AdminBroadcast.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        validated = serializer.validated_data
        try:
            broadcast = services.create_broadcast(
                creator_id=self.request.user.pk,
                title=validated["title"],
                body=validated["body"],
                audience_type=validated.get("audience_type"),
                audience_filter=validated.get("audience_filter", {}),
                scheduled_at=validated.get("scheduled_at"),
                metadata=validated.get("metadata", {}),
            )
        except MessagingError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(exc)})
        serializer.instance = broadcast

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request: Request, pk: Any = None) -> Response:
        """Immediately dispatch a broadcast."""
        try:
            result = services.send_broadcast(broadcast_id=pk, actor_id=request.user.pk)
        except BroadcastNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except (BroadcastStateError, BroadcastSendError, MessagingError) as exc:
            return _error_response(exc)
        return Response(result)

    @action(detail=True, methods=["post"], url_path="send-async")
    def send_async(self, request: Request, pk: Any = None) -> Response:
        """Queue a broadcast for async delivery via Celery."""
        try:
            from .tasks import send_broadcast_async
            task = send_broadcast_async.delay(str(pk), actor_id=str(request.user.pk))
        except Exception as exc:
            return _error_response(MessagingError(str(exc)))
        return Response({"task_id": task.id, "broadcast_id": str(pk)})


# ---------------------------------------------------------------------------
# SupportThread ViewSet
# ---------------------------------------------------------------------------

class SupportThreadViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = SupportThreadFilter

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SupportThread.objects.all().with_messages().order_by("-last_reply_at")
        return SupportThread.objects.for_user(user.pk).with_messages().order_by("-last_reply_at")

    def list(self, request: Request) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer = SupportThreadSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request: Request, pk: Any = None) -> Response:
        try:
            thread = SupportThread.objects.with_messages().get(pk=pk)
        except SupportThread.DoesNotExist:
            return _error_response(
                SupportThreadNotFoundError(f"Thread {pk} not found."), status.HTTP_404_NOT_FOUND
            )
        if not request.user.is_staff and thread.user_id != request.user.pk:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(SupportThreadSerializer(thread).data)

    @action(detail=False, methods=["post"], url_path="create")
    def create_thread(self, request: Request) -> Response:
        serializer = CreateSupportThreadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            thread = services.create_support_thread(
                user_id=request.user.pk,
                subject=data["subject"],
                initial_message=data["initial_message"],
                priority=data.get("priority", SupportThreadPriority.NORMAL),
            )
        except SupportThreadLimitError as exc:
            return _error_response(exc, status.HTTP_429_TOO_MANY_REQUESTS)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        return Response(SupportThreadSerializer(thread).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request: Request, pk: Any = None) -> Response:
        content = request.data.get("content", "")
        if not content or not content.strip():
            return Response({"detail": "content is required."}, status=status.HTTP_400_BAD_REQUEST)
        is_internal = bool(request.data.get("is_internal_note", False))
        try:
            msg = services.reply_to_support_thread(
                thread_id=pk,
                sender_id=request.user.pk,
                content=content,
                attachments=request.data.get("attachments", []),
                is_internal_note=is_internal,
            )
        except SupportThreadNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except SupportThreadClosedError as exc:
            return _error_response(exc)
        except MessagingError as exc:
            return _error_response(exc)
        return Response(SupportMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="assign", permission_classes=[permissions.IsAdminUser])
    def assign(self, request: Request, pk: Any = None) -> Response:
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"detail": "agent_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            thread = services.assign_support_thread(thread_id=pk, agent_id=agent_id)
        except SupportThreadNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        return Response(SupportThreadSerializer(thread).data)

    @action(detail=True, methods=["post"], url_path="transition", permission_classes=[permissions.IsAdminUser])
    def transition(self, request: Request, pk: Any = None) -> Response:
        new_status = request.data.get("status")
        if not new_status:
            return Response({"detail": "status is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            thread = SupportThread.objects.get(pk=pk)
            thread.transition_to(new_status, agent=request.user)
        except SupportThread.DoesNotExist:
            return _error_response(
                SupportThreadNotFoundError(f"Thread {pk} not found."), status.HTTP_404_NOT_FOUND
            )
        except (ValueError, SupportThreadClosedError) as exc:
            return _error_response(MessagingError(str(exc)))
        return Response(SupportThreadSerializer(thread).data)


# ---------------------------------------------------------------------------
# UserInbox ViewSet
# ---------------------------------------------------------------------------

class UserInboxViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserInboxSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = UserInboxFilter

    def get_queryset(self):
        return UserInbox.objects.for_user(self.request.user.pk)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request: Request) -> Response:
        try:
            count = services.get_unread_count(request.user.pk)
        except MessagingError as exc:
            return _error_response(exc)
        return Response({"unread_count": count})

    @action(detail=False, methods=["post"], url_path="mark-read")
    def mark_read(self, request: Request) -> Response:
        item_ids = request.data.get("item_ids", [])
        if not isinstance(item_ids, list) or not item_ids:
            return Response(
                {"detail": "item_ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            updated = services.mark_inbox_items_read(
                user_id=request.user.pk, item_ids=item_ids
            )
        except MessagingError as exc:
            return _error_response(exc)
        return Response({"updated": updated})

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request: Request, pk: Any = None) -> Response:
        try:
            item = UserInbox.objects.get(pk=pk, user=request.user)
            item.archive()
        except UserInbox.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(UserInboxSerializer(item).data)
