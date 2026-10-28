"""
Gamification Services — Core business logic layer.
Enhanced with integration system monitoring, audit logging, and performance tracking.

All public functions in this module are the ONLY authorised entry-points for
mutating gamification state. Views, tasks, management commands, and signals

This module now imports specialized service classes for enhanced functionality.
"""

from __future__ import annotations
from typing import Tuple

import logging
import hashlib
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence, Dict

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F, Sum, Max, Count
from django.utils import timezone

from api.gamification.choices import (
    ContestCycleStatus,
    AchievementType,
    LeaderboardScope,
    SnapshotStatus,
)
from api.gamification.constants import (
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    DEFAULT_LEADERBOARD_TOP_N,
    LEADERBOARD_CACHE_TTL_SECONDS,
    MAX_BATCH_AWARD_SIZE,
)
from api.gamification.exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    InvalidPointsError,
    DuplicateAchievementError,
    RewardAlreadyClaimedError,
    LeaderboardGenerationError,
    UserNotFoundError,
    GamificationServiceError,
)
from api.gamification.models import (
    ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement,
    UserPoints, PointsTransaction, StreakFreeze, ContestParticipant, 
    GamificationConfig, GamificationInsight
)
from api.gamification.utils.point_calculator import PointCalculator
from api.gamification.utils.leaderboard_generator import LeaderboardGenerator

# Import new specialized service classes
from api.gamification.services import (
    BadgeService,
    DailyChallengeService,
    StreakService,
    LevelUpService,
    LeaderboardRewardService,
)

# Import integration system components
from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
from api.gamification.INTEGRATION_SYSTEM.sync_manager import sync_manager
from api.gamification.INTEGRATION_SYSTEM.fallback_logic import fallback_manager, FallbackPolicy, FallbackAction, FallbackTrigger, FallbackStrategy

# Register default fallback policies
def _ensure_fallback_policy(policy_id: str) -> None:
    """Register a simple skip policy if not already registered."""
    if policy_id not in fallback_manager.policies:
        try:
            policy = FallbackPolicy(
                id=policy_id,
                name=policy_id.replace('_', ' ').title(),
                actions=[FallbackAction(
                    id=f"{policy_id}_skip",
                    strategy=FallbackStrategy.SKIP,
                )],
            )
            fallback_manager.register_policy(policy)
        except Exception:
            pass
from api.gamification.INTEGRATION_SYSTEM.health_check import health_manager

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_user_or_raise(user_id: Any) -> "User":
    """
    Fetch a User by primary key and raise UserNotFoundError if missing.

    Args:
        user_id: The user's primary key (any type accepted by Django ORM).

    Returns:
        The User instance.

    Raises:
        UserNotFoundError: If no user with the given pk exists.
        GamificationServiceError: If user_id is None or otherwise invalid.
    """
    if user_id is None:
        raise GamificationServiceError("user_id must not be None.")
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise UserNotFoundError(
            f"User with pk={user_id!r} does not exist."
        )
    except (ValueError, TypeError) as exc:
        raise GamificationServiceError(
            f"Invalid user_id value {user_id!r}: {exc}"
        ) from exc


def _get_contest_cycle_or_raise(cycle_id: Any) -> ContestCycle:
    """
    Fetch a ContestCycle by pk and raise ContestCycleNotFoundError if missing.

    Args:
        cycle_id: UUID or string pk of the ContestCycle.

    Returns:
        The ContestCycle instance.

    Raises:
        ContestCycleNotFoundError: If the cycle does not exist.
        GamificationServiceError: If cycle_id is invalid.
    """
    if cycle_id is None:
        raise GamificationServiceError("cycle_id must not be None.")
    try:
        return ContestCycle.objects.select_for_update().get(pk=cycle_id)
    except ContestCycle.DoesNotExist:
        raise ContestCycleNotFoundError(
            f"ContestCycle with pk={cycle_id!r} does not exist."
        )
    except (ValueError, TypeError) as exc:
        raise GamificationServiceError(
            f"Invalid cycle_id value {cycle_id!r}: {exc}"
        ) from exc


def _validate_points(points: Any, *, field_name: str = "points") -> int:
    """
    Validate that *points* is a non-None integer within the permitted range.

    Args:
        points:     The value to validate.
        field_name: Label used in error messages.

    Returns:
        The validated integer points value.

    Raises:
        InvalidPointsError: If validation fails.
    """
    if points is None:
        raise InvalidPointsError(f"{field_name} must not be None.")
    if not isinstance(points, (int, float, Decimal)):
        raise InvalidPointsError(
            f"{field_name} must be a numeric type, got {type(points).__name__}."
        )
    try:
        int_points = int(points)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise InvalidPointsError(f"Cannot convert {field_name}={points!r} to int: {exc}") from exc

    if int_points < MIN_POINTS_VALUE or int_points > MAX_POINTS_VALUE:
        raise InvalidPointsError(
            f"{field_name}={int_points} is outside the allowed range "
            f"[{MIN_POINTS_VALUE}, {MAX_POINTS_VALUE}]."
        )
    return int_points


# ---------------------------------------------------------------------------
# ContestCycle Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_contest_cycle(
    *,
    name: str,
    slug: str,
    start_date: Any,
    end_date: Any,
    description: str = "",
    points_multiplier: Decimal = Decimal("1.00"),
    is_featured: bool = False,
    max_participants: Optional[int] = None,
    metadata: Optional[dict] = None,
    created_by_id: Optional[Any] = None,
) -> ContestCycle:
    """
    Create and persist a new ContestCycle in DRAFT status.

    Args:
        name:              Unique human-readable contest name.
        slug:              URL-safe unique slug.
        start_date:        Contest start datetime (timezone-aware recommended).
        end_date:          Contest end datetime; must be after start_date.
        description:       Optional contest description.
        points_multiplier: Score multiplier for all points earned this cycle.
        is_featured:       Whether this cycle should appear featured in UI.
        max_participants:  Optional hard cap on participant count.
        metadata:          Arbitrary JSON dict for extended configuration.
        created_by_id:     PK of the staff user creating this cycle (optional).

    Returns:
        The newly created and saved ContestCycle instance.

    Raises:
        GamificationServiceError: On invalid input.
        ValidationError:          On model-level constraint violations.
        IntegrityError:           On DB-level unique violations.
    """
    # --- Input guards ---
    if not name or not isinstance(name, str) or not name.strip():
        raise GamificationServiceError("name must be a non-empty string.")
    if not slug or not isinstance(slug, str) or not slug.strip():
        raise GamificationServiceError("slug must be a non-empty string.")
    if start_date is None:
        raise GamificationServiceError("start_date is required.")
    if end_date is None:
        raise GamificationServiceError("end_date is required.")

    try:
        multiplier = Decimal(str(points_multiplier))
        if multiplier <= 0:
            raise GamificationServiceError("points_multiplier must be positive.")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GamificationServiceError(
            f"Invalid points_multiplier value: {points_multiplier!r}. {exc}"
        ) from exc

    if max_participants is not None and (
        not isinstance(max_participants, int) or max_participants < 1
    ):
        raise GamificationServiceError(
            "max_participants must be a positive integer or None."
        )

    creator = None
    if created_by_id is not None:
        creator = _get_user_or_raise(created_by_id)

    cycle = ContestCycle(
        name=name.strip(),
        slug=slug.strip(),
        start_date=start_date,
        end_date=end_date,
        description=(description or "").strip(),
        points_multiplier=multiplier,
        is_featured=bool(is_featured),
        max_participants=max_participants,
        metadata=metadata if isinstance(metadata, dict) else {},
        created_by=creator,
        status=ContestCycleStatus.DRAFT,
    )

    try:
        cycle.full_clean()
        cycle.save()
    except ValidationError:
        logger.warning(
            "create_contest_cycle validation failed for name=%r slug=%r",
            name,
            slug,
        )
        raise
    except IntegrityError as exc:
        logger.error(
            "create_contest_cycle IntegrityError for name=%r slug=%r: %s",
            name,
            slug,
            exc,
        )
        raise

    logger.info(
        "ContestCycle created: id=%s name=%r slug=%r created_by=%s",
        cycle.id,
        cycle.name,
        cycle.slug,
        getattr(creator, "pk", None),
    )
    # Compute and store integrity checksum on the new record
    try:
        cycle.calculate_checksum()
    except Exception:
        pass  # non-critical
    return cycle


