"""
Messaging Exceptions — Complete domain exception hierarchy.
Every exception maps to a specific error code for API responses.
"""
from __future__ import annotations


class MessagingError(Exception):
    """Base exception for all messaging errors."""
    code = "messaging_error"
    http_status = 400

    def __init__(self, message: str = "", code: str = None, http_status: int = None):
        super().__init__(message)
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status

    def to_dict(self) -> dict:
        return {"error_type": type(self).__name__, "code": self.code, "detail": str(self)}


# ── Chat Exceptions ───────────────────────────────────────────────────────────

class ChatNotFoundError(MessagingError):
    code = "chat_not_found"
    http_status = 404


class ChatAccessDeniedError(MessagingError):
    code = "chat_access_denied"
    http_status = 403


class ChatArchivedError(MessagingError):
    code = "chat_archived"
    http_status = 400


class ChatDeletedError(MessagingError):
    code = "chat_deleted"
    http_status = 400


class ChatFullError(MessagingError):
    """Chat has reached max_participants limit."""
    code = "chat_full"
    http_status = 400


class AlreadyParticipantError(MessagingError):
    code = "already_participant"
    http_status = 400


class NotParticipantError(MessagingError):
    code = "not_participant"
    http_status = 403


# ── Message Exceptions ────────────────────────────────────────────────────────

class MessageNotFoundError(MessagingError):
    code = "message_not_found"
    http_status = 404


class MessageDeletedError(MessagingError):
    code = "message_deleted"
    http_status = 400


class MessageTooLongError(MessagingError):
    code = "message_too_long"
    http_status = 400


class MessageEditNotAllowedError(MessagingError):
    """Can only edit own messages within edit window."""
    code = "message_edit_not_allowed"
    http_status = 403


class MessageForwardError(MessagingError):
    code = "message_forward_error"
    http_status = 400


# ── Broadcast Exceptions ──────────────────────────────────────────────────────

class BroadcastNotFoundError(MessagingError):
    code = "broadcast_not_found"
    http_status = 404


class BroadcastStateError(MessagingError):
    code = "broadcast_invalid_state"
    http_status = 400


class BroadcastSendError(MessagingError):
    code = "broadcast_send_error"
    http_status = 500


# ── Support Thread Exceptions ─────────────────────────────────────────────────

class SupportThreadNotFoundError(MessagingError):
    code = "support_thread_not_found"
    http_status = 404


class SupportThreadClosedError(MessagingError):
    code = "support_thread_closed"
    http_status = 400


class SupportThreadLimitError(MessagingError):
    code = "support_thread_limit"
    http_status = 429


# ── User Exceptions ───────────────────────────────────────────────────────────

class UserNotFoundError(MessagingError):
    code = "user_not_found"
    http_status = 404


class UserBlockedError(MessagingError):
    """Sender has been blocked by recipient."""
    code = "user_blocked"
    http_status = 403


class UserSuspendedError(MessagingError):
    """User account is suspended."""
    code = "user_suspended"
    http_status = 403


# ── Rate Limit Exceptions ─────────────────────────────────────────────────────

class RateLimitError(MessagingError):
    code = "rate_limit_exceeded"
    http_status = 429

    def __init__(self, message: str = "", retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class SpamDetectedError(MessagingError):
    code = "spam_detected"
    http_status = 400


class ToxicContentError(MessagingError):
    code = "toxic_content"
    http_status = 400


# ── Media Exceptions ──────────────────────────────────────────────────────────

class MediaUploadError(MessagingError):
    code = "media_upload_error"
    http_status = 400


class MediaNotFoundError(MessagingError):
    code = "media_not_found"
    http_status = 404


class MediaTooLargeError(MessagingError):
    code = "media_too_large"
    http_status = 413


class MediaTypeNotAllowedError(MessagingError):
    code = "media_type_not_allowed"
    http_status = 415


class MediaNSFWError(MessagingError):
    code = "media_nsfw"
    http_status = 400


class MediaVirusError(MessagingError):
    code = "media_virus_detected"
    http_status = 400


# ── Call Exceptions ───────────────────────────────────────────────────────────

class CallNotFoundError(MessagingError):
    code = "call_not_found"
    http_status = 404


class CallAlreadyActiveError(MessagingError):
    code = "call_already_active"
    http_status = 400


class CallInvalidStateError(MessagingError):
    code = "call_invalid_state"
    http_status = 400


# ── WebSocket Exceptions ──────────────────────────────────────────────────────

class WebSocketAuthError(MessagingError):
    code = "websocket_auth_failed"
    http_status = 401


class WebSocketConnectionError(MessagingError):
    code = "websocket_connection_error"
    http_status = 400


# ── Search Exceptions ─────────────────────────────────────────────────────────

class SearchError(MessagingError):
    code = "search_error"
    http_status = 400


class SearchQueryTooShortError(MessagingError):
    code = "search_query_too_short"
    http_status = 400


# ── Channel / Story Exceptions ────────────────────────────────────────────────

class ChannelNotFoundError(MessagingError):
    code = "channel_not_found"
    http_status = 404


class ChannelAccessDeniedError(MessagingError):
    code = "channel_access_denied"
    http_status = 403


class StoryNotFoundError(MessagingError):
    code = "story_not_found"
    http_status = 404


class StoryExpiredError(MessagingError):
    code = "story_expired"
    http_status = 400


# ── Bot Exceptions ────────────────────────────────────────────────────────────

class BotNotFoundError(MessagingError):
    code = "bot_not_found"
    http_status = 404


class BotConfigError(MessagingError):
    code = "bot_config_error"
    http_status = 400


# ── Webhook Exceptions ────────────────────────────────────────────────────────

class WebhookNotFoundError(MessagingError):
    code = "webhook_not_found"
    http_status = 404


class WebhookDeliveryError(MessagingError):
    code = "webhook_delivery_error"
    http_status = 500


# ── Encryption Exceptions ─────────────────────────────────────────────────────

class EncryptionError(MessagingError):
    code = "encryption_error"
    http_status = 500


class DecryptionError(MessagingError):
    code = "decryption_error"
    http_status = 400


class KeyExchangeError(MessagingError):
    code = "key_exchange_error"
    http_status = 400


# ── Permission Exceptions ─────────────────────────────────────────────────────

class PermissionDeniedError(MessagingError):
    code = "permission_denied"
    http_status = 403


class AdminOnlyError(MessagingError):
    code = "admin_only"
    http_status = 403


class OwnerOnlyError(MessagingError):
    code = "owner_only"
    http_status = 403
