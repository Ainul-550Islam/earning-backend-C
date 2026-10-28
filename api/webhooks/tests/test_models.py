"""Test Models for Webhooks System

This module contains tests for all webhook models
including core models, advanced features, analytics, and replay functionality.
"""

from datetime import timedelta
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from unittest.mock import Mock, patch

from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem,
    WebhookBatchItem
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)
from ..services.core.TemplateEngine import TemplateEngine

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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
            label='Test Endpoint',
        )
        
        # Real __str__ (models/core.py) is "[STATUS] label -> target_url",
        # not the bare URL - confirmed by direct instantiation.
        self.assertEqual(str(endpoint), '[ACTIVE] Test Endpoint -> https://example.com/webhook')
        # endpoint.status holds the raw stored value ('active'); 'Active' is
        # only the choices display label (endpoint.get_status_display()).
        self.assertEqual(endpoint.status, WebhookStatus.ACTIVE)
    
    def test_url_validation(self):
        """Test URL validation."""
        # .objects.create() never calls full_clean() - Django doesn't do
        # this automatically on save (confirmed empirically). Model-level
        # validators (validate_webhook_url + URLValidator, see CORE-01 in
        # models/core.py) only run via an explicit full_clean() call, which
        # is the real way this model's own validation gets exercised.
        endpoint = WebhookEndpoint(
            target_url='invalid-url',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
            label='Invalid URL Test',
        )
        with self.assertRaises(Exception):
            endpoint.full_clean()
    
    def test_secret_rotation(self):
        """Test secret rotation."""
        # The real field is secret_key (EncryptedCharField) - WebhookEndpoint
        # has no "secret" attribute at all (confirmed empirically). Rotation
        # also isn't manual assignment: the model's own rotate_secret()
        # always auto-generates a new secret and returns it; the caller
        # saves. Testing the real mechanism instead of a fictional one.
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        old_secret = endpoint.secret_key
        new_secret = endpoint.rotate_secret()
        endpoint.save()
        endpoint.refresh_from_db()
        
        self.assertEqual(endpoint.secret_key, new_secret)
        self.assertNotEqual(endpoint.secret_key, old_secret)
    
    def test_rate_limit_configuration(self):
        """Test rate limit configuration."""
        # rate_limit_per_min is not a field on WebhookEndpoint - it belonged
        # to the old flat model (see WebhookEndpointSerializer's SER-01 fix
        # comment: "Removed: timeout_seconds, ip_whitelist,
        # rate_limit_per_min... (not on model)"). Rate limiting is now a
        # separate, real, actively-used WebhookRateLimit row related to the
        # endpoint - testing its actual defaults instead of a phantom field.
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        rate_limit = WebhookRateLimit.objects.create(endpoint=endpoint)
        
        self.assertEqual(rate_limit.max_requests, 1000)
        self.assertEqual(rate_limit.window_seconds, 3600)
        self.assertEqual(rate_limit.endpoint, endpoint)
    
    def test_endpoint_has_no_ip_whitelist_field(self):
        """WebhookEndpoint has no ip_whitelist concept - documenting the
        boundary rather than asserting a phantom field.

        ip_whitelist is real, but lives on InboundWebhook (models/inbound.py)
        for validating the source of inbound payloads (bKash/Nagad/Stripe
        etc.) - a different direction entirely from an outbound
        WebhookEndpoint. Same class of finding as test_dispatch_service.py's
        test_emit_webhook_has_no_ip_whitelist_concept from Session 7,
        confirmed via the same removed-field trail documented in
        WebhookEndpointSerializer's SER-01 comment.
        """
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        self.assertFalse(hasattr(endpoint, 'ip_whitelist'))
    
    def test_status_transitions(self):
        """Test status transitions."""
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        
        # Test pause
        endpoint.status = WebhookStatus.PAUSED
        endpoint.save()
        endpoint.refresh_from_db()
        self.assertEqual(endpoint.status, WebhookStatus.PAUSED)
        
        # Test resume
        endpoint.status = WebhookStatus.ACTIVE
        endpoint.save()
        endpoint.refresh_from_db()
        
        # endpoint.status holds the raw stored value ('active'), not the
        # choices display label ('Active') - same fix as test_str_representation.
        self.assertEqual(endpoint.status, WebhookStatus.ACTIVE)
    
    def test_deletion(self):
        """Test endpoint deletion."""
        endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_subscription_creation(self):
        """Test subscription creation."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        
        self.assertEqual(subscription.endpoint, self.endpoint)
        self.assertEqual(subscription.event_type, 'user.created')
        self.assertTrue(subscription.is_active)
        # filters defaults to {} (models/core.py's _empty_dict) when not
        # explicitly provided - confirmed empirically. {'user_id': 12345}
        # was never written anywhere in the create() call above.
        self.assertEqual(subscription.filters, {})
    
    def test_filter_configuration(self):
        """Test filter configuration."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            filters={
                'field_path': 'user.email',
                'operator': FilterOperator.EQUALS,
                'value': '@example.com',
            },
            is_active=True,
        )
        
        self.assertEqual(subscription.filters['field_path'], 'user.email')
        self.assertEqual(subscription.filters['operator'], FilterOperator.EQUALS)
        self.assertEqual(subscription.filters['value'], '@example.com')
    
    def test_subscription_deactivation(self):
        """Test subscription deactivation."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        
        subscription.is_active = False
        subscription.save()
        
        self.assertFalse(subscription.is_active)
    
    def test_subscription_deletion(self):
        """Test subscription deletion."""
        subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_delivery_log_creation(self):
        """Test delivery log creation."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
            response_body='{"status": "success"}',
            response_time_ms=150,
            attempt_number=1,
        )
        
        self.assertEqual(log.endpoint, self.endpoint)
        self.assertEqual(log.event_type, 'user.created')
        self.assertEqual(log.status, DeliveryStatus.SUCCESS)
        self.assertEqual(log.http_status_code, 200)
        self.assertEqual(log.attempt_number, 1)
    
    def test_retry_logic(self):
        """Test retry logic."""
        log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            http_status_code=500,
            response_body='{"error": "Server error"}',
            attempt_number=1,
        )
        
        # Test retry
        retry_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.RETRYING,
            http_status_code=500,
            response_body='{"error": "Server error"}',
            attempt_number=2,
            next_retry_at=timezone.now() + timedelta(minutes=5),
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
            http_status_code=200,
            response_body='{"status": "success"}',
            response_time_ms=100,
            attempt_number=1,
        )
        
        self.assertEqual(log.status, DeliveryStatus.SUCCESS)
        self.assertEqual(log.http_status_code, 200)
        self.assertEqual(log.response_time_ms, 100)
    
    def test_log_ordering(self):
        """Test log ordering."""
        # Create multiple logs
        for i in range(5):
            WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345},
                status=DeliveryStatus.SUCCESS,
                http_status_code=200,
                response_time_ms=100 + i,
                attempt_number=i + 1,
            )
        
        # Test ordering
        logs = WebhookDeliveryLog.objects.filter(endpoint=self.endpoint)
        self.assertEqual(logs.count(), 5)
        
        # Check they're ordered by created_at (newest first)
        for i, log in enumerate(logs):
            self.assertEqual(log.response_time_ms, 100 + (4 - i))


