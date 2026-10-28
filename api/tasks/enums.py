"""
tasks/enums.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Central enums.  Uses stdlib Enum so no Django dependency at all —
Django's TextChoices just adds .label convenience which we don't need
here.  These classes are usable in both Django model fields and pure
Python code.
"""

from enum import Enum


class PostbackStatus(str, Enum):
    PENDING   = 'pending'
    SENT      = 'sent'
    FAILED    = 'failed'
    RETRYING  = 'retrying'
    SKIPPED   = 'skipped'
    DUPLICATE = 'duplicate'


class ClickStatus(str, Enum):
    VALID     = 'valid'
    INVALID   = 'invalid'
    DUPLICATE = 'duplicate'
    FRAUD     = 'fraud'
    EXPIRED   = 'expired'


class ConversionStatus(str, Enum):
    PENDING  = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    REVERSED = 'reversed'
    FRAUD    = 'fraud'


class LeaderboardType(str, Enum):
    EARNINGS  = 'earnings'
    POINTS    = 'points'
    REFERRALS = 'referrals'
    TASKS     = 'tasks'
    STREAK    = 'streak'


class LeaderboardScope(str, Enum):
    GLOBAL   = 'global'
    REGIONAL = 'regional'
    COUNTRY  = 'country'
    WEEKLY   = 'weekly'
    MONTHLY  = 'monthly'


class RewardTransactionType(str, Enum):
    EARN   = 'earn'
    REDEEM = 'redeem'
    EXPIRE = 'expire'
    ADJUST = 'adjust'
    REFUND = 'refund'
    BONUS  = 'bonus'


__all__ = [
    'PostbackStatus', 'ClickStatus', 'ConversionStatus',
    'LeaderboardType', 'LeaderboardScope', 'RewardTransactionType',
]
