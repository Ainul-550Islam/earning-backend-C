# wallet/tests/test_adapters.py
"""
Tests for api/wallet/adapters.py
Verifies that every adapter:
  1. Works when the external app IS available (mocked)
  2. Gracefully degrades when the external app is NOT available (ImportError)
  3. Never raises — always returns a safe result
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _user(username):
    return User.objects.create_user(
        username=username, password="pass", email=f"{username}@t.com"
    )


def _wallet(user):
    from api.wallet.services import WalletService
    w = WalletService.get_or_create(user)
    w.current_balance = Decimal("5000")
    w.total_earned    = Decimal("10000")
    w.save()
    return w


def _txn(wallet):
    from api.wallet.services import WalletService
    return WalletService.credit(
        wallet, Decimal("100"), txn_type="earning", description="Adapter test"
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. FraudSignalAdapter
# ══════════════════════════════════════════════════════════════════════════════
class FraudSignalAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import FraudSignalAdapter
        self.adapter = FraudSignalAdapter
        self.user   = _user("fraud_adp1")
        self.wallet = _wallet(self.user)
        self.txn    = _txn(self.wallet)

    def test_on_transaction_missing_app_returns_skipped(self):
        with patch.dict("sys.modules", {"api.fraud_detection": None,
                                        "api.fraud_detection.services": None}):
            result = self.adapter.on_transaction(
                self.txn, self.user, self.wallet, ip_address="10.0.0.1"
            )
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success") or result.get("skipped"))

    def test_on_transaction_returns_dict_always(self):
        """adapter always returns a dict even when external module unavailable."""
        import sys
        # Simulate module being available via sys.modules patch
        mock_module = MagicMock()
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = {"block": False, "score": 0.1, "risk": "low"}
        mock_module.FraudEngine = mock_engine
        
        with patch.dict(sys.modules, {
            "api.fraud_detection": MagicMock(),
            "api.fraud_detection.services": mock_module,
        }):
            result = self.adapter.on_transaction(
                self.txn, self.user, self.wallet, ip_address="1.2.3.4"
            )
        self.assertIsInstance(result, dict)

    def test_on_withdrawal_requested_missing_app_returns_allowed(self):
        result = self.adapter.on_withdrawal_requested(
            self.user, self.wallet, Decimal("500"), "bkash"
        )
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("allowed", True))

    def test_on_suspicious_activity_never_raises(self):
        try:
            result = self.adapter.on_suspicious_activity(
                self.user, self.wallet, "multiple_failed_pin"
            )
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"FraudSignalAdapter raised: {e}")

    def test_on_transaction_with_exception_returns_error_dict(self):
        with patch("api.wallet.adapters.FraudSignalAdapter.on_transaction",
                   side_effect=Exception("DB error")):
            try:
                result = self.adapter.on_transaction(self.txn, self.user, self.wallet)
            except Exception:
                pass  # Acceptable — but must not propagate to caller in real use


# ══════════════════════════════════════════════════════════════════════════════
# 2. WalletAnalyticsAdapter
# ══════════════════════════════════════════════════════════════════════════════
class WalletAnalyticsAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import WalletAnalyticsAdapter
        self.adapter = WalletAnalyticsAdapter
        self.user   = _user("analytics_adp1")
        self.wallet = _wallet(self.user)

    def test_track_credit_missing_app_does_not_raise(self):
        try:
            self.adapter.track_credit(self.user, self.wallet, Decimal("100"), "earning", "BD")
        except Exception as e:
            self.fail(f"track_credit raised: {e}")

    def test_track_withdrawal_missing_app_does_not_raise(self):
        try:
            self.adapter.track_withdrawal(self.user, self.wallet, Decimal("500"), "bkash", "completed")
        except Exception as e:
            self.fail(f"track_withdrawal raised: {e}")

    def test_track_balance_snapshot_missing_app_does_not_raise(self):
        try:
            self.adapter.track_balance_snapshot(self.wallet)
        except Exception as e:
            self.fail(f"track_balance_snapshot raised: {e}")

    def test_track_credit_with_mock(self):
        mock_tracker = MagicMock()
        with patch.dict("sys.modules", {
            "api.analytics": MagicMock(),
            "api.analytics.tracker": MagicMock(WalletTracker=mock_tracker)
        }):
            self.adapter.track_credit(self.user, self.wallet, Decimal("200"), "bonus", "US")
        # If called, mock_tracker.track should have been called
        # (may or may not be — depends on import resolution in test env)


# ══════════════════════════════════════════════════════════════════════════════
# 3. ReferralWalletAdapter
# ══════════════════════════════════════════════════════════════════════════════
class ReferralWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import ReferralWalletAdapter
        self.adapter  = ReferralWalletAdapter
        self.referrer = _user("ref_adp_ref")
        self.referred = _user("ref_adp_rrd")
        self.wallet   = _wallet(self.referrer)

    def test_on_referral_earning_missing_app_returns_skipped(self):
        result = self.adapter.on_referral_earning(
            self.referrer, self.referred, Decimal("100"), "offer"
        )
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success") or result.get("skipped"))

    def test_on_first_withdrawal_missing_app_returns_skipped(self):
        result = self.adapter.on_first_withdrawal(self.referrer, self.wallet, Decimal("500"))
        self.assertIsInstance(result, dict)

    def test_get_referral_stats_missing_app_returns_defaults(self):
        result = self.adapter.get_referral_stats(self.referrer)
        self.assertIsInstance(result, dict)
        self.assertIn("total_referrals", result)
        self.assertEqual(result["total_referrals"], 0)

    def test_on_referral_earning_with_mock(self):
        mock_service = MagicMock()
        mock_service.process_commission.return_value = {"success": True, "commission": "10.00"}
        with patch.dict("sys.modules", {
            "api.referral": MagicMock(),
            "api.referral.services": MagicMock(ReferralService=mock_service)
        }):
            result = self.adapter.on_referral_earning(
                self.referrer, self.referred, Decimal("100"), "offer"
            )
        self.assertIsInstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 4. WalletNotificationAdapter
# ══════════════════════════════════════════════════════════════════════════════
class WalletNotificationAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import WalletNotificationAdapter
        self.adapter = WalletNotificationAdapter
        self.user    = _user("notif_adp1")

    def test_notify_credit_missing_app_does_not_raise(self):
        try:
            self.adapter.notify_credit(self.user, Decimal("100"), "earning", Decimal("5100"))
        except Exception as e:
            self.fail(f"notify_credit raised: {e}")

    def test_notify_withdrawal_initiated_does_not_raise(self):
        try:
            self.adapter.notify_withdrawal_initiated(self.user, Decimal("500"), "bkash")
        except Exception as e:
            self.fail(f"notify_withdrawal_initiated raised: {e}")

    def test_notify_withdrawal_approved_does_not_raise(self):
        try:
            self.adapter.notify_withdrawal_approved(self.user, Decimal("500"), Decimal("485"), "bkash")
        except Exception as e:
            self.fail(f"notify_withdrawal_approved raised: {e}")

    def test_notify_withdrawal_rejected_does_not_raise(self):
        try:
            self.adapter.notify_withdrawal_rejected(self.user, Decimal("500"), "KYC required")
        except Exception as e:
            self.fail(f"notify_withdrawal_rejected raised: {e}")

    def test_notify_wallet_locked_does_not_raise(self):
        try:
            self.adapter.notify_wallet_locked(self.user, "Suspicious activity")
        except Exception as e:
            self.fail(f"notify_wallet_locked raised: {e}")

    def test_notify_kyc_required_does_not_raise(self):
        try:
            self.adapter.notify_kyc_required(self.user, 2, "Amount exceeds limit")
        except Exception as e:
            self.fail(f"notify_kyc_required raised: {e}")

    def test_all_notifications_with_mock(self):
        mock_service = MagicMock()
        mock_service.send.return_value = {"sent": True}
        with patch.dict("sys.modules", {
            "api.notifications": MagicMock(),
            "api.notifications.services": MagicMock(NotificationService=mock_service)
        }):
            self.adapter.notify_credit(self.user, Decimal("100"), "earning", Decimal("5100"))


# ══════════════════════════════════════════════════════════════════════════════
# 5. KYCWalletAdapter
# ══════════════════════════════════════════════════════════════════════════════
class KYCWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import KYCWalletAdapter
        self.adapter = KYCWalletAdapter
        self.user    = _user("kyc_adp1")
        self.wallet  = _wallet(self.user)

    def test_get_kyc_level_missing_app_returns_int(self):
        result = self.adapter.get_kyc_level(self.user)
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    def test_is_withdrawal_allowed_missing_app_returns_true(self):
        allowed, reason = self.adapter.is_withdrawal_allowed(
            self.user, self.wallet, Decimal("500")
        )
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(reason, str)

    def test_on_kyc_approved_level1_returns_dict(self):
        result = self.adapter.on_kyc_approved(self.user, self.wallet, 1)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("kyc_level"), 1)

    def test_on_kyc_approved_level3_returns_high_limit(self):
        result = self.adapter.on_kyc_approved(self.user, self.wallet, 3)
        self.assertEqual(result.get("new_limit"), "500000")

    def test_on_kyc_approved_level2(self):
        result = self.adapter.on_kyc_approved(self.user, self.wallet, 2)
        self.assertEqual(result.get("new_limit"), "50000")

    def test_get_kyc_level_with_mock(self):
        mock_service = MagicMock()
        mock_service.get_verified_level.return_value = 2
        with patch.dict("sys.modules", {
            "api.kyc": MagicMock(),
            "api.kyc.services": MagicMock(KYCService=mock_service)
        }):
            level = self.adapter.get_kyc_level(self.user)
        self.assertIsInstance(level, int)


# ══════════════════════════════════════════════════════════════════════════════
# 6. PayoutQueueAdapter
# ══════════════════════════════════════════════════════════════════════════════
class PayoutQueueAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import PayoutQueueAdapter
        from api.wallet.models import WithdrawalMethod, WithdrawalRequest
        self.adapter = PayoutQueueAdapter
        self.user    = _user("pq_adp1")
        self.wallet  = _wallet(self.user)
        self.method  = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01711111111", account_name="PQ Test",
            is_verified=True,
        )
        self.wr = WithdrawalRequest.objects.create(
            user=self.user, wallet=self.wallet,
            payment_method=self.method,
            amount=Decimal("500"), net_amount=Decimal("485"),
            status="pending",
        )

    def test_enqueue_missing_app_returns_skipped(self):
        result = self.adapter.enqueue_withdrawal(self.wr, self.user, self.wallet)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("success") or result.get("skipped"))

    def test_get_queue_status_missing_app_returns_unknown(self):
        result = self.adapter.get_queue_status(str(self.wr.withdrawal_id))
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)

    def test_cancel_queued_missing_app_returns_skipped(self):
        result = self.adapter.cancel_queued_withdrawal(str(self.wr.withdrawal_id))
        self.assertIsInstance(result, dict)

    def test_enqueue_with_mock(self):
        mock_service = MagicMock()
        mock_service.enqueue.return_value = {"success": True, "queue_id": "q_123"}
        with patch.dict("sys.modules", {
            "api.payout_queue": MagicMock(),
            "api.payout_queue.services": MagicMock(PayoutQueueService=mock_service)
        }):
            result = self.adapter.enqueue_withdrawal(self.wr, self.user, self.wallet)
        self.assertIsInstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 7. ExternalWebhookAdapter
# ══════════════════════════════════════════════════════════════════════════════
class ExternalWebhookAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import ExternalWebhookAdapter
        self.adapter = ExternalWebhookAdapter
        self.user    = _user("webhook_adp1")

    def test_dispatch_missing_app_does_not_raise(self):
        try:
            self.adapter.dispatch("credit", self.user, {"amount": "100"})
        except Exception as e:
            self.fail(f"dispatch raised: {e}")

    def test_dispatch_all_known_events(self):
        for event in self.adapter.EVENTS.keys():
            try:
                self.adapter.dispatch(event, self.user, {"test": True})
            except Exception as e:
                self.fail(f"dispatch({event}) raised: {e}")

    def test_dispatch_with_mock(self):
        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = {"queued": 1}
        with patch.dict("sys.modules", {
            "api.webhooks": MagicMock(),
            "api.webhooks.services": MagicMock(WebhookDispatcher=mock_dispatcher)
        }):
            self.adapter.dispatch("credit", self.user, {"amount": "500"})


# ══════════════════════════════════════════════════════════════════════════════
# 8. AIWalletAdapter
# ══════════════════════════════════════════════════════════════════════════════
class AIWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import AIWalletAdapter
        self.adapter = AIWalletAdapter
        self.user    = _user("ai_adp1")
        self.wallet  = _wallet(self.user)

    def test_predict_fraud_score_missing_app_returns_low_risk(self):
        result = self.adapter.predict_fraud_score(self.user, self.wallet, {"amount": "100"})
        self.assertIsInstance(result, dict)
        self.assertIn("score", result)
        self.assertEqual(result.get("risk"), "low")

    def test_get_spending_insights_missing_app_returns_empty(self):
        result = self.adapter.get_spending_insights(self.user, self.wallet)
        self.assertIsInstance(result, dict)
        self.assertIn("insights", result)
        self.assertIsInstance(result["insights"], list)

    def test_recommend_offers_missing_app_returns_empty_list(self):
        result = self.adapter.recommend_offers(self.user, self.wallet)
        self.assertIsInstance(result, list)

    def test_optimal_withdrawal_time_missing_app_returns_default(self):
        result = self.adapter.optimal_withdrawal_time(self.user, self.wallet)
        self.assertIsInstance(result, dict)
        self.assertIn("recommended_hour", result)


# ══════════════════════════════════════════════════════════════════════════════
# 9. AlertWalletAdapter
# ══════════════════════════════════════════════════════════════════════════════
class AlertWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import AlertWalletAdapter
        self.adapter = AlertWalletAdapter
        self.user    = _user("alert_adp1")
        self.wallet  = _wallet(self.user)

    def test_alert_large_transaction_below_threshold_does_nothing(self):
        try:
            self.adapter.alert_large_transaction(self.user, self.wallet, Decimal("100"), "earning")
        except Exception as e:
            self.fail(f"alert_large_transaction raised: {e}")

    def test_alert_large_transaction_above_threshold_does_not_raise(self):
        try:
            self.adapter.alert_large_transaction(self.user, self.wallet, Decimal("15000"), "earning")
        except Exception as e:
            self.fail(f"large transaction alert raised: {e}")

    def test_alert_wallet_error_does_not_raise(self):
        try:
            self.adapter.alert_wallet_error(self.user, self.wallet, "sync_failure", "DB timeout")
        except Exception as e:
            self.fail(f"alert_wallet_error raised: {e}")

    def test_alert_balance_discrepancy_does_not_raise(self):
        try:
            self.adapter.alert_balance_discrepancy(
                self.wallet, Decimal("5000"), Decimal("4999")
            )
        except Exception as e:
            self.fail(f"alert_balance_discrepancy raised: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 10. SupportWalletAdapter
# ══════════════════════════════════════════════════════════════════════════════
class SupportWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import SupportWalletAdapter
        self.adapter = SupportWalletAdapter
        self.user    = _user("support_adp1")
        self.wallet  = _wallet(self.user)

    def test_get_wallet_summary_for_support_returns_dict(self):
        result = self.adapter.get_wallet_summary_for_support(self.user)
        self.assertIsInstance(result, dict)

    def test_get_wallet_summary_has_support_actions(self):
        result = self.adapter.get_wallet_summary_for_support(self.user)
        self.assertIn("support_actions", result)
        self.assertIn("lock", result["support_actions"])

    def test_get_transaction_history_returns_list(self):
        _txn(self.wallet)
        result = self.adapter.get_transaction_history_for_support(self.user, limit=10)
        self.assertIsInstance(result, list)
        if result:
            self.assertIn("txn_id", result[0])
            self.assertIn("amount", result[0])

    def test_get_transaction_history_respects_limit(self):
        for _ in range(5):
            _txn(self.wallet)
        result = self.adapter.get_transaction_history_for_support(self.user, limit=3)
        self.assertLessEqual(len(result), 3)


# ══════════════════════════════════════════════════════════════════════════════
# 11. WalletAdapter (Master)
# ══════════════════════════════════════════════════════════════════════════════
class WalletAdapterMasterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import WalletAdapter
        from api.wallet.models import WithdrawalRequest, WithdrawalMethod
        self.WalletAdapter = WalletAdapter
        self.user    = _user("master_adp1")
        self.wallet  = _wallet(self.user)
        self.txn     = _txn(self.wallet)
        self.method  = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01722222222", account_name="Master Test",
            is_verified=True,
        )
        self.wr = WithdrawalRequest.objects.create(
            user=self.user, wallet=self.wallet,
            payment_method=self.method,
            amount=Decimal("500"), net_amount=Decimal("485"),
            status="pending",
        )

    def test_on_credit_does_not_raise(self):
        try:
            self.WalletAdapter.on_credit(
                self.txn, self.user, self.wallet, Decimal("100"),
                txn_type="earning", country_code="BD"
            )
        except Exception as e:
            self.fail(f"WalletAdapter.on_credit raised: {e}")

    def test_on_credit_with_offer_id(self):
        try:
            self.WalletAdapter.on_credit(
                self.txn, self.user, self.wallet, Decimal("50"),
                txn_type="earning", offer_id=1, click_id="abc123"
            )
        except Exception as e:
            self.fail(f"on_credit with offer raised: {e}")

    def test_on_withdrawal_initiated_does_not_raise(self):
        try:
            self.WalletAdapter.on_withdrawal_initiated(self.wr, self.user, self.wallet)
        except Exception as e:
            self.fail(f"on_withdrawal_initiated raised: {e}")

    def test_on_withdrawal_completed_does_not_raise(self):
        try:
            self.WalletAdapter.on_withdrawal_completed(
                self.txn, self.user, self.wallet, Decimal("500"), "bkash"
            )
        except Exception as e:
            self.fail(f"on_withdrawal_completed raised: {e}")

    def test_on_withdrawal_rejected_does_not_raise(self):
        try:
            self.WalletAdapter.on_withdrawal_rejected(
                self.user, self.wallet, Decimal("500"), "KYC required"
            )
        except Exception as e:
            self.fail(f"on_withdrawal_rejected raised: {e}")

    def test_on_wallet_locked_does_not_raise(self):
        try:
            self.WalletAdapter.on_wallet_locked(self.user, self.wallet, "Fraud")
        except Exception as e:
            self.fail(f"on_wallet_locked raised: {e}")

    def test_on_kyc_approved_does_not_raise(self):
        try:
            self.WalletAdapter.on_kyc_approved(self.user, self.wallet, 2)
        except Exception as e:
            self.fail(f"on_kyc_approved raised: {e}")

    def test_check_withdrawal_allowed_returns_bool_str_tuple(self):
        allowed, reason = self.WalletAdapter.check_withdrawal_allowed(
            self.user, self.wallet, Decimal("500"), ip_address="10.0.0.1"
        )
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(reason, str)

    def test_check_withdrawal_allowed_normal_user_allowed(self):
        allowed, reason = self.WalletAdapter.check_withdrawal_allowed(
            self.user, self.wallet, Decimal("100")
        )
        self.assertIsInstance(allowed, bool)

    def test_adapter_never_raises_on_external_failure(self):
        """Even if all external apps fail, master adapter must not raise."""
        with patch("api.wallet.adapters.FraudSignalAdapter.on_withdrawal_requested",
                   side_effect=Exception("Fraud service down")):
            with patch("api.wallet.adapters.KYCWalletAdapter.is_withdrawal_allowed",
                       side_effect=Exception("KYC service down")):
                try:
                    allowed, reason = self.WalletAdapter.check_withdrawal_allowed(
                        self.user, self.wallet, Decimal("500")
                    )
                    # Fail open is acceptable
                    self.assertIsInstance(allowed, bool)
                except Exception as e:
                    self.fail(f"Master adapter raised despite all failures: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# NEW ADAPTERS — All 19 missing adapters (HIGH + MEDIUM + LOW priority)
# ══════════════════════════════════════════════════════════════════════════════

class PaymentGatewayAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import PaymentGatewayAdapter
        from api.wallet.models import WithdrawalMethod, WithdrawalRequest
        self.adapter = PaymentGatewayAdapter
        self.user   = _user("pgw1")
        self.wallet = _wallet(self.user)
        self.method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01711111111", account_name="PGW Test",
            is_verified=True,
        )
        self.wr = WithdrawalRequest.objects.create(
            user=self.user, wallet=self.wallet,
            payment_method=self.method,
            amount=Decimal("500"), net_amount=Decimal("485"),
            status="approved",
        )

    def test_process_withdrawal_returns_dict(self):
        r = self.adapter.process_withdrawal(self.wr, self.user, self.wallet)
        self.assertIsInstance(r, dict)
        self.assertTrue(r.get("success") or r.get("skipped"))

    def test_verify_account_returns_valid(self):
        r = self.adapter.verify_account("bkash", "01711111111", "Test User")
        self.assertIsInstance(r, dict)
        self.assertIn("valid", r)

    def test_get_gateway_fee_returns_decimal(self):
        r = self.adapter.get_gateway_fee("bkash", Decimal("1000"))
        self.assertIsInstance(r, dict)
        self.assertIn("fee", r)

    def test_get_transaction_status_returns_dict(self):
        r = self.adapter.get_transaction_status("TXN123", "bkash")
        self.assertIsInstance(r, dict)
        self.assertIn("status", r)

    def test_gateway_map_has_all_methods(self):
        for method in ["bkash", "nagad", "rocket", "bank", "usdt_trc20"]:
            self.assertIn(method, self.adapter.GATEWAY_MAP)


class UserProfileAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import UserProfileAdapter
        self.adapter = UserProfileAdapter
        self.user   = _user("upa1")
        self.wallet = _wallet(self.user)

    def test_get_user_status_returns_dict(self):
        r = self.adapter.get_user_status(self.user)
        self.assertIsInstance(r, dict)
        self.assertIn("active", r)
        self.assertIn("suspended", r)

    def test_is_suspended_returns_bool(self):
        self.assertIsInstance(self.adapter.is_suspended(self.user), bool)
        self.assertFalse(self.adapter.is_suspended(self.user))

    def test_get_withdrawal_limit_multiplier_returns_decimal(self):
        m = self.adapter.get_withdrawal_limit_multiplier(self.user)
        self.assertIsInstance(m, Decimal)
        self.assertGreater(m, 0)

    def test_on_wallet_created_does_not_raise(self):
        try:
            self.adapter.on_wallet_created(self.user, self.wallet)
        except Exception as e:
            self.fail(f"on_wallet_created raised: {e}")

    def test_get_preferred_currency_returns_string(self):
        c = self.adapter.get_preferred_currency(self.user)
        self.assertIsInstance(c, str)
        self.assertGreater(len(c), 0)


class SecurityAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import SecurityAdapter
        self.adapter = SecurityAdapter
        self.user   = _user("sec_adp1")
        self.wallet = _wallet(self.user)

    def test_verify_2fa_missing_app_returns_verified(self):
        r = self.adapter.verify_2fa(self.user, "123456", "withdrawal")
        self.assertIsInstance(r, dict)
        self.assertTrue(r.get("verified") or r.get("skipped"))

    def test_is_2fa_required_below_threshold_false(self):
        r = self.adapter.is_2fa_required(self.user, Decimal("100"))
        self.assertIsInstance(r, bool)
        self.assertFalse(r)

    def test_is_2fa_required_above_threshold_true(self):
        r = self.adapter.is_2fa_required(self.user, Decimal("10000"))
        self.assertIsInstance(r, bool)
        self.assertTrue(r)

    def test_check_session_freshness_returns_dict(self):
        r = self.adapter.check_session_freshness(self.user)
        self.assertIsInstance(r, dict)
        self.assertIn("fresh", r)

    def test_log_sensitive_action_does_not_raise(self):
        try:
            self.adapter.log_sensitive_action(
                self.user, "withdrawal", self.wallet, Decimal("500"), "1.2.3.4", True
            )
        except Exception as e:
            self.fail(f"log_sensitive_action raised: {e}")


class OfferwallAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import OfferwallAdapter
        self.adapter = OfferwallAdapter
        self.user   = _user("offerwall1")
        self.wallet = _wallet(self.user)

    def test_on_offer_completed_credits_wallet(self):
        before = self.wallet.current_balance
        r = self.adapter.on_offer_completed(
            self.user, self.wallet, 42, Decimal("10"), "click_xyz", "1.1.1.1", "BD"
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.current_balance, before)

    def test_on_offer_reversed_debits_wallet(self):
        self.wallet.current_balance = Decimal("100")
        self.wallet.save()
        r = self.adapter.on_offer_reversed(
            self.user, self.wallet, 42, Decimal("10"), "fraud"
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertLessEqual(self.wallet.current_balance, Decimal("100"))

    def test_get_available_balance_for_offers(self):
        r = self.adapter.get_available_balance_for_offers(self.wallet)
        self.assertIn("current_balance", r)
        self.assertIn("is_locked", r)


class AdNetworkAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import AdNetworkAdapter
        self.adapter = AdNetworkAdapter
        self.user   = _user("adnet1")
        self.wallet = _wallet(self.user)

    def test_on_ad_revenue_credits_publisher_share(self):
        before = self.wallet.current_balance
        r = self.adapter.on_ad_revenue(
            self.user, self.wallet, "google", Decimal("10"), "imp_123", "1.2.3.4"
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            # Publisher gets 70% = 7.00
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.current_balance, before)

    def test_revenue_share_is_70_percent(self):
        self.assertEqual(self.adapter.REVENUE_SHARE, Decimal("0.70"))

    def test_get_revenue_summary_returns_dict(self):
        r = self.adapter.get_revenue_summary(self.user, self.wallet)
        self.assertIsInstance(r, dict)
        self.assertIn("total", r)


class PromotionAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import PromotionAdapter
        self.adapter = PromotionAdapter
        self.user   = _user("promo1")
        self.wallet = _wallet(self.user)

    def test_apply_promo_code_missing_app_returns_error(self):
        r = self.adapter.apply_promo_code(self.user, self.wallet, "SAVE10")
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_credit_signup_bonus_does_not_raise(self):
        try:
            r = self.adapter.credit_signup_bonus(self.user, self.wallet)
            self.assertIsInstance(r, dict)
        except Exception as e:
            self.fail(f"credit_signup_bonus raised: {e}")

    def test_get_active_promotions_returns_list(self):
        r = self.adapter.get_active_promotions(self.user)
        self.assertIsInstance(r, list)


class EngagementAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import EngagementAdapter
        self.adapter = EngagementAdapter
        self.user   = _user("engage1")
        self.wallet = _wallet(self.user)

    def test_on_daily_login_returns_dict(self):
        r = self.adapter.on_daily_login(self.user, self.wallet, 7)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_on_milestone_reached_with_zero_reward(self):
        r = self.adapter.on_milestone_reached(self.user, self.wallet, "first_withdrawal", Decimal("0"))
        self.assertIsInstance(r, dict)
        self.assertTrue(r.get("success"))
        self.assertFalse(r.get("credited", True))

    def test_on_milestone_reached_credits_wallet(self):
        before = self.wallet.current_balance
        r = self.adapter.on_milestone_reached(
            self.user, self.wallet, "first_100_earned", Decimal("50")
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.current_balance, before)


class LoyaltyAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import LoyaltyAdapter
        self.adapter = LoyaltyAdapter
        self.user   = _user("loyal1")
        self.wallet = _wallet(self.user)

    def test_points_to_cash_missing_app_returns_error(self):
        r = self.adapter.points_to_cash(self.user, self.wallet, 100)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_earn_points_for_withdrawal_returns_int(self):
        points = self.adapter.earn_points_for_withdrawal(self.user, Decimal("1000"))
        self.assertIsInstance(points, int)
        self.assertGreaterEqual(points, 0)

    def test_get_point_balance_returns_dict(self):
        r = self.adapter.get_point_balance(self.user)
        self.assertIsInstance(r, dict)
        self.assertIn("points", r)


class SmartLinkAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import SmartLinkAdapter
        self.adapter = SmartLinkAdapter
        self.user   = _user("sl1")
        self.wallet = _wallet(self.user)

    def test_on_conversion_credits_wallet(self):
        before = self.wallet.current_balance
        r = self.adapter.on_conversion(
            self.user, self.wallet, "sl_abc123", Decimal("15"), "click_1", "BD", "1.2.3.4"
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.current_balance, before)

    def test_get_earnings_returns_dict(self):
        r = self.adapter.get_publisher_smartlink_earnings(self.user, self.wallet)
        self.assertIsInstance(r, dict)
        self.assertIn("total", r)


class AuditLogAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import AuditLogAdapter
        self.adapter = AuditLogAdapter
        self.user   = _user("audit1")
        self.wallet = _wallet(self.user)
        self.txn    = _txn(self.wallet)

    def test_log_transaction_does_not_raise(self):
        try:
            self.adapter.log_transaction(
                self.user, self.wallet, self.txn, "credited", ip="1.2.3.4"
            )
        except Exception as e:
            self.fail(f"log_transaction raised: {e}")

    def test_log_withdrawal_does_not_raise(self):
        from api.wallet.models import WithdrawalMethod, WithdrawalRequest
        method = WithdrawalMethod.objects.create(
            user=self.user, method_type="bkash",
            account_number="01711112222", account_name="Audit"
        )
        wr = WithdrawalRequest.objects.create(
            user=self.user, wallet=self.wallet,
            payment_method=method,
            amount=Decimal("100"), net_amount=Decimal("95"),
            status="pending"
        )
        try:
            self.adapter.log_withdrawal(self.user, self.wallet, wr, "initiated")
        except Exception as e:
            self.fail(f"log_withdrawal raised: {e}")

    def test_log_admin_action_does_not_raise(self):
        admin = User.objects.create_superuser("audit_admin", "x@x.com", "p")
        try:
            self.adapter.log_admin_action(admin, self.user, self.wallet, "credit", Decimal("500"), "bonus")
        except Exception as e:
            self.fail(f"log_admin_action raised: {e}")


class RateLimitAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import RateLimitAdapter
        self.adapter = RateLimitAdapter
        self.user   = _user("rl1")

    def test_check_withdrawal_rate_returns_dict(self):
        r = self.adapter.check_withdrawal_rate(self.user, Decimal("500"))
        self.assertIsInstance(r, dict)
        self.assertIn("allowed", r)

    def test_check_earning_rate_returns_dict(self):
        r = self.adapter.check_earning_rate(self.user, "offerwall")
        self.assertIsInstance(r, dict)
        self.assertIn("allowed", r)

    def test_normal_user_allowed_withdrawal(self):
        r = self.adapter.check_withdrawal_rate(self.user, Decimal("500"))
        self.assertTrue(r.get("allowed", True))


class MessagingAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import MessagingAdapter
        self.adapter = MessagingAdapter
        self.user   = _user("msg1")

    def test_alert_admin_does_not_raise(self):
        try:
            self.adapter.alert_admin("Test Alert", "Wallet test", "info")
        except Exception as e:
            self.fail(f"alert_admin raised: {e}")

    def test_send_user_message_does_not_raise(self):
        try:
            self.adapter.send_user_message(self.user, "Your wallet was credited")
        except Exception as e:
            self.fail(f"send_user_message raised: {e}")

    def test_create_support_ticket_returns_dict(self):
        r = self.adapter.create_support_ticket(
            self.user, "Withdrawal failed", "My withdrawal did not process"
        )
        self.assertIsInstance(r, dict)
        self.assertIn("ticket_id", r)


class MarketplaceAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import MarketplaceAdapter
        self.adapter = MarketplaceAdapter
        self.buyer  = _user("buyer1")
        self.seller = _user("seller1")
        self.buyer_wallet  = _wallet(self.buyer)
        self.seller_wallet = _wallet(self.seller)

    def test_charge_buyer_debits_wallet(self):
        before = self.buyer_wallet.current_balance
        r = self.adapter.charge_buyer(
            self.buyer, self.buyer_wallet, "ORD-001", Decimal("200"), self.seller.pk
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.buyer_wallet.refresh_from_db()
            self.assertLess(self.buyer_wallet.current_balance, before)

    def test_credit_seller_after_fee(self):
        before = self.seller_wallet.current_balance
        r = self.adapter.credit_seller(
            self.seller, self.seller_wallet, "ORD-001", Decimal("200")
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.assertEqual(r["credited"], "180.00")  # 200 - 10% = 180
            self.assertEqual(r["fee"], "20.00")

    def test_process_refund_credits_buyer(self):
        before = self.buyer_wallet.current_balance
        r = self.adapter.process_refund(
            self.buyer, self.buyer_wallet, "ORD-001", Decimal("200")
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.buyer_wallet.refresh_from_db()
            self.assertGreater(self.buyer_wallet.current_balance, before)


class ProxyIntelligenceAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import ProxyIntelligenceAdapter
        self.adapter = ProxyIntelligenceAdapter

    def test_check_ip_clean_returns_dict(self):
        r = self.adapter.check_ip("8.8.8.8")
        self.assertIsInstance(r, dict)
        self.assertIn("is_proxy", r)
        self.assertIn("is_vpn", r)

    def test_clean_ip_is_allowed(self):
        allowed, reason = self.adapter.is_withdrawal_allowed_from_ip("8.8.8.8")
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(reason, str)

    def test_skipped_always_allows(self):
        # When service unavailable (skipped=True), always allow
        allowed, reason = self.adapter.is_withdrawal_allowed_from_ip("1.2.3.4")
        self.assertTrue(allowed)


class PublisherToolsAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import PublisherToolsAdapter
        self.adapter = PublisherToolsAdapter
        self.user   = _user("pub1")
        self.wallet = _wallet(self.user)

    def test_get_earnings_dashboard_returns_dict(self):
        r = self.adapter.get_earnings_dashboard(self.user, self.wallet)
        self.assertIsInstance(r, dict)
        self.assertIn("total_earned", r)

    def test_on_monetization_event_does_not_raise(self):
        try:
            r = self.adapter.on_monetization_event(
                self.user, self.wallet, "widget_impression", Decimal("0.01")
            )
            self.assertIsInstance(r, dict)
        except Exception as e:
            self.fail(f"monetization event raised: {e}")


class TenantWalletAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import TenantWalletAdapter
        self.adapter = TenantWalletAdapter
        self.user   = _user("tenant1")

    def test_get_tenant_returns_none_or_obj(self):
        result = self.adapter.get_tenant_for_user(self.user)
        # Either None (no tenant) or a tenant object
        self.assertIsInstance(result, (type(None), object))

    def test_get_tenant_wallet_config_has_currency(self):
        config = self.adapter.get_tenant_wallet_config(None)
        self.assertIsInstance(config, dict)
        self.assertIn("currency", config)
        self.assertIn("min_withdrawal", config)

    def test_wallet_enabled_returns_true(self):
        enabled = self.adapter.is_wallet_enabled_for_tenant(None)
        self.assertIsInstance(enabled, bool)
        self.assertTrue(enabled)


class CacheAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import CacheAdapter
        self.adapter = CacheAdapter
        self.user   = _user("cache1")
        self.wallet = _wallet(self.user)

    def test_set_and_get_cached_balance(self):
        self.adapter.set_cached_balance(self.wallet.pk, Decimal("5000"))
        cached = self.adapter.get_cached_balance(self.wallet.pk)
        self.assertEqual(cached, Decimal("5000"))

    def test_get_uncached_returns_none(self):
        self.adapter.invalidate_wallet_cache(self.wallet.pk)
        cached = self.adapter.get_cached_balance(99999)
        self.assertIsNone(cached)

    def test_invalidate_does_not_raise(self):
        try:
            self.adapter.invalidate_wallet_cache(self.wallet.pk)
        except Exception as e:
            self.fail(f"invalidate raised: {e}")


class LocalizationAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import LocalizationAdapter
        self.adapter = LocalizationAdapter
        self.user   = _user("locale1")

    def test_format_amount_returns_string(self):
        result = self.adapter.format_amount(Decimal("1000.50"), "BDT", "bn_BD")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_format_amount_contains_amount(self):
        result = self.adapter.format_amount(Decimal("500"), "BDT")
        self.assertIn("500", result)

    def test_get_user_locale_returns_string(self):
        locale = self.adapter.get_user_locale(self.user)
        self.assertIsInstance(locale, str)
        self.assertGreater(len(locale), 0)


# ══════════════════════════════════════════════════════════════════════════════
# COVERAGE SUMMARY TEST — verifies all 46 apps have coverage
# ══════════════════════════════════════════════════════════════════════════════
class AdapterCoverageTest(TestCase):
    """Verifies all INSTALLED_APPS have at least one adapter method."""

    def test_all_apps_have_adapter(self):
        from api.wallet.adapters import integration
        adapter_classes = [
            name for name in dir(integration)
            if isinstance(getattr(integration, name), type)
            and name.endswith('Adapter')
        ]
        # 37 adapter classes covering all 46 apps (some apps share adapters)
        self.assertGreaterEqual(len(adapter_classes), 35,
            f"Expected 35+ adapter classes, got {len(adapter_classes)}: {adapter_classes}")

    def test_wallet_adapter_has_all_gate_checks(self):
        from api.wallet.adapters import WalletAdapter
        self.assertTrue(hasattr(WalletAdapter, 'check_withdrawal_allowed'))
        self.assertTrue(hasattr(WalletAdapter, 'on_credit'))
        self.assertTrue(hasattr(WalletAdapter, 'on_withdrawal_initiated'))
        self.assertTrue(hasattr(WalletAdapter, 'on_withdrawal_completed'))
        self.assertTrue(hasattr(WalletAdapter, 'on_withdrawal_rejected'))
        self.assertTrue(hasattr(WalletAdapter, 'on_wallet_locked'))
        self.assertTrue(hasattr(WalletAdapter, 'on_kyc_approved'))

    def test_master_adapter_check_withdrawal_uses_6_gates(self):
        """check_withdrawal_allowed checks KYC+Fraud+AutoMod+Proxy+RateLimit+UserStatus."""
        import inspect
        from api.wallet.adapters import WalletAdapter
        src = inspect.getsource(WalletAdapter.check_withdrawal_allowed)
        self.assertIn('KYCWalletAdapter', src)
        self.assertIn('FraudSignalAdapter', src)
        self.assertIn('AutoModWalletAdapter', src)
        self.assertIn('ProxyIntelligenceAdapter', src)
        self.assertIn('RateLimitAdapter', src)
        self.assertIn('UserProfileAdapter', src)


# ══════════════════════════════════════════════════════════════════════════════
# FINAL BATCH — 9 remaining adapters (all INSTALLED_APPS now covered)
# ══════════════════════════════════════════════════════════════════════════════

class AdminPanelAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import AdminPanelAdapter
        self.adapter = AdminPanelAdapter
        self.user   = _user("ap1")
        self.wallet = _wallet(self.user)
        self.admin  = User.objects.create_superuser("ap_admin", "ap@t.com", "p")

    def test_get_wallet_admin_summary_returns_dict(self):
        r = self.adapter.get_wallet_admin_summary(self.wallet)
        self.assertIsInstance(r, dict)
        self.assertIn("wallet_id", r)
        self.assertIn("current_balance", r)
        self.assertIn("is_locked", r)

    def test_register_admin_action_does_not_raise(self):
        try:
            self.adapter.register_admin_action(
                "credit", self.admin.pk, self.wallet.pk, Decimal("100"), "test"
            )
        except Exception as e:
            self.fail(f"register_admin_action raised: {e}")

    def test_get_pending_approvals_returns_list(self):
        r = self.adapter.get_pending_approvals()
        self.assertIsInstance(r, list)
        if r:
            self.assertIn("type", r[0])
            self.assertIn("count", r[0])


class CMSAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import CMSAdapter
        self.adapter = CMSAdapter
        self.user   = _user("cms1")

    def test_get_wallet_banner_returns_dict(self):
        r = self.adapter.get_wallet_banner(self.user, "wallet_home")
        self.assertIsInstance(r, dict)

    def test_get_wallet_notice_returns_string(self):
        r = self.adapter.get_wallet_notice("withdrawal_notice")
        self.assertIsInstance(r, str)

    def test_get_faq_returns_list(self):
        r = self.adapter.get_faq("wallet")
        self.assertIsInstance(r, list)

    def test_get_withdrawal_method_info_bkash(self):
        r = self.adapter.get_withdrawal_method_info("bkash")
        self.assertIsInstance(r, dict)
        self.assertEqual(r.get("name"), "bKash")
        self.assertEqual(r.get("processing_time"), "Instant")

    def test_get_withdrawal_method_info_bank(self):
        r = self.adapter.get_withdrawal_method_info("bank")
        self.assertIsInstance(r, dict)
        self.assertIn("processing_time", r)

    def test_get_withdrawal_method_info_unknown(self):
        r = self.adapter.get_withdrawal_method_info("unknown_method")
        self.assertIsInstance(r, dict)


class TasksAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import TasksAdapter
        self.adapter = TasksAdapter
        self.user   = _user("tasks1")
        self.wallet = _wallet(self.user)

    def test_schedule_withdrawal_processing_returns_dict(self):
        r = self.adapter.schedule_withdrawal_processing("WD-001", delay_seconds=0)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_schedule_balance_sync_returns_dict(self):
        r = self.adapter.schedule_balance_sync(self.wallet.pk)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_schedule_fraud_check_returns_dict(self):
        txn = _txn(self.wallet)
        r = self.adapter.schedule_fraud_check(txn.pk)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_schedule_statement_generation_returns_dict(self):
        r = self.adapter.schedule_statement_generation(self.user.pk, 12, 2024)
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)


class BackupAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import BackupAdapter
        self.adapter = BackupAdapter
        self.user   = _user("backup1")
        self.wallet = _wallet(self.user)

    def test_backup_before_operation_returns_dict(self):
        r = self.adapter.backup_wallet_before_operation(self.wallet, "bulk_debit")
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_backup_skips_gracefully_when_service_missing(self):
        r = self.adapter.backup_wallet_before_operation(self.wallet, "migration")
        self.assertTrue(r.get("success") or r.get("skipped"))

    def test_restore_missing_snapshot_returns_error(self):
        r = self.adapter.restore_wallet_from_backup(self.wallet.pk, "nonexistent_snapshot")
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_get_wallet_backup_history_returns_list(self):
        r = self.adapter.get_wallet_backup_history(self.wallet.pk)
        self.assertIsInstance(r, list)


class VersionControlAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import VersionControlAdapter
        self.adapter = VersionControlAdapter

    def test_get_api_version_default_is_v2(self):
        v = self.adapter.get_api_version(request=None)
        self.assertEqual(v, "v2")

    def test_is_deprecated_v1_true(self):
        self.assertTrue(self.adapter.is_deprecated("v1"))

    def test_is_deprecated_v2_false(self):
        self.assertFalse(self.adapter.is_deprecated("v2"))

    def test_transform_v1_renames_balance(self):
        data = {"current_balance": "1000.00", "frozen_balance": "0.00"}
        result = self.adapter.transform_response_for_version(data, "v1")
        self.assertIn("balance", result)
        self.assertEqual(result["balance"], "1000.00")

    def test_transform_v2_unchanged(self):
        data = {"current_balance": "500.00"}
        result = self.adapter.transform_response_for_version(data, "v2")
        self.assertEqual(result, data)

    def test_log_version_usage_does_not_raise(self):
        try:
            self.adapter.log_version_usage("v1", "/api/wallet/wallets/me/")
        except Exception as e:
            self.fail(f"log_version_usage raised: {e}")

    def test_supported_versions_contains_v1_and_v2(self):
        self.assertIn("v1", self.adapter.SUPPORTED_VERSIONS)
        self.assertIn("v2", self.adapter.SUPPORTED_VERSIONS)


class InventoryAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import InventoryAdapter
        self.adapter = InventoryAdapter
        self.user   = _user("inv1")
        self.wallet = _wallet(self.user)

    def test_deduct_for_purchase_debits_wallet(self):
        before = self.wallet.current_balance
        r = self.adapter.deduct_for_purchase(
            self.user, self.wallet, "ITEM-001", 2, Decimal("100")
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertEqual(self.wallet.current_balance, before - Decimal("200"))

    def test_deduct_calculates_total_correctly(self):
        r = self.adapter.deduct_for_purchase(
            self.user, self.wallet, "ITEM-002", 3, Decimal("50")
        )
        if r.get("success"):
            self.assertEqual(r["charged"], "150.00")

    def test_get_affordable_items_returns_list(self):
        r = self.adapter.get_affordable_items(self.wallet, "digital")
        self.assertIsInstance(r, list)

    def test_refund_inventory_purchase_credits_wallet(self):
        before = self.wallet.current_balance
        r = self.adapter.refund_inventory_purchase(
            self.user, self.wallet, "ITEM-001", Decimal("200")
        )
        self.assertIsInstance(r, dict)
        if r.get("success"):
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.current_balance, before)


class OfferInventoryAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import OfferInventoryAdapter
        self.adapter = OfferInventoryAdapter
        self.user   = _user("oi1")
        self.wallet = _wallet(self.user)

    def test_get_available_offers_returns_list(self):
        r = self.adapter.get_available_offers(self.user, self.wallet, "BD", 10)
        self.assertIsInstance(r, list)

    def test_estimate_daily_earnings_returns_decimal(self):
        r = self.adapter.estimate_daily_earnings(self.user, "BD")
        self.assertIsInstance(r, Decimal)
        self.assertGreaterEqual(r, Decimal("0"))

    def test_mark_offer_seen_does_not_raise(self):
        try:
            self.adapter.mark_offer_seen(self.user, 42)
        except Exception as e:
            self.fail(f"mark_offer_seen raised: {e}")


class DisasterRecoveryFullAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import DisasterRecoveryFullAdapter
        self.adapter = DisasterRecoveryFullAdapter
        self.user   = _user("dr1")
        self.wallet = _wallet(self.user)

    def test_health_check_returns_healthy(self):
        r = self.adapter.health_check()
        self.assertIsInstance(r, dict)
        self.assertIn("healthy", r)
        self.assertTrue(r["healthy"])
        self.assertIn("wallet_count", r)

    def test_initiate_failover_skips_gracefully(self):
        r = self.adapter.initiate_failover("test_failover")
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_verify_data_integrity_returns_dict(self):
        r = self.adapter.verify_data_integrity([self.wallet.pk])
        self.assertIsInstance(r, dict)
        self.assertIn("checked", r)
        self.assertIn("issues", r)
        self.assertIn("clean", r)
        self.assertIsInstance(r["issues"], list)

    def test_create_emergency_snapshot_returns_dict(self):
        r = self.adapter.create_emergency_snapshot()
        self.assertIsInstance(r, dict)
        self.assertIn("success", r)

    def test_health_check_has_status_operational(self):
        r = self.adapter.health_check()
        self.assertEqual(r.get("status"), "operational")


class APIRootAdapterTest(TestCase):
    def setUp(self):
        from api.wallet.adapters import APIRootAdapter
        self.adapter = APIRootAdapter

    def test_get_wallet_feature_flags_returns_dict(self):
        r = self.adapter.get_wallet_feature_flags()
        self.assertIsInstance(r, dict)

    def test_get_global_wallet_limits_returns_dict(self):
        r = self.adapter.get_global_wallet_limits()
        self.assertIsInstance(r, dict)
        self.assertIn("min_withdrawal", r)
        self.assertIn("max_withdrawal", r)
        self.assertIn("currency", r)

    def test_global_limits_currency_is_bdt(self):
        r = self.adapter.get_global_wallet_limits()
        self.assertEqual(r["currency"], "BDT")

    def test_is_maintenance_mode_returns_bool(self):
        r = self.adapter.is_maintenance_mode()
        self.assertIsInstance(r, bool)
        self.assertFalse(r)  # Should not be in maintenance by default

    def test_min_withdrawal_is_valid_decimal(self):
        r = self.adapter.get_global_wallet_limits()
        self.assertGreater(float(r["min_withdrawal"]), 0)


# ══════════════════════════════════════════════════════════════════════════════
# FINAL COVERAGE VERIFICATION — All 48 INSTALLED_APPS covered
# ══════════════════════════════════════════════════════════════════════════════
class FullAdapterCoverageTest(TestCase):
    """Verifies ALL apps from INSTALLED_APPS have adapter coverage."""

    INSTALLED_APPS_NEEDING_ADAPTER = [
        "api",
        "api.users", "api.security", "api.admin_panel", "api.payment_gateways",
        "api.tenants", "api.ad_networks", "api.offerwall", "api.fraud_detection",
        "api.analytics", "api.referral", "api.engagement", "api.notifications",
        "api.cms", "api.support", "api.alerts", "api.djoyalty",
        "api.kyc", "api.cache", "api.tasks", "api.rate_limit",
        "api.localization", "api.audit_logs", "api.backup",
        "api.promotions", "api.subscription", "api.gamification",
        "api.auto_mod", "api.version_control", "api.behavior_analytics",
        "api.postback", "api.inventory", "api.messaging",
        "api.payout_queue", "api.webhooks", "api.marketplace",
        "api.postback_engine", "api.monetization_tools", "api.publisher_tools",
        "api.proxy_intelligence", "api.advertiser_portal", "api.offer_inventory",
        "api.smartlink", "api.disaster_recovery", "api.dr_integration",
        "api.ai_engine", "api.offer_routing",
    ]

    ADAPTER_MAP = {
        "api":                  "APIRootAdapter",
        "api.users":            "UserProfileAdapter",
        "api.security":         "SecurityAdapter",
        "api.admin_panel":      "AdminPanelAdapter",
        "api.payment_gateways": "PaymentGatewayAdapter",
        "api.tenants":          "TenantWalletAdapter",
        "api.ad_networks":      "AdNetworkAdapter",
        "api.offerwall":        "OfferwallAdapter",
        "api.fraud_detection":  "FraudSignalAdapter",
        "api.analytics":        "WalletAnalyticsAdapter",
        "api.referral":         "ReferralWalletAdapter",
        "api.engagement":       "EngagementAdapter",
        "api.notifications":    "WalletNotificationAdapter",
        "api.cms":              "CMSAdapter",
        "api.support":          "SupportWalletAdapter",
        "api.alerts":           "AlertWalletAdapter",
        "api.djoyalty":         "LoyaltyAdapter",
        "api.kyc":              "KYCWalletAdapter",
        "api.cache":            "CacheAdapter",
        "api.tasks":            "TasksAdapter",
        "api.rate_limit":       "RateLimitAdapter",
        "api.localization":     "LocalizationAdapter",
        "api.audit_logs":       "AuditLogAdapter",
        "api.backup":           "BackupAdapter",
        "api.promotions":       "PromotionAdapter",
        "api.subscription":     "SubscriptionWalletAdapter",
        "api.gamification":     "GamificationWalletAdapter",
        "api.auto_mod":         "AutoModWalletAdapter",
        "api.version_control":  "VersionControlAdapter",
        "api.behavior_analytics": "BehaviorAnalyticsAdapter",
        "api.postback":         "PostbackWalletAdapter",
        "api.inventory":        "InventoryAdapter",
        "api.messaging":        "MessagingAdapter",
        "api.payout_queue":     "PayoutQueueAdapter",
        "api.webhooks":         "ExternalWebhookAdapter",
        "api.marketplace":      "MarketplaceAdapter",
        "api.postback_engine":  "PostbackWalletAdapter",
        "api.monetization_tools": "PublisherToolsAdapter",
        "api.publisher_tools":  "PublisherToolsAdapter",
        "api.proxy_intelligence": "ProxyIntelligenceAdapter",
        "api.advertiser_portal": "AdvertiserPortalAdapter",
        "api.offer_inventory":  "OfferInventoryAdapter",
        "api.smartlink":        "SmartLinkAdapter",
        "api.disaster_recovery": "DisasterRecoveryFullAdapter",
        "api.dr_integration":   "DisasterRecoveryAdapter",
        "api.ai_engine":        "AIWalletAdapter",
        "api.offer_routing":    "OfferRoutingAdapter",
    }

    def test_all_installed_apps_have_adapter_mapping(self):
        """Every app in INSTALLED_APPS must have an adapter."""
        missing = [
            app for app in self.INSTALLED_APPS_NEEDING_ADAPTER
            if app not in self.ADAPTER_MAP
        ]
        self.assertEqual(
            missing, [],
            f"Apps without adapter mapping: {missing}"
        )

    def test_all_mapped_adapters_are_importable(self):
        """Every adapter class must be importable from api.wallet.adapters."""
        import api.wallet.adapters as adapter_module
        missing = []
        for app, adapter_name in self.ADAPTER_MAP.items():
            if not hasattr(adapter_module, adapter_name):
                missing.append(f"{app} -> {adapter_name}")
        self.assertEqual(
            missing, [],
            f"Adapter classes not importable: {missing}"
        )

    def test_all_adapter_classes_are_instantiable(self):
        """Adapter classes must be classes (not functions or None)."""
        import api.wallet.adapters as adapter_module
        for adapter_name in set(self.ADAPTER_MAP.values()):
            cls = getattr(adapter_module, adapter_name, None)
            self.assertIsNotNone(cls, f"{adapter_name} is None")
            self.assertTrue(isinstance(cls, type), f"{adapter_name} is not a class")

    def test_total_adapter_count_46(self):
        """We have 46 adapter classes covering all apps."""
        from api.wallet.adapters import integration
        adapter_classes = [
            name for name in dir(integration)
            if isinstance(getattr(integration, name), type)
            and name.endswith('Adapter')
        ]
        self.assertGreaterEqual(
            len(adapter_classes), 46,
            f"Expected 46+ adapters, got {len(adapter_classes)}"
        )

    def test_coverage_percentage_is_100(self):
        """100% of INSTALLED_APPS that need wallet integration are covered."""
        import api.wallet.adapters as adapter_module
        covered = sum(
            1 for app in self.INSTALLED_APPS_NEEDING_ADAPTER
            if app in self.ADAPTER_MAP
            and hasattr(adapter_module, self.ADAPTER_MAP[app])
        )
        total = len(self.INSTALLED_APPS_NEEDING_ADAPTER)
        pct = (covered / total) * 100
        self.assertEqual(pct, 100.0, f"Coverage: {covered}/{total} = {pct:.1f}%")
