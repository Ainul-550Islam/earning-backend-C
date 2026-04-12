"""
Tests for Channel ViewSets
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta
import json

from alerts.models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, ChannelRateLimit, AlertRecipient
)
from alerts.viewsets.channel import (
    AlertChannelViewSet, ChannelRouteViewSet, ChannelHealthLogViewSet,
    ChannelRateLimitViewSet, AlertRecipientViewSet
)

User = get_user_model()


class AlertChannelViewSetTest(APITestCase):
    """Test cases for AlertChannelViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_channel = AlertChannel.objects.create(
            name='Email Channel',
            channel_type='email',
            description='Primary email notification channel',
            is_enabled=True,
            priority=1,
            config={
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'alerts@example.com',
                'use_tls': True
            },
            webhook_url='https://api.example.com/webhooks/email'
        )
    
    def test_list_alert_channels(self):
        """Test listing alert channels"""
        url = '/api/alerts/channels/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['channel_type'], 'email')
    
    def test_create_alert_channel(self):
        """Test creating alert channel"""
        url = '/api/alerts/channels/'
        data = {
            'name': 'SMS Channel',
            'channel_type': 'sms',
            'description': 'SMS notification channel',
            'is_enabled': True,
            'priority': 2,
            'config': {
                'api_key': 'test_api_key',
                'api_url': 'https://sms.example.com/api'
            }
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertChannel.objects.count(), 2)
    
    def test_retrieve_alert_channel(self):
        """Test retrieving single alert channel"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Email Channel')
    
    def test_update_alert_channel(self):
        """Test updating alert channel"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/'
        data = {
            'name': 'Updated Email Channel',
            'priority': 2
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_channel.refresh_from_db()
        self.assertEqual(self.alert_channel.name, 'Updated Email Channel')
        self.assertEqual(self.alert_channel.priority, 2)
    
    def test_delete_alert_channel(self):
        """Test deleting alert channel"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AlertChannel.objects.count(), 0)
    
    def test_enable_alert_channel(self):
        """Test enabling alert channel"""
        self.alert_channel.is_enabled = False
        self.alert_channel.save()
        
        url = f'/api/alerts/channels/{self.alert_channel.id}/enable/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_channel.refresh_from_db()
        self.assertTrue(self.alert_channel.is_enabled)
    
    def test_disable_alert_channel(self):
        """Test disabling alert channel"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/disable/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_channel.refresh_from_db()
        self.assertFalse(self.alert_channel.is_enabled)
    
    def test_test_alert_channel(self):
        """Test testing alert channel"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/test/'
        data = {
            'message': 'Test notification',
            'recipient': 'test@example.com',
            'subject': 'Test Subject'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('test_result', response.data)
    
    def test_get_channel_health(self):
        """Test getting channel health"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/health/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('health_status', response.data)
        self.assertIn('success_rate', response.data)
    
    def test_get_channel_statistics(self):
        """Test getting channel statistics"""
        url = f'/api/alerts/channels/{self.alert_channel.id}/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_sent', response.data)
        self.assertIn('total_failed', response.data)
        self.assertIn('success_rate', response.data)


