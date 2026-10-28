# api/djoyalty/models/catalog.py
"""
Reward Catalog + SmartLink + WebhookSubscription + DigitalWalletCard Models।
World: Open Loyalty reward catalog, CPAlead SmartLink, Voucherify webhooks,
PassKit/Apple Wallet digital cards।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


# ─── REWARD CATALOG ──────────────────────────────────────────────────────────

class RewardCatalogCategory(models.Model):
    """Reward catalog category।"""
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reward_categories',
    )
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='🎁')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children',
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Reward Category'
        ordering = ['sort_order', 'name']
        # AUDIT FIX (4): (tenant, is_active) for active category listing;
        # (sort_order,) for ordered category browse.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='rwcat_tenant_active_idx'),
            models.Index(fields=['sort_order'],
                         name='rwcat_sort_idx'),
        ]

    def __str__(self):
        return f'RewardCategory({self.name})'


class RewardCatalogItem(models.Model):
    """
    Item in reward catalog -- customers browse and redeem with points।
    World: Snipp rewards catalog (gift cards, experiences, merchandise)।
    Open Loyalty reward catalog। Marriott Bonvoy experiences।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reward_catalog',
    )
    category = models.ForeignKey(
        RewardCatalogCategory, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='items',
    )
    name = models.CharField(max_length=300)
    description = models.TextField(null=True, blank=True)
    short_description = models.CharField(max_length=200, null=True, blank=True)

    reward_type = models.CharField(
        max_length=30,
        choices=[
            ('voucher', '🎟️ Discount Voucher'),
            ('gift_card', '💳 Gift Card'),
            ('product', '📦 Physical Product'),
            ('digital', '💻 Digital Product'),
            ('experience', '🎉 Experience'),
            ('cashback', '💰 Cashback'),
            ('charity', '❤️ Charity Donation'),
            ('subscription', '📱 Subscription'),
            ('travel', '✈️ Travel'),
            ('custom', '✨ Custom'),
        ],
        default='voucher',
    )

    # Pricing
    points_cost = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='Points Required')
    cash_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), verbose_name='Cash Value')
    original_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='BDT')

    # Availability
    stock_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name='Stock (null=unlimited)')
    redeemed_count = models.PositiveIntegerField(default=0)
    max_per_customer = models.PositiveIntegerField(default=1)

    # Requirements
    min_tier = models.ForeignKey(
        'djoyalty.LoyaltyTier', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='catalog_items',
    )

    # Media
    image_url = models.URLField(null=True, blank=True)
    gallery = models.JSONField(default=list, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    terms = models.TextField(null=True, blank=True)

    # Partner/supplier
    supplier_name = models.CharField(max_length=200, null=True, blank=True)
    fulfillment_type = models.CharField(
        max_length=20,
        choices=[('instant', 'Instant'), ('manual', 'Manual'), ('shipping', 'Physical Shipping')],
        default='instant',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Reward Catalog Item'
        ordering = ['-is_featured', 'sort_order', 'points_cost']
        indexes = [
            models.Index(fields=['reward_type', 'is_active']),
            models.Index(fields=['points_cost']),
        ]

    def is_available(self) -> bool:
        if not self.is_active:
            return False
        if self.stock_quantity is not None and self.redeemed_count >= self.stock_quantity:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def __str__(self):
        return f'CatalogItem({self.name}: {self.points_cost} pts)'


# ─── SMART LINK ──────────────────────────────────────────────────────────────

class SmartLink(models.Model):
    """
    CPAlead-style SmartLink -- geo-targeted short URLs।
    Auto-routes visitors to best offer based on GEO + device।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='smart_links',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='smart_links',
        verbose_name='Publisher/Customer',
    )
    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=300, null=True, blank=True)

    # Routing
    default_url = models.URLField(verbose_name='Default Destination URL')
    geo_rules = models.JSONField(
        default=list, blank=True,
        verbose_name='Geo Rules',
        help_text='[{"countries": ["BD", "IN"], "url": "https://..."}]',
    )
    device_rules = models.JSONField(
        default=list, blank=True,
        verbose_name='Device Rules',
        help_text='[{"devices": ["android"], "url": "https://..."}]',
    )

    # Stats
    total_clicks = models.PositiveIntegerField(default=0)
    unique_clicks = models.PositiveIntegerField(default=0)
    total_conversions = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    # Linked offer/campaign
    linked_offer = models.ForeignKey(
        'djoyalty.Offer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='smart_links',
    )
    linked_campaign = models.ForeignKey(
        'djoyalty.LoyaltyCampaign', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='smart_links',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Smart Link'
        verbose_name_plural = 'Smart Links'
        indexes = [
            models.Index(fields=['slug']),
        ]

    def get_destination_url(self, country: str = '', device: str = '') -> str:
        """Get best URL for visitor's geo + device।"""
        if country and self.geo_rules:
            for rule in self.geo_rules:
                if country.upper() in rule.get('countries', []):
                    return rule.get('url', self.default_url)
        if device and self.device_rules:
            for rule in self.device_rules:
                if device.lower() in rule.get('devices', []):
                    return rule.get('url', self.default_url)
        return self.default_url

    def __str__(self):
        return f'SmartLink({self.slug}: {self.total_clicks} clicks)'


class SmartLinkClick(models.Model):
    """Click on a SmartLink।"""
    smart_link = models.ForeignKey(SmartLink, on_delete=models.CASCADE, related_name='clicks')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country_code = models.CharField(max_length=5, null=True, blank=True)
    device_type = models.CharField(max_length=20, null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    destination_url = models.URLField(null=True, blank=True)
    converted = models.BooleanField(default=False)
    is_unique = models.BooleanField(default=True)
    clicked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Smart Link Click'
        ordering = ['-clicked_at']
        # AUDIT FIX (4): (smart_link, clicked_at) for analytics;
        # (smart_link, converted) for conversion funnel.
        indexes = [
            models.Index(fields=['smart_link', 'clicked_at'],
                         name='slclick_link_time_idx'),
            models.Index(fields=['smart_link', 'converted'],
                         name='slclick_link_conv_idx'),
            models.Index(fields=['clicked_at'],
                         name='slclick_time_idx'),
        ]

    def __str__(self):
        return f'SmartClick({self.smart_link.slug}: {self.country_code})'


# ─── WEBHOOK SUBSCRIPTION ────────────────────────────────────────────────────

class WebhookSubscription(models.Model):
    """
    Webhook subscription model।
    Who subscribes to which events -> their delivery URL।
    World: Voucherify webhook subscriptions, Open Loyalty webhooks।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='webhook_subscriptions',
    )
    name = models.CharField(max_length=200)
    url = models.URLField(verbose_name='Webhook Delivery URL')
    secret = models.CharField(max_length=100, verbose_name='HMAC Secret')

    subscribed_events = models.JSONField(
        default=list,
        verbose_name='Subscribed Events',
        help_text='["points.earned", "tier.upgraded", "badge.unlocked"]',
    )

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False, verbose_name='URL Verified')

    # Stats
    total_deliveries = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries = models.PositiveIntegerField(default=0)
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    # Config
    max_retries = models.PositiveIntegerField(default=5)
    timeout_seconds = models.PositiveIntegerField(default=10)
    api_version = models.CharField(max_length=10, default='v1')

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Webhook Subscription'
        verbose_name_plural = 'Webhook Subscriptions'
        # AUDIT FIX (4): (tenant, is_active) for loading active webhooks;
        # (is_active, is_verified) for verified endpoint checks.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='webhooksub_tenant_active_idx'),
            models.Index(fields=['is_active', 'is_verified'],
                         name='webhooksub_active_verified_idx'),
        ]

    def subscribes_to(self, event_type: str) -> bool:
        return '*' in self.subscribed_events or event_type in self.subscribed_events

    def success_rate(self) -> str:
        if self.total_deliveries == 0:
            return '100%'
        return f'{self.successful_deliveries / self.total_deliveries * 100:.1f}%'

    def __str__(self):
        return f'WebhookSub({self.name}: {self.url[:50]})'


class WebhookDeliveryLog(models.Model):
    """Log of each webhook delivery attempt।"""
    subscription = models.ForeignKey(
        WebhookSubscription, on_delete=models.CASCADE,
        related_name='delivery_logs',
    )
    event_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    attempt_number = models.PositiveIntegerField(default=1)
    http_status = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True, max_length=1000)
    duration_ms = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    success = models.BooleanField(default=False)
    error_message = models.CharField(max_length=500, null=True, blank=True)
    delivered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Webhook Delivery Log'
        ordering = ['-delivered_at']
        indexes = [
            models.Index(fields=['subscription', 'success']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f'WebhookLog({self.subscription.name}: {self.event_type} {"✓" if self.success else "✗"})'


# ─── DIGITAL WALLET CARD ─────────────────────────────────────────────────────

class DigitalWalletCard(models.Model):
    """
    Apple Wallet / Google Wallet digital loyalty card।
    World: PassKit, Loopy Loyalty, Starbucks digital card।
    2025: QR code loyalty cards replacing physical cards।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='digital_wallet_cards',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='digital_wallet_cards',
    )

    wallet_type = models.CharField(
        max_length=20,
        choices=[
            ('apple_wallet', 'Apple Wallet'),
            ('google_wallet', 'Google Wallet'),
            ('both', 'Both'),
        ],
        default='both',
    )

    # Card data
    card_number = models.CharField(max_length=30, unique=True)
    pass_serial = models.CharField(max_length=100, null=True, blank=True, verbose_name='Pass Serial Number')
    barcode_value = models.CharField(max_length=200, verbose_name='QR/Barcode Value')
    barcode_type = models.CharField(
        max_length=10,
        choices=[('qr', 'QR Code'), ('barcode', 'Barcode'), ('code128', 'Code 128')],
        default='qr',
    )

    # Display
    program_name = models.CharField(max_length=100, default='Loyalty Program')
    card_title = models.CharField(max_length=100, null=True, blank=True)
    background_color = models.CharField(max_length=20, default='#3b82f6')
    text_color = models.CharField(max_length=20, default='#ffffff')
    logo_url = models.URLField(null=True, blank=True)
    strip_image_url = models.URLField(null=True, blank=True)

    # Pass file
    pkpass_url = models.URLField(null=True, blank=True, verbose_name='.pkpass Download URL')
    google_pass_url = models.URLField(null=True, blank=True, verbose_name='Google Wallet Add URL')

    # Sync
    last_pushed_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Push Update')
    push_token = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Digital Wallet Card'
        indexes = [
            models.Index(fields=['card_number']),
            models.Index(fields=['barcode_value']),
        ]

    def __str__(self):
        return f'WalletCard({self.customer.code}: {self.wallet_type} {self.card_number})'
