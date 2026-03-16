"""
Gamification Models - ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
Bulletproof / Defensive Coding with full validation, constraints, and audit fields.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Optional, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q, F, CheckConstraint, UniqueConstraint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .choices import (
    ContestCycleStatus,
    RewardType,
    AchievementType,
    LeaderboardScope,
    SnapshotStatus,
)
from .constants import (
    MAX_CONTEST_NAME_LENGTH,
    MAX_REWARD_TITLE_LENGTH,
    MAX_ACHIEVEMENT_TITLE_LENGTH,
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    MAX_DESCRIPTION_LENGTH,
    MAX_META_JSON_SIZE_BYTES,
    DEFAULT_LEADERBOARD_TOP_N,
)
from .exceptions import (
    ContestCycleStateError,
    InvalidPointsError,
    DuplicateAchievementError,
    RewardAlreadyClaimedError,
)
from .managers import (
    ContestCycleManager,
    LeaderboardSnapshotManager,
    ContestRewardManager,
    UserAchievementManager,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------

class TimestampedModel(models.Model):
    """
    Abstract base providing created_at / updated_at audit timestamps
    and a UUID primary key for all gamification models.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
        help_text=_("Universally unique identifier for this record."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
        help_text=_("Timestamp when this record was first created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("Timestamp when this record was last modified."),
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} id={self.id}>"


# ---------------------------------------------------------------------------
# ContestCycle
# ---------------------------------------------------------------------------

class ContestCycle(TimestampedModel):
    """
    Represents a bounded contest period (e.g. weekly, monthly leaderboard season).

    A ContestCycle must always move forward through a defined state machine:
        DRAFT → ACTIVE → COMPLETED → ARCHIVED
    Transitions that skip or reverse states are rejected at the model level.

    Business rules enforced here (not just in the service layer):
    - start_date must be strictly before end_date.
    - Only one ContestCycle may be ACTIVE at a time (enforced via DB constraint
      and model-level validation).
    - Points multiplier must be a positive, finite decimal.
    """

    VALID_TRANSITIONS: dict[str, list[str]] = {
        ContestCycleStatus.DRAFT: [ContestCycleStatus.ACTIVE],
        ContestCycleStatus.ACTIVE: [ContestCycleStatus.COMPLETED],
        ContestCycleStatus.COMPLETED: [ContestCycleStatus.ARCHIVED],
        ContestCycleStatus.ARCHIVED: [],  # terminal state
    }

    name = models.CharField(
        max_length=MAX_CONTEST_NAME_LENGTH,
        unique=True,
        verbose_name=_("Contest Name"),
        help_text=_("Human-readable unique name for this contest cycle."),
    )
    slug = models.SlugField(
        max_length=MAX_CONTEST_NAME_LENGTH,
        unique=True,
        db_index=True,
        verbose_name=_("Slug"),
        help_text=_("URL-safe identifier derived from the contest name."),
    )
    description = models.TextField(
        blank=True,
        default="",
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
        help_text=_("Optional contest description shown to participants."),
    )
    status = models.CharField(
        max_length=20,
        choices=ContestCycleStatus.choices,
        default=ContestCycleStatus.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Lifecycle state of the contest cycle."),
    )
    start_date = models.DateTimeField(
        verbose_name=_("Start Date"),
        help_text=_("Inclusive start of the contest window (UTC)."),
    )
    end_date = models.DateTimeField(
        verbose_name=_("End Date"),
        help_text=_("Exclusive end of the contest window (UTC)."),
    )
    points_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100.00"))],
        verbose_name=_("Points Multiplier"),
        help_text=_(
            "All points earned during this cycle are multiplied by this factor. "
            "Must be between 0.01 and 100.00."
        ),
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Is Featured"),
        help_text=_("Featured cycles are prominently displayed in the UI."),
    )
    max_participants = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Participants"),
        help_text=_("Optional hard cap on participant count. NULL = unlimited."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_(
            "Arbitrary JSON configuration for this cycle (e.g. reward tiers, "
            "eligibility rules). Must not exceed %(size)s bytes."
        ) % {"size": MAX_META_JSON_SIZE_BYTES},
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_contest_cycles",
        verbose_name=_("Created By"),
        help_text=_("Staff user who created this contest cycle."),
    )

    objects: ContestCycleManager = ContestCycleManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Contest Cycle")
        verbose_name_plural = _("Contest Cycles")
        indexes = [
            models.Index(fields=["status", "start_date"], name="gamif_cc_status_start_idx"),
            models.Index(fields=["start_date", "end_date"], name="gamif_cc_date_range_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=Q(start_date__lt=F("end_date")),
                name="gamif_cc_start_before_end",
            ),
            CheckConstraint(
                check=Q(points_multiplier__gt=Decimal("0")),
                name="gamif_cc_positive_multiplier",
            ),
        ]

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.name} [{self.get_status_display()}]"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True only when status is ACTIVE and the current time is within the window."""
        if self.status != ContestCycleStatus.ACTIVE:
            return False
        now = timezone.now()
        return self.start_date <= now < self.end_date

    @property
    def is_expired(self) -> bool:
        """True when the contest window has passed, regardless of status."""
        return timezone.now() >= self.end_date

    @property
    def duration_days(self) -> Optional[int]:
        """Duration in whole days; None if dates are not set."""
        if not self.start_date or not self.end_date:
            return None
        delta = self.end_date - self.start_date
        return delta.days

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        """
        Model-level validation called by full_clean() and Django admin.
        Service layer must also call full_clean() before save().
        """
        errors: dict[str, list] = {}

        # Date ordering
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors.setdefault("end_date", []).append(
                    _("end_date must be strictly after start_date.")
                )

        # Points multiplier sanity (belt-and-suspenders beyond field validators)
        if self.points_multiplier is not None:
            try:
                multiplier = Decimal(str(self.points_multiplier))
                if multiplier <= 0:
                    errors.setdefault("points_multiplier", []).append(
                        _("points_multiplier must be a positive value.")
                    )
            except (InvalidOperation, TypeError, ValueError):
                errors.setdefault("points_multiplier", []).append(
                    _("points_multiplier must be a valid decimal number.")
                )

        # Only one ACTIVE cycle allowed at a time
        if self.status == ContestCycleStatus.ACTIVE:
            qs = ContestCycle.objects.filter(status=ContestCycleStatus.ACTIVE)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors.setdefault("status", []).append(
                    _("Another ContestCycle is already ACTIVE. "
                      "Complete it before activating a new one.")
                )

        # Metadata size guard
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata JSON exceeds maximum allowed size of "
                          f"{MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Metadata is not serialisable JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        """
        Always run full_clean before persisting to catch constraint violations
        early and produce developer-friendly error messages.
        """
        self.full_clean()
        super().save(*args, **kwargs)
        logger.debug(
            "ContestCycle saved: id=%s name=%s status=%s",
            self.id,
            self.name,
            self.status,
        )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition_to(self, new_status: str, *, actor: Optional["AbstractBaseUser"] = None) -> None:
        """
        Advance the contest cycle to *new_status* via the defined state machine.

        Args:
            new_status: One of ContestCycleStatus values.
            actor: Optional user performing the transition (for audit logging).

        Raises:
            ContestCycleStateError: If the transition is not permitted.
            ValidationError: If the resulting state fails model validation.
        """
        if new_status not in ContestCycleStatus.values:
            raise ContestCycleStateError(
                f"Unknown status '{new_status}'. "
                f"Valid choices: {ContestCycleStatus.values}"
            )

        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ContestCycleStateError(
                f"Cannot transition ContestCycle from '{self.status}' to '{new_status}'. "
                f"Allowed next states: {allowed}"
            )

        old_status = self.status
        self.status = new_status

        with transaction.atomic():
            self.save(update_fields=["status", "updated_at"])

        logger.info(
            "ContestCycle %s transitioned: %s → %s (actor=%s)",
            self.id,
            old_status,
            new_status,
            getattr(actor, "pk", "system"),
        )


# ---------------------------------------------------------------------------
# LeaderboardSnapshot
# ---------------------------------------------------------------------------

class LeaderboardSnapshot(TimestampedModel):
    """
    A point-in-time snapshot of the leaderboard for a given ContestCycle.

    Snapshots are immutable once they reach FINALIZED status. The raw ranking
    data is stored in `snapshot_data` as a JSON array ordered by rank.

    Each entry in `snapshot_data` should conform to:
    {
        "rank": <int>,
        "user_id": <str>,
        "display_name": <str>,
        "points": <int>,
        "delta_rank": <int | null>   // rank change since previous snapshot
    }
    """

    contest_cycle = models.ForeignKey(
        ContestCycle,
        on_delete=models.PROTECT,
        related_name="leaderboard_snapshots",
        verbose_name=_("Contest Cycle"),
        help_text=_("The contest cycle this snapshot belongs to."),
    )
    scope = models.CharField(
        max_length=20,
        choices=LeaderboardScope.choices,
        default=LeaderboardScope.GLOBAL,
        db_index=True,
        verbose_name=_("Scope"),
        help_text=_(
            "GLOBAL = all participants; REGIONAL / CATEGORY may be added via scope_ref."
        ),
    )
    scope_ref = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Scope Reference"),
        help_text=_(
            "Optional identifier qualifying the scope "
            "(e.g. region code, category slug)."
        ),
    )
    snapshot_data = models.JSONField(
        default=list,
        verbose_name=_("Snapshot Data"),
        help_text=_(
            "Ordered list of leaderboard entries at snapshot time. "
            "See model docstring for entry schema."
        ),
    )
    top_n = models.PositiveSmallIntegerField(
        default=DEFAULT_LEADERBOARD_TOP_N,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name=_("Top N"),
        help_text=_("Number of top entries captured in this snapshot."),
    )
    status = models.CharField(
        max_length=20,
        choices=SnapshotStatus.choices,
        default=SnapshotStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_(
            "PENDING = being built; FINALIZED = immutable; FAILED = error during generation."
        ),
    )
    generated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Generated At"),
        help_text=_("Timestamp when this snapshot was successfully finalized."),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
        help_text=_("Populated when status=FAILED; contains traceback or summary."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_(
            "SHA-256 hex digest of the serialized snapshot_data. "
            "Used for integrity verification."
        ),
    )

    objects: LeaderboardSnapshotManager = LeaderboardSnapshotManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Leaderboard Snapshot")
        verbose_name_plural = _("Leaderboard Snapshots")
        indexes = [
            models.Index(
                fields=["contest_cycle", "scope", "created_at"],
                name="gamif_ls_cyc_scope_crt_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="gamif_ls_status_created_idx",
            ),
        ]

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return (
            f"Snapshot [{self.scope}] for '{self.contest_cycle_id}' "
            f"@ {self.created_at:%Y-%m-%d %H:%M} ({self.get_status_display()})"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        return self.status == SnapshotStatus.FINALIZED

    @property
    def entry_count(self) -> int:
        """Number of ranked entries in snapshot_data."""
        if not isinstance(self.snapshot_data, list):
            return 0
        return len(self.snapshot_data)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # snapshot_data must be a list
        if self.snapshot_data is not None and not isinstance(self.snapshot_data, list):
            errors.setdefault("snapshot_data", []).append(
                _("snapshot_data must be a JSON array.")
            )
        elif isinstance(self.snapshot_data, list):
            for idx, entry in enumerate(self.snapshot_data):
                if not isinstance(entry, dict):
                    errors.setdefault("snapshot_data", []).append(
                        _(f"Entry at index {idx} must be a JSON object.")
                    )
                    continue
                for required_key in ("rank", "user_id", "points"):
                    if required_key not in entry:
                        errors.setdefault("snapshot_data", []).append(
                            _(f"Entry at index {idx} is missing required key '{required_key}'.")
                        )

        # Finalized snapshots must have generated_at populated
        if self.status == SnapshotStatus.FINALIZED and not self.generated_at:
            errors.setdefault("generated_at", []).append(
                _("generated_at must be set when status is FINALIZED.")
            )

        # Immutability guard: once FINALIZED, critical fields cannot change
        if self.pk:
            try:
                original = LeaderboardSnapshot.objects.get(pk=self.pk)
                if original.status == SnapshotStatus.FINALIZED:
                    immutable_fields = ("snapshot_data", "contest_cycle_id", "scope")
                    for field in immutable_fields:
                        if getattr(original, field) != getattr(self, field):
                            errors.setdefault(field, []).append(
                                _(
                                    f"Field '{field}' cannot be changed on a FINALIZED snapshot."
                                )
                            )
            except LeaderboardSnapshot.DoesNotExist:
                pass  # New record; no immutability check needed

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """
        Mark this snapshot as FINALIZED and compute its integrity checksum.
        Idempotent if already finalized.

        Raises:
            ValidationError: If snapshot_data is empty or malformed.
        """
        import hashlib
        import json

        if self.is_finalized:
            logger.debug("LeaderboardSnapshot %s already finalized; skipping.", self.id)
            return

        if not self.snapshot_data:
            raise ValidationError(
                {"snapshot_data": [_("Cannot finalize a snapshot with no data.")]}
            )

        raw = json.dumps(self.snapshot_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.status = SnapshotStatus.FINALIZED
        self.generated_at = timezone.now()
        self.save(update_fields=["status", "generated_at", "checksum", "updated_at"])
        logger.info("LeaderboardSnapshot %s finalized; checksum=%s", self.id, self.checksum)

    def mark_failed(self, error: str) -> None:
        """
        Transition snapshot to FAILED status with an error message.

        Args:
            error: Human-readable description of the failure.
        """
        if not isinstance(error, str) or not error.strip():
            error = "Unknown error (no message provided)."
        self.status = SnapshotStatus.FAILED
        self.error_message = error[:4096]  # truncate to DB-safe length
        self.save(update_fields=["status", "error_message", "updated_at"])
        logger.error(
            "LeaderboardSnapshot %s marked FAILED: %s",
            self.id,
            self.error_message,
        )


# ---------------------------------------------------------------------------
# ContestReward
# ---------------------------------------------------------------------------

class ContestReward(TimestampedModel):
    """
    A reward that can be granted to users upon achieving a rank or milestone
    within a ContestCycle.

    Rewards are configured per-cycle and per-rank-threshold. A single reward
    record represents the *definition* of what is awarded; actual issuance is
    tracked via ``UserAchievement`` or an external fulfilment service.

    Design notes:
    - ``rank_from`` / ``rank_to`` define an inclusive rank window (1-based).
    - ``reward_value`` carries the monetary / point / coupon value depending
      on ``reward_type``.
    - ``total_budget`` optionally caps how many times this reward can be issued.
    """

    contest_cycle = models.ForeignKey(
        ContestCycle,
        on_delete=models.PROTECT,
        related_name="rewards",
        verbose_name=_("Contest Cycle"),
    )
    title = models.CharField(
        max_length=MAX_REWARD_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Short display title shown to the user (e.g. '1st Place Trophy')."),
    )
    description = models.TextField(
        blank=True,
        default="",
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
    )
    reward_type = models.CharField(
        max_length=30,
        choices=RewardType.choices,
        verbose_name=_("Reward Type"),
        help_text=_("Category of reward (POINTS, BADGE, COUPON, PHYSICAL, CUSTOM)."),
    )
    reward_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("Reward Value"),
        help_text=_(
            "Numeric value of the reward. Interpretation depends on reward_type "
            "(e.g. point amount, coupon discount percentage)."
        ),
    )
    rank_from = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_RANK_VALUE)],
        verbose_name=_("Rank From"),
        help_text=_("Inclusive lower bound of the rank window (1 = top)."),
    )
    rank_to = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_RANK_VALUE)],
        verbose_name=_("Rank To"),
        help_text=_("Inclusive upper bound of the rank window."),
    )
    total_budget = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Total Budget"),
        help_text=_(
            "Maximum number of times this reward can be issued. "
            "NULL = no cap (issue to all eligible participants)."
        ),
    )
    issued_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Issued Count"),
        help_text=_("Running total of how many times this reward has been issued."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Inactive rewards are not issued to new participants."),
    )
    image_url = models.URLField(
        blank=True,
        default="",
        max_length=500,
        verbose_name=_("Image URL"),
        help_text=_("Optional URL to a reward badge or trophy image."),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Arbitrary extra data for the reward (e.g. coupon code, SKU)."),
    )

    objects: ContestRewardManager = ContestRewardManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Contest Reward")
        verbose_name_plural = _("Contest Rewards")
        indexes = [
            models.Index(
                fields=["contest_cycle", "rank_from", "rank_to"],
                name="gamif_cr_cycle_rank_idx",
            ),
            models.Index(
                fields=["reward_type", "is_active"],
                name="gamif_cr_type_active_idx",
            ),
        ]
        constraints = [
            CheckConstraint(
                check=Q(rank_from__lte=F("rank_to")),
                name="gamif_cr_rank_from_lte_rank_to",
            ),
            CheckConstraint(
                check=Q(reward_value__gte=Decimal("0")),
                name="gamif_cr_non_negative_value",
            ),
            CheckConstraint(
                check=Q(issued_count__gte=0),
                name="gamif_cr_nn_issued_count",
            ),
        ]

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return (
            f"{self.title} [{self.get_reward_type_display()}] "
            f"(Rank {self.rank_from}–{self.rank_to})"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_exhausted(self) -> bool:
        """True when total_budget is set and fully consumed."""
        if self.total_budget is None:
            return False
        return self.issued_count >= self.total_budget

    @property
    def remaining_budget(self) -> Optional[int]:
        """Remaining issuance capacity; None if uncapped."""
        if self.total_budget is None:
            return None
        return max(0, self.total_budget - self.issued_count)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict[str, list] = {}

        if self.rank_from is not None and self.rank_to is not None:
            if self.rank_from > self.rank_to:
                errors.setdefault("rank_to", []).append(
                    _("rank_to must be greater than or equal to rank_from.")
                )

        if self.total_budget is not None and self.total_budget < 1:
            errors.setdefault("total_budget", []).append(
                _("total_budget must be at least 1 if specified.")
            )

        if self.issued_count and self.total_budget is not None:
            if self.issued_count > self.total_budget:
                errors.setdefault("issued_count", []).append(
                    _("issued_count cannot exceed total_budget.")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def increment_issued_count(self) -> None:
        """
        Atomically increment the issued_count using F() expression to avoid
        race conditions in concurrent environments.

        Raises:
            RewardAlreadyClaimedError: If the reward budget is exhausted.
        """
        if self.is_exhausted:
            raise RewardAlreadyClaimedError(
                f"ContestReward '{self.title}' (id={self.id}) budget is exhausted. "
                f"total_budget={self.total_budget}, issued_count={self.issued_count}."
            )

        with transaction.atomic():
            updated = ContestReward.objects.filter(pk=self.pk).update(
                issued_count=F("issued_count") + 1
            )
            if updated != 1:
                raise RewardAlreadyClaimedError(
                    f"Failed to increment issued_count for ContestReward id={self.id}. "
                    "Record may have been deleted concurrently."
                )
            # Refresh local state
            self.refresh_from_db(fields=["issued_count"])
            logger.debug(
                "ContestReward %s issued_count incremented to %s",
                self.id,
                self.issued_count,
            )

    def covers_rank(self, rank: int) -> bool:
        """Return True if *rank* falls within this reward's rank window."""
        if not isinstance(rank, int) or rank < 1:
            return False
        return self.rank_from <= rank <= self.rank_to


