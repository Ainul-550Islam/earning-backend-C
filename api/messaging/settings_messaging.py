"""
settings_messaging.py — Drop-in settings for the messaging module.

Include in your main settings.py:

    from .settings_messaging import (
        MESSAGING_INSTALLED_APPS,
        MESSAGING_REST_FRAMEWORK,
        MESSAGING_MIDDLEWARE,
        MESSAGING_CHANNEL_LAYERS,
        MESSAGING_CACHES,
    )

    INSTALLED_APPS += MESSAGING_INSTALLED_APPS

    # Merge REST_FRAMEWORK
    REST_FRAMEWORK = {**REST_FRAMEWORK, **MESSAGING_REST_FRAMEWORK}

    MIDDLEWARE += MESSAGING_MIDDLEWARE

    CHANNEL_LAYERS = MESSAGING_CHANNEL_LAYERS

    # Beat schedule
    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {**globals().get("CELERY_BEAT_SCHEDULE", {}), **MESSAGING_BEAT_SCHEDULE}
"""
from __future__ import annotations

# ── Required apps ─────────────────────────────────────────────────────────────

MESSAGING_INSTALLED_APPS: list[str] = [
    "channels",
    "django_filters",
    "drf_spectacular",
    "messaging",
]

# ── REST Framework ─────────────────────────────────────────────────────────────

