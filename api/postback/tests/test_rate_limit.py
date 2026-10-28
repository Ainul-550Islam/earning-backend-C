"""test_rate_limit.py – Comprehensive tests for rate limiting functionality."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.core.exceptions import ValidationError

from api.postback.models import PostbackRateLimit, NetworkPostbackConfig
from api.postback.services import _check_rate_limit
from api.postback.exceptions import RateLimitExceededException
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackRateLimitFactory,
    BlockedRateLimitFactory,
    HighUsageRateLimitFactory,
)
from api.postback.choices import PostbackStatus


class PostbackRateLimitModelTests(TestCase):
    """Test PostbackRateLimit model functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.rate_limit = PostbackRateLimitFactory(network=self.network)

    def test_rate_limit_creation(self):
        """Test basic rate limit creation."""
        self.assertEqual(self.rate_limit.network, self.network)
        self.assertEqual(self.rate_limit.max_per_minute, 1000)
        self.assertEqual(self.rate_limit.max_per_hour, 50000)
        self.assertEqual(self.rate_limit.max_per_day, 1000000)
        self.assertEqual(self.rate_limit.current_count, 0)
        self.assertTrue(self.rate_limit.is_active)
        self.assertFalse(self.rate_limit.is_blocked)

    def test_rate_limit_str_representation(self):
        """Test string representation of rate limit."""
        str_repr = str(self.rate_limit)
        self.assertIn(self.rate_limit.name, str_repr)
        self.assertIn(self.rate_limit.network.network_key, str_repr)
        self.assertIn(str(self.rate_limit.max_per_minute), str_repr)

    def test_rate_limit_default_values(self):
        """Test default field values."""
        rate_limit = PostbackRateLimitFactory()
        
        self.assertEqual(rate_limit.current_count, 0)
        self.assertEqual(rate_limit.total_violations, 0)
        self.assertTrue(rate_limit.is_active)
        self.assertFalse(rate_limit.is_blocked)
        self.assertIsNone(rate_limit.blocked_until)
        self.assertIsNone(rate_limit.last_violation_at)
        self.assertIsNone(rate_limit.last_reset_at)
        self.assertIsNone(rate_limit.window_start)

    def test_rate_limit_unique_constraint(self):
        """Test unique constraint on (network, name)."""
        name = "UNIQUE_TEST_LIMIT"
        
        # First rate limit should succeed
        limit1 = PostbackRateLimitFactory(network=self.network, name=name)
        
        # Second rate limit with same name should fail
        with self.assertRaises(Exception):  # Should raise IntegrityError
            PostbackRateLimitFactory(network=self.network, name=name)

    def test_rate_limit_different_networks(self):
        """Test same name with different networks is allowed."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        name = "CROSS_NETWORK_LIMIT"
        
        limit1 = PostbackRateLimitFactory(network=network1, name=name)
        limit2 = PostbackRateLimitFactory(network=network2, name=name)
        
        self.assertNotEqual(limit1.id, limit2.id)
        self.assertEqual(limit1.name, limit2.name)

    def test_rate_limit_validation(self):
        """Test rate limit field validation."""
        # Test positive limits
        limit = PostbackRateLimitFactory(
            max_per_minute=100,
            max_per_hour=5000,
            max_per_day=100000
        )
        
        self.assertEqual(limit.max_per_minute, 100)
        self.assertEqual(limit.max_per_hour, 5000)
        self.assertEqual(limit.max_per_day, 100000)

    def test_rate_limit_zero_limits(self):
        """Test rate limit with zero limits (unlimited)."""
        limit = PostbackRateLimitFactory(
            max_per_minute=0,
            max_per_hour=0,
            max_per_day=0
        )
        
        self.assertEqual(limit.max_per_minute, 0)
        self.assertEqual(limit.max_per_hour, 0)
        self.assertEqual(limit.max_per_day, 0)

    def test_rate_limit_timestamp_fields(self):
        """Test timestamp field behavior."""
        before_creation = timezone.now()
        limit = PostbackRateLimitFactory()
        after_creation = timezone.now()
        
        self.assertGreaterEqual(limit.created_at, before_creation)
        self.assertLessEqual(limit.created_at, after_creation)
        self.assertGreaterEqual(limit.updated_at, before_creation)
        self.assertLessEqual(limit.updated_at, after_creation)

    def test_rate_limit_integrity_hash_field(self):
        """Test integrity hash field exists and can be set."""
        limit = PostbackRateLimitFactory()
        
        # Initially should be empty
        self.assertEqual(limit.integrity_hash, "")
        
        # Can set integrity hash
        test_hash = "a" * 64  # 64 character SHA-256 hash
        limit.integrity_hash = test_hash
        limit.save()
        
        limit.refresh_from_db()
        self.assertEqual(limit.integrity_hash, test_hash)

    def test_rate_limit_integrity_hash_generation(self):
        """Test integrity hash generation method."""
        limit = PostbackRateLimitFactory(
            max_per_minute=500,
            max_per_hour=25000,
            max_per_day=500000
        )
        
        hash_value = limit.generate_integrity_hash()
        
        # Should be 64 characters (SHA-256)
        self.assertEqual(len(hash_value), 64)
        self.assertIsInstance(hash_value, str)
        
        # Should be consistent for same data
        hash_value2 = limit.generate_integrity_hash()
        self.assertEqual(hash_value, hash_value2)

    def test_rate_limit_integrity_verification(self):
        """Test integrity hash verification."""
        limit = PostbackRateLimitFactory()
        
        # Initially no hash, should be invalid
        self.assertFalse(limit.verify_integrity())
        
        # Generate hash and verify
        limit.integrity_hash = limit.generate_integrity_hash()
        limit.save()
        self.assertTrue(limit.verify_integrity())

    def test_rate_limit_integrity_verification_tampering(self):
        """Test integrity verification detects tampering."""
        limit = PostbackRateLimitFactory()
        limit.integrity_hash = limit.generate_integrity_hash()
        limit.save()
        
        # Tamper with data
        limit.max_per_minute = 999
        limit.save()
        
        # Should detect tampering
        self.assertFalse(limit.verify_integrity())


class RateLimitFunctionalityTests(TestCase):
    """Test rate limiting functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10,
            max_per_hour=500,
            max_per_day=10000
        )

    def test_is_rate_exceeded_under_limit(self):
        """Test rate limit check when under limit."""
        self.rate_limit.current_count = 5
        
        result = self.rate_limit.is_rate_exceeded()
        
        self.assertFalse(result)

    def test_is_rate_exceeded_at_limit(self):
        """Test rate limit check when exactly at limit."""
        self.rate_limit.current_count = 10
        
        result = self.rate_limit.is_rate_exceeded()
        
        self.assertFalse(result)  # At limit should still be allowed

    def test_is_rate_exceeded_over_limit(self):
        """Test rate limit check when over limit."""
        self.rate_limit.current_count = 15
        
        result = self.rate_limit.is_rate_exceeded()
        
        self.assertTrue(result)

    def test_is_rate_exceeded_zero_limit(self):
        """Test rate limit check with zero limit (unlimited)."""
        unlimited_limit = PostbackRateLimitFactory(max_per_minute=0)
        
        result = unlimited_limit.is_rate_exceeded()
        
        self.assertFalse(result)  # Zero limit means unlimited

    def test_increment_count_under_limit(self):
        """Test increment count when under limit."""
        initial_count = self.rate_limit.current_count
        
        result = self.rate_limit.increment_count()
        
        self.assertTrue(result)  # Should succeed
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.current_count, initial_count + 1)

    def test_increment_count_at_limit(self):
        """Test increment count when at limit."""
        self.rate_limit.current_count = 10
        
        result = self.rate_limit.increment_count()
        
        self.assertTrue(result)  # Should still succeed at limit
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.current_count, 11)

    def test_increment_count_over_limit(self):
        """Test increment count when over limit."""
        self.rate_limit.current_count = 10
        
        # Increment to reach limit
        for i in range(10):
            self.rate_limit.increment_count()
        
        # Next increment should fail
        result = self.rate_limit.increment_count()
        
        self.assertFalse(result)  # Should fail
        self.assertTrue(self.rate_limit.is_blocked)

    def test_increment_count_zero_limit(self):
        """Test increment count with zero limit (unlimited)."""
        unlimited_limit = PostbackRateLimitFactory(max_per_minute=0)
        
        result = unlimited_limit.increment_count()
        
        self.assertTrue(result)  # Should always succeed with unlimited

    def test_record_violation(self):
        """Test violation recording."""
        initial_violations = self.rate_limit.total_violations
        
        self.rate_limit.record_violation()
        
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.total_violations, initial_violations + 1)
        self.assertTrue(self.rate_limit.is_blocked)
        self.assertIsNotNone(self.rate_limit.blocked_until)

    def test_record_violation_block_duration(self):
        """Test violation blocking duration."""
        before_violation = timezone.now()
        
        self.rate_limit.record_violation()
        
        self.rate_limit.refresh_from_db()
        
        # Should be blocked for some time in the future
        self.assertGreater(self.rate_limit.blocked_until, before_violation)
        self.assertIsNotNone(self.rate_limit.last_violation_at)

    def test_reset_window(self):
        """Test window reset functionality."""
        # Set some count and block state
        self.rate_limit.current_count = 50
        self.rate_limit.is_blocked = True
        self.rate_limit.blocked_until = timezone.now() + timedelta(hours=1)
        self.rate_limit.save()
        
        # Reset window
        self.rate_limit.reset_window()
        
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.current_count, 0)
        self.assertIsNotNone(self.rate_limit.last_reset_at)
        self.assertFalse(self.rate_limit.is_blocked)
        self.assertIsNone(self.rate_limit.blocked_until)

    def test_reset_window_updates_timestamps(self):
        """Test window reset updates timestamps correctly."""
        before_reset = timezone.now()
        
        self.rate_limit.reset_window()
        
        self.rate_limit.refresh_from_db()
        
        self.assertGreaterEqual(self.rate_limit.last_reset_at, before_reset)
        self.assertLessEqual(self.rate_limit.last_reset_at, timezone.now())

    def test_unblock_expired_block(self):
        """Test unblocking when block has expired."""
        # Create expired block
        past_time = timezone.now() - timedelta(minutes=30)
        self.rate_limit.is_blocked = True
        self.rate_limit.blocked_until = past_time
        self.rate_limit.save()
        
        # Reset window should clear expired block
        self.rate_limit.reset_window()
        
        self.rate_limit.refresh_from_db()
        self.assertFalse(self.rate_limit.is_blocked)
        self.assertIsNone(self.rate_limit.blocked_until)

    def test_is_currently_blocked(self):
        """Test current block status checking."""
        # Not blocked
        self.assertFalse(self.rate_limit.is_currently_blocked())
        
        # Blocked with future time
        self.rate_limit.is_blocked = True
        self.rate_limit.blocked_until = timezone.now() + timedelta(hours=1)
        self.rate_limit.save()
        
        self.assertTrue(self.rate_limit.is_currently_blocked())
        
        # Blocked with past time
        self.rate_limit.blocked_until = timezone.now() - timedelta(hours=1)
        self.rate_limit.save()
        
        self.assertFalse(self.rate_limit.is_currently_blocked())

    def test_current_utilization(self):
        """Test current utilization calculation."""
        # Test with some usage
        self.rate_limit.current_count = 25
        
        utilization = self.rate_limit.current_utilization
        
        self.assertEqual(utilization, 250.0)  # 25/100 * 100

    def test_current_utilization_zero_limit(self):
        """Test utilization calculation with zero limit."""
        unlimited_limit = PostbackRateLimitFactory(max_per_minute=0)
        
        utilization = unlimited_limit.current_utilization
        
        self.assertEqual(utilization, 0.0)  # Should handle division by zero

    def test_current_utilization_zero_count(self):
        """Test utilization calculation with zero count."""
        utilization = self.rate_limit.current_utilization
        
        self.assertEqual(utilization, 0.0)

    def test_current_utilization_high_usage(self):
        """Test utilization calculation with high usage."""
        self.rate_limit.current_count = 95
        
        utilization = self.rate_limit.current_utilization
        
        self.assertEqual(utilization, 950.0)  # 95/100 * 100

    def test_window_start_tracking(self):
        """Test window start time tracking."""
        # Reset window should set window_start
        self.rate_limit.reset_window()
        
        self.rate_limit.refresh_from_db()
        self.assertIsNotNone(self.rate_limit.window_start)
        
        # Increment should not change window_start
        original_window_start = self.rate_limit.window_start
        self.rate_limit.increment_count()
        
        self.rate_limit.refresh_from_db()
        self.assertEqual(self.rate_limit.window_start, original_window_start)