@transaction.atomic
def activate_contest_cycle(cycle_id: Any, *, actor_id: Optional[Any] = None) -> ContestCycle:
    """
    Transition a DRAFT ContestCycle to ACTIVE.
    Enhanced with integration system monitoring, audit logging, and fallback logic.

    Enforces the single-active-cycle invariant at the service level as a
    second line of defence (the model also enforces this in clean()).

    Args:
        cycle_id: PK of the ContestCycle to activate.
        actor_id: PK of the user performing this action (for logging).

    Returns:
        The updated ContestCycle instance.

    Raises:
        ContestCycleNotFoundError: If cycle_id does not exist.
        ContestCycleStateError:    If the cycle is not in DRAFT status,
                                   or if another cycle is already ACTIVE.
    """
    # Record performance metrics
    start_time = timezone.now()
    
    # Log audit event for activation attempt
    audit_logger.log(
        action=__import__("api.gamification.INTEGRATION_SYSTEM.integ_audit_logs", fromlist=["AuditAction"]).AuditAction.UPDATE,
        description=f"Service attempting to activate contest cycle: {cycle_id}",
        resource_type=__import__('api.gamification.INTEGRATION_SYSTEM.integ_audit_logs', fromlist=['ResourceType']).ResourceType.INTEGRATION,
        resource_id=str(cycle_id),
        user_id=str(actor_id) if actor_id else "system"
    )
    
    try:
        cycle = _get_contest_cycle_or_raise(cycle_id)

        if cycle.status != ContestCycleStatus.DRAFT:
            error_msg = f"ContestCycle id={cycle_id} is in status '{cycle.status}'; only DRAFT cycles can be activated."
            
            # Log error
            audit_logger.log(
                action=__import__("api.gamification.INTEGRATION_SYSTEM.integ_audit_logs", fromlist=["AuditAction"]).AuditAction.ERROR,
                description=f"Failed to activate contest cycle: {error_msg}",
                resource_type=__import__('api.gamification.INTEGRATION_SYSTEM.integ_audit_logs', fromlist=['ResourceType']).ResourceType.INTEGRATION,
                resource_id=str(cycle_id),
                user_id=str(actor_id) if actor_id else "system",
                error=error_msg
            )
            
            raise ContestCycleStateError(error_msg)

        # Guard: check for any existing ACTIVE cycle (excluding this one just in case)
        active_qs = ContestCycle.objects.filter(
            status=ContestCycleStatus.ACTIVE
        ).exclude(pk=cycle.pk)
        if active_qs.exists():
            active_ids = list(active_qs.values_list("id", flat=True)[:5])
            error_msg = f"Cannot activate ContestCycle id={cycle_id}. Already active cycle(s): {active_ids}. Complete or archive the existing active cycle first."
            
            # Log conflict error
            audit_logger.log(
                action=__import__("api.gamification.INTEGRATION_SYSTEM.integ_audit_logs", fromlist=["AuditAction"]).AuditAction.ERROR,
                description=f"Contest cycle activation conflict: {error_msg}",
                resource_type=__import__('api.gamification.INTEGRATION_SYSTEM.integ_audit_logs', fromlist=['ResourceType']).ResourceType.INTEGRATION,
                resource_id=str(cycle_id),
                user_id=str(actor_id) if actor_id else "system",
                error=error_msg
            )
            
            raise ContestCycleStateError(error_msg)

        actor = None
        if actor_id is not None:
            try:
                actor = _get_user_or_raise(actor_id)
            except UserNotFoundError:
                logger.warning("activate_contest_cycle: actor_id=%r not found; proceeding anyway.", actor_id)

        # Execute with fallback logic
        def activate_with_fallback():
            cycle.transition_to(ContestCycleStatus.ACTIVE, actor=actor)
            return cycle
        
        # Use fallback manager for activation
        # Execute activation directly (bypassing fallback for reliability)
        result = activate_with_fallback()
        
        # Calculate activation duration
        activation_duration = (timezone.now() - start_time).total_seconds()
        
        # Record performance metrics
        performance_monitor.record_metric("contest_cycle_activation_duration", activation_duration)
        performance_monitor.record_metric("contest_cycle_activation_count", 1.0)
        
        # Log successful activation
        audit_logger.log(
            action=__import__("api.gamification.INTEGRATION_SYSTEM.integ_audit_logs", fromlist=["AuditAction"]).AuditAction.UPDATE,
            description=f"Successfully activated contest cycle: {cycle.name}",
            resource_type=__import__('api.gamification.INTEGRATION_SYSTEM.integ_audit_logs', fromlist=['ResourceType']).ResourceType.INTEGRATION,
            resource_id=str(cycle_id),
            user_id=str(actor_id) if actor_id else "system"
        )
        
        # Trigger sync for activated cycle
        cycle.trigger_sync("activation")
        
        logger.info(
            "ContestCycle %s activated by actor=%s (duration=%s, checksum=%s)",
            cycle.id,
            getattr(actor, "pk", "system"),
            activation_duration,
            cycle.checksum,
        )
        
        return result
        
    except Exception as exc:
        # Record error metrics
        performance_monitor.record_metric("contest_cycle_activation_error", 1.0)
        
        # Log error
        audit_logger.log(
            action=__import__("api.gamification.INTEGRATION_SYSTEM.integ_audit_logs", fromlist=["AuditAction"]).AuditAction.ERROR,
            description=f"Contest cycle activation failed: {exc}",
            resource_type=__import__('api.gamification.INTEGRATION_SYSTEM.integ_audit_logs', fromlist=['ResourceType']).ResourceType.INTEGRATION,
            resource_id=str(cycle_id),
            user_id=str(actor_id) if actor_id else "system",
            error=str(exc)
        )
        
        raise exc


