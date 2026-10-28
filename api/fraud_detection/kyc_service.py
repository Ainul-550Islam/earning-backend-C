# =============================================================================
# fraud_detection/kyc_service.py  — KYC / IDENTITY VERIFICATION SERVICE
#
# Business purpose:
#   - Submit identity documents for verification
#   - Track KYC status per user (pending → verified → rejected)
#   - Integrate verification result into risk score
#   - Expose KYC status to fraud detection engine
# =============================================================================
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


class KYCStatus(str, Enum):
    PENDING         = "pending"
    UNDER_REVIEW    = "under_review"
    VERIFIED        = "verified"
    REJECTED        = "rejected"
    EXPIRED         = "expired"
    REQUIRES_UPDATE = "requires_update"


class DocumentType(str, Enum):
    PASSPORT         = "passport"
    NATIONAL_ID      = "national_id"
    DRIVING_LICENSE  = "driving_license"
    UTILITY_BILL     = "utility_bill"
    BANK_STATEMENT   = "bank_statement"
    SELFIE           = "selfie"


@dataclass
class KYCSubmissionResult:
    submission_id:  str
    user_id:        Any
    status:         KYCStatus
    document_type:  str
    risk_score_delta: int = 0          # how much to adjust user risk score
    rejection_reason: Optional[str] = None
    expires_at:     Optional[str]   = None
    metadata:       Dict[str, Any]  = field(default_factory=dict)


