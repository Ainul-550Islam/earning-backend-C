"""
Scoring Viewsets for Offer Routing System

This module contains viewsets for managing scoring configurations,
offer scores, and ranking operations.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count
from ..models import (
    OfferScore, OfferScoreConfig, GlobalOfferRank,
    UserOfferHistory, OfferAffinityScore
)
from ..services.scoring import scoring_service, ranker_service
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, ScoringError

User = get_user_model()


class OfferScoreConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing offer scoring configurations.
    
    Provides CRUD operations for scoring configurations
    with validation and testing capabilities.
    """
    
    queryset = OfferScoreConfig.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    
    def get_queryset(self):
        """Filter configs by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('offer__name')
    
    @action(detail=True, methods=['post'])
    def test_config(self, request, pk=None):
        """Test scoring configuration with sample data."""
        try:
            config = self.get_object()
            
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
            
            # Test scoring
            test_context = request.data.get('context', {})
            score_data = scoring_service.calculate_offer_score(
                offer=config.offer,
                user=test_user,
                context=test_context
            )
            
            return Response({
                'success': True,
                'config_id': config.id,
                'offer_id': config.offer.id,
                'offer_name': config.offer.name,
                'test_user_id': test_user_id,
                'test_context': test_context,
                'score_data': score_data
            })
            
        except ScoringError as e:
            return Response({
                'success': False,
                'error': 'Scoring error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def optimize_weights(self, request, pk=None):
        """Optimize scoring weights for this configuration."""
        try:
            config = self.get_object()
            
            from ..services.optimizer import routing_optimizer
            optimization_result = routing_optimizer.optimize_score_weights(
                tenant_id=config.tenant.id
            )
            
            # Find if this config was optimized
            config_change = next(
                (change for change in optimization_result['config_changes'] 
                 if change['offer_id'] == config.offer.id),
                None
            )
            
            if config_change:
                # Refresh config from database
                config.refresh_from_db()
            
            return Response({
                'success': True,
                'config_id': config.id,
                'optimized': config_change is not None,
                'optimization_result': optimization_result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_optimize(self, request):
        """Optimize all scoring configurations for the tenant."""
        try:
            from ..services.optimizer import routing_optimizer
            
            optimization_results = routing_optimizer.optimize_score_weights(
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
    
    @action(detail=False, methods=['get'])
    def performance_analysis(self, request):
        """Get performance analysis for scoring configurations."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get scoring performance metrics
            configs = self.get_queryset().filter(
                updated_at__gte=cutoff_date
            )
            
            analysis = []
            for config in configs:
                # Get recent scores for this offer
                recent_scores = OfferScore.objects.filter(
                    offer=config.offer,
                    user__tenant=config.tenant,
                    created_at__gte=cutoff_date
                ).aggregate(
                    avg_score=Avg('score'),
                    total_scores=Count('id'),
                    avg_epc=Avg('epc'),
                    avg_cr=Avg('cr'),
                    avg_relevance=Avg('relevance'),
                    avg_freshness=Avg('freshness')
                )
                
                analysis.append({
                    'config_id': config.id,
                    'offer_id': config.offer.id,
                    'offer_name': config.offer.name,
                    'weights': {
                        'epc_weight': float(config.epc_weight),
                        'cr_weight': float(config.cr_weight),
                        'relevance_weight': float(config.relevance_weight),
                        'freshness_weight': float(config.freshness_weight)
                    },
                    'performance': recent_scores
                })
            
            return Response({
                'success': True,
                'period_days': 30,
                'analysis': analysis
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing offer scores.
    
    Provides read-only access to offer scores
    with filtering and analytics capabilities.
    """
    
    queryset = OfferScore.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter scores by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def user_scores(self, request):
        """Get scores for a specific user."""
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
            
            # Get scores
            scores = self.queryset.filter(user_id=user_id)
            
            # Apply filters
            offer_id = request.query_params.get('offer_id')
            if offer_id:
                scores = scores.filter(offer_id=offer_id)
            
            days = request.query_params.get('days')
            if days:
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=int(days))
                scores = scores.filter(created_at__gte=cutoff_date)
            
            # Serialize
            page = self.paginate_queryset(scores)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(scores, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def offer_scores(self, request):
        """Get scores for a specific offer."""
        try:
            offer_id = request.query_params.get('offer_id')
            if not offer_id:
                return Response({
                    'success': False,
                    'error': 'offer_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get scores
            scores = self.queryset.filter(offer_id=offer_id)
            
            # Apply filters
            days = request.query_params.get('days')
            if days:
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=int(days))
                scores = scores.filter(created_at__gte=cutoff_date)
            
            # Get statistics
            stats = scores.aggregate(
                avg_score=Avg('score'),
                max_score=Max('score'),
                min_score=Min('score'),
                total_scores=Count('id'),
                avg_epc=Avg('epc'),
                avg_cr=Avg('cr'),
                avg_relevance=Avg('relevance'),
                avg_freshness=Avg('freshness')
            )
            
            # Serialize
            page = self.paginate_queryset(scores)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'success': True,
                    'stats': stats,
                    'results': self.get_paginated_response(serializer).data
                })
            else:
                serializer = self.get_serializer(scores, many=True)
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
    
    @action(detail=False, methods=['post'])
    def calculate_score(self, request):
        """Calculate score for a specific user and offer."""
        try:
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            context = request.data.get('context', {})
            
            if not user_id or not offer_id:
                return Response({
                    'success': False,
                    'error': 'Both user_id and offer_id are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user and offer belong to tenant
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
            
            try:
                from ..models import OfferRoute
                offer = OfferRoute.objects.get(id=offer_id)
                if offer.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'Offer not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except OfferRoute.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Offer not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Calculate score
            score_data = scoring_service.calculate_offer_score(
                offer=offer,
                user=user,
                context=context
            )
            
            return Response({
                'success': True,
                'user_id': user_id,
                'offer_id': offer_id,
                'context': context,
                'score_data': score_data
            })
            
        except ScoringError as e:
            return Response({
                'success': False,
                'error': 'Scoring error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GlobalOfferRankViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing global offer rankings.
    
    Provides read-only access to global offer rankings
    with filtering and analytics capabilities.
    """
    
    queryset = GlobalOfferRank.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter ranks by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(tenant=self.request.user)
        return queryset.order_by('-rank_date', 'rank_score')
    
    @action(detail=False, methods=['get'])
    def top_offers(self, request):
        """Get top-ranked offers."""
        try:
            limit = int(request.query_params.get('limit', 10))
            
            # Get top offers
            top_offers = self.queryset.order_by('-rank_score')[:limit]
            
            serializer = self.get_serializer(top_offers, many=True)
            return Response({
                'success': True,
                'limit': limit,
                'results': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def ranking_history(self, request):
        """Get ranking history for offers."""
        try:
            offer_id = request.query_params.get('offer_id')
            days = int(request.query_params.get('days', 30))
            
            if not offer_id:
                return Response({
                    'success': False,
                    'error': 'offer_id parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get ranking history
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            history = self.queryset.filter(
                offer_id=offer_id,
                rank_date__gte=cutoff_date.date()
            ).order_by('rank_date')
            
            serializer = self.get_serializer(history, many=True)
            return Response({
                'success': True,
                'offer_id': offer_id,
                'period_days': days,
                'results': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_rankings(self, request):
        """Update global offer rankings."""
        try:
            updated_count = ranker_service.update_global_rankings()
            
            return Response({
                'success': True,
                'updated_count': updated_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserOfferHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user offer interaction history.
    
    Provides read-only access to user offer history
    with filtering and analytics capabilities.
    """
    
    queryset = UserOfferHistory.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter history by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def user_history(self, request):
        """Get offer history for a specific user."""
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
            
            # Get history
            history = self.queryset.filter(user_id=user_id)
            
            # Apply filters
            offer_id = request.query_params.get('offer_id')
            if offer_id:
                history = history.filter(offer_id=offer_id)
            
            days = request.query_params.get('days')
            if days:
                from datetime import timedelta
                cutoff_date = timezone.now() - timedelta(days=int(days))
                history = history.filter(created_at__gte=cutoff_date)
            
            # Get statistics
            stats = history.aggregate(
                total_interactions=Count('id'),
                total_views=Count('id', filter=Q(viewed_at__isnull=False)),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False)),
                total_revenue=Sum('conversion_value')
            )
            
            # Serialize
            page = self.paginate_queryset(history)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'success': True,
                    'stats': stats,
                    'results': self.get_paginated_response(serializer).data
                })
            else:
                serializer = self.get_serializer(history, many=True)
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
    
    @action(detail=False, methods=['post'])
    def record_interaction(self, request):
        """Record a user-offer interaction."""
        try:
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            interaction_type = request.data.get('interaction_type')
            conversion_value = request.data.get('conversion_value', 0)
            
            if not user_id or not offer_id or not interaction_type:
                return Response({
                    'success': False,
                    'error': 'user_id, offer_id, and interaction_type are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify user and offer belong to tenant
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
            
            try:
                from ..models import OfferRoute
                offer = OfferRoute.objects.get(id=offer_id)
                if offer.tenant != request.user:
                    return Response({
                        'success': False,
                        'error': 'Offer not found in your tenant'
                    }, status=status.HTTP_403_FORBIDDEN)
            except OfferRoute.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Offer not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Record interaction
            history, created = UserOfferHistory.objects.update_or_create(
                user=user,
                offer=offer,
                defaults={
                    'route_id': offer.id,  # Use offer as route for now
                    'conversion_value': conversion_value
                }
            )
            
            # Update interaction timestamps
            if interaction_type == 'view':
                history.viewed_at = timezone.now()
            elif interaction_type == 'click':
                history.clicked_at = timezone.now()
            elif interaction_type == 'conversion':
                history.completed_at = timezone.now()
                history.conversion_value = conversion_value
            
            history.save()
            
            return Response({
                'success': True,
                'user_id': user_id,
                'offer_id': offer_id,
                'interaction_type': interaction_type,
                'conversion_value': conversion_value,
                'created': created
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# OfferAffinityScoreViewSet moved to viewsets/personalization.py to avoid duplication
            
            # Get affinities
            affinities = self.queryset.filter(user_id=user_id)
            
            # Apply filters
            category = request.query_params.get('category')
            if category:
                affinities = affinities.filter(category=category)
            
            limit = request.query_params.get('limit')
            if limit:
                affinities = affinities[:int(limit)]
            
            serializer = self.get_serializer(affinities, many=True)
            return Response({
                'success': True,
                'user_id': user_id,
                'results': serializer.data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def category_affinities(self, request):
        """Get affinity scores for a specific category."""
        try:
            category = request.query_params.get('category')
            if not category:
                return Response({
                    'success': False,
                    'error': 'category parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get affinities
            affinities = self.queryset.filter(category=category)
            
            # Get statistics
            stats = affinities.aggregate(
                avg_score=Avg('score'),
                max_score=Max('score'),
                min_score=Min('score'),
                total_users=Count('user_id', distinct=True),
                avg_confidence=Avg('confidence')
            )
            
            # Serialize
            page = self.paginate_queryset(affinities)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'success': True,
                    'category': category,
                    'stats': stats,
                    'results': self.get_paginated_response(serializer).data
                })
            else:
                serializer = self.get_serializer(affinities, many=True)
                return Response({
                    'success': True,
                    'category': category,
                    'stats': stats,
                    'results': serializer.data
                })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_affinity(self, request):
        """Update affinity score for a user and category."""
        try:
            user_id = request.data.get('user_id')
            category = request.data.get('category')
            score = request.data.get('score')
            confidence = request.data.get('confidence', 1.0)
            
            if not user_id or not category or score is None:
                return Response({
                    'success': False,
                    'error': 'user_id, category, and score are required'
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
            
            # Update affinity
            from ..services.personalization import affinity_service
            affinity_service.update_affinity_score(
                user_id=user_id,
                category=category,
                score=score,
                confidence=confidence
            )
            
            return Response({
                'success': True,
                'user_id': user_id,
                'category': category,
                'score': score,
                'confidence': confidence
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Alias
OfferAffinityScoreViewSet = UserOfferHistoryViewSet
