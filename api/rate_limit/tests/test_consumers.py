"""
Comprehensive WebSocket consumer tests for rate_limit module.

This test file covers all WebSocket consumers, real-time functionality,
connection management, and WebSocket security.
"""

import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from rest_framework.test import APITestCase
from datetime import datetime, timedelta

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.consumers import RateLimitConsumer
from api.rate_limit.routing import websocket_urlpatterns

User = get_user_model()


class RateLimitConsumerTest(TransactionTestCase):
    """Test cases for RateLimitConsumer WebSocket functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
        # Create test rate limit config
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
        # Create test user profile
        self.profile = UserRateLimitProfile.objects.create(
            user=self.regular_user,
            risk_level='low',
            custom_rate_multiplier=1.0,
            is_trusted=True
        )
        
    async def test_websocket_connection_authenticated(self):
        """Test WebSocket connection with authenticated user"""
        # Create application with authentication middleware
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        
        # Create communicator with authenticated user
        communicator = WebsocketCommunicator(
            application,
            path='/ws/rate-limit/',
        )
        
        # Simulate authentication
        communicator.scope['user'] = self.regular_user
        
        # Connect to WebSocket
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send test message
        await communicator.send_json_to({
            'type': 'get_stats',
            'data': {}
        })
        
        # Receive response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'stats_response')
        self.assertIn('total_requests', response['data'])
        
        # Close connection
        await communicator.disconnect()
        
    async def test_websocket_connection_unauthenticated(self):
        """Test WebSocket connection without authentication"""
        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Connect should be rejected
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        
    async def test_websocket_real_time_rate_limit_updates(self):
        """Test real-time rate limit updates via WebSocket"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to real-time updates
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'rate_limit_violation'
            }
        })
        
        # Receive subscription confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        self.assertEqual(response['data']['event_type'], 'rate_limit_violation')
        
        # Simulate rate limit violation
        with patch('api.rate_limit.consumers.RateLimitConsumer.broadcast_rate_limit_violation') as mock_broadcast:
            mock_broadcast.return_value = AsyncMock()
            
            # Trigger violation
            await communicator.send_json_to({
                'type': 'simulate_violation',
                'data': {
                    'user_id': self.regular_user.id,
                    'endpoint': '/api/test/',
                    'ip_address': '192.168.1.100'
                }
            })
            
            # Verify broadcast was called
            mock_broadcast.assert_called_once()
        
        await communicator.disconnect()
        
    async def test_websocket_user_specific_updates(self):
        """Test WebSocket updates filtered by user"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as regular user
        communicator.scope['user'] = self.regular_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to user-specific updates
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'user_rate_limit',
                'user_id': self.regular_user.id
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Request user-specific stats
        await communicator.send_json_to({
            'type': 'get_user_stats',
            'data': {
                'user_id': self.regular_user.id
            }
        })
        
        # Receive user stats
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'user_stats_response')
        self.assertEqual(response['data']['user_id'], self.regular_user.id)
        
        await communicator.disconnect()
        
    async def test_websocket_admin_monitoring(self):
        """Test WebSocket monitoring for admin users"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to admin monitoring
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'admin_monitoring'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Request system-wide stats
        await communicator.send_json_to({
            'type': 'get_system_stats',
            'data': {}
        })
        
        # Receive system stats
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'system_stats_response')
        self.assertIn('total_users', response['data'])
        self.assertIn('active_configs', response['data'])
        self.assertIn('recent_violations', response['data'])
        
        await communicator.disconnect()
        
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate
        communicator.scope['user'] = self.regular_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send invalid message
        await communicator.send_json_to({
            'type': 'invalid_type',
            'data': {}
        })
        
        # Receive error response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('message', response['data'])
        
        await communicator.disconnect()
        
    async def test_websocket_connection_limits(self):
        """Test WebSocket connection limits"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        
        # Create multiple connections for the same user
        communicators = []
        for i in range(3):
            communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
            communicator.scope['user'] = self.regular_user
            communicators.append(communicator)
        
        # Connect first two (should succeed)
        connected1, _ = await communicators[0].connect()
        connected2, _ = await communicators[1].connect()
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        
        # Try to connect third (should be limited)
        connected3, _ = await communicators[2].connect()
        self.assertFalse(connected3)
        
        # Clean up
        await communicators[0].disconnect()
        await communicators[1].disconnect()
        
    async def test_websocket_rate_limit_broadcast(self):
        """Test WebSocket rate limit event broadcasting"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to rate limit events
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'rate_limit_event'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Simulate rate limit event
        with patch('api.rate_limit.consumers.RateLimitConsumer.broadcast_rate_limit_event') as mock_broadcast:
            mock_broadcast.return_value = AsyncMock()
            
            # Create rate limit log
            await database_sync_to_async(RateLimitLog.objects.create)(
                user=self.regular_user,
                endpoint='/api/test/',
                method='GET',
                ip_address='192.168.1.100',
                status_code=429,
                is_allowed=False
            )
            
            # Verify broadcast was called
            await asyncio.sleep(0.1)  # Allow async operations to complete
            mock_broadcast.assert_called()
        
        await communicator.disconnect()
        
    async def test_websocket_abuse_report_notifications(self):
        """Test WebSocket abuse report notifications"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to abuse report notifications
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'abuse_report'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Create abuse report
        with patch('api.rate_limit.consumers.RateLimitConsumer.broadcast_abuse_report') as mock_broadcast:
            mock_broadcast.return_value = AsyncMock()
            
            await database_sync_to_async(AbuseReport.objects.create)(
                reporter=self.regular_user,
                reported_ip='192.168.1.100',
                reason='suspicious_activity',
                description='Multiple failed attempts'
            )
            
            # Verify broadcast was called
            await asyncio.sleep(0.1)
            mock_broadcast.assert_called()
        
        await communicator.disconnect()
        
    async def test_websocket_ip_block_notifications(self):
        """Test WebSocket IP block notifications"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to IP block notifications
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'ip_block'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Create IP block
        with patch('api.rate_limit.consumers.RateLimitConsumer.broadcast_ip_block') as mock_broadcast:
            mock_broadcast.return_value = AsyncMock()
            
            await database_sync_to_async(IPBlockList.objects.create)(
                ip_address='192.168.1.100',
                reason='malicious_activity',
                block_type='permanent',
                created_by=self.admin_user
            )
            
            # Verify broadcast was called
            await asyncio.sleep(0.1)
            mock_broadcast.assert_called()
        
        await communicator.disconnect()
        
    async def test_websocket_rate_limit_insights(self):
        """Test WebSocket rate limit insights"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to insights
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'rate_limit_insight'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Request insights
        await communicator.send_json_to({
            'type': 'get_insights',
            'data': {
                'timeframe': '1h'
            }
        })
        
        # Receive insights
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'insights_response')
        self.assertIn('insights', response['data'])
        self.assertIn('timeframe', response['data'])
        
        await communicator.disconnect()
        
    async def test_websocket_rate_limit_exceptions(self):
        """Test WebSocket rate limit exceptions"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to exceptions
        await communicator.send_json_to({
            'type': 'subscribe',
            'data': {
                'event_type': 'rate_limit_exception'
            }
        })
        
        # Receive confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Create rate limit exception
        with patch('api.rate_limit.consumers.RateLimitConsumer.broadcast_rate_limit_exception') as mock_broadcast:
            mock_broadcast.return_value = AsyncMock()
            
            await database_sync_to_async(RateLimitException.objects.create)(
                user=self.regular_user,
                reason='api_client',
                description='API client requires higher limits',
                multiplier=2.0,
                created_by=self.admin_user
            )
            
            # Verify broadcast was called
            await asyncio.sleep(0.1)
            mock_broadcast.assert_called()
        
        await communicator.disconnect()
        
    async def test_websocket_performance_metrics(self):
        """Test WebSocket performance metrics"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Request performance metrics
        await communicator.send_json_to({
            'type': 'get_performance_metrics',
            'data': {
                'timeframe': '1h'
            }
        })
        
        # Receive metrics
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'performance_metrics_response')
        self.assertIn('metrics', response['data'])
        self.assertIn('response_times', response['data']['metrics'])
        self.assertIn('throughput', response['data']['metrics'])
        
        await communicator.disconnect()
        
    async def test_websocket_connection_timeout(self):
        """Test WebSocket connection timeout handling"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate
        communicator.scope['user'] = self.regular_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Wait for timeout (simulated)
        await asyncio.sleep(0.1)
        
        # Send ping to check connection
        await communicator.send_json_to({
            'type': 'ping',
            'data': {}
        })
        
        # Should receive pong
        response = await communicator.receive_json_from(timeout=1)
        self.assertEqual(response['type'], 'pong')
        
        await communicator.disconnect()


