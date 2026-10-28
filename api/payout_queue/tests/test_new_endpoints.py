"""
payout_queue/tests/test_new_endpoints.py  ← NEW FILE  (Part 1 / File 5)

Covers every new endpoint exposed in this round:
  POST /batches/{id}/hold/
  POST /batches/{id}/resume/
  POST /batches/{id}/release-lock/
  POST /batches/{id}/refresh-totals/
  GET  /batches/financial-summary/
  GET  /batches/gateways/
  GET  /batches/choices/
  POST /items/{id}/retry/
  POST /items/retry-due/
  POST /items/{id}/verify/
  POST /items/validate-account/
  GET  /logs/by-task/?task_id=
  POST /priorities/set-priority/
  POST /priorities/{id}/deactivate/
  GET  /priorities/active-for-user/?user_id=
  GET  /fee-summary/?gateway=
  GET  /health/
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from ..choices import (
    PayoutBatchStatus, PayoutItemStatus, PaymentGateway,
    PriorityLevel, WithdrawalPriorityReason,
)
from ..models import PayoutBatch, PayoutItem, WithdrawalPriority
from ..utils.payment_gateway import PayoutResult
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
    WithdrawalPriorityFactory, BulkProcessLogFactory,
)

BASE = "/api/payout-queue"

def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: hold / resume
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchHoldTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_hold_pending_batch(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        r = _client(self.admin).post(f"{BASE}/batches/{b.pk}/hold/",
                                     {"note": "pause"}, format="json")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, PayoutBatchStatus.ON_HOLD)

    def test_hold_completed_batch_409(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.COMPLETED)
        r = _client(self.admin).post(f"{BASE}/batches/{b.pk}/hold/")
        self.assertIn(r.status_code, [400, 409])

    def test_hold_nonexistent_404(self):
        import uuid
        r = _client(self.admin).post(f"{BASE}/batches/{uuid.uuid4()}/hold/")
        self.assertEqual(r.status_code, 404)

    def test_resume_on_hold_batch(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        b.transition_to(PayoutBatchStatus.ON_HOLD)
        r = _client(self.admin).post(f"{BASE}/batches/{b.pk}/resume/",
                                     {"note": "go"}, format="json")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, PayoutBatchStatus.PENDING)

    def test_resume_pending_returns_error(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        r = _client(self.admin).post(f"{BASE}/batches/{b.pk}/resume/")
        self.assertIn(r.status_code, [400, 409])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: release-lock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchReleaseLockTest(TestCase):
    def setUp(self):
        self.su    = StaffUserFactory(is_superuser=True)
        self.staff = StaffUserFactory(is_superuser=False)

    def test_superuser_can_release(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        b.acquire_lock("stuck-worker")
        r = _client(self.su).post(f"{BASE}/batches/{b.pk}/release-lock/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("released", r.data["detail"].lower())
        b.refresh_from_db()
        self.assertIsNone(b.locked_at)

    def test_non_superuser_forbidden(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        b.acquire_lock("w")
        r = _client(self.staff).post(f"{BASE}/batches/{b.pk}/release-lock/")
        self.assertEqual(r.status_code, 403)

    def test_unlocked_batch_ok(self):
        b = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        r = _client(self.su).post(f"{BASE}/batches/{b.pk}/release-lock/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("not locked", r.data["detail"])

    def test_nonexistent_404(self):
        import uuid
        r = _client(self.su).post(f"{BASE}/batches/{uuid.uuid4()}/release-lock/")
        self.assertEqual(r.status_code, 404)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: refresh-totals
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchRefreshTotalsTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_refresh_totals_recomputes(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING,
                                   total_amount=Decimal("0.00"), item_count=0)
        user = UserFactory()
        PayoutItemFactory(batch=batch, user=user,
                          gross_amount=Decimal("500.00"),
                          fee_amount=Decimal("9.25"),
                          net_amount=Decimal("490.75"))
        r = _client(self.admin).post(f"{BASE}/batches/{batch.pk}/refresh-totals/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(r.data["total_amount"]), Decimal("500.00"))
        self.assertEqual(r.data["item_count"], 1)

    def test_nonexistent_404(self):
        import uuid
        r = _client(self.admin).post(f"{BASE}/batches/{uuid.uuid4()}/refresh-totals/")
        self.assertEqual(r.status_code, 404)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: financial-summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchFinancialSummaryTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_returns_aggregated_totals(self):
        PayoutBatchFactory(total_amount=Decimal("1000"), total_fee=Decimal("18.50"),
                           net_amount=Decimal("981.50"))
        r = _client(self.admin).get(f"{BASE}/batches/financial-summary/")
        self.assertEqual(r.status_code, 200)
        for k in ("total_batches", "total_amount", "total_fee", "total_net"):
            self.assertIn(k, r.data)

    def test_empty_returns_zeros(self):
        PayoutBatch.objects.all().delete()
        r = _client(self.admin).get(f"{BASE}/batches/financial-summary/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_batches"], 0)

    def test_requires_auth(self):
        r = APIClient().get(f"{BASE}/batches/financial-summary/")
        self.assertIn(r.status_code, [401, 403])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: gateways
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchGatewaysTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_returns_all_gateways(self):
        r = _client(self.admin).get(f"{BASE}/batches/gateways/")
        self.assertEqual(r.status_code, 200)
        values = {g["value"] for g in r.data}
        for gw in PaymentGateway.values:
            self.assertIn(gw, values)

    def test_each_has_fee_type(self):
        r = _client(self.admin).get(f"{BASE}/batches/gateways/")
        for gw in r.data:
            self.assertIn("fee_type", gw)

    def test_requires_staff(self):
        r = _client(UserFactory()).get(f"{BASE}/batches/gateways/")
        self.assertEqual(r.status_code, 403)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BATCH: choices
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BatchChoicesTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_returns_all_enum_groups(self):
        r = _client(self.admin).get(f"{BASE}/batches/choices/")
        self.assertEqual(r.status_code, 200)
        for key in ("batch_statuses", "item_statuses", "priority_levels",
                    "gateways", "priority_reasons", "fee_types"):
            self.assertIn(key, r.data)

    def test_gateway_choices_match_paymentgateway(self):
        r = _client(self.admin).get(f"{BASE}/batches/choices/")
        values = {g["value"] for g in r.data["gateways"]}
        self.assertEqual(values, set(PaymentGateway.values))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ITEM: retry (single)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ItemRetrySingleTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)

    @patch("api.payout_queue.services._get_processor")
    def test_retry_due_item(self, mock_proc):
        item = PayoutItemFactory(
            batch=self.batch, user=self.user,
            gateway=PaymentGateway.BKASH, status=PayoutItemStatus.RETRYING,
            next_retry_at=timezone.now() - timedelta(seconds=1), retry_count=1,
        )
        mock_proc.return_value.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="GW_OK"
        )
        r = _client(self.admin).post(f"{BASE}/items/{item.pk}/retry/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["retried_count"], 1)
        self.assertEqual(r.data["success_count"], 1)

    def test_not_due_returns_400(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user,
                                 status=PayoutItemStatus.QUEUED)
        r = _client(self.admin).post(f"{BASE}/items/{item.pk}/retry/")
        self.assertEqual(r.status_code, 400)

    def test_requires_staff(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        r = _client(self.user).post(f"{BASE}/items/{item.pk}/retry/")
        self.assertEqual(r.status_code, 403)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ITEM: retry-due (bulk)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ItemRetryDueTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)

    @patch("api.payout_queue.services._get_processor")
    def test_retries_due_items(self, mock_proc):
        PayoutItemFactory(
            batch=self.batch, user=self.user,
            gateway=PaymentGateway.BKASH, status=PayoutItemStatus.RETRYING,
            next_retry_at=timezone.now() - timedelta(seconds=1), retry_count=1,
        )
        mock_proc.return_value.send_payout.return_value = PayoutResult(
            success=True, gateway_reference="BULK_OK"
        )
        r = _client(self.admin).post(f"{BASE}/items/retry-due/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("retried_count", r.data)

    def test_no_items_returns_zeros(self):
        r = _client(self.admin).post(f"{BASE}/items/retry-due/", {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["retried_count"], 0)

    def test_batch_id_scoping(self):
        other_batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)
        PayoutItemFactory(batch=other_batch, user=self.user,
                          status=PayoutItemStatus.RETRYING,
                          next_retry_at=timezone.now() - timedelta(seconds=1))
        with patch("api.payout_queue.services._get_processor") as mock_proc:
            mock_proc.return_value.send_payout.return_value = PayoutResult(
                success=True, gateway_reference="S")
            r = _client(self.admin).post(f"{BASE}/items/retry-due/",
                                         {"batch_id": str(self.batch.pk)},
                                         format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["retried_count"], 0)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ITEM: verify
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ItemVerifyTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory(gateway=PaymentGateway.BKASH)

    @patch("api.payout_queue.services._get_processor")
    def test_verify_success(self, mock_proc):
        item = PayoutItemFactory(batch=self.batch, user=self.user,
                                 gateway=PaymentGateway.BKASH,
                                 status=PayoutItemStatus.SUCCESS)
        PayoutItem.objects.filter(pk=item.pk).update(gateway_reference="GW_REF_001")
        mock_proc.return_value.verify_transaction.return_value = PayoutResult(
            success=True, gateway_reference="GW_REF_001",
            raw_response={"transactionStatus": "Completed"})
        r = _client(self.admin).post(f"{BASE}/items/{item.pk}/verify/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["verified_success"])

    def test_no_gateway_reference_400(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user,
                                 status=PayoutItemStatus.QUEUED)
        PayoutItem.objects.filter(pk=item.pk).update(gateway_reference="")
        r = _client(self.admin).post(f"{BASE}/items/{item.pk}/verify/")
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_404(self):
        import uuid
        r = _client(self.admin).post(f"{BASE}/items/{uuid.uuid4()}/verify/")
        self.assertEqual(r.status_code, 404)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ITEM: validate-account
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ItemValidateAccountTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    @patch("api.payout_queue.services._get_processor")
    def test_valid_account(self, mock_proc):
        mock_proc.return_value.validate_account.return_value = True
        r = _client(self.admin).post(f"{BASE}/items/validate-account/",
                                     {"gateway": "BKASH", "account_number": "01712345678"},
                                     format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_valid"])

    @patch("api.payout_queue.services._get_processor")
    def test_invalid_account(self, mock_proc):
        mock_proc.return_value.validate_account.return_value = False
        r = _client(self.admin).post(f"{BASE}/items/validate-account/",
                                     {"gateway": "BKASH", "account_number": "BAD"},
                                     format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["is_valid"])

    def test_missing_gateway_400(self):
        r = _client(self.admin).post(f"{BASE}/items/validate-account/",
                                     {"account_number": "01712345678"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_all_gateways_accepted(self):
        for gw in PaymentGateway.values:
            with patch("api.payout_queue.services._get_processor") as mp:
                mp.return_value.validate_account.return_value = True
                r = _client(self.admin).post(f"{BASE}/items/validate-account/",
                                             {"gateway": gw, "account_number": "01712345678"},
                                             format="json")
                self.assertEqual(r.status_code, 200, f"Gateway {gw}: {r.status_code}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGS: by-task
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LogByTaskTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()

    def test_by_task_returns_match(self):
        batch = PayoutBatchFactory()
        BulkProcessLogFactory(batch=batch, task_id="celery-task-999")
        r = _client(self.admin).get(f"{BASE}/logs/by-task/?task_id=celery-task-999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_no_match_returns_empty(self):
        r = _client(self.admin).get(f"{BASE}/logs/by-task/?task_id=no-such-task")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_missing_param_400(self):
        r = _client(self.admin).get(f"{BASE}/logs/by-task/")
        self.assertEqual(r.status_code, 400)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIORITIES: set-priority / deactivate / active-for-user
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PriorityEndpointsTest(TestCase):
    def setUp(self):
        self.admin = StaffUserFactory()
        self.user  = UserFactory()

    def test_set_priority_201(self):
        r = _client(self.admin).post(f"{BASE}/priorities/set-priority/", {
            "user_id":   self.user.pk,
            "priority":  PriorityLevel.URGENT,
            "reason":    WithdrawalPriorityReason.ADMIN_OVERRIDE,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["priority"], PriorityLevel.URGENT)

    def test_set_priority_invalid_choice_400(self):
        r = _client(self.admin).post(f"{BASE}/priorities/set-priority/", {
            "user_id": self.user.pk, "priority": "GODMODE", "reason": "BAD",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_set_priority_nonexistent_user_404(self):
        r = _client(self.admin).post(f"{BASE}/priorities/set-priority/", {
            "user_id": 9_999_999, "priority": PriorityLevel.NORMAL,
            "reason":  WithdrawalPriorityReason.USER_REQUEST,
        }, format="json")
        self.assertEqual(r.status_code, 404)

    def test_set_priority_requires_staff(self):
        r = _client(self.user).post(f"{BASE}/priorities/set-priority/", {
            "user_id": self.user.pk, "priority": PriorityLevel.NORMAL,
            "reason":  WithdrawalPriorityReason.USER_REQUEST,
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_deactivate_201(self):
        wp = WithdrawalPriorityFactory(user=self.user, is_active=True)
        r = _client(self.admin).post(f"{BASE}/priorities/{wp.pk}/deactivate/")
        self.assertEqual(r.status_code, 200)
        wp.refresh_from_db()
        self.assertFalse(wp.is_active)

    def test_deactivate_nonexistent_404(self):
        import uuid
        r = _client(self.admin).post(f"{BASE}/priorities/{uuid.uuid4()}/deactivate/")
        self.assertEqual(r.status_code, 404)

    def test_active_for_user_returns_highest(self):
        WithdrawalPriorityFactory(user=self.user, priority=PriorityLevel.NORMAL,
                                  reason=WithdrawalPriorityReason.USER_REQUEST,
                                  is_active=True)
        WithdrawalPriorityFactory(user=self.user, priority=PriorityLevel.URGENT,
                                  reason=WithdrawalPriorityReason.ADMIN_OVERRIDE,
                                  is_active=True)
        r = _client(self.admin).get(
            f"{BASE}/priorities/active-for-user/?user_id={self.user.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["priority"], PriorityLevel.URGENT)

    def test_active_for_user_none_returns_null_priority(self):
        new_u = UserFactory()
        r = _client(self.admin).get(
            f"{BASE}/priorities/active-for-user/?user_id={new_u.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data["priority"])

    def test_active_for_user_missing_param_400(self):
        r = _client(self.admin).get(f"{BASE}/priorities/active-for-user/")
        self.assertEqual(r.status_code, 400)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEE-SUMMARY + HEALTH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FeeSummaryTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_bkash_200(self):
        r = _client(self.user).get(f"{BASE}/fee-summary/?gateway=BKASH")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["gateway"], "BKASH")
        self.assertIn("fee_type", r.data)

    def test_all_gateways_200(self):
        for gw in PaymentGateway.values:
            r = _client(self.user).get(f"{BASE}/fee-summary/?gateway={gw}")
            self.assertEqual(r.status_code, 200, f"Gateway {gw}: {r.status_code}")

    def test_missing_gateway_400(self):
        r = _client(self.user).get(f"{BASE}/fee-summary/")
        self.assertEqual(r.status_code, 400)

    def test_invalid_gateway_400(self):
        r = _client(self.user).get(f"{BASE}/fee-summary/?gateway=PAYPAL")
        self.assertEqual(r.status_code, 400)

    def test_unauthenticated_401(self):
        r = APIClient().get(f"{BASE}/fee-summary/?gateway=BKASH")
        self.assertIn(r.status_code, [401, 403])

    def test_example_in_response(self):
        r = _client(self.user).get(f"{BASE}/fee-summary/?gateway=BKASH")
        if "example" in r.data:
            self.assertIn("gross", r.data["example"])

class HealthCheckTest(TestCase):
    def test_returns_200_no_auth(self):
        r = APIClient().get(f"{BASE}/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ok")

    def test_db_ok(self):
        r = APIClient().get(f"{BASE}/health/")
        self.assertEqual(r.data["db"], "ok")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIEWS.PY: timeline field completeness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TimelineFieldsTest(TestCase):
    def setUp(self):
        self.user  = UserFactory()
        self.batch = PayoutBatchFactory()

    def test_new_fields_present(self):
        PayoutItemFactory(batch=self.batch, user=self.user,
                          status=PayoutItemStatus.QUEUED)
        r = _client(self.user).get(f"{BASE}/my-timeline/")
        self.assertEqual(r.status_code, 200)
        item = r.data["data"]["recent"][0]
        # New fields added in this round:
        for field in ("gateway_reference", "retry_count", "error_code",
                      "batch_name", "priority"):
            self.assertIn(field, item, f"'{field}' missing from timeline response")

    def test_pagination_params_honoured(self):
        for _ in range(25):
            PayoutItemFactory(batch=self.batch, user=self.user)
        r = _client(self.user).get(f"{BASE}/my-timeline/?limit=5&offset=0")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["data"]["limit"], 5)
        self.assertEqual(len(r.data["data"]["recent"]), 5)
        self.assertEqual(r.data["data"]["total_count"], 25)

    def test_bad_limit_400(self):
        r = _client(self.user).get(f"{BASE}/my-timeline/?limit=abc")
        self.assertEqual(r.status_code, 400)
