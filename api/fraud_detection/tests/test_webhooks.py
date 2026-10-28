"""
Comprehensive webhook endpoint testing for fraud_detection module.

This test file covers all webhook functionality and external integrations
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.http import HttpResponse
import hashlib
import hmac
import base64

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase
)
from api.fraud_detection.webhooks import (
    FraudWebhookView, FraudAlertWebhookView, FraudAnalysisWebhookView,
    ExternalSystemWebhookView, CAPWebhookView
)
from api.fraud_detection.services import FraudDetectionService
from api.users.models import User

User = get_user_model()


class BaseWebhookTest(TestCase):
    """Base test class for webhook testing"""
    
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
        
        # Webhook configuration
        self.webhook_secret = 'test_webhook_secret_key_12345'
        self.webhook_url = '/webhooks/fraud_detection/'
        
        cache.clear()
    
    def generate_webhook_signature(self, payload, secret=None):
        """Generate HMAC signature for webhook payload"""
        if secret is None:
            secret = self.webhook_secret
            
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()


class FraudWebhookViewTest(BaseWebhookTest):
    """Test cases for FraudWebhookView"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
    
    def test_fraud_webhook_invalid_method(self):
        """Test webhook with invalid HTTP method"""
        url = reverse('frauddetection:fraud-webhook')
        
        # Test GET request (should fail)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Test PUT request (should fail)
        response = self.client.put(url, {}, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_fraud_webhook_missing_signature(self):
        """Test webhook without signature"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85,
                'risk_level': 'high'
            }
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.json())
    
    def test_fraud_webhook_invalid_signature(self):
        """Test webhook with invalid signature"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85,
                'risk_level': 'high'
            }
        }
        
        # Generate signature with wrong secret
        wrong_signature = self.generate_webhook_signature(payload, 'wrong_secret')
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=wrong_signature
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_fraud_webhook_valid_signature(self):
        """Test webhook with valid signature"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85,
                'risk_level': 'high',
                'detected_rules': [self.fraud_rule.pk],
                'evidence': {
                    'ip_address': '192.168.1.1',
                    'user_agent': 'Mozilla/5.0 (Test Browser)',
                    'timestamp': timezone.now().isoformat()
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'external_system'
        }
        
        # Generate valid signature
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.return_value = {
                'processed': True,
                'fraud_attempt_id': 123,
                'alert_created': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            response_data = response.json()
            self.assertIn('status', response_data)
            self.assertIn('processed', response_data)
            self.assertEqual(response_data['status'], 'success')
    
    def test_fraud_webhook_invalid_payload(self):
        """Test webhook with invalid payload"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'invalid_event',  # Invalid event type
            'data': {}  # Missing required fields
        }
        
        signature = self.generate_webhook_signature(payload)
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
    
    def test_fraud_webhook_fraud_detected_event(self):
        """Test processing fraud_detected event"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 92,
                'risk_level': 'critical',
                'attempt_type': 'account_takeover',
                'detected_patterns': ['suspicious_login', 'unusual_device'],
                'evidence': {
                    'ip_address': '192.168.1.100',
                    'device_fingerprint': 'abc123def456',
                    'location': {'country': 'CN', 'city': 'Beijing'},
                    'timestamp': timezone.now().isoformat()
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'security_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.return_value = {
                'processed': True,
                'fraud_attempt_id': 456,
                'alert_created': True,
                'user_risk_updated': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify service was called with correct data
            mock_service.process_webhook_event.assert_called_once()
            call_args = mock_service.process_webhook_event.call_args[0][0]
            self.assertEqual(call_args['event_type'], 'fraud_detected')
            self.assertEqual(call_args['data']['user_id'], self.regular_user.pk)
            self.assertEqual(call_args['data']['fraud_score'], 92)
    
    def test_fraud_webhook_user_risk_updated_event(self):
        """Test processing user_risk_updated event"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'user_risk_updated',
            'data': {
                'user_id': self.regular_user.pk,
                'previous_risk_score': 45,
                'new_risk_score': 78,
                'risk_factors': {
                    'new_device': True,
                    'suspicious_location': True,
                    'unusual_behavior': True
                },
                'reason': 'Multiple suspicious activities detected'
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'risk_assessment_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.return_value = {
                'processed': True,
                'risk_profile_updated': True,
                'alerts_created': 2
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_fraud_webhook_rate_limiting(self):
        """Test webhook rate limiting"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85
            }
        }
        
        signature = self.generate_webhook_signature(payload)
        
        # Mock rate limiting
        with patch('api.fraud_detection.webhooks.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = False  # Rate limited
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_fraud_webhook_duplicate_detection(self):
        """Test duplicate event detection"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85,
                'event_id': 'unique_event_123'  # Unique identifier
            }
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.is_duplicate_event') as mock_duplicate:
            mock_duplicate.return_value = True  # Duplicate event
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = response.json()
            self.assertEqual(response_data['status'], 'duplicate')
    
    def test_fraud_webhook_error_handling(self):
        """Test webhook error handling"""
        url = reverse('frauddetection:fraud-webhook')
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85
            }
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.side_effect = Exception("Service error")
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            response_data = response.json()
            self.assertIn('error', response_data)


