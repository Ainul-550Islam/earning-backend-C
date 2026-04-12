"""Notification Dispatcher — Sends alerts via Slack, PagerDuty, email, SMS."""
import logging, json
from datetime import datetime
logger = logging.getLogger(__name__)

class NotificationDispatcher:
    def __init__(self, config: dict):
        self.config = config

    def dispatch(self, alert: dict):
        channels = self.config.get("channels", ["slack"])
        for ch in channels:
            try:
                getattr(self, f"_send_{ch}")(alert)
            except Exception as e:
                logger.error(f"Notification failed [{ch}]: {e}")

    def dispatch_resolution(self, alert: dict):
        alert["resolved"] = True
        self.dispatch(alert)

    def _send_slack(self, alert: dict):
        import urllib.request, urllib.parse
        url = self.config.get("slack_webhook_url", "")
        if not url:
            logger.debug("Slack webhook not configured")
            return
        color = {"critical": "#FF0000", "error": "#FF6600", "warning": "#FFCC00", "info": "#36A64F"}.get(str(alert.get("severity","info")), "#888888")
        payload = {"attachments": [{"color": color, "title": f"[{str(alert.get('severity','info')).upper()}] {alert.get('rule_name','')}",
                                     "text": alert.get("message", ""), "ts": datetime.utcnow().timestamp()}]}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        logger.info("Slack notification sent")

    def _send_pagerduty(self, alert: dict):
        import urllib.request, json
        api_key = self.config.get("pagerduty_api_key", "")
        if not api_key:
            return
        payload = {"routing_key": api_key, "event_action": "trigger",
                   "payload": {"summary": alert.get("message", ""), "severity": str(alert.get("severity","error")),
                                "source": "DR System", "timestamp": datetime.utcnow().isoformat()}}
        data = json.dumps(payload).encode()
        req = urllib.request.Request("https://events.pagerduty.com/v2/enqueue", data=data,
                                      headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)

    def _send_email(self, alert: dict):
        import smtplib
        from email.mime.text import MIMEText
        cfg = self.config
        if not cfg.get("smtp_host"):
            return
        msg = MIMEText(alert.get("message", ""))
        msg["Subject"] = f"[DR ALERT] {alert.get('rule_name','')} - {alert.get('severity','')}"
        msg["From"] = cfg.get("smtp_user", "dr@system.com")
        msg["To"] = ", ".join(cfg.get("alert_emails", []))
        with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587)) as s:
            s.starttls()
            s.login(cfg["smtp_user"], cfg["smtp_password"])
            s.send_message(msg)
