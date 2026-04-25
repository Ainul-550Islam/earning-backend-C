"""
Tenant Choices - Comprehensive Configuration Options

This module contains all choice fields and configuration options
for the tenant management system with comprehensive categorization.
"""

from django.utils.translation import gettext_lazy as _
from enum import Enum
from typing import List, Tuple, Dict, Any


class BaseChoiceEnum(Enum):
    """Base enum class for choice fields."""
    
    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """Return choices as list of tuples."""
        return [(member.value, member.name.replace('_', ' ').title()) for member in cls]
    
    @classmethod
    def values(cls) -> List[str]:
        """Return all values as list."""
        return [member.value for member in cls]
    
    @classmethod
    def get_label(cls, value: str) -> str:
        """Get label for a given value."""
        for member in cls:
            if member.value == value:
                return member.name.replace('_', ' ').title()
        return value.title()


class TenantPlanChoices(BaseChoiceEnum):
    """Tenant subscription plan choices."""
    
    BASIC = 'basic'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'
    CUSTOM = 'custom'
    
    @classmethod
    def get_plan_limits(cls, plan: str) -> Dict[str, Any]:
        """Get limits and features for a plan."""
        plans_config = {
            cls.BASIC.value: {
                'max_users': 100,
                'max_storage_gb': 10,
                'features': ['referral', 'offerwall'],
                'api_rate_limit': '1000/hour',
                'support_level': 'basic',
                'custom_domains': False,
                'white_label': False,
                'advanced_analytics': False,
            },
            cls.PRO.value: {
                'max_users': 500,
                'max_storage_gb': 50,
                'features': ['referral', 'offerwall', 'kyc', 'leaderboard'],
                'api_rate_limit': '5000/hour',
                'support_level': 'priority',
                'custom_domains': True,
                'white_label': False,
                'advanced_analytics': True,
            },
            cls.ENTERPRISE.value: {
                'max_users': 10000,
                'max_storage_gb': 500,
                'features': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics'],
                'api_rate_limit': 'unlimited',
                'support_level': 'dedicated',
                'custom_domains': True,
                'white_label': True,
                'advanced_analytics': True,
            },
            cls.CUSTOM.value: {
                'max_users': 0,  # Unlimited
                'max_storage_gb': 0,  # Unlimited
                'features': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics', 'api_access'],
                'api_rate_limit': 'unlimited',
                'support_level': 'enterprise',
                'custom_domains': True,
                'white_label': True,
                'advanced_analytics': True,
            },
        }
        return plans_config.get(plan, {})


class TenantStatusChoices(BaseChoiceEnum):
    """Tenant status choices."""
    
    TRIAL = 'trial'
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'
    PAST_DUE = 'past_due'
    
    @classmethod
    def get_status_color(cls, status: str) -> str:
        """Get color code for status."""
        colors = {
            cls.TRIAL.value: 'blue',
            cls.ACTIVE.value: 'green',
            cls.SUSPENDED.value: 'orange',
            cls.EXPIRED.value: 'red',
            cls.CANCELLED.value: 'gray',
            cls.PAST_DUE.value: 'red',
        }
        return colors.get(status, 'black')
    
    @classmethod
    def is_active_status(cls, status: str) -> bool:
        """Check if status is considered active."""
        active_statuses = [cls.TRIAL.value, cls.ACTIVE.value]
        return status in active_statuses


class BillingStatusChoices(BaseChoiceEnum):
    """Billing status choices."""
    
    TRIAL = 'trial'
    ACTIVE = 'active'
    PAST_DUE = 'past_due'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'
    UNPAID = 'unpaid'
    
    @classmethod
    def requires_payment(cls, status: str) -> bool:
        """Check if status requires payment processing."""
        payment_required = [cls.ACTIVE.value, cls.PAST_DUE.value, cls.UNPAID.value]
        return status in payment_required


class BillingCycleChoices(BaseChoiceEnum):
    """Billing cycle choices."""
    
    MONTHLY = 'monthly'
    QUARTERLY = 'quarterly'
    YEARLY = 'yearly'
    CUSTOM = 'custom'
    
    @classmethod
    def get_cycle_days(cls, cycle: str) -> int:
        """Get number of days for billing cycle."""
        days = {
            cls.MONTHLY.value: 30,
            cls.QUARTERLY.value: 90,
            cls.YEARLY.value: 365,
            cls.CUSTOM.value: 30,  # Default to monthly for custom
        }
        return days.get(cycle, 30)
    
    @classmethod
    def get_cycle_multiplier(cls, cycle: str) -> float:
        """Get multiplier for pricing (relative to monthly)."""
        multipliers = {
            cls.MONTHLY.value: 1.0,
            cls.QUARTERLY.value: 3.0,
            cls.YEARLY.value: 12.0,
            cls.CUSTOM.value: 1.0,
        }
        return multipliers.get(cycle, 1.0)


