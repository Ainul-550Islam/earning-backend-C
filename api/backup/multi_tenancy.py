"""
Multi-Tenancy Management
Inspired by: Commvault multi-tenant, Veeam Service Provider Console
Isolated per-tenant backup policies, storage quotas, and RBAC.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Tenant:
    tenant_id: str
    name: str
    storage_quota_bytes: int = 100 * 1024 ** 3   # 100 GB default
    max_backup_jobs: int = 50
    allowed_storage_backends: List[str] = field(default_factory=lambda: ["s3", "local"])
    retention_policy_override: Optional[int] = None    # days; None = use global
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.tenant_id[:8]})"


class TenantRegistry:
    def __init__(self):
        self._tenants: Dict[str, Tenant] = {}

    def register(self, tenant: Tenant) -> None:
        self._tenants[tenant.tenant_id] = tenant
        logger.info("Tenant registered: %s", tenant.display_name)

    def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def list_active(self) -> List[Tenant]:
        return [t for t in self._tenants.values() if t.is_active]

    def deactivate(self, tenant_id: str) -> bool:
        t = self._tenants.get(tenant_id)
        if t:
            t.is_active = False
            return True
        return False

    def check_quota(self, tenant_id: str, current_bytes: int, new_bytes: int) -> bool:
        t = self._tenants.get(tenant_id)
        if not t:
            return False
        return (current_bytes + new_bytes) <= t.storage_quota_bytes
