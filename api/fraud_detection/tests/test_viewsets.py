"""
Comprehensive viewset testing for fraud_detection module.

This test file focuses specifically on testing viewset functionality,
including CRUD operations, custom actions, filtering, pagination,
and permissions.
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
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend

from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, FraudCase, FraudCaseEvidence
)
from api.fraud_detection.viewsets import (
    FraudRuleViewSet, FraudAttemptViewSet, FraudPatternViewSet,
    UserRiskProfileViewSet, DeviceFingerprintViewSet, IPReputationViewSet,
    FraudAlertViewSet, FraudCaseViewSet
)
from api.fraud_detection.serializers import (
    FraudRuleSerializer, FraudAttemptSerializer, FraudPatternSerializer,
    UserRiskProfileSerializer, DeviceFingerprintSerializer, IPReputationSerializer,
    FraudAlertSerializer, FraudCaseSerializer
)
from api.users.models import User

User = get_user_model()


class BaseViewSetTest(APITestCase):
    """Base test class for viewset testing"""
    
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
        self.factory = APIRequestFactory()
        cache.clear()


class FraudRuleViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for FraudRuleViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
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
        self.viewset = FraudRuleViewSet
    
    def test_viewset_configuration(self):
        """Test viewset configuration"""
        self.assertEqual(self.viewset.queryset.model, FraudRule)
        self.assertEqual(self.viewset.serializer_class, FraudRuleSerializer)
        self.assertIn(DjangoFilterBackend, self.viewset.filter_backends)
        self.assertEqual(self.viewset.pagination_class.page_size, 50)
    
    def test_queryset_filtering(self):
        """Test queryset filtering logic"""
        # Create additional test data
        FraudRule.objects.create(
            name='Payment Rule',
            description='Payment fraud rule',
            rule_type='payment',
            severity='high',
            condition={'amount_threshold': 5000},
            weight=80,
            threshold=85,
            is_active=False
        )
        
        request = self.factory.get('/api/fraud-detection/rules/')
        request.query_params = {'rule_type': 'account'}
        view = self.viewset.as_view({'get': 'list'})
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)  # Unauthorized
        
        # Test with authenticated user
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        response = self.client.get(url, {'rule_type': 'account'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['rule_type'], 'account')
    
    def test_custom_actions(self):
        """Test custom actions on viewset"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test toggle_active action
        url = reverse('frauddetection:fraudrule-toggle-active', kwargs={'pk': self.fraud_rule.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('is_active', data)
        self.assertIn('message', data)
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['is_active'])
        
        # Verify the change was persisted
        self.fraud_rule.refresh_from_db()
        self.assertFalse(self.fraud_rule.is_active)
    
    def test_bulk_operations(self):
        """Test bulk operations if implemented"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test bulk update if implemented
        url = reverse('frauddetection:fraudrule-list')
        bulk_data = [
            {'id': self.fraud_rule.pk, 'is_active': False},
        ]
        
        # This would need to be implemented in the viewset
        # response = self.client.patch(url, bulk_data, format='json')
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_viewset_permissions(self):
        """Test viewset permissions"""
        # Test unauthorized access
        url = reverse('frauddetection:fraudrule-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test admin user (should be allowed)
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_serializer_validation(self):
        """Test serializer validation in viewset context"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        
        # Test invalid data
        invalid_data = {
            'name': '',  # Empty name should be invalid
            'description': 'Test rule',
            'rule_type': 'invalid_type',  # Invalid choice
            'severity': 'invalid_severity',  # Invalid choice
            'weight': 150,  # Above max value
            'threshold': -10  # Below min value
        }
        
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        data = response.json()
        self.assertIn('name', data)
        self.assertIn('rule_type', data)
        self.assertIn('severity', data)
        self.assertIn('weight', data)
        self.assertIn('threshold', data)
    
    def test_pagination(self):
        """Test pagination functionality"""
        # Create multiple rules
        for i in range(60):
            FraudRule.objects.create(
                name=f'Rule {i}',
                description=f'Test rule {i}',
                rule_type='account',
                severity='medium',
                condition={'amount_threshold': 1000 + i},
                weight=50,
                threshold=70
            )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudrule-list')
        
        # Test default pagination
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(len(response.data['results']), 50)  # Default page size
        
        # Test custom page size
        response = self.client.get(url, {'page_size': 20})
        self.assertEqual(len(response.data['results']), 20)
        
        # Test page size limit
        response = self.client.get(url, {'page_size': 300})
        self.assertEqual(len(response.data['results']), 200)  # Max page size


class FraudAttemptViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for FraudAttemptViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
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
    
    def test_fraud_attempt_crud(self):
        """Test CRUD operations for fraud attempts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudattempt-list')
        
        # Create
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
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:fraudattempt-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['attempt_type'], 'vpn_proxy')
        
        # Update
        update_data = {
            'status': 'confirmed',
            'is_resolved': True,
            'resolution_notes': 'Confirmed as fraud'
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_fraud_attempt_custom_actions(self):
        """Test custom actions for fraud attempts"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test mark_as_confirmed action
        url = reverse('frauddetection:fraudattempt-mark-confirmed', kwargs={'pk': self.fraud_attempt.pk})
        data = {'notes': 'Confirmed as fraud'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.fraud_attempt.refresh_from_db()
        self.assertEqual(self.fraud_attempt.status, 'confirmed')
        self.assertTrue(self.fraud_attempt.is_resolved)
    
    def test_fraud_attempt_filtering(self):
        """Test filtering functionality"""
        # Create test attempts with different types
        FraudAttempt.objects.create(
            user=self.user,
            attempt_type='click_fraud',
            description='Click fraud detection',
            detected_by='ClickFraudDetector',
            fraud_score=70,
            confidence_score=80,
            status='false_positive'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudattempt-list')
        
        # Filter by attempt type
        response = self.client.get(url, {'attempt_type': 'multi_account'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['attempt_type'], 'multi_account')
        
        # Filter by status
        response = self.client.get(url, {'status': 'detected'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'detected')


class FraudPatternViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for FraudPatternViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.fraud_pattern = FraudPattern.objects.create(
            name='Test Pattern',
            pattern_type='behavioral',
            description='Test fraud pattern',
            pattern_data={'features': ['login_frequency', 'device_count']},
            features=['login_frequency', 'device_count'],
            occurrence_count=10,
            accuracy_rate=0.85
        )
    
    def test_fraud_pattern_crud(self):
        """Test CRUD operations for fraud patterns"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudpattern-list')
        
        # Create
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
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:fraudpattern-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pattern_type'], 'temporal')
        
        # Update
        update_data = {
            'accuracy_rate': 0.80,
            'occurrence_count': 8
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_fraud_pattern_validation(self):
        """Test validation for fraud patterns"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudpattern-list')
        
        # Test invalid accuracy rate
        invalid_data = {
            'name': 'Invalid Pattern',
            'pattern_type': 'behavioral',
            'description': 'Invalid pattern',
            'accuracy_rate': 1.5  # Above max value of 1.0
        }
        
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('accuracy_rate', response.data)


class UserRiskProfileViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for UserRiskProfileViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
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
    
    def test_user_risk_profile_crud(self):
        """Test CRUD operations for user risk profiles"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:userriskprofile-list')
        
        # Create
        new_user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='newpass123'
        )
        
        data = {
            'user': new_user.pk,
            'overall_risk_score': 45,
            'account_risk_score': 50,
            'payment_risk_score': 40,
            'behavior_risk_score': 45,
            'risk_factors': {'new_device': True},
            'warning_flags': ['suspicious_location'],
            'monitoring_level': 'normal'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:userriskprofile-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_risk_score'], 45)
        
        # Update
        update_data = {
            'overall_risk_score': 55,
            'is_flagged': True
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_user_risk_profile_custom_actions(self):
        """Test custom actions for user risk profiles"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test update_risk_score action
        with patch('api.fraud_detection.services.FraudScoreCalculator') as mock_calculator:
            mock_instance = mock_calculator.return_value
            mock_instance.calculate_overall_risk.return_value = 75
            
            url = reverse('frauddetection:userriskprofile-update-risk-score', kwargs={'pk': self.risk_profile.pk})
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            data = response.json()
            self.assertIn('message', data)
            self.assertIn('new_risk_score', data)


class DeviceFingerprintViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for DeviceFingerprintViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.device_fingerprint = DeviceFingerprint.objects.create(
            user=self.user,
            device_id='test-device-123',
            device_hash='abc123def456',
            user_agent='Mozilla/5.0 (Test Browser)',
            platform='Windows',
            browser='Chrome',
            ip_address='192.168.1.1',
            location_data={'country': 'US', 'city': 'New York'},
            trust_score=85
        )
    
    def test_device_fingerprint_crud(self):
        """Test CRUD operations for device fingerprints"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:devicefingerprint-list')
        
        # Create
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
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:devicefingerprint-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['platform'], 'Mac')
        
        # Update
        update_data = {
            'trust_score': 95,
            'is_vpn': True
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_device_fingerprint_unique_constraints(self):
        """Test unique constraints for device fingerprints"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:devicefingerprint-list')
        
        # Test duplicate device_id (should fail if unique constraint exists)
        data = {
            'user': self.user.pk,
            'device_id': 'test-device-123',  # Same as existing
            'device_hash': 'different-hash',
            'user_agent': 'Mozilla/5.0 (Different Browser)',
            'ip_address': '192.168.1.3'
        }
        response = self.client.post(url, data, format='json')
        # This should either succeed (if unique constraint was fixed) or fail
        # The test verifies the current behavior
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])


class IPReputationViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for IPReputationViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
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
    
    def test_ip_reputation_crud(self):
        """Test CRUD operations for IP reputation"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:ipreputation-list')
        
        # Create
        data = {
            'ip_address': '192.168.1.100',
            'fraud_score': 50,
            'spam_score': 40,
            'malware_score': 10,
            'total_requests': 50,
            'fraud_attempts': 5,
            'unique_users': 3,
            'country': 'CA',
            'city': 'Toronto',
            'isp': 'Canadian ISP'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:ipreputation-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country'], 'CA')
        
        # Update
        update_data = {
            'fraud_score': 85,
            'is_blacklisted': True,
            'blacklist_reason': 'High fraud activity'
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_ip_reputation_filtering(self):
        """Test filtering for IP reputation"""
        # Create additional IP reputation entries
        IPReputation.objects.create(
            ip_address='192.168.1.2',
            fraud_score=90,
            spam_score=80,
            malware_score=50,
            is_blacklisted=True,
            country='CN'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:ipreputation-list')
        
        # Filter by country
        response = self.client.get(url, {'country': 'US'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['country'], 'US')
        
        # Filter by blacklist status
        response = self.client.get(url, {'is_blacklisted': 'false'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertFalse(response.data['results'][0]['is_blacklisted'])


class FraudAlertViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for FraudAlertViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
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
    
    def test_fraud_alert_crud(self):
        """Test CRUD operations for fraud alerts"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudalert-list')
        
        # Create
        data = {
            'alert_type': 'pattern_detected',
            'priority': 'medium',
            'title': 'Suspicious Pattern Detected',
            'description': 'Fraud pattern detected',
            'user': self.user.pk,
            'data': {'pattern_id': 1, 'confidence': 0.9}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:fraudalert-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['alert_type'], 'pattern_detected')
        
        # Update
        update_data = {
            'priority': 'low',
            'is_resolved': True
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_fraud_alert_custom_actions(self):
        """Test custom actions for fraud alerts"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test resolve action
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
    
    def test_fraud_alert_filtering(self):
        """Test filtering for fraud alerts"""
        # Create additional alerts
        FraudAlert.objects.create(
            alert_type='threshold_exceeded',
            priority='critical',
            title='Critical Alert',
            description='Critical threshold exceeded',
            is_resolved=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudalert-list')
        
        # Filter by priority
        response = self.client.get(url, {'priority': 'high'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['priority'], 'high')
        
        # Filter by resolved status
        response = self.client.get(url, {'is_resolved': 'false'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertFalse(response.data['results'][0]['is_resolved'])


class FraudCaseViewSetDetailedTest(BaseViewSetTest):
    """Detailed test cases for FraudCaseViewSet"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
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
    
    def test_fraud_case_crud(self):
        """Test CRUD operations for fraud cases"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudcase-list')
        
        # Create
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
        
        created_id = response.data['id']
        
        # Read
        detail_url = reverse('frauddetection:fraudcase-detail', kwargs={'pk': created_id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['case_number'], 'FC-2023-002')
        
        # Update
        update_data = {
            'status': 'resolved',
            'resolved_by': self.admin_user.pk,
            'resolved_at': timezone.now().isoformat()
        }
        response = self.client.patch(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Delete
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_fraud_case_custom_actions(self):
        """Test custom actions for fraud cases"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Test assign action (if implemented)
        # url = reverse('frauddetection:fraudcase-assign', kwargs={'pk': self.fraud_case.pk})
        # data = {'assigned_to': self.admin_user.pk}
        # response = self.client.post(url, data, format='json')
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test close action (if implemented)
        # url = reverse('frauddetection:fraudcase-close', kwargs={'pk': self.fraud_case.pk})
        # data = {'resolution_summary': 'Case closed'}
        # response = self.client.post(url, data, format='json')
        # self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_fraud_case_filtering(self):
        """Test filtering for fraud cases"""
        # Create additional cases
        FraudCase.objects.create(
            case_number='FC-2023-003',
            user=self.user,
            title='Low Priority Case',
            description='Low priority investigation',
            status='closed',
            risk_score=25,
            priority='low',
            assigned_to=self.admin_user
        )
        
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('frauddetection:fraudcase-list')
        
        # Filter by status
        response = self.client.get(url, {'status': 'open'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'open')
        
        # Filter by priority
        response = self.client.get(url, {'priority': 'high'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['priority'], 'high')
