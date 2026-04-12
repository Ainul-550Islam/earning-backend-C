"""
PagerDuty Integration — Trigger, resolve, and manage PagerDuty alerts and incidents.
"""
import logging, json, urllib.request
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class PagerDutyIntegration:
    """
    PagerDuty Events API v2 integration for DR alert escalation.
    """

    EVENTS_API = "https://events.pagerduty.com/v2/enqueue"
    REST_API = "https://api.pagerduty.com"
    SEVERITY_MAP = {"sev1":"critical","sev2":"error","sev3":"warning","sev4":"info",
                    "critical":"critical","error":"error","warning":"warning","info":"info",
                    "high":"error","medium":"warning","low":"info"}

    def __init__(self, api_key: str = None, config: dict = None):
        self.config = config or {}
        self.api_key = api_key or config.get("api_key","") if config else ""
        self.integration_key = config.get("integration_key", api_key) if config else api_key or ""
        self.service_id = config.get("service_id","") if config else ""
        self.from_email = config.get("from_email","dr-system@example.com") if config else "dr-system@example.com"

    def trigger_alert(self, summary: str, severity: str = "error", dedup_key: str = None,
                       source: str = "DR System", component: str = None, details: dict = None,
                       custom_details: dict = None) -> dict:
        """Trigger a PagerDuty alert via Events API v2."""
        pd_severity = self.SEVERITY_MAP.get(severity.lower(),"error")
        dedup = dedup_key or f"dr-{component or 'system'}-{int(datetime.utcnow().timestamp())}"
        payload = {"routing_key": self.integration_key, "event_action": "trigger",
                   "dedup_key": dedup,
                   "payload": {"summary": summary[:1024], "severity": pd_severity,
                               "source": source, "timestamp": datetime.utcnow().isoformat()+"Z",
                               "component": component or "DR System", "group": "Disaster Recovery",
                               "custom_details": {**(custom_details or {}), **(details or {})}}}
        result = self._events_request(payload)
        if result.get("status") == "success":
            logger.warning(f"PagerDuty TRIGGERED [{pd_severity}]: {summary[:80]} dedup={dedup}")
        return {**result, "dedup_key": dedup}

    def resolve_alert(self, dedup_key: str, summary: str = "Resolved by DR System") -> dict:
        """Resolve a PagerDuty alert."""
        payload = {"routing_key": self.integration_key, "event_action": "resolve",
                   "dedup_key": dedup_key,
                   "payload": {"summary": summary, "severity": "info", "source": "DR System"}}
        result = self._events_request(payload)
        if result.get("status") == "success": logger.info(f"PagerDuty RESOLVED: {dedup_key}")
        return result

    def acknowledge_alert(self, dedup_key: str) -> dict:
        """Acknowledge a PagerDuty alert."""
        return self._events_request({"routing_key": self.integration_key,
                                      "event_action": "acknowledge", "dedup_key": dedup_key})

    def create_incident(self, title: str, body: str, service_id: str = None,
                         urgency: str = "high") -> dict:
        """Create a PagerDuty incident via REST API."""
        svc_id = service_id or self.service_id
        if not svc_id: return {"error": "service_id required"}
        payload = {"incident": {"type": "incident", "title": title[:1024],
                                "service": {"id": svc_id, "type": "service_reference"},
                                "urgency": urgency,
                                "body": {"type": "incident_body", "details": body[:32768]}}}
        result = self._rest_request("POST", "/incidents", payload)
        if "incident" in result:
            i = result["incident"]
            return {"incident_id": i.get("id",""), "incident_number": i.get("incident_number",""),
                    "url": i.get("html_url",""), "status": i.get("status","")}
        return result

    def resolve_incident(self, incident_id: str, resolution: str = "Resolved by DR System") -> dict:
        """Resolve a PagerDuty incident."""
        return self._rest_request("PUT", f"/incidents/{incident_id}",
                                   {"incident": {"type":"incident","status":"resolved","resolution":resolution}})

    def add_note(self, incident_id: str, content: str) -> dict:
        return self._rest_request("POST", f"/incidents/{incident_id}/notes",
                                   {"note": {"content": content[:25000]}})

    def get_on_call(self, escalation_policy_id: str = None) -> List[dict]:
        ep = escalation_policy_id or self.config.get("escalation_policy_id","")
        params = f"?escalation_policy_ids[]={ep}" if ep else ""
        result = self._rest_request("GET", f"/oncalls{params}")
        return [{"user": oc.get("user",{}).get("summary",""),
                  "escalation_level": oc.get("escalation_level",1)} for oc in result.get("oncalls",[])]

    def trigger_dr_critical(self, system: str, description: str, affected_components: list = None) -> dict:
        return self.trigger_alert(
            summary=f"[DR CRITICAL] {system}: {description[:100]}", severity="critical",
            dedup_key=f"dr-critical-{system.lower().replace(' ','-')}-{int(datetime.utcnow().timestamp())}",
            component=system, custom_details={"description": description, "severity": "SEV1",
                                               "affected": ", ".join(affected_components or [])})

    def _events_request(self, payload: dict) -> dict:
        data = json.dumps(payload, default=str).encode()
        req = urllib.request.Request(self.EVENTS_API, data=data,
                                      headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"status": "success", **json.loads(resp.read().decode())}
        except urllib.request.HTTPError as e:
            body = e.read().decode()
            logger.error(f"PagerDuty Events API error {e.code}: {body[:200]}")
            return {"status": "error", "http_status": e.code, "error": body[:200]}
        except Exception as e:
            logger.error(f"PagerDuty request failed: {e}")
            return {"status": "error", "error": str(e)}

    def _rest_request(self, method: str, endpoint: str, payload: dict = None) -> dict:
        url = f"{self.REST_API}{endpoint}"
        data = json.dumps(payload, default=str).encode() if payload else None
        headers = {"Content-Type":"application/json","Accept":"application/vnd.pagerduty+json;version=2",
                    "Authorization": f"Token token={self.api_key}","From": self.from_email}
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.request.HTTPError as e:
            return {"error": e.read().decode()[:200], "http_status": e.code}
        except Exception as e:
            return {"error": str(e)}
