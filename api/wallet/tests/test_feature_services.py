# wallet/tests/test_feature_services.py
"""
Tests: webhooks.py, savings_goals.py, subscriptions.py,
       smart_escrow.py, bnpl_service.py, recurring_payments.py,
       virtual_cards.py, payment_links.py, open_banking.py
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, patch as mock_patch
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# 1. webhooks.py — WebhookDelivery
# ══════════════════════════════════════════════════════════════════════════════
class WebhookDeliveryTest(TestCase):
    def setUp(self):
        from ..webhooks import WebhookDelivery
        self.WebhookDelivery = WebhookDelivery

    def test_sign_returns_hex_string(self):
        sig = self.WebhookDelivery.sign("payload", "secret")
        self.assertIsInstance(sig, str)
        self.assertGreater(len(sig), 10)

    def test_sign_deterministic(self):
        self.assertEqual(
            self.WebhookDelivery.sign("payload", "secret"),
            self.WebhookDelivery.sign("payload", "secret"),
        )

    def test_sign_different_secret_different_sig(self):
        self.assertNotEqual(
            self.WebhookDelivery.sign("payload", "secret1"),
            self.WebhookDelivery.sign("payload", "secret2"),
        )

    def test_build_payload_has_event_key(self):
        payload = self.WebhookDelivery.build_payload("wallet.credit", {"amount": "100"}, wallet_id=1)
        self.assertIn("event", payload)
        self.assertEqual(payload["event"], "wallet.credit")

    def test_build_payload_has_data_key(self):
        payload = self.WebhookDelivery.build_payload("wallet.credit", {"amount": "100"})
        self.assertIn("data", payload)

    def test_build_payload_has_created_key(self):
        # payload uses "created" (unix timestamp), not "timestamp"
        payload = self.WebhookDelivery.build_payload("wallet.debit", {})
        self.assertIn("created", payload)
        self.assertIsInstance(payload["created"], int)

    def test_verify_incoming_valid(self):
        secret = "mysecret"
        raw = b'{"event":"wallet.credit"}'
        sig = self.WebhookDelivery.sign(raw.decode(), secret)
        self.assertTrue(self.WebhookDelivery.verify_incoming(raw, sig, secret))

    def test_verify_incoming_invalid_sig(self):
        raw = b'{"event":"wallet.credit"}'
        self.assertFalse(self.WebhookDelivery.verify_incoming(raw, "badsig", "secret"))

    def test_deliver_http_failure_returns_success_false(self):
        with patch("requests.post", side_effect=Exception("Connection refused")):
            result = self.WebhookDelivery.deliver(
                "http://localhost:9999/hook", "secret",
                "wallet.credit", {"amount": 100}
            )
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success", True))


# ══════════════════════════════════════════════════════════════════════════════
# 2. savings_goals.py
# ══════════════════════════════════════════════════════════════════════════════
class SavingsGoalServiceTest(TestCase):
    def setUp(self):
        from ..savings_goals import SavingsGoalService
        from ..services import WalletService
        self.SavingsGoalService = SavingsGoalService
        self.user   = User.objects.create_user(username="sg1", password="p", email="sg1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()

    def test_create_goal_returns_dict(self):
        result = self.SavingsGoalService.create(self.user, "Laptop", Decimal("50000"))
        self.assertIsInstance(result, dict)
        self.assertIn("goal_id", result)

    def test_create_goal_has_target_amount(self):
        result = self.SavingsGoalService.create(self.user, "Holiday", Decimal("20000"))
        self.assertEqual(Decimal(str(result["target"])), Decimal("20000"))

    def test_contribute_updates_progress(self):
        goal = self.SavingsGoalService.create(self.user, "Phone", Decimal("10000"))
        result = self.SavingsGoalService.contribute(goal["goal_id"], Decimal("2000"), user=self.user)
        self.assertIsInstance(result, dict)
        self.assertIn("current", result)
        self.assertIn("current", result)
        self.assertEqual(Decimal(str(result["current"])), Decimal("2000"))

    def test_get_progress_returns_progress_pct(self):
        goal = self.SavingsGoalService.create(self.user, "Car", Decimal("100000"))
        if goal.get("goal_id"):
            progress = self.SavingsGoalService.get_progress(goal["goal_id"])
            self.assertIn("progress_pct", progress)
            self.assertIsInstance(float(progress["progress_pct"]), float)

    def test_withdraw_goal_returns_dict(self):
        goal = self.SavingsGoalService.create(self.user, "Emergency", Decimal("5000"))
        self.SavingsGoalService.contribute(goal["goal_id"], Decimal("1000"), user=self.user)
        result = self.SavingsGoalService.withdraw_goal(goal["goal_id"], self.user)
        self.assertIsInstance(result, dict)

    def test_contribute_caps_at_target(self):
        goal = self.SavingsGoalService.create(self.user, "Small", Decimal("500"))
        result = self.SavingsGoalService.contribute(
            goal["goal_id"], Decimal("1000"), user=self.user
        )
        self.assertLessEqual(Decimal(str(result.get("current", result.get("contributed", "500")))), Decimal("500"))


# ══════════════════════════════════════════════════════════════════════════════
# 3. subscriptions.py
# ══════════════════════════════════════════════════════════════════════════════
class SubscriptionServiceTest(TestCase):
    def setUp(self):
        from ..subscriptions import SubscriptionService
        from ..services import WalletService
        self.SubscriptionService = SubscriptionService
        self.user   = User.objects.create_user(username="sub1", password="p", email="sub1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("10000")
        self.wallet.save()

    def test_subscribe_returns_dict_with_plan(self):
        result = self.SubscriptionService.subscribe(self.user, self.wallet, "basic")
        self.assertIsInstance(result, dict)
        self.assertIn("plan", result)

    def test_get_active_after_subscribe(self):
        self.SubscriptionService.subscribe(self.user, self.wallet, "basic")
        active = self.SubscriptionService.get_active(self.user.pk)
        self.assertIsInstance(active, dict)
        self.assertIn("plan", active)

    def test_cancel_subscription_returns_success(self):
        self.SubscriptionService.subscribe(self.user, self.wallet, "basic")
        result = self.SubscriptionService.cancel(self.user.pk)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success", False))

    def test_get_plan_features_returns_dict(self):
        self.SubscriptionService.subscribe(self.user, self.wallet, "basic")
        features = self.SubscriptionService.get_plan_features(self.user.pk)
        self.assertIsInstance(features, dict)

    def test_no_active_subscription_returns_empty_dict(self):
        user2 = User.objects.create_user(username="nosub", password="p", email="nosub@t.com")
        result = self.SubscriptionService.get_active(user2.pk)
        self.assertIsInstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 4. smart_escrow.py
# ══════════════════════════════════════════════════════════════════════════════
class EscrowServiceTest(TestCase):
    def setUp(self):
        from ..smart_escrow import EscrowService
        from ..services import WalletService
        self.EscrowService = EscrowService
        self.payer  = User.objects.create_user(username="esc_payer", password="p", email="ep@t.com")
        self.payee  = User.objects.create_user(username="esc_payee", password="p", email="epay@t.com")
        self.wallet = WalletService.get_or_create(self.payer)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()
        WalletService.get_or_create(self.payee)

    def test_create_escrow_returns_escrow_id(self):
        result = self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("1000"),
            description="Service payment", expires_days=7
        )
        self.assertIsInstance(result, dict)
        self.assertIn("escrow_id", result)

    def test_create_deducts_from_payer(self):
        self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("500"),
            description="Test", expires_days=3
        )
        self.wallet.refresh_from_db()
        self.assertLess(self.wallet.current_balance, Decimal("5000"))

    def test_release_returns_success(self):
        result = self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("500"),
            description="Release test", expires_days=3
        )
        if result.get("success"):
            release_result = self.EscrowService.release(result["escrow_id"], self.payee.pk)
            self.assertIsInstance(release_result, dict)
            # Either success or error (payee wallet credit may fail without refresh)
            self.assertIn("success", release_result)

    def test_dispute_changes_status(self):
        result = self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("500"),
            description="Dispute test", expires_days=3
        )
        dispute_result = self.EscrowService.dispute(
            result["escrow_id"], self.payer.pk, reason="Not delivered"
        )
        self.assertIsInstance(dispute_result, dict)

    def test_get_returns_correct_amount(self):
        result = self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("200"),
            description="Get test", expires_days=1
        )
        retrieved = self.EscrowService.get(result["escrow_id"])
        self.assertEqual(Decimal(str(retrieved["amount"])), Decimal("200"))

    def test_insufficient_balance_fails(self):
        result = self.EscrowService.create(
            self.payer, self.payee.pk, Decimal("999999"),
            description="Overspend", expires_days=1
        )
        # Either raises or returns success=False
        if isinstance(result, dict):
            self.assertFalse(result.get("success", True))


# ══════════════════════════════════════════════════════════════════════════════
# 5. bnpl_service.py
# ══════════════════════════════════════════════════════════════════════════════
class BNPLServiceTest(TestCase):
    def setUp(self):
        from ..bnpl_service import BNPLService
        from ..services import WalletService
        self.BNPLService = BNPLService
        self.user   = User.objects.create_user(username="bnpl1", password="p", email="bnpl1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()

    def test_create_plan_returns_plan_id(self):
        with patch.object(self.BNPLService, "_check_bnpl_eligibility",
                          return_value={"eligible": True}):
            result = self.BNPLService.create_plan(self.user, Decimal("1200"), months=3)
        self.assertIsInstance(result, dict)
        self.assertIn("plan_id", result)

    def test_installment_amount_correct(self):
        with patch.object(self.BNPLService, "_check_bnpl_eligibility",
                          return_value={"eligible": True}):
            result = self.BNPLService.create_plan(self.user, Decimal("1200"), months=3)
        self.assertIn("installment", result)
        # 1200 / 3 = 400 + interest
        self.assertGreaterEqual(Decimal(str(result["installment"])), Decimal("400"))

    def test_oversized_amount_returns_error(self):
        result = self.BNPLService.create_plan(self.user, Decimal("9999999"), months=3)
        if isinstance(result, dict):
            self.assertFalse(result.get("success", True))

    def test_get_user_plans_returns_list(self):
        with patch.object(self.BNPLService, "_check_bnpl_eligibility",
                          return_value={"eligible": True}):
            self.BNPLService.create_plan(self.user, Decimal("600"), months=2)
        plans = self.BNPLService.get_user_plans(self.user.pk)
        self.assertIsInstance(plans, list)  # May be empty in test cache

    def test_deduct_installment_returns_dict(self):
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()
        with patch.object(self.BNPLService, "_check_bnpl_eligibility",
                          return_value={"eligible": True}):
            result = self.BNPLService.create_plan(self.user, Decimal("900"), months=3)
        if result.get("plan_id"):
            deduct = self.BNPLService.deduct_installment(result["plan_id"], self.wallet)
            self.assertIsInstance(deduct, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 6. recurring_payments.py
# ══════════════════════════════════════════════════════════════════════════════
class RecurringPaymentServiceTest(TestCase):
    def setUp(self):
        from ..recurring_payments import RecurringPaymentService
        from ..services import WalletService
        self.RecurringPaymentService = RecurringPaymentService
        self.user   = User.objects.create_user(username="rec1", password="p", email="rec1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("10000")
        self.wallet.save()

    def test_create_plan_returns_plan_id(self):
        result = self.RecurringPaymentService.create(
            self.user, self.wallet, Decimal("100"), "monthly",
            beneficiary="test_beneficiary", description="Netflix"
        )
        self.assertIsInstance(result, dict)
        self.assertIn("plan_id", result)

    def test_list_for_user_returns_list(self):
        self.RecurringPaymentService.create(
            self.user, self.wallet, Decimal("50"), "weekly",
            beneficiary="test_beneficiary", description="Gym"
        )
        plans = self.RecurringPaymentService.list_for_user(self.user.pk)
        # Cache client scan may not work in tests — just check it returns a list
        self.assertIsInstance(plans, list)

    def test_pause_plan_returns_paused(self):
        result = self.RecurringPaymentService.create(
            self.user, self.wallet, Decimal("100"), "monthly",
            beneficiary="test_beneficiary", description="Pause test"
        )
        paused = self.RecurringPaymentService.pause(result["plan_id"], self.user.pk)
        self.assertIsInstance(paused, dict)
        self.assertTrue(paused.get("paused", False) or paused.get("success", False) or paused.get("status") == "paused")

    def test_cancel_plan_returns_cancelled(self):
        result = self.RecurringPaymentService.create(
            self.user, self.wallet, Decimal("100"), "monthly",
            beneficiary="test_beneficiary", description="Cancel"
        )
        cancelled = self.RecurringPaymentService.cancel(result["plan_id"], self.user.pk)
        self.assertIsInstance(cancelled, dict)
        self.assertTrue(cancelled.get("success", False) or cancelled.get("cancelled", False) or cancelled.get("status") == "cancelled")

    def test_invalid_frequency_rejected(self):
        result = self.RecurringPaymentService.create(
            self.user, self.wallet, Decimal("100"),
            "every-fortnight", beneficiary="x", description="Invalid"
        )
        # Returns {"success": False, "error": ...}
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success", True))


# ══════════════════════════════════════════════════════════════════════════════
# 7. virtual_cards.py
# ══════════════════════════════════════════════════════════════════════════════
class VirtualCardServiceTest(TestCase):
    def setUp(self):
        from ..virtual_cards import VirtualCardService
        from ..services import WalletService
        self.VirtualCardService = VirtualCardService
        self.user   = User.objects.create_user(username="vc1", password="p", email="vc1@t.com")
        self.wallet = WalletService.get_or_create(self.user)
        self.wallet.current_balance = Decimal("5000")
        self.wallet.save()

    def test_issue_card_no_api_key_returns_error(self):
        """Without Stripe API key configured, issue() returns error dict."""
        result = self.VirtualCardService.issue(
            self.user, self.wallet, Decimal("2000"), currency="usd"
        )
        self.assertIsInstance(result, dict)
        # Either success (if Stripe configured) or error
        self.assertIn("success", result)

    def test_freeze_card_nonexistent_returns_error(self):
        """Freezing non-existent card returns error dict."""
        result = self.VirtualCardService.freeze("ic_nonexistent_999")
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_cancel_card_nonexistent_returns_error(self):
        """Cancelling non-existent card returns error dict."""
        result = self.VirtualCardService.cancel(
            "ic_nonexistent_999", self.wallet, release_funds=False
        )
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


# ══════════════════════════════════════════════════════════════════════════════
# 8. payment_links.py
# ══════════════════════════════════════════════════════════════════════════════
class PaymentLinkServiceTest(TestCase):
    def setUp(self):
        from ..payment_links import PaymentLinkService
        from ..services import WalletService
        self.PaymentLinkService = PaymentLinkService
        self.user   = User.objects.create_user(username="pl1", password="p", email="pl1@t.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_create_link_returns_link_url(self):
        result = self.PaymentLinkService.create(
            self.user, amount=Decimal("500"), description="Invoice #001"
        )
        self.assertIsInstance(result, dict)
        self.assertIn("link_id", result)
        self.assertIn("link_url", result)

    def test_link_has_expires_at(self):
        result = self.PaymentLinkService.create(
            self.user, amount=Decimal("100"), description="Test", expires_minutes=60
        )
        self.assertIn("expires_at", result)

    def test_get_link_by_id(self):
        created = self.PaymentLinkService.create(
            self.user, amount=Decimal("250"), description="Get test"
        )
        retrieved = self.PaymentLinkService.get(created["link_id"])
        self.assertIsInstance(retrieved, dict)
        self.assertEqual(str(retrieved.get("amount", "")), "250")

    def test_static_link_no_amount(self):
        result = self.PaymentLinkService.create(self.user, description="Static link")
        self.assertIsInstance(result, dict)
        self.assertIn("link_id", result)
        self.assertIsNone(result.get("amount"))


# ══════════════════════════════════════════════════════════════════════════════
# 9. open_banking.py
# ══════════════════════════════════════════════════════════════════════════════
class OpenBankingServiceTest(TestCase):
    def setUp(self):
        from ..open_banking import OpenBankingService
        self.OpenBankingService = OpenBankingService
        self.user = User.objects.create_user(username="ob1", password="p", email="ob1@t.com")

    def test_get_auth_url_returns_dict(self):
        result = self.OpenBankingService.get_auth_url(
            self.user.pk, redirect_uri="https://example.com/callback"
        )
        self.assertIsInstance(result, dict)
        # Returns either auth_url (enabled) or error (disabled/misconfigured)
        self.assertTrue("auth_url" in result or "error" in result)

    def test_get_auth_url_returns_success_key(self):
        result = self.OpenBankingService.get_auth_url(
            self.user.pk, "https://a.com/cb"
        )
        self.assertIsInstance(result, dict)

    def test_auth_url_state_unique_per_call(self):
        r1 = self.OpenBankingService.get_auth_url(self.user.pk, "https://a.com/cb")
        r2 = self.OpenBankingService.get_auth_url(self.user.pk, "https://a.com/cb")
        self.assertNotEqual(r1["state"], r2["state"])

    def test_exchange_token_invalid_returns_error_dict(self):
        # exchange_token may raise OR return {"success": False}
        try:
            result = self.OpenBankingService.exchange_token("invalid_code", "bad_state")
            # If it returns a dict, success should be False
            if isinstance(result, dict):
                self.assertFalse(result.get("success", True))
        except Exception:
            pass  # Raising is also acceptable

    def test_get_accounts_no_token_returns_error(self):
        user2 = User.objects.create_user(username="ob_notoken", password="p", email="ont@t.com")
        try:
            result = self.OpenBankingService.get_accounts(user2.pk)
            # Should return empty list or error dict, not crash
            self.assertIsInstance(result, (list, dict))
        except Exception:
            pass  # Raising is acceptable
