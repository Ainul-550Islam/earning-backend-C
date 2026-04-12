# api/offer_inventory/enums.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class OfferStatus(models.TextChoices):
    ACTIVE   = 'active',   _('Active')
    PAUSED   = 'paused',   _('Paused')
    EXPIRED  = 'expired',  _('Expired')
    DRAFT    = 'draft',    _('Draft')
    REJECTED = 'rejected', _('Rejected')


class ConversionStatusEnum(models.TextChoices):
    PENDING    = 'pending',    _('Pending')
    APPROVED   = 'approved',   _('Approved')
    REJECTED   = 'rejected',   _('Rejected')
    REVERSED   = 'reversed',   _('Reversed')
    CHARGEBACK = 'chargeback', _('Chargeback')


class RewardType(models.TextChoices):
    COINS  = 'coins',  _('Coins')
    CASH   = 'cash',   _('Cash')
    POINTS = 'points', _('Points')
    BONUS  = 'bonus',  _('Bonus')


class PaymentProvider(models.TextChoices):
    BKASH  = 'bkash',  'bKash'
    NAGAD  = 'nagad',  'Nagad'
    ROCKET = 'rocket', 'Rocket'
    PAYPAL = 'paypal', 'PayPal'
    STRIPE = 'stripe', 'Stripe'
    BANK   = 'bank',   'Bank Transfer'
    CRYPTO = 'crypto', 'Crypto'


class WithdrawalStatus(models.TextChoices):
    PENDING    = 'pending',    _('Pending')
    APPROVED   = 'approved',   _('Approved')
    PROCESSING = 'processing', _('Processing')
    COMPLETED  = 'completed',  _('Completed')
    REJECTED   = 'rejected',   _('Rejected')
    CANCELLED  = 'cancelled',  _('Cancelled')


class FraudAction(models.TextChoices):
    FLAG    = 'flag',    _('Flag')
    BLOCK   = 'block',   _('Block')
    SUSPEND = 'suspend', _('Suspend')
    ALERT   = 'alert',   _('Alert')


class RiskLevel(models.TextChoices):
    LOW      = 'low',      _('Low')
    MEDIUM   = 'medium',   _('Medium')
    HIGH     = 'high',     _('High')
    CRITICAL = 'critical', _('Critical')


class DeviceType(models.TextChoices):
    MOBILE  = 'mobile',  _('Mobile')
    DESKTOP = 'desktop', _('Desktop')
    TABLET  = 'tablet',  _('Tablet')
    UNKNOWN = 'unknown', _('Unknown')


class CapType(models.TextChoices):
    DAILY   = 'daily',   _('Daily')
    WEEKLY  = 'weekly',  _('Weekly')
    MONTHLY = 'monthly', _('Monthly')
    TOTAL   = 'total',   _('Total')


class CampaignGoal(models.TextChoices):
    CPA = 'cpa', 'Cost Per Action'
    CPI = 'cpi', 'Cost Per Install'
    CPL = 'cpl', 'Cost Per Lead'
    CPC = 'cpc', 'Cost Per Click'
    CPM = 'cpm', 'Cost Per Mille'


class NotificationChannel(models.TextChoices):
    IN_APP = 'in_app', _('In-App')
    EMAIL  = 'email',  _('Email')
    PUSH   = 'push',   _('Push')
    SMS    = 'sms',    _('SMS')
