"""
Model Choices for Advertiser Portal

This module contains all choice definitions for model fields
across the advertiser portal system.
"""

from django.utils.translation import gettext_lazy as _


class BaseChoices:
    """Base class for choice definitions."""
    
    @classmethod
    def get_choices(cls):
        """Get all choices as a list of tuples."""
        return [
            (getattr(cls, attr), getattr(cls, f"{attr}_label"))
            for attr in dir(cls)
            if not attr.startswith('_') and not callable(getattr(cls, attr)) and not attr.endswith('_label')
        ]
    
    @classmethod
    def get_labels(cls):
        """Get all labels as a dictionary."""
        return {
            getattr(cls, attr): getattr(cls, f"{attr}_label")
            for attr in dir(cls)
            if not attr.startswith('_') and not callable(getattr(cls, attr)) and not attr.endswith('_label')
        }
    
    @classmethod
    def get_value(cls, label):
        """Get value by label."""
        for value, lbl in cls.get_choices():
            if lbl == label:
                return value
        return None


class AdvertiserChoices(BaseChoices):
    """Choices for Advertiser model with new integration status codes."""
    
    # Verification status
    PENDING = 'pending'
    PENDING_label = _('Pending')
    
    VERIFIED = 'verified'
    VERIFIED_label = _('Verified')
    
    REJECTED = 'rejected'
    REJECTED_label = _('Rejected')
    
    SUSPENDED = 'suspended'
    SUSPENDED_label = _('Suspended')
    
    # Integration status
    SYNCED = 'synced'
    SYNCED_label = _('Synced with Legacy System')
    
    UNSYNCED = 'unsynced'
    UNSYNCED_label = _('Not Synced with Legacy System')
    
    # Business type
    INDIVIDUAL = 'individual'
    INDIVIDUAL_label = _('Individual')
    
    COMPANY = 'company'
    COMPANY_label = _('Company')
    
    AGENCY = 'agency'
    AGENCY_label = _('Agency')
    
    # Company size
    STARTUP = 'startup'
    STARTUP_label = _('Startup (1-10)')
    
    SMALL = 'small'
    SMALL_label = _('Small (11-50)')
    
    MEDIUM = 'medium'
    MEDIUM_label = _('Medium (51-250)')
    
    LARGE = 'large'
    LARGE_label = _('Large (251-1000)')
    
    ENTERPRISE = 'enterprise'
    ENTERPRISE_label = _('Enterprise (1000+)')
    
    REJECTED = 'rejected'
    REJECTED_label = _('Rejected')
    
    SUSPENDED = 'suspended'
    SUSPENDED_label = _('Suspended')
    
    VERIFICATION_STATUS_CHOICES = [
        (PENDING, PENDING_label),
        (VERIFIED, VERIFIED_label),
        (REJECTED, REJECTED_label),
        (SUSPENDED, SUSPENDED_label),
    ]
    
    # Account status
    ACTIVE = 'active'
    ACTIVE_label = _('Active')
    
    INACTIVE = 'inactive'
    INACTIVE_label = _('Inactive')
    
    ACCOUNT_STATUS_CHOICES = [
        (ACTIVE, ACTIVE_label),
        (INACTIVE, INACTIVE_label),
    ]
    
    # Industry types
    TECHNOLOGY = 'technology'
    TECHNOLOGY_label = _('Technology')
    
    FINANCE = 'finance'
    FINANCE_label = _('Finance')
    
    HEALTHCARE = 'healthcare'
    HEALTHCARE_label = _('Healthcare')
    
    RETAIL = 'retail'
    RETAIL_label = _('Retail')
    
    EDUCATION = 'education'
    EDUCATION_label = _('Education')
    
    ENTERTAINMENT = 'entertainment'
    ENTERTAINMENT_label = _('Entertainment')
    
    TRAVEL = 'travel'
    TRAVEL_label = _('Travel')
    
    AUTOMOTIVE = 'automotive'
    AUTOMOTIVE_label = _('Automotive')
    
    REAL_ESTATE = 'real_estate'
    REAL_ESTATE_label = _('Real Estate')
    
    OTHER = 'other'
    OTHER_label = _('Other')
    
    INDUSTRY_CHOICES = [
        (TECHNOLOGY, TECHNOLOGY_label),
        (FINANCE, FINANCE_label),
        (HEALTHCARE, HEALTHCARE_label),
        (RETAIL, RETAIL_label),
        (EDUCATION, EDUCATION_label),
        (ENTERTAINMENT, ENTERTAINMENT_label),
        (TRAVEL, TRAVEL_label),
        (AUTOMOTIVE, AUTOMOTIVE_label),
        (REAL_ESTATE, REAL_ESTATE_label),
        (OTHER, OTHER_label),
    ]