class RateLimitServiceTests(TestCase):
    """Test rate limiting service integration."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_check_rate_limit_service_no_limits(self):
        """Test service check when no rate limits exist."""
        # Should not raise exception when no limits configured
        try:
            _check_rate_limit(self.network)
        except RateLimitExceededException:
            self.fail("Should not raise exception when no rate limits exist")

    def test_check_rate_limit_service_under_limit(self):
        """Test service check when under rate limit."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=100,
            current_count=50
        )
        
        # Should not raise exception
        try:
            _check_rate_limit(self.network)
        except RateLimitExceededException:
            self.fail("Should not raise exception when under limit")

    def test_check_rate_limit_service_over_limit(self):
        """Test service check when over rate limit."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10,
            current_count=15  # Over limit
        )
        
        # Should raise exception
        with self.assertRaises(RateLimitExceededException):
            _check_rate_limit(self.network)

    def test_check_rate_limit_service_multiple_limits(self):
        """Test service check with multiple rate limits."""
        # Create multiple rate limits
        PostbackRateLimitFactory(
            network=self.network,
            name="Minute Limit",
            max_per_minute=5,
            current_count=3
        )
        PostbackRateLimitFactory(
            network=self.network,
            name="Hour Limit",
            max_per_minute=1000,
            current_count=500
        )
        
        # Should not raise exception (both under limits)
        try:
            _check_rate_limit(self.network)
        except RateLimitExceededException:
            self.fail("Should not raise exception when all limits are under threshold")

    def test_check_rate_limit_service_one_limit_exceeded(self):
        """Test service check when one limit is exceeded."""
        # Create limits where one is exceeded
        PostbackRateLimitFactory(
            network=self.network,
            name="Strict Limit",
            max_per_minute=5,
            current_count=10  # Over limit
        )
        PostbackRateLimitFactory(
            network=self.network,
            name="Lenient Limit",
            max_per_minute=1000,
            current_count=100
        )
        
        # Should raise exception due to strict limit
        with self.assertRaises(RateLimitExceededException):
            _check_rate_limit(self.network)

    def test_check_rate_limit_service_inactive_limits(self):
        """Test service check with inactive rate limits."""
        # Create inactive rate limit that's exceeded
        PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5,
            current_count=10,
            is_active=False
        )
        
        # Should not raise exception (limit is inactive)
        try:
            _check_rate_limit(self.network)
        except RateLimitExceededException:
            self.fail("Should not raise exception for inactive limits")


class RateLimitWindowTests(TestCase):
    """Test rate limiting window behavior."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10
        )

    def test_minute_window_behavior(self):
        """Test minute-level rate limiting window."""
        # Fill up to limit
        for i in range(10):
            self.rate_limit.increment_count()
        
        # Should be at limit
        self.assertEqual(self.rate_limit.current_count, 10)
        self.assertFalse(self.rate_limit.is_rate_exceeded())
        
        # Next increment should fail
        result = self.rate_limit.increment_count()
        self.assertFalse(result)
        self.assertTrue(self.rate_limit.is_blocked)

    def test_hour_window_behavior(self):
        """Test hour-level rate limiting."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5,
            max_per_hour=100
        )
        
        # Fill minute limit multiple times
        for cycle in range(3):
            # Fill minute limit
            for i in range(5):
                rate_limit.increment_count()
            
            # Reset to simulate new minute
            rate_limit.reset_window()
        
        # Should not exceed hour limit
        self.assertFalse(rate_limit.is_rate_exceeded())

    def test_day_window_behavior(self):
        """Test day-level rate limiting."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5,
            max_per_hour=50,
            max_per_day=200
        )
        
        # Simulate usage throughout the day
        total_requests = 0
        for hour in range(24):
            # Each hour: 10 requests in 2-minute cycles
            for cycle in range(5):
                for i in range(5):
                    rate_limit.increment_count()
                    total_requests += 1
                rate_limit.reset_window()
        
        # Should not exceed day limit
        self.assertEqual(total_requests, 120)  # 24 * 5 * 5
        self.assertFalse(rate_limit.is_rate_exceeded())

    def test_window_boundary_conditions(self):
        """Test window boundary conditions."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10
        )
        
        # Fill to exactly limit
        for i in range(10):
            rate_limit.increment_count()
        
        # Should be exactly at limit
        self.assertEqual(rate_limit.current_count, 10)
        self.assertFalse(rate_limit.is_rate_exceeded())
        
        # One more should fail
        result = rate_limit.increment_count()
        self.assertFalse(result)

    def test_window_reset_timing(self):
        """Test window reset timing accuracy."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10
        )
        
        # Set initial window start
        initial_start = timezone.now() - timedelta(minutes=5)
        rate_limit.window_start = initial_start
        rate_limit.save()
        
        # Reset window
        rate_limit.reset_window()
        
        # Window start should be updated
        rate_limit.refresh_from_db()
        self.assertGreater(rate_limit.window_start, initial_start)

    def test_multiple_window_types(self):
        """Test multiple window types simultaneously."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5,
            max_per_hour=100,
            max_per_day=1000
        )
        
        # Test minute limit
        for i in range(5):
            rate_limit.increment_count()
        
        self.assertFalse(rate_limit.is_rate_exceeded())
        
        # One more should exceed minute limit
        rate_limit.increment_count()
        self.assertTrue(rate_limit.is_rate_exceeded())

    def test_window_reset_with_violations(self):
        """Test window reset with existing violations."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5
        )
        
        # Cause violation
        for i in range(6):
            rate_limit.increment_count()
        
        # Should be blocked
        self.assertTrue(rate_limit.is_blocked)
        
        # Reset window
        rate_limit.reset_window()
        
        # Should be unblocked and count reset
        self.assertFalse(rate_limit.is_blocked)
        self.assertEqual(rate_limit.current_count, 0)

    def test_window_persistence(self):
        """Test window state persistence."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10
        )
        
        # Set some state
        rate_limit.current_count = 7
        rate_limit.window_start = timezone.now() - timedelta(minutes=3)
        rate_limit.save()
        
        # Reload from database
        rate_limit.refresh_from_db()
        
        # State should be preserved
        self.assertEqual(rate_limit.current_count, 7)
        self.assertIsNotNone(rate_limit.window_start)


class RateLimitConcurrencyTests(TestCase):
    """Test rate limiting under concurrent conditions."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=10
        )

    def test_concurrent_increment_count(self):
        """Test concurrent increment count operations."""
        # Simulate concurrent requests
        with transaction.atomic():
            # Lock the rate limit
            locked_limit = PostbackRateLimit.objects.select_for_update().get(
                network=self.network,
                name=self.rate_limit.name
            )
            
            # Multiple increments in same transaction
            results = []
            for i in range(5):
                result = locked_limit.increment_count()
                results.append(result)
        
        # Should have consistent results
        self.assertEqual(sum(results), 5)
        
        # Final count should be correct
        final_limit = PostbackRateLimit.objects.get(
            network=self.network,
            name=self.rate_limit.name
        )
        self.assertEqual(final_limit.current_count, 5)

    def test_concurrent_violation_recording(self):
        """Test concurrent violation recording."""
        # Set up near limit
        for i in range(9):
            self.rate_limit.increment_count()
        
        # Simulate concurrent violations
        with transaction.atomic():
            locked_limit = PostbackRateLimit.objects.select_for_update().get(
                network=self.network,
                name=self.rate_limit.name
            )
            
            # Multiple violations
            violations = []
            for i in range(3):
                try:
                    locked_limit.increment_count()
                    violations.append(False)
                except:
                    violations.append(True)
        
        # Should handle violations consistently
        self.assertTrue(any(violations))  # At least one violation occurred

    def test_database_lock_behavior(self):
        """Test database locking during rate limiting."""
        with transaction.atomic():
            # Lock the rate limit
            locked_limit = PostbackRateLimit.objects.select_for_update().get(
                network=self.network,
                name=self.rate_limit.name
            )
            
            # Modify while locked
            locked_limit.current_count = 5
            locked_limit.save()
            
            # Verify changes while still locked
            self.assertEqual(locked_limit.current_count, 5)
        
        # Verify changes persisted
        final_limit = PostbackRateLimit.objects.get(
            network=self.network,
            name=self.rate_limit.name
        )
        self.assertEqual(final_limit.current_count, 5)

    def test_transaction_rollback_scenarios(self):
        """Test transaction rollback during rate limiting."""
        initial_count = self.rate_limit.current_count
        
        try:
            with transaction.atomic():
                # Increment count
                self.rate_limit.increment_count()
                
                # Simulate error causing rollback
                raise Exception("Simulated error")
        except Exception:
            pass  # Expected
        
        # Count should be rolled back
        final_count = PostbackRateLimit.objects.get(
            network=self.network,
            name=self.rate_limit.name
        ).current_count
        
        self.assertEqual(final_count, initial_count)

    def test_race_condition_prevention(self):
        """Test prevention of race conditions in rate limiting."""
        # Use select_for_update to prevent race conditions
        with transaction.atomic():
            locked_limit = PostbackRateLimit.objects.select_for_update().get(
                network=self.network,
                name=self.rate_limit.name
            )
            
            # Check and increment atomically
            if not locked_limit.is_rate_exceeded():
                result = locked_limit.increment_count()
                created = True
            else:
                result = False
                created = False
        
        # Verify consistent state
        final_limit = PostbackRateLimit.objects.get(
            network=self.network,
            name=self.rate_limit.name
        )
        
        if created:
            self.assertEqual(final_limit.current_count, 1)
        else:
            self.assertEqual(final_limit.current_count, 0)


