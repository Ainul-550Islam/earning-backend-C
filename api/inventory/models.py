"""
models.py – Inventory module data layer.

Design decisions:
  • current_stock lives on RewardItem for fast reads (hot path).
    StockManager holds the audit log and threshold configuration.
  • SELECT FOR UPDATE used inside services for stock decrements to prevent
    oversell under concurrent load.
  • RedemptionCode is a separate model so codes can be bulk-imported and
    assigned atomically without touching the item row.
  • UserInventory is the fulfilment receipt – one row per item awarded to a user.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    CodeStatus,
    DeliveryMethod,
    InventoryStatus,
    ItemStatus,
    ItemType,
    StockAlertLevel,
    StockEventType,
)
from .constants import (
    DEFAULT_CRITICAL_STOCK_THRESHOLD,
    DEFAULT_LOW_STOCK_THRESHOLD,
    UNLIMITED_STOCK,
)
from .managers import RedemptionCodeManager, RewardItemManager, UserInventoryManager
from .validators import (
    validate_future_expiry_date,
    validate_non_negative_stock,
    validate_positive_points_cost,
    validate_low_stock_threshold,
)


class TimeStampedModel(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ── RewardItem ────────────────────────────────────────────────────────────────

class RewardItem(TimeStampedModel):
    """
    A redeemable reward that can be awarded to users.
    Supports physical products, digital codes, vouchers, and point top-ups.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=200, unique=True)
    description = models.TextField(_("description"), blank=True)
    item_type = models.CharField(
        _("item type"),
        max_length=30,
        choices=ItemType.choices,
        default=ItemType.DIGITAL,
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=30,
        choices=ItemStatus.choices,
        default=ItemStatus.DRAFT,
        db_index=True,
    )

    # ── Pricing ───────────────────────────────────────────────────────────────
    points_cost = models.PositiveIntegerField(
        _("points cost"),
        default=0,
        validators=[validate_positive_points_cost],
        help_text=_("Points required to redeem this item. 0 = free."),
    )
    cash_value = models.DecimalField(
        _("cash value"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Real-world monetary value for accounting purposes."),
    )

    # ── Stock ─────────────────────────────────────────────────────────────────
    current_stock = models.IntegerField(
        _("current stock"),
        default=0,
        validators=[validate_non_negative_stock],
        db_index=True,
        help_text=_(f"Use {UNLIMITED_STOCK} for unlimited stock."),
    )
    total_redeemed = models.PositiveIntegerField(_("total redeemed"), default=0)

    # ── Delivery ──────────────────────────────────────────────────────────────
    delivery_method = models.CharField(
        _("delivery method"),
        max_length=30,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.EMAIL,
    )
    delivery_template = models.TextField(
        _("delivery template"),
        blank=True,
        help_text=_("Jinja2 template for email/SMS delivery body."),
    )
    delivery_callback_url = models.URLField(
        _("delivery callback URL"),
        blank=True,
        help_text=_("For API delivery method: POST to this URL on fulfilment."),
    )

    # ── Limits ────────────────────────────────────────────────────────────────
    max_per_user = models.PositiveSmallIntegerField(
        _("max per user"),
        default=1,
        help_text=_("Maximum times a single user can redeem this item."),
    )
    is_transferable = models.BooleanField(_("transferable"), default=False)
    requires_shipping_address = models.BooleanField(
        _("requires shipping address"), default=False
    )

    # ── Presentation ─────────────────────────────────────────────────────────
    image_url = models.URLField(_("image URL"), blank=True)
    thumbnail_url = models.URLField(_("thumbnail URL"), blank=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    is_featured = models.BooleanField(_("featured"), default=False)
    tags = models.JSONField(_("tags"), default=list, blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = RewardItemManager()

    class Meta:
        verbose_name = _("reward item")
        verbose_name_plural = _("reward items")
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["status", "item_type"]),
            models.Index(fields=["status", "current_stock"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.get_item_type_display()}] (stock={self.current_stock})"

    # ── Derived Properties ────────────────────────────────────────────────────

    @property
    def is_unlimited(self) -> bool:
        return self.current_stock == UNLIMITED_STOCK

    @property
    def is_in_stock(self) -> bool:
        return self.is_unlimited or self.current_stock > 0

    @property
    def is_active(self) -> bool:
        return self.status == ItemStatus.ACTIVE

    @property
    def uses_codes(self) -> bool:
        return self.item_type in (ItemType.DIGITAL, ItemType.VOUCHER)

    # ── Stock Mutation Helpers (use within atomic transactions) ───────────────

    def decrement_stock(self, qty: int = 1) -> None:
        """
        Decrease current_stock by qty.
        Must be called inside a SELECT FOR UPDATE block.
        Raises InsufficientStockException if stock would go negative.
        """
        from .exceptions import InsufficientStockException
        if self.is_unlimited:
            return
        if self.current_stock < qty:
            raise InsufficientStockException(
                detail=(
                    f"Only {self.current_stock} unit(s) of '{self.name}' available; "
                    f"{qty} requested."
                )
            )
        self.current_stock = models.F("current_stock") - qty
        self.total_redeemed = models.F("total_redeemed") + qty
        self.save(update_fields=["current_stock", "total_redeemed", "updated_at"])
        self.refresh_from_db(fields=["current_stock", "total_redeemed"])

    def increment_stock(self, qty: int) -> None:
        """Increase current_stock by qty (restock / return)."""
        if self.is_unlimited:
            return
        if qty <= 0:
            raise ValueError(f"Restock quantity must be positive. Got {qty}.")
        self.current_stock = models.F("current_stock") + qty
        self.save(update_fields=["current_stock", "updated_at"])
        self.refresh_from_db(fields=["current_stock"])


# ── StockManager ─────────────────────────────────────────────────────────────

class StockManager(TimeStampedModel):
    """
    Per-item stock configuration and audit log holder.
    One StockManager per RewardItem (OneToOne).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.OneToOneField(
        RewardItem,
        on_delete=models.CASCADE,
        related_name="stock_manager",
        verbose_name=_("item"),
    )
    low_stock_threshold = models.PositiveSmallIntegerField(
        _("low-stock threshold"),
        default=DEFAULT_LOW_STOCK_THRESHOLD,
        validators=[validate_low_stock_threshold],
    )
    critical_stock_threshold = models.PositiveSmallIntegerField(
        _("critical-stock threshold"),
        default=DEFAULT_CRITICAL_STOCK_THRESHOLD,
        validators=[validate_low_stock_threshold],
    )
    alert_level = models.CharField(
        _("alert level"),
        max_length=20,
        choices=StockAlertLevel.choices,
        default=StockAlertLevel.NONE,
        db_index=True,
    )
    alert_sent = models.BooleanField(_("alert sent"), default=False)
    alert_sent_at = models.DateTimeField(_("alert sent at"), null=True, blank=True)
    reorder_quantity = models.PositiveIntegerField(
        _("reorder quantity"),
        default=100,
        help_text=_("Suggested restock quantity when low-stock alert fires."),
    )
    notes = models.TextField(_("internal notes"), blank=True)

    class Meta:
        verbose_name = _("stock manager")
        verbose_name_plural = _("stock managers")

    def __str__(self) -> str:
        return f"StockManager for {self.item.name}"

    def evaluate_alert_level(self) -> StockAlertLevel:
        """Compute alert level from current stock. Does NOT save."""
        stock = self.item.current_stock
        if self.item.is_unlimited:
            return StockAlertLevel.NONE
        if stock <= 0:
            return StockAlertLevel.DEPLETED
        if stock <= self.critical_stock_threshold:
            return StockAlertLevel.CRITICAL
        if stock <= self.low_stock_threshold:
            return StockAlertLevel.LOW
        return StockAlertLevel.NONE

    def update_alert_level(self) -> bool:
        """Re-evaluate and persist alert level. Returns True if level changed."""
        new_level = self.evaluate_alert_level()
        if new_level != self.alert_level:
            self.alert_level = new_level
            self.alert_sent = False  # reset so alert fires again
            self.save(update_fields=["alert_level", "alert_sent", "updated_at"])
            return True
        return False


class StockEvent(TimeStampedModel):
    """
    Immutable audit trail for every stock mutation.
    Never deleted – write once.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        RewardItem,
        on_delete=models.PROTECT,
        related_name="stock_events",
        verbose_name=_("item"),
        db_index=True,
    )
    event_type = models.CharField(
        _("event type"),
        max_length=30,
        choices=StockEventType.choices,
        db_index=True,
    )
    quantity_delta = models.IntegerField(
        _("quantity delta"),
        help_text=_("Positive = added, negative = removed."),
    )
    stock_before = models.IntegerField(_("stock before"))
    stock_after = models.IntegerField(_("stock after"))
    reference_id = models.CharField(
        _("reference ID"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("UserInventory UUID, order ID, or other reference."),
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_events",
        verbose_name=_("performed by"),
    )
    note = models.TextField(_("note"), blank=True)

    class Meta:
        verbose_name = _("stock event")
        verbose_name_plural = _("stock events")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item", "event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_event_type_display()} | {self.item.name} | "
            f"Δ{self.quantity_delta:+d} → {self.stock_after}"
        )


