"""
Enhanced Trusted Device Tests
Comprehensive test suite for trusted device functionality
Author: System Security Team
Version: 2.0.0
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APITestCase

from ..services.TrustedDeviceService import TrustedDeviceService
from .factories import (
    UserFactory, StaffUserFactory, TrustedDeviceFactory,
    DeviceInfoFactory, SecurityLogFactory
)
from api.security.models import TrustedDevice
from datetime import timedelta


class TrustedDeviceServiceTest(TestCase):
    """Test TrustedDeviceService class"""
    
    def setUp(self):
        self.service = TrustedDeviceService()
        self.user = UserFactory()
        self.staff_user = StaffUserFactory()
        cache.clear()
    
    def test_trusted_device_service_initialization(self):
        """Test TrustedDeviceService initialization"""
        self.assertIsNotNone(self.service.cache_manager)
        self.assertIsNotNone(self.service.logger)
        self.assertIsNotNone(self.service.default_trust_score)
        self.assertIsNotNone(self.service.default_expiration_days)
    
    def test_trusted_device_service_default_config(self):
        """Test default configuration"""
        self.assertEqual(self.service.default_trust_score, 70)
        self.assertEqual(self.service.default_expiration_days, 30)
    
    def test_register_device_new_device(self):
        """Test registering a new trusted device"""
        device_data = {
            'device_fingerprint': 'test_fingerprint_123',
            'device_name': 'Test Device',
            'platform': 'Windows',
            'browser': 'Chrome',
            'ip_address': '192.168.1.100',
            'user_agent': 'TestAgent/1.0',
            'location': {'country': 'US', 'city': 'New York'}
        }
        
        with patch('api.security.models.TrustedDevice.objects.create') as mock_create:
            mock_device = MagicMock()
            mock_device.id = 'device-id'
            mock_create.return_value = mock_device
            
            result = self.service.register_device(
                self.user,
                **device_data
            )
            
            self.assertEqual(result, mock_device)
            mock_create.assert_called_once()
            
            # Check call arguments
            call_args = mock_create.call_args[1]
            self.assertEqual(call_args['user'], self.user)
            self.assertEqual(call_args['device_fingerprint'], 'test_fingerprint_123')
            self.assertEqual(call_args['device_name'], 'Test Device')
            self.assertTrue(call_args['is_trusted'])
            self.assertGreaterEqual(call_args['trust_score'], self.service.default_trust_score)
    
    def test_register_device_existing_device(self):
        """Test registering an existing device"""
        existing_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='existing_fingerprint'
        )
        
        device_data = {
            'device_fingerprint': 'existing_fingerprint',
            'device_name': 'Updated Device Name',
            'platform': 'Windows',
            'browser': 'Chrome'
        }
        
        with patch('api.security.models.TrustedDevice.objects.get_or_create') as mock_get_create:
            mock_device = MagicMock()
            mock_device.id = 'device-id'
            mock_get_create.return_value = (mock_device, False)  # Existing device
            
            result = self.service.register_device(
                self.user,
                **device_data
            )
            
            self.assertEqual(result, mock_device)
            mock_get_create.assert_called_once()
    
    def test_register_device_auto_trust_eligible(self):
        """Test auto-trust eligibility for new device"""
        device_data = {
            'device_fingerprint': 'new_fingerprint',
            'device_name': 'New Device',
            'platform': 'Windows',
            'browser': 'Chrome',
            'ip_address': '192.168.1.100'
        }
        
        with patch.object(self.service, '_check_auto_trust_eligibility') as mock_eligible:
            mock_eligible.return_value = True
            
            with patch('api.security.models.TrustedDevice.objects.create') as mock_create:
                mock_device = MagicMock()
                mock_device.id = 'device-id'
                mock_create.return_value = mock_device
                
                result = self.service.register_device(
                    self.user,
                    **device_data
                )
                
                self.assertEqual(result, mock_device)
                mock_eligible.assert_called_once_with(self.user, device_data)
    
    def test_register_device_auto_trust_not_eligible(self):
        """Test device not eligible for auto-trust"""
        device_data = {
            'device_fingerprint': 'new_fingerprint',
            'device_name': 'New Device',
            'platform': 'Windows',
            'browser': 'Chrome',
            'ip_address': '192.168.1.100'
        }
        
        with patch.object(self.service, '_check_auto_trust_eligibility') as mock_eligible:
            mock_eligible.return_value = False
            
            with patch('api.security.models.TrustedDevice.objects.create') as mock_create:
                mock_device = MagicMock()
                mock_device.id = 'device-id'
                mock_create.return_value = mock_device
                
                result = self.service.register_device(
                    self.user,
                    **device_data
                )
                
                self.assertEqual(result, mock_device)
                mock_eligible.assert_called_once_with(self.user, device_data)
    
    def test_check_auto_trust_eligible_good_history(self):
        """Test auto-trust eligibility with good user history"""
        device_data = {
            'device_fingerprint': 'new_fingerprint',
            'ip_address': '192.168.1.100'
        }
        
        with patch.object(self.service, '_get_user_trust_history') as mock_history:
            mock_history.return_value = {
                'account_age_days': 365,
                'successful_logins': 100,
                'failed_login_attempts': 2,
                'security_incidents': 0,
                'previous_trusted_devices': 3
            }
            
            result = self.service._check_auto_trust_eligibility(self.user, device_data)
            
            self.assertTrue(result)
    
    def test_check_auto_trust_eligible_poor_history(self):
        """Test auto-trust eligibility with poor user history"""
        device_data = {
            'device_fingerprint': 'new_fingerprint',
            'ip_address': '192.168.1.100'
        }
        
        with patch.object(self.service, '_get_user_trust_history') as mock_history:
            mock_history.return_value = {
                'account_age_days': 7,
                'successful_logins': 5,
                'failed_login_attempts': 20,
                'security_incidents': 3,
                'previous_trusted_devices': 0
            }
            
            result = self.service._check_auto_trust_eligibility(self.user, device_data)
            
            self.assertFalse(result)
    
    def test_get_user_trust_history(self):
        """Test getting user trust history"""
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_filter.return_value = mock_queryset
            
            with patch('api.security.models.TrustedDevice.objects.filter') as mock_device_filter:
                mock_device_queryset = MagicMock()
                mock_device_queryset.count.return_value = 3
                mock_device_filter.return_value = mock_device_queryset
                
                with patch('api.security.models.SecurityIncident.objects.filter') as mock_incident_filter:
                    mock_incident_queryset = MagicMock()
                    mock_incident_queryset.count.return_value = 1
                    mock_incident_filter.return_value = mock_incident_queryset
                    
                    result = self.service._get_user_trust_history(self.user)
                    
                    self.assertEqual(result['successful_logins'], 50)
                    self.assertEqual(result['previous_trusted_devices'], 3)
                    self.assertEqual(result['security_incidents'], 1)
                    self.assertIn('account_age_days', result)
    
    def test_verify_device_trust_trusted_device(self):
        """Test verifying trust for trusted device"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='trusted_fingerprint',
            is_trusted=True,
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )
        
        result = self.service.verify_device_trust(
            self.user,
            'trusted_fingerprint'
        )
        
        self.assertTrue(result['is_trusted'])
        self.assertEqual(result['device'], trusted_device)
        self.assertEqual(result['trust_score'], trusted_device.trust_score)
    
    def test_verify_device_trust_expired_device(self):
        """Test verifying trust for expired device"""
        expired_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='expired_fingerprint',
            is_trusted=True,
            expires_at=timezone.now() - timezone.timedelta(days=1)
        )
        
        result = self.service.verify_device_trust(
            self.user,
            'expired_fingerprint'
        )
        
        self.assertFalse(result['is_trusted'])
        self.assertEqual(result['reason'], 'expired')
    
    def test_verify_device_trust_not_trusted_device(self):
        """Test verifying trust for non-trusted device"""
        not_trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='not_trusted_fingerprint',
            is_trusted=False
        )
        
        result = self.service.verify_device_trust(
            self.user,
            'not_trusted_fingerprint'
        )
        
        self.assertFalse(result['is_trusted'])
        self.assertEqual(result['reason'], 'not_trusted')
    
    def test_verify_device_trust_no_device(self):
        """Test verifying trust for non-existent device"""
        result = self.service.verify_device_trust(
            self.user,
            'non_existent_fingerprint'
        )
        
        self.assertFalse(result['is_trusted'])
        self.assertEqual(result['reason'], 'not_found')
    
    def test_verify_device_trust_with_risk_assessment(self):
        """Test verifying trust with risk assessment"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='risky_fingerprint',
            is_trusted=True,
            trust_score=60  # Low trust score
        )
        
        with patch.object(self.service, '_assess_device_risk') as mock_risk:
            mock_risk.return_value = {
                'risk_score': 75,
                'risk_factors': ['new_location', 'suspicious_timing'],
                'recommendation': 'require_additional_verification'
            }
            
            result = self.service.verify_device_trust(
                self.user,
                'risky_fingerprint',
                assess_risk=True
            )
            
            self.assertTrue(result['is_trusted'])
            self.assertIn('risk_assessment', result)
            self.assertEqual(result['risk_assessment']['risk_score'], 75)
    
    def test_assess_device_risk_low_risk(self):
        """Test assessing device risk for low risk scenario"""
        device_data = {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'location': {'country': 'US', 'city': 'New York'}
        }
        
        with patch.object(self.service, '_check_ip_risk') as mock_ip_risk:
            mock_ip_risk.return_value = {'risk_score': 20, 'is_suspicious': False}
            
            with patch.object(self.service, '_check_user_agent_risk') as mock_ua_risk:
                mock_ua_risk.return_value = {'risk_score': 10, 'is_suspicious': False}
                
                with patch.object(self.service, '_check_location_risk') as mock_loc_risk:
                    mock_loc_risk.return_value = {'risk_score': 15, 'is_suspicious': False}
                    
                    result = self.service._assess_device_risk(device_data)
                    
                    self.assertLess(result['risk_score'], 50)
                    self.assertEqual(result['risk_level'], 'low')
                    self.assertIn('recommendation', result)
    
    def test_assess_device_risk_high_risk(self):
        """Test assessing device risk for high risk scenario"""
        device_data = {
            'ip_address': '192.168.1.100',
            'user_agent': 'SuspiciousBot/1.0',
            'location': {'country': 'CN', 'city': 'Beijing'}
        }
        
        with patch.object(self.service, '_check_ip_risk') as mock_ip_risk:
            mock_ip_risk.return_value = {'risk_score': 80, 'is_suspicious': True}
            
            with patch.object(self.service, '_check_user_agent_risk') as mock_ua_risk:
                mock_ua_risk.return_value = {'risk_score': 70, 'is_suspicious': True}
                
                with patch.object(self.service, '_check_location_risk') as mock_loc_risk:
                    mock_loc_risk.return_value = {'risk_score': 60, 'is_suspicious': True}
                    
                    result = self.service._assess_device_risk(device_data)
                    
                    self.assertGreater(result['risk_score'], 70)
                    self.assertEqual(result['risk_level'], 'high')
                    self.assertIn('recommendation', result)
    
    def test_check_ip_risk_safe_ip(self):
        """Test IP risk assessment for safe IP"""
        with patch.object(self.service, '_get_ip_reputation') as mock_reputation:
            mock_reputation.return_value = {
                'risk_score': 10,
                'is_blacklisted': False,
                'is_proxy': False,
                'is_vpn': False
            }
            
            result = self.service._check_ip_risk('192.168.1.100')
            
            self.assertEqual(result['risk_score'], 10)
            self.assertFalse(result['is_suspicious'])
    
    def test_check_ip_risk_suspicious_ip(self):
        """Test IP risk assessment for suspicious IP"""
        with patch.object(self.service, '_get_ip_reputation') as mock_reputation:
            mock_reputation.return_value = {
                'risk_score': 85,
                'is_blacklisted': True,
                'is_proxy': False,
                'is_vpn': True
            }
            
            result = self.service._check_ip_risk('192.168.1.100')
            
            self.assertEqual(result['risk_score'], 85)
            self.assertTrue(result['is_suspicious'])
    
    def test_check_user_agent_risk_safe_ua(self):
        """Test user agent risk assessment for safe UA"""
        safe_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        
        result = self.service._check_user_agent_risk(safe_ua)
        
        self.assertLess(result['risk_score'], 30)
        self.assertFalse(result['is_suspicious'])
    
    def test_check_user_agent_risk_suspicious_ua(self):
        """Test user agent risk assessment for suspicious UA"""
        suspicious_ua = 'Bot/1.0 (+http://suspicious-bot.com)'
        
        result = self.service._check_user_agent_risk(suspicious_ua)
        
        self.assertGreater(result['risk_score'], 50)
        self.assertTrue(result['is_suspicious'])
    
    def test_check_location_risk_safe_location(self):
        """Test location risk assessment for safe location"""
        location = {
            'country': 'US',
            'city': 'New York',
            'latitude': 40.7128,
            'longitude': -74.0060
        }
        
        with patch.object(self.service, '_get_user_location_history') as mock_history:
            mock_history.return_value = [
                {'country': 'US', 'city': 'New York', 'count': 10},
                {'country': 'US', 'city': 'Boston', 'count': 5}
            ]
            
            result = self.service._check_location_risk(location, self.user)
            
            self.assertLess(result['risk_score'], 30)
            self.assertFalse(result['is_suspicious'])
    
    def test_check_location_risk_suspicious_location(self):
        """Test location risk assessment for suspicious location"""
        location = {
            'country': 'CN',
            'city': 'Beijing',
            'latitude': 39.9042,
            'longitude': 116.4074
        }
        
        with patch.object(self.service, '_get_user_location_history') as mock_history:
            mock_history.return_value = [
                {'country': 'US', 'city': 'New York', 'count': 15},
                {'country': 'US', 'city': 'Los Angeles', 'count': 8}
            ]
            
            result = self.service._check_location_risk(location, self.user)
            
            self.assertGreater(result['risk_score'], 60)
            self.assertTrue(result['is_suspicious'])
    
    def test_get_user_location_history(self):
        """Test getting user location history"""
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {'country': 'US', 'city': 'New York', 'ip_address': '192.168.1.100'},
                {'country': 'US', 'city': 'Boston', 'ip_address': '192.168.1.101'},
                {'country': 'US', 'city': 'New York', 'ip_address': '192.168.1.100'}
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service._get_user_location_history(self.user)
            
            self.assertEqual(len(result), 2)  # Should group by location
            self.assertEqual(result[0]['country'], 'US')
            self.assertEqual(result[0]['city'], 'New York')
            self.assertEqual(result[0]['count'], 2)
    
    def test_update_device_trust_score(self):
        """Test updating device trust score"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=70
        )
        
        with patch.object(trusted_device, 'save') as mock_save:
            result = self.service.update_device_trust_score(
                trusted_device.id,
                85,
                reason='Consistent positive usage'
            )
            
            self.assertEqual(result['trust_score'], 85)
            self.assertIn('reason', result['metadata'])
            mock_save.assert_called_once()
    
    def test_update_device_trust_score_not_found(self):
        """Test updating trust score for non-existent device"""
        with patch('api.security.models.TrustedDevice.objects.get') as mock_get:
            mock_get.side_effect = TrustedDevice.DoesNotExist()
            
            result = self.service.update_device_trust_score(
                'non-existent-id',
                85
            )
            
            self.assertIsNone(result)
    
    def test_revoke_device_trust(self):
        """Test revoking device trust"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            is_trusted=True
        )
        
        with patch.object(trusted_device, 'save') as mock_save:
            result = self.service.revoke_device_trust(
                trusted_device.id,
                reason='Security concern detected'
            )
            
            self.assertFalse(result['is_trusted'])
            self.assertIn('reason', result['metadata'])
            mock_save.assert_called_once()
    
    def test_revoke_device_trust_not_found(self):
        """Test revoking trust for non-existent device"""
        with patch('api.security.models.TrustedDevice.objects.get') as mock_get:
            mock_get.side_effect = TrustedDevice.DoesNotExist()
            
            result = self.service.revoke_device_trust(
                'non-existent-id',
                reason='Test reason'
            )
            
            self.assertIsNone(result)
    
    def test_revoke_all_user_devices(self):
        """Test revoking all devices for a user"""
        trusted_devices = TrustedDeviceFactory.create_batch(
            3,
            user=self.user,
            is_trusted=True
        )
        
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.update.return_value = 3
            mock_filter.return_value = mock_queryset
            
            result = self.service.revoke_all_user_devices(
                self.user.id,
                reason='Security policy violation'
            )
            
            self.assertEqual(result['revoked_count'], 3)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_revoke_all_user_devices_not_found(self):
        """Test revoking all devices for non-existent user"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 0
            mock_filter.return_value = mock_queryset
            
            result = self.service.revoke_all_user_devices(
                'non-existent-user-id',
                reason='Test reason'
            )
            
            self.assertEqual(result['revoked_count'], 0)
    
    def test_extend_device_trust(self):
        """Test extending device trust"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            expires_at=timezone.now() + timezone.timedelta(days=10)
        )
        
        with patch.object(trusted_device, 'save') as mock_save:
            result = self.service.extend_device_trust(
                trusted_device.id,
                days=30
            )
            
            self.assertGreater(result['expires_at'], trusted_device.expires_at)
            mock_save.assert_called_once()
    
    def test_extend_device_trust_not_found(self):
        """Test extending trust for non-existent device"""
        with patch('api.security.models.TrustedDevice.objects.get') as mock_get:
            mock_get.side_effect = TrustedDevice.DoesNotExist()
            
            result = self.service.extend_device_trust(
                'non-existent-id',
                days=30
            )
            
            self.assertIsNone(result)
    
    def test_get_user_trusted_devices(self):
        """Test getting user's trusted devices"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.order_by.return_value = [
                TrustedDeviceFactory(user=self.user),
                TrustedDeviceFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_user_trusted_devices(self.user.id)
            
            self.assertEqual(result['count'], 3)
            self.assertEqual(len(result['devices']), 2)
            mock_filter.assert_called_once_with(user=self.user)
    
    def test_get_user_trusted_devices_active_only(self):
        """Test getting only active trusted devices"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.order_by.return_value = [
                TrustedDeviceFactory(user=self.user),
                TrustedDeviceFactory(user=self.user)
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_user_trusted_devices(
                self.user.id,
                active_only=True
            )
            
            self.assertEqual(result['count'], 2)
            mock_filter.assert_called_once_with(
                user=self.user,
                is_trusted=True,
                expires_at__gt=timezone.now()
            )
    
    def test_get_device_usage_statistics(self):
        """Test getting device usage statistics"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            usage_count=50
        )
        
        with patch.object(self.service, '_calculate_device_usage_stats') as mock_stats:
            mock_stats.return_value = {
                'total_usage': 50,
                'avg_daily_usage': 2.5,
                'peak_usage_hour': 14,
                'usage_trend': 'increasing',
                'last_used': timezone.now() - timedelta(hours=2)
            }
            
            result = self.service.get_device_usage_statistics(trusted_device.id)
            
            self.assertEqual(result['total_usage'], 50)
            self.assertEqual(result['avg_daily_usage'], 2.5)
            self.assertEqual(result['peak_usage_hour'], 14)
    
    def test_calculate_device_usage_stats(self):
        """Test calculating device usage statistics"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            usage_count=50,
            last_used_at=timezone.now() - timedelta(hours=2)
        )
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 50
            mock_queryset.extra.return_value = [
                {'hour': 14, 'count': 15},
                {'hour': 10, 'count': 10},
                {'hour': 16, 'count': 8}
            ]
            mock_filter.return_value = mock_queryset
            
            stats = self.service._calculate_device_usage_stats(trusted_device)
            
            self.assertEqual(stats['total_usage'], 50)
            self.assertIn('avg_daily_usage', stats)
            self.assertIn('peak_usage_hour', stats)
            self.assertIn('usage_trend', stats)
    
    def test_cleanup_expired_devices(self):
        """Test cleaning up expired devices"""
        # Create expired devices
        expired_devices = TrustedDeviceFactory.create_batch(
            3,
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.delete.return_value = (3, {'api.security.TrustedDevice': 3})
            mock_filter.return_value = mock_queryset
            
            result = self.service.cleanup_expired_devices()
            
            self.assertEqual(result['deleted_count'], 3)
            mock_filter.assert_called_once()
    
    def test_cleanup_expired_devices_with_notification(self):
        """Test cleaning up expired devices with user notification"""
        # Create expired devices
        expired_devices = TrustedDeviceFactory.create_batch(
            2,
            user=self.user,
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 2
            mock_queryset.delete.return_value = (2, {'api.security.TrustedDevice': 2})
            mock_filter.return_value = mock_queryset
            
            with patch.object(self.service, '_notify_device_cleanup') as mock_notify:
                mock_notify.return_value = True
                
                result = self.service.cleanup_expired_devices(notify_users=True)
                
                self.assertEqual(result['deleted_count'], 2)
                self.assertEqual(result['notification_sent'], 2)
    
    def test_notify_device_cleanup(self):
        """Test notifying user about device cleanup"""
        cleanup_data = {
            'user': self.user,
            'deleted_devices': [
                {'device_name': 'Device 1', 'device_fingerprint': 'fp1'},
                {'device_name': 'Device 2', 'device_fingerprint': 'fp2'}
            ]
        }
        
        with patch('django.core.mail.send_mail') as mock_send:
            mock_send.return_value = True
            
            result = self.service._notify_device_cleanup(cleanup_data)
            
            self.assertTrue(result)
            mock_send.assert_called_once()
    
    def test_get_device_trust_recommendations(self):
        """Test getting device trust recommendations"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60
        )
        
        with patch.object(self.service, '_generate_trust_recommendations') as mock_recommend:
            mock_recommend.return_value = [
                {
                    'type': 'increase_trust_score',
                    'description': 'Device has been used consistently',
                    'action': 'Increase trust score to 75',
                    'confidence': 0.8
                },
                {
                    'type': 'extend_expiration',
                    'description': 'Device is reliable',
                    'action': 'Extend trust period by 30 days',
                    'confidence': 0.9
                }
            ]
            
            result = self.service.get_device_trust_recommendations(trusted_device.id)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['type'], 'increase_trust_score')
    
    def test_generate_trust_recommendations(self):
        """Test generating trust recommendations"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60,
            usage_count=100,
            last_used_at=timezone.now() - timedelta(hours=1)
        )
        
        recommendations = self.service._generate_trust_recommendations(trusted_device)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Should have recommendations based on trust score and usage
        for rec in recommendations:
            self.assertIn('type', rec)
            self.assertIn('description', rec)
            self.assertIn('action', rec)
            self.assertIn('confidence', rec)
    
    def test_export_trusted_devices(self):
        """Test exporting trusted devices"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'device-1',
                    'device_fingerprint': 'fp1',
                    'device_name': 'Device 1',
                    'trust_score': 80,
                    'is_trusted': True,
                    'expires_at': timezone.now() + timedelta(days=30)
                },
                {
                    'id': 'device-2',
                    'device_fingerprint': 'fp2',
                    'device_name': 'Device 2',
                    'trust_score': 70,
                    'is_trusted': True,
                    'expires_at': timezone.now() + timedelta(days=15)
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_trusted_devices(
                user_id=self.user.id,
                format='json'
            )
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['device_name'], 'Device 1')
            self.assertEqual(result[1]['trust_score'], 70)
    
    def test_export_trusted_devices_csv(self):
        """Test exporting trusted devices in CSV format"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.values.return_value = [
                {
                    'id': 'device-1',
                    'device_fingerprint': 'fp1',
                    'device_name': 'Device 1',
                    'trust_score': 80,
                    'is_trusted': True
                }
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.export_trusted_devices(
                user_id=self.user.id,
                format='csv'
            )
            
            self.assertIn('device_fingerprint', result)
            self.assertIn('fp1', result)
    
    def test_import_trusted_devices(self):
        """Test importing trusted devices"""
        import_data = [
            {
                'device_fingerprint': 'import_fp1',
                'device_name': 'Imported Device 1',
                'platform': 'Windows',
                'browser': 'Chrome',
                'trust_score': 75,
                'expires_at': timezone.now() + timedelta(days=30)
            },
            {
                'device_fingerprint': 'import_fp2',
                'device_name': 'Imported Device 2',
                'platform': 'macOS',
                'browser': 'Safari',
                'trust_score': 85,
                'expires_at': timezone.now() + timedelta(days=45)
            }
        ]
        
        with patch.object(self.service, '_create_trusted_device_from_import') as mock_create:
            mock_create.return_value = MagicMock()
            
            result = self.service.import_trusted_devices(
                self.user.id,
                import_data
            )
            
            self.assertEqual(result['imported_count'], 2)
            self.assertEqual(result['failed_count'], 0)
            self.assertEqual(mock_create.call_count, 2)
    
    def test_import_trusted_devices_with_errors(self):
        """Test importing trusted devices with validation errors"""
        import_data = [
            {
                'device_fingerprint': '',  # Invalid - empty
                'device_name': 'Invalid Device',
                'trust_score': 150  # Invalid - too high
            },
            {
                'device_fingerprint': 'valid_fp2',
                'device_name': 'Valid Device',
                'trust_score': 75
            }
        ]
        
        with patch.object(self.service, '_create_trusted_device_from_import') as mock_create:
            mock_create.return_value = MagicMock()
            
            result = self.service.import_trusted_devices(
                self.user.id,
                import_data
            )
            
            self.assertEqual(result['imported_count'], 1)
            self.assertEqual(result['failed_count'], 1)
            self.assertIn('errors', result)
    
    def test_create_trusted_device_from_import(self):
        """Test creating trusted device from import data"""
        import_data = {
            'device_fingerprint': 'import_fp1',
            'device_name': 'Imported Device',
            'platform': 'Windows',
            'browser': 'Chrome',
            'trust_score': 75,
            'expires_at': timezone.now() + timedelta(days=30)
        }
        
        with patch('api.security.models.TrustedDevice.objects.create') as mock_create:
            mock_device = MagicMock()
            mock_device.id = 'imported-device-id'
            mock_create.return_value = mock_device
            
            result = self.service._create_trusted_device_from_import(
                self.user,
                import_data
            )
            
            self.assertEqual(result, mock_device)
            mock_create.assert_called_once()
    
    def test_validate_trusted_device_data(self):
        """Test validating trusted device data"""
        valid_data = {
            'device_fingerprint': 'valid_fingerprint',
            'device_name': 'Valid Device',
            'trust_score': 75,
            'platform': 'Windows',
            'browser': 'Chrome'
        }
        
        result = self.service._validate_trusted_device_data(valid_data)
        
        self.assertTrue(result['valid'])
        self.assertNotIn('errors', result)
    
    def test_validate_trusted_device_data_invalid(self):
        """Test validating invalid trusted device data"""
        invalid_data = {
            'device_fingerprint': '',  # Empty
            'device_name': '',  # Empty
            'trust_score': 150,  # Invalid range
            'platform': '',  # Empty
            'browser': ''  # Empty
        }
        
        result = self.service._validate_trusted_device_data(invalid_data)
        
        self.assertFalse(result['valid'])
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
    
    def test_get_device_trust_audit_log(self):
        """Test getting device trust audit log"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.DeviceTrustAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_device_trust_audit_log(trusted_device.id)
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['audit_entries']), 2)
    
    def test_create_device_trust_audit_log(self):
        """Test creating device trust audit log entry"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.DeviceTrustAuditLog.objects.create') as mock_create:
            mock_log = MagicMock()
            mock_log.id = 'audit-log-id'
            mock_create.return_value = mock_log
            
            result = self.service._create_device_trust_audit_log(
                trusted_device,
                'trust_score_updated',
                {'old_score': 70, 'new_score': 85},
                self.staff_user
            )
            
            self.assertEqual(result, mock_log)
            mock_create.assert_called_once()
    
    def test_get_device_trust_analytics(self):
        """Test getting device trust analytics"""
        with patch.object(self.service, '_calculate_trust_analytics') as mock_analytics:
            mock_analytics.return_value = {
                'total_devices': 100,
                'trusted_devices': 75,
                'avg_trust_score': 72.5,
                'trust_distribution': {
                    'low': 10,
                    'medium': 30,
                    'high': 35
                },
                'platform_distribution': {
                    'Windows': 40,
                    'macOS': 25,
                    'iOS': 20,
                    'Android': 15
                },
                'expiration_trends': [
                    {'month': '2023-01', 'expirations': 5},
                    {'month': '2023-02', 'expirations': 8}
                ]
            }
            
            result = self.service.get_device_trust_analytics(days=30)
            
            self.assertEqual(result['total_devices'], 100)
            self.assertEqual(result['trusted_devices'], 75)
            self.assertEqual(result['avg_trust_score'], 72.5)
            self.assertIn('trust_distribution', result)
            self.assertIn('platform_distribution', result)
    
    def test_calculate_trust_analytics(self):
        """Test calculating trust analytics"""
        # Create test devices
        trusted_devices = [
            TrustedDeviceFactory(
                user=self.user,
                trust_score=80,
                platform='Windows',
                is_trusted=True
            ),
            TrustedDeviceFactory(
                user=self.user,
                trust_score=60,
                platform='macOS',
                is_trusted=True
            ),
            TrustedDeviceFactory(
                user=self.user,
                trust_score=40,
                platform='iOS',
                is_trusted=False
            )
        ]
        
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 3
            mock_queryset.aggregate.return_value = {
                'avg_trust_score': 60.0,
                'max_trust_score': 80,
                'min_trust_score': 40
            }
            mock_filter.return_value = mock_queryset
            
            analytics = self.service._calculate_trust_analytics(trusted_devices)
            
            self.assertIn('total_devices', analytics)
            self.assertIn('trusted_devices', analytics)
            self.assertIn('avg_trust_score', analytics)
            self.assertIn('trust_distribution', analytics)
    
    def test_get_device_trust_trends(self):
        """Test getting device trust trends"""
        with patch.object(self.service, '_calculate_trust_trends') as mock_trends:
            mock_trends.return_value = [
                {
                    'date': '2023-01-01',
                    'total_devices': 100,
                    'trusted_devices': 75,
                    'avg_trust_score': 72.5
                },
                {
                    'date': '2023-01-02',
                    'total_devices': 105,
                    'trusted_devices': 80,
                    'avg_trust_score': 73.2
                }
            ]
            
            result = self.service.get_device_trust_trends(days=30)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['total_devices'], 100)
            self.assertEqual(result[1]['avg_trust_score'], 73.2)
    
    def test_calculate_trust_trends(self):
        """Test calculating trust trends"""
        # Create test devices with different creation dates
        devices = [
            TrustedDeviceFactory(
                user=self.user,
                created_at=timezone.now() - timedelta(days=5),
                trust_score=80
            ),
            TrustedDeviceFactory(
                user=self.user,
                created_at=timezone.now() - timedelta(days=3),
                trust_score=75
            )
        ]
        
        trends = self.service._calculate_trust_trends(devices)
        
        self.assertIsInstance(trends, list)
        self.assertGreater(len(trends), 0)
        
        for trend in trends:
            self.assertIn('date', trend)
            self.assertIn('total_devices', trend)
            self.assertIn('trusted_devices', trend)
            self.assertIn('avg_trust_score', trend)
    
    def test_get_device_security_events(self):
        """Test getting security events for device"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 10
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_device_security_events(
                trusted_device.id,
                days=7
            )
            
            self.assertEqual(result['count'], 10)
            self.assertEqual(len(result['events']), 2)
    
    def test_flag_suspicious_device(self):
        """Test flagging suspicious device"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='suspicious_fingerprint',
            is_trusted=True
        )
        
        with patch.object(trusted_device, 'save') as mock_save:
            with patch.object(self.service, '_create_device_trust_audit_log') as mock_audit:
                mock_audit.return_value = MagicMock()
                
                result = self.service.flag_suspicious_device(
                    trusted_device.id,
                    reason='Unusual login pattern detected',
                    severity='high'
                )
                
                self.assertFalse(result['is_trusted'])
                self.assertIn('suspicious_flag', result['metadata'])
                mock_save.assert_called_once()
                mock_audit.assert_called_once()
    
    def test_flag_suspicious_device_not_found(self):
        """Test flagging non-existent device"""
        with patch('api.security.models.TrustedDevice.objects.get') as mock_get:
            mock_get.side_effect = TrustedDevice.DoesNotExist()
            
            result = self.service.flag_suspicious_device(
                'non-existent-id',
                reason='Test reason'
            )
            
            self.assertIsNone(result)
    
    def test_unflag_suspicious_device(self):
        """Test unflagging suspicious device"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='suspicious_fingerprint',
            is_trusted=False,
            metadata={'suspicious_flag': True}
        )
        
        with patch.object(trusted_device, 'save') as mock_save:
            with patch.object(self.service, '_create_device_trust_audit_log') as mock_audit:
                mock_audit.return_value = MagicMock()
                
                result = self.service.unflag_suspicious_device(
                    trusted_device.id,
                    reason='Investigation completed, no threat found'
                )
                
                self.assertTrue(result['is_trusted'])
                self.assertNotIn('suspicious_flag', result['metadata'])
                mock_save.assert_called_once()
                mock_audit.assert_called_once()
    
    def test_get_suspicious_devices(self):
        """Test getting suspicious devices"""
        with patch('api.security.models.TrustedDevice.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_suspicious_devices()
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['devices']), 2)
    
    def test_get_device_compliance_status(self):
        """Test getting device compliance status"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=80
        )
        
        with patch.object(self.service, '_check_device_compliance') as mock_compliance:
            mock_compliance.return_value = {
                'is_compliant': True,
                'compliance_score': 85,
                'violations': [],
                'recommendations': []
            }
            
            result = self.service.get_device_compliance_status(trusted_device.id)
            
            self.assertTrue(result['is_compliant'])
            self.assertEqual(result['compliance_score'], 85)
    
    def test_check_device_compliance(self):
        """Test checking device compliance"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=80,
            platform='Windows',
            browser='Chrome'
        )
        
        compliance = self.service._check_device_compliance(trusted_device)
        
        self.assertIn('is_compliant', compliance)
        self.assertIn('compliance_score', compliance)
        self.assertIn('violations', compliance)
        self.assertIn('recommendations', compliance)
    
    def test_get_device_trust_score_history(self):
        """Test getting device trust score history"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.DeviceTrustAuditLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.order_by.return_value = [
                MagicMock(
                    action='trust_score_updated',
                    metadata={'old_score': 70, 'new_score': 75},
                    created_at=timezone.now() - timedelta(days=5)
                ),
                MagicMock(
                    action='trust_score_updated',
                    metadata={'old_score': 75, 'new_score': 80},
                    created_at=timezone.now() - timedelta(days=2)
                )
            ]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_device_trust_score_history(trusted_device.id)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['old_score'], 70)
            self.assertEqual(result[1]['new_score'], 80)
    
    def test_get_device_usage_patterns(self):
        """Test getting device usage patterns"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch.object(self.service, '_analyze_device_usage_patterns') as mock_patterns:
            mock_patterns.return_value = {
                'peak_hours': [9, 14, 16],
                'avg_session_duration': 45.5,
                'most_used_features': ['login', 'dashboard', 'reports'],
                'usage_frequency': 'daily',
                'consistency_score': 0.85
            }
            
            result = self.service.get_device_usage_patterns(trusted_device.id)
            
            self.assertEqual(result['peak_hours'], [9, 14, 16])
            self.assertEqual(result['avg_session_duration'], 45.5)
            self.assertIn('most_used_features', result)
    
    def test_analyze_device_usage_patterns(self):
        """Test analyzing device usage patterns"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.SecurityLog.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.extra.return_value = [
                {'hour': 9, 'count': 15},
                {'hour': 14, 'count': 20},
                {'hour': 16, 'count': 12}
            ]
            mock_filter.return_value = mock_queryset
            
            patterns = self.service._analyze_device_usage_patterns(trusted_device)
            
            self.assertIn('peak_hours', patterns)
            self.assertIn('avg_session_duration', patterns)
            self.assertIn('usage_frequency', patterns)
            self.assertIn('consistency_score', patterns)
    
    def test_get_device_risk_assessment_history(self):
        """Test getting device risk assessment history"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        with patch('api.security.models.DeviceRiskAssessment.objects.filter') as mock_filter:
            mock_queryset = MagicMock()
            mock_queryset.count.return_value = 5
            mock_queryset.order_by.return_value = [MagicMock(), MagicMock()]
            mock_filter.return_value = mock_queryset
            
            result = self.service.get_device_risk_assessment_history(trusted_device.id)
            
            self.assertEqual(result['count'], 5)
            self.assertEqual(len(result['assessments']), 2)
    
    def test_create_device_risk_assessment(self):
        """Test creating device risk assessment"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint'
        )
        
        risk_data = {
            'risk_score': 75,
            'risk_factors': ['new_location', 'suspicious_timing'],
            'assessment_details': {
                'ip_risk': 60,
                'user_agent_risk': 20,
                'location_risk': 40
            }
        }
        
        with patch('api.security.models.DeviceRiskAssessment.objects.create') as mock_create:
            mock_assessment = MagicMock()
            mock_assessment.id = 'assessment-id'
            mock_create.return_value = mock_assessment
            
            result = self.service.create_device_risk_assessment(
                trusted_device.id,
                risk_data
            )
            
            self.assertEqual(result, mock_assessment)
            mock_create.assert_called_once()
    
    def test_get_device_trust_recommendations_engine(self):
        """Test getting device trust recommendations from engine"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60,
            usage_count=100
        )
        
        with patch.object(self.service, '_run_trust_recommendation_engine') as mock_engine:
            mock_engine.return_value = [
                {
                    'type': 'increase_trust_score',
                    'priority': 'high',
                    'confidence': 0.85,
                    'reasoning': 'Consistent positive usage patterns',
                    'action': 'Increase trust score to 75',
                    'expected_impact': 'Reduced authentication friction'
                },
                {
                    'type': 'extend_expiration',
                    'priority': 'medium',
                    'confidence': 0.90,
                    'reasoning': 'Device reliability established',
                    'action': 'Extend trust period by 30 days',
                    'expected_impact': 'Improved user experience'
                }
            ]
            
            result = self.service.get_device_trust_recommendations_engine(trusted_device.id)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['type'], 'increase_trust_score')
            self.assertEqual(result[0]['priority'], 'high')
    
    def test_run_trust_recommendation_engine(self):
        """Test running trust recommendation engine"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60,
            usage_count=100,
            last_used_at=timezone.now() - timedelta(hours=1)
        )
        
        recommendations = self.service._run_trust_recommendation_engine(trusted_device)
        
        self.assertIsInstance(recommendations, list)
        
        for rec in recommendations:
            self.assertIn('type', rec)
            self.assertIn('priority', rec)
            self.assertIn('confidence', rec)
            self.assertIn('reasoning', rec)
            self.assertIn('action', rec)
            self.assertIn('expected_impact', rec)
    
    def test_get_device_trust_prediction(self):
        """Test getting device trust prediction"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=70
        )
        
        with patch.object(self.service, '_predict_device_trust') as mock_predict:
            mock_predict.return_value = {
                'predicted_trust_score': 78,
                'confidence': 0.82,
                'prediction_horizon': '30 days',
                'factors': [
                    {'factor': 'usage_consistency', 'weight': 0.3, 'impact': 5},
                    {'factor': 'security_incidents', 'weight': -0.2, 'impact': -2}
                ],
                'recommendations': ['Continue monitoring', 'Consider trust score increase']
            }
            
            result = self.service.get_device_trust_prediction(trusted_device.id)
            
            self.assertEqual(result['predicted_trust_score'], 78)
            self.assertEqual(result['confidence'], 0.82)
            self.assertIn('factors', result)
            self.assertIn('recommendations', result)
    
    def test_predict_device_trust(self):
        """Test predicting device trust"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=70,
            usage_count=100
        )
        
        prediction = self.service._predict_device_trust(trusted_device)
        
        self.assertIn('predicted_trust_score', prediction)
        self.assertIn('confidence', prediction)
        self.assertIn('prediction_horizon', prediction)
        self.assertIn('factors', prediction)
        self.assertIn('recommendations', prediction)
    
    def test_get_device_trust_benchmarking(self):
        """Test getting device trust benchmarking"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=70
        )
        
        with patch.object(self.service, '_benchmark_device_trust') as mock_benchmark:
            mock_benchmark.return_value = {
                'percentile_rank': 75,
                'industry_average': 65,
                'top_quartile_threshold': 80,
                'comparison': 'above_average',
                'recommendations': ['Device performs well compared to peers']
            }
            
            result = self.service.get_device_trust_benchmarking(trusted_device.id)
            
            self.assertEqual(result['percentile_rank'], 75)
            self.assertEqual(result['industry_average'], 65)
            self.assertEqual(result['comparison'], 'above_average')
    
    def test_benchmark_device_trust(self):
        """Test benchmarking device trust"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=70
        )
        
        with patch('api.security.models.TrustedDevice.objects.aggregate') as mock_aggregate:
            mock_aggregate.return_value = {
                'avg_trust_score': 65.0,
                'median_trust_score': 68.0,
                'p75_trust_score': 75.0,
                'p90_trust_score': 82.0
            }
            
            benchmark = self.service._benchmark_device_trust(trusted_device)
            
            self.assertIn('percentile_rank', benchmark)
            self.assertIn('industry_average', benchmark)
            self.assertIn('comparison', benchmark)
            self.assertIn('recommendations', benchmark)
    
    def test_get_device_trust_optimization_suggestions(self):
        """Test getting device trust optimization suggestions"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60
        )
        
        with patch.object(self.service, '_generate_trust_optimization_suggestions') as mock_suggestions:
            mock_suggestions.return_value = [
                {
                    'area': 'trust_score',
                    'current_value': 60,
                    'target_value': 75,
                    'improvement_actions': ['Increase usage consistency', 'Maintain security hygiene'],
                    'expected_impact': 'Reduced authentication steps',
                    'implementation_difficulty': 'low'
                },
                {
                    'area': 'usage_patterns',
                    'current_value': 'inconsistent',
                    'target_value': 'consistent',
                    'improvement_actions': ['Regular usage schedule', 'Feature diversity'],
                    'expected_impact': 'Higher trust score',
                    'implementation_difficulty': 'medium'
                }
            ]
            
            result = self.service.get_device_trust_optimization_suggestions(trusted_device.id)
            
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['area'], 'trust_score')
            self.assertEqual(result[0]['target_value'], 75)
    
    def test_generate_trust_optimization_suggestions(self):
        """Test generating trust optimization suggestions"""
        trusted_device = TrustedDeviceFactory(
            user=self.user,
            device_fingerprint='test_fingerprint',
            trust_score=60,
            usage_count=50
        )
        
        suggestions = self.service._generate_trust_optimization_suggestions(trusted_device)
        
        self.assertIsInstance(suggestions, list)
        
        for suggestion in suggestions:
            self.assertIn('area', suggestion)
            self.assertIn('current_value', suggestion)
            self.assertIn('target_value', suggestion)
            self.assertIn('improvement_actions', suggestion)
            self.assertIn('expected_impact', suggestion)
            self.assertIn('implementation_difficulty', suggestion)