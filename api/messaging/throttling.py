"""
Messaging Throttling — Custom DRF throttle classes.

All rates are sourced from constants.py so there is one authoritative
place to change limits.

Wire up in settings.py:
    REST_FRAMEWORK = {
        "DEFAULT_THROTTLE_CLASSES": [
            "rest_framework.throttling.AnonRateThrottle",
            "rest_framework.throttling.UserRateThrottle",
        ],
        "DEFAULT_THROTTLE_RATES": {
            "anon":              "20/minute",
            "user":              "200/minute",
            "message_send":      "30/minute",
            "reaction":          "60/minute",
            "call_initiate":     "20/hour",
            "bot_request":       "100/minute",
            "support_thread":    "10/day",
            "story_create":      "20/hour",
            "media_upload":      "30/hour",
            "search":            "30/minute",
            "broadcast_send":    "5/minute",
        },
    }

Or per-viewset:
    class InternalChatViewSet(viewsets.GenericViewSet):
        throttle_classes = [MessageSendThrottle]
"""
from __future__ import annotations

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from .constants import (
    MAX_MESSAGES_PER_MINUTE,
    MAX_REACTIONS_PER_MINUTE,
    MAX_CALLS_PER_HOUR,
    MAX_BOT_REQUESTS_PER_MINUTE,
    MAX_SUPPORT_THREADS_PER_USER,
)


# ── Message send throttle ─────────────────────────────────────────────────────

class MessageSendThrottle(UserRateThrottle):
    """
    Limits authenticated users to MAX_MESSAGES_PER_MINUTE (30) message
    sends per minute across all chats.

    Applied to InternalChatViewSet.send_message().
    """
    scope = "message_send"
    THROTTLE_RATES = {
        "message_send": f"{MAX_MESSAGES_PER_MINUTE}/minute",
    }


# ── Reaction throttle ─────────────────────────────────────────────────────────

class ReactionThrottle(UserRateThrottle):
    """
    Limits reaction adds/removes to MAX_REACTIONS_PER_MINUTE (60) per minute.

    Applied to MessageReactionViewSet.add() and .remove().
    """
    scope = "reaction"
    THROTTLE_RATES = {
        "reaction": f"{MAX_REACTIONS_PER_MINUTE}/minute",
    }


# ── Call initiation throttle ──────────────────────────────────────────────────

class CallInitiateThrottle(UserRateThrottle):
    """
    Limits call initiations to MAX_CALLS_PER_HOUR (20) per hour.

    Applied to CallSessionViewSet.initiate().
    Prevents spam-calling.
    """
    scope = "call_initiate"
    THROTTLE_RATES = {
        "call_initiate": f"{MAX_CALLS_PER_HOUR}/hour",
    }


# ── Bot request throttle ──────────────────────────────────────────────────────

class BotRequestThrottle(UserRateThrottle):
    """
    Limits bot trigger processing to MAX_BOT_REQUESTS_PER_MINUTE (100) per minute.

    Applied to BotConfigViewSet.test_trigger() and process_bot_triggers_task.
    """
    scope = "bot_request"
    THROTTLE_RATES = {
        "bot_request": f"{MAX_BOT_REQUESTS_PER_MINUTE}/minute",
    }


# ── Support thread creation throttle ─────────────────────────────────────────

class SupportThreadCreateThrottle(UserRateThrottle):
    """
    Limits support thread creation to MAX_SUPPORT_THREADS_PER_USER (10) per day.

    Applied to SupportThreadViewSet.create().
    """
    scope = "support_thread"
    THROTTLE_RATES = {
        "support_thread": f"{MAX_SUPPORT_THREADS_PER_USER}/day",
    }


# ── Story creation throttle ───────────────────────────────────────────────────

class StoryCreateThrottle(UserRateThrottle):
    """
    Limits story creation to 20 per hour.

    Applied to UserStoryViewSet.create().
    """
    scope = "story_create"
    THROTTLE_RATES = {
        "story_create": "20/hour",
    }


# ── Media upload throttle ─────────────────────────────────────────────────────

class MediaUploadThrottle(UserRateThrottle):
    """
    Limits media upload presign requests to 30 per hour.

    Applied to MessageAttachmentUploadView.post().
    Prevents S3 pre-signed URL abuse.
    """
    scope = "media_upload"
    THROTTLE_RATES = {
        "media_upload": "30/hour",
    }


# ── Link preview fetch throttle ────────────────────────────────────────────────

class LinkPreviewFetchThrottle(UserRateThrottle):
    """
    Limits arbitrary-URL link preview fetches to 20 per minute.

    Applied to LinkPreviewViewSet.fetch(). This endpoint makes a real
    outbound HTTP request to a caller-supplied URL server-side (SSRF
    protections live in utils.link_preview, but that only blocks WHERE
    the server is allowed to connect - it doesn't limit HOW OFTEN, so
    without this an authenticated user could otherwise spam the server
    into making unlimited outbound requests).
    """
    scope = "link_preview_fetch"
    THROTTLE_RATES = {
        "link_preview_fetch": "20/minute",
    }


# ── Search throttle ───────────────────────────────────────────────────────────

class SearchThrottle(UserRateThrottle):
    """
    Limits full-text search to 30 requests per minute.

    Applied to MessageSearchView and MessageSearchViewSet.
    """
    scope = "search"
    THROTTLE_RATES = {
        "search": "30/minute",
    }


# ── Broadcast send throttle ───────────────────────────────────────────────────

class BroadcastSendThrottle(UserRateThrottle):
    """
    Limits broadcast sends to 5 per minute (admin only).

    Applied to AdminBroadcastViewSet.send() and BroadcastSendView.
    Prevents accidental mass-send storms.
    """
    scope = "broadcast_send"
    THROTTLE_RATES = {
        "broadcast_send": "5/minute",
    }


# ── Anonymous rate throttle ───────────────────────────────────────────────────

class StrictAnonThrottle(AnonRateThrottle):
    """
    Strict throttle for unauthenticated requests to public endpoints.

    Applied to HealthCheckView and WebSocket auth endpoints.
    """
    scope = "anon"
    THROTTLE_RATES = {
        "anon": "20/minute",
    }
