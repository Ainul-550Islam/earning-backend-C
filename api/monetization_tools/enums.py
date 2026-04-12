"""
api/monetization_tools/enums.py
================================
All Enum / TextChoices used across the monetization_tools app.
Centralised here so models, serializers, and views all import from one place.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Ad Campaign
# ---------------------------------------------------------------------------

class CampaignStatus(models.TextChoices):
    DRAFT    = 'draft',    _('Draft')
    ACTIVE   = 'active',   _('Active')
    PAUSED   = 'paused',   _('Paused')
    ENDED    = 'ended',    _('Ended')
    ARCHIVED = 'archived', _('Archived')


class PricingModel(models.TextChoices):
    CPM  = 'cpm',  _('CPM – Cost Per Mille')
    CPC  = 'cpc',  _('CPC – Cost Per Click')
    CPA  = 'cpa',  _('CPA – Cost Per Action')
    CPI  = 'cpi',  _('CPI – Cost Per Install')
    CPE  = 'cpe',  _('CPE – Cost Per Engagement')
    FLAT = 'flat', _('Flat Rate')


# ---------------------------------------------------------------------------
# Ad Unit / Format
# ---------------------------------------------------------------------------

class AdFormat(models.TextChoices):
    BANNER         = 'banner',         _('Banner')
    INTERSTITIAL   = 'interstitial',   _('Interstitial')
    REWARDED_VIDEO = 'rewarded_video', _('Rewarded Video')
    NATIVE         = 'native',         _('Native Ad')
    PLAYABLE       = 'playable',       _('Playable Ad')
    CAROUSEL       = 'carousel',       _('Carousel')
    AUDIO          = 'audio',          _('Audio Ad')
    OFFERWALL      = 'offerwall',      _('Offerwall')


# ---------------------------------------------------------------------------
# Ad Network
# ---------------------------------------------------------------------------

class AdNetworkType(models.TextChoices):
    ADMOB       = 'admob',       _('Google AdMob')
    FACEBOOK    = 'facebook',    _('Facebook Audience Network')
    APPLOVIN    = 'applovin',    _('AppLovin MAX')
    IRONSOURCE  = 'ironsource',  _('IronSource')
    UNITY       = 'unity',       _('Unity Ads')
    VUNGLE      = 'vungle',      _('Vungle')
    CHARTBOOST  = 'chartboost',  _('Chartboost')
    TAPJOY      = 'tapjoy',      _('Tapjoy')
    FYBER       = 'fyber',       _('Fyber')
    MINTEGRAL   = 'mintegral',   _('Mintegral')
    PANGLE      = 'pangle',      _('Pangle (TikTok)')
    INMOBI      = 'inmobi',      _('InMobi')
    ADCOLONY    = 'adcolony',    _('AdColony')
    CUSTOM      = 'custom',      _('Custom Network')


# ---------------------------------------------------------------------------
# Ad Placement
# ---------------------------------------------------------------------------

class PlacementPosition(models.TextChoices):
    TOP          = 'top',          _('Top')
    BOTTOM       = 'bottom',       _('Bottom')
    MID_CONTENT  = 'mid_content',  _('Mid-Content')
    FULLSCREEN   = 'fullscreen',   _('Fullscreen / Interstitial')
    SIDEBAR      = 'sidebar',      _('Sidebar')
    AFTER_ACTION = 'after_action', _('After User Action')
    ON_EXIT      = 'on_exit',      _('On Exit Intent')


# ---------------------------------------------------------------------------
# Offerwall / Offer
# ---------------------------------------------------------------------------

class OfferType(models.TextChoices):
    APP_INSTALL  = 'app_install',  _('App Install')
    SURVEY       = 'survey',       _('Survey')
    QUIZ         = 'quiz',         _('Quiz')
    VIDEO        = 'video',        _('Video Ad')
    TRIAL        = 'trial',        _('Free Trial')
    SUBSCRIPTION = 'subscription', _('Subscription')
    PURCHASE     = 'purchase',     _('Purchase')
    SOCIAL       = 'social',       _('Social Action')
    OTHER        = 'other',        _('Other')


class OfferStatus(models.TextChoices):
    ACTIVE  = 'active',  _('Active')
    PAUSED  = 'paused',  _('Paused')
    EXPIRED = 'expired', _('Expired')
    PENDING = 'pending', _('Pending Approval')


class OfferCompletionStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending')
    APPROVED  = 'approved',  _('Approved')
    REJECTED  = 'rejected',  _('Rejected')
    CANCELLED = 'cancelled', _('Cancelled')
    FRAUD     = 'fraud',     _('Fraud Detected')


# ---------------------------------------------------------------------------
# Reward Transaction
# ---------------------------------------------------------------------------

class RewardTransactionType(models.TextChoices):
    OFFER_REWARD   = 'offer_reward',   _('Offer Reward')
    REFERRAL_BONUS = 'referral_bonus', _('Referral Bonus')
    STREAK_REWARD  = 'streak_reward',  _('Daily Streak Reward')
    SPIN_WHEEL     = 'spin_wheel',     _('Spin Wheel Win')
    SCRATCH_CARD   = 'scratch_card',   _('Scratch Card Win')
    ACHIEVEMENT    = 'achievement',    _('Achievement Bonus')
    ADMIN_GRANT    = 'admin_grant',    _('Admin Manual Grant')
    ADMIN_DEDUCT   = 'admin_deduct',   _('Admin Manual Deduction')
    WITHDRAWAL     = 'withdrawal',     _('Withdrawal')
    EXPIRY_DEDUCT  = 'expiry_deduct',  _('Points Expiry')


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

class SubscriptionInterval(models.TextChoices):
    DAILY    = 'daily',    _('Daily')
    WEEKLY   = 'weekly',   _('Weekly')
    MONTHLY  = 'monthly',  _('Monthly')
    YEARLY   = 'yearly',   _('Yearly')
    LIFETIME = 'lifetime', _('Lifetime')


class SubscriptionStatus(models.TextChoices):
    TRIAL     = 'trial',     _('Trial')
    ACTIVE    = 'active',    _('Active')
    PAST_DUE  = 'past_due',  _('Past Due')
    CANCELLED = 'cancelled', _('Cancelled')
    EXPIRED   = 'expired',   _('Expired')


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class PaymentGateway(models.TextChoices):
    STRIPE     = 'stripe',     _('Stripe')
    PAYPAL     = 'paypal',     _('PayPal')
    BKASH      = 'bkash',      _('bKash')
    NAGAD      = 'nagad',      _('Nagad')
    ROCKET     = 'rocket',     _('Rocket')
    SSLCOMMERZ = 'sslcommerz', _('SSLCommerz')
    RAZORPAY   = 'razorpay',   _('Razorpay')
    PAYONEER   = 'payoneer',   _('Payoneer')
    CRYPTO     = 'crypto',     _('Crypto')
    MANUAL     = 'manual',     _('Manual / Bank Transfer')


class PaymentStatus(models.TextChoices):
    INITIATED = 'initiated', _('Initiated')
    PENDING   = 'pending',   _('Pending')
    SUCCESS   = 'success',   _('Success')
    FAILED    = 'failed',    _('Failed')
    CANCELLED = 'cancelled', _('Cancelled')
    REFUNDED  = 'refunded',  _('Refunded')
    DISPUTED  = 'disputed',  _('Disputed')


class PaymentPurpose(models.TextChoices):
    SUBSCRIPTION = 'subscription', _('Subscription')
    IN_APP       = 'in_app',       _('In-App Purchase')
    DEPOSIT      = 'deposit',      _('Deposit')
    WITHDRAWAL   = 'withdrawal',   _('Withdrawal')
    OTHER        = 'other',        _('Other')


# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

class AchievementCategory(models.TextChoices):
    EARNING  = 'earning',  _('Earning')
    REFERRAL = 'referral', _('Referral')
    STREAK   = 'streak',   _('Streak')
    OFFER    = 'offer',    _('Offer Completion')
    SOCIAL   = 'social',   _('Social')
    SPECIAL  = 'special',  _('Special Event')


class LeaderboardScope(models.TextChoices):
    GLOBAL  = 'global',  _('Global')
    COUNTRY = 'country', _('Country')
    WEEKLY  = 'weekly',  _('Weekly')
    MONTHLY = 'monthly', _('Monthly')


class LeaderboardType(models.TextChoices):
    EARNINGS  = 'earnings',  _('Total Earnings')
    REFERRALS = 'referrals', _('Referrals')
    OFFERS    = 'offers',    _('Offers Completed')
    STREAK    = 'streak',    _('Longest Streak')


class SpinWheelType(models.TextChoices):
    SPIN_WHEEL   = 'spin_wheel',   _('Spin Wheel')
    SCRATCH_CARD = 'scratch_card', _('Scratch Card')


class PrizeType(models.TextChoices):
    COINS      = 'coins',      _('Coins')
    XP         = 'xp',         _('XP Points')
    NO_PRIZE   = 'no_prize',   _('No Prize')
    MULTIPLIER = 'multiplier', _('Earning Multiplier')
    VOUCHER    = 'voucher',    _('Voucher Code')


# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------

class ABTestStatus(models.TextChoices):
    DRAFT     = 'draft',     _('Draft')
    RUNNING   = 'running',   _('Running')
    PAUSED    = 'paused',    _('Paused')
    COMPLETED = 'completed', _('Completed')
    ARCHIVED  = 'archived',  _('Archived')


class WinnerCriteria(models.TextChoices):
    CTR     = 'ctr',     _('Click-Through Rate')
    CVR     = 'cvr',     _('Conversion Rate')
    REVENUE = 'revenue', _('Revenue')
    ECPM    = 'ecpm',    _('eCPM')


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

class ConversionType(models.TextChoices):
    INSTALL      = 'install',      _('App Install')
    SIGNUP       = 'signup',       _('Sign Up')
    PURCHASE     = 'purchase',     _('Purchase')
    LEAD         = 'lead',         _('Lead')
    ENGAGEMENT   = 'engagement',   _('Engagement')
    SUBSCRIPTION = 'subscription', _('Subscription')


# ---------------------------------------------------------------------------
# Recurring Billing
# ---------------------------------------------------------------------------

class BillingStatus(models.TextChoices):
    SCHEDULED  = 'scheduled',  _('Scheduled')
    PROCESSING = 'processing', _('Processing')
    SUCCESS    = 'success',    _('Success')
    FAILED     = 'failed',     _('Failed')
    SKIPPED    = 'skipped',    _('Skipped')


# ---------------------------------------------------------------------------
# Payout
# ---------------------------------------------------------------------------

class PayoutMethodType(models.TextChoices):
    BKASH     = 'bkash',     _('bKash')
    NAGAD     = 'nagad',     _('Nagad')
    ROCKET    = 'rocket',    _('Rocket')
    UPAY      = 'upay',      _('Upay')
    BANK      = 'bank',      _('Bank Transfer')
    PAYPAL    = 'paypal',    _('PayPal')
    PAYONEER  = 'payoneer',  _('Payoneer')
    CRYPTO    = 'crypto',    _('Cryptocurrency')
    GIFT_CARD = 'gift_card', _('Gift Card')


class PayoutRequestStatus(models.TextChoices):
    PENDING    = 'pending',    _('Pending Review')
    APPROVED   = 'approved',   _('Approved')
    PROCESSING = 'processing', _('Processing Payment')
    PAID       = 'paid',       _('Paid')
    REJECTED   = 'rejected',   _('Rejected')
    CANCELLED  = 'cancelled',  _('Cancelled by User')
    FAILED     = 'failed',     _('Payment Failed')


# ---------------------------------------------------------------------------
# Referral
# ---------------------------------------------------------------------------

class ReferralCommissionType(models.TextChoices):
    SIGNUP       = 'signup',       _('Signup Bonus')
    OFFER_EARN   = 'offer_earn',   _('Offer Earning Commission')
    PURCHASE     = 'purchase',     _('Purchase Commission')
    SUBSCRIPTION = 'subscription', _('Subscription Commission')
    MILESTONE    = 'milestone',    _('Milestone Bonus')


# ---------------------------------------------------------------------------
# Fraud
# ---------------------------------------------------------------------------

class FraudAlertType(models.TextChoices):
    HIGH_FRAUD_SCORE   = 'high_fraud_score',   _('High Fraud Score')
    DUPLICATE_DEVICE   = 'duplicate_device',   _('Duplicate Device')
    VPN_PROXY          = 'vpn_proxy',          _('VPN/Proxy')
    VELOCITY_BREACH    = 'velocity_breach',    _('Velocity Breach')
    IP_BLACKLIST       = 'ip_blacklist',       _('Blacklisted IP')
    UNUSUAL_PATTERN    = 'unusual_pattern',    _('Unusual Pattern')
    MULTIPLE_ACCOUNTS  = 'multiple_accounts',  _('Multiple Accounts')
    POSTBACK_MISMATCH  = 'postback_mismatch',  _('Postback Mismatch')


class FraudSeverity(models.TextChoices):
    LOW      = 'low',      _('Low')
    MEDIUM   = 'medium',   _('Medium')
    HIGH     = 'high',     _('High')
    CRITICAL = 'critical', _('Critical')


class FraudResolution(models.TextChoices):
    OPEN          = 'open',          _('Open')
    REVIEWING     = 'reviewing',     _('Under Review')
    CLEARED       = 'cleared',       _('Cleared — False Positive')
    CONFIRMED     = 'confirmed',     _('Confirmed — Action Taken')
    AUTO_RESOLVED = 'auto_resolved', _('Auto-Resolved')


# ---------------------------------------------------------------------------
# Revenue Goal
# ---------------------------------------------------------------------------

class RevenueGoalPeriod(models.TextChoices):
    DAILY     = 'daily',     _('Daily')
    WEEKLY    = 'weekly',    _('Weekly')
    MONTHLY   = 'monthly',   _('Monthly')
    QUARTERLY = 'quarterly', _('Quarterly')
    YEARLY    = 'yearly',    _('Yearly')


class RevenueGoalType(models.TextChoices):
    TOTAL_REVENUE = 'total_revenue', _('Total Revenue')
    AD_REVENUE    = 'ad_revenue',    _('Ad Network Revenue')
    OFFER_REVENUE = 'offer_revenue', _('Offerwall Revenue')
    SUBSCRIPTIONS = 'subscriptions', _('Subscription Revenue')
    NEW_USERS     = 'new_users',     _('New User Registrations')
    ACTIVE_USERS  = 'active_users',  _('Daily Active Users')


# ---------------------------------------------------------------------------
# Publisher Account
# ---------------------------------------------------------------------------

class PublisherAccountType(models.TextChoices):
    ADVERTISER = 'advertiser', _('Advertiser')
    PUBLISHER  = 'publisher',  _('Publisher')
    AGENCY     = 'agency',     _('Agency')
    NETWORK    = 'network',    _('Network Partner')


class PublisherStatus(models.TextChoices):
    PENDING   = 'pending',   _('Pending Approval')
    ACTIVE    = 'active',    _('Active')
    SUSPENDED = 'suspended', _('Suspended')
    BANNED    = 'banned',    _('Banned')
    CLOSED    = 'closed',    _('Closed')


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class NotificationEventType(models.TextChoices):
    OFFER_APPROVED      = 'offer_approved',      _('Offer Approved')
    OFFER_REJECTED      = 'offer_rejected',      _('Offer Rejected')
    REWARD_CREDITED     = 'reward_credited',     _('Reward Credited')
    WITHDRAWAL_APPROVED = 'withdrawal_approved', _('Withdrawal Approved')
    WITHDRAWAL_REJECTED = 'withdrawal_rejected', _('Withdrawal Rejected')
    SUBSCRIPTION_START  = 'subscription_start',  _('Subscription Started')
    SUBSCRIPTION_EXPIRE = 'subscription_expire', _('Subscription Expiring')
    REFERRAL_JOINED     = 'referral_joined',     _('Referral Joined')
    REFERRAL_EARNED     = 'referral_earned',     _('Referral Commission Earned')
    LEVEL_UP            = 'level_up',            _('Level Up')
    STREAK_MILESTONE    = 'streak_milestone',    _('Streak Milestone')
    FLASH_SALE_START    = 'flash_sale_start',    _('Flash Sale Started')
    FRAUD_ALERT         = 'fraud_alert',         _('Fraud Alert')
    COUPON_EXPIRY       = 'coupon_expiry',       _('Coupon Expiring Soon')
    GOAL_ACHIEVED       = 'goal_achieved',       _('Revenue Goal Achieved')
    PAYOUT_PAID         = 'payout_paid',         _('Payout Paid')
    PAYOUT_REJECTED     = 'payout_rejected',     _('Payout Rejected')


class NotificationChannel(models.TextChoices):
    IN_APP = 'in_app', _('In-App')
    EMAIL  = 'email',  _('Email')
    SMS    = 'sms',    _('SMS')
    PUSH   = 'push',   _('Push Notification')


# ---------------------------------------------------------------------------
# Postback
# ---------------------------------------------------------------------------

class PostbackStatus(models.TextChoices):
    RECEIVED   = 'received',   _('Received')
    PROCESSING = 'processing', _('Processing')
    ACCEPTED   = 'accepted',   _('Accepted')
    REJECTED   = 'rejected',   _('Rejected')
    DUPLICATE  = 'duplicate',  _('Duplicate')
    FRAUD      = 'fraud',      _('Fraud Detected')
    ERROR      = 'error',      _('Processing Error')


# ---------------------------------------------------------------------------
# Ad Creative
# ---------------------------------------------------------------------------

class CreativeType(models.TextChoices):
    IMAGE  = 'image',  _('Image')
    VIDEO  = 'video',  _('Video')
    HTML5  = 'html5',  _('HTML5')
    AUDIO  = 'audio',  _('Audio')
    VAST   = 'vast',   _('VAST Tag')
    MRAID  = 'mraid',  _('MRAID')
    NATIVE = 'native', _('Native Bundle')


class CreativeStatus(models.TextChoices):
    DRAFT    = 'draft',    _('Draft')
    PENDING  = 'pending',  _('Pending Review')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')
    ARCHIVED = 'archived', _('Archived')


# ---------------------------------------------------------------------------
# Segment
# ---------------------------------------------------------------------------

class SegmentType(models.TextChoices):
    MANUAL     = 'manual',     _('Manual')
    RFM        = 'rfm',        _('RFM')
    BEHAVIORAL = 'behavioral', _('Behavioral')
    GEO        = 'geo',        _('Geographic')
    DEVICE     = 'device',     _('Device/Platform')
    CUSTOM_SQL = 'custom_sql', _('Custom SQL')


# ---------------------------------------------------------------------------
# Flash Sale
# ---------------------------------------------------------------------------

class FlashSaleType(models.TextChoices):
    OFFER_BOOST   = 'offer_boost',   _('Offer Reward Multiplier')
    COIN_BONUS    = 'coin_bonus',    _('Bonus Coin Grant')
    SUBSCRIPTION  = 'subscription',  _('Subscription Discount')
    DOUBLE_POINTS = 'double_points', _('Double Points Event')
    FREE_SPIN     = 'free_spin',     _('Extra Free Spins')
