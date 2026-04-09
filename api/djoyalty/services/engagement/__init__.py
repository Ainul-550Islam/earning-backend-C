# api/djoyalty/services/engagement/__init__.py
"""
Engagement services:
  StreakService      : Daily streak tracking + milestone rewards
  BadgeService       : Badge evaluation and awarding
  ChallengeService   : Challenge join, progress, completion
  MilestoneService   : Milestone threshold checking
  LeaderboardService : Top customer leaderboard
"""
from .StreakService import StreakService
from .BadgeService import BadgeService
from .ChallengeService import ChallengeService
from .MilestoneService import MilestoneService
from .LeaderboardService import LeaderboardService

__all__ = [
    'StreakService', 'BadgeService', 'ChallengeService',
    'MilestoneService', 'LeaderboardService',
]
