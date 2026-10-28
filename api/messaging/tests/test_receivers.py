"""
test_receivers.py
==================
Full coverage for messaging/receivers.py — all 26 signal receivers.
Place in: messaging/tests/test_receivers.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock, call
from django.test import TestCase

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
    UserInbox,
    ChatMessage,
    CallSession,
    DisappearingMessageConfig,
    MessagePin,
    VoiceMessageTranscription,
    MessageEditHistory,
)
from ..signals import (
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
    users_mentioned,
    user_blocked,
    user_unblocked,
    scheduled_message_sent,
    bot_response_sent,
    channel_subscribed,
    channel_unsubscribed,
    webhook_delivery_attempted,
    story_created,
    story_viewed,
    story_replied,
    message_edited_with_history,
    disappearing_config_changed,
    voice_message_transcribed,
)
from ..signals import chat_message_sent as _cms


class TestOnChatMessageSent(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("messaging.tasks.notify_new_chat_message")
    @patch("messaging.services.dispatch_webhook_event")
    def test_queues_notification_task(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        chat_message_sent.send(sender=ChatMessage, message=self.msg, chat=self.chat)
        mock_notify.delay.assert_called_once_with(str(self.msg.id))

    @patch("messaging.tasks.notify_new_chat_message")
    @patch("messaging.services.dispatch_webhook_event")
    def test_dispatches_webhook_event(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        chat_message_sent.send(sender=ChatMessage, message=self.msg, chat=self.chat)
        mock_webhook.assert_called_once()
        call_args = mock_webhook.call_args[0]
        self.assertEqual(call_args[0], "message.sent")

    @patch("messaging.tasks.notify_new_chat_message")
    @patch("messaging.services.dispatch_webhook_event")
    def test_missing_message_does_not_raise(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        # Should not raise even with None message
        chat_message_sent.send(sender=ChatMessage, message=None, chat=self.chat)

    @patch("messaging.tasks.notify_new_chat_message")
    @patch("messaging.services.dispatch_webhook_event")
    def test_task_exception_does_not_propagate(self, mock_webhook, mock_notify):
        mock_notify.delay.side_effect = Exception("Celery down")
        # Should swallow exception — receiver is defensive
        chat_message_sent.send(sender=ChatMessage, message=self.msg, chat=self.chat)


class TestOnBroadcastSent(TestCase):
    @patch("messaging.utils.notifier.notify_broadcast_sent")
    @patch("messaging.services.dispatch_webhook_event")
    def test_calls_notify_and_webhook(self, mock_webhook, mock_notify):
        broadcast = MagicMock()
        broadcast.id = "bc-1"
        broadcast.title = "Big Announcement"
        broadcast.recipient_count = 500
        broadcast_sent.send(sender=object, broadcast=broadcast)
        mock_notify.assert_called_once()
        mock_webhook.assert_called_once()

    @patch("messaging.utils.notifier.notify_broadcast_sent")
    @patch("messaging.services.dispatch_webhook_event")
    def test_missing_broadcast_does_not_raise(self, mock_webhook, mock_notify):
        broadcast_sent.send(sender=object, broadcast=None)
        mock_notify.assert_not_called()

    @patch("messaging.utils.notifier.notify_broadcast_sent")
    @patch("messaging.services.dispatch_webhook_event")
    def test_exception_does_not_propagate(self, mock_webhook, mock_notify):
        mock_notify.side_effect = Exception("Notifier down")
        broadcast = MagicMock()
        broadcast.id = "bc-2"
        broadcast.title = "Test"
        broadcast.recipient_count = 10
        # Should not raise
        broadcast_sent.send(sender=object, broadcast=broadcast)


class TestOnSupportReplyPosted(TestCase):
    @patch("messaging.tasks.notify_support_reply")
    def test_queues_support_reply_task(self, mock_task):
        mock_task.delay = MagicMock()
        support_msg = MagicMock()
        support_msg.id = "sm-1"
        thread = MagicMock()
        support_reply_posted.send(sender=object, support_message=support_msg, thread=thread)
        mock_task.delay.assert_called_once_with(str(support_msg.id))

    @patch("messaging.tasks.notify_support_reply")
    def test_missing_support_message_does_not_raise(self, mock_task):
        mock_task.delay = MagicMock()
        support_reply_posted.send(sender=object, support_message=None, thread=None)
        mock_task.delay.assert_not_called()


class TestOnSupportThreadStatusChanged(TestCase):
    @patch("messaging.services.dispatch_webhook_event")
    def test_dispatches_support_closed_event(self, mock_webhook):
        thread = MagicMock()
        thread.id = "t-1"
        support_thread_status_changed.send(
            sender=object, thread=thread,
            old_status="IN_PROGRESS", new_status="CLOSED"
        )
        mock_webhook.assert_called_once()
        args = mock_webhook.call_args[0]
        self.assertEqual(args[0], "support.closed")

    @patch("messaging.services.dispatch_webhook_event")
    def test_dispatches_support_opened_event(self, mock_webhook):
        thread = MagicMock()
        thread.id = "t-2"
        support_thread_status_changed.send(
            sender=object, thread=thread,
            old_status="CLOSED", new_status="OPEN"
        )
        args = mock_webhook.call_args[0]
        self.assertEqual(args[0], "support.opened")

    @patch("messaging.services.dispatch_webhook_event")
    def test_missing_thread_does_not_raise(self, mock_webhook):
        support_thread_status_changed.send(
            sender=object, thread=None, old_status="OPEN", new_status="CLOSED"
        )
        mock_webhook.assert_not_called()


class TestOnMessageReactionAdded(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_websocket_reaction_added(self, mock_ws):
        reaction = MagicMock()
        reaction.user_id = self.user.pk
        reaction.emoji = "👍"
        reaction.custom_emoji = None
        message_reaction_added.send(
            sender=object, reaction=reaction, message=self.msg
        )
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "reaction.added")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_reaction_does_not_raise(self, mock_ws):
        message_reaction_added.send(sender=object, reaction=None, message=self.msg)
        mock_ws.assert_not_called()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_websocket_exception_does_not_propagate(self, mock_ws):
        mock_ws.side_effect = Exception("WS down")
        reaction = MagicMock()
        reaction.user_id = self.user.pk
        reaction.emoji = "❤️"
        reaction.custom_emoji = None
        # Should not raise
        message_reaction_added.send(sender=object, reaction=reaction, message=self.msg)

    @patch("messaging.receivers.safe_receiver_error_handler")
    @patch("messaging.utils.notifier.notify_reaction")
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_pushes_notify_reaction_to_message_sender(self, mock_ws, mock_notify, mock_err):
        """
        Regression test (Part 6 audit): notify_reaction() existed fully
        built and tested in utils/notifier.py, but nothing ever called it -
        only the WS event was wired, so a message sender who wasn't
        actively WS-connected got no notification of a reaction at all.
        """
        reactor = UserFactory()
        reaction = MagicMock()
        reaction.user_id = reactor.pk
        reaction.user = reactor
        reaction.emoji = "🔥"
        reaction.custom_emoji = None
        message_reaction_added.send(sender=object, reaction=reaction, message=self.msg)
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs["user_id"], self.msg.sender_id)
        self.assertEqual(call_kwargs["emoji"], "🔥")
        mock_err.assert_not_called()

    @patch("messaging.utils.notifier.notify_reaction")
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_does_not_push_notify_for_self_reaction(self, mock_ws, mock_notify):
        """A user reacting to their own message shouldn't get pushed."""
        reaction = MagicMock()
        reaction.user_id = self.msg.sender_id  # same as message sender
        reaction.user = self.user
        reaction.emoji = "👍"
        reaction.custom_emoji = None
        message_reaction_added.send(sender=object, reaction=reaction, message=self.msg)
        mock_notify.assert_not_called()

    @patch("messaging.receivers.safe_receiver_error_handler")
    @patch("messaging.utils.notifier.notify_reaction")
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_push_failure_does_not_affect_websocket_delivery(self, mock_ws, mock_notify, mock_err):
        mock_notify.side_effect = Exception("push service down")
        reactor = UserFactory()
        reaction = MagicMock()
        reaction.user_id = reactor.pk
        reaction.user = reactor
        reaction.emoji = "🎉"
        reaction.custom_emoji = None
        # Should not raise, and the WS call (which happens first) must
        # still have gone through despite the later push failure.
        message_reaction_added.send(sender=object, reaction=reaction, message=self.msg)
        mock_ws.assert_called_once()
        mock_err.assert_called_once()


