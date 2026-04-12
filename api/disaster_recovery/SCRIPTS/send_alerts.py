#!/usr/bin/env python3
"""
Script: Send test or manual alerts via configured notification channels.
Usage: python send_alerts.py --message "Test alert" --severity warning --channel slack
"""
import sys
import os
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Send DR system alerts manually")
    parser.add_argument("--message", required=True, help="Alert message")
    parser.add_argument("--severity", choices=["info", "warning", "error", "critical"],
                         default="info")
    parser.add_argument("--channel", choices=["slack", "pagerduty", "teams", "email", "all"],
                         default="slack")
    parser.add_argument("--rule-name", type=str, default="manual_alert")
    args = parser.parse_args()

    from disaster_recovery.config import settings
    alert = {
        "rule_name": args.rule_name,
        "message": args.message,
        "severity": args.severity,
        "fired_at": datetime.utcnow().isoformat(),
        "source": "manual_script",
    }

    logger.info(f"Sending [{args.severity.upper()}] alert via {args.channel}: {args.message}")

    channels_to_notify = []
    if args.channel == "all":
        channels_to_notify = ["slack", "pagerduty", "teams", "email"]
    else:
        channels_to_notify = [args.channel]

    results = {}
    for channel in channels_to_notify:
        try:
            if channel == "slack" and settings.notifications.slack_webhook_url:
                from disaster_recovery.INTEGRATIONS.slack_integration import SlackIntegration
                slack = SlackIntegration(settings.notifications.slack_webhook_url)
                success = slack.post_alert(alert)
                results["slack"] = "sent" if success else "failed"

            elif channel == "pagerduty" and settings.notifications.pagerduty_api_key:
                from disaster_recovery.INTEGRATIONS.pagerduty_integration import PagerDutyIntegration
                pd = PagerDutyIntegration(settings.notifications.pagerduty_api_key)
                result = pd.trigger_alert(args.message, severity=args.severity)
                results["pagerduty"] = "sent" if result.get("status") == 202 else "failed"

            elif channel == "teams" and hasattr(settings, "teams_webhook_url"):
                from disaster_recovery.INTEGRATIONS.teams_integration import TeamsIntegration
                teams = TeamsIntegration({"webhook_url": getattr(settings, "teams_webhook_url", "")})
                success = teams.send_alert(alert)
                results["teams"] = "sent" if success else "failed"

            elif channel == "email" and settings.notifications.smtp_host:
                from disaster_recovery.MONITORING_ALERTING.notification_dispatcher import NotificationDispatcher
                dispatcher = NotificationDispatcher({
                    "smtp_host": settings.notifications.smtp_host,
                    "smtp_port": settings.notifications.smtp_port,
                    "smtp_user": settings.notifications.smtp_user,
                    "smtp_password": settings.notifications.smtp_password,
                    "alert_emails": settings.notifications.alert_emails,
                })
                dispatcher._send_email(alert)
                results["email"] = "sent"
            else:
                results[channel] = "skipped (not configured)"
        except Exception as e:
            results[channel] = f"error: {e}"
            logger.error(f"  {channel}: failed — {e}")

    for channel, status in results.items():
        icon = "✅" if status == "sent" else ("⏭️" if "skipped" in status else "❌")
        logger.info(f"  {icon} {channel}: {status}")


if __name__ == "__main__":
    main()