class CampaignChoices(BaseChoices):
    """Choices for Campaign model with new integration status codes."""
    
    # Status
    DRAFT = 'draft'
    DRAFT_label = _('Draft')
    
    ACTIVE = 'active'
    ACTIVE_label = _('Active')
    
    PAUSED = 'paused'
    PAUSED_label = _('Paused')
    
    COMPLETED = 'completed'
    COMPLETED_label = _('Completed')
    
    CANCELLED = 'cancelled'
    CANCELLED_label = _('Cancelled')
    
    ARCHIVED = 'archived'
    ARCHIVED_label = _('Archived')
        (DRAFT, DRAFT_label),
        (ACTIVE, ACTIVE_label),
        (PAUSED, PAUSED_label),
        (COMPLETED, COMPLETED_label),
        (CANCELLED, CANCELLED_label),
    ]
    
    # Campaign types
    DISPLAY = 'display'
    DISPLAY_label = _('Display')
    
    SEARCH = 'search'
    SEARCH_label = _('Search')
    
    SOCIAL = 'social'
    SOCIAL_label = _('Social')
    
    VIDEO = 'video'
    VIDEO_label = _('Video')
    
    NATIVE = 'native'
    NATIVE_label = _('Native')
    
    MOBILE = 'mobile'
    MOBILE_label = _('Mobile')
    
    CAMPAIGN_TYPE_CHOICES = [
        (DISPLAY, DISPLAY_label),
        (SEARCH, SEARCH_label),
        (SOCIAL, SOCIAL_label),
        (VIDEO, VIDEO_label),
        (NATIVE, NATIVE_label),
        (MOBILE, MOBILE_label),
    ]
    
    # Campaign objectives
    AWARENESS = 'awareness'
    AWARENESS_label = _('Brand Awareness')
    
    TRAFFIC = 'traffic'
    TRAFFIC_label = _('Website Traffic')
    
    ENGAGEMENT = 'engagement'
    ENGAGEMENT_label = _('Engagement')
    
    LEADS = 'leads'
    LEADS_label = _('Lead Generation')
    
    SALES = 'sales'
    SALES_label = _('Sales/Conversions')
    
    APP_PROMOTION = 'app_promotion'
    APP_PROMOTION_label = _('App Promotion')
    
    OBJECTIVE_CHOICES = [
        (AWARENESS, AWARENESS_label),
        (TRAFFIC, TRAFFIC_label),
        (ENGAGEMENT, ENGAGEMENT_label),
        (LEADS, LEADS_label),
        (SALES, SALES_label),
        (APP_PROMOTION, APP_PROMOTION_label),
    ]
    
    # Bidding strategies
    MANUAL_CPC = 'manual_cpc'
    MANUAL_CPC_label = _('Manual CPC')
    
    ENHANCED_CPC = 'enhanced_cpc'
    ENHANCED_CPC_label = _('Enhanced CPC')
    
    TARGET_CPA = 'target_cpa'
    TARGET_CPA_label = _('Target CPA')
    
    TARGET_ROAS = 'target_roas'
    TARGET_ROAS_label = _('Target ROAS')
    
    MAXIMIZE_CLICKS = 'maximize_clicks'
    MAXIMIZE_CLICKS_label = _('Maximize Clicks')
    
    MAXIMIZE_CONVERSIONS = 'maximize_conversions'
    MAXIMIZE_CONVERSIONS_label = _('Maximize Conversions')
    
    BIDDING_STRATEGY_CHOICES = [
        (MANUAL_CPC, MANUAL_CPC_label),
        (ENHANCED_CPC, ENHANCED_CPC_label),
        (TARGET_CPA, TARGET_CPA_label),
        (TARGET_ROAS, TARGET_ROAS_label),
        (MAXIMIZE_CLICKS, MAXIMIZE_CLICKS_label),
        (MAXIMIZE_CONVERSIONS, MAXIMIZE_CONVERSIONS_label),
    ]


