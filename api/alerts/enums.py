"""
Alert System Enums
This file contains Python enums for type-safe constants throughout the alert system.
"""

from enum import Enum, auto


class AlertType(Enum):
    """Enum for alert types"""
    HIGH_EARNING = "high_earning"
    MASS_SIGNUP = "mass_signup"
    PAYMENT_SPIKE = "payment_spike"
    FRAUD_SPIKE = "fraud_spike"
    SERVER_ERROR = "server_error"
    LOW_BALANCE = "low_balance"
    SERVER_DOWN = "server_down"
    OFFER_FRAUD = "offer_fraud"
    REFERRAL_ABUSE = "referral_abuse"
    REVENUE_DROP = "revenue_drop"
    PAYOUT_DELAY = "payout_delay"
    GATEWAY_FAILURE = "gateway_failure"
    HIGH_CHURN = "high_churn"
    ABUSE_DETECTED = "abuse_detected"


class SeverityLevel(Enum):
    """Enum for severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    """Enum for notification types"""
    EMAIL = "email"
    TELEGRAM = "telegram"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"


class NotificationStatus(Enum):
    """Enum for notification status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    READ = "read"


class AlertStatus(Enum):
    """Enum for alert status"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"
    ARCHIVED = "archived"


class ThresholdType(Enum):
    """Enum for threshold types"""
    ABSOLUTE = "absolute"
    PERCENTAGE = "percentage"
    DEVIATION = "deviation"
    ROLLING = "rolling"


class ScheduleType(Enum):
    """Enum for schedule types"""
    RECURRING = "recurring"
    ONE_TIME = "one_time"
    MAINTENANCE = "maintenance"


class SuppressionType(Enum):
    """Enum for suppression types"""
    TEMPORAL = "temporal"
    CONDITIONAL = "conditional"
    GLOBAL = "global"


class HealthCheckStatus(Enum):
    """Enum for health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IncidentStatus(Enum):
    """Enum for incident status"""
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POST_MORTEM = "post_mortem"


class OnCallScheduleType(Enum):
    """Enum for on-call schedule types"""
    ROTATION = "rotation"
    FIXED = "fixed"
    FOLLOW_THE_SUN = "follow_the_sun"


class ChannelHealthStatus(Enum):
    """Enum for channel health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class ExportFormat(Enum):
    """Enum for export formats"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    PDF = "pdf"


class ReportType(Enum):
    """Enum for report types"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class PriorityLevel(Enum):
    """Enum for priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Environment(Enum):
    """Enum for environments"""
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TESTING = "testing"


class FeatureFlag(Enum):
    """Enum for feature flags"""
    ADAPTIVE_THRESHOLDS = "adaptive_thresholds"
    AI_CORRELATION = "ai_correlation"
    REAL_TIME_DASHBOARD = "real_time_dashboard"
    MULTI_TENANCY = "multi_tenancy"
    ADVANCED_REPORTING = "advanced_reporting"


class HttpStatusCode(Enum):
    """Enum for HTTP status codes"""
    TOO_MANY_REQUESTS = 429
    SERVICE_UNAVAILABLE = 503
    UNPROCESSABLE_ENTITY = 422
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


class LogLevel(Enum):
    """Enum for log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TimeUnit(Enum):
    """Enum for time units"""
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class ComparisonOperator(Enum):
    """Enum for comparison operators"""
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="


class AggregationFunction(Enum):
    """Enum for aggregation functions"""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    STDDEV = "stddev"


class AlertAction(Enum):
    """Enum for alert actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    TRIGGER = "trigger"
    RESOLVE = "resolve"
    ESCALATE = "escalate"
    SUPPRESS = "suppress"
    ACKNOWLEDGE = "acknowledge"


def get_display_name(enum_member):
    """Get display name for enum member"""
    if isinstance(enum_member, Enum):
        return enum_member.value.replace('_', ' ').title()
    return str(enum_member)


def from_value(enum_class, value):
    """Get enum member from value"""
    for member in enum_class:
        if member.value == value:
            return member
    raise ValueError(f"No {enum_class.__name__} with value {value}")


def get_choices(enum_class):
    """Get choices tuple for Django models from enum"""
    return [(member.value, get_display_name(member)) for member in enum_class]