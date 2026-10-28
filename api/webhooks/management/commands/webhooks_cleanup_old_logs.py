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
from ...services.analytics.AgingService import AgingService

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
        """Execute the command's own --days-based cleanup of
        WebhookDeliveryLog/WebhookHealthLog/WebhookAnalytics rows."""
        days       = options['days']
        dry_run    = options['dry_run']
        batch_size = options['batch_size']

        self.stdout.write(f"Starting cleanup of logs older than {days} days...")
        logger.info("cleanup_old_logs: days=%d dry_run=%s", days, dry_run)

        # BUG FIX: docstring/label used to claim this command "uses
        # AgingService for integrated archive/purge operations" - it
        # doesn't. This block only ever ran in dry-run mode, and even then
        # only as an extra, separate preview: AgingService.purge_due_records()
        # tracks its own schedule (WebhookEndpointAging/WebhookDeliveryAging
        # rows with their own purge_after date) via a completely different
        # criterion than this command's own --days/created_at cutoff below -
        # so the two numbers can legitimately disagree, and showing them
        # side by side without saying so read as one command with one
        # inconsistent preview rather than two unrelated systems. The real
        # (non-dry-run) deletion path never called AgingService at all, so
        # nothing here was actually deciding what gets deleted for real.
        # AgingService.purge_due_records(dry_run=False) is also documented
        # as "only from the Celery purge task" - deliberately not called
        # from here even to fix the real path, since doing so would cross
        # that boundary rather than fix this command's own logic. Left as
        # a clearly-labeled separate informational preview.
        if dry_run:
            aging_service = AgingService()
            aging_preview = aging_service.purge_due_records(dry_run=True)
            self.stdout.write(
                "(Informational, separate from this command: "
                "AgingService's own scheduled purge queue currently has "
                f"{aging_preview.get('endpoints_to_purge', 0)} endpoint(s) and "
                f"{aging_preview.get('delivery_logs_to_purge', 0)} delivery log(s) "
                "due, tracked independently of --days below.)"
            )
        
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
        """Delete queryset in batches to avoid memory issues.

        BUG FIX: the previous version did `batch = queryset[:batch_size];
        batch.delete()` - Django does not allow delete() on a sliced
        queryset at all (confirmed empirically: TypeError: Cannot use
        'limit' or 'offset' with delete()), so this raised on the very
        first batch, every time, for every log type - the real (non
        dry-run) deletion path was 100% broken. Even setting that aside,
        the loop's `queryset = queryset[batch_size:]` re-slice would have
        been wrong too: querysets re-evaluate their filter lazily, so
        after deleting the first batch_size matching rows, the "next"
        batch_size-to-2*batch_size window would silently skip over rows
        that just became first in line, and a real backlog larger than
        one batch would never fully clear.

        Fixed by fetching a batch of PKs (slicing a values_list() for
        reading is fine) and deleting by an explicit pk__in list - no
        LIMIT/OFFSET on the delete itself, and each iteration re-queries
        the original filter fresh against the now-smaller table, so
        nothing is skipped.
        """
        deleted_count = 0
        model = queryset.model

        while True:
            batch_pks = list(queryset.values_list('pk', flat=True)[:batch_size])
            if not batch_pks:
                break

            deleted, _ = model.objects.filter(pk__in=batch_pks).delete()
            deleted_count += deleted

            self.stdout.write(f"  Deleted batch of {deleted} items")

        return deleted_count