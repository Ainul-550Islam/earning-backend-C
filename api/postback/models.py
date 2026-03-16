"""
models.py – Postback / Security & Tracking module.

Design:
  • NetworkPostbackConfig holds per-network signing secrets, IP whitelist,
    field mappings, and reward rules. Secrets are stored as Django fields
    but should be encrypted at rest (use django-fernet-fields in production).
  • PostbackLog is an append-only audit record – never updated, never deleted
    within the retention window.  status is updated via a separate column so
    the raw_payload is preserved.
  • DuplicateLeadCheck is a fast lookup table for dedup; indexed on (network, lead_id).
  • LeadValidator holds per-network custom validation rules that can be chained
    at processing time.
"""
import uuid
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    DeduplicationWindow,
    NetworkType,
    PostbackStatus,
    RejectionReason,
    SignatureAlgorithm,
    ValidatorStatus,
)
from .constants import MAX_PAYOUT_PER_POSTBACK
from .managers import (
    DuplicateLeadCheckManager,
    NetworkPostbackConfigManager,
    PostbackLogManager,
)
from .validators import (
    validate_field_mapping,
    validate_ip_whitelist,
    validate_network_key_format,
    validate_reward_rules,
)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ── NetworkPostbackConfig ─────────────────────────────────────────────────────

class NetworkPostbackConfig(TimeStampedModel):
    """
    Per-network postback configuration.
    One row per integration partner (affiliate network, CPA network, etc.).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("network name"), max_length=200)
    network_key = models.CharField(
        _("network key"),
        max_length=64,
        unique=True,
        db_index=True,
        validators=[validate_network_key_format],
        help_text=_("Unique slug used in the postback URL: /api/postback/{network_key}/"),
    )
    network_type = models.CharField(
        _("network type"),
        max_length=20,
        choices=NetworkType.choices,
        default=NetworkType.CPA,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ValidatorStatus.choices,
        default=ValidatorStatus.TESTING,
        db_index=True,
    )

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key = models.CharField(
        _("secret key"),
        max_length=512,
        help_text=_("Shared HMAC secret. Store encrypted at rest."),
    )
    signature_algorithm = models.CharField(
        _("signature algorithm"),
        max_length=20,
        choices=SignatureAlgorithm.choices,
        default=SignatureAlgorithm.HMAC_SHA256,
    )
    ip_whitelist = models.JSONField(
        _("IP whitelist"),
        default=list,
        blank=True,
        validators=[validate_ip_whitelist],
        help_text=_("List of allowed IP addresses / CIDR ranges. Empty = allow all."),
    )
    trust_forwarded_for = models.BooleanField(
        _("trust X-Forwarded-For"),
        default=False,
        help_text=_("Only enable if behind a trusted reverse proxy."),
    )
    require_nonce = models.BooleanField(
        _("require nonce"),
        default=True,
        help_text=_("Require X-Postback-Nonce header to prevent replay attacks."),
    )

    # ── Field Mapping ─────────────────────────────────────────────────────────
    field_mapping = models.JSONField(
        _("field mapping"),
        default=dict,
        blank=True,
        validators=[validate_field_mapping],
        help_text=_(
            "Map standard field names to network-specific param names. "
            'e.g. {"lead_id": "click_id", "offer_id": "campaign_id"}'
        ),
    )
    required_fields = models.JSONField(
        _("required fields"),
        default=list,
        blank=True,
        help_text=_("List of field names that MUST be present in the postback payload."),
    )

    # ── Deduplication ─────────────────────────────────────────────────────────
    dedup_window = models.CharField(
        _("deduplication window"),
        max_length=10,
        choices=DeduplicationWindow.choices,
        default=DeduplicationWindow.FOREVER,
    )

    # ── Reward Rules ──────────────────────────────────────────────────────────
    reward_rules = models.JSONField(
        _("reward rules"),
        default=dict,
        blank=True,
        validators=[validate_reward_rules],
        help_text=_(
            "Per-offer reward configuration. "
            'e.g. {"offer_123": {"points": 500, "item_id": "<uuid>"}}'
        ),
    )
    default_reward_points = models.PositiveIntegerField(
        _("default reward points"),
        default=0,
        help_text=_("Points awarded when no specific offer rule matches."),
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute = models.PositiveIntegerField(
        _("rate limit (per minute)"),
        default=1000,
    )

    # ── Contact ───────────────────────────────────────────────────────────────
    contact_email = models.EmailField(_("contact email"), blank=True)
    notes = models.TextField(_("internal notes"), blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    objects = NetworkPostbackConfigManager()

    class Meta:
        verbose_name = _("network postback config")
        verbose_name_plural = _("network postback configs")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["network_key", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.network_key}) [{self.get_status_display()}]"

    def get_field(self, standard_name: str, payload: dict):
        """Resolve a field value from payload using the network's field mapping."""
        mapped_name = self.field_mapping.get(standard_name, standard_name)
        return payload.get(mapped_name)

    def get_reward_for_offer(self, offer_id: str) -> dict:
        """Return reward config for an offer, falling back to default."""
        rule = self.reward_rules.get(str(offer_id))
        if rule:
            return rule
        return {"points": self.default_reward_points}


