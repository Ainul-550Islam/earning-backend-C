"""
Personalization Viewsets for Offer Routing System

Exposes ALL four personalization sub-services via API:
  - UserPreferenceVectorViewSet     — preference vector CRUD + update
  - ContextualSignalViewSet         — signal CRUD + manual trigger
  - OfferAffinityScoreViewSet       — affinity scores + category matrix
  - HybridRecommendationViewSet     — hybrid recs + algorithm comparison ← NEW
  - CollaborativeFilterViewSet      — CF-specific recommendations ← NEW
  - ContentBasedViewSet             — CB-specific recommendations ← NEW

Business Value Added:
  - Tenants can compare CF vs CB vs Hybrid algorithm performance
  - Tenants can manually trigger context signal processing
  - Tenants can preview hybrid recommendations before going live
  - Tenants can see which algorithm drives their conversions
"""

import logging

from ..throttling import RoutingEngineThrottle, RoutingEngineThrottle, AnalyticsThrottle, BulkOperationThrottle, EvaluatorThrottle
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Avg, Count, Max, Min

from ..models import (
    UserPreferenceVector, ContextualSignal,
    PersonalizationConfig, OfferAffinityScore,
)
from ..services.personalization import (
    personalization_service,
    collaborative_service,
    content_based_service,
    context_signal_service,
    hybrid_service,
    affinity_service,
)
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..serializers import (
    UserPreferenceVectorSerializer,
    ContextualSignalSerializer,
    OfferAffinityScoreSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# UserPreferenceVectorViewSet  (existing — preserved + fail-safe queryset)
# ─────────────────────────────────────────────────────────────────────────────

class UserPreferenceVectorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user preference vectors.

    Provides CRUD + analytics + update capabilities.
    """

    queryset = UserPreferenceVector.objects.all()
    serializer_class = UserPreferenceVectorSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(user__tenant=self.request.user)
        except Exception as e:
            logger.error("UserPreferenceVectorViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('-updated_at')

    @action(detail=True, methods=['post'])
    def update_preferences(self, request, pk=None):
        """Update user preferences based on interaction data."""
        try:
            vector = self.get_object()
            interaction_data = request.data.get('interaction_data', [])
            if not interaction_data:
                return Response({'success': False, 'error': 'interaction_data is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            success = personalization_service.update_user_preferences(
                user=vector.user,
                interaction_data=interaction_data,
            )
            if success:
                vector.refresh_from_db()
            return Response({'success': success, 'vector_id': vector.id, 'updated': success})
        except Exception as e:
            logger.error("update_preferences error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def merge_vector(self, request, pk=None):
        """Merge another preference vector into this one."""
        try:
            vector = self.get_object()
            other_vector_data = request.data.get('other_vector', {})
            weight = float(request.data.get('weight', 0.5))
            if not other_vector_data:
                return Response({'success': False, 'error': 'other_vector is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            vector.merge_vector(other_vector_data, weight)
            return Response({'success': True, 'vector_id': vector.id, 'merged': True})
        except Exception as e:
            logger.error("merge_vector error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def similarity_analysis(self, request, pk=None):
        """Calculate similarity with other users (collaborative filtering)."""
        try:
            vector = self.get_object()
            similar_users = collaborative_service._get_similar_users(vector.user, limit=10)
            similarity_data = [
                {'user_id': u.id, 'username': u.username, 'similarity': sim}
                for u, sim in similar_users
            ]
            return Response({'success': True, 'vector_id': vector.id, 'similar_users': similarity_data})
        except Exception as e:
            logger.error("similarity_analysis error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def rebuild_vectors(self, request):
        """Rebuild preference vectors from content analysis (content-based service)."""
        try:
            rebuilt_count = content_based_service.rebuild_preference_vectors()
            return Response({'success': True, 'rebuilt_count': rebuilt_count})
        except Exception as e:
            logger.error("rebuild_vectors error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def analytics_summary(self, request):
        """Analytics summary for preference vectors."""
        try:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=30)
            vectors = self.get_queryset().filter(updated_at__gte=cutoff).aggregate(
                total_vectors=Count('id'),
                avg_accuracy=Avg('accuracy_score'),
                avg_version=Avg('version'),
            )
            category_stats = {}
            for v in self.get_queryset().filter(updated_at__gte=cutoff):
                for cat, wt in (v.category_weights or {}).items():
                    if cat not in category_stats:
                        category_stats[cat] = {'total_weight': 0.0, 'user_count': 0}
                    category_stats[cat]['total_weight'] += float(wt)
                    category_stats[cat]['user_count'] += 1
            for cat in category_stats:
                if category_stats[cat]['user_count']:
                    category_stats[cat]['avg_weight'] = (
                        category_stats[cat]['total_weight'] / category_stats[cat]['user_count']
                    )
            return Response({'success': True, 'period_days': 30,
                             'vector_stats': vectors, 'category_stats': category_stats})
        except Exception as e:
            logger.error("analytics_summary error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# ContextualSignalViewSet  (existing — preserved + manual trigger)
# ─────────────────────────────────────────────────────────────────────────────

class ContextualSignalViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing contextual signals.

    NEW: process_signals action triggers ContextSignalService manually.
    """

    queryset = ContextualSignal.objects.all()
    serializer_class = ContextualSignalSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(user__tenant=self.request.user)
        except Exception as e:
            logger.error("ContextualSignalViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('-created_at')

    @action(detail=False, methods=['post'])
    def create_signal(self, request):
        """Create a contextual signal for a user."""
        try:
            user_id     = request.data.get('user_id')
            signal_type = request.data.get('signal_type')
            value       = request.data.get('value')
            expires_hours = int(request.data.get('expires_hours', 24))

            if not user_id or not signal_type or value is None:
                return Response({'success': False,
                                 'error': 'user_id, signal_type, and value are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            signal = ContextualSignal.create_signal(
                user=user, signal_type=signal_type,
                value=value, expires_hours=expires_hours,
            )
            return Response({'success': True, 'signal_id': signal.id, 'user_id': user_id,
                             'signal_type': signal_type, 'value': value,
                             'expires_at': signal.expires_at.isoformat() if signal.expires_at else None})
        except Exception as e:
            logger.error("create_signal error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def process_signals(self, request):
        """
        Manually trigger ContextSignalService to process all active signals.
        Business value: ops team can flush signals without waiting for celery beat.
        """
        try:
            user_id = request.data.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    if user.tenant != request.user:
                        return Response({'success': False, 'error': 'User not in your tenant'},
                                        status=status.HTTP_403_FORBIDDEN)
                except User.DoesNotExist:
                    return Response({'success': False, 'error': 'User not found'},
                                    status=status.HTTP_404_NOT_FOUND)
            result = context_signal_service.process_signals(
                tenant_id=request.user.id,
                user_id=user_id,
            )
            return Response({'success': True, 'processed': result})
        except Exception as e:
            logger.error("process_signals error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def user_signals(self, request):
        """Get contextual signals for a specific user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            qs = self.get_queryset().filter(user_id=user_id)
            if request.query_params.get('signal_type'):
                qs = qs.filter(signal_type=request.query_params['signal_type'])
            if request.query_params.get('active_only') == 'true':
                qs = qs.filter(expires_at__gt=timezone.now())
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(self.get_serializer(page, many=True).data)
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            logger.error("user_signals error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Remove expired contextual signals."""
        try:
            deleted_count = context_signal_service.cleanup_expired(
                tenant_id=request.user.id
            )
            if not isinstance(deleted_count, int):
                deleted_count = ContextualSignal.objects.filter(
                    user__tenant=request.user,
                    expires_at__lt=timezone.now(),
                ).delete()[0]
            return Response({'success': True, 'deleted_count': deleted_count})
        except Exception as e:
            logger.error("cleanup_expired error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def signal_types(self, request):
        """Get available signal types."""
        return Response({'success': True, 'signal_types': [
            {'value': 'time',     'label': 'Time-based',     'description': 'Time of day / day of week signals'},
            {'value': 'location', 'label': 'Location-based', 'description': 'Geographic location signals'},
            {'value': 'device',   'label': 'Device-based',   'description': 'Device type / OS signals'},
            {'value': 'behavior', 'label': 'Behavior-based', 'description': 'User action / interaction signals'},
            {'value': 'context',  'label': 'General Context','description': 'Miscellaneous contextual data'},
        ]})

    @action(detail=False, methods=['get'])
    def signal_analytics(self, request):
        """Analytics for contextual signals."""
        try:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=30)
            stats = self.get_queryset().filter(created_at__gte=cutoff).aggregate(
                total_signals=Count('id'),
                active_signals=Count('id', filter=Q(expires_at__gt=timezone.now())),
                avg_confidence=Avg('confidence'),
            )
            dist = (self.get_queryset().filter(created_at__gte=cutoff)
                    .values('signal_type')
                    .annotate(count=Count('id'), avg_confidence=Avg('confidence'))
                    .order_by('-count'))
            return Response({'success': True, 'period_days': 30,
                             'signal_stats': stats, 'type_distribution': list(dist)})
        except Exception as e:
            logger.error("signal_analytics error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# OfferAffinityScoreViewSet  (existing — preserved + affinity service wired)
# ─────────────────────────────────────────────────────────────────────────────

class OfferAffinityScoreViewSet(viewsets.ModelViewSet):
    """ViewSet for managing offer affinity scores."""

    queryset = OfferAffinityScore.objects.all()
    serializer_class = OfferAffinityScoreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return queryset.none()
        try:
            queryset = queryset.filter(user__tenant=self.request.user)
        except Exception as e:
            logger.error("OfferAffinityScoreViewSet.get_queryset error: %s", e, exc_info=True)
            return queryset.none()
        return queryset.order_by('-score')

    @action(detail=False, methods=['post'])
    def update_affinity_scores(self, request):
        """Trigger collaborative service to refresh all affinity scores."""
        try:
            updated_count = collaborative_service.update_affinity_scores()
            return Response({'success': True, 'updated_count': updated_count})
        except Exception as e:
            logger.error("update_affinity_scores error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def category_affinity_matrix(self, request):
        """Affinity matrix grouped by category."""
        try:
            categories = self.get_queryset().values_list('category', flat=True).distinct()
            matrix = {}
            for cat in categories:
                cat_qs = self.get_queryset().filter(category=cat)
                agg = cat_qs.aggregate(
                    avg=Avg('score'), maximum=Max('score'),
                    minimum=Min('score'), user_count=Count('id'),
                )
                top = [{'user_id': s.user_id, 'score': s.score, 'confidence': s.confidence}
                       for s in cat_qs.order_by('-score')[:5]]
                matrix[cat] = {'avg_score': agg['avg'], 'max_score': agg['maximum'],
                                'min_score': agg['minimum'], 'user_count': agg['user_count'],
                                'top_users': top}
            return Response({'success': True, 'affinity_matrix': matrix})
        except Exception as e:
            logger.error("category_affinity_matrix error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def user_affinity_summary(self, request):
        """Full affinity summary for a single user."""
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            qs  = self.get_queryset().filter(user_id=user_id)
            agg = qs.aggregate(avg_score=Avg('score'), max_score=Max('score'),
                               min_score=Min('score'), categories=Count('category', distinct=True),
                               avg_confidence=Avg('confidence'))
            top = [{'category': s.category, 'score': s.score, 'confidence': s.confidence}
                   for s in qs.order_by('-score')[:10]]
            return Response({'success': True, 'user_id': user_id,
                             'summary': agg, 'top_categories': top})
        except Exception as e:
            logger.error("user_affinity_summary error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# HybridRecommendationViewSet  ← NEW — exposes HybridRoutingService via API
# ─────────────────────────────────────────────────────────────────────────────

class HybridRecommendationViewSet(viewsets.ViewSet):
    """
    ViewSet for the Hybrid Recommendation Engine.

    Business Value:
      - Tenants can get offers ranked by the COMBINED CF+CB algorithm
      - Tenants can compare CF vs CB vs Hybrid output side-by-side
      - Tenants can tune CF/CB weighting and preview the effect
      - Tenants can see which algorithm produces better conversions
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    @action(detail=False, methods=['post'])
    def recommend(self, request):
        """
        Get hybrid recommendations for a user.
        Combines collaborative filtering and content-based scoring.

        POST body:
            user_id   (int)  — required
            context   (dict) — optional
            limit     (int)  — default 10
        """
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            context = request.data.get('context', {})
            limit   = int(request.data.get('limit', 10))
            recs    = hybrid_service.get_hybrid_recommendations(
                user=user, context=context, limit=limit,
            )
            return Response({'success': True, 'user_id': user_id,
                             'algorithm': 'hybrid', 'recommendations': recs,
                             'count': len(recs) if isinstance(recs, list) else 0})
        except Exception as e:
            logger.error("hybrid recommend error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def compare_algorithms(self, request):
        """
        Compare CF vs CB vs Hybrid recommendations for the same user side-by-side.

        Business value: lets tenants see exactly what each algorithm would show
        without having to run three separate API calls.

        POST body:
            user_id   (int)   — required
            context   (dict)  — optional
            limit     (int)   — default 10 per algorithm
        """
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            context = request.data.get('context', {})
            limit   = int(request.data.get('limit', 10))

            cf_recs = []
            cb_recs = []
            hy_recs = []
            cf_error = cb_error = hy_error = None

            try:
                cf_recs = collaborative_service.get_collaborative_recommendations(
                    user=user, context=context, limit=limit,
                )
            except Exception as e:
                cf_error = str(e)
                logger.warning("CF recommendations failed: %s", e)

            try:
                cb_recs = content_based_service.get_content_based_recommendations(
                    user=user, context=context, limit=limit,
                )
            except Exception as e:
                cb_error = str(e)
                logger.warning("CB recommendations failed: %s", e)

            try:
                hy_recs = hybrid_service.get_hybrid_recommendations(
                    user=user, context=context, limit=limit,
                )
            except Exception as e:
                hy_error = str(e)
                logger.warning("Hybrid recommendations failed: %s", e)

            return Response({
                'success': True,
                'user_id': user_id,
                'comparison': {
                    'collaborative_filtering': {
                        'recommendations': cf_recs,
                        'count': len(cf_recs) if isinstance(cf_recs, list) else 0,
                        'error': cf_error,
                    },
                    'content_based': {
                        'recommendations': cb_recs,
                        'count': len(cb_recs) if isinstance(cb_recs, list) else 0,
                        'error': cb_error,
                    },
                    'hybrid': {
                        'recommendations': hy_recs,
                        'count': len(hy_recs) if isinstance(hy_recs, list) else 0,
                        'error': hy_error,
                    },
                },
            })
        except Exception as e:
            logger.error("compare_algorithms error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def algorithm_weights(self, request):
        """
        Get current CF/CB weighting for the hybrid algorithm.
        Business value: transparency on how recommendations are blended.
        """
        try:
            weights = hybrid_service.get_algorithm_weights()
            metrics = hybrid_service.get_performance_metrics()
            return Response({'success': True, 'weights': weights, 'performance': metrics})
        except Exception as e:
            logger.error("algorithm_weights error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_weights(self, request):
        """
        Update CF/CB blending weights for the hybrid algorithm.

        POST body:
            collaborative_weight  (float 0–1)
            content_based_weight  (float 0–1)
            Note: both must sum to 1.0
        """
        try:
            cf_w = float(request.data.get('collaborative_weight', 0.5))
            cb_w = float(request.data.get('content_based_weight', 0.5))
            if abs(cf_w + cb_w - 1.0) > 0.01:
                return Response({'success': False,
                                 'error': 'collaborative_weight + content_based_weight must equal 1.0'},
                                status=status.HTTP_400_BAD_REQUEST)
            success = hybrid_service.update_weights(
                collaborative_weight=cf_w,
                content_based_weight=cb_w,
            )
            return Response({'success': success,
                             'new_weights': {'collaborative': cf_w, 'content_based': cb_w}})
        except Exception as e:
            logger.error("update_weights error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance_metrics(self, request):
        """
        Get performance metrics for all three algorithms.
        Business value: show which algorithm converts best.
        """
        try:
            cf_metrics = collaborative_service.get_performance_metrics()
            cb_metrics = content_based_service.get_performance_metrics()
            hy_metrics = hybrid_service.get_performance_metrics()
            return Response({
                'success': True,
                'algorithm_performance': {
                    'collaborative_filtering': cf_metrics,
                    'content_based':           cb_metrics,
                    'hybrid':                  hy_metrics,
                },
            })
        except Exception as e:
            logger.error("performance_metrics error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Health status of all personalization sub-services."""
        return Response({
            'success': True,
            'services': {
                'personalization':       personalization_service.health_check(),
                'collaborative_filter':  collaborative_service.health_check(),
                'content_based':         content_based_service.health_check(),
                'context_signal':        context_signal_service.health_check(),
                'hybrid':                hybrid_service.health_check(),
                'affinity':              affinity_service.health_check(),
            },
        })


# ─────────────────────────────────────────────────────────────────────────────
# CollaborativeFilterViewSet  ← NEW — direct CF API
# ─────────────────────────────────────────────────────────────────────────────

class CollaborativeFilterViewSet(viewsets.ViewSet):
    """
    Direct API for Collaborative Filtering recommendations.

    Business Value:
      - Power users who understand CF can tune it independently
      - QA teams can verify CF produces sensible recommendations
      - Analytics teams can pull CF-only outputs for analysis
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    @action(detail=False, methods=['post'])
    def recommend(self, request):
        """Get collaborative filtering recommendations for a user."""
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            limit = int(request.data.get('limit', 10))
            context = request.data.get('context', {})
            recs = collaborative_service.get_collaborative_recommendations(
                user=user, context=context, limit=limit,
            )
            return Response({'success': True, 'user_id': user_id,
                             'algorithm': 'collaborative_filtering',
                             'recommendations': recs,
                             'count': len(recs) if isinstance(recs, list) else 0})
        except Exception as e:
            logger.error("CF recommend error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def similar_users(self, request):
        """Find users similar to a given user based on behaviour history."""
        try:
            user_id = request.query_params.get('user_id')
            limit   = int(request.query_params.get('limit', 10))
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            similar = collaborative_service._get_similar_users(user, limit=limit)
            data = [{'user_id': u.id, 'username': u.username, 'similarity': sim}
                    for u, sim in similar]
            return Response({'success': True, 'user_id': user_id, 'similar_users': data})
        except Exception as e:
            logger.error("similar_users error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def rebuild_affinity(self, request):
        """Rebuild affinity scores for all users under this tenant."""
        try:
            updated = collaborative_service.update_affinity_scores()
            return Response({'success': True, 'updated_count': updated})
        except Exception as e:
            logger.error("rebuild_affinity error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Performance metrics for the CF algorithm."""
        try:
            m = collaborative_service.get_performance_metrics()
            return Response({'success': True, 'metrics': m})
        except Exception as e:
            logger.error("CF metrics error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# ContentBasedViewSet  ← NEW — direct CB API
# ─────────────────────────────────────────────────────────────────────────────

class ContentBasedViewSet(viewsets.ViewSet):
    """
    Direct API for Content-Based recommendations.

    Business Value:
      - Marketers can see what CB filtering recommends based on offer attributes
      - QA teams can verify content analysis is working
      - Content managers can trigger on-demand content re-analysis
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [RoutingEngineThrottle]

    @action(detail=False, methods=['post'])
    def recommend(self, request):
        """Get content-based recommendations for a user."""
        try:
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'success': False, 'error': 'user_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                user = User.objects.get(id=user_id)
                if user.tenant != request.user:
                    return Response({'success': False, 'error': 'User not in your tenant'},
                                    status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                return Response({'success': False, 'error': 'User not found'},
                                status=status.HTTP_404_NOT_FOUND)

            limit   = int(request.data.get('limit', 10))
            context = request.data.get('context', {})
            recs = content_based_service.get_content_based_recommendations(
                user=user, context=context, limit=limit,
            )
            return Response({'success': True, 'user_id': user_id,
                             'algorithm': 'content_based',
                             'recommendations': recs,
                             'count': len(recs) if isinstance(recs, list) else 0})
        except Exception as e:
            logger.error("CB recommend error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def analyze_offer(self, request):
        """
        Analyse the content features of a specific offer.
        Business value: content managers can see why an offer is recommended.
        """
        try:
            offer_id = request.data.get('offer_id')
            if not offer_id:
                return Response({'success': False, 'error': 'offer_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            analysis = content_based_service.analyze_offer_content(offer_id=offer_id)
            return Response({'success': True, 'offer_id': offer_id, 'content_analysis': analysis})
        except Exception as e:
            logger.error("analyze_offer (CB) error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def rebuild_vectors(self, request):
        """Rebuild all content-based preference vectors for this tenant."""
        try:
            rebuilt = content_based_service.rebuild_preference_vectors()
            return Response({'success': True, 'rebuilt_count': rebuilt})
        except Exception as e:
            logger.error("CB rebuild_vectors error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Performance metrics for the CB algorithm."""
        try:
            m = content_based_service.get_performance_metrics()
            return Response({'success': True, 'metrics': m})
        except Exception as e:
            logger.error("CB metrics error: %s", e, exc_info=True)
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
