"""
Fallback Viewsets for Offer Routing System

This module contains viewsets for managing fallback rules,
default offer pools, and empty result handlers.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from ..models import (
    FallbackRule, DefaultOfferPool, EmptyResultHandler
)
from ..services.fallback import fallback_service
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, FallbackError

User = get_user_model()


class FallbackRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing fallback rules.
    
    Provides CRUD operations for fallback rules
    with testing and validation capabilities.
    """
    
    queryset = FallbackRule.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter rules by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('priority', 'name')
    
    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test fallback rule with sample user data."""
        try:
            rule = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            test_context = request.data.get('context', {})
            
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
            
            # Test rule
            applies = rule.applies_now(test_context.get('current_time'))
            conditions_match = rule.evaluate_conditions(test_user, test_context)
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.name,
                'test_user_id': test_user_id,
                'test_context': test_context,
                'applies_now': applies,
                'conditions_match': conditions_match,
                'fallback_type': rule.fallback_type,
                'priority': rule.priority
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def get_fallback_offers(self, request, pk=None):
        """Get fallback offers from this rule."""
        try:
            rule = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            test_context = request.data.get('context', {})
            
            if not test_user_id:
                return Response({
                    'success': False,
                    'error': 'User ID is required'
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
            
            # Get fallback offers
            if rule.fallback_type == 'category':
                offers = fallback_service._get_category_fallback_offers(test_user, rule, test_context)
            elif rule.fallback_type == 'network':
                offers = fallback_service._get_network_fallback_offers(test_user, rule, test_context)
            elif rule.fallback_type == 'default':
                offers = fallback_service._get_default_fallback_offers(test_user, rule, test_context)
            elif rule.fallback_type == 'promotion':
                offers = fallback_service._get_promotion_fallback_offers(test_user, rule, test_context)
            elif rule.fallback_type == 'hide_section':
                offers = fallback_service._handle_hide_section(test_user, rule, test_context)
            else:
                offers = []
            
            return Response({
                'success': True,
                'rule_id': rule.id,
                'rule_name': rule.name,
                'fallback_type': rule.fallback_type,
                'offers': offers,
                'offer_count': len(offers)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active_rules(self, request):
        """Get currently active fallback rules."""
        try:
            current_time = timezone.now()
            test_context = {'current_time': current_time}
            
            active_rules = []
            for rule in self.get_queryset().filter(is_active=True):
                if rule.applies_now(current_time):
                    active_rules.append({
                        'rule_id': rule.id,
                        'name': rule.name,
                        'description': rule.description,
                        'fallback_type': rule.fallback_type,
                        'priority': rule.priority,
                        'start_time': rule.start_time,
                        'end_time': rule.end_time,
                        'timezone': rule.timezone
                    })
            
            return Response({
                'success': True,
                'active_rules': active_rules
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def rule_analytics(self, request):
        """Get analytics for fallback rules."""
        try:
            days = int(request.query_params.get('days', 30))
            
            from ..services.fallback import FallbackService
            fallback_service_instance = FallbackService()
            analytics = fallback_service_instance.get_fallback_analytics(
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
    
    @action(detail=False, methods=['post'])
    def check_fallback_health(self, request):
        """Check health of fallback configurations."""
        try:
            from ..services.fallback import FallbackService
            fallback_service_instance = FallbackService()
            
            checked_count = fallback_service_instance.check_fallback_health()
            
            return Response({
                'success': True,
                'checked_count': checked_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DefaultOfferPoolViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing default offer pools.
    
    Provides CRUD operations for default offer pools
    with management and analytics capabilities.
    """
    
    queryset = DefaultOfferPool.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter pools by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('name', 'pool_type')
    
    @action(detail=True, methods=['post'])
    def add_offers(self, request, pk=None):
        """Add offers to this pool."""
        try:
            pool = self.get_object()
            
            offer_ids = request.data.get('offer_ids', [])
            if not offer_ids:
                return Response({
                    'success': False,
                    'error': 'offer_ids is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify offers belong to tenant
            from ..models import OfferRoute
            offers = OfferRoute.objects.filter(
                id__in=offer_ids,
                tenant=pool.tenant
            )
            
            if len(offers) != len(offer_ids):
                return Response({
                    'success': False,
                    'error': 'Some offers not found or not in your tenant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Add offers to pool
            pool.offers.add(*offers)
            
            return Response({
                'success': True,
                'pool_id': pool.id,
                'added_offers': len(offers),
                'total_offers': pool.offers.count()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def remove_offers(self, request, pk=None):
        """Remove offers from this pool."""
        try:
            pool = self.get_object()
            
            offer_ids = request.data.get('offer_ids', [])
            if not offer_ids:
                return Response({
                    'success': False,
                    'error': 'offer_ids is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Remove offers from pool
            pool.offers.remove(*offer_ids)
            
            return Response({
                'success': True,
                'pool_id': pool.id,
                'removed_offers': len(offer_ids),
                'total_offers': pool.offers.count()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_offers(self, request, pk=None):
        """Get offers from this pool based on rotation strategy."""
        try:
            pool = self.get_object()
            
            limit = int(request.query_params.get('limit', pool.max_offers))
            
            # Get offers based on rotation strategy
            if pool.rotation_strategy == 'random':
                offers = pool.get_random_offers(limit)
            elif pool.rotation_strategy == 'weighted':
                offers = pool.get_weighted_offers(limit)
            elif pool.rotation_strategy == 'priority':
                offers = pool.get_priority_offers(limit)
            else:  # round_robin
                offers = pool.offers.all()[:limit]
            
            # Serialize offers
            offer_data = []
            for offer in offers:
                offer_data.append({
                    'offer_id': offer.id,
                    'offer_name': offer.name,
                    'priority': offer.priority,
                    'is_active': offer.is_active
                })
            
            return Response({
                'success': True,
                'pool_id': pool.id,
                'pool_name': pool.name,
                'rotation_strategy': pool.rotation_strategy,
                'offers': offer_data,
                'offer_count': len(offer_data)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test_rotation(self, request, pk=None):
        """Test rotation strategy with multiple calls."""
        try:
            pool = self.get_object()
            
            test_iterations = int(request.data.get('iterations', 10))
            limit = int(request.data.get('limit', pool.max_offers))
            
            rotation_results = []
            for i in range(test_iterations):
                if pool.rotation_strategy == 'random':
                    offers = pool.get_random_offers(limit)
                elif pool.rotation_strategy == 'weighted':
                    offers = pool.get_weighted_offers(limit)
                elif pool.rotation_strategy == 'priority':
                    offers = pool.get_priority_offers(limit)
                else:  # round_robin
                    offers = pool.offers.all()[:limit]
                
                rotation_results.append({
                    'iteration': i + 1,
                    'offer_ids': [offer.id for offer in offers],
                    'offer_count': len(offers)
                })
            
            return Response({
                'success': True,
                'pool_id': pool.id,
                'rotation_strategy': pool.rotation_strategy,
                'test_iterations': test_iterations,
                'results': rotation_results
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def pool_analytics(self, request):
        """Get analytics for offer pools."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get pool statistics
            pools = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_pools=Count('id'),
                active_pools=Count('id', filter=Q(is_active=True)),
                avg_offers_per_pool=Avg('offers__count')
            )
            
            # Get distribution by type
            type_distribution = self.get_queryset().values('pool_type').annotate(
                count=Count('id'),
                avg_offers=Avg('offers__count')
            ).order_by('-count')
            
            # Get distribution by rotation strategy
            rotation_distribution = self.get_queryset().values('rotation_strategy').annotate(
                count=Count('id'),
                avg_offers=Avg('offers__count')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'pool_stats': pools,
                'type_distribution': list(type_distribution),
                'rotation_distribution': list(rotation_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmptyResultHandlerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing empty result handlers.
    
    Provides CRUD operations for empty result handlers
    with testing and validation capabilities.
    """
    
    queryset = EmptyResultHandler.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter handlers by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('name')
    
    @action(detail=True, methods=['post'])
    def test_handler(self, request, pk=None):
        """Test empty result handler with sample data."""
        try:
            handler = self.get_object()
            
            # Get test user data
            test_user_id = request.data.get('user_id')
            test_context = request.data.get('context', {})
            
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
            
            # Test handler
            should_apply = handler.should_apply(test_context)
            
            if should_apply:
                # Execute handler action
                if handler.action_type == 'hide_section':
                    action_result = {
                        'action': 'hide_section',
                        'message': handler.action_value
                    }
                elif handler.action_type == 'show_promo':
                    action_result = {
                        'action': 'show_promo',
                        'message': handler.action_value
                    }
                elif handler.action_type == 'redirect_url':
                    action_result = {
                        'action': 'redirect_url',
                        'redirect_url': handler.redirect_url
                    }
                elif handler.action_type == 'show_default':
                    default_offers = fallback_service._get_default_offers_for_handler(test_user, handler)
                    action_result = {
                        'action': 'show_default',
                        'offers': default_offers
                    }
                elif handler.action_type == 'custom_message':
                    action_result = {
                        'action': 'custom_message',
                        'custom_message': handler.custom_message
                    }
                else:
                    action_result = {
                        'action': 'unknown',
                        'message': 'Unknown action type'
                    }
            else:
                action_result = {
                    'action': 'none',
                    'message': 'Handler conditions not met'
                }
            
            return Response({
                'success': True,
                'handler_id': handler.id,
                'handler_name': handler.name,
                'test_user_id': test_user_id,
                'test_context': test_context,
                'should_apply': should_apply,
                'action_result': action_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def applicable_handlers(self, request):
        """Get handlers that would apply to current context."""
        try:
            context = request.query_params.dict()
            
            applicable_handlers = []
            for handler in self.get_queryset().filter(is_active=True):
                if handler.should_apply(context):
                    applicable_handlers.append({
                        'handler_id': handler.id,
                        'name': handler.name,
                        'description': handler.description,
                        'action_type': handler.action_type,
                        'priority': handler.priority
                    })
            
            return Response({
                'success': True,
                'context': context,
                'applicable_handlers': applicable_handlers
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def handler_analytics(self, request):
        """Get analytics for empty result handlers."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get handler statistics
            handlers = self.get_queryset().filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_handlers=Count('id'),
                active_handlers=Count('id', filter=Q(is_active=True))
            )
            
            # Get distribution by action type
            action_distribution = self.get_queryset().values('action_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'handler_stats': handlers,
                'action_distribution': list(action_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def supported_actions(self, request):
        """Get list of supported handler actions."""
        try:
            actions = [
                {
                    'value': 'hide_section',
                    'label': 'Hide Section',
                    'description': 'Hide the offers section completely'
                },
                {
                    'value': 'show_promo',
                    'label': 'Show Promotional Message',
                    'description': 'Display a promotional message instead of offers'
                },
                {
                    'value': 'redirect_url',
                    'label': 'Redirect to URL',
                    'description': 'Redirect user to a specific URL'
                },
                {
                    'value': 'show_default',
                    'label': 'Show Default Offers',
                    'description': 'Show default offers from a pool'
                },
                {
                    'value': 'custom_message',
                    'label': 'Show Custom Message',
                    'description': 'Display a custom message'
                }
            ]
            
            return Response({
                'success': True,
                'actions': actions
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
