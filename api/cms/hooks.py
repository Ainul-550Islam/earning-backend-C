# api/cms/hooks.py
"""
CMS Hook system — other apps register callbacks here.
Similar to WordPress action/filter hooks but Django-style.
"""
import logging
from typing import Callable, Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CMSHooks:
    """
    Lightweight hook system for CMS extensibility.
    Apps register hooks in their AppConfig.ready().

    Usage:
        # Register hook (in external app):
        from api.cms.hooks import CMSHooks
        CMSHooks.on('reward_earned', my_handler)

        # Fire hook (in CMS):
        CMSHooks.fire('reward_earned', user=user, amount=10.5)
    """
    _hooks: Dict[str, List[Callable]] = {}
    _filters: Dict[str, List[Callable]] = {}

    @classmethod
    def on(cls, hook_name: str, callback: Callable, priority: int = 10):
        if hook_name not in cls._hooks:
            cls._hooks[hook_name] = []
        cls._hooks[hook_name].append((priority, callback))
        cls._hooks[hook_name].sort(key=lambda x: x[0])
        logger.debug(f"[Hooks] Registered: {hook_name} ← {callback.__qualname__}")

    @classmethod
    def fire(cls, hook_name: str, **kwargs) -> List[Any]:
        results = []
        for priority, callback in cls._hooks.get(hook_name, []):
            try:
                result = callback(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"[Hooks] {hook_name} callback error: {e}")
        return results

    @classmethod
    def filter(cls, filter_name: str, callback: Callable, priority: int = 10):
        if filter_name not in cls._filters:
            cls._filters[filter_name] = []


# ── Survey Hooks ─────────────────────────────────────────────

# Hook: survey_started
# Called when user starts a survey
# Args: user, survey, completion

    @classmethod
    def apply_filter(cls, filter_name: str, value: Any, **kwargs) -> Any:
        for priority, callback in cls._filters.get(filter_name, []):
            try:
                value = callback(value, **kwargs)
            except Exception as e:
                logger.error(f"[Hooks] {filter_name} filter error: {e}")
        return value

    @classmethod
    def has_hook(cls, hook_name: str) -> bool:
        return hook_name in cls._hooks and len(cls._hooks[hook_name]) > 0

    @classmethod
    def remove(cls, hook_name: str, callback: Callable):
        if hook_name in cls._hooks:
            cls._hooks[hook_name] = [(p, c) for p, c in cls._hooks[hook_name] if c != callback]

    @classmethod
    def all_hooks(cls) -> Dict[str, int]:
        return {name: len(callbacks) for name, callbacks in cls._hooks.items()}

CMSHooks.on('survey_started', lambda user, survey, completion: {
    'user_id': user.id,
    'survey_id': str(survey.uuid),
    'completion_id': str(completion.uuid) if completion else None
})

# Hook: survey_completed
# Called when user completes a survey
# Args: user, survey, completion, quality_score
CMSHooks.on('survey_completed', lambda user, survey, completion, quality_score: {
    'user_id': user.id,
    'survey_id': str(survey.uuid),
    'completion_id': str(completion.uuid),
    'quality_score': quality_score
})

# Hook: survey_response_submitted
# Called when user submits survey responses
# Args: user, survey, responses, completion
CMSHooks.on('survey_response_submitted', lambda user, survey, responses, completion: {
    'user_id': user.id,
    'survey_id': str(survey.uuid),
    'response_count': len(responses),
    'completion_id': str(completion.uuid)
})

# Hook: survey_quality_updated
# Called when survey quality score is updated
# Args: completion, old_quality, new_quality
CMSHooks.on('survey_quality_updated', lambda completion, old_quality, new_quality: {
    'completion_id': str(completion.uuid),
    'old_quality': old_quality,
    'new_quality': new_quality
})

# Hook: survey_created
# Called when a new survey is created
# Args: survey, created_by
CMSHooks.on('survey_created', lambda survey, created_by: {
    'survey_id': str(survey.uuid),
    'created_by_id': created_by.id if created_by else None,
    'title': survey.title
})

# Hook: survey_updated
# Called when a survey is updated
# Args: survey, updated_by, changed_fields
CMSHooks.on('survey_updated', lambda survey, updated_by, changed_fields: {
    'survey_id': str(survey.uuid),
    'updated_by_id': updated_by.id if updated_by else None,
    'changed_fields': changed_fields
})

