"""
b2b_models.py — Complete B2B partner system models.

Covers:
  1. OrganizationAccount     — Publisher / Advertiser / Agency accounts
  2. B2BAPIKey               — API key auth for partner integrations
  3. OrganizationRole        — RBAC roles per organisation
  4. OrganizationMember      — User ↔ Organisation membership + role
  5. RevenueShareRule        — Per-partner revenue split configuration
  6. AdvertiserBudgetCap     — Monthly/daily spend cap per advertiser
  7. B2BContract             — Service agreements with validity dates
  8. B2BInvoice              — Monthly billing statements
  9. OutboundWebhookSub      — Partners subscribe to postback events
 10. WhiteLabelConfig        — Per-tenant brand/domain customisation
 11. ImpersonationLog        — Admin-acts-as-partner audit trail
 12. PartnerCreditLedger     — Prepaid credit balance per partner
"""
import hashlib
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ── 1. OrganizationAccount ────────────────────────────────────────────────────

class OrganizationAccount(models.Model):
    """
    A B2B partner account — Publisher, Advertiser, or Agency.

    Publishers:  embed the offerwall, send users to complete offers.
    Advertisers: fund campaigns, define offers, receive postbacks.
    Agencies:    manage multiple sub-accounts (Publishers or Advertisers).
    """
    ACCOUNT_TYPES = [
        ("publisher",   "Publisher"),
        ("advertiser",  "Advertiser"),
        ("agency",      "Agency"),
        ("reseller",    "Reseller"),
        ("internal",    "Internal / House Account"),
    ]
    STATUS = [
        ("pending",    "Pending Approval"),
        ("active",     "Active"),
        ("suspended",  "Suspended"),
        ("terminated", "Terminated"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_type     = models.CharField(_("account type"), max_length=12, choices=ACCOUNT_TYPES, db_index=True)
    name             = models.CharField(_("company name"), max_length=300)
    slug             = models.SlugField(_("slug"), max_length=300, unique=True)
    status           = models.CharField(_("status"), max_length=12, choices=STATUS, default="pending", db_index=True)

    # Contact
    contact_name     = models.CharField(_("contact name"), max_length=200, blank=True)
    contact_email    = models.EmailField(_("contact email"), blank=True)
    contact_phone    = models.CharField(_("contact phone"), max_length=30, blank=True)
    website          = models.URLField(_("website"), blank=True)
    country_code     = models.CharField(_("country"), max_length=2, blank=True)

    # Ownership
    owner            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="postback_owned_organizations",
    )
    parent_agency    = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sub_accounts", verbose_name=_("parent agency"),
        limit_choices_to={"account_type__in": ["agency", "reseller"]},
    )

    # Financial
    currency         = models.CharField(_("currency"), max_length=3, default="BDT")
    payment_terms_days = models.PositiveSmallIntegerField(_("payment terms (days)"), default=30)
    tax_id           = models.CharField(_("tax ID / VAT"), max_length=50, blank=True)

    # Metadata
    notes            = models.TextField(_("internal notes"), blank=True)
    metadata         = models.JSONField(_("metadata"), default=dict, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("organization account")
        verbose_name_plural = _("organization accounts")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["account_type", "status"], name="idx_org_type_status_4001"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def is_active(self):
        return self.status == "active"


# ── 2. B2BAPIKey ──────────────────────────────────────────────────────────────

class B2BAPIKey(models.Model):
    """
    Scoped API keys for partner integrations.
    One organisation can have multiple keys (rotate without downtime).
    """
    SCOPES = [
        ("read",            "Read-only"),
        ("postback",        "Receive postbacks"),
        ("offers",          "Offer catalogue"),
        ("reporting",       "Reporting & analytics"),
        ("withdrawals",     "Withdrawals"),
        ("full",            "Full access"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="api_keys",
    )
    name             = models.CharField(_("key name"), max_length=200,
                                        help_text=_("e.g. 'Production', 'Staging', 'Mobile SDK'"))
    key_prefix       = models.CharField(_("key prefix"), max_length=8, db_index=True,
                                        help_text=_("First 8 chars — shown in UI for identification."))
    key_hash         = models.CharField(_("key hash"), max_length=64,
                                        help_text=_("SHA-256 of full key — never store plaintext."))
    scopes           = models.JSONField(_("scopes"), default=list,
                                        help_text=_("List of allowed scope strings."))
    is_active        = models.BooleanField(_("active"), default=True, db_index=True)
    ip_whitelist     = models.JSONField(_("IP whitelist"), default=list, blank=True,
                                        help_text=_("Empty = allow all IPs."))
    last_used_at     = models.DateTimeField(_("last used at"), null=True, blank=True)
    expires_at       = models.DateTimeField(_("expires at"), null=True, blank=True)
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="postback_b2b_created_api_keys",
    )
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("B2B API key")
        verbose_name_plural = _("B2B API keys")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.key_prefix}... — {self.organization} ({self.name})"

    @classmethod
    def generate(cls, organization, name, scopes, created_by=None, expires_at=None):
        """Generate a new API key. Returns (instance, raw_key). raw_key shown only once."""
        raw_key   = f"pb_{secrets.token_urlsafe(32)}"
        prefix    = raw_key[:8]
        key_hash  = hashlib.sha256(raw_key.encode()).hexdigest()
        instance  = cls.objects.create(
            organization=organization,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=scopes,
            created_by=created_by,
            expires_at=expires_at,
        )
        return instance, raw_key

    @classmethod
    def verify(cls, raw_key: str):
        """Look up a key by hash. Returns the B2BAPIKey or None."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            key = cls.objects.select_related("organization").get(
                key_hash=key_hash, is_active=True,
            )
        except cls.DoesNotExist:
            return None
        if key.expires_at and key.expires_at < timezone.now():
            return None
        cls.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "full" in self.scopes

    def is_ip_allowed(self, ip: str) -> bool:
        if not self.ip_whitelist:
            return True
        return ip in self.ip_whitelist


# ── 3. OrganizationRole ───────────────────────────────────────────────────────

class OrganizationRole(models.Model):
    """
    RBAC roles per organisation — Admin, Manager, Analyst, ReadOnly, Finance.
    """
    PRESET_ROLES = [
        ("owner",    "Owner"),
        ("admin",    "Admin"),
        ("manager",  "Manager"),
        ("analyst",  "Analyst (read-only reports)"),
        ("finance",  "Finance (billing & withdrawals)"),
        ("readonly", "Read Only"),
        ("custom",   "Custom"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="roles",
    )
    name             = models.CharField(_("role name"), max_length=100)
    preset           = models.CharField(_("preset"), max_length=10, choices=PRESET_ROLES, default="custom")
    permissions      = models.JSONField(
        _("permissions"), default=list,
        help_text=_("List of permission codenames, e.g. ['view_postbacks', 'manage_offers']."),
    )
    is_system        = models.BooleanField(_("system role"), default=False,
                                           help_text=_("System roles cannot be deleted."))

    class Meta:
        verbose_name = _("organization role")
        verbose_name_plural = _("organization roles")
        unique_together = [("organization", "name")]

    def __str__(self):
        return f"{self.organization.slug}::{self.name}"

    def has_permission(self, codename: str) -> bool:
        return codename in self.permissions or "all" in self.permissions


# ── 4. OrganizationMember ─────────────────────────────────────────────────────

class OrganizationMember(models.Model):
    """Links a Django User to an OrganizationAccount with a specific role."""
    STATUS = [
        ("invited",  "Invited (pending acceptance)"),
        ("active",   "Active"),
        ("suspended","Suspended"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="members",
    )
    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="org_memberships",
    )
    role             = models.ForeignKey(
        OrganizationRole, on_delete=models.PROTECT, related_name="members",
    )
    status           = models.CharField(_("status"), max_length=10, choices=STATUS, default="invited")
    invited_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sent_invitations",
    )
    joined_at        = models.DateTimeField(_("joined at"), null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("organization member")
        verbose_name_plural = _("organization members")
        unique_together = [("organization", "user")]

    def __str__(self):
        return f"{self.user} @ {self.organization} [{self.role.name}]"

    def accept_invitation(self):
        self.status = "active"
        self.joined_at = timezone.now()
        self.save(update_fields=["status", "joined_at"])


# ── 5. RevenueShareRule ───────────────────────────────────────────────────────

class RevenueShareRule(models.Model):
    """
    Defines revenue split between platform and a Publisher.
    Supports: flat CPA, revenue % share, tiered (volume-based).
    """
    RULE_TYPES = [
        ("flat_cpa",    "Flat CPA (fixed payout per conversion)"),
        ("rev_share",   "Revenue share (% of advertiser payout)"),
        ("tiered",      "Tiered (different rates per volume tier)"),
        ("hybrid",      "Hybrid (flat + rev share)"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="rev_share_rules",
        limit_choices_to={"account_type": "publisher"},
    )
    network          = models.ForeignKey(
        "postback.NetworkPostbackConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="rev_share_rules",
        help_text=_("Leave blank to apply to all networks."),
    )
    rule_type        = models.CharField(_("rule type"), max_length=12, choices=RULE_TYPES, default="rev_share")
    flat_cpa_bdt     = models.DecimalField(_("flat CPA (BDT)"), max_digits=10, decimal_places=2, default=0)
    rev_share_pct    = models.DecimalField(_("rev share %"), max_digits=5, decimal_places=2, default=70,
                                            help_text=_("Publisher gets this % of network payout."))
    min_payout_bdt   = models.DecimalField(_("min payout (BDT)"), max_digits=10, decimal_places=2, default=0)
    max_payout_bdt   = models.DecimalField(_("max payout cap (BDT)"), max_digits=10, decimal_places=2, default=0,
                                            help_text=_("0 = no cap."))
    tiers            = models.JSONField(_("tiers"), default=list, blank=True,
                                        help_text=_(
                                            "For tiered type: [{min_conversions, max_conversions, pct}, ...]"
                                        ))
    is_active        = models.BooleanField(_("active"), default=True)
    valid_from       = models.DateField(_("valid from"), default=timezone.now)
    valid_until      = models.DateField(_("valid until"), null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("revenue share rule")
        verbose_name_plural = _("revenue share rules")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} — {self.get_rule_type_display()} ({self.rev_share_pct}%)"

    def calculate_publisher_payout(self, gross_payout_bdt: Decimal, conversions_this_month: int = 0) -> Decimal:
        """Return the publisher's share in BDT."""
        if self.rule_type == "flat_cpa":
            amt = self.flat_cpa_bdt
        elif self.rule_type == "rev_share":
            amt = gross_payout_bdt * self.rev_share_pct / 100
        elif self.rule_type == "tiered" and self.tiers:
            pct = Decimal("70")
            for tier in self.tiers:
                if tier["min_conversions"] <= conversions_this_month <= tier.get("max_conversions", 10**9):
                    pct = Decimal(str(tier["pct"]))
                    break
            amt = gross_payout_bdt * pct / 100
        elif self.rule_type == "hybrid":
            amt = self.flat_cpa_bdt + (gross_payout_bdt * self.rev_share_pct / 100)
        else:
            amt = Decimal("0")

        if self.max_payout_bdt > 0:
            amt = min(amt, self.max_payout_bdt)
        return max(amt, self.min_payout_bdt)


