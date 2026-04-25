"""Webhook Endpoint ViewSet

This viewset handles webhook endpoint CRUD operations
including secret rotation, testing, and status management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as filters

from ...models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ...serializers import (
    WebhookEndpointSerializer, WebhookSubscriptionSerializer,
    WebhookDeliveryLogSerializer, WebhookEmitSerializer, WebhookTestSerializer
)
from ...services.core import DispatchService
from ...services.core import SecretRotationService
from ...services.analytics import HealthMonitorService
from ...choices import WebhookStatus


class WebhookEndpointFilter(filters.FilterSet):
    """Filter set for webhook endpoints."""
    
    status = filters.ChoiceFilter(
        choices=WebhookStatus.CHOICES,
        label=_('Status')
    )
    
    url = filters.CharFilter(
        lookup_expr='icontains',
        label=_('URL')
    )
    
    created_at = filters.DateTimeFromToRangeFilter(
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookEndpoint
        fields = ['status', 'url', 'created_at']


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook endpoint CRUD operations.
    Provides full CRUD functionality with additional actions.
    """
    
    queryset = WebhookEndpoint.objects.all()
    serializer_class = WebhookEndpointSerializer
    filterset_class = WebhookEndpointFilter
    lookup_field = 'id'
    
    def get_permissions(self):
        """Get permissions based on action."""
        if self.action in ['create', 'partial_update', 'update', 'destroy']:
            return ['webhooks.add_webhook_endpoint']
        return ['webhooks.view_webhook_endpoint']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'test':
            return WebhookTestSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'], url_path='test')
    def test(self, request, pk=None):
        """Test webhook endpoint with custom payload."""
        endpoint = self.get_object()
        
        serializer = self.get_serializer_class()
        serializer.is_valid(raise_exception=True)
        
        # Send test webhook
        dispatch_service = DispatchService()
        success = dispatch_service.emit(
            endpoint=endpoint,
            event_type=serializer.validated_data['event_type'],
            payload=serializer.validated_data['payload'],
            delivery_log=None,  # Create new delivery log
        )
        
        if success:
            return Response({
                'success': True,
                'message': _('Test webhook sent successfully'),
                'delivery_log_id': delivery_log.id if delivery_log else None,
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': _('Failed to send test webhook'),
                'error': str(success.error) if success.error else _('Unknown error'),
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='rotate-secret')
    def rotate_secret(self, request, pk=None):
        """Rotate webhook endpoint secret."""
        endpoint = self.get_object()
        
        rotation_service = SecretRotationService()
        success = rotation_service.rotate_secret(endpoint)
        
        if success:
            return Response({
                'success': True,
                'message': _('Secret rotated successfully'),
                'new_secret_hash': success.get('new_secret_hash'),
                'old_secret_expires_at': success.get('old_secret_expires_at'),
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': _('Failed to rotate secret'),
                'error': str(success.error) if success.error else _('Unknown error'),
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Pause webhook endpoint."""
        endpoint = self.get_object()
        
        if endpoint.status == WebhookStatus.PAUSED:
            return Response({
                'success': False,
                'message': _('Endpoint is already paused'),
            }, status=status.HTTP_400_BAD_REQUEST)
        
        endpoint.status = WebhookStatus.PAUSED
        endpoint.save()
        
        return Response({
            'success': True,
            'message': _('Endpoint paused successfully'),
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        """Resume webhook endpoint."""
        endpoint = self.get_object()
        
        if endpoint.status != WebhookStatus.PAUSED:
            return Response({
                'success': False,
                'message': _('Endpoint is not paused'),
            }, status=status.HTTP_400_BAD_REQUEST)
        
        endpoint.status = WebhookStatus.ACTIVE
        endpoint.save()
        
        return Response({
            'success': True,
            'message': _('Endpoint resumed successfully'),
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def health_status(self, request, pk=None):
        """Get health status of webhook endpoint."""
        endpoint = self.get_object()
        
        health_service = HealthMonitorService()
        health_summary = health_service.get_endpoint_health_summary(endpoint, hours=24)
        
        return Response({
            'success': True,
            'data': health_summary,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def delivery_logs(self, request, pk=None):
        """Get delivery logs for webhook endpoint."""
        endpoint = self.get_object()
        
        # Get recent delivery logs
        logs = WebhookDeliveryLog.objects.filter(
            endpoint=endpoint
        ).order_by('-created_at')[:100]  # Last 100 logs
        
        serializer = WebhookDeliveryLogSerializer(logs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def subscriptions(self, request, pk=None):
        """Get subscriptions for webhook endpoint."""
        endpoint = self.get_object()
        
        subscriptions = endpoint.subscriptions.filter(is_active=True)
        serializer = WebhookSubscriptionSerializer(subscriptions, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
    
    def perform_create(self, serializer):
        """Create webhook endpoint with user assignment."""
        serializer.save(created_by=self.request.user)
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_201_CREATED)
    
    def perform_update(self, serializer):
        """Update webhook endpoint."""
        serializer.save(updated_at=timezone.now())
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
