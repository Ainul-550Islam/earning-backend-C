"""tasks.py – Celery tasks for the inventory module."""
import logging
from celery import shared_task
from django.utils import timezone

from .constants import (
    TASK_CHECK_LOW_STOCK,
    TASK_EXPIRE_CODES,
    TASK_RETRY_FAILED_DELIVERIES,
    TASK_SYNC_STOCK_COUNTS,
    MAX_DELIVERY_RETRY_ATTEMPTS,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="inventory.tasks.deliver_inventory_item",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def deliver_inventory_item(self, inventory_id: str):
    """Attempt delivery of a single UserInventory entry. Retries on failure."""
    from .services import deliver_item
    from .exceptions import DeliveryFailedException
    try:
        deliver_item(inventory_id)
    except DeliveryFailedException as exc:
        logger.warning(
            "[deliver_inventory_item] Delivery failed for %s: %s", inventory_id, exc
        )
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception(
            "[deliver_inventory_item] Unexpected error for %s: %s", inventory_id, exc
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name=TASK_RETRY_FAILED_DELIVERIES,
    max_retries=2,
    default_retry_delay=120,
)
def retry_failed_deliveries(self):
    """
    Pick up all UserInventory entries in FAILED state that are
    eligible for retry (attempts < max, next_retry_at <= now).
    """
    from .models import UserInventory
    from .choices import InventoryStatus

    now = timezone.now()
    retryable = UserInventory.objects.filter(
        status=InventoryStatus.FAILED,
        delivery_attempts__lt=MAX_DELIVERY_RETRY_ATTEMPTS,
        next_retry_at__lte=now,
    ).values_list("id", flat=True)

    queued = 0
    for inv_id in retryable:
        deliver_inventory_item.delay(str(inv_id))
        queued += 1

    logger.info("[retry_failed_deliveries] Queued %d delivery retries.", queued)
    return {"queued": queued}


@shared_task(
    bind=True,
    name=TASK_EXPIRE_CODES,
    max_retries=2,
)
def expire_redemption_codes(self):
    """
    Mark past-expiry AVAILABLE codes as EXPIRED.
    Runs nightly.
    """
    from .models import RedemptionCode
    from .choices import CodeStatus

    now = timezone.now()
    expired_count = RedemptionCode.objects.filter(
        status=CodeStatus.AVAILABLE,
        expires_at__lt=now,
    ).update(status=CodeStatus.EXPIRED)

    logger.info("[expire_redemption_codes] Expired %d codes.", expired_count)
    return {"expired": expired_count}


@shared_task(
    bind=True,
    name=TASK_CHECK_LOW_STOCK,
    max_retries=2,
)
def check_low_stock_alerts(self):
    """
    Re-evaluate alert levels for all active items and fire signals
    for those newly crossing a threshold.
    """
    from .models import RewardItem, StockManager
    from .signals import low_stock_alert

    items = RewardItem.objects.active().select_related("stock_manager")
    alerted = 0
    for item in items.iterator():
        try:
            sm = item.stock_manager
        except StockManager.DoesNotExist:
            continue
        changed = sm.update_alert_level()
        if changed and sm.alert_level != "none" and not sm.alert_sent:
            low_stock_alert.send(
                sender=RewardItem, instance=item, alert_level=sm.alert_level
            )
            sm.alert_sent = True
            sm.alert_sent_at = timezone.now()
            sm.save(update_fields=["alert_sent", "alert_sent_at", "updated_at"])
            alerted += 1

    logger.info("[check_low_stock_alerts] Alerted on %d item(s).", alerted)
    return {"alerted": alerted}


@shared_task(
    bind=True,
    name=TASK_SYNC_STOCK_COUNTS,
    max_retries=1,
)
def sync_stock_counts(self):
    """
    Recount stock from RedemptionCode table for code-based items
    and correct any drift between codes and current_stock.
    """
    from .models import RewardItem, RedemptionCode
    from .choices import CodeStatus, ItemType
    from django.db.models import Count

    code_items = RewardItem.objects.filter(
        item_type__in=[ItemType.DIGITAL, ItemType.VOUCHER],
    ).exclude(current_stock=-1)  # skip unlimited

    corrections = 0
    for item in code_items.iterator():
        true_count = RedemptionCode.objects.filter(
            item=item, status=CodeStatus.AVAILABLE
        ).count()
        if item.current_stock != true_count:
            logger.warning(
                "[sync_stock_counts] Correcting '%s': DB=%d codes=%d",
                item.name, item.current_stock, true_count,
            )
            RewardItem.objects.filter(pk=item.pk).update(current_stock=true_count)
            corrections += 1

    logger.info("[sync_stock_counts] Corrected %d item(s).", corrections)
    return {"corrections": corrections}


@shared_task(
    bind=True,
    name="inventory.tasks.send_expiry_warnings",
    max_retries=2,
)
def send_expiry_warnings(self):
    """Notify users whose inventory items are expiring soon."""
    from .models import UserInventory
    from .signals import item_expiring_soon
    from .constants import CODE_EXPIRY_WARNING_DAYS

    for days in [CODE_EXPIRY_WARNING_DAYS, 1]:
        expiring = UserInventory.objects.expiring_soon(days=days).select_related("user", "item")
        for inv in expiring.iterator():
            item_expiring_soon.send(
                sender=UserInventory, instance=inv, days_remaining=days
            )
    return {"checked": True}
