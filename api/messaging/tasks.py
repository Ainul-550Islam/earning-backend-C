"""
Messaging Celery Tasks — World-class async task queue.

Task categories:
1. Message delivery — update_delivery_status_task
2. Media processing — process_image_task, process_video_task, scan_media_task
3. Search indexing — index_message_task, bulk_index_task, delete_from_index_task
4. Broadcasts — send_broadcast_async, send_scheduled_broadcasts
5. Notifications — notify_new_chat_message, notify_support_reply, notify_call_incoming
6. Scheduled messages — send_scheduled_messages
7. Presence — cleanup_presence
8. Webhooks — dispatch_webhook_task
9. Bot — process_bot_triggers_task
10. Story — expire_stories_task, send_story_views_digest
11. Voice — process_voice_message_task
12. Link preview — fetch_link_previews_task
13. Disappearing — expire_disappearing_messages_task
14. Cleanup — cleanup_old_inbox_items, cleanup_old_edit_history, etc.
15. Moderation — review_reported_messages_task, scan_for_spam_task
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)

DEFAULT_RETRY_DELAY: int = 60
DEFAULT_MAX_RETRIES: int = 3
BACKOFF_MULTIPLIER: int  = 2


# ── 1. Message Delivery ───────────────────────────────────────────────────────

@shared_task(name="messaging.update_delivery_status")
def update_delivery_status_task(message_id: str, user_id: str, status: str, timestamp: str) -> dict:
    """
    Update delivery/read status in DB. DB-agnostic (PostgreSQL + MySQL + SQLite).
    """
    from .models import ChatMessage
    try:
        msg = ChatMessage.objects.filter(pk=message_id).first()
        if not msg:
            return {"ok": False, "error": "message_not_found"}
        if status == "DELIVERED":
            receipts = dict(msg.delivery_receipts or {})
            receipts[str(user_id)] = timestamp
            ChatMessage.objects.filter(pk=message_id).update(delivery_receipts=receipts)
        elif status == "READ":
            receipts = dict(msg.read_receipts or {})
            receipts[str(user_id)] = timestamp
            ChatMessage.objects.filter(pk=message_id).update(read_receipts=receipts)
        return {"ok": True, "message_id": message_id, "status": status}
    except Exception as exc:
        logger.error("update_delivery_status_task: %s", exc)
        return {"ok": False, "error": str(exc)}


@shared_task(
    bind=True, max_retries=3, default_retry_delay=30,
    name="messaging.process_image",
)
def process_image_task(self, media_id: str) -> dict:
    """
    Process uploaded image: compress, generate thumbnail, WebP, scan NSFW.
    Called after client confirms upload to S3.
    """
    from .models import MediaAttachment
    try:
        media = MediaAttachment.objects.get(pk=media_id)
    except MediaAttachment.DoesNotExist:
        return {"ok": False, "error": "not_found"}

    MediaAttachment.objects.filter(pk=media_id).update(
        status=MediaAttachment.STATUS_PROCESSING
    )
    try:
        from .utils.media_pipeline import process_image_after_upload, detect_nsfw
        results = process_image_after_upload(media.file_key, media.mimetype)

        # NSFW check
        nsfw_result = detect_nsfw(media.original_url or "")

        MediaAttachment.objects.filter(pk=media_id).update(
            status=MediaAttachment.STATUS_BLOCKED if nsfw_result.get("is_nsfw") else MediaAttachment.STATUS_READY,
            compressed_url=results.get("compressed"),
            thumbnail_url=results.get("thumbnail"),
            webp_url=results.get("webp"),
            is_nsfw=nsfw_result.get("is_nsfw", False),
            nsfw_score=nsfw_result.get("toxic_score", 0.0),
        )

        if nsfw_result.get("is_nsfw"):
            logger.warning("process_image_task: NSFW detected media=%s", media_id)

        return {"ok": True, "media_id": media_id, "nsfw": nsfw_result.get("is_nsfw")}
    except Exception as exc:
        MediaAttachment.objects.filter(pk=media_id).update(
            status=MediaAttachment.STATUS_FAILED,
            processing_error=str(exc)[:500],
        )
        raise self.retry(exc=exc, countdown=30)


@shared_task(
    bind=True, max_retries=2, default_retry_delay=60,
    name="messaging.process_video",
)
def process_video_task(self, media_id: str) -> dict:
    """Generate video thumbnail + virus scan."""
    from .models import MediaAttachment
    try:
        media = MediaAttachment.objects.get(pk=media_id)
    except MediaAttachment.DoesNotExist:
        return {"ok": False, "error": "not_found"}

    try:
        from .utils.media_pipeline import generate_video_thumbnail, scan_file_for_viruses
        thumb_url = generate_video_thumbnail(media.file_key)
        is_clean = scan_file_for_viruses(media.file_key)

        MediaAttachment.objects.filter(pk=media_id).update(
            status=MediaAttachment.STATUS_BLOCKED if not is_clean else MediaAttachment.STATUS_READY,
            thumbnail_url=thumb_url,
            is_virus_scanned=True,
            is_virus_free=is_clean,
        )
        return {"ok": True, "media_id": media_id, "virus_free": is_clean}
    except Exception as exc:
        MediaAttachment.objects.filter(pk=media_id).update(
            status=MediaAttachment.STATUS_FAILED,
            processing_error=str(exc)[:500],
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="messaging.scan_media_virus")
def scan_media_virus_task(media_id: str) -> dict:
    """Standalone virus scan task."""
    from .models import MediaAttachment
    try:
        media = MediaAttachment.objects.get(pk=media_id)
        from .utils.media_pipeline import scan_file_for_viruses
        is_clean = scan_file_for_viruses(media.file_key)
        MediaAttachment.objects.filter(pk=media_id).update(
            is_virus_scanned=True,
            is_virus_free=is_clean,
            status=MediaAttachment.STATUS_BLOCKED if not is_clean else MediaAttachment.STATUS_READY,
        )
        return {"media_id": media_id, "clean": is_clean}
    except Exception as exc:
        logger.error("scan_media_virus_task: %s → %s", media_id, exc)
        return {"media_id": media_id, "error": str(exc)}


# ── 3. Search Indexing ────────────────────────────────────────────────────────

@shared_task(name="messaging.index_message")
def index_message_task(message_id: str) -> dict:
    """Index a single message in Elasticsearch after it's sent."""
    from .models import ChatMessage
    try:
        msg = ChatMessage.objects.get(pk=message_id)
        if msg.is_deleted:
            return {"ok": False, "reason": "deleted"}

        # Elasticsearch index
        from .utils.search_engine import index_message
        ok = index_message(
            message_id=str(msg.id),
            chat_id=str(msg.chat_id),
            sender_id=str(msg.sender_id) if msg.sender_id else "",
            content=msg.content or "",
            message_type=msg.message_type,
            created_at=msg.created_at.isoformat(),
            tenant_id=msg.tenant_id,
        )

        # Also update DB fallback search index
        from .models import MessageSearchIndex
        MessageSearchIndex.objects.update_or_create(
            message=msg,
            defaults={
                "chat": msg.chat,
                "search_text": (msg.content or "").lower().strip(),
                "tenant": msg.tenant,
            },
        )

        return {"ok": ok, "message_id": message_id}
    except Exception as exc:
        logger.error("index_message_task: msg=%s err=%s", message_id, exc)
        return {"ok": False, "error": str(exc)}


