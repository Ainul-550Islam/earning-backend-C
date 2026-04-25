"""
Cap Viewsets for Offer Routing System

This module contains viewsets for managing offer caps,
including global caps, user-specific caps, and cap overrides.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from ..models import (
    OfferRoutingCap, UserOfferCap, CapOverride
)
from ..services.cap import cap_service
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, CapExceededError

User = get_user_model()


class OfferRoutingCapViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing global offer caps.
    
    Provides CRUD operations for global offer caps
    with analytics and management capabilities.
    """
    
    queryset = OfferRoutingCap.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter caps by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('offer__name', 'cap_type')
    
    @action(detail=True, methods=['post'])
    def test_cap(self, request, pk=None):
        """Test cap with sample user data."""
        try:
            cap = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'User ID is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get test user
            try:
                test_user = User.objects.get(id=test_user_id)
                if test_user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Test user not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test cap
            cap_result = cap_service.check_offer_cap(test_user, cap.offer)
            
            return Response({
                'success': True,
                'cap_id': cap.id,
                'offer_id': cap.offer.id,
                'offer_name': cap.offer.name,
                'test_user_id': test_user_id,
                'cap_result': cap_result
            })
            
        except CapExceededError as e:
            return Response({
                'success': False,
                'error': 'Cap exceeded',
                'details': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def reset_cap(self, request, pk=None):
        """Reset cap for next period."""
        try:
            cap = self.get_object()
            
            if cap.cap_type == 'daily':
                cap.reset_daily_cap()
            else:
                return Response({
                    'success': False,
                    'error': 'Only daily caps can be reset manually'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'cap_id': cap.id,
                'reset_at': cap.reset_at,
                'next_reset_at': cap.next_reset_at
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def reset_daily_caps(self, request):
        """Reset all daily caps for the tenant."""
        try:
            reset_count = cap_service.reset_daily_caps()
            
            return Response({
                'success': True,
                'reset_count': reset_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def cap_analytics(self, request):
        """Get analytics for offer caps."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.cap import CapEnforcementService
            cap_service_instance = CapEnforcementService()
            analytics = cap_service_instance.get_cap_analytics(
                tenant_id=request.user.id,
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
    
    @action(detail=False, methods=['get'])
    def cap_status(self, request):
        """Get current status of all caps."""
        try:
            offer_id = request.query_params.get('offer_id')
            
            caps = self.get_queryset()
            if offer_id:
                caps = caps.filter(offer_id=offer_id)
            
            cap_status = []
            for cap in caps:
                status_data = {
                    'cap_id': cap.id,
                    'offer_id': cap.offer.id,
                    'offer_name': cap.offer.name,
                    'cap_type': cap.cap_type,
                    'cap_value': cap.cap_value,
                    'current_count': cap.current_count,
                    'remaining_capacity': cap.get_remaining_capacity(),
                    'is_active': cap.is_active(),
                    'last_reset_at': cap.reset_at,
                    'next_reset_at': cap.next_reset_at
                }
                cap_status.append(status_data)
            
            return Response({
                'success': True,
                'cap_status': cap_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserOfferCapViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user-specific offer caps.
    
    Provides CRUD operations for user offer caps
    with analytics and management capabilities.
    """
    
    queryset = UserOfferCap.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter caps by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('user__username', 'offer__name')
    
    @action(detail=True, methods=['post'])
    def increment_usage(self, request, pk=None):
        """Increment cap usage for this user-offer pair."""
        try:
            cap = self.get_object()
            
            # Check if cap allows increment
            if cap.cap_type == 'daily' and cap.is_daily_cap_reached():
                return Response({
                    'success': False,
                    'error': 'Daily cap has been reached'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Increment usage
            cap.increment_shown()
            
            return Response({
                'success': True,
                'cap_id': cap.id,
                'shown_today': cap.shown_today,
                'max_shows_per_day': cap.max_shows_per_day,
                'remaining_today': cap.max_shows_per_day - cap.shown_today
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def reset_daily_cap(self, request, pk=None):
        """Reset daily cap for this user-offer pair."""
        try:
            cap = self.get_object()
            
            if cap.cap_type != 'daily':
                return Response({
                    'success': False,
                    'error': 'Only daily caps can be reset'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            cap.reset_daily_cap()
            
            return Response({
                'success': True,
                'cap_id': cap.id,
                'shown_today': cap.shown_today,
                'reset_at': cap.reset_at
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def user_caps(self, request):
        """Get caps for a specific user."""
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
            
            # Get user caps
            caps = self.get_queryset().filter(user_id=user_id)
            
            # Apply filters
            offer_id = request.query_params.get('offer_id')
            if offer_id:
                caps = caps.filter(offer_id=offer_id)
            
            # Serialize
            page = self.paginate_queryset(caps)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(caps, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def offer_caps(self, request):
        """Get caps for a specific offer."""
        try:
            offer_id = request.query_params.get('offer_id')
            if not offer_id:
                return Response({
                    'success': False,
                    'error': 'offer_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get caps
            caps = self.get_queryset().filter(offer_id=offer_id)
            
            # Get statistics
            stats = caps.aggregate(
                total_users=Count('user_id', distinct=True),
                avg_shown_today=Avg('shown_today'),
                users_with_caps_reached=Count('id', filter=Q(shown_today__gte=F('max_shows_per_day'))),
                total_shown_today=Sum('shown_today')
            )
            
            # Serialize
            page = self.paginate_queryset(caps)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'success': True,
                    'stats': stats,
                    'results': self.get_paginated_response(serializer).data
                })
            else:
                serializer = self.get_serializer(caps, many=True)
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
    def cap_utilization(self, request):
        """Get cap utilization statistics."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get utilization stats
            caps = self.get_queryset().filter(
                updated_at__gte=cutoff_date
            ).aggregate(
                total_caps=Count('id'),
                daily_caps=Count('id', filter=Q(cap_type='daily')),
                caps_reached=Count('id', filter=Q(shown_today__gte=F('max_shows_per_day'))),
                avg_utilization=Avg('shown_today'),
                max_utilization=Max('shown_today')
            )
            
            # Calculate utilization rate
            if caps['total_caps'] > 0:
                caps['utilization_rate'] = (caps['caps_reached'] / caps['total_caps']) * 100
            else:
                caps['utilization_rate'] = 0
            
            return Response({
                'success': True,
                'period_days': 30,
                'utilization_stats': caps
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CapOverrideViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cap overrides.
    
    Provides CRUD operations for cap overrides
    with validation and analytics capabilities.
    """
    
    queryset = CapOverride.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter overrides by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def test_override(self, request, pk=None):
        """Test override with sample data."""
        try:
            override = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'User ID is required for testing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get test user
            try:
                test_user = User.objects.get(id=test_user_id)
                if test_user.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'User not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Test user not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Test override
            override_result = override.is_valid_now()
            original_cap_value = cap_service._get_original_cap_value(test_user, override.offer)
            new_cap_value = override.apply_override(original_cap_value)
            
            return Response({
                'success': True,
                'override_id': override.id,
                'offer_id': override.offer.id,
                'offer_name': override.offer.name,
                'test_user_id': test_user_id,
                'is_valid_now': override_result,
                'original_cap_value': original_cap_value,
                'new_cap_value': new_cap_value,
                'override_type': override.override_type,
                'reason': override.reason
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def approve_override(self, request, pk=None):
        """Approve a cap override."""
        try:
            override = self.get_object()
            
            override.approved_by = request.user
            override.save()
            
            return Response({
                'success': True,
                'override_id': override.id,
                'approved_by': override.approved_by.username,
                'approved_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_overrides(self, request):
        """Get currently active overrides."""
        try:
            overrides = self.get_queryset().filter(is_active=True)
            
            # Check validity
            active_overrides = []
            for override in overrides:
                if override.is_valid_now():
                    active_overrides.append({
                        'override_id': override.id,
                        'offer_id': override.offer.id,
                        'offer_name': override.offer.name,
                        'override_type': override.override_type,
                        'override_cap': override.override_cap,
                        'valid_from': override.valid_from,
                        'valid_to': override.valid_to,
                        'reason': override.reason,
                        'approved_by': override.approved_by.username if override.approved_by else None
                    })
            
            return Response({
                'success': True,
                'active_overrides': active_overrides
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def override_analytics(self, request):
        """Get analytics for cap overrides."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get override statistics
            overrides = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_overrides=Count('id'),
                active_overrides=Count('id', filter=Q(is_active=True)),
                approved_overrides=Count('id', filter=Q(approved_by__isnull=False))
            )
            
            # Get distribution by type
            type_distribution = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).values('override_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'override_stats': overrides,
                'type_distribution': list(type_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired overrides."""
        try:
            deleted_count = CapOverride.objects.filter(
                is_active=True,
                valid_to__lt=timezone.now()
            ).update(is_active=False)
            
            return Response({
                'success': True,
                'deactivated_count': deleted_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def override_impact(self, request):
        """Get impact analysis of overrides."""
        try:
            # Get all active overrides
            active_overrides = self.get_queryset().filter(is_active=True)
            
            impact_analysis = []
            for override in active_overrides:
                # Calculate impact
                original_cap_value = cap_service._get_original_cap_value(None, override.offer)
                new_cap_value = override.apply_override(original_cap_value)
                
                impact = {
                    'override_id': override.id,
                    'offer_id': override.offer.id,
                    'offer_name': override.offer.name,
                    'override_type': override.override_type,
                    'original_cap': original_cap_value,
                    'new_cap': new_cap_value,
                    'impact_percentage': ((new_cap_value - original_cap_value) / original_cap_value * 100) if original_cap_value > 0 else 0,
                    'reason': override.reason
                }
                impact_analysis.append(impact)
            
            # Sort by impact
            impact_analysis.sort(key=lambda x: abs(x['impact_percentage']), reverse=True)
            
            return Response({
                'success': True,
                'impact_analysis': impact_analysis
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
