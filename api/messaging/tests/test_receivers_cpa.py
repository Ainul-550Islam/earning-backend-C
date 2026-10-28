"""
test_receivers_cpa.py
======================
Full coverage for messaging/receivers_cpa.py — all 13 CPA signal receivers.
Place in: messaging/tests/test_receivers_cpa.py
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock, call
from django.test import TestCase

from .factories import UserFactory
from ..signals_cpa import (
    offer_status_changed,
    new_offer_published,
    conversion_received,
    conversion_status_changed,
    postback_failed,
    payout_processed,
    payout_threshold_reached,
    payout_on_hold,
    affiliate_status_changed,
    manager_assigned,
    fraud_detected,
    milestone_reached,
    epc_dropped,
)


class TestOnOfferStatusChanged(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_offer_approved")
    def test_calls_notify_offer_approved(self, mock_fn):
        offer_status_changed.send(
            sender=object,
            offer_id="offer-1",
            offer_name="Super Offer",
            affiliate_id=self.affiliate.pk,
            new_status="approved",
            payout="$2.50",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_offer_rejected")
    def test_calls_notify_offer_rejected(self, mock_fn):
        offer_status_changed.send(
            sender=object,
            offer_id="offer-2",
            offer_name="Bad Offer",
            affiliate_id=self.affiliate.pk,
            new_status="rejected",
            reason="Low quality traffic",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_offer_paused")
    def test_calls_notify_offer_paused(self, mock_fn):
        offer_status_changed.send(
            sender=object,
            offer_id="offer-3",
            offer_name="Capped Offer",
            affiliate_id=self.affiliate.pk,
            new_status="paused",
            reason="Daily cap reached",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_offer_paused")
    def test_calls_notify_offer_paused_for_cap_reached(self, mock_fn):
        offer_status_changed.send(
            sender=object,
            offer_id="offer-4",
            offer_name="Capped Offer",
            affiliate_id=self.affiliate.pk,
            new_status="cap_reached",
            reason="",
            tenant=None,
        )
        mock_fn.assert_called_once()

    def test_missing_offer_id_does_not_raise(self):
        # Should return early without error
        offer_status_changed.send(
            sender=object,
            offer_id=None,
            offer_name="Offer",
            affiliate_id=self.affiliate.pk,
            new_status="approved",
        )

    def test_missing_affiliate_id_does_not_raise(self):
        offer_status_changed.send(
            sender=object,
            offer_id="o-1",
            offer_name="Offer",
            affiliate_id=None,
            new_status="approved",
        )

    @patch("messaging.services_cpa.notify_offer_approved")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("DB error")
        # Should swallow exception
        offer_status_changed.send(
            sender=object,
            offer_id="o-1",
            offer_name="Offer",
            affiliate_id=self.affiliate.pk,
            new_status="approved",
        )


class TestOnNewOfferPublished(TestCase):
    @patch("messaging.services_cpa.notify_new_offer_available")
    def test_calls_notify_new_offer_available(self, mock_fn):
        new_offer_published.send(
            sender=object,
            offer_id="offer-new",
            offer_name="Fresh Offer",
            vertical="gaming",
            payout="$1.50",
            countries=["US", "CA"],
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["offer_name"], "Fresh Offer")
        self.assertEqual(kwargs["vertical"], "gaming")

    @patch("messaging.services_cpa.notify_new_offer_available")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Service error")
        new_offer_published.send(
            sender=object, offer_id="o-1", offer_name="Offer",
            tenant=None,
        )


class TestOnConversionReceived(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_conversion_received")
    def test_calls_notify_conversion_received(self, mock_fn):
        conversion_received.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-1",
            offer_name="Gaming Offer",
            payout_amount="$2.50",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["payout_amount"], "$2.50")

    @patch("messaging.services_cpa.notify_conversion_received")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Notification error")
        conversion_received.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-2",
            offer_name="Offer",
            payout_amount="$1.00",
        )


class TestOnConversionStatusChanged(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_conversion_rejected")
    def test_calls_notify_conversion_rejected_for_rejected_status(self, mock_fn):
        conversion_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-3",
            offer_name="Offer",
            payout_amount="$2.00",
            new_status="rejected",
            reason="Fraud detected",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_conversion_rejected")
    def test_calls_notify_for_reversed_status(self, mock_fn):
        conversion_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-4",
            offer_name="Offer",
            payout_amount="$1.50",
            new_status="reversed",
            reason="",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_conversion_rejected")
    def test_calls_notify_for_chargeback_status(self, mock_fn):
        conversion_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-5",
            offer_name="Offer",
            payout_amount="$3.00",
            new_status="chargeback",
            reason="",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_conversion_rejected")
    def test_approved_status_does_not_call_rejected(self, mock_fn):
        conversion_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="conv-6",
            offer_name="Offer",
            payout_amount="$2.00",
            new_status="approved",
        )
        mock_fn.assert_not_called()

    @patch("messaging.services_cpa.notify_conversion_rejected")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("DB error")
        conversion_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            conversion_id="c-1",
            new_status="rejected",
        )


class TestOnPostbackFailed(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_postback_failed")
    def test_calls_notify_postback_failed(self, mock_fn):
        postback_failed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-1",
            offer_name="Postback Offer",
            error_detail="Connection refused",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["error_detail"], "Connection refused")

    @patch("messaging.services_cpa.notify_postback_failed")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Error")
        postback_failed.send(
            sender=object, affiliate_id=1, offer_id="o1", offer_name="O"
        )


class TestOnPayoutProcessed(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_payout_processed")
    def test_calls_notify_payout_processed(self, mock_fn):
        payout_processed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-1",
            amount="$250.00",
            payment_method="PayPal",
            transaction_id="txn-123",
            expected_date="2024-02-01",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["amount"], "$250.00")
        self.assertEqual(kwargs["payment_method"], "PayPal")

    @patch("messaging.services_cpa.notify_payout_processed")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Payment service down")
        payout_processed.send(
            sender=object, affiliate_id=1, payout_id="p-1",
            amount="$100", payment_method="wire",
        )


class TestOnPayoutThresholdReached(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_payout_threshold_met")
    def test_calls_notify_threshold_met(self, mock_fn):
        payout_threshold_reached.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            current_balance="$100.00",
            threshold="$50.00",
            next_payout_date="2024-02-15",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["current_balance"], "$100.00")
        self.assertEqual(kwargs["threshold"], "$50.00")

    @patch("messaging.services_cpa.notify_payout_threshold_met")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Error")
        payout_threshold_reached.send(
            sender=object, affiliate_id=1, current_balance="$50", threshold="$50"
        )


class TestOnPayoutOnHold(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_payout_on_hold")
    def test_calls_notify_payout_on_hold(self, mock_fn):
        payout_on_hold.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-hold-1",
            amount="$500.00",
            reason="Compliance review",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["reason"], "Compliance review")

    @patch("messaging.services_cpa.notify_payout_on_hold")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Error")
        payout_on_hold.send(
            sender=object, affiliate_id=1, payout_id="p-1", amount="$100"
        )


class TestOnAffiliateStatusChanged(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_affiliate_approved")
    def test_calls_notify_affiliate_approved(self, mock_fn):
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            affiliate_name="Alice Affiliate",
            new_status="approved",
            manager_name="Bob Manager",
            welcome_bonus="$10 bonus",
            tenant=None,
        )
        mock_fn.assert_called_once()

    @patch("messaging.services_cpa.notify_affiliate_suspended")
    def test_calls_notify_affiliate_suspended(self, mock_fn):
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            affiliate_name="Bad Actor",
            new_status="suspended",
            reason="Policy violation",
            duration="30 days",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["reason"], "Policy violation")

    @patch("messaging.services_cpa.notify_affiliate_suspended")
    def test_calls_notify_for_banned_status(self, mock_fn):
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            affiliate_name="Banned User",
            new_status="banned",
            reason="Fraud",
            tenant=None,
        )
        mock_fn.assert_called_once()

    def test_missing_affiliate_id_does_not_raise(self):
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=None,
            affiliate_name="Test",
            new_status="approved",
        )

    def test_missing_new_status_does_not_raise(self):
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            affiliate_name="Test",
            new_status=None,
        )

    @patch("messaging.services_cpa.notify_affiliate_approved")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Error")
        affiliate_status_changed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            affiliate_name="Test",
            new_status="approved",
        )


class TestOnManagerAssigned(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()
        self.manager = UserFactory(is_staff=True)

    @patch("messaging.services_cpa.notify_manager_assigned")
    def test_calls_notify_manager_assigned(self, mock_fn):
        manager_assigned.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Bob Manager",
            manager_email="bob@example.com",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["manager_name"], "Bob Manager")
        self.assertEqual(kwargs["manager_email"], "bob@example.com")

    @patch("messaging.services_cpa.notify_manager_assigned")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Assignment failed")
        manager_assigned.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            manager_id=self.manager.pk,
            manager_name="Manager",
        )


class TestOnFraudDetected(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_fraud_alert")
    def test_calls_notify_fraud_alert(self, mock_fn):
        fraud_detected.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-fraud",
            offer_name="Suspicious Offer",
            details="100% click-through rate detected",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["details"], "100% click-through rate detected")

    @patch("messaging.services_cpa.notify_fraud_alert")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Alert service down")
        fraud_detected.send(
            sender=object, affiliate_id=1, offer_id="o-1", offer_name="O"
        )


class TestOnMilestoneReached(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa.notify_milestone_reached")
    def test_calls_notify_milestone_reached(self, mock_fn):
        milestone_reached.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            milestone_type="first_conversion",
            milestone_value="First Conversion",
            reward="$5 bonus",
            tenant=None,
        )
        mock_fn.assert_called_once()
        kwargs = mock_fn.call_args[1]
        self.assertEqual(kwargs["milestone_type"], "first_conversion")
        self.assertEqual(kwargs["reward"], "$5 bonus")

    @patch("messaging.services_cpa.notify_milestone_reached")
    def test_exception_does_not_propagate(self, mock_fn):
        mock_fn.side_effect = Exception("Error")
        milestone_reached.send(
            sender=object, affiliate_id=1,
            milestone_type="custom", milestone_value="Test",
        )


class TestOnEpcDropped(TestCase):
    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa._create_notification")
    def test_creates_notification_for_large_drop(self, mock_create):
        epc_dropped.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-epc",
            offer_name="Dropping Offer",
            drop_percent=45,
            old_epc="$1.20",
            new_epc="$0.66",
            tenant=None,
        )
        mock_create.assert_called_once()
        kwargs = mock_create.call_args[1]
        self.assertEqual(kwargs["notification_type"], "epc.drop")
        self.assertIn("45", kwargs["body"])

    @patch("messaging.services_cpa._create_notification")
    def test_skips_small_drop_under_30_percent(self, mock_create):
        epc_dropped.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-epc",
            offer_name="Stable Offer",
            drop_percent=15,
            old_epc="$1.00",
            new_epc="$0.85",
            tenant=None,
        )
        mock_create.assert_not_called()

    @patch("messaging.services_cpa._create_notification")
    def test_exactly_30_percent_drop_is_skipped(self, mock_create):
        epc_dropped.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="o-1",
            offer_name="Offer",
            drop_percent=29,
        )
        mock_create.assert_not_called()

    @patch("messaging.services_cpa._create_notification")
    def test_exactly_30_percent_triggers_alert(self, mock_create):
        epc_dropped.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="o-1",
            offer_name="Offer",
            drop_percent=30,
        )
        mock_create.assert_called_once()

    @patch("messaging.services_cpa._create_notification")
    def test_exception_does_not_propagate(self, mock_create):
        mock_create.side_effect = Exception("Notification error")
        epc_dropped.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="o-1",
            offer_name="Offer",
            drop_percent=50,
        )


# ═════════════════════════════════════════════════════════════════════════════
# Fix 7: Tests for previously-untested CPA signals: offer_expiring_soon,
#         payout_failed
# ═════════════════════════════════════════════════════════════════════════════

from ..signals_cpa import offer_expiring_soon, payout_failed


class TestOnOfferExpiringSoon(TestCase):
    """Receiver for offer_expiring_soon signal."""

    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa._create_notification")
    def test_creates_expiry_notification(self, mock_notify):
        offer_expiring_soon.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-exp-1",
            offer_name="Hot Deal",
            hours_left=12,
            expires_at="2025-06-01T23:59:00Z",
            tenant=None,
        )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs["notification_type"], "offer.expiring_soon")
        self.assertIn("Hot Deal", call_kwargs["title"])
        self.assertIn("12", call_kwargs["body"])

    @patch("messaging.services_cpa._create_notification")
    def test_missing_affiliate_id_skips_notify(self, mock_notify):
        offer_expiring_soon.send(
            sender=object,
            affiliate_id=None,
            offer_id="offer-exp-2",
            offer_name="Deal",
            tenant=None,
        )
        mock_notify.assert_not_called()

    @patch("messaging.services_cpa._create_notification")
    def test_missing_offer_id_skips_notify(self, mock_notify):
        offer_expiring_soon.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id=None,
            offer_name="Deal",
            tenant=None,
        )
        mock_notify.assert_not_called()

    @patch("messaging.services_cpa._create_notification")
    def test_singular_hour_grammar(self, mock_notify):
        offer_expiring_soon.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-1",
            offer_name="Flash",
            hours_left=1,
            tenant=None,
        )
        call_kwargs = mock_notify.call_args[1]
        # "1 hour" not "1 hours"
        self.assertIn("1 hour", call_kwargs["body"])
        self.assertNotIn("1 hours", call_kwargs["body"])

    @patch("messaging.services_cpa._create_notification", side_effect=Exception("DB error"))
    def test_exception_does_not_propagate(self, mock_notify):
        try:
            offer_expiring_soon.send(
                sender=object,
                affiliate_id=self.affiliate.pk,
                offer_id="offer-1",
                offer_name="Deal",
                tenant=None,
            )
        except Exception:
            self.fail("on_offer_expiring_soon raised an exception")

    @patch("messaging.services_cpa._create_notification")
    def test_passes_offer_data_to_notification(self, mock_notify):
        offer_expiring_soon.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            offer_id="offer-xyz",
            offer_name="Premium Campaign",
            hours_left=6,
            expires_at="2025-06-02T06:00:00Z",
            tenant=None,
        )
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs["data"]["offer_id"], "offer-xyz")
        self.assertEqual(call_kwargs["data"]["hours_left"], 6)


class TestOnPayoutFailed(TestCase):
    """Receiver for payout_failed signal."""

    def setUp(self):
        self.affiliate = UserFactory()

    @patch("messaging.services_cpa._create_notification")
    def test_creates_payout_failed_notification(self, mock_notify):
        payout_failed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-001",
            amount="$150.00",
            reason="Invalid bank account details.",
            tenant=None,
        )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs["notification_type"], "payout.failed")
        self.assertEqual(call_kwargs["title"], "Payout Failed")
        self.assertIn("$150.00", call_kwargs["body"])
        self.assertIn("Invalid bank account details.", call_kwargs["body"])

    @patch("messaging.services_cpa._create_notification")
    def test_missing_affiliate_id_skips_notify(self, mock_notify):
        payout_failed.send(
            sender=object,
            affiliate_id=None,
            payout_id="payout-002",
            amount="$50.00",
            reason="Timeout",
            tenant=None,
        )
        mock_notify.assert_not_called()

    @patch("messaging.services_cpa._create_notification")
    def test_retry_at_included_in_body(self, mock_notify):
        payout_failed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-003",
            amount="$75.00",
            reason="System error.",
            retry_at="2025-06-03 09:00 UTC",
            tenant=None,
        )
        call_kwargs = mock_notify.call_args[1]
        self.assertIn("2025-06-03", call_kwargs["body"])

    @patch("messaging.services_cpa._create_notification")
    def test_no_retry_at_still_works(self, mock_notify):
        payout_failed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-004",
            amount="$20.00",
            reason="Compliance hold.",
            retry_at=None,
            tenant=None,
        )
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        self.assertIsNone(call_kwargs["data"]["retry_at"])

    @patch("messaging.services_cpa._create_notification", side_effect=Exception("notification service down"))
    def test_exception_does_not_propagate(self, mock_notify):
        try:
            payout_failed.send(
                sender=object,
                affiliate_id=self.affiliate.pk,
                payout_id="payout-005",
                amount="$10.00",
                reason="Unknown error.",
                tenant=None,
            )
        except Exception:
            self.fail("on_payout_failed raised an exception")

    @patch("messaging.services_cpa._create_notification")
    def test_payout_id_in_data(self, mock_notify):
        payout_failed.send(
            sender=object,
            affiliate_id=self.affiliate.pk,
            payout_id="payout-abc",
            amount="$500.00",
            reason="Fraud check failed.",
            tenant=None,
        )
        call_kwargs = mock_notify.call_args[1]
        self.assertEqual(call_kwargs["data"]["payout_id"], "payout-abc")
        self.assertEqual(call_kwargs["data"]["amount"], "$500.00")