# Hook: survey_deleted
# Called when a survey is deleted
# Args: survey_id, deleted_by
CMSHooks.on('survey_deleted', lambda survey_id, deleted_by: {
    'survey_id': survey_id,
    'deleted_by_id': deleted_by.id if deleted_by else None
})


# ── Reward Hooks ─────────────────────────────────────────────

# Hook: reward_earned
# Called when user earns a reward
# Args: user, transaction, amount, source_type
CMSHooks.on('reward_earned', lambda user, transaction, amount, source_type: {
    'user_id': user.id,
    'transaction_id': str(transaction.uuid),
    'amount': float(amount),
    'source_type': source_type
})

# Hook: reward_approved
# Called when reward transaction is approved
# Args: user, transaction, amount
CMSHooks.on('reward_approved', lambda user, transaction, amount: {
    'user_id': user.id,
    'transaction_id': str(transaction.uuid),
    'amount': float(amount)
})

# Hook: reward_paid
# Called when reward is paid out
# Args: user, transaction, amount, payment_method
CMSHooks.on('reward_paid', lambda user, transaction, amount, payment_method: {
    'user_id': user.id,
    'transaction_id': str(transaction.uuid),
    'amount': float(amount),
    'payment_method': payment_method
})

# Hook: reward_pool_low
# Called when reward pool is running low
# Args: pool, utilization_percentage, remaining_amount
CMSHooks.on('reward_pool_low', lambda pool, utilization_percentage, remaining_amount: {
    'pool_id': str(pool.uuid),
    'pool_name': pool.name,
    'utilization_percentage': utilization_percentage,
    'remaining_amount': float(remaining_amount)
})

# Hook: reward_pool_refilled
# Called when reward pool is refilled
# Args: pool, refill_amount, new_total
CMSHooks.on('reward_pool_refilled', lambda pool, refill_amount, new_total: {
    'pool_id': str(pool.uuid),
    'pool_name': pool.name,
    'refill_amount': float(refill_amount),
    'new_total': float(new_total)
})

# Hook: reward_transaction_created
# Called when reward transaction is created
# Args: user, transaction, amount, transaction_type, status
CMSHooks.on('reward_transaction_created', lambda user, transaction, amount, transaction_type, status: {
    'user_id': user.id,
    'transaction_id': str(transaction.uuid),
    'amount': float(amount),
    'transaction_type': transaction_type,
    'status': status
})


# ── Task Management Hooks ─────────────────────────────────────

# Hook: task_started
# Called when task execution starts
# Args: task, execution, worker_id
CMSHooks.on('task_started', lambda task, execution, worker_id: {
    'task_id': str(task.uuid),
    'execution_id': str(execution.uuid),
    'worker_id': worker_id
})

# Hook: task_completed
# Called when task execution completes
# Args: task, execution, runtime_seconds, success
CMSHooks.on('task_completed', lambda task, execution, runtime_seconds, success: {
    'task_id': str(task.uuid),
    'execution_id': str(execution.uuid),
    'runtime_seconds': runtime_seconds,
    'success': success
})

# Hook: task_failed
# Called when task execution fails
# Args: task, execution, error_message, retry_count
CMSHooks.on('task_failed', lambda task, execution, error_message, retry_count: {
    'task_id': str(task.uuid),
    'execution_id': str(execution.uuid),
    'error_message': error_message,
    'retry_count': retry_count
})

# Hook: task_scheduled
# Called when task is scheduled
# Args: task, next_run_time, created_by
CMSHooks.on('task_scheduled', lambda task, next_run_time, created_by: {
    'task_id': str(task.uuid),
    'next_run_time': next_run_time.isoformat() if next_run_time else None,
    'created_by_id': created_by.id if created_by else None
})

# Hook: task_queue_updated
# Called when task queue item is updated
# Args: queue_item, old_status, new_status
CMSHooks.on('task_queue_updated', lambda queue_item, old_status, new_status: {
    'queue_item_id': str(queue_item.uuid),
    'old_status': old_status,
    'new_status': new_status
})

# Hook: task_timeout
# Called when task execution times out
# Args: task, execution, timeout_duration
CMSHooks.on('task_timeout', lambda task, execution, timeout_duration: {
    'task_id': str(task.uuid),
    'execution_id': str(execution.uuid),
    'timeout_duration': timeout_duration
})


