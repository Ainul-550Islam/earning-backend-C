# =============================================================================
# behavior_analytics/models.py
# =============================================================================
"""
ORM models for the behavior_analytics application.

Design decisions:
  - UUIDField as primary key on every model → globally unique, no enumeration.
  - All timestamps use auto_now / auto_now_add; never set manually.
  - DecimalField for scores — never float (precision matters for aggregation).
  - JSONField with a strict default factory, never None.
  - __str__ always returns a human-readable string.
  - Meta defines indexes on every FK and on common filter/order fields.
  - clean() enforces domain invariants at the model layer (not just serializers).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from .choices import (
    ClickCategory,
    DeviceType,
    EngagementTier,
    PathNodeType,
    SessionStatus,
)
from .constants import (
    ENGAGEMENT_SCORE_MAX,
    ENGAGEMENT_SCORE_MIN,
    MAX_CLICK_METRICS_PER_SESSION,
    MAX_PATH_NODES,
    MAX_URL_LENGTH,
    STAY_TIME_BOUNCE_THRESHOLD,
    STAY_TIME_MAX_SECONDS,
    STAY_TIME_MIN_SECONDS,
)
from .exceptions import (
    InvalidEngagementScoreError,
    InvalidPathDataError,
    StayTimeOutOfRangeError,
)
from .managers import (
    ClickMetricManager,
    EngagementScoreManager,
    StayTimeManager,
    UserPathManager,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------

class TimeStampedUUIDModel(models.Model):
    """
    Abstract base giving every concrete model:
      - UUID PK (non-sequential, safe for public exposure)
      - created_at / updated_at auto-timestamps
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )


    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:  # always safe repr
        return f"<{self.__class__.__name__} pk={self.pk}>"


# ---------------------------------------------------------------------------
# UserPath
# ---------------------------------------------------------------------------

class UserPath(TimeStampedUUIDModel):
    """
    Records the ordered sequence of pages / screens a user visited in a
    single session.  The path is stored as a JSON list of node dicts:

        [
          {"url": "/home/", "type": "entry", "ts": 1710000000},
          {"url": "/product/42/", "type": "navigation", "ts": 1710000030},
          ...
        ]

    Constraints:
      - nodes list may not exceed MAX_PATH_NODES entries.
      - session_id is unique per user-session combination.
    """

    user       = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="analytics_paths",
        db_index=True,
        verbose_name=_("User"),
    )
    session_id = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name=_("Session ID"),
        help_text=_("Frontend-generated session identifier (UUID v4 recommended)."),
    )
    nodes = models.JSONField(
        default=list,
        verbose_name=_("Path Nodes"),
        help_text=_("Ordered list of navigation node objects."),
    )
    device_type = models.CharField(
        max_length=16,
        choices=DeviceType.choices,
        default=DeviceType.UNKNOWN,
        verbose_name=_("Device Type"),
    )
    status = models.CharField(
        max_length=16,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Session Status"),
    )
    entry_url = models.URLField(
        max_length=MAX_URL_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Entry URL"),
    )
    exit_url = models.URLField(
        max_length=MAX_URL_LENGTH,
        blank=True,
        default="",
        verbose_name=_("Exit URL"),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        protocol="both",
        unpack_ipv4=True,
        verbose_name=_("IP Address"),
    )
    user_agent = models.TextField(blank=True, default="", verbose_name=_("User Agent"))

    objects = UserPathManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("User Path")
        verbose_name_plural = _("User Paths")
        indexes = [
            models.Index(fields=["user", "session_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["device_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "session_id"],
                name="unique_user_session_path",
            ),
        ]

    def __str__(self) -> str:
        return f"Path[{self.session_id[:8]}] – {self.user} ({self.status})"

    # ------------------------------------------------------------------
    # Domain validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.nodes, list):
            raise InvalidPathDataError(
                _("nodes must be a JSON list, got %(t)s.") % {"t": type(self.nodes).__name__}
            )
        if len(self.nodes) > MAX_PATH_NODES:
            raise InvalidPathDataError(
                _(
                    "Path exceeds maximum node count (%(max)d). Got %(got)d."
                ) % {"max": MAX_PATH_NODES, "got": len(self.nodes)}
            )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def depth(self) -> int:
        """Number of distinct URLs visited."""
        return len({n.get("url", "") for n in self.nodes if isinstance(n, dict)})

    @property
    def is_bounce(self) -> bool:
        """True when the session lasted fewer than STAY_TIME_BOUNCE_THRESHOLD seconds."""
        return len(self.nodes) <= 1

    def add_node(
        self,
        *,
        url: str,
        node_type: str = PathNodeType.NAVIGATION,
        ts: int | None = None,
    ) -> None:
        """
        Append a navigation node to this path (in-memory).
        Caller must call .save() afterwards.

        Raises InvalidPathDataError when the limit would be exceeded.
        """
        if len(self.nodes) >= MAX_PATH_NODES:
            raise InvalidPathDataError(
                _("Cannot add node: path is already at the maximum limit (%d).") % MAX_PATH_NODES
            )
        import time as _time
        self.nodes.append(
            {
                "url":  url[:MAX_URL_LENGTH],
                "type": node_type,
                "ts":   ts if ts is not None else int(_time.time()),
            }
        )


