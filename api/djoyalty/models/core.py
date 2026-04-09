# api/djoyalty/models/core.py
"""
Core models: Customer, Txn, Event
Original models.py থেকে নেওয়া + related_name fix + tenant isolation।
"""

from django.db import models
from django.contrib.auth import get_user_model
from ..managers import (
    ActiveCustomerManager, NewsletterCustomerManager,
    FullPriceTxnManager, DiscountedTxnManager, SpendingTxnManager, RecentTxnManager,
    CustomerRelatedEvtManager, AnonymousEvtManager, RecentEvtManager,
)

User = get_user_model()


class Customer(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_customer_tenant',
        db_index=True,
    )
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='loyalty_customer',
        help_text='Linked auth user (optional)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    code = models.CharField(max_length=32, unique=True)
    firstname = models.CharField(max_length=64, null=True, blank=True)
    lastname = models.CharField(max_length=64, null=True, blank=True)
    street = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    zip = models.CharField(max_length=16, null=True, blank=True)
    email = models.CharField(max_length=64, null=True, blank=True)
    phone = models.CharField(max_length=64, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    newsletter = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    birth_date = models.DateField(null=True, blank=True)
    referral_code = models.CharField(max_length=32, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='referrals',
    )

    objects = models.Manager()
    active = ActiveCustomerManager()
    newsletter_subscribers = NewsletterCustomerManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'email']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return '[{}] {}'.format(
            self.code,
            ' '.join(filter(None, [self.firstname, self.lastname]))
        )

    @property
    def full_name(self):
        return ' '.join(filter(None, [self.firstname, self.lastname])) or 'Unnamed'

    @property
    def current_tier(self):
        try:
            return self.user_tiers.filter(is_current=True).first()
        except Exception:
            return None

    @property
    def points_balance(self):
        try:
            lp = self.loyalty_points.first()
            return lp.balance if lp else 0
        except Exception:
            return 0


class Txn(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_txn_tenant',
        db_index=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(
        'Customer',
        related_name='transactions',
        on_delete=models.CASCADE,
    )
    value = models.DecimalField(decimal_places=2, max_digits=10)
    is_discount = models.BooleanField(default=False)
    reference = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    note = models.TextField(null=True, blank=True)

    objects = models.Manager()
    txn_full = FullPriceTxnManager()
    txn_discount = DiscountedTxnManager()
    spending = SpendingTxnManager()
    recent = RecentTxnManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_discount']),
        ]

    def __str__(self):
        return '{}{}@{} by {}'.format(
            self.value,
            '[X]' if self.is_discount else '',
            self.timestamp,
            self.customer,
        )


class Event(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='djoyalty_event_tenant',
        db_index=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(
        'Customer',
        related_name='events',
        null=True, blank=True,
        on_delete=models.CASCADE,
    )
    action = models.CharField(max_length=128, db_index=True)
    description = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True, default=dict)

    objects = models.Manager()
    customer_related = CustomerRelatedEvtManager()
    anonymous = AnonymousEvtManager()
    recent = RecentEvtManager()

    class Meta:
        app_label = 'djoyalty'
        indexes = [
            models.Index(fields=['tenant', 'customer']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return '{} @ {} by {}'.format(
            self.action,
            self.timestamp,
            self.customer or 'Anonymous',
        )
