"""Test Models for Webhooks System

This module contains tests for all webhook models
including core models, advanced features, analytics, and replay functionality.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch

from ...models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from ...constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)

User = get_user_model()


class WebhookEndpointModelTest(TestCase):
    """Test cases for WebhookEndpoint model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_str_representation(self):
        """Test string representation."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        self.assertEqual(str(endpoint), 'https://example.com/webhook')
        self.assertEqual(endpoint.status, 'Active')
    
    def test_url_validation(self):
        """Test URL validation."""
        with self.assertRaises(Exception):
            endpoint = WebhookEndpoint.objects.create(
                url='invalid-url',
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )
    
    def test_secret_rotation(self):
        """Test secret rotation."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        old_secret = endpoint.secret
        new_secret = 'new-test-secret'
        endpoint.secret = new_secret
        endpoint.save()
        
        self.assertEqual(endpoint.secret, new_secret)
        self.assertNotEqual(endpoint.secret, old_secret)
    
    def test_rate_limit_configuration(self):
        """Test rate limit configuration."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            rate_limit_per_min=500,
            created_by=self.user,
        )
        
        self.assertEqual(endpoint.rate_limit_per_min, 500)
    
    def test_ip_whitelist_configuration(self):
        """Test IP whitelist configuration."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            ip_whitelist=['192.168.1.1', '10.0.0.1'],
            created_by=self.user,
        )
        
        self.assertEqual(endpoint.ip_whitelist, ['192.168.1.1', '10.0.0.1'])
    
    def test_status_transitions(self):
        """Test status transitions."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        # Test pause
        endpoint.status = WebhookStatus.PAUSED
        endpoint.save()
        
        # Test resume
        endpoint.status = WebhookStatus.ACTIVE
        endpoint.save()
        
        self.assertEqual(endpoint.status, 'Active')
    
    def test_deletion(self):
        """Test endpoint deletion."""
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        
        endpoint_id = endpoint.id
        endpoint.delete()
        
        self.assertFalse(WebhookEndpoint.objects.filter(id=endpoint_id).exists())


class WebhookSubscriptionModelTest(TestCase):
    """Test cases for WebhookSubscription model."""
    
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
    
    def test_subscription_creation(self):
        """Test subscription creation."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        self.assertEqual(subscription.endpoint, self.endpoint)
        self.assertEqual(subscription.event_type, 'user.created')
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.filter_config, {'user_id': 12345})
    
    def test_filter_configuration(self):
        """Test filter configuration."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={
                'field_path': 'user.email',
                'operator': FilterOperator.EQUALS,
                'value': '@example.com',
            },
            is_active=True,
            created_by=self.user,
        )
        
        self.assertEqual(subscription.filter_config['field_path'], 'user.email')
        self.assertEqual(subscription.filter_config['operator'], FilterOperator.EQUALS)
        self.assertEqual(subscription.filter_config['value'], '@example.com')
    
    def test_subscription_deactivation(self):
        """Test subscription deactivation."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        subscription.is_active = False
        subscription.save()
        
        self.assertFalse(subscription.is_active)
    
    def test_subscription_deletion(self):
        """Test subscription deletion."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filter_config={'user_id': 12345},
            is_active=True,
            created_by=self.user,
        )
        
        subscription_id = subscription.id
        subscription.delete()
        
        self.assertFalse(WebhookSubscription.objects.filter(id=subscription_id).exists())


class WebhookDeliveryLogModelTest(TestCase):
    """Test cases for WebhookDeliveryLog model."""
    
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
    
    def test_delivery_log_creation(self):
        """Test delivery log creation."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            response_body='{"status": "success"}',
            duration_ms=150,
            attempt_number=1,
            created_by=self.user,
        )
        
        self.assertEqual(log.endpoint, self.endpoint)
        self.assertEqual(log.event_type, 'user.created')
        self.assertEqual(log.status, DeliveryStatus.SUCCESS)
        self.assertEqual(log.response_code, 200)
        self.assertEqual(log.attempt_number, 1)
    
    def test_retry_logic(self):
        """Test retry logic."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            response_code=500,
            response_body='{"error": "Server error"}',
            attempt_number=1,
            created_by=self.user,
        )
        
        # Test retry
        retry_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.RETRYING,
            response_code=500,
            response_body='{"error": "Server error"}',
            attempt_number=2,
            created_by=self.user,
            next_retry_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        
        self.assertEqual(retry_log.attempt_number, 2)
        self.assertIsNotNone(retry_log.next_retry_at)
    
    def test_success_log(self):
        """Test successful delivery log."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            response_body='{"status": "success"}',
            duration_ms=100,
            attempt_number=1,
            created_by=self.user,
        )
        
        self.assertEqual(log.status, DeliveryStatus.SUCCESS)
        self.assertEqual(log.response_code, 200)
        self.assertEqual(log.duration_ms, 100)
    
    def test_log_ordering(self):
        """Test log ordering."""
        # Create multiple logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                duration_ms=100 + i,
                attempt_number=i + 1,
                created_by=self.user,
            )
        
        # Test ordering
        logs = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint)
        self.assertEqual(logs.count(), 5)
        
        # Check they're ordered by created_at (newest first)
        for i, log in enumerate(logs):
            self.assertEqual(log.duration_ms, 100 + (4 - i))


