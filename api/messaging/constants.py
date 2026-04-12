"""
Messaging Constants — All magic numbers in one place.
World-class update: added call, reaction, bot, webhook, translation limits.
"""

# ── Field length limits ───────────────────────────────────────────────────────
MAX_CHAT_NAME_LENGTH: int        = 255
MAX_MESSAGE_LENGTH: int          = 10_000
MAX_BROADCAST_TITLE_LENGTH: int  = 255
MAX_BROADCAST_BODY_LENGTH: int   = 50_000
MAX_SUBJECT_LENGTH: int          = 500
MAX_THREAD_NOTE_LENGTH: int      = 5_000
MAX_REACTION_CUSTOM_LENGTH: int  = 64
MAX_BOT_RESPONSE_LENGTH: int     = 4_000
MAX_CHANNEL_DESCRIPTION: int     = 1_000
MAX_POLL_QUESTION_LENGTH: int    = 500
MAX_POLL_OPTION_LENGTH: int      = 200
MAX_POLL_OPTIONS: int            = 10
MAX_SCHEDULED_MSG_BODY: int      = 10_000
MAX_SNIPPET_LENGTH: int          = 200    # preview/snippet in inbox
MAX_WEBHOOK_URL_LENGTH: int      = 2_000

# ── File attachment limits ────────────────────────────────────────────────────
MAX_ATTACHMENT_SIZE_BYTES: int    = 20 * 1024 * 1024   # 20 MB
MAX_AUDIO_SIZE_BYTES: int         = 50 * 1024 * 1024   # 50 MB
MAX_VIDEO_SIZE_BYTES: int         = 200 * 1024 * 1024  # 200 MB
MAX_ATTACHMENTS_PER_MESSAGE: int  = 10
ALLOWED_ATTACHMENT_MIMETYPES: frozenset = frozenset([
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml",
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm",
    "video/mp4", "video/webm", "video/ogg",
    "application/pdf",
    "text/plain",
    "application/zip",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
])

# ── Pagination / Query limits ─────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: int          = 20
MAX_PAGE_SIZE: int              = 100
MAX_MESSAGES_FETCH: int         = 200
MAX_BROADCAST_RECIPIENTS: int   = 100_000
MAX_BATCH_BROADCAST_SIZE: int   = 1_000   # per Celery batch
MAX_SEARCH_RESULTS: int         = 50
MAX_REACTION_PER_MESSAGE: int   = 20      # unique emoji per message
MAX_PINNED_MESSAGES: int        = 10      # per chat

# ── Rate limiting ─────────────────────────────────────────────────────────────
MAX_MESSAGES_PER_MINUTE: int    = 30
MAX_SUPPORT_THREADS_PER_USER: int = 10
MAX_REACTIONS_PER_MINUTE: int   = 60
MAX_CALLS_PER_HOUR: int         = 20
MAX_BOT_REQUESTS_PER_MINUTE: int= 100

# ── WebSocket constants ───────────────────────────────────────────────────────
WS_MESSAGE_MAX_SIZE: int        = 65_536   # 64 KB per WS frame
WS_GROUP_NAME_PREFIX: str       = "chat_"
WS_SUPPORT_GROUP_PREFIX: str    = "support_"
WS_PRESENCE_GROUP_PREFIX: str   = "presence_"
WS_CALL_GROUP_PREFIX: str       = "call_"
WS_CHANNEL_GROUP_PREFIX: str    = "channel_"
WS_TYPING_DEBOUNCE_SECONDS: int = 3

# ── Call settings ─────────────────────────────────────────────────────────────
CALL_RING_TIMEOUT_SECONDS: int  = 30
CALL_MAX_DURATION_SECONDS: int  = 3_600   # 1 hour
CALL_RECORDING_ENABLED: bool    = False   # set True to enable

# ── Presence settings ─────────────────────────────────────────────────────────
PRESENCE_OFFLINE_AFTER_SECONDS: int = 120
PRESENCE_CACHE_TTL: int             = 90

# ── Scheduled message ─────────────────────────────────────────────────────────
SCHEDULED_MSG_MAX_FUTURE_DAYS: int  = 365

# ── Bot / Auto-reply ──────────────────────────────────────────────────────────
BOT_GREETING_DELAY_SECONDS: int     = 1
BOT_RESPONSE_DELAY_SECONDS: int     = 0

# ── Translation ───────────────────────────────────────────────────────────────
TRANSLATION_CACHE_TTL: int          = 86_400   # 24 hours
SUPPORTED_TRANSLATION_LANGUAGES: tuple = (
    "en", "bn", "hi", "ar", "fr", "de", "es", "zh", "ja", "ko",
    "pt", "ru", "tr", "ur", "id", "ms",
)

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_MAX_RETRIES: int            = 3
WEBHOOK_RETRY_DELAY_SECONDS: int    = 30
WEBHOOK_TIMEOUT_SECONDS: int        = 10
WEBHOOK_SIGNATURE_HEADER: str       = "X-Messaging-Signature"

# ── Encryption ────────────────────────────────────────────────────────────────
E2E_KEY_ROTATION_DAYS: int          = 30


# ── Story constants ───────────────────────────────────────────────────────────
STORY_TTL_HOURS: int              = 24
STORY_MAX_DURATION_SECONDS: int   = 15
STORY_MAX_TEXT_LENGTH: int        = 500
STORY_MAX_PER_USER_PER_DAY: int   = 20
MAX_HIGHLIGHT_STORIES: int        = 100
MAX_STORY_HIGHLIGHTS: int         = 20

# ── Voice message constants ───────────────────────────────────────────────────
VOICE_MAX_DURATION_SECONDS: int   = 300     # 5 minutes
VOICE_WAVEFORM_SAMPLES: int       = 64      # Number of amplitude samples for UI
VOICE_TRANSCRIPTION_TIMEOUT: int  = 60      # Seconds to wait for STT

# ── Link preview constants ────────────────────────────────────────────────────
LINK_PREVIEW_TIMEOUT_SECONDS: int = 5
LINK_PREVIEW_MAX_IMAGE_SIZE: int  = 5 * 1024 * 1024  # 5 MB
LINK_PREVIEW_CACHE_DAYS: int      = 7
MAX_LINK_PREVIEWS_PER_MSG: int    = 3

# ── Disappearing message constants ────────────────────────────────────────────
DISAPPEARING_MSG_CHECK_INTERVAL: int = 300   # Run cleanup every 5 minutes
