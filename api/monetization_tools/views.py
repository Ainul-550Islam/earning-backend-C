"""
api/monetization_tools/views.py
================================
DRF ViewSets for all monetization_tools models.
"""

import logging
from decimal import Decimal

from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import (
    AdCampaign, AdUnit, AdNetwork, AdPlacement,
    Offerwall, Offer, OfferCompletion, RewardTransaction,
    ImpressionLog, ClickLog, ConversionLog, RevenueDailySummary,
    SubscriptionPlan, UserSubscription, InAppPurchase,
    PaymentTransaction, RecurringBilling,
    UserLevel, Achievement, LeaderboardRank, SpinWheelLog,
    ABTest, WaterfallConfig, FloorPriceConfig,
)
from .serializers import (
    AdCampaignListSerializer, AdCampaignDetailSerializer, AdUnitSerializer,
    AdNetworkSerializer, AdPlacementSerializer,
    OfferwallSerializer, OfferListSerializer, OfferDetailSerializer,
    OfferCompletionSerializer, OfferCompletionAdminSerializer,
    RewardTransactionSerializer,
    ImpressionLogSerializer, ClickLogSerializer, ConversionLogSerializer,
    RevenueDailySummarySerializer,
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    InAppPurchaseSerializer, PaymentTransactionSerializer,
    PaymentTransactionPublicSerializer, RecurringBillingSerializer,
    UserLevelSerializer, AchievementSerializer, LeaderboardRankSerializer,
    SpinWheelLogSerializer,
    ABTestSerializer, WaterfallConfigSerializer, FloorPriceConfigSerializer,
)
from .services import (
    OfferService, RewardService, SubscriptionService,
    PaymentService, GamificationService, LeaderboardService,
)
from .exceptions import MonetizationBaseException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class TenantFilterMixin:
    """Filter queryset to current tenant if available."""
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs


class MonetizationBaseViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def success_response(self, data=None, message='', status_code=status.HTTP_200_OK):
        return Response({'success': True, 'message': message, 'data': data}, status=status_code)

    def error_response(self, message='', errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response({'success': False, 'message': message, 'errors': errors}, status=status_code)

    def handle_exception(self, exc):
        if isinstance(exc, MonetizationBaseException):
            return self.error_response(message=str(exc.detail), status_code=exc.status_code)
        return super().handle_exception(exc)


# ===========================================================================
# 1. AD CAMPAIGN
# ===========================================================================

class AdCampaignViewSet(MonetizationBaseViewSet):
    queryset = AdCampaign.objects.select_related('tenant').all()

    def get_serializer_class(self):
        if self.action in ('list',):
            return AdCampaignListSerializer
        return AdCampaignDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'paused'
        campaign.save(update_fields=['status', 'updated_at'])
        return self.success_response(message=_('Campaign paused.'))

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'active'
        campaign.save(update_fields=['status', 'updated_at'])
        return self.success_response(message=_('Campaign activated.'))

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        campaign = self.get_object()
        return self.success_response(data={
            'impressions':  campaign.total_impressions,
            'clicks':       campaign.total_clicks,
            'conversions':  campaign.total_conversions,
            'ctr':          str(campaign.ctr),
            'spent_budget': str(campaign.spent_budget),
            'remaining':    str(campaign.remaining_budget),
        })


# ===========================================================================
# 2. AD UNIT
# ===========================================================================

class AdUnitViewSet(MonetizationBaseViewSet):
    queryset = AdUnit.objects.select_related('campaign').all()
    serializer_class = AdUnitSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            qs = qs.filter(campaign__campaign_id=campaign_id)
        return qs


# ===========================================================================
# 3. AD NETWORK
# ===========================================================================

class AdNetworkViewSet(MonetizationBaseViewSet):
    queryset = AdNetwork.objects.all()
    serializer_class = AdNetworkSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]


# ===========================================================================
# 4. AD PLACEMENT
# ===========================================================================

class AdPlacementViewSet(MonetizationBaseViewSet):
    queryset = AdPlacement.objects.select_related('ad_unit', 'ad_network').all()
    serializer_class = AdPlacementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        screen = self.request.query_params.get('screen')
        if screen:
            qs = qs.filter(screen_name__icontains=screen)
        return qs


# ===========================================================================
# 5. OFFERWALL
# ===========================================================================

