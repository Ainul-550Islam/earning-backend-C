"""PAYMENT_PROCESSING/recurring_billing.py — Recurring billing processor."""
import logging
from decimal import Decimal
from django.utils import timezone
from ..models import RecurringBilling, UserSubscription

logger = logging.getLogger(__name__)


class RecurringBillingProcessor:
    """Processes scheduled recurring billing for active subscriptions."""

    @classmethod
    def get_due(cls) -> list:
        return list(
            RecurringBilling.objects.filter(
                status="scheduled", scheduled_at__lte=timezone.now()
            ).select_related("subscription", "subscription__user", "subscription__plan")
        )

    @classmethod
    def process(cls, billing: RecurringBilling) -> dict:
        try:
            from .payment_gateway import BasePaymentGateway
            sub = billing.subscription
            gw  = BasePaymentGateway.gateway_for("bkash")  # default gateway
            result = gw.initiate(
                billing.amount, billing.currency,
                sub.user, str(billing.id)
            )
            RecurringBilling.objects.filter(pk=billing.pk).update(
                status="completed", processed_at=timezone.now()
            )
            logger.info("Recurring billing processed: id=%s sub=%s", billing.id, sub.id)
            return {"success": True, "billing_id": billing.id, "result": result}
        except Exception as e:
            RecurringBilling.objects.filter(pk=billing.pk).update(
                status="failed", attempt_count=billing.attempt_count + 1,
                failure_reason=str(e),
            )
            logger.error("Recurring billing failed: id=%s error=%s", billing.id, e)
            return {"success": False, "error": str(e)}

    @classmethod
    def process_all_due(cls) -> dict:
        due       = cls.get_due()
        success   = failed = 0
        for billing in due:
            result = cls.process(billing)
            if result["success"]:
                success += 1
            else:
                failed += 1
        return {"processed": len(due), "success": success, "failed": failed}
