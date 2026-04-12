"""AD_CREATIVES/creative_approval.py — Creative review & approval workflow."""
import logging
from ..models import AdCreative

logger = logging.getLogger(__name__)

BLOCKED_KEYWORDS = [
    "casino", "gambling", "adult", "xxx", "porn",
    "drugs", "weapon", "hack", "crack",
]


class CreativeApprovalEngine:
    """Automated and manual creative approval pipeline."""

    @classmethod
    def auto_check(cls, creative: AdCreative) -> dict:
        """Run automated pre-screening checks."""
        issues = []
        headline = (creative.headline or "").lower()
        body     = (creative.body_text or "").lower()
        for kw in BLOCKED_KEYWORDS:
            if kw in headline or kw in body:
                issues.append(f"Blocked keyword detected: '{kw}'")
        if creative.file_size_kb and creative.file_size_kb > 5120:
            issues.append("File size exceeds 5MB limit.")
        if creative.duration_sec and creative.duration_sec > 60:
            issues.append("Video duration exceeds 60 seconds.")
        passed = len(issues) == 0
        return {"passed": passed, "issues": issues}

    @classmethod
    def submit_for_review(cls, creative_id: int) -> bool:
        updated = AdCreative.objects.filter(
            pk=creative_id, status="draft"
        ).update(status="pending")
        if updated:
            logger.info("Creative %d submitted for review.", creative_id)
        return bool(updated)

    @classmethod
    def bulk_approve(cls, creative_ids: list, reviewer=None) -> int:
        count = AdCreative.objects.filter(
            pk__in=creative_ids, status="pending"
        ).update(status="approved", reviewed_by=reviewer)
        logger.info("Bulk approved %d creatives.", count)
        return count

    @classmethod
    def bulk_reject(cls, creative_ids: list, reason: str, reviewer=None) -> int:
        count = AdCreative.objects.filter(
            pk__in=creative_ids, status="pending"
        ).update(status="rejected", rejection_reason=reason, reviewed_by=reviewer)
        return count
