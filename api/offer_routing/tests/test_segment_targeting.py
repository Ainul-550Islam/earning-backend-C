"""
Test Segment Targeting

Tests for the segment targeting service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.targeting import SegmentTargetingService
from ..models import UserSegmentRule, UserSegment
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestSegmentTargeting(TestCase):
    """Test cases for SegmentTargetingService."""
    
    def setUp(self):
        """Set up test environment."""
        self.segment_service = SegmentTargetingService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_matches_segment_rule_basic(self):
        """Test basic segment rule matching."""
        try:
            # Create test segment rule
            rule = UserSegmentRule.objects.create(
                name='Test Segment Rule',
                segment_type='demographic',
                conditions={
                    'age_range': [18, 65],
                    'gender': 'all',
                    'location': ['US', 'CA']
                },
                is_active=True
            )
            
            # Create test user profile
            user_profile = {
                'age': 25,
                'gender': 'male',
                'location': 'US',
                'registration_date': timezone.now() - timezone.timedelta(days=365)
            }
            
            # Test matching
            result = self.segment_service.matches_segment_rule(rule, user_profile)
            
            # Assertions
            self.assertTrue(result['matches'])
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_conditions'], ['age_range', 'location'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_segment_rule_basic: {e}")
    
    def test_matches_segment_rule_behavioral(self):
        """Test behavioral segment rule matching."""
        try:
            # Create test segment rule
            rule = UserSegmentRule.objects.create(
                name='Behavioral Segment Rule',
                segment_type='behavioral',
                conditions={
                    'purchase_frequency': 'high',
                    'last_purchase_days': 30,
                    'total_purchases': 5
                },
                is_active=True
            )
            
            # Create test user profile
            user_profile = {
                'purchase_history': [
                    {'date': timezone.now() - timezone.timedelta(days=10), 'amount': 50},
                    {'date': timezone.now() - timezone.timedelta(days=20), 'amount': 75},
                    {'date': timezone.now() - timezone.timedelta(days=30), 'amount': 100}
                ],
                'total_purchases': 3,
                'last_purchase_days': 10
            }
            
            # Test matching
            result = self.segment_service.matches_segment_rule(rule, user_profile)
            
            # Assertions
            self.assertFalse(result['matches'])  # Total purchases < 5
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_conditions'], ['last_purchase_days'])
            
        except Exception as e:
            self.fail(f"Error in test_matches_segment_rule_behavioral: {e}")
    
    def test_matches_segment_rule_transactional(self):
        """Test transactional segment rule matching."""
        try:
            # Create test segment rule
            rule = UserSegmentRule.objects.create(
                name='Transactional Segment Rule',
                segment_type='transactional',
                conditions={
                    'total_spend': 1000,
                    'avg_order_value': 50,
                    'purchase_categories': ['electronics', 'fashion']
                },
                is_active=True
            )
            
            # Create test user profile
            user_profile = {
                'total_spend': 1200,
                'avg_order_value': 60,
                'purchase_categories': ['electronics', 'home']
            }
            
            # Test matching
            result = self.segment_service.matches_segment_rule(rule, user_profile)
            
            # Assertions
            self.assertTrue(result['matches'])  # Total spend > 1000
            self.assertEqual(result['rule_id'], rule.id)
            self.assertEqual(result['matched_conditions'], ['total_spend'])
            self.assertNotIn('purchase_categories', result['matched_conditions'])  # Partial match
            
        except Exception as e:
            self.fail(f"Error in test_matches_segment_rule_transactional: {e}")
    
    def test_get_user_segments_basic(self):
        """Test getting basic user segments."""
        try:
            # Create test segment rules
            rules = [
                UserSegmentRule.objects.create(
                    name='Young Adults',
                    segment_type='demographic',
                    conditions={'age_range': [18, 35]},
                    is_active=True
                ),
                UserSegmentRule.objects.create(
                    name='High Spenders',
                    segment_type='transactional',
                    conditions={'total_spend': 1000},
                    is_active=True
                )
            ]
            
            # Create test user profile
            user_profile = {
                'age': 25,
                'total_spend': 1500,
                'purchase_history': []
            }
            
            # Get user segments
            result = self.segment_service.get_user_segments(user_profile)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['segments']), 2)
            segment_names = [seg['name'] for seg in result['segments']]
            self.assertIn('Young Adults', segment_names)
            self.assertIn('High Spenders', segment_names)
            
        except Exception as e:
            self.fail(f"Error in test_get_user_segments_basic: {e}")
    
    def test_get_user_segments_with_priority(self):
        """Test getting user segments with priority handling."""
        try:
            # Create test segment rules with different priorities
            rules = [
                UserSegmentRule.objects.create(
                    name='Low Priority Segment',
                    segment_type='demographic',
                    conditions={'age_range': [18, 65]},
                    priority=3,
                    is_active=True
                ),
                UserSegmentRule.objects.create(
                    name='High Priority Segment',
                    segment_type='behavioral',
                    conditions={'purchase_frequency': 'high'},
                    priority=1,
                    is_active=True
                )
            ]
            
            # Create test user profile
            user_profile = {
                'age': 25,
                'purchase_frequency': 'high',
                'purchase_history': []
            }
            
            # Get user segments
            result = self.segment_service.get_user_segments(user_profile)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['segments']), 2)
            # High priority segment should come first
            segments = result['segments']
            self.assertEqual(segments[0]['name'], 'High Priority Segment')
            self.assertEqual(segments[1]['name'], 'Low Priority Segment')
            
        except Exception as e:
            self.fail(f"Error in test_get_user_segments_with_priority: {e}")
    
    def test_create_user_segment_basic(self):
        """Test creating basic user segment."""
        try:
            # Create segment data
            segment_data = {
                'name': 'Test Segment',
                'description': 'Test segment for unit testing',
                'segment_type': 'custom',
                'conditions': {
                    'custom_field': 'test_value'
                },
                'priority': 1,
                'is_active': True
            }
            
            # Create segment
            result = self.segment_service.create_user_segment(segment_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['segment']['name'], 'Test Segment')
            self.assertEqual(result['segment']['segment_type'], 'custom')
            self.assertEqual(result['segment']['priority'], 1)
            self.assertTrue(result['segment']['is_active'])
            
        except Exception as e:
            self.fail(f"Error in test_create_user_segment_basic: {e}")
    
    def test_create_user_segment_validation(self):
        """Test user segment creation validation."""
        try:
            # Test invalid segment data
            invalid_data = {
                'name': '',  # Missing name
                'segment_type': 'invalid_type',  # Invalid type
                'conditions': {},  # Empty conditions
                'priority': 0,  # Invalid priority
                'is_active': True
            }
            
            # Create segment
            result = self.segment_service.create_user_segment(invalid_data)
            
            # Assertions
            self.assertFalse(result['success'])
            self.assertIn('name', result['errors'])
            self.assertIn('segment_type', result['errors'])
            self.assertIn('conditions', result['errors'])
            self.assertIn('priority', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_create_user_segment_validation: {e}")
    
    def test_update_user_segment_basic(self):
        """Test updating basic user segment."""
        try:
            # Create initial segment
            segment = UserSegment.objects.create(
                name='Original Segment',
                segment_type='demographic',
                conditions={'age_range': [18, 65]},
                priority=1,
                is_active=True
            )
            
            # Update segment
            update_data = {
                'name': 'Updated Segment',
                'description': 'Updated segment description',
                'conditions': {'age_range': [21, 60]},
                'priority': 2
            }
            
            result = self.segment_service.update_user_segment(segment.id, update_data)
            
            # Assertions
            self.assertTrue(result['success'])
            updated_segment = result['segment']
            self.assertEqual(updated_segment['name'], 'Updated Segment')
            self.assertEqual(updated_segment['description'], 'Updated segment description')
            self.assertEqual(updated_segment['conditions']['age_range'], [21, 60])
            self.assertEqual(updated_segment['priority'], 2)
            
        except Exception as e:
            self.fail(f"Error in test_update_user_segment_basic: {e}")
    
    def test_delete_user_segment_basic(self):
        """Test deleting basic user segment."""
        try:
            # Create segment
            segment = UserSegment.objects.create(
                name='Test Segment',
                segment_type='demographic',
                conditions={'age_range': [18, 65]},
                is_active=True
            )
            
            # Delete segment
            result = self.segment_service.delete_user_segment(segment.id)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['segment_id'], segment.id)
            
            # Verify segment is deleted
            with self.assertRaises(UserSegment.DoesNotExist):
                UserSegment.objects.get(id=segment.id)
            
        except Exception as e:
            self.fail(f"Error in test_delete_user_segment_basic: {e}")
    
    def test_get_segment_statistics_basic(self):
        """Test getting basic segment statistics."""
        try:
            # Create test segments
            segments = [
                UserSegment.objects.create(
                    name='Segment 1',
                    segment_type='demographic',
                    conditions={'age_range': [18, 35]},
                    is_active=True
                ),
                UserSegment.objects.create(
                    name='Segment 2',
                    segment_type='behavioral',
                    conditions={'purchase_frequency': 'high'},
                    is_active=True
                )
            ]
            
            # Get segment statistics
            result = self.segment_service.get_segment_statistics()
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['total_segments'], 2)
            self.assertEqual(result['active_segments'], 2)
            self.assertEqual(result['segment_types']['demographic'], 1)
            self.assertEqual(result['segment_types']['behavioral'], 1)
            
        except Exception as e:
            self.fail(f"Error in test_get_segment_statistics_basic: {e}")
    
    def test_validate_segment_config_basic(self):
        """Test basic segment configuration validation."""
        try:
            # Test valid configuration
            valid_config = {
                'name': 'Test Segment',
                'segment_type': 'demographic',
                'conditions': {'age_range': [18, 65]},
                'priority': 1,
                'is_active': True
            }
            
            result = self.segment_service.validate_segment_config(valid_config)
            
            # Assertions
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
            
        except Exception as e:
            self.fail(f"Error in test_validate_segment_config_basic: {e}")
    
    def test_validate_segment_config_invalid(self):
        """Test invalid segment configuration validation."""
        try:
            # Test invalid configuration
            invalid_config = {
                'name': '',  # Missing name
                'segment_type': 'invalid_type',  # Invalid type
                'conditions': {},  # Empty conditions
                'priority': 0,  # Invalid priority
                'is_active': True
            }
            
            result = self.segment_service.validate_segment_config(invalid_config)
            
            # Assertions
            self.assertFalse(result['valid'])
            self.assertIn('name', result['errors'])
            self.assertIn('segment_type', result['errors'])
            self.assertIn('conditions', result['errors'])
            self.assertIn('priority', result['errors'])
            
        except Exception as e:
            self.fail(f"Error in test_validate_segment_config_invalid: {e}")
    
    def test_health_check(self):
        """Test segment targeting service health check."""
        try:
            # Test health check
            health = self.segment_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('supported_segment_types', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")


if __name__ == '__main__':
    pytest.main()
