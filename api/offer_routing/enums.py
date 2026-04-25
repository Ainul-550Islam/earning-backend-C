"""
Enumerations for Offer Routing System
"""

from enum import Enum
from typing import Optional, Dict, Any


class RouteConditionType(str, Enum):
    """Route condition types."""
    AND = "and"
    OR = "or"


class RouteOperator(str, Enum):
    """Route condition operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IN = "in"
    NOT_IN = "not_in"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class ActionType(str, Enum):
    """Route action types."""
    SHOW = "show"
    HIDE = "hide"
    BOOST = "boost"
    CAP = "cap"
    REDIRECT = "redirect"


class UserSegmentType(str, Enum):
    """User segment types."""
    TIER = "tier"
    NEW_USER = "new_user"
    ACTIVE_USER = "active_user"
    CHURNED_USER = "churned_user"
    PREMIUM_USER = "premium_user"
    FREE_USER = "free_user"
    ENGAGED_USER = "engaged_user"
    INACTIVE_USER = "inactive_user"


class DeviceType(str, Enum):
    """Device types."""
    MOBILE = "mobile"
    DESKTOP = "desktop"
    TABLET = "tablet"
    SMART_TV = "smart_tv"
    WEARABLE = "wearable"
    GAME_CONSOLE = "game_console"


class OSType(str, Enum):
    """Operating system types."""
    IOS = "ios"
    ANDROID = "android"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    CHROME_OS = "chrome_os"


class BrowserType(str, Enum):
    """Browser types."""
    CHROME = "chrome"
    SAFARI = "safari"
    FIREFOX = "firefox"
    EDGE = "edge"
    OPERA = "opera"
    INTERNET_EXPLORER = "ie"


class CapType(str, Enum):
    """Cap types."""
    DAILY = "daily"
    HOURLY = "hourly"
    TOTAL = "total"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class FallbackType(str, Enum):
    """Fallback types."""
    CATEGORY = "category"
    NETWORK = "network"
    DEFAULT = "default"
    PROMOTION = "promotion"
    HIDE_SECTION = "hide_section"


class SignalType(str, Enum):
    """Signal types."""
    TIME = "time"
    LOCATION = "location"
    DEVICE = "device"
    BEHAVIOR = "behavior"
    WEATHER = "weather"
    CONTEXT = "context"


class PersonalizationAlgorithm(str, Enum):
    """Personalization algorithms."""
    COLLABORATIVE = "collaborative"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "machine_learning"


class ABTestVariant(str, Enum):
    """A/B test variants."""
    CONTROL = "control"
    VARIANT_A = "variant_a"
    VARIANT_B = "variant_b"


class RoutingDecisionReason(str, Enum):
    """Routing decision reasons."""
    ROUTE_MATCH = "route_match"
    CONDITION_EVALUATION = "condition_evaluation"
    SCORE_CALCULATION = "score_calculation"
    PERSONALIZATION = "personalization"
    CAP_ENFORCEMENT = "cap_enforcement"
    FALLBACK = "fallback"
    AB_TEST = "ab_test"
    CACHE_HIT = "cache_hit"


class EventType(str, Enum):
    """Event types."""
    PAGE_VIEW = "page_view"
    CLICK = "click"
    PURCHASE = "purchase"
    ADD_TO_CART = "add_to_cart"
    SEARCH = "search"
    LOGIN = "login"
    SIGNUP = "signup"


class OfferStatus(str, Enum):
    """Offer status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SCHEDULED = "scheduled"
    EXPIRED = "expired"
    PAUSED = "paused"


