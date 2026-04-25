"""
Core Routing Engine for Offer Routing System

This module contains the core routing engine that handles offer routing logic,
including route matching, condition evaluation, action execution, and decision making.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, F, Window
from django.db.models.functions import RowNumber

from .models import (
    OfferRoute, RouteCondition, RouteAction, OfferScore, UserOfferHistory,
    RoutingDecisionLog, RoutingInsight, OfferRoutingCap, UserOfferCap,
    RoutingABTest, ABTestAssignment, NetworkPerformanceCache
)
from .exceptions import RoutingError, ConditionEvaluationError, ActionExecutionError
from .utils import get_user_context, get_offer_context, calculate_route_score
from .signals import routing_decision_made, cap_limit_reached

logger = logging.getLogger(__name__)
User = get_user_model()


class RoutingEngine:
    """
    Core routing engine for offer routing system.
    
    This class handles the complete routing process:
    1. Context preparation
    2. Route matching
    3. Condition evaluation
    4. Action execution
    5. Decision logging
    6. Performance tracking
    """
    
    def __init__(self, cache_enabled: bool = True, performance_tracking: bool = True):
        self.cache_enabled = cache_enabled
        self.performance_tracking = performance_tracking
        self.logger = logging.getLogger(__name__)
    
    def route_offer(self, user_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main routing method to find the best offer for a user.
        
        Args:
            user_id: User ID
            context: Additional context data
            
        Returns:
            Routing decision result
        """
        start_time = time.time()
        
        try:
            # Prepare context
            full_context = self._prepare_context(user_id, context)
            
            # Get matching routes
            matching_routes = self._get_matching_routes(full_context)
            
            if not matching_routes:
                return self._create_no_route_result(full_context, start_time)
            
            # Evaluate conditions and score routes
            scored_routes = self._evaluate_and_score_routes(matching_routes, full_context)
            
            if not scored_routes:
                return self._create_no_route_result(full_context, start_time)
            
            # Select best route
            best_route = self._select_best_route(scored_routes, full_context)
            
            # Execute route actions
            action_results = self._execute_route_actions(best_route, full_context)
            
            # Create result
            result = self._create_routing_result(best_route, action_results, full_context, start_time)
            
            # Log decision
            self._log_routing_decision(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in route_offer for user {user_id}: {str(e)}")
            return self._create_error_result(user_id, str(e), start_time)
    
    def route_multiple_offers(self, user_id: int, count: int = 5, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Route multiple offers for a user.
        
        Args:
            user_id: User ID
            count: Number of offers to return
            context: Additional context data
            
        Returns:
            List of routing decisions
        """
        start_time = time.time()
        results = []
        
        try:
            # Prepare context
            full_context = self._prepare_context(user_id, context)
            
            # Get matching routes
            matching_routes = self._get_matching_routes(full_context)
            
            if not matching_routes:
                return [self._create_no_route_result(full_context, start_time)]
            
            # Evaluate conditions and score routes
            scored_routes = self._evaluate_and_score_routes(matching_routes, full_context)
            
            if not scored_routes:
                return [self._create_no_route_result(full_context, start_time)]
            
            # Get top routes
            top_routes = scored_routes[:count]
            
            # Process each route
            for route_data in top_routes:
                route = route_data['route']
                
                # Execute actions
                action_results = self._execute_route_actions(route, full_context)
                
                # Create result
                result = self._create_routing_result(route, action_results, full_context, start_time)
                
                # Add to results
                results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in route_multiple_offers for user {user_id}: {str(e)}")
            return [self._create_error_result(user_id, str(e), start_time)]
    
    def _prepare_context(self, user_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Prepare full context for routing."""
        full_context = context or {}
        
        # Add user context
        user_context = get_user_context(user_id)
        full_context.update(user_context)
        
        # Add system context
        full_context.update({
            'timestamp': timezone.now(),
            'routing_engine_version': '1.0.0',
            'cache_enabled': self.cache_enabled,
            'performance_tracking': self.performance_tracking
        })
        
        return full_context
    
    def _get_matching_routes(self, context: Dict[str, Any]) -> List[OfferRoute]:
        """Get routes that match the context."""
        cache_key = f"matching_routes:{hash(str(context))}"
        
        if self.cache_enabled:
            cached_routes = cache.get(cache_key)
            if cached_routes:
                return cached_routes
        
        # Get active routes
        routes = OfferRoute.objects.get_active_routes()
        
        # Apply basic filters
        filtered_routes = []
        for route in routes:
            if self._route_matches_context(route, context):
                filtered_routes.append(route)
        
        # Cache result
        if self.cache_enabled:
            cache.set(cache_key, filtered_routes, timeout=300)  # 5 minutes
        
        return filtered_routes
    
    def _route_matches_context(self, route: OfferRoute, context: Dict[str, Any]) -> bool:
        """Check if route matches basic context requirements."""
        # Check geographic targeting
        if route.geo_targeting and not self._matches_geo_targeting(route.geo_targeting, context):
            return False
        
        # Check device targeting
        if route.device_targeting and not self._matches_device_targeting(route.device_targeting, context):
            return False
        
        # Check user segment targeting
        if route.user_segment_targeting and not self._matches_user_segment_targeting(route.user_segment_targeting, context):
            return False
        
        # Check time targeting
        if route.time_targeting and not self._matches_time_targeting(route.time_targeting, context):
            return False
        
        return True
    
    def _matches_geo_targeting(self, geo_targeting, context: Dict[str, Any]) -> bool:
        """Check if context matches geographic targeting."""
        user_country = context.get('country')
        if not user_country:
            return True  # No country info, assume match
        
        allowed_countries = geo_targeting.countries or []
        excluded_countries = geo_targeting.excluded_countries or []
        
        if excluded_countries and user_country in excluded_countries:
            return False
        
        if allowed_countries and user_country not in allowed_countries:
            return False
        
        return True
    
    def _matches_device_targeting(self, device_targeting, context: Dict[str, Any]) -> bool:
        """Check if context matches device targeting."""
        user_device = context.get('device_type')
        if not user_device:
            return True  # No device info, assume match
        
        allowed_devices = device_targeting.device_types or []
        excluded_devices = device_targeting.excluded_device_types or []
        
        if excluded_devices and user_device in excluded_devices:
            return False
        
        if allowed_devices and user_device not in allowed_devices:
            return False
        
        return True
    
    def _matches_user_segment_targeting(self, user_segment_targeting, context: Dict[str, Any]) -> bool:
        """Check if context matches user segment targeting."""
        user_segments = context.get('user_segments', [])
        
        required_segments = user_segment_targeting.required_segments or []
        excluded_segments = user_segment_targeting.excluded_segments or []
        
        # Check excluded segments
        for segment in excluded_segments:
            if segment in user_segments:
                return False
        
        # Check required segments
        if required_segments:
            for segment in required_segments:
                if segment not in user_segments:
                    return False
        
        return True
    
    def _matches_time_targeting(self, time_targeting, context: Dict[str, Any]) -> bool:
        """Check if context matches time targeting."""
        current_time = timezone.now()
        
        # Check hours
        if time_targeting.hours:
            if current_time.hour not in time_targeting.hours:
                return False
        
        # Check days of week
        if time_targeting.days_of_week:
            if current_time.weekday() not in time_targeting.days_of_week:
                return False
        
        # Check date range
        if time_targeting.start_date and current_time < time_targeting.start_date:
            return False
        
        if time_targeting.end_date and current_time > time_targeting.end_date:
            return False
        
        return True
    
    def _evaluate_and_score_routes(self, routes: List[OfferRoute], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate conditions and score routes."""
        scored_routes = []
        
        for route in routes:
            try:
                # Evaluate conditions
                condition_results = self._evaluate_route_conditions(route, context)
                
                # Check if all conditions pass
                if not all(result['passed'] for result in condition_results):
                    continue
                
                # Calculate route score
                route_score = self._calculate_route_score(route, context, condition_results)
                
                scored_routes.append({
                    'route': route,
                    'condition_results': condition_results,
                    'score': route_score
                })
                
            except Exception as e:
                self.logger.error(f"Error evaluating route {route.id}: {str(e)}")
                continue
        
        # Sort by score (descending)
        scored_routes.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_routes
    
    def _evaluate_route_conditions(self, route: OfferRoute, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate all conditions for a route."""
        conditions = route.conditions.filter(is_active=True).order_by('priority')
        results = []
        
        for condition in conditions:
            try:
                result = condition.evaluate(context)
                results.append({
                    'condition_id': condition.id,
                    'condition_type': condition.condition_type,
                    'passed': result,
                    'evaluation_time': time.time()
                })
            except Exception as e:
                self.logger.error(f"Error evaluating condition {condition.id}: {str(e)}")
                results.append({
                    'condition_id': condition.id,
                    'condition_type': condition.condition_type,
                    'passed': False,
                    'error': str(e)
                })
        
        return results
    
    def _calculate_route_score(self, route: OfferRoute, context: Dict[str, Any], condition_results: List[Dict[str, Any]]) -> float:
        """Calculate route score."""
        base_score = route.priority or 50
        
        # Add condition score bonus
        condition_bonus = sum(1 for result in condition_results if result['passed'])
        
        # Add personalization score
        personalization_score = self._get_personalization_score(route, context)
        
        # Add performance score
        performance_score = self._get_performance_score(route, context)
        
        # Add A/B test score
        ab_test_score = self._get_ab_test_score(route, context)
        
        # Calculate final score
        final_score = (
            base_score * 0.3 +
            condition_bonus * 0.2 +
            personalization_score * 0.25 +
            performance_score * 0.15 +
            ab_test_score * 0.1
        )
        
        return min(final_score, 100)  # Cap at 100
    
    def _get_personalization_score(self, route: OfferRoute, context: Dict[str, Any]) -> float:
        """Get personalization score for route."""
        user_id = context.get('user_id')
        if not user_id:
            return 50.0  # Default score
        
        # Get user's interaction history with this route
        history_count = UserOfferHistory.objects.filter(
            user_id=user_id,
            route=route
        ).count()
        
        if history_count == 0:
            return 50.0  # No history, default score
        
        # Calculate score based on historical performance
        successful_interactions = UserOfferHistory.objects.filter(
            user_id=user_id,
            route=route,
            success=True
        ).count()
        
        success_rate = successful_interactions / history_count
        return success_rate * 100
    
    def _get_performance_score(self, route: OfferRoute, context: Dict[str, Any]) -> float:
        """Get performance score for route."""
        # Get recent performance metrics
        recent_logs = RoutingDecisionLog.objects.filter(
            route=route,
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        )
        
        if not recent_logs.exists():
            return 50.0  # No recent data, default score
        
        total_decisions = recent_logs.count()
        successful_decisions = recent_logs.filter(success=True).count()
        
        success_rate = successful_decisions / total_decisions
        return success_rate * 100
    
    def _get_ab_test_score(self, route: OfferRoute, context: Dict[str, Any]) -> float:
        """Get A/B test score for route."""
        user_id = context.get('user_id')
        if not user_id:
            return 50.0  # No user, default score
        
        # Check if user is in any A/B tests for this route
        active_tests = RoutingABTest.objects.filter(
            route=route,
            status='running'
        )
        
        for test in active_tests:
            assignment = ABTestAssignment.objects.filter(
                test_id=test.id,
                user_id=user_id
            ).first()
            
            if assignment:
                # Return score based on variant performance
                return self._get_variant_score(test, assignment.variant)
        
        return 50.0  # No A/B test assignment, default score
    
    def _get_variant_score(self, test: RoutingABTest, variant: str) -> float:
        """Get score for A/B test variant."""
        # This would typically be based on historical performance
        # For now, return a simple score based on variant
        variant_scores = {
            'control': 50.0,
            'variant_a': 55.0,
            'variant_b': 45.0
        }
        
        return variant_scores.get(variant, 50.0)
    
    def _select_best_route(self, scored_routes: List[Dict[str, Any]], context: Dict[str, Any]) -> OfferRoute:
        """Select the best route from scored routes."""
        # Check caps
        available_routes = []
        
        for route_data in scored_routes:
            route = route_data['route']
            
            # Check offer caps
            if not self._check_caps(route, context):
                continue
            
            # Check user caps
            if not self._check_user_caps(route, context):
                continue
            
            available_routes.append(route_data)
        
        if not available_routes:
            raise RoutingError("No routes available due to caps")
        
        # Return the highest scoring available route
        return available_routes[0]['route']
    
    def _check_caps(self, route: OfferRoute, context: Dict[str, Any]) -> bool:
        """Check if route caps allow routing."""
        for offer in route.offers.all():
            caps = OfferRoutingCap.objects.filter(
                offer=offer,
                is_active=True
            )
            
            for cap in caps:
                if cap.is_limit_reached():
                    self.logger.warning(f"Cap limit reached for offer {offer.id}, cap type {cap.cap_type}")
                    return False
        
        return True
    
    def _check_user_caps(self, route: OfferRoute, context: Dict[str, Any]) -> bool:
        """Check if user caps allow routing."""
        user_id = context.get('user_id')
        if not user_id:
            return True  # No user, no caps to check
        
        for offer in route.offers.all():
            caps = UserOfferCap.objects.filter(
                user_id=user_id,
                offer=offer,
                is_active=True
            )
            
            for cap in caps:
                if cap.is_limit_reached():
                    self.logger.warning(f"User cap limit reached for user {user_id}, offer {offer.id}")
                    return False
        
        return True
    
    def _execute_route_actions(self, route: OfferRoute, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all actions for a route."""
        actions = route.actions.filter(is_active=True).order_by('priority')
        results = []
        
        for action in actions:
            try:
                result = action.execute(context)
                results.append({
                    'action_id': action.id,
                    'action_type': action.action_type,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                self.logger.error(f"Error executing action {action.id}: {str(e)}")
                results.append({
                    'action_id': action.id,
                    'action_type': action.action_type,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def _create_routing_result(self, route: OfferRoute, action_results: List[Dict[str, Any]], context: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Create routing result."""
        response_time = time.time() - start_time
        
        return {
            'success': True,
            'route_id': route.id,
            'route_name': route.name,
            'offers': [offer.id for offer in route.offers.all()],
            'score': self._calculate_route_score(route, context, []),
            'action_results': action_results,
            'response_time': response_time,
            'context': context,
            'timestamp': timezone.now()
        }
    
    def _create_no_route_result(self, context: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Create result for no matching routes."""
        response_time = time.time() - start_time
        
        return {
            'success': False,
            'error': 'No matching routes found',
            'route_id': None,
            'route_name': None,
            'offers': [],
            'score': 0.0,
            'action_results': [],
            'response_time': response_time,
            'context': context,
            'timestamp': timezone.now()
        }
    
    def _create_error_result(self, user_id: int, error: str, start_time: float) -> Dict[str, Any]:
        """Create result for routing error."""
        response_time = time.time() - start_time
        
        return {
            'success': False,
            'error': error,
            'route_id': None,
            'route_name': None,
            'offers': [],
            'score': 0.0,
            'action_results': [],
            'response_time': response_time,
            'context': {'user_id': user_id},
            'timestamp': timezone.now()
        }
    
    def _log_routing_decision(self, result: Dict[str, Any]):
        """Log routing decision."""
        try:
            RoutingDecisionLog.objects.create(
                user_id=result['context'].get('user_id'),
                route_id=result.get('route_id'),
                context=result['context'],
                success=result['success'],
                response_time=result['response_time'],
                score=result.get('score', 0.0),
                error_message=result.get('error')
            )
            
            # Send signal
            routing_decision_made.send(
                sender=self.__class__,
                user_id=result['context'].get('user_id'),
                route_id=result.get('route_id'),
                success=result['success'],
                response_time=result['response_time'],
                score=result.get('score', 0.0)
            )
            
        except Exception as e:
            self.logger.error(f"Error logging routing decision: {str(e)}")


class PersonalizedRoutingEngine(RoutingEngine):
    """
    Enhanced routing engine with personalization features.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ml_enabled = getattr(settings, 'ML_ROUTING_ENABLED', False)
    
    def route_offer(self, user_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Route offer with personalization."""
        # Add personalization context
        personalized_context = self._add_personalization_context(user_id, context)
        
        # Use parent routing logic
        result = super().route_offer(user_id, personalized_context)
        
        # Add personalization insights
        if result['success']:
            result['personalization_insights'] = self._get_personalization_insights(user_id, result)
        
        return result
    
    def _add_personalization_context(self, user_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add personalization context."""
        personalized_context = context or {}
        
        # Add user preferences
        user_preferences = self._get_user_preferences(user_id)
        personalized_context['user_preferences'] = user_preferences
        
        # Add user journey
        user_journey = self._get_user_journey(user_id)
        personalized_context['user_journey'] = user_journey
        
        # Add behavioral patterns
        behavioral_patterns = self._get_behavioral_patterns(user_id)
        personalized_context['behavioral_patterns'] = behavioral_patterns
        
        # Add ML predictions if enabled
        if self.ml_enabled:
            ml_predictions = self._get_ml_predictions(user_id)
            personalized_context['ml_predictions'] = ml_predictions
        
        return personalized_context
    
    def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user preferences."""
        # Implementation would get user preferences from database
        return {}
    
    def _get_user_journey(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user journey."""
        # Implementation would get user journey from database
        return []
    
    def _get_behavioral_patterns(self, user_id: int) -> Dict[str, Any]:
        """Get behavioral patterns."""
        # Implementation would analyze user behavior
        return {}
    
    def _get_ml_predictions(self, user_id: int) -> Dict[str, Any]:
        """Get ML predictions."""
        # Implementation would use ML models
        return {}
    
    def _get_personalization_insights(self, user_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
        """Get personalization insights."""
        # Implementation would generate insights
        return {}


# Global routing engine instances
routing_engine = RoutingEngine()
personalized_routing_engine = PersonalizedRoutingEngine()


# Utility functions
def route_offer(user_id: int, context: Dict[str, Any] = None, personalized: bool = False) -> Dict[str, Any]:
    """Route offer for user."""
    engine = personalized_routing_engine if personalized else routing_engine
    return engine.route_offer(user_id, context)


def route_multiple_offers(user_id: int, count: int = 5, context: Dict[str, Any] = None, personalized: bool = False) -> List[Dict[str, Any]]:
    """Route multiple offers for user."""
    engine = personalized_routing_engine if personalized else routing_engine
    return engine.route_multiple_offers(user_id, count, context)


# Export the main classes and functions
__all__ = [
    'RoutingEngine',
    'PersonalizedRoutingEngine',
    'routing_engine',
    'personalized_routing_engine',
    'route_offer',
    'route_multiple_offers',
]