class OfferwallViewSet(MonetizationBaseViewSet):
    queryset = Offerwall.objects.select_related('network').filter(is_active=True)
    serializer_class = OfferwallSerializer
    http_method_names = ['get', 'head', 'options']


# ===========================================================================
# 6. OFFER
# ===========================================================================

class OfferViewSet(MonetizationBaseViewSet):
    queryset = Offer.objects.select_related('offerwall').filter(status='active')

    def get_serializer_class(self):
        if self.action == 'list':
            return OfferListSerializer
        return OfferDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        offer_type = self.request.query_params.get('type')
        offerwall  = self.request.query_params.get('offerwall')
        featured   = self.request.query_params.get('featured')
        if offer_type:
            qs = qs.filter(offer_type=offer_type)
        if offerwall:
            qs = qs.filter(offerwall__slug=offerwall)
        if featured == '1':
            qs = qs.filter(is_featured=True)
        return qs

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        offer = self.get_object()
        ip    = request.META.get('REMOTE_ADDR', '')
        completion = OfferService.start_offer(
            offer=offer,
            user=request.user,
            ip_address=ip,
            device_id=request.data.get('device_id'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        return self.success_response(
            data={'transaction_id': str(completion.transaction_id)},
            message=_('Offer started. Complete the requirements and await credit.'),
            status_code=status.HTTP_201_CREATED,
        )


# ===========================================================================
# 7. OFFER COMPLETION
# ===========================================================================

class OfferCompletionViewSet(MonetizationBaseViewSet):
    queryset = OfferCompletion.objects.select_related('user', 'offer').all()

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return OfferCompletionAdminSerializer
        return OfferCompletionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        completion = self.get_object()
        reward_txn = OfferService.approve_completion(completion)
        return self.success_response(
            data={'reward_transaction_id': str(reward_txn.transaction_id)},
            message=_('Offer completion approved and reward credited.'),
        )

    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        completion = self.get_object()
        reason     = request.data.get('reason', '')
        OfferService.reject_completion(completion, reason)
        return self.success_response(message=_('Offer completion rejected.'))


# ===========================================================================
# 8. REWARD TRANSACTION
# ===========================================================================

class RewardTransactionViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = RewardTransaction.objects.select_related('user').all()
    serializer_class = RewardTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs.order_by('-created_at')


# ===========================================================================
# 9. IMPRESSION / CLICK / CONVERSION LOGS
# ===========================================================================

class ImpressionLogViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ImpressionLog.objects.select_related('ad_unit').all()
    serializer_class = ImpressionLogSerializer
    permission_classes = [IsAdminUser]


class ClickLogViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ClickLog.objects.select_related('ad_unit').all()
    serializer_class = ClickLogSerializer
    permission_classes = [IsAdminUser]


class ConversionLogViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ConversionLog.objects.select_related('campaign').all()
    serializer_class = ConversionLogSerializer
    permission_classes = [IsAdminUser]


# ===========================================================================
# 10. REVENUE DAILY SUMMARY
# ===========================================================================

class RevenueDailySummaryViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = RevenueDailySummary.objects.select_related('ad_network', 'campaign').all()
    serializer_class = RevenueDailySummarySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        start = self.request.query_params.get('start')
        end   = self.request.query_params.get('end')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.order_by('-date')

    @action(detail=False, methods=['get'], url_path='totals')
    def totals(self, request):
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_revenue=Sum('total_revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            avg_ecpm=Avg('ecpm'),
        )
        return Response({'success': True, 'data': agg})


# ===========================================================================
# 11. SUBSCRIPTION PLAN
# ===========================================================================

class SubscriptionPlanViewSet(MonetizationBaseViewSet):
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    serializer_class = SubscriptionPlanSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]


# ===========================================================================
# 12. USER SUBSCRIPTION
# ===========================================================================

class UserSubscriptionViewSet(MonetizationBaseViewSet):
    queryset = UserSubscription.objects.select_related('user', 'plan').all()
    serializer_class = UserSubscriptionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['get'], url_path='my')
    def my_subscription(self, request):
        sub = UserSubscription.objects.filter(
            user=request.user,
            status__in=['trial', 'active']
        ).select_related('plan').first()
        if not sub:
            return Response({'success': True, 'data': None, 'message': _('No active subscription.')})
        return self.success_response(data=UserSubscriptionSerializer(sub).data)

    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        plan_slug = request.data.get('plan_slug')
        try:
            plan = SubscriptionPlan.objects.get(slug=plan_slug, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return self.error_response(message=_('Plan not found.'), status_code=status.HTTP_404_NOT_FOUND)
        sub = SubscriptionService.create_subscription(request.user, plan)
        return self.success_response(
            data=UserSubscriptionSerializer(sub).data,
            message=_('Subscription created.'),
            status_code=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        sub    = self.get_object()
        reason = request.data.get('reason', '')
        SubscriptionService.cancel_subscription(sub, reason)
        return self.success_response(message=_('Subscription cancelled.'))


# ===========================================================================
# 13. IN-APP PURCHASE
# ===========================================================================

class InAppPurchaseViewSet(MonetizationBaseViewSet):
    queryset = InAppPurchase.objects.select_related('user').all()
    serializer_class = InAppPurchaseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs


# ===========================================================================
# 14. PAYMENT TRANSACTION
# ===========================================================================

class PaymentTransactionViewSet(MonetizationBaseViewSet):
    queryset = PaymentTransaction.objects.select_related('user').all()

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return PaymentTransactionSerializer
        return PaymentTransactionPublicSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs.order_by('-initiated_at')


# ===========================================================================
# 15. RECURRING BILLING
# ===========================================================================

class RecurringBillingViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = RecurringBilling.objects.select_related('subscription').all()
    serializer_class = RecurringBillingSerializer
    permission_classes = [IsAdminUser]


# ===========================================================================
# 16. USER LEVEL
# ===========================================================================

class UserLevelViewSet(MonetizationBaseViewSet):
    queryset = UserLevel.objects.select_related('user').all()
    serializer_class = UserLevelSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['get'], url_path='me')
    def my_level(self, request):
        obj, _ = UserLevel.objects.get_or_create(user=request.user)
        return self.success_response(data=UserLevelSerializer(obj).data)


# ===========================================================================
# 17. ACHIEVEMENT
# ===========================================================================

class AchievementViewSet(MonetizationBaseViewSet):
    queryset = Achievement.objects.select_related('user').all()
    serializer_class = AchievementSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs


# ===========================================================================
# 18. LEADERBOARD
# ===========================================================================

class LeaderboardRankViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = LeaderboardRank.objects.select_related('user').all()
    serializer_class = LeaderboardRankSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        scope      = self.request.query_params.get('scope', 'global')
        board_type = self.request.query_params.get('type', 'earnings')
        period     = self.request.query_params.get('period')
        qs = qs.filter(scope=scope, board_type=board_type)
        if period:
            qs = qs.filter(period_label=period)
        return qs.order_by('rank')[:100]


# ===========================================================================
# 19. SPIN WHEEL / SCRATCH CARD
# ===========================================================================

class SpinWheelViewSet(MonetizationBaseViewSet):
    queryset = SpinWheelLog.objects.select_related('user').all()
    serializer_class = SpinWheelLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['post'], url_path='spin')
    def spin(self, request):
        log = GamificationService.spin_wheel(
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        return self.success_response(
            data=SpinWheelLogSerializer(log).data,
            message=_('Spin complete!'),
            status_code=status.HTTP_201_CREATED,
        )


# ===========================================================================
# 20. A/B TEST
# ===========================================================================

class ABTestViewSet(MonetizationBaseViewSet):
    queryset = ABTest.objects.all()
    serializer_class = ABTestSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'start_test', 'stop_test'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='start')
    def start_test(self, request, pk=None):
        test = self.get_object()
        test.status = 'running'
        test.started_at = timezone.now()
        test.save(update_fields=['status', 'started_at', 'updated_at'])
        return self.success_response(message=_('A/B test started.'))

    @action(detail=True, methods=['post'], url_path='stop')
    def stop_test(self, request, pk=None):
        test = self.get_object()
        test.status = 'completed'
        test.ended_at = timezone.now()
        test.save(update_fields=['status', 'ended_at', 'updated_at'])
        return self.success_response(message=_('A/B test stopped.'))