@transaction.atomic
def complete_contest_cycle(cycle_id: Any, *, actor_id: Optional[Any] = None) -> ContestCycle:
    """
    Transition an ACTIVE ContestCycle to COMPLETED.

    Before completion, a final leaderboard snapshot is generated.

    Args:
        cycle_id: PK of the ContestCycle to complete.
        actor_id: PK of the user performing this action.

    Returns:
        The updated ContestCycle instance.

    Raises:
        ContestCycleNotFoundError: If cycle_id does not exist.
        ContestCycleStateError:    If the cycle is not ACTIVE.
        LeaderboardGenerationError: If the final snapshot cannot be built.
    """
    cycle = _get_contest_cycle_or_raise(cycle_id)

    if cycle.status != ContestCycleStatus.ACTIVE:
        raise ContestCycleStateError(
            f"ContestCycle id={cycle_id} is in status '{cycle.status}'; "
            "only ACTIVE cycles can be completed."
        )

    actor = None
    if actor_id is not None:
        try:
            actor = _get_user_or_raise(actor_id)
        except UserNotFoundError:
            logger.warning("complete_contest_cycle: actor_id=%r not found; proceeding anyway.", actor_id)

    # Generate final snapshot before transitioning
    try:
        generate_leaderboard_snapshot(cycle_id=cycle.id, top_n=DEFAULT_LEADERBOARD_TOP_N)
        logger.info("Final leaderboard snapshot generated for ContestCycle %s.", cycle.id)
    except LeaderboardGenerationError as exc:
        # Log but do NOT block completion; manual snapshot can be run later
        logger.error(
            "Failed to generate final snapshot for ContestCycle %s: %s. "
            "Proceeding with completion regardless.",
            cycle.id,
            exc,
        )

    cycle.transition_to(ContestCycleStatus.COMPLETED, actor=actor)
    logger.info(
        "ContestCycle %s completed by actor=%s",
        cycle.id,
        getattr(actor, "pk", "system"),
    )
    return cycle


# ---------------------------------------------------------------------------
# Leaderboard Services
# ---------------------------------------------------------------------------

@transaction.atomic
def generate_leaderboard_snapshot(
    *,
    cycle_id: Any,
    scope: str = LeaderboardScope.GLOBAL,
    scope_ref: str = "",
    top_n: int = DEFAULT_LEADERBOARD_TOP_N,
) -> LeaderboardSnapshot:
    """
    Build and persist a ranked leaderboard snapshot for a ContestCycle.

    The function delegates the actual ranking computation to
    ``LeaderboardGenerator`` (which can be mocked in tests) and then
    validates and stores the result as a ``LeaderboardSnapshot``.

    Args:
        cycle_id:  PK of the ContestCycle to snapshot.
        scope:     One of LeaderboardScope values.
        scope_ref: Optional qualifier for non-GLOBAL scopes.
        top_n:     How many entries to capture.

    Returns:
        The finalized LeaderboardSnapshot.

    Raises:
        ContestCycleNotFoundError:  If cycle_id does not exist.
        LeaderboardGenerationError: On generation failure.
        ValidationError:            If snapshot data is malformed.
    """
    # --- Input validation ---
    if scope not in LeaderboardScope.values:
        raise LeaderboardGenerationError(
            f"Invalid scope '{scope}'. Valid choices: {LeaderboardScope.values}"
        )
    if not isinstance(top_n, int) or top_n < 1 or top_n > 1000:
        raise LeaderboardGenerationError(
            f"top_n must be an integer between 1 and 1000, got {top_n!r}."
        )
    if not isinstance(scope_ref, str):
        scope_ref = str(scope_ref)

    # Fetch cycle WITHOUT locking here (no state mutation on cycle in this function)
    try:
        cycle = ContestCycle.objects.get(pk=cycle_id)
    except ContestCycle.DoesNotExist:
        raise ContestCycleNotFoundError(
            f"ContestCycle with pk={cycle_id!r} does not exist."
        )
    except (ValueError, TypeError) as exc:
        raise GamificationServiceError(
            f"Invalid cycle_id={cycle_id!r}: {exc}"
        ) from exc

    # Create a PENDING snapshot record first so we have an ID to reference in logs/tasks
    snapshot = LeaderboardSnapshot.objects.create(
        contest_cycle=cycle,
        scope=scope,
        scope_ref=scope_ref,
        top_n=top_n,
        status=SnapshotStatus.PENDING,
    )
    logger.info(
        "LeaderboardSnapshot %s created (PENDING) for cycle=%s scope=%s top_n=%s",
        snapshot.id,
        cycle_id,
        scope,
        top_n,
    )

    try:
        from api.gamification import services as _svc_module
        LG = getattr(_svc_module, 'LeaderboardGenerator', LeaderboardGenerator)
        generator = LG(cycle=cycle, scope=scope, scope_ref=scope_ref)
        entries: list[dict] = generator.generate(top_n=top_n)

        if not isinstance(entries, list):
            raise LeaderboardGenerationError(
                f"LeaderboardGenerator.generate() returned {type(entries).__name__} "
                "instead of list."
            )

        # Validate each entry schema
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise LeaderboardGenerationError(
                    f"Entry at index {idx} is not a dict: {entry!r}"
                )
            missing = [k for k in ("rank", "user_id", "points") if k not in entry]
            if missing:
                raise LeaderboardGenerationError(
                    f"Entry at index {idx} missing keys: {missing}"
                )
            if not isinstance(entry.get("rank"), int) or entry["rank"] < 1:
                raise LeaderboardGenerationError(
                    f"Entry at index {idx} has invalid rank: {entry.get('rank')!r}"
                )
            if not isinstance(entry.get("points"), (int, float)) or entry["points"] < 0:
                raise LeaderboardGenerationError(
                    f"Entry at index {idx} has invalid points: {entry.get('points')!r}"
                )

        snapshot.snapshot_data = entries
        snapshot.finalize()

    except LeaderboardGenerationError as exc:
        snapshot.mark_failed(str(exc))
        raise
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        snapshot.mark_failed(error_msg)
        logger.exception(
            "Unexpected error generating snapshot %s: %s",
            snapshot.id,
            error_msg,
        )
        raise LeaderboardGenerationError(
            f"Unexpected error during snapshot generation: {error_msg}"
        ) from exc

    logger.info(
        "LeaderboardSnapshot %s finalized with %s entries.",
        snapshot.id,
        snapshot.entry_count,
    )
    return snapshot


def get_latest_snapshot(
    cycle_id: Any,
    *,
    scope: str = LeaderboardScope.GLOBAL,
    scope_ref: str = "",
) -> Optional[LeaderboardSnapshot]:
    """
    Retrieve the most recently finalized leaderboard snapshot for a cycle.

    Args:
        cycle_id:  PK of the ContestCycle.
        scope:     Leaderboard scope filter.
        scope_ref: Optional scope qualifier.

    Returns:
        The latest FINALIZED LeaderboardSnapshot, or None if none exists.

    Raises:
        GamificationServiceError: On invalid arguments.
    """
    if cycle_id is None:
        raise GamificationServiceError("cycle_id must not be None.")
    if scope not in LeaderboardScope.values:
        raise GamificationServiceError(
            f"Invalid scope '{scope}'. Valid choices: {LeaderboardScope.values}"
        )

    return (
        LeaderboardSnapshot.objects
        .filter(
            contest_cycle_id=cycle_id,
            scope=scope,
            scope_ref=scope_ref,
            status=SnapshotStatus.FINALIZED,
        )
        .order_by("-generated_at")
        .first()
    )


