"""
Data Governance & Policy Engine
Inspired by: Rubrik data governance, Commvault compliance policies, Druva eDiscovery
Enforces data classification, retention policies, legal holds, and compliance rules.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DataClassification(str, Enum):
    PUBLIC       = "public"
    INTERNAL     = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED   = "restricted"    # PII, PHI, PCI data
    TOP_SECRET   = "top_secret"


class ComplianceFramework(str, Enum):
    GDPR  = "gdpr"
    HIPAA = "hipaa"
    PCI   = "pci_dss"
    SOC2  = "soc2"
    ISO27001 = "iso27001"
    CCPA  = "ccpa"


class LegalHoldStatus(str, Enum):
    ACTIVE    = "active"
    RELEASED  = "released"
    EXPIRED   = "expired"


@dataclass
class RetentionPolicy:
    policy_id: str
    name: str
    classification: DataClassification
    frameworks: List[ComplianceFramework]
    min_retention_days: int
    max_retention_days: Optional[int]
    immutable: bool = False
    geo_restriction: Optional[str] = None    # e.g. "EU" for GDPR data residency
    description: str = ""

    def is_compliant(self, actual_retention_days: int) -> bool:
        if actual_retention_days < self.min_retention_days:
            return False
        if self.max_retention_days and actual_retention_days > self.max_retention_days:
            return False
        return True


@dataclass
class LegalHold:
    hold_id: str
    name: str
    reason: str
    applied_by: str
    backup_ids: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: LegalHoldStatus = LegalHoldStatus.ACTIVE
    case_reference: str = ""

    @property
    def is_active(self) -> bool:
        if self.status != LegalHoldStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def prevents_deletion(self, backup_id: str) -> bool:
        return self.is_active and backup_id in self.backup_ids


@dataclass
class DataGovernanceRecord:
    backup_id: str
    classification: DataClassification
    policy: RetentionPolicy
    contains_pii: bool = False
    contains_phi: bool = False
    contains_pci: bool = False
    geo_location: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


class DataGovernanceEngine:
    """
    Central data governance engine.
    Manages classification, retention compliance, and legal holds.
    """

    def __init__(self):
        self._policies: Dict[str, RetentionPolicy] = {}
        self._records: Dict[str, DataGovernanceRecord] = {}
        self._holds: Dict[str, LegalHold] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        defaults = [
            RetentionPolicy(
                policy_id="gdpr-personal",
                name="GDPR Personal Data",
                classification=DataClassification.RESTRICTED,
                frameworks=[ComplianceFramework.GDPR],
                min_retention_days=365,
                max_retention_days=2 * 365,
                immutable=True,
                geo_restriction="EU",
                description="GDPR Article 5 — data minimisation and storage limitation",
            ),
            RetentionPolicy(
                policy_id="hipaa-phi",
                name="HIPAA PHI Data",
                classification=DataClassification.RESTRICTED,
                frameworks=[ComplianceFramework.HIPAA],
                min_retention_days=6 * 365,
                max_retention_days=None,
                immutable=True,
                description="HIPAA requires 6-year retention of PHI",
            ),
            RetentionPolicy(
                policy_id="pci-cardholder",
                name="PCI Cardholder Data",
                classification=DataClassification.RESTRICTED,
                frameworks=[ComplianceFramework.PCI],
                min_retention_days=365,
                max_retention_days=365,
                immutable=True,
                description="PCI DSS 3.x — 1-year retention for transaction logs",
            ),
            RetentionPolicy(
                policy_id="standard-internal",
                name="Standard Internal Data",
                classification=DataClassification.INTERNAL,
                frameworks=[ComplianceFramework.SOC2],
                min_retention_days=90,
                max_retention_days=7 * 365,
                immutable=False,
            ),
        ]
        for p in defaults:
            self._policies[p.policy_id] = p

    def register_policy(self, policy: RetentionPolicy) -> None:
        self._policies[policy.policy_id] = policy

    def classify_backup(self, backup_id: str, policy_id: str,
                         metadata: Optional[Dict] = None) -> DataGovernanceRecord:
        policy = self._policies.get(policy_id)
        if not policy:
            raise LookupError(f"Governance policy {policy_id} not found")
        meta = metadata or {}
        record = DataGovernanceRecord(
            backup_id=backup_id,
            classification=policy.classification,
            policy=policy,
            contains_pii=meta.get("contains_pii", False),
            contains_phi=meta.get("contains_phi", False),
            contains_pci=meta.get("contains_pci", False),
            geo_location=meta.get("geo_location"),
        )
        self._records[backup_id] = record
        logger.info("Backup %s classified: %s [%s]",
                    backup_id, policy.name, policy.classification.value)
        return record

    def apply_legal_hold(self, hold: LegalHold) -> None:
        self._holds[hold.hold_id] = hold
        logger.info("Legal hold applied: %s covering %d backups",
                    hold.name, len(hold.backup_ids))

    def release_hold(self, hold_id: str, released_by: str) -> bool:
        hold = self._holds.get(hold_id)
        if not hold:
            return False
        hold.status = LegalHoldStatus.RELEASED
        logger.info("Legal hold %s released by %s", hold_id, released_by)
        return True

    def can_delete(self, backup_id: str) -> tuple[bool, str]:
        """Returns (allowed, reason)"""
        # Check legal holds
        for hold in self._holds.values():
            if hold.prevents_deletion(backup_id):
                return False, f"Legal hold active: {hold.name} ({hold.case_reference})"

        # Check governance policy
        record = self._records.get(backup_id)
        if record and record.policy.immutable:
            return False, f"Policy '{record.policy.name}' marks this backup as immutable"

        return True, "Deletion permitted"

    def compliance_report(self) -> Dict[str, Any]:
        violations = []
        for bid, record in self._records.items():
            from api.backup.repositories import BackupRepository
            backup = BackupRepository().get_by_id(bid)
            if backup:
                age_days = (datetime.utcnow() - backup.created_at).days
                if not record.policy.is_compliant(age_days):
                    violations.append({
                        "backup_id": bid,
                        "policy": record.policy.name,
                        "actual_days": age_days,
                        "min_required": record.policy.min_retention_days,
                    })

        return {
            "total_classified": len(self._records),
            "active_holds": sum(1 for h in self._holds.values() if h.is_active),
            "violations": violations,
            "frameworks_covered": list({
                f.value for r in self._records.values()
                for f in r.policy.frameworks
            }),
        }
