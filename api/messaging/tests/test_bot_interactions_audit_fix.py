"""
Tests for Part 20 (world-system audit): interactive bot components.

Covers the two things added in Part 20:
  1. BotConfig.trigger_type=SLASH_COMMAND matching + {arg0}/{arg1}/...
     substitution, and response_blocks rendering onto
     ChatMessage.interactive_blocks (services.process_bot_triggers).
  2. The click -> record -> react loop for those blocks
     (services.process_bot_interaction / BotInteractionView), including
     the tenant-isolation fix made alongside it: BotConfig matching in
     process_bot_triggers() is now scoped to the triggering message's own
     tenant (previously a "global" bot from one tenant would also fire in
     every other tenant's chats).
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from .factories import (
    UserFactory, InternalChatFactory, ChatParticipantFactory,
    ChatMessageFactory, BotConfigFactory,
)
from ..models import ChatMessage, BotConfig, BotInteraction, BotResponse
from .. import services
from ..exceptions import BotNotFoundError, ChatAccessDeniedError


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestSlashCommandTrigger(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

    def test_slash_command_matches_and_substitutes_args(self):
        BotConfigFactory(
            chat=self.chat,
            trigger_type="SLASHCMD",
            trigger_value="offer",
            response_template="Fetching offer {arg0} for {user_name}...",
        )
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="/offer 4471")

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 1)
        sent = responses[0].sent_message
        self.assertIn("4471", sent.content)
        self.assertEqual(sent.message_type, "BOT")

    def test_slash_command_does_not_match_without_leading_slash(self):
        BotConfigFactory(chat=self.chat, trigger_type="SLASHCMD", trigger_value="offer")
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="offer 4471")

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 0)

    def test_slash_command_does_not_match_different_command_name(self):
        BotConfigFactory(chat=self.chat, trigger_type="SLASHCMD", trigger_value="offer")
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="/help")

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 0)

    def test_response_blocks_rendered_onto_sent_message(self):
        BotConfigFactory(
            chat=self.chat,
            trigger_type="SLASHCMD",
            trigger_value="offer",
            response_template="Offer {arg0}",
            response_blocks=[
                {"type": "button", "action_id": "accept", "label": "Accept {arg0}", "value": "{arg0}"},
                {"type": "button", "action_id": "decline", "label": "Decline", "value": "no"},
            ],
        )
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="/offer 99")

        responses = services.process_bot_triggers(msg.id)

        blocks = responses[0].sent_message.interactive_blocks
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["action_id"], "accept")
        self.assertEqual(blocks[0]["label"], "Accept 99")
        self.assertEqual(blocks[0]["value"], "99")
        self.assertEqual(blocks[1]["label"], "Decline")  # no placeholder -> unchanged

    def test_keyword_bot_without_response_blocks_is_unaffected(self):
        """Backward compatibility: a plain KEYWORD bot with no response_blocks
        configured still sends a plain-text reply with empty interactive_blocks."""
        BotConfigFactory(chat=self.chat, trigger_type="KEYWORD", trigger_value="hello")
        msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="hello there")

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].sent_message.interactive_blocks, [])


class TestBotTriggerTenantIsolation(TestCase):
    """The tenant-isolation fix made alongside Part 20: a bot from tenant A
    must not fire on a message in tenant B's chat, including "global"
    (chat=None) bots."""

    def setUp(self):
        from ..tests._tenant_stub.models import Tenant
        self.tenant_a = Tenant.objects.create(name="tenant-a")
        self.tenant_b = Tenant.objects.create(name="tenant-b")
        self.user_b = UserFactory()
        self.chat_b = InternalChatFactory(tenant=self.tenant_b)
        ChatParticipantFactory(chat=self.chat_b, user=self.user_b)

    def test_global_bot_from_other_tenant_does_not_fire(self):
        # A "global" (chat=None) bot belonging to tenant A...
        BotConfigFactory(
            chat=None, tenant=self.tenant_a,
            trigger_type="ALWAYS", trigger_value="",
        )
        # ...must not respond to a message in tenant B's chat.
        msg = ChatMessageFactory(chat=self.chat_b, sender=self.user_b, content="hi", tenant=self.tenant_b)

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 0)

    def test_global_bot_from_same_tenant_still_fires(self):
        BotConfigFactory(
            chat=None, tenant=self.tenant_b,
            trigger_type="ALWAYS", trigger_value="",
        )
        msg = ChatMessageFactory(chat=self.chat_b, sender=self.user_b, content="hi", tenant=self.tenant_b)

        responses = services.process_bot_triggers(msg.id)

        self.assertEqual(len(responses), 1)


class TestBotInteractionService(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

        self.bot = BotConfigFactory(
            chat=self.chat, trigger_type="SLASHCMD", trigger_value="offer",
            response_template="You picked {value}",
        )
        trigger_msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="/offer 1")
        [self.bot_response] = services.process_bot_triggers(trigger_msg.id)
        self.bot_msg = self.bot_response.sent_message
        self.bot_msg.interactive_blocks = [
            {"type": "button", "action_id": "accept", "label": "Accept", "value": "yes"},
        ]
        self.bot_msg.save(update_fields=["interactive_blocks"])

    def test_click_records_interaction_and_sends_follow_up(self):
        interaction = services.process_bot_interaction(
            message_id=self.bot_msg.id, action_id="accept", value="yes", user_id=self.user.id,
        )

        self.assertEqual(interaction.action_id, "accept")
        self.assertIsNotNone(interaction.resulting_message)
        self.assertIn("yes", interaction.resulting_message.content)
        self.assertEqual(BotInteraction.objects.count(), 1)

    def test_reclick_updates_rather_than_duplicates(self):
        services.process_bot_interaction(
            message_id=self.bot_msg.id, action_id="accept", value="yes", user_id=self.user.id,
        )
        services.process_bot_interaction(
            message_id=self.bot_msg.id, action_id="accept", value="yes-again", user_id=self.user.id,
        )

        self.assertEqual(BotInteraction.objects.count(), 1)
        self.assertEqual(BotInteraction.objects.first().value, "yes-again")

    def test_non_participant_cannot_click(self):
        with self.assertRaises(ChatAccessDeniedError):
            services.process_bot_interaction(
                message_id=self.bot_msg.id, action_id="accept", value="yes",
                user_id=self.other_user.id,
            )

    def test_unknown_action_id_raises(self):
        with self.assertRaises(BotNotFoundError):
            services.process_bot_interaction(
                message_id=self.bot_msg.id, action_id="does-not-exist", value="",
                user_id=self.user.id,
            )


class TestBotInteractionView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.other_user = UserFactory()
        self.chat = InternalChatFactory()
        ChatParticipantFactory(chat=self.chat, user=self.user)

        BotConfigFactory(
            chat=self.chat, trigger_type="SLASHCMD", trigger_value="offer",
            response_template="Confirmed: {value}",
        )
        trigger_msg = ChatMessageFactory(chat=self.chat, sender=self.user, content="/offer 1")
        [resp] = services.process_bot_triggers(trigger_msg.id)
        self.bot_msg = resp.sent_message
        self.bot_msg.interactive_blocks = [
            {"type": "button", "action_id": "accept", "label": "Accept", "value": "yes"},
        ]
        self.bot_msg.save(update_fields=["interactive_blocks"])

    def test_post_interact_happy_path(self):
        resp = _api(self.user).post("/messaging/bots/interact/", {
            "message_id": str(self.bot_msg.id), "action_id": "accept", "value": "yes",
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["action_id"], "accept")
        self.assertIsNotNone(resp.data["resulting_message_id"])

    def test_post_interact_missing_fields_400(self):
        resp = _api(self.user).post("/messaging/bots/interact/", {"action_id": "accept"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_post_interact_requires_auth(self):
        resp = APIClient().post("/messaging/bots/interact/", {
            "message_id": str(self.bot_msg.id), "action_id": "accept",
        }, format="json")
        self.assertIn(resp.status_code, (401, 403))

    def test_post_interact_non_participant_rejected(self):
        resp = _api(self.other_user).post("/messaging/bots/interact/", {
            "message_id": str(self.bot_msg.id), "action_id": "accept",
        }, format="json")
        self.assertIn(resp.status_code, (400, 403))
