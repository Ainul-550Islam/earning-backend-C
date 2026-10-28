"""
test_utils_offer_context.py
=============================
Tests for messaging/utils/offer_context.py against its ACTUAL public API:
  build_offer_card_message, build_stats_summary_message,
  build_payout_card_message, send_offer_recommendation_message

Place in: messaging/tests/test_utils_offer_context.py
"""
from __future__ import annotations
from unittest.mock import patch

from django.test import TestCase

from .factories import InternalChatFactory, UserFactory
from ..utils.offer_context import (
    build_offer_card_message,
    build_stats_summary_message,
    build_payout_card_message,
    send_offer_recommendation_message,
)


class TestBuildOfferCardMessage(TestCase):
    def test_builds_full_payload(self):
        payload = build_offer_card_message(
            offer_id=42, offer_name="Gaming App", payout="$3.00",
            vertical="gaming", countries=["US", "CA"],
            offer_url="https://x.com/o/42", preview_url="https://x.com/p/42",
            status="active", description="Top converting offer this week",
        )
        self.assertEqual(payload["type"], "offer_card")
        self.assertEqual(payload["offer_id"], "42")
        self.assertEqual(payload["offer_name"], "Gaming App")
        self.assertEqual(payload["payout"], "$3.00")
        self.assertEqual(payload["countries"], ["US", "CA"])
        self.assertEqual(payload["status"], "active")

    def test_defaults_for_optional_fields(self):
        payload = build_offer_card_message(offer_id=1, offer_name="x")
        self.assertEqual(payload["countries"], [])
        self.assertEqual(payload["payout"], "")
        self.assertEqual(payload["status"], "active")

    def test_truncates_long_description(self):
        payload = build_offer_card_message(
            offer_id=1, offer_name="x", description="y" * 500
        )
        self.assertEqual(len(payload["description"]), 300)

    def test_offer_id_coerced_to_string(self):
        payload = build_offer_card_message(offer_id=999, offer_name="x")
        self.assertEqual(payload["offer_id"], "999")
        self.assertIsInstance(payload["offer_id"], str)

    def test_none_description_does_not_raise(self):
        """
        Regression test (Part 6 audit): description[:300] previously
        crashed with TypeError when description=None. views_extra.py's
        OfferCardView calls offer.get("description", "") - a default that
        only applies when the key is missing, not when a client explicitly
        sends {"description": null}, which is an easy thing for a JS
        frontend to send for "no description".
        """
        payload = build_offer_card_message(offer_id=1, offer_name="x", description=None)
        self.assertEqual(payload["description"], "")


class TestBuildStatsSummaryMessage(TestCase):
    def test_builds_full_payload(self):
        payload = build_stats_summary_message(
            affiliate_id=7, period="this_week", clicks=500, conversions=20,
            revenue="$150.00", epc="$0.30", cr="4%",
        )
        self.assertEqual(payload["type"], "stats_summary")
        self.assertEqual(payload["affiliate_id"], "7")
        self.assertEqual(payload["period"], "this_week")
        self.assertEqual(payload["stats"]["clicks"], 500)
        self.assertEqual(payload["stats"]["conversions"], 20)
        self.assertEqual(payload["stats"]["revenue"], "$150.00")
        self.assertEqual(payload["stats"]["conversion_rate"], "4%")

    def test_defaults_to_zero_stats(self):
        payload = build_stats_summary_message(affiliate_id=7)
        self.assertEqual(payload["stats"]["clicks"], 0)
        self.assertEqual(payload["stats"]["conversions"], 0)
        self.assertEqual(payload["period"], "today")


class TestBuildPayoutCardMessage(TestCase):
    def test_builds_full_payload(self):
        payload = build_payout_card_message(
            payout_id=55, amount="$200.00", payment_method="PayPal",
            transaction_id="txn_abc", status="processed", period="June 2026",
        )
        self.assertEqual(payload["type"], "payout_card")
        self.assertEqual(payload["payout_id"], "55")
        self.assertEqual(payload["amount"], "$200.00")
        self.assertEqual(payload["payment_method"], "PayPal")
        self.assertEqual(payload["transaction_id"], "txn_abc")

    def test_defaults_to_processed_status(self):
        payload = build_payout_card_message(payout_id=1, amount="$10.00")
        self.assertEqual(payload["status"], "processed")
        self.assertEqual(payload["payment_method"], "")


class TestSendOfferRecommendationMessage(TestCase):
    def setUp(self):
        self.manager = UserFactory()
        self.affiliate = UserFactory()
        self.chat = InternalChatFactory()
        from ..models import ChatParticipant
        ChatParticipant.objects.create(chat=self.chat, user=self.manager)
        ChatParticipant.objects.create(chat=self.chat, user=self.affiliate)

    def test_sends_a_real_chat_message_with_offer_card_metadata(self):
        from ..models import ChatMessage
        send_offer_recommendation_message(
            chat_id=self.chat.id, manager_id=self.manager.pk,
            offer_id=42, offer_name="Gaming App", payout="$3.00",
            reason="High EPC this week",
        )
        msg = ChatMessage.objects.filter(chat=self.chat, sender=self.manager).first()
        self.assertIsNotNone(msg)
        self.assertIn("Gaming App", msg.content)
        self.assertEqual(msg.metadata["offer_card"]["offer_id"], "42")
        self.assertEqual(msg.metadata["offer_card"]["payout"], "$3.00")

    def test_includes_reason_in_message_content(self):
        from ..models import ChatMessage
        send_offer_recommendation_message(
            chat_id=self.chat.id, manager_id=self.manager.pk,
            offer_id=1, offer_name="App X", reason="Great conversion rate",
        )
        msg = ChatMessage.objects.filter(chat=self.chat, sender=self.manager).first()
        self.assertIn("Great conversion rate", msg.content)

    def test_does_not_raise_on_invalid_chat(self):
        # Defensive: the function logs and swallows errors rather than
        # propagating them, since it's typically called from a background
        # task / management workflow where a hard failure shouldn't crash
        # the caller.
        try:
            send_offer_recommendation_message(
                chat_id="00000000-0000-0000-0000-000000000000",
                manager_id=self.manager.pk, offer_id=1, offer_name="x",
            )
        except Exception as exc:
            self.fail(f"send_offer_recommendation_message raised unexpectedly: {exc}")

    @patch("messaging.services.send_chat_message")
    def test_does_not_pass_unsupported_tenant_kwarg(self, mock_send):
        # Regression guard: this previously passed tenant= straight through
        # to services.send_chat_message, which has no such parameter, so
        # every call raised TypeError (silently swallowed) and the feature
        # never actually sent anything.
        send_offer_recommendation_message(
            chat_id=self.chat.id, manager_id=self.manager.pk,
            offer_id=1, offer_name="x", tenant=object(),
        )
        mock_send.assert_called_once()
        self.assertNotIn("tenant", mock_send.call_args.kwargs)
