"""
Management command: export_data_gdpr
GDPR-compliant data export for a user.
Usage: python manage.py export_data_gdpr --user-id 123 --output /tmp/export.json
"""
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Export all messaging data for a user (GDPR Article 20 — Right to Data Portability)."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--output", type=str, default=None,
                            help="Output file path (default: stdout)")
        parser.add_argument("--format", choices=["json", "csv"], default="json")

    def handle(self, *args, **options):
        User = get_user_model()
        user_id = options["user_id"]

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User {user_id} not found."))
            return

        self.stderr.write(f"Exporting data for user: {user.username} (id={user_id})")

        from api.messaging.models import (
            ChatMessage, ChatParticipant, UserInbox, SupportThread,
            SupportMessage, MessageReaction, UserPresence, CallSession,
            UserBlock, DeviceToken, CPANotification, AffiliateConversationThread,
            UserStory, StoryView,
        )

        data = {
            "user": {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "date_joined": user.date_joined.isoformat(),
            },
            "chats_participated": [],
            "messages_sent": [],
            "support_threads": [],
            "inbox_items": [],
            "reactions": [],
            "blocked_users": [],
            "device_tokens": [],
            "cpa_notifications": [],
            "stories": [],
            "call_history": [],
        }

        # Chat participations
        for cp in ChatParticipant.objects.filter(user_id=user_id).select_related("chat"):
            data["chats_participated"].append({
                "chat_id": str(cp.chat_id),
                "chat_name": cp.chat.name,
                "role": cp.role,
                "joined_at": cp.joined_at.isoformat(),
                "left_at": cp.left_at.isoformat() if cp.left_at else None,
            })

        # Messages sent
        for msg in ChatMessage.objects.filter(sender_id=user_id).only(
            "id", "chat_id", "content", "message_type", "created_at", "status"
        ):
            data["messages_sent"].append({
                "message_id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "content": msg.content if not msg.is_deleted else "[deleted]",
                "message_type": msg.message_type,
                "created_at": msg.created_at.isoformat(),
            })

        # Reactions
        for reaction in MessageReaction.objects.filter(user_id=user_id).select_related("message"):
            data["reactions"].append({
                "message_id": str(reaction.message_id),
                "chat_id": str(reaction.message.chat_id),
                "emoji": reaction.emoji,
                "custom_emoji": reaction.custom_emoji,
                "created_at": reaction.created_at.isoformat(),
            })

        # Support threads
        for thread in SupportThread.objects.filter(user_id=user_id):
            thread_data = {
                "thread_id": str(thread.id),
                "subject": thread.subject,
                "status": thread.status,
                "created_at": thread.created_at.isoformat(),
                "messages": [],
            }
            for sm in SupportMessage.objects.filter(thread=thread).order_by("created_at"):
                thread_data["messages"].append({
                    "content": sm.content,
                    "is_agent": sm.is_agent_reply,
                    "created_at": sm.created_at.isoformat(),
                })
            data["support_threads"].append(thread_data)

        # Inbox items
        for item in UserInbox.objects.filter(user_id=user_id).only(
            "id", "item_type", "title", "is_read", "created_at"
        ):
            data["inbox_items"].append({
                "id": str(item.id),
                "type": item.item_type,
                "title": item.title,
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat(),
            })

        # Blocked users (users this account has blocked - UserBlock.blocker's
        # own related_name is literally "blocked_users", matching this key)
        for block in UserBlock.objects.filter(blocker_id=user_id).select_related("blocked"):
            data["blocked_users"].append({
                "blocked_user_id": str(block.blocked_id),
                "blocked_username": block.blocked.username,
                "reason": block.reason,
                "created_at": block.created_at.isoformat(),
            })

        # Device tokens
        for token in DeviceToken.objects.filter(user_id=user_id):
            data["device_tokens"].append({
                "id": str(token.id),
                "platform": token.platform,
                "device_name": token.device_name,
                "token": token.token,
                "is_active": token.is_active,
                "created_at": token.created_at.isoformat(),
                "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
            })

        # CPA notifications
        for notif in CPANotification.objects.filter(recipient_id=user_id).only(
            "id", "notification_type", "title", "is_read", "created_at"
        ):
            data["cpa_notifications"].append({
                "id": str(notif.id),
                "type": notif.notification_type,
                "title": notif.title,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat(),
            })

        # Stories
        for story in UserStory.objects.filter(user_id=user_id):
            data["stories"].append({
                "id": str(story.id),
                "type": story.story_type,
                "content": story.content,
                "view_count": story.view_count,
                "created_at": story.created_at.isoformat(),
            })

        # Call history
        for call in CallSession.objects.filter(participants__pk=user_id):
            data["call_history"].append({
                "call_id": str(call.id),
                "type": call.call_type,
                "status": call.status,
                "duration_seconds": call.duration_seconds,
                "created_at": call.created_at.isoformat(),
            })

        output = json.dumps(data, indent=2, ensure_ascii=False)

        # Part 21 (world-system audit): record that this export happened -
        # a GDPR Article 20 export is exactly the kind of event a
        # compliance audit trail exists to answer "did this happen, when,
        # for whom" about. tenant_id comes from the user's own
        # participant rows since a GDPR export command takes --user-id,
        # not a tenant - falls back to None (no ChatParticipant found)
        # rather than raising, since the export itself has already
        # succeeded by this point and shouldn't be blocked by this.
        from api.messaging.models import ChatParticipant
        from api.messaging.choices import AuditAction
        from messaging import services as messaging_services
        tenant_id = (
            ChatParticipant.objects.filter(user_id=user_id)
            .values_list("tenant_id", flat=True).first()
        )
        messaging_services.log_audit_event(
            actor_id=user_id, action=AuditAction.DATA_EXPORTED,
            target_type="User", target_id=user_id, tenant_id=tenant_id,
            metadata={"format": options["format"], "message_count": len(data["messages_sent"])},
        )

        if options["output"]:
            with open(options["output"], "w") as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(
                f"Exported to: {options['output']} "
                f"({len(data['messages_sent'])} messages, "
                f"{len(data['support_threads'])} threads)"
            ))
        else:
            self.stdout.write(output)