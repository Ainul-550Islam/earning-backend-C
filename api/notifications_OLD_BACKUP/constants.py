from enum import Enum


class NotificationTypes(Enum):
    """নোটিফিকেশন টাইপ কনস্ট্যান্টস"""
    SYSTEM_UPDATE = 'system_update'
    TASK_REWARD = 'task_reward'
    WITHDRAWAL = 'withdrawal'
    REFERRAL = 'referral'
    SECURITY = 'security'
    PROMOTIONAL = 'promotional'
    TASK_UPDATE = 'task_update'
    PAYMENT = 'payment'
    OTHER = 'other'


class NotificationPriority(Enum):
    """নোটিফিকেশন প্রায়োরিটি কনস্ট্যান্টস"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'


class NotificationChannels(Enum):
    """নোটিফিকেশন চ্যানেল কনস্ট্যান্টস"""
    IN_APP = 'in_app'
    PUSH = 'push'
    EMAIL = 'email'
    SMS = 'sms'
    ALL = 'all'


# টেমপ্লেট ভেরিয়েবল
TEMPLATE_VARIABLES = {
    'user': ['username', 'email', 'first_name', 'last_name'],
    'task': ['task_id', 'task_title', 'reward_amount', 'status'],
    'payment': ['amount', 'transaction_id', 'payment_method', 'status'],
    'referral': ['referral_code', 'reward_amount', 'friend_name'],
    'system': ['version', 'update_date', 'features'],
}


# নোটিফিকেশন সেটিংস
NOTIFICATION_SETTINGS = {
    'MAX_TITLE_LENGTH': 255,
    'MAX_MESSAGE_LENGTH': 2000,
    'DEFAULT_EXPIRY_DAYS': 30,
    'BULK_SEND_LIMIT': 1000,
    'PUSH_RETRY_ATTEMPTS': 3,
    'EMAIL_RETRY_ATTEMPTS': 2,
}


# এপিআই রেসপন্স মেসেজ
MESSAGES = {
    'NOTIFICATION_CREATED': 'নোটিফিকেশন তৈরি করা হয়েছে।',
    'NOTIFICATION_UPDATED': 'নোটিফিকেশন আপডেট করা হয়েছে।',
    'NOTIFICATION_DELETED': 'নোটিফিকেশন ডিলিট করা হয়েছে।',
    'MARKED_AS_READ': 'নোটিফিকেশন পড়া হিসেবে মার্ক করা হয়েছে।',
    'ALL_MARKED_AS_READ': 'সব নোটিফিকেশন পড়া হিসেবে মার্ক করা হয়েছে।',
    'PREFERENCE_UPDATED': 'প্রিফারেন্স আপডেট করা হয়েছে।',
    'INVALID_DATA': 'অবৈধ ডেটা।',
    'NOT_FOUND': 'নোটিফিকেশন পাওয়া যায়নি।',
    'PERMISSION_DENIED': 'অনুমতি নেই।',
}


# এরর কোড
ERROR_CODES = {
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'NOT_FOUND': 'NOT_FOUND',
    'PERMISSION_DENIED': 'PERMISSION_DENIED',
    'SERVER_ERROR': 'SERVER_ERROR',
    'RATE_LIMITED': 'RATE_LIMITED',
}