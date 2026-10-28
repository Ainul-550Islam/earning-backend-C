"""
Gamification Signals — Signal definitions for the gamification module.
Enhanced with integration system monitoring and audit logging.

Signals are defined here and connected to receivers in receivers.py via AppConfig.ready().
Do NOT import receivers here to avoid circular imports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.dispatch import Signal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Fired after a ContestCycle successfully transitions to a new status.
# kwargs: cycle (ContestCycle), old_status (str), new_status (str), actor (User|None)
contest_cycle_status_changed = Signal()

# Fired after a UserAchievement is formally awarded (is_awarded=True).
# kwargs: achievement (UserAchievement)
achievement_awarded = Signal()

# Fired after a LeaderboardSnapshot is finalized.
# kwargs: snapshot (LeaderboardSnapshot)
leaderboard_snapshot_finalized = Signal()

# Fired when a user's total points are updated.
# kwargs: user_id (UUID), old_points (int), new_points (int), source (str)
user_points_updated = Signal()

# Fired when a user earns a new badge.
# kwargs: user_id (UUID), badge_id (UUID), user_badge_id (UUID)
badge_earned = Signal()

# Fired when a user levels up.
# kwargs: user_id (UUID), old_level (int), new_level (int), level_config_id (UUID)
user_leveled_up = Signal()

# Fired when a user's streak is updated.
# kwargs: user_id (UUID), streak_days (int), was_extended (bool)
streak_updated = Signal()

# Fired when a daily challenge is completed.
# kwargs: user_id (UUID), challenge_id (UUID), user_challenge_id (UUID)
daily_challenge_completed = Signal()

# ---------------------------------------------------------------------------
# Additional Gamification Signals (from signals_cap.py)
# ---------------------------------------------------------------------------

# Contest Cycle Signals
CONTEST_CYCLE_CREATED = Signal()
"""Signal sent when a new contest cycle is created."""

CONTEST_CYCLE_UPDATED = Signal()
"""Signal sent when a contest cycle is updated."""

CONTEST_CYCLE_ACTIVATED = Signal()
"""Signal sent when a contest cycle is activated."""

CONTEST_CYCLE_COMPLETED = Signal()
"""Signal sent when a contest cycle is completed."""

CONTEST_CYCLE_ARCHIVED = Signal()
"""Signal sent when a contest cycle is archived."""

# Achievement Signals
ACHIEVEMENT_CREATED = Signal()
"""Signal sent when a new achievement is created."""

ACHIEVEMENT_REVOKED = Signal()
"""Signal sent when an achievement is revoked."""

ACHIEVEMENT_NOTIFIED = Signal()
"""Signal sent when an achievement notification is sent."""

# Leaderboard Signals
LEADERBOARD_SNAPSHOT_CREATED = Signal()
"""Signal sent when a leaderboard snapshot is created."""

LEADERBOARD_SNAPSHOT_FAILED = Signal()
"""Signal sent when a leaderboard snapshot generation fails."""

LEADERBOARD_UPDATED = Signal()
"""Signal sent when a leaderboard is updated."""

# Badge Signals
BADGE_CREATED = Signal()
"""Signal sent when a new badge is created."""

BADGE_PINNED = Signal()
"""Signal sent when a badge is pinned to user profile."""

BADGE_UNPINNED = Signal()
"""Signal sent when a badge is unpinned from user profile."""

# Challenge Signals
CHALLENGE_CREATED = Signal()
"""Signal sent when a new challenge is created."""

CHALLENGE_EXPIRED = Signal()
"""Signal sent when a challenge expires."""

CHALLENGE_ACTIVATED = Signal()
"""Signal sent when a challenge is activated."""

# Streak Signals
STREAK_CREATED = Signal()
"""Signal sent when a new streak is created."""

STREAK_RESET = Signal()
"""Signal sent when a streak is reset."""

STREAK_EXPIRED = Signal()
"""Signal sent when a streak expires."""

STREAK_REWARD_CLAIMED = Signal()
"""Signal sent when a streak reward is claimed."""

# Level Signals
LEVEL_CONFIG_CREATED = Signal()
"""Signal sent when a new level configuration is created."""

LEVEL_CONFIG_UPDATED = Signal()
"""Signal sent when a level configuration is updated."""

# Points Signals
POINTS_AWARDED = Signal()
"""Signal sent when points are awarded to a user."""

POINTS_DEDUCTED = Signal()
"""Signal sent when points are deducted from a user."""

# User Signals
USER_GAMIFICATION_PROFILE_CREATED = Signal()
"""Signal sent when a user's gamification profile is created."""

