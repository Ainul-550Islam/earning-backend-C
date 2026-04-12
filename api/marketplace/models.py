"""
marketplace/models.py — All Marketplace Database Models
=========================================================
Required Classes:
  🛍️  Product & Inventory: Product, ProductVariant, ProductInventory,
       Category, ProductAttribute
  👥  Seller & Store:  SellerProfile, SellerVerification, SellerPayout,
       CommissionConfig
  🛒  Order & Cart:    Cart, CartItem, Order, OrderItem, OrderTracking
  💳  Payment:         PaymentTransaction, EscrowHolding, RefundRequest
  🎁  Marketing:       Coupon, ProductReview, PromotionCampaign
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

from api.tenants.models import Tenant
from .enums import (
    ProductStatus, ProductCondition,
    SellerStatus, VerificationStatus, PayoutStatus,
    OrderStatus, TrackingEvent,
    PaymentMethod, PaymentStatus, EscrowStatus,
    RefundStatus, RefundReason,
    CouponType, PromotionType,
    DisputeStatus, DisputeType,
    ShippingStatus,
)
from .constants import (
    MIN_RATING, MAX_RATING,
    DEFAULT_COMMISSION_RATE, LOW_STOCK_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────────────────────
# MIXIN
# ─────────────────────────────────────────────────────────────────────────────
class TenantMixin(models.Model):
    """Multi-tenant isolation — present in every marketplace model."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_tenant",
        db_index=True,
    )

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ═════════════════════════════════════════════════════════════════════════════
# 🛍️  PRODUCT & INVENTORY
# ═════════════════════════════════════════════════════════════════════════════

class Category(TenantMixin, TimestampMixin):
    """
    মাল্টি-লেভেল ক্যাটাগরি ট্রি (Parent-Child relationship)।
    যেমন: Electronics → Mobile → Smartphone
    """

    name = models.CharField(max_length=200, verbose_name=_("Category Name"))
    slug = models.SlugField(max_length=220, db_index=True, null=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="marketplace/categories/", null=True, blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Icon class or emoji", null=True)

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent Category"),
    )

    level = models.PositiveSmallIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_category"
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["sort_order", "name"]
        unique_together = [("tenant", "slug")]

    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def full_path(self):
        """Electronics > Mobile > Smartphone"""
        parts = [self.name]
        node = self.parent
        while node:
            parts.insert(0, node.name)
            node = node.parent
        return " > ".join(parts)