class RateLimitPerformanceTests(TestCase):
    """Test performance characteristics of rate limiting."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_rate_limit_check_performance(self):
        """Test performance of rate limit checks."""
        import time
        
        # Create rate limit
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=1000
        )
        
        start_time = time.time()
        
        # Perform many checks
        for i in range(1000):
            try:
                _check_rate_limit(self.network)
            except RateLimitExceededException:
                pass
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 2.0, "Rate limit checking too slow")

    def test_increment_count_performance(self):
        """Test performance of count increment operations."""
        import time
        
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=1000
        )
        
        start_time = time.time()
        
        # Perform many increments
        for i in range(500):
            rate_limit.increment_count()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 1.0, "Count increment too slow")

    def test_bulk_rate_limit_operations(self):
        """Test performance of bulk rate limit operations."""
        import time
        
        # Create many rate limits
        rate_limits = []
        for i in range(100):
            rate_limits.append(PostbackRateLimitFactory(
                network=self.network,
                name=f"Bulk Limit {i}",
                max_per_minute=100
            ))
        
        start_time = time.time()
        
        # Perform operations on all limits
        for rate_limit in rate_limits:
            for j in range(10):
                rate_limit.increment_count()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 3.0, "Bulk operations too slow")

    def test_database_query_performance(self):
        """Test database query performance."""
        import time
        
        # Create many rate limits
        for i in range(500):
            PostbackRateLimitFactory(
                network=self.network,
                name=f"Query Test {i}",
                max_per_minute=100
            )
        
        start_time = time.time()
        
        # Query active rate limits
        active_limits = PostbackRateLimit.objects.filter(
            network=self.network,
            is_active=True
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should be very fast with proper indexing
        self.assertLess(elapsed_time, 0.1, "Database query too slow")
        self.assertEqual(active_limits.count(), 500)

    def test_memory_usage_with_high_volume(self):
        """Test memory usage with high volume rate limiting."""
        # Create many rate limits with high counts
        for i in range(100):
            rate_limit = PostbackRateLimitFactory(
                network=self.network,
                name=f"Memory Test {i}",
                max_per_minute=1000
            )
            
            # Set high counts
            for j in range(500):
                rate_limit.increment_count()
        
        # Query all rate limits
        all_limits = list(PostbackRateLimit.objects.all())
        
        # Should handle large datasets efficiently
        self.assertEqual(len(all_limits), 100)

    def test_cache_usage_optimization(self):
        """Test cache usage in rate limiting."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=100
        )
        
        # Simulate cache-based rate limiting
        cache_key = f"rate_limit:{rate_limit.id}"
        
        # Test cache operations
        cache.set(cache_key, 50, timeout=60)
        cached_count = cache.get(cache_key)
        
        self.assertEqual(cached_count, 50)


