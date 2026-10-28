# engagement/choices.py
"""
Centralized choice definitions for engagement system.
All model field choices and status options.
"""

# ── User Status Choices ────────────────────────────────────────────────────────
USER_STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('suspended', 'Suspended'),
    ('banned', 'Banned'),
]

USER_LEVEL_CHOICES = [
    ('bronze', 'Bronze'),
    ('silver', 'Silver'),
    ('gold', 'Gold'),
    ('platinum', 'Platinum'),
    ('diamond', 'Diamond'),
]

# ── Achievement Choices ───────────────────────────────────────────────────────
ACHIEVEMENT_TYPE_CHOICES = [
    ('streak', 'Streak Based'),
    ('total', 'Total Count'),
    ('level', 'Level Based'),
    ('social', 'Social Interaction'),
    ('earning', 'Earning Based'),
    ('special', 'Special Event'),
]

ACHIEVEMENT_DIFFICULTY_CHOICES = [
    ('easy', 'Easy'),
    ('medium', 'Medium'),
    ('hard', 'Hard'),
    ('legendary', 'Legendary'),
]

ACHIEVEMENT_STATUS_CHOICES = [
    ('locked', 'Locked'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('expired', 'Expired'),
]

# ── Quest Choices ────────────────────────────────────────────────────────────
QUEST_TYPE_CHOICES = [
    ('daily', 'Daily Quest'),
    ('weekly', 'Weekly Quest'),
    ('monthly', 'Monthly Quest'),
    ('special', 'Special Quest'),
    ('story', 'Story Quest'),
]

QUEST_STATUS_CHOICES = [
    ('available', 'Available'),
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('expired', 'Expired'),
    ('failed', 'Failed'),
]

QUEST_DIFFICULTY_CHOICES = [
    ('beginner', 'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced', 'Advanced'),
    ('expert', 'Expert'),
]

# ── Leaderboard Choices ───────────────────────────────────────────────────────
LEADERBOARD_PERIOD_CHOICES = [
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
    ('seasonal', 'Seasonal'),
    ('all_time', 'All Time'),
]

LEADERBOARD_TYPE_CHOICES = [
    ('coins', 'Coins Earned'),
    ('xp', 'XP Gained'),
    ('checkins', 'Check-ins'),
    ('spins', 'Spins Completed'),
    ('achievements', 'Achievements Unlocked'),
]

# ── Shop Choices ───────────────────────────────────────────────────────────────
SHOP_ITEM_TYPE_CHOICES = [
    ('coin_pack', 'Coin Pack'),
    ('xp_boost', 'XP Boost'),
    ('spin_boost', 'Spin Boost'),
    ('streak_shield', 'Streak Shield'),
    ('cosmetic', 'Cosmetic Item'),
    ('badge', 'Achievement Badge'),
    ('power_up', 'Power Up'),
]

SHOP_ITEM_RARITY_CHOICES = [
    ('common', 'Common'),
    ('uncommon', 'Uncommon'),
    ('rare', 'Rare'),
    ('epic', 'Epic'),
    ('legendary', 'Legendary'),
]

SHOP_PURCHASE_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
]

# ── Notification Choices ───────────────────────────────────────────────────────
NOTIFICATION_TYPE_CHOICES = [
    ('achievement', 'Achievement'),
    ('quest', 'Quest'),
    ('level_up', 'Level Up'),
    ('reward', 'Reward'),
    ('social', 'Social'),
    ('system', 'System'),
    ('promotion', 'Promotion'),
]

NOTIFICATION_PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('normal', 'Normal'),
    ('high', 'High'),
    ('urgent', 'Urgent'),
]

NOTIFICATION_STATUS_CHOICES = [
    ('unread', 'Unread'),
    ('read', 'Read'),
    ('archived', 'Archived'),
    ('deleted', 'Deleted'),
]

# ── Referral Choices ───────────────────────────────────────────────────────────
REFERRAL_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('rewarded', 'Rewarded'),
    ('expired', 'Expired'),
    ('cancelled', 'Cancelled'),
]

REFERRAL_REWARD_TYPE_CHOICES = [
    ('coins', 'Coins'),
    ('xp', 'XP'),
    ('item', 'Item'),
    ('badge', 'Badge'),
]

# ── Battle Pass Choices ───────────────────────────────────────────────────────
BATTLE_PASS_STATUS_CHOICES = [
    ('inactive', 'Inactive'),
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('expired', 'Expired'),
]

BATTLE_PASS_TIER_STATUS_CHOICES = [
    ('locked', 'Locked'),
    ('available', 'Available'),
    ('claimed', 'Claimed'),
    ('premium_only', 'Premium Only'),
]

# ── Guild Choices ─────────────────────────────────────────────────────────────
GUILD_STATUS_CHOICES = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('disbanded', 'Disbanded'),
]

GUILD_MEMBER_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('kicked', 'Kicked'),
    ('left', 'Left'),
]

GUILD_MEMBER_ROLE_CHOICES = [
    ('member', 'Member'),
    ('officer', 'Officer'),
    ('leader', 'Leader'),
]

