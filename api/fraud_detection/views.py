# =============================================================================
# fraud_detection/views.py
#
# Primary views module — exported from here so urls.py can import everything
# from a single namespace:  from api.fraud_detection import views
#
# Architecture: thin façade — each class delegates to the rich
# implementations in viewset.py and views_extended.py.
# =============================================================================
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.decorators import audit_log
from api.fraud_detection.mixins import FraudDetectionMixin, UserRiskAssessmentMixin
from api.fraud_detection.models import (
    FraudAlert,
    FraudAttempt,
    FraudCase,
    FraudRule,
    FraudSettings,
    UserRiskProfile,
)
from api.fraud_detection.permissions import (
    CanBanUsers,
    CanManageFraudRules,
    CanReviewFraudCases,
    CanViewRiskProfiles,
    HasFraudDetectionPermission,
)
from api.fraud_detection.serializers import (
    FraudAlertSerializer,
    FraudAttemptSerializer,
    FraudDetectionResponseSerializer,
    FraudRuleSerializer,
    FraudSettingsSerializer,
    FraudStatisticsSerializer,
    UserRiskProfileSerializer,
)

# Pull in the rich viewset implementations
from api.fraud_detection.viewset import (
    BaseFraudDetectionViewSet,
    FraudAlertViewSet as _FraudAlertViewSet,
    FraudCaseViewSet,
    FraudRuleViewSet as _FraudRuleViewSet,
    UserRiskProfileViewSet as _UserRiskProfileViewSet,
)

User = get_user_model()
logger = logging.getLogger('fraud_detection')


# =============================================================================
# Re-exported ViewSets (used by the DRF router in urls.py)
# =============================================================================

class FraudRuleViewSet(_FraudRuleViewSet):
    """
    CRUD + custom actions for FraudRule objects.
    Delegates entirely to viewset.FraudRuleViewSet.
    Extra permission: CanManageFraudRules for write operations.
    """
    permission_classes  = [IsAuthenticated, CanManageFraudRules]