class ChannelRouteViewSetTest(APITestCase):
    """Test cases for ChannelRouteViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.source_channel = AlertChannel.objects.create(
            name='Source Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.destination_channel = AlertChannel.objects.create(
            name='Destination Channel',
            channel_type='sms',
            is_enabled=True
        )
        
        self.channel_route = ChannelRoute.objects.create(
            name='Email to SMS Route',
            route_type='escalation',
            is_active=True,
            priority=1,
            escalation_delay_minutes=30,
            escalate_after_failures=3
        )
        
        self.channel_route.source_channels.add(self.source_channel)
        self.channel_route.destination_channels.add(self.destination_channel)
    
    def test_list_channel_routes(self):
        """Test listing channel routes"""
        url = '/api/alerts/channels/routes/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['route_type'], 'escalation')
    
    def test_create_channel_route(self):
        """Test creating channel route"""
        url = '/api/alerts/channels/routes/'
        data = {
            'name': 'SMS to Webhook Route',
            'route_type': 'routing',
            'is_active': True,
            'priority': 2,
            'escalation_delay_minutes': 15,
            'source_channels': [self.source_channel.id],
            'destination_channels': [self.destination_channel.id]
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ChannelRoute.objects.count(), 2)
    
    def test_retrieve_channel_route(self):
        """Test retrieving single channel route"""
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Email to SMS Route')
    
    def test_update_channel_route(self):
        """Test updating channel route"""
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/'
        data = {
            'name': 'Updated Route',
            'priority': 2
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_route.refresh_from_db()
        self.assertEqual(self.channel_route.name, 'Updated Route')
        self.assertEqual(self.channel_route.priority, 2)
    
    def test_delete_channel_route(self):
        """Test deleting channel route"""
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ChannelRoute.objects.count(), 0)
    
    def test_activate_channel_route(self):
        """Test activating channel route"""
        self.channel_route.is_active = False
        self.channel_route.save()
        
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_route.refresh_from_db()
        self.assertTrue(self.channel_route.is_active)
    
    def test_deactivate_channel_route(self):
        """Test deactivating channel route"""
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_route.refresh_from_db()
        self.assertFalse(self.channel_route.is_active)
    
    def test_test_channel_route(self):
        """Test testing channel route"""
        url = f'/api/alerts/channels/routes/{self.channel_route.id}/test/'
        data = {
            'test_message': 'Test route message',
            'test_recipient': 'test@example.com'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('test_result', response.data)
    
    def test_get_routes_by_type(self):
        """Test getting routes by type"""
        url = '/api/alerts/channels/routes/by_type/escalation/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_routes(self):
        """Test getting active routes"""
        url = '/api/alerts/channels/routes/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class ChannelHealthLogViewSetTest(APITestCase):
    """Test cases for ChannelHealthLogViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.channel_health_log = ChannelHealthLog.objects.create(
            channel=self.alert_channel,
            check_name='smtp_connection',
            check_type='connectivity',
            status='healthy',
            response_time_ms=150.5,
            status_message='Connection successful'
        )
    
    def test_list_channel_health_logs(self):
        """Test listing channel health logs"""
        url = '/api/alerts/channels/health_logs/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['check_name'], 'smtp_connection')
    
    def test_create_channel_health_log(self):
        """Test creating channel health log"""
        url = '/api/alerts/channels/health_logs/'
        data = {
            'channel': self.alert_channel.id,
            'check_name': 'api_connectivity',
            'check_type': 'connectivity',
            'status': 'warning',
            'response_time_ms': 500.0,
            'status_message': 'Slow response'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ChannelHealthLog.objects.count(), 2)
    
    def test_retrieve_channel_health_log(self):
        """Test retrieving single channel health log"""
        url = f'/api/alerts/channels/health_logs/{self.channel_health_log.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['check_name'], 'smtp_connection')
    
    def test_get_health_logs_by_channel(self):
        """Test getting health logs by channel"""
        url = f'/api/alerts/channels/health_logs/by_channel/{self.alert_channel.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_health_logs_by_status(self):
        """Test getting health logs by status"""
        url = '/api/alerts/channels/health_logs/by_status/healthy/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_health_logs_by_type(self):
        """Test getting health logs by type"""
        url = '/api/alerts/channels/health_logs/by_type/connectivity/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_recent_health_logs(self):
        """Test getting recent health logs"""
        url = '/api/alerts/channels/health_logs/recent/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recent_logs', response.data)
    
    def test_get_health_statistics(self):
        """Test getting health statistics"""
        url = '/api/alerts/channels/health_logs/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_checks', response.data)
        self.assertIn('healthy_checks', response.data)
        self.assertIn('warning_checks', response.data)
        self.assertIn('critical_checks', response.data)