class RateLimitConsumerIntegrationTest(TransactionTestCase):
    """Integration tests for RateLimitConsumer"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='regularpass123'
        )
        
    async def test_complete_rate_limit_monitoring_workflow(self):
        """Test complete rate limit monitoring workflow via WebSocket"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        
        # Authenticate as admin
        communicator.scope['user'] = self.admin_user
        
        # Connect
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to all events
        events = [
            'rate_limit_violation',
            'abuse_report',
            'ip_block',
            'rate_limit_insight',
            'rate_limit_exception'
        ]
        
        for event in events:
            await communicator.send_json_to({
                'type': 'subscribe',
                'data': {'event_type': event}
            })
            
            # Receive confirmation
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Get system stats
        await communicator.send_json_to({
            'type': 'get_system_stats',
            'data': {}
        })
        
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'system_stats_response')
        
        # Verify all subscriptions are active
        await communicator.send_json_to({
            'type': 'get_subscriptions',
            'data': {}
        })
        
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'subscriptions_response')
        self.assertEqual(len(response['data']['subscriptions']), len(events))
        
        await communicator.disconnect()
        
    async def test_multi_user_rate_limit_monitoring(self):
        """Test multi-user rate limit monitoring"""
        application = AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        
        # Create connections for multiple users
        admin_communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        admin_communicator.scope['user'] = self.admin_user
        
        user_communicator = WebsocketCommunicator(application, path='/ws/rate-limit/')
        user_communicator.scope['user'] = self.regular_user
        
        # Connect both users
        admin_connected, _ = await admin_communicator.connect()
        user_connected, _ = await user_communicator.connect()
        
        self.assertTrue(admin_connected)
        self.assertTrue(user_connected)
        
        # Admin subscribes to system monitoring
        await admin_communicator.send_json_to({
            'type': 'subscribe',
            'data': {'event_type': 'admin_monitoring'}
        })
        
        # User subscribes to personal monitoring
        await user_communicator.send_json_to({
            'type': 'subscribe',
            'data': {'event_type': 'user_rate_limit'}
        })
        
        # Receive confirmations
        admin_response = await admin_communicator.receive_json_from()
        user_response = await user_communicator.receive_json_from()
        
        self.assertEqual(admin_response['type'], 'subscription_confirmed')
        self.assertEqual(user_response['type'], 'subscription_confirmed')
        
        # Clean up
        await admin_communicator.disconnect()
        await user_communicator.disconnect()
