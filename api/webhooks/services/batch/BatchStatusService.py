"""Batch Status Service

This module provides batch completion tracking and status management.
"""

import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q

from ...models import WebhookBatch, WebhookBatchItem
from ...constants import BatchStatus

logger = logging.getLogger(__name__)


class BatchStatusService:
    """Service for tracking batch completion and managing batch status."""
    
    def __init__(self):
        """Initialize the batch status service."""
        self.logger = logger
    
    def update_batch_status(self, batch: WebhookBatch, status: str, error_message: str = None) -> bool:
        """
        Update the status of a batch.
        
        Args:
            batch: The batch to update
            status: The new status
            error_message: Optional error message
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Validate status transition
                if not self._is_valid_status_transition(batch.status, status):
                    self.logger.error(f"Invalid status transition from {batch.status} to {status}")
                    return False
                
                # Update batch
                batch.status = status
                if error_message:
                    batch.error_message = error_message
                
                # Update timestamps based on status
                if status == BatchStatus.PROCESSING and not batch.started_at:
                    batch.started_at = timezone.now()
                elif status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED, BatchStatus.FAILED] and not batch.completed_at:
                    batch.completed_at = timezone.now()
                
                batch.save()
                
                self.logger.info(f"Updated batch {batch.batch_id} status to {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating batch status: {str(e)}")
            return False
    
    def update_item_status(self, item: WebhookBatchItem, status: str, error_message: str = None) -> bool:
        """
        Update the status of a batch item.
        
        Args:
            item: The batch item to update
            status: The new status
            error_message: Optional error message
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Validate status transition
                if not self._is_valid_item_status_transition(item.status, status):
                    self.logger.error(f"Invalid item status transition from {item.status} to {status}")
                    return False
                
                # Update item
                item.status = status
                if error_message:
                    item.error_message = error_message
                
                # Update timestamps based on status
                if status == BatchStatus.PROCESSING and not item.started_at:
                    item.started_at = timezone.now()
                elif status in [BatchStatus.COMPLETED, BatchStatus.CANCELLED, BatchStatus.FAILED] and not item.completed_at:
                    item.completed_at = timezone.now()
                
                item.save()
                
                # Update batch status if needed
                self._update_batch_status_from_items(item.batch)
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating item status: {str(e)}")
            return False
    
    def _is_valid_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Check if a status transition is valid.
        
        Args:
            current_status: The current status
            new_status: The new status
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_transitions = {
            BatchStatus.PENDING: [BatchStatus.PROCESSING, BatchStatus.CANCELLED],
            BatchStatus.PROCESSING: [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED],
            BatchStatus.COMPLETED: [],  # Terminal state
            BatchStatus.FAILED: [BatchStatus.PENDING],  # Can retry
            BatchStatus.CANCELLED: []  # Terminal state
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    def _is_valid_item_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Check if an item status transition is valid.
        
        Args:
            current_status: The current status
            new_status: The new status
            
        Returns:
            True if transition is valid, False otherwise
        """
        valid_transitions = {
            BatchStatus.PENDING: [BatchStatus.PROCESSING, BatchStatus.CANCELLED],
            BatchStatus.PROCESSING: [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED],
            BatchStatus.COMPLETED: [],  # Terminal state
            BatchStatus.FAILED: [BatchStatus.PENDING],  # Can retry
            BatchStatus.CANCELLED: []  # Terminal state
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    def _update_batch_status_from_items(self, batch: WebhookBatch) -> None:
        """
        Update batch status based on item statuses.
        
        Args:
            batch: The batch to update
        """
        try:
            # Get item counts
            items = batch.items.all()
            total_items = items.count()
            
            if total_items == 0:
                return
            
            completed_items = items.filter(status=BatchStatus.COMPLETED).count()
            failed_items = items.filter(status=BatchStatus.FAILED).count()
            cancelled_items = items.filter(status=BatchStatus.CANCELLED).count()
            pending_items = items.filter(status=BatchStatus.PENDING).count()
            processing_items = items.filter(status=BatchStatus.PROCESSING).count()
            
            # Determine batch status
            if processing_items > 0:
                # Still processing
                if batch.status != BatchStatus.PROCESSING:
                    batch.status = BatchStatus.PROCESSING
                    batch.started_at = timezone.now()
            elif pending_items > 0:
                # Some items still pending
                if batch.status != BatchStatus.PROCESSING:
                    batch.status = BatchStatus.PROCESSING
                    batch.started_at = timezone.now()
            elif completed_items == total_items:
                # All items completed
                batch.status = BatchStatus.COMPLETED
                batch.completed_at = timezone.now()
            elif cancelled_items > 0 and cancelled_items + completed_items == total_items:
                # All items either completed or cancelled
                batch.status = BatchStatus.CANCELLED
                batch.completed_at = timezone.now()
            elif failed_items > 0 and failed_items + completed_items == total_items:
                # All items either completed or failed
                batch.status = BatchStatus.FAILED
                batch.completed_at = timezone.now()
            
            batch.save()
            
        except Exception as e:
            logger.error(f"Error updating batch status from items: {str(e)}")
    
    def get_batch_status_summary(self, batch_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive status summary for a batch.
        
        Args:
            batch_id: The batch ID
            
        Returns:
            Dictionary with status summary
        """
        try:
            batch = WebhookBatch.objects.get(batch_id=batch_id)
            
            # Get item statistics
            items = batch.items.all()
            total_items = items.count()
            
            status_counts = {}
            for status_choice in BatchStatus.CHOICES:
                status = status_choice[0]
                count = items.filter(status=status).count()
                if count > 0:
                    status_counts[status] = count
            
            # Calculate progress
            completed_count = status_counts.get(BatchStatus.COMPLETED, 0)
            progress_percentage = (completed_count / total_items * 100) if total_items > 0 else 0
            
            # Get timing information
            timing_info = {
                'created_at': batch.created_at.isoformat(),
                'started_at': batch.started_at.isoformat() if batch.started_at else None,
                'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
            }
            
            if batch.started_at and batch.completed_at:
                processing_time = (batch.completed_at - batch.started_at).total_seconds()
                timing_info['processing_time_seconds'] = processing_time
            
            return {
                'batch_id': batch.batch_id,
                'status': batch.status,
                'total_items': total_items,
                'status_counts': status_counts,
                'progress_percentage': round(progress_percentage, 2),
                'timing': timing_info,
                'error_message': batch.error_message
            }
            
        except WebhookBatch.DoesNotExist:
            return {
                'batch_id': batch_id,
                'error': 'Batch not found'
            }
        except Exception as e:
            logger.error(f"Error getting batch status summary: {str(e)}")
            return {
                'batch_id': batch_id,
                'error': str(e)
            }
    
    def get_item_status_history(self, item_id: str) -> Dict[str, Any]:
        """
        Get status history for a batch item.
        
        Args:
            item_id: The item ID
            
        Returns:
            Dictionary with status history
        """
        try:
            item = WebhookBatchItem.objects.get(id=item_id)
            
            # Create status timeline
            timeline = []
            
            # Created
            timeline.append({
                'status': 'created',
                'timestamp': item.created_at.isoformat(),
                'description': 'Item created'
            })
            
            # Started processing
            if item.started_at:
                timeline.append({
                    'status': 'started',
                    'timestamp': item.started_at.isoformat(),
                    'description': 'Started processing'
                })
            
            # Completed
            if item.completed_at:
                timeline.append({
                    'status': 'completed',
                    'timestamp': item.completed_at.isoformat(),
                    'description': f'Completed with status: {item.status}'
                })
            
            return {
                'item_id': str(item.id),
                'batch_id': item.batch.batch_id,
                'sequence_number': item.sequence_number,
                'current_status': item.status,
                'timeline': timeline,
                'error_message': item.error_message
            }
            
        except WebhookBatchItem.DoesNotExist:
            return {
                'item_id': item_id,
                'error': 'Item not found'
            }
        except Exception as e:
            logger.error(f"Error getting item status history: {str(e)}")
            return {
                'item_id': item_id,
                'error': str(e)
            }
    
    def get_batch_status_overview(self, endpoint_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get overview of batch statuses.
        
        Args:
            endpoint_id: Optional endpoint ID to filter by
            days: Number of days to look back
            
        Returns:
            Dictionary with status overview
        """
        try:
            from datetime import timedelta
            
            since = timezone.now() - timedelta(days=days)
            
            # Base query for batches
            batches = WebhookBatch.objects.filter(created_at__gte=since)
            if endpoint_id:
                batches = batches.filter(endpoint_id=endpoint_id)
            
            # Get status breakdown
            status_breakdown = batches.values('status').annotate(
                count=Count('id')
            ).order_by('status')
            
            # Get daily statistics
            daily_stats = []
            for day in range(days):
                date = (timezone.now() - timedelta(days=day)).date()
                
                day_batches = batches.filter(created_at__date=date)
                day_completed = day_batches.filter(status=BatchStatus.COMPLETED).count()
                day_failed = day_batches.filter(status=BatchStatus.FAILED).count()
                day_cancelled = day_batches.filter(status=BatchStatus.CANCELLED).count()
                
                daily_stats.append({
                    'date': date.isoformat(),
                    'total': day_batches.count(),
                    'completed': day_completed,
                    'failed': day_failed,
                    'cancelled': day_cancelled
                })
            
            # Get item statistics
            total_items = batches.aggregate(
                total=Count('items')
            )['total'] or 0
            
            completed_items = batches.filter(
                items__status=BatchStatus.COMPLETED
            ).aggregate(
                total=Count('items')
            )['total'] or 0
            
            return {
                'total_batches': batches.count(),
                'total_items': total_items,
                'completed_items': completed_items,
                'completion_rate': round((completed_items / total_items * 100) if total_items > 0 else 0, 2),
                'status_breakdown': list(status_breakdown),
                'daily_statistics': daily_stats,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting batch status overview: {str(e)}")
            return {
                'error': str(e),
                'period_days': days
            }
    
    def get_stalled_batches(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Get batches that appear to be stalled (processing for too long).
        
        Args:
            hours: Number of hours to consider stalled
            
        Returns:
            List of stalled batch information
        """
        try:
            from datetime import timedelta
            
            stall_threshold = timezone.now() - timedelta(hours=hours)
            
            stalled_batches = WebhookBatch.objects.filter(
                status=BatchStatus.PROCESSING,
                started_at__lt=stall_threshold
            ).select_related('endpoint')
            
            stalled_list = []
            for batch in stalled_batches:
                processing_time = (timezone.now() - batch.started_at).total_seconds()
                
                stalled_list.append({
                    'batch_id': batch.batch_id,
                    'endpoint_id': str(batch.endpoint.id),
                    'endpoint_label': batch.endpoint.label,
                    'status': batch.status,
                    'started_at': batch.started_at.isoformat(),
                    'processing_time_seconds': processing_time,
                    'total_items': batch.items.count(),
                    'completed_items': batch.items.filter(status=BatchStatus.COMPLETED).count()
                })
            
            return stalled_list
            
        except Exception as e:
            logger.error(f"Error getting stalled batches: {str(e)}")
            return []
    
    def cleanup_completed_batches(self, days: int = 7) -> Dict[str, Any]:
        """
        Clean up old completed batches.
        
        Args:
            days: Number of days to keep completed batches
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete old completed batches
            old_batches = WebhookBatch.objects.filter(
                created_at__lt=cutoff_date,
                status__in=[BatchStatus.COMPLETED, BatchStatus.CANCELLED, BatchStatus.FAILED]
            )
            
            deleted_count = old_batches.count()
            old_batches.delete()
            
            return {
                'deleted_batches': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'days': days
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up completed batches: {str(e)}")
            return {
                'error': str(e),
                'days': days
            }
    
    def reset_failed_items(self, batch_id: str) -> Dict[str, Any]:
        """
        Reset failed items in a batch to pending status.
        
        Args:
            batch_id: The batch ID
            
        Returns:
            Dictionary with reset results
        """
        try:
            batch = WebhookBatch.objects.get(batch_id=batch_id)
            
            # Get failed items
            failed_items = batch.items.filter(status=BatchStatus.FAILED)
            
            if not failed_items.exists():
                return {
                    'batch_id': batch_id,
                    'success': False,
                    'error': 'No failed items to reset'
                }
            
            # Reset items to pending
            reset_count = failed_items.update(
                status=BatchStatus.PENDING,
                error_message=None,
                started_at=None,
                completed_at=None
            )
            
            # Update batch status if needed
            if batch.status == BatchStatus.FAILED:
                batch.status = BatchStatus.PENDING
                batch.error_message = None
                batch.started_at = None
                batch.completed_at = None
                batch.save()
            
            return {
                'batch_id': batch_id,
                'success': True,
                'reset_count': reset_count
            }
            
        except WebhookBatch.DoesNotExist:
            return {
                'batch_id': batch_id,
                'success': False,
                'error': 'Batch not found'
            }
        except Exception as e:
            logger.error(f"Error resetting failed items: {str(e)}")
            return {
                'batch_id': batch_id,
                'success': False,
                'error': str(e)
            }
    
    def get_batch_performance_metrics(self, batch_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for a batch.
        
        Args:
            batch_id: The batch ID
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            batch = WebhookBatch.objects.get(batch_id=batch_id)
            items = batch.items.all()
            
            if not batch.started_at or not batch.completed_at:
                return {
                    'batch_id': batch_id,
                    'error': 'Batch not completed'
                }
            
            # Calculate processing time
            processing_time = (batch.completed_at - batch.started_at).total_seconds()
            
            # Calculate item processing times
            item_times = []
            for item in items:
                if item.started_at and item.completed_at:
                    item_time = (item.completed_at - item.started_at).total_seconds()
                    item_times.append(item_time)
            
            if not item_times:
                return {
                    'batch_id': batch_id,
                    'error': 'No completed items with timing data'
                }
            
            # Calculate statistics
            avg_item_time = sum(item_times) / len(item_times)
            min_item_time = min(item_times)
            max_item_time = max(item_times)
            
            # Calculate throughput
            throughput = len(items) / processing_time if processing_time > 0 else 0
            
            return {
                'batch_id': batch_id,
                'total_processing_time_seconds': processing_time,
                'total_items': items.count(),
                'throughput_items_per_second': round(throughput, 2),
                'avg_item_processing_time_seconds': round(avg_item_time, 2),
                'min_item_processing_time_seconds': round(min_item_time, 2),
                'max_item_processing_time_seconds': round(max_item_time, 2),
                'completed_items': items.filter(status=BatchStatus.COMPLETED).count(),
                'failed_items': items.filter(status=BatchStatus.FAILED).count()
            }
            
        except WebhookBatch.DoesNotExist:
            return {
                'batch_id': batch_id,
                'error': 'Batch not found'
            }
        except Exception as e:
            logger.error(f"Error getting batch performance metrics: {str(e)}")
            return {
                'batch_id': batch_id,
                'error': str(e)
            }
