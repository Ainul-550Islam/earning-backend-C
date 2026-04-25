"""Webhook Batch ViewSet

This module contains the ViewSet for webhook batch management.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookBatch, WebhookBatchItem, WebhookEndpoint
from ..serializers import (
    WebhookBatchSerializer,
    WebhookBatchCreateSerializer,
    WebhookBatchUpdateSerializer,
    WebhookBatchDetailSerializer,
    WebhookBatchListSerializer,
    WebhookBatchItemSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookBatchFilter


class WebhookBatchViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook batch management."""
    
    queryset = WebhookBatch.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookBatchFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookBatchCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return WebhookBatchUpdateSerializer
        elif self.action == 'retrieve':
            return WebhookBatchDetailSerializer
        elif self.action == 'list':
            return WebhookBatchListSerializer
        else:
            return WebhookBatchSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own batches."""
        return super().get_queryset().filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process a batch."""
        batch = self.get_object()
        
        if batch.status not in ['pending', 'failed']:
            return Response({
                'error': 'Only pending or failed batches can be processed',
                'status': batch.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from ..services.batch import BatchService
            batch_service = BatchService()
            
            result = batch_service.process_batch(batch)
            
            return Response({
                'success': result['success'],
                'batch_id': str(batch.id),
                'batch_id_display': batch.batch_id,
                'processed_count': result.get('processed_count', 0),
                'success_count': result.get('success_count', 0),
                'failed_count': result.get('failed_count', 0),
                'processing_time': result.get('processing_time', 0),
                'message': 'Batch processing completed' if result['success'] else 'Batch processing failed'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Batch processing failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a batch."""
        batch = self.get_object()
        
        if batch.status in ['completed', 'cancelled']:
            return Response({
                'error': 'Cannot cancel completed or cancelled batches',
                'status': batch.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from ..services.batch import BatchService
            batch_service = BatchService()
            
            result = batch_service.cancel_batch(batch, reason="Cancelled via API")
            
            return Response({
                'success': result['success'],
                'batch_id': str(batch.id),
                'batch_id_display': batch.batch_id,
                'message': 'Batch cancelled successfully' if result['success'] else 'Batch cancellation failed'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Batch cancellation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def retry_failed(self, request, pk=None):
        """Retry failed items in a batch."""
        batch = self.get_object()
        
        if batch.status != 'completed':
            return Response({
                'error': 'Can only retry failed items in completed batches',
                'status': batch.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from ..services.batch import BatchService
            batch_service = BatchService()
            
            result = batch_service.retry_batch(batch)
            
            return Response({
                'success': result['success'],
                'batch_id': str(batch.id),
                'batch_id_display': batch.batch_id,
                'retry_count': result.get('retry_count', 0),
                'message': 'Failed items retry initiated' if result['success'] else 'Failed items retry failed'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed items retry failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get items in a batch."""
        batch = self.get_object()
        
        items = batch.items.all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            items = items.filter(status=status_filter)
        
        # Apply pagination
        page = self.paginate_queryset(items)
        if page is not None:
            serializer = WebhookBatchItemSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = WebhookBatchItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get batch statistics."""
        batch = self.get_object()
        
        items = batch.items.all()
        
        total_items = items.count()
        pending_items = items.filter(status='pending').count()
        processing_items = items.filter(status='processing').count()
        completed_items = items.filter(status='completed').count()
        failed_items = items.filter(status='failed').count()
        cancelled_items = items.filter(status='cancelled').count()
        
        success_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        # Get processing statistics
        processing_time = 0
        if batch.started_at and batch.completed_at:
            processing_time = (batch.completed_at - batch.started_at).total_seconds()
        
        return Response({
            'batch_id': str(batch.id),
            'batch_id_display': batch.batch_id,
            'status': batch.status,
            'total_items': total_items,
            'pending_items': pending_items,
            'processing_items': processing_items,
            'completed_items': completed_items,
            'failed_items': failed_items,
            'cancelled_items': cancelled_items,
            'success_rate': round(success_rate, 2),
            'processing_time': processing_time,
            'created_at': batch.created_at,
            'started_at': batch.started_at,
            'completed_at': batch.completed_at
        })
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get batch processing progress."""
        batch = self.get_object()
        
        items = batch.items.all()
        total_items = items.count()
        completed_items = items.filter(status='completed').count()
        failed_items = items.filter(status='failed').count()
        
        progress_percentage = (completed_items / total_items * 100) if total_items > 0 else 0
        
        # Estimate remaining time
        estimated_remaining_time = None
        if batch.status == 'processing' and completed_items > 0:
            elapsed_time = (timezone.now() - batch.started_at).total_seconds()
            avg_time_per_item = elapsed_time / completed_items
            remaining_items = total_items - completed_items
            estimated_remaining_time = avg_time_per_item * remaining_items
        
        return Response({
            'batch_id': str(batch.id),
            'batch_id_display': batch.batch_id,
            'status': batch.status,
            'total_items': total_items,
            'completed_items': completed_items,
            'failed_items': failed_items,
            'progress_percentage': round(progress_percentage, 2),
            'estimated_remaining_time': round(estimated_remaining_time, 2) if estimated_remaining_time else None,
            'started_at': batch.started_at,
            'completed_at': batch.completed_at
        })
    
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get batches by status."""
        status_filter = request.query_params.get('status')
        if status_filter:
            batches = self.queryset.filter(status=status_filter)
        else:
            batches = self.queryset
        
        page = self.paginate_queryset(batches)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get batches by endpoint."""
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
        
        batches = self.queryset.filter(endpoint=endpoint)
        
        page = self.paginate_queryset(batches)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent batches."""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        batches = self.queryset.filter(created_at__gte=since)
        
        page = self.paginate_queryset(batches)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_cancel(self, request):
        """Cancel multiple batches."""
        batch_ids = request.data.get('batch_ids', [])
        if not batch_ids:
            return Response({
                'error': 'batch_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        batches = self.queryset.filter(
            id__in=batch_ids,
            status__in=['pending', 'processing', 'failed']
        )
        
        cancelled_count = 0
        from ..services.batch import BatchService
        batch_service = BatchService()
        
        for batch in batches:
            try:
                result = batch_service.cancel_batch(batch, reason="Bulk cancelled via API")
                if result['success']:
                    cancelled_count += 1
            except Exception as e:
                continue
        
        return Response({
            'message': f'Cancelled {cancelled_count} batches',
            'cancelled_count': cancelled_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_process(self, request):
        """Process multiple batches."""
        batch_ids = request.data.get('batch_ids', [])
        if not batch_ids:
            return Response({
                'error': 'batch_ids parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        batches = self.queryset.filter(
            id__in=batch_ids,
            status__in=['pending', 'failed']
        )
        
        processed_count = 0
        from ..services.batch import BatchService
        batch_service = BatchService()
        
        for batch in batches:
            try:
                result = batch_service.process_batch(batch)
                if result['success']:
                    processed_count += 1
            except Exception as e:
                continue
        
        return Response({
            'message': f'Processed {processed_count} batches',
            'processed_count': processed_count
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall batch statistics."""
        batches = self.queryset
        
        total_batches = batches.count()
        pending_batches = batches.filter(status='pending').count()
        processing_batches = batches.filter(status='processing').count()
        completed_batches = batches.filter(status='completed').count()
        failed_batches = batches.filter(status='failed').count()
        cancelled_batches = batches.filter(status='cancelled').count()
        
        # Get item statistics
        from ..models import WebhookBatchItem
        
        total_items = WebhookBatchItem.objects.filter(batch__in=batches).count()
        completed_items = WebhookBatchItem.objects.filter(
            batch__in=batches,
            status='completed'
        ).count()
        
        success_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        return Response({
            'total_batches': total_batches,
            'pending_batches': pending_batches,
            'processing_batches': processing_batches,
            'completed_batches': completed_batches,
            'failed_batches': failed_batches,
            'cancelled_batches': cancelled_batches,
            'total_items': total_items,
            'completed_items': completed_items,
            'success_rate': round(success_rate, 2)
        })
