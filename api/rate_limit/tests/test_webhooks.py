"""
Comprehensive webhook tests for rate_limit module.

This test file covers all webhook endpoints, event processing,
authentication, signature verification, and webhook security.
"""

import json
import hashlib
import hmac
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.http import HttpResponse
from datetime import datetime, timedelta
import base64

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport,
    IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.webhooks import RateLimitWebhookView
from api.rate_limit.serializers import RateLimitWebhookSerializer

User = get_user_model()


class RateLimitWebhookViewTest(APITestCase):
    """Test cases for RateLimitWebhookView"""
    
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
        self.client = APIClient()
        
        # Create test webhook secret
        self.webhook_secret = 'test_webhook_secret_12345'
        
        # Create test rate limit config
        self.config = RateLimitConfig.objects.create(
            name='test_config',
            rate_limit_type='user',
            requests_per_unit=100,
            time_unit='hour',
            time_value=1,
            user=self.admin_user
        )
        
    def generate_webhook_signature(self, payload, secret):
        """Generate webhook signature for authentication"""
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
        
    def test_webhook_rate_limit_violation(self):
        """Test webhook for rate limit violation events"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/',
                'method': 'GET',
                'ip_address': '192.168.1.100',
                'user_agent': 'Mozilla/5.0',
                'status_code': 429,
                'limit_type': 'user',
                'limit_value': 100,
                'current_usage': 101
            }
        }
        
        # Generate signature
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        # Send webhook
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['event_processed'], True)
        
    def test_webhook_abuse_report(self):
        """Test webhook for abuse report events"""
        payload = {
            'event_type': 'abuse_report',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'reporter_id': self.admin_user.id,
                'reported_ip': '192.168.1.100',
                'reported_user': self.regular_user.id,
                'reason': 'suspicious_activity',
                'description': 'Multiple failed login attempts detected',
                'evidence': {
                    'attempts': 10,
                    'timeframe': '5 minutes',
                    'endpoints': ['/api/login/', '/api/auth/']
                }
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        # Verify abuse report was created
        self.assertTrue(AbuseReport.objects.filter(
            reporter=self.admin_user,
            reported_ip='192.168.1.100'
        ).exists())
        
    def test_webhook_ip_block(self):
        """Test webhook for IP block events"""
        payload = {
            'event_type': 'ip_block',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'ip_address': '192.168.1.100',
                'reason': 'malicious_activity',
                'block_type': 'permanent',
                'created_by': self.admin_user.id,
                'metadata': {
                    'source': 'automated_detection',
                    'confidence': 0.95
                }
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify IP block was created
        self.assertTrue(IPBlockList.objects.filter(
            ip_address='192.168.1.100',
            reason='malicious_activity'
        ).exists())
        
    def test_webhook_rate_limit_insight(self):
        """Test webhook for rate limit insight events"""
        payload = {
            'event_type': 'rate_limit_insight',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'insight_type': 'traffic_spike',
                'description': 'Unusual traffic pattern detected',
                'severity': 'medium',
                'endpoint': '/api/test/',
                'timeframe': '1h',
                'metrics': {
                    'normal_requests_per_minute': 50,
                    'current_requests_per_minute': 175,
                    'spike_factor': 3.5
                },
                'affected_users': [self.regular_user.id],
                'recommendations': ['Investigate source IPs', 'Consider temporary rate limiting']
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify insight was created
        self.assertTrue(RateLimitInsight.objects.filter(
            insight_type='traffic_spike',
            severity='medium'
        ).exists())
        
    def test_webhook_rate_limit_exception(self):
        """Test webhook for rate limit exception events"""
        payload = {
            'event_type': 'rate_limit_exception',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'reason': 'api_client',
                'description': 'API client requires higher rate limits',
                'multiplier': 2.0,
                'expires_at': (timezone.now() + timedelta(days=30)).isoformat(),
                'created_by': self.admin_user.id,
                'metadata': {
                    'client_type': 'mobile_app',
                    'version': '2.1.0'
                }
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify exception was created
        self.assertTrue(RateLimitException.objects.filter(
            user=self.regular_user,
            reason='api_client',
            multiplier=2.0
        ).exists())
        
    def test_webhook_authentication_failure(self):
        """Test webhook authentication failure"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/'
            }
        }
        
        # Send without signature
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        
    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/'
            }
        }
        
        # Send with invalid signature
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE='invalid_signature',
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        
    def test_webhook_invalid_payload(self):
        """Test webhook with invalid payload"""
        payload = {
            'event_type': 'invalid_event',
            'timestamp': timezone.now().isoformat(),
            'data': {}
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
    def test_webhook_missing_required_fields(self):
        """Test webhook with missing required fields"""
        payload = {
            'event_type': 'rate_limit_violation',
            # Missing timestamp
            'data': {
                'user_id': self.regular_user.id
                # Missing required fields
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
    def test_webhook_duplicate_event_handling(self):
        """Test webhook duplicate event handling"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/',
                'method': 'GET',
                'ip_address': '192.168.1.100',
                'event_id': 'unique_event_12345'  # Unique event identifier
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        # Send first webhook
        response1 = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Send duplicate webhook
        response2 = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['status'], 'success')
        self.assertEqual(response2.data['duplicate'], True)
        
    def test_webhook_batch_events(self):
        """Test webhook with batch events"""
        payload = {
            'event_type': 'batch_events',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'events': [
                    {
                        'event_type': 'rate_limit_violation',
                        'user_id': self.regular_user.id,
                        'endpoint': '/api/test1/',
                        'method': 'GET',
                        'ip_address': '192.168.1.100',
                        'status_code': 429
                    },
                    {
                        'event_type': 'rate_limit_violation',
                        'user_id': self.regular_user.id,
                        'endpoint': '/api/test2/',
                        'method': 'POST',
                        'ip_address': '192.168.1.100',
                        'status_code': 429
                    }
                ]
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['processed_events'], 2)
        
    def test_webhook_rate_limit_config_update(self):
        """Test webhook for rate limit config updates"""
        payload = {
            'event_type': 'rate_limit_config_update',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'config_id': self.config.id,
                'updates': {
                    'requests_per_unit': 150,
                    'is_active': False
                },
                'updated_by': self.admin_user.id,
                'reason': 'Performance optimization'
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify config was updated
        self.config.refresh_from_db()
        self.assertEqual(self.config.requests_per_unit, 150)
        self.assertFalse(self.config.is_active)
        
    def test_webhook_user_profile_update(self):
        """Test webhook for user profile updates"""
        profile = UserRateLimitProfile.objects.create(
            user=self.regular_user,
            risk_level='low',
            custom_rate_multiplier=1.0,
            is_trusted=True
        )
        
        payload = {
            'event_type': 'user_profile_update',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'updates': {
                    'risk_level': 'medium',
                    'custom_rate_multiplier': 0.8,
                    'is_trusted': False
                },
                'updated_by': self.admin_user.id,
                'reason': 'Suspicious activity detected'
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify profile was updated
        profile.refresh_from_db()
        self.assertEqual(profile.risk_level, 'medium')
        self.assertEqual(profile.custom_rate_multiplier, 0.8)
        self.assertFalse(profile.is_trusted)
        
    def test_webhook_system_health_check(self):
        """Test webhook for system health check"""
        payload = {
            'event_type': 'system_health_check',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'system_status': 'healthy',
                'metrics': {
                    'total_requests': 10000,
                    'blocked_requests': 500,
                    'average_response_time': 150,
                    'memory_usage': '65%',
                    'cpu_usage': '45%'
                },
                'services': {
                    'rate_limiter': 'healthy',
                    'database': 'healthy',
                    'cache': 'healthy',
                    'monitoring': 'healthy'
                }
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
    def test_webhook_security_headers(self):
        """Test webhook security headers"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/'
            }
        }
        
        signature = self.generate_webhook_signature(payload, self.webhook_secret)
        
        response = self.client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret,
            HTTP_X_FORWARDED_FOR='192.168.1.100',
            HTTP_USER_AGENT='Test-Webhook-Client/1.0'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check security headers in response
        self.assertIn('X-Content-Type-Options', response)
        self.assertIn('X-Frame-Options', response)
        self.assertIn('X-XSS-Protection', response)


class RateLimitWebhookIntegrationTest(TransactionTestCase):
    """Integration tests for rate limit webhooks"""
    
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
        self.webhook_secret = 'test_webhook_secret_12345'
        
    def test_complete_webhook_workflow(self):
        """Test complete webhook event processing workflow"""
        # Create rate limit violation
        violation_payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/',
                'method': 'GET',
                'ip_address': '192.168.1.100',
                'status_code': 429,
                'event_id': 'violation_12345'
            }
        }
        
        # Generate signature
        payload_bytes = json.dumps(violation_payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Send webhook
        client = APIClient()
        response = client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(violation_payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature_b64,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Create abuse report based on violation
        abuse_payload = {
            'event_type': 'abuse_report',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'reporter_id': self.admin_user.id,
                'reported_ip': '192.168.1.100',
                'reason': 'rate_limit_abuse',
                'description': 'Excessive rate limit violations',
                'related_event_id': 'violation_12345'
            }
        }
        
        payload_bytes = json.dumps(abuse_payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        response = client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(abuse_payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature_b64,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Create IP block based on abuse report
        block_payload = {
            'event_type': 'ip_block',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'ip_address': '192.168.1.100',
                'reason': 'automated_block',
                'block_type': 'temporary',
                'duration_hours': 24,
                'related_abuse_report_id': AbuseReport.objects.first().id
            }
        }
        
        payload_bytes = json.dumps(block_payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        response = client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(block_payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature_b64,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify all objects were created
        self.assertEqual(RateLimitLog.objects.filter(
            user=self.regular_user,
            endpoint='/api/test/'
        ).count(), 1)
        
        self.assertEqual(AbuseReport.objects.filter(
            reporter=self.admin_user,
            reported_ip='192.168.1.100'
        ).count(), 1)
        
        self.assertEqual(IPBlockList.objects.filter(
            ip_address='192.168.1.100'
        ).count(), 1)
        
    def test_webhook_error_recovery(self):
        """Test webhook error recovery and retry logic"""
        payload = {
            'event_type': 'rate_limit_violation',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'user_id': self.regular_user.id,
                'endpoint': '/api/test/',
                'method': 'GET',
                'ip_address': '192.168.1.100',
                'status_code': 429
            }
        }
        
        # Generate signature
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        client = APIClient()
        
        # Simulate temporary database error with patch
        with patch('api.rate_limit.models.RateLimitLog.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database temporarily unavailable")
            
            response = client.post(
                '/api/rate-limit/webhooks/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature_b64,
                HTTP_X_WEBHOOK_SECRET=self.webhook_secret
            )
            
            # Should return error but not crash
            self.assertEqual(response.status_code, 500)
            self.assertIn('error', response.data)
        
        # Retry should succeed
        response = client.post(
            '/api/rate-limit/webhooks/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature_b64,
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