class WebhookFilterModelTest(TestCase):
    """Test cases for WebhookFilter model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_filter_creation(self):
        """Test filter creation."""
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='@example.com',
            is_active=True,
        )
        
        self.assertEqual(filter_obj.endpoint, self.endpoint)
        self.assertEqual(filter_obj.field_path, 'user.email')
        self.assertEqual(filter_obj.operator, FilterOperator.EQUALS)
        self.assertEqual(filter_obj.value, '@example.com')
        self.assertTrue(filter_obj.is_active)
    
    def test_filter_evaluation(self):
        """Test filter evaluation logic."""
        from ..services.filtering import FilterService
        
        filter_service = FilterService()
        
        # Test equals operator
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.EQUALS,
            value='test@example.com',
            is_active=True,
        )
        
        # EQUALS needs an exact match - '@example.com' (partial) can never
        # equal a full email address (confirmed empirically: evaluates
        # False). Looks like a copy/paste from a CONTAINS-style filter.
        event_data = {'user_email': 'test@example.com'}
        result = filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_complex_filter(self):
        """Test complex filter with nested fields."""
        from ..services.filtering import FilterService
        
        filter_service = FilterService()
        
        # Test contains operator on nested field
        filter_obj = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='profile.settings.notifications.email',
            operator=FilterOperator.CONTAINS,
            value='marketing',
            is_active=True,
        )
        
        # 'marketing' must actually appear in the nested value for CONTAINS
        # to match - the original fixture email ('test@example.com')
        # contained no such substring (confirmed empirically: evaluates
        # False). This still exercises the same 4-level nested traversal.
        event_data = {
            'profile': {
                'settings': {
                    'notifications': {
                        'email': 'marketing@example.com'
                    }
                }
            }
        }
        
        result = filter_service.evaluate_filter(filter_obj, event_data)
        
        self.assertTrue(result)
    
    def test_filter_validation(self):
        """Test filter validation."""
        # Same root cause as WebhookEndpointModelTest.test_url_validation:
        # .create() doesn't invoke clean()/validators - full_clean() is the
        # real way to exercise WebhookFilter.clean()'s field_path check
        # (ADV-01), confirmed empirically.
        filter_obj = WebhookFilter(
            endpoint=self.endpoint,
            field_path='',  # Invalid: empty field path
            operator=FilterOperator.EQUALS,
            value='test',
            is_active=True,
        )
        with self.assertRaises(Exception):
            filter_obj.full_clean()


class WebhookBatchModelTest(TestCase):
    """Test cases for WebhookBatch model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_batch_creation(self):
        """Test batch creation."""
        batch = WebhookBatch.objects.create(
            batch_id='TEST-BATCH-001',
            endpoint=self.endpoint,
            event_count=100,
            status=BatchStatus.PENDING,
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
        )
        
        # Create delivery logs
        delivery_logs = []
        for i in range(10):
            log = WebhookDeliveryLog.objects.create(
                endpoint=self.endpoint,
                event_type='user.created',
                payload={'user_id': 12345 + i},
                status=DeliveryStatus.SUCCESS,
                http_status_code=200,
                attempt_number=1,
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
            payload_template='{"user_id": {{user_id}}, "user_email": {{user_email}}, "created_at": {{created_at}}}',
            is_active=True,
        )
        
        engine = TemplateEngine()
        
        event_data = {
            'user_id': 12345,
            'user_email': 'test@example.com',
            'created_at': '2024-01-01T00:00:00Z',
        }
        
        rendered_payload = engine.render_template(template, event_data)
        
        self.assertIn('user_id', rendered_payload)
        self.assertIn('user_email', rendered_payload)
        self.assertIn('created_at', rendered_payload)
    
    def test_transformation_rules(self):
        """Test transformation rules."""
        template = WebhookTemplate.objects.create(
            name='Transformation Test',
            event_type='user.created',
            payload_template='{"email": "{{user_email}}"}',
            transform_rules={'format_email': {'type': 'upper', 'field': 'email'}},
            is_active=True,
        )
        self.assertIsNotNone(template)
        self.assertEqual(template.name, 'Transformation Test')

