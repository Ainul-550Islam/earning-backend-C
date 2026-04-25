"""
Evaluator Viewsets for Offer Routing System

This module contains viewsets for route evaluation,
testing, and validation operations.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ..services.evaluator import route_evaluator
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError

User = get_user_model()


class RouteEvaluatorViewSet(viewsets.ViewSet):
    """
    ViewSet for route evaluation operations.
    
    Provides endpoints for validating routes,
    testing configurations, and evaluating performance.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    @action(detail=False, methods=['post'])
    def validate_route(self, request):
        """Validate a specific route configuration."""
        try:
            route_id = request.data.get('route_id')
            
            if not route_id:
                return Response({
                    'success': False,
                    'error': 'route_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify route belongs to tenant
            from ..models import OfferRoute
            try:
                route = OfferRoute.objects.get(id=route_id)
                if route.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'Route not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except OfferRoute.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Route not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate route
            validation_result = route_evaluator.validate_route(route)
            
            return Response({
                'success': True,
                'route_id': route_id,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def test_route_with_user(self, request):
        """Test route with a specific user."""
        try:
            route_id = request.data.get('route_id')
            user_id = request.data.get('user_id')
            context = request.data.get('context', {})
            
            if not route_id or not user_id:
                return Response({
                    'success': False,
                    'error': 'route_id and user_id are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify route belongs to tenant
            from ..models import OfferRoute
            try:
                route = OfferRoute.objects.get(id=route_id)
                if route.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'Route not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except OfferRoute.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Route not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Verify user belongs to tenant
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test route
            test_result = route_evaluator.test_route_with_user(route, user, context)
            
            return Response({
                'success': True,
                'route_id': route_id,
                'user_id': user_id,
                'context': context,
                'test_result': test_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def validate_all_routes(self, request):
        """Validate all routes for the tenant."""
        try:
            validation_results = route_evaluator.validate_all_routes(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'validation_results': validation_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def batch_test_routes(self, request):
        """Test multiple routes with multiple users."""
        try:
            route_ids = request.data.get('route_ids', [])
            user_ids = request.data.get('user_ids', [])
            context = request.data.get('context', {})
            
            if not route_ids or not user_ids:
                return Response({
                    'success': False,
                    'error': 'route_ids and user_ids are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify routes belong to tenant
            from ..models import OfferRoute
            valid_routes = []
            for route_id in route_ids:
                try:
                    route = OfferRoute.objects.get(id=route_id)
                    if route.tenant == request.user:
                        valid_routes.append(route)
                except OfferRoute.DoesNotExist:
                    continue
            
            # Verify users belong to tenant
            valid_users = []
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)
                    if user.tenant == request.user:
                        valid_users.append(user)
                except User.DoesNotExist:
                    continue
            
            if not valid_routes or not valid_users:
                return Response({
                    'success': False,
                    'error': 'No valid routes or users found'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Test all combinations
            test_results = []
            for route in valid_routes:
                for user in valid_users:
                    try:
                        test_result = route_evaluator.test_route_with_user(route, user, context)
                        test_results.append({
                            'route_id': route.id,
                            'route_name': route.name,
                            'user_id': user.id,
                            'test_result': test_result
                        })
                    except Exception as e:
                        test_results.append({
                            'route_id': route.id,
                            'route_name': route.name,
                            'user_id': user.id,
                            'error': str(e)
                        })
            
            return Response({
                'success': True,
                'total_routes': len(valid_routes),
                'total_users': len(valid_users),
                'total_tests': len(test_results),
                'test_results': test_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def evaluation_summary(self, request):
        """Get evaluation summary for all routes."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get route evaluation statistics
            from ..models import OfferRoute
            routes = OfferRoute.objects.filter(tenant=request.user)
            
            summary = {
                'total_routes': routes.count(),
                'active_routes': routes.filter(is_active=True).count(),
                'inactive_routes': routes.filter(is_active=False).count(),
                'routes_with_conditions': routes.filter(conditions__isnull=False).distinct().count(),
                'routes_with_actions': routes.filter(actions__isnull=False).distinct().count(),
                'routes_with_targeting': routes.filter(
                    Q(geo_rules__isnull=False) |
                    Q(device_rules__isnull=False) |
                    Q(segment_rules__isnull=False) |
                    Q(time_rules__isnull=False) |
                    Q(behavior_rules__isnull=False)
                ).distinct().count()
            }
            
            # Get priority distribution
            priority_distribution = routes.values('priority').annotate(
                count=Count('id')
            ).order_by('priority')
            
            # Get recent validation status
            validation_status = {
                'validated_routes': 0,
                'invalid_routes': 0,
                'routes_with_warnings': 0
            }
            
            for route in routes:
                try:
                    validation_result = route_evaluator.validate_route(route)
                    if not validation_result['is_valid']:
                        validation_status['invalid_routes'] += 1
                    elif validation_result['warnings']:
                        validation_status['routes_with_warnings'] += 1
                    else:
                        validation_status['validated_routes'] += 1
                except:
                    pass
            
            return Response({
                'success': True,
                'summary': summary,
                'priority_distribution': list(priority_distribution),
                'validation_status': validation_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def simulate_route_conflicts(self, request):
        """Simulate potential route conflicts."""
        try:
            from ..models import OfferRoute
            routes = OfferRoute.objects.filter(tenant=request.user, is_active=True)
            
            conflicts = []
            
            # Check for overlapping targeting rules
            for i, route1 in enumerate(routes):
                for route2 in routes[i+1:]:
                    conflict = self._check_route_conflicts(route1, route2)
                    if conflict:
                        conflicts.append(conflict)
            
            return Response({
                'success': True,
                'total_routes': routes.count(),
                'conflicts_found': len(conflicts),
                'conflicts': conflicts
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _check_route_conflicts(self, route1, route2):
        """Check for conflicts between two routes."""
        try:
            conflicts = []
            
            # Check priority conflicts
            if route1.priority == route2.priority:
                conflicts.append({
                    'type': 'priority_conflict',
                    'message': 'Both routes have the same priority',
                    'severity': 'medium'
                })
            
            # Check condition overlaps
            conditions1 = set(route1.conditions.values_list('field_name', flat=True))
            conditions2 = set(route2.conditions.values_list('field_name', flat=True))
            
            overlapping_conditions = conditions1.intersection(conditions2)
            if overlapping_conditions:
                conflicts.append({
                    'type': 'condition_overlap',
                    'message': f'Overlapping conditions: {list(overlapping_conditions)}',
                    'severity': 'low'
                })
            
            # Check targeting rule overlaps
            geo_overlap = self._check_targeting_overlap(route1.geo_rules.all(), route2.geo_rules.all())
            if geo_overlap:
                conflicts.append(geo_overlap)
            
            if conflicts:
                return {
                    'route1_id': route1.id,
                    'route1_name': route1.name,
                    'route2_id': route2.id,
                    'route2_name': route2.name,
                    'conflicts': conflicts
                }
            
            return None
            
        except Exception as e:
            return None
    
    def _check_targeting_overlap(self, rules1, rules2):
        """Check overlap between targeting rules."""
        try:
            # Simple overlap detection
            includes1 = rules1.filter(is_include=True)
            includes2 = rules2.filter(is_include=True)
            
            if includes1.exists() and includes2.exists():
                return {
                    'type': 'targeting_overlap',
                    'message': 'Both routes have include targeting rules',
                    'severity': 'medium'
                }
            
            return None
            
        except Exception as e:
            return None
    
    @action(detail=False, methods=['post'])
    def generate_route_recommendations(self, request):
        """Generate recommendations for route optimization."""
        try:
            from ..models import OfferRoute
            routes = OfferRoute.objects.filter(tenant=request.user)
            
            recommendations = []
            
            for route in routes:
                route_recommendations = []
                
                # Check if route has no conditions
                if not route.conditions.exists():
                    route_recommendations.append({
                        'type': 'add_conditions',
                        'message': 'Add conditions to target specific user segments',
                        'priority': 'high'
                    })
                
                # Check if route has no actions
                if not route.actions.exists():
                    route_recommendations.append({
                        'type': 'add_actions',
                        'message': 'Add actions to define what happens when route matches',
                        'priority': 'high'
                    })
                
                # Check if route has default priority
                if route.priority == 5:
                    route_recommendations.append({
                        'type': 'set_priority',
                        'message': 'Set a specific priority for predictable routing',
                        'priority': 'medium'
                    })
                
                # Check if route has too many conditions
                condition_count = route.conditions.count()
                if condition_count > 10:
                    route_recommendations.append({
                        'type': 'simplify_conditions',
                        'message': f'Consider simplifying conditions ({condition_count} conditions)',
                        'priority': 'low'
                    })
                
                # Check if route has no targeting rules
                has_targeting = (
                    route.geo_rules.exists() or
                    route.device_rules.exists() or
                    route.segment_rules.exists() or
                    route.time_rules.exists() or
                    route.behavior_rules.exists()
                )
                
                if not has_targeting:
                    route_recommendations.append({
                        'type': 'add_targeting',
                        'message': 'Add targeting rules for better user segmentation',
                        'priority': 'medium'
                    })
                
                if route_recommendations:
                    recommendations.append({
                        'route_id': route.id,
                        'route_name': route.name,
                        'recommendations': route_recommendations
                    })
            
            return Response({
                'success': True,
                'total_routes': routes.count(),
                'routes_with_recommendations': len(recommendations),
                'recommendations': recommendations
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def export_evaluation_report(self, request):
        """Export comprehensive evaluation report."""
        try:
            # Get all validation results
            validation_results = route_evaluator.validate_all_routes(tenant_id=request.user.id)
            
            # Get evaluation summary
            evaluation_summary = self._get_evaluation_summary()
            
            # Get route recommendations
            from ..models import OfferRoute
            routes = OfferRoute.objects.filter(tenant=request.user)
            
            recommendations = []
            for route in routes:
                validation_result = route_evaluator.validate_route(route)
                if not validation_result['is_valid'] or validation_result['warnings']:
                    recommendations.append({
                        'route_id': route.id,
                        'route_name': route.name,
                        'is_valid': validation_result['is_valid'],
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings'],
                        'recommendations': validation_result['recommendations']
                    })
            
            # Generate report
            report = {
                'generated_at': timezone.now().isoformat(),
                'tenant_id': request.user.id,
                'validation_results': validation_results,
                'evaluation_summary': evaluation_summary,
                'route_recommendations': recommendations,
                'summary': {
                    'total_routes': validation_results['total_routes'],
                    'valid_routes': validation_results['valid_routes'],
                    'invalid_routes': validation_results['invalid_routes'],
                    'routes_with_recommendations': len(recommendations),
                    'total_errors': validation_results['summary']['total_errors'],
                    'total_warnings': validation_results['summary']['total_warnings']
                }
            }
            
            return Response({
                'success': True,
                'report': report
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_evaluation_summary(self):
        """Get evaluation summary statistics."""
        try:
            from datetime import timedelta
            from ..models import OfferRoute
            
            cutoff_date = timezone.now() - timedelta(days=30)
            routes = OfferRoute.objects.filter(tenant=self.request.user)
            
            summary = {
                'total_routes': routes.count(),
                'active_routes': routes.filter(is_active=True).count(),
                'routes_with_conditions': routes.filter(conditions__isnull=False).distinct().count(),
                'routes_with_actions': routes.filter(actions__isnull=False).distinct().count(),
                'avg_conditions_per_route': 0,
                'avg_priority': 0,
                'priority_distribution': {},
                'routes_updated_recently': routes.filter(updated_at__gte=cutoff_date).count()
            }
            
            if routes.exists():
                # Calculate averages
                condition_counts = [route.conditions.count() for route in routes]
                priorities = [route.priority for route in routes]
                
                summary['avg_conditions_per_route'] = sum(condition_counts) / len(condition_counts)
                summary['avg_priority'] = sum(priorities) / len(priorities)
                
                # Priority distribution
                for priority in range(1, 11):
                    summary['priority_distribution'][priority] = routes.filter(priority=priority).count()
            
            return summary
            
        except Exception as e:
            return {}
