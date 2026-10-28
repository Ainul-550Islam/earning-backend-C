# api/admin_panel/choices.py
"""
Centralized choices for admin_panel models.
CPAlead-style earning platform admin choices.
"""


# ==================== Admin Activity Choices ====================

ADMIN_ACTION_TYPE_CHOICES = [
    ('user_ban', 'User Ban'),
    ('user_unban', 'User Unban'),
    ('user_verify', 'User Verify'),
    ('user_unverify', 'User Unverify'),
    ('payment_approve', 'Payment Approve'),
    ('payment_reject', 'Payment Reject'),
    ('content_delete', 'Content Delete'),
    ('content_create', 'Content Create'),
    ('content_update', 'Content Update'),
    ('setting_change', 'Setting Change'),
    ('feature_toggle', 'Feature Flag Toggle'),
    ('maintenance_enable', 'Maintenance Enable'),
    ('maintenance_disable', 'Maintenance Disable'),
    ('bulk_action', 'Bulk Action'),
    ('data_export', 'Data Export'),
    ('report_generate', 'Report Generate'),
    ('config_update', 'Config Update'),
    ('admin_login', 'Admin Login'),
    ('admin_logout', 'Admin Logout'),
    ('endpoint_toggle', 'Endpoint Toggle'),
    ('other', 'Other'),
]

ADMIN_ACTIVITY_STATUS_CHOICES = [
    ('success', 'Success'),
    ('failed', 'Failed'),
    ('partial', 'Partial'),
]

# ==================== Dashboard Choices ====================

WIDGET_TYPE_CHOICES = [
    ('stat_card', 'Stat Card'),
    ('line_chart', 'Line Chart'),
    ('bar_chart', 'Bar Chart'),
    ('pie_chart', 'Pie Chart'),
    ('donut_chart', 'Donut Chart'),
    ('area_chart', 'Area Chart'),
    ('table', 'Data Table'),
    ('recent_activity', 'Recent Activity'),
    ('quick_actions', 'Quick Actions'),
    ('calendar', 'Calendar'),
    ('map', 'Map'),
    ('funnel', 'Funnel Chart'),
    ('gauge', 'Gauge'),
    ('text', 'Text Block'),
    ('custom', 'Custom HTML'),
]

WIDGET_SIZE_CHOICES = [
    ('sm', 'Small (1/4)'),
    ('md', 'Medium (1/2)'),
    ('lg', 'Large (3/4)'),
    ('xl', 'Full Width'),
]

METRIC_PERIOD_CHOICES = [
    ('realtime', 'Real-time'),
    ('hourly', 'Hourly'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
    ('yearly', 'Yearly'),
    ('custom', 'Custom'),
]

ALERT_OPERATOR_CHOICES = [
    ('gt', 'Greater Than'),
    ('gte', 'Greater Than or Equal'),
    ('lt', 'Less Than'),
    ('lte', 'Less Than or Equal'),
    ('eq', 'Equal'),
    ('neq', 'Not Equal'),
]

# ==================== Session Choices ====================

SESSION_STATUS_CHOICES = [
    ('active', 'Active'),
    ('expired', 'Expired'),
    ('logged_out', 'Logged Out'),
    ('force_logout', 'Force Logged Out'),
]

# ==================== Config Choices ====================

CONFIG_VALUE_TYPE_CHOICES = [
    ('string', 'String'),
    ('integer', 'Integer'),
    ('float', 'Float'),
    ('boolean', 'Boolean'),
    ('json', 'JSON'),
    ('url', 'URL'),
    ('email', 'Email'),
    ('text', 'Text'),
    ('color', 'Color'),
    ('date', 'Date'),
    ('datetime', 'DateTime'),
]

CONFIG_GROUP_CHOICES = [
    ('general', 'General'),
    ('payment', 'Payment'),
    ('security', 'Security'),
    ('email', 'Email'),
    ('sms', 'SMS'),
    ('notification', 'Notification'),
    ('referral', 'Referral'),
    ('earning', 'Earning'),
    ('gamification', 'Gamification'),
    ('analytics', 'Analytics'),
    ('maintenance', 'Maintenance'),
    ('api', 'API'),
    ('social', 'Social'),
    ('legal', 'Legal'),
    ('advanced', 'Advanced'),
]

# ==================== Report Choices ====================

REPORT_TYPE_CHOICES = [
    ('user', 'User Report'),
    ('payment', 'Payment Report'),
    ('revenue', 'Revenue Report'),
    ('activity', 'Activity Report'),
    ('withdrawal', 'Withdrawal Report'),
    ('referral', 'Referral Report'),
    ('earning', 'Earning Report'),
    ('fraud', 'Fraud Report'),
    ('system', 'System Report'),
    ('custom', 'Custom Report'),
]

REPORT_FORMAT_CHOICES = [
    ('csv', 'CSV'),
    ('xlsx', 'Excel'),
    ('pdf', 'PDF'),
    ('json', 'JSON'),
]

REPORT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]

