# earning_backend/api/notifications/workflow.py
"""
Workflow — Triggered automation workflows for notifications.

A workflow is a rule-based automation:
  WHEN [trigger event] AND [conditions]
  THEN [actions] WITH [delay]

Examples:
  - WHEN user registers AND no task in 24h → send task reminder push
  - WHEN withdrawal created AND amount > 1000 → send special offer email
  - WHEN user inactive for 3 days → start reengagement journey
  - WHEN fraud score > 80 → send security alert + notify admin

vs Journey: Journeys are sequential multi-step sequences.
            Workflows are event-triggered single or multi-action rules.

Usage:
    from api.notifications.workflow import workflow_engine

    # Register a workflow
    @workflow_engine.workflow('user_inactive_3d')
    def inactive_user_workflow(event):
        user = event.user
        if not user_has_done_task_recently(user, days=3):
            return WorkflowActions.send_push(
                user=user,
                title='আমরা আপনাকে miss করছি!',
                message='৩ দিন হয়ে গেল। আজই task করুন!',
            )

    # Trigger a workflow
    workflow_engine.trigger('user_inactive_3d', user=user, data={...})
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow result actions
# ---------------------------------------------------------------------------

class WorkflowActions:
    """Helper methods to return workflow action payloads."""

    @staticmethod
    def send_notification(user, notification_type: str, title: str,
                          message: str, channel: str = 'in_app',
                          priority: str = 'medium', delay_seconds: int = 0) -> dict:
        return {
            'action': 'send_notification',
            'user': user, 'notification_type': notification_type,
            'title': title, 'message': message, 'channel': channel,
            'priority': priority, 'delay_seconds': delay_seconds,
        }

    @staticmethod
    def send_push(user, title: str, message: str,
                  notification_type: str = 'announcement', delay_seconds: int = 0) -> dict:
        return WorkflowActions.send_notification(user, notification_type, title, message, 'push', 'medium', delay_seconds)

    @staticmethod
    def send_email(user, title: str, message: str,
                   notification_type: str = 'announcement') -> dict:
        return WorkflowActions.send_notification(user, notification_type, title, message, 'email', 'medium')

    @staticmethod
    def enroll_journey(user, journey_id: str, context: dict = None) -> dict:
        return {'action': 'enroll_journey', 'user': user, 'journey_id': journey_id, 'context': context or {}}

    @staticmethod
    def notify_admin(title: str, message: str, priority: str = 'high') -> dict:
        return {'action': 'notify_admin', 'title': title, 'message': message, 'priority': priority}

    @staticmethod
    def skip() -> dict:
        return {'action': 'skip', 'reason': 'condition_not_met'}

    @staticmethod
    def stop() -> dict:
        return {'action': 'stop', 'reason': 'workflow_stopped'}


# ---------------------------------------------------------------------------
# Workflow data class
# ---------------------------------------------------------------------------

@dataclass
class Workflow:
    workflow_id: str
    name: str
    description: str = ''
    handler: Optional[Callable] = None
    trigger_events: List[str] = field(default_factory=list)
    conditions: List[Callable] = field(default_factory=list)
    is_active: bool = True
    max_executions_per_user: int = 1  # 0 = unlimited
    cooldown_hours: int = 24


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """
    Event-triggered workflow automation engine.

    Features:
    - Register workflows with decorators or directly
    - Trigger workflows from any module (via EventBus or direct call)
    - Per-user execution limits and cooldowns
    - Condition evaluation before execution
    - Action execution (send notification, start journey, notify admin)
    """

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._register_builtin_workflows()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, workflow: Workflow):
        self._workflows[workflow.workflow_id] = workflow
        logger.info(f'WorkflowEngine: registered "{workflow.workflow_id}"')

    def workflow(self, workflow_id: str, name: str = '', description: str = '',
                  trigger_events: List[str] = None, conditions: List[Callable] = None,
                  max_executions: int = 1, cooldown_hours: int = 24):
        """Decorator to register a workflow handler."""
        def decorator(fn: Callable):
            wf = Workflow(
                workflow_id=workflow_id,
                name=name or workflow_id,
                description=description,
                handler=fn,
                trigger_events=trigger_events or [],
                conditions=conditions or [],
                max_executions_per_user=max_executions,
                cooldown_hours=cooldown_hours,
            )
            self.register(wf)
            return fn
        return decorator

    # ------------------------------------------------------------------
    # Triggering
    # ------------------------------------------------------------------

    def trigger(self, workflow_id: str, user=None, data: dict = None,
                async_exec: bool = True) -> dict:
        """
        Trigger a workflow for a user.

        Args:
            workflow_id: Workflow identifier.
            user:        Target user (optional).
            data:        Event data dict.
            async_exec:  If True, execute via Celery task.

        Returns:
            {'executed': bool, 'action': str, 'reason': str}
        """
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {'executed': False, 'reason': 'workflow_not_found'}
        if not wf.is_active:
            return {'executed': False, 'reason': 'workflow_inactive'}

        # Check per-user cooldown and execution limit
        if user:
            if not self._check_execution_allowed(wf, user):
                return {'executed': False, 'reason': 'cooldown_or_limit_reached'}

        # Evaluate conditions
        event_data = data or {}
        for condition in wf.conditions:
            try:
                if not condition(user=user, data=event_data):
                    return {'executed': False, 'reason': 'condition_not_met'}
            except Exception as exc:
                logger.warning(f'WorkflowEngine condition error {workflow_id}: {exc}')

        if async_exec:
            return self._execute_async(wf, user, event_data)
        return self._execute_sync(wf, user, event_data)

    def trigger_for_event(self, event_type: str, user=None, data: dict = None):
        """Trigger all workflows registered for an event type."""
        triggered = []
        for wf in self._workflows.values():
            if event_type in wf.trigger_events:
                result = self.trigger(wf.workflow_id, user=user, data=data)
                triggered.append({'workflow': wf.workflow_id, **result})
        return triggered

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_sync(self, wf: Workflow, user, data: dict) -> dict:
        """Execute workflow handler synchronously."""
        if not wf.handler:
            return {'executed': False, 'reason': 'no_handler'}
        try:
            result = wf.handler(user=user, data=data)
            if result:
                executed = self._run_action(result)
                self._record_execution(wf, user)
                return {'executed': executed, 'action': result.get('action', ''), 'reason': ''}
        except Exception as exc:
            logger.error(f'WorkflowEngine execute {wf.workflow_id}: {exc}')
            return {'executed': False, 'reason': str(exc)}
        return {'executed': True, 'action': 'completed', 'reason': ''}

    def _execute_async(self, wf: Workflow, user, data: dict) -> dict:
        """Queue workflow execution via Celery."""
        try:
            from api.notifications.tasks.background_tasks import execute_workflow_task
            task = execute_workflow_task.delay(
                wf.workflow_id,
                getattr(user, 'pk', None),
                data,
            )
            return {'executed': True, 'action': 'queued', 'task_id': task.id}
        except Exception:
            # Fallback to sync
            return self._execute_sync(wf, user, data)

    def _run_action(self, action: dict) -> bool:
        """Execute a workflow action dict."""
        action_type = action.get('action', '')

        if action_type == 'skip' or action_type == 'stop':
            return False

        if action_type == 'send_notification':
            try:
                from api.notifications.services.NotificationService import notification_service
                user = action['user']
                notif = notification_service.create_notification(
                    user=user,
                    title=action.get('title', ''),
                    message=action.get('message', ''),
                    notification_type=action.get('notification_type', 'announcement'),
                    channel=action.get('channel', 'in_app'),
                    priority=action.get('priority', 'medium'),
                )
                if notif:
                    delay = action.get('delay_seconds', 0)
                    if delay > 0:
                        from api.notifications.tasks_cap import enqueue_notification_send
                        enqueue_notification_send(notif.pk, action.get('channel', 'in_app'), action.get('priority', 'medium'))
                    else:
                        notification_service.send_notification(notif)
                    return True
            except Exception as exc:
                logger.error(f'_run_action send_notification: {exc}')
            return False

        elif action_type == 'enroll_journey':
            try:
                from api.notifications.services.JourneyService import journey_service
                result = journey_service.enroll_user(action['user'], action['journey_id'], action.get('context', {}))
                return result.get('success', False)
            except Exception as exc:
                logger.error(f'_run_action enroll_journey: {exc}')
            return False

        elif action_type == 'notify_admin':
            try:
                from django.contrib.auth import get_user_model
                from api.notifications.services.NotificationService import notification_service
                User = get_user_model()
                for admin in User.objects.filter(is_staff=True, is_active=True)[:3]:
                    notification_service.create_notification(
                        user=admin, title=action['title'], message=action['message'],
                        notification_type='system_alert', channel='in_app',
                        priority=action.get('priority', 'high'),
                    )
                return True
            except Exception as exc:
                logger.error(f'_run_action notify_admin: {exc}')
            return False

        return False

    def _check_execution_allowed(self, wf: Workflow, user) -> bool:
        """Check cooldown and execution limits for a user."""
        from django.core.cache import cache
        cooldown_key = f'workflow:cooldown:{wf.workflow_id}:{user.pk}'
        if cache.get(cooldown_key):
            return False
        return True

    def _record_execution(self, wf: Workflow, user):
        """Record workflow execution for cooldown tracking."""
        if not user:
            return
        from django.core.cache import cache
        cooldown_key = f'workflow:cooldown:{wf.workflow_id}:{user.pk}'
        cache.set(cooldown_key, '1', wf.cooldown_hours * 3600)

    # ------------------------------------------------------------------
    # Built-in workflows
    # ------------------------------------------------------------------

    def _register_builtin_workflows(self):
        """Register pre-built workflows for the earning site."""

        @self.workflow(
            'inactive_user_3d',
            name='3-Day Inactive User',
            description='Re-engage users who haven\'t logged in for 3 days',
            trigger_events=['user.inactivity.3d'],
            max_executions=1,
            cooldown_hours=72,
        )
        def inactive_3d(user, data: dict):
            from api.notifications.helpers import _user_logged_in_recently
            if _user_logged_in_recently(user, days=3):
                return WorkflowActions.skip()
            return WorkflowActions.send_push(
                user=user,
                title='আমরা আপনাকে miss করছি! 😢',
                message='৩ দিন ধরে দেখা নেই। আজই task করুন!',
                notification_type='announcement',
            )

        @self.workflow(
            'high_value_user_vip',
            name='High Value User VIP Offer',
            description='Send special offer to users who earned > 5000 BDT',
            trigger_events=['wallet.credited'],
            max_executions=1,
            cooldown_hours=168,  # 1 week
        )
        def high_value_vip(user, data: dict):
            total_earned = data.get('total_earned', 0)
            if float(total_earned) < 5000:
                return WorkflowActions.skip()
            return WorkflowActions.send_notification(
                user=user,
                notification_type='vip_offer',
                title='🌟 VIP Status Unlocked!',
                message=f'আপনি ৳5000+ আয় করেছেন! VIP exclusive offers আপনার জন্য ready।',
                channel='in_app',
                priority='high',
            )

        @self.workflow(
            'fraud_risk_alert',
            name='Fraud Risk Alert',
            description='Alert admin when user fraud score exceeds threshold',
            trigger_events=['fraud.score_updated'],
            max_executions=0,  # Unlimited
            cooldown_hours=1,
        )
        def fraud_alert(user, data: dict):
            score = data.get('fraud_score', 0)
            if float(score) < 70:
                return WorkflowActions.skip()
            return WorkflowActions.notify_admin(
                title=f'🚨 High Fraud Risk Score',
                message=f'User #{getattr(user,"pk","?")} fraud score: {score}. Immediate review needed.',
                priority='urgent',
            )

        @self.workflow(
            'first_withdrawal_congratulate',
            name='First Withdrawal Congratulation',
            description='Congratulate user on their first successful withdrawal',
            trigger_events=['withdrawal.completed'],
            max_executions=1,
            cooldown_hours=24 * 365,  # Once per year
        )
        def first_withdrawal(user, data: dict):
            from api.notifications.models import Notification
            prev_withdrawals = Notification.objects.filter(
                user=user, notification_type='withdrawal_success'
            ).count()
            if prev_withdrawals > 1:
                return WorkflowActions.skip()
            amount = data.get('amount', 0)
            return WorkflowActions.send_notification(
                user=user,
                notification_type='achievement_unlocked',
                title='🎉 প্রথম Withdrawal সফল!',
                message=f'অভিনন্দন! আপনার প্রথম ৳{amount} withdrawal সফলভাবে সম্পন্ন হয়েছে!',
                channel='in_app',
                priority='high',
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_workflows(self) -> List[dict]:
        return [
            {'workflow_id': wf.workflow_id, 'name': wf.name,
             'description': wf.description, 'is_active': wf.is_active,
             'trigger_events': wf.trigger_events, 'cooldown_hours': wf.cooldown_hours}
            for wf in self._workflows.values()
        ]

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)


# Singleton
workflow_engine = WorkflowEngine()


def _user_logged_in_recently(user, days: int = 3) -> bool:
    """Check if user logged in within the last N days."""
    from datetime import timedelta
    from django.utils import timezone as tz
    last_login = getattr(user, 'last_login', None)
    if not last_login:
        return False
    return last_login >= tz.now() - timedelta(days=days)
