# api/referral/choices.py
# All TextChoices / IntegerChoices for referral module
# Use these in models, serializers, filters — single source of truth
# ============================================================

from django.db import models
from django.utils.translation import gettext_lazy as _


class ReferralStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending')
    QUALIFIED = 'qualified', _('Qualified')
    REWARDED  = 'rewarded',  _('Rewarded')
    REJECTED  = 'rejected',  _('Rejected')
    FRAUD     = 'fraud',     _('Fraud')


class CommissionStatus(models.TextChoices):
    PENDING    = 'pending',    _('Pending')
    HELD       = 'held',       _('Held')
    RELEASED   = 'released',   _('Released')
    CANCELLED  = 'cancelled',  _('Cancelled')
    CLAWED_BACK= 'clawed_back',_('Clawed Back')


class CommissionLevel(models.IntegerChoices):
    LEVEL_1 = 1, _('Level 1 (Direct)')
    LEVEL_2 = 2, _('Level 2 (Indirect)')
    LEVEL_3 = 3, _('Level 3 (Deep)')


class PayoutStatus(models.TextChoices):
    PENDING    = 'pending',    _('Pending')
    PROCESSING = 'processing', _('Processing')
    COMPLETED  = 'completed',  _('Completed')
    FAILED     = 'failed',     _('Failed')
    CANCELLED  = 'cancelled',  _('Cancelled')


class PayoutSchedule(models.TextChoices):
    DAILY   = 'daily',   _('Daily')
    WEEKLY  = 'weekly',  _('Weekly')
    MONTHLY = 'monthly', _('Monthly')
    MANUAL  = 'manual',  _('Manual Request')


class FraudStatus(models.TextChoices):
    PENDING   = 'pending',      _('Pending Review')
    REVIEWING = 'reviewing',    _('Under Review')
    CLEARED   = 'cleared',      _('Cleared')
    FRAUD     = 'fraud',        _('Confirmed Fraud')
    PARTIAL   = 'partial_fraud',_('Partial Fraud')


class FraudAction(models.TextChoices):
    FLAG             = 'flag',            _('Flag')
    BLOCK            = 'block',           _('Block')
    HOLD_COMMISSION  = 'hold_commission', _('Hold Commission')
    NOTIFY_ADMIN     = 'notify_admin',    _('Notify Admin')
    BAN_USER         = 'ban_user',        _('Ban User')


class CampaignStatus(models.TextChoices):
    DRAFT    = 'draft',    _('Draft')
    ACTIVE   = 'active',   _('Active')
    PAUSED   = 'paused',   _('Paused')
    ENDED    = 'ended',    _('Ended')
    ARCHIVED = 'archived', _('Archived')


class ContestStatus(models.TextChoices):
    UPCOMING  = 'upcoming',           _('Upcoming')
    ACTIVE    = 'active',             _('Active')
    ENDED     = 'ended',              _('Ended')
    PRIZES_DISTRIBUTED = 'prizes_distributed', _('Prizes Distributed')


class RewardType(models.TextChoices):
    CASH       = 'cash',      _('Cash')
    COINS      = 'coins',     _('Coins')
    CREDITS    = 'credits',   _('Credits')
    BADGE      = 'badge',     _('Badge')
    MULTIPLIER = 'multiplier',_('Rate Multiplier')
    GIFT_CARD  = 'gift_card', _('Gift Card')


class SourceType(models.TextChoices):
    TASK       = 'task',       _('Task Completion')
    OFFER      = 'offer',      _('Offer Completion')
    WITHDRAWAL = 'withdrawal', _('Withdrawal')
    DEPOSIT    = 'deposit',    _('Deposit')
    SIGNUP     = 'signup',     _('Signup Bonus')
    PROMOTION  = 'promotion',  _('Promotion')
    MANUAL     = 'manual',     _('Manual')


class ClawbackReason(models.TextChoices):
    FRAUD             = 'fraud',            _('Fraud')
    CHARGEBACK        = 'chargeback',       _('Chargeback')
    REFUND            = 'refund',           _('Refund')
    FAKE_ACTIVITY     = 'fake_activity',    _('Fake Activity')
    POLICY_VIOLATION  = 'policy_violation', _('Policy Violation')
    MANUAL            = 'manual',           _('Manual Clawback')


class CommissionRateType(models.TextChoices):
    PERCENTAGE = 'percentage', _('Percentage (%)')
    FIXED      = 'fixed',      _('Fixed Amount')


class Period(models.TextChoices):
    DAILY   = 'daily',   _('Daily')
    WEEKLY  = 'weekly',  _('Weekly')
    MONTHLY = 'monthly', _('Monthly')
    ALLTIME = 'alltime', _('All Time')


class ChurnRisk(models.TextChoices):
    LOW     = 'low',     _('Low Risk')
    MEDIUM  = 'medium',  _('Medium Risk')
    HIGH    = 'high',    _('High Risk')
    CHURNED = 'churned', _('Churned')


class ValueCategory(models.TextChoices):
    HIGH_VALUE = 'high_value', _('High Value')
    MID_VALUE  = 'mid_value',  _('Mid Value')
    LOW_VALUE  = 'low_value',  _('Low Value')
    INACTIVE   = 'inactive',   _('Inactive')


class AffiliateStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending Review')
    ACTIVE    = 'active',    _('Active')
    SUSPENDED = 'suspended', _('Suspended')
    REJECTED  = 'rejected',  _('Rejected')


class SocialPlatform(models.TextChoices):
    WHATSAPP  = 'whatsapp',  _('WhatsApp')
    TELEGRAM  = 'telegram',  _('Telegram')
    FACEBOOK  = 'facebook',  _('Facebook')
    TWITTER   = 'twitter',   _('Twitter/X')
    INSTAGRAM = 'instagram', _('Instagram')
    TIKTOK    = 'tiktok',    _('TikTok')
    LINKEDIN  = 'linkedin',  _('LinkedIn')
    SMS       = 'sms',       _('SMS')
    EMAIL     = 'email',     _('Email')
    COPY_LINK = 'copy_link', _('Copy Link')
    QR_CODE   = 'qr_code',   _('QR Code')
    OTHER     = 'other',     _('Other')


class TierLevel(models.TextChoices):
    BRONZE   = 'bronze',   _('🥉 Bronze')
    SILVER   = 'silver',   _('🥈 Silver')
    GOLD     = 'gold',     _('🥇 Gold')
    PLATINUM = 'platinum', _('💎 Platinum')
    CUSTOM   = 'custom',   _('Custom')


class NotificationChannel(models.TextChoices):
    IN_APP  = 'in_app',  _('In-App')
    PUSH    = 'push',    _('Push Notification')
    EMAIL   = 'email',   _('Email')
    SMS     = 'sms',     _('SMS')