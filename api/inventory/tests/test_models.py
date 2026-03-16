"""test_models.py – Unit tests for inventory models."""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from inventory.choices import CodeStatus, InventoryStatus
from inventory.constants import UNLIMITED_STOCK
from inventory.exceptions import InsufficientStockException, InventoryRevokedException
from inventory.models import RedemptionCode, RewardItem, UserInventory
from .factories import (
    ExpiredCodeFactory,
    RedeemedCodeFactory,
    RedemptionCodeFactory,
    RewardItemFactory,
    UnlimitedItemFactory,
    UserFactory,
    UserInventoryFactory,
    RevokedInventoryFactory,
    FailedInventoryFactory,
)


class RewardItemModelTests(TestCase):

    def test_str_includes_name_and_stock(self):
        item = RewardItemFactory(name="Test Gift", current_stock=10)
        self.assertIn("Test Gift", str(item))
        self.assertIn("10", str(item))

    def test_is_in_stock_true(self):
        item = RewardItemFactory(current_stock=5)
        self.assertTrue(item.is_in_stock)

    def test_is_in_stock_false(self):
        item = RewardItemFactory(current_stock=0)
        self.assertFalse(item.is_in_stock)

    def test_is_unlimited_true(self):
        item = UnlimitedItemFactory()
        self.assertTrue(item.is_unlimited)

    def test_is_unlimited_false(self):
        item = RewardItemFactory(current_stock=5)
        self.assertFalse(item.is_unlimited)

    def test_decrement_stock_success(self):
        item = RewardItemFactory(current_stock=10)
        item.decrement_stock(3)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, 7)
        self.assertEqual(item.total_redeemed, 3)

    def test_decrement_stock_raises_on_insufficient(self):
        item = RewardItemFactory(current_stock=2)
        with self.assertRaises(InsufficientStockException):
            item.decrement_stock(5)

    def test_decrement_stock_unlimited_does_not_change(self):
        item = UnlimitedItemFactory()
        item.decrement_stock(100)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, UNLIMITED_STOCK)

    def test_increment_stock(self):
        item = RewardItemFactory(current_stock=5)
        item.increment_stock(10)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, 15)

    def test_increment_stock_invalid_qty_raises(self):
        item = RewardItemFactory(current_stock=5)
        with self.assertRaises(ValueError):
            item.increment_stock(0)


class RedemptionCodeModelTests(TestCase):

    def test_is_available_true(self):
        code = RedemptionCodeFactory()
        self.assertTrue(code.is_available)

    def test_is_available_false_when_expired(self):
        code = ExpiredCodeFactory()
        self.assertFalse(code.is_available)

    def test_is_expired_true(self):
        code = ExpiredCodeFactory()
        self.assertTrue(code.is_expired)

    def test_mark_redeemed(self):
        user = UserFactory()
        code = RedemptionCodeFactory()
        code.mark_redeemed(user)
        code.refresh_from_db()
        self.assertEqual(code.status, CodeStatus.REDEEMED)
        self.assertEqual(code.redeemed_by, user)
        self.assertIsNotNone(code.redeemed_at)

    def test_reserve(self):
        code = RedemptionCodeFactory()
        code.reserve(ttl_seconds=300)
        code.refresh_from_db()
        self.assertEqual(code.status, CodeStatus.RESERVED)
        self.assertIsNotNone(code.reserved_until)

    def test_release_reservation(self):
        code = RedemptionCodeFactory(status=CodeStatus.RESERVED)
        code.reserved_until = timezone.now() + timezone.timedelta(minutes=5)
        code.save()
        code.release_reservation()
        code.refresh_from_db()
        self.assertEqual(code.status, CodeStatus.AVAILABLE)

    def test_void(self):
        code = RedemptionCodeFactory()
        code.void(reason="Admin voided.")
        code.refresh_from_db()
        self.assertEqual(code.status, CodeStatus.VOIDED)
        self.assertIn("Admin voided.", code.metadata.get("void_reason", ""))


class UserInventoryModelTests(TestCase):

    def test_is_delivered(self):
        inv = UserInventoryFactory(status=InventoryStatus.DELIVERED)
        self.assertTrue(inv.is_delivered)

    def test_is_claimable_when_delivered_no_expiry(self):
        inv = UserInventoryFactory(status=InventoryStatus.DELIVERED, expires_at=None)
        self.assertTrue(inv.is_claimable)

    def test_is_claimable_false_when_expired(self):
        inv = UserInventoryFactory(
            status=InventoryStatus.DELIVERED,
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertFalse(inv.is_claimable)

    def test_mark_delivered(self):
        inv = UserInventoryFactory(status=InventoryStatus.PENDING, delivered_at=None)
        inv.mark_delivered()
        inv.refresh_from_db()
        self.assertEqual(inv.status, InventoryStatus.DELIVERED)
        self.assertIsNotNone(inv.delivered_at)

    def test_mark_claimed(self):
        inv = UserInventoryFactory(status=InventoryStatus.DELIVERED)
        inv.mark_claimed()
        inv.refresh_from_db()
        self.assertEqual(inv.status, InventoryStatus.CLAIMED)
        self.assertIsNotNone(inv.claimed_at)

    def test_mark_failed(self):
        inv = UserInventoryFactory(status=InventoryStatus.PENDING, delivery_attempts=0)
        inv.mark_failed(error="SMTP error.", next_retry_at=timezone.now())
        inv.refresh_from_db()
        self.assertEqual(inv.status, InventoryStatus.FAILED)
        self.assertEqual(inv.delivery_error, "SMTP error.")

    def test_revoke(self):
        inv = UserInventoryFactory()
        admin = UserFactory(is_staff=True)
        inv.revoke(reason="Fraud detected.", revoked_by=admin)
        inv.refresh_from_db()
        self.assertEqual(inv.status, InventoryStatus.REVOKED)
        self.assertIsNotNone(inv.revoked_at)

    def test_revoke_already_revoked_raises(self):
        inv = RevokedInventoryFactory()
        with self.assertRaises(InventoryRevokedException):
            inv.revoke(reason="Double revoke attempt.")
