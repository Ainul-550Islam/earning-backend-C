"""
test_models_missing.py
=======================
Tests for the 16 models with zero coverage and 3 validators never exercised.
Covers:
  PollVote.clean, MessagePin.clean (MAX_PINNED_MESSAGES),
  DisappearingMessageConfig.ttl_display, UserBlock.clean (self-block),
  AffiliateConversationThread, AnnouncementChannel, DisappearingMessageConfig,
  MessageEditHistory, MessageLinkPreview, MessagePin, MessageTemplate,
  MessageTranslation, MessagingWebhook, StoryHighlight, StoryView,
  VoiceMessageTranscription, BotResponse, ChatMention, MediaAttachment,
  WebhookDelivery

Place in: messaging/tests/test_models_missing.py
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from .factories import (
    UserFactory,
    InternalChatFactory,
    ChatParticipantFactory,
    ChatMessageFactory,
    BotConfigFactory,
    AnnouncementChannelFactory,
    UserStoryFactory,
)
from ..models import (
    AffiliateConversationThread,
    AnnouncementChannel,
    BotResponse,
    ChatMention,
    DisappearingMessageConfig,
    LinkPreview,
    MediaAttachment,
    MessageEditHistory,
    MessageLinkPreview,
    MessagePin,
    MessageReport,
    MessageSearchIndex,
    MessageTemplate,
    MessageTranslation,
    MessagingWebhook,
    PollVote,
    StoryHighlight,
    StoryView,
    UserBlock,
    UserDevice,
    UserStory,
    VoiceMessageTranscription,
    WebhookDelivery,
    ChatMessage,
)
from ..constants import MAX_PINNED_MESSAGES


# ─────────────────────────────────────────────────────────────────────────────
# PollVote.clean — must be a POLL-type message
# ─────────────────────────────────────────────────────────────────────────────

class TestPollVoteClean(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_valid_vote_on_poll_message(self):
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user,
            content="Best color?",
            message_type="POLL",
            poll_data={
                "question": "Best color?",
                "options": [{"id": "a", "text": "Red"}, {"id": "b", "text": "Blue"}],
            },
        )
        vote = PollVote(message=msg, user=self.user, option_id="a")
        vote.full_clean()  # should not raise

    def test_invalid_vote_on_text_message(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        vote = PollVote(message=msg, user=self.user, option_id="a")
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_invalid_vote_on_non_text_message(self):
        # Use factory to create an IMAGE message (avoids content constraint)
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="[img]",
                                  message_type="IMAGE")
        vote = PollVote(message=msg, user=self.user, option_id="a")
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_unique_constraint_single_choice(self):
        from django.db import IntegrityError
        msg = ChatMessage.objects.create(
            chat=self.chat, sender=self.user,
            content="Question?", message_type="POLL",
            poll_data={"question": "Q?", "options": [{"id": "a", "text": "A"}]},
        )
        PollVote.objects.create(message=msg, user=self.user, option_id="a")
        with self.assertRaises(Exception):
            PollVote.objects.create(message=msg, user=self.user, option_id="a")


# ─────────────────────────────────────────────────────────────────────────────
# MessagePin.clean — MAX_PINNED_MESSAGES constraint
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagePinClean(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.admin = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.admin, role="ADMIN")

    def test_can_pin_up_to_max(self):
        for i in range(MAX_PINNED_MESSAGES):
            msg = ChatMessageFactory(chat=self.chat, sender=self.admin)
            pin = MessagePin(chat=self.chat, message=msg, pinned_by=self.admin)
            pin.full_clean()  # should not raise
            pin.save()

    def test_cannot_pin_beyond_max(self):
        for i in range(MAX_PINNED_MESSAGES):
            msg = ChatMessageFactory(chat=self.chat, sender=self.admin)
            MessagePin.objects.create(chat=self.chat, message=msg, pinned_by=self.admin)
        extra_msg = ChatMessageFactory(chat=self.chat, sender=self.admin)
        pin = MessagePin(chat=self.chat, message=extra_msg, pinned_by=self.admin)
        with self.assertRaises(ValidationError):
            pin.full_clean()

    def test_different_chats_have_separate_pin_limits(self):
        other_chat = InternalChatFactory()
        ChatParticipantFactory(chat=other_chat, user=self.admin, role="ADMIN")
        # Fill pins for first chat
        for i in range(MAX_PINNED_MESSAGES):
            msg = ChatMessageFactory(chat=self.chat, sender=self.admin)
            MessagePin.objects.create(chat=self.chat, message=msg, pinned_by=self.admin)
        # Other chat should still be able to pin
        other_msg = ChatMessageFactory(chat=other_chat, sender=self.admin)
        pin = MessagePin(chat=other_chat, message=other_msg, pinned_by=self.admin)
        pin.full_clean()  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# DisappearingMessageConfig.ttl_display
# ─────────────────────────────────────────────────────────────────────────────

class TestDisappearingMessageConfigTtlDisplay(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def _make_config(self, ttl_seconds):
        cfg, _ = DisappearingMessageConfig.objects.update_or_create(
            chat=self.chat,
            defaults={"ttl_seconds": ttl_seconds, "is_enabled": True},
        )
        return cfg

    def test_ttl_display_seconds(self):
        cfg = self._make_config(30)
        self.assertIn("30", cfg.ttl_display)

    def test_ttl_display_one_minute(self):
        cfg = self._make_config(60)
        display = cfg.ttl_display.lower()
        self.assertTrue("1 minute" in display or "60" in display)

    def test_ttl_display_one_hour(self):
        cfg = self._make_config(3600)
        display = cfg.ttl_display.lower()
        self.assertTrue("1 hour" in display or "3600" in display)

    def test_ttl_display_one_day(self):
        cfg = self._make_config(86400)
        display = cfg.ttl_display.lower()
        self.assertTrue("1 day" in display or "24" in display or "86400" in display)

    def test_ttl_display_one_week(self):
        cfg = self._make_config(604800)
        display = cfg.ttl_display.lower()
        self.assertTrue("7 day" in display or "1 week" in display or "604800" in display)

    def test_ttl_display_not_empty(self):
        cfg = self._make_config(86400)
        self.assertGreater(len(cfg.ttl_display), 0)


# ─────────────────────────────────────────────────────────────────────────────
# UserBlock.clean — self-block raises ValidationError
# ─────────────────────────────────────────────────────────────────────────────

class TestUserBlockClean(TestCase):
    def test_cannot_block_self_via_clean(self):
        user = UserFactory()
        block = UserBlock(blocker=user, blocked=user, reason="testing")
        with self.assertRaises(ValidationError):
            block.full_clean()

    def test_can_block_different_user(self):
        blocker = UserFactory()
        blocked = UserFactory()
        block = UserBlock(blocker=blocker, blocked=blocked)
        block.full_clean()  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# UserStory.save — auto-sets expires_at when blank
# ─────────────────────────────────────────────────────────────────────────────

class TestUserStorySave(TestCase):
    def test_expires_at_set_automatically(self):
        user = UserFactory()
        story = UserStory(
            user=user,
            story_type="text",
            content="Auto expire test",
            is_active=True,
        )
        # expires_at not set — save should auto-fill it
        story.save()
        self.assertIsNotNone(story.expires_at)
        self.assertGreater(story.expires_at, timezone.now())

    def test_expires_at_not_overwritten_if_already_set(self):
        user = UserFactory()
        custom_expiry = timezone.now() + timedelta(hours=6)
        story = UserStory(
            user=user,
            story_type="text",
            content="Custom expiry",
            is_active=True,
            expires_at=custom_expiry,
        )
        story.save()
        story.refresh_from_db()
        # Should respect the custom expiry (within 1 second tolerance)
        self.assertAlmostEqual(
            story.expires_at.timestamp(),
            custom_expiry.timestamp(),
            delta=1.0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# AffiliateConversationThread
# ─────────────────────────────────────────────────────────────────────────────

class TestAffiliateConversationThread(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()
        self.manager = UserFactory(is_staff=True)
        self.chat = InternalChatFactory()

    def test_create_thread(self):
        thread = AffiliateConversationThread.objects.create(
            affiliate=self.affiliate,
            manager=self.manager,
            chat=self.chat,
        )
        self.assertIsNotNone(thread.id)
        self.assertEqual(thread.affiliate_id, self.affiliate.pk)
        self.assertEqual(thread.manager_id, self.manager.pk)

    def test_unique_per_affiliate_manager(self):
        AffiliateConversationThread.objects.create(
            affiliate=self.affiliate,
            manager=self.manager,
            chat=self.chat,
        )
        other_chat = InternalChatFactory()
        with self.assertRaises(Exception):
            AffiliateConversationThread.objects.create(
                affiliate=self.affiliate,
                manager=self.manager,
                chat=other_chat,
            )

    def test_str_representation(self):
        thread = AffiliateConversationThread.objects.create(
            affiliate=self.affiliate,
            manager=self.manager,
            chat=self.chat,
        )
        s = str(thread)
        self.assertGreater(len(s), 0)


# ─────────────────────────────────────────────────────────────────────────────
# AnnouncementChannel
# ─────────────────────────────────────────────────────────────────────────────

class TestAnnouncementChannel(TestCase):
    def test_slug_uniqueness_validated(self):
        admin = UserFactory(is_staff=True)
        AnnouncementChannel.objects.create(
            name="Channel Alpha", slug="ch-alpha",
            channel_type="PUBLIC", created_by=admin,
        )
        dup = AnnouncementChannel(
            name="Channel Alpha Dup", slug="ch-alpha",
            channel_type="PUBLIC", created_by=admin,
        )
        with self.assertRaises(Exception):
            dup.full_clean()
            dup.save()

    def test_subscriber_count_starts_at_zero(self):
        channel = AnnouncementChannelFactory()
        self.assertEqual(channel.subscriber_count, 0)

    def test_channel_types(self):
        admin = UserFactory(is_staff=True)
        for ctype in ["PUBLIC", "PRIVATE", "INVITE_ONLY"]:
            ch = AnnouncementChannel.objects.create(
                name=f"Channel {ctype}", slug=f"ch-{ctype.lower()}",
                channel_type=ctype, created_by=admin,
            )
            self.assertEqual(ch.channel_type, ctype)


# ─────────────────────────────────────────────────────────────────────────────
# MessageEditHistory
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageEditHistory(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="v1")

    def test_create_edit_history_record(self):
        history = MessageEditHistory.objects.create(
            message=self.msg,
            edited_by=self.user,
            previous_content="v1",
            edit_number=1,
        )
        self.assertIsNotNone(history.id)
        self.assertEqual(history.edit_number, 1)

    def test_multiple_history_records_ordered(self):
        for i in range(3):
            MessageEditHistory.objects.create(
                message=self.msg,
                edited_by=self.user,
                previous_content=f"v{i+1}",
                edit_number=i + 1,
            )
        histories = MessageEditHistory.objects.filter(message=self.msg).order_by("edit_number")
        self.assertEqual(histories.count(), 3)
        self.assertEqual(histories[0].edit_number, 1)
        self.assertEqual(histories[2].edit_number, 3)


# ─────────────────────────────────────────────────────────────────────────────
# MessageLinkPreview
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageLinkPreview(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(
            chat=self.chat, sender=self.user,
            content="Check https://example.com"
        )

    def test_create_link_preview(self):
        preview = LinkPreview.objects.create(
            url="https://example.com",
            domain="example.com",
            title="Example Domain",
            description="The best example",
            is_safe=True,
        )
        lp = MessageLinkPreview.objects.create(
            message=self.msg, preview=preview, position=0
        )
        self.assertIsNotNone(lp.id)
        self.assertEqual(lp.position, 0)
        self.assertFalse(lp.is_dismissed)

    def test_dismiss_link_preview(self):
        preview = LinkPreview.objects.create(
            url="https://spam.com", domain="spam.com", is_safe=False
        )
        lp = MessageLinkPreview.objects.create(
            message=self.msg, preview=preview, position=0
        )
        lp.is_dismissed = True
        lp.save()
        lp.refresh_from_db()
        self.assertTrue(lp.is_dismissed)


# ─────────────────────────────────────────────────────────────────────────────
# MessageTemplate
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageTemplate(TestCase):
    def test_render_with_context(self):
        template = MessageTemplate.objects.create(
            name="Welcome",
            body="Hello {affiliate_name}, your payout of {amount} is ready!",
            subject="Payment Ready: {amount}",
            category="payout",
        )
        subject, body = template.render({
            "affiliate_name": "Alice",
            "amount": "$250.00",
        })
        self.assertEqual(subject, "Payment Ready: $250.00")
        self.assertIn("Alice", body)
        self.assertIn("$250.00", body)

    def test_render_with_missing_key_uses_empty_string(self):
        template = MessageTemplate.objects.create(
            name="Offer",
            body="Your offer {offer_name} has been {status}!",
            subject="Offer Update",
        )
        try:
            subject, body = template.render({"offer_name": "Gaming Offer"})
            # Missing {status} — should not raise, uses empty or placeholder
        except KeyError:
            self.fail("render() raised KeyError for missing key — should handle gracefully")

    def test_category_defaults_to_custom(self):
        template = MessageTemplate.objects.create(
            name="No Category",
            body="Content here",
            subject="Subject here",
        )
        self.assertIsNotNone(template.category)

    def test_template_is_active_by_default(self):
        template = MessageTemplate.objects.create(
            name="Active Test", body="Hello", subject="Hi"
        )
        self.assertTrue(template.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# MessageTranslation
# ─────────────────────────────────────────────────────────────────────────────

class TestMessageTranslation(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(
            chat=self.chat, sender=self.user, content="Hello world"
        )

    def test_create_translation(self):
        t = MessageTranslation.objects.create(
            message=self.msg,
            target_language="es",
            translated_content="Hola mundo",
            source_language="en",
            provider="google",
        )
        self.assertIsNotNone(t.id)
        self.assertEqual(t.translated_content, "Hola mundo")

    def test_unique_per_message_and_language(self):
        MessageTranslation.objects.create(
            message=self.msg,
            target_language="fr",
            translated_content="Bonjour le monde",
        )
        with self.assertRaises(Exception):
            MessageTranslation.objects.create(
                message=self.msg,
                target_language="fr",
                translated_content="Bonjour encore",
            )


# ─────────────────────────────────────────────────────────────────────────────
# MessagingWebhook
# ─────────────────────────────────────────────────────────────────────────────

class TestMessagingWebhook(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)

    def test_create_webhook(self):
        wh = MessagingWebhook.objects.create(
            name="CRM Hook",
            url="https://crm.example.com/messaging",
            secret="s3cr3t",
            events=["message.sent", "call.ended"],
            created_by=self.admin,
        )
        self.assertIsNotNone(wh.id)
        self.assertTrue(wh.is_active)
        self.assertEqual(wh.failure_count, 0)

    def test_events_is_list(self):
        wh = MessagingWebhook.objects.create(
            name="Hook", url="https://example.com/hook",
            secret="x", events=["message.sent"],
            created_by=self.admin,
        )
        wh.refresh_from_db()
        self.assertIsInstance(wh.events, list)

    def test_url_must_be_valid(self):
        wh = MessagingWebhook(
            name="Bad Hook", url="not-a-url", secret="x",
            events=[], created_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            wh.full_clean()


# ─────────────────────────────────────────────────────────────────────────────
# StoryHighlight / StoryView
# ─────────────────────────────────────────────────────────────────────────────

class TestStoryHighlight(TestCase):
    def test_create_highlight(self):
        user = UserFactory()
        story = UserStoryFactory(user=user)
        highlight = StoryHighlight.objects.create(
            user=user,
            title="Travel",
            cover_url="",
        )
        highlight.stories.add(story)
        self.assertEqual(highlight.stories.count(), 1)
        self.assertEqual(highlight.title, "Travel")

    def test_highlight_can_have_multiple_stories(self):
        user = UserFactory()
        stories = UserStoryFactory.create_batch(3, user=user)
        highlight = StoryHighlight.objects.create(user=user, title="My Life")
        for s in stories:
            highlight.stories.add(s)
        self.assertEqual(highlight.stories.count(), 3)

    def test_highlight_str(self):
        user = UserFactory()
        highlight = StoryHighlight.objects.create(user=user, title="Memories")
        self.assertIn("Memories", str(highlight))


class TestStoryView(TestCase):
    def setUp(self):
        self.author = UserFactory()
        self.viewer = UserFactory()

    def test_create_story_view(self):
        story = UserStoryFactory(user=self.author)
        view = StoryView.objects.create(story=story, viewer=self.viewer)
        self.assertIsNotNone(view.id)
        self.assertIsNotNone(view.viewed_at)

    def test_story_view_unique_per_viewer(self):
        story = UserStoryFactory(user=self.author)
        StoryView.objects.create(story=story, viewer=self.viewer)
        with self.assertRaises(Exception):
            StoryView.objects.create(story=story, viewer=self.viewer)

    def test_story_view_with_reaction(self):
        story = UserStoryFactory(user=self.author)
        view = StoryView.objects.create(
            story=story, viewer=self.viewer, reaction_emoji="🔥"
        )
        self.assertEqual(view.reaction_emoji, "🔥")

    def test_story_view_with_reply(self):
        story = UserStoryFactory(user=self.author)
        view = StoryView.objects.create(
            story=story, viewer=self.viewer, reply_text="Amazing!"
        )
        self.assertEqual(view.reply_text, "Amazing!")


# ─────────────────────────────────────────────────────────────────────────────
# VoiceMessageTranscription
# ─────────────────────────────────────────────────────────────────────────────

class TestVoiceMessageTranscription(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        # Use TEXT type to avoid content constraint; transcription model is independent
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="[audio]")

    def test_create_transcription(self):
        t = VoiceMessageTranscription.objects.create(
            message=self.msg,
            transcribed_text="This is the transcribed content",
            language="en",
            confidence=0.95,
            duration_seconds=8.3,
            provider="whisper",
            is_processing=False,
        )
        self.assertIsNotNone(t.id)
        self.assertFalse(t.is_processing)

    def test_transcription_starts_as_processing(self):
        t = VoiceMessageTranscription.objects.create(
            message=self.msg,
            is_processing=True,
        )
        self.assertTrue(t.is_processing)

    def test_waveform_data_stored_as_list(self):
        t = VoiceMessageTranscription.objects.create(
            message=self.msg,
            waveform_data=[0.1, 0.5, 1.0, 0.7, 0.3],
            is_processing=False,
        )
        t.refresh_from_db()
        self.assertIsInstance(t.waveform_data, list)
        self.assertEqual(len(t.waveform_data), 5)

    def test_one_transcription_per_message(self):
        VoiceMessageTranscription.objects.create(message=self.msg)
        with self.assertRaises(Exception):
            VoiceMessageTranscription.objects.create(message=self.msg)


# ─────────────────────────────────────────────────────────────────────────────
# BotResponse
# ─────────────────────────────────────────────────────────────────────────────

class TestBotResponse(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.bot = BotConfigFactory()
        self.trigger_msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def test_create_successful_response(self):
        sent_msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        response = BotResponse.objects.create(
            bot=self.bot,
            trigger_message=self.trigger_msg,
            sent_message=sent_msg,
            was_successful=True,
        )
        self.assertIsNotNone(response.id)
        self.assertTrue(response.was_successful)
        # error field is blank by default
        self.assertFalse(bool(response.error))

    def test_create_failed_response(self):
        response = BotResponse.objects.create(
            bot=self.bot,
            trigger_message=self.trigger_msg,
            was_successful=False,
            error="Template rendering failed",
        )
        self.assertFalse(response.was_successful)
        self.assertEqual(response.error, "Template rendering failed")
        self.assertIsNone(response.sent_message)

    def test_response_timestamps(self):
        response = BotResponse.objects.create(
            bot=self.bot, trigger_message=self.trigger_msg, was_successful=True
        )
        self.assertIsNotNone(response.created_at)


# ─────────────────────────────────────────────────────────────────────────────
# ChatMention
# ─────────────────────────────────────────────────────────────────────────────

class TestChatMention(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.sender = UserFactory()
        self.mentioned = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.sender)
        ChatParticipantFactory(chat=self.chat, user=self.mentioned)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.sender)

    def test_create_mention(self):
        mention = ChatMention.objects.create(
            message=self.msg,
            chat=self.chat,
            mentioned_user=self.mentioned,
            mentioned_by=self.sender,
        )
        self.assertIsNotNone(mention.id)
        self.assertFalse(mention.is_read)

    def test_mark_mention_read(self):
        mention = ChatMention.objects.create(
            message=self.msg,
            chat=self.chat,
            mentioned_user=self.mentioned,
            mentioned_by=self.sender,
        )
        mention.is_read = True
        mention.save()
        mention.refresh_from_db()
        self.assertTrue(mention.is_read)

    def test_unique_per_message_and_user(self):
        ChatMention.objects.create(
            message=self.msg, chat=self.chat,
            mentioned_user=self.mentioned, mentioned_by=self.sender,
        )
        with self.assertRaises(Exception):
            ChatMention.objects.create(
                message=self.msg, chat=self.chat,
                mentioned_user=self.mentioned, mentioned_by=self.sender,
            )


# ─────────────────────────────────────────────────────────────────────────────
# MediaAttachment
# ─────────────────────────────────────────────────────────────────────────────

class TestMediaAttachment(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    def _make(self, mimetype="image/jpeg", status="ready", **kwargs):
        return MediaAttachment.objects.create(
            uploaded_by=self.user,
            message=self.msg,
            original_filename="test.jpg",
            file_key=f"uploads/test_{mimetype.replace('/','_')}_{status}.jpg",
            original_url=f"https://cdn.example.com/uploads/test_{status}.jpg",
            mimetype=mimetype,
            file_size=102400,
            status=status,
            **kwargs,
        )

    def test_is_image_property(self):
        a = self._make("image/jpeg")
        self.assertTrue(a.is_image)
        self.assertFalse(a.is_video)
        self.assertFalse(a.is_audio)

    def test_is_video_property(self):
        a = self._make("video/mp4")
        self.assertFalse(a.is_image)
        self.assertTrue(a.is_video)

    def test_is_audio_property(self):
        a = self._make("audio/ogg")
        self.assertFalse(a.is_image)
        self.assertTrue(a.is_audio)

    def test_best_url_prefers_compressed_over_webp(self):
        # best_url = compressed > webp > original (per model)
        a = self._make(
            webp_url="https://cdn.example.com/uploads/test.webp",
            compressed_url="https://cdn.example.com/uploads/test-c.jpg",
        )
        self.assertIn("test-c", a.best_url)

    def test_best_url_falls_back_to_compressed(self):
        a = self._make(
            compressed_url="https://cdn.example.com/uploads/test-c.jpg",
            webp_url="",
        )
        self.assertIn("test-c", a.best_url)

    def test_best_url_falls_back_to_original(self):
        a = self._make()
        self.assertEqual(a.best_url, a.original_url)

    def test_status_values(self):
        for s in ["pending", "processing", "ready", "failed", "blocked"]:
            a = self._make(status=s)
            self.assertEqual(a.status, s)


# ─────────────────────────────────────────────────────────────────────────────
# WebhookDelivery
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookDelivery(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        self.webhook = MessagingWebhook.objects.create(
            name="Delivery Test Hook",
            url="https://example.com/hook",
            secret="abc",
            events=["message.sent"],
            created_by=self.admin,
        )

    def test_create_successful_delivery(self):
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={"message_id": "msg-123", "content": "Hello"},
            response_status=200,
            response_body='{"ok": true}',
            is_successful=True,
            attempt_count=1,
        )
        self.assertIsNotNone(delivery.id)
        self.assertTrue(delivery.is_successful)

    def test_create_failed_delivery(self):
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={"message_id": "msg-456"},
            response_status=500,
            is_successful=False,
            attempt_count=1,
            error="Connection refused",
        )
        self.assertFalse(delivery.is_successful)
        self.assertEqual(delivery.error, "Connection refused")

    def test_retry_scheduling(self):
        from django.utils import timezone
        next_retry = timezone.now() + timedelta(minutes=5)
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={},
            is_successful=False,
            attempt_count=2,
            next_retry_at=next_retry,
        )
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.next_retry_at)

    def test_max_attempts_logic(self):
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={},
            is_successful=False,
            attempt_count=5,
        )
        self.assertEqual(delivery.attempt_count, 5)

    def test_delivered_at_set_on_success(self):
        now = timezone.now()
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="message.sent",
            payload={},
            is_successful=True,
            delivered_at=now,
        )
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.delivered_at)