# ── RedemptionCode ────────────────────────────────────────────────────────────

class RedemptionCode(TimeStampedModel):
    """
    A single-use code tied to a RewardItem.
    Codes are pre-loaded and assigned to users at redemption time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        RewardItem,
        on_delete=models.CASCADE,
        related_name="redemption_codes",
        verbose_name=_("item"),
        db_index=True,
    )
    code = models.CharField(
        _("code"),
        max_length=100,
        unique=True,
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=CodeStatus.choices,
        default=CodeStatus.AVAILABLE,
        db_index=True,
    )
    batch_id = models.CharField(
        _("batch ID"),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_("Group identifier for bulk-imported codes."),
    )
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        db_index=True,
        validators=[validate_future_expiry_date],
    )
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redeemed_codes",
        verbose_name=_("redeemed by"),
    )
    redeemed_at = models.DateTimeField(_("redeemed at"), null=True, blank=True)
    reserved_until = models.DateTimeField(
        _("reserved until"),
        null=True,
        blank=True,
        help_text=_("Temporary reservation expiry during checkout."),
    )
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = RedemptionCodeManager()

    class Meta:
        verbose_name = _("redemption code")
        verbose_name_plural = _("redemption codes")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["item", "status"]),
            models.Index(fields=["code"]),
            models.Index(fields=["batch_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} [{self.get_status_display()}] – {self.item.name}"

    @property
    def is_available(self) -> bool:
        return (
            self.status == CodeStatus.AVAILABLE
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def mark_redeemed(self, user) -> None:
        self.status = CodeStatus.REDEEMED
        self.redeemed_by = user
        self.redeemed_at = timezone.now()
        self.reserved_until = None
        self.save(update_fields=["status", "redeemed_by", "redeemed_at", "reserved_until", "updated_at"])

    def reserve(self, ttl_seconds: int) -> None:
        self.status = CodeStatus.RESERVED
        self.reserved_until = timezone.now() + timezone.timedelta(seconds=ttl_seconds)
        self.save(update_fields=["status", "reserved_until", "updated_at"])

    def release_reservation(self) -> None:
        if self.status == CodeStatus.RESERVED:
            self.status = CodeStatus.AVAILABLE
            self.reserved_until = None
            self.save(update_fields=["status", "reserved_until", "updated_at"])

    def void(self, reason: str = "") -> None:
        self.status = CodeStatus.VOIDED
        if reason:
            self.metadata["void_reason"] = reason
        self.save(update_fields=["status", "metadata", "updated_at"])


# ── UserInventory ─────────────────────────────────────────────────────────────

class UserInventory(TimeStampedModel):
    """
    Fulfilment receipt – records a reward item awarded to a specific user.
    Every redemption or automated award creates one row here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory",
        verbose_name=_("user"),
        db_index=True,
    )
    item = models.ForeignKey(
        RewardItem,
        on_delete=models.PROTECT,
        related_name="user_inventories",
        verbose_name=_("item"),
    )
    redemption_code = models.OneToOneField(
        RedemptionCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_inventory",
        verbose_name=_("redemption code"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=InventoryStatus.choices,
        default=InventoryStatus.PENDING,
        db_index=True,
    )
    delivery_method = models.CharField(
        _("delivery method"),
        max_length=30,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.EMAIL,
    )

    # ── Delivery Tracking ─────────────────────────────────────────────────────
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    claimed_at = models.DateTimeField(_("claimed at"), null=True, blank=True)
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        db_index=True,
    )
    delivery_attempts = models.PositiveSmallIntegerField(_("delivery attempts"), default=0)
    last_delivery_attempt_at = models.DateTimeField(
        _("last delivery attempt at"), null=True, blank=True
    )
    delivery_error = models.TextField(_("delivery error"), blank=True)
    next_retry_at = models.DateTimeField(
        _("next retry at"),
        null=True,
        blank=True,
        db_index=True,
    )

    # ── Revocation ────────────────────────────────────────────────────────────
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    revocation_reason = models.TextField(_("revocation reason"), blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_inventories",
        verbose_name=_("revoked by"),
    )

    # ── Context ───────────────────────────────────────────────────────────────
    awarded_by_postback = models.CharField(
        _("postback reference"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Postback log ID or campaign reference that triggered this award."),
    )
    notes = models.TextField(_("internal notes"), blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = UserInventoryManager()

    class Meta:
        verbose_name = _("user inventory")
        verbose_name_plural = _("user inventories")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "item"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} → {self.item.name} [{self.get_status_display()}]"

    # ── Status Helpers ────────────────────────────────────────────────────────

    @property
    def is_delivered(self) -> bool:
        return self.status == InventoryStatus.DELIVERED

    @property
    def is_claimable(self) -> bool:
        return self.status == InventoryStatus.DELIVERED and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    @property
    def is_revoked(self) -> bool:
        return self.status == InventoryStatus.REVOKED

    def mark_delivered(self) -> None:
        self.status = InventoryStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.delivery_error = ""
        self.save(update_fields=["status", "delivered_at", "delivery_error", "updated_at"])

    def mark_claimed(self) -> None:
        self.status = InventoryStatus.CLAIMED
        self.claimed_at = timezone.now()
        self.save(update_fields=["status", "claimed_at", "updated_at"])

    def mark_failed(self, error: str = "", next_retry_at=None) -> None:
        self.status = InventoryStatus.FAILED
        self.delivery_error = error
        self.delivery_attempts += 1
        self.last_delivery_attempt_at = timezone.now()
        self.next_retry_at = next_retry_at
        self.save(update_fields=[
            "status", "delivery_error", "delivery_attempts",
            "last_delivery_attempt_at", "next_retry_at", "updated_at",
        ])

    def revoke(self, reason: str, revoked_by=None) -> None:
        from .exceptions import InventoryRevokedException
        if self.is_revoked:
            raise InventoryRevokedException(detail="Inventory entry is already revoked.")
        self.status = InventoryStatus.REVOKED
        self.revoked_at = timezone.now()
        self.revocation_reason = reason
        self.revoked_by = revoked_by
        self.save(update_fields=[
            "status", "revoked_at", "revocation_reason", "revoked_by", "updated_at"
        ])

    def increment_delivery_attempt(self, error: str, backoff_seconds: int) -> None:
        self.delivery_attempts += 1
        self.last_delivery_attempt_at = timezone.now()
        self.delivery_error = error
        self.next_retry_at = timezone.now() + timezone.timedelta(seconds=backoff_seconds)
        self.save(update_fields=[
            "delivery_attempts", "last_delivery_attempt_at",
            "delivery_error", "next_retry_at", "updated_at",
        ])
