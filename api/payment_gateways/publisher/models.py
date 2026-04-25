# api/payment_gateways/publisher/models.py
from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel

TRAFFIC_TYPES = (
    ('social',   'Social Media'),
    ('search',   'Search / SEO'),
    ('email',    'Email marketing'),
    ('display',  'Display / Banner'),
    ('content',  'Content / Blog'),
    ('mobile',   'Mobile app'),
    ('push',     'Push notifications'),
    ('native',   'Native advertising'),
    ('video',    'Video'),
    ('other',    'Other'),
)


class PublisherProfile(TimeStampedModel):
    """Extended publisher profile and settings."""
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='publisher_profile')
    website_url      = models.URLField(blank=True)
    traffic_types    = models.JSONField(default=list)
    monthly_traffic  = models.CharField(max_length=50, blank=True,
                        choices=(('0-1k','0–1K/mo'),('1k-10k','1K–10K/mo'),
                                 ('10k-100k','10K–100K/mo'),('100k+','100K+/mo')))
    primary_geos     = models.JSONField(default=list, help_text='Top GEOs for their traffic')
    primary_devices  = models.JSONField(default=list)

    # Payment settings
    postback_url     = models.URLField(max_length=2000, blank=True,
                        help_text='Your S2S postback URL (receives {click_id},{payout},{status})')
    payment_email    = models.EmailField(blank=True)
    preferred_payment= models.CharField(max_length=20, blank=True,
                        choices=(('paypal','PayPal'),('payoneer','Payoneer'),
                                 ('crypto','Crypto'),('wire','Wire'),('ach','ACH')))
    payment_currency = models.CharField(max_length=5, default='USD')
    minimum_payout   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('25'))

    # Status
    status           = models.CharField(max_length=15, default='pending',
                        choices=(('pending','Pending approval'),('active','Active'),
                                 ('suspended','Suspended'),('banned','Banned')))
    is_fast_pay_eligible = models.BooleanField(default=False,
                            help_text='Eligible for daily payments (requires proven traffic)')
    quality_score    = models.IntegerField(default=50, help_text='0-100, affects offer access')
    tier             = models.CharField(max_length=10, default='standard',
                        choices=(('standard','Standard'),('preferred','Preferred'),('elite','Elite')))

    # Stats totals
    lifetime_earnings  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    lifetime_clicks    = models.BigIntegerField(default=0)
    lifetime_conversions = models.BigIntegerField(default=0)

    notes            = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Publisher Profile'

    def __str__(self):
        return f'Publisher: {self.user.username} [{self.status}]'


class AdvertiserProfile(TimeStampedModel):
    """Extended advertiser profile."""
    user             = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='advertiser_profile')
    company_name     = models.CharField(max_length=200, blank=True)
    website_url      = models.URLField(blank=True)
    status           = models.CharField(max_length=15, default='pending',
                        choices=(('pending','Pending'),('active','Active'),
                                 ('suspended','Suspended')))

    # Billing
    balance          = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                        help_text='Advertiser prepaid balance')
    currency         = models.CharField(max_length=5, default='USD')
    total_spent      = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    credit_limit     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                        help_text='Amount of credit extended (0 = prepay only)')

    # Postback
    default_postback_url = models.URLField(max_length=2000, blank=True)
    allowed_postback_ips = models.JSONField(default=list,
                            help_text='Whitelisted IPs for postback verification')

    # Billing
    invoice_email    = models.EmailField(blank=True)
    tax_id           = models.CharField(max_length=100, blank=True)
    billing_address  = models.TextField(blank=True)

    notes            = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Advertiser Profile'

    def __str__(self):
        return f'Advertiser: {self.user.username} [{self.status}]'

    @property
    def available_balance(self):
        return self.balance + self.credit_limit

    def can_afford(self, amount: Decimal) -> bool:
        return self.available_balance >= amount
