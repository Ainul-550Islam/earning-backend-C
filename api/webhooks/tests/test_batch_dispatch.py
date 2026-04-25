"""Test Batch Dispatch for Webhooks System

This module contains tests for the webhook batch dispatch service
including batch processing, status tracking, and error handling.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..services.batch import BatchService
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookBatch, WebhookBatchItem, WebhookFilter
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)

User = get_user_model()


class BatchServiceTest(TestCase):
    """Test cases for BatchService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.batch_service = BatchService()
    
    def test_create_batch_success(self):
        """Test successful batch creation."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        self.assertIsInstance(batch, WebhookBatch)
        self.assertEqual(batch.endpoint, self.endpoint)
        self.assertEqual(batch.event_type, 'user.created')
        self.assertEqual(batch.event_count, 3)
        self.assertEqual(batch.status, BatchStatus.PENDING)
        self.assertEqual(batch.created_by, self.user)
        
        # Check that batch items were created
        items = batch.items.all()
        self.assertEqual(items.count(), 3)
    
    def test_create_batch_empty_events(self):
        """Test batch creation with empty events."""
        events = []
        
        with self.assertRaises(ValueError):
            self.batch_service.create_batch(
                endpoint=self.endpoint,
                event_type='user.created',
                events=events,
                created_by=self.user
            )
    
    def test_create_batch_none_events(self):
        """Test batch creation with None events."""
        with self.assertRaises(ValueError):
            self.batch_service.create_batch(
                endpoint=self.endpoint,
                event_type='user.created',
                events=None,
                created_by=self.user
            )
    
    def test_create_batch_with_filters(self):
        """Test batch creation with filters."""
        # Create filter
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@other.com'},  # Should be filtered out
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Only 2 events should pass the filter
        self.assertEqual(batch.event_count, 2)
        self.assertEqual(batch.items.count(), 2)
    
    def test_process_batch_success(self):
        """Test successful batch processing."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = self.batch_service.process_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 2)
            self.assertEqual(result['success_count'], 2)
            self.assertEqual(result['failed_count'], 0)
            
            # Check batch status
            batch.refresh_from_db()
            self.assertEqual(batch.status, BatchStatus.COMPLETED)
            self.assertIsNotNone(batch.completed_at)
    
    def test_process_batch_with_failures(self):
        """Test batch processing with some failures."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            # First two succeed, third fails
            mock_emit.side_effect = [True, True, False]
            
            result = self.batch_service.process_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 3)
            self.assertEqual(result['success_count'], 2)
            self.assertEqual(result['failed_count'], 1)
            
            # Check batch status
            batch.refresh_from_db()
            self.assertEqual(batch.status, BatchStatus.COMPLETED)
    
    def test_process_batch_all_failures(self):
        """Test batch processing with all failures."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = False
            
            result = self.batch_service.process_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 2)
            self.assertEqual(result['success_count'], 0)
            self.assertEqual(result['failed_count'], 2)
            
            # Check batch status
            batch.refresh_from_db()
            self.assertEqual(batch.status, BatchStatus.COMPLETED)
    
    def test_process_batch_already_completed(self):
        """Test processing an already completed batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as completed
        batch.status = BatchStatus.COMPLETED
        batch.save()
        
        result = self.batch_service.process_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])
    
    def test_process_batch_already_processing(self):
        """Test processing an already processing batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as processing
        batch.status = BatchStatus.PROCESSING
        batch.save()
        
        result = self.batch_service.process_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('already processing', result['error'])
    
    def test_process_batch_cancelled(self):
        """Test processing a cancelled batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as cancelled
        batch.status = BatchStatus.CANCELLED
        batch.save()
        
        result = self.batch_service.process_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('cancelled', result['error'])
    
    def test_process_batch_with_exception(self):
        """Test batch processing with exception."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.side_effect = Exception('Dispatch error')
            
            result = self.batch_service.process_batch(batch)
            
            self.assertFalse(result['success'])
            self.assertIn('Dispatch error', result['error'])
            
            # Check batch status
            batch.refresh_from_db()
            self.assertEqual(batch.status, BatchStatus.FAILED)
    
    def test_cancel_batch_success(self):
        """Test successful batch cancellation."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        result = self.batch_service.cancel_batch(batch, reason='Test cancellation')
        
        self.assertTrue(result['success'])
        
        # Check batch status
        batch.refresh_from_db()
        self.assertEqual(batch.status, BatchStatus.CANCELLED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_cancel_batch_already_completed(self):
        """Test cancelling an already completed batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as completed
        batch.status = BatchStatus.COMPLETED
        batch.save()
        
        result = self.batch_service.cancel_batch(batch, reason='Test cancellation')
        
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])
    
    def test_cancel_batch_already_processing(self):
        """Test cancelling a processing batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as processing
        batch.status = BatchStatus.PROCESSING
        batch.save()
        
        result = self.batch_service.cancel_batch(batch, reason='Test cancellation')
        
        self.assertFalse(result['success'])
        self.assertIn('already processing', result['error'])
    
    def test_retry_batch_success(self):
        """Test successful batch retry."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark some items as failed
        items = batch.items.all()
        items[0].status = BatchStatus.FAILED
        items[0].save()
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = self.batch_service.retry_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['retry_count'], 1)
            
            # Check that failed item was retried
            items[0].refresh_from_db()
            self.assertEqual(items[0].status, BatchStatus.COMPLETED)
    
    def test_retry_batch_no_failed_items(self):
        """Test retrying batch with no failed items."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # All items are already completed
        items = batch.items.all()
        for item in items:
            item.status = BatchStatus.COMPLETED
            item.save()
        
        result = self.batch_service.retry_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('no failed items', result['error'])
    
    def test_get_batch_status_success(self):
        """Test getting batch status."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        status = self.batch_service.get_batch_status(batch)
        
        self.assertEqual(status['batch_id'], batch.batch_id)
        self.assertEqual(status['status'], BatchStatus.PENDING)
        self.assertEqual(status['total_items'], 1)
        self.assertEqual(status['completed_items'], 0)
        self.assertEqual(status['failed_items'], 0)
        self.assertEqual(status['completion_percentage'], 0.0)
    
    def test_get_batch_status_with_progress(self):
        """Test getting batch status with progress."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark some items as completed
        items = batch.items.all()
        items[0].status = BatchStatus.COMPLETED
        items[0].save()
        items[1].status = BatchStatus.FAILED
        items[1].save()
        
        status = self.batch_service.get_batch_status(batch)
        
        self.assertEqual(status['total_items'], 3)
        self.assertEqual(status['completed_items'], 1)
        self.assertEqual(status['failed_items'], 1)
        self.assertEqual(status['completion_percentage'], 33.33)
    
    def test_get_batch_status_completed(self):
        """Test getting batch status for completed batch."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark all items as completed
        items = batch.items.all()
        for item in items:
            item.status = BatchStatus.COMPLETED
            item.save()
        
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = timezone.now()
        batch.save()
        
        status = self.batch_service.get_batch_status(batch)
        
        self.assertEqual(status['status'], BatchStatus.COMPLETED)
        self.assertEqual(status['total_items'], 2)
        self.assertEqual(status['completed_items'], 2)
        self.assertEqual(status['failed_items'], 0)
        self.assertEqual(status['completion_percentage'], 100.0)
        self.assertIsNotNone(status['completed_at'])
    
    def test_create_batch_with_large_events(self):
        """Test batch creation with large events."""
        # Create large events
        events = []
        for i in range(100):
            events.append({
                'user_id': 12345 + i,
                'email': f'user{i}@example.com',
                'large_data': ['x' * 100] * 10  # Large data
            })
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        self.assertEqual(batch.event_count, 100)
        self.assertEqual(batch.items.count(), 100)
    
    def test_process_batch_with_large_events(self):
        """Test batch processing with large events."""
        # Create large events
        events = []
        for i in range(50):
            events.append({
                'user_id': 12345 + i,
                'email': f'user{i}@example.com',
                'large_data': ['x' * 100] * 10  # Large data
            })
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = self.batch_service.process_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 50)
            self.assertEqual(result['success_count'], 50)
    
    def test_process_batch_performance(self):
        """Test batch processing performance."""
        import time
        
        # Create events
        events = []
        for i in range(100):
            events.append({
                'user_id': 12345 + i,
                'email': f'user{i}@example.com'
            })
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            start_time = time.time()
            
            result = self.batch_service.process_batch(batch)
            
            end_time = time.time()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 100)
            self.assertEqual(result['success_count'], 100)
            
            # Should complete in reasonable time (less than 5 seconds)
            self.assertLess(end_time - start_time, 5.0)
    
    def test_process_batch_concurrent_safety(self):
        """Test batch processing concurrent safety."""
        import threading
        
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        results = []
        
        def process_batch():
            with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
                mock_emit.return_value = True
                
                result = self.batch_service.process_batch(batch)
                results.append(result)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=process_batch)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Only one thread should succeed
        success_count = sum(1 for result in results if result['success'])
        self.assertEqual(success_count, 1)
    
    def test_create_batch_with_custom_batch_id(self):
        """Test batch creation with custom batch ID."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user,
            batch_id='CUSTOM-BATCH-123'
        )
        
        self.assertEqual(batch.batch_id, 'CUSTOM-BATCH-123')
    
    def test_create_batch_with_priority(self):
        """Test batch creation with priority."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user,
            priority='high'
        )
        
        # Priority should be stored (implementation dependent)
        self.assertIsInstance(batch, WebhookBatch)
    
    def test_create_batch_with_metadata(self):
        """Test batch creation with metadata."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        metadata = {
            'source': 'import',
            'import_id': 'import-123',
            'user_id': 12345
        }
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user,
            metadata=metadata
        )
        
        # Metadata should be stored (implementation dependent)
        self.assertIsInstance(batch, WebhookBatch)
    
    def test_get_batch_statistics(self):
        """Test getting batch statistics."""
        events = [
            {'user_id': 12345, 'email': 'user1@example.com'},
            {'user_id': 12346, 'email': 'user2@example.com'},
            {'user_id': 12347, 'email': 'user3@example.com'}
        ]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark some items as completed/failed
        items = batch.items.all()
        items[0].status = BatchStatus.COMPLETED
        items[0].save()
        items[1].status = BatchStatus.FAILED
        items[1].save()
        
        stats = self.batch_service.get_batch_statistics(batch)
        
        self.assertEqual(stats['total_items'], 3)
        self.assertEqual(stats['completed_items'], 1)
        self.assertEqual(stats['failed_items'], 1)
        self.assertEqual(stats['pending_items'], 1)
        self.assertEqual(stats['success_rate'], 33.33)
    
    def test_get_batch_statistics_empty(self):
        """Test getting batch statistics for empty batch."""
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=[],
            created_by=self.user
        )
        
        stats = self.batch_service.get_batch_statistics(batch)
        
        self.assertEqual(stats['total_items'], 0)
        self.assertEqual(stats['completed_items'], 0)
        self.assertEqual(stats['failed_items'], 0)
        self.assertEqual(stats['pending_items'], 0)
        self.assertEqual(stats['success_rate'], 0.0)
    
    def test_cleanup_old_batches(self):
        """Test cleanup of old batches."""
        # Create old batch
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as completed and set old date
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = timezone.now() - timezone.timedelta(days=30)
        batch.save()
        
        # Cleanup batches older than 7 days
        result = self.batch_service.cleanup_old_batches(days=7)
        
        self.assertEqual(result['cleaned_count'], 1)
        
        # Check that batch was deleted
        with self.assertRaises(WebhookBatch.DoesNotExist):
            WebhookBatch.objects.get(id=batch.id)
    
    def test_cleanup_old_batches_recent(self):
        """Test cleanup of old batches with recent batch."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark as completed and set recent date
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = timezone.now() - timezone.timedelta(days=1)
        batch.save()
        
        # Cleanup batches older than 7 days
        result = self.batch_service.cleanup_old_batches(days=7)
        
        self.assertEqual(result['cleaned_count'], 0)
        
        # Check that batch still exists
        WebhookBatch.objects.get(id=batch.id)
    
    def test_get_batches_by_status(self):
        """Test getting batches by status."""
        # Create batches with different statuses
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        batch1 = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        batch2 = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Mark one as completed
        batch2.status = BatchStatus.COMPLETED
        batch2.save()
        
        # Get pending batches
        pending_batches = self.batch_service.get_batches_by_status(BatchStatus.PENDING)
        
        self.assertEqual(pending_batches.count(), 1)
        self.assertEqual(pending_batches.first().id, batch1.id)
        
        # Get completed batches
        completed_batches = self.batch_service.get_batches_by_status(BatchStatus.COMPLETED)
        
        self.assertEqual(completed_batches.count(), 1)
        self.assertEqual(completed_batches.first().id, batch2.id)
    
    def test_get_batches_by_endpoint(self):
        """Test getting batches by endpoint."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        # Create batches for different endpoints
        endpoint2 = WebhookEndpoint.objects.create(
            url='https://example2.com/webhook',
            secret='test-secret-key-2',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        batch1 = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        batch2 = self.batch_service.create_batch(
            endpoint=endpoint2,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Get batches for first endpoint
        endpoint1_batches = self.batch_service.get_batches_by_endpoint(self.endpoint)
        
        self.assertEqual(endpoint1_batches.count(), 1)
        self.assertEqual(endpoint1_batches.first().id, batch1.id)
        
        # Get batches for second endpoint
        endpoint2_batches = self.batch_service.get_batches_by_endpoint(endpoint2)
        
        self.assertEqual(endpoint2_batches.count(), 1)
        self.assertEqual(endpoint2_batches.first().id, batch2.id)
    
    def test_get_batches_by_date_range(self):
        """Test getting batches by date range."""
        events = [{'user_id': 12345, 'email': 'user1@example.com'}]
        
        # Create batches with different dates
        batch1 = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        batch2 = self.batch_service.create_batch(
            endpoint=self.endpoint,
            event_type='user.created',
            events=events,
            created_by=self.user
        )
        
        # Modify created_at for batch2
        batch2.created_at = timezone.now() - timezone.timedelta(days=10)
        batch2.save()
        
        # Get batches for last 7 days
        recent_batches = self.batch_service.get_batches_by_date_range(
            start_date=timezone.now() - timezone.timedelta(days=7),
            end_date=timezone.now()
        )
        
        self.assertEqual(recentent_batches.count(), 1)
        self.assertEqual(recentent_batches.first().id, batch1.id)
        
        # Get batches for last 14 days
        all_batches = self.batch_service.get_batches_by_date_range(
            start_date=timezone.now() - timezone.timedelta(days=14),
            end_date=timezone.now()
        )
        
        self.assertEqual(all_batches.count(), 2)