@shared_task(name="messaging.delete_from_search_index")
def delete_from_index_task(message_id: str) -> dict:
    """Remove a deleted message from search index."""
    from .utils.search_engine import delete_from_index
    from .models import MessageSearchIndex
    ok = delete_from_index(message_id)
    MessageSearchIndex.objects.filter(message_id=message_id).delete()
    return {"ok": ok, "message_id": message_id}


@shared_task(name="messaging.bulk_reindex")
def bulk_reindex_task(chat_id: str = None, days: int = 90) -> dict:
    """
    Bulk reindex messages into Elasticsearch.
    Run this when ES index is reset or new index created.
    """
    from .models import ChatMessage, MessageStatus
    from .utils.search_engine import index_message, ensure_index_exists
    from django.utils import timezone
    from datetime import timedelta

    ensure_index_exists()
    cutoff = timezone.now() - timedelta(days=days)
    qs = ChatMessage.objects.filter(
        created_at__gte=cutoff,
        status__in=[MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ],
    ).select_related("chat")

    if chat_id:
        qs = qs.filter(chat_id=chat_id)

    indexed = 0
    errors = 0
    for msg in qs.iterator(chunk_size=500):
        try:
            index_message(
                message_id=str(msg.id),
                chat_id=str(msg.chat_id),
                sender_id=str(msg.sender_id) if msg.sender_id else "",
                content=msg.content or "",
                message_type=msg.message_type,
                created_at=msg.created_at.isoformat(),
                tenant_id=msg.tenant_id,
            )
            indexed += 1
        except Exception:
            errors += 1

    logger.info("bulk_reindex_task: indexed=%d errors=%d", indexed, errors)
    return {"indexed": indexed, "errors": errors}


