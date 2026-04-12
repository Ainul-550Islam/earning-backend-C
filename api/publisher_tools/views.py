# api/publisher_tools/views.py
"""
Publisher Tools — DRF ViewSets।
সব CRUD + custom actions এখানে।
"""
from decimal import Decimal
from datetime import date

from django.db.models import Sum, Avg, Count, Q, Prefetch
from django.utils import timezone
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from core.views import BaseViewSet
from .models import (
    Publisher, Site, App, InventoryVerification,
    AdUnit, AdPlacement, AdUnitTargeting,
    MediationGroup, WaterfallItem, HeaderBiddingConfig,
    PublisherEarning, PayoutThreshold, PublisherInvoice,
    TrafficSafetyLog, SiteQualityMetric,
)
from .serializers import (
    PublisherCreateSerializer, PublisherUpdateSerializer,
    PublisherListSerializer, PublisherDetailSerializer, PublisherStatsSerializer,
    SiteCreateSerializer, SiteUpdateSerializer,
    SiteListSerializer, SiteDetailSerializer, SiteVerifySerializer,
    AppCreateSerializer, AppUpdateSerializer,
    AppListSerializer, AppDetailSerializer,
    InventoryVerificationSerializer, VerifyInventorySerializer,
    AdUnitCreateSerializer, AdUnitUpdateSerializer,
    AdUnitListSerializer, AdUnitDetailSerializer,
    AdPlacementSerializer, AdPlacementCreateSerializer,
    AdUnitTargetingSerializer,
    MediationGroupSerializer,
    WaterfallItemSerializer, WaterfallReorderSerializer,
    HeaderBiddingConfigSerializer,
    PublisherEarningSerializer, EarningsSummarySerializer,
    PayoutThresholdSerializer,
    PublisherInvoiceListSerializer, PublisherInvoiceDetailSerializer,
    InvoiceDisputeSerializer,
    TrafficSafetyLogSerializer, FraudActionSerializer, MarkFalsePositiveSerializer,
    SiteQualityMetricSerializer, QualityTrendSerializer,
    DateRangeSerializer, ReportFilterSerializer,
)
from .permissions import (
    IsPublisher, IsPublisherOwner, IsAdminOrPublisher,
    CanManageAdUnit, CanManageSite, CanManageApp,
    CanViewEarnings, IsVerifiedPublisher,
)
from .services import (
    PublisherService, SiteService, AppService,
    AdUnitService, MediationService,
    EarningService, InvoiceService,
    FraudDetectionService, QualityMetricService,
)
from .utils import get_date_range


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class PublisherViewSet(BaseViewSet):
    """
    Publisher profile CRUD।
    list/create: admin only।
    retrieve/update: publisher নিজে বা admin।
    """
    queryset = Publisher.objects.select_related('user').all()

    def get_permissions(self):
        if self.action in ('list',):
            return [IsAdminUser()]
        if self.action in ('create',):
            return [IsAuthenticated()]
        return [IsAdminOrPublisher()]

    def get_serializer_class(self):
        if self.action == 'create':
            return PublisherCreateSerializer
        if self.action in ('update', 'partial_update'):
            return PublisherUpdateSerializer
        if self.action == 'list':
            return PublisherListSerializer
        return PublisherDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            # Publisher শুধু নিজেরটা দেখবে
            try:
                return qs.filter(user=self.request.user)
            except Exception:
                return qs.none()
        # Admin filters
        params = self.request.query_params
        status_f = params.get('status')
        tier_f   = params.get('tier')
        country  = params.get('country')
        if status_f:
            qs = qs.filter(status=status_f)
        if tier_f:
            qs = qs.filter(tier=tier_f)
        if country:
            qs = qs.filter(country__icontains=country)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = PublisherCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        publisher = PublisherService.create_publisher(request.user, serializer.validated_data)
        return self.success_response(
            data=PublisherDetailSerializer(publisher).data,
            message='Publisher profile created successfully.',
            status_code=201,
        )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Publisher dashboard stats"""
        publisher = self.get_object()
        period = request.query_params.get('period', 'last_30_days')
        stats = PublisherService.get_publisher_dashboard_stats(publisher, period)
        return self.success_response(data=stats)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Publisher approve করে (admin only)"""
        publisher = self.get_object()
        publisher = PublisherService.approve_publisher(publisher, approved_by=request.user)
        return self.success_response(
            data=PublisherDetailSerializer(publisher).data,
            message='Publisher approved successfully.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def suspend(self, request, pk=None):
        """Publisher suspend করে (admin only)"""
        publisher = self.get_object()
        reason = request.data.get('reason', '')
        publisher = PublisherService.suspend_publisher(publisher, reason)
        return self.success_response(
            data=PublisherDetailSerializer(publisher).data,
            message='Publisher suspended.'
        )

    @action(detail=True, methods=['post'])
    def regenerate_api_key(self, request, pk=None):
        """API key regenerate করে"""
        publisher = self.get_object()
        self.check_object_permissions(request, publisher)
        publisher = PublisherService.regenerate_api_key(publisher)
        return self.success_response(
            data={'api_key': publisher.api_key, 'api_secret': publisher.api_secret},
            message='API key regenerated. Store your new secret securely.'
        )

    @action(detail=True, methods=['get'])
    def payout_eligibility(self, request, pk=None):
        """Payout eligibility check করে"""
        publisher = self.get_object()
        eligibility = InvoiceService.check_payout_eligibility(publisher)
        return self.success_response(data=eligibility)


# ──────────────────────────────────────────────────────────────────────────────
# SITE VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class SiteViewSet(BaseViewSet):
    """Site management ViewSet"""
    queryset = Site.objects.select_related('publisher', 'approved_by').all()

    def get_permissions(self):
        if self.action in ('create',):
            return [IsPublisher()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsPublisher(), CanManageSite()]
        if self.action in ('approve', 'reject'):
            return [IsAdminUser()]
        return [IsAdminOrPublisher()]

    def get_serializer_class(self):
        if self.action == 'create':
            return SiteCreateSerializer
        if self.action in ('update', 'partial_update'):
            return SiteUpdateSerializer
        if self.action == 'list':
            return SiteListSerializer
        return SiteDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        # Admin filters
        params = self.request.query_params
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('category'):
            qs = qs.filter(category=params['category'])
        if params.get('publisher_id'):
            qs = qs.filter(publisher__publisher_id=params['publisher_id'])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = SiteCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        publisher = request.user.publisher_profile
        site = SiteService.register_site(publisher, serializer.validated_data)
        return self.success_response(
            data=SiteDetailSerializer(site).data,
            message='Site registered. Please complete domain verification.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Site ownership verification trigger করে"""
        site = self.get_object()
        serializer = SiteVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        method = serializer.validated_data['method']
        result = SiteService.verify_site(site, method)
        return self.success_response(
            data={
                'verified': result['success'],
                'message': result['message'],
                'status': result['verification'].status,
            }
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Site approve করে (admin only)"""
        site = self.get_object()
        site = SiteService.approve_site(site, approved_by=request.user)
        return self.success_response(
            data=SiteDetailSerializer(site).data,
            message='Site approved.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Site reject করে (admin only)"""
        site = self.get_object()
        reason = request.data.get('reason', 'Does not meet content guidelines.')
        site = SiteService.reject_site(site, reason)
        return self.success_response(
            data=SiteDetailSerializer(site).data,
            message='Site rejected.'
        )

    @action(detail=True, methods=['post'])
    def refresh_ads_txt(self, request, pk=None):
        """ads.txt refresh করে"""
        site = self.get_object()
        success = SiteService.refresh_ads_txt(site)
        return self.success_response(
            data={'ads_txt_verified': success},
            message='ads.txt refreshed.' if success else 'ads.txt not found on server.'
        )

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Site analytics data"""
        site = self.get_object()
        serializer = DateRangeSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = SiteService.get_site_analytics(
            site,
            serializer.validated_data['start_date'],
            serializer.validated_data['end_date'],
        )
        return self.success_response(data=result)

    @action(detail=True, methods=['get'])
    def quality_metrics(self, request, pk=None):
        """Site quality metrics"""
        site = self.get_object()
        days = int(request.query_params.get('days', 30))
        trend = QualityMetricService.get_quality_trend(site, days)
        latest = SiteQualityMetric.objects.filter(site=site).order_by('-date').first()
        return self.success_response(data={
            'latest': SiteQualityMetricSerializer(latest).data if latest else None,
            'trend': trend,
        })

    @action(detail=True, methods=['get'])
    def ad_units(self, request, pk=None):
        """Site-এর সব Ad Units"""
        site = self.get_object()
        units = AdUnit.objects.filter(site=site).order_by('-created_at')
        return self.success_response(
            data=AdUnitListSerializer(units, many=True).data
        )


# ──────────────────────────────────────────────────────────────────────────────
# APP VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class AppViewSet(BaseViewSet):
    """App management ViewSet"""
    queryset = App.objects.select_related('publisher', 'approved_by').all()

    def get_permissions(self):
        if self.action in ('create',):
            return [IsPublisher()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsPublisher(), CanManageApp()]
        if self.action in ('approve', 'reject'):
            return [IsAdminUser()]
        return [IsAdminOrPublisher()]

    def get_serializer_class(self):
        if self.action == 'create':
            return AppCreateSerializer
        if self.action in ('update', 'partial_update'):
            return AppUpdateSerializer
        if self.action == 'list':
            return AppListSerializer
        return AppDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('platform'):
            qs = qs.filter(platform=params['platform'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('publisher_id'):
            qs = qs.filter(publisher__publisher_id=params['publisher_id'])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AppCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        publisher = request.user.publisher_profile
        app = AppService.register_app(publisher, serializer.validated_data)
        return self.success_response(
            data=AppDetailSerializer(app).data,
            message='App registered. Pending review.',
            status_code=201,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        app = self.get_object()
        app = AppService.approve_app(app, approved_by=request.user)
        return self.success_response(data=AppDetailSerializer(app).data, message='App approved.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        app = self.get_object()
        reason = request.data.get('reason', 'Does not meet app store guidelines.')
        app = AppService.reject_app(app, reason)
        return self.success_response(data=AppDetailSerializer(app).data, message='App rejected.')

    @action(detail=True, methods=['get'])
    def ad_units(self, request, pk=None):
        """App-এর সব Ad Units"""
        app = self.get_object()
        units = AdUnit.objects.filter(app=app).order_by('-created_at')
        return self.success_response(data=AdUnitListSerializer(units, many=True).data)


# ──────────────────────────────────────────────────────────────────────────────
# INVENTORY VERIFICATION VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class InventoryVerificationViewSet(BaseViewSet):
    """Inventory verification management"""
    queryset = InventoryVerification.objects.select_related('publisher', 'site', 'app').all()
    serializer_class = InventoryVerificationSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        return qs

    @action(detail=True, methods=['post'])
    def check(self, request, pk=None):
        """Verification status re-check করে"""
        verification = self.get_object()
        if verification.site:
            result = SiteService.verify_site(verification.site, verification.method)
        else:
            result = {'success': False, 'message': 'App verification not yet supported.'}
        return self.success_response(data={
            'verified': result['success'],
            'message': result['message'],
        })


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class AdUnitViewSet(BaseViewSet):
    """Ad Unit CRUD + performance actions"""
    queryset = AdUnit.objects.select_related('publisher', 'site', 'app').all()

    def get_permissions(self):
        if self.action in ('create',):
            return [IsPublisher()]
        if self.action in ('update', 'partial_update', 'destroy', 'pause', 'activate'):
            return [IsPublisher(), CanManageAdUnit()]
        return [IsAdminOrPublisher()]

    def get_serializer_class(self):
        if self.action == 'create':
            return AdUnitCreateSerializer
        if self.action in ('update', 'partial_update'):
            return AdUnitUpdateSerializer
        if self.action == 'list':
            return AdUnitListSerializer
        return AdUnitDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('format'):
            qs = qs.filter(format=params['format'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('inventory_type'):
            qs = qs.filter(inventory_type=params['inventory_type'])
        if params.get('site_id'):
            qs = qs.filter(site__site_id=params['site_id'])
        if params.get('app_id'):
            qs = qs.filter(app__app_id=params['app_id'])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AdUnitCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        publisher = request.user.publisher_profile
        ad_unit = AdUnitService.create_ad_unit(publisher, serializer.validated_data)
        return self.success_response(
            data=AdUnitDetailSerializer(ad_unit).data,
            message='Ad unit created successfully.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Ad unit pause করে"""
        ad_unit = self.get_object()
        ad_unit = AdUnitService.pause_ad_unit(ad_unit)
        return self.success_response(
            data=AdUnitDetailSerializer(ad_unit).data,
            message='Ad unit paused.'
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Ad unit activate করে"""
        ad_unit = self.get_object()
        ad_unit = AdUnitService.activate_ad_unit(ad_unit)
        return self.success_response(
            data=AdUnitDetailSerializer(ad_unit).data,
            message='Ad unit activated.'
        )

    @action(detail=True, methods=['get'])
    def tag_code(self, request, pk=None):
        """Ad tag code return করে"""
        ad_unit = self.get_object()
        return self.success_response(data={
            'unit_id': ad_unit.unit_id,
            'tag_code': ad_unit.tag_code,
            'sdk_key': ad_unit.sdk_key,
            'format': ad_unit.format,
        })

    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Ad unit performance stats"""
        ad_unit = self.get_object()
        serializer = DateRangeSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        earnings = PublisherEarning.objects.filter(
            ad_unit=ad_unit,
            date__range=[
                serializer.validated_data['start_date'],
                serializer.validated_data['end_date'],
            ],
        ).aggregate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
            requests=Sum('ad_requests'),
        )
        return self.success_response(data={
            'unit_id': ad_unit.unit_id,
            'name': ad_unit.name,
            'period_revenue': earnings.get('revenue') or 0,
            'period_impressions': earnings.get('impressions') or 0,
            'period_clicks': earnings.get('clicks') or 0,
            'lifetime_revenue': ad_unit.total_revenue,
            'avg_ecpm': ad_unit.avg_ecpm,
            'fill_rate': ad_unit.fill_rate,
        })

    @action(detail=True, methods=['get', 'post'])
    def targeting(self, request, pk=None):
        """Ad unit targeting — GET: দেখাও, POST: update করো"""
        ad_unit = self.get_object()
        if request.method == 'GET':
            try:
                targeting = ad_unit.targeting
                return self.success_response(data=AdUnitTargetingSerializer(targeting).data)
            except AdUnitTargeting.DoesNotExist:
                return self.success_response(data=None)

        serializer = AdUnitTargetingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        targeting, _ = AdUnitTargeting.objects.update_or_create(
            ad_unit=ad_unit,
            defaults=serializer.validated_data,
        )
        return self.success_response(
            data=AdUnitTargetingSerializer(targeting).data,
            message='Targeting updated.'
        )

    @action(detail=True, methods=['get'])
    def placements(self, request, pk=None):
        """Ad unit-এর সব placements"""
        ad_unit = self.get_object()
        placements = AdPlacement.objects.filter(ad_unit=ad_unit)
        return self.success_response(data=AdPlacementSerializer(placements, many=True).data)

    @action(detail=True, methods=['get'])
    def mediation(self, request, pk=None):
        """Ad unit-এর mediation group"""
        ad_unit = self.get_object()
        try:
            group = ad_unit.mediation_group
            return self.success_response(data=MediationGroupSerializer(group).data)
        except MediationGroup.DoesNotExist:
            return self.success_response(data=None)


# ──────────────────────────────────────────────────────────────────────────────
# AD PLACEMENT VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class AdPlacementViewSet(BaseViewSet):
    """Ad Placement CRUD"""
    queryset = AdPlacement.objects.select_related('ad_unit', 'ad_unit__publisher').all()
    serializer_class = AdPlacementSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(ad_unit__publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AdPlacementCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        placement = serializer.save()
        return self.success_response(
            data=AdPlacementSerializer(placement).data,
            message='Placement created.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Placement active/inactive toggle করে"""
        placement = self.get_object()
        placement.is_active = not placement.is_active
        placement.save(update_fields=['is_active', 'updated_at'])
        return self.success_response(
            data={'is_active': placement.is_active},
            message=f'Placement {"activated" if placement.is_active else "deactivated"}.'
        )


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION GROUP VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class MediationGroupViewSet(BaseViewSet):
    """Mediation Group management"""
    queryset = MediationGroup.objects.select_related('ad_unit', 'ad_unit__publisher').all()
    serializer_class = MediationGroupSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(ad_unit__publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        return qs

    def create(self, request, *args, **kwargs):
        serializer = MediationGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ad_unit = serializer.validated_data['ad_unit']
        # Ownership check
        publisher = request.user.publisher_profile
        if ad_unit.publisher != publisher:
            return self.error_response('You do not own this ad unit.', status_code=403)
        group = MediationService.create_mediation_group(ad_unit, serializer.validated_data)
        return self.success_response(
            data=MediationGroupSerializer(group).data,
            message='Mediation group created.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def optimize(self, request, pk=None):
        """Waterfall auto-optimize করে (eCPM-based)"""
        group = self.get_object()
        group = MediationService.optimize_waterfall(group)
        return self.success_response(
            data=MediationGroupSerializer(group).data,
            message='Waterfall optimized based on eCPM performance.'
        )

    @action(detail=True, methods=['get'])
    def waterfall(self, request, pk=None):
        """Active waterfall items priority order-এ return করে"""
        group = self.get_object()
        items = MediationService.get_active_waterfall(group)
        return self.success_response(
            data=WaterfallItemSerializer(items, many=True).data
        )

    @action(detail=True, methods=['post'])
    def reorder(self, request, pk=None):
        """Waterfall priority reorder করে"""
        group = self.get_object()
        serializer = WaterfallReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = MediationService.reorder_waterfall(group, serializer.validated_data['items'])
        return self.success_response(
            data=WaterfallItemSerializer(updated, many=True).data,
            message='Waterfall reordered.'
        )


# ──────────────────────────────────────────────────────────────────────────────
# WATERFALL ITEM VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class WaterfallItemViewSet(BaseViewSet):
    """Waterfall Item CRUD"""
    queryset = WaterfallItem.objects.select_related('mediation_group', 'network').all()
    serializer_class = WaterfallItemSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                pub = self.request.user.publisher_profile
                return qs.filter(mediation_group__ad_unit__publisher=pub)
            except Exception:
                return qs.none()
        return qs

    def create(self, request, *args, **kwargs):
        serializer = WaterfallItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = serializer.validated_data['mediation_group']
        item = MediationService.add_waterfall_item(group, serializer.validated_data)
        return self.success_response(
            data=WaterfallItemSerializer(item).data,
            message='Waterfall item added.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Waterfall item active/paused toggle"""
        item = self.get_object()
        item.status = 'paused' if item.status == 'active' else 'active'
        item.save(update_fields=['status', 'updated_at'])
        return self.success_response(
            data={'status': item.status},
            message=f'Waterfall item {item.status}.'
        )


# ──────────────────────────────────────────────────────────────────────────────
# HEADER BIDDING CONFIG VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class HeaderBiddingConfigViewSet(BaseViewSet):
    """Header Bidding Config CRUD"""
    queryset = HeaderBiddingConfig.objects.select_related('mediation_group').all()
    serializer_class = HeaderBiddingConfigSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                pub = self.request.user.publisher_profile
                return qs.filter(mediation_group__ad_unit__publisher=pub)
            except Exception:
                return qs.none()
        return qs


# ──────────────────────────────────────────────────────────────────────────────
# EARNING VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class PublisherEarningViewSet(BaseViewSet):
    """Publisher Earning records"""
    queryset = PublisherEarning.objects.select_related(
        'publisher', 'ad_unit', 'site', 'app', 'network'
    ).all()
    serializer_class = PublisherEarningSerializer
    permission_classes = [CanViewEarnings]
    http_method_names = ['get', 'head', 'options']  # Read-only

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('publisher_id'):
            qs = qs.filter(publisher__publisher_id=params['publisher_id'])
        return qs

    def list(self, request, *args, **kwargs):
        """Earnings with date range filter"""
        params = request.query_params
        qs = self.get_queryset()

        if params.get('start_date') and params.get('end_date'):
            qs = qs.filter(date__range=[params['start_date'], params['end_date']])
        if params.get('granularity'):
            qs = qs.filter(granularity=params['granularity'])
        if params.get('earning_type'):
            qs = qs.filter(earning_type=params['earning_type'])
        if params.get('country'):
            qs = qs.filter(country=params['country'])
        if params.get('site_id'):
            qs = qs.filter(site__site_id=params['site_id'])
        if params.get('app_id'):
            qs = qs.filter(app__app_id=params['app_id'])
        if params.get('ad_unit_id'):
            qs = qs.filter(ad_unit__unit_id=params['ad_unit_id'])

        qs = qs.order_by('-date', '-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return self.success_response(data=self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Earnings aggregated summary"""
        period = request.query_params.get('period', 'last_30_days')
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return self.error_response('No publisher profile found.')

        start_date, end_date = get_date_range(period)
        report = EarningService.get_earnings_report(publisher, start_date, end_date)
        return self.success_response(data=report)

    @action(detail=False, methods=['get'])
    def by_country(self, request):
        """Country-wise earnings breakdown"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return self.error_response('No publisher profile found.')

        period = request.query_params.get('period', 'last_30_days')
        start_date, end_date = get_date_range(period)

        data = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
        ).values('country', 'country_name').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
        ).order_by('-revenue')[:20]

        return self.success_response(data=list(data))

    @action(detail=False, methods=['get'])
    def by_ad_unit(self, request):
        """Ad unit-wise earnings breakdown"""
        try:
            publisher = request.user.publisher_profile
        except Exception:
            return self.error_response('No publisher profile found.')

        period = request.query_params.get('period', 'last_30_days')
        start_date, end_date = get_date_range(period)

        data = PublisherEarning.objects.filter(
            publisher=publisher,
            date__range=[start_date, end_date],
        ).values('ad_unit__unit_id', 'ad_unit__name', 'ad_unit__format').annotate(
            revenue=Sum('publisher_revenue'),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
        ).order_by('-revenue')

        return self.success_response(data=list(data))


# ──────────────────────────────────────────────────────────────────────────────
# PAYOUT THRESHOLD VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class PayoutThresholdViewSet(BaseViewSet):
    """Payout threshold / payment method management"""
    queryset = PayoutThreshold.objects.select_related('publisher').all()
    serializer_class = PayoutThresholdSerializer
    permission_classes = [IsPublisher]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        return qs

    def create(self, request, *args, **kwargs):
        serializer = PayoutThresholdSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        threshold = serializer.save()
        return self.success_response(
            data=PayoutThresholdSerializer(threshold).data,
            message='Payment method added.',
            status_code=201,
        )

    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Payment method primary হিসেবে set করে"""
        threshold = self.get_object()
        # Others unset
        PayoutThreshold.objects.filter(
            publisher=threshold.publisher
        ).update(is_primary=False)
        threshold.is_primary = True
        threshold.save(update_fields=['is_primary', 'updated_at'])
        return self.success_response(message='Primary payment method updated.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Payment method verify করে (admin only)"""
        threshold = self.get_object()
        threshold.is_verified = True
        threshold.verified_at = timezone.now()
        threshold.save(update_fields=['is_verified', 'verified_at', 'updated_at'])
        return self.success_response(message='Payment method verified.')


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class PublisherInvoiceViewSet(BaseViewSet):
    """Publisher Invoice management"""
    queryset = PublisherInvoice.objects.select_related(
        'publisher', 'payout_threshold', 'processed_by'
    ).all()

    def get_permissions(self):
        if self.action in ('issue', 'mark_paid', 'generate'):
            return [IsAdminUser()]
        return [CanViewEarnings()]

    def get_serializer_class(self):
        if self.action == 'list':
            return PublisherInvoiceListSerializer
        return PublisherInvoiceDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('publisher_id'):
            qs = qs.filter(publisher__publisher_id=params['publisher_id'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('year'):
            qs = qs.filter(period_start__year=params['year'])
        if params.get('month'):
            qs = qs.filter(period_start__month=params['month'])
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def generate(self, request):
        """Monthly invoice generate করে (admin only)"""
        publisher_id = request.data.get('publisher_id')
        year  = int(request.data.get('year', timezone.now().year))
        month = int(request.data.get('month', timezone.now().month))

        try:
            publisher = Publisher.objects.get(publisher_id=publisher_id)
        except Publisher.DoesNotExist:
            return self.error_response('Publisher not found.')

        invoice = InvoiceService.generate_monthly_invoice(publisher, year, month)
        return self.success_response(
            data=PublisherInvoiceDetailSerializer(invoice).data,
            message='Invoice generated.',
            status_code=201,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def issue(self, request, pk=None):
        """Invoice issue করে (Draft → Issued)"""
        invoice = self.get_object()
        invoice = InvoiceService.issue_invoice(invoice, issued_by=request.user)
        return self.success_response(
            data=PublisherInvoiceDetailSerializer(invoice).data,
            message='Invoice issued.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_paid(self, request, pk=None):
        """Invoice paid mark করে"""
        invoice = self.get_object()
        reference = request.data.get('payment_reference', '')
        if not reference:
            return self.error_response('Payment reference is required.')
        invoice = InvoiceService.mark_as_paid(invoice, reference, processed_by=request.user)
        return self.success_response(
            data=PublisherInvoiceDetailSerializer(invoice).data,
            message='Invoice marked as paid.'
        )

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        """Invoice dispute raise করে"""
        invoice = self.get_object()
        serializer = InvoiceDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice.status = 'disputed'
        invoice.publisher_notes = serializer.validated_data['reason']
        invoice.save(update_fields=['status', 'publisher_notes', 'updated_at'])
        return self.success_response(message='Dispute submitted. Admin will review within 5 business days.')


# ──────────────────────────────────────────────────────────────────────────────
# TRAFFIC SAFETY LOG VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class TrafficSafetyLogViewSet(BaseViewSet):
    """Traffic Safety / IVT Log management"""
    queryset = TrafficSafetyLog.objects.select_related(
        'publisher', 'site', 'app', 'ad_unit', 'action_taken_by'
    ).all()
    serializer_class = TrafficSafetyLogSerializer

    def get_permissions(self):
        if self.action in ('take_action', 'mark_false_positive'):
            return [IsAdminUser()]
        return [IsAdminOrPublisher()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                return qs.filter(publisher=self.request.user.publisher_profile)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('publisher_id'):
            qs = qs.filter(publisher__publisher_id=params['publisher_id'])
        if params.get('traffic_type'):
            qs = qs.filter(traffic_type=params['traffic_type'])
        if params.get('severity'):
            qs = qs.filter(severity=params['severity'])
        if params.get('action'):
            qs = qs.filter(action_taken=params['action'])
        if params.get('min_fraud_score'):
            qs = qs.filter(fraud_score__gte=params['min_fraud_score'])
        if params.get('start_date') and params.get('end_date'):
            qs = qs.filter(detected_at__date__range=[params['start_date'], params['end_date']])
        return qs

    @action(detail=True, methods=['post'])
    def take_action(self, request, pk=None):
        """IVT log-এ action নেয় (admin only)"""
        log = self.get_object()
        serializer = FraudActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = FraudDetectionService.take_action(
            log,
            serializer.validated_data['action'],
            taken_by=request.user,
            notes=serializer.validated_data.get('notes', ''),
        )
        return self.success_response(
            data=TrafficSafetyLogSerializer(log).data,
            message=f'Action "{serializer.validated_data["action"]}" applied.'
        )

    @action(detail=True, methods=['post'])
    def mark_false_positive(self, request, pk=None):
        """False positive হিসেবে mark করে (admin only)"""
        log = self.get_object()
        serializer = MarkFalsePositiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log.is_false_positive = serializer.validated_data['is_false_positive']
        if serializer.validated_data.get('notes'):
            log.notes = serializer.validated_data['notes']
        log.save(update_fields=['is_false_positive', 'notes', 'updated_at'])
        return self.success_response(
            data=TrafficSafetyLogSerializer(log).data,
            message='False positive status updated.'
        )

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """IVT summary by type"""
        qs = self.get_queryset()
        period = request.query_params.get('period', 'last_30_days')
        start_date, end_date = get_date_range(period)
        qs = qs.filter(detected_at__date__range=[start_date, end_date])

        summary = qs.values('traffic_type').annotate(
            count=Count('id'),
            total_revenue_at_risk=Sum('revenue_at_risk'),
            total_deducted=Sum('revenue_deducted'),
        ).order_by('-count')

        return self.success_response(data=list(summary))


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC VIEWSET
# ──────────────────────────────────────────────────────────────────────────────

class SiteQualityMetricViewSet(BaseViewSet):
    """Site Quality Metric — read-mostly"""
    queryset = SiteQualityMetric.objects.select_related('site', 'site__publisher').all()
    serializer_class = SiteQualityMetricSerializer
    http_method_names = ['get', 'head', 'options', 'post']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAdminUser()]
        return [IsAdminOrPublisher()]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            try:
                pub = self.request.user.publisher_profile
                return qs.filter(site__publisher=pub)
            except Exception:
                return qs.none()
        params = self.request.query_params
        if params.get('site_id'):
            qs = qs.filter(site__site_id=params['site_id'])
        if params.get('has_alerts') == 'true':
            qs = qs.filter(has_alerts=True)
        if params.get('min_score'):
            qs = qs.filter(overall_quality_score__gte=params['min_score'])
        if params.get('date'):
            qs = qs.filter(date=params['date'])
        return qs

    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """has_alerts=True এমন সব metrics return করে"""
        qs = self.get_queryset().filter(has_alerts=True).order_by('-date')[:50]
        return self.success_response(data=SiteQualityMetricSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """Quality score trend for a site"""
        site_id = request.query_params.get('site_id')
        if not site_id:
            return self.error_response('site_id is required.')
        try:
            if request.user.is_staff:
                site = Site.objects.get(site_id=site_id)
            else:
                site = Site.objects.get(site_id=site_id, publisher=request.user.publisher_profile)
        except Site.DoesNotExist:
            return self.error_response('Site not found.', status_code=404)

        days = int(request.query_params.get('days', 30))
        trend = QualityMetricService.get_quality_trend(site, days)
        return self.success_response(data=trend)
