"""
api/tasks/choices.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All Django model choices, TextChoices, IntegerChoices, and Python Enums
for the tasks system. Single source of truth for all option sets.
"""

from enum import Enum
_TextChoices    = Enum
_IntegerChoices = Enum
try:
    from django.db import models
    # Only use Django TextChoices if it is a real class (not a MagicMock)
    if isinstance(models.TextChoices, type) and issubclass(models.TextChoices, Enum):
        _TextChoices    = models.TextChoices
        _IntegerChoices = models.IntegerChoices
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# TASK SYSTEM CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class TaskStatus(_TextChoices):
    ACTIVE     = 'active',     'Active'
    INACTIVE   = 'inactive',   'Inactive'
    PENDING    = 'pending',    'Pending Review'
    ARCHIVED   = 'archived',   'Archived'
    SCHEDULED  = 'scheduled',  'Scheduled'


class TaskSystemType(_TextChoices):
    CLICK_VISIT       = 'click_visit',       'Click & Visit'
    SOCIAL_FOLLOW     = 'social_follow',     'Social Follow'
    VIDEO_WATCH       = 'video_watch',       'Video Watch'
    APP_INSTALL       = 'app_install',       'App Install (CPI)'
    APP_EVENT         = 'app_event',         'In-App Event (CPE)'
    SURVEY            = 'survey',            'Survey'
    QUIZ              = 'quiz',              'Personality Quiz'
    EMAIL_SUBMIT      = 'email_submit',      'Email Submit'
    REGISTRATION      = 'registration',      'Registration'
    PURCHASE          = 'purchase',          'Purchase (CPS)'
    DOWNLOAD          = 'download',          'Download'
    CONTENT_LOCK      = 'content_lock',      'Content Locker'
    LINK_LOCK         = 'link_lock',         'Link Locker'
    FILE_LOCK         = 'file_lock',         'File Locker'
    DAILY_LOGIN       = 'daily_login',       'Daily Login'
    REFERRAL          = 'referral',          'Referral'
    CUSTOM            = 'custom',            'Custom'
    SMARTLINK         = 'smartlink',         'Smartlink CPA'
    PPC               = 'ppc',               'Pay Per Click'
    BANNER_AD         = 'banner_ad',         'Banner Ad Click'
    POPUNDER          = 'popunder',          'Pop-Under'
    PUSH_NOTIFICATION = 'push_notification', 'Push Notification'
    INTERSTITIAL      = 'interstitial',      'Interstitial Ad'


class TaskCategory(_TextChoices):
    DAILY_RETENTION  = 'daily_retention',  'Daily Retention'
    MONETIZATION     = 'monetization',     'Monetization'
    ACQUISITION      = 'acquisition',      'User Acquisition'
    ENGAGEMENT       = 'engagement',       'Engagement'
    SOCIAL           = 'social',           'Social Media'
    GAMING           = 'gaming',           'Gaming'
    FINANCE          = 'finance',          'Finance'
    HEALTH           = 'health',           'Health & Fitness'
    SHOPPING         = 'shopping',         'Shopping'
    EDUCATION        = 'education',        'Education'
    ENTERTAINMENT    = 'entertainment',    'Entertainment'
    TRAVEL           = 'travel',           'Travel'
    FOOD             = 'food',             'Food & Beverage'
    TECHNOLOGY       = 'technology',       'Technology'
    NEWS             = 'news',             'News & Media'
    SURVEY           = 'survey',           'Survey & Research'
    QUIZ             = 'quiz',             'Quiz & Games'
    CRYPTO           = 'crypto',           'Cryptocurrency'
    METAVERSE        = 'metaverse',        'Metaverse / Web3'


class CompletionStatus(_TextChoices):
    PENDING    = 'pending',    'Pending'
    COMPLETED  = 'completed',  'Completed'
    FAILED     = 'failed',     'Failed'
    REJECTED   = 'rejected',   'Rejected'
    EXPIRED    = 'expired',    'Expired'
    CANCELLED  = 'cancelled',  'Cancelled'
    REVERSED   = 'reversed',   'Reversed'
    IN_REVIEW  = 'in_review',  'Under Review'


