# api/payment_gateways/locker/models.py
# Content Locker + Offerwall system — like CPAlead's core product
# Supports: URL locker, file locker, overlay mode, offerwall with virtual currency

import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import TimeStampedModel


def gen_locker_key():
    return uuid.uuid4().hex[:16].upper()


# ── Content Locker ────────────────────────────────────────────────────────────
class ContentLocker(TimeStampedModel):
    """
    A content locker created by a publisher.
    Locks content behind an offer completion.

    Types:
        url_locker  — locks a URL (redirect after offer done)
        file_locker — locks a file download
        overlay     — shows overlay on page, unlocks after offer
    """

    LOCKER_TYPES = (
        ('url_locker',  'URL Locker — lock a link'),
        ('file_locker', 'File Locker — lock a download'),
        ('overlay',     'Overlay — lock page content'),
    )

    UNLOCK_DURATION = (
        ('0',    'Require every visit'),
        ('24',   '24 hours'),
        ('72',   '72 hours'),
        ('168',  '7 days'),
        ('720',  '30 days'),
        ('never','Never expire — unlock once, always unlocked'),
    )

    STATUS = (
        ('active',   'Active'),
        ('paused',   'Paused'),
        ('deleted',  'Deleted'),
    )

    publisher        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='content_lockers')
    name             = models.CharField(max_length=200)
    locker_type      = models.CharField(max_length=15, choices=LOCKER_TYPES, default='url_locker')
    status           = models.CharField(max_length=10, choices=STATUS, default='active')
    locker_key       = models.CharField(max_length=20, unique=True, default=gen_locker_key,
                        help_text='Public key used in embed code')

    # Content being locked
    destination_url  = models.URLField(max_length=2000, blank=True,
                        help_text='URL to unlock (for url_locker)')
    file_upload      = models.FileField(upload_to='locker_files/', null=True, blank=True,
                        help_text='File to unlock (for file_locker)')
    overlay_selector = models.CharField(max_length=200, blank=True,
                        help_text='CSS selector for content to hide (for overlay)')
    page_url         = models.URLField(max_length=2000, blank=True,
                        help_text='Page this overlay is placed on')

    # Unlock settings
    unlock_duration_hours = models.CharField(max_length=10, choices=UNLOCK_DURATION, default='24')
    require_specific_offer= models.ForeignKey('offerwall.Offer', on_delete=models.SET_NULL,
                            null=True, blank=True,
                            help_text='Force a specific offer (null = show best available)')
    show_offer_count = models.IntegerField(default=1, help_text='How many offers to show')

    # Customization
    title            = models.CharField(max_length=200, blank=True,
                        default='Complete an offer to unlock this content')
    description      = models.TextField(blank=True)
    theme            = models.CharField(max_length=20, default='default',
                        choices=(('default','Default'),('dark','Dark'),
                                 ('minimal','Minimal'),('branded','Branded')))
    primary_color    = models.CharField(max_length=7, default='#635BFF')
    logo_url         = models.URLField(max_length=500, blank=True)

    # Stats
    total_impressions= models.BigIntegerField(default=0)
    total_unlocks    = models.BigIntegerField(default=0)
    total_earnings   = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    metadata         = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name  = 'Content Locker'
        ordering      = ['-created_at']
        indexes       = [models.Index(fields=['locker_key'])]

    def __str__(self):
        return f'[{self.locker_type}] {self.name} — {self.publisher.username}'

    @property
    def embed_code(self) -> str:
        """JavaScript embed code for publisher's website."""
        return (
            f'<script src="https://yourdomain.com/static/locker.js" '
            f'data-key="{self.locker_key}"></script>'
        )

    @property
    def unlock_rate(self) -> float:
        if self.total_impressions == 0:
            return 0.0
        return round(self.total_unlocks / self.total_impressions * 100, 2)


# ── Locker Session ─────────────────────────────────────────────────────────────
class LockerSession(TimeStampedModel):
    """
    Tracks visitor sessions for a content locker.
    Records whether they completed an offer and unlocked content.
    """

    STATUS = (
        ('shown',     'Locker shown — not yet unlocked'),
        ('unlocked',  'Unlocked — offer completed'),
        ('expired',   'Expired — session timed out'),
        ('skipped',   'Visitor left without completing'),
    )

    locker           = models.ForeignKey(ContentLocker, on_delete=models.CASCADE,
                        related_name='sessions')
    session_id       = models.CharField(max_length=64, default=uuid.uuid4().hex, db_index=True)
    visitor_ip       = models.GenericIPAddressField(null=True, blank=True)
    country_code     = models.CharField(max_length=2, blank=True)
    device_type      = models.CharField(max_length=20, blank=True)
    os_name          = models.CharField(max_length=50, blank=True)
    status           = models.CharField(max_length=10, choices=STATUS, default='shown')
    offer            = models.ForeignKey('offerwall.Offer', on_delete=models.SET_NULL,
                        null=True, blank=True, help_text='Offer shown to this visitor')
    click_id         = models.CharField(max_length=64, blank=True,
                        help_text='Tracking click_id for this session')
    conversion       = models.ForeignKey('offerwall.OfferConversion', on_delete=models.SET_NULL,
                        null=True, blank=True)
    unlocked_at      = models.DateTimeField(null=True, blank=True)
    expires_at       = models.DateTimeField(null=True, blank=True)
    payout_earned    = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))

    class Meta:
        verbose_name  = 'Locker Session'
        ordering      = ['-created_at']

    def __str__(self):
        return f'{self.locker.name} session [{self.status}]'

    @property
    def is_unlocked(self) -> bool:
        return self.status == 'unlocked'