# ---------------------------------------------------------------------------
# ClickMetric
# ---------------------------------------------------------------------------

class ClickMetric(TimeStampedUUIDModel):
    """
    Stores individual click / interaction events tied to a session path.

    One UserPath may have up to MAX_CLICK_METRICS_PER_SESSION rows.
    Enforced at the service layer (not DB — to avoid expensive count queries
    on every insert; a periodic cleanup task handles excess).
    """

    path = models.ForeignKey(
        UserPath,
        on_delete=models.CASCADE,
        related_name="click_metrics",
        db_index=True,
        verbose_name=_("User Path"),
    )
    page_url = models.URLField(
        max_length=MAX_URL_LENGTH,
        verbose_name=_("Page URL"),
        help_text=_("The page where the click occurred."),
    )
    element_selector = models.CharField(
        max_length=512,
        blank=True,
        default="",
        verbose_name=_("CSS Selector"),
        help_text=_("CSS selector of the clicked element."),
    )
    element_text = models.CharField(
        max_length=256,
        blank=True,
        default="",
        verbose_name=_("Element Text"),
    )
    category = models.CharField(
        max_length=16,
        choices=ClickCategory.choices,
        default=ClickCategory.OTHER,
        db_index=True,
        verbose_name=_("Click Category"),
    )
    x_position = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("X Position (px)")
    )
    y_position = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Y Position (px)")
    )
    viewport_width  = models.PositiveSmallIntegerField(null=True, blank=True)
    viewport_height = models.PositiveSmallIntegerField(null=True, blank=True)
    clicked_at = models.DateTimeField(
        db_index=True,
        verbose_name=_("Clicked At"),
        help_text=_("Client-side timestamp of the click event."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Extra Metadata"),
    )

    objects = ClickMetricManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Click Metric")
        verbose_name_plural = _("Click Metrics")
        indexes = [
            models.Index(fields=["path", "clicked_at"]),
            models.Index(fields=["category", "clicked_at"]),
            models.Index(fields=["page_url"]),
        ]

    def __str__(self) -> str:
        return f"Click[{self.category}] on {self.page_url[:60]} @ {self.clicked_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# StayTime
# ---------------------------------------------------------------------------

class StayTime(TimeStampedUUIDModel):
    """
    Records how long a user remained on a specific page within a session.

    duration_seconds is always positive and bounded by domain constants.
    """

    path = models.ForeignKey(
        UserPath,
        on_delete=models.CASCADE,
        related_name="stay_times",
        db_index=True,
        verbose_name=_("User Path"),
    )
    page_url = models.URLField(
        max_length=MAX_URL_LENGTH,
        verbose_name=_("Page URL"),
    )
    duration_seconds = models.PositiveIntegerField(
        validators=[
            MinValueValidator(STAY_TIME_MIN_SECONDS),
            MaxValueValidator(STAY_TIME_MAX_SECONDS),
        ],
        verbose_name=_("Duration (seconds)"),
    )
    is_active_time = models.BooleanField(
        default=True,
        verbose_name=_("Is Active Time?"),
        help_text=_("False when the tab was hidden/backgrounded for most of the duration."),
    )
    scroll_depth_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(100)],
        verbose_name=_("Scroll Depth (%)"),
    )

    objects = StayTimeManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Stay Time")
        verbose_name_plural = _("Stay Times")
        indexes = [
            models.Index(fields=["path", "created_at"]),
            models.Index(fields=["page_url"]),
            models.Index(fields=["duration_seconds"]),
        ]

    def __str__(self) -> str:
        return (
            f"StayTime {self.duration_seconds}s on {self.page_url[:60]}"
        )

    def clean(self) -> None:
        super().clean()
        if not (STAY_TIME_MIN_SECONDS <= self.duration_seconds <= STAY_TIME_MAX_SECONDS):
            raise StayTimeOutOfRangeError(
                _(
                    "duration_seconds must be between %(min)d and %(max)d."
                ) % {
                    "min": STAY_TIME_MIN_SECONDS,
                    "max": STAY_TIME_MAX_SECONDS,
                }
            )

    @property
    def is_bounce(self) -> bool:
        return self.duration_seconds < STAY_TIME_BOUNCE_THRESHOLD


