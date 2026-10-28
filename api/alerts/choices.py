"""
Alert System Choices and Constants
This file contains all choice tuples and constants used throughout the alert system.
"""

# Alert Types
ALERT_TYPES = [
    ('high_earning', 'High Earning Activity'),
    ('mass_signup', 'Mass User Signup'),
    ('payment_spike', 'Payment Request Spike'),
    ('fraud_spike', 'Fraud Indicator Spike'),
    ('server_error', 'Server Error Rate'),
    ('low_balance', 'Low Advertiser Balance'),
    ('server_down', 'Server Down/Degraded'),
    ('offer_fraud', 'Offer Fraud Detected'),
    ('referral_abuse', 'Referral Program Abuse'),
    ('revenue_drop', 'Revenue Drop Alert'),
    ('payout_delay', 'Payout Processing Delay'),
    ('gateway_failure', 'Payment Gateway Failure'),
    ('high_churn', 'High User Churn Rate'),
    ('abuse_detected', 'System Abuse Detected'),
]

# Severity Levels
SEVERITY_LEVELS = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]

# Notification Types
NOTIFICATION_TYPES = [
    ('email', '📧 Email'),
    ('telegram', '📱 Telegram'),
    ('sms', '📲 SMS'),
    ('push', '📱 Push Notification'),
    ('webhook', '🌐 Webhook'),
    ('slack', '💬 Slack'),
    ('discord', '🎮 Discord'),
    ('pagerduty', '🚨 PagerDuty'),
    ('opsgenie', '🔔 OpsGenie'),
]

# Notification Status
NOTIFICATION_STATUS = [
    ('pending', '⏳ Pending'),
    ('sent', '[OK] Sent'),
    ('failed', '[ERROR] Failed'),
    ('delivered', '📨 Delivered'),
    ('read', '👁️ Read'),
]

# Alert Status
ALERT_STATUS = [
    ('active', 'Active'),
    ('resolved', 'Resolved'),
    ('escalated', 'Escalated'),
    ('suppressed', 'Suppressed'),
    ('archived', 'Archived'),
]

# Time Windows (minutes)
TIME_WINDOWS = [
    (5, '5 minutes'),
    (15, '15 minutes'),
    (30, '30 minutes'),
    (60, '1 hour'),
    (120, '2 hours'),
    (240, '4 hours'),
    (360, '6 hours'),
    (720, '12 hours'),
    (1440, '24 hours'),
]

# Cooldown Periods (minutes)
COOLDOWN_PERIODS = [
    (1, '1 minute'),
    (5, '5 minutes'),
    (15, '15 minutes'),
    (30, '30 minutes'),
    (60, '1 hour'),
    (120, '2 hours'),
    (240, '4 hours'),
]

# Escalation Levels
ESCALATION_LEVELS = [
    (1, 'Level 1 - First Response'),
    (2, 'Level 2 - Technical Team'),
    (3, 'Level 3 - Management'),
    (4, 'Level 4 - Executive'),
]

# Threshold Types
THRESHOLD_TYPES = [
    ('absolute', 'Absolute Value'),
    ('percentage', 'Percentage'),
    ('deviation', 'Standard Deviation'),
    ('rolling', 'Rolling Average'),
]

# Schedule Types
SCHEDULE_TYPES = [
    ('recurring', 'Recurring'),
    ('one_time', 'One Time'),
    ('maintenance', 'Maintenance Window'),
]

# Suppression Types
SUPPRESSION_TYPES = [
    ('temporal', 'Temporal'),
    ('conditional', 'Conditional'),
    ('global', 'Global'),
]

# Health Check Status
HEALTH_CHECK_STATUS = [
    ('healthy', '✅ Healthy'),
    ('degraded', '⚠️ Degraded'),
    ('unhealthy', '❌ Unhealthy'),
    ('unknown', '❓ Unknown'),
]

# Incident Status
INCIDENT_STATUS = [
    ('investigating', '🔍 Investigating'),
    ('identified', '📋 Identified'),
    ('monitoring', '👀 Monitoring'),
    ('resolved', '✅ Resolved'),
    ('post_mortem', '📊 Post Mortem'),
]

# On-Call Schedule Types
ONCALL_SCHEDULE_TYPES = [
    ('rotation', 'Rotation'),
    ('fixed', 'Fixed Schedule'),
    ('follow_the_sun', 'Follow the Sun'),
]

# Channel Health Status
CHANNEL_HEALTH_STATUS = [
    ('healthy', '✅ Healthy'),
    ('degraded', '⚠️ Degraded'),
    ('unhealthy', '❌ Unhealthy'),
    ('disabled', '🚫 Disabled'),
]

# Alert Rule Filter Fields
FILTER_FIELDS = [
    ('alert_type', 'Alert Type'),
    ('severity', 'Severity'),
    ('is_active', 'Active Status'),
    ('created_by', 'Created By'),
    ('created_at', 'Created Date'),
    ('last_triggered', 'Last Triggered'),
]

# Export Formats
EXPORT_FORMATS = [
    ('json', 'JSON'),
    ('csv', 'CSV'),
    ('xlsx', 'Excel'),
    ('pdf', 'PDF'),
]

# Report Types
REPORT_TYPES = [
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('yearly', 'Yearly'),
    ('custom', 'Custom'),
]