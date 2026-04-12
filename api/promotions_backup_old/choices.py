# =============================================================================
# api/promotions/choices.py
# সব Choices এক জায়গায় — models, serializers, filters সবাই এখান থেকে import করবে
# =============================================================================

from django.db import models
from django.utils.translation import gettext_lazy as _


class CategoryType(models.TextChoices):
    SOCIAL  = 'social',  _('Social Media')
    APPS    = 'apps',    _('Mobile Apps')
    WEB     = 'web',     _('Web Tasks')
    SURVEYS = 'surveys', _('Surveys')


class PlatformType(models.TextChoices):
    YOUTUBE    = 'youtube',    _('YouTube')
    FACEBOOK   = 'facebook',   _('Facebook')
    INSTAGRAM  = 'instagram',  _('Instagram')
    TIKTOK     = 'tiktok',     _('TikTok')
    PLAY_STORE = 'play_store', _('Google Play Store')
    APP_STORE  = 'app_store',  _('Apple App Store')
    TWITTER    = 'twitter',    _('Twitter / X')
    OTHER      = 'other',      _('Other')


class CreativeType(models.TextChoices):
    IMAGE  = 'image',  _('Image')
    VIDEO  = 'video',  _('Video')
    BANNER = 'banner', _('Banner')


class CampaignStatus(models.TextChoices):
    DRAFT     = 'draft',     _('Draft')
    PENDING   = 'pending',   _('Pending Review')
    ACTIVE    = 'active',    _('Active')
    PAUSED    = 'paused',    _('Paused')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')


class ProofType(models.TextChoices):
    SCREENSHOT = 'screenshot', _('Screenshot')
    LINK       = 'link',       _('Link / URL')
    TEXT       = 'text',       _('Text Answer')
    VIDEO      = 'video',      _('Screen Recording')


class SubmissionStatus(models.TextChoices):
    PENDING  = 'pending',  _('Pending Review')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')
    DISPUTED = 'disputed', _('Under Dispute')
    EXPIRED  = 'expired',  _('Expired')


class DisputeStatus(models.TextChoices):
    OPEN              = 'open',              _('Open')
    UNDER_REVIEW      = 'under_review',      _('Under Review')
    RESOLVED_APPROVED = 'resolved_approved', _('Resolved — Approved')
    RESOLVED_REJECTED = 'resolved_rejected', _('Resolved — Rejected')


class TransactionType(models.TextChoices):
    DEPOSIT        = 'deposit',        _('Deposit')
    WITHDRAWAL     = 'withdrawal',     _('Withdrawal')
    REWARD         = 'reward',         _('Task Reward')
    COMMISSION     = 'commission',     _('Admin Commission')
    REFERRAL       = 'referral',       _('Referral Commission')
    REFUND         = 'refund',         _('Refund')
    ESCROW_LOCK    = 'escrow_lock',    _('Escrow Lock')
    ESCROW_RELEASE = 'escrow_release', _('Escrow Release')
    BONUS          = 'bonus',          _('Bonus Payment')
    PENALTY        = 'penalty',        _('Fraud Penalty')


class EscrowStatus(models.TextChoices):
    LOCKED             = 'locked',             _('Locked')
    PARTIALLY_RELEASED = 'partially_released', _('Partially Released')
    FULLY_RELEASED     = 'fully_released',     _('Fully Released')
    REFUNDED           = 'refunded',           _('Refunded to Advertiser')


class FraudType(models.TextChoices):
    FAKE_SCREENSHOT  = 'fake_screenshot',      _('Fake Screenshot')
    VPN_DETECTED     = 'vpn_detected',         _('VPN / Proxy Detected')
    BOT_ACTIVITY     = 'bot_activity',         _('Bot / Automated Activity')
    DUPLICATE_SUBMIT = 'duplicate_submission', _('Duplicate Submission')
    ACCOUNT_FARMING  = 'account_farming',      _('Multiple Account Farming')
    EMULATOR         = 'emulator_detected',    _('Emulator Detected')
    CLICK_FRAUD      = 'click_fraud',          _('Click Fraud')


class FraudAction(models.TextChoices):
    FLAGGED = 'flagged', _('Flagged for Review')
    WARNED  = 'warned',  _('Warning Issued')
    BANNED  = 'banned',  _('Account Banned')
    IGNORED = 'ignored', _('Ignored / False Positive')


class BlacklistType(models.TextChoices):
    USER         = 'user',         _('User Account')
    IP           = 'ip',           _('IP Address')
    DEVICE       = 'device',       _('Device Fingerprint')
    CHANNEL_URL  = 'channel_url',  _('YouTube / Social Channel')
    EMAIL_DOMAIN = 'email_domain', _('Email Domain')
    PHONE        = 'phone',        _('Phone Number')


class BlacklistSeverity(models.TextChoices):
    WARN      = 'warn',      _('Warning Only')
    TEMP_BAN  = 'temp_ban',  _('Temporary Ban')
    PERMANENT = 'permanent', _('Permanent Ban')


class BonusConditionType(models.TextChoices):
    APPROVAL_RATE = 'approval_rate', _('Approval Rate')
    SPEED         = 'speed',         _('Completion Speed')
    STREAK        = 'streak',        _('Consecutive Approvals')


class RateSource(models.TextChoices):
    OPEN_EXCHANGE = 'open_exchange_rates', _('Open Exchange Rates')
    FIXER         = 'fixer',              _('Fixer.io')
    MANUAL        = 'manual',             _('Manual Entry')


class VerifiedBy(models.TextChoices):
    AI     = 'ai',     _('AI System')
    ADMIN  = 'admin',  _('Admin')
    SYSTEM = 'system', _('Auto System')


class VerificationDecision(models.TextChoices):
    APPROVE  = 'approve',  _('Approve')
    REJECT   = 'reject',   _('Reject')
    ESCALATE = 'escalate', _('Escalate to Human')


class CommissionStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending')
    PAID      = 'paid',      _('Paid')
    CANCELLED = 'cancelled', _('Cancelled')
