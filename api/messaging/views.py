"""
Messaging Views — REST API views (non-ViewSet endpoints).
Includes media upload, search, health check, and utility endpoints.
"""
from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import (
    MessagingError, MediaUploadError, MediaTooLargeError,
    MediaTypeNotAllowedError, ChatAccessDeniedError, SearchQueryTooShortError,
)

logger = logging.getLogger(__name__)


def _err(exc: Exception, http_status: int = 400) -> Response:
    return Response(
        {"detail": str(exc), "error_type": type(exc).__name__},
        status=http_status,
    )


# ---------------------------------------------------------------------------
# MessageAttachmentUploadView  — Presigned S3 upload URL
# ---------------------------------------------------------------------------

class MessageAttachmentUploadView(APIView):
    """
    POST /messaging/upload/
    Request:  {filename, mimetype, file_size, chat_id?}
    Response: {upload_url, file_key, cdn_url, expires_in, method, headers}

    Client uploads directly to S3 using presigned PUT URL.
    After upload, client calls /messaging/upload/confirm/ to trigger processing.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        filename  = request.data.get("filename", "").strip()
        mimetype  = request.data.get("mimetype", "").strip()
        file_size = request.data.get("file_size", 0)
        chat_id   = request.data.get("chat_id")

        # Validate inputs
        if not filename:
            return Response({"detail": "filename required."}, status=400)
        if not mimetype:
            return Response({"detail": "mimetype required."}, status=400)
        try:
            file_size = int(file_size)
        except (TypeError, ValueError):
            return Response({"detail": "file_size must be an integer."}, status=400)
        if file_size <= 0:
            return Response({"detail": "file_size must be positive."}, status=400)

        try:
            from .utils.media_pipeline import generate_presigned_upload_url
            result = generate_presigned_upload_url(
                user_id=request.user.pk,
                filename=filename,
                mimetype=mimetype,
                file_size=file_size,
                chat_id=chat_id,
            )

            # Create MediaAttachment record (status=PENDING)
            from .models import MediaAttachment
            media = MediaAttachment.objects.create(
                uploaded_by=request.user,
                original_filename=filename[:500],
                file_key=result["file_key"],
                original_url=result["cdn_url"],
                mimetype=mimetype,
                file_size=file_size,
                status=MediaAttachment.STATUS_PENDING,
                tenant=getattr(request, "tenant", None),
            )
            result["media_id"] = str(media.id)
            return Response(result, status=status.HTTP_201_CREATED)

        except (MediaTooLargeError, MediaTypeNotAllowedError) as exc:
            return _err(exc, 413 if isinstance(exc, MediaTooLargeError) else 415)
        except ValueError as exc:
            return _err(MediaUploadError(str(exc)))
        except Exception as exc:
            logger.error("MessageAttachmentUploadView.post: %s", exc)
            return Response({"detail": "Upload initiation failed."}, status=500)


class UploadConfirmView(APIView):
    """
    POST /messaging/upload/confirm/
    Request:  {media_id}
    Triggers: image/video processing pipeline asynchronously.
    Response: {media_id, status, processing}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        media_id = request.data.get("media_id")
        if not media_id:
            return Response({"detail": "media_id required."}, status=400)

        from .models import MediaAttachment
        try:
            media = MediaAttachment.objects.get(pk=media_id, uploaded_by=request.user)
        except MediaAttachment.DoesNotExist:
            return Response({"detail": "Media not found."}, status=404)

        if media.status != MediaAttachment.STATUS_PENDING:
            return Response({"detail": "Already confirmed.", "status": media.status})

        # Queue processing based on mimetype
        from .tasks import process_image_task, process_video_task
        if media.is_image:
            process_image_task.delay(str(media.id))
        elif media.is_video:
            process_video_task.delay(str(media.id))
        else:
            # Documents etc — mark ready immediately
            MediaAttachment.objects.filter(pk=media.id).update(
                status=MediaAttachment.STATUS_READY
            )

        return Response({
            "media_id": str(media.id),
            "status": "processing" if (media.is_image or media.is_video) else "ready",
            "cdn_url": media.original_url,
            "thumbnail_url": media.thumbnail_url,
        })