# ---------------------------------------------------------------------------
# EngagementScore
# ---------------------------------------------------------------------------

class EngagementScore(TimeStampedUUIDModel):
    """
    Stores the computed engagement score for a user per calendar date.

    One row per (user, date) — enforced by a unique constraint.
    The score is a Decimal in [0, 100] with 2 dp.
    Component breakdown is stored in breakdown_json for auditability.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="engagement_scores",
        db_index=True,
        verbose_name=_("User"),
    )
    date = models.DateField(db_index=True, verbose_name=_("Date"))
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal(str(ENGAGEMENT_SCORE_MIN))),
            MaxValueValidator(Decimal(str(ENGAGEMENT_SCORE_MAX))),
        ],
        verbose_name=_("Engagement Score"),
    )
    tier = models.CharField(
        max_length=8,
        choices=EngagementTier.choices,
        default=EngagementTier.LOW,
        db_index=True,
        verbose_name=_("Engagement Tier"),
    )
    # Raw component values used in the score formula
    click_count    = models.PositiveIntegerField(default=0, verbose_name=_("Click Count"))
    total_stay_sec = models.PositiveIntegerField(default=0, verbose_name=_("Total Stay (s)"))
    path_depth     = models.PositiveSmallIntegerField(default=0, verbose_name=_("Path Depth"))
    return_visits  = models.PositiveSmallIntegerField(default=0, verbose_name=_("Return Visits"))
    breakdown_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Score Breakdown"),
        help_text=_("Per-component weighted contribution to the final score."),
    )

    objects = EngagementScoreManager()

    class Meta(TimeStampedUUIDModel.Meta):
        verbose_name        = _("Engagement Score")
        verbose_name_plural = _("Engagement Scores")
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["tier", "date"]),
            models.Index(fields=["score"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="unique_user_daily_engagement",
            ),
        ]

    def __str__(self) -> str:
        return f"Score({self.score}/{ENGAGEMENT_SCORE_MAX}) – {self.user} [{self.date}]"

    def clean(self) -> None:
        super().clean()
        score_val = Decimal(str(self.score)) if not isinstance(self.score, Decimal) else self.score
        if not (Decimal(str(ENGAGEMENT_SCORE_MIN)) <= score_val <= Decimal(str(ENGAGEMENT_SCORE_MAX))):
            raise InvalidEngagementScoreError(
                _(
                    "Score %(s)s is out of range [%(min)d, %(max)d]."
                ) % {
                    "s":   score_val,
                    "min": ENGAGEMENT_SCORE_MIN,
                    "max": ENGAGEMENT_SCORE_MAX,
                }
            )

    def get_tier_display_verbose(self) -> str:
        """Return a full human-readable tier label."""
        return EngagementTier(self.tier).label
