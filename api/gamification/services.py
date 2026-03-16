"""
Gamification Services — Core business logic layer.

All public functions in this module are the ONLY authorised entry-points for
mutating gamification state. Views, tasks, management commands, and signals
must go through this layer — never write directly to gamification models from
outside this module.

Design principles:
- Every public function runs inside an atomic transaction.
- Every function validates its inputs before touching the database.
- Every function emits structured log lines at INFO/DEBUG/WARNING/ERROR.
- No function silently swallows exceptions; they either re-raise or convert to
  domain-specific exceptions defined in exceptions.py.
- Type hints everywhere; no implicit Any.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F, Sum, Max, Count
from django.utils import timezone

from .choices import (
    ContestCycleStatus,
    AchievementType,
    LeaderboardScope,
    SnapshotStatus,
)
from .constants import (
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    DEFAULT_LEADERBOARD_TOP_N,
    LEADERBOARD_CACHE_TTL_SECONDS,
    MAX_BATCH_AWARD_SIZE,
)
from .exceptions import (
    ContestCycleNotFoundError,
    ContestCycleStateError,
    InvalidPointsError,
    DuplicateAchievementError,
    RewardAlreadyClaimedError,
    LeaderboardGenerationError,
    UserNotFoundError,
    GamificationServiceError,
)
from .models import ContestCycle, LeaderboardSnapshot, ContestReward, UserAchievement
from .utils.point_calculator import PointCalculator
from .utils.leaderboard_generator import LeaderboardGenerator

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
    return cycle


@transaction.atomic
def activate_contest_cycle(cycle_id: Any, *, actor_id: Optional[Any] = None) -> ContestCycle:
    """
    Transition a DRAFT ContestCycle to ACTIVE.

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
    cycle = _get_contest_cycle_or_raise(cycle_id)

    if cycle.status != ContestCycleStatus.DRAFT:
        raise ContestCycleStateError(
            f"ContestCycle id={cycle_id} is in status '{cycle.status}'; "
            "only DRAFT cycles can be activated."
        )

    # Guard: check for any existing ACTIVE cycle (excluding this one just in case)
    active_qs = ContestCycle.objects.filter(
        status=ContestCycleStatus.ACTIVE
    ).exclude(pk=cycle.pk)
    if active_qs.exists():
        active_ids = list(active_qs.values_list("id", flat=True)[:5])
        raise ContestCycleStateError(
            f"Cannot activate ContestCycle id={cycle_id}. "
            f"Already active cycle(s): {active_ids}. "
            "Complete or archive the existing active cycle first."
        )

    actor = None
    if actor_id is not None:
        try:
            actor = _get_user_or_raise(actor_id)
        except UserNotFoundError:
            logger.warning("activate_contest_cycle: actor_id=%r not found; proceeding anyway.", actor_id)

    cycle.transition_to(ContestCycleStatus.ACTIVE, actor=actor)
    logger.info(
        "ContestCycle %s activated by actor=%s",
        cycle.id,
        getattr(actor, "pk", "system"),
    )
    return cycle


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
        generator = LeaderboardGenerator(cycle=cycle, scope=scope, scope_ref=scope_ref)
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

    except LeaderboardGenerationError:
        snapshot.mark_failed(str(LeaderboardGenerationError))
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
    from .choices import RewardType

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
        "UserAchievement %s awarded: user=%s type=%s points=%s rank=%s cycle=%s",
        achievement.id,
        user_id,
        achievement_type,
        validated_points,
        rank,
        cycle_id,
    )
    return achievement


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

    user_score_row = user_totals.filter(user_id=user_id).first()
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
        raise GamificationServiceError(
            "achievement_ids must not be empty."
        )

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
