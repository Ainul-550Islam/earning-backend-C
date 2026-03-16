"""
Gamification Signals — Signal definitions for the gamification module.

Signals are defined here and connected to receivers in receivers.py via AppConfig.ready().
Do NOT import receivers here to avoid circular imports.
"""

from django.dispatch import Signal

# Fired after a ContestCycle successfully transitions to a new status.
# kwargs: cycle (ContestCycle), old_status (str), new_status (str), actor (User|None)
contest_cycle_status_changed = Signal()

# Fired after a UserAchievement is formally awarded (is_awarded=True).
# kwargs: achievement (UserAchievement)
achievement_awarded = Signal()

# Fired after a LeaderboardSnapshot is finalized.
# kwargs: snapshot (LeaderboardSnapshot)
leaderboard_snapshot_finalized = Signal()
