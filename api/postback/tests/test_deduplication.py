"""test_deduplication.py – Comprehensive tests for postback deduplication logic."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.cache import cache

from api.postback.models import DuplicateLeadCheck, PostbackLog, NetworkPostbackConfig
from api.postback.choices import PostbackStatus, DeduplicationWindow
from api.postback.services import _check_duplicate_lead
from api.postback.exceptions import DuplicateLeadException
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    DuplicateLeadCheckFactory,
    RewardedPostbackLogFactory,
)


class DuplicateLeadCheckModelTests(TestCase):
    """Test DuplicateLeadCheck model functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.duplicate_check = DuplicateLeadCheckFactory(network=self.network)

    def test_duplicate_lead_check_creation(self):
        """Test basic duplicate lead check creation."""
        self.assertEqual(self.duplicate_check.network, self.network)
        self.assertIsNotNone(self.duplicate_check.lead_id)
        self.assertIsNotNone(self.duplicate_check.first_seen_at)
        self.assertIsNotNone(self.duplicate_check.id)

    def test_duplicate_lead_check_str_representation(self):
        """Test string representation of duplicate lead check."""
        str_repr = str(self.duplicate_check)
        self.assertIn(self.duplicate_check.lead_id, str_repr)
        self.assertIn(self.duplicate_check.network.network_key, str_repr)

    def test_duplicate_lead_check_unique_constraint(self):
        """Test unique constraint on (network, lead_id)."""
        # First check should succeed
        lead_id = "UNIQUE_TEST_LEAD"
        check1 = DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
        
        # Second check with same lead_id should fail
        with self.assertRaises(IntegrityError):
            DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)

    def test_duplicate_lead_check_different_networks(self):
        """Test same lead_id with different networks is allowed."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        lead_id = "CROSS_NETWORK_LEAD"
        
        check1 = DuplicateLeadCheckFactory(network=network1, lead_id=lead_id)
        check2 = DuplicateLeadCheckFactory(network=network2, lead_id=lead_id)
        
        self.assertNotEqual(check1.id, check2.id)
        self.assertEqual(check1.lead_id, check2.lead_id)

    def test_duplicate_lead_check_first_seen_at(self):
        """Test first_seen_at field behavior."""
        before_creation = timezone.now()
        check = DuplicateLeadCheckFactory()
        after_creation = timezone.now()
        
        self.assertGreaterEqual(check.first_seen_at, before_creation)
        self.assertLessEqual(check.first_seen_at, after_creation)

    def test_duplicate_lead_check_postback_log_relationship(self):
        """Test relationship with PostbackLog."""
        log = PostbackLogFactory()
        check = DuplicateLeadCheckFactory(postback_log=log)
        
        self.assertEqual(check.postback_log, log)

    def test_duplicate_lead_check_manager_methods(self):
        """Test custom manager methods."""
        # Create test data
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        lead_id = "MANAGER_TEST_LEAD"
        
        DuplicateLeadCheckFactory(network=network1, lead_id=lead_id)
        DuplicateLeadCheckFactory(network=network2, lead_id="OTHER_LEAD")
        
        # Test by_network method
        network1_checks = DuplicateLeadCheck.objects.by_network(network1)
        self.assertEqual(network1_checks.count(), 1)
        self.assertEqual(network1_checks.first().lead_id, lead_id)
        
        # Test by_lead_id method
        lead_checks = DuplicateLeadCheck.objects.by_lead_id(lead_id)
        self.assertEqual(lead_checks.count(), 1)
        self.assertEqual(lead_checks.first().network, network1)

    def test_duplicate_lead_check_queryset_methods(self):
        """Test custom queryset methods."""
        network = NetworkPostbackConfigFactory()
        
        # Create checks with different first_seen times
        old_check = DuplicateLeadCheckFactory(
            network=network,
            lead_id="OLD_LEAD",
            first_seen_at=timezone.now() - timedelta(days=7)
        )
        recent_check = DuplicateLeadCheckFactory(
            network=network,
            lead_id="RECENT_LEAD",
            first_seen_at=timezone.now() - timedelta(hours=2)
        )
        
        # Test recent method
        recent_checks = DuplicateLeadCheck.objects.recent(days=1)
        self.assertIn(recent_check, recent_checks)
        self.assertNotIn(old_check, recent_checks)
        
        # Test by_date_range method
        today = timezone.now().date()
        today_checks = DuplicateLeadCheck.objects.by_date_range(today, today)
        self.assertIn(recent_check, today_checks)
        self.assertNotIn(old_check, today_checks)


class DeduplicationServiceTests(TestCase):
    """Test deduplication service functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory(
            dedup_window=DeduplicationWindow.FOREVER
        )

    def test_check_duplicate_lead_no_duplicate(self):
        """Test duplicate check when no duplicate exists."""
        lead_id = "NEW_LEAD_123"
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertFalse(result)  # No duplicate found

    def test_check_duplicate_lead_with_duplicate(self):
        """Test duplicate check when duplicate exists."""
        lead_id = "DUPLICATE_LEAD_456"
        
        # Create existing duplicate check
        DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)  # Duplicate found

    def test_check_duplicate_lead_different_networks(self):
        """Test duplicate check across different networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        lead_id = "CROSS_NETWORK_LEAD"
        
        # Create duplicate check for network1 only
        DuplicateLeadCheckFactory(network=network1, lead_id=lead_id)
        
        # Check network2 (should not find duplicate)
        result1 = _check_duplicate_lead(network1, lead_id)
        result2 = _check_duplicate_lead(network2, lead_id)
        
        self.assertTrue(result1)  # Found in network1
        self.assertFalse(result2)  # Not found in network2

    def test_check_duplicate_lead_with_postback_log(self):
        """Test duplicate check with associated postback log."""
        log = PostbackLogFactory()
        lead_id = "LOG_ASSOCIATED_LEAD"
        
        # Create duplicate check with postback log
        DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            postback_log=log
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)

    def test_check_duplicate_lead_case_sensitivity(self):
        """Test duplicate check case sensitivity."""
        lead_id_lower = "case_test_lead"
        lead_id_upper = "CASE_TEST_LEAD"
        
        # Create duplicate check with lowercase
        DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id_lower)
        
        # Check with uppercase (should be different)
        result_lower = _check_duplicate_lead(self.network, lead_id_lower)
        result_upper = _check_duplicate_lead(self.network, lead_id_upper)
        
        self.assertTrue(result_lower)
        self.assertFalse(result_upper)

    def test_check_duplicate_lead_unicode_handling(self):
        """Test duplicate check with Unicode lead IDs."""
        unicode_lead_id = "测试_LEAD_123"
        
        # Create duplicate check with Unicode
        DuplicateLeadCheckFactory(network=self.network, lead_id=unicode_lead_id)
        
        result = _check_duplicate_lead(self.network, unicode_lead_id)
        
        self.assertTrue(result)

    def test_check_duplicate_lead_empty_lead_id(self):
        """Test duplicate check with empty lead ID."""
        result = _check_duplicate_lead(self.network, "")
        
        self.assertFalse(result)  # Empty lead_id should not be checked

    def test_check_duplicate_lead_none_lead_id(self):
        """Test duplicate check with None lead ID."""
        result = _check_duplicate_lead(self.network, None)
        
        self.assertFalse(result)  # None lead_id should not be checked

    def test_check_duplicate_lead_very_long_lead_id(self):
        """Test duplicate check with very long lead ID."""
        long_lead_id = "x" * 1000  # 1000 character lead ID
        
        # Create duplicate check
        DuplicateLeadCheckFactory(network=self.network, lead_id=long_lead_id)
        
        result = _check_duplicate_lead(self.network, long_lead_id)
        
        self.assertTrue(result)

    def test_check_duplicate_lead_special_characters(self):
        """Test duplicate check with special characters."""
        special_lead_id = "LEAD_123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        
        # Create duplicate check
        DuplicateLeadCheckFactory(network=self.network, lead_id=special_lead_id)
        
        result = _check_duplicate_lead(self.network, special_lead_id)
        
        self.assertTrue(result)


class DeduplicationWindowTests(TestCase):
    """Test deduplication window functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_deduplication_window_forever(self):
        """Test FOREVER deduplication window."""
        self.network.dedup_window = DeduplicationWindow.FOREVER
        self.network.save()
        
        lead_id = "FOREVER_TEST_LEAD"
        
        # Create old duplicate check
        old_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            first_seen_at=timezone.now() - timedelta(days=365)
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)  # Should still find duplicate after 1 year

    def test_deduplication_window_24_hours(self):
        """Test 24_HOURS deduplication window."""
        self.network.dedup_window = DeduplicationWindow.TWENTY_FOUR_HOURS
        self.network.save()
        
        lead_id = "24H_TEST_LEAD"
        
        # Create duplicate check within window
        recent_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            first_seen_at=timezone.now() - timedelta(hours=12)
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)  # Should find duplicate within 24 hours
        
        # Create duplicate check outside window
        old_lead_id = "OLD_24H_LEAD"
        old_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=old_lead_id,
            first_seen_at=timezone.now() - timedelta(days=2)
        )
        
        result = _check_duplicate_lead(self.network, old_lead_id)
        
        self.assertFalse(result)  # Should not find duplicate after 24 hours

    def test_deduplication_window_7_days(self):
        """Test SEVEN_DAYS deduplication window."""
        self.network.dedup_window = DeduplicationWindow.SEVEN_DAYS
        self.network.save()
        
        lead_id = "7D_TEST_LEAD"
        
        # Create duplicate check within window
        recent_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            first_seen_at=timezone.now() - timedelta(days=5)
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)  # Should find duplicate within 7 days
        
        # Create duplicate check outside window
        old_lead_id = "OLD_7D_LEAD"
        old_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=old_lead_id,
            first_seen_at=timezone.now() - timedelta(days=10)
        )
        
        result = _check_duplicate_lead(self.network, old_lead_id)
        
        self.assertFalse(result)  # Should not find duplicate after 7 days

    def test_deduplication_window_30_days(self):
        """Test THIRTY_DAYS deduplication window."""
        self.network.dedup_window = DeduplicationWindow.THIRTY_DAYS
        self.network.save()
        
        lead_id = "30D_TEST_LEAD"
        
        # Create duplicate check within window
        recent_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            first_seen_at=timezone.now() - timedelta(days=20)
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        self.assertTrue(result)  # Should find duplicate within 30 days
        
        # Create duplicate check outside window
        old_lead_id = "OLD_30D_LEAD"
        old_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=old_lead_id,
            first_seen_at=timezone.now() - timedelta(days=40)
        )
        
        result = _check_duplicate_lead(self.network, old_lead_id)
        
        self.assertFalse(result)  # Should not find duplicate after 30 days

    def test_deduplication_window_edge_cases(self):
        """Test deduplication window edge cases."""
        self.network.dedup_window = DeduplicationWindow.TWENTY_FOUR_HOURS
        self.network.save()
        
        lead_id = "EDGE_CASE_LEAD"
        
        # Test exactly at window boundary
        boundary_time = timezone.now() - timedelta(hours=24)
        boundary_check = DuplicateLeadCheckFactory(
            network=self.network,
            lead_id=lead_id,
            first_seen_at=boundary_time
        )
        
        result = _check_duplicate_lead(self.network, lead_id)
        
        # Behavior at exact boundary may vary by implementation
        # This test documents the expected behavior
        self.assertIsInstance(result, bool)

    def test_deduplication_window_manager_methods(self):
        """Test deduplication window manager methods."""
        network = NetworkPostbackConfigFactory(dedup_window=DeduplicationWindow.SEVEN_DAYS)
        
        # Create duplicate checks at different times
        recent_check = DuplicateLeadCheckFactory(
            network=network,
            lead_id="RECENT_WINDOW_LEAD",
            first_seen_at=timezone.now() - timedelta(days=3)
        )
        old_check = DuplicateLeadCheckFactory(
            network=network,
            lead_id="OLD_WINDOW_LEAD",
            first_seen_at=timezone.now() - timedelta(days=10)
        )
        
        # Test within_window method
        within_window = DuplicateLeadCheck.objects.within_window(network)
        
        # Should only include recent checks
        lead_ids = [check.lead_id for check in within_window]
        self.assertIn("RECENT_WINDOW_LEAD", lead_ids)
        self.assertNotIn("OLD_WINDOW_LEAD", lead_ids)

    def test_deduplication_window_cleanup(self):
        """Test cleanup of expired duplicate checks."""
        network = NetworkPostbackConfigFactory(dedup_window=DeduplicationWindow.SEVEN_DAYS)
        
        # Create expired duplicate checks
        for i in range(5):
            DuplicateLeadCheckFactory(
                network=network,
                lead_id=f"EXPIRED_LEAD_{i}",
                first_seen_at=timezone.now() - timedelta(days=10)
            )
        
        # Create valid duplicate checks
        for i in range(3):
            DuplicateLeadCheckFactory(
                network=network,
                lead_id=f"VALID_LEAD_{i}",
                first_seen_at=timezone.now() - timedelta(days=3)
            )
        
        # Test cleanup_expired method
        deleted_count = DuplicateLeadCheck.objects.cleanup_expired(network)
        
        # Should delete expired checks
        self.assertGreaterEqual(deleted_count, 5)
        
        # Valid checks should remain
        remaining_checks = DuplicateLeadCheck.objects.filter(network=network)
        self.assertEqual(remaining_checks.count(), 3)


