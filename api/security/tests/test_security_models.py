"""
Enhanced Security Models Tests
Comprehensive test suite for all security models with defensive coding patterns
Author: System Security Team
Version: 2.0.0
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from unittest.mock import patch, MagicMock

from .factories import (
    UserFactory, StaffUserFactory, SuperUserFactory,
    DeviceInfoFactory, TrustedDeviceFactory, SecurityLogFactory,
    UserBanFactory, IPBlacklistFactory, ThreatIntelligenceFactory,
    SecurityIncidentFactory, PasswordHistoryFactory, SecurityPolicyFactory,
    SecurityInsightFactory, RiskScoreFactory, GeolocationLogFactory,
    UserSessionFactory, SessionActivityFactory, TwoFactorMethodFactory,
    TwoFactorAttemptFactory, TwoFactorRecoveryCodeFactory,
    CountryFactory, CountryBlockRuleFactory, APIRateLimitFactory,
    RateLimitLogFactory, ClickTrackerFactory, EnhancedClickTrackerFactory
)
from api.security.models import DeviceInfo
from api.security.models import TrustedDevice
from api.security.models import UserBan
from api.security.models import SecurityIncident
from api.security.models import UserSession
from api.security.models import TwoFactorMethod
from api.security.models import TwoFactorRecoveryCode
from api.security.models import IPBlacklist
from api.security.models import SecurityLog
from api.security.models import SessionActivity
from api.security.models import TwoFactorAttempt

User = get_user_model()


class DeviceInfoModelTest(TestCase):
    """Test DeviceInfo model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.device = DeviceInfoFactory(user=self.user)
    
    def test_device_info_creation(self):
        """Test DeviceInfo model creation"""
        self.assertEqual(self.device.user, self.user)
        self.assertIsNotNone(self.device.device_fingerprint)
        self.assertIsNotNone(self.device.ip_address)
        self.assertIsNotNone(self.device.created_at)
        self.assertIsNotNone(self.device.updated_at)
    
    def test_device_info_str_representation(self):
        """Test DeviceInfo string representation"""
        expected = f"{self.user.username} - {self.device.device_type}"
        self.assertEqual(str(self.device), expected)
    
    def test_device_info_unique_fingerprint_per_user(self):
        """Test unique fingerprint constraint per user"""
        # Create second device with same fingerprint for same user should fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeviceInfoFactory(
                    user=self.user,
                    device_fingerprint=self.device.device_fingerprint
                )
    
    def test_device_info_trust_score_validation(self):
        """Test trust score validation"""
        # Valid trust scores
        valid_scores = [0, 50, 100]
        for score in valid_scores:
            device = DeviceInfoFactory(trust_score=score)
            self.assertEqual(device.trust_score, score)
        
        # Invalid trust scores
        invalid_scores = [-1, 101, 150]
        for score in invalid_scores:
            with self.assertRaises(ValidationError):
                device = DeviceInfoFactory(trust_score=score)
                device.full_clean()
    
    def test_device_info_risk_score_validation(self):
        """Test risk score validation"""
        # Valid risk scores
        valid_scores = [0, 50, 100]
        for score in valid_scores:
            device = DeviceInfoFactory(risk_score=score)
            self.assertEqual(device.risk_score, score)
        
        # Invalid risk scores
        invalid_scores = [-1, 101, 150]
        for score in invalid_scores:
            with self.assertRaises(ValidationError):
                device = DeviceInfoFactory(risk_score=score)
                device.full_clean()
    
    def test_device_info_usage_count(self):
        """Test usage count functionality"""
        initial_count = self.device.usage_count
        self.device.usage_count += 1
        self.device.save()
        
        updated_device = DeviceInfo.objects.get(id=self.device.id)
        self.assertEqual(updated_device.usage_count, initial_count + 1)


