"""Webhook Replay ViewSet

This viewset handles webhook replay operations
including batch creation, status tracking, and progress monitoring.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ...models import (
    WebhookReplay, WebhookReplayBatch, WebhookDeliveryLog
)
from ...serializers import (
    WebhookReplaySerializer, WebhookReplayBatchSerializer,
    WebhookDeliveryLogSerializer
)
from ...services.replay import ReplayService
from ...constants import ReplayStatus


class WebhookReplayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook replay CRUD operations.
    Provides comprehensive replay functionality with batch management.
    """
    
    queryset = WebhookReplay.objects.all()
    serializer_class = WebhookReplaySerializer
    lookup_field = 'id'
    
    def get_permissions(self):
        """Get permissions for replay viewset."""
        if self.action in ['create', 'list', 'retrieve']:
            return ['webhooks.manage_webhook_replay']
        return ['webhooks.view_webhook_replay']
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'create_batch':
            return WebhookReplayBatchSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'], url_path='create-batch')
    def create_batch(self, request):
        """Create a new replay batch."""
        event_type = request.data.get('event_type')
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        batch_size = request.data.get('batch_size', 100)
        user_id = request.user.id if request.user.is_authenticated else None
        
        serializer = self.get_serializer_class()
        serializer.is_valid(raise_exception=True)
        
        replay_service = ReplayService()
        result = replay_service.create_replay_batch(
            event_type=event_type,
            from_date=date_from,
            to_date=date_to,
            batch_size=batch_size,
            user_id=user_id,
        )
        
        if result['batch']:
            return Response({
                'success': True,
                'data': serializer.data,
                'batch_id': result['batch'].batch_id,
                'message': _('Replay batch created successfully'),
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': _('Failed to create replay batch'),
                'errors': result.get('errors', {}),
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], url_path='start-batch')
    def start_batch(self, request, pk=None):
        """Start processing a replay batch."""
        batch_id = request.data.get('batch_id')
        
        try:
            replay_service = ReplayService()
            batch = get_object_or_404(WebhookReplayBatch, batch_id=batch_id)
            
            success = replay_service.start_batch_processing(batch)
            
            if success:
                return Response({
                    'success': True,
                    'message': _('Batch processing started'),
                    'batch_id': batch.batch_id,
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': _('Failed to start batch processing'),
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except WebhookReplayBatch.DoesNotExist:
            return Response({
                'success': False,
                'message': _('Replay batch not found'),
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'], url_path='batch-progress')
    def batch_progress(self, request, pk=None):
        """Get progress of a replay batch."""
        batch_id = request.query_params.get('batch_id')
        
        try:
            replay_service = ReplayService()
            batch = replay_service.get_batch_status(batch_id)
            
            if not batch:
                return Response({
                    'success': False,
                    'message': _('Replay batch not found'),
                }, status=status.HTTP_404_NOT_FOUND)
            
            progress = replay_service.get_batch_progress(batch_id)
            
            return Response({
                'success': True,
                'data': progress,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': _('Failed to get batch progress'),
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='batch-status')
    def batch_status(self, request, pk=None):
        """Get detailed status of a replay batch."""
        batch_id = request.query_params.get('batch_id')
        
        try:
            replay_service = ReplayService()
            batch = replay_service.get_batch_status(batch_id)
            
            if not batch:
                return Response({
                    'success': False,
                    'message': _('Replay batch not found'),
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get batch items with status
            batch_items = WebhookReplay.objects.filter(batch_id=batch_id)
            
            status_counts = {}
            for item in batch_items:
                status = item.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return Response({
                'success': True,
                'data': {
                    'batch_id': batch.batch_id,
                    'event_type': batch.event_type,
                    'status': batch.status,
                    'total_items': batch_items.count(),
                    'status_counts': status_counts,
                    'created_at': batch.created_at,
                    'updated_at': batch.updated_at,
                    'completed_at': batch.completed_at,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': _('Failed to get batch status'),
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='cancel-batch')
    def cancel_batch(self, request, pk=None):
        """Cancel a replay batch."""
        batch_id = request.data.get('batch_id')
        reason = request.data.get('reason', _('User cancellation'))
        
        try:
            replay_service = ReplayService()
            batch = get_object_or_404(WebhookReplayBatch, batch_id=batch_id)
            
            success = replay_service.cancel_batch(batch, reason)
            
            if success:
                return Response({
                    'success': True,
                    'message': _('Batch cancelled successfully'),
                    'batch_id': batch.batch_id,
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': _('Failed to cancel batch'),
                    'errors': result.get('errors', {}),
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except WebhookReplayBatch.DoesNotExist:
            return Response({
                'success': False,
                'message': _('Replay batch not found'),
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def replay_history(self, request):
        """Get replay history for a user or event type."""
        event_type = request.query_params.get('event_type')
        user_id = request.user.id if request.user.is_authenticated else None
        
        queryset = WebhookReplay.objects.all()
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        if user_id:
            queryset = queryset.filter(replayed_by=user_id)
        
        queryset = queryset.order_by('-created_at')
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        serializer = WebhookReplaySerializer(page.object_list, many=True)
        
        return self.get_paginated_response(serializer)
    
    @action(detail=True, methods=['get'])
    def replay_statistics(self, request):
        """Get replay statistics."""
        from django.utils import timezone
        from django.db.models import Count, Avg, Sum
        
        # Get statistics
        stats = WebhookReplay.objects.aggregate(
            total_replays=Count('id'),
            completed_replays=Count('id', filter=Q(status=ReplayStatus.COMPLETED)),
            failed_replays=Count('id', filter=Q(status=ReplayStatus.FAILED)),
            avg_completion_time=Avg('completed_at', filter=Q(status=ReplayStatus.COMPLETED)),
        )
        
        return Response({
            'success': True,
            'data': {
                'total_replays': stats['total_replays'],
                'completed_replays': stats['completed_replays'],
                'failed_replays': stats['failed_replays'],
                'success_rate': (
                    (stats['completed_replays'] / stats['total_replays'] * 100
                    if stats['total_replays'] > 0 else 0
                ),
                'avg_completion_time_hours': stats['avg_completion_time'],
                'generated_at': timezone.now(),
            }
        }, status=status.HTTP_200_OK)
