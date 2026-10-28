"""Test Serializers for Webhooks System

This module contains tests for the webhook serializers
including data validation, serialization, and deserialization.
"""

import pytest
from datetime import timedelta
from unittest.mock import Mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from ..serializers import (
    WebhookEndpointSerializer, WebhookSubscriptionSerializer,
    WebhookDeliveryLogSerializer, WebhookFilterSerializer,
    WebhookTemplateSerializer, WebhookBatchSerializer,
    WebhookSecretSerializer, WebhookAnalyticsSerializer,
    WebhookHealthSerializer, WebhookReplaySerializer,
    WebhookEmitSerializer, WebhookEventTypeSerializer
)
from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    WebhookAnalytics, WebhookHealthLog, WebhookReplay
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus
)

User = get_user_model()


class WebhookEndpointSerializerTest(TestCase):
    """Test cases for WebhookEndpointSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.serializer = WebhookEndpointSerializer(instance=self.endpoint)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'label', 'target_url', 'http_method', 'status',
            'custom_headers', 'description', 'version', 'payload_template',
            'max_retries', 'verify_ssl', 'total_deliveries', 'success_deliveries',
            'failed_deliveries', 'success_rate', 'last_triggered_at',
            'suspension_reason', 'created_at', 'updated_at',
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['target_url'], self.endpoint.target_url)
        self.assertEqual(data['status'], self.endpoint.status)
        self.assertEqual(data['http_method'], self.endpoint.http_method)
        self.assertEqual(data['max_retries'], self.endpoint.max_retries)
        self.assertEqual(data['verify_ssl'], self.endpoint.verify_ssl)
        self.assertEqual(data['custom_headers'], self.endpoint.custom_headers)
        self.assertEqual(data['total_deliveries'], self.endpoint.total_deliveries)
        self.assertEqual(data['success_deliveries'], self.endpoint.success_deliveries)
        self.assertEqual(data['failed_deliveries'], self.endpoint.failed_deliveries)
    
    def test_create_endpoint_valid_data(self):
        """Test creating endpoint with valid data."""
        data = {
            'target_url': 'https://example.com/new-webhook',
            'http_method': HttpMethod.POST,
            'max_retries': 3,
            'verify_ssl': True,
            'custom_headers': {'Content-Type': 'application/json'},
            'label': 'Test Webhook',
            'description': 'Test webhook description'
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        endpoint = serializer.save(owner=self.user)
        self.assertEqual(endpoint.target_url, data['target_url'])
        self.assertEqual(endpoint.http_method, data['http_method'])
        self.assertEqual(endpoint.max_retries, data['max_retries'])
        self.assertEqual(endpoint.verify_ssl, data['verify_ssl'])
        self.assertEqual(endpoint.custom_headers, data['custom_headers'])
        self.assertEqual(endpoint.label, data['label'])
        self.assertEqual(endpoint.description, data['description'])
    
    def test_create_endpoint_invalid_url(self):
        """Test creating endpoint with invalid URL."""
        data = {
            'target_url': 'invalid-url',
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_url', serializer.errors)
    
    def test_status_field_is_read_only(self):
        """status isn't writable through this serializer — status changes
        go through the dedicated pause/resume actions instead, so a bad
        value here is silently ignored rather than raising a validation
        error (this replaces a prior version of this test that assumed
        status was a plain writable field with choice validation)."""
        data = {
            'target_url': 'https://example.com/webhook',
            'label': 'Test Webhook',
            'status': 'invalid-status',
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        endpoint = serializer.save(owner=self.user)
        self.assertEqual(endpoint.status, WebhookStatus.ACTIVE)  # model default, input ignored
    
    def test_create_endpoint_invalid_http_method(self):
        """Test creating endpoint with invalid HTTP method."""
        data = {
            'target_url': 'https://example.com/webhook',
            'http_method': 'INVALID'
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('http_method', serializer.errors)
    
    def test_create_endpoint_invalid_max_retries(self):
        """Test creating endpoint with invalid max retries."""
        data = {
            'target_url': 'https://example.com/webhook',
            'label': 'Test Webhook',
            'max_retries': -1
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('max_retries', serializer.errors)
    
    def test_update_endpoint_valid_data(self):
        """Test updating endpoint with valid data."""
        data = {
            'max_retries': 5,
            'verify_ssl': False,
        }
        
        serializer = WebhookEndpointSerializer(
            instance=self.endpoint,
            data=data,
            partial=True
        )
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        updated_endpoint = serializer.save()
        self.assertEqual(updated_endpoint.max_retries, data['max_retries'])
        self.assertEqual(updated_endpoint.verify_ssl, data['verify_ssl'])
    
    def test_validate_headers_valid(self):
        """Test custom_headers validation with valid data."""
        data = {
            'target_url': 'https://example.com/webhook',
            'label': 'Test Webhook',
            'custom_headers': {
                'Content-Type': 'application/json',
                'X-Custom-Header': 'custom-value'
            }
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
    
    def test_validate_headers_invalid_value(self):
        """Test custom_headers validation with invalid value type."""
        data = {
            'target_url': 'https://example.com/webhook',
            'custom_headers': {
                'Content-Type': 123  # Invalid type
            }
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('custom_headers', serializer.errors)


class WebhookSubscriptionSerializerTest(TestCase):
    """Test cases for WebhookSubscriptionSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
        )
        self.serializer = WebhookSubscriptionSerializer(instance=self.subscription)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'event_type', 'is_active',
            'filters', 'created_at', 'updated_at'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.subscription.endpoint.id)
        self.assertEqual(data['event_type'], self.subscription.event_type)
        self.assertEqual(data['is_active'], self.subscription.is_active)
        self.assertEqual(data['filters'], self.subscription.filters)
    
    def test_create_subscription_valid_data(self):
        """Test creating subscription with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.updated',
            'is_active': True,
            'filters': {
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                }
            }
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        subscription = serializer.save()
        self.assertEqual(subscription.endpoint.id, data['endpoint'])
        self.assertEqual(subscription.event_type, data['event_type'])
        self.assertEqual(subscription.is_active, data['is_active'])
        self.assertEqual(subscription.filters, data['filters'])
    
    def test_create_subscription_invalid_endpoint(self):
        """Test creating subscription with invalid endpoint."""
        data = {
            'endpoint': 99999,  # Non-existent endpoint
            'event_type': 'user.created',
            'is_active': True
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('endpoint', serializer.errors)
    
    def test_create_subscription_invalid_event_type(self):
        """Test creating subscription with invalid event type."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': '',  # Empty event type
            'is_active': True
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_type', serializer.errors)
    
    def test_validate_filter_config_valid(self):
        """Test filters validation with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.updated',
            'filters': {
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                },
                'user.status': {
                    'operator': 'equals',
                    'value': 'active'
                }
            }
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
    
    def test_validate_filter_config_invalid_structure(self):
        """Test filters validation with invalid structure."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'filters': 'invalid-string'  # Should be dict
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('filters', serializer.errors)


