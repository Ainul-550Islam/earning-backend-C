"""
Messaging Constants — All magic numbers in one place.
"""

# Field length limits
MAX_CHAT_NAME_LENGTH: int = 255
MAX_MESSAGE_LENGTH: int = 10_000
MAX_BROADCAST_TITLE_LENGTH: int = 255
MAX_BROADCAST_BODY_LENGTH: int = 50_000
MAX_SUBJECT_LENGTH: int = 500
MAX_THREAD_NOTE_LENGTH: int = 5_000

# File attachment limits
MAX_ATTACHMENT_SIZE_BYTES: int = 20 * 1024 * 1024   # 20 MB
MAX_ATTACHMENTS_PER_MESSAGE: int = 10
ALLOWED_ATTACHMENT_MIMETYPES: frozenset = frozenset([
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
])

# Pagination / Query limits
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
MAX_MESSAGES_FETCH: int = 200
MAX_BROADCAST_RECIPIENTS: int = 100_000

# WebSocket
WS_MESSAGE_MAX_SIZE: int = 65_536          # 64 KB
WS_HEARTBEAT_INTERVAL: int = 30            # seconds
WS_CLOSE_TIMEOUT: int = 5                  # seconds
WS_GROUP_NAME_PREFIX: str = "chat_"
WS_SUPPORT_GROUP_PREFIX: str = "support_"

# Cache
INBOX_UNREAD_CACHE_TTL: int = 60           # seconds
CHAT_PRESENCE_CACHE_TTL: int = 120         # seconds

# Rate limiting (per user per minute)
MAX_MESSAGES_PER_MINUTE: int = 60
MAX_BROADCASTS_PER_DAY: int = 10

# Cleanup
CHAT_SOFT_DELETE_DAYS: int = 30
BROADCAST_ARCHIVE_DAYS: int = 90

# Batch processing
MAX_BATCH_BROADCAST_SIZE: int = 1_000

# Support thread
MAX_SUPPORT_THREADS_PER_USER: int = 10
