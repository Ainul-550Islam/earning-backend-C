"""
tasks/services/TaskAlertService.py
Evaluate alert rules and fire notifications on failure/slow/missing tasks.
"""
import logging
from typing import Dict, Any, List
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class TaskAlertService:
    """
    Evaluates all active TaskAlert rules against current metrics.
    Fires configured notification channels when thresholds are breached.
    Respects cooldown windows to prevent alert fatigue.
    """

    def evaluate_all(self) -> List[Dict]:
        """
        Evaluate every active TaskAlert rule.
        Returns a list of fired alert dicts.
        """
        fired = []
        try:
            from api.tasks.models.monitoring import TaskAlert

            alerts = TaskAlert.objects.filter(is_active=True)
            for alert in alerts:
                result = self.evaluate_alert(alert)
                if result.get('fired'):
                    fired.append(result)

        except Exception as e:
            logger.error(f"[ERROR] TaskAlertService.evaluate_all: {e}")

        return fired

    def evaluate_alert(self, alert) -> Dict[str, Any]:
        """
        Evaluate a single TaskAlert instance.
        Returns {'fired': bool, 'reason': str, 'value': float}.
        """
        try:
            if alert.is_in_cooldown:
                return {'fired': False, 'reason': 'in_cooldown'}

            alert_type = alert.alert_type
            evaluator  = getattr(self, f'_eval_{alert_type}', None)

            if not evaluator:
                logger.warning(f"[WARN] No evaluator for alert type: {alert_type}")
                return {'fired': False, 'reason': 'unknown_type'}

            value, exceeded = evaluator(alert)

            if exceeded:
                alert.record_trigger()
                self._dispatch_alert(alert, value)
                return {
                    'fired': True,
                    'alert_id': alert.pk,
                    'task_name': alert.task_name,
                    'alert_type': alert_type,
                    'value': value,
                    'threshold': alert.threshold,
                    'severity': alert.severity,
                }

            return {'fired': False, 'value': value}

        except Exception as e:
            logger.error(f"[ERROR] TaskAlertService.evaluate_alert {alert.pk}: {e}")
            return {'fired': False, 'error': str(e)}

    def trigger_manual(self, alert_id: int) -> Dict[str, Any]:
        """Manually fire an alert (for testing)."""
        try:
            from api.tasks.models.monitoring import TaskAlert

            alert = TaskAlert.objects.get(pk=alert_id, is_active=True)
            alert.record_trigger()
            self._dispatch_alert(alert, value=0.0, manual=True)
            return {'success': True, 'alert_id': alert_id}

        except Exception as e:
            logger.error(f"[ERROR] TaskAlertService.trigger_manual {alert_id}: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Evaluators per alert type ────────────────────────────────────

    def _eval_failure(self, alert) -> tuple:
        """Fire if failure_rate > threshold% in last 1 hour."""
        try:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from django.db.models import Count, Q

            cutoff = timezone.now() - timedelta(hours=1)
            qs     = TaskPerformanceLog.objects.filter(created_at__gte=cutoff)

            if alert.task_name != '*':
                qs = qs.filter(task_name=alert.task_name)

            agg = qs.aggregate(
                total=Count('id'),
                failures=Count('id', filter=Q(result='failure')),
            )
            total    = agg['total'] or 0
            failures = agg['failures'] or 0
            rate     = (failures / total * 100) if total > 0 else 0.0

            return rate, rate > alert.threshold

        except Exception:
            return 0.0, False

    def _eval_slow(self, alert) -> tuple:
        """Fire if average duration > threshold seconds in last 1 hour."""
        try:
            from api.tasks.models.monitoring import TaskMonitor

            qs = TaskMonitor.objects.all()
            if alert.task_name != '*':
                qs = qs.filter(task_name=alert.task_name)

            monitor = qs.first()
            if not monitor:
                return 0.0, False

            avg_dur = monitor.avg_duration_seconds or 0.0
            return avg_dur, avg_dur > alert.threshold

        except Exception:
            return 0.0, False

    def _eval_missing(self, alert) -> tuple:
        """Fire if task has not run in more than threshold minutes."""
        try:
            from api.tasks.models.monitoring import TaskMonitor

            monitor = TaskMonitor.objects.filter(task_name=alert.task_name).first()
            if not monitor or not monitor.last_run_at:
                # Never run → definitely missing
                return float('inf'), True

            minutes_since = (timezone.now() - monitor.last_run_at).total_seconds() / 60
            return minutes_since, minutes_since > alert.threshold

        except Exception:
            return 0.0, False

    def _eval_dlq(self, alert) -> tuple:
        """Fire if DLQ size exceeds threshold."""
        try:
            from api.tasks.models.queue import TaskDeadLetterQueue

            qs = TaskDeadLetterQueue.objects.filter(reprocess_status='pending')
            if alert.task_name != '*':
                qs = qs.filter(task_name=alert.task_name)

            count = qs.count()
            return float(count), count > alert.threshold

        except Exception:
            return 0.0, False

    def _eval_depth(self, alert) -> tuple:
        """Fire if queue depth exceeds threshold."""
        try:
            from api.tasks.services.QueueDepthService import QueueDepthService

            svc   = QueueDepthService()
            info  = svc.get_queue_depth(alert.task_name)  # task_name stores queue name for depth alerts
            depth = info.get('depth', 0)
            return float(depth), depth > alert.threshold

        except Exception:
            return 0.0, False

    # ─── Notification dispatch ────────────────────────────────────────

    def _dispatch_alert(self, alert, value: float, manual: bool = False) -> None:
        """
        Send alert notification to all configured channels.
        Supported channels: email:addr, slack:#channel, webhook:url
        """
        channels  = alert.notification_channels or []
        task_name = alert.task_name
        msg = (
            f"[{'MANUAL' if manual else alert.severity.upper()}] "
            f"TaskAlert fired: {alert.alert_type} for '{task_name}' "
            f"– value={value:.2f} threshold={alert.threshold}"
        )
        logger.warning(f"[ALERT] {msg}")

        for channel in channels:
            try:
                if channel.startswith('email:'):
                    self._send_email_alert(channel[6:], msg, alert)
                elif channel.startswith('slack:'):
                    self._send_slack_alert(channel[6:], msg, alert)
                elif channel.startswith('webhook:'):
                    self._send_webhook_alert(channel[8:], msg, alert, value)
            except Exception as ch_err:
                logger.error(f"[ERROR] Alert channel '{channel}': {ch_err}")

    def _send_email_alert(self, email: str, msg: str, alert) -> None:
        from django.core.mail import send_mail
        from django.conf import settings

        send_mail(
            subject=f"[Alert] {alert.alert_type} – {alert.task_name}",
            message=msg,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@example.com'),
            recipient_list=[email],
            fail_silently=True,
        )

    def _send_slack_alert(self, channel: str, msg: str, alert) -> None:
        import requests
        from django.conf import settings

        webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', '')
        if not webhook_url:
            return

        requests.post(
            webhook_url,
            json={'text': f'*{channel}*\n{msg}'},
            timeout=5,
        )

    def _send_webhook_alert(self, url: str, msg: str, alert, value: float) -> None:
        import requests

        requests.post(
            url,
            json={
                'alert_type': alert.alert_type,
                'task_name': alert.task_name,
                'severity': alert.severity,
                'message': msg,
                'value': value,
                'threshold': alert.threshold,
                'triggered_at': timezone.now().isoformat(),
            },
            timeout=5,
        )