# ── 6. AdvertiserBudgetCap ────────────────────────────────────────────────────

class AdvertiserBudgetCap(models.Model):
    """
    Monthly / daily spend cap for an Advertiser.
    Prevents overspend before invoice settlement.
    """
    PERIOD = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="budget_caps",
        limit_choices_to={"account_type": "advertiser"},
    )
    network          = models.ForeignKey(
        "postback.NetworkPostbackConfig", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="budget_caps",
    )
    period           = models.CharField(_("period"), max_length=8, choices=PERIOD, default="monthly")
    cap_bdt          = models.DecimalField(_("cap (BDT)"), max_digits=14, decimal_places=2)
    cap_conversions  = models.PositiveIntegerField(_("cap (conversions)"), default=0,
                                                    help_text=_("0 = no conversion cap."))
    current_spend    = models.DecimalField(_("current spend (BDT)"), max_digits=14, decimal_places=2, default=0)
    current_conversions = models.PositiveIntegerField(_("current conversions"), default=0)
    period_start     = models.DateField(_("period start"), default=timezone.now, db_index=True)
    is_active        = models.BooleanField(_("active"), default=True)
    alert_threshold_pct = models.PositiveSmallIntegerField(_("alert at %"), default=80,
                                                            help_text=_("Send alert when spend hits this %."))
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("advertiser budget cap")
        verbose_name_plural = _("advertiser budget caps")
        unique_together = [("organization", "network", "period", "period_start")]

    def __str__(self):
        return f"{self.organization} — {self.period} cap {self.cap_bdt} BDT"

    @property
    def remaining_bdt(self) -> Decimal:
        return max(Decimal("0"), self.cap_bdt - self.current_spend)

    @property
    def is_exhausted(self) -> bool:
        return self.current_spend >= self.cap_bdt

    @property
    def utilisation_pct(self) -> float:
        if self.cap_bdt == 0:
            return 0.0
        return float(self.current_spend / self.cap_bdt * 100)


