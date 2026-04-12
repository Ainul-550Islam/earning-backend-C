"""
api/users/constants.py
সব User-related constants এক জায়গায়
অন্য app এখান থেকে import করবে — duplicate করবে না
"""

# ─────────────────────────────────────────
# USER STATUS
# ─────────────────────────────────────────
class UserStatus:
    ACTIVE    = 'active'
    INACTIVE  = 'inactive'
    SUSPENDED = 'suspended'
    BANNED    = 'banned'
    PENDING   = 'pending'

    CHOICES = [
        (ACTIVE,    'Active'),
        (INACTIVE,  'Inactive'),
        (SUSPENDED, 'Suspended'),
        (BANNED,    'Banned'),
        (PENDING,   'Pending Verification'),
    ]


# ─────────────────────────────────────────
# USER TIER
# ─────────────────────────────────────────
class UserTier:
    FREE     = 'FREE'
    BRONZE   = 'BRONZE'
    SILVER   = 'SILVER'
    GOLD     = 'GOLD'
    PLATINUM = 'PLATINUM'
    DIAMOND  = 'DIAMOND'

    CHOICES = [
        (FREE,     'Free'),
        (BRONZE,   'Bronze'),
        (SILVER,   'Silver'),
        (GOLD,     'Gold'),
        (PLATINUM, 'Platinum'),
        (DIAMOND,  'Diamond'),
    ]

    # প্রতিটি tier-এ minimum total_earned (USD)
    THRESHOLDS = {
        FREE:     0,
        BRONZE:   10,
        SILVER:   50,
        GOLD:     200,
        PLATINUM: 500,
        DIAMOND:  2000,
    }

    # প্রতিটি tier-এ withdrawal minimum (USD)
    MIN_WITHDRAWAL = {
        FREE:     5.00,
        BRONZE:   3.00,
        SILVER:   2.00,
        GOLD:     1.00,
        PLATINUM: 0.50,
        DIAMOND:  0.25,
    }

    # প্রতিটি tier-এ referral bonus %
    REFERRAL_BONUS = {
        FREE:     5,
        BRONZE:   7,
        SILVER:   10,
        GOLD:     12,
        PLATINUM: 15,
        DIAMOND:  20,
    }


# ─────────────────────────────────────────
# USER ROLE
# ─────────────────────────────────────────
class UserRole:
    USER      = 'user'
    MODERATOR = 'moderator'
    ADMIN     = 'admin'
    SUPERUSER = 'superuser'

    CHOICES = [
        (USER,      'User'),
        (MODERATOR, 'Moderator'),
        (ADMIN,     'Admin'),
        (SUPERUSER, 'Super User'),
    ]

    STAFF_ROLES = [MODERATOR, ADMIN, SUPERUSER]


# ─────────────────────────────────────────
# AUTH CONSTANTS
# ─────────────────────────────────────────
class AuthConstants:
    # OTP
    OTP_LENGTH          = 6
    OTP_EXPIRY_MINUTES  = 10
    OTP_MAX_ATTEMPTS    = 5
    OTP_RESEND_COOLDOWN = 60  # seconds

    # JWT
    ACCESS_TOKEN_LIFETIME_MINUTES  = 60
    REFRESH_TOKEN_LIFETIME_DAYS    = 30

    # Brute force
    MAX_LOGIN_ATTEMPTS     = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Magic link
    MAGIC_LINK_EXPIRY_MINUTES = 15

    # API Key
    API_KEY_PREFIX  = 'ek_'   # earning key
    API_KEY_LENGTH  = 48

    # Session
    MAX_ACTIVE_SESSIONS = 5


# ─────────────────────────────────────────
# PROFILE CONSTANTS
# ─────────────────────────────────────────
class ProfileConstants:
    AVATAR_MAX_SIZE_MB   = 5
    AVATAR_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
    AVATAR_DIMENSIONS    = (400, 400)   # resize করবে

    BIO_MAX_LENGTH       = 500
    USERNAME_MIN_LENGTH  = 3
    USERNAME_MAX_LENGTH  = 30
    USERNAME_REGEX       = r'^[a-zA-Z0-9_]+$'

    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
        ('other',  'Other'),
        ('prefer_not', 'Prefer not to say'),
    ]


