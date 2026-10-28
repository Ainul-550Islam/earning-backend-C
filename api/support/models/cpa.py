"""
api/support/models/cpa.py
CPA-specific support models: the single registration point.

Merged from two competing definitions:
  * the shadowed legacy api/support/models.py (never loaded)
  * api/support/cpa/models.py (now a re-export shim)
"""
from django.db import models
from django.conf import settings


class OfferDispute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('investigating', 'Investigating'),
        ('approved', 'Approved'), ('rejected', 'Rejected'),
        ('escalated', 'Escalated'), ('needs_proof', 'Needs Proof'),
    ]
    tenant              = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='support_offerdispute_tenant')
    user                = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offer_disputes')
    ticket              = models.ForeignKey('support.SupportTicket', null=True, blank=True, on_delete=models.SET_NULL)
    offer_id            = models.CharField(max_length=200, blank=True, default='', db_index=True)
    offer_name          = models.CharField(max_length=500, blank=True, default='')
    expected_amount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    click_id            = models.CharField(max_length=200, blank=True, default='')
    proof_url           = models.URLField(blank=True, default='')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    verification_status = models.CharField(max_length=30, blank=True, default='unknown')
    confidence_score    = models.FloatField(default=0.0)
    resolved_amount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agent_notes         = models.TextField(blank=True, default='')
    created_at          = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_offer_dispute'

    def __str__(self):
        return f'Dispute: {self.offer_id} [{self.status}]'


class WithdrawalDispute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('reviewing', 'Reviewing'),
        ('resolved', 'Resolved'), ('rejected', 'Rejected'),
    ]
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_disputes')
    ticket           = models.ForeignKey('support.SupportTicket', on_delete=models.SET_NULL, null=True, blank=True)
    transaction_id   = models.CharField(max_length=200, blank=True, default='')
    amount           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method   = models.CharField(max_length=50, blank=True, default='')
    account_number   = models.CharField(max_length=100, blank=True, default='')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    resolution_notes = models.TextField(blank=True, default='')
    created_at       = models.DateTimeField(auto_now_add=True)
    resolved_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_withdrawal_dispute'


class NetworkAnnouncement(models.Model):
    TYPE_CHOICES = [
        ('info', 'Info'), ('warning', 'Warning'),
        ('maintenance', 'Maintenance'), ('update', 'Update'),
    ]
    tenant         = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='support_networkannouncement_tenant')
    title          = models.CharField(max_length=300)
    content        = models.TextField()
    type           = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_active      = models.BooleanField(default=True, db_index=True)
    show_in_app    = models.BooleanField(default=True)
    show_in_portal = models.BooleanField(default=True)
    show_in_ticket = models.BooleanField(default=False)
    target_tiers   = models.JSONField(default=list, blank=True, help_text='Empty = all tiers')
    starts_at      = models.DateTimeField(null=True, blank=True)
    ends_at        = models.DateTimeField(null=True, blank=True)
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'support_network_announcement'

    def __str__(self):
        return f'[{self.type.upper()}] {self.title}'


class PublisherProfile(models.Model):
    """Publisher support profile, extends User"""
    TIER_CHOICES = [('vip', 'VIP'), ('gold', 'Gold'), ('silver', 'Silver'), ('standard', 'Standard'), ('new', 'New')]
    user              = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='publisher_support_profile')
    tier              = models.CharField(max_length=20, choices=TIER_CHOICES, default='new', db_index=True)
    account_manager   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_publishers')
    health_score      = models.IntegerField(default=100)
    total_disputes    = models.IntegerField(default=0)
    approved_disputes = models.IntegerField(default=0)
    is_flagged        = models.BooleanField(default=False)
    notes             = models.TextField(blank=True, default='')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'support_publisher_profile'

    def __str__(self):
        return f'{self.user.username} [{self.tier}] score={self.health_score}'
