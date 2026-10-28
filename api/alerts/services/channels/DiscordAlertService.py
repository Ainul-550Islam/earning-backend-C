"""
Discord Alert Service — Discord webhook embed with full alert details
"""
import logging
from ._shared import get_effective_alert_log
import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

# Discord embed color per severity (decimal int)
SEVERITY_COLOR = {
    'low': 3066993,      # green  #2ECC71
    'medium': 16776960,  # yellow #FFFF00
    'high': 16744272,    # orange #FF6600
    'critical': 15158332, # red   #E74C3C
}

SEVERITY_EMOJI = {
    'low': '🟢',
    'medium': '🟡',
    'high': '🟠',
    'critical': '🔴',
}


class DiscordAlertService:
    """Send alerts to Discord via incoming webhook embed"""

    @staticmethod
    def send(notification, channel):
        """
        Send a rich Discord embed notification.

        channel.config expected keys:
            webhook_url  (required)  — Discord webhook URL
            username     (optional)  — Bot display name, default "Alert Bot"
            avatar_url   (optional)  — Bot avatar URL
        """
        try:
            config = channel.config
            webhook_url = config.get('webhook_url')
            if not webhook_url:
                logger.error("DiscordAlertService: webhook_url not configured")
                channel.record_failure()
                return False

            alert_log = get_effective_alert_log(notification)
            rule = alert_log.rule
            severity = rule.severity
            color = SEVERITY_COLOR.get(severity, 8421504)
            emoji = SEVERITY_EMOJI.get(severity, '⚠️')

            # Build embed fields
            fields = [
                {
                    "name": "Severity",
                    "value": f"`{severity.upper()}`",
                    "inline": True,
                },
                {
                    "name": "Alert Type",
                    "value": f"`{rule.alert_type}`",
                    "inline": True,
                },
                {
                    "name": "Trigger Value",
                    "value": f"`{alert_log.trigger_value}`",
                    "inline": True,
                },
                {
                    "name": "Threshold",
                    "value": f"`{alert_log.threshold_value}`",
                    "inline": True,
                },
                {
                    "name": "Triggered At",
                    "value": alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    "inline": False,
                },
            ]

            # Add resolution info if resolved
            if alert_log.is_resolved and alert_log.resolved_at:
                resolution_minutes = (
                    alert_log.resolved_at - alert_log.triggered_at
                ).total_seconds() / 60
                fields.append({
                    "name": "Resolved In",
                    "value": f"`{resolution_minutes:.1f} minutes`",
                    "inline": True,
                })

            embed = {
                "title": f"{emoji} {rule.name}",
                "description": notification.message,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "Alert Monitoring System",
                },
                "timestamp": timezone.now().isoformat(),
            }

            payload = {
                "username": config.get('username', 'Alert Bot'),
                "embeds": [embed],
            }

            if config.get('avatar_url'):
                payload['avatar_url'] = config['avatar_url']

            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

            channel.record_success()
            logger.info(
                f"DiscordAlertService: embed sent for alert {alert_log.id} "
                f"(severity={severity})"
            )
            return True

        except requests.exceptions.Timeout:
            logger.error("DiscordAlertService: request timed out")
            channel.record_failure()
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"DiscordAlertService: HTTP error {e.response.status_code} — {e.response.text}")
            channel.record_failure()
            return False
        except Exception as e:
            logger.error(f"DiscordAlertService: unexpected error — {e}")
            channel.record_failure()
            return False

    @staticmethod
    def send_resolved(alert_log, channel):
        """
        Send a 'resolved' notification embed to Discord.
        Useful when an alert is manually or automatically resolved.
        """
        try:
            config = channel.config
            webhook_url = config.get('webhook_url')
            if not webhook_url:
                return False

            rule = alert_log.rule
            resolution_minutes = None
            if alert_log.resolved_at:
                resolution_minutes = (
                    alert_log.resolved_at - alert_log.triggered_at
                ).total_seconds() / 60

            fields = [
                {"name": "Rule", "value": f"`{rule.name}`", "inline": True},
                {"name": "Severity", "value": f"`{rule.severity.upper()}`", "inline": True},
            ]
            if resolution_minutes is not None:
                fields.append({
                    "name": "Resolution Time",
                    "value": f"`{resolution_minutes:.1f} minutes`",
                    "inline": True,
                })
            if alert_log.resolution_note:
                fields.append({
                    "name": "Note",
                    "value": alert_log.resolution_note,
                    "inline": False,
                })

            embed = {
                "title": f"✅ RESOLVED — {rule.name}",
                "color": 3066993,  # green
                "fields": fields,
                "footer": {"text": "Alert Monitoring System"},
                "timestamp": timezone.now().isoformat(),
            }

            payload = {
                "username": config.get('username', 'Alert Bot'),
                "embeds": [embed],
            }

            resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"DiscordAlertService: resolved embed sent for alert {alert_log.id}")
            return True

        except Exception as e:
            logger.error(f"DiscordAlertService.send_resolved error: {e}")
            return False