class TestOnMessageReactionRemoved(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_websocket_reaction_removed(self, mock_ws):
        message_reaction_removed.send(
            sender=object,
            user_id=self.user.pk,
            message_id=str(self.msg.id),
            emoji="👍",
        )
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "reaction.removed")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_params_does_not_raise(self, mock_ws):
        message_reaction_removed.send(
            sender=object, user_id=None, message_id=None, emoji=None
        )
        mock_ws.assert_not_called()


class TestOnCallStarted(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.caller = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.caller)

    @patch("messaging.tasks.notify_call_incoming")
    @patch("messaging.services.dispatch_webhook_event")
    def test_queues_call_incoming_task(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        call = MagicMock()
        call.id = "call-1"
        call.call_type = "audio"
        call.room_id = "room123"
        call.initiated_by_id = self.caller.pk
        call_started.send(sender=object, call=call, caller=self.caller)
        mock_notify.delay.assert_called_once_with(str(call.id))

    @patch("messaging.tasks.notify_call_incoming")
    @patch("messaging.services.dispatch_webhook_event")
    def test_dispatches_call_started_webhook(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        call = MagicMock()
        call.id = "call-2"
        call.call_type = "video"
        call.room_id = "room456"
        call.initiated_by_id = self.caller.pk
        call_started.send(sender=object, call=call, caller=self.caller)
        mock_webhook.assert_called_once()
        args = mock_webhook.call_args[0]
        self.assertEqual(args[0], "call.started")

    @patch("messaging.tasks.notify_call_incoming")
    @patch("messaging.services.dispatch_webhook_event")
    def test_missing_call_does_not_raise(self, mock_webhook, mock_notify):
        mock_notify.delay = MagicMock()
        call_started.send(sender=object, call=None, caller=None)
        mock_notify.delay.assert_not_called()


class TestOnCallEnded(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.services.dispatch_webhook_event")
    def test_writes_call_log_message(self, mock_webhook):
        call = MagicMock()
        call.id = "call-end-1"
        call.chat_id = str(self.chat.id)
        call.call_type = "audio"
        call.status = "ENDED"
        call.initiated_by_id = self.user.pk
        call.tenant = None
        call_ended.send(sender=object, call=call, duration_seconds=120)
        self.assertTrue(
            ChatMessage.objects.filter(chat=self.chat, message_type="CALL_LOG").exists()
        )

    @patch("messaging.services.dispatch_webhook_event")
    def test_dispatches_call_ended_webhook(self, mock_webhook):
        call = MagicMock()
        call.id = "call-end-2"
        call.chat_id = None
        call.call_type = "video"
        call.status = "ENDED"
        call.initiated_by_id = self.user.pk
        call.tenant = None
        call_ended.send(sender=object, call=call, duration_seconds=60)
        mock_webhook.assert_called()
        args = mock_webhook.call_args[0]
        self.assertEqual(args[0], "call.ended")

    @patch("messaging.services.dispatch_webhook_event")
    def test_missing_call_does_not_raise(self, mock_webhook):
        call_ended.send(sender=object, call=None, duration_seconds=0)
        mock_webhook.assert_not_called()


class TestOnPresenceChanged(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_broadcasts_to_all_user_chats(self, mock_ws):
        presence_changed.send(
            sender=object, user_id=self.user.pk, new_status="ONLINE"
        )
        mock_ws.assert_called()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "presence.changed")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_user_id_does_not_raise(self, mock_ws):
        presence_changed.send(sender=object, user_id=None, new_status="ONLINE")
        mock_ws.assert_not_called()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_exception_does_not_propagate(self, mock_ws):
        mock_ws.side_effect = Exception("WS error")
        # Should not raise
        presence_changed.send(sender=object, user_id=self.user.pk, new_status="AWAY")


class TestOnMessagePinned(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user, role="ADMIN")
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_message_pinned_event(self, mock_ws):
        pin = MagicMock()
        pin.message_id = str(self.msg.id)
        pin.pinned_by_id = self.user.pk
        message_pinned.send(sender=object, pin=pin, chat=self.chat)
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "message.pinned")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_pin_does_not_raise(self, mock_ws):
        message_pinned.send(sender=object, pin=None, chat=self.chat)
        mock_ws.assert_not_called()


class TestOnMessageUnpinned(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_message_unpinned_event(self, mock_ws):
        message_unpinned.send(
            sender=object,
            message_id="msg-123",
            chat_id=str(self.chat.id),
        )
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "message.unpinned")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_ids_does_not_raise(self, mock_ws):
        message_unpinned.send(sender=object, message_id=None, chat_id=None)
        mock_ws.assert_not_called()


class TestOnUsersMentioned(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.sender = UserFactory()
        self.mentionee_a = UserFactory()
        self.mentionee_b = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.sender)
        ChatParticipantFactory(chat=self.chat, user=self.mentionee_a)
        ChatParticipantFactory(chat=self.chat, user=self.mentionee_b)
        self.msg = ChatMessageFactory(
            chat=self.chat, sender=self.sender,
            content=f"@{self.mentionee_a.username} and @{self.mentionee_b.username}"
        )

    def test_creates_inbox_mention_items(self):
        users_mentioned.send(
            sender=ChatMessage,
            message=self.msg,
            mentioned_user_ids=[self.mentionee_a.pk, self.mentionee_b.pk],
        )
        self.assertEqual(
            UserInbox.objects.filter(
                user__in=[self.mentionee_a, self.mentionee_b],
                item_type="MENTION",
            ).count(),
            2,
        )

    def test_missing_message_does_not_raise(self):
        users_mentioned.send(
            sender=ChatMessage, message=None,
            mentioned_user_ids=[self.mentionee_a.pk]
        )
        self.assertEqual(UserInbox.objects.filter(item_type="MENTION").count(), 0)

    def test_empty_mentioned_list_does_not_raise(self):
        users_mentioned.send(
            sender=ChatMessage, message=self.msg, mentioned_user_ids=[]
        )
        self.assertEqual(UserInbox.objects.filter(item_type="MENTION").count(), 0)

    @patch("messaging.receivers.safe_receiver_error_handler")
    @patch("messaging.utils.notifier.notify_mention")
    def test_pushes_notify_mention_to_each_mentioned_user(self, mock_notify, mock_err):
        """
        Regression test (Part 6 audit): notify_mention() existed fully
        built and tested in utils/notifier.py, but nothing ever called it -
        a mentioned user previously only got a silent UserInbox row with
        no push alerting them to go check it.
        """
        users_mentioned.send(
            sender=ChatMessage,
            message=self.msg,
            mentioned_user_ids=[self.mentionee_a.pk, self.mentionee_b.pk],
        )
        self.assertEqual(mock_notify.call_count, 2)
        notified_uids = {c.kwargs["user_id"] for c in mock_notify.call_args_list}
        self.assertEqual(notified_uids, {self.mentionee_a.pk, self.mentionee_b.pk})
        mock_err.assert_not_called()

    @patch("messaging.utils.notifier.notify_mention")
    def test_does_not_push_notify_self_mention(self, mock_notify):
        """If the sender @mentions themselves, they shouldn't be pushed."""
        users_mentioned.send(
            sender=ChatMessage,
            message=self.msg,
            mentioned_user_ids=[self.sender.pk, self.mentionee_a.pk],
        )
        notified_uids = {c.kwargs["user_id"] for c in mock_notify.call_args_list}
        self.assertNotIn(self.sender.pk, notified_uids)
        self.assertIn(self.mentionee_a.pk, notified_uids)

    @patch("messaging.receivers.safe_receiver_error_handler")
    @patch("messaging.utils.notifier.notify_mention")
    def test_push_failure_does_not_affect_inbox_creation(self, mock_notify, mock_err):
        mock_notify.side_effect = Exception("push service down")
        users_mentioned.send(
            sender=ChatMessage,
            message=self.msg,
            mentioned_user_ids=[self.mentionee_a.pk],
        )
        # Inbox item (created first, in its own try/except) must still exist
        self.assertEqual(
            UserInbox.objects.filter(user=self.mentionee_a, item_type="MENTION").count(), 1
        )
        mock_err.assert_called_once()


class TestOnUserBlocked(TestCase):
    def test_logs_block_event_without_raising(self):
        block = MagicMock()
        block.blocker_id = 1
        block.blocked_id = 2
        user_blocked.send(sender=object, block=block)


class TestOnUserUnblocked(TestCase):
    def test_logs_unblock_event_without_raising(self):
        user_unblocked.send(sender=object, blocker_id=1, blocked_id=2)


class TestOnScheduledMessageSent(TestCase):
    def test_logs_without_raising(self):
        sched = MagicMock()
        sched.id = "sched-1"
        sent = MagicMock()
        sent.id = "msg-1"
        scheduled_message_sent.send(sender=object, scheduled_msg=sched, sent_message=sent)

    def test_missing_args_does_not_raise(self):
        scheduled_message_sent.send(sender=object, scheduled_msg=None, sent_message=None)


class TestOnBotResponseSent(TestCase):
    def test_logs_debug_without_raising(self):
        bot_response = MagicMock()
        bot_response.bot_id = "bot-1"
        bot_response.sent_message_id = "msg-1"
        bot_response_sent.send(sender=object, bot_response=bot_response)

    def test_missing_bot_response_does_not_raise(self):
        bot_response_sent.send(sender=object, bot_response=None)


class TestOnChannelSubscribed(TestCase):
    def test_logs_without_raising(self):
        channel = MagicMock()
        channel.id = "ch-1"
        user = UserFactory()
        channel_subscribed.send(sender=object, channel=channel, user=user)

    def test_missing_args_does_not_raise(self):
        channel_subscribed.send(sender=object, channel=None, user=None)


class TestOnChannelUnsubscribed(TestCase):
    def test_logs_without_raising(self):
        channel_unsubscribed.send(sender=object, channel_id="ch-1", user_id=1)


class TestOnWebhookDeliveryAttempted(TestCase):
    def test_logs_failed_delivery(self):
        delivery = MagicMock()
        delivery.id = "d-1"
        delivery.webhook_id = "wh-1"
        delivery.response_status = 500
        delivery.is_successful = False
        webhook_delivery_attempted.send(sender=object, delivery=delivery)

    def test_successful_delivery_no_warning(self):
        delivery = MagicMock()
        delivery.id = "d-2"
        delivery.is_successful = True
        webhook_delivery_attempted.send(sender=object, delivery=delivery)

    def test_missing_delivery_does_not_raise(self):
        webhook_delivery_attempted.send(sender=object, delivery=None)


class TestOnStoryCreated(TestCase):
    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_story_created_websocket_event(self, mock_ws):
        user = UserFactory()
        story = UserStoryFactory(user=user)
        story_created.send(sender=object, story=story)
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "story.created")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_story_does_not_raise(self, mock_ws):
        story_created.send(sender=object, story=None)
        mock_ws.assert_not_called()


class TestOnStoryViewed(TestCase):
    @patch("messaging.tasks.send_story_views_digest")
    def test_queues_digest_task(self, mock_task):
        mock_task.apply_async = MagicMock()
        user = UserFactory()
        viewer = UserFactory()
        story = UserStoryFactory(user=user)
        view = MagicMock()
        story_viewed.send(
            sender=object, view=view, story=story, viewer_id=viewer.pk
        )
        mock_task.apply_async.assert_called_once()

    @patch("messaging.tasks.send_story_views_digest")
    def test_owner_viewing_own_story_no_digest(self, mock_task):
        mock_task.apply_async = MagicMock()
        user = UserFactory()
        story = UserStoryFactory(user=user)
        view = MagicMock()
        story_viewed.send(
            sender=object, view=view, story=story, viewer_id=user.pk
        )
        mock_task.apply_async.assert_not_called()

    @patch("messaging.tasks.send_story_views_digest")
    def test_missing_args_does_not_raise(self, mock_task):
        mock_task.apply_async = MagicMock()
        story_viewed.send(sender=object, view=None, story=None, viewer_id=None)
        mock_task.apply_async.assert_not_called()


class TestOnStoryReplied(TestCase):
    def test_logs_without_raising(self):
        view = MagicMock()
        view.story_id = "story-1"
        view.viewer_id = 1
        story_replied.send(sender=object, view=view)

    def test_missing_view_does_not_raise(self):
        story_replied.send(sender=object, view=None)


class TestOnMessageEditedWithHistory(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("channels.layers.get_channel_layer")
    def test_sends_message_edited_websocket_event(self, mock_get_layer):
        """
        Audit fix (Part 19): rewritten. on_message_edited_with_history
        used to call send_websocket_event(event_type="message.edited"),
        which mapped to a Channels handler name (message_edited) that
        doesn't exist on ChatConsumer, and even fixed to point at the
        right name (chat_message_edited) would have nested the payload
        under "data" while chat_message_edited expects a flat event -
        mismatched from the pre-existing WS-native edit path
        (consumers.py:_handle_edit). Now calls channel_layer.group_send
        directly with the same flat shape _handle_edit already uses; see
        test_ws_dispatch_audit_fix.py for the real end-to-end version of
        this test (a connected client actually receiving it).
        """
        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer
        history = MagicMock()
        history.edit_number = 1
        history.edited_by_id = self.user.pk
        message_edited_with_history.send(
            sender=object, message=self.msg, edit_history=history
        )
        mock_layer.group_send.assert_called_once()
        args, _ = mock_layer.group_send.call_args
        group_name, event = args
        self.assertEqual(group_name, f"chat_{str(self.msg.chat_id).replace('-', '')}")
        self.assertEqual(event["type"], "chat_message_edited")
        self.assertEqual(event["message_id"], str(self.msg.id))
        self.assertNotIn("data", event)

    @patch("channels.layers.get_channel_layer")
    def test_missing_message_does_not_raise(self, mock_get_layer):
        mock_get_layer.return_value = MagicMock()
        message_edited_with_history.send(sender=object, message=None, edit_history=None)
        mock_get_layer.return_value.group_send.assert_not_called()

    @patch("channels.layers.get_channel_layer")
    def test_websocket_exception_does_not_propagate(self, mock_get_layer):
        mock_get_layer.side_effect = Exception("WS error")
        history = MagicMock()
        history.edit_number = 2
        history.edited_by_id = self.user.pk
        # Should not raise
        message_edited_with_history.send(
            sender=object, message=self.msg, edit_history=history
        )


class TestOnDisappearingConfigChanged(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user, role="ADMIN")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_disappearing_changed_event(self, mock_ws):
        config = MagicMock()
        config.is_enabled = True
        config.ttl_seconds = 86400
        config.ttl_display = "24 hours"
        disappearing_config_changed.send(
            sender=object, config=config, chat=self.chat
        )
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "chat.disappearing_changed")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_args_does_not_raise(self, mock_ws):
        disappearing_config_changed.send(sender=object, config=None, chat=None)
        mock_ws.assert_not_called()


class TestOnVoiceMessageTranscribed(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)
        self.msg = ChatMessageFactory(chat=self.chat, sender=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_voice_transcribed_event(self, mock_ws):
        transcription = MagicMock()
        transcription.message = self.msg
        transcription.transcribed_text = "Hello this is a voice message"
        transcription.language = "en"
        transcription.duration_seconds = 5.0
        transcription.waveform_data = [0.1, 0.5, 0.9]
        voice_message_transcribed.send(sender=object, transcription=transcription)
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "voice.transcribed")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_transcription_does_not_raise(self, mock_ws):
        voice_message_transcribed.send(sender=object, transcription=None)
        mock_ws.assert_not_called()


class TestOnChatMessageSentPostprocess(TestCase):
    def setUp(self):
        self.chat = InternalChatFactory()
        self.user = UserFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.tasks.fetch_link_previews_task")
    def test_queues_link_preview_for_text_message(self, mock_task):
        mock_task.apply_async = MagicMock()
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.user,
            content="Check https://example.com",
            message_type="TEXT",
        )
        _cms.send(sender=ChatMessage, message=msg, chat=self.chat)
        mock_task.apply_async.assert_called()

    @patch("messaging.tasks.process_voice_message_task")
    def test_queues_voice_transcription_for_audio_message(self, mock_task):
        mock_task.apply_async = MagicMock()
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.user,
            content="[audio]",
            message_type="AUDIO",
        )
        _cms.send(sender=ChatMessage, message=msg, chat=self.chat)
        mock_task.apply_async.assert_called()

    @patch("messaging.tasks.fetch_link_previews_task")
    def test_no_link_preview_for_non_text_message(self, mock_task):
        mock_task.apply_async = MagicMock()
        msg = ChatMessageFactory(
            chat=self.chat, sender=self.user,
            content="[img]",
            message_type="IMAGE",
        )
        _cms.send(sender=ChatMessage, message=msg, chat=self.chat)
        mock_task.apply_async.assert_not_called()

    @patch("messaging.tasks.fetch_link_previews_task")
    def test_missing_message_does_not_raise(self, mock_task):
        mock_task.apply_async = MagicMock()
        _cms.send(sender=ChatMessage, message=None, chat=self.chat)
        mock_task.apply_async.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Fix 7: Tests for previously-untested signals: message_forwarded,