class RewardCurrency(_TextChoices):
    USD    = 'USD',    'US Dollar'
    EUR    = 'EUR',    'Euro'
    GBP    = 'GBP',   'British Pound'
    BDT    = 'BDT',   'Bangladeshi Taka'
    POINTS = 'POINTS', 'Platform Points'
    COINS  = 'COINS',  'Virtual Coins'
    MANA   = 'MANA',  'Decentraland MANA'
    MATIC  = 'MATIC', 'Polygon MATIC'
    USDT   = 'USDT',  'USDT Stablecoin'


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT & WITHDRAWAL CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class WithdrawalStatus(_TextChoices):
    PENDING    = 'pending',    'Pending'
    PROCESSING = 'processing', 'Processing'
    APPROVED   = 'approved',   'Approved'
    COMPLETED  = 'completed',  'Completed'
    FAILED     = 'failed',     'Failed'
    REJECTED   = 'rejected',   'Rejected'
    CANCELLED  = 'cancelled',  'Cancelled'
    ON_HOLD    = 'on_hold',    'On Hold'


class PaymentMethod(_TextChoices):
    PAYPAL      = 'paypal',      'PayPal'
    PAYONEER    = 'payoneer',    'Payoneer'
    USDT_TRC20  = 'usdt_trc20',  'USDT (TRC20)'
    USDT_ERC20  = 'usdt_erc20',  'USDT (ERC20)'
    BITCOIN     = 'bitcoin',     'Bitcoin'
    ETHEREUM    = 'ethereum',    'Ethereum'
    BANK_WIRE   = 'bank_wire',   'Bank Wire Transfer'
    BANK_ACH    = 'bank_ach',    'Bank ACH (US)'
    BKASH       = 'bkash',       'bKash (BD)'
    NAGAD       = 'nagad',       'Nagad (BD)'
    ROCKET      = 'rocket',      'Rocket (BD)'
    MONEYGRAM   = 'moneygram',   'MoneyGram'
    WISE        = 'wise',        'Wise (TransferWise)'
    VENMO       = 'venmo',       'Venmo'
    CASHAPP     = 'cashapp',     'Cash App'
    CHECK       = 'check',       'Check / Cheque'
    GIFT_CARD   = 'gift_card',   'Gift Card'


class WithdrawalType(_TextChoices):
    MANUAL         = 'manual',          'Manual Request'
    DAILY_AUTO     = 'daily_auto',      'Daily Auto Payout'
    PUBLISHER_PAY  = 'publisher_pay',   'Publisher Payout'
    CRYPTO         = 'crypto',          'Crypto Withdrawal'
    USDT_FAST      = 'usdt_fast_pay',   'USDT Fast Pay'
    TEST_TRAFFIC   = 'test_traffic',    'Test Traffic Purchase'
    REFUND         = 'refund',          'Refund'
    BONUS          = 'bonus',           'Bonus Payout'


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD & KYC CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class FraudRiskLevel(_TextChoices):
    CLEAN   = 'clean',   'Clean (0-19)'
    LOW     = 'low',     'Low Risk (20-39)'
    MEDIUM  = 'medium',  'Medium Risk (40-59)'
    HIGH    = 'high',    'High Risk (60-79)'
    CRITICAL = 'critical', 'Critical Risk (80-100)'


class KYCTier(_TextChoices):
    NONE     = 'none',     'Not Verified'
    BASIC    = 'basic',    'Basic (Auto-Approved)'
    STANDARD = 'standard', 'Standard (ID Verified)'
    FULL     = 'full',     'Full (ID + Address)'
    EDD      = 'edd',      'Enhanced Due Diligence'


