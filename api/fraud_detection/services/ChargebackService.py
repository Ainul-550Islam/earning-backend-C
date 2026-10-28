# =============================================================================
# fraud_detection/services/ChargebackService.py  — CHARGEBACK MANAGEMENT
#
# Business purpose:
#   - Open / update / close chargeback disputes
#   - Gather evidence for dispute representation
#   - Score chargeback fraud risk
#   - Track chargeback rate per advertiser / user
#   - Trigger fraud signals on high CB rates
# =============================================================================
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class ChargebackService:
    """
    Central chargeback service.
    DRY: all business logic here; views and tasks delegate.
    """

    # ── Open dispute ───────────────────────────────────────────────────────────
    def open_dispute(self, user_id: Any, transaction_id: str,
                     amount: Decimal, reason: str,
                     metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Open a new chargeback dispute."""
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.create(
                user_id        = user_id,
                transaction_id = transaction_id,
                amount         = amount,
                reason         = reason,
                status         = ChargebackDispute.Status.RECEIVED,
                metadata       = metadata or {},
            )
            risk = self._score_chargeback_risk(user_id, amount)
            self._trigger_fraud_signal_if_needed(user_id, risk, dispute.dispute_id)
            logger.info("Chargeback opened: dispute=%s user=%s amount=%s",
                        dispute.dispute_id, user_id, amount)
            return {"dispute_id": str(dispute.dispute_id), "status": dispute.status,
                    "fraud_risk_score": risk}
        except Exception as exc:
            logger.error("open_dispute failed: %s", exc, exc_info=True)
            raise

    # ── Update dispute ─────────────────────────────────────────────────────────
    def update_status(self, dispute_id: str, new_status: str,
                      notes: Optional[str] = None) -> Dict[str, Any]:
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.get(dispute_id=dispute_id)
            old_status     = dispute.status
            dispute.status = new_status
            if notes:
                dispute.metadata = {**dispute.metadata, "notes": notes}
            dispute.save(update_fields=["status", "metadata"])
            logger.info("Chargeback %s: %s → %s", dispute_id, old_status, new_status)
            return {"dispute_id": dispute_id, "old_status": old_status, "new_status": new_status}
        except Exception as exc:
            logger.error("update_status failed: %s", exc, exc_info=True)
            raise

    # ── Evidence collection ────────────────────────────────────────────────────
    def add_evidence(self, dispute_id: str, evidence_type: str,
                     evidence_data: Dict[str, Any]) -> Dict[str, Any]:
        """Attach evidence for dispute representation."""
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.get(dispute_id=dispute_id)
            evidence_list = dispute.metadata.get("evidence", [])
            evidence_list.append({
                "type":      evidence_type,
                "data":      evidence_data,
                "added_at":  timezone.now().isoformat(),
            })
            dispute.metadata["evidence"] = evidence_list
            dispute.status = ChargebackDispute.Status.REPRESENTED
            dispute.save(update_fields=["metadata", "status"])
            return {"dispute_id": dispute_id, "evidence_count": len(evidence_list),
                    "status": dispute.status}
        except Exception as exc:
            logger.error("add_evidence failed: %s", exc, exc_info=True)
            raise

    # ── Analytics ──────────────────────────────────────────────────────────────
    def get_user_chargeback_rate(self, user_id: Any,
                                  period_days: int = 30) -> Dict[str, Any]:
        """Chargeback rate for a user over the last N days."""
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            since = timezone.now() - timedelta(days=period_days)
            total    = ChargebackDispute.objects.filter(
                user_id=user_id, created_at__gte=since).count()
            won      = ChargebackDispute.objects.filter(
                user_id=user_id, created_at__gte=since,
                status=ChargebackDispute.Status.WON).count()
            lost_amt = sum(
                d.amount for d in ChargebackDispute.objects.filter(
                    user_id=user_id, created_at__gte=since,
                    status=ChargebackDispute.Status.LOST)
            )
            return {"user_id": user_id, "period_days": period_days,
                    "total_disputes": total, "won": won,
                    "loss_amount": float(lost_amt),
                    "win_rate": (won / total * 100) if total else 0}
        except Exception as exc:
            logger.error("get_user_chargeback_rate: %s", exc)
            return {"user_id": user_id, "error": str(exc)}

    def get_platform_chargeback_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """Platform-wide chargeback KPIs."""
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            from django.db.models import Sum, Count, Avg
            since = timezone.now() - timedelta(days=period_days)
            qs    = ChargebackDispute.objects.filter(created_at__gte=since)
            agg   = qs.aggregate(
                total=Count("id"),
                total_amount=Sum("amount"),
                avg_amount=Avg("amount"),
            )
            by_status = {
                s: qs.filter(status=s).count()
                for s in ChargebackDispute.Status.values
            }
            return {"period_days": period_days, **agg, "by_status": by_status}
        except Exception as exc:
            logger.error("platform chargeback stats: %s", exc)
            return {"error": str(exc)}

    def get_high_risk_users(self, min_disputes: int = 3,
                             period_days: int = 30) -> List[Dict]:
        """Users with suspiciously many chargebacks."""
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            from django.db.models import Count
            since  = timezone.now() - timedelta(days=period_days)
            result = (ChargebackDispute.objects
                      .filter(created_at__gte=since)
                      .values("user_id")
                      .annotate(dispute_count=Count("id"))
                      .filter(dispute_count__gte=min_disputes)
                      .order_by("-dispute_count"))
            return list(result)
        except Exception as exc:
            logger.error("get_high_risk_users chargebacks: %s", exc)
            return []

    # ── Fraud scoring ──────────────────────────────────────────────────────────
    def _score_chargeback_risk(self, user_id: Any, amount: Decimal) -> int:
        """Compute a fraud risk score for this chargeback."""
        score = 0
        # High amount = higher risk
        if amount > 500:    score += 30
        elif amount > 100:  score += 15

        # Repeat chargebacks
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            recent = ChargebackDispute.objects.filter(
                user_id=user_id,
                created_at__gte=timezone.now() - timedelta(days=90)
            ).count()
            score += min(50, recent * 15)
        except Exception:
            pass
        return min(100, score)

    def _trigger_fraud_signal_if_needed(self, user_id: Any,
                                         risk_score: int, dispute_id: Any) -> None:
        if risk_score < 50:
            return
        try:
            from api.fraud_detection.signals import fraud_attempt_detected
            fraud_attempt_detected.send(
                sender     = self.__class__,
                user_id    = user_id,
                fraud_type = "chargeback_fraud",
                risk_score = risk_score,
                metadata   = {"dispute_id": str(dispute_id)},
            )
        except Exception as exc:
            logger.debug("chargeback signal: %s", exc)


# ── Singleton ─────────────────────────────────────────────────────────────────
_cb_service: Optional[ChargebackService] = None

def get_chargeback_service() -> ChargebackService:
    global _cb_service
    if _cb_service is None:
        _cb_service = ChargebackService()
    return _cb_service
