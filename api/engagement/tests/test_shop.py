# engagement/tests/test_shop.py
import pytest
from decimal import Decimal

from ..services.shop_service import ShopService
from ..models.shop import ShopItem, ShopPurchase, UserInventory
from ..exceptions import InsufficientCoinsError, ItemNotAvailableError
from .factories import UserFactory, ShopItemFactory


@pytest.mark.django_db
class TestShopService:

    def test_purchase_deducts_coins(self):
        user = UserFactory(coin_balance=Decimal("200"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug)
        user.refresh_from_db()
        assert user.coin_balance == Decimal("150")

    def test_purchase_creates_purchase_record(self):
        user = UserFactory(coin_balance=Decimal("200"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug)
        assert ShopPurchase.objects.filter(user=user, item=item).exists()

    def test_purchase_adds_to_inventory(self):
        user = UserFactory(coin_balance=Decimal("200"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug)
        inv = UserInventory.objects.get(user=user, item=item)
        assert inv.quantity == 1

    def test_purchase_multiple_quantity(self):
        user = UserFactory(coin_balance=Decimal("500"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug, quantity=3)
        user.refresh_from_db()
        assert user.coin_balance == Decimal("350")
        inv = UserInventory.objects.get(user=user, item=item)
        assert inv.quantity == 3

    def test_purchase_insufficient_coins_raises(self):
        user = UserFactory(coin_balance=Decimal("10"))
        item = ShopItemFactory(price_coins=Decimal("100"), stock=-1)
        with pytest.raises(InsufficientCoinsError):
            ShopService.purchase(user, item.slug)

    def test_purchase_inactive_item_raises(self):
        user = UserFactory(coin_balance=Decimal("500"))
        item = ShopItemFactory(price_coins=Decimal("50"), is_active=False, stock=-1)
        with pytest.raises(ItemNotAvailableError):
            ShopService.purchase(user, item.slug)

    def test_purchase_out_of_stock_raises(self):
        user = UserFactory(coin_balance=Decimal("500"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=0)
        with pytest.raises(ItemNotAvailableError):
            ShopService.purchase(user, item.slug)

    def test_purchase_reduces_limited_stock(self):
        user = UserFactory(coin_balance=Decimal("500"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=5)
        ShopService.purchase(user, item.slug)
        item.refresh_from_db()
        assert item.stock == 4

    def test_inventory_returns_active_items(self):
        user = UserFactory(coin_balance=Decimal("200"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug)
        inventory = ShopService.inventory(user)
        assert len(inventory) == 1
        assert inventory[0].item.pk == item.pk

    def test_available_items_filters_inactive(self):
        ShopItemFactory(is_active=True)
        ShopItemFactory(is_active=False)
        items = ShopService.available_items()
        assert all(i.is_active for i in items)

    def test_second_purchase_increments_inventory(self):
        user = UserFactory(coin_balance=Decimal("500"))
        item = ShopItemFactory(price_coins=Decimal("50"), stock=-1)
        ShopService.purchase(user, item.slug, quantity=2)
        ShopService.purchase(user, item.slug, quantity=1)
        inv = UserInventory.objects.get(user=user, item=item)
        assert inv.quantity == 3
