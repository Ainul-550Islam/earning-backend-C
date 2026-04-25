"""
models.py – Postback Engine Database Models.

Architecture:
  ┌─────────────────────────────────────────────────────────┐
  │  TRACKING CORE                                           │
  │   ClickLog → PostbackRawLog → Conversion → Impression   │
  ├─────────────────────────────────────────────────────────┤
  │  NETWORK MANAGEMENT                                      │
  │   AdNetworkConfig → NetworkAdapterMapping → OfferPostback│
  ├─────────────────────────────────────────────────────────┤
  │  FRAUD & SECURITY                                        │
  │   FraudAttemptLog → IPBlacklist → ConversionDeduplication│
  ├─────────────────────────────────────────────────────────┤
  │  QUEUE & RELIABILITY                                     │
  │   PostbackQueue → RetryLog                              │
  ├─────────────────────────────────────────────────────────┤
  │  ANALYTICS                                              │
  │   NetworkPerformance → HourlyStat                       │
  └─────────────────────────────────────────────────────────┘

Design Principles:
  • All primary keys are UUIDs (no guessable sequential IDs in URLs).
  • Raw payload fields are write-once (append-only audit trail).
  • Mutable fields (status, fraud flags) use dedicated save() helpers.
  • All models carry a `tenant` FK for multi-tenancy support.
  • Heavy query fields carry explicit db_index=True.
  • Large tables use composite indexes for analytics queries.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .enums import (
    AttributionModel,
    BlacklistReason,
    BlacklistType,
    ClickStatus,
    ConversionStatus,
    DeduplicationWindow,
    DeviceType,
    FraudType,
    ImpressionStatus,
    NetworkStatus,
    NetworkType,
    PostbackStatus,
    QueuePriority,
    QueueStatus,
    RejectionReason,
    SignatureAlgorithm,
)
from .constants import (
    MAX_PAYOUT_PER_POSTBACK,
    CLICK_ID_LENGTH,
    FRAUD_SCORE_THRESHOLD_FLAG,
    FRAUD_SCORE_THRESHOLD_BLOCK,
)


# ══════════════════════════════════════════════════════════════════════════════
# Base / Abstract Models
# ══════════════════════════════════════════════════════════════════════════════

class TenantModel(models.Model):
    """Abstract base providing tenant isolation + timestamps."""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_set',
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ImmutableRecord(TenantModel):
    """Abstract base for append-only audit records."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


# ══════════════════════════════════════════════════════════════════════════════
# 1. NETWORK MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

class AdNetworkConfig(TenantModel):
    """
    Per-network configuration.
    One row per integration partner (CPALead, AdGate, AppLovin, etc.).

    Stores:
      - Authentication credentials (secret key, API key)
      - Postback URL format & signature algorithm
      - Field mapping (network-specific param names → standard names)
      - Reward rules per offer
      - Rate limits and deduplication settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("network name"), max_length=200)
    network_key = models.CharField(
        _("network key"),
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_("URL-safe slug: /api/postback_engine/{network_key}/"),
    )
    network_type = models.CharField(
        _("type"), max_length=20, choices=NetworkType.choices, default=NetworkType.CPA,
    )
    status = models.CharField(
        _("status"), max_length=20, choices=NetworkStatus.choices,
        default=NetworkStatus.TESTING, db_index=True,
    )
    logo_url = models.URLField(_("logo URL"), blank=True)

    # ── Credentials ──────────────────────────────────────────────────────────
    secret_key = models.CharField(
        _("secret key"), max_length=512,
        help_text=_("HMAC secret. Encrypt at rest with django-fernet-fields."),
    )
    api_key = models.CharField(_("API key"), max_length=512, blank=True)
    signature_algorithm = models.CharField(
        _("signature algorithm"), max_length=20,
        choices=SignatureAlgorithm.choices, default=SignatureAlgorithm.HMAC_SHA256,
    )
    require_nonce = models.BooleanField(_("require nonce"), default=True)

    # ── IP Security ───────────────────────────────────────────────────────────
    ip_whitelist = models.JSONField(
        _("IP whitelist"), default=list, blank=True,
        help_text=_("List of allowed IPs / CIDR ranges. Empty = allow all."),
    )
    trust_x_forwarded_for = models.BooleanField(
        _("trust X-Forwarded-For"), default=False,
        help_text=_("Enable only behind a trusted reverse proxy."),
    )

    # ── Field Mapping ─────────────────────────────────────────────────────────
    field_mapping = models.JSONField(
        _("field mapping"), default=dict, blank=True,
        help_text=_(
            'Map standard names → network param names. '
            'e.g. {"lead_id": "click_id", "offer_id": "campaign_id"}'
        ),
    )
    required_fields = models.JSONField(
        _("required fields"), default=list, blank=True,
        help_text=_("Fields that MUST be present in every postback payload."),
    )

    # ── Postback URL Template ─────────────────────────────────────────────────
    postback_url_template = models.TextField(
        _("postback URL template"), blank=True,
        help_text=_("Outbound S2S postback URL. Use {macro} placeholders."),
    )

    # ── Reward Configuration ──────────────────────────────────────────────────
    reward_rules = models.JSONField(
        _("reward rules"), default=dict, blank=True,
        help_text=_(
            'Per-offer reward config. '
            'e.g. {"offer_123": {"points": 500, "usd": 0.5}}'
        ),
    )
    default_reward_points = models.PositiveIntegerField(
        _("default reward points"), default=0,
    )
    default_reward_usd = models.DecimalField(
        _("default reward USD"), max_digits=10, decimal_places=4, default=Decimal("0"),
    )

    # ── Deduplication ─────────────────────────────────────────────────────────
    dedup_window = models.CharField(
        _("dedup window"), max_length=10,
        choices=DeduplicationWindow.choices, default=DeduplicationWindow.FOREVER,
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute = models.PositiveIntegerField(
        _("rate limit / minute"), default=1000,
    )

    # ── Attribution ───────────────────────────────────────────────────────────
    attribution_model = models.CharField(
        _("attribution model"), max_length=20,
        choices=AttributionModel.choices, default=AttributionModel.LAST_CLICK,
    )
    conversion_window_hours = models.PositiveIntegerField(
        _("conversion window (hours)"), default=720,  # 30 days
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    contact_email = models.EmailField(_("contact email"), blank=True)
    notes = models.TextField(_("internal notes"), blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)
    is_test_mode = models.BooleanField(
        _("test mode"), default=False,
        help_text=_("If True, postbacks are logged but no rewards are issued."),
    )

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("ad network config")
        verbose_name_plural = _("ad network configs")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["network_key", "status"], name='idx_network_key_status_1368'),
        ]

    def __str__(self):
        return f"{self.name} ({self.network_key}) [{self.get_status_display()}]"

    def get_mapped_field(self, standard_name: str, payload: dict):
        """Resolve a field value from payload using this network's field mapping."""
        mapped = self.field_mapping.get(standard_name, standard_name)
        return payload.get(mapped)

    def get_reward_for_offer(self, offer_id: str) -> dict:
        """Return reward config for a specific offer, falling back to default."""
        rule = self.reward_rules.get(str(offer_id))
        if rule:
            return rule
        return {
            "points": self.default_reward_points,
            "usd": float(self.default_reward_usd),
        }

    @property
    def is_active(self) -> bool:
        return self.status == NetworkStatus.ACTIVE