class InvoiceStatusChoices(BaseChoiceEnum):
    """Invoice status choices."""
    
    DRAFT = 'draft'
    SENT = 'sent'
    PAID = 'paid'
    PARTIALLY_PAID = 'partially_paid'
    OVERDUE = 'overdue'
    CANCELLED = 'cancelled'
    REFUNDED = 'refunded'
    
    @classmethod
    def is_paid_status(cls, status: str) -> bool:
        """Check if invoice is paid."""
        paid_statuses = [cls.PAID.value, cls.PARTIALLY_PAID.value]
        return status in paid_statuses
    
    @classmethod
    def can_be_paid(cls, status: str) -> bool:
        """Check if invoice can be marked as paid."""
        payable_statuses = [cls.DRAFT.value, cls.SENT.value, cls.PARTIALLY_PAID.value, cls.OVERDUE.value]
        return status in payable_statuses


class AuditActionChoices(BaseChoiceEnum):
    """Audit log action choices."""
    
    CREATED = 'created'
    UPDATED = 'updated'
    DELETED = 'deleted'
    SUSPENDED = 'suspended'
    ACTIVATED = 'activated'
    BILLING_UPDATED = 'billing_updated'
    SETTINGS_UPDATED = 'settings_updated'
    USER_ADDED = 'user_added'
    USER_REMOVED = 'user_removed'
    API_KEY_REGENERATED = 'api_key_regenerated'
    FEATURE_ENABLED = 'feature_enabled'
    FEATURE_DISABLED = 'feature_disabled'
    PAYMENT_PROCESSED = 'payment_processed'
    INVOICE_GENERATED = 'invoice_generated'
    LOGIN_ATTEMPT = 'login_attempt'
    PERMISSION_GRANTED = 'permission_granted'
    PERMISSION_REVOKED = 'permission_revoked'
    FILE_UPLOADED = 'file_uploaded'
    FILE_DELETED = 'file_deleted'
    WEBHOOK_RECEIVED = 'webhook_received'
    PUBLIC_ACCESS = 'public_access'
    PUBLIC_API_ACCESS = 'public_api_access'
    SECURITY_LOGIN_ATTEMPT = 'security_login_attempt'
    SECURITY_FILE_UPLOADED = 'security_file_uploaded'
    SECURITY_RATE_LIMIT_EXCEEDED = 'security_rate_limit_exceeded'
    
    @classmethod
    def get_security_actions(cls) -> List[str]:
        """Get all security-related actions."""
        return [
            cls.LOGIN_ATTEMPT.value,
            cls.SECURITY_LOGIN_ATTEMPT.value,
            cls.SECURITY_FILE_UPLOADED.value,
            cls.SECURITY_RATE_LIMIT_EXCEEDED.value,
        ]
    
    @classmethod
    def get_billing_actions(cls) -> List[str]:
        """Get all billing-related actions."""
        return [
            cls.BILLING_UPDATED.value,
            cls.PAYMENT_PROCESSED.value,
            cls.INVOICE_GENERATED.value,
        ]
    
    @classmethod
    def get_user_management_actions(cls) -> List[str]:
        """Get all user management actions."""
        return [
            cls.USER_ADDED.value,
            cls.USER_REMOVED.value,
            cls.PERMISSION_GRANTED.value,
            cls.PERMISSION_REVOKED.value,
        ]


class ReferralBonusTypeChoices(BaseChoiceEnum):
    """Referral bonus type choices."""
    
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'
    
    @classmethod
    def get_bonus_label(cls, bonus_type: str) -> str:
        """Get formatted label for bonus type."""
        labels = {
            cls.FIXED.value: _('Fixed Amount'),
            cls.PERCENTAGE.value: _('Percentage'),
        }
        return labels.get(bonus_type, bonus_type.title())


class LogLevelChoices(BaseChoiceEnum):
    """Log level choices."""
    
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    
    @classmethod
    def get_level_priority(cls, level: str) -> int:
        """Get priority level for logging."""
        priorities = {
            cls.DEBUG.value: 10,
            cls.INFO.value: 20,
            cls.WARNING.value: 30,
            cls.ERROR.value: 40,
            cls.CRITICAL.value: 50,
        }
        return priorities.get(level, 20)