EXPORT_STATUS_CHOICES = [
    ('queued', 'Queued'),
    ('processing', 'Processing'),
    ('ready', 'Ready'),
    ('failed', 'Failed'),
    ('expired', 'Expired'),
]

INSIGHT_TYPE_CHOICES = [
    ('anomaly', 'Anomaly Detection'),
    ('trend', 'Trend Analysis'),
    ('recommendation', 'Recommendation'),
    ('alert', 'System Alert'),
    ('summary', 'Daily Summary'),
    ('prediction', 'Prediction'),
    ('performance', 'Performance'),
]

INSIGHT_PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]

# ==================== Notification Choices ====================

NOTIFICATION_TYPE_CHOICES = [
    ('INFO', 'Information'),
    ('SUCCESS', 'Success'),
    ('WARNING', 'Warning'),
    ('ERROR', 'Error'),
    ('MAINTENANCE', 'Maintenance'),
    ('UPDATE', 'Update'),
    ('PROMOTION', 'Promotion'),
]

SITE_CONTENT_TYPE_CHOICES = [
    ('PAGE', 'Page'),
    ('SECTION', 'Section'),
    ('BANNER', 'Banner'),
    ('FOOTER', 'Footer'),
    ('SIDEBAR', 'Sidebar'),
    ('POPUP', 'Popup'),
    ('FAQ', 'FAQ'),
    ('ANNOUNCEMENT', 'Announcement'),
]

# ==================== Maintenance Choices ====================

MAINTENANCE_TYPE_CHOICES = [
    ('scheduled', 'Scheduled Maintenance'),
    ('emergency', 'Emergency Maintenance'),
    ('upgrade', 'System Upgrade'),
    ('backup', 'Database Backup'),
]

# ==================== Cron Choices ====================

CRON_PRESETS = [
    ('*/5 * * * *', 'Every 5 Minutes'),
    ('*/15 * * * *', 'Every 15 Minutes'),
    ('*/30 * * * *', 'Every 30 Minutes'),
    ('0 * * * *', 'Every Hour'),
    ('0 */6 * * *', 'Every 6 Hours'),
    ('0 0 * * *', 'Daily at Midnight'),
    ('0 8 * * *', 'Daily at 8 AM'),
    ('0 0 * * 1', 'Weekly on Monday'),
    ('0 0 1 * *', 'Monthly on 1st'),
]

# ==================== Bulk Action Choices ====================

BULK_ACTION_CHOICES = [
    ('approve', 'Approve'),
    ('reject', 'Reject'),
    ('delete', 'Delete'),
    ('ban', 'Ban Users'),
    ('unban', 'Unban Users'),
    ('verify', 'Mark as Verified'),
    ('export', 'Export Selected'),
    ('send_notification', 'Send Notification'),
    ('reset_password', 'Reset Password'),
    ('activate', 'Activate'),
    ('deactivate', 'Deactivate'),
]

BULK_ACTION_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('completed', 'Completed'),
    ('partial', 'Partially Completed'),
    ('failed', 'Failed'),
]

# ==================== Admin Profile Choices ====================

ADMIN_ROLE_CHOICES = [
    ('superadmin', 'Super Admin'),
    ('admin', 'Admin'),
    ('moderator', 'Moderator'),
    ('support', 'Support Agent'),
    ('finance', 'Finance Manager'),
    ('analyst', 'Data Analyst'),
    ('viewer', 'Read-Only Viewer'),
]

ADMIN_THEME_CHOICES = [
    ('light', 'Light'),
    ('dark', 'Dark'),
    ('auto', 'System Default'),
]