# ── OfferWall ─────────────────────────────────────────────────────────────────
class OfferWall(TimeStampedModel):
    """
    A customizable incentivized offer wall.
    Users complete offers to earn virtual currency or rewards.

    Used in:
        - Mobile games (earn coins by installing apps)
        - Websites (earn points by completing surveys)
        - Android integration via JS API
    """

    STATUS = (('active','Active'),('paused','Paused'),('deleted','Deleted'))

    publisher         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                         related_name='offer_walls')
    name              = models.CharField(max_length=200)
    status            = models.CharField(max_length=10, choices=STATUS, default='active')
    wall_key          = models.CharField(max_length=20, unique=True, default=gen_locker_key)

    # Virtual currency
    currency_name     = models.CharField(max_length=50, default='Coins',
                         help_text='Name of virtual currency e.g. Coins, Points, Gems')
    currency_icon_url = models.URLField(max_length=500, blank=True)
    exchange_rate     = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('100'),
                         help_text='Virtual currency per $1 USD payout. E.g. 100 = 100 coins per $1')
    min_payout_usd    = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.01'))

    # Display
    title             = models.CharField(max_length=200, default='Earn rewards by completing offers')
    description       = models.TextField(blank=True)
    theme             = models.CharField(max_length=20, default='default')
    primary_color     = models.CharField(max_length=7, default='#635BFF')
    logo_url          = models.URLField(max_length=500, blank=True)
    banner_url        = models.URLField(max_length=500, blank=True)

    # Targeting (override per-offer targeting)
    target_countries  = models.JSONField(default=list, blank=True)
    target_devices    = models.JSONField(default=list, blank=True)

    # Android SDK config
    android_app_id    = models.CharField(max_length=200, blank=True)
    android_user_id_param = models.CharField(max_length=100, default='user_id')
    postback_url      = models.URLField(max_length=2000, blank=True,
                         help_text='Your server URL to credit user rewards on completion')

    # Stats
    total_completions = models.BigIntegerField(default=0)
    total_earnings    = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    metadata          = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name  = 'Offer Wall'
        ordering      = ['-created_at']

    def __str__(self):
        return f'OfferWall: {self.name} ({self.currency_name})'

    def usd_to_virtual(self, usd_amount: Decimal) -> Decimal:
        """Convert USD payout to virtual currency amount."""
        return usd_amount * self.exchange_rate

    @property
    def api_url(self) -> str:
        return f'https://yourdomain.com/api/payment/locker/offerwall/{self.wall_key}/'

    @property
    def embed_script(self) -> str:
        return (
            f'<script src="https://yourdomain.com/static/offerwall.js" '
            f'data-wall="{self.wall_key}" '
            f'data-user-id="REPLACE_WITH_USER_ID"></script>'
        )


# ── Virtual Currency & Rewards ─────────────────────────────────────────────────
class UserVirtualBalance(TimeStampedModel):
    """
    User's virtual currency balance for a specific offer wall.
    """
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='virtual_balances')
    offer_wall       = models.ForeignKey(OfferWall, on_delete=models.CASCADE,
                        related_name='user_balances')
    balance          = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_earned     = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    total_spent      = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))

    class Meta:
        verbose_name    = 'User Virtual Balance'
        unique_together = ['user', 'offer_wall']

    def __str__(self):
        return f'{self.user.username} — {self.balance} {self.offer_wall.currency_name}'


class VirtualReward(TimeStampedModel):
    """
    A single reward credit/debit transaction for virtual currency.
    """
    TYPES = (
        ('earned',   'Earned — offer completed'),
        ('spent',    'Spent — redeemed'),
        ('adjusted', 'Adjusted — admin action'),
        ('reversed', 'Reversed — offer reversed'),
    )

    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name='virtual_rewards')
    offer_wall       = models.ForeignKey(OfferWall, on_delete=models.CASCADE,
                        related_name='rewards')
    reward_type      = models.CharField(max_length=15, choices=TYPES, default='earned')
    amount           = models.DecimalField(max_digits=12, decimal_places=2,
                        help_text='Virtual currency amount (positive=credit, negative=debit)')
    usd_equivalent   = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0'))
    offer            = models.ForeignKey('offerwall.Offer', on_delete=models.SET_NULL,
                        null=True, blank=True)
    conversion       = models.ForeignKey('offerwall.OfferConversion', on_delete=models.SET_NULL,
                        null=True, blank=True)
    description      = models.CharField(max_length=200, blank=True)
    metadata         = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Virtual Reward'
        ordering     = ['-created_at']

    def __str__(self):
        return f'{self.user.username} {self.reward_type} {self.amount} {self.offer_wall.currency_name}'
