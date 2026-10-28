# api/admin_panel/enums.py
"""
Django TextChoices / IntegerChoices enums for admin_panel.
Use these in model field definitions for type safety.
"""
from django.db import models


class AdminRole(models.TextChoices):
    SUPERADMIN = 'superadmin', 'Super Admin'
    ADMIN = 'admin', 'Admin'
    MODERATOR = 'moderator', 'Moderator'
    SUPPORT = 'support', 'Support Agent'
    FINANCE = 'finance', 'Finance Manager'
    ANALYST = 'analyst', 'Data Analyst'
    VIEWER = 'viewer', 'Read-Only Viewer'


class AdminTheme(models.TextChoices):
    LIGHT = 'light', 'Light'
    DARK = 'dark', 'Dark'
    AUTO = 'auto', 'System Default'


class WidgetType(models.TextChoices):
    STAT_CARD = 'stat_card', 'Stat Card'
    LINE_CHART = 'line_chart', 'Line Chart'
    BAR_CHART = 'bar_chart', 'Bar Chart'
    PIE_CHART = 'pie_chart', 'Pie Chart'
    DONUT_CHART = 'donut_chart', 'Donut Chart'
    AREA_CHART = 'area_chart', 'Area Chart'
    TABLE = 'table', 'Data Table'
    RECENT_ACTIVITY = 'recent_activity', 'Recent Activity'
    QUICK_ACTIONS = 'quick_actions', 'Quick Actions'
    CALENDAR = 'calendar', 'Calendar'
    MAP = 'map', 'Map'
    FUNNEL = 'funnel', 'Funnel Chart'
    GAUGE = 'gauge', 'Gauge'
    TEXT = 'text', 'Text Block'
    CUSTOM = 'custom', 'Custom HTML'


class WidgetSize(models.TextChoices):
    SM = 'sm', 'Small (1/4)'
    MD = 'md', 'Medium (1/2)'
    LG = 'lg', 'Large (3/4)'
    XL = 'xl', 'Full Width'


class MetricPeriod(models.TextChoices):
    REALTIME = 'realtime', 'Real-time'
    HOURLY = 'hourly', 'Hourly'
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    YEARLY = 'yearly', 'Yearly'
    CUSTOM = 'custom', 'Custom'


class AlertOperator(models.TextChoices):
    GT = 'gt', 'Greater Than'
    GTE = 'gte', 'Greater Than or Equal'
    LT = 'lt', 'Less Than'
    LTE = 'lte', 'Less Than or Equal'
    EQ = 'eq', 'Equal'
    NEQ = 'neq', 'Not Equal'


class ActivityStatus(models.TextChoices):
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    PARTIAL = 'partial', 'Partial'


class SessionStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    LOGGED_OUT = 'logged_out', 'Logged Out'
    FORCE_LOGOUT = 'force_logout', 'Force Logged Out'


class ConfigValueType(models.TextChoices):
    STRING = 'string', 'String'
    INTEGER = 'integer', 'Integer'
    FLOAT = 'float', 'Float'
    BOOLEAN = 'boolean', 'Boolean'
    JSON = 'json', 'JSON'
    URL = 'url', 'URL'
    EMAIL = 'email', 'Email'
    TEXT = 'text', 'Text'
    COLOR = 'color', 'Color'
    DATE = 'date', 'Date'
    DATETIME = 'datetime', 'DateTime'


class ConfigGroup(models.TextChoices):
    GENERAL = 'general', 'General'
    PAYMENT = 'payment', 'Payment'
    SECURITY = 'security', 'Security'
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'
    NOTIFICATION = 'notification', 'Notification'
    REFERRAL = 'referral', 'Referral'
    EARNING = 'earning', 'Earning'
    GAMIFICATION = 'gamification', 'Gamification'
    ANALYTICS = 'analytics', 'Analytics'
    MAINTENANCE = 'maintenance', 'Maintenance'
    API = 'api', 'API'
    SOCIAL = 'social', 'Social'
    LEGAL = 'legal', 'Legal'
    ADVANCED = 'advanced', 'Advanced'


class ReportType(models.TextChoices):
    USER = 'user', 'User Report'
    PAYMENT = 'payment', 'Payment Report'
    REVENUE = 'revenue', 'Revenue Report'
    ACTIVITY = 'activity', 'Activity Report'
    WITHDRAWAL = 'withdrawal', 'Withdrawal Report'
    REFERRAL = 'referral', 'Referral Report'
    EARNING = 'earning', 'Earning Report'
    FRAUD = 'fraud', 'Fraud Report'
    SYSTEM = 'system', 'System Report'
    CUSTOM = 'custom', 'Custom Report'


class ReportFormat(models.TextChoices):
    CSV = 'csv', 'CSV'
    XLSX = 'xlsx', 'Excel'
    PDF = 'pdf', 'PDF'
    JSON = 'json', 'JSON'


class ReportStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class ExportStatus(models.TextChoices):
    QUEUED = 'queued', 'Queued'
    PROCESSING = 'processing', 'Processing'
    READY = 'ready', 'Ready'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'


class InsightType(models.TextChoices):
    ANOMALY = 'anomaly', 'Anomaly Detection'
    TREND = 'trend', 'Trend Analysis'
    RECOMMENDATION = 'recommendation', 'Recommendation'
    ALERT = 'alert', 'System Alert'
    SUMMARY = 'summary', 'Daily Summary'
    PREDICTION = 'prediction', 'Prediction'
    PERFORMANCE = 'performance', 'Performance'


class InsightPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'


class BulkActionType(models.TextChoices):
    APPROVE = 'approve', 'Approve'
    REJECT = 'reject', 'Reject'
    DELETE = 'delete', 'Delete'
    BAN = 'ban', 'Ban Users'
    UNBAN = 'unban', 'Unban Users'
    VERIFY = 'verify', 'Mark as Verified'
    EXPORT = 'export', 'Export Selected'
    SEND_NOTIFICATION = 'send_notification', 'Send Notification'
    RESET_PASSWORD = 'reset_password', 'Reset Password'
    ACTIVATE = 'activate', 'Activate'
    DEACTIVATE = 'deactivate', 'Deactivate'


class BulkActionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    PARTIAL = 'partial', 'Partially Completed'
    FAILED = 'failed', 'Failed'


class MaintenanceType(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled Maintenance'
    EMERGENCY = 'emergency', 'Emergency Maintenance'
    UPGRADE = 'upgrade', 'System Upgrade'
    BACKUP = 'backup', 'Database Backup'


class NotificationType(models.TextChoices):
    INFO = 'INFO', 'Information'
    SUCCESS = 'SUCCESS', 'Success'
    WARNING = 'WARNING', 'Warning'
    ERROR = 'ERROR', 'Error'
    MAINTENANCE = 'MAINTENANCE', 'Maintenance'
    UPDATE = 'UPDATE', 'Update'
    PROMOTION = 'PROMOTION', 'Promotion'


class SiteContentType(models.TextChoices):
    PAGE = 'PAGE', 'Page'
    SECTION = 'SECTION', 'Section'
    BANNER = 'BANNER', 'Banner'
    FOOTER = 'FOOTER', 'Footer'
    SIDEBAR = 'SIDEBAR', 'Sidebar'
    POPUP = 'POPUP', 'Popup'
    FAQ = 'FAQ', 'FAQ'
    ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'