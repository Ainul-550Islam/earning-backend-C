"""
Gamification Choices — All Django TextChoices enums used across the module.
"""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class ContestCycleStatus(TextChoices):
    DRAFT = "DRAFT", _("Draft")
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    ARCHIVED = "ARCHIVED", _("Archived")


class RewardType(TextChoices):
    POINTS = "POINTS", _("Points")
    BADGE = "BADGE", _("Badge")
    COUPON = "COUPON", _("Coupon")
    PHYSICAL = "PHYSICAL", _("Physical Prize")
    CUSTOM = "CUSTOM", _("Custom")


class AchievementType(TextChoices):
    RANK_REWARD = "RANK_REWARD", _("Rank Reward")
    MILESTONE = "MILESTONE", _("Milestone")
    STREAK = "STREAK", _("Streak")
    BADGE = "BADGE", _("Badge")
    BONUS = "BONUS", _("Bonus")
    CUSTOM = "CUSTOM", _("Custom")


class LeaderboardScope(TextChoices):
    GLOBAL = "GLOBAL", _("Global")
    REGIONAL = "REGIONAL", _("Regional")
    CATEGORY = "CATEGORY", _("Category")


class SnapshotStatus(TextChoices):
    PENDING = "PENDING", _("Pending")
    FINALIZED = "FINALIZED", _("Finalized")
    FAILED = "FAILED", _("Failed")


class BadgeRarity(TextChoices):
    COMMON = "COMMON", _("Common")
    UNCOMMON = "UNCOMMON", _("Uncommon")
    RARE = "RARE", _("Rare")
    EPIC = "EPIC", _("Epic")
    LEGENDARY = "LEGENDARY", _("Legendary")


class BadgeCriteriaType(TextChoices):
    POINTS_THRESHOLD = "POINTS_THRESHOLD", _("Points Threshold")
    STREAK_DAYS = "STREAK_DAYS", _("Streak Days")
    ACHIEVEMENT_COUNT = "ACHIEVEMENT_COUNT", _("Achievement Count")
    CONTEST_WINS = "CONTEST_WINS", _("Contest Wins")
    REFERRAL_COUNT = "REFERRAL_COUNT", _("Referral Count")
    CUSTOM = "CUSTOM", _("Custom")


class ChallengeAction(TextChoices):
    LOGIN = "LOGIN", _("Daily Login")
    COMPLETE_PROFILE = "COMPLETE_PROFILE", _("Complete Profile")
    REFER_FRIEND = "REFER_FRIEND", _("Refer Friend")
    EARN_POINTS = "EARN_POINTS", _("Earn Points")
    COMPLETE_CHALLENGE = "COMPLETE_CHALLENGE", _("Complete Challenge")
    VIEW_CONTENT = "VIEW_CONTENT", _("View Content")
    SHARE_CONTENT = "SHARE_CONTENT", _("Share Content")
    COMMENT = "COMMENT", _("Comment")
    CUSTOM = "CUSTOM", _("Custom Action")