class DataRegionChoices(BaseChoiceEnum):
    """Data storage region choices."""
    
    US_EAST_1 = 'us-east-1'
    US_WEST_2 = 'us-west-2'
    EU_WEST_1 = 'eu-west-1'
    EU_CENTRAL_1 = 'eu-central-1'
    AP_SOUTHEAST_1 = 'ap-southeast-1'
    AP_NORTHEAST_1 = 'ap-northeast-1'
    
    @classmethod
    def get_region_display(cls, region: str) -> str:
        """Get display name for region."""
        displays = {
            cls.US_EAST_1.value: _('US East (N. Virginia)'),
            cls.US_WEST_2.value: _('US West (Oregon)'),
            cls.EU_WEST_1.value: _('EU West (Ireland)'),
            cls.EU_CENTRAL_1.value: _('EU Central (Frankfurt)'),
            cls.AP_SOUTHEAST_1.value: _('AP Southeast (Singapore)'),
            cls.AP_NORTHEAST_1.value: _('AP Northeast (Tokyo)'),
        }
        return displays.get(region, region)


class CurrencyChoices(BaseChoiceEnum):
    """Currency choices."""
    
    USD = 'USD'
    EUR = 'EUR'
    GBP = 'GBP'
    JPY = 'JPY'
    CAD = 'CAD'
    AUD = 'AUD'
    CHF = 'CHF'
    CNY = 'CNY'
    INR = 'INR'
    BRL = 'BRL'
    
    @classmethod
    def get_currency_symbol(cls, currency: str) -> str:
        """Get currency symbol."""
        symbols = {
            cls.USD.value: '$',
            cls.EUR.value: 'â',
            cls.GBP.value: 'Â£',
            cls.JPY.value: 'Â¥',
            cls.CAD.value: 'C$',
            cls.AUD.value: 'A$',
            cls.CHF.value: 'CHF',
            cls.CNY.value: 'Â¥',
            cls.INR.value: 'â¹',
            cls.BRL.value: 'R$',
        }
        return symbols.get(currency, currency)
    
    @classmethod
    def get_currency_name(cls, currency: str) -> str:
        """Get currency name."""
        names = {
            cls.USD.value: _('US Dollar'),
            cls.EUR.value: _('Euro'),
            cls.GBP.value: _('British Pound'),
            cls.JPY.value: _('Japanese Yen'),
            cls.CAD.value: _('Canadian Dollar'),
            cls.AUD.value: _('Australian Dollar'),
            cls.CHF.value: _('Swiss Franc'),
            cls.CNY.value: _('Chinese Yuan'),
            cls.INR.value: _('Indian Rupee'),
            cls.BRL.value: _('Brazilian Real'),
        }
        return names.get(currency, currency)


class CountryCodeChoices(BaseChoiceEnum):
    """Country code choices (ISO 3166-1 alpha-2)."""
    
    US = 'US'
    GB = 'GB'
    CA = 'CA'
    AU = 'AU'
    DE = 'DE'
    FR = 'FR'
    IT = 'IT'
    ES = 'ES'
    NL = 'NL'
    JP = 'JP'
    CN = 'CN'
    IN = 'IN'
    BR = 'BR'
    MX = 'MX'
    KR = 'KR'
    
    @classmethod
    def get_country_name(cls, code: str) -> str:
        """Get country name from code."""
        names = {
            cls.US.value: _('United States'),
            cls.GB.value: _('United Kingdom'),
            cls.CA.value: _('Canada'),
            cls.AU.value: _('Australia'),
            cls.DE.value: _('Germany'),
            cls.FR.value: _('France'),
            cls.IT.value: _('Italy'),
            cls.ES.value: _('Spain'),
            cls.NL.value: _('Netherlands'),
            cls.JP.value: _('Japan'),
            cls.CN.value: _('China'),
            cls.IN.value: _('India'),
            cls.BR.value: _('Brazil'),
            cls.MX.value: _('Mexico'),
            cls.KR.value: _('South Korea'),
        }
        return names.get(code, code)