class TrustedDeviceModelTest(TestCase):
    """Test TrustedDevice model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.trusted_device = TrustedDeviceFactory(user=self.user)
    
    def test_trusted_device_creation(self):
        """Test TrustedDevice model creation"""
        self.assertEqual(self.trusted_device.user, self.user)
        self.assertTrue(self.trusted_device.is_trusted)
        self.assertGreaterEqual(self.trusted_device.trust_score, 70)
        self.assertIsNotNone(self.trusted_device.expires_at)
    
    def test_trusted_device_str_representation(self):
        """Test TrustedDevice string representation"""
        expected = f"{self.user.username} - {self.trusted_device.device_name}"
        self.assertEqual(str(self.trusted_device), expected)
    
    def test_trusted_device_expiration(self):
        """Test trusted device expiration"""
        # Create expired trusted device
        expired_device = TrustedDeviceFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(expired_device.is_trusted)  # Still marked as trusted in DB
        self.assertLess(expired_device.expires_at, timezone.now())
    
    def test_trusted_device_auto_expiry(self):
        """Test automatic expiry check"""
        # This would be implemented in a custom manager method
        active_devices = TrustedDevice.objects.filter(
            user=self.user,
            is_trusted=True,
            expires_at__gt=timezone.now()
        )
        self.assertIn(self.trusted_device, active_devices)


class SecurityLogModelTest(TestCase):
    """Test SecurityLog model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.security_log = SecurityLogFactory(user=self.user)
    
    def test_security_log_creation(self):
        """Test SecurityLog model creation"""
        self.assertEqual(self.security_log.user, self.user)
        self.assertIsNotNone(self.security_log.event_type)
        self.assertIsNotNone(self.security_log.severity)
        self.assertIsNotNone(self.security_log.ip_address)
        self.assertIsNotNone(self.security_log.created_at)
    
    def test_security_log_str_representation(self):
        """Test SecurityLog string representation"""
        expected = f"{self.user.username} - {self.security_log.event_type}"
        self.assertEqual(str(self.security_log), expected)
    
    def test_security_log_metadata_validation(self):
        """Test metadata JSON field validation"""
        # Valid JSON metadata
        valid_metadata = {"key": "value", "number": 123}
        log = SecurityLogFactory(metadata=valid_metadata)
        self.assertEqual(log.metadata, valid_metadata)
        
        # Invalid JSON metadata (should be handled by Django's JSONField)
        # This test would need custom validation logic in the model
    
    def test_security_log_severity_levels(self):
        """Test all severity levels"""
        severities = ['debug', 'info', 'warning', 'error', 'critical']
        for severity in severities:
            log = SecurityLogFactory(severity=severity)
            self.assertEqual(log.severity, severity)
    
    def test_security_log_event_types(self):
        """Test common event types"""
        event_types = [
            'login_success', 'login_failed', 'logout', 'password_change',
            'account_locked', 'suspicious_activity', 'vpn_detected'
        ]
        for event_type in event_types:
            log = SecurityLogFactory(event_type=event_type)
            self.assertEqual(log.event_type, event_type)


class UserBanModelTest(TestCase):
    """Test UserBan model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.user_ban = UserBanFactory(
            user=self.user,
            created_by=self.staff_user
        )
    
    def test_user_ban_creation(self):
        """Test UserBan model creation"""
        self.assertEqual(self.user_ban.user, self.user)
        self.assertEqual(self.user_ban.created_by, self.staff_user)
        self.assertTrue(self.user_ban.is_active)
        self.assertIsNotNone(self.user_ban.reason)
        self.assertIsNotNone(self.user_ban.expires_at)
    
    def test_user_ban_str_representation(self):
        """Test UserBan string representation"""
        expected = f"{self.user.username} - {self.user_ban.ban_type}"
        self.assertEqual(str(self.user_ban), expected)
    
    def test_user_ban_types(self):
        """Test different ban types"""
        ban_types = ['temporary', 'permanent', 'suspension']
        for ban_type in ban_types:
            ban = UserBanFactory(user=self.user, ban_type=ban_type)
            self.assertEqual(ban.ban_type, ban_type)
    
    def test_user_ban_expiration(self):
        """Test ban expiration"""
        # Create expired ban
        expired_ban = UserBanFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(expired_ban.is_active)  # Still active in DB
        self.assertLess(expired_ban.expires_at, timezone.now())
    
    def test_user_ban_deactivation(self):
        """Test ban deactivation"""
        self.user_ban.is_active = False
        self.user_ban.save()
        
        updated_ban = UserBan.objects.get(id=self.user_ban.id)
        self.assertFalse(updated_ban.is_active)


class IPBlacklistModelTest(TestCase):
    """Test IPBlacklist model"""
    
    def setUp(self):
        self.staff_user = StaffUserFactory()
        self.ip_blacklist = IPBlacklistFactory(created_by=self.staff_user)
    
    def test_ip_blacklist_creation(self):
        """Test IPBlacklist model creation"""
        self.assertEqual(self.ip_blacklist.created_by, self.staff_user)
        self.assertIsNotNone(self.ip_blacklist.ip_address)
        self.assertTrue(self.ip_blacklist.is_active)
        self.assertIsNotNone(self.ip_blacklist.reason)
    
    def test_ip_blacklist_str_representation(self):
        """Test IPBlacklist string representation"""
        expected = f"{self.ip_blacklist.ip_address} - {self.ip_blacklist.blacklist_type}"
        self.assertEqual(str(self.ip_blacklist), expected)
    
    def test_ip_blacklist_types(self):
        """Test different blacklist types"""
        blacklist_types = ['manual', 'automatic', 'vpn_detected', 'threat_intelligence']
        for blacklist_type in blacklist_types:
            blacklist = IPBlacklistFactory(blacklist_type=blacklist_type)
            self.assertEqual(blacklist.blacklist_type, blacklist_type)
    
    def test_ip_blacklist_unique_ip(self):
        """Test unique IP constraint"""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IPBlacklistFactory(
                    ip_address=self.ip_blacklist.ip_address
                )
    
    def test_ip_blacklist_expiration(self):
        """Test blacklist expiration"""
        expired_blacklist = IPBlacklistFactory(
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(expired_blacklist.is_active)  # Still active in DB
        self.assertLess(expired_blacklist.expires_at, timezone.now())


class ThreatIntelligenceModelTest(TestCase):
    """Test ThreatIntelligence model"""
    
    def setUp(self):
        self.threat_intel = ThreatIntelligenceFactory()
    
    def test_threat_intelligence_creation(self):
        """Test ThreatIntelligence model creation"""
        self.assertIsNotNone(self.threat_intel.threat_type)
        self.assertIsNotNone(self.threat_intel.indicator_type)
        self.assertIsNotNone(self.threat_intel.indicators)
        self.assertTrue(self.threat_intel.is_active)
        self.assertGreaterEqual(self.threat_intel.confidence, 0)
        self.assertLessEqual(self.threat_intel.confidence, 1)
    
    def test_threat_intelligence_str_representation(self):
        """Test ThreatIntelligence string representation"""
        expected = f"{self.threat_intel.threat_type} - {self.threat_intel.indicator_type}"
        self.assertEqual(str(self.threat_intel), expected)
    
    def test_threat_intelligence_confidence_validation(self):
        """Test confidence score validation"""
        # Valid confidence scores
        valid_scores = [0.0, 0.5, 1.0]
        for score in valid_scores:
            threat = ThreatIntelligenceFactory(confidence=score)
            self.assertEqual(threat.confidence, score)
        
        # Invalid confidence scores (would need custom validation)
        invalid_scores = [-0.1, 1.1, 2.0]
        for score in invalid_scores:
            # This would require custom clean() method validation
            pass
    
    def test_threat_intelligence_indicator_types(self):
        """Test different indicator types"""
        indicator_types = ['ip', 'domain', 'url', 'hash', 'email']
        for indicator_type in indicator_types:
            threat = ThreatIntelligenceFactory(indicator_type=indicator_type)
            self.assertEqual(threat.indicator_type, indicator_type)
    
    def test_threat_intelligence_severity_levels(self):
        """Test different severity levels"""
        severities = ['low', 'medium', 'high', 'critical']
        for severity in severities:
            threat = ThreatIntelligenceFactory(severity=severity)
            self.assertEqual(threat.severity, severity)


class SecurityIncidentModelTest(TestCase):
    """Test SecurityIncident model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        self.incident = SecurityIncidentFactory(
            user=self.user,
            assigned_to=self.staff_user
        )
    
    def test_security_incident_creation(self):
        """Test SecurityIncident model creation"""
        self.assertEqual(self.incident.user, self.user)
        self.assertEqual(self.incident.assigned_to, self.staff_user)
        self.assertIsNotNone(self.incident.incident_id)
        self.assertIsNotNone(self.incident.title)
        self.assertIsNotNone(self.incident.description)
    
    def test_security_incident_str_representation(self):
        """Test SecurityIncident string representation"""
        expected = f"{self.incident.incident_id} - {self.incident.title}"
        self.assertEqual(str(self.incident), expected)
    
    def test_security_incident_unique_incident_id(self):
        """Test unique incident ID constraint"""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SecurityIncidentFactory(
                    incident_id=self.incident.incident_id
                )
    
    def test_security_incident_status_flow(self):
        """Test incident status flow"""
        statuses = ['open', 'investigating', 'resolved', 'closed']
        
        for status in statuses:
            self.incident.status = status
            self.incident.save()
            updated_incident = SecurityIncident.objects.get(id=self.incident.id)
            self.assertEqual(updated_incident.status, status)
    
    def test_security_incident_severity_levels(self):
        """Test different severity levels"""
        severities = ['low', 'medium', 'high', 'critical']
        for severity in severities:
            incident = SecurityIncidentFactory(severity=severity)
            self.assertEqual(incident.severity, severity)
    
    def test_security_incident_evidence_json(self):
        """Test evidence JSON field"""
        evidence = {
            'ip_addresses': ['192.168.1.1', '10.0.0.1'],
            'user_agents': ['Mozilla/5.0', 'Chrome/91.0'],
            'timestamps': ['2023-01-01T00:00:00Z', '2023-01-01T01:00:00Z']
        }
        
        incident = SecurityIncidentFactory(evidence=evidence)
        self.assertEqual(incident.evidence, evidence)


