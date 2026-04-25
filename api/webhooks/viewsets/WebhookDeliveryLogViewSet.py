"""Webhook Delivery Log ViewSet

This module contains the ViewSet for webhook delivery log management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookDeliveryLog, WebhookEndpoint
from ..serializers import (
    WebhookDeliveryLogSerializer,
    WebhookDeliveryLogListSerializer,
    WebhookDeliveryLogDetailSerializer,
    WebhookDeliveryLogStatsSerializer,
    WebhookDeliveryLogRetrySerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookDeliveryLogFilter


class WebhookDeliveryLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for webhook delivery log management (read-only)."""
    
    queryset = WebhookDeliveryLog.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookDeliveryLogFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'retrieve':
            return WebhookDeliveryLogDetailSerializer
        elif self.action == 'list':
            return WebhookDeliveryLogListSerializer
        else:
            return WebhookDeliveryLogSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own delivery logs."""
        return super().get_queryset().filter(endpoint__owner=self.request.user)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed delivery."""
        delivery_log = self.get_object()
        
        if delivery_log.status != 'failed':
            return Response({
                'error': 'Only failed deliveries can be retried',
                'status': delivery_log.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if delivery_log.attempt_number >= delivery_log.max_attempts:
            return Response({
                'error': 'Maximum retry attempts exceeded',
                'attempt_number': delivery_log.attempt_number,
                'max_attempts': delivery_log.max_attempts
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = WebhookDeliveryLogRetrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from ..services.core import DispatchService
        
        try:
            dispatch_service = DispatchService()
            result = dispatch_service.retry_delivery(delivery_log)
            
            return Response({
                'success': result,
                'message': 'Delivery retry initiated' if result else 'Delivery retry failed',
                'delivery_log_id': str(delivery_log.id)
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed to retry delivery'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Get detailed information about a delivery log."""
        delivery_log = self.get_object()
        
        # Get detailed payload and response
        payload = delivery_log.payload
        headers = delivery_log.request_headers
        response_body = delivery_log.response_body
        
        return Response({
            'id': str(delivery_log.id),
            'endpoint': {
                'id': str(delivery_log.endpoint.id),
                'label': delivery_log.endpoint.label,
                'url': delivery_log.endpoint.url
            },
            'event_type': delivery_log.event_type,
            'payload': payload,
            'headers': headers,
            'signature': delivery_log.signature,
            'http_status_code': delivery_log.http_status_code,
            'response_body': response_body,
            'duration_ms': delivery_log.duration_ms,
            'error_message': delivery_log.error_message,
            'status': delivery_log.status,
            'attempt_number': delivery_log.attempt_number,
            'max_attempts': delivery_log.max_attempts,
            'next_retry_at': delivery_log.next_retry_at,
            'dispatched_at': delivery_log.dispatched_at,
            'completed_at': delivery_log.completed_at,
            'created_at': delivery_log.created_at,
            'updated_at': delivery_log.updated_at
        })
    
    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        """Get timeline of delivery attempts."""
        delivery_log = self.get_object()
        
        # Get all delivery logs for the same original request
        all_attempts = WebhookDeliveryLog.objects.filter(
            endpoint=delivery_log.endpoint,
            event_type=delivery_log.event_type,
            created_at__gte=delivery_log.created_at - timezone.timedelta(hours=1)
        ).order_by('created_at')
        
        timeline = []
        for attempt in all_attempts:
            timeline.append({
                'id': str(attempt.id),
                'attempt_number': attempt.attempt_number,
                'status': attempt.status,
                'http_status_code': attempt.http_status_code,
                'duration_ms': attempt.duration_ms,
                'error_message': attempt.error_message,
                'created_at': attempt.created_at,
                'completed_at': attempt.completed_at
            })
        
        return Response({
            'delivery_log_id': str(delivery_log.id),
            'timeline': timeline
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get delivery log statistics."""
        queryset = self.get_queryset()
        
        # Get overall statistics
        total_count = queryset.count()
        success_count = queryset.filter(status='success').count()
        failed_count = queryset.filter(status='failed').count()
        pending_count = queryset.filter(status='pending').count()
        retrying_count = queryset.filter(status='retrying').count()
        
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        # Get performance statistics
        successful_deliveries = queryset.filter(status='success')
        if successful_deliveries.exists():
            avg_response_time = successful_deliveries.aggregate(
                models.Avg('duration_ms')
            )['duration_ms__avg'] or 0
            
            min_response_time = successful_deliveries.aggregate(
                models.Min('duration_ms')
            )['duration_ms__min'] or 0
            
            max_response_time = successful_deliveries.aggregate(
                models.Max('duration_ms')
            )['duration_ms__max'] or 0
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
        
        return Response({
            'total_count': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'pending_count': pending_count,
            'retrying_count': retrying_count,
            'success_rate': round(success_rate, 2),
            'avg_response_time_ms': round(avg_response_time, 2),
            'min_response_time_ms': min_response_time,
            'max_response_time_ms': max_response_time
        })
    
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get delivery logs grouped by status."""
        queryset = self.get_queryset()
        
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get delivery logs by endpoint."""
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
        
        queryset = self.get_queryset().filter(endpoint=endpoint)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_event_type(self, request):
        """Get delivery logs by event type."""
        event_type = request.query_params.get('event_type')
        if not event_type:
            return Response({
                'error': 'event_type parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(event_type=event_type)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent delivery logs."""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        queryset = self.get_queryset().filter(created_at__gte=since)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def failed(self, request):
        """Get failed delivery logs."""
        queryset = self.get_queryset().filter(status='failed')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def retryable(self, request):
        """Get delivery logs that can be retried."""
        queryset = self.get_queryset().filter(
            status='failed',
            attempt_number__lt=models.F('max_attempts')
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_retry(self, request):
        """Retry multiple failed deliveries."""
        delivery_log_ids = request.data.get('delivery_log_ids', [])
        if not delivery_log_ids:
            return Response({
                'error': 'delivery_log_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(
            id__in=delivery_log_ids,
            status='failed',
            attempt_number__lt=models.F('max_attempts')
        )
        
        retry_count = 0
        success_count = 0
        failed_count = 0
        
        from ..services.core import DispatchService
        
        for delivery_log in queryset:
            try:
                dispatch_service = DispatchService()
                result = dispatch_service.retry_delivery(delivery_log)
                retry_count += 1
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
        
        return Response({
            'message': f'Processed {retry_count} delivery logs',
            'retry_count': retry_count,
            'success_count': success_count,
            'failed_count': failed_count
        })
