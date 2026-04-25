"""
Test Geo Targeting

Tests for the geo targeting service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.targeting import GeoTargetingService
from ..models import GeoRouteRule, OfferRoute
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestGeoTargeting(TestCase):
    """Test cases for GeoTargetingService."""
    
    def setUp(self):
        """Set up test environment."""
        self.geo_service = GeoTargetingService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_matches_geo_rule_basic(self):
        """Test basic geo rule matching."""
        try:
            # Create test geo rule
            rule = GeoRouteRule.objects.create(
                name='Test Geo Rule',
                country='US',
                region='California',
                city='Los Angeles',
                is_active=True
            )
            
            # Create test context
            context = {
                'location': {
                    'country': 'US',
                    'region': 'California',
                    'city': 'Los Angeles',
                    'ip': '192.168.1.1'
                }
            }
            
            # Test matching
            result = self.geo_service.matches_geo_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], ['country', 'region', 'city'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_geo_rule_basic: {e}")
    
    def test_matches_geo_rule_partial_match(self):
        """Test geo rule partial matching."""
        try:
            # Create test geo rule
            rule = GeoRouteRule.objects.create(
                name='Test Geo Rule',
                country='US',
                region='California',
                is_active=True
            )
            
            # Create test context with partial match
            context = {
                'location': {
                    'country': 'US',
                    'region': 'California',
                    'city': 'San Francisco'  # Different city
                }
            }
            
            # Test matching
            result = self.geo_service.matches_geo_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['matched_fields'], ['country', 'region'])
            self.assertNotIn('city', result['matched_fields'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_geo_rule_partial_match: {e}")
    
    def test_matches_geo_rule_no_match(self):
        """Test geo rule no match."""
        try:
            # Create test geo rule
            rule = GeoRouteRule.objects.create(
                name='Test Geo Rule',
                country='US',
                region='California',
                is_active=True
            )
            
            # Create test context with no match
            context = {
                'location': {
                    'country': 'Canada',
                    'region': 'Ontario',
                    'city': 'Toronto'
                }
            }
            
            # Test matching
            result = self.geo_service.matches_geo_rule(rule, context)
            
            # Assertions
            self.assertFalse(result['matches'])
            self.assertEqual(result['matched_fields'], [])
            
        except Exception as e:
            self.fail(f"Error in test_matches_geo_rule_no_match: {e}")
    
    def test_get_user_location_basic(self):
        """Test basic user location detection."""
        try:
            # Create test context
            context = {
                'ip_address': '192.168.1.1',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.4 Mobile/15E148 Safari/604.1'
            }
            
            # Mock IP geolocation service
            with patch('..services.targeting.GeoTargetingService._get_ip_geolocation') as mock_geo:
                mock_geo.return_value = {
                    'country': 'US',
                    'region': 'California',
                    'city': 'Los Angeles',
                    'latitude': 34.0522,
                    'longitude': -118.2437
                }
                
                # Get user location
                location = self.geo_service.get_user_location(context)
                
                # Assertions
                self.assertIsInstance(location, dict)
                self.assertIn('country', location)
                self.assertIn('region', location)
                self.assertIn('city', location)
                self.assertEqual(location['country'], 'US')
                self.assertEqual(location['region'], 'California')
                self.assertEqual(location['city'], 'Los Angeles')
                
        except Exception as e:
            self.fail(f"Error in test_get_user_location_basic: {e}")
    
    def test_get_user_location_with_cache(self):
        """Test user location detection with caching."""
        try:
            # Create test context
            context = {
                'ip_address': '192.168.1.1'
            }
            
            # Mock cache service
            with patch('..services.cache.cache_service') as mock_cache:
                # First call - cache miss
                mock_cache.get.return_value = None
                
                with patch('..services.targeting.GeoTargetingService._get_ip_geolocation') as mock_geo:
                    mock_geo.return_value = {
                        'country': 'US',
                        'region': 'California'
                    }
                    
                    # First call
                    location1 = self.geo_service.get_user_location(context)
                    
                    # Second call - cache hit
                    mock_cache.get.return_value = {
                        'country': 'US',
                        'region': 'California'
                    }
                    
                    location2 = self.geo_service.get_user_location(context)
                    
                    # Assertions
                    self.assertEqual(location1, location2)
                    self.assertEqual(mock_cache.get.call_count, 2)
                    mock_cache.set.assert_called_once()
                    
        except Exception as e:
            self.fail(f"Error in test_get_user_location_with_cache: {e}")
    
    def test_validate_geo_rule_config(self):
        """Test geo rule configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'country': 'US',
                'region': 'California',
                'city': 'Los Angeles',
                'is_active': True
            }
            
            result = self.geo_service.validate_geo_rule_config(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
            # Test invalid configuration
            invalid_config = {
                'country': '',  # Missing country
                'region': 'California',
                'city': 'Los Angeles',
                'is_active': True
            }
            
            result = self.geo_service.validate_geo_rule_config(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('country', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_geo_rule_config: {e}")
    
    def test_get_geo_rules_for_location(self):
        """Test getting geo rules for a location."""
        try:
            # Create test geo rules
            rules = [
                GeoRouteRule.objects.create(
                    name='US Rule',
                    country='US',
                    is_active=True
                ),
                GeoRouteRule.objects.create(
                    name='California Rule',
                    country='US',
                    region='California',
                    is_active=True
                ),
                GeoRouteRule.objects.create(
                    name='Inactive Rule',
                    country='US',
                    is_active=False
                )
            ]
            
            # Create test location
            location = {
                'country': 'US',
                'region': 'California',
                'city': 'Los Angeles'
            }
            
            # Get matching rules
            matching_rules = self.geo_service.get_geo_rules_for_location(location)
            
            # Assertions
            self.assertEqual(len(matching_rules), 2)  # Should match US and California rules
            self.assertIn(rules[0].id, [rule.id for rule in matching_rules])
            self.assertIn(rules[1].id, [rule.id for rule in matching_rules])
            self.assertNotIn(rules[2].id, [rule.id for rule in matching_rules])  # Inactive rule
            
        except Exception as e:
            self.fail(f"Error in test_get_geo_rules_for_location: {e}")
    
    def test_is_ip_in_range(self):
        """Test IP range checking."""
        try:
            # Test valid IP in range
            ip_range = '192.168.1.0/24'
            test_ip = '192.168.1.100'
            
            result = self.geo_service.is_ip_in_range(test_ip, ip_range)
            
            # Assertions
            self.assertTrue(result)
            
            # Test invalid IP in range
            test_ip = '192.168.2.100'
            
            result = self.geo_service.is_ip_in_range(test_ip, ip_range)
            
            # Assertions
            self.assertFalse(result)
            
        except Exception as e:
            self.fail(f"Error in test_is_ip_in_range: {e}")
    
    def test_get_country_from_ip(self):
        """Test getting country from IP."""
        try:
            # Mock IP geolocation service
            with patch('..services.targeting.GeoTargetingService._get_ip_geolocation') as mock_geo:
                mock_geo.return_value = {
                    'country': 'US',
                    'region': 'California',
                    'city': 'Los Angeles'
                }
                
                # Get country from IP
                country = self.geo_service.get_country_from_ip('192.168.1.1')
                
                # Assertions
                self.assertEqual(country, 'US')
                mock_geo.assert_called_once_with('192.168.1.1')
                
        except Exception as e:
            self.fail(f"Error in test_get_country_from_ip: {e}")
    
    def test_health_check(self):
        """Test geo targeting service health check."""
        try:
            # Mock external services
            with patch('..services.targeting.GeoTargetingService._get_ip_geolocation') as mock_geo:
                mock_geo.return_value = {'country': 'US'}
                
                # Test health check
                health = self.geo_service.health_check()
                
                # Assertions
                self.assertIsInstance(health, dict)
                self.assertIn('status', health)
                self.assertIn('timestamp', health)
                self.assertIn('ip_geolocation_service', health)
                
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