class NetworkAdapterMapping(TenantModel):
    """
    Detailed per-parameter mapping for a network.

    While AdNetworkConfig.field_mapping stores a simple dict,
    this model allows per-field metadata: type coercion, default value,
    validation regex, and whether the field is required.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.CASCADE,
        related_name="adapter_mappings", verbose_name=_("network"),
    )

    # Standard field name (our internal name)
    standard_name = models.CharField(_("standard name"), max_length=100)
    # Network-specific param name in the postback request
    network_param = models.CharField(_("network param"), max_length=200)

    data_type = models.CharField(
        _("data type"), max_length=20,
        choices=[
            ("string", "String"),
            ("integer", "Integer"),
            ("decimal", "Decimal"),
            ("boolean", "Boolean"),
            ("timestamp", "Unix Timestamp"),
            ("iso_datetime", "ISO DateTime"),
        ],
        default="string",
    )
    is_required = models.BooleanField(_("required"), default=False)
    default_value = models.CharField(_("default value"), max_length=255, blank=True)
    validation_regex = models.CharField(_("validation regex"), max_length=500, blank=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("network adapter mapping")
        verbose_name_plural = _("network adapter mappings")
        unique_together = [("network", "standard_name")]
        ordering = ["network", "standard_name"]

    def __str__(self):
        return f"{self.network.network_key}: {self.network_param} → {self.standard_name}"


class OfferPostback(TenantModel):
    """
    Per-offer custom postback settings.
    Overrides the AdNetworkConfig defaults for a specific offer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.CASCADE,
        related_name="offer_postbacks", verbose_name=_("network"),
    )
    offer_id = models.CharField(_("offer ID"), max_length=255, db_index=True)
    offer_name = models.CharField(_("offer name"), max_length=500, blank=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)

    # Reward override
    reward_points = models.PositiveIntegerField(_("reward points"), default=0)
    reward_usd = models.DecimalField(
        _("reward USD"), max_digits=10, decimal_places=4, default=Decimal("0"),
    )
    max_conversions_per_user = models.PositiveIntegerField(
        _("max conversions / user"), default=1,
        help_text=_("0 = unlimited"),
    )
    max_total_conversions = models.PositiveIntegerField(
        _("max total conversions"), default=0,
        help_text=_("0 = unlimited"),
    )

    # Conversion window override (None = use network default)
    conversion_window_hours = models.PositiveIntegerField(
        _("conversion window (hours)"), null=True, blank=True,
    )

    # Custom outbound postback URL for this offer
    custom_postback_url = models.TextField(_("custom postback URL"), blank=True)

    # Geo restrictions (empty = all allowed)
    allowed_countries = models.JSONField(_("allowed countries"), default=list, blank=True)
    blocked_countries = models.JSONField(_("blocked countries"), default=list, blank=True)

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("offer postback config")
        verbose_name_plural = _("offer postback configs")
        unique_together = [("network", "offer_id")]
        indexes = [
            models.Index(fields=["network", "offer_id", "is_active"], name='idx_network_offer_id_is_ac_265'),
        ]

    def __str__(self):
        return f"{self.network.network_key} / {self.offer_id}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. TRACKING CORE
