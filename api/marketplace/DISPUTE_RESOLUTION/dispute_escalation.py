"""
DISPUTE_RESOLUTION/dispute_escalation.py — Auto-Escalation Rules
"""
import logging
from django.utils import timezone
from .dispute_model import Dispute
from api.marketplace.enums import DisputeStatus

logger = logging.getLogger(__name__)

AUTO_ESCALATE_DAYS = 3   # Auto-escalate if no seller response in 3 days


def auto_escalate_stale_disputes(tenant) -> int:
    """Celery task: escalate disputes with no seller response after 3 days."""
    cutoff = timezone.now() - timezone.timedelta(days=AUTO_ESCALATE_DAYS)
    stale = Dispute.objects.filter(
        tenant=tenant,
        status=DisputeStatus.OPEN,
        created_at__lt=cutoff,
        messages__role="seller",
    ).exclude(messages__role="seller").distinct()

    count = 0
    for dispute in stale:
        dispute.status = DisputeStatus.ESCALATED
        dispute.save(update_fields=["status"])
        from .dispute_communication import send_message
        send_message(dispute, None, "admin",
                     f"Auto-escalated: No seller response after {AUTO_ESCALATE_DAYS} days.",
                     is_internal=True)
        count += 1
        logger.info("[Dispute] Auto-escalated #%s", dispute.pk)

    return count


def get_escalation_queue(tenant) -> list:
    return list(
        Dispute.objects.filter(tenant=tenant, status=DisputeStatus.ESCALATED)
        .select_related("order","raised_by","against_seller")
        .order_by("created_at")
    )


def sla_breach_report(tenant, sla_hours: int = 72) -> list:
    """Return disputes that have breached SLA (not resolved within N hours)."""
    cutoff = timezone.now() - timezone.timedelta(hours=sla_hours)
    return list(
        Dispute.objects.filter(
            tenant=tenant,
            created_at__lt=cutoff,
            resolved_at__isnull=True,
        ).values("pk","order__order_number","status","created_at")
    )