# ===========================================================================
# 21. WATERFALL CONFIG
# ===========================================================================

class WaterfallConfigViewSet(MonetizationBaseViewSet):
    queryset = WaterfallConfig.objects.select_related('ad_unit', 'ad_network').all()
    serializer_class = WaterfallConfigSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        ad_unit_id = self.request.query_params.get('ad_unit_id')
        if ad_unit_id:
            qs = qs.filter(ad_unit_id=ad_unit_id)
        return qs.order_by('ad_unit', 'priority')


# ===========================================================================
# 22. FLOOR PRICE CONFIG
# ===========================================================================

class FloorPriceConfigViewSet(MonetizationBaseViewSet):
    queryset = FloorPriceConfig.objects.select_related('ad_network', 'ad_unit').all()
    serializer_class = FloorPriceConfigSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]


# ============================================================================
# NEW VIEWSETS  (Phase-2 models)
# ============================================================================

from .models import (
    AdPerformanceHourly, AdPerformanceDaily, AdNetworkDailyStat,
    PointLedgerSnapshot, ABTestAssignment, MonetizationConfig, AdCreative,
    UserSegment, UserSegmentMembership, PostbackLog,
    PayoutMethod, PayoutRequest, ReferralProgram, ReferralLink, ReferralCommission,
    DailyStreak, SpinWheelConfig, PrizeConfig, FlashSale,
    Coupon, CouponUsage, FraudAlert, RevenueGoal, PublisherAccount,
    MonetizationNotificationTemplate,
)
from .serializers import (
    AdPerformanceHourlySerializer, AdPerformanceDailySerializer,
    AdNetworkDailyStatSerializer, PointLedgerSnapshotSerializer,
    ABTestAssignmentSerializer, MonetizationConfigSerializer,
    AdCreativeListSerializer, AdCreativeDetailSerializer,
    UserSegmentSerializer, UserSegmentMembershipSerializer,
    PostbackLogSerializer, PostbackLogListSerializer,
    PayoutMethodSerializer, PayoutRequestSerializer, PayoutRequestAdminSerializer,
    ReferralProgramSerializer, ReferralLinkSerializer, ReferralCommissionSerializer,
    DailyStreakSerializer, SpinWheelConfigSerializer, PrizeConfigSerializer,
    FlashSaleListSerializer, FlashSaleDetailSerializer,
    CouponSerializer, CouponPublicSerializer, CouponUsageSerializer,
    FraudAlertSerializer, RevenueGoalSerializer,
    PublisherAccountSerializer, MonetizationNotificationTemplateSerializer,
)


