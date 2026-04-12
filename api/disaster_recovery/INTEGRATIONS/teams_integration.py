"""
Microsoft Teams Integration — Send DR notifications to Teams channels.
"""
import logging
import json
import urllib.request
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class TeamsIntegration:
    """
    Microsoft Teams DR notification integration.
    Uses Incoming Webhooks to post rich adaptive cards to Teams channels.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.webhook_url = config.get("webhook_url", "") if config else ""
        self.alert_channel_url = config.get("alert_channel_url", "") if config else ""
        self.incident_channel_url = config.get("incident_channel_url", "") if config else ""

    def send_message(self, title: str, body: str, color: str = "0078D4",
                      url: str = None) -> bool:
        """Send a simple message card to Teams."""
        target_url = url or self.webhook_url
        if not target_url:
            logger.warning("Teams webhook URL not configured")
            return False
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [{
                "activityTitle": title,
                "activityText": body,
                "activitySubtitle": f"DR System — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            }]
        }
        return self._post(card, target_url)

    def send_alert(self, alert: dict) -> bool:
        """Send an alert notification as a Teams message card."""
        severity = str(alert.get("severity", "info")).upper()
        color_map = {
            "CRITICAL": "FF0000", "ERROR": "FF6600",
            "WARNING": "FFCC00", "INFO": "0078D4"
        }
        color = color_map.get(severity, "888888")
        target_url = self.alert_channel_url or self.webhook_url
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"DR Alert: {alert.get('rule_name', '')}",
            "sections": [{
                "activityTitle": f"🚨 [{severity}] DR System Alert",
                "activitySubtitle": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "activityText": alert.get("message", ""),
                "facts": [
                    {"name": "Rule", "value": alert.get("rule_name", "")},
                    {"name": "Metric", "value": alert.get("metric", "")},
                    {"name": "Value", "value": str(alert.get("value", ""))},
                    {"name": "Threshold", "value": str(alert.get("threshold", ""))},
                ]
            }]
        }
        return self._post(card, target_url)

    def send_incident_notification(self, incident: dict) -> bool:
        """Send an incident creation or update notification."""
        severity = str(incident.get("severity", "")).upper()
        color_map = {"SEV1": "FF0000", "SEV2": "FF6600", "SEV3": "FFCC00", "SEV4": "0078D4"}
        color = color_map.get(severity, "888888")
        target_url = self.incident_channel_url or self.webhook_url
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"Incident: {incident.get('title', '')}",
            "sections": [{
                "activityTitle": f"🔴 Incident [{severity}]: {incident.get('title', '')}",
                "activitySubtitle": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "activityText": incident.get("description", "No description provided."),
                "facts": [
                    {"name": "Incident ID", "value": incident.get("id", "")[:8] + "..."},
                    {"name": "Status", "value": str(incident.get("status", ""))},
                    {"name": "Severity", "value": severity},
                    {"name": "Affected", "value": ", ".join(incident.get("affected_systems", []))},
                    {"name": "Assigned To", "value": incident.get("assigned_to", "Unassigned")},
                ]
            }],
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "View Incident",
                "targets": [{"os": "default", "uri": f"https://dr-system/incidents/{incident.get('id','')}"}]
            }]
        }
        return self._post(card, target_url)

    def send_failover_notification(self, failover_event: dict) -> bool:
        """Notify Teams channel about a failover event."""
        color = "FF0000" if failover_event.get("failover_type") == "automatic" else "FF9900"
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": "DR Failover Triggered",
            "sections": [{
                "activityTitle": "⚡ Failover Event",
                "activitySubtitle": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "activityText": (
                    f"Failover from **{failover_event.get('primary_node')}** "
                    f"to **{failover_event.get('secondary_node')}**"
                ),
                "facts": [
                    {"name": "Type", "value": str(failover_event.get("failover_type", ""))},
                    {"name": "Status", "value": str(failover_event.get("status", ""))},
                    {"name": "Triggered By", "value": failover_event.get("triggered_by", "auto")},
                    {"name": "Reason", "value": failover_event.get("trigger_reason", "")[:200]},
                ]
            }]
        }
        return self._post(card, self.webhook_url)

    def send_backup_summary(self, stats: dict) -> bool:
        """Send a daily backup summary to Teams."""
        success_count = stats.get("status_counts", {}).get("completed", 0)
        failed_count = stats.get("status_counts", {}).get("failed", 0)
        color = "FF0000" if failed_count > 0 else "00CC00"
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": "Daily Backup Summary",
            "sections": [{
                "activityTitle": "📦 Daily Backup Summary",
                "activitySubtitle": datetime.utcnow().strftime("%Y-%m-%d"),
                "facts": [
                    {"name": "Successful", "value": str(success_count)},
                    {"name": "Failed", "value": str(failed_count)},
                    {"name": "Latest Backup", "value": stats.get("latest_backup", "N/A")},
                    {"name": "Total Jobs", "value": str(stats.get("total_jobs", 0))},
                ]
            }]
        }
        return self._post(card, self.webhook_url)

    def send_adaptive_card(self, card_body: dict, url: str = None) -> bool:
        """Send a raw Adaptive Card for maximum flexibility."""
        target_url = url or self.webhook_url
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_body,
            }]
        }
        return self._post(payload, target_url)

    def _post(self, payload: dict, url: str) -> bool:
        """HTTP POST to Teams webhook URL."""
        data = json.dumps(payload, default=str).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Teams notification failed: {e}")
            return False
