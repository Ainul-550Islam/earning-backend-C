# api/djoyalty/models/campaigns.py
"""
Djoyalty Campaign Models।
LoyaltyCampaign, CampaignSegment, CampaignParticipant,
ReferralPointsRule, PartnerMerchant।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager, ActiveCampaignManager

logger = logging.getLogger(__name__)


class LoyaltyCampaign(models.Model):
    """
    Loyalty campaign -- points multiplier, bonus, flash earn, etc।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='campaigns',
    )
    name = models.CharField(max_length=200, verbose_name='Campaign Name')
    description = models.TextField(null=True, blank=True)

    campaign_type = models.CharField(
        max_length=30,
        choices=[
            ('points_multiplier', 'Points Multiplier'),
            ('bonus_points', 'Bonus Points'),
            ('double_points', 'Double Points'),
            ('flash_earn', 'Flash Earn'),
            ('challenge', 'Challenge'),
        ],
        default='bonus_points',
        verbose_name='Campaign Type',
    )

    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        verbose_name='Points Multiplier',
    )
    bonus_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Bonus Points',
    )

    # Targeting
    segment_target = models.CharField(
        max_length=30,
        choices=[
            ('all', 'All Customers'),
            ('tier', 'Specific Tier'),
            ('geo', 'Geographic'),
            ('activity', 'Activity Based'),
        ],
        default='all',
        verbose_name='Segment Target',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'), ('active', 'Active'),
            ('ended', 'Ended'), ('paused', 'Paused'),
        ],
        default='draft',
    )

    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Start Date')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='End Date')

    max_participants = models.PositiveIntegerField(null=True, blank=True)
    budget_points = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    points_issued = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    image = models.URLField(null=True, blank=True, verbose_name='Campaign Image')
    terms = models.TextField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_campaigns = ActiveCampaignManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Loyalty Campaign'
        verbose_name_plural = 'Loyalty Campaigns'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['status', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f'Campaign({self.name} [{self.status}])'


class CampaignSegment(models.Model):
    """
    Campaign targeting segment definition।
    """
    campaign = models.ForeignKey(
        LoyaltyCampaign,
        on_delete=models.CASCADE,
        related_name='segments',
        verbose_name='Campaign',
    )
    segment_type = models.CharField(
        max_length=20,
        choices=[
            ('tier', 'Tier'), ('geo', 'Geographic'), ('activity', 'Activity'),
        ],
        verbose_name='Segment Type',
    )
    condition_value = models.CharField(max_length=200, verbose_name='Condition Value')
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Campaign Segment'
        # AUDIT FIX (4): (campaign, is_active) covers every segment load;
        # (segment_type,) covers admin filter by type.
        indexes = [
            models.Index(fields=['campaign', 'is_active'],
                         name='cseg_campaign_active_idx'),
            models.Index(fields=['segment_type'],
                         name='cseg_type_idx'),
        ]

    def __str__(self):
        return f'Segment({self.campaign.name}: {self.segment_type}={self.condition_value})'


class CampaignParticipant(models.Model):
    """
    Customer এর campaign participation।
    """
    campaign = models.ForeignKey(
        LoyaltyCampaign,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='Campaign',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer',
        on_delete=models.CASCADE,
        related_name='campaign_participations',
        verbose_name='Customer',
    )
    is_active = models.BooleanField(default=True)
    points_earned_in_campaign = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points Earned in Campaign',
    )
    joined_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Campaign Participant'
        verbose_name_plural = 'Campaign Participants'
        unique_together = [('campaign', 'customer')]
        indexes = [
            models.Index(fields=['campaign', 'is_active']),
            models.Index(fields=['customer']),
        ]

    def __str__(self):
        return f'CampaignParticipant({self.campaign.name}: {self.customer.code})'


class ReferralPointsRule(models.Model):
    """
    Referral points configuration (multi-level)।
    Level 1 = direct referral, Level 2 = referral's referral, etc।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referral_rules',
    )
    level = models.PositiveIntegerField(
        default=1,
        choices=[(1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3')],
        verbose_name='Referral Level',
    )
    points_on_signup = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points on Signup',
    )
    points_on_first_offer = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Points on First Purchase',
    )
    multiplier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        verbose_name='Multiplier',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Referral Points Rule'
        verbose_name_plural = 'Referral Points Rules'
        unique_together = [('tenant', 'level')]
        # AUDIT FIX (4): (tenant, is_active) covers active rule lookup;
        # unique_together already covers (tenant, level) lookup.
        indexes = [
            models.Index(fields=['tenant', 'is_active'],
                         name='rprule_tenant_active_idx'),
            models.Index(fields=['level', 'is_active'],
                         name='rprule_level_active_idx'),
        ]

    def __str__(self):
        return f'ReferralRule(Level {self.level}: signup={self.points_on_signup}, purchase={self.points_on_first_offer})'


class PartnerMerchant(models.Model):
    """
    Partner merchant for coalition loyalty।
    Customers earn points at partner locations।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='partner_merchants',
    )
    name = models.CharField(max_length=200, verbose_name='Merchant Name')
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True, verbose_name='Category')
    logo = models.URLField(null=True, blank=True, verbose_name='Logo URL')
    website = models.URLField(null=True, blank=True)

    earn_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('1'),
        verbose_name='Earn Rate (pts per currency unit)',
    )
    burn_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('1'),
        verbose_name='Burn Rate (pts per currency unit)',
    )

    api_key = models.CharField(max_length=100, unique=True, verbose_name='API Key')
    webhook_url = models.URLField(null=True, blank=True, verbose_name='Webhook URL')
    webhook_secret = models.CharField(max_length=100, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Synced At')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Partner Merchant'
        verbose_name_plural = 'Partner Merchants'
        ordering = ['name']
        indexes = [
            models.Index(fields=['api_key']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'Partner({self.name})'
