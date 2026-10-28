# engagement/models/__init__.py  — COMPLETE — all models
from .base import TenantModel, UserEngagementModel

# Core engagement
from .checkin import DailyCheckIn
from .spinwheel import SpinWheel
from .leaderboard import Leaderboard, LeaderboardReward, LeaderboardSeason
from .achievement import Achievement, UserAchievement, AchievementProgress
from .xp import UserXP, XPTransaction, xp_for_level, level_from_total_xp
from .quest import Quest, UserQuest
from .challenge import Challenge, ChallengeParticipant
from .shop import ShopItem, ShopPurchase, UserInventory
from .referral import ReferralProgram, Referral
from .notification import Notification, UserPushToken

# Advanced engagement systems
from .battle_pass import BattlePass, BattlePassTier, UserBattlePass, BattlePassXPSource
from .guild import Guild, GuildMember, GuildChallenge, GuildLeaderboard, GuildInvite
from .social import FeedItem, FeedLike, FeedComment, Friendship, UserFollow
from .loot_box import ChestType, ChestDropTable, UserChest, ChestOpening
from .seasonal_event import (SeasonalEvent, EventMission, UserEventProgress,
                              UserEventCurrency, EventShopItem)
from .combo import ComboConfig, UserCombo, EnergyConfig, EnergyCost, UserEnergy
from .prestige import (PrestigeLevel, UserPrestige, Milestone, UserMilestone,
                       UserTitle, UserEquippedTitle)
from .anti_cheat import AntiCheatRule, AntiCheatLog, UserRiskScore, IPReputation
from .campaign import (UserSegment, SegmentMember, Campaign, CampaignEvent,
                       FeatureFlag, ABTest, ABTestVariant, UserABAssignment)
from .analytics import EngagementEvent, RetentionCohort, DailyPlatformMetric
from .webhook import WebhookEndpoint, WebhookDelivery
from .scratch_card import (ScratchCardTemplate, ScratchCardPrize, ScratchCardResult,
                            LoginCalendar, LoginCalendarDay, UserLoginCalendarProgress)
from .auction import Auction, AuctionBid, AuctionWatchlist

__all__ = [
    # Base (EngagementTestUser intentionally excluded — test-only)
    "TenantModel", "UserEngagementModel",
    # Core
    "DailyCheckIn", "SpinWheel",
    "Leaderboard", "LeaderboardReward", "LeaderboardSeason",
    "Achievement", "UserAchievement", "AchievementProgress",
    "UserXP", "XPTransaction", "xp_for_level", "level_from_total_xp",
    "Quest", "UserQuest",
    "Challenge", "ChallengeParticipant",
    "ShopItem", "ShopPurchase", "UserInventory",
    "ReferralProgram", "Referral",
    "Notification", "UserPushToken",
    # Advanced
    "BattlePass", "BattlePassTier", "UserBattlePass", "BattlePassXPSource",
    "Guild", "GuildMember", "GuildChallenge", "GuildLeaderboard", "GuildInvite",
    "FeedItem", "FeedLike", "FeedComment", "Friendship", "UserFollow",
    "ChestType", "ChestDropTable", "UserChest", "ChestOpening",
    "SeasonalEvent", "EventMission", "UserEventProgress", "UserEventCurrency", "EventShopItem",
    "ComboConfig", "UserCombo", "EnergyConfig", "EnergyCost", "UserEnergy",
    "PrestigeLevel", "UserPrestige", "Milestone", "UserMilestone", "UserTitle", "UserEquippedTitle",
    "AntiCheatRule", "AntiCheatLog", "UserRiskScore", "IPReputation",
    "UserSegment", "SegmentMember", "Campaign", "CampaignEvent",
    "FeatureFlag", "ABTest", "ABTestVariant", "UserABAssignment",
    "EngagementEvent", "RetentionCohort", "DailyPlatformMetric",
    "WebhookEndpoint", "WebhookDelivery",
    "ScratchCardTemplate", "ScratchCardPrize", "ScratchCardResult",
    "LoginCalendar", "LoginCalendarDay", "UserLoginCalendarProgress",
    "Auction", "AuctionBid", "AuctionWatchlist",
]

# EngagementTestUser is for testing only — not imported in production
