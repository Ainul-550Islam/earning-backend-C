"""test_signature_validator.py – Comprehensive tests for signature validation utilities."""
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from api.postback.utils.signature_validator import (
    validate_full_request,
    generate_signature,
    verify_timestamp,
    validate_nonce,
    build_canonical_string,
    is_timestamp_valid,
    is_nonce_unique,
    extract_signature_components,
    SignatureValidationError,
    TimestampExpiredError,
    NonceReuseError,
    InvalidSignatureError,
)
from api.postback.tests.factories import NetworkPostbackConfigFactory
from api.postback.choices import SignatureAlgorithm


class SignatureValidatorCoreTests(TestCase):
    """Test core signature validation functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            secret_key="test_secret_key_12345",
            signature_algorithm=SignatureAlgorithm.HMAC_SHA256
        )
        self.test_payload = b'{"lead_id": "123", "offer_id": "456"}'
        self.test_path = "/api/postback/receive/test-network/"
        self.test_timestamp = str(int(time.time()))
        self.test_nonce = "unique_nonce_12345"

    def test_generate_signature_hmac_sha256(self):
        """Test HMAC SHA256 signature generation."""
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 hex length
        
        # Verify signature is deterministic
        signature2 = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        self.assertEqual(signature, signature2)

    def test_generate_signature_hmac_sha1(self):
        """Test HMAC SHA1 signature generation."""
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA1
        )
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 40)  # SHA1 hex length

    def test_generate_signature_none_algorithm(self):
        """Test signature generation with NONE algorithm."""
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.NONE
        )
        
        self.assertEqual(signature, "")

    def test_build_canonical_string_basic(self):
        """Test basic canonical string building."""
        canonical = build_canonical_string(
            self.test_path,
            "POST",
            self.test_payload,
            self.test_timestamp,
            self.test_nonce,
            {}
        )
        
        self.assertIsInstance(canonical, str)
        self.assertIn(self.test_path, canonical)
        self.assertIn("POST", canonical)
        self.assertIn(self.test_timestamp, canonical)
        self.assertIn(self.test_nonce, canonical)

    def test_build_canonical_string_with_query_params(self):
        """Test canonical string building with query parameters."""
        query_params = {"param1": "value1", "param2": "value2"}
        canonical = build_canonical_string(
            self.test_path,
            "POST",
            self.test_payload,
            self.test_timestamp,
            self.test_nonce,
            query_params
        )
        
        self.assertIn("param1=value1", canonical)
        self.assertIn("param2=value2", canonical)

    def test_build_canonical_string_sorted_query_params(self):
        """Test canonical string with sorted query parameters."""
        query_params = {"z_param": "z", "a_param": "a", "m_param": "m"}
        canonical = build_canonical_string(
            self.test_path,
            "POST",
            self.test_payload,
            self.test_timestamp,
            self.test_nonce,
            query_params
        )
        
        # Parameters should be sorted alphabetically
        params_start = canonical.find("a_param=a")
        z_param_start = canonical.find("z_param=z")
        self.assertLess(params_start, z_param_start)

    def test_build_canonical_string_empty_payload(self):
        """Test canonical string with empty payload."""
        canonical = build_canonical_string(
            self.test_path,
            "GET",
            b"",
            self.test_timestamp,
            self.test_nonce,
            {}
        )
        
        self.assertIn("GET", canonical)
        self.assertIn(self.test_path, canonical)

    def test_verify_timestamp_valid(self):
        """Test timestamp verification with valid timestamp."""
        current_time = int(time.time())
        valid_timestamp = str(current_time - 30)  # 30 seconds ago
        
        result = verify_timestamp(valid_timestamp, tolerance_seconds=60)
        self.assertTrue(result)

    def test_verify_timestamp_expired(self):
        """Test timestamp verification with expired timestamp."""
        expired_timestamp = str(int(time.time()) - 120)  # 2 minutes ago
        
        with self.assertRaises(TimestampExpiredError):
            verify_timestamp(expired_timestamp, tolerance_seconds=60)

    def test_verify_timestamp_future(self):
        """Test timestamp verification with future timestamp."""
        future_timestamp = str(int(time.time()) + 300)  # 5 minutes in future
        
        with self.assertRaises(TimestampExpiredError):
            verify_timestamp(future_timestamp, tolerance_seconds=60)

    def test_verify_timestamp_invalid_format(self):
        """Test timestamp verification with invalid format."""
        with self.assertRaises(SignatureValidationError):
            verify_timestamp("invalid_timestamp")

    def test_verify_timestamp_edge_cases(self):
        """Test timestamp verification edge cases."""
        current_time = int(time.time())
        
        # Exactly at tolerance limit
        edge_timestamp = str(current_time - 60)
        result = verify_timestamp(edge_timestamp, tolerance_seconds=60)
        self.assertTrue(result)
        
        # Just beyond tolerance limit
        beyond_timestamp = str(current_time - 61)
        with self.assertRaises(TimestampExpiredError):
            verify_timestamp(beyond_timestamp, tolerance_seconds=60)

    def test_validate_nonce_unique(self):
        """Test nonce validation with unique nonce."""
        nonce = "unique_test_nonce_12345"
        
        # First use should be valid
        result = validate_nonce(nonce, cache_timeout=300)
        self.assertTrue(result)
        
        # Second use should fail
        with self.assertRaises(NonceReuseError):
            validate_nonce(nonce, cache_timeout=300)

    def test_validate_nonce_cache_timeout(self):
        """Test nonce cache timeout functionality."""
        nonce = "timeout_test_nonce"
        
        # Use nonce
        validate_nonce(nonce, cache_timeout=1)
        
        # Wait for cache to expire (simulated)
        cache.delete(f"postback_nonce:{nonce}")
        
        # Should be valid again after cache expiry
        result = validate_nonce(nonce, cache_timeout=1)
        self.assertTrue(result)

    def test_validate_nonce_empty_nonce(self):
        """Test nonce validation with empty nonce."""
        # Empty nonce should be valid (no caching)
        result = validate_nonce("")
        self.assertTrue(result)
        
        # Multiple empty nonces should be valid
        result = validate_nonce("")
        self.assertTrue(result)

    def test_is_timestamp_valid_helper(self):
        """Test timestamp validation helper function."""
        current_time = int(time.time())
        
        # Valid timestamp
        self.assertTrue(is_timestamp_valid(str(current_time - 30), 60))
        
        # Invalid timestamp
        self.assertFalse(is_timestamp_valid(str(current_time - 120), 60))

    def test_is_nonce_unique_helper(self):
        """Test nonce uniqueness helper function."""
        nonce = "helper_test_nonce"
        
        # First use
        self.assertTrue(is_nonce_unique(nonce))
        
        # Second use
        self.assertFalse(is_nonce_unique(nonce))

    def test_extract_signature_components(self):
        """Test signature component extraction."""
        headers = {
            "X-Signature": "test_signature",
            "X-Timestamp": "1234567890",
            "X-Nonce": "test_nonce"
        }
        
        signature, timestamp, nonce = extract_signature_components(headers)
        
        self.assertEqual(signature, "test_signature")
        self.assertEqual(timestamp, "1234567890")
        self.assertEqual(nonce, "test_nonce")

    def test_extract_signature_components_missing_headers(self):
        """Test signature component extraction with missing headers."""
        headers = {"X-Signature": "test_signature"}  # Missing timestamp and nonce
        
        with self.assertRaises(SignatureValidationError):
            extract_signature_components(headers)

    def test_validate_full_request_success(self):
        """Test full request validation success."""
        # Generate valid signature
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=self.test_timestamp,
            nonce=self.test_nonce,
            body_bytes=self.test_payload,
            path=self.test_path,
            query_params={}
        )
        
        self.assertTrue(result)

    def test_validate_full_request_invalid_signature(self):
        """Test full request validation with invalid signature."""
        invalid_signature = "invalid_signature_hash"
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=self.network,
                signature=invalid_signature,
                timestamp_str=self.test_timestamp,
                nonce=self.test_nonce,
                body_bytes=self.test_payload,
                path=self.test_path,
                query_params={}
            )

    def test_validate_full_request_expired_timestamp(self):
        """Test full request validation with expired timestamp."""
        expired_timestamp = str(int(time.time()) - 120)
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        with self.assertRaises(TimestampExpiredError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=expired_timestamp,
                nonce=self.test_nonce,
                body_bytes=self.test_payload,
                path=self.test_path,
                query_params={}
            )

    def test_validate_full_request_reused_nonce(self):
        """Test full request validation with reused nonce."""
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # First validation (should succeed)
        validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=self.test_timestamp,
            nonce=self.test_nonce,
            body_bytes=self.test_payload,
            path=self.test_path,
            query_params={}
        )
        
        # Second validation with same nonce (should fail)
        with self.assertRaises(NonceReuseError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=self.test_timestamp,
                nonce=self.test_nonce,
                body_bytes=self.test_payload,
                path=self.test_path,
                query_params={}
            )

    def test_validate_full_request_none_algorithm(self):
        """Test full request validation with NONE algorithm."""
        network_none = NetworkPostbackConfigFactory(
            signature_algorithm=SignatureAlgorithm.NONE,
            require_nonce=False
        )
        
        result = validate_full_request(
            network=network_none,
            signature="",
            timestamp_str="",
            nonce="",
            body_bytes=self.test_payload,
            path=self.test_path,
            query_params={}
        )
        
        self.assertTrue(result)

    def test_validate_full_request_with_query_params(self):
        """Test full request validation with query parameters."""
        query_params = {"param1": "value1", "param2": "value2"}
        signature = generate_signature(
            self.network.secret_key,
            self.test_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=self.test_timestamp,
            nonce=self.test_nonce,
            body_bytes=self.test_payload,
            path=self.test_path,
            query_params=query_params
        )
        
        self.assertTrue(result)


class SignatureValidatorEdgeCasesTests(TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            secret_key="edge_case_secret_key",
            signature_algorithm=SignatureAlgorithm.HMAC_SHA256
        )

    def test_unicode_payload_handling(self):
        """Test signature validation with Unicode payload."""
        unicode_payload = '{"lead_id": "测试_123", "offer": "предложение"}'.encode('utf-8')
        signature = generate_signature(
            self.network.secret_key,
            unicode_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="unicode_test",
            body_bytes=unicode_payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_large_payload_handling(self):
        """Test signature validation with large payload."""
        large_payload = '{"data": "' + "x" * 10000 + '"}'.encode('utf-8')
        signature = generate_signature(
            self.network.secret_key,
            large_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="large_payload_test",
            body_bytes=large_payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_empty_payload_handling(self):
        """Test signature validation with empty payload."""
        empty_payload = b""
        signature = generate_signature(
            self.network.secret_key,
            empty_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="empty_payload_test",
            body_bytes=empty_payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_special_characters_in_path(self):
        """Test signature validation with special characters in path."""
        special_path = "/api/postback/receive/test-network?param=value&other=测试"
        payload = b'{"test": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="special_path_test",
            body_bytes=payload,
            path=special_path,
            query_params={}
        )
        
        self.assertTrue(result)

    def test_query_params_with_special_characters(self):
        """Test signature validation with special characters in query params."""
        query_params = {
            "param1": "value with spaces",
            "param2": "测试中文",
            "param3": "special&chars=here"
        }
        payload = b'{"test": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="special_query_test",
            body_bytes=payload,
            path="/test/",
            query_params=query_params
        )
        
        self.assertTrue(result)

    def test_very_long_nonce(self):
        """Test signature validation with very long nonce."""
        long_nonce = "a" * 1000  # 1000 character nonce
        payload = b'{"test": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce=long_nonce,
            body_bytes=payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_timestamp_boundary_values(self):
        """Test timestamp validation at boundary values."""
        current_time = int(time.time())
        payload = b'{"test": "data"}'
        
        # Test exactly at tolerance boundary
        boundary_timestamp = str(current_time - 60)
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=boundary_timestamp,
            nonce="boundary_test",
            body_bytes=payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_concurrent_nonce_validation(self):
        """Test concurrent nonce validation scenarios."""
        payload = b'{"test": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Simulate concurrent requests with same nonce
        nonce = "concurrent_test_nonce"
        
        # First request should succeed
        result1 = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce=nonce,
            body_bytes=payload,
            path="/test/",
            query_params={}
        )
        self.assertTrue(result1)
        
        # Second request should fail
        with self.assertRaises(NonceReuseError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=str(int(time.time())),
                nonce=nonce,
                body_bytes=payload,
                path="/test/",
                query_params={}
            )

    def test_cache_failure_scenarios(self):
        """Test behavior when cache fails."""
        payload = b'{"test": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Mock cache to simulate failure
        with patch('api.postback.utils.signature_validator.cache') as mock_cache:
            mock_cache.get.side_effect = Exception("Cache failure")
            mock_cache.set.side_effect = Exception("Cache failure")
            
            # Should still work but may not properly validate nonce
            with self.assertRaises(Exception):
                validate_full_request(
                    network=self.network,
                    signature=signature,
                    timestamp_str=str(int(time.time())),
                    nonce="cache_failure_test",
                    body_bytes=payload,
                    path="/test/",
                    query_params={}
                )

    def test_different_secret_key_formats(self):
        """Test signature validation with different secret key formats."""
        payload = b'{"test": "data"}'
        
        # Test with numeric secret
        numeric_secret = "12345678901234567890"
        network_numeric = NetworkPostbackConfigFactory(
            secret_key=numeric_secret,
            signature_algorithm=SignatureAlgorithm.HMAC_SHA256
        )
        
        signature = generate_signature(
            numeric_secret,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        result = validate_full_request(
            network=network_numeric,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="numeric_secret_test",
            body_bytes=payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)

    def test_algorithm_switching_consistency(self):
        """Test signature consistency when switching algorithms."""
        payload = b'{"test": "data"}'
        
        # Generate SHA256 signature
        sha256_signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Try to validate with SHA1 network (should fail)
        network_sha1 = NetworkPostbackConfigFactory(
            secret_key=self.network.secret_key,
            signature_algorithm=SignatureAlgorithm.HMAC_SHA1
        )
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=network_sha1,
                signature=sha256_signature,
                timestamp_str=str(int(time.time())),
                nonce="algorithm_switch_test",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )


class SignatureValidatorPerformanceTests(TestCase):
    """Test performance characteristics of signature validation."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            secret_key="performance_test_secret",
            signature_algorithm=SignatureAlgorithm.HMAC_SHA256
        )

    def test_signature_generation_performance(self):
        """Test signature generation performance with large payload."""
        import time
        
        large_payload = b'{"data": "' + "x" * 50000 + '"}'  # 50KB payload
        
        start_time = time.time()
        
        # Generate 100 signatures
        for i in range(100):
            generate_signature(
                self.network.secret_key,
                large_payload,
                SignatureAlgorithm.HMAC_SHA256
            )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        self.assertLess(elapsed_time, 5.0, "Signature generation too slow")

    def test_validation_performance(self):
        """Test validation performance with high volume."""
        import time
        
        payload = b'{"test": "performance data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        start_time = time.time()
        
        # Validate 1000 requests
        for i in range(1000):
            try:
                validate_full_request(
                    network=self.network,
                    signature=signature,
                    timestamp_str=str(int(time.time())),
                    nonce=f"perf_test_{i}",
                    body_bytes=payload,
                    path="/test/",
                    query_params={}
                )
            except NonceReuseError:
                pass  # Expected for repeated nonces
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 10.0, "Validation too slow")

    def test_memory_usage_with_large_payloads(self):
        """Test memory usage with large payloads."""
        import sys
        
        # Create very large payload
        large_payload = b'{"data": "' + "x" * 100000 + '"}'  # 100KB payload
        
        # Generate signature
        signature = generate_signature(
            self.network.secret_key,
            large_payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Validate (should not cause memory issues)
        result = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="memory_test",
            body_bytes=large_payload,
            path="/test/",
            query_params={}
        )
        
        self.assertTrue(result)