# ── 7. B2BContract ────────────────────────────────────────────────────────────

class B2BContract(models.Model):
    """Service-level agreement / contract between platform and a partner."""
    STATUS = [
        ("draft",     "Draft"),
        ("sent",      "Sent for Signature"),
        ("signed",    "Signed & Active"),
        ("expired",   "Expired"),
        ("terminated","Terminated"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="contracts",
    )
    title            = models.CharField(_("contract title"), max_length=300)
    status           = models.CharField(_("status"), max_length=12, choices=STATUS, default="draft")
    contract_number  = models.CharField(_("contract number"), max_length=50, unique=True, blank=True)
    signed_at        = models.DateTimeField(_("signed at"), null=True, blank=True)
    valid_from       = models.DateField(_("valid from"), null=True, blank=True)
    valid_until      = models.DateField(_("valid until"), null=True, blank=True)
    document_url     = models.URLField(_("document URL"), blank=True,
                                       help_text=_("Signed PDF URL (S3, GDrive, etc.)"))
    terms_summary    = models.TextField(_("terms summary"), blank=True)
    monthly_minimum  = models.DecimalField(_("monthly minimum (BDT)"), max_digits=14, decimal_places=2, default=0)
    revenue_share_rule = models.ForeignKey(
        RevenueShareRule, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="contracts",
    )
    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="created_contracts",
    )
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("B2B contract")
        verbose_name_plural = _("B2B contracts")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.contract_number or self.id} — {self.organization} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.contract_number:
            import datetime
            year = datetime.date.today().year
            count = B2BContract.objects.filter(created_at__year=year).count() + 1
            self.contract_number = f"CTR-{year}-{count:05d}"
        super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        import datetime
        today = datetime.date.today()
        if self.status != "signed":
            return False
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return True


