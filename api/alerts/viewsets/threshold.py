"""
Threshold ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
import logging

from ..models.threshold import (
    ThresholdConfig, ThresholdBreach, AdaptiveThreshold, 
    ThresholdHistory, ThresholdProfile
)

logger = logging.getLogger(__name__)


class ThresholdConfigViewSet(viewsets.ModelViewSet):
    """ThresholdConfig ViewSet for CRUD operations"""
    queryset = ThresholdConfig.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('alert_rule')
        
        # Apply filters
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
        # Will be defined in serializers
        from ..serializers.threshold import ThresholdConfigSerializer
        return ThresholdConfigSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
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
        except Exception as e:
            logger.error(f"Error calculating threshold: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error evaluating threshold condition: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdBreachViewSet(viewsets.ModelViewSet):
    """ThresholdBreach ViewSet for CRUD operations"""
    queryset = ThresholdBreach.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('threshold_config', 'alert_log')
        
        # Apply filters
        severity = self.request.query_params.get('severity')
        threshold_config_id = self.request.query_params.get('threshold_config_id')
        is_resolved = self.request.query_params.get('is_resolved')
        
        if severity:
            queryset = queryset.filter(severity=severity)
        if threshold_config_id:
            queryset = queryset.filter(threshold_config_id=threshold_config_id)
        if is_resolved is not None and is_resolved != '':
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        return queryset.order_by('-detected_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.threshold import ThresholdBreachSerializer
        return ThresholdBreachSerializer
    
    def get_permissions(self):
        if self.action in ['acknowledge', 'resolve']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge threshold breach"""
        try:
            breach = self.get_object()
            notes = request.data.get('notes', '')
            
            breach.acknowledge(request.user, notes)
            
            return Response({'success': True, 'acknowledged_at': breach.acknowledged_at})
        except Exception as e:
            logger.error(f"Error acknowledging breach: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve threshold breach"""
        try:
            breach = self.get_object()
            notes = request.data.get('notes', '')
            
            breach.resolve(request.user, notes)
            
            return Response({'success': True, 'resolved_at': breach.resolved_at})
        except Exception as e:
            logger.error(f"Error resolving breach: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
                'resolved_breaches': breaches.filter(is_resolved=True).count(),
                'unresolved_breaches': breaches.filter(is_resolved=False).count(),
                'by_severity': {},
                'average_duration': 0
            }
            
            # By severity
            for severity in ['low', 'medium', 'high', 'critical']:
                stats['by_severity'][severity] = breaches.filter(severity=severity).count()
            
            # Average duration
            resolved_breaches = breaches.filter(is_resolved=True)
            if resolved_breaches.exists():
                total_duration = sum(
                    (breach.resolved_at - breach.detected_at).total_seconds() / 60
                    for breach in resolved_breaches
                )
                stats['average_duration'] = total_duration / resolved_breaches.count()
            
            return Response(stats)
        except Exception as e:
            logger.error(f"Error getting breach stats: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdaptiveThresholdViewSet(viewsets.ModelViewSet):
    """AdaptiveThreshold ViewSet for CRUD operations"""
    queryset = AdaptiveThreshold.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('threshold_config')
        
        # Apply filters
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
        # Will be defined in serializers
        from ..serializers.threshold import AdaptiveThresholdSerializer
        return AdaptiveThresholdSerializer
    
    def get_permissions(self):
        if self.action in ['adapt_threshold', 'update_cache']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def adapt_threshold(self, request, pk=None):
        """Manually trigger threshold adaptation"""
        try:
            adaptive_threshold = self.get_object()
            
            adaptive_threshold.adapt_threshold()
            
            return Response({
                'success': True,
                'current_threshold': adaptive_threshold.current_threshold,
                'adaptation_count': adaptive_threshold.adaptation_count,
                'adapted_at': adaptive_threshold.last_adaptation
            })
        except Exception as e:
            logger.error(f"Error adapting threshold: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_cache(self, request, pk=None):
        """Update threshold cache"""
        try:
            adaptive_threshold = self.get_object()
            adaptive_threshold.update_cache()
            
            return Response({'success': True, 'cache_updated_at': timezone.now()})
        except Exception as e:
            logger.error(f"Error updating cache: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting adaptation history: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ThresholdHistory ViewSet for viewing history"""
    queryset = ThresholdHistory.objects.all()
    permission_classes = [IsAuthenticated]
    
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
        except Exception as e:
            logger.error(f"Error getting threshold history summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThresholdProfileViewSet(viewsets.ModelViewSet):
    """ThresholdProfile ViewSet for CRUD operations"""
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
        if self.action in ['apply_to_config']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def apply_to_config(self, request, pk=None):
        """Apply profile to threshold configuration"""
        try:
            profile = self.get_object()
            threshold_config_id = request.data.get('threshold_config_id')
            
            if not threshold_config_id:
                return Response({'error': 'threshold_config_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            from ..models.threshold import ThresholdConfig
            threshold_config = ThresholdConfig.objects.get(id=threshold_config_id)
            
            updated_config = profile.apply_to_threshold_config(threshold_config)
            
            return Response({
                'success': True,
                'threshold_config_id': updated_config.id,
                'primary_threshold': updated_config.primary_threshold,
                'secondary_threshold': updated_config.secondary_threshold
            })
        except ThresholdConfig.DoesNotExist:
            return Response({'error': 'Threshold configuration not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error applying profile: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting effective settings: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error listing available profiles: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
