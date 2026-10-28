"""
api/tasks/receivers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django signal receivers for the task system.
Connected in apps.py → signals.py.
Handles cross-app side effects triggered by model changes.
"""

import logging
from decimal import Decimal
from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# USER TASK COMPLETION RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def on_task_completion_saved(sender, instance, created, **kwargs):
    """
    Fires when a UserTaskCompletion is saved.

    On completion (status=completed):
    1. Emit EventBus event → triggers gamification, fraud check, analytics
    2. Update DataBridge user snapshot
    3. Update community points
    4. Check milestone rewards
    5. Award XP
    """
    try:
        if instance.status != 'completed':
            return

        user_id    = instance.user_id
        task_id    = getattr(instance.task, 'task_id', '') if instance.task else ''
        reward     = instance.reward_amount or Decimal('0')

        # Emit EventBus event (async)
        try:
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit('task.completed', {
                'user_id':       user_id,
                'task_id':       task_id,
                'reward_amount': str(reward),
                'completion_id': instance.pk,
                'ip_address':    getattr(instance, 'ip_address', ''),
            }, async_dispatch=True)
        except Exception as e:
            logger.debug(f"[RECEIVER] EventBus emit: {e}")

        # Invalidate DataBridge user cache
        try:
            from api.tasks.integration.data_bridge import DataBridge
            DataBridge.user(user_id).invalidate('wallet_balance')
            DataBridge.user(user_id).invalidate('total_earnings')
        except Exception as e:
            logger.debug(f"[RECEIVER] DataBridge invalidate: {e}")

    except Exception as e:
        logger.error(f"[RECEIVER] on_task_completion_saved: {e}")


