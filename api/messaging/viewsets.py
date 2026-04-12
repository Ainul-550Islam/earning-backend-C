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
)
from .filters import ChatFilter, BroadcastFilter, SupportThreadFilter, UserInboxFilter
from .models import (
    InternalChat, ChatMessage, AdminBroadcast, SupportThread, UserInbox,
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

logger = logging.getLogger(__name__)


def _error_response(exc: Exception, http_status: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )


# ============================================================================
# EXISTING ViewSets (unchanged logic, kept complete)
# ============================================================================

class InternalChatViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = ChatFilter

    def get_queryset(self):
        return (
            InternalChat.objects
            .for_user(self.request.user.pk)
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
            return _error_response(ChatNotFoundError(f"Chat {pk} not found."), status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(InternalChatSerializer(chat, context={"request": request}).data)

    @action(detail=False, methods=["post"])
    def direct(self, request: Request) -> Response:
        other_user_id = request.data.get("user_id")
        if not other_user_id:
            return _error_response(MessagingError("user_id required."))
        try:
            chat = services.create_direct_chat(request.user.pk, other_user_id)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        return Response(InternalChatSerializer(chat, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def group(self, request: Request) -> Response:
        name = request.data.get("name", "")
        member_ids = request.data.get("member_ids", [])
        try:
            chat = services.create_group_chat(creator_id=request.user.pk, name=name, member_ids=member_ids)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)
        return Response(InternalChatSerializer(chat, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def messages(self, request: Request, pk: Any = None) -> Response:
        before_id = request.query_params.get("before_id")
        limit = int(request.query_params.get("limit", 20))
        try:
            msgs = services.get_chat_messages(chat_id=pk, user_id=request.user.pk, before_id=before_id, limit=limit)
        except (ChatNotFoundError, ChatAccessDeniedError) as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(ChatMessageSerializer(msgs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def send_message(self, request: Request, pk: Any = None) -> Response:
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
        return Response(ChatMessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="messages/(?P<message_id>[^/.]+)")
    def delete_message(self, request: Request, pk: Any = None, message_id: Any = None) -> Response:
        try:
            services.delete_chat_message(message_id=message_id, requesting_user_id=request.user.pk)
        except (MessageNotFoundError, MessageDeletedError) as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except ChatAccessDeniedError as exc:
            return _error_response(exc, status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def mark_read(self, request: Request, pk: Any = None) -> Response:
        item_ids = request.data.get("item_ids", [])
        updated = services.mark_inbox_items_read(user_id=request.user.pk, item_ids=item_ids or None)
        return Response({"updated": updated})

    @action(detail=True, methods=["get"])
    def pinned_messages(self, request: Request, pk: Any = None) -> Response:
        pins = services.get_pinned_messages(chat_id=pk)
        return Response([{
            "pin_id": str(p.id),
            "message_id": str(p.message_id),
            "pinned_by": str(p.pinned_by_id),
            "pinned_at": p.pinned_at.isoformat(),
        } for p in pins])

    @action(detail=True, methods=["get"])
    def presences(self, request: Request, pk: Any = None) -> Response:
        presences = services.get_chat_presences(chat_id=pk)
        return Response(presences)

    @action(detail=True, methods=["post"])
    def pin_message(self, request: Request, pk: Any = None) -> Response:
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            pin = services.pin_message(message_id=message_id, chat_id=pk, pinned_by_id=request.user.pk)
            return Response({"pin_id": str(pin.id)}, status=status.HTTP_201_CREATED)
        except (MessageNotFoundError, MessageDeletedError, MessagingError, ChatAccessDeniedError) as exc:
            return _error_response(exc)

    @action(detail=True, methods=["post"])
    def unpin_message(self, request: Request, pk: Any = None) -> Response:
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        deleted = services.unpin_message(message_id=message_id, chat_id=pk, unpinned_by_id=request.user.pk)
        return Response({"unpinned": deleted})

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
        except (MessageNotFoundError, MessageDeletedError, MessagingError) as exc:
            return _error_response(exc)

    @action(detail=True, methods=["get"])
    def search_messages(self, request: Request, pk: Any = None) -> Response:
        query = request.query_params.get("q", "")
        results = services.search_messages(user_id=request.user.pk, query=query, chat_id=pk)
        return Response(ChatMessageSerializer(results, many=True, context={"request": request}).data)


class AdminBroadcastViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminBroadcastSerializer
    filterset_class = BroadcastFilter

    def get_queryset(self):
        return AdminBroadcast.objects.select_related("created_by").order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def send(self, request: Request, pk: Any = None) -> Response:
        try:
            result = services.send_broadcast(broadcast_id=pk, actor_id=request.user.pk)
        except BroadcastNotFoundError as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        except (BroadcastStateError, BroadcastSendError) as exc:
            return _error_response(exc)
        return Response(result)

    @action(detail=True, methods=["post"])
    def send_async(self, request: Request, pk: Any = None) -> Response:
        from .tasks import send_broadcast_async
        send_broadcast_async.delay(str(pk), actor_id=request.user.pk)
        return Response({"queued": True, "broadcast_id": str(pk)})


class SupportThreadViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = SupportThreadFilter

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return SupportThread.objects.select_related("user", "assigned_agent").order_by("-created_at")
        return SupportThread.objects.filter(user=user).order_by("-created_at")

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

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def assign(self, request: Request, pk: Any = None) -> Response:
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"detail": "agent_id required."}, status=400)
        try:
            thread = services.assign_support_thread(thread_id=pk, agent_id=agent_id, assigner_id=request.user.pk)
        except (SupportThreadNotFoundError, UserNotFoundError) as exc:
            return _error_response(exc, status.HTTP_404_NOT_FOUND)
        return Response(SupportThreadSerializer(thread, context={"request": request}).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def transition(self, request: Request, pk: Any = None) -> Response:
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
    serializer_class = UserInboxSerializer
    filterset_class = UserInboxFilter

    def get_queryset(self):
        return (
            UserInbox.objects
            .filter(user=self.request.user, is_archived=False)
            .order_by("-created_at")
        )

    @action(detail=False, methods=["get"])
    def unread_count(self, request: Request) -> Response:
        count = services.get_unread_count(user_id=request.user.pk)
        return Response({"unread_count": count})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request: Request) -> Response:
        updated = services.mark_inbox_items_read(user_id=request.user.pk)
        return Response({"updated": updated})

    @action(detail=True, methods=["post"])
    def mark_read(self, request: Request, pk: Any = None) -> Response:
        updated = services.mark_inbox_items_read(user_id=request.user.pk, item_ids=[pk])
        return Response({"updated": updated})

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

class MessageReactionViewSet(viewsets.GenericViewSet):
    """Reactions on messages."""
    permission_classes = [permissions.IsAuthenticated]

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

    @action(detail=False, methods=["post"])
    def remove(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        emoji = request.data.get("emoji")
        if not message_id or not emoji:
            return Response({"detail": "message_id and emoji required."}, status=400)
        deleted = services.remove_reaction(message_id=message_id, user_id=request.user.pk, emoji=emoji)
        return Response({"deleted": deleted})

    @action(detail=False, methods=["get"])
    def for_message(self, request: Request) -> Response:
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        reactions = services.get_message_reactions(message_id)
        return Response(reactions)


class UserPresenceViewSet(viewsets.GenericViewSet):
    """Presence status management."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request: Request) -> Response:
        presence = services.get_presence(request.user.pk)
        return Response(presence)

    @action(detail=False, methods=["post"])
    def update_status(self, request: Request) -> Response:
        status_val = request.data.get("status")
        platform = request.data.get("platform", "web")
        if not status_val:
            return Response({"detail": "status required."}, status=400)
        presence = services.update_presence(user_id=request.user.pk, status=status_val, platform=platform)
        return Response({"status": presence.status, "last_seen_at": presence.last_seen_at.isoformat()})

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

    @action(detail=False, methods=["get"])
    def for_chat(self, request: Request) -> Response:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        presences = services.get_chat_presences(chat_id=chat_id)
        return Response(presences)

    @action(detail=False, methods=["get"])
    def bulk(self, request: Request) -> Response:
        user_ids = request.query_params.getlist("user_ids")
        return Response({uid: services.get_presence(uid) for uid in user_ids[:50]})


class CallSessionViewSet(viewsets.GenericViewSet):
    """Voice/Video call sessions."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CallSession.objects.filter(
            participants=self.request.user
        ).select_related("initiated_by").order_by("-created_at")

    def list(self, request: Request) -> Response:
        qs = self.get_queryset()
        data = [{
            "id": str(c.id), "call_type": c.call_type, "status": c.status,
            "room_id": c.room_id, "duration_seconds": c.duration_seconds,
            "initiated_by": str(c.initiated_by_id), "created_at": c.created_at.isoformat(),
        } for c in qs[:20]]
        return Response(data)

    @action(detail=False, methods=["post"])
    def initiate(self, request: Request) -> Response:
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
        except (ChatNotFoundError, ChatAccessDeniedError, RateLimitError, MessagingError) as exc:
            return _error_response(exc)

    @action(detail=True, methods=["post"])
    def accept(self, request: Request, pk: Any = None) -> Response:
        try:
            call = services.accept_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status, "room_id": call.room_id})
        except MessagingError as exc:
            return _error_response(exc)

    @action(detail=True, methods=["post"])
    def decline(self, request: Request, pk: Any = None) -> Response:
        try:
            call = services.decline_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status})
        except MessagingError as exc:
            return _error_response(exc)

    @action(detail=True, methods=["post"])
    def end(self, request: Request, pk: Any = None) -> Response:
        try:
            call = services.end_call(call_id=pk, user_id=request.user.pk)
            return Response({"status": call.status, "duration_seconds": call.duration_seconds})
        except MessagingError as exc:
            return _error_response(exc)

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


class AnnouncementChannelViewSet(viewsets.GenericViewSet):
    """Telegram-style announcement channels."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AnnouncementChannel.objects.all().order_by("-subscriber_count")

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

    @action(detail=True, methods=["post"])
    def subscribe(self, request: Request, pk: Any = None) -> Response:
        try:
            member = services.subscribe_channel(channel_id=pk, user_id=request.user.pk)
            return Response({"subscribed": True, "member_id": str(member.id)})
        except MessagingError as exc:
            return _error_response(exc)

    @action(detail=True, methods=["post"])
    def unsubscribe(self, request: Request, pk: Any = None) -> Response:
        deleted = services.unsubscribe_channel(channel_id=pk, user_id=request.user.pk)
        return Response({"unsubscribed": deleted})

    @action(detail=True, methods=["get"])
    def members(self, request: Request, pk: Any = None) -> Response:
        members = ChannelMember.objects.filter(channel_id=pk).select_related("user")
        return Response([{
            "user_id": str(m.user_id), "is_admin": m.is_admin,
            "joined_at": m.joined_at.isoformat(),
        } for m in members[:100]])


class ScheduledMessageViewSet(viewsets.GenericViewSet):
    """Scheduled future messages."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ScheduledMessage.objects.filter(
            sender=self.request.user
        ).order_by("scheduled_for")

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


class MessagePinViewSet(viewsets.GenericViewSet):
    """Message pins."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def for_chat(self, request: Request) -> Response:
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({"detail": "chat_id required."}, status=400)
        pins = services.get_pinned_messages(chat_id=chat_id)
        return Response([{
            "pin_id": str(p.id), "message_id": str(p.message_id),
            "pinned_by": str(p.pinned_by_id), "pinned_at": p.pinned_at.isoformat(),
        } for p in pins])

    @action(detail=False, methods=["post"])
    def pin(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        chat_id = request.data.get("chat_id")
        if not message_id or not chat_id:
            return Response({"detail": "message_id and chat_id required."}, status=400)
        try:
            pin = services.pin_message(message_id=message_id, chat_id=chat_id, pinned_by_id=request.user.pk)
            return Response({"pin_id": str(pin.id)}, status=201)
        except (MessageNotFoundError, MessageDeletedError, MessagingError, ChatAccessDeniedError) as exc:
            return _error_response(exc)

    @action(detail=False, methods=["post"])
    def unpin(self, request: Request) -> Response:
        message_id = request.data.get("message_id")
        chat_id = request.data.get("chat_id")
        if not message_id or not chat_id:
            return Response({"detail": "message_id and chat_id required."}, status=400)
        deleted = services.unpin_message(message_id=message_id, chat_id=chat_id, unpinned_by_id=request.user.pk)
        return Response({"unpinned": deleted})


class BotConfigViewSet(viewsets.ModelViewSet):
    """Auto-reply bot configuration."""
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return BotConfig.objects.all().order_by("-priority")

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

    @action(detail=True, methods=["post"])
    def toggle(self, request: Request, pk: Any = None) -> Response:
        try:
            bot = BotConfig.objects.get(pk=pk)
            bot.is_active = not bot.is_active
            bot.save(update_fields=["is_active"])
            return Response({"is_active": bot.is_active})
        except BotConfig.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)


class MessagingWebhookViewSet(viewsets.GenericViewSet):
    """Outbound webhook registrations."""
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return MessagingWebhook.objects.all().order_by("-created_at")

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

    @action(detail=True, methods=["post"])
    def test(self, request: Request, pk: Any = None) -> Response:
        try:
            webhook = MessagingWebhook.objects.get(pk=pk)
            services.dispatch_webhook_event("message.sent", {
                "message_id": "test-00000000",
                "chat_id": "test",
                "test": True,
            })
            return Response({"queued": True})
        except MessagingWebhook.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)


class UserBlockViewSet(viewsets.GenericViewSet):
    """Block/unblock users."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserBlock.objects.filter(blocker=self.request.user)

    def list(self, request: Request) -> Response:
        qs = self.get_queryset().select_related("blocked")
        data = [{"blocked_user_id": str(b.blocked_id), "reason": b.reason} for b in qs]
        return Response(data)

    @action(detail=False, methods=["post"])
    def block(self, request: Request) -> Response:
        blocked_id = request.data.get("user_id")
        reason = request.data.get("reason", "")
        if not blocked_id:
            return Response({"detail": "user_id required."}, status=400)
        try:
            block = services.block_user(blocker_id=request.user.pk, blocked_id=blocked_id, reason=reason)
            return Response({"blocked": True, "block_id": str(block.id)}, status=201)
        except (UserNotFoundError, MessagingError) as exc:
            return _error_response(exc)

    @action(detail=False, methods=["post"])
    def unblock(self, request: Request) -> Response:
        blocked_id = request.data.get("user_id")
        if not blocked_id:
            return Response({"detail": "user_id required."}, status=400)
        deleted = services.unblock_user(blocker_id=request.user.pk, blocked_id=blocked_id)
        return Response({"unblocked": deleted})

    @action(detail=False, methods=["get"])
    def is_blocked(self, request: Request) -> Response:
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"detail": "user_id required."}, status=400)
        return Response({"is_blocked": services.is_user_blocked(request.user.pk, user_id)})


