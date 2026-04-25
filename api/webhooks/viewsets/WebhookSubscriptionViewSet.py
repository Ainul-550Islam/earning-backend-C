"""Webhook Subscription ViewSet

This module contains the ViewSet for webhook subscription management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookSubscription, WebhookEndpoint
from ..serializers import (
    WebhookSubscriptionSerializer,
    WebhookSubscriptionCreateSerializer,
    WebhookSubscriptionUpdateSerializer,
    WebhookSubscriptionDetailSerializer,
    WebhookSubscriptionListSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookSubscriptionFilter


class WebhookSubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook subscription management."""
    
    queryset = WebhookSubscription.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookSubscriptionFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookSubscriptionCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return WebhookSubscriptionUpdateSerializer
        elif self.action == 'retrieve':
            return WebhookSubscriptionDetailSerializer
        elif self.action == 'list':
            return WebhookSubscriptionListSerializer
        else:
            return WebhookSubscriptionSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own subscriptions."""
        return super().get_queryset().filter(endpoint__owner=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a subscription."""
        subscription = self.get_object()
        subscription.is_active = True
        subscription.save()
        
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a subscription."""
        subscription = self.get_object()
        subscription.is_active = False
        subscription.save()
        
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get subscription statistics."""
        subscription = self.get_object()
        
        from ..models import WebhookDeliveryLog
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=subscription.endpoint,
            event_type=subscription.event_type
        )
        
        if deliveries.exists():
            total_count = deliveries.count()
            success_count = deliveries.filter(status='success').count()
            failed_count = deliveries.filter(status='failed').count()
            success_rate = (success_count / total_count) * 100
            
            # Get recent statistics
            from datetime import timedelta
            recent_deliveries = deliveries.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            )
            
            recent_success_rate = 0
            if recent_deliveries.exists():
                recent_success_count = recent_deliveries.filter(status='success').count()
                recent_success_rate = (recent_success_count / recent_deliveries.count()) * 100
        else:
            total_count = 0
            success_count = 0
            failed_count = 0
            success_rate = 0
            recent_success_rate = 0
        
        return Response({
            'total_deliveries': total_count,
            'successful_deliveries': success_count,
            'failed_deliveries': failed_count,
            'success_rate': round(success_rate, 2),
            'recent_success_rate': round(recent_success_rate, 2),
            'last_delivery': deliveries.order_by('-created_at').first().created_at if deliveries.exists() else None
        })
    
    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """Get recent deliveries for this subscription."""
        subscription = self.get_object()
        
        from ..models import WebhookDeliveryLog
        from ..serializers import WebhookDeliveryLogListSerializer
        
        deliveries = WebhookDeliveryLog.objects.filter(
            endpoint=subscription.endpoint,
            event_type=subscription.event_type
        ).order_by('-created_at')
        
        # Apply pagination
        page = self.paginate_queryset(deliveries)
        if page is not None:
            serializer = WebhookDeliveryLogListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = WebhookDeliveryLogListSerializer(deliveries, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test the subscription with a sample payload."""
        subscription = self.get_object()
        
        from ..services.core import DispatchService
        
        test_payload = {
            'test': True,
            'subscription_id': str(subscription.id),
            'timestamp': timezone.now().isoformat(),
            'event_type': subscription.event_type
        }
        
        try:
            dispatch_service = DispatchService()
            result = dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type=subscription.event_type,
                payload=test_payload
            )
            
            return Response({
                'success': result,
                'message': 'Test webhook sent successfully' if result else 'Test webhook failed',
                'payload': test_payload
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed to send test webhook'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get subscriptions by endpoint ID."""
        endpoint_id = request.query_params.get('endpoint_id')
        if not endpoint_id:
            return Response({
                'error': 'endpoint_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        subscriptions = self.queryset.filter(endpoint=endpoint)
        
        page = self.paginate_queryset(subscriptions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(subscriptions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_event_type(self, request):
        """Get subscriptions by event type."""
        event_type = request.query_params.get('event_type')
        if not event_type:
            return Response({
                'error': 'event_type parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        subscriptions = self.queryset.filter(event_type=event_type)
        
        page = self.paginate_queryset(subscriptions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(subscriptions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Activate multiple subscriptions."""
        subscription_ids = request.data.get('subscription_ids', [])
        if not subscription_ids:
            return Response({
                'error': 'subscription_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        subscriptions = self.queryset.filter(id__in=subscription_ids)
        updated_count = subscriptions.update(is_active=True)
        
        return Response({
            'message': f'Activated {updated_count} subscriptions',
            'updated_count': updated_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Deactivate multiple subscriptions."""
        subscription_ids = request.data.get('subscription_ids', [])
        if not subscription_ids:
            return Response({
                'error': 'subscription_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        subscriptions = self.queryset.filter(id__in=subscription_ids)
        updated_count = subscriptions.update(is_active=False)
        
        return Response({
            'message': f'Deactivated {updated_count} subscriptions',
            'updated_count': updated_count
        })
