"""evaluator service package - wraps services/core/RouteEvaluator."""

import logging
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class RouteEvaluator:
    """
    Facade that adapts services/core/RouteEvaluator for the viewsets.

    Methods exposed:
      validate_route(route)
      test_route_with_user(route, user, context)
      validate_all_routes(tenant_id)
      evaluate_route(route, user, context)
      parse_condition_value(value_str, field_type)
      validate_condition_config(condition_data)
    """

    def __init__(self):
        self._core = None

    def _get_core(self):
        """Lazy-load core evaluator."""
        if self._core is None:
            try:
                from ..core.RouteEvaluator import RouteEvaluator as CoreEvaluator
                self._core = CoreEvaluator()
            except Exception as e:
                logger.error(f"Could not load core RouteEvaluator: {e}")
        return self._core

    def evaluate_route(self, route, user=None, context=None):
        """Evaluate a route against user and context."""
        core = self._get_core()
        return core.evaluate_route(route, user, context or {}) if core else False

    def validate_route(self, route) -> dict:
        """Validate a route configuration."""
        errors, warnings, recommendations = [], [], []
        try:
            if not getattr(route, 'name', None):
                errors.append("Route must have a name.")
            if not (1 <= getattr(route, 'priority', 0) <= 10):
                warnings.append("Priority should be between 1 and 10.")
            if not route.conditions.filter(is_active=True).exists():
                warnings.append("Route has no active conditions.")
            if not route.actions.filter(is_active=True).exists():
                recommendations.append("Add at least one active action.")
        except Exception as e:
            errors.append(f"Validation exception: {e}")
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'recommendations': recommendations,
            'checked_at': timezone.now().isoformat(),
        }

    def test_route_with_user(self, route, user, context: dict) -> dict:
        """Run a full route evaluation for a given user and context."""
        result = {
            'matched': False, 'actions_applied': [], 'priority': None,
            'evaluation_stats': {}, 'tested_at': timezone.now().isoformat(),
        }
        try:
            core = self._get_core()
            if core is None:
                result['error'] = 'Core evaluator unavailable'
                return result
            matched = core.evaluate_route(route, user, context or {})
            result['matched'] = matched
            if matched:
                actions = core.evaluate_route_actions(route, user, context or {}) if hasattr(core, 'evaluate_route_actions') else []
                result['actions_applied'] = actions if isinstance(actions, list) else []
                result['priority'] = core.get_route_priority(route, user, context or {}) if hasattr(core, 'get_route_priority') else None
            result['evaluation_stats'] = core.get_evaluation_stats() if hasattr(core, 'get_evaluation_stats') else {}
        except Exception as e:
            result['error'] = str(e)
        return result

    def validate_all_routes(self, tenant_id: int) -> dict:
        """Validate every route for a tenant."""
        from ...models import OfferRoute
        total = valid = invalid = total_errors = total_warnings = 0
        route_results = []
        try:
            routes = OfferRoute.objects.filter(tenant_id=tenant_id)
            total = routes.count()
            for route in routes:
                vr = self.validate_route(route)
                route_results.append({
                    'route_id': route.id, 'route_name': route.name,
                    'is_valid': vr['is_valid'], 'errors': vr['errors'],
                    'warnings': vr['warnings'], 'recommendations': vr['recommendations'],
                })
                if vr['is_valid']:
                    valid += 1
                else:
                    invalid += 1
                total_errors += len(vr['errors'])
                total_warnings += len(vr['warnings'])
        except Exception as e:
            logger.error(f"validate_all_routes error: {e}")
        return {
            'total_routes': total, 'valid_routes': valid, 'invalid_routes': invalid,
            'route_results': route_results,
            'summary': {'total_errors': total_errors, 'total_warnings': total_warnings},
            'validated_at': timezone.now().isoformat(),
        }

    def parse_condition_value(self, value_str, field_type='string'):
        """Public alias of _parse_condition_value."""
        core = self._get_core()
        return core._parse_condition_value(value_str, field_type) if (core and hasattr(core, '_parse_condition_value')) else value_str

    def validate_condition_config(self, condition_data) -> dict:
        """Validate a condition configuration dict."""
        errors = []
        if not condition_data.get('field_name'):
            errors.append('field_name required')
        if not condition_data.get('operator'):
            errors.append('operator required')
        return {'is_valid': len(errors) == 0, 'errors': errors}

    def health_check(self) -> dict:
        core = self._get_core()
        return core.health_check() if core and hasattr(core, 'health_check') else {'status': 'degraded'}

    def get_metrics(self) -> dict:
        core = self._get_core()
        return core.get_evaluation_stats() if core and hasattr(core, 'get_evaluation_stats') else {}


# Module-level singleton
try:
    route_evaluator = RouteEvaluator()
except Exception:
    route_evaluator = None
