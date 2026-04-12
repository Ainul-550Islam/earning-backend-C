"""
Proxy Intelligence Views
=========================
REST API endpoints for the proxy intelligence module.
"""

import logging
import time
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Avg, Q
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    IPIntelligence, VPNDetectionLog, ProxyDetectionLog, TorExitNode,
    DatacenterIPRange, FraudAttempt, ClickFraudRecord, DeviceFingerprint,
    MultiAccountLink, IPBlacklist, IPWhitelist, ThreatFeedProvider,
    MaliciousIPDatabase, UserRiskProfile, MLModelMetadata, AnomalyDetectionLog,
    FraudRule, AlertConfiguration, APIRequestLog, SystemAuditTrail
)
from .serializers import (
    IPIntelligenceSerializer, IPIntelligenceSummarySerializer,
    VPNDetectionLogSerializer, ProxyDetectionLogSerializer,
    TorExitNodeSerializer, DatacenterIPRangeSerializer,
    FraudAttemptSerializer, ClickFraudRecordSerializer,
    DeviceFingerprintSerializer, MultiAccountLinkSerializer,
    IPBlacklistSerializer, IPWhitelistSerializer,
    ThreatFeedProviderSerializer, MaliciousIPDatabaseSerializer,
    UserRiskProfileSerializer, MLModelMetadataSerializer,
    AnomalyDetectionLogSerializer, FraudRuleSerializer,
    AlertConfigurationSerializer, APIRequestLogSerializer,
    SystemAuditTrailSerializer,
    IPCheckRequestSerializer, IPCheckResponseSerializer, BulkIPCheckSerializer
)
from .services import (
    IPIntelligenceService, BlacklistService, RiskScoringService, VelocityService
)
from .exceptions import InvalidIPAddress

logger = logging.getLogger(__name__)


class ProxyIntelligencePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


# ==================================================================
# IP Intelligence
# ==================================================================

