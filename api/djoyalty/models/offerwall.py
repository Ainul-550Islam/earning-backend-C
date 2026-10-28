# api/djoyalty/models/offerwall.py
"""
OfferWall Models -- CPAlead-style CPA/CPI offer completion system।
Users complete offers (app install, survey, video, signup) -> earn points।

World reference: CPAlead (2006, 3M+ members), Tapjoy, Xsolla Offerwall।
Research 2025: Offerwall retention +40%, eCPM up to $1500।
Postback URL: advertiser confirms completion -> system awards points।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class OfferWall(models.Model):
    """
    OfferWall configuration -- your app's offer section।
    CPAlead style: "Earn Points" section where users complete tasks।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offer_walls',
    )
    name = models.CharField(max_length=200, verbose_name='OfferWall Name')
    description = models.TextField(null=True, blank=True)
    currency_name = models.CharField(
        max_length=50, default='Points',
        verbose_name='Currency Name (e.g. Points, Coins, Stars)',
    )
    # Currency ratio: how many points per $1 advertiser revenue
    currency_ratio = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('100'),
        verbose_name='Points per $1 Earned',
        help_text='e.g. 100 = user gets 100 pts when you earn $1',
    )
    header_title = models.CharField(max_length=200, default='Earn Free Points', verbose_name='Header Title')
    header_image = models.URLField(null=True, blank=True)
    primary_color = models.CharField(max_length=20, default='#3b82f6')
    is_active = models.BooleanField(default=True)
    # External offerwall provider API key (CPAlead, Tapjoy, etc.)
    provider = models.CharField(
        max_length=30,
        choices=[
            ('internal', 'Internal (Custom Offers)'),
            ('cpalead', 'CPAlead'),
            ('tapjoy', 'Tapjoy / Ironsource'),
            ('xsolla', 'Xsolla'),
            ('perkox', 'Perkox'),
            ('custom', 'Custom Provider'),
        ],
        default='internal',
    )
    provider_api_key = models.CharField(max_length=200, null=True, blank=True)
    provider_pub_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Publisher ID')
    postback_secret = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name='Postback Secret Key',
        help_text='Used to verify postback requests from provider',
    )
    postback_url = models.CharField(
        max_length=500, null=True, blank=True,
        verbose_name='Your Postback URL',
        help_text='URL provider calls when offer is completed',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'OfferWall'
        verbose_name_plural = 'OfferWalls'
        # AUDIT FIX (4): (tenant, is_active) for active offerwall per tenant.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='offerwall_tenant_active_idx'),
        ]

    def __str__(self):
        return f'OfferWall({self.name} [{self.provider}])'