# ─────────────────────────────────────────
# WALLET BRIDGE CONSTANTS (api.wallet থেকে আসে)
# ─────────────────────────────────────────
class WalletConstants:
    MIN_BALANCE_FOR_WITHDRAWAL = 1.00  # USD
    HOLD_PERIOD_DAYS           = 3     # conversion hold
    MAX_DAILY_WITHDRAWAL       = 500.00


# ─────────────────────────────────────────
# REFERRAL CONSTANTS (api.referral থেকে আসে)
# ─────────────────────────────────────────
class ReferralConstants:
    CODE_LENGTH         = 8
    CODE_PREFIX         = 'EARN'
    SIGNUP_BONUS_COINS  = 20
    REFERRER_BONUS_COINS= 50
    MAX_REFERRAL_LEVELS = 3


# ─────────────────────────────────────────
# CACHE KEYS
# ─────────────────────────────────────────
class CacheKeys:
    USER_PROFILE      = 'user:profile:{user_id}'
    USER_BALANCE      = 'user:balance:{user_id}'
    USER_TIER         = 'user:tier:{user_id}'
    USER_PERMISSIONS  = 'user:perms:{user_id}'
    LOGIN_ATTEMPTS    = 'auth:attempts:{identifier}'
    OTP_CODE          = 'auth:otp:{user_id}:{purpose}'
    MAGIC_LINK        = 'auth:magic:{token}'
    API_KEY           = 'auth:apikey:{key_hash}'
    RATE_LIMIT        = 'rl:user:{user_id}:{action}'

    # TTL (seconds)
    TTL_PROFILE     = 300       # 5 min
    TTL_BALANCE     = 60        # 1 min
    TTL_PERMISSIONS = 600       # 10 min
    TTL_OTP         = 600       # 10 min
    TTL_MAGIC_LINK  = 900       # 15 min
    TTL_API_KEY     = 3600      # 1 hour


# ─────────────────────────────────────────
# ACTIVITY / EVENT NAMES
# ─────────────────────────────────────────
class UserEvent:
    REGISTERED      = 'user.registered'
    LOGGED_IN       = 'user.logged_in'
    LOGGED_OUT      = 'user.logged_out'
    PASSWORD_CHANGED= 'user.password_changed'
    PROFILE_UPDATED = 'user.profile_updated'
    TIER_UPGRADED   = 'user.tier_upgraded'
    KYC_SUBMITTED   = 'user.kyc_submitted'    # api.kyc কে signal দেবে
    KYC_APPROVED    = 'user.kyc_approved'     # api.kyc থেকে signal আসবে
    WITHDRAWAL_REQ  = 'user.withdrawal_requested'  # api.wallet কে signal দেবে
    REFERRAL_JOINED = 'user.referral_joined'       # api.referral কে signal দেবে


# ─────────────────────────────────────────
# ERROR CODES
# ─────────────────────────────────────────
class ErrorCode:
    USER_NOT_FOUND      = 'USER_001'
    INVALID_CREDENTIALS = 'USER_002'
    ACCOUNT_SUSPENDED   = 'USER_003'
    EMAIL_NOT_VERIFIED  = 'USER_004'
    OTP_EXPIRED         = 'USER_005'
    OTP_INVALID         = 'USER_006'
    OTP_MAX_ATTEMPTS    = 'USER_007'
    ACCOUNT_LOCKED      = 'USER_008'
    INVALID_TOKEN       = 'USER_009'
    TOKEN_EXPIRED       = 'USER_010'
    DUPLICATE_USERNAME  = 'USER_011'
    DUPLICATE_EMAIL     = 'USER_012'
    DUPLICATE_PHONE     = 'USER_013'
    INVALID_API_KEY     = 'USER_014'
    PROFILE_INCOMPLETE  = 'USER_015'
    KYC_REQUIRED        = 'USER_016'
    INSUFFICIENT_BALANCE= 'USER_017'
    RATE_LIMIT_EXCEEDED = 'USER_018'
