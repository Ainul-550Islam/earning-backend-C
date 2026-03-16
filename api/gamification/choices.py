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
