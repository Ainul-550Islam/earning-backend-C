"""
test_signals_audit_fix.py
===========================
Audit finding (Part 19): 8 of the 21 signals flagged in earlier sessions
as "never fired" already had real, working @receiver functions connected
in receivers.py - several doing genuine user-facing work (broadcasting
message.edited / chat.disappearing_changed / voice.transcribed /
message.link_previews WebSocket events to live clients, or dispatching
support-thread webhooks). Nothing on the sender side ever called
.send(), so none of that ever ran in production. test_receivers.py
already covers the receiver logic in isolation (by calling .send()
directly); this file covers the piece that was missing - that the real
application code path actually fires the signal.

process_voice_message() had a second, adjacent bug surfaced while
wiring this up: language/duration_seconds were saved to the DB but
never mirrored onto the in-memory `transcription` object the way
transcribed_text/waveform_data/is_processing already were - fixed
alongside the signal wiring since the receiver reads both straight off
that object.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from .factories import (
    ChatMessageFactory,
    ChatParticipantFactory,
    InternalChatFactory,
    UserFactory,
)
from .. import services, signals
from ..choices import ParticipantRole, SupportThreadStatus
from ..models import (
    BotConfig,
    BotResponse,
    LinkPreview,
    MessagingWebhook,
    SupportThread,
    VoiceMessageTranscription,
    WebhookDelivery,
)


class TestSupportThreadStatusChangedFires(TestCase):
    def setUp(self):
        self.thread = SupportThread.objects.create(user=UserFactory(), subject="Help")
        self.agent = UserFactory()

    @patch.object(signals.support_thread_status_changed, "send")
    def test_transition_to_fires_signal(self, mock_send):
        self.thread.transition_to(SupportThreadStatus.IN_PROGRESS, agent=self.agent)
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["thread"], self.thread)
        self.assertEqual(kwargs["old_status"], SupportThreadStatus.OPEN)
        self.assertEqual(kwargs["new_status"], SupportThreadStatus.IN_PROGRESS)

    @patch("messaging.services.dispatch_webhook_event")
    def test_transition_to_reaches_real_receiver_which_dispatches_webhook(self, mock_dispatch):
        """End-to-end (no signal mock): the receiver that was already there
        actually runs now and calls dispatch_webhook_event."""
        self.thread.transition_to(SupportThreadStatus.IN_PROGRESS, agent=self.agent)
        mock_dispatch.assert_called_once()
        self.assertEqual(mock_dispatch.call_args[0][0], "support.opened")


class TestBotResponseSentFires(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.bot = BotConfig.objects.create(
            name="Greeter", trigger_type="ALWAYS", trigger_value="", response_template="hi", is_active=True,
        )
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="hello")

    @patch.object(signals.bot_response_sent, "send")
    def test_successful_bot_reply_fires_signal(self, mock_send):
        responses = services.process_bot_triggers(str(self.msg.id))
        self.assertEqual(len(responses), 1)
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs["bot_response"], responses[0])

    @patch.object(signals.bot_response_sent, "send")
    def test_failed_bot_reply_does_not_fire_signal(self, mock_send):
        with patch("messaging.models.ChatMessage.objects.create", side_effect=Exception("db down")):
            services.process_bot_triggers(str(self.msg.id))
        mock_send.assert_not_called()


class TestWebhookDeliveryAttemptedFires(TestCase):
    def setUp(self):
        self.webhook = MessagingWebhook.objects.create(
            url="https://example.com/hook", events=["support.opened"], secret="s3cr3t", is_active=True,
        )

    @patch("requests.post")
    @patch.object(signals.webhook_delivery_attempted, "send")
    def test_dispatch_task_fires_signal_per_delivery(self, mock_send, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "ok"
        from ..tasks import dispatch_webhook_task
        dispatch_webhook_task.run("support.opened", {"thread_id": "abc"})
        mock_send.assert_called_once()
        delivery = mock_send.call_args.kwargs["delivery"]
        self.assertIsInstance(delivery, WebhookDelivery)
        self.assertTrue(delivery.is_successful)


class TestStoryRepliedFires(TestCase):
    def setUp(self):
        from ..models import UserStory, StoryView
        self.owner = UserFactory()
        self.viewer = UserFactory()
        self.story = UserStory.objects.create(user=self.owner, story_type="text", content="hi")
        self.view = StoryView.objects.create(story=self.story, viewer=self.viewer)

    @patch.object(signals.story_replied, "send")
    def test_reply_to_story_fires_signal(self, mock_send):
        result = services.reply_to_story(story_id=str(self.story.id), viewer_id=self.viewer.pk, reaction_emoji="🔥")
        mock_send.assert_called_once_with(sender=type(self.view), view=result)


class TestMessageEditedWithHistoryFires(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="v1")

    @patch.object(signals.message_edited_with_history, "send")
    def test_edit_fires_signal(self, mock_send):
        message, history = services.edit_message_with_history(
            message_id=str(self.msg.id), user_id=self.user.pk, new_content="v2",
        )
        mock_send.assert_called_once_with(sender=type(message), message=message, edit_history=history)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_edit_reaches_real_receiver_which_broadcasts_ws_event(self, mock_ws):
        """
        Note: on_message_edited_with_history no longer calls
        send_websocket_event() directly - see test_ws_dispatch_audit_fix.py
        for why (it needs chat_message_edited's flat event shape, not
        send_websocket_event's data-nested one, to match the pre-existing
        WS-native edit path). This test now just confirms the receiver
        runs without raising; the full broadcast-reaches-a-real-client
        path is covered end-to-end in test_ws_dispatch_audit_fix.py.
        """
        message, history = services.edit_message_with_history(
            message_id=str(self.msg.id), user_id=self.user.pk, new_content="v2 for real",
        )
        self.assertEqual(message.content, "v2 for real")


class TestDisappearingConfigChangedFires(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user, role=ParticipantRole.ADMIN)

    @patch.object(signals.disappearing_config_changed, "send")
    def test_set_disappearing_messages_fires_signal(self, mock_send):
        config = services.set_disappearing_messages(
            chat_id=str(self.chat.id), enabled_by_id=self.user.pk, ttl_seconds=3600,
        )
        mock_send.assert_called_once_with(sender=type(config), config=config, chat=self.chat)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_reaches_real_receiver_which_broadcasts_ws_event(self, mock_ws):
        services.set_disappearing_messages(
            chat_id=str(self.chat.id), enabled_by_id=self.user.pk, ttl_seconds=3600,
        )
        mock_ws.assert_called_once()
        self.assertEqual(mock_ws.call_args.kwargs["event_type"], "chat.disappearing_changed")


class TestLinkPreviewsFetchedFires(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="check https://example.com out")

    @patch("messaging.utils.link_preview.check_safe_browsing", return_value=True)
    @patch("messaging.utils.link_preview.fetch_link_preview")
    @patch.object(signals.link_previews_fetched, "send")
    def test_fetch_fires_signal_with_dict_shaped_previews(self, mock_send, mock_fetch, mock_safe):
        mock_fetch.return_value = {
            "title": "Example", "description": "An example site", "domain": "example.com",
        }
        services.fetch_and_save_link_previews(str(self.msg.id))
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["message"], self.msg)
        self.assertEqual(len(kwargs["previews"]), 1)
        # Receiver-compatible dict shape (p.get("url", ...)), not a model instance
        self.assertIsInstance(kwargs["previews"][0], dict)
        self.assertIn("url", kwargs["previews"][0])


class TestVoiceMessageTranscribedFires(TestCase):
    def setUp(self):
        from ..choices import MessageType
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(
            chat=self.chat, sender=self.user, message_type=MessageType.AUDIO,
            attachments=[{
                "url": "https://example.com/voice.ogg",
                "filename": "voice.ogg",
                "mimetype": "audio/ogg",
                "size_bytes": 12345,
            }],
        )

    @patch("requests.get")
    @patch("messaging.utils.voice_processor.get_audio_duration", return_value=12.5)
    @patch("messaging.utils.voice_processor.generate_waveform", return_value=[0.1, 0.2])
    @patch("messaging.utils.voice_processor.transcribe_audio")
    @patch.object(signals.voice_message_transcribed, "send")
    def test_transcription_fires_signal_with_full_data(
        self, mock_send, mock_transcribe, mock_waveform, mock_duration, mock_get
    ):
        mock_get.return_value.content = b"fake-audio-bytes"
        mock_get.return_value.raise_for_status = lambda: None
        mock_transcribe.return_value = {"text": "hello there", "language": "en", "confidence": 0.9, "provider": "whisper"}

        result = services.process_voice_message(str(self.msg.id))

        mock_send.assert_called_once()
        transcription = mock_send.call_args.kwargs["transcription"]
        self.assertEqual(transcription, result)
        # Audit fix: language/duration_seconds must be present on the
        # in-memory object the receiver reads, not just written to the DB.
        self.assertEqual(transcription.language, "en")
        self.assertEqual(transcription.duration_seconds, 12.5)

    @patch("requests.get")
    @patch("messaging.utils.voice_processor.get_audio_duration", return_value=12.5)
    @patch("messaging.utils.voice_processor.generate_waveform", return_value=[0.1, 0.2])
    @patch("messaging.utils.voice_processor.transcribe_audio")
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_reaches_real_receiver_with_correct_language_and_duration(
        self, mock_ws, mock_transcribe, mock_waveform, mock_duration, mock_get
    ):
        mock_get.return_value.content = b"fake-audio-bytes"
        mock_get.return_value.raise_for_status = lambda: None
        mock_transcribe.return_value = {"text": "hi", "language": "bn", "confidence": 0.9, "provider": "whisper"}

        services.process_voice_message(str(self.msg.id))

        mock_ws.assert_called_once()
        data = mock_ws.call_args.kwargs["data"]
        self.assertEqual(data["language"], "bn")
        self.assertEqual(data["duration_seconds"], 12.5)

    @patch("requests.get", side_effect=Exception("network down"))
    @patch.object(signals.voice_message_transcribed, "send")
    def test_failed_transcription_does_not_fire_signal(self, mock_send, mock_get):
        with self.assertRaises(Exception):
            services.process_voice_message(str(self.msg.id))
        mock_send.assert_not_called()