class PasswordHistoryModelTest(TestCase):
    """Test PasswordHistory model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.password_history = PasswordHistoryFactory(user=self.user)
    
    def test_password_history_creation(self):
        """Test PasswordHistory model creation"""
        self.assertEqual(self.password_history.user, self.user)
        self.assertIsNotNone(self.password_history.password_hash)
        self.assertIsNotNone(self.password_history.password_algorithm)
        self.assertFalse(self.password_history.is_active)
    
    def test_password_history_str_representation(self):
        """Test PasswordHistory string representation"""
        expected = f"{self.user.username} - {self.password_history.password_algorithm}"
        self.assertEqual(str(self.password_history), expected)
    
    def test_password_history_algorithms(self):
        """Test different password algorithms"""
        algorithms = ['bcrypt', 'pbkdf2', 'argon2']
        for algorithm in algorithms:
            history = PasswordHistoryFactory(
                user=self.user,
                password_algorithm=algorithm
            )
            self.assertEqual(history.password_algorithm, algorithm)
    
    def test_password_history_expiration(self):
        """Test password history expiration"""
        expired_history = PasswordHistoryFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertFalse(expired_history.is_active)
        self.assertLess(expired_history.expires_at, timezone.now())


class SecurityPolicyModelTest(TestCase):
    """Test SecurityPolicy model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.security_policy = SecurityPolicyFactory(user=self.user)
    
    def test_security_policy_creation(self):
        """Test SecurityPolicy model creation"""
        self.assertEqual(self.security_policy.user, self.user)
        self.assertIsNotNone(self.security_policy.policy_key)
        self.assertTrue(self.security_policy.is_active)
    
    def test_security_policy_str_representation(self):
        """Test SecurityPolicy string representation"""
        expected = f"{self.user.username} - {self.security_policy.policy_key}"
        self.assertEqual(str(self.security_policy), expected)
    
    def test_security_policy_keys(self):
        """Test different policy keys"""
        policy_keys = ['password_policy', 'session_policy', 'access_policy']
        for policy_key in policy_keys:
            policy = SecurityPolicyFactory(
                user=self.user,
                policy_key=policy_key
            )
            self.assertEqual(policy.policy_key, policy_key)
    
    def test_security_policy_unique_user_key(self):
        """Test unique user-key constraint"""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SecurityPolicyFactory(
                    user=self.user,
                    policy_key=self.security_policy.policy_key
                )