class RoutingPriority(int, Enum):
    """Routing priority levels."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class CacheKeyPattern(str, Enum):
    """Cache key patterns."""
    ROUTING = "offer_routing:routing:{user_id}:{context_hash}"
    SCORE = "offer_routing:score:{offer_id}:{user_id}"
    ROUTE = "offer_routing:route:{route_id}:{user_id}"
    CAP = "offer_routing:cap:{offer_id}:{user_id}"
    AFFINITY = "offer_routing:affinity:{user_id}:{category}"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(str, Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AggregationType(str, Enum):
    """Aggregation types."""
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"


class TimeWindow(str, Enum):
    """Time windows."""
    LAST_1_HOUR = "1h"
    LAST_6_HOURS = "6h"
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"


class ComparisonOperator(str, Enum):
    """Comparison operators."""
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"


class JoinType(str, Enum):
    """Join types for data queries."""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"


class SortOrder(str, Enum):
    """Sort orders."""
    ASC = "asc"
    DESC = "desc"


class DataSourceType(str, Enum):
    """Data source types."""
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL_API = "external_api"
    FILE = "file"
    STREAM = "stream"


class ProcessingStatus(str, Enum):
    """Processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationSeverity(str, Enum):
    """Validation severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class NotificationType(str, Enum):
    """Notification types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class PermissionLevel(str, Enum):
    """Permission levels."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class FeatureFlag(str, Enum):
    """Feature flags."""
    COLLABORATIVE_FILTERING = "collaborative_filtering"
    CONTENT_BASED_PERSONALIZATION = "content_based_personalization"
    HYBRID_PERSONALIZATION = "hybrid_personalization"
    BEHAVIORAL_TARGETING = "behavioral_targeting"
    GEOGRAPHIC_TARGETING = "geographic_targeting"
    DEVICE_TARGETING = "device_targeting"
    TIME_BASED_TARGETING = "time_based_targeting"
    A_B_TESTING = "a_b_testing"
    REAL_TIME_PERSONALIZATION = "real_time_personalization"


class CacheStrategy(str, Enum):
    """Cache strategies."""
    WRITE_THROUGH = "write_through"
    WRITE_AROUND = "write_around"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RANDOM = "random"


class ConsistencyLevel(str, Enum):
    """Consistency levels."""
    STRONG = "strong"
    EVENTUAL = "eventual"
    WEAK = "weak"


class RoutingMode(str, Enum):
    """Routing modes."""
    REAL_TIME = "real_time"
    BATCH = "batch"
    HYBRID = "hybrid"


class OptimizationGoal(str, Enum):
    """Optimization goals."""
    MAXIMIZE_CLICKS = "maximize_clicks"
    MAXIMIZE_CONVERSIONS = "maximize_conversions"
    MAXIMIZE_REVENUE = "maximize_revenue"
    MAXIMIZE_ENGAGEMENT = "maximize_engagement"
    BALANCE_EXPOSURE = "balance_exposure"


class StatisticalTest(str, Enum):
    """Statistical tests."""
    T_TEST = "t_test"
    CHI_SQUARE = "chi_square"
    Z_TEST = "z_test"
    WILCOXON = "wilcoxon"
    MANN_WHITNEY = "mann_whitney"


class ConfidenceLevel(float, Enum):
    """Confidence levels."""
    NINETY = 0.90
    NINETY_FIVE = 0.95
    NINETY_NINE = 0.99


class EffectSize(str, Enum):
    """Effect size measures."""
    COHENS_D = "cohens_d"
    PEARSON_R = "pearson_r"
    ODDS_RATIO = "odds_ratio"
    RISK_RATIO = "risk_ratio"


class DataType(str, Enum):
    """Data types."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TEXT = "text"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"
    ARRAY = "array"


class AggregationPeriod(str, Enum):
    """Aggregation periods."""
    REAL_TIME = "real_time"
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class AlertType(str, Enum):
    """Alert types."""
    PERFORMANCE = "performance"
    ERROR_RATE = "error_rate"
    CAP_EXCEEDED = "cap_exceeded"
    CACHE_MISS = "cache_miss"
    ROUTING_FAILURE = "routing_failure"
    AB_TEST_ANOMALY = "ab_test_anomaly"


class SeverityLevel(str, Enum):
    """Severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RoutingStrategy(str, Enum):
    """Routing strategies."""
    SCORE_BASED = "score_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    RANDOM = "random"
    WEIGHTED = "weighted"
    PRIORITY_BASED = "priority_based"


class PersonalizationLevel(str, Enum):
    """Personalization levels."""
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ULTRA = "ultra"


class TargetingPrecision(str, Enum):
    """Targeting precision levels."""
    BROAD = "broad"
    NARROW = "narrow"
    EXACT = "exact"
    FUZZY = "fuzzy"


class OfferType(str, Enum):
    """Offer types."""
    DISCOUNT = "discount"
    CASHBACK = "cashback"
    FREE_SHIPPING = "free_shipping"
    BUNDLE = "bundle"
    UPGRADE = "upgrade"
    LOYALTY = "loyalty"
    REFERRAL = "referral"


class ConversionType(str, Enum):
    """Conversion types."""
    PURCHASE = "purchase"
    SIGNUP = "signup"
    DOWNLOAD = "download"
    ACTIVATION = "activation"
    SUBSCRIPTION = "subscription"
    TRIAL_START = "trial_start"


class EngagementMetric(str, Enum):
    """Engagement metrics."""
    CLICK_THROUGH_RATE = "click_through_rate"
    CONVERSION_RATE = "conversion_rate"
    REVENUE_PER_OFFER = "revenue_per_offer"
    AVERAGE_ORDER_VALUE = "average_order_value"
    LIFETIME_VALUE = "lifetime_value"
    CHURN_RATE = "churn_rate"
    RETENTION_RATE = "retention_rate"


class QualityMetric(str, Enum):
    """Quality metrics."""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    MEAN_ABSOLUTE_ERROR = "mean_absolute_error"
    ROOT_MEAN_SQUARE_ERROR = "root_mean_square_error"


class SystemStatus(str, Enum):
    """System status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