class MediaStatusView(APIView):
    """
    GET /messaging/upload/status/?media_id=<id>
    Poll processing status of an uploaded file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        media_id = request.query_params.get("media_id")
        if not media_id:
            return Response({"detail": "media_id required."}, status=400)

        from .models import MediaAttachment
        try:
            media = MediaAttachment.objects.get(pk=media_id, uploaded_by=request.user)
        except MediaAttachment.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        return Response({
            "media_id": str(media.id),
            "status": media.status,
            "original_url": media.original_url,
            "compressed_url": media.compressed_url,
            "thumbnail_url": media.thumbnail_url,
            "webp_url": media.webp_url,
            "best_url": media.best_url,
            "is_nsfw": media.is_nsfw,
            "is_virus_free": media.is_virus_free,
            "width": media.width,
            "height": media.height,
            "duration_seconds": media.duration_seconds,
            "blurhash": media.blurhash,
        })


# ---------------------------------------------------------------------------
# MessageSearchView  — Full-text search
# ---------------------------------------------------------------------------

class MessageSearchView(APIView):
    """
    GET /messaging/search/?q=<query>&chat_id=<id>&from=<date>&to=<date>&page=1
    Full-text Elasticsearch search with DB fallback.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query       = request.query_params.get("q", "").strip()
        chat_id     = request.query_params.get("chat_id")
        sender_id   = request.query_params.get("sender_id")
        msg_type    = request.query_params.get("message_type")
        from_date   = request.query_params.get("from")
        to_date     = request.query_params.get("to")
        page        = int(request.query_params.get("page", 1))
        page_size   = min(int(request.query_params.get("page_size", 20)), 50)

        if not query:
            return Response({"detail": "q parameter required."}, status=400)
        if len(query) < 2:
            return _err(SearchQueryTooShortError("Search query must be at least 2 characters."))

        try:
            from .utils.search_engine import search_messages
            results = search_messages(
                user_id=request.user.pk,
                query=query,
                chat_id=chat_id,
                sender_id=sender_id,
                message_type=msg_type,
                from_date=from_date,
                to_date=to_date,
                tenant_id=getattr(request, "tenant_id", None),
                page=page,
                page_size=page_size,
            )
            return Response(results)
        except Exception as exc:
            logger.error("MessageSearchView.get: %s", exc)
            return Response({"detail": "Search failed."}, status=500)


class UserSearchView(APIView):
    """
    GET /messaging/users/search/?q=<query>
    Autocomplete user search for @mentions and adding chat participants.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        if len(query) < 1:
            return Response({"results": []})

        from .utils.search_engine import autocomplete_users
        results = autocomplete_users(
            query=query,
            tenant_id=getattr(request, "tenant_id", None),
            limit=10,
        )
        return Response({"results": results})


# ---------------------------------------------------------------------------
# DeliveryStatusView  — Get delivery/read receipts for a message
# ---------------------------------------------------------------------------

class DeliveryStatusView(APIView):
    """
    GET /messaging/delivery/?message_id=<id>
    Returns per-user delivery and read timestamps.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        message_id = request.query_params.get("message_id")
        if not message_id:
            return Response({"detail": "message_id required."}, status=400)

        from .utils.delivery_manager import get_delivery_status
        from .models import ChatMessage
        try:
            msg = ChatMessage.objects.get(pk=message_id)
            # Only sender can see delivery receipts
            if str(msg.sender_id) != str(request.user.pk):
                return Response({"detail": "Only the sender can view receipts."}, status=403)
            receipts = get_delivery_status(message_id)
            return Response({
                "message_id": str(message_id),
                "delivery_receipts": receipts,
                "read_receipts": msg.read_receipts or {},
                "status": msg.status,
            })
        except ChatMessage.DoesNotExist:
            return Response({"detail": "Message not found."}, status=404)


# ---------------------------------------------------------------------------
# PresenceView  — REST endpoint for presence (non-WS)
# ---------------------------------------------------------------------------