# ── Performance Analytics ────────────────────────────────────────────────────

class AdPerformanceHourlyViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AdPerformanceHourly.objects.select_related('ad_unit', 'ad_network').all()
    serializer_class = AdPerformanceHourlySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        unit = self.request.query_params.get('ad_unit_id')
        if unit:
            qs = qs.filter(ad_unit_id=unit)
        start = self.request.query_params.get('start')
        end   = self.request.query_params.get('end')
        if start:
            qs = qs.filter(hour_bucket__date__gte=start)
        if end:
            qs = qs.filter(hour_bucket__date__lte=end)
        return qs.order_by('-hour_bucket')


class AdPerformanceDailyViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AdPerformanceDaily.objects.select_related('ad_unit', 'ad_network', 'campaign').all()
    serializer_class = AdPerformanceDailySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        start = self.request.query_params.get('start')
        end   = self.request.query_params.get('end')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs.order_by('-date')

    @action(detail=False, methods=['get'], url_path='kpi-summary')
    def kpi_summary(self, request):
        from django.db.models import Sum, Avg
        qs   = self.get_queryset()
        agg  = qs.aggregate(
            total_revenue=Sum('total_revenue'), total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'), total_conversions=Sum('conversions'),
            avg_ecpm=Avg('ecpm'), avg_ctr=Avg('ctr'), avg_fill_rate=Avg('fill_rate'),
        )
        return Response({'success': True, 'data': agg})


class AdNetworkDailyStatViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AdNetworkDailyStat.objects.select_related('ad_network').all()
    serializer_class = AdNetworkDailyStatSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'], url_path='high-discrepancy')
    def high_discrepancy(self, request):
        from decimal import Decimal
        qs = self.get_queryset().filter(discrepancy_pct__gte=Decimal('5.00'))
        return Response({'success': True, 'data': AdNetworkDailyStatSerializer(qs, many=True).data})


class PointLedgerSnapshotViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PointLedgerSnapshot.objects.select_related('user').all()
    serializer_class = PointLedgerSnapshotSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs.order_by('-snapshot_date')


# ── A/B Test Assignment ──────────────────────────────────────────────────────

class ABTestAssignmentViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ABTestAssignment.objects.select_related('test', 'user').all()
    serializer_class = ABTestAssignmentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        test_id = self.request.query_params.get('test_id')
        if test_id:
            qs = qs.filter(test_id=test_id)
        return qs