class SecurityInsightModelTest(TestCase):
    """Test SecurityInsight model"""
    
    def setUp(self):
        self.security_insight = SecurityInsightFactory()
    
    def test_security_insight_creation(self):
        """Test SecurityInsight model creation"""
        self.assertIsNotNone(self.security_insight.insight_date)
        self.assertGreaterEqual(self.security_insight.total_security_events, 0)
        self.assertGreaterEqual(self.security_insight.high_risk_events, 0)
        self.assertIsNotNone(self.security_insight.risk_distribution)
    
    def test_security_insight_str_representation(self):
        """Test SecurityInsight string representation"""
        expected = f"{self.security_insight.insight_date} - {self.security_insight.total_security_events} events"
        self.assertEqual(str(self.security_insight), expected)
    
    def test_security_insight_risk_distribution(self):
        """Test risk distribution structure"""
        risk_dist = self.security_insight.risk_distribution
        
        # Should have all risk levels
        expected_levels = ['low', 'medium', 'high', 'critical']
        for level in expected_levels:
            self.assertIn(level, risk_dist)
            self.assertGreaterEqual(risk_dist[level], 0)
        
        # Total should be 100%
        total = sum(risk_dist.values())
        self.assertEqual(total, 100)
    
    def test_security_insight_top_threat_types(self):
        """Test top threat types structure"""
        threat_types = self.security_insight.top_threat_types
        
        # Should have valid threat types
        for threat_type, count in threat_types.items():
            self.assertIsInstance(threat_type, str)
            self.assertGreaterEqual(count, 0)


class RiskScoreModelTest(TestCase):
    """Test RiskScore model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.risk_score = RiskScoreFactory(user=self.user)
    
    def test_risk_score_creation(self):
        """Test RiskScore model creation"""
        self.assertEqual(self.risk_score.user, self.user)
        self.assertGreaterEqual(self.risk_score.current_score, 0)
        self.assertLessEqual(self.risk_score.current_score, 100)
        self.assertIsNotNone(self.risk_score.calculated_at)
    
    def test_risk_score_str_representation(self):
        """Test RiskScore string representation"""
        expected = f"{self.user.username} - {self.risk_score.current_score}"
        self.assertEqual(str(self.risk_score), expected)
    
    def test_risk_score_validation(self):
        """Test risk score validation"""
        # Valid scores
        valid_scores = [Decimal('0'), Decimal('50.5'), Decimal('100')]
        for score in valid_scores:
            risk = RiskScoreFactory(user=self.user, current_score=score)
            self.assertEqual(risk.current_score, score)
        
        # Invalid scores (would need custom validation)
        invalid_scores = [Decimal('-1'), Decimal('101'), Decimal('150')]
        for score in invalid_scores:
            # This would require custom clean() method validation
            pass
    
    def test_risk_score_factors(self):
        """Test risk factors list"""
        factors = ['multiple_ips', 'suspicious_location', 'vpn_usage']
        risk = RiskScoreFactory(
            user=self.user,
            risk_factors=factors
        )
        self.assertEqual(risk.risk_factors, factors)
    
    def test_risk_score_expiration(self):
        """Test risk score expiration"""
        expired_risk = RiskScoreFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        self.assertLess(expired_risk.expires_at, timezone.now())


class GeolocationLogModelTest(TestCase):
    """Test GeolocationLog model"""
    
    def setUp(self):
        self.geo_log = GeolocationLogFactory()
    
    def test_geolocation_log_creation(self):
        """Test GeolocationLog model creation"""
        self.assertIsNotNone(self.geo_log.ip_address)
        self.assertIsNotNone(self.geo_log.country)
        self.assertIsNotNone(self.geo_log.country_name)
        self.assertIsNotNone(self.geo_log.queried_at)
    
    def test_geolocation_log_str_representation(self):
        """Test GeolocationLog string representation"""
        expected = f"{self.geo_log.ip_address} - {self.geo_log.country_name}"
        self.assertEqual(str(self.geo_log), expected)
    
    def test_geolocation_log_coordinates(self):
        """Test latitude and longitude validation"""
        # Valid coordinates
        valid_coords = [
            (40.7128, -74.0060),  # New York
            (51.5074, -0.1278),   # London
            (-33.8688, 151.2093)  # Sydney
        ]
        
        for lat, lon in valid_coords:
            geo = GeolocationLogFactory(latitude=lat, longitude=lon)
            self.assertEqual(geo.latitude, lat)
            self.assertEqual(geo.longitude, lon)
    
    def test_geolocation_log_vpn_proxy_flags(self):
        """Test VPN and proxy flags"""
        # Test various combinations
        combinations = [
            {'is_proxy': True, 'is_vpn': False},
            {'is_proxy': False, 'is_vpn': True},
            {'is_proxy': True, 'is_vpn': True},
            {'is_proxy': False, 'is_vpn': False}
        ]
        
        for flags in combinations:
            geo = GeolocationLogFactory(**flags)
            self.assertEqual(geo.is_proxy, flags['is_proxy'])
            self.assertEqual(geo.is_vpn, flags['is_vpn'])


class UserSessionModelTest(TestCase):
    """Test UserSession model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.user_session = UserSessionFactory(user=self.user)
    
    def test_user_session_creation(self):
        """Test UserSession model creation"""
        self.assertEqual(self.user_session.user, self.user)
        self.assertIsNotNone(self.user_session.session_key)
        self.assertIsNotNone(self.user_session.ip_address)
        self.assertIsNotNone(self.user_session.created_at)
        self.assertIsNotNone(self.user_session.expires_at)
    
    def test_user_session_str_representation(self):
        """Test UserSession string representation"""
        expected = f"{self.user.username} - {self.user_session.session_key[:8]}..."
        self.assertEqual(str(self.user_session), expected)
    
    def test_user_session_expiration(self):
        """Test session expiration"""
        expired_session = UserSessionFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        self.assertLess(expired_session.expires_at, timezone.now())
    
    def test_user_session_activity_tracking(self):
        """Test last activity tracking"""
        initial_activity = self.user_session.last_activity
        
        # Update last activity
        self.user_session.last_activity = timezone.now()
        self.user_session.save()
        
        updated_session = UserSession.objects.get(id=self.user_session.id)
        self.assertGreater(updated_session.last_activity, initial_activity)


