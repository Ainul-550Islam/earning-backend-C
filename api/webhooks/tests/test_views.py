"""Test Views for Webhooks System

This module contains tests for the webhook views
including API endpoints, authentication, and response handling.
"""

import pytest
import json
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from ..models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret
)
from ..constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus
)

User = get_user_model()


class WebhookEndpointViewTest(TestCase):
    """Test cases for WebhookEndpoint views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
    
    def test_list_endpoints_success(self):
        """Test listing webhook endpoints successfully."""
        url = reverse('webhookendpoint-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.endpoint.id))
    
    def test_list_endpoints_unauthorized(self):
        """Test listing webhook endpoints without authorization."""
        self.client.credentials()  # Remove authentication
        url = reverse('webhookendpoint-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_endpoint_success(self):
        """Test getting a specific webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.endpoint.id))
        self.assertEqual(response.data['url'], self.endpoint.url)
    
    def test_get_endpoint_not_found(self):
        """Test getting a non-existent webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': '123e4567-e89b-12d3-a456-426614174000'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_create_endpoint_success(self):
        """Test creating a webhook endpoint successfully."""
        data = {
            'url': 'https://example.com/new-webhook',
            'secret': 'new-secret-key',
            'status': WebhookStatus.ACTIVE,
            'http_method': HttpMethod.POST,
            'timeout_seconds': 30,
            'max_retries': 3,
            'verify_ssl': True,
            'ip_whitelist': ['192.168.1.1'],
            'headers': {'Content-Type': 'application/json'},
            'rate_limit_per_min': 1000,
            'label': 'New Webhook',
            'description': 'A new webhook endpoint'
        }
        
        url = reverse('webhookendpoint-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['url'], data['url'])
        self.assertEqual(response.data['status'], data['status'])
        self.assertEqual(response.data['label'], data['label'])
    
    def test_create_endpoint_invalid_data(self):
        """Test creating a webhook endpoint with invalid data."""
        data = {
            'url': 'invalid-url',
            'secret': 'test-secret-key',
            'status': WebhookStatus.ACTIVE
        }
        
        url = reverse('webhookendpoint-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('url', response.data)
    
    def test_update_endpoint_success(self):
        """Test updating a webhook endpoint successfully."""
        data = {
            'status': WebhookStatus.PAUSED,
            'timeout_seconds': 60,
            'max_retries': 5
        }
        
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], data['status'])
        self.assertEqual(response.data['timeout_seconds'], data['timeout_seconds'])
        self.assertEqual(response.data['max_retries'], data['max_retries'])
    
    def test_update_endpoint_not_found(self):
        """Test updating a non-existent webhook endpoint."""
        data = {'status': WebhookStatus.PAUSED}
        
        url = reverse('webhookendpoint-detail', kwargs={'pk': '123e4567-e89b-12d3-a456-426614174000'})
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_endpoint_success(self):
        """Test deleting a webhook endpoint successfully."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': self.endpoint.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        with self.assertRaises(WebhookEndpoint.DoesNotExist):
            WebhookEndpoint.objects.get(id=self.endpoint.id)
    
    def test_delete_endpoint_not_found(self):
        """Test deleting a non-existent webhook endpoint."""
        url = reverse('webhookendpoint-detail', kwargs={'pk': '123e4567-e89b-12d3-a456-426614174000'})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_endpoint_health_check_success(self):
        """Test endpoint health check action."""
        with patch('api.webhooks.services.analytics.HealthMonitorService.check_endpoint_health') as mock_health:
            mock_health.return_value = {
                'is_healthy': True,
                'status_code': 200,
                'response_time_ms': 150
            }
            
            url = reverse('webhookendpoint-health-check', kwargs={'pk': self.endpoint.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['is_healthy'])
            self.assertEqual(response.data['status_code'], 200)
            mock_health.assert_called_once()
    
    def test_endpoint_test_webhook_success(self):
        """Test endpoint test webhook action."""
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            url = reverse('webhookendpoint-test-webhook', kwargs={'pk': self.endpoint.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_endpoint_rotate_secret_success(self):
        """Test endpoint rotate secret action."""
        with patch('api.webhooks.services.core.SecretRotationService.rotate_secret') as mock_rotate:
            mock_rotate.return_value = 'new-secret-key'
            
            url = reverse('webhookendpoint-rotate-secret', kwargs={'pk': self.endpoint.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['new_secret'], 'new-secret-key')
            mock_rotate.assert_called_once()


class WebhookSubscriptionViewTest(TestCase):
    """Test cases for WebhookSubscription views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
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
    
    def test_list_subscriptions_success(self):
        """Test listing webhook subscriptions successfully."""
        url = reverse('webhooksubscription-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.subscription.id))
    
    def test_create_subscription_success(self):
        """Test creating a webhook subscription successfully."""
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
        
        url = reverse('webhooksubscription-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_type'], data['event_type'])
        self.assertEqual(response.data['filter_config'], data['filter_config'])
    
    def test_create_subscription_duplicate_event_type(self):
        """Test creating subscription with duplicate event type."""
        data = {
            'endpoint': self.endpoint.id,
            'event_type': 'user.created',  # Same as existing subscription
            'is_active': True
        }
        
        url = reverse('webhooksubscription-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_update_subscription_success(self):
        """Test updating a webhook subscription successfully."""
        data = {
            'is_active': False,
            'filter_config': {
                'user.status': {
                    'operator': 'equals',
                    'value': 'active'
                }
            }
        }
        
        url = reverse('webhooksubscription-detail', kwargs={'pk': self.subscription.id})
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_active'], data['is_active'])
        self.assertEqual(response.data['filter_config'], data['filter_config'])


class WebhookDeliveryLogViewTest(TestCase):
    """Test cases for WebhookDeliveryLog views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.delivery_log = WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.created',
            payload={'user_id': 12345},
            status=DeliveryStatus.SUCCESS,
            response_code=200,
            created_by=self.user,
        )
    
    def test_list_delivery_logs_success(self):
        """Test listing webhook delivery logs successfully."""
        url = reverse('webhookdeliverylog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.delivery_log.id))
    
    def test_list_delivery_logs_with_filters(self):
        """Test listing webhook delivery logs with filters."""
        # Create additional delivery log with different status
        WebhookDeliveryLog.objects.create(
            endpoint=self.endpoint,
            event_type='user.updated',
            payload={'user_id': 12346},
            status=DeliveryStatus.FAILED,
            response_code=500,
            created_by=self.user,
        )
        
        url = reverse('webhookdeliverylog-list')
        response = self.client.get(url, {'status': DeliveryStatus.SUCCESS})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], DeliveryStatus.SUCCESS)
    
    def test_get_delivery_log_success(self):
        """Test getting a specific webhook delivery log."""
        url = reverse('webhookdeliverylog-detail', kwargs={'pk': self.delivery_log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.delivery_log.id))
        self.assertEqual(response.data['event_type'], self.delivery_log.event_type)
    
    def test_retry_delivery_log_success(self):
        """Test retrying a webhook delivery log successfully."""
        with patch('api.webhooks.services.core.DispatchService.retry_delivery') as mock_retry:
            mock_retry.return_value = True
            
            url = reverse('webhookdeliverylog-retry', kwargs={'pk': self.delivery_log.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_retry.assert_called_once()


class WebhookEmitViewTest(TestCase):
    """Test cases for WebhookEmit views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
    
    def test_emit_webhook_success(self):
        """Test emitting a webhook successfully."""
        with patch('api.webhooks.services.core.DispatchService.emit') as mock_emit:
            mock_emit.return_value = True
            
            data = {
                'event_type': 'user.created',
                'payload': {'user_id': 12345, 'email': 'test@example.com'},
                'endpoint_id': self.endpoint.id,
                'async_emit': False
            }
            
            url = reverse('webhook-emit')
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_emit_webhook_async_success(self):
        """Test emitting a webhook asynchronously successfully."""
        with patch('api.webhooks.services.core.DispatchService.emit_async') as mock_emit:
            mock_emit.return_value = True
            
            data = {
                'event_type': 'user.created',
                'payload': {'user_id': 12345},
                'endpoint_id': self.endpoint.id,
                'async_emit': True
            }
            
            url = reverse('webhook-emit')
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_emit.assert_called_once()
    
    def test_emit_webhook_invalid_data(self):
        """Test emitting a webhook with invalid data."""
        data = {
            'event_type': 'user.created',
            'payload': 'invalid-payload',  # Should be dict
            'endpoint_id': self.endpoint.id
        }
        
        url = reverse('webhook-emit')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('payload', response.data)
    
    def test_emit_webhook_endpoint_not_found(self):
        """Test emitting a webhook with non-existent endpoint."""
        data = {
            'event_type': 'user.created',
            'payload': {'user_id': 12345},
            'endpoint_id': '123e4567-e89b-12d3-a456-426614174000'
        }
        
        url = reverse('webhook-emit')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('endpoint_id', response.data)


class WebhookEventTypeListViewTest(TestCase):
    """Test cases for WebhookEventTypeList views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
    
    def test_list_event_types_success(self):
        """Test listing webhook event types successfully."""
        url = reverse('webhook-event-types')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('event_types', response.data)
        self.assertIsInstance(response.data['event_types'], list)
        self.assertGreater(len(response.data['event_types']), 0)
    
    def test_list_event_types_unauthorized(self):
        """Test listing webhook event types without authorization."""
        self.client.credentials()  # Remove authentication
        url = reverse('webhook-event-types')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WebhookFilterViewTest(TestCase):
    """Test cases for WebhookFilter views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
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
    
    def test_list_filters_success(self):
        """Test listing webhook filters successfully."""
        url = reverse('webhookfilter-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.filter.id))
    
    def test_create_filter_success(self):
        """Test creating a webhook filter successfully."""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': 'user.status',
            'operator': FilterOperator.EQUALS,
            'value': 'active',
            'is_active': True
        }
        
        url = reverse('webhookfilter-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['field_path'], data['field_path'])
        self.assertEqual(response.data['operator'], data['operator'])
        self.assertEqual(response.data['value'], data['value'])
    
    def test_test_filter_success(self):
        """Test testing a webhook filter successfully."""
        with patch('api.webhooks.services.filtering.FilterService.evaluate_filter') as mock_evaluate:
            mock_evaluate.return_value = True
            
            data = {
                'payload': {'user_email': 'test@example.com'}
            }
            
            url = reverse('webhookfilter-test-filter', kwargs={'pk': self.filter.id})
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['matches'])
            mock_evaluate.assert_called_once()


class WebhookBatchViewTest(TestCase):
    """Test cases for WebhookBatch views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.batch = WebhookBatch.objects.create(
            batch_id='BATCH-123456',
            endpoint=self.endpoint,
            event_count=10,
            status=BatchStatus.PENDING,
            created_by=self.user,
        )
    
    def test_list_batches_success(self):
        """Test listing webhook batches successfully."""
        url = reverse('webhookbatch-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.batch.id))
    
    def test_get_batch_status_success(self):
        """Test getting batch status successfully."""
        url = reverse('webhookbatch-status', kwargs={'pk': self.batch.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['batch_id'], self.batch.batch_id)
        self.assertEqual(response.data['status'], self.batch.status)
        self.assertEqual(response.data['total_items'], self.batch.event_count)
    
    def test_process_batch_success(self):
        """Test processing a batch successfully."""
        with patch('api.webhooks.services.batch.BatchService.process_batch') as mock_process:
            mock_process.return_value = {
                'success': True,
                'processed_count': 10,
                'success_count': 8,
                'failed_count': 2
            }
            
            url = reverse('webhookbatch-process', kwargs={'pk': self.batch.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertEqual(response.data['processed_count'], 10)
            mock_process.assert_called_once()
    
    def test_cancel_batch_success(self):
        """Test canceling a batch successfully."""
        with patch('api.webhooks.services.batch.BatchService.cancel_batch') as mock_cancel:
            mock_cancel.return_value = {'success': True}
            
            url = reverse('webhookbatch-cancel', kwargs={'pk': self.batch.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            mock_cancel.assert_called_once()


class WebhookTemplateViewTest(TestCase):
    """Test cases for WebhookTemplate views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user_id": {{user_id}}, "email": {{user_email}}}',
            is_active=True,
            created_by=self.user,
        )
    
    def test_list_templates_success(self):
        """Test listing webhook templates successfully."""
        url = reverse('webhooktemplate-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.template.id))
    
    def test_create_template_success(self):
        """Test creating a webhook template successfully."""
        data = {
            'name': 'New Template',
            'event_type': 'user.updated',
            'payload_template': '{"user_id": {{user_id}}, "status": {{user_status}}}',
            'is_active': True
        }
        
        url = reverse('webhooktemplate-list')
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], data['name'])
        self.assertEqual(response.data['event_type'], data['event_type'])
        self.assertEqual(response.data['payload_template'], data['payload_template'])
    
    def test_preview_template_success(self):
        """Test previewing a webhook template successfully."""
        with patch('api.webhooks.services.core.TemplateEngine.render_template') as mock_render:
            mock_render.return_value = '{"user_id": 12345, "email": "test@example.com"}'
            
            data = {
                'payload': {'user_id': 12345, 'user_email': 'test@example.com'}
            }
            
            url = reverse('webhooktemplate-preview', kwargs={'pk': self.template.id})
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('user_id', response.data['rendered_template'])
            mock_render.assert_called_once()


class WebhookSecretViewTest(TestCase):
    """Test cases for WebhookSecret views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        
        self.endpoint = WebhookEndpoint.objects.create(
            url='https://example.com/webhook',
            secret='test-secret-key',
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.secret = WebhookSecret.objects.create(
            endpoint=self.endpoint,
            secret_hash='hashed-secret',
            is_active=True,
            created_by=self.user,
        )
    
    def test_list_secrets_success(self):
        """Test listing webhook secrets successfully."""
        url = reverse('webhooksecret-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.secret.id))
    
    def test_rotate_secret_success(self):
        """Test rotating a webhook secret successfully."""
        with patch('api.webhooks.services.core.SecretRotationService.rotate_secret') as mock_rotate:
            mock_rotate.return_value = 'new-secret-key'
            
            url = reverse('webhooksecret-rotate', kwargs={'pk': self.secret.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['new_secret'], 'new-secret-key')
            mock_rotate.assert_called_once()


# Additional view tests can be added here for the remaining views
# (WebhookAnalyticsView, WebhookHealthView, WebhookReplayView, etc.)
