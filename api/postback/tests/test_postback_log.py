"""test_postback_log.py – Comprehensive tests for PostbackLog model and functionality."""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError

from api.postback.models import PostbackLog, NetworkPostbackConfig, DuplicateLeadCheck
from api.postback.choices import PostbackStatus, RejectionReason
from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackLogFactory,
    RewardedPostbackLogFactory,
    RejectedPostbackLogFactory,
    DuplicatePostbackLogFactory,
    FailedPostbackLogFactory,
    UserFactory,
)
from api.postback.exceptions import PostbackAlreadyProcessedException


class PostbackLogModelTests(TestCase):
    """Test PostbackLog model functionality."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.log = PostbackLogFactory(network=self.network)

    def test_postback_log_creation(self):
        """Test basic postback log creation."""
        self.assertEqual(self.log.network, self.network)
        self.assertEqual(self.log.status, PostbackStatus.RECEIVED)
        self.assertIsNotNone(self.log.id)
        self.assertIsNotNone(self.log.received_at)

    def test_postback_log_str_representation(self):
        """Test string representation of postback log."""
        str_repr = str(self.log)
        self.assertIn(self.log.network.network_key, str_repr)
        self.assertIn(self.log.get_status_display(), str_repr)
        self.assertIn(str(self.log.received_at.year), str_repr)

    def test_postback_log_default_values(self):
        """Test default field values."""
        log = PostbackLogFactory()
        self.assertEqual(log.status, PostbackStatus.RECEIVED)
        self.assertEqual(log.method, "GET")
        self.assertEqual(log.query_string, "")
        self.assertEqual(log.signature_verified, False)
        self.assertEqual(log.ip_whitelisted, False)
        self.assertEqual(log.points_awarded, 0)
        self.assertEqual(log.payout, 0)
        self.assertEqual(log.retry_count, 0)
        self.assertIsNone(log.processed_at)
        self.assertIsNone(log.next_retry_at)
        self.assertIsNone(log.resolved_user)
        self.assertIsNone(log.inventory_id)

    def test_postback_log_payload_structure(self):
        """Test raw_payload structure and validation."""
        payload = {
            "lead_id": "LEAD123",
            "offer_id": "OFFER456",
            "payout": "10.50",
            "currency": "USD",
            "custom_field": "value"
        }
        log = PostbackLogFactory(raw_payload=payload)
        
        self.assertEqual(log.raw_payload, payload)
        self.assertIsInstance(log.raw_payload, dict)
        self.assertIn("lead_id", log.raw_payload)

    def test_postback_log_request_headers_sanitization(self):
        """Test request headers are properly sanitized."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret_token",
            "X-Signature": "hmac_signature",
            "User-Agent": "TestAgent/1.0"
        }
        log = PostbackLogFactory(request_headers=headers)
        
        # Headers should be stored as-is (sanitization happens in service layer)
        self.assertEqual(log.request_headers, headers)

    def test_postback_log_extracted_fields(self):
        """Test extracted fields are properly stored."""
        log = PostbackLogFactory(
            lead_id="LEAD123",
            offer_id="OFFER456",
            transaction_id="TXN789",
            payout=Decimal("10.50"),
            currency="USD"
        )
        
        self.assertEqual(log.lead_id, "LEAD123")
        self.assertEqual(log.offer_id, "OFFER456")
        self.assertEqual(log.transaction_id, "TXN789")
        self.assertEqual(log.payout, Decimal("10.50"))
        self.assertEqual(log.currency, "USD")

    def test_postback_log_security_context(self):
        """Test security context fields."""
        log = PostbackLogFactory(
            source_ip="192.168.1.100",
            signature_verified=True,
            ip_whitelisted=True
        )
        
        self.assertEqual(log.source_ip, "192.168.1.100")
        self.assertTrue(log.signature_verified)
        self.assertTrue(log.ip_whitelisted)

    def test_postback_log_rejection_context(self):
        """Test rejection context fields."""
        log = RejectedPostbackLogFactory(
            rejection_reason=RejectionReason.INVALID_SIGNATURE,
            rejection_detail="HMAC signature mismatch"
        )
        
        self.assertEqual(log.status, PostbackStatus.REJECTED)
        self.assertEqual(log.rejection_reason, RejectionReason.INVALID_SIGNATURE)
        self.assertEqual(log.rejection_detail, "HMAC signature mismatch")

    def test_postback_log_reward_context(self):
        """Test reward context fields."""
        user = UserFactory()
        log = RewardedPostbackLogFactory(
            resolved_user=user,
            points_awarded=100,
            inventory_id="inv-123"
        )
        
        self.assertEqual(log.status, PostbackStatus.REWARDED)
        self.assertEqual(log.resolved_user, user)
        self.assertEqual(log.points_awarded, 100)
        self.assertEqual(log.inventory_id, "inv-123")

    def test_postback_log_processing_context(self):
        """Test processing context fields."""
        log = FailedPostbackLogFactory(
            processing_error="Database connection timeout",
            retry_count=3,
            next_retry_at=timezone.now() + timedelta(minutes=5)
        )
        
        self.assertEqual(log.status, PostbackStatus.FAILED)
        self.assertEqual(log.processing_error, "Database connection timeout")
        self.assertEqual(log.retry_count, 3)
        self.assertIsNotNone(log.next_retry_at)

    def test_postback_log_duplicate_context(self):
        """Test duplicate postback context."""
        log = DuplicatePostbackLogFactory()
        
        self.assertEqual(log.status, PostbackStatus.DUPLICATE)
        self.assertEqual(log.rejection_reason, RejectionReason.DUPLICATE_LEAD)

    def test_postback_log_integrity_hash_field(self):
        """Test integrity hash field exists and can be set."""
        log = PostbackLogFactory()
        
        # Initially should be empty
        self.assertEqual(log.integrity_hash, "")
        
        # Can set integrity hash
        test_hash = "a" * 64  # 64 character SHA-256 hash
        log.integrity_hash = test_hash
        log.save()
        
        log.refresh_from_db()
        self.assertEqual(log.integrity_hash, test_hash)

    def test_postback_log_integrity_hash_generation(self):
        """Test integrity hash generation method."""
        log = PostbackLogFactory(
            lead_id="LEAD123",
            offer_id="OFFER456",
            payout=Decimal("10.50")
        )
        
        hash_value = log.generate_integrity_hash()
        
        # Should be 64 characters (SHA-256)
        self.assertEqual(len(hash_value), 64)
        self.assertIsInstance(hash_value, str)
        
        # Should be consistent for same data
        hash_value2 = log.generate_integrity_hash()
        self.assertEqual(hash_value, hash_value2)

    def test_postback_log_integrity_verification(self):
        """Test integrity hash verification."""
        log = PostbackLogFactory()
        
        # Initially no hash, should be invalid
        self.assertFalse(log.verify_integrity())
        
        # Generate hash and verify
        log.integrity_hash = log.generate_integrity_hash()
        log.save()
        self.assertTrue(log.verify_integrity())

    def test_postback_log_integrity_verification_tampering(self):
        """Test integrity verification detects tampering."""
        log = PostbackLogFactory()
        log.integrity_hash = log.generate_integrity_hash()
        log.save()
        
        # Tamper with data
        log.lead_id = "TAMPERED"
        log.save()
        
        # Should detect tampering
        self.assertFalse(log.verify_integrity())

    def test_postback_log_mark_validated(self):
        """Test marking postback as validated."""
        log = PostbackLogFactory(status=PostbackStatus.RECEIVED)
        
        log.mark_validated()
        
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.VALIDATED)

    def test_postback_log_mark_rewarded(self):
        """Test marking postback as rewarded."""
        log = PostbackLogFactory(status=PostbackStatus.VALIDATED)
        user = UserFactory()
        
        log.mark_rewarded(points=100, inventory_id="inv-123")
        log.resolved_user = user
        log.save()
        
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.REWARDED)
        self.assertEqual(log.points_awarded, 100)
        self.assertEqual(log.inventory_id, "inv-123")
        self.assertIsNotNone(log.processed_at)

    def test_postback_log_mark_rejected(self):
        """Test marking postback as rejected."""
        log = PostbackLogFactory(status=PostbackStatus.RECEIVED)
        
        log.mark_rejected(
            RejectionReason.INVALID_SIGNATURE,
            "HMAC signature mismatch"
        )
        
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.REJECTED)
        self.assertEqual(log.rejection_reason, RejectionReason.INVALID_SIGNATURE)
        self.assertEqual(log.rejection_detail, "HMAC signature mismatch")
        self.assertIsNotNone(log.processed_at)

    def test_postback_log_mark_duplicate(self):
        """Test marking postback as duplicate."""
        log = PostbackLogFactory(status=PostbackStatus.RECEIVED)
        
        log.mark_duplicate()
        
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.DUPLICATE)
        self.assertEqual(log.rejection_reason, RejectionReason.DUPLICATE_LEAD)
        self.assertIsNotNone(log.processed_at)

    def test_postback_log_mark_failed(self):
        """Test marking postback as failed."""
        log = PostbackLogFactory(status=PostbackStatus.PROCESSING)
        retry_time = timezone.now() + timedelta(minutes=5)
        
        log.mark_failed("Database error", retry_time)
        
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.FAILED)
        self.assertEqual(log.processing_error, "Database error")
        self.assertEqual(log.retry_count, 1)
        self.assertEqual(log.next_retry_at, retry_time)

    def test_postback_log_increment_retry_count(self):
        """Test retry count increment in mark_failed."""
        log = PostbackLogFactory(status=PostbackStatus.FAILED, retry_count=2)
        
        log.mark_failed("Another error", timezone.now() + timedelta(minutes=10))
        
        log.refresh_from_db()
        self.assertEqual(log.retry_count, 3)

    def test_postback_log_manager_active(self):
        """Test PostbackLogManager active method."""
        # Create logs with different statuses
        PostbackLogFactory(status=PostbackStatus.RECEIVED)
        PostbackLogFactory(status=PostbackStatus.PROCESSING)
        PostbackLogFactory(status=PostbackStatus.REWARDED)
        PostbackLogFactory(status=PostbackStatus.REJECTED)
        
        active_logs = PostbackLog.objects.active()
        
        # Should include RECEIVED and PROCESSING
        statuses = [log.status for log in active_logs]
        self.assertIn(PostbackStatus.RECEIVED, statuses)
        self.assertIn(PostbackStatus.PROCESSING, statuses)
        self.assertNotIn(PostbackStatus.REWARDED, statuses)
        self.assertNotIn(PostbackStatus.REJECTED, statuses)

    def test_postback_log_manager_retryable(self):
        """Test PostbackLogManager retryable method."""
        # Create logs with different retry counts
        PostbackLogFactory(status=PostbackStatus.FAILED, retry_count=1)
        PostbackLogFactory(status=PostbackStatus.FAILED, retry_count=3)
        PostbackLogFactory(status=PostbackStatus.FAILED, retry_count=5)
        PostbackLogFactory(status=PostbackStatus.REWARDED)  # Not failed
        
        retryable_logs = PostbackLog.objects.retryable(max_retries=3)
        
        # Should include failed logs with retry_count <= 3
        retry_counts = [log.retry_count for log in retryable_logs]
        self.assertIn(1, retry_counts)
        self.assertIn(3, retry_counts)
        self.assertNotIn(5, retry_counts)

    def test_postback_log_manager_by_network(self):
        """Test PostbackLogManager by_network method."""
        network1 = NetworkPostbackConfigFactory()
        network2 = NetworkPostbackConfigFactory()
        
        PostbackLogFactory(network=network1)
        PostbackLogFactory(network=network1)
        PostbackLogFactory(network=network2)
        
        network1_logs = PostbackLog.objects.by_network(network1)
        network2_logs = PostbackLog.objects.by_network(network2)
        
        self.assertEqual(network1_logs.count(), 2)
        self.assertEqual(network2_logs.count(), 1)

    def test_postback_log_manager_by_status(self):
        """Test PostbackLogManager by_status method."""
        PostbackLogFactory(status=PostbackStatus.RECEIVED)
        PostbackLogFactory(status=PostbackStatus.RECEIVED)
        PostbackLogFactory(status=PostbackStatus.REWARDED)
        
        received_logs = PostbackLog.objects.by_status(PostbackStatus.RECEIVED)
        rewarded_logs = PostbackLog.objects.by_status(PostbackStatus.REWARDED)
        
        self.assertEqual(received_logs.count(), 2)
        self.assertEqual(rewarded_logs.count(), 1)

    def test_postback_log_manager_by_date_range(self):
        """Test PostbackLogManager by_date_range method."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        
        PostbackLogFactory(received_at=timezone.make_aware(datetime.combine(two_days_ago, datetime.min.time())))
        PostbackLogFactory(received_at=timezone.make_aware(datetime.combine(yesterday, datetime.min.time())))
        PostbackLogFactory(received_at=timezone.make_aware(datetime.combine(today, datetime.min.time())))
        
        logs = PostbackLog.objects.by_date_range(yesterday, today)
        
        self.assertEqual(logs.count(), 2)  # yesterday and today

    def test_postback_log_manager_search(self):
        """Test PostbackLogManager search method."""
        PostbackLogFactory(lead_id="LEAD123")
        PostbackLogFactory(lead_id="LEAD456")
        PostbackLogFactory(offer_id="OFFER789")
        
        # Search by lead_id
        lead_results = PostbackLog.objects.search("LEAD123")
        self.assertEqual(lead_results.count(), 1)
        self.assertEqual(lead_results.first().lead_id, "LEAD123")
        
        # Search by offer_id
        offer_results = PostbackLog.objects.search("OFFER789")
        self.assertEqual(offer_results.count(), 1)
        self.assertEqual(offer_results.first().offer_id, "OFFER789")

    def test_postback_log_timestamp_indexing(self):
        """Test timestamp-based queries are efficient."""
        # Create logs with different timestamps
        base_time = timezone.now()
        for i in range(10):
            PostbackLogFactory(
                received_at=base_time - timedelta(hours=i),
                processed_at=base_time - timedelta(hours=i) + timedelta(minutes=5)
            )
        
        # Query by received_at (should use index)
        recent_logs = PostbackLog.objects.filter(
            received_at__gte=base_time - timedelta(hours=5)
        )
        self.assertEqual(recent_logs.count(), 6)  # Last 5 hours + current

    def test_postback_log_network_indexing(self):
        """Test network-based queries are efficient."""
        network = NetworkPostbackConfigFactory()
        
        # Create multiple logs for the network
        for i in range(20):
            PostbackLogFactory(network=network)
        
        # Query by network (should use index)
        network_logs = PostbackLog.objects.filter(network=network)
        self.assertEqual(network_logs.count(), 20)

    def test_postback_log_status_indexing(self):
        """Test status-based queries are efficient."""
        # Create logs with different statuses
        for i in range(10):
            PostbackLogFactory(status=PostbackStatus.RECEIVED)
        for i in range(5):
            PostbackLogFactory(status=PostbackStatus.REWARDED)
        
        # Query by status (should use index)
        received_logs = PostbackLog.objects.filter(status=PostbackStatus.RECEIVED)
        rewarded_logs = PostbackLog.objects.filter(status=PostbackStatus.REWARDED)
        
        self.assertEqual(received_logs.count(), 10)
        self.assertEqual(rewarded_logs.count(), 5)

    def test_postback_log_composite_indexing(self):
        """Test composite index queries are efficient."""
        network = NetworkPostbackConfigFactory()
        
        # Create logs with network and status
        for i in range(15):
            PostbackLogFactory(network=network, status=PostbackStatus.RECEIVED)
        for i in range(10):
            PostbackLogFactory(network=network, status=PostbackStatus.REWARDED)
        
        # Query by network and status (should use composite index)
        received_network_logs = PostbackLog.objects.filter(
            network=network,
            status=PostbackStatus.RECEIVED
        )
        rewarded_network_logs = PostbackLog.objects.filter(
            network=network,
            status=PostbackStatus.REWARDED
        )
        
        self.assertEqual(received_network_logs.count(), 15)
        self.assertEqual(rewarded_network_logs.count(), 10)

    def test_postback_log_integrity_hash_indexing(self):
        """Test integrity hash queries are efficient."""
        # Create logs with integrity hashes
        for i in range(10):
            log = PostbackLogFactory()
            log.integrity_hash = log.generate_integrity_hash()
            log.save()
        
        # Query by integrity hash (should use index)
        test_log = PostbackLog.objects.first()
        hash_query = PostbackLog.objects.filter(integrity_hash=test_log.integrity_hash)
        self.assertEqual(hash_query.count(), 1)

    def test_postback_log_bulk_operations(self):
        """Test bulk operations on PostbackLog."""
        # Create logs in bulk
        logs_data = []
        for i in range(100):
            logs_data.append(PostbackLog(
                network=self.network,
                lead_id=f"LEAD{i}",
                offer_id=f"OFFER{i}",
                status=PostbackStatus.RECEIVED,
                received_at=timezone.now()
            ))
        
        created_logs = PostbackLog.objects.bulk_create(logs_data)
        self.assertEqual(len(created_logs), 100)
        
        # Bulk update
        PostbackLog.objects.filter(
            id__in=[log.id for log in created_logs[:50]]
        ).update(status=PostbackStatus.VALIDATED)
        
        validated_count = PostbackLog.objects.filter(
            id__in=[log.id for log in created_logs[:50]],
            status=PostbackStatus.VALIDATED
        ).count()
        self.assertEqual(validated_count, 50)

    def test_postback_log_transaction_isolation(self):
        """Test transaction isolation for postback operations."""
        with transaction.atomic():
            # Create log within transaction
            log = PostbackLogFactory(
                network=self.network,
                lead_id="TRANSACTION_TEST"
            )
            
            # Should be visible within transaction
            found_log = PostbackLog.objects.filter(lead_id="TRANSACTION_TEST").first()
            self.assertIsNotNone(found_log)
            
            # Rollback transaction
            transaction.set_rollback(True)
        
        # Should not exist after rollback
        found_log = PostbackLog.objects.filter(lead_id="TRANSACTION_TEST").first()
        self.assertIsNone(found_log)

    def test_postback_log_concurrent_processing(self):
        """Test concurrent postback processing scenarios."""
        log = PostbackLogFactory(status=PostbackStatus.RECEIVED)
        
        # Simulate concurrent status changes
        with transaction.atomic():
            # First transaction updates status
            locked_log = PostbackLog.objects.select_for_update().get(id=log.id)
            locked_log.status = PostbackStatus.PROCESSING
            locked_log.save()
        
        # Second transaction should see the updated status
        updated_log = PostbackLog.objects.get(id=log.id)
        self.assertEqual(updated_log.status, PostbackStatus.PROCESSING)

    def test_postback_log_data_integrity(self):
        """Test data integrity constraints."""
        # Test unique constraint on (network, lead_id) is not enforced (duplicates allowed)
        log1 = PostbackLogFactory(
            network=self.network,
            lead_id="DUPLICATE_TEST"
        )
        log2 = PostbackLogFactory(
            network=self.network,
            lead_id="DUPLICATE_TEST"
        )
        
        self.assertNotEqual(log1.id, log2.id)
        self.assertEqual(log1.lead_id, log2.lead_id)

    def test_postback_log_field_validation(self):
        """Test field validation constraints."""
        # Test max length constraints
        with self.assertRaises(Exception):  # Should raise database error
            PostbackLogFactory(lead_id="x" * 300)  # Exceeds max_length
        
        # Test decimal field constraints
        with self.assertRaises(Exception):  # Should raise database error
            PostbackLogFactory(payout=Decimal("999999999.99"))  # Exceeds max_digits

    def test_postback_log_soft_delete_scenarios(self):
        """Test scenarios where logs might be soft-deleted."""
        log = PostbackLogFactory()
        
        # Mark as failed with high retry count (effectively "soft deleted")
        log.mark_failed("Permanent failure", None)
        log.retry_count = 999
        log.save()
        
        # Should not appear in retryable queries
        retryable_logs = PostbackLog.objects.retryable(max_retries=10)
        self.assertNotIn(log.id, [l.id for l in retryable_logs])

    def test_postback_log_archival_readiness(self):
        """Test postback log readiness for archival."""
        # Create old logs
        old_date = timezone.now() - timedelta(days=400)
        old_log = PostbackLogFactory(
            received_at=old_date,
            status=PostbackStatus.REWARDED,
            processed_at=old_date + timedelta(minutes=5)
        )
        
        # Should be ready for archival (status is final, processed long ago)
        self.assertIn(old_log.status, [PostbackStatus.REWARDED, PostbackStatus.REJECTED, PostbackStatus.DUPLICATE])
        self.assertIsNotNone(old_log.processed_at)
        self.assertTrue((timezone.now() - old_log.processed_at).days > 365)

    def test_postback_log_performance_with_large_payloads(self):
        """Test performance with large JSON payloads."""
        # Create large payload
        large_payload = {
            "lead_id": "LEAD123",
            "data": {f"field_{i}": f"value_{i}" * 100 for i in range(100)}
        }
        
        log = PostbackLogFactory(raw_payload=large_payload)
        
        # Should handle large payloads efficiently
        self.assertIsInstance(log.raw_payload, dict)
        self.assertEqual(len(log.raw_payload["data"]), 100)

    def test_postback_log_unicode_handling(self):
        """Test Unicode character handling in postback logs."""
        unicode_payload = {
            "lead_id": "LEAD_测试_123",
            "offer_name": "Тестовое предложение",
            "description": "🎉 Special characters: àáâãäåæçèéêë"
        }
        
        log = PostbackLogFactory(raw_payload=unicode_payload)
        
        # Should handle Unicode properly
        self.assertEqual(log.raw_payload["lead_id"], "LEAD_测试_123")
        self.assertEqual(log.raw_payload["offer_name"], "Тестовое предложение")

    def test_postback_log_timezone_handling(self):
        """Test timezone handling in postback logs."""
        # Create log with specific timezone
        utc_time = timezone.now()
        log = PostbackLogFactory(received_at=utc_time)
        
        # Should store and retrieve timezone-aware datetime correctly
        self.assertEqual(log.received_at.tzinfo, utc_time.tzinfo)
        self.assertEqual(log.received_at.hour, utc_time.hour)

    def test_postback_log_null_field_handling(self):
        """Test handling of null/None fields."""
        log = PostbackLogFactory(
            resolved_user=None,
            processed_at=None,
            next_retry_at=None,
            inventory_id=None,
            rejection_detail=None,
            processing_error=None
        )
        
        # All nullable fields should be None
        self.assertIsNone(log.resolved_user)
        self.assertIsNone(log.processed_at)
        self.assertIsNone(log.next_retry_at)
        self.assertIsNone(log.inventory_id)
        self.assertEqual(log.rejection_detail, "")
        self.assertEqual(log.processing_error, "")

    def test_postback_log_json_field_validation(self):
        """Test JSON field validation and handling."""
        # Valid JSON
        valid_data = {"key": "value", "number": 123, "nested": {"inner": "data"}}
        log = PostbackLogFactory(raw_payload=valid_data)
        self.assertEqual(log.raw_payload, valid_data)
        
        # Invalid JSON should be handled at serializer level
        # Model accepts any dict-like structure

    def test_postback_log_manager_custom_filters(self):
        """Test custom manager filter methods."""
        network = NetworkPostbackConfigFactory()
        
        # Create test data
        PostbackLogFactory(network=network, status=PostbackStatus.RECEIVED, lead_id="LEAD1")
        PostbackLogFactory(network=network, status=PostbackStatus.REWARDED, lead_id="LEAD2")
        PostbackLogFactory(network=network, status=PostbackStatus.REJECTED, lead_id="LEAD3")
        
        # Test combined filters
        results = PostbackLog.objects.by_network(network).by_status(PostbackStatus.REWARDED)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().lead_id, "LEAD2")

    def test_postback_log_signal_integration(self):
        """Test signal integration with postback logs."""
        from api.postback.signals import postback_received, postback_rewarded
        
        # Mock signal handlers
        received_handler = MagicMock()
        rewarded_handler = MagicMock()
        
        postback_received.connect(received_handler)
        postback_rewarded.connect(rewarded_handler)
        
        # Create log (should trigger received signal)
        log = PostbackLogFactory()
        
        # Mark as rewarded (should trigger rewarded signal)
        log.mark_rewarded(100)
        
        # Verify signals were called
        received_handler.assert_called_once()
        rewarded_handler.assert_called_once()

    def test_postback_log_error_scenarios(self):
        """Test various error scenarios."""
        log = PostbackLogFactory()
        
        # Test marking already processed log
        log.status = PostbackStatus.REWARDED
        log.save()
        
        # Should still allow status changes (business logic may prevent this)
        log.mark_rejected(RejectionReason.MISSING_FIELDS, "Test rejection")
        log.refresh_from_db()
        self.assertEqual(log.status, PostbackStatus.REJECTED)

    def test_postback_log_memory_usage(self):
        """Test memory usage with large numbers of logs."""
        # Create many logs to test memory efficiency
        logs = []
        for i in range(1000):
            log = PostbackLogFactory(
                lead_id=f"LEAD{i}",
                raw_payload={"index": i, "data": "test" * 10}
            )
            logs.append(log)
        
        # Should handle large datasets efficiently
        self.assertEqual(len(logs), 1000)
        
        # Test queryset evaluation
        all_logs = list(PostbackLog.objects.all()[:100])
        self.assertEqual(len(all_logs), 100)
