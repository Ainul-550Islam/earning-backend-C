# api/djoyalty/services.py
"""
Djoyalty Services -- root-level convenience import।
All services defined in djoyalty/services/ package।
"এক কাজের জন্য একটাই মালিক" -- each service owns its domain।
"""

# Core Services
from .services.earn.EarnRuleEngine import EarnRuleEngine as EarnService  # EarnService alias
from .services.redemption.RedemptionService import RedemptionService
# TierService -> use TierEvaluationService (actual class)
from .services.tiers.TierEvaluationService import TierEvaluationService as TierService
# PointsService -> use PointsEngine (actual class)
from .services.points.PointsEngine import PointsEngine as PointsService

# Engagement Services
from .services.engagement.BadgeService import BadgeService
from .services.engagement.StreakService import StreakService
from .services.engagement.ChallengeService import ChallengeService
from .services.engagement.MilestoneService import MilestoneService

# Gamification
from .services.gamification.SpinWheelService import SpinWheelService
from .services.gamification.ScratchCardService import ScratchCardService
from .services.gamification.LotteryService import LotteryService

# Advanced / World-class
from .services.AIPersonalizationService import AIPersonalizationService
from .services.NotificationService import NotificationService
from .services.RewardCatalogService import RewardCatalogService
from .services.SmartLinkService import SmartLinkService
from .services.OfferWallService import OfferWallService

__all__ = [
    'EarnService', 'RedemptionService', 'TierService', 'PointsService',
    'BadgeService', 'StreakService', 'ChallengeService', 'MilestoneService',
    'SpinWheelService', 'ScratchCardService', 'LotteryService',
    'AIPersonalizationService', 'NotificationService',
    'RewardCatalogService', 'SmartLinkService', 'OfferWallService',
]