# ── 4. Broadcasts ─────────────────────────────────────────────────────────────

@shared_task(
    bind=True, max_retries=DEFAULT_MAX_RETRIES, default_retry_delay=DEFAULT_RETRY_DELAY,
    name="messaging.send_broadcast_async",
)
def send_broadcast_async(self, broadcast_id: Any, *, actor_id: Optional[Any] = None) -> dict:
    from . import services
    from .exceptions import BroadcastNotFoundError, BroadcastStateError, BroadcastSendError

    logger.info("send_broadcast_async: broadcast=%s", broadcast_id)
    try:
        return services.send_broadcast(broadcast_id=broadcast_id, actor_id=actor_id)
    except (BroadcastNotFoundError, BroadcastStateError) as exc:
        logger.error("send_broadcast_async: non-retryable: %s", exc)
        raise
    except BroadcastSendError as exc:
        delay = DEFAULT_RETRY_DELAY * (BACKOFF_MULTIPLIER ** self.request.retries)
        try:
            raise self.retry(exc=exc, countdown=delay)
        except MaxRetriesExceededError:
            logger.error("send_broadcast_async: max retries exceeded broadcast=%s", broadcast_id)
            raise
    except Exception as exc:
        logger.exception("send_broadcast_async: unexpected: %s", exc)
        raise


@shared_task(name="messaging.send_scheduled_broadcasts")
def send_scheduled_broadcasts() -> dict:
    from django.utils import timezone
    from .models import AdminBroadcast
    from .choices import BroadcastStatus

    due = AdminBroadcast.objects.filter(
        status=BroadcastStatus.SCHEDULED, scheduled_at__lte=timezone.now()
    )
    count = 0
    for b in due:
        send_broadcast_async.delay(str(b.id))
        count += 1
    return {"dispatched": count}


# ── 5. Notifications ──────────────────────────────────────────────────────────

@shared_task(
    bind=True, max_retries=2, default_retry_delay=30,
    name="messaging.notify_new_chat_message",
)
def notify_new_chat_message(self, message_id: Any) -> bool:
    from .models import ChatMessage, ChatParticipant
    from .utils.notifier import notify_user_new_message
    from .utils.delivery_manager import queue_message_for_offline_user, get_total_unread

    try:
        msg = ChatMessage.objects.select_related("sender", "chat").get(pk=message_id)
    except ChatMessage.DoesNotExist:
        return False

    sender_id = msg.sender_id
    sender_name = ChatMessage.objects.select_related("sender").get(pk=message_id)
    sender_name = (
        getattr(msg.sender, "get_full_name", lambda: "")() or
        getattr(msg.sender, "username", "Someone")
    ) if msg.sender else "Someone"

    preview = msg.content[:100] if msg.content else f"[{msg.message_type}]"

    participants = ChatParticipant.objects.filter(
        chat=msg.chat, left_at__isnull=True, is_muted=False,
    ).exclude(user_id=sender_id)

    for p in participants:
        user_id = p.user_id

        # Queue for offline delivery
        from .utils.notifier import send_websocket_event
        is_online = send_websocket_event(
            group_name=f"chat_{str(msg.chat_id).replace('-', '')}",
            event_type="ping_check",
            data={},
        )

        # Push notification
        notify_user_new_message(
            user_id=user_id,
            chat_id=str(msg.chat_id),
            sender_name=sender_name,
            preview=preview,
        )

        # Queue offline message
        queue_message_for_offline_user(user_id, {
            "type": "chat_message_new",
            "message_id": str(msg.id),
            "chat_id": str(msg.chat_id),
            "sender_name": sender_name,
            "preview": preview,
            "created_at": msg.created_at.isoformat(),
        })

    return True


@shared_task(
    bind=True, max_retries=2, default_retry_delay=30,
    name="messaging.notify_support_reply",
)
def notify_support_reply(self, support_message_id: Any) -> bool:
    from .models import SupportMessage
    from .utils.notifier import notify_user_support_reply
    try:
        sm = SupportMessage.objects.select_related("thread", "thread__user").get(pk=support_message_id)
    except SupportMessage.DoesNotExist:
        return False
    return notify_user_support_reply(
        user_id=sm.thread.user_id,
        thread_id=str(sm.thread_id),
        preview=sm.content[:100],
    )


