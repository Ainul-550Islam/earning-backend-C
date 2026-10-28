"""
Trial & Freemium Management
Handles trial periods, plan upgrades, freemium limits, and plan enforcement.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlanTier(str, Enum):
    FREE      = "free"
    TRIAL     = "trial"
    STARTER   = "starter"
    BUSINESS  = "business"
    ENTERPRISE = "enterprise"
    CUSTOM    = "custom"


class TrialStatus(str, Enum):
    ACTIVE    = "active"
    EXPIRED   = "expired"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


@dataclass
class PlanLimits:
    storage_gb: float
    backup_jobs: int
    retention_days: int
    users: int
    api_calls_per_day: int
    cloud_providers: int
    sla_guarantee_pct: float = 99.0
    support_tier: str = "community"       # community / email / priority / dedicated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "storage_gb": self.storage_gb,
            "backup_jobs": self.backup_jobs,
            "retention_days": self.retention_days,
            "users": self.users,
            "api_calls_per_day": self.api_calls_per_day,
            "cloud_providers": self.cloud_providers,
            "sla_guarantee_pct": self.sla_guarantee_pct,
            "support_tier": self.support_tier,
        }


PLAN_LIMITS: Dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        storage_gb=5, backup_jobs=3, retention_days=7,
        users=1, api_calls_per_day=100, cloud_providers=1,
        sla_guarantee_pct=0, support_tier="community",
    ),
    PlanTier.TRIAL: PlanLimits(
        storage_gb=50, backup_jobs=10, retention_days=30,
        users=5, api_calls_per_day=1000, cloud_providers=3,
        sla_guarantee_pct=99.0, support_tier="email",
    ),
    PlanTier.STARTER: PlanLimits(
        storage_gb=100, backup_jobs=25, retention_days=30,
        users=5, api_calls_per_day=5000, cloud_providers=3,
        sla_guarantee_pct=99.5, support_tier="email",
    ),
    PlanTier.BUSINESS: PlanLimits(
        storage_gb=1000, backup_jobs=200, retention_days=90,
        users=25, api_calls_per_day=50000, cloud_providers=5,
        sla_guarantee_pct=99.9, support_tier="priority",
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        storage_gb=999999, backup_jobs=999999, retention_days=365,
        users=999999, api_calls_per_day=999999, cloud_providers=999,
        sla_guarantee_pct=99.99, support_tier="dedicated",
    ),
}


@dataclass
class TenantSubscription:
    tenant_id: str
    plan: PlanTier
    trial_status: Optional[TrialStatus] = None
    trial_started_at: Optional[datetime] = None
    trial_days: int = 14
    plan_started_at: datetime = field(default_factory=datetime.utcnow)
    plan_expires_at: Optional[datetime] = None
    custom_limits: Optional[PlanLimits] = None

    @property
    def limits(self) -> PlanLimits:
        if self.custom_limits:
            return self.custom_limits
        return PLAN_LIMITS.get(self.plan, PLAN_LIMITS[PlanTier.FREE])

    @property
    def trial_expires_at(self) -> Optional[datetime]:
        if self.trial_started_at:
            return self.trial_started_at + timedelta(days=self.trial_days)
        return None

    @property
    def is_trial_active(self) -> bool:
        if self.trial_status != TrialStatus.ACTIVE:
            return False
        if self.trial_expires_at and datetime.utcnow() > self.trial_expires_at:
            return False
        return True

    @property
    def trial_days_remaining(self) -> int:
        if not self.trial_expires_at:
            return 0
        delta = self.trial_expires_at - datetime.utcnow()
        return max(0, delta.days)

    @property
    def is_expired(self) -> bool:
        if self.plan_expires_at and datetime.utcnow() > self.plan_expires_at:
            return True
        if self.plan == PlanTier.TRIAL and not self.is_trial_active:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "plan": self.plan.value,
            "trial_status": self.trial_status.value if self.trial_status else None,
            "trial_days_remaining": self.trial_days_remaining,
            "is_trial_active": self.is_trial_active,
            "is_expired": self.is_expired,
            "limits": self.limits.to_dict(),
        }


class TrialManager:
    """
    Manages trial periods, plan upgrades, and freemium enforcement.
    """

    def __init__(self):
        self._subscriptions: Dict[str, TenantSubscription] = {}

    def start_trial(self, tenant_id: str, trial_days: int = 14) -> TenantSubscription:
        sub = TenantSubscription(
            tenant_id=tenant_id,
            plan=PlanTier.TRIAL,
            trial_status=TrialStatus.ACTIVE,
            trial_started_at=datetime.utcnow(),
            trial_days=trial_days,
        )
        self._subscriptions[tenant_id] = sub
        logger.info("Trial started: tenant=%s days=%d expires=%s",
                    tenant_id, trial_days, sub.trial_expires_at)
        return sub

    def start_free(self, tenant_id: str) -> TenantSubscription:
        sub = TenantSubscription(tenant_id=tenant_id, plan=PlanTier.FREE)
        self._subscriptions[tenant_id] = sub
        return sub

    def upgrade(self, tenant_id: str, new_plan: PlanTier,
                months: int = 12,
                custom_limits: Optional[PlanLimits] = None) -> TenantSubscription:
        sub = self._subscriptions.get(tenant_id)
        if not sub:
            sub = TenantSubscription(tenant_id=tenant_id, plan=new_plan)
            self._subscriptions[tenant_id] = sub

        old_plan = sub.plan
        sub.plan = new_plan
        sub.plan_started_at = datetime.utcnow()
        sub.plan_expires_at = datetime.utcnow() + timedelta(days=months * 30)
        if custom_limits:
            sub.custom_limits = custom_limits
        if sub.trial_status == TrialStatus.ACTIVE:
            sub.trial_status = TrialStatus.CONVERTED

        logger.info("Plan upgraded: tenant=%s %s → %s expires=%s",
                    tenant_id, old_plan.value, new_plan.value, sub.plan_expires_at)
        return sub

    def check_limit(self, tenant_id: str, resource: str,
                    current_usage: float) -> Dict[str, Any]:
        """Check if a tenant is within their plan limits for a resource"""
        sub = self._subscriptions.get(tenant_id)
        if not sub:
            return {"allowed": False, "reason": "No subscription found"}

        limits = sub.limits
        limit_map = {
            "storage_gb":        limits.storage_gb,
            "backup_jobs":       limits.backup_jobs,
            "users":             limits.users,
            "api_calls_per_day": limits.api_calls_per_day,
        }
        limit = limit_map.get(resource)
        if limit is None:
            return {"allowed": True, "reason": "Unknown resource"}

        allowed = current_usage < limit
        return {
            "allowed": allowed,
            "current": current_usage,
            "limit": limit,
            "used_pct": round(current_usage / limit * 100, 1) if limit else 0,
            "reason": "OK" if allowed else f"Plan limit reached: {resource} {current_usage}/{limit}",
        }

    def expire_trials(self) -> List[str]:
        """Mark expired trials and return their tenant IDs"""
        expired = []
        for sub in self._subscriptions.values():
            if (sub.trial_status == TrialStatus.ACTIVE
                    and sub.trial_expires_at
                    and datetime.utcnow() > sub.trial_expires_at):
                sub.trial_status = TrialStatus.EXPIRED
                sub.plan = PlanTier.FREE
                expired.append(sub.tenant_id)
                logger.info("Trial expired → downgraded to FREE: tenant=%s", sub.tenant_id)
        return expired

    def get_subscription(self, tenant_id: str) -> Optional[TenantSubscription]:
        return self._subscriptions.get(tenant_id)

    def list_trials_expiring_soon(self, days: int = 3) -> List[TenantSubscription]:
        threshold = datetime.utcnow() + timedelta(days=days)
        return [
            s for s in self._subscriptions.values()
            if s.is_trial_active and s.trial_expires_at and s.trial_expires_at <= threshold
        ]
