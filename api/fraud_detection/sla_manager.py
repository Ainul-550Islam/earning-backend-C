# =============================================================================
# fraud_detection/sla_manager.py  — SLA TIMER & CASE ESCALATION ENGINE
#
# Business purpose:
#   - Define SLA targets per case severity (critical=2h, high=8h, medium=24h)
#   - Track SLA breach status on every FraudCase
#   - Auto-escalate breached cases via Celery task
#   - Expose SLA dashboard data
# =============================================================================
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

# SLA targets per severity (hours)
SLA_TARGETS: Dict[str, int] = {
    "critical": 2,
    "high":     8,
    "medium":   24,
    "low":      72,
}

ESCALATION_MATRIX: Dict[str, str] = {
    "critical": "executive",
    "high":     "senior_analyst",
    "medium":   "analyst",
    "low":      "analyst",
}


@dataclass
class SLAStatus:
    case_id:       Any
    severity:      str
    target_hours:  int
    elapsed_hours: float
    is_breached:   bool
    breach_pct:    float          # elapsed / target * 100
    escalate_to:   Optional[str]  # who to escalate to if breached


class SLAManager:
    """
    DRY: All SLA business logic here.
    Tasks and views delegate; no duplication.
    """

    # ── Check single case ──────────────────────────────────────────────────────
    def get_case_sla_status(self, case_id: Any) -> Optional[SLAStatus]:
        try:
            from api.fraud_detection.models import FraudCase
            case    = FraudCase.objects.get(pk=case_id)
            return self._compute_sla(case)
        except Exception as exc:
            logger.error("get_case_sla_status %s: %s", case_id, exc)
            return None

    # ── Batch check ───────────────────────────────────────────────────────────
    def get_open_cases_sla(self) -> List[SLAStatus]:
        """Return SLA status for all open FraudCases."""
        try:
            from api.fraud_detection.models import FraudCase
            open_cases = FraudCase.objects.filter(
                status__in=["open", "under_review", "escalated"]
            ).order_by("created_at")
            return [self._compute_sla(c) for c in open_cases]
        except Exception as exc:
            logger.error("get_open_cases_sla: %s", exc)
            return []

    def get_breached_cases(self) -> List[SLAStatus]:
        """Return only breached cases."""
        return [s for s in self.get_open_cases_sla() if s.is_breached]

    # ── Dashboard stats ────────────────────────────────────────────────────────
    def get_sla_dashboard(self) -> Dict[str, Any]:
        all_statuses = self.get_open_cases_sla()
        breached     = [s for s in all_statuses if s.is_breached]
        near_breach  = [s for s in all_statuses
                        if not s.is_breached and s.breach_pct >= 80]
        return {
            "total_open":           len(all_statuses),
            "breached":             len(breached),
            "near_breach":          len(near_breach),
            "on_track":             len(all_statuses) - len(breached) - len(near_breach),
            "breach_rate_pct":      round(len(breached) / len(all_statuses) * 100, 1)
                                    if all_statuses else 0,
            "targets_hours":        SLA_TARGETS,
            "breached_cases":       [{"case_id": s.case_id, "severity": s.severity,
                                      "elapsed_hours": round(s.elapsed_hours, 1),
                                      "target_hours": s.target_hours,
                                      "escalate_to": s.escalate_to}
                                     for s in breached],
        }

    # ── Escalation ─────────────────────────────────────────────────────────────
    def escalate_case(self, case_id: Any, escalate_to: str,
                       reason: str = "sla_breach") -> Dict[str, Any]:
        """Mark a case as escalated and notify the right tier."""
        try:
            from api.fraud_detection.models import FraudCase
            case        = FraudCase.objects.get(pk=case_id)
            case.status = "escalated"
            case.metadata = {
                **getattr(case, "metadata", {}),
                "escalated_to":  escalate_to,
                "escalated_at":  timezone.now().isoformat(),
                "escalate_reason": reason,
            }
            case.save(update_fields=["status", "metadata"])
            self._notify_escalation(case_id, escalate_to, reason)
            logger.warning("Case %s escalated to %s (reason=%s)", case_id, escalate_to, reason)
            return {"case_id": case_id, "escalated_to": escalate_to, "reason": reason}
        except Exception as exc:
            logger.error("escalate_case %s: %s", case_id, exc)
            raise

    def auto_escalate_breached(self) -> Dict[str, Any]:
        """Called by Celery task — escalate all newly-breached cases."""
        breached = self.get_breached_cases()
        escalated, failed = 0, 0
        for sla in breached:
            if not sla.escalate_to:
                continue
            try:
                self.escalate_case(sla.case_id, sla.escalate_to, "sla_breach")
                escalated += 1
            except Exception:
                failed += 1
        return {"processed": len(breached), "escalated": escalated, "failed": failed}

    # ── Private ────────────────────────────────────────────────────────────────
    def _compute_sla(self, case) -> SLAStatus:
        severity     = getattr(case, "severity", "medium")
        target_h     = SLA_TARGETS.get(severity, 24)
        created_at   = getattr(case, "created_at", timezone.now())
        elapsed_h    = (timezone.now() - created_at).total_seconds() / 3600
        is_breached  = elapsed_h > target_h
        breach_pct   = (elapsed_h / target_h * 100) if target_h else 0
        return SLAStatus(
            case_id      = case.pk,
            severity     = severity,
            target_hours = target_h,
            elapsed_hours= elapsed_h,
            is_breached  = is_breached,
            breach_pct   = round(breach_pct, 1),
            escalate_to  = ESCALATION_MATRIX.get(severity) if is_breached else None,
        )

    def _notify_escalation(self, case_id: Any, tier: str, reason: str) -> None:
        try:
            from api.fraud_detection.tasks import executive_alert_generation
            executive_alert_generation.delay(
                "sla_escalation",
                {"case_id": str(case_id), "tier": tier, "reason": reason},
            )
        except Exception as exc:
            logger.warning("escalation notify failed: %s", exc)


# ── Singleton ─────────────────────────────────────────────────────────────────
_sla_manager: Optional[SLAManager] = None

def get_sla_manager() -> SLAManager:
    global _sla_manager
    if _sla_manager is None:
        _sla_manager = SLAManager()
    return _sla_manager