# ── Monetization Config ──────────────────────────────────────────────────────

class MonetizationConfigViewSet(TenantFilterMixin, viewsets.ModelViewSet):
    queryset = MonetizationConfig.objects.all()
    serializer_class = MonetizationConfigSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_object(self):
        tenant = getattr(self.request, 'tenant', None)
        obj, _ = MonetizationConfig.objects.get_or_create(tenant=tenant)
        return obj

    @action(detail=False, methods=['get'], url_path='feature-flags')
    def feature_flags(self, request):
        obj = self.get_object()
        flags = {
            'offerwall': obj.offerwall_enabled,
            'subscription': obj.subscription_enabled,
            'spin_wheel': obj.spin_wheel_enabled,
            'scratch_card': obj.scratch_card_enabled,
            'referral': obj.referral_enabled,
            'ab_testing': obj.ab_testing_enabled,
            'flash_sale': obj.flash_sale_enabled,
            'coupon': obj.coupon_enabled,
            'daily_streak': obj.daily_streak_enabled,
        }
        return Response({'success': True, 'data': flags})


# ── Ad Creative ──────────────────────────────────────────────────────────────

class AdCreativeViewSet(MonetizationBaseViewSet):
    queryset = AdCreative.objects.select_related('ad_unit').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AdCreativeListSerializer
        return AdCreativeDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        creative = self.get_object()
        creative.status = 'approved'
        creative.reviewed_by = request.user
        creative.save(update_fields=['status', 'reviewed_by', 'updated_at'])
        return self.success_response(message=_('Creative approved.'))

    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        creative = self.get_object()
        creative.status = 'rejected'
        creative.reviewed_by = request.user
        creative.rejection_reason = request.data.get('reason', '')
        creative.save(update_fields=['status', 'reviewed_by', 'rejection_reason', 'updated_at'])
        return self.success_response(message=_('Creative rejected.'))


# ── User Segment ─────────────────────────────────────────────────────────────

class UserSegmentViewSet(MonetizationBaseViewSet):
    queryset = UserSegment.objects.all()
    serializer_class = UserSegmentSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='add-user', permission_classes=[IsAdminUser])
    def add_user(self, request, pk=None):
        segment = self.get_object()
        user_id = request.data.get('user_id')
        UserSegmentMembership.objects.get_or_create(
            segment=segment, user_id=user_id,
            defaults={'tenant': segment.tenant},
        )
        segment.member_count = UserSegmentMembership.objects.filter(segment=segment).count()
        segment.save(update_fields=['member_count'])
        return self.success_response(message=_('User added to segment.'))


class UserSegmentMembershipViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = UserSegmentMembership.objects.select_related('user', 'segment').all()
    serializer_class = UserSegmentMembershipSerializer
    permission_classes = [IsAdminUser]


# ── Postback Log ─────────────────────────────────────────────────────────────

class PostbackLogViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PostbackLog.objects.select_related('ad_network').all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'list':
            return PostbackLogListSerializer
        return PostbackLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        net = self.request.query_params.get('network_id')
        st  = self.request.query_params.get('status')
        if net:
            qs = qs.filter(ad_network_id=net)
        if st:
            qs = qs.filter(status=st)
        return qs.order_by('-received_at')

    @action(detail=False, methods=['get'], url_path='status-summary')
    def status_summary(self, request):
        from django.db.models import Count
        data = (
            self.get_queryset()
                .values('status')
                .annotate(count=Count('id'))
                .order_by('-count')
        )
        return Response({'success': True, 'data': list(data)})


# ── Payout ───────────────────────────────────────────────────────────────────

