from django.conf import settings as _sl_settings
_OFFER_MODEL = getattr(_sl_settings, 'SMARTLINK_OFFER_MODEL', 'offer_inventory.Offer')
_ADVERTISER_MODEL = getattr(_sl_settings, 'SMARTLINK_ADVERTISER_MODEL', 'advertiser_portal.Advertiser')

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
        _ADVERTISER_MODEL, on_delete=models.CASCADE,
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
        _ADVERTISER_MODEL, on_delete=models.CASCADE,
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

class SubPublisher(models.Model):
    """
    Sub-publisher / referral chain model.
    Enables multi-level affiliate structures where a publisher can refer
    other publishers and earn a percentage of their referrals' earnings.

    Structure:
        parent_publisher → refers → child_publisher
        Parent earns commission_pct % of child's net payout.

    This model is referenced in PublisherPayoutService to compute
    sub-publisher referral commissions during payout calculation.
    """

    class CommissionType(models.TextChoices):
        PERCENTAGE = 'percent', _('Percentage of sub-publisher earnings')
        FLAT       = 'flat',    _('Flat rate per valid click')

    parent_publisher = models.ForeignKey(
        _sl_settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sub_publishers',
        verbose_name=_('Referring publisher'),
    )
    child_publisher  = models.OneToOneField(
        _sl_settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='smartlink_referred_by',
        verbose_name=_('Referred publisher'),
    )
    commission_type  = models.CharField(
        max_length=10,
        choices=CommissionType.choices,
        default=CommissionType.PERCENTAGE,
    )
    commission_pct   = models.DecimalField(
        _('Commission %'), max_digits=5, decimal_places=2, default=5,
        help_text=_('Percentage of sub-publisher net earnings paid to parent. e.g. 5 = 5%.'),
    )
    commission_flat  = models.DecimalField(
        _('Flat rate (USD per click)'), max_digits=8, decimal_places=4, default=0,
        help_text=_('Used when commission_type=flat. USD per valid non-fraud click.'),
    )
    is_active        = models.BooleanField(default=True)
    referral_code    = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text=_('Unique code the parent shares for referrals.'),
    )
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    approved_at      = models.DateTimeField(null=True, blank=True)
    lifetime_earned  = models.DecimalField(
        _('Lifetime commission earned (USD)'),
        max_digits=14, decimal_places=4, default=0,
    )

    class Meta:
        db_table     = 'sl_sub_publisher'
        verbose_name = _('Sub-Publisher')
        indexes      = [
            models.Index(fields=['parent_publisher', 'is_active']),
        ]

    def __str__(self):
        return (
            f"{self.parent_publisher.username} → "
            f"{self.child_publisher.username} ({self.commission_pct}%)"
        )

    def calculate_commission(self, child_net_payout: float) -> float:
        """
        Calculate the commission owed to the parent for a given child payout.
        """
        if not self.is_active:
            return 0.0
        if self.commission_type == self.CommissionType.PERCENTAGE:
            return round(child_net_payout * float(self.commission_pct) / 100, 4)
        return 0.0  # flat rate handled separately per click

    @classmethod
    def generate_referral_code(cls) -> str:
        """Generate a unique 8-char referral code."""
        import secrets, string
        charset = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = ''.join(secrets.choice(charset) for _ in range(8))
            if not cls.objects.filter(referral_code=code).exists():
                return code
        raise RuntimeError('Could not generate unique referral code after 20 attempts')