class FraudAttemptViewSet(BaseFraudDetectionViewSet):
    """
    List, retrieve, and manage FraudAttempt records.
    """
    permission_classes  = [IsAuthenticated, HasFraudDetectionPermission]
    serializer_class    = FraudAttemptSerializer
    queryset            = FraudAttempt.objects.select_related('user', 'resolved_by').all()
    ordering_fields     = ['created_at', 'fraud_score', 'attempt_type']
    search_fields       = ['user__username', 'attempt_type', 'description']
    filterset_fields    = ['status', 'attempt_type', 'is_resolved']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    from rest_framework.decorators import action as _action

    @_action(detail=False, methods=['get'])
    def statistics(self, request):
        """Aggregate fraud attempt statistics."""
        from django.db.models import Count, Avg
        now   = timezone.now()
        day   = now - timezone.timedelta(hours=24)
        week  = now - timezone.timedelta(days=7)
        month = now - timezone.timedelta(days=30)

        qs = self.get_queryset()
        data = {
            'total':       qs.count(),
            'last_24h':    qs.filter(created_at__gte=day).count(),
            'last_7d':     qs.filter(created_at__gte=week).count(),
            'last_30d':    qs.filter(created_at__gte=month).count(),
            'unresolved':  qs.filter(is_resolved=False).count(),
            'avg_score':   qs.aggregate(a=Avg('fraud_score'))['a'] or 0,
            'by_type':     list(qs.values('attempt_type').annotate(count=Count('id'))),
            'by_status':   list(qs.values('status').annotate(count=Count('id'))),
        }
        return Response(data)

    @_action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk-update status / resolution on multiple attempts."""
        attempt_ids = request.data.get('ids', [])
        new_status  = request.data.get('status')

        if not attempt_ids or not new_status:
            return Response(
                {'detail': "'ids' and 'status' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = (
            FraudAttempt.objects
            .filter(pk__in=attempt_ids)
            .update(status=new_status, updated_at=timezone.now())
        )
        return Response({'updated': updated})


class UserRiskProfileViewSet(_UserRiskProfileViewSet, UserRiskAssessmentMixin):
    """
    Read + update user risk profiles.
    """
    permission_classes  = [IsAuthenticated, CanViewRiskProfiles]

    from rest_framework.decorators import action as _action

    @_action(detail=False, methods=['get'])
    def high_risk_users(self, request):
        """Return users with overall_risk_score >= threshold."""
        threshold = int(request.query_params.get('threshold', 70))
        qs = UserRiskProfile.objects.filter(
            overall_risk_score__gte=threshold
        ).select_related('user').order_by('-overall_risk_score')
        page = self.paginate_queryset(qs)
        serializer = UserRiskProfileSerializer(page or qs, many=True)
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @_action(detail=False, methods=['get'])
    def risk_distribution(self, request):
        """Histogram of users by risk band."""
        from django.db.models import Count
        data = {
            'low':      UserRiskProfile.objects.filter(overall_risk_score__lt=30).count(),
            'medium':   UserRiskProfile.objects.filter(overall_risk_score__range=(30, 60)).count(),
            'high':     UserRiskProfile.objects.filter(overall_risk_score__range=(61, 80)).count(),
            'critical': UserRiskProfile.objects.filter(overall_risk_score__gt=80).count(),
        }
        return Response(data)


class FraudAlertViewSet(_FraudAlertViewSet):
    """
    List, retrieve, and resolve FraudAlert records.
    """
    permission_classes  = [IsAuthenticated, HasFraudDetectionPermission]

    from rest_framework.decorators import action as _action

    @_action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Quick stats for the alert badge / dashboard widget."""
        now  = timezone.now()
        day  = now - timezone.timedelta(hours=24)
        data = {
            'total_unresolved':    FraudAlert.objects.filter(is_resolved=False).count(),
            'critical_unresolved': FraudAlert.objects.filter(is_resolved=False, priority='critical').count(),
            'resolved_today':      FraudAlert.objects.filter(is_resolved=True, resolved_at__date=now.date()).count(),
            'new_last_24h':        FraudAlert.objects.filter(created_at__gte=day).count(),
        }
        return Response(data)

    @audit_log(action='bulk_resolve_alerts')
    @_action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        """Resolve multiple alerts at once."""
        alert_ids = request.data.get('ids', [])
        notes     = request.data.get('notes', '')

        if not alert_ids:
            return Response({'detail': "'ids' is required."}, status=status.HTTP_400_BAD_REQUEST)

        resolved = (
            FraudAlert.objects
            .filter(pk__in=alert_ids, is_resolved=False)
            .update(
                is_resolved=True,
                resolved_by=request.user,
                resolved_at=timezone.now(),
                resolution_notes=notes,
            )
        )
        return Response({'resolved': resolved})


# =============================================================================
# FraudDetectionAPIView  — unified detection endpoint
# =============================================================================

class FraudDetectionAPIView(FraudDetectionMixin, APIView):
    """
    POST  /fraud/detect/check-user/
    POST  /fraud/detect/check-transaction/
    POST  /fraud/detect/check-offer/
    POST  /fraud/detect/check-device/

    The specific *action* is passed as a URL kwarg from urls.py.
    """
    permission_classes = [IsAuthenticated]

    _ACTION_HANDLERS = {
        'check_user':        '_check_user',
        'check_transaction': '_check_transaction',
        'check_offer':       '_check_offer',
        'check_device':      '_check_device',
    }

    def post(self, request, *args, **kwargs):
        action_name = kwargs.get('action', 'check_user')
        handler_name = self._ACTION_HANDLERS.get(action_name)
        if not handler_name:
            return Response({'detail': f'Unknown action: {action_name}'}, status=status.HTTP_400_BAD_REQUEST)
        return getattr(self, handler_name)(request)

    # Safe alias so GET also works for 'check_user'
    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    # ------------------------------------------------------------------
    def _check_user(self, request):
        user_id = request.data.get('user_id') or request.user.pk
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        ctx    = self.get_fraud_context()
        ctx['target_user_id'] = user_id
        result = self.run_fraud_check(ctx)
        return Response(result)

    def _check_transaction(self, request):
        ctx              = self.get_fraud_context()
        ctx['amount']    = request.data.get('amount', 0)
        ctx['currency']  = request.data.get('currency', 'USD')
        ctx['method']    = request.data.get('payment_method', '')
        result           = self.run_fraud_check(ctx)
        return Response(result)

    def _check_offer(self, request):
        ctx              = self.get_fraud_context()
        ctx['offer_id']  = request.data.get('offer_id')
        ctx['reward']    = request.data.get('reward_amount', 0)
        result           = self.run_fraud_check(ctx)
        return Response(result)

    def _check_device(self, request):
        ctx              = self.get_fraud_context()
        ctx['device']    = request.data.get('device_data', {})
        result           = self.run_fraud_check(ctx)
        return Response(result)


