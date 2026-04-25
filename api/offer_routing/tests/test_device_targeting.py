"""
Test Device Targeting

Tests for the device targeting service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.targeting import DeviceTargetingService
from ..models import DeviceRouteRule, OfferRoute
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestDeviceTargeting(TestCase):
    """Test cases for DeviceTargetingService."""
    
    def setUp(self):
        """Set up test environment."""
        self.device_service = DeviceTargetingService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_matches_device_rule_basic(self):
        """Test basic device rule matching."""
        try:
            # Create test device rule
            rule = DeviceRouteRule.objects.create(
                name='Test Device Rule',
                device_type='mobile',
                os='iOS',
                is_active=True
            )
            
            # Create test context
            context = {
                'device': {
                    'type': 'mobile',
                    'os': 'iOS',
                    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
                }
            }
            
            # Test matching
            result = self.device_service.matches_device_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], ['device_type', 'os'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_device_rule_basic: {e}")
    
    def test_matches_device_rule_partial_match(self):
        """Test device rule partial matching."""
        try:
            # Create test device rule
            rule = DeviceRouteRule.objects.create(
                name='Test Device Rule',
                device_type='mobile',
                os='iOS',
                is_active=True
            )
            
            # Create test context with partial match
            context = {
                'device': {
                    'type': 'mobile',
                    'os': 'Android',  # Different OS
                    'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
                }
            }
            
            # Test matching
            result = self.device_service.matches_device_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['matched_fields'], ['device_type'])
            self.assertNotIn('os', result['matched_fields'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_device_rule_partial_match: {e}")
    
    def test_matches_device_rule_no_match(self):
        """Test device rule no match."""
        try:
            # Create test device rule
            rule = DeviceRouteRule.objects.create(
                name='Test Device Rule',
                device_type='mobile',
                os='iOS',
                is_active=True
            )
            
            # Create test context with no match
            context = {
                'device': {
                    'type': 'desktop',
                    'os': 'Windows',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            
            # Test matching
            result = self.device_service.matches_device_rule(rule, context)
            
            # Assertions
            self.assertFalse(result['matches'])
            self.assertEqual(result['matched_fields'], [])
            
        except Exception as e:
            self.fail(f"Error in test_matches_device_rule_no_match: {e}")
    
    def test_parse_device_from_user_agent(self):
        """Test device parsing from user agent."""
        try:
            # Test mobile device parsing
            user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            
            device = self.device_service.parse_device_from_user_agent(user_agent)
            
            # Assertions
            self.assertEqual(device['type'], 'mobile')
            self.assertEqual(device['os'], 'iOS')
            self.assertEqual(device['browser'], 'Safari')
            self.assertIn('version', device)
            
            # Test desktop device parsing
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            device = self.device_service.parse_device_from_user_agent(user_agent)
            
            # Assertions
            self.assertEqual(device['type'], 'desktop')
            self.assertEqual(device['os'], 'Windows')
            self.assertEqual(device['browser'], 'Chrome')
            
        except Exception as e:
            self.fail(f"Error in test_parse_device_from_user_agent: {e}")
    
    def test_is_mobile_device(self):
        """Test mobile device detection."""
        try:
            # Test mobile user agent
            mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            
            is_mobile = self.device_service.is_mobile_device(mobile_ua)
            self.assertTrue(is_mobile)
            
            # Test desktop user agent
            desktop_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            is_mobile = self.device_service.is_mobile_device(desktop_ua)
            self.assertFalse(is_mobile)
            
        except Exception as e:
            self.fail(f"Error in test_is_mobile_device: {e}")
    
    def test_is_tablet_device(self):
        """Test tablet device detection."""
        try:
            # Test tablet user agent
            tablet_ua = 'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
            
            is_tablet = self.device_service.is_tablet_device(tablet_ua)
            self.assertTrue(is_tablet)
            
            # Test mobile user agent (not tablet)
            mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            
            is_tablet = self.device_service.is_tablet_device(mobile_ua)
            self.assertFalse(is_tablet)
            
        except Exception as e:
            self.fail(f"Error in test_is_tablet_device: {e}")
    
    def test_get_device_rules_for_device(self):
        """Test getting device rules for a device."""
        try:
            # Create test device rules
            rules = [
                DeviceRouteRule.objects.create(
                    name='Mobile Rule',
                    device_type='mobile',
                    is_active=True
                ),
                DeviceRouteRule.objects.create(
                    name='iOS Rule',
                    device_type='mobile',
                    os='iOS',
                    is_active=True
                ),
                DeviceRouteRule.objects.create(
                    name='Desktop Rule',
                    device_type='desktop',
                    is_active=True
                ),
                DeviceRouteRule.objects.create(
                    name='Inactive Rule',
                    device_type='mobile',
                    is_active=False
                )
            ]
            
            # Create test device context
            device = {
                'type': 'mobile',
                'os': 'iOS',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            }
            
            # Get matching rules
            matching_rules = self.device_service.get_device_rules_for_device(device)
            
            # Assertions
            self.assertEqual(len(matching_rules), 2)  # Should match mobile and iOS rules
            self.assertIn(rules[0].id, [rule.id for rule in matching_rules])
            self.assertIn(rules[1].id, [rule.id for rule in matching_rules])
            self.assertNotIn(rules[2].id, [rule.id for rule in matching_rules])  # Desktop rule
            self.assertNotIn(rules[3].id, [rule.id for rule in matching_rules])  # Inactive rule
            
        except Exception as e:
            self.fail(f"Error in test_get_device_rules_for_device: {e}")
    
    def test_validate_device_rule_config(self):
        """Test device rule configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'device_type': 'mobile',
                'os': 'iOS',
                'is_active': True
            }
            
            result = self.device_service.validate_device_rule_config(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
            # Test invalid configuration
            invalid_config = {
                'device_type': '',  # Missing device type
                'os': 'iOS',
                'is_active': True
            }
            
            result = self.device_service.validate_device_rule_config(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('device_type', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_device_rule_config: {e}")
    
    def test_get_supported_device_types(self):
        """Test getting supported device types."""
        try:
            device_types = self.device_service.get_supported_device_types()
            
            # Check for required device types
            required_types = ['mobile', 'desktop', 'tablet', 'smart_tv', 'wearable']
            
            for device_type in required_types:
                self.assertIn(device_type, device_types)
            
        except Exception as e:
            self.fail(f"Error in test_get_supported_device_types: {e}")
    
    def test_get_supported_operating_systems(self):
        """Test getting supported operating systems."""
        try:
            operating_systems = self.device_service.get_supported_operating_systems()
            
            # Check for required operating systems
            required_os = ['iOS', 'Android', 'Windows', 'macOS', 'Linux', 'ChromeOS']
            
            for os in required_os:
                self.assertIn(os, operating_systems)
            
        except Exception as e:
            self.fail(f"Error in test_get_supported_operating_systems: {e}")
    
    def test_health_check(self):
        """Test device targeting service health check."""
        try:
            # Test health check
            health = self.device_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('supported_device_types', health)
            self.assertIn('supported_operating_systems', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
