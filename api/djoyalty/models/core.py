# api/djoyalty/models/core.py
"""
Djoyalty Core Models -- Customer, Txn, Event।
Existing models fix + new fields add।

AUDIT FIXES (v2 -- integrity pass):
  Tenant.Meta: Added Meta.indexes with (slug, is_active) compound index and
               standalone (is_active,) index।  Previously only `slug` and
               `api_key` had implicit B-tree indexes via unique=True।  The
               compound (slug, is_active) covers the most common query pattern
               ("find active tenant by slug") without a second scan।
"""
import logging
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..managers import (
    ActiveManager, InactiveManager,
    CustomerRelatedManager, AnonymousManager,
    FullPriceTxnManager, DiscountTxnManager,
)
from ..validators import validate_customer_code, validate_phone_number

logger = logging.getLogger(__name__)
User = get_user_model()


class Customer(models.Model):
    """
    Loyalty customer profile।
    User FK optional -- guest customers support করে।
    """
    # Optional Django User link
    user = models.OneToOneField(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='loyalty_customer',
        verbose_name='User Account',
    )

    # Tenant support
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='customers',
        verbose_name='Tenant',
    )

    # Identity
    code = models.CharField(
        max_length=50, unique=True,
        validators=[validate_customer_code],
        verbose_name='Customer Code',
        help_text='Unique customer identifier (uppercase)',
    )
    loyalty_number = models.CharField(
        max_length=30, unique=True,
        null=True, blank=True,
        verbose_name='Loyalty Number',
        help_text='Auto-generated loyalty card number',
    )
    firstname = models.CharField(max_length=100, null=True, blank=True, verbose_name='First Name')
    lastname = models.CharField(max_length=100, null=True, blank=True, verbose_name='Last Name')
    email = models.EmailField(null=True, blank=True, verbose_name='Email Address')
    phone = models.CharField(
        max_length=30, null=True, blank=True,
        validators=[validate_phone_number],
        verbose_name='Phone Number',
    )
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name='City')
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name='Country')
    address = models.TextField(null=True, blank=True, verbose_name='Address')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Date of Birth')
    gender = models.CharField(
        max_length=10, null=True, blank=True,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
    )

    # Preferences
    newsletter = models.BooleanField(default=True, verbose_name='Newsletter Subscribed')
    sms_opt_in = models.BooleanField(default=False, verbose_name='SMS Opt-in')
    push_opt_in = models.BooleanField(default=False, verbose_name='Push Notification Opt-in')

    # Status
    is_active = models.BooleanField(default=True, verbose_name='Active')
    is_verified = models.BooleanField(default=False, verbose_name='Verified')

    # Referral
    referred_by = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals',
        verbose_name='Referred By',
    )
    referral_code = models.CharField(max_length=20, null=True, blank=True, unique=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Metadata')
    notes = models.TextField(null=True, blank=True, verbose_name='Internal Notes')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    last_activity_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Activity')

    # Managers
    objects = models.Manager()
    active = ActiveManager()
    inactive = InactiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['email']),
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        name = self.full_name
        return f'{self.code} -- {name}' if name != 'Unnamed' else self.code

    @property
    def full_name(self) -> str:
        parts = [p for p in [self.firstname, self.lastname] if p]
        return ' '.join(parts) if parts else 'Unnamed'

    @property
    def points_balance(self) -> Decimal:
        lp = self.loyalty_points.first()
        return lp.balance if lp else Decimal('0')

    @property
    def current_tier(self):
        """Customer এর current active UserTier।"""
        return self.user_tiers.filter(is_current=True).select_related('tier').first()

    @property
    def lifetime_points(self) -> Decimal:
        lp = self.loyalty_points.first()
        return lp.lifetime_earned if lp else Decimal('0')

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        if not self.loyalty_number:
            from ..utils import generate_loyalty_number
            ln = generate_loyalty_number()
            while Customer.objects.filter(loyalty_number=ln).exists():
                ln = generate_loyalty_number()
            self.loyalty_number = ln
        super().save(*args, **kwargs)