class Product(TenantMixin, TimestampMixin):
    """
    মেইন প্রোডাক্ট টেবিল (Name, Description, Base Price)।
    একটি প্রোডাক্টের একাধিক Variant থাকতে পারে।
    """

    seller = models.ForeignKey(
        "marketplace.SellerProfile",
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name=_("Seller"),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="products",)

    name = models.CharField(max_length=500, verbose_name=_("Product Name"))
    slug = models.SlugField(max_length=520, db_index=True, null=True, blank=True)
    description = models.TextField(verbose_name=_("Description"))
    short_description = models.CharField(max_length=500, null=True, blank=True)

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("Base Price (BDT)"),
    )
    sale_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name=_("Sale Price")
    )

    condition = models.CharField(
        max_length=20,
        choices=ProductCondition.choices,
        default=ProductCondition.NEW,)
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT,
        db_index=True,)

    # SEO
    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags", null=True)

    # Flags
    is_featured = models.BooleanField(default=False, db_index=True)
    is_digital = models.BooleanField(default=False)
    requires_shipping = models.BooleanField(default=True)

    # Aggregates (denormalised for speed)
    total_sales = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "is_featured"]),
            models.Index(fields=["seller", "status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def effective_price(self):
        return self.sale_price if self.sale_price else self.base_price

    @property
    def discount_percent(self):
        if self.sale_price and self.sale_price < self.base_price:
            return round((1 - self.sale_price / self.base_price) * 100, 1)
        return 0


class ProductVariant(TenantMixin, TimestampMixin):
    """
    সাইজ, কালার বা টাইপ অনুযায়ী ভ্যারিয়েশন।
    যেমন: T-Shirt — Red / L
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", null=True, blank=True)

    sku = models.CharField(max_length=100, unique=True, verbose_name=_("SKU"))
    name = models.CharField(max_length=200, help_text="e.g. Red / Large", null=True, blank=True)

    # Variation axes
    color = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    type = models.CharField(max_length=50, null=True, blank=True)
    material = models.CharField(max_length=100, null=True, blank=True)

    # Pricing
    price_modifier = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True,
        help_text="Added to/subtracted from base price"
    )
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Physical attributes
    weight_grams = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="marketplace/variants/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_variant"

    def __str__(self):
        return f"{self.product.name} — {self.name}"

    @property
    def effective_price(self):
        if self.sale_price:
            return self.sale_price
        return self.product.base_price + self.price_modifier


class ProductInventory(TenantMixin, TimestampMixin):
    """
    স্টকের পরিমাণ এবং ওয়ারহাউস লোকেশন।
    """

    variant = models.OneToOneField(
        ProductVariant, on_delete=models.CASCADE, related_name="inventory")
    quantity = models.PositiveIntegerField(default=0, verbose_name=_("Stock Quantity"))
    reserved_quantity = models.PositiveIntegerField(
        default=0, help_text="Quantity reserved for pending orders"
    )

    warehouse_location = models.CharField(max_length=200, blank=True, verbose_name=_("Warehouse Location"))
    reorder_point = models.PositiveIntegerField(default=LOW_STOCK_THRESHOLD)
    reorder_quantity = models.PositiveIntegerField(default=50)
    track_quantity = models.BooleanField(default=True)
    allow_backorder = models.BooleanField(default=False)
    last_restocked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_inventory"

    def __str__(self):
        return f"{self.variant} — {self.available_quantity} in stock"

    @property
    def available_quantity(self):
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.reorder_point

    @property
    def is_out_of_stock(self):
        return self.available_quantity == 0

    def reserve(self, qty: int):
        self.reserved_quantity += qty
        self.save(update_fields=["reserved_quantity"])

    def release(self, qty: int):
        self.reserved_quantity = max(0, self.reserved_quantity - qty)
        self.save(update_fields=["reserved_quantity"])

    def deduct(self, qty: int):
        """Deduct after order confirmed."""
        self.quantity = max(0, self.quantity - qty)
        self.reserved_quantity = max(0, self.reserved_quantity - qty)
        self.save(update_fields=["quantity", "reserved_quantity"])


class ProductAttribute(TenantMixin):
    """
    স্পেসিফিকেশন। যেমন: RAM = 8GB, Material = Cotton, Screen Size = 6.5"
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes", null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name=_("Attribute Name"))
    value = models.CharField(max_length=300, verbose_name=_("Attribute Value"))
    unit = models.CharField(max_length=30, blank=True, help_text="e.g. GB, inch, kg", null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_attribute"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.product.name} — {self.name}: {self.value} {self.unit}"


# ═════════════════════════════════════════════════════════════════════════════
# 👥  SELLER & STORE
# ═════════════════════════════════════════════════════════════════════════════

class SellerProfile(TenantMixin, TimestampMixin):
    """
    সেলারের ব্যক্তিগত ও স্টোর ইনফো।
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",)

    # Store identity
    store_name = models.CharField(max_length=200, verbose_name=_("Store Name"))
    store_slug = models.SlugField(max_length=220, unique=True, null=True, blank=True)
    store_logo = models.ImageField(upload_to="marketplace/stores/logos/", null=True, blank=True)
    store_banner = models.ImageField(upload_to="marketplace/stores/banners/", null=True, blank=True)
    store_description = models.TextField(blank=True)
    store_url = models.URLField(null=True, blank=True)

    # Personal info
    full_name = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=10, null=True, blank=True)
    country = models.CharField(max_length=100, default="Bangladesh", null=True, blank=True)

    # Business info
    business_type = models.CharField(
        max_length=20,
        choices=[
            ("individual", "Individual"),
            ("company", "Company"),
            ("partnership", "Partnership"),
        ],
        default="individual",
    )
    business_name = models.CharField(max_length=200, null=True, blank=True)
    trade_license = models.CharField(max_length=100, null=True, blank=True)
    tin_number = models.CharField(max_length=50, null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=SellerStatus.choices,
        default=SellerStatus.PENDING,
        db_index=True,)
    is_featured = models.BooleanField(default=False)

    # Metrics
    total_sales = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    total_reviews = models.PositiveIntegerField(default=0)
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_profile"
        ordering = ["-created_at"]

    def __str__(self):
        return self.store_name

    @property
    def is_active(self):
        return self.status == SellerStatus.ACTIVE


class SellerVerification(TenantMixin, TimestampMixin):
    """
    KYC এবং ডকুমেন্ট ভেরিফিকেশন স্ট্যাটাস।
    """

    seller = models.OneToOneField(
        SellerProfile, on_delete=models.CASCADE, related_name="verification")

    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,)

    # NID / National ID
    nid_number = models.CharField(max_length=20, blank=True, verbose_name=_("NID Number"))
    nid_front = models.ImageField(upload_to="marketplace/kyc/nid/front/", null=True, blank=True)
    nid_back = models.ImageField(upload_to="marketplace/kyc/nid/back/", null=True, blank=True)
    selfie = models.ImageField(upload_to="marketplace/kyc/selfie/", null=True, blank=True)

    # Business documents
    trade_license_doc = models.FileField(upload_to="marketplace/kyc/trade/", null=True, blank=True)
    tin_certificate = models.FileField(upload_to="marketplace/kyc/tin/", null=True, blank=True)

    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="marketplace_verifications_reviewed",)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_verification"

    def __str__(self):
        return f"{self.seller.store_name} — {self.status}"

    def approve(self, reviewed_by):
        self.status = VerificationStatus.VERIFIED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()
        self.seller.status = SellerStatus.ACTIVE
        self.seller.save(update_fields=["status"])

    def reject(self, reviewed_by, reason):
        self.status = VerificationStatus.REJECTED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()


class SellerPayout(TenantMixin, TimestampMixin):
    """
    সেলারের পেমেন্ট এবং ব্যালেন্স হিস্ট্রি।
    """

    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="payouts", null=True, blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.BKASH, null=True, blank=True)
    account_number = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=PayoutStatus.choices, default=PayoutStatus.PENDING, db_index=True, null=True, blank=True)

    reference_id = models.CharField(max_length=100, blank=True, help_text="Gateway reference", null=True)
    note = models.TextField(blank=True)

    # Balance snapshot
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)

    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="marketplace_payouts_processed",)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_seller_payout"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seller.store_name} — {self.amount} BDT ({self.status})"


class CommissionConfig(TenantMixin, TimestampMixin):
    """
    কোন ক্যাটাগরিতে কত পারসেন্ট কমিশন।
    """

    category = models.OneToOneField(
        Category, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="commission_config",
        help_text="Null = global default",)
    rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal(str(DEFAULT_COMMISSION_RATE)),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        verbose_name=_("Commission Rate (%)"),
    )
    flat_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"), null=True, blank=True,
        help_text="Fixed fee per transaction (BDT)"
    )
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    effective_from = models.DateField(default=timezone.now)
    effective_until = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_commission_config"

    def __str__(self):
        cat = self.category.name if self.category else "Global"
        return f"{cat} — {self.rate}% commission"

    def calculate(self, amount: Decimal) -> Decimal:
        commission = (amount * self.rate / 100) + self.flat_fee
        return commission.quantize(Decimal("0.01"))


# ═════════════════════════════════════════════════════════════════════════════
# 🛒  ORDER & CART
# ═════════════════════════════════════════════════════════════════════════════

class Cart(TenantMixin, TimestampMixin):
    """
    ইউজারের বর্তমান কার্ট সেশন।
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="marketplace_carts",)
    session_key = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="For guest carts")
    coupon = models.ForeignKey(
        "marketplace.Coupon", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="carts",)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_cart"

    def __str__(self):
        owner = self.user.username if self.user else f"guest:{self.session_key}"
        return f"Cart({owner})"

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def item_count(self):
        return self.items.aggregate(total=models.Sum("quantity"))["total"] or 0


class CartItem(TenantMixin, TimestampMixin):
    """
    কার্টে থাকা নির্দিষ্ট প্রোডাক্ট ও পরিমাণ।
    """

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Price at time of adding to cart")
    note = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_cart_item"
        unique_together = [("cart", "variant")]

    def __str__(self):
        return f"{self.variant} x {self.quantity}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class Order(TenantMixin, TimestampMixin):
    """
    মেইন অর্ডার টেবিল (Total Price, Status, Address)।
    """

    order_number = models.CharField(max_length=20, unique=True, editable=False, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="marketplace_orders",)

    # Financials
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)

    # Coupon
    coupon = models.ForeignKey(
        "marketplace.Coupon", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="orders",)
    coupon_code = models.CharField(max_length=50, null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=30, choices=OrderStatus.choices,
        default=OrderStatus.PENDING, db_index=True,)

    # Payment
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Shipping address (snapshot)
    shipping_name = models.CharField(max_length=200, null=True, blank=True)
    shipping_phone = models.CharField(max_length=20, null=True, blank=True)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100, null=True, blank=True)
    shipping_district = models.CharField(max_length=100, null=True, blank=True)
    shipping_postal_code = models.CharField(max_length=10, null=True, blank=True)
    shipping_country = models.CharField(max_length=100, default="Bangladesh", null=True, blank=True)

    notes = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_order"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["order_number"]),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random
            self.order_number = f"ORD{random.randint(10000000, 99999999)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number

    def cancel(self, reason=""):
        self.status = OrderStatus.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save()


