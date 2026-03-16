import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── QuerySets ─────────────────────────────────────────────────────────────────

class RewardItemQuerySet(models.QuerySet):
    def active(self):
        from .choices import ItemStatus
        return self.filter(status=ItemStatus.ACTIVE)

    def by_type(self, item_type):
        return self.filter(item_type=item_type)

    def in_stock(self):
        """Items that have stock > 0 or unlimited stock (-1)."""
        from .constants import UNLIMITED_STOCK
        return self.filter(
            models.Q(current_stock__gt=0) | models.Q(current_stock=UNLIMITED_STOCK)
        )

    def low_stock(self):
        """Items below their own low-stock threshold (but not unlimited)."""
        from .constants import UNLIMITED_STOCK
        return self.exclude(current_stock=UNLIMITED_STOCK).filter(
            current_stock__gt=0,
            current_stock__lte=models.F("low_stock_threshold"),
        )

    def critical_stock(self):
        from .constants import UNLIMITED_STOCK
        return self.exclude(current_stock=UNLIMITED_STOCK).filter(
            current_stock__gt=0,
            current_stock__lte=models.F("critical_stock_threshold"),
        )

    def out_of_stock(self):
        from .constants import UNLIMITED_STOCK
        return self.exclude(current_stock=UNLIMITED_STOCK).filter(current_stock__lte=0)

    def redeemable_by_user(self, user):
        """Active items in stock that the user has not exceeded quantity limits for."""
        return self.active().in_stock()

    def with_stock_manager(self):
        return self.select_related("stock_manager")


class StockManagerQuerySet(models.QuerySet):
    def needing_alert(self):
        from .choices import StockAlertLevel
        return self.exclude(alert_level=StockAlertLevel.NONE)

    def unsent_alerts(self):
        return self.needing_alert().filter(alert_sent=False)


class RedemptionCodeQuerySet(models.QuerySet):
    def available(self):
        from .choices import CodeStatus
        return self.filter(status=CodeStatus.AVAILABLE)

    def for_item(self, item):
        return self.filter(item=item)

    def expired(self):
        from .choices import CodeStatus
        return self.filter(
            models.Q(status=CodeStatus.EXPIRED) |
            models.Q(expires_at__lt=timezone.now(), status=CodeStatus.AVAILABLE)
        )

    def expiring_soon(self, days=7):
        from .choices import CodeStatus
        threshold = timezone.now() + timezone.timedelta(days=days)
        return self.filter(
            status=CodeStatus.AVAILABLE,
            expires_at__lte=threshold,
            expires_at__gt=timezone.now(),
        )

    def redeemed(self):
        from .choices import CodeStatus
        return self.filter(status=CodeStatus.REDEEMED)

    def get_next_available(self, item):
        """Atomically claim the next available code for item."""
        return self.select_for_update(skip_locked=True).available().for_item(item).first()


class UserInventoryQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def delivered(self):
        from .choices import InventoryStatus
        return self.filter(status=InventoryStatus.DELIVERED)

    def pending(self):
        from .choices import InventoryStatus
        return self.filter(status=InventoryStatus.PENDING)

    def failed(self):
        from .choices import InventoryStatus
        return self.filter(status=InventoryStatus.FAILED)

    def active(self):
        from .choices import InventoryStatus
        return self.filter(
            status__in=[
                InventoryStatus.PENDING,
                InventoryStatus.DELIVERED,
                InventoryStatus.CLAIMED,
            ]
        )

    def expiring_soon(self, days=7):
        from .choices import InventoryStatus
        threshold = timezone.now() + timezone.timedelta(days=days)
        return self.filter(
            status=InventoryStatus.DELIVERED,
            expires_at__lte=threshold,
            expires_at__gt=timezone.now(),
        )

    def retryable(self):
        from .choices import InventoryStatus
        from .constants import MAX_DELIVERY_RETRY_ATTEMPTS
        return self.filter(
            status=InventoryStatus.FAILED,
            delivery_attempts__lt=MAX_DELIVERY_RETRY_ATTEMPTS,
        )

    def with_item(self):
        return self.select_related("item", "redemption_code")


# ── Managers ─────────────────────────────────────────────────────────────────

class RewardItemManager(models.Manager):
    def get_queryset(self):
        return RewardItemQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def in_stock(self):
        return self.get_queryset().in_stock()

    def low_stock(self):
        return self.get_queryset().low_stock()

    def with_stock_manager(self):
        return self.get_queryset().with_stock_manager()
    def with_stock_manager(self):
        return self.get_queryset().with_stock_manager()
    def get_active_or_raise(self, pk):
        from .exceptions import ItemNotFoundException, ItemNotActiveException
        from .choices import ItemStatus
        try:
            item = self.get(pk=pk)
        except self.model.DoesNotExist:
            raise ItemNotFoundException()
        if item.status != ItemStatus.ACTIVE:
            raise ItemNotActiveException(detail=f"Item '{item.name}' is not active.")
        return item


class RedemptionCodeManager(models.Manager):
    def get_queryset(self):
        return RedemptionCodeQuerySet(self.model, using=self._db)

    def available_for_item(self, item):
        return self.get_queryset().available().for_item(item)

    def get_next_available(self, item):
        return self.get_queryset().get_next_available(item)


class UserInventoryManager(models.Manager):
    def get_queryset(self):
        return UserInventoryQuerySet(self.model, using=self._db)
    def with_item(self):
        return self.get_queryset().with_item()

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def retryable(self):
        return self.get_queryset().retryable()
