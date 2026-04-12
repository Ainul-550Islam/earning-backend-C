from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .smartlink import SmartLink
from ..choices import DomainVerificationStatus
from ..validators import validate_custom_domain, validate_sub_id_value

User = get_user_model()


class PublisherSmartLink(models.Model):
    """
    Publisher ↔ SmartLink assignment.
    A publisher can have multiple SmartLinks, and an admin can assign
    a SmartLink to a specific publisher with permissions and notes.
    """
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='publisher_smartlinks',
        verbose_name=_('Publisher'),
    )
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='publisher_assignments',
    )
    is_active = models.BooleanField(default=True)
    can_edit_targeting = models.BooleanField(
        default=True,
        help_text=_('Allow publisher to edit targeting rules.')
    )
    can_edit_pool = models.BooleanField(
        default=False,
        help_text=_('Allow publisher to add/remove offers from pool.')
    )
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='assigned_smartlinks',
    )
    notes = models.TextField(blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_publisher_smartlink'
        verbose_name = _('Publisher SmartLink')
        unique_together = [('publisher', 'smartlink')]
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.publisher.username} ↔ {self.smartlink.slug}"


class PublisherSubID(models.Model):
    """
    Sub-ID parameter definitions for a publisher.
    Defines what sub1-sub5 mean for a specific publisher
    (e.g., sub1 = campaign_id, sub2 = adset_id).
    """
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='sub_id_definitions',
    )
    smartlink = models.ForeignKey(
        SmartLink, on_delete=models.CASCADE,
        related_name='sub_id_definitions',
        null=True, blank=True,
        help_text=_('If null, applies to all publisher SmartLinks.')
    )
    sub1_label = models.CharField(max_length=50, blank=True, default='sub1')
    sub2_label = models.CharField(max_length=50, blank=True, default='sub2')
    sub3_label = models.CharField(max_length=50, blank=True, default='sub3')
    sub4_label = models.CharField(max_length=50, blank=True, default='sub4')
    sub5_label = models.CharField(max_length=50, blank=True, default='sub5')
    sub1_required = models.BooleanField(default=False)
    sub2_required = models.BooleanField(default=False)
    sub3_required = models.BooleanField(default=False)
    sub4_required = models.BooleanField(default=False)
    sub5_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_publisher_sub_id'
        verbose_name = _('Publisher Sub ID Definition')

    def __str__(self):
        return f"SubID Def: {self.publisher.username} | {self.sub1_label}/{self.sub2_label}/..."


class PublisherDomain(models.Model):
    """
    Custom domain verification for a publisher.
    Publisher verifies ownership via DNS TXT record.
    Once verified, domain can be used as redirect base.
    """
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='verified_domains',
    )
    domain = models.CharField(
        max_length=253,
        unique=True,
        validators=[validate_custom_domain],
        verbose_name=_('Domain'),
    )
    verification_status = models.CharField(
        max_length=10,
        choices=DomainVerificationStatus.choices,
        default=DomainVerificationStatus.PENDING,
        db_index=True,
    )
    verification_token = models.CharField(
        max_length=64,
        blank=True,
        help_text=_('TXT record value for DNS verification.')
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_enabled = models.BooleanField(default=False)
    ssl_expires_at = models.DateTimeField(null=True, blank=True)
    is_primary = models.BooleanField(
        default=False,
        help_text=_('Primary domain for this publisher.')
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sl_publisher_domain'
        verbose_name = _('Publisher Domain')
        ordering = ['-is_primary', 'domain']

    def __str__(self):
        return f"{self.domain} [{self.verification_status}] — {self.publisher.username}"

    @property
    def dns_txt_record(self):
        from ..constants import DOMAIN_DNS_TXT_PREFIX
        return f"{DOMAIN_DNS_TXT_PREFIX}{self.verification_token}"


class PublisherAllowList(models.Model):
    """
    Allowed offer categories/verticals per publisher.
    Admin controls which offer categories a publisher can access.
    """
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='allowed_categories',
    )
    category = models.CharField(
        max_length=100,
        help_text=_('Offer category/vertical name. e.g. "finance", "gaming", "health"')
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='publisher_allowlists',
        help_text=_('Specific advertiser access grant. Null = all advertisers in category.')
    )
    is_active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='granted_allowlists',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sl_publisher_allowlist'
        verbose_name = _('Publisher Allow List')
        unique_together = [('publisher', 'category', 'advertiser')]

    def __str__(self):
        return f"Allow: {self.publisher.username} → {self.category}"


class PublisherBlockList(models.Model):
    """
    Blocked advertisers or offer categories per publisher.
    Prevents specific advertiser offers from showing to this publisher's traffic.
    """
    publisher = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='blocked_advertisers',
    )
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='publisher_blocklists',
    )
    category = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    blocked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_blocklists',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sl_publisher_blocklist'
        verbose_name = _('Publisher Block List')

    def __str__(self):
        target = self.advertiser or self.category or 'unknown'
        return f"Block: {self.publisher.username} ✗ {target}"
