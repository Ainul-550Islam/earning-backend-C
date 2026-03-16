# api/promotions/monitoring/alert_system.py
# Alert System — Multi-channel alerts (Slack, Email, SMS, PagerDuty)
import logging, time
from dataclasses import dataclass
from enum import Enum
from django.conf import settings
from django.core.cache import cache
logger = logging.getLogger('monitoring.alert')

class AlertSeverity(str, Enum):
    INFO     = 'info'
    WARNING  = 'warning'
    CRITICAL = 'critical'
    EMERGENCY = 'emergency'

@dataclass
class Alert:
    title:    str
    message:  str
    severity: AlertSeverity
    category: str    # 'fraud', 'system', 'financial', 'security'
    metadata: dict   = None

class AlertSystem:
    COOLDOWN = 300  # 5 min between same alerts

    def send(self, alert: Alert) -> bool:
        cooldown_key = f'alert:cd:{alert.category}:{alert.title[:20]}'
        if cache.get(cooldown_key):
            return False
        cache.set(cooldown_key, True, timeout=self.COOLDOWN)

        sent = False
        if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY):
            sent = self._slack(alert) or sent
            sent = self._email(alert) or sent
        elif alert.severity == AlertSeverity.WARNING:
            sent = self._slack(alert) or sent
        else:
            logger.info(f'Alert [{alert.severity}] {alert.title}: {alert.message}')
            sent = True

        logger.warning(f'ALERT [{alert.severity}] {alert.category}: {alert.title}')
        return sent

    def send_fraud_alert(self, campaign_id: int, user_id: int, details: dict) -> bool:
        return self.send(Alert(
            f'Fraud Detected: Campaign #{campaign_id}',
            f'User #{user_id} — score={details.get("score",0):.2f} type={details.get("type","unknown")}',
            AlertSeverity.CRITICAL, 'fraud', details,
        ))

    def send_system_alert(self, component: str, error: str, severity: AlertSeverity = AlertSeverity.WARNING) -> bool:
        return self.send(Alert(f'System Error: {component}', error, severity, 'system'))

    def send_financial_alert(self, title: str, message: str) -> bool:
        return self.send(Alert(title, message, AlertSeverity.WARNING, 'financial'))

    def _slack(self, alert: Alert) -> bool:
        webhook = getattr(settings, 'SLACK_ALERT_WEBHOOK', None)
        if not webhook:
            return False
        try:
            import requests
            emoji = {'info':'ℹ️','warning':'⚠️','critical':'🔴','emergency':'🚨'}.get(alert.severity,'📢')
            requests.post(webhook, json={
                'text': f'{emoji} *[{alert.severity.upper()}] {alert.title}*\n{alert.message}',
                'attachments': [{'color': {'critical':'danger','warning':'warning'}.get(alert.severity,'good'),
                                 'fields': [{'title': k, 'value': str(v), 'short': True} for k, v in (alert.metadata or {}).items()]}]
            }, timeout=5)
            return True
        except Exception as e:
            logger.error(f'Slack alert failed: {e}')
            return False

    def _email(self, alert: Alert) -> bool:
        emails = getattr(settings, 'ALERT_EMAILS', [])
        if not emails:
            return False
        try:
            from django.core.mail import send_mail
            send_mail(f'[{alert.severity.upper()}] {alert.title}', alert.message, None, emails, fail_silently=True)
            return True
        except Exception:
            return False