@shared_task(name="messaging.notify_call_incoming")
def notify_call_incoming(call_id: str) -> bool:
    from .models import CallSession
    from .utils.notifier import notify_incoming_call
    try:
        call = CallSession.objects.select_related("initiated_by").prefetch_related("participants").get(pk=call_id)
    except CallSession.DoesNotExist:
        return False
    caller_name = (
        getattr(call.initiated_by, "get_full_name", lambda: "")() or
        getattr(call.initiated_by, "username", "Someone")
    )
    for uid in call.participants.exclude(pk=call.initiated_by_id).values_list("pk", flat=True):
        notify_incoming_call(user_id=uid, call_id=call_id, caller_name=caller_name, call_type=call.call_type)
    return True


@shared_task(name="messaging.send_push_batch")
def send_push_batch(user_ids: list, title: str, body: str, data: dict) -> dict:
    """
    Send push to many users in one task.
    Used for broadcast push notifications.
    """
    from .utils.notifier import _send_push_to_user
    sent = 0
    for uid in user_ids:
        try:
            if _send_push_to_user(user_id=uid, title=title, body=body, data=data):
                sent += 1
        except Exception:
            pass
    return {"sent": sent, "total": len(user_ids)}


# ── 6. Scheduled Messages ─────────────────────────────────────────────────────

@shared_task(name="messaging.send_scheduled_messages")
def send_scheduled_messages() -> dict:
    from django.utils import timezone
    from .models import ScheduledMessage
    from .choices import ScheduledMessageStatus
    from . import services

    due = ScheduledMessage.objects.filter(
        status=ScheduledMessageStatus.PENDING,
        scheduled_for__lte=timezone.now(),
    ).select_for_update(skip_locked=True)

    sent = 0
    failed = 0
    for sched in due:
        try:
            services.send_scheduled_message_now(scheduled_id=str(sched.id))
            sent += 1
        except Exception as exc:
            failed += 1
            logger.error("send_scheduled_messages: sched=%s err=%s", sched.id, exc)
    return {"sent": sent, "failed": failed}


# ── 7. Presence ───────────────────────────────────────────────────────────────

@shared_task(name="messaging.cleanup_presence")
def cleanup_presence() -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import UserPresence
    from .choices import PresenceStatus
    from .constants import PRESENCE_OFFLINE_AFTER_SECONDS

    cutoff = timezone.now() - timedelta(seconds=PRESENCE_OFFLINE_AFTER_SECONDS)
    updated = UserPresence.objects.filter(
        status__in=[PresenceStatus.ONLINE, PresenceStatus.AWAY],
        last_seen_at__lt=cutoff,
    ).update(status=PresenceStatus.OFFLINE)
    return {"marked_offline": updated}


# ── 8. Webhooks ───────────────────────────────────────────────────────────────

@shared_task(
    bind=True, max_retries=DEFAULT_MAX_RETRIES, default_retry_delay=30,
    name="messaging.dispatch_webhook",
)
def dispatch_webhook_task(self, event_type: str, payload: dict) -> dict:
    import json
    import requests as _req
    from django.utils import timezone
    from datetime import timedelta
    from .models import MessagingWebhook, WebhookDelivery
    from .constants import WEBHOOK_TIMEOUT_SECONDS, WEBHOOK_SIGNATURE_HEADER

    webhooks = MessagingWebhook.objects.filter(
        is_active=True, failure_count__lt=10
    ).filter(events__contains=[event_type])

    delivered = 0
    failed = 0
    for webhook in webhooks:
        body = json.dumps({"event": event_type, "data": payload, "ts": timezone.now().isoformat()})
        sig = webhook.sign_payload(body)
        delivery = WebhookDelivery(webhook=webhook, event_type=event_type, payload=payload, tenant=webhook.tenant)
        try:
            resp = _req.post(
                webhook.url,
                data=body,
                headers={"Content-Type": "application/json", WEBHOOK_SIGNATURE_HEADER: sig, "User-Agent": "MessagingSystem/2.0"},
                timeout=WEBHOOK_TIMEOUT_SECONDS,
            )
            delivery.response_status = resp.status_code
            delivery.response_body = resp.text[:500]
            delivery.is_successful = 200 <= resp.status_code < 300
            if delivery.is_successful:
                delivery.delivered_at = timezone.now()
                MessagingWebhook.objects.filter(pk=webhook.pk).update(last_triggered_at=timezone.now(), failure_count=0)
                delivered += 1
            else:
                raise Exception(f"HTTP {resp.status_code}")
        except Exception as exc:
            delivery.is_successful = False
            delivery.error = str(exc)[:500]
            MessagingWebhook.objects.filter(pk=webhook.pk).update(
                failure_count=webhook.failure_count + 1
            )
            failed += 1
        delivery.attempt_count = self.request.retries + 1
        delivery.save()

    return {"event": event_type, "delivered": delivered, "failed": failed}


