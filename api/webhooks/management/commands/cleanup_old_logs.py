"""Cleanup Old Logs Management Command

This Django management command archives old webhook logs
for compliance and database maintenance.
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.module_loading import import_string

from ...models import WebhookDeliveryLog, WebhookHealthLog, WebhookAnalytics
from ...constants import WEBHOOK_ANALYTICS_RETENTION_DAYS

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to cleanup old webhook logs.
    Archives logs older than specified retention period.
    """
    
    help = 'Archive old webhook logs for database maintenance'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=WEBHOOK_ANALYTICS_RETENTION_DAYS,
            help=f'Days of logs to retain (default: {WEBHOOK_ANALYTICS_RETENTION_DAYS})',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without executing',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for deletion processing',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        self.stdout.write(f"Starting cleanup of logs older than {days} days...")
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get counts before deletion
            delivery_logs_count = WebhookDeliveryLog.objects.filter(
                created_at__lt=cutoff_date
            ).count()
            
            health_logs_count = WebhookHealthLog.objects.filter(
                checked_at__lt=cutoff_date
            ).count()
            
            analytics_count = WebhookAnalytics.objects.filter(
                date__lt=cutoff_date
            ).count()
            
            total_old_logs = delivery_logs_count + health_logs_count + analytics_count
            
            if total_old_logs == 0:
                self.stdout.write("No old logs found to cleanup.")
                return
            
            if dry_run:
                self.stdout.write(f"DRY RUN: Would delete {total_old_logs} old logs:")
                self.stdout.write(f"  Delivery logs: {delivery_logs_count}")
                self.stdout.write(f"  Health logs: {health_logs_count}")
                self.stdout.write(f"  Analytics records: {analytics_count}")
                return
            
            # Delete in batches
            deleted_count = 0
            
            # Delete delivery logs
            self.stdout.write("Deleting old delivery logs...")
            deleted_delivery = self._delete_in_batches(
                WebhookDeliveryLog.objects.filter(created_at__lt=cutoff_date),
                batch_size
            )
            deleted_count += deleted_delivery
            
            # Delete health logs
            self.stdout.write("Deleting old health logs...")
            deleted_health = self._delete_in_batches(
                WebhookHealthLog.objects.filter(checked_at__lt=cutoff_date),
                batch_size
            )
            deleted_count += deleted_health
            
            # Delete analytics records
            self.stdout.write("Deleting old analytics records...")
            deleted_analytics = self._delete_in_batches(
                WebhookAnalytics.objects.filter(date__lt=cutoff_date),
                batch_size
            )
            deleted_count += deleted_analytics
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted {deleted_count} old logs"
                )
            )
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Cleanup failed: {e}")
            )
            logger.error(f"Log cleanup command failed: {e}")
    
    def _delete_in_batches(self, queryset, batch_size):
        """Delete queryset in batches to avoid memory issues."""
        deleted_count = 0
        
        while queryset.exists():
            batch = queryset[:batch_size]
            deleted = batch.delete()[0]
            deleted_count += deleted
            
            self.stdout.write(f"  Deleted batch of {deleted} items")
            
            # Remove deleted items from queryset
            queryset = queryset[batch_size:]
        
        return deleted_count
