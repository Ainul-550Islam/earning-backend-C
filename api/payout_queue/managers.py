"""
Payout Queue Managers — Custom QuerySet and Manager classes.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from django.db import models
from django.db.models import Q, Sum, Count, QuerySet
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PayoutBatch
# ---------------------------------------------------------------------------

class PayoutBatchQuerySet(models.QuerySet):

    def pending(self) -> "PayoutBatchQuerySet":
        from .choices import PayoutBatchStatus
        return self.filter(status=PayoutBatchStatus.PENDING)

    def processing(self) -> "PayoutBatchQuerySet":
        from .choices import PayoutBatchStatus
        return self.filter(status=PayoutBatchStatus.PROCESSING)

    def terminal(self) -> "PayoutBatchQuerySet":
        from .choices import PayoutBatchStatus
        return self.filter(status__in=[
            PayoutBatchStatus.COMPLETED,
            PayoutBatchStatus.PARTIALLY_COMPLETED,
            PayoutBatchStatus.CANCELLED,
        ])

    def on_hold(self) -> "PayoutBatchQuerySet":
        from .choices import PayoutBatchStatus
        return self.filter(status=PayoutBatchStatus.ON_HOLD)

    def failed(self) -> "PayoutBatchQuerySet":
        from .choices import PayoutBatchStatus
        return self.filter(status=PayoutBatchStatus.FAILED)

    def unlocked(self) -> "PayoutBatchQuerySet":
        return self.filter(locked_at__isnull=True)

    def stale_locked(self, timeout_seconds: int = 3600) -> "PayoutBatchQuerySet":
        """Batches locked longer than timeout_seconds (stuck workers)."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
        return self.filter(locked_at__lt=cutoff)

    def due_for_processing(self) -> "PayoutBatchQuerySet":
        """PENDING, unlocked, scheduled_at in the past or null."""
        from .choices import PayoutBatchStatus
        return self.filter(
            status=PayoutBatchStatus.PENDING,
            locked_at__isnull=True,
        ).filter(
            Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=timezone.now())
        )

    def by_gateway(self, gateway: str) -> "PayoutBatchQuerySet":
        if not gateway:
            raise ValueError("gateway must not be empty.")
        return self.filter(gateway=gateway)

    def by_priority(self, priority: str) -> "PayoutBatchQuerySet":
        return self.filter(priority=priority)

    def with_item_counts(self) -> "PayoutBatchQuerySet":
        return self.annotate(
            computed_item_count=Count("items"),
            computed_success=Count("items", filter=Q(items__status="SUCCESS")),
            computed_failed=Count("items", filter=Q(items__status="FAILED")),
        )

    def financial_summary(self) -> dict:
        return self.aggregate(
            total_batches=Count("id"),
            total_amount=Sum("total_amount"),
            total_fee=Sum("total_fee"),
            total_net=Sum("net_amount"),
        )


class PayoutBatchManager(models.Manager):
    def get_queryset(self) -> PayoutBatchQuerySet:
        return PayoutBatchQuerySet(self.model, using=self._db)

    def pending(self) -> PayoutBatchQuerySet:
        return self.get_queryset().pending()

    def due_for_processing(self) -> PayoutBatchQuerySet:
        return self.get_queryset().due_for_processing().order_by("-priority", "scheduled_at", "created_at")

    def stale_locked(self, timeout_seconds: int = 3600) -> PayoutBatchQuerySet:
        return self.get_queryset().stale_locked(timeout_seconds)


# ---------------------------------------------------------------------------
# PayoutItem
# ---------------------------------------------------------------------------

