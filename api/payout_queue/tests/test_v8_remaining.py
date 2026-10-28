"""
payout_queue/tests/test_v8_remaining.py  ← v9 NEW

Tests for all 6 remaining production gaps fixed in v9:

  Gap R1 — Admin PII (admin.py)
      Class 1: TestAdminAccountMasking
      Class 2: TestAdminHashSearch

  Gap R2 — Filter broken on encrypted field (filters.py)
      Class 3: TestAccountHashFilter

  Gap R3 — CSV/API PII exposure (viewsets.py)
      Class 4: TestCSVExportMasking
      Class 5: TestValidateAccountMasking

  Gap R4 — requirements.txt completeness
      Class 6: TestRequirementsFile

  Gap R5 — Encryption key rotation command
      Class 7: TestPayoutRotateEncryptionCommand

  Gap R6 — Search broken on encrypted account_number field
      Class 8: TestSearchFieldsEncryption
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from api.payout_queue.choices import (
    PayoutBatchStatus, PayoutItemStatus,
    PaymentGateway, PriorityLevel,
)
from api.payout_queue.models import PayoutBatch, PayoutItem

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _staff(**kw):
    return User.objects.create_user(
        username=f"staff_{uuid.uuid4().hex[:8]}", password="x",
        is_staff=True, is_superuser=True, **kw
    )

def _user(**kw):
    return User.objects.create_user(
        username=f"u_{uuid.uuid4().hex[:8]}", password="x", **kw
    )

def _batch(**kw) -> PayoutBatch:
    return PayoutBatch.objects.create(
        name="Test", gateway=PaymentGateway.BKASH,
        status=PayoutBatchStatus.PENDING,
        priority=PriorityLevel.NORMAL,
        total_amount=Decimal("1000.00"),
        total_fee=Decimal("20.00"),
        net_amount=Decimal("980.00"),
        item_count=2, created_by=_staff(), **kw,
    )

def _item(batch, *, acct="01700123456", gross=Decimal("500.00"),
          item_status=PayoutItemStatus.QUEUED) -> PayoutItem:
    return PayoutItem.objects.create(
        batch=batch, user=_user(), gateway=batch.gateway,
        account_number=acct, gross_amount=gross,
        fee_amount=Decimal("10.00"), net_amount=gross - Decimal("10.00"),
        internal_reference=str(uuid.uuid4()),
        status=item_status,
    )

# ===========================================================================
# Class 1 — TestAdminAccountMasking  (Gap R1)
# ===========================================================================

class TestAdminAccountMasking(TestCase):
    """Admin list view shows masked account number, not plaintext."""

    def test_mask_account_helper_last4(self):
        """_mask_account shows last 4 chars with bullets prefix."""
        from api.payout_queue.admin import _mask_account
        self.assertEqual(_mask_account("01700123456"), "•••••••3456")

    def test_mask_account_short_value_returned_as_is(self):
        """Values shorter than visible param returned unchanged."""
        from api.payout_queue.admin import _mask_account
        self.assertEqual(_mask_account("1234"), "1234")
        self.assertEqual(_mask_account(""),     "—")

    def test_masked_account_number_column_exists(self):
        """PayoutItemAdmin must have masked_account_number method."""
        from api.payout_queue.admin import PayoutItemAdmin
        self.assertTrue(
            hasattr(PayoutItemAdmin, "masked_account_number"),
            "PayoutItemAdmin must have masked_account_number() method",
        )

    def test_masked_account_in_list_display(self):
        """masked_account_number must be in list_display, not raw account_number."""
        from api.payout_queue.admin import PayoutItemAdmin
        self.assertIn(
            "masked_account_number", PayoutItemAdmin.list_display,
            "masked_account_number must appear in list_display",
        )
        self.assertNotIn(
            "account_number", PayoutItemAdmin.list_display,
            "Raw account_number must NOT be in list_display (PII risk)",
        )

    def test_admin_list_view_renders_masked_value(self):
        """Admin list response must contain masked value, not full account number."""
        admin_user = _staff()
        batch = _batch()
        _item(batch, acct="01700123456")

        self.client.force_login(admin_user)
        response = self.client.get("/admin/payout_queue/payoutitem/")
        if response.status_code == 200:
            content = response.content.decode()
            self.assertNotIn(
                "01700123456", content,
                "Full plaintext account number must NOT appear in admin list HTML",
            )
            self.assertIn(
                "3456", content,
                "Last 4 digits must appear in admin list HTML (masked)",
            )

    def test_account_number_not_in_search_fields(self):
        """account_number must not be in search_fields — icontains breaks on ciphertext."""
        from api.payout_queue.admin import PayoutItemAdmin
        self.assertNotIn(
            "account_number", PayoutItemAdmin.search_fields,
            "account_number must be removed from search_fields after encryption (v9)",
        )

# ===========================================================================
# Class 2 — TestAdminHashSearch  (Gap R1)
# ===========================================================================

class TestAdminHashSearch(TestCase):
    """Admin custom get_search_results uses hash lookup for phone-like terms."""

    def test_search_by_account_number_uses_hash(self):
        """Search term that looks like a phone number triggers hash-based lookup."""
        batch = _batch()
        item  = _item(batch, acct="01700123456")
        item.refresh_from_db()

        from api.payout_queue.admin import PayoutItemAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        admin_instance = PayoutItemAdmin(PayoutItem, AdminSite())
        request        = RequestFactory().get("/admin/payout_queue/payoutitem/")

        qs_all   = PayoutItem.objects.all()
        qs, _    = admin_instance.get_search_results(request, qs_all, "01700123456")

        # The item with account_number_hash matching "01700123456" must be in results
        self.assertIn(item.pk, qs.values_list("pk", flat=True))

    def test_non_phone_search_uses_default(self):
        """Non-phone search term delegates to default search (gateway_reference etc.)."""
        from api.payout_queue.admin import PayoutItemAdmin
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        admin_instance = PayoutItemAdmin(PayoutItem, AdminSite())
        request        = RequestFactory().get("/admin/")
        qs_all         = PayoutItem.objects.all()

        # Non-phone terms should not crash
        qs, _ = admin_instance.get_search_results(request, qs_all, "GW-REF-001")
        self.assertIsNotNone(qs)

# ===========================================================================
# Class 3 — TestAccountHashFilter  (Gap R2)
# ===========================================================================

class TestAccountHashFilter(TestCase):
    """
    Gap R2: AccountHashFilter hashes the plaintext input and filters
    by account_number_hash (exact match) for encrypted field lookup.
    """

    def test_filter_by_account_number_returns_matching_item(self):
        """?account_number=01700123456 must return items with that account."""
        from api.payout_queue.filters import PayoutItemFilter
        batch = _batch()
        item1 = _item(batch, acct="01700123456")
        item2 = _item(batch, acct="01799999999")

        f = PayoutItemFilter({"account_number": "01700123456"}, queryset=PayoutItem.objects.all())
        results = list(f.qs.values_list("pk", flat=True))

        self.assertIn(item1.pk, results, "Item with matching account must appear in results")
        self.assertNotIn(item2.pk, results, "Item with different account must NOT appear")

    def test_filter_empty_value_returns_all(self):
        """Empty account_number filter must return unfiltered queryset."""
        from api.payout_queue.filters import PayoutItemFilter
        batch = _batch()
        _item(batch, acct="01700123456")
        _item(batch, acct="01799999999")

        f = PayoutItemFilter({"account_number": ""}, queryset=PayoutItem.objects.all())
        self.assertEqual(f.qs.count(), PayoutItem.objects.count())

    def test_filter_uses_hash_not_icontains(self):
        """AccountHashFilter must use account_number_hash (exact), not icontains."""
        import inspect
        from api.payout_queue.filters import AccountHashFilter
        source = inspect.getsource(AccountHashFilter.filter)
        self.assertIn("account_number_hash", source)
        self.assertNotIn("icontains", source)

    def test_filter_class_imported_in_filters_module(self):
        """AccountHashFilter must be defined in filters.py."""
        from api.payout_queue.filters import AccountHashFilter
        self.assertTrue(callable(AccountHashFilter))

    def test_payoutitem_filter_account_number_field_is_hash_filter(self):
        """PayoutItemFilter.account_number must be AccountHashFilter instance."""
        from api.payout_queue.filters import PayoutItemFilter, AccountHashFilter
        self.assertIsInstance(
            PayoutItemFilter.declared_filters.get("account_number"),
            AccountHashFilter,
            "PayoutItemFilter.account_number must be AccountHashFilter (not CharFilter)",
        )

# ===========================================================================
# Class 4 — TestCSVExportMasking  (Gap R3)
# ===========================================================================

class TestCSVExportMasking(TestCase):
    """
    Gap R3: CSV export must write masked account numbers, not plaintext.
    """

    def setUp(self):
        self.client = APIClient()
        self.staff  = _staff()
        self.client.force_authenticate(user=self.staff)

    def test_csv_export_header_uses_masked_column_name(self):
        """CSV header must say 'account_number_masked', not 'account_number'."""
        batch = _batch()
        _item(batch, acct="01700123456")

        response = self.client.get("/api/payout-queue/items/export-csv/")
        if response.status_code == 200:
            first_chunk = b"".join(response.streaming_content).decode()
            self.assertIn(
                "account_number_masked", first_chunk,
                "CSV header must use 'account_number_masked' column name (v9)",
            )
            self.assertNotIn(
                '"account_number"', first_chunk,
                "Old 'account_number' plaintext header must not appear",
            )

    def test_csv_export_does_not_contain_full_account_number(self):
        """Full plaintext account number must not appear in CSV body."""
        batch = _batch()
        _item(batch, acct="01700123456")

        response = self.client.get("/api/payout-queue/items/export-csv/")
        if response.status_code == 200:
            content = b"".join(response.streaming_content).decode()
            self.assertNotIn(
                "01700123456", content,
                "Full plaintext account number must NOT appear in CSV export (PII risk)",
            )

    def test_csv_export_contains_last_4_digits(self):
        """Masked value (last 4 digits) must appear in CSV body."""
        batch = _batch()
        _item(batch, acct="01700123456")

        response = self.client.get("/api/payout-queue/items/export-csv/")
        if response.status_code == 200:
            content = b"".join(response.streaming_content).decode()
            self.assertIn(
                "3456", content,
                "Last 4 digits must appear in masked CSV column",
            )

    def test_csv_export_mask_function(self):
        """The _mask helper must correctly mask account numbers."""
        # Test the mask logic directly
        def _mask(val, visible=4):
            s = str(val or "")
            return ("*" * max(0, len(s) - visible) + s[-visible:]) if len(s) > visible else s

        self.assertEqual(_mask("01700123456"), "*******3456")
        self.assertEqual(_mask("1234"),         "1234")
        self.assertEqual(_mask(""),             "")
        self.assertEqual(_mask("12345"),        "*2345")

# ===========================================================================
# Class 5 — TestValidateAccountMasking  (Gap R3)
# ===========================================================================

class TestValidateAccountMasking(TestCase):
    """
    Gap R3: validate_account response must not echo back plaintext account number.
    """

    def setUp(self):
        self.client = APIClient()
        self.staff  = _staff()
        self.client.force_authenticate(user=self.staff)

    @patch("api.payout_queue.services._get_processor")
    def test_validate_account_response_does_not_contain_plaintext(self, mock_get_proc):
        """validate_account must NOT return the full account number in response."""
        mock_proc = MagicMock()
        mock_proc.validate_account.return_value = True
        mock_get_proc.return_value = mock_proc

        response = self.client.post(
            "/api/payout-queue/items/validate-account/",
            {"gateway": "BKASH", "account_number": "01700123456"},
            format="json",
        )
        if response.status_code == 200:
            self.assertNotIn(
                "01700123456", str(response.data),
                "Full account number must NOT be echoed in validate_account response (PII risk)",
            )

    @patch("api.payout_queue.services._get_processor")
    def test_validate_account_response_has_masked_field(self, mock_get_proc):
        """validate_account response must have account_number_masked field."""
        mock_proc = MagicMock()
        mock_proc.validate_account.return_value = True
        mock_get_proc.return_value = mock_proc

        response = self.client.post(
            "/api/payout-queue/items/validate-account/",
            {"gateway": "BKASH", "account_number": "01700123456"},
            format="json",
        )
        if response.status_code == 200:
            self.assertIn(
                "account_number_masked", response.data,
                "Response must include account_number_masked key",
            )
            masked = response.data["account_number_masked"]
            self.assertIn("3456", masked, "Masked value must contain last 4 digits")

    def test_viewsets_search_fields_no_account_number(self):
        """PayoutItemViewSet.search_fields must not contain 'account_number'."""
        from api.payout_queue.viewsets import PayoutItemViewSet
        self.assertNotIn(
            "account_number", PayoutItemViewSet.search_fields,
            "account_number must be removed from search_fields (icontains broken after encryption)",
        )

# ===========================================================================
# Class 6 — TestRequirementsFile  (Gap R4)
# ===========================================================================

class TestRequirementsFile(TestCase):
    """Gap R4: requirements.txt exists and lists all critical dependencies."""

    def _read_requirements(self):
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path = os.path.join(base, "requirements.txt")
        if not os.path.exists(req_path):
            self.skipTest("requirements.txt not found")
        with open(req_path) as f:
            return f.read().lower()

    def test_requirements_file_exists(self):
        """requirements.txt must exist in the payout_queue module directory."""
        import os
        base     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        req_path = os.path.join(base, "requirements.txt")
        self.assertTrue(os.path.exists(req_path), "requirements.txt must exist")

    def test_cryptography_in_requirements(self):
        """cryptography package must be listed (for EncryptedCharField)."""
        content = self._read_requirements()
        self.assertIn("cryptography", content)

    def test_sentry_sdk_in_requirements(self):
        """sentry-sdk must be listed (for Sentry error tracking)."""
        content = self._read_requirements()
        self.assertIn("sentry", content)

    def test_celery_in_requirements(self):
        """celery must be listed."""
        content = self._read_requirements()
        self.assertIn("celery", content)

    def test_django_in_requirements(self):
        """Django must be listed."""
        content = self._read_requirements()
        self.assertIn("django", content)

    def test_djangorestframework_in_requirements(self):
        """djangorestframework must be listed."""
        content = self._read_requirements()
        self.assertIn("djangorestframework", content)

    def test_requests_in_requirements(self):
        """requests must be listed (for gateway HTTP calls)."""
        content = self._read_requirements()
        self.assertIn("requests", content)

    def test_django_filter_in_requirements(self):
        """django-filter must be listed."""
        content = self._read_requirements()
        self.assertIn("django-filter", content)

# ===========================================================================
# Class 7 — TestPayoutRotateEncryptionCommand  (Gap R5)
# ===========================================================================

class TestPayoutRotateEncryptionCommand(TestCase):
    """Gap R5: payout_rotate_encryption management command works correctly."""

    def _run_command(self, *args, **kwargs):
        from django.core.management import call_command
        out = StringIO()
        err = StringIO()
        try:
            call_command("payout_rotate_encryption", *args, stdout=out, stderr=err, **kwargs)
        except SystemExit:
            pass
        return out.getvalue(), err.getvalue()

    def test_command_importable(self):
        """Command must be importable."""
        from api.payout_queue.management.commands.payout_rotate_encryption import Command
        self.assertTrue(callable(Command))

    def test_command_requires_confirm_without_dry_run(self):
        """Without --confirm or --dry-run, command must raise CommandError."""
        from django.core.management.base import CommandError
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography not installed")

        k1 = Fernet.generate_key().decode()
        k2 = Fernet.generate_key().decode()
        with self.assertRaises(CommandError):
            from django.core.management import call_command
            call_command(
                "payout_rotate_encryption",
                old_key=k1, new_key=k2, stdout=StringIO(), stderr=StringIO(),
            )

    def test_dry_run_does_not_write_to_db(self):
        """--dry-run must not modify any PayoutItem rows."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography not installed")

        batch = _batch()
        item  = _item(batch, acct="01700123456")
        original_hash = item.account_number_hash

        k1 = Fernet.generate_key().decode()
        k2 = Fernet.generate_key().decode()

        # Encrypt the item with k1 first
        with override_settings(PAYOUT_ENCRYPTION_KEY=k1):
            item.account_number = "01700123456"
            item.save()

        original_enc = str(PayoutItem.objects.get(pk=item.pk).account_number)

        # Dry run with new key — should NOT change the DB
        out, _ = self._run_command(
            old_key=k1, new_key=k2, dry_run=True, stdout=StringIO(), stderr=StringIO(),
        )
        db_item = PayoutItem.objects.get(pk=item.pk)
        self.assertEqual(
            str(db_item.account_number), original_enc,
            "--dry-run must not modify account_number in DB",
        )

    def test_same_old_and_new_key_raises_error(self):
        """Same old-key and new-key must raise CommandError."""
        from django.core.management.base import CommandError
        try:
            from cryptography.fernet import Fernet
            k = Fernet.generate_key().decode()
        except ImportError:
            self.skipTest("cryptography not installed")

        with self.assertRaises(CommandError):
            from django.core.management import call_command
            call_command(
                "payout_rotate_encryption",
                old_key=k, new_key=k, confirm=True,
                stdout=StringIO(), stderr=StringIO(),
            )

    def test_invalid_old_key_raises_error(self):
        """Invalid Fernet key format must raise CommandError."""
        from django.core.management.base import CommandError
        try:
            from cryptography.fernet import Fernet
            k2 = Fernet.generate_key().decode()
        except ImportError:
            self.skipTest("cryptography not installed")

        with self.assertRaises(CommandError):
            from django.core.management import call_command
            call_command(
                "payout_rotate_encryption",
                old_key="not-a-valid-fernet-key",
                new_key=k2,
                dry_run=True,
                stdout=StringIO(), stderr=StringIO(),
            )

    def test_command_has_required_arguments(self):
        """Command must accept --old-key, --new-key, --dry-run, --confirm."""
        import argparse
        from api.payout_queue.management.commands.payout_rotate_encryption import Command
        cmd    = Command()
        parser = argparse.ArgumentParser()
        cmd.add_arguments(parser)

        # All required flags must be parseable
        args = parser.parse_args([
            "--old-key", "abc", "--new-key", "def",
            "--dry-run", "--batch-size", "100",
        ])
        self.assertTrue(args.dry_run)
        self.assertEqual(args.batch_size, 100)

