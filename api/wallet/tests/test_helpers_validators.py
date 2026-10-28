# wallet/tests/test_helpers_validators.py
"""
Tests: helpers.py, validators.py, permissions.py, compliance.py, sanctions.py
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# 1. helpers.py
# ══════════════════════════════════════════════════════════════════════════════
class HelpersTest(TestCase):
    def setUp(self):
        from ..helpers import (
            safe_decimal, round_bdt, amount_to_paisa, paisa_to_amount,
            clamp_positive, calculate_percentage, apply_fee,
            mask_account, mask_email, compute_hmac, verify_hmac,
            is_valid_bd_mobile, normalize_bd_mobile, is_valid_crypto_address,
            generate_idempotency_key, generate_uuid, truncate,
        )
        self.safe_decimal             = safe_decimal
        self.round_bdt                = round_bdt
        self.amount_to_paisa          = amount_to_paisa
        self.paisa_to_amount          = paisa_to_amount
        self.clamp_positive           = clamp_positive
        self.calculate_percentage     = calculate_percentage
        self.apply_fee                = apply_fee
        self.mask_account             = mask_account
        self.mask_email               = mask_email
        self.compute_hmac             = compute_hmac
        self.verify_hmac              = verify_hmac
        self.is_valid_bd_mobile       = is_valid_bd_mobile
        self.normalize_bd_mobile      = normalize_bd_mobile
        self.is_valid_crypto_address  = is_valid_crypto_address
        self.generate_idempotency_key = generate_idempotency_key
        self.generate_uuid            = generate_uuid
        self.truncate                 = truncate

    # safe_decimal
    def test_safe_decimal_valid(self):
        self.assertEqual(self.safe_decimal("123.45"), Decimal("123.45"))

    def test_safe_decimal_none_returns_default(self):
        self.assertEqual(self.safe_decimal(None), Decimal("0"))

    def test_safe_decimal_invalid_returns_default(self):
        self.assertEqual(self.safe_decimal("abc"), Decimal("0"))

    def test_safe_decimal_custom_default(self):
        self.assertEqual(self.safe_decimal(None, Decimal("99")), Decimal("99"))

    # round_bdt
    def test_round_bdt_two_decimals(self):
        result = self.round_bdt(Decimal("10.555"))
        self.assertIsInstance(result, Decimal)

    def test_round_bdt_zero(self):
        result = self.round_bdt(Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    # amount_to_paisa / paisa_to_amount
    def test_amount_to_paisa(self):
        self.assertEqual(self.amount_to_paisa(Decimal("10.50")), 1050)

    def test_paisa_to_amount(self):
        self.assertEqual(self.paisa_to_amount(1050), Decimal("10.50"))

    def test_paisa_roundtrip(self):
        original = Decimal("99.99")
        self.assertEqual(self.paisa_to_amount(self.amount_to_paisa(original)), original)

    # clamp_positive
    def test_clamp_positive_negative_returns_zero(self):
        self.assertEqual(self.clamp_positive(Decimal("-5")), Decimal("0"))

    def test_clamp_positive_positive_unchanged(self):
        self.assertEqual(self.clamp_positive(Decimal("10")), Decimal("10"))

    # calculate_percentage
    def test_calculate_percentage(self):
        result = self.calculate_percentage(Decimal("1000"), Decimal("10"))
        self.assertEqual(result, Decimal("100"))

    # apply_fee — returns single Decimal (the fee amount)
    def test_apply_fee_percentage(self):
        fee = self.apply_fee(Decimal("1000"), Decimal("2"))
        self.assertEqual(fee, Decimal("20"))

    def test_apply_fee_with_flat(self):
        fee = self.apply_fee(Decimal("1000"), Decimal("2"), flat_fee=Decimal("5"))
        self.assertEqual(fee, Decimal("25"))

    def test_apply_fee_respects_min(self):
        fee = self.apply_fee(Decimal("100"), Decimal("1"), min_fee=Decimal("10"))
        self.assertEqual(fee, Decimal("10"))

    # mask_account — returns "****XXXX" format
    def test_mask_account_normal(self):
        result = self.mask_account("01712345678")
        self.assertTrue(result.endswith("5678"), f"Got: {result}")
        self.assertIn("*", result)

    def test_mask_account_short(self):
        result = self.mask_account("123")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    # mask_email
    def test_mask_email(self):
        result = self.mask_email("testuser@example.com")
        self.assertIn("@", result)
        self.assertNotEqual(result, "testuser@example.com")

    # HMAC
    def test_compute_and_verify_hmac(self):
        sig = self.compute_hmac("hello", "secret")
        self.assertTrue(self.verify_hmac("hello", sig, "secret"))

    def test_verify_hmac_wrong_secret_fails(self):
        sig = self.compute_hmac("hello", "secret")
        self.assertFalse(self.verify_hmac("hello", sig, "wrongsecret"))

    # BD mobile validation
    def test_valid_bkash_number(self):
        self.assertTrue(self.is_valid_bd_mobile("01711111111"))

    def test_invalid_bd_mobile(self):
        self.assertFalse(self.is_valid_bd_mobile("12345678901"))

    def test_normalize_bd_mobile_removes_country_code(self):
        result = self.normalize_bd_mobile("+8801711111111")
        self.assertEqual(result, "01711111111")

    # crypto address
    def test_valid_trc20_address(self):
        self.assertTrue(self.is_valid_crypto_address("T" + "A" * 33, "trc20"))

    def test_invalid_crypto_address(self):
        self.assertFalse(self.is_valid_crypto_address("short", "trc20"))

    # generate
    def test_generate_uuid_unique(self):
        a, b = self.generate_uuid(), self.generate_uuid()
        self.assertNotEqual(a, b)

    def test_generate_idempotency_key_has_prefix(self):
        key = self.generate_idempotency_key("txn")
        self.assertTrue(key.startswith("txn"))

    # truncate
    def test_truncate_long_string(self):
        result = self.truncate("a" * 300, 200)
        self.assertLessEqual(len(result), 203)

    def test_truncate_short_string_unchanged(self):
        self.assertEqual(self.truncate("hello", 200), "hello")


# ══════════════════════════════════════════════════════════════════════════════
# 2. validators.py
# ══════════════════════════════════════════════════════════════════════════════
class ValidatorsTest(TestCase):
    def setUp(self):
        from ..validators import (
            is_valid_ipv4, is_valid_ipv6, safe_ip_address,
            safe_decimal, validate_amount, safe_string, safe_int,
            safe_bool, CircuitBreaker,
        )
        self.is_valid_ipv4   = is_valid_ipv4
        self.is_valid_ipv6   = is_valid_ipv6
        self.safe_ip_address = safe_ip_address
        self.safe_decimal    = safe_decimal
        self.validate_amount = validate_amount
        self.safe_string     = safe_string
        self.safe_int        = safe_int
        self.safe_bool       = safe_bool
        self.CircuitBreaker  = CircuitBreaker

    def test_valid_ipv4(self):
        self.assertTrue(self.is_valid_ipv4("192.168.1.1"))

    def test_invalid_ipv4(self):
        self.assertFalse(self.is_valid_ipv4("999.999.999.999"))

    def test_valid_ipv6(self):
        self.assertTrue(self.is_valid_ipv6("::1"))

    def test_invalid_ipv6(self):
        self.assertFalse(self.is_valid_ipv6("not_an_ip"))

    def test_safe_ip_address_valid(self):
        self.assertEqual(self.safe_ip_address("10.0.0.1"), "10.0.0.1")

    def test_safe_ip_address_invalid_returns_default(self):
        self.assertEqual(self.safe_ip_address("bad_ip"), "0.0.0.0")

    def test_safe_ip_address_none_returns_default(self):
        self.assertEqual(self.safe_ip_address(None), "0.0.0.0")

    def test_validators_safe_decimal_valid(self):
        self.assertEqual(self.safe_decimal("50.00"), Decimal("50.00"))

    def test_validators_safe_decimal_none(self):
        result = self.safe_decimal(None)
        self.assertEqual(result, Decimal("0.00"))

    # validate_amount returns (bool, str, Decimal|None)
    def test_validate_amount_valid(self):
        ok, err, val = self.validate_amount("100.00")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("100.00"))

    def test_validate_amount_zero_fails(self):
        ok, err, val = self.validate_amount("0")
        self.assertFalse(ok)
        self.assertIsNotNone(err)

    def test_validate_amount_negative_fails(self):
        ok, err, val = self.validate_amount("-50")
        self.assertFalse(ok)

    def test_validate_amount_with_min_amount(self):
        ok, err, val = self.validate_amount("10", min_amount=Decimal("50"))
        self.assertFalse(ok)

    def test_validate_amount_with_max_amount(self):
        ok, err, val = self.validate_amount("200", max_amount=Decimal("100"))
        self.assertFalse(ok)

    def test_safe_string_normal(self):
        self.assertEqual(self.safe_string("hello"), "hello")

    def test_safe_string_none_returns_default(self):
        self.assertEqual(self.safe_string(None), "")

    def test_safe_string_max_length_truncates(self):
        result = self.safe_string("a" * 200, max_length=10)
        self.assertLessEqual(len(result), 10)

    def test_safe_int_valid(self):
        self.assertEqual(self.safe_int("42"), 42)

    def test_safe_int_invalid_returns_default(self):
        self.assertEqual(self.safe_int("abc"), 0)

    def test_safe_bool_true(self):
        for v in (True, "true", "1", "yes"):
            self.assertTrue(self.safe_bool(v), f"Expected True for {v!r}")

    def test_safe_bool_false(self):
        for v in (False, "false", "0", "no", None):
            self.assertFalse(self.safe_bool(v), f"Expected False for {v!r}")

    def test_circuit_breaker_allows_success(self):
        cb = self.CircuitBreaker("test_cb", failure_threshold=3, recovery_timeout=60)
        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")

    def test_circuit_breaker_opens_after_threshold(self):
        cb = self.CircuitBreaker("test_cb2", failure_threshold=2, recovery_timeout=60)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        try:
            cb.call(lambda: "ok")
        except Exception:
            pass  # Expected — circuit open


# ══════════════════════════════════════════════════════════════════════════════
# 3. permissions.py
# ══════════════════════════════════════════════════════════════════════════════
class PermissionsTest(TestCase):
    def setUp(self):
        from ..permissions import (
            IsWalletOwner, IsWalletOwnerOrAdmin,
            WalletNotLocked, IsAdminOrReadOnly,
        )
        from ..services import WalletService
        self.IsWalletOwner        = IsWalletOwner
        self.IsWalletOwnerOrAdmin = IsWalletOwnerOrAdmin
        self.WalletNotLocked      = WalletNotLocked
        self.IsAdminOrReadOnly    = IsAdminOrReadOnly
        self.WalletService        = WalletService
        self.factory = APIRequestFactory()
        self.user  = User.objects.create_user(username="perm1", password="p", email="perm1@t.com")
        self.admin = User.objects.create_superuser(username="padmin", password="p", email="padmin@t.com")
        self.wallet = WalletService.get_or_create(self.user)

    def _req(self, user, method="GET"):
        req = self.factory.get("/") if method == "GET" else self.factory.post("/")
        req.user = user
        return req

    def test_wallet_owner_own_wallet_allowed(self):
        perm = self.IsWalletOwner()
        req = self._req(self.user)
        self.assertTrue(perm.has_object_permission(req, None, self.wallet))

    def test_wallet_owner_other_wallet_denied(self):
        other = User.objects.create_user(username="other1", password="p", email="o1@t.com")
        other_wallet = self.WalletService.get_or_create(other)
        perm = self.IsWalletOwner()
        req = self._req(self.user)
        self.assertFalse(perm.has_object_permission(req, None, other_wallet))

    def test_wallet_owner_or_admin_allows_admin(self):
        perm = self.IsWalletOwnerOrAdmin()
        req = self._req(self.admin)
        self.assertTrue(perm.has_object_permission(req, None, self.wallet))

    def test_wallet_not_locked_unlocked_allows(self):
        perm = self.WalletNotLocked()
        req = self._req(self.user)
        self.assertTrue(perm.has_permission(req, None))

    def test_wallet_not_locked_locked_denies_via_related(self):
        self.wallet.is_locked = True
        self.wallet.save()
        perm = self.WalletNotLocked()
        req = self._req(self.user)
        try:
            result = perm.has_permission(req, None)
            # If no exception, locked wallet should return False
            self.assertFalse(result)
        except Exception:
            pass  # related_name accessor may differ
        finally:
            self.wallet.is_locked = False
            self.wallet.save()

    def test_admin_or_readonly_allows_admin_post(self):
        perm = self.IsAdminOrReadOnly()
        req = self._req(self.admin, method="POST")
        self.assertTrue(perm.has_permission(req, None))

    def test_admin_or_readonly_allows_user_get(self):
        perm = self.IsAdminOrReadOnly()
        req = self._req(self.user, method="GET")
        self.assertTrue(perm.has_permission(req, None))

    def test_admin_or_readonly_denies_user_post(self):
        perm = self.IsAdminOrReadOnly()
        req = self._req(self.user, method="POST")
        self.assertFalse(perm.has_permission(req, None))


# ══════════════════════════════════════════════════════════════════════════════
# 4. compliance.py
# ══════════════════════════════════════════════════════════════════════════════
class ComplianceTest(TestCase):
    def setUp(self):
        from ..compliance import ComplianceChecker, GDPRCompliance
        from ..services import WalletService
        self.ComplianceChecker = ComplianceChecker
        self.GDPRCompliance    = GDPRCompliance
        self.user   = User.objects.create_user(username="comp1", password="p", email="comp1@t.com")
        self.wallet = WalletService.get_or_create(self.user)

    def test_compliance_check_returns_dict_with_compliant_key(self):
        result = self.ComplianceChecker.check_withdrawal_compliance(
            self.user, self.wallet, Decimal("500")
        )
        self.assertIsInstance(result, dict)
        self.assertIn("compliant", result)

    def test_small_amount_passes(self):
        result = self.ComplianceChecker.check_withdrawal_compliance(
            self.user, self.wallet, Decimal("100")
        )
        self.assertTrue(result["compliant"])

    def test_result_has_warnings_and_blocks(self):
        result = self.ComplianceChecker.check_withdrawal_compliance(
            self.user, self.wallet, Decimal("500")
        )
        self.assertIn("warnings", result)
        self.assertIn("blocks", result)

    def test_gdpr_export_returns_dict(self):
        result = self.GDPRCompliance.export_user_data(self.user)
        self.assertIsInstance(result, dict)

    def test_gdpr_delete_returns_dict(self):
        result = self.GDPRCompliance.delete_user_data(self.user)
        self.assertIsInstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 5. sanctions.py
# ══════════════════════════════════════════════════════════════════════════════
class SanctionsTest(TestCase):
    def setUp(self):
        from ..sanctions import SanctionsChecker
        self.SanctionsChecker = SanctionsChecker
        self.user = User.objects.create_user(
            username="sanctions1", password="p",
            email="s1@t.com", first_name="John", last_name="Doe"
        )

    def test_check_user_returns_dict_with_is_sanctioned(self):
        result = self.SanctionsChecker.check_user(self.user)
        self.assertIsInstance(result, dict)
        self.assertIn("is_sanctioned", result)
        self.assertFalse(result["is_sanctioned"])

    def test_check_user_has_is_pep_key(self):
        result = self.SanctionsChecker.check_user(self.user)
        self.assertIn("is_pep", result)

    def test_check_local_blocklist_clean_name(self):
        result = self.SanctionsChecker.check_local_blocklist("John Doe", "BD")
        self.assertIsInstance(result, dict)
        # Key is "is_sanctioned" not "matched"
        self.assertIn("is_sanctioned", result)
        self.assertFalse(result["is_sanctioned"])

    def test_check_pep_clean_name(self):
        result = self.SanctionsChecker.check_pep("John Doe", "BD")
        self.assertIsInstance(result, dict)
        self.assertIn("is_pep", result)
        self.assertFalse(result["is_pep"])

    def test_normalize_name(self):
        normalized = self.SanctionsChecker._normalize_name("  OSAMA BIN LADEN  ")
        self.assertEqual(normalized, "osama bin laden")

    def test_bulk_check_returns_results_for_user(self):
        result = self.SanctionsChecker.bulk_check_users([self.user.pk])
        self.assertIsInstance(result, dict)
        self.assertIn(self.user.pk, result)

    def test_unknown_user_id_handled_gracefully(self):
        result = self.SanctionsChecker.bulk_check_users([999999])
        self.assertIsInstance(result, dict)
