# api/djoyalty/models/campaigns.py
from django.db import models
from ..choices import CAMPAIGN_STATUS_CHOICES, CAMPAIGN_TYPE_CHOICES
from ..constants import POINTS_DECIMAL_PLACES, POINTS_MAX_DIGITS
from ..managers import ActiveCampaignManager, UpcomingCampaignManager, EndedCampaignManager


class LoyaltyCampaign(models.Model):
    """Loyalty campaign — double points, bonus, multiplier।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_loyaltycampaign_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    description = models.TextField(null=True, blank=True)
    campaign_type = models.CharField(max_length=32, choices=CAMPAIGN_TYPE_CHOICES, db_index=True)
    status = models.CharField(max_length=16, choices=CAMPAIGN_STATUS_CHOICES, default='draft', db_index=True)
    multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    bonus_points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    min_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_participants = models.PositiveIntegerField(null=True, blank=True)
    applicable_tiers = models.JSONField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active_campaigns = ActiveCampaignManager()
    upcoming = UpcomingCampaignManager()
    ended = EndedCampaignManager()

    class Meta:
        app_label = 'djoyalty'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.name} [{self.status}]'


class CampaignSegment(models.Model):
    """Campaign customer segment।"""

    campaign = models.ForeignKey(
        'LoyaltyCampaign', on_delete=models.CASCADE,
        related_name='segments',
    )
    name = models.CharField(max_length=128)
    filter_criteria = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'{self.campaign.name} → Segment: {self.name}'


class CampaignParticipant(models.Model):
    """Campaign participant record।"""

    campaign = models.ForeignKey(
        'LoyaltyCampaign', on_delete=models.CASCADE,
        related_name='campaign_participants',
    )
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE,
        related_name='campaign_participations',
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    points_earned = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'djoyalty'
        unique_together = [('campaign', 'customer')]

    def __str__(self):
        return f'{self.customer} in {self.campaign}'


class ReferralPointsRule(models.Model):
    """Referral bonus configuration।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_referralpointsrule_tenant', db_index=True,
    )
    referrer_points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=150)
    referee_points = models.DecimalField(max_digits=POINTS_MAX_DIGITS, decimal_places=POINTS_DECIMAL_PLACES, default=50)
    min_referee_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_referrals_per_customer = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'Referral: referrer={self.referrer_points}, referee={self.referee_points}'


class PartnerMerchant(models.Model):
    """Coalition partner merchant — cross-brand earn/burn।"""

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_partnermerchant_tenant', db_index=True,
    )
    name = models.CharField(max_length=128)
    api_key = models.CharField(max_length=64, unique=True, db_index=True)
    webhook_url = models.URLField(null=True, blank=True)
    earn_rate = models.DecimalField(max_digits=8, decimal_places=4, default=1)
    burn_rate = models.DecimalField(max_digits=8, decimal_places=4, default=1)
    is_active = models.BooleanField(default=True, db_index=True)
    sync_interval_minutes = models.PositiveIntegerField(default=60)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'

    def __str__(self):
        return f'Partner: {self.name} (active={self.is_active})'
