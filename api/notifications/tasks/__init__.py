# earning_backend/api/notifications/tasks/__init__.py
"""
Tasks package — imports all Celery tasks.
Core tasks from _tasks_core.py (renamed from tasks.py to unblock tasks/ package).
New split tasks from individual modules.
"""
# ---------------------------------------------------------------------------
# Import all core tasks from monolithic _tasks_core.py
# ---------------------------------------------------------------------------
import importlib as _imp
_core = _imp.import_module('api.notifications._tasks_core')
import sys as _sys
_this = _sys.modules[__name__]
for _name in dir(_core):
    if not _name.startswith('__') and callable(getattr(_core, _name)):
        setattr(_this, _name, getattr(_core, _name))
del _imp, _core, _sys, _this, _name

# ---------------------------------------------------------------------------
# New split task modules
# ---------------------------------------------------------------------------
from .send_push_tasks import send_push_batch_task, send_push_multicast_task          # noqa
from .send_email_tasks import send_email_batch_task, send_bulk_email_task, process_sendgrid_webhook_task  # noqa
from .send_sms_tasks import send_sms_batch_task, send_bulk_sms_task, process_twilio_sms_webhook_task      # noqa
from .campaign_tasks import (process_campaign_task, start_scheduled_campaigns,        # noqa
    check_campaign_completion, update_all_campaign_results)
from .ab_test_tasks import evaluate_ab_test_task, evaluate_all_pending_ab_tests       # noqa
from .retry_tasks import retry_notification_task, process_all_retries, retry_failed_queue_entries  # noqa
from .schedule_tasks import send_scheduled_notifications, cancel_overdue_schedules, schedule_notification_task  # noqa
from .delivery_tracking_tasks import (poll_delivery_status, update_campaign_results_task,  # noqa
    update_all_active_campaign_results, process_sendgrid_events_task,
    process_twilio_webhook_task, mark_notification_delivered_task,
    mark_notification_read_task, mark_notification_clicked_task,
    process_push_delivery_receipt_task)
from .fatigue_check_tasks import (reset_daily_fatigue_counters, reset_weekly_fatigue_counters,  # noqa
    reset_monthly_fatigue_counters, recalculate_fatigue_flags,
    clear_user_fatigue_task, create_missing_fatigue_records)
from .insight_tasks import (generate_daily_notification_insights, generate_weekly_notification_summary,  # noqa
    refresh_delivery_rates, backfill_insights, generate_legacy_daily_analytics, run_all_daily_analytics)
from .cleanup_tasks import (cleanup_expired_notifications, cleanup_old_notifications,  # noqa
    cleanup_old_delivery_logs, cleanup_stale_queue_entries, cleanup_old_retry_records,
    cleanup_read_in_app_messages, cleanup_expired_in_app_messages, cleanup_old_schedules, run_all_cleanup)
from .token_refresh_tasks import (refresh_stale_fcm_tokens, cleanup_inactive_devices,  # noqa
    deactivate_duplicate_tokens, deactivate_invalid_push_devices)
from .batch_send_tasks import process_batch_task, send_batch_chunk_task, finalize_batch_task, cancel_batch_task  # noqa
from .unsubscribe_tasks import (process_unsubscribe_request_task, process_bulk_unsubscribe_task,  # noqa
    sync_sendgrid_unsubscribes, process_one_click_unsubscribe_task, cleanup_old_opt_out_records)


# ---------------------------------------------------------------------------
# Integration System tasks
# ---------------------------------------------------------------------------
from api.notifications.integration_system.tasks import (  # noqa: F401
    dispatch_event_task,
    retry_integration_task,
    process_queue_message_task,
    persist_audit_log_task,
    run_health_checks_task,
    sync_event_bus_stats_task,
)

from .journey_tasks import execute_journey_step_task, enroll_users_in_journey_task  # noqa

from .background_tasks import (  # noqa: F401
    execute_workflow_task, run_data_retention_task,
    trigger_inactive_user_workflows, compute_rfm_segments_task,
    run_monitoring_check_task,
)
