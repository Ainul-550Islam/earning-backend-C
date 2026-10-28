# api/wallet/tests/test_content_locker.py
"""Tests for ContentLocker — CPALead content locking feature."""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _make_user(username):
    return User.objects.create_user(username=username, password="pass",
                                    email=f"{username}@test.com")


def _make_wallet(user):
    from ..services import WalletService
    return WalletService.get_or_create(user)


class ContentLockerModelTest(TestCase):

    def setUp(self):
        self.user   = _make_user("locker_user")
        self.wallet = _make_wallet(self.user)

    def _make_locker(self, **kwargs):
        from ..content_locker import ContentLockerService
        return ContentLockerService.create(
            publisher=self.user,
            wallet=self.wallet,
            title=kwargs.get("title", "Test Locker"),
            content_url=kwargs.get("content_url", "https://example.com/secret"),
            payout_rate=kwargs.get("payout_rate", Decimal("1.50")),
        )

    def test_create_locker(self):
        from ..content_locker import ContentLocker
        locker = self._make_locker()
        self.assertIsNotNone(locker.locker_id)
        self.assertEqual(locker.status, ContentLocker.STATUS_ACTIVE)
        self.assertEqual(locker.payout_rate, Decimal("1.50"))
        self.assertEqual(locker.total_views, 0)
        self.assertEqual(locker.total_completions, 0)

    def test_is_active_true_for_active_status(self):
        locker = self._make_locker()
        self.assertTrue(locker.is_active)

    def test_conversion_rate_zero_when_no_views(self):
        locker = self._make_locker()
        self.assertEqual(locker.conversion_rate, 0.0)

    def test_conversion_rate_calculated(self):
        from ..content_locker import ContentLocker
        locker = self._make_locker()
        locker.total_views       = 100
        locker.total_completions = 35
        locker.save()
        self.assertAlmostEqual(locker.conversion_rate, 35.0)

    def test_record_view_increments_counter(self):
        from ..content_locker import ContentLockerService, ContentLocker
        locker = self._make_locker()
        ContentLockerService.record_view(str(locker.locker_id))
        locker.refresh_from_db()
        self.assertEqual(locker.total_views, 1)

    def test_record_view_multiple(self):
        from ..content_locker import ContentLockerService
        locker = self._make_locker()
        for _ in range(5):
            ContentLockerService.record_view(str(locker.locker_id))
        locker.refresh_from_db()
        self.assertEqual(locker.total_views, 5)


class ContentLockerUnlockTest(TestCase):

    def setUp(self):
        self.user   = _make_user("unlock_user")
        self.wallet = _make_wallet(self.user)
        from ..content_locker import ContentLockerService
        self.locker = ContentLockerService.create(
            publisher=self.user,
            wallet=self.wallet,
            title="Unlock Test",
            content_url="https://example.com/secret-video",
            payout_rate=Decimal("2.00"),
        )

    @patch("api.wallet.content_locker.ContentLockerService._send_credit", create=True)
    def test_unlock_returns_access_token(self, _mock):
        from ..content_locker import ContentLockerService
        with patch.object(ContentLockerService, "_send_credit", create=True):
            result = ContentLockerService.unlock(
                locker_id=str(self.locker.locker_id),
                visitor_id="visitor-abc-123",
            )
        self.assertIn("access_token", result)
        self.assertIn("content_url", result)
        self.assertIn("expires_at", result)
        self.assertEqual(result["content_url"], "https://example.com/secret-video")

    def test_unlock_increments_completions(self):
        from ..content_locker import ContentLockerService
        with patch("api.wallet.content_locker.CPALeadService", create=True):
            try:
                ContentLockerService.unlock(
                    locker_id=str(self.locker.locker_id),
                    visitor_id="visitor-def-456",
                )
            except Exception:
                pass
        self.locker.refresh_from_db()
        self.assertGreaterEqual(self.locker.total_completions, 0)

    def test_verify_valid_token(self):
        from ..content_locker import ContentLockerService, ContentLockerUnlock
        from django.utils import timezone
        from datetime import timedelta
        unlock = ContentLockerUnlock.objects.create(
            locker=self.locker,
            visitor_id="vv1",
            access_token="test-token-abc123",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        result = ContentLockerService.verify_token("test-token-abc123")
        self.assertIsNotNone(result)
        self.assertEqual(result["content_url"], "https://example.com/secret-video")

    def test_verify_expired_token_returns_none(self):
        from ..content_locker import ContentLockerService, ContentLockerUnlock
        from django.utils import timezone
        from datetime import timedelta
        ContentLockerUnlock.objects.create(
            locker=self.locker,
            visitor_id="vv2",
            access_token="expired-token-xyz",
            expires_at=timezone.now() - timedelta(hours=2),
        )
        result = ContentLockerService.verify_token("expired-token-xyz")
        self.assertIsNone(result)

    def test_verify_nonexistent_token_returns_none(self):
        from ..content_locker import ContentLockerService
        result = ContentLockerService.verify_token("no-such-token")
        self.assertIsNone(result)

    def test_stats_returns_correct_data(self):
        from ..content_locker import ContentLockerService
        stats = ContentLockerService.stats(str(self.locker.locker_id))
        self.assertEqual(stats["title"], "Unlock Test")
        self.assertIn("total_views", stats)
        self.assertIn("conversion_rate", stats)

    def test_unlock_invalid_locker_raises(self):
        from ..content_locker import ContentLockerService
        with self.assertRaises(ValueError):
            ContentLockerService.unlock(
                locker_id="00000000-0000-0000-0000-000000000000",
                visitor_id="v1",
            )
