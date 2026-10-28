"""
PagerDuty Service — create/resolve incidents via Events API v2
"""
import logging
from ._shared import get_effective_alert_log
import requests

logger = logging.getLogger(__name__)

SEVERITY_MAP = {
    'low': 'info',
    'medium': 'warning',
    'high': 'error',
    'critical': 'critical',
}


class PagerDutyService:
    """Manage PagerDuty incidents"""

    EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

    @staticmethod
    def send(notification, channel):
        """Trigger a PagerDuty incident"""
        try:
            config = channel.config
            routing_key = config.get('routing_key')
            if not routing_key:
                logger.error("PagerDuty routing_key not configured")
                return False

            alert_log = get_effective_alert_log(notification)
            payload = {
                "routing_key": routing_key,
                "event_action": "trigger",
                "dedup_key": f"alert-{alert_log.id}",
                "payload": {
                    "summary": notification.message,
                    "severity": SEVERITY_MAP.get(alert_log.rule.severity, 'warning'),
                    "source": alert_log.rule.name,
                    "custom_details": {
                        "trigger_value": alert_log.trigger_value,
                        "threshold_value": alert_log.threshold_value,
                        "alert_type": alert_log.rule.alert_type,
                    }
                }
            }

            resp = requests.post(PagerDutyService.EVENTS_URL, json=payload, timeout=10)
            resp.raise_for_status()

            channel.record_success()
            logger.info(f"PagerDuty incident triggered for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"PagerDutyService error: {e}")
            channel.record_failure()
            return False

    @staticmethod
    def resolve(alert_log, channel):
        """Resolve a PagerDuty incident"""
        try:
            config = channel.config
            routing_key = config.get('routing_key')
            if not routing_key:
                return False

            payload = {
                "routing_key": routing_key,
                "event_action": "resolve",
                "dedup_key": f"alert-{alert_log.id}",
            }

            resp = requests.post(PagerDutyService.EVENTS_URL, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"PagerDuty incident resolved for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"PagerDutyService resolve error: {e}")
            return False
