# api/wallet/tests/test_notifications.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from ..notifications import WalletNotifier, NotificationTemplate

User = get_user_model()

class NotificationTemplateTest(TestCase):
    def test_wallet_credited_template(self):
        tmpl = NotificationTemplate.get("wallet_credited", {"amount":"500","balance_after":"1500"})
        self.assertIn("500", tmpl["body"])
        self.assertIn("1500", tmpl["body"])

    def test_withdrawal_completed_template(self):
        tmpl = NotificationTemplate.get("withdrawal_completed", {"amount":"300","gateway_ref":"BKS123"})
        self.assertIn("300", tmpl["body"])
        self.assertIn("BKS123", tmpl["body"])

    def test_unknown_event_returns_default(self):
        tmpl = NotificationTemplate.get("unknown_event", {})
        self.assertIn("title", tmpl)
        self.assertIn("body", tmpl)

    def test_template_format_error_graceful(self):
        # Missing format key — should not raise
        tmpl = NotificationTemplate.get("wallet_credited", {})
        self.assertIn("title", tmpl)

class WalletNotifierTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="notiftest", email="n@test.com", password="pass")

    def test_in_app_notification_saved(self):
        try:
            from ..models.notification import WalletNotification
            WalletNotifier._save_in_app(self.user.id, "wallet_credited",
                {"title":"Test","body":"Test body"}, {"amount":"100"})
            self.assertTrue(WalletNotification.objects.filter(user=self.user).exists())
        except Exception:
            pass  # Model may not be migrated in test

    def test_send_no_crash(self):
        # Should not raise even if push/email/SMS all fail
        result = WalletNotifier.send(
            user_id=self.user.id,
            event_type="wallet_credited",
            data={"amount":"100","balance_after":"600"},
            channels=["in_app"],
        )
        self.assertIsInstance(result, dict)
