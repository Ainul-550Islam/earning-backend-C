"""Test Replay Service for Webhooks System

This module contains tests for the webhook replay service
including replay creation, processing, and batch operations.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..services.replay import ReplayService
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ..constants import (
    WebhookStatus, DeliveryStatus, ReplayStatus
)

User = get_user_model()


class ReplayServiceTest(TestCase):
    """Test cases for ReplayService."""
    
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
        self.replay_service = ReplayService()
    
    def test_create_replay_success(self):
        """Test successful replay creation."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.FAILED,
            response_code=500,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        self.assertIsInstance(replay, WebhookReplay)
        self.assertEqual(replay.original_log, original_log)
        self.assertEqual(replay.replayed_by, self.user)
        self.assertEqual(replay.reason, 'Test replay')
        self.assertEqual(replay.status, ReplayStatus.PENDING)
    
    def test_create_replay_with_none_log(self):
        """Test replay creation with None log."""
        with self.assertRaises(ValueError):
            self.replay_service.create_replay(
                original_log=None,
                replayed_by=self.user,
                reason='Test replay'
            )
    
    def test_create_replay_with_none_user(self):
        """Test replay creation with None user."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        with self.assertRaises(ValueError):
            self.replay_service.create_replay(
                original_log=original_log,
                replayed_by=None,
                reason='Test replay'
            )
    
    def test_create_replay_with_empty_reason(self):
        """Test replay creation with empty reason."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        with self.assertRaises(ValueError):
            self.replay_service.create_replay(
                original_log=original_log,
                replayed_by=self.user,
                reason=''
            )
    
    def test_process_replay_success(self):
        """Test successful replay processing."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.FAILED,
            response_code=500,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = self.replay_service.process_replay(replay)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['new_log_status'], DeliveryStatus.SUCCESS)
            
            # Check that replay was updated
            replay.refresh_from_db()
            self.assertEqual(replay.status, ReplayStatus.COMPLETED)
            self.assertIsNotNone(replay.new_log)
            self.assertIsNotNone(replay.replayed_at)
    
    def test_process_replay_failure(self):
        """Test replay processing failure."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.FAILED,
            response_code=500,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = False
            
            result = self.replay_service.process_replay(replay)
            
            self.assertFalse(result['success'])
            self.assertEqual(result['new_log_status'], DeliveryStatus.FAILED)
            
            # Check that replay was updated
            replay.refresh_from_db()
            self.assertEqual(replay.status, ReplayStatus.FAILED)
            self.assertIsNotNone(replay.new_log)
            self.assertIsNotNone(replay.replayed_at)
    
    def test_process_replay_already_completed(self):
        """Test processing an already completed replay."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Mark as completed
        replay.status = ReplayStatus.COMPLETED
        replay.save()
        
        result = self.replay_service.process_replay(replay)
        
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])
    
    def test_process_replay_already_processing(self):
        """Test processing an already processing replay."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Mark as processing
        replay.status = ReplayStatus.PROCESSING
        replay.save()
        
        result = self.replay_service.process_replay(replay)
        
        self.assertFalse(result['success'])
        self.assertIn('already processing', result['error'])
    
    def test_process_replay_with_exception(self):
        """Test replay processing with exception."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.side_effect = Exception('Dispatch error')
            
            result = self.replay_service.process_replay(replay)
            
            self.assertFalse(result['success'])
            self.assertIn('Dispatch error', result['error'])
            
            # Check that replay was marked as failed
            replay.refresh_from_db()
            self.assertEqual(replay.status, ReplayStatus.FAILED)
    
    def test_create_replay_batch_success(self):
        """Test successful replay batch creation."""
        # Create multiple delivery logs
        delivery_logs = []
        for i in range(5):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i, 'email': f'user{i}@example.com'},
                status=DeliveryStatus.FAILED,
                response_code=500,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        self.assertIsInstance(batch, WebhookReplayBatch)
        self.assertEqual(batch.created_by, self.user)
        self.assertEqual(batch.reason, 'Batch test replay')
        self.assertEqual(batch.count, 5)
        self.assertEqual(batch.status, ReplayStatus.PENDING)
        
        # Check that batch items were created
        items = batch.items.all()
        self.assertEqual(items.count(), 5)
        self.assertEqual(set(item.original_log for item in items), set(delivery_logs))
    
    def test_create_replay_batch_empty_logs(self):
        """Test replay batch creation with empty logs."""
        with self.assertRaises(ValueError):
            self.replay_service.create_replay_batch(
                delivery_logs=[],
                replayed_by=self.user,
                reason='Batch test replay'
            )
    
    def test_create_replay_batch_none_logs(self):
        """Test replay batch creation with None logs."""
        with self.assertRaises(ValueError):
            self.replay_service.create_replay_batch(
                delivery_logs=None,
                replayed_by=self.user,
                reason='Batch test replay'
            )
    
    def test_create_replay_batch_with_filters(self):
        """Test replay batch creation with filters."""
        # Create delivery logs with different event types
        delivery_logs = []
        for i in range(5):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created' if i < 3 else 'user.updated',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                response_code=500,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay',
            event_type_filter='user.created'
        )
        
        # Only 3 logs should match the filter
        self.assertEqual(batch.count, 3)
        self.assertEqual(batch.items.count(), 3)
    
    def test_process_replay_batch_success(self):
        """Test successful replay batch processing."""
        # Create delivery logs
        delivery_logs = []
        for i in range(3):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                response_code=500,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            result = self.replay_service.process_replay_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 3)
            self.assertEqual(result['success_count'], 3)
            self.assertEqual(result['failed_count'], 0)
            
            # Check that batch was updated
            batch.refresh_from_db()
            self.assertEqual(batch.status, ReplayStatus.COMPLETED)
            self.assertIsNotNone(batch.completed_at)
    
    def test_process_replay_batch_with_failures(self):
        """Test replay batch processing with some failures."""
        # Create delivery logs
        delivery_logs = []
        for i in range(3):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                response_code=500,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            # First two succeed, third fails
            mock_emit.side_effect = [True, True, False]
            
            result = self.replay_service.process_replay_batch(batch)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 3)
            self.assertEqual(result['success_count'], 2)
            self.assertEqual(result['failed_count'], 1)
            
            # Check that batch was updated
            batch.refresh_from_db()
            self.assertEqual(batch.status, ReplayStatus.COMPLETED)
    
    def test_process_replay_batch_already_completed(self):
        """Test processing an already completed replay batch."""
        delivery_logs = [WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        # Mark as completed
        batch.status = ReplayStatus.COMPLETED
        batch.save()
        
        result = self.replay_service.process_replay_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])
    
    def test_process_replay_batch_already_processing(self):
        """Test processing an already processing replay batch."""
        delivery_logs = [WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        # Mark as processing
        batch.status = ReplayStatus.PROCESSING
        batch.save()
        
        result = self.replay_service.process_replay_batch(batch)
        
        self.assertFalse(result['success'])
        self.assertIn('already processing', result['error'])
    
    def test_cancel_replay_success(self):
        """Test successful replay cancellation."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        result = self.replay_service.cancel_replay(replay, reason='Test cancellation')
        
        self.assertTrue(result['success'])
        
        # Check that replay was cancelled
        replay.refresh_from_db()
        self.assertEqual(replay.status, ReplayStatus.CANCELLED)
    
    def test_cancel_replay_already_completed(self):
        """Test cancelling an already completed replay."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Mark as completed
        replay.status = ReplayStatus.COMPLETED
        replay.save()
        
        result = self.replay_service.cancel_replay(replay, reason='Test cancellation')
        
        self.assertFalse(result['success'])
        self.assertIn('already completed', result['error'])
    
    def test_cancel_replay_batch_success(self):
        """Test successful replay batch cancellation."""
        delivery_logs = [WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        result = self.replay_service.cancel_replay_batch(batch, reason='Test batch cancellation')
        
        self.assertTrue(result['success'])
        
        # Check that batch was cancelled
        batch.refresh_from_db()
        self.assertEqual(batch.status, ReplayStatus.CANCELLED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_get_replay_status_success(self):
        """Test getting replay status."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        status = self.replay_service.get_replay_status(replay)
        
        self.assertEqual(status['replay_id'], replay.id)
        self.assertEqual(status['status'], ReplayStatus.PENDING)
        self.assertEqual(status['original_log_id'], original_log.id)
        self.assertEqual(status['reason'], 'Test replay')
        self.assertIsNone(status['new_log_id'])
        self.assertIsNone(status['replayed_at'])
    
    def test_get_replay_status_completed(self):
        """Test getting replay status for completed replay."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Mark as completed with new log
        new_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            created_by=self.user,
        )
        
        replay.status = ReplayStatus.COMPLETED
        replay.new_log = new_log
        replay.replayed_at = timezone.now()
        replay.save()
        
        status = self.replay_service.get_replay_status(replay)
        
        self.assertEqual(status['status'], ReplayStatus.COMPLETED)
        self.assertEqual(status['new_log_id'], new_log.id)
        self.assertIsNotNone(status['replayed_at'])
    
    def test_get_replay_batch_status_success(self):
        """Test getting replay batch status."""
        delivery_logs = [
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                created_by=self.user,
            )
            for i in range(3)
        ]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        status = self.replay_service.get_replay_batch_status(batch)
        
        self.assertEqual(status['batch_id'], batch.id)
        self.assertEqual(status['status'], ReplayStatus.PENDING)
        self.assertEqual(status['total_items'], 3)
        self.assertEqual(status['completed_items'], 0)
        self.assertEqual(status['failed_items'], 0)
        self.assertEqual(status['completion_percentage'], 0.0)
    
    def test_get_replay_batch_status_with_progress(self):
        """Test getting replay batch status with progress."""
        delivery_logs = [
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                created_by=self.user,
            )
            for i in range(3)
        ]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Batch test replay'
        )
        
        # Mark some items as completed
        items = batch.items.all()
        items[0].status = ReplayStatus.COMPLETED
        items[0].save()
        items[1].status = ReplayStatus.FAILED
        items[1].save()
        
        status = self.replay_service.get_replay_batch_status(batch)
        
        self.assertEqual(status['total_items'], 3)
        self.assertEqual(status['completed_items'], 1)
        self.assertEqual(status['failed_items'], 1)
        self.assertEqual(status['completion_percentage'], 33.33)
    
    def test_get_replay_statistics(self):
        """Test getting replay statistics."""
        # Create multiple replays
        original_logs = [
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                created_by=self.user,
            )
            for i in range(5)
        ]
        
        replays = []
        for log in original_logs:
            replay = self.replay_service.create_replay(
                original_log=log,
                replayed_by=self.user,
                reason='Test replay'
            )
            replays.append(replay)
        
        # Mark some as completed
        replays[0].status = ReplayStatus.COMPLETED
        replays[0].save()
        replays[1].status = ReplayStatus.COMPLETED
        replays[1].save()
        replays[2].status = ReplayStatus.FAILED
        replays[2].save()
        
        stats = self.replay_service.get_replay_statistics(
            endpoint=self.endpoint,
            days=30
        )
        
        self.assertEqual(stats['total_replays'], 5)
        self.assertEqual(stats['completed_replays'], 2)
        self.assertEqual(stats['failed_replays'], 1)
        self.assertEqual(stats['pending_replays'], 2)
        self.assertEqual(stats['success_rate'], 40.0)
    
    def test_get_replay_statistics_no_replays(self):
        """Test getting replay statistics with no replays."""
        stats = self.replay_service.get_replay_statistics(
            endpoint=self.endpoint,
            days=30
        )
        
        self.assertEqual(stats['total_replays'], 0)
        self.assertEqual(stats['completed_replays'], 0)
        self.assertEqual(stats['failed_replays'], 0)
        self.assertEqual(stats['pending_replays'], 0)
        self.assertEqual(stats['success_rate'], 0.0)
    
    def test_get_replay_statistics_by_event_type(self):
        """Test getting replay statistics by event type."""
        # Create replays for different event types
        log1 = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        log2 = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay1 = self.replay_service.create_replay(
            original_log=log1,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        replay2 = self.replay_service.create_replay(
            original_log=log2,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Mark one as completed
        replay1.status = ReplayStatus.COMPLETED
        replay1.save()
        
        stats = self.replay_service.get_replay_statistics(
            endpoint=self.endpoint,
            days=30,
            event_type='user.created'
        )
        
        self.assertEqual(stats['total_replays'], 1)
        self.assertEqual(stats['completed_replays'], 1)
        self.assertEqual(stats['success_rate'], 100.0)
    
    def test_cleanup_old_replays(self):
        """Test cleanup of old replays."""
        # Create old replay
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        replay = self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Test replay'
        )
        
        # Set old creation time
        replay.created_at = timezone.now() - timezone.timedelta(days=30)
        replay.save()
        
        result = self.replay_service.cleanup_old_replays(days=7)
        
        self.assertEqual(result['cleaned_count'], 1)
        
        # Check that replay was deleted
        with self.assertRaises(WebhookReplay.DoesNotExist):
            WebhookReplay.objects.get(id=replay.id)
    
    def test_cleanup_old_replay_batches(self):
        """Test cleanup of old replay batches."""
        # Create old replay batch
        delivery_logs = [WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )]
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Test batch replay'
        )
        
        # Set old creation time
        batch.created_at = timezone.now() - timezone.timedelta(days=30)
        batch.save()
        
        result = self.replay_service.cleanup_old_replay_batches(days=7)
        
        self.assertEqual(result['cleaned_count'], 1)
        
        # Check that batch was deleted
        with self.assertRaises(WebhookReplayBatch.DoesNotExist):
            WebhookReplayBatch.objects.get(id=batch.id)
    
    def test_get_replay_recommendations(self):
        """Test getting replay recommendations."""
        # Create failed delivery logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                response_code=500,
                created_by=self.user,
            )
        
        recommendations = self.replay_service.get_replay_recommendations(
            endpoint=self.endpoint,
            days=30
        )
        
        self.assertIn('high_failure_rate', recommendations)
        self.assertIn('recent_failures', recommendations)
    
    def test_get_replay_recommendations_no_failures(self):
        """Test getting replay recommendations with no failures."""
        # Create successful delivery logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                created_by=self.user,
            )
        
        recommendations = self.replay_service.get_replay_recommendations(
            endpoint=self.endpoint,
            days=30
        )
        
        self.assertEqual(recommendations, [])
    
    def test_validate_replay_eligibility(self):
        """Test validating replay eligibility."""
        # Create failed delivery log
        failed_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            response_code=500,
            created_by=self.user,
        )
        
        # Create successful delivery log
        success_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12346},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            created_by=self.user,
        )
        
        # Failed log should be eligible
        failed_eligibility = self.replay_service.validate_replay_eligibility(failed_log)
        self.assertTrue(failed_eligibility['eligible'])
        
        # Successful log should not be eligible
        success_eligibility = self.replay_service.validate_replay_eligibility(success_log)
        self.assertFalse(success_eligibility['eligible'])
        self.assertIn('already successful', success_eligibility['reason'])
    
    def test_validate_replay_eligibility_with_existing_replay(self):
        """Test validating replay eligibility with existing replay."""
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        # Create existing replay
        self.replay_service.create_replay(
            original_log=original_log,
            replayed_by=self.user,
            reason='Existing replay'
        )
        
        eligibility = self.replay_service.validate_replay_eligibility(original_log)
        
        self.assertFalse(eligibility['eligible'])
        self.assertIn('already replayed', eligibility['reason'])
    
    def test_validate_replay_eligibility_old_log(self):
        """Test validating replay eligibility with old log."""
        old_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_at=timezone.now() - timezone.timedelta(days=30),
            created_by=self.user,
        )
        
        eligibility = self.replay_service.validate_replay_eligibility(old_log)
        
        self.assertFalse(eligibility['eligible'])
        self.assertIn('too old', eligibility['reason'])
    
    def test_replay_performance(self):
        """Test replay performance."""
        import time
        
        # Create multiple delivery logs
        delivery_logs = []
        for i in range(10):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.FAILED,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        batch = self.replay_service.create_replay_batch(
            delivery_logs=delivery_logs,
            replayed_by=self.user,
            reason='Performance test'
        )
        
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            start_time = time.time()
            
            result = self.replay_service.process_replay_batch(batch)
            
            end_time = time.time()
            
            self.assertTrue(result['success'])
            self.assertEqual(result['processed_count'], 10)
            self.assertEqual(result['success_count'], 10)
            
            # Should complete in reasonable time (less than 5 seconds)
            self.assertLess(end_time - start_time, 5.0)
    
    def test_replay_concurrent_safety(self):
        """Test replay concurrent safety."""
        import threading
        
        original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        
        results = []
        
        def process_replay():
            replay = self.replay_service.create_replay(
                original_log=original_log,
                replayed_by=self.user,
                reason='Concurrent test'
            )
            
            with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
                mock_emit.return_value = True
                
                result = self.replay_service.process_replay(replay)
                results.append(result)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=process_replay)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All replays should succeed
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result['success'] for result in results))
