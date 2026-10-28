# api/djoyalty/models/social.py
"""
Djoyalty Social + Omnichannel + Segmentation Models।
SocialShareReward, ReviewReward, QRCodeEarn, CustomerSegment, SegmentRule।

World reference: Smile.io social sharing, Voucherify omnichannel,
Subway QR scan earn, Open Loyalty customer segments।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class SocialShareReward(models.Model):
    """
    Social share -> points reward।
    World: Smile.io Facebook/Instagram share, Voucherify social rewards।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='social_share_rewards',
    )
    platform = models.CharField(
        max_length=30,
        choices=[
            ('facebook', 'Facebook'),
            ('instagram', 'Instagram'),
            ('twitter', 'Twitter/X'),
            ('linkedin', 'LinkedIn'),
            ('whatsapp', 'WhatsApp'),
            ('tiktok', 'TikTok'),
            ('other', 'Other'),
        ],
        verbose_name='Platform',
    )
    share_type = models.CharField(
        max_length=30,
        choices=[
            ('post', 'Share Post'),
            ('follow', 'Follow Account'),
            ('review', 'Leave Review'),
            ('check_in', 'Check-in'),
            ('tag', 'Tag a Friend'),
        ],
        default='post',
        verbose_name='Share Type',
    )
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('20'),
        verbose_name='Points Reward',
    )
    max_per_customer_per_day = models.PositiveIntegerField(default=1)
    max_per_customer_total = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    requires_proof = models.BooleanField(
        default=False, verbose_name='Requires Screenshot Proof',
    )
    share_url = models.URLField(null=True, blank=True, verbose_name='URL to Share')
    campaign = models.ForeignKey(
        'djoyalty.LoyaltyCampaign', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='social_share_rewards',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Social Share Reward'
        verbose_name_plural = 'Social Share Rewards'
        # AUDIT FIX (4): (tenant, platform) and (tenant, is_active).
        indexes = [
            models.Index(fields=['tenant', 'platform'],
                         name='socialrew_tenant_platform_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='socialrew_tenant_active_idx'),
        ]

    def __str__(self):
        return f'SocialReward({self.platform}/{self.share_type}: {self.points_reward} pts)'


class CustomerSocialAction(models.Model):
    """
    Customer এর completed social action record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='social_actions',
    )
    reward_config = models.ForeignKey(
        SocialShareReward, on_delete=models.CASCADE,
        related_name='customer_actions',
    )
    platform = models.CharField(max_length=30)
    share_type = models.CharField(max_length=30)
    proof_url = models.URLField(null=True, blank=True, verbose_name='Proof Screenshot URL')
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=200, null=True, blank=True)
    completed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Social Action'
        ordering = ['-completed_at']
        indexes = [
            models.Index(fields=['customer', 'platform', 'share_type']),
        ]

    def __str__(self):
        return f'SocialAction({self.customer.code}: {self.platform}/{self.share_type})'


class ReviewReward(models.Model):
    """
    Product/service review -> points reward।
    World: Smile.io review rewards, WooCommerce review points।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='review_rewards',
    )
    review_platform = models.CharField(
        max_length=30,
        choices=[
            ('in_app', 'In-App Review'),
            ('google', 'Google Review'),
            ('facebook', 'Facebook Review'),
            ('trustpilot', 'Trustpilot'),
            ('app_store', 'App Store Review'),
            ('play_store', 'Play Store Review'),
            ('other', 'Other'),
        ],
        default='in_app',
        verbose_name='Review Platform',
    )
    min_rating = models.PositiveIntegerField(
        default=4, verbose_name='Minimum Rating (1-5)',
    )
    min_words = models.PositiveIntegerField(
        default=20, verbose_name='Minimum Words',
    )
    points_reward = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('50'),
    )
    photo_bonus_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('20'),
        verbose_name='Bonus Points for Photo Review',
    )
    max_reviews_rewarded = models.PositiveIntegerField(
        default=1, verbose_name='Max Reviews Rewarded per Customer',
    )
    is_active = models.BooleanField(default=True)
    requires_verification = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Review Reward'
        # AUDIT FIX (4): (tenant, review_platform, is_active) for reward lookup.
        indexes = [
            models.Index(fields=['tenant', 'review_platform'],
                         name='reviewrew_tenant_platform_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='reviewrew_tenant_active_idx'),
        ]

    def __str__(self):
        return f'ReviewReward({self.review_platform}: {self.points_reward} pts)'


class CustomerReview(models.Model):
    """
    Customer submitted review record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='reviews',
    )
    reward_config = models.ForeignKey(
        ReviewReward, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_reviews',
    )
    platform = models.CharField(max_length=30)
    rating = models.PositiveIntegerField(default=5)
    review_text = models.TextField()
    review_url = models.URLField(null=True, blank=True)
    has_photo = models.BooleanField(default=False)
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=200, null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Review'
        ordering = ['-submitted_at']
        # AUDIT FIX (4): (customer, platform) for customer review per platform;
        # (customer, is_verified) for verified review checks.
        indexes = [
            models.Index(fields=['customer', 'platform'],
                         name='custrev_customer_platform_idx'),
            models.Index(fields=['customer', 'is_verified'],
                         name='custrev_customer_verified_idx'),
            models.Index(fields=['submitted_at'],
                         name='custrev_time_idx'),
        ]

    def __str__(self):
        return f'Review({self.customer.code}: ★{self.rating} on {self.platform})'


class QRCodeEarn(models.Model):
    """
    QR Code scan -> points earn (in-store/POS)।
    World: Subway QR rewards, Starbucks store scan, Fitbit check-in।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='qr_code_earns',
    )
    code = models.CharField(max_length=100, unique=True, verbose_name='QR Code Value')
    name = models.CharField(max_length=200, verbose_name='QR Point Name')
    location_name = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Store/Location Name',
    )
    channel = models.CharField(
        max_length=20,
        choices=[
            ('in_store', 'In-Store'),
            ('pos', 'POS Terminal'),
            ('event', 'Event Check-in'),
            ('product', 'Product Scan'),
            ('receipt', 'Receipt Scan'),
        ],
        default='in_store',
        verbose_name='Channel',
    )
    points_per_scan = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('10'),
        verbose_name='Points per Scan',
    )
    max_scans_per_customer_per_day = models.PositiveIntegerField(default=1)
    max_total_scans = models.PositiveIntegerField(null=True, blank=True)
    total_scans = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'QR Code Earn'
        verbose_name_plural = 'QR Code Earns'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['channel', 'is_active']),
        ]

    def __str__(self):
        return f'QRCode({self.code}: {self.points_per_scan} pts @ {self.location_name or "any"})'