class TimezoneChoices(BaseChoiceEnum):
    """Timezone choices."""
    
    UTC = 'UTC'
    EST = 'EST'
    CST = 'CST'
    MST = 'MST'
    PST = 'PST'
    CET = 'CET'
    EET = 'EET'
    JST = 'JST'
    AEST = 'AEST'
    IST = 'IST'
    BRT = 'BRT'
    KST = 'KST'
    
    @classmethod
    def get_timezone_offset(cls, timezone: str) -> str:
        """Get UTC offset for timezone."""
        offsets = {
            cls.UTC.value: '+00:00',
            cls.EST.value: '-05:00',
            cls.CST.value: '-06:00',
            cls.MST.value: '-07:00',
            cls.PST.value: '-08:00',
            cls.CET.value: '+01:00',
            cls.EET.value: '+02:00',
            cls.JST.value: '+09:00',
            cls.AEST.value: '+10:00',
            cls.IST.value: '+05:30',
            cls.BRT.value: '-03:00',
            cls.KST.value: '+09:00',
        }
        return offsets.get(timezone, '+00:00')


class PaymentMethodChoices(BaseChoiceEnum):
    """Payment method choices."""
    
    STRIPE = 'stripe'
    PAYPAL = 'paypal'
    BANK_TRANSFER = 'bank_transfer'
    CREDIT_CARD = 'credit_card'
    CRYPTO = 'crypto'
    CHECK = 'check'
    
    @classmethod
    def get_method_display(cls, method: str) -> str:
        """Get display name for payment method."""
        displays = {
            cls.STRIPE.value: _('Stripe'),
            cls.PAYPAL.value: _('PayPal'),
            cls.BANK_TRANSFER.value: _('Bank Transfer'),
            cls.CREDIT_CARD.value: _('Credit Card'),
            cls.CRYPTO.value: _('Cryptocurrency'),
            cls.CHECK.value: _('Check'),
        }
        return displays.get(method, method.title())


class NotificationChannelChoices(BaseChoiceEnum):
    """Notification channel choices."""
    
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    WEBHOOK = 'webhook'
    IN_APP = 'in_app'
    
    @classmethod
    def get_channel_display(cls, channel: str) -> str:
        """Get display name for notification channel."""
        displays = {
            cls.EMAIL.value: _('Email'),
            cls.SMS.value: _('SMS'),
            cls.PUSH.value: _('Push Notification'),
            cls.WEBHOOK.value: _('Webhook'),
            cls.IN_APP.value: _('In-App Notification'),
        }
        return displays.get(channel, channel.title())


class SupportLevelChoices(BaseChoiceEnum):
    """Support level choices."""
    
    BASIC = 'basic'
    PRIORITY = 'priority'
    DEDICATED = 'dedicated'
    ENTERPRISE = 'enterprise'
    
    @classmethod
    def get_support_features(cls, level: str) -> List[str]:
        """Get features available for support level."""
        features = {
            cls.BASIC.value: [
                _('Email support'),
                _('Knowledge base'),
                _('Community forum'),
            ],
            cls.PRIORITY.value: [
                _('Priority email support'),
                _('Knowledge base'),
                _('Community forum'),
                _('Live chat (business hours)'),
            ],
            cls.DEDICATED.value: [
                _('Dedicated account manager'),
                _('24/7 phone support'),
                _('Priority email support'),
                _('Knowledge base'),
                _('Community forum'),
                _('Live chat (24/7)'),
                _('Custom training'),
            ],
            cls.ENTERPRISE.value: [
                _('Enterprise account manager'),
                _('24/7 phone support'),
                _('Priority email support'),
                _('Knowledge base'),
                _('Community forum'),
                _('Live chat (24/7)'),
                _('Custom training'),
                _('On-site support'),
                _('Custom SLA'),
            ],
        }
        return features.get(level, [])