# ---------------------------------------------------------------------------
# Reward Services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_contest_reward(
    *,
    cycle_id: Any,
    title: str,
    reward_type: str,
    rank_from: int,
    rank_to: int,
    reward_value: Decimal = Decimal("0.00"),
    description: str = "",
    total_budget: Optional[int] = None,
    image_url: str = "",
    metadata: Optional[dict] = None,
) -> ContestReward:
    """
    Create a new ContestReward definition for a given ContestCycle.

    Args:
        cycle_id:     PK of the owning ContestCycle.
        title:        Display title for the reward.
        reward_type:  One of RewardType choices.
        rank_from:    Inclusive lower rank bound (1-based).
        rank_to:      Inclusive upper rank bound.
        reward_value: Numeric value of the reward.
        description:  Optional description.
        total_budget: Optional issuance cap.
        image_url:    Optional reward image URL.
        metadata:     Arbitrary extra configuration.

    Returns:
        The saved ContestReward instance.

    Raises:
        ContestCycleNotFoundError: If cycle_id does not exist.
        GamificationServiceError:  On invalid input.
        ValidationError:           On model constraint violations.
    """
    from api.gamification.choices import RewardType

    # --- Input guards ---
    if not title or not isinstance(title, str) or not title.strip():
        raise GamificationServiceError("title must be a non-empty string.")

    if reward_type not in RewardType.values:
        raise GamificationServiceError(
            f"Invalid reward_type '{reward_type}'. Valid choices: {RewardType.values}"
        )

    for param_name, param_val in (("rank_from", rank_from), ("rank_to", rank_to)):
        if not isinstance(param_val, int) or param_val < 1 or param_val > MAX_RANK_VALUE:
            raise GamificationServiceError(
                f"{param_name} must be an integer between 1 and {MAX_RANK_VALUE}, "
                f"got {param_val!r}."
            )

    if rank_from > rank_to:
        raise GamificationServiceError(
            f"rank_from ({rank_from}) must be <= rank_to ({rank_to})."
        )

    try:
        value = Decimal(str(reward_value))
        if value < 0:
            raise GamificationServiceError("reward_value must be non-negative.")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GamificationServiceError(
            f"Invalid reward_value {reward_value!r}: {exc}"
        ) from exc

    if total_budget is not None and (
        not isinstance(total_budget, int) or total_budget < 1
    ):
        raise GamificationServiceError(
            "total_budget must be a positive integer or None."
        )

    # Fetch cycle (no lock needed; we're just FK-ing to it)
    try:
        cycle = ContestCycle.objects.get(pk=cycle_id)
    except ContestCycle.DoesNotExist:
        raise ContestCycleNotFoundError(
            f"ContestCycle pk={cycle_id!r} does not exist."
        )

    reward = ContestReward(
        contest_cycle=cycle,
        title=title.strip(),
        reward_type=reward_type,
        rank_from=rank_from,
        rank_to=rank_to,
        reward_value=value,
        description=(description or "").strip(),
        total_budget=total_budget,
        image_url=(image_url or "").strip(),
        metadata=metadata if isinstance(metadata, dict) else {},
    )

    reward.full_clean()
    reward.save()

    logger.info(
        "ContestReward created: id=%s title=%r type=%s rank=%s–%s cycle=%s",
        reward.id,
        reward.title,
        reward.reward_type,
        rank_from,
        rank_to,
        cycle_id,
    )
    return reward


# ---------------------------------------------------------------------------
# Achievement Services
# ---------------------------------------------------------------------------

@transaction.atomic
def award_achievement(
    *,
    user_id: Any,
    achievement_type: str,
    title: str,
    points: int = 0,
    cycle_id: Optional[Any] = None,
    reward_id: Optional[Any] = None,
    rank: Optional[int] = None,
    description: str = "",
    metadata: Optional[dict] = None,
) -> UserAchievement:
    """
    Grant a gamification achievement to a user and credit any associated points.

    This function is idempotent with respect to the unique constraints on
    UserAchievement: if an identical award already exists it is returned as-is
    without raising an error (unless it was created in a failed/un-awarded state,
    in which case it is completed).

    Args:
        user_id:          PK of the user receiving the achievement.
        achievement_type: One of AchievementType choices.
        title:            Human-readable achievement title.
        points:           Points to credit (0 for badge-only achievements).
        cycle_id:         PK of the ContestCycle scope, or None for global.
        reward_id:        PK of an associated ContestReward, or None.
        rank:             User's leaderboard rank at time of award (optional).
        description:      Optional description text.
        metadata:         Arbitrary context (snapshot id, score, etc.).

    Returns:
        The UserAchievement instance (newly created or pre-existing).

    Raises:
        UserNotFoundError:         If user_id does not exist.
        ContestCycleNotFoundError: If cycle_id is provided but does not exist.
        InvalidPointsError:        If points is out of range.
        GamificationServiceError:  On other validation failures.
        DuplicateAchievementError: If a conflicting awarded achievement exists
                                   and cannot be safely idempotency-merged.
    """
    # --- Input guards ---
    if achievement_type not in AchievementType.values:
        raise GamificationServiceError(
            f"Invalid achievement_type '{achievement_type}'. "
            f"Valid choices: {AchievementType.values}"
        )
    if not title or not isinstance(title, str) or not title.strip():
        raise GamificationServiceError("title must be a non-empty string.")

    validated_points = _validate_points(points)

    if rank is not None and (not isinstance(rank, int) or rank < 1 or rank > MAX_RANK_VALUE):
        raise GamificationServiceError(
            f"rank must be a positive integer up to {MAX_RANK_VALUE}, got {rank!r}."
        )

    user = _get_user_or_raise(user_id)

    cycle = None
    if cycle_id is not None:
        cycle = _get_contest_cycle_or_raise(cycle_id)

    reward = None
    if reward_id is not None:
        try:
            reward = ContestReward.objects.select_for_update().get(pk=reward_id)
        except ContestReward.DoesNotExist:
            raise GamificationServiceError(
                f"ContestReward pk={reward_id!r} does not exist."
            )

    # --- Idempotency check ---
    existing_qs = UserAchievement.objects.select_for_update().filter(
        user=user,
        achievement_type=achievement_type,
        contest_cycle=cycle,
    )
    existing = existing_qs.first()

    if existing is not None:
        if existing.is_awarded:
            logger.info(
                "award_achievement: idempotent return for user=%s type=%s cycle=%s",
                user_id,
                achievement_type,
                cycle_id,
            )
            return existing
        # Existing un-awarded record: complete it now
        existing.title = title.strip()
        existing.description = (description or "").strip()
        existing.metadata = metadata if isinstance(metadata, dict) else {}
        if reward:
            existing.contest_reward = reward
        existing.award(points=validated_points, rank=rank)

        if reward:
            reward.increment_issued_count()

        logger.info(
            "award_achievement: completed pre-existing pending achievement id=%s for user=%s",
            existing.id,
            user_id,
        )
        return existing

    # --- Create and award new achievement ---
    achievement = UserAchievement(
        user=user,
        contest_cycle=cycle,
        contest_reward=reward,
        achievement_type=achievement_type,
        title=title.strip(),
        description=(description or "").strip(),
        metadata=metadata if isinstance(metadata, dict) else {},
    )

    try:
        achievement.full_clean()
        achievement.save()
    except IntegrityError as exc:
        # Race condition: another process already created this achievement
        raise DuplicateAchievementError(
            f"Concurrent award_achievement call for user={user_id} "
            f"type={achievement_type} cycle={cycle_id}: {exc}"
        ) from exc

    achievement.award(points=validated_points, rank=rank)

    if reward:
        reward.increment_issued_count()

    logger.info(
        "award_achievement: user=%s type=%s points=%s achievement=%s",
        getattr(achievement, "user_id", "?"),
        getattr(achievement, "achievement_type", "?"),
        getattr(achievement, "points_awarded", 0),
        getattr(achievement, "id", "?"),
    )

    # Record performance metric on the model instance (wires TimestampedModel.record_performance_metric)
    try:
        achievement.record_performance_metric("achievement_awarded", 1.0, tags={"type": achievement_type})
    except Exception:
        pass  # metric recording is non-critical

    return achievement