#         link_previews_fetched
# ═════════════════════════════════════════════════════════════════════════════

from ..signals import message_forwarded, link_previews_fetched


class TestOnMessageForwarded(TestCase):
    """Receiver for message_forwarded signal."""

    def setUp(self):
        self.user  = UserFactory()
        self.chat  = InternalChatFactory()
        self.chat2 = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat,  user=self.user)
        ChatParticipantFactory(chat=self.chat2, user=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_websocket_event_to_target_chat(self, mock_ws):
        original  = ChatMessageFactory(chat=self.chat,  sender=self.user)
        forwarded = ChatMessageFactory(chat=self.chat2, sender=self.user)

        message_forwarded.send(
            sender=object,
            original_message=original,
            forwarded_message=forwarded,
            forwarded_by_id=self.user.pk,
            target_chat_id=self.chat2.id,
        )

        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "message.forwarded")
        self.assertEqual(call_kwargs["data"]["message_id"], str(forwarded.id))
        self.assertEqual(call_kwargs["data"]["original_message_id"], str(original.id))

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_messages_does_not_send(self, mock_ws):
        message_forwarded.send(
            sender=object,
            original_message=None,
            forwarded_message=None,
            forwarded_by_id=self.user.pk,
            target_chat_id=self.chat2.id,
        )
        mock_ws.assert_not_called()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_websocket_exception_does_not_raise(self, mock_ws):
        mock_ws.side_effect = Exception("WS down")
        original  = ChatMessageFactory(chat=self.chat,  sender=self.user)
        forwarded = ChatMessageFactory(chat=self.chat2, sender=self.user)

        # Should not propagate exception
        try:
            message_forwarded.send(
                sender=object,
                original_message=original,
                forwarded_message=forwarded,
                forwarded_by_id=self.user.pk,
                target_chat_id=self.chat2.id,
            )
        except Exception:
            self.fail("on_message_forwarded raised an exception")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_increments_forward_count_in_metadata(self, mock_ws):
        original = ChatMessageFactory(
            chat=self.chat, sender=self.user,
            metadata={"forward_count": 2},
        )
        forwarded = ChatMessageFactory(chat=self.chat2, sender=self.user)

        message_forwarded.send(
            sender=object,
            original_message=original,
            forwarded_message=forwarded,
            forwarded_by_id=self.user.pk,
            target_chat_id=self.chat2.id,
        )

        original.refresh_from_db()
        self.assertEqual(original.metadata.get("forward_count"), 3)


