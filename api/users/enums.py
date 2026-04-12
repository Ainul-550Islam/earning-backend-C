"""
api/users/enums.py
Python Enums — type-safe choices
"""
from enum import Enum, IntEnum


class UserStatusEnum(str, Enum):
    ACTIVE    = 'active'
    INACTIVE  = 'inactive'
    SUSPENDED = 'suspended'
    BANNED    = 'banned'
    PENDING   = 'pending'

    @classmethod
    def active_states(cls):
        return [cls.ACTIVE]

    @classmethod
    def blocked_states(cls):
        return [cls.SUSPENDED, cls.BANNED]


class UserTierEnum(str, Enum):
    FREE     = 'FREE'
    BRONZE   = 'BRONZE'
    SILVER   = 'SILVER'
    GOLD     = 'GOLD'
    PLATINUM = 'PLATINUM'
    DIAMOND  = 'DIAMOND'

    def next_tier(self):
        order = [
            UserTierEnum.FREE,
            UserTierEnum.BRONZE,
            UserTierEnum.SILVER,
            UserTierEnum.GOLD,
            UserTierEnum.PLATINUM,
            UserTierEnum.DIAMOND,
        ]
        idx = order.index(self)
        return order[idx + 1] if idx < len(order) - 1 else self

    def is_premium(self):
        return self in [
            UserTierEnum.GOLD,
            UserTierEnum.PLATINUM,
            UserTierEnum.DIAMOND,
        ]


class UserRoleEnum(str, Enum):
    USER      = 'user'
    MODERATOR = 'moderator'
    ADMIN     = 'admin'
    SUPERUSER = 'superuser'

    def is_staff(self):
        return self in [
            UserRoleEnum.MODERATOR,
            UserRoleEnum.ADMIN,
            UserRoleEnum.SUPERUSER,
        ]


class OTPPurposeEnum(str, Enum):
    REGISTRATION     = 'registration'
    LOGIN            = 'login'
    PASSWORD_RESET   = 'password_reset'
    PHONE_VERIFY     = 'phone_verify'
    EMAIL_VERIFY     = 'email_verify'
    WITHDRAWAL       = 'withdrawal'
    PROFILE_CHANGE   = 'profile_change'
    TWO_FACTOR       = 'two_factor'


class OTPChannelEnum(str, Enum):
    SMS   = 'sms'
    EMAIL = 'email'
    WHATSAPP = 'whatsapp'


class LoginMethodEnum(str, Enum):
    PASSWORD   = 'password'
    OTP        = 'otp'
    GOOGLE     = 'google'
    FACEBOOK   = 'facebook'
    MAGIC_LINK = 'magic_link'
    API_KEY    = 'api_key'
    PASSKEY    = 'passkey'


class GenderEnum(str, Enum):
    MALE       = 'male'
    FEMALE     = 'female'
    OTHER      = 'other'
    PREFER_NOT = 'prefer_not'


class MFAMethodEnum(str, Enum):
    TOTP        = 'totp'       # Google Authenticator
    SMS         = 'sms'
    EMAIL       = 'email'
    BACKUP_CODE = 'backup_code'


class AccountActionEnum(str, Enum):
    """Admin actions on user account"""
    SUSPEND  = 'suspend'
    BAN      = 'ban'
    ACTIVATE = 'activate'
    RESET_PW = 'reset_password'
    VERIFY   = 'verify'
    WARN     = 'warn'


class NotificationChannelEnum(str, Enum):
    """
    শুধু reference — actual logic api.notifications-এ
    users app শুধু এই enum ব্যবহার করে preference store করতে
    """
    EMAIL    = 'email'
    SMS      = 'sms'
    PUSH     = 'push'
    IN_APP   = 'in_app'
    WHATSAPP = 'whatsapp'


class VerificationBadgeEnum(str, Enum):
    NONE     = 'none'
    EMAIL    = 'email_verified'
    PHONE    = 'phone_verified'
    KYC      = 'kyc_verified'     # api.kyc approve করলে আসে
    PREMIUM  = 'premium'


class WalletEventEnum(str, Enum):
    """
    শুধু reference — actual logic api.wallet-এ
    """
    CREDIT   = 'credit'
    DEBIT    = 'debit'
    HOLD     = 'hold'
    RELEASE  = 'release'
    WITHDRAW = 'withdraw'


class ReferralStatusEnum(str, Enum):
    """
    শুধু reference — actual logic api.referral-এ
    """
    PENDING   = 'pending'
    QUALIFIED = 'qualified'
    REWARDED  = 'rewarded'
    REJECTED  = 'rejected'


class ActivityTypeEnum(str, Enum):
    LOGIN          = 'login'
    LOGOUT         = 'logout'
    PROFILE_UPDATE = 'profile_update'
    PASSWORD_CHANGE= 'password_change'
    OFFER_CLICK    = 'offer_click'
    OFFER_COMPLETE = 'offer_complete'
    WITHDRAWAL_REQ = 'withdrawal_request'
    KYC_SUBMIT     = 'kyc_submit'
    REFERRAL_SHARE = 'referral_share'
    TIER_UPGRADE   = 'tier_upgrade'
    BADGE_EARNED   = 'badge_earned'
