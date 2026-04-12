"""
Migration 0003 — CPA platform models + new messaging models.
Adds:
  - CPANotification
  - MessageTemplate
  - CPABroadcast
  - NotificationRead
  - AffiliateConversationThread
  - MediaAttachment
  - MessageReport
  - UserDevice
  - ChatMention
  - MessageSearchIndex
  - MessageEditHistory
  - DisappearingMessageConfig
  - UserStory, StoryView, StoryHighlight
  - VoiceMessageTranscription
  - LinkPreview, MessageLinkPreview
  - New fields on InternalChat, ChatMessage, ChatParticipant
"""
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0002_adminbroadcast_tenant_chatmessage_tenant_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── New fields on InternalChat ────────────────────────────────────────
        migrations.AddField(
            model_name="internalchat",
            name="avatar",
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name="Group Avatar URL"),
        ),
        migrations.AddField(
            model_name="internalchat",
            name="description",
            field=models.CharField(blank=True, default="", max_length=500, verbose_name="Group Description"),
        ),
        migrations.AddField(
            model_name="internalchat",
            name="is_encrypted",
            field=models.BooleanField(default=False, verbose_name="End-to-End Encrypted"),
        ),
        migrations.AddField(
            model_name="internalchat",
            name="max_participants",
            field=models.PositiveIntegerField(default=256, verbose_name="Max Participants"),
        ),
        migrations.AddField(
            model_name="internalchat",
            name="notification_preference",
            field=models.CharField(choices=[("ALL", "All Notifications"), ("MENTIONS", "Mentions Only"), ("NONE", "Muted")], default="ALL", max_length=10, verbose_name="Default Notification Preference"),
        ),

        # ── New fields on ChatParticipant ─────────────────────────────────────
        migrations.AddField(
            model_name="chatparticipant",
            name="notification_preference",
            field=models.CharField(choices=[("ALL", "All Notifications"), ("MENTIONS", "Mentions Only"), ("NONE", "Muted")], default="ALL", max_length=10, verbose_name="Notification Preference"),
        ),
        migrations.AddField(
            model_name="chatparticipant",
            name="is_pinned",
            field=models.BooleanField(default=False, verbose_name="Chat Pinned"),
        ),
        migrations.AddField(
            model_name="chatparticipant",
            name="nickname",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Nickname"),
        ),

        # ── New fields on ChatMessage ─────────────────────────────────────────
        migrations.AddField(
            model_name="chatmessage",
            name="priority",
            field=models.CharField(choices=[("LOW", "Low"), ("NORMAL", "Normal"), ("HIGH", "High"), ("URGENT", "Urgent (Push)")], default="NORMAL", max_length=10, verbose_name="Priority"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="is_forwarded",
            field=models.BooleanField(default=False, verbose_name="Is Forwarded"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="forwarded_from",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="forward_instances", to="messaging.chatmessage", verbose_name="Forwarded From"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="mentions",
            field=models.JSONField(blank=True, default=list, verbose_name="Mentions"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="thread_id",
            field=models.UUIDField(blank=True, db_index=True, null=True, verbose_name="Thread ID"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="thread_reply_count",
            field=models.PositiveIntegerField(default=0, verbose_name="Thread Reply Count"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="delivery_receipts",
            field=models.JSONField(blank=True, default=dict, verbose_name="Delivery Receipts"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="read_receipts",
            field=models.JSONField(blank=True, default=dict, verbose_name="Read Receipts"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="poll_data",
            field=models.JSONField(blank=True, null=True, verbose_name="Poll Data"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="location_data",
            field=models.JSONField(blank=True, null=True, verbose_name="Location Data"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="call_log_data",
            field=models.JSONField(blank=True, null=True, verbose_name="Call Log Data"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="encrypted_content",
            field=models.BinaryField(blank=True, null=True, verbose_name="Encrypted Content"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="encryption_key_id",
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name="Encryption Key ID"),
        ),

        # ── New indexes on ChatMessage ─────────────────────────────────────────
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(fields=["thread_id"], name="msg_cm_thread_idx"),
        ),

        # ── MessageReaction ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageReaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("emoji", models.CharField(max_length=10, verbose_name="Emoji")),
                ("custom_emoji", models.CharField(blank=True, max_length=64, null=True, verbose_name="Custom Emoji Code")),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="messaging.chatmessage", verbose_name="Message")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="message_reactions", to=settings.AUTH_USER_MODEL, verbose_name="User")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagereaction_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "Message Reaction", "verbose_name_plural": "Message Reactions", "ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint(
            model_name="messagereaction",
            constraint=models.UniqueConstraint(fields=["message", "user", "emoji"], name="msg_mr_unique_message_user_emoji"),
        ),
        migrations.AddIndex(
            model_name="messagereaction",
            index=models.Index(fields=["message", "emoji"], name="msg_mr_msg_emoji_idx"),
        ),

        # ── UserPresence ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="UserPresence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("status", models.CharField(choices=[("ONLINE", "Online"), ("AWAY", "Away"), ("BUSY", "Busy"), ("OFFLINE", "Offline")], db_index=True, default="OFFLINE", max_length=10, verbose_name="Presence Status")),
                ("last_seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name="Last Seen At")),
                ("last_seen_on", models.CharField(blank=True, max_length=50, null=True, verbose_name="Last Seen On")),
                ("custom_status", models.CharField(blank=True, default="", max_length=128, verbose_name="Custom Status")),
                ("custom_status_emoji", models.CharField(blank=True, default="", max_length=10, verbose_name="Custom Status Emoji")),
                ("custom_status_expires_at", models.DateTimeField(blank=True, null=True, verbose_name="Custom Status Expires At")),
                ("is_invisible", models.BooleanField(default=False, verbose_name="Invisible Mode")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="presence", to=settings.AUTH_USER_MODEL, verbose_name="User")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_userpresence_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "User Presence", "verbose_name_plural": "User Presences", "ordering": ["-created_at"], "abstract": False},
        ),

        # ── CallSession ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="CallSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("call_type", models.CharField(choices=[("AUDIO", "Audio Call"), ("VIDEO", "Video Call")], default="AUDIO", max_length=10, verbose_name="Call Type")),
                ("status", models.CharField(choices=[("RINGING", "Ringing"), ("ONGOING", "Ongoing"), ("ENDED", "Ended"), ("MISSED", "Missed"), ("DECLINED", "Declined"), ("FAILED", "Failed"), ("NO_ANSWER", "No Answer")], db_index=True, default="RINGING", max_length=10, verbose_name="Call Status")),
                ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="Started At")),
                ("ended_at", models.DateTimeField(blank=True, null=True, verbose_name="Ended At")),
                ("duration_seconds", models.PositiveIntegerField(default=0, verbose_name="Duration (seconds)")),
                ("room_id", models.CharField(max_length=128, unique=True, verbose_name="WebRTC Room ID")),
                ("is_recorded", models.BooleanField(default=False, verbose_name="Is Recorded")),
                ("recording_url", models.URLField(blank=True, null=True, verbose_name="Recording URL")),
                ("ice_servers", models.JSONField(blank=True, default=list, verbose_name="ICE Servers")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="Metadata")),
                ("chat", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="calls", to="messaging.internalchat", verbose_name="Related Chat")),
                ("initiated_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="initiated_calls", to=settings.AUTH_USER_MODEL, verbose_name="Caller")),
                ("participants", models.ManyToManyField(blank=True, related_name="call_sessions", to=settings.AUTH_USER_MODEL, verbose_name="Participants")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_callsession_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "Call Session", "verbose_name_plural": "Call Sessions", "ordering": ["-created_at"], "abstract": False},
        ),

        # ── DeviceToken ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("token", models.CharField(max_length=512, unique=True, verbose_name="Device Token")),
                ("platform", models.CharField(choices=[("android", "Android (FCM)"), ("ios", "iOS (APNs)"), ("web", "Web (WebPush)"), ("expo", "Expo")], default="android", max_length=10, verbose_name="Platform")),
                ("device_name", models.CharField(blank=True, default="", max_length=200, verbose_name="Device Name")),
                ("app_version", models.CharField(blank=True, default="", max_length=20, verbose_name="App Version")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("last_used_at", models.DateTimeField(blank=True, null=True, verbose_name="Last Used At")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messaging_device_tokens", to=settings.AUTH_USER_MODEL, verbose_name="User")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_devicetoken_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "Device Token", "verbose_name_plural": "Device Tokens", "ordering": ["-created_at"], "abstract": False},
        ),

        # ── CPANotification ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="CPANotification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("notification_type", models.CharField(db_index=True, max_length=40, verbose_name="Notification Type")),
                ("title", models.CharField(max_length=255, verbose_name="Title")),
                ("body", models.TextField(verbose_name="Body")),
                ("priority", models.CharField(default="NORMAL", max_length=10, verbose_name="Priority")),
                ("object_type", models.CharField(blank=True, default="", max_length=50, verbose_name="Object Type")),
                ("object_id", models.CharField(blank=True, db_index=True, default="", max_length=100, verbose_name="Object ID")),
                ("action_url", models.CharField(blank=True, default="", max_length=500, verbose_name="Action URL")),
                ("action_label", models.CharField(blank=True, default="", max_length=100, verbose_name="Action Label")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Payload")),
                ("is_read", models.BooleanField(db_index=True, default=False, verbose_name="Is Read")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="Read At")),
                ("is_dismissed", models.BooleanField(default=False, verbose_name="Is Dismissed")),
                ("push_sent", models.BooleanField(default=False, verbose_name="Push Sent")),
                ("email_sent", models.BooleanField(default=False, verbose_name="Email Sent")),
                ("sms_sent", models.BooleanField(default=False, verbose_name="SMS Sent")),
                ("push_sent_at", models.DateTimeField(blank=True, null=True)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cpa_notifications", to=settings.AUTH_USER_MODEL, verbose_name="Recipient")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_cpanotification_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "CPA Notification", "verbose_name_plural": "CPA Notifications", "ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessageTemplate ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("name", models.CharField(max_length=200, verbose_name="Template Name")),
                ("category", models.CharField(default="custom", max_length=15, verbose_name="Category")),
                ("subject", models.CharField(blank=True, default="", max_length=300, verbose_name="Subject / Title")),
                ("body", models.TextField(verbose_name="Body Template")),
                ("is_active", models.BooleanField(default=True, verbose_name="Is Active")),
                ("usage_count", models.PositiveIntegerField(default=0, verbose_name="Times Used")),
                ("tags", models.JSONField(blank=True, default=list, verbose_name="Tags")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_created_templates", to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagetemplate_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "Message Template", "verbose_name_plural": "Message Templates", "ordering": ["-usage_count", "name"], "abstract": False},
        ),

        # ── CPABroadcast ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="CPABroadcast",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("title", models.CharField(max_length=300, verbose_name="Title")),
                ("body", models.TextField(verbose_name="Body")),
                ("notification_type", models.CharField(blank=True, default="system.announcement", max_length=40, verbose_name="Notification Type")),
                ("priority", models.CharField(default="NORMAL", max_length=10, verbose_name="Priority")),
                ("audience_filter", models.CharField(default="all", max_length=20, verbose_name="Audience Filter")),
                ("audience_params", models.JSONField(blank=True, default=dict, verbose_name="Audience Parameters")),
                ("send_push", models.BooleanField(default=True, verbose_name="Send Push Notification")),
                ("send_email", models.BooleanField(default=False, verbose_name="Send Email")),
                ("send_inbox", models.BooleanField(default=True, verbose_name="Create Inbox Item")),
                ("send_sms", models.BooleanField(default=False, verbose_name="Send SMS")),
                ("action_url", models.CharField(blank=True, default="", max_length=500, verbose_name="CTA URL")),
                ("action_label", models.CharField(blank=True, default="", max_length=100, verbose_name="CTA Label")),
                ("status", models.CharField(db_index=True, default="DRAFT", max_length=15, verbose_name="Status")),
                ("scheduled_at", models.DateTimeField(blank=True, null=True, verbose_name="Scheduled At")),
                ("sent_at", models.DateTimeField(blank=True, null=True, verbose_name="Sent At")),
                ("recipient_count", models.PositiveIntegerField(default=0, verbose_name="Recipients")),
                ("delivered_count", models.PositiveIntegerField(default=0, verbose_name="Delivered")),
                ("opened_count", models.PositiveIntegerField(default=0, verbose_name="Opened")),
                ("clicked_count", models.PositiveIntegerField(default=0, verbose_name="CTA Clicked")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="Error")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cpa_broadcasts", to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="broadcasts", to="messaging.messagetemplate", verbose_name="Template Used")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_cpabroadcast_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "CPA Broadcast", "verbose_name_plural": "CPA Broadcasts", "ordering": ["-created_at"], "abstract": False},
        ),

        # ── AffiliateConversationThread ───────────────────────────────────────
        migrations.CreateModel(
            name="AffiliateConversationThread",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("status", models.CharField(choices=[("active", "Active"), ("archived", "Archived")], default="active", max_length=10, verbose_name="Status")),
                ("affiliate_unread", models.PositiveIntegerField(default=0, verbose_name="Affiliate Unread")),
                ("manager_unread", models.PositiveIntegerField(default=0, verbose_name="Manager Unread")),
                ("last_message_at", models.DateTimeField(blank=True, null=True, verbose_name="Last Message At")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Manager Notes")),
                ("tags", models.JSONField(blank=True, default=list, verbose_name="Tags")),
                ("affiliate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="affiliate_threads", to=settings.AUTH_USER_MODEL, verbose_name="Affiliate")),
                ("chat", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="affiliate_thread", to="messaging.internalchat", verbose_name="Chat")),
                ("last_message_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="last_sent_in_threads", to=settings.AUTH_USER_MODEL, verbose_name="Last Message By")),
                ("manager", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="managed_threads", to=settings.AUTH_USER_MODEL, verbose_name="Account Manager")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_affiliateconversationthread_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "Affiliate Conversation Thread", "verbose_name_plural": "Affiliate Conversation Threads", "ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint(
            model_name="affiliateconversationthread",
            constraint=models.UniqueConstraint(fields=["affiliate"], name="msg_act_unique_affiliate"),
        ),

        # ── UserBlock ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="UserBlock",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Updated At")),
                ("reason", models.CharField(blank=True, default="", max_length=200, verbose_name="Reason")),
                ("blocker", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_users", to=settings.AUTH_USER_MODEL, verbose_name="Blocker")),
                ("blocked", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_by_users", to=settings.AUTH_USER_MODEL, verbose_name="Blocked User")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_userblock_tenant", to="tenants.tenant")),
            ],
            options={"verbose_name": "User Block", "verbose_name_plural": "User Blocks", "ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint(
            model_name="userblock",
            constraint=models.UniqueConstraint(fields=["blocker", "blocked"], name="msg_ub_unique_blocker_blocked"),
        ),
    ]