class Txn(models.Model):
    """
    Customer transaction record।
    Purchase, spend, discount transactions।
    """
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
    )
    value = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Transaction Value',
    )
    is_discount = models.BooleanField(default=False, verbose_name='Is Discount Purchase')

    # New fields
    txn_type = models.CharField(
        max_length=30, null=True, blank=True,
        choices=[
            ('purchase', 'Purchase'),
            ('refund', 'Refund'),
            ('spend', 'Spend'),
            ('discount', 'Discount Purchase'),
            ('other', 'Other'),
        ],
        verbose_name='Transaction Type',
    )
    source = models.CharField(max_length=50, null=True, blank=True, verbose_name='Source')
    reference_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='Reference ID')
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name='Description')
    currency = models.CharField(max_length=10, default='BDT', verbose_name='Currency')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Metadata')

    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Timestamp')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers
    objects = models.Manager()
    txn_full = FullPriceTxnManager()
    txn_discount = DiscountTxnManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['customer', 'timestamp']),
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['is_discount']),
            models.Index(fields=['reference_id']),
        ]

    def __str__(self):
        discount_flag = ' [D]' if self.is_discount else ''
        return f'Txn({self.customer.code}: {self.value}{discount_flag})'

    @property
    def type_label(self) -> str:
        if self.is_discount:
            return 'Discount'
        if self.value < 0:
            return 'Spend / Refund'
        return 'Full Price'


class Event(models.Model):
    """
    Customer activity event log।
    Anonymous events support করে (customer=None)।
    """
    customer = models.ForeignKey(
        Customer,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
        verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='events',
    )
    action = models.CharField(max_length=100, verbose_name='Action')
    description = models.TextField(null=True, blank=True, verbose_name='Description')

    # New fields
    event_category = models.CharField(
        max_length=50, null=True, blank=True,
        choices=[
            ('auth', 'Authentication'),
            ('purchase', 'Purchase'),
            ('loyalty', 'Loyalty'),
            ('engagement', 'Engagement'),
            ('admin', 'Admin'),
            ('system', 'System'),
            ('other', 'Other'),
        ],
        verbose_name='Event Category',
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Metadata')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    user_agent = models.CharField(max_length=500, null=True, blank=True, verbose_name='User Agent')
    source = models.CharField(max_length=50, null=True, blank=True, verbose_name='Source')

    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Timestamp')
    created_at = models.DateTimeField(auto_now_add=True)

    # Managers
    objects = models.Manager()
    customer_related = CustomerRelatedManager()
    anonymous = AnonymousManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['customer', 'action']),
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        who = self.customer.code if self.customer else 'Anonymous'
        return f'Event({who}: {self.action})'

    @property
    def is_anonymous(self) -> bool:
        return self.customer is None


class Tenant(models.Model):
    """
    Multi-tenant support।
    SaaS deployment এ প্রতিটি business তার নিজের tenant।

    AUDIT FIX (v2): Added Meta.indexes block।
    `slug` and `api_key` already have implicit indexes via unique=True, but the
    compound (slug, is_active) pattern -- "find active tenant by slug" -- was
    doing a B-tree scan on slug then a Python-level filter on is_active।
    The compound index covers this in a single index lookup।
    """
    name = models.CharField(max_length=200, verbose_name='Tenant Name')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    settings = models.JSONField(default=dict, blank=True)
    plan = models.CharField(max_length=50, default='standard')
    api_key = models.CharField(max_length=100, null=True, blank=True, unique=True)

    # Managers
    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        # AUDIT FIX (v2): Added indexes।  slug + api_key unique=True already
        # create individual B-tree indexes।  Compound (slug, is_active) added
        # for the most frequent lookup pattern used in middleware and
        # DjoyaltyTenantMixin।  Standalone (is_active,) covers admin list views।
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name