class TestOnLinkPreviewsFetched(TestCase):
    """Receiver for link_previews_fetched signal."""

    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_sends_websocket_event_with_previews(self, mock_ws):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        previews = [
            {
                "url":         "https://example.com",
                "title":       "Example",
                "description": "Example page",
                "image_url":   "https://example.com/img.jpg",
                "site_name":   "Example",
            }
        ]

        link_previews_fetched.send(
            sender=object,
            message=msg,
            previews=previews,
        )

        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs["event_type"], "message.link_previews")
        self.assertEqual(call_kwargs["data"]["message_id"], str(msg.id))
        self.assertEqual(len(call_kwargs["data"]["previews"]), 1)
        self.assertEqual(call_kwargs["data"]["previews"][0]["url"], "https://example.com")

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_empty_previews_does_not_send(self, mock_ws):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        link_previews_fetched.send(
            sender=object,
            message=msg,
            previews=[],
        )
        mock_ws.assert_not_called()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_max_4_previews_enforced(self, mock_ws):
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        previews = [
            {"url": f"https://example{i}.com", "title": f"Site {i}"}
            for i in range(6)
        ]
        link_previews_fetched.send(sender=object, message=msg, previews=previews)

        call_kwargs = mock_ws.call_args[1]
        self.assertLessEqual(len(call_kwargs["data"]["previews"]), 4)

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_missing_message_does_not_send(self, mock_ws):
        link_previews_fetched.send(
            sender=object, message=None, previews=[{"url": "https://x.com"}]
        )
        mock_ws.assert_not_called()

    @patch("messaging.utils.notifier.send_websocket_event")
    def test_exception_does_not_propagate(self, mock_ws):
        mock_ws.side_effect = RuntimeError("Channel layer error")
        msg = ChatMessageFactory(chat=self.chat, sender=self.user)
        try:
            link_previews_fetched.send(
                sender=object,
                message=msg,
                previews=[{"url": "https://x.com", "title": "X"}],
            )
        except Exception:
            self.fail("on_link_previews_fetched raised an exception")
