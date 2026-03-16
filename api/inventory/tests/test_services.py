"""test_services.py – Unit tests for inventory services."""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from inventory.choices import CodeStatus, InventoryStatus, ItemStatus
from inventory.constants import UNLIMITED_STOCK, MAX_QUANTITY_PER_USER_PER_ITEM
from inventory.exceptions import (
    BulkImportException,
    InsufficientStockException,
    ItemNotActiveException,
    ItemNotFoundException,
    ItemQuantityLimitExceededException,
    NoCodesAvailableException,
    StockAdjustmentException,
    UserInventoryNotFoundException,
)
from inventory.models import RedemptionCode, RewardItem, StockEvent, UserInventory
from inventory.services import (
    adjust_stock,
    award_item_to_user,
    bulk_import_codes,
    generate_and_import_codes,
    restock_item,
    revoke_inventory,
)
from .factories import (
    RedemptionCodeFactory,
    RewardItemFactory,
    UnlimitedItemFactory,
    UserFactory,
    UserInventoryFactory,
    VoucherItemFactory,
)


class RestockItemTests(TestCase):

    def test_restock_increases_stock_and_creates_event(self):
        item = RewardItemFactory(current_stock=10)
        updated = restock_item(item.pk, quantity=20)
        self.assertEqual(updated.current_stock, 30)
        event = StockEvent.objects.filter(item=item, event_type="restock").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.quantity_delta, 20)

    def test_restock_unlimited_item_does_not_change_stock(self):
        item = UnlimitedItemFactory()
        updated = restock_item(item.pk, quantity=100)
        self.assertEqual(updated.current_stock, UNLIMITED_STOCK)

    def test_restock_invalid_quantity_raises(self):
        item = RewardItemFactory()
        with self.assertRaises(StockAdjustmentException):
            restock_item(item.pk, quantity=0)

    def test_restock_nonexistent_item_raises(self):
        import uuid
        with self.assertRaises(RewardItem.DoesNotExist):
            restock_item(uuid.uuid4(), quantity=10)


class AdjustStockTests(TestCase):

    def test_positive_adjustment(self):
        item = RewardItemFactory(current_stock=10)
        updated = adjust_stock(item.pk, delta=5)
        self.assertEqual(updated.current_stock, 15)

    def test_negative_adjustment(self):
        item = RewardItemFactory(current_stock=10)
        updated = adjust_stock(item.pk, delta=-3)
        self.assertEqual(updated.current_stock, 7)

    def test_adjustment_would_go_negative_raises(self):
        item = RewardItemFactory(current_stock=5)
        with self.assertRaises(Exception):  # ValidationError from validator
            adjust_stock(item.pk, delta=-10)

    def test_reduce_unlimited_raises(self):
        item = UnlimitedItemFactory()
        with self.assertRaises(StockAdjustmentException):
            adjust_stock(item.pk, delta=-5)


class BulkImportCodesTests(TestCase):

    def _valid_codes(self, count: int):
        import random, string
        charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        codes = set()
        while len(codes) < count:
            codes.add("".join(random.choices(charset, k=16)))
        return list(codes)

    def test_imports_valid_codes(self):
        item = VoucherItemFactory(current_stock=0)
        codes = self._valid_codes(5)
        count = bulk_import_codes(item.pk, codes)
        self.assertEqual(count, 5)
        self.assertEqual(RedemptionCode.objects.filter(item=item).count(), 5)

    def test_skips_duplicate_db_codes(self):
        item = VoucherItemFactory(current_stock=0)
        codes = self._valid_codes(3)
        bulk_import_codes(item.pk, codes[:2])
        # Re-import first 2 + 1 new
        count = bulk_import_codes(item.pk, codes)
        self.assertEqual(count, 1)  # only new one imported

    def test_empty_list_raises(self):
        item = VoucherItemFactory()
        with self.assertRaises(BulkImportException):
            bulk_import_codes(item.pk, [])

    def test_all_duplicates_raises(self):
        item = VoucherItemFactory(current_stock=0)
        codes = self._valid_codes(2)
        bulk_import_codes(item.pk, codes)
        with self.assertRaises(BulkImportException):
            bulk_import_codes(item.pk, codes)

    def test_nonexistent_item_raises(self):
        import uuid
        with self.assertRaises(ItemNotFoundException):
            bulk_import_codes(uuid.uuid4(), self._valid_codes(1))


class AwardItemTests(TestCase):

    def setUp(self):
        self.user = UserFactory()
        self.item = RewardItemFactory(current_stock=10)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_creates_inventory_and_decrements_stock(self, mock_task):
        mock_task.delay = MagicMock()
        inv = award_item_to_user(self.user, self.item.pk)
        self.assertIsInstance(inv, UserInventory)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, 9)
        self.assertEqual(self.item.total_redeemed, 1)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_inactive_item_raises(self, mock_task):
        item = RewardItemFactory(status=ItemStatus.PAUSED)
        with self.assertRaises(ItemNotActiveException):
            award_item_to_user(self.user, item.pk)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_out_of_stock_raises(self, mock_task):
        item = RewardItemFactory(current_stock=0)
        with self.assertRaises(InsufficientStockException):
            award_item_to_user(self.user, item.pk)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_exceeds_per_user_limit_raises(self, mock_task):
        mock_task.delay = MagicMock()
        item = RewardItemFactory(current_stock=50, max_per_user=1)
        # Create existing active inventory up to the global limit
        for _ in range(MAX_QUANTITY_PER_USER_PER_ITEM):
            UserInventoryFactory(user=self.user, item=item)
        with self.assertRaises(ItemQuantityLimitExceededException):
            award_item_to_user(self.user, item.pk)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_code_item_assigns_code(self, mock_task):
        mock_task.delay = MagicMock()
        item = VoucherItemFactory(current_stock=5)
        code = RedemptionCodeFactory(item=item)
        inv = award_item_to_user(self.user, item.pk)
        self.assertIsNotNone(inv.redemption_code)

    @patch("inventory.services.deliver_inventory_item")
    def test_award_code_item_no_codes_raises(self, mock_task):
        mock_task.delay = MagicMock()
        item = VoucherItemFactory(current_stock=5)
        # No codes created
        with self.assertRaises(NoCodesAvailableException):
            award_item_to_user(self.user, item.pk)


class RevokeInventoryTests(TestCase):

    @patch("inventory.services.deliver_inventory_item")
    def test_revoke_restores_stock(self, mock_task):
        mock_task.delay = MagicMock()
        item = RewardItemFactory(current_stock=5)
        inv = UserInventoryFactory(item=item)
        admin = UserFactory(is_staff=True)
        stock_before = item.current_stock
        revoke_inventory(inv.pk, reason="Test revoke.", revoked_by=admin)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, stock_before + 1)

    def test_revoke_nonexistent_raises(self):
        import uuid
        with self.assertRaises(UserInventoryNotFoundException):
            revoke_inventory(uuid.uuid4(), reason="oops")
