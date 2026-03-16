"""
Messaging WebSocket Consumers — Django Channels consumers for real-time chat.

All consumers follow the defensive pattern:
- Authenticate in websocket_connect / connect; reject if invalid.
- Catch all exceptions in receive; never crash the consumer.
- Use group names from constants to avoid magic strings.
- Validate all incoming messages before processing.
- Never trust client-supplied data without validation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .choices import MessageType
from .constants import WS_MESSAGE_MAX_SIZE, WS_GROUP_NAME_PREFIX, WS_SUPPORT_GROUP_PREFIX
from .exceptions import (
    ChatNotFoundError,
    ChatAccessDeniedError,
    ChatArchivedError,
    RateLimitError,
    WebSocketAuthError,
    MessagingError,
    SupportThreadNotFoundError,
    SupportThreadClosedError,
)
from .utils.websocket_auth import authenticate_websocket_user

logger = logging.getLogger(__name__)


def _chat_group_name(chat_id: Any) -> str:
    """Consistent group name for a chat room."""
    safe_id = str(chat_id).replace("-", "")
    return f"{WS_GROUP_NAME_PREFIX}{safe_id}"


def _support_group_name(thread_id: Any) -> str:
    """Consistent group name for a support thread room."""
    safe_id = str(thread_id).replace("-", "")
    return f"{WS_SUPPORT_GROUP_PREFIX}{safe_id}"


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for InternalChat rooms.

    Connection lifecycle:
    1. connect()   — authenticate user, validate chat access, join group.
    2. receive()   — validate + dispatch incoming messages.
    3. disconnect()— leave group, clean up presence.

    Client → Server message format:
    {
        "type": "chat.message",
        "content": "Hello",
        "message_type": "TEXT",          // optional, default TEXT
        "reply_to_id": "<uuid>",         // optional
        "attachments": [...]             // optional
    }

    Server → Client message format:
    {
        "type": "chat.message",
        "message_id": "<uuid>",
        "chat_id": "<uuid>",
        "sender_id": "<pk>",
        "sender_name": "<str>",
        "content": "<str>",
        "message_type": "TEXT",
        "created_at": "<iso8601>",
        "is_edited": false
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_id: Optional[str] = None
        self.group_name: Optional[str] = None
        self.user = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Authenticate and join the chat group.
        Rejects the connection if auth fails or user is not a participant.
        """
        try:
            self.user = await authenticate_websocket_user(self.scope)
        except WebSocketAuthError as exc:
            logger.warning("ChatConsumer: auth failed: %s", exc)
            await self.close(code=4001)
            return

        self.chat_id = self.scope["url_route"]["kwargs"].get("chat_id")
        if not self.chat_id:
            logger.warning("ChatConsumer: no chat_id in URL route.")
            await self.close(code=4002)
            return

        try:
            await self._assert_chat_access(self.chat_id, self.user.pk)
        except (ChatNotFoundError, ChatAccessDeniedError, ChatArchivedError) as exc:
            logger.warning(
                "ChatConsumer: access denied for user=%s chat=%s: %s",
                getattr(self.user, "pk", "?"), self.chat_id, exc,
            )
            await self.close(code=4003)
            return

        self.group_name = _chat_group_name(self.chat_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(
            "ChatConsumer: user=%s connected to chat=%s group=%s.",
            self.user.pk, self.chat_id, self.group_name,
        )

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    async def disconnect(self, close_code: int) -> None:
        if self.group_name:
            try:
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
            except Exception as exc:
                logger.error(
                    "ChatConsumer: error leaving group %s: %s", self.group_name, exc
                )
        logger.info(
            "ChatConsumer: user=%s disconnected from chat=%s code=%s.",
            getattr(self.user, "pk", "?"), self.chat_id, close_code,
        )

    # ------------------------------------------------------------------
    # Receive
    # ------------------------------------------------------------------

    async def receive_json(self, content: Any, **kwargs) -> None:
        """
        Handle an incoming JSON message from the client.
        All errors are caught and sent back as error frames.
        """
        if not isinstance(content, dict):
            await self._send_error("Message must be a JSON object.")
            return

        if len(json.dumps(content)) > WS_MESSAGE_MAX_SIZE:
            await self._send_error(
                f"Message exceeds maximum size of {WS_MESSAGE_MAX_SIZE} bytes."
            )
            return

        msg_type = content.get("type")
        if msg_type == "chat.message":
            await self._handle_chat_message(content)
        elif msg_type == "chat.read":
            await self._handle_mark_read(content)
        elif msg_type == "chat.typing":
            await self._handle_typing(content)
        else:
            await self._send_error(
                f"Unknown message type '{msg_type}'. "
                "Expected: chat.message, chat.read, chat.typing"
            )

    async def _handle_chat_message(self, content: dict) -> None:
        """Validate and persist a chat message, then broadcast to group."""
        raw_content = content.get("content", "")
        message_type = content.get("message_type", MessageType.TEXT)
        reply_to_id = content.get("reply_to_id")
        attachments = content.get("attachments", [])

        if not isinstance(raw_content, str) or not raw_content.strip():
            await self._send_error("content must be a non-empty string.")
            return

        if message_type not in MessageType.values:
            await self._send_error(
                f"Invalid message_type '{message_type}'."
            )
            return

        if not isinstance(attachments, list):
            await self._send_error("attachments must be a list.")
            return

        try:
            message = await self._send_message_to_db(
                content=raw_content.strip(),
                message_type=message_type,
                reply_to_id=reply_to_id,
                attachments=attachments,
            )
        except RateLimitError as exc:
            await self._send_error(str(exc), code="rate_limit")
            return
        except (ChatArchivedError, ChatAccessDeniedError, ChatNotFoundError) as exc:
            await self._send_error(str(exc), code="chat_error")
            return
        except MessagingError as exc:
            await self._send_error(str(exc))
            return
        except Exception as exc:
            logger.exception(
                "ChatConsumer._handle_chat_message: unexpected error for user=%s chat=%s: %s",
                getattr(self.user, "pk", "?"), self.chat_id, exc,
            )
            await self._send_error("An unexpected error occurred.")
            return

        # Broadcast to all group members
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message.broadcast",
                "message_id": str(message.id),
                "chat_id": str(self.chat_id),
                "sender_id": str(self.user.pk),
                "sender_name": self._get_display_name(self.user),
                "content": message.content,
                "message_type": message.message_type,
                "created_at": message.created_at.isoformat(),
                "is_edited": False,
                "reply_to_id": str(reply_to_id) if reply_to_id else None,
                "attachments": message.attachments if isinstance(message.attachments, list) else [],
            },
        )

    async def _handle_mark_read(self, content: dict) -> None:
        """Mark an inbox item as read."""
        item_ids = content.get("item_ids")
        if not isinstance(item_ids, list) or not item_ids:
            await self._send_error("item_ids must be a non-empty list.")
            return
        try:
            count = await self._mark_read_in_db(item_ids)
            await self.send_json({"type": "chat.read.ack", "updated": count})
        except Exception as exc:
            logger.error(
                "ChatConsumer._handle_mark_read: error for user=%s: %s",
                getattr(self.user, "pk", "?"), exc,
            )
            await self._send_error("Failed to mark messages as read.")

    async def _handle_typing(self, content: dict) -> None:
        """Broadcast typing indicator to group (no DB writes)."""
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.typing.broadcast",
                "user_id": str(self.user.pk),
                "user_name": self._get_display_name(self.user),
                "is_typing": bool(content.get("is_typing", True)),
            },
        )

    # ------------------------------------------------------------------
    # Group event handlers (channel layer → WebSocket)
    # ------------------------------------------------------------------

    async def chat_message_broadcast(self, event: dict) -> None:
        """Relay a group-sent chat message to this client."""
        await self.send_json(event)

    async def chat_typing_broadcast(self, event: dict) -> None:
        """Relay a typing indicator to this client."""
        # Don't send your own typing indicator back to yourself
        if str(event.get("user_id")) != str(self.user.pk):
            await self.send_json(event)

    # ------------------------------------------------------------------
    # DB helpers (sync_to_async wrappers)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _assert_chat_access(self, chat_id: Any, user_id: Any) -> None:
        from . import services
        chat = services._get_chat_or_raise(chat_id)
        chat.assert_active()
        services._assert_chat_participant(chat, user_id)

    @database_sync_to_async
    def _send_message_to_db(
        self,
        *,
        content: str,
        message_type: str,
        reply_to_id: Optional[Any],
        attachments: list,
    ):
        from . import services
        return services.send_chat_message(
            chat_id=self.chat_id,
            sender_id=self.user.pk,
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id,
            attachments=attachments,
        )

    @database_sync_to_async
    def _mark_read_in_db(self, item_ids: list) -> int:
        from . import services
        return services.mark_inbox_items_read(
            user_id=self.user.pk, item_ids=item_ids
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_error(self, detail: str, *, code: str = "error") -> None:
        """Send a structured error frame to the client."""
        try:
            await self.send_json({"type": "error", "code": code, "detail": detail})
        except Exception as exc:
            logger.error("ChatConsumer._send_error: failed to send error frame: %s", exc)

    @staticmethod
    def _get_display_name(user: Any) -> str:
        """Safe display name extraction."""
        try:
            full = f"{user.first_name or ''} {user.last_name or ''}".strip()
            return full or getattr(user, "username", str(user.pk))
        except Exception:
            return str(getattr(user, "pk", "unknown"))


# ---------------------------------------------------------------------------
# SupportConsumer
# ---------------------------------------------------------------------------

class SupportConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for SupportThread rooms.

    Only the thread owner and staff agents may connect.
    Internal notes (is_internal_note=True) are only sent to agents.

    Client → Server message format:
    {
        "type": "support.message",
        "content": "My issue is..."
    }

    Server → Client message format:
    {
        "type": "support.message",
        "message_id": "<uuid>",
        "thread_id": "<uuid>",
        "sender_id": "<pk>",
        "is_agent_reply": true/false,
        "content": "...",
        "created_at": "<iso8601>"
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_id: Optional[str] = None
        self.group_name: Optional[str] = None
        self.user = None
        self.is_agent: bool = False

    async def connect(self) -> None:
        try:
            self.user = await authenticate_websocket_user(self.scope)
        except WebSocketAuthError as exc:
            logger.warning("SupportConsumer: auth failed: %s", exc)
            await self.close(code=4001)
            return

        self.thread_id = self.scope["url_route"]["kwargs"].get("thread_id")
        if not self.thread_id:
            await self.close(code=4002)
            return

        try:
            self.is_agent = await self._check_thread_access(self.thread_id, self.user.pk)
        except (SupportThreadNotFoundError, PermissionError) as exc:
            logger.warning(
                "SupportConsumer: access denied for user=%s thread=%s: %s",
                self.user.pk, self.thread_id, exc,
            )
            await self.close(code=4003)
            return

        self.group_name = _support_group_name(self.thread_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(
            "SupportConsumer: user=%s (agent=%s) connected to thread=%s.",
            self.user.pk, self.is_agent, self.thread_id,
        )

    async def disconnect(self, close_code: int) -> None:
        if self.group_name:
            try:
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
            except Exception as exc:
                logger.error("SupportConsumer: error leaving group: %s", exc)

    async def receive_json(self, content: Any, **kwargs) -> None:
        if not isinstance(content, dict):
            await self._send_error("Message must be a JSON object.")
            return

        msg_type = content.get("type")
        if msg_type == "support.message":
            await self._handle_support_message(content)
        else:
            await self._send_error(f"Unknown type '{msg_type}'.")

    async def _handle_support_message(self, content: dict) -> None:
        raw_content = content.get("content", "")
        if not isinstance(raw_content, str) or not raw_content.strip():
            await self._send_error("content must be a non-empty string.")
            return

        try:
            msg = await self._post_reply(raw_content.strip())
        except SupportThreadClosedError as exc:
            await self._send_error(str(exc), code="thread_closed")
            return
        except MessagingError as exc:
            await self._send_error(str(exc))
            return
        except Exception as exc:
            logger.exception(
                "SupportConsumer._handle_support_message: unexpected error user=%s: %s",
                self.user.pk, exc,
            )
            await self._send_error("An unexpected error occurred.")
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "support.message.broadcast",
                "message_id": str(msg.id),
                "thread_id": str(self.thread_id),
                "sender_id": str(self.user.pk),
                "is_agent_reply": msg.is_agent_reply,
                "is_internal_note": msg.is_internal_note,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            },
        )

    async def support_message_broadcast(self, event: dict) -> None:
        """
        Relay support message to client.
        Internal notes are only sent to agents.
        """
        if event.get("is_internal_note") and not self.is_agent:
            return
        await self.send_json(event)

    @database_sync_to_async
    def _check_thread_access(self, thread_id: Any, user_id: Any) -> bool:
        """Return True if user is agent, False if thread owner. Raise on no access."""
        from .models import SupportThread
        try:
            thread = SupportThread.objects.get(pk=thread_id)
        except SupportThread.DoesNotExist:
            raise SupportThreadNotFoundError(
                f"SupportThread pk={thread_id!r} does not exist."
            )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        if user.is_staff:
            return True
        if thread.user_id == user_id:
            return False
        raise PermissionError(
            f"User pk={user_id!r} has no access to SupportThread {thread_id}."
        )

    @database_sync_to_async
    def _post_reply(self, content: str):
        from . import services
        return services.reply_to_support_thread(
            thread_id=self.thread_id,
            sender_id=self.user.pk,
            content=content,
        )

    async def _send_error(self, detail: str, *, code: str = "error") -> None:
        try:
            await self.send_json({"type": "error", "code": code, "detail": detail})
        except Exception as exc:
            logger.error("SupportConsumer._send_error: failed: %s", exc)