class ChallengeStatus(TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    EXPIRED = "EXPIRED", _("Expired")
    CANCELLED = "CANCELLED", _("Cancelled")


class StreakStatus(TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    EXPIRED = "EXPIRED", _("Expired")
    PAUSED = "PAUSED", _("Paused")
    RESET = "RESET", _("Reset")


class LevelPerkType(TextChoices):
    POINTS_MULTIPLIER = "POINTS_MULTIPLIER", _("Points Multiplier")
    BONUS_BADGE = "BONUS_BADGE", _("Bonus Badge")
    EXCLUSIVE_CONTENT = "EXCLUSIVE_CONTENT", _("Exclusive Content")
    PRIORITY_SUPPORT = "PRIORITY_SUPPORT", _("Priority Support")
    CUSTOM_AVATAR = "CUSTOM_AVATAR", _("Custom Avatar")
    EARLY_ACCESS = "EARLY_ACCESS", _("Early Access")
    INCREASED_LIMITS = "INCREASED_LIMITS", _("Increased Limits")
    CUSTOM = "CUSTOM", _("Custom Perk")


# ---------------------------------------------------------------------------
# New Choices for Added Models
# ---------------------------------------------------------------------------

class PointsTransactionSource(TextChoices):
    OFFER = "OFFER", _("Offer Completion")
    REFERRAL = "REFERRAL", _("Referral")
    STREAK = "STREAK", _("Streak Milestone")
    CHALLENGE = "CHALLENGE", _("Challenge Completion")
    CONTEST = "CONTEST", _("Contest Reward")
    MANUAL = "MANUAL", _("Manual Adjustment")
    BONUS = "BONUS", _("Bonus Points")
    PENALTY = "PENALTY", _("Penalty Deduction")
    DAILY_LOGIN = "DAILY_LOGIN", _("Daily Login")
    PROFILE_COMPLETE = "PROFILE_COMPLETE", _("Profile Completion")
    SOCIAL_SHARE = "SOCIAL_SHARE", _("Social Share")
    CONTENT_VIEW = "CONTENT_VIEW", _("Content View")
    COMMENT_POST = "COMMENT_POST", _("Comment Post")
    REVIEW_SUBMIT = "REVIEW_SUBMIT", _("Review Submit")


class StreakFreezeReason(TextChoices):
    VACATION = "VACATION", _("Vacation")
    SICKNESS = "SICKNESS", _("Sickness")
    EMERGENCY = "EMERGENCY", _("Emergency")
    TECHNICAL_ISSUE = "TECHNICAL_ISSUE", _("Technical Issue")
    HOLIDAY = "HOLIDAY", _("Holiday")
    PERSONAL = "PERSONAL", _("Personal Reason")
    SYSTEM_ERROR = "SYSTEM_ERROR", _("System Error")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")
    CUSTOM = "CUSTOM", _("Custom Reason")


class ContestParticipantStatus(TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    DISQUALIFIED = "DISQUALIFIED", _("Disqualified")
    WITHDRAWN = "WITHDRAWN", _("Withdrawn")
    SUSPENDED = "SUSPENDED", _("Suspended")
    BANNED = "BANNED", _("Banned")


class GamificationFeature(TextChoices):
    CONTESTS = "CONTESTS", _("Contests")
    BADGES = "BADGES", _("Badges")
    STREAKS = "STREAKS", _("Streaks")
    LEVELS = "LEVELS", _("Levels")
    DAILY_CHALLENGES = "DAILY_CHALLENGES", _("Daily Challenges")
    LEADERBOARDS = "LEADERBOARDS", _("Leaderboards")
    POINTS_SYSTEM = "POINTS_SYSTEM", _("Points System")
    REWARDS = "REWARDS", _("Rewards")
    NOTIFICATIONS = "NOTIFICATIONS", _("Notifications")
    ANALYTICS = "ANALYTICS", _("Analytics")


class InsightMetricType(TextChoices):
    USER_ENGAGEMENT = "USER_ENGAGEMENT", _("User Engagement")
    POINTS_DISTRIBUTION = "POINTS_DISTRIBUTION", _("Points Distribution")
    CONTEST_PARTICIPATION = "CONTEST_PARTICIPATION", _("Contest Participation")
    STREAK_ACTIVITY = "STREAK_ACTIVITY", _("Streak Activity")
    CHALLENGE_COMPLETION = "CHALLENGE_COMPLETION", _("Challenge Completion")
    BADGE_EARNED = "BADGE_EARNED", _("Badge Earned")
    LEVEL_PROGRESSION = "LEVEL_PROGRESSION", _("Level Progression")
    REWARD_CLAIMED = "REWARD_CLAIMED", _("Reward Claimed")
    SOCIAL_ACTIVITY = "SOCIAL_ACTIVITY", _("Social Activity")
    RETENTION_RATE = "RETENTION_RATE", _("Retention Rate")


class AlertSeverity(TextChoices):
    LOW = "LOW", _("Low")
    MEDIUM = "MEDIUM", _("Medium")
    HIGH = "HIGH", _("High")
    CRITICAL = "CRITICAL", _("Critical")


class AlertType(TextChoices):
    FAILED = "FAILED", _("Operation Failed")
    SIZE_EXCEEDED = "SIZE_EXCEEDED", _("Size Limit Exceeded")
    SCHEDULE_MISSED = "SCHEDULE_MISSED", _("Schedule Missed")
    STORAGE_FULL = "STORAGE_FULL", _("Storage Full")
    VERIFICATION_FAILED = "VERIFICATION_FAILED", _("Verification Failed")
    RETENTION_EXPIRED = "RETENTION_EXPIRED", _("Retention Expired")
    SECURITY = "SECURITY", _("Security Issue")
    PERFORMANCE = "PERFORMANCE", _("Performance Issue")
    USAGE_SPIKE = "USAGE_SPIKE", _("Usage Spike")
    ERROR_RATE = "ERROR_RATE", _("High Error Rate")
    INTEGRITY = "INTEGRITY", _("Data Integrity Issue")


class WebhookStatus(TextChoices):
    PENDING   = "PENDING",   _("Pending")
    DELIVERED = "DELIVERED", _("Delivered")
    FAILED    = "FAILED",    _("Failed")
    RETRYING  = "RETRYING",  _("Retrying")

class IntegrationEventType(TextChoices):
    SYNC    = "SYNC",    _("Sync")
    WEBHOOK = "WEBHOOK", _("Webhook")
    AUDIT   = "AUDIT",   _("Audit")
    HEALTH  = "HEALTH",  _("Health Check")

class WebhookEventType(TextChoices):
    ACHIEVEMENT_AWARDED      = "ACHIEVEMENT_AWARDED",      _("Achievement Awarded")
    BADGE_EARNED             = "BADGE_EARNED",             _("Badge Earned")
    LEVEL_UP                 = "LEVEL_UP",                 _("Level Up")
    STREAK_UPDATED           = "STREAK_UPDATED",           _("Streak Updated")
    CONTEST_STARTED          = "CONTEST_STARTED",          _("Contest Started")
    CONTEST_ENDED            = "CONTEST_ENDED",            _("Contest Ended")
    CHALLENGE_COMPLETED      = "CHALLENGE_COMPLETED",      _("Challenge Completed")
    POINTS_AWARDED           = "POINTS_AWARDED",           _("Points Awarded")
    LEADERBOARD_UPDATED      = "LEADERBOARD_UPDATED",      _("Leaderboard Updated")
    REWARD_DISTRIBUTED       = "REWARD_DISTRIBUTED",       _("Reward Distributed")