# ---------------------------------------------------------------------------
# UserAchievement
# ---------------------------------------------------------------------------

class UserAchievement(TimestampedModel):
    """
    Records an achievement (badge, milestone, rank reward) earned by a user,
    optionally within a specific ContestCycle.

    This model serves as the canonical ledger for all gamification outcomes.

    Uniqueness:
    - For CYCLE-scoped achievements: one record per (user, achievement_type, contest_cycle).
    - For GLOBAL achievements: one record per (user, achievement_type) where
      contest_cycle is NULL.
    This is enforced via DB-level partial unique indexes and model clean().

    Immutability:
    - Once ``is_awarded`` is True and ``awarded_at`` is set, the core award
      fields must not change.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="achievements",
        db_index=True,
        verbose_name=_("User"),
    )
    contest_cycle = models.ForeignKey(
        ContestCycle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="user_achievements",
        verbose_name=_("Contest Cycle"),
        help_text=_("NULL for global/lifetime achievements."),
    )
    contest_reward = models.ForeignKey(
        ContestReward,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="user_achievements",
        verbose_name=_("Contest Reward"),
        help_text=_("The reward template that triggered this achievement, if applicable."),
    )
    achievement_type = models.CharField(
        max_length=50,
        choices=AchievementType.choices,
        db_index=True,
        verbose_name=_("Achievement Type"),
        help_text=_("Semantic category of the achievement."),
    )
    title = models.CharField(
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Display title for the achievement (e.g. 'Top 10 Finisher')."),
    )
    description = models.TextField(
        blank=True,
        default="",
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
    )
    points_awarded = models.IntegerField(
        default=0,
        validators=[
            MinValueValidator(MIN_POINTS_VALUE),
            MaxValueValidator(MAX_POINTS_VALUE),
        ],
        verbose_name=_("Points Awarded"),
        help_text=_(
            "Points credited to the user's account for this achievement. "
            "May be 0 for badge-only achievements."
        ),
    )
    rank_at_award = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_RANK_VALUE)],
        verbose_name=_("Rank at Award"),
        help_text=_("User's leaderboard rank at the time of award, if applicable."),
    )
    is_awarded = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Awarded"),
        help_text=_(
            "True once the achievement has been formally granted and any associated "
            "points/rewards have been dispatched."
        ),
    )
    awarded_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Awarded At"),
        help_text=_("Timestamp when is_awarded was set to True."),
    )
    is_notified = models.BooleanField(
        default=False,
        verbose_name=_("Is Notified"),
        help_text=_("True once the user has been notified of this achievement."),
    )
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Notified At"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Arbitrary context data at time of award (e.g. snapshot id, score)."),
    )

    objects: UserAchievementManager = UserAchievementManager()

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Achievement")
        verbose_name_plural = _("User Achievements")
        indexes = [
            models.Index(
                fields=["user", "is_awarded", "created_at"],
                name="gamif_ua_user_awarded_idx",
            ),
            models.Index(
                fields=["contest_cycle", "achievement_type"],
                name="gamif_ua_cycle_type_idx",
            ),
            models.Index(
                fields=["achievement_type", "awarded_at"],
                name="gamif_ua_type_awarded_at_idx",
            ),
        ]
        constraints = [
            # Unique award per user + type + cycle (when cycle is set)
            UniqueConstraint(
                fields=["user", "achievement_type", "contest_cycle"],
                condition=Q(contest_cycle__isnull=False),
                name="gamif_ua_uniq_usr_type_cyc",
            ),
            # Unique global award per user + type (when no cycle)
            UniqueConstraint(
                fields=["user", "achievement_type"],
                condition=Q(contest_cycle__isnull=True),
                name="gamif_ua_uniq_usr_type_glb",
            ),
            CheckConstraint(
                check=Q(points_awarded__gte=MIN_POINTS_VALUE),
                name="gamif_ua_min_points",
            ),
        ]

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        awarded = "✓" if self.is_awarded else "pending"
        return f"{self.user_id} — {self.title} [{awarded}]"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_cycle_scoped(self) -> bool:
        """True when this achievement is tied to a specific ContestCycle."""
        return self.contest_cycle_id is not None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # awarded_at must be set when is_awarded is True
        if self.is_awarded and not self.awarded_at:
            errors.setdefault("awarded_at", []).append(
                _("awarded_at must be set when is_awarded is True.")
            )

        # awarded_at must not be set when is_awarded is False
        if not self.is_awarded and self.awarded_at:
            errors.setdefault("awarded_at", []).append(
                _("awarded_at should be blank when is_awarded is False.")
            )

        # notified_at must correspond to is_notified
        if self.is_notified and not self.notified_at:
            errors.setdefault("notified_at", []).append(
                _("notified_at must be set when is_notified is True.")
            )

        # Immutability: once awarded, core award fields must not change
        if self.pk and self.is_awarded:
            try:
                original = UserAchievement.objects.get(pk=self.pk)
                if original.is_awarded:
                    immutable = ("user_id", "achievement_type", "contest_cycle_id", "points_awarded")
                    for field in immutable:
                        if getattr(original, field) != getattr(self, field):
                            errors.setdefault(field, []).append(
                                _(
                                    f"Field '{field}' cannot be changed after the achievement "
                                    "has been awarded."
                                )
                            )
            except UserAchievement.DoesNotExist:
                pass

        # points_awarded sanity
        if self.points_awarded is not None:
            if not isinstance(self.points_awarded, int):
                errors.setdefault("points_awarded", []).append(
                    _("points_awarded must be an integer.")
                )
            elif self.points_awarded < MIN_POINTS_VALUE or self.points_awarded > MAX_POINTS_VALUE:
                errors.setdefault("points_awarded", []).append(
                    _(
                        f"points_awarded must be between {MIN_POINTS_VALUE} "
                        f"and {MAX_POINTS_VALUE}."
                    )
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------

    def award(self, *, points: int = 0, rank: Optional[int] = None) -> None:
        """
        Formally grant this achievement to the user.

        This method is idempotent — calling it on an already-awarded achievement
        is a no-op (with a warning log).

        Args:
            points: Points to credit for this achievement. Defaults to 0.
            rank:   Leaderboard rank at time of award (optional).

        Raises:
            InvalidPointsError: If *points* is outside the valid range.
            ValidationError:    If the resulting state is invalid.
        """
        if self.is_awarded:
            logger.warning(
                "UserAchievement.award() called on already-awarded record id=%s; ignoring.",
                self.id,
            )
            return

        if not isinstance(points, int):
            raise InvalidPointsError(
                f"points must be an integer, got {type(points).__name__}."
            )
        if points < MIN_POINTS_VALUE or points > MAX_POINTS_VALUE:
            raise InvalidPointsError(
                f"points={points} is outside allowed range "
                f"[{MIN_POINTS_VALUE}, {MAX_POINTS_VALUE}]."
            )

        now = timezone.now()
        self.is_awarded = True
        self.awarded_at = now
        self.points_awarded = points

        if rank is not None:
            if not isinstance(rank, int) or rank < 1:
                raise ValidationError(
                    {"rank_at_award": [_("rank must be a positive integer.")]}
                )
            self.rank_at_award = rank

        with transaction.atomic():
            self.save(
                update_fields=[
                    "is_awarded",
                    "awarded_at",
                    "points_awarded",
                    "rank_at_award",
                    "updated_at",
                ]
            )

        logger.info(
            "UserAchievement %s awarded to user %s: points=%s rank=%s",
            self.id,
            self.user_id,
            points,
            rank,
        )

    def mark_notified(self) -> None:
        """
        Record that the user has been notified of this achievement.
        Idempotent.
        """
        if self.is_notified:
            return

        self.is_notified = True
        self.notified_at = timezone.now()
        self.save(update_fields=["is_notified", "notified_at", "updated_at"])
        logger.debug("UserAchievement %s marked as notified.", self.id)