# ══════════════════════════════════════════════════════════════════════════════

class ClickLog(ImmutableRecord):
    """
    Records every user click on an offer link.

    Generated when a user clicks an offer link. The click_id is embedded
    as a macro ({click_id}) in the offer URL so the CPA network returns
    it in the postback, allowing us to link the conversion back to the user.

    This is the FOUNDATION of the tracking system.
    Without a valid ClickLog, no conversion can be credited.
    """
    # Click identity
    click_id = models.CharField(
        _("click ID"), max_length=64, unique=True, db_index=True,
        help_text=_("Unique ID embedded in the offer URL as a macro."),
    )

    # Actor
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="click_logs",
        verbose_name=_("user"),
    )
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="click_logs",
        verbose_name=_("network"),
    )
    offer_id = models.CharField(_("offer ID"), max_length=255, blank=True, db_index=True)
    offer_name = models.CharField(_("offer name"), max_length=500, blank=True)
    campaign_id = models.CharField(_("campaign ID"), max_length=255, blank=True, db_index=True)

    # Status
    status = models.CharField(
        _("status"), max_length=20, choices=ClickStatus.choices,
        default=ClickStatus.VALID, db_index=True,
    )

    # Device & Network Context
    ip_address = models.GenericIPAddressField(
        _("IP address"), null=True, blank=True, db_index=True,
    )
    user_agent = models.TextField(_("user agent"), blank=True)
    device_type = models.CharField(
        _("device type"), max_length=20, choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
    )
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=255, blank=True, db_index=True)
    device_id = models.CharField(_("device ID"), max_length=255, blank=True, db_index=True)
    os = models.CharField(_("OS"), max_length=100, blank=True)
    os_version = models.CharField(_("OS version"), max_length=50, blank=True)
    browser = models.CharField(_("browser"), max_length=100, blank=True)
    browser_version = models.CharField(_("browser version"), max_length=50, blank=True)

    # Geo
    country = models.CharField(_("country"), max_length=2, blank=True, db_index=True)
    region = models.CharField(_("region"), max_length=100, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    isp = models.CharField(_("ISP"), max_length=200, blank=True)

    # Tracking Params
    sub_id = models.CharField(_("sub ID"), max_length=255, blank=True, db_index=True)
    sub_id2 = models.CharField(_("sub ID 2"), max_length=255, blank=True)
    sub_id3 = models.CharField(_("sub ID 3"), max_length=255, blank=True)
    utm_source = models.CharField(_("UTM source"), max_length=200, blank=True)
    utm_medium = models.CharField(_("UTM medium"), max_length=200, blank=True)
    utm_campaign = models.CharField(_("UTM campaign"), max_length=200, blank=True)
    referrer = models.TextField(_("referrer"), blank=True)

    # Timestamps
    clicked_at = models.DateTimeField(_("clicked at"), default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True, db_index=True)

    # Conversion link
    converted = models.BooleanField(_("converted"), default=False, db_index=True)
    converted_at = models.DateTimeField(_("converted at"), null=True, blank=True)

    # Fraud flags
    is_fraud = models.BooleanField(_("fraud"), default=False, db_index=True)
    fraud_score = models.FloatField(_("fraud score"), default=0.0)
    fraud_type = models.CharField(
        _("fraud type"), max_length=30, choices=FraudType.choices, blank=True,
    )

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("click log")
        verbose_name_plural = _("click logs")
        ordering = ["-clicked_at"]
        indexes = [
            models.Index(fields=["user", "offer_id", "clicked_at"], name='idx_user_offer_id_clicked__b46'),
            models.Index(fields=["network", "clicked_at"], name='idx_network_clicked_at_1371'),
            models.Index(fields=["ip_address", "clicked_at"], name='idx_ip_address_clicked_at_1372'),
            models.Index(fields=["device_fingerprint", "clicked_at"], name='idx_device_fingerprint_cli_bd2'),
            models.Index(fields=["country", "clicked_at"], name='idx_country_clicked_at_1374'),
            models.Index(fields=["status", "clicked_at"], name='idx_status_clicked_at_1375'),
            models.Index(fields=["converted", "expires_at"], name='idx_converted_expires_at_1376'),
        ]

    def __str__(self):
        return f"Click {self.click_id} | {self.user} | {self.offer_id}"

    def mark_converted(self):
        self.converted = True
        self.converted_at = timezone.now()
        self.save(update_fields=["converted", "converted_at", "updated_at"])

    def mark_fraud(self, fraud_type: str, score: float = 100.0):
        self.is_fraud = True
        self.fraud_type = fraud_type
        self.fraud_score = score
        self.status = ClickStatus.FRAUD
        self.save(update_fields=["is_fraud", "fraud_type", "fraud_score", "status", "updated_at"])

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at


class PostbackRawLog(ImmutableRecord):
    """
    Raw, unprocessed postback received from a CPA network.

    This is the first record created the instant we receive a request.
    It's an append-only audit record — the raw_payload is NEVER modified.
    Processing status is tracked via the `status` field only.

    Purpose: If anything goes wrong, we can re-process from this raw log.
    """
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.PROTECT,
        related_name="raw_logs", verbose_name=_("network"), db_index=True,
    )
    status = models.CharField(
        _("status"), max_length=20, choices=PostbackStatus.choices,
        default=PostbackStatus.RECEIVED, db_index=True,
    )

    # ── Raw Request Data (WRITE-ONCE) ─────────────────────────────────────────
    raw_payload = models.JSONField(
        _("raw payload"),
        help_text=_("Original request payload — never modified after creation."),
    )
    http_method = models.CharField(_("HTTP method"), max_length=10, default="GET")
    query_string = models.TextField(_("query string"), blank=True)
    request_headers = models.JSONField(
        _("request headers"), default=dict, blank=True,
        help_text=_("Sanitised headers (secrets stripped)."),
    )
    request_body = models.TextField(_("request body"), blank=True)
    content_type = models.CharField(_("content type"), max_length=200, blank=True)

    # ── Extracted Fields ──────────────────────────────────────────────────────
    lead_id = models.CharField(_("lead ID"), max_length=255, blank=True, db_index=True)
    click_id = models.CharField(_("click ID"), max_length=255, blank=True, db_index=True)
    offer_id = models.CharField(_("offer ID"), max_length=255, blank=True, db_index=True)
    transaction_id = models.CharField(_("transaction ID"), max_length=255, blank=True, db_index=True)
    payout = models.DecimalField(_("payout"), max_digits=12, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(_("currency"), max_length=10, blank=True)
    goal_id = models.CharField(_("goal ID"), max_length=255, blank=True)
    goal_value = models.DecimalField(
        _("goal value"), max_digits=12, decimal_places=4, null=True, blank=True,
    )

    # ── User Resolution ───────────────────────────────────────────────────────
    resolved_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="raw_postback_logs",
        verbose_name=_("resolved user"),
    )

    # ── Security ──────────────────────────────────────────────────────────────
    source_ip = models.GenericIPAddressField(
        _("source IP"), null=True, blank=True, db_index=True,
    )
    signature_verified = models.BooleanField(_("signature verified"), default=False)
    ip_whitelisted = models.BooleanField(_("IP whitelisted"), default=False)
    nonce = models.CharField(_("nonce"), max_length=128, blank=True)

    # ── Rejection ─────────────────────────────────────────────────────────────
    rejection_reason = models.CharField(
        _("rejection reason"), max_length=40,
        choices=RejectionReason.choices, blank=True,
    )
    rejection_detail = models.TextField(_("rejection detail"), blank=True)

    # ── Processing ────────────────────────────────────────────────────────────
    received_at = models.DateTimeField(_("received at"), default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(_("retry count"), default=0)
    next_retry_at = models.DateTimeField(_("next retry at"), null=True, blank=True, db_index=True)
    processing_error = models.TextField(_("processing error"), blank=True)

    # ── Reward ────────────────────────────────────────────────────────────────
    points_awarded = models.PositiveIntegerField(_("points awarded"), default=0)
    usd_awarded = models.DecimalField(
        _("USD awarded"), max_digits=10, decimal_places=4, default=Decimal("0"),
    )

    # Linked records (populated after processing)
    click_log = models.ForeignKey(
        ClickLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="raw_postback_logs",
        verbose_name=_("click log"),
    )

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("postback raw log")
        verbose_name_plural = _("postback raw logs")
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["network", "status", "received_at"], name='idx_network_status_receive_18b'),
            models.Index(fields=["lead_id", "network"], name='idx_lead_id_network_1378'),
            models.Index(fields=["click_id", "network"], name='idx_click_id_network_1379'),
            models.Index(fields=["status", "next_retry_at"], name='idx_status_next_retry_at_1380'),
            models.Index(fields=["source_ip", "received_at"], name='idx_source_ip_received_at_1381'),
            models.Index(fields=["transaction_id"], name='idx_transaction_id_1382'),
        ]

    def __str__(self):
        return (
            f"[{self.get_status_display()}] {self.network.network_key} "
            f"lead={self.lead_id or '—'} @ {self.received_at:%Y-%m-%d %H:%M:%S}"
        )

    # ── State Transition Helpers ──────────────────────────────────────────────

    def mark_processing(self):
        self.status = PostbackStatus.PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_validated(self):
        self.status = PostbackStatus.VALIDATED
        self.save(update_fields=["status", "updated_at"])

    def mark_rewarded(self, points: int = 0, usd: Decimal = Decimal("0")):
        self.status = PostbackStatus.REWARDED
        self.points_awarded = points
        self.usd_awarded = usd
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status", "points_awarded", "usd_awarded", "processed_at", "updated_at",
        ])

    def mark_rejected(self, reason: str, detail: str = ""):
        self.status = PostbackStatus.REJECTED
        self.rejection_reason = reason
        self.rejection_detail = detail
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status", "rejection_reason", "rejection_detail", "processed_at", "updated_at",
        ])

    def mark_duplicate(self):
        self.status = PostbackStatus.DUPLICATE
        self.rejection_reason = RejectionReason.DUPLICATE_LEAD
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status", "rejection_reason", "processed_at", "updated_at",
        ])

    def mark_failed(self, error: str, next_retry_at=None):
        self.status = PostbackStatus.FAILED
        self.processing_error = error
        self.retry_count += 1
        self.next_retry_at = next_retry_at
        self.save(update_fields=[
            "status", "processing_error", "retry_count", "next_retry_at", "updated_at",
        ])