# ---------------------------------------------------------------------------
# Convenience functions for new service classes
# ---------------------------------------------------------------------------

def check_and_award_user_badges(user_id: Any, **kwargs) -> int:
    """
    Convenience function to check and award eligible badges for a user.
    
    Args:
        user_id: User identifier
        **kwargs: Additional parameters for badge eligibility checking
        
    Returns:
        Number of badges awarded
    """
    awarded_badges = BadgeService.award_eligible_badges(user_id=user_id, **kwargs)
    return len(awarded_badges)


def update_user_streak(user_id: Any, **kwargs) -> Tuple[int, bool]:
    """
    Convenience function to update user streak activity.
    
    Args:
        user_id: User identifier
        **kwargs: Additional parameters for streak update
        
    Returns:
        Tuple of (current_streak_days, was_extended)
    """
    streak, was_extended, days_added = StreakService.update_user_activity(user_id=user_id, **kwargs)
    return streak.current_days, was_extended


def check_user_level_up(user_id: Any, old_points: int, new_points: int, **kwargs) -> Optional[int]:
    """
    Convenience function to check and handle user level progression.
    
    Args:
        user_id: User identifier
        old_points: Previous total points
        new_points: New total points
        **kwargs: Additional parameters for level checking
        
    Returns:
        New level number if leveled up, None otherwise
    """
    old_level, new_level, did_level_up = LevelUpService.check_level_up(
        user_id=user_id, old_points=old_points, new_points=new_points, **kwargs
    )
    return new_level.level_number if did_level_up else None


def start_user_daily_challenges(user_id: Any) -> int:
    """
    Convenience function to auto-start all active daily challenges for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Number of challenges started
    """
    started_challenges = DailyChallengeService.auto_start_active_challenges(user_id=user_id)
    return len(started_challenges)


def get_user_gamification_summary(user_id: Any) -> Dict[str, Any]:
    """
    Convenience function to get a comprehensive gamification summary for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Dictionary with comprehensive gamification statistics
    """
    try:
        # Get badge statistics
        badge_stats = BadgeService.get_badge_statistics(user_id=user_id)
        
        # Get streak statistics
        streak_stats = StreakService.get_streak_statistics(user_id=user_id)
        
        # Get level statistics
        level_stats = LevelUpService.get_level_statistics(user_id=user_id)
        
        # Get recent challenges
        recent_challenges = DailyChallengeService.get_user_challenge_progress(
            user_id=user_id, limit=5
        )
        
        return {
            "user_id": user_id,
            "badges": badge_stats,
            "streak": streak_stats,
            "level": level_stats,
            "recent_challenges": [
                {
                    "challenge_id": uc.challenge.id,
                    "title": uc.challenge.title,
                    "progress": uc.progress,
                    "target": uc.challenge.target_count,
                    "completed": uc.is_completed,
                    "bonus_points": uc.challenge.bonus_points,
                }
                for uc in recent_challenges
            ],
        }
        
    except UserNotFoundError:
        return {"user_id": user_id, "error": "User not found"}


@transaction.atomic
def batch_award_achievements(
    awards: Sequence[dict],
    *,
    cycle_id: Optional[Any] = None,
    stop_on_first_error: bool = False,
) -> dict[str, Any]:
    """
    Award achievements to multiple users in a single atomic operation.

    Each item in *awards* must be a dict matching the keyword arguments of
    ``award_achievement`` (minus ``cycle_id`` which is supplied separately).

    Args:
        awards:              Sequence of award specification dicts.
        cycle_id:            Optional ContestCycle scope applied to all awards.
        stop_on_first_error: If True, the entire batch is rolled back on the
                             first error. If False (default), errors are
                             collected and partial results returned.

    Returns:
        A dict with keys:
        - "succeeded": list of UserAchievement instances successfully awarded.
        - "failed":    list of {"index": int, "spec": dict, "error": str} for failures.
        - "total":     total number of input awards.

    Raises:
        GamificationServiceError: If awards is not a sequence or exceeds MAX_BATCH_AWARD_SIZE.
    """
    if not isinstance(awards, (list, tuple)):
        raise GamificationServiceError(
            f"awards must be a list or tuple, got {type(awards).__name__}."
        )

    if len(awards) == 0:
        logger.debug("batch_award_achievements called with empty awards list; nothing to do.")
        return {"succeeded": [], "failed": [], "total": 0}

    if len(awards) > MAX_BATCH_AWARD_SIZE:
        raise GamificationServiceError(
            f"batch_award_achievements received {len(awards)} awards, "
            f"which exceeds the maximum batch size of {MAX_BATCH_AWARD_SIZE}. "
            "Split into smaller batches."
        )

    succeeded: list[UserAchievement] = []
    failed: list[dict] = []

    for idx, spec in enumerate(awards):
        if not isinstance(spec, dict):
            error_detail = f"Award at index {idx} is not a dict: {spec!r}"
            if stop_on_first_error:
                raise GamificationServiceError(error_detail)
            failed.append({"index": idx, "spec": spec, "error": error_detail})
            continue

        try:
            # Each individual award runs in its own savepoint so a failure
            # doesn't necessarily abort the whole outer transaction.
            with transaction.atomic():
                achievement = award_achievement(
                    cycle_id=cycle_id,
                    **spec,
                )
            succeeded.append(achievement)
        except (
            GamificationServiceError,
            InvalidPointsError,
            DuplicateAchievementError,
            UserNotFoundError,
            ValidationError,
        ) as exc:
            error_detail = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "batch_award_achievements: award at index %d failed: %s",
                idx,
                error_detail,
            )
            if stop_on_first_error:
                raise GamificationServiceError(
                    f"Batch aborted at index {idx}: {error_detail}"
                ) from exc
            failed.append({"index": idx, "spec": spec, "error": error_detail})

    logger.info(
        "batch_award_achievements complete: %d succeeded, %d failed out of %d total.",
        len(succeeded),
        len(failed),
        len(awards),
    )
    return {
        "succeeded": succeeded,
        "failed": failed,
        "total": len(awards),
    }


# ---------------------------------------------------------------------------
# User Points Summary
# ---------------------------------------------------------------------------

def get_user_total_points(
    user_id: Any,
    *,
    cycle_id: Optional[Any] = None,
) -> int:
    """
    Calculate the total awarded points for a user, optionally scoped to a cycle.

    Args:
        user_id:  PK of the user.
        cycle_id: Optional ContestCycle pk to narrow the query.

    Returns:
        Total integer points (0 if the user has no achievements).

    Raises:
        UserNotFoundError:         If user_id does not exist.
        ContestCycleNotFoundError: If cycle_id is provided but not found.
    """
    _get_user_or_raise(user_id)  # validates existence

    if cycle_id is not None:
        # Validate cycle exists
        if not ContestCycle.objects.filter(pk=cycle_id).exists():
            raise ContestCycleNotFoundError(
                f"ContestCycle pk={cycle_id!r} does not exist."
            )

    qs = UserAchievement.objects.filter(user_id=user_id, is_awarded=True)
    if cycle_id is not None:
        qs = qs.filter(contest_cycle_id=cycle_id)

    result = qs.aggregate(total=Sum("points_awarded"))
    total = result.get("total") or 0

    if not isinstance(total, int):
        try:
            total = int(total)
        except (TypeError, ValueError):
            logger.error(
                "get_user_total_points: unexpected aggregate type %s for user=%s cycle=%s",
                type(total).__name__,
                user_id,
                cycle_id,
            )
            total = 0

    logger.debug(
        "get_user_total_points: user=%s cycle=%s → %d pts",
        user_id,
        cycle_id,
        total,
    )
    return total


