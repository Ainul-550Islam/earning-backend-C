# earning_backend/api/notifications/constants.py
"""
Notification system constants — CPAlead/earning site specific.
"""
from enum import Enum


class NotificationTypes(Enum):
    """All notification types for earning site."""
    # System
    SYSTEM_UPDATE = 'system_update'
    MAINTENANCE = 'maintenance'
    ANNOUNCEMENT = 'announcement'
    NEW_FEATURE = 'new_feature'

    # Financial
    WITHDRAWAL_SUCCESS = 'withdrawal_success'
    WITHDRAWAL_FAILED = 'withdrawal_failed'
    WITHDRAWAL_PENDING = 'withdrawal_pending'
    WITHDRAWAL_APPROVED = 'withdrawal_approved'
    WITHDRAWAL_REJECTED = 'withdrawal_rejected'
    DEPOSIT_SUCCESS = 'deposit_success'
    WALLET_CREDITED = 'wallet_credited'
    WALLET_DEBITED = 'wallet_debited'
    LOW_BALANCE = 'low_balance'
    BONUS_ADDED = 'bonus_added'
    CASHBACK = 'cashback'

    # Task / Offer / Survey (CPAlead specific)
    TASK_ASSIGNED = 'task_assigned'
    TASK_COMPLETED = 'task_completed'
    TASK_APPROVED = 'task_approved'
    TASK_REJECTED = 'task_rejected'
    TASK_EXPIRED = 'task_expired'
    TASK_REWARD = 'task_reward'
    OFFER_AVAILABLE = 'offer_available'
    OFFER_COMPLETED = 'offer_completed'
    SURVEY_AVAILABLE = 'survey_available'
    SURVEY_COMPLETED = 'survey_completed'
    DAILY_REWARD = 'daily_reward'
    STREAK_REWARD = 'streak_reward'

    # Referral
    REFERRAL_SIGNUP = 'referral_signup'
    REFERRAL_COMPLETED = 'referral_completed'
    REFERRAL_REWARD = 'referral_reward'
    TEAM_BONUS = 'team_bonus'

    # Security
    LOGIN_SUCCESS = 'login_success'
    LOGIN_NEW_DEVICE = 'login_new_device'
    LOGIN_NEW_LOCATION = 'login_new_location'
    PASSWORD_CHANGED = 'password_changed'
    TWO_FACTOR_ENABLED = 'two_factor_enabled'
    SUSPICIOUS_ACTIVITY = 'suspicious_activity'
    ACCOUNT_LOCKED = 'account_locked'
    KYC_SUBMITTED = 'kyc_submitted'
    KYC_APPROVED = 'kyc_approved'
    KYC_REJECTED = 'kyc_rejected'
    FRAUD_DETECTED = 'fraud_detected'

    # Achievement / Gamification
    LEVEL_UP = 'level_up'
    BADGE_EARNED = 'badge_earned'
    ACHIEVEMENT_UNLOCKED = 'achievement_unlocked'
    MILESTONE_REACHED = 'milestone_reached'
    RANK_UP = 'rank_up'

    # CPAlead / Offerwall
    OFFER_COMPLETED = 'offer_completed'
    OFFER_AVAILABLE = 'offer_available'
    POSTBACK_RECEIVED = 'postback_received'
    POSTBACK_FAILED = 'postback_failed'
    IP_FRAUD_BLOCKED = 'ip_fraud_blocked'
    ACCOUNT_SUSPENDED = 'account_suspended'
    ACCOUNT_REINSTATED = 'account_reinstated'
    ACCOUNT_WARNING = 'account_warning'
    AFFILIATE_COMMISSION = 'affiliate_commission'
    SUB_AFFILIATE_EARN = 'sub_affiliate_earn'
    LEADERBOARD_UPDATE = 'leaderboard_update'
    PUBLISHER_PAYOUT = 'publisher_payout'
    CONVERSION_RECEIVED = 'conversion_received'
    CAMPAIGN_LIVE = 'campaign_live'
    CAMPAIGN_PAUSED = 'campaign_paused'

    # Support
    TICKET_CREATED = 'ticket_created'
    TICKET_UPDATED = 'ticket_updated'
    TICKET_RESOLVED = 'ticket_resolved'

    # Marketing
    PROMOTION = 'promotion'
    FLASH_SALE = 'flash_sale'
    SPECIAL_OFFER = 'special_offer'


class NotificationPriority(Enum):
    LOWEST = 'lowest'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'
    CRITICAL = 'critical'


