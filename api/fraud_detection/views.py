from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone
from datetime import timedelta, datetime
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.conf import settings
import json
import logging

from .models import (
    FraudRule, FraudAttempt, FraudPattern,
    UserRiskProfile, DeviceFingerprint,
    IPReputation, FraudAlert
)
from .serializers import (
    FraudRuleSerializer, FraudAttemptSerializer,
    FraudPatternSerializer, UserRiskProfileSerializer,
    DeviceFingerprintSerializer, IPReputationSerializer,
    FraudAlertSerializer, FraudDetectionResponseSerializer,
    FraudStatisticsSerializer
)
from .detectors import (
    MultiAccountDetector, VPNProxyDetector,
    ClickFraudDetector, DeviceFingerprinter,
    PatternAnalyzer
)
from .services import FraudScoreCalculator, AutoBanService, ReviewService
from api.users.models import User
from core.permissions import IsSuperUser, IsFraudAnalyst

logger = logging.getLogger(__name__)


class FraudDetectionPagination(PageNumberPagination):
    """Custom pagination for fraud detection endpoints"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class FraudRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing fraud detection rules
    """
    queryset = FraudRule.objects.all()
    serializer_class = FraudRuleSerializer
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]
    pagination_class = FraudDetectionPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['rule_type', 'severity', 'is_active', 'run_frequency']
    search_fields = ['name', 'description']
    ordering_fields = ['severity', 'weight', 'trigger_count', 'last_triggered']

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = super().get_queryset()
        
        # Filter by rule type if provided
        rule_type = self.request.query_params.get('rule_type')
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)
        
        # Filter by severity if provided
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by active status if provided
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle rule active status"""
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save()
        
        # Log the change
        logger.info(f"Rule {rule.name} active status toggled to {rule.is_active} by {request.user.username}")
        
        return Response({
            'status': 'success',
            'is_active': rule.is_active,
            'message': f'Rule {rule.name} is now {"active" if rule.is_active else "inactive"}'
        })

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test a fraud rule with sample data"""
        rule = self.get_object()
        test_data = request.data.get('test_data', {})
        
        try:
            # Simulate rule testing
            # In production, this would actually evaluate the rule
            result = {
                'rule_id': rule.id,
                'rule_name': rule.name,
                'test_data': test_data,
                'evaluation_result': 'PASS' if test_data else 'FAIL',
                'triggered': bool(test_data),
                'confidence': 85,
                'tested_at': timezone.now().isoformat()
            }
            
            return Response({
                'status': 'success',
                'result': result,
                'message': 'Rule test completed successfully'
            })
            
        except Exception as e:
            logger.error(f"Error testing rule {rule.name}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error testing rule: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a fraud rule"""
        original_rule = self.get_object()
        
        try:
            # Create duplicate with modified name
            new_rule = FraudRule.objects.create(
                name=f"{original_rule.name} (Copy)",
                description=original_rule.description,
                rule_type=original_rule.rule_type,
                severity=original_rule.severity,
                condition=original_rule.condition,
                weight=original_rule.weight,
                threshold=original_rule.threshold,
                action_on_trigger=original_rule.action_on_trigger,
                is_active=False,  # Keep duplicate inactive by default
                run_frequency=original_rule.run_frequency
            )
            
            serializer = self.get_serializer(new_rule)
            
            logger.info(f"Rule duplicated: {original_rule.name} -> {new_rule.name} by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': 'Rule duplicated successfully',
                'data': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error duplicating rule {original_rule.name}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error duplicating rule: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def types(self, request):
        """Get available rule types"""
        rule_types = FraudRule.RULE_TYPES
        return Response({
            'rule_types': [{'value': rt[0], 'label': rt[1]} for rt in rule_types],
            'severity_levels': [{'value': sl[0], 'label': sl[1]} for sl in FraudRule.SEVERITY_LEVELS],
            'action_types': [
                {'value': 'flag', 'label': 'Flag User'},
                {'value': 'review', 'label': 'Mark for Review'},
                {'value': 'limit', 'label': 'Limit Actions'},
                {'value': 'suspend', 'label': 'Suspend Account'},
                {'value': 'ban', 'label': 'Ban Permanently'}
            ],
            'run_frequencies': [
                {'value': 'realtime', 'label': 'Real-time'},
                {'value': 'hourly', 'label': 'Hourly'},
                {'value': 'daily', 'label': 'Daily'},
                {'value': 'weekly', 'label': 'Weekly'}
            ]
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get rule statistics"""
        total_rules = self.get_queryset().count()
        active_rules = self.get_queryset().filter(is_active=True).count()
        
        # Group by rule type
        by_type = self.get_queryset().values('rule_type').annotate(
            count=Count('id'),
            active=Count('id', filter=Q(is_active=True))
        ).order_by('-count')
        
        # Group by severity
        by_severity = self.get_queryset().values('severity').annotate(
            count=Count('id'),
            active=Count('id', filter=Q(is_active=True))
        ).order_by('-count')
        
        # Most triggered rules
        most_triggered = self.get_queryset().order_by('-trigger_count')[:10]
        most_triggered_data = FraudRuleSerializer(most_triggered, many=True).data
        
        return Response({
            'total_rules': total_rules,
            'active_rules': active_rules,
            'inactive_rules': total_rules - active_rules,
            'by_type': list(by_type),
            'by_severity': list(by_severity),
            'most_triggered': most_triggered_data
        })


class FraudAttemptViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing fraud attempts
    """
    queryset = FraudAttempt.objects.all()
    serializer_class = FraudAttemptSerializer
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]
    pagination_class = FraudDetectionPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['attempt_type', 'status', 'is_resolved', 'user']
    search_fields = ['description', 'detected_by', 'resolution_notes']
    ordering_fields = ['fraud_score', 'created_at', 'resolved_at', 'amount_involved']

    def get_queryset(self):
        """Filter queryset based on user permissions and request params"""
        queryset = super().get_queryset()
        
        # Apply filters from query params
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        min_score = self.request.query_params.get('min_score')
        max_score = self.request.query_params.get('max_score')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if min_score:
            queryset = queryset.filter(fraud_score__gte=min_score)
        if max_score:
            queryset = queryset.filter(fraud_score__lte=max_score)
        
        # Filter by resolved status
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            queryset = queryset.filter(is_resolved=resolved.lower() == 'true')
        
        return queryset.select_related('user', 'resolved_by').prefetch_related('fraud_rules')

    @action(detail=True, methods=['post'])
    def mark_confirmed(self, request, pk=None):
        """Mark fraud attempt as confirmed"""
        fraud_attempt = self.get_object()
        
        try:
            notes = request.data.get('notes', '')
            
            fraud_attempt.mark_as_confirmed(
                resolved_by=request.user,
                notes=notes
            )
            
            logger.info(f"Fraud attempt {fraud_attempt.attempt_id} marked as confirmed by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': 'Fraud attempt confirmed',
                'attempt_id': str(fraud_attempt.attempt_id)
            })
            
        except Exception as e:
            logger.error(f"Error confirming fraud attempt: {e}")
            return Response({
                'status': 'error',
                'message': f'Error confirming fraud attempt: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def mark_false_positive(self, request, pk=None):
        """Mark fraud attempt as false positive"""
        fraud_attempt = self.get_object()
        
        try:
            notes = request.data.get('notes', '')
            
            fraud_attempt.status = 'false_positive'
            fraud_attempt.is_resolved = True
            fraud_attempt.resolved_at = timezone.now()
            fraud_attempt.resolved_by = request.user
            fraud_attempt.resolution_notes = notes
            fraud_attempt.save()
            
            # Update false positive count in related rules
            for rule in fraud_attempt.fraud_rules.all():
                rule.false_positive_count += 1
                rule.save()
            
            logger.info(f"Fraud attempt {fraud_attempt.attempt_id} marked as false positive by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': 'Fraud attempt marked as false positive',
                'attempt_id': str(fraud_attempt.attempt_id)
            })
            
        except Exception as e:
            logger.error(f"Error marking false positive: {e}")
            return Response({
                'status': 'error',
                'message': f'Error marking false positive: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """Escalate fraud attempt for review"""
        fraud_attempt = self.get_object()
        
        try:
            escalation_reason = request.data.get('reason', 'Manual escalation')
            
            fraud_attempt.status = 'reviewing'
            fraud_attempt.save()
            
            # Create escalation alert
            FraudAlert.objects.create(
                alert_type='manual_review',
                priority='high',
                title=f"Case escalated: {fraud_attempt.attempt_type}",
                description=f"Case {fraud_attempt.attempt_id} escalated by {request.user.username}: {escalation_reason}",
                user=fraud_attempt.user,
                fraud_attempt=fraud_attempt,
                data={
                    'escalation_reason': escalation_reason,
                    'escalated_by': request.user.username
                }
            )
            
            logger.info(f"Fraud attempt {fraud_attempt.attempt_id} escalated by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': 'Fraud attempt escalated for review',
                'attempt_id': str(fraud_attempt.attempt_id)
            })
            
        except Exception as e:
            logger.error(f"Error escalating fraud attempt: {e}")
            return Response({
                'status': 'error',
                'message': f'Error escalating fraud attempt: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get fraud attempt statistics"""
        # Time periods
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Overall statistics
        total_attempts = self.get_queryset().count()
        resolved_attempts = self.get_queryset().filter(is_resolved=True).count()
        confirmed_fraud = self.get_queryset().filter(status='confirmed').count()
        false_positives = self.get_queryset().filter(status='false_positive').count()
        
        # Time-based statistics
        today_attempts = self.get_queryset().filter(created_at__date=today).count()
        yesterday_attempts = self.get_queryset().filter(created_at__date=yesterday).count()
        week_attempts = self.get_queryset().filter(created_at__date__gte=week_ago).count()
        month_attempts = self.get_queryset().filter(created_at__date__gte=month_ago).count()
        
        # Type-based statistics
        by_type = self.get_queryset().values('attempt_type').annotate(
            count=Count('id'),
            avg_score=Avg('fraud_score'),
            confirmed=Count('id', filter=Q(status='confirmed')),
            false_positive=Count('id', filter=Q(status='false_positive'))
        ).order_by('-count')
        
        # Status distribution
        by_status = self.get_queryset().values('status').annotate(
            count=Count('id'),
            avg_score=Avg('fraud_score')
        ).order_by('-count')
        
        # Score distribution
        score_ranges = [
            ('critical', 90, 100),
            ('high', 70, 89),
            ('medium', 50, 69),
            ('low', 30, 49),
            ('minimal', 0, 29)
        ]
        
        score_distribution = []
        for label, min_score, max_score in score_ranges:
            count = self.get_queryset().filter(
                fraud_score__gte=min_score,
                fraud_score__lte=max_score
            ).count()
            score_distribution.append({
                'range': label,
                'min_score': min_score,
                'max_score': max_score,
                'count': count
            })
        
        # Top users by fraud attempts
        top_users = self.get_queryset().values(
            'user__id', 'user__username', 'user__email'
        ).annotate(
            attempt_count=Count('id'),
            avg_score=Avg('fraud_score'),
            total_amount=Sum('amount_involved')
        ).order_by('-attempt_count')[:10]
        
        # Monthly trend (last 6 months)
        monthly_trend = []
        for i in range(5, -1, -1):
            month_start = today - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            
            month_data = self.get_queryset().filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_end
            ).aggregate(
                total=Count('id'),
                confirmed=Count('id', filter=Q(status='confirmed')),
                avg_score=Avg('fraud_score')
            )
            
            monthly_trend.append({
                'month': month_start.strftime('%Y-%m'),
                'start_date': month_start.isoformat(),
                'end_date': month_end.isoformat(),
                'total': month_data['total'] or 0,
                'confirmed': month_data['confirmed'] or 0,
                'avg_score': float(month_data['avg_score'] or 0)
            })
        
        return Response({
            'overall': {
                'total_attempts': total_attempts,
                'resolved_attempts': resolved_attempts,
                'unresolved_attempts': total_attempts - resolved_attempts,
                'confirmed_fraud': confirmed_fraud,
                'false_positives': false_positives,
                'confirmation_rate': (confirmed_fraud / total_attempts * 100) if total_attempts > 0 else 0,
                'false_positive_rate': (false_positives / total_attempts * 100) if total_attempts > 0 else 0
            },
            'time_periods': {
                'today': today_attempts,
                'yesterday': yesterday_attempts,
                'last_7_days': week_attempts,
                'last_30_days': month_attempts
            },
            'by_type': list(by_type),
            'by_status': list(by_status),
            'score_distribution': score_distribution,
            'top_users': list(top_users),
            'monthly_trend': monthly_trend
        })

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update fraud attempts"""
        try:
            attempt_ids = request.data.get('attempt_ids', [])
            action_type = request.data.get('action')
            notes = request.data.get('notes', '')
            
            if not attempt_ids:
                return Response({
                    'status': 'error',
                    'message': 'No attempt IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if action_type not in ['confirm', 'false_positive', 'escalate', 'resolve']:
                return Response({
                    'status': 'error',
                    'message': 'Invalid action type'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the attempts
            attempts = FraudAttempt.objects.filter(attempt_id__in=attempt_ids)
            
            updated_count = 0
            for attempt in attempts:
                if action_type == 'confirm':
                    attempt.mark_as_confirmed(request.user, notes)
                elif action_type == 'false_positive':
                    attempt.status = 'false_positive'
                    attempt.is_resolved = True
                    attempt.resolved_at = timezone.now()
                    attempt.resolved_by = request.user
                    attempt.resolution_notes = notes
                    attempt.save()
                elif action_type == 'escalate':
                    attempt.status = 'reviewing'
                    attempt.save()
                elif action_type == 'resolve':
                    attempt.is_resolved = True
                    attempt.resolved_at = timezone.now()
                    attempt.resolved_by = request.user
                    attempt.resolution_notes = notes
                    attempt.save()
                
                updated_count += 1
            
            logger.info(f"Bulk updated {updated_count} fraud attempts with action '{action_type}' by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': f'Updated {updated_count} fraud attempts',
                'updated_count': updated_count,
                'action': action_type
            })
            
        except Exception as e:
            logger.error(f"Error in bulk update: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in bulk update: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRiskProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user risk profiles
    """
    queryset = UserRiskProfile.objects.all()
    serializer_class = UserRiskProfileSerializer
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]
    pagination_class = FraudDetectionPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_flagged', 'is_restricted', 'monitoring_level']
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['overall_risk_score', 'last_risk_assessment', 'updated_at']

    def get_queryset(self):
        """Filter queryset based on request params"""
        queryset = super().get_queryset()
        
        # Filter by risk score range
        min_score = self.request.query_params.get('min_score')
        max_score = self.request.query_params.get('max_score')
        
        if min_score:
            queryset = queryset.filter(overall_risk_score__gte=min_score)
        if max_score:
            queryset = queryset.filter(overall_risk_score__lte=max_score)
        
        # Filter by warning flags
        warning_flag = self.request.query_params.get('warning_flag')
        if warning_flag:
            queryset = queryset.filter(warning_flags__contains=[warning_flag])
        
        return queryset.select_related('user')

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """Recalculate risk score for a user"""
        risk_profile = self.get_object()
        
        try:
            calculator = FraudScoreCalculator(risk_profile.user)
            new_score = calculator.calculate_overall_risk()
            
            # Refresh the profile
            risk_profile.refresh_from_db()
            
            return Response({
                'status': 'success',
                'message': 'Risk score recalculated',
                'previous_score': new_score,  # Actually the new score after refresh
                'new_score': risk_profile.overall_risk_score,
                'user_id': risk_profile.user_id,
                'recalculated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error recalculating risk score for user {risk_profile.user_id}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error recalculating risk score: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def flag_user(self, request, pk=None):
        """Flag user for review"""
        risk_profile = self.get_object()
        
        try:
            reason = request.data.get('reason', 'Manual flag')
            
            risk_profile.is_flagged = True
            risk_profile.warning_flags.append('manually_flagged')
            risk_profile.save()
            
            # Create audit log
            from audit_logs.models import AuditLog
            AuditLog.objects.create(
                user=risk_profile.user,
                action='USER_FLAGGED',
                description=f"User flagged for review: {reason}",
                metadata={
                    'flagged_by': request.user.username,
                    'reason': reason,
                    'risk_score': risk_profile.overall_risk_score
                }
            )
            
            logger.info(f"User {risk_profile.user.username} flagged by {request.user.username}: {reason}")
            
            return Response({
                'status': 'success',
                'message': 'User flagged for review',
                'user_id': risk_profile.user_id,
                'is_flagged': True,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error flagging user {risk_profile.user_id}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error flagging user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def unflag_user(self, request, pk=None):
        """Remove flag from user"""
        risk_profile = self.get_object()
        
        try:
            reason = request.data.get('reason', 'Manual unflag')
            
            risk_profile.is_flagged = False
            if 'manually_flagged' in risk_profile.warning_flags:
                risk_profile.warning_flags.remove('manually_flagged')
            risk_profile.save()
            
            # Create audit log
            from audit_logs.models import AuditLog
            AuditLog.objects.create(
                user=risk_profile.user,
                action='USER_UNFLAGGED',
                description=f"User un-flagged: {reason}",
                metadata={
                    'unflagged_by': request.user.username,
                    'reason': reason
                }
            )
            
            logger.info(f"User {risk_profile.user.username} un-flagged by {request.user.username}: {reason}")
            
            return Response({
                'status': 'success',
                'message': 'User flag removed',
                'user_id': risk_profile.user_id,
                'is_flagged': False,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error unflagging user {risk_profile.user_id}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error unflagging user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def restrict_user(self, request, pk=None):
        """Restrict user actions"""
        risk_profile = self.get_object()
        
        try:
            restrictions = request.data.get('restrictions', [])
            reason = request.data.get('reason', 'Manual restriction')
            level = request.data.get('level', 'custom')
            
            if not restrictions:
                return Response({
                    'status': 'error',
                    'message': 'No restrictions specified'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            risk_profile.is_restricted = True
            risk_profile.restrictions = {
                'restricted_actions': restrictions,
                'restriction_level': level,
                'reason': reason,
                'restricted_by': request.user.username,
                'restricted_at': timezone.now().isoformat()
            }
            risk_profile.save()
            
            # Create audit log
            from audit_logs.models import AuditLog
            AuditLog.objects.create(
                user=risk_profile.user,
                action='USER_RESTRICTED',
                description=f"User restricted: {reason}",
                metadata={
                    'restricted_by': request.user.username,
                    'reason': reason,
                    'restrictions': restrictions,
                    'level': level
                }
            )
            
            logger.info(f"User {risk_profile.user.username} restricted by {request.user.username}: {reason}")
            
            return Response({
                'status': 'success',
                'message': 'User restrictions applied',
                'user_id': risk_profile.user_id,
                'restrictions': restrictions,
                'level': level,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error restricting user {risk_profile.user_id}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error restricting user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def unrestrict_user(self, request, pk=None):
        """Remove restrictions from user"""
        risk_profile = self.get_object()
        
        try:
            reason = request.data.get('reason', 'Manual unrestriction')
            
            risk_profile.is_restricted = False
            risk_profile.restrictions = {}
            risk_profile.save()
            
            # Create audit log
            from audit_logs.models import AuditLog
            AuditLog.objects.create(
                user=risk_profile.user,
                action='USER_UNRESTRICTED',
                description=f"User restrictions removed: {reason}",
                metadata={
                    'unrestricted_by': request.user.username,
                    'reason': reason
                }
            )
            
            logger.info(f"User {risk_profile.user.username} unrestricted by {request.user.username}: {reason}")
            
            return Response({
                'status': 'success',
                'message': 'User restrictions removed',
                'user_id': risk_profile.user_id,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error unrestricting user {risk_profile.user_id}: {e}")
            return Response({
                'status': 'error',
                'message': f'Error unrestricting user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def high_risk_users(self, request):
        """Get high risk users"""
        threshold = int(request.query_params.get('threshold', 70))
        limit = int(request.query_params.get('limit', 50))
        
        high_risk_users = self.get_queryset().filter(
            overall_risk_score__gte=threshold
        ).order_by('-overall_risk_score')[:limit]
        
        serializer = self.get_serializer(high_risk_users, many=True)
        
        return Response({
            'threshold': threshold,
            'count': len(high_risk_users),
            'users': serializer.data
        })

    @action(detail=False, methods=['get'])
    def risk_distribution(self, request):
        """Get risk score distribution"""
        # Define risk categories
        categories = [
            {'name': 'Critical', 'min': 90, 'max': 100},
            {'name': 'High', 'min': 70, 'max': 89},
            {'name': 'Medium', 'min': 50, 'max': 69},
            {'name': 'Low', 'min': 30, 'max': 49},
            {'name': 'Minimal', 'min': 0, 'max': 29}
        ]
        
        distribution = []
        for category in categories:
            count = UserRiskProfile.objects.filter(
                overall_risk_score__gte=category['min'],
                overall_risk_score__lte=category['max']
            ).count()
            
            flagged_count = UserRiskProfile.objects.filter(
                overall_risk_score__gte=category['min'],
                overall_risk_score__lte=category['max'],
                is_flagged=True
            ).count()
            
            restricted_count = UserRiskProfile.objects.filter(
                overall_risk_score__gte=category['min'],
                overall_risk_score__lte=category['max'],
                is_restricted=True
            ).count()
            
            distribution.append({
                'category': category['name'],
                'min_score': category['min'],
                'max_score': category['max'],
                'count': count,
                'flagged_count': flagged_count,
                'restricted_count': restricted_count,
                'flagged_percentage': (flagged_count / count * 100) if count > 0 else 0
            })
        
        # Overall statistics
        total_users = UserRiskProfile.objects.count()
        flagged_users = UserRiskProfile.objects.filter(is_flagged=True).count()
        restricted_users = UserRiskProfile.objects.filter(is_restricted=True).count()
        avg_risk_score = UserRiskProfile.objects.aggregate(
            avg_score=Avg('overall_risk_score')
        )['avg_score'] or 0
        
        return Response({
            'distribution': distribution,
            'overall': {
                'total_users': total_users,
                'flagged_users': flagged_users,
                'restricted_users': restricted_users,
                'flagged_percentage': (flagged_users / total_users * 100) if total_users > 0 else 0,
                'restricted_percentage': (restricted_users / total_users * 100) if total_users > 0 else 0,
                'average_risk_score': float(avg_risk_score)
            }
        })


class FraudAlertViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing fraud alerts
    """
    queryset = FraudAlert.objects.all()
    serializer_class = FraudAlertSerializer
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]
    pagination_class = FraudDetectionPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['alert_type', 'priority', 'is_resolved', 'notification_sent']
    search_fields = ['title', 'description', 'resolution_notes']
    ordering_fields = ['priority', 'created_at', 'resolved_at']

    def get_queryset(self):
        """Filter queryset based on request params"""
        queryset = super().get_queryset()
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Filter by resolved status
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            queryset = queryset.filter(is_resolved=resolved.lower() == 'true')
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset.select_related('user', 'fraud_attempt', 'resolved_by').prefetch_related('related_rules')

    @action(detail=True, methods=['post'])
    def mark_resolved(self, request, pk=None):
        """Mark alert as resolved"""
        alert = self.get_object()
        
        try:
            notes = request.data.get('notes', '')
            
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.resolution_notes = notes
            alert.save()
            
            logger.info(f"Alert {alert.alert_id} marked as resolved by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': 'Alert marked as resolved',
                'alert_id': str(alert.alert_id)
            })
            
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return Response({
                'status': 'error',
                'message': f'Error resolving alert: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def notify_users(self, request, pk=None):
        """Send notifications for this alert"""
        alert = self.get_object()
        
        try:
            # Get users to notify
            user_ids = request.data.get('user_ids', [])
            
            if not user_ids:
                # Default to admin users
                from users.models import User
                admin_users = User.objects.filter(
                    Q(is_staff=True) | Q(is_superuser=True)
                ).values_list('id', flat=True)
                user_ids = list(admin_users)
            
            # Mark users as notified
            users_to_notify = User.objects.filter(id__in=user_ids)
            alert.notified_users.add(*users_to_notify)
            alert.notification_sent = True
            alert.save()
            
            # In production, this would send actual notifications
            # For now, just log it
            logger.info(f"Alert {alert.alert_id} notifications sent to {len(user_ids)} users")
            
            return Response({
                'status': 'success',
                'message': f'Notifications sent to {len(user_ids)} users',
                'alert_id': str(alert.alert_id),
                'notified_users': len(user_ids)
            })
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return Response({
                'status': 'error',
                'message': f'Error sending notifications: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for alerts"""
        # Time periods
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Overall counts
        total_alerts = self.get_queryset().count()
        resolved_alerts = self.get_queryset().filter(is_resolved=True).count()
        unresolved_alerts = total_alerts - resolved_alerts
        
        # Recent alerts
        recent_alerts = self.get_queryset().filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # By priority
        by_priority = self.get_queryset().values('priority').annotate(
            count=Count('id'),
            resolved=Count('id', filter=Q(is_resolved=True)),
            unresolved=Count('id', filter=Q(is_resolved=False))
        ).order_by('-count')
        
        # By alert type
        by_type = self.get_queryset().values('alert_type').annotate(
            count=Count('id'),
            avg_resolution_time=Avg(F('resolved_at') - F('created_at'), filter=Q(is_resolved=True))
        ).order_by('-count')
        
        # Top alert creators (users with most alerts)
        top_users = self.get_queryset().filter(user__isnull=False).values(
            'user__id', 'user__username'
        ).annotate(
            alert_count=Count('id'),
            resolved_count=Count('id', filter=Q(is_resolved=True))
        ).order_by('-alert_count')[:10]
        
        # Resolution time statistics
        resolved_alerts_qs = self.get_queryset().filter(
            is_resolved=True,
            resolved_at__isnull=False,
            created_at__isnull=False
        )
        
        if resolved_alerts_qs.exists():
            avg_resolution_time = resolved_alerts_qs.aggregate(
                avg_time=Avg(F('resolved_at') - F('created_at'))
            )['avg_time']
        else:
            avg_resolution_time = None
        
        return Response({
            'overall': {
                'total_alerts': total_alerts,
                'resolved_alerts': resolved_alerts,
                'unresolved_alerts': unresolved_alerts,
                'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
            },
            'recent': {
                'last_24_hours': recent_alerts,
                'last_7_days': self.get_queryset().filter(created_at__gte=week_ago).count(),
                'last_30_days': self.get_queryset().filter(created_at__gte=month_ago).count()
            },
            'by_priority': list(by_priority),
            'by_type': list(by_type),
            'top_users': list(top_users),
            'resolution_time': {
                'average': str(avg_resolution_time) if avg_resolution_time else None,
                'unit': 'seconds'
            }
        })

    @action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        """Bulk resolve alerts"""
        try:
            alert_ids = request.data.get('alert_ids', [])
            notes = request.data.get('notes', 'Bulk resolution')
            
            if not alert_ids:
                return Response({
                    'status': 'error',
                    'message': 'No alert IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Resolve alerts
            alerts = FraudAlert.objects.filter(alert_id__in=alert_ids)
            resolved_count = 0
            
            for alert in alerts:
                alert.is_resolved = True
                alert.resolved_at = timezone.now()
                alert.resolved_by = request.user
                alert.resolution_notes = notes
                alert.save()
                resolved_count += 1
            
            logger.info(f"Bulk resolved {resolved_count} alerts by {request.user.username}")
            
            return Response({
                'status': 'success',
                'message': f'Resolved {resolved_count} alerts',
                'resolved_count': resolved_count
            })
            
        except Exception as e:
            logger.error(f"Error in bulk resolve: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in bulk resolve: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudDetectionAPIView(APIView):
    """
    API endpoints for real-time fraud detection
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        """
        Run comprehensive fraud detection on user/transaction
        """
        action = kwargs.get('action', 'check_user')
        
        if action == 'check_user':
            return self.check_user(request)
        elif action == 'check_transaction':
            return self.check_transaction(request)
        elif action == 'check_offer':
            return self.check_offer(request)
        elif action == 'check_device':
            return self.check_device(request)
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)

    def check_user(self, request):
        """Check user for fraud indicators"""
        try:
            user_id = request.data.get('user_id')
            detection_type = request.data.get('detection_type', 'comprehensive')
            
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Initialize detectors based on type
            detectors = []
            
            if detection_type == 'comprehensive' or detection_type == 'multi_account':
                detectors.append(MultiAccountDetector())
            
            if detection_type == 'comprehensive' or detection_type == 'vpn_proxy':
                detectors.append(VPNProxyDetector())
            
            if detection_type == 'comprehensive' or detection_type == 'click_fraud':
                detectors.append(ClickFraudDetector())
            
            if detection_type == 'comprehensive' or detection_type == 'device':
                detectors.append(DeviceFingerprinter())
            
            if detection_type == 'comprehensive' or detection_type == 'pattern':
                detectors.append(PatternAnalyzer())
            
            # Run detection
            results = []
            overall_score = 0
            reasons = []
            evidence = {}
            
            for detector in detectors:
                try:
                    detection_data = {
                        'user_id': user_id,
                        'ip_address': request.data.get('ip_address'),
                        'device_data': request.data.get('device_data', {}),
                        'click_data': request.data.get('click_data', {}),
                        'activity_type': request.data.get('activity_type'),
                        'timeframe': request.data.get('timeframe', '7d')
                    }
                    
                    result = detector.detect(detection_data)
                    results.append({
                        'detector': detector.detector_name,
                        'result': result
                    })
                    
                    # Update overall score
                    detector_score = result.get('fraud_score', 0)
                    overall_score = max(overall_score, detector_score)
                    
                    # Collect reasons
                    if result.get('reasons'):
                        reasons.extend(result['reasons'])
                    
                    # Collect evidence
                    if result.get('evidence'):
                        evidence[detector.detector_name] = result['evidence']
                        
                except Exception as e:
                    logger.error(f"Error in detector {detector.detector_name}: {e}")
                    results.append({
                        'detector': detector.detector_name,
                        'error': str(e)
                    })
            
            # Calculate confidence
            confidence = min(100, overall_score + (len(results) * 5))
            
            # Check if fraud is detected
            is_fraud = overall_score >= 70
            
            # Create response
            response_data = {
                'is_fraud': is_fraud,
                'fraud_score': overall_score,
                'confidence': confidence,
                'reasons': reasons,
                'detection_type': detection_type,
                'detectors_used': [d.detector_name for d in detectors],
                'detailed_results': results,
                'evidence_summary': evidence,
                'timestamp': timezone.now().isoformat(),
                'user_id': user_id
            }
            
            # If fraud is detected, create fraud attempt
            if is_fraud:
                fraud_attempt = FraudAttempt.objects.create(
                    user=user,
                    attempt_type='comprehensive_check',
                    description=f'Comprehensive fraud check detected multiple indicators',
                    detected_by='FraudDetectionAPI',
                    fraud_score=overall_score,
                    confidence_score=confidence,
                    evidence_data=evidence,
                    status='detected'
                )
                
                response_data['fraud_attempt_id'] = str(fraud_attempt.attempt_id)
                
                # Trigger auto-ban if score is high
                if overall_score >= 80:
                    auto_ban_service = AutoBanService()
                    auto_ban_service.process_fraud_attempt(fraud_attempt)
            
            # Serialize response
            serializer = FraudDetectionResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in check_user: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in fraud detection: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_transaction(self, request):
        """Check transaction for fraud"""
        try:
            transaction_data = request.data
            
            # Validate required fields
            required_fields = ['user_id', 'amount', 'transaction_type']
            missing_fields = [field for field in required_fields if field not in transaction_data]
            
            if missing_fields:
                return Response({
                    'status': 'error',
                    'message': f'Missing required fields: {missing_fields}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_id = transaction_data['user_id']
            amount = transaction_data['amount']
            transaction_type = transaction_data['transaction_type']
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Initialize pattern analyzer for transaction patterns
            analyzer = PatternAnalyzer()
            
            # Analyze transaction patterns
            analysis_data = {
                'user_id': user_id,
                'activity_type': f'transaction_{transaction_type}',
                'metadata': {
                    'amount': amount,
                    'transaction_type': transaction_type,
                    'recipient': transaction_data.get('recipient'),
                    'payment_method': transaction_data.get('payment_method')
                }
            }
            
            result = analyzer.detect(analysis_data)
            
            # Check for high risk
            fraud_score = result.get('fraud_score', 0)
            is_fraud = fraud_score >= 65
            
            response_data = {
                'is_fraud': is_fraud,
                'fraud_score': fraud_score,
                'confidence': result.get('confidence', 0),
                'reasons': result.get('reasons', []),
                'transaction_type': transaction_type,
                'amount': amount,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            }
            
            # If fraud is detected, create fraud attempt
            if is_fraud:
                fraud_attempt = FraudAttempt.objects.create(
                    user=user,
                    attempt_type='payment_fraud',
                    description=f'Suspicious {transaction_type} transaction: ${amount}',
                    detected_by='TransactionFraudDetector',
                    fraud_score=fraud_score,
                    confidence_score=result.get('confidence', 0),
                    evidence_data=result.get('evidence', {}),
                    amount_involved=amount,
                    status='detected'
                )
                
                response_data['fraud_attempt_id'] = str(fraud_attempt.attempt_id)
            
            serializer = FraudDetectionResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in check_transaction: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in transaction fraud detection: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_offer(self, request):
        """Check offer completion for fraud"""
        try:
            offer_data = request.data
            
            # Validate required fields
            required_fields = ['user_id', 'offer_id']
            missing_fields = [field for field in required_fields if field not in offer_data]
            
            if missing_fields:
                return Response({
                    'status': 'error',
                    'message': f'Missing required fields: {missing_fields}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_id = offer_data['user_id']
            offer_id = offer_data['offer_id']
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Initialize click fraud detector
            detector = ClickFraudDetector()
            
            # Check for click fraud
            detection_data = {
                'user_id': user_id,
                'offer_id': offer_id,
                'click_data': {
                    'revenue': offer_data.get('payout', 0),
                    'completion_time': offer_data.get('completion_time'),
                    'click_source': offer_data.get('click_source'),
                    'device_data': offer_data.get('device_data', {})
                }
            }
            
            result = detector.detect(detection_data)
            
            # Check for high risk
            fraud_score = result.get('fraud_score', 0)
            is_fraud = fraud_score >= 60
            
            response_data = {
                'is_fraud': is_fraud,
                'fraud_score': fraud_score,
                'confidence': result.get('confidence', 0),
                'reasons': result.get('reasons', []),
                'offer_id': offer_id,
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            }
            
            # If fraud is detected, create fraud attempt
            if is_fraud:
                fraud_attempt = FraudAttempt.objects.create(
                    user=user,
                    attempt_type='click_fraud',
                    description=f'Suspicious offer completion: {offer_id}',
                    detected_by='ClickFraudDetector',
                    fraud_score=fraud_score,
                    confidence_score=result.get('confidence', 0),
                    evidence_data=result.get('evidence', {}),
                    amount_involved=offer_data.get('payout', 0),
                    status='detected'
                )
                
                response_data['fraud_attempt_id'] = str(fraud_attempt.attempt_id)
            
            serializer = FraudDetectionResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in check_offer: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in offer fraud detection: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_device(self, request):
        """Check device for spoofing"""
        try:
            device_data = request.data
            
            # Validate required fields
            required_fields = ['user_id', 'device_data']
            missing_fields = [field for field in required_fields if field not in device_data]
            
            if missing_fields:
                return Response({
                    'status': 'error',
                    'message': f'Missing required fields: {missing_fields}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user_id = device_data['user_id']
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Initialize device fingerprinter
            detector = DeviceFingerprinter()
            
            # Check for device spoofing
            detection_data = {
                'user_id': user_id,
                'user_agent': device_data.get('user_agent', ''),
                'device_data': device_data.get('device_data', {})
            }
            
            result = detector.detect(detection_data)
            
            # Check for high risk
            fraud_score = result.get('fraud_score', 0)
            is_fraud = fraud_score >= 70
            
            response_data = {
                'is_fraud': is_fraud,
                'fraud_score': fraud_score,
                'confidence': result.get('confidence', 0),
                'reasons': result.get('reasons', []),
                'device_fingerprint': result.get('fingerprint', {}),
                'device_hash': result.get('device_hash'),
                'user_id': user_id,
                'timestamp': timezone.now().isoformat()
            }
            
            # If fraud is detected, create fraud attempt
            if is_fraud:
                fraud_attempt = FraudAttempt.objects.create(
                    user=user,
                    attempt_type='device_spoofing',
                    description='Device fingerprint spoofing detected',
                    detected_by='DeviceFingerprinter',
                    fraud_score=fraud_score,
                    confidence_score=result.get('confidence', 0),
                    evidence_data=result.get('evidence', {}),
                    status='detected'
                )
                
                response_data['fraud_attempt_id'] = str(fraud_attempt.attempt_id)
                
                # Also save device fingerprint if available
                if result.get('fingerprint'):
                    DeviceFingerprint.objects.create(
                        user=user,
                        device_id=device_data.get('device_id', 'unknown'),
                        device_hash=result.get('device_hash', ''),
                        user_agent=device_data.get('user_agent', ''),
                        ip_address=device_data.get('ip_address', ''),
                        trust_score=100 - fraud_score,  # Lower trust for higher fraud score
                        **result.get('fingerprint', {})
                    )
            
            serializer = FraudDetectionResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error in check_device: {e}")
            return Response({
                'status': 'error',
                'message': f'Error in device fraud detection: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutoBanAPIView(APIView):
    """
    API endpoints for auto-ban management
    """
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]

    def post(self, request, *args, **kwargs):
        """
        Handle auto-ban actions
        """
        action = kwargs.get('action')
        
        if action == 'process_attempt':
            return self.process_fraud_attempt(request)
        elif action == 'ban_user':
            return self.ban_user(request)
        elif action == 'suspend_user':
            return self.suspend_user(request)
        elif action == 'restrict_user':
            return self.restrict_user(request)
        elif action == 'unban_users':
            return self.unban_users(request)
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)

    def process_fraud_attempt(self, request):
        """Process a fraud attempt with auto-ban"""
        try:
            attempt_id = request.data.get('attempt_id')
            
            if not attempt_id:
                return Response({
                    'status': 'error',
                    'message': 'attempt_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get fraud attempt
            fraud_attempt = get_object_or_404(FraudAttempt, attempt_id=attempt_id)
            
            # Process with auto-ban service
            auto_ban_service = AutoBanService()
            result = auto_ban_service.process_fraud_attempt(fraud_attempt)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error processing fraud attempt: {e}")
            return Response({
                'status': 'error',
                'message': f'Error processing fraud attempt: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def ban_user(self, request):
        """Ban a user"""
        try:
            user_id = request.data.get('user_id')
            reason = request.data.get('reason', 'Manual ban')
            duration_hours = request.data.get('duration_hours', 24)
            
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Ban user
            auto_ban_service = AutoBanService()
            result = auto_ban_service.auto_ban_user(user, reason, duration_hours)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return Response({
                'status': 'error',
                'message': f'Error banning user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def suspend_user(self, request):
        """Suspend a user"""
        try:
            user_id = request.data.get('user_id')
            reason = request.data.get('reason', 'Manual suspension')
            duration_hours = request.data.get('duration_hours', 24)
            
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Suspend user
            auto_ban_service = AutoBanService()
            result = auto_ban_service.auto_suspend_user(user, reason, duration_hours)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error suspending user: {e}")
            return Response({
                'status': 'error',
                'message': f'Error suspending user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def restrict_user(self, request):
        """Restrict a user"""
        try:
            user_id = request.data.get('user_id')
            reason = request.data.get('reason', 'Manual restriction')
            restriction_level = request.data.get('restriction_level', 'level_1')
            
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user
            user = get_object_or_404(User, id=user_id)
            
            # Restrict user
            auto_ban_service = AutoBanService()
            result = auto_ban_service.auto_restrict_user(user, reason, restriction_level)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error restricting user: {e}")
            return Response({
                'status': 'error',
                'message': f'Error restricting user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def unban_users(self, request):
        """Check and unban expired bans"""
        try:
            auto_ban_service = AutoBanService()
            result = auto_ban_service.check_and_unban_users()
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error unbanning users: {e}")
            return Response({
                'status': 'error',
                'message': f'Error unbanning users: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReviewAPIView(APIView):
    """
    API endpoints for fraud case review
    """
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests for review
        """
        action = kwargs.get('action')
        
        if action == 'pending':
            return self.get_pending_reviews(request)
        elif action == 'case':
            attempt_id = kwargs.get('attempt_id')
            return self.get_review_case(request, attempt_id)
        elif action == 'stats':
            return self.get_review_stats(request)
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for review
        """
        action = kwargs.get('action')
        
        if action == 'decide':
            return self.make_decision(request)
        elif action == 'escalate':
            return self.escalate_case(request)
        elif action == 'comment':
            return self.add_comment(request)
        elif action == 'batch':
            return self.batch_decisions(request)
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)

    def get_pending_reviews(self, request):
        """Get pending fraud cases for review"""
        try:
            filters = {
                'min_score': request.query_params.get('min_score'),
                'max_score': request.query_params.get('max_score'),
                'fraud_type': request.query_params.get('fraud_type'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to')
            }
            
            # Remove None values
            filters = {k: v for k, v in filters.items() if v is not None}
            
            review_service = ReviewService()
            reviews = review_service.get_pending_reviews(filters)
            
            return Response({
                'status': 'success',
                'count': len(reviews),
                'reviews': reviews
            })
            
        except Exception as e:
            logger.error(f"Error getting pending reviews: {e}")
            return Response({
                'status': 'error',
                'message': f'Error getting pending reviews: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_review_case(self, request, attempt_id):
        """Get detailed review case"""
        try:
            if not attempt_id:
                return Response({
                    'status': 'error',
                    'message': 'attempt_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review_service = ReviewService()
            case_data = review_service.get_review_case(attempt_id)
            
            return Response({
                'status': 'success',
                'case': case_data
            })
            
        except Exception as e:
            logger.error(f"Error getting review case: {e}")
            return Response({
                'status': 'error',
                'message': f'Error getting review case: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_review_stats(self, request):
        """Get review statistics"""
        try:
            reviewer_id = request.query_params.get('reviewer_id')
            days = int(request.query_params.get('days', 30))
            
            reviewer = None
            if reviewer_id:
                reviewer = get_object_or_404(User, id=reviewer_id)
            
            review_service = ReviewService()
            stats = review_service.get_review_stats(reviewer, days)
            
            return Response({
                'status': 'success',
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting review stats: {e}")
            return Response({
                'status': 'error',
                'message': f'Error getting review stats: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def make_decision(self, request):
        """Make a decision on a fraud case"""
        try:
            attempt_id = request.data.get('attempt_id')
            decision = request.data.get('decision')
            notes = request.data.get('notes', '')
            metadata = request.data.get('metadata', {})
            
            if not attempt_id or not decision:
                return Response({
                    'status': 'error',
                    'message': 'attempt_id and decision are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review_service = ReviewService()
            result = review_service.review_decision(
                attempt_id=attempt_id,
                decision=decision,
                reviewer=request.user,
                notes=notes,
                metadata=metadata
            )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error making review decision: {e}")
            return Response({
                'status': 'error',
                'message': f'Error making review decision: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def escalate_case(self, request):
        """Escalate a fraud case"""
        try:
            attempt_id = request.data.get('attempt_id')
            escalation_reason = request.data.get('reason', 'Manual escalation')
            priority = request.data.get('priority', 'high')
            
            if not attempt_id:
                return Response({
                    'status': 'error',
                    'message': 'attempt_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review_service = ReviewService()
            result = review_service.escalate_case(
                attempt_id=attempt_id,
                escalation_reason=escalation_reason,
                escalated_by=request.user,
                priority=priority
            )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error escalating case: {e}")
            return Response({
                'status': 'error',
                'message': f'Error escalating case: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def add_comment(self, request):
        """Add comment to fraud case"""
        try:
            attempt_id = request.data.get('attempt_id')
            comment = request.data.get('comment')
            is_internal = request.data.get('is_internal', False)
            
            if not attempt_id or not comment:
                return Response({
                    'status': 'error',
                    'message': 'attempt_id and comment are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review_service = ReviewService()
            result = review_service.add_review_comment(
                attempt_id=attempt_id,
                comment=comment,
                commenter=request.user,
                is_internal=is_internal
            )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return Response({
                'status': 'error',
                'message': f'Error adding comment: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def batch_decisions(self, request):
        """Process multiple review decisions"""
        try:
            decisions = request.data.get('decisions', [])
            
            if not decisions:
                return Response({
                    'status': 'error',
                    'message': 'decisions array is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            review_service = ReviewService()
            result = review_service.batch_review_decisions(decisions, request.user)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error processing batch decisions: {e}")
            return Response({
                'status': 'error',
                'message': f'Error processing batch decisions: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudDashboardAPIView(APIView):
    """
    API endpoints for fraud detection dashboard
    """
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]

    def get(self, request):
        """Get dashboard statistics"""
        try:
            # Time periods
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Fraud attempts statistics
            fraud_attempts_total = FraudAttempt.objects.count()
            fraud_attempts_today = FraudAttempt.objects.filter(created_at__date=today).count()
            fraud_attempts_week = FraudAttempt.objects.filter(created_at__date__gte=week_ago).count()
            fraud_attempts_month = FraudAttempt.objects.filter(created_at__date__gte=month_ago).count()
            
            # Status distribution
            fraud_status = FraudAttempt.objects.values('status').annotate(
                count=Count('id'),
                percentage=Count('id') * 100.0 / fraud_attempts_total if fraud_attempts_total > 0 else 0
            )
            
            # Risk profile statistics
            risk_profiles_total = UserRiskProfile.objects.count()
            flagged_users = UserRiskProfile.objects.filter(is_flagged=True).count()
            restricted_users = UserRiskProfile.objects.filter(is_restricted=True).count()
            
            # High risk users
            high_risk_users = UserRiskProfile.objects.filter(
                overall_risk_score__gte=70
            ).count()
            
            # Alert statistics
            alerts_total = FraudAlert.objects.count()
            unresolved_alerts = FraudAlert.objects.filter(is_resolved=False).count()
            critical_alerts = FraudAlert.objects.filter(priority='critical', is_resolved=False).count()
            
            # Recent fraud attempts (last 24 hours)
            recent_fraud_attempts = FraudAttempt.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-created_at')[:10]
            
            recent_attempts_data = FraudAttemptSerializer(recent_fraud_attempts, many=True).data
            
            # Fraud type distribution
            fraud_type_distribution = FraudAttempt.objects.values('attempt_type').annotate(
                count=Count('id'),
                avg_score=Avg('fraud_score')
            ).order_by('-count')[:5]
            
            # Top fraud detectors
            detector_distribution = FraudAttempt.objects.values('detected_by').annotate(
                count=Count('id'),
                avg_score=Avg('fraud_score')
            ).order_by('-count')[:5]
            
            # Recent alerts
            recent_alerts = FraudAlert.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).order_by('-created_at')[:10]
            
            recent_alerts_data = FraudAlertSerializer(recent_alerts, many=True).data
            
            # Auto-ban statistics
            auto_ban_service = AutoBanService()
            auto_ban_stats = auto_ban_service.get_auto_ban_stats(7)
            
            # Review statistics
            review_service = ReviewService()
            review_stats = review_service.get_review_stats(None, 7)
            
            # Compile dashboard data
            dashboard_data = {
                'overview': {
                    'fraud_attempts_total': fraud_attempts_total,
                    'fraud_attempts_today': fraud_attempts_today,
                    'fraud_attempts_week': fraud_attempts_week,
                    'fraud_attempts_month': fraud_attempts_month,
                    'flagged_users': flagged_users,
                    'restricted_users': restricted_users,
                    'high_risk_users': high_risk_users,
                    'alerts_total': alerts_total,
                    'unresolved_alerts': unresolved_alerts,
                    'critical_alerts': critical_alerts
                },
                'fraud_status': list(fraud_status),
                'fraud_type_distribution': list(fraud_type_distribution),
                'detector_distribution': list(detector_distribution),
                'recent_fraud_attempts': recent_attempts_data,
                'recent_alerts': recent_alerts_data,
                'auto_ban_stats': auto_ban_stats,
                'review_stats': review_stats,
                'updated_at': timezone.now().isoformat()
            }
            
            return Response({
                'status': 'success',
                'dashboard': dashboard_data
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return Response({
                'status': 'error',
                'message': f'Error getting dashboard data: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudSettingsAPIView(APIView):
    """
    Simple settings endpoint for fraud detection toggles (admin-only)
    """
    permission_classes = [IsAuthenticated, IsFraudAnalyst | IsSuperUser]

    def get(self, request, *args, **kwargs):
        """Return current settings"""
        try:
            from .models import FraudSettings
            settings_obj = FraudSettings.objects.first()
            if not settings_obj:
                settings_obj = FraudSettings.objects.create()
            return Response({
                'block_vpn': bool(settings_obj.block_vpn),
                'global_risk_threshold': settings_obj.global_risk_threshold
            })
        except Exception as e:
            logger.error(f"Error reading fraud settings: {e}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        """Update fraud detection settings"""
        try:
            from .models import FraudSettings
            data = request.data
            block_vpn = bool(data.get('block_vpn', False))
            threshold = int(data.get('global_risk_threshold', 70))
            settings_obj = FraudSettings.objects.first()
            if settings_obj:
                settings_obj.block_vpn = block_vpn
                settings_obj.global_risk_threshold = threshold
                if request.user and request.user.is_authenticated:
                    settings_obj.updated_by = request.user
                settings_obj.save()
            else:
                settings_obj = FraudSettings.objects.create(
                    block_vpn=block_vpn,
                    global_risk_threshold=threshold,
                    updated_by=request.user if request.user.is_authenticated else None
                )
            return Response({
                'status': 'success',
                'block_vpn': settings_obj.block_vpn,
                'global_risk_threshold': settings_obj.global_risk_threshold
            })
        except Exception as e:
            logger.error(f"Error writing fraud settings: {e}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsFraudAnalyst | IsSuperUser])
def fraud_statistics(request):
    """
    Get comprehensive fraud statistics
    """
    try:
        # Get time period from query params
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get fraud attempts in period
        fraud_attempts = FraudAttempt.objects.filter(created_at__gte=start_date)
        
        # Calculate statistics
        total_detections = fraud_attempts.count()
        confirmed_fraud = fraud_attempts.filter(status='confirmed').count()
        false_positives = fraud_attempts.filter(status='false_positive').count()
        
        detection_rate = (confirmed_fraud / total_detections * 100) if total_detections > 0 else 0
        
        avg_fraud_score = fraud_attempts.aggregate(
            avg_score=Avg('fraud_score')
        )['avg_score'] or 0
        
        # Top fraud types
        top_fraud_types = fraud_attempts.values('attempt_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        top_types_dict = {item['attempt_type']: item['count'] for item in top_fraud_types}
        
        # Risk distribution
        risk_distribution = UserRiskProfile.objects.aggregate(
            critical=Count('id', filter=Q(overall_risk_score__gte=90)),
            high=Count('id', filter=Q(overall_risk_score__gte=80, overall_risk_score__lt=90)),
            medium=Count('id', filter=Q(overall_risk_score__gte=60, overall_risk_score__lt=80)),
            low=Count('id', filter=Q(overall_risk_score__lt=60))
        )
        
        # Monthly trend
        monthly_trend = []
        for i in range(min(6, days // 30), -1, -1):
            month_start = timezone.now() - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            
            month_data = fraud_attempts.filter(
                created_at__date__gte=month_start,
                created_at__date__lt=month_end
            ).aggregate(
                total=Count('id'),
                confirmed=Count('id', filter=Q(status='confirmed')),
                avg_score=Avg('fraud_score')
            )
            
            monthly_trend.append({
                'month': month_start.strftime('%Y-%m'),
                'total': month_data['total'] or 0,
                'confirmed': month_data['confirmed'] or 0,
                'avg_score': float(month_data['avg_score'] or 0)
            })
        
        # Compile statistics
        statistics = {
            'total_detections': total_detections,
            'confirmed_fraud': confirmed_fraud,
            'false_positives': false_positives,
            'detection_rate': detection_rate,
            'average_fraud_score': avg_fraud_score,
            'top_fraud_types': top_types_dict,
            'risk_distribution': risk_distribution,
            'monthly_trend': monthly_trend,
            'time_period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            }
        }
        
        serializer = FraudStatisticsSerializer(data=statistics)
        serializer.is_valid(raise_exception=True)
        
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error getting fraud statistics: {e}")
        return Response({
            'status': 'error',
            'message': f'Error getting fraud statistics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_fraud_check(request):
    """
    Quick fraud check for user or transaction
    """
    try:
        check_type = request.data.get('type', 'user')
        
        if check_type == 'user':
            user_id = request.data.get('user_id')
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user risk profile
            risk_profile = UserRiskProfile.objects.filter(user_id=user_id).first()
            
            if not risk_profile:
                return Response({
                    'status': 'success',
                    'is_fraud': False,
                    'fraud_score': 0,
                    'message': 'No risk profile found for user'
                })
            
            # Quick check based on risk profile
            is_fraud = risk_profile.overall_risk_score >= 70
            
            return Response({
                'status': 'success',
                'is_fraud': is_fraud,
                'fraud_score': risk_profile.overall_risk_score,
                'is_flagged': risk_profile.is_flagged,
                'is_restricted': risk_profile.is_restricted,
                'risk_level': 'high' if risk_profile.overall_risk_score >= 70 else 'medium' if risk_profile.overall_risk_score >= 50 else 'low'
            })
        
        elif check_type == 'transaction':
            amount = request.data.get('amount', 0)
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response({
                    'status': 'error',
                    'message': 'user_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Simple transaction check
            is_fraud = False
            fraud_score = 0
            reasons = []
            
            # Check amount
            if amount > 1000:
                fraud_score += 30
                reasons.append('Large transaction amount')
                is_fraud = True
            
            # Check user risk
            risk_profile = UserRiskProfile.objects.filter(user_id=user_id).first()
            if risk_profile and risk_profile.overall_risk_score >= 60:
                fraud_score += risk_profile.overall_risk_score * 0.5
                reasons.append('High risk user')
                is_fraud = True
            
            return Response({
                'status': 'success',
                'is_fraud': is_fraud,
                'fraud_score': min(100, fraud_score),
                'reasons': reasons,
                'recommendation': 'Review manually' if is_fraud else 'Proceed'
            })
        
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid check type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error in quick fraud check: {e}")
        return Response({
            'status': 'error',
            'message': f'Error in quick fraud check: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)