class SignatureValidatorSecurityTests(TestCase):
    """Test security aspects of signature validation."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            secret_key="security_test_secret",
            signature_algorithm=SignatureAlgorithm.HMAC_SHA256
        )

    def test_signature_tampering_detection(self):
        """Test detection of signature tampering."""
        payload = b'{"original": "data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Tamper with payload
        tampered_payload = b'{"tampered": "data"}'
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=str(int(time.time())),
                nonce="tamper_test",
                body_bytes=tampered_payload,
                path="/test/",
                query_params={}
            )

    def test_path_tampering_detection(self):
        """Test detection of path tampering."""
        payload = b'{"test": "data"}'
        original_path = "/api/postback/receive/test/"
        tampered_path = "/api/postback/receive/other/"
        
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=str(int(time.time())),
                nonce="path_tamper_test",
                body_bytes=payload,
                path=tampered_path,
                query_params={}
            )

    def test_query_param_tampering_detection(self):
        """Test detection of query parameter tampering."""
        payload = b'{"test": "data"}'
        original_params = {"param1": "value1"}
        tampered_params = {"param1": "different_value"}
        
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=str(int(time.time())),
                nonce="query_tamper_test",
                body_bytes=payload,
                path="/test/",
                query_params=tampered_params
            )

    def test_replay_attack_prevention(self):
        """Test prevention of replay attacks."""
        payload = b'{"test": "replay_data"}'
        signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # First request should succeed
        result1 = validate_full_request(
            network=self.network,
            signature=signature,
            timestamp_str=str(int(time.time())),
            nonce="replay_test_nonce",
            body_bytes=payload,
            path="/test/",
            query_params={}
        )
        self.assertTrue(result1)
        
        # Second request with same nonce should fail
        with self.assertRaises(NonceReuseError):
            validate_full_request(
                network=self.network,
                signature=signature,
                timestamp_str=str(int(time.time())),
                nonce="replay_test_nonce",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )

    def test_timing_attack_resistance(self):
        """Test resistance to timing attacks."""
        payload = b'{"test": "timing_data"}'
        valid_signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        invalid_signature = "invalid_signature_hash"
        
        import time
        
        # Time valid signature validation
        start_time = time.time()
        try:
            validate_full_request(
                network=self.network,
                signature=valid_signature,
                timestamp_str=str(int(time.time())),
                nonce="timing_test_1",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )
        except:
            pass
        valid_time = time.time() - start_time
        
        # Time invalid signature validation
        start_time = time.time()
        try:
            validate_full_request(
                network=self.network,
                signature=invalid_signature,
                timestamp_str=str(int(time.time())),
                nonce="timing_test_2",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )
        except:
            pass
        invalid_time = time.time() - start_time
        
        # Timing should be similar (within reasonable tolerance)
        time_diff = abs(valid_time - invalid_time)
        self.assertLess(time_diff, 0.1, "Timing difference suggests potential timing vulnerability")

    def test_secret_key_exposure_prevention(self):
        """Test that secret key is not exposed in error messages."""
        payload = b'{"test": "data"}'
        invalid_signature = "wrong_signature"
        
        try:
            validate_full_request(
                network=self.network,
                signature=invalid_signature,
                timestamp_str=str(int(time.time())),
                nonce="secret_test",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )
        except InvalidSignatureError as e:
            # Error message should not contain secret key
            error_str = str(e)
            self.assertNotIn(self.network.secret_key, error_str)

    def test_brute_force_resistance(self):
        """Test resistance to brute force attacks."""
        payload = b'{"test": "brute_force_data"}'
        correct_signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Simulate brute force attempts
        attempts = 0
        max_attempts = 1000
        
        for i in range(max_attempts):
            fake_signature = f"fake_signature_{i}".ljust(64, '0')
            try:
                validate_full_request(
                    network=self.network,
                    signature=fake_signature,
                    timestamp_str=str(int(time.time())),
                    nonce=f"brute_force_{i}",
                    body_bytes=payload,
                    path="/test/",
                    query_params={}
                )
                attempts += 1
            except InvalidSignatureError:
                continue
        
        # Should not succeed with brute force
        self.assertEqual(attempts, 0, "Brute force should not succeed")

    def test_collision_resistance(self):
        """Test collision resistance of signature algorithm."""
        payload1 = b'{"data": "collision_test_1"}'
        payload2 = b'{"data": "collision_test_2"}'
        
        signature1 = generate_signature(
            self.network.secret_key,
            payload1,
            SignatureAlgorithm.HMAC_SHA256
        )
        signature2 = generate_signature(
            self.network.secret_key,
            payload2,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Different payloads should produce different signatures
        self.assertNotEqual(signature1, signature2)

    def test_algorithm_confusion_attack(self):
        """Test resistance to algorithm confusion attacks."""
        payload = b'{"test": "algorithm_confusion"}'
        
        # Generate SHA256 signature
        sha256_signature = generate_signature(
            self.network.secret_key,
            payload,
            SignatureAlgorithm.HMAC_SHA256
        )
        
        # Try to validate with network expecting different algorithm
        network_sha1 = NetworkPostbackConfigFactory(
            secret_key=self.network.secret_key,
            signature_algorithm=SignatureAlgorithm.HMAC_SHA1
        )
        
        with self.assertRaises(InvalidSignatureError):
            validate_full_request(
                network=network_sha1,
                signature=sha256_signature,
                timestamp_str=str(int(time.time())),
                nonce="algorithm_confusion_test",
                body_bytes=payload,
                path="/test/",
                query_params={}
            )
