"""
Rate Limit Choices

Choice definitions for rate limiting module.
"""

from django.utils.translation import gettext_lazy as _


class LimitType:
    """
    Rate limit types for different limiting strategies.
    """
    PER_MINUTE = 'per_minute'
    PER_HOUR = 'per_hour'
    PER_DAY = 'per_day'
    PER_IP = 'per_ip'
    PER_USER = 'per_user'
    PER_ENDPOINT = 'per_endpoint'
    PER_GLOBAL = 'per_global'
    PER_REFERRAL = 'per_referral'
    PER_TASK = 'per_task'
    PER_OFFER = 'per_offer'
    PER_WITHDRAWAL = 'per_withdrawal'
    
    CHOICES = [
        (PER_MINUTE, _('Per Minute')),
        (PER_HOUR, _('Per Hour')),
        (PER_DAY, _('Per Day')),
        (PER_IP, _('Per IP')),
        (PER_USER, _('Per User')),
        (PER_ENDPOINT, _('Per Endpoint')),
        (PER_GLOBAL, _('Per Global')),
        (PER_REFERRAL, _('Per Referral')),
        (PER_TASK, _('Per Task')),
        (PER_OFFER, _('Per Offer')),
        (PER_WITHDRAWAL, _('Per Withdrawal')),
    ]
    
    # Grouped choices for better organization
    TIME_BASED = [
        (PER_MINUTE, _('Per Minute')),
        (PER_HOUR, _('Per Hour')),
        (PER_DAY, _('Per Day')),
    ]
    
    ENTITY_BASED = [
        (PER_IP, _('Per IP')),
        (PER_USER, _('Per User')),
        (PER_ENDPOINT, _('Per Endpoint')),
        (PER_GLOBAL, _('Per Global')),
    ]
    
    EARNING_APP = [
        (PER_REFERRAL, _('Per Referral')),
        (PER_TASK, _('Per Task')),
        (PER_OFFER, _('Per Offer')),
        (PER_WITHDRAWAL, _('Per Withdrawal')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a limit type."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def is_time_based(cls, value):
        """Check if limit type is time-based."""
        return value in [choice[0] for choice in cls.TIME_BASED]
    
    @classmethod
    def is_entity_based(cls, value):
        """Check if limit type is entity-based."""
        return value in [choice[0] for choice in cls.ENTITY_BASED]
    
    @classmethod
    def is_earning_app(cls, value):
        """Check if limit type is for earning app."""
        return value in [choice[0] for choice in cls.EARNING_APP]


class ThrottleAction:
    """
    Actions to take when rate limit is exceeded.
    """
    BLOCK = 'block'
    THROTTLE = 'throttle'
    WARN = 'warn'
    LOG_ONLY = 'log_only'
    DELAY = 'delay'
    CAPTCHA = 'captcha'
    REDUCE_PRIVILEGES = 'reduce_privileges'
    TEMPORARY_SUSPEND = 'temporary_suspend'
    
    CHOICES = [
        (BLOCK, _('Block Request')),
        (THROTTLE, _('Throttle/Slow Down')),
        (WARN, _('Warning Only')),
        (LOG_ONLY, _('Log Only')),
        (DELAY, _('Add Delay')),
        (CAPTCHA, _('Require CAPTCHA')),
        (REDUCE_PRIVILEGES, _('Reduce Privileges')),
        (TEMPORARY_SUSPEND, _('Temporary Suspend')),
    ]
    
    # Severity levels for actions
    LOW_SEVERITY = [
        (LOG_ONLY, _('Log Only')),
        (WARN, _('Warning Only')),
    ]
    
    MEDIUM_SEVERITY = [
        (THROTTLE, _('Throttle/Slow Down')),
        (DELAY, _('Add Delay')),
        (CAPTCHA, _('Require CAPTCHA')),
    ]
    
    HIGH_SEVERITY = [
        (BLOCK, _('Block Request')),
        (REDUCE_PRIVILEGES, _('Reduce Privileges')),
        (TEMPORARY_SUSPEND, _('Temporary Suspend')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a throttle action."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def get_severity(cls, value):
        """Get severity level for an action."""
        if value in [choice[0] for choice in cls.LOW_SEVERITY]:
            return 'low'
        elif value in [choice[0] for choice in cls.MEDIUM_SEVERITY]:
            return 'medium'
        elif value in [choice[0] for choice in cls.HIGH_SEVERITY]:
            return 'high'
        return 'unknown'
    
    @classmethod
    def is_blocking(cls, value):
        """Check if action blocks the request."""
        return value in [cls.BLOCK, cls.TEMPORARY_SUSPEND]
    
    @classmethod
    def is_degrading(cls, value):
        """Check if action degrades user experience."""
        return value in [cls.THROTTLE, cls.DELAY, cls.CAPTCHA, cls.REDUCE_PRIVILEGES]


class BackoffStrategy:
    """
    Backoff strategies for rate limiting.
    """
    FIXED = 'fixed'
    LINEAR = 'linear'
    EXPONENTIAL = 'exponential'
    FIBONACCI = 'fibonacci'
    ADAPTIVE = 'adaptive'
    RANDOM_JITTER = 'random_jitter'
    GRADUAL = 'gradual'
    
    CHOICES = [
        (FIXED, _('Fixed Delay')),
        (LINEAR, _('Linear Backoff')),
        (EXPONENTIAL, _('Exponential Backoff')),
        (FIBONACCI, _('Fibonacci Backoff')),
        (ADAPTIVE, _('Adaptive Backoff')),
        (RANDOM_JITTER, _('Random Jitter')),
        (GRADUAL, _('Gradual Backoff')),
    ]
    
    # Strategy categories
    SIMPLE = [
        (FIXED, _('Fixed Delay')),
        (LINEAR, _('Linear Backoff')),
    ]
    
    ADVANCED = [
        (EXPONENTIAL, _('Exponential Backoff')),
        (FIBONACCI, _('Fibonacci Backoff')),
        (ADAPTIVE, _('Adaptive Backoff')),
    ]
    
    JITTER_BASED = [
        (RANDOM_JITTER, _('Random Jitter')),
        (GRADUAL, _('Gradual Backoff')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a backoff strategy."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def calculate_delay(cls, strategy, attempt, base_delay=1, max_delay=300, multiplier=2):
        """
        Calculate delay based on strategy and attempt number.
        
        Args:
            strategy: Backoff strategy
            attempt: Current attempt number (starting from 1)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Multiplier for exponential/linear growth
            
        Returns:
            float: Calculated delay in seconds
        """
        import random
        import math
        
        if strategy == cls.FIXED:
            return base_delay
        
        elif strategy == cls.LINEAR:
            return min(base_delay * attempt, max_delay)
        
        elif strategy == cls.EXPONENTIAL:
            return min(base_delay * (multiplier ** (attempt - 1)), max_delay)
        
        elif strategy == cls.FIBONACCI:
            # Fibonacci sequence: 1, 1, 2, 3, 5, 8, 13, 21, ...
            def fibonacci(n):
                if n <= 1:
                    return n
                a, b = 0, 1
                for _ in range(2, n + 1):
                    a, b = b, a + b
                return b
            
            return min(base_delay * fibonacci(attempt), max_delay)
        
        elif strategy == cls.ADAPTIVE:
            # Adaptive based on success rate (simplified)
            success_rate = getattr(adaptive_backoff_cache, 'success_rate', 0.5)
            if success_rate > 0.8:
                return min(base_delay * 0.5, max_delay)  # Reduce delay on high success
            elif success_rate < 0.2:
                return min(base_delay * 2, max_delay)   # Increase delay on low success
            else:
                return base_delay
        
        elif strategy == cls.RANDOM_JITTER:
            # Exponential with random jitter
            exp_delay = min(base_delay * (multiplier ** (attempt - 1)), max_delay)
            jitter = random.uniform(0.1, 0.3) * exp_delay
            return exp_delay + jitter
        
        elif strategy == cls.GRADUAL:
            # Gradual increase with diminishing returns
            return min(base_delay * math.log(attempt + 1), max_delay)
        
        return base_delay


class AbuseType:
    """
    Types of abuse detected by the system.
    """
    RATE_LIMIT = 'rate_limit'
    SPAM = 'spam'
    FRAUD = 'fraud'
    MALICIOUS = 'malicious'
    BOT = 'bot'
    SCRAPING = 'scraping'
    BRUTE_FORCE = 'brute_force'
    DDOS = 'ddos'
    SUSPICIOUS_PATTERN = 'suspicious_pattern'
    OTHER = 'other'
    
    CHOICES = [
        (RATE_LIMIT, _('Rate Limit Violation')),
        (SPAM, _('Spam')),
        (FRAUD, _('Fraud')),
        (MALICIOUS, _('Malicious Activity')),
        (BOT, _('Bot Activity')),
        (SCRAPING, _('Web Scraping')),
        (BRUTE_FORCE, _('Brute Force')),
        (DDOS, _('DDoS Attack')),
        (SUSPICIOUS_PATTERN, _('Suspicious Pattern')),
        (OTHER, _('Other')),
    ]
    
    # Severity levels for abuse types
    LOW_SEVERITY = [
        (RATE_LIMIT, _('Rate Limit Violation')),
        (SUSPICIOUS_PATTERN, _('Suspicious Pattern')),
        (OTHER, _('Other')),
    ]
    
    MEDIUM_SEVERITY = [
        (SPAM, _('Spam')),
        (BOT, _('Bot Activity')),
        (SCRAPING, _('Web Scraping')),
    ]
    
    HIGH_SEVERITY = [
        (FRAUD, _('Fraud')),
        (MALICIOUS, _('Malicious Activity')),
        (BRUTE_FORCE, _('Brute Force')),
        (DDOS, _('DDoS Attack')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for an abuse type."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def get_severity_level(cls, value):
        """Get severity level for an abuse type."""
        if value in [choice[0] for choice in cls.LOW_SEVERITY]:
            return 1
        elif value in [choice[0] for choice in cls.MEDIUM_SEVERITY]:
            return 3
        elif value in [choice[0] for choice in cls.HIGH_SEVERITY]:
            return 5
        return 2


class BlockReason:
    """
    Reasons for IP blocking.
    """
    MANUAL = 'manual'
    ABUSE = 'abuse'
    RATE_LIMIT = 'rate_limit'
    SECURITY = 'security'
    POLICY = 'policy'
    MALWARE = 'malware'
    SUSPICIOUS = 'suspicious'
    AUTO_DETECTION = 'auto_detection'
    USER_REPORT = 'user_report'
    SYSTEM_DETECTION = 'system_detection'
    
    CHOICES = [
        (MANUAL, _('Manual Block')),
        (ABUSE, _('Abuse Detection')),
        (RATE_LIMIT, _('Rate Limit Violation')),
        (SECURITY, _('Security Threat')),
        (POLICY, _('Policy Violation')),
        (MALWARE, _('Malware Detection')),
        (SUSPICIOUS, _('Suspicious Activity')),
        (AUTO_DETECTION, _('Auto Detection')),
        (USER_REPORT, _('User Report')),
        (SYSTEM_DETECTION, _('System Detection')),
    ]
    
    # Categories of block reasons
    AUTOMATIC = [
        (ABUSE, _('Abuse Detection')),
        (RATE_LIMIT, _('Rate Limit Violation')),
        (MALWARE, _('Malware Detection')),
        (AUTO_DETECTION, _('Auto Detection')),
        (SYSTEM_DETECTION, _('System Detection')),
    ]
    
    MANUAL = [
        (MANUAL, _('Manual Block')),
        (SECURITY, _('Security Threat')),
        (POLICY, _('Policy Violation')),
        (USER_REPORT, _('User Report')),
    ]
    
    DETECTION_BASED = [
        (SUSPICIOUS, _('Suspicious Activity')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a block reason."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def is_automatic(cls, value):
        """Check if block reason is automatic."""
        return value in [choice[0] for choice in cls.AUTOMATIC]
    
    @classmethod
    def is_manual(cls, value):
        """Check if block reason is manual."""
        return value in [choice[0] for choice in cls.MANUAL]


class BlockType:
    """
    Types of IP blocking.
    """
    SINGLE = 'single'
    RANGE = 'range'
    SUBNET = 'subnet'
    COUNTRY = 'country'
    ASN = 'asn'
    WILDCARD = 'wildcard'
    
    CHOICES = [
        (SINGLE, _('Single IP')),
        (RANGE, _('IP Range')),
        (SUBNET, _('Subnet/CIDR')),
        (COUNTRY, _('Country')),
        (ASN, _('ASN')),
        (WILDCARD, _('Wildcard')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a block type."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value


class ExceptionType:
    """
    Types of rate limit exceptions.
    """
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'
    BYPASS = 'bypass'
    INCREASED_LIMIT = 'increased_limit'
    DECREASED_LIMIT = 'decreased_limit'
    NO_LIMIT = 'no_limit'
    CUSTOM_LIMIT = 'custom_limit'
    
    CHOICES = [
        (WHITELIST, _('Whitelist')),
        (BLACKLIST, _('Blacklist')),
        (BYPASS, _('Bypass')),
        (INCREASED_LIMIT, _('Increased Limit')),
        (DECREASED_LIMIT, _('Decreased Limit')),
        (NO_LIMIT, _('No Limit')),
        (CUSTOM_LIMIT, _('Custom Limit')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for an exception type."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value


class LogLevel:
    """
    Log levels for rate limiting.
    """
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    SECURITY = 'security'
    
    CHOICES = [
        (DEBUG, _('Debug')),
        (INFO, _('Info')),
        (WARNING, _('Warning')),
        (ERROR, _('Error')),
        (CRITICAL, _('Critical')),
        (SECURITY, _('Security')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a log level."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value


class HealthStatus:
    """
    Health status indicators.
    """
    EXCELLENT = 'excellent'
    GOOD = 'good'
    FAIR = 'fair'
    POOR = 'poor'
    CRITICAL = 'critical'
    
    CHOICES = [
        (EXCELLENT, _('Excellent')),
        (GOOD, _('Good')),
        (FAIR, _('Fair')),
        (POOR, _('Poor')),
        (CRITICAL, _('Critical')),
    ]
    
    # Numeric ranges for health status
    RANGES = {
        EXCELLENT: (80, 100),
        GOOD: (60, 79),
        FAIR: (40, 59),
        POOR: (20, 39),
        CRITICAL: (0, 19),
    }
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for a health status."""
        for choice_value, display_name in cls.CHOICES:
            if choice_value == value:
                return display_name
        return value
    
    @classmethod
    def from_score(cls, score):
        """Get health status from numeric score."""
        for status, (min_score, max_score) in cls.RANGES.items():
            if min_score <= score <= max_score:
                return status
        return cls.POOR


# Cache for adaptive backoff strategy
class AdaptiveBackoffCache:
    """Simple cache for adaptive backoff strategy."""
    def __init__(self):
        self.success_rate = 0.5
        self.total_requests = 0
        self.successful_requests = 0
    
    def update_success_rate(self, success):
        """Update success rate based on request result."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        self.success_rate = self.successful_requests / self.total_requests

# Global instance
adaptive_backoff_cache = AdaptiveBackoffCache()