class KYCService:
    """
    Central KYC orchestrator.
    DRY: all KYC logic lives here; views and tasks delegate to this class.
    """

    # KYC status → risk score adjustment
    RISK_DELTA = {
        KYCStatus.VERIFIED:        -20,   # verified user = lower risk
        KYCStatus.REJECTED:        +40,   # rejected = higher risk
        KYCStatus.PENDING:           0,
        KYCStatus.UNDER_REVIEW:      0,
        KYCStatus.EXPIRED:         +10,
        KYCStatus.REQUIRES_UPDATE: +10,
    }

    # ── Submission ─────────────────────────────────────────────────────────────
    def submit_document(self, user_id: Any, document_type: str,
                        document_data: Dict[str, Any],
                        metadata: Optional[Dict] = None) -> KYCSubmissionResult:
        """
        Submit a KYC document for a user.
        Returns a KYCSubmissionResult with the initial status.
        """
        submission_id = str(uuid.uuid4())
        try:
            # Validate document type
            if document_type not in [d.value for d in DocumentType]:
                raise ValueError(f"Unknown document_type: {document_type!r}")

            # Call external provider (or stub for offline)
            provider_result = self._call_provider(
                user_id, document_type, document_data
            )
            status   = KYCStatus(provider_result.get("status", "pending"))
            expires  = (timezone.now() + timedelta(days=365)).isoformat() \
                       if status == KYCStatus.VERIFIED else None

            result = KYCSubmissionResult(
                submission_id   = submission_id,
                user_id         = user_id,
                status          = status,
                document_type   = document_type,
                risk_score_delta= self.RISK_DELTA.get(status, 0),
                rejection_reason= provider_result.get("rejection_reason"),
                expires_at      = expires,
                metadata        = metadata or {},
            )

            self._persist_result(result)
            self._update_user_risk_score(user_id, result.risk_score_delta)
            self._invalidate_cache(user_id)
            self._emit_kyc_signal(result)

            logger.info("KYC submission %s: user=%s status=%s",
                        submission_id, user_id, status.value)
            return result

        except Exception as exc:
            logger.error("KYC submit failed: user=%s exc=%s", user_id, exc, exc_info=True)
            raise

    # ── Status query ───────────────────────────────────────────────────────────
    def get_status(self, user_id: Any) -> Dict[str, Any]:
        """Return the current KYC status for a user."""
        cache_key = f"kyc_status:{user_id}"
        cached    = cache.get(cache_key)
        if cached:
            return cached

        result = self._fetch_latest_status(user_id)
        cache.set(cache_key, result, CACHE_TTL)
        return result

    def get_all_statuses(self, user_ids: List[Any]) -> Dict[Any, Dict]:
        """Bulk status fetch — DRY wrapper for multiple users."""
        return {uid: self.get_status(uid) for uid in user_ids}

    # ── Verification decision ──────────────────────────────────────────────────
    def manual_decision(self, submission_id: str, decision: str,
                        reason: Optional[str] = None,
                        reviewer_id: Optional[Any] = None) -> Dict[str, Any]:
        """Analyst manual approve/reject a pending submission."""
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be 'approved' or 'rejected'")

        new_status = KYCStatus.VERIFIED if decision == "approved" else KYCStatus.REJECTED
        try:
            submission = self._get_submission(submission_id)
            if not submission:
                raise ValueError(f"Submission {submission_id} not found")

            old_status = KYCStatus(submission.get("status", "pending"))
            delta      = self.RISK_DELTA.get(new_status, 0) - self.RISK_DELTA.get(old_status, 0)

            self._update_submission_status(submission_id, new_status.value, reason)
            self._update_user_risk_score(submission["user_id"], delta)
            self._invalidate_cache(submission["user_id"])

            logger.info("KYC manual decision: %s → %s by reviewer=%s",
                        submission_id, new_status.value, reviewer_id)
            return {
                "submission_id":  submission_id,
                "status":         new_status.value,
                "reviewer_id":    reviewer_id,
                "reason":         reason,
                "risk_delta":     delta,
            }
        except Exception as exc:
            logger.error("KYC manual decision failed: %s exc=%s", submission_id, exc)
            raise

    # ── Compliance check ───────────────────────────────────────────────────────
    def is_user_kyc_verified(self, user_id: Any) -> bool:
        """Quick boolean: is this user currently KYC-verified?"""
        status = self.get_status(user_id)
        return status.get("status") == KYCStatus.VERIFIED.value

    def get_unverified_high_risk_users(self, risk_threshold: int = 60) -> List[Dict]:
        """Return users with risk_score ≥ threshold who are NOT kyc-verified."""
        try:
            from api.fraud_detection.models import UserRiskProfile
            profiles = UserRiskProfile.objects.filter(
                risk_score__gte=risk_threshold
            ).values("user_id", "risk_score")
            return [
                p for p in profiles
                if not self.is_user_kyc_verified(p["user_id"])
            ]
        except Exception as exc:
            logger.error("get_unverified_high_risk_users: %s", exc)
            return []

    # ── Private helpers ────────────────────────────────────────────────────────
    def _call_provider(self, user_id, doc_type, doc_data) -> Dict:
        """
        Call external KYC provider.
        Stub returns 'pending' — replace with real provider SDK.
        """
        provider = getattr(settings, "KYC_PROVIDER", "stub")
        if provider == "stub":
            return {"status": "pending", "rejection_reason": None}
        # Real provider integration point
        raise NotImplementedError(f"Provider {provider!r} not implemented")

    def _persist_result(self, result: KYCSubmissionResult) -> None:
        """Persist to cache (replace with DB model in production)."""
        cache.set(f"kyc_submission:{result.submission_id}", {
            "submission_id":   result.submission_id,
            "user_id":         str(result.user_id),
            "status":          result.status.value,
            "document_type":   result.document_type,
            "rejection_reason":result.rejection_reason,
            "expires_at":      result.expires_at,
            "submitted_at":    timezone.now().isoformat(),
        }, timeout=86400 * 365)

        # Also update user's latest status
        cache.set(f"kyc_status:{result.user_id}", {
            "user_id":       str(result.user_id),
            "status":        result.status.value,
            "document_type": result.document_type,
            "expires_at":    result.expires_at,
            "last_checked":  timezone.now().isoformat(),
        }, CACHE_TTL)

    def _fetch_latest_status(self, user_id) -> Dict:
        return {
            "user_id":      str(user_id),
            "status":       KYCStatus.PENDING.value,
            "document_type": None,
            "expires_at":   None,
            "last_checked": timezone.now().isoformat(),
        }

    def _get_submission(self, submission_id: str) -> Optional[Dict]:
        return cache.get(f"kyc_submission:{submission_id}")

    def _update_submission_status(self, submission_id: str,
                                  status: str, reason: Optional[str]) -> None:
        sub = self._get_submission(submission_id) or {}
        sub.update({"status": status, "rejection_reason": reason})
        cache.set(f"kyc_submission:{submission_id}", sub, timeout=86400 * 365)

    def _update_user_risk_score(self, user_id: Any, delta: int) -> None:
        if delta == 0:
            return
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.get(user_id=user_id)
            profile.risk_score = max(0, min(100, profile.risk_score + delta))
            profile.save(update_fields=["risk_score"])
        except Exception as exc:
            logger.debug("Risk score update for KYC: %s", exc)

    def _invalidate_cache(self, user_id: Any) -> None:
        cache.delete(f"kyc_status:{user_id}")

    def _emit_kyc_signal(self, result: KYCSubmissionResult) -> None:
        try:
            from django.dispatch import Signal
            kyc_status_changed = Signal()
            kyc_status_changed.send(
                sender=self.__class__,
                user_id=result.user_id,
                status=result.status.value,
                submission_id=result.submission_id,
            )
        except Exception:
            pass


# ── Singleton ─────────────────────────────────────────────────────────────────
_kyc_service: Optional[KYCService] = None

def get_kyc_service() -> KYCService:
    global _kyc_service
    if _kyc_service is None:
        _kyc_service = KYCService()
    return _kyc_service