# ── 8. B2BInvoice ─────────────────────────────────────────────────────────────

class B2BInvoice(models.Model):
    """Monthly billing statement generated for publishers and advertisers."""
    STATUS = [
        ("draft",     "Draft"),
        ("sent",      "Sent"),
        ("paid",      "Paid"),
        ("overdue",   "Overdue"),
        ("cancelled", "Cancelled"),
        ("disputed",  "Disputed"),
    ]
    INVOICE_TYPES = [
        ("publisher_payout", "Publisher Payout"),
        ("advertiser_charge","Advertiser Charge"),
        ("platform_fee",     "Platform Fee"),
        ("adjustment",       "Adjustment"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="invoices",
    )
    invoice_number   = models.CharField(_("invoice number"), max_length=50, unique=True, blank=True)
    invoice_type     = models.CharField(_("type"), max_length=20, choices=INVOICE_TYPES)
    status           = models.CharField(_("status"), max_length=12, choices=STATUS, default="draft")

    # Period
    period_start     = models.DateField(_("period start"))
    period_end       = models.DateField(_("period end"))

    # Amounts
    subtotal_bdt     = models.DecimalField(_("subtotal (BDT)"), max_digits=14, decimal_places=2, default=0)
    tax_bdt          = models.DecimalField(_("tax (BDT)"), max_digits=12, decimal_places=2, default=0)
    total_bdt        = models.DecimalField(_("total (BDT)"), max_digits=14, decimal_places=2, default=0)
    conversions      = models.PositiveIntegerField(_("total conversions"), default=0)
    line_items       = models.JSONField(_("line items"), default=list,
                                        help_text=_(
                                            "[{description, quantity, unit_price_bdt, total_bdt}, ...]"
                                        ))

    # Dates
    issued_at        = models.DateTimeField(_("issued at"), null=True, blank=True)
    due_date         = models.DateField(_("due date"), null=True, blank=True)
    paid_at          = models.DateTimeField(_("paid at"), null=True, blank=True)
    payment_reference = models.CharField(_("payment reference"), max_length=255, blank=True)

    notes            = models.TextField(_("notes"), blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("B2B invoice")
        verbose_name_plural = _("B2B invoices")
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["organization", "status"], name="idx_invoice_org_status_4010"),
            models.Index(fields=["status", "due_date"],     name="idx_invoice_status_due_4011"),
        ]

    def __str__(self):
        return f"{self.invoice_number} — {self.organization} — {self.total_bdt} BDT ({self.status})"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import datetime
            year = datetime.date.today().year
            month = datetime.date.today().month
            count = B2BInvoice.objects.filter(
                created_at__year=year, created_at__month=month
            ).count() + 1
            self.invoice_number = f"INV-{year}{month:02d}-{count:05d}"
        self.total_bdt = self.subtotal_bdt + self.tax_bdt
        super().save(*args, **kwargs)

    def mark_paid(self, payment_reference: str = ""):
        self.status = "paid"
        self.paid_at = timezone.now()
        self.payment_reference = payment_reference
        self.save(update_fields=["status", "paid_at", "payment_reference", "updated_at"])


