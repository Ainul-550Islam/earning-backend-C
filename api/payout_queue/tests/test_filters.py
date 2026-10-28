"""
payout_queue/tests/test_filters.py  ← NEW FILE

Filters had 0% test coverage.
Covers: PayoutBatchFilter, PayoutItemFilter, BulkProcessLogFilter
— all new fields added in filters_fixed.py as well as existing ones.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, BulkProcessLogStatus,
)
from ..filters import PayoutBatchFilter, PayoutItemFilter, BulkProcessLogFilter
from ..models import PayoutBatch, PayoutItem, BulkProcessLog
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
    BulkProcessLogFactory,
)

class PayoutBatchFilterTest(TestCase):

    def setUp(self):
        self.admin = StaffUserFactory()
        self.b1 = PayoutBatchFactory(
            name="Eid Bonus Batch",
            gateway=PaymentGateway.BKASH,
            status=PayoutBatchStatus.PENDING,
            priority=PriorityLevel.NORMAL,
        )
        self.b2 = PayoutBatchFactory(
            name="Salary Payment",
            gateway=PaymentGateway.NAGAD,
            status=PayoutBatchStatus.COMPLETED,
            priority=PriorityLevel.HIGH,
        )

    def _filter(self, **params):
        qs = PayoutBatch.objects.all()
        return PayoutBatchFilter(data=params, queryset=qs).qs

    def test_filter_by_status(self):
        result = self._filter(status=PayoutBatchStatus.PENDING)
        self.assertIn(self.b1, result)
        self.assertNotIn(self.b2, result)

    def test_filter_by_gateway(self):
        result = self._filter(gateway=PaymentGateway.NAGAD)
        self.assertIn(self.b2, result)
        self.assertNotIn(self.b1, result)

    def test_filter_by_priority(self):
        result = self._filter(priority=PriorityLevel.HIGH)
        self.assertIn(self.b2, result)
        self.assertNotIn(self.b1, result)

    # FIX: name search was added
    def test_filter_by_name_partial(self):
        result = self._filter(name="eid")
        self.assertIn(self.b1, result)
        self.assertNotIn(self.b2, result)

    def test_filter_by_name_case_insensitive(self):
        result = self._filter(name="EID BONUS")
        self.assertIn(self.b1, result)

    def test_filter_by_created_after(self):
        past = timezone.now() - timedelta(hours=1)
        result = self._filter(created_after=past.isoformat())
        self.assertIn(self.b1, result)
        self.assertIn(self.b2, result)

    def test_filter_by_created_before(self):
        future = timezone.now() + timedelta(hours=1)
        result = self._filter(created_before=future.isoformat())
        self.assertIn(self.b1, result)

    def test_filter_before_epoch_returns_empty(self):
        past = (timezone.now() - timedelta(days=9999)).isoformat()
        result = self._filter(created_before=past)
        self.assertEqual(result.count(), 0)

    # FIX: is_locked filter
    def test_filter_locked(self):
        self.b1.acquire_lock("test-worker")
        result = self._filter(is_locked=True)
        self.assertIn(self.b1, result)
        self.assertNotIn(self.b2, result)

    def test_ordering_by_priority(self):
        result = list(self._filter(ordering="priority"))
        priorities = [b.priority for b in result]
        self.assertEqual(priorities, sorted(priorities))

    def test_ordering_by_created_at_desc(self):
        result = list(self._filter(ordering="-created_at"))
        dates = [b.created_at for b in result]
        self.assertEqual(dates, sorted(dates, reverse=True))

class PayoutItemFilterTest(TestCase):

    def setUp(self):
        self.batch = PayoutBatchFactory()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.item1 = PayoutItemFactory(
            batch=self.batch,
            user=self.user1,
            gateway=PaymentGateway.BKASH,
            status=PayoutItemStatus.QUEUED,
            gross_amount=Decimal("500.00"),
            account_number="01712345678",
        )
        self.item2 = PayoutItemFactory(
            batch=self.batch,
            user=self.user2,
            gateway=PaymentGateway.NAGAD,
            status=PayoutItemStatus.SUCCESS,
            gross_amount=Decimal("15000.00"),
            account_number="01898765432",
        )

    def _filter(self, **params):
        qs = PayoutItem.objects.all()
        return PayoutItemFilter(data=params, queryset=qs).qs

    def test_filter_by_status(self):
        result = self._filter(status=PayoutItemStatus.QUEUED)
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    def test_filter_by_gateway(self):
        result = self._filter(gateway=PaymentGateway.BKASH)
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    def test_filter_by_user(self):
        result = self._filter(user=self.user1.pk)
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    def test_filter_by_batch(self):
        other_batch = PayoutBatchFactory()
        other_item = PayoutItemFactory(batch=other_batch, user=self.user1)
        result = self._filter(batch=str(self.batch.pk))
        self.assertIn(self.item1, result)
        self.assertNotIn(other_item, result)

    # FIX: amount range filters were added
    def test_filter_amount_min(self):
        result = self._filter(amount_min=1000)
        self.assertIn(self.item2, result)
        self.assertNotIn(self.item1, result)

    def test_filter_amount_max(self):
        result = self._filter(amount_max=999)
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    def test_filter_amount_range(self):
        result = self._filter(amount_min=400, amount_max=600)
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    # FIX: date range filters were added
    def test_filter_created_after(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        result = self._filter(created_after=past)
        self.assertIn(self.item1, result)
        self.assertIn(self.item2, result)

    def test_filter_created_before_past_returns_empty(self):
        ancient = (timezone.now() - timedelta(days=999)).isoformat()
        result = self._filter(created_before=ancient)
        self.assertEqual(result.count(), 0)

    # FIX: account_number partial search
    def test_filter_account_number_partial(self):
        result = self._filter(account_number="01712")
        self.assertIn(self.item1, result)
        self.assertNotIn(self.item2, result)

    # FIX: gateway_reference exact match
    def test_filter_gateway_reference_exact(self):
        from ..models import PayoutItem
        PayoutItem.objects.filter(pk=self.item2.pk).update(
            gateway_reference="TRX_EXACT_001"
        )
        result = self._filter(gateway_reference="TRX_EXACT_001")
        ids = list(result.values_list("id", flat=True))
        self.assertIn(self.item2.id, ids)
        self.assertNotIn(self.item1.id, ids)

    def test_ordering_by_gross_amount_desc(self):
        result = list(self._filter(ordering="-gross_amount"))
        amounts = [i.gross_amount for i in result]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

class BulkProcessLogFilterTest(TestCase):

    def setUp(self):
        self.batch1 = PayoutBatchFactory()
        self.batch2 = PayoutBatchFactory()
        self.log1 = BulkProcessLogFactory(
            batch=self.batch1,
            status=BulkProcessLogStatus.SUCCESS,
            task_id="task-aaa-001",
            duration_ms=500,
        )
        self.log2 = BulkProcessLogFactory(
            batch=self.batch2,
            status=BulkProcessLogStatus.FAILED,
            task_id="task-bbb-002",
            duration_ms=8000,
        )

    def _filter(self, **params):
        qs = BulkProcessLog.objects.all()
        return BulkProcessLogFilter(data=params, queryset=qs).qs

    def test_filter_by_status(self):
        result = self._filter(status=BulkProcessLogStatus.SUCCESS)
        self.assertIn(self.log1, result)
        self.assertNotIn(self.log2, result)

    def test_filter_by_batch(self):
        result = self._filter(batch=str(self.batch1.pk))
        self.assertIn(self.log1, result)
        self.assertNotIn(self.log2, result)

    # FIX: task_id exact match was added
    def test_filter_by_task_id(self):
        result = self._filter(task_id="task-aaa-001")
        self.assertIn(self.log1, result)
        self.assertNotIn(self.log2, result)

    def test_filter_task_id_no_match(self):
        result = self._filter(task_id="nonexistent-task")
        self.assertEqual(result.count(), 0)

    # FIX: date range was added
    def test_filter_created_after(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        result = self._filter(created_after=past)
        self.assertIn(self.log1, result)

    # FIX: duration_min_ms was added
    def test_filter_duration_min(self):
        result = self._filter(duration_min_ms=1000)
        self.assertIn(self.log2, result)
        self.assertNotIn(self.log1, result)

    def test_ordering_by_duration_desc(self):
        result = list(self._filter(ordering="-duration_ms"))
        durations = [l.duration_ms for l in result]
        self.assertEqual(durations, sorted(durations, reverse=True))
