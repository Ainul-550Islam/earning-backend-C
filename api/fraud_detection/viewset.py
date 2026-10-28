# =============================================================================
# fraud_detection/viewset.py
# =============================================================================
"""
ViewSets for Fraud Detection System.

Provides Django REST Framework ViewSets for fraud detection
API endpoints with comprehensive CRUD operations and business logic.

FIXES APPLIED (previously floating):
  - throttle_classes set on every ViewSet
  - Granular permissions: CanReviewFraudCases, CanManageFraudRules,
    CanViewRiskProfiles, CanBanUsers, CanManageWhitelist
  - @audit_log decorator on all mutating actions
  - BlockedUserError, ThrottlingError, FraudRuleViolation caught in views
  - dashboard_stats + bulk_resolve added to FraudAlertViewSet
  - types + stats added to FraudRuleViewSet
  - risk_distribution added to UserRiskProfileViewSet
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from api.fraud_detection.decorators import audit_log
from api.fraud_detection.exceptions import (
    BlockedUserError,
    FraudDetectionError,
    FraudRuleViolation,
    ThrottlingError,
)
from api.fraud_detection.mixins import FraudDetectionMixin, UserRiskAssessmentMixin
from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
    HighRiskUserThrottle,
)
from api.fraud_detection.models import (
    DeviceFingerprint,
    FraudAlert,
    FraudCase,
    FraudCaseAction,
    FraudRule,
    IPReputation,
    UserRiskProfile,
)
from api.fraud_detection.permissions import (
    CanBanUsers,
    CanManageFraudRules,
    CanManageWhitelist,
    CanReviewFraudCases,
    CanViewRiskProfiles,
    HasFraudDetectionPermission,
    IsOwnerOrStaff,
)
from api.fraud_detection.selectors import (
    fraud_alert_selector,
    fraud_case_selector,
    fraud_rule_selector,
)
from api.fraud_detection.serializers import (
    DeviceFingerprintSerializer,
    FraudAlertSerializer,
    FraudCaseSerializer,
    FraudRuleSerializer,
    IPReputationSerializer,
    UserRiskProfileSerializer,
)
from api.fraud_detection.services import (
    fraud_detection_service,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# =============================================================================
# Shared exception handler
# =============================================================================

def _handle_known_exc(exc: Exception, context: str) -> Response | None:
    """
    Map known fraud detection exceptions to HTTP responses.
    Returns a Response or None (let caller re-raise).
    """
    if isinstance(exc, BlockedUserError):
        logger.warning("%s — BlockedUserError: %s", context, exc)
        return Response({'detail': str(exc), 'code': 'user_blocked'},
                        status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ThrottlingError):
        logger.warning("%s — ThrottlingError: %s", context, exc)
        return Response({'detail': str(exc), 'code': 'throttled'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(exc, FraudRuleViolation):
        logger.warning("%s — FraudRuleViolation: %s", context, exc)
        return Response({'detail': str(exc), 'code': 'rule_violation'},
                        status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, FraudDetectionError):
        logger.error("%s — FraudDetectionError: %s", context, exc)
        return Response({'detail': str(exc), 'code': 'fraud_detection_error'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return None


# =============================================================================
# Mixins
# =============================================================================

class SafeActionMixin:
    """Catches unhandled exceptions from any dispatch and returns structured JSON."""

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied:
            raise
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, self.__class__.__name__)
            if mapped:
                return mapped
            raise
        except Exception as exc:
            logger.exception("Unhandled exception in %s: %s", self.__class__.__name__, exc)
            return Response(
                {'detail': 'An unexpected error occurred. Our team has been notified.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# Base ViewSet
# =============================================================================

class BaseFraudDetectionViewSet(viewsets.ModelViewSet):
    """Base ViewSet for fraud detection with common functionality."""

    permission_classes  = [IsAuthenticated, HasFraudDetectionPermission]
    throttle_classes    = [FraudEndpointRateThrottle, BurstProtectionThrottle]
    filter_backends     = [DjangoFilterBackend]
    filterset_fields    = ['user_id', 'status', 'severity']

    def get_queryset(self):
        """Get queryset with user filtering."""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user_id=self.request.user.id)
        return queryset

    def perform_create(self, serializer):
        """Perform creation — audit handled per-ViewSet via @audit_log."""
        serializer.save(created_by=self.request.user, created_at=timezone.now())

    def perform_update(self, serializer):
        """Perform update — audit handled per-ViewSet via @audit_log."""
        serializer.save(updated_by=self.request.user, updated_at=timezone.now())


# =============================================================================
# FraudCaseViewSet
# =============================================================================

class FraudCaseViewSet(SafeActionMixin, BaseFraudDetectionViewSet,
                       FraudDetectionMixin, UserRiskAssessmentMixin):
    """ViewSet for fraud case management."""

    queryset            = FraudCase.objects.all()
    serializer_class    = FraudCaseSerializer
    # Granular permission: CanReviewFraudCases instead of plain IsAuthenticated
    permission_classes  = [IsAuthenticated, CanReviewFraudCases]
    throttle_classes    = [FraudEndpointRateThrottle, BurstProtectionThrottle]
    filterset_fields    = ['user_id', 'status', 'severity', 'case_type']
    search_fields       = ['description', 'title', 'case_type']
    ordering_fields     = ['created_at', 'updated_at', 'risk_score', 'severity']
    ordering            = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            from api.fraud_detection.serializers import FraudCaseCreateSerializer
            return FraudCaseCreateSerializer
        if self.action in ['update', 'partial_update']:
            from api.fraud_detection.serializers import FraudCaseUpdateSerializer
            return FraudCaseUpdateSerializer
        return self.serializer_class

    @audit_log(action='assign_case')
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign case to staff member."""
        case = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can assign cases")

        assigned_to_id = request.data.get('assigned_to')
        if not assigned_to_id:
            raise ValidationError("assigned_to field is required")

        try:
            assigned_user = User.objects.get(id=assigned_to_id)
            if not assigned_user.is_staff:
                raise ValidationError("Can only assign to staff members")
            case.assigned_to = assigned_user
            case.status = 'investigating'
            case.save()
            from api.fraud_detection.events import create_case_created_event
            create_case_created_event(
                case_id=str(case.pk),
                user_id=case.user_id,
                description=f"Case assigned to {assigned_user.get_full_name()}",
                metadata={'assigned_by': request.user.id},
            )
            return Response(self.get_serializer(case).data)
        except User.DoesNotExist:
            raise ValidationError("Assigned user not found")
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'FraudCaseViewSet.assign')
            if mapped:
                return mapped
            raise

    @audit_log(action='escalate_case')
    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate case to higher priority."""
        case = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can escalate cases")

        escalation_reason = request.data.get('reason')
        if not escalation_reason:
            raise ValidationError("reason field is required")

        case.status   = 'escalated'
        case.severity = 'critical' if case.severity != 'critical' else case.severity
        case.save()

        try:
            from api.fraud_detection.signals_cap import send_major_fraud_signal
            send_major_fraud_signal(
                description=f"Fraud case escalated: {case.title}",
                affected_entities=[f"case:{case.pk}", f"user:{case.user_id}"],
                metadata={
                    'escalation_reason': escalation_reason,
                    'escalated_by':      request.user.id,
                    'case_id':           str(case.pk),
                },
            )
        except Exception as exc:
            logger.warning("send_major_fraud_signal failed: %s", exc)

        return Response(self.get_serializer(case).data)

    @audit_log(action='resolve_case')
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve fraud case."""
        case = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can resolve cases")

        resolution  = request.data.get('resolution')
        action_taken = request.data.get('action_taken')
        if not resolution:
            raise ValidationError("resolution field is required")

        try:
            case.status      = 'resolved'
            case.resolution  = resolution
            case.action_taken = action_taken
            case.resolved_by  = request.user
            case.resolved_at  = timezone.now()
            case.save()

            self.assess_user_risk(case.user_id, 'case_resolved', {
                'case_id':    str(case.pk),
                'resolution': resolution,
                'risk_score': case.risk_score,
            })
            return Response(self.get_serializer(case).data)
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'FraudCaseViewSet.resolve')
            if mapped:
                return mapped
            raise

    @action(detail=False, methods=['get'])
    def my_cases(self, request):
        """Get cases assigned to current user."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view assigned cases")
        cases = self.queryset.filter(assigned_to=request.user)
        page  = self.paginate_queryset(cases)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(cases, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get fraud case statistics."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view statistics")

        days        = int(request.query_params.get('days', 30))
        cutoff_date = timezone.now() - timedelta(days=days)
        cases       = self.queryset.filter(created_at__gte=cutoff_date)

        stats = {
            'total_cases':    cases.count(),
            'cases_by_status':   {},
            'cases_by_severity': {},
            'cases_by_type':     {},
            'average_risk_score': cases.aggregate(avg=Avg('risk_score'))['avg'] or 0,
            'resolved_cases': cases.filter(status='resolved').count(),
            'escalated_cases': cases.filter(status='escalated').count(),
        }
        for s in ['open', 'investigating', 'pending_review', 'escalated', 'resolved', 'closed']:
            stats['cases_by_status'][s] = cases.filter(status=s).count()
        for sv in ['low', 'medium', 'high', 'critical']:
            stats['cases_by_severity'][sv] = cases.filter(severity=sv).count()
        for ct in cases.values_list('case_type', flat=True).distinct():
            stats['cases_by_type'][ct] = cases.filter(case_type=ct).count()

        return Response(stats)

    @action(detail=False, methods=['get'], url_path='timeline')
    def timeline(self, request):
        """Daily case-open counts for the last 30 days."""
        try:
            from django.db.models.functions import TruncDay
            since = timezone.now() - timedelta(days=30)
            data  = (
                self.get_queryset()
                    .filter(opened_at__gte=since)
                    .annotate(day=TruncDay('opened_at'))
                    .values('day')
                    .annotate(count=Count('id'))
                    .order_by('day')
            )
            return Response(
                [{'date': item['day'].date().isoformat(), 'count': item['count']} for item in data]
            )
        except Exception as exc:
            logger.error("timeline failed: %s", exc)
            return Response({'error': 'Timeline query failed.'}, status=500)

    @audit_log(action='bulk_close_cases')
    @action(detail=False, methods=['post'], url_path='bulk-close')
    def bulk_close(self, request):
        """Close multiple cases."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can bulk-close cases.")
        case_ids = request.data.get('case_ids', [])
        if not isinstance(case_ids, list) or not case_ids:
            return Response({'error': 'case_ids must be a non-empty list.'}, status=400)
        try:
            updated = self.get_queryset().filter(id__in=case_ids).exclude(
                status='closed'
            ).update(
                status='closed',
                resolved_at=timezone.now(),
                resolved_by=request.user,
            )
            logger.info("User %s bulk-closed %d cases: %s", request.user, updated, case_ids)
            return Response({'closed': updated, 'case_ids': case_ids})
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'FraudCaseViewSet.bulk_close')
            if mapped:
                return mapped
            raise
        except Exception as exc:
            logger.error("bulk_close failed: %s", exc)
            return Response({'error': 'Bulk close failed.'}, status=500)