# ── 9. Bot Engine ─────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="messaging.process_bot_triggers")
def process_bot_triggers_task(self, message_id: str) -> dict:
    from . import services
    try:
        responses = services.process_bot_triggers(message_id)
        return {"message_id": message_id, "bot_responses": len(responses)}
    except Exception as exc:
        logger.error("process_bot_triggers_task: msg=%s err=%s", message_id, exc)
        raise self.retry(exc=exc, countdown=5)


# ── 10. Stories ───────────────────────────────────────────────────────────────

@shared_task(name="messaging.expire_stories")
def expire_stories_task() -> dict:
    from . import services
    expired = services.expire_old_stories()
    return {"expired": expired}


@shared_task(name="messaging.send_story_views_digest")
def send_story_views_digest(user_id: Any, story_id: str) -> dict:
    from .models import UserStory, StoryView
    from .utils.notifier import _send_push_to_user
    try:
        story = UserStory.objects.get(pk=story_id)
        view_count = StoryView.objects.filter(story=story).count()
        if view_count > 0 and str(story.user_id) != str(user_id):
            _send_push_to_user(
                user_id=story.user_id,
                title=f"{view_count} people viewed your story",
                body=story.content[:50] if story.content else f"[{story.story_type}]",
                data={"type": "story_views", "story_id": story_id},
            )
        return {"story_id": story_id, "view_count": view_count}
    except Exception as exc:
        return {"error": str(exc)}


@shared_task(name="messaging.cleanup_old_stories")
def cleanup_old_stories(days: int = 7) -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import UserStory
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = UserStory.objects.filter(is_active=False, expires_at__lt=cutoff).delete()
    return {"deleted": deleted}


# ── 11. Voice ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, name="messaging.process_voice_message")
def process_voice_message_task(self, message_id: str) -> dict:
    from . import services
    try:
        result = services.process_voice_message(message_id)
        return {"message_id": message_id, "transcribed": bool(result.transcribed_text), "duration": result.duration_seconds}
    except Exception as exc:
        logger.error("process_voice_message_task: msg=%s err=%s", message_id, exc)
        try:
            raise self.retry(exc=exc, countdown=30, max_retries=2)
        except Exception:
            return {"message_id": message_id, "error": str(exc)}


# ── 12. Link Preview ──────────────────────────────────────────────────────────

@shared_task(name="messaging.fetch_link_previews")
def fetch_link_previews_task(message_id: str) -> dict:
    from . import services
    try:
        previews = services.fetch_and_save_link_previews(message_id)
        return {"message_id": message_id, "previews_saved": len(previews)}
    except Exception as exc:
        logger.error("fetch_link_previews_task: msg=%s err=%s", message_id, exc)
        return {"message_id": message_id, "error": str(exc)}


# ── 13. Disappearing Messages ─────────────────────────────────────────────────

@shared_task(name="messaging.expire_disappearing_messages")
def expire_disappearing_messages_task() -> dict:
    from . import services
    deleted = services.expire_disappearing_messages()
    return {"deleted": deleted}


# ── 14. Call Management ───────────────────────────────────────────────────────

@shared_task(name="messaging.expire_calls")
def expire_calls() -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import CallSession
    from .choices import CallStatus
    from .constants import CALL_RING_TIMEOUT_SECONDS, CALL_MAX_DURATION_SECONDS

    now = timezone.now()
    missed = CallSession.objects.filter(
        status=CallStatus.RINGING, created_at__lt=now - timedelta(seconds=CALL_RING_TIMEOUT_SECONDS)
    ).update(status=CallStatus.MISSED, ended_at=now)
    ended = CallSession.objects.filter(
        status=CallStatus.ONGOING, started_at__lt=now - timedelta(seconds=CALL_MAX_DURATION_SECONDS)
    ).update(status=CallStatus.ENDED, ended_at=now)
    return {"missed": missed, "ended": ended}


