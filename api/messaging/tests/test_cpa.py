"""
CPA Messaging Service Tests — CPAlead-style notification system.
"""
from __future__ import annotations
from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import UserFactory, InternalChatFactory, ChatParticipantFactory
from ..models import CPANotification, CPABroadcast, MessageTemplate, AffiliateConversationThread
from .. import services_cpa


class TestCPAOfferNotifications(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_offer_approved(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_offer_approved(
            affiliate_id=self.affiliate.pk,
            offer_id=1,
            offer_name="Test Offer",
            offer_payout="$2.50",
        )
        self.assertEqual(notif.notification_type, "offer.approved")
        self.assertIn("Test Offer", notif.title)
        self.assertEqual(notif.recipient_id, self.affiliate.pk)
        self.assertEqual(notif.priority, "HIGH")
        mock_task.delay.assert_called_once()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_offer_rejected(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_offer_rejected(
            affiliate_id=self.affiliate.pk,
            offer_id=1,
            offer_name="Test Offer",
            reason="Traffic quality issues",
        )
        self.assertEqual(notif.notification_type, "offer.rejected")
        self.assertIn("Traffic quality issues", notif.body)


class TestCPAConversionNotifications(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_conversion_received(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_conversion_received(
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-001",
            offer_name="Gaming Offer",
            payout_amount="$5.00",
        )
        self.assertEqual(notif.notification_type, "conversion.received")
        self.assertEqual(notif.priority, "HIGH")
        self.assertIn("$5.00", notif.body)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_postback_failed(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_postback_failed(
            affiliate_id=self.affiliate.pk,
            offer_id=1,
            offer_name="Test Offer",
            error_detail="Connection timeout",
        )
        self.assertEqual(notif.notification_type, "postback.failed")
        self.assertEqual(notif.priority, "URGENT")


class TestCPAPayoutNotifications(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_payout_processed(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_payout_processed(
            affiliate_id=self.affiliate.pk,
            payout_id="pay-001",
            amount="$150.00",
            payment_method="PayPal",
            transaction_id="PP-12345",
        )
        self.assertEqual(notif.notification_type, "payout.processed")
        self.assertIn("$150.00", notif.title)
        self.assertIn("PayPal", notif.body)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_payout_on_hold(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_payout_on_hold(
            affiliate_id=self.affiliate.pk,
            payout_id="pay-002",
            amount="$200.00",
            reason="Fraud review",
        )
        self.assertEqual(notif.notification_type, "payout.hold")
        self.assertEqual(notif.priority, "URGENT")
        self.assertIn("Fraud review", notif.body)


class TestCPAAccountNotifications(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    @patch("messaging.services_cpa.get_or_create_affiliate_thread")
    def test_notify_affiliate_approved(self, mock_thread, mock_task):
        mock_task.delay = MagicMock()
        mock_thread.return_value = MagicMock()
        notif = services_cpa.notify_affiliate_approved(
            affiliate_id=self.affiliate.pk,
            affiliate_name="John Doe",
            manager_name="Jane Smith",
        )
        self.assertEqual(notif.notification_type, "affiliate.approved")
        self.assertIn("John Doe", notif.body)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_notify_fraud_alert(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_fraud_alert(
            affiliate_id=self.affiliate.pk,
            offer_id=1,
            offer_name="Gaming Offer",
            details="Bot traffic detected",
        )
        self.assertEqual(notif.notification_type, "fraud.alert")
        self.assertEqual(notif.priority, "URGENT")


class TestMessageTemplate(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)

    def test_create_template(self):
        t = services_cpa.create_template(
            name="Payout Processed",
            body="Hello {affiliate_name}, your payout of {amount} has been sent!",
            subject="Payment Sent: {amount}",
            category="payout",
            created_by_id=self.admin.pk,
        )
        self.assertEqual(t.name, "Payout Processed")
        self.assertEqual(t.category, "payout")

    def test_template_render(self):
        t = MessageTemplate.objects.create(
            name="Test",
            body="Hello {affiliate_name}, you earned {amount}!",
            subject="Welcome {affiliate_name}",
            category="custom",
        )
        subject, body = t.render({
            "affiliate_name": "John",
            "amount": "$100",
        })
        self.assertEqual(subject, "Welcome John")
        self.assertIn("John", body)
        self.assertIn("$100", body)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_send_from_template(self, mock_task):
        mock_task.delay = MagicMock()
        affiliate = UserFactory()
        t = MessageTemplate.objects.create(
            name="Welcome",
            body="Welcome {affiliate_name}!",
            subject="Welcome to the platform",
        )
        notif = services_cpa.send_from_template(
            template_id=str(t.id),
            recipient_id=affiliate.pk,
            context={"affiliate_name": "Jane"},
        )
        self.assertIn("Jane", notif.body)


class TestNotificationReadTracking(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_mark_notification_read(self, mock_task):
        mock_task.delay = MagicMock()
        notif = services_cpa.notify_milestone_reached(
            affiliate_id=self.affiliate.pk,
            milestone_type="first_conversion",
            milestone_value="First Conversion!",
        )
        self.assertFalse(notif.is_read)
        result = services_cpa.mark_notification_read(str(notif.id), self.affiliate.pk)
        self.assertTrue(result)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.read_at)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_mark_all_notifications_read(self, mock_task):
        mock_task.delay = MagicMock()
        for _ in range(3):
            services_cpa.notify_milestone_reached(
                affiliate_id=self.affiliate.pk,
                milestone_type="custom",
                milestone_value="Test",
            )
        count = services_cpa.mark_all_notifications_read(self.affiliate.pk)
        self.assertEqual(count, 3)
        unread = CPANotification.objects.filter(
            recipient=self.affiliate, is_read=False
        ).count()
        self.assertEqual(unread, 0)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_get_unread_counts_by_category(self, mock_task):
        mock_task.delay = MagicMock()
        services_cpa.notify_offer_approved(
            affiliate_id=self.affiliate.pk, offer_id=1, offer_name="Offer A"
        )
        services_cpa.notify_conversion_received(
            affiliate_id=self.affiliate.pk,
            conversion_id="c1", offer_name="Offer A", payout_amount="$1"
        )
        counts = services_cpa.get_unread_notification_counts(self.affiliate.pk)
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["offers"], 1)
        self.assertEqual(counts["conversions"], 1)


class TestAffiliateThread(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()
        self.manager   = UserFactory(is_staff=True)

    def test_get_or_create_thread(self):
        thread = services_cpa.get_or_create_affiliate_thread(
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
        )
        self.assertEqual(thread.affiliate_id, self.affiliate.pk)
        self.assertEqual(thread.manager_id, self.manager.pk)
        self.assertIsNotNone(thread.chat)

    def test_get_or_create_is_idempotent(self):
        t1 = services_cpa.get_or_create_affiliate_thread(
            affiliate_id=self.affiliate.pk, manager_id=self.manager.pk
        )
        t2 = services_cpa.get_or_create_affiliate_thread(
            affiliate_id=self.affiliate.pk, manager_id=self.manager.pk
        )
        self.assertEqual(str(t1.id), str(t2.id))

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_reassign_manager(self, mock_task):
        mock_task.delay = MagicMock()
        new_manager = UserFactory(is_staff=True)
        services_cpa.get_or_create_affiliate_thread(
            affiliate_id=self.affiliate.pk, manager_id=self.manager.pk
        )
        thread = services_cpa.reassign_affiliate_manager(
            affiliate_id=self.affiliate.pk,
            new_manager_id=new_manager.pk,
            notify=False,
        )
        self.assertEqual(thread.manager_id, new_manager.pk)


class TestBroadcastAnalytics(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        self.affiliate = UserFactory()

    @patch("messaging.tasks_cpa.send_cpa_broadcast_task")
    def test_create_broadcast(self, mock_task):
        mock_task.delay = MagicMock()
        broadcast = services_cpa.send_cpa_broadcast(
            title="Test Broadcast",
            body="Hello affiliates!",
            audience_filter="all",
            created_by_id=self.admin.pk,
        )
        self.assertIsNotNone(broadcast.id)
        mock_task.delay.assert_called_once()

    def test_track_broadcast_open(self):
        broadcast = CPABroadcast.objects.create(
            title="Test", body="Body",
            status="SENT", recipient_count=10,
        )
        result = services_cpa.track_broadcast_open(str(broadcast.id), self.affiliate.pk)
        self.assertTrue(result)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.opened_count, 1)
        # Second open should not increment
        result2 = services_cpa.track_broadcast_open(str(broadcast.id), self.affiliate.pk)
        self.assertFalse(result2)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.opened_count, 1)

    def test_track_broadcast_click(self):
        broadcast = CPABroadcast.objects.create(
            title="Test", body="Body",
            status="SENT", recipient_count=10,
        )
        from ..models import NotificationRead
        NotificationRead.objects.create(broadcast=broadcast, user=self.affiliate)
        result = services_cpa.track_broadcast_click(str(broadcast.id), self.affiliate.pk)
        self.assertTrue(result)
        broadcast.refresh_from_db()
        self.assertEqual(broadcast.clicked_count, 1)


class TestCPASignals(TestCase):
    """Test that CPA signals correctly trigger notifications."""

    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_offer_status_changed_signal_approved(self, mock_task):
        mock_task.delay = MagicMock()
        from ..signals_cpa import offer_status_changed
        offer_status_changed.send(
            sender=None,
            offer_id=1,
            offer_name="Test Offer",
            affiliate_id=self.affiliate.pk,
            new_status="approved",
            payout="$2.00",
        )
        notif = CPANotification.objects.filter(
            recipient=self.affiliate, notification_type="offer.approved"
        ).first()
        self.assertIsNotNone(notif)

    @patch("messaging.services_cpa.deliver_cpa_notification_task")
    def test_payout_processed_signal(self, mock_task):
        mock_task.delay = MagicMock()
        from ..signals_cpa import payout_processed
        payout_processed.send(
            sender=None,
            payout_id="pay-001",
            affiliate_id=self.affiliate.pk,
            amount="$100.00",
            payment_method="Wire",
        )
        notif = CPANotification.objects.filter(
            recipient=self.affiliate, notification_type="payout.processed"
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("$100.00", notif.title)
