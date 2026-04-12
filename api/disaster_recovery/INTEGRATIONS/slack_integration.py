"""
Slack Integration — Post DR alerts and notifications to Slack channels.
"""
import logging, json, urllib.request
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


class SlackIntegration:
    """
    Slack notification integration with rich message blocks,
    severity-based color coding, and multiple channel routing.
    """

    def __init__(self, webhook_url: str, config: dict = None):
        self.webhook_url = webhook_url
        self.config = config or {}
        self.username = config.get("username","DR System") if config else "DR System"
        self.icon_emoji = config.get("icon_emoji",":shield:") if config else ":shield:"
        self.alert_channel_url = config.get("alert_channel_url", webhook_url) if config else webhook_url
        self.incident_channel_url = config.get("incident_channel_url", webhook_url) if config else webhook_url

    def post(self, text: str, color: str = "#0078D4", title: str = None, fields: List[dict] = None, url: str = None) -> bool:
        """Post a message to Slack."""
        attachment = {"color": color, "text": text,
                      "footer": f"DR System | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                      "mrkdwn_in": ["text"]}
        if title: attachment["title"] = title
        if fields: attachment["fields"] = fields
        return self._send({"username": self.username, "icon_emoji": self.icon_emoji,
                            "attachments": [attachment]}, url or self.webhook_url)

    def post_alert(self, alert: dict) -> bool:
        """Post an alert notification."""
        severity = str(alert.get("severity","info")).lower()
        colors = {"critical":"#FF0000","error":"#FF4444","warning":"#FFAA00","info":"#0078D4"}
        emojis = {"critical":"🚨","error":"❌","warning":"⚠️","info":"ℹ️"}
        attachment = {
            "color": colors.get(severity,"#888888"),
            "title": f"{emojis.get(severity,'•')} [{severity.upper()}] {alert.get('rule_name','')}",
            "text": alert.get("message",""),
            "fields": [{"title":"Metric","value":str(alert.get("metric","")),"short":True},
                       {"title":"Value","value":str(alert.get("value","")),"short":True},
                       {"title":"Threshold","value":str(alert.get("threshold","")),"short":True},
                       {"title":"Fired At","value":str(alert.get("fired_at","")),"short":True}],
            "footer": "DR System Alerting", "ts": int(datetime.utcnow().timestamp())}
        url = self.config.get("critical_channel_url", self.alert_channel_url) if severity == "critical" else self.alert_channel_url
        return self._send({"username": self.username, "icon_emoji": self.icon_emoji,
                            "attachments": [attachment]}, url)

    def post_incident(self, incident: dict) -> bool:
        """Post an incident notification."""
        severity = str(incident.get("severity","")).upper()
        colors = {"SEV1":"#FF0000","SEV2":"#FF6600","SEV3":"#FFAA00","SEV4":"#0078D4"}
        attachment = {"color": colors.get(severity,"#888888"),
                      "title": f"🔴 Incident [{severity}]: {incident.get('title','')[:100]}",
                      "text": incident.get("description","")[:500],
                      "fields": [{"title":"ID","value":str(incident.get("id",""))[:12]+"...","short":True},
                                  {"title":"Status","value":str(incident.get("status","")),"short":True},
                                  {"title":"Severity","value":severity,"short":True},
                                  {"title":"Affected","value":", ".join(incident.get("affected_systems",[]))[:200],"short":True}],
                      "ts": int(datetime.utcnow().timestamp())}
        return self._send({"username": self.username, "icon_emoji": ":rotating_light:",
                            "attachments": [attachment]}, self.incident_channel_url)

    def post_failover_event(self, failover: dict) -> bool:
        """Post failover notification."""
        fo_type = str(failover.get("failover_type","")).upper()
        text = (f"⚡ *FAILOVER {fo_type}*\n"
                f"Primary: `{failover.get('primary_node','')}` → Secondary: `{failover.get('secondary_node','')}`\n"
                f"Reason: {failover.get('trigger_reason','')[:200]}")
        return self.post(text=text, color="#FF0000" if fo_type=="AUTOMATIC" else "#FF9900", title="Failover Event")

    def post_backup_summary(self, stats: dict) -> bool:
        """Post daily backup summary."""
        s = stats.get("status_counts",{}).get("completed",0)
        f = stats.get("status_counts",{}).get("failed",0)
        total = stats.get("total_jobs",0)
        return self.post(f"📦 *Daily Backup Summary*\n✅ {s} | ❌ {f} | Total: {total}",
                          color="#00CC00" if f==0 else "#FF0000")

    def post_drill_result(self, drill: dict) -> bool:
        """Post drill result."""
        passed = drill.get("passed",False)
        return self.post(f"{'✅' if passed else '❌'} *DR Drill {'PASSED' if passed else 'FAILED'}*\n{drill.get('name','')}",
                          color="#00CC00" if passed else "#FF0000")

    def post_status_update(self, component: str, old_status: str, new_status: str, message: str = "") -> bool:
        colors = {"down":"#FF0000","critical":"#FF0000","degraded":"#FFAA00","healthy":"#00CC00"}
        emojis = {"down":"🔴","critical":"🔴","degraded":"🟡","healthy":"🟢"}
        new_s = str(new_status).lower()
        return self.post(f"{emojis.get(new_s,'•')} `{component}`: {old_status} → *{new_status}*\n{message}",
                          color=colors.get(new_s,"#888888"))

    def _send(self, payload: dict, url: str = None) -> bool:
        target = url or self.webhook_url
        if not target: return False
        try:
            data = json.dumps(payload, default=str).encode()
            req = urllib.request.Request(target, data=data,
                                          headers={"Content-Type":"application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Slack send error: {e}"); return False