class Conversion(ImmutableRecord):
    """
    Final, approved conversion record.

    Created AFTER a PostbackRawLog passes all validation gates.
    This is the authoritative record that triggers wallet credit.

    Lifecycle: PostbackRawLog → [validate] → Conversion → [reward] → wallet.credit()
    """
    # Identity
    raw_log = models.OneToOneField(
        PostbackRawLog, on_delete=models.PROTECT,
        related_name="conversion", verbose_name=_("raw postback log"),
    )
    click_log = models.ForeignKey(
        ClickLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="conversions",
        verbose_name=_("click log"),
    )
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.PROTECT,
        related_name="conversions", verbose_name=_("network"), db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="postback_engine_conversions", verbose_name=_("user"), db_index=True,
    )

    # Tracking IDs
    lead_id = models.CharField(_("lead ID"), max_length=255, db_index=True)
    click_id = models.CharField(_("click ID"), max_length=255, blank=True, db_index=True)
    offer_id = models.CharField(_("offer ID"), max_length=255, blank=True, db_index=True)
    transaction_id = models.CharField(
        _("transaction ID"), max_length=255, unique=True, db_index=True,
    )

    # Status
    status = models.CharField(
        _("status"), max_length=20, choices=ConversionStatus.choices,
        default=ConversionStatus.PENDING, db_index=True,
    )

    # Payout
    network_payout = models.DecimalField(
        _("network payout"), max_digits=12, decimal_places=4, default=Decimal("0"),
        help_text=_("What the network reports as the payout amount."),
    )
    actual_payout = models.DecimalField(
        _("actual payout"), max_digits=12, decimal_places=4, default=Decimal("0"),
        help_text=_("Actual payout after applying our reward rules."),
    )
    currency = models.CharField(_("currency"), max_length=10, default="USD")
    points_awarded = models.PositiveIntegerField(_("points awarded"), default=0)

    # Attribution
    attribution_model = models.CharField(
        _("attribution model"), max_length=20,
        choices=AttributionModel.choices, default=AttributionModel.LAST_CLICK,
    )
    time_to_convert_seconds = models.PositiveIntegerField(
        _("time to convert (seconds)"), null=True, blank=True,
    )

    # Context
    source_ip = models.GenericIPAddressField(
        _("source IP"), null=True, blank=True, db_index=True,
    )
    country = models.CharField(_("country"), max_length=2, blank=True, db_index=True)
    device_type = models.CharField(
        _("device type"), max_length=20, choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
    )

    # Reward tracking
    wallet_credited = models.BooleanField(_("wallet credited"), default=False, db_index=True)
    wallet_credited_at = models.DateTimeField(_("wallet credited at"), null=True, blank=True)
    wallet_transaction_id = models.UUIDField(
        _("wallet transaction ID"), null=True, blank=True,
    )

    # Reversal
    is_reversed = models.BooleanField(_("reversed"), default=False, db_index=True)
    reversed_at = models.DateTimeField(_("reversed at"), null=True, blank=True)
    reversal_reason = models.TextField(_("reversal reason"), blank=True)

    # Timestamps
    converted_at = models.DateTimeField(_("converted at"), default=timezone.now, db_index=True)
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("conversion")
        verbose_name_plural = _("conversions")
        ordering = ["-converted_at"]
        indexes = [
            models.Index(fields=["user", "status", "converted_at"], name='idx_user_status_converted__8ca'),
            models.Index(fields=["network", "status", "converted_at"], name='idx_network_status_convert_21d'),
            models.Index(fields=["offer_id", "status"], name='idx_offer_id_status_1385'),
            models.Index(fields=["country", "converted_at"], name='idx_country_converted_at_1386'),
            models.Index(fields=["wallet_credited", "converted_at"], name='idx_wallet_credited_conver_927'),
        ]

    def __str__(self):
        return (
            f"Conversion {self.transaction_id} | "
            f"{self.user} | {self.offer_id} | {self.actual_payout}"
        )

    def approve(self):
        self.status = ConversionStatus.APPROVED
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_at", "updated_at"])

    def reject(self, reason: str = ""):
        self.status = ConversionStatus.REJECTED
        self.save(update_fields=["status", "updated_at"])

    def reverse(self, reason: str = ""):
        self.is_reversed = True
        self.reversed_at = timezone.now()
        self.reversal_reason = reason
        self.status = ConversionStatus.REVERSED
        self.save(update_fields=[
            "is_reversed", "reversed_at", "reversal_reason", "status", "updated_at",
        ])

    def mark_wallet_credited(self, wallet_transaction_id):
        self.wallet_credited = True
        self.wallet_credited_at = timezone.now()
        self.wallet_transaction_id = wallet_transaction_id
        self.status = ConversionStatus.PAID
        self.save(update_fields=[
            "wallet_credited", "wallet_credited_at",
            "wallet_transaction_id", "status", "updated_at",
        ])


