# cms/viewsets_new/missing_viewsets_group3.py
"""
Missing ViewSets — Group 3

Covers:
  - ReferralCode, ReferralRelationship, ReferralEarning
  - RTBConfig, RTBAdSlot, RTBBidLog
  - UserSession
  - SmartLink, SmartLinkRule, SmartLinkClick
  - SurveyReward, RewardTransaction, RewardPool
  - TaskSchedule, TaskExecution, TaskQueue
  - VideoContent, VideoGenerationRequest
  - PayoutMethod
  - WorkflowState, WorkflowTransition, WorkflowRule
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

logger = logging.getLogger('cms.viewsets.group3')


# ─────────────────────────────────────────────────────────────────────────────
# REFERRAL VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class ReferralCodeViewSet(viewsets.ModelViewSet):
    """
    CRUD for referral codes.

    Endpoints:
        GET    /api/v3/referral-codes/
        POST   /api/v3/referral-codes/
        GET    /api/v3/referral-codes/{id}/
        PATCH  /api/v3/referral-codes/{id}/
        DELETE /api/v3/referral-codes/{id}/
        GET    /api/v3/referral-codes/my/
        GET    /api/v3/referral-codes/{id}/stats/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'is_active']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.referral import ReferralCode
        qs = ReferralCode.objects.select_related('user')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import ReferralCodeSerializer
        return ReferralCodeSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my(self, request):
        """Return current user's referral code."""
        from api.cms.models_new.referral import ReferralCode
        code = ReferralCode.objects.filter(user=request.user, is_active=True).first()
        if not code:
            return Response({'detail': 'No active referral code found'}, status=404)
        serializer = self.get_serializer(code)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Return usage stats for this referral code."""
        obj = self.get_object()
        from api.cms.models_new.referral import ReferralRelationship, ReferralEarning
        referrals = ReferralRelationship.objects.filter(referral_code=obj).count()
        earnings = ReferralEarning.objects.filter(
            referral_code=obj
        ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('amount'))
        return Response({
            'code': obj.code,
            'total_referrals': referrals,
            'total_earnings': float(earnings['total'] or 0),
        })


class ReferralRelationshipViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for referral relationships.

    Endpoints:
        GET    /api/v3/referral-relationships/
        GET    /api/v3/referral-relationships/{id}/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['referrer', 'referred_user', 'referral_code']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.referral import ReferralRelationship
        qs = ReferralRelationship.objects.select_related('referrer', 'referred_user', 'referral_code')
        if not self.request.user.is_staff:
            qs = qs.filter(referrer=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import ReferralRelationshipSerializer
        return ReferralRelationshipSerializer


class ReferralEarningViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for referral earnings.

    Endpoints:
        GET    /api/v3/referral-earnings/
        GET    /api/v3/referral-earnings/{id}/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'referral_code', 'earning_type']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.referral import ReferralEarning
        qs = ReferralEarning.objects.select_related('user', 'referral_code')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import ReferralEarningSerializer
        return ReferralEarningSerializer


# ─────────────────────────────────────────────────────────────────────────────
# RTB (REAL-TIME BIDDING) VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class RTBConfigViewSet(viewsets.ModelViewSet):
    """
    CRUD for RTB configuration.

    Endpoints:
        GET    /api/v3/rtb-configs/
        POST   /api/v3/rtb-configs/
        GET    /api/v3/rtb-configs/{id}/
        PATCH  /api/v3/rtb-configs/{id}/
        DELETE /api/v3/rtb-configs/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'provider']

    def get_queryset(self):
        from api.cms.models_new.rtb import RTBConfig
        return RTBConfig.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import RTBConfigSerializer
        return RTBConfigSerializer