class MessageSearchViewSet(viewsets.GenericViewSet):
    """Full-text message search."""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        query = request.query_params.get("q", "")
        chat_id = request.query_params.get("chat_id")
        limit = int(request.query_params.get("limit", 20))
        results = services.search_messages(
            user_id=request.user.pk, query=query, chat_id=chat_id, limit=limit,
        )
        from .serializers import ChatMessageSerializer
        return Response(ChatMessageSerializer(results, many=True, context={"request": request}).data)


class DeviceTokenViewSet(viewsets.GenericViewSet):
    """Push notification device token management."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user, is_active=True)

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


class MessageEditHistoryViewSet(viewsets.GenericViewSet):
    """View edit history of a message."""
    permission_classes = [permissions.IsAuthenticated]

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


class DisappearingMessageViewSet(viewsets.GenericViewSet):
    """Disappearing message settings per chat."""
    permission_classes = [permissions.IsAuthenticated]

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


class UserStoryViewSet(viewsets.GenericViewSet):
    """WhatsApp/Telegram-style 24-hour stories."""
    permission_classes = [permissions.IsAuthenticated]

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


class VoiceMessageViewSet(viewsets.GenericViewSet):
    """Voice message waveform + transcription."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def transcription(self, request: Request) -> Response:
        """GET /messaging/voice/?message_id=<id>"""
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        try:
            t = VoiceMessageTranscription.objects.get(message_id=message_id)
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

    @action(detail=False, methods=["post"])
    def request_transcription(self, request: Request) -> Response:
        """POST /messaging/voice/request_transcription/ {message_id}"""
        message_id = request.data.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
        from .tasks import process_voice_message_task
        process_voice_message_task.delay(message_id)
        return Response({"queued": True, "message_id": message_id})


class LinkPreviewViewSet(viewsets.GenericViewSet):
    """Link preview metadata."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def for_message(self, request: Request) -> Response:
        """GET /messaging/link-previews/?message_id=<id>"""
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)
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

    @action(detail=False, methods=["post"])
    def fetch(self, request: Request) -> Response:
        """POST /messaging/link-previews/fetch/ {url} — Fetch preview for any URL."""
        url = request.data.get("url", "")
        if not url:
            return Response({"detail": "url required."}, status=400)
        from .utils.link_preview import fetch_link_preview
        data = fetch_link_preview(url)
        return Response(data)

    @action(detail=True, methods=["post"])
    def dismiss(self, request: Request, pk: Any = None) -> Response:
        """POST /messaging/link-previews/{id}/dismiss/"""
        MessageLinkPreview.objects.filter(pk=pk, message__sender=request.user).update(is_dismissed=True)
        return Response({"dismissed": True})