class WebhookFilterModelTest(TestCase):
    """Test cases for WebhookFilter model."""
    
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
    
    def test_filter_creation(self):
        """Test filter creation."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        self.assertEqual(filter_obj.endpoint, self.endpoint)
        self.assertEqual(filter_obj.field_path, 'user.email')
        self.assertEqual(filter_obj.operator, FilterOperator.EQUALS)
        self.assertEqual(filter_obj.value, '@example.com')
        self.assertTrue(filter_obj.is_active)
    
    def test_filter_evaluation(self):
        """Test filter evaluation logic."""
        from ...services.filtering import FilterService
        
        filter_service = FilterService()
        
        # Test equals operator
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        
        event_data = {'user_email': 'test@example.com'}
        result = filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_complex_filter(self):
        """Test complex filter with nested fields."""
        from ...services.filtering import FilterService
        
        filter_service = FilterService()
        
        # Test contains operator on nested field
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.CONTAINS,
            value='marketing',
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
        
        result = filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_validation(self):
        """Test filter validation."""
        with self.assertRaises(Exception):
            WebhookFilter.objects.create(
                endpoint=self.endpoint,
                field_path='',  # Invalid: empty field path
                operator=FilterOperator.EQUALS,
                value='test',
                is_active=True,
                created_by=self.user,
            )


class WebhookBatchModelTest(TestCase):
    """Test cases for WebhookBatch model."""
    
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
    
    def test_batch_creation(self):
        """Test batch creation."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-001',
            endpoint=self.endpoint,
            event_count=100,
            status=BatchStatus.PENDING,
            created_by=self.user,
        )
        
        self.assertEqual(batch.batch_id, 'TEST-BATCH-001')
        self.assertEqual(batch.endpoint, self.endpoint)
        self.assertEqual(batch.event_count, 100)
        self.assertEqual(batch.status, BatchStatus.PENDING)
    
    def test_batch_processing(self):
        """Test batch processing."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-002',
            endpoint=self.endpoint,
            event_count=50,
            status=BatchStatus.PROCESSING,
            created_by=self.user,
        )
        
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = timezone.now()
        batch.save()
        
        self.assertEqual(batch.status, BatchStatus.COMPLETED)
        self.assertIsNotNone(batch.completed_at)
    
    def test_batch_items(self):
        """Test batch item creation."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-003',
            endpoint=self.endpoint,
            event_count=10,
            status=BatchStatus.PROCESSING,
            created_by=self.user,
        )
        
        # Create delivery logs
        delivery_logs = []
        for i in range(10):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                response_code=200,
                attempt_number=1,
                created_by=self.user,
            )
            delivery_logs.append(log)
        
        # Create batch items
        for i, log in enumerate(delivery_logs):
            WebhookBatchItem.objects.create(
                batch=batch,
                delivery_log=log,
                position=i + 1,
            )
        
        self.assertEqual(batch.items.count(), 10)
        self.assertEqual(batch.event_count, 10)
    
    def test_batch_status_transitions(self):
        """Test batch status transitions."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-004',
            endpoint=self.endpoint,
            event_count=5,
            status=BatchStatus.PENDING,
            created_by=self.user,
        )
        
        # Test completion
        batch.status = BatchStatus.COMPLETED
        batch.completed_at = timezone.now()
        batch.save()
        
        # Test cancellation
        batch.status = BatchStatus.CANCELLED
        batch.completed_at = timezone.now()
        batch.save()
        
        self.assertEqual(batch.status, BatchStatus.CANCELLED)
        self.assertIsNotNone(batch.completed_at)


class WebhookTemplateModelTest(TestCase):
    """Test cases for WebhookTemplate model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
    
    def test_template_creation(self):
        """Test template creation."""
        template = WebhookTemplate.objects.create(
            name='Welcome Email Template',
            event_type='user.created',
            payload_template='''
                'Welcome {{user.email}}!',
                'Your account has been created successfully.'
                'Best regards,'
                'The Team'
            '',
            is_active=True,
            created_by=self.user,
        )
        
        self.assertEqual(template.name, 'Welcome Email Template')
        self.assertEqual(template.event_type, 'user.created')
        self.assertTrue(template.is_active)
        self.assertIn('Welcome {{user.email}}!', template.payload_template)
        self.assertIn('Your account has been created successfully.', template.payload_template)
    
    def test_template_rendering(self):
        """Test template rendering."""
        from ...services.core import TemplateEngine
        
        template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='''
                '{'
                'user_id': {{user_id}},
                'email': {{user_email}},
                'created_at': {{created_at}}
                '}'
            '',
            is_active=True,
            created_by=self.user,
        )
        
        engine = TemplateEngine()
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z',
        }
        
        rendered_payload = engine.render_template(template, event_data)
        
        self.assertIn('user_id': 12345', rendered_payload)
        self.assertIn('user_email': 'test@example.com', rendered_payload)
        self.assertIn('created_at': '2024-01-01T00:00:00Z', rendered_payload)
    
    def test_transformation_rules(self):
        """Test transformation rules."""
        template = WebhookTemplate.objects.create(
            name='Transformation Test',
            event_type='user.created',
            payload_template='''
                '{'
                'original_email': {{user_email}},
                'formatted_email': {{user_email | upper}}
                '}'
            '',
            transform_rules={
                'format_email': {
                    'type': 'format_date',
                    'path': 'user_email',
                    'format': '%Y-%m-%d'
                }
            },
            is_active=True,
            created_by=self.user,
        )
        
        engine = TemplateEngine()
        
        event_data = {
            'user_email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z',
        }
        
        rendered_payload = engine.render_template(template, event_data)
        
        self.assertIn('formatted_email': 'TEST@EXAMPLE.COM', rendered_payload)
        self.assertNotIn('original_email', rendered_payload)  # Should be transformed


class WebhookAnalyticsModelTest(TestCase):
    """Test cases for WebhookAnalytics model."""
    
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
    
    def test_analytics_creation(self):
        """Test analytics creation."""
        analytics = WebhookAnalytics.objects.create(
            date=timezone.now().date(),
            endpoint=self.endpoint,
            total_sent=100,
            success_count=95,
            failed_count=5,
            avg_latency_ms=150.5,
            success_rate=95.0,
            created_by=self.user,
        )
        
        self.assertEqual(analytics.endpoint, self.endpoint)
        self.assertEqual(analytics.total_sent, 100)
        self.assertEqual(analytics.success_count, 95)
        self.assertEqual(analytics.failed_count, 5)
        self.assertEqual(analytics.success_rate, 95.0)
    
    def test_analytics_aggregation(self):
        """Test analytics aggregation."""
        # Create analytics for multiple days
        dates = [timezone.now().date() - timezone.timedelta(days=i) for i in range(5)]
        
        for i, date in enumerate(dates):
            WebhookAnalytics.objects.create(
                date=date,
                endpoint=self.endpoint,
                total_sent=50 + i,
                success_count=45 + i,
                failed_count=5,
                avg_latency_ms=140.0 + i * 2,
                success_rate=90.0 + i,
                created_by=self.user,
            )
        
        # Test aggregation
        from django.db.models import Sum, Avg
        aggregated = WebhookAnalytics.objects.filter(
            endpoint=self.endpoint
        ).aggregate(
            total_sent=Sum('total_sent'),
            success_count=Sum('success_count'),
            failed_count=Sum('failed_count'),
            avg_latency_ms=Avg('avg_latency_ms'),
        )
        
        self.assertEqual(aggregated['total_sent__sum'], 275)
        self.assertEqual(aggregated['success_count__sum'], 245)
        self.assertEqual(aggregated['failed_count__sum'], 25)
        self.assertEqual(aggregated['avg_latency_ms__avg'], 150.0)


class WebhookHealthLogModelTest(TestCase):
    """Test cases for WebhookHealthLog model."""
    
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
    
    def test_health_log_creation(self):
        """Test health log creation."""
        health_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            is_healthy=True,
            response_time_ms=150,
            status_code=200,
            created_by=self.user,
        )
        
        self.assertEqual(health_log.endpoint, self.endpoint)
        self.assertTrue(health_log.is_healthy)
        self.assertEqual(health_log.response_time_ms, 150)
        self.assertEqual(health_log.status_code, 200)
    
    def test_health_log_failure(self):
        """Test health log failure."""
        health_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            is_healthy=False,
            response_time_ms=5000,
            status_code=500,
            error='Connection timeout',
            created_by=self.user,
        )
        
        self.assertEqual(health_log.endpoint, self.endpoint)
        self.assertFalse(health_log.is_healthy)
        self.assertEqual(health_log.response_time_ms, 5000)
        self.assertEqual(health_log.status_code, 500)
        self.assertEqual(health_log.error, 'Connection timeout')
    
    def test_health_log_auto_suspend(self):
        """Test automatic suspension logic."""
        # This would be tested with the actual HealthMonitorService
        # For now, just test the model behavior
        endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret',
            status=WebhookStatus.SUSPENDED,
            created_by=self.user,
        )
        
        # Create health logs showing unhealthy status
        for i in range(3):
            WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=False,
                response_time_ms=1000 + i * 100,
                status_code=500,
                error=f'Health check {i + 1} failed',
                created_by=self.user,
            )
        
        self.assertEqual(endpoint.status, WebhookStatus.SUSPENDED)
        self.assertEqual(WebhookHealthLog.objects.filter(endpoint=endpoint, is_healthy=False).count(), 3)


class WebhookReplayModelTest(TestCase):
    """Test cases for WebhookReplay model."""
    
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
                created_by=self.user,
            )
            self.delivery_logs.append(log)
    
    def test_replay_creation(self):
        """Test replay creation."""
        replay = WebhookReplay.objects.create(
            original_log=self.delivery_logs[0],
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
            created_by=self.user,
        )
        
        self.assertEqual(replay.original_log, self.delivery_logs[0])
        self.assertEqual(replay.replayed_by, self.user)
        self.assertEqual(replay.reason, 'Test replay')
        self.assertEqual(replay.status, ReplayStatus.PENDING)
    
    def test_replay_completion(self):
        """Test replay completion."""
        replay = WebhookReplay.objects.create(
            original_log=self.delivery_logs[0],
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.COMPLETED,
            replayed_at=timezone.now(),
            created_by=self.user,
        )
        
        self.assertEqual(replay.status, ReplayStatus.COMPLETED)
        self.assertIsNotNone(replay.replayed_at)
    
    def test_replay_batch_creation(self):
        """Test replay batch creation."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date(),
            date_to=timezone.now().date() + timezone.timedelta(days=1),
            count=10,
            status=ReplayStatus.PENDING,
        )
        
        self.assertEqual(batch.event_type, 'user.created')
        self.assertEqual(batch.count, 10)
        self.assertEqual(batch.status, ReplayStatus.PENDING)
        self.assertEqual(batch.created_by, self.user)
