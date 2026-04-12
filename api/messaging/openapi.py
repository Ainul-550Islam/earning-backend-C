"""
Messaging OpenAPI/Swagger Configuration.
Integrates with drf-spectacular or drf-yasg.

For drf-spectacular (recommended), add to settings.py:
    INSTALLED_APPS += ['drf_spectacular']
    REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Messaging API',
        'DESCRIPTION': 'World-class messaging system with CPA platform integration.',
        'VERSION': '2.0.0',
        'SERVE_INCLUDE_SCHEMA': False,
    }

Then add to urls.py:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]
"""
from __future__ import annotations

# ── Manual OpenAPI schema extensions (for custom endpoints) ───────────────────

try:
    from drf_spectacular.utils import (
        extend_schema, extend_schema_view,
        OpenApiParameter, OpenApiExample, OpenApiResponse,
    )
    from drf_spectacular.types import OpenApiTypes
    HAS_SPECTACULAR = True
except ImportError:
    HAS_SPECTACULAR = False
    # Stub decorators when drf-spectacular is not installed
    def extend_schema(*args, **kwargs):
        def decorator(func): return func
        return decorator
    def extend_schema_view(*args, **kwargs):
        def decorator(cls): return cls
        return decorator
    class OpenApiParameter:
        QUERY = "query"
        def __init__(self, *a, **kw): pass
    class OpenApiExample:
        def __init__(self, *a, **kw): pass


# ── Schema decorators for key endpoints ───────────────────────────────────────

# Apply these to viewsets for rich Swagger documentation

CHAT_LIST_SCHEMA = extend_schema(
    summary="List user's chats",
    description=(
        "Returns all active chats the authenticated user participates in, "
        "ordered by last_message_at. Supports filtering by status and is_group."
    ),
    parameters=[
        OpenApiParameter("status", description="Filter by chat status", enum=["ACTIVE", "ARCHIVED", "DELETED"]),
        OpenApiParameter("is_group", description="Filter group vs direct chats", type=bool),
    ],
) if HAS_SPECTACULAR else lambda f: f


SEND_MESSAGE_SCHEMA = extend_schema(
    summary="Send a message",
    description="Send a text, image, audio, video, file, poll, or location message to a chat.",
    examples=[
        OpenApiExample(
            "Text message",
            value={"content": "Hello!", "message_type": "TEXT"},
        ),
        OpenApiExample(
            "Poll",
            value={
                "message_type": "POLL",
                "content": "Best framework?",
                "poll_data": {
                    "question": "Best framework?",
                    "options": [{"id": "0", "text": "Django"}, {"id": "1", "text": "FastAPI"}],
                    "multiple_choice": False,
                    "expires_at": "2024-12-31T23:59:59Z",
                },
            },
        ),
    ],
) if HAS_SPECTACULAR else lambda f: f


CPA_NOTIFICATION_SCHEMA = extend_schema(
    summary="List CPA notifications",
    description=(
        "Returns CPA platform notifications (offer approvals, conversion alerts, "
        "payout notifications, etc.) for the authenticated user. "
        "Filter by type for smart inbox tabs."
    ),
    parameters=[
        OpenApiParameter("type", description="Category filter",
                         enum=["offers", "conversions", "payments", "account", "system", "performance"]),
        OpenApiParameter("unread", description="Show only unread", type=bool),
    ],
) if HAS_SPECTACULAR else lambda f: f


BROADCAST_SEND_SCHEMA = extend_schema(
    summary="Send CPA broadcast",
    description=(
        "Send a targeted notification to a filtered audience of affiliates. "
        "Supports filtering by offer, vertical, GEO, tier, and more."
    ),
    examples=[
        OpenApiExample(
            "All affiliates announcement",
            value={
                "title": "Platform Maintenance",
                "body": "Scheduled maintenance on Sunday 2 AM UTC.",
                "audience_filter": "all",
                "notification_type": "system.maintenance",
                "priority": "HIGH",
                "send_push": True,
                "send_email": True,
            },
        ),
        OpenApiExample(
            "Offer-specific notification",
            value={
                "title": "Offer Cap Reached",
                "body": "Please pause traffic for Offer XYZ.",
                "audience_filter": "by_offer",
                "audience_params": {"offer_id": "123"},
                "notification_type": "offer.paused",
                "priority": "URGENT",
            },
        ),
    ],
) if HAS_SPECTACULAR else lambda f: f


UPLOAD_SCHEMA = extend_schema(
    summary="Get presigned upload URL",
    description=(
        "Get a presigned S3 URL for direct client upload. "
        "Client uploads directly to S3, then calls /upload/confirm/ to trigger processing."
    ),
    examples=[
        OpenApiExample(
            "Image upload",
            value={"filename": "photo.jpg", "mimetype": "image/jpeg", "file_size": 2097152},
        ),
    ],
    responses={
        201: OpenApiResponse(description="Presigned URL generated"),
        400: OpenApiResponse(description="Invalid mimetype or file size exceeded"),
        413: OpenApiResponse(description="File too large"),
        415: OpenApiResponse(description="Mimetype not allowed"),
    },
) if HAS_SPECTACULAR else lambda f: f
