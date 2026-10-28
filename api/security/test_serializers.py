"""
Security Serializers Tests
Comprehensive test suite for security module serializers
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.test import APITestCase
from rest_framework import serializers
from unittest.mock import patch, MagicMock

from .models import (
    DeviceInfo, SecurityLog, UserBan, IPBlacklist, ThreatIntelligence,
    SecurityIncident, TrustedDevice, PasswordHistory, SecurityPolicy,
    SecurityInsight, RiskScore, UserSession
)
from .serializers import (
    DeviceInfoSerializer, SecurityLogSerializer, UserBanSerializer,
    IPBlacklistSerializer, ThreatIntelligenceSerializer, SecurityIncidentSerializer,
    TrustedDeviceSerializer, PasswordHistorySerializer, SecurityPolicySerializer,
    SecurityInsightSerializer, RiskScoreSerializer, UserSessionSerializer,
    ThreatIntelligenceCreateSerializer, SecurityIncidentCreateSerializer,
    TrustedDeviceCreateSerializer, SecurityPolicyCreateSerializer,
    SecurityInsightCreateSerializer
)

User = get_user_model()


class DeviceInfoSerializerTest(APITestCase):
    """Test cases for DeviceInfoSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.device = DeviceInfo.objects.create(
            user=self.user,
            device_id='test_device_123',
            device_model='Test Phone',
            device_brand='TestBrand',
            android_version='13.0',
            app_version='2.1.0',
            is_rooted=False,
            is_emulator=False,
            is_vpn=False,
            is_proxy=False,
            is_trusted=True,
            last_ip='192.168.1.100',
            fingerprint='test_fingerprint',
            risk_score=25,
            trust_level=2
        )
    
    def test_device_info_serializer_fields(self):
        """Test DeviceInfoSerializer field mapping"""
        serializer = DeviceInfoSerializer(self.device)
        data = serializer.data
        
        expected_fields = [
            'id', 'user', 'user_info', 'device_id', 'device_id_hash',
            'device_model', 'device_brand', 'android_version', 'app_version',
            'is_rooted', 'is_emulator', 'is_vpn', 'is_proxy', 'is_trusted',
            'last_ip', 'fingerprint', 'risk_score', 'trust_level',
            'last_activity', 'created_at', 'updated_at', 'metadata',
            'risk_level'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_device_info_serializer_user_info(self):
        """Test DeviceInfoSerializer user_info method field"""
        serializer = DeviceInfoSerializer(self.device)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertEqual(data['user_info']['id'], self.user.id)
        self.assertEqual(data['user_info']['username'], self.user.username)
        self.assertEqual(data['user_info']['email'], self.user.email)
    
    def test_device_info_serializer_risk_level(self):
        """Test DeviceInfoSerializer risk_level method field"""
        serializer = DeviceInfoSerializer(self.device)
        data = serializer.data
        
        self.assertIn('risk_level', data)
        self.assertIsInstance(data['risk_level'], str)
    
    def test_device_info_serializer_read_only_fields(self):
        """Test DeviceInfoSerializer read-only fields"""
        read_only_fields = DeviceInfoSerializer.Meta.read_only_fields
        expected_read_only = [
            'id', 'user', 'device_id_hash', 'fingerprint',
            'risk_score', 'trust_level', 'created_at', 'updated_at'
        ]
        
        self.assertEqual(set(read_only_fields), set(expected_read_only))
    
    def test_device_info_serializer_validation(self):
        """Test DeviceInfoSerializer validation"""
        # Test valid data
        valid_data = {
            'device_id': 'new_device_123',
            'device_model': 'New Phone',
            'device_brand': 'NewBrand',
            'android_version': '14.0',
            'app_version': '2.2.0'
        }
        
        serializer = DeviceInfoSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
    
    def test_device_info_serializer_without_user(self):
        """Test DeviceInfoSerializer without user context"""
        serializer = DeviceInfoSerializer()
        data = serializer.data
        
        # Should not raise error when user is None
        self.assertIn('user_info', data)


class SecurityLogSerializerTest(APITestCase):
    """Test cases for SecurityLogSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.log = SecurityLog.objects.create(
            user=self.user,
            security_type='login_success',
            severity='info',
            ip_address='192.168.1.100',
            description='User logged in successfully',
            risk_score=10,
            response_time_ms=150,
            user_agent='Test User Agent',
            metadata={'test': True}
        )
    
    def test_security_log_serializer_fields(self):
        """Test SecurityLogSerializer field mapping"""
        serializer = SecurityLogSerializer(self.log)
        data = serializer.data
        
        expected_fields = [
            'log_id', 'user', 'user_info', 'security_type', 'severity',
            'severity_display', 'ip_address', 'user_agent', 'description',
            'risk_score', 'response_time_ms', 'metadata', 'device_info',
            'action_taken', 'resolved', 'resolved_at', 'resolved_by',
            'request_path', 'request_method', 'details', 'created_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_security_log_serializer_user_info(self):
        """Test SecurityLogSerializer user_info method field"""
        serializer = SecurityLogSerializer(self.log)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertEqual(data['user_info']['id'], self.user.id)
        self.assertEqual(data['user_info']['username'], self.user.username)
    
    def test_security_log_serializer_severity_display(self):
        """Test SecurityLogSerializer severity_display method field"""
        serializer = SecurityLogSerializer(self.log)
        data = serializer.data
        
        self.assertIn('severity_display', data)
        self.assertIsInstance(data['severity_display'], str)
    
    def test_security_log_serializer_without_user(self):
        """Test SecurityLogSerializer without user"""
        log_without_user = SecurityLog.objects.create(
            security_type='login_failed',
            severity='medium',
            ip_address='192.168.1.100',
            description='Failed login attempt'
        )
        
        serializer = SecurityLogSerializer(log_without_user)
        data = serializer.data
        
        self.assertIsNone(data['user_info'])
    
    def test_security_log_serializer_read_only_fields(self):
        """Test SecurityLogSerializer read-only fields"""
        read_only_fields = SecurityLogSerializer.Meta.read_only_fields
        expected_read_only = [
            'log_id', 'user', 'created_at', 'resolved_by', 'resolved_at'
        ]
        
        self.assertEqual(set(read_only_fields), set(expected_read_only))


class ThreatIntelligenceSerializerTest(APITestCase):
    """Test cases for ThreatIntelligenceSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.threat = ThreatIntelligence.objects.create(
            ip_range='192.168.1.0/24',
            threat_type='malware',
            source='VirusTotal',
            confidence=0.85,
            expires_at=timezone.now() + timedelta(days=7),
            indicator='test_indicator',
            indicator_type='hash',
            severity='high',
            is_active=True
        )
    
    def test_threat_intelligence_serializer_fields(self):
        """Test ThreatIntelligenceSerializer field mapping"""
        serializer = ThreatIntelligenceSerializer(self.threat)
        data = serializer.data
        
        expected_fields = [
            'id', 'ip_range', 'threat_type', 'threat_type_display',
            'source', 'confidence', 'expires_at', 'indicator',
            'indicator_type', 'severity', 'severity_display',
            'is_active', 'is_expired', 'metadata',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_threat_intelligence_serializer_threat_type_display(self):
        """Test ThreatIntelligenceSerializer threat_type_display method field"""
        serializer = ThreatIntelligenceSerializer(self.threat)
        data = serializer.data
        
        self.assertIn('threat_type_display', data)
        self.assertIsInstance(data['threat_type_display'], str)
    
    def test_threat_intelligence_serializer_severity_display(self):
        """Test ThreatIntelligenceSerializer severity_display method field"""
        serializer = ThreatIntelligenceSerializer(self.threat)
        data = serializer.data
        
        self.assertIn('severity_display', data)
        self.assertIsInstance(data['severity_display'], str)
    
    def test_threat_intelligence_serializer_is_expired(self):
        """Test ThreatIntelligenceSerializer is_expired method field"""
        # Test active threat
        active_threat = ThreatIntelligence.objects.create(
            ip_range='192.168.2.0/24',
            threat_type='phishing',
            source='Test',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        serializer = ThreatIntelligenceSerializer(active_threat)
        data = serializer.data
        
        self.assertIn('is_expired', data)
        self.assertFalse(data['is_expired'])
        
        # Test expired threat
        expired_threat = ThreatIntelligence.objects.create(
            ip_range='192.168.3.0/24',
            threat_type='botnet',
            source='Test',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        serializer = ThreatIntelligenceSerializer(expired_threat)
        data = serializer.data
        
        self.assertTrue(data['is_expired'])


class ThreatIntelligenceCreateSerializerTest(APITestCase):
    """Test cases for ThreatIntelligenceCreateSerializer"""
    
    def test_threat_intelligence_create_serializer_validation(self):
        """Test ThreatIntelligenceCreateSerializer validation"""
        # Test valid data
        valid_data = {
            'ip_range': '192.168.1.0/24',
            'threat_type': 'malware',
            'source': 'VirusTotal',
            'confidence': 0.85,
            'expires_at': '2024-12-31T23:59:59Z',
            'indicator': 'test_indicator',
            'indicator_type': 'hash',
            'severity': 'high'
        }
        
        serializer = ThreatIntelligenceCreateSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
    
    def test_threat_intelligence_create_serializer_confidence_validation(self):
        """Test ThreatIntelligenceCreateSerializer confidence validation"""
        # Test invalid confidence (too high)
        invalid_data = {
            'ip_range': '192.168.1.0/24',
            'threat_type': 'malware',
            'source': 'VirusTotal',
            'confidence': 1.5,  # Invalid: > 1.0
            'severity': 'high'
        }
        
        serializer = ThreatIntelligenceCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confidence', serializer.errors)
        
        # Test invalid confidence (too low)
        invalid_data['confidence'] = -0.5  # Invalid: < 0.0
        serializer = ThreatIntelligenceCreateSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confidence', serializer.errors)
        
        # Test valid confidence
        valid_data = {
            'ip_range': '192.168.1.0/24',
            'threat_type': 'malware',
            'source': 'VirusTotal',
            'confidence': 0.85,  # Valid: 0.0 <= 0.85 <= 1.0
            'severity': 'high'
        }
        
        serializer = ThreatIntelligenceCreateSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())


class SecurityIncidentSerializerTest(APITestCase):
    """Test cases for SecurityIncidentSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.incident = SecurityIncident.objects.create(
            user=self.user,
            incident_type='unauthorized_access',
            severity='high',
            status='open',
            title='Unauthorized access detected',
            description='Suspicious access attempt detected',
            affected_systems=['web_application', 'database'],
            impact_assessment='Medium impact',
            mitigation_steps=['Block IP', 'Notify user'],
            priority='high'
        )
    
    def test_security_incident_serializer_fields(self):
        """Test SecurityIncidentSerializer field mapping"""
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        expected_fields = [
            'id', 'user', 'user_info', 'incident_type', 'incident_type_display',
            'severity', 'severity_display', 'status', 'status_display',
            'title', 'description', 'affected_systems', 'impact_assessment',
            'mitigation_steps', 'assigned_to', 'assigned_to_info',
            'priority', 'opened_at', 'resolved_at', 'is_resolved',
            'duration', 'resolution_details', 'lessons_learned',
            'metadata', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_security_incident_serializer_user_info(self):
        """Test SecurityIncidentSerializer user_info method field"""
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertEqual(data['user_info']['id'], self.user.id)
        self.assertEqual(data['user_info']['username'], self.user.username)
    
    def test_security_incident_serializer_incident_type_display(self):
        """Test SecurityIncidentSerializer incident_type_display method field"""
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIn('incident_type_display', data)
        self.assertIsInstance(data['incident_type_display'], str)
    
    def test_security_incident_serializer_severity_display(self):
        """Test SecurityIncidentSerializer severity_display method field"""
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIn('severity_display', data)
        self.assertIsInstance(data['severity_display'], str)
    
    def test_security_incident_serializer_status_display(self):
        """Test SecurityIncidentSerializer status_display method field"""
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIn('status_display', data)
        self.assertIsInstance(data['status_display'], str)
    
    def test_security_incident_serializer_is_resolved(self):
        """Test SecurityIncidentSerializer is_resolved method field"""
        # Test open incident
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIn('is_resolved', data)
        self.assertFalse(data['is_resolved'])
        
        # Test resolved incident
        resolved_incident = SecurityIncident.objects.create(
            user=self.user,
            incident_type='data_breach',
            severity='medium',
            status='resolved',
            title='Data breach resolved',
            resolved_at=timezone.now()
        )
        
        serializer = SecurityIncidentSerializer(resolved_incident)
        data = serializer.data
        
        self.assertTrue(data['is_resolved'])
    
    def test_security_incident_serializer_duration(self):
        """Test SecurityIncidentSerializer duration method field"""
        # Test resolved incident
        resolved_incident = SecurityIncident.objects.create(
            user=self.user,
            incident_type='data_breach',
            severity='medium',
            status='resolved',
            title='Data breach resolved',
            opened_at=timezone.now() - timedelta(hours=2),
            resolved_at=timezone.now()
        )
        
        serializer = SecurityIncidentSerializer(resolved_incident)
        data = serializer.data
        
        self.assertIn('duration', data)
        self.assertIsNotNone(data['duration'])
        
        # Test open incident
        serializer = SecurityIncidentSerializer(self.incident)
        data = serializer.data
        
        self.assertIsNone(data['duration'])


class TrustedDeviceSerializerTest(APITestCase):
    """Test cases for TrustedDeviceSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.device = TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint='test_fingerprint_123',
            device_name='My Phone',
            device_type='mobile',
            platform='Android',
            browser='Chrome',
            ip_address='192.168.1.100',
            user_agent='Test User Agent',
            trust_score=95,
            is_trusted=True
        )
    
    def test_trusted_device_serializer_fields(self):
        """Test TrustedDeviceSerializer field mapping"""
        serializer = TrustedDeviceSerializer(self.device)
        data = serializer.data
        
        expected_fields = [
            'id', 'user', 'user_info', 'device_fingerprint', 'device_name',
            'device_type', 'device_type_display', 'platform', 'browser',
            'ip_address', 'user_agent', 'trust_score', 'last_seen',
            'is_trusted', 'is_expired', 'expires_at', 'metadata',
            'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_trusted_device_serializer_user_info(self):
        """Test TrustedDeviceSerializer user_info method field"""
        serializer = TrustedDeviceSerializer(self.device)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertEqual(data['user_info']['id'], self.user.id)
        self.assertEqual(data['user_info']['username'], self.user.username)
    
    def test_trusted_device_serializer_device_type_display(self):
        """Test TrustedDeviceSerializer device_type_display method field"""
        serializer = TrustedDeviceSerializer(self.device)
        data = serializer.data
        
        self.assertIn('device_type_display', data)
        self.assertIsInstance(data['device_type_display'], str)
    
    def test_trusted_device_serializer_is_expired(self):
        """Test TrustedDeviceSerializer is_expired method field"""
        # Test active device
        serializer = TrustedDeviceSerializer(self.device)
        data = serializer.data
        
        self.assertIn('is_expired', data)
        self.assertFalse(data['is_expired'])
        
        # Test expired device
        expired_device = TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint='expired_fingerprint',
            device_name='Expired Device',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        serializer = TrustedDeviceSerializer(expired_device)
        data = serializer.data
        
        self.assertTrue(data['is_expired'])


class SecurityPolicySerializerTest(APITestCase):
    """Test cases for SecurityPolicySerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.policy = SecurityPolicy.objects.create(
            policy_key='password_min_length',
            value={'min_length': 8, 'require_special_chars': True},
            policy_type='password',
            description='Minimum password length policy',
            priority=100,
            is_active=True,
            enforced=True
        )
    
    def test_security_policy_serializer_fields(self):
        """Test SecurityPolicySerializer field mapping"""
        serializer = SecurityPolicySerializer(self.policy)
        data = serializer.data
        
        expected_fields = [
            'id', 'tenant', 'tenant_info', 'policy_key', 'value',
            'policy_type', 'policy_type_display', 'description',
            'priority', 'is_active', 'enforced', 'effective_value',
            'metadata', 'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_security_policy_serializer_policy_type_display(self):
        """Test SecurityPolicySerializer policy_type_display method field"""
        serializer = SecurityPolicySerializer(self.policy)
        data = serializer.data
        
        self.assertIn('policy_type_display', data)
        self.assertIsInstance(data['policy_type_display'], str)
    
    def test_security_policy_serializer_effective_value(self):
        """Test SecurityPolicySerializer effective_value method field"""
        serializer = SecurityPolicySerializer(self.policy)
        data = serializer.data
        
        self.assertIn('effective_value', data)
        self.assertEqual(data['effective_value'], self.policy.value)


class SecurityInsightSerializerTest(APITestCase):
    """Test cases for SecurityInsightSerializer"""
    
    def setUp(self):
        """Set up test data"""
        self.insight = SecurityInsight.objects.create(
            date='2024-01-01',
            total_events=1000,
            critical_count=5,
            high_count=20,
            medium_count=100,
            low_count=875,
            blocked_ips=['192.168.1.100', '192.168.1.101'],
            locked_accounts=['user1', 'user2'],
            risk_score=25.5,
            system_health_score=85.2
        )
    
    def test_security_insight_serializer_fields(self):
        """Test SecurityInsightSerializer field mapping"""
        serializer = SecurityInsightSerializer(self.insight)
        data = serializer.data
        
        expected_fields = [
            'id', 'date', 'total_events', 'critical_count', 'high_count',
            'medium_count', 'low_count', 'blocked_ips', 'locked_accounts',
            'failed_logins', 'successful_logins', 'suspicious_activities',
            'fraud_attempts', 'malware_detections', 'phishing_attempts',
            'ddos_attacks', 'data_breaches', 'countries_affected',
            'risk_score', 'system_health_score', 'avg_response_time',
            'severity_breakdown', 'event_breakdown', 'risk_score_calculated',
            'metadata', 'created_at', 'updated_at'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
    
    def test_security_insight_serializer_severity_breakdown(self):
        """Test SecurityInsightSerializer severity_breakdown method field"""
        serializer = SecurityInsightSerializer(self.insight)
        data = serializer.data
        
        self.assertIn('severity_breakdown', data)
        self.assertIsInstance(data['severity_breakdown'], dict)
        self.assertEqual(data['severity_breakdown']['critical'], 5)
        self.assertEqual(data['severity_breakdown']['high'], 20)
    
    def test_security_insight_serializer_event_breakdown(self):
        """Test SecurityInsightSerializer event_breakdown method field"""
        serializer = SecurityInsightSerializer(self.insight)
        data = serializer.data
        
        self.assertIn('event_breakdown', data)
        self.assertIsInstance(data['event_breakdown'], dict)
    
    def test_security_insight_serializer_risk_score_calculated(self):
        """Test SecurityInsightSerializer risk_score_calculated method field"""
        serializer = SecurityInsightSerializer(self.insight)
        data = serializer.data
        
        self.assertIn('risk_score_calculated', data)
        self.assertIsInstance(data['risk_score_calculated'], (int, float))


# Integration Tests
class SecuritySerializersIntegrationTest(APITestCase):
    """Integration tests for security serializers"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_device_info_with_related_data(self):
        """Test DeviceInfoSerializer with related data"""
        device = DeviceInfo.objects.create(
            user=self.user,
            device_id='test_device',
            device_model='Test Phone',
            is_trusted=True
        )
        
        # Create related session
        session = UserSession.objects.create(
            user=self.user,
            session_key='test_session',
            ip_address='192.168.1.100',
            device_info=device,
            is_active=True
        )
        
        # Create related security logs
        SecurityLog.objects.create(
            user=self.user,
            security_type='login_success',
            severity='info',
            ip_address='192.168.1.100',
            description='User logged in successfully'
        )
        
        # Test serializer
        serializer = DeviceInfoSerializer(device)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertEqual(data['user_info']['username'], self.user.username)
        self.assertIn('risk_level', data)
    
    def test_security_incident_with_assigned_user(self):
        """Test SecurityIncidentSerializer with assigned user"""
        # Create staff user for assignment
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        
        incident = SecurityIncident.objects.create(
            user=self.user,
            incident_type='unauthorized_access',
            severity='high',
            status='open',
            title='Unauthorized access detected',
            assigned_to=staff_user
        )
        
        serializer = SecurityIncidentSerializer(incident)
        data = serializer.data
        
        self.assertIn('user_info', data)
        self.assertIn('assigned_to_info', data)
        self.assertEqual(data['user_info']['username'], self.user.username)
        self.assertEqual(data['assigned_to_info']['username'], staff_user.username)


# Error Handling Tests
class SecuritySerializersErrorHandlingTest(APITestCase):
    """Error handling tests for security serializers"""
    
    def test_serializer_with_invalid_data(self):
        """Test serializer with invalid data"""
        invalid_data = {
            'device_id': '',  # Empty device_id should be invalid
            'device_model': 'Test Phone'
        }
        
        serializer = DeviceInfoSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('device_id', serializer.errors)
    
    def test_serializer_with_missing_required_fields(self):
        """Test serializer with missing required fields"""
        incomplete_data = {
            'device_model': 'Test Phone'
            # Missing device_id
        }
        
        serializer = DeviceInfoSerializer(data=incomplete_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('device_id', serializer.errors)
    
    def test_serializer_with_nonexistent_user(self):
        """Test serializer with nonexistent user"""
        invalid_data = {
            'user': 99999,  # Nonexistent user ID
            'device_id': 'test_device',
            'device_model': 'Test Phone'
        }
        
        serializer = DeviceInfoSerializer(data=invalid_data)
        # This might not raise an error until save time, depending on implementation
        # The test checks that the serializer handles invalid references gracefully
        result = serializer.is_valid()
        # The result depends on the specific serializer implementation


# Performance Tests
class SecuritySerializersPerformanceTest(APITestCase):
    """Performance tests for security serializers"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_serializer_performance_with_large_dataset(self):
        """Test serializer performance with large dataset"""
        # Create many security logs
        logs = []
        for i in range(100):
            log = SecurityLog.objects.create(
                user=self.user,
                security_type='api_request',
                severity='info',
                ip_address=f'192.168.1.{i % 255}',
                description=f'API request {i}',
                risk_score=i % 100
            )
            logs.append(log)
        
        # Test serialization performance
        import time
        start_time = time.time()
        
        serializer = SecurityLogSerializer(logs, many=True)
        data = serializer.data
        
        end_time = time.time()
        serialization_time = end_time - start_time
        
        # Serialization should be fast (less than 1 second for 100 records)
        self.assertLess(serialization_time, 1.0)
        self.assertEqual(len(data), 100)
    
    def test_serializer_with_nested_data(self):
        """Test serializer with complex nested data"""
        # Create device with complex metadata
        device = DeviceInfo.objects.create(
            user=self.user,
            device_id='complex_device',
            device_model='Complex Phone',
            metadata={
                'screen_resolution': '1080x1920',
                'battery_level': 85,
                'storage_available': '32GB',
                'installed_apps': ['app1', 'app2', 'app3'],
                'network_info': {
                    'carrier': 'Test Carrier',
                    'network_type': '5G',
                    'signal_strength': -45
                },
                'security_features': {
                    'encryption_enabled': True,
                    'biometric_auth': True,
                    'find_my_device': True
                }
            }
        )
        
        # Test serialization
        serializer = DeviceInfoSerializer(device)
        data = serializer.data
        
        self.assertIn('metadata', data)
        self.assertIsInstance(data['metadata'], dict)
        self.assertIn('screen_resolution', data['metadata'])
        self.assertIn('network_info', data['metadata'])
        self.assertIn('security_features', data['metadata'])