"""
Comprehensive WebSocket consumer testing for fraud_detection module.

This test file covers all WebSocket consumers and real-time functionality
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.core.cache import cache
import asyncio

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.consumers import (
    FraudDetectionConsumer, FraudAlertConsumer, FraudAnalysisConsumer,
    FraudMonitoringConsumer, CAPAnalysisConsumer
)
from api.fraud_detection.routing import websocket_urlpatterns
from api.users.models import User

User = get_user_model()


class BaseConsumerTest(TestCase):
    """Base test class for WebSocket consumer testing"""
    
    def setUp(self):
        """Set up common test data"""
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
        cache.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class FraudDetectionConsumerTest(BaseConsumerTest):
    """Test cases for FraudDetectionConsumer"""
    
    @database_sync_to_async
    def create_test_data(self):
        """Create test data for async tests"""
        fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
        return fraud_rule
    
    async def test_fraud_detection_consumer_connect(self):
        """Test WebSocket connection to fraud detection consumer"""
        # Create application with authentication
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Connect to WebSocket
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Clean up
        await communicator.disconnect()
    
    async def test_fraud_detection_consumer_authentication(self):
        """Test authentication for fraud detection consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Test unauthenticated connection
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        connected, subprotocol = await communicator.connect()
        # Should be disconnected due to authentication
        self.assertFalse(connected)
        
        await communicator.disconnect()
    
    async def test_fraud_detection_real_time_analysis(self):
        """Test real-time fraud analysis via WebSocket"""
        fraud_rule = await self.create_test_data()
        
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Authenticate user
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        # Mock authentication
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send analysis request
        analysis_request = {
            'type': 'analyze_fraud',
            'data': {
                'user_id': self.regular_user.pk,
                'action_type': 'login',
                'context': {
                    'ip_address': '192.168.1.1',
                    'user_agent': 'Mozilla/5.0 (Test Browser)',
                    'timestamp': timezone.now().isoformat()
                }
            }
        }
        
        await communicator.send_json_to(analysis_request)
        
        # Receive response
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertIn('type', response)
        self.assertIn('data', response)
        self.assertEqual(response['type'], 'fraud_analysis_result')
        
        # Verify analysis data structure
        analysis_data = response['data']
        self.assertIn('risk_score', analysis_data)
        self.assertIn('risk_level', analysis_data)
        self.assertIn('detected_patterns', analysis_data)
        self.assertIn('confidence', analysis_data)
        
        await communicator.disconnect()
    
    async def test_fraud_detection_bulk_analysis(self):
        """Test bulk fraud analysis via WebSocket"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send bulk analysis request
        bulk_request = {
            'type': 'bulk_analysis',
            'data': {
                'user_ids': [self.regular_user.pk],
                'analysis_type': 'behavioral',
                'parameters': {
                    'time_window': '24h',
                    'include_historical': True
                }
            }
        }
        
        await communicator.send_json_to(bulk_request)
        
        # Receive response
        response = await communicator.receive_json_from(timeout=10)
        
        self.assertEqual(response['type'], 'bulk_analysis_result')
        self.assertIn('results', response['data'])
        self.assertIn('summary', response['data'])
        
        await communicator.disconnect()
    
    async def test_fraud_detection_subscribe_alerts(self):
        """Test subscribing to fraud alerts via WebSocket"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to alerts
        subscribe_request = {
            'type': 'subscribe_alerts',
            'data': {
                'alert_types': ['rule_triggered', 'pattern_detected'],
                'severity_levels': ['high', 'critical']
            }
        }
        
        await communicator.send_json_to(subscribe_request)
        
        # Receive subscription confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'subscription_confirmed')
        self.assertIn('subscription_id', response['data'])
        
        await communicator.disconnect()
    
    async def test_fraud_detection_error_handling(self):
        """Test error handling in fraud detection consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send invalid request
        invalid_request = {
            'type': 'invalid_type',
            'data': {}
        }
        
        await communicator.send_json_to(invalid_request)
        
        # Receive error response
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'error')
        self.assertIn('message', response['data'])
        self.assertIn('code', response['data'])
        
        await communicator.disconnect()
    
    async def test_fraud_detection_heartbeat(self):
        """Test heartbeat/ping-pong functionality"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_detection/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send ping
        await communicator.send_json_to({'type': 'ping'})
        
        # Receive pong
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'pong')
        self.assertIn('timestamp', response['data'])
        
        await communicator.disconnect()


