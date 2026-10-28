"""
Comprehensive API-level tests for fraud_detection views.

This test file covers all HTTP views, viewsets, and API endpoints
that were previously untested in the fraud_detection module.
"""

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.test import APIRequestFactory
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.test import Client
from django.core.cache import cache

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase, FraudCaseEvidence
)
from api.fraud_detection.views import (
    FraudRuleViewSet, FraudAttemptViewSet, FraudPatternViewSet,
    UserRiskProfileViewSet, DeviceFingerprintViewSet, IPReputationViewSet,
    FraudAlertViewSet, FraudDetectionAPIView, FraudStatisticsAPIView,
    BulkFraudAnalysisAPIView
)
from api.fraud_detection.consumers import FraudDetectionConsumer
from api.fraud_detection.webhooks import FraudWebhookView
from api.fraud_detection.encryption import FraudEncryptionService
from api.fraud_detection.monitoring import FraudMonitoringService
from api.fraud_detection.feature_flags import FraudFeatureFlags
from api.users.models import User

User = get_user_model()


class FraudRuleViewSetTest(APITestCase):
    """Test cases for FraudRuleViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            weight=50,
            threshold=70,
            is_active=True
        )
        self.factory = APIRequestFactory()
    
    def test_list_fraud_rules_unauthorized(self):
        """Test that unauthorized users cannot list fraud rules"""
        view = FraudRuleViewSet.as_view({'get': 'list'})
        request = self.factory.get('/api/fraud-detection/rules/')
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_fraud_rules_authorized(self):
        """Test that authorized users can list fraud rules"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_fraud_rule(self):
        """Test creating a new fraud rule"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        data = {
            'name': 'New Rule',
            'description': 'New fraud detection rule',
            'rule_type': 'payment',
            'severity': 'high',
            'condition': {'amount_threshold': 5000},
            'weight': 80,
            'threshold': 85,
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FraudRule.objects.count(), 2)
    
    def test_update_fraud_rule(self):
        """Test updating an existing fraud rule"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-detail', kwargs={'pk': self.fraud_rule.pk})
        data = {
            'name': 'Updated Rule',
            'description': 'Updated fraud detection rule',
            'rule_type': 'payment',
            'severity': 'high',
            'condition': {'amount_threshold': 2000},
            'weight': 60,
            'threshold': 75,
            'is_active': False
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fraud_rule.refresh_from_db()
        self.assertEqual(self.fraud_rule.name, 'Updated Rule')
        self.assertEqual(self.fraud_rule.severity, 'high')
    
    def test_partial_update_fraud_rule(self):
        """Test partially updating a fraud rule"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-detail', kwargs={'pk': self.fraud_rule.pk})
        data = {'severity': 'low'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fraud_rule.refresh_from_db()
        self.assertEqual(self.fraud_rule.severity, 'low')
    
    def test_delete_fraud_rule(self):
        """Test deleting a fraud rule"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-detail', kwargs={'pk': self.fraud_rule.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(FraudRule.objects.count(), 0)
    
    def test_toggle_active_action(self):
        """Test the toggle_active custom action"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-toggle-active', kwargs={'pk': self.fraud_rule.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fraud_rule.refresh_from_db()
        self.assertFalse(self.fraud_rule.is_active)
    
    def test_filter_by_rule_type(self):
        """Test filtering fraud rules by rule type"""
        # Create another rule with different type
        FraudRule.objects.create(
            name='Payment Rule',
            description='Payment fraud rule',
            rule_type='payment',
            severity='high',
            condition={'amount_threshold': 3000},
            weight=70,
            threshold=80
        )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        response = self.client.get(url, {'rule_type': 'account'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['rule_type'], 'account')
    
    def test_search_fraud_rules(self):
        """Test searching fraud rules"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        response = self.client.get(url, {'search': 'Test'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Rule')


class FraudAttemptViewSetTest(APITestCase):
    """Test cases for FraudAttemptViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000}
        )
        self.fraud_attempt = FraudAttempt.objects.create(
            user=self.user,
            attempt_type='multi_account',
            description='Multiple account detection',
            detected_by='MultiAccountDetector',
            fraud_score=85,
            confidence_score=90,
            status='detected'
        )
        self.fraud_attempt.fraud_rules.add(self.fraud_rule)
    
    def test_list_fraud_attempts(self):
        """Test listing fraud attempts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudattempt-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_fraud_attempt(self):
        """Test creating a fraud attempt"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudattempt-list')
        data = {
            'user': self.user.pk,
            'attempt_type': 'vpn_proxy',
            'description': 'VPN detection',
            'detected_by': 'VPNProxyDetector',
            'fraud_score': 75,
            'confidence_score': 80,
            'status': 'detected',
            'evidence_data': {'ip_address': '192.168.1.1'},
            'metadata': {'vpn_provider': 'TestVPN'}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FraudAttempt.objects.count(), 2)
    
    def test_mark_as_confirmed(self):
        """Test marking a fraud attempt as confirmed"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudattempt-mark-confirmed', kwargs={'pk': self.fraud_attempt.pk})
        response = self.client.post(url, {'notes': 'Confirmed as fraud'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fraud_attempt.refresh_from_db()
        self.assertEqual(self.fraud_attempt.status, 'confirmed')
        self.assertTrue(self.fraud_attempt.is_resolved)


class FraudDetectionAPIViewTest(APITestCase):
    """Test cases for FraudDetectionAPIView"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.fraud_rule = FraudRule.objects.create(
            name='Test Rule',
            description='Test fraud detection rule',
            rule_type='account',
            severity='medium',
            condition={'amount_threshold': 1000},
            is_active=True
        )
    
    @patch('api.fraud_detection.detectors.MultiAccountDetector.detect')
    def test_fraud_detection_analysis(self, mock_detect):
        """Test fraud detection analysis endpoint"""
        mock_detect.return_value = {
            'is_fraud': True,
            'fraud_score': 85,
            'risk_level': 'high',
            'detected_rules': [self.fraud_rule.pk],
            'evidence': {'multiple_accounts': True}
        }
        
        self.client.force_authenticate(user=self.user)
        url = reverse('frauddetection:detect-fraud')
        data = {
            'user_id': self.user.pk,
            'action_type': 'login',
            'context': {'ip_address': '192.168.1.1', 'user_agent': 'TestAgent'}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_fraud'])
        self.assertEqual(response.data['fraud_score'], 85)
    
    def test_fraud_detection_analysis_invalid_data(self):
        """Test fraud detection analysis with invalid data"""
        self.client.force_authenticate(user=self.user)
        url = reverse('frauddetection:detect-fraud')
        data = {'user_id': 999999}  # Non-existent user
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FraudStatisticsAPIViewTest(APITestCase):
    """Test cases for FraudStatisticsAPIView"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        # Create test fraud attempts
        for i in range(5):
            FraudAttempt.objects.create(
                user=self.user,
                attempt_type='multi_account' if i % 2 == 0 else 'vpn_proxy',
                description=f'Test attempt {i}',
                detected_by='TestDetector',
                fraud_score=70 + i * 5,
                confidence_score=80 + i * 3,
                status='detected' if i < 3 else 'confirmed'
            )
    
    def test_fraud_statistics(self):
        """Test fraud statistics endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:statistics')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_attempts', response.data)
        self.assertIn('attempts_by_type', response.data)
        self.assertIn('attempts_by_status', response.data)
        self.assertIn('average_fraud_score', response.data)
        self.assertEqual(response.data['total_attempts'], 5)
    
    def test_fraud_statistics_with_date_filter(self):
        """Test fraud statistics with date filtering"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:statistics')
        response = self.client.get(url, {
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date()
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_attempts', response.data)


class BulkFraudAnalysisAPIViewTest(APITestCase):
    """Test cases for BulkFraudAnalysisAPIView"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        # Create test users for bulk analysis
        for i in range(3):
            User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
    
    @patch('api.fraud_detection.detectors.MultiAccountDetector.detect')
    def test_bulk_fraud_analysis(self, mock_detect):
        """Test bulk fraud analysis endpoint"""
        mock_detect.return_value = {
            'is_fraud': False,
            'fraud_score': 25,
            'risk_level': 'low'
        }
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:bulk-analysis')
        data = {
            'user_ids': [2, 3, 4],  # IDs of created users
            'analysis_type': 'multi_account'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_bulk_fraud_analysis_invalid_user_ids(self):
        """Test bulk fraud analysis with invalid user IDs"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:bulk-analysis')
        data = {
            'user_ids': [999999, 1000000],  # Non-existent users
            'analysis_type': 'multi_account'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FraudPatternViewSetTest(APITestCase):
    """Test cases for FraudPatternViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.fraud_pattern = FraudPattern.objects.create(
            name='Test Pattern',
            pattern_type='behavioral',
            description='Test fraud pattern',
            pattern_data={'features': ['login_frequency', 'device_count']},
            features=['login_frequency', 'device_count'],
            occurrence_count=10,
            accuracy_rate=0.85
        )
    
    def test_list_fraud_patterns(self):
        """Test listing fraud patterns"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudpattern-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_fraud_pattern(self):
        """Test creating a fraud pattern"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudpattern-list')
        data = {
            'name': 'New Pattern',
            'pattern_type': 'temporal',
            'description': 'New fraud pattern',
            'pattern_data': {'time_window': '24h'},
            'features': ['time_of_day', 'day_of_week'],
            'occurrence_count': 5,
            'accuracy_rate': 0.75
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FraudPattern.objects.count(), 2)


class UserRiskProfileViewSetTest(APITestCase):
    """Test cases for UserRiskProfileViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.risk_profile = UserRiskProfile.objects.create(
            user=self.user,
            overall_risk_score=65,
            account_risk_score=70,
            payment_risk_score=60,
            behavior_risk_score=65,
            risk_factors={'multiple_accounts': True, 'suspicious_ips': 2},
            warning_flags=['high_login_frequency', 'new_device'],
            total_fraud_attempts=3,
            confirmed_fraud_attempts=1,
            false_positives=0,
            is_flagged=True,
            is_restricted=False,
            monitoring_level='enhanced'
        )
    
    def test_list_user_risk_profiles(self):
        """Test listing user risk profiles"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:userriskprofile-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_update_risk_score(self):
        """Test updating user risk score"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:userriskprofile-update-risk-score', kwargs={'pk': self.risk_profile.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.risk_profile.refresh_from_db()
        # Risk score should be updated by the service
        self.assertIn('message', response.data)


class DeviceFingerprintViewSetTest(APITestCase):
    """Test cases for DeviceFingerprintViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.device_fingerprint = DeviceFingerprint.objects.create(
            user=self.user,
            device_id='test-device-123',
            device_hash='abc123def456',
            user_agent='Mozilla/5.0 (Test Browser)',
            platform='Windows',
            browser='Chrome',
            browser_version='91.0',
            os='Windows',
            os_version='10',
            screen_resolution='1920x1080',
            language='en-US',
            timezone='America/New_York',
            ip_address='192.168.1.1',
            location_data={'country': 'US', 'city': 'New York'},
            trust_score=85
        )
    
    def test_list_device_fingerprints(self):
        """Test listing device fingerprints"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:devicefingerprint-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_device_fingerprint(self):
        """Test creating a device fingerprint"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:devicefingerprint-list')
        data = {
            'user': self.user.pk,
            'device_id': 'new-device-456',
            'device_hash': 'xyz789abc123',
            'user_agent': 'Mozilla/5.0 (New Browser)',
            'platform': 'Mac',
            'browser': 'Safari',
            'ip_address': '192.168.1.2',
            'location_data': {'country': 'US', 'city': 'Los Angeles'},
            'trust_score': 90
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeviceFingerprint.objects.count(), 2)


class IPReputationViewSetTest(APITestCase):
    """Test cases for IPReputationViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.ip_reputation = IPReputation.objects.create(
            ip_address='192.168.1.1',
            fraud_score=75,
            spam_score=60,
            malware_score=20,
            total_requests=100,
            fraud_attempts=15,
            unique_users=5,
            is_blacklisted=False,
            country='US',
            city='New York',
            isp='Test ISP',
            threat_types=['vpn', 'proxy']
        )
    
    def test_list_ip_reputation(self):
        """Test listing IP reputation data"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:ipreputation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_update_ip_reputation(self):
        """Test updating IP reputation"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:ipreputation-detail', kwargs={'pk': self.ip_reputation.pk})
        data = {
            'fraud_score': 85,
            'spam_score': 70,
            'malware_score': 30,
            'is_blacklisted': True,
            'blacklist_reason': 'High fraud activity'
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ip_reputation.refresh_from_db()
        self.assertEqual(self.ip_reputation.fraud_score, 85)
        self.assertTrue(self.ip_reputation.is_blacklisted)


class FraudAlertViewSetTest(APITestCase):
    """Test cases for FraudAlertViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.fraud_alert = FraudAlert.objects.create(
            alert_type='rule_triggered',
            priority='high',
            title='High Risk Activity Detected',
            description='Suspicious activity detected for user',
            user=self.user,
            data={'rule_id': 1, 'risk_score': 85},
            is_resolved=False
        )
    
    def test_list_fraud_alerts(self):
        """Test listing fraud alerts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudalert-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_resolve_fraud_alert(self):
        """Test resolving a fraud alert"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudalert-resolve', kwargs={'pk': self.fraud_alert.pk})
        data = {
            'resolution_notes': 'Alert reviewed and resolved',
            'resolved_by': self.admin_user.pk
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.fraud_alert.refresh_from_db()
        self.assertTrue(self.fraud_alert.is_resolved)
        self.assertEqual(self.fraud_alert.resolved_by, self.admin_user)


class FraudCaseViewSetTest(APITestCase):
    """Test cases for FraudCaseViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
            is_superuser=True
        )
        self.fraud_case = FraudCase.objects.create(
            case_number='FC-2023-001',
            user=self.user,
            title='Multi Account Investigation',
            description='Investigation of multiple account usage',
            status='open',
            risk_score=85,
            priority='high',
            assigned_to=self.admin_user
        )
    
    def test_list_fraud_cases(self):
        """Test listing fraud cases"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudcase-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_fraud_case(self):
        """Test creating a fraud case"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudcase-list')
        data = {
            'case_number': 'FC-2023-002',
            'user': self.user.pk,
            'title': 'Suspicious Activity Investigation',
            'description': 'Investigation of suspicious login patterns',
            'status': 'open',
            'risk_score': 75,
            'priority': 'medium',
            'assigned_to': self.admin_user.pk
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FraudCase.objects.count(), 2)
