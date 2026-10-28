"""
Reseller / MSP Model & Sub-Tenant Hierarchy
Supports Managed Service Providers (MSPs) and resellers who manage
multiple end-customer tenants under their own account.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PartnerTier(str, Enum):
    DISTRIBUTOR = "distributor"    # top-level: manages resellers
    RESELLER    = "reseller"       # manages end-customers
    MSP         = "msp"            # managed service provider
    END_CUSTOMER = "end_customer"  # leaf tenant


class ResellerStatus(str, Enum):
    ACTIVE    = "active"
    SUSPENDED = "suspended"
    TRIAL     = "trial"
    CHURNED   = "churned"


@dataclass
class ResellerProfile:
    reseller_id: str
    company_name: str
    tier: PartnerTier
    parent_id: Optional[str] = None       # None = root level
    contact_email: str = ""
    contact_name: str = ""
    status: ResellerStatus = ResellerStatus.ACTIVE
    max_tenants: int = 100
    max_storage_tb: float = 500.0
    commission_pct: float = 20.0          # % of customer revenue
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == ResellerStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reseller_id": self.reseller_id,
            "company_name": self.company_name,
            "tier": self.tier.value,
            "parent_id": self.parent_id,
            "status": self.status.value,
            "max_tenants": self.max_tenants,
            "max_storage_tb": self.max_storage_tb,
            "commission_pct": self.commission_pct,
        }


@dataclass
class SubTenant:
    """A tenant owned/managed by a reseller"""
    tenant_id: str
    reseller_id: str
    company_name: str
    admin_email: str
    storage_quota_gb: float = 100.0
    backup_quota: int = 50              # max backup jobs
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    contract_start: Optional[datetime] = None
    contract_end: Optional[datetime] = None
    notes: str = ""

    @property
    def is_in_contract(self) -> bool:
        now = datetime.utcnow()
        if self.contract_start and now < self.contract_start:
            return False
        if self.contract_end and now > self.contract_end:
            return False
        return True


@dataclass
class ResellerUsageSummary:
    reseller_id: str
    period: str                           # e.g. "2026-05"
    tenant_count: int = 0
    total_storage_gb: float = 0.0
    total_backups: int = 0
    successful_backups: int = 0
    failed_backups: int = 0
    revenue_estimate: float = 0.0
    commission_estimate: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.successful_backups + self.failed_backups
        return self.successful_backups / total if total else 0.0


class ResellerHierarchyManager:
    """
    Manages the reseller / MSP / sub-tenant hierarchy.
    Supports unlimited depth: Distributor → Reseller → MSP → End-Customer.
    """

    def __init__(self):
        self._resellers: Dict[str, ResellerProfile] = {}
        self._sub_tenants: Dict[str, List[SubTenant]] = {}   # reseller_id → [tenants]

    # ── Reseller management ───────────────────────────────────────────────────

    def register_reseller(self, profile: ResellerProfile) -> None:
        if profile.parent_id and profile.parent_id not in self._resellers:
            raise LookupError(f"Parent reseller {profile.parent_id} not found")
        self._resellers[profile.reseller_id] = profile
        self._sub_tenants.setdefault(profile.reseller_id, [])
        logger.info("Reseller registered: %s [%s] parent=%s",
                    profile.company_name, profile.tier.value, profile.parent_id)

    def get_reseller(self, reseller_id: str) -> Optional[ResellerProfile]:
        return self._resellers.get(reseller_id)

    def get_children(self, reseller_id: str) -> List[ResellerProfile]:
        """Direct child resellers"""
        return [r for r in self._resellers.values() if r.parent_id == reseller_id]

    def get_ancestors(self, reseller_id: str) -> List[ResellerProfile]:
        """All ancestors from leaf to root"""
        ancestors = []
        current = self._resellers.get(reseller_id)
        while current and current.parent_id:
            parent = self._resellers.get(current.parent_id)
            if parent:
                ancestors.append(parent)
            current = parent
        return ancestors

    def get_full_subtree(self, reseller_id: str) -> List[ResellerProfile]:
        """All descendants (BFS)"""
        result = []
        queue = self.get_children(reseller_id)
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(self.get_children(node.reseller_id))
        return result

    def suspend_reseller(self, reseller_id: str) -> int:
        """Suspend reseller and all their tenants. Returns count suspended."""
        reseller = self._resellers.get(reseller_id)
        if not reseller:
            return 0
        reseller.status = ResellerStatus.SUSPENDED
        count = 1
        for subtenant in self._sub_tenants.get(reseller_id, []):
            subtenant.is_active = False
            count += 1
        logger.info("Reseller suspended: %s (%d affected)", reseller_id, count)
        return count

    # ── Sub-tenant management ─────────────────────────────────────────────────

    def provision_tenant(self, tenant: SubTenant) -> None:
        reseller = self._resellers.get(tenant.reseller_id)
        if not reseller:
            raise LookupError(f"Reseller {tenant.reseller_id} not found")
        if not reseller.is_active:
            raise RuntimeError(f"Reseller {tenant.reseller_id} is not active")
        existing = self._sub_tenants.get(tenant.reseller_id, [])
        if len(existing) >= reseller.max_tenants:
            raise RuntimeError(
                f"Reseller {tenant.reseller_id} has reached max tenants ({reseller.max_tenants})"
            )
        existing.append(tenant)
        self._sub_tenants[tenant.reseller_id] = existing
        logger.info("Sub-tenant provisioned: %s under reseller=%s",
                    tenant.company_name, tenant.reseller_id)

    def get_tenants(self, reseller_id: str,
                    active_only: bool = True) -> List[SubTenant]:
        tenants = self._sub_tenants.get(reseller_id, [])
        if active_only:
            tenants = [t for t in tenants if t.is_active]
        return tenants

    def get_all_tenants_in_subtree(self, reseller_id: str) -> List[SubTenant]:
        """Collect tenants from reseller + all descendants"""
        all_tenants = list(self.get_tenants(reseller_id, active_only=False))
        for child in self.get_full_subtree(reseller_id):
            all_tenants.extend(self.get_tenants(child.reseller_id, active_only=False))
        return all_tenants

    def deactivate_tenant(self, tenant_id: str) -> bool:
        for tenants in self._sub_tenants.values():
            for t in tenants:
                if t.tenant_id == tenant_id:
                    t.is_active = False
                    return True
        return False

    # ── Reporting ─────────────────────────────────────────────────────────────

    def usage_summary(self, reseller_id: str,
                      period: Optional[str] = None) -> ResellerUsageSummary:
        period = period or datetime.utcnow().strftime("%Y-%m")
        tenants = self.get_all_tenants_in_subtree(reseller_id)
        summary = ResellerUsageSummary(reseller_id=reseller_id, period=period)
        summary.tenant_count = len([t for t in tenants if t.is_active])
        summary.total_storage_gb = sum(t.storage_quota_gb for t in tenants if t.is_active)
        # Revenue estimate: $0.10 per GB per month
        summary.revenue_estimate = summary.total_storage_gb * 0.10
        reseller = self._resellers.get(reseller_id)
        if reseller:
            summary.commission_estimate = (
                summary.revenue_estimate * reseller.commission_pct / 100
            )
        return summary

    def commission_report(self) -> List[Dict[str, Any]]:
        rows = []
        for rid, reseller in self._resellers.items():
            summary = self.usage_summary(rid)
            rows.append({
                "reseller_id": rid,
                "company": reseller.company_name,
                "tier": reseller.tier.value,
                "tenants": summary.tenant_count,
                "storage_gb": round(summary.total_storage_gb, 2),
                "revenue_estimate": round(summary.revenue_estimate, 2),
                "commission_pct": reseller.commission_pct,
                "commission_estimate": round(summary.commission_estimate, 2),
            })
        return sorted(rows, key=lambda r: r["commission_estimate"], reverse=True)
