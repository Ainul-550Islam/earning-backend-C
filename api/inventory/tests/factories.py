"""factories.py – Factory Boy factories for inventory tests."""
import factory
import factory.fuzzy
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory.choices import (
    CodeStatus,
    DeliveryMethod,
    InventoryStatus,
    ItemStatus,
    ItemType,
)
from inventory.constants import UNLIMITED_STOCK
from inventory.models import (
    RedemptionCode,
    RewardItem,
    StockEvent,
    StockManager,
    UserInventory,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "pass1234")
    is_active = True


class RewardItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RewardItem
    name = factory.Sequence(lambda n: f"Item {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    item_type = ItemType.DIGITAL
    status = ItemStatus.ACTIVE
    points_cost = 100
    cash_value = Decimal("5.00")
    current_stock = 50
    delivery_method = DeliveryMethod.EMAIL
    max_per_user = 1


class UnlimitedItemFactory(RewardItemFactory):
    current_stock = UNLIMITED_STOCK
    item_type = ItemType.POINTS


class OutOfStockItemFactory(RewardItemFactory):
    current_stock = 0
    status = ItemStatus.OUT_OF_STOCK


class PhysicalItemFactory(RewardItemFactory):
    item_type = ItemType.PHYSICAL
    delivery_method = DeliveryMethod.PHYSICAL_SHIPMENT
    requires_shipping_address = True


class VoucherItemFactory(RewardItemFactory):
    item_type = ItemType.VOUCHER
    delivery_method = DeliveryMethod.EMAIL


class StockManagerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StockManager
    item = factory.SubFactory(RewardItemFactory)
    low_stock_threshold = 10
    critical_stock_threshold = 3
    reorder_quantity = 100


class RedemptionCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RedemptionCode
    item = factory.SubFactory(VoucherItemFactory)
    code = factory.Sequence(lambda n: f"TESTCODE{n:08d}")
    status = CodeStatus.AVAILABLE
    batch_id = "test-batch"


class ExpiredCodeFactory(RedemptionCodeFactory):
    status = CodeStatus.EXPIRED
    expires_at = factory.LazyFunction(
        lambda: timezone.now() - timezone.timedelta(days=1)
    )


class RedeemedCodeFactory(RedemptionCodeFactory):
    status = CodeStatus.REDEEMED
    redeemed_at = factory.LazyFunction(timezone.now)
    redeemed_by = factory.SubFactory(UserFactory)


class UserInventoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserInventory
    user = factory.SubFactory(UserFactory)
    item = factory.SubFactory(RewardItemFactory)
    status = InventoryStatus.DELIVERED
    delivery_method = DeliveryMethod.EMAIL
    delivered_at = factory.LazyFunction(timezone.now)
    delivery_attempts = 1


class PendingInventoryFactory(UserInventoryFactory):
    status = InventoryStatus.PENDING
    delivered_at = None
    delivery_attempts = 0


class FailedInventoryFactory(UserInventoryFactory):
    status = InventoryStatus.FAILED
    delivery_attempts = 1
    delivery_error = "SMTP connection refused."
    next_retry_at = factory.LazyFunction(
        lambda: timezone.now() - timezone.timedelta(minutes=5)
    )


class RevokedInventoryFactory(UserInventoryFactory):
    status = InventoryStatus.REVOKED
    revoked_at = factory.LazyFunction(timezone.now)
    revocation_reason = "Fraudulent redemption."
