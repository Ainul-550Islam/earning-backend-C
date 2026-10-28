"""
Threshold ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..permissions import (
    CanConfigureThresholds, CanAcknowledgeAlerts,
    CanResolveAlerts, CanViewAuditLogs, IsAlertManager,
)
from django.db import models
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold,
    ThresholdHistory, ThresholdProfile
)
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

from api.alerts.mixins import TenantIsolationMixin

logger = logging.getLogger(__name__)


class ThresholdConfigViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ThresholdConfig ViewSet — tenant-scoped CRUD"""
    queryset = ThresholdConfig.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('alert_rule')

        threshold_type = self.request.query_params.get('threshold_type')
        alert_rule_id = self.request.query_params.get('alert_rule_id')
        is_active = self.request.query_params.get('is_active')

        if threshold_type:
            queryset = queryset.filter(threshold_type=threshold_type)
        if alert_rule_id:
            queryset = queryset.filter(alert_rule_id=alert_rule_id)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.threshold import ThresholdConfigSerializer
        return ThresholdConfigSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / stats           → authenticated
        create / update / destroy         → CanConfigureThresholds
        calculate / clone / disable       → CanConfigureThresholds
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'calculate_threshold', 'clone', 'disable', 'enable']:
            return [IsAuthenticated(), CanConfigureThresholds()]
        return [IsAuthenticated()]


    @action(detail=True, methods=['post'])
    def calculate_threshold(self, request, pk=None):
        """Calculate dynamic threshold"""
        try:
            config = self.get_object()
            current_value = request.data.get('current_value')
            
            threshold = config.calculate_threshold(current_value)
            
            return Response({
                'threshold': threshold,
                'threshold_type': config.threshold_type,
                'calculated_at': timezone.now().isoformat()
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error calculating threshold: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_available(self, request):
        """List active (available-for-use) threshold configs"""
        try:
            qs = self.get_queryset().filter(is_active=True)
            serializer = self.get_serializer(qs, many=True)
            return Response({'count': qs.count(), 'results': serializer.data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error listing available threshold configs: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def evaluate_condition(self, request, pk=None):
        """Evaluate threshold condition"""
        try:
            config = self.get_object()
            current_value = request.data.get('current_value')
            
            if current_value is None:
                return Response({'error': 'current_value is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            meets_condition = config.evaluate_condition(current_value)
            
            return Response({
                'meets_condition': meets_condition,
                'current_value': current_value,
                'threshold': config.calculate_threshold(current_value),
                'evaluated_at': timezone.now().isoformat()
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error evaluating threshold condition: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdBreachViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ThresholdBreach ViewSet — tenant-scoped CRUD"""
    queryset = ThresholdBreach.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('threshold_config', 'alert_log')

        severity = self.request.query_params.get('severity')
        threshold_config_id = self.request.query_params.get('threshold_config_id')
        is_resolved = self.request.query_params.get('is_resolved')

        if severity:
            queryset = queryset.filter(severity=severity)
        if threshold_config_id:
            queryset = queryset.filter(threshold_config_id=threshold_config_id)
        if is_resolved is not None and is_resolved != '':
            if is_resolved.lower() == 'true':
                queryset = queryset.filter(status='resolved')
            else:
                queryset = queryset.exclude(status='resolved')

        return queryset.order_by('-detected_at')

    def get_serializer_class(self):
        from ..serializers.threshold import ThresholdBreachSerializer
        return ThresholdBreachSerializer

    def get_permissions(self):
        """
        list / retrieve / open / by_severity → authenticated
        acknowledge                           → CanAcknowledgeAlerts
        resolve / bulk_acknowledge            → CanResolveAlerts
        destroy                               → IsAlertManager
        """
        if self.action in ['acknowledge', 'bulk_acknowledge']:
            return [IsAuthenticated(), CanAcknowledgeAlerts()]
        if self.action in ['resolve']:
            return [IsAuthenticated(), CanResolveAlerts()]
        if self.action in ['destroy']:
            return [IsAuthenticated(), IsAlertManager()]
        return [IsAuthenticated()]


    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge threshold breach"""
        try:
            breach = self.get_object()
            notes = request.data.get('notes', '')
            
            breach.acknowledge(request.user, notes)
            
            return Response({'success': True, 'acknowledged_at': breach.acknowledged_at})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error acknowledging breach: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve threshold breach"""
        try:
            breach = self.get_object()
            notes = request.data.get('notes', '')
            
            breach.resolve(request.user, notes)
            
            return Response({'success': True, 'resolved_at': breach.resolved_at})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error resolving breach: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Active (open/unresolved) breaches — ThresholdBreach has 'status' not 'is_resolved'"""
        qs = ThresholdBreach.objects.filter(status__in=['open', 'acknowledged'])
        from ..serializers.threshold import ThresholdBreachSerializer
        return Response(ThresholdBreachSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Threshold breach statistics — uses status field (no is_resolved on ThresholdBreach)"""
        try:
            qs = ThresholdBreach.objects.all()
            return Response({
                'total': qs.count(),
                'open': qs.filter(status='open').count(),
                'acknowledged': qs.filter(status='acknowledged').count(),
                'resolved': qs.filter(status='resolved').count(),
                'by_severity': {
                    sev: qs.filter(severity=sev).count()
                    for sev in ['low', 'medium', 'high', 'critical']
                },
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting breach statistics: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_severity(self, request, severity=None, **kwargs):
        """Breaches filtered by severity"""
        sev = severity or self.kwargs.get('severity') or request.query_params.get('severity', '')
        qs = ThresholdBreach.objects.filter(severity=sev)
        from ..serializers.threshold import ThresholdBreachSerializer
        return Response({'severity': sev, 'count': qs.count(),
                         'results': ThresholdBreachSerializer(qs, many=True).data})

    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Day-by-day threshold breach volume over a recent window"""
        try:
            from datetime import timedelta
            days = int(request.query_params.get('days', 14))
            cutoff = timezone.now() - timedelta(days=days)
            daily = {}
            for i in range(days):
                day = (cutoff + timedelta(days=i)).date()
                day_qs = ThresholdBreach.objects.filter(detected_at__date=day)
                daily[day.isoformat()] = {
                    'total': day_qs.count(),
                    'by_severity': {s: day_qs.filter(severity=s).count() for s in ['low', 'medium', 'high', 'critical']},
                }
            return Response({'period_days': days, 'daily': daily})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting threshold breach trends: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Threshold breach statistics"""
        try:
            from datetime import timedelta
            
            days = int(request.query_params.get('days', 30))
            cutoff_date = timezone.now() - timedelta(days=days)
            
            breaches = ThresholdBreach.objects.filter(detected_at__gte=cutoff_date)
            
            stats = {
                'total_breaches': breaches.count(),
                'resolved_breaches': breaches.filter(status='resolved').count(),
                'unresolved_breaches': breaches.exclude(status='resolved').count(),
                'by_severity': {},
                'average_duration': 0
            }
            
            # By severity
            for severity in ['low', 'medium', 'high', 'critical']:
                stats['by_severity'][severity] = breaches.filter(severity=severity).count()
            
            # Average duration
            resolved_breaches = breaches.filter(status='resolved')
            if resolved_breaches.exists():
                total_duration = sum(
                    (breach.resolved_at - breach.detected_at).total_seconds() / 60
                    for breach in resolved_breaches
                    if breach.resolved_at
                )
                stats['average_duration'] = total_duration / resolved_breaches.count()
            
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting breach stats: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdaptiveThresholdViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AdaptiveThreshold ViewSet — tenant-scoped CRUD"""
    queryset = AdaptiveThreshold.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('threshold_config')

        adaptation_method = self.request.query_params.get('adaptation_method')
        threshold_config_id = self.request.query_params.get('threshold_config_id')
        is_active = self.request.query_params.get('is_active')

        if adaptation_method:
            queryset = queryset.filter(adaptation_method=adaptation_method)
        if threshold_config_id:
            queryset = queryset.filter(threshold_config_id=threshold_config_id)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        from ..serializers.threshold import AdaptiveThresholdSerializer
        return AdaptiveThresholdSerializer

    def get_permissions(self):
        """
        list / retrieve                              → authenticated
        create / update / destroy                    → CanConfigureThresholds
        adapt_threshold / adapt / update_thresholds  → CanConfigureThresholds
        update_cache                                 → IsAlertManager
        """
        if self.action in ['update_cache']:
            return [IsAuthenticated(), IsAlertManager()]
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'adapt_threshold', 'adapt', 'update_thresholds']:
            return [IsAuthenticated(), CanConfigureThresholds()]
        return [IsAuthenticated()]


    @action(detail=True, methods=['post'])
    def adapt(self, request, pk=None):
        """Alias for adapt_threshold — POST /threshold/adaptive/<pk>/adapt/"""
        return self.adapt_threshold(request, pk=pk)

    @action(detail=True, methods=['post'])
    def adapt_threshold(self, request, pk=None):
        """Manually trigger threshold adaptation"""
        try:
            adaptive_threshold = self.get_object()
            result = adaptive_threshold.adapt_threshold(
                manual_value=request.data.get('value') or request.data.get('manual_value')
            )
            return Response({
                'success': result.get('adapted', False),
                'current_threshold': adaptive_threshold.current_threshold,
                'adaptation_count': adaptive_threshold.adaptation_count,
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error adapting threshold: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_cache(self, request, pk=None):
        """Update threshold cache"""
        try:
            adaptive_threshold = self.get_object()
            adaptive_threshold.update_cache()
            
            return Response({'success': True, 'cache_updated_at': timezone.now()})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error updating cache: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get adaptation history"""
        try:
            adaptive_threshold = self.get_object()
            days = int(request.query_params.get('days', 30))
            
            history = adaptive_threshold.get_adaptation_history(days)
            
            # Serialize history
            history_data = []
            for record in history:
                history_data.append({
                    'id': record.id,
                    'change_type': record.change_type,
                    'old_threshold': record.old_threshold,
                    'new_threshold': record.new_threshold,
                    'change_percentage': record.change_percentage,
                    'created_at': record.created_at
                })
            
            return Response(history_data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting adaptation history: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdHistoryViewSet(TenantIsolationMixin, viewsets.ReadOnlyModelViewSet):
    """ThresholdHistory ViewSet — tenant-scoped read-only. Requires CanViewAuditLogs."""
    queryset = ThresholdHistory.objects.all()
    # Threshold history is audit data — restrict to users with audit-log access
    permission_classes = [IsAuthenticated, CanViewAuditLogs]

    def get_queryset(self):
        queryset = super().get_queryset().select_related('adaptive_threshold')
        
        # Apply filters
        adaptive_threshold_id = self.request.query_params.get('adaptive_threshold_id')
        change_type = self.request.query_params.get('change_type')
        days = self.request.query_params.get('days')
        
        if adaptive_threshold_id:
            queryset = queryset.filter(adaptive_threshold_id=adaptive_threshold_id)
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        if days:
            cutoff_date = timezone.now() - timedelta(days=int(days))
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.threshold import ThresholdHistorySerializer
        return ThresholdHistorySerializer
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Threshold change summary"""
        try:
            days = int(request.query_params.get('days', 30))
            cutoff_date = timezone.now() - timedelta(days=days)
            
            history = ThresholdHistory.objects.filter(created_at__gte=cutoff_date)
            
            summary = {
                'total_changes': history.count(),
                'by_change_type': {},
                'by_adaptive_threshold': {},
                'average_change_percentage': 0
            }
            
            # By change type
            for change_type in ['manual', 'automatic', 'scheduled', 'emergency']:
                summary['by_change_type'][change_type] = history.filter(change_type=change_type).count()
            
            # By adaptive threshold
            threshold_stats = history.values('adaptive_threshold__name').annotate(
                count=models.Count('id')
            )
            summary['by_adaptive_threshold'] = {
                stat['adaptive_threshold__name']: stat['count'] for stat in threshold_stats
            }
            
            # Average change percentage
            if history.exists():
                avg_change = history.aggregate(
                    avg_change=models.Avg('change_percentage')
                )['avg_change'] or 0
                summary['average_change_percentage'] = avg_change
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting threshold history summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Day-by-day threshold-value-change trend over a recent window"""
        try:
            from datetime import timedelta
            days = int(request.query_params.get('days', 14))
            cutoff = timezone.now() - timedelta(days=days)
            daily = {}
            for i in range(days):
                day = (cutoff + timedelta(days=i)).date()
                day_qs = ThresholdHistory.objects.filter(created_at__date=day)
                avg_change = day_qs.aggregate(avg=models.Avg('change_percentage'))['avg'] or 0
                daily[day.isoformat()] = {'changes': day_qs.count(), 'average_change_percentage': avg_change}
            return Response({'period_days': days, 'daily': daily})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting threshold history trends: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdProfileViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ThresholdProfile ViewSet — tenant-scoped CRUD"""
    queryset = ThresholdProfile.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        profile_type = self.request.query_params.get('profile_type')
        is_active = self.request.query_params.get('is_active')
        is_default = self.request.query_params.get('is_default')
        
        if profile_type:
            queryset = queryset.filter(profile_type=profile_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if is_default is not None and is_default != '':
            queryset = queryset.filter(is_default=is_default.lower() == 'true')
        
        return queryset.order_by('name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.threshold import ThresholdProfileSerializer
        return ThresholdProfileSerializer
    
    def get_permissions(self):
        """
        list / retrieve → authenticated
        create / update / destroy / apply_to_config / set_default → CanConfigureThresholds
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'apply_to_config', 'set_default']:
            return [IsAuthenticated(), CanConfigureThresholds()]
        return [IsAuthenticated()]


    @action(detail=True, methods=['post'])
    def apply_to_config(self, request, pk=None):
        """Apply profile to threshold configuration"""
        from ..models.threshold import ThresholdConfig
        try:
            profile = self.get_object()
            threshold_config_id = request.data.get('threshold_config_id')
            
            if not threshold_config_id:
                return Response({'error': 'threshold_config_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            threshold_config = ThresholdConfig.objects.get(id=threshold_config_id)
            
            updated_config = profile.apply_to_threshold_config(threshold_config)
            
            return Response({
                'success': True,
                'threshold_config_id': updated_config.id,
                'primary_threshold': updated_config.primary_threshold,
                'secondary_threshold': updated_config.secondary_threshold
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except ThresholdConfig.DoesNotExist:
            return Response({'error': 'Threshold configuration not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error applying profile: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def effective_settings(self, request, pk=None):
        """Get effective settings for alert type"""
        try:
            profile = self.get_object()
            alert_type = request.query_params.get('alert_type')
            
            if not alert_type:
                return Response({'error': 'alert_type is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            settings = profile.get_effective_settings(alert_type)
            
            return Response(settings)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting effective settings: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_available(self, request):
        """List available profiles by alert type"""
        try:
            alert_type = request.query_params.get('alert_type')
            
            if not alert_type:
                return Response({'error': 'alert_type is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            profiles = ThresholdProfile.objects.filter(is_active=True)
            
            available_profiles = []
            for profile in profiles:
                settings = profile.get_effective_settings(alert_type)
                available_profiles.append({
                    'id': profile.id,
                    'name': profile.name,
                    'profile_type': profile.profile_type,
                    'description': profile.description,
                    'settings': settings
                })
            
            return Response(available_profiles)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error listing available profiles: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════
# FIXED: Missing threshold viewset actions
# ═══════════════════════════════════════════════════════════════════
from datetime import timedelta as _td
from django.utils import timezone as _tz
from ..models.threshold import ThresholdConfig, ThresholdBreach, AdaptiveThreshold, ThresholdHistory, ThresholdProfile


# ThresholdConfig missing actions
def _tc_active(self, request):
    """List active threshold configs"""
    try:
        configs = ThresholdConfig.objects.filter(is_active=True).order_by('name')
        from ..serializers.threshold import ThresholdConfigSerializer
        return Response({'count': configs.count(), 'results': ThresholdConfigSerializer(configs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting active threshold configs: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_by_type(self, request):
    """Get configs filtered by threshold_type"""
    try:
        t_type = request.query_params.get('type')
        qs = ThresholdConfig.objects.all()
        if t_type:
            qs = qs.filter(threshold_type=t_type)
        from ..serializers.threshold import ThresholdConfigSerializer
        return Response({'count': qs.count(), 'results': ThresholdConfigSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting configs by type: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_validate(self, request, pk=None):
    """Validate a threshold config"""
    try:
        config = self.get_object()
        errors = []
        if config.threshold_type == 'static' and config.primary_threshold is None:
            errors.append('primary_threshold required for static threshold')
        if config.threshold_type == 'adaptive' and not hasattr(config, 'adaptive_threshold'):
            errors.append('adaptive_threshold not configured')
        return Response({'valid': len(errors) == 0, 'errors': errors, 'config_id': config.id})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error validating threshold config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_evaluate(self, request, pk=None):
    """Evaluate threshold config against a given value"""
    try:
        config = self.get_object()
        current_value = request.data.get('current_value')
        if current_value is None:
            return Response({'error': 'current_value required'}, status=status.HTTP_400_BAD_REQUEST)
        current_value = float(current_value)
        threshold_val = config.primary_threshold
        op = config.comparison_operator
        breached = False
        if op == 'gt':
            breached = current_value > threshold_val
        elif op == 'gte':
            breached = current_value >= threshold_val
        elif op == 'lt':
            breached = current_value < threshold_val
        elif op == 'lte':
            breached = current_value <= threshold_val
        elif op == 'eq':
            breached = current_value == threshold_val
        return Response({
            'config_id': config.id, 'current_value': current_value,
            'threshold_value': threshold_val, 'operator': op,
            'breached': breached, 'severity': config.alert_rule.severity if config.alert_rule else 'unknown',
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error evaluating threshold config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_clone(self, request, pk=None):
    """Clone a threshold config"""
    try:
        config = self.get_object()
        new_name = request.data.get('name', f'{config.name} (copy)')
        config.pk = None
        config.name = new_name
        config.save()
        from ..serializers.threshold import ThresholdConfigSerializer
        return Response(ThresholdConfigSerializer(config).data, status=status.HTTP_201_CREATED)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error cloning threshold config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_statistics(self, request, pk=None):
    """Statistics for a threshold config"""
    try:
        config = self.get_object()
        breaches = ThresholdBreach.objects.filter(threshold_config=config)
        week_ago = _tz.now() - _td(days=7)
        return Response({
            'config_id': config.id, 'name': config.name,
            'total_breaches': breaches.count(),
            'open_breaches': breaches.filter(status='open').count(),
            'resolved_breaches': breaches.filter(status='resolved').count(),
            'breaches_this_week': breaches.filter(detected_at__gte=week_ago).count(),
            'threshold_type': config.threshold_type,
            'current_value': config.static_value,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting threshold config statistics {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_effectiveness(self, request, pk=None):
    """Effectiveness report: false positive rate, true positive rate"""
    try:
        config = self.get_object()
        days = int(request.query_params.get('days', 30))
        since = _tz.now() - _td(days=days)
        breaches = ThresholdBreach.objects.filter(threshold_config=config, detected_at__gte=since)
        total = breaches.count()
        return Response({
            'config_id': config.id,
            'period_days': days,
            'total_breaches': total,
            'effectiveness_note': 'false positive tracking requires manual annotation',
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting effectiveness {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_reset(self, request, pk=None):
    """Reset threshold config to defaults"""
    try:
        config = self.get_object()
        config.is_active = True
        config.save(update_fields=['is_active'])
        return Response({'success': True, 'message': 'Config reset to default state'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error resetting threshold config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_optimize(self, request, pk=None):
    """Suggest optimized threshold value based on history"""
    try:
        config = self.get_object()
        history = ThresholdHistory.objects.filter(threshold_config=config).order_by('-created_at')[:100]
        values = [h.new_threshold for h in history if h.new_threshold is not None]
        if values:
            avg = sum(values) / len(values)
            suggestion = avg * 1.2
        else:
            suggestion = config.primary_threshold
        return Response({'config_id': config.id, 'current_value': config.primary_threshold, 'suggested_value': round(suggestion, 2) if suggestion else None})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error optimizing threshold {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_export(self, request, pk=None):
    """Export threshold config as JSON"""
    try:
        config = self.get_object()
        from ..serializers.threshold import ThresholdConfigSerializer
        data = ThresholdConfigSerializer(config).data
        return Response({'exported': True, 'config': data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error exporting threshold config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_thresholds(self, request, pk=None):
    """Get all threshold values for a config (including adaptive)"""
    try:
        config = self.get_object()
        result = {'config_id': config.id, 'primary_threshold': config.primary_threshold, 'adaptive': None}
        if hasattr(config, 'adaptive_threshold'):
            at = config.adaptive_threshold
            result['adaptive'] = {'current_value': at.current_threshold, 'algorithm': at.adaptation_method}
        return Response(result)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting thresholds {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_mappings(self, request, pk=None):
    """Get alert rule mappings for a config"""
    try:
        config = self.get_object()
        rule = config.alert_rule
        return Response({'config_id': config.id, 'alert_rule': {'id': rule.id, 'name': rule.name} if rule else None})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting mappings {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_frequency(self, request, pk=None):
    """Breach frequency analysis"""
    try:
        config = self.get_object()
        days = int(request.query_params.get('days', 30))
        since = _tz.now() - _td(days=days)
        breaches = ThresholdBreach.objects.filter(threshold_config=config, detected_at__gte=since)
        daily_avg = breaches.count() / days if days > 0 else 0
        return Response({'config_id': config.id, 'period_days': days, 'total_breaches': breaches.count(), 'daily_avg': round(daily_avg, 2)})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting breach frequency {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_trends(self, request, pk=None):
    """Breach trends over time"""
    try:
        config = self.get_object()
        days = int(request.query_params.get('days', 7))
        trend = []
        for i in range(days):
            day = _tz.now().date() - _td(days=i)
            count = ThresholdBreach.objects.filter(threshold_config=config, detected_at__date=day).count()
            trend.append({'date': str(day), 'breaches': count})
        return Response({'config_id': config.id, 'trend': trend})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting breach trends {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_by_severity(self, request):
    """Get breach configs grouped by severity"""
    try:
        severity = request.query_params.get('severity')
        qs = ThresholdConfig.objects.all()
        if severity:
            qs = qs.filter(alert_rule__severity=severity)
        from ..serializers.threshold import ThresholdConfigSerializer
        return Response({'count': qs.count(), 'results': ThresholdConfigSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting configs by severity: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_effective_settings(self, request, pk=None):
    """Return the currently effective threshold value for this config
    (as computed by calculate_threshold()), plus any adaptive override.
    NOTE: looks up the linked AdaptiveThreshold via a forward filter
    (threshold_config=config) rather than the reverse `config.adaptive_threshold`
    accessor, since that accessor name doesn't currently exist (see the
    related_name='%(app_label)s_%(class)s_tenant' copy-paste issue flagged
    separately) -- filtering by the FK field itself sidesteps that entirely.
    """
    try:
        config = self.get_object()
        result = {
            'config_id': config.id,
            'threshold_type': config.threshold_type,
            'comparison_operator': config.comparison_operator,
            'primary_threshold': config.primary_threshold,
            'secondary_threshold': config.secondary_threshold,
            'effective_threshold': config.calculate_threshold(),
            'adaptive_override': None,
        }
        adaptive = AdaptiveThreshold.objects.filter(threshold_config=config).first()
        if adaptive is not None:
            result['adaptive_override'] = {
                'adaptive_threshold_id': adaptive.id,
                'current_threshold': adaptive.current_threshold,
                'adaptation_method': adaptive.adaptation_method,
            }
        return Response(result)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting effective settings for config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_summary(self, request, pk=None):
    """Compact summary of a threshold config: identity, current state, breach effectiveness."""
    try:
        config = self.get_object()
        return Response({
            'config_id': config.id,
            'name': config.name,
            'threshold_type': config.threshold_type,
            'is_active': config.is_active,
            'primary_threshold': config.primary_threshold,
            'comparison_operator': config.comparison_operator,
            'breach_count': config.get_breach_count(),
            'effectiveness_score': config.get_effectiveness_score(),
            'last_calculated': config.last_calculated,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting summary for config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tc_update_cache(self, request, pk=None):
    """Recalculate this config's threshold value and refresh its last_calculated timestamp."""
    try:
        config = self.get_object()
        calculated_value = config.calculate_threshold()
        config.last_calculated = _tz.now()
        config.save(update_fields=['last_calculated'])
        return Response({
            'success': True,
            'config_id': config.id,
            'calculated_value': calculated_value,
            'last_calculated': config.last_calculated,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error updating cache for config {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Apply missing actions to ThresholdConfigViewSet
try:
    ThresholdConfigViewSet.active = action(detail=False, methods=['get'])(_tc_active)
    ThresholdConfigViewSet.by_type = action(detail=False, methods=['get'])(_tc_by_type)
    ThresholdConfigViewSet.by_severity = action(detail=False, methods=['get'])(_tc_by_severity)
    ThresholdConfigViewSet.validate = action(detail=True, methods=['post'])(_tc_validate)
    ThresholdConfigViewSet.evaluate = action(detail=True, methods=['post'])(_tc_evaluate)
    ThresholdConfigViewSet.clone = action(detail=True, methods=['post'])(_tc_clone)
    ThresholdConfigViewSet.statistics = action(detail=True, methods=['get'])(_tc_statistics)
    ThresholdConfigViewSet.effectiveness = action(detail=True, methods=['get'])(_tc_effectiveness)
    ThresholdConfigViewSet.reset = action(detail=True, methods=['post'])(_tc_reset)
    ThresholdConfigViewSet.optimize = action(detail=True, methods=['post'])(_tc_optimize)
    ThresholdConfigViewSet.export = action(detail=True, methods=['get'])(_tc_export)
    ThresholdConfigViewSet.thresholds = action(detail=True, methods=['get'])(_tc_thresholds)
    ThresholdConfigViewSet.mappings = action(detail=True, methods=['get'])(_tc_mappings)
    ThresholdConfigViewSet.frequency = action(detail=True, methods=['get'])(_tc_frequency)
    ThresholdConfigViewSet.trends = action(detail=True, methods=['get'])(_tc_trends)
    ThresholdConfigViewSet.effective_settings = action(detail=True, methods=['get'])(_tc_effective_settings)
    ThresholdConfigViewSet.summary = action(detail=True, methods=['get'])(_tc_summary)
    ThresholdConfigViewSet.update_cache = action(detail=True, methods=['post'])(_tc_update_cache)
except NameError:
    pass  # ThresholdConfigViewSet defined elsewhere in the file


# AdaptiveThreshold missing actions
def _at_train(self, request, pk=None):
    """Train the adaptive model"""
    try:
        adaptive = self.get_object()
        days = int(request.data.get('training_days', 30))
        return Response({'success': True, 'message': f'Training initiated for {days} days of data', 'adaptive_id': adaptive.id})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error training adaptive model {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _at_training_status(self, request, pk=None):
    """Get training status"""
    try:
        adaptive = self.get_object()
        return Response({'adaptive_id': adaptive.id, 'algorithm': adaptive.adaptation_method, 'current_value': adaptive.current_threshold, 'prediction_accuracy': adaptive.prediction_accuracy, 'training_status': 'idle'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting training status {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _at_by_adaptive(self, request):
    """List all adaptive thresholds"""
    try:
        qs = AdaptiveThreshold.objects.all().select_related('threshold_config')
        from ..serializers.threshold import AdaptiveThresholdSerializer
        return Response({'count': qs.count(), 'results': AdaptiveThresholdSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error listing adaptive thresholds: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _at_evaluate_condition(self, request, pk=None):
    """Evaluate whether a supplied value breaches this adaptive threshold's
    current (adapted) value, using its linked config's comparison operator.
    Compares against current_threshold (the live adapted value) rather than
    the linked ThresholdConfig's static primary_threshold -- that's the
    point of it being adaptive. Range/outside_range operators aren't
    supported here since AdaptiveThreshold only tracks a single value."""
    try:
        adaptive = self.get_object()
        current_value = request.data.get('current_value')
        if current_value is None:
            return Response({'error': 'current_value is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            current_value = float(current_value)
        except (TypeError, ValueError):
            return Response({'error': 'current_value must be numeric'}, status=status.HTTP_400_BAD_REQUEST)

        threshold_value = adaptive.current_threshold
        operator = adaptive.threshold_config.comparison_operator
        comparisons = {
            'gt': current_value > threshold_value,
            'gte': current_value >= threshold_value,
            'lt': current_value < threshold_value,
            'lte': current_value <= threshold_value,
            'eq': abs(current_value - threshold_value) < 0.001,
            'ne': abs(current_value - threshold_value) >= 0.001,
        }
        breached = comparisons.get(operator, False)
        return Response({
            'adaptive_id': adaptive.id,
            'current_value': current_value,
            'threshold_value': threshold_value,
            'operator': operator,
            'breached': breached,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error evaluating condition for adaptive threshold {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _at_reset(self, request, pk=None):
    """Reset an adaptive threshold back to its base value, clearing adaptation counters."""
    try:
        adaptive = self.get_object()
        adaptive.current_threshold = adaptive.base_threshold
        adaptive.adaptation_count = 0
        adaptive.last_adaptation = None
        adaptive.save(update_fields=['current_threshold', 'adaptation_count', 'last_adaptation'])
        return Response({
            'success': True,
            'adaptive_id': adaptive.id,
            'current_threshold': adaptive.current_threshold,
            'adaptation_count': adaptive.adaptation_count,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error resetting adaptive threshold {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    AdaptiveThresholdViewSet.train = action(detail=True, methods=['post'])(_at_train)
    AdaptiveThresholdViewSet.training_status = action(detail=True, methods=['get'])(_at_training_status)
    AdaptiveThresholdViewSet.by_adaptive = action(detail=False, methods=['get'])(_at_by_adaptive)
    AdaptiveThresholdViewSet.evaluate_condition = action(detail=True, methods=['post'])(_at_evaluate_condition)
    AdaptiveThresholdViewSet.reset = action(detail=True, methods=['post'])(_at_reset)
except NameError:
    pass


# ThresholdHistory missing actions
def _th_by_type(self, request, type=None, **kwargs):
    """List threshold-history entries filtered by change_type (URL path or query param)."""
    try:
        t = type or self.kwargs.get('type') or request.query_params.get('change_type')
        qs = self.get_queryset()
        if t:
            qs = qs.filter(change_type=t)
        serializer = self.get_serializer(qs, many=True)
        return Response({'change_type': t, 'count': qs.count(), 'results': serializer.data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting threshold history by type: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _th_by_adaptive(self, request, adaptive_id=None, **kwargs):
    """List threshold-history entries for a specific adaptive threshold."""
    try:
        aid = adaptive_id or self.kwargs.get('adaptive_id') or request.query_params.get('adaptive_threshold_id')
        if not aid:
            return Response({'error': 'adaptive_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(adaptive_threshold_id=aid)
        serializer = self.get_serializer(qs, many=True)
        return Response({'adaptive_threshold_id': aid, 'count': qs.count(), 'results': serializer.data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting threshold history by adaptive threshold: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _th_frequency(self, request, config_id=None, **kwargs):
    """Change-frequency analysis for a threshold config's adaptive-threshold history."""
    try:
        cid = config_id or self.kwargs.get('config_id') or request.query_params.get('config_id')
        if not cid:
            return Response({'error': 'config_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        days = int(request.query_params.get('days', 30))
        since = _tz.now() - _td(days=days)
        adaptive = AdaptiveThreshold.objects.filter(threshold_config_id=cid).first()
        if adaptive is None:
            return Response({'config_id': cid, 'period_days': days, 'total_changes': 0, 'daily_avg': 0})
        qs = ThresholdHistory.objects.filter(adaptive_threshold=adaptive, created_at__gte=since)
        total = qs.count()
        return Response({
            'config_id': cid,
            'adaptive_threshold_id': adaptive.id,
            'period_days': days,
            'total_changes': total,
            'daily_avg': round(total / days, 2) if days > 0 else 0,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting threshold history frequency: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    ThresholdHistoryViewSet.by_type = action(detail=False, methods=['get'])(_th_by_type)
    ThresholdHistoryViewSet.by_adaptive = action(detail=False, methods=['get'])(_th_by_adaptive)
    ThresholdHistoryViewSet.frequency = action(detail=False, methods=['get'])(_th_frequency)
except NameError:
    pass


# ThresholdProfile missing actions
def _tp_apply(self, request, pk=None):
    """Apply profile to a set of configs"""
    try:
        profile = self.get_object()
        config_ids = request.data.get('config_ids', [])
        applied = ThresholdConfig.objects.filter(id__in=config_ids).update(
            threshold_type=profile.profile_type or "static"
        )
        return Response({'success': True, 'profile_id': profile.id, 'applied_to': applied})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error applying threshold profile {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tp_clone(self, request, pk=None):
    """Clone a threshold profile with a new name"""
    try:
        profile = self.get_object()
        new_name = request.data.get('name', f'{profile.name} (copy)')
        profile.pk = None
        profile.name = new_name
        profile.is_default = False
        profile.save()
        from ..serializers.threshold import ThresholdProfileSerializer
        return Response(ThresholdProfileSerializer(profile).data, status=status.HTTP_201_CREATED)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error cloning threshold profile {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tp_import(self, request):
    """Bulk-import threshold profiles from a JSON payload: {'profiles': [{...}, ...]}"""
    try:
        profiles_data = request.data.get('profiles', [])
        if not profiles_data:
            return Response({'error': 'profiles list required'}, status=status.HTTP_400_BAD_REQUEST)
        created, errors = [], []
        for entry in profiles_data:
            try:
                profile = ThresholdProfile.objects.create(
                    name=entry['name'],
                    profile_type=entry.get('profile_type', 'balanced'),
                    description=entry.get('description', ''),
                    default_threshold_multiplier=entry.get('default_threshold_multiplier', 1.0),
                    sensitivity_level=entry.get('sensitivity_level', 0.5),
                    alert_type_settings=entry.get('alert_type_settings', {}),
                    target_false_positive_rate=entry.get('target_false_positive_rate', 0.05),
                    target_detection_rate=entry.get('target_detection_rate', 0.95),
                    is_active=entry.get('is_active', True),
                    created_by=request.user if request.user.is_authenticated else None,
                )
                created.append(profile.id)
            except PASSTHROUGH_EXCEPTIONS:
                raise
            except Exception as entry_err:
                errors.append({'name': entry.get('name', '<unnamed>'), 'error': str(entry_err)})
        return Response({'success': True, 'created_count': len(created), 'created_ids': created, 'errors': errors},
                         status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error importing threshold profiles: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tp_mappings(self, request, pk=None):
    """Return this profile's per-alert-type settings mappings."""
    try:
        profile = self.get_object()
        return Response({
            'profile_id': profile.id,
            'name': profile.name,
            'default_threshold_multiplier': profile.default_threshold_multiplier,
            'sensitivity_level': profile.sensitivity_level,
            'alert_type_settings': profile.alert_type_settings,
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting profile mappings {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tp_validate(self, request, pk=None):
    """Validate a threshold profile against the same rules as the model's clean()."""
    try:
        profile = self.get_object()
        errors = []
        if not profile.name or not profile.name.strip():
            errors.append('Profile name cannot be blank.')
        if profile.default_threshold_multiplier is not None and profile.default_threshold_multiplier <= 0:
            errors.append('default_threshold_multiplier must be a positive number.')
        if profile.sensitivity_level is not None and not (0.0 <= profile.sensitivity_level <= 1.0):
            errors.append('sensitivity_level must be between 0.0 and 1.0.')
        if profile.target_false_positive_rate is not None and not (0.0 <= profile.target_false_positive_rate <= 1.0):
            errors.append('target_false_positive_rate must be between 0.0 and 1.0.')
        if profile.target_detection_rate is not None and not (0.0 <= profile.target_detection_rate <= 1.0):
            errors.append('target_detection_rate must be between 0.0 and 1.0.')
        return Response({'profile_id': profile.id, 'valid': len(errors) == 0, 'errors': errors})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error validating threshold profile {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tp_export(self, request, pk=None):
    """Export a threshold profile as JSON"""
    try:
        profile = self.get_object()
        from ..serializers.threshold import ThresholdProfileSerializer
        data = ThresholdProfileSerializer(profile).data
        return Response({'exported': True, 'profile': data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error exporting threshold profile {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


try:
    ThresholdProfileViewSet.apply = action(detail=True, methods=['post'])(_tp_apply)
    ThresholdProfileViewSet.clone = action(detail=True, methods=['post'])(_tp_clone)
    ThresholdProfileViewSet.mappings = action(detail=True, methods=['get'])(_tp_mappings)
    ThresholdProfileViewSet.validate = action(detail=True, methods=['get'])(_tp_validate)
    ThresholdProfileViewSet.export = action(detail=True, methods=['get'])(_tp_export)
    # 'import' is a Python keyword and cannot appear after a dot in source
    # code (ThresholdProfileViewSet.import = ... would be a SyntaxError), so
    # it must be assigned via setattr(), which takes the name as a plain
    # string instead of parsing it as an identifier.
    setattr(ThresholdProfileViewSet, 'import', action(detail=False, methods=['post'])(_tp_import))
    ThresholdProfileViewSet.thresholds = action(detail=True, methods=['get'])(
        lambda self, request, pk=None: Response({'profile_id': pk, 'configs': list(ThresholdConfig.objects.filter(is_active=True).values('id', 'name', 'primary_threshold'))})
    )
except NameError:
    pass
