"""viewsets.py – DRF ViewSets for the postback module."""
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .filters import NetworkPostbackConfigFilter, PostbackLogFilter
from .pagination import PostbackPagination, PostbackAnalyticsPagination, PostbackLogPagination
from .models import (
    DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog,
    PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit
)
from .permissions import IsPostbackAdmin, IsReadOnlyOrAdmin
from .serializers import (
    DuplicateLeadCheckSerializer,
    LeadValidatorSerializer,
    NetworkPostbackConfigDetailSerializer,
    NetworkPostbackConfigListSerializer,
    NetworkPostbackConfigWriteSerializer,
    PostbackLogDetailSerializer,
    PostbackLogSerializer,
    PostbackInsightSerializer,
    PostbackInsightDetailSerializer,
    PostbackTemplateSerializer,
    PostbackTemplateCreateSerializer,
    PostbackTemplateRenderSerializer,
    PostbackIPWhitelistSerializer,
    PostbackIPWhitelistCreateSerializer,
    PostbackRateLimitSerializer,
    PostbackRateLimitCreateSerializer,
)

logger = logging.getLogger(__name__)


class NetworkPostbackConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD for network postback configurations.
    Staff only. Secret key is write-only.
    """
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = NetworkPostbackConfigFilter
    search_fields = ["name", "network_key"]
    ordering_fields = ["name", "created_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        return NetworkPostbackConfig.objects.all().order_by("name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return NetworkPostbackConfigWriteSerializer
        if self.action == "retrieve":
            return NetworkPostbackConfigDetailSerializer
        return NetworkPostbackConfigListSerializer

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        """Switch a network to ACTIVE status."""
        from .choices import ValidatorStatus
        network = self.get_object()
        network.status = ValidatorStatus.ACTIVE
        network.save(update_fields=["status", "updated_at"])
        logger.info("Admin %s activated network %s", request.user.pk, network.network_key)
        return Response(NetworkPostbackConfigDetailSerializer(network).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        """Switch a network to INACTIVE status."""
        from .choices import ValidatorStatus
        network = self.get_object()
        network.status = ValidatorStatus.INACTIVE
        network.save(update_fields=["status", "updated_at"])
        logger.info("Admin %s deactivated network %s", request.user.pk, network.network_key)
        return Response(NetworkPostbackConfigDetailSerializer(network).data)

    @action(detail=True, methods=["get", "post"], url_path="validators")
    def validators(self, request, pk=None):
        """List or create LeadValidators for this network."""
        network = self.get_object()
        if request.method == "GET":
            qs = LeadValidator.objects.filter(network=network).order_by("sort_order")
            return Response(LeadValidatorSerializer(qs, many=True).data)
        # POST – create a new validator
        serializer = LeadValidatorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(network=network)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        """Quick stats for a specific network."""
        from django.db.models import Count, Q
        from .choices import PostbackStatus
        network = self.get_object()
        agg = PostbackLog.objects.filter(network=network).aggregate(
            total=Count("id"),
            rewarded=Count("id", filter=Q(status=PostbackStatus.REWARDED)),
            rejected=Count("id", filter=Q(status=PostbackStatus.REJECTED)),
            duplicate=Count("id", filter=Q(status=PostbackStatus.DUPLICATE)),
            failed=Count("id", filter=Q(status=PostbackStatus.FAILED)),
        )
        return Response({"network": network.network_key, **agg})


class PostbackLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only viewset for postback logs.
    Supports advanced filtering, search, and analytics.
    """
    pagination_class = PostbackLogPagination
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = PostbackLogFilter
    ordering_fields = ["received_at", "processed_at", "status", "payout"]
    ordering = ["-received_at"]

    def get_queryset(self):
        return PostbackLog.objects.select_related("network", "resolved_user").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostbackLogDetailSerializer
        return PostbackLogSerializer

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        """Re-queue a failed/rejected log for reprocessing."""
        from .tasks import process_postback
        from .choices import PostbackStatus
        log = self.get_object()
        if log.status not in (PostbackStatus.FAILED, PostbackStatus.REJECTED):
            return Response(
                {"detail": "Only FAILED or REJECTED logs can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        process_postback.delay(
            str(log.pk),
            signature="", timestamp_str="", nonce="",
            body_bytes_hex="", path="", query_params={},
        )
        logger.info("Admin %s retried postback log %s", request.user.pk, pk)
        return Response({"status": "queued"})

    @action(detail=True, methods=["get"], url_path="s2s-logs")
    def s2s_logs(self, request, pk=None):
        """List all outbound S2S postback attempts for this log entry."""
        from .models import PostbackS2SLog
        from .serializers import PostbackS2SLogSerializer
        log = self.get_object()
        qs = PostbackS2SLog.objects.filter(postback_log=log).order_by("-fired_at")
        return Response(PostbackS2SLogSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        """Mark this postback as reversed / charged back."""
        from .choices import PostbackStatus, PostbackConversionStatus
        log = self.get_object()
        if not log.lead_id:
            return Response(
                {"detail": "Cannot reverse a log with no lead_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .models import PostbackLog
        reversal = PostbackLog.objects.create(
            network=log.network,
            raw_payload=log.raw_payload,
            lead_id=log.lead_id,
            offer_id=log.offer_id,
            transaction_id=log.transaction_id,
            payout=-log.payout,
            currency=log.currency,
            source_ip=log.source_ip,
            status=PostbackStatus.REWARDED,
            is_reversal=True,
            reversed_log=log,
            conversion_status="reversed",
            method=log.method,
            request_headers={},
        )
        logger.info(
            "Admin %s created reversal %s for log %s",
            request.user.pk, reversal.pk, log.pk,
        )
        return Response({"status": "reversed", "reversal_id": str(reversal.pk)},
                        status=status.HTTP_201_CREATED)


class DuplicateLeadCheckViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Admin view of the dedup table.
    DELETE on a specific entry allows manual dedup clearance (re-allow a lead).
    """
    serializer_class = DuplicateLeadCheckSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ["-first_seen_at"]

    def get_queryset(self):
        return DuplicateLeadCheck.objects.select_related("network").all()


# ── New Model ViewSets ───────────────────────────────────────────────────────

class PostbackInsightViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only view for postback analytics and insights.
    Provides daily aggregated metrics and health scores.
    """
    pagination_class = PostbackAnalyticsPagination
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['network', 'date', 'anomaly_detected']
    ordering_fields = ['date', 'health_score', 'received_count', 'total_payout']
    ordering = ['-date']

    def get_queryset(self):
        return PostbackInsight.objects.select_related("network").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostbackInsightDetailSerializer
        return PostbackInsightSerializer

    @action(detail=True, methods=['post'])
    def detect_anomalies(self, request, pk=None):
        """Run anomaly detection for this insight."""
        from .services import PostbackInsightService
        insight = self.get_object()
        anomalies = PostbackInsightService.detect_anomalies(insight.network, insight.date)
        return Response({
            'anomalies_detected': bool(anomalies),
            'anomaly_details': anomalies,
        })

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """Force recalculation of this insight from raw postback logs."""
        from .services import PostbackInsightService
        insight = self.get_object()
        updated_insight = PostbackInsightService.recalculate_daily_insight(
            insight.network, insight.date
        )
        return Response(PostbackInsightDetailSerializer(updated_insight).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Aggregated metrics across all networks and time periods."""
        from django.db.models import Sum, Avg, Count, Q, Min, Max
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_received=Sum('received_count'),
            total_validated=Sum('validated_count'),
            total_rewarded=Sum('rewarded_count'),
            total_rejected=Sum('rejected_count'),
            total_duplicate=Sum('duplicate_count'),
            total_failed=Sum('failed_count'),
            total_payout=Sum('total_payout'),
            total_points=Sum('total_points_awarded'),
            avg_health_score=Avg('health_score'),
            networks_with_anomalies=Count('id', filter=Q(anomaly_detected=True)),
            total_networks=Count('network', distinct=True),
            date_range_start=Min('date'),
            date_range_end=Max('date'),
        )
        tr = agg['total_received'] or 0
        tv = agg['total_validated'] or 0
        tn = agg['total_networks'] or 0
        agg['validation_rate'] = round(tv / tr * 100, 2) if tr else 0.0
        agg['reward_rate'] = round((agg['total_rewarded'] or 0) / tv * 100, 2) if tv else 0.0
        agg['anomaly_rate'] = round((agg['networks_with_anomalies'] or 0) / tn * 100, 2) if tn else 0.0
        return Response(agg)

    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Time-series aggregation for trend analysis."""
        from django.db.models import Sum
        from django.db.models.functions import TruncDate, TruncHour
        qs = self.get_queryset()
        period = request.query_params.get('period', 'daily')
        trunc = TruncHour('date') if period == 'hourly' else TruncDate('date')
        data = (
            qs.annotate(period=trunc)
            .values('period')
            .annotate(
                total_received=Sum('received_count'),
                total_rewarded=Sum('rewarded_count'),
                total_rejected=Sum('rejected_count'),
                total_payout=Sum('total_payout'),
            )
            .order_by('period')
        )
        return Response(list(data))

    @action(detail=False, methods=['get'])
    def network_comparison(self, request):
        """Side-by-side metrics per network over a date range."""
        from django.db.models import Sum, Avg
        qs = self.get_queryset()
        data = (
            qs.values('network__name', 'network__network_key')
            .annotate(
                total_received=Sum('received_count'),
                total_rewarded=Sum('rewarded_count'),
                total_rejected=Sum('rejected_count'),
                total_payout=Sum('total_payout'),
                avg_health=Avg('health_score'),
            )
            .order_by('-total_received')
        )
        return Response(list(data))

    @action(detail=False, methods=['get'])
    def health_report(self, request):
        """Aggregate health scores and anomaly summary across networks."""
        from django.db.models import Avg, Count, Q, Min, Max
        qs = self.get_queryset()
        agg = qs.aggregate(
            avg_health=Avg('health_score'),
            min_health=Min('health_score'),
            max_health=Max('health_score'),
            total_anomalies=Count('id', filter=Q(anomaly_detected=True)),
            total_records=Count('id'),
        )
        anomalies = list(
            qs.filter(anomaly_detected=True)
            .values('network__network_key', 'date', 'anomaly_details', 'health_score')
            .order_by('-date')[:50]
        )
        return Response({'health_metrics': agg, 'recent_anomalies': anomalies})


class PostbackTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for postback templates.
    Supports template rendering and usage tracking.
    """
    pagination_class = PostbackPagination
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['network', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'usage_count', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return PostbackTemplate.objects.select_related("network").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostbackTemplateCreateSerializer
        return PostbackTemplateSerializer

    @action(detail=True, methods=['post'])
    def render(self, request, pk=None):
        """Render the template with provided context."""
        template = self.get_object()
        
        serializer = PostbackTemplateRenderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from .services import TemplateService
            rendered = TemplateService.render_template(
                str(template.id),
                serializer.validated_data['context'],
                serializer.validated_data['increment_usage']
            )
            
            return Response({
                'rendered_content': rendered,
                'template_name': template.name,
                'usage_count': template.usage_count
            })
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Clone this template with a new name."""
        template = self.get_object()
        
        new_name = request.data.get('name')
        if not new_name:
            return Response(
                {'error': 'New name is required for cloning'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .services import TemplateService
            cloned = TemplateService.clone_template(
                str(template.id),
                new_name
            )
            
            return Response(
                PostbackTemplateSerializer(cloned).data,
                status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def verify_integrity(self, request, pk=None):
        """Verify the integrity hash of this template."""
        template = self.get_object()
        is_valid = template.verify_integrity()
        
        return Response({
            'is_valid': is_valid,
            'template_name': template.name
        })


class PostbackIPWhitelistViewSet(viewsets.ModelViewSet):
    """
    CRUD for IP whitelist entries.
    Supports IP address and CIDR range management.
    """
    pagination_class = PostbackPagination
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['network', 'is_active']
    search_fields = ['name', 'ip_address', 'description']
    ordering_fields = ['name', 'priority', 'usage_count', 'created_at']
    ordering = ['-priority', 'name']

    def get_queryset(self):
        return PostbackIPWhitelist.objects.select_related("network").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostbackIPWhitelistCreateSerializer
        return PostbackIPWhitelistSerializer

    @action(detail=True, methods=['post'])
    def test_ip(self, request, pk=None):
        """Test if an IP address matches this whitelist rule."""
        whitelist = self.get_object()
        
        ip_address = request.data.get('ip_address')
        if not ip_address:
            return Response(
                {'error': 'IP address is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_allowed = whitelist.is_ip_allowed(ip_address)
        
        return Response({
            'ip_address': ip_address,
            'is_allowed': is_allowed,
            'rule_name': whitelist.name,
            'rule_priority': whitelist.priority
        })

    @action(detail=True, methods=['post'])
    def verify_integrity(self, request, pk=None):
        """Verify the integrity hash of this whitelist rule."""
        whitelist = self.get_object()
        is_valid = whitelist.verify_integrity()
        
        return Response({
            'is_valid': is_valid,
            'ip_address': whitelist.ip_address
        })


class PostbackRateLimitViewSet(viewsets.ModelViewSet):
    """
    CRUD for rate limit configurations.
    Provides real-time monitoring and violation tracking.
    """
    pagination_class = PostbackPagination
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['network', 'is_active', 'is_blocked']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'max_per_minute', 'total_violations', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return PostbackRateLimit.objects.select_related("network").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostbackRateLimitCreateSerializer
        return PostbackRateLimitSerializer

    @action(detail=True, methods=['post'])
    def reset_window(self, request, pk=None):
        """Reset the counting window for this rate limit."""
        rate_limit = self.get_object()
        rate_limit.reset_window()
        
        return Response({
            'message': 'Rate limit window reset successfully',
            'current_count': rate_limit.current_count,
            'window_start': rate_limit.window_start
        })

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Manually unblock this rate limit."""
        rate_limit = self.get_object()
        rate_limit.is_blocked = False
        rate_limit.blocked_until = None
        rate_limit.save(update_fields=['is_blocked', 'blocked_until', 'updated_at'])
        
        return Response({
            'message': 'Rate limit unblocked successfully',
            'is_blocked': rate_limit.is_blocked
        })

    @action(detail=True, methods=['post'])
    def verify_integrity(self, request, pk=None):
        """Verify the integrity hash of this rate limit."""
        rate_limit = self.get_object()
        is_valid = rate_limit.verify_integrity()
        
        return Response({
            'is_valid': is_valid,
            'rate_limit_name': rate_limit.name
        })
