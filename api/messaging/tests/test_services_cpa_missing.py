"""
test_services_cpa_missing.py
=============================
Tests for 7 uncovered services_cpa.py functions:
  notify_offer_paused, notify_new_offer_available,
  notify_conversion_rejected, notify_payout_threshold_met,
  notify_payout_pending_reminder, notify_affiliate_suspended,
  notify_manager_assigned

Plus 2 uncovered services.py functions:
  assign_support_thread, mark_inbox_items_read

Place in: messaging/tests/test_services_cpa_missing.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory
from ..models import (
    CPANotification,
    AffiliateConversationThread,
    SupportThread,
    UserInbox,
)
from ..services_cpa import (
    notify_offer_paused,
    notify_new_offer_available,
    notify_conversion_rejected,
    notify_payout_threshold_met,
    notify_payout_pending_reminder,
    notify_affiliate_suspended,
    notify_manager_assigned,
)
from .. import services


# ─────────────────────────────────────────────────────────────────────────────
# services_cpa.py — missing functions
# ─────────────────────────────────────────────────────────────────────────────

class TestNotifyOfferPaused(TestCase):
    def setUp(self):
        self.affiliate_a = UserFactory()
        self.affiliate_b = UserFactory()

    @patch("messaging.services_cpa._get_affiliates_running_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notifies_all_running_affiliates(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = [self.affiliate_a.pk, self.affiliate_b.pk]
        count = notify_offer_paused(
            offer_id="offer-paused",
            offer_name="Hot Gaming Offer",
            reason="Daily cap reached",
        )
        self.assertEqual(count, 2)
        self.assertEqual(
            CPANotification.objects.filter(
                notification_type="offer.paused"
            ).count(),
            2,
        )

    @patch("messaging.services_cpa._get_affiliates_running_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_contains_reason(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = [self.affiliate_a.pk]
        notify_offer_paused(
            offer_id="offer-2",
            offer_name="Paused Offer",
            reason="Manual pause by admin",
        )
        notif = CPANotification.objects.filter(
            recipient=self.affiliate_a,
            notification_type="offer.paused",
        ).first()
        self.assertIn("Manual pause by admin", notif.body)

    @patch("messaging.services_cpa._get_affiliates_running_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_returns_zero_when_no_affiliates(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = []
        count = notify_offer_paused(offer_id="o-1", offer_name="Empty Offer")
        self.assertEqual(count, 0)


class TestNotifyNewOfferAvailable(TestCase):
    def setUp(self):
        self.affiliate_a = UserFactory()
        self.affiliate_b = UserFactory()

    @patch("messaging.services_cpa._get_relevant_affiliates_for_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notifies_relevant_affiliates(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = [self.affiliate_a.pk, self.affiliate_b.pk]
        count = notify_new_offer_available(
            offer_id="offer-new",
            offer_name="Brand New Gaming Offer",
            vertical="gaming",
            payout="$2.50",
            countries=["US", "CA"],
        )
        self.assertEqual(count, 2)

    @patch("messaging.services_cpa._get_relevant_affiliates_for_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_contains_offer_details(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = [self.affiliate_a.pk]
        notify_new_offer_available(
            offer_id="offer-new-2",
            offer_name="Health Supplement Offer",
            vertical="health",
            payout="$5.00",
            countries=["GB"],
        )
        notif = CPANotification.objects.filter(
            recipient=self.affiliate_a,
            notification_type="offer.new",
        ).first()
        self.assertIn("Health Supplement Offer", notif.body)
        self.assertIn("$5.00", notif.body)

    @patch("messaging.services_cpa._get_relevant_affiliates_for_offer")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_returns_zero_when_no_relevant_affiliates(self, mock_task, mock_get_affiliates):
        mock_task.delay = MagicMock()
        mock_get_affiliates.return_value = []
        count = notify_new_offer_available(
            offer_id="o-niche", offer_name="Niche Offer",
            vertical="finance", countries=["JP"],
        )
        self.assertEqual(count, 0)


class TestNotifyConversionRejected(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_creates_rejection_notification(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_conversion_rejected(
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-reject-1",
            offer_name="Gaming Offer",
            payout_amount="$2.50",
            reason="Click fraud detected",
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.notification_type, "conversion.rejected")
        self.assertEqual(notif.recipient_id, self.affiliate.pk)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_contains_reason(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_conversion_rejected(
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-reject-2",
            offer_name="Finance Offer",
            payout_amount="$5.00",
            reason="Duplicate submission",
        )
        self.assertIn("Duplicate submission", notif.body)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_without_reason(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_conversion_rejected(
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-reject-3",
            offer_name="Offer",
            payout_amount="$1.00",
            reason="",
        )
        self.assertIsNotNone(notif)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_priority_is_high(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_conversion_rejected(
            affiliate_id=self.affiliate.pk,
            conversion_id="c-4",
            offer_name="O",
            payout_amount="$1",
        )
        self.assertEqual(notif.priority, "HIGH")


class TestNotifyPayoutThresholdMet(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_creates_threshold_notification(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_threshold_met(
            affiliate_id=self.affiliate.pk,
            current_balance="$100.00",
            threshold="$50.00",
            next_payout_date="2024-02-15",
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.notification_type, "payout.threshold")

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_mentions_balance_and_threshold(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_threshold_met(
            affiliate_id=self.affiliate.pk,
            current_balance="$150.00",
            threshold="$100.00",
        )
        self.assertIn("$150.00", notif.body)
        self.assertIn("$100.00", notif.body)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_next_payout_date_in_body_when_provided(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_threshold_met(
            affiliate_id=self.affiliate.pk,
            current_balance="$75.00",
            threshold="$50.00",
            next_payout_date="March 1, 2024",
        )
        self.assertIn("March 1, 2024", notif.body)


class TestNotifyPayoutPendingReminder(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_creates_reminder_notification(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_pending_reminder(
            affiliate_id=self.affiliate.pk,
            amount="$250.00",
            payout_date="2024-02-15",
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.notification_type, "payout.reminder")

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_notification_body_mentions_amount_and_date(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_pending_reminder(
            affiliate_id=self.affiliate.pk,
            amount="$500.00",
            payout_date="January 31, 2024",
        )
        self.assertIn("$500.00", notif.body)
        self.assertIn("January 31, 2024", notif.body)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_action_url_is_payment_methods(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_payout_pending_reminder(
            affiliate_id=self.affiliate.pk,
            amount="$100",
            payout_date="Tomorrow",
        )
        self.assertIn("payment", notif.action_url)


class TestNotifyAffiliateSuspended(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_creates_suspension_notification(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_affiliate_suspended(
            affiliate_id=self.affiliate.pk,
            reason="Policy violation",
            duration="30 days",
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.notification_type, "affiliate.suspended")

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_body_contains_reason(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_affiliate_suspended(
            affiliate_id=self.affiliate.pk,
            reason="Fraudulent traffic",
            duration="",
        )
        self.assertIn("Fraudulent traffic", notif.body)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_body_contains_duration(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_affiliate_suspended(
            affiliate_id=self.affiliate.pk,
            reason="",
            duration="Permanent",
        )
        self.assertIn("Permanent", notif.body)

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_priority_is_urgent(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_affiliate_suspended(
            affiliate_id=self.affiliate.pk,
            reason="Fraud",
        )
        self.assertEqual(notif.priority, "URGENT")

    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_appeal_url_in_action(self, mock_task):
        mock_task.delay = MagicMock()
        notif = notify_affiliate_suspended(
            affiliate_id=self.affiliate.pk,
            reason="Fraud",
            appeal_url="/appeal-form/",
        )
        self.assertIn("appeal", notif.action_url.lower())


class TestNotifyManagerAssigned(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()
        self.manager = UserFactory(is_staff=True)

    @patch("messaging.services_cpa._ensure_affiliate_manager_thread")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_creates_manager_assigned_notification(self, mock_task, mock_thread):
        mock_task.delay = MagicMock()
        notif = notify_manager_assigned(
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Bob Manager",
            manager_email="bob@example.com",
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.notification_type, "affiliate.manager")

    @patch("messaging.services_cpa._ensure_affiliate_manager_thread")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_body_contains_manager_name(self, mock_task, mock_thread):
        mock_task.delay = MagicMock()
        notif = notify_manager_assigned(
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Alice Manager",
        )
        self.assertIn("Alice Manager", notif.body)

    @patch("messaging.services_cpa._ensure_affiliate_manager_thread")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_body_contains_manager_email_when_provided(self, mock_task, mock_thread):
        mock_task.delay = MagicMock()
        notif = notify_manager_assigned(
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Carol Manager",
            manager_email="carol@example.com",
        )
        self.assertIn("carol@example.com", notif.body)

    @patch("messaging.services_cpa._ensure_affiliate_manager_thread")
    @patch("messaging.tasks_cpa.deliver_cpa_notification_task")
    def test_calls_ensure_thread(self, mock_task, mock_thread):
        mock_task.delay = MagicMock()
        notify_manager_assigned(
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Dave Manager",
        )
        mock_thread.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# services.py — 2 missing functions
# ─────────────────────────────────────────────────────────────────────────────

class TestAssignSupportThread(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.agent = UserFactory(is_staff=True)
        self.assigner = UserFactory(is_staff=True)
        self.thread = services.create_support_thread(
            user_id=self.user.pk,
            subject="Help with account",
            initial_message="I need help.",
        )

    def test_assigns_agent_to_thread(self):
        thread = services.assign_support_thread(
            thread_id=str(self.thread.id),
            agent_id=self.agent.pk,
            assigner_id=self.assigner.pk,
        )
        self.assertEqual(thread.assigned_agent_id, self.agent.pk)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.assigned_agent_id, self.agent.pk)

    def test_reassigns_to_different_agent(self):
        other_agent = UserFactory(is_staff=True)
        services.assign_support_thread(
            thread_id=str(self.thread.id),
            agent_id=self.agent.pk,
            assigner_id=self.assigner.pk,
        )
        thread = services.assign_support_thread(
            thread_id=str(self.thread.id),
            agent_id=other_agent.pk,
            assigner_id=self.assigner.pk,
        )
        self.assertEqual(thread.assigned_agent_id, other_agent.pk)

    def test_raises_for_nonexistent_thread(self):
        import uuid
        from ..exceptions import SupportThreadNotFoundError
        with self.assertRaises(SupportThreadNotFoundError):
            services.assign_support_thread(
                thread_id=str(uuid.uuid4()),
                agent_id=self.agent.pk,
                assigner_id=self.assigner.pk,
            )

    def test_raises_for_nonexistent_agent(self):
        from ..exceptions import UserNotFoundError
        with self.assertRaises(UserNotFoundError):
            services.assign_support_thread(
                thread_id=str(self.thread.id),
                agent_id=99999999,
                assigner_id=self.assigner.pk,
            )


class TestMarkInboxItemsRead(TestCase):
    def setUp(self):
        self.user = UserFactory()
        import uuid
        self.items = [
            UserInbox.objects.create(
                user=self.user,
                item_type="CHAT_MESSAGE",
                source_id=str(uuid.uuid4()),
                title=f"Message {i}",
                preview="preview",
                is_read=False,
                is_archived=False,
            )
            for i in range(5)
        ]

    def test_marks_all_unread_as_read_when_no_ids_specified(self):
        count = services.mark_inbox_items_read(user_id=self.user.pk)
        self.assertEqual(count, 5)
        self.assertEqual(
            UserInbox.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_marks_only_specified_items(self):
        ids = [self.items[0].id, self.items[1].id]
        count = services.mark_inbox_items_read(user_id=self.user.pk, item_ids=ids)
        self.assertEqual(count, 2)
        self.assertEqual(
            UserInbox.objects.filter(user=self.user, is_read=False).count(), 3
        )

    def test_does_not_affect_already_read_items(self):
        from django.utils import timezone as _tz
        UserInbox.objects.filter(user=self.user).update(
            is_read=True, read_at=_tz.now()
        )
        count = services.mark_inbox_items_read(user_id=self.user.pk)
        self.assertEqual(count, 0)

    def test_does_not_affect_other_users_items(self):
        other = UserFactory()
        import uuid
        other_item = UserInbox.objects.create(
            user=other,
            item_type="SYSTEM",
            source_id=str(uuid.uuid4()),
            title="Other",
            preview="",
            is_read=False,
        )
        services.mark_inbox_items_read(user_id=self.user.pk)
        other_item.refresh_from_db()
        self.assertFalse(other_item.is_read)

    def test_returns_zero_when_no_unread_items(self):
        from django.utils import timezone as _tz
        UserInbox.objects.filter(user=self.user).update(
            is_read=True, read_at=_tz.now()
        )
        count = services.mark_inbox_items_read(user_id=self.user.pk)
        self.assertEqual(count, 0)


# ─────────────────────────────────────────────────────────────────────────────
# tasks_cpa.py — send_payout_reminders
# ─────────────────────────────────────────────────────────────────────────────

class TestSendPayoutReminders(TestCase):
    def test_runs_without_raising(self):
        """
        send_payout_reminders is a stub that integrates with the payout model.
        It should run without error and return a dict with 'sent' and 'date'.
        """
        from ..tasks_cpa import send_payout_reminders
        result = send_payout_reminders()
        self.assertIn("sent", result)
        self.assertIn("date", result)
        # Stub returns 0 until integrated with payout model
        self.assertIsInstance(result["sent"], int)


# ─────────────────────────────────────────────────────────────────────────────
# services_cpa.py — _resolve_cpa_broadcast_audience and its per-filter helpers
# (BY_VERTICAL / BY_COUNTRY / BY_TIER / BY_MANAGER / NEW_AFFILIATES paths were
# previously only exercised via the ALL_AFFILIATES default in other tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveCpaBroadcastAudience(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    def _broadcast(self, audience_filter, audience_params=None):
        from ..models import CPABroadcast
        return CPABroadcast.objects.create(
            title="x", body="y",
            audience_filter=audience_filter,
            audience_params=audience_params or {},
        )

    def test_by_vertical_returns_active_users(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("by_vertical", {"vertical": "finance"})
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)

    def test_by_country_returns_active_users(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("by_country", {"country": "BD"})
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)

    def test_by_tier_returns_active_users(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("by_tier", {"tier": "gold"})
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)

    def test_by_manager_returns_assigned_affiliates(self):
        from .. import services as msg_services
        from ..services_cpa import _resolve_cpa_broadcast_audience
        manager = UserFactory(is_staff=True)
        chat = msg_services.create_group_chat(
            creator_id=self.affiliate.pk, name="thread", member_ids=[]
        )
        AffiliateConversationThread.objects.create(
            affiliate=self.affiliate, manager=manager, chat=chat,
        )
        b = self._broadcast("by_manager", {"manager_id": manager.pk})
        result = _resolve_cpa_broadcast_audience(b)
        self.assertEqual(list(result), [self.affiliate.pk])

    def test_by_manager_without_manager_id_falls_back_to_all_affiliates(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("by_manager", {})
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)

    def test_new_affiliates_returns_recently_joined(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("new")
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)

    def test_unknown_filter_falls_back_to_all_affiliates(self):
        from ..services_cpa import _resolve_cpa_broadcast_audience
        b = self._broadcast("something_unrecognised")
        result = _resolve_cpa_broadcast_audience(b)
        self.assertIn(self.affiliate.pk, result)


class TestGetAffiliateManagerId(TestCase):
    def test_returns_manager_from_thread(self):
        from .. import services as msg_services
        from ..services_cpa import _get_affiliate_manager_id
        affiliate = UserFactory()
        manager = UserFactory(is_staff=True)
        chat = msg_services.create_group_chat(
            creator_id=affiliate.pk, name="thread2", member_ids=[]
        )
        AffiliateConversationThread.objects.create(
            affiliate=affiliate, manager=manager, chat=chat,
        )
        self.assertEqual(_get_affiliate_manager_id(affiliate.pk), manager.pk)

    def test_returns_none_when_no_thread_and_no_staff(self):
        from ..services_cpa import _get_affiliate_manager_id
        affiliate = UserFactory()
        self.assertIsNone(_get_affiliate_manager_id(affiliate.pk))