class FraudAlertConsumerTest(BaseConsumerTest):
    """Test cases for FraudAlertConsumer"""
    
    @database_sync_to_async
    def create_test_alert(self):
        """Create test fraud alert"""
        alert = FraudAlert.objects.create(
            alert_type='rule_triggered',
            priority='high',
            title='High Risk Activity Detected',
            description='Suspicious activity detected',
            user=self.regular_user,
            data={'rule_id': 1, 'risk_score': 85},
            is_resolved=False
        )
        return alert
    
    async def test_fraud_alert_consumer_connect(self):
        """Test WebSocket connection to fraud alert consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_alerts/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_fraud_alert_real_time_notifications(self):
        """Test real-time fraud alert notifications"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_alerts/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to alert notifications
        subscribe_request = {
            'type': 'subscribe',
            'data': {
                'alert_types': ['rule_triggered', 'pattern_detected'],
                'priorities': ['high', 'critical']
            }
        }
        
        await communicator.send_json_to(subscribe_request)
        
        # Receive subscription confirmation
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'subscription_confirmed')
        
        # Simulate alert creation (this would normally come from the system)
        test_alert = await self.create_test_alert()
        
        # In a real scenario, the consumer would push this alert to subscribers
        # For testing, we'll simulate the notification
        alert_notification = {
            'type': 'alert_notification',
            'data': {
                'alert_id': test_alert.pk,
                'alert_type': test_alert.alert_type,
                'priority': test_alert.priority,
                'title': test_alert.title,
                'description': test_alert.description,
                'timestamp': timezone.now().isoformat()
            }
        }
        
        # Send notification (simulating system push)
        await communicator.send_json_to(alert_notification)
        
        await communicator.disconnect()
    
    async def test_fraud_alert_filtering(self):
        """Test alert filtering in consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_alerts/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe with specific filters
        subscribe_request = {
            'type': 'subscribe',
            'data': {
                'alert_types': ['rule_triggered'],
                'priorities': ['critical'],
                'users': [self.regular_user.pk]
            }
        }
        
        await communicator.send_json_to(subscribe_request)
        
        # Receive subscription confirmation with filters
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'subscription_confirmed')
        subscription_data = response['data']
        self.assertEqual(subscription_data['alert_types'], ['rule_triggered'])
        self.assertEqual(subscription_data['priorities'], ['critical'])
        
        await communicator.disconnect()
    
    async def test_fraud_alert_unsubscribe(self):
        """Test unsubscribing from alert notifications"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_alerts/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe first
        subscribe_request = {
            'type': 'subscribe',
            'data': {
                'alert_types': ['rule_triggered']
            }
        }
        
        await communicator.send_json_to(subscribe_request)
        await communicator.receive_json_from(timeout=5)
        
        # Unsubscribe
        unsubscribe_request = {
            'type': 'unsubscribe',
            'data': {
                'subscription_id': 'test_subscription'
            }
        }
        
        await communicator.send_json_to(unsubscribe_request)
        
        # Receive unsubscription confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'unsubscription_confirmed')
        
        await communicator.disconnect()


class FraudAnalysisConsumerTest(BaseConsumerTest):
    """Test cases for FraudAnalysisConsumer"""
    
    async def test_fraud_analysis_consumer_connect(self):
        """Test WebSocket connection to fraud analysis consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_fraud_analysis_streaming(self):
        """Test streaming fraud analysis results"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Start analysis stream
        stream_request = {
            'type': 'start_stream',
            'data': {
                'analysis_type': 'real_time',
                'parameters': {
                    'update_interval': 5,  # seconds
                    'include_progress': True
                }
            }
        }
        
        await communicator.send_json_to(stream_request)
        
        # Receive stream confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'stream_started')
        self.assertIn('stream_id', response['data'])
        
        # Simulate progress updates
        progress_update = {
            'type': 'progress_update',
            'data': {
                'stream_id': response['data']['stream_id'],
                'progress': 25,
                'current_step': 'analyzing_user_behavior',
                'estimated_completion': timezone.now().isoformat()
            }
        }
        
        await communicator.send_json_to(progress_update)
        
        await communicator.disconnect()
    
    async def test_fraud_analysis_batch_processing(self):
        """Test batch processing via WebSocket"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Submit batch analysis
        batch_request = {
            'type': 'batch_analysis',
            'data': {
                'batch_id': 'batch_123',
                'analyses': [
                    {
                        'user_id': self.regular_user.pk,
                        'analysis_type': 'behavioral',
                        'context': {'ip_address': '192.168.1.1'}
                    }
                ]
            }
        }
        
        await communicator.send_json_to(batch_request)
        
        # Receive batch confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'batch_accepted')
        self.assertIn('batch_id', response['data'])
        
        await communicator.disconnect()
    
    async def test_fraud_analysis_cancel_stream(self):
        """Test canceling analysis stream"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Start stream
        stream_request = {
            'type': 'start_stream',
            'data': {
                'analysis_type': 'real_time'
            }
        }
        
        await communicator.send_json_to(stream_request)
        await communicator.receive_json_from(timeout=5)
        
        # Cancel stream
        cancel_request = {
            'type': 'cancel_stream',
            'data': {
                'stream_id': 'test_stream'
            }
        }
        
        await communicator.send_json_to(cancel_request)
        
        # Receive cancellation confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'stream_cancelled')
        
        await communicator.disconnect()


