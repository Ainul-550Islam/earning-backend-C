"""
Migration 0004 — All remaining models not covered in 0003.
Covers: AnnouncementChannel, ChannelMember, ScheduledMessage, MessagePin,
        PollVote, BotConfig, BotResponse, MessagingWebhook, WebhookDelivery,
        MessageTranslation, MessageEditHistory, DisappearingMessageConfig,
        UserStory, StoryView, StoryHighlight, VoiceMessageTranscription,
        LinkPreview, MessageLinkPreview, MediaAttachment, MessageReport,
        UserDevice, ChatMention, MessageSearchIndex, NotificationRead
"""
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0003_cpa_models"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── AnnouncementChannel ───────────────────────────────────────────────
        migrations.CreateModel(
            name="AnnouncementChannel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, default="", max_length=1000)),
                ("channel_type", models.CharField(choices=[("PUBLIC","Public Channel"),("PRIVATE","Private Channel")], default="PUBLIC", max_length=10)),
                ("avatar", models.URLField(blank=True, max_length=500, null=True)),
                ("is_verified", models.BooleanField(default=False)),
                ("subscriber_count", models.PositiveIntegerField(default=0)),
                ("post_count", models.PositiveIntegerField(default=0)),
                ("last_post_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_channels", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_announcementchannel_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── ChannelMember ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ChannelMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_admin", models.BooleanField(default=False)),
                ("notification_preference", models.CharField(choices=[("ALL","All"),("MENTIONS","Mentions"),("NONE","None")], default="ALL", max_length=10)),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="messaging.announcementchannel")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="channel_memberships", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_channelmember_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("channelmember", models.UniqueConstraint(fields=["channel","user"], name="msg_cm_unique_channel_user")),

        # ── ScheduledMessage ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="ScheduledMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content", models.TextField(max_length=10000)),
                ("message_type", models.CharField(choices=[("TEXT","Text"),("IMAGE","Image"),("FILE","File"),("AUDIO","Audio"),("VIDEO","Video")], default="TEXT", max_length=10)),
                ("attachments", models.JSONField(blank=True, default=list)),
                ("scheduled_for", models.DateTimeField(db_index=True)),
                ("status", models.CharField(choices=[("PENDING","Pending"),("SENT","Sent"),("CANCELLED","Cancelled"),("FAILED","Failed")], db_index=True, default="PENDING", max_length=10)),
                ("error", models.TextField(blank=True, default="")),
                ("chat", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scheduled_messages", to="messaging.internalchat")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="my_scheduled_messages", to=settings.AUTH_USER_MODEL)),
                ("sent_message", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scheduled_origin", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_scheduledmessage_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessagePin ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessagePin",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pinned_at", models.DateTimeField(auto_now_add=True)),
                ("chat", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pinned_messages", to="messaging.internalchat")),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pins", to="messaging.chatmessage")),
                ("pinned_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pinned_messages", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagepin_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-pinned_at"], "abstract": False},
        ),
        migrations.AddConstraint("messagepin", models.UniqueConstraint(fields=["chat","message"], name="msg_mp_unique_chat_message")),

        # ── PollVote ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="PollVote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("option_id", models.CharField(max_length=50)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="poll_votes", to="messaging.chatmessage")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="poll_votes", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_pollvote_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("pollvote", models.UniqueConstraint(fields=["message","user","option_id"], name="msg_pv_unique_msg_user_opt")),

        # ── BotConfig ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="BotConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("trigger_type", models.CharField(choices=[("KEYWORD","Keyword"),("REGEX","Regex"),("ALWAYS","Always"),("NEW_USER","New User")], default="KEYWORD", max_length=10)),
                ("trigger_value", models.CharField(blank=True, default="", max_length=500)),
                ("response_template", models.TextField(max_length=4000)),
                ("is_active", models.BooleanField(default=True)),
                ("priority", models.PositiveSmallIntegerField(default=0)),
                ("delay_seconds", models.PositiveSmallIntegerField(default=0)),
                ("chat", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="bot_configs", to="messaging.internalchat")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_bots", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_botconfig_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-priority","name"], "abstract": False},
        ),

        # ── BotResponse ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="BotResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("was_successful", models.BooleanField(default=True)),
                ("error", models.TextField(blank=True, default="")),
                ("bot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="responses", to="messaging.botconfig")),
                ("sent_message", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bot_sent_response", to="messaging.chatmessage")),
                ("trigger_message", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bot_trigger_responses", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_botresponse_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessagingWebhook ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessagingWebhook",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("url", models.URLField(max_length=2000)),
                ("secret", models.CharField(max_length=256)),
                ("events", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("failure_count", models.PositiveSmallIntegerField(default=0)),
                ("last_triggered_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_webhooks", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagingwebhook_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── WebhookDelivery ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="WebhookDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_type", models.CharField(max_length=30)),
                ("payload", models.JSONField()),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True, default="")),
                ("attempt_count", models.PositiveSmallIntegerField(default=1)),
                ("is_successful", models.BooleanField(default=False)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("webhook", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="messaging.messagingwebhook")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_webhookdelivery_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessageTranslation ────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageTranslation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("target_language", models.CharField(max_length=10)),
                ("translated_content", models.TextField()),
                ("source_language", models.CharField(blank=True, default="", max_length=10)),
                ("provider", models.CharField(blank=True, default="google", max_length=50)),
                ("is_auto_detected", models.BooleanField(default=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagetranslation_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("messagetranslation", models.UniqueConstraint(fields=["message","target_language"], name="msg_mt_unique_msg_lang")),

        # ── MessageEditHistory ────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageEditHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("previous_content", models.TextField()),
                ("previous_attachments", models.JSONField(blank=True, default=list)),
                ("edit_reason", models.CharField(blank=True, default="", max_length=300)),
                ("edit_number", models.PositiveSmallIntegerField(default=1)),
                ("edited_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="message_edits", to=settings.AUTH_USER_MODEL)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="edit_history", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messageedithistory_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── DisappearingMessageConfig ─────────────────────────────────────────
        migrations.CreateModel(
            name="DisappearingMessageConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_enabled", models.BooleanField(default=False)),
                ("ttl_seconds", models.PositiveIntegerField(choices=[(3600,"1 hour"),(86400,"24 hours"),(604800,"7 days"),(2592000,"30 days"),(7776000,"90 days")], default=604800)),
                ("enabled_at", models.DateTimeField(blank=True, null=True)),
                ("chat", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="disappearing_config", to="messaging.internalchat")),
                ("enabled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="disappearing_configs_set", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_disappearingmessageconfig_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── UserStory ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="UserStory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("story_type", models.CharField(choices=[("text","Text"),("image","Image"),("video","Video")], default="text", max_length=10)),
                ("content", models.TextField(blank=True, default="", max_length=500)),
                ("media_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("thumbnail_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("background_color", models.CharField(blank=True, default="#000000", max_length=7)),
                ("font_style", models.CharField(blank=True, default="default", max_length=50)),
                ("duration_seconds", models.PositiveSmallIntegerField(default=5)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("visibility", models.CharField(choices=[("all","All"),("close","Close Friends"),("except","Except"),("selected","Selected")], default="all", max_length=10)),
                ("visibility_user_ids", models.JSONField(blank=True, default=list)),
                ("link_url", models.URLField(blank=True, max_length=500, null=True)),
                ("link_label", models.CharField(blank=True, default="", max_length=100)),
                ("location", models.CharField(blank=True, default="", max_length=200)),
                ("music_track", models.JSONField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stories", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_userstory_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── StoryView ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="StoryView",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("viewed_at", models.DateTimeField(auto_now_add=True)),
                ("reaction_emoji", models.CharField(blank=True, max_length=10, null=True)),
                ("reply_text", models.CharField(blank=True, default="", max_length=500)),
                ("story", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="views", to="messaging.userstory")),
                ("viewer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_views", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_storyview_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-viewed_at"], "abstract": False},
        ),
        migrations.AddConstraint("storyview", models.UniqueConstraint(fields=["story","viewer"], name="msg_sv_unique_story_viewer")),

        # ── StoryHighlight ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="StoryHighlight",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=50)),
                ("cover_url", models.URLField(blank=True, max_length=500, null=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="story_highlights", to=settings.AUTH_USER_MODEL)),
                ("stories", models.ManyToManyField(blank=True, related_name="highlights", to="messaging.userstory")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_storyhighlight_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["order","created_at"], "abstract": False},
        ),

        # ── VoiceMessageTranscription ─────────────────────────────────────────
        migrations.CreateModel(
            name="VoiceMessageTranscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transcribed_text", models.TextField()),
                ("language", models.CharField(blank=True, default="", max_length=10)),
                ("confidence", models.FloatField(default=0.0, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ("provider", models.CharField(blank=True, default="whisper", max_length=50)),
                ("duration_seconds", models.FloatField(default=0.0)),
                ("waveform_data", models.JSONField(blank=True, null=True)),
                ("is_processing", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True, default="")),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="transcription", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_voicemessagetranscription_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── LinkPreview ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="LinkPreview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("url", models.URLField(max_length=2000, unique=True)),
                ("title", models.CharField(blank=True, default="", max_length=500)),
                ("description", models.TextField(blank=True, default="")),
                ("image_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("favicon_url", models.URLField(blank=True, max_length=500, null=True)),
                ("site_name", models.CharField(blank=True, default="", max_length=200)),
                ("domain", models.CharField(blank=True, db_index=True, default="", max_length=200)),
                ("content_type", models.CharField(blank=True, default="website", max_length=50)),
                ("video_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("is_safe", models.BooleanField(default=True)),
                ("fetch_error", models.CharField(blank=True, default="", max_length=300)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessageLinkPreview ────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageLinkPreview",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("is_dismissed", models.BooleanField(default=False)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="link_previews", to="messaging.chatmessage")),
                ("preview", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="message_links", to="messaging.linkpreview")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagelinkpreview_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["position"], "abstract": False},
        ),
        migrations.AddConstraint("messagelinkpreview", models.UniqueConstraint(fields=["message","preview"], name="msg_mlp_unique_msg_preview")),

        # ── MediaAttachment ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="MediaAttachment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("original_filename", models.CharField(max_length=500)),
                ("file_key", models.CharField(max_length=1000, unique=True)),
                ("original_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("compressed_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("thumbnail_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("webp_url", models.URLField(blank=True, max_length=2000, null=True)),
                ("mimetype", models.CharField(max_length=100)),
                ("file_size", models.PositiveBigIntegerField(default=0)),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("duration_seconds", models.FloatField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending","Pending"),("processing","Processing"),("ready","Ready"),("failed","Failed"),("blocked","Blocked")], db_index=True, default="pending", max_length=15)),
                ("is_nsfw", models.BooleanField(default=False)),
                ("nsfw_score", models.FloatField(default=0.0)),
                ("is_virus_scanned", models.BooleanField(default=False)),
                ("is_virus_free", models.BooleanField(default=True)),
                ("processing_error", models.TextField(blank=True, default="")),
                ("blurhash", models.CharField(blank=True, default="", max_length=100)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("message", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="media_records", to="messaging.chatmessage")),
                ("uploaded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="media_attachments", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_mediaattachment_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── MessageReport ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.CharField(choices=[("spam","Spam"),("abuse","Abuse"),("harassment","Harassment"),("nsfw","NSFW"),("misinformation","Misinformation"),("other","Other")], max_length=20)),
                ("details", models.TextField(blank=True, default="", max_length=1000)),
                ("status", models.CharField(choices=[("pending","Pending"),("reviewed","Reviewed"),("resolved","Resolved"),("dismissed","Dismissed")], db_index=True, default="pending", max_length=15)),
                ("action_taken", models.CharField(blank=True, default="", max_length=200)),
                ("moderator_note", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reports", to="messaging.chatmessage")),
                ("reported_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submitted_reports", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_reports", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagereport_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("messagereport", models.UniqueConstraint(fields=["message","reported_by"], name="msg_mr2_unique_msg_reporter")),

        # ── UserDevice ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="UserDevice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device_id", models.CharField(max_length=256)),
                ("device_name", models.CharField(blank=True, default="", max_length=200)),
                ("platform", models.CharField(max_length=20)),
                ("os_version", models.CharField(blank=True, default="", max_length=50)),
                ("app_version", models.CharField(blank=True, default="", max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("location_city", models.CharField(blank=True, default="", max_length=100)),
                ("location_country", models.CharField(blank=True, default="", max_length=50)),
                ("is_trusted", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("first_login_at", models.DateTimeField(auto_now_add=True)),
                ("last_active_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("session_key", models.CharField(blank=True, max_length=128, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="registered_devices", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_userdevice_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("userdevice", models.UniqueConstraint(fields=["user","device_id"], name="msg_ud_unique_user_device")),

        # ── ChatMention ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ChatMention",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("chat", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentions", to="messaging.internalchat")),
                ("mentioned_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_mentions", to=settings.AUTH_USER_MODEL)),
                ("mentioned_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="received_mentions", to=settings.AUTH_USER_MODEL)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mention_records", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_chatmention_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("chatmention", models.UniqueConstraint(fields=["message","mentioned_user"], name="msg_cm2_unique_msg_user")),

        # ── MessageSearchIndex ────────────────────────────────────────────────
        migrations.CreateModel(
            name="MessageSearchIndex",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("search_text", models.TextField()),
                ("indexed_at", models.DateTimeField(auto_now=True)),
                ("chat", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="search_index", to="messaging.internalchat")),
                ("message", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="search_index", to="messaging.chatmessage")),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_messagesearchindex_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),

        # ── NotificationRead ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="NotificationRead",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("clicked_at", models.DateTimeField(blank=True, null=True)),
                ("broadcast", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="messaging.cpabroadcast")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_reads", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_notificationread_tenant", to="tenants.tenant")),
            ],
            options={"ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint("notificationread", models.UniqueConstraint(fields=["broadcast","user"], name="msg_nr_unique_broadcast_user")),
    ]