class FraudAlertWebhookViewTest(BaseWebhookTest):
    """Test cases for FraudAlertWebhookView"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.fraud_alert = FraudAlert.objects.create(
            alert_type='rule_triggered',
            priority='high',
            title='High Risk Activity Detected',
            description='Suspicious activity detected',
            user=self.regular_user,
            data={'rule_id': 1, 'risk_score': 85},
            is_resolved=False
        )
    
    def test_fraud_alert_webhook_alert_created(self):
        """Test processing alert_created event"""
        url = reverse('frauddetection:fraud-alert-webhook')
        payload = {
            'event_type': 'alert_created',
            'data': {
                'alert_id': self.fraud_alert.pk,
                'alert_type': self.fraud_alert.alert_type,
                'priority': self.fraud_alert.priority,
                'title': self.fraud_alert.title,
                'user_id': self.regular_user.pk,
                'risk_score': 85,
                'triggered_rules': [1, 2],
                'evidence': {
                    'ip_address': '192.168.1.1',
                    'timestamp': timezone.now().isoformat()
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'fraud_detection_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudAlertService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_alert_webhook.return_value = {
                'processed': True,
                'notifications_sent': True,
                'escalation_triggered': False
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_fraud_alert_webhook_alert_resolved(self):
        """Test processing alert_resolved event"""
        url = reverse('frauddetection:fraud-alert-webhook')
        payload = {
            'event_type': 'alert_resolved',
            'data': {
                'alert_id': self.fraud_alert.pk,
                'resolved_by': self.admin_user.pk,
                'resolution_notes': 'Investigation completed - false positive',
                'resolution_time': timezone.now().isoformat(),
                'action_taken': 'no_action'
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'fraud_management_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudAlertService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_alert_webhook.return_value = {
                'processed': True,
                'case_closed': True,
                'notifications_sent': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_fraud_alert_webhook_bulk_alerts(self):
        """Test processing bulk alerts"""
        url = reverse('frauddetection:fraud-alert-webhook')
        payload = {
            'event_type': 'bulk_alerts',
            'data': {
                'alerts': [
                    {
                        'alert_type': 'pattern_detected',
                        'priority': 'medium',
                        'title': 'Suspicious Pattern',
                        'user_id': self.regular_user.pk,
                        'risk_score': 65
                    },
                    {
                        'alert_type': 'threshold_exceeded',
                        'priority': 'high',
                        'title': 'Risk Threshold Exceeded',
                        'user_id': self.regular_user.pk,
                        'risk_score': 88
                    }
                ],
                'batch_id': 'batch_123',
                'total_count': 2
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'batch_processing_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudAlertService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_bulk_alerts.return_value = {
                'processed': True,
                'alerts_created': 2,
                'notifications_sent': True,
                'escalation_triggered': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class FraudAnalysisWebhookViewTest(BaseWebhookTest):
    """Test cases for FraudAnalysisWebhookView"""
    
    def test_fraud_analysis_webhook_analysis_completed(self):
        """Test processing analysis_completed event"""
        url = reverse('frauddetection:fraud-analysis-webhook')
        payload = {
            'event_type': 'analysis_completed',
            'data': {
                'analysis_id': 'analysis_123',
                'user_id': self.regular_user.pk,
                'analysis_type': 'behavioral',
                'results': {
                    'risk_score': 72,
                    'risk_level': 'medium',
                    'confidence': 0.85,
                    'detected_patterns': ['unusual_login_times'],
                    'recommendations': ['monitor_user', 'additional_verification']
                },
                'processing_time': 2.3,
                'completed_at': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'analysis_engine'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_analysis_result.return_value = {
                'processed': True,
                'risk_profile_updated': True,
                'alerts_created': 1,
                'recommendations_applied': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_fraud_analysis_webhook_batch_analysis(self):
        """Test processing batch analysis results"""
        url = reverse('frauddetection:fraud-analysis-webhook')
        payload = {
            'event_type': 'batch_analysis_completed',
            'data': {
                'batch_id': 'batch_456',
                'analysis_type': 'comprehensive',
                'results': [
                    {
                        'user_id': self.regular_user.pk,
                        'risk_score': 65,
                        'risk_level': 'medium',
                        'patterns_found': 2
                    }
                ],
                'summary': {
                    'total_analyzed': 1,
                    'high_risk_count': 0,
                    'medium_risk_count': 1,
                    'low_risk_count': 0
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'batch_analysis_engine'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_batch_analysis_result.return_value = {
                'processed': True,
                'profiles_updated': 1,
                'alerts_created': 0,
                'reports_generated': 1
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class ExternalSystemWebhookViewTest(BaseWebhookTest):
    """Test cases for ExternalSystemWebhookView"""
    
    def test_external_system_webhook_user_created(self):
        """Test processing user_created event from external system"""
        url = reverse('frauddetection:external-system-webhook')
        payload = {
            'event_type': 'user_created',
            'data': {
                'user_id': self.regular_user.pk,
                'username': self.regular_user.username,
                'email': self.regular_user.email,
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0 (Test Browser)',
                'registration_source': 'web_form',
                'timestamp': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'user_management_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.ExternalSystemService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_user_event.return_value = {
                'processed': True,
                'risk_profile_created': True,
                'initial_analysis_completed': True,
                'risk_score': 25
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_external_system_webhook_transaction_completed(self):
        """Test processing transaction_completed event"""
        url = reverse('frauddetection:external-system-webhook')
        payload = {
            'event_type': 'transaction_completed',
            'data': {
                'transaction_id': 'txn_123',
                'user_id': self.regular_user.pk,
                'amount': 1500.00,
                'currency': 'USD',
                'transaction_type': 'payment',
                'merchant': 'Test Merchant',
                'ip_address': '192.168.1.1',
                'device_id': 'device_123',
                'timestamp': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'payment_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.ExternalSystemService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_transaction_event.return_value = {
                'processed': True,
                'fraud_score_calculated': True,
                'risk_level': 'medium',
                'alerts_triggered': 0
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_external_system_webhook_login_attempt(self):
        """Test processing login_attempt event"""
        url = reverse('frauddetection:external-system-webhook')
        payload = {
            'event_type': 'login_attempt',
            'data': {
                'user_id': self.regular_user.pk,
                'login_result': 'success',
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0 (Test Browser)',
                'device_fingerprint': 'abc123def456',
                'location': {
                    'country': 'US',
                    'city': 'New York',
                    'latitude': 40.7128,
                    'longitude': -74.0060
                },
                'timestamp': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'authentication_system'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.ExternalSystemService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_login_event.return_value = {
                'processed': True,
                'behavior_updated': True,
                'risk_score_affected': False,
                'anomalies_detected': 0
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class CAPWebhookViewTest(BaseWebhookTest):
    """Test cases for CAPWebhookView"""
    
    def test_cap_webhook_analysis_completed(self):
        """Test processing CAP analysis completed event"""
        url = reverse('frauddetection:cap-webhook')
        payload = {
            'event_type': 'cap_analysis_completed',
            'data': {
                'analysis_id': 'cap_analysis_123',
                'analysis_type': 'comprehensive',
                'target': {
                    'user_id': self.regular_user.pk,
                    'scope': 'individual'
                },
                'results': {
                    'overall_risk_score': 68,
                    'risk_level': 'medium',
                    'confidence': 0.91,
                    'detected_patterns': [
                        {
                            'pattern_id': 'behavior_anomaly_001',
                            'pattern_type': 'temporal',
                            'severity': 'medium',
                            'confidence': 0.88
                        }
                    ],
                    'recommendations': [
                        'enhanced_monitoring',
                        'additional_verification'
                    ]
                },
                'processing_metrics': {
                    'processing_time': 4.2,
                    'data_points_analyzed': 1250,
                    'algorithms_used': ['behavioral', 'network', 'device']
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'cap_analysis_engine'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_cap_analysis_result.return_value = {
                'processed': True,
                'risk_profile_updated': True,
                'patterns_stored': 1,
                'alerts_created': 0,
                'recommendations_applied': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_webhook_pattern_detected(self):
        """Test processing CAP pattern detected event"""
        url = reverse('frauddetection:cap-webhook')
        payload = {
            'event_type': 'cap_pattern_detected',
            'data': {
                'pattern_id': 'pattern_456',
                'pattern_type': 'network_anomaly',
                'severity': 'high',
                'confidence': 0.94,
                'affected_entities': {
                    'users': [self.regular_user.pk],
                    'ip_addresses': ['192.168.1.1', '192.168.1.2'],
                    'devices': ['device_123', 'device_456']
                },
                'pattern_details': {
                    'description': 'Suspicious network activity pattern detected',
                    'characteristics': ['unusual_timing', 'multiple_connections'],
                    'risk_factors': ['shared_network', 'coordinated_behavior']
                },
                'detection_timestamp': timezone.now().isoformat()
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'cap_pattern_engine'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_pattern_detection.return_value = {
                'processed': True,
                'pattern_stored': True,
                'alerts_triggered': 2,
                'investigations_initiated': 1
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cap_webhook_batch_analysis(self):
        """Test processing CAP batch analysis event"""
        url = reverse('frauddetection:cap-webhook')
        payload = {
            'event_type': 'cap_batch_analysis_completed',
            'data': {
                'batch_id': 'cap_batch_789',
                'batch_type': 'user_segment',
                'segment_criteria': {
                    'risk_level': 'high',
                    'activity_period': '30d'
                },
                'results': {
                    'total_analyzed': 50,
                    'patterns_detected': 3,
                    'high_risk_users': 8,
                    'medium_risk_users': 15,
                    'low_risk_users': 27
                },
                'patterns': [
                    {
                        'pattern_id': 'coordinated_behavior_001',
                        'affected_users': 5,
                        'severity': 'high'
                    }
                ]
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'cap_batch_engine'
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.CAPAnalysisService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_batch_analysis_result.return_value = {
                'processed': True,
                'patterns_stored': 3,
                'risk_profiles_updated': 50,
                'alerts_created': 8,
                'report_generated': True
            }
            
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class WebhookIntegrationTest(BaseWebhookTest):
    """Integration tests for webhook functionality"""
    
    def test_webhook_end_to_end_flow(self):
        """Test complete webhook flow from external system to internal processing"""
        # Step 1: External system sends fraud detection event
        fraud_payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 88,
                'risk_level': 'high',
                'attempt_type': 'account_takeover',
                'evidence': {
                    'ip_address': '192.168.1.100',
                    'device_fingerprint': 'abc123def456'
                }
            },
            'timestamp': timezone.now().isoformat(),
            'source': 'external_security_system'
        }
        
        signature = self.generate_webhook_signature(fraud_payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.return_value = {
                'processed': True,
                'fraud_attempt_id': 789,
                'alert_created': True,
                'user_risk_updated': True
            }
            
            # Send webhook
            url = reverse('frauddetection:fraud-webhook')
            response = self.client.post(
                url,
                data=json.dumps(fraud_payload),
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=signature
            )
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Step 2: System creates alert (simulated)
            alert_payload = {
                'event_type': 'alert_created',
                'data': {
                    'alert_id': 123,
                    'alert_type': 'rule_triggered',
                    'priority': 'high',
                    'user_id': self.regular_user.pk,
                    'fraud_attempt_id': 789
                },
                'timestamp': timezone.now().isoformat(),
                'source': 'fraud_detection_system'
            }
            
            alert_signature = self.generate_webhook_signature(alert_payload)
            
            with patch('api.fraud_detection.webhooks.FraudAlertService') as mock_alert_service:
                mock_alert_instance = mock_alert_service.return_value
                mock_alert_instance.process_alert_webhook.return_value = {
                    'processed': True,
                    'notifications_sent': True
                }
                
                # Send alert webhook
                alert_url = reverse('frauddetection:fraud-alert-webhook')
                alert_response = self.client.post(
                    alert_url,
                    data=json.dumps(alert_payload),
                    content_type='application/json',
                    HTTP_X_WEBHOOK_SIGNATURE=alert_signature
                )
                
                self.assertEqual(alert_response.status_code, status.HTTP_200_OK)
    
    def test_webhook_error_recovery(self):
        """Test webhook error recovery and retry mechanism"""
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85
            }
        }
        
        signature = self.generate_webhook_signature(payload)
        
        # Simulate service failure
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.side_effect = [
                Exception("Temporary failure"),  # First call fails
                {
                    'processed': True,
                    'fraud_attempt_id': 999
                }  # Second call succeeds
            ]
            
            # Mock retry mechanism
            with patch('api.fraud_detection.webhooks.retry_webhook_processing') as mock_retry:
                mock_retry.return_value = True  # Retry successful
                
                url = reverse('frauddetection:fraud-webhook')
                response = self.client.post(
                    url,
                    data=json.dumps(payload),
                    content_type='application/json',
                    HTTP_X_WEBHOOK_SIGNATURE=signature
                )
                
                # Should eventually succeed after retry
                self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_webhook_performance_monitoring(self):
        """Test webhook performance monitoring"""
        payload = {
            'event_type': 'fraud_detected',
            'data': {
                'user_id': self.regular_user.pk,
                'fraud_score': 85
            }
        }
        
        signature = self.generate_webhook_signature(payload)
        
        with patch('api.fraud_detection.webhooks.FraudDetectionService') as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.process_webhook_event.return_value = {
                'processed': True,
                'fraud_attempt_id': 1001
            }
            
            # Mock performance monitoring
            with patch('api.fraud_detection.webhooks.log_webhook_performance') as mock_perf:
                url = reverse('frauddetection:fraud-webhook')
                response = self.client.post(
                    url,
                    data=json.dumps(payload),
                    content_type='application/json',
                    HTTP_X_WEBHOOK_SIGNATURE=signature
                )
                
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                
                # Verify performance logging was called
                mock_perf.assert_called_once()
                perf_call_args = mock_perf.call_args[0]
                self.assertIn('processing_time', perf_call_args)
                self.assertIn('payload_size', perf_call_args)