# ── Seasonal Event Choices ───────────────────────────────────────────────────
SEASONAL_EVENT_STATUS_CHOICES = [
    ('upcoming', 'Upcoming'),
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

SEASONAL_EVENT_TYPE_CHOICES = [
    ('holiday', 'Holiday'),
    ('special', 'Special'),
    ('competition', 'Competition'),
    ('community', 'Community'),
]

# ── Webhook Choices ───────────────────────────────────────────────────────────
WEBHOOK_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('delivered', 'Delivered'),
    ('failed', 'Failed'),
    ('retrying', 'Retrying'),
    ('abandoned', 'Abandoned'),
]

WEBHOOK_EVENT_CHOICES = [
    ('user_registered', 'User Registered'),
    ('level_up', 'Level Up'),
    ('achievement_unlocked', 'Achievement Unlocked'),
    ('quest_completed', 'Quest Completed'),
    ('reward_claimed', 'Reward Claimed'),
    ('social_interaction', 'Social Interaction'),
    ('all', 'All Events'),
]

# ── Anti-Cheat Choices ───────────────────────────────────────────────────────
ANTI_CHEAT_RULE_TYPE_CHOICES = [
    ('velocity', 'Velocity Check'),
    ('duplicate', 'Duplicate Check'),
    ('pattern', 'Pattern Analysis'),
    ('threshold', 'Threshold Limit'),
    ('behavioral', 'Behavioral Analysis'),
]

ANTI_CHEAT_RISK_LEVEL_CHOICES = [
    ('low', 'Low Risk'),
    ('medium', 'Medium Risk'),
    ('high', 'High Risk'),
    ('critical', 'Critical Risk'),
]

# ── Analytics Choices ─────────────────────────────────────────────────────────
ANALYTICS_EVENT_TYPE_CHOICES = [
    ('user_action', 'User Action'),
    ('system_event', 'System Event'),
    ('engagement', 'Engagement'),
    ('conversion', 'Conversion'),
    ('error', 'Error'),
]

ANALYTICS_PERIOD_CHOICES = [
    ('realtime', 'Real-time'),
    ('hourly', 'Hourly'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
]

# ── Feature Flag Choices ───────────────────────────────────────────────────────
FEATURE_FLAG_STATUS_CHOICES = [
    ('disabled', 'Disabled'),
    ('enabled', 'Enabled'),
    ('scheduled', 'Scheduled'),
    ('testing', 'Testing'),
]

FEATURE_FLAG_ENVIRONMENT_CHOICES = [
    ('development', 'Development'),
    ('staging', 'Staging'),
    ('production', 'Production'),
]

# ── A/B Test Choices ───────────────────────────────────────────────────────────
AB_TEST_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('running', 'Running'),
    ('completed', 'Completed'),
    ('paused', 'Paused'),
    ('cancelled', 'Cancelled'),
]

AB_TEST_VARIANT_STATUS_CHOICES = [
    ('control', 'Control'),
    ('variant_a', 'Variant A'),
    ('variant_b', 'Variant B'),
    ('variant_c', 'Variant C'),
]

# ── Common Utility Functions ──────────────────────────────────────────────────

def get_choice_label(choices, value):
    """Get human-readable label for choice value."""
    for choice_key, choice_label in choices:
        if choice_key == value:
            return choice_label
    return value

def get_valid_choices(choices):
    """Get list of valid choice keys."""
    return [choice_key for choice_key, _ in choices]

def validate_choice(choices, value):
    """Validate that value is in choices."""
    return value in get_valid_choices(choices)

# ── Choice Collections ──────────────────────────────────────────────────────────

# Status collections
STATUS_CHOICES_COMMON = [
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

STATUS_CHOICES_WITH_PENDING = [
    ('pending', 'Pending'),
    ('active', 'Active'),
    ('inactive', 'Inactive'),
]

STATUS_CHOICES_COMPLETE = [
    ('pending', 'Pending'),
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
]

# Priority collections
PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('normal', 'Normal'),
    ('high', 'High'),
]

PRIORITY_CHOICES_WITH_URGENT = [
    ('low', 'Low'),
    ('normal', 'Normal'),
    ('high', 'High'),
    ('urgent', 'Urgent'),
]

# Rarity collections
RARITY_CHOICES = [
    ('common', 'Common'),
    ('uncommon', 'Uncommon'),
    ('rare', 'Rare'),
    ('epic', 'Epic'),
    ('legendary', 'Legendary'),
]

# Difficulty collections
DIFFICULTY_CHOICES_BASIC = [
    ('easy', 'Easy'),
    ('medium', 'Medium'),
    ('hard', 'Hard'),
]

DIFFICULTY_CHOICES_EXTENDED = [
    ('beginner', 'Beginner'),
    ('easy', 'Easy'),
    ('medium', 'Medium'),
    ('hard', 'Hard'),
    ('expert', 'Expert'),
    ('legendary', 'Legendary'),
]