class OrderItem(TenantMixin, TimestampMixin):
    """
    একটি অর্ডারের ভেতরে থাকা আলাদা আলাদা প্রোডাক্ট।
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", null=True, blank=True)
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.SET_NULL, null=True, related_name="order_items"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, related_name="order_items"
    )

    # Snapshots at order time
    product_name = models.CharField(max_length=500, null=True, blank=True)
    variant_name = models.CharField(max_length=200, null=True, blank=True)
    sku = models.CharField(max_length=100, null=True, blank=True)
    product_image = models.URLField(null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Commission
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    seller_net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)

    # Status
    item_status = models.CharField(
        max_length=30, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    is_reviewed = models.BooleanField(default=False)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_order_item"

    def __str__(self):
        return f"{self.order.order_number} — {self.product_name} x{self.quantity}"

    def save(self, *args, **kwargs):
        self.subtotal = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)


class OrderTracking(TenantMixin, TimestampMixin):
    """
    শিপিং স্ট্যাটাস আপডেট (Shipped, Out for delivery, Delivered…)।
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tracking_events", null=True, blank=True)
    event = models.CharField(
        max_length=30, choices=TrackingEvent.choices, db_index=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)

    # Courier info
    courier_name = models.CharField(max_length=100, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, null=True, blank=True)

    occurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="marketplace_tracking_updates",
    )

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_order_tracking"
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.order.order_number} — {self.event} @ {self.occurred_at:%Y-%m-%d %H:%M}"