# ── 15. Cleanup Tasks ─────────────────────────────────────────────────────────

@shared_task(name="messaging.cleanup_old_inbox_items")
def cleanup_old_inbox_items(days: int = 90) -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import UserInbox
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = UserInbox.objects.filter(is_read=True, is_archived=True, created_at__lt=cutoff).delete()
    return {"deleted": deleted}


@shared_task(name="messaging.cleanup_old_edit_history")
def cleanup_old_edit_history(days: int = 365) -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import MessageEditHistory
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = MessageEditHistory.objects.filter(created_at__lt=cutoff).delete()
    return {"deleted": deleted}


@shared_task(name="messaging.cleanup_old_call_sessions")
def cleanup_old_call_sessions(days: int = 30) -> dict:
    from django.utils import timezone
    from datetime import timedelta
    from .models import CallSession
    from .choices import CallStatus
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = CallSession.objects.filter(
        status__in=[CallStatus.ENDED, CallStatus.MISSED, CallStatus.DECLINED, CallStatus.FAILED],
        created_at__lt=cutoff,
    ).delete()
    return {"deleted": deleted}


@shared_task(name="messaging.cleanup_expired_polls")
def cleanup_expired_polls() -> dict:
    from django.utils import timezone
    from .models import ChatMessage
    from .choices import MessageType
    from django.utils.dateparse import parse_datetime

    closed = 0
    for poll in ChatMessage.objects.filter(message_type=MessageType.POLL).exclude(poll_data__isnull=True):
        exp_str = (poll.poll_data or {}).get("expires_at")
        if not exp_str or (poll.poll_data or {}).get("closed"):
            continue
        exp = parse_datetime(exp_str)
        if exp and timezone.now() > exp:
            poll.poll_data["closed"] = True
            ChatMessage.objects.filter(pk=poll.pk).update(poll_data=poll.poll_data)
            closed += 1
    return {"closed": closed}


@shared_task(name="messaging.cleanup_media_attachments")
def cleanup_media_attachments(days: int = 365) -> dict:
    """Delete FAILED/BLOCKED media records older than days."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import MediaAttachment
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = MediaAttachment.objects.filter(
        status__in=[MediaAttachment.STATUS_FAILED, MediaAttachment.STATUS_BLOCKED],
        created_at__lt=cutoff,
    ).delete()
    return {"deleted": deleted}


# ── 16. Moderation ────────────────────────────────────────────────────────────

@shared_task(name="messaging.review_reported_messages")
def review_reported_messages_auto() -> dict:
    """
    Auto-review pending reports.
    Messages with many reports are auto-flagged for human review.
    """
    from django.db.models import Count
    from .models import MessageReport, ChatMessage
    from django.utils import timezone

    high_priority = (
        MessageReport.objects.filter(status=MessageReport.STATUS_PENDING)
        .values("message_id")
        .annotate(report_count=Count("id"))
        .filter(report_count__gte=3)
        .values_list("message_id", flat=True)
    )

    flagged = 0
    for mid in high_priority:
        ChatMessage.objects.filter(pk=mid).update(
            metadata={"auto_flagged": True, "flagged_at": timezone.now().isoformat()}
        )
        flagged += 1

    logger.info("review_reported_messages_auto: flagged %d messages", flagged)
    return {"auto_flagged": flagged}


@shared_task(name="messaging.scan_for_spam")
def scan_for_spam_task() -> dict:
    """
    Scan recent messages for spam patterns.
    Runs every 10 minutes.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import ChatMessage, MessageStatus
    from .utils.spam_detector import analyze_message

    cutoff = timezone.now() - timedelta(minutes=10)
    msgs = ChatMessage.objects.filter(
        created_at__gte=cutoff,
        status=MessageStatus.SENT,
        message_type="TEXT",
    ).order_by("-created_at")[:500]

    flagged = 0
    for msg in msgs:
        result = analyze_message(msg.content, user_id=msg.sender_id)
        if result["is_spam"] and result["spam_score"] >= 0.7:
            ChatMessage.objects.filter(pk=msg.pk).update(
                metadata={"spam_score": result["spam_score"], "spam_reasons": result["reasons"]}
            )
            flagged += 1

    return {"scanned": msgs.count(), "flagged": flagged}