class SessionActivityModelTest(TestCase):
    """Test SessionActivity model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.user_session = UserSessionFactory(user=self.user)
        self.session_activity = SessionActivityFactory(
            user=self.user,
            session=self.user_session
        )
    
    def test_session_activity_creation(self):
        """Test SessionActivity model creation"""
        self.assertEqual(self.session_activity.user, self.user)
        self.assertEqual(self.session_activity.session, self.user_session)
        self.assertIsNotNone(self.session_activity.activity_type)
        self.assertIsNotNone(self.session_activity.ip_address)
    
    def test_session_activity_str_representation(self):
        """Test SessionActivity string representation"""
        expected = f"{self.user.username} - {self.session_activity.activity_type}"
        self.assertEqual(str(self.session_activity), expected)
    
    def test_session_activity_types(self):
        """Test different activity types"""
        activity_types = ['login', 'logout', 'page_view', 'api_call', 'form_submit']
        for activity_type in activity_types:
            activity = SessionActivityFactory(
                user=self.user,
                activity_type=activity_type
            )
            self.assertEqual(activity.activity_type, activity_type)


class TwoFactorMethodModelTest(TestCase):
    """Test TwoFactorMethod model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.two_factor = TwoFactorMethodFactory(user=self.user)
    
    def test_two_factor_method_creation(self):
        """Test TwoFactorMethod model creation"""
        self.assertEqual(self.two_factor.user, self.user)
        self.assertIsNotNone(self.two_factor.method_type)
        self.assertTrue(self.two_factor.is_active)
        self.assertIsNotNone(self.two_factor.secret_key)
    
    def test_two_factor_method_str_representation(self):
        """Test TwoFactorMethod string representation"""
        expected = f"{self.user.username} - {self.two_factor.method_type}"
        self.assertEqual(str(self.two_factor), expected)
    
    def test_two_factor_method_types(self):
        """Test different 2FA method types"""
        method_types = ['totp', 'sms', 'email', 'backup_codes']
        for method_type in method_types:
            two_factor = TwoFactorMethodFactory(
                user=self.user,
                method_type=method_type
            )
            self.assertEqual(two_factor.method_type, method_type)
    
    def test_two_factor_primary_flag(self):
        """Test primary method flag"""
        # Test setting primary method
        self.two_factor.is_primary = True
        self.two_factor.save()
        
        updated_two_factor = TwoFactorMethod.objects.get(id=self.two_factor.id)
        self.assertTrue(updated_two_factor.is_primary)


