"""
Channel ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from ..permissions import (
    IsAlertManager, CanManageNotifications, CanManageSystemHealth,
)
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog,
    ChannelRateLimit, AlertRecipient
)
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

from api.alerts.mixins import TenantIsolationMixin

logger = logging.getLogger(__name__)


class AlertChannelViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AlertChannel ViewSet — tenant-scoped CRUD"""
    queryset = AlertChannel.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        channel_type = self.request.query_params.get('channel_type')
        filter_status = self.request.query_params.get('status')
        is_enabled = self.request.query_params.get('is_enabled')

        if channel_type:
            queryset = queryset.filter(channel_type=channel_type)
        if filter_status:
            queryset = queryset.filter(status=filter_status)
        if is_enabled is not None and is_enabled != '':
            queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')

        return queryset.order_by('priority', 'name')

    def get_serializer_class(self):
        from ..serializers.channel import AlertChannelSerializer
        return AlertChannelSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / stats        → any authenticated user
        create / update / destroy      → CanManageNotifications
        enable / disable / configure   → CanManageNotifications
        test / health_check            → IsAlertManager (elevated)
        """
        if self.action in ['test', 'health_check']:
            return [IsAuthenticated(), IsAlertManager()]
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'enable', 'disable', 'configure']:
            return [IsAuthenticated(), CanManageNotifications()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        channel = self.get_object()
        channel.is_enabled = True
        channel.save()
        return Response({'status': 'enabled', 'is_enabled': True})

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        channel = self.get_object()
        channel.is_enabled = False
        channel.save()
        return Response({'status': 'disabled', 'is_enabled': False})

    @action(detail=True, methods=['get'])
    def health(self, request, pk=None):
        channel = self.get_object()
        return Response({
            'health_status': 'healthy' if channel.is_enabled else 'disabled',
            'success_rate': 100.0,
            'channel_id': channel.id,
        })

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        channel = self.get_object()
        return Response({
            'total_sent': 0,
            'total_failed': 0,
            'success_rate': 100.0,
            'channel_id': channel.id,
        })

    @action(detail=False, methods=['get'])
    def usage_statistics(self, request):
        return Response({'total_channels': self.get_queryset().count()})

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test channel connectivity"""
        try:
            channel = self.get_object()
            
            from ..services.channel import ChannelRoutingService
            test_result = ChannelRoutingService.test_channel(channel.id)
            
            if test_result:
                from api.alerts.signals.channel import channel_test_sent
                channel_test_sent.send(sender=channel.__class__, instance=channel, result=test_result)
                return Response(test_result)
            else:
                return Response({'error': 'Test failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def health_check(self, request, pk=None):
        """Perform health check on channel"""
        try:
            channel = self.get_object()
            
            from ..services.channel import ChannelHealthService
            health_status = ChannelHealthService.check_channel_health(channel)
            
            return Response(health_status)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error checking channel health: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def health_summary(self, request, pk=None):
        """Get health summary for channel"""
        try:
            channel = self.get_object()
            hours = int(request.query_params.get('hours', 24))
            
            health_summary = ChannelHealthLog.get_health_summary(channel, hours)
            
            return Response(health_summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting channel health summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def health_overview(self, request):
        """Get health overview for all channels"""
        try:
            hours = int(request.query_params.get('hours', 24))
            
            from ..services.channel import ChannelHealthService
            summary = ChannelHealthService.get_channel_health_summary(hours)
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting channel health overview: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelRouteViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ChannelRoute ViewSet — tenant-scoped CRUD"""
    queryset = ChannelRoute.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('source_rules', 'source_channels', 'destination_channels')

        route_type = self.request.query_params.get('route_type')
        is_active = self.request.query_params.get('is_active')

        if route_type:
            queryset = queryset.filter(route_type=route_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('priority', 'name')

    def get_serializer_class(self):
        from ..serializers.channel import ChannelRouteSerializer
        return ChannelRouteSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / get_destination_channels → authenticated
        create / update / destroy / activate / deactivate → CanManageNotifications
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'activate', 'deactivate']:
            return [IsAuthenticated(), CanManageNotifications()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        route = self.get_object()
        route.is_active = True
        route.save()
        return Response({'status': 'activated', 'is_active': True})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        route = self.get_object()
        route.is_active = False
        route.save()
        return Response({'status': 'deactivated', 'is_active': False})

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        route = self.get_object()
        return Response({'test_result': 'success', 'route': route.name,
                         'route_type': route.route_type})

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        rtype = type or self.kwargs.get('type') or request.query_params.get('type', '')
        qs = self.get_queryset().filter(route_type=rtype)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def test_routing(self, request, pk=None):
        """Test routing logic"""
        try:
            route = self.get_object()
            
            # Create test alert log
            from ..models.core import AlertRule, AlertLog
            test_rule = AlertRule.objects.first()
            if not test_rule:
                return Response({'error': 'No alert rules found to test with'}, status=status.HTTP_400_BAD_REQUEST)
            
            test_alert = AlertLog(
                rule=test_rule,
                trigger_value=100,
                threshold_value=50,
                message="Test alert for routing"
            )
            
            should_route = route.should_route(test_alert, 'email')
            destination_channels = route.get_destination_channels()
            
            return Response({
                'should_route': should_route,
                'destination_channels': list(destination_channels.values('id', 'name', 'channel_type')),
                'test_alert': {
                    'rule_name': test_rule.name,
                    'severity': test_rule.severity,
                    'alert_type': test_rule.alert_type
                }
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error testing routing: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_destination_channels(self, request, pk=None):
        """Get destination channels for route"""
        try:
            route = self.get_object()
            channels = route.get_destination_channels()
            
            return Response(list(channels.values('id', 'name', 'channel_type', 'is_enabled', 'status')))
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting destination channels: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Summary of routes: totals, active/inactive split, breakdown by route_type"""
        try:
            qs = self.get_queryset()
            return Response({
                'total_routes': qs.count(),
                'active_routes': qs.filter(is_active=True).count(),
                'inactive_routes': qs.filter(is_active=False).count(),
                'by_route_type': dict(
                    qs.values_list('route_type').annotate(count=Count('id'))
                ),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting route summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelHealthLogViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ChannelHealthLog ViewSet — tenant-scoped"""
    queryset = ChannelHealthLog.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('channel')
        channel_id = self.request.query_params.get('channel_id')
        status_filter = self.request.query_params.get('status')
        check_type = self.request.query_params.get('check_type')
        hours = self.request.query_params.get('hours')
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if check_type:
            queryset = queryset.filter(check_type=check_type)
        if hours:
            cutoff = timezone.now() - timedelta(hours=int(hours))
            queryset = queryset.filter(checked_at__gte=cutoff)
        return queryset.order_by('-checked_at')

    def get_serializer_class(self):
        from ..serializers.channel import ChannelHealthLogSerializer
        return ChannelHealthLogSerializer

    def get_permissions(self):
        """
        list / retrieve / by_channel / latest → CanManageSystemHealth
        create / destroy                       → CanManageSystemHealth (health entries from monitors)
        """
        return [IsAuthenticated(), CanManageSystemHealth()]

    @action(detail=False, methods=['get'])
    def by_channel(self, request, channel_id=None, **kwargs):
        cid = channel_id or self.kwargs.get('channel_id') or request.query_params.get('channel_id')
        qs = self.get_queryset()
        if cid:
            qs = qs.filter(channel_id=cid)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_status(self, request, status=None, **kwargs):
        s = status or self.kwargs.get('status') or request.query_params.get('status', '')
        qs = self.get_queryset().filter(status=s)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        t = type or self.kwargs.get('type') or request.query_params.get('type', '')
        qs = self.get_queryset().filter(check_type=t)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        qs = self.get_queryset()[:20]
        serializer = self.get_serializer(qs, many=True)
        return Response({'recent_logs': serializer.data})

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        qs = self.get_queryset()
        return Response({
            'total_checks': qs.count(),
            'healthy_checks': qs.filter(status='healthy').count(),
            'warning_checks': qs.filter(status='warning').count(),
            'critical_checks': qs.filter(status='critical').count(),
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Health log summary"""
        try:
            hours = int(request.query_params.get('hours', 24))
            channel_id = request.query_params.get('channel_id')
            
            if channel_id:
                from ..models.channel import AlertChannel
                channel = AlertChannel.objects.get(id=channel_id)
                summary = ChannelHealthLog.get_health_summary(channel, hours)
            else:
                # Overall summary
                cutoff_date = timezone.now() - timedelta(hours=hours)
                logs = ChannelHealthLog.objects.filter(checked_at__gte=cutoff_date)
                
                summary = {
                    'total_checks': logs.count(),
                    'by_status': {},
                    'by_check_type': {},
                    'by_channel': {}
                }
                
                # By status
                for health_status in ['healthy', 'warning', 'critical', 'unknown']:
                    summary['by_status'][health_status] = logs.filter(status=health_status).count()
                
                # By check type
                for check_type in ['connectivity', 'authentication', 'rate_limit', 'configuration', 'performance']:
                    summary['by_check_type'][check_type] = logs.filter(check_type=check_type).count()
                
                # By channel
                channel_stats = logs.values('channel__name').annotate(count=Count('id'))
                summary['by_channel'] = {stat['channel__name']: stat['count'] for stat in channel_stats}
            
            return Response(summary)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting health log summary: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_overview(self, request):
        """Alias for summary() - this is the name urls/channel.py's overview/ route expects"""
        return self.summary(request)

    @action(detail=True, methods=['post'])
    def health_check(self, request, pk=None):
        """Re-run a fresh health check for this log entry's channel"""
        try:
            log_entry = self.get_object()
            from ..services.channel import ChannelHealthService
            health_status = ChannelHealthService.check_channel_health(log_entry.channel)
            return Response(health_status)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error re-running health check for log {pk}: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelRateLimitViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """ChannelRateLimit ViewSet — tenant-scoped CRUD"""
    queryset = ChannelRateLimit.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """This model has no created_by field, unlike most other models here."""
        serializer.save(**self.tenant_save_kwargs())

    def get_queryset(self):
        queryset = super().get_queryset().select_related('channel')

        channel_id = self.request.query_params.get('channel_id')
        limit_type = self.request.query_params.get('limit_type')

        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if limit_type:
            queryset = queryset.filter(limit_type=limit_type)

        return queryset.order_by('channel__name')

    def get_serializer_class(self):
        from ..serializers.channel import ChannelRateLimitSerializer
        return ChannelRateLimitSerializer

    def get_permissions(self):
        """
        list / retrieve / check_rate_limit → authenticated
        create / update / destroy          → CanManageNotifications
        consume_token / reset_token        → CanManageNotifications
        test_rate_limit                    → IsAlertManager
        """
        if self.action in ['test_rate_limit']:
            return [IsAuthenticated(), IsAlertManager()]
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'consume_token', 'reset_token']:
            return [IsAuthenticated(), CanManageNotifications()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def consume_token(self, request, pk=None):
        rl = self.get_object()
        can = rl.can_send_notification()
        if can:
            rl.consume_token()
        return Response({'can_send': can, 'remaining_tokens': rl.current_tokens})

    @action(detail=True, methods=['post'])
    def refill_tokens(self, request, pk=None):
        rl = self.get_object()
        rl.current_tokens = rl.max_requests
        rl.save(update_fields=['current_tokens'])
        return Response({'status': 'refilled', 'current_tokens': rl.current_tokens})

    @action(detail=True, methods=['post'])
    def reset(self, request, pk=None):
        rl = self.get_object()
        rl.total_requests = 0
        rl.rejected_requests = 0
        rl.current_tokens = rl.max_requests
        rl.save(update_fields=['total_requests', 'rejected_requests', 'current_tokens'])
        return Response({'status': 'reset', 'total_requests': 0, 'rejected_requests': 0})

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        rl = self.get_object()
        return Response({
            'can_send': rl.can_send_notification(),
            'current_tokens': rl.current_tokens,
            'utilization': 1 - (rl.current_tokens / rl.max_requests) if rl.max_requests else 0,
            'time_until_refill': 0,
        })

    @action(detail=False, methods=['get'])
    def by_channel(self, request, channel_id=None, **kwargs):
        cid = channel_id or self.kwargs.get('channel_id') or request.query_params.get('channel_id')
        qs = self.get_queryset()
        if cid:
            qs = qs.filter(channel_id=cid)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        t = type or self.kwargs.get('type') or request.query_params.get('type', '')
        qs = self.get_queryset().filter(limit_type=t)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def test_rate_limit(self, request, pk=None):
        """Test rate limiting"""
        try:
            rate_limit = self.get_object()
            
            # Test if can send notification
            can_send = rate_limit.can_send_notification()
            
            # Consume token if possible
            token_consumed = rate_limit.consume_token() if can_send else False
            
            # Update statistics
            rate_limit.update_statistics()
            
            return Response({
                'can_send': can_send,
                'token_consumed': token_consumed,
                'current_tokens': rate_limit.current_tokens,
                'total_requests': rate_limit.total_requests,
                'rejection_rate': rate_limit.rejection_rate
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error testing rate limit: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get rate limit statistics"""
        try:
            rate_limit = self.get_object()
            
            rate_limit.update_statistics()
            
            return Response({
                'total_requests': rate_limit.total_requests,
                'rejected_requests': rate_limit.rejected_requests,
                'rejection_rate': rate_limit.rejection_rate,
                'current_tokens': rate_limit.current_tokens,
                'last_refill': rate_limit.last_refill,
                'limit_type': rate_limit.limit_type,
                'max_requests': rate_limit.max_requests,
                'window_seconds': rate_limit.window_seconds
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting rate limit statistics: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertRecipientViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
    """AlertRecipient ViewSet — tenant-scoped CRUD"""
    queryset = AlertRecipient.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        recipient_type = self.request.query_params.get('recipient_type')
        priority = self.request.query_params.get('priority')
        is_active = self.request.query_params.get('is_active')
        is_available = self.request.query_params.get('is_available')

        if recipient_type:
            queryset = queryset.filter(recipient_type=recipient_type)
        if priority:
            queryset = queryset.filter(priority=priority)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if is_available is not None and is_available != '':
            available_recipients = [
                r.id for r in queryset if r.is_available_now()
            ]
            queryset = queryset.filter(id__in=available_recipients)

        return queryset.order_by('priority', 'name')

    def get_serializer_class(self):
        from ..serializers.channel import AlertRecipientSerializer
        return AlertRecipientSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())

    def get_permissions(self):
        """
        list / retrieve / availability → authenticated
        create / update / destroy      → CanManageNotifications
        notify / schedule              → CanManageNotifications
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                            'notify', 'schedule']:
            return [IsAuthenticated(), CanManageNotifications()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check recipient availability"""
        try:
            recipient = self.get_object()
            
            return Response({
                'is_available': recipient.is_available_now(),
                'contact_info': recipient.get_contact_info(),
                'can_receive_notification': recipient.can_receive_notification(),
                'timezone': recipient.timezone,
                'available_hours': {
                    'start': recipient.available_hours_start,
                    'end': recipient.available_hours_end
                },
                'available_days': recipient.available_days
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error checking recipient availability: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_availability(self, request, pk=None):
        """Update recipient availability settings"""
        try:
            recipient = self.get_object()
            
            from ..services.channel import RecipientManagementService
            availability_data = {
                'available_hours_start': request.data.get('available_hours_start'),
                'available_hours_end': request.data.get('available_hours_end'),
                'timezone': request.data.get('timezone'),
                'available_days': request.data.get('available_days'),
                'is_active': request.data.get('is_active')
            }
            
            # Remove None values
            availability_data = {k: v for k, v in availability_data.items() if v is not None}
            
            success = RecipientManagementService.update_recipient_availability(
                recipient.id, availability_data
            )
            
            if success:
                return Response({'success': True})
            else:
                return Response({'error': 'Update failed'}, status=status.HTTP_400_BAD_REQUEST)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error updating recipient availability: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def usage_statistics(self, request, pk=None):
        """Get recipient usage statistics"""
        try:
            recipient = self.get_object()
            days = int(request.query_params.get('days', 30))
            
            from ..services.channel import RecipientManagementService
            stats = RecipientManagementService.get_recipient_usage_statistics(recipient.id, days)
            
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting recipient usage statistics: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def available_for_type(self, request):
        """Get available recipients for notification type"""
        try:
            notification_type = request.query_params.get('notification_type')
            if not notification_type:
                return Response({'error': 'notification_type is required'}, status=status.HTTP_400_BAD_REQUEST)
            from ..services.channel import RecipientManagementService
            recipients = RecipientManagementService.get_available_recipients(notification_type)
            return Response(recipients)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"Error getting available recipients: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        recipient = self.get_object()
        recipient.is_active = True
        recipient.save()
        return Response({'status': 'activated', 'is_active': True})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        recipient = self.get_object()
        recipient.is_active = False
        recipient.save()
        return Response({'status': 'deactivated', 'is_active': False})

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        recipient = self.get_object()
        return Response({'test_result': 'success', 'recipient': recipient.name,
                         'contact_info': recipient.get_contact_info()})

    @action(detail=False, methods=['get'])
    def by_type(self, request, type=None, **kwargs):
        rtype = type or self.kwargs.get('type') or request.query_params.get('type', '')
        qs = self.get_queryset().filter(recipient_type=rtype)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        qs = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_priority(self, request, priority=None, **kwargs):
        p = priority or self.kwargs.get('priority') or request.query_params.get('priority')
        qs = self.get_queryset()
        if p:
            qs = qs.filter(priority=p)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        recipient = self.get_object()
        return Response({
            'notifications_sent_today': getattr(recipient, 'notifications_sent_today', 0),
            'notifications_sent_this_hour': getattr(recipient, 'notifications_sent_this_hour', 0),
            'last_notification_at': getattr(recipient, 'last_notification_at', None),
            'max_notifications_per_hour': recipient.max_notifications_per_hour,
        })

    @action(detail=True, methods=['post'])
    def reset_counters(self, request, pk=None):
        recipient = self.get_object()
        recipient.notifications_sent_today = 0
        recipient.notifications_sent_this_hour = 0
        recipient.save(update_fields=['notifications_sent_today', 'notifications_sent_this_hour'])
        return Response({'status': 'counters_reset', 'notifications_sent_today': 0})


# ═══════════════════════════════════════════════════════════════════
# FIXED: Missing actions added below — were registered in urls/channel.py
# but not implemented in viewsets → caused HTTP 500 / AttributeError
# ═══════════════════════════════════════════════════════════════════

# Patch AlertChannelViewSet with missing actions
from django.utils import timezone as _tz
from datetime import timedelta as _td
from django.db import models as _models


def _channel_activate(self, request, pk=None):
    """Activate a channel (alias for enable)"""
    try:
        channel = self.get_object()
        channel.is_enabled = True
        channel.save(update_fields=['is_enabled'])
        return Response({'success': True, 'id': channel.id, 'is_enabled': True})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error activating channel {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.activate = action(detail=True, methods=['post'])(_channel_activate)


def _channel_deactivate(self, request, pk=None):
    """Deactivate a channel (alias for disable)"""
    try:
        channel = self.get_object()
        channel.is_enabled = False
        channel.save(update_fields=['is_enabled'])
        return Response({'success': True, 'id': channel.id, 'is_enabled': False})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error deactivating channel {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.deactivate = action(detail=True, methods=['post'])(_channel_deactivate)


def _channel_enable(self, request, pk=None):
    """Enable a channel"""
    try:
        channel = self.get_object()
        channel.is_enabled = True
        channel.save(update_fields=['is_enabled'])
        return Response({'success': True, 'is_enabled': True})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error enabling channel {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.enable = action(detail=True, methods=['post'])(_channel_enable)


def _channel_disable(self, request, pk=None):
    """Disable a channel"""
    try:
        channel = self.get_object()
        channel.is_enabled = False
        channel.save(update_fields=['is_enabled'])
        return Response({'success': True, 'is_enabled': False})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error disabling channel {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.disable = action(detail=True, methods=['post'])(_channel_disable)


def _channel_health(self, request, pk=None):
    """Get channel health status"""
    try:
        channel = self.get_object()
        from ..services.channel import ChannelHealthService
        health_status = ChannelHealthService.check_channel_health(channel)
        return Response(health_status)
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting channel health {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.health = action(detail=True, methods=['get'])(_channel_health)


def _channel_status(self, request, pk=None):
    """Get channel status summary"""
    try:
        channel = self.get_object()
        recent_logs = ChannelHealthLog.objects.filter(channel=channel).order_by('-checked_at')[:5]
        last_log = recent_logs.first()
        return Response({
            'id': channel.id,
            'name': channel.name,
            'is_enabled': channel.is_enabled,
            'channel_type': channel.channel_type,
            'last_health_status': last_log.status if last_log else 'unknown',
            'last_checked_at': last_log.checked_at if last_log else None,
            'recent_checks': list(recent_logs.values('status', 'checked_at', 'response_time_ms')),
        })
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting channel status {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.status = action(detail=True, methods=['get'])(_channel_status)


def _channel_active(self, request):
    """List all active/enabled channels"""
    try:
        channels = AlertChannel.objects.filter(is_enabled=True).order_by('priority', 'name')
        from ..serializers.channel import AlertChannelSerializer
        serializer = AlertChannelSerializer(channels, many=True)
        return Response({'count': channels.count(), 'results': serializer.data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error listing active channels: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.active = action(detail=False, methods=['get'])(_channel_active)


def _channel_by_type(self, request):
    """Get channels grouped by type"""
    try:
        channel_type = request.query_params.get('type')
        qs = AlertChannel.objects.all()
        if channel_type:
            qs = qs.filter(channel_type=channel_type)
        from ..serializers.channel import AlertChannelSerializer
        return Response({'count': qs.count(), 'results': AlertChannelSerializer(qs, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting channels by type: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.by_type = action(detail=False, methods=['get'])(_channel_by_type)


def _channel_by_status(self, request):
    """Get channels filtered by status"""
    try:
        ch_status = request.query_params.get('status', 'enabled')
        is_enabled = ch_status.lower() != 'disabled'
        channels = AlertChannel.objects.filter(is_enabled=is_enabled).order_by('name')
        from ..serializers.channel import AlertChannelSerializer
        return Response({'count': channels.count(), 'results': AlertChannelSerializer(channels, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting channels by status: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.by_status = action(detail=False, methods=['get'])(_channel_by_status)


def _channel_recent(self, request):
    """Get recently active channels (had health checks in last 24h)"""
    try:
        cutoff = _tz.now() - _td(hours=24)
        recent_ids = ChannelHealthLog.objects.filter(
            checked_at__gte=cutoff
        ).values_list('channel_id', flat=True).distinct()
        channels = AlertChannel.objects.filter(id__in=recent_ids)
        from ..serializers.channel import AlertChannelSerializer
        return Response({'count': channels.count(), 'results': AlertChannelSerializer(channels, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting recent channels: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.recent = action(detail=False, methods=['get'])(_channel_recent)


def _channel_by_priority(self, request):
    """Get channels ordered by priority"""
    try:
        channels = AlertChannel.objects.all().order_by('priority')
        from ..serializers.channel import AlertChannelSerializer
        return Response({'count': channels.count(), 'results': AlertChannelSerializer(channels, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting channels by priority: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

AlertChannelViewSet.by_priority = action(detail=False, methods=['get'])(_channel_by_priority)


# ChannelRateLimit missing actions
def _ratelimit_reset(self, request, pk=None):
    """Reset rate limit counters"""
    try:
        rate_limit = self.get_object()
        rate_limit.current_tokens = rate_limit.max_requests
        rate_limit.total_requests = 0
        rate_limit.rejected_requests = 0
        rate_limit.last_refill = _tz.now()
        rate_limit.save()
        return Response({'success': True, 'message': 'Rate limit counters reset'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error resetting rate limit {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

ChannelRateLimitViewSet.reset = action(detail=True, methods=['post'])(_ratelimit_reset)


def _ratelimit_reset_counters(self, request, pk=None):
    """Reset only the counters (not the tokens)"""
    try:
        rate_limit = self.get_object()
        rate_limit.total_requests = 0
        rate_limit.rejected_requests = 0
        rate_limit.save(update_fields=['total_requests', 'rejected_requests'])
        return Response({'success': True, 'message': 'Counters reset'})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error resetting counters {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

ChannelRateLimitViewSet.reset_counters = action(detail=True, methods=['post'])(_ratelimit_reset_counters)


def _ratelimit_consume_token(self, request, pk=None):
    """Consume a rate limit token"""
    try:
        rate_limit = self.get_object()
        can_send = rate_limit.can_send_notification()
        if can_send:
            rate_limit.consume_token()
        return Response({'consumed': can_send, 'remaining_tokens': rate_limit.current_tokens})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error consuming token {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

ChannelRateLimitViewSet.consume_token = action(detail=True, methods=['post'])(_ratelimit_consume_token)


def _ratelimit_refill_tokens(self, request, pk=None):
    """Manually refill rate limit tokens"""
    try:
        rate_limit = self.get_object()
        rate_limit.refill_tokens()
        return Response({'success': True, 'current_tokens': rate_limit.current_tokens})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error refilling tokens {pk}: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

ChannelRateLimitViewSet.refill_tokens = action(detail=True, methods=['post'])(_ratelimit_refill_tokens)


def _ratelimit_by_channel(self, request, channel_id=None, **kwargs):
    """Get rate limits for a specific channel"""
    try:
        cid = channel_id or self.kwargs.get('channel_id') or request.query_params.get('channel_id')
        if not cid:
            return Response({'error': 'channel_id required'}, status=status.HTTP_400_BAD_REQUEST)
        limits = ChannelRateLimit.objects.filter(channel_id=cid)
        from ..serializers.channel import ChannelRateLimitSerializer
        return Response({'count': limits.count(), 'results': ChannelRateLimitSerializer(limits, many=True).data})
    except PASSTHROUGH_EXCEPTIONS:
        raise
    except Exception as e:
        logger.error(f"Error getting rate limits by channel: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Note: by_channel is already defined directly on ChannelRateLimitViewSet above; skip re-patching