# ═════════════════════════════════════════════════════════════════════════════
# 💳  PAYMENT & SETTLEMENT
# ═════════════════════════════════════════════════════════════════════════════

class PaymentTransaction(TenantMixin, TimestampMixin):
    """
    প্রতিটি ট্রানজাকশনের গেটওয়ে আইডি ও স্ট্যাটাস।
    """

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="transactions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="marketplace_transactions",)

    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    gateway_transaction_id = models.CharField(
        max_length=200, blank=True, verbose_name=_("Gateway Transaction ID")
    )
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="BDT", null=True, blank=True)

    status = models.CharField(
        max_length=25, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING, db_index=True,)

    gateway_response = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=500, null=True, blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_payment_transaction"
        ordering = ["-initiated_at"]

    def __str__(self):
        return f"{self.order.order_number} — {self.amount} {self.currency} ({self.status})"

    def mark_success(self, gateway_id="", response=None):
        self.status = PaymentStatus.SUCCESS
        self.gateway_transaction_id = gateway_id
        self.gateway_response = response or {}
        self.completed_at = timezone.now()
        self.save()


class EscrowHolding(TenantMixin, TimestampMixin):
    """
    টাকা সেলারকে দেওয়ার আগে সিস্টেমের হোল্ডিং ব্যালেন্স।
    """

    order_item = models.OneToOneField(
        OrderItem, on_delete=models.CASCADE, related_name="escrow")
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name="escrow_holdings")

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commission_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=EscrowStatus.choices,
        default=EscrowStatus.HOLDING, db_index=True,)
    held_at = models.DateTimeField(auto_now_add=True)
    release_after = models.DateTimeField(help_text="Auto-release date")
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_escrow_holding"

    def __str__(self):
        return f"Escrow {self.order_item} — {self.net_amount} BDT ({self.status})"

    def release(self):
        self.status = EscrowStatus.RELEASED
        self.released_at = timezone.now()
        self.save()


