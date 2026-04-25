# api/wallet/tests/test_idempotency.py
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import Wallet, IdempotencyKey
from ..services import WalletService, IdempotencyService

User = get_user_model()


class IdempotencyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="idem", password="pass", email="id@test.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_save_and_get(self):
        key = "test-key-001"
        IdempotencyService.save(key, {"result": "ok"}, wallet=self.wallet)
        fetched = IdempotencyService.get(key)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.key, key)

    def test_expired_key_returns_none(self):
        key = "expired-key-001"
        IdempotencyKey.objects.create(
            key=key, wallet=self.wallet,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        result = IdempotencyService.get(key)
        self.assertIsNone(result)

    def test_cleanup_removes_expired(self):
        for i in range(5):
            IdempotencyKey.objects.create(
                key=f"old-{i}", wallet=self.wallet,
                expires_at=timezone.now() - timedelta(hours=1)
            )
        count = IdempotencyService.cleanup()
        self.assertGreaterEqual(count, 5)

    def test_is_duplicate_true_for_existing(self):
        IdempotencyService.save("dup-key", {}, wallet=self.wallet)
        self.assertTrue(IdempotencyService.is_duplicate("dup-key"))

    def test_is_duplicate_false_for_nonexistent(self):
        self.assertFalse(IdempotencyService.is_duplicate("nonexistent-key-xyz"))

    def test_wallet_credit_idempotency(self):
        WalletService.credit(self.wallet, Decimal("500"), idempotency_key="credit-idem-001")
        WalletService.credit(self.wallet, Decimal("500"), idempotency_key="credit-idem-001")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.current_balance, Decimal("500"))
