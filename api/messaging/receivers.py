"""
Messaging Signal Receivers — Connected in MessagingConfig.ready().
All receivers are defensive: never let exceptions bubble up.
Existing receivers preserved. New receivers added.
"""

from __future__ import annotations
import logging
from typing import Any
from django.dispatch import receiver
from .signals import (
    chat_message_sent,
    broadcast_sent,
    support_reply_posted,
    support_thread_status_changed,
    message_reaction_added,
    message_reaction_removed,
    call_started,
    call_ended,
    presence_changed,
    message_pinned,
    message_unpinned,
    scheduled_message_sent,
    users_mentioned,
    user_blocked,
    user_unblocked,
    message_forwarded,
    bot_response_sent,
    channel_subscribed,
    channel_unsubscribed,
    webhook_delivery_attempted,
)

logger = logging.getLogger(__name__)


# ── Existing Receivers ────────────────────────────────────────────────────────

@receiver(chat_message_sent)
def on_chat_message_sent(sender: Any, **kwargs: Any) -> None:
    """
    After a chat message is sent:
    - Enqueue push notification for each non-sender participant.
    - Dispatch outbound webhook.
    """
    message = kwargs.get("message")
    chat = kwargs.get("chat")
    if not message or not chat:
        return
    try:
        from .tasks import notify_new_chat_message
        notify_new_chat_message.delay(str(message.id))
    except Exception as exc:
        logger.error("on_chat_message_sent: failed to queue notification: %s", exc)

    try:
        from .services import dispatch_webhook_event
        dispatch_webhook_event("message.sent", {
            "message_id": str(message.id),
            "chat_id": str(chat.id),
            "sender_id": str(message.sender_id) if message.sender_id else None,
            "message_type": message.message_type,
            "preview": message.content[:50] if message.content else "",
        })
    except Exception as exc:
        logger.error("on_chat_message_sent: webhook dispatch failed: %s", exc)


@receiver(broadcast_sent)
def on_broadcast_sent(sender: Any, **kwargs: Any) -> None:
    broadcast = kwargs.get("broadcast")
    if not broadcast:
        return
    try:
        from .utils.notifier import notify_broadcast_sent
        notify_broadcast_sent(broadcast_id=str(broadcast.id), title=broadcast.title)
    except Exception as exc:
        logger.error("on_broadcast_sent: failed: %s", exc)

    try:
        from .services import dispatch_webhook_event
        dispatch_webhook_event("broadcast.sent", {
            "broadcast_id": str(broadcast.id),
            "title": broadcast.title,
            "recipient_count": broadcast.recipient_count,
        })
    except Exception as exc:
        logger.error("on_broadcast_sent: webhook failed: %s", exc)


@receiver(support_reply_posted)
def on_support_reply_posted(sender: Any, **kwargs: Any) -> None:
    support_message = kwargs.get("support_message")
    thread = kwargs.get("thread")
    if not support_message or not thread:
        return
    try:
        from .tasks import notify_support_reply
        notify_support_reply.delay(str(support_message.id))
    except Exception as exc:
        logger.error("on_support_reply_posted: failed: %s", exc)


@receiver(support_thread_status_changed)
def on_support_thread_status_changed(sender: Any, **kwargs: Any) -> None:
    thread = kwargs.get("thread")
    old_status = kwargs.get("old_status")
    new_status = kwargs.get("new_status")
    if not thread:
        return
    logger.info(
        "on_support_thread_status_changed: thread=%s %s → %s",
        getattr(thread, "id", "?"), old_status, new_status,
    )
    try:
        event = "support.closed" if new_status in ("CLOSED", "RESOLVED") else "support.opened"
        from .services import dispatch_webhook_event
        dispatch_webhook_event(event, {
            "thread_id": str(thread.id),
            "old_status": old_status,
            "new_status": new_status,
        })
    except Exception as exc:
        logger.error("on_support_thread_status_changed: webhook failed: %s", exc)


# ── New Receivers ─────────────────────────────────────────────────────────────

