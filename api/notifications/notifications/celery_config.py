# api/notifications/celery_config.py
"""
Celery configuration for the notifications system.

Add to Django settings.py:
    from api.notifications.celery_config import (
        NOTIFICATION_TASK_ROUTES,
        NOTIFICATION_QUEUES,
        NOTIFICATION_QUEUE_CONFIG,
    )
    CELERY_TASK_ROUTES = {**CELERY_TASK_ROUTES, **NOTIFICATION_TASK_ROUTES}
"""

# ---------------------------------------------------------------------------
# Task Routes — maps task names to queues
# ---------------------------------------------------------------------------
NOTIFICATION_TASK_ROUTES = {
    # High priority — real-time sends
    'notifications.send_push_batch':                    {'queue': 'notifications_push'},
    'notifications.send_push_multicast':                {'queue': 'notifications_push'},
    'notifications.send_email_batch':                   {'queue': 'notifications_email'},
    'notifications.send_bulk_email':                    {'queue': 'notifications_email'},
    'notifications.send_sms_batch':                     {'queue': 'notifications_sms'},
    'notifications.send_bulk_sms':                      {'queue': 'notifications_sms'},

    # Campaign tasks
    'notifications.process_campaign':                   {'queue': 'notifications_campaigns'},
    'notifications.start_scheduled_campaigns':          {'queue': 'notifications_campaigns'},
    'notifications.check_campaign_completion':          {'queue': 'notifications_campaigns'},
    'notifications.update_all_campaign_results':        {'queue': 'notifications_campaigns'},
    'notifications.send_batch_chunk':                   {'queue': 'notifications_batch'},
    'notifications.process_batch':                      {'queue': 'notifications_batch'},
    'notifications.finalize_batch':                     {'queue': 'notifications_batch'},
    'notifications.cancel_batch':                       {'queue': 'notifications_batch'},

    # A/B Testing
    'notifications.evaluate_ab_test':                   {'queue': 'notifications_campaigns'},
    'notifications.evaluate_all_pending_ab_tests':      {'queue': 'notifications_campaigns'},

    # Retry tasks
    'notifications.retry_notification':                 {'queue': 'notifications_retry'},
    'notifications.process_all_retries':                {'queue': 'notifications_retry'},
    'notifications.retry_failed_queue_entries':         {'queue': 'notifications_retry'},

    # Scheduling
    'notifications.send_scheduled_notifications':       {'queue': 'notifications_scheduled'},
    'notifications.cancel_overdue_schedules':           {'queue': 'notifications_scheduled'},
    'notifications.schedule_notification':              {'queue': 'notifications_scheduled'},

    # Delivery tracking
    'notifications.poll_delivery_status':               {'queue': 'notifications_tracking'},
    'notifications.update_campaign_results':            {'queue': 'notifications_tracking'},
    'notifications.update_all_campaign_results':        {'queue': 'notifications_tracking'},
    'notifications.process_sendgrid_events':            {'queue': 'notifications_tracking'},
    'notifications.process_twilio_webhook':             {'queue': 'notifications_tracking'},
    'notifications.mark_notification_delivered':        {'queue': 'notifications_tracking'},
    'notifications.mark_notification_read':             {'queue': 'notifications_tracking'},
    'notifications.mark_notification_clicked':          {'queue': 'notifications_tracking'},
    'notifications.process_push_delivery_receipt':      {'queue': 'notifications_tracking'},

    # Opt-out / unsubscribe
    'notifications.process_unsubscribe_request':        {'queue': 'notifications_optout'},
    'notifications.process_bulk_unsubscribe':           {'queue': 'notifications_optout'},
    'notifications.sync_sendgrid_unsubscribes':         {'queue': 'notifications_optout'},
    'notifications.process_one_click_unsubscribe':      {'queue': 'notifications_optout'},
    'notifications.cleanup_old_opt_out_records':        {'queue': 'notifications_optout'},

    # Analytics
    'notifications.run_all_daily_analytics':            {'queue': 'notifications_analytics'},
    'notifications.generate_daily_insights':            {'queue': 'notifications_analytics'},
    'notifications.generate_weekly_summary':            {'queue': 'notifications_analytics'},
    'notifications.refresh_delivery_rates':             {'queue': 'notifications_analytics'},
    'notifications.backfill_insights':                  {'queue': 'notifications_analytics'},
    'notifications.generate_legacy_daily_analytics':    {'queue': 'notifications_analytics'},

    # Maintenance / cleanup
    'notifications.run_all_cleanup':                    {'queue': 'notifications_maintenance'},
    'notifications.cleanup_expired_notifications':      {'queue': 'notifications_maintenance'},
    'notifications.cleanup_old_notifications':          {'queue': 'notifications_maintenance'},
    'notifications.cleanup_old_delivery_logs':          {'queue': 'notifications_maintenance'},
    'notifications.cleanup_stale_queue_entries':        {'queue': 'notifications_maintenance'},
    'notifications.cleanup_old_retry_records':          {'queue': 'notifications_maintenance'},
    'notifications.cleanup_read_in_app_messages':       {'queue': 'notifications_maintenance'},
    'notifications.cleanup_expired_in_app_messages':    {'queue': 'notifications_maintenance'},
    'notifications.cleanup_old_schedules':              {'queue': 'notifications_maintenance'},

    # Fatigue management
    'notifications.reset_daily_fatigue_counters':       {'queue': 'notifications_maintenance'},
    'notifications.reset_weekly_fatigue_counters':      {'queue': 'notifications_maintenance'},
    'notifications.reset_monthly_fatigue_counters':     {'queue': 'notifications_maintenance'},
    'notifications.recalculate_fatigue_flags':          {'queue': 'notifications_maintenance'},
    'notifications.clear_user_fatigue':                 {'queue': 'notifications_maintenance'},
    'notifications.create_missing_fatigue_records':     {'queue': 'notifications_maintenance'},

    # Token management
    'notifications.refresh_stale_fcm_tokens':           {'queue': 'notifications_maintenance'},
    'notifications.cleanup_inactive_devices':           {'queue': 'notifications_maintenance'},
    'notifications.deactivate_duplicate_tokens':        {'queue': 'notifications_maintenance'},
    'notifications.deactivate_invalid_push_devices':    {'queue': 'notifications_maintenance'},

    # Workflow + background jobs
    'notifications.execute_workflow':              {'queue': 'notifications_campaigns'},
    'notifications.trigger_inactive_workflows':    {'queue': 'notifications_maintenance'},
    'notifications.compute_rfm_segments':          {'queue': 'notifications_analytics'},
    'notifications.run_data_retention':            {'queue': 'notifications_maintenance'},
    'notifications.run_monitoring_check':          {'queue': 'notifications_maintenance'},

    # Integration system
    'notifications.integration.dispatch_event':         {'queue': 'notifications_high'},
    'notifications.integration.retry_integration':      {'queue': 'notifications_high'},
    'notifications.integration.process_queue_message':  {'queue': 'notifications_batch'},
    'notifications.integration.persist_audit_log':      {'queue': 'notifications_maintenance'},
    'notifications.integration.run_health_checks':      {'queue': 'notifications_maintenance'},
    'notifications.integration.sync_event_bus_stats':   {'queue': 'notifications_maintenance'},
    'notifications.integration.auto_discover':          {'queue': 'notifications_maintenance'},

    # Webhook tasks
    'notifications.process_sendgrid_webhook':           {'queue': 'notifications_tracking'},
    'notifications.process_twilio_sms_webhook':         {'queue': 'notifications_tracking'},
}