class Impression(ImmutableRecord):
    """
    Records when an offer/ad was rendered/displayed to a user.

    Impressions are high-volume — typically much more than clicks.
    Used for: viewability analysis, CTR calculation, fraud detection.
    """
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="impressions",
        verbose_name=_("network"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="impressions",
        verbose_name=_("user"),
    )
    offer_id = models.CharField(_("offer ID"), max_length=255, blank=True, db_index=True)
    placement = models.CharField(_("placement"), max_length=200, blank=True)
    status = models.CharField(
        _("status"), max_length=20, choices=ImpressionStatus.choices,
        default=ImpressionStatus.RENDERED,
    )

    # Context
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True, db_index=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    device_type = models.CharField(
        _("device type"), max_length=20, choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
    )
    country = models.CharField(_("country"), max_length=2, blank=True, db_index=True)

    # Viewability
    is_viewable = models.BooleanField(_("viewable"), default=False)
    view_time_seconds = models.PositiveSmallIntegerField(
        _("view time (seconds)"), default=0,
    )

    impressed_at = models.DateTimeField(_("impressed at"), default=timezone.now, db_index=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("impression")
        verbose_name_plural = _("impressions")
        ordering = ["-impressed_at"]
        indexes = [
            models.Index(fields=["network", "impressed_at"], name='idx_network_impressed_at_1388'),
            models.Index(fields=["user", "offer_id"], name='idx_user_offer_id_1389'),
            models.Index(fields=["ip_address", "impressed_at"], name='idx_ip_address_impressed_a_d3f'),
        ]

    def __str__(self):
        return f"Impression {self.id} | {self.offer_id} | {self.impressed_at:%Y-%m-%d %H:%M}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. FRAUD & SECURITY
# ══════════════════════════════════════════════════════════════════════════════

class FraudAttemptLog(ImmutableRecord):
    """
    Records every detected or suspected fraud attempt.

    Never deleted — required for compliance and pattern analysis.
    """
    raw_log = models.ForeignKey(
        PostbackRawLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fraud_attempts",
        verbose_name=_("raw postback log"),
    )
    click_log = models.ForeignKey(
        ClickLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fraud_attempts",
        verbose_name=_("click log"),
    )
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fraud_attempts",
        verbose_name=_("network"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="postback_fraud_attempts",
        verbose_name=_("user"),
    )

    fraud_type = models.CharField(
        _("fraud type"), max_length=30, choices=FraudType.choices,
        default=FraudType.OTHER, db_index=True,
    )
    fraud_score = models.FloatField(_("fraud score"), default=0.0, db_index=True)
    is_auto_blocked = models.BooleanField(_("auto-blocked"), default=False, db_index=True)
    is_reviewed = models.BooleanField(_("reviewed"), default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_fraud_attempts",
        verbose_name=_("reviewed by"),
    )
    review_action = models.CharField(
        _("review action"), max_length=20,
        choices=[
            ("confirmed", "Confirmed Fraud"),
            ("dismissed", "Dismissed (False Positive)"),
            ("escalated", "Escalated"),
        ],
        blank=True,
    )

    # Evidence
    source_ip = models.GenericIPAddressField(
        _("source IP"), null=True, blank=True, db_index=True,
    )
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=255, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    country = models.CharField(_("country"), max_length=2, blank=True)
    details = models.JSONField(_("details"), default=dict, blank=True)
    signals = models.JSONField(_("fraud signals"), default=list, blank=True)

    detected_at = models.DateTimeField(_("detected at"), default=timezone.now, db_index=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("fraud attempt log")
        verbose_name_plural = _("fraud attempt logs")
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["fraud_type", "detected_at"], name='idx_fraud_type_detected_at_81e'),
            models.Index(fields=["source_ip", "detected_at"], name='idx_source_ip_detected_at_1392'),
            models.Index(fields=["user", "detected_at"], name='idx_user_detected_at_1393'),
            models.Index(fields=["fraud_score", "is_auto_blocked"], name='idx_fraud_score_is_auto_bl_d87'),
        ]

    def __str__(self):
        return f"Fraud [{self.fraud_type}] score={self.fraud_score} @ {self.detected_at:%Y-%m-%d %H:%M}"