class OfferChoices(BaseChoices):
    """Choices for Offer model."""
    
    # Offer types
    CPA = 'cpa'
    CPA_label = _('Cost Per Action')
    
    CPL = 'cpl'
    CPL_label = _('Cost Per Lead')
    
    CPS = 'cps'
    CPS_label = _('Cost Per Sale')
    
    CPC = 'cpc'
    CPC_label = _('Cost Per Click')
    
    CPM = 'cpm'
    CPM_label = _('Cost Per Mille')
    
    CPI = 'cpi'
    CPI_label = _('Cost Per Install')
    
    REVSHARE = 'revshare'
    REVSHARE_label = _('Revenue Share')
    
    OFFER_TYPE_CHOICES = [
        (CPA, CPA_label),
        (CPL, CPL_label),
        (CPS, CPS_label),
        (CPC, CPC_label),
        (CPM, CPM_label),
        (CPI, CPI_label),
        (REVSHARE, REVSHARE_label),
    ]
    
    # Pricing models
    FIXED = 'fixed'
    FIXED_label = _('Fixed Amount')
    
    PERCENTAGE = 'percentage'
    PERCENTAGE_label = _('Percentage')
    
    TIERED = 'tiered'
    TIERED_label = _('Tiered')
    
    DYNAMIC = 'dynamic'
    DYNAMIC_label = _('Dynamic')
    
    PRICING_MODEL_CHOICES = [
        (FIXED, FIXED_label),
        (PERCENTAGE, PERCENTAGE_label),
        (TIERED, TIERED_label),
        (DYNAMIC, DYNAMIC_label),
    ]
    
    # Offer status
    ACTIVE = 'active'
    ACTIVE_label = _('Active')
    
    INACTIVE = 'inactive'
    INACTIVE_label = _('Inactive')
    
    PENDING = 'pending'
    PENDING_label = _('Pending')
    
    EXPIRED = 'expired'
    EXPIRED_label = _('Expired')
    
    STATUS_CHOICES = [
        (ACTIVE, ACTIVE_label),
        (INACTIVE, INACTIVE_label),
        (PENDING, PENDING_label),
        (EXPIRED, EXPIRED_label),
    ]
    
    # Offer categories
    ECOMMERCE = 'ecommerce'
    ECOMMERCE_label = _('E-commerce')
    
    FINANCE = 'finance'
    FINANCE_label = _('Finance')
    
    GAMING = 'gaming'
    GAMING_label = _('Gaming')
    
    DATING = 'dating'
    DATING_label = _('Dating')
    
    HEALTH = 'health'
    HEALTH_label = _('Health & Wellness')
    
    EDUCATION = 'education'
    EDUCATION_label = _('Education')
    
    TRAVEL = 'travel'
    TRAVEL_label = _('Travel')
    
    ENTERTAINMENT = 'entertainment'
    ENTERTAINMENT_label = _('Entertainment')
    
    CATEGORY_CHOICES = [
        (ECOMMERCE, ECOMMERCE_label),
        (FINANCE, FINANCE_label),
        (GAMING, GAMING_label),
        (DATING, DATING_label),
        (HEALTH, HEALTH_label),
        (EDUCATION, EDUCATION_label),
        (TRAVEL, TRAVEL_label),
        (ENTERTAINMENT, ENTERTAINMENT_label),
    ]


class TrackingChoices(BaseChoices):
    """Choices for Tracking model."""
    
    # Pixel types
    CONVERSION = 'conversion'
    CONVERSION_label = _('Conversion Pixel')
    
    IMPRESSION = 'impression'
    IMPRESSION_label = _('Impression Pixel')
    
    CLICK = 'click'
    CLICK_label = _('Click Pixel')
    
    POSTBACK = 'postback'
    POSTBACK_label = _('Server-to-Server Postback')
    
    PIXEL_TYPE_CHOICES = [
        (CONVERSION, CONVERSION_label),
        (IMPRESSION, IMPRESSION_label),
        (CLICK, CLICK_label),
        (POSTBACK, POSTBACK_label),
    ]
    
    # Event types
    CLICK = 'click'
    CLICK_label = _('Click')
    
    IMPRESSION = 'impression'
    IMPRESSION_label = _('Impression')
    
    CONVERSION = 'conversion'
    CONVERSION_label = _('Conversion')
    
    LEAD = 'lead'
    LEAD_label = _('Lead')
    
    SALE = 'sale'
    SALE_label = _('Sale')
    
    INSTALL = 'install'
    INSTALL_label = _('Install')
    
    SIGNUP = 'signup'
    SIGNUP_label = _('Signup')
    
    EVENT_TYPE_CHOICES = [
        (CLICK, CLICK_label),
        (IMPRESSION, IMPRESSION_label),
        (CONVERSION, CONVERSION_label),
        (LEAD, LEAD_label),
        (SALE, SALE_label),
        (INSTALL, INSTALL_label),
        (SIGNUP, SIGNUP_label),
    ]
    
    # Device types
    DESKTOP = 'desktop'
    DESKTOP_label = _('Desktop')
    
    MOBILE = 'mobile'
    MOBILE_label = _('Mobile')
    
    TABLET = 'tablet'
    TABLET_label = _('Tablet')
    
    SMART_TV = 'smart_tv'
    SMART_TV_label = _('Smart TV')
    
    GAMING_CONSOLE = 'gaming_console'
    GAMING_CONSOLE_label = _('Gaming Console')
    
    DEVICE_TYPE_CHOICES = [
        (DESKTOP, DESKTOP_label),
        (MOBILE, MOBILE_label),
        (TABLET, TABLET_label),
        (SMART_TV, SMART_TV_label),
        (GAMING_CONSOLE, GAMING_CONSOLE_label),
    ]