# ── PostbackLog ───────────────────────────────────────────────────────────────

class PostbackLog(TimeStampedModel):
    """
    Immutable audit record of every received postback.
    status and rejection columns are mutable; raw_payload is write-once.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.PROTECT,
        related_name="postback_logs",
        verbose_name=_("network"),
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PostbackStatus.choices,
        default=PostbackStatus.RECEIVED,
        db_index=True,
    )

    # ── Payload ───────────────────────────────────────────────────────────────
    raw_payload = models.JSONField(
        _("raw payload"),
        help_text=_("Original request payload as received – never modified."),
    )
    method = models.CharField(_("HTTP method"), max_length=10, default="GET")
    query_string = models.TextField(_("query string"), blank=True)
    request_headers = models.JSONField(
        _("request headers"),
        default=dict,
        blank=True,
        help_text=_("Sanitised headers – secrets stripped before storage."),
    )

    # ── Extracted Fields ──────────────────────────────────────────────────────
    lead_id = models.CharField(
        _("lead ID"),
        max_length=255,
        blank=True,
        db_index=True,
    )
    offer_id = models.CharField(
        _("offer ID"),
        max_length=255,
        blank=True,
        db_index=True,
    )
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=255,
        blank=True,
        db_index=True,
    )
    payout = models.DecimalField(
        _("payout"),
        max_digits=12,
        decimal_places=4,
        default=0,
    )
    currency = models.CharField(_("currency"), max_length=10, blank=True)

    # ── User Resolution ───────────────────────────────────────────────────────
    resolved_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="postback_logs",
        verbose_name=_("resolved user"),
    )

    # ── Security Context ──────────────────────────────────────────────────────
    source_ip = models.GenericIPAddressField(
        _("source IP"),
        null=True,
        blank=True,
        db_index=True,
    )
    signature_verified = models.BooleanField(_("signature verified"), default=False)
    ip_whitelisted = models.BooleanField(_("IP whitelisted"), default=False)

    # ── Rejection ─────────────────────────────────────────────────────────────
    rejection_reason = models.CharField(
        _("rejection reason"),
        max_length=40,
        choices=RejectionReason.choices,
        blank=True,
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
    inventory_id = models.UUIDField(
        _("inventory ID"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("UserInventory UUID if an item was awarded."),
    )

    objects = PostbackLogManager()

    class Meta:
        verbose_name = _("postback log")
        verbose_name_plural = _("postback logs")
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["network", "status", "received_at"]),
            models.Index(fields=["lead_id", "network"]),
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["source_ip", "received_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"[{self.get_status_display()}] {self.network.network_key} "
            f"lead={self.lead_id or '—'} @ {self.received_at:%Y-%m-%d %H:%M:%S}"
        )

    def mark_validated(self) -> None:
        self.status = PostbackStatus.VALIDATED
        self.save(update_fields=["status", "updated_at"])

    def mark_rewarded(self, points: int = 0, inventory_id=None) -> None:
        self.status = PostbackStatus.REWARDED
        self.points_awarded = points
        self.processed_at = timezone.now()
        if inventory_id:
            self.inventory_id = inventory_id
        self.save(update_fields=[
            "status", "points_awarded", "processed_at", "inventory_id", "updated_at"
        ])

    def mark_rejected(self, reason: str, detail: str = "") -> None:
        self.status = PostbackStatus.REJECTED
        self.rejection_reason = reason
        self.rejection_detail = detail
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status", "rejection_reason", "rejection_detail", "processed_at", "updated_at"
        ])

    def mark_duplicate(self) -> None:
        self.status = PostbackStatus.DUPLICATE
        self.rejection_reason = RejectionReason.DUPLICATE_LEAD
        self.processed_at = timezone.now()
        self.save(update_fields=[
            "status", "rejection_reason", "processed_at", "updated_at"
        ])

    def mark_failed(self, error: str, next_retry_at=None) -> None:
        self.status = PostbackStatus.FAILED
        self.processing_error = error
        self.retry_count += 1
        self.next_retry_at = next_retry_at
        self.save(update_fields=[
            "status", "processing_error", "retry_count", "next_retry_at", "updated_at"
        ])


# ── DuplicateLeadCheck ────────────────────────────────────────────────────────

class DuplicateLeadCheck(models.Model):
    """
    Dedicated fast-lookup table for duplicate lead detection.
    Written once per validated lead. Never updated.

    Separate from PostbackLog to avoid scanning the large log table on
    every incoming postback.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="duplicate_checks",
        verbose_name=_("network"),
    )
    lead_id = models.CharField(_("lead ID"), max_length=255, db_index=True)
    first_seen_at = models.DateTimeField(_("first seen at"), default=timezone.now)
    postback_log = models.OneToOneField(
        PostbackLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicate_check",
        verbose_name=_("original postback log"),
    )

    objects = DuplicateLeadCheckManager()

    class Meta:
        verbose_name = _("duplicate lead check")
        verbose_name_plural = _("duplicate lead checks")
        unique_together = [("network", "lead_id")]
        indexes = [
            models.Index(fields=["network", "lead_id"]),
        ]

    def __str__(self) -> str:
        return f"DedupCheck: {self.network.network_key} / {self.lead_id}"


