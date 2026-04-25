"""
A/B Test Viewsets for Offer Routing System

This module contains viewsets for managing A/B testing,
including test creation, assignment, and result analysis.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from ..models import (
    RoutingABTest, ABTestAssignment, ABTestResult
)
from ..services.ab_test import ab_test_service
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, ABTestError

User = get_user_model()


class RoutingABTestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing routing A/B tests.
    
    Provides CRUD operations for A/B tests
    with testing, evaluation, and result analysis capabilities.
    """
    
    queryset = RoutingABTest.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter tests by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set tenant and created_by when creating test."""
        serializer.save(
            tenant=self.request.user,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def start_test(self, request, pk=None):
        """Start an A/B test."""
        try:
            test = self.get_object()
            
            if test.is_active:
                return Response({
                    'success': False,
                    'error': 'Test is already active'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if test.ended_at:
                return Response({
                    'success': False,
                    'error': 'Test has already ended'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Start test
            success = ab_test_service.start_test(test.id)
            
            if success:
                test.refresh_from_db()
                return Response({
                    'success': True,
                    'test_id': test.id,
                    'test_name': test.name,
                    'started_at': test.started_at,
                    'is_active': test.is_active
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to start test'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def stop_test(self, request, pk=None):
        """Stop an A/B test."""
        try:
            test = self.get_object()
            
            if not test.is_active:
                return Response({
                    'success': False,
                    'error': 'Test is not active'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Stop test
            success = ab_test_service.stop_test(test.id)
            
            if success:
                test.refresh_from_db()
                return Response({
                    'success': True,
                    'test_id': test.id,
                    'test_name': test.name,
                    'ended_at': test.ended_at,
                    'is_active': test.is_active,
                    'winner': test.winner,
                    'confidence': test.confidence
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to stop test'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_results(self, request, pk=None):
        """Get detailed results for this A/B test."""
        try:
            test = self.get_object()
            
            results = ab_test_service.get_test_results(test.id)
            
            if results:
                return Response({
                    'success': True,
                    'test_id': test.id,
                    'test_name': test.name,
                    'results': results
                })
            else:
                return Response({
                    'success': False,
                    'error': 'No results found for this test'
                }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def evaluate_test(self, request, pk=None):
        """Evaluate test for statistical significance."""
        try:
            test = self.get_object()
            
            if not test.is_active:
                return Response({
                    'success': False,
                    'error': 'Test is not active'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Evaluate test
            evaluated_count = ab_test_service.evaluate_active_tests()
            
            # Get updated results
            results = ab_test_service.get_test_results(test.id)
            
            return Response({
                'success': True,
                'test_id': test.id,
                'test_name': test.name,
                'evaluated': True,
                'results': results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def assign_user(self, request, pk=None):
        """Assign a user to this A/B test."""
        try:
            test = self.get_object()
            
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({
                    'success': False,
                    'error': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
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
            
            # Get offer for this test
            offer = test.control_route  # Use control route as representative offer
            
            # Assign user
            assignment = ab_test_service.assign_user_to_test(user, offer)
            
            if assignment:
                return Response({
                    'success': True,
                    'test_id': test.id,
                    'test_name': test.name,
                    'user_id': user_id,
                    'assignment': assignment
                })
            else:
                return Response({
                    'success': False,
                    'error': 'User not eligible for this test'
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def record_event(self, request, pk=None):
        """Record an event for test assignments."""
        try:
            test = self.get_object()
            
            user_id = request.data.get('user_id')
            event_type = request.data.get('event_type')
            event_value = request.data.get('event_value', 0.0)
            
            if not user_id or not event_type:
                return Response({
                    'success': False,
                    'error': 'user_id and event_type are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
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
            
            # Get offer for this test
            offer = test.control_route  # Use control route as representative offer
            
            # Record event
            ab_test_service.record_assignment_event(user, offer, event_type, event_value)
            
            return Response({
                'success': True,
                'test_id': test.id,
                'user_id': user_id,
                'event_type': event_type,
                'event_value': event_value
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_tests(self, request):
        """Get all active A/B tests."""
        try:
            active_tests = self.get_queryset().filter(
                is_active=True,
                started_at__isnull=False,
                ended_at__isnull=True
            )
            
            test_data = []
            for test in active_tests:
                test_data.append({
                    'test_id': test.id,
                    'name': test.name,
                    'description': test.description,
                    'control_route_id': test.control_route.id,
                    'control_route_name': test.control_route.name,
                    'variant_route_id': test.variant_route.id,
                    'variant_route_name': test.variant_route.name,
                    'split_percentage': test.split_percentage,
                    'started_at': test.started_at,
                    'duration_hours': test.duration_hours,
                    'success_metric': test.success_metric
                })
            
            return Response({
                'success': True,
                'active_tests': test_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def evaluate_all_active(self, request):
        """Evaluate all active A/B tests."""
        try:
            evaluated_count = ab_test_service.evaluate_active_tests()
            
            return Response({
                'success': True,
                'evaluated_count': evaluated_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def test_analytics(self, request):
        """Get analytics for A/B tests."""
        try:
            days = int(request.query_params.get('days', 30))
            
            analytics = ab_test_service.get_test_analytics(
                user_id=request.user.id,
                days=days
            )
            
            return Response({
                'success': True,
                'period_days': days,
                'analytics': analytics
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing A/B test assignments.
    
    Provides read-only access to test assignments
    with filtering and analytics capabilities.
    """
    
    queryset = ABTestAssignment.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter assignments by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(test__tenant=self.request.user)
        return queryset.order_by('-assigned_at')
    
    @action(detail=False, methods=['get'])
    def user_assignments(self, request):
        """Get assignments for a specific user."""
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
            
            # Get assignments
            assignments = self.get_queryset().filter(user_id=user_id)
            
            # Apply filters
            test_id = request.query_params.get('test_id')
            if test_id:
                assignments = assignments.filter(test_id=test_id)
            
            variant = request.query_params.get('variant')
            if variant:
                assignments = assignments.filter(variant=variant)
            
            # Serialize
            page = self.paginate_queryset(assignments)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(assignments, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def test_assignments(self, request):
        """Get assignments for a specific test."""
        try:
            test_id = request.query_params.get('test_id')
            if not test_id:
                return Response({
                    'success': False,
                    'error': 'test_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get assignments
            assignments = self.get_queryset().filter(test_id=test_id)
            
            # Get statistics
            stats = assignments.aggregate(
                total_assignments=Count('id'),
                control_assignments=Count('id', filter=Q(variant='control')),
                variant_assignments=Count('id', filter=Q(variant='variant')),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_revenue=Sum('revenue')
            )
            
            # Calculate rates
            if stats['total_assignments'] > 0:
                stats['control_rate'] = (stats['control_assignments'] / stats['total_assignments']) * 100
                stats['variant_rate'] = (stats['variant_assignments'] / stats['total_assignments']) * 100
            else:
                stats['control_rate'] = 0
                stats['variant_rate'] = 0
            
            if stats['total_impressions'] > 0:
                stats['overall_ctr'] = (stats['total_clicks'] / stats['total_impressions']) * 100
                stats['overall_cr'] = (stats['total_conversions'] / stats['total_impressions']) * 100
            else:
                stats['overall_ctr'] = 0
                stats['overall_cr'] = 0
            
            # Serialize
            page = self.paginate_queryset(assignments)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'success': True,
                    'stats': stats,
                    'results': self.get_paginated_response(serializer).data
                })
            else:
                serializer = self.get_serializer(assignments, many=True)
                return Response({
                    'success': True,
                    'stats': stats,
                    'results': serializer.data
                })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def assignment_analytics(self, request):
        """Get analytics for test assignments."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get assignment statistics
            assignments = self.get_queryset().filter(
                assigned_at__gte=cutoff_date
            ).aggregate(
                total_assignments=Count('id'),
                control_assignments=Count('id', filter=Q(variant='control')),
                variant_assignments=Count('id', filter=Q(variant='variant')),
                avg_impressions=Avg('impressions'),
                avg_clicks=Avg('clicks'),
                avg_conversions=Avg('conversions')
            )
            
            # Get distribution by test
            test_distribution = self.get_queryset().filter(
                assigned_at__gte=cutoff_date
            ).values('test__name').annotate(
                count=Count('id'),
                avg_impressions=Avg('impressions'),
                avg_conversions=Avg('conversions')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'assignment_stats': assignments,
                'test_distribution': list(test_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ABTestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing A/B test results.
    
    Provides read-only access to test results
    with filtering and analytics capabilities.
    """
    
    queryset = ABTestResult.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter results by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(test__tenant=self.request.user)
        return queryset.order_by('-analyzed_at')
    
    @action(detail=False, methods=['get'])
    def test_results(self, request):
        """Get results for a specific test."""
        try:
            test_id = request.query_params.get('test_id')
            if not test_id:
                return Response({
                    'success': False,
                    'error': 'test_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get results
            results = self.get_queryset().filter(test_id=test_id)
            
            # Get latest result
            latest_result = results.first()
            
            if latest_result:
                return Response({
                    'success': True,
                    'test_id': test_id,
                    'result': {
                        'result_id': latest_result.id,
                        'control_impressions': latest_result.control_impressions,
                        'control_clicks': latest_result.control_clicks,
                        'control_conversions': latest_result.control_conversions,
                        'control_revenue': float(latest_result.control_revenue),
                        'control_cr': float(latest_result.control_cr),
                        'variant_impressions': latest_result.variant_impressions,
                        'variant_clicks': latest_result.variant_clicks,
                        'variant_conversions': latest_result.variant_conversions,
                        'variant_revenue': float(latest_result.variant_revenue),
                        'variant_cr': float(latest_result.variant_cr),
                        'cr_difference': float(latest_result.cr_difference),
                        'z_score': float(latest_result.z_score),
                        'p_value': float(latest_result.p_value),
                        'is_significant': latest_result.is_significant,
                        'confidence_level': latest_result.confidence_level,
                        'effect_size': float(latest_result.effect_size),
                        'winner': latest_result.winner,
                        'winner_confidence': latest_result.winner_confidence,
                        'analyzed_at': latest_result.analyzed_at.isoformat()
                    }
                })
            else:
                return Response({
                    'success': False,
                    'error': 'No results found for this test'
                }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def significant_results(self, request):
        """Get statistically significant test results."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get significant results
            results = self.get_queryset().filter(
                analyzed_at__gte=cutoff_date,
                is_significant=True
            ).order_by('-winner_confidence')
            
            result_data = []
            for result in results:
                result_data.append({
                    'result_id': result.id,
                    'test_id': result.test.id,
                    'test_name': result.test.name,
                    'winner': result.winner,
                    'winner_confidence': result.winner_confidence,
                    'p_value': result.p_value,
                    'effect_size': result.effect_size,
                    'cr_difference': result.cr_difference,
                    'analyzed_at': result.analyzed_at.isoformat()
                })
            
            return Response({
                'success': True,
                'period_days': days,
                'significant_results': result_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def result_analytics(self, request):
        """Get analytics for test results."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get result statistics
            results = self.get_queryset().filter(
                analyzed_at__gte=cutoff_date
            ).aggregate(
                total_results=Count('id'),
                significant_results=Count('id', filter=Q(is_significant=True)),
                avg_confidence=Avg('winner_confidence'),
                avg_effect_size=Avg('effect_size'),
                avg_p_value=Avg('p_value')
            )
            
            # Get winner distribution
            winner_distribution = self.get_queryset().filter(
                analyzed_at__gte=cutoff_date,
                winner__isnull=False
            ).values('winner').annotate(
                count=Count('id'),
                avg_confidence=Avg('winner_confidence')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'result_stats': results,
                'winner_distribution': list(winner_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