class PayoutMethodViewSet(MonetizationBaseViewSet):
    queryset = PayoutMethod.objects.select_related('user').all()
    serializer_class = PayoutMethodSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        method = self.get_object()
        PayoutMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)
        method.is_default = True
        method.save(update_fields=['is_default', 'updated_at'])
        return self.success_response(message=_('Default payout method updated.'))

    @action(detail=True, methods=['post'], url_path='verify', permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        method = self.get_object()
        method.is_verified = True
        method.verified_at = timezone.now()
        method.save(update_fields=['is_verified', 'verified_at', 'updated_at'])
        return self.success_response(message=_('Payout method verified.'))


class PayoutRequestViewSet(MonetizationBaseViewSet):
    queryset = PayoutRequest.objects.select_related('user', 'payout_method').all()

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return PayoutRequestAdminSerializer
        return PayoutRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        st = self.request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        pr = self.get_object()
        if pr.status != 'pending':
            return self.error_response(message=_('Only pending requests can be approved.'))
        pr.status = 'approved'
        pr.reviewed_by = request.user
        pr.reviewed_at = timezone.now()
        pr.admin_note  = request.data.get('note', '')
        pr.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_note', 'updated_at'])
        return self.success_response(message=_('Payout request approved.'))

    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        pr = self.get_object()
        if pr.status not in ('pending', 'approved'):
            return self.error_response(message=_('Cannot reject this request.'))
        pr.status = 'rejected'
        pr.reviewed_by = request.user
        pr.reviewed_at = timezone.now()
        pr.rejection_reason = request.data.get('reason', '')
        pr.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason', 'updated_at'])
        return self.success_response(message=_('Payout request rejected.'))

    @action(detail=True, methods=['post'], url_path='mark-paid', permission_classes=[IsAdminUser])
    def mark_paid(self, request, pk=None):
        pr = self.get_object()
        pr.status = 'paid'
        pr.paid_at = timezone.now()
        pr.gateway_reference = request.data.get('gateway_reference', '')
        pr.save(update_fields=['status', 'paid_at', 'gateway_reference', 'updated_at'])
        return self.success_response(message=_('Payout marked as paid.'))


# ── Referral ─────────────────────────────────────────────────────────────────

class ReferralProgramViewSet(MonetizationBaseViewSet):
    queryset = ReferralProgram.objects.all()
    serializer_class = ReferralProgramSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]


class ReferralLinkViewSet(MonetizationBaseViewSet):
    queryset = ReferralLink.objects.select_related('user', 'program').all()
    serializer_class = ReferralLinkSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['get'], url_path='my-link')
    def my_link(self, request):
        link = ReferralLink.objects.filter(user=request.user, is_active=True).first()
        if not link:
            return Response({'success': True, 'data': None, 'message': _('No referral link found.')})
        return self.success_response(data=ReferralLinkSerializer(link).data)


class ReferralCommissionViewSet(MonetizationBaseViewSet):
    queryset = ReferralCommission.objects.select_related('referrer', 'referee', 'program').all()
    serializer_class = ReferralCommissionSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(referrer=self.request.user)
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        from .services import ReferralService
        data = ReferralService.get_summary(request.user)
        return self.success_response(data=data)


# ── Daily Streak ─────────────────────────────────────────────────────────────

class DailyStreakViewSet(MonetizationBaseViewSet):
    queryset = DailyStreak.objects.select_related('user').all()
    serializer_class = DailyStreakSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=False, methods=['get'], url_path='me')
    def my_streak(self, request):
        streak, _ = DailyStreak.objects.get_or_create(user=request.user)
        return self.success_response(data=DailyStreakSerializer(streak).data)

    @action(detail=False, methods=['post'], url_path='check-in')
    def check_in(self, request):
        from .services import GamificationService
        result = GamificationService.daily_check_in(request.user)
        return self.success_response(data=result, message=_('Check-in recorded.'))


# ── Spin Wheel Config ─────────────────────────────────────────────────────────

class SpinWheelConfigViewSet(MonetizationBaseViewSet):
    queryset = SpinWheelConfig.objects.all()
    serializer_class = SpinWheelConfigSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]


class PrizeConfigViewSet(MonetizationBaseViewSet):
    queryset = PrizeConfig.objects.select_related('wheel_config').all()
    serializer_class = PrizeConfigSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        wheel = self.request.query_params.get('wheel_id')
        if wheel:
            qs = qs.filter(wheel_config_id=wheel)
        return qs


# ── Flash Sale ────────────────────────────────────────────────────────────────

class FlashSaleViewSet(MonetizationBaseViewSet):
    queryset = FlashSale.objects.all()

    def get_serializer_class(self):
        if self.action in ('list',):
            return FlashSaleListSerializer
        return FlashSaleDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='live')
    def live_now(self, request):
        now = timezone.now()
        sales = FlashSale.objects.filter(
            is_active=True, starts_at__lte=now, ends_at__gte=now
        )
        return self.success_response(data=FlashSaleListSerializer(sales, many=True).data)


# ── Coupon ────────────────────────────────────────────────────────────────────