class KYCStatus(_TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    STARTED     = 'started',     'In Progress'
    PENDING     = 'pending',     'Pending Review'
    APPROVED    = 'approved',    'Approved'
    REJECTED    = 'rejected',    'Rejected'
    EXPIRED     = 'expired',     'Expired'
    SUSPENDED   = 'suspended',   'Suspended'


class KYCProvider(_TextChoices):
    SUMSUB   = 'sumsub',   'Sumsub'
    ONFIDO   = 'onfido',   'Onfido'
    JUMIO    = 'jumio',    'Jumio'
    MANUAL   = 'manual',   'Manual Review'
    AUTO     = 'auto',     'Auto-Approved'


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISHER / ADVERTISER CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class PublisherTier(_TextChoices):
    BRONZE   = 'bronze',   'Bronze'
    SILVER   = 'silver',   'Silver'
    GOLD     = 'gold',     'Gold'
    PLATINUM = 'platinum', 'Platinum'


class TrafficTier(_TextChoices):
    TIER_1      = 'tier_1',      'Tier 1 (Premium — US/UK/CA/AU)'
    TIER_2      = 'tier_2',      'Tier 2 (Standard)'
    TIER_3      = 'tier_3',      'Tier 3 (Low Quality)'
    LOW_QUALITY = 'low_quality', 'Low Quality (Blocked)'


class CampaignStatus(_TextChoices):
    DRAFT          = 'draft',               'Draft'
    PENDING_REVIEW = 'pending_review',      'Pending Review'
    PENDING_MANUAL = 'pending_manual_review','Pending Manual Review'
    ACTIVE         = 'active',              'Active'
    PAUSED         = 'paused',              'Paused'
    COMPLETED      = 'completed',           'Completed'
    REJECTED       = 'rejected',            'Rejected'
    ARCHIVED       = 'archived',            'Archived'


class CampaignType(_TextChoices):
    CPA  = 'cpa',  'CPA (Cost Per Action)'
    CPI  = 'cpi',  'CPI (Cost Per Install)'
    CPC  = 'cpc',  'CPC (Cost Per Click)'
    CPL  = 'cpl',  'CPL (Cost Per Lead)'
    CPS  = 'cps',  'CPS (Cost Per Sale)'
    CPE  = 'cpe',  'CPE (Cost Per Engagement)'
    CPM  = 'cpm',  'CPM (Cost Per 1000 Impressions)'
    FLAT = 'flat', 'Flat Rate'


class OfferType(_TextChoices):
    STANDARD    = 'standard',    'Standard CPA'
    EMAIL_SUBMIT = 'email_submit', 'Email Submit'
    QUIZ         = 'quiz',        'Personality Quiz'
    SURVEY       = 'survey',      'Survey'
    APP_INSTALL  = 'app_install', 'Mobile App Install'
    APP_EVENT    = 'app_event',   'In-App Event'
    VIDEO        = 'video',       'Video Watch'
    NATIVE       = 'native',      'Native Ad'
    CONTENT_LOCK = 'content_lock', 'Content Lock'
    SMARTLINK    = 'smartlink',   'Smartlink'
    CO_REG       = 'co_reg',      'Co-Registration Lead'
    CLICK_TO_CALL = 'click_to_call', 'Click to Call'
    FREE_TRIAL   = 'free_trial',  'Free Trial'
    SWEEPSTAKES  = 'sweepstakes', 'Sweepstakes Entry'


# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICATION CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class BadgeCategory(_TextChoices):
    EARNINGS   = 'earnings',   'Earning Milestones'
    ACTIVITY   = 'activity',   'Activity & Engagement'
    SOCIAL     = 'social',     'Social & Referrals'
    STREAK     = 'streak',     'Daily Streaks'
    SPECIAL    = 'special',    'Special Achievements'
    VIP        = 'vip',        'VIP Status'
    COMMUNITY  = 'community',  'Community'


class UserSegment(_TextChoices):
    NEW_USER    = 'new_user',    'New User (< 7 days)'
    CASUAL      = 'casual_user', 'Casual User'
    POWER       = 'power_user',  'Power User'
    VIP         = 'vip_user',    'VIP User'
    CHURNED     = 'churned',     'Churned'
    AT_RISK     = 'at_risk',     'At Risk of Churning'
    REACTIVATED = 'reactivated', 'Reactivated'
    DORMANT     = 'dormant',     'Dormant (> 30 days)'


class LeaderboardPeriod(_TextChoices):
    DAILY   = 'daily',   'Daily'
    WEEKLY  = 'weekly',  'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    ALLTIME = 'alltime', 'All Time'


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW & MONITORING CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowStatus(_TextChoices):
    PENDING   = 'pending',   'Pending'
    RUNNING   = 'running',   'Running'
    SUCCESS   = 'success',   'Success'
    FAILED    = 'failed',    'Failed'
    CANCELLED = 'cancelled', 'Cancelled'
    PARTIAL   = 'partial',   'Partial Success'


class WorkflowTriggerType(_TextChoices):
    MANUAL  = 'manual',  'Manual (API / Admin)'
    CRON    = 'cron',    'Scheduled (Cron)'
    EVENT   = 'event',   'Event-Driven'
    WEBHOOK = 'webhook', 'Webhook'
    CELERY  = 'celery',  'Triggered by Celery Task'


class MonitorStatus(_TextChoices):
    HEALTHY  = 'healthy',  'Healthy'
    DEGRADED = 'degraded', 'Degraded'
    FAILING  = 'failing',  'Failing'
    MISSING  = 'missing',  'Missing (no recent runs)'
    UNKNOWN  = 'unknown',  'Unknown'


class AlertSeverity(_TextChoices):
    INFO     = 'info',     'Informational'
    WARNING  = 'warning',  'Warning'
    CRITICAL = 'critical', 'Critical'
    EMERGENCY = 'emergency', 'Emergency'


class AlertType(_TextChoices):
    FAILURE  = 'failure',  'High Failure Rate'
    SLOW     = 'slow',     'Slow Execution'
    MISSING  = 'missing',  'Task Not Running'
    DLQ      = 'dlq',      'Dead Letter Queue Growth'
    DEPTH    = 'depth',    'Queue Depth Exceeded'
    MEMORY   = 'memory',   'High Memory Usage'
    CPU      = 'cpu',      'High CPU Usage'
    DISK     = 'disk',     'Low Disk Space'
    LATENCY  = 'latency',  'High Latency'


class WorkerStatus(_TextChoices):
    ONLINE   = 'online',   'Online'
    OFFLINE  = 'offline',  'Offline'
    IDLE     = 'idle',     'Idle'
    BUSY     = 'busy',     'Busy'
    DEGRADED = 'degraded', 'Degraded'


class DLQStatus(_TextChoices):
    PENDING   = 'pending',   'Pending Review'
    REQUEUED  = 'requeued',  'Requeued for Retry'
    RESOLVED  = 'resolved',  'Manually Resolved'
    DISCARDED = 'discarded', 'Discarded'


class DLQFailureReason(_TextChoices):
    EXCEPTION        = 'exception',        'Unhandled Exception'
    TIMEOUT          = 'timeout',          'Task Timeout'
    MAX_RETRIES      = 'max_retries',      'Max Retries Exceeded'
    WORKER_LOST      = 'worker_lost',      'Worker Process Lost'
    REVOKED          = 'revoked',          'Task Revoked'
    DESERIALIZATION  = 'deserialization',  'Payload Deserialization Error'
    UNKNOWN          = 'unknown',          'Unknown'


class RetryBackoff(_TextChoices):
    LINEAR      = 'linear',      'Linear'
    EXPONENTIAL = 'exponential', 'Exponential'
    FIBONACCI   = 'fibonacci',   'Fibonacci'
    CONSTANT    = 'constant',    'Constant'


class ScheduleType(_TextChoices):
    CRON     = 'cron',     'Cron Expression'
    INTERVAL = 'interval', 'Fixed Interval'
    SOLAR    = 'solar',    'Solar Event'
    CLOCKED  = 'clocked',  'One-Time'


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT LOCKER CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class LockerType(_TextChoices):
    CONTENT = 'content', 'Content Locker'
    LINK    = 'link',    'Link Locker'
    FILE    = 'file',    'File Locker'
    OVERLAY = 'overlay', 'Overlay Locker'


class OverlayAccessMode(_TextChoices):
    EVERY_TIME = '0h',   'Every Time (0h)'
    DAILY      = '24h',  '24 Hour Access'
    MONTHLY    = '720h', '30 Day Access (720h)'


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS & REPORTING CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class ReportPeriod(_TextChoices):
    HOURLY  = 'hourly',  'Hourly'
    DAILY   = 'daily',   'Daily'
    WEEKLY  = 'weekly',  'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    CUSTOM  = 'custom',  'Custom Range'


class ExportFormat(_TextChoices):
    JSON = 'json', 'JSON'
    CSV  = 'csv',  'CSV'
    XLSX = 'xlsx', 'Excel (XLSX)'
    PDF  = 'pdf',  'PDF'
    XML  = 'xml',  'XML'


class AnalyticsPeriod(_TextChoices):
    ONE_MINUTE   = '1m',  '1 Minute'
    FIVE_MINUTES = '5m',  '5 Minutes'
    ONE_HOUR     = '1h',  '1 Hour'
    ONE_DAY      = '1d',  '1 Day'


# ══════════════════════════════════════════════════════════════════════════════
# CPI / MOBILE CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class MobilePlatform(_TextChoices):
    ANDROID = 'android', 'Android'
    IOS     = 'ios',     'iOS'
    WEB     = 'web',     'Mobile Web'


class MMPProvider(_TextChoices):
    APPSFLYER = 'appsflyer', 'AppsFlyer'
    ADJUST    = 'adjust',    'Adjust'
    KOCHAVA   = 'kochava',   'Kochava'
    BRANCH    = 'branch',    'Branch'
    SINGULAR  = 'singular',  'Singular'
    TENJIN    = 'tenjin',    'Tenjin'


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class NotificationType(_TextChoices):
    REWARD      = 'reward',      'Task Reward'
    WITHDRAWAL  = 'withdrawal',  'Withdrawal Status'
    ALERT       = 'alert',       'Account Alert'
    FRAUD       = 'fraud',       'Fraud Warning'
    OFFER       = 'offer',       'New Offer'
    SYSTEM      = 'system',      'System Message'
    PROMOTION   = 'promotion',   'Promotion'
    ACHIEVEMENT = 'achievement', 'Achievement Unlocked'
    STREAK      = 'streak',      'Streak Bonus'
    MILESTONE   = 'milestone',   'Milestone Reached'
    LEVEL_UP    = 'level_up',    'Level Up!'
    KYC         = 'kyc',         'KYC Update'
    BIRTHDAY    = 'birthday',    'Birthday Bonus'
    COMMUNITY   = 'community',   'Community Points'


class NotificationChannel(_TextChoices):
    IN_APP = 'in_app', 'In-App'
    PUSH   = 'push',   'Push Notification'
    EMAIL  = 'email',  'Email'
    SMS    = 'sms',    'SMS'
    SLACK  = 'slack',  'Slack'


class NotificationSeverity(_TextChoices):
    INFO    = 'info',    'Informational'
    SUCCESS = 'success', 'Success'
    WARNING = 'warning', 'Warning'
    ERROR   = 'error',   'Error'


# ══════════════════════════════════════════════════════════════════════════════
# WEB3 / METAVERSE CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class Web3Token(_TextChoices):
    MANA  = 'mana',  'MANA (Decentraland)'
    MATIC = 'matic', 'MATIC (Polygon)'
    SAND  = 'sand',  'SAND (The Sandbox)'
    GALA  = 'gala',  'GALA (Gala Games)'
    AXS   = 'axs',   'AXS (Axie Infinity)'
    SLP   = 'slp',   'SLP (Smooth Love Potion)'
    ETH   = 'eth',   'ETH (Ethereum)'


class BlockchainNetwork(_TextChoices):
    ETHEREUM = 'ethereum', 'Ethereum Mainnet'
    POLYGON  = 'polygon',  'Polygon (Matic)'
    TRON     = 'tron',     'Tron (TRC20)'
    BSC      = 'bsc',      'Binance Smart Chain'
    RONIN    = 'ronin',    'Ronin (Axie)'
    SOLANA   = 'solana',   'Solana'


# ══════════════════════════════════════════════════════════════════════════════
# DEVICE & GEO CHOICES
# ══════════════════════════════════════════════════════════════════════════════

class DeviceType(_TextChoices):
    DESKTOP = 'desktop', 'Desktop'
    MOBILE  = 'mobile',  'Mobile'
    TABLET  = 'tablet',  'Tablet'
    TV      = 'tv',      'Smart TV'
    UNKNOWN = 'unknown', 'Unknown'


class GeoTier(_TextChoices):
    TIER_1 = 'tier_1', 'Tier 1 (US/UK/CA/AU/DE/NL)'
    TIER_2 = 'tier_2', 'Tier 2 (EU/APAC)'
    TIER_3 = 'tier_3', 'Tier 3 (Rest of World)'


# ══════════════════════════════════════════════════════════════════════════════
# PYTHON ENUMS (for non-model use)
# ══════════════════════════════════════════════════════════════════════════════

class TaskPriority(str, Enum):
    LOW      = 'low'
    NORMAL   = 'normal'
    HIGH     = 'high'
    CRITICAL = 'critical'


class EventType(str, Enum):
    USER_REGISTERED     = 'user.registered'
    USER_VERIFIED       = 'user.verified'
    TASK_COMPLETED      = 'task.completed'
    TASK_FAILED         = 'task.failed'
    OFFER_CONVERTED     = 'offer.converted'
    OFFER_CLICKED       = 'offer.clicked'
    CPI_INSTALLED       = 'cpi.installed'
    SURVEY_COMPLETED    = 'survey.completed'
    QUIZ_COMPLETED      = 'quiz.completed'
    EMAIL_SUBMITTED     = 'email.submitted'
    PAYMENT_WITHDRAWN   = 'payment.withdrawal_requested'
    PAYMENT_COMPLETED   = 'payment.completed'
    FRAUD_DETECTED      = 'fraud.detected'
    KYC_APPROVED        = 'kyc.approved'
    KYC_REJECTED        = 'kyc.rejected'
    PUBLISHER_TIER_UP   = 'publisher.tier_changed'
    LEVEL_UP            = 'user.level_up'
    STREAK_BROKEN       = 'user.streak_broken'
    MILESTONE_REACHED   = 'user.milestone_reached'
    BADGE_AWARDED       = 'user.badge_awarded'
    CAMPAIGN_ACTIVATED  = 'campaign.activated'
    CAMPAIGN_PAUSED     = 'campaign.paused'
    OVERLAY_UNLOCKED    = 'locker.overlay_unlocked'
    CONTENT_UNLOCKED    = 'locker.content_unlocked'


class QueueName(str, Enum):
    DEFAULT   = 'default'
    HIGH      = 'high'
    LOW       = 'low'
    PAYMENTS  = 'payments'
    EMAILS    = 'emails'
    REPORTS   = 'reports'
    ML        = 'ml'
    WEBHOOKS  = 'webhooks'


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_tier_1_countries() -> list:
    """Countries considered Tier 1 for traffic quality."""
    return ['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'NL', 'SE', 'NO', 'DK',
            'FI', 'CH', 'AT', 'BE', 'IE', 'NZ', 'SG', 'JP', 'KR', 'HK']


def get_min_payout_for_method(method: str) -> float:
    """Minimum payout amount per payment method."""
    from decimal import Decimal
    thresholds = {
        'paypal':      1.00,
        'payoneer':    5.00,
        'usdt_trc20': 25.00,
        'usdt_erc20': 25.00,
        'bitcoin':    50.00,
        'ethereum':   30.00,
        'bank_wire': 100.00,
        'bank_ach':    5.00,
        'bkash':       0.75,
        'nagad':       0.75,
        'rocket':      0.75,
        'wise':        5.00,
        'gift_card':   5.00,
    }
    return thresholds.get(method, 0.75)


def get_revenue_share_for_tier(tier: str) -> float:
    """Publisher revenue share percentage per tier."""
    shares = {
        'platinum': 0.85,
        'gold':     0.80,
        'silver':   0.75,
        'bronze':   0.70,
    }
    return shares.get(tier, 0.70)


# Export all choices for easy import
__all__ = [
    'TaskStatus', 'TaskSystemType', 'TaskCategory', 'CompletionStatus',
    'RewardCurrency', 'WithdrawalStatus', 'PaymentMethod', 'WithdrawalType',
    'FraudRiskLevel', 'KYCTier', 'KYCStatus', 'KYCProvider',
    'PublisherTier', 'TrafficTier', 'CampaignStatus', 'CampaignType',
    'OfferType', 'BadgeCategory', 'UserSegment', 'LeaderboardPeriod',
    'WorkflowStatus', 'WorkflowTriggerType', 'MonitorStatus',
    'AlertSeverity', 'AlertType', 'WorkerStatus', 'DLQStatus',
    'DLQFailureReason', 'RetryBackoff', 'ScheduleType',
    'LockerType', 'OverlayAccessMode', 'ReportPeriod', 'ExportFormat',
    'AnalyticsPeriod', 'MobilePlatform', 'MMPProvider',
    'NotificationType', 'NotificationChannel', 'NotificationSeverity',
    'Web3Token', 'BlockchainNetwork', 'DeviceType', 'GeoTier',
    'TaskPriority', 'EventType', 'QueueName',
    'get_tier_1_countries', 'get_min_payout_for_method',
    'get_revenue_share_for_tier',
]


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL CHOICES — Added to resolve missing imports across task files
# ══════════════════════════════════════════════════════════════════════════════

# _m is the same as _TextChoices for the appended choice classes
_m_TextChoices = _TextChoices


class SubscriptionStatus(_m_TextChoices):
    TRIALING    = 'trialing',    'Trialing'
    ACTIVE      = 'active',      'Active'
    PAST_DUE    = 'past_due',    'Past Due'
    CANCELLED   = 'cancelled',   'Cancelled'
    EXPIRED     = 'expired',     'Expired'
    PAUSED      = 'paused',      'Paused'


class PaymentStatus(_m_TextChoices):
    PENDING     = 'pending',     'Pending'
    COMPLETED   = 'completed',   'Completed'
    FAILED      = 'failed',      'Failed'
    REFUNDED    = 'refunded',    'Refunded'
    REVERSED    = 'reversed',    'Reversed'


class BroadcastStatus(_m_TextChoices):
    DRAFT       = 'draft',       'Draft'
    SCHEDULED   = 'scheduled',   'Scheduled'
    SENDING     = 'sending',     'Sending'
    SENT        = 'sent',        'Sent'
    FAILED      = 'failed',      'Failed'
    CANCELLED   = 'cancelled',   'Cancelled'


class ScheduledMessageStatus(_m_TextChoices):
    PENDING     = 'pending',     'Pending'
    SENT        = 'sent',        'Sent'
    FAILED      = 'failed',      'Failed'
    CANCELLED   = 'cancelled',   'Cancelled'


class PresenceStatus(_m_TextChoices):
    ONLINE      = 'online',      'Online'
    AWAY        = 'away',        'Away'
    BUSY        = 'busy',        'Busy'
    OFFLINE     = 'offline',     'Offline'


class CallStatus(_m_TextChoices):
    RINGING     = 'ringing',     'Ringing'
    ACTIVE      = 'active',      'Active'
    ENDED       = 'ended',       'Ended'
    MISSED      = 'missed',      'Missed'
    DECLINED    = 'declined',    'Declined'
    FAILED      = 'failed',      'Failed'


class MessageType(_m_TextChoices):
    TEXT        = 'text',        'Text'
    IMAGE       = 'image',       'Image'
    VIDEO       = 'video',       'Video'
    AUDIO       = 'audio',       'Audio'
    FILE        = 'file',        'File'
    SYSTEM      = 'system',      'System'


class BotStatus(_m_TextChoices):
    IDLE        = 'idle',        'Idle'
    RUNNING     = 'running',     'Running'
    PAUSED      = 'paused',      'Paused'
    ERROR       = 'error',       'Error'
    STOPPED     = 'stopped',     'Stopped'


class ModerationStatus(_m_TextChoices):
    PENDING     = 'pending',     'Pending'
    APPROVED    = 'approved',    'Approved'
    REJECTED    = 'rejected',    'Rejected'
    ESCALATED   = 'escalated',   'Escalated'
    AUTO_OK     = 'auto_ok',     'Auto Approved'
    AUTO_REJECT = 'auto_reject', 'Auto Rejected'


class InventoryStatus(_m_TextChoices):
    AVAILABLE    = 'available',    'Available'
    LOW_STOCK    = 'low_stock',    'Low Stock'
    OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'
    DISCONTINUED = 'discontinued', 'Discontinued'


class CodeStatus(_m_TextChoices):
    ACTIVE      = 'active',      'Active'
    REDEEMED    = 'redeemed',    'Redeemed'
    EXPIRED     = 'expired',     'Expired'
    CANCELLED   = 'cancelled',   'Cancelled'
    RESERVED    = 'reserved',    'Reserved'


class ItemType(_m_TextChoices):
    DIGITAL     = 'digital',     'Digital'
    PHYSICAL    = 'physical',    'Physical'
    VOUCHER     = 'voucher',     'Voucher'
    GIFT_CARD   = 'gift_card',   'Gift Card'
    CRYPTO      = 'crypto',      'Crypto'


class MaintenanceStatus(_m_TextChoices):
    SCHEDULED   = 'scheduled',   'Scheduled'
    ACTIVE      = 'active',      'Active'
    COMPLETED   = 'completed',   'Completed'
    CANCELLED   = 'cancelled',   'Cancelled'


class PolicyStatus(_m_TextChoices):
    DRAFT       = 'draft',       'Draft'
    ACTIVE      = 'active',      'Active'
    ARCHIVED    = 'archived',    'Archived'
    DEPRECATED  = 'deprecated',  'Deprecated'


class SubmissionStatus(_m_TextChoices):
    PENDING     = 'pending',     'Pending'
    APPROVED    = 'approved',    'Approved'
    REJECTED    = 'rejected',    'Rejected'
    FRAUD       = 'fraud',       'Fraud'
    REVERSED    = 'reversed',    'Reversed'


class FraudType(_m_TextChoices):
    CLICK_FRAUD      = 'click_fraud',      'Click Fraud'
    IMPRESSION_FRAUD = 'impression_fraud', 'Impression Fraud'
    CONVERSION_FRAUD = 'conversion_fraud', 'Conversion Fraud'
    ACCOUNT_FRAUD    = 'account_fraud',    'Account Fraud'
    BOT_TRAFFIC      = 'bot_traffic',      'Bot Traffic'


class FraudAction(_m_TextChoices):
    FLAG        = 'flag',        'Flag'
    BLOCK       = 'block',       'Block'
    REVERSE     = 'reverse',     'Reverse'
    BLACKLIST   = 'blacklist',   'Blacklist'
    WARN        = 'warn',        'Warn'


class CommissionStatus(_m_TextChoices):
    PENDING     = 'pending',     'Pending'
    APPROVED    = 'approved',    'Approved'
    PAID        = 'paid',        'Paid'
    REVERSED    = 'reversed',    'Reversed'
    CANCELLED   = 'cancelled',   'Cancelled'


class TransactionType(_m_TextChoices):
    CREDIT      = 'credit',      'Credit'
    DEBIT       = 'debit',       'Debit'
    REVERSAL    = 'reversal',    'Reversal'
    BONUS       = 'bonus',       'Bonus'
    FEE         = 'fee',         'Fee'


class RateSource(_m_TextChoices):
    MANUAL      = 'manual',      'Manual'
    API         = 'api',         'API'
    EXCHANGE    = 'exchange',    'Exchange'
    ORACLE      = 'oracle',      'Oracle'