@receiver(message_reaction_added)
def on_message_reaction_added(sender: Any, **kwargs: Any) -> None:
    """Notify message sender about a new reaction via WebSocket."""
    reaction = kwargs.get("reaction")
    message = kwargs.get("message")
    if not reaction or not message:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(message.chat_id).replace('-', '')}",
            event_type="reaction.added",
            data={
                "message_id": str(message.id),
                "user_id": str(reaction.user_id),
                "emoji": reaction.emoji,
                "custom_emoji": reaction.custom_emoji or "",
            },
        )
    except Exception as exc:
        logger.error("on_message_reaction_added: websocket notify failed: %s", exc)


@receiver(message_reaction_removed)
def on_message_reaction_removed(sender: Any, **kwargs: Any) -> None:
    """Notify chat about a reaction being removed."""
    user_id = kwargs.get("user_id")
    message_id = kwargs.get("message_id")
    emoji = kwargs.get("emoji")
    if not all([user_id, message_id, emoji]):
        return
    try:
        from .models import ChatMessage
        message = ChatMessage.objects.only("chat_id").get(pk=message_id)
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(message.chat_id).replace('-', '')}",
            event_type="reaction.removed",
            data={"message_id": str(message_id), "user_id": str(user_id), "emoji": emoji},
        )
    except Exception as exc:
        logger.error("on_message_reaction_removed: failed: %s", exc)


@receiver(call_started)
def on_call_started(sender: Any, **kwargs: Any) -> None:
    """Push-notify all participants of the incoming call."""
    call = kwargs.get("call")
    caller = kwargs.get("caller")
    if not call:
        return
    try:
        from .tasks import notify_call_incoming
        notify_call_incoming.delay(str(call.id))
    except Exception as exc:
        logger.error("on_call_started: failed to queue call notification: %s", exc)

    try:
        from .services import dispatch_webhook_event
        dispatch_webhook_event("call.started", {
            "call_id": str(call.id),
            "call_type": call.call_type,
            "room_id": call.room_id,
            "caller_id": str(call.initiated_by_id),
        })
    except Exception as exc:
        logger.error("on_call_started: webhook failed: %s", exc)


@receiver(call_ended)
def on_call_ended(sender: Any, **kwargs: Any) -> None:
    """Log call end, dispatch webhook."""
    call = kwargs.get("call")
    duration = kwargs.get("duration_seconds", 0)
    if not call:
        return

    logger.info("on_call_ended: call=%s status=%s duration=%ds", call.id, call.status, duration)

    # Write call log message to the chat
    try:
        from .models import ChatMessage
        from .choices import MessageType
        if call.chat_id:
            ChatMessage.objects.create(
                chat_id=call.chat_id,
                message_type=MessageType.CALL_LOG,
                content=f"Call {call.status.lower()}",
                call_log_data={
                    "call_id": str(call.id),
                    "type": call.call_type,
                    "status": call.status,
                    "duration_seconds": duration,
                    "caller_id": str(call.initiated_by_id),
                },
                tenant=call.tenant,
            )
    except Exception as exc:
        logger.error("on_call_ended: failed to write call log message: %s", exc)

    try:
        from .services import dispatch_webhook_event
        dispatch_webhook_event("call.ended", {
            "call_id": str(call.id),
            "call_type": call.call_type,
            "status": call.status,
            "duration_seconds": duration,
        })
    except Exception as exc:
        logger.error("on_call_ended: webhook failed: %s", exc)


@receiver(presence_changed)
def on_presence_changed(sender: Any, **kwargs: Any) -> None:
    """Broadcast presence change to all chats the user participates in."""
    user_id = kwargs.get("user_id")
    new_status = kwargs.get("new_status")
    if not user_id or not new_status:
        return
    try:
        from .utils.notifier import send_websocket_event
        from .models import ChatParticipant
        chat_ids = list(
            ChatParticipant.objects.filter(user_id=user_id, left_at__isnull=True)
            .values_list("chat_id", flat=True)[:20]
        )
        for chat_id in chat_ids:
            send_websocket_event(
                group_name=f"chat_{str(chat_id).replace('-', '')}",
                event_type="presence.changed",
                data={"user_id": str(user_id), "status": new_status},
            )
    except Exception as exc:
        logger.error("on_presence_changed: failed: %s", exc)