# ── 9. OutboundWebhookSubscription ───────────────────────────────────────────

class OutboundWebhookSubscription(models.Model):
    """
    Partners subscribe to postback events (conversion, reversal, fraud_flag)
    and receive real-time HTTP POST callbacks to their endpoint.
    """
    EVENT_TYPES = [
        ("conversion",   "New conversion postback"),
        ("reversal",     "Postback reversal / chargeback"),
        ("fraud_flag",   "Fraud flagged"),
        ("cap_reached",  "Budget cap reached"),
        ("daily_summary","Daily summary"),
        ("all",          "All events"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="webhook_subscriptions",
    )
    endpoint_url     = models.URLField(_("endpoint URL"), max_length=2000)
    event_types      = models.JSONField(_("event types"), default=list,
                                        help_text=_("List of event type keys to subscribe to."))
    secret           = models.CharField(_("signing secret"), max_length=256,
                                        help_text=_("HMAC-SHA256 secret — included as X-Webhook-Sig header."))
    is_active        = models.BooleanField(_("active"), default=True, db_index=True)
    failure_count    = models.PositiveSmallIntegerField(_("consecutive failures"), default=0)
    last_triggered_at = models.DateTimeField(_("last triggered at"), null=True, blank=True)
    last_success_at  = models.DateTimeField(_("last success at"), null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("outbound webhook subscription")
        verbose_name_plural = _("outbound webhook subscriptions")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} → {self.endpoint_url[:60]}"

    def build_signature(self, payload: bytes) -> str:
        import hmac, hashlib
        return hmac.new(self.secret.encode(), payload, hashlib.sha256).hexdigest()

    def record_success(self):
        self.failure_count = 0
        self.last_success_at = timezone.now()
        self.last_triggered_at = timezone.now()
        self.save(update_fields=["failure_count", "last_success_at", "last_triggered_at"])

    def record_failure(self):
        self.failure_count += 1
        self.last_triggered_at = timezone.now()
        if self.failure_count >= 10:
            self.is_active = False  # Auto-disable after 10 consecutive failures
        self.save(update_fields=["failure_count", "last_triggered_at", "is_active"])


# ── 10. WhiteLabelConfig ──────────────────────────────────────────────────────

class WhiteLabelConfig(models.Model):
    """
    Per-organisation white-label branding — custom domain, logo, colours.
    Enables resellers / agencies to offer the platform under their brand.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.OneToOneField(
        OrganizationAccount, on_delete=models.CASCADE, related_name="white_label",
    )
    brand_name       = models.CharField(_("brand name"), max_length=200)
    custom_domain    = models.CharField(_("custom domain"), max_length=253, blank=True, unique=True,
                                        help_text=_("e.g. 'earn.mybrand.com'. Must have DNS CNAME set up."))
    logo_url         = models.URLField(_("logo URL"), blank=True)
    favicon_url      = models.URLField(_("favicon URL"), blank=True)
    primary_color    = models.CharField(_("primary colour"), max_length=7, default="#2196F3")
    secondary_color  = models.CharField(_("secondary colour"), max_length=7, default="#FF9800")
    font_family      = models.CharField(_("font family"), max_length=100, default="Inter, sans-serif")
    support_email    = models.EmailField(_("support email"), blank=True)
    support_url      = models.URLField(_("support URL"), blank=True)
    privacy_url      = models.URLField(_("privacy policy URL"), blank=True)
    terms_url        = models.URLField(_("terms of service URL"), blank=True)
    hide_platform_branding = models.BooleanField(_("hide platform branding"), default=False)
    custom_css       = models.TextField(_("custom CSS"), blank=True)
    custom_js        = models.TextField(_("custom JS"), blank=True,
                                        help_text=_("Injected in <head>. Use responsibly."))
    ssl_verified     = models.BooleanField(_("SSL verified"), default=False)
    is_active        = models.BooleanField(_("active"), default=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("white-label config")
        verbose_name_plural = _("white-label configs")

    def __str__(self):
        return f"{self.brand_name} ({self.custom_domain or 'no domain'})"


# ── 11. ImpersonationLog ──────────────────────────────────────────────────────

class ImpersonationLog(models.Model):
    """
    Audit trail when a platform admin impersonates a partner user.
    Required for compliance and dispute resolution.
    """
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="impersonations_performed",
    )
    impersonated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="impersonations_received",
    )
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="impersonation_logs",
    )
    reason           = models.CharField(_("reason"), max_length=500,
                                        help_text=_("Required: why is this impersonation needed?"))
    session_token    = models.CharField(_("session token"), max_length=64, unique=True)
    started_at       = models.DateTimeField(_("started at"), default=timezone.now, db_index=True)
    ended_at         = models.DateTimeField(_("ended at"), null=True, blank=True)
    source_ip        = models.GenericIPAddressField(_("admin IP"), null=True, blank=True)
    actions_log      = models.JSONField(_("actions log"), default=list,
                                        help_text=_("List of {action, timestamp} tuples."))

    class Meta:
        verbose_name = _("impersonation log")
        verbose_name_plural = _("impersonation logs")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.admin_user} → {self.impersonated_user} @ {self.started_at:%Y-%m-%d %H:%M}"

    @classmethod
    def start_session(cls, admin_user, impersonated_user, reason, source_ip=None):
        token = secrets.token_urlsafe(32)
        return cls.objects.create(
            admin_user=admin_user,
            impersonated_user=impersonated_user,
            organization=getattr(
                OrganizationMember.objects.filter(user=impersonated_user).first(),
                "organization", None,
            ),
            reason=reason,
            session_token=token,
            source_ip=source_ip,
        )

    def end_session(self):
        self.ended_at = timezone.now()
        self.save(update_fields=["ended_at"])

    @property
    def duration_minutes(self):
        if not self.ended_at:
            return None
        return int((self.ended_at - self.started_at).total_seconds() / 60)


# ── 12. PartnerCreditLedger ───────────────────────────────────────────────────

class PartnerCreditLedger(models.Model):
    """
    Prepaid credit balance for Advertisers.
    Advertisers top-up in advance; each conversion deducts from their balance.
    """
    ENTRY_TYPES = [
        ("topup",        "Top-up (credit added)"),
        ("deduction",    "Conversion deduction"),
        ("refund",       "Reversal refund"),
        ("fee",          "Platform fee"),
        ("adjustment",   "Manual adjustment"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization     = models.ForeignKey(
        OrganizationAccount, on_delete=models.CASCADE, related_name="credit_ledger",
        limit_choices_to={"account_type__in": ["advertiser", "agency"]},
    )
    entry_type       = models.CharField(_("entry type"), max_length=12, choices=ENTRY_TYPES)
    amount_bdt       = models.DecimalField(_("amount (BDT)"), max_digits=14, decimal_places=2,
                                           help_text=_("Positive = credit. Negative = debit."))
    balance_after    = models.DecimalField(_("balance after (BDT)"), max_digits=14, decimal_places=2)
    reference        = models.CharField(_("reference"), max_length=255, blank=True,
                                        help_text=_("Invoice ID, postback log ID, etc."))
    note             = models.TextField(_("note"), blank=True)
    performed_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="credit_entries_performed",
    )
    created_at       = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("partner credit ledger entry")
        verbose_name_plural = _("partner credit ledger entries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"], name="idx_credit_org_date_4020"),
        ]

    def __str__(self):
        sign = "+" if self.amount_bdt >= 0 else ""
        return f"{self.organization} {sign}{self.amount_bdt} BDT → bal {self.balance_after} ({self.entry_type})"

    @classmethod
    def get_balance(cls, organization) -> Decimal:
        latest = cls.objects.filter(organization=organization).order_by("-created_at").first()
        return latest.balance_after if latest else Decimal("0")

    @classmethod
    def credit(cls, organization, amount_bdt: Decimal, entry_type="topup",
               reference="", note="", performed_by=None) -> "PartnerCreditLedger":
        from django.db import transaction
        with transaction.atomic():
            current = cls.get_balance(organization)
            new_balance = current + amount_bdt
            return cls.objects.create(
                organization=organization,
                entry_type=entry_type,
                amount_bdt=amount_bdt,
                balance_after=new_balance,
                reference=reference,
                note=note,
                performed_by=performed_by,
            )