class WebhookDeliveryLogSerializerTest(TestCase):
    """Test cases for WebhookDeliveryLogSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.SUCCESS,
            http_status_code=200,
            response_body='{"status": "success"}',
            response_time_ms=150,
            attempt_number=1,
            max_attempts=3,
        )
        self.serializer = WebhookDeliveryLogSerializer(instance=self.delivery_log)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'endpoint_label', 'endpoint_url', 'event_type',
            'payload', 'request_headers', 'signature', 'http_status_code',
            'response_body', 'response_time_ms', 'error_message', 'status',
            'attempt_number', 'max_attempts', 'next_retry_at', 'dispatched_at',
            'completed_at', 'created_at', 'updated_at'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.delivery_log.endpoint.id)
        self.assertEqual(data['event_type'], self.delivery_log.event_type)
        self.assertEqual(data['payload'], self.delivery_log.payload)
        self.assertEqual(data['status'], self.delivery_log.status)
        self.assertEqual(data['http_status_code'], self.delivery_log.http_status_code)
        self.assertEqual(data['response_body'], self.delivery_log.response_body)
        self.assertEqual(data['response_time_ms'], self.delivery_log.response_time_ms)
        self.assertEqual(data['attempt_number'], self.delivery_log.attempt_number)
        self.assertEqual(data['max_attempts'], self.delivery_log.max_attempts)
    
    def test_create_delivery_log_valid_data(self):
        """Test creating delivery log with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.updated',
            'payload': {'user_id': 12346, 'email': 'updated@example.com'},
            'status': DeliveryStatus.SUCCESS,
            'http_status_code': 200,
            'response_body': '{"status": "success"}',
            'response_time_ms': 200,
            'attempt_number': 1,
            'max_attempts': 3
        }
        
        serializer = WebhookDeliveryLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        delivery_log = serializer.save()
        self.assertEqual(delivery_log.endpoint.id, data['endpoint'])
        self.assertEqual(delivery_log.event_type, data['event_type'])
        self.assertEqual(delivery_log.payload, data['payload'])
        self.assertEqual(delivery_log.status, data['status'])
        self.assertEqual(delivery_log.http_status_code, data['http_status_code'])
        self.assertEqual(delivery_log.response_body, data['response_body'])
        self.assertEqual(delivery_log.response_time_ms, data['response_time_ms'])
        self.assertEqual(delivery_log.attempt_number, data['attempt_number'])
        self.assertEqual(delivery_log.max_attempts, data['max_attempts'])
    
    def test_create_delivery_log_invalid_status(self):
        """Test creating delivery log with invalid status."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'status': 'invalid-status'
        }
        
        serializer = WebhookDeliveryLogSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)
    
    def test_validate_payload_valid_json(self):
        """Test payload validation with valid JSON."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'payload': {'user_id': 12345, 'email': 'test@example.com'},
            'status': DeliveryStatus.SUCCESS
        }
        
        serializer = WebhookDeliveryLogSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_payload_invalid_json(self):
        """Test payload validation with invalid JSON."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'payload': 'invalid-json-string',
            'status': DeliveryStatus.SUCCESS
        }
        
        serializer = WebhookDeliveryLogSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('payload', serializer.errors)


class WebhookFilterSerializerTest(TestCase):
    """Test cases for WebhookFilterSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.filter = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
        )
        self.serializer = WebhookFilterSerializer(instance=self.filter)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'endpoint_name', 'field_path', 'operator',
            'value', 'is_active', 'created_at', 'updated_at'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.filter.endpoint.id)
        self.assertEqual(data['field_path'], self.filter.field_path)
        self.assertEqual(data['operator'], self.filter.operator)
        self.assertEqual(data['value'], self.filter.value)
        self.assertEqual(data['is_active'], self.filter.is_active)
    
    def test_create_filter_valid_data(self):
        """Test creating filter with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': 'user.status',
            'operator': FilterOperator.EQUALS,
            'value': 'active',
            'is_active': True
        }
        
        serializer = WebhookFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        webhook_filter = serializer.save()
        self.assertEqual(webhook_filter.endpoint.id, data['endpoint'])
        self.assertEqual(webhook_filter.field_path, data['field_path'])
        self.assertEqual(webhook_filter.operator, data['operator'])
        self.assertEqual(webhook_filter.value, data['value'])
        self.assertEqual(webhook_filter.is_active, data['is_active'])
    
    def test_create_filter_invalid_operator(self):
        """Test creating filter with invalid operator."""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': 'user.email',
            'operator': 'invalid-operator',
            'value': '@example.com'
        }
        
        serializer = WebhookFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('operator', serializer.errors)
    
    def test_validate_field_path_valid(self):
        """Test field path validation with valid path."""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': 'user.email',
            'operator': FilterOperator.CONTAINS,
            'value': '@example.com'
        }
        
        serializer = WebhookFilterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_field_path_invalid(self):
        """Test field path validation with invalid path."""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': '',  # Empty field path
            'operator': FilterOperator.CONTAINS,
            'value': '@example.com'
        }
        
        serializer = WebhookFilterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('field_path', serializer.errors)


class WebhookEmitSerializerTest(TestCase):
    """Test cases for WebhookEmitSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345, 'email': 'test@example.com'},
            'endpoint_id': self.endpoint.id
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        expected_fields = {
            'event_type', 'payload', 'endpoint_id', 'async_emit'
        }
        
        self.assertEqual(set(serializer.validated_data.keys()), expected_fields)
    
    def test_validate_emit_data_valid(self):
        """Test emit data validation with valid data."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345, 'email': 'test@example.com'},
            'endpoint_id': self.endpoint.id,
            'async_emit': False
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_emit_data_missing_event_type(self):
        """Test emit data validation with missing event type."""
        data = {
            'payload': {'user_id': 12345},
            'endpoint_id': self.endpoint.id
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_type', serializer.errors)
    
    def test_validate_emit_data_missing_payload(self):
        """Test emit data validation with missing payload."""
        data = {
            'event_type': 'user.created',
            'endpoint_id': self.endpoint.id
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('payload', serializer.errors)
    
    def test_validate_emit_data_missing_endpoint(self):
        """Test emit data validation with missing endpoint."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345}
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('endpoint_id', serializer.errors)
    
    def test_validate_emit_data_invalid_endpoint(self):
        """Test emit data validation with invalid endpoint."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': 99999  # Non-existent endpoint
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('endpoint_id', serializer.errors)
    
    def test_validate_payload_valid_json(self):
        """Test payload validation with valid JSON."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345, 'email': 'test@example.com'},
            'endpoint_id': self.endpoint.id
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_payload_invalid_json(self):
        """Test payload validation with invalid JSON."""
        data = {
            'event_type': 'user.created',
            'payload': 'invalid-json-string',
            'endpoint_id': self.endpoint.id
        }
        
        serializer = WebhookEmitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('payload', serializer.errors)