class ChannelRateLimitViewSetTest(APITestCase):
    """Test cases for ChannelRateLimitViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_channel = AlertChannel.objects.create(
            name='Test Channel',
            channel_type='email',
            is_enabled=True
        )
        
        self.channel_rate_limit = ChannelRateLimit.objects.create(
            channel=self.alert_channel,
            limit_type='per_minute',
            window_seconds=60,
            max_requests=100,
            current_tokens=100,
            last_refill=timezone.now()
        )
    
    def test_list_channel_rate_limits(self):
        """Test listing channel rate limits"""
        url = '/api/alerts/channels/rate_limits/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['limit_type'], 'per_minute')
    
    def test_create_channel_rate_limit(self):
        """Test creating channel rate limit"""
        url = '/api/alerts/channels/rate_limits/'
        data = {
            'channel': self.alert_channel.id,
            'limit_type': 'per_hour',
            'window_seconds': 3600,
            'max_requests': 1000,
            'current_tokens': 1000
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ChannelRateLimit.objects.count(), 2)
    
    def test_retrieve_channel_rate_limit(self):
        """Test retrieving single channel rate limit"""
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['limit_type'], 'per_minute')
    
    def test_update_channel_rate_limit(self):
        """Test updating channel rate limit"""
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/'
        data = {
            'max_requests': 200,
            'current_tokens': 200
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_rate_limit.refresh_from_db()
        self.assertEqual(self.channel_rate_limit.max_requests, 200)
        self.assertEqual(self.channel_rate_limit.current_tokens, 200)
    
    def test_delete_channel_rate_limit(self):
        """Test deleting channel rate limit"""
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ChannelRateLimit.objects.count(), 0)
    
    def test_consume_token(self):
        """Test consuming token"""
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/consume_token/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('remaining_tokens', response.data)
    
    def test_refill_tokens(self):
        """Test refilling tokens"""
        self.channel_rate_limit.current_tokens = 50
        self.channel_rate_limit.save()
        
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/refill_tokens/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_rate_limit.refresh_from_db()
        self.assertEqual(self.channel_rate_limit.current_tokens, self.channel_rate_limit.max_requests)
    
    def test_reset_rate_limit(self):
        """Test resetting rate limit"""
        self.channel_rate_limit.total_requests = 500
        self.channel_rate_limit.rejected_requests = 50
        self.channel_rate_limit.save()
        
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/reset/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.channel_rate_limit.refresh_from_db()
        self.assertEqual(self.channel_rate_limit.total_requests, 0)
        self.assertEqual(self.channel_rate_limit.rejected_requests, 0)
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status"""
        url = f'/api/alerts/channels/rate_limits/{self.channel_rate_limit.id}/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('can_send', response.data)
        self.assertIn('utilization', response.data)
        self.assertIn('time_until_refill', response.data)
    
    def test_get_rate_limits_by_channel(self):
        """Test getting rate limits by channel"""
        url = f'/api/alerts/channels/rate_limits/by_channel/{self.alert_channel.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_rate_limits_by_type(self):
        """Test getting rate limits by type"""
        url = '/api/alerts/channels/rate_limits/by_type/per_minute/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class AlertRecipientViewSetTest(APITestCase):
    """Test cases for AlertRecipientViewSet"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.alert_recipient = AlertRecipient.objects.create(
            name='Test User',
            recipient_type='user',
            user=self.user,
            email_address='test@example.com',
            phone_number='+1234567890',
            priority=1,
            is_active=True,
            timezone='UTC',
            max_notifications_per_hour=50
        )
    
    def test_list_alert_recipients(self):
        """Test listing alert recipients"""
        url = '/api/alerts/channels/recipients/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['recipient_type'], 'user')
    
    def test_create_alert_recipient(self):
        """Test creating alert recipient"""
        url = '/api/alerts/channels/recipients/'
        data = {
            'name': 'New User',
            'recipient_type': 'email',
            'email_address': 'newuser@example.com',
            'priority': 2,
            'is_active': True,
            'max_notifications_per_hour': 25
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AlertRecipient.objects.count(), 2)
    
    def test_retrieve_alert_recipient(self):
        """Test retrieving single alert recipient"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test User')
    
    def test_update_alert_recipient(self):
        """Test updating alert recipient"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/'
        data = {
            'name': 'Updated User',
            'priority': 2
        }
        
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_recipient.refresh_from_db()
        self.assertEqual(self.alert_recipient.name, 'Updated User')
        self.assertEqual(self.alert_recipient.priority, 2)
    
    def test_delete_alert_recipient(self):
        """Test deleting alert recipient"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AlertRecipient.objects.count(), 0)
    
    def test_activate_alert_recipient(self):
        """Test activating alert recipient"""
        self.alert_recipient.is_active = False
        self.alert_recipient.save()
        
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/activate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_recipient.refresh_from_db()
        self.assertTrue(self.alert_recipient.is_active)
    
    def test_deactivate_alert_recipient(self):
        """Test deactivating alert recipient"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_recipient.refresh_from_db()
        self.assertFalse(self.alert_recipient.is_active)
    
    def test_test_alert_recipient(self):
        """Test testing alert recipient"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/test/'
        data = {
            'message': 'Test notification',
            'subject': 'Test Subject'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('test_result', response.data)
    
    def test_get_recipients_by_type(self):
        """Test getting recipients by type"""
        url = '/api/alerts/channels/recipients/by_type/user/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_active_recipients(self):
        """Test getting active recipients"""
        url = '/api/alerts/channels/recipients/active/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_recipients_by_priority(self):
        """Test getting recipients by priority"""
        url = '/api/alerts/channels/recipients/by_priority/1/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_recipient_statistics(self):
        """Test getting recipient statistics"""
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/statistics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('notifications_sent_today', response.data)
        self.assertIn('notifications_sent_this_hour', response.data)
        self.assertIn('last_notification_at', response.data)
    
    def test_reset_daily_counters(self):
        """Test resetting daily counters"""
        self.alert_recipient.notifications_sent_today = 100
        self.alert_recipient.save()
        
        url = f'/api/alerts/channels/recipients/{self.alert_recipient.id}/reset_counters/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.alert_recipient.refresh_from_db()
        self.assertEqual(self.alert_recipient.notifications_sent_today, 0)
