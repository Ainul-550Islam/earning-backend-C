"""
Choice definitions for Offer Routing System
"""

from django.utils.translation import gettext_lazy as _


class RouteConditionType:
    """Types of route conditions."""
    AND = 'and'
    OR = 'or'
    
    CHOICES = [
        (AND, 'AND - All conditions must be true'),
        (OR, 'OR - Any condition must be true'),
    ]


class RouteOperator:
    """Operators for route conditions."""
    EQUALS = 'equals'
    NOT_EQUALS = 'not_equals'
    GREATER_THAN = 'greater_than'
    LESS_THAN = 'less_than'
    GREATER_EQUAL = 'greater_equal'
    LESS_EQUAL = 'less_equal'
    CONTAINS = 'contains'
    NOT_CONTAINS = 'not_contains'
    IN = 'in'
    NOT_IN = 'not_in'
    STARTS_WITH = 'starts_with'
    ENDS_WITH = 'ends_with'
    
    CHOICES = [
        (EQUALS, 'Equals'),
        (NOT_EQUALS, 'Not Equals'),
        (GREATER_THAN, 'Greater Than'),
        (LESS_THAN, 'Less Than'),
        (GREATER_EQUAL, 'Greater or Equal'),
        (LESS_EQUAL, 'Less or Equal'),
        (CONTAINS, 'Contains'),
        (NOT_CONTAINS, 'Does Not Contain'),
        (IN, 'In List'),
        (NOT_IN, 'Not In List'),
        (STARTS_WITH, 'Starts With'),
        (ENDS_WITH, 'Ends With'),
    ]


class ActionType:
    """Types of route actions."""
    SHOW = 'show'
    HIDE = 'hide'
    BOOST = 'boost'
    CAP = 'cap'
    REDIRECT = 'redirect'
    
    CHOICES = [
        (SHOW, 'Show Offer'),
        (HIDE, 'Hide Offer'),
        (BOOST, 'Boost Offer Priority'),
        (CAP, 'Limit Offer Exposure'),
        (REDIRECT, 'Redirect to Alternative'),
    ]


class UserSegmentType:
    """Types of user segments."""
    TIER = 'tier'
    NEW_USER = 'new_user'
    ACTIVE_USER = 'active_user'
    CHURNED_USER = 'churned_user'
    PREMIUM_USER = 'premium_user'
    FREE_USER = 'free_user'
    ENGAGED_USER = 'engaged_user'
    INACTIVE_USER = 'inactive_user'
    
    CHOICES = [
        (TIER, 'User Tier'),
        (NEW_USER, 'New User'),
        (ACTIVE_USER, 'Active User'),
        (CHURNED_USER, 'Churned User'),
        (PREMIUM_USER, 'Premium User'),
        (FREE_USER, 'Free User'),
        (ENGAGED_USER, 'Engaged User'),
        (INACTIVE_USER, 'Inactive User'),
    ]


class DeviceType:
    """Device types for targeting."""
    MOBILE = 'mobile'
    DESKTOP = 'desktop'
    TABLET = 'tablet'
    SMART_TV = 'smart_tv'
    WEARABLE = 'wearable'
    GAME_CONSOLE = 'game_console'
    
    CHOICES = [
        (MOBILE, 'Mobile'),
        (DESKTOP, 'Desktop'),
        (TABLET, 'Tablet'),
        (SMART_TV, 'Smart TV'),
        (WEARABLE, 'Wearable'),
        (GAME_CONSOLE, 'Game Console'),
    ]


class OSType:
    """Operating system types."""
    IOS = 'ios'
    ANDROID = 'android'
    WINDOWS = 'windows'
    MACOS = 'macos'
    LINUX = 'linux'
    CHROME_OS = 'chrome_os'
    
    CHOICES = [
        (IOS, 'iOS'),
        (ANDROID, 'Android'),
        (WINDOWS, 'Windows'),
        (MACOS, 'macOS'),
        (LINUX, 'Linux'),
        (CHROME_OS, 'Chrome OS'),
    ]


class BrowserType:
    """Browser types for targeting."""
    CHROME = 'chrome'
    SAFARI = 'safari'
    FIREFOX = 'firefox'
    EDGE = 'edge'
    OPERA = 'opera'
    INTERNET_EXPLORER = 'ie'
    
    CHOICES = [
        (CHROME, 'Chrome'),
        (SAFARI, 'Safari'),
        (FIREFOX, 'Firefox'),
        (EDGE, 'Edge'),
        (OPERA, 'Opera'),
        (INTERNET_EXPLORER, 'Internet Explorer'),
    ]