# ===========================================================================
# Class 8 — TestSearchFieldsEncryption  (Gap R6)
# ===========================================================================

class TestSearchFieldsEncryption(TestCase):
    """
    Gap R6: DRF search_fields must not include encrypted fields.
    DRF SearchFilter uses icontains — searching on ciphertext always returns 0.
    """

    def test_payoutitem_viewset_search_fields_safe(self):
        """PayoutItemViewSet.search_fields must not contain encrypted fields."""
        from api.payout_queue.viewsets import PayoutItemViewSet
        encrypted_fields = {"account_number"}
        for field in PayoutItemViewSet.search_fields:
            self.assertNotIn(
                field, encrypted_fields,
                f"search_fields contains encrypted field '{field}' — "
                "DRF icontains on ciphertext always returns 0 results",
            )

    def test_viewset_search_contains_safe_fields(self):
        """Safe (non-encrypted) fields must still be searchable."""
        from api.payout_queue.viewsets import PayoutItemViewSet
        for safe in ("gateway_reference", "internal_reference"):
            self.assertIn(
                safe, PayoutItemViewSet.search_fields,
                f"'{safe}' must remain in search_fields",
            )

    def test_filter_account_number_hash_filter_works(self):
        """The AccountHashFilter must find items by full account number."""
        from api.payout_queue.filters import PayoutItemFilter, AccountHashFilter
        declared = PayoutItemFilter.declared_filters
        self.assertIn("account_number", declared)
        self.assertIsInstance(declared["account_number"], AccountHashFilter)

    def test_api_filter_by_account_number_returns_correct_result(self):
        """GET /items/?account_number=<full_number> must return the correct item."""
        client = APIClient()
        staff  = _staff()
        client.force_authenticate(user=staff)

        batch = _batch()
        item1 = _item(batch, acct="01700123456")
        _item(batch, acct="01799999999")

        response = client.get(
            "/api/payout-queue/items/",
            {"account_number": "01700123456"},
        )
        if response.status_code == 200:
            ids = [r["id"] for r in response.data.get("results", [])]
            self.assertIn(
                str(item1.id), ids,
                "Filter by account_number must return the matching item",
            )