class BillingChoices(BaseChoices):
    """Choices for Billing model."""
    
    # Transaction types
    DEPOSIT = 'deposit'
    DEPOSIT_label = _('Deposit')
    
    WITHDRAWAL = 'withdrawal'
    WITHDRAWAL_label = _('Withdrawal')
    
    SPEND = 'spend'
    SPEND_label = _('Campaign Spend')
    
    REFUND = 'refund'
    REFUND_label = _('Refund')
    
    BONUS = 'bonus'
    BONUS_label = _('Bonus')
    
    PENALTY = 'penalty'
    PENALTY_label = _('Penalty')
    
    TRANSACTION_TYPE_CHOICES = [
        (DEPOSIT, DEPOSIT_label),
        (WITHDRAWAL, WITHDRAWAL_label),
        (SPEND, SPEND_label),
        (REFUND, REFUND_label),
        (BONUS, BONUS_label),
        (PENALTY, PENALTY_label),
    ]
    
    # Payment methods
    CREDIT_CARD = 'credit_card'
    CREDIT_CARD_label = _('Credit Card')
    
    DEBIT_CARD = 'debit_card'
    DEBIT_CARD_label = _('Debit Card')
    
    BANK_TRANSFER = 'bank_transfer'
    BANK_TRANSFER_label = _('Bank Transfer')
    
    PAYPAL = 'paypal'
    PAYPAL_label = _('PayPal')
    
    STRIPE = 'stripe'
    STRIPE_label = _('Stripe')
    
    WIRE = 'wire'
    WIRE_label = _('Wire Transfer')
    
    PAYMENT_METHOD_CHOICES = [
        (CREDIT_CARD, CREDIT_CARD_label),
        (DEBIT_CARD, DEBIT_CARD_label),
        (BANK_TRANSFER, BANK_TRANSFER_label),
        (PAYPAL, PAYPAL_label),
        (STRIPE, STRIPE_label),
        (WIRE, WIRE_label),
    ]
    
    # Invoice statuses
    DRAFT = 'draft'
    DRAFT_label = _('Draft')
    
    SENT = 'sent'
    SENT_label = _('Sent')
    
    PAID = 'paid'
    PAID_label = _('Paid')
    
    OVERDUE = 'overdue'
    OVERDUE_label = _('Overdue')
    
    CANCELLED = 'cancelled'
    CANCELLED_label = _('Cancelled')
    
    INVOICE_STATUS_CHOICES = [
        (DRAFT, DRAFT_label),
        (SENT, SENT_label),
        (PAID, PAID_label),
        (OVERDUE, OVERDUE_label),
        (CANCELLED, CANCELLED_label),
    ]