# ── User Profile Hooks ─────────────────────────────────────────────

# Hook: profile_updated
# Called when user profile is updated
# Args: user, profile, changed_fields
CMSHooks.on('profile_updated', lambda user, profile, changed_fields: {
    'user_id': user.id,
    'profile_id': str(profile.uuid),
    'changed_fields': changed_fields
})

# Hook: profile_completeness_changed
# Called when profile completeness changes
# Args: user, profile, old_completeness, new_completeness
CMSHooks.on('profile_completeness_changed', lambda user, profile, old_completeness, new_completeness: {
    'user_id': user.id,
    'profile_id': str(profile.uuid),
    'old_completeness': old_completeness,
    'new_completeness': new_completeness
})

# Hook: user_segment_changed
# Called when user's segment assignments change
# Args: user, old_segments, new_segments
CMSHooks.on('user_segment_changed', lambda user, old_segments, new_segments: {
    'user_id': user.id,
    'old_segments': [str(s.uuid) for s in old_segments],
    'new_segments': [str(s.uuid) for s in new_segments]
})

# Hook: user_registered
# Called when new user registers
# Args: user, registration_method
CMSHooks.on('user_registered', lambda user, registration_method: {
    'user_id': user.id,
    'registration_method': registration_method
})

# Hook: user_login
# Called when user logs in
# Args: user, login_method, ip_address, user_agent
CMSHooks.on('user_login', lambda user, login_method, ip_address, user_agent: {
    'user_id': user.id,
    'login_method': login_method,
    'ip_address': ip_address,
    'user_agent': user_agent
})

# Hook: user_logout
# Called when user logs out
# Args: user, logout_reason
CMSHooks.on('user_logout', lambda user, logout_reason: {
    'user_id': user.id,
    'logout_reason': logout_reason
})


# ── Analytics Hooks ─────────────────────────────────────────────

# Hook: analytics_updated
# Called when analytics data is updated
# Args: data_type, instance, old_data, new_data
CMSHooks.on('analytics_updated', lambda data_type, instance, old_data, new_data: {
    'data_type': data_type,
    'instance_id': str(instance.uuid) if hasattr(instance, 'uuid') else str(instance.id),
    'old_data': old_data,
    'new_data': new_data
})

# Hook: report_generated
# Called when a report is generated
# Args: report_type, file_path, generated_by, filters
CMSHooks.on('report_generated', lambda report_type, file_path, generated_by, filters: {
    'report_type': report_type,
    'file_path': file_path,
    'generated_by_id': generated_by.id if hasattr(generated_by, 'id') else str(generated_by),
    'filters': filters
})

# Hook: dashboard_data_updated
# Called when dashboard data is updated
# Args: user, section, data
CMSHooks.on('dashboard_data_updated', lambda user, section, data: {
    'user_id': user.id if user else None,
    'section': section,
    'data': data
})

# Hook: metrics_collected
# Called when system metrics are collected
# Args: metric_type, value, tags
CMSHooks.on('metrics_collected', lambda metric_type, value, tags: {
    'metric_type': metric_type,
    'value': value,
    'tags': tags
})


# ── Notification Hooks ─────────────────────────────────────────────

# Hook: notification_created
# Called when notification is created
# Args: user, notification, recipients
CMSHooks.on('notification_created', lambda user, notification, recipients: {
    'user_id': user.id if user else None,
    'notification_id': str(notification.uuid),
    'recipients': recipients
})

# Hook: notification_read
# Called when notification is read
# Args: user, notification, read_at
CMSHooks.on('notification_read', lambda user, notification, read_at: {
    'user_id': user.id,
    'notification_id': str(notification.uuid),
    'read_at': read_at.isoformat() if read_at else None
})

# Hook: bulk_notification_sent
# Called when bulk notification is sent
# Args: recipients, notification_data, sent_count
CMSHooks.on('bulk_notification_sent', lambda recipients, notification_data, sent_count: {
    'recipients': recipients,
    'notification_type': notification_data.get('type'),
    'sent_count': sent_count
})


# ── System Hooks ─────────────────────────────────────────────

# Hook: system_maintenance_started
# Called when system maintenance starts
# Args: reason, estimated_duration, affected_services
CMSHooks.on('system_maintenance_started', lambda reason, estimated_duration, affected_services: {
    'reason': reason,
    'estimated_duration': estimated_duration,
    'affected_services': affected_services
})