# ---------------------------------------------------------------------------
# Queue Definitions
# ---------------------------------------------------------------------------
from kombu import Queue, Exchange

NOTIFICATION_QUEUES = [
    Queue('notifications_high',        Exchange('notifications'), routing_key='notifications.high'),
    Queue('notifications_push',        Exchange('notifications'), routing_key='notifications.push'),
    Queue('notifications_email',       Exchange('notifications'), routing_key='notifications.email'),
    Queue('notifications_sms',         Exchange('notifications'), routing_key='notifications.sms'),
    Queue('notifications_campaigns',   Exchange('notifications'), routing_key='notifications.campaigns'),
    Queue('notifications_scheduled',   Exchange('notifications'), routing_key='notifications.scheduled'),
    Queue('notifications_retry',       Exchange('notifications'), routing_key='notifications.retry'),
    Queue('notifications_tracking',    Exchange('notifications'), routing_key='notifications.tracking'),
    Queue('notifications_analytics',   Exchange('notifications'), routing_key='notifications.analytics'),
    Queue('notifications_maintenance', Exchange('notifications'), routing_key='notifications.maintenance'),
    Queue('notifications_batch',       Exchange('notifications'), routing_key='notifications.batch'),
    Queue('notifications_optout',      Exchange('notifications'), routing_key='notifications.optout'),
]

# ---------------------------------------------------------------------------
# Per-queue concurrency configuration
# ---------------------------------------------------------------------------
NOTIFICATION_QUEUE_CONFIG = {
    'notifications_high':        {'concurrency': 8,  'prefetch_count': 4},
    'notifications_push':        {'concurrency': 16, 'prefetch_count': 8},
    'notifications_email':       {'concurrency': 8,  'prefetch_count': 4},
    'notifications_sms':         {'concurrency': 4,  'prefetch_count': 2},
    'notifications_campaigns':   {'concurrency': 4,  'prefetch_count': 2},
    'notifications_scheduled':   {'concurrency': 2,  'prefetch_count': 10},
    'notifications_retry':       {'concurrency': 2,  'prefetch_count': 4},
    'notifications_tracking':    {'concurrency': 4,  'prefetch_count': 8},
    'notifications_analytics':   {'concurrency': 2,  'prefetch_count': 2},
    'notifications_maintenance': {'concurrency': 2,  'prefetch_count': 2},
    'notifications_batch':       {'concurrency': 4,  'prefetch_count': 4},
    'notifications_optout':      {'concurrency': 2,  'prefetch_count': 4},
}

# ---------------------------------------------------------------------------
# Example settings.py additions
# ---------------------------------------------------------------------------
EXAMPLE_SETTINGS = """
# Add to settings.py:

from api.notifications.celery_config import (
    NOTIFICATION_TASK_ROUTES, NOTIFICATION_QUEUES, NOTIFICATION_QUEUE_CONFIG
)

CELERY_TASK_ROUTES = {
    **getattr(globals(), 'CELERY_TASK_ROUTES', {}),
    **NOTIFICATION_TASK_ROUTES,
}

CELERY_TASK_QUEUES = list(NOTIFICATION_QUEUES)

# Worker command (run each queue with appropriate concurrency):
# celery -A config worker \\
#     -Q notifications_high,notifications_push -c 16 \\
#     --loglevel=info &
# celery -A config worker \\
#     -Q notifications_email,notifications_sms -c 8 \\
#     --loglevel=info &
# celery -A config worker \\
#     -Q notifications_campaigns,notifications_batch -c 4 \\
#     --loglevel=info &
# celery -A config worker \\
#     -Q notifications_maintenance,notifications_analytics -c 2 \\
#     --loglevel=info &
"""
