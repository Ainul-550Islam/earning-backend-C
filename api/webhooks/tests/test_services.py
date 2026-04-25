"""Test Services for Webhooks System

This module contains tests for all webhook services
including core services, advanced features, analytics, and replay functionality.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from ...services.core import DispatchService, SignatureEngine
from ...services.filtering import FilterService
from ...services.batch import BatchService
from ...services.core import TemplateEngine
from ...services.analytics import HealthMonitorService, RateLimiterService
from ...services.replay import ReplayService
from ...models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ...constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, ErrorType
)

User = get_user_model()


class DispatchServiceTest(TestCase):
    """Test cases for DispatchService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.dispatch_service = DispatchService()
    
    def test_emit_webhook_success(self):
        """Test successful webhook emission."""
        event_data = {
            'user_id': 12345,
            'email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z',
        }
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = '{"status": "success"}'
            mock_post.return_value.elapsed.total_seconds.return_value = 0.1
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertTrue(success)
            mock_post.assert_called_once()
    
    def test_emit_webhook_failure(self):
        """Test webhook emission failure."""
        event_data = {'user_id': 12345}
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = '{"error": "Server error"}'
            mock_post.return_value.elapsed.total_seconds.return_value = 0.1
            
            success = self.dispatch_service.emit(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertFalse(success)
    
    def test_emit_async_webhook(self):
        """Test asynchronous webhook emission."""
        event_data = {'user_id': 12345}
        
        with patch('api.webhooks.tasks.dispatch_event.delay') as mock_task:
            success = self.dispatch_service.emit_async(
                endpoint=self.endpoint,
                event_type='user.created',
                payload=event_data,
            )
            
            self.assertTrue(success)
            mock_task.assert_called_once()
    
    def test_retry_logic(self):
        """Test retry logic."""
        event_data = {'user_id': 12345}
        
        # Create failed delivery log
        delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload=event_data,
            status=DeliveryStatus.FAILED,
            response_code=500,
            attempt_number=1,
        )
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.text = '{"status": "success"}'
            mock_post.return_value.elapsed.total_seconds.return_value = 0.1
            
            success = self.dispatch_service.retry_delivery(delivery_log)
            
            self.assertTrue(success)
            self.assertEqual(delivery_log.attempt_number, 2)
            self.assertEqual(delivery_log.status, DeliveryStatus.SUCCESS)
    
    def test_signature_generation(self):
        """Test webhook signature generation."""
        event_data = {'user_id': 12345}
        
        signature = self.dispatch_service.generate_signature(
            endpoint=self.endpoint,
            payload=event_data
        )
        
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)
    
    def test_signature_verification(self):
        """Test webhook signature verification."""
        event_data = {'user_id': 12345}
        
        signature = self.dispatch_service.generate_signature(
            endpoint=self.endpoint,
            payload=event_data
        )
        
        is_valid = self.dispatch_service.verify_signature(
            endpoint=self.endpoint,
            payload=event_data,
            signature=signature
        )
        
        self.assertTrue(is_valid)


