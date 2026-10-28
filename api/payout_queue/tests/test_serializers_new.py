"""
payout_queue/tests/test_serializers_new.py  ← NEW FILE  (Part 2 / File 10)

Tests for new/fixed serializer fields:
  SetWithdrawalPrioritySerializer — all validation paths
  ValidateAccountSerializer       — all gateways, missing fields
  PayoutItemSerializer            — gateway_reference, retry_count, error_code
  PayoutBatchSerializer           — computed_net_amount, locked_by
"""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from ..choices import (
    PaymentGateway, PriorityLevel, WithdrawalPriorityReason, PayoutBatchStatus,
)
from ..serializers import (
    SetWithdrawalPrioritySerializer,
    ValidateAccountSerializer,
    PayoutItemSerializer,
    PayoutBatchSerializer,
    CreatePayoutBatchSerializer,
    PayoutItemInputSerializer,
)
from .factories import (
    UserFactory, StaffUserFactory,
    PayoutBatchFactory, PayoutItemFactory,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SetWithdrawalPrioritySerializer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SetWithdrawalPrioritySerializerTest(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def _valid(self, **overrides):
        d = {
            "user_id":  self.user.pk,
            "priority": PriorityLevel.URGENT,
            "reason":   WithdrawalPriorityReason.ADMIN_OVERRIDE,
        }
        d.update(overrides)
        return d

    def test_valid_minimal(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid())
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_priority(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid(priority="GODMODE"))
        self.assertFalse(s.is_valid())
        self.assertIn("priority", s.errors)

    def test_invalid_reason(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid(reason="BECAUSE"))
        self.assertFalse(s.is_valid())
        self.assertIn("reason", s.errors)

    def test_future_expires_at_valid(self):
        future = (timezone.now() + timedelta(hours=4)).isoformat()
        s = SetWithdrawalPrioritySerializer(data=self._valid(expires_at=future))
        self.assertTrue(s.is_valid(), s.errors)

    def test_past_expires_at_invalid(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        s = SetWithdrawalPrioritySerializer(data=self._valid(expires_at=past))
        self.assertFalse(s.is_valid())
        self.assertIn("expires_at", s.errors)

    def test_expires_at_null_valid(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid(expires_at=None))
        self.assertTrue(s.is_valid(), s.errors)

    def test_payout_item_id_optional(self):
        import uuid
        s = SetWithdrawalPrioritySerializer(
            data=self._valid(payout_item_id=str(uuid.uuid4())))
        self.assertTrue(s.is_valid(), s.errors)

    def test_payout_item_id_null_valid(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid(payout_item_id=None))
        self.assertTrue(s.is_valid(), s.errors)

    def test_reason_note_defaults_empty(self):
        s = SetWithdrawalPrioritySerializer(data=self._valid())
        s.is_valid()
        self.assertEqual(s.validated_data["reason_note"], "")

    def test_all_priority_levels_accepted(self):
        for level in PriorityLevel.values:
            s = SetWithdrawalPrioritySerializer(data=self._valid(priority=level))
            self.assertTrue(s.is_valid(), f"Level {level}: {s.errors}")

    def test_all_reasons_accepted(self):
        for reason in WithdrawalPriorityReason.values:
            s = SetWithdrawalPrioritySerializer(
                data=self._valid(reason=reason))
            self.assertTrue(s.is_valid(), f"Reason {reason}: {s.errors}")

    def test_missing_user_id_invalid(self):
        d = self._valid()
        del d["user_id"]
        s = SetWithdrawalPrioritySerializer(data=d)
        self.assertFalse(s.is_valid())
        self.assertIn("user_id", s.errors)

    def test_missing_priority_invalid(self):
        d = self._valid()
        del d["priority"]
        s = SetWithdrawalPrioritySerializer(data=d)
        self.assertFalse(s.is_valid())

    def test_missing_reason_invalid(self):
        d = self._valid()
        del d["reason"]
        s = SetWithdrawalPrioritySerializer(data=d)
        self.assertFalse(s.is_valid())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ValidateAccountSerializer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ValidateAccountSerializerTest(TestCase):

    def test_valid(self):
        s = ValidateAccountSerializer(data={
            "gateway": PaymentGateway.BKASH, "account_number": "01712345678"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_gateway(self):
        s = ValidateAccountSerializer(data={"account_number": "01712345678"})
        self.assertFalse(s.is_valid())
        self.assertIn("gateway", s.errors)

    def test_missing_account_number(self):
        s = ValidateAccountSerializer(data={"gateway": PaymentGateway.BKASH})
        self.assertFalse(s.is_valid())
        self.assertIn("account_number", s.errors)

    def test_invalid_gateway_choice(self):
        s = ValidateAccountSerializer(data={
            "gateway": "FAKE_GW", "account_number": "01712345678"})
        self.assertFalse(s.is_valid())
        self.assertIn("gateway", s.errors)

    def test_all_valid_gateways_accepted(self):
        for gw in PaymentGateway.values:
            s = ValidateAccountSerializer(data={
                "gateway": gw, "account_number": "01712345678"})
            self.assertTrue(s.is_valid(), f"Gateway {gw}: {s.errors}")

    def test_empty_account_number_invalid(self):
        s = ValidateAccountSerializer(data={
            "gateway": PaymentGateway.BKASH, "account_number": ""})
        self.assertFalse(s.is_valid())

    def test_account_number_max_length_50(self):
        # 51 chars → invalid
        s = ValidateAccountSerializer(data={
            "gateway": PaymentGateway.BKASH,
            "account_number": "A" * 51})
        self.assertFalse(s.is_valid())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PayoutItemSerializer — new fields
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PayoutItemSerializerNewFieldsTest(TestCase):

    def setUp(self):
        self.batch = PayoutBatchFactory()
        self.user  = UserFactory()

    def test_gateway_reference_exposed(self):
        """FIX: gateway_reference was missing from serializer."""
        item = PayoutItemFactory(batch=self.batch, user=self.user)
        from ..models import PayoutItem
        PayoutItem.objects.filter(pk=item.pk).update(gateway_reference="GW_TEST_001")
        item.refresh_from_db()
        s = PayoutItemSerializer(item)
        self.assertIn("gateway_reference", s.data)
        self.assertEqual(s.data["gateway_reference"], "GW_TEST_001")

    def test_retry_count_exposed(self):
        """FIX: retry_count was missing from serializer."""
        item = PayoutItemFactory(batch=self.batch, user=self.user, retry_count=2)
        s = PayoutItemSerializer(item)
        self.assertIn("retry_count", s.data)
        self.assertEqual(s.data["retry_count"], 2)

    def test_error_code_exposed(self):
        """FIX: error_code was missing from serializer."""
        item = PayoutItemFactory(batch=self.batch, user=self.user,
                                  error_code="TRX_FAIL_001")
        s = PayoutItemSerializer(item)
        self.assertIn("error_code", s.data)
        self.assertEqual(s.data["error_code"], "TRX_FAIL_001")

    def test_can_retry_false_for_success(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status="SUCCESS")
        s = PayoutItemSerializer(item)
        self.assertFalse(s.data["can_retry"])

    def test_is_terminal_true_for_success(self):
        item = PayoutItemFactory(batch=self.batch, user=self.user, status="SUCCESS")
        s = PayoutItemSerializer(item)
        self.assertTrue(s.data["is_terminal"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PayoutBatchSerializer — new fields
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PayoutBatchSerializerNewFieldsTest(TestCase):

    def test_computed_net_amount_exposed(self):
        """FIX: computed_net_amount was missing."""
        batch = PayoutBatchFactory(
            total_amount=Decimal("1000.00"), total_fee=Decimal("18.50"))
        s = PayoutBatchSerializer(batch)
        self.assertIn("computed_net_amount", s.data)

    def test_locked_by_exposed(self):
        """FIX: locked_by was missing — ops needs to know which worker holds lock."""
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("celery-worker-abc")
        s = PayoutBatchSerializer(batch)
        self.assertIn("locked_by", s.data)
        self.assertEqual(s.data["locked_by"], "celery-worker-abc")

    def test_is_locked_true_when_locked(self):
        batch = PayoutBatchFactory(status=PayoutBatchStatus.PENDING)
        batch.acquire_lock("w")
        s = PayoutBatchSerializer(batch)
        self.assertTrue(s.data["is_locked"])

    def test_is_locked_false_when_not_locked(self):
        batch = PayoutBatchFactory()
        s = PayoutBatchSerializer(batch)
        self.assertFalse(s.data["is_locked"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CreatePayoutBatchSerializer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CreatePayoutBatchSerializerTest(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def _valid(self, **overrides):
        d = {"name": "My Batch", "gateway": PaymentGateway.BKASH}
        d.update(overrides)
        return d

    def test_valid_minimal(self):
        s = CreatePayoutBatchSerializer(data=self._valid())
        self.assertTrue(s.is_valid(), s.errors)

    def test_blank_name_fails(self):
        s = CreatePayoutBatchSerializer(data=self._valid(name="   "))
        self.assertFalse(s.is_valid())
        self.assertIn("name", s.errors)

    def test_name_stripped(self):
        s = CreatePayoutBatchSerializer(data=self._valid(name="  Padded  "))
        s.is_valid()
        self.assertEqual(s.validated_data["name"], "Padded")

    def test_invalid_gateway(self):
        s = CreatePayoutBatchSerializer(data=self._valid(gateway="FAKE"))
        self.assertFalse(s.is_valid())
        self.assertIn("gateway", s.errors)

    def test_default_priority_normal(self):
        s = CreatePayoutBatchSerializer(data=self._valid())
        s.is_valid()
        self.assertEqual(s.validated_data["priority"], PriorityLevel.NORMAL)

    def test_items_default_empty_list(self):
        s = CreatePayoutBatchSerializer(data=self._valid())
        s.is_valid()
        self.assertEqual(s.validated_data["items"], [])

    def test_with_items(self):
        s = CreatePayoutBatchSerializer(data=self._valid(items=[{
            "user_id": self.user.pk,
            "account_number": "01712345678",
            "gross_amount": "500.00",
        }]))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(len(s.validated_data["items"]), 1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PayoutItemInputSerializer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PayoutItemInputSerializerTest(TestCase):

    def setUp(self):
        self.user = UserFactory()

    def _valid(self, **overrides):
        d = {"user_id": self.user.pk,
             "account_number": "01712345678",
             "gross_amount": "500.00"}
        d.update(overrides)
        return d

    def test_valid(self):
        s = PayoutItemInputSerializer(data=self._valid())
        self.assertTrue(s.is_valid(), s.errors)

    def test_below_minimum_fails(self):
        s = PayoutItemInputSerializer(data=self._valid(gross_amount="0.50"))
        self.assertFalse(s.is_valid())
        self.assertIn("gross_amount", s.errors)

    def test_above_maximum_fails(self):
        s = PayoutItemInputSerializer(data=self._valid(gross_amount="9999999.00"))
        self.assertFalse(s.is_valid())
        self.assertIn("gross_amount", s.errors)

    def test_metadata_defaults_empty_dict(self):
        s = PayoutItemInputSerializer(data=self._valid())
        s.is_valid()
        self.assertEqual(s.validated_data["metadata"], {})

    def test_note_defaults_empty_string(self):
        s = PayoutItemInputSerializer(data=self._valid())
        s.is_valid()
        self.assertEqual(s.validated_data["note"], "")
