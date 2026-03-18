# =============================================================================
# api/promotions/views.py
# DRF ViewSets — সব model এর জন্য full CRUD + custom actions
# =============================================================================

import logging
from django.db.models import Q, Avg, Sum, Count, F
from django.utils import timezone
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import (
    PromotionCategory, Platform, RewardPolicy, CurrencyRate,
    Campaign, TaskSubmission, Dispute,
    PromotionTransaction, EscrowWallet, ReferralCommissionLog,
    Blacklist, FraudReport, DeviceFingerprint, UserReputation, CampaignAnalytics,
)
from .serializers import (
    PromotionCategorySerializer, PlatformSerializer, RewardPolicySerializer,
    CurrencyRateSerializer, CampaignListSerializer, CampaignDetailSerializer,
    CampaignCreateSerializer, TaskSubmissionListSerializer, TaskSubmissionDetailSerializer,
    TaskSubmissionCreateSerializer, SubmissionReviewSerializer,
    DisputeSerializer, DisputeResolveSerializer, VerificationLogSerializer,
    PromotionTransactionSerializer, EscrowWalletSerializer,
    ReferralCommissionLogSerializer, BlacklistSerializer,
    FraudReportSerializer, DeviceFingerprintSerializer,
    UserReputationSerializer, CampaignAnalyticsSerializer,
)
from .permissions import (
    IsAdminUser, IsWorker, IsAdminOrReadOnly,
    IsCampaignOwnerOrAdmin, CanCreateCampaign, CanViewCampaignDetails,
    IsSubmissionOwnerOrAdmin, CanReviewSubmission, CanSubmitTask,
    IsDisputeOwnerOrAdmin, CanResolveDispute,
    CanViewFinancialData, CanManageBlacklist, CanViewAnalytics,
)
from .filters import (
    CampaignFilter, TaskSubmissionFilter, DisputeFilter,
    PromotionTransactionFilter, FraudReportFilter, BlacklistFilter,
    CampaignAnalyticsFilter, RewardPolicyFilter, ReferralCommissionFilter,
    UserReputationFilter,
)
from .pagination_throttles import (
    StandardResultsPagination, TransactionCursorPagination,
    SubmissionCursorPagination, SmallResultsPagination,
    SubmissionThrottle, CampaignCreateThrottle, DisputeThrottle,
    WithdrawalThrottle,
)
from .exceptions import (
    CampaignNotFoundException, SubmissionNotFoundException,
    InvalidCampaignTransitionException, SubmissionAlreadyReviewedException,
)
from .choices import CampaignStatus, SubmissionStatus, DisputeStatus

logger = logging.getLogger('promotions.views')


# =============================================================================
# ── SYSTEM FOUNDATION ────────────────────────────────────────────────────────
# =============================================================================

class PromotionCategoryViewSet(viewsets.ModelViewSet):
    queryset            = PromotionCategory.objects.filter(is_active=True)
    serializer_class    = PromotionCategorySerializer
    permission_classes  = [IsAdminOrReadOnly]
    pagination_class    = SmallResultsPagination
    search_fields       = ['name']
    ordering_fields     = ['sort_order', 'name']
    ordering            = ['sort_order']


class PlatformViewSet(viewsets.ModelViewSet):
    queryset            = Platform.objects.filter(is_active=True)
    serializer_class    = PlatformSerializer
    permission_classes  = [IsAdminOrReadOnly]
    pagination_class    = SmallResultsPagination
    ordering            = ['name']


class RewardPolicyViewSet(viewsets.ModelViewSet):
    queryset            = RewardPolicy.objects.select_related('category').filter(is_active=True)
    serializer_class    = RewardPolicySerializer
    permission_classes  = [IsAdminOrReadOnly]
    filterset_class     = RewardPolicyFilter
    ordering_fields     = ['country_code', 'rate_usd']
    ordering            = ['country_code']

    @action(detail=False, methods=['get'], url_path='by-country/(?P<country_code>[A-Z]{2})')
    def by_country(self, request, country_code=None):
        """নির্দিষ্ট দেশের সব reward policies।"""
        policies = self.get_queryset().filter(country_code=country_code.upper())
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)


class CurrencyRateViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """Currency rates — Admin create করতে পারবে, সবাই read করতে পারবে।"""
    queryset            = CurrencyRate.objects.order_by('-fetched_at')
    serializer_class    = CurrencyRateSerializer
    permission_classes  = [IsAdminOrReadOnly]
    pagination_class    = StandardResultsPagination

    @action(detail=False, methods=['get'], url_path='latest/(?P<from_currency>[A-Z]{3})/(?P<to_currency>[A-Z]{3})')
    def latest(self, request, from_currency=None, to_currency=None):
        """দুটো currency এর সর্বশেষ rate।"""
        rate = CurrencyRate.get_latest_rate(from_currency, to_currency)
        if not rate:
            return Response({'detail': 'Rate not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(rate)
        return Response(serializer.data)


# =============================================================================
# ── CAMPAIGN ────────────────────────────────────────────────────────────────
# =============================================================================

class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes  = [IsAuthenticated]
    pagination_class    = StandardResultsPagination
    filterset_class     = CampaignFilter
    search_fields       = ['title', 'description']
    ordering_fields     = ['created_at', 'total_budget_usd', 'filled_slots']
    ordering            = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs   = Campaign.objects.select_related(
            'category', 'platform', 'advertiser', 'schedule', 'targeting', 'limits',
        ).prefetch_related('steps', 'bonus_policies', 'creatives')

        if user.is_staff:
            return qs  # Admin সব দেখতে পাবে
        if getattr(user, 'is_advertiser', False):
            # Advertiser নিজেরটা + active campaign দেখবে
            return qs.filter(Q(advertiser=user) | Q(status=CampaignStatus.ACTIVE))
        # Worker: শুধু active campaign
        return qs.filter(status=CampaignStatus.ACTIVE)

    def get_serializer_class(self):
        if self.action == 'create':
            return CampaignCreateSerializer
        if self.action == 'list':
            return CampaignListSerializer
        return CampaignDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [CanCreateCampaign()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsCampaignOwnerOrAdmin()]
        if self.action in ('approve', 'cancel'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == 'create':
            return [CampaignCreateThrottle()]
        return super().get_throttles()

    # ── Custom Actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Campaign approve করে active করো।"""
        campaign = self.get_object()
        if campaign.status != CampaignStatus.PENDING:
            raise InvalidCampaignTransitionException(campaign.status, CampaignStatus.ACTIVE)
        campaign.status = CampaignStatus.ACTIVE
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Campaign approved and activated.'})

    @action(detail=True, methods=['post'], permission_classes=[IsCampaignOwnerOrAdmin])
    def pause(self, request, pk=None):
        """Campaign pause করো।"""
        campaign = self.get_object()
        if campaign.status != CampaignStatus.ACTIVE:
            raise InvalidCampaignTransitionException(campaign.status, CampaignStatus.PAUSED)
        campaign.status = CampaignStatus.PAUSED
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Campaign paused.'})

    @action(detail=True, methods=['post'], permission_classes=[IsCampaignOwnerOrAdmin])
    def resume(self, request, pk=None):
        """Paused campaign resume করো।"""
        campaign = self.get_object()
        if campaign.status != CampaignStatus.PAUSED:
            raise InvalidCampaignTransitionException(campaign.status, CampaignStatus.ACTIVE)
        campaign.status = CampaignStatus.ACTIVE
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Campaign resumed.'})

    @action(detail=True, methods=['post'], permission_classes=[IsCampaignOwnerOrAdmin])
    def cancel(self, request, pk=None):
        """Campaign cancel করো।"""
        campaign = self.get_object()
        if campaign.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED):
            raise InvalidCampaignTransitionException(campaign.status, CampaignStatus.CANCELLED)
        campaign.status = CampaignStatus.CANCELLED
        campaign.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Campaign cancelled.'})

    @action(detail=True, methods=['post'], permission_classes=[IsCampaignOwnerOrAdmin])
    def archive(self, request, pk=None):
        """Archive campaign (Google Ads style)."""
        campaign = self.get_object()
        if campaign.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED):
            return Response({'detail': 'Campaign is already archived/cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        campaign.status = CampaignStatus.CANCELLED
        campaign.save(update_fields=['status', 'updated_at'])
        logger.info(f"Campaign {campaign.pk} archived by {request.user}")
        return Response({'id': campaign.pk, 'status': 'archived', 'message': 'Campaign archived'})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate campaign — Google Ads style copy."""
        original = self.get_object()
        new_campaign = Campaign.objects.create(
            advertiser=request.user,
            title=f"{original.title} (Copy)",
            description=original.description,
            category=original.category,
            platform=original.platform,
            target_url=original.target_url,
            total_budget_usd=original.total_budget_usd,
            total_slots=original.total_slots,
            profit_margin=original.profit_margin,
            bonus_rate=original.bonus_rate,
            promo_type=original.promo_type,
            yield_optimization=original.yield_optimization,
            risk_level=original.risk_level,
            risk_score=original.risk_score,
            traffic_monitor=original.traffic_monitor,
            status='draft',
            sparkline_data=[],
        )
        from .serializers import CampaignListSerializer
        return Response(CampaignListSerializer(new_campaign).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def budget_top_up(self, request, pk=None):
        """Add more budget to campaign (Advertiser tops up)."""
        campaign = self.get_object()
        from decimal import Decimal
        amount = Decimal(str(request.data.get('amount', 0)))
        if amount <= 0:
            return Response({'detail': 'Amount must be positive.'}, status=status.HTTP_400_BAD_REQUEST)
        campaign.total_budget_usd = campaign.total_budget_usd + amount
        campaign.save(update_fields=['total_budget_usd'])
        return Response({
            'id': campaign.pk,
            'new_total_budget': str(campaign.total_budget_usd),
            'remaining_budget': str(campaign.remaining_budget),
            'message': f'Budget topped up by ${amount}'
        })

    @action(detail=True, methods=['get'], permission_classes=[CanViewAnalytics])
    def analytics(self, request, pk=None):
        """Campaign এর analytics data।"""
        campaign   = self.get_object()
        analytics  = campaign.analytics.order_by('-date')[:30]
        serializer = CampaignAnalyticsSerializer(analytics, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Campaign এর সব submissions।"""
        campaign = self.get_object()
        qs = TaskSubmission.objects.filter(campaign=campaign)
        if not request.user.is_staff:
            qs = qs.filter(worker=request.user)
        serializer = TaskSubmissionListSerializer(qs, many=True)
        return Response(serializer.data)


# =============================================================================
# ── TASK SUBMISSION ──────────────────────────────────────────────────────────
# =============================================================================

class TaskSubmissionViewSet(viewsets.ModelViewSet):
    pagination_class   = SubmissionCursorPagination
    filterset_class    = TaskSubmissionFilter
    ordering_fields    = ['submitted_at', 'reward_usd']
    ordering           = ['-submitted_at']

    def get_queryset(self):
        user = self.request.user
        qs   = TaskSubmission.objects.select_related(
            'worker', 'campaign', 'reviewer', 'device_fingerprint'
        ).prefetch_related('proofs', 'verification_logs')

        if user.is_staff:
            return qs
        return qs.filter(worker=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskSubmissionCreateSerializer
        if self.action == 'list':
            return TaskSubmissionListSerializer
        if self.action in ('approve', 'reject'):
            return SubmissionReviewSerializer
        return TaskSubmissionDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [CanSubmitTask()]
        if self.action in ('approve', 'reject'):
            return [CanReviewSubmission()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAdminUser()]
        return [IsSubmissionOwnerOrAdmin()]

    def get_throttles(self):
        if self.action == 'create':
            return [SubmissionThrottle()]
        return super().get_throttles()

    # ── Custom Actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], permission_classes=[CanReviewSubmission])
    def approve(self, request, pk=None):
        """Submission approve করো।"""
        submission = self.get_object()
        serializer = SubmissionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if submission.status not in (SubmissionStatus.PENDING, SubmissionStatus.DISPUTED):
            raise SubmissionAlreadyReviewedException()

        submission.approve(
            reviewer=request.user,
            note=serializer.validated_data.get('note', ''),
        )

        # Reward override হলে apply করো
        reward = serializer.validated_data.get('reward_usd')
        if reward is not None:
            TaskSubmission.objects.filter(pk=submission.pk).update(reward_usd=reward)

        return Response({'detail': 'Submission approved.', 'submission_id': submission.pk})

    @action(detail=True, methods=['post'], permission_classes=[CanReviewSubmission])
    def reject(self, request, pk=None):
        """Submission reject করো।"""
        submission = self.get_object()
        serializer = SubmissionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if submission.status not in (SubmissionStatus.PENDING, SubmissionStatus.DISPUTED):
            raise SubmissionAlreadyReviewedException()

        submission.reject(
            reviewer=request.user,
            note=serializer.validated_data['note'],
        )
        return Response({'detail': 'Submission rejected.', 'submission_id': submission.pk})

    @action(detail=True, methods=['get'])
    def verification_logs(self, request, pk=None):
        """Submission এর verification history।"""
        submission = self.get_object()
        logs       = submission.verification_logs.order_by('-verified_at')
        serializer = VerificationLogSerializer(logs, many=True)
        return Response(serializer.data)


# =============================================================================
# ── DISPUTE ──────────────────────────────────────────────────────────────────
# =============================================================================

class DisputeViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = DisputeSerializer
    filterset_class    = DisputeFilter
    pagination_class   = StandardResultsPagination
    ordering           = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs   = Dispute.objects.select_related('worker', 'submission', 'resolved_by')
        if user.is_staff:
            return qs
        return qs.filter(worker=user)

    def get_permissions(self):
        if self.action == 'create':
            return [IsWorker()]
        if self.action == 'resolve':
            return [CanResolveDispute()]
        return [IsDisputeOwnerOrAdmin()]

    def get_throttles(self):
        if self.action == 'create':
            return [DisputeThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        serializer.save(worker=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[CanResolveDispute])
    def resolve(self, request, pk=None):
        """Dispute resolve করো।"""
        dispute    = self.get_object()
        serializer = DisputeResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if dispute.status in (DisputeStatus.RESOLVED_APPROVED, DisputeStatus.RESOLVED_REJECTED):
            return Response({'detail': 'Dispute already resolved.'}, status=status.HTTP_400_BAD_REQUEST)

        decision = serializer.validated_data['decision']
        new_status = (
            DisputeStatus.RESOLVED_APPROVED if decision == 'approve'
            else DisputeStatus.RESOLVED_REJECTED
        )

        dispute.status      = new_status
        dispute.admin_note  = serializer.validated_data['admin_note']
        dispute.resolved_at = timezone.now()
        dispute.resolved_by = request.user
        dispute.save(update_fields=['status', 'admin_note', 'resolved_at', 'resolved_by'])

        return Response({'detail': f'Dispute {decision}d successfully.'})


# =============================================================================
# ── FINANCE ──────────────────────────────────────────────────────────────────
# =============================================================================

class PromotionTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Transaction — read only। Programmatically তৈরি হয়।"""
    serializer_class   = PromotionTransactionSerializer
    pagination_class   = TransactionCursorPagination
    filterset_class    = PromotionTransactionFilter
    permission_classes = [CanViewFinancialData]

    def get_queryset(self):
        user = self.request.user
        qs   = PromotionTransaction.objects.select_related('user', 'campaign')
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """User এর transaction summary।"""
        from django.db.models import Sum
        from .choices import TransactionType
        qs = self.get_queryset()
        data = {
            'total_earned':    qs.filter(type=TransactionType.REWARD).aggregate(s=Sum('amount_usd'))['s'] or 0,
            'total_withdrawn': qs.filter(type=TransactionType.WITHDRAWAL).aggregate(s=Sum('amount_usd'))['s'] or 0,
            'total_referral':  qs.filter(type=TransactionType.REFERRAL).aggregate(s=Sum('amount_usd'))['s'] or 0,
            'total_bonus':     qs.filter(type=TransactionType.BONUS).aggregate(s=Sum('amount_usd'))['s'] or 0,
        }
        return Response(data)


class EscrowWalletViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = EscrowWalletSerializer
    permission_classes = [CanViewFinancialData]

    def get_queryset(self):
        user = self.request.user
        qs   = EscrowWallet.objects.select_related('campaign', 'advertiser')
        if user.is_staff:
            return qs
        return qs.filter(advertiser=user)


class ReferralCommissionLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = ReferralCommissionLogSerializer
    pagination_class   = StandardResultsPagination
    filterset_class    = ReferralCommissionFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs   = ReferralCommissionLog.objects.select_related('referrer', 'referred')
        if user.is_staff:
            return qs
        return qs.filter(referrer=user)


# =============================================================================
# ── SECURITY ─────────────────────────────────────────────────────────────────
# =============================================================================

class BlacklistViewSet(viewsets.ModelViewSet):
    queryset           = Blacklist.objects.select_related('added_by').order_by('-id')
    serializer_class   = BlacklistSerializer
    permission_classes = [CanManageBlacklist]
    filterset_class    = BlacklistFilter
    pagination_class   = StandardResultsPagination
    search_fields      = ['value', 'reason']
    ordering           = ['-created_at']

    @action(detail=False, methods=['post'])
    def check(self, request):
        """একটি value blacklisted কিনা দ্রুত check করো।"""
        bl_type = request.data.get('type')
        value   = request.data.get('value')
        if not bl_type or not value:
            return Response({'detail': 'type এবং value দিতে হবে।'}, status=400)
        is_blocked = Blacklist.is_blacklisted(bl_type, value)
        return Response({'is_blacklisted': is_blocked, 'type': bl_type, 'value': value})


class FraudReportViewSet(viewsets.ModelViewSet):
    queryset           = FraudReport.objects.select_related('user', 'submission', 'reviewed_by_admin').order_by('-id')
    serializer_class   = FraudReportSerializer
    permission_classes = [IsAdminUser]
    filterset_class    = FraudReportFilter
    pagination_class   = StandardResultsPagination
    ordering           = ['-created_at']

    @action(detail=True, methods=['post'])
    def take_action(self, request, pk=None):
        """Fraud report এ action নাও।"""
        report = self.get_object()
        action_taken = request.data.get('action')
        valid_actions = ['flagged', 'warned', 'banned', 'ignored']
        if action_taken not in valid_actions:
            return Response({'detail': f'Valid actions: {valid_actions}'}, status=400)
        report.action_taken       = action_taken
        report.reviewed_by_admin  = request.user
        report.admin_note         = request.data.get('note', '')
        report.save(update_fields=['action_taken', 'reviewed_by_admin', 'admin_note'])
        return Response({'detail': f'Action "{action_taken}" taken on fraud report #{report.pk}.'})


class DeviceFingerprintViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = DeviceFingerprintSerializer
    permission_classes = [IsAuthenticated]
    pagination_class   = StandardResultsPagination
    ordering           = ['-last_seen']

    def get_queryset(self):
        user = self.request.user
        qs   = DeviceFingerprint.objects.select_related('user')
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        fingerprint_hash = serializer.validated_data['fingerprint_hash']
        # Existing fingerprint এ linked_account_count বাড়াও
        existing = DeviceFingerprint.objects.filter(fingerprint_hash=fingerprint_hash).first()
        if existing and existing.user != self.request.user:
            from django.db.models import F
            DeviceFingerprint.objects.filter(pk=existing.pk).update(
                linked_account_count=F('linked_account_count') + 1,
                last_seen=timezone.now(),
            )
        serializer.save(user=self.request.user)


class UserReputationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = UserReputationSerializer
    filterset_class    = UserReputationFilter
    pagination_class   = StandardResultsPagination
    permission_classes = [IsAuthenticated]
    ordering           = ['-trust_score']

    def get_queryset(self):
        user = self.request.user
        qs   = UserReputation.objects.select_related('user')
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """নিজের reputation দেখো।"""
        reputation, _ = UserReputation.objects.get_or_create(user=request.user)
        serializer    = self.get_serializer(reputation)
        return Response(serializer.data)


# =============================================================================
# ── ANALYTICS ────────────────────────────────────────────────────────────────
# =============================================================================

class CampaignAnalyticsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class   = CampaignAnalyticsSerializer
    filterset_class    = CampaignAnalyticsFilter
    pagination_class   = StandardResultsPagination
    permission_classes = [CanViewAnalytics]
    ordering           = ['-date']

    def get_queryset(self):
        user = self.request.user
        qs   = CampaignAnalytics.objects.select_related('campaign')
        if user.is_staff:
            return qs
        return qs.filter(campaign__advertiser=user)

    @action(detail=False, methods=['get'])
    def overall(self, request):
        """Admin এর সামগ্রিক platform analytics।"""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)

        from django.db.models import Sum, Count
        from .choices import SubmissionStatus
        today = timezone.now().date()
        data = CampaignAnalytics.objects.filter(date=today).aggregate(
            total_views       = Sum('total_views'),
            total_submissions = Sum('total_submissions'),
            total_approved    = Sum('approved_count'),
            total_spent       = Sum('total_spent_usd'),
            total_commission  = Sum('admin_commission_usd'),
            total_fraud       = Sum('fraud_detected'),
        )
        return Response({'date': str(today), **data})


# =============================================================================
# ── STATS & SPARKLINE (Frontend এর জন্য) ────────────────────────────────────
# =============================================================================
from rest_framework.decorators import api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as R

@api_view(['GET'])
@pc([IsAuthenticated])
def promotions_stats(request):
    from .models import Campaign, TaskSubmission, AdminCommissionLog
    from django.db.models import Sum
    qs = Campaign.objects.all()
    commission = AdminCommissionLog.objects.aggregate(total=Sum('commission_usd'))['total'] or 0
    data = {
        'total':                qs.filter(status='active').count(),
        'users_engaged':        TaskSubmission.objects.filter(status='approved').values('worker').distinct().count(),
        'promos_managed':       qs.count(),
        'active_count':         qs.filter(status='active').count(),
        'paused_count':         qs.filter(status='paused').count(),
        'draft_count':          qs.filter(status='draft').count(),
        'total_budget':         str(qs.aggregate(t=Sum('total_budget_usd'))['t'] or 0),
        'total_spent':          str(qs.aggregate(t=Sum('spent_usd'))['t'] or 0),
        'admin_commission':     str(commission),
        'pending_submissions':  TaskSubmission.objects.filter(status='pending').count(),
        'approved_submissions': TaskSubmission.objects.filter(status='approved').count(),
    }
    return R(data)

@api_view(['GET'])
@pc([IsAuthenticated])
def promotions_sparkline(request, pk):
    from .models import Campaign, CampaignAnalytics
    from datetime import date, timedelta
    days = int(request.query_params.get('days', 7))
    try:
        campaign = Campaign.objects.get(pk=pk)
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        analytics = CampaignAnalytics.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date,
        ).order_by('date').values('date', 'total_spent_usd')
        if analytics:
            data   = [float(a['total_spent_usd']) for a in analytics]
            labels = [str(a['date']) for a in analytics]
        else:
            raw    = campaign.sparkline_data or [3, 5, 4, 7, 6, 8, 9, 7, 10, 8]
            data   = raw[:days]
            labels = [(end_date - timedelta(days=days - 1 - i)).strftime('%m/%d') for i in range(len(data))]
        return R({'data': data, 'labels': labels})
    except Campaign.DoesNotExist:
        return R({'data': [], 'labels': []}, status=404)


# =============================================================================
# ── SIMPLE ADMIN CAMPAIGN CREATE/UPDATE ──────────────────────────────────────
# =============================================================================
from rest_framework.decorators import api_view, permission_classes as pc
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as R2
from rest_framework import status as st

@api_view(['POST'])
@pc([IsAuthenticated])
def campaign_quick_create(request):
    from .models import Campaign, PromotionCategory, Platform
    d = request.data
    cat  = PromotionCategory.objects.first()
    plat = Platform.objects.first()
    c = Campaign.objects.create(
        advertiser       = request.user,
        category         = cat,
        platform         = plat,
        title            = d.get('title', 'Untitled'),
        description      = d.get('description', ''),
        status           = d.get('status', 'active'),
        bonus_rate       = d.get('bonus_rate') or 0,
        yield_optimization = d.get('yield_optimization') or 0,
        risk_level       = d.get('risk_level', 'LOW'),
        risk_score       = d.get('risk_score') or 0,
        verified         = d.get('verified', False),
        sparkline_data   = [3,5,4,7,6,8,9,7,10,8],
        target_url       = d.get('target_url', 'https://example.com'),
        total_budget_usd = d.get('total_budget_usd') or 1000,
        total_slots      = d.get('total_slots') or 100,
        profit_margin    = d.get('profit_margin') or 30,
    )
    from .serializers import CampaignListSerializer
    return R2(CampaignListSerializer(c).data, status=201)


@api_view(['PUT', 'PATCH'])
@pc([IsAuthenticated])
def campaign_quick_update(request, pk):
    from .models import Campaign
    try:
        c = Campaign.objects.get(pk=pk)
    except Campaign.DoesNotExist:
        return R2({'detail': 'Not found'}, status=404)
    d = request.data
    for field in ['title','description','status','bonus_rate','yield_optimization','risk_level','risk_score','verified']:
        if field in d:
            setattr(c, field, d[field])
    c.save()
    from .serializers import CampaignListSerializer
    return R2(CampaignListSerializer(c).data)


@api_view(['DELETE'])
@pc([IsAuthenticated])
def campaign_quick_delete(request, pk):
    from .models import Campaign
    try:
        Campaign.objects.get(pk=pk).delete()
        return R2({'detail': 'Deleted'}, status=204)
    except Campaign.DoesNotExist:
        return R2({'detail': 'Not found'}, status=404)


# =============================================================================
# ── BIDDING ENDPOINTS ─────────────────────────────────────────────────────────
# =============================================================================
@api_view(['GET', 'POST'])
@pc([IsAuthenticated])
def bidding_list(request):
    from .models import CampaignBid
    from decimal import Decimal
    if request.method == 'GET':
        bids = CampaignBid.objects.select_related('campaign', 'advertiser').order_by('-bid_at')[:50]
        data = [{
            'id': b.id,
            'campaign_id': b.campaign_id,
            'campaign_title': b.campaign.title,
            'advertiser': b.advertiser.username,
            'bid_amount': str(b.bid_amount),
            'floor_price': str(b.floor_price),
            'final_price': str(b.final_price) if b.final_price else None,
            'auction_type': b.auction_type,
            'status': b.status,
            'bid_at': b.bid_at.isoformat(),
        } for b in bids]
        stats = {
            'total_bids': CampaignBid.objects.count(),
            'active_auctions': CampaignBid.objects.filter(status='pending').count(),
            'won_bids': CampaignBid.objects.filter(status='won').count(),
            'avg_bid': str(CampaignBid.objects.filter(status='won').aggregate(
                avg=Avg('bid_amount'))['avg'] or 0),
        }
        return R({'stats': stats, 'bids': data})
    else:
        from .models import Campaign
        d = request.data
        try:
            campaign = Campaign.objects.get(pk=d.get('campaign_id'))
        except Campaign.DoesNotExist:
            return R({'detail': 'Campaign not found'}, status=404)
        bid = CampaignBid.objects.create(
            campaign=campaign,
            advertiser=request.user,
            bid_amount=Decimal(str(d.get('bid_amount', 0))),
            floor_price=Decimal(str(d.get('floor_price', 0))),
            auction_type=d.get('auction_type', 'gsp'),
        )
        return R({'id': bid.id, 'status': bid.status, 'bid_amount': str(bid.bid_amount)}, status=201)


@api_view(['POST'])
@pc([IsAuthenticated])
def bidding_resolve(request, pk):
    from .models import CampaignBid
    from django.utils import timezone
    try:
        bid = CampaignBid.objects.get(pk=pk)
    except CampaignBid.DoesNotExist:
        return R({'detail': 'Not found'}, status=404)
    action = request.data.get('action', 'won')
    bid.status = action
    bid.resolved_at = timezone.now()
    if action == 'won':
        bid.final_price = bid.bid_amount
    bid.save()
    return R({'id': bid.id, 'status': bid.status})


@api_view(['GET', 'POST'])
@pc([IsAuthenticated])
def user_offers(request):
    from decimal import Decimal
    if request.method == 'POST':
        d = request.data
        reward_bdt = Decimal(str(d.get('reward_bdt', 2)))
        cat  = PromotionCategory.objects.first()
        plat = Platform.objects.first()
        campaign = Campaign.objects.create(
            advertiser=request.user,
            category=cat, platform=plat,
            title=d.get('title', ''),
            description=d.get('description', ''),
            target_url=d.get('target_url', ''),
            status='pending',
            total_budget_usd=reward_bdt * Decimal(str(d.get('total_slots', 100))) * Decimal('1.20'),
            total_slots=int(d.get('total_slots', 100)),
            profit_margin=20,
            bonus_rate=0, yield_optimization=0,
            risk_level='LOW', risk_score=5,
        )
        return R({'id': campaign.id, 'status': 'pending', 'message': 'Submitted for review'}, status=201)
    campaigns = Campaign.objects.filter(advertiser=request.user).order_by('-created_at')
    return R({'results': [{'id':c.id,'title':c.title,'status':c.status} for c in campaigns]})


@api_view(['GET'])
@pc([IsAuthenticated])
def promotions_analytics_overall(request):
    from .models import Campaign, TaskSubmission
    return R({
        'total_campaigns': Campaign.objects.count(),
        'active_campaigns': Campaign.objects.filter(status='active').count(),
        'total_submissions': TaskSubmission.objects.count(),
        'approved_submissions': TaskSubmission.objects.filter(status='approved').count(),
    })


# =============================================================================
# ── FRONTEND ALIAS VIEWS (/promotions/ → /promotions/campaigns/) ─────────────
# Frontend calls /api/promotions/ but campaigns live at /api/promotions/campaigns/
# These aliases bridge the gap without breaking existing API.
# =============================================================================

@api_view(['GET', 'POST'])
@pc([IsAuthenticated])
def promotions_list_alias(request):
    """GET /api/promotions/ — list or create campaign (frontend alias)."""
    from .models import Campaign, PromotionCategory, Platform
    from .serializers import CampaignListSerializer
    from decimal import Decimal

    if request.method == 'POST':
        d = request.data
        cat  = PromotionCategory.objects.filter(is_active=True).first()
        plat = Platform.objects.filter(is_active=True).first()
        if not cat or not plat:
            return R({'detail': 'No category or platform found. Add one first.'}, status=400)
        c = Campaign.objects.create(
            advertiser=request.user,
            category=cat, platform=plat,
            title=d.get('title', 'Untitled'),
            description=d.get('description', ''),
            status=d.get('status', 'active'),
            bonus_rate=d.get('bonus_rate') or 0,
            promo_type=d.get('promo_type', 'bonus'),
            yield_optimization=d.get('yield_optimization') or 0,
            risk_level=d.get('risk_level', 'LOW'),
            risk_score=d.get('risk_score') or 0,
            verified=d.get('verified', False),
            traffic_monitor=d.get('traffic_monitor', True),
            sparkline_data=d.get('sparkline_data', [3,5,4,7,6,8,9,7,10,8]),
            target_url=d.get('target_url', 'https://example.com'),
            total_budget_usd=d.get('total_budget_usd') or 1000,
            total_slots=d.get('total_slots') or 100,
            profit_margin=d.get('profit_margin') or 30,
        )
        return R(CampaignListSerializer(c).data, status=201)

    # GET — list with filters
    qs = Campaign.objects.select_related('category', 'platform')
    promo_type = request.query_params.get('promo_type')
    search     = request.query_params.get('search')
    stat       = request.query_params.get('status')
    if promo_type: qs = qs.filter(promo_type=promo_type)
    if search:     qs = qs.filter(title__icontains=search)
    if stat:       qs = qs.filter(status=stat)
    page_size = int(request.query_params.get('page_size', 20))
    page      = int(request.query_params.get('page', 1))
    total     = qs.count()
    start     = (page - 1) * page_size
    qs        = qs.order_by('-created_at')[start:start + page_size]
    return R({
        'count':    total,
        'next':     None,
        'previous': None,
        'results':  CampaignListSerializer(qs, many=True).data,
    })


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@pc([IsAuthenticated])
def promotions_detail_alias(request, pk):
    """GET/PATCH/DELETE /api/promotions/:id/ — campaign detail (frontend alias)."""
    from .models import Campaign
    from .serializers import CampaignListSerializer
    try:
        c = Campaign.objects.get(pk=pk)
    except Campaign.DoesNotExist:
        return R({'detail': 'Not found.'}, status=404)

    if request.method == 'DELETE':
        c.delete()
        return R({'detail': 'Deleted'}, status=204)

    if request.method in ('PUT', 'PATCH'):
        d = request.data
        for field in ['title', 'description', 'status', 'bonus_rate', 'promo_type',
                      'yield_optimization', 'risk_level', 'risk_score', 'verified',
                      'traffic_monitor', 'sparkline_data']:
            if field in d:
                setattr(c, field, d[field])
        c.save()

    return R(CampaignListSerializer(c).data)


@api_view(['POST'])
@pc([IsAuthenticated])
def promotions_pause_alias(request, pk):
    """POST /api/promotions/:id/pause/"""
    from .models import Campaign
    try:
        c = Campaign.objects.get(pk=pk)
        c.status = 'paused'
        c.save(update_fields=['status'])
        return R({'id': c.pk, 'status': 'paused'})
    except Campaign.DoesNotExist:
        return R({'detail': 'Not found.'}, status=404)


@api_view(['POST'])
@pc([IsAuthenticated])
def promotions_resume_alias(request, pk):
    """POST /api/promotions/:id/resume/"""
    from .models import Campaign
    try:
        c = Campaign.objects.get(pk=pk)
        c.status = 'active'
        c.save(update_fields=['status'])
        return R({'id': c.pk, 'status': 'active'})
    except Campaign.DoesNotExist:
        return R({'detail': 'Not found.'}, status=404)


@api_view(['POST'])
@pc([IsAuthenticated])
def promotions_archive_alias(request, pk):
    """POST /api/promotions/:id/archive/"""
    from .models import Campaign
    try:
        c = Campaign.objects.get(pk=pk)
        c.status = 'cancelled'
        c.save(update_fields=['status'])
        return R({'id': c.pk, 'status': 'archived'})
    except Campaign.DoesNotExist:
        return R({'detail': 'Not found.'}, status=404)