class PayoutItemQuerySet(models.QuerySet):

    def queued(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(status=PayoutItemStatus.QUEUED)

    def processing(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(status=PayoutItemStatus.PROCESSING)

    def successful(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(status=PayoutItemStatus.SUCCESS)

    def failed(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(status=PayoutItemStatus.FAILED)

    def retrying(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(status=PayoutItemStatus.RETRYING)

    def due_for_retry(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.filter(
            status=PayoutItemStatus.RETRYING,
            next_retry_at__lte=timezone.now(),
        )

    def for_batch(self, batch_id: Any) -> "PayoutItemQuerySet":
        if batch_id is None:
            raise ValueError("batch_id must not be None.")
        return self.filter(batch_id=batch_id)

    def for_user(self, user_id: Any) -> "PayoutItemQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(user_id=user_id)

    def by_gateway(self, gateway: str) -> "PayoutItemQuerySet":
        return self.filter(gateway=gateway)

    def non_terminal(self) -> "PayoutItemQuerySet":
        from .choices import PayoutItemStatus
        return self.exclude(status__in=[
            PayoutItemStatus.SUCCESS,
            PayoutItemStatus.CANCELLED,
            PayoutItemStatus.SKIPPED,
        ])

    def total_amount(self) -> Optional[Decimal]:
        return self.aggregate(total=Sum("gross_amount"))["total"]

    def total_fees(self) -> Optional[Decimal]:
        return self.aggregate(total=Sum("fee_amount"))["total"]


class PayoutItemManager(models.Manager):
    def get_queryset(self) -> PayoutItemQuerySet:
        return PayoutItemQuerySet(self.model, using=self._db)

    def queued(self) -> PayoutItemQuerySet:
        return self.get_queryset().queued()

    def due_for_retry(self) -> PayoutItemQuerySet:
        return self.get_queryset().due_for_retry().order_by("next_retry_at")

    def for_batch(self, batch_id: Any) -> PayoutItemQuerySet:
        return self.get_queryset().for_batch(batch_id).order_by("created_at")


# ---------------------------------------------------------------------------
# WithdrawalPriority
# ---------------------------------------------------------------------------

class WithdrawalPriorityQuerySet(models.QuerySet):

    def active(self) -> "WithdrawalPriorityQuerySet":
        return self.filter(is_active=True)

    def expired(self) -> "WithdrawalPriorityQuerySet":
        return self.filter(
            is_active=True,
            expires_at__isnull=False,
            expires_at__lte=timezone.now(),
        )

    def for_user(self, user_id: Any) -> "WithdrawalPriorityQuerySet":
        if user_id is None:
            raise ValueError("user_id must not be None.")
        return self.filter(user_id=user_id)

    def urgent(self) -> "WithdrawalPriorityQuerySet":
        from .choices import PriorityLevel
        return self.filter(priority__in=[PriorityLevel.URGENT, PriorityLevel.CRITICAL])


class WithdrawalPriorityManager(models.Manager):
    def get_queryset(self) -> WithdrawalPriorityQuerySet:
        return WithdrawalPriorityQuerySet(self.model, using=self._db)

    def active(self) -> WithdrawalPriorityQuerySet:
        return self.get_queryset().active()

    def get_active_for_user(self, user_id: Any) -> Optional[Any]:
        """Return the highest active priority for a user, or None."""
        from .choices import PriorityLevel
        priority_order = [
            PriorityLevel.CRITICAL,
            PriorityLevel.URGENT,
            PriorityLevel.HIGH,
            PriorityLevel.NORMAL,
            PriorityLevel.LOW,
        ]
        records = self.get_queryset().active().for_user(user_id).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        for level in priority_order:
            match = records.filter(priority=level).order_by("-created_at").first()
            if match:
                return match
        return None

    def expire_stale(self) -> int:
        """Bulk-deactivate expired priority records. Returns count."""
        expired = self.get_queryset().expired()
        count = expired.count()
        expired.update(is_active=False)
        logger.info("WithdrawalPriorityManager.expire_stale: deactivated %d records.", count)
        return count


# ---------------------------------------------------------------------------
# BulkProcessLog
# ---------------------------------------------------------------------------

class BulkProcessLogQuerySet(models.QuerySet):

    def for_batch(self, batch_id: Any) -> "BulkProcessLogQuerySet":
        if batch_id is None:
            raise ValueError("batch_id must not be None.")
        return self.filter(batch_id=batch_id)

    def successful(self) -> "BulkProcessLogQuerySet":
        from .choices import BulkProcessLogStatus
        return self.filter(status=BulkProcessLogStatus.SUCCESS)

    def failed(self) -> "BulkProcessLogQuerySet":
        from .choices import BulkProcessLogStatus
        return self.filter(status=BulkProcessLogStatus.FAILED)

    def by_task(self, task_id: str) -> "BulkProcessLogQuerySet":
        if not task_id:
            raise ValueError("task_id must not be empty.")
        return self.filter(task_id=task_id)


class BulkProcessLogManager(models.Manager):
    def get_queryset(self) -> BulkProcessLogQuerySet:
        return BulkProcessLogQuerySet(self.model, using=self._db)

    def for_batch(self, batch_id: Any) -> BulkProcessLogQuerySet:
        return self.get_queryset().for_batch(batch_id).order_by("-created_at")
