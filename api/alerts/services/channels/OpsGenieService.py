"""
OpsGenie Service — alert management via OpsGenie API v2
"""
import logging
from ._shared import get_effective_alert_log
import requests

logger = logging.getLogger(__name__)

PRIORITY_MAP = {
    'low': 'P5',
    'medium': 'P3',
    'high': 'P2',
    'critical': 'P1',
}


class OpsGenieService:
    """Manage OpsGenie alerts"""

    CREATE_URL = "https://api.opsgenie.com/v2/alerts"

    @staticmethod
    def send(notification, channel):
        """Create an OpsGenie alert"""
        try:
            config = channel.config
            api_key = config.get('api_key')
            if not api_key:
                logger.error("OpsGenie api_key not configured")
                return False

            alert_log = get_effective_alert_log(notification)
            payload = {
                "message": notification.message[:130],
                "alias": f"alert-{alert_log.id}",
                "description": notification.message,
                "priority": PRIORITY_MAP.get(alert_log.rule.severity, 'P3'),
                "details": {
                    "rule": alert_log.rule.name,
                    "trigger_value": str(alert_log.trigger_value),
                    "threshold_value": str(alert_log.threshold_value),
                    "alert_type": alert_log.rule.alert_type,
                }
            }

            headers = {
                "Authorization": f"GenieKey {api_key}",
                "Content-Type": "application/json",
            }

            resp = requests.post(OpsGenieService.CREATE_URL, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()

            channel.record_success()
            logger.info(f"OpsGenie alert created for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"OpsGenieService error: {e}")
            channel.record_failure()
            return False

    @staticmethod
    def close(alert_log, channel):
        """Close an OpsGenie alert"""
        try:
            config = channel.config
            api_key = config.get('api_key')
            if not api_key:
                return False

            alias = f"alert-{alert_log.id}"
            url = f"{OpsGenieService.CREATE_URL}/{alias}/close"
            headers = {"Authorization": f"GenieKey {api_key}"}

            resp = requests.post(url, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"OpsGenie alert closed for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"OpsGenieService close error: {e}")
            return False