class Offer(models.Model):
    """
    Individual offer/task in the offerwall।
    CPAlead: app install, survey, video watch, signup, purchase।
    """
    offer_wall = models.ForeignKey(
        OfferWall, on_delete=models.CASCADE,
        related_name='offers', verbose_name='OfferWall',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offers',
    )

    # Offer identity
    external_offer_id = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='External Offer ID (from provider)',
    )
    title = models.CharField(max_length=300, verbose_name='Offer Title')
    description = models.TextField(null=True, blank=True, verbose_name='Offer Description')
    short_description = models.CharField(max_length=200, null=True, blank=True)
    image_url = models.URLField(null=True, blank=True, verbose_name='Offer Image')
    advertiser_name = models.CharField(max_length=200, null=True, blank=True)

    # Offer type
    offer_type = models.CharField(
        max_length=30,
        choices=[
            ('app_install', '📱 App Install (CPI)'),
            ('survey', '📋 Survey'),
            ('video', '🎬 Video Watch'),
            ('signup', '✍️ Sign Up'),
            ('purchase', '💳 Purchase'),
            ('trial', '🆓 Free Trial'),
            ('quiz', '❓ Quiz'),
            ('game', '🎮 Play Game'),
            ('review', '⭐ Write Review'),
            ('social', '📱 Social Action'),
            ('other', 'Other'),
        ],
        default='app_install',
    )

    # Points reward
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('50'),
        verbose_name='Points Reward on Completion',
    )
    # Advertiser payout (what you earn when user completes)
    advertiser_payout = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0'),
        verbose_name='Advertiser Payout ($)',
    )
    currency = models.CharField(max_length=10, default='USD')

    # Requirements
    requirements = models.TextField(
        null=True, blank=True,
        verbose_name='Steps to Complete',
        help_text='e.g. "1. Download app 2. Open app 3. Reach level 5"',
    )
    estimated_time_minutes = models.PositiveIntegerField(
        default=5, verbose_name='Estimated Completion Time (minutes)',
    )
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='easy',
    )

    # Targeting
    geo_targets = models.JSONField(
        default=list, blank=True,
        verbose_name='Target Countries (ISO codes, empty = all)',
        help_text='["BD", "US", "UK"] or [] for all',
    )
    device_targets = models.JSONField(
        default=list, blank=True,
        verbose_name='Target Devices',
        help_text='["android", "ios", "web"]',
    )
    min_tier = models.ForeignKey(
        'djoyalty.LoyaltyTier', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offers',
    )

    # Limits
    max_completions_per_user = models.PositiveIntegerField(default=1)
    max_total_completions = models.PositiveIntegerField(null=True, blank=True)
    total_completions = models.PositiveIntegerField(default=0)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('ended', 'Ended'),
            ('draft', 'Draft'),
        ],
        default='active',
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    # Postback
    offer_url = models.URLField(null=True, blank=True, verbose_name='Offer URL (redirect link)')
    postback_token = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name='Offer-specific Postback Token',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'
        ordering = ['-is_featured', 'sort_order', '-points_reward']
        indexes = [
            models.Index(fields=['status', 'offer_type']),
            models.Index(fields=['external_offer_id']),
            models.Index(fields=['offer_wall', 'status']),
        ]

    def __str__(self):
        return f'Offer({self.title}: {self.points_reward} pts [{self.offer_type}])'


