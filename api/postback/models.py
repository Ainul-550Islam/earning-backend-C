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
import hashlib
import json
import uuid
from decimal import Decimal
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

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
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

    # ── Sandbox / Test Mode ────────────────────────────────────────────────────────
    is_sandbox = models.BooleanField(
        _("sandbox mode"),
        default=False,
        db_index=True,
        help_text=_(
            "When True, incoming postbacks are accepted and logged but NO wallet credits "
            "or S2S callbacks are fired. Use for integration testing."
        ),
    )
    sandbox_payout_override = models.DecimalField(
        _("sandbox payout override (USD)"),
        max_digits=8,
        decimal_places=4,
        default=0,
        help_text=_("Override payout for all sandbox postbacks (0 = use real payout)."),
    )

    # ── S2S Outbound Callback (added migration 0006) ───────────────────────────
    callback_url = models.CharField(
        _("S2S callback URL"),
        max_length=2000,
        blank=True,
        help_text=_(
            "Outbound postback URL template fired after reward. "
            "Supports macros: {lead_id}, {payout}, {offer_id}, {goal_id}, "
            "{sub_id1}, {sub_id2}, {sub_id3}, {transaction_id}, {currency}."
        ),
    )
    callback_method = models.CharField(
        _("S2S callback method"),
        max_length=4,
        choices=[("GET", "GET"), ("POST", "POST")],
        default="GET",
    )
    callback_secret = models.CharField(
        _("S2S callback HMAC secret"),
        max_length=512,
        blank=True,
        help_text=_(
            "If set, appends an HMAC &sig= parameter to the outbound URL "
            "so the advertiser can verify authenticity."
        ),
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
            models.Index(fields=["network_key", "status"], name='idx_network_key_status_1362'),
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
    idfa = models.CharField(
        _("IDFA"),
        max_length=36,
        blank=True,
        db_index=True,
        help_text=_("iOS Identifier for Advertisers — required for OGAds/AdGate CPI offers."),
    )
    gaid = models.CharField(
        _("GAID"),
        max_length=36,
        blank=True,
        db_index=True,
        help_text=_("Google Advertising ID — required for Android CPI offer postbacks."),
    )
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

    # ── Integrity ───────────────────────────────────────────────────────────────
    integrity_hash = models.CharField(
        _("integrity hash"),
        max_length=64,
        db_index=True,
        help_text=_("SHA-256 hash of critical fields for tamper detection."),
    )

    # ── Click Linking (added migration 0007) ──────────────────────────────────
    click_id = models.CharField(
        _("click ID"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_(
            "Original click_id from the ad network click. "
            "Links this conversion back to the OfferClick record."
        ),
    )

    # ── Conversion Detail (added migration 0008) ───────────────────────────────
    event_type = models.CharField(
        _("event type"),
        max_length=20,
        choices=[
            ("install", "App Install (CPI)"),
            ("lead", "Lead / Form Fill (CPL)"),
            ("sale", "Sale / Purchase (CPA)"),
            ("registration", "User Registration"),
            ("trial", "Free Trial Start"),
            ("subscription", "Subscription"),
            ("deposit", "First Deposit"),
            ("survey", "Survey Complete"),
            ("video", "Video View"),
            ("click", "Click Event"),
            ("custom", "Custom Event"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        db_index=True,
        help_text=_("Conversion funnel stage: install, lead, sale, registration, etc."),
    )
    conversion_status = models.CharField(
        _("conversion status"),
        max_length=20,
        choices=[
            ("approved", "Approved"),
            ("pending", "Pending Review"),
            ("reversed", "Reversed / Chargeback"),
            ("rejected", "Rejected"),
            ("fraud", "Flagged as Fraud"),
        ],
        default="approved",
        db_index=True,
        help_text=_("Network-reported status: approved / pending / reversed."),
    )
    is_reversal = models.BooleanField(
        _("is reversal"),
        default=False,
        db_index=True,
        help_text=_("True if this postback is a chargeback/reversal of a prior conversion."),
    )
    reversed_log = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversal_logs",
        verbose_name=_("reversed postback log"),
        help_text=_("Points to the original PostbackLog that this reversal cancels."),
    )
    fire_delay_ms = models.PositiveIntegerField(
        _("fire delay (ms)"),
        default=0,
        help_text=_("Delay in milliseconds before firing the S2S callback. Max 300000 (5 min)."),
    )

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
            models.Index(fields=["network", "status", "received_at"], name='idx_network_status_receive_127'),
            models.Index(fields=["lead_id", "network"], name='idx_lead_id_network_1364'),
            models.Index(fields=["status", "next_retry_at"], name='idx_status_next_retry_at_1365'),
            models.Index(fields=["source_ip", "received_at"], name='idx_source_ip_received_at_1366'),
            # Performance indexes for high-volume queries
            models.Index(fields=["network", "received_at"], name='idx_network_received_at_1368'),
            models.Index(fields=["lead_id", "network", "received_at"], name='idx_lead_network_received_1369'),
            models.Index(fields=["status", "received_at"], name='idx_status_received_at_1370'),
            models.Index(fields=["integrity_hash"], name='idx_integrity_hash_1371'),
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

    def generate_integrity_hash(self) -> str:
        """
        Generate SHA-256 hash of critical fields for integrity verification.
        This hash ensures data tampering detection.
        """
        # Create canonical representation of critical fields
        canonical_data = {
            "network_id": str(self.network.pk),
            "lead_id": self.lead_id or "",
            "offer_id": self.offer_id or "",
            "transaction_id": self.transaction_id or "",
            "payout": str(self.payout),
            "currency": self.currency or "",
            "status": self.status,
            "received_at": self.received_at.isoformat() if self.received_at else "",
            "raw_payload": self.raw_payload,
        }
        
        # Sort keys for consistent hash generation
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the stored integrity_hash matches the current data."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.generate_integrity_hash()
        return self.integrity_hash == current_hash
    
    def save(self, *args, **kwargs):
        """Override save to automatically generate integrity hash."""
        # Generate integrity hash before saving
        self.integrity_hash = self.generate_integrity_hash()
        super().save(*args, **kwargs)


# ── DuplicateLeadCheck ────────────────────────────────────────────────────────

class DuplicateLeadCheck(models.Model):
    """
    Dedicated fast-lookup table for duplicate lead detection.
    Written once per validated lead. Never updated.

    Separate from PostbackLog to avoid scanning the large log table on
    every incoming postback.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

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
            models.Index(fields=["network", "lead_id"], name='idx_network_lead_id_1367'),
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

    def evaluate(self, payload: dict) -> tuple:
        """
        Run this validator against a postback payload dict.

        Returns:
            (passed: bool, reason: str)
        """
        vtype = self.validator_type
        params = self.params or {}

        try:
            if vtype == "field_present":
                field = params.get("field", "")
                val = payload.get(field)
                if not val:
                    return False, f"Required field '{field}' is missing or empty."
                return True, ""

            elif vtype == "field_regex":
                import re
                field = params.get("field", "")
                pattern = params.get("pattern", ".*")
                val = str(payload.get(field, ""))
                if not re.fullmatch(pattern, val):
                    return False, (
                        f"Field '{field}' value '{val}' does not match pattern '{pattern}'."
                    )
                return True, ""

            elif vtype == "payout_range":
                from decimal import Decimal, InvalidOperation
                try:
                    payout = Decimal(str(payload.get("payout", 0)))
                except InvalidOperation:
                    return False, "Payout is not a valid number."
                min_p = Decimal(str(params.get("min", "0")))
                max_p = Decimal(str(params.get("max", "99999")))
                if not (min_p <= payout <= max_p):
                    return False, (
                        f"Payout {payout} is outside allowed range [{min_p}, {max_p}]."
                    )
                return True, ""

            elif vtype == "offer_whitelist":
                allowed = params.get("allowed_offers", [])
                offer_id = str(payload.get("offer_id", ""))
                if allowed and offer_id not in allowed:
                    return False, f"Offer '{offer_id}' is not in the whitelist."
                return True, ""

            elif vtype == "user_must_exist":
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user_field = params.get("field", "user_id")
                user_id = payload.get(user_field)
                if not user_id:
                    return False, f"User field '{user_field}' is missing."
                if not User.objects.filter(pk=user_id).exists():
                    return False, f"User '{user_id}' does not exist."
                return True, ""

            elif vtype == "ip_reputation":
                from .utils.fraud_detector import check_fraud
                source_ip = payload.get("_source_ip", "")
                bad_subnets = params.get("blocked_subnets", [])
                if bad_subnets and source_ip:
                    import ipaddress
                    for subnet in bad_subnets:
                        try:
                            if ipaddress.ip_address(source_ip) in ipaddress.ip_network(subnet, strict=False):
                                return False, f"Source IP {source_ip} is in blocked subnet {subnet}."
                        except ValueError:
                            pass
                return True, ""

            elif vtype == "custom_expression":
                # Safe limited eval using asteval
                expression = params.get("expression", "True")
                try:
                    import ast
                    tree = ast.parse(expression, mode="eval")
                    # Only allow safe nodes
                    allowed_nodes = (
                        ast.Expression, ast.BoolOp, ast.Compare, ast.Name,
                        ast.Constant, ast.And, ast.Or, ast.Not, ast.UnaryOp,
                        ast.Attribute, ast.Subscript, ast.Load,
                        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                        ast.In, ast.NotIn,
                    )
                    for node in ast.walk(tree):
                        if not isinstance(node, allowed_nodes):
                            return False, f"Unsafe expression node: {type(node).__name__}"
                    result = eval(compile(tree, "<validator>", "eval"), {"payload": payload, "__builtins__": {}})
                    if not result:
                        return False, params.get("failure_message", "Custom expression failed.")
                    return True, ""
                except Exception as exc:
                    return False, f"Expression error: {exc}"

            else:
                return True, ""  # Unknown type → pass

        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).error(
                "LeadValidator.evaluate() error: validator=%s type=%s: %s",
                self.pk, vtype, exc,
            )
            return True, ""  # Never block on validator internal error


# ── PostbackInsight ─────────────────────────────────────────────────────────────

class PostbackInsight(TimeStampedModel):
    """
    Daily analytics and insights for postback performance.
    Aggregated metrics for monitoring and reporting.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="daily_insights",
        verbose_name=_("network"),
        db_index=True,
    )
    date = models.DateField(_("date"), db_index=True)
    
    # ── Count Metrics ───────────────────────────────────────────────────────────
    received_count = models.PositiveIntegerField(_("received count"), default=0)
    validated_count = models.PositiveIntegerField(_("validated count"), default=0)
    rewarded_count = models.PositiveIntegerField(_("rewarded count"), default=0)
    rejected_count = models.PositiveIntegerField(_("rejected count"), default=0)
    duplicate_count = models.PositiveIntegerField(_("duplicate count"), default=0)
    failed_count = models.PositiveIntegerField(_("failed count"), default=0)
    
    # ── Financial Metrics ───────────────────────────────────────────────────────
    total_payout = models.DecimalField(
        _("total payout"),
        max_digits=14,
        decimal_places=4,
        default=0,
        help_text=_("Sum of all payouts for the day."),
    )
    total_points_awarded = models.PositiveIntegerField(_("total points awarded"), default=0)
    
    # ── Health Metrics ─────────────────────────────────────────────────────────
    health_score = models.DecimalField(
        _("health score"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("0-100 score based on success rate and error patterns."),
    )
    average_processing_time = models.FloatField(
        _("average processing time (seconds)"),
        default=0,
        help_text=_("Average time from received to processed."),
    )
    
    # ── Anomaly Detection ───────────────────────────────────────────────────────
    anomaly_detected = models.BooleanField(_("anomaly detected"), default=False)
    anomaly_details = models.JSONField(
        _("anomaly details"),
        default=dict,
        blank=True,
        help_text=_("Details of any detected anomalies."),
    )
    
    # ── Integrity ───────────────────────────────────────────────────────────────
    integrity_hash = models.CharField(
        _("integrity hash"),
        max_length=64,
        db_index=True,
        help_text=_("SHA-256 hash of all metrics for tamper detection."),
    )

    class Meta:
        verbose_name = _("postback insight")
        verbose_name_plural = _("postback insights")
        unique_together = [("network", "date")]
        ordering = ["-date", "network"]
        indexes = [
            models.Index(fields=["network", "date"], name='idx_network_date_1372'),
            models.Index(fields=["date", "health_score"], name='idx_date_health_score_1373'),
            models.Index(fields=["anomaly_detected", "date"], name='idx_anomaly_date_1374'),
            models.Index(fields=["integrity_hash"], name='insight_integrity_hash_1375'),
        ]

    def __str__(self) -> str:
        return f"{self.network.network_key} – {self.date} (Health: {self.health_score}%)"

    def calculate_health_score(self) -> Decimal:
        """Calculate health score based on success rate and error patterns."""
        total = self.received_count
        if total == 0:
            return Decimal('0')
        
        # Base score from success rate
        success_rate = (self.rewarded_count + self.validated_count) / total * 100
        
        # Penalty for high failure rates
        failure_penalty = (self.failed_count + self.rejected_count) / total * 20
        
        # Penalty for duplicates
        duplicate_penalty = self.duplicate_count / total * 10
        
        score = max(0, success_rate - failure_penalty - duplicate_penalty)
        return Decimal(str(min(100, score)))

    def generate_integrity_hash(self) -> str:
        """Generate SHA-256 hash of all metrics for integrity verification."""
        canonical_data = {
            "network_id": str(self.network.pk),
            "date": self.date.isoformat(),
            "received_count": self.received_count,
            "validated_count": self.validated_count,
            "rewarded_count": self.rewarded_count,
            "rejected_count": self.rejected_count,
            "duplicate_count": self.duplicate_count,
            "failed_count": self.failed_count,
            "total_payout": str(self.total_payout),
            "total_points_awarded": self.total_points_awarded,
            "health_score": str(self.health_score),
            "average_processing_time": self.average_processing_time,
            "anomaly_detected": self.anomaly_detected,
        }
        
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the stored integrity_hash matches the current data."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.generate_integrity_hash()
        return self.integrity_hash == current_hash
    
    def save(self, *args, **kwargs):
        """Override save to automatically generate integrity hash."""
        # Generate integrity hash before saving
        self.integrity_hash = self.generate_integrity_hash()
        super().save(*args, **kwargs)


# ── PostbackTemplate ────────────────────────────────────────────────────────────

class PostbackTemplate(TimeStampedModel):
    """
    Reusable postback templates for common network configurations.
    Enables rapid network onboarding with standardized field mappings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="postback_templates",
        verbose_name=_("network"),
        db_index=True,
    )
    name = models.CharField(_("template name"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    
    # ── Template Content ─────────────────────────────────────────────────────────
    template_body = models.TextField(
        _("template body"),
        help_text=_("Template content with variable placeholders like {{lead_id}}"),
    )
    variables = models.JSONField(
        _("variables"),
        default=dict,
        blank=True,
        help_text=_("JSON mapping of variable names to their descriptions and types"),
    )
    
    # ── Validation ───────────────────────────────────────────────────────────────
    validation_regex = models.TextField(
        _("validation regex"),
        blank=True,
        help_text=_("Regex pattern to validate rendered template output"),
    )
    required_variables = models.JSONField(
        _("required variables"),
        default=list,
        blank=True,
        help_text=_("List of variables that must be present in template"),
    )
    
    # ── Status ─────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(_("active"), default=True)
    usage_count = models.PositiveIntegerField(_("usage count"), default=0)
    last_used_at = models.DateTimeField(_("last used at"), null=True, blank=True)
    
    # ── Integrity ───────────────────────────────────────────────────────────────
    integrity_hash = models.CharField(
        _("integrity hash"),
        max_length=64,
        db_index=True,
        help_text=_("SHA-256 hash of template content for tamper detection."),
    )

    class Meta:
        verbose_name = _("postback template")
        verbose_name_plural = _("postback templates")
        unique_together = [("network", "name")]
        ordering = ["network", "name"]
        indexes = [
            models.Index(fields=["network", "is_active"], name='idx_network_active_1376'),
            models.Index(fields=["is_active", "usage_count"], name='idx_active_usage_count_1377'),
            models.Index(fields=["integrity_hash"], name='template_integrity_hash_1378'),
        ]

    def __str__(self) -> str:
        return f"{self.network.network_key} – {self.name} [{'Active' if self.is_active else 'Inactive'}]"

    def render_template(self, context: dict) -> str:
        """
        Render the template with provided context variables.
        Raises ValueError if required variables are missing.
        """
        # Check required variables
        missing_vars = [var for var in self.required_variables if var not in context]
        if missing_vars:
            raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")
        
        # Simple template rendering
        rendered = self.template_body
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder, str(value))
        
        # Validate with regex if provided
        if self.validation_regex:
            import re
            if not re.match(self.validation_regex, rendered):
                raise ValueError(f"Rendered template does not match validation pattern")
        
        return rendered

    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at", "updated_at"])

    def generate_integrity_hash(self) -> str:
        """Generate SHA-256 hash of template content for integrity verification."""
        canonical_data = {
            "network_id": str(self.network.pk),
            "name": self.name,
            "template_body": self.template_body,
            "variables": self.variables,
            "validation_regex": self.validation_regex,
            "required_variables": self.required_variables,
            "is_active": self.is_active,
        }
        
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the stored integrity_hash matches the current data."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.generate_integrity_hash()
        return self.integrity_hash == current_hash


# ── PostbackIPWhitelist ─────────────────────────────────────────────────────────

class PostbackIPWhitelist(TimeStampedModel):
    """
    Dedicated IP whitelist management for postback networks.
    Allows granular control over allowed IP addresses and ranges.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="ip_whitelists",
        verbose_name=_("network"),
        db_index=True,
    )
    name = models.CharField(_("rule name"), max_length=200)
    
    # ── IP Configuration ─────────────────────────────────────────────────────────
    ip_address = models.CharField(
        _("IP address/range"),
        max_length=45,  # IPv6 can be up to 45 chars with CIDR
        db_index=True,
        help_text=_("Single IP address or CIDR range (e.g., 192.168.1.0/24)"),
    )
    description = models.TextField(_("description"), blank=True)
    
    # ── Status ─────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(_("active"), default=True)
    priority = models.PositiveSmallIntegerField(
        _("priority"),
        default=0,
        help_text=_("Higher priority rules are evaluated first."),
    )
    
    # ── Usage Tracking ────────────────────────────────────────────────────────
    last_used_at = models.DateTimeField(_("last used at"), null=True, blank=True)
    usage_count = models.PositiveIntegerField(_("usage count"), default=0)
    
    # ── Integrity ───────────────────────────────────────────────────────────────
    integrity_hash = models.CharField(
        _("integrity hash"),
        max_length=64,
        db_index=True,
        help_text=_("SHA-256 hash of IP rule for tamper detection."),
    )

    class Meta:
        verbose_name = _("postback IP whitelist")
        verbose_name_plural = _("postback IP whitelists")
        unique_together = [("network", "ip_address")]
        ordering = ["network", "-priority", "ip_address"]
        indexes = [
            models.Index(fields=["network", "is_active"], name='idx_ip_network_active_1379'),
            models.Index(fields=["is_active", "priority"], name='idx_ip_active_priority_1380'),
            models.Index(fields=["ip_address", "is_active"], name='idx_ip_address_active_1381'),
            models.Index(fields=["integrity_hash"], name='idx_ip_integrity_hash_1382'),
        ]

    def __str__(self) -> str:
        return f"{self.network.network_key} – {self.ip_address} [{'Active' if self.is_active else 'Inactive'}]"

    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if the given IP address matches this whitelist rule.
        Supports both single IPs and CIDR ranges.
        """
        import ipaddress
        
        if not self.is_active:
            return False
        
        try:
            # Try to parse as a network first (CIDR)
            network = ipaddress.ip_network(self.ip_address, strict=False)
            client_ip = ipaddress.ip_address(ip_address)
            return client_ip in network
        except ValueError:
            # If not a valid network, try exact IP match
            try:
                return self.ip_address == ip_address
            except ValueError:
                return False

    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["usage_count", "last_used_at", "updated_at"])

    def generate_integrity_hash(self) -> str:
        """Generate SHA-256 hash of IP rule for integrity verification."""
        canonical_data = {
            "network_id": str(self.network.pk),
            "name": self.name,
            "ip_address": self.ip_address,
            "description": self.description,
            "is_active": self.is_active,
            "priority": self.priority,
        }
        
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the stored integrity_hash matches the current data."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.generate_integrity_hash()
        return self.integrity_hash == current_hash


# ── PostbackRateLimit ───────────────────────────────────────────────────────────

class PostbackRateLimit(TimeStampedModel):
    """
    Rate limiting configuration for postback networks.
    Prevents abuse and ensures fair usage across networks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig,
        on_delete=models.CASCADE,
        related_name="rate_limits",
        verbose_name=_("network"),
        db_index=True,
    )
    name = models.CharField(_("limit name"), max_length=200)
    
    # ── Rate Configuration ───────────────────────────────────────────────────────
    max_per_minute = models.PositiveIntegerField(
        _("max per minute"),
        default=1000,
        help_text=_("Maximum requests allowed per minute."),
    )
    max_per_hour = models.PositiveIntegerField(
        _("max per hour"),
        default=50000,
        help_text=_("Maximum requests allowed per hour."),
    )
    max_per_day = models.PositiveIntegerField(
        _("max per day"),
        default=1000000,
        help_text=_("Maximum requests allowed per day."),
    )
    
    # ── Current State ───────────────────────────────────────────────────────────
    current_count = models.PositiveIntegerField(_("current count"), default=0)
    last_reset_at = models.DateTimeField(_("last reset at"), default=timezone.now)
    window_start = models.DateTimeField(_("window start"), default=timezone.now)
    
    # ── Status ─────────────────────────────────────────────────────────────────
    is_active = models.BooleanField(_("active"), default=True)
    is_blocked = models.BooleanField(_("blocked"), default=False)
    blocked_until = models.DateTimeField(_("blocked until"), null=True, blank=True)
    
    # ── Tracking ───────────────────────────────────────────────────────────────
    total_violations = models.PositiveIntegerField(_("total violations"), default=0)
    last_violation_at = models.DateTimeField(_("last violation at"), null=True, blank=True)
    
    # ── Integrity ───────────────────────────────────────────────────────────────
    integrity_hash = models.CharField(
        _("integrity hash"),
        max_length=64,
        db_index=True,
        help_text=_("SHA-256 hash of rate limit config for tamper detection."),
    )

    class Meta:
        verbose_name = _("postback rate limit")
        verbose_name_plural = _("postback rate limits")
        unique_together = [("network", "name")]
        ordering = ["network", "name"]
        indexes = [
            models.Index(fields=["network", "is_active"], name='idx_rate_network_active_1383'),
            models.Index(fields=["is_blocked", "blocked_until"], name='idx_rate_blocked_until_1384'),
            models.Index(fields=["window_start", "is_active"], name='idx_rate_window_start_1385'),
            models.Index(fields=["integrity_hash"], name='idx_rate_integrity_hash_1386'),
        ]

    def __str__(self) -> str:
        return f"{self.network.network_key} – {self.name} ({self.max_per_minute}/min)"

    def is_rate_exceeded(self, current_requests: int) -> bool:
        """Check if the current request count exceeds the configured limits."""
        if not self.is_active or self.is_blocked:
            return True  # Block if inactive or explicitly blocked
        
        return current_requests > self.max_per_minute

    def record_violation(self) -> None:
        """Record a rate limit violation and potentially block the network."""
        import datetime
        
        self.total_violations += 1
        self.last_violation_at = timezone.now()
        
        # Block for increasing durations based on violation count
        block_duration = datetime.timedelta(minutes=min(60, self.total_violations * 5))
        self.is_blocked = True
        self.blocked_until = timezone.now() + block_duration
        
        self.save(update_fields=[
            "total_violations", "last_violation_at", "is_blocked", 
            "blocked_until", "updated_at"
        ])

    def reset_window(self) -> None:
        """Reset the counting window and current count."""
        self.current_count = 0
        self.window_start = timezone.now()
        self.last_reset_at = timezone.now()
        
        # Unblock if block period has expired
        if self.is_blocked and self.blocked_until and timezone.now() > self.blocked_until:
            self.is_blocked = False
            self.blocked_until = None
        
        self.save(update_fields=[
            "current_count", "window_start", "last_reset_at", 
            "is_blocked", "blocked_until", "updated_at"
        ])

    def increment_count(self) -> bool:
        """
        Increment the request count and return True if within limits,
        False if rate limit exceeded.
        """
        import datetime
        
        # Reset window if needed (simple implementation - per minute)
        now = timezone.now()
        if now - self.window_start > datetime.timedelta(minutes=1):
            self.reset_window()
        
        self.current_count += 1
        
        if self.is_rate_exceeded(self.current_count):
            self.record_violation()
            return False
        
        self.save(update_fields=["current_count", "updated_at"])
        return True

    def generate_integrity_hash(self) -> str:
        """Generate SHA-256 hash of rate limit config for integrity verification."""
        canonical_data = {
            "network_id": str(self.network.pk),
            "name": self.name,
            "max_per_minute": self.max_per_minute,
            "max_per_hour": self.max_per_hour,
            "max_per_day": self.max_per_day,
            "is_active": self.is_active,
        }
        
        canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the stored integrity_hash matches the current data."""
        if not self.integrity_hash:
            return False
        
        current_hash = self.generate_integrity_hash()
        return self.integrity_hash == current_hash


# ── PostbackS2SLog ────────────────────────────────────────────────────────────

class PostbackS2SLog(models.Model):
    """
    Audit log for every outbound S2S postback attempt.

    Write-once per attempt: one row per HTTP fire, including retries.
    Never updated after creation – use a new row for each attempt.
    Added in migration 0006.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    postback_log = models.ForeignKey(
        PostbackLog,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="s2s_logs",
        verbose_name=_("postback log"),
    )

    # ── Request ───────────────────────────────────────────────────────────────
    callback_url = models.CharField(
        _("callback URL"),
        max_length=2000,
        help_text=_("Outbound URL fired (macros substituted)."),
    )

    # ── Response ──────────────────────────────────────────────────────────────
    http_status = models.PositiveSmallIntegerField(
        _("HTTP status"),
        null=True,
        blank=True,
    )
    response_body = models.TextField(_("response body"), blank=True)

    # ── Outcome ───────────────────────────────────────────────────────────────
    success = models.BooleanField(_("success"), default=False, db_index=True)
    attempt_number = models.PositiveSmallIntegerField(_("attempt number"), default=1)
    error_message = models.CharField(_("error message"), max_length=500, blank=True)

    # ── Timing ────────────────────────────────────────────────────────────────
    fired_at = models.DateTimeField(
        _("fired at"),
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        verbose_name = _("postback S2S log")
        verbose_name_plural = _("postback S2S logs")
        ordering = ["-fired_at"]
        indexes = [
            models.Index(fields=["postback_log", "success"], name="idx_s2s_log_success_1368"),
            models.Index(fields=["fired_at"], name="idx_s2s_log_fired_at_1369"),
        ]

    def __str__(self) -> str:
        status_str = "OK" if self.success else f"ERR {self.http_status}"
        return (
            f"S2S [{status_str}] attempt={self.attempt_number} "
            f"@ {self.fired_at:%Y-%m-%d %H:%M:%S}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# MISSING COMPONENTS — Added to match CPAlead / OGAds / AdGate / Offertoro / Monlix
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Offer / Task Catalogue ─────────────────────────────────────────────────

class OfferCategory(TimeStampedModel):
    """Top-level category grouping offers (e.g. 'Games', 'Surveys', 'Shopping')."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=120)
    slug = models.SlugField(_("slug"), max_length=120, unique=True)
    icon_url = models.URLField(_("icon URL"), blank=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("offer category")
        verbose_name_plural = _("offer categories")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Offer(TimeStampedModel):
    """
    A single earning opportunity shown in the offerwall.
    Mirrors CPAlead / AdGate / Offertoro offer schema.
    """
    DIFFICULTY = [
        ("easy", "Easy (< 2 min)"),
        ("medium", "Medium (2–10 min)"),
        ("hard", "Hard (10+ min)"),
    ]
    DEVICE_TARGET = [
        ("all", "All devices"),
        ("mobile", "Mobile only"),
        ("desktop", "Desktop only"),
        ("android", "Android only"),
        ("ios", "iOS only"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig, on_delete=models.CASCADE,
        related_name="offers", verbose_name=_("network"),
    )
    category = models.ForeignKey(
        OfferCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="offers",
    )
    external_offer_id = models.CharField(
        _("external offer ID"), max_length=255, db_index=True,
        help_text=_("Offer ID as used by the network (e.g. CPAlead task_id)."),
    )
    name = models.CharField(_("offer name"), max_length=500)
    description = models.TextField(_("description"), blank=True)
    requirements = models.TextField(
        _("requirements"),
        blank=True,
        help_text=_("Human-readable steps a user must complete."),
    )
    points_reward = models.PositiveIntegerField(
        _("points reward"),
        help_text=_("Points awarded on completion."),
    )
    payout_usd = models.DecimalField(
        _("payout (USD)"), max_digits=10, decimal_places=4, default=0,
        help_text=_("Network payout in USD (for reference/cap enforcement)."),
    )
    difficulty = models.CharField(_("difficulty"), max_length=10, choices=DIFFICULTY, default="medium")
    device_target = models.CharField(_("device target"), max_length=10, choices=DEVICE_TARGET, default="all")
    icon_url = models.URLField(_("icon URL"), blank=True)
    offer_url = models.URLField(_("offer URL"), max_length=2000, blank=True)
    countries_allowed = models.JSONField(
        _("countries allowed"),
        default=list, blank=True,
        help_text=_("ISO-3166-1 alpha-2 country codes. Empty = all countries."),
    )
    countries_blocked = models.JSONField(_("countries blocked"), default=list, blank=True)
    idfa_required = models.BooleanField(
        _("IDFA required"),
        default=False,
        help_text=_("OGAds CPI offers: iOS IDFA must be collected before redirect."),
    )
    gaid_required = models.BooleanField(
        _("GAID required"),
        default=False,
        help_text=_("OGAds CPI offers: Android GAID must be collected before redirect."),
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    is_featured = models.BooleanField(_("featured"), default=False)
    daily_cap = models.PositiveIntegerField(
        _("daily cap"), default=0,
        help_text=_("Max completions per day across all users. 0 = unlimited."),
    )
    user_daily_cap = models.PositiveSmallIntegerField(
        _("per-user daily cap"), default=1,
        help_text=_("Max completions per user per day. 1 = complete once per day."),
    )
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("offer")
        verbose_name_plural = _("offers")
        ordering = ["-is_featured", "-points_reward"]
        indexes = [
            models.Index(fields=["network", "is_active"], name="idx_offer_network_active_2001"),
            models.Index(fields=["external_offer_id"], name="idx_offer_ext_id_2002"),
        ]
        unique_together = [("network", "external_offer_id")]

    def __str__(self):
        return f"{self.name} ({self.points_reward} pts)"

    def is_available_for_country(self, country_code: str) -> bool:
        if self.countries_blocked and country_code in self.countries_blocked:
            return False
        if self.countries_allowed and country_code not in self.countries_allowed:
            return False
        return True


class OfferClick(models.Model):
    """Tracks each time a user clicks through to an offer — used to link postbacks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="clicks")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_offer_clicks",
    )
    click_id = models.CharField(
        _("click ID"), max_length=255, unique=True, db_index=True,
        help_text=_("Unique click token passed as sub_id1 / aff_sub1 to the network."),
    )
    source_ip = models.GenericIPAddressField(_("source IP"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    country_code = models.CharField(_("country code"), max_length=2, blank=True, db_index=True)
    device_type = models.CharField(
        _("device type"), max_length=10,
        choices=[("mobile", "Mobile"), ("desktop", "Desktop"), ("tablet", "Tablet")],
        blank=True,
    )
    idfa = models.CharField(_("IDFA"), max_length=36, blank=True)
    gaid = models.CharField(_("GAID"), max_length=36, blank=True)
    clicked_at = models.DateTimeField(_("clicked at"), default=timezone.now, db_index=True)
    converted = models.BooleanField(_("converted"), default=False, db_index=True)
    postback_log = models.OneToOneField(
        PostbackLog, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="offer_click",
    )

    class Meta:
        verbose_name = _("offer click")
        verbose_name_plural = _("offer clicks")
        ordering = ["-clicked_at"]
        indexes = [
            models.Index(fields=["user", "offer", "clicked_at"], name="idx_click_user_offer_2003"),
        ]

    def __str__(self):
        return f"Click {self.click_id} → {self.offer_id}"


class UserOfferCompletion(models.Model):
    """Records a user completing an offer (after postback confirmed)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_offer_completions",
    )
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="completions")
    postback_log = models.ForeignKey(
        PostbackLog, on_delete=models.SET_NULL, null=True, blank=True, related_name="completions",
    )
    points_awarded = models.PositiveIntegerField(_("points awarded"))
    completed_at = models.DateTimeField(_("completed at"), default=timezone.now, db_index=True)
    is_reversed = models.BooleanField(_("reversed"), default=False)

    class Meta:
        verbose_name = _("user offer completion")
        verbose_name_plural = _("user offer completions")
        ordering = ["-completed_at"]
        indexes = [
            models.Index(fields=["user", "offer"], name="idx_completion_user_offer_2004"),
        ]

    def __str__(self):
        return f"{self.user_id} completed {self.offer_id}"


# ── 2. Withdrawal / Payout System ─────────────────────────────────────────────

class PaymentMethod(TimeStampedModel):
    """A user's saved cashout method (PayPal, bKash, Binance, gift card, etc.)."""
    METHOD_TYPES = [
        ("paypal", "PayPal"),
        ("bkash", "bKash"),
        ("nagad", "Nagad"),
        ("binance_pay", "Binance Pay"),
        ("usdt_trc20", "USDT TRC-20"),
        ("bitcoin", "Bitcoin"),
        ("amazon_gift", "Amazon Gift Card"),
        ("bank_transfer", "Bank Transfer"),
        ("skrill", "Skrill"),
        ("wise", "Wise"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_payment_methods",
    )
    method_type = models.CharField(_("method type"), max_length=20, choices=METHOD_TYPES)
    account_identifier = models.CharField(
        _("account / address"), max_length=500,
        help_text=_("Email, phone, wallet address, or account number."),
    )
    is_verified = models.BooleanField(_("verified"), default=False)
    is_default = models.BooleanField(_("default"), default=False)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("payment method")
        verbose_name_plural = _("payment methods")
        ordering = ["-is_default", "method_type"]

    def __str__(self):
        return f"{self.get_method_type_display()} — {self.account_identifier[:30]}"


class WithdrawalRequest(TimeStampedModel):
    """A user's request to cash out their earned points/balance."""
    STATUS = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled by User"),
        ("failed", "Failed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_withdrawal_requests",
    )
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.PROTECT, related_name="withdrawals",
    )
    points_requested = models.PositiveIntegerField(_("points requested"))
    amount_bdt = models.DecimalField(
        _("amount (BDT)"), max_digits=12, decimal_places=2,
        help_text=_("Calculated at submission time using current rate."),
    )
    status = models.CharField(_("status"), max_length=12, choices=STATUS, default="pending", db_index=True)
    admin_note = models.TextField(_("admin note"), blank=True)
    rejection_reason = models.CharField(_("rejection reason"), max_length=500, blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="postback_processed_withdrawals",
    )
    transaction_reference = models.CharField(
        _("transaction reference"), max_length=255, blank=True,
        help_text=_("External payment gateway reference/txn ID."),
    )

    class Meta:
        verbose_name = _("withdrawal request")
        verbose_name_plural = _("withdrawal requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="withdrawal_user_status_2010"),
            models.Index(fields=["status", "created_at"], name="withdrawal_status_date_2011"),
        ]

    def __str__(self):
        return f"Withdrawal #{self.pk} — {self.user_id} — {self.amount_bdt} BDT ({self.status})"


# ── 3. Referral / Affiliate Program ───────────────────────────────────────────

class ReferralProgram(TimeStampedModel):
    """Global or per-campaign referral program configuration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=200)
    is_active = models.BooleanField(_("active"), default=True)
    commission_type = models.CharField(
        _("commission type"),
        max_length=10,
        choices=[("percent", "% of referral earnings"), ("flat", "Flat points per referral")],
        default="percent",
    )
    commission_value = models.DecimalField(
        _("commission value"), max_digits=6, decimal_places=2,
        help_text=_("% (0–100) for percent type, or flat points for flat type."),
    )
    max_referral_depth = models.PositiveSmallIntegerField(
        _("max referral depth"), default=1,
        help_text=_("1 = direct only. 2 = direct + their referrals earn too."),
    )
    referral_bonus_points = models.PositiveIntegerField(
        _("referral signup bonus"), default=0,
        help_text=_("One-time bonus for the referrer when a new user signs up via their link."),
    )
    referee_bonus_points = models.PositiveIntegerField(
        _("referee signup bonus"), default=0,
        help_text=_("One-time bonus for the new user who signed up via a referral link."),
    )
    minimum_earning_for_commission = models.PositiveIntegerField(
        _("minimum earning for commission"), default=0,
        help_text=_("Referral must earn at least N points before commission fires."),
    )

    class Meta:
        verbose_name = _("referral program")
        verbose_name_plural = _("referral programs")

    def __str__(self):
        return self.name


class UserReferral(TimeStampedModel):
    """Tracks who referred whom."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(ReferralProgram, on_delete=models.CASCADE, related_name="referrals")
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_referrals_made",
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="postback_referred_by",
    )
    referral_code = models.CharField(_("referral code"), max_length=20, db_index=True)
    total_commission_earned = models.DecimalField(
        _("total commission earned"), max_digits=12, decimal_places=2, default=0,
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("user referral")
        verbose_name_plural = _("user referrals")
        unique_together = [("referrer", "referee")]

    def __str__(self):
        return f"{self.referrer_id} → {self.referee_id}"


class ReferralCommission(models.Model):
    """One commission payment earned by a referrer."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral = models.ForeignKey(UserReferral, on_delete=models.CASCADE, related_name="commissions")
    postback_log = models.ForeignKey(
        PostbackLog, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referral_commissions",
    )
    points_awarded = models.PositiveIntegerField(_("points awarded"))
    commission_rate = models.DecimalField(_("commission rate"), max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("referral commission")
        verbose_name_plural = _("referral commissions")
        ordering = ["-created_at"]


# ── 4. User Tier / VIP Level ──────────────────────────────────────────────────

class UserTier(models.Model):
    """Tier configuration (Bronze / Silver / Gold / Platinum)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=50, unique=True)
    slug = models.SlugField(_("slug"), max_length=50, unique=True)
    min_lifetime_points = models.PositiveIntegerField(
        _("min lifetime points"),
        help_text=_("User enters this tier when they cross this threshold."),
    )
    earnings_multiplier = models.DecimalField(
        _("earnings multiplier"), max_digits=4, decimal_places=2, default=1,
        help_text=_("1.0 = base. 1.5 = 50% bonus on all postback rewards."),
    )
    withdrawal_priority = models.PositiveSmallIntegerField(
        _("withdrawal priority"), default=0,
        help_text=_("Higher = processed first in the payout queue."),
    )
    badge_color = models.CharField(_("badge color"), max_length=7, default="#888888")
    badge_icon = models.CharField(_("badge icon"), max_length=100, blank=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        verbose_name = _("user tier")
        verbose_name_plural = _("user tiers")
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class UserTierMembership(TimeStampedModel):
    """Tracks a user's current tier and lifetime points."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="tier_membership", primary_key=True,
    )
    tier = models.ForeignKey(UserTier, on_delete=models.PROTECT, related_name="members")
    lifetime_points = models.PositiveIntegerField(_("lifetime points"), default=0)
    tier_entered_at = models.DateTimeField(_("tier entered at"), default=timezone.now)

    class Meta:
        verbose_name = _("user tier membership")
        verbose_name_plural = _("user tier memberships")

    def __str__(self):
        return f"{self.user_id} — {self.tier}"

    def recalculate_tier(self):
        """Promote/demote user based on lifetime_points. Called after each postback reward."""
        best = (
            UserTier.objects.filter(min_lifetime_points__lte=self.lifetime_points)
            .order_by("-min_lifetime_points")
            .first()
        )
        if best and best != self.tier:
            self.tier = best
            self.tier_entered_at = timezone.now()
            self.save(update_fields=["tier", "tier_entered_at", "updated_at"])


# ── 5. Daily Bonus / Login Streak ─────────────────────────────────────────────

class DailyBonusConfig(models.Model):
    """Configures the streak reward schedule (day 1 → N points, day 7 → N*5 points, etc.)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day_number = models.PositiveSmallIntegerField(_("day number"), unique=True)
    points_reward = models.PositiveIntegerField(_("points reward"))
    is_milestone = models.BooleanField(_("milestone day"), default=False)
    label = models.CharField(_("label"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("daily bonus config")
        verbose_name_plural = _("daily bonus configs")
        ordering = ["day_number"]

    def __str__(self):
        return f"Day {self.day_number} — {self.points_reward} pts"


class UserLoginStreak(models.Model):
    """Tracks a user's login streak for daily bonus eligibility."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="login_streak", primary_key=True,
    )
    current_streak = models.PositiveSmallIntegerField(_("current streak"), default=0)
    longest_streak = models.PositiveSmallIntegerField(_("longest streak"), default=0)
    last_claim_date = models.DateField(_("last claim date"), null=True, blank=True)
    total_bonuses_claimed = models.PositiveIntegerField(_("total bonuses claimed"), default=0)
    total_points_from_bonus = models.PositiveIntegerField(_("total points from bonus"), default=0)

    class Meta:
        verbose_name = _("user login streak")
        verbose_name_plural = _("user login streaks")

    def __str__(self):
        return f"{self.user_id} — streak {self.current_streak}"

    def claim_daily_bonus(self) -> int:
        """
        Claim today's bonus if not already claimed.
        Returns points awarded (0 if already claimed today).
        """
        from django.utils.timezone import localdate
        today = localdate()
        if self.last_claim_date == today:
            return 0
        yesterday = today - timezone.timedelta(days=1)
        if self.last_claim_date == yesterday:
            self.current_streak += 1
        else:
            self.current_streak = 1
        self.longest_streak = max(self.longest_streak, self.current_streak)
        self.last_claim_date = today
        day_config = (
            DailyBonusConfig.objects.filter(day_number=self.current_streak).first()
            or DailyBonusConfig.objects.order_by("-day_number").first()
        )
        points = day_config.points_reward if day_config else 10
        self.total_bonuses_claimed += 1
        self.total_points_from_bonus += points
        self.save()
        return points


# ── 6. Leaderboard ────────────────────────────────────────────────────────────

class LeaderboardPeriod(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    ALL_TIME = "all_time", "All Time"


class LeaderboardEntry(models.Model):
    """
    Materialized leaderboard snapshot. Rebuilt by a Celery beat task.
    One row per (user, period, period_start).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.CharField(_("period"), max_length=10, choices=LeaderboardPeriod.choices, db_index=True)
    period_start = models.DateField(_("period start"), db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leaderboard_entries",
    )
    rank = models.PositiveIntegerField(_("rank"), db_index=True)
    points_earned = models.PositiveIntegerField(_("points earned"))
    offers_completed = models.PositiveIntegerField(_("offers completed"), default=0)
    display_name = models.CharField(_("display name"), max_length=100, blank=True)
    avatar_url = models.URLField(_("avatar URL"), blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("leaderboard entry")
        verbose_name_plural = _("leaderboard entries")
        ordering = ["period", "period_start", "rank"]
        unique_together = [("period", "period_start", "user")]
        indexes = [
            models.Index(fields=["period", "period_start", "rank"], name="idx_lb_period_rank_2020"),
        ]

    def __str__(self):
        return f"#{self.rank} {self.display_name} — {self.period} — {self.points_earned} pts"


# ── 7. Geo Targeting ──────────────────────────────────────────────────────────

class GeoTargetingRule(TimeStampedModel):
    """Per-network country allow/block rules and routing configuration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig, on_delete=models.CASCADE, related_name="geo_rules",
    )
    country_code = models.CharField(
        _("country code"), max_length=2, db_index=True,
        help_text=_("ISO 3166-1 alpha-2, e.g. 'BD', 'US', 'GB'."),
    )
    action = models.CharField(
        _("action"), max_length=5,
        choices=[("allow", "Allow"), ("block", "Block"), ("bonus", "Bonus Multiplier")],
        default="allow",
    )
    payout_multiplier = models.DecimalField(
        _("payout multiplier"), max_digits=4, decimal_places=2, default=1,
        help_text=_("Multiplies points_reward for users in this country. Requires action=bonus."),
    )
    is_active = models.BooleanField(_("active"), default=True)
    priority = models.PositiveSmallIntegerField(_("priority"), default=0)

    class Meta:
        verbose_name = _("geo targeting rule")
        verbose_name_plural = _("geo targeting rules")
        ordering = ["-priority", "country_code"]
        unique_together = [("network", "country_code", "action")]

    def __str__(self):
        return f"{self.network.network_key} — {self.country_code} — {self.action}"


# ── 8. Survey Router ──────────────────────────────────────────────────────────

class SurveyRouter(TimeStampedModel):
    """
    Routes users to the highest-EPC survey provider available for their
    country + device combination. Mirrors AdGate / Offertoro survey routing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=200)
    network = models.ForeignKey(
        NetworkPostbackConfig, on_delete=models.CASCADE,
        related_name="survey_routers", null=True, blank=True,
    )
    provider_key = models.CharField(
        _("provider key"), max_length=50,
        help_text=_("Matches adapter key: pollfish, cpx_research, inbrain, theorem_reach, bitlabs."),
    )
    router_url_template = models.CharField(
        _("router URL template"), max_length=2000,
        help_text=_(
            "URL with macros: {user_id}, {country_code}, {device_type}, "
            "{sub_id1}, {sub_id2}, {api_key}."
        ),
    )
    countries_supported = models.JSONField(
        _("countries supported"), default=list,
        help_text=_("ISO-2 codes. Empty = all countries."),
    )
    device_support = models.CharField(
        _("device support"), max_length=10,
        choices=[("all", "All"), ("mobile", "Mobile"), ("desktop", "Desktop")],
        default="all",
    )
    min_cpi_usd = models.DecimalField(
        _("min CPI (USD)"), max_digits=6, decimal_places=4, default=0,
        help_text=_("Minimum earnings per survey completion in USD."),
    )
    priority = models.PositiveSmallIntegerField(
        _("priority"), default=0,
        help_text=_("Higher = tried first. Router waterfalls to next if no surveys available."),
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    api_key = models.CharField(_("API key"), max_length=500, blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    class Meta:
        verbose_name = _("survey router")
        verbose_name_plural = _("survey routers")
        ordering = ["-priority"]

    def __str__(self):
        return f"{self.name} ({self.provider_key})"

    def build_redirect_url(self, user_id: str, country_code: str, device_type: str,
                           sub_id1: str = "", sub_id2: str = "") -> str:
        """Substitute macros and return the redirect URL."""
        return self.router_url_template.format(
            user_id=user_id,
            country_code=country_code,
            device_type=device_type,
            sub_id1=sub_id1,
            sub_id2=sub_id2,
            api_key=self.api_key,
        )

    def is_available_for(self, country_code: str, device_type: str) -> bool:
        country_ok = (not self.countries_supported) or (country_code in self.countries_supported)
        device_ok = self.device_support == "all" or self.device_support == device_type
        return self.is_active and country_ok and device_ok


# ── 9. Offerwall SDK Embed ────────────────────────────────────────────────────

class OfferwallSDKConfig(TimeStampedModel):
    """
    Generates a signed iframe / SDK embed URL for a publisher's site.
    Mirrors OGAds content locking and AdGate offerwall embed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.ForeignKey(
        NetworkPostbackConfig, on_delete=models.CASCADE, related_name="sdk_configs",
    )
    publisher_name = models.CharField(_("publisher name"), max_length=200)
    sdk_key = models.CharField(
        _("SDK key"), max_length=128, unique=True,
        help_text=_("Public key embedded in the iframe URL — identifies the publisher."),
    )
    sdk_secret = models.CharField(
        _("SDK secret"), max_length=256,
        help_text=_("Used to sign the iframe URL. Never exposed client-side."),
    )
    allowed_domains = models.JSONField(
        _("allowed domains"), default=list,
        help_text=_("List of domains that may embed this offerwall. Empty = unrestricted."),
    )
    theme = models.CharField(
        _("theme"), max_length=10,
        choices=[("light", "Light"), ("dark", "Dark"), ("auto", "Auto")],
        default="auto",
    )
    primary_color = models.CharField(_("primary color"), max_length=7, default="#2196F3")
    show_search = models.BooleanField(_("show search bar"), default=True)
    show_categories = models.BooleanField(_("show categories"), default=True)
    default_category = models.ForeignKey(
        OfferCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sdk_configs",
    )
    session_ttl_seconds = models.PositiveIntegerField(
        _("session TTL (seconds)"), default=3600,
        help_text=_("Signed embed URL expires after this many seconds."),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("offerwall SDK config")
        verbose_name_plural = _("offerwall SDK configs")

    def __str__(self):
        return f"SDK — {self.publisher_name} ({self.sdk_key})"

    def generate_embed_url(self, user_id: str, country_code: str = "",
                           device_type: str = "all", sub_id1: str = "") -> str:
        """
        Returns a signed embed URL that can be used as an iframe src.
        The signature prevents tampering with user_id or payout parameters.
        """
        import hashlib, hmac, time, urllib.parse
        expiry = int(time.time()) + self.session_ttl_seconds
        params = {
            "sdk_key": self.sdk_key,
            "user_id": user_id,
            "country": country_code,
            "device": device_type,
            "sub1": sub_id1,
            "exp": expiry,
        }
        query = urllib.parse.urlencode(sorted(params.items()))
        sig = hmac.new(
            self.sdk_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        return f"/api/postback/offerwall/embed/?{query}&sig={sig}"


# ── DevicePushToken ───────────────────────────────────────────────────────────

class DevicePushToken(models.Model):
    """
    FCM (Firebase) and APNs push notification tokens per user device.
    Updated on every app launch; stale tokens cleaned by Celery beat.
    """
    PLATFORM = [
        ("android", "Android (FCM)"),
        ("ios", "iOS (APNs via FCM)"),
        ("web", "Web Push"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="push_tokens",
    )
    token = models.TextField(
        _("push token"),
        unique=True,
        help_text=_("FCM registration token or APNs device token."),
    )
    platform = models.CharField(_("platform"), max_length=8, choices=PLATFORM, db_index=True)
    device_id = models.CharField(
        _("device ID"), max_length=255, blank=True,
        help_text=_("Stable device fingerprint — used to replace old tokens for the same device."),
    )
    app_version = models.CharField(_("app version"), max_length=20, blank=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    last_used_at = models.DateTimeField(_("last used at"), default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("device push token")
        verbose_name_plural = _("device push tokens")
        ordering = ["-last_used_at"]
        indexes = [
            models.Index(fields=["user", "is_active"], name="push_token_user_active_3001"),
        ]

    def __str__(self):
        return f"{self.platform} token for {self.user_id}"


# ── ManualPointsAdjustment ────────────────────────────────────────────────────

class ManualPointsAdjustment(TimeStampedModel):
    """
    Admin-initiated manual credit or debit of points.
    Every adjustment is logged with admin user, reason, and IP for audit trail.
    """
    ADJUSTMENT_TYPE = [
        ("credit", "Credit (add points)"),
        ("debit", "Debit (remove points)"),
        ("bonus", "Bonus / promotional"),
        ("correction", "Correction / error fix"),
        ("penalty", "Penalty"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="manual_adjustments",
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="adjustments_made",
    )
    adjustment_type = models.CharField(_("type"), max_length=12, choices=ADJUSTMENT_TYPE)
    points = models.PositiveIntegerField(
        _("points"),
        help_text=_("Always positive. adjustment_type determines credit vs debit."),
    )
    reason = models.TextField(_("reason"), help_text=_("Required explanation for audit trail."))
    admin_ip = models.GenericIPAddressField(_("admin IP"), null=True, blank=True)
    reference_id = models.CharField(
        _("reference"), max_length=255, blank=True,
        help_text=_("Optional: ticket ID, postback ID, etc."),
    )

    class Meta:
        verbose_name = _("manual points adjustment")
        verbose_name_plural = _("manual points adjustments")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.adjustment_type} {self.points} pts → {self.user_id} by {self.admin_id}"


# ── SiteConfig (Global admin-controlled settings) ────────────────────────────

class SiteConfig(models.Model):
    """
    Singleton table — admin-controlled runtime settings.
    Only one row should ever exist (enforced by save()).

    Covers: min withdrawal, points-to-BDT rate, maintenance mode,
    referral activation, daily bonus activation.
    """
    # Points economy
    points_to_bdt_rate = models.DecimalField(
        _("points → BDT rate"),
        max_digits=10, decimal_places=6,
        default="0.010000",
        help_text=_("1 point = this many BDT. Changing this affects ALL future withdrawals."),
    )
    points_to_usd_rate = models.DecimalField(
        _("points → USD rate"),
        max_digits=10, decimal_places=8,
        default="0.00010000",
        help_text=_("1 point = this many USD. Used for network payout cross-checks."),
    )
    min_withdrawal_points = models.PositiveIntegerField(
        _("min withdrawal (points)"),
        default=500,
        help_text=_("Users cannot request a withdrawal below this point threshold."),
    )
    max_withdrawal_points_per_day = models.PositiveIntegerField(
        _("max withdrawal per day (points)"),
        default=50000,
        help_text=_("Per-user daily withdrawal cap. 0 = unlimited."),
    )

    # Feature flags
    maintenance_mode = models.BooleanField(
        _("maintenance mode"),
        default=False,
        help_text=_("When True, all earning endpoints return 503. Admin panel still accessible."),
    )
    referral_program_enabled = models.BooleanField(_("referral program enabled"), default=True)
    daily_bonus_enabled = models.BooleanField(_("daily bonus enabled"), default=True)
    leaderboard_enabled = models.BooleanField(_("leaderboard enabled"), default=True)
    survey_router_enabled = models.BooleanField(_("survey router enabled"), default=True)
    offerwall_enabled = models.BooleanField(_("offerwall enabled"), default=True)

    # Fraud thresholds
    max_completions_per_user_per_day = models.PositiveSmallIntegerField(
        _("max offer completions per user per day"),
        default=50,
        help_text=_("Hard limit across all offers. Anti-abuse guard."),
    )
    max_withdrawal_requests_per_day = models.PositiveSmallIntegerField(
        _("max withdrawal requests per day"),
        default=3,
    )
    withdrawal_fraud_hold_hours = models.PositiveSmallIntegerField(
        _("withdrawal fraud hold (hours)"),
        default=24,
        help_text=_("New users must wait N hours after first earn before first withdrawal."),
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = _("site config")
        verbose_name_plural = _("site config")

    def __str__(self):
        return f"SiteConfig (1 BDT per {1 / float(self.points_to_bdt_rate):.0f} pts)"

    def save(self, *args, **kwargs):
        self.pk = 1  # Singleton
        super().save(*args, **kwargs)
        self._bust_cache()

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def _bust_cache(self):
        try:
            from django.core.cache import cache
            cache.delete("site_config_singleton")
        except Exception:
            pass

    @classmethod
    def cached(cls):
        """Cache-first access — use this in hot paths."""
        try:
            from django.core.cache import cache
            obj = cache.get("site_config_singleton")
            if obj is None:
                obj = cls.get()
                cache.set("site_config_singleton", obj, timeout=300)
            return obj
        except Exception:
            return cls.get()


# ── CurrencyRate (historical rate log) ───────────────────────────────────────

class CurrencyRate(models.Model):
    """
    Historical log of points↔BDT rate changes.
    One row per rate change — the latest active row is the current rate.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    points_to_bdt = models.DecimalField(
        _("points → BDT"), max_digits=10, decimal_places=6,
    )
    points_to_usd = models.DecimalField(
        _("points → USD"), max_digits=10, decimal_places=8,
    )
    effective_from = models.DateTimeField(
        _("effective from"), default=timezone.now, db_index=True,
    )
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="currency_rate_changes",
    )
    note = models.TextField(_("note"), blank=True)

    class Meta:
        verbose_name = _("currency rate")
        verbose_name_plural = _("currency rates")
        ordering = ["-effective_from"]
        get_latest_by = "effective_from"

    def __str__(self):
        return f"1 pt = {self.points_to_bdt} BDT (from {self.effective_from:%Y-%m-%d})"


# ── ManualPointAdjustment (Admin-initiated credit / debit) ────────────────────

class ManualPointAdjustment(models.Model):
    """
    Admin-initiated point credit or debit to a user's account.
    All CPA platforms provide this for dispute resolution and bonuses.
    """
    TYPES = [
        ("credit", "Credit (add points)"),
        ("debit", "Debit (remove points)"),
    ]
    REASONS = [
        ("bonus", "Bonus / Promotion"),
        ("correction", "Error Correction"),
        ("dispute_resolution", "Dispute Resolution"),
        ("referral_manual", "Manual Referral Award"),
        ("chargeback_penalty", "Chargeback Penalty"),
        ("fraud_clawback", "Fraud Clawback"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="manual_point_adjustments",
    )
    adjustment_type = models.CharField(_("type"), max_length=6, choices=TYPES)
    points = models.PositiveIntegerField(_("points"), help_text=_("Absolute value — always positive."))
    reason = models.CharField(_("reason"), max_length=30, choices=REASONS, default="bonus")
    note = models.TextField(_("admin note"), blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="performed_adjustments",
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("manual point adjustment")
        verbose_name_plural = _("manual point adjustments")
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.adjustment_type == "credit" else "-"
        return f"{sign}{self.points} pts → {self.user} ({self.reason})"


# ── FCMDevice (Push notification tokens) ─────────────────────────────────────

class FCMDevice(models.Model):
    """
    Stores Firebase Cloud Messaging / APNs push tokens per device.
    Enables withdrawal-approved, tier-upgrade, daily-bonus push notifications.
    """
    PLATFORMS = [
        ("android", "Android (FCM)"),
        ("ios", "iOS (APNs via FCM)"),
        ("web", "Web Push"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="fcm_devices",
    )
    registration_id = models.TextField(
        _("registration token"),
        help_text=_("FCM registration token or APNs device token."),
    )
    platform = models.CharField(_("platform"), max_length=8, choices=PLATFORMS, default="android")
    device_id = models.CharField(
        _("device fingerprint / UUID"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Unique device identifier for deduplication."),
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    last_used_at = models.DateTimeField(_("last used at"), default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("FCM device")
        verbose_name_plural = _("FCM devices")
        ordering = ["-last_used_at"]
        unique_together = [("user", "device_id")]

    def __str__(self):
        return f"{self.platform} device — {self.user_id}"


# ── OfferImpression (viewed / displayed tracking) ────────────────────────────

class OfferImpression(models.Model):
    """
    Records every time an offer is shown to a user in the offerwall.
    Used for CTR (click-through rate) analytics and frequency capping.
    Mirrors AdGate/Offertoro impression analytics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="impressions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="postback_offer_impressions",
    )
    sdk_config = models.ForeignKey(
        OfferwallSDKConfig, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="impressions",
    )
    country_code = models.CharField(_("country code"), max_length=2, blank=True, db_index=True)
    device_type = models.CharField(_("device type"), max_length=10, blank=True)
    shown_at = models.DateTimeField(_("shown at"), default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("offer impression")
        verbose_name_plural = _("offer impressions")
        ordering = ["-shown_at"]
        indexes = [
            models.Index(fields=["offer", "user", "shown_at"], name="idx_impression_offer_user_3001"),
        ]

    def __str__(self):
        return f"Impression: {self.offer_id} → {self.user_id} @ {self.shown_at:%Y-%m-%d %H:%M}"


# ── OfferDailyCapCounter (runtime cap enforcement) ───────────────────────────

class OfferDailyCapCounter(models.Model):
    """
    Tracks daily completion count per offer (global) and per user.
    Checked atomically at completion time to enforce Offer.daily_cap
    and Offer.user_daily_cap.
    """
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="cap_counters")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="offer_cap_counters",
    )
    date = models.DateField(_("date"), default=timezone.now, db_index=True)
    user_count = models.PositiveSmallIntegerField(_("user completions today"), default=0)

    class Meta:
        verbose_name = _("offer daily cap counter")
        verbose_name_plural = _("offer daily cap counters")
        unique_together = [("offer", "user", "date")]
        indexes = [
            models.Index(fields=["offer", "date"], name="idx_cap_offer_date_3002"),
        ]

    def __str__(self):
        return f"{self.offer_id} / {self.user_id} — {self.date} — {self.user_count}"

    @classmethod
    def check_and_increment(cls, offer: "Offer", user) -> tuple[bool, str]:
        """
        Thread-safe cap check + increment using select_for_update.
        Returns (allowed: bool, reason: str).
        """
        from django.db import transaction
        from django.utils.timezone import localdate

        today = localdate()

        with transaction.atomic():
            # Global daily cap
            if offer.daily_cap > 0:
                global_count = UserOfferCompletion.objects.filter(
                    offer=offer,
                    completed_at__date=today,
                    is_reversed=False,
                ).count()
                if global_count >= offer.daily_cap:
                    return False, f"Offer has reached its daily cap of {offer.daily_cap} completions."

            # Per-user cap
            counter, _ = cls.objects.select_for_update().get_or_create(
                offer=offer, user=user, date=today,
            )
            if offer.user_daily_cap > 0 and counter.user_count >= offer.user_daily_cap:
                return False, f"You can only complete this offer {offer.user_daily_cap}x per day."

            counter.user_count += 1
            counter.save(update_fields=["user_count"])

        return True, ""