class FraudChoices(BaseChoices):
    """Choices for Fraud Detection model."""
    
    # Fraud types
    CLICK_FRAUD = 'click_fraud'
    CLICK_FRAUD_label = _('Click Fraud')
    
    CONVERSION_FRAUD = 'conversion_fraud'
    CONVERSION_FRAUD_label = _('Conversion Fraud')
    
    IP_FRAUD = 'ip_fraud'
    IP_FRAUD_label = _('IP Fraud')
    
    DEVICE_FRAUD = 'device_fraud'
    DEVICE_FRAUD_label = _('Device Fraud')
    
    BOT_TRAFFIC = 'bot_traffic'
    BOT_TRAFFIC_label = _('Bot Traffic')
    
    PROXY_TRAFFIC = 'proxy_traffic'
    PROXY_TRAFFIC_label = _('Proxy Traffic')
    
    FRAUD_TYPE_CHOICES = [
        (CLICK_FRAUD, CLICK_FRAUD_label),
        (CONVERSION_FRAUD, CONVERSION_FRAUD_label),
        (IP_FRAUD, IP_FRAUD_label),
        (DEVICE_FRAUD, DEVICE_FRAUD_label),
        (BOT_TRAFFIC, BOT_TRAFFIC_label),
        (PROXY_TRAFFIC, PROXY_TRAFFIC_label),
    ]
    
    # Risk levels
    LOW = 'low'
    LOW_label = _('Low Risk')
    
    MEDIUM = 'medium'
    MEDIUM_label = _('Medium Risk')
    
    HIGH = 'high'
    HIGH_label = _('High Risk')
    
    CRITICAL = 'critical'
    CRITICAL_label = _('Critical Risk')
    
    RISK_LEVEL_CHOICES = [
        (LOW, LOW_label),
        (MEDIUM, MEDIUM_label),
        (HIGH, HIGH_label),
        (CRITICAL, CRITICAL_label),
    ]
    
    # Quality levels
    HIGH = 'high'
    HIGH_label = _('High Quality')
    
    MEDIUM = 'medium'
    MEDIUM_label = _('Medium Quality')
    
    LOW = 'low'
    LOW_label = _('Low Quality')
    
    INVALID = 'invalid'
    INVALID_label = _('Invalid')
    
    QUALITY_LEVEL_CHOICES = [
        (HIGH, HIGH_label),
        (MEDIUM, MEDIUM_label),
        (LOW, LOW_label),
        (INVALID, INVALID_label),
    ]


class NotificationChoices(BaseChoices):
    """Choices for Notification model."""
    
    # Notification types
    INFO = 'info'
    INFO_label = _('Information')
    
    WARNING = 'warning'
    WARNING_label = _('Warning')
    
    ERROR = 'error'
    ERROR_label = _('Error')
    
    SUCCESS = 'success'
    SUCCESS_label = _('Success')
    
    BILLING = 'billing'
    BILLING_label = _('Billing')
    
    CAMPAIGN = 'campaign'
    CAMPAIGN_label = _('Campaign')
    
    OFFER = 'offer'
    OFFER_label = _('Offer')
    
    FRAUD = 'fraud'
    FRAUD_label = _('Fraud Alert')
    
    SYSTEM = 'system'
    SYSTEM_label = _('System')
    
    NOTIFICATION_TYPE_CHOICES = [
        (INFO, INFO_label),
        (WARNING, WARNING_label),
        (ERROR, ERROR_label),
        (SUCCESS, SUCCESS_label),
        (BILLING, BILLING_label),
        (CAMPAIGN, CAMPAIGN_label),
        (OFFER, OFFER_label),
        (FRAUD, FRAUD_label),
        (SYSTEM, SYSTEM_label),
    ]
    
    # Priority levels
    LOW = 'low'
    LOW_label = _('Low')
    
    MEDIUM = 'medium'
    MEDIUM_label = _('Medium')
    
    HIGH = 'high'
    HIGH_label = _('High')
    
    URGENT = 'urgent'
    URGENT_label = _('Urgent')
    
    PRIORITY_CHOICES = [
        (LOW, LOW_label),
        (MEDIUM, MEDIUM_label),
        (HIGH, HIGH_label),
        (URGENT, URGENT_label),
    ]
    
    # Channels
    EMAIL = 'email'
    EMAIL_label = _('Email')
    
    SMS = 'sms'
    SMS_label = _('SMS')
    
    PUSH = 'push'
    PUSH_label = _('Push Notification')
    
    IN_APP = 'in_app'
    IN_APP_label = _('In-App')
    
    WEBHOOK = 'webhook'
    WEBHOOK_label = _('Webhook')
    
    CHANNEL_CHOICES = [
        (EMAIL, EMAIL_label),
        (SMS, SMS_label),
        (PUSH, PUSH_label),
        (IN_APP, IN_APP_label),
        (WEBHOOK, WEBHOOK_label),
    ]