# ── LeadValidator ─────────────────────────────────────────────────────────────

class LeadValidator(TimeStampedModel):
    """
    A configurable validation rule attached to a NetworkPostbackConfig.
    Rules are evaluated in sort_order sequence at processing time.

    Example rules:
      type=field_present  → params={"field": "user_id"}
      type=field_regex    → params={"field": "lead_id", "pattern": "^[A-Z0-9]{10}$"}
      type=payout_range   → params={"min": 0.5, "max": 100.0}
      type=offer_whitelist → params={"allowed_offers": ["offer_1", "offer_2"]}
    """
    VALIDATOR_TYPES = [
        ("field_present", "Field Present"),
        ("field_regex", "Field Regex Match"),
        ("payout_range", "Payout Range"),
        ("offer_whitelist", "Offer Whitelist"),
        ("user_must_exist", "User Must Exist"),
        ("ip_reputation", "IP Reputation Check"),
        ("custom_expression", "Custom Expression"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="lead_validators",
        verbose_name=_("network"),
    )
    name = models.CharField(_("name"), max_length=200)
    validator_type = models.CharField(
        _("validator type"),
        max_length=30,
        choices=VALIDATOR_TYPES,
    )
    params = models.JSONField(
        _("params"),
        default=dict,
        blank=True,
        help_text=_("Type-specific parameters as a JSON object."),
    )
    is_blocking = models.BooleanField(
        _("is blocking"),
        default=True,
        help_text=_("If True, a failure rejects the postback. If False, only logs a warning."),
    )
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)
    failure_reason = models.CharField(
        _("failure rejection reason"),
        max_length=40,
        choices=RejectionReason.choices,
        default=RejectionReason.SCHEMA_VALIDATION,
    )

    class Meta:
        verbose_name = _("lead validator")
        verbose_name_plural = _("lead validators")
        ordering = ["network", "sort_order"]

    def __str__(self) -> str:
        return f"{self.network.network_key} – {self.name} [{self.validator_type}]"