@receiver(message_pinned)
def on_message_pinned(sender: Any, **kwargs: Any) -> None:
    pin = kwargs.get("pin")
    chat = kwargs.get("chat")
    if not pin or not chat:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(chat.id).replace('-', '')}",
            event_type="message.pinned",
            data={
                "message_id": str(pin.message_id),
                "chat_id": str(chat.id),
                "pinned_by": str(pin.pinned_by_id),
            },
        )
    except Exception as exc:
        logger.error("on_message_pinned: failed: %s", exc)


@receiver(message_unpinned)
def on_message_unpinned(sender: Any, **kwargs: Any) -> None:
    message_id = kwargs.get("message_id")
    chat_id = kwargs.get("chat_id")
    if not message_id or not chat_id:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(chat_id).replace('-', '')}",
            event_type="message.unpinned",
            data={"message_id": str(message_id), "chat_id": str(chat_id)},
        )
    except Exception as exc:
        logger.error("on_message_unpinned: failed: %s", exc)


@receiver(users_mentioned)
def on_users_mentioned(sender: Any, **kwargs: Any) -> None:
    """Create inbox MENTION items for mentioned users."""
    message = kwargs.get("message")
    mentioned_user_ids = kwargs.get("mentioned_user_ids", [])
    if not message or not mentioned_user_ids:
        return
    try:
        from .models import UserInbox
        from .choices import InboxItemType
        items = [
            UserInbox(
                user_id=uid,
                item_type=InboxItemType.MENTION,
                source_id=message.id,
                title="You were mentioned",
                preview=message.content[:80] if message.content else "",
                tenant=message.tenant,
            )
            for uid in mentioned_user_ids
        ]
        UserInbox.objects.bulk_create(items, ignore_conflicts=True)
    except Exception as exc:
        logger.error("on_users_mentioned: failed: %s", exc)


@receiver(user_blocked)
def on_user_blocked(sender: Any, **kwargs: Any) -> None:
    block = kwargs.get("block")
    if not block:
        return
    logger.info("on_user_blocked: %s blocked %s", block.blocker_id, block.blocked_id)


@receiver(user_unblocked)
def on_user_unblocked(sender: Any, **kwargs: Any) -> None:
    blocker_id = kwargs.get("blocker_id")
    blocked_id = kwargs.get("blocked_id")
    logger.info("on_user_unblocked: %s unblocked %s", blocker_id, blocked_id)


@receiver(scheduled_message_sent)
def on_scheduled_message_sent(sender: Any, **kwargs: Any) -> None:
    sched = kwargs.get("scheduled_msg")
    sent = kwargs.get("sent_message")
    if not sched or not sent:
        return
    logger.info("on_scheduled_message_sent: sched=%s → msg=%s", sched.id, sent.id)


@receiver(bot_response_sent)
def on_bot_response_sent(sender: Any, **kwargs: Any) -> None:
    bot_response = kwargs.get("bot_response")
    if not bot_response:
        return
    logger.debug("on_bot_response_sent: bot=%s msg=%s", bot_response.bot_id, bot_response.sent_message_id)


@receiver(channel_subscribed)
def on_channel_subscribed(sender: Any, **kwargs: Any) -> None:
    channel = kwargs.get("channel")
    user = kwargs.get("user")
    if not channel or not user:
        return
    logger.info("on_channel_subscribed: channel=%s user=%s", channel.id, user.pk)


@receiver(channel_unsubscribed)
def on_channel_unsubscribed(sender: Any, **kwargs: Any) -> None:
    channel_id = kwargs.get("channel_id")
    user_id = kwargs.get("user_id")
    logger.info("on_channel_unsubscribed: channel=%s user=%s", channel_id, user_id)


@receiver(webhook_delivery_attempted)
def on_webhook_delivery_attempted(sender: Any, **kwargs: Any) -> None:
    delivery = kwargs.get("delivery")
    if not delivery:
        return
    if not delivery.is_successful:
        logger.warning(
            "on_webhook_delivery_attempted: FAILED delivery=%s webhook=%s status=%s",
            delivery.id, delivery.webhook_id, delivery.response_status,
        )


# ── Final 6% Receivers ────────────────────────────────────────────────────────

from .signals import (
    story_created, story_viewed, story_replied,
    message_edited_with_history, disappearing_config_changed,
    link_previews_fetched, voice_message_transcribed,
)


