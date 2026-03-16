"""test_validators.py – Tests for postback validation utilities."""
import hashlib
import hmac
import time
from decimal import Decimal
from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase

from postback.exceptions import (
    InvalidSignatureException,
    IPNotWhitelistedException,
    NonceReusedException,
    SignatureExpiredException,
)
from postback.utils.ip_checker import (
    get_client_ip,
    is_ip_in_whitelist,
    is_private_ip,
    validate_ip_whitelist_entries,
)
from postback.utils.signature_validator import (
    build_canonical_string,
    compute_signature,
    validate_and_consume_nonce,
    validate_full_request,
    validate_timestamp,
    verify_signature,
)
from postback.validators import (
    validate_field_mapping,
    validate_ip_whitelist,
    validate_payout_not_exceeds_cap,
    validate_required_postback_fields,
)


class IPCheckerTests(TestCase):

    def test_exact_ip_in_whitelist(self):
        self.assertTrue(is_ip_in_whitelist("1.2.3.4", ["1.2.3.4", "5.6.7.8"]))

    def test_ip_not_in_whitelist(self):
        self.assertFalse(is_ip_in_whitelist("9.9.9.9", ["1.2.3.4"]))

    def test_cidr_match(self):
        self.assertTrue(is_ip_in_whitelist("192.168.1.50", ["192.168.1.0/24"]))

    def test_cidr_no_match(self):
        self.assertFalse(is_ip_in_whitelist("10.0.0.1", ["192.168.1.0/24"]))

    def test_empty_whitelist_returns_false(self):
        self.assertFalse(is_ip_in_whitelist("1.2.3.4", []))

    def test_unparseable_ip_returns_false(self):
        self.assertFalse(is_ip_in_whitelist("not-an-ip", ["1.2.3.4"]))

    def test_private_ip_detection(self):
        self.assertTrue(is_private_ip("192.168.1.1"))
        self.assertTrue(is_private_ip("10.0.0.1"))
        self.assertTrue(is_private_ip("127.0.0.1"))
        self.assertFalse(is_private_ip("8.8.8.8"))

    def test_ipv6_in_whitelist(self):
        self.assertTrue(is_ip_in_whitelist("::1", ["::1"]))

    def test_validate_whitelist_entries_valid(self):
        errors = validate_ip_whitelist_entries(["1.2.3.4", "10.0.0.0/8", "::1"])
        self.assertEqual(errors, [])

    def test_validate_whitelist_entries_invalid(self):
        errors = validate_ip_whitelist_entries(["not-an-ip", "999.999.999.999"])
        self.assertEqual(len(errors), 2)

    def test_get_client_ip_from_remote_addr(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="5.5.5.5")
        self.assertEqual(get_client_ip(request, trust_forwarded=False), "5.5.5.5")

    def test_get_client_ip_ignores_xff_when_not_trusted(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get(
            "/",
            REMOTE_ADDR="5.5.5.5",
            HTTP_X_FORWARDED_FOR="6.6.6.6",
        )
        self.assertEqual(get_client_ip(request, trust_forwarded=False), "5.5.5.5")

    def test_get_client_ip_uses_xff_when_trusted(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get(
            "/",
            REMOTE_ADDR="10.0.0.1",
            HTTP_X_FORWARDED_FOR="8.8.8.8, 10.0.0.1",
        )
        self.assertEqual(get_client_ip(request, trust_forwarded=True), "8.8.8.8")


class SignatureValidatorTests(TestCase):

    def setUp(self):
        cache.clear()

    def _make_signature(self, secret, method, path, query, body, ts, nonce):
        canonical = build_canonical_string(
            method=method, path=path, query_params=query,
            body=body, timestamp=ts, nonce=nonce,
        )
        return compute_signature(secret, canonical, algorithm="hmac_sha256")

    def test_verify_signature_valid(self):
        secret = "super-secret-key"
        now = str(int(time.time()))
        body = b'{"lead_id":"L1"}'
        canonical = build_canonical_string(
            "POST", "/api/postback/", {}, body, now, "nonce-abc"
        )
        sig = compute_signature(secret, canonical)
        self.assertTrue(verify_signature(
            provided_signature=sig,
            secret=secret,
            canonical_bytes=canonical,
            algorithm="hmac_sha256",
        ))

    def test_verify_signature_invalid(self):
        canonical = build_canonical_string("POST", "/", {}, b"", "123", "n1")
        self.assertFalse(verify_signature(
            provided_signature="deadbeef",
            secret="secret",
            canonical_bytes=canonical,
            algorithm="hmac_sha256",
        ))

    def test_validate_timestamp_within_tolerance(self):
        ts = str(int(time.time()))
        validate_timestamp(ts)  # should not raise

    def test_validate_timestamp_too_old_raises(self):
        old_ts = str(int(time.time()) - 400)
        with self.assertRaises(SignatureExpiredException):
            validate_timestamp(old_ts, tolerance=300)

    def test_validate_timestamp_future_raises(self):
        future_ts = str(int(time.time()) + 400)
        with self.assertRaises(SignatureExpiredException):
            validate_timestamp(future_ts, tolerance=300)

    def test_validate_timestamp_non_integer_raises(self):
        with self.assertRaises(InvalidSignatureException):
            validate_timestamp("not-a-number")

    def test_nonce_consumed_on_first_use(self):
        validate_and_consume_nonce("my-nonce-1", "network-1")  # should succeed

    def test_nonce_reuse_raises(self):
        validate_and_consume_nonce("my-nonce-2", "network-1")
        with self.assertRaises(NonceReusedException):
            validate_and_consume_nonce("my-nonce-2", "network-1")

    def test_nonce_reuse_allowed_across_networks(self):
        validate_and_consume_nonce("my-nonce-3", "network-A")
        validate_and_consume_nonce("my-nonce-3", "network-B")  # different network – ok

    def test_empty_nonce_raises(self):
        with self.assertRaises(InvalidSignatureException):
            validate_and_consume_nonce("", "network-1")

    def test_nonce_too_long_raises(self):
        long_nonce = "x" * 65
        with self.assertRaises(InvalidSignatureException):
            validate_and_consume_nonce(long_nonce, "network-1")

    def test_validate_full_request_success(self):
        secret = "test-secret"
        now = str(int(time.time()))
        nonce = "full-req-nonce-1"
        body = b'{"a":"b"}'
        canonical = build_canonical_string("POST", "/test/", {}, body, now, nonce)
        sig = compute_signature(secret, canonical)
        validate_full_request(
            provided_signature=sig,
            secret=secret,
            network_id="net-1",
            algorithm="hmac_sha256",
            timestamp_str=now,
            nonce=nonce,
            method="POST",
            path="/test/",
            query_params={},
            body=body,
        )  # Should not raise

    def test_validate_full_request_bad_sig_raises(self):
        now = str(int(time.time()))
        with self.assertRaises(InvalidSignatureException):
            validate_full_request(
                provided_signature="badsig",
                secret="secret",
                network_id="net-2",
                algorithm="hmac_sha256",
                timestamp_str=now,
                nonce="nonce-bad-sig",
                method="POST",
                path="/test/",
                query_params={},
                body=b"",
            )


class PostbackValidatorTests(TestCase):

    def test_required_fields_all_present(self):
        payload = {"lead_id": "L1", "offer_id": "O1"}
        missing = validate_required_postback_fields(payload, ["lead_id", "offer_id"])
        self.assertEqual(missing, [])

    def test_required_fields_some_missing(self):
        payload = {"lead_id": "L1"}
        missing = validate_required_postback_fields(payload, ["lead_id", "offer_id"])
        self.assertIn("offer_id", missing)

    def test_required_fields_empty_string_counts_as_missing(self):
        payload = {"lead_id": "   "}
        missing = validate_required_postback_fields(payload, ["lead_id"])
        self.assertIn("lead_id", missing)

    def test_payout_cap_within_limit(self):
        validate_payout_not_exceeds_cap(100.0)  # Should not raise

    def test_payout_cap_exceeded_raises(self):
        from django.core.exceptions import ValidationError
        from postback.constants import MAX_PAYOUT_PER_POSTBACK
        with self.assertRaises(ValidationError):
            validate_payout_not_exceeds_cap(MAX_PAYOUT_PER_POSTBACK + 1)

    def test_validate_ip_whitelist_valid(self):
        validate_ip_whitelist(["1.2.3.4", "10.0.0.0/8"])  # no raise

    def test_validate_ip_whitelist_not_a_list_raises(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_ip_whitelist("1.2.3.4")

    def test_validate_field_mapping_valid(self):
        validate_field_mapping({"lead_id": "click_id", "offer_id": "campaign"})  # no raise

    def test_validate_field_mapping_non_dict_raises(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_field_mapping(["not", "a", "dict"])

    def test_validate_field_mapping_blank_value_raises(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_field_mapping({"lead_id": "  "})