class ReportChoices(BaseChoices):
    """Choices for Reporting model."""
    
    # Report types
    CAMPAIGN = 'campaign'
    CAMPAIGN_label = _('Campaign Report')
    
    OFFER = 'offer'
    OFFER_label = _('Offer Report')
    
    BILLING = 'billing'
    BILLING_label = _('Billing Report')
    
    CONVERSION = 'conversion'
    CONVERSION_label = _('Conversion Report')
    
    FRAUD = 'fraud'
    FRAUD_label = _('Fraud Report')
    
    PERFORMANCE = 'performance'
    PERFORMANCE_label = _('Performance Report')
    
    ANALYTICS = 'analytics'
    ANALYTICS_label = _('Analytics Report')
    
    CUSTOM = 'custom'
    CUSTOM_label = _('Custom Report')
    
    REPORT_TYPE_CHOICES = [
        (CAMPAIGN, CAMPAIGN_label),
        (OFFER, OFFER_label),
        (BILLING, BILLING_label),
        (CONVERSION, CONVERSION_label),
        (FRAUD, FRAUD_label),
        (PERFORMANCE, PERFORMANCE_label),
        (ANALYTICS, ANALYTICS_label),
        (CUSTOM, CUSTOM_label),
    ]
    
    # Report formats
    CSV = 'csv'
    CSV_label = _('CSV')
    
    XLSX = 'xlsx'
    XLSX_label = _('Excel')
    
    PDF = 'pdf'
    PDF_label = _('PDF')
    
    JSON = 'json'
    JSON_label = _('JSON')
    
    XML = 'xml'
    XML_label = _('XML')
    
    FORMAT_CHOICES = [
        (CSV, CSV_label),
        (XLSX, XLSX_label),
        (PDF, PDF_label),
        (JSON, JSON_label),
        (XML, XML_label),
    ]


class MLChoices(BaseChoices):
    """Choices for Machine Learning model."""
    
    # Model types
    CLASSIFICATION = 'classification'
    CLASSIFICATION_label = _('Classification')
    
    REGRESSION = 'regression'
    REGRESSION_label = _('Regression')
    
    CLUSTERING = 'clustering'
    CLUSTERING_label = _('Clustering')
    
    ANOMALY_DETECTION = 'anomaly_detection'
    ANOMALY_DETECTION_label = _('Anomaly Detection')
    
    RECOMMENDATION = 'recommendation'
    RECOMMENDATION_label = _('Recommendation')
    
    TIME_SERIES = 'time_series'
    TIME_SERIES_label = _('Time Series')
    
    MODEL_TYPE_CHOICES = [
        (CLASSIFICATION, CLASSIFICATION_label),
        (REGRESSION, REGRESSION_label),
        (CLUSTERING, CLUSTERING_label),
        (ANOMALY_DETECTION, ANOMALY_DETECTION_label),
        (RECOMMENDATION, RECOMMENDATION_label),
        (TIME_SERIES, TIME_SERIES_label),
    ]
    
    # Model statuses
    TRAINING = 'training'
    TRAINING_label = _('Training')
    
    TRAINED = 'trained'
    TRAINED_label = _('Trained')
    
    ACTIVE = 'active'
    ACTIVE_label = _('Active')
    
    INACTIVE = 'inactive'
    INACTIVE_label = _('Inactive')
    
    FAILED = 'failed'
    FAILED_label = _('Failed')
    
    DEPRECATED = 'deprecated'
    DEPRECATED_label = _('Deprecated')
    
    MODEL_STATUS_CHOICES = [
        (TRAINING, TRAINING_label),
        (TRAINED, TRAINED_label),
        (ACTIVE, ACTIVE_label),
        (INACTIVE, INACTIVE_label),
        (FAILED, FAILED_label),
        (DEPRECATED, DEPRECATED_label),
    ]


# Utility functions for working with choices
def get_choice_value(choice_class, label):
    """Get choice value by label."""
    return choice_class.get_value(label)


def get_choice_label(choice_class, value):
    """Get choice label by value."""
    labels = choice_class.get_labels()
    return labels.get(value, value)


def format_choices_for_api(choices):
    """Format choices for API response."""
    return [
        {'value': choice[0], 'label': str(choice[1])}
        for choice in choices
    ]


def validate_choice(choice_class, value):
    """Validate that a value is in the choice class."""
    valid_values = [choice[0] for choice in choice_class.get_choices()]
    return value in valid_values


# Export all choice classes
__all__ = [
    'BaseChoices',
    'AdvertiserChoices',
    'CampaignChoices',
    'OfferChoices',
    'TrackingChoices',
    'BillingChoices',
    'FraudChoices',
    'NotificationChoices',
    'ReportChoices',
    'MLChoices',
    'get_choice_value',
    'get_choice_label',
    'format_choices_for_api',
    'validate_choice',
]