class IPIntelligenceViewSet(viewsets.ModelViewSet):
    """Full CRUD + extra actions for IP Intelligence records."""
    queryset = IPIntelligence.objects.all().order_by('-last_checked')
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['risk_level', 'is_vpn', 'is_proxy', 'is_tor', 'is_datacenter', 'country_code']
    search_fields = ['ip_address', 'isp', 'asn', 'country_name']
    ordering_fields = ['risk_score', 'last_checked', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return IPIntelligenceSummarySerializer
        return IPIntelligenceSerializer

    @action(detail=False, methods=['post'], url_path='check')
    def check_ip(self, request):
        """Check a single IP address."""
        serializer = IPCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = serializer.validated_data['ip_address']
        tenant = getattr(request, 'tenant', None)
        user = request.user if request.user.is_authenticated else None

        start = time.time()
        try:
            svc = IPIntelligenceService(tenant=tenant)
            result = svc.full_check(ip, user=user)
            result['response_time_ms'] = round((time.time() - start) * 1000, 2)
            return Response(result, status=status.HTTP_200_OK)
        except InvalidIPAddress as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"IP check failed for {ip}: {e}")
            return Response({'error': 'Detection service error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='bulk-check')
    def bulk_check(self, request):
        """Check multiple IPs at once (max 100)."""
        serializer = BulkIPCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ips = serializer.validated_data['ip_addresses']
        tenant = getattr(request, 'tenant', None)
        svc = IPIntelligenceService(tenant=tenant)
        results = []
        for ip in ips:
            try:
                results.append(svc.full_check(ip))
            except Exception as e:
                results.append({'ip_address': ip, 'error': str(e)})

        return Response({'results': results, 'total': len(results)})

    @action(detail=False, methods=['get'], url_path='high-risk')
    def high_risk_ips(self, request):
        """Return IPs with risk_score >= 61."""
        threshold = int(request.query_params.get('threshold', 61))
        qs = IPIntelligence.objects.filter(risk_score__gte=threshold).order_by('-risk_score')[:100]
        serializer = IPIntelligenceSummarySerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Dashboard statistics."""
        qs = IPIntelligence.objects.all()
        return Response({
            'total': qs.count(),
            'vpn': qs.filter(is_vpn=True).count(),
            'proxy': qs.filter(is_proxy=True).count(),
            'tor': qs.filter(is_tor=True).count(),
            'datacenter': qs.filter(is_datacenter=True).count(),
            'high_risk': qs.filter(risk_score__gte=61).count(),
            'avg_risk_score': qs.aggregate(avg=Avg('risk_score'))['avg'] or 0,
        })


# ==================================================================
# Blacklist & Whitelist
# ==================================================================

class IPBlacklistViewSet(viewsets.ModelViewSet):
    queryset = IPBlacklist.objects.filter(is_active=True).order_by('-created_at')
    serializer_class = IPBlacklistSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['reason', 'is_permanent', 'is_active']
    search_fields = ['ip_address', 'description']

    @action(detail=False, methods=['post'], url_path='bulk-add')
    def bulk_add(self, request):
        """Add multiple IPs to the blacklist."""
        ips = request.data.get('ip_addresses', [])
        reason = request.data.get('reason', 'manual')
        tenant = getattr(request, 'tenant', None)
        added = []
        for ip in ips:
            try:
                entry = BlacklistService.add_to_blacklist(
                    ip_address=ip, reason=reason, tenant=tenant,
                    blocked_by=request.user
                )
                added.append(ip)
            except Exception as e:
                logger.warning(f"Could not blacklist {ip}: {e}")
        return Response({'added': added, 'count': len(added)})

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        entry = self.get_object()
        entry.is_active = False
        entry.save(update_fields=['is_active'])
        cache.delete(f"pi:blacklist:{entry.ip_address}")
        return Response({'status': 'deactivated'})


class IPWhitelistViewSet(viewsets.ModelViewSet):
    queryset = IPWhitelist.objects.filter(is_active=True).order_by('label')
    serializer_class = IPWhitelistSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['ip_address', 'label', 'description']


# ==================================================================
# Detection Logs
# ==================================================================

class VPNDetectionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VPNDetectionLog.objects.all().order_by('-created_at')
    serializer_class = VPNDetectionLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_confirmed']
    search_fields = ['ip_address', 'vpn_provider']


class ProxyDetectionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProxyDetectionLog.objects.all().order_by('-created_at')
    serializer_class = ProxyDetectionLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['proxy_type', 'is_anonymous']


class TorExitNodeViewSet(viewsets.ModelViewSet):
    queryset = TorExitNode.objects.filter(is_active=True)
    serializer_class = TorExitNodeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']

    @action(detail=False, methods=['post'], url_path='sync')
    def sync_from_tor_project(self, request):
        """Trigger Tor exit node list refresh."""
        from .detection_engines.tor_detector import TorDetector
        try:
            count = TorDetector.sync_exit_nodes()
            return Response({'synced': count, 'status': 'success'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DatacenterIPRangeViewSet(viewsets.ModelViewSet):
    queryset = DatacenterIPRange.objects.filter(is_active=True)
    serializer_class = DatacenterIPRangeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['cidr', 'provider_name']


# ==================================================================
# Fraud
# ==================================================================

class FraudAttemptViewSet(viewsets.ModelViewSet):
    queryset = FraudAttempt.objects.all().order_by('-created_at')
    serializer_class = FraudAttemptSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['fraud_type', 'status']
    search_fields = ['ip_address', 'description']

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        attempt = self.get_object()
        notes = request.data.get('notes', '')
        is_false_positive = request.data.get('is_false_positive', False)
        attempt.status = 'false_positive' if is_false_positive else 'resolved'
        attempt.resolved_by = request.user
        attempt.resolved_at = timezone.now()
        attempt.resolution_notes = notes
        attempt.save()
        return Response(FraudAttemptSerializer(attempt).data)


class UserRiskProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserRiskProfile.objects.all().order_by('-overall_risk_score')
    serializer_class = UserRiskProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['risk_level', 'is_high_risk', 'is_under_review']

    @action(detail=False, methods=['get'], url_path='distribution')
    def distribution(self, request):
        return Response(
            UserRiskProfile.objects.values('risk_level')
            .annotate(count=Count('id'))
            .order_by('risk_level')
        )


# ==================================================================
# Threat Intelligence
# ==================================================================

class ThreatFeedProviderViewSet(viewsets.ModelViewSet):
    queryset = ThreatFeedProvider.objects.all().order_by('priority')
    serializer_class = ThreatFeedProviderSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class MaliciousIPDatabaseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaliciousIPDatabase.objects.filter(is_active=True).order_by('-last_reported')
    serializer_class = MaliciousIPDatabaseSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['threat_type', 'threat_feed']
    search_fields = ['ip_address']


# ==================================================================
# AI/ML
# ==================================================================

class MLModelMetadataViewSet(viewsets.ModelViewSet):
    queryset = MLModelMetadata.objects.all().order_by('-trained_at')
    serializer_class = MLModelMetadataSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        model = self.get_object()
        # Deactivate others of same type
        MLModelMetadata.objects.filter(model_type=model.model_type).update(is_active=False)
        model.is_active = True
        model.save(update_fields=['is_active'])
        return Response({'status': 'activated', 'model': self.get_serializer(model).data})


class AnomalyDetectionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AnomalyDetectionLog.objects.all().order_by('-created_at')
    serializer_class = AnomalyDetectionLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['anomaly_type', 'is_investigated']


# ==================================================================
# Config
# ==================================================================

class FraudRuleViewSet(viewsets.ModelViewSet):
    queryset = FraudRule.objects.all().order_by('priority')
    serializer_class = FraudRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['condition_type', 'action', 'is_active']


class AlertConfigurationViewSet(viewsets.ModelViewSet):
    queryset = AlertConfiguration.objects.all().order_by('name')
    serializer_class = AlertConfigurationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ==================================================================
# Audit & Logs
# ==================================================================

class APIRequestLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = APIRequestLog.objects.all().order_by('-created_at')
    serializer_class = APIRequestLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status_code', 'method']
    search_fields = ['ip_address', 'endpoint']


class SystemAuditTrailViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemAuditTrail.objects.all().order_by('-created_at')
    serializer_class = SystemAuditTrailSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = ProxyIntelligencePagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['action', 'model_name']


# ==================================================================
# Dashboard
# ==================================================================

class ProxyIntelligenceDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .models import (
            IPIntelligence, IPBlacklist, FraudAttempt,
            TorExitNode, MaliciousIPDatabase, AnomalyDetectionLog
        )
        return Response({
            'ip_intelligence': {
                'total': IPIntelligence.objects.count(),
                'high_risk': IPIntelligence.objects.filter(risk_score__gte=61).count(),
                'vpn': IPIntelligence.objects.filter(is_vpn=True).count(),
                'tor': IPIntelligence.objects.filter(is_tor=True).count(),
            },
            'blacklist': {
                'total_active': IPBlacklist.objects.filter(is_active=True).count(),
            },
            'fraud': {
                'total': FraudAttempt.objects.count(),
                'pending': FraudAttempt.objects.filter(status='detected').count(),
            },
            'threat_intel': {
                'tor_exit_nodes': TorExitNode.objects.filter(is_active=True).count(),
                'malicious_ips': MaliciousIPDatabase.objects.filter(is_active=True).count(),
            },
            'anomalies': {
                'recent_24h': AnomalyDetectionLog.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(hours=24)
                ).count(),
            },
        })