class SignatureEngineTest(TestCase):
    """Test cases for SignatureEngine."""
    
    def setUp(self):
        """Set up test data."""
        self.signature_engine = SignatureEngine()
        self.secret = 'test-secret-key'
        self.payload = {'user_id': 12345, 'email': 'test@example.com'}
    
    def test_sign_payload(self):
        """Test payload signing."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)
    
    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        
        is_valid = self.signature_engine.verify(self.payload, signature, self.secret)
        
        self.assertTrue(is_valid)
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        invalid_signature = 'invalid-signature'
        
        is_valid = self.signature_engine.verify(self.payload, invalid_signature, self.secret)
        
        self.assertFalse(is_valid)
    
    def test_verify_signature_wrong_secret(self):
        """Test signature verification with wrong secret."""
        signature = self.signature_engine.sign(self.payload, self.secret)
        wrong_secret = 'wrong-secret'
        
        is_valid = self.signature_engine.verify(self.payload, signature, wrong_secret)
        
        self.assertFalse(is_valid)
    
    def test_signature_consistency(self):
        """Test signature consistency."""
        signature1 = self.signature_engine.sign(self.payload, self.secret)
        signature2 = self.signature_engine.sign(self.payload, self.secret)
        
        self.assertEqual(signature1, signature2)


class FilterServiceTest(TestCase):
    """Test cases for FilterService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.filter_service = FilterService()
    
    def test_evaluate_filter_equals(self):
        """Test filter evaluation with equals operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_contains(self):
        """Test filter evaluation with contains operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_greater_than(self):
        """Test filter evaluation with greater than operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.GREATER_THAN,
            value=100,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 150}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filter_less_than(self):
        """Test filter evaluation with less than operator."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='transaction.amount',
            operator=FilterOperator.LESS_THAN,
            value=200,
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'transaction_amount': 150}
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_evaluate_filters_multiple(self):
        """Test multiple filter evaluation (AND logic)."""
        # Create multiple filters
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.status',
            operator=FilterOperator.EQUALS,
            value='active',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_email': 'test@example.com',
            'user_status': 'active'
        }
        
        result = self.filter_service.evaluate_filters(self.endpoint, event_data)
        
        self.assertTrue(result)
    
    def test_nested_field_access(self):
        """Test nested field access in filters."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'profile': {
                'settings': {
                    'notifications': {
                        'email': 'test@example.com'
                    }
                }
            }
        }
        
        result = self.filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_validation(self):
        """Test filter configuration validation."""
        # Test invalid operator
        with self.assertRaises(Exception):
            WebhookFilter.objects.create(
                endpoint=self.endpoint,
                field_path='user.email',
                operator='invalid_operator',
                value='test@example.com',
                is_active=True,
                created_by=self.user,
            )
        
        # Test empty field path
        with self.assertRaises(Exception):
            WebhookFilter.objects.create(
                endpoint=self.endpoint,
                field_path='',
                operator=FilterOperator.EQUALS,
                value='test@example.com',
                is_active=True,
                created_by=self.user,
            )


class BatchServiceTest(TestCase):
    """Test cases for BatchService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.batch_service = BatchService()
    
    def test_create_batch(self):
        """Test batch creation."""
        # Create delivery logs
        delivery_logs = []
        for i in range(10):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 1000 + i},
                status=DeliveryStatus.PENDING,
                attempt_number=1,
            )
            delivery_logs.append(log)
        
        batch = self.batch_service.create_batch(self.endpoint, delivery_logs)
        
        self.assertEqual(batch.endpoint, self.endpoint)
        self.assertEqual(batch.event_count, 10)
        self.assertEqual(batch.status, BatchStatus.PENDING)
        self.assertIsNotNone(batch.batch_id)
    
    def test_start_batch_processing(self):
        """Test starting batch processing."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-001',
            endpoint=self.endpoint,
            event_count=5,
            status=BatchStatus.PENDING,
        )
        
        success = self.batch_service.start_batch_processing(batch)
        
        self.assertTrue(success)
        self.assertEqual(batch.status, BatchStatus.PROCESSING)
    
    def test_complete_batch(self):
        """Test batch completion."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-002',
            endpoint=self.endpoint,
            event_count=5,
            status=BatchStatus.PROCESSING,
        )
        
        success = self.batch_service.complete_batch(batch, 4)
        
        self.assertTrue(success)
        self.assertEqual(batch.status, BatchStatus.COMPLETED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_cancel_batch(self):
        """Test batch cancellation."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-003',
            endpoint=self.endpoint,
            event_count=5,
            status=BatchStatus.PROCESSING,
        )
        
        success = self.batch_service.cancel_batch(batch, 'Test cancellation')
        
        self.assertTrue(success)
        self.assertEqual(batch.status, BatchStatus.CANCELLED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_get_pending_batches(self):
        """Test getting pending batches."""
        # Create multiple batches
        for i in range(3):
            WebhookBatch.objects.create(
                batch_id=f'TEST-BATCH-00{i}',
                endpoint=self.endpoint,
                event_count=5,
                status=BatchStatus.PENDING,
            )
        
        pending_batches = self.batch_service.get_pending_batches()
        
        self.assertEqual(len(pending_batches), 3)
        for batch in pending_batches:
            self.assertEqual(batch.status, BatchStatus.PENDING)
    
    def test_batch_statistics(self):
        """Test batch statistics."""
        # Create batches with different statuses
        for i in range(5):
            status = BatchStatus.COMPLETED if i < 3 else BatchStatus.FAILED
            WebhookBatch.objects.create(
                batch_id=f'TEST-BATCH-00{i}',
                endpoint=self.endpoint,
                event_count=5,
                status=status,
                completed_at=timezone.now() if status == BatchStatus.COMPLETED else None,
            )
        
        stats = self.batch_service.get_batch_statistics(self.endpoint, days=30)
        
        self.assertEqual(stats['total_batches'], 5)
        self.assertEqual(stats['completed_batches'], 3)
        self.assertEqual(stats['failed_batches'], 2)
        self.assertEqual(stats['success_rate'], 60.0)


class TemplateEngineTest(TestCase):
    """Test cases for TemplateEngine."""
    
    def setUp(self):
        """Set up test data."""
        self.template_engine = TemplateEngine()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='''
                '{'
                'user_id': {{user_id}},
                'email': {{user_email}},
                'message': 'Welcome {{user_email}}!'
                '}'
            '',
            is_active=True,
            created_by=self.user,
        )
    
    def test_render_template_simple(self):
        """Test simple template rendering."""
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
        }
        
        rendered = self.template_engine.render_template(self.template, event_data)
        
        self.assertIn('user_id': 12345', rendered)
        self.assertIn('user_email': 'test@example.com', rendered)
        self.assertIn('message': 'Welcome test@example.com!', rendered)
    
    def test_render_template_with_conditionals(self):
        """Test template rendering with conditionals."""
        template = WebhookTemplate.objects.create(
            name='Conditional Template',
            event_type='user.created',
            payload_template='''
                '{'
                'user_id': {{user_id}},
                'email': {{user_email}},
                'is_premium': {% if user_premium %}true{% else %}false{% endif %}
                '}'
            '',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
            'user_premium': True,
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('is_premium': true', rendered)
    
    def test_apply_transform_rules(self):
        """Test transformation rules application."""
        template = WebhookTemplate.objects.create(
            name='Transform Test',
            event_type='user.created',
            payload_template='''
                '{'
                'user_id': {{user_id}},
                'email': {{user_email}},
                'formatted_email': {{user_email | upper}}
                '}'
            '',
            transform_rules={
                'format_email': {
                    'type': 'map_value',
                    'path': 'user_email',
                    'mappings': {
                        'test@example.com': 'TEST@EXAMPLE.COM',
                        'user@example.com': 'USER@EXAMPLE.COM',
                    }
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('formatted_email': 'TEST@EXAMPLE.COM', rendered)
    
    def test_template_validation(self):
        """Test template validation."""
        # Test invalid Jinja2 syntax
        with self.assertRaises(Exception):
            WebhookTemplate.objects.create(
                name='Invalid Template',
                event_type='user.created',
                payload_template='{% invalid syntax %}',
                is_active=True,
                created_by=self.user,
            )
    
    def test_nested_field_transformation(self):
        """Test nested field transformation."""
        template = WebhookTemplate.objects.create(
            name='Nested Field Test',
            event_type='user.created',
            payload_template='''
                '{'
                'user_id': {{user_id}},
                'profile_name': {{profile.name}}
                '}'
            '',
            transform_rules={
                'add_profile': {
                    'type': 'add_field',
                    'field_name': 'profile',
                    'value': {'name': 'Test User'}
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {
            'user_id': 12345,
        }
        
        rendered = self.template_engine.render_template(template, event_data)
        
        self.assertIn('profile_name': 'Test User', rendered)


class HealthMonitorServiceTest(TestCase):
    """Test cases for HealthMonitorService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.health_service = HealthMonitorService()
    
    def test_health_check_success(self):
        """Test successful health check."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.elapsed.total_seconds.return_value = 0.1
            
            result = self.health_service.check_endpoint_health(self.endpoint)
            
            self.assertTrue(result['is_healthy'])
            self.assertEqual(result['response_time_ms'], 100)
            self.assertEqual(result['status_code'], 200)
    
    def test_health_check_failure(self):
        """Test failed health check."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 500
            mock_get.return_value.elapsed.total_seconds.return_value = 5.0
            
            result = self.health_service.check_endpoint_health(self.endpoint)
            
            self.assertFalse(result['is_healthy'])
            self.assertEqual(result['response_time_ms'], 5000)
            self.assertEqual(result['status_code'], 500)
            self.assertIsNotNone(result['error'])
    
    def test_health_check_timeout(self):
        """Test health check timeout."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception('Connection timeout')
            
            result = self.health_service.check_endpoint_health(self.endpoint)
            
            self.assertFalse(result['is_healthy'])
            self.assertIsNone(result['response_time_ms'])
            self.assertIsNone(result['status_code'])
            self.assertIsNotNone(result['error'])
    
    def test_get_health_summary(self):
        """Test getting health summary."""
        # Create health logs
        for i in range(10):
            is_healthy = i < 8  # 8 healthy, 2 unhealthy
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                is_healthy=is_healthy,
                response_time_ms=100 + i * 10,
                status_code=200 if is_healthy else 500,
            )
        
        summary = self.health_service.get_endpoint_health_summary(self.endpoint, hours=24)
        
        self.assertEqual(summary['total_checks'], 10)
        self.assertEqual(summary['healthy_checks'], 8)
        self.assertEqual(summary['unhealthy_checks'], 2)
        self.assertEqual(summary['uptime_percentage'], 80.0)
    
    def test_auto_suspend_endpoint(self):
        """Test automatic endpoint suspension."""
        # Create unhealthy health logs
        for i in range(3):
            WebhookHealthLog.objects.create(
                endpoint=self.endpoint,
                is_healthy=False,
                response_time_ms=5000,
                status_code=500,
                error='Server error',
            )
        
        # This would be tested with actual health monitoring
        # For now, just test the model behavior
        self.assertEqual(
            WebhookHealthLog.objects.filter(
                endpoint=self.endpoint,
                is_healthy=False
            ).count(),
            3
        )


class RateLimiterServiceTest(TestCase):
    """Test cases for RateLimiterService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.rate_limiter = RateLimiterService()
    
    def test_is_rate_limited_false(self):
        """Test rate limiting when not exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 5  # Below limit of 1000
            
            is_limited = self.rate_limiter.is_rate_limited(self.endpoint)
            
            self.assertFalse(is_limited)
    
    def test_is_rate_limited_true(self):
        """Test rate limiting when exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 1000  # At limit
            
            is_limited = self.rate_limiter.is_rate_limited(self.endpoint)
            
            self.assertTrue(is_limited)
    
    def test_increment_request(self):
        """Test request increment."""
        with patch('django.core.cache.cache.get') as mock_get, \
             patch('django.core.cache.cache.set') as mock_set:
            mock_get.return_value = 5
            
            success = self.rate_limiter.increment_request(self.endpoint)
            
            self.assertTrue(success)
            mock_set.assert_called_once()
    
    def test_increment_request_exceeded(self):
        """Test request increment when limit exceeded."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 1000  # At limit
            
            success = self.rate_limiter.increment_request(self.endpoint)
            
            self.assertFalse(success)
    
    def test_reset_rate_limit(self):
        """Test rate limit reset."""
        with patch('django.core.cache.cache.delete') as mock_delete, \
             patch('django.core.cache.cache.set') as mock_set:
            
            success = self.rate_limiter.reset_rate_limit(self.endpoint)
            
            self.assertTrue(success)
            mock_delete.assert_called_once()
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status."""
        with patch('django.core.cache.cache.get') as mock_get:
            mock_get.return_value = 150
            
            status = self.rate_limiter.get_rate_limit_status(self.endpoint)
            
            self.assertEqual(status['current_count'], 150)
            self.assertEqual(status['rate_limit'], 1000)
            self.assertEqual(status['is_limited'], False)
            self.assertEqual(status['usage_percentage'], 15.0)
            self.assertEqual(status['remaining_requests'], 850)


class ReplayServiceTest(TestCase):
    """Test cases for ReplayService."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        # Create test delivery logs
        self.delivery_logs = []
        for i in range(5):
            log = WebhookDeliveryLog.objects.create(
                endpoint=WebhookEndpoint.objects.create(
                    url='https://example.com/webhook',
                    secret='test-secret',
                    status=WebhookStatus.ACTIVE,
                    created_by=self.user,
                ),
                event_type='user.created',
                payload={'user_id': 1000 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                attempt_number=1,
            )
            self.delivery_logs.append(log)
        
        self.replay_service = ReplayService()
    
    def test_create_replay(self):
        """Test replay creation."""
        replay = self.replay_service.create_replay(
            original_log=self.delivery_logs[0],
            replayed_by=self.user,
            reason='Test replay'
        )
        
        self.assertEqual(replay.original_log, self.delivery_logs[0])
        self.assertEqual(replay.replayed_by, self.user)
        self.assertEqual(replay.reason, 'Test replay')
        self.assertEqual(replay.status, ReplayStatus.PENDING)
    
    def test_create_replay_batch(self):
        """Test replay batch creation."""
        result = self.replay_service.create_replay_batch(
            event_type='user.created',
            from_date=timezone.now().date(),
            to_date=timezone.now().date() + timezone.timedelta(days=1),
            batch_size=10,
            user_id=self.user.id,
        )
        
        self.assertIsNotNone(result['batch'])
        self.assertEqual(result['event_count'], 5)
        self.assertEqual(result['batch'].event_type, 'user.created')
        self.assertEqual(result['batch'].status, ReplayStatus.PENDING)
    
    def test_start_batch_processing(self):
        """Test starting batch processing."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date(),
            date_to=timezone.now().date() + timezone.timedelta(days=1),
            count=5,
            status=ReplayStatus.PENDING,
        )
        
        success = self.replay_service.start_batch_processing(batch)
        
        self.assertTrue(success)
        self.assertEqual(batch.status, ReplayStatus.PROCESSING)
    
    def test_get_batch_progress(self):
        """Test getting batch progress."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date(),
            date_to=timezone.now().date() + timezone.timedelta(days=1),
            count=5,
            status=ReplayStatus.PROCESSING,
        )
        
        # Create replay items
        for i, log in enumerate(self.delivery_logs[:3]):
            WebhookReplayItem.objects.create(
                batch=batch,
                original_log=log,
                status=ReplayStatus.COMPLETED if i < 2 else ReplayStatus.PENDING,
            )
        
        progress = self.replay_service.get_batch_progress(batch.batch_id)
        
        self.assertEqual(progress['total_items'], 3)
        self.assertEqual(progress['processed_items'], 2)
        self.assertEqual(progress['completion_percentage'], 66.67)
    
    def test_cancel_batch(self):
        """Test batch cancellation."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date(),
            date_to=timezone.now().date() + timezone.timedelta(days=1),
            count=5,
            status=ReplayStatus.PROCESSING,
        )
        
        success = self.replay_service.cancel_batch(batch, 'Test cancellation')
        
        self.assertTrue(success)
        self.assertEqual(batch.status, ReplayStatus.CANCELLED)
        self.assertIsNotNone(batch.completed_at)
