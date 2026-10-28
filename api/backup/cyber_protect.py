"""
Integrated Cyber Protection
Inspired by: Acronis Cyber Protect — unifies backup + cybersecurity
Combines antimalware, patch management, vulnerability assessment,
and backup into a single protection layer.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProtectionStatus(str, Enum):
    PROTECTED      = "protected"
    AT_RISK        = "at_risk"
    VULNERABLE     = "vulnerable"
    COMPROMISED    = "compromised"
    UNPROTECTED    = "unprotected"


class VulnerabilitySeverity(str, Enum):
    INFO     = "info"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class Vulnerability:
    cve_id: str
    severity: VulnerabilitySeverity
    title: str
    affected_component: str
    cvss_score: float
    patch_available: bool = False
    patch_id: Optional[str] = None
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    remediated_at: Optional[datetime] = None

    @property
    def is_remediated(self) -> bool:
        return self.remediated_at is not None


@dataclass
class PatchRecord:
    patch_id: str
    title: str
    kb_article: str
    component: str
    severity: str
    released_at: datetime
    applied_at: Optional[datetime] = None
    reboot_required: bool = False

    @property
    def is_applied(self) -> bool:
        return self.applied_at is not None


@dataclass
class CyberProtectionReport:
    endpoint_id: str
    generated_at: datetime = field(default_factory=datetime.utcnow)
    status: ProtectionStatus = ProtectionStatus.UNPROTECTED
    backup_status: str = "unknown"
    last_backup_at: Optional[datetime] = None
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    pending_patches: List[PatchRecord] = field(default_factory=list)
    antimalware_last_scan: Optional[datetime] = None
    threats_detected: int = 0
    threats_quarantined: int = 0
    protection_score: float = 0.0     # 0–100

    def compute_score(self) -> float:
        score = 100.0
        # Deduct for vulnerabilities
        critical = sum(1 for v in self.vulnerabilities
                       if v.severity == VulnerabilitySeverity.CRITICAL and not v.is_remediated)
        high = sum(1 for v in self.vulnerabilities
                   if v.severity == VulnerabilitySeverity.HIGH and not v.is_remediated)
        score -= critical * 20
        score -= high * 10
        # Deduct for stale backup
        if self.last_backup_at:
            age_hours = (datetime.utcnow() - self.last_backup_at).total_seconds() / 3600
            if age_hours > 48:
                score -= 20
            elif age_hours > 24:
                score -= 10
        else:
            score -= 30
        # Deduct for stale antimalware scan
        if self.antimalware_last_scan:
            scan_age = (datetime.utcnow() - self.antimalware_last_scan).total_seconds() / 3600
            if scan_age > 24:
                score -= 15
        else:
            score -= 20
        # Deduct for pending patches
        score -= min(len(self.pending_patches) * 2, 20)
        self.protection_score = max(0.0, min(100.0, score))
        return self.protection_score

    def determine_status(self) -> ProtectionStatus:
        score = self.protection_score
        if self.threats_detected > self.threats_quarantined:
            return ProtectionStatus.COMPROMISED
        if score >= 80:
            return ProtectionStatus.PROTECTED
        if score >= 50:
            return ProtectionStatus.AT_RISK
        if score >= 20:
            return ProtectionStatus.VULNERABLE
        return ProtectionStatus.UNPROTECTED


class VulnerabilityScanner:
    """Scans for known vulnerabilities in backup system components"""

    def __init__(self):
        self._known_vulns: List[Vulnerability] = self._load_vuln_db()

    def _load_vuln_db(self) -> List[Vulnerability]:
        # Sample vulnerability database — in production, sync from NVD/vendor feeds
        return [
            Vulnerability(
                cve_id="CVE-2024-XXXX",
                severity=VulnerabilitySeverity.HIGH,
                title="Remote Code Execution in Backup Agent",
                affected_component="backup_agent",
                cvss_score=8.8,
                patch_available=True,
                patch_id="PATCH-2024-001",
            ),
        ]

    def scan(self, components: List[str]) -> List[Vulnerability]:
        """Return vulnerabilities affecting the given components"""
        return [v for v in self._known_vulns
                if v.affected_component in components and not v.is_remediated]


class PatchManager:
    """Manages patch discovery and application"""

    def __init__(self):
        self._patches: Dict[str, PatchRecord] = {}
        self._applied: List[str] = []

    def register_patch(self, patch: PatchRecord) -> None:
        self._patches[patch.patch_id] = patch

    def apply_patch(self, patch_id: str) -> bool:
        patch = self._patches.get(patch_id)
        if not patch:
            return False
        patch.applied_at = datetime.utcnow()
        self._applied.append(patch_id)
        logger.info("Patch applied: %s — %s", patch_id, patch.title)
        return True

    def pending_patches(self) -> List[PatchRecord]:
        return [p for p in self._patches.values() if not p.is_applied]

    def applied_patches(self) -> List[PatchRecord]:
        return [p for p in self._patches.values() if p.is_applied]


class CyberProtectionEngine:
    """
    Unified cyber protection engine — coordinates backup + security assessment.
    Produces a holistic protection score per endpoint.
    """

    def __init__(self):
        self.vuln_scanner = VulnerabilityScanner()
        self.patch_manager = PatchManager()

    def assess_endpoint(self, endpoint_id: str,
                         components: Optional[List[str]] = None,
                         last_backup_at: Optional[datetime] = None,
                         antimalware_last_scan: Optional[datetime] = None,
                         threats_detected: int = 0,
                         threats_quarantined: int = 0) -> CyberProtectionReport:

        components = components or ["backup_agent", "scheduler", "storage_adapter"]
        vulnerabilities = self.vuln_scanner.scan(components)
        pending = self.patch_manager.pending_patches()

        report = CyberProtectionReport(
            endpoint_id=endpoint_id,
            last_backup_at=last_backup_at,
            antimalware_last_scan=antimalware_last_scan,
            vulnerabilities=vulnerabilities,
            pending_patches=pending,
            threats_detected=threats_detected,
            threats_quarantined=threats_quarantined,
        )
        report.compute_score()
        report.status = report.determine_status()

        logger.info("Cyber protection assessment: endpoint=%s score=%.0f status=%s",
                    endpoint_id, report.protection_score, report.status.value)
        return report

    def auto_remediate(self, report: CyberProtectionReport) -> List[str]:
        """Apply available patches for detected vulnerabilities"""
        actions = []
        for vuln in report.vulnerabilities:
            if vuln.patch_available and vuln.patch_id:
                if self.patch_manager.apply_patch(vuln.patch_id):
                    vuln.remediated_at = datetime.utcnow()
                    actions.append(f"Applied patch {vuln.patch_id} for {vuln.cve_id}")
        return actions
