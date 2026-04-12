from django.db import models


class SmartLinkType(models.TextChoices):
    GENERAL = 'general', 'General'
    GEO_SPECIFIC = 'geo_specific', 'Geo Specific'
    DEVICE_SPECIFIC = 'device_specific', 'Device Specific'
    OFFER_SPECIFIC = 'offer_specific', 'Offer Specific'
    AB_TEST = 'ab_test', 'A/B Test'
    CAMPAIGN = 'campaign', 'Campaign'


class DeviceType(models.TextChoices):
    MOBILE = 'mobile', 'Mobile'
    TABLET = 'tablet', 'Tablet'
    DESKTOP = 'desktop', 'Desktop'
    UNKNOWN = 'unknown', 'Unknown'


class OSType(models.TextChoices):
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'
    WINDOWS = 'windows', 'Windows'
    MAC = 'mac', 'macOS'
    LINUX = 'linux', 'Linux'
    UNKNOWN = 'unknown', 'Unknown'


class BrowserType(models.TextChoices):
    CHROME = 'chrome', 'Chrome'
    FIREFOX = 'firefox', 'Firefox'
    SAFARI = 'safari', 'Safari'
    EDGE = 'edge', 'Edge'
    OPERA = 'opera', 'Opera'
    OTHER = 'other', 'Other'


class TargetingMode(models.TextChoices):
    WHITELIST = 'whitelist', 'Whitelist'
    BLACKLIST = 'blacklist', 'Blacklist'


class RotationMethod(models.TextChoices):
    WEIGHTED = 'weighted', 'Weighted Random'
    ROUND_ROBIN = 'round_robin', 'Round Robin'
    EPC_OPTIMIZED = 'epc_optimized', 'EPC Optimized'
    PRIORITY = 'priority', 'Priority Based'


class RedirectType(models.TextChoices):
    HTTP_302 = '302', 'HTTP 302 (Temporary)'
    HTTP_301 = '301', 'HTTP 301 (Permanent)'
    META_REFRESH = 'meta', 'Meta Refresh'
    JAVASCRIPT = 'js', 'JavaScript Redirect'


class ABTestStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    RUNNING = 'running', 'Running'
    PAUSED = 'paused', 'Paused'
    COMPLETED = 'completed', 'Completed'
    WINNER_FOUND = 'winner_found', 'Winner Found'


class FraudAction(models.TextChoices):
    ALLOW = 'allow', 'Allow'
    BLOCK = 'block', 'Block'
    FLAG = 'flag', 'Flag for Review'
    REDIRECT_FALLBACK = 'redirect_fallback', 'Redirect to Fallback'


class DomainVerificationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'


class CapPeriod(models.TextChoices):
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    TOTAL = 'total', 'Total (Lifetime)'


class DayOfWeek(models.IntegerChoices):
    MONDAY = 0, 'Monday'
    TUESDAY = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY = 3, 'Thursday'
    FRIDAY = 4, 'Friday'
    SATURDAY = 5, 'Saturday'
    SUNDAY = 6, 'Sunday'