class PresenceView(APIView):
    """GET /messaging/online/?user_ids=1,2,3 — bulk presence lookup."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        ids_str = request.query_params.get("user_ids", "")
        user_ids = [i.strip() for i in ids_str.split(",") if i.strip()][:50]
        if not user_ids:
            return Response({"detail": "user_ids required."}, status=400)

        from . import services
        return Response({uid: services.get_presence(uid) for uid in user_ids})


# ---------------------------------------------------------------------------
# TranslationView  — Translate a message on demand
# ---------------------------------------------------------------------------

class TranslationView(APIView):
    """
    POST /messaging/translate/
    {message_id, target_language}
    Returns translated content (cached after first call).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        message_id      = request.data.get("message_id")
        target_language = request.data.get("target_language", "en")

        if not message_id:
            return Response({"detail": "message_id required."}, status=400)

        from .constants import SUPPORTED_TRANSLATION_LANGUAGES
        if target_language not in SUPPORTED_TRANSLATION_LANGUAGES:
            return Response({
                "detail": f"Unsupported language. Supported: {SUPPORTED_TRANSLATION_LANGUAGES}"
            }, status=400)

        try:
            from . import services
            translated = services.translate_message(
                message_id=message_id,
                target_language=target_language,
                user_id=request.user.pk,
            )
            return Response({
                "message_id": str(message_id),
                "target_language": target_language,
                "translated_content": translated,
            })
        except MessagingError as exc:
            return _err(exc)
        except Exception as exc:
            logger.error("TranslationView.post: %s", exc)
            return Response({"detail": "Translation failed."}, status=500)


# ---------------------------------------------------------------------------
# UnreadCountView  — Fast unread count
# ---------------------------------------------------------------------------

class UnreadCountView(APIView):
    """GET /messaging/unread/ — Total unread count."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .utils.delivery_manager import get_total_unread
        count = get_total_unread(request.user.pk)
        return Response({"unread_count": count, "user_id": str(request.user.pk)})


# ---------------------------------------------------------------------------
# DeviceSyncView  — Initial sync on device login
# ---------------------------------------------------------------------------

class DeviceSyncView(APIView):
    """
    POST /messaging/sync/
    Called when app opens — syncs chats, unread counts.
    {device_token_id}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        device_token_id = request.data.get("device_token_id")
        try:
            from .utils.device_sync import sync_device_on_login
            result = sync_device_on_login(
                user_id=request.user.pk,
                device_token_id=device_token_id,
            )
            return Response(result)
        except Exception as exc:
            logger.error("DeviceSyncView.post: %s", exc)
            return Response({"detail": "Sync failed."}, status=500)


# ---------------------------------------------------------------------------
# HealthCheckView  — Liveness + readiness probe
# ---------------------------------------------------------------------------

class HealthCheckView(APIView):
    """GET /messaging/health/ — Returns system health status."""
    permission_classes = []

    def get(self, request: Request) -> Response:
        checks = {}

        # DB check
        try:
            from django.db import connection
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"

        # Redis / cache check
        try:
            from django.core.cache import cache
            cache.set("health_check", "ok", 5)
            val = cache.get("health_check")
            checks["cache"] = "ok" if val == "ok" else "error"
        except Exception as exc:
            checks["cache"] = f"error: {exc}"

        # Elasticsearch check
        try:
            from .utils.search_engine import get_es_client
            es = get_es_client()
            if es and es.ping():
                checks["elasticsearch"] = "ok"
            else:
                checks["elasticsearch"] = "not configured"
        except Exception as exc:
            checks["elasticsearch"] = f"error: {exc}"

        # Celery check
        try:
            from celery import current_app
            inspector = current_app.control.inspect()
            active = inspector.active()
            checks["celery"] = "ok" if active else "no_workers"
        except Exception:
            checks["celery"] = "not configured"

        all_ok = all(v in ("ok", "not configured", "no_workers") for v in checks.values())
        return Response(
            {"status": "healthy" if all_ok else "degraded", "checks": checks},
            status=200 if all_ok else 207,
        )


# ---------------------------------------------------------------------------
# MentionsView  — Messages where user was @mentioned
# ---------------------------------------------------------------------------

class MentionsView(APIView):
    """
    GET /messaging/mentions/?unread=1
    Returns all @mention records for the current user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .models import ChatMention, ChatMessage
        unread_only = request.query_params.get("unread") == "1"
        qs = ChatMention.objects.filter(
            mentioned_user=request.user
        ).select_related("message", "chat", "mentioned_by").order_by("-created_at")[:50]

        if unread_only:
            qs = qs.filter(is_read=False)

        results = [{
            "mention_id": str(m.id),
            "chat_id": str(m.chat_id),
            "message_id": str(m.message_id),
            "mentioned_by_id": str(m.mentioned_by_id) if m.mentioned_by_id else None,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat(),
        } for m in qs]

        # Mark as read if requested
        if request.query_params.get("mark_read") == "1":
            ChatMention.objects.filter(
                mentioned_user=request.user, is_read=False
            ).update(is_read=True)

        return Response({"results": results, "count": len(results)})
