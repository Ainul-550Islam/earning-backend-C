"""Webhook Batch Service

This service manages webhook batch processing and status tracking.
Groups multiple webhook events for efficient processing.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from ...models import WebhookBatch, WebhookBatchItem, WebhookDeliveryLog
from ...constants import BatchStatus

logger = logging.getLogger(__name__)


class BatchService:
    """
    Service for managing webhook batch operations.
    Handles batch creation, processing, and completion tracking.
    """
    
    def __init__(self):
        """Initialize batch service."""
        self.logger = logger
    
    def create_batch(self, endpoint, delivery_logs: List[WebhookDeliveryLog]) -> WebhookBatch:
        """
        Create a new batch from delivery logs.
        
        Args:
            endpoint: WebhookEndpoint instance
            delivery_logs: List of delivery logs to batch
            
        Returns:
            WebhookBatch: Created batch instance
        """
        try:
            with transaction.atomic():
                batch = WebhookBatch.objects.create(
                    batch_id=self._generate_batch_id(),
                    endpoint=endpoint,
                    event_count=len(delivery_logs),
                    status=BatchStatus.PENDING,
                )
                
                # Create batch items
                for position, delivery_log in enumerate(delivery_logs, 1):
                    WebhookBatchItem.objects.create(
                        batch=batch,
                        delivery_log=delivery_log,
                        position=position,
                    )
                
                self.logger.info(
                    f"Created batch {batch.batch_id} with {len(delivery_logs)} items"
                )
                
                return batch
                
        except Exception as e:
            self.logger.error(f"Failed to create batch: {e}")
            raise
    
    def start_batch_processing(self, batch: WebhookBatch) -> bool:
        """
        Start processing a batch.
        
        Args:
            batch: WebhookBatch instance
            
        Returns:
            bool: True if successful
        """
        try:
            batch.status = BatchStatus.PROCESSING
            batch.save()
            
            self.logger.info(f"Started processing batch {batch.batch_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start batch processing: {e}")
            return False
    
    def complete_batch(self, batch: WebhookBatch, success_count: int) -> bool:
        """
        Mark a batch as completed.
        
        Args:
            batch: WebhookBatch instance
            success_count: Number of successful deliveries
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                batch.status = BatchStatus.COMPLETED
                batch.completed_at = timezone.now()
                batch.save()
                
                # Update batch items with success status
                batch.items.filter(
                    delivery_log__status='success'
                ).update(status='completed')
                
                self.logger.info(
                    f"Completed batch {batch.batch_id} with {success_count} successes"
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to complete batch: {e}")
            return False
    
    def cancel_batch(self, batch: WebhookBatch, reason: str) -> bool:
        """
        Cancel a batch.
        
        Args:
            batch: WebhookBatch instance
            reason: Reason for cancellation
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                batch.status = BatchStatus.CANCELLED
                batch.completed_at = timezone.now()
                batch.save()
                
                # Mark all items as cancelled
                batch.items.update(status='cancelled')
                
                self.logger.info(f"Cancelled batch {batch.batch_id}: {reason}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to cancel batch: {e}")
            return False
    
    def fail_batch(self, batch: WebhookBatch, error_message: str) -> bool:
        """
        Mark a batch as failed.
        
        Args:
            batch: WebhookBatch instance
            error_message: Error description
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                batch.status = BatchStatus.FAILED
                batch.completed_at = timezone.now()
                batch.save()
                
                # Mark all items as failed
                batch.items.update(status='failed')
                
                self.logger.error(f"Failed batch {batch.batch_id}: {error_message}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to mark batch as failed: {e}")
            return False
    
    def get_batch_status(self, batch_id: str) -> Optional[WebhookBatch]:
        """
        Get batch status by ID.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            WebhookBatch or None
        """
        try:
            return WebhookBatch.objects.filter(batch_id=batch_id).first()
        except Exception as e:
            self.logger.error(f"Failed to get batch status: {e}")
            return None
    
    def get_pending_batches(self, endpoint=None) -> List[WebhookBatch]:
        """
        Get all pending batches.
        
        Args:
            endpoint: Optional endpoint filter
            
        Returns:
            List[WebhookBatch]: Pending batches
        """
        try:
            queryset = WebhookBatch.objects.filter(status=BatchStatus.PENDING)
            
            if endpoint:
                queryset = queryset.filter(endpoint=endpoint)
            
            return list(queryset.order_by('created_at'))
            
        except Exception as e:
            self.logger.error(f"Failed to get pending batches: {e}")
            return []
    
    def get_batch_statistics(self, endpoint, days: int = 30) -> Dict[str, Any]:
        """
        Get batch processing statistics.
        
        Args:
            endpoint: WebhookEndpoint instance
            days: Number of days to analyze
            
        Returns:
            Dict: Batch statistics
        """
        try:
            since = timezone.now() - timedelta(days=days)
            
            batches = WebhookBatch.objects.filter(
                endpoint=endpoint,
                created_at__gte=since
            )
            
            total_batches = batches.count()
            completed_batches = batches.filter(status=BatchStatus.COMPLETED).count()
            failed_batches = batches.filter(status=BatchStatus.FAILED).count()
            cancelled_batches = batches.filter(status=BatchStatus.CANCELLED).count()
            
            return {
                'total_batches': total_batches,
                'completed_batches': completed_batches,
                'failed_batches': failed_batches,
                'cancelled_batches': cancelled_batches,
                'success_rate': (completed_batches / total_batches * 100) if total_batches > 0 else 0,
                'period_days': days,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get batch statistics: {e}")
            return {}
    
    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID."""
        return str(uuid.uuid4())[:8].upper()
    
    def cleanup_old_batches(self, days: int = 90) -> int:
        """
        Clean up old completed batches.
        
        Args:
            days: Age threshold in days
            
        Returns:
            int: Number of batches cleaned up
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            deleted_count = WebhookBatch.objects.filter(
                completed_at__lt=cutoff_date,
                status__in=[BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]
            ).delete()[0]
            
            self.logger.info(f"Cleaned up {deleted_count} old batches")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old batches: {e}")
            return 0
