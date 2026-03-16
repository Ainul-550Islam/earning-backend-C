"""
Messaging Exceptions — Domain-specific exception hierarchy.
"""


class MessagingError(Exception):
    """Base exception for all messaging module errors."""


class ChatNotFoundError(MessagingError):
    """Raised when an InternalChat lookup fails."""


class ChatAccessDeniedError(MessagingError):
    """Raised when a user tries to access a chat they are not part of."""


class ChatArchivedError(MessagingError):
    """Raised when attempting to send a message to an archived/deleted chat."""


class MessageNotFoundError(MessagingError):
    """Raised when a message lookup by pk fails."""


class MessageDeletedError(MessagingError):
    """Raised when attempting to interact with a deleted message."""


class BroadcastNotFoundError(MessagingError):
    """Raised when an AdminBroadcast lookup fails."""


class BroadcastStateError(MessagingError):
    """Raised when a broadcast state transition is not permitted."""


class BroadcastSendError(MessagingError):
    """Raised when broadcast delivery fails."""


class SupportThreadNotFoundError(MessagingError):
    """Raised when a SupportThread lookup fails."""


class SupportThreadClosedError(MessagingError):
    """Raised when attempting to reply to a closed/resolved thread."""


class SupportThreadLimitError(MessagingError):
    """Raised when a user exceeds the open support thread limit."""


class UserInboxNotFoundError(MessagingError):
    """Raised when a UserInbox item lookup fails."""


class UserNotFoundError(MessagingError):
    """Raised when a User lookup by pk fails."""


class AttachmentError(MessagingError):
    """Raised for invalid file attachments (size, type, count)."""


class RateLimitError(MessagingError):
    """Raised when a user exceeds messaging rate limits."""


class WebSocketAuthError(MessagingError):
    """Raised on WebSocket authentication failure."""
