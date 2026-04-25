"""
Core Viewsets for Offer Routing System

This module contains the main viewsets for routing operations,
including route management, offer routing, and decision tracking.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from ..models import OfferRoute, RoutingDecisionLog
from ..services.core import routing_engine
from ..services.cache import cache_service
from ..permissions import (
    IsAuthenticatedOrReadOnly, CanManageRoutes, CanManageOffers,
    IsOwnerOrReadOnly, HasValidSubscription
)
from ..exceptions import (
    RouteNotFoundError, OfferNotFoundError, ValidationError,
    RoutingTimeoutError, CacheError
)
from ..utils import validate_routing_data, format_routing_response

User = get_user_model()


class OfferRouteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing offer routes.
    
    Provides CRUD operations for routes and additional actions
    for testing, validation, and optimization.
    """
    
    queryset = OfferRoute.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    
    def get_queryset(self):
        """Filter routes by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('priority', 'name')
    
    def perform_create(self, serializer):
        """Set tenant when creating route."""
        serializer.save(tenant=self.request.user)
    
    @action(detail=True, methods=['post'])
    def test_route(self, request, pk=None):
        """Test route with sample user data."""
        try:
            route = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            test_context = request.data.get('context', {})
            
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get test user
            try:
                test_user = User.objects.get(id=test_user_id)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Test user not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test routing
            routing_result = routing_engine.route_offers(
                user_id=test_user_id,
                context=test_context,
                limit=10,
                cache_enabled=False  # Don't use cache for testing
            )
            
            return Response({
                'success': True,
                'route_id': route.id,
                'route_name': route.name,
                'test_user_id': test_user_id,
                'test_context': test_context,
                'routing_result': routing_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def validate_route(self, request, pk=None):
        """Validate route configuration."""
        try:
            route = self.get_object()
            
            from ..services.evaluator import route_evaluator
            validation_result = route_evaluator.validate_route(route)
            
            return Response({
                'success': True,
                'route_id': route.id,
                'validation_result': validation_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def optimize_route(self, request, pk=None):
        """Optimize route configuration."""
        try:
            route = self.get_object()
            
            from ..services.optimizer import routing_optimizer
            optimization_result = routing_optimizer.optimize_route_priorities(
                tenant_id=route.tenant.id
            )
            
            # Find if this route was optimized
            route_change = next(
                (change for change in optimization_result['route_changes'] 
                 if change['route_id'] == route.id),
                None
            )
            
            return Response({
                'success': True,
                'route_id': route.id,
                'optimized': route_change is not None,
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_validate(self, request):
        """Validate all routes for the tenant."""
        try:
            from ..services.evaluator import route_evaluator
            
            validation_results = route_evaluator.validate_all_routes(
                tenant_id=request.user.id
            )
            
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
    def bulk_optimize(self, request):
        """Optimize all routes for the tenant."""
        try:
            from ..services.optimizer import routing_optimizer
            
            optimization_results = routing_optimizer.optimize_all_configurations(
                tenant_id=request.user.id
            )
            
            return Response({
                'success': True,
                'optimization_results': optimization_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def performance_stats(self, request, pk=None):
        """Get performance statistics for this route."""
        try:
            route = self.get_object()
            
            from ..services.analytics import analytics_service
            stats = analytics_service.get_route_analytics(
                route_id=route.id,
                days=request.query_params.get('days', 30)
            )
            
            return Response({
                'success': True,
                'route_id': route.id,
                'stats': stats
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def clone_route(self, request, pk=None):
        """Clone this route with modifications."""
        try:
            original_route = self.get_object()
            
            # Create clone
            clone_name = request.data.get('name', f"{original_route.name} (Clone)")
            clone = OfferRoute.objects.create(
                name=clone_name,
                description=request.data.get('description', f"Clone of {original_route.name}"),
                tenant=original_route.tenant,
                priority=request.data.get('priority', original_route.priority),
                max_offers=request.data.get('max_offers', original_route.max_offers),
                is_active=request.data.get('is_active', False)  # Start inactive
            )
            
            # Clone conditions
            for condition in original_route.conditions.all():
                condition.pk = None
                condition.route = clone
                condition.save()
            
            # Clone actions
            for action in original_route.actions.all():
                action.pk = None
                action.route = clone
                action.save()
            
            # Clone targeting rules
            for geo_rule in original_route.geo_rules.all():
                geo_rule.pk = None
                geo_rule.route = clone
                geo_rule.save()
            
            for device_rule in original_route.device_rules.all():
                device_rule.pk = None
                device_rule.route = clone
                device_rule.save()
            
            for segment_rule in original_route.segment_rules.all():
                segment_rule.pk = None
                segment_rule.route = clone
                segment_rule.save()
            
            for time_rule in original_route.time_rules.all():
                time_rule.pk = None
                time_rule.route = clone
                time_rule.save()
            
            for behavior_rule in original_route.behavior_rules.all():
                behavior_rule.pk = None
                behavior_rule.route = clone
                behavior_rule.save()
            
            return Response({
                'success': True,
                'original_route_id': original_route.id,
                'cloned_route_id': clone.id,
                'cloned_route_name': clone.name
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoutingDecisionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing routing decisions.
    
    Provides read-only access to routing decision logs
    with filtering and analytics capabilities.
    """
    
    queryset = RoutingDecisionLog.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter decisions by user's tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def user_decisions(self, request):
        """Get routing decisions for a specific user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
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
            
            # Get decisions
            decisions = self.queryset.filter(user_id=user_id)
            
            # Apply filters
            days = request.query_params.get('days')
            if days:
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=int(days))
                decisions = decisions.filter(created_at__gte=cutoff_date)
            
            # Serialize
            page = self.paginate_queryset(decisions)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(decisions, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def route_decisions(self, request):
        """Get routing decisions for a specific route."""
        try:
            route_id = request.query_params.get('route_id')
            if not route_id:
                return Response({
                    'success': False,
                    'error': 'route_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify route belongs to tenant
            try:
                from ..models import OfferRoute
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
            
            # Get decisions
            decisions = self.queryset.filter(route_id=route_id)
            
            # Apply filters
            days = request.query_params.get('days')
            if days:
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=int(days))
                decisions = decisions.filter(created_at__gte=cutoff_date)
            
            # Serialize
            page = self.paginate_queryset(decisions)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(decisions, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def analytics_summary(self, request):
        """Get analytics summary for routing decisions."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.analytics import analytics_service
            summary = analytics_service.get_performance_metrics(
                tenant_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'period_days': days,
                'summary': summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_old_decisions(self, request):
        """Clean up old routing decision logs."""
        try:
            retention_days = int(request.data.get('retention_days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=retention_days)
            
            deleted_count = RoutingDecisionLog.objects.filter(
                user__tenant=request.user,
                created_at__lt=cutoff_date
            ).delete()[0]
            
            return Response({
                'success': True,
                'deleted_count': deleted_count,
                'retention_days': retention_days
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminRoutingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin ViewSet for superadmin global statistics.
    
    Provides read-only access to global statistics and system metrics
    for superadmin users to monitor the entire system.
    """
    
    queryset = OfferRoute.objects.none()  # No direct queryset, custom actions only
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = []  # No authentication for admin endpoints
    
    @action(detail=False, methods=['get'])
    def global_stats(self, request):
        """Get global system statistics."""
        try:
            # Get global stats from analytics service
            from ..services.analytics import analytics_service
            
            stats = analytics_service.get_routing_metrics(
                start_date=timezone.now() - timedelta(days=30),
                end_date=timezone.now()
            )
            
            return Response({
                'success': True,
                'global_stats': stats,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def tenant_overview(self, request):
        """Get overview of all tenants."""
        try:
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # Get tenant statistics
            tenants = User.objects.values('tenant_id').annotate(
                user_count=Count('id'),
                active_routes=Count('routes', filter=Q(routes__is_active=True)),
                total_decisions=Count('routingdecisionlog')
            ).order_by('-user_count')
            
            return Response({
                'success': True,
                'tenant_overview': list(tenants),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """Get overall system health status."""
        try:
            from ..services.monitoring import monitoring_service
            
            health_status = monitoring_service.check_system_health()
            
            return Response({
                'success': True,
                'system_health': health_status,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance_metrics(self, request):
        """Get system-wide performance metrics."""
        try:
            from ..services.analytics import analytics_service
            
            # Get performance metrics for last 7 days
            metrics = analytics_service.get_routing_metrics(
                start_date=timezone.now() - timedelta(days=7),
                end_date=timezone.now()
            )
            
            return Response({
                'success': True,
                'performance_metrics': metrics,
                'period_days': 7,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicRoutingViewSet(viewsets.ViewSet):
    """
    Public viewset for external routing requests.
    
    Provides public API endpoints for offer routing without authentication.
    """
    
    permission_classes = []  # No authentication required for public endpoints
    
    @action(detail=False, methods=['post'])
    def route_offers(self, request):
        """
        Public endpoint for routing offers.
        
        This endpoint can be called by external systems
        without authentication using API key.
        """
        try:
            # Validate API key
            api_key = request.META.get('HTTP_X_API_KEY')
            if not api_key:
                return Response({
                    'success': False,
                    'error': 'API key is required'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Validate request data
            validation_result = validate_routing_data(request.data)
            if not validation_result['is_valid']:
                return Response({
                    'success': False,
                    'error': 'Validation failed',
                    'errors': validation_result['errors'],
                    'warnings': validation_result['warnings']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_id = request.data['user_id']
            context = request.data['context']
            limit = request.data.get('limit', 10)
            
            # Route offers
            routing_result = routing_engine.route_offers(
                user_id=user_id,
                context=context,
                limit=limit,
                cache_enabled=True
            )
            
            # Format response
            response = format_routing_response(
                success=routing_result['success'],
                offers=routing_result.get('offers', []),
                metadata=routing_result.get('metadata', {})
            )
            
            return Response(response)
            
        except ValidationError as e:
            return Response({
                'success': False,
                'error': 'Validation error',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except RoutingTimeoutError as e:
            return Response({
                'success': False,
                'error': 'Routing timeout',
                'details': str(e)
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
            
        except CacheError as e:
            return Response({
                'success': False,
                'error': 'Cache error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': 'Internal server error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check endpoint for public API."""
        try:
            # Check system health
            from ..services.monitoring import monitoring_service
            health_status = monitoring_service.check_system_health()
            
            return Response({
                'success': True,
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'system_health': health_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
