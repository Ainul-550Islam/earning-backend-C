"""
SIEM & Security Platform Integration
Inspired by: Veeam CrowdStrike integration, Rubrik Security Cloud, Commvault ThreatWise
Sends backup events and threat alerts to SIEM, CrowdStrike, Splunk, Microsoft Sentinel.
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class SIEMPlatform(str, Enum):
    CROWDSTRIKE      = "crowdstrike"
    SPLUNK           = "splunk"
    MS_SENTINEL      = "microsoft_sentinel"
    IBM_QRADAR       = "ibm_qradar"
    ELASTIC_SIEM     = "elastic_siem"
    PALO_ALTO_XSIAM  = "palo_alto_xsiam"
    GENERIC_SYSLOG   = "generic_syslog"


class EventSeverity(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class BackupSecurityEvent(str, Enum):
    BACKUP_STARTED       = "backup_started"
    BACKUP_COMPLETED     = "backup_completed"
    BACKUP_FAILED        = "backup_failed"
    RANSOMWARE_DETECTED  = "ransomware_detected"
    ANOMALY_DETECTED     = "anomaly_detected"
    IMMUTABILITY_BREACH  = "immutability_breach"
    UNAUTHORIZED_ACCESS  = "unauthorized_access"
    POLICY_VIOLATION     = "policy_violation"
    DR_FAILOVER_STARTED  = "dr_failover_started"
    DR_FAILOVER_COMPLETE = "dr_failover_complete"
    LEGAL_HOLD_APPLIED   = "legal_hold_applied"


@dataclass
class SecurityEvent:
    event_type: BackupSecurityEvent
    severity: EventSeverity
    source: str               # "backup_module"
    resource_id: str          # backup_id / schedule_id
    user_id: Optional[str]
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: __import__('uuid').uuid4().hex)

    def to_cef(self) -> str:
        """Common Event Format (CEF) for SIEM ingestion"""
        severity_map = {"info": 0, "low": 3, "medium": 5, "high": 7, "critical": 10}
        sev_num = severity_map.get(self.severity.value, 5)
        ext = " ".join(f"{k}={v}" for k, v in self.metadata.items())
        return (
            f"CEF:0|BackupSystem|BackupModule|1.0|"
            f"{self.event_type.value}|{self.description}|{sev_num}|"
            f"src={self.source} dst={self.resource_id} "
            f"suser={self.user_id or 'system'} "
            f"rt={int(self.timestamp.timestamp()*1000)} {ext}"
        )

    def to_leef(self) -> str:
        """Log Event Extended Format (LEEF) for IBM QRadar"""
        attrs = "\t".join([
            f"devTime={self.timestamp.isoformat()}",
            f"severity={self.severity.value}",
            f"resource={self.resource_id}",
            f"user={self.user_id or 'system'}",
            f"description={self.description}",
        ])
        return f"LEEF:2.0|BackupSystem|BackupModule|1.0|{self.event_type.value}|{attrs}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "source": self.source,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "description": self.description,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


# ── Abstract base ──────────────────────────────────────────────────────────────

class AbstractSIEMConnector:
    def send_event(self, event: SecurityEvent) -> bool:
        raise NotImplementedError

    def send_bulk(self, events: List[SecurityEvent]) -> Dict[str, bool]:
        return {e.event_id: self.send_event(e) for e in events}

    def health_check(self) -> bool:
        return True


# ── CrowdStrike Connector ──────────────────────────────────────────────────────

class CrowdStrikeConnector(AbstractSIEMConnector):
    """
    CrowdStrike Falcon SIEM Connector.
    Sends backup events to CrowdStrike via Custom IOA or Event Streams API.
    """
    BASE_URL = "https://api.crowdstrike.com"

    def __init__(self, client_id: str, client_secret: str, base_url: str = BASE_URL):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _authenticate(self) -> bool:
        if self._token and self._token_expiry and datetime.utcnow() < self._token_expiry:
            return True
        try:
            resp = requests.post(
                f"{self.base_url}/oauth2/token",
                data={"client_id": self.client_id, "client_secret": self.client_secret},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expiry = datetime.utcnow().__class__.utcnow()
            return True
        except Exception as exc:
            logger.error("CrowdStrike auth failed: %s", exc)
            return False

    def send_event(self, event: SecurityEvent) -> bool:
        if not self._authenticate():
            return False
        payload = {
            "resources": [{
                "event_type": "BackupSystemEvent",
                "severity": event.severity.value.upper(),
                "description": event.description,
                "metadata": event.to_dict(),
                "cef": event.to_cef(),
            }]
        }
        try:
            resp = requests.post(
                f"{self.base_url}/detects/entities/alerts/v1",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("CrowdStrike event sent: %s", event.event_type.value)
            return True
        except Exception as exc:
            logger.error("CrowdStrike send failed: %s", exc)
            return False

    def get_detections(self, filter_query: str = "") -> List[Dict]:
        """Retrieve CrowdStrike detections related to backup events"""
        if not self._authenticate():
            return []
        try:
            resp = requests.get(
                f"{self.base_url}/detects/queries/detects/v1",
                params={"filter": filter_query or "description:'BackupSystem'"},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("resources", [])
        except Exception as exc:
            logger.error("CrowdStrike detections fetch failed: %s", exc)
            return []


# ── Splunk Connector ───────────────────────────────────────────────────────────

class SplunkConnector(AbstractSIEMConnector):
    """Splunk HEC (HTTP Event Collector) connector"""

    def __init__(self, hec_url: str, hec_token: str, index: str = "backup_events"):
        self.hec_url = hec_url.rstrip("/")
        self.hec_token = hec_token
        self.index = index

    def send_event(self, event: SecurityEvent) -> bool:
        payload = {
            "time": event.timestamp.timestamp(),
            "host": "backup_module",
            "source": "backup:system",
            "sourcetype": "backup:event",
            "index": self.index,
            "event": event.to_dict(),
        }
        try:
            resp = requests.post(
                f"{self.hec_url}/services/collector/event",
                json=payload,
                headers={"Authorization": f"Splunk {self.hec_token}"},
                timeout=15,
                verify=True,
            )
            resp.raise_for_status()
            logger.info("Splunk event sent: %s", event.event_type.value)
            return True
        except Exception as exc:
            logger.error("Splunk send failed: %s", exc)
            return False

    def send_bulk(self, events: List[SecurityEvent]) -> Dict[str, bool]:
        payloads = []
        for event in events:
            payloads.append(json.dumps({
                "time": event.timestamp.timestamp(),
                "host": "backup_module",
                "index": self.index,
                "event": event.to_dict(),
            }))
        body = "\n".join(payloads)
        try:
            resp = requests.post(
                f"{self.hec_url}/services/collector/event",
                data=body,
                headers={"Authorization": f"Splunk {self.hec_token}",
                         "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            return {e.event_id: True for e in events}
        except Exception as exc:
            logger.error("Splunk bulk send failed: %s", exc)
            return {e.event_id: False for e in events}


# ── Microsoft Sentinel Connector ───────────────────────────────────────────────

class MicrosoftSentinelConnector(AbstractSIEMConnector):
    """Microsoft Sentinel (Log Analytics) connector via Data Collector API"""

    def __init__(self, workspace_id: str, shared_key: str,
                 log_type: str = "BackupSystemEvents"):
        self.workspace_id = workspace_id
        self.shared_key = shared_key
        self.log_type = log_type

    def _build_signature(self, date: str, content_length: int,
                          method: str, content_type: str, resource: str) -> str:
        import hmac, base64
        x_headers = f"x-ms-date:{date}"
        string_to_hash = "\n".join([method, str(content_length),
                                    content_type, x_headers, resource])
        bytes_to_hash = string_to_hash.encode("utf-8")
        decoded_key = base64.b64decode(self.shared_key)
        encoded_hash = base64.b64encode(
            hmac.new(decoded_key, bytes_to_hash, hashlib.sha256).digest()
        ).decode("utf-8")
        return f"SharedKey {self.workspace_id}:{encoded_hash}"

    def send_event(self, event: SecurityEvent) -> bool:
        return self.send_bulk([event]).get(event.event_id, False)

    def send_bulk(self, events: List[SecurityEvent]) -> Dict[str, bool]:
        import base64
        from email.utils import formatdate
        body = json.dumps([e.to_dict() for e in events])
        body_bytes = body.encode("utf-8")
        now = formatdate(usegmt=True)
        signature = self._build_signature(
            now, len(body_bytes), "POST", "application/json",
            f"/api/logs"
        )
        url = (f"https://{self.workspace_id}.ods.opinsights.azure.com"
               f"/api/logs?api-version=2016-04-01")
        headers = {
            "Content-Type": "application/json",
            "Authorization": signature,
            "Log-Type": self.log_type,
            "x-ms-date": now,
        }
        try:
            resp = requests.post(url, data=body_bytes, headers=headers, timeout=30)
            resp.raise_for_status()
            logger.info("Sentinel: %d events sent", len(events))
            return {e.event_id: True for e in events}
        except Exception as exc:
            logger.error("Sentinel send failed: %s", exc)
            return {e.event_id: False for e in events}


# ── Unified SIEM Manager ───────────────────────────────────────────────────────

class SIEMIntegrationManager:
    """
    Unified SIEM integration — send backup security events to multiple platforms.
    Supports fan-out: one event → multiple SIEMs simultaneously.
    """

    def __init__(self):
        self._connectors: Dict[str, AbstractSIEMConnector] = {}
        self._event_log: List[SecurityEvent] = []

    def register(self, name: str, connector: AbstractSIEMConnector) -> None:
        self._connectors[name] = connector
        logger.info("SIEM connector registered: %s", name)

    def emit(self, event: SecurityEvent) -> Dict[str, bool]:
        """Send event to all registered SIEM platforms"""
        self._event_log.append(event)
        results: Dict[str, bool] = {}
        for name, connector in self._connectors.items():
            try:
                results[name] = connector.send_event(event)
            except Exception as exc:
                logger.error("SIEM emit failed [%s]: %s", name, exc)
                results[name] = False
        return results

    def emit_bulk(self, events: List[SecurityEvent]) -> Dict[str, Dict[str, bool]]:
        results: Dict[str, Dict[str, bool]] = {}
        for name, connector in self._connectors.items():
            try:
                results[name] = connector.send_bulk(events)
            except Exception as exc:
                results[name] = {e.event_id: False for e in events}
        self._event_log.extend(events)
        return results

    # Convenience event factories
    def backup_completed(self, backup_id: str, size_bytes: int,
                          user_id: Optional[str] = None) -> Dict[str, bool]:
        return self.emit(SecurityEvent(
            event_type=BackupSecurityEvent.BACKUP_COMPLETED,
            severity=EventSeverity.INFO,
            source="backup_module",
            resource_id=backup_id,
            user_id=user_id,
            description=f"Backup {backup_id} completed ({size_bytes:,} bytes)",
            metadata={"size_bytes": size_bytes},
        ))

    def ransomware_detected(self, backup_id: str, threat_level: str,
                             indicators: int) -> Dict[str, bool]:
        return self.emit(SecurityEvent(
            event_type=BackupSecurityEvent.RANSOMWARE_DETECTED,
            severity=EventSeverity.CRITICAL,
            source="ransomware_scanner",
            resource_id=backup_id,
            user_id=None,
            description=f"Ransomware indicators detected in backup {backup_id}",
            metadata={"threat_level": threat_level, "indicators": indicators},
        ))

    def unauthorized_access(self, resource_id: str, user_id: str,
                             action: str) -> Dict[str, bool]:
        return self.emit(SecurityEvent(
            event_type=BackupSecurityEvent.UNAUTHORIZED_ACCESS,
            severity=EventSeverity.HIGH,
            source="zero_trust_engine",
            resource_id=resource_id,
            user_id=user_id,
            description=f"Unauthorized access attempt: {action} on {resource_id}",
            metadata={"action": action},
        ))

    def anomaly_detected(self, backup_id: str, anomaly_type: str,
                          deviation_pct: float) -> Dict[str, bool]:
        severity = EventSeverity.CRITICAL if deviation_pct > 100 else EventSeverity.HIGH
        return self.emit(SecurityEvent(
            event_type=BackupSecurityEvent.ANOMALY_DETECTED,
            severity=severity,
            source="ml_anomaly_detector",
            resource_id=backup_id,
            user_id=None,
            description=f"Anomaly: {anomaly_type} ({deviation_pct:+.1f}% deviation)",
            metadata={"anomaly_type": anomaly_type, "deviation_pct": deviation_pct},
        ))

    def dr_failover_started(self, source: str, target: str,
                             workloads: int) -> Dict[str, bool]:
        return self.emit(SecurityEvent(
            event_type=BackupSecurityEvent.DR_FAILOVER_STARTED,
            severity=EventSeverity.HIGH,
            source="dr_orchestrator",
            resource_id=f"dr-{source}-to-{target}",
            user_id=None,
            description=f"DR failover initiated: {source} → {target} ({workloads} workloads)",
            metadata={"source": source, "target": target, "workloads": workloads},
        ))

    def get_event_log(self, limit: int = 100) -> List[SecurityEvent]:
        return self._event_log[-limit:]

    def health_check_all(self) -> Dict[str, bool]:
        return {name: conn.health_check()
                for name, conn in self._connectors.items()}