USER_GAMIFICATION_PROFILE_UPDATED = Signal()
"""Signal sent when a user's gamification profile is updated."""

USER_RANK_CHANGED = Signal()
"""Signal sent when a user's rank changes."""

# System Signals
GAMIFICATION_SYSTEM_INITIALIZED = Signal()
"""Signal sent when gamification system is initialized."""

GAMIFICATION_DATA_IMPORTED = Signal()
"""Signal sent when gamification data is imported."""

GAMIFICATION_DATA_EXPORTED = Signal()
"""Signal sent when gamification data is exported."""

GAMIFICATION_CACHE_CLEARED = Signal()
"""Signal sent when gamification cache is cleared."""

GAMIFICATION_ERROR_OCCURRED = Signal()
"""Signal sent when a gamification error occurs."""

# ---------------------------------------------------------------------------
# Integration System Signals
# ---------------------------------------------------------------------------

# Fired when integration system health check is performed.
# kwargs: resource_type (str), resource_id (str), health_status (str), details (dict)
integration_health_check = Signal()

# Fired when integration system sync operation is triggered.
# kwargs: resource_type (str), resource_id (str), sync_type (str), operation_id (str)
integration_sync_triggered = Signal()

# Fired when integration system audit event is logged.
# kwargs: action (str), resource_type (str), resource_id (str), user_id (str), details (dict)
integration_audit_logged = Signal()

# Fired when integration system performance metric is recorded.
# kwargs: metric_name (str), value (float), tags (dict), resource_id (str)
integration_metric_recorded = Signal()

# Fired when integration system fallback logic is executed.
# kwargs: operation (str), success (bool), fallback_used (bool), error (str)
integration_fallback_executed = Signal()

# Fired when integration system circuit breaker changes state.
# kwargs: circuit_name (str), old_state (str), new_state (str), failure_count (int)
integration_circuit_breaker_state_changed = Signal()

# Fired when integration system webhook is processed.
# kwargs: webhook_id (str), event_type (str), processing_result (str), duration (float)
integration_webhook_processed = Signal()

# Fired when integration system data validation is performed.
# kwargs: resource_type (str), resource_id (str), validation_result (str), errors (list)
integration_validation_performed = Signal()

# Fired when integration system authentication event occurs.
# kwargs: auth_type (str), user_id (str), success (bool), provider (str), details (dict)
integration_authentication_event = Signal()

# Fired when integration system data transformation is executed.
# kwargs: transformation_id (str), source_format (str), target_format (str), success (bool)
integration_data_transformed = Signal()

# Fired when integration system version compatibility is checked.
# kwargs: component (str), current_version (str), required_version (str), is_compatible (bool)
integration_version_checked = Signal()

# Fired when integration system message queue operation occurs.
# kwargs: queue_name (str), operation (str), message_count (int), success (bool)
integration_queue_operation = Signal()

# Fired when integration system conflict resolution is executed.
# kwargs: resource_type (str), resource_id (str), conflict_type (str), resolution_strategy (str)
integration_conflict_resolved = Signal()

points_awarded = Signal()
points_deducted = Signal()

contest_started = Signal()
contest_ended = Signal()
user_joined_contest = Signal()
leaderboard_position_changed = Signal()
sanction_applied = Signal()