class IPBlacklist(TenantModel):
    """
    Blacklisted IPs, CIDR ranges, device IDs, user agents.

    Checked on every incoming request for fast rejection.
    Redis-cached for performance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blacklist_type = models.CharField(
        _("type"), max_length=20, choices=BlacklistType.choices,
        default=BlacklistType.IP, db_index=True,
    )
    value = models.CharField(
        _("value"), max_length=500, db_index=True,
        help_text=_("IP, CIDR, device_id, user_agent string, or fingerprint hash."),
    )
    reason = models.CharField(
        _("reason"), max_length=20, choices=BlacklistReason.choices,
        default=BlacklistReason.FRAUD,
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)

    # Origin
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="added_blacklists",
        verbose_name=_("added by"),
    )
    added_by_system = models.BooleanField(
        _("auto-added by system"), default=False,
        help_text=_("True = auto-blocked by fraud detection."),
    )
    fraud_attempt = models.ForeignKey(
        FraudAttemptLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="blacklist_entries",
        verbose_name=_("fraud attempt"),
    )

    notes = models.TextField(_("notes"), blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True, db_index=True)
    hit_count = models.PositiveIntegerField(_("hit count"), default=0)
    last_hit_at = models.DateTimeField(_("last hit at"), null=True, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("IP blacklist")
        verbose_name_plural = _("IP blacklist")
        unique_together = [("blacklist_type", "value", "tenant")]
        indexes = [
            models.Index(fields=["blacklist_type", "is_active"], name='idx_blacklist_type_is_acti_621'),
            models.Index(fields=["value", "blacklist_type"], name='idx_value_blacklist_type_1396'),
        ]

    def __str__(self):
        return f"[{self.get_blacklist_type_display()}] {self.value}"

    def increment_hit(self):
        self.hit_count += 1
        self.last_hit_at = timezone.now()
        self.save(update_fields=["hit_count", "last_hit_at"])

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at


class ConversionDeduplication(models.Model):
    """
    Fast-lookup deduplication table.

    Written once per validated lead/transaction.
    Separate from PostbackRawLog to avoid scanning the large log table
    on every incoming postback.

    Query pattern: CHECK EXISTS WHERE (network_id, lead_id)
    This is the hot path — must be as fast as possible.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True, related_name="dedup_records", db_index=True,)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.CASCADE,
        related_name="dedup_records", verbose_name=_("network"),
    )
    lead_id = models.CharField(_("lead ID"), max_length=255, db_index=True)
    transaction_id = models.CharField(_("transaction ID"), max_length=255, blank=True, db_index=True)
    first_seen_at = models.DateTimeField(_("first seen at"), default=timezone.now)
    raw_log = models.OneToOneField(
        PostbackRawLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="dedup_record",
        verbose_name=_("original postback log"),
    )
    conversion = models.OneToOneField(
        Conversion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="dedup_record",
        verbose_name=_("conversion"),
    )

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("conversion deduplication")
        verbose_name_plural = _("conversion deduplications")
        unique_together = [("network", "lead_id")]
        indexes = [
            models.Index(fields=["network", "lead_id"], name='idx_network_lead_id_1397'),
            models.Index(fields=["transaction_id"], name='idx_transaction_id_1398'),
        ]

    def __str__(self):
        return f"Dedup: {self.network.network_key}/{self.lead_id}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. QUEUE & RELIABILITY
