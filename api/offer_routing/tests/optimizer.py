"""
Optimizer Tests for Offer Routing System

This module contains unit tests for optimizer functionality,
including route optimization, score optimization, and configuration optimization.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from ..services.optimizer import RoutingOptimizer, routing_optimizer
from ..models import OfferRoute, OfferScore, RoutePerformanceStat
from ..exceptions import OptimizationError, ValidationError

User = get_user_model()


class RoutingOptimizerTestCase(TestCase):
    """Test cases for RoutingOptimizer."""
    
    def setUp(self):
        """Set up test data."""
        self.routing_optimizer = RoutingOptimizer()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.tenant = self.user
        
        # Create test offer routes
        self.offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for optimization',
                tenant=self.tenant,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
        
        # Create performance stats
        for i, offer in enumerate(self.offers):
            RoutePerformanceStat.objects.create(
                tenant=self.tenant,
                offer=offer,
                date=timezone.now().date(),
                impressions=100 + (i * 10),
                clicks=10 + (i * 2),
                conversions=2 + i,
                revenue=20.0 + (i * 5),
                avg_response_time_ms=45.2 + (i * 2),
                click_through_rate=10.0 + (i * 2),
                conversion_rate=2.0 + (i * 0.5)
            )
    
    def test_optimize_route_priorities(self):
        """Test route priority optimization."""
        optimization_result = self.routing_optimizer.optimize_route_priorities(tenant_id=self.tenant.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_routes', optimization_result)
        self.assertIn('priority_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
        self.assertIn('optimization_timestamp', optimization_result)
        
        # Should have optimized some routes
        self.assertIsInstance(optimization_result['optimized_routes'], int)
        self.assertGreaterEqual(optimization_result['optimized_routes'], 0)
        
        # Check priority changes
        priority_changes = optimization_result['priority_changes']
        self.assertIsInstance(priority_changes, list)
        
        for change in priority_changes:
            self.assertIsInstance(change, dict)
            self.assertIn('route_id', change)
            self.assertIn('old_priority', change)
            self.assertIn('new_priority', change)
            self.assertIn('reason', change)
    
    def test_optimize_score_weights(self):
        """Test score weight optimization."""
        optimization_result = self.routing_optimizer.optimize_score_weights(tenant_id=self.tenant.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_configs', optimization_result)
        self.assertIn('weight_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
        self.assertIn('optimization_timestamp', optimization_result)
        
        # Should have optimized some configs
        self.assertIsInstance(optimization_result['optimized_configs'], int)
        self.assertGreaterEqual(optimization_result['optimized_configs'], 0)
        
        # Check weight changes
        weight_changes = optimization_result['weight_changes']
        self.assertIsInstance(weight_changes, list)
        
        for change in weight_changes:
            self.assertIsInstance(change, dict)
            self.assertIn('config_id', change)
            self.assertIn('old_weights', change)
            self.assertIn('new_weights', change)
            self.assertIn('reason', change)
    
    def test_optimize_personalization_config(self):
        """Test personalization configuration optimization."""
        optimization_result = self.routing_optimizer.optimize_personalization_config(tenant_id=self.tenant.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_configs', optimization_result)
        self.assertIn('config_changes', optimization_result)
        self.assertIn('performance_improvement', optimization_result)
        self.assertIn('optimization_timestamp', optimization_result)
        
        # Should have optimized some configs
        self.assertIsInstance(optimization_result['optimized_configs'], int)
        self.assertGreaterEqual(optimization_result['optimized_configs'], 0)
        
        # Check config changes
        config_changes = optimization_result['config_changes']
        self.assertIsInstance(config_changes, list)
        
        for change in config_changes:
            self.assertIsInstance(change, dict)
            self.assertIn('config_id', change)
            self.assertIn('old_config', change)
            self.assertIn('new_config', change)
            self.assertIn('reason', change)
    
    def test_optimize_all_configurations(self):
        """Test optimization of all configurations."""
        optimization_results = self.routing_optimizer.optimize_all_configurations(tenant_id=self.tenant.id)
        
        self.assertIsInstance(optimization_results, dict)
        self.assertIn('route_priorities', optimization_results)
        self.assertIn('score_weights', optimization_results)
        self.assertIn('personalization_configs', optimization_results)
        self.assertIn('overall_improvement', optimization_results)
        self.assertIn('optimization_timestamp', optimization_results)
        
        # Check individual optimization results
        for key, result in optimization_results.items():
            if key != 'overall_improvement' and key != 'optimization_timestamp':
                self.assertIsInstance(result, dict)
                self.assertIn('optimized_count', result)
                self.assertIn('performance_improvement', result)
    
    def test_get_optimization_recommendations(self):
        """Test getting optimization recommendations."""
        recommendations = self.routing_optimizer.get_optimization_recommendations(tenant_id=self.tenant.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('route_priorities', recommendations)
        self.assertIn('score_weights', recommendations)
        self.assertIn('personalization', recommendations)
        self.assertIn('overall', recommendations)
        self.assertIn('recommendation_timestamp', recommendations)
        
        # Check recommendation structure
        for category in ['route_priorities', 'score_weights', 'personalization']:
            self.assertIn(category, recommendations)
            self.assertIsInstance(recommendations[category], list)
            
            for rec in recommendations[category]:
                self.assertIsInstance(rec, dict)
                self.assertIn('type', rec)
                self.assertIn('title', rec)
                self.assertIn('description', rec)
                self.assertIn('priority', rec)
                self.assertIn('estimated_impact', rec)
    
    def test_simulate_optimization(self):
        """Test optimization simulation."""
        optimization_type = 'route_priorities'
        
        simulation_result = self.routing_optimizer.simulate_optimization(
            tenant_id=self.tenant.id,
            optimization_type=optimization_type
        )
        
        self.assertIsInstance(simulation_result, dict)
        self.assertIn('optimization_type', simulation_result)
        self.assertIn('simulated_changes', simulation_result)
        self.assertIn('estimated_improvement', simulation_result)
        self.assertIn('recommendations', simulation_result)
        self.assertIn('simulation_timestamp', simulation_result)
        
        # Should have simulated some changes
        self.assertIsInstance(simulation_result['simulated_changes'], int)
        self.assertGreaterEqual(simulation_result['simulated_changes'], 0)
        
        # Should have recommendations
        recommendations = simulation_result['recommendations']
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
    
    def test_apply_optimization(self):
        """Test applying optimization."""
        optimization_type = 'route_priorities'
        recommendations = [
            {
                'type': 'priority_adjustment',
                'route_id': self.offers[0].id,
                'new_priority': 1,
                'reason': 'High performance'
            }
        ]
        
        result = self.routing_optimizer.apply_optimization(
            tenant_id=self.tenant.id,
            optimization_type=optimization_type,
            recommendations=recommendations
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('optimization_type', result)
        self.assertIn('applied_recommendations', result)
        self.assertIn('optimization_result', result)
        self.assertIn('applied_timestamp', result)
        
        # Should have applied recommendations
        self.assertEqual(len(result['applied_recommendations']), len(recommendations))
    
    def test_get_optimization_status(self):
        """Test getting optimization status."""
        status = self.routing_optimizer.get_optimization_status(tenant_id=self.tenant.id)
        
        self.assertIsInstance(status, dict)
        self.assertIn('routes', status)
        self.assertIn('scoring', status)
        self.assertIn('personalization', status)
        self.assertIn('overall', status)
        self.assertIn('status_timestamp', status)
        
        # Check individual status sections
        for section in ['routes', 'scoring', 'personalization']:
            self.assertIn(section, status)
            self.assertIsInstance(status[section], dict)
            self.assertIn('total', status[section])
            self.assertIn('optimized', status[section])
            self.assertIn('last_optimized', status[section])
    
    def test_create_optimization_schedule(self):
        """Test creating optimization schedule."""
        optimization_type = 'route_priorities'
        schedule = {
            'frequency': 'daily',
            'next_run': timezone.now() + timezone.timedelta(hours=24),
            'enabled': True
        }
        
        result = self.routing_optimizer.create_optimization_schedule(
            tenant_id=self.tenant.id,
            optimization_type=optimization_type,
            schedule=schedule
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('optimization_type', result)
        self.assertIn('tenant_id', result)
        self.assertIn('schedule', result)
        self.assertIn('created_at', result)
        self.assertIn('status', result)
        
        self.assertEqual(result['status'], 'active')
    
    def test_get_optimization_schedules(self):
        """Test getting optimization schedules."""
        schedules = self.routing_optimizer.get_optimization_schedules(tenant_id=self.tenant.id)
        
        self.assertIsInstance(schedules, list)
        
        for schedule in schedules:
            self.assertIsInstance(schedule, dict)
            self.assertIn('id', schedule)
            self.assertIn('optimization_type', schedule)
            self.assertIn('frequency', schedule)
            self.assertIn('next_run', schedule)
            self.assertIn('status', schedule)
    
    def test_rollback_optimization(self):
        """Test optimization rollback."""
        optimization_type = 'route_priorities'
        
        result = self.routing_optimizer.rollback_optimization(
            tenant_id=self.tenant.id,
            optimization_type=optimization_type
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('optimization_type', result)
        self.assertIn('rollback_timestamp', result)
        self.assertIn('changes_reverted', result)
        self.assertIn('status', result)
        
        self.assertEqual(result['status'], 'completed')
    
    def test_get_optimization_metrics(self):
        """Test getting optimization metrics."""
        metrics = self.routing_optimizer.get_optimization_metrics(tenant_id=self.tenant.id, days=30)
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('period_days', metrics)
        self.assertIn('total_optimizations', metrics)
        self.assertIn('successful_optimizations', metrics)
        self.assertIn('failed_optimizations', metrics)
        self.assertIn('avg_improvement', metrics)
        self.assertIn('optimization_types', metrics)
        self.assertIn('trend', metrics)
        
        # Check optimization types
        optimization_types = metrics['optimization_types']
        self.assertIsInstance(optimization_types, dict)
        self.assertIn('route_priorities', optimization_types)
        self.assertIn('score_weights', optimization_types)
        self.assertIn('personalization', optimization_types)
    
    def test_analyze_performance_data(self):
        """Test performance data analysis."""
        performance_data = self.routing_optimizer._analyze_performance_data(tenant_id=self.tenant.id, days=30)
        
        self.assertIsInstance(performance_data, dict)
        self.assertIn('route_performance', performance_data)
        self.assertIn('scoring_performance', performance_data)
        self.assertIn('personalization_performance', performance_data)
        self.assertIn('overall_trends', performance_data)
        
        # Check route performance
        route_perf = performance_data['route_performance']
        self.assertIsInstance(route_perf, dict)
        self.assertIn('avg_response_time', route_perf)
        self.assertIn('avg_conversion_rate', route_perf)
        self.assertIn('avg_revenue_per_impression', route_perf)
        
        # Check overall trends
        trends = performance_data['overall_trends']
        self.assertIsInstance(trends, dict)
        self.assertIn('response_time_trend', trends)
        self.assertIn('conversion_rate_trend', trends)
        self.assertIn('revenue_trend', trends)
    
    def test_calculate_optimization_potential(self):
        """Test optimization potential calculation."""
        potential = self.routing_optimizer._calculate_optimization_potential(self.offers[0])
        
        self.assertIsInstance(potential, dict)
        self.assertIn('priority_optimization', potential)
        self.assertIn('score_optimization', potential)
        self.assertIn('overall_potential', potential)
        self.assertIn('confidence_level', potential)
        
        # Check individual potentials
        for key in ['priority_optimization', 'score_optimization']:
            self.assertIn(key, potential)
            self.assertIsInstance(potential[key], (int, float))
            self.assertGreaterEqual(potential[key], 0)
            self.assertLessEqual(potential[key], 100)
    
    def test_generate_optimization_plan(self):
        """Test optimization plan generation."""
        plan = self.routing_optimizer._generate_optimization_plan(tenant_id=self.tenant.id)
        
        self.assertIsInstance(plan, dict)
        self.assertIn('route_priorities', plan)
        self.assertIn('score_weights', plan)
        self.assertIn('personalization', plan)
        self.assertIn('estimated_total_improvement', plan)
        self.assertIn('estimated_time_to_complete', plan)
        self.assertIn('risks', plan)
        
        # Check individual sections
        for section in ['route_priorities', 'score_weights', 'personalization']:
            self.assertIn(section, plan)
            self.assertIsInstance(plan[section], list)
            
            for item in plan[section]:
                self.assertIsInstance(item, dict)
                self.assertIn('action', item)
                self.assertIn('priority', item)
                self.assertIn('estimated_impact', item)
    
    def test_validate_optimization_parameters(self):
        """Test optimization parameter validation."""
        # Valid parameters
        valid_params = {
            'optimization_type': 'route_priorities',
            'max_changes': 10,
            'min_improvement_threshold': 5.0,
            'confidence_threshold': 0.8
        }
        
        is_valid, errors = self.routing_optimizer._validate_optimization_parameters(valid_params)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid parameters
        invalid_params = {
            'optimization_type': 'invalid_type',
            'max_changes': -1,
            'min_improvement_threshold': -5.0,
            'confidence_threshold': 1.5
        }
        
        is_valid, errors = self.routing_optimizer._validate_optimization_parameters(invalid_params)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


class OptimizationIntegrationTestCase(TestCase):
    """Integration tests for optimizer functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test offers
        self.offers = []
        for i in range(5):
            offer = OfferRoute.objects.create(
                name=f'Test Route {i}',
                description=f'Test route {i} for optimization',
                tenant=self.user,
                priority=i + 1,
                max_offers=10,
                is_active=True
            )
            self.offers.append(offer)
        
        # Create performance stats
        for i, offer in enumerate(self.offers):
            RoutePerformanceStat.objects.create(
                tenant=self.user,
                offer=offer,
                date=timezone.now().date(),
                impressions=100 + (i * 10),
                clicks=10 + (i * 2),
                conversions=2 + i,
                revenue=20.0 + (i * 5),
                avg_response_time_ms=45.2 + (i * 2),
                click_through_rate=10.0 + (i * 2),
                conversion_rate=2.0 + (i * 0.5)
            )
    
    def test_optimizer_workflow(self):
        """Test complete optimizer workflow."""
        # Get optimization recommendations
        recommendations = routing_optimizer.get_optimization_recommendations(tenant_id=self.user.id)
        
        self.assertIsInstance(recommendations, dict)
        self.assertIn('route_priorities', recommendations)
        
        # Simulate optimization
        simulation_result = routing_optimizer.simulate_optimization(
            tenant_id=self.user.id,
            optimization_type='route_priorities'
        )
        
        self.assertIsInstance(simulation_result, dict)
        self.assertIn('estimated_improvement', simulation_result)
        
        # Apply optimization
        if simulation_result['simulated_changes'] > 0:
            result = routing_optimizer.apply_optimization(
                tenant_id=self.user.id,
                optimization_type='route_priorities',
                recommendations=simulation_result['recommendations']
            )
            
            self.assertIsInstance(result, dict)
            self.assertIn('applied_recommendations', result)
        
        # Get optimization status
        status = routing_optimizer.get_optimization_status(tenant_id=self.user.id)
        
        self.assertIsInstance(status, dict)
        self.assertIn('overall', status)
    
    def test_route_priority_optimization(self):
        """Test route priority optimization."""
        # Create performance variation
        for i, offer in enumerate(self.offers):
            # Update performance to create optimization opportunity
            if i == 0:  # High performing route
                RoutePerformanceStat.objects.filter(offer=offer).update(
                    conversions=10,
                    revenue=100.0,
                    conversion_rate=10.0
                )
            elif i == 4:  # Low performing route
                RoutePerformanceStat.objects.filter(offer=offer).update(
                    conversions=1,
                    revenue=5.0,
                    conversion_rate=1.0
                )
        
        optimization_result = routing_optimizer.optimize_route_priorities(tenant_id=self.user.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_routes', optimization_result)
        self.assertIn('priority_changes', optimization_result)
        
        # Should have optimized at least one route
        self.assertGreater(optimization_result['optimized_routes'], 0)
        
        # Check priority changes
        priority_changes = optimization_result['priority_changes']
        self.assertIsInstance(priority_changes, list)
        
        for change in priority_changes:
            self.assertIn('route_id', change)
            self.assertIn('old_priority', change)
            self.assertIn('new_priority', change)
    
    def test_score_weight_optimization(self):
        """Test score weight optimization."""
        # Create score configs
        from ..models import OfferScoreConfig
        
        for offer in self.offers:
            OfferScoreConfig.objects.create(
                tenant=self.user,
                offer=offer,
                epc_weight=0.4,
                cr_weight=0.3,
                relevance_weight=0.2,
                freshness_weight=0.1
            )
        
        optimization_result = routing_optimizer.optimize_score_weights(tenant_id=self.user.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_configs', optimization_result)
        self.assertIn('weight_changes', optimization_result)
        
        # Should have optimized at least one config
        self.assertGreater(optimization_result['optimized_configs'], 0)
        
        # Check weight changes
        weight_changes = optimization_result['weight_changes']
        self.assertIsInstance(weight_changes, list)
        
        for change in weight_changes:
            self.assertIn('config_id', change)
            self.assertIn('old_weights', change)
            self.assertIn('new_weights', change)
    
    def test_personalization_optimization(self):
        """Test personalization optimization."""
        # Create personalization configs
        from ..models import PersonalizationConfig
        
        for offer in self.offers:
            PersonalizationConfig.objects.create(
                tenant=self.user,
                user=self.user,
                algorithm='hybrid',
                collaborative_weight=0.4,
                content_based_weight=0.3,
                hybrid_weight=0.3,
                real_time_enabled=True,
                context_signals_enabled=True
            )
        
        optimization_result = routing_optimizer.optimize_personalization_config(tenant_id=self.user.id)
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimized_configs', optimization_result)
        self.assertIn('config_changes', optimization_result)
        
        # Should have optimized at least one config
        self.assertGreater(optimization_result['optimized_configs'], 0)
        
        # Check config changes
        config_changes = optimization_result['config_changes']
        self.assertIsInstance(config_changes, list)
        
        for change in config_changes:
            self.assertIn('config_id', change)
            self.assertIn('old_config', change)
            self.assertIn('new_config', change)
    
    def test_all_configurations_optimization(self):
        """Test optimization of all configurations."""
        # Create score configs and personalization configs
        from ..models import OfferScoreConfig, PersonalizationConfig
        
        for offer in self.offers:
            OfferScoreConfig.objects.create(
                tenant=self.user,
                offer=offer,
                epc_weight=0.4,
                cr_weight=0.3,
                relevance_weight=0.2,
                freshness_weight=0.1
            )
            
            PersonalizationConfig.objects.create(
                tenant=self.user,
                user=self.user,
                algorithm='hybrid',
                collaborative_weight=0.4,
                content_based_weight=0.3,
                hybrid_weight=0.3,
                real_time_enabled=True,
                context_signals_enabled=True
            )
        
        optimization_results = routing_optimizer.optimize_all_configurations(tenant_id=self.user.id)
        
        self.assertIsInstance(optimization_results, dict)
        self.assertIn('route_priorities', optimization_results)
        self.assertIn('score_weights', optimization_results)
        self.assertIn('personalization_configs', optimization_results)
        self.assertIn('overall_improvement', optimization_results)
        
        # Check individual results
        for key in ['route_priorities', 'score_weights', 'personalization_configs']:
            self.assertIn(key, optimization_results)
            self.assertIsInstance(optimization_results[key], dict)
            self.assertIn('optimized_count', optimization_results[key])
            self.assertIn('performance_improvement', optimization_results[key])
    
    def test_optimization_scheduling(self):
        """Test optimization scheduling."""
        # Create schedule
        optimization_type = 'route_priorities'
        schedule = {
            'frequency': 'daily',
            'next_run': timezone.now() + timezone.timedelta(hours=24),
            'enabled': True
        }
        
        result = routing_optimizer.create_optimization_schedule(
            tenant_id=self.user.id,
            optimization_type=optimization_type,
            schedule=schedule
        )
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'active')
        
        # Get schedules
        schedules = routing_optimizer.get_optimization_schedules(tenant_id=self.user.id)
        
        self.assertIsInstance(schedules, list)
        self.assertGreater(len(schedules), 0)
        
        # Check schedule structure
        for schedule in schedules:
            self.assertIn('optimization_type', schedule)
            self.assertIn('frequency', schedule)
            self.assertIn('next_run', schedule)
            self.assertIn('status', schedule)
    
    def test_optimization_rollback(self):
        """Test optimization rollback."""
        # Apply optimization first
        optimization_result = routing_optimizer.optimize_route_priorities(tenant_id=self.user.id)
        
        if optimization_result['optimized_routes'] > 0:
            # Rollback optimization
            rollback_result = routing_optimizer.rollback_optimization(
                tenant_id=self.user.id,
                optimization_type='route_priorities'
            )
            
            self.assertIsInstance(rollback_result, dict)
            self.assertIn('optimization_type', rollback_result)
            self.assertIn('rollback_timestamp', rollback_result)
            self.assertIn('changes_reverted', rollback_result)
            self.assertEqual(rollback_result['status'], 'completed')
    
    def test_optimization_metrics(self):
        """Test optimization metrics."""
        # Apply some optimizations first
        routing_optimizer.optimize_route_priorities(tenant_id=self.user.id)
        routing_optimizer.optimize_score_weights(tenant_id=self.user.id)
        
        # Get metrics
        metrics = routing_optimizer.get_optimization_metrics(tenant_id=self.user.id, days=30)
        
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_optimizations', metrics)
        self.assertIn('successful_optimizations', metrics)
        self.assertIn('failed_optimizations', metrics)
        self.assertIn('avg_improvement', metrics)
        self.assertIn('optimization_types', metrics)
        
        # Check optimization types
        optimization_types = metrics['optimization_types']
        self.assertIn('route_priorities', optimization_types)
        self.assertIn('score_weights', optimization_types)
        self.assertIn('personalization', optimization_types)
    
    def test_optimization_performance(self):
        """Test optimization performance."""
        import time
        
        # Measure optimization time
        start_time = time.time()
        
        optimization_result = routing_optimizer.optimize_route_priorities(tenant_id=self.user.id)
        
        end_time = time.time()
        optimization_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(optimization_time, 2000)  # Within 2 seconds
        
        # Measure simulation time
        start_time = time.time()
        
        simulation_result = routing_optimizer.simulate_optimization(
            tenant_id=self.user.id,
            optimization_type='route_priorities'
        )
        
        end_time = time.time()
        simulation_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Should complete within reasonable time
        self.assertLess(simulation_time, 1000)  # Within 1 second
    
    def test_optimization_error_handling(self):
        """Test error handling in optimization."""
        # Test with invalid tenant ID
        with self.assertRaises(Exception):
            routing_optimizer.optimize_route_priorities(tenant_id=999999)
        
        # Test with invalid optimization type
        with self.assertRaises(Exception):
            routing_optimizer.simulate_optimization(
                tenant_id=self.user.id,
                optimization_type='invalid_type'
            )
        
        # Test with invalid schedule
        with self.assertRaises(Exception):
            routing_optimizer.create_optimization_schedule(
                tenant_id=self.user.id,
                optimization_type='route_priorities',
                schedule={}
            )
        
        # Test with invalid recommendations
        with self.assertRaises(Exception):
            routing_optimizer.apply_optimization(
                tenant_id=self.user.id,
                optimization_type='route_priorities',
                recommendations=[]
            )
