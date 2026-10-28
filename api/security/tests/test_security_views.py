"""
Enhanced Security Views Tests
Comprehensive test suite for security views and ViewSets
Author: System Security Team
Version: 2.0.0
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.test import force_authenticate

from ..viewset import (
    DeviceInfoViewSet, SecurityLogViewSet, UserBanViewSet,
    RiskScoreViewSet, ThreatIntelligenceViewSet, SecurityIncidentViewSet,
    TrustedDeviceViewSet, PasswordHistoryViewSet, SecurityPolicyViewSet,
    SecurityInsightViewSet
)
from .factories import (
    UserFactory, StaffUserFactory, SuperUserFactory,
    DeviceInfoFactory, SecurityLogFactory, UserBanFactory,
    RiskScoreFactory, ThreatIntelligenceFactory, SecurityIncidentFactory,
    TrustedDeviceFactory, PasswordHistoryFactory, SecurityPolicyFactory,
    SecurityInsightFactory
)

User = get_user_model()


class DeviceInfoViewSetTest(APITestCase):
    """Test DeviceInfoViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.device = DeviceInfoFactory(user=self.user)
    
    def test_list_device_info_authenticated(self):
        """Test listing device info as authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_device_info_unauthenticated(self):
        """Test listing device info as unauthenticated user"""
        url = reverse('deviceinfo-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_retrieve_device_info_owner(self):
        """Test retrieving own device info"""
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.device.id))
    
    def test_retrieve_device_info_staff(self):
        """Test retrieving device info as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_device_info_unauthorized(self):
        """Test retrieving device info as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_device_info(self):
        """Test creating device info"""
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-list')
        data = {
            'device_fingerprint': 'test_fingerprint_123',
            'device_type': 'desktop',
            'device_name': 'Test Device',
            'operating_system': 'Windows 10',
            'browser': 'Chrome',
            'browser_version': '91.0',
            'screen_resolution': '1920x1080',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['device_fingerprint'], 'test_fingerprint_123')
    
    def test_update_device_info_owner(self):
        """Test updating own device info"""
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        data = {
            'device_name': 'Updated Device Name',
            'trust_score': 85
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['device_name'], 'Updated Device Name')
    
    def test_update_device_info_unauthorized(self):
        """Test updating device info as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        data = {'device_name': 'Updated Device Name'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_device_info_owner(self):
        """Test deleting own device info"""
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_delete_device_info_unauthorized(self):
        """Test deleting device info as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_trust_device_action(self):
        """Test trust device custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('deviceinfo-trust', kwargs={'pk': self.device.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_trusted'])
    
    def test_untrust_device_action(self):
        """Test untrust device custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('deviceinfo-untrust', kwargs={'pk': self.device.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_trusted'])


class SecurityLogViewSetTest(APITestCase):
    """Test SecurityLogViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.security_log = SecurityLogFactory(user=self.user)
    
    def test_list_security_logs_staff(self):
        """Test listing security logs as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_security_logs_user(self):
        """Test listing security logs as regular user"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitylog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own logs
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_security_logs_unauthenticated(self):
        """Test listing security logs as unauthenticated user"""
        url = reverse('securitylog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_retrieve_security_log_staff(self):
        """Test retrieving security log as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-detail', kwargs={'pk': self.security_log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.security_log.id))
    
    def test_retrieve_security_log_owner(self):
        """Test retrieving own security log"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitylog-detail', kwargs={'pk': self.security_log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_security_log_unauthorized(self):
        """Test retrieving security log as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('securitylog-detail', kwargs={'pk': self.security_log.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_security_log_staff(self):
        """Test creating security log as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-list')
        data = {
            'event_type': 'manual_log',
            'severity': 'info',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'metadata': {'reason': 'Manual entry for testing'}
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_type'], 'manual_log')
    
    def test_create_security_log_user_forbidden(self):
        """Test creating security log as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitylog-list')
        data = {
            'event_type': 'manual_log',
            'severity': 'info',
            'ip_address': '192.168.1.100'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_filter_security_logs_by_event_type(self):
        """Test filtering security logs by event type"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-list') + '?event_type=login_success'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_security_logs_by_severity(self):
        """Test filtering security logs by severity"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-list') + '?severity=warning'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_filter_security_logs_by_date_range(self):
        """Test filtering security logs by date range"""
        self.client.force_authenticate(user=self.staff_user)
        today = timezone.now().date()
        url = reverse('securitylog-list') + f'?date_from={today}&date_to={today}'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_export_security_logs_staff(self):
        """Test exporting security logs as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitylog-export')
        response = self.client.post(url, {'format': 'csv'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_export_security_logs_user_forbidden(self):
        """Test exporting security logs as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitylog-export')
        response = self.client.post(url, {'format': 'csv'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserBanViewSetTest(APITestCase):
    """Test UserBanViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.super_user = SuperUserFactory()
        self.user_ban = UserBanFactory(user=self.user)
    
    def test_list_user_bans_staff(self):
        """Test listing user bans as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_user_bans_user_forbidden(self):
        """Test listing user bans as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('userban-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_user_ban_staff(self):
        """Test retrieving user ban as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-detail', kwargs={'pk': self.user_ban.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.user_ban.id))
    
    def test_create_user_ban_staff(self):
        """Test creating user ban as staff user"""
        target_user = UserFactory()
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-list')
        data = {
            'user': target_user.id,
            'reason': 'Violation of terms of service',
            'ban_type': 'temporary',
            'expires_at': (timezone.now() + timezone.timedelta(days=7)).isoformat()
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['reason'], 'Violation of terms of service')
    
    def test_create_user_ban_user_forbidden(self):
        """Test creating user ban as regular user (should be forbidden)"""
        target_user = UserFactory()
        self.client.force_authenticate(user=self.user)
        url = reverse('userban-list')
        data = {
            'user': target_user.id,
            'reason': 'Test ban',
            'ban_type': 'temporary'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_user_ban_staff(self):
        """Test updating user ban as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-detail', kwargs={'pk': self.user_ban.id})
        data = {
            'reason': 'Updated ban reason',
            'is_active': False
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reason'], 'Updated ban reason')
        self.assertFalse(response.data['is_active'])
    
    def test_delete_user_ban_super_user(self):
        """Test deleting user ban as super user"""
        self.client.force_authenticate(user=self.super_user)
        url = reverse('userban-detail', kwargs={'pk': self.user_ban.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_delete_user_ban_staff_forbidden(self):
        """Test deleting user ban as staff user (should be forbidden)"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-detail', kwargs={'pk': self.user_ban.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_lift_user_ban_action(self):
        """Test lift ban custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-lift', kwargs={'pk': self.user_ban.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
    
    def test_extend_user_ban_action(self):
        """Test extend ban custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('userban-extend', kwargs={'pk': self.user_ban.id})
        data = {'days': 7}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('expires_at', response.data)


class RiskScoreViewSetTest(APITestCase):
    """Test RiskScoreViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.risk_score = RiskScoreFactory(user=self.user)
    
    def test_list_risk_scores_staff(self):
        """Test listing risk scores as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_risk_scores_user(self):
        """Test listing risk scores as regular user"""
        self.client.force_authenticate(user=self.user)
        url = reverse('riskscore-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own risk scores
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_risk_score_owner(self):
        """Test retrieving own risk score"""
        self.client.force_authenticate(user=self.user)
        url = reverse('riskscore-detail', kwargs={'pk': self.risk_score.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.risk_score.id))
    
    def test_retrieve_risk_score_staff(self):
        """Test retrieving risk score as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-detail', kwargs={'pk': self.risk_score.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_retrieve_risk_score_unauthorized(self):
        """Test retrieving risk score as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('riskscore-detail', kwargs={'pk': self.risk_score.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_risk_score_staff(self):
        """Test creating risk score as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-list')
        data = {
            'user': self.user.id,
            'current_score': 75.5,
            'risk_factors': ['suspicious_location', 'unusual_device'],
            'expires_at': (timezone.now() + timezone.timedelta(hours=24)).isoformat()
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['current_score']), 75.5)
    
    def test_create_risk_score_user_forbidden(self):
        """Test creating risk score as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('riskscore-list')
        data = {
            'current_score': 50.0,
            'risk_factors': ['test_factor']
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_risk_score_staff(self):
        """Test updating risk score as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-detail', kwargs={'pk': self.risk_score.id})
        data = {
            'current_score': 85.0,
            'risk_factors': ['new_factor']
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['current_score']), 85.0)
    
    def test_recalculate_risk_score_action(self):
        """Test recalculate risk score custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-recalculate', kwargs={'pk': self.risk_score.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('new_score', response.data)
    
    def test_reset_risk_score_action(self):
        """Test reset risk score custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('riskscore-reset', kwargs={'pk': self.risk_score.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['current_score']), 0.0)


class ThreatIntelligenceViewSetTest(APITestCase):
    """Test ThreatIntelligenceViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.threat_intel = ThreatIntelligenceFactory()
    
    def test_list_threat_intelligence_staff(self):
        """Test listing threat intelligence as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_threat_intelligence_user_forbidden(self):
        """Test listing threat intelligence as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('threatintelligence-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_threat_intelligence_staff(self):
        """Test retrieving threat intelligence as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-detail', kwargs={'pk': self.threat_intel.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.threat_intel.id))
    
    def test_create_threat_intelligence_staff(self):
        """Test creating threat intelligence as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-list')
        data = {
            'threat_type': 'malware',
            'indicator_type': 'ip',
            'indicators': ['192.168.1.100', '192.168.1.101'],
            'severity': 'high',
            'confidence': 0.85,
            'source': 'internal_analysis',
            'description': 'Suspicious activity detected'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['threat_type'], 'malware')
        self.assertEqual(len(response.data['indicators']), 2)
    
    def test_create_threat_intelligence_user_forbidden(self):
        """Test creating threat intelligence as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('threatintelligence-list')
        data = {
            'threat_type': 'malware',
            'indicator_type': 'ip',
            'indicators': ['192.168.1.100']
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_threat_intelligence_staff(self):
        """Test updating threat intelligence as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-detail', kwargs={'pk': self.threat_intel.id})
        data = {
            'severity': 'critical',
            'confidence': 0.95
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['severity'], 'critical')
    
    def test_delete_threat_intelligence_staff(self):
        """Test deleting threat intelligence as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-detail', kwargs={'pk': self.threat_intel.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_bulk_create_threat_intelligence(self):
        """Test bulk creating threat intelligence"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-bulk-create')
        data = {
            'threat_intel_list': [
                {
                    'threat_type': 'malware',
                    'indicator_type': 'ip',
                    'indicators': ['192.168.1.100'],
                    'severity': 'high'
                },
                {
                    'threat_type': 'phishing',
                    'indicator_type': 'domain',
                    'indicators': ['malicious-site.com'],
                    'severity': 'medium'
                }
            ]
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_count'], 2)
    
    def test_export_threat_intelligence(self):
        """Test exporting threat intelligence"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-export')
        response = self.client.post(url, {'format': 'json'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_import_threat_intelligence(self):
        """Test importing threat intelligence"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-import')
        import_data = [
            {
                'threat_type': 'malware',
                'indicator_type': 'ip',
                'indicators': ['192.168.1.100'],
                'severity': 'high'
            }
        ]
        response = self.client.post(url, {'data': json.dumps(import_data)}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['imported_count'], 1)


class SecurityIncidentViewSetTest(APITestCase):
    """Test SecurityIncidentViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.incident = SecurityIncidentFactory(user=self.user)
    
    def test_list_security_incidents_staff(self):
        """Test listing security incidents as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_security_incidents_user(self):
        """Test listing security incidents as regular user"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securityincident-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see own incidents
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_security_incident_owner(self):
        """Test retrieving own security incident"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securityincident-detail', kwargs={'pk': self.incident.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.incident.id))
    
    def test_retrieve_security_incident_staff(self):
        """Test retrieving security incident as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-detail', kwargs={'pk': self.incident.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_security_incident_staff(self):
        """Test creating security incident as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-list')
        data = {
            'user': self.user.id,
            'incident_type': 'security_breach',
            'severity': 'high',
            'title': 'Test Security Incident',
            'description': 'This is a test incident',
            'evidence': {'ip_addresses': ['192.168.1.100']}
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['incident_type'], 'security_breach')
    
    def test_create_security_incident_user_forbidden(self):
        """Test creating security incident as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securityincident-list')
        data = {
            'incident_type': 'security_breach',
            'severity': 'high',
            'title': 'Test Incident'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_security_incident_staff(self):
        """Test updating security incident as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-detail', kwargs={'pk': self.incident.id})
        data = {
            'severity': 'critical',
            'status': 'investigating'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['severity'], 'critical')
    
    def test_assign_security_incident_action(self):
        """Test assign incident custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-assign', kwargs={'pk': self.incident.id})
        data = {'assigned_to': self.staff_user.id}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assigned_to'], self.staff_user.id)
    
    def test_resolve_security_incident_action(self):
        """Test resolve incident custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-resolve', kwargs={'pk': self.incident.id})
        data = {'resolution': 'Investigation completed, no threat found'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'resolved')
    
    def test_escalate_security_incident_action(self):
        """Test escalate incident custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-escalate', kwargs={'pk': self.incident.id})
        data = {'new_severity': 'critical'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['severity'], 'critical')
    
    def test_add_evidence_action(self):
        """Test add evidence custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-add-evidence', kwargs={'pk': self.incident.id})
        data = {
            'evidence': {
                'new_ip_address': '192.168.1.200',
                'additional_info': 'New evidence found'
            }
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('new_ip_address', response.data['evidence'])
    
    def test_get_timeline_action(self):
        """Test get timeline custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-timeline', kwargs={'pk': self.incident.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data['timeline'], list)


class TrustedDeviceViewSetTest(APITestCase):
    """Test TrustedDeviceViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.trusted_device = TrustedDeviceFactory(user=self.user)
    
    def test_list_trusted_devices_owner(self):
        """Test listing trusted devices as owner"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_trusted_devices_staff(self):
        """Test listing trusted devices as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('trusteddevice-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_trusted_device_owner(self):
        """Test retrieving own trusted device"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-detail', kwargs={'pk': self.trusted_device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.trusted_device.id))
    
    def test_retrieve_trusted_device_unauthorized(self):
        """Test retrieving trusted device as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('trusteddevice-detail', kwargs={'pk': self.trusted_device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_trusted_device(self):
        """Test creating trusted device"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-list')
        data = {
            'device_fingerprint': 'test_fingerprint_123',
            'device_name': 'Test Device',
            'platform': 'Windows',
            'browser': 'Chrome',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'trust_score': 80
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['device_fingerprint'], 'test_fingerprint_123')
    
    def test_update_trusted_device_owner(self):
        """Test updating own trusted device"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-detail', kwargs={'pk': self.trusted_device.id})
        data = {
            'device_name': 'Updated Device Name',
            'trust_score': 90
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['device_name'], 'Updated Device Name')
    
    def test_revoke_trust_action(self):
        """Test revoke trust custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-revoke-trust', kwargs={'pk': self.trusted_device.id})
        data = {'reason': 'Security concern detected'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_trusted'])
    
    def test_extend_trust_action(self):
        """Test extend trust custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-extend-trust', kwargs={'pk': self.trusted_device.id})
        data = {'days': 30}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('expires_at', response.data)
    
    def test_verify_device_action(self):
        """Test verify device custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-verify', kwargs={'pk': self.trusted_device.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_trusted', response.data)
    
    def test_get_usage_statistics_action(self):
        """Test get usage statistics custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('trusteddevice-usage-stats', kwargs={'pk': self.trusted_device.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_usage', response.data)


class PasswordHistoryViewSetTest(APITestCase):
    """Test PasswordHistoryViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.password_history = PasswordHistoryFactory(user=self.user)
    
    def test_list_password_history_owner(self):
        """Test listing password history as owner"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_password_history_staff(self):
        """Test listing password history as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('passwordhistory-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_password_history_owner(self):
        """Test retrieving own password history"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-detail', kwargs={'pk': self.password_history.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.password_history.id))
    
    def test_retrieve_password_history_unauthorized(self):
        """Test retrieving password history as unauthorized user"""
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('passwordhistory-detail', kwargs={'pk': self.password_history.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_password_history(self):
        """Test creating password history"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-list')
        data = {
            'password_hash': 'hashed_password_123',
            'password_algorithm': 'bcrypt',
            'salt': 'salt_value_456',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['password_algorithm'], 'bcrypt')
    
    def test_check_password_reuse_action(self):
        """Test check password reuse custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-check-reuse')
        data = {'password_hash': 'hashed_password_123'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_reused', response.data)
    
    def test_get_password_age_action(self):
        """Test get password age custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-password-age')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('age_days', response.data)
    
    def test_export_password_history(self):
        """Test exporting password history"""
        self.client.force_authenticate(user=self.user)
        url = reverse('passwordhistory-export')
        response = self.client.post(url, {'format': 'json'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cleanup_old_passwords_action(self):
        """Test cleanup old passwords custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('passwordhistory-cleanup')
        data = {'days': 365}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deleted_count', response.data)


class SecurityPolicyViewSetTest(APITestCase):
    """Test SecurityPolicyViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.security_policy = SecurityPolicyFactory(user=self.user)
    
    def test_list_security_policies_owner(self):
        """Test listing security policies as owner"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_security_policies_staff(self):
        """Test listing security policies as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securitypolicy-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_retrieve_security_policy_owner(self):
        """Test retrieving own security policy"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-detail', kwargs={'pk': self.security_policy.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.security_policy.id))
    
    def test_create_security_policy(self):
        """Test creating security policy"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-list')
        data = {
            'policy_key': 'password_policy',
            'policy_value': {
                'min_length': 12,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_special_chars': True
            },
            'is_active': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['policy_key'], 'password_policy')
    
    def test_update_security_policy_owner(self):
        """Test updating own security policy"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-detail', kwargs={'pk': self.security_policy.id})
        data = {
            'policy_value': {
                'min_length': 14,
                'require_uppercase': True
            },
            'is_active': False
        }
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
    
    def test_delete_security_policy_owner(self):
        """Test deleting own security policy"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-detail', kwargs={'pk': self.security_policy.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_validate_policy_action(self):
        """Test validate policy custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-validate')
        data = {
            'policy_type': 'password_policy',
            'policy_data': {
                'min_length': 8,
                'require_uppercase': True,
                'require_lowercase': True
            }
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
    
    def test_apply_template_action(self):
        """Test apply template custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-apply-template')
        data = {
            'policy_type': 'password_policy',
            'customizations': {
                'min_length': 14
            }
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('policy_key', response.data)
    
    def test_get_compliance_status_action(self):
        """Test get compliance status custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-compliance-status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('compliant', response.data)
    
    def test_export_policies(self):
        """Test exporting policies"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-export')
        response = self.client.post(url, {'format': 'json'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_import_policies(self):
        """Test importing policies"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securitypolicy-import')
        import_data = [
            {
                'policy_key': 'session_policy',
                'policy_value': {'timeout': 3600}
            }
        ]
        response = self.client.post(url, {'data': json.dumps(import_data)}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['imported_count'], 1)


class SecurityInsightViewSetTest(APITestCase):
    """Test SecurityInsightViewSet"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.security_insight = SecurityInsightFactory()
    
    def test_list_security_insights_staff(self):
        """Test listing security insights as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_list_security_insights_user_forbidden(self):
        """Test listing security insights as regular user (should be forbidden)"""
        self.client.force_authenticate(user=self.user)
        url = reverse('securityinsight-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_retrieve_security_insight_staff(self):
        """Test retrieving security insight as staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-detail', kwargs={'pk': self.security_insight.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.security_insight.id))
    
    def test_create_daily_insight_action(self):
        """Test create daily insight custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-create-daily')
        data = {'insight_date': timezone.now().date().isoformat()}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('insight_date', response.data)
    
    def test_get_trends_action(self):
        """Test get trends custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-trends')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_get_threat_intelligence_insights_action(self):
        """Test get threat intelligence insights custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-threat-intelligence')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_threats', response.data)
    
    def test_get_user_behavior_insights_action(self):
        """Test get user behavior insights custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-user-behavior')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_active_users', response.data)
    
    def test_get_network_security_insights_action(self):
        """Test get network security insights custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-network-security')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_unique_ips', response.data)
    
    def test_get_executive_summary_action(self):
        """Test get executive summary custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-executive-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_security_status', response.data)
    
    def test_export_insights(self):
        """Test exporting insights"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-export')
        response = self.client.post(url, {'format': 'json', 'days': 30})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_dashboard_action(self):
        """Test get dashboard custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overview', response.data)
    
    def test_get_real_time_insights_action(self):
        """Test get real-time insights custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-real-time')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('current_events_per_minute', response.data)
    
    def test_get_health_check_action(self):
        """Test get health check custom action"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityinsight-health-check')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_health', response.data)


class SecurityViewsIntegrationTest(TransactionTestCase):
    """Integration tests for security views"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.super_user = SuperUserFactory()
    
    def test_device_info_workflow(self):
        """Test complete device info workflow"""
        # Create device
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-list')
        data = {
            'device_fingerprint': 'workflow_test_fingerprint',
            'device_type': 'mobile',
            'device_name': 'Test Mobile Device',
            'ip_address': '192.168.1.100'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        device_id = response.data['id']
        
        # Trust device (as staff)
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('deviceinfo-trust', kwargs={'pk': device_id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_trusted'])
        
        # Verify device is trusted
        url = reverse('deviceinfo-detail', kwargs={'pk': device_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_trusted'])
    
    def test_security_incident_workflow(self):
        """Test complete security incident workflow"""
        # Create incident
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('securityincident-list')
        data = {
            'user': self.user.id,
            'incident_type': 'security_breach',
            'severity': 'high',
            'title': 'Test Workflow Incident',
            'description': 'Testing complete workflow'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        incident_id = response.data['id']
        
        # Assign incident
        url = reverse('securityincident-assign', kwargs={'pk': incident_id})
        response = self.client.post(url, {'assigned_to': self.staff_user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assigned_to'], self.staff_user.id)
        
        # Add evidence
        url = reverse('securityincident-add-evidence', kwargs={'pk': incident_id})
        evidence_data = {
            'evidence': {
                'suspicious_ips': ['192.168.1.100', '192.168.1.101'],
                'log_entries': ['Entry 1', 'Entry 2']
            }
        }
        response = self.client.post(url, evidence_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('suspicious_ips', response.data['evidence'])
        
        # Resolve incident
        url = reverse('securityincident-resolve', kwargs={'pk': incident_id})
        response = self.client.post(url, {'resolution': 'Investigation completed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'resolved')
    
    def test_threat_intelligence_workflow(self):
        """Test complete threat intelligence workflow"""
        # Create threat intelligence
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('threatintelligence-list')
        data = {
            'threat_type': 'malware',
            'indicator_type': 'ip',
            'indicators': ['192.168.1.100', '192.168.1.101'],
            'severity': 'high',
            'confidence': 0.85,
            'source': 'internal_analysis'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        threat_id = response.data['id']
        
        # Update threat intelligence
        url = reverse('threatintelligence-detail', kwargs={'pk': threat_id})
        response = self.client.patch(url, {'severity': 'critical'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['severity'], 'critical')
        
        # Export threat intelligence
        url = reverse('threatintelligence-export')
        response = self.client.post(url, {'format': 'json'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_permission_hierarchy(self):
        """Test permission hierarchy across different user types"""
        # Regular user should only access their own data
        self.client.force_authenticate(user=self.user)
        
        # Can access own device info
        url = reverse('deviceinfo-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cannot access security logs (filtered to own only)
        url = reverse('securitylog-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Cannot access threat intelligence
        url = reverse('threatintelligence-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Staff user can access more data
        self.client.force_authenticate(user=self.staff_user)
        
        url = reverse('threatintelligence-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # But still cannot delete incidents
        incident = SecurityIncidentFactory()
        url = reverse('securityincident-detail', kwargs={'pk': incident.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Super user can do everything
        self.client.force_authenticate(user=self.super_user)
        
        url = reverse('securityincident-detail', kwargs={'pk': incident.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_api_error_handling(self):
        """Test API error handling"""
        self.client.force_authenticate(user=self.user)
        
        # Test invalid data
        url = reverse('deviceinfo-list')
        invalid_data = {
            'device_fingerprint': '',  # Invalid: empty
            'device_type': 'invalid_type'  # Invalid: not in choices
        }
        response = self.client.post(url, invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test non-existent resource
        url = reverse('deviceinfo-detail', kwargs={'pk': 'non-existent-id'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test unauthorized access
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_api_performance(self):
        """Test API performance with bulk operations"""
        # Create multiple devices
        self.client.force_authenticate(user=self.user)
        url = reverse('deviceinfo-list')
        
        devices = []
        for i in range(10):
            data = {
                'device_fingerprint': f'perf_test_fingerprint_{i}',
                'device_type': 'desktop',
                'device_name': f'Performance Test Device {i}',
                'ip_address': f'192.168.1.{i + 100}'
            }
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            devices.append(response.data['id'])
        
        # List all devices
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 11)  # 10 new + 1 from setUp
    
    def test_api_versioning(self):
        """Test API versioning"""
        # Test v1 endpoints (if implemented)
        self.client.force_authenticate(user=self.staff_user)
        
        # Test that endpoints respond correctly
        endpoints = [
            'deviceinfo-list',
            'securitylog-list',
            'userban-list',
            'riskscore-list',
            'threatintelligence-list',
            'securityincident-list',
            'trusteddevice-list',
            'passwordhistory-list',
            'securitypolicy-list',
            'securityinsight-list'
        ]
        
        for endpoint in endpoints:
            url = reverse(endpoint)
            response = self.client.get(url)
            # Should either work or return appropriate error
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])
    
    def test_api_filtering_and_pagination(self):
        """Test API filtering and pagination"""
        self.client.force_authenticate(user=self.staff_user)
        
        # Create multiple security logs
        SecurityLogFactory.create_batch(20, severity='info')
        SecurityLogFactory.create_batch(10, severity='warning')
        SecurityLogFactory.create_batch(5, severity='error')
        
        # Test filtering
        url = reverse('securitylog-list')
        response = self.client.get(url, {'severity': 'warning'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Test pagination
        response = self.client.get(url, {'page': 1, 'page_size': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        self.assertIn('next', response.data)
    
    def test_api_serialization(self):
        """Test API serialization"""
        self.client.force_authenticate(user=self.staff_user)
        
        # Test device info serialization
        url = reverse('deviceinfo-detail', kwargs={'pk': self.device.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check required fields are present
        required_fields = [
            'id', 'user', 'device_fingerprint', 'device_type', 'device_name',
            'operating_system', 'browser', 'ip_address', 'trust_score',
            'is_trusted', 'created_at', 'updated_at'
        ]
        
        for field in required_fields:
            self.assertIn(field, response.data)
        
        # Test datetime fields are properly serialized
        self.assertIsInstance(response.data['created_at'], str)
        self.assertIsInstance(response.data['updated_at'], str)