@receiver(story_created)
def on_story_created(sender: Any, **kwargs: Any) -> None:
    """Notify contacts that a new story is available."""
    story = kwargs.get("story")
    if not story:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"presence_{story.user_id}",
            event_type="story.created",
            data={"user_id": str(story.user_id), "story_id": str(story.id), "story_type": story.story_type},
        )
    except Exception as exc:
        logger.error("on_story_created: websocket notify failed: %s", exc)


@receiver(story_viewed)
def on_story_viewed(sender: Any, **kwargs: Any) -> None:
    """Queue a batched digest notification to the story owner."""
    view = kwargs.get("view")
    story = kwargs.get("story")
    viewer_id = kwargs.get("viewer_id")
    if not all([view, story, viewer_id]):
        return
    if str(viewer_id) == str(story.user_id):
        return
    try:
        from .tasks import send_story_views_digest
        send_story_views_digest.apply_async(
            args=[str(story.user_id), str(story.id)],
            countdown=30,
        )
    except Exception as exc:
        logger.error("on_story_viewed: failed to queue digest: %s", exc)


@receiver(story_replied)
def on_story_replied(sender: Any, **kwargs: Any) -> None:
    view = kwargs.get("view")
    if not view:
        return
    logger.info("on_story_replied: story=%s viewer=%s", view.story_id, view.viewer_id)


@receiver(message_edited_with_history)
def on_message_edited_with_history(sender: Any, **kwargs: Any) -> None:
    """Broadcast the edit event to chat participants."""
    message = kwargs.get("message")
    edit_history = kwargs.get("edit_history")
    if not message:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(message.chat_id).replace('-', '')}",
            event_type="message.edited",
            data={
                "message_id": str(message.id),
                "chat_id": str(message.chat_id),
                "content": message.content,
                "edit_number": edit_history.edit_number if edit_history else 1,
            },
        )
    except Exception as exc:
        logger.error("on_message_edited_with_history: websocket failed: %s", exc)


@receiver(disappearing_config_changed)
def on_disappearing_config_changed(sender: Any, **kwargs: Any) -> None:
    config = kwargs.get("config")
    chat = kwargs.get("chat")
    if not config or not chat:
        return
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"chat_{str(chat.id).replace('-', '')}",
            event_type="chat.disappearing_changed",
            data={
                "chat_id": str(chat.id),
                "is_enabled": config.is_enabled,
                "ttl_seconds": config.ttl_seconds,
                "ttl_display": config.ttl_display,
            },
        )
    except Exception as exc:
        logger.error("on_disappearing_config_changed: failed: %s", exc)


@receiver(voice_message_transcribed)
def on_voice_message_transcribed(sender: Any, **kwargs: Any) -> None:
    """Broadcast transcription result to chat."""
    transcription = kwargs.get("transcription")
    if not transcription:
        return
    try:
        from .utils.notifier import send_websocket_event
        message = transcription.message
        send_websocket_event(
            group_name=f"chat_{str(message.chat_id).replace('-', '')}",
            event_type="voice.transcribed",
            data={
                "message_id": str(message.id),
                "text": transcription.transcribed_text,
                "language": transcription.language,
                "duration_seconds": transcription.duration_seconds,
                "waveform": transcription.waveform_data or [],
            },
        )
    except Exception as exc:
        logger.error("on_voice_message_transcribed: failed: %s", exc)


# ── Auto-trigger post-processing after message sent ───────────────────────────

from .signals import chat_message_sent as _cms

@receiver(_cms)
def on_chat_message_sent_postprocess(sender: Any, **kwargs: Any) -> None:
    """
    After a message is sent:
    - Queue link preview fetch (if text message with URLs)
    - Queue voice transcription (if audio message)
    """
    message = kwargs.get("message")
    if not message:
        return

    # Link preview
    if message.message_type == "TEXT" and message.content:
        try:
            from .tasks import fetch_link_previews_task
            fetch_link_previews_task.apply_async(
                args=[str(message.id)], countdown=2
            )
        except Exception as exc:
            logger.warning("on_chat_message_sent_postprocess: link preview queue failed: %s", exc)

    # Voice transcription
    if message.message_type == "AUDIO":
        try:
            from .tasks import process_voice_message_task
            process_voice_message_task.apply_async(
                args=[str(message.id)], countdown=1
            )
        except Exception as exc:
            logger.warning("on_chat_message_sent_postprocess: voice queue failed: %s", exc)