class RTBAdSlotViewSet(viewsets.ModelViewSet):
    """
    CRUD for RTB ad slots.

    Endpoints:
        GET    /api/v3/rtb-ad-slots/
        POST   /api/v3/rtb-ad-slots/
        GET    /api/v3/rtb-ad-slots/{id}/
        PATCH  /api/v3/rtb-ad-slots/{id}/
        DELETE /api/v3/rtb-ad-slots/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['rtb_config', 'slot_type', 'is_active']
    search_fields = ['name', 'slot_id']

    def get_queryset(self):
        from api.cms.models_new.rtb import RTBAdSlot
        return RTBAdSlot.objects.select_related('rtb_config')

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import RTBAdSlotSerializer
        return RTBAdSlotSerializer


class RTBBidLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for RTB bid logs.

    Endpoints:
        GET    /api/v3/rtb-bid-logs/
        GET    /api/v3/rtb-bid-logs/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ad_slot', 'win_status', 'date']
    ordering = ['-timestamp']

    def get_queryset(self):
        from api.cms.models_new.rtb import RTBBidLog
        return RTBBidLog.objects.select_related('ad_slot')

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import RTBBidLogSerializer
        return RTBBidLogSerializer


# ─────────────────────────────────────────────────────────────────────────────
# SESSION VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for user sessions.

    Endpoints:
        GET    /api/v3/user-sessions/
        GET    /api/v3/user-sessions/{id}/
        GET    /api/v3/user-sessions/active/
        POST   /api/v3/user-sessions/{id}/terminate/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'is_active', 'device_type']
    ordering = ['-started_at']

    def get_queryset(self):
        from api.cms.models_new.sessions import UserSession
        qs = UserSession.objects.select_related('user')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.UserProfileSerializer import UserSessionSerializer
        return UserSessionSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return active sessions for current user."""
        from api.cms.models_new.sessions import UserSession
        qs = UserSession.objects.filter(user=request.user, is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Terminate a session."""
        obj = self.get_object()
        if obj.user != request.user and not request.user.is_staff:
            return Response({'detail': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        obj.is_active = False
        obj.ended_at = timezone.now()
        obj.save(update_fields=['is_active', 'ended_at'])
        return Response({'status': 'terminated', 'id': obj.id})


# ─────────────────────────────────────────────────────────────────────────────
# SMARTLINK VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class SmartLinkViewSet(viewsets.ModelViewSet):
    """
    CRUD + stats for smart links.

    Endpoints:
        GET    /api/v3/smart-links/
        POST   /api/v3/smart-links/
        GET    /api/v3/smart-links/{id}/
        PATCH  /api/v3/smart-links/{id}/
        DELETE /api/v3/smart-links/{id}/
        GET    /api/v3/smart-links/{id}/stats/
        POST   /api/v3/smart-links/{id}/activate/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'link_type', 'created_by']
    search_fields = ['name', 'destination_url', 'short_code']
    ordering_fields = ['created_at', 'click_count', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.smartlink import SmartLink
        qs = SmartLink.objects.select_related('created_by')
        if not self.request.user.is_staff:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import SmartLinkSerializer
        return SmartLinkSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Return click stats for this smart link."""
        obj = self.get_object()
        from api.cms.models_new.smartlink import SmartLinkClick
        clicks = SmartLinkClick.objects.filter(smart_link=obj)
        return Response({
            'smart_link_id': obj.id,
            'total_clicks': clicks.count(),
            'unique_clicks': clicks.values('ip_address').distinct().count(),
        })

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Enable the smart link."""
        obj = self.get_object()
        obj.is_active = True
        obj.save(update_fields=['is_active'])
        return Response({'status': 'activated', 'id': obj.id})


class SmartLinkRuleViewSet(viewsets.ModelViewSet):
    """CRUD for smart link redirect rules."""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['smart_link', 'rule_type', 'is_active']

    def get_queryset(self):
        from api.cms.models_new.smartlink import SmartLinkRule
        return SmartLinkRule.objects.select_related('smart_link')

    def get_serializer_class(self):
        from api.cms.serializers_new.SmartLinkReferralRTBSerializer import SmartLinkRuleSerializer
        return SmartLinkRuleSerializer


# ─────────────────────────────────────────────────────────────────────────────
# SURVEY REWARDS VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class VideoContentViewSet(viewsets.ModelViewSet):
    """
    CRUD for video content.

    Endpoints:
        GET    /api/v3/videos/
        POST   /api/v3/videos/
        GET    /api/v3/videos/{id}/
        PATCH  /api/v3/videos/{id}/
        DELETE /api/v3/videos/{id}/
        POST   /api/v3/videos/{id}/publish/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_published', 'video_type', 'created_by']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'published_at', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.video import VideoContent
        qs = VideoContent.objects.select_related('created_by')
        if not self.request.user.is_staff:
            qs = qs.filter(is_published=True)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import VideoContentSerializer
        return VideoContentSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish the video."""
        obj = self.get_object()
        obj.is_published = True
        obj.published_at = timezone.now()
        obj.save(update_fields=['is_published', 'published_at'])
        return Response({'status': 'published', 'id': obj.id})


class VideoGenerationRequestViewSet(viewsets.ModelViewSet):
    """
    CRUD for AI video generation requests.

    Endpoints:
        GET    /api/v3/video-generation-requests/
        POST   /api/v3/video-generation-requests/
        GET    /api/v3/video-generation-requests/{id}/
        DELETE /api/v3/video-generation-requests/{id}/
        GET    /api/v3/video-generation-requests/{id}/status/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'requested_by']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.video import VideoGenerationRequest
        qs = VideoGenerationRequest.objects.select_related('requested_by')
        if not self.request.user.is_staff:
            qs = qs.filter(requested_by=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import VideoGenerationRequestSerializer
        return VideoGenerationRequestSerializer

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Poll generation status."""
        obj = self.get_object()
        return Response({'id': obj.id, 'status': obj.status, 'progress': getattr(obj, 'progress', 0)})


# ─────────────────────────────────────────────────────────────────────────────
# WITHDRAWAL SUB-MODEL: PAYOUT METHOD
# ─────────────────────────────────────────────────────────────────────────────

class PayoutMethodViewSet(viewsets.ModelViewSet):
    """
    CRUD for user payout methods (bank, bKash, PayPal, etc.).

    Endpoints:
        GET    /api/v3/payout-methods/
        POST   /api/v3/payout-methods/
        GET    /api/v3/payout-methods/{id}/
        PATCH  /api/v3/payout-methods/{id}/
        DELETE /api/v3/payout-methods/{id}/
        POST   /api/v3/payout-methods/{id}/set-default/
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'method_type', 'is_verified', 'is_default']

    def get_queryset(self):
        from api.cms.models_new.withdrawal import PayoutMethod
        qs = PayoutMethod.objects.select_related('user')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        from api.cms.serializers_new.FinanceSerializer import PayoutMethodSerializer
        return PayoutMethodSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this payout method as default."""
        from api.cms.models_new.withdrawal import PayoutMethod
        PayoutMethod.objects.filter(user=request.user, is_default=True).update(is_default=False)
        obj = self.get_object()
        obj.is_default = True
        obj.save(update_fields=['is_default'])
        return Response({'status': 'set_as_default', 'id': obj.id})


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW VIEWSETS
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowStateViewSet(viewsets.ModelViewSet):
    """
    CRUD for workflow states.

    Endpoints:
        GET    /api/v3/workflow-states/
        POST   /api/v3/workflow-states/
        GET    /api/v3/workflow-states/{id}/
        PATCH  /api/v3/workflow-states/{id}/
        DELETE /api/v3/workflow-states/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['workflow', 'is_initial', 'is_final', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['display_order', 'name']

    def get_queryset(self):
        from api.cms.models_new.workflow import WorkflowState
        return WorkflowState.objects.select_related('workflow')

    def get_serializer_class(self):
        from api.cms.serializers_new.WorkflowSerializer import WorkflowStateSerializer
        return WorkflowStateSerializer


class WorkflowTransitionViewSet(viewsets.ModelViewSet):
    """
    CRUD for workflow transitions.

    Endpoints:
        GET    /api/v3/workflow-transitions/
        POST   /api/v3/workflow-transitions/
        GET    /api/v3/workflow-transitions/{id}/
        PATCH  /api/v3/workflow-transitions/{id}/
        DELETE /api/v3/workflow-transitions/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['workflow', 'from_state', 'to_state', 'is_active']

    def get_queryset(self):
        from api.cms.models_new.workflow import WorkflowTransition
        return WorkflowTransition.objects.select_related('workflow', 'from_state', 'to_state')

    def get_serializer_class(self):
        from api.cms.serializers_new.WorkflowSerializer import WorkflowTransitionSerializer
        return WorkflowTransitionSerializer


class WorkflowRuleViewSet(viewsets.ModelViewSet):
    """
    CRUD for workflow rules (auto-transition triggers).

    Endpoints:
        GET    /api/v3/workflow-rules/
        POST   /api/v3/workflow-rules/
        GET    /api/v3/workflow-rules/{id}/
        PATCH  /api/v3/workflow-rules/{id}/
        DELETE /api/v3/workflow-rules/{id}/
    """
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['transition', 'rule_type', 'is_active']
    search_fields = ['name', 'description']

    def get_queryset(self):
        from api.cms.models_new.workflow import WorkflowRule
        return WorkflowRule.objects.select_related('transition')

    def get_serializer_class(self):
        from api.cms.serializers_new.WorkflowSerializer import WorkflowRuleSerializer
        return WorkflowRuleSerializer
