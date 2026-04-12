"""
validation_engines/status_validator.py
────────────────────────────────────────
Postback status normalisation and validation.
"""
from __future__ import annotations

APPROVED_VALUES = {
    "1", "approved", "approve", "success", "complete", "completed",
    "paid", "confirmed", "accepted", "yes", "true", "converted",
}
REJECTED_VALUES = {
    "0", "rejected", "reject", "failed", "failure", "declined",
    "cancelled", "canceled", "denied", "invalid", "no", "false",
    "fraud", "chargeback", "reversed", "refunded",
}
PENDING_VALUES = {
    "2", "pending", "hold", "review", "processing", "waiting",
}


class StatusValidator:

    def normalise(self, raw_status: str) -> str:
        """Map any network status value → 'approved' | 'rejected' | 'pending' | 'unknown'."""
        if not raw_status:
            return "approved"   # Most networks only fire on success
        s = str(raw_status).lower().strip()
        if s in APPROVED_VALUES: return "approved"
        if s in REJECTED_VALUES: return "rejected"
        if s in PENDING_VALUES:  return "pending"
        return "unknown"

    def is_approvable(self, status: str) -> bool:
        return status in ("approved", "")

    def is_chargeback(self, raw_status: str) -> bool:
        return str(raw_status).lower().strip() in ("chargeback", "reversed", "refunded")


status_validator = StatusValidator()
