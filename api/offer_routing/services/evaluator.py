"""
Route Evaluator Service for Offer Routing System

This module provides route evaluation functionality to validate
and test routing configurations and conditions.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import OfferRoute, RouteCondition
from ..exceptions import ValidationError, ConditionEvaluationError

User = get_user_model()
logger = logging.getLogger(__name__)


class RouteEvaluator:
    """
    Service for evaluating routing configurations and conditions.
    
    Provides validation, testing, and debugging functionality for routes.
    """
    
    def __init__(self):
        self.targeting_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize evaluator services."""
        try:
            from .targeting import TargetingService
            self.targeting_service = TargetingService()
        except ImportError as e:
            logger.error(f"Failed to initialize evaluator services: {e}")
    
    def validate_route(self, route: OfferRoute) -> Dict[str, Any]:
        """Validate a complete route configuration."""
        try:
            validation_result = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'recommendations': []
            }
            
            # Validate basic fields
            self._validate_basic_fields(route, validation_result)
            
            # Validate conditions
            self._validate_conditions(route, validation_result)
            
            # Validate actions
            self._validate_actions(route, validation_result)
            
            # Validate targeting rules
            self._validate_targeting_rules(route, validation_result)
            
            # Check for logical issues
            self._check_logical_issues(route, validation_result)
            
            # Generate recommendations
            self._generate_recommendations(route, validation_result)
            
            # Set overall validity
            validation_result['is_valid'] = len(validation_result['errors']) == 0
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating route: {e}")
            return {
                'is_valid': False,
                'errors': [str(e)],
                'warnings': [],
                'recommendations': []
            }
    
    def _validate_basic_fields(self, route: OfferRoute, result: Dict[str, Any]):
        """Validate basic route fields."""
        try:
            # Check name
            if not route.name or not route.name.strip():
                result['errors'].append("Route name is required")
            elif len(route.name) > 100:
                result['warnings'].append("Route name is longer than 100 characters")
            
            # Check priority
            if route.priority < 1 or route.priority > 10:
                result['errors'].append("Route priority must be between 1 and 10")
            
            # Check max_offers
            if route.max_offers < 1 or route.max_offers > 1000:
                result['errors'].append("Max offers must be between 1 and 1000")
            
            # Check tenant
            if not route.tenant:
                result['errors'].append("Route must have a tenant")
            
        except Exception as e:
            logger.error(f"Error validating basic fields: {e}")
            result['errors'].append(f"Basic field validation error: {str(e)}")
    
    def _validate_conditions(self, route: OfferRoute, result: Dict[str, Any]):
        """Validate route conditions."""
        try:
            conditions = route.conditions.all()
            
            if not conditions.exists():
                result['warnings'].append("Route has no conditions - it will match all users")
                return
            
            for condition in conditions:
                condition_errors = self._validate_single_condition(condition)
                result['errors'].extend(condition_errors['errors'])
                result['warnings'].extend(condition_errors['warnings'])
            
        except Exception as e:
            logger.error(f"Error validating conditions: {e}")
            result['errors'].append(f"Condition validation error: {str(e)}")
    
    def _validate_single_condition(self, condition: RouteCondition) -> Dict[str, Any]:
        """Validate a single condition."""
        errors = []
        warnings = []
        
        try:
            # Check field_name
            if not condition.field_name or not condition.field_name.strip():
                errors.append("Condition field_name is required")
            
            # Check operator
            if not condition.operator:
                errors.append("Condition operator is required")
            
            # Check value
            if condition.value is None or condition.value == '':
                errors.append("Condition value is required")
            
            # Validate operator-value compatibility
            if condition.operator and condition.value and condition.field_name:
                compatibility_error = self._check_operator_value_compatibility(
                    condition.operator, condition.value, condition.field_name
                )
                if compatibility_error:
                    errors.append(compatibility_error)
            
            # Check for potential logical issues
            if condition.field_name == 'user_id' and condition.operator == 'equals':
                warnings.append("Condition on user_id is rarely useful in production")
            
        except Exception as e:
            errors.append(f"Condition validation error: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _check_operator_value_compatibility(self, operator: str, value: Any, field_name: str) -> Optional[str]:
        """Check if operator and value are compatible."""
        try:
            # Check IN/NOT_IN operators
            if operator in ['in', 'not_in']:
                if not isinstance(value, (list, tuple)):
                    return f"Operator '{operator}' requires a list/tuple value"
                if len(value) == 0:
                    return f"Operator '{operator}' requires non-empty list/tuple"
                if len(value) > 100:
                    return f"Operator '{operator}' list cannot exceed 100 items"
            
            # Check numeric operators
            if operator in ['greater_than', 'less_than', 'greater_equal', 'less_equal']:
                if field_name in ['age', 'score', 'priority']:
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        return f"Operator '{operator}' requires numeric value for field '{field_name}'"
            
            # Check string operators
            if operator in ['contains', 'not_contains', 'starts_with', 'ends_with']:
                if not isinstance(value, str):
                    return f"Operator '{operator}' requires string value"
                if len(value) > 500:
                    return f"String value cannot exceed 500 characters"
            
            return None
            
        except Exception as e:
            return f"Operator-value compatibility check failed: {str(e)}"
    
    def _validate_actions(self, route: OfferRoute, result: Dict[str, Any]):
        """Validate route actions."""
        try:
            actions = route.actions.all()
            
            if not actions.exists():
                result['warnings'].append("Route has no actions - no offers will be returned")
                return
            
            for action in actions:
                action_errors = self._validate_single_action(action)
                result['errors'].extend(action_errors['errors'])
                result['warnings'].extend(action_errors['warnings'])
            
        except Exception as e:
            logger.error(f"Error validating actions: {e}")
            result['errors'].append(f"Action validation error: {str(e)}")
    
    def _validate_single_action(self, action) -> Dict[str, Any]:
        """Validate a single action."""
        errors = []
        warnings = []
        
        try:
            # Check action_type
            if not action.action_type:
                errors.append("Action type is required")
            
            # Check action_value for certain types
            if action.action_type in ['show_promo', 'redirect_url'] and not action.action_value:
                errors.append(f"Action type '{action.action_type}' requires action_value")
            
        except Exception as e:
            errors.append(f"Action validation error: {str(e)}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _validate_targeting_rules(self, route: OfferRoute, result: Dict[str, Any]):
        """Validate targeting rules."""
        try:
            # Check geographic rules
            geo_rules = route.geo_rules.all()
            for rule in geo_rules:
                if not rule.country and not rule.region and not rule.city:
                    result['warnings'].append("Geographic rule has no location specified")
            
            # Check device rules
            device_rules = route.device_rules.all()
            for rule in device_rules:
                if not rule.device_type and not rule.os_type and not rule.browser:
                    result['warnings'].append("Device rule has no device specification")
            
            # Check time rules
            time_rules = route.time_rules.all()
            for rule in time_rules:
                if rule.hour_from > rule.hour_to:
                    result['errors'].append("Time rule hour_from must be less than or equal to hour_to")
                
                if not rule.day_of_week:
                    result['warnings'].append("Time rule has no days specified")
            
            # Check behavior rules
            behavior_rules = route.behavior_rules.all()
            for rule in behavior_rules:
                if rule.min_count < 1:
                    result['errors'].append("Behavior rule min_count must be at least 1")
                
                if rule.window_days < 1 or rule.window_days > 365:
                    result['errors'].append("Behavior rule window_days must be between 1 and 365")
            
        except Exception as e:
            logger.error(f"Error validating targeting rules: {e}")
            result['errors'].append(f"Targeting rules validation error: {str(e)}")
    
    def _check_logical_issues(self, route: OfferRoute, result: Dict[str, Any]):
        """Check for logical issues in route configuration."""
        try:
            # Check for conflicting conditions
            conditions = route.conditions.all()
            if conditions.count() > 1:
                # Check for duplicate field names with different operators
                field_names = list(conditions.values_list('field_name', flat=True))
                if len(field_names) != len(set(field_names)):
                    result['warnings'].append("Multiple conditions on same field may conflict")
            
            # Check for impossible combinations
            geo_rules = route.geo_rules.all()
            device_rules = route.device_rules.all()
            
            # Check if all geo rules are exclusions
            if geo_rules.exists() and all(not rule.is_include for rule in geo_rules):
                result['warnings'].append("All geographic rules are exclusions - route may never match")
            
            # Check if all device rules are exclusions
            if device_rules.exists() and all(not rule.is_include for rule in device_rules):
                result['warnings'].append("All device rules are exclusions - route may never match")
            
        except Exception as e:
            logger.error(f"Error checking logical issues: {e}")
            result['errors'].append(f"Logical issue check failed: {str(e)}")
    
    def _generate_recommendations(self, route: OfferRoute, result: Dict[str, Any]):
        """Generate recommendations for route improvement."""
        try:
            # Performance recommendations
            if route.max_offers > 50:
                result['recommendations'].append("Consider reducing max_offers for better performance")
            
            # Targeting recommendations
            conditions = route.conditions.all()
            if conditions.count() == 0:
                result['recommendations'].append("Add conditions to target specific user segments")
            elif conditions.count() > 10:
                result['recommendations'].append("Consider simplifying conditions for better maintainability")
            
            # Priority recommendations
            if route.priority == 5:  # Default priority
                result['recommendations'].append("Set a specific priority for predictable routing order")
            
            # Action recommendations
            actions = route.actions.all()
            if actions.count() == 0:
                result['recommendations'].append("Add actions to define what happens when route matches")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
    
    def test_route_with_user(self, route: OfferRoute, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test route with a specific user and context."""
        try:
            test_result = {
                'route_id': route.id,
                'user_id': user.id,
                'matches': False,
                'condition_results': [],
                'targeting_results': {},
                'errors': [],
                'warnings': []
            }
            
            # Get user segment info
            from ..utils import get_user_segment_info
            user_segment = get_user_segment_info(user.id)
            
            # Test conditions
            for condition in route.conditions.all():
                condition_result = self._test_condition(condition, user, context)
                test_result['condition_results'].append(condition_result)
            
            # Test targeting rules
            if self.targeting_service:
                targeting_matches = self.targeting_service.matches_route(route, user, user_segment, context)
                test_result['matches'] = targeting_matches
                
                # Get detailed targeting results
                test_result['targeting_results'] = self.targeting_service.get_matching_rules(route, user, user_segment, context)
            else:
                test_result['warnings'].append("Targeting service not available")
            
            return test_result
            
        except Exception as e:
            logger.error(f"Error testing route with user: {e}")
            return {
                'route_id': route.id,
                'user_id': user.id,
                'matches': False,
                'condition_results': [],
                'targeting_results': {},
                'errors': [str(e)],
                'warnings': []
            }
    
    def _test_condition(self, condition: RouteCondition, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single condition."""
        try:
            result = {
                'condition_id': condition.id,
                'field_name': condition.field_name,
                'operator': condition.operator,
                'value': condition.value,
                'matches': False,
                'actual_value': None,
                'error': None
            }
            
            # Get actual value
            actual_value = self._get_condition_value(condition.field_name, user, context)
            result['actual_value'] = actual_value
            
            # Evaluate condition
            if actual_value is not None:
                result['matches'] = self._evaluate_condition_operator(condition.operator, actual_value, condition.value)
            else:
                result['error'] = f"Could not get value for field '{condition.field_name}'"
            
            return result
            
        except Exception as e:
            return {
                'condition_id': condition.id,
                'field_name': condition.field_name,
                'operator': condition.operator,
                'value': condition.value,
                'matches': False,
                'actual_value': None,
                'error': str(e)
            }
    
    def _get_condition_value(self, field_name: str, user: User, context: Dict[str, Any]) -> Any:
        """Get actual value for a condition field."""
        try:
            # User fields
            if field_name == 'user_id':
                return user.id
            elif field_name == 'user_tier':
                return getattr(user, 'tier', 'basic')
            elif field_name == 'user_email':
                return user.email
            
            # Context fields
            if field_name in context:
                return context[field_name]
            
            # User profile fields
            if hasattr(user, field_name):
                return getattr(user, field_name)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting condition value: {e}")
            return None
    
    def _evaluate_condition_operator(self, operator: str, actual_value: Any, expected_value: Any) -> bool:
        """Evaluate condition operator."""
        try:
            if operator == 'equals':
                return str(actual_value) == str(expected_value)
            elif operator == 'not_equals':
                return str(actual_value) != str(expected_value)
            elif operator == 'contains':
                return str(expected_value) in str(actual_value)
            elif operator == 'not_contains':
                return str(expected_value) not in str(actual_value)
            elif operator == 'starts_with':
                return str(actual_value).startswith(str(expected_value))
            elif operator == 'ends_with':
                return str(actual_value).endswith(str(expected_value))
            elif operator == 'greater_than':
                try:
                    return float(actual_value) > float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif operator == 'less_than':
                try:
                    return float(actual_value) < float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif operator == 'greater_equal':
                try:
                    return float(actual_value) >= float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif operator == 'less_equal':
                try:
                    return float(actual_value) <= float(expected_value)
                except (ValueError, TypeError):
                    return False
            elif operator == 'in':
                return str(actual_value) in [str(v) for v in expected_value]
            elif operator == 'not_in':
                return str(actual_value) not in [str(v) for v in expected_value]
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating condition operator: {e}")
            return False
    
    def validate_all_routes(self, tenant_id: int) -> Dict[str, Any]:
        """Validate all routes for a tenant."""
        try:
            from ..models import OfferRoute
            
            routes = OfferRoute.objects.filter(tenant_id=tenant_id)
            
            validation_results = {
                'total_routes': routes.count(),
                'valid_routes': 0,
                'invalid_routes': 0,
                'route_results': [],
                'summary': {
                    'total_errors': 0,
                    'total_warnings': 0,
                    'total_recommendations': 0
                }
            }
            
            for route in routes:
                route_validation = self.validate_route(route)
                validation_results['route_results'].append({
                    'route_id': route.id,
                    'route_name': route.name,
                    'is_valid': route_validation['is_valid'],
                    'error_count': len(route_validation['errors']),
                    'warning_count': len(route_validation['warnings']),
                    'recommendation_count': len(route_validation['recommendations'])
                })
                
                if route_validation['is_valid']:
                    validation_results['valid_routes'] += 1
                else:
                    validation_results['invalid_routes'] += 1
                
                validation_results['summary']['total_errors'] += len(route_validation['errors'])
                validation_results['summary']['total_warnings'] += len(route_validation['warnings'])
                validation_results['summary']['total_recommendations'] += len(route_validation['recommendations'])
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating all routes: {e}")
            return {
                'total_routes': 0,
                'valid_routes': 0,
                'invalid_routes': 0,
                'route_results': [],
                'summary': {'total_errors': 1, 'total_warnings': 0, 'total_recommendations': 0},
                'error': str(e)
            }


# Singleton instance
route_evaluator = RouteEvaluator()
