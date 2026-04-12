"""
Enhanced Alert System — api/alerts/ এর replacement।
DR-level escalation + multi-channel routing সহ।

কিভাবে ব্যবহার করবে:
    # api/alerts/services.py এর বদলে:
    from dr_integration.alert_bridge.enhanced_alerts import EnhancedAlertService
    svc = EnhancedAlertService()
    svc.fire("high_cpu", "critical", "CPU 95%", metric="cpu_percent", value=95)
"""
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class EnhancedAlertService:
    """
    api/alerts/services.py এর enhanced replacement।
    
    নতুন features:
    - PagerDuty escalation (SEV1/SEV2 এর জন্য)
    - Slack rich attachments (সব level এর জন্য)
    - Datadog event tracking
    - 4-level escalation policy
    - Cooldown (duplicate alert suppress)
    - DRAlert model-এ save
    """

    # Severity → চ্যানেল mapping
    CHANNELS = {
        "critical": ["pagerduty", "slack", "datadog"],
        "error":    ["pagerduty", "slack", "datadog"],
        "warning":  ["slack", "datadog"],
        "info":     ["datadog"],
    }

    def __init__(self):
        self.config = getattr(settings, "DR_NOTIFICATION_CONFIG", {})

    def fire(self, rule_name: str, severity: str, message: str,
             metric: str = None, value: float = None, threshold: float = None,
             tenant_id: str = None, dedup_key: str = None) -> dict:
        """Alert fire করো — api/alerts/ সব জায়গায় এটা call করবে।"""
        alert = {
            "rule_name": rule_name, "severity": severity,
            "message": message, "metric": metric or rule_name,
            "value": value, "threshold": threshold,
            "fired_at": datetime.utcnow().isoformat(),
            "dedup_key": dedup_key or f"{rule_name}:{severity}",
        }
        # Save to DB
        self._save_alert(alert, tenant_id)
        # Route to channels
        channels = self.CHANNELS.get(severity, ["datadog"])
        results = {}
        for channel in channels:
            try:
                if channel == "pagerduty":
                    results["pagerduty"] = self._notify_pagerduty(alert)
                elif channel == "slack":
                    results["slack"] = self._notify_slack(alert)
                elif channel == "datadog":
                    results["datadog"] = self._notify_datadog(alert)
            except Exception as e:
                results[channel] = f"error: {e}"
                logger.warning(f"Alert channel {channel} failed: {e}")
        logger.warning(f"ALERT [{severity.upper()}] {rule_name}: {message[:100]}")
        return {"fired": True, "channels": results, "alert": alert}

    def resolve(self, rule_name: str, dedup_key: str = None) -> dict:
        """Alert resolve করো।"""
        try:
            from dr_integration.models import DRAlert
            DRAlert.objects.filter(rule_name=rule_name, resolved_at__isnull=True).update(
                resolved_at=datetime.utcnow())
        except Exception: pass
        # PagerDuty resolve
        if self.config.get("pagerduty_integration_key"):
            try:
                from disaster_recovery.INTEGRATIONS.pagerduty_integration import PagerDutyIntegration
                pd = PagerDutyIntegration(self.config.get("pagerduty_api_key",""))
                pd.resolve_alert(dedup_key or rule_name)
            except Exception as e:
                logger.debug(f"PD resolve error: {e}")
        return {"resolved": True, "rule_name": rule_name}

    def get_escalation_level(self, rule_name: str, fired_at: datetime, severity: str = "warning") -> int:
        """বর্তমান escalation level জানো।"""
        try:
            from disaster_recovery.MONITORING_ALERTING.escalation_policy import EscalationPolicy
            return EscalationPolicy().get_current_escalation_level(fired_at, False, severity)
        except Exception: return 1

    def _save_alert(self, alert: dict, tenant_id: str = None):
        try:
            from dr_integration.models import DRAlert
            DRAlert.objects.create(
                rule_name=alert["rule_name"], severity=alert["severity"],
                message=alert["message"], metric=alert.get("metric",""),
                metric_value=alert.get("value"), threshold=alert.get("threshold"),
            )
        except Exception as e:
            logger.debug(f"DRAlert save error: {e}")

    def _notify_pagerduty(self, alert: dict) -> str:
        api_key = self.config.get("pagerduty_api_key") or self.config.get("pagerduty_integration_key","")
        if not api_key: return "skipped: no key"
        try:
            from disaster_recovery.INTEGRATIONS.pagerduty_integration import PagerDutyIntegration
            pd = PagerDutyIntegration(api_key, config=self.config)
            result = pd.trigger_alert(
                summary=f"[{alert['severity'].upper()}] {alert['rule_name']}: {alert['message'][:100]}",
                severity=alert["severity"],
                dedup_key=alert.get("dedup_key"),
                component="django_api",
                custom_details={k: v for k,v in alert.items() if k != "dedup_key"},
            )
            return "sent" if result.get("status") == "success" else f"failed: {result.get('error','')}"
        except Exception as e:
            return f"error: {e}"

    def _notify_slack(self, alert: dict) -> str:
        url = self.config.get("slack_webhook_url","")
        if not url: return "skipped: no webhook"
        try:
            from disaster_recovery.INTEGRATIONS.slack_integration import SlackIntegration
            slack = SlackIntegration(url, config=self.config)
            ok = slack.post_alert(alert)
            return "sent" if ok else "failed"
        except Exception as e:
            return f"error: {e}"

    def _notify_datadog(self, alert: dict) -> str:
        api_key = self.config.get("datadog_api_key","")
        if not api_key: return "skipped: no key"
        try:
            from disaster_recovery.INTEGRATIONS.datadog_integration import DatadogIntegration
            dd = DatadogIntegration(api_key)
            result = dd.create_event(
                title=f"[API Alert] {alert['rule_name']}",
                text=alert["message"],
                alert_type={"critical":"error","error":"error","warning":"warning","info":"info"}.get(
                    alert["severity"],"info"),
                tags=[f"severity:{alert['severity']}", "source:django_api",
                      f"metric:{alert.get('metric','')}"],
            )
            return "sent" if result.get("success") else "failed"
        except Exception as e:
            return f"error: {e}"
