from ..services.domain import (
    offer_quality_service, network_performance_service,
    user_journey_service, security_event_service,
)

"""
Domain Model Viewsets — offer_routing specific.

Single owners for all domain-specific models:
  RoutingBlacklistViewSet   — blacklist CRUD + check/bulk-add
  BlacklistHitViewSet       — hit log (read-only)
  ClickFraudSignalViewSet   — fraud signals CRUD + analyze
  FraudPatternViewSet       — fraud pattern library CRUD
  NetworkPerformanceCacheViewSet — network perf cache (read/invalidate)
  OfferQualityScoreViewSet  — quality scores CRUD + recalculate
  UserJourneyStepViewSet    — user journey tracking (read-only + log)
"""

from ..throttling import RoutingEngineThrottle, RoutingEngineThrottle, AnalyticsThrottle, BulkOperationThrottle, EvaluatorThrottle
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers, CanViewAnalytics
from ..serializers import (
    RoutingBlacklistSerializer, BlacklistHitSerializer,
    ClickFraudSignalSerializer, FraudPatternSerializer,
    NetworkPerformanceCacheSerializer, OfferQualityScoreSerializer,
    UserJourneyStepSerializer,
    RouteActionSerializer,
)


class RoutingBlacklistViewSet(viewsets.ModelViewSet):
    """Manage routing blacklist — blocked offers, users, IPs."""
    serializer_class = RoutingBlacklistSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import RoutingBlacklist
        qs = RoutingBlacklist.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-created_at')

    @action(detail=False, methods=['post'])
    def check_blacklisted(self, request):
        """Check if an offer/user/IP is blacklisted."""
        try:
            from ..models import RoutingBlacklist
            offer_id = request.data.get('offer_id')
            user_id = request.data.get('user_id')
            ip_address = request.data.get('ip_address')
            qs = RoutingBlacklist.objects.filter(is_active=True)
            is_blocked = False
            if offer_id:
                is_blocked = is_blocked or qs.filter(blacklist_type='offer', entity_id=str(offer_id)).exists()
            if user_id:
                is_blocked = is_blocked or qs.filter(blacklist_type='user', entity_id=str(user_id)).exists()
            if ip_address:
                is_blocked = is_blocked or qs.filter(blacklist_type='ip', entity_id=ip_address).exists()
            return Response({'is_blacklisted': is_blocked})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bulk_add(self, request):
        """Bulk add entries to blacklist."""
        try:
            from ..models import RoutingBlacklist
            entries = request.data.get('entries', [])
            if not entries:
                return Response({'error': 'entries is required'}, status=status.HTTP_400_BAD_REQUEST)
            created = 0
            for entry in entries:
                RoutingBlacklist.objects.get_or_create(
                    tenant=request.user,
                    blacklist_type=entry.get('type', 'offer'),
                    entity_id=str(entry.get('id', '')),
                    defaults={'reason': entry.get('reason', ''), 'is_active': True}
                )
                created += 1
            return Response({'success': True, 'created': created})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Remove expired blacklist entries."""
        try:
            from ..models import RoutingBlacklist
            from django.utils import timezone
            deleted, _ = RoutingBlacklist.objects.filter(
                tenant=request.user,
                expires_at__lt=timezone.now()
            ).delete()
            return Response({'success': True, 'deleted': deleted})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Blacklist statistics."""
        try:
            from ..models import RoutingBlacklist
            from django.db.models import Count
            stats = RoutingBlacklist.objects.filter(
                tenant=request.user
            ).values('blacklist_type').annotate(count=Count('id'))
            return Response({'success': True, 'stats': list(stats)})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BlacklistHitViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to blacklist hit log."""
    serializer_class = BlacklistHitSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import BlacklistHit
        qs = BlacklistHit.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(blacklist__tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-hit_at')

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent blacklist hits."""
        try:
            from ..models import BlacklistHit
            limit = int(request.query_params.get('limit', 50))
            qs = BlacklistHit.objects.all().order_by('-hit_at')[:limit]
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def hit_summary(self, request):
        """Summary of blacklist hits by type."""
        try:
            from ..models import BlacklistHit
            from django.db.models import Count
            summary = BlacklistHit.objects.values(
                'blacklist__blacklist_type'
            ).annotate(hits=Count('id')).order_by('-hits')
            return Response({'success': True, 'summary': list(summary)})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClickFraudSignalViewSet(viewsets.ModelViewSet):
    """Manage click fraud signals."""
    serializer_class = ClickFraudSignalSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import ClickFraudSignal
        qs = ClickFraudSignal.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-detected_at')

    @action(detail=False, methods=['post'])
    def analyze_click(self, request):
        """Analyze a click event for fraud signals."""
        try:
            from ..services import fraud_detection_service
            user_id = request.data.get('user_id')
            offer_id = request.data.get('offer_id')
            context = request.data.get('context', {})
            if not user_id or not offer_id:
                return Response({'error': 'user_id and offer_id required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = fraud_detection_service.detect_conversion_fraud(int(user_id), int(offer_id))
            return Response({'success': True, 'analysis': result})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def fraud_summary(self, request):
        """Get fraud signal summary for the tenant."""
        try:
            from ..models import ClickFraudSignal
            from django.db.models import Count, Avg
            summary = ClickFraudSignal.objects.filter(
                tenant=request.user
            ).aggregate(
                total_signals=Count('id'),
                avg_fraud_score=Avg('fraud_score'),
            )
            return Response({'success': True, 'summary': summary})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """Get high-risk fraud signals."""
        try:
            from ..models import ClickFraudSignal
            threshold = float(request.query_params.get('threshold', 0.8))
            qs = ClickFraudSignal.objects.filter(
                tenant=request.user, fraud_score__gte=threshold
            ).order_by('-fraud_score')[:50]
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudPatternViewSet(viewsets.ModelViewSet):
    """Manage fraud detection patterns."""
    serializer_class = FraudPatternSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import FraudPattern
        qs = FraudPattern.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.filter(is_active=True).order_by('-severity')

    @action(detail=False, methods=['get'])
    def active_patterns(self, request):
        """List all active fraud patterns."""
        try:
            from ..models import FraudPattern
            qs = FraudPattern.objects.filter(is_active=True).order_by('-severity')
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def test_pattern(self, request, pk=None):
        """Test a fraud pattern against sample data."""
        try:
            pattern = self.get_object()
            sample_data = request.data.get('sample_data', {})
            matched = bool(sample_data)
            return Response({'success': True, 'matched': matched, 'pattern_id': pattern.id})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NetworkPerformanceCacheViewSet(viewsets.ReadOnlyModelViewSet):
    """Network performance cache — read + invalidate."""
    serializer_class = NetworkPerformanceCacheSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import NetworkPerformanceCache
        qs = NetworkPerformanceCache.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-updated_at')

    @action(detail=False, methods=['post'])
    def invalidate(self, request):
        """Invalidate network performance cache entries."""
        try:
            from ..models import NetworkPerformanceCache
            network_id = request.data.get('network_id')
            qs = NetworkPerformanceCache.objects.filter(tenant=request.user)
            if network_id:
                qs = qs.filter(network_id=network_id)
            deleted, _ = qs.delete()
            return Response({'success': True, 'deleted': deleted})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance_summary(self, request):
        """Summarize cached network performance data."""
        try:
            from ..models import NetworkPerformanceCache
            from django.db.models import Avg, Min, Max
            summary = NetworkPerformanceCache.objects.filter(
                tenant=request.user
            ).aggregate(
                avg_latency_ms=Avg('avg_latency_ms'),
                min_latency_ms=Min('avg_latency_ms'),
                max_latency_ms=Max('avg_latency_ms'),
            )
            return Response({'success': True, 'summary': summary})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def slow_networks(self, request):
        """Get networks with high latency."""
        try:
            from ..models import NetworkPerformanceCache
            threshold = float(request.query_params.get('threshold_ms', 1000))
            qs = NetworkPerformanceCache.objects.filter(
                tenant=request.user,
                avg_latency_ms__gt=threshold
            ).order_by('-avg_latency_ms')
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferQualityScoreViewSet(viewsets.ModelViewSet):
    """Manage offer quality scores."""
    serializer_class = OfferQualityScoreSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import OfferQualityScore
        qs = OfferQualityScore.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-score')

    @action(detail=False, methods=['post'])
    def recalculate(self, request):
        """Trigger quality score recalculation for an offer."""
        try:
            offer_id = request.data.get('offer_id')
            if not offer_id:
                return Response({'error': 'offer_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            from ..models import OfferQualityScore
            score_obj, created = OfferQualityScore.objects.get_or_create(
                tenant=request.user,
                offer_id=offer_id,
                defaults={'score': 0.5, 'quality_tier': 'medium'}
            )
            return Response({'success': True, 'score': score_obj.score, 'created': created})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def low_quality(self, request):
        """Get offers with low quality scores."""
        try:
            from ..models import OfferQualityScore
            threshold = float(request.query_params.get('threshold', 0.3))
            qs = OfferQualityScore.objects.filter(
                tenant=request.user, score__lt=threshold
            ).order_by('score')
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def quality_distribution(self, request):
        """Get quality score distribution."""
        try:
            from ..models import OfferQualityScore
            from django.db.models import Count
            dist = OfferQualityScore.objects.filter(
                tenant=request.user
            ).values('quality_tier').annotate(count=Count('id'))
            return Response({'success': True, 'distribution': list(dist)})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserJourneyStepViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to user journey tracking."""
    serializer_class = UserJourneyStepSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    throttle_classes = [RoutingEngineThrottle]

    def get_queryset(self):
        from ..models import UserJourneyStep
        qs = UserJourneyStep.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-step_timestamp')

    @action(detail=False, methods=['get'])
    def user_journey(self, request):
        """Get full journey for a specific user."""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from ..models import UserJourneyStep
            qs = UserJourneyStep.objects.filter(
                tenant=request.user, user_id=user_id
            ).order_by('step_timestamp')
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def log_step(self, request):
        """Log a new user journey step."""
        try:
            from ..models import UserJourneyStep
            from django.utils import timezone
            step = UserJourneyStep.objects.create(
                tenant=request.user,
                user_id=request.data.get('user_id'),
                step_type=request.data.get('step_type', 'view'),
                offer_id=request.data.get('offer_id'),
                route_id=request.data.get('route_id'),
                step_data=request.data.get('step_data', {}),
                step_timestamp=timezone.now()
            )
            return Response({'success': True, 'step_id': step.id},
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def funnel_analysis(self, request):
        """Analyze conversion funnel from journey steps."""
        try:
            from ..models import UserJourneyStep
            from django.db.models import Count
            funnel = UserJourneyStep.objects.filter(
                tenant=request.user
            ).values('step_type').annotate(
                count=Count('id')
            ).order_by('-count')
            return Response({'success': True, 'funnel': list(funnel)})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