MESSAGING_REST_FRAMEWORK: dict = {
    "DEFAULT_PAGINATION_CLASS": "messaging.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # ── per-scope rates used by messaging/throttling.py ──────────────────
        "anon":           "20/minute",
        "user":           "200/minute",
        "message_send":   "30/minute",   # InternalChatViewSet.send_message
        "reaction":       "60/minute",   # MessageReactionViewSet
        "call_initiate":  "20/hour",     # CallSessionViewSet
        "bot_request":    "100/minute",  # BotConfigViewSet, BotResponseViewSet
        "support_thread": "10/day",      # SupportThreadViewSet
        "story_create":   "20/hour",     # UserStoryViewSet
        "media_upload":   "30/hour",     # MediaUploadThrottle
        "search":         "30/minute",   # MessageSearchViewSet
        "link_preview_fetch": "20/minute",  # LinkPreviewViewSet.fetch — SSRF-adjacent, real outbound request
        "broadcast_send": "5/minute",    # AdminBroadcastViewSet, CPABroadcastViewSet
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "messaging.views.messaging_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# ── Middleware (append to your MIDDLEWARE list) ───────────────────────────────

MESSAGING_MIDDLEWARE: list[str] = [
    "messaging.middleware.InboxUnreadCountMiddleware",
    "messaging.middleware.MessagingRequestTimingMiddleware",
    "messaging.middleware.WebSocketRateLimitMiddleware",
]

# WebSocketRateLimitMiddleware trusts X-Forwarded-For for client-IP-based
# rate limiting ONLY when this is set to the exact number of trusted
# reverse-proxy hops between the client and Django (e.g. 1 for a single
# nginx/ALB in front of the app). Left at 0/unset, REMOTE_ADDR is used
# instead - safe by default, since REMOTE_ADDR can't be spoofed by the
# client directly, but wrong if you *do* sit behind a proxy without
# configuring this (every request would appear to come from the proxy's
# own IP, sharing one rate-limit bucket across all real clients).
MESSAGING_TRUSTED_PROXY_COUNT: int = 0

# Origin allowlist for WebSocket connections (Cross-Site WebSocket
# Hijacking protection — see messaging.routing.messaging_origin_validator
# for the full three-tier fallback this feeds into: this setting, then
# CORS_ALLOWED_ORIGINS, then ALLOWED_HOSTS). Only set this if your
# WebSocket client is served from a domain that isn't already covered
# by one of those two. Leave empty/unset to use the automatic fallback.
MESSAGING_WS_ALLOWED_ORIGINS: list[str] = []

# ── Channels (WebSocket) ──────────────────────────────────────────────────────

MESSAGING_CHANNEL_LAYERS: dict = {
    "default": {
        # Development: in-memory (no Redis needed)
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

MESSAGING_CHANNEL_LAYERS_REDIS: dict = {
    "default": {
        # Production: use Redis
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
            "capacity": 1500,
            "expiry": 10,
        },
    }
}

# ── Cache (for rate limiting, presence, link previews) ───────────────────────

MESSAGING_CACHES: dict = {
    "default": {
        # Development: local memory
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "messaging-cache",
        "TIMEOUT": 300,
    }
}

MESSAGING_CACHES_REDIS: dict = {
    "default": {
        # Production: use Redis
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "TIMEOUT": 300,
        "KEY_PREFIX": "messaging",
    }
}

# ── drf-spectacular (OpenAPI) ─────────────────────────────────────────────────

SPECTACULAR_SETTINGS: dict = {
    "TITLE": "Messaging API",
    "DESCRIPTION": (
        "World-class Django messaging system — chats, stories, calls, "
        "broadcasts, CPA notifications, and WebSocket consumers."
    ),
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
    },
    "TAGS": [
        {"name": "Chats",          "description": "Direct and group messaging"},
        {"name": "Broadcasts",     "description": "Admin and CPA broadcast management"},
        {"name": "Support",        "description": "User-to-agent support threads"},
        {"name": "Calls",          "description": "Audio and video call sessions"},
        {"name": "Presence",       "description": "Online/offline presence tracking"},
        {"name": "Stories",        "description": "Ephemeral user stories"},
        {"name": "CPA",            "description": "Affiliate CPA platform notifications"},
        {"name": "Notifications",  "description": "Inbox and read-state management"},
        {"name": "Search",         "description": "Full-text Elasticsearch search"},
        {"name": "WebSocket",      "description": "Real-time WebSocket consumers"},
        {"name": "Admin",          "description": "Platform administration endpoints"},
    ],
}

# ── Celery ────────────────────────────────────────────────────────────────────

MESSAGING_CELERY: dict = {
    "CELERY_TASK_SERIALIZER":   "json",
    "CELERY_RESULT_SERIALIZER": "json",
    "CELERY_ACCEPT_CONTENT":    ["json"],
    "CELERY_TIMEZONE":          "UTC",
    "CELERY_TASK_TRACK_STARTED": True,
    "CELERY_TASK_TIME_LIMIT":   30 * 60,
    "CELERY_TASK_SOFT_TIME_LIMIT": 25 * 60,
    "CELERYD_MAX_TASKS_PER_CHILD": 1000,
}

# ── Elasticsearch ─────────────────────────────────────────────────────────────

MESSAGING_ELASTICSEARCH: dict = {
    # Part 6 audit fix: this key was previously named ELASTICSEARCH_HOST,
    # which nothing in the codebase reads - both utils/elasticsearch_setup.py
    # and utils/search_engine.py only ever look for ELASTICSEARCH_URL.
    # Following this template as originally written would leave ES
    # permanently unconfigured with no error at all - just a silent,
    # forever fallback to DB search.
    "ELASTICSEARCH_URL":          "http://localhost:9200",
    "ELASTICSEARCH_INDEX_PREFIX": "messaging",
    "ELASTICSEARCH_TIMEOUT":       30,
    "ELASTICSEARCH_MAX_RETRIES":    3,
    "ELASTICSEARCH_RETRY_ON_TIMEOUT": True,
}

# ── Storage (S3 / media uploads) ──────────────────────────────────────────────

MESSAGING_STORAGE: dict = {
    "MESSAGING_MEDIA_BUCKET":     "your-s3-bucket",
    "MESSAGING_MEDIA_PRESIGN_TTL": 3600,
    "MESSAGING_MAX_ATTACHMENT_SIZE_MB": 100,
    "MESSAGING_ALLOWED_MEDIA_TYPES": [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/quicktime",
        "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm",
        "application/pdf",
    ],
}
