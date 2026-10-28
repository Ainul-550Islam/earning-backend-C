"""
Gamification Signal Receivers — Connected in GamificationConfig.ready().

All receivers are defensive: they never let an exception bubble up and kill
the calling thread. Failures are logged at ERROR level.
"""

from __future__ import annotations

import logging
from typing import Any

from django.dispatch import receiver

from api.gamification.signals import (
    contest_cycle_status_changed,
    achievement_awarded,
    leaderboard_snapshot_finalized,
    user_points_updated,
    badge_earned,
    user_leveled_up,
    streak_updated,
    daily_challenge_completed,
)

logger = logging.getLogger(__name__)


@receiver(contest_cycle_status_changed)
def on_contest_cycle_status_changed(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a ContestCycle transitions to a new status.

    On COMPLETED transition: enqueues the async reward distribution task.
    """
    from api.gamification.choices import ContestCycleStatus

    cycle = kwargs.get("cycle")
    new_status = kwargs.get("new_status")
    old_status = kwargs.get("old_status")

    if cycle is None or new_status is None:
        logger.error(
            "on_contest_cycle_status_changed: received signal without 'cycle' or 'new_status'. "
            "kwargs=%r",
            kwargs,
        )
        return

    logger.info(
        "on_contest_cycle_status_changed: cycle=%s %s → %s",
        getattr(cycle, "id", "?"),
        old_status,
        new_status,
    )

    if new_status == ContestCycleStatus.COMPLETED:
        try:
            from api.gamification.tasks import distribute_cycle_rewards_async
            task = distribute_cycle_rewards_async.delay(str(cycle.id))
            logger.info(
                "Enqueued distribute_cycle_rewards_async for cycle=%s task_id=%s",
                cycle.id,
                task.id,
            )
        except Exception as exc:
            # Never crash the caller — log and move on
            logger.exception(
                "Failed to enqueue distribute_cycle_rewards_async for cycle=%s: %s",
                getattr(cycle, "id", "?"),
                exc,
            )


@receiver(achievement_awarded)
def on_achievement_awarded(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a UserAchievement is formally awarded.

    Responsibilities:
    - Enqueue user notification (e.g. push notification / email).
    - Could trigger downstream point-balance update if not handled in service.
    """
    achievement = kwargs.get("achievement")
    if achievement is None:
        logger.error(
            "on_achievement_awarded: received signal without 'achievement'. kwargs=%r", kwargs
        )
        return

    logger.info(
        "on_achievement_awarded: user=%s type=%s points=%s achievement=%s",
        getattr(achievement, "user_id", "?"),
        getattr(achievement, "achievement_type", "?"),
        getattr(achievement, "points_awarded", 0),
        getattr(achievement, "id", "?"),
    )

    # Notify user and track analytics
    try:
        from api.gamification.integrations.adapter import gamification_adapter
        gamification_adapter.notify_achievement_awarded(achievement)
        gamification_adapter.track_event(
            "achievement_awarded",
            user=getattr(achievement, "user", None),
            properties={
                "type": str(getattr(achievement, "achievement_type", "")),
                "points": getattr(achievement, "points_awarded", 0),
                "achievement_id": str(getattr(achievement, "id", "")),
            },
        )
        # Mark the achievement as notified now that the notification has been dispatched
        achievement.mark_notified()
    except Exception as exc:
        logger.exception("on_achievement_awarded: adapter call failed: %s", exc)

    # Wire TimestampedModel.log_audit_event (non-critical)
    try:
        achievement.log_audit_event(event_type="achievement_awarded",
            details={"type": str(getattr(achievement,"achievement_type","")),
                     "points": getattr(achievement,"points_awarded",0)})
    except Exception:
        pass

    # Publish domain event to INTEGRATION_SYSTEM EventBus (non-critical)
    try:
        from api.gamification.INTEGRATION_SYSTEM.wiring import publish_domain_event
        publish_domain_event("achievement.awarded", {
            "user_id": str(getattr(achievement, "user_id", "")),
            "achievement_type": str(getattr(achievement, "achievement_type", "")),
            "achievement_id": str(getattr(achievement, "id", "")),
            "points_awarded": getattr(achievement, "points_awarded", 0),
        })
    except Exception as exc:
        logger.debug("EventBus publish skipped: %s", exc)


@receiver(leaderboard_snapshot_finalized)
def on_leaderboard_snapshot_finalized(sender: Any, **kwargs: Any) -> None:
    """
    Triggered after a LeaderboardSnapshot is finalized.

    Invalidates leaderboard caches and notifies via the gamification adapter.
    """
    snapshot = kwargs.get("snapshot")
    if snapshot is None:
        logger.error(
            "on_leaderboard_snapshot_finalized: missing 'snapshot'. kwargs=%r", kwargs
        )
        return

    logger.info(
        "on_leaderboard_snapshot_finalized: snapshot=%s cycle=%s entries=%d",
        getattr(snapshot, "id", "?"),
        getattr(snapshot, "contest_cycle_id", "?"),
        getattr(snapshot, "entry_count", 0),
    )

    # Invalidate cached leaderboard
    try:
        from django.core.cache import cache
        cache_key = f"leaderboard:{snapshot.contest_cycle_id}:{snapshot.scope}"
        cache.delete(cache_key)
    except Exception as exc:
        logger.exception("Failed to invalidate leaderboard cache: %s", exc)

    # Notify via gamification adapter
    try:
        from api.gamification.integrations.adapter import gamification_adapter
        gamification_adapter.notify_leaderboard_finalized(
            snapshot, top_n=getattr(snapshot, "entry_count", 10)
        )
    except Exception as exc:
        logger.exception("Failed to notify leaderboard finalized: %s", exc)


@receiver(user_points_updated)
def on_user_points_updated(sender: Any, **kwargs: Any) -> None:
    """
    Triggered when a user's total points are updated.
    
    Automatically checks for level-ups and badge eligibility.
    """
    user_id = kwargs.get("user_id")
    old_points = kwargs.get("old_points", 0)
    new_points = kwargs.get("new_points", 0)
    source = kwargs.get("source", "unknown")
    
    if user_id is None:
        logger.error("on_user_points_updated: missing user_id. kwargs=%r", kwargs)
        return
    
    logger.info(
        "on_user_points_updated: user=%s %d→%d source=%s",
        user_id,
        old_points,
        new_points,
        source,
    )
    
    try:
        # Check for level-up
        _check_level_up(user_id, new_points)
        
        # Check for badge eligibility
        _check_badge_eligibility(user_id, new_points)
        
    except Exception as exc:
        logger.exception("Failed to process points update for user=%s: %s", user_id, exc)


@receiver(user_leveled_up)
def on_user_leveled_up(sender: Any, **kwargs: Any) -> None:
    """
    Triggered when a user levels up.
    
    Handles level-up rewards and notifications.
    """
    user_id = kwargs.get("user_id")
    old_level = kwargs.get("old_level", 0)
    new_level = kwargs.get("new_level", 0)
    level_config_id = kwargs.get("level_config_id")
    
    if user_id is None:
        logger.error("on_user_leveled_up: missing user_id. kwargs=%r", kwargs)
        return
    
    logger.info(
        "on_user_leveled_up: user=%s %d→%d level_config=%s",
        user_id,
        old_level,
        new_level,
        level_config_id,
    )
    
    try:
        # Award level-up badge if configured
        _award_level_badge(user_id, level_config_id)
        
        # Could enqueue notification task here
        # from notifications.tasks import send_level_up_notification
        # send_level_up_notification.delay(str(user_id), new_level)
        
    except Exception as exc:
        logger.exception("Failed to process level-up for user=%s: %s", user_id, exc)


@receiver(streak_updated)
def on_streak_updated(sender: Any, **kwargs: Any) -> None:
    """
    Triggered when a user's streak is updated.
    
    Checks for streak milestone rewards.
    """
    user_id = kwargs.get("user_id")
    streak_days = kwargs.get("streak_days", 0)
    was_extended = kwargs.get("was_extended", False)
    
    if user_id is None:
        logger.error("on_streak_updated: missing user_id. kwargs=%r", kwargs)
        return
    
    logger.info(
        "on_streak_updated: user=%s days=%d extended=%s",
        user_id,
        streak_days,
        was_extended,
    )
    
    try:
        # Check for streak rewards
        _check_streak_rewards(user_id, streak_days)
        
    except Exception as exc:
        logger.exception("Failed to process streak update for user=%s: %s", user_id, exc)


@receiver(daily_challenge_completed)
def on_daily_challenge_completed(sender: Any, **kwargs: Any) -> None:
    """
    Triggered when a daily challenge is completed.
    
    Awards bonus points and updates streak.
    """
    user_id = kwargs.get("user_id")
    challenge_id = kwargs.get("challenge_id")
    user_challenge_id = kwargs.get("user_challenge_id")
    
    if user_id is None:
        logger.error("on_daily_challenge_completed: missing user_id. kwargs=%r", kwargs)
        return
    
    logger.info(
        "on_daily_challenge_completed: user=%s challenge=%s user_challenge=%s",
        user_id,
        challenge_id,
        user_challenge_id,
    )
    
    try:
        # Update streak for daily activity
        _update_daily_streak(user_id)
        
    except Exception as exc:
        logger.exception("Failed to process challenge completion for user=%s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _check_level_up(user_id: Any, total_points: int) -> None:
    """Check if user should level up based on total points."""
    from api.gamification.models import LevelConfig
    
    current_level = LevelConfig.get_level_for_points(total_points)
    if not current_level:
        return
    
    # Get previous level to determine if this is a level-up
    prev_points = max(0, total_points - 1)  # Assume at least 1 point was just added
    prev_level = LevelConfig.get_level_for_points(prev_points)
    
    if prev_level and current_level.level_number > prev_level.level_number:
        # User leveled up!
        from api.gamification.signals import user_leveled_up
        user_leveled_up.send(
            sender=None,
            user_id=user_id,
            old_level=prev_level.level_number,
            new_level=current_level.level_number,
            level_config_id=current_level.id,
        )


def _check_badge_eligibility(user_id: Any, total_points: int) -> None:
    """Check if user is eligible for any new badges based on points."""
    from api.gamification.models import Badge, UserBadge
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    
    # Get user's current streak for badge checking
    try:
        streak = user.streak
        streak_days = streak.current_days if streak else 0
    except:
        streak_days = 0
    
    # Check badges the user doesn't already have
    eligible_badges = Badge.objects.filter(
        is_active=True,
        criteria_type="POINTS_THRESHOLD",
        criteria_value__lte=total_points
    ).exclude(
        id__in=UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
    )
    
    for badge in eligible_badges:
        if badge.is_unlocked_by_user(user_points=total_points, streak_days=streak_days):
            # Award the badge
            user_badge = UserBadge.objects.create(
                user=user,
                badge=badge,
                metadata={"awarded_via": "points_check", "total_points": total_points}
            )
            
            # Send badge earned signal
            from api.gamification.signals import badge_earned
            badge_earned.send(
                sender=None,
                user_id=user_id,
                badge_id=badge.id,
                user_badge_id=user_badge.id,
            )


def _award_level_badge(user_id: Any, level_config_id: Any) -> None:
    """Award badge associated with level-up if configured."""
    from api.gamification.models import LevelConfig, UserBadge
    from django.contrib.auth import get_user_model
    
    try:
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        level_config = LevelConfig.objects.get(pk=level_config_id)
        
        if level_config.badge:
            # Check if user already has this badge
            if not UserBadge.objects.filter(user=user, badge=level_config.badge).exists():
                user_badge = UserBadge.objects.create(
                    user=user,
                    badge=level_config.badge,
                    metadata={"awarded_via": "level_up", "level": level_config.level_number}
                )
                
                # Send badge earned signal
                from api.gamification.signals import badge_earned
                badge_earned.send(
                    sender=None,
                    user_id=user_id,
                    badge_id=level_config.badge.id,
                    user_badge_id=user_badge.id,
                )
                
    except (User.DoesNotExist, LevelConfig.DoesNotExist):
        pass


def _check_streak_rewards(user_id: Any, streak_days: int) -> None:
    """Check and award streak milestone rewards."""
    from api.gamification.models import StreakReward, UserBadge
    from django.contrib.auth import get_user_model
    
    try:
        User = get_user_model()
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    
    # Find eligible streak rewards
    eligible_rewards = StreakReward.objects.filter(
        is_active=True,
        streak_days__lte=streak_days
    ).order_by('-streak_days')
    
    for reward in eligible_rewards:
        # Check if user already received this reward (via badge)
        if reward.badge:
            if UserBadge.objects.filter(user=user, badge=reward.badge).exists():
                continue  # Already awarded
            
            # Award the badge
            user_badge = UserBadge.objects.create(
                user=user,
                badge=reward.badge,
                metadata={"awarded_via": "streak_milestone", "streak_days": streak_days}
            )
            
            # Send badge earned signal
            from api.gamification.signals import badge_earned
            badge_earned.send(
                sender=None,
                user_id=user_id,
                badge_id=reward.badge.id,
                user_badge_id=user_badge.id,
            )


def _update_daily_streak(user_id: Any) -> None:
    """Update user's daily activity streak."""
    from api.gamification.models import Streak
    from django.contrib.auth import get_user_model
    
    try:
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        
        streak, created = Streak.objects.get_or_create(user=user)
        streak_extended, days_added = streak.update_activity()
        
        # Send streak updated signal
        from api.gamification.signals import streak_updated
        streak_updated.send(
            sender=None,
            user_id=user_id,
            streak_days=streak.current_days,
            was_extended=streak_extended,
        )
        
    except User.DoesNotExist:
        pass