class OfferCompletion(models.Model):
    """
    Customer offer completion record।
    Created when postback received from provider OR user self-reports।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='offer_completions',
    )
    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE,
        related_name='completions',
    )
    offer_wall = models.ForeignKey(
        OfferWall, on_delete=models.CASCADE,
        related_name='completions',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='offer_completions',
    )

    # Postback data
    postback_received = models.BooleanField(default=False, verbose_name='Postback Received')
    postback_data = models.JSONField(default=dict, blank=True, verbose_name='Raw Postback Data')
    provider_transaction_id = models.CharField(
        max_length=200, null=True, blank=True,
        verbose_name='Provider Transaction ID',
    )
    advertiser_payout_received = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0'),
        verbose_name='Advertiser Payout Received',
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Verification'),
            ('verified', 'Verified'),
            ('points_awarded', 'Points Awarded'),
            ('rejected', 'Rejected'),
            ('chargeback', 'Chargeback'),
        ],
        default='pending',
    )
    points_awarded = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    rejection_reason = models.CharField(max_length=300, null=True, blank=True)

    # Fraud
    fraud_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
    )
    is_flagged = models.BooleanField(default=False)

    # Device info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=500, null=True, blank=True)
    country_code = models.CharField(max_length=5, null=True, blank=True)

    completed_at = models.DateTimeField(default=timezone.now)
    postback_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Offer Completion'
        verbose_name_plural = 'Offer Completions'
        ordering = ['-completed_at']
        unique_together = [('customer', 'offer', 'provider_transaction_id')]
        indexes = [
            models.Index(fields=['customer', 'offer', 'status']),
            models.Index(fields=['status', 'postback_received']),
            models.Index(fields=['provider_transaction_id']),
        ]

    def __str__(self):
        return f'Completion({self.customer.code}: {self.offer.title} [{self.status}])'


class ContentLock(models.Model):
    """
    Content Locking -- CPAlead style।
    Lock premium content behind offer completion।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='content_locks',
    )
    offer_wall = models.ForeignKey(
        OfferWall, on_delete=models.CASCADE,
        related_name='content_locks',
    )
    title = models.CharField(max_length=200, verbose_name='Locked Content Title')
    description = models.TextField(null=True, blank=True)
    content_type = models.CharField(
        max_length=20,
        choices=[
            ('url', 'URL/Link'),
            ('file', 'File Download'),
            ('text', 'Premium Text/Article'),
            ('video', 'Video'),
            ('product', 'Product/Service'),
        ],
        default='url',
    )
    locked_content = models.TextField(
        verbose_name='Content (URL, file path, or text)',
    )
    unlock_method = models.CharField(
        max_length=20,
        choices=[
            ('offer_complete', 'Complete Any Offer'),
            ('points', 'Spend Points'),
            ('specific_offer', 'Complete Specific Offer'),
        ],
        default='offer_complete',
    )
    required_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Required (if unlock_method=points)',
    )
    required_offer = models.ForeignKey(
        Offer, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='content_locks',
    )
    unlock_duration_hours = models.PositiveIntegerField(
        default=0, verbose_name='Unlock Duration (hours, 0=permanent)',
    )
    total_unlocks = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    thumbnail = models.URLField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Content Lock'
        verbose_name_plural = 'Content Locks'
        # AUDIT FIX (4): (offer_wall, is_active) for active locks per wall;
        # (tenant, is_active) for admin panel listing.
        indexes = [
            models.Index(fields=['offer_wall', 'is_active'],
                         name='contentlock_wall_active_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='contentlock_tenant_active_idx'),
        ]

    def __str__(self):
        return f'ContentLock({self.title}: {self.unlock_method})'


class ContentUnlock(models.Model):
    """
    Record of customer unlocking locked content।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='content_unlocks',
    )
    content_lock = models.ForeignKey(
        ContentLock, on_delete=models.CASCADE,
        related_name='unlocks',
    )
    offer_completion = models.ForeignKey(
        OfferCompletion, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='content_unlocks',
    )
    points_spent = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    unlocked_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Content Unlock'
        ordering = ['-unlocked_at']
        # AUDIT FIX (4): (customer, content_lock) for 'has customer unlocked?';
        # (customer, unlocked_at) for history.
        indexes = [
            models.Index(fields=['customer', 'content_lock'],
                         name='unlock_customer_lock_idx'),
            models.Index(fields=['customer', 'unlocked_at'],
                         name='unlock_customer_time_idx'),
        ]

    def __str__(self):
        return f'Unlock({self.customer.code}: {self.content_lock.title})'


class OfferPostbackLog(models.Model):
    """
    Raw postback log from providers (CPAlead, Tapjoy, etc.)।
    Every incoming postback recorded here for audit।
    """
    offer_wall = models.ForeignKey(
        OfferWall, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='postback_logs',
    )
    # Raw request data
    raw_data = models.JSONField(default=dict, verbose_name='Raw Postback Data')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    signature_valid = models.BooleanField(default=False, verbose_name='Signature Verified')

    # Parsed fields
    customer_ref = models.CharField(max_length=200, null=True, blank=True)
    offer_id = models.CharField(max_length=200, null=True, blank=True)
    transaction_id = models.CharField(max_length=200, null=True, blank=True)
    payout = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
    )

    # Processing result
    processed = models.BooleanField(default=False)
    points_credited = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
    )
    error_message = models.TextField(null=True, blank=True)

    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Offer Postback Log'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['processed', 'received_at']),
        ]

    def __str__(self):
        return f'Postback({self.transaction_id}: {self.payout} [{("ok" if self.signature_valid else "invalid")}])'