def get_user_rank_in_cycle(user_id: Any, cycle_id: Any) -> Optional[int]:
    """
    Determine a user's current rank within a ContestCycle based on total
    awarded points.

    Rank is 1-based; users with equal points receive equal rank (dense ranking).

    Args:
        user_id:  PK of the user.
        cycle_id: PK of the ContestCycle.

    Returns:
        Integer rank (1 = top), or None if the user has no points in the cycle.

    Raises:
        UserNotFoundError:         If user_id does not exist.
        ContestCycleNotFoundError: If cycle_id does not exist.
    """
    _get_user_or_raise(user_id)

    if not ContestCycle.objects.filter(pk=cycle_id).exists():
        raise ContestCycleNotFoundError(
            f"ContestCycle pk={cycle_id!r} does not exist."
        )

    # Compute this user's total first
    user_totals = (
        UserAchievement.objects
        .filter(contest_cycle_id=cycle_id, is_awarded=True)
        .values("user_id")
        .annotate(total_points=Sum("points_awarded"))
    )

    # Use list slicing instead of .first() to avoid annotated queryset error
    _rows = list(user_totals.filter(user_id=user_id)[:1])
    user_score_row = _rows[0] if _rows else None
    if user_score_row is None:
        logger.debug(
            "get_user_rank_in_cycle: user=%s has no points in cycle=%s",
            user_id,
            cycle_id,
        )
        return None

    user_score = user_score_row["total_points"] or 0

    # Dense rank: count how many distinct users have STRICTLY more points
    users_above = user_totals.filter(total_points__gt=user_score).values("user_id").distinct().count()
    rank = users_above + 1

    logger.debug(
        "get_user_rank_in_cycle: user=%s cycle=%s score=%s rank=%s",
        user_id,
        cycle_id,
        user_score,
        rank,
    )
    return rank


# ---------------------------------------------------------------------------
# Reward Distribution Services
# ---------------------------------------------------------------------------

