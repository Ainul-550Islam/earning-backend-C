"""
Enums for Advertiser Portal

This module contains enumeration classes used throughout the application
for type safety and consistent value representation.
"""

from enum import Enum, IntEnum, auto
from typing import Dict, Any, List, Tuple


class BaseEnum(Enum):
    """Base enum class with common functionality."""
    
    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model fields."""
        return [(member.value, member.name) for member in cls]
    
    @classmethod
    def values(cls) -> List[str]:
        """Get all enum values."""
        return [member.value for member in cls]
    
    @classmethod
    def names(cls) -> List[str]:
        """Get all enum names."""
        return [member.name for member in cls]
    
    @classmethod
    def from_value(cls, value: str):
        """Get enum member from value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid value for {cls.__name__}: {value}")


class StatusEnum(BaseEnum):
    """Status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VerificationStatusEnum(BaseEnum):
    """Verification status enumeration."""
    NOT_VERIFIED = "not_verified"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AccountTypeEnum(BaseEnum):
    """Account type enumeration."""
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    AGENCY = "agency"


class CampaignObjectiveEnum(BaseEnum):
    """Campaign objective enumeration."""
    AWARENESS = "awareness"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    LEADS = "leads"
    SALES = "sales"
    APP_PROMOTION = "app_promotion"
    STORE_VISITS = "store_visits"
    BRAND_SAFETY = "brand_safety"


class BiddingStrategyEnum(BaseEnum):
    """Bidding strategy enumeration."""
    MANUAL_CPC = "manual_cpc"
    ENHANCED_CPC = "enhanced_cpc"
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"
    MAXIMIZE_CLICKS = "maximize_clicks"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    TARGET_IMPRESSION_SHARE = "target_impression_share"


class BudgetDeliveryMethodEnum(BaseEnum):
    """Budget delivery method enumeration."""
    STANDARD = "standard"
    ACCELERATED = "accelerated"


class CreativeTypeEnum(BaseEnum):
    """Creative type enumeration."""
    BANNER = "banner"
    VIDEO = "video"
    NATIVE = "native"
    PLAYABLE = "playable"
    INTERACTIVE = "interactive"
    RICH_MEDIA = "rich_media"
    HTML5 = "html5"
    DYNAMIC = "dynamic"


class CreativeStatusEnum(BaseEnum):
    """Creative status enumeration."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class DeviceTypeEnum(BaseEnum):
    """Device type enumeration."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    CONNECTED_TV = "connected_tv"


class OSFamilyEnum(BaseEnum):
    """Operating system family enumeration."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    IOS = "ios"
    ANDROID = "android"
    OTHER = "other"


class BrowserEnum(BaseEnum):
    """Browser enumeration."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    SAFARI = "safari"
    EDGE = "edge"
    OPERA = "opera"
    IE = "ie"


class CarrierTypeEnum(BaseEnum):
    """Carrier type enumeration."""
    MOBILE = "mobile"
    WIFI = "wifi"
    BROADBAND = "broadband"
    DIALUP = "dialup"
    SATELLITE = "satellite"


class GenderEnum(BaseEnum):
    """Gender enumeration."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class AgeRangeEnum(BaseEnum):
    """Age range enumeration."""
    TEEN = "13-17"
    YOUNG_ADULT = "18-24"
    ADULT = "25-34"
    MIDDLE_AGED = "35-44"
    MATURE_ADULT = "45-54"
    SENIOR = "55-64"
    ELDERLY = "65+"


class LanguageEnum(BaseEnum):
    """Language enumeration."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    HINDI = "hi"


class GeoTargetingTypeEnum(BaseEnum):
    """Geo targeting type enumeration."""
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    POSTAL_CODE = "postal_code"
    COORDINATE = "coordinate"
    RADIUS = "radius"


class InterestCategoryEnum(BaseEnum):
    """Interest category enumeration."""
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    NEWS = "news"
    BUSINESS = "business"
    HEALTH = "health"
    EDUCATION = "education"
    TRAVEL = "travel"
    FOOD = "food"
    FASHION = "fashion"
    AUTOMOTIVE = "automotive"
    REAL_ESTATE = "real_estate"
    FINANCE = "finance"
    SHOPPING = "shopping"
    GAMING = "gaming"


class PaymentMethodEnum(BaseEnum):
    """Payment method enumeration."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    WIRE_TRANSFER = "wire_transfer"
    CRYPTO = "crypto"