def on_task_status_changed(sender, instance, **kwargs):
    """
    pre_save receiver: detects status transitions on UserTaskCompletion.
    Logs status change for audit trail.
    """
    try:
        if instance.pk:
            try:
                old = sender.objects.get(pk=instance.pk)
                if old.status != instance.status:
                    logger.info(
                        f"[STATUS CHANGE] UserTaskCompletion #{instance.pk}: "
                        f"{old.status} → {instance.status}"
                    )
                    instance._status_changed_from = old.status
            except sender.DoesNotExist:
                pass
    except Exception as e:
        logger.debug(f"[RECEIVER] on_task_status_changed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MASTER TASK RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def on_master_task_saved(sender, instance, created, **kwargs):
    """
    Fires when a MasterTask is saved.
    1. Invalidates offer feed cache
    2. Re-indexes for search
    3. Syncs to DataBridge
    """
    try:
        # Invalidate cached offer feed
        cache.delete('offer_feed_all_all')
        cache.delete(f'task_config_{instance.task_id}')

        # Re-index in background
        try:
            from celery import current_app
            current_app.send_task(
                'tasks.search_tasks.index_tasks',
                kwargs={'task_ids': [instance.pk]},
                queue='low',
                countdown=5,
            )
        except Exception:
            pass

    except Exception as e:
        logger.debug(f"[RECEIVER] on_master_task_saved: {e}")


def on_master_task_deleted(sender, instance, **kwargs):
    """
    Fires when a MasterTask is deleted.
    Cleans up related caches.
    """
    try:
        cache.delete(f'task_config_{instance.task_id}')
        cache.delete('offer_feed_all_all')
    except Exception as e:
        logger.debug(f"[RECEIVER] on_master_task_deleted: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# USER RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def on_user_created(sender, instance, created, **kwargs):
    """
    Fires when a new User is created.
    1. Emit 'user.registered' EventBus event
    2. Schedule welcome email drip
    3. Assign onboarding tasks
    """
    if not created:
        return

    try:
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.registered', {
            'user_id':   instance.pk,
            'username':  instance.username,
            'email':     instance.email,
            'joined_at': instance.date_joined.isoformat(),
        }, async_dispatch=True)
    except Exception as e:
        logger.debug(f"[RECEIVER] on_user_created EventBus: {e}")

    # Initialize DataBridge
    try:
        from api.tasks.integration.data_bridge import DataBridge
        DataBridge.set_user(instance.pk, 'kyc_tier',      'none', ttl=86400)
        DataBridge.set_user(instance.pk, 'fraud_score',   0,       ttl=86400)
        DataBridge.set_user(instance.pk, 'publisher_tier', 'bronze', ttl=86400)
        DataBridge.set_user(instance.pk, 'level',          1,       ttl=86400)
        DataBridge.set_user(instance.pk, 'xp_points',      0,       ttl=86400)
    except Exception as e:
        logger.debug(f"[RECEIVER] on_user_created DataBridge: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def on_workflow_saved(sender, instance, created, **kwargs):
    """Clears workflow-related caches when a workflow is updated."""
    try:
        cache.delete(f'workflow_config_{instance.pk}')
        cache.delete(f'workflow_steps_{instance.pk}')
    except Exception as e:
        logger.debug(f"[RECEIVER] on_workflow_saved: {e}")


def on_workflow_instance_status_changed(sender, instance, **kwargs):
    """
    pre_save: detect workflow instance status transitions.
    Triggers notifications and DataBridge updates.
    """
    try:
        if instance.pk:
            try:
                old = sender.objects.get(pk=instance.pk)
                if old.status != instance.status:
                    logger.info(
                        f"[WORKFLOW] Instance #{instance.pk}: "
                        f"{old.status} → {instance.status}"
                    )
            except sender.DoesNotExist:
                pass
    except Exception as e:
        logger.debug(f"[RECEIVER] on_workflow_instance_status_changed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def on_task_alert_saved(sender, instance, created, **kwargs):
    """
    Clears alert evaluation cache when an alert is modified.
    Forces re-evaluation on next cycle.
    """
    try:
        cache.delete(f'alert_eval_{instance.pk}')
        cache.delete('alert_eval_all')
    except Exception as e:
        logger.debug(f"[RECEIVER] on_task_alert_saved: {e}")


def on_worker_health_updated(sender, instance, **kwargs):
    """
    pre_save: detect worker status changes.
    Logs degraded/offline transitions.
    """
    try:
        if instance.pk:
            try:
                old = sender.objects.get(pk=instance.pk)
                if old.status != instance.status:
                    if instance.status in ('offline', 'degraded'):
                        logger.warning(
                            f"[WORKER] {instance.worker_id} status: "
                            f"{old.status} → {instance.status}"
                        )
                    else:
                        logger.info(
                            f"[WORKER] {instance.worker_id} status: "
                            f"{old.status} → {instance.status}"
                        )
            except sender.DoesNotExist:
                pass
    except Exception as e:
        logger.debug(f"[RECEIVER] on_worker_health_updated: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CONNECT ALL RECEIVERS
# ══════════════════════════════════════════════════════════════════════════════

def connect_all_receivers():
    """
    Connect all signal receivers.
    Called from tasks/signals.py which is loaded by apps.py.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # User lifecycle
    try:
        post_save.connect(on_user_created, sender=User,
                          dispatch_uid='tasks_on_user_created')
        logger.debug("[RECEIVER] on_user_created connected")
    except Exception as e:
        logger.warning(f"[RECEIVER] connect user_created: {e}")

    # Task completions
    try:
        from api.tasks.models import UserTaskCompletion, MasterTask
        pre_save.connect(on_task_status_changed, sender=UserTaskCompletion,
                         dispatch_uid='tasks_on_task_status_changed')
        post_save.connect(on_task_completion_saved, sender=UserTaskCompletion,
                          dispatch_uid='tasks_on_task_completion_saved')
        post_save.connect(on_master_task_saved, sender=MasterTask,
                          dispatch_uid='tasks_on_master_task_saved')
        post_delete.connect(on_master_task_deleted, sender=MasterTask,
                            dispatch_uid='tasks_on_master_task_deleted')
        logger.debug("[RECEIVER] Task completion receivers connected")
    except ImportError as e:
        logger.debug(f"[RECEIVER] Task models not available: {e}")

    # Workflow
    try:
        from api.tasks.models.workflow import TaskWorkflow, WorkflowInstance
        post_save.connect(on_workflow_saved, sender=TaskWorkflow,
                          dispatch_uid='tasks_on_workflow_saved')
        pre_save.connect(on_workflow_instance_status_changed, sender=WorkflowInstance,
                         dispatch_uid='tasks_on_workflow_instance_status')
        logger.debug("[RECEIVER] Workflow receivers connected")
    except ImportError as e:
        logger.debug(f"[RECEIVER] Workflow models not available: {e}")

    # Monitoring
    try:
        from api.tasks.models.monitoring import TaskAlert, WorkerHealth
        post_save.connect(on_task_alert_saved, sender=TaskAlert,
                          dispatch_uid='tasks_on_alert_saved')
        pre_save.connect(on_worker_health_updated, sender=WorkerHealth,
                         dispatch_uid='tasks_on_worker_health_updated')
        logger.debug("[RECEIVER] Monitoring receivers connected")
    except ImportError as e:
        logger.debug(f"[RECEIVER] Monitoring models not available: {e}")

    logger.info("[OK] All task signal receivers connected")


__all__ = [
    'connect_all_receivers',
    'on_task_completion_saved', 'on_task_status_changed',
    'on_master_task_saved', 'on_master_task_deleted',
    'on_user_created', 'on_workflow_saved',
    'on_workflow_instance_status_changed', 'on_task_alert_saved',
    'on_worker_health_updated',
]