class CapType:
    """Types of offer caps."""
    DAILY = 'daily'
    HOURLY = 'hourly'
    TOTAL = 'total'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    
    CHOICES = [
        (DAILY, 'Daily'),
        (HOURLY, 'Hourly'),
        (TOTAL, 'Total'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly'),
    ]


class FallbackType:
    """Types of fallback rules."""
    CATEGORY = 'category'
    NETWORK = 'network'
    DEFAULT = 'default'
    PROMOTION = 'promotion'
    HIDE_SECTION = 'hide_section'
    
    CHOICES = [
        (CATEGORY, 'Category-based'),
        (NETWORK, 'Network-based'),
        (DEFAULT, 'Default Offer'),
        (PROMOTION, 'Promotional Offer'),
        (HIDE_SECTION, 'Hide Section'),
    ]


class SignalType:
    """Types of contextual signals."""
    TIME = 'time'
    LOCATION = 'location'
    DEVICE = 'device'
    BEHAVIOR = 'behavior'
    WEATHER = 'weather'
    CONTEXT = 'context'
    
    CHOICES = [
        (TIME, 'Time-based'),
        (LOCATION, 'Location-based'),
        (DEVICE, 'Device-based'),
        (BEHAVIOR, 'Behavior-based'),
        (WEATHER, 'Weather-based'),
        (CONTEXT, 'Context-based'),
    ]


class PersonalizationLevel:
    """Personalization levels."""
    BASIC = 'basic'
    STANDARD = 'standard'
    ADVANCED = 'advanced'
    PREMIUM = 'premium'
    
    CHOICES = [
        (BASIC, 'Basic Personalization'),
        (STANDARD, 'Standard Personalization'),
        (ADVANCED, 'Advanced Personalization'),
        (PREMIUM, 'Premium Personalization'),
    ]


class PersonalizationAlgorithm:
    """Personalization algorithms."""
    COLLABORATIVE = 'collaborative'
    CONTENT_BASED = 'content_based'
    HYBRID = 'hybrid'
    RULE_BASED = 'rule_based'
    MACHINE_LEARNING = 'machine_learning'
    
    CHOICES = [
        (COLLABORATIVE, 'Collaborative Filtering'),
        (CONTENT_BASED, 'Content-based'),
        (HYBRID, 'Hybrid Approach'),
        (RULE_BASED, 'Rule-based'),
        (MACHINE_LEARNING, 'Machine Learning'),
    ]


class ABTestVariant:
    """A/B test variants."""
    CONTROL = 'control'
    VARIANT_A = 'variant_a'
    VARIANT_B = 'variant_b'
    
    CHOICES = [
        (CONTROL, 'Control Group'),
        (VARIANT_A, 'Variant A'),
        (VARIANT_B, 'Variant B'),
    ]


class RoutingDecisionReason:
    """Reasons for routing decisions."""
    ROUTE_MATCH = 'route_match'
    CONDITION_EVALUATION = 'condition_evaluation'
    SCORE_CALCULATION = 'score_calculation'
    PERSONALIZATION = 'personalization'
    CAP_ENFORCEMENT = 'cap_enforcement'
    FALLBACK = 'fallback'
    AB_TEST = 'ab_test'
    CACHE_HIT = 'cache_hit'
    
    CHOICES = [
        (ROUTE_MATCH, 'Route Match'),
        (CONDITION_EVALUATION, 'Condition Evaluation'),
        (SCORE_CALCULATION, 'Score Calculation'),
        (PERSONALIZATION, 'Personalization'),
        (CAP_ENFORCEMENT, 'Cap Enforcement'),
        (FALLBACK, 'Fallback Rule'),
        (AB_TEST, 'A/B Test'),
        (CACHE_HIT, 'Cache Hit'),
    ]


class LogLevel:
    """Log levels for routing decisions."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    
    CHOICES = [
        (DEBUG, 'Debug'),
        (INFO, 'Info'),
        (WARNING, 'Warning'),
        (ERROR, 'Error'),
        (CRITICAL, 'Critical'),
    ]


class ComparisonOperator:
    """Comparison operators for analytics."""
    GREATER_THAN = '>'
    LESS_THAN = '<'
    EQUAL = '='
    NOT_EQUAL = '!='
    GREATER_EQUAL = '>='
    LESS_EQUAL = '<='
    
    CHOICES = [
        (GREATER_THAN, 'Greater Than'),
        (LESS_THAN, 'Less Than'),
        (EQUAL, 'Equal'),
        (NOT_EQUAL, 'Not Equal'),
        (GREATER_EQUAL, 'Greater or Equal'),
        (LESS_EQUAL, 'Less or Equal'),
    ]


class SortOrder:
    """Sort order options."""
    ASCENDING = 'asc'
    DESCENDING = 'desc'
    
    CHOICES = [
        (ASCENDING, 'Ascending'),
        (DESCENDING, 'Descending'),
    ]


class AggregationType:
    """Aggregation types for analytics."""
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    HOURLY = 'hourly'
    REAL_TIME = 'real_time'
    
    CHOICES = [
        (DAILY, 'Daily'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly'),
        (HOURLY, 'Hourly'),
        (REAL_TIME, 'Real-time'),
    ]


class EventType:
    """Event types for behavioral targeting."""
    PAGE_VIEW = 'page_view'
    CLICK = 'click'
    PURCHASE = 'purchase'
    ADD_TO_CART = 'add_to_cart'
    SEARCH = 'search'
    LOGIN = 'login'
    SIGNUP = 'signup'
    
    CHOICES = [
        (PAGE_VIEW, 'Page View'),
        (CLICK, 'Click'),
        (PURCHASE, 'Purchase'),
        (ADD_TO_CART, 'Add to Cart'),
        (SEARCH, 'Search'),
        (LOGIN, 'Login'),
        (SIGNUP, 'Signup'),
    ]


class OfferStatus:
    """Offer status for routing."""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    SCHEDULED = 'scheduled'
    EXPIRED = 'expired'
    PAUSED = 'paused'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (SCHEDULED, 'Scheduled'),
        (EXPIRED, 'Expired'),
        (PAUSED, 'Paused'),
    ]


class RoutingPriority:
    """Routing priority levels."""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    
    CHOICES = [
        (URGENT, 'Urgent'),
        (HIGH, 'High'),
        (NORMAL, 'Normal'),
        (LOW, 'Low'),
    ]


class PermissionLevel:
    """Permission levels for route access control."""
    READ = 'read'
    WRITE = 'write'
    ADMIN = 'admin'
    PUBLIC = 'public'
    CHOICES = [
        (READ, 'Read'),
        (WRITE, 'Write'),
        (ADMIN, 'Admin'),
        (PUBLIC, 'Public'),
    ]