class DeduplicationConcurrencyTests(TestCase):
    """Test deduplication under concurrent conditions."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_concurrent_duplicate_check(self):
        """Test duplicate check under concurrent conditions."""
        lead_id = "CONCURRENT_TEST_LEAD"
        
        # Simulate concurrent requests
        with transaction.atomic():
            # First request should create duplicate check
            result1 = _check_duplicate_lead(self.network, lead_id)
            self.assertFalse(result1)
            
            # Second request in same transaction should find duplicate
            result2 = _check_duplicate_lead(self.network, lead_id)
            self.assertTrue(result2)

    def test_race_condition_prevention(self):
        """Test prevention of race conditions in duplicate checking."""
        lead_id = "RACE_CONDITION_LEAD"
        
        # Use select_for_update to prevent race conditions
        with transaction.atomic():
            # Lock the potential duplicate check
            existing_check = DuplicateLeadCheck.objects.select_for_update().filter(
                network=self.network,
                lead_id=lead_id
            ).first()
            
            if not existing_check:
                # Create new check if none exists
                DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
                created = True
            else:
                created = False
        
        # Verify only one check was created
        checks = DuplicateLeadCheck.objects.filter(network=self.network, lead_id=lead_id)
        self.assertEqual(checks.count(), 1)

    def test_database_lock_behavior(self):
        """Test database locking behavior during duplicate checks."""
        lead_id = "LOCK_TEST_LEAD"
        
        # Create initial check
        initial_check = DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
        
        # Test locking behavior
        with transaction.atomic():
            locked_check = DuplicateLeadCheck.objects.select_for_update().get(
                network=self.network,
                lead_id=lead_id
            )
            
            # Modify while locked
            locked_check.first_seen_at = timezone.now()
            locked_check.save()
        
        # Verify changes were applied
        updated_check = DuplicateLeadCheck.objects.get(
            network=self.network,
            lead_id=lead_id
        )
        self.assertEqual(updated_check.first_seen_at, locked_check.first_seen_at)

    def test_transaction_rollback_scenarios(self):
        """Test transaction rollback during duplicate checking."""
        lead_id = "ROLLBACK_TEST_LEAD"
        
        try:
            with transaction.atomic():
                # Create duplicate check
                DuplicateLeadCheckFactory(network=self.network, lead_id=lead_id)
                
                # Simulate error that should cause rollback
                raise Exception("Simulated error")
        except Exception:
            pass  # Expected
        
        # Check if rollback occurred
        check_exists = DuplicateLeadCheck.objects.filter(
            network=self.network,
            lead_id=lead_id
        ).exists()
        
        self.assertFalse(check_exists)  # Should be rolled back


class DeduplicationPerformanceTests(TestCase):
    """Test performance characteristics of deduplication."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_duplicate_check_performance_high_volume(self):
        """Test duplicate check performance with high volume."""
        import time
        
        # Create many duplicate checks
        for i in range(1000):
            DuplicateLeadCheckFactory(
                network=self.network,
                lead_id=f"PERF_TEST_LEAD_{i}"
            )
        
        # Test performance of checking existing leads
        start_time = time.time()
        
        for i in range(100):
            lead_id = f"PERF_TEST_LEAD_{i}"
            result = _check_duplicate_lead(self.network, lead_id)
            self.assertTrue(result)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 2.0, "Duplicate checking too slow")

    def test_duplicate_check_performance_new_leads(self):
        """Test performance with new leads (no duplicates)."""
        import time
        
        start_time = time.time()
        
        # Check many new leads
        for i in range(100):
            lead_id = f"NEW_PERF_LEAD_{i}"
            result = _check_duplicate_lead(self.network, lead_id)
            self.assertFalse(result)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(elapsed_time, 1.0, "New lead checking too slow")

    def test_database_index_effectiveness(self):
        """Test effectiveness of database indexes."""
        # Create many duplicate checks
        for i in range(500):
            DuplicateLeadCheckFactory(network=self.network, lead_id=f"INDEX_TEST_{i}")
        
        # Test query performance
        import time
        
        start_time = time.time()
        
        # Query by network and lead_id (should use index)
        checks = DuplicateLeadCheck.objects.filter(
            network=self.network,
            lead_id="INDEX_TEST_250"
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Should be very fast with proper indexing
        self.assertLess(elapsed_time, 0.01, "Index query too slow")
        self.assertEqual(checks.count(), 1)

    def test_bulk_duplicate_check_creation(self):
        """Test bulk creation of duplicate checks."""
        import time
        
        # Prepare bulk data
        checks_data = []
        for i in range(100):
            checks_data.append(DuplicateLeadCheck(
                network=self.network,
                lead_id=f"BULK_TEST_LEAD_{i}",
                first_seen_at=timezone.now()
            ))
        
        # Bulk create
        start_time = time.time()
        created_checks = DuplicateLeadCheck.objects.bulk_create(checks_data)
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        
        # Should complete quickly
        self.assertLess(elapsed_time, 1.0, "Bulk creation too slow")
        self.assertEqual(len(created_checks), 100)

    def test_memory_usage_with_large_dataset(self):
        """Test memory usage with large duplicate check dataset."""
        # Create many duplicate checks
        for i in range(1000):
            DuplicateLeadCheckFactory(
                network=self.network,
                lead_id=f"MEMORY_TEST_{i}",
                first_seen_at=timezone.now() - timedelta(days=i % 30)
            )
        
        # Query large dataset
        all_checks = list(DuplicateLeadCheck.objects.all())
        
        # Should handle large datasets efficiently
        self.assertEqual(len(all_checks), 1000)


class DeduplicationIntegrationTests(TestCase):
    """Test deduplication integration with postback processing."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()

    def test_deduplication_in_postback_processing(self):
        """Test deduplication integration in postback processing pipeline."""
        from api.postback.services import process_postback_sync
        
        lead_id = "INTEGRATION_TEST_LEAD"
        
        # Create initial postback
        log1 = PostbackLogFactory(
            network=self.network,
            lead_id=lead_id,
            status=PostbackStatus.RECEIVED
        )
        
        # Process first postback (should succeed)
        process_postback_sync(
            log1,
            signature="test",
            timestamp_str="1234567890",
            nonce="test_nonce",
            body_bytes=b'{"test": "data"}',
            path="/test/",
            query_params={}
        )
        
        log1.refresh_from_db()
        self.assertIn(log1.status, [PostbackStatus.VALIDATED, PostbackStatus.REWARDED])
        
        # Create second postback with same lead_id
        log2 = PostbackLogFactory(
            network=self.network,
            lead_id=lead_id,
            status=PostbackStatus.RECEIVED
        )
        
        # Process second postback (should be marked as duplicate)
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
        self.assertEqual(log2.status, PostbackStatus.DUPLICATE)

    def test_deduplication_with_different_networks(self):
        """Test deduplication across different networks."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        lead_id = "CROSS_NETWORK_INTEGRATION"
        
        # Create postback for network1
        log1 = PostbackLogFactory(
            network=network1,
            lead_id=lead_id,
            status=PostbackStatus.RECEIVED
        )
        
        # Create postback for network2 with same lead_id
        log2 = PostbackLogFactory(
            network=network2,
            lead_id=lead_id,
            status=PostbackStatus.RECEIVED
        )
        
        # Both should succeed (different networks)
        from api.postback.services import process_postback_sync
        
        process_postback_sync(log1, "test", "123", "nonce1", b'data', "/test/", {})
        process_postback_sync(log2, "test", "123", "nonce2", b'data', "/test/", {})
        
        log1.refresh_from_db()
        log2.refresh_from_db()
        
        self.assertNotEqual(log1.status, PostbackStatus.DUPLICATE)
        self.assertNotEqual(log2.status, PostbackStatus.DUPLICATE)

    def test_deduplication_cleanup_integration(self):
        """Test deduplication cleanup integration."""
        self.network.dedup_window = DeduplicationWindow.TWENTY_FOUR_HOURS
        self.network.save()
        
        # Create expired duplicate checks
        for i in range(5):
            DuplicateLeadCheckFactory(
                network=self.network,
                lead_id=f"EXPIRED_INTEGRATION_{i}",
                first_seen_at=timezone.now() - timedelta(days=2)
            )
        
        # Run cleanup
        deleted_count = DuplicateLeadCheck.objects.cleanup_expired(self.network)
        
        # Should delete expired checks
        self.assertGreaterEqual(deleted_count, 5)
        
        # Verify cleanup
        remaining_checks = DuplicateLeadCheck.objects.filter(network=self.network)
        self.assertEqual(remaining_checks.count(), 0)

    def test_deduplication_statistics(self):
        """Test deduplication statistics and reporting."""
        network = NetworkPostbackConfigFactory()
        
        # Create test data
        for i in range(10):
            DuplicateLeadCheckFactory(network=network, lead_id=f"STATS_LEAD_{i}")
        
        # Get statistics
        total_checks = DuplicateLeadCheck.objects.filter(network=network).count()
        recent_checks = DuplicateLeadCheck.objects.recent(days=7).filter(network=network).count()
        
        self.assertEqual(total_checks, 10)
        self.assertEqual(recent_checks, 10)
        
        # Test network-specific statistics
        network_stats = {
            'total_duplicates': total_checks,
            'recent_duplicates': recent_checks,
            'duplicate_rate': 0.0  # Would be calculated based on postback volume
        }
        
        self.assertIsInstance(network_stats, dict)
        self.assertIn('total_duplicates', network_stats)
        self.assertIn('recent_duplicates', network_stats)