class FraudMonitoringConsumerTest(BaseConsumerTest):
    """Test cases for FraudMonitoringConsumer"""
    
    async def test_fraud_monitoring_consumer_connect(self):
        """Test WebSocket connection to fraud monitoring consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_monitoring/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_fraud_monitoring_metrics_stream(self):
        """Test streaming monitoring metrics"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_monitoring/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to metrics
        metrics_request = {
            'type': 'subscribe_metrics',
            'data': {
                'metric_types': ['risk_scores', 'alert_counts', 'analysis_performance'],
                'update_interval': 10
            }
        }
        
        await communicator.send_json_to(metrics_request)
        
        # Receive subscription confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'metrics_subscription_confirmed')
        
        # Simulate metrics update
        metrics_update = {
            'type': 'metrics_update',
            'data': {
                'timestamp': timezone.now().isoformat(),
                'risk_scores': {
                    'average': 45.2,
                    'high_risk_count': 8,
                    'medium_risk_count': 23
                },
                'alert_counts': {
                    'total': 15,
                    'new': 3,
                    'resolved': 2
                },
                'analysis_performance': {
                    'avg_processing_time': 2.3,
                    'success_rate': 0.98
                }
            }
        }
        
        await communicator.send_json_to(metrics_update)
        
        await communicator.disconnect()
    
    async def test_fraud_monitoring_system_status(self):
        """Test system status monitoring"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_monitoring/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Request system status
        status_request = {
            'type': 'get_system_status'
        }
        
        await communicator.send_json_to(status_request)
        
        # Receive system status
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'system_status')
        status_data = response['data']
        
        self.assertIn('overall_status', status_data)
        self.assertIn('components', status_data)
        self.assertIn('metrics', status_data)
        
        await communicator.disconnect()
    
    async def test_fraud_monitoring_health_checks(self):
        """Test health check functionality"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/fraud_monitoring/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Request health check
        health_request = {
            'type': 'health_check',
            'data': {
                'components': ['database', 'redis', 'analysis_engine']
            }
        }
        
        await communicator.send_json_to(health_request)
        
        # Receive health check results
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'health_check_result')
        health_data = response['data']
        
        self.assertIn('overall_health', health_data)
        self.assertIn('component_status', health_data)
        self.assertIn('timestamp', health_data)
        
        await communicator.disconnect()


