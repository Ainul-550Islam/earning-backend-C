"""
Messaging ViewSets — World-class update.
Existing ViewSets preserved. New ViewSets added.
"""

from __future__ import annotations
import logging
from typing import Any

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .pagination import SearchResultsPagination, SmallResultsPagination, StandardResultsPagination
from .throttling import BotRequestThrottle, BroadcastSendThrottle, CallInitiateThrottle, MediaUploadThrottle, MessageSendThrottle, ReactionThrottle, SearchThrottle, StoryCreateThrottle, SupportThreadCreateThrottle, LinkPreviewFetchThrottle

from .openapi import extend_schema, OpenApiParameter, SchemaSafeSerializerClassMixin  # noqa: F401

from .choices import (
    SupportThreadStatus, SupportThreadPriority,
    CallStatus, CallType,
)
from .exceptions import (
    MessagingError, ChatNotFoundError, ChatAccessDeniedError,
    ChatArchivedError, MessageNotFoundError, MessageDeletedError,
    BroadcastNotFoundError, BroadcastStateError, BroadcastSendError,
    SupportThreadNotFoundError, SupportThreadClosedError,
    SupportThreadLimitError, UserNotFoundError, RateLimitError,
    # Fix 5: previously defined but never imported/caught — now wired
    ChatDeletedError, ChatFullError, AlreadyParticipantError, NotParticipantError,
    MessageTooLongError, MessageEditNotAllowedError, MessageForwardError,
    UserBlockedError, UserSuspendedError, SpamDetectedError, ToxicContentError,
    MediaNotFoundError, MediaNSFWError, MediaVirusError,
    CallNotFoundError, CallAlreadyActiveError, CallInvalidStateError,
    WebSocketAuthError, WebSocketConnectionError, SearchError,
    ChannelNotFoundError, ChannelAccessDeniedError,
    StoryNotFoundError, StoryExpiredError,
    BotNotFoundError, BotConfigError,
    WebhookNotFoundError, WebhookDeliveryError,
    EncryptionError, DecryptionError, KeyExchangeError,
    PermissionDeniedError, AdminOnlyError, OwnerOnlyError,
)
from .filters import ChatFilter, BroadcastFilter, SupportThreadFilter, UserInboxFilter
from .models import (
    InternalChat, ChatMessage, ChatParticipant, AdminBroadcast, SupportThread, UserInbox,
    MessageReaction, UserPresence, CallSession, AnnouncementChannel,
    ChannelMember, ScheduledMessage, MessagePin, BotConfig,
    MessagingWebhook, UserBlock, MessageTranslation, DeviceToken,
)
from .permissions import IsChatParticipant, IsStaffOrReadOwn
from .serializers import (
    InternalChatSerializer, InternalChatListSerializer,
    ChatMessageSerializer, SendMessageSerializer,
    AdminBroadcastSerializer, SupportThreadSerializer,
    CreateSupportThreadSerializer, SupportMessageSerializer,
    UserInboxSerializer,
)
from . import services
from .openapi import (
    CHAT_LIST_SCHEMA,
    SEND_MESSAGE_SCHEMA,
    BROADCAST_SEND_SCHEMA,
    UPLOAD_SCHEMA,
)

logger = logging.getLogger(__name__)


def _error_response(exc: Exception, http_status: int = None) -> Response:
    if http_status is None:
        http_status = getattr(exc, "http_status", status.HTTP_400_BAD_REQUEST)
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )

# Centralised http helper (same as _error_response but imported from utils.http for new code)
from .utils.http import _err as _http_err  # noqa: E402


# ============================================================================
# EXISTING ViewSets (unchanged logic, kept complete)
# ============================================================================

log = logging.getLogger(__name__)


class InternalChatViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class     = StandardResultsPagination
    filterset_class = ChatFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return InternalChat.objects.none()
        qs_ = (InternalChat.objects
            .for_user(self.request.user.pk)
            .with_last_message()
            .with_participants())
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def get_serializer_class(self):
        if self.action == "list":
            return InternalChatListSerializer
        return InternalChatSerializer

    @CHAT_LIST_SCHEMA
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
            return _error_response(ChatNotFoundError(f"Chat {pk} not found."), status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(InternalChatSerializer(chat, context={"request": request}).data)

    @extend_schema(
        summary='Start a direct (1-to-1) chat',
        description=(
            "Creates a new direct chat between the authenticated user and a single "
            "recipient. Returns existing chat if one already exists."
        ),
    )
    @action(detail=False, methods=["post"])
    def direct(self, request: Request) -> Response:
        # Accept both 'other_user_id' (documented) and 'user_id' (old field name)
        other_user_id = request.data.get("other_user_id") or request.data.get("user_id")
        if not other_user_id:
            return _error_response(MessagingError("other_user_id required."))
        try:
            chat = services.create_direct_chat(request.user.pk, other_user_id)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        serializer = InternalChatSerializer(chat, context={"request": request})
        # Return 201 if this is a new chat, 200 if returning an existing one.
        # create_direct_chat() returns the existing chat unchanged if one already
        # exists, so we check whether we were just added (i.e. participant row
        # was created now vs pre-existing).
        just_created = not ChatParticipant.objects.filter(
            chat=chat, user_id=request.user.pk,
        ).exclude(joined_at=chat.created_at).exists()
        return Response(serializer.data, status=status.HTTP_201_CREATED if just_created else status.HTTP_200_OK)

    @extend_schema(
        summary='Create a group chat',
        description=(
            "Creates a new group chat with multiple initial participants. The creator "
            "is automatically added as ADMIN."
        ),
    )
    @action(detail=False, methods=["post"])
    def group(self, request: Request) -> Response:
        name = request.data.get("name", "").strip()
        member_ids = request.data.get("member_ids", [])
        if not name:
            return _error_response(MessagingError("name is required."))
        if not member_ids:
            return _error_response(MessagingError("member_ids must not be empty."))
        try:
            chat = services.create_group_chat(creator_id=request.user.pk, name=name, member_ids=member_ids)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        return Response(InternalChatSerializer(chat, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='List chat messages',
        description=(
            "Returns paginated messages for a chat the user participates in, ordered "
            "newest-first. Supports cursor-based pagination via ?cursor=."
        ),
    )
    @action(detail=True, methods=["get"])
    def messages(self, request: Request, pk: Any = None) -> Response:
        before_id = request.query_params.get("before_id")
        limit = int(request.query_params.get("limit", 20))
        try:
            msgs = services.get_chat_messages(chat_id=pk, user_id=request.user.pk, before_id=before_id, limit=limit)
        except (ChatNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(ChatMessageSerializer(msgs, many=True, context={"request": request}).data)

    @extend_schema(
        summary='Send a message',
        description=(
            "Sends a TEXT, IMAGE, AUDIO, VIDEO, FILE, POLL, LOCATION, or STICKER "
            "message. Triggers real-time WebSocket delivery, push notifications, and "
            "spam/toxicity checks."
        ),
    )
    @action(detail=True, methods=["post"])
    @SEND_MESSAGE_SCHEMA
    def send_message(self, request: Request, pk: Any = None) -> Response:
        log.info("send_message user=%s chat=%s", request.user.pk, pk)
        self.throttle_classes = [MessageSendThrottle]
        self.check_throttles(request)
        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            msg = services.send_chat_message(
                chat_id=pk,
                sender_id=request.user.pk,
                content=serializer.validated_data.get("content", ""),
                message_type=serializer.validated_data.get("message_type", "TEXT"),
                reply_to_id=serializer.validated_data.get("reply_to_id"),
                attachments=serializer.validated_data.get("attachments", []),
                mentions=request.data.get("mentions", []),
                thread_id=request.data.get("thread_id"),
                poll_data=request.data.get("poll_data"),
                location_data=request.data.get("location_data"),
            )
        except (ChatNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except (ChatArchivedError, MessagingError, RateLimitError) as exc:
            return _error_response(exc)
        except (UserBlockedError, UserSuspendedError) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except (SpamDetectedError, ToxicContentError) as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except MessageTooLongError as exc:
            return _error_response(exc, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        return Response(ChatMessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Delete a message',
        description=(
            "Soft-deletes a message. Sender can delete their own; admins can delete "
            "any. Publishes a deleted-message event over WebSocket."
        ),
    )
    @action(detail=True, methods=["delete"], url_path="messages/(?P<message_id>[^/.]+)")
    def delete_message(self, request: Request, pk: Any = None, message_id: Any = None) -> Response:
        log.info("delete_message user=%s msg=%s", request.user.pk, message_id)
        try:
            services.delete_chat_message(message_id=message_id, requesting_user_id=request.user.pk)
        except (MessageNotFoundError, MessageDeletedError) as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary='Mark chat as read',
        description=(
            "Updates the participant's last_read_at timestamp, clearing the unread "
            "badge for this chat."
        ),
    )
    @action(detail=True, methods=["post"])
    def mark_read(self, request: Request, pk: Any = None) -> Response:
        log.debug("mark_read user=%s chat=%s", request.user.pk, pk)
        try:
            participant = services.mark_chat_read(chat_id=pk, user_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response({
            "last_read_at": participant.last_read_at.isoformat() if participant.last_read_at else None,
        })

    @extend_schema(
        summary='List pinned messages',
        description=(
            "Returns all currently pinned messages for the chat, ordered by pinned_at "
            "descending."
        ),
    )
    @action(detail=True, methods=["get"])
    def pinned_messages(self, request: Request, pk: Any = None) -> Response:
        try:
            pins = services.get_pinned_messages(chat_id=pk, requesting_user_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response([{
            "pin_id": str(p.id),
            "message_id": str(p.message_id),
            "pinned_by": str(p.pinned_by_id),
            "pinned_at": p.pinned_at.isoformat(),
        } for p in pins])

    @extend_schema(
        summary='Get participant presences',
        description=(
            "Returns the current online/offline/away presence for every participant "
            "in the chat."
        ),
    )
    @action(detail=True, methods=["get"])
    def presences(self, request: Request, pk: Any = None) -> Response:
        try:
            presences = services.get_chat_presences(chat_id=pk, requesting_user_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(presences)

    @extend_schema(
        summary='Pin a message',
        description=(
            "Pins a message in the chat. Only chat admins may pin. Fires the "
            "message_pinned signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def pin_message(self, request: Request, pk: Any = None) -> Response:
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            pin = services.pin_message(message_id=message_id, chat_id=pk, pinned_by_id=request.user.pk)
            return Response({"pin_id": str(pin.id)}, status=status.HTTP_201_CREATED)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except (MessageNotFoundError, MessageDeletedError, MessagingError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Unpin a message',
        description=(
            "Removes a message from the pinned list. Fires the message_unpinned "
            "signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def unpin_message(self, request: Request, pk: Any = None) -> Response:
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            deleted = services.unpin_message(message_id=message_id, chat_id=pk, unpinned_by_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response({"unpinned": deleted})

    @extend_schema(
        summary='Forward a message',
        description=(
            "Forwards an existing message to one or more chats. Creates new "
            "ChatMessage records with forwarded_from set."
        ),
    )
    @action(detail=True, methods=["post"])
    def forward_message(self, request: Request, pk: Any = None) -> Response:
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            msg = services.forward_message(
                message_id=message_id, target_chat_id=pk, forwarded_by_id=request.user.pk
            )
            return Response(ChatMessageSerializer(msg, context={"request": request}).data, status=201)
        except (MessageNotFoundError, MessageDeletedError) as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except MessageForwardError as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Search messages in chat',
        description=(
            "Full-text search over messages in a single chat via Elasticsearch. "
            "Supports ?q= query parameter."
        ),
    )
    @action(detail=True, methods=["get"])
    def search_messages(self, request: Request, pk: Any = None) -> Response:
        query = request.query_params.get("q", "")
        results = services.search_messages(user_id=request.user.pk, query=query, chat_id=pk)
        return Response(ChatMessageSerializer(results, many=True, context={"request": request}).data)


class AdminBroadcastViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [BroadcastSendThrottle]
    serializer_class = AdminBroadcastSerializer
    filterset_class = BroadcastFilter

    def get_queryset(self):
        qs_ = (AdminBroadcast.objects.select_related("created_by").order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def perform_create(self, serializer):
        """
        Route creation through services.create_broadcast() to guarantee:
          - full_clean() validation runs
          - status is forced to DRAFT
          - tenant is assigned from the creator

        The serializer's validated_data is passed through, so all serializer
        validation still runs before this method is called.
        """
        vd = serializer.validated_data
        broadcast = services.create_broadcast(
            title=vd.get("title", ""),
            body=vd.get("body", ""),
            created_by_id=self.request.user.pk,
            audience_type=vd.get("audience_type", "ALL_USERS"),
            audience_filter=vd.get("audience_filter") or {},
            scheduled_at=vd.get("scheduled_at"),
        )
        # Sync back to serializer instance so DRF returns the correct response
        serializer.instance = broadcast

    @extend_schema(
        summary='Send broadcast immediately',
        description=(
            "Synchronously delivers the broadcast to all recipients. Use send_async "
            "for large audiences."
        ),
    )
    @action(detail=True, methods=["post"])
    @BROADCAST_SEND_SCHEMA
    def send(self, request: Request, pk: Any = None) -> Response:
        log.info("broadcast_send user=%s broadcast=%s", request.user.pk, pk)
        try:
            result = services.send_broadcast(broadcast_id=pk, actor_id=request.user.pk)
        except BroadcastNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except (BroadcastStateError, BroadcastSendError) as exc:
            return _error_response(exc)
        return Response(result)

    @extend_schema(
        summary='Queue broadcast for async delivery',
        description=(
            "Enqueues the broadcast via Celery. Returns a task ID for polling status. "
            "Preferred for audiences > 1,000."
        ),
    )
    @action(detail=True, methods=["post"])
    def send_async(self, request: Request, pk: Any = None) -> Response:
        log.info("broadcast_send_async user=%s broadcast=%s", request.user.pk, pk)
        from .tasks import send_broadcast_async
        send_broadcast_async.delay(str(pk), actor_id=request.user.pk)
        return Response({"queued": True, "broadcast_id": str(pk)})


class SupportThreadViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [SupportThreadCreateThrottle]
    filterset_class = SupportThreadFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return SupportThread.objects.none()
        user = self.request.user
        if user.is_staff:
            qs_ = (SupportThread.objects.select_related("user", "assigned_agent").order_by("-created_at"))
            return qs_.filter(tenant=getattr(self.request, "tenant", None))
        qs_ = (SupportThread.objects.filter(user=user).order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def get_serializer_class(self):
        if self.action == "create":
            return CreateSupportThreadSerializer
        return SupportThreadSerializer

    def list(self, request: Request) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer = SupportThreadSerializer(page or qs, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request: Request) -> Response:
        serializer = CreateSupportThreadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            thread = services.create_support_thread(
                user_id=request.user.pk,
                subject=serializer.validated_data["subject"],
                initial_message=serializer.validated_data["initial_message"],
                priority=serializer.validated_data.get("priority", SupportThreadPriority.NORMAL),
            )
        except (MessagingError, SupportThreadLimitError) as exc:
            return _error_response(exc)
        return Response(SupportThreadSerializer(thread, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: Any = None) -> Response:
        try:
            thread = self.get_queryset().get(pk=pk)
        except SupportThread.DoesNotExist:
            return _error_response(SupportThreadNotFoundError(f"Thread {pk} not found."), status.HTTP_404_NOT_FOUND)
        serializer = SupportThreadSerializer(thread, context={"request": request})
        messages = SupportMessageSerializer(
            thread.messages.all().order_by("created_at"),
            many=True, context={"request": request},
        )
        data = serializer.data
        data["messages"] = messages.data
        return Response(data)

    @extend_schema(
        summary='Reply to support thread',
        description=(
            "Adds a reply message to the thread. Fires support_reply_posted signal "
            "and sends push notification to the other party."
        ),
    )
    @action(detail=True, methods=["post"])
    def reply(self, request: Request, pk: Any = None) -> Response:
        content = request.data.get("content", "")
        is_internal = request.data.get("is_internal_note", False) and request.user.is_staff
        if not content:
            return Response({"detail": "content required."}, status=400)
        try:
            msg = services.reply_to_support_thread(
                thread_id=pk,
                sender_id=request.user.pk,
                content=content,
                is_agent=request.user.is_staff,
                is_internal_note=is_internal,
            )
        except SupportThreadNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except SupportThreadClosedError as exc:
            return _error_response(exc)
        return Response(SupportMessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Assign support thread to agent',
        description=(
            "Admin only. Assigns the thread to a support agent. Fires "
            "support_thread_status_changed signal."
        ),
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def assign(self, request: Request, pk: Any = None) -> Response:
        log.info("support_assign admin=%s thread=%s", request.user.pk, pk)
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"detail": "agent_id required."}, status=400)
        try:
            thread = services.assign_support_thread(thread_id=pk, agent_id=agent_id, assigner_id=request.user.pk)
        except (SupportThreadNotFoundError, UserNotFoundError) as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        return Response(SupportThreadSerializer(thread, context={"request": request}).data)

    @extend_schema(
        summary='Change support thread status',
        description=(
            "Admin only. Transitions thread status (OPEN → IN_PROGRESS → RESOLVED → "
            "CLOSED). Validated against allowed transitions."
        ),
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def transition(self, request: Request, pk: Any = None) -> Response:
        log.info("support_transition admin=%s thread=%s status=%s", request.user.pk, pk, request.data.get("status"))
        new_status = request.data.get("status")
        if not new_status:
            return Response({"detail": "status required."}, status=400)
        try:
            thread = self.get_queryset().get(pk=pk)
            thread.transition_to(new_status, agent=request.user)
        except (SupportThread.DoesNotExist, SupportThreadClosedError, ValueError) as exc:
            return _error_response(exc)
        return Response(SupportThreadSerializer(thread, context={"request": request}).data)


class UserInboxViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination
    serializer_class = UserInboxSerializer
    filterset_class = UserInboxFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return UserInbox.objects.none()
        qs_ = (UserInbox.objects
            .filter(user=self.request.user, is_archived=False)
            .order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    @extend_schema(
        summary='Get unread inbox count',
        description=(
            "Returns the total number of unread UserInbox items for the authenticated "
            "user."
        ),
    )
    @action(detail=False, methods=["get"])
    def unread_count(self, request: Request) -> Response:
        count = services.get_unread_count(user_id=request.user.pk)
        return Response({"unread_count": count})

    @extend_schema(
        summary='Mark all inbox items as read',
        description=(
            "Bulk-marks every unread inbox item as read. Resets unread badge to 0."
        ),
    )
    @action(detail=False, methods=["post"])
    def mark_all_read(self, request: Request) -> Response:
        updated = services.mark_inbox_items_read(user_id=request.user.pk)
        return Response({"updated": updated})

    @extend_schema(
        summary='Mark inbox item as read',
        description=(
            "Marks a single UserInbox item as read and updates last_read_at."
        ),
    )
    @action(detail=True, methods=["post"])
    def mark_read(self, request: Request, pk: Any = None) -> Response:
        log.debug("mark_read user=%s chat=%s", request.user.pk, pk)
        updated = services.mark_inbox_items_read(user_id=request.user.pk, item_ids=[pk])
        return Response({"updated": updated})

    @extend_schema(
        summary='Archive inbox item',
        description=(
            "Moves an inbox item to the archived state. Archived items are excluded "
            "from the default list view."
        ),
    )
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: Any = None) -> Response:
        try:
            item = UserInbox.objects.get(pk=pk, user=request.user)
            item.archive()
        except UserInbox.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response({"archived": True})


# ============================================================================
# NEW ViewSets
# ============================================================================

class MessageReactionViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Reactions on messages."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]
    throttle_classes     = [ReactionThrottle]

    @extend_schema(
        summary='Add reaction to message',
        description=(
            "Adds an emoji reaction. Fires message_reaction_added signal. Idempotent "
            "— re-adding the same emoji updates existing record."
        ),
    )
    @action(detail=False, methods=["post"])
    def add(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        emoji = request.data.get("emoji")
        custom_emoji = request.data.get("custom_emoji", "")
        if not message_id or not emoji:
            return Response({"detail": "message_id and emoji required."}, status=400)
        try:
            reaction = services.add_reaction(
                message_id=message_id, user_id=request.user.pk,
                emoji=emoji, custom_emoji=custom_emoji,
            )
            return Response({"id": str(reaction.id), "emoji": reaction.emoji}, status=201)
        except (MessageNotFoundError, MessageDeletedError, ChatAccessDeniedError, RateLimitError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Remove reaction from message',
        description=(
            "Removes the authenticated user's reaction. Fires "
            "message_reaction_removed signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def remove(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        emoji = request.data.get("emoji")
        if not message_id or not emoji:
            return Response({"detail": "message_id and emoji required."}, status=400)
        deleted = services.remove_reaction(message_id=message_id, user_id=request.user.pk, emoji=emoji)
        return Response({"deleted": deleted})

    @extend_schema(
        summary='List reactions for a message',
        description=(
            "Returns all emoji reactions grouped by emoji with per-emoji user lists."
        ),
    )
    @action(detail=False, methods=["get"])
    def for_message(self, request: Request) -> Response:
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            reactions = services.get_message_reactions(message_id, request.user.pk)
        except (MessageNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc)
        return Response(reactions)


class UserPresenceViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Presence status management."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]

    @extend_schema(
        summary='Get own presence',
        description=(
            "Returns the authenticated user's current presence record (status, "
            "last_seen, custom_status)."
        ),
    )
    @action(detail=False, methods=["get"])
    def me(self, request: Request) -> Response:
        presence = services.get_presence(request.user.pk)
        return Response(presence)

    @extend_schema(
        summary='Update presence status',
        description=(
            "Sets presence to ONLINE, AWAY, BUSY, or OFFLINE. ONLINE refreshes the "
            "heartbeat; OFFLINE triggers presence_changed signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def update_status(self, request: Request) -> Response:
        status_val = request.data.get("status")
        platform = request.data.get("platform", "web")
        if not status_val:
            return Response({"detail": "status required."}, status=400)
        presence = services.update_presence(user_id=request.user.pk, status=status_val, platform=platform)
        return Response({"status": presence.status, "last_seen_at": presence.last_seen_at.isoformat()})

    @extend_schema(
        summary='Set custom status text',
        description=(
            "Sets a custom status string (e.g. 'In a meeting'). Visible to chat "
            "participants."
        ),
    )
    @action(detail=False, methods=["post"])
    def set_custom_status(self, request: Request) -> Response:
        custom_status = request.data.get("custom_status", "")
        emoji = request.data.get("emoji", "")
        try:
            UserPresence.objects.update_or_create(
                user_id=request.user.pk,
                defaults={"custom_status": custom_status[:128], "custom_status_emoji": emoji[:10]},
            )
        except Exception as exc:
            return _error_response(MessagingError(str(exc)))
        return Response({"custom_status": custom_status, "emoji": emoji})

    @extend_schema(
        summary='Get presences for a chat',
        description=(
            "Returns presence records for all active participants in a specific chat."
        ),
    )
    @action(detail=False, methods=["get"])
    def for_chat(self, request: Request) -> Response:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            presences = services.get_chat_presences(chat_id=chat_id, requesting_user_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(presences)

    @extend_schema(
        summary='Bulk get presences',
        description=(
            "Returns presence records for a list of user IDs passed as "
            "?user_ids=1,2,3."
        ),
    )
    @action(detail=False, methods=["get"])
    def bulk(self, request: Request) -> Response:
        user_ids = request.query_params.getlist("user_ids")
        return Response({uid: services.get_presence(uid) for uid in user_ids[:50]})


class CallSessionViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Voice/Video call sessions."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [CallInitiateThrottle]

    def get_queryset(self):
        qs_ = (CallSession.objects.filter(
            participants=self.request.user
        ).select_related("initiated_by").order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id": str(c.id), "call_type": c.call_type, "status": c.status,
            "room_id": c.room_id, "duration_seconds": c.duration_seconds,
            "initiated_by": str(c.initiated_by_id), "created_at": c.created_at.isoformat(),
        } for c in qs[:20]]
        return Response(data)

    @extend_schema(
        summary='Initiate a call',
        description=(
            "Starts a new audio or video call. Creates a CallSession, fires "
            "call_started signal, and returns ICE server credentials for WebRTC "
            "setup."
        ),
    )
    @action(detail=False, methods=["post"])
    def initiate(self, request: Request) -> Response:
        log.info("call_initiate user=%s", request.user.pk)
        chat_id = request.data.get("chat_id")
        call_type = request.data.get("call_type", CallType.AUDIO)
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            from .utils.call_manager import get_ice_servers
            call = services.initiate_call(
                caller_id=request.user.pk, chat_id=chat_id,
                call_type=call_type, ice_servers=get_ice_servers(request.user.pk),
            )
            return Response({
                "call_id": str(call.id), "room_id": call.room_id,
                "call_type": call.call_type, "status": call.status,
                "ice_servers": call.ice_servers,
                "ws_url": f"/ws/messaging/call/{call.room_id}/",
            }, status=201)
        except (ChatNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except CallAlreadyActiveError as exc:
            return _error_response(exc, status.HTTP_409_CONFLICT)
        except (RateLimitError, MessagingError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Accept incoming call',
        description=(
            "Accepts an incoming call. Transitions CallSession to IN_PROGRESS. "
            "Returns updated ICE credentials."
        ),
    )
    @action(detail=True, methods=["post"])
    def accept(self, request: Request, pk: Any = None) -> Response:
        log.info("call_accept user=%s call=%s", request.user.pk, pk)
        try:
            call = services.accept_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status, "room_id": call.room_id})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Decline incoming call',
        description=(
            "Declines an incoming call. Transitions to DECLINED. Fires call_ended "
            "signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def decline(self, request: Request, pk: Any = None) -> Response:
        try:
            call = services.decline_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='End an active call',
        description=(
            "Ends an in-progress call. Records duration, transitions to COMPLETED, "
            "fires call_ended signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def end(self, request: Request, pk: Any = None) -> Response:
        log.info("call_end user=%s call=%s", request.user.pk, pk)
        try:
            call = services.end_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status, "duration_seconds": call.duration_seconds})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Get call history',
        description=(
            "Returns paginated call history for the authenticated user, ordered by "
            "started_at descending."
        ),
    )
    @action(detail=False, methods=["get"])
    def history(self, request: Request) -> Response:
        qs = self.get_queryset().filter(
            status__in=[CallStatus.ENDED, CallStatus.MISSED, CallStatus.DECLINED]
        )
        data = [{
            "id": str(c.id), "call_type": c.call_type, "status": c.status,
            "duration_seconds": c.duration_seconds, "created_at": c.created_at.isoformat(),
        } for c in qs[:50]]
        return Response(data)


class AnnouncementChannelViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Telegram-style announcement channels."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [SearchFilter, OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs_ = (AnnouncementChannel.objects.all().order_by("-subscriber_count"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        channel_type = request.query_params.get("type")
        if channel_type:
            qs = qs.filter(channel_type=channel_type)
        data = [{
            "id": str(c.id), "name": c.name, "slug": c.slug,
            "description": c.description, "channel_type": c.channel_type,
            "subscriber_count": c.subscriber_count, "post_count": c.post_count,
            "is_verified": c.is_verified,
        } for c in qs[:50]]
        return Response(data)

    def create(self, request: Request) -> Response:
        try:
            channel = services.create_channel(
                name=request.data.get("name", ""),
                created_by_id=request.user.pk,
                description=request.data.get("description", ""),
                channel_type=request.data.get("channel_type", "PUBLIC"),
                tenant=getattr(request, "tenant", None),
            )
            return Response({"id": str(channel.id), "slug": channel.slug}, status=201)
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Subscribe to channel',
        description=(
            "Subscribes the authenticated user to the announcement channel. Creates a "
            "ChannelMember record."
        ),
    )
    @action(detail=True, methods=["post"])
    def subscribe(self, request: Request, pk: Any = None) -> Response:
        try:
            member = services.subscribe_channel(channel_id=pk, user_id=request.user.pk)
            return Response({"subscribed": True, "member_id": str(member.id)})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Unsubscribe from channel',
        description=(
            "Removes the user's ChannelMember record. The user will no longer receive "
            "announcements from this channel."
        ),
    )
    @action(detail=True, methods=["post"])
    def unsubscribe(self, request: Request, pk: Any = None) -> Response:
        deleted = services.unsubscribe_channel(channel_id=pk, user_id=request.user.pk)
        return Response({"unsubscribed": deleted})

    @extend_schema(
        summary='List channel members',
        description=(
            "Returns paginated list of users subscribed to this announcement channel."
        ),
    )
    @action(detail=True, methods=["get"])
    def members(self, request: Request, pk: Any = None) -> Response:
        members = ChannelMember.objects.filter(channel_id=pk).select_related("user")
        return Response([{
            "user_id": str(m.user_id), "is_admin": m.is_admin,
            "joined_at": m.joined_at.isoformat(),
        } for m in members[:100]])


class ScheduledMessageViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Scheduled future messages."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ScheduledMessage.objects.none()
        qs_ = (ScheduledMessage.objects.filter(
            sender=self.request.user
        ).order_by("scheduled_for"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id": str(s.id), "chat_id": str(s.chat_id), "content": s.content[:80],
            "scheduled_for": s.scheduled_for.isoformat(), "status": s.status,
        } for s in qs]
        return Response(data)

    def create(self, request: Request) -> Response:
        chat_id = request.data.get("chat_id")
        content = request.data.get("content", "")
        scheduled_for_str = request.data.get("scheduled_for")
        if not all([chat_id, content, scheduled_for_str]):
            return Response({"detail": "chat_id, content, scheduled_for required."}, status=400)
        try:
            from django.utils.dateparse import parse_datetime
            scheduled_for = parse_datetime(scheduled_for_str)
            if not scheduled_for:
                return Response({"detail": "Invalid scheduled_for datetime."}, status=400)
            sched = services.schedule_message(
                chat_id=chat_id, sender_id=request.user.pk,
                content=content, scheduled_for=scheduled_for,
                message_type=request.data.get("message_type", "TEXT"),
                attachments=request.data.get("attachments", []),
            )
            return Response({"id": str(sched.id), "scheduled_for": sched.scheduled_for.isoformat()}, status=201)
        except (ChatNotFoundError, ChatAccessDeniedError, MessagingError) as exc:
            return _error_response(exc)

    def destroy(self, request: Request, pk: Any = None) -> Response:
        try:
            sched = services.cancel_scheduled_message(scheduled_id=pk, user_id=request.user.pk)
            return Response({"cancelled": True})
        except (MessagingError, ChatAccessDeniedError) as exc:
            return _error_response(exc)


class MessagePinViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Message pins."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]

    @extend_schema(
        summary='List pinned messages for chat',
        description=(
            "Returns all MessagePin records for a chat. Pass ?chat_id= to filter."
        ),
    )
    @action(detail=False, methods=["get"])
    def for_chat(self, request: Request) -> Response:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            pins = services.get_pinned_messages(chat_id=chat_id, requesting_user_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response([{
            "pin_id": str(p.id), "message_id": str(p.message_id),
            "pinned_by": str(p.pinned_by_id), "pinned_at": p.pinned_at.isoformat(),
        } for p in pins])

    @extend_schema(
        summary='Pin a message',
        description=(
            "Creates a MessagePin for the given message_id in the given chat_id."
        ),
    )
    @action(detail=False, methods=["post"])
    def pin(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        chat_id = request.data.get("chat_id")
        if not message_id or not chat_id:
            return Response({"detail": "message_id and chat_id required."}, status=400)
        try:
            pin = services.pin_message(message_id=message_id, chat_id=chat_id, pinned_by_id=request.user.pk)
            return Response({"pin_id": str(pin.id)}, status=201)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        except (MessageNotFoundError, MessageDeletedError, MessagingError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Unpin a message',
        description=(
            "Removes the MessagePin. Fires message_unpinned signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def unpin(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        chat_id = request.data.get("chat_id")
        if not message_id or not chat_id:
            return Response({"detail": "message_id and chat_id required."}, status=400)
        try:
            deleted = services.unpin_message(message_id=message_id, chat_id=chat_id, unpinned_by_id=request.user.pk)
        except ChatNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response({"unpinned": deleted})


class BotConfigViewSet(SchemaSafeSerializerClassMixin, viewsets.ModelViewSet):
    """Auto-reply bot configuration."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [SearchFilter, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [BotRequestThrottle]

    def get_queryset(self):
        qs_ = (BotConfig.objects.all().order_by("-priority"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id": str(b.id), "name": b.name, "trigger_type": b.trigger_type,
            "trigger_value": b.trigger_value, "is_active": b.is_active, "priority": b.priority,
        } for b in qs]
        return Response(data)

    def create(self, request: Request) -> Response:
        try:
            bot = BotConfig.objects.create(
                name=request.data.get("name", "Bot"),
                trigger_type=request.data.get("trigger_type", "KEYWORD"),
                trigger_value=request.data.get("trigger_value", ""),
                response_template=request.data.get("response_template", ""),
                is_active=request.data.get("is_active", True),
                priority=request.data.get("priority", 0),
                delay_seconds=request.data.get("delay_seconds", 0),
                created_by=request.user,
                chat_id=request.data.get("chat_id"),
                tenant=getattr(request, "tenant", None),
            )
            return Response({"id": str(bot.id)}, status=201)
        except Exception as exc:
            return _error_response(MessagingError(str(exc)))

    def destroy(self, request: Request, pk: Any = None) -> Response:
        BotConfig.objects.filter(pk=pk).delete()
        return Response(status=204)

    @extend_schema(
        summary='Toggle bot active state',
        description=(
            "Flips the bot's is_active flag. Inactive bots do not process trigger "
            "patterns."
        ),
    )
    @action(detail=True, methods=["post"])
    def toggle(self, request: Request, pk: Any = None) -> Response:
        try:
            bot = BotConfig.objects.get(pk=pk, tenant=getattr(request, "tenant", None))
            if not request.user.is_staff:
                raise PermissionDeniedError("Only admins can toggle bots.")
            bot.is_active = not bot.is_active
            bot.save(update_fields=["is_active"])
            return Response({"is_active": bot.is_active})
        except BotConfig.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        except PermissionDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)


class MessagingWebhookViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Outbound webhook registrations."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [SearchFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs_ = (MessagingWebhook.objects.all().order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id": str(w.id), "name": w.name, "url": w.url,
            "events": w.events, "is_active": w.is_active,
            "failure_count": w.failure_count,
            "last_triggered_at": w.last_triggered_at.isoformat() if w.last_triggered_at else None,
        } for w in qs]
        return Response(data)

    def create(self, request: Request) -> Response:
        import secrets
        secret = request.data.get("secret") or secrets.token_hex(32)
        webhook = MessagingWebhook.objects.create(
            name=request.data.get("name", "Webhook"),
            url=request.data.get("url", ""),
            secret=secret,
            events=request.data.get("events", []),
            created_by=request.user,
            tenant=getattr(request, "tenant", None),
        )
        return Response({"id": str(webhook.id), "secret": secret}, status=201)

    def destroy(self, request: Request, pk: Any = None) -> Response:
        MessagingWebhook.objects.filter(pk=pk).delete()
        return Response(status=204)

    @extend_schema(summary='Test')
    @action(detail=True, methods=["post"])
    def test(self, request: Request, pk: Any = None) -> Response:
        try:
            webhook = MessagingWebhook.objects.get(
                pk=pk, tenant=getattr(request, "tenant", None)
            )
            services.dispatch_webhook_event("message.sent", {
                "message_id": "test-00000000",
                "chat_id": "test",
                "test": True,
            }, webhook_id=str(webhook.pk))
            return Response({"queued": True})
        except MessagingWebhook.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)


class UserBlockViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Block/unblock users."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [SearchFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs_ = (UserBlock.objects.filter(blocker=self.request.user))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset().select_related("blocked")
        data = [{"blocked_user_id": str(b.blocked_id), "reason": b.reason} for b in qs]
        return Response(data)

    @extend_schema(
        summary='Block a user',
        description=(
            "Creates a UserBlock record. Blocked users cannot send messages to the "
            "blocker. Fires user_blocked signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def block(self, request: Request) -> Response:
        log.info("user_block actor=%s target=%s", request.user.pk, request.data.get("user_id"))
        blocked_id = request.data.get("user_id")
        reason = request.data.get("reason", "")
        if not blocked_id:
            return Response({"detail": "user_id required."}, status=400)
        try:
            block = services.block_user(blocker_id=request.user.pk, blocked_id=blocked_id, reason=reason)
            return Response({"blocked": True, "block_id": str(block.id)}, status=201)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Unblock a user',
        description=(
            "Removes the UserBlock. The previously blocked user can now send messages "
            "again. Fires user_unblocked signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def unblock(self, request: Request) -> Response:
        blocked_id = request.data.get("user_id")
        log.info("user_unblock actor=%s target=%s", request.user.pk, blocked_id)
        if not blocked_id:
            return Response({"detail": "user_id required."}, status=400)
        deleted = services.unblock_user(blocker_id=request.user.pk, blocked_id=blocked_id)
        return Response({"unblocked": deleted})


    @extend_schema(summary='Is blocked')
    @action(detail=False, methods=["get"])
    def is_blocked(self, request: Request) -> Response:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=400)
        return Response({"is_blocked": services.is_user_blocked(request.user.pk, user_id)})


class MessageSearchViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Full-text message search."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = []
    pagination_class     = SearchResultsPagination
    throttle_classes     = [SearchThrottle]

    def list(self, request: Request) -> Response:
        query = request.query_params.get("q", "")
        chat_id = request.query_params.get("chat_id")
        limit = int(request.query_params.get("limit", 20))
        results = services.search_messages(
            user_id=request.user.pk, query=query, chat_id=chat_id, limit=limit,
        )
        from .serializers import ChatMessageSerializer
        return Response(ChatMessageSerializer(results, many=True, context={"request": request}).data)


class DeviceTokenViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Push notification device token management."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs_ = (DeviceToken.objects.filter(user=self.request.user, is_active=True))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        return Response([{
            "id": str(t.id), "platform": t.platform,
            "device_name": t.device_name, "app_version": t.app_version,
        } for t in qs])

    def create(self, request: Request) -> Response:
        token_str = request.data.get("token", "")
        platform = request.data.get("platform", "android")
        if not token_str:
            return Response({"detail": "token required."}, status=400)
        token, created = DeviceToken.objects.update_or_create(
            token=token_str,
            defaults={
                "user": request.user,
                "platform": platform,
                "device_name": request.data.get("device_name", ""),
                "app_version": request.data.get("app_version", ""),
                "is_active": True,
                "tenant": getattr(request, "tenant", None),
            },
        )
        return Response({"id": str(token.id), "registered": True}, status=201 if created else 200)

    def destroy(self, request: Request, pk: Any = None) -> Response:
        DeviceToken.objects.filter(pk=pk, user=request.user).update(is_active=False)
        return Response(status=204)

    @extend_schema(summary='Unregister token')
    @action(detail=False, methods=["delete"])
    def unregister_token(self, request: Request) -> Response:
        token_str = request.data.get("token", "")
        if token_str:
            DeviceToken.objects.filter(token=token_str, user=request.user).update(is_active=False)
        return Response({"unregistered": True})


# ============================================================================
# FINAL 6% — New ViewSets
# ============================================================================

from .models import (
    MessageEditHistory, DisappearingMessageConfig, UserStory,
    StoryView, StoryHighlight, VoiceMessageTranscription,
    LinkPreview, MessageLinkPreview,
)


class MessageEditHistoryViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """View edit history of a message."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]

    @extend_schema(
        summary='Get message edit history',
        description=(
            "Returns all previous versions of a message, ordered by edited_at "
            "descending. Fires message_edited_with_history signal."
        ),
    )
    @action(detail=False, methods=["get"])
    def for_message(self, request: Request) -> Response:
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            history = services.get_message_edit_history(
                message_id=message_id, user_id=request.user.pk
            )
            return Response([{
                "id": str(h.id),
                "previous_content": h.previous_content,
                "edit_number": h.edit_number,
                "edited_by": str(h.edited_by_id),
                "edit_reason": h.edit_reason,
                "created_at": h.created_at.isoformat(),
            } for h in history])
        except (MessageNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc)

    @extend_schema(summary='Edit message')
    @action(detail=False, methods=["post"])
    def edit_message(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        new_content = request.data.get("content", "")
        reason = request.data.get("reason", "")
        if not message_id or not new_content:
            return Response({"detail": "message_id and content required."}, status=400)
        try:
            msg, history = services.edit_message_with_history(
                message_id=message_id,
                user_id=request.user.pk,
                new_content=new_content,
                reason=reason,
            )
            return Response({
                "message_id": str(msg.id),
                "content": msg.content,
                "edit_number": history.edit_number,
                "is_edited": msg.is_edited,
            })
        except (MessageNotFoundError, MessageDeletedError, ChatAccessDeniedError, MessagingError) as exc:
            return _error_response(exc)


class DisappearingMessageViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Disappearing message settings per chat."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]

    @extend_schema(summary='Config')
    @action(detail=False, methods=["get"])
    def config(self, request: Request) -> Response:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            config = DisappearingMessageConfig.objects.get(chat_id=chat_id)
            return Response({
                "chat_id": str(config.chat_id),
                "is_enabled": config.is_enabled,
                "ttl_seconds": config.ttl_seconds,
                "ttl_display": config.ttl_display,
                "enabled_at": config.enabled_at.isoformat() if config.enabled_at else None,
            })
        except DisappearingMessageConfig.DoesNotExist:
            return Response({"is_enabled": False})

    @extend_schema(
        summary='Set disappearing message timer',
        description=(
            "Configures auto-deletion of messages after a given duration. Pass "
            "duration_seconds=0 to disable. Fires disappearing_config_changed signal."
        ),
    )
    @action(detail=False, methods=["post"])
    def set_config(self, request: Request) -> Response:
        chat_id = request.data.get("chat_id")
        ttl_seconds = request.data.get("ttl_seconds")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        try:
            config = services.set_disappearing_messages(
                chat_id=chat_id,
                enabled_by_id=request.user.pk,
                ttl_seconds=int(ttl_seconds) if ttl_seconds else None,
            )
            return Response({
                "is_enabled": config.is_enabled,
                "ttl_seconds": config.ttl_seconds,
                "ttl_display": config.ttl_display,
            })
        except (ChatNotFoundError, ChatAccessDeniedError, MessagingError) as exc:
            return _error_response(exc)


class UserStoryViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """WhatsApp/Telegram-style 24-hour stories."""
    # Schema-generation only: list()/create()/etc. below build their own
    # Response(...) from services.* calls and never call self.get_queryset()
    # or self.get_object() at runtime - drf-spectacular still needs *some*
    # queryset to derive the detail-route path parameter's type from.
    queryset = UserStory.objects.none()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [StoryCreateThrottle]

    def list(self, request: Request) -> Response:
        """GET /messaging/stories/ — Stories tray for my contacts."""
        groups = services.get_active_stories_for_contacts(request.user.pk)
        data = []
        for g in groups:
            data.append({
                "user_id": str(g["user_id"]),
                "stories": [{
                    "id": str(s.id),
                    "story_type": s.story_type,
                    "content": s.content,
                    "media_url": s.media_url,
                    "thumbnail_url": s.thumbnail_url,
                    "background_color": s.background_color,
                    "duration_seconds": s.duration_seconds,
                    "expires_at": s.expires_at.isoformat(),
                    "view_count": s.view_count,
                    "seen": bool(s.my_views),
                    "link_url": s.link_url,
                    "location": s.location,
                    "music_track": s.music_track,
                } for s in g["stories"]],
                "has_unseen": g["has_unseen"],
            })
        return Response(data)

    def create(self, request: Request) -> Response:
        """POST /messaging/stories/ — Create a new story."""
        try:
            story = services.create_story(
                user_id=request.user.pk,
                story_type=request.data.get("story_type", "text"),
                content=request.data.get("content", ""),
                media_url=request.data.get("media_url"),
                background_color=request.data.get("background_color", "#000000"),
                visibility=request.data.get("visibility", "all"),
                link_url=request.data.get("link_url"),
                link_label=request.data.get("link_label", ""),
                location=request.data.get("location", ""),
                music_track=request.data.get("music_track"),
                tenant=getattr(request, "tenant", None),
            )
            from .signals import story_created
            story_created.send(sender=UserStory, story=story)
            return Response({"id": str(story.id), "expires_at": story.expires_at.isoformat()}, status=201)
        except (RateLimitError, MessagingError) as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Mark story as viewed',
        description=(
            "Records a StoryView for the authenticated user. Fires story_viewed "
            "signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def view(self, request: Request, pk: Any = None) -> Response:
        """POST /messaging/stories/{id}/view/"""
        try:
            story_view = services.view_story(story_id=pk, viewer_id=request.user.pk)
            from .signals import story_viewed
            story_viewed.send(
                sender=StoryView,
                view=story_view,
                story=story_view.story,
                viewer_id=request.user.pk,
            )
            return Response({"viewed": True, "view_id": str(story_view.id)})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary='Reply to a story',
        description=(
            "Posts a reply to a story. The reply is delivered as a direct message and "
            "fires story_replied signal."
        ),
    )
    @action(detail=True, methods=["post"])
    def reply(self, request: Request, pk: Any = None) -> Response:
        """POST /messaging/stories/{id}/reply/ {reply_text?, reaction_emoji?}"""
        try:
            story_view = services.reply_to_story(
                story_id=pk,
                viewer_id=request.user.pk,
                reply_text=request.data.get("reply_text", ""),
                reaction_emoji=request.data.get("reaction_emoji", ""),
            )
            return Response({"replied": True})
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(summary='Viewers')
    @action(detail=True, methods=["get"])
    def viewers(self, request: Request, pk: Any = None) -> Response:
        """GET /messaging/stories/{id}/viewers/ — Only visible to story owner."""
        views = StoryView.objects.filter(
            story_id=pk, story__user=request.user
        ).select_related("viewer").order_by("-viewed_at")
        return Response([{
            "viewer_id": str(v.viewer_id),
            "viewed_at": v.viewed_at.isoformat(),
            "reaction_emoji": v.reaction_emoji or "",
            "reply_text": v.reply_text,
        } for v in views[:100]])

    def destroy(self, request: Request, pk: Any = None) -> Response:
        """DELETE /messaging/stories/{id}/ — Delete own story."""
        from .models import UserStory
        UserStory.objects.filter(pk=pk, user=request.user).update(is_active=False)
        return Response(status=204)

    @extend_schema(summary='My stories')
    @action(detail=False, methods=["get"])
    def my_stories(self, request: Request) -> Response:
        """GET /messaging/stories/my_stories/ — All my active stories."""
        from .models import UserStory
        stories = UserStory.objects.filter(
            user=request.user, is_active=True
        ).order_by("-created_at")
        return Response([{
            "id": str(s.id), "story_type": s.story_type,
            "content": s.content, "media_url": s.media_url,
            "view_count": s.view_count, "expires_at": s.expires_at.isoformat(),
        } for s in stories])


class VoiceMessageViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Voice message waveform + transcription."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]
    throttle_classes     = [MediaUploadThrottle]

    @extend_schema(
        summary='Get voice message transcription',
        description=(
            "Returns the auto-generated transcription for a voice message. Returns "
            "404 if not yet processed."
        ),
    )
    @action(detail=False, methods=["get"])
    def transcription(self, request: Request) -> Response:
        """GET /messaging/voice/?message_id=<id>
        Ownership check: only chat participants can fetch transcription.
        """
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            t = VoiceMessageTranscription.objects.select_related(
                "message__chat"
            ).get(message_id=message_id)
            # Ownership: verify the requesting user is a chat participant
            try:
                services._assert_chat_participant(t.message.chat, request.user.pk)
            except Exception:
                return Response({"detail": "Access denied."}, status=403)
            return Response({
                "message_id": str(t.message_id),
                "text": t.transcribed_text,
                "language": t.language,
                "confidence": t.confidence,
                "duration_seconds": t.duration_seconds,
                "waveform": t.waveform_data or [],
                "is_processing": t.is_processing,
                "provider": t.provider,
            })
        except VoiceMessageTranscription.DoesNotExist:
            return Response({"status": "not_transcribed"}, status=404)

    @extend_schema(summary='Request transcription')
    @action(detail=False, methods=["post"])
    def request_transcription(self, request: Request) -> Response:
        """POST /messaging/voice/request_transcription/ {message_id}"""
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            message = ChatMessage.objects.select_related("chat").get(pk=message_id)
        except ChatMessage.DoesNotExist:
            return Response({"detail": "Message not found."}, status=404)
        try:
            services._assert_chat_participant(message.chat, request.user.pk)
        except Exception:
            return Response({"detail": "Access denied."}, status=403)
        from .tasks import process_voice_message_task
        process_voice_message_task.delay(message_id)
        return Response({"queued": True, "message_id": message_id})


class LinkPreviewViewSet(SchemaSafeSerializerClassMixin, viewsets.GenericViewSet):
    """Link preview metadata."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]

    def get_throttles(self):
        if self.action == "fetch":
            return [LinkPreviewFetchThrottle()]
        return super().get_throttles()

    @extend_schema(summary='For message')
    @action(detail=False, methods=["get"])
    def for_message(self, request: Request) -> Response:
        """GET /messaging/link-previews/?message_id=<id>"""
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            message = ChatMessage.objects.select_related("chat").get(pk=message_id)
        except ChatMessage.DoesNotExist:
            return Response({"detail": "Message not found."}, status=404)
        try:
            services._assert_chat_participant(message.chat, request.user.pk)
        except Exception:
            return Response({"detail": "Access denied."}, status=403)
        links = MessageLinkPreview.objects.filter(
            message_id=message_id, is_dismissed=False
        ).select_related("preview").order_by("position")
        return Response([{
            "id": str(lp.id),
            "url": lp.preview.url,
            "title": lp.preview.title,
            "description": lp.preview.description,
            "image_url": lp.preview.image_url,
            "favicon_url": lp.preview.favicon_url,
            "site_name": lp.preview.site_name,
            "domain": lp.preview.domain,
            "content_type": lp.preview.content_type,
            "video_url": lp.preview.video_url,
            "is_safe": lp.preview.is_safe,
        } for lp in links])

    @extend_schema(
        summary='Fetch link preview',
        description=(
            "Fetches Open Graph / oEmbed metadata for a given URL. Cached per URL."
        ),
    )
    @action(detail=False, methods=["post"])
    def fetch(self, request: Request) -> Response:
        """POST /messaging/link-previews/fetch/ {url} — Fetch preview for any URL."""
        url = request.data.get("url", "")
        if not url:
            return Response({"detail": "url required."}, status=400)
        from .utils.link_preview import fetch_link_preview
        data = fetch_link_preview(url)
        return Response(data)

    @extend_schema(
        summary='Dismiss link preview',
        description=(
            "Marks a MessageLinkPreview as dismissed for this message. Dismissed "
            "previews are hidden on all devices."
        ),
    )
    @action(detail=True, methods=["post"])
    def dismiss(self, request: Request, pk: Any = None) -> Response:
        """POST /messaging/link-previews/{id}/dismiss/"""
        MessageLinkPreview.objects.filter(pk=pk, message__sender=request.user).update(is_dismissed=True)
        return Response({"dismissed": True})


from django.utils import timezone as _tz
from .models import (
    BotResponse,
    BotInteraction,
    MessageReport,
    MessageSearchIndex,
    NotificationRead,
    PollVote,
    UserDevice,
    WebhookDelivery,
    CPABroadcast,
)
from .serializers import (
    BotResponseSerializer,
    BotInteractionSerializer,
    MessageReportSerializer,
    MessageSearchIndexSerializer,
    NotificationReadSerializer,
    PollVoteSerializer,
    UserDeviceSerializer,
    WebhookDeliverySerializer,
)



class BotResponseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /messaging/bot-responses/          — list trigger log
    GET  /messaging/bot-responses/{id}/     — single entry

    Supports ?bot_id=<uuid> and ?was_successful=true|false filters.
    """

    serializer_class = BotResponseSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [BotRequestThrottle]

    def get_queryset(self):
        qs = BotResponse.objects.select_related(
            "bot", "trigger_message", "sent_message"
        ).order_by("-created_at")

        bot_id = self.request.query_params.get("bot_id")
        if bot_id:
            qs = qs.filter(bot_id=bot_id)

        was_successful = self.request.query_params.get("was_successful")
        if was_successful is not None:
            qs = qs.filter(was_successful=was_successful.lower() == "true")

        qs_ = (qs)
        return qs_.filter(tenant=getattr(self.request, "tenant", None))


# ---------------------------------------------------------------------------
# BotInteractionViewSet (Part 20 — world-system audit: interactive components)
# ---------------------------------------------------------------------------

class BotInteractionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /messaging/bot-interactions/          — list interaction log
    GET /messaging/bot-interactions/{id}/     — single entry

    Supports ?bot_id=<uuid> and ?action_id=<str> filters. Admin-only, same
    as BotResponseViewSet - this is the click-side counterpart to that
    trigger-side log. Written tenant-scoped from the start (unlike most of
    this file before the world-system audit), since it's new in Part 20.
    """
    serializer_class = BotInteractionSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination
    throttle_classes     = [BotRequestThrottle]

    @extend_schema(
        summary="List bot interaction (button click) log",
        description="Admin-only, tenant-scoped. Filter with ?bot_id=<uuid> and ?action_id=<str>.",
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = BotInteraction.objects.select_related(
            "bot", "source_message", "user", "resulting_message"
        ).filter(
            tenant=getattr(self.request, "tenant", None)
        ).order_by("-created_at")

        bot_id = self.request.query_params.get("bot_id")
        if bot_id:
            qs = qs.filter(bot_id=bot_id)

        action_id = self.request.query_params.get("action_id")
        if action_id:
            qs = qs.filter(action_id=action_id)

        return qs


# ---------------------------------------------------------------------------
# MessageReportViewSet — report abusive messages; admin reviews them
# ---------------------------------------------------------------------------

class MessageReportViewSet(viewsets.ModelViewSet):
    """
    POST   /messaging/reports/              — any auth'd user: submit a report
    GET    /messaging/reports/              — admin: list all; users: own reports
    GET    /messaging/reports/{id}/         — retrieve
    PATCH  /messaging/reports/{id}/         — admin: update status / notes
    POST   /messaging/reports/{id}/review/  — admin: mark reviewed with action

    Supports ?status=pending|reviewed|resolved|dismissed filter (admin).
    """
    permission_classes   = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination

    serializer_class = MessageReportSerializer

    def get_permissions(self):
        # BUG FIX: "list" used to be grouped with the admin-only actions
        # below, which contradicted both this class's own docstring
        # ("users: own reports") and get_queryset()'s dedicated
        # non-admin filtering branch (`qs.filter(reported_by=user)`) -
        # that filtering was unreachable dead code for the list action
        # specifically, since non-admins got a 403 before ever reaching
        # it. Non-admins can now list, but still only ever see their own
        # reports (get_queryset already enforces that), so this doesn't
        # expose anyone else's data - it just makes listing actually
        # work the way the class was documented and built to.
        if self.action in ("update", "partial_update", "review", "destroy"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return MessageReport.objects.none()
        user = self.request.user
        qs = MessageReport.objects.select_related(
            "message", "reported_by", "reviewed_by"
        ).order_by("-created_at")

        if not user.is_staff:
            qs = qs.filter(reported_by=user)

        report_status = self.request.query_params.get("status")
        if report_status:
            qs = qs.filter(status=report_status)

        reason = self.request.query_params.get("reason")
        if reason:
            qs = qs.filter(reason=reason)

        qs_ = (qs)
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def perform_create(self, serializer):
        serializer.save(
            reported_by=self.request.user,
            tenant=getattr(self.request, "tenant", None),
        )

    @extend_schema(
        summary='Review a message report',
        description=(
            "Admin only. Marks the report as reviewed with an action taken "
            "(DISMISSED, WARNED, DELETED, BANNED)."
        ),
    )
    @action(detail=True, methods=["post"])
    def review(self, request: Request, pk: Any = None) -> Response:
        """Admin marks a report reviewed with optional status, note, and action."""
        report = self.get_object()

        new_status = request.data.get("status", MessageReport.STATUS_REVIEWED)
        valid_statuses = [
            MessageReport.STATUS_REVIEWED,
            MessageReport.STATUS_RESOLVED,
            MessageReport.STATUS_DISMISSED,
        ]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"status must be one of {valid_statuses}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone as _ts; now = _ts.now()
        MessageReport.objects.filter(pk=report.pk).update(
            status=new_status,
            reviewed_by=request.user,
            reviewed_at=now,
            moderator_note=request.data.get("moderator_note", report.moderator_note),
            action_taken=request.data.get("action_taken", report.action_taken),
        )
        report.refresh_from_db()
        return Response(MessageReportSerializer(report).data)


# ---------------------------------------------------------------------------
# MessageSearchIndexViewSet — DB search index admin view + rebuild trigger
# ---------------------------------------------------------------------------

class MessageSearchIndexViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /messaging/search-index/              — admin: browse DB index entries
    GET  /messaging/search-index/{id}/         — single entry
    POST /messaging/search-index/rebuild/      — admin: queue async full re-index

    Supports ?chat_id=<uuid> filter.
    """

    serializer_class = MessageSearchIndexSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs = MessageSearchIndex.objects.select_related(
            "message", "chat"
        ).order_by("-indexed_at")

        chat_id = self.request.query_params.get("chat_id")
        if chat_id:
            qs = qs.filter(chat_id=chat_id)

        qs_ = (qs)
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    @extend_schema(summary='Rebuild')
    @action(detail=False, methods=["post"])
    def rebuild(self, request: Request) -> Response:
        """Queue a full re-index of all messages in the background."""
        try:
            from .tasks import bulk_reindex_task as bulk_index_messages_task
            bulk_index_messages_task.delay()
            return Response(
                {"detail": "Full search index rebuild queued."},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            logger.error("MessageSearchIndexViewSet.rebuild: %s", exc)
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# NotificationReadViewSet — track broadcast open/click analytics
# ---------------------------------------------------------------------------

class NotificationReadViewSet(viewsets.ModelViewSet):
    """
    GET   /messaging/notification-reads/              — user's own open records
    POST  /messaging/notification-reads/              — record a broadcast open
    POST  /messaging/notification-reads/{id}/click/   — record CTA click

    Filtering: ?broadcast_id=<uuid>
    """

    serializer_class = NotificationReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return NotificationRead.objects.none()
        qs = NotificationRead.objects.filter(
            user=self.request.user
        ).select_related("broadcast").order_by("-opened_at")

        broadcast_id = self.request.query_params.get("broadcast_id")
        if broadcast_id:
            qs = qs.filter(broadcast_id=broadcast_id)

        qs_ = (qs)
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def create(self, request: Request, *args, **kwargs) -> Response:
        broadcast_id = request.data.get("broadcast_id")
        if not broadcast_id:
            return Response(
                {"detail": "broadcast_id required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            broadcast = CPABroadcast.objects.get(pk=broadcast_id)
        except CPABroadcast.DoesNotExist:
            return Response(
                {"detail": "Broadcast not found."}, status=status.HTTP_404_NOT_FOUND
            )

        read, created = NotificationRead.objects.get_or_create(
            broadcast=broadcast,
            user=request.user,
        )
        if created:
            CPABroadcast.objects.filter(pk=broadcast.pk).update(
                opened_count=broadcast.opened_count + 1
            )

        return Response(
            NotificationReadSerializer(read).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(summary='Click')
    @action(detail=True, methods=["post"])
    def click(self, request: Request, pk: Any = None) -> Response:
        """Record that the user clicked the CTA button on this notification."""
        read = self.get_object()
        if not read.clicked_at:
            from django.utils import timezone as _ts; now = _ts.now()
            NotificationRead.objects.filter(pk=read.pk).update(clicked_at=now)
            CPABroadcast.objects.filter(pk=read.broadcast_id).update(
                clicked_count=read.broadcast.clicked_count + 1
            )
        return Response({"clicked": True}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Updates not allowed on read records."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ---------------------------------------------------------------------------
# PollVoteViewSet — cast / retract votes on POLL messages
# ---------------------------------------------------------------------------

class PollVoteViewSet(viewsets.ModelViewSet):
    """
    GET    /messaging/poll-votes/?message_id=<id>   — votes for a poll
    POST   /messaging/poll-votes/                   — cast a vote
    DELETE /messaging/poll-votes/{id}/              — retract own vote

    Single-choice polls: casting a new vote automatically retracts the old one.
    Multiple-choice polls (poll_data.multiple_choice=true): each option tracked
    separately via the unique constraint (message, user, option_id).
    """

    serializer_class = PollVoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [DjangoFilterBackend]
    pagination_class     = SmallResultsPagination

    def get_queryset(self):
        """
        SECURITY: this used to return PollVote.objects.select_related(...)
        with NO scoping at all - the bare list endpoint exposed every
        vote from every user on the platform, ?user_id=<any id> exposed
        that user's complete voting history across every chat, and
        ?message_id=<any id> exposed votes for polls in chats the
        requester was never a participant of. Fixed:
          - message_id given: only if the requester is a participant of
            that message's chat (or staff) - otherwise empty, matching
            this file's existing pattern of not confirming existence to
            unauthorized callers rather than a distinct 403.
          - user_id given: only allowed to be the requester's own id
            unless staff - prevents pulling an arbitrary user's voting
            history by id.
          - neither given: defaults to the requester's own votes only
            (staff sees everything), never a platform-wide dump.
        """
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects with an AnonymousUser and no
            # real request - short-circuit before touching self.request.user.
            return PollVote.objects.none()
        user = self.request.user
        qs = PollVote.objects.select_related("message__chat", "user")

        message_id = self.request.query_params.get("message_id")
        if message_id:
            if not user.is_staff:
                try:
                    message = ChatMessage.objects.select_related("chat").get(pk=message_id)
                except ChatMessage.DoesNotExist:
                    qs_ = (qs.none())
                    return qs_.filter(tenant=getattr(self.request, "tenant", None))
                try:
                    services._assert_chat_participant(message.chat, user.pk)
                except Exception:
                    qs_ = (qs.none())
                    return qs_.filter(tenant=getattr(self.request, "tenant", None))
            qs = qs.filter(message_id=message_id)
        elif not user.is_staff:
            qs = qs.filter(user=user)

        user_id = self.request.query_params.get("user_id")
        if user_id:
            if not user.is_staff and str(user_id) != str(user.pk):
                qs_ = (qs.none())
                return qs_.filter(tenant=getattr(self.request, "tenant", None))
            qs = qs.filter(user_id=user_id)

        qs_ = (qs.order_by("-created_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def perform_create(self, serializer):
        message = serializer.validated_data["message"]
        user = self.request.user
        poll_data = message.poll_data or {}

        # Single-choice: remove old vote before saving new one
        if not poll_data.get("multiple_choice", False):
            PollVote.objects.filter(message=message, user=user).delete()

        serializer.save(
            user=user,
            tenant=getattr(self.request, "tenant", None),
        )

    def perform_update(self, serializer):
        if serializer.instance.user_id != self.request.user.pk and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cannot modify another user's vote.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cannot retract another user's vote.")
        instance.delete()

    @extend_schema(
        summary='Get poll results',
        description=(
            "Returns the current vote counts per option for a poll message. Includes "
            "the authenticated user's vote if cast."
        ),
    )
    @action(detail=False, methods=["get"])
    def results(self, request: Request) -> Response:
        """GET /messaging/poll-votes/results/?message_id=<id>"""
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response(
                {"detail": "message_id required."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            from . import services
            results = services.get_poll_results(message_id, request.user.pk)
            return Response(results)
        except Exception as exc:
            return _error_response(exc)


# ---------------------------------------------------------------------------
# UserDeviceViewSet — multi-device management and security
# ---------------------------------------------------------------------------

class UserDeviceViewSet(viewsets.ModelViewSet):
    """
    GET    /messaging/devices/              — list user's own active devices
    POST   /messaging/devices/              — register a new device
    PATCH  /messaging/devices/{id}/         — update device name / version
    DELETE /messaging/devices/{id}/         — soft-deregister (set is_active=False)
    POST   /messaging/devices/{id}/trust/   — admin: mark device trusted
    POST   /messaging/devices/{id}/distrust/— admin: revoke trusted status

    Admin can also filter by ?user_id=<pk> to see another user's devices.
    """

    serializer_class = UserDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends      = [OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            target_user_id = self.request.query_params.get("user_id")
            if target_user_id:
                qs_ = (UserDevice.objects.filter(user_id=target_user_id).order_by("-last_active_at"))
                return qs_.filter(tenant=getattr(self.request, "tenant", None))
        qs_ = (UserDevice.objects.filter(user=user, is_active=True).order_by("-last_active_at"))
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            last_active_at=_tz.now(),
            tenant=getattr(self.request, "tenant", None),
        )

    def perform_destroy(self, instance):
        # Soft-delete: marking inactive logs the logout without losing history
        if instance.user != self.request.user and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Cannot deregister another user's device.")
        UserDevice.objects.filter(pk=instance.pk).update(is_active=False)

    @extend_schema(summary='Trust')
    @action(detail=True, methods=["post"])
    def trust(self, request: Request, pk: Any = None) -> Response:
        """Admin marks a device as trusted (no re-verification needed)."""
        if not request.user.is_staff:
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)
        UserDevice.objects.filter(pk=pk).update(is_trusted=True)
        return Response({"is_trusted": True})

    @extend_schema(summary='Distrust')
    @action(detail=True, methods=["post"])
    def distrust(self, request: Request, pk: Any = None) -> Response:
        """Admin revokes trusted status — device must re-verify on next login."""
        if not request.user.is_staff:
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)
        UserDevice.objects.filter(pk=pk).update(is_trusted=False)
        return Response({"is_trusted": False})

    @extend_schema(summary='Heartbeat')
    @action(detail=False, methods=["post"])
    def heartbeat(self, request: Request) -> Response:
        """POST /messaging/devices/heartbeat/ — update last_active_at for current device."""
        device_id = request.data.get("device_id")
        if not device_id:
            return Response(
                {"detail": "device_id required."}, status=status.HTTP_400_BAD_REQUEST
            )
        from django.utils import timezone as _ts; now = _ts.now()
        updated = UserDevice.objects.filter(
            user=request.user, device_id=device_id, is_active=True
        ).update(last_active_at=now)
        return Response({"updated": bool(updated), "last_active_at": now.isoformat()})


# ---------------------------------------------------------------------------
# WebhookDeliveryViewSet — log of every outbound webhook attempt (admin only)
# ---------------------------------------------------------------------------

class WebhookDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /messaging/webhook-deliveries/              — list all deliveries
    GET  /messaging/webhook-deliveries/{id}/         — single delivery record
    POST /messaging/webhook-deliveries/{id}/retry/   — admin: queue a retry

    Supports ?webhook_id=<uuid> and ?is_successful=true|false filters.
    """

    serializer_class = WebhookDeliverySerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [DjangoFilterBackend, OrderingFilter]
    pagination_class     = StandardResultsPagination

    def get_queryset(self):
        qs = WebhookDelivery.objects.select_related("webhook").order_by("-created_at")

        webhook_id = self.request.query_params.get("webhook_id")
        if webhook_id:
            qs = qs.filter(webhook_id=webhook_id)

        is_successful = self.request.query_params.get("is_successful")
        if is_successful is not None:
            qs = qs.filter(is_successful=is_successful.lower() == "true")

        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        qs_ = (qs)
        return qs_.filter(tenant=getattr(self.request, "tenant", None))

    @extend_schema(
        summary='Retry webhook delivery',
        description=(
            "Manually retries a failed webhook delivery. Subject to max-retry limit."
        ),
    )
    @action(detail=True, methods=["post"])
    def retry(self, request: Request, pk: Any = None) -> Response:
        log.info("webhook_retry user=%s delivery=%s", request.user.pk, pk)
        """Queue a retry for a failed delivery."""
        delivery = self.get_object()
        if delivery.is_successful:
            return Response(
                {"detail": "Delivery already succeeded — no retry needed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from .tasks import retry_webhook_delivery_task
            retry_webhook_delivery_task.delay(str(delivery.id))
            return Response(
                {"detail": "Retry queued.", "delivery_id": str(delivery.id)},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            logger.error("WebhookDeliveryViewSet.retry: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================================
# Part 21 (world-system audit): Compliance Audit Trail & Retention
# ===========================================================================
from .models import AuditLogEntry, RetentionPolicy, LegalHold
from .serializers import AuditLogEntrySerializer, RetentionPolicySerializer, LegalHoldSerializer
from . import services as _compliance_services


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /messaging/audit-log/        — list, newest first
    GET /messaging/audit-log/{id}/   — single entry

    Admin-only, tenant-scoped. Supports ?action=<AuditAction>,
    ?target_type=<str>, ?target_id=<str> filters. Append-only on the
    model side (see AuditLogEntry) - this viewset is read-only for the
    same reason: an editable/deletable audit trail defeats its purpose.
    """
    serializer_class = AuditLogEntrySerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [OrderingFilter]
    pagination_class     = StandardResultsPagination

    @extend_schema(
        summary='List compliance audit log entries',
        description=(
            "Admin-only, tenant-scoped, newest first. Filter with "
            "?action=<AuditAction>, ?target_type=<str>, ?target_id=<str>."
        ),
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = AuditLogEntry.objects.select_related("actor").filter(
            tenant=getattr(self.request, "tenant", None)
        ).order_by("-created_at")

        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        target_type = self.request.query_params.get("target_type")
        if target_type:
            qs = qs.filter(target_type=target_type)
        target_id = self.request.query_params.get("target_id")
        if target_id:
            qs = qs.filter(target_id=target_id)

        return qs


class RetentionPolicyViewSet(viewsets.GenericViewSet):
    """
    GET  /messaging/retention-policy/               — this tenant's policy
                                                        (created with defaults on first read)
    PUT  /messaging/retention-policy/set_policy/    — {"chat_message_retention_days": N|null}

    Admin-only. One policy per tenant - there's no {id} in either URL
    because "which tenant" comes from the request, not a path param,
    same as e.g. BotConfigViewSet's tenant scoping.
    """
    serializer_class = RetentionPolicySerializer
    permission_classes = [permissions.IsAdminUser]

    @extend_schema(
        summary="Get this tenant's message retention policy",
        description="Created with defaults (unlimited retention) on first read if none exists yet.",
    )
    def list(self, request: Request) -> Response:
        tenant = getattr(request, "tenant", None)
        policy = _compliance_services.get_retention_policy(tenant)
        return Response(self.get_serializer(policy).data)

    @extend_schema(
        summary="Set this tenant's message retention policy",
        description=(
            "Body: {\"chat_message_retention_days\": N|null}. null means unlimited "
            "(no auto-expiry). Enforced by the cleanup_chats management command."
        ),
    )
    @action(detail=False, methods=["put"], url_path="")
    def set_policy(self, request: Request) -> Response:
        """PUT /messaging/retention-policy/ — separate from list() above
        because DRF's router only ever maps a viewset's update() to the
        detail route (.../{pk}/), never the list route; url_path="" keeps
        this on the same bare URL as list() instead of .../set_policy/."""
        tenant = getattr(request, "tenant", None)
        try:
            policy = _compliance_services.set_retention_policy(
                tenant=tenant,
                chat_message_retention_days=request.data.get("chat_message_retention_days"),
                updated_by_id=request.user.pk,
            )
            return Response(self.get_serializer(policy).data)
        except MessagingError as exc:
            return _error_response(exc)

    def get_queryset(self):
        # Required by GenericViewSet even though list()/update() above
        # don't use it - RetentionPolicy has no list/detail concept
        # (one row per tenant, addressed implicitly via request.tenant).
        return RetentionPolicy.objects.filter(tenant=getattr(self.request, "tenant", None))


class LegalHoldViewSet(viewsets.ModelViewSet):
    """
    GET  /messaging/legal-holds/               — list (admin, this tenant)
    POST /messaging/legal-holds/                — apply a hold
         {"chat_id"?: str, "user_id"?: str, "reason": str}
    POST /messaging/legal-holds/{id}/release/   — release a hold

    Admin-only, tenant-scoped. No PATCH/PUT/DELETE - a hold is applied and
    released, not edited, so its own history stays intact (is_active,
    released_at, released_by rather than a row that gets mutated away).
    """
    serializer_class = LegalHoldSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends      = [OrderingFilter]
    pagination_class     = StandardResultsPagination
    http_method_names    = ["get", "post", "head", "options"]

    def get_queryset(self):
        return LegalHold.objects.select_related("chat", "user", "applied_by").filter(
            tenant=getattr(self.request, "tenant", None)
        ).order_by("-created_at")

    @extend_schema(
        summary="Apply a legal hold",
        description=(
            'Body: {"chat_id"?: str, "user_id"?: str, "reason": str}. At least one '
            "of chat_id/user_id is required. A user-level hold protects every chat "
            "that user is a participant in, not just one chat."
        ),
    )
    def create(self, request: Request) -> Response:
        try:
            hold = _compliance_services.apply_legal_hold(
                tenant=getattr(request, "tenant", None),
                chat_id=request.data.get("chat_id"),
                user_id=request.data.get("user_id"),
                reason=request.data.get("reason", ""),
                applied_by_id=request.user.pk,
            )
            return Response(self.get_serializer(hold).data, status=status.HTTP_201_CREATED)
        except MessagingError as exc:
            return _error_response(exc)

    @extend_schema(
        summary="Release a legal hold",
        description="Sets is_active=False and records released_at/released_by. Cannot release a hold belonging to a different tenant.",
    )
    @action(detail=True, methods=["post"])
    def release(self, request: Request, pk=None) -> Response:
        try:
            hold = _compliance_services.release_legal_hold(
                hold_id=pk, released_by_id=request.user.pk,
                tenant_id=getattr(getattr(request, "tenant", None), "id", None),
            )
            return Response(self.get_serializer(hold).data)
        except MessagingError as exc:
            return _error_response(exc)
