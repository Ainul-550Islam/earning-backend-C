"""
Tenant Tasks Module

This module contains all Celery tasks for the tenant management system,
including background jobs for metrics collection, billing, notifications,
and maintenance operations.
"""

from .billing import (
    generate_monthly_invoices,
    process_dunning_workflow,
    send_payment_reminders,
    calculate_commission_payments,
)

from .metrics import (
    collect_daily_metrics,
    collect_weekly_metrics,
    collect_monthly_metrics,
    calculate_health_scores,
    cleanup_old_metrics,
)

from .notifications import (
    send_onboarding_reminders,
    send_trial_expiry_notifications,
    send_quota_exceeded_notifications,
    send_security_alerts,
    process_email_queue,
)

from .maintenance import (
    cleanup_expired_api_keys,
    cleanup_expired_feature_flags,
    renew_ssl_certificates,
    backup_tenant_data,
    archive_audit_logs,
)

from .monitoring import (
    monitor_ssl_expiry,
    check_disk_usage,
    monitor_api_usage,
    generate_system_health_report,
)

from .onboarding import (
    complete_onboarding_steps,
    send_welcome_emails,
    schedule_trial_extensions,
)

__all__ = [
    # Billing tasks
    'generate_monthly_invoices',
    'process_dunning_workflow',
    'send_payment_reminders',
    'calculate_commission_payments',
    
    # Metrics tasks
    'collect_daily_metrics',
    'collect_weekly_metrics',
    'collect_monthly_metrics',
    'calculate_health_scores',
    'cleanup_old_metrics',
    
    # Notification tasks
    'send_onboarding_reminders',
    'send_trial_expiry_notifications',
    'send_quota_exceeded_notifications',
    'send_security_alerts',
    'process_email_queue',
    
    # Maintenance tasks
    'cleanup_expired_api_keys',
    'cleanup_expired_feature_flags',
    'renew_ssl_certificates',
    'backup_tenant_data',
    'archive_audit_logs',
    
    # Monitoring tasks
    'monitor_ssl_expiry',
    'check_disk_usage',
    'monitor_api_usage',
    'generate_system_health_report',
    
    # Onboarding tasks
    'complete_onboarding_steps',
    'send_welcome_emails',
    'schedule_trial_extensions',
]