class RefundRequest(TenantMixin, TimestampMixin):
    """
    কাস্টমারের রিফান্ড রিকোয়েস্ট ও প্রসেস।
    """

    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="refund_requests")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="marketplace_refund_requests",)

    reason = models.CharField(max_length=30, choices=RefundReason.choices, null=True, blank=True)
    description = models.TextField()
    evidence_images = models.JSONField(default=list, blank=True)

    amount_requested = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=RefundStatus.choices,
        default=RefundStatus.REQUESTED, db_index=True,)
    rejection_reason = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="marketplace_refunds_reviewed",)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    transaction = models.OneToOneField(
        PaymentTransaction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="refund",)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_refund_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund#{self.pk} — {self.order_item} ({self.status})"


# ═════════════════════════════════════════════════════════════════════════════
# 🎁  MARKETING & REVIEW
# ═════════════════════════════════════════════════════════════════════════════

class Coupon(TenantMixin, TimestampMixin):
    """
    ডিসকাউন্ট কোড এবং ব্যবহারের লিমিট।
    """

    code = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(blank=True)

    coupon_type = models.CharField(max_length=20, choices=CouponType.choices, null=True, blank=True)
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), null=True, blank=True,
        help_text="Minimum order amount required to use this coupon"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Cap on percentage discount")

    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    # Usage limits
    usage_limit = models.PositiveIntegerField(default=1000)
    usage_per_user = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)

    # Scope
    applicable_to = models.CharField(
        max_length=20,
        choices=[("all", "All"), ("product", "Specific Products"), ("category", "Category")],
        default="all",
    )
    applicable_categories = models.ManyToManyField(Category, blank=True)
    applicable_products = models.ManyToManyField(Product, blank=True)

    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Show in coupon listing")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="marketplace_coupons_created",)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_coupon"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} — {self.discount_value}{'%' if self.coupon_type == CouponType.PERCENTAGE else ' BDT'}"

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now <= self.valid_until
            and self.used_count < self.usage_limit
        )

    def calculate_discount(self, order_amount: Decimal) -> Decimal:
        if not self.is_valid or order_amount < self.min_order_amount:
            return Decimal("0.00")
        if self.coupon_type == CouponType.PERCENTAGE:
            disc = order_amount * self.discount_value / 100
            if self.max_discount_amount:
                disc = min(disc, self.max_discount_amount)
        elif self.coupon_type == CouponType.FIXED:
            disc = min(self.discount_value, order_amount)
        else:
            disc = Decimal("0.00")
        return disc.quantize(Decimal("0.01"))


class ProductReview(TenantMixin, TimestampMixin):
    """
    রেটিং এবং কাস্টমার কমেন্ট।
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews", null=True, blank=True)
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="review",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="marketplace_reviews",)

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)],
    )
    title = models.CharField(max_length=200, null=True, blank=True)
    body = models.TextField()
    images = models.JSONField(default=list, blank=True)

    # Moderation
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)

    # Seller response
    seller_reply = models.TextField(blank=True)
    seller_replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_product_review"
        ordering = ["-created_at"]
        unique_together = [("product", "user", "order_item")]

    def __str__(self):
        return f"{self.product.name} — {self.rating}★ by {self.user.username}"


class PromotionCampaign(TenantMixin, TimestampMixin):
    """
    ফ্ল্যাশ সেল বা ডিল অফ দ্য ডে।
    """

    name = models.CharField(max_length=200, null=True, blank=True)
    slug = models.SlugField(max_length=220, unique=True, null=True, blank=True)
    promotion_type = models.CharField(max_length=20, choices=PromotionType.choices, null=True, blank=True)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to="marketplace/promotions/", null=True, blank=True)

    # Discount
    discount_value = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), null=True, blank=True)
    discount_type = models.CharField(
        max_length=10, choices=[("percent", "Percent"), ("fixed", "Fixed")], default="percent"
    )

    # Products / categories in campaign
    products = models.ManyToManyField(Product, blank=True, related_name="campaigns")
    categories = models.ManyToManyField(Category, blank=True, related_name="campaigns")

    # Schedule
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)
    max_items = models.PositiveIntegerField(null=True, blank=True, help_text="Max products in flash sale")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="marketplace_campaigns_created",)

    class Meta:
        app_label = "marketplace"
        db_table = "marketplace_promotion_campaign"
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.name} ({self.promotion_type})"

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at
