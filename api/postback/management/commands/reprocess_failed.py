"""
reprocess_failed.py – Management command to reprocess failed postbacks.

This command provides comprehensive functionality to reprocess failed postbacks
with various filtering options, batch processing, and monitoring capabilities.
"""
import logging
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.postback.models import PostbackLog, NetworkPostbackConfig
from api.postback.choices import PostbackStatus, RejectionReason
from api.postback.tasks import process_postback

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to reprocess failed postbacks."""

    help = "Reprocess failed postbacks with various filtering options"

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--network',
            type=str,
            help='Network key to filter postbacks (optional)'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['FAILED', 'REJECTED', 'BOTH'],
            default='FAILED',
            help='Status to reprocess: FAILED, REJECTED, or BOTH (default: FAILED)'
        )
        parser.add_argument(
            '--rejection-reason',
            type=str,
            help='Specific rejection reason to reprocess (optional)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Reprocess postbacks from last N hours (default: 24)'
        )
        parser.add_argument(
            '--days',
            type=int,
            help='Reprocess postbacks from last N days (overrides --hours)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of postbacks to reprocess (optional)'
        )
        parser.add_argument(
            '--retry-count',
            type=int,
            help='Only reprocess postbacks with retry count less than this (optional)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reprocessed without actually doing it'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Process in batches of N postbacks (default: 100)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reprocess even for postbacks with high retry counts'
        )
        parser.add_argument(
            '--exclude-reasons',
            type=str,
            help='Comma-separated list of rejection reasons to exclude'
        )
        parser.add_argument(
            '--include-reasons',
            type=str,
            help='Comma-separated list of rejection reasons to include only'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        
        # Parse time range
        if options['days']:
            since = timezone.now() - timedelta(days=options['days'])
        else:
            since = timezone.now() - timedelta(hours=options['hours'])
        
        # Build queryset
        queryset = self._build_queryset(options, since)
        
        # Get postback count
        total_count = queryset.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No failed postbacks found matching the criteria.")
            )
            return
        
        # Apply limit if specified
        if options['limit'] and total_count > options['limit']:
            queryset = queryset[:options['limit']]
            total_count = options['limit']
        
        self.stdout.write(
            f"Found {total_count} postbacks to reprocess "
            f"since {since.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if options['dry_run']:
            self._dry_run(queryset, options)
            return
        
        # Process postbacks
        self._process_postbacks(queryset, options)

    def _build_queryset(self, options, since):
        """Build the queryset for postbacks to reprocess."""
        queryset = PostbackLog.objects.filter(
            received_at__gte=since
        ).select_related('network', 'resolved_user')
        
        # Filter by network
        if options['network']:
            try:
                network = NetworkPostbackConfig.objects.get(network_key=options['network'])
                queryset = queryset.filter(network=network)
            except NetworkPostbackConfig.DoesNotExist:
                raise CommandError(f"Network with key '{options['network']}' not found")
        
        # Filter by status
        status_filter = options['status']
        if status_filter == 'FAILED':
            queryset = queryset.filter(status=PostbackStatus.FAILED)
        elif status_filter == 'REJECTED':
            queryset = queryset.filter(status=PostbackStatus.REJECTED)
        elif status_filter == 'BOTH':
            queryset = queryset.filter(
                status__in=[PostbackStatus.FAILED, PostbackStatus.REJECTED]
            )
        
        # Filter by rejection reason
        if options['rejection_reason']:
            try:
                reason = RejectionReason(options['rejection_reason'])
                queryset = queryset.filter(rejection_reason=reason)
            except ValueError:
                raise CommandError(f"Invalid rejection reason: {options['rejection_reason']}")
        
        # Filter by retry count
        if options['retry_count'] and not options['force']:
            queryset = queryset.filter(retry_count__lt=options['retry_count'])
        
        # Exclude rejection reasons
        if options['exclude_reasons']:
            exclude_reasons = [r.strip() for r in options['exclude_reasons'].split(',')]
            valid_reasons = []
            for reason in exclude_reasons:
                try:
                    valid_reasons.append(RejectionReason(reason))
                except ValueError:
                    self.stdout.write(
                        self.style.WARNING(f"Invalid rejection reason to exclude: {reason}")
                    )
            if valid_reasons:
                queryset = queryset.exclude(rejection_reason__in=valid_reasons)
        
        # Include only specific rejection reasons
        if options['include_reasons']:
            include_reasons = [r.strip() for r in options['include_reasons'].split(',')]
            valid_reasons = []
            for reason in include_reasons:
                try:
                    valid_reasons.append(RejectionReason(reason))
                except ValueError:
                    self.stdout.write(
                        self.style.WARNING(f"Invalid rejection reason to include: {reason}")
                    )
            if valid_reasons:
                queryset = queryset.filter(rejection_reason__in=valid_reasons)
        
        # Order by received_at (oldest first)
        queryset = queryset.order_by('received_at')
        
        return queryset

    def _dry_run(self, queryset, options):
        """Perform dry run to show what would be reprocessed."""
        self.stdout.write("\n" + "="*50)
        self.stdout.write("DRY RUN - Postbacks that would be reprocessed:")
        self.stdout.write("="*50)
        
        # Group by network and status
        summary = {}
        for log in queryset[:50]:  # Show first 50 for dry run
            key = f"{log.network.network_key}:{log.get_status_display()}"
            if key not in summary:
                summary[key] = []
            summary[key].append(log)
        
        for key, logs in summary.items():
            network_key, status = key.split(':')
            self.stdout.write(f"\n{network_key} - {status} ({len(logs)} postbacks):")
            
            for log in logs[:5]:  # Show first 5 per group
                self.stdout.write(
                    f"  - ID: {log.id}, "
                    f"Received: {log.received_at.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"Retry: {log.retry_count}, "
                    f"Reason: {log.rejection_reason or 'None'}"
                )
            
            if len(logs) > 5:
                self.stdout.write(f"  ... and {len(logs) - 5} more")
        
        total_count = queryset.count()
        self.stdout.write(f"\nTotal postbacks to reprocess: {total_count}")
        
        if total_count > 50:
            self.stdout.write("(Showing first 50, use --limit to see exact count)")

    def _process_postbacks(self, queryset, options):
        """Process the postbacks in batches."""
        batch_size = options['batch_size']
        total_count = queryset.count()
        processed_count = 0
        success_count = 0
        error_count = 0
        
        self.stdout.write(f"\nProcessing {total_count} postbacks in batches of {batch_size}...")
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = queryset[i:i + batch_size]
            
            self.stdout.write(
                f"\nProcessing batch {i//batch_size + 1}/{(total_count + batch_size - 1)//batch_size} "
                f"({len(batch)} postbacks)..."
            )
            
            batch_success = 0
            batch_errors = 0
            
            for log in batch:
                try:
                    self._reprocess_single_postback(log, options)
                    batch_success += 1
                    success_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Error reprocessing postback {log.id}: {str(e)}"
                        )
                    )
                    batch_errors += 1
                    error_count += 1
                
                processed_count += 1
                
                # Progress indicator
                if processed_count % 10 == 0 or processed_count == total_count:
                    progress = (processed_count / total_count) * 100
                    self.stdout.write(
                        f"  Progress: {processed_count}/{total_count} ({progress:.1f}%)"
                    )
            
            # Batch summary
            self.stdout.write(
                f"  Batch completed: {batch_success} successful, {batch_errors} errors"
            )
        
        # Final summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("REPROCESSING SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total processed: {processed_count}")
        self.stdout.write(f"Successful: {success_count}")
        self.stdout.write(f"Errors: {error_count}")
        self.stdout.write(f"Success rate: {(success_count/processed_count*100):.1f}%" if processed_count > 0 else "Success rate: 0%")
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f"\n{error_count} postbacks failed to reprocess. "
                "Check the logs above for details.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\nAll postbacks reprocessed successfully!")
            )

    def _reprocess_single_postback(self, log, options):
        """Reprocess a single postback."""
        # Reset status to received for reprocessing
        original_status = log.status
        original_retry_count = log.retry_count
        
        log.status = PostbackStatus.RECEIVED
        log.retry_count += 1
        log.processed_at = None
        log.processing_error = None
        log.save(update_fields=['status', 'retry_count', 'processed_at', 'processing_error', 'updated_at'])
        
        # Queue for processing
        try:
            process_postback.delay(
                str(log.id),
                signature="",
                timestamp_str="",
                nonce="reprocess",
                body_bytes_hex="",
                path="",
                query_params={}
            )
            
            logger.info(f"Queued postback {log.id} for reprocessing (attempt {log.retry_count})")
            
        except Exception as e:
            # Restore original status on queue failure
            log.status = original_status
            log.retry_count = original_retry_count
            log.save(update_fields=['status', 'retry_count', 'updated_at'])
            raise e
