"""
A/B Test Tests for Offer Routing System

This module contains unit tests for A/B testing functionality,
including test creation, assignment, evaluation, and analytics.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.ab_test import ABTestService, ab_test_service
from ..models import RoutingABTest, ABTestAssignment, ABTestResult
from ..exceptions import ABTestError, ValidationError

User = get_user_model()


class ABTestServiceTestCase(TestCase):
    """Test cases for ABTestService."""
    
    def setUp(self):
        """Set up test data."""
        self.ab_test_service = ABTestService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer routes
        from ..models import OfferRoute
        self.control_route = OfferRoute.objects.create(
            name='Control Route',
            description='Control route for A/B testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        self.variant_route = OfferRoute.objects.create(
            name='Variant Route',
            description='Variant route for A/B testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_create_test(self):
        """Test creating an A/B test."""
        test_data = {
            'name': 'Test A/B Test',
            'description': 'Test A/B test for unit testing',
            'control_route_id': self.control_route.id,
            'variant_route_id': self.variant_route.id,
            'split_percentage': 50,
            'min_sample_size': 100,
            'duration_hours': 168,  # 7 days
        }
        
        test = self.ab_test_service.create_test(
            tenant_id=self.tenant.id,
            test_data=test_data
        )
        
        self.assertIsInstance(test, RoutingABTest)
        self.assertEqual(test.name, test_data['name'])
        self.assertEqual(test.control_route, self.control_route)
        self.assertEqual(test.variant_route, self.variant_route)
    
    def test_start_test(self):
        """Test starting an A/B test."""
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            created_by=self.tenant
        )
        
        success = self.ab_test_service.start_test(test.id)
        
        self.assertTrue(success)
        
        # Check if test was started
        test.refresh_from_db()
        self.assertIsNotNone(test.started_at)
        self.assertTrue(test.is_active)
    
    def test_stop_test(self):
        """Test stopping an A/B test."""
        # Create and start test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            is_active=True,
            started_at=timezone.now() - timezone.timedelta(hours=1),
            created_by=self.tenant
        )
        
        success = self.ab_test_service.stop_test(test.id)
        
        self.assertTrue(success)
        
        # Check if test was stopped
        test.refresh_from_db()
        self.assertIsNotNone(test.ended_at)
        self.assertFalse(test.is_active)
    
    def test_assign_user_to_test(self):
        """Test assigning user to A/B test."""
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        # Create test offer
        from ..models import OfferRoute
        test_offer = OfferRoute.objects.create(
            name='Test Offer',
            description='Test offer for A/B testing',
            tenant=self.tenant,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        assignment = self.ab_test_service.assign_user_to_test(self.user, test_offer)
        
        self.assertIsInstance(assignment, ABTestAssignment)
        self.assertEqual(assignment.user, self.user)
        self.assertEqual(assignment.test, test)
        self.assertIn(assignment.variant, ['control', 'variant'])
    
    def test_record_assignment_event(self):
        """Test recording assignment event."""
        # Create assignment
        assignment = ABTestAssignment.objects.create(
            user=self.user,
            test=self.ab_test_service.get_active_test_for_offer(self.control_route.id),
            variant='control'
        )
        
        success = self.ab_test_service.record_assignment_event(
            self.user, self.control_route, 'impression', 0.0
        )
        
        self.assertTrue(success)
        
        # Check if event was recorded
        assignment.refresh_from_db()
        self.assertEqual(assignment.impressions, 1)
    
    def test_evaluate_active_tests(self):
        """Test evaluating active A/B tests."""
        # Create test with enough data
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=10,
            duration_hours=168,
            is_active=True,
            started_at=timezone.now() - timezone.timedelta(hours=2),
            created_by=self.tenant
        )
        
        # Create assignments with data
        for i in range(15):
            variant = 'control' if i < 8 else 'variant'
            ABTestAssignment.objects.create(
                user=self.user,
                test=test,
                variant=variant,
                impressions=10,
                clicks=2 if variant == 'control' else 3,
                conversions=1 if variant == 'control' else 2,
                revenue=10.0 if variant == 'control' else 15.0
            )
        
        evaluated_count = self.ab_test_service.evaluate_active_tests()
        
        self.assertIsInstance(evaluated_count, int)
        self.assertGreaterEqual(evaluated_count, 0)
    
    def test_get_test_results(self):
        """Test getting A/B test results."""
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            created_by=self.tenant
        )
        
        # Create result
        ABTestResult.objects.create(
            test=test,
            control_impressions=100,
            control_clicks=20,
            control_conversions=5,
            control_revenue=50.0,
            control_cr=5.0,
            variant_impressions=100,
            variant_clicks=25,
            variant_conversions=8,
            variant_revenue=80.0,
            variant_cr=8.0,
            cr_difference=3.0,
            z_score=2.1,
            p_value=0.036,
            is_significant=True,
            confidence_level=95.0,
            effect_size=0.3,
            winner='variant',
            winner_confidence=0.8,
            analyzed_at=timezone.now()
        )
        
        results = self.ab_test_service.get_test_results(test.id)
        
        self.assertIsInstance(results, dict)
        self.assertIn('control_impressions', results)
        self.assertIn('variant_impressions', results)
        self.assertIn('winner', results)
    
    def test_declare_winner(self):
        """Test declaring test winner."""
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        # Create result with winner
        ABTestResult.objects.create(
            test=test,
            control_impressions=100,
            control_clicks=20,
            control_conversions=5,
            control_revenue=50.0,
            control_cr=5.0,
            variant_impressions=100,
            variant_clicks=25,
            variant_conversions=8,
            variant_revenue=80.0,
            variant_cr=8.0,
            cr_difference=3.0,
            z_score=2.1,
            p_value=0.036,
            is_significant=True,
            confidence_level=95.0,
            effect_size=0.3,
            winner='variant',
            winner_confidence=0.8,
            analyzed_at=timezone.now()
        )
        
        success = self.ab_test_service.declare_winner(test.id, 'variant', 0.8)
        
        self.assertTrue(success)
        
        # Check if winner was declared
        test.refresh_from_db()
        self.assertEqual(test.winner, 'variant')
        self.assertEqual(test.confidence, 0.8)
    
    def test_get_active_test_for_offer(self):
        """Test getting active test for offer."""
        # Create active test
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name='Test A/B Test',
            description='Test A/B test',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=168,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.tenant
        )
        
        active_test = self.ab_test_service.get_active_test_for_offer(self.control_route.id)
        
        self.assertEqual(active_test, test)
    
    def test_get_test_analytics(self):
        """Test getting A/B test analytics."""
        # Create tests
        for i in range(3):
            RoutingABTest.objects.create(
                tenant=self.tenant,
                name=f'Test A/B Test {i}',
                description=f'Test A/B test {i}',
                control_route=self.control_route,
                variant_route=self.variant_route,
                split_percentage=50,
                min_sample_size=100,
                duration_hours=168,
                created_by=self.tenant
            )
        
        analytics = self.ab_test_service.get_test_analytics(
            user_id=self.tenant.id,
            days=30
        )
        
        self.assertIsInstance(analytics, dict)
        self.assertIn('test_stats', analytics)
        self.assertIn('winner_distribution', analytics)
    
    def test_calculate_statistical_significance(self):
        """Test statistical significance calculation."""
        control_data = {
            'impressions': 1000,
            'conversions': 50
        }
        
        variant_data = {
            'impressions': 1000,
            'conversions': 65
        }
        
        significance = self.ab_test_service._calculate_statistical_significance(
            control_data, variant_data
        )
        
        self.assertIsInstance(significance, dict)
        self.assertIn('p_value', significance)
        self.assertIn('z_score', significance)
        self.assertIn('is_significant', significance)
    
    def test_calculate_conversion_rate(self):
        """Test conversion rate calculation."""
        impressions = 1000
        conversions = 50
        
        cr = self.ab_test_service._calculate_conversion_rate(impressions, conversions)
        
        self.assertEqual(cr, 5.0)
        
        # Test with zero impressions
        cr = self.ab_test_service._calculate_conversion_rate(0, 0)
        self.assertEqual(cr, 0.0)
    
    def test_calculate_effect_size(self):
        """Test effect size calculation."""
        control_cr = 5.0
        variant_cr = 8.0
        
        effect_size = self.ab_test_service._calculate_effect_size(control_cr, variant_cr)
        
        self.assertIsInstance(effect_size, (int, float))
        self.assertGreater(effect_size, 0)
    
    def test_validate_test_configuration(self):
        """Test test configuration validation."""
        valid_config = {
            'name': 'Test A/B Test',
            'control_route_id': self.control_route.id,
            'variant_route_id': self.variant_route.id,
            'split_percentage': 50,
            'min_sample_size': 100,
            'duration_hours': 168
        }
        
        is_valid, errors = self.ab_test_service._validate_test_configuration(valid_config)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid configuration
        invalid_config = {
            'name': '',
            'control_route_id': None,
            'variant_route_id': None,
            'split_percentage': 150,
            'min_sample_size': 0,
            'duration_hours': -1
        }
        
        is_valid, errors = self.ab_test_service._validate_test_configuration(invalid_config)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class ABTestIntegrationTestCase(TestCase):
    """Integration tests for A/B testing functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        from ..models import OfferRoute
        self.control_route = OfferRoute.objects.create(
            name='Control Route',
            description='Control route for A/B testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
        
        self.variant_route = OfferRoute.objects.create(
            name='Variant Route',
            description='Variant route for A/B testing',
            tenant=self.user,
            priority=5,
            max_offers=10,
            is_active=True
        )
    
    def test_ab_test_workflow(self):
        """Test complete A/B test workflow."""
        # Create test
        test_data = {
            'name': 'Integration Test',
            'description': 'Integration test for A/B testing',
            'control_route_id': self.control_route.id,
            'variant_route_id': self.variant_route.id,
            'split_percentage': 50,
            'min_sample_size': 10,
            'duration_hours': 24
        }
        
        test = ab_test_service.create_test(
            tenant_id=self.user.id,
            test_data=test_data
        )
        
        self.assertIsInstance(test, RoutingABTest)
        
        # Start test
        success = ab_test_service.start_test(test.id)
        self.assertTrue(success)
        
        # Assign users
        for i in range(20):
            test_user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'testuser{i}@example.com',
                password='testpass123'
            )
            
            test_offer = self.control_route if i < 10 else self.variant_route
            assignment = ab_test_service.assign_user_to_test(test_user, test_offer)
            
            # Record events
            ab_test_service.record_assignment_event(
                test_user, test_offer, 'impression', 0.0
            )
            
            if i % 5 == 0:
                ab_test_service.record_assignment_event(
                    test_user, test_offer, 'click', 0.0
                )
            
            if i % 10 == 0:
                ab_test_service.record_assignment_event(
                    test_user, test_offer, 'conversion', 10.0
                )
        
        # Evaluate test
        evaluated_count = ab_test_service.evaluate_active_tests()
        self.assertGreaterEqual(evaluated_count, 0)
        
        # Get results
        results = ab_test_service.get_test_results(test.id)
        self.assertIsInstance(results, dict)
    
    def test_ab_test_with_significant_results(self):
        """Test A/B test with significant results."""
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.user,
            name='Significance Test',
            description='Test with significant results',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=20,
            duration_hours=24,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.user
        )
        
        # Create assignments with different conversion rates
        for i in range(40):
            test_user = User.objects.create_user(
                username=f'testuser{i}',
                email=f'testuser{i}@example.com',
                password='testpass123'
            )
            
            variant = 'control' if i < 20 else 'variant'
            test_offer = self.control_route if variant == 'control' else self.variant_route
            
            assignment = ABTestAssignment.objects.create(
                user=test_user,
                test=test,
                variant=variant,
                impressions=10
            )
            
            # Control: 5% CR, Variant: 8% CR
            if variant == 'control':
                assignment.conversions = 0 if i % 20 != 0 else 1
                assignment.revenue = 10.0 if assignment.conversions > 0 else 0.0
            else:
                assignment.conversions = 0 if i % 12 != 0 else 1
                assignment.revenue = 15.0 if assignment.conversions > 0 else 0.0
            
            assignment.save()
        
        # Evaluate test
        evaluated_count = ab_test_service.evaluate_active_tests()
        
        # Check if significant result was found
        test.refresh_from_db()
        if test.ended_at:
            self.assertIsNotNone(test.winner)
            self.assertGreater(test.confidence, 0)
    
    def test_ab_test_performance(self):
        """Test A/B test performance."""
        import time
        
        # Create test
        test = RoutingABTest.objects.create(
            tenant=self.user,
            name='Performance Test',
            description='Performance test for A/B testing',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=24,
            is_active=True,
            started_at=timezone.now(),
            created_by=self.user
        )
        
        # Measure assignment time
        start_time = time.time()
        
        for i in range(100):
            test_user = User.objects.create_user(
                username=f'perfuser{i}',
                email=f'perfuser{i}@example.com',
                password='testpass123'
            )
            
            test_offer = self.control_route if i < 50 else self.variant_route
            ab_test_service.assign_user_to_test(test_user, test_offer)
        
        end_time = time.time()
        assignment_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(assignment_time, 1000)  # Within 1 second
    
    def test_ab_test_error_handling(self):
        """Test error handling in A/B testing."""
        # Test with invalid test data
        invalid_test_data = {
            'name': '',
            'control_route_id': 999999,
            'variant_route_id': 999999,
            'split_percentage': 150,
            'min_sample_size': 0,
            'duration_hours': -1
        }
        
        with self.assertRaises(Exception):
            ab_test_service.create_test(
                tenant_id=self.user.id,
                test_data=invalid_test_data
            )
        
        # Test with invalid test ID
        with self.assertRaises(Exception):
            ab_test_service.start_test(999999)
        
        # Test with invalid assignment
        with self.assertRaises(Exception):
            ab_test_service.assign_user_to_test(None, self.control_route)
    
    def test_ab_test_cleanup(self):
        """Test A/B test cleanup."""
        # Create old test
        old_test = RoutingABTest.objects.create(
            tenant=self.user,
            name='Old Test',
            description='Old test for cleanup',
            control_route=self.control_route,
            variant_route=self.variant_route,
            split_percentage=50,
            min_sample_size=100,
            duration_hours=24,
            ended_at=timezone.now() - timezone.timedelta(days=100),
            created_by=self.user
        )
        
        # Create old assignments and results
        ABTestAssignment.objects.create(
            user=self.user,
            test=old_test,
            variant='control',
            impressions=10,
            clicks=2,
            conversions=1,
            revenue=10.0
        )
        
        ABTestResult.objects.create(
            test=old_test,
            control_impressions=100,
            control_clicks=20,
            control_conversions=5,
            control_revenue=50.0,
            control_cr=5.0,
            variant_impressions=100,
            variant_clicks=25,
            variant_conversions=8,
            variant_revenue=80.0,
            variant_cr=8.0,
            analyzed_at=timezone.now() - timezone.timedelta(days=90)
        )
        
        # Cleanup old tests
        deleted_count = ab_test_service.cleanup_old_tests(days=30)
        
        self.assertIsInstance(deleted_count, int)
        self.assertGreaterEqual(deleted_count, 0)
