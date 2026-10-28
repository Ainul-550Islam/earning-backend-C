# api/admin_panel/alert_manager.py
"""Alert rule builder and delivery management."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class AlertManager:
    """Build and manage admin alert rules."""

    ALERT_CHANNELS = ['websocket', 'email', 'push', 'sms', 'webhook']

    @classmethod
    def create_alert_rule(cls, name: str, metric: str, condition: Dict,
                           channels: List[str], actor=None) -> Dict:
        """Create a new alert rule."""
        try:
            from api.alerts.models import AlertRule
            rule = AlertRule.objects.create(
                name=name, metric=metric,
                condition=condition, channels=channels,
                is_active=True,
            )
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='create_alert_rule',
                                  model_name='AlertRule', object_id=str(rule.pk),
                                  changes={'name': name, 'metric': metric})
            return {'success': True, 'rule_id': rule.pk, 'name': name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def fire_alert(cls, alert_type: str, message: str, severity: str = 'medium',
                   data: Dict = None) -> Dict:
        """Fire an alert through all configured channels."""
        results = {}
        try:
            from api.alerts.models import AlertLog
            alert = AlertLog.objects.create(
                alert_type=alert_type, severity=severity,
                message=message, data=data or {}, status='active'
            )
            results['created'] = alert.pk
            # WebSocket broadcast
            if severity in ('critical', 'high'):
                cache.set(f'admin_panel:critical_alert:{alert.pk}', {
                    'type': alert_type, 'message': message, 'severity': severity
                }, 3600)
        except Exception as e:
            results['error'] = str(e)
        return results

    @classmethod
    def get_active_alerts(cls, severity: str = '') -> List[Dict]:
        try:
            from api.alerts.models import AlertLog
            qs = AlertLog.objects.filter(status='active')
            if severity:
                qs = qs.filter(severity=severity)
            return list(qs.values('id', 'alert_type', 'severity', 'message', 'created_at')
                        .order_by('-severity', '-created_at')[:100])
        except Exception:
            return []

    @classmethod
    def acknowledge_alert(cls, alert_id: Any, actor) -> bool:
        try:
            from api.alerts.models import AlertLog
            AlertLog.objects.filter(pk=alert_id).update(
                status='acknowledged',
                acknowledged_by=actor,
                acknowledged_at=timezone.now()
            )
            return True
        except Exception:
            return False

    @classmethod
    def get_alert_stats(cls, days: int = 7) -> Dict:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.alerts.models import AlertLog
            from django.db.models import Count
            return {
                'total': AlertLog.objects.filter(created_at__gte=cutoff).count(),
                'by_severity': list(AlertLog.objects.filter(created_at__gte=cutoff)
                               .values('severity').annotate(c=Count('id')).order_by('-c')),
                'active': AlertLog.objects.filter(status='active').count(),
                'period_days': days,
            }
        except Exception:
            return {}

alert_manager = AlertManager()