class FeatureFlagChoices(BaseChoiceEnum):
    """Feature flag choices."""
    
    ENABLE_REFERRAL = 'enable_referral'
    ENABLE_OFFERWALL = 'enable_offerwall'
    ENABLE_KYC = 'enable_kyc'
    ENABLE_LEADERBOARD = 'enable_leaderboard'
    ENABLE_CHAT = 'enable_chat'
    ENABLE_PUSH_NOTIFICATIONS = 'enable_push_notifications'
    ENABLE_ANALYTICS = 'enable_analytics'
    ENABLE_API_ACCESS = 'enable_api_access'
    ENABLE_WHITE_LABEL = 'enable_white_label'
    ENABLE_CUSTOM_DOMAINS = 'enable_custom_domains'
    ENABLE_ADVANCED_ANALYTICS = 'enable_advanced_analytics'
    ENABLE_MULTI_LANGUAGE = 'enable_multi_language'
    ENABLE_SSO = 'enable_sso'
    ENABLE_TWO_FACTOR_AUTH = 'enable_two_factor_auth'
    
    @classmethod
    def get_feature_description(cls, feature: str) -> str:
        """Get description for feature flag."""
        descriptions = {
            cls.ENABLE_REFERRAL.value: _('Enable referral system'),
            cls.ENABLE_OFFERWALL.value: _('Enable offerwall integration'),
            cls.ENABLE_KYC.value: _('Enable KYC verification'),
            cls.ENABLE_LEADERBOARD.value: _('Enable leaderboard system'),
            cls.ENABLE_CHAT.value: _('Enable chat functionality'),
            cls.ENABLE_PUSH_NOTIFICATIONS.value: _('Enable push notifications'),
            cls.ENABLE_ANALYTICS.value: _('Enable analytics dashboard'),
            cls.ENABLE_API_ACCESS.value: _('Enable API access'),
            cls.ENABLE_WHITE_LABEL.value: _('Enable white-label options'),
            cls.ENABLE_CUSTOM_DOMAINS.value: _('Enable custom domains'),
            cls.ENABLE_ADVANCED_ANALYTICS.value: _('Enable advanced analytics'),
            cls.ENABLE_MULTI_LANGUAGE.value: _('Enable multi-language support'),
            cls.ENABLE_SSO.value: _('Enable single sign-on'),
            cls.ENABLE_TWO_FACTOR_AUTH.value: _('Enable two-factor authentication'),
        }
        return descriptions.get(feature, feature)


class TaskPriorityChoices(BaseChoiceEnum):
    """Task priority choices for background tasks."""
    
    LOW = 1
    NORMAL = 3
    HIGH = 5
    URGENT = 7
    CRITICAL = 9
    
    @classmethod
    def get_priority_label(cls, priority: int) -> str:
        """Get label for priority level."""
        labels = {
            cls.LOW.value: _('Low'),
            cls.NORMAL.value: _('Normal'),
            cls.HIGH.value: _('High'),
            cls.URGENT.value: _('Urgent'),
            cls.CRITICAL.value: _('Critical'),
        }
        return labels.get(priority, _('Unknown'))
    
    @classmethod
    def get_priority_color(cls, priority: int) -> str:
        """Get color for priority level."""
        colors = {
            cls.LOW.value: 'gray',
            cls.NORMAL.value: 'blue',
            cls.HIGH.value: 'orange',
            cls.URGENT.value: 'red',
            cls.CRITICAL.value: 'darkred',
        }
        return colors.get(priority, 'black')


class TaskStatusChoices(BaseChoiceEnum):
    """Task status choices."""
    
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RETRY = 'retry'
    CANCELLED = 'cancelled'
    
    @classmethod
    def get_status_color(cls, status: str) -> str:
        """Get color for task status."""
        colors = {
            cls.PENDING.value: 'gray',
            cls.RUNNING.value: 'blue',
            cls.COMPLETED.value: 'green',
            cls.FAILED.value: 'red',
            cls.RETRY.value: 'orange',
            cls.CANCELLED.value: 'darkgray',
        }
        return colors.get(status, 'black')


# Legacy choice tuples for backward compatibility
TENANT_PLAN_CHOICES = TenantPlanChoices.choices()
TENANT_STATUS_CHOICES = TenantStatusChoices.choices()
BILLING_STATUS_CHOICES = BillingStatusChoices.choices()
BILLING_CYCLE_CHOICES = BillingCycleChoices.choices()
INVOICE_STATUS_CHOICES = InvoiceStatusChoices.choices()
AUDIT_ACTION_CHOICES = AuditActionChoices.choices()
REFERRAL_BONUS_TYPE_CHOICES = ReferralBonusTypeChoices.choices()
LOG_LEVEL_CHOICES = LogLevelChoices.choices()
DATA_REGION_CHOICES = DataRegionChoices.choices()
CURRENCY_CHOICES = CurrencyChoices.choices()
COUNTRY_CODE_CHOICES = CountryCodeChoices.choices()
TIMEZONE_CHOICES = TimezoneChoices.choices()
PAYMENT_METHOD_CHOICES = PaymentMethodChoices.choices()
NOTIFICATION_CHANNEL_CHOICES = NotificationChannelChoices.choices()
SUPPORT_LEVEL_CHOICES = SupportLevelChoices.choices()
FEATURE_FLAG_CHOICES = FeatureFlagChoices.choices()
TASK_PRIORITY_CHOICES = [(p.value, p.get_priority_label(p.value)) for p in TaskPriorityChoices]
TASK_STATUS_CHOICES = TaskStatusChoices.choices()