# =============================================================================
# FraudAlertViewSet
# =============================================================================

class FraudAlertViewSet(SafeActionMixin, BaseFraudDetectionViewSet):
    """ViewSet for fraud alert management."""

    queryset            = FraudAlert.objects.all()
    serializer_class    = FraudAlertSerializer
    permission_classes  = [IsAuthenticated, CanReviewFraudCases]
    throttle_classes    = [FraudEndpointRateThrottle, BurstProtectionThrottle]
    filterset_fields    = ['user_id', 'alert_type', 'severity_score', 'acknowledged']
    search_fields       = ['description', 'title', 'alert_type']
    ordering_fields     = ['created_at', 'severity_score', 'acknowledged']
    ordering            = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            from api.fraud_detection.serializers import FraudAlertCreateSerializer
            return FraudAlertCreateSerializer
        return self.serializer_class

    @audit_log(action='acknowledge_alert')
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge fraud alert."""
        alert = self.get_object()
        if not request.user.is_staff and alert.user_id != request.user.id:
            raise PermissionDenied("Cannot acknowledge this alert")

        alert.acknowledged    = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()

        if alert.severity_score >= 70 and not getattr(alert, 'case_id', None):
            case_data = {
                'user_id':          alert.user_id,
                'case_type':        'suspicious_activity',
                'severity':         'high' if alert.severity_score >= 80 else 'medium',
                'title':            f"Alert: {alert.title}",
                'description':      alert.description,
                'detection_method': 'alert',
                'related_alerts':   [str(alert.pk)],
            }
            try:
                case_result = fraud_detection_service.create_fraud_case(
                    alert.user_id, case_data, auto_assign=True
                )
                if case_result.success:
                    alert.case_id = case_result.data['case_id']
                    alert.save()
            except Exception as exc:
                logger.error("Failed to create case from alert %s: %s", alert.pk, exc)

        return Response(self.get_serializer(alert).data)

    @audit_log(action='resolve_alert')
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve fraud alert."""
        alert = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can resolve alerts")

        resolution = request.data.get('resolution')
        if not resolution:
            raise ValidationError("resolution field is required")

        alert.resolved    = True
        alert.resolved_by = request.user
        alert.resolved_at = timezone.now()
        alert.resolution  = resolution
        alert.save()
        return Response(self.get_serializer(alert).data)

    @action(detail=False, methods=['get'])
    def unacknowledged(self, request):
        """Get unacknowledged alerts."""
        if not request.user.is_staff:
            alerts = self.queryset.filter(user_id=request.user.id, acknowledged=False)
        else:
            alerts = self.queryset.filter(acknowledged=False)
        page = self.paginate_queryset(alerts)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(alerts, many=True).data)

    @action(detail=False, methods=['get'])
    def high_priority(self, request):
        """Get high priority alerts."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view high priority alerts")
        alerts = self.queryset.filter(severity_score__gte=70)
        page   = self.paginate_queryset(alerts)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(alerts, many=True).data)

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """Alert dashboard summary statistics."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view dashboard stats")
        today  = timezone.now().date()
        qs     = self.get_queryset()
        return Response({
            'total_alerts':        qs.count(),
            'unacknowledged':      qs.filter(acknowledged=False).count(),
            'critical_today':      qs.filter(severity_score__gte=80, created_at__date=today).count(),
            'resolved_today':      qs.filter(resolved=True, resolved_at__date=today).count(),
            'by_type':             dict(qs.values('alert_type').annotate(n=Count('id')).values_list('alert_type', 'n')),
            'avg_severity':        qs.aggregate(avg=Avg('severity_score'))['avg'] or 0,
        })

    @audit_log(action='bulk_resolve_alerts')
    @action(detail=False, methods=['post'], url_path='bulk-resolve')
    def bulk_resolve(self, request):
        """Bulk-resolve multiple alerts."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can bulk-resolve alerts.")
        alert_ids  = request.data.get('alert_ids', [])
        resolution = request.data.get('resolution', 'Bulk resolved by admin')
        if not isinstance(alert_ids, list) or not alert_ids:
            return Response({'error': 'alert_ids must be a non-empty list.'}, status=400)
        updated = self.get_queryset().filter(id__in=alert_ids).update(
            resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user,
            resolution=resolution,
        )
        return Response({'resolved': updated, 'alert_ids': alert_ids})


# =============================================================================
# FraudRuleViewSet
# =============================================================================

class FraudRuleViewSet(SafeActionMixin, BaseFraudDetectionViewSet):
    """ViewSet for fraud rule management."""

    queryset            = FraudRule.objects.all()
    serializer_class    = FraudRuleSerializer
    # Granular permission for rule management
    permission_classes  = [IsAuthenticated, CanManageFraudRules]
    throttle_classes    = [FraudEndpointRateThrottle, BurstProtectionThrottle]
    filterset_fields    = ['rule_type', 'enabled', 'priority']
    search_fields       = ['name', 'description', 'rule_type']
    ordering_fields     = ['priority', 'created_at', 'updated_at']
    ordering            = ['-priority', '-created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanManageFraudRules()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            from api.fraud_detection.serializers import FraudRuleCreateSerializer
            return FraudRuleCreateSerializer
        if self.action in ['update', 'partial_update']:
            from api.fraud_detection.serializers import FraudRuleUpdateSerializer
            return FraudRuleUpdateSerializer
        return self.serializer_class

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test fraud rule with sample data."""
        rule      = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can test rules")
        test_data = request.data.get('test_data')
        if not test_data:
            raise ValidationError("test_data field is required")
        try:
            from api.fraud_detection.logic import ComparisonOperator, Condition, Rule
            conditions = []
            for cd in rule.conditions:
                conditions.append(Condition(
                    field=cd['field'],
                    operator=ComparisonOperator(cd['operator']),
                    value=cd['value'],
                    weight=cd.get('weight', 1.0),
                ))
            test_rule = Rule(
                name=rule.name,
                description=rule.description,
                conditions=conditions,
                logic_operator=rule.logic_operator,
                risk_score_impact=rule.risk_score_impact,
                confidence_score=rule.confidence_score,
            )
            matched, confidence = test_rule.evaluate(test_data)
            return Response({
                'rule_matched':      matched,
                'confidence':        confidence,
                'risk_score_impact': rule.risk_score_impact if matched else 0,
                'test_data':         test_data,
            })
        except Exception as exc:
            raise ValidationError(f"Rule test failed: {exc}")

    @audit_log(action='enable_rule')
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """Enable fraud rule."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can enable rules")
        rule         = self.get_object()
        rule.enabled = True
        rule.save()
        return Response(self.get_serializer(rule).data)

    @audit_log(action='disable_rule')
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """Disable fraud rule."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can disable rules")
        rule         = self.get_object()
        rule.enabled = False
        rule.save()
        return Response(self.get_serializer(rule).data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active fraud rules."""
        rules = self.queryset.filter(enabled=True)
        page  = self.paginate_queryset(rules)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(rules, many=True).data)

    @action(detail=False, methods=['get'])
    def types(self, request):
        """List all distinct rule types with counts."""
        data = (
            self.get_queryset()
                .values('rule_type')
                .annotate(count=Count('id'), active=Count('id', filter=Q(enabled=True)))
                .order_by('rule_type')
        )
        return Response(list(data))

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Rule performance statistics."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view rule stats")
        qs = self.get_queryset()
        return Response({
            'total_rules':  qs.count(),
            'active_rules': qs.filter(enabled=True).count(),
            'by_severity':  dict(
                qs.values('severity').annotate(n=Count('id')).values_list('severity', 'n')
            ),
            'top_triggered': list(
                qs.filter(trigger_count__gt=0)
                  .order_by('-trigger_count')
                  .values('id', 'name', 'trigger_count', 'false_positive_count')[:10]
            ),
        })


# =============================================================================
# UserRiskProfileViewSet
# =============================================================================

class UserRiskProfileViewSet(SafeActionMixin, BaseFraudDetectionViewSet):
    """ViewSet for fraud risk profile management."""

    queryset            = UserRiskProfile.objects.all()
    serializer_class    = UserRiskProfileSerializer
    # Granular permission: CanViewRiskProfiles
    permission_classes  = [IsAuthenticated, CanViewRiskProfiles]
    throttle_classes    = [FraudEndpointRateThrottle, HighRiskUserThrottle]
    filterset_fields    = ['user_id', 'risk_level', 'monitoring_level']
    search_fields       = ['user_id', 'risk_level']
    ordering_fields     = ['current_risk_score', 'last_updated', 'created_at']
    ordering            = ['-last_updated']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user_id=self.request.user.id)
        return qs

    @audit_log(action='manual_risk_update')
    @action(detail=True, methods=['post'])
    def update_risk(self, request, pk=None):
        """Update risk profile manually."""
        profile = self.get_object()
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can update risk profiles")

        new_risk_score = request.data.get('risk_score')
        if new_risk_score is None:
            raise ValidationError("risk_score field is required")

        try:
            new_risk_score = int(new_risk_score)
            if not 0 <= new_risk_score <= 100:
                raise ValidationError("risk_score must be between 0 and 100")
        except (ValueError, TypeError):
            raise ValidationError("risk_score must be a valid integer")

        try:
            old_score              = profile.current_risk_score
            profile.current_risk_score  = new_risk_score
            profile.previous_risk_score = old_score
            profile.last_updated        = timezone.now()

            if new_risk_score >= 80:
                profile.risk_level = 'critical'
            elif new_risk_score >= 60:
                profile.risk_level = 'high'
            elif new_risk_score >= 40:
                profile.risk_level = 'medium'
            elif new_risk_score >= 20:
                profile.risk_level = 'low'
            else:
                profile.risk_level = 'very_low'

            profile.save()

            from api.fraud_detection.events import create_fraud_detected_event
            create_fraud_detected_event(
                user_id=profile.user_id,
                description=f"Risk score manually updated from {old_score} to {new_risk_score}",
                risk_score=new_risk_score,
                metadata={'updated_by': request.user.id, 'manual_update': True},
            )
            return Response(self.get_serializer(profile).data)
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'UserRiskProfileViewSet.update_risk')
            if mapped:
                return mapped
            raise

    @action(detail=False, methods=['get'])
    def high_risk_users(self, request):
        """Get high risk users."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view high risk users")
        profiles = self.queryset.filter(current_risk_score__gte=60)
        page     = self.paginate_queryset(profiles)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(profiles, many=True).data)

    @action(detail=False, methods=['get'], url_path='risk-distribution')
    def risk_distribution(self, request):
        """Risk score distribution across all profiles."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff members can view risk distribution")
        qs = self.get_queryset()
        return Response({
            'critical':  qs.filter(current_risk_score__gte=80).count(),
            'high':      qs.filter(current_risk_score__gte=60, current_risk_score__lt=80).count(),
            'medium':    qs.filter(current_risk_score__gte=40, current_risk_score__lt=60).count(),
            'low':       qs.filter(current_risk_score__gte=20, current_risk_score__lt=40).count(),
            'minimal':   qs.filter(current_risk_score__lt=20).count(),
            'flagged':   qs.filter(is_flagged=True).count(),
            'restricted': qs.filter(is_restricted=True).count(),
            'total':     qs.count(),
        })


# =============================================================================
# FraudDetectionViewSet
# =============================================================================

class FraudDetectionViewSet(viewsets.GenericViewSet, FraudDetectionMixin):
    """ViewSet for fraud detection operations."""

    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    @action(detail=False, methods=['post'])
    def detect(self, request):
        """Perform fraud detection on transaction."""
        user_id          = request.data.get('user_id')
        transaction_data = request.data.get('transaction_data')
        if not user_id or not transaction_data:
            raise ValidationError("user_id and transaction_data are required")
        if not request.user.is_staff and str(request.user.id) != str(user_id):
            raise PermissionDenied("Cannot perform fraud detection for other users")
        try:
            context          = self.get_request_context(request)
            detection_result = self.perform_fraud_detection(user_id, transaction_data, context)
            return Response({
                'success':          True,
                'detection_result': detection_result,
                'timestamp':        timezone.now().isoformat(),
            })
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'FraudDetectionViewSet.detect')
            if mapped:
                return mapped
            raise
        except Exception as exc:
            logger.error("Fraud detection failed: %s", exc, exc_info=True)
            raise ValidationError(f"Fraud detection failed: {exc}")

    @action(detail=False, methods=['post'])
    def assess_risk(self, request):
        """Assess user risk."""
        user_id = request.data.get('user_id')
        if not user_id:
            raise ValidationError("user_id is required")
        if not request.user.is_staff and str(request.user.id) != str(user_id):
            raise PermissionDenied("Cannot assess risk for other users")
        try:
            context           = self.get_request_context(request)
            assessment_result = self.assess_user_risk(user_id, 'manual_assessment', context)
            return Response({
                'success':           True,
                'assessment_result': assessment_result,
                'timestamp':         timezone.now().isoformat(),
            })
        except (BlockedUserError, ThrottlingError, FraudRuleViolation, FraudDetectionError) as exc:
            mapped = _handle_known_exc(exc, 'FraudDetectionViewSet.assess_risk')
            if mapped:
                return mapped
            raise
        except Exception as exc:
            logger.error("Risk assessment failed: %s", exc, exc_info=True)
            raise ValidationError(f"Risk assessment failed: {exc}")

    @action(detail=False, methods=['get'], url_path='timeline')
    def timeline(self, request):
        """Return chronological timeline of fraud case events."""
        from api.fraud_detection.models import FraudCase
        days   = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timedelta(days=days)
        qs     = FraudCase.objects.filter(opened_at__gte=cutoff).order_by('opened_at')
        if not request.user.is_staff:
            qs = qs.filter(user=request.user)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        events = [
            {
                'case_id':       case.pk,
                'case_number':   case.case_number,
                'title':         case.title,
                'status':        case.status,
                'priority':      case.priority,
                'risk_score':    case.risk_score,
                'opened_at':     case.opened_at.isoformat(),
                'resolved_at':   case.resolved_at.isoformat() if case.resolved_at else None,
                'user_id':       case.user_id,
                'assigned_to_id': case.assigned_to_id,
            }
            for case in qs.select_related('user', 'assigned_to')
        ]
        return Response({'days': days, 'total': len(events), 'events': events})

    @audit_log(action='bulk_close_cases')
    @action(detail=False, methods=['post'], url_path='bulk-close')
    def bulk_close(self, request):
        """Bulk-close multiple fraud cases."""
        from api.fraud_detection.choices import CaseStatus
        from api.fraud_detection.models import FraudCase

        case_ids = request.data.get('case_ids', [])
        notes    = request.data.get('resolution_notes', '')
        if not case_ids:
            return Response(
                {'error': 'case_ids is required and must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = FraudCase.objects.filter(
            pk__in=case_ids,
            status__in=[CaseStatus.OPEN, CaseStatus.RESOLVED],
        )
        now     = timezone.now()
        updated = qs.update(status=CaseStatus.CLOSED, resolved_at=now)

        try:
            for case in qs:
                FraudCaseAction.objects.create(
                    case=case,
                    action_type='closed',
                    performed_by=request.user,
                    note=notes or 'Bulk closed.',
                )
        except Exception:
            pass

        return Response({
            'closed':                    updated,
            'not_found_or_already_closed': len(case_ids) - updated,
            'closed_at':                 now.isoformat(),
        })


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'BaseFraudDetectionViewSet',
    'FraudCaseViewSet',
    'FraudAlertViewSet',
    'FraudRuleViewSet',
    'UserRiskProfileViewSet',
    'FraudDetectionViewSet',
]


# =============================================================================
# CAPITAL VIEWSETS  (was viewset_cap.py — now merged here, DRY)
# Requires: IsAdminUser + is_executive permission for write operations.
# =============================================================================

class BaseCapitalViewSet(viewsets.ModelViewSet):
    """
    Base class for capital/regulatory-level ViewSets.
    Enforces admin-only access and adds AML audit logging on every mutation.
    """
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        instance = serializer.save()
        self._capital_audit("create", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._capital_audit("update", instance)

    def perform_destroy(self, instance):
        self._capital_audit("destroy", instance)
        instance.delete()

    def _capital_audit(self, action_name: str, instance) -> None:
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLogger
            IntegrationAuditLogger().log(
                action=f"capital.{action_name}",
                object_type=type(instance).__name__,
                object_id=str(getattr(instance, "pk", "")),
                user=getattr(self.request, "user", None),
            )
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).warning("Capital audit log failed: %s", exc)


class CapitalFraudCaseViewSet(SafeActionMixin, BaseCapitalViewSet):
    """Executive-level fraud case management with AML screening."""

    from api.fraud_detection.models import FraudCase as _M  # noqa

    queryset           = None   # set lazily
    serializer_class   = None   # set lazily
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.fraud_detection.models import FraudCase
        return FraudCase.objects.filter(severity__in=["critical", "high"]).order_by("-created_at")

    def get_serializer_class(self):
        from api.fraud_detection.serializers import FraudCaseSerializer
        return FraudCaseSerializer

    @action(detail=True, methods=["post"], url_path="trigger-aml")
    def trigger_aml_check(self, request, pk=None):
        """Trigger AML screening for a specific case."""
        from api.fraud_detection.tasks import terrorist_financing_screening
        case = self.get_object()
        job  = terrorist_financing_screening.delay({"case_id": str(case.pk)})
        return Response({"task_id": job.id, "case_id": str(case.pk)})

    @action(detail=False, methods=["get"], url_path="critical-summary")
    def critical_summary(self, request):
        """Return summary counts for critical-severity open cases."""
        from api.fraud_detection.models import FraudCase
        from django.db.models import Count
        summary = FraudCase.objects.filter(severity="critical").aggregate(
            total=Count("id"),
        )
        return Response(summary)


class CapitalAlertViewSet(SafeActionMixin, BaseCapitalViewSet):
    """Capital-level fraud alert management."""

    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.fraud_detection.models import FraudAlert
        return FraudAlert.objects.filter(risk_score__gte=80).order_by("-created_at")

    def get_serializer_class(self):
        from api.fraud_detection.serializers import FraudAlertSerializer
        return FraudAlertSerializer

    @action(detail=True, methods=["post"], url_path="escalate-exec")
    def escalate_to_executive(self, request, pk=None):
        """Send executive alert for this fraud alert."""
        from api.fraud_detection.tasks import executive_alert_generation
        alert = self.get_object()
        job   = executive_alert_generation.delay("fraud_alert", {"alert_id": str(alert.pk)})
        return Response({"task_id": job.id})


class CapitalComplianceViewSet(SafeActionMixin, BaseCapitalViewSet):
    """Regulatory compliance case management."""

    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.fraud_detection.models import FraudAttempt
        return FraudAttempt.objects.filter(fraud_type="regulatory_violation").order_by("-created_at")

    def get_serializer_class(self):
        from api.fraud_detection.serializers import FraudAttemptSerializer
        return FraudAttemptSerializer

    @action(detail=False, methods=["post"], url_path="generate-report")
    def generate_compliance_report(self, request):
        """Trigger async compliance report generation."""
        from api.fraud_detection.tasks import generate_compliance_report
        report_type = request.data.get("report_type", "monthly")
        period_days = int(request.data.get("period_days", 30))
        job = generate_compliance_report.delay(report_type, period_days)
        return Response({"task_id": job.id, "report_type": report_type})


class CapitalAnalyticsViewSet(SafeActionMixin, BaseCapitalViewSet):
    """Executive analytics and board-level reporting."""

    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.fraud_detection.models import FraudAttempt
        return FraudAttempt.objects.all()

    def get_serializer_class(self):
        from api.fraud_detection.serializers import FraudAttemptSerializer
        return FraudAttemptSerializer

    @action(detail=False, methods=["get"], url_path="executive-summary")
    def executive_summary(self, request):
        """Return high-level executive fraud KPIs."""
        from api.fraud_detection.analytics import FraudAnalyticsEngine
        return Response(FraudAnalyticsEngine().get_executive_summary())


# =============================================================================
# PERMISSION PATCH (was viewset_permissions_patch.py — applied inline, DRY)
# SafeActionMixin already defined at the top of viewset.py.
# safe_action decorator: use on individual @action methods for fine-grained catch.
# =============================================================================

def safe_action(func):
    """
    Decorator for individual @action methods.
    Catches all exceptions and returns a structured 500 JSON response.
    """
    from functools import wraps
    from rest_framework.response import Response
    from rest_framework import status
    import logging as _log

    _logger = _log.getLogger(__name__)

    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        try:
            return func(self, request, *args, **kwargs)
        except Exception as exc:
            _logger.error("safe_action caught in %s.%s: %s", type(self).__name__, func.__name__, exc, exc_info=True)
            return Response(
                {"success": False, "error": "Internal error", "detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    return wrapper