# ══════════════════════════════════════════════════════════════════════════════

class PostbackQueue(TenantModel):
    """
    Database-backed queue for postback processing.

    Used when the worker is busy, during peak load, or when
    async processing is required (Celery/Redis fallback).

    Priority: 1=Critical > 2=High > 3=Normal > 4=Low > 5=Background
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_log = models.OneToOneField(
        PostbackRawLog, on_delete=models.CASCADE,
        related_name="queue_entry", verbose_name=_("raw postback log"),
    )
    priority = models.PositiveSmallIntegerField(
        _("priority"), choices=QueuePriority.choices,
        default=QueuePriority.NORMAL, db_index=True,
    )
    status = models.CharField(
        _("status"), max_length=20, choices=QueueStatus.choices,
        default=QueueStatus.PENDING, db_index=True,
    )

    # Worker assignment
    worker_id = models.CharField(_("worker ID"), max_length=100, blank=True)
    locked_at = models.DateTimeField(_("locked at"), null=True, blank=True)
    lock_expires_at = models.DateTimeField(_("lock expires at"), null=True, blank=True)

    # Scheduling
    process_after = models.DateTimeField(
        _("process after"), default=timezone.now, db_index=True,
        help_text=_("Don't process before this time (for delayed/scheduled jobs)."),
    )
    enqueued_at = models.DateTimeField(_("enqueued at"), default=timezone.now, db_index=True)
    processing_started_at = models.DateTimeField(_("processing started"), null=True, blank=True)
    processing_finished_at = models.DateTimeField(_("processing finished"), null=True, blank=True)

    error_message = models.TextField(_("error message"), blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("postback queue")
        verbose_name_plural = _("postback queue")
        ordering = ["priority", "enqueued_at"]
        indexes = [
            models.Index(fields=["status", "priority", "process_after"], name='idx_status_priority_proces_46c'),
            models.Index(fields=["status", "enqueued_at"], name='idx_status_enqueued_at_1400'),
        ]

    def __str__(self):
        return (
            f"Queue[{self.get_priority_display()}] "
            f"{self.raw_log.network.network_key} [{self.get_status_display()}]"
        )


class RetryLog(TenantModel):
    """
    Tracks retry attempts for failed postbacks, webhooks, and conversions.

    Keeps a full history of every retry — when, why, and the result.
    """
    RETRY_TYPES = [
        ("postback", "Postback Processing"),
        ("webhook", "Webhook Delivery"),
        ("conversion", "Conversion Processing"),
        ("reward", "Reward Dispatch"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    retry_type = models.CharField(_("retry type"), max_length=20, choices=RETRY_TYPES, db_index=True)
    object_id = models.UUIDField(_("object ID"), db_index=True)

    attempt_number = models.PositiveSmallIntegerField(_("attempt #"), default=1)
    attempted_at = models.DateTimeField(_("attempted at"), default=timezone.now, db_index=True)
    succeeded = models.BooleanField(_("succeeded"), default=False)
    error_message = models.TextField(_("error message"), blank=True)
    error_traceback = models.TextField(_("error traceback"), blank=True)
    response_data = models.JSONField(_("response data"), default=dict, blank=True)
    next_retry_at = models.DateTimeField(_("next retry at"), null=True, blank=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("retry log")
        verbose_name_plural = _("retry logs")
        ordering = ["-attempted_at"]
        indexes = [
            models.Index(fields=["retry_type", "object_id"], name='idx_retry_type_object_id_1401'),
            models.Index(fields=["succeeded", "attempted_at"], name='idx_succeeded_attempted_at_bb4'),
        ]

    def __str__(self):
        return (
            f"Retry #{self.attempt_number} [{self.retry_type}] "
            f"{self.object_id} {'✓' if self.succeeded else '✗'}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. ANALYTICS & REPORTING
# ══════════════════════════════════════════════════════════════════════════════

class NetworkPerformance(TenantModel):
    """
    Aggregated daily performance metrics per network.

    Pre-aggregated by a scheduled task (not computed on-the-fly)
    to keep dashboard queries fast.

    Metrics: clicks, conversions, conversion_rate, revenue, fraud_rate
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.CASCADE,
        related_name="performance_records", verbose_name=_("network"), db_index=True,
    )
    date = models.DateField(_("date"), db_index=True)

    # Volume
    total_clicks = models.PositiveIntegerField(_("total clicks"), default=0)
    unique_clicks = models.PositiveIntegerField(_("unique clicks"), default=0)
    total_impressions = models.PositiveIntegerField(_("total impressions"), default=0)
    total_conversions = models.PositiveIntegerField(_("total conversions"), default=0)
    approved_conversions = models.PositiveIntegerField(_("approved conversions"), default=0)
    rejected_conversions = models.PositiveIntegerField(_("rejected conversions"), default=0)
    duplicate_conversions = models.PositiveIntegerField(_("duplicate conversions"), default=0)

    # Revenue
    total_payout_usd = models.DecimalField(
        _("total payout USD"), max_digits=14, decimal_places=4, default=Decimal("0"),
    )
    total_points_awarded = models.PositiveIntegerField(_("total points"), default=0)

    # Fraud
    fraud_clicks = models.PositiveIntegerField(_("fraud clicks"), default=0)
    fraud_conversions = models.PositiveIntegerField(_("fraud conversions"), default=0)

    # Derived (stored for fast reads)
    conversion_rate = models.FloatField(_("conversion rate %"), default=0.0)
    fraud_rate = models.FloatField(_("fraud rate %"), default=0.0)
    avg_payout_usd = models.DecimalField(
        _("avg payout USD"), max_digits=10, decimal_places=4, default=Decimal("0"),
    )

    computed_at = models.DateTimeField(_("computed at"), default=timezone.now)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("network performance")
        verbose_name_plural = _("network performance")
        unique_together = [("network", "date")]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date", "network"], name='idx_date_network_1403'),
        ]

    def __str__(self):
        return f"{self.network.network_key} | {self.date} | CR={self.conversion_rate:.2f}%"

    def recalculate_rates(self):
        """Update derived rate fields from raw counts."""
        if self.total_clicks > 0:
            self.conversion_rate = (self.approved_conversions / self.total_clicks) * 100
            self.fraud_rate = (self.fraud_clicks / self.total_clicks) * 100
        if self.approved_conversions > 0:
            self.avg_payout_usd = self.total_payout_usd / self.approved_conversions
        self.computed_at = timezone.now()
        self.save(update_fields=[
            "conversion_rate", "fraud_rate", "avg_payout_usd", "computed_at", "updated_at",
        ])