@transaction.atomic
def distribute_cycle_rewards(cycle_id: Any) -> dict[str, Any]:
    """
    Distribute configured ContestRewards to eligible participants at the end
    of a ContestCycle.

    This function:
    1. Fetches the latest finalized leaderboard snapshot for the cycle.
    2. Iterates over each active ContestReward for the cycle.
    3. For each entry in the snapshot whose rank falls within a reward's window,
       calls ``award_achievement`` for the corresponding user.
    4. Respects budget caps and skips exhausted rewards.

    Args:
        cycle_id: PK of a COMPLETED ContestCycle.

    Returns:
        Dict with "awarded_count", "skipped_count", "errors" keys.

    Raises:
        ContestCycleNotFoundError: If cycle_id does not exist.
        ContestCycleStateError:    If the cycle is not COMPLETED.
        LeaderboardGenerationError: If no finalized snapshot is available.
    """
    cycle = _get_contest_cycle_or_raise(cycle_id)

    if cycle.status != ContestCycleStatus.COMPLETED:
        raise ContestCycleStateError(
            f"distribute_cycle_rewards requires a COMPLETED cycle; "
            f"cycle id={cycle_id} is '{cycle.status}'."
        )

    snapshot = get_latest_snapshot(cycle_id=cycle_id)
    if snapshot is None:
        raise LeaderboardGenerationError(
            f"No finalized leaderboard snapshot found for ContestCycle id={cycle_id}. "
            "Run generate_leaderboard_snapshot first."
        )

    entries: list[dict] = snapshot.snapshot_data
    if not entries:
        logger.warning(
            "distribute_cycle_rewards: snapshot %s for cycle %s has no entries.",
            snapshot.id,
            cycle_id,
        )
        return {"awarded_count": 0, "skipped_count": 0, "errors": []}

    rewards = list(
        ContestReward.objects.select_for_update()
        .filter(contest_cycle=cycle, is_active=True)
        .order_by("rank_from")
    )

    if not rewards:
        logger.info(
            "distribute_cycle_rewards: no active rewards configured for cycle %s.",
            cycle_id,
        )
        return {"awarded_count": 0, "skipped_count": 0, "errors": []}

    awarded_count = 0
    skipped_count = 0
    errors: list[dict] = []

    for entry in entries:
        rank = entry.get("rank")
        entry_user_id = entry.get("user_id")
        entry_points = entry.get("points", 0)

        if not isinstance(rank, int) or rank < 1:
            logger.warning(
                "distribute_cycle_rewards: invalid rank in snapshot entry: %r; skipping.",
                entry,
            )
            skipped_count += 1
            continue

        if entry_user_id is None:
            logger.warning(
                "distribute_cycle_rewards: null user_id at rank %d; skipping.",
                rank,
            )
            skipped_count += 1
            continue

        for reward in rewards:
            if not reward.covers_rank(rank):
                continue

            if reward.is_exhausted:
                logger.info(
                    "distribute_cycle_rewards: reward %s exhausted; skipping user %s at rank %d.",
                    reward.id,
                    entry_user_id,
                    rank,
                )
                skipped_count += 1
                continue

            try:
                with transaction.atomic():
                    award_achievement(
                        user_id=entry_user_id,
                        achievement_type=AchievementType.RANK_REWARD,
                        title=reward.title,
                        description=reward.description,
                        points=int(entry_points),
                        cycle_id=cycle_id,
                        reward_id=reward.id,
                        rank=rank,
                        metadata={
                            "snapshot_id": str(snapshot.id),
                            "reward_type": reward.reward_type,
                            "reward_value": str(reward.reward_value),
                        },
                    )
                awarded_count += 1
            except DuplicateAchievementError:
                logger.debug(
                    "distribute_cycle_rewards: achievement already awarded for "
                    "user=%s cycle=%s rank=%d; skipping.",
                    entry_user_id,
                    cycle_id,
                    rank,
                )
                skipped_count += 1
            except (GamificationServiceError, InvalidPointsError, UserNotFoundError) as exc:
                error_detail = f"{type(exc).__name__}: {exc}"
                logger.error(
                    "distribute_cycle_rewards: failed for user=%s rank=%d reward=%s: %s",
                    entry_user_id,
                    rank,
                    reward.id,
                    error_detail,
                )
                errors.append({
                    "user_id": entry_user_id,
                    "rank": rank,
                    "reward_id": str(reward.id),
                    "error": error_detail,
                })

    logger.info(
        "distribute_cycle_rewards complete for cycle %s: "
        "awarded=%d skipped=%d errors=%d",
        cycle_id,
        awarded_count,
        skipped_count,
        len(errors),
    )
    return {
        "awarded_count": awarded_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Notification Services
# ---------------------------------------------------------------------------

@transaction.atomic
def mark_achievements_notified(achievement_ids: Sequence[Any]) -> int:
    """
    Bulk-mark a collection of UserAchievement records as notified.

    Args:
        achievement_ids: Sequence of UserAchievement primary keys.

    Returns:
        Number of records actually updated.

    Raises:
        GamificationServiceError: If achievement_ids is not a sequence or is empty.
    """
    if not isinstance(achievement_ids, (list, tuple, set)):
        raise GamificationServiceError(
            f"achievement_ids must be a list/tuple/set, got {type(achievement_ids).__name__}."
        )

    # Deduplicate
    unique_ids = list(set(achievement_ids))

    if not unique_ids:
        return 0  # Nothing to mark

    now = timezone.now()
    updated = UserAchievement.objects.filter(
        pk__in=unique_ids,
        is_notified=False,
        is_awarded=True,
    ).update(is_notified=True, notified_at=now, updated_at=now)

    logger.info(
        "mark_achievements_notified: %d/%d records updated.",
        updated,
        len(unique_ids),
    )
    return updated


# ---------------------------------------------------------------------------
# UserPoints Service Functions
# ---------------------------------------------------------------------------

def get_or_create_user_points(user_id: str) -> UserPoints:
    """
    Get or create UserPoints record for a user.
    
    Args:
        user_id: User ID to get/create points for
        
    Returns:
        UserPoints instance
    """
    user_points, created = UserPoints.objects.get_or_create(
        user_id=user_id,
        defaults={
            "total_points": 0,
            "lifetime_points": 0,
            "points_this_month": 0,
            "points_this_week": 0,
        }
    )
    
    if created:
        logger.info(f"Created UserPoints for user {user_id}")
    
    return user_points


def add_points_to_user(user_id: str, amount: int, source: str = "manual", 
                      description: str = "", source_id: str = "") -> UserPoints:
    """
    Add points to a user's balance.
    
    Args:
        user_id: User ID to add points to
        amount: Positive amount of points to add
        source: Source of points (offer, referral, streak, etc.)
        description: Optional description
        source_id: Optional reference ID
        
    Returns:
        Updated UserPoints instance
        
    Raises:
        InvalidPointsError: If amount is invalid
        UserNotFoundError: If user doesn't exist
    """
    if amount <= 0:
        raise InvalidPointsError("Points amount must be positive")
    
    try:
        user_points = get_or_create_user_points(user_id)
        user_points.add_points(amount, source, description)
        
        logger.info(f"Added {amount} points to user {user_id} from {source}")
        return user_points
        
    except Exception as e:
        logger.error(f"Failed to add points to user {user_id}: {e}")
        raise GamificationServiceError(f"Failed to add points: {e}")


def deduct_points_from_user(user_id: str, amount: int, source: str = "manual",
                           description: str = "", source_id: str = "") -> UserPoints:
    """
    Deduct points from a user's balance.
    
    Args:
        user_id: User ID to deduct points from
        amount: Positive amount of points to deduct
        source: Source of deduction (penalty, etc.)
        description: Optional description
        source_id: Optional reference ID
        
    Returns:
        Updated UserPoints instance
        
    Raises:
        InvalidPointsError: If amount is invalid
        UserNotFoundError: If user doesn't exist
    """
    if amount <= 0:
        raise InvalidPointsError("Points amount must be positive")
    
    try:
        user_points = get_or_create_user_points(user_id)
        user_points.deduct_points(amount, source, description)
        
        logger.info(f"Deducted {amount} points from user {user_id} for {source}")
        return user_points
        
    except Exception as e:
        logger.error(f"Failed to deduct points from user {user_id}: {e}")
        raise GamificationServiceError(f"Failed to deduct points: {e}")


def get_user_points_summary(user_id: str) -> Dict[str, Any]:
    """
    Get comprehensive points summary for a user.
    
    Args:
        user_id: User ID to get summary for
        
    Returns:
        Dictionary with points summary
        
    Raises:
        UserNotFoundError: If user doesn't exist
    """
    try:
        user_points = UserPoints.objects.get(user_id=user_id)
        
        # Get transaction summary
        transactions = PointsTransaction.objects.filter(user_id=user_id)
        total_earned = transactions.filter(amount__gt=0).aggregate(total=Sum("amount"))["total"] or 0
        total_deducted = abs(transactions.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"] or 0)
        
        return {
            "user_id": user_id,
            "total_points": user_points.total_points,
            "lifetime_points": user_points.lifetime_points,
            "points_this_month": user_points.points_this_month,
            "points_this_week": user_points.points_this_week,
            "monthly_rank": user_points.monthly_rank,
            "weekly_rank": user_points.weekly_rank,
            "total_earned": total_earned,
            "total_deducted": total_deducted,
            "transaction_count": transactions.count(),
            "last_updated": user_points.last_updated,
        }
        
    except UserPoints.DoesNotExist:
        raise UserNotFoundError(f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Failed to get points summary for user {user_id}: {e}")
        raise GamificationServiceError(f"Failed to get points summary: {e}")


# ---------------------------------------------------------------------------
# PointsTransaction Service Functions
# ---------------------------------------------------------------------------

def get_user_transactions(user_id: str, limit: int = 100, 
                          source: Optional[str] = None) -> Sequence[PointsTransaction]:
    """
    Get transaction history for a user.
    
    Args:
        user_id: User ID to get transactions for
        limit: Maximum number of transactions to return
        source: Optional source filter
        
    Returns:
        List of PointsTransaction instances
    """
    queryset = PointsTransaction.objects.filter(user_id=user_id)
    
    if source:
        queryset = queryset.filter(source=source)
    
    return queryset.order_by("-created_at")[:limit]


def create_points_transaction(user_id: str, amount: int, source: str,
                              description: str = "", source_id: str = "",
                              balance_after: Optional[int] = None) -> PointsTransaction:
    """
    Create a points transaction record.
    
    Args:
        user_id: User ID for the transaction
        amount: Transaction amount (positive=earn, negative=deduct)
        source: Source of transaction
        description: Optional description
        source_id: Optional reference ID
        balance_after: Balance after transaction (calculated if not provided)
        
    Returns:
        Created PointsTransaction instance
    """
    if balance_after is None:
        try:
            user_points = get_or_create_user_points(user_id)
            balance_after = user_points.total_points + amount
        except:
            balance_after = 0
    
    transaction = PointsTransaction.objects.create(
        user_id=user_id,
        amount=amount,
        source=source,
        source_id=source_id,
        description=description or f"{source.title()} transaction",
        balance_after=balance_after,
    )
    
    logger.info(f"Created points transaction: {transaction.id} for user {user_id}")
    return transaction


# ---------------------------------------------------------------------------
# StreakFreeze Service Functions
# ---------------------------------------------------------------------------

def use_streak_freeze(user_id: str, streak_id: str, used_at: str, 
                      reason: str = "") -> StreakFreeze:
    """
    Use a streak freeze for a user.
    
    Args:
        user_id: User ID using the freeze
        streak_id: Streak ID to protect
        used_at: Date to use freeze for
        reason: Optional reason for using freeze
        
    Returns:
        Created StreakFreeze instance
        
    Raises:
        UserNotFoundError: If user doesn't exist
        GamificationServiceError: If freeze cannot be used
    """
    try:
        # Check if freeze already exists for this date
        existing = StreakFreeze.objects.filter(
            user_id=user_id, 
            used_at=used_at
        ).first()
        
        if existing:
            raise GamificationServiceError(f"Freeze already used for {used_at}")
        
        freeze = StreakFreeze.objects.create(
            user_id=user_id,
            streak_id=streak_id,
            used_at=used_at,
            reason=reason,
        )
        
        logger.info(f"Used streak freeze for user {user_id} on {used_at}")
        return freeze
        
    except Exception as e:
        logger.error(f"Failed to use streak freeze for user {user_id}: {e}")
        raise GamificationServiceError(f"Failed to use streak freeze: {e}")


def get_user_streak_freezes(user_id: str, limit: int = 50) -> Sequence[StreakFreeze]:
    """
    Get streak freeze history for a user.
    
    Args:
        user_id: User ID to get freezes for
        limit: Maximum number of freezes to return
        
    Returns:
        List of StreakFreeze instances
    """
    return StreakFreeze.objects.filter(
        user_id=user_id
    ).order_by("-used_at")[:limit]


# ---------------------------------------------------------------------------
# ContestParticipant Service Functions
# ---------------------------------------------------------------------------

def join_contest(user_id: str, contest_cycle_id: str) -> ContestParticipant:
    """
    Join a user to a contest cycle.
    
    Args:
        user_id: User ID joining the contest
        contest_cycle_id: Contest cycle ID to join
        
    Returns:
        Created ContestParticipant instance
        
    Raises:
        ContestCycleNotFoundError: If contest doesn't exist
        GamificationServiceError: If user cannot join
    """
    try:
        # Check if contest exists and is active
        contest = ContestCycle.objects.get(id=contest_cycle_id)
        if contest.status != ContestCycleStatus.ACTIVE:
            raise GamificationServiceError("Contest is not active")
        
        # Check if already participating
        existing = ContestParticipant.objects.filter(
            user_id=user_id,
            contest_cycle_id=contest_cycle_id
        ).first()
        
        if existing:
            return existing
        
        participant = ContestParticipant.objects.create(
            user_id=user_id,
            contest_cycle_id=contest_cycle_id,
        )
        
        logger.info(f"User {user_id} joined contest {contest_cycle_id}")
        return participant
        
    except ContestCycle.DoesNotExist:
        raise ContestCycleNotFoundError(f"Contest {contest_cycle_id} not found")
    except Exception as e:
        logger.error(f"Failed to join contest: {e}")
        raise GamificationServiceError(f"Failed to join contest: {e}")


def add_contest_points(participant_id: str, amount: int) -> ContestParticipant:
    """
    Add points to a contest participant.
    
    Args:
        participant_id: ContestParticipant ID
        amount: Points to add (must be positive)
        
    Returns:
        Updated ContestParticipant instance
        
    Raises:
        InvalidPointsError: If amount is invalid
        GamificationServiceError: If points cannot be added
    """
    if amount <= 0:
        raise InvalidPointsError("Points amount must be positive")
    
    try:
        participant = ContestParticipant.objects.get(id=participant_id)
        participant.add_points(amount)
        
        logger.info(f"Added {amount} points to participant {participant_id}")
        return participant
        
    except ContestParticipant.DoesNotExist:
        raise GamificationServiceError(f"Participant {participant_id} not found")
    except Exception as e:
        logger.error(f"Failed to add contest points: {e}")
        raise GamificationServiceError(f"Failed to add contest points: {e}")


def get_contest_leaderboard(contest_cycle_id: str, limit: int = 100) -> Sequence[ContestParticipant]:
    """
    Get leaderboard for a contest cycle.
    
    Args:
        contest_cycle_id: Contest cycle ID
        limit: Maximum number of participants to return
        
    Returns:
        List of ContestParticipant instances ordered by points
    """
    return ContestParticipant.objects.filter(
        contest_cycle_id=contest_cycle_id,
        is_disqualified=False
    ).order_by("-current_points")[:limit]


# ---------------------------------------------------------------------------
# GamificationConfig Service Functions
# ---------------------------------------------------------------------------

def get_gamification_config(tenant_id: str) -> GamificationConfig:
    """
    Get or create gamification config for a tenant.
    
    Args:
        tenant_id: Tenant ID to get config for
        
    Returns:
        GamificationConfig instance
    """
    return GamificationConfig.get_for_tenant(tenant_id)


def update_gamification_config(tenant_id: str, **kwargs) -> GamificationConfig:
    """
    Update gamification config for a tenant.
    
    Args:
        tenant_id: Tenant ID to update config for
        **kwargs: Fields to update
        
    Returns:
        Updated GamificationConfig instance
    """
    config = get_gamification_config(tenant_id)
    
    for field, value in kwargs.items():
        if hasattr(config, field):
            setattr(config, field, value)
    
    config.save()
    logger.info(f"Updated gamification config for tenant {tenant_id}")
    return config


def is_feature_enabled(tenant_id: str, feature: str) -> bool:
    """
    Check if a gamification feature is enabled for a tenant.
    
    Args:
        tenant_id: Tenant ID to check
        feature: Feature name (contests, badges, streaks, levels, daily_challenges)
        
    Returns:
        True if feature is enabled, False otherwise
    """
    try:
        config = get_gamification_config(tenant_id)
        feature_field = f"enable_{feature}"
        return getattr(config, feature_field, False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GamificationInsight Service Functions
# ---------------------------------------------------------------------------

def calculate_daily_insights(date: Optional[str] = None) -> GamificationInsight:
    """
    Calculate and save daily gamification insights.
    
    Args:
        date: Date to calculate insights for (defaults to today)
        
    Returns:
        Created/updated GamificationInsight instance
    """
    if date:
        from datetime import datetime
        date = datetime.strptime(date, "%Y-%m-%d").date()
    
    return GamificationInsight.calculate_daily_metrics(date)


def get_insights_summary(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Get insights summary for a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        
    Returns:
        Dictionary with summary statistics
    """
    from datetime import datetime
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        insights = GamificationInsight.objects.filter(
            date__range=[start, end]
        ).order_by("date")
        
        if not insights:
            return {"period": f"{start_date} to {end_date}", "data": []}
        
        summary = {
            "period": f"{start_date} to {end_date}",
            "total_days": insights.count(),
            "total_active_users": sum(i.active_users for i in insights),
            "total_badges_awarded": sum(i.badges_awarded for i in insights),
            "total_challenges_completed": sum(i.challenges_completed for i in insights),
            "total_points_issued": sum(i.total_points_issued for i in insights),
            "total_contest_participants": sum(i.contest_participants for i in insights),
            "total_streak_milestones": sum(i.streak_milestones for i in insights),
            "average_engagement_rate": sum(i.engagement_rate for i in insights) / len(insights),
            "daily_data": [
                {
                    "date": str(i.date),
                    "active_users": i.active_users,
                    "badges_awarded": i.badges_awarded,
                    "challenges_completed": i.challenges_completed,
                    "total_points_issued": i.total_points_issued,
                    "contest_participants": i.contest_participants,
                    "streak_milestones": i.streak_milestones,
                    "engagement_rate": i.engagement_rate,
                }
                for i in insights
            ]
        }
        
        return summary
        
    except ValueError as e:
        raise GamificationServiceError(f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Failed to get insights summary: {e}")
        raise GamificationServiceError(f"Failed to get insights summary: {e}")
