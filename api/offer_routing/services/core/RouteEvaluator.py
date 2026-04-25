"""
Route Evaluator Service

Evaluates route conditions against user context to determine
which routes match and should be considered for offer routing.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ...models import (
    OfferRoute, RouteCondition, RouteAction,
    GeoRouteRule, DeviceRouteRule, UserSegmentRule,
    TimeRouteRule, BehaviorRouteRule
)
from ...choices import RouteConditionType, RouteOperator, ActionType
from ...exceptions import TargetingError, RouteEvaluationError
from ...utils import extract_device_info, get_geo_location_from_ip

User = get_user_model()
logger = logging.getLogger(__name__)


class RouteEvaluator:
    """
    Service for evaluating route conditions and determining
    which routes match a user's profile and context.
    
    Performance target: <5ms per route evaluation
    """
    
    def __init__(self):
        self.condition_cache = {}
        self.evaluation_stats = {
            'total_evaluations': 0,
            'cache_hits': 0,
            'avg_time_ms': 0
        }
    
    def evaluate_route(self, route: OfferRoute, user: User, 
                     context: Dict[str, Any]) -> bool:
        """
        Evaluate if a route matches the user and context.
        
        Args:
            route: Route to evaluate
            user: User object
            context: User context (device, location, time, etc.)
            
        Returns:
            True if route matches, False otherwise
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(route, user, context)
            if cache_key in self.condition_cache:
                self.evaluation_stats['cache_hits'] += 1
                return self.condition_cache[cache_key]
            
            # Get route conditions
            conditions = route.conditions.filter(is_active=True).order_by('priority')
            
            if not conditions:
                # No conditions means route matches everyone
                result = True
            else:
                result = self._evaluate_conditions(conditions, user, context)
            
            # Cache result
            self.condition_cache[cache_key] = result
            
            # Update stats
            self.evaluation_stats['total_evaluations'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating route {route.id} for user {user.id}: {e}")
            return False
    
    def _evaluate_conditions(self, conditions: List[RouteCondition], 
                           user: User, context: Dict[str, Any]) -> bool:
        """Evaluate multiple conditions for a route."""
        if not conditions:
            return True
        
        # Group conditions by logic type (AND/OR)
        and_conditions = []
        or_conditions = []
        
        for condition in conditions:
            if condition.logic == RouteConditionType.AND:
                and_conditions.append(condition)
            else:
                or_conditions.append(condition)
        
        # Evaluate AND conditions (all must be true)
        and_result = True
        for condition in and_conditions:
            if not self._evaluate_single_condition(condition, user, context):
                and_result = False
                break
        
        # Evaluate OR conditions (at least one must be true)
        or_result = False
        for condition in or_conditions:
            if self._evaluate_single_condition(condition, user, context):
                or_result = True
                break
        
        # Final result depends on condition types
        if and_conditions and or_conditions:
            # Mixed AND/OR - both groups must be satisfied
            return and_result and or_result
        elif and_conditions:
            # Only AND conditions
            return and_result
        elif or_conditions:
            # Only OR conditions
            return or_result
        else:
            # No conditions
            return True
    
    def _evaluate_single_condition(self, condition: RouteCondition, 
                                user: User, context: Dict[str, Any]) -> bool:
        """Evaluate a single route condition."""
        try:
            field_value = self._get_field_value(condition.field_name, user, context)
            condition_value = self._parse_condition_value(condition.value)
            
            return self._apply_operator(
                field_value, condition_value, condition.operator
            )
            
        except Exception as e:
            logger.error(f"Error evaluating condition {condition.id}: {e}")
            return False
    
    def _get_field_value(self, field_name: str, user: User, 
                        context: Dict[str, Any]) -> Any:
        """Get value for a field from user or context."""
        # User fields
        if field_name.startswith('user.'):
            user_field = field_name[5:]  # Remove 'user.' prefix
            return getattr(user, user_field, None)
        
        # Context fields
        if field_name.startswith('context.'):
            context_field = field_name[8:]  # Remove 'context.' prefix
            return context.get(context_field, None)
        
        # Special fields
        if field_name == 'user_segment':
            return self._get_user_segment(user)
        elif field_name == 'device_type':
            return context.get('device', {}).get('type')
        elif field_name == 'country':
            return context.get('location', {}).get('country')
        elif field_name == 'hour_of_day':
            return timezone.now().hour
        elif field_name == 'day_of_week':
            return timezone.now().weekday()
        elif field_name == 'is_premium_user':
            return self._is_premium_user(user)
        
        # Default to context
        return context.get(field_name, None)
    
    def _parse_condition_value(self, value: str) -> Any:
        """Parse condition value to appropriate type."""
        # Try to parse as JSON first
        try:
            import json
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try to parse as number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Try to parse as boolean
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Return as string
        return value
    
    def _apply_operator(self, field_value: Any, condition_value: Any, 
                       operator: str) -> bool:
        """Apply comparison operator to field and condition values."""
        try:
            if operator == RouteOperator.EQUALS:
                return field_value == condition_value
            elif operator == RouteOperator.NOT_EQUALS:
                return field_value != condition_value
            elif operator == RouteOperator.GREATER_THAN:
                return field_value > condition_value
            elif operator == RouteOperator.LESS_THAN:
                return field_value < condition_value
            elif operator == RouteOperator.GREATER_EQUAL:
                return field_value >= condition_value
            elif operator == RouteOperator.LESS_EQUAL:
                return field_value <= condition_value
            elif operator == RouteOperator.IN:
                return field_value in condition_value
            elif operator == RouteOperator.NOT_IN:
                return field_value not in condition_value
            elif operator == RouteOperator.CONTAINS:
                return condition_value in str(field_value)
            elif operator == RouteOperator.NOT_CONTAINS:
                return condition_value not in str(field_value)
            elif operator == RouteOperator.STARTS_WITH:
                return str(field_value).startswith(str(condition_value))
            elif operator == RouteOperator.ENDS_WITH:
                return str(field_value).endswith(str(condition_value))
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying operator {operator}: {e}")
            return False
    
    def _get_user_segment(self, user: User) -> str:
        """Get user segment information."""
        # This would implement user segmentation logic
        # For now, return basic segment
        if user.date_joined > timezone.now() - timezone.timedelta(days=30):
            return 'new'
        elif user.is_active:
            return 'active'
        else:
            return 'churned'
    
    def _is_premium_user(self, user: User) -> bool:
        """Check if user is premium."""
        # This would check premium status
        # For now, check user profile or subscription
        return getattr(user, 'is_premium', False)
    
    def _get_cache_key(self, route: OfferRoute, user: User, 
                      context: Dict[str, Any]) -> str:
        """Generate cache key for route evaluation."""
        # Create a simple cache key based on route, user, and key context fields
        key_fields = [
            str(route.id),
            str(user.id),
            str(context.get('device', {}).get('type', '')),
            str(context.get('location', {}).get('country', '')),
            str(timezone.now().hour),
            str(timezone.now().weekday())
        ]
        return ':'.join(key_fields)
    
    def evaluate_route_actions(self, route: OfferRoute, user: User, 
                             context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate actions that should be applied when route matches.
        
        Args:
            route: Route that matched
            user: User object
            context: User context
            
        Returns:
            List of actions to apply
        """
        actions = []
        
        try:
            route_actions = route.actions.filter(is_active=True).order_by('priority')
            
            for action in route_actions:
                action_data = {
                    'action_type': action.action_type,
                    'action_value': action.action_value,
                    'priority': action.priority,
                    'route_id': route.id,
                    'route_name': route.name
                }
                
                # Check if action should be applied
                if self._should_apply_action(action, user, context):
                    actions.append(action_data)
            
            return actions
            
        except Exception as e:
            logger.error(f"Error evaluating actions for route {route.id}: {e}")
            return []
    
    def _should_apply_action(self, action: RouteAction, user: User, 
                           context: Dict[str, Any]) -> bool:
        """Check if an action should be applied."""
        # This would implement action-specific logic
        # For now, always apply actions
        return True
    
    def get_route_priority(self, route: OfferRoute, user: User, 
                         context: Dict[str, Any]) -> int:
        """
        Calculate effective priority for a route based on user and context.
        
        Args:
            route: Route to evaluate
            user: User object
            context: User context
            
        Returns:
            Effective priority (lower numbers = higher priority)
        """
        base_priority = route.priority
        
        # Apply priority adjustments based on conditions
        # This would implement dynamic priority logic
        
        return base_priority
    
    def clear_cache(self):
        """Clear evaluation cache."""
        self.condition_cache.clear()
        logger.info("Route evaluation cache cleared")
    
    def get_evaluation_stats(self) -> Dict[str, Any]:
        """Get evaluation performance statistics."""
        return {
            'total_evaluations': self.evaluation_stats['total_evaluations'],
            'cache_hits': self.evaluation_stats['cache_hits'],
            'cache_hit_rate': (
                self.evaluation_stats['cache_hits'] / 
                max(1, self.evaluation_stats['total_evaluations'])
            ),
            'cache_size': len(self.condition_cache),
            'avg_time_ms': self.evaluation_stats['avg_time_ms']
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on route evaluator."""
        try:
            # Test basic evaluation
            test_user = User(id=1, username='test')
            test_context = {'device': {'type': 'mobile'}, 'location': {'country': 'US'}}
            
            # This would create a test route and evaluate it
            # For now, return basic health status
            
            return {
                'status': 'healthy',
                'cache_size': len(self.condition_cache),
                'stats': self.get_evaluation_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