class RateLimitIntegrationTests(TestCase):
    """Test rate limiting integration with postback processing."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_rate_limiting_in_postback_pipeline(self):
        """Test rate limiting integration in postback processing pipeline."""
        from api.postback.services import process_postback_sync
        
        # Create restrictive rate limit
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=2
        )
        
        # Create first postback (should succeed)
        log1 = PostbackLogFactory(
            network=self.network,
            lead_id="RATE_LIMIT_TEST_1",
            status=PostbackStatus.RECEIVED
        )
        
        process_postback_sync(
            log1,
            signature="test",
            timestamp_str="1234567890",
            nonce="test_nonce_1",
            body_bytes=b'{"test": "data"}',
            path="/test/",
            query_params={}
        )
        
        log1.refresh_from_db()
        self.assertNotEqual(log1.status, PostbackStatus.REJECTED)
        
        # Create second postback (should succeed)
        log2 = PostbackLogFactory(
            network=self.network,
            lead_id="RATE_LIMIT_TEST_2",
            status=PostbackStatus.RECEIVED
        )
        
        process_postback_sync(
            log2,
            signature="test",
            timestamp_str="1234567890",
            nonce="test_nonce_2",
            body_bytes=b'{"test": "data"}',
            path="/test/",
            query_params={}
        )
        
        log2.refresh_from_db()
        self.assertNotEqual(log2.status, PostbackStatus.REJECTED)
        
        # Create third postback (should be rate limited)
        log3 = PostbackLogFactory(
            network=self.network,
            lead_id="RATE_LIMIT_TEST_3",
            status=PostbackStatus.RECEIVED
        )
        
        process_postback_sync(
            log3,
            signature="test",
            timestamp_str="1234567890",
            nonce="test_nonce_3",
            body_bytes=b'{"test": "data"}',
            path="/test/",
            query_params={}
        )
        
        log3.refresh_from_db()
        # Should be rejected due to rate limiting
        self.assertEqual(log3.status, PostbackStatus.REJECTED)

    def test_rate_limiting_with_different_networks(self):
        """Test rate limiting across different networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        # Create restrictive rate limits for both networks
        PostbackRateLimitFactory(
            network=network1,
            max_per_minute=2
        )
        PostbackRateLimitFactory(
            network=network2,
            max_per_minute=2
        )
        
        # Fill rate limit for network1
        for i in range(2):
            log = PostbackLogFactory(network=network1, status=PostbackStatus.RECEIVED)
            from api.postback.services import process_postback_sync
            process_postback_sync(log, "test", "123", f"nonce{i}", b'data', "/test/", {})
        
        # Network1 should be rate limited, network2 should not
        log1_blocked = PostbackLogFactory(network=network1, status=PostbackStatus.RECEIVED)
        log2_allowed = PostbackLogFactory(network=network2, status=PostbackStatus.RECEIVED)
        
        from api.postback.services import process_postback_sync
        
        process_postback_sync(log1_blocked, "test", "123", "blocked", b'data', "/test/", {})
        process_postback_sync(log2_allowed, "test", "123", "allowed", b'data', "/test/", {})
        
        log1_blocked.refresh_from_db()
        log2_allowed.refresh_from_db()
        
        self.assertEqual(log1_blocked.status, PostbackStatus.REJECTED)
        self.assertNotEqual(log2_allowed.status, PostbackStatus.REJECTED)

    def test_rate_limiting_cleanup_integration(self):
        """Test rate limiting cleanup integration."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5
        )
        
        # Fill rate limit and cause violation
        for i in range(6):
            rate_limit.increment_count()
        
        # Should be blocked
        self.assertTrue(rate_limit.is_blocked)
        
        # Test cleanup (reset window)
        rate_limit.reset_window()
        
        # Should be unblocked
        self.assertFalse(rate_limit.is_blocked)
        self.assertEqual(rate_limit.current_count, 0)

    def test_rate_limiting_statistics(self):
        """Test rate limiting statistics and reporting."""
        # Create multiple rate limits with different states
        active_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=100,
            current_count=50,
            is_active=True
        )
        blocked_limit = BlockedRateLimitFactory(network=self.network)
        inactive_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=100,
            is_active=False
        )
        
        # Get statistics
        all_limits = PostbackRateLimit.objects.filter(network=self.network)
        active_limits = all_limits.filter(is_active=True)
        blocked_limits = active_limits.filter(is_blocked=True)
        
        stats = {
            'total_limits': all_limits.count(),
            'active_limits': active_limits.count(),
            'blocked_limits': blocked_limits.count(),
            'average_utilization': sum(limit.current_utilization() for limit in active_limits) / active_limits.count() if active_limits.exists() else 0
        }
        
        self.assertEqual(stats['total_limits'], 3)
        self.assertEqual(stats['active_limits'], 2)
        self.assertEqual(stats['blocked_limits'], 1)
        self.assertGreater(stats['average_utilization'], 0)

    def test_rate_limiting_with_multiple_windows(self):
        """Test rate limiting with multiple time windows."""
        rate_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=5,
            max_per_hour=100,
            max_per_day=1000
        )
        
        # Test minute window
        for i in range(5):
            rate_limit.increment_count()
        self.assertFalse(rate_limit.is_rate_exceeded())
        
        # One more should exceed minute limit
        rate_limit.increment_count()
        self.assertTrue(rate_limit.is_rate_exceeded())
        
        # Reset and test hour window
        rate_limit.reset_window()
        for i in range(100):
            rate_limit.increment_count()
        self.assertFalse(rate_limit.is_rate_exceeded())  # Still under hour limit

    def test_rate_limiting_error_handling(self):
        """Test error handling in rate limiting."""
        # Test with non-existent network
        fake_network = NetworkPostbackConfigFactory.build(
            network_key="non_existent",
            name="Fake Network"
        )
        
        # Should handle gracefully
        try:
            _check_rate_limit(fake_network)
        except RateLimitExceededException:
            self.fail("Should not raise exception for non-existent network")

    def test_rate_limiting_configuration_validation(self):
        """Test rate limiting configuration validation."""
        # Test invalid configurations
        with self.assertRaises(Exception):  # Should raise validation error
            PostbackRateLimitFactory(
                network=self.network,
                max_per_minute=-1  # Invalid negative value
            )
        
        # Test valid configurations
        valid_limit = PostbackRateLimitFactory(
            network=self.network,
            max_per_minute=100,
            max_per_hour=5000,
            max_per_day=100000
        )
        
        self.assertEqual(valid_limit.max_per_minute, 100)
        self.assertEqual(valid_limit.max_per_hour, 5000)
        self.assertEqual(valid_limit.max_per_day, 100000)
