"""
test_services_coverage_boost.py
=================================
Targeted coverage for services.py functions/branches not exercised by the
existing test_services.py / test_services_missing.py suites: forward_message,
send_scheduled_message_now, _call_translation_provider (Google/DeepL/stub),
poll edge cases, the bot trigger engine, and the Celery-beat cleanup/
processing functions (expire_disappearing_messages, expire_old_stories,
fetch_and_save_link_previews, process_voice_message).

Place in: messaging/tests/test_services_coverage_boost.py
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone

from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory, ChatMessageFactory,
    BotConfigFactory,
)
from ..models import (
    ScheduledMessage, MessageTranslation, PollVote, BotConfig, BotResponse,
    DisappearingMessageConfig, UserStory, LinkPreview, MessageLinkPreview,
    VoiceMessageTranscription, ChatMessage,
)
from ..choices import ScheduledMessageStatus, MessageType
from ..exceptions import MessageNotFoundError, MessageDeletedError, MessagingError
from .. import services


def _chat_with_two_participants():
    chat = InternalChatFactory()
    a, b = UserFactory(), UserFactory()
    ChatParticipantFactory(chat=chat, user=a)
    ChatParticipantFactory(chat=chat, user=b)
    return chat, a, b


class TestForwardMessage(TestCase):
    def test_forwards_to_target_chat(self):
        chat, a, b = _chat_with_two_participants()
        target = InternalChatFactory()
        ChatParticipantFactory(chat=target, user=a)
        original = ChatMessageFactory(chat=chat, sender=a, content="check this out")

        forwarded = services.forward_message(
            message_id=original.id, target_chat_id=target.id, forwarded_by_id=a.pk,
        )
        self.assertEqual(forwarded.chat_id, target.id)
        self.assertEqual(forwarded.content, "check this out")
        self.assertTrue(forwarded.is_forwarded)
        forwarded.refresh_from_db()
        self.assertTrue(forwarded.is_forwarded)
        self.assertEqual(forwarded.forwarded_from_id, original.id)

    def test_not_found(self):
        chat, a, b = _chat_with_two_participants()
        with self.assertRaises(MessageNotFoundError):
            services.forward_message(
                message_id="00000000-0000-0000-0000-000000000000",
                target_chat_id=chat.id, forwarded_by_id=a.pk,
            )

    def test_cannot_forward_deleted_message(self):
        chat, a, b = _chat_with_two_participants()
        msg = ChatMessageFactory(chat=chat, sender=a, status="DELETED")
        with self.assertRaises(MessageDeletedError):
            services.forward_message(
                message_id=msg.id, target_chat_id=chat.id, forwarded_by_id=a.pk,
            )


class TestSendScheduledMessageNow(TestCase):
    def test_sends_pending_scheduled_message(self):
        chat, a, b = _chat_with_two_participants()
        sched = ScheduledMessage.objects.create(
            chat=chat, sender=a, content="future msg", scheduled_for=timezone.now(),
            status=ScheduledMessageStatus.PENDING,
        )
        msg = services.send_scheduled_message_now(scheduled_id=sched.id)
        self.assertEqual(msg.content, "future msg")
        sched.refresh_from_db()
        self.assertEqual(sched.status, ScheduledMessageStatus.SENT)
        self.assertEqual(sched.sent_message_id, msg.id)

    def test_not_found_or_not_pending(self):
        chat, a, b = _chat_with_two_participants()
        sched = ScheduledMessage.objects.create(
            chat=chat, sender=a, content="x", scheduled_for=timezone.now(),
            status=ScheduledMessageStatus.CANCELLED,
        )
        with self.assertRaises(MessagingError):
            services.send_scheduled_message_now(scheduled_id=sched.id)

    def test_marks_failed_on_send_error(self):
        chat, a, b = _chat_with_two_participants()
        sched = ScheduledMessage.objects.create(
            chat=chat, sender=a, content="x", scheduled_for=timezone.now(),
            status=ScheduledMessageStatus.PENDING,
        )
        with patch("messaging.services.send_chat_message", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.send_scheduled_message_now(scheduled_id=sched.id)
        sched.refresh_from_db()
        self.assertEqual(sched.status, ScheduledMessageStatus.FAILED)
        self.assertIn("boom", sched.error)


class TestCallTranslationProvider(TestCase):
    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key", DEEPL_API_KEY=None)
    def test_google_translate_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"translations": [{"translatedText": "Bonjour", "detectedSourceLanguage": "en"}]}
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp) as mock_post:
            text, source = services._call_translation_provider("Hello", "fr")
        self.assertEqual(text, "Bonjour")
        self.assertEqual(source, "en")
        mock_post.assert_called_once()

    @override_settings(GOOGLE_TRANSLATE_API_KEY="fake-key", DEEPL_API_KEY=None)
    def test_google_translate_failure_falls_back_to_stub(self):
        with patch("requests.post", side_effect=RuntimeError("network down")):
            text, source = services._call_translation_provider("Hello", "fr")
        self.assertIn("Hello", text)
        self.assertEqual(source, "unknown")

    @override_settings(GOOGLE_TRANSLATE_API_KEY=None, DEEPL_API_KEY="fake-deepl-key")
    def test_deepl_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "translations": [{"text": "Hallo", "detected_source_language": "EN"}]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_resp):
            text, source = services._call_translation_provider("Hello", "de")
        self.assertEqual(text, "Hallo")
        self.assertEqual(source, "en")

    @override_settings(GOOGLE_TRANSLATE_API_KEY=None, DEEPL_API_KEY="fake-deepl-key")
    def test_deepl_failure_falls_back_to_stub(self):
        with patch("requests.post", side_effect=RuntimeError("network down")):
            text, source = services._call_translation_provider("Hello", "de")
        self.assertIn("Hello", text)
        self.assertEqual(source, "unknown")

    @override_settings(GOOGLE_TRANSLATE_API_KEY=None, DEEPL_API_KEY=None)
    def test_stub_when_no_provider_configured(self):
        text, source = services._call_translation_provider("Hello", "bn")
        self.assertEqual(text, "[BN] Hello")
        self.assertEqual(source, "unknown")

    @override_settings(GOOGLE_TRANSLATE_API_KEY=None, DEEPL_API_KEY=None)
    def test_translate_message_caches_result(self):
        chat, a, b = _chat_with_two_participants()
        msg = ChatMessageFactory(chat=chat, sender=a, content="Hi there")
        result1 = services.translate_message(message_id=msg.id, target_language="fr", user_id=a.pk)
        self.assertEqual(MessageTranslation.objects.filter(message=msg).count(), 1)
        # Second call should hit the cache, not call the provider again.
        with patch("messaging.services._call_translation_provider") as mock_provider:
            result2 = services.translate_message(message_id=msg.id, target_language="fr", user_id=a.pk)
        mock_provider.assert_not_called()
        self.assertEqual(result1, result2)


class TestPollEdgeCases(TestCase):
    def setUp(self):
        self.chat, self.a, self.b = _chat_with_two_participants()

    def test_create_poll_requires_question(self):
        with self.assertRaises(MessagingError):
            services.create_poll(chat_id=self.chat.id, sender_id=self.a.pk, question="  ", options=["A", "B"])

    def test_create_poll_requires_at_least_two_options(self):
        with self.assertRaises(MessagingError):
            services.create_poll(chat_id=self.chat.id, sender_id=self.a.pk, question="Q?", options=["A"])

    def test_create_poll_rejects_too_many_options(self):
        with self.assertRaises(MessagingError):
            services.create_poll(
                chat_id=self.chat.id, sender_id=self.a.pk, question="Q?",
                options=[str(i) for i in range(11)],
            )

    def test_vote_on_unknown_option_rejected(self):
        poll = services.create_poll(
            chat_id=self.chat.id, sender_id=self.a.pk, question="Pick one", options=["Red", "Blue"],
        )
        with self.assertRaises(MessagingError):
            services.vote_on_poll(message_id=poll.id, user_id=self.b.pk, option_id="99")

    def test_vote_on_expired_poll_rejected(self):
        poll = services.create_poll(
            chat_id=self.chat.id, sender_id=self.a.pk, question="Pick one",
            options=["Red", "Blue"], expires_in_hours=-1,
        )
        with self.assertRaises(MessagingError):
            services.vote_on_poll(message_id=poll.id, user_id=self.b.pk, option_id="0")

    def test_vote_success_and_results(self):
        poll = services.create_poll(
            chat_id=self.chat.id, sender_id=self.a.pk, question="Pick one", options=["Red", "Blue"],
        )
        services.vote_on_poll(message_id=poll.id, user_id=self.a.pk, option_id="0")
        services.vote_on_poll(message_id=poll.id, user_id=self.b.pk, option_id="1")
        results = services.get_poll_results(poll.id, self.a.pk)
        self.assertEqual(results["options"]["0"]["votes"], 1)
        self.assertEqual(results["options"]["0"]["percentage"], 50.0)

    def test_results_not_found(self):
        with self.assertRaises(MessageNotFoundError):
            services.get_poll_results("00000000-0000-0000-0000-000000000000", self.a.pk)

    def test_results_with_zero_votes(self):
        poll = services.create_poll(
            chat_id=self.chat.id, sender_id=self.a.pk, question="Pick one", options=["Red", "Blue"],
        )
        results = services.get_poll_results(poll.id, self.a.pk)
        self.assertEqual(results["total_votes"], 0)
        self.assertEqual(results["options"]["0"]["percentage"], 0)


class TestProcessBotTriggers(TestCase):
    def setUp(self):
        self.chat, self.a, self.b = _chat_with_two_participants()

    def test_no_message_returns_empty(self):
        result = services.process_bot_triggers("00000000-0000-0000-0000-000000000000")
        self.assertEqual(result, [])

    def test_deleted_message_returns_empty(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, status="DELETED")
        self.assertEqual(services.process_bot_triggers(msg.id), [])

    def test_system_message_returns_empty(self):
        msg = ChatMessageFactory(chat=self.chat, sender=None, message_type=MessageType.SYSTEM, content="user joined")
        self.assertEqual(services.process_bot_triggers(msg.id), [])

    def test_keyword_trigger_matches(self):
        BotConfigFactory(
            trigger_type="KEYWORD", trigger_value="help", is_active=True,
            response_template="How can I help, {user_name}?", chat=None, delay_seconds=0,
        )
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="I need HELP please")
        responses = services.process_bot_triggers(msg.id)
        self.assertEqual(len(responses), 1)
        self.assertTrue(responses[0].was_successful)

    def test_keyword_trigger_no_match(self):
        BotConfigFactory(trigger_type="KEYWORD", trigger_value="refund", is_active=True, chat=None)
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="hello world")
        self.assertEqual(services.process_bot_triggers(msg.id), [])

    def test_regex_trigger_matches(self):
        BotConfigFactory(
            trigger_type="REGEX", trigger_value=r"\border\s*#?\d+\b", is_active=True,
            response_template="Thanks!", chat=None,
        )
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="Where is order #4521?")
        responses = services.process_bot_triggers(msg.id)
        self.assertEqual(len(responses), 1)

    def test_regex_trigger_invalid_pattern_skipped(self):
        BotConfigFactory(
            trigger_type="REGEX", trigger_value="[invalid(regex", is_active=True, chat=None,
        )
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="anything")
        # Should not raise -- invalid regex is caught and logged, bot just doesn't fire.
        self.assertEqual(services.process_bot_triggers(msg.id), [])

    def test_always_trigger_fires(self):
        BotConfigFactory(trigger_type="ALWAYS", is_active=True, response_template="Auto-reply", chat=None)
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="anything at all")
        responses = services.process_bot_triggers(msg.id)
        self.assertEqual(len(responses), 1)

    def test_response_template_substitutes_chat_name(self):
        named_chat = InternalChatFactory(name="Support Room", is_group=True)
        ChatParticipantFactory(chat=named_chat, user=self.a)
        BotConfigFactory(
            trigger_type="ALWAYS", is_active=True,
            response_template="Welcome to {chat_name}!", chat=None,
        )
        msg = ChatMessageFactory(chat=named_chat, sender=self.a, content="hi")
        responses = services.process_bot_triggers(msg.id)
        self.assertEqual(responses[0].sent_message.content, "Welcome to Support Room!")

    def test_bot_failure_recorded(self):
        BotConfigFactory(trigger_type="ALWAYS", is_active=True, chat=None)
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="hi")
        with patch("messaging.services.ChatMessage.objects.create", side_effect=RuntimeError("db error")):
            responses = services.process_bot_triggers(msg.id)
        self.assertEqual(len(responses), 1)
        self.assertFalse(responses[0].was_successful)
        self.assertIn("db error", responses[0].error)

    def test_inactive_bot_does_not_fire(self):
        BotConfigFactory(trigger_type="ALWAYS", is_active=False, chat=None)
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="hi")
        self.assertEqual(services.process_bot_triggers(msg.id), [])


class TestExpireDisappearingMessages(TestCase):
    def test_deletes_old_messages_in_enabled_chats(self):
        chat, a, b = _chat_with_two_participants()
        DisappearingMessageConfig.objects.create(
            chat=chat, is_enabled=True, ttl_seconds=60, enabled_by=a, enabled_at=timezone.now(),
        )
        old_msg = ChatMessageFactory(chat=chat, sender=a, content="old")
        ChatMessage.objects.filter(pk=old_msg.pk).update(
            created_at=timezone.now() - timedelta(seconds=120)
        )
        deleted_count = services.expire_disappearing_messages()
        self.assertEqual(deleted_count, 1)
        old_msg.refresh_from_db()
        self.assertEqual(old_msg.status, "DELETED")

    def test_leaves_recent_messages_alone(self):
        chat, a, b = _chat_with_two_participants()
        DisappearingMessageConfig.objects.create(
            chat=chat, is_enabled=True, ttl_seconds=3600, enabled_by=a, enabled_at=timezone.now(),
        )
        ChatMessageFactory(chat=chat, sender=a, content="fresh")
        self.assertEqual(services.expire_disappearing_messages(), 0)

    def test_no_configs_returns_zero(self):
        self.assertEqual(services.expire_disappearing_messages(), 0)


class TestExpireOldStories(TestCase):
    def test_deactivates_expired_stories(self):
        user = UserFactory()
        story = UserStory.objects.create(
            user=user, story_type="text", content="old story", is_active=True,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        count = services.expire_old_stories()
        self.assertEqual(count, 1)
        story.refresh_from_db()
        self.assertFalse(story.is_active)

    def test_leaves_active_stories_alone(self):
        user = UserFactory()
        UserStory.objects.create(
            user=user, story_type="text", content="fresh", is_active=True,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(services.expire_old_stories(), 0)


class TestFetchAndSaveLinkPreviews(TestCase):
    def setUp(self):
        self.chat, self.a, self.b = _chat_with_two_participants()

    def test_no_message_returns_empty(self):
        self.assertEqual(services.fetch_and_save_link_previews("00000000-0000-0000-0000-000000000000"), [])

    def test_no_urls_returns_empty(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="no links here")
        self.assertEqual(services.fetch_and_save_link_previews(msg.id), [])

    def test_fetches_and_saves_new_preview(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="check https://example.com out")
        with patch("messaging.utils.link_preview.fetch_link_preview") as mock_fetch, \
             patch("messaging.utils.link_preview.check_safe_browsing", return_value=True):
            mock_fetch.return_value = {
                "title": "Example Site", "description": "desc", "domain": "example.com",
                "is_safe": True,
            }
            previews = services.fetch_and_save_link_previews(msg.id)
        self.assertEqual(len(previews), 1)
        self.assertEqual(previews[0].title, "Example Site")
        self.assertTrue(MessageLinkPreview.objects.filter(message=msg, preview=previews[0]).exists())

    def test_reuses_cached_preview(self):
        LinkPreview.objects.create(url="https://example.com", title="Cached")
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, content="see https://example.com")
        with patch("messaging.utils.link_preview.fetch_link_preview") as mock_fetch:
            previews = services.fetch_and_save_link_previews(msg.id)
        mock_fetch.assert_not_called()
        self.assertEqual(previews[0].title, "Cached")


class TestProcessVoiceMessage(TestCase):
    def setUp(self):
        self.chat, self.a, self.b = _chat_with_two_participants()

    def test_not_found(self):
        with self.assertRaises(MessageNotFoundError):
            services.process_voice_message("00000000-0000-0000-0000-000000000000")

    def test_no_attachments_rejected(self):
        msg = ChatMessageFactory(chat=self.chat, sender=self.a, message_type=MessageType.AUDIO, attachments=[])
        with self.assertRaises(MessagingError):
            services.process_voice_message(msg.id)

    def test_returns_existing_completed_transcription(self):
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.a, message_type=MessageType.AUDIO,
            attachments=[{"url": "https://cdn.example.com/audio.mp3", "filename": "audio.mp3", "mimetype": "audio/mpeg", "size_bytes": 5000}],
        )
        existing = VoiceMessageTranscription.objects.create(
            message=msg, transcribed_text="already done", is_processing=False,
        )
        result = services.process_voice_message(msg.id)
        self.assertEqual(result.pk, existing.pk)

    def test_success_path(self):
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.a, message_type=MessageType.AUDIO,
            attachments=[{"url": "https://cdn.example.com/audio.mp3", "filename": "audio.mp3", "mimetype": "audio/mpeg", "size_bytes": 5000}],
        )
        mock_resp = MagicMock()
        mock_resp.content = b"fake-audio-bytes"
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp), \
             patch("messaging.utils.voice_processor.generate_waveform", return_value=[0.1, 0.2]), \
             patch("messaging.utils.voice_processor.get_audio_duration", return_value=12.5), \
             patch("messaging.utils.voice_processor.transcribe_audio", return_value={
                 "text": "hello world", "language": "en", "confidence": 0.9, "provider": "whisper",
             }):
            result = services.process_voice_message(msg.id)
        self.assertEqual(result.transcribed_text, "hello world")
        self.assertFalse(result.is_processing)

    def test_failure_marks_error(self):
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.a, message_type=MessageType.AUDIO,
            attachments=[{"url": "https://cdn.example.com/audio.mp3", "filename": "audio.mp3", "mimetype": "audio/mpeg", "size_bytes": 5000}],
        )
        with patch("requests.get", side_effect=RuntimeError("timeout")):
            with self.assertRaises(RuntimeError):
                services.process_voice_message(msg.id)
        transcription = VoiceMessageTranscription.objects.get(message=msg)
        self.assertFalse(transcription.is_processing)
        self.assertIn("timeout", transcription.error)
