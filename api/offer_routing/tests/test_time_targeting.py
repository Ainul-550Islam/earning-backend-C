"""
Test Time Targeting

Tests for the time targeting service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.targeting import TimeTargetingService
from ..models import TimeRouteRule, OfferRoute
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestTimeTargeting(TestCase):
    """Test cases for TimeTargetingService."""
    
    def setUp(self):
        """Set up test environment."""
        self.time_service = TimeTargetingService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_matches_time_rule_basic(self):
        """Test basic time rule matching."""
        try:
            # Create test time rule
            rule = TimeRouteRule.objects.create(
                name='Test Time Rule',
                start_time='09:00',
                end_time='17:00',
                days_of_week=[1, 2, 3, 4, 5],  # Monday to Friday
                timezone='UTC',
                is_active=True
            )
            
            # Create test context - Monday 10:00 UTC
            context = {
                'timestamp': timezone.make_aware(timezone.datetime(2023, 1, 2, 10, 0, 0, 0, 0))
            }
            
            # Test matching
            result = self.time_service.matches_time_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], ['day_of_week', 'time_range'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_time_rule_basic: {e}")
    
    def test_matches_time_rule_outside_hours(self):
        """Test time rule matching outside hours."""
        try:
            # Create test time rule
            rule = TimeRouteRule.objects.create(
                name='Test Time Rule',
                start_time='09:00',
                end_time='17:00',
                days_of_week=[1, 2, 3, 4, 5],
                timezone='UTC',
                is_active=True
            )
            
            # Create test context - Saturday 20:00 UTC
            context = {
                'timestamp': timezone.make_aware(timezone.datetime(2023, 1, 7, 20, 0, 0, 0, 0))
            }
            
            # Test matching
            result = self.time_service.matches_time_rule(rule, context)
            
            # Assertions
            self.assertFalse(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], [])
            
        except Exception as e:
            self.fail(f"Error in test_matches_time_rule_outside_hours: {e}")
    
    def test_matches_time_rule_wrong_day(self):
        """Test time rule matching wrong day."""
        try:
            # Create test time rule
            rule = TimeRouteRule.objects.create(
                name='Test Time Rule',
                start_time='09:00',
                end_time='17:00',
                days_of_week=[1, 2, 3, 4, 5],  # Monday to Friday
                timezone='UTC',
                is_active=True
            )
            
            # Create test context - Sunday 10:00 UTC
            context = {
                'timestamp': timezone.make_aware(timezone.datetime(2023, 1, 1, 10, 0, 0, 0, 0))
            }
            
            # Test matching
            result = self.time_service.matches_time_rule(rule, context)
            
            # Assertions
            self.assertFalse(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], [])
            
        except Exception as e:
            self.fail(f"Error in test_matches_time_rule_wrong_day: {e}")
    
    def test_matches_time_rule_timezone_conversion(self):
        """Test time rule matching with timezone conversion."""
        try:
            # Create test time rule
            rule = TimeRouteRule.objects.create(
                name='Test Time Rule',
                start_time='09:00',
                end_time='17:00',
                days_of_week=[1, 2, 3, 4, 5],
                timezone='America/New_York',
                is_active=True
            )
            
            # Create test context - 14:00 UTC (09:00 EST)
            context = {
                'timestamp': timezone.make_aware(timezone.datetime(2023, 1, 2, 14, 0, 0, 0, 0))
            }
            
            # Test matching
            result = self.time_service.matches_time_rule(rule, context)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_fields'], ['day_of_week', 'time_range'])
            self.assertEqual(result['timezone_converted'], True)
            
        except Exception as e:
            self.fail(f"Error in test_matches_time_rule_timezone_conversion: {e}")
    
    def test_is_time_in_range_basic(self):
        """Test basic time range checking."""
        try:
            # Test time within range
            current_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 14, 0, 0, 0, 0))
            start_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 9, 0, 0, 0, 0))
            end_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 17, 0, 0, 0, 0))
            
            result = self.time_service.is_time_in_range(current_time, start_time, end_time)
            
            # Assertions
            self.assertTrue(result['in_range'])
            self.assertEqual(result['start_time'], start_time)
            self.assertEqual(result['end_time'], end_time)
            
        except Exception as e:
            self.fail(f"Error in test_is_time_in_range_basic: {e}")
    
    def test_is_time_in_range_boundary(self):
        """Test time range boundary checking."""
        try:
            # Test exact start time
            current_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 9, 0, 0, 0, 0))
            start_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 9, 0, 0, 0, 0))
            end_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 17, 0, 0, 0, 0))
            
            result = self.time_service.is_time_in_range(current_time, start_time, end_time)
            
            # Assertions
            self.assertTrue(result['in_range'])
            
            # Test exact end time
            current_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 17, 0, 0, 0, 0))
            result = self.time_service.is_time_in_range(current_time, start_time, end_time)
            
            # Assertions
            self.assertFalse(result['in_range'])  # At exact end time, typically not in range
            
        except Exception as e:
            self.fail(f"Error in test_is_time_in_range_boundary: {e}")
    
    def test_is_time_in_range_outside(self):
        """Test time range checking outside range."""
        try:
            # Test time before range
            current_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 8, 0, 0, 0, 0))
            start_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 9, 0, 0, 0, 0))
            end_time = timezone.make_aware(timezone.datetime(2023, 1, 2, 17, 0, 0, 0, 0))
            
            result = self.time_service.is_time_in_range(current_time, start_time, end_time)
            
            # Assertions
            self.assertFalse(result['in_range'])
            
        except Exception as e:
            self.fail(f"Error in test_is_time_in_range_outside: {e}")
    
    def test_is_day_of_week_match(self):
        """Test day of week matching."""
        try:
            # Test matching day
            current_day = 2  # Tuesday
            rule_days = [1, 2, 3, 4, 5]  # Monday to Friday
            
            result = self.time_service.is_day_of_week_match(current_day, rule_days)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['current_day'], current_day)
            self.assertEqual(result['rule_days'], rule_days)
            
        except Exception as e:
            self.fail(f"Error in test_is_day_of_week_match: {e}")
    
    def test_is_day_of_week_no_match(self):
        """Test day of week no match."""
        try:
            # Test non-matching day
            current_day = 6  # Saturday
            rule_days = [1, 2, 3, 4, 5]  # Monday to Friday
            
            result = self.time_service.is_day_of_week_match(current_day, rule_days)
            
            # Assertions
            self.assertFalse(result['matches'])
            self.assertEqual(result['current_day'], current_day)
            self.assertEqual(result['rule_days'], rule_days)
            
        except Exception as e:
            self.fail(f"Error in test_is_day_of_week_no_match: {e}")
    
    def test_parse_time_string_basic(self):
        """Test basic time string parsing."""
        try:
            # Test valid time strings
            valid_times = ['09:00', '17:30', '23:59', '00:00']
            
            for time_str in valid_times:
                result = self.time_service.parse_time_string(time_str)
                
                # Assertions
                self.assertTrue(result['valid'])
                self.assertIn('hour', result)
                self.assertIn('minute', result)
                self.assertGreaterEqual(result['hour'], 0)
                self.assertLessEqual(result['hour'], 23)
                self.assertGreaterEqual(result['minute'], 0)
                self.assertLessEqual(result['minute'], 59)
            
        except Exception as e:
            self.fail(f"Error in test_parse_time_string_basic: {e}")
    
    def test_parse_time_string_invalid(self):
        """Test invalid time string parsing."""
        try:
            # Test invalid time strings
            invalid_times = ['25:00', '09:60', 'invalid', '09:00:00']
            
            for time_str in invalid_times:
                result = self.time_service.parse_time_string(time_str)
                
                # Assertions
                self.assertFalse(result['valid'])
                self.assertIn('error', result)
            
        except Exception as e:
            self.fail(f"Error in test_parse_time_string_invalid: {e}")
    
    def test_get_time_rules_for_context_basic(self):
        """Test getting time rules for context."""
        try:
            # Create test time rules
            rules = [
                TimeRouteRule.objects.create(
                    name='Weekday Rule',
                    start_time='09:00',
                    end_time='17:00',
                    days_of_week=[1, 2, 3, 4, 5],
                    timezone='UTC',
                    is_active=True
                ),
                TimeRouteRule.objects.create(
                    name='Weekend Rule',
                    start_time='10:00',
                    end_time='22:00',
                    days_of_week=[6, 0],  # Saturday, Sunday
                    timezone='UTC',
                    is_active=True
                ),
                TimeRouteRule.objects.create(
                    name='Inactive Rule',
                    start_time='09:00',
                    end_time='17:00',
                    days_of_week=[1, 2, 3, 4, 5],
                    timezone='UTC',
                    is_active=False
                )
            ]
            
            # Create test context - Tuesday 14:00 UTC
            context = {
                'timestamp': timezone.make_aware(timezone.datetime(2023, 1, 3, 14, 0, 0, 0, 0))
            }
            
            # Get matching rules
            matching_rules = self.time_service.get_time_rules_for_context(context)
            
            # Assertions
            self.assertEqual(len(matching_rules), 1)  # Only weekday rule matches
            self.assertEqual(matching_rules[0].id, rules[0].id)
            
        except Exception as e:
            self.fail(f"Error in test_get_time_rules_for_context_basic: {e}")
    
    def test_validate_time_rule_config_basic(self):
        """Test basic time rule configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'name': 'Test Time Rule',
                'start_time': '09:00',
                'end_time': '17:00',
                'days_of_week': [1, 2, 3, 4, 5],
                'timezone': 'UTC',
                'is_active': True
            }
            
            result = self.time_service.validate_time_rule_config(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
        except Exception as e:
            self.fail(f"Error in test_validate_time_rule_config_basic: {e}")
    
    def test_validate_time_rule_config_invalid(self):
        """Test invalid time rule configuration validation."""
        try:
            # Test invalid configuration
            invalid_config = {
                'name': '',  # Missing name
                'start_time': '25:00',  # Invalid hour
                'end_time': '09:00',  # End before start
                'days_of_week': [8],  # Invalid day
                'timezone': 'Invalid/Timezone',
                'is_active': True
            }
            
            result = self.time_service.validate_time_rule_config(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('name', result['errors'])
            self.assertIn('start_time', result['errors'])
            self.assertIn('end_time', result['errors'])
            self.assertIn('days_of_week', result['errors'])
            self.assertIn('timezone', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_time_rule_config_invalid: {e}")
    
    def test_get_supported_timezones(self):
        """Test getting supported timezones."""
        try:
            timezones = self.time_service.get_supported_timezones()
            
            # Check for common timezones
            common_timezones = ['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo']
            
            for tz in common_timezones:
                self.assertIn(tz, timezones)
            
        except Exception as e:
            self.fail(f"Error in test_get_supported_timezones: {e}")
    
    def test_health_check(self):
        """Test time targeting service health check."""
        try:
            # Test health check
            health = self.time_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('supported_timezones', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