class WebhookAnalyticsModelTest(TestCase):
    """Test cases for WebhookAnalytics model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
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
        )
        
        self.assertEqual(analytics.endpoint, self.endpoint)
        self.assertEqual(analytics.total_sent, 100)
        self.assertEqual(analytics.success_count, 95)
        self.assertEqual(analytics.failed_count, 5)
        self.assertEqual(analytics.success_rate, 95.0)
    
    def test_analytics_aggregation(self):
        """Test analytics aggregation."""
        # Create analytics for multiple days
        dates = [timezone.now().date() - timedelta(days=i) for i in range(5)]
        
        for i, date in enumerate(dates):
            WebhookAnalytics.objects.create(
                date=date,
                endpoint=self.endpoint,
                total_sent=50 + i,
                success_count=45 + i,
                failed_count=5,
                avg_latency_ms=140.0 + i * 2,
                success_rate=90.0 + i,
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
        
        # total_sent: 50+51+52+53+54=260; success_count: 45+46+47+48+49=235;
        # avg_latency_ms: mean(140,142,144,146,148)=144.0 - the original
        # expected values (275/245/150.0) didn't match the fixture data
        # created above (verified by hand and empirically; failed_count's
        # 25 was already correct, which is why only 3 of 4 needed fixing).
        self.assertEqual(aggregated['total_sent'], 260)
        self.assertEqual(aggregated['success_count'], 235)
        self.assertEqual(aggregated['failed_count'], 25)
        self.assertEqual(aggregated['avg_latency_ms'], 144.0)


class WebhookHealthLogModelTest(TestCase):
    """Test cases for WebhookHealthLog model."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_health_log_creation(self):
        """Test health log creation."""
        health_log = WebhookHealthLog.objects.create(
            endpoint=self.endpoint,
            is_healthy=True,
            response_time_ms=150,
            status_code=200,
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
            target_url='https://example.com/webhook',
            secret_key='test-secret',
            status=WebhookStatus.SUSPENDED,
            owner=self.user,
        )
        
        # Create health logs showing unhealthy status
        for i in range(3):
            WebhookHealthLog.objects.create(
                endpoint=endpoint,
                is_healthy=False,
                response_time_ms=1000 + i * 100,
                status_code=500,
                error=f'Health check {i + 1} failed',
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
                    target_url='https://example.com/webhook',
                    secret_key='test-secret',
                    status=WebhookStatus.ACTIVE,
                    owner=self.user,
                ),
                event_type='user.created',
                payload={'user_id': 1000 + i},
                status=DeliveryStatus.SUCCESS,
                http_status_code=200,
                attempt_number=1,
            )
            self.delivery_logs.append(log)
    
    def test_replay_creation(self):
        """Test replay creation."""
        replay = WebhookReplay.objects.create(
            original_log=self.delivery_logs[0],
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
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
        )
        
        self.assertEqual(replay.status, ReplayStatus.COMPLETED)
        self.assertIsNotNone(replay.replayed_at)
    
    def test_replay_batch_creation(self):
        """Test replay batch creation."""
        batch = WebhookReplayBatch.objects.create(
            created_by=self.user,
            event_type='user.created',
            date_from=timezone.now().date(),
            date_to=timezone.now().date() + timedelta(days=1),
            count=10,
            status=ReplayStatus.PENDING,
        )
        
        self.assertEqual(batch.event_type, 'user.created')
        self.assertEqual(batch.count, 10)
        self.assertEqual(batch.status, ReplayStatus.PENDING)
        self.assertEqual(batch.created_by, self.user)