# Hook: system_maintenance_ended
# Called when system maintenance ends
# Args: duration, affected_services
CMSHooks.on('system_maintenance_ended', lambda duration, affected_services: {
    'duration': duration,
    'affected_services': affected_services
})

# Hook: cache_invalidated
# Called when cache is invalidated
# Args: cache_key, pattern, invalidated_by
CMSHooks.on('cache_invalidated', lambda cache_key, pattern, invalidated_by: {
    'cache_key': cache_key,
    'pattern': pattern,
    'invalidated_by': invalidated_by
})

# Hook: webhook_triggered
# Called when webhook is triggered
# Args: webhook_url, event_type, payload, response_status
CMSHooks.on('webhook_triggered', lambda webhook_url, event_type, payload, response_status: {
    'webhook_url': webhook_url,
    'event_type': event_type,
    'payload': payload,
    'response_status': response_status
})

# Hook: error_occurred
# Called when system error occurs
# Args: error_type, error_message, context, severity
CMSHooks.on('error_occurred', lambda error_type, error_message, context, severity: {
    'error_type': error_type,
    'error_message': error_message,
    'context': context,
    'severity': severity
})

# Hook: performance_alert
# Called when performance alert is triggered
# Args: metric_name, threshold, actual_value, alert_type
CMSHooks.on('performance_alert', lambda metric_name, threshold, actual_value, alert_type: {
    'metric_name': metric_name,
    'threshold': threshold,
    'actual_value': actual_value,
    'alert_type': alert_type
})


# ── Hook Filters ─────────────────────────────────────────────

# Filter: survey_reward_calculation
# Filter to modify survey reward calculation
# Args: base_reward, user, survey, quality_score
CMSHooks.filter('survey_reward_calculation', lambda base_reward, user, survey, quality_score: {
    'base_reward': base_reward,
    'user_id': user.id,
    'survey_id': str(survey.uuid),
    'quality_score': quality_score
})

# Filter: task_execution_permission
# Filter to check if task can be executed
# Args: task, context
CMSHooks.filter('task_execution_permission', lambda task, context: {
    'task_id': str(task.uuid),
    'can_execute': True
})

# Filter: notification_delivery_channels
# Filter to modify notification delivery channels
# Args: user, notification_type, channels
CMSHooks.filter('notification_delivery_channels', lambda user, notification_type, channels: {
    'user_id': user.id,
    'notification_type': notification_type,
    'channels': channels
})

# Filter: user_profile_validation
# Filter to add custom profile validation
# Args: profile_data, context
CMSHooks.filter('user_profile_validation', lambda profile_data, context: {
    'profile_data': profile_data,
    'valid': True,
    'errors': []
})

# Filter: reward_transaction_validation
# Filter to validate reward transactions
# Args: transaction_data, context
CMSHooks.filter('reward_transaction_validation', lambda transaction_data, context: {
    'transaction_data': transaction_data,
    'valid': True,
    'errors': []
})
# ── Built-in CMS hooks (fired by CMS internally) ──────────────────

HOOK_REWARD_EARNED        = 'reward_earned'
HOOK_OFFER_COMPLETED      = 'offer_completed'
HOOK_USER_LEVEL_UP        = 'user_level_up'
HOOK_STREAK_MILESTONE     = 'streak_milestone'
HOOK_REFERRAL_BONUS       = 'referral_bonus'
HOOK_WITHDRAWAL_REQUESTED = 'withdrawal_requested'
HOOK_WITHDRAWAL_PAID      = 'withdrawal_paid'
HOOK_CONTENT_PUBLISHED    = 'content_published'
HOOK_FORM_SUBMITTED       = 'form_submitted'
HOOK_QUIZ_COMPLETED       = 'quiz_completed'
HOOK_USER_REGISTERED      = 'user_registered'

FILTER_REWARD_AMOUNT    = 'filter_reward_amount'   # Modify reward before award
FILTER_OFFER_LIST       = 'filter_offer_list'      # Modify offer list before display
FILTER_USER_LEVEL       = 'filter_user_level'      # Override level calculation
FILTER_WITHDRAWAL_LIMIT = 'filter_withdrawal_limit'# Modify min withdrawal
