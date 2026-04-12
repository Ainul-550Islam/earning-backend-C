"""
Retention Policy — Enforces data retention rules per regulatory requirements.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RetentionRule:
    """A single retention rule with conditions and actions."""
    def __init__(self, name: str, backup_type: str, retain_days: int,
                 min_copies: int = 1, offsite_copy: bool = False,
                 compliance_framework: str = None):
        self.name = name
        self.backup_type = backup_type
        self.retain_days = retain_days
        self.min_copies = min_copies
        self.offsite_copy = offsite_copy
        self.compliance_framework = compliance_framework


class RetentionPolicyManager:
    """
    Enforces data retention policies including:
    - GDPR: Right to erasure within 30 days of request
    - HIPAA: 6-year minimum retention
    - PCI-DSS: 1-year online, 3-year archive
    - SOC2: Evidence retention for audit periods
    - Custom business rules
    """

    COMPLIANCE_DEFAULTS = {
        "GDPR": {"full": 30, "incremental": 7, "min_copies": 2, "offsite": True},
        "HIPAA": {"full": 2190, "incremental": 365, "min_copies": 3, "offsite": True},  # 6 years
        "PCI_DSS": {"full": 365, "incremental": 90, "min_copies": 2, "offsite": True},
        "SOC2": {"full": 365, "incremental": 90, "min_copies": 2, "offsite": True},
        "ISO27001": {"full": 365, "incremental": 90, "min_copies": 2, "offsite": True},
        "INTERNAL": {"full": 30, "incremental": 7, "min_copies": 1, "offsite": False},
    }

    def __init__(self, rules: List[RetentionRule] = None, framework: str = "INTERNAL"):
        self.rules = rules or []
        self.framework = framework.upper()
        if not rules:
            self._load_framework_defaults()

    def _load_framework_defaults(self):
        defaults = self.COMPLIANCE_DEFAULTS.get(self.framework, self.COMPLIANCE_DEFAULTS["INTERNAL"])
        self.rules = [
            RetentionRule("full_backup_retention", "full",
                          defaults["full"], defaults["min_copies"], defaults["offsite"], self.framework),
            RetentionRule("incremental_backup_retention", "incremental",
                          defaults["incremental"], defaults["min_copies"], defaults["offsite"], self.framework),
            RetentionRule("snapshot_retention", "snapshot", 7, 1, False, self.framework),
        ]
        logger.info(f"Loaded {self.framework} retention defaults: full={defaults['full']}d, incr={defaults['incremental']}d")

    def get_retention_for_type(self, backup_type: str) -> int:
        """Get retention days for a specific backup type."""
        for rule in self.rules:
            if rule.backup_type == backup_type:
                return rule.retain_days
        return 30  # Safe default

    def is_expired(self, backup: dict) -> bool:
        """Check if a backup has exceeded its retention period."""
        if backup.get("legal_hold", False):
            return False
        created = datetime.fromisoformat(backup.get("created_at", datetime.utcnow().isoformat()))
        retention_days = backup.get("retention_days") or self.get_retention_for_type(
            backup.get("backup_type", "full")
        )
        return (datetime.utcnow() - created).days > retention_days

    def get_expiry_date(self, backup: dict) -> datetime:
        """Calculate expiry date for a backup."""
        created = datetime.fromisoformat(backup.get("created_at", datetime.utcnow().isoformat()))
        retention = backup.get("retention_days") or self.get_retention_for_type(
            backup.get("backup_type", "full")
        )
        return created + timedelta(days=retention)

    def evaluate_backups(self, backups: List[dict]) -> dict:
        """Evaluate all backups against retention policy."""
        to_delete = []
        to_keep = []
        compliance_violations = []
        for backup in backups:
            if self.is_expired(backup):
                to_delete.append(backup)
            else:
                to_keep.append(backup)
        # Check minimum copy requirements
        for rule in self.rules:
            matching = [b for b in to_keep if b.get("backup_type") == rule.backup_type]
            if len(matching) < rule.min_copies:
                compliance_violations.append({
                    "rule": rule.name,
                    "backup_type": rule.backup_type,
                    "required_copies": rule.min_copies,
                    "actual_copies": len(matching),
                    "severity": "critical" if rule.compliance_framework else "warning",
                })
        return {
            "framework": self.framework,
            "total_backups": len(backups),
            "to_keep": len(to_keep),
            "to_delete": len(to_delete),
            "delete_candidates": [b.get("id") for b in to_delete],
            "compliance_violations": compliance_violations,
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    def generate_compliance_report(self, backups: List[dict]) -> dict:
        """Generate a compliance report for audit purposes."""
        evaluation = self.evaluate_backups(backups)
        oldest = min(
            (datetime.fromisoformat(b.get("created_at", datetime.utcnow().isoformat())) for b in backups),
            default=datetime.utcnow()
        )
        newest = max(
            (datetime.fromisoformat(b.get("created_at", datetime.utcnow().isoformat())) for b in backups),
            default=datetime.utcnow()
        )
        return {
            "compliance_framework": self.framework,
            "report_date": datetime.utcnow().isoformat(),
            "backup_coverage": {
                "oldest_backup": oldest.isoformat(),
                "newest_backup": newest.isoformat(),
                "coverage_days": (newest - oldest).days,
            },
            "retention_rules": [
                {"name": r.name, "type": r.backup_type,
                 "retain_days": r.retain_days, "min_copies": r.min_copies}
                for r in self.rules
            ],
            "policy_evaluation": evaluation,
            "compliant": len(evaluation["compliance_violations"]) == 0,
        }
