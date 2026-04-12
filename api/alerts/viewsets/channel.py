"""
Channel ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
import logging

from ..models.channel import (
    AlertChannel, ChannelRoute, ChannelHealthLog, 
    ChannelRateLimit, AlertRecipient
)

logger = logging.getLogger(__name__)


class AlertChannelViewSet(viewsets.ModelViewSet):
    """AlertChannel ViewSet for CRUD operations"""
    queryset = AlertChannel.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        channel_type = self.request.query_params.get('channel_type')
        status = self.request.query_params.get('status')
        is_enabled = self.request.query_params.get('is_enabled')
        
        if channel_type:
            queryset = queryset.filter(channel_type=channel_type)
        if status:
            queryset = queryset.filter(status=status)
        if is_enabled is not None and is_enabled != '':
            queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')
        
        return queryset.order_by('priority', 'name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.channel import AlertChannelSerializer
        return AlertChannelSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def get_permissions(self):
        if self.action in ['test', 'health_check']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test channel connectivity"""
        try:
            channel = self.get_object()
            
            from ..services.channel import ChannelRoutingService
            test_result = ChannelRoutingService.test_channel(channel.id)
            
            if test_result:
                return Response(test_result)
            else:
                return Response({'error': 'Test failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def health_check(self, request, pk=None):
        """Perform health check on channel"""
        try:
            channel = self.get_object()
            
            from ..services.channel import ChannelHealthService
            health_status = ChannelHealthService.check_channel_health(channel)
            
            return Response(health_status)
        except Exception as e:
            logger.error(f"Error checking channel health: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def health_summary(self, request, pk=None):
        """Get health summary for channel"""
        try:
            channel = self.get_object()
            hours = int(request.query_params.get('hours', 24))
            
            health_summary = ChannelHealthLog.get_health_summary(channel, hours)
            
            return Response(health_summary)
        except Exception as e:
            logger.error(f"Error getting channel health summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def health_overview(self, request):
        """Get health overview for all channels"""
        try:
            hours = int(request.query_params.get('hours', 24))
            
            from ..services.channel import ChannelHealthService
            summary = ChannelHealthService.get_channel_health_summary(hours)
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting channel health overview: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelRouteViewSet(viewsets.ModelViewSet):
    """ChannelRoute ViewSet for CRUD operations"""
    queryset = ChannelRoute.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('source_rules', 'source_channels', 'destination_channels')
        
        # Apply filters
        route_type = self.request.query_params.get('route_type')
        is_active = self.request.query_params.get('is_active')
        
        if route_type:
            queryset = queryset.filter(route_type=route_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('priority', 'name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.channel import ChannelRouteSerializer
        return ChannelRouteSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
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
        except Exception as e:
            logger.error(f"Error testing routing: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def get_destination_channels(self, request, pk=None):
        """Get destination channels for route"""
        try:
            route = self.get_object()
            channels = route.get_destination_channels()
            
            return Response(list(channels.values('id', 'name', 'channel_type', 'is_enabled', 'status')))
        except Exception as e:
            logger.error(f"Error getting destination channels: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelHealthLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ChannelHealthLog ViewSet for viewing health logs"""
    queryset = ChannelHealthLog.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('channel')
        
        # Apply filters
        channel_id = self.request.query_params.get('channel_id')
        status = self.request.query_params.get('status')
        check_type = self.request.query_params.get('check_type')
        hours = self.request.query_params.get('hours')
        
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if status:
            queryset = queryset.filter(status=status)
        if check_type:
            queryset = queryset.filter(check_type=check_type)
        if hours:
            cutoff_date = timezone.now() - timedelta(hours=int(hours))
            queryset = queryset.filter(checked_at__gte=cutoff_date)
        
        return queryset.order_by('-checked_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.channel import ChannelHealthLogSerializer
        return ChannelHealthLogSerializer
    
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
                for status in ['healthy', 'warning', 'critical', 'unknown']:
                    summary['by_status'][status] = logs.filter(status=status).count()
                
                # By check type
                for check_type in ['connectivity', 'authentication', 'rate_limit', 'configuration', 'performance']:
                    summary['by_check_type'][check_type] = logs.filter(check_type=check_type).count()
                
                # By channel
                channel_stats = logs.values('channel__name').annotate(count=models.Count('id'))
                summary['by_channel'] = {stat['channel__name']: stat['count'] for stat in channel_stats}
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting health log summary: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChannelRateLimitViewSet(viewsets.ModelViewSet):
    """ChannelRateLimit ViewSet for CRUD operations"""
    queryset = ChannelRateLimit.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('channel')
        
        # Apply filters
        channel_id = self.request.query_params.get('channel_id')
        limit_type = self.request.query_params.get('limit_type')
        
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
        if limit_type:
            queryset = queryset.filter(limit_type=limit_type)
        
        return queryset.order_by('channel__name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.channel import ChannelRateLimitSerializer
        return ChannelRateLimitSerializer
    
    @action(detail=True, methods=['post'])
    def test_rate_limit(self, request, pk=None):
        """Test rate limiting"""
        try:
            rate_limit = self.get_object()
            
            # Test if can send notification
            can_send = rate_limit.can_send()
            
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
        except Exception as e:
            logger.error(f"Error testing rate limit: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting rate limit statistics: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertRecipientViewSet(viewsets.ModelViewSet):
    """AlertRecipient ViewSet for CRUD operations"""
    queryset = AlertRecipient.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
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
            available_recipients = []
            for recipient in queryset:
                if recipient.is_available_now():
                    available_recipients.append(recipient.id)
            queryset = queryset.filter(id__in=available_recipients)
        
        return queryset.order_by('priority', 'name')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.channel import AlertRecipientSerializer
        return AlertRecipientSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
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
        except Exception as e:
            logger.error(f"Error checking recipient availability: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error updating recipient availability: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def usage_statistics(self, request, pk=None):
        """Get recipient usage statistics"""
        try:
            recipient = self.get_object()
            days = int(request.query_params.get('days', 30))
            
            from ..services.channel import RecipientManagementService
            stats = RecipientManagementService.get_recipient_usage_statistics(recipient.id, days)
            
            return Response(stats)
        except Exception as e:
            logger.error(f"Error getting recipient usage statistics: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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
        except Exception as e:
            logger.error(f"Error getting available recipients: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
