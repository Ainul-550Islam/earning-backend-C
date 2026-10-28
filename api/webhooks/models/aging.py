# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Aging & Lifecycle Models

Tracks the staleness and lifecycle state of endpoints and delivery logs.
Used by AgingService to escalate, archive, and purge records automatically.

Models:
    WebhookEndpointAging    — Lifecycle state per endpoint (last_active, age_tier, etc.)
    WebhookDeliveryAging    — Per-log aging metadata (age_bucket, archived_at, purge_after)
    WebhookAgingPolicy      — Owner-configurable retention policy
    WebhookAgingEvent       — Audit trail of every aging state transition
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  CHOICES
# ─────────────────────────────────────────────────────────────────────────────

class AgeTier(models.TextChoices):
    FRESH    = "fresh",    _("Fresh")          # < 7 days inactive
    WARM     = "warm",     _("Warm")           # 7–30 days inactive
    COOLING  = "cooling",  _("Cooling")        # 30–90 days inactive
    STALE    = "stale",    _("Stale")          # 90–180 days inactive
    DORMANT  = "dormant",  _("Dormant")        # 180+ days inactive
    ARCHIVED = "archived", _("Archived")       # moved to cold storage
    PURGED   = "purged",   _("Purged")         # permanently deleted marker


class AgingEventType(models.TextChoices):
    TIER_CHANGE    = "tier_change",    _("Tier Changed")
    ARCHIVED       = "archived",       _("Archived")
    PURGED         = "purged",         _("Purged")
    RESUMED        = "resumed",        _("Resumed / Reactivated")
    POLICY_APPLIED = "policy_applied", _("Policy Applied")
    NOTIFICATION   = "notification",   _("Notification Sent")


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK AGING POLICY
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingPolicy(models.Model):
    """
    Ainul Enterprise Engine — Owner-configurable log and endpoint retention policy.

    Defines at what age (days) logs move between tiers, get archived, and get purged.
    A default global policy (owner=None) is used when no owner-level policy exists.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="webhook_aging_policy",
        null=True,
        blank=True,
        verbose_name=_("Owner"),
        help_text=_("Null = global default policy."),
    )

    # ── Log retention thresholds ───────────────────────────────────────────────
    log_warm_after_days    = models.PositiveSmallIntegerField(default=7,   validators=[MinValueValidator(1), MaxValueValidator(365)])
    log_cooling_after_days = models.PositiveSmallIntegerField(default=30,  validators=[MinValueValidator(1), MaxValueValidator(365)])
    log_stale_after_days   = models.PositiveSmallIntegerField(default=90,  validators=[MinValueValidator(1), MaxValueValidator(1825)])
    log_archive_after_days = models.PositiveSmallIntegerField(default=180, validators=[MinValueValidator(1), MaxValueValidator(3650)])
    log_purge_after_days   = models.PositiveSmallIntegerField(default=365, validators=[MinValueValidator(1), MaxValueValidator(3650)])

    # ── Endpoint inactivity thresholds ────────────────────────────────────────
    endpoint_warm_after_days    = models.PositiveSmallIntegerField(default=7,   validators=[MinValueValidator(1)])
    endpoint_cooling_after_days = models.PositiveSmallIntegerField(default=30,  validators=[MinValueValidator(1)])
    endpoint_stale_after_days   = models.PositiveSmallIntegerField(default=90,  validators=[MinValueValidator(1)])
    endpoint_dormant_after_days = models.PositiveSmallIntegerField(default=180, validators=[MinValueValidator(1)])

    # ── Notifications ─────────────────────────────────────────────────────────
    notify_on_stale     = models.BooleanField(default=True)
    notify_on_dormant   = models.BooleanField(default=True)
    notify_on_archive   = models.BooleanField(default=True)
    notify_before_purge = models.BooleanField(default=True)
    purge_warning_days  = models.PositiveSmallIntegerField(
        default=7,
        help_text=_("Days before purge to send warning notification."),
    )

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "webhook_aging_policies"
        verbose_name        = _("Webhook Aging Policy")
        verbose_name_plural = _("Webhook Aging Policies")
        constraints = [
            # FIX: promoting the existing MinValueValidator/MaxValueValidator
            # field validators to real DB-level constraints. These were never
            # actually enforced for writes outside a DRF serializer (nothing
            # here calls full_clean()/clean_fields() - clean() above is
            # wired to save(), but clean() itself doesn't run field
            # validators, only its own explicit business-rule checks).
            models.CheckConstraint(check=models.Q(log_warm_after_days__gte=1) & models.Q(log_warm_after_days__lte=365),
                name="wap_log_warm_range",
            ),
            models.CheckConstraint(check=models.Q(log_cooling_after_days__gte=1) & models.Q(log_cooling_after_days__lte=365),
                name="wap_log_cooling_range",
            ),
            models.CheckConstraint(check=models.Q(log_stale_after_days__gte=1) & models.Q(log_stale_after_days__lte=1825),
                name="wap_log_stale_range",
            ),
            models.CheckConstraint(check=models.Q(log_archive_after_days__gte=1) & models.Q(log_archive_after_days__lte=3650),
                name="wap_log_archive_range",
            ),
            models.CheckConstraint(check=models.Q(log_purge_after_days__gte=1) & models.Q(log_purge_after_days__lte=3650),
                name="wap_log_purge_range",
            ),
            models.CheckConstraint(check=models.Q(endpoint_warm_after_days__gte=1),
                name="wap_endpoint_warm_gte_1",
            ),
            models.CheckConstraint(check=models.Q(endpoint_cooling_after_days__gte=1),
                name="wap_endpoint_cooling_gte_1",
            ),
            models.CheckConstraint(check=models.Q(endpoint_stale_after_days__gte=1),
                name="wap_endpoint_stale_gte_1",
            ),
            models.CheckConstraint(check=models.Q(endpoint_dormant_after_days__gte=1),
                name="wap_endpoint_dormant_gte_1",
            ),
        ]

    def __str__(self):
        owner_label = self.owner.email if self.owner_id else "Global Default"
        return f"AgingPolicy [{owner_label}]"

    def clean(self):
        super().clean()
        thresholds = [
            ("log_warm_after_days",    self.log_warm_after_days),
            ("log_cooling_after_days", self.log_cooling_after_days),
            ("log_stale_after_days",   self.log_stale_after_days),
            ("log_archive_after_days", self.log_archive_after_days),
            ("log_purge_after_days",   self.log_purge_after_days),
        ]
        for i in range(1, len(thresholds)):
            prev_name, prev_val = thresholds[i - 1]
            curr_name, curr_val = thresholds[i]
            if curr_val <= prev_val:
                raise ValidationError(
                    f"{curr_name} ({curr_val}) must be greater than {prev_name} ({prev_val})."
                )

    # FIX: clean() above was defined but never called (same gap fixed
    # across models/core.py and models/advanced.py in this pass). Wired
    # in the same way: create/full-save only, narrow update_fields saves
    # skipped. Verified safe for creation specifically: this model's own
    # field defaults (7/30/90/180/365 days) already satisfy the strict
    # ordering clean() checks, so this can't reject a normal
    # WebhookAgingPolicy.objects.create() with no args.
    def save(self, *args, **kwargs):
        if self.pk is None or not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_for_owner(cls, owner):
        """Return owner policy if one exists, else the global default."""
        try:
            return cls.objects.get(owner=owner, is_active=True)
        except cls.DoesNotExist:
            return cls.objects.filter(owner__isnull=True, is_active=True).first()


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK ENDPOINT AGING
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointAging(models.Model):
    """
    Ainul Enterprise Engine — Lifecycle aging record per endpoint.

    One row per endpoint, updated by AgingService on every sweep.
    Records the current age tier, inactivity duration, and whether
    the endpoint has been notified about staleness.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    endpoint = models.OneToOneField(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="aging",
        verbose_name=_("Endpoint"),
    )

    tier = models.CharField(
        max_length=20,
        choices=AgeTier.choices,
        default=AgeTier.FRESH,
        db_index=True,
        verbose_name=_("Age Tier"),
    )
    previous_tier = models.CharField(
        max_length=20,
        choices=AgeTier.choices,
        blank=True,
        default="",
        verbose_name=_("Previous Tier"),
    )

    # ── Activity tracking ─────────────────────────────────────────────────────
    last_delivery_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Delivery At"))
    days_inactive      = models.PositiveIntegerField(default=0, verbose_name=_("Days Inactive"))
    total_deliveries   = models.PositiveIntegerField(default=0)
    failed_deliveries  = models.PositiveIntegerField(default=0)

    # ── Notification flags ────────────────────────────────────────────────────
    stale_notified_at   = models.DateTimeField(null=True, blank=True)
    dormant_notified_at = models.DateTimeField(null=True, blank=True)
    purge_warned_at     = models.DateTimeField(null=True, blank=True)

    # ── Archive / Purge scheduling ────────────────────────────────────────────
    archive_after  = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Archive After"))
    purge_after    = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Purge After"))
    archived_at    = models.DateTimeField(null=True, blank=True)
    purged_at      = models.DateTimeField(null=True, blank=True)
    is_archived    = models.BooleanField(default=False, db_index=True)
    is_purged      = models.BooleanField(default=False, db_index=True)

    last_evaluated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Evaluated At"))
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "webhook_endpoint_aging"
        verbose_name        = _("Endpoint Aging Record")
        verbose_name_plural = _("Endpoint Aging Records")
        indexes = [
            models.Index(fields=["tier"],         name="idx_ea_tier"),
            models.Index(fields=["days_inactive"], name="idx_ea_days_inactive"),
            models.Index(fields=["archive_after"], name="idx_ea_archive_after"),
            models.Index(fields=["purge_after"],   name="idx_ea_purge_after"),
        ]

    def __str__(self):
        return f"[{self.tier.upper()}] {self.endpoint.label} — {self.days_inactive}d inactive"

    @property
    def is_stale(self) -> bool:
        return self.tier in (AgeTier.STALE, AgeTier.DORMANT, AgeTier.ARCHIVED)

    @property
    def needs_purge_warning(self) -> bool:
        if not self.purge_after or self.purge_warned_at:
            return False
        warning_window = self.purge_after - timedelta(days=7)
        return timezone.now() >= warning_window

    def compute_days_inactive(self) -> int:
        ref = self.last_delivery_at or self.endpoint.created_at
        return (timezone.now() - ref).days

    def compute_tier(self, policy: "WebhookAgingPolicy") -> str:
        d = self.days_inactive
        if d >= policy.endpoint_dormant_after_days:
            return AgeTier.DORMANT
        if d >= policy.endpoint_stale_after_days:
            return AgeTier.STALE
        if d >= policy.endpoint_cooling_after_days:
            return AgeTier.COOLING
        if d >= policy.endpoint_warm_after_days:
            return AgeTier.WARM
        return AgeTier.FRESH


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK DELIVERY AGING
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryAging(models.Model):
    """
    Ainul Enterprise Engine — Aging metadata for a delivery log entry.

    Tracks which retention bucket a log belongs to, and when it
    should be archived or purged according to the owner's AgingPolicy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    delivery_log = models.OneToOneField(
        "WebhookDeliveryLog",
        on_delete=models.CASCADE,
        related_name="aging",
        verbose_name=_("Delivery Log"),
    )

    bucket = models.CharField(
        max_length=20,
        choices=AgeTier.choices,
        default=AgeTier.FRESH,
        db_index=True,
        verbose_name=_("Age Bucket"),
    )

    age_days       = models.PositiveIntegerField(default=0, verbose_name=_("Age in Days"))
    archive_after  = models.DateTimeField(null=True, blank=True, db_index=True)
    purge_after    = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_at    = models.DateTimeField(null=True, blank=True)
    purged_at      = models.DateTimeField(null=True, blank=True)
    is_archived    = models.BooleanField(default=False, db_index=True)
    is_purged      = models.BooleanField(default=False, db_index=True)

    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "webhook_delivery_aging"
        verbose_name        = _("Delivery Aging Record")
        verbose_name_plural = _("Delivery Aging Records")
        indexes = [
            models.Index(fields=["bucket"],       name="idx_da_bucket"),
            models.Index(fields=["archive_after"], name="idx_da_archive_after"),
            models.Index(fields=["purge_after"],   name="idx_da_purge_after"),
            models.Index(fields=["is_archived"],   name="idx_da_is_archived"),
            models.Index(fields=["is_purged"],     name="idx_da_is_purged"),
        ]

    def __str__(self):
        return f"[{self.bucket.upper()}] DeliveryLog {self.delivery_log_id} — {self.age_days}d old"


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK AGING EVENT  (audit trail)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAgingEvent(models.Model):
    """
    Ainul Enterprise Engine — Immutable audit trail of every aging transition.

    Records every tier change, archive, purge, and notification event
    so operators can audit why a record was escalated or deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    event_type = models.CharField(
        max_length=30,
        choices=AgingEventType.choices,
        db_index=True,
        verbose_name=_("Event Type"),
    )

    # ── Subject — one of these will be set ────────────────────────────────────
    endpoint_aging = models.ForeignKey(
        WebhookEndpointAging,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="events",
        verbose_name=_("Endpoint Aging"),
    )
    delivery_aging = models.ForeignKey(
        WebhookDeliveryAging,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="events",
        verbose_name=_("Delivery Aging"),
    )

    # ── Transition detail ─────────────────────────────────────────────────────
    from_tier  = models.CharField(max_length=20, blank=True, default="")
    to_tier    = models.CharField(max_length=20, blank=True, default="")
    detail     = models.JSONField(default=dict, blank=True)
    triggered_by = models.CharField(
        max_length=50,
        default="aging_service",
        verbose_name=_("Triggered By"),
    )

    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table            = "webhook_aging_events"
        verbose_name        = _("Aging Event")
        verbose_name_plural = _("Aging Events")
        ordering            = ["-occurred_at"]
        indexes = [
            models.Index(fields=["event_type"],  name="idx_ae_event_type"),
            models.Index(fields=["occurred_at"], name="idx_ae_occurred_at"),
        ]

    def __str__(self):
        subject = (
            f"Endpoint:{self.endpoint_aging_id}"
            if self.endpoint_aging_id
            else f"Delivery:{self.delivery_aging_id}"
        )
        return f"[{self.event_type}] {subject} {self.from_tier}→{self.to_tier}"