class CouponViewSet(MonetizationBaseViewSet):
    queryset = Coupon.objects.all()

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return CouponSerializer
        return CouponPublicSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='validate')
    def validate_coupon(self, request):
        from .services import CouponService
        code   = request.data.get('code', '').strip().upper()
        coupon, error = CouponService.validate(code, request.user)
        if error:
            return self.error_response(message=error)
        return self.success_response(
            data=CouponPublicSerializer(coupon).data,
            message=_('Coupon is valid.'),
        )

    @action(detail=False, methods=['post'], url_path='redeem')
    def redeem(self, request):
        from .services import CouponService
        code = request.data.get('code', '').strip().upper()
        result = CouponService.redeem(code, request.user)
        if result.get('error'):
            return self.error_response(message=result['error'])
        return self.success_response(data=result, message=_('Coupon redeemed successfully.'),
                                      status_code=status.HTTP_201_CREATED)


class CouponUsageViewSet(TenantFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CouponUsage.objects.select_related('coupon', 'user').all()
    serializer_class = CouponUsageSerializer
    permission_classes = [IsAdminUser]


# ── Fraud Alert ───────────────────────────────────────────────────────────────

class FraudAlertViewSet(MonetizationBaseViewSet):
    queryset = FraudAlert.objects.select_related('user').all()
    serializer_class = FraudAlertSerializer

    def get_permissions(self):
        return [IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        severity   = self.request.query_params.get('severity')
        resolution = self.request.query_params.get('resolution')
        alert_type = self.request.query_params.get('type')
        if severity:
            qs = qs.filter(severity=severity)
        if resolution:
            qs = qs.filter(resolution=resolution)
        if alert_type:
            qs = qs.filter(alert_type=alert_type)
        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.resolution     = request.data.get('resolution', 'cleared')
        alert.resolved_by    = request.user
        alert.resolved_at    = timezone.now()
        alert.resolution_note = request.data.get('note', '')
        alert.save(update_fields=['resolution', 'resolved_by', 'resolved_at',
                                   'resolution_note', 'updated_at'])
        return self.success_response(message=_('Alert resolved.'))

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        from django.db.models import Count
        data = {
            'open_alerts':    FraudAlert.objects.filter(resolution='open').count(),
            'critical_open':  FraudAlert.objects.filter(resolution='open', severity='critical').count(),
            'today':          FraudAlert.objects.filter(created_at__date=timezone.now().date()).count(),
        }
        return self.success_response(data=data)


# ── Revenue Goal ──────────────────────────────────────────────────────────────

class RevenueGoalViewSet(MonetizationBaseViewSet):
    queryset = RevenueGoal.objects.all()
    serializer_class = RevenueGoalSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'update_progress'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['patch'], url_path='update-progress', permission_classes=[IsAdminUser])
    def update_progress(self, request, pk=None):
        goal  = self.get_object()
        value = request.data.get('current_value')
        if value is None:
            return self.error_response(message=_('current_value is required.'))
        from decimal import Decimal
        goal.current_value = Decimal(str(value))
        goal.save(update_fields=['current_value', 'updated_at'])
        return self.success_response(
            data={'progress_pct': str(goal.progress_pct), 'is_achieved': goal.is_achieved}
        )


# ── Publisher Account ─────────────────────────────────────────────────────────

class PublisherAccountViewSet(MonetizationBaseViewSet):
    queryset = PublisherAccount.objects.all()
    serializer_class = PublisherAccountSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'verify', 'suspend', 'activate'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='verify', permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        account = self.get_object()
        account.is_verified = True
        account.verified_at = timezone.now()
        account.status = 'active'
        account.save(update_fields=['is_verified', 'verified_at', 'status', 'updated_at'])
        return self.success_response(message=_('Account verified and activated.'))

    @action(detail=True, methods=['post'], url_path='suspend', permission_classes=[IsAdminUser])
    def suspend(self, request, pk=None):
        account = self.get_object()
        account.status = 'suspended'
        account.save(update_fields=['status', 'updated_at'])
        return self.success_response(message=_('Account suspended.'))


# ── Notification Template ─────────────────────────────────────────────────────

class MonetizationNotificationTemplateViewSet(MonetizationBaseViewSet):
    queryset = MonetizationNotificationTemplate.objects.all()
    serializer_class = MonetizationNotificationTemplateSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='preview')
    def preview(self, request, pk=None):
        template = self.get_object()
        context  = request.data.get('context', {})
        rendered = template.render(context)
        return self.success_response(data={'rendered': rendered})