class QRCodeScan(models.Model):
    """
    QR code scan event record।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='qr_scans',
    )
    qr_code = models.ForeignKey(
        QRCodeEarn, on_delete=models.CASCADE,
        related_name='scans',
    )
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    channel = models.CharField(max_length=20, default='in_store')
    device_info = models.CharField(max_length=300, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    scanned_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'QR Code Scan'
        ordering = ['-scanned_at']
        indexes = [
            models.Index(fields=['customer', 'qr_code', 'scanned_at']),
        ]

    def __str__(self):
        return f'QRScan({self.customer.code}: {self.qr_code.code} @ {self.scanned_at.strftime("%Y-%m-%d")})'


class CustomerSegment(models.Model):
    """
    Customer segmentation model।
    World: Open Loyalty segments, Voucherify customer groups।
    RFM analysis + behavioral segmentation।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_segments',
    )
    name = models.CharField(max_length=200, verbose_name='Segment Name')
    description = models.TextField(null=True, blank=True)
    segment_type = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual (Admin Assigns)'),
            ('rfm', 'RFM Based'),
            ('tier', 'Tier Based'),
            ('geo', 'Geographic'),
            ('behavioral', 'Behavioral'),
            ('spend', 'Spend Based'),
            ('custom', 'Custom Rules'),
        ],
        default='custom',
        verbose_name='Segment Type',
    )
    color = models.CharField(max_length=20, default='#3b82f6')
    icon = models.CharField(max_length=50, default='👥')
    is_active = models.BooleanField(default=True)
    is_dynamic = models.BooleanField(
        default=True, verbose_name='Auto-update Members',
    )
    last_computed_at = models.DateTimeField(null=True, blank=True)
    member_count = models.PositiveIntegerField(default=0)

    # RFM thresholds
    rfm_recency_days = models.PositiveIntegerField(null=True, blank=True, verbose_name='RFM: Max Days Since Last Purchase')
    rfm_frequency_min = models.PositiveIntegerField(null=True, blank=True, verbose_name='RFM: Min Transaction Count')
    rfm_monetary_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name='RFM: Min Total Spend')

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Segment'
        verbose_name_plural = 'Customer Segments'
        ordering = ['name']
        # AUDIT FIX (4): (tenant, segment_type) and (tenant, is_active).
        indexes = [
            models.Index(fields=['tenant', 'segment_type'],
                         name='custseg_tenant_type_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='custseg_tenant_active_idx'),
        ]

    def __str__(self):
        return f'Segment({self.name}: {self.member_count} members)'


class CustomerSegmentMember(models.Model):
    """
    Customer ↔ Segment many-to-many with metadata।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='segment_memberships',
    )
    segment = models.ForeignKey(
        CustomerSegment, on_delete=models.CASCADE,
        related_name='members',
    )
    added_at = models.DateTimeField(default=timezone.now)
    added_by = models.CharField(max_length=200, null=True, blank=True)
    rfm_score = models.CharField(max_length=10, null=True, blank=True, verbose_name='RFM Score')
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Segment Member'
        unique_together = [('customer', 'segment')]
        indexes = [
            models.Index(fields=['segment', 'is_active']),
        ]

    def __str__(self):
        return f'SegmentMember({self.customer.code} -> {self.segment.name})'