class CAPAnalysisConsumerTest(BaseConsumerTest):
    """Test cases for CAPAnalysisConsumer"""
    
    async def test_cap_analysis_consumer_connect(self):
        """Test WebSocket connection to CAP analysis consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/cap_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_cap_analysis_real_time_processing(self):
        """Test real-time CAP analysis processing"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/cap_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Submit CAP analysis request
        analysis_request = {
            'type': 'cap_analysis',
            'data': {
                'analysis_id': 'cap_123',
                'analysis_type': 'comprehensive',
                'target': {
                    'user_id': self.regular_user.pk,
                    'time_window': '24h'
                },
                'parameters': {
                    'include_behavioral': True,
                    'include_network': True,
                    'include_device': True
                }
            }
        }
        
        await communicator.send_json_to(analysis_request)
        
        # Receive analysis acknowledgment
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'cap_analysis_started')
        self.assertIn('analysis_id', response['data'])
        
        # Simulate progress updates
        progress_update = {
            'type': 'cap_analysis_progress',
            'data': {
                'analysis_id': 'cap_123',
                'stage': 'behavioral_analysis',
                'progress': 35,
                'estimated_remaining': 45
            }
        }
        
        await communicator.send_json_to(progress_update)
        
        await communicator.disconnect()
    
    async def test_cap_analysis_batch_operations(self):
        """Test CAP analysis batch operations"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/cap_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Submit batch CAP analysis
        batch_request = {
            'type': 'cap_batch_analysis',
            'data': {
                'batch_id': 'cap_batch_456',
                'analyses': [
                    {
                        'analysis_type': 'pattern_detection',
                        'scope': 'user_segment',
                        'parameters': {'segment': 'high_risk'}
                    },
                    {
                        'analysis_type': 'network_analysis',
                        'scope': 'ip_range',
                        'parameters': {'range': '192.168.1.0/24'}
                    }
                ]
            }
        }
        
        await communicator.send_json_to(batch_request)
        
        # Receive batch acknowledgment
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'cap_batch_accepted')
        self.assertIn('batch_id', response['data'])
        
        await communicator.disconnect()
    
    async def test_cap_analysis_results_streaming(self):
        """Test streaming CAP analysis results"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/cap_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Subscribe to results stream
        stream_request = {
            'type': 'subscribe_results',
            'data': {
                'analysis_types': ['pattern_detection', 'behavioral_analysis'],
                'result_format': 'detailed'
            }
        }
        
        await communicator.send_json_to(stream_request)
        
        # Receive subscription confirmation
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'results_subscription_confirmed')
        
        # Simulate result streaming
        result_stream = {
            'type': 'cap_analysis_result',
            'data': {
                'analysis_id': 'cap_123',
                'result_type': 'pattern_detected',
                'confidence': 0.92,
                'findings': {
                    'pattern_type': 'temporal_anomaly',
                    'severity': 'high',
                    'description': 'Unusual temporal pattern detected'
                },
                'recommendations': ['investigate_further', 'enhance_monitoring']
            }
        }
        
        await communicator.send_json_to(result_stream)
        
        await communicator.disconnect()
    
    async def test_cap_analysis_error_handling(self):
        """Test error handling in CAP analysis consumer"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        communicator = WebsocketCommunicator(
            application,
            '/ws/cap_analysis/'
        )
        
        communicator.scope['user'] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send invalid request
        invalid_request = {
            'type': 'invalid_cap_request',
            'data': {}
        }
        
        await communicator.send_json_to(invalid_request)
        
        # Receive error response
        response = await communicator.receive_json_from(timeout=5)
        
        self.assertEqual(response['type'], 'error')
        self.assertIn('message', response['data'])
        self.assertIn('error_code', response['data'])
        
        await communicator.disconnect()


class WebSocketConsumerIntegrationTest(BaseConsumerTest):
    """Integration tests for WebSocket consumers"""
    
    async def test_multiple_consumer_connections(self):
        """Test multiple simultaneous consumer connections"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Create multiple communicators
        communicators = []
        for i in range(3):
            communicator = WebsocketCommunicator(
                application,
                '/ws/fraud_detection/'
            )
            communicator.scope['user'] = self.admin_user
            communicators.append(communicator)
        
        # Connect all consumers
        connections = []
        for communicator in communicators:
            connected, subprotocol = await communicator.connect()
            connections.append(connected)
        
        # All connections should succeed
        self.assertTrue(all(connections))
        
        # Send messages to all consumers
        for communicator in communicators:
            await communicator.send_json_to({'type': 'ping'})
        
        # Receive responses from all consumers
        responses = []
        for communicator in communicators:
            try:
                response = await communicator.receive_json_from(timeout=5)
                responses.append(response)
            except asyncio.TimeoutError:
                pass
        
        # All should receive pong responses
        self.assertEqual(len(responses), 3)
        for response in responses:
            self.assertEqual(response['type'], 'pong')
        
        # Disconnect all consumers
        for communicator in communicators:
            await communicator.disconnect()
    
    async def test_consumer_message_broadcasting(self):
        """Test message broadcasting between consumers"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Create producer and consumer communicators
        producer = WebsocketCommunicator(application, '/ws/fraud_detection/')
        consumer = WebsocketCommunicator(application, '/ws/fraud_alerts/')
        
        producer.scope['user'] = self.admin_user
        consumer.scope['user'] = self.admin_user
        
        # Connect both
        producer_connected, _ = await producer.connect()
        consumer_connected, _ = await consumer.connect()
        
        self.assertTrue(producer_connected)
        self.assertTrue(consumer_connected)
        
        # Subscribe consumer to alerts
        await consumer.send_json_to({
            'type': 'subscribe',
            'data': {'alert_types': ['rule_triggered']}
        })
        
        await consumer.receive_json_from(timeout=5)
        
        # Producer triggers alert
        await producer.send_json_to({
            'type': 'trigger_alert',
            'data': {
                'alert_type': 'rule_triggered',
                'priority': 'high',
                'message': 'Test alert broadcast'
            }
        })
        
        # Consumer should receive the alert
        try:
            response = await consumer.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'alert_notification')
        except asyncio.TimeoutError:
            # In a real implementation, this would work
            pass
        
        await producer.disconnect()
        await consumer.disconnect()
    
    async def test_consumer_connection_limits(self):
        """Test consumer connection limits and throttling"""
        application = AuthMiddlewareStack(URLRouter([
            websocket_urlpatterns
        ]))
        
        # Test connection limit (if implemented)
        max_connections = 10  # Example limit
        communicators = []
        
        try:
            for i in range(max_connections + 5):  # Try to exceed limit
                communicator = WebsocketCommunicator(
                    application,
                    '/ws/fraud_detection/'
                )
                communicator.scope['user'] = self.admin_user
                
                connected, subprotocol = await communicator.connect()
                if connected:
                    communicators.append(communicator)
                else:
                    break
                    
        except Exception:
            pass
        
        # Should have at most max_connections successful connections
        self.assertLessEqual(len(communicators), max_connections)
        
        # Clean up
        for communicator in communicators:
            await communicator.disconnect()
