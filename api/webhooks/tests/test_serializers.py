"""Test Serializers for Webhooks System

This module contains tests for the webhook serializers
including data validation, serialization, and deserialization.
"""

import pytest
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.serializer = WebhookEndpointSerializer(instance=self.endpoint)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'url', 'status', 'http_method', 'timeout_seconds',
            'max_retries', 'verify_ssl', 'ip_whitelist', 'headers',
            'rate_limit_per_min', 'payload_template', 'created_at',
            'updated_at', 'total_deliveries', 'success_deliveries',
            'failed_deliveries', 'last_triggered_at', 'owner',
            'tenant', 'label', 'description', 'version'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['url'], self.endpoint.url)
        self.assertEqual(data['status'], self.endpoint.status)
        self.assertEqual(data['http_method'], self.endpoint.http_method)
        self.assertEqual(data['timeout_seconds'], self.endpoint.timeout_seconds)
        self.assertEqual(data['max_retries'], self.endpoint.max_retries)
        self.assertEqual(data['verify_ssl'], self.endpoint.verify_ssl)
        self.assertEqual(data['ip_whitelist'], self.endpoint.ip_whitelist)
        self.assertEqual(data['headers'], self.endpoint.headers)
        self.assertEqual(data['rate_limit_per_min'], self.endpoint.rate_limit_per_min)
        self.assertEqual(data['total_deliveries'], self.endpoint.total_deliveries)
        self.assertEqual(data['success_deliveries'], self.endpoint.success_deliveries)
        self.assertEqual(data['failed_deliveries'], self.endpoint.failed_deliveries)
    
    def test_create_endpoint_valid_data(self):
        """Test creating endpoint with valid data."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'new-secret-key',
            'status': WebhookStatus.ACTIVE,
            'http_method': HttpMethod.POST,
            'timeout_seconds': 30,
            'max_retries': 3,
            'verify_ssl': True,
            'ip_whitelist': ['192.168.1.1', '10.0.0.1'],
            'headers': {'Content-Type': 'application/json'},
            'rate_limit_per_min': 1000,
            'label': 'Test Webhook',
            'description': 'Test webhook description'
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        endpoint = serializer.save()
        self.assertEqual(endpoint.url, data['url'])
        self.assertEqual(endpoint.status, data['status'])
        self.assertEqual(endpoint.http_method, data['http_method'])
        self.assertEqual(endpoint.timeout_seconds, data['timeout_seconds'])
        self.assertEqual(endpoint.max_retries, data['max_retries'])
        self.assertEqual(endpoint.verify_ssl, data['verify_ssl'])
        self.assertEqual(endpoint.ip_whitelist, data['ip_whitelist'])
        self.assertEqual(endpoint.headers, data['headers'])
        self.assertEqual(endpoint.rate_limit_per_min, data['rate_limit_per_min'])
        self.assertEqual(endpoint.label, data['label'])
        self.assertEqual(endpoint.description, data['description'])
    
    def test_create_endpoint_invalid_url(self):
        """Test creating endpoint with invalid URL."""
        data = {
            'url': 'invalid-url',
            'secret': 'test-secret-key',
            'status': WebhookStatus.ACTIVE
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)
    
    def test_create_endpoint_invalid_status(self):
        """Test creating endpoint with invalid status."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'status': 'invalid-status'
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)
    
    def test_create_endpoint_invalid_http_method(self):
        """Test creating endpoint with invalid HTTP method."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'http_method': 'INVALID'
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('http_method', serializer.errors)
    
    def test_create_endpoint_invalid_timeout(self):
        """Test creating endpoint with invalid timeout."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'timeout_seconds': -1
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('timeout_seconds', serializer.errors)
    
    def test_create_endpoint_invalid_max_retries(self):
        """Test creating endpoint with invalid max retries."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'max_retries': -1
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('max_retries', serializer.errors)
    
    def test_create_endpoint_invalid_rate_limit(self):
        """Test creating endpoint with invalid rate limit."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'rate_limit_per_min': -1
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('rate_limit_per_min', serializer.errors)
    
    def test_update_endpoint_valid_data(self):
        """Test updating endpoint with valid data."""
        data = {
            'status': WebhookStatus.PAUSED,
            'timeout_seconds': 60,
            'max_retries': 5
        }
        
        serializer = WebhookEndpointSerializer(
            instance=self.endpoint,
            data=data,
            partial=True
        )
        
        self.assertTrue(serializer.is_valid())
        
        updated_endpoint = serializer.save()
        self.assertEqual(updated_endpoint.status, data['status'])
        self.assertEqual(updated_endpoint.timeout_seconds, data['timeout_seconds'])
        self.assertEqual(updated_endpoint.max_retries, data['max_retries'])
    
    def test_validate_ip_whitelist_valid(self):
        """Test IP whitelist validation with valid data."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'ip_whitelist': ['192.168.1.1', '10.0.0.1', '127.0.0.1']
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_ip_whitelist_invalid_ip(self):
        """Test IP whitelist validation with invalid IP."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'ip_whitelist': ['invalid-ip-address']
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip_whitelist', serializer.errors)
    
    def test_validate_headers_valid(self):
        """Test headers validation with valid data."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'headers': {
                'Content-Type': 'application/json',
                'X-Custom-Header': 'custom-value'
            }
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_validate_headers_invalid_value(self):
        """Test headers validation with invalid value type."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'test-secret-key',
            'headers': {
                'Content-Type': 123  # Invalid type
            }
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('headers', serializer.errors)
    
    def test_validate_secret_strength(self):
        """Test secret strength validation."""
        data = {
            'url': 'https://example.com/webhook',
            'secret': 'weak',  # Too short
            'status': WebhookStatus.ACTIVE
        }
        
        serializer = WebhookEndpointSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('secret', serializer.errors)


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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.subscription = WebhookSubscription.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            is_active=True,
            created_by=self.user,
        )
        self.serializer = WebhookSubscriptionSerializer(instance=self.subscription)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'event_type', 'is_active',
            'filter_config', 'created_at', 'updated_at'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.subscription.endpoint.id)
        self.assertEqual(data['event_type'], self.subscription.event_type)
        self.assertEqual(data['is_active'], self.subscription.is_active)
        self.assertEqual(data['filter_config'], self.subscription.filter_config)
    
    def test_create_subscription_valid_data(self):
        """Test creating subscription with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.updated',
            'is_active': True,
            'filter_config': {
                'user.email': {
                    'operator': 'contains',
                    'value': '@example.com'
                }
            }
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        subscription = serializer.save()
        self.assertEqual(subscription.endpoint.id, data['endpoint'])
        self.assertEqual(subscription.event_type, data['event_type'])
        self.assertEqual(subscription.is_active, data['is_active'])
        self.assertEqual(subscription.filter_config, data['filter_config'])
    
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
        """Test filter config validation with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'filter_config': {
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
        self.assertTrue(serializer.is_valid())
    
    def test_validate_filter_config_invalid_structure(self):
        """Test filter config validation with invalid structure."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',
            'filter_config': 'invalid-string'  # Should be dict
        }
        
        serializer = WebhookSubscriptionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('filter_config', serializer.errors)


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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345, 'email': 'test@example.com'},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            response_body='{"status": "success"}',
            duration_ms=150,
            attempt_number=1,
            max_attempts=3,
            created_by=self.user,
        )
        self.serializer = WebhookDeliveryLogSerializer(instance=self.delivery_log)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'event_type', 'payload', 'request_headers',
            'signature', 'http_status_code', 'response_body',
            'duration_ms', 'error_message', 'status', 'attempt_number',
            'max_attempts', 'next_retry_at', 'dispatched_at',
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
        self.assertEqual(data['http_status_code'], self.delivery_log.response_code)
        self.assertEqual(data['response_body'], self.delivery_log.response_body)
        self.assertEqual(data['duration_ms'], self.delivery_log.duration_ms)
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
            'duration_ms': 200,
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
        self.assertEqual(delivery_log.duration_ms, data['duration_ms'])
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.filter = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator=FilterOperator.CONTAINS,
            value='@example.com',
            is_active=True,
            created_by=self.user,
        )
        self.serializer = WebhookFilterSerializer(instance=self.filter)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'field_path', 'operator', 'value',
            'is_active', 'created_at', 'updated_at', 'created_by'
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
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
        """Test event types validation with empty list."""
        data = {
            'event_types': []
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['event_types'], [])
    
    def test_validate_event_types_invalid_type(self):
        """Test event types validation with invalid type."""
        data = {
            'event_types': 'user.created'  # Should be list
        }
        
        serializer = WebhookEventTypeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('event_types', serializer.errors)
    
    def test_validate_event_types_invalid_event_type(self):
        """Test event types validation with invalid event type."""
        data = {
            'event_types': ['invalid.event.type']
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.analytics = WebhookAnalytics.objects.create(
            endpoint=self.endpoint,
            date=timezone.now().date(),
            total_sent=100,
            success_count=95,
            failed_count=5,
            avg_latency_ms=150.0,
            success_rate=95.0,
            created_by=self.user,
        )
        self.serializer = WebhookAnalyticsSerializer(instance=self.analytics)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'endpoint', 'date', 'total_sent', 'success_count',
            'failed_count', 'avg_latency_ms', 'success_rate',
            'created_at', 'updated_at', 'created_by'
        }
        
        self.assertEqual(set(data.keys()), expected_fields)
    
    def test_field_content(self):
        """Test serializer field content."""
        data = self.serializer.data
        
        self.assertEqual(data['endpoint'], self.analytics.endpoint.id)
        self.assertEqual(data['date'], self.analytics.date)
        self.assertEqual(data['total_sent'], self.analytics.total_sent)
        self.assertEqual(data['success_count'], self.analytics.success_count)
        self.assertEqual(data['failed_count'], self.analytics.failed_count)
        self.assertEqual(data['avg_latency_ms'], self.analytics.avg_latency_ms)
        self.assertEqual(data['success_rate'], self.analytics.success_rate)
    
    def test_create_analytics_valid_data(self):
        """Test creating analytics with valid data."""
        data = {
            'endpoint': self.endpoint.id,
            'date': timezone.now().date(),
            'total_sent': 200,
            'success_count': 190,
            'failed_count': 10,
            'avg_latency_ms': 200.0,
            'success_rate': 95.0
        }
        
        serializer = WebhookAnalyticsSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
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
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.original_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.FAILED,
            created_by=self.user,
        )
        self.replay = WebhookReplay.objects.create(
            original_log=self.original_log,
            replayed_by=self.user,
            reason='Test replay',
            status=ReplayStatus.PENDING,
            created_by=self.user,
        )
        self.serializer = WebhookReplaySerializer(instance=self.replay)
    
    def test_contains_expected_fields(self):
        """Test serializer contains expected fields."""
        data = self.serializer.data
        
        expected_fields = {
            'id', 'original_log', 'replayed_by', 'new_log',
            'reason', 'status', 'replayed_at', 'created_at',
            'updated_at', 'created_by'
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
        """Test creating replay with valid data."""
        new_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            created_by=self.user,
        )
        
        data = {
            'original_log': self.original_log.id,
            'replayed_by': self.user.id,
            'reason': 'Test replay 2',
            'status': ReplayStatus.COMPLETED,
            'new_log': new_log.id
        }
        
        serializer = WebhookReplaySerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        replay = serializer.save()
        self.assertEqual(replay.original_log.id, data['original_log'])
        self.assertEqual(replay.replayed_by.id, data['replayed_by'])
        self.assertEqual(replay.reason, data['reason'])
        self.assertEqual(replay.status, data['status'])
        self.assertEqual(replay.new_log.id, data['new_log'])
    
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