class WebhookEventTypeSerializerTest(TestCase):
    """Test cases for WebhookEventTypeSerializer."""
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = {
            'event_types': ['user.created', 'user.updated', 'user.deleted']
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        expected_fields = {
            'event_types'
        }
        
        self.assertEqual(set(serializer.validated_data.keys()), expected_fields)
    
    def test_validate_event_types_valid(self):
        """Test event types validation with valid data."""
        data = {
            'event_types': ['user.created', 'user.updated', 'user.deleted']
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['event_types'], data['event_types'])
    
    def test_validate_event_types_empty_list(self):
        """Test event types validation rejects an empty list."""
        data = {
            'event_types': []
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_types', serializer.errors)
    
    def test_validate_event_types_invalid_type(self):
        """Test event types validation with invalid type."""
        data = {
            'event_types': 'user.created'  # Should be list
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_types', serializer.errors)
    
    def test_validate_event_types_invalid_event_type(self):
        """Test event types validation with a malformed event type (no domain.event dot)."""
        data = {
            'event_types': ['invalideventtype']
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_types', serializer.errors)


class WebhookAnalyticsSerializerTest(TestCase):
    """Test cases for WebhookAnalyticsSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.analytics = WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date(),
            total_sent=100,
            success_count=95,
            failed_count=5,
            avg_latency_ms=150.0,
            success_rate=95.0,
        )
        self.serializer = WebhookAnalyticsSerializer(instance=self.analytics)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'date', 'total_sent', 'success_count',
            'failed_count', 'avg_latency_ms', 'success_rate',
            'created_at', 'updated_at', 'failure_rate', 'performance_rating'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.analytics.endpoint.id)
        self.assertEqual(data['date'], self.analytics.date.isoformat())
        self.assertEqual(data['total_sent'], self.analytics.total_sent)
        self.assertEqual(data['success_count'], self.analytics.success_count)
        self.assertEqual(data['failed_count'], self.analytics.failed_count)
        self.assertEqual(data['avg_latency_ms'], self.analytics.avg_latency_ms)
        self.assertEqual(data['success_rate'], self.analytics.success_rate)
    
    def test_create_analytics_valid_data(self):
        """Test creating analytics with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'date': timezone.now().date() - timedelta(days=1),
            'total_sent': 200,
            'success_count': 190,
            'failed_count': 10,
            'avg_latency_ms': 200.0,
            'success_rate': 95.0
        }
        
        serializer = WebhookAnalyticsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        analytics = serializer.save()
        self.assertEqual(analytics.endpoint.id, data['endpoint'])
        self.assertEqual(analytics.date, data['date'])
        self.assertEqual(analytics.total_sent, data['total_sent'])
        self.assertEqual(analytics.success_count, data['success_count'])
        self.assertEqual(analytics.failed_count, data['failed_count'])
        self.assertEqual(analytics.avg_latency_ms, data['avg_latency_ms'])
        self.assertEqual(analytics.success_rate, data['success_rate'])
    
    def test_create_analytics_invalid_success_rate(self):
        """Test creating analytics with invalid success rate."""
        data = {
            'endpoint': self.endpoint.id,
            'date': timezone.now().date(),
            'total_sent': 100,
            'success_count': 50,
            'failed_count': 50,
            'success_rate': 150.0  # Invalid percentage
        }
        
        serializer = WebhookAnalyticsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('success_rate', serializer.errors)


class WebhookReplaySerializerTest(TestCase):
    """Test cases for WebhookReplaySerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            target_url='https://example.com/webhook',
            secret_key='test-secret-key',
            status=WebhookStatus.ACTIVE,
            owner=self.user,
        )
        self.original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
        )
        self.replay = WebhookReplay.objects.create(
            original_log=self.original_log,
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
        )
        self.serializer = WebhookReplaySerializer(instance=self.replay)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'original_log', 'original_log_endpoint_label',
            'original_log_event_type', 'replayed_by', 'replayed_by_username',
            'new_log', 'reason', 'status', 'replayed_at', 'created_at',
            'updated_at'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['original_log'], self.replay.original_log.id)
        self.assertEqual(data['replayed_by'], self.replay.replayed_by.id)
        self.assertEqual(data['reason'], self.replay.reason)
        self.assertEqual(data['status'], self.replay.status)
        self.assertIsNone(data['new_log'])
        self.assertIsNone(data['replayed_at'])
    
    def test_create_replay_valid_data(self):
        """Test creating replay with valid data. replayed_by/new_log are
        deliberately read-only on this serializer (see Meta.read_only_fields)
        — the caller doesn't get to backdate who replayed something or
        which log it produced, so those are set explicitly via save(),
        not through the input data."""
        data = {
            'original_log': self.original_log.id,
            'reason': 'Test replay 2',
            'status': ReplayStatus.COMPLETED,
        }
        
        serializer = WebhookReplaySerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
        new_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
        )
        replay = serializer.save(replayed_by=self.user, new_log=new_log)
        self.assertEqual(replay.original_log.id, data['original_log'])
        self.assertEqual(replay.replayed_by.id, self.user.id)
        self.assertEqual(replay.reason, data['reason'])
        self.assertEqual(replay.status, data['status'])
        self.assertEqual(replay.new_log.id, new_log.id)
    
    def test_create_replay_invalid_status(self):
        """Test creating replay with invalid status."""
        data = {
            'original_log': self.original_log.id,
            'replayed_by': self.user.id,
            'reason': 'Test replay',
            'status': 'invalid-status'
        }
        
        serializer = WebhookReplaySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)


# Additional serializer tests can be added here for the remaining serializers
# (WebhookTemplateSerializer, WebhookBatchSerializer, etc.)