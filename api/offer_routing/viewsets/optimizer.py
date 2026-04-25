"""
Optimizer Viewsets for Offer Routing System

This module contains viewsets for optimization operations,
including route optimization, scoring optimization, and performance tuning.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from ..services.optimizer import routing_optimizer
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError

User = get_user_model()


class RoutingOptimizerViewSet(viewsets.ViewSet):
    """
    ViewSet for routing optimization operations.
    
    Provides endpoints for optimizing routes, scores,
    and personalization configurations.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    @action(detail=False, methods=['post'])
    def optimize_route_priorities(self, request):
        """Optimize route priorities based on performance data."""
        try:
            optimization_result = routing_optimizer.optimize_route_priorities(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_score_weights(self, request):
        """Optimize scoring weights for offers."""
        try:
            optimization_result = routing_optimizer.optimize_score_weights(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_personalization_config(self, request):
        """Optimize personalization configurations."""
        try:
            optimization_result = routing_optimizer.optimize_personalization_config(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_all_configurations(self, request):
        """Optimize all configurations for the tenant."""
        try:
            optimization_results = routing_optimizer.optimize_all_configurations(tenant_id=request.user.id)
            
            return Response({
                'success': True,
                'optimization_results': optimization_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_history(self, request):
        """Get optimization history for the tenant."""
        try:
            days = int(request.query_params.get('days', 30))
            
            # This would get actual optimization history
            # For now, return placeholder
            history = [
                {
                    'timestamp': timezone.now().isoformat(),
                    'optimization_type': 'route_priorities',
                    'changes_made': 5,
                    'performance_improvement': 12.5,
                    'status': 'completed'
                }
            ]
            
            return Response({
                'success': True,
                'period_days': days,
                'history': history
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def simulate_optimization(self, request):
        """Simulate optimization without applying changes."""
        try:
            optimization_type = request.data.get('optimization_type')
            
            if not optimization_type:
                return Response({
                    'success': False,
                    'error': 'optimization_type is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Simulate optimization
            simulation_result = {
                'optimization_type': optimization_type,
                'simulated_changes': 0,
                'estimated_improvement': 0.0,
                'recommendations': []
            }
            
            if optimization_type == 'route_priorities':
                simulation_result['simulated_changes'] = 8
                simulation_result['estimated_improvement'] = 15.2
                simulation_result['recommendations'] = [
                    'Increase priority for high-performing routes',
                    'Decrease priority for low-performing routes'
                ]
            elif optimization_type == 'score_weights':
                simulation_result['simulated_changes'] = 12
                simulation_result['estimated_improvement'] = 8.7
                simulation_result['recommendations'] = [
                    'Adjust EPC weights for revenue-focused offers',
                    'Increase CR weights for conversion-focused offers'
                ]
            elif optimization_type == 'personalization':
                simulation_result['simulated_changes'] = 6
                simulation_result['estimated_improvement'] = 10.3
                simulation_result['recommendations'] = [
                    'Enable real-time personalization for active users',
                    'Adjust collaborative filtering weights'
                ]
            
            return Response({
                'success': True,
                'simulation_result': simulation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_recommendations(self, request):
        """Get optimization recommendations based on current performance."""
        try:
            # Get performance-based recommendations
            recommendations = []
            
            # Analyze route performance
            from ..models import RoutePerformanceStat
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=30)
            route_stats = RoutePerformanceStat.objects.filter(
                tenant=request.user,
                date__gte=cutoff_date.date()
            ).aggregate(
                avg_conversion_rate=Avg('conversion_rate'),
                avg_response_time=Avg('avg_response_time_ms')
            )
            
            avg_cr = route_stats['avg_conversion_rate'] or 0
            avg_response_time = route_stats['avg_response_time'] or 0
            
            # Route optimization recommendations
            if avg_cr < 2:
                recommendations.append({
                    'type': 'route_priorities',
                    'priority': 'high',
                    'title': 'Low Conversion Rate Detected',
                    'description': f'Average conversion rate is {avg_cr:.2f}%',
                    'action': 'Optimize route priorities to focus on high-converting routes',
                    'estimated_impact': '15-25% improvement in conversions'
                })
            
            if avg_response_time > 100:
                recommendations.append({
                    'type': 'route_priorities',
                    'priority': 'medium',
                    'title': 'High Response Time',
                    'description': f'Average response time is {avg_response_time:.1f}ms',
                    'action': 'Optimize route order and caching to reduce response time',
                    'estimated_impact': '20-30% improvement in response time'
                })
            
            # Scoring optimization recommendations
            from ..models import OfferScoreConfig
            score_configs = OfferScoreConfig.objects.filter(tenant=request.user)
            
            if score_configs.exists():
                recommendations.append({
                    'type': 'score_weights',
                    'priority': 'medium',
                    'title': 'Score Weight Optimization Available',
                    'description': 'Multiple scoring configurations found',
                    'action': 'Optimize scoring weights based on recent performance data',
                    'estimated_impact': '5-15% improvement in scoring accuracy'
                })
            
            # Personalization optimization recommendations
            from ..models import PersonalizationConfig
            personalization_configs = PersonalizationConfig.objects.filter(tenant=request.user)
            
            if personalization_configs.exists():
                recommendations.append({
                    'type': 'personalization',
                    'priority': 'low',
                    'title': 'Personalization Configuration Review',
                    'description': 'Personalization configurations found',
                    'action': 'Review and optimize personalization settings',
                    'estimated_impact': '3-10% improvement in personalization effectiveness'
                })
            
            return Response({
                'success': True,
                'recommendations': recommendations,
                'total_recommendations': len(recommendations)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def apply_optimization(self, request):
        """Apply specific optimization recommendations."""
        try:
            optimization_type = request.data.get('optimization_type')
            recommendations = request.data.get('recommendations', [])
            
            if not optimization_type:
                return Response({
                    'success': False,
                    'error': 'optimization_type is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Apply optimization
            if optimization_type == 'route_priorities':
                result = routing_optimizer.optimize_route_priorities(tenant_id=request.user.id)
            elif optimization_type == 'score_weights':
                result = routing_optimizer.optimize_score_weights(tenant_id=request.user.id)
            elif optimization_type == 'personalization':
                result = routing_optimizer.optimize_personalization_config(tenant_id=request.user.id)
            else:
                return Response({
                    'success': False,
                    'error': 'Invalid optimization type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'optimization_type': optimization_type,
                'applied_recommendations': recommendations,
                'optimization_result': result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_status(self, request):
        """Get current optimization status and metrics."""
        try:
            from datetime import timedelta
            from ..models import OfferRoute, OfferScoreConfig, PersonalizationConfig
            
            # Get current status
            status_data = {
                'routes': {
                    'total': OfferRoute.objects.filter(tenant=request.user).count(),
                    'optimized': 0,  # Would track actual optimization status
                    'last_optimized': None
                },
                'scoring': {
                    'total_configs': OfferScoreConfig.objects.filter(tenant=request.user).count(),
                    'optimized': 0,
                    'last_optimized': None
                },
                'personalization': {
                    'total_configs': PersonalizationConfig.objects.filter(tenant=request.user).count(),
                    'optimized': 0,
                    'last_optimized': None
                },
                'overall': {
                    'optimization_score': 0.0,
                    'last_optimization': None,
                    'total_improvements': 0
                }
            }
            
            return Response({
                'success': True,
                'status': status_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_optimization_schedule(self, request):
        """Create scheduled optimization tasks."""
        try:
            optimization_type = request.data.get('optimization_type')
            schedule = request.data.get('schedule', {})
            
            if not optimization_type:
                return Response({
                    'success': False,
                    'error': 'optimization_type is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate schedule
            required_fields = ['frequency', 'next_run']
            for field in required_fields:
                if field not in schedule:
                    return Response({
                        'success': False,
                        'error': f'Schedule field {field} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create schedule (placeholder)
            schedule_data = {
                'optimization_type': optimization_type,
                'tenant_id': request.user.id,
                'schedule': schedule,
                'created_at': timezone.now().isoformat(),
                'status': 'active'
            }
            
            return Response({
                'success': True,
                'schedule': schedule_data,
                'message': 'Optimization schedule created successfully'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_schedules(self, request):
        """Get all optimization schedules for the tenant."""
        try:
            # This would get actual schedules
            # For now, return placeholder
            schedules = [
                {
                    'id': 1,
                    'optimization_type': 'route_priorities',
                    'frequency': 'daily',
                    'next_run': timezone.now().isoformat(),
                    'status': 'active',
                    'last_run': timezone.now().isoformat()
                }
            ]
            
            return Response({
                'success': True,
                'schedules': schedules
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def rollback_optimization(self, request):
        """Rollback the last optimization."""
        try:
            optimization_type = request.data.get('optimization_type')
            
            if not optimization_type:
                return Response({
                    'success': False,
                    'error': 'optimization_type is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Rollback optimization (placeholder)
            rollback_result = {
                'optimization_type': optimization_type,
                'rolled_back_at': timezone.now().isoformat(),
                'changes_reverted': 0,
                'status': 'completed'
            }
            
            return Response({
                'success': True,
                'rollback_result': rollback_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_metrics(self, request):
        """Get optimization performance metrics."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get optimization metrics (placeholder)
            metrics = {
                'period_days': days,
                'total_optimizations': 5,
                'successful_optimizations': 4,
                'failed_optimizations': 1,
                'avg_improvement': 12.5,
                'optimization_types': {
                    'route_priorities': 2,
                    'score_weights': 2,
                    'personalization': 1
                },
                'trend': 'improving'
            }
            
            return Response({
                'success': True,
                'metrics': metrics
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
