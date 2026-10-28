"""
Gamification Models - ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
Bulletproof / Defensive Coding with full validation, constraints, and audit fields.
Enhanced with integration system monitoring, audit logging, and SHA-256 hash chaining.
"""

from __future__ import annotations

import logging
import uuid
import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Optional, TYPE_CHECKING, Dict, Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q, F, CheckConstraint, UniqueConstraint
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.gamification.choices import (
    ContestCycleStatus,
    RewardType,
    AchievementType,
    LeaderboardScope,
    SnapshotStatus,
    BadgeRarity,
    BadgeCriteriaType,
    ChallengeAction,
    ChallengeStatus,
    StreakStatus,
    LevelPerkType,
)
from api.gamification.constants import (
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
from api.gamification.exceptions import (
    ContestCycleStateError,
    InvalidPointsError,
    DuplicateAchievementError,
    RewardAlreadyClaimedError,
)
from api.gamification.managers import (
    ContestCycleManager,
    LeaderboardSnapshotManager,
    ContestRewardManager,
    UserAchievementManager,
)
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from api.gamification.INTEGRATION_SYSTEM.sync_manager import sync_manager

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
import datetime

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------

class TimestampedModel(models.Model):
    """
    Abstract base providing created_at / updated_at audit timestamps
    and a UUID primary key for all gamification models.
    Enhanced with integration system monitoring and SHA-256 hash chaining.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )


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
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )
    integration_sync_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Integration Sync ID"),
        help_text=_("Integration system synchronization identifier."),
    )
    audit_metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Audit Metadata"),
        help_text=_("Additional audit and integration metadata."),
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} id={self.id}>"
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for this model instance."""
        # Get all field values except checksum itself
        data = {}
        for field in self._meta.fields:
            if field.name != 'checksum':
                value = getattr(self, field.name)
                if hasattr(value, 'isoformat'):  # DateTime fields
                    value = value.isoformat()
                elif hasattr(value, 'id'):  # Foreign keys
                    value = str(value.id) if value else None
                elif isinstance(value, (dict, list)):  # JSON fields
                    value = json.dumps(value, sort_keys=True)
                elif isinstance(value, Decimal):  # Decimal fields
                    value = str(value)
                elif value is not None:
                    value = str(value)
                else:
                    value = ''
                data[field.name] = value
        
        # Sort keys for consistent hashing
        json_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Calculate SHA-256 hash
        return hashlib.sha256(json_data.encode('utf-8')).hexdigest()
    
    def verify_checksum(self) -> bool:
        """Verify the checksum of this model instance."""
        current_checksum = self.checksum
        calculated_checksum = self.calculate_checksum()
        return current_checksum == calculated_checksum
    
    def log_audit_event(self, action: str, description: str, user_id: Optional[str] = None, **kwargs) -> None:
        """Log an audit event for this model instance."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger, AuditAction, ResourceType
            
            audit_logger.log(
                action=AuditAction(action.upper()) if hasattr(AuditAction, action.upper()) else AuditAction.UPDATE,
                description=description,
                resource_type=ResourceType.INTEGRATION,
                resource_id=str(self.id),
                user_id=user_id,
                details={
                    'model': self.__class__.__name__,
                    'checksum': self.checksum,
                    'integration_sync_id': self.integration_sync_id,
                    **kwargs
                }
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit event for {self.__class__.__name__}: {exc}")
    
    def record_performance_metric(self, metric_name: str, value: float, **kwargs) -> None:
        """Record a performance metric for this model instance."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
            
            labels = {
                'model': self.__class__.__name__,
                'resource_id': str(self.id),
                **kwargs
            }
            
            performance_monitor.record_metric(metric_name, value, labels)
        except Exception as exc:
            logger.warning(f"Failed to record performance metric for {self.__class__.__name__}: {exc}")
    
    def trigger_sync(self, sync_type: str = 'update', **kwargs) -> None:
        """Trigger synchronization for this model instance."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.sync_manager import sync_manager
            
            # Create sync policy if needed
            policy_id = f"{self.__class__.__name__.lower()}_{sync_type}"
            
            # Check if policy exists, create if not
            if policy_id not in sync_manager.policies:
                from api.gamification.INTEGRATION_SYSTEM.sync_manager import create_sync_policy, SyncType
                
                create_sync_policy(
                    policy_id=policy_id,
                    name=f"{self.__class__.__name__} {sync_type.title()} Sync",
                    source_system="gamification",
                    target_system="integration",
                    resource_type=self.__class__.__name__.lower(),
                    sync_type=SyncType.INCREMENTAL_SYNC,
                    enabled=True
                )
            
            # Start sync operation
            sync_manager.start_sync(policy_id, [str(self.id)])
            
        except Exception as exc:
            logger.warning(f"Failed to trigger sync for {self.__class__.__name__}: {exc}")
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to calculate checksum and log events."""
        # Calculate checksum before saving
        self.checksum = self.calculate_checksum()
        
        # Generate integration sync ID if not present
        if not self.integration_sync_id:
            import uuid
            self.integration_sync_id = str(uuid.uuid4())
        
        # Log audit event
        is_new = self.pk is None
        action = 'CREATE' if is_new else 'UPDATE'
        description = f"{self.__class__.__name__} {action.lower()}d"
        
        try:
            user_id = kwargs.get('user_id') or getattr(self, 'user_id', None)
            if hasattr(self, 'user') and self.user:
                user_id = str(self.user.id)
        except:
            user_id = None
        
        # Save the model
        super().save(*args, **kwargs)
        
        # Log audit event after successful save
        self.log_audit_event(action, description, user_id)
        
        # Trigger sync
        self.trigger_sync(action.lower())
        
        # Record performance metric
        self.record_performance_metric(f"{self.__class__.__name__.lower()}_save_duration", 1.0)

    def verify_checksum(self) -> bool:
        """Verify data integrity using checksum."""
        if not self.checksum:
            return True
        
        calculated = self.calculate_checksum()
        return self.checksum == calculated
    
    def log_audit_event(self, action: str, user_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an audit event for this model instance."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import AuditAction, AuditLevel, ResourceType
            
            audit_logger.log(
                action=AuditAction(action.lower()) if action.lower() in [a.value for a in AuditAction] else AuditAction.CREATE,
                description=f"{action} on {self.__class__.__name__} {self.id}",
                resource_type=ResourceType.INTEGRATION,
                resource_id=str(self.id),
                user_id=user_id,
            )
        except Exception as exc:
            logger.error(f"Failed to log audit event for {self.__class__.__name__}: {exc}")
    
    def record_performance_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a performance metric for this model instance."""
        try:
            performance_monitor.record_metric(
                f"{self.__class__.__name__.lower()}_{metric_name}",
                value,
                tags or {"model": self.__class__.__name__, "id": str(self.id)}
            )
        except Exception as exc:
            logger.error(f"Failed to record performance metric for {self.__class__.__name__}: {exc}")
    
    def trigger_sync(self, sync_type: str = "full") -> Optional[str]:
        """Trigger integration synchronization for this model instance."""
        try:
            from api.gamification.INTEGRATION_SYSTEM.sync_manager import (
                sync_manager, create_sync_policy, SyncType
            )

            # Create sync policy if needed
            policy_id = f"{self.__class__.__name__.lower()}_{sync_type}_sync"

            if policy_id not in sync_manager.policies:
                create_sync_policy(
                    policy_id=policy_id,
                    name=f"{self.__class__.__name__} {sync_type.title()} Sync",
                    source_system="gamification",
                    target_system="integration",
                    resource_type=self.__class__.__name__.lower(),
                    sync_type=SyncType.INCREMENTAL_SYNC,
                    enabled=True,
                )

            # Start sync operation
            operation_id = sync_manager.start_sync(
                policy_id=policy_id,
                resource_ids=[str(self.id)]
            )

            return operation_id
        except Exception as exc:
            logger.error(f"Failed to trigger sync for {self.__class__.__name__}: {exc}")
            return None


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
        blank=True, default='',
        verbose_name=_("Contest Name"),
        help_text=_("Human-readable unique name for this contest cycle."),
    )
    slug = models.SlugField(
        blank=True, default='',
        max_length=MAX_CONTEST_NAME_LENGTH,
        unique=True,
        db_index=True,
        verbose_name=_("Slug"),
        help_text=_("URL-safe identifier derived from the contest name."),
    )
    description = models.TextField(
        default="",
        blank=True,
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
        null=True, blank=True,
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
        blank=True,
        default=dict,
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
        constraints = []

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
        Enhanced with integration system monitoring and audit logging.
        """
        self.full_clean()
        
        # Generate SHA-256 checksum
        self.checksum = self.calculate_checksum()
        
        # Record performance metrics
        start_time = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Calculate save duration
        save_duration = (timezone.now() - start_time).total_seconds()
        self.record_performance_metric("save_duration", save_duration)
        
        # Log audit event
        is_new = self.created_at == self.updated_at
        action = "create" if is_new else "update"
        self.log_audit_event(
            action=action,
            details={
                "name": self.name,
                "status": self.status,
                "start_date": self.start_date.isoformat() if self.start_date else None,
                "end_date": self.end_date.isoformat() if self.end_date else None,
                "points_multiplier": str(self.points_multiplier)
            }
        )
        
        # Trigger sync for new records
        if is_new:
            self.trigger_sync("full")
        
        logger.debug(
            "ContestCycle saved: id=%s name=%s status=%s checksum=%s",
            self.id,
            self.name,
            self.status,
            self.checksum,
        )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition_to(self, new_status: str, *, actor: Optional["AbstractBaseUser"] = None) -> None:
        """
        Advance the contest cycle to *new_status* via the defined state machine.
        Enhanced with integration system monitoring and audit logging.

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

        # Record performance metrics for transition
        start_time = timezone.now()
        
        with transaction.atomic():
            self.save(update_fields=["status", "updated_at"])

        # Calculate transition duration
        transition_duration = (timezone.now() - start_time).total_seconds()
        self.record_performance_metric("state_transition_duration", transition_duration)

        # Log audit event for state transition
        self.log_audit_event(
            action="state_transition",
            user_id=str(getattr(actor, "pk", "system")) if actor else "system",
            details={
                "old_status": old_status,
                "new_status": new_status,
                "transition_duration": transition_duration,
                "actor_id": str(getattr(actor, "pk", "system")) if actor else "system"
            }
        )

        # Trigger sync for state changes
        self.trigger_sync("state_change")

        logger.info(
            "ContestCycle %s transitioned: %s → %s (actor=%s, duration=%s, checksum=%s)",
            self.id,
            old_status,
            new_status,
            getattr(actor, "pk", "system"),
            transition_duration,
            self.checksum,
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
        null=True, blank=True,
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
        blank=True,
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
        default="",
        blank=True,
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
        Enhanced with integration system monitoring and audit logging.
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

        # Record performance metrics for finalization
        start_time = timezone.now()
        
        raw = json.dumps(self.snapshot_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.status = SnapshotStatus.FINALIZED
        self.generated_at = timezone.now()
        
        # Update checksum using base class method
        self.checksum = self.calculate_checksum()
        
        self.save(update_fields=["status", "generated_at", "checksum", "updated_at"])
        
        # Calculate finalization duration
        finalization_duration = (timezone.now() - start_time).total_seconds()
        self.record_performance_metric("finalization_duration", finalization_duration)
        
        # Log audit event for finalization
        self.log_audit_event(
            action="finalize",
            details={
                "entry_count": self.entry_count,
                "finalization_duration": finalization_duration,
                "contest_cycle_id": str(self.contest_cycle_id) if self.contest_cycle_id else None,
                "scope": self.scope,
                "checksum": self.checksum
            }
        )
        
        # Trigger sync for finalized snapshots
        self.trigger_sync("finalization")
        
        logger.info(
            "LeaderboardSnapshot %s finalized; checksum=%s; duration=%s; entries=%d",
            self.id,
            self.checksum,
            finalization_duration,
            self.entry_count,
        )

    def mark_failed(self, error: str) -> None:
        """
        Transition snapshot to FAILED status with an error message.
        Uses a nested atomic savepoint so the FAILED status persists
        even if the outer transaction is rolled back.

        Args:
            error: Human-readable description of the failure.
        """
        if not isinstance(error, str) or not error.strip():
            error = "Unknown error (no message provided)."
        self.status = SnapshotStatus.FAILED
        self.error_message = error[:4096]  # truncate to DB-safe length
        from django.db import transaction as _tx
        with _tx.atomic():
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
        null=True, blank=True,
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
        null=True, blank=True,
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
        blank=True,
        default=dict,
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
        constraints = []

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
        null=True, blank=True,
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
        null=True, blank=True,
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Display title for the achievement (e.g. 'Top 10 Finisher')."),
    )
    description = models.TextField(
        default="",
        blank=True,
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
        blank=True,
        default=dict,
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
        Enhanced with integration system monitoring and audit logging.

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

        # Record performance metrics for awarding
        start_time = timezone.now()
        
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

        # Update checksum before saving
        self.checksum = self.calculate_checksum()

        with transaction.atomic():
            self.save(
                update_fields=[
                    "is_awarded",
                    "awarded_at",
                    "points_awarded",
                    "rank_at_award",
                    "checksum",
                    "updated_at",
                ]
            )

        # Calculate award duration
        award_duration = (timezone.now() - start_time).total_seconds()
        self.record_performance_metric("award_duration", award_duration)

        # Log audit event for awarding
        self.log_audit_event(
            action="award",
            user_id=str(self.user_id),
            details={
                "points_awarded": points,
                "rank_at_award": rank,
                "award_duration": award_duration,
                "achievement_type": self.achievement_type,
                "contest_cycle_id": str(self.contest_cycle_id) if self.contest_cycle_id else None
            }
        )

        # Trigger sync for awarded achievements
        self.trigger_sync("award")

        logger.info(
            "UserAchievement %s awarded to user %s: points=%s rank=%s duration=%s checksum=%s",
            self.id,
            self.user_id,
            points,
            rank,
            award_duration,
            self.checksum,
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


# ---------------------------------------------------------------------------
# Badge
# ---------------------------------------------------------------------------

class Badge(TimestampedModel):
    """
    Represents a badge that can be earned by users through various achievements.
    
    Badges have rarity tiers and criteria-based unlocking mechanisms.
    Each badge is immutable once created to maintain achievement integrity.
    """

    name = models.CharField(
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        unique=True,
        verbose_name=_("Badge Name"),
        help_text=_("Unique name of the badge."),
    )
    description = models.TextField(
        default="",
        blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
        help_text=_("Detailed description of what this badge represents."),
    )
    icon = models.CharField(
        max_length=100,
        default="🏆",
        verbose_name=_("Icon"),
        help_text=_("Emoji or icon identifier for the badge."),
    )
    rarity = models.CharField(
        max_length=20,
        choices=BadgeRarity.choices,
        default=BadgeRarity.COMMON,
        db_index=True,
        verbose_name=_("Rarity"),
        help_text=_("Rarity tier of the badge."),
    )
    criteria_type = models.CharField(
        max_length=50,
        choices=BadgeCriteriaType.choices,
        verbose_name=_("Criteria Type"),
        help_text=_("Type of achievement required to earn this badge."),
    )
    criteria_value = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name=_("Criteria Value"),
        help_text=_("Numeric value required to meet the criteria."),
    )
    points_bonus = models.IntegerField(
        default=0,
        validators=[MinValueValidator(MIN_POINTS_VALUE), MaxValueValidator(MAX_POINTS_VALUE)],
        verbose_name=_("Points Bonus"),
        help_text=_("Bonus points awarded when this badge is earned."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this badge can be earned by users."),
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Sort Order"),
        help_text=_("Display order for badges (lower numbers appear first)."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Additional badge configuration data."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash of badge definition for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Badge")
        verbose_name_plural = _("Badges")
        indexes = [
            models.Index(fields=["rarity", "is_active"], name="gamif_badge_rarity_active_idx"),
            models.Index(fields=["criteria_type", "criteria_value"], name="gamif_badge_criteria_idx"),
            models.Index(fields=["sort_order"], name="gamif_badge_sort_idx"),
        ]
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.icon} {self.name} [{self.get_rarity_display()}]"

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Validate criteria_value based on criteria_type
        if self.criteria_type == "POINTS_THRESHOLD" and self.criteria_value < 100:
            errors.setdefault("criteria_value", []).append(
                _("Points threshold must be at least 100.")
            )
        elif self.criteria_type == "STREAK_DAYS" and self.criteria_value < 1:
            errors.setdefault("criteria_value", []).append(
                _("Streak days must be at least 1.")
            )

        # Metadata size validation
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Invalid metadata JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        badge_data = {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "rarity": self.rarity,
            "criteria_type": self.criteria_type,
            "criteria_value": self.criteria_value,
            "points_bonus": self.points_bonus,
        }
        raw = json.dumps(badge_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("Badge %s saved with checksum %s", self.id, self.checksum)

    def is_unlocked_by_user(self, user_points: int = 0, streak_days: int = 0) -> bool:
        """Check if a user meets the criteria to unlock this badge."""
        if self.criteria_type == "POINTS_THRESHOLD":
            return user_points >= self.criteria_value
        elif self.criteria_type == "STREAK_DAYS":
            return streak_days >= self.criteria_value
        return False


# ---------------------------------------------------------------------------
# UserBadge
# ---------------------------------------------------------------------------

class UserBadge(TimestampedModel):
    """
    Junction model representing a badge earned by a specific user.
    
    Tracks when the badge was earned and whether it's pinned for display.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="badges",
        db_index=True,
        verbose_name=_("User"),
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.PROTECT,
        related_name="user_badges",
        verbose_name=_("Badge"),
    )
    earned_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Earned At"),
        help_text=_("Timestamp when the user earned this badge."),
    )
    is_pinned = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Pinned"),
        help_text=_("Whether this badge is pinned for display."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Context data about how the badge was earned."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Badge")
        verbose_name_plural = _("User Badges")
        indexes = [
            models.Index(fields=["user", "earned_at"], name="gamif_ub_user_earned_idx"),
            models.Index(fields=["badge", "earned_at"], name="gamif_ub_badge_earned_idx"),
            models.Index(fields=["user", "is_pinned"], name="gamif_ub_user_pinned_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["user", "badge"],
                name="gamif_ub_uniq_user_badge"
            ),
        ]
        ordering = ["-earned_at"]

    def __str__(self) -> str:
        pinned = "📌" if self.is_pinned else ""
        return f"{pinned}{self.user_id} — {self.badge.name}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        badge_data = {
            "user_id": str(self.user_id),
            "badge_id": str(self.badge_id),
            "earned_at": self.earned_at.isoformat() if self.earned_at else None,
            "is_pinned": self.is_pinned,
        }
        raw = json.dumps(badge_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("UserBadge %s saved with checksum %s", self.id, self.checksum)


# ---------------------------------------------------------------------------
# DailyChallenge
# ---------------------------------------------------------------------------

class DailyChallenge(TimestampedModel):
    """
    Represents a daily challenge that users can complete for bonus points.
    
    Challenges are created per day and have specific action targets.
    """

    title = models.CharField(
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Challenge title displayed to users."),
    )
    description = models.TextField(
        default="",
        blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the challenge."),
    )
    target_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name=_("Target Count"),
        help_text=_("Number of actions required to complete the challenge."),
    )
    target_action = models.CharField(
        max_length=50,
        choices=ChallengeAction.choices,
        blank=True, default="",
        verbose_name=_("Target Action"),
        help_text=_("Type of action that counts toward this challenge."),
    )
    bonus_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(MIN_POINTS_VALUE), MaxValueValidator(MAX_POINTS_VALUE)],
        verbose_name=_("Bonus Points"),
        help_text=_("Points awarded for completing this challenge."),
    )
    date = models.DateField(
        db_index=True,
        null=True, blank=True,
        verbose_name=_("Date"),
        help_text=_("Date when this challenge is active."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this challenge is currently available."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Additional challenge configuration."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Daily Challenge")
        verbose_name_plural = _("Daily Challenges")
        indexes = [
            models.Index(fields=["date", "is_active"], name="gamif_dc_date_active_idx"),
            models.Index(fields=["target_action", "date"], name="gamif_dc_action_date_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["date", "target_action"],
                name="gamif_dc_uniq_date_action"
            ),
        ]
        ordering = ["-date", "target_action"]

    def __str__(self) -> str:
        return f"{self.date} — {self.title}"

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Validate bonus points based on target count
        if self.target_count > 10 and self.bonus_points < 50:
            errors.setdefault("bonus_points", []).append(
                _("Challenges with high targets should award more bonus points.")
            )

        # Metadata validation
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Invalid metadata JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        challenge_data = {
            "title": self.title,
            "target_count": self.target_count,
            "target_action": self.target_action,
            "bonus_points": self.bonus_points,
            "date": self.date.isoformat() if self.date else None,
        }
        raw = json.dumps(challenge_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("DailyChallenge %s saved with checksum %s", self.id, self.checksum)


# ---------------------------------------------------------------------------
# UserDailyChallenge
# ---------------------------------------------------------------------------

class UserDailyChallenge(TimestampedModel):
    """
    Tracks a user's progress on a specific daily challenge.
    
    One record per user per challenge per day.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="daily_challenges",
        db_index=True,
        verbose_name=_("User"),
    )
    challenge = models.ForeignKey(
        DailyChallenge,
        on_delete=models.PROTECT,
        related_name="user_challenges",
        verbose_name=_("Challenge"),
    )
    progress = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Progress"),
        help_text=_("Current progress count toward the target."),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Completed At"),
        help_text=_("Timestamp when the challenge was completed."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Progress tracking data."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Daily Challenge")
        verbose_name_plural = _("User Daily Challenges")
        indexes = [
            models.Index(fields=["user", "challenge", "completed_at"], name="gamif_udc_user_challenge_idx"),
            models.Index(fields=["challenge", "completed_at"], name="gamif_udc_chal_cmp_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["user", "challenge"],
                name="gamif_udc_uniq_user_challenge"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "✓" if self.completed_at else f"{self.progress}/{self.challenge.target_count}"
        return f"{self.user_id} — {self.challenge.title} [{status}]"

    @property
    def is_completed(self) -> bool:
        """True when the challenge has been completed."""
        return self.completed_at is not None

    @is_completed.setter
    def is_completed(self, value: bool) -> None:
        """Allow serializers to set completion via this property."""
        from django.utils import timezone as tz
        if value and self.completed_at is None:
            self.completed_at = tz.now()
        elif not value:
            self.completed_at = None

    @property
    def progress_percentage(self) -> float:
        """Progress as a percentage (0-100)."""
        if self.challenge.target_count == 0:
            return 0.0
        return min(100.0, (self.progress / self.challenge.target_count) * 100.0)

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Progress cannot exceed target
        if self.progress > self.challenge.target_count:
            errors.setdefault("progress", []).append(
                _("Progress cannot exceed the challenge target count.")
            )

        # Completed at must be set when progress reaches target
        # (Skip this check on create if saving directly with progress - auto-set it)
        if self.progress >= self.challenge.target_count and not self.completed_at:
            from django.utils import timezone as _tz
            self.completed_at = _tz.now()  # auto-correct rather than raise error

        # Completed at should not be set if progress is less than target
        if self.completed_at and self.progress < self.challenge.target_count:
            errors.setdefault("completed_at", []).append(
                _("completed_at should not be set if challenge is not completed.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Auto-complete if progress reaches target
        if self.progress >= self.challenge.target_count and not self.completed_at:
            self.completed_at = timezone.now()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        challenge_data = {
            "user_id": str(self.user_id),
            "challenge_id": str(self.challenge_id),
            "progress": self.progress,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        raw = json.dumps(challenge_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("UserDailyChallenge %s saved with checksum %s", self.id, self.checksum)

    def increment_progress(self, amount: int = 1) -> bool:
        """
        Increment progress by the specified amount.
        
        Returns True if the challenge was completed by this increment.
        """
        if amount <= 0:
            return False
        
        from django.utils import timezone as _tz
        was_completed = self.is_completed
        self.progress = min(self.progress + amount, self.challenge.target_count)
        # Auto-set completed_at when target is reached (required by clean())
        if self.progress >= self.challenge.target_count and self.completed_at is None:
            self.completed_at = _tz.now()
        self.save()
        
        return not was_completed and self.is_completed


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------

class Streak(TimestampedModel):
    """
    Tracks user activity streaks for gamification engagement.
    
    Maintains current and longest streak records with automatic reset logic.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="streak",
        db_index=True,
        verbose_name=_("User"),
    )
    current_days = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Current Days"),
        help_text=_("Current consecutive days of activity."),
    )
    longest_days = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Longest Days"),
        help_text=_("Longest consecutive days achieved."),
    )
    last_activity_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Last Activity Date"),
        help_text=_("Date of the most recent activity."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether the streak is currently active."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Streak configuration and history data."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Streak")
        verbose_name_plural = _("Streaks")
        indexes = [
            models.Index(fields=["current_days", "is_active"], name="gamif_stk_cur_act_idx"),
            models.Index(fields=["longest_days"], name="gamif_streak_longest_idx"),
            models.Index(fields=["last_activity_date"], name="gamif_streak_last_activity_idx"),
        ]
        ordering = ["-current_days"]

    def __str__(self) -> str:
        status = "🔥" if self.is_active else "❄️"
        return f"{status}{self.user_id} — {self.current_days} days (best: {self.longest_days})"

    @property
    def days_until_reset(self) -> int:
        """Days remaining before streak resets (assuming 1-day grace period)."""
        if not self.last_activity_date:
            return 0
        from datetime import date
        today = date.today()
        days_since = (today - self.last_activity_date).days
        return max(0, 1 - days_since)  # 1-day grace period

    @property
    def is_expired(self) -> bool:
        """True if streak has expired (no activity for >1 day)."""
        return self.days_until_reset == 0 and self.last_activity_date is not None

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Current days cannot exceed longest days
        if self.current_days > self.longest_days:
            errors.setdefault("longest_days", []).append(
                _("Longest days must be >= current days.")
            )

        # Validate last_activity_date logic
        if self.last_activity_date:
            from datetime import date
            if self.last_activity_date > date.today():
                errors.setdefault("last_activity_date", []).append(
                    _("Last activity date cannot be in the future.")
                )

        # Metadata validation
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Invalid metadata JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        streak_data = {
            "user_id": str(self.user_id),
            "current_days": self.current_days,
            "longest_days": self.longest_days,
            "last_activity_date": self.last_activity_date.isoformat() if self.last_activity_date else None,
            "is_active": self.is_active,
        }
        raw = json.dumps(streak_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("Streak %s saved with checksum %s", self.id, self.checksum)

    def update_activity(self) -> tuple[bool, int]:
        """
        Update streak based on today's activity.
        
        Returns:
            Tuple of (streak_extended, days_added)
        """
        from datetime import date
        today = date.today()
        
        if not self.last_activity_date:
            # First activity
            self.current_days = 1
            self.longest_days = 1
            self.last_activity_date = today
            self.is_active = True
            self.save()
            return True, 1
        
        days_since = (today - self.last_activity_date).days
        
        if days_since == 0:
            # Already updated today
            return False, 0
        elif days_since == 1:
            # Consecutive day
            self.current_days += 1
            self.last_activity_date = today
            if self.current_days > self.longest_days:
                self.longest_days = self.current_days
            self.is_active = True
            self.save()
            return True, 1
        else:
            # Streak broken
            self.current_days = 1
            self.last_activity_date = today
            self.is_active = True
            self.save()
            return False, 1

    def reset_streak(self) -> None:
        """Reset the current streak to 0."""
        self.current_days = 0
        self.is_active = False
        self.save()
        logger.info("Streak reset for user %s", self.user_id)


# ---------------------------------------------------------------------------
# StreakReward
# ---------------------------------------------------------------------------

class StreakReward(TimestampedModel):
    """
    Defines rewards that users earn for maintaining streaks of specific lengths.
    
    Links streak milestones to points bonuses and badge rewards.
    """

    streak_days = models.PositiveIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        verbose_name=_("Streak Days"),
        help_text=_("Number of consecutive days required to earn this reward."),
    )
    points_bonus = models.IntegerField(
        default=0,
        validators=[MinValueValidator(MIN_POINTS_VALUE), MaxValueValidator(MAX_POINTS_VALUE)],
        verbose_name=_("Points Bonus"),
        help_text=_("Points awarded for reaching this streak milestone."),
    )
    badge = models.ForeignKey(
        Badge,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="streak_rewards",
        verbose_name=_("Badge"),
        help_text=_("Optional badge awarded for this streak milestone."),
    )
    title = models.CharField(
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Display title for this streak reward."),
    )
    description = models.TextField(
        default="",
        blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
        help_text=_("Description of the streak reward."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this reward is currently available."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Additional reward configuration."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Streak Reward")
        verbose_name_plural = _("Streak Rewards")
        indexes = [
            models.Index(fields=["streak_days", "is_active"], name="gamif_sr_days_active_idx"),
            models.Index(fields=["badge"], name="gamif_sr_badge_idx"),
        ]
        ordering = ["streak_days"]

    def __str__(self) -> str:
        badge_info = f" + {self.badge.name}" if self.badge else ""
        return f"{self.streak_days} days — {self.points_bonus} pts{badge_info}"

    def clean(self) -> None:
        errors: dict[str, list] = []

        # Validate points bonus based on streak days
        if self.streak_days >= 30 and self.points_bonus < 100:
            errors.setdefault("points_bonus", []).append(
                _("Long streaks should award more bonus points.")
            )

        # Metadata validation
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Invalid metadata JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        reward_data = {
            "streak_days": self.streak_days,
            "points_bonus": self.points_bonus,
            "badge_id": str(self.badge_id) if self.badge_id else None,
            "title": self.title,
        }
        raw = json.dumps(reward_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("StreakReward %s saved with checksum %s", self.id, self.checksum)


# ---------------------------------------------------------------------------
# LevelConfig
# ---------------------------------------------------------------------------

class LevelConfig(TimestampedModel):
    """
    Defines level thresholds and rewards for user progression.
    
    Each level requires specific points and provides perks and benefits.
    """

    level_number = models.PositiveIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        verbose_name=_("Level Number"),
        help_text=_("Unique level identifier in progression order."),
    )
    points_required = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_("Points Required"),
        help_text=_("Total points needed to reach this level."),
    )
    title = models.CharField(
        max_length=MAX_ACHIEVEMENT_TITLE_LENGTH,
        verbose_name=_("Title"),
        help_text=_("Display title for this level."),
    )
    description = models.TextField(
        default="",
        blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        verbose_name=_("Description"),
        help_text=_("Level description and benefits."),
    )
    perks = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Perks"),
        help_text=_("JSON configuration of level-specific perks and benefits."),
    )
    badge = models.ForeignKey(
        Badge,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="level_configs",
        verbose_name=_("Badge"),
        help_text=_("Optional badge awarded for reaching this level."),
    )
    points_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("5.00"))],
        verbose_name=_("Points Multiplier"),
        help_text=_("Multiplier applied to points earned at this level."),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Active"),
        help_text=_("Whether this level is currently available."),
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name=_("Metadata"),
        help_text=_("Additional level configuration data."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Level Config")
        verbose_name_plural = _("Level Configs")
        indexes = [
            models.Index(fields=["level_number", "is_active"], name="gamif_lc_level_active_idx"),
            models.Index(fields=["points_required"], name="gamif_lc_points_idx"),
            models.Index(fields=["badge"], name="gamif_lc_badge_idx"),
        ]
        ordering = ["level_number"]

    def __str__(self) -> str:
        return f"Level {self.level_number} — {self.title} ({self.points_required} pts)"

    @property
    def next_level(self) -> Optional["LevelConfig"]:
        """Get the next level in the progression."""
        try:
            return LevelConfig.objects.filter(
                level_number__gt=self.level_number,
                is_active=True
            ).order_by("level_number").first()
        except LevelConfig.DoesNotExist:
            return None

    @property
    def prev_level(self) -> Optional["LevelConfig"]:
        """Get the previous level in the progression."""
        try:
            return LevelConfig.objects.filter(
                level_number__lt=self.level_number,
                is_active=True
            ).order_by("-level_number").first()
        except LevelConfig.DoesNotExist:
            return None

    def clean(self) -> None:
        errors: dict[str, list] = []

        # Validate points progression
        if self.level_number > 1:
            prev_level = self.prev_level
            if prev_level and self.points_required <= prev_level.points_required:
                errors.setdefault("points_required", []).append(
                    _("Points required must be greater than the previous level.")
                )

        # Validate perks JSON structure
        if self.perks:
            import json
            try:
                if not isinstance(self.perks, dict):
                    raise ValueError("Perks must be a JSON object")
                encoded = json.dumps(self.perks).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("perks", []).append(
                        _(f"Perks configuration exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("perks", []).append(
                    _(f"Invalid perks JSON: {exc}")
                )

        # Metadata validation
        if self.metadata:
            import json
            try:
                encoded = json.dumps(self.metadata).encode("utf-8")
                if len(encoded) > MAX_META_JSON_SIZE_BYTES:
                    errors.setdefault("metadata", []).append(
                        _(f"Metadata exceeds maximum size of {MAX_META_JSON_SIZE_BYTES} bytes.")
                    )
            except (TypeError, ValueError) as exc:
                errors.setdefault("metadata", []).append(
                    _(f"Invalid metadata JSON: {exc}")
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        level_data = {
            "level_number": self.level_number,
            "points_required": self.points_required,
            "title": self.title,
            "points_multiplier": str(self.points_multiplier),
        }
        raw = json.dumps(level_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("LevelConfig %s saved with checksum %s", self.id, self.checksum)

    @classmethod
    def get_level_for_points(cls, total_points: int) -> Optional["LevelConfig"]:
        """Get the highest level achievable with the given points."""
        return cls.objects.filter(
            points_required__lte=total_points,
            is_active=True
        ).order_by("-level_number").first()

    @classmethod
    def get_progress_to_next_level(cls, current_points: int) -> dict:
        """Get progress information toward the next level."""
        current_level = cls.get_level_for_points(current_points)
        next_level = current_level.next_level if current_level else cls.objects.filter(
            is_active=True
        ).order_by("level_number").first()
        
        if not next_level:
            return {"is_max_level": True, "current_level": current_level}
        
        points_needed = next_level.points_required - current_points
        points_progress = max(0, current_points - (current_level.points_required if current_level else 0))
        points_total = next_level.points_required - (current_level.points_required if current_level else 0)
        
        return {
            "is_max_level": False,
            "current_level": current_level,
            "next_level": next_level,
            "points_needed": max(0, points_needed),
            "points_progress": points_progress,
            "points_total": points_total,
            "progress_percentage": (points_progress / points_total * 100) if points_total > 0 else 100,
        }


# ---------------------------------------------------------------------------
# UserPoints
# ---------------------------------------------------------------------------

class UserPoints(TimestampedModel):
    """
    Tracks user points across different time periods for gamification.
    
    Central points tracking model that aggregates points from all sources.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="points",
        db_index=True,
        verbose_name=_("User"),
        help_text=_("User who owns these points."),
    )
    total_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Total Points"),
        help_text=_("Current total points balance."),
    )
    lifetime_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Lifetime Points"),
        help_text=_("Total points earned historically (never decreases)."),
    )
    points_this_month = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Points This Month"),
        help_text=_("Points earned in the current calendar month."),
    )
    points_this_week = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Points This Week"),
        help_text=_("Points earned in the current week (Monday-Sunday)."),
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name=_("Last Updated"),
        help_text=_("Timestamp when points were last recalculated."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("User Points")
        verbose_name_plural = _("User Points")
        indexes = [
            models.Index(fields=["total_points"], name="gamif_up_total_idx"),
            models.Index(fields=["lifetime_points"], name="gamif_up_lifetime_idx"),
            models.Index(fields=["points_this_month"], name="gamif_up_month_idx"),
            models.Index(fields=["points_this_week"], name="gamif_up_week_idx"),
            models.Index(fields=["last_updated"], name="gamif_up_updated_idx"),
        ]
        ordering = ["-total_points"]

    def __str__(self) -> str:
        return f"{self.user_id} — {self.total_points} pts (lifetime: {self.lifetime_points})"

    @property
    def monthly_rank(self) -> Optional[int]:
        """Get user's rank based on points this month."""
        from django.db.models import Count
        users_with_more = UserPoints.objects.filter(
            points_this_month__gt=self.points_this_month
        ).count()
        return users_with_more + 1

    @property
    def weekly_rank(self) -> Optional[int]:
        """Get user's rank based on points this week."""
        from django.db.models import Count
        users_with_more = UserPoints.objects.filter(
            points_this_week__gt=self.points_this_week
        ).count()
        return users_with_more + 1

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Lifetime points must be >= total points
        if self.lifetime_points < self.total_points:
            errors.setdefault("lifetime_points", []).append(
                _("Lifetime points cannot be less than total points.")
            )

        # Monthly and weekly points cannot exceed lifetime points
        if self.points_this_month > self.lifetime_points:
            errors.setdefault("points_this_month", []).append(
                _("Monthly points cannot exceed lifetime points.")
            )

        if self.points_this_week > self.lifetime_points:
            errors.setdefault("points_this_week", []).append(
                _("Weekly points cannot exceed lifetime points.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        points_data = {
            "user_id": str(self.user_id),
            "total_points": self.total_points,
            "lifetime_points": self.lifetime_points,
            "points_this_month": self.points_this_month,
            "points_this_week": self.points_this_week,
        }
        raw = json.dumps(points_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("UserPoints %s saved with checksum %s", self.id, self.checksum)

    def add_points(self, amount: int, source: str = "manual", description: str = "") -> None:
        """Add points to this user's balance."""
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        
        self.total_points += amount
        self.lifetime_points += amount
        self.points_this_month += amount
        self.points_this_week += amount
        self.save()
        
        # Create transaction record
        PointsTransaction.objects.create(
            user=self.user,
            amount=amount,
            source=source,
            description=description or f"Added {amount} points from {source}",
            balance_after=self.total_points,
        )

    def deduct_points(self, amount: int, source: str = "manual", description: str = "") -> None:
        """Deduct points from this user's balance."""
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        
        if self.total_points < amount:
            raise ValueError("Insufficient points balance")
        
        self.total_points -= amount
        self.save()
        
        # Create transaction record (negative amount)
        PointsTransaction.objects.create(
            user=self.user,
            amount=-amount,
            source=source,
            description=description or f"Deducted {amount} points for {source}",
            balance_after=self.total_points,
        )

    def reset_monthly_points(self) -> None:
        """Reset monthly points to zero (typically called on first day of month)."""
        self.points_this_month = 0
        self.save()

    def reset_weekly_points(self) -> None:
        """Reset weekly points to zero (typically called on Monday)."""
        self.points_this_week = 0
        self.save()


# ---------------------------------------------------------------------------
# PointsTransaction
# ---------------------------------------------------------------------------

class PointsTransaction(TimestampedModel):
    """
    Records all point transactions for audit and tracking purposes.
    
    Every point addition or deduction creates a transaction record.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="point_transactions",
        db_index=True,
        verbose_name=_("User"),
        help_text=_("User who performed this transaction."),
    )
    amount = models.IntegerField(
        verbose_name=_("Amount"),
        help_text=_("Points amount (positive=earned, negative=deducted)."),
    )
    source = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name=_("Source"),
        help_text=_("Source of points: offer, referral, streak, challenge, contest, manual."),
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("Source ID"),
        help_text=_("Reference ID from the source system."),
    )
    description = models.CharField(
        max_length=255,
        verbose_name=_("Description"),
        help_text=_("Human-readable description of the transaction."),
    )
    balance_after = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_("Balance After"),
        help_text=_("User's total points balance after this transaction."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created At"),
        help_text=_("Timestamp when this transaction occurred."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Points Transaction")
        verbose_name_plural = _("Points Transactions")
        indexes = [
            models.Index(fields=["user", "created_at"], name="gamif_pt_user_created_idx"),
            models.Index(fields=["source", "created_at"], name="gamif_pt_source_created_idx"),
            models.Index(fields=["amount", "created_at"], name="gamif_pt_amount_created_idx"),
            models.Index(fields=["source_id"], name="gamif_pt_source_id_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        sign = "+" if self.amount > 0 else ""
        return f"{sign}{self.amount} pts for {self.user_id} from {self.source}"

    @property
    def is_earning(self) -> bool:
        """True if this transaction earned points."""
        return self.amount > 0

    @property
    def is_deduction(self) -> bool:
        """True if this transaction deducted points."""
        return self.amount < 0

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Amount cannot be zero
        if self.amount == 0:
            errors.setdefault("amount", []).append(
                _("Transaction amount cannot be zero.")
            )

        # Balance after must be non-negative
        if self.balance_after < 0:
            errors.setdefault("balance_after", []).append(
                _("Balance after transaction cannot be negative.")
            )

        # Validate source
        valid_sources = ["offer", "referral", "streak", "challenge", "contest", "manual", "bonus", "penalty"]
        if self.source not in valid_sources:
            errors.setdefault("source", []).append(
                _(f"Invalid source. Must be one of: {', '.join(valid_sources)}")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        transaction_data = {
            "user_id": str(self.user_id),
            "amount": self.amount,
            "source": self.source,
            "source_id": self.source_id,
            "description": self.description,
            "balance_after": self.balance_after,
        }
        raw = json.dumps(transaction_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("PointsTransaction %s saved with checksum %s", self.id, self.checksum)


# ---------------------------------------------------------------------------
# StreakFreeze
# ---------------------------------------------------------------------------

class StreakFreeze(TimestampedModel):
    """
    Records when users use streak freeze protection.
    
    Allows users to protect their streak from breaking for a day.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="streak_freezes",
        db_index=True,
        verbose_name=_("User"),
        help_text=_("User who used the streak freeze."),
    )
    streak = models.ForeignKey(
        "Streak",
        on_delete=models.CASCADE,
        related_name="freezes",
        db_index=True,
        verbose_name=_("Streak"),
        help_text=_("The streak that was protected."),
    )
    used_at = models.DateField(
        db_index=True,
        verbose_name=_("Used At"),
        help_text=_("Date when the streak freeze was applied."),
    )
    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Reason"),
        help_text=_("Optional reason for using the streak freeze."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Streak Freeze")
        verbose_name_plural = _("Streak Freezes")
        indexes = [
            models.Index(fields=["user", "used_at"], name="gamif_sf_user_used_idx"),
            models.Index(fields=["streak", "used_at"], name="gamif_sf_streak_used_idx"),
            models.Index(fields=["used_at"], name="gamif_sf_used_idx"),
        ]
        ordering = ["-used_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "used_at"],
                name="gamif_sf_unique_user_date"
            )
        ]

    def __str__(self) -> str:
        return f"Freeze for {self.user_id} on {self.used_at}"

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Used at cannot be in the future
        if self.used_at > timezone.now().date():
            errors.setdefault("used_at", []).append(
                _("Streak freeze date cannot be in the future.")
            )

        # Reason length validation
        if len(self.reason) > 255:
            errors.setdefault("reason", []).append(
                _("Reason cannot exceed 255 characters.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        freeze_data = {
            "user_id": str(self.user_id),
            "streak_id": str(self.streak_id),
            "used_at": self.used_at.isoformat(),
            "reason": self.reason,
        }
        raw = json.dumps(freeze_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("StreakFreeze %s saved with checksum %s", self.id, self.checksum)


# ---------------------------------------------------------------------------
# ContestParticipant
# ---------------------------------------------------------------------------

class ContestParticipant(TimestampedModel):
    """
    Tracks user participation in contest cycles.
    
    Records current points, rank, and disqualification status.
    """

    contest_cycle = models.ForeignKey(
        "ContestCycle",
        on_delete=models.CASCADE,
        related_name="participants",
        db_index=True,
        verbose_name=_("Contest Cycle"),
        help_text=_("The contest cycle this user is participating in."),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="contest_participations",
        db_index=True,
        verbose_name=_("User"),
        help_text=_("User participating in the contest."),
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Joined At"),
        help_text=_("Timestamp when user joined the contest."),
    )
    current_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Current Points"),
        help_text=_("Points earned in this contest cycle."),
    )
    current_rank = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name=_("Current Rank"),
        help_text=_("Current rank in the contest leaderboard."),
    )
    is_disqualified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is Disqualified"),
        help_text=_("Whether user is disqualified from this contest."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Contest Participant")
        verbose_name_plural = _("Contest Participants")
        indexes = [
            models.Index(fields=["contest_cycle", "current_rank"], name="gamif_cp_cycle_rank_idx"),
            models.Index(fields=["contest_cycle", "user"], name="gamif_cp_cycle_user_idx"),
            models.Index(fields=["user", "joined_at"], name="gamif_cp_user_joined_idx"),
            models.Index(fields=["current_points", "is_disqualified"], name="gamif_cp_pts_disq_idx"),
            models.Index(fields=["is_disqualified"], name="gamif_cp_disqualified_idx"),
        ]
        ordering = ["contest_cycle", "-current_points"]
        constraints = [
            models.UniqueConstraint(
                fields=["contest_cycle", "user"],
                name="gamif_cp_unique_cycle_user"
            )
        ]

    def __str__(self) -> str:
        status = "❌" if self.is_disqualified else "✅"
        rank_info = f"#{self.current_rank}" if self.current_rank else "unranked"
        return f"{status} {self.user_id} in {self.contest_cycle_id} — {self.current_points} pts ({rank_info})"

    @property
    def is_ranked(self) -> bool:
        """True if participant has a rank assigned."""
        return self.current_rank is not None

    @property
    def days_in_contest(self) -> int:
        """Number of days since joining the contest."""
        return (timezone.now().date() - self.joined_at.date()).days + 1

    def clean(self) -> None:
        errors: dict[str, list] = []

        # Points cannot be negative
        if self.current_points < 0:
            errors.setdefault("current_points", []).append(
                _("Current points cannot be negative.")
            )

        # Rank must be positive if set
        if self.current_rank is not None and self.current_rank <= 0:
            errors.setdefault("current_rank", []).append(
                _("Current rank must be positive.")
            )

        # Disqualified users should not have ranks
        if self.is_disqualified and self.current_rank is not None:
            errors.setdefault("current_rank", []).append(
                _("Disqualified participants cannot have ranks.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        participant_data = {
            "contest_cycle_id": str(self.contest_cycle_id),
            "user_id": str(self.user_id),
            "current_points": self.current_points,
            "current_rank": self.current_rank,
            "is_disqualified": self.is_disqualified,
        }
        raw = json.dumps(participant_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("ContestParticipant %s saved with checksum %s", self.id, self.checksum)

    def add_points(self, amount: int) -> None:
        """Add points to this participant's contest score."""
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        
        self.current_points += amount
        self.save()

    def disqualify(self) -> None:
        """Disqualify this participant from the contest."""
        self.is_disqualified = True
        self.current_rank = None
        self.save()

    def update_rank(self, new_rank: int) -> None:
        """Update the participant's rank."""
        if self.is_disqualified:
            raise ValueError("Cannot update rank for disqualified participant")
        
        self.current_rank = new_rank
        self.save()


# ---------------------------------------------------------------------------
# GamificationConfig
# ---------------------------------------------------------------------------

class GamificationConfig(TimestampedModel):
    """
    Tenant-level configuration for gamification features.
    
    Controls which gamification features are enabled per tenant.
    """

    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name="gamification_config",
        db_index=True,
        verbose_name=_("Tenant"),
        help_text=_("Tenant this configuration belongs to."),
    )
    enable_contests = models.BooleanField(
        default=True,
        verbose_name=_("Enable Contests"),
        help_text=_("Enable contest cycles and leaderboards."),
    )
    enable_badges = models.BooleanField(
        default=True,
        verbose_name=_("Enable Badges"),
        help_text=_("Enable badge system and achievements."),
    )
    enable_streaks = models.BooleanField(
        default=True,
        verbose_name=_("Enable Streaks"),
        help_text=_("Enable activity streak tracking."),
    )
    enable_levels = models.BooleanField(
        default=True,
        verbose_name=_("Enable Levels"),
        help_text=_("Enable user level progression system."),
    )
    enable_daily_challenges = models.BooleanField(
        default=True,
        verbose_name=_("Enable Daily Challenges"),
        help_text=_("Enable daily challenge system."),
    )
    points_expiry_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        verbose_name=_("Points Expiry Days"),
        help_text=_("Days after which points expire. Null = never expire."),
    )
    leaderboard_refresh_interval = models.IntegerField(
        default=300,
        validators=[MinValueValidator(60), MaxValueValidator(3600)],
        verbose_name=_("Leaderboard Refresh Interval"),
        help_text=_("Seconds between leaderboard updates (60-3600)."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Gamification Config")
        verbose_name_plural = _("Gamification Configs")
        indexes = [
            models.Index(fields=["tenant"], name="gamif_gc_tenant_idx"),
            models.Index(fields=["enable_contests"], name="gamif_gc_contests_idx"),
            models.Index(fields=["enable_badges"], name="gamif_gc_badges_idx"),
            models.Index(fields=["enable_streaks"], name="gamif_gc_streaks_idx"),
            models.Index(fields=["enable_levels"], name="gamif_gc_levels_idx"),
            models.Index(fields=["enable_daily_challenges"], name="gamif_gc_challenges_idx"),
        ]

    def __str__(self) -> str:
        return f"Config for tenant {self.tenant_id}"

    @property
    def features_enabled(self) -> list[str]:
        """List of enabled feature names."""
        features = []
        if self.enable_contests:
            features.append("contests")
        if self.enable_badges:
            features.append("badges")
        if self.enable_streaks:
            features.append("streaks")
        if self.enable_levels:
            features.append("levels")
        if self.enable_daily_challenges:
            features.append("daily_challenges")
        return features

    @property
    def is_points_expiry_enabled(self) -> bool:
        """True if points expire after some time."""
        return self.points_expiry_days is not None

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # Leaderboard refresh interval validation
        if not (60 <= self.leaderboard_refresh_interval <= 3600):
            errors.setdefault("leaderboard_refresh_interval", []).append(
                _("Leaderboard refresh interval must be between 60 and 3600 seconds.")
            )

        # Points expiry days validation
        if self.points_expiry_days is not None and self.points_expiry_days < 1:
            errors.setdefault("points_expiry_days", []).append(
                _("Points expiry days must be at least 1 if set.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        config_data = {
            "tenant_id": str(self.tenant_id),
            "enable_contests": self.enable_contests,
            "enable_badges": self.enable_badges,
            "enable_streaks": self.enable_streaks,
            "enable_levels": self.enable_levels,
            "enable_daily_challenges": self.enable_daily_challenges,
            "points_expiry_days": self.points_expiry_days,
            "leaderboard_refresh_interval": self.leaderboard_refresh_interval,
        }
        raw = json.dumps(config_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("GamificationConfig %s saved with checksum %s", self.id, self.checksum)

    @classmethod
    def get_for_tenant(cls, tenant_id: str) -> "GamificationConfig":
        """Get or create config for a tenant."""
        config, created = cls.objects.get_or_create(
            tenant_id=tenant_id,
            defaults={}
        )
        return config


# ---------------------------------------------------------------------------
# GamificationInsight
# ---------------------------------------------------------------------------

class GamificationInsight(TimestampedModel):
    """
    Daily analytics and insights for gamification system.
    
    Tracks engagement metrics and system performance.
    """

    date = models.DateField(
        unique=True,
        db_index=True,
        null=True, blank=True,
        verbose_name=_("Date"),
        help_text=_("Date for these insights."),
    )
    active_users = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Active Users"),
        help_text=_("Number of users who earned points on this date."),
    )
    badges_awarded = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Badges Awarded"),
        help_text=_("Number of badges awarded on this date."),
    )
    challenges_completed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Challenges Completed"),
        help_text=_("Number of challenges completed on this date."),
    )
    total_points_issued = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Total Points Issued"),
        help_text=_("Total points issued to users on this date."),
    )
    contest_participants = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Contest Participants"),
        help_text=_("Number of users participating in contests on this date."),
    )
    streak_milestones = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Streak Milestones"),
        help_text=_("Number of streak milestones reached on this date."),
    )
    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 hash for integrity verification."),
    )

    class Meta(TimestampedModel.Meta):
        verbose_name = _("Gamification Insight")
        verbose_name_plural = _("Gamification Insights")
        indexes = [
            models.Index(fields=["date"], name="gamif_gi_date_idx"),
            models.Index(fields=["active_users"], name="gamif_gi_active_users_idx"),
            models.Index(fields=["total_points_issued"], name="gamif_gi_points_issued_idx"),
        ]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Insights for {self.date}"

    @property
    def points_per_active_user(self) -> float:
        """Average points earned per active user."""
        if self.active_users == 0:
            return 0.0
        return self.total_points_issued / self.active_users

    @property
    def engagement_rate(self) -> float:
        """Engagement rate as badges per active user."""
        if self.active_users == 0:
            return 0.0
        return self.badges_awarded / self.active_users

    def clean(self) -> None:
        errors: dict[str, list] = {}

        # All numeric fields must be non-negative
        numeric_fields = [
            "active_users", "badges_awarded", "challenges_completed",
            "total_points_issued", "contest_participants", "streak_milestones"
        ]
        
        for field in numeric_fields:
            value = getattr(self, field)
            if value < 0:
                errors.setdefault(field, []).append(
                    _(f"{field.replace('_', ' ').title()} cannot be negative.")
                )

        # Date cannot be in the future
        if self.date > timezone.now().date():
            errors.setdefault("date", []).append(
                _("Insight date cannot be in the future.")
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        
        # Generate SHA-256 checksum
        import hashlib
        import json
        insight_data = {
            "date": self.date.isoformat(),
            "active_users": self.active_users,
            "badges_awarded": self.badges_awarded,
            "challenges_completed": self.challenges_completed,
            "total_points_issued": self.total_points_issued,
            "contest_participants": self.contest_participants,
            "streak_milestones": self.streak_milestones,
        }
        raw = json.dumps(insight_data, sort_keys=True, ensure_ascii=False)
        self.checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        
        super().save(*args, **kwargs)
        logger.debug("GamificationInsight %s saved with checksum %s", self.id, self.checksum)

    @classmethod
    def get_or_create_today(cls) -> "GamificationInsight":
        """Get or create insights for today."""
        today = timezone.now().date()
        insight, created = cls.objects.get_or_create(
            date=today,
            defaults={}
        )
        return insight

    @classmethod
    def calculate_daily_metrics(cls, date: Optional["datetime.date"] = None) -> "GamificationInsight":
        """Calculate and save metrics for a specific date."""
        if date is None:
            date = timezone.now().date()
        
        insight, created = cls.objects.get_or_create(date=date)
        
        # Calculate active users (users who earned points)
        from django.db.models import Count
        insight.active_users = PointsTransaction.objects.filter(
            created_at__date=date,
            amount__gt=0
        ).values('user').distinct().count()
        
        # Calculate badges awarded
        try:
            from api.gamification.models import UserAchievement
            insight.badges_awarded = UserAchievement.objects.filter(
                created_at__date=date
            ).count()
        except:
            insight.badges_awarded = 0
        
        # Calculate challenges completed
        try:
            from api.gamification.models import Challenge
            insight.challenges_completed = Challenge.objects.filter(
                completed_at__date=date
            ).count()
        except:
            insight.challenges_completed = 0
        
        # Calculate total points issued
        points_issued = PointsTransaction.objects.filter(
            created_at__date=date,
            amount__gt=0
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        insight.total_points_issued = points_issued
        
        # Calculate contest participants
        try:
            insight.contest_participants = ContestParticipant.objects.filter(
                joined_at__date=date
            ).count()
        except:
            insight.contest_participants = 0
        
        # Calculate streak milestones
        try:
            from api.gamification.models import Streak
            insight.streak_milestones = Streak.objects.filter(
                updated_at__date=date
            ).filter(
                current_days__in=[7, 14, 30, 60, 90, 180, 365]
            ).count()
        except:
            insight.streak_milestones = 0
        
        insight.save()
        return insight


# ── Webhook Models ────────────────────────────────────────────────────────────

class WebhookEndpoint(TimestampedModel):
    """Webhook endpoint configuration."""
    url             = models.URLField(verbose_name=_("Endpoint URL"))
    secret          = models.CharField(max_length=255, blank=True, default="")
    event_types     = models.JSONField(blank=True, default=list)
    is_active       = models.BooleanField(default=True)
    description     = models.CharField(max_length=500, blank=True, default="")
    failure_count   = models.PositiveIntegerField(default=0)
    last_triggered  = models.DateTimeField(null=True, blank=True)
    metadata        = models.JSONField(blank=True, default=dict)

    class Meta:
        app_label = "gamification"
        verbose_name = _("Webhook Endpoint")
        verbose_name_plural = _("Webhook Endpoints")
        indexes = [
            models.Index(fields=["is_active"], name="gamif_we_active_idx"),
        ]

    def __str__(self):
        return f"WebhookEndpoint({self.url[:50]})"


class WebhookEvent(TimestampedModel):
    """Webhook event payload."""
    endpoint    = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE,
                                    related_name="events")
    event_type  = models.CharField(max_length=100)
    payload     = models.JSONField(blank=True, default=dict)
    status      = models.CharField(max_length=50, default="pending")
    metadata    = models.JSONField(blank=True, default=dict)

    class Meta:
        app_label  = "gamification"
        verbose_name = _("Webhook Event")
        verbose_name_plural = _("Webhook Events")
        indexes = [
            models.Index(fields=["event_type", "status"], name="gamif_wev_type_status_idx"),
        ]

    def __str__(self):
        return f"WebhookEvent({self.event_type})"


class WebhookDelivery(TimestampedModel):
    """Webhook delivery attempt record."""
    event           = models.ForeignKey(WebhookEvent, on_delete=models.CASCADE,
                                        related_name="deliveries")
    attempt_number  = models.PositiveSmallIntegerField(default=1)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_body   = models.TextField(blank=True, default="")
    error_message   = models.TextField(blank=True, default="")
    delivered_at    = models.DateTimeField(null=True, blank=True)
    metadata        = models.JSONField(blank=True, default=dict)

    class Meta:
        app_label = "gamification"
        verbose_name = _("Webhook Delivery")
        verbose_name_plural = _("Webhook Deliveries")
        indexes = [
            models.Index(fields=["delivered_at"], name="gamif_wd_delivered_idx"),
        ]

    def __str__(self):
        return f"WebhookDelivery(event={self.event_id} attempt={self.attempt_number})"