class HourlyStat(TenantModel):
    """
    Per-hour aggregated statistics for real-time monitoring.

    Updated by a Celery beat task every 5 minutes.
    Used for: real-time dashboards, anomaly detection, alerts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        AdNetworkConfig, on_delete=models.CASCADE,
        related_name="hourly_stats", verbose_name=_("network"), db_index=True,
    )
    date = models.DateField(_("date"), db_index=True)
    hour = models.PositiveSmallIntegerField(
        _("hour"), help_text=_("0–23 in UTC."), db_index=True,
    )

    # Counters
    clicks = models.PositiveIntegerField(_("clicks"), default=0)
    conversions = models.PositiveIntegerField(_("conversions"), default=0)
    impressions = models.PositiveIntegerField(_("impressions"), default=0)
    rejected = models.PositiveIntegerField(_("rejected"), default=0)
    fraud = models.PositiveIntegerField(_("fraud"), default=0)

    # Revenue
    payout_usd = models.DecimalField(
        _("payout USD"), max_digits=12, decimal_places=4, default=Decimal("0"),
    )
    points_awarded = models.PositiveIntegerField(_("points awarded"), default=0)

    # Rates
    conversion_rate = models.FloatField(_("CR %"), default=0.0)
    fraud_rate = models.FloatField(_("fraud rate %"), default=0.0)

    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        app_label = "postback_engine"
        verbose_name = _("hourly stat")
        verbose_name_plural = _("hourly stats")
        unique_together = [("network", "date", "hour")]
        ordering = ["-date", "-hour"]
        indexes = [
            models.Index(fields=["date", "hour", "network"], name='idx_date_hour_network_1404'),
        ]

    def __str__(self):
        return f"{self.network.network_key} | {self.date} {self.hour:02d}:00 | {self.conversions} conv"