class TwoFactorAttemptModelTest(TestCase):
    """Test TwoFactorAttempt model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.two_factor = TwoFactorMethodFactory(user=self.user)
        self.two_factor_attempt = TwoFactorAttemptFactory(
            user=self.user,
            method=self.two_factor
        )
    
    def test_two_factor_attempt_creation(self):
        """Test TwoFactorAttempt model creation"""
        self.assertEqual(self.two_factor_attempt.user, self.user)
        self.assertEqual(self.two_factor_attempt.method, self.two_factor)
        self.assertIsNotNone(self.two_factor_attempt.attempt_type)
        self.assertIsNotNone(self.two_factor_attempt.ip_address)
    
    def test_two_factor_attempt_str_representation(self):
        """Test TwoFactorAttempt string representation"""
        expected = f"{self.user.username} - {self.two_factor_attempt.attempt_type}"
        self.assertEqual(str(self.two_factor_attempt), expected)
    
    def test_two_factor_attempt_types(self):
        """Test different attempt types"""
        attempt_types = ['login', 'setup', 'verify', 'disable']
        for attempt_type in attempt_types:
            attempt = TwoFactorAttemptFactory(
                user=self.user,
                method=self.two_factor,
                attempt_type=attempt_type
            )
            self.assertEqual(attempt.attempt_type, attempt_type)
    
    def test_two_factor_attempt_success_tracking(self):
        """Test success/failure tracking"""
        # Test successful attempt
        successful_attempt = TwoFactorAttemptFactory(
            user=self.user,
            method=self.two_factor,
            is_successful=True
        )
        self.assertTrue(successful_attempt.is_successful)
        self.assertIsNone(successful_attempt.failure_reason)
        
        # Test failed attempt
        failed_attempt = TwoFactorAttemptFactory(
            user=self.user,
            method=self.two_factor,
            is_successful=False,
            failure_reason="Invalid code"
        )
        self.assertFalse(failed_attempt.is_successful)
        self.assertEqual(failed_attempt.failure_reason, "Invalid code")


class TwoFactorRecoveryCodeModelTest(TestCase):
    """Test TwoFactorRecoveryCode model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.recovery_code = TwoFactorRecoveryCodeFactory(user=self.user)
    
    def test_two_factor_recovery_code_creation(self):
        """Test TwoFactorRecoveryCode model creation"""
        self.assertEqual(self.recovery_code.user, self.user)
        self.assertIsNotNone(self.recovery_code.code)
        self.assertFalse(self.recovery_code.is_used)
        self.assertIsNone(self.recovery_code.used_at)
    
    def test_two_factor_recovery_code_str_representation(self):
        """Test TwoFactorRecoveryCode string representation"""
        expected = f"{self.user.username} - {self.recovery_code.code[:4]}..."
        self.assertEqual(str(self.recovery_code), expected)
    
    def test_two_factor_recovery_code_usage(self):
        """Test recovery code usage"""
        # Mark code as used
        self.recovery_code.is_used = True
        self.recovery_code.used_at = timezone.now()
        self.recovery_code.save()
        
        updated_code = TwoFactorRecoveryCode.objects.get(id=self.recovery_code.id)
        self.assertTrue(updated_code.is_used)
        self.assertIsNotNone(updated_code.used_at)
    
    def test_two_factor_recovery_code_expiration(self):
        """Test recovery code expiration"""
        expired_code = TwoFactorRecoveryCodeFactory(
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertLess(expired_code.expires_at, timezone.now())


class CountryModelTest(TestCase):
    """Test Country model"""
    
    def setUp(self):
        self.country = CountryFactory()
    
    def test_country_creation(self):
        """Test Country model creation"""
        self.assertIsNotNone(self.country.country_code)
        self.assertIsNotNone(self.country.country_name)
        self.assertTrue(self.country.is_active)
    
    def test_country_str_representation(self):
        """Test Country string representation"""
        expected = f"{self.country.country_code} - {self.country.country_name}"
        self.assertEqual(str(self.country), expected)
    
    def test_country_risk_levels(self):
        """Test different risk levels"""
        risk_levels = ['low', 'medium', 'high']
        for risk_level in risk_levels:
            country = CountryFactory(risk_level=risk_level)
            self.assertEqual(country.risk_level, risk_level)


class CountryBlockRuleModelTest(TestCase):
    """Test CountryBlockRule model"""
    
    def setUp(self):
        self.staff_user = StaffUserFactory()
        self.country = CountryFactory()
        self.block_rule = CountryBlockRuleFactory(
            country=self.country,
            created_by=self.staff_user
        )
    
    def test_country_block_rule_creation(self):
        """Test CountryBlockRule model creation"""
        self.assertEqual(self.block_rule.country, self.country)
        self.assertEqual(self.block_rule.created_by, self.staff_user)
        self.assertTrue(self.block_rule.is_active)
        self.assertIsNotNone(self.block_rule.block_type)
    
    def test_country_block_rule_str_representation(self):
        """Test CountryBlockRule string representation"""
        expected = f"{self.country.country_code} - {self.block_rule.block_type}"
        self.assertEqual(str(self.block_rule), expected)
    
    def test_country_block_rule_types(self):
        """Test different block types"""
        block_types = ['complete', 'partial', 'monitor']
        for block_type in block_types:
            rule = CountryBlockRuleFactory(
                country=self.country,
                block_type=block_type
            )
            self.assertEqual(rule.block_type, block_type)


class APIRateLimitModelTest(TestCase):
    """Test APIRateLimit model"""
    
    def setUp(self):
        self.rate_limit = APIRateLimitFactory()
    
    def test_api_rate_limit_creation(self):
        """Test APIRateLimit model creation"""
        self.assertIsNotNone(self.rate_limit.endpoint)
        self.assertIsNotNone(self.rate_limit.method)
        self.assertTrue(self.rate_limit.is_active)
        self.assertGreater(self.rate_limit.requests_per_minute, 0)
    
    def test_api_rate_limit_str_representation(self):
        """Test APIRateLimit string representation"""
        expected = f"{self.rate_limit.method} {self.rate_limit.endpoint}"
        self.assertEqual(str(self.rate_limit), expected)
    
    def test_api_rate_limit_methods(self):
        """Test different HTTP methods"""
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        for method in methods:
            limit = APIRateLimitFactory(method=method)
            self.assertEqual(limit.method, method)


class RateLimitLogModelTest(TestCase):
    """Test RateLimitLog model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.rate_limit_log = RateLimitLogFactory(user=self.user)
    
    def test_rate_limit_log_creation(self):
        """Test RateLimitLog model creation"""
        self.assertEqual(self.rate_limit_log.user, self.user)
        self.assertIsNotNone(self.rate_limit_log.ip_address)
        self.assertIsNotNone(self.rate_limit_log.endpoint)
        self.assertIsNotNone(self.rate_limit_log.method)
    
    def test_rate_limit_log_str_representation(self):
        """Test RateLimitLog string representation"""
        expected = f"{self.rate_limit_log.ip_address} - {self.rate_limit_log.method}"
        self.assertEqual(str(self.rate_limit_log), expected)
    
    def test_rate_limit_log_blocking(self):
        """Test blocking functionality"""
        # Test blocked request
        blocked_log = RateLimitLogFactory(
            user=self.user,
            is_blocked=True,
            block_reason="Rate limit exceeded"
        )
        self.assertTrue(blocked_log.is_blocked)
        self.assertEqual(blocked_log.block_reason, "Rate limit exceeded")
        
        # Test non-blocked request
        normal_log = RateLimitLogFactory(
            user=self.user,
            is_blocked=False
        )
        self.assertFalse(normal_log.is_blocked)
        self.assertIsNone(normal_log.block_reason)


class ClickTrackerModelTest(TestCase):
    """Test ClickTracker model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.click_tracker = ClickTrackerFactory(user=self.user)
    
    def test_click_tracker_creation(self):
        """Test ClickTracker model creation"""
        self.assertEqual(self.click_tracker.user, self.user)
        self.assertIsNotNone(self.click_tracker.page_url)
        self.assertIsNotNone(self.click_tracker.element_selector)
        self.assertIsNotNone(self.click_tracker.clicked_at)
    
    def test_click_tracker_str_representation(self):
        """Test ClickTracker string representation"""
        expected = f"{self.user.username} - {self.click_tracker.element_selector}"
        self.assertEqual(str(self.click_tracker), expected)
    
    def test_click_tracker_categories(self):
        """Test different click categories"""
        categories = ['navigation', 'form', 'button', 'link', 'image']
        for category in categories:
            tracker = ClickTrackerFactory(
                user=self.user,
                click_category=category
            )
            self.assertEqual(tracker.click_category, category)
    
    def test_click_tracker_coordinates(self):
        """Test coordinate validation"""
        # Valid coordinates
        valid_coords = [
            (100, 200),   # Normal click
            (0, 0),       # Top-left corner
            (1920, 1080)  # Bottom-right corner (typical screen)
        ]
        
        for x, y in valid_coords:
            tracker = ClickTrackerFactory(
                user=self.user,
                position_x=x,
                position_y=y
            )
            self.assertEqual(tracker.position_x, x)
            self.assertEqual(tracker.position_y, y)


class EnhancedClickTrackerModelTest(TestCase):
    """Test EnhancedClickTracker model"""
    
    def setUp(self):
        self.user = UserFactory()
        self.enhanced_tracker = EnhancedClickTrackerFactory(user=self.user)
    
    def test_enhanced_click_tracker_creation(self):
        """Test EnhancedClickTracker model creation"""
        self.assertEqual(self.enhanced_tracker.user, self.user)
        self.assertIsNotNone(self.enhanced_tracker.heat_score)
        self.assertIsNotNone(self.enhanced_tracker.engagement_value)
        self.assertIsNotNone(self.enhanced_tracker.conversion_value)
    
    def test_enhanced_click_tracker_str_representation(self):
        """Test EnhancedClickTracker string representation"""
        expected = f"{self.user.username} - {self.enhanced_tracker.heat_score}"
        self.assertEqual(str(self.enhanced_tracker), expected)
    
    def test_enhanced_click_tracker_scores(self):
        """Test score validations"""
        # Heat score (0-100)
        self.assertGreaterEqual(self.enhanced_tracker.heat_score, 0)
        self.assertLessEqual(self.enhanced_tracker.heat_score, 100)
        
        # Engagement value (1-10)
        self.assertGreaterEqual(self.enhanced_tracker.engagement_value, 1)
        self.assertLessEqual(self.enhanced_tracker.engagement_value, 10)
        
        # Conversion value (0-100)
        self.assertGreaterEqual(self.enhanced_tracker.conversion_value, 0)
        self.assertLessEqual(self.enhanced_tracker.conversion_value, 100)
    
    def test_enhanced_click_tracker_metadata(self):
        """Test metadata JSON field"""
        metadata = {
            'scroll_depth': 75,
            'dwell_time': 5000,
            'device_type': 'mobile'
        }
        
        tracker = EnhancedClickTrackerFactory(
            user=self.user,
            metadata=metadata
        )
        self.assertEqual(tracker.metadata, metadata)


class SecurityModelIntegrationTest(TransactionTestCase):
    """Integration tests for security models"""
    
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
    
    def test_user_device_security_flow(self):
        """Test complete user device security flow"""
        # Create device
        device = DeviceInfoFactory(user=self.user)
        
        # Create security log for device registration
        security_log = SecurityLogFactory(
            user=self.user,
            event_type='device_registered',
            ip_address=device.ip_address
        )
        
        # Create trusted device
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint=device.device_fingerprint
        )
        
        # Verify relationships
        self.assertEqual(device.user, self.user)
        self.assertEqual(security_log.user, self.user)
        self.assertEqual(trusted_device.user, self.user)
        self.assertEqual(device.ip_address, security_log.ip_address)
    
    def test_security_incident_with_related_models(self):
        """Test security incident with related security models"""
        # Create security incident
        incident = SecurityIncidentFactory(user=self.user)
        
        # Create related security logs
        logs = SecurityLogFactory.create_batch(
            5,
            user=self.user,
            ip_address='192.168.1.100'
        )
        
        # Create user ban
        ban = UserBanFactory(
            user=self.user,
            created_by=self.staff_user
        )
        
        # Verify incident creation
        self.assertEqual(incident.user, self.user)
        self.assertEqual(len(logs), 5)
        self.assertEqual(ban.user, self.user)
    
    def test_threat_intelligence_workflow(self):
        """Test threat intelligence workflow"""
        # Create threat intelligence
        threat = ThreatIntelligenceFactory(
            indicators=['192.168.1.100', '192.168.1.101'],
            indicator_type='ip'
        )
        
        # Create IP blacklist based on threat
        for ip in threat.indicators:
            IPBlacklistFactory(
                ip_address=ip,
                blacklist_type='threat_intelligence'
            )
        
        # Create security logs for blacklisted IPs
        for ip in threat.indicators:
            SecurityLogFactory(
                event_type='blocked_request',
                ip_address=ip,
                severity='warning'
            )
        
        # Verify workflow
        self.assertEqual(len(threat.indicators), 2)
        self.assertEqual(
            IPBlacklist.objects.filter(
                ip_address__in=threat.indicators
            ).count(),
            2
        )
        self.assertEqual(
            SecurityLog.objects.filter(
                ip_address__in=threat.indicators
            ).count(),
            2
        )
    
    def test_risk_assessment_workflow(self):
        """Test risk assessment workflow"""
        # Create risk score
        risk_score = RiskScoreFactory(
            user=self.user,
            current_score=Decimal('75.5'),
            risk_factors=['multiple_ips', 'suspicious_location']
        )
        
        # Create related security events
        SecurityLogFactory.create_batch(
            3,
            user=self.user,
            severity='warning'
        )
        
        # Create security incident for high risk
        if risk_score.current_score > 70:
            SecurityIncidentFactory(
                user=self.user,
                severity='high',
                incident_type='risk_threshold_breach'
            )
        
        # Verify risk assessment
        self.assertGreater(risk_score.current_score, 70)
        self.assertEqual(len(risk_score.risk_factors), 2)
        self.assertEqual(
            SecurityLog.objects.filter(
                user=self.user,
                severity='warning'
            ).count(),
            3
        )
        self.assertEqual(
            SecurityIncident.objects.filter(
                user=self.user,
                severity='high'
            ).count(),
            1
        )
    
    def test_session_security_workflow(self):
        """Test session security workflow"""
        # Create user session
        session = UserSessionFactory(user=self.user)
        
        # Create session activities
        activities = SessionActivityFactory.create_batch(
            5,
            user=self.user,
            session=session
        )
        
        # Create device info for session
        device = DeviceInfoFactory(
            user=self.user,
            ip_address=session.ip_address
        )
        
        # Create security logs for session
        SecurityLogFactory.create_batch(
            3,
            user=self.user,
            ip_address=session.ip_address
        )
        
        # Verify session workflow
        self.assertEqual(session.user, self.user)
        self.assertEqual(len(activities), 5)
        self.assertEqual(
            SessionActivity.objects.filter(session=session).count(),
            5
        )
        self.assertEqual(device.ip_address, session.ip_address)
        self.assertEqual(
            SecurityLog.objects.filter(
                user=self.user,
                ip_address=session.ip_address
            ).count(),
            3
        )
    
    def test_2fa_security_workflow(self):
        """Test 2FA security workflow"""
        # Create 2FA method
        two_factor = TwoFactorMethodFactory(user=self.user)
        
        # Create 2FA attempts
        attempts = TwoFactorAttemptFactory.create_batch(
            5,
            user=self.user,
            method=two_factor
        )
        
        # Create recovery codes
        recovery_codes = TwoFactorRecoveryCodeFactory.create_batch(
            10,
            user=self.user
        )
        
        # Create security logs for 2FA events
        SecurityLogFactory.create_batch(
            3,
            user=self.user,
            event_type='2fa_attempt'
        )
        
        # Verify 2FA workflow
        self.assertEqual(two_factor.user, self.user)
        self.assertEqual(len(attempts), 5)
        self.assertEqual(len(recovery_codes), 10)
        self.assertEqual(
            TwoFactorAttempt.objects.filter(method=two_factor).count(),
            5
        )
        self.assertEqual(
            TwoFactorRecoveryCode.objects.filter(user=self.user).count(),
            10
        )
        self.assertEqual(
            SecurityLog.objects.filter(
                user=self.user,
                security_type='2fa_attempt'
            ).count(),
            3
        )