# =============================================================================
# AutoBanAPIView
# =============================================================================

class AutoBanAPIView(APIView):
    """
    POST  /fraud/auto-ban/process-attempt/
    POST  /fraud/auto-ban/ban-user/
    POST  /fraud/auto-ban/suspend-user/
    POST  /fraud/auto-ban/restrict-user/
    POST  /fraud/auto-ban/unban-users/
    """
    permission_classes = [IsAuthenticated, CanBanUsers]

    _ACTION_HANDLERS = {
        'process_attempt': '_process_attempt',
        'ban_user':        '_ban_user',
        'suspend_user':    '_suspend_user',
        'restrict_user':   '_restrict_user',
        'unban_users':     '_unban_users',
    }

    def post(self, request, *args, **kwargs):
        action_name  = kwargs.get('action', 'process_attempt')
        handler_name = self._ACTION_HANDLERS.get(action_name)
        if not handler_name:
            return Response({'detail': f'Unknown action: {action_name}'}, status=status.HTTP_400_BAD_REQUEST)
        return getattr(self, handler_name)(request)

    # ------------------------------------------------------------------
    @audit_log(action='process_attempt')
    def _process_attempt(self, request):
        attempt_id = request.data.get('attempt_id')
        if not attempt_id:
            return Response({'detail': "'attempt_id' is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            attempt = FraudAttempt.objects.select_related('user').get(pk=attempt_id)
        except FraudAttempt.DoesNotExist:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        banned = False
        if attempt.fraud_score >= 90:
            self._do_ban(attempt.user, reason='Auto-ban: fraud score ≥ 90')
            banned = True

        return Response({'attempt_id': attempt_id, 'auto_banned': banned, 'score': attempt.fraud_score})

    @audit_log(action='ban_user')
    def _ban_user(self, request):
        user_id = request.data.get('user_id')
        reason  = request.data.get('reason', '')
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        self._do_ban(user, reason=reason)
        return Response({'user_id': user_id, 'action': 'banned'})

    @audit_log(action='suspend_user')
    def _suspend_user(self, request):
        user_id       = request.data.get('user_id')
        duration_days = int(request.data.get('duration_days', 7))
        reason        = request.data.get('reason', '')
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        self._do_suspend(user, duration_days=duration_days, reason=reason)
        return Response({'user_id': user_id, 'action': 'suspended', 'duration_days': duration_days})

    @audit_log(action='restrict_user')
    def _restrict_user(self, request):
        user_id      = request.data.get('user_id')
        restrictions = request.data.get('restrictions', {})
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile, _ = UserRiskProfile.objects.get_or_create(user=user)
        profile.is_restricted = True
        profile.restrictions  = restrictions
        profile.save(update_fields=['is_restricted', 'restrictions'])
        return Response({'user_id': user_id, 'action': 'restricted', 'restrictions': restrictions})

    @audit_log(action='unban_users')
    def _unban_users(self, request):
        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response({'detail': "'user_ids' is required."}, status=status.HTTP_400_BAD_REQUEST)
        unbanned = 0
        for uid in user_ids:
            try:
                user = User.objects.get(pk=uid)
                user.is_active = True
                user.save(update_fields=['is_active'])
                try:
                    profile = user.risk_profile
                    profile.is_restricted = False
                    profile.save(update_fields=['is_restricted'])
                except Exception:
                    pass
                unbanned += 1
            except User.DoesNotExist:
                pass
        return Response({'unbanned': unbanned})

    # ------------------------------------------------------------------
    @staticmethod
    def _do_ban(user, reason: str = '') -> None:
        user.is_active = False
        user.save(update_fields=['is_active'])
        try:
            profile, _ = UserRiskProfile.objects.get_or_create(user=user)
            profile.is_flagged    = True
            profile.is_restricted = True
            profile.restrictions  = {'ban_reason': reason, 'banned_at': timezone.now().isoformat()}
            profile.save(update_fields=['is_flagged', 'is_restricted', 'restrictions'])
        except Exception:
            pass

    @staticmethod
    def _do_suspend(user, duration_days: int = 7, reason: str = '') -> None:
        try:
            profile, _ = UserRiskProfile.objects.get_or_create(user=user)
            profile.is_restricted = True
            profile.restrictions  = {
                'suspension_reason': reason,
                'suspended_until':   (timezone.now() + timezone.timedelta(days=duration_days)).isoformat(),
            }
            profile.save(update_fields=['is_restricted', 'restrictions'])
        except Exception:
            pass


# =============================================================================
# ReviewAPIView
# =============================================================================

class ReviewAPIView(APIView):
    """
    GET   /fraud/review/pending/
    GET   /fraud/review/case/<uuid>/
    GET   /fraud/review/stats/
    POST  /fraud/review/decide/
    POST  /fraud/review/escalate/
    POST  /fraud/review/comment/
    POST  /fraud/review/batch/
    """
    permission_classes = [IsAuthenticated, CanReviewFraudCases]

    _ACTION_HANDLERS = {
        'pending':  ('GET',  '_pending'),
        'case':     ('GET',  '_case'),
        'stats':    ('GET',  '_stats'),
        'decide':   ('POST', '_decide'),
        'escalate': ('POST', '_escalate'),
        'comment':  ('POST', '_comment'),
        'batch':    ('POST', '_batch'),
    }

    def get(self, request, *args, **kwargs):
        return self._dispatch(request, 'GET', *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._dispatch(request, 'POST', *args, **kwargs)

    def _dispatch(self, request, http_method, *args, **kwargs):
        action_name = kwargs.get('action', 'pending')
        entry = self._ACTION_HANDLERS.get(action_name)
        if not entry:
            return Response({'detail': f'Unknown action: {action_name}'}, status=status.HTTP_400_BAD_REQUEST)
        expected_method, handler_name = entry
        if http_method != expected_method:
            return Response({'detail': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return getattr(self, handler_name)(request, *args, **kwargs)

    # ------------------------------------------------------------------
    def _pending(self, request, *args, **kwargs):
        attempts = (
            FraudAttempt.objects
            .filter(status='pending')
            .select_related('user')
            .order_by('-fraud_score', '-created_at')[:50]
        )
        serializer = FraudAttemptSerializer(attempts, many=True)
        return Response({'results': serializer.data, 'count': len(serializer.data)})

    def _case(self, request, *args, **kwargs):
        attempt_id = kwargs.get('attempt_id')
        try:
            attempt = FraudAttempt.objects.select_related('user').get(attempt_id=attempt_id)
        except FraudAttempt.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FraudAttemptSerializer(attempt).data)

    def _stats(self, request, *args, **kwargs):
        from django.db.models import Avg
        now  = timezone.now()
        day  = now - timezone.timedelta(hours=24)
        week = now - timezone.timedelta(days=7)
        data = {
            'pending':         FraudAttempt.objects.filter(status='pending').count(),
            'confirmed_today': FraudAttempt.objects.filter(status='confirmed', updated_at__date=now.date()).count(),
            'dismissed_today': FraudAttempt.objects.filter(status='dismissed', updated_at__date=now.date()).count(),
            'avg_score':       FraudAttempt.objects.filter(created_at__gte=week).aggregate(a=Avg('fraud_score'))['a'] or 0,
        }
        return Response(data)

    @audit_log(action='review_decide')
    def _decide(self, request, *args, **kwargs):
        attempt_id = request.data.get('attempt_id')
        decision   = request.data.get('decision')   # 'confirmed' | 'dismissed'
        notes      = request.data.get('notes', '')

        if not attempt_id or decision not in ('confirmed', 'dismissed'):
            return Response(
                {'detail': "'attempt_id' and 'decision' (confirmed|dismissed) are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            attempt = FraudAttempt.objects.get(pk=attempt_id)
        except FraudAttempt.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        attempt.status           = decision
        attempt.is_resolved      = True
        attempt.resolved_at      = timezone.now()
        attempt.resolved_by      = request.user
        attempt.resolution_notes = notes
        attempt.save(update_fields=['status', 'is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes'])
        return Response({'attempt_id': attempt_id, 'decision': decision})

    @audit_log(action='review_escalate')
    def _escalate(self, request, *args, **kwargs):
        attempt_id = request.data.get('attempt_id')
        reason     = request.data.get('reason', '')
        try:
            attempt = FraudAttempt.objects.get(pk=attempt_id)
        except FraudAttempt.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        attempt.status = 'investigating'
        attempt.save(update_fields=['status'])
        return Response({'attempt_id': attempt_id, 'status': 'escalated', 'reason': reason})

    def _comment(self, request, *args, **kwargs):
        attempt_id = request.data.get('attempt_id')
        comment    = request.data.get('comment', '')
        try:
            attempt = FraudAttempt.objects.get(pk=attempt_id)
        except FraudAttempt.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        # Append comment to resolution_notes
        sep  = '\n\n---\n' if attempt.resolution_notes else ''
        ts   = timezone.now().strftime('%Y-%m-%d %H:%M')
        user = request.user.username
        attempt.resolution_notes += f'{sep}[{ts} {user}] {comment}'
        attempt.save(update_fields=['resolution_notes'])
        return Response({'attempt_id': attempt_id, 'comment_added': True})

    @audit_log(action='review_batch')
    def _batch(self, request, *args, **kwargs):
        items = request.data.get('items', [])
        if not items:
            return Response({'detail': "'items' is required."}, status=status.HTTP_400_BAD_REQUEST)

        results = []
        for item in items:
            aid      = item.get('attempt_id')
            decision = item.get('decision')
            try:
                attempt          = FraudAttempt.objects.get(pk=aid)
                attempt.status   = decision
                attempt.is_resolved = decision in ('confirmed', 'dismissed')
                attempt.resolved_by = request.user
                attempt.resolved_at = timezone.now()
                attempt.save(update_fields=['status', 'is_resolved', 'resolved_by', 'resolved_at'])
                results.append({'attempt_id': aid, 'ok': True})
            except Exception as exc:
                results.append({'attempt_id': aid, 'ok': False, 'error': str(exc)})
        return Response({'results': results})


# =============================================================================
# FraudDashboardAPIView
# =============================================================================

class FraudDashboardAPIView(APIView):
    """
    GET  /fraud/dashboard/

    Returns a consolidated overview for the admin dashboard.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        now   = timezone.now()
        day   = now - timezone.timedelta(hours=24)
        week  = now - timezone.timedelta(days=7)
        month = now - timezone.timedelta(days=30)

        from django.db.models import Avg

        data = {
            'attempts': {
                'total':       FraudAttempt.objects.count(),
                'last_24h':    FraudAttempt.objects.filter(created_at__gte=day).count(),
                'last_7d':     FraudAttempt.objects.filter(created_at__gte=week).count(),
                'last_30d':    FraudAttempt.objects.filter(created_at__gte=month).count(),
                'pending':     FraudAttempt.objects.filter(status='pending').count(),
                'avg_score':   FraudAttempt.objects.aggregate(a=Avg('fraud_score'))['a'] or 0,
            },
            'alerts': {
                'total_unresolved': FraudAlert.objects.filter(is_resolved=False).count(),
                'critical':         FraudAlert.objects.filter(is_resolved=False, priority='critical').count(),
                'new_today':        FraudAlert.objects.filter(created_at__date=now.date()).count(),
            },
            'cases': {
                'open':        FraudCase.objects.filter(status='open').count(),
                'escalated':   FraudCase.objects.filter(status='escalated').count(),
            },
            'users': {
                'flagged':    UserRiskProfile.objects.filter(is_flagged=True).count(),
                'restricted': UserRiskProfile.objects.filter(is_restricted=True).count(),
                'high_risk':  UserRiskProfile.objects.filter(overall_risk_score__gte=70).count(),
            },
            'rules': {
                'active': FraudRule.objects.filter(is_active=True).count(),
                'total':  FraudRule.objects.count(),
            },
            'generated_at': now.isoformat(),
        }
        return Response(data)


# =============================================================================
# FraudSettingsAPIView
# =============================================================================

class FraudSettingsAPIView(APIView):
    """
    GET   /fraud/settings/block-vpn/
    POST  /fraud/settings/block-vpn/
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        settings_obj = FraudSettings.get()
        return Response(FraudSettingsSerializer(settings_obj).data)

    @audit_log(action='update_fraud_settings')
    def post(self, request):
        settings_obj = FraudSettings.get()
        serializer   = FraudSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            # Bust the settings cache
            from django.core.cache import cache
            from api.fraud_detection.constants import CACHE_KEYS
            cache.delete(CACHE_KEYS['fraud_settings'])
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