class NotificationChannels(Enum):
    IN_APP = 'in_app'
    SLACK = 'slack'
    DISCORD = 'discord'
    VOICE = 'voice'
    TEAMS = 'teams'
    LINE = 'line'
    PUSH = 'push'
    EMAIL = 'email'
    SMS = 'sms'
    TELEGRAM = 'telegram'
    WHATSAPP = 'whatsapp'
    BROWSER = 'browser'
    ALL = 'all'


class NotificationStatus(Enum):
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    PENDING = 'pending'
    SENDING = 'sending'
    SENT = 'sent'
    DELIVERED = 'delivered'
    READ = 'read'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'


# Priority map — higher number = more important
PRIORITY_SCORE = {
    'lowest': 1, 'low': 2, 'medium': 5,
    'high': 7, 'urgent': 9, 'critical': 10,
}

# Template variables available for each notification type
TEMPLATE_VARIABLES = {
    'user': ['username', 'email', 'first_name', 'last_name', 'phone'],
    'task': ['task_id', 'task_title', 'reward_amount', 'status', 'deadline'],
    'payment': ['amount', 'transaction_id', 'payment_method', 'status', 'currency'],
    'referral': ['referral_code', 'reward_amount', 'friend_name', 'total_referrals'],
    'system': ['version', 'update_date', 'features', 'maintenance_time'],
    'wallet': ['balance', 'amount', 'currency', 'transaction_id'],
    'kyc': ['document_type', 'rejection_reason', 'verification_date'],
    'achievement': ['badge_name', 'level', 'rank', 'points_earned'],
    'campaign': ['campaign_name', 'offer_title', 'expiry_date', 'reward'],
}

# Notification settings
NOTIFICATION_SETTINGS = {
    'MAX_TITLE_LENGTH': 255,
    'MAX_MESSAGE_LENGTH': 2000,
    'DEFAULT_EXPIRY_DAYS': 30,
    'BULK_SEND_LIMIT': 10000,
    'PUSH_RETRY_ATTEMPTS': 3,
    'EMAIL_RETRY_ATTEMPTS': 2,
    'SMS_RETRY_ATTEMPTS': 2,
    'FCM_BATCH_SIZE': 500,
    'DEFAULT_DAILY_FATIGUE_LIMIT': 10,
    'DEFAULT_WEEKLY_FATIGUE_LIMIT': 50,
    'QUEUE_PROCESSING_BATCH_SIZE': 100,
    'MAX_CAMPAIGN_BATCH_SIZE': 500,
    'SEGMENT_CACHE_TTL_SECONDS': 300,
}

# Channel → Provider mapping
CHANNEL_PROVIDERS = {
    'in_app': 'database',
    'push': 'fcm_or_apns',
    'email': 'sendgrid_or_smtp',
    'sms': 'shoho_or_twilio',
    'telegram': 'telegram_bot',
    'whatsapp': 'twilio_whatsapp',
    'browser': 'webpush_vapid',
}

# API response messages (Bangla + English)
MESSAGES = {
    'NOTIFICATION_CREATED': 'Notification created successfully.',
    'NOTIFICATION_UPDATED': 'Notification updated.',
    'NOTIFICATION_DELETED': 'Notification deleted.',
    'MARKED_AS_READ': 'Marked as read.',
    'ALL_MARKED_AS_READ': 'All notifications marked as read.',
    'PREFERENCE_UPDATED': 'Preferences updated.',
    'DEVICE_REGISTERED': 'Device registered successfully.',
    'DEVICE_UNREGISTERED': 'Device removed.',
    'OPT_OUT_SUCCESS': 'You have been unsubscribed.',
    'RESUBSCRIBED': 'You have been re-subscribed.',
    'CAMPAIGN_STARTED': 'Campaign started.',
    'CAMPAIGN_CANCELLED': 'Campaign cancelled.',
    'INVALID_DATA': 'Invalid data provided.',
    'NOT_FOUND': 'Not found.',
    'PERMISSION_DENIED': 'Permission denied.',
    'FATIGUED': 'Too many notifications today. Please try again tomorrow.',
}

# Error codes
ERROR_CODES = {
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'NOT_FOUND': 'NOT_FOUND',
    'PERMISSION_DENIED': 'PERMISSION_DENIED',
    'SERVER_ERROR': 'SERVER_ERROR',
    'RATE_LIMITED': 'RATE_LIMITED',
    'PROVIDER_ERROR': 'PROVIDER_ERROR',
    'INVALID_TOKEN': 'INVALID_TOKEN',
    'USER_FATIGUED': 'USER_FATIGUED',
    'USER_OPTED_OUT': 'USER_OPTED_OUT',
}