class PaymentStatusEnum(BaseEnum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class BillingCycleEnum(BaseEnum):
    """Billing cycle enumeration."""
    PREPAID = "prepaid"
    POSTPAID = "postpaid"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class InvoiceStatusEnum(BaseEnum):
    """Invoice status enumeration."""
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class CreditTypeEnum(BaseEnum):
    """Credit type enumeration."""
    PAYMENT = "payment"
    REFUND = "refund"
    BONUS = "bonus"
    PROMOTION = "promotion"
    ADJUSTMENT = "adjustment"
    CHARGEBACK = "chargeback"


class FraudTypeEnum(BaseEnum):
    """Fraud type enumeration."""
    CLICK_FRAUD = "click_fraud"
    IMPRESSION_FRAUD = "impression_fraud"
    CONVERSION_FRAUD = "conversion_fraud"
    BOT_TRAFFIC = "bot_traffic"
    PROXY_TRAFFIC = "proxy_traffic"
    INVALID_GEO = "invalid_geo"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


class FraudActionEnum(BaseEnum):
    """Fraud action enumeration."""
    IGNORE = "ignore"
    FLAG = "flag"
    BLOCK = "block"
    INVESTIGATE = "investigate"
    REPORT = "report"


class RiskLevelEnum(BaseEnum):
    """Risk level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestTypeEnum(BaseEnum):
    """A/B test type enumeration."""
    CREATIVE_TEST = "creative_test"
    LANDING_PAGE_TEST = "landing_page_test"
    TARGETING_TEST = "targeting_test"
    BIDDING_TEST = "bidding_test"
    MESSAGE_TEST = "message_test"


class TestStatusEnum(BaseEnum):
    """A/B test status enumeration."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestResultEnum(BaseEnum):
    """A/B test result enumeration."""
    INCONCLUSIVE = "inconclusive"
    CONTROL_WINS = "control_wins"
    VARIANT_WINS = "variant_wins"
    STATISTICAL_TIE = "statistical_tie"


class ConfidenceLevelEnum(BaseEnum):
    """Confidence level enumeration."""
    NINETY = 90
    NINETY_FIVE = 95
    NINETY_NINE = 99


class MetricTypeEnum(BaseEnum):
    """Metric type enumeration."""
    COUNT = "count"
    RATE = "rate"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    TIME = "time"
    RATIO = "ratio"


class DimensionTypeEnum(BaseEnum):
    """Dimension type enumeration."""
    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    ENUM = "enum"


class GranularityEnum(BaseEnum):
    """Time granularity enumeration."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ReportFormatEnum(BaseEnum):
    """Report format enumeration."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"
    XML = "xml"


class DeliveryStatusEnum(BaseEnum):
    """Delivery status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LogLevelEnum(BaseEnum):
    """Log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditActionEnum(BaseEnum):
    """Audit action enumeration."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    APPROVE = "approve"
    REJECT = "reject"
    SUSPEND = "suspend"
    LOGIN = "login"
    LOGOUT = "logout"


class IntegrationTypeEnum(BaseEnum):
    """Integration type enumeration."""
    GOOGLE_ADS = "google_ads"
    FACEBOOK_ADS = "facebook_ads"
    TIKTOK_ADS = "tiktok_ads"
    SNAPCHAT_ADS = "snapchat_ads"
    TWITTER_ADS = "twitter_ads"
    LINKEDIN_ADS = "linkedin_ads"
    PINTEREST_ADS = "pinterest_ads"
    GOOGLE_ANALYTICS = "google_analytics"
    FACEBOOK_PIXEL = "facebook_pixel"
    GOOGLE_TAG_MANAGER = "google_tag_manager"
    APPSFLYER = "appsflyer"
    ADJUST = "adjust"
    BRANCH = "branch"
    AMPLITUDE = "amplitude"
    MIXPANEL = "mixpanel"


class IntegrationStatusEnum(BaseEnum):
    """Integration status enumeration."""
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    EXPIRED = "expired"


class WebhookEventEnum(BaseEnum):
    """Webhook event enumeration."""
    CONVERSION = "conversion"
    BUDGET_ALERT = "budget_alert"
    CAMPAIGN_STATUS_CHANGE = "campaign_status_change"
    CREATIVE_APPROVAL = "creative_approval"
    PAYMENT_PROCESSED = "payment_processed"
    INVOICE_GENERATED = "invoice_generated"
    FRAUD_DETECTED = "fraud_detected"
    ACCOUNT_SUSPENDED = "account_suspended"


class WebhookStatusEnum(BaseEnum):
    """Webhook status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DISABLED = "disabled"


class TaskStatusEnum(BaseEnum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriorityEnum(IntEnum):
    """Task priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class FrequencyCappingEnum(BaseEnum):
    """Frequency capping enumeration."""
    NO_LIMIT = "no_limit"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"
    PER_WEEK = "per_week"
    PER_MONTH = "per_month"
    PER_CAMPAIGN = "per_campaign"
    PER_LIFETIME = "per_lifetime"


class AttributionModelEnum(BaseEnum):
    """Attribution model enumeration."""
    LAST_CLICK = "last_click"
    FIRST_CLICK = "first_click"
    LINEAR = "linear"
    TIME_DECAY = "time_decay"
    POSITION_BASED = "position_based"
    DATA_DRIVEN = "data_driven"


class OptimizationGoalEnum(BaseEnum):
    """Optimization goal enumeration."""
    MAXIMIZE_CLICKS = "maximize_clicks"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    MAXIMIZE_REVENUE = "maximize_revenue"
    MINIMIZE_CPA = "minimize_cpa"
    MINIMIZE_CPC = "minimize_cpc"
    MAXIMIZE_ROAS = "maximize_roas"
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"


class CurrencyEnum(BaseEnum):
    """Currency enumeration."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"
    INR = "INR"
    BRL = "BRL"


class TimeZoneEnum(BaseEnum):
    """Time zone enumeration."""
    UTC = "UTC"
    EST = "EST"
    CST = "CST"
    MST = "MST"
    PST = "PST"
    CET = "CET"
    EET = "EET"
    IST = "IST"
    JST = "JST"
    AEST = "AEST"


class PermissionEnum(BaseEnum):
    """Permission enumeration."""
    READ_ADVERTISER = "read_advertiser"
    WRITE_ADVERTISER = "write_advertiser"
    DELETE_ADVERTISER = "delete_advertiser"
    READ_CAMPAIGN = "read_campaign"
    WRITE_CAMPAIGN = "write_campaign"
    DELETE_CAMPAIGN = "delete_campaign"
    READ_CREATIVE = "read_creative"
    WRITE_CREATIVE = "write_creative"
    DELETE_CREATIVE = "delete_creative"
    READ_ANALYTICS = "read_analytics"
    READ_BILLING = "read_billing"
    WRITE_BILLING = "write_billing"
    ADMIN_ACCESS = "admin_access"
    API_ACCESS = "api_access"


class RoleEnum(BaseEnum):
    """Role enumeration."""
    ADVERTISER = "advertiser"
    AGENCY = "agency"
    ACCOUNT_MANAGER = "account_manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    ANALYST = "analyst"
    BILLING_MANAGER = "billing_manager"


class NotificationTypeEnum(BaseEnum):
    """Notification type enumeration."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"


class NotificationChannelEnum(BaseEnum):
    """Notification channel enumeration."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class ExportFormatEnum(BaseEnum):
    """Export format enumeration."""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"
    XML = "xml"


class ImportStatusEnum(BaseEnum):
    """Import status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class ValidationSeverityEnum(BaseEnum):
    """Validation severity enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PerformanceTierEnum(BaseEnum):
    """Performance tier enumeration."""
    POOR = "poor"
    BELOW_AVERAGE = "below_average"
    AVERAGE = "average"
    ABOVE_AVERAGE = "above_average"
    EXCELLENT = "excellent"


class AlertSeverityEnum(BaseEnum):
    """Alert severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertTypeEnum(BaseEnum):
    """Alert type enumeration."""
    BUDGET_EXHAUSTED = "budget_exhausted"
    BUDGET_LOW = "budget_low"
    CAMPAIGN_PAUSED = "campaign_paused"
    CREATIVE_REJECTED = "creative_rejected"
    PAYMENT_FAILED = "payment_failed"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    PERFORMANCE_DECLINE = "performance_decline"
    INTEGRATION_ERROR = "integration_error"


class CacheKeyEnum(BaseEnum):
    """Cache key enumeration."""
    ADVERTISER_STATS = "advertiser_stats"
    CAMPAIGN_PERFORMANCE = "campaign_performance"
    CREATIVE_PERFORMANCE = "creative_performance"
    TARGETING_ESTIMATE = "targeting_estimate"
    USER_PERMISSIONS = "user_permissions"
    RATE_LIMIT = "rate_limit"
    ANALYTICS_DATA = "analytics_data"
    BILLING_SUMMARY = "billing_summary"


class ConfigKeyEnum(BaseEnum):
    """Configuration key enumeration."""
    MAX_CAMPAIGNS = "max_campaigns"
    MAX_CREATIVES = "max_creatives"
    DEFAULT_BUDGET = "default_budget"
    RATE_LIMIT = "rate_limit"
    CACHE_TIMEOUT = "cache_timeout"
    EMAIL_ENABLED = "email_enabled"
    SMS_ENABLED = "sms_enabled"
    WEBHOOK_ENABLED = "webhook_enabled"


class EnvironmentEnum(BaseEnum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class DatabaseTypeEnum(BaseEnum):
    """Database type enumeration."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"


class StorageTypeEnum(BaseEnum):
    """Storage type enumeration."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    DIGITAL_OCEAN = "digital_ocean"


class ProtocolEnum(BaseEnum):
    """Protocol enumeration."""
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    SFTP = "sftp"
    WS = "ws"
    WSS = "wss"


class EncodingEnum(BaseEnum):
    """Encoding enumeration."""
    UTF8 = "utf-8"
    UTF16 = "utf-16"
    ASCII = "ascii"
    ISO88591 = "iso-8859-1"
    BASE64 = "base64"


class CompressionEnum(BaseEnum):
    """Compression enumeration."""
    GZIP = "gzip"
    DEFLATE = "deflate"
    BROTLI = "brotli"
    ZIP = "zip"
    TAR = "tar"


class AlgorithmEnum(BaseEnum):
    """Algorithm enumeration."""
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    AES256 = "aes256"
    RSA = "rsa"


# Bidding and Budget Enums
class BidTypeEnum(BaseEnum):
    """Bid type enumeration."""
    CPC = "cpc"
    CPM = "cpm"
    CPA = "cpa"
    CPV = "cpv"


class BidStrategyEnum(BaseEnum):
    """Bid strategy enumeration."""
    MANUAL = "manual"
    MANUAL_CPC = "manual_cpc"
    ENHANCED_CPC = "enhanced_cpc"
    TARGET_CPA = "target_cpa"
    TARGET_ROAS = "target_roas"
    MAXIMIZE_CLICKS = "maximize_clicks"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    TARGET_IMPRESSION_SHARE = "target_impression_share"


class OptimizationGoalEnum(BaseEnum):
    """Optimization goal enumeration."""
    CONVERSIONS = "conversions"
    CLICKS = "clicks"
    IMPRESSIONS = "impressions"
    VIEWS = "views"
    ENGAGEMENT = "engagement"
    REACH = "reach"


class OptimizationTypeEnum(BaseEnum):
    """Optimization type enumeration."""
    PERFORMANCE = "performance"
    BUDGET = "budget"
    TARGETING = "targeting"
    CREATIVE = "creative"
    BIDDING = "bidding"
    AUTOMATED = "automated"


class BudgetTypeEnum(BaseEnum):
    """Budget type enumeration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"
    LIFETIME = "lifetime"


class BudgetAllocationTypeEnum(BaseEnum):
    """Budget allocation type enumeration."""
    CAMPAIGN = "campaign"
    AD_GROUP = "ad_group"
    KEYWORD = "keyword"
    PLACEMENT = "placement"
    DEMOGRAPHIC = "demographic"
    GEOGRAPHIC = "geographic"


class BudgetPeriodEnum(BaseEnum):
    """Budget period enumeration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class SpendRuleTypeEnum(BaseEnum):
    """Spend rule type enumeration."""
    BUDGET_CAP = "budget_cap"
    SPEND_LIMIT = "spend_limit"
    PERFORMANCE_BASED = "performance_based"
    TIME_BASED = "time_based"
    AUTOMATED = "automated"


class AlertTypeEnum(BaseEnum):
    """Alert type enumeration."""
    BUDGET_EXHAUSTED = "budget_exhausted"
    BUDGET_WARNING = "budget_warning"
    PERFORMANCE_DECLINE = "performance_decline"
    CAMPAIGN_PAUSED = "campaign_paused"
    PAYMENT_DUE = "payment_due"
    VERIFICATION_REQUIRED = "verification_required"


# Compliance Enums
class ComplianceCheckTypeEnum(BaseEnum):
    """Compliance check type enumeration."""
    BUSINESS_VERIFICATION = "business_verification"
    IDENTITY_VERIFICATION = "identity_verification"
    DOCUMENT_VERIFICATION = "document_verification"
    FINANCIAL_COMPLIANCE = "financial_compliance"
    ADVERTISING_STANDARDS = "advertising_standards"
    DATA_PROTECTION = "data_protection"


class ComplianceStatusEnum(BaseEnum):
    """Compliance status enumeration."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class CompliancePriorityEnum(BaseEnum):
    """Compliance priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentTypeEnum(BaseEnum):
    """Document type enumeration."""
    BUSINESS_LICENSE = "business_license"
    TAX_DOCUMENT = "tax_document"
    ID_DOCUMENT = "id_document"
    BANK_STATEMENT = "bank_statement"
    PROOF_OF_ADDRESS = "proof_of_address"
    CERTIFICATE_OF_INCORPORATION = "certificate_of_incorporation"


class DocumentStatusEnum(BaseEnum):
    """Document status enumeration."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class VerificationStatusEnum(BaseEnum):
    """Verification status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ViolationTypeEnum(BaseEnum):
    """Violation type enumeration."""
    POLICY_VIOLATION = "policy_violation"
    CONTENT_VIOLATION = "content_violation"
    TARGETING_VIOLATION = "targeting_violation"
    BUDGET_VIOLATION = "budget_violation"
    FRAUD_VIOLATION = "fraud_violation"


class ViolationSeverityEnum(BaseEnum):
    """Violation severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationStatusEnum(BaseEnum):
    """Violation status enumeration."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DetectionMethodEnum(BaseEnum):
    """Detection method enumeration."""
    AUTOMATED = "automated"
    MANUAL = "manual"
    USER_REPORT = "user_report"
    SYSTEM_ALERT = "system_alert"
    AUDIT = "audit"


class AuditTypeEnum(BaseEnum):
    """Audit type enumeration."""
    COMPLIANCE_AUDIT = "compliance_audit"
    FINANCIAL_AUDIT = "financial_audit"
    PERFORMANCE_AUDIT = "performance_audit"
    SECURITY_AUDIT = "security_audit"
    OPERATIONAL_AUDIT = "operational_audit"


class AuditGradeEnum(BaseEnum):
    """Audit grade enumeration."""
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"
    NOT_GRADED = "not_graded"
