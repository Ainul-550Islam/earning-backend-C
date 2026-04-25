"""
Personalization Viewsets for Offer Routing System

This module contains viewsets for managing personalization configurations,
user preference vectors, and contextual signals.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count
from ..models import (
    UserPreferenceVector, ContextualSignal, PersonalizationConfig, OfferAffinityScore
)
from ..services.personalization import (
    personalization_service, collaborative_service, content_based_service, affinity_service
)
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..exceptions import ValidationError, PersonalizationError

User = get_user_model()


# PersonalizationConfigViewSet moved to viewsets/config.py to avoid duplication

class UserPreferenceVectorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user preference vectors.
    
    Provides CRUD operations for user preference vectors
    with analytics and update capabilities.
    """
    
    queryset = UserPreferenceVector.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter vectors by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-last_updated')
    
    @action(detail=True, methods=['post'])
    def update_preferences(self, request, pk=None):
        """Update user preferences based on interaction data."""
        try:
            vector = self.get_object()
            
            interaction_data = request.data.get('interaction_data', [])
            if not interaction_data:
                return Response({
                    'success': False,
                    'error': 'interaction_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update preferences
            success = personalization_service.update_user_preferences(
                user=vector.user,
                interaction_data=interaction_data
            )
            
            if success:
                # Refresh from database
                vector.refresh_from_db()
            
            return Response({
                'success': success,
                'vector_id': vector.id,
                'updated': success
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def merge_vector(self, request, pk=None):
        """Merge another preference vector into this one."""
        try:
            vector = self.get_object()
            
            other_vector_data = request.data.get('other_vector', {})
            weight = request.data.get('weight', 0.5)
            
            if not other_vector_data:
                return Response({
                    'success': False,
                    'error': 'other_vector is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Merge vectors
            vector.merge_vector(other_vector_data, weight)
            
            return Response({
                'success': True,
                'vector_id': vector.id,
                'merged': True
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def similarity_analysis(self, request, pk=None):
        """Calculate similarity with other users."""
        try:
            vector = self.get_object()
            
            # Get similar users
            similar_users = collaborative_service._get_similar_users(vector.user, limit=10)
            
            similarity_data = []
            for similar_user, similarity in similar_users:
                similarity_data.append({
                    'user_id': similar_user.id,
                    'username': similar_user.username,
                    'similarity': similarity
                })
            
            return Response({
                'success': True,
                'vector_id': vector.id,
                'similar_users': similarity_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def rebuild_vectors(self, request):
        """Rebuild preference vectors from content analysis."""
        try:
            rebuilt_count = content_based_service.rebuild_preference_vectors()
            
            return Response({
                'success': True,
                'rebuilt_count': rebuilt_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def analytics_summary(self, request):
        """Get analytics summary for preference vectors."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get vector statistics
            vectors = self.get_queryset().filter(
                last_updated__gte=cutoff_date
            ).aggregate(
                total_vectors=Count('id'),
                avg_accuracy=Avg('accuracy_score'),
                avg_version=Avg('version')
            )
            
            # Get category distribution
            category_stats = {}
            for vector in self.get_queryset().filter(last_updated__gte=cutoff_date):
                for category, weight in vector.category_weights.items():
                    if category not in category_stats:
                        category_stats[category] = {
                            'total_weight': 0,
                            'user_count': 0
                        }
                    category_stats[category]['total_weight'] += weight
                    category_stats[category]['user_count'] += 1
            
            # Calculate averages
            for category in category_stats:
                if category_stats[category]['user_count'] > 0:
                    category_stats[category]['avg_weight'] = (
                        category_stats[category]['total_weight'] / category_stats[category]['user_count']
                    )
            
            return Response({
                'success': True,
                'period_days': 30,
                'vector_stats': vectors,
                'category_stats': category_stats
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContextualSignalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing contextual signals.
    
    Provides CRUD operations for contextual signals
    with analytics and filtering capabilities.
    """
    
    queryset = ContextualSignal.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter signals by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def create_signal(self, request):
        """Create a contextual signal for a user."""
        try:
            user_id = request.data.get('user_id')
            signal_type = request.data.get('signal_type')
            value = request.data.get('value')
            expires_hours = request.data.get('expires_hours', 24)
            
            if not user_id or not signal_type or value is None:
                return Response({
                    'success': False,
                    'error': 'user_id, signal_type, and value are required'
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
            
            # Create signal
            from ..services.personalization import ContextualSignal
            signal = ContextualSignal.create_signal(
                user=user,
                signal_type=signal_type,
                value=value,
                expires_hours=expires_hours
            )
            
            return Response({
                'success': True,
                'signal_id': signal.id,
                'user_id': user_id,
                'signal_type': signal_type,
                'value': value,
                'expires_at': signal.expires_at.isoformat() if signal.expires_at else None
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def user_signals(self, request):
        """Get contextual signals for a specific user."""
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
            
            # Get signals
            signals = self.queryset.filter(user_id=user_id)
            
            # Apply filters
            signal_type = request.query_params.get('signal_type')
            if signal_type:
                signals = signals.filter(signal_type=signal_type)
            
            active_only = request.query_params.get('active_only')
            if active_only == 'true':
                signals = signals.filter(expires_at__gt=timezone.now())
            
            # Serialize
            page = self.paginate_queryset(signals)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer)
            else:
                serializer = self.get_serializer(signals, many=True)
                return Response(serializer.data)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def signal_types(self, request):
        """Get available signal types and their descriptions."""
        try:
            signal_types = [
                {
                    'value': 'time',
                    'label': 'Time-based',
                    'description': 'Signals based on time of day, day of week, etc.'
                },
                {
                    'value': 'location',
                    'label': 'Location-based',
                    'description': 'Signals based on geographic location'
                },
                {
                    'value': 'device',
                    'label': 'Device-based',
                    'description': 'Signals based on device type and characteristics'
                },
                {
                    'value': 'behavior',
                    'label': 'Behavior-based',
                    'description': 'Signals based on user behavior patterns'
                },
                {
                    'value': 'context',
                    'label': 'General Context',
                    'description': 'General contextual information'
                }
            ]
            
            return Response({
                'success': True,
                'signal_types': signal_types
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired contextual signals."""
        try:
            deleted_count = ContextualSignal.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            return Response({
                'success': True,
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def signal_analytics(self, request):
        """Get analytics for contextual signals."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=30)
            
            # Get signal statistics
            signals = self.queryset.filter(
                created_at__gte=cutoff_date
            ).aggregate(
                total_signals=Count('id'),
                active_signals=Count('id', filter=Q(expires_at__gt=timezone.now())),
                avg_confidence=Avg('confidence')
            )
            
            # Get distribution by type
            type_distribution = self.queryset.filter(
                created_at__gte=cutoff_date
            ).values('signal_type').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('-count')
            
            return Response({
                'success': True,
                'period_days': 30,
                'signal_stats': signals,
                'type_distribution': list(type_distribution)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferAffinityScoreViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing offer affinity scores.
    
    Provides CRUD operations for affinity scores
    with analytics and update capabilities.
    """
    
    queryset = OfferAffinityScore.objects.all()
    serializer_class = None  # Will be defined in serializers.py
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        """Filter affinity scores by tenant."""
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user__tenant=self.request.user)
        return queryset.order_by('-score')
    
    @action(detail=False, methods=['post'])
    def update_affinity_scores(self, request):
        """Update affinity scores for all users."""
        try:
            updated_count = collaborative_service.update_affinity_scores()
            
            return Response({
                'success': True,
                'updated_count': updated_count
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def category_affinity_matrix(self, request):
        """Get affinity matrix for categories."""
        try:
            # Get unique categories
            categories = self.get_queryset().values_list('category', flat=True).distinct()
            
            # Create matrix
            matrix = {}
            for category in categories:
                category_scores = self.get_queryset().filter(category=category)
                
                matrix[category] = {
                    'avg_score': category_scores.aggregate(avg=Avg('score'))['avg'] or 0,
                    'max_score': category_scores.aggregate(max=Max('score'))['max'] or 0,
                    'min_score': category_scores.aggregate(min=Min('score'))['min'] or 0,
                    'user_count': category_scores.count(),
                    'top_users': []
                }
                
                # Get top users for this category
                top_users = category_scores.order_by('-score')[:5]
                for score in top_users:
                    matrix[category]['top_users'].append({
                        'user_id': score.user.id,
                        'username': score.user.username,
                        'score': score.score,
                        'confidence': score.confidence
                    })
            
            return Response({
                'success': True,
                'affinity_matrix': matrix
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def user_affinity_summary(self, request):
        """Get affinity summary for users."""
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
            
            # Get user's affinity scores
            user_affinities = self.get_queryset().filter(user_id=user_id)
            
            # Calculate summary
            summary = user_affinities.aggregate(
                avg_score=Avg('score'),
                max_score=Max('score'),
                min_score=Min('score'),
                total_categories=Count('category', distinct=True),
                avg_confidence=Avg('confidence')
            )
            
            # Get top categories
            top_categories = user_affinities.order_by('-score')[:10]
            
            return Response({
                'success': True,
                'user_id': user_id,
                'summary': summary,
                'top_categories': [
                    {
                        'category': score.category,
                        'score': score.score,
                        'confidence': score.confidence
                    }
                    for score in top_categories
                ]
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
