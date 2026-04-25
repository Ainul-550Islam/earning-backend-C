"""
Test A/B Test

Tests for the A/B test service
to ensure it works correctly.
"""

import logging
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
from ..services.ab_test import ABTestService
from ..models import RoutingABTest, ABTestAssignment, ABTestResult
from ..constants import DEFAULT_ROUTING_LIMIT

logger = logging.getLogger(__name__)

User = get_user_model()


class TestABTest(TestCase):
    """Test cases for ABTestService."""
    
    def setUp(self):
        """Set up test environment."""
        self.ab_test_service = ABTestService()
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            is_active=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        User.objects.filter(id=self.test_user.id).delete()
    
    def test_create_ab_test_basic(self):
        """Test basic A/B test creation."""
        try:
            # Test data
            test_data = {
                'name': 'Test A/B Test',
                'description': 'Test A/B test description',
                'variant_a': {
                    'name': 'Control Variant',
                    'config': {'offer_id': 1, 'weight': 50}
                },
                'variant_b': {
                    'name': 'Test Variant',
                    'config': {'offer_id': 2, 'weight': 50}
                },
                'primary_metric': 'conversion_rate',
                'confidence_level': 0.95,
                'min_sample_size': 100,
                'start_date': timezone.now().isoformat(),
                'end_date': (timezone.now() + timezone.timedelta(days=7)).isoformat()
            }
            
            # Create A/B test
            result = self.ab_test_service.create_ab_test(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['test']['name'], 'Test A/B Test')
            self.assertEqual(result['test']['variant_a']['name'], 'Control Variant')
            self.assertEqual(result['test']['variant_b']['name'], 'Test Variant')
            self.assertEqual(result['test']['primary_metric'], 'conversion_rate')
            self.assertEqual(result['test']['confidence_level'], 0.95)
            self.assertEqual(result['test']['min_sample_size'], 100)
            
        except Exception as e:
            self.fail(f"Error in test_create_ab_test_basic: {e}")
    
    def test_assign_user_to_test_basic(self):
        """Test basic user assignment to A/B test."""
        try:
            # Create test A/B test
            test = RoutingABTest.objects.create(
                name='Test Assignment',
                is_active=True,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            # Mock random assignment
            with patch('random.random') as mock_random:
                mock_random.return_value = 0.3  # 30% chance for variant A
                
                # Assign user to test
                result = self.ab_test_service.assign_user_to_test(
                    test_id=test.id,
                    user_id=self.test_user.id
                )
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(result['test_id'], test.id)
                self.assertEqual(result['user_id'], self.test_user.id)
                self.assertEqual(result['variant'], 'variant_a')
                self.assertEqual(result['assignment_date'], timezone.now().date())
                mock_random.assert_called_once()
                
        except Exception as e:
            self.fail(f"Error in test_assign_user_to_test_basic: {e}")
    
    def test_get_test_results_basic(self):
        """Test basic test results retrieval."""
        try:
            # Create test A/B test
            test = RoutingABTest.objects.create(
                name='Test Results',
                is_active=True,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            # Create test assignments
            assignments = []
            for i in range(100):
                variant = 'variant_a' if i < 50 else 'variant_b'
                assignments.append(ABTestAssignment.objects.create(
                    test=test,
                    user_id=self.test_user.id,
                    variant=variant,
                    assigned_at=timezone.now() - timezone.timedelta(hours=i)
                ))
            
            # Create test results
            for assignment in assignments[:50]:  # First 50 assignments
                ABTestResult.objects.create(
                    test=test,
                    user_id=assignment.user_id,
                    variant=assignment.variant,
                    metric_value=1.0 if assignment.variant == 'variant_a' else 0.8,
                    created_at=timezone.now() - timezone.timedelta(hours=1)
                )
            
            # Get test results
            result = self.ab_test_service.get_test_results(test.id)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['test_id'], test.id)
            self.assertEqual(result['total_assignments'], 100)
            self.assertEqual(result['total_conversions'], 50)  # 50% conversion rate
            self.assertEqual(result['variant_a_conversions'], 25)
            self.assertEqual(result['variant_b_conversions'], 25)
            self.assertEqual(result['conversion_rate'], 0.5)
            
        except Exception as e:
            self.fail(f"Error in test_get_test_results_basic: {e}")
    
    def test_calculate_statistical_significance_basic(self):
        """Test basic statistical significance calculation."""
        try:
            # Test data
            test_data = {
                'variant_a_conversions': 25,
                'variant_b_conversions': 35,
                'variant_a_total': 100,
                'variant_b_total': 100,
                'confidence_level': 0.95
            }
            
            # Calculate statistical significance
            result = self.ab_test_service.calculate_statistical_significance(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['variant_a_rate'], 0.25)
            self.assertEqual(result['variant_b_rate'], 0.35)
            self.assertEqual(result['lift'], 0.4)  # 40% lift
            self.assertEqual(result['p_value'], 0.02)  # Significant at 95% confidence
            self.assertTrue(result['is_significant'])
            self.assertEqual(result['confidence_level'], 0.95)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_statistical_significance_basic: {e}")
    
    def test_calculate_statistical_significance_no_significance(self):
        """Test statistical significance calculation with no significance."""
        try:
            # Test data
            test_data = {
                'variant_a_conversions': 25,
                'variant_b_conversions': 30,
                'variant_a_total': 100,
                'variant_b_total': 100,
                'confidence_level': 0.95
            }
            
            # Calculate statistical significance
            result = self.ab_test_service.calculate_statistical_significance(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['variant_a_rate'], 0.25)
            self.assertEqual(result['variant_b_rate'], 0.30)
            self.assertEqual(result['lift'], 0.2)  # 20% lift
            self.assertGreater(result['p_value'], 0.05)  # Not significant
            self.assertFalse(result['is_significant'])
            self.assertEqual(result['confidence_level'], 0.95)
            
        except Exception as e:
            self.fail(f"Error in test_calculate_statistical_significance_no_significance: {e}")
    
    def test_determine_winner_basic(self):
        """Test basic winner determination."""
        try:
            # Test data
            test_data = {
                'variant_a_rate': 0.25,
                'variant_b_rate': 0.35,
                'variant_a_conversions': 25,
                'variant_b_conversions': 35,
                'is_significant': True,
                'lift': 0.4,
                'p_value': 0.02
            }
            
            # Determine winner
            result = self.ab_test_service.determine_winner(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['winner'], 'variant_b')  # Higher conversion rate
            self.assertEqual(result['confidence'], 0.98)
            self.assertEqual(result['lift'], 0.4)
            self.assertEqual(result['p_value'], 0.02)
            self.assertTrue(result['is_significant'])
            
        except Exception as e:
            self.fail(f"Error in test_determine_winner_basic: {e}")
    
    def test_determine_winner_no_winner(self):
        """Test winner determination with no clear winner."""
        try:
            # Test data
            test_data = {
                'variant_a_rate': 0.25,
                'variant_b_rate': 0.24,  # Very close
                'variant_a_conversions': 25,
                'variant_b_conversions': 24,
                'is_significant': False,
                'lift': 0.04,
                'p_value': 0.15
            }
            
            # Determine winner
            result = self.ab_test_service.determine_winner(test_data)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['winner'], 'variant_a')  # Slightly higher
            self.assertEqual(result['confidence'], 0.6)  # Low confidence
            self.assertEqual(result['lift'], 0.04)
            self.assertEqual(result['p_value'], 0.15)
            self.assertFalse(result['is_significant'])
            
        except Exception as e:
            self.fail(f"Error in test_determine_winner_no_winner: {e}")
    
    def test_complete_ab_test_basic(self):
        """Test basic A/B test completion."""
        try:
            # Create test A/B test
            test = RoutingABTest.objects.create(
                name='Test Completion',
                is_active=True,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            # Mock statistical analysis
            with patch.object(self.ab_test_service, 'calculate_statistical_significance') as mock_stats:
                mock_stats.return_value = {
                    'success': True,
                    'is_significant': True,
                    'winner': 'variant_b',
                    'confidence': 0.98
                }
                
                # Complete test
                result = self.ab_test_service.complete_ab_test(test.id)
                
                # Assertions
                self.assertTrue(result['success'])
                self.assertEqual(result['test_id'], test.id)
                self.assertEqual(result['winner'], 'variant_b')
                self.assertEqual(result['confidence'], 0.98)
                self.assertTrue(result['is_significant'])
                
                # Verify test is marked as completed
                updated_test = RoutingABTest.objects.get(id=test.id)
                self.assertFalse(updated_test.is_active)
                self.assertEqual(updated_test.status, 'completed')
                
        except Exception as e:
            self.fail(f"Error in test_complete_ab_test_basic: {e}")
    
    def test_get_active_tests_basic(self):
        """Test getting active A/B tests."""
        try:
            # Create test A/B tests
            active_test = RoutingABTest.objects.create(
                name='Active Test',
                is_active=True,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            inactive_test = RoutingABTest.objects.create(
                name='Inactive Test',
                is_active=False,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            # Get active tests
            result = self.ab_test_service.get_active_tests()
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(len(result['tests']), 1)
            self.assertEqual(result['tests'][0]['id'], active_test.id)
            self.assertEqual(result['tests'][0]['name'], 'Active Test')
            self.assertTrue(result['tests'][0]['is_active'])
            
        except Exception as e:
            self.fail(f"Error in test_get_active_tests_basic: {e}")
    
    def test_get_test_statistics_basic(self):
        """Test getting test statistics."""
        try:
            # Create test A/B test
            test = RoutingABTest.objects.create(
                name='Statistics Test',
                is_active=True,
                variant_a_config={'offer_id': 1},
                variant_b_config={'offer_id': 2},
                primary_metric='conversion_rate'
            )
            
            # Create test assignments and results
            for i in range(50):
                variant = 'variant_a' if i < 25 else 'variant_b'
                ABTestAssignment.objects.create(
                    test=test,
                    user_id=self.test_user.id,
                    variant=variant,
                    assigned_at=timezone.now() - timezone.timedelta(hours=i)
                )
                
                # Create results for first 25 assignments
                if i < 25:
                    ABTestResult.objects.create(
                        test=test,
                        user_id=self.test_user.id,
                        variant=variant,
                        metric_value=1.0 if variant == 'variant_a' else 0.8,
                        created_at=timezone.now() - timezone.timedelta(hours=i+1)
                    )
            
            # Get test statistics
            result = self.ab_test_service.get_test_statistics(test.id)
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertEqual(result['test_id'], test.id)
            self.assertEqual(result['total_assignments'], 50)
            self.assertEqual(result['total_results'], 25)
            self.assertEqual(result['variant_a_assignments'], 25)
            self.assertEqual(result['variant_b_assignments'], 25)
            self.assertEqual(result['variant_a_results'], 25)
            self.assertEqual(result['variant_b_results'], 0)  # Only first 25 have results
            self.assertEqual(result['variant_a_rate'], 1.0)  # 100% for variant_a
            self.assertEqual(result['variant_b_rate'], 0.0)  # 0% for variant_b
            
        except Exception as e:
            self.fail(f"Error in test_get_test_statistics_basic: {e}")
    
    def test_health_check(self):
        """Test A/B test service health check."""
        try:
            # Test health check
            health = self.ab_test_service.health_check()
            
            # Assertions
            self.assertIsInstance(health, dict)
            self.assertIn('status', health)
            self.assertIn('timestamp', health)
            self.assertIn('active_tests', health)
            self.assertIn('cache_status', health)
            self.assertIn('performance_stats', health)
            
        except Exception as e:
            self.fail(f"Error in test_health_check: {e}")
    
    def test_performance_under_load(self):
        """Test A/B test service performance under load."""
        try:
            # Create many test assignments
            assignments = []
            for i in range(100):
                assignments.append(ABTestAssignment.objects.create(
                    test=RoutingABTest.objects.create(
                        name=f'Performance Test {i+1}',
                        is_active=True,
                        variant_a_config={'offer_id': 1},
                        variant_b_config={'offer_id': 2},
                        primary_metric='conversion_rate'
                    ),
                    user_id=self.test_user.id,
                    variant='variant_a' if i % 2 == 0 else 'variant_b',
                    assigned_at=timezone.now() - timezone.timedelta(hours=i)
                ))
            
            # Measure performance
            start_time = timezone.now()
            result = self.ab_test_service.get_test_statistics(assignments[0].test.id)
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Assertions
            self.assertTrue(result['success'])
            self.assertLess(elapsed_ms, 1000)  # Should complete in under 1 second
            
        except Exception as e:
            self.fail(f"Error in test_performance_under_load: {e}")


if __name__ == '__main__':
    pytest.main()
