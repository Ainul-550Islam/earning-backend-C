"""Replay Events Management Command

This Django management command replays webhook events
for a specified date range or event type.
"""

import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from ...services.replay import ReplayService
from ...models import WebhookDeliveryLog, WebhookReplayBatch
from ...constants import EventType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to replay webhook events.
    Allows replaying specific events or date ranges safely.
    """
    
    help = 'Replay webhook events for a date range or event type'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--event-type',
            type=str,
            help='Event type to replay (e.g., user.created, payment.succeeded)',
        )
        parser.add_argument(
            '--date-from',
            type=str,
            help='Start date for replay (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--date-to',
            type=str,
            help='End date for replay (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be replayed without executing',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for replay processing',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID who is performing the replay',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        event_type = options.get('event_type')
        date_from = options.get('date_from')
        date_to = options.get('date_to')
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        user_id = options.get('user_id')
        
        self.stdout.write("Starting webhook event replay...")
        
        try:
            # Validate arguments
            if not any([event_type, date_from, date_to]):
                self.stderr.write(
                    self.style.ERROR(
                        "Must provide either --event-type or --date-from/--date-to"
                    )
                )
                return
            
            # Parse dates
            from_date = None
            to_date = None
            
            if date_from:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            if date_to:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            
            # Get replay service
            replay_service = ReplayService()
            
            if dry_run:
                # Preview mode
                preview = replay_service.preview_replay(
                    event_type=event_type,
                    from_date=from_date,
                    to_date=to_date,
                    batch_size=batch_size,
                    user_id=user_id,
                )
                
                self.stdout.write(self.style.SUCCESS("Replay preview:"))
                self.stdout.write(f"  Event type: {event_type or 'ALL'}")
                self.stdout.write(f"  Date range: {from_date or 'START'} to {to_date or 'NOW'}")
                self.stdout.write(f"  Batch size: {batch_size}")
                self.stdout.write(f"  Total events: {preview['total_events']}")
                self.stdout.write(f"  Estimated batches: {preview['estimated_batches']}")
                
            else:
                # Execute replay
                result = replay_service.create_replay_batch(
                    event_type=event_type,
                    from_date=from_date,
                    to_date=to_date,
                    batch_size=batch_size,
                    user_id=user_id,
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created replay batch {result['batch_id']} with {result['event_count']} events"
                    )
                )
                
                # Start processing
                if replay_service.start_batch_processing(result['batch']):
                    self.stdout.write(
                        self.style.SUCCESS("Replay batch processing started")
                    )
                    
                    # Show progress
                    self._show_progress(replay_service, result['batch'])
                else:
                    self.stderr.write(
                        self.style.ERROR("Failed to start batch processing")
                    )
            
        except ValueError as e:
            self.stderr.write(
                self.style.ERROR(f"Date format error: {e}")
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Replay failed: {e}")
            )
            logger.error(f"Webhook replay command failed: {e}")
    
    def _show_progress(self, replay_service, replay_batch):
        """Show progress of batch processing."""
        try:
            while True:
                batch_status = replay_service.get_batch_status(replay_batch.batch_id)
                
                if batch_status['status'] in ['completed', 'failed']:
                    break
                
                # Get progress
                progress = replay_service.get_batch_progress(replay_batch.batch_id)
                
                self.stdout.write(
                    f"Progress: {progress['processed_items']}/{progress['total_items']} "
                    f"({progress['completion_percentage']}%) - "
                    f"Status: {batch_status['status']}"
                )
                
                # Wait before next check
                import time
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.stdout.write("\nReplay monitoring stopped by user")
        except Exception as e:
            logger.error(f"Progress monitoring error: {e}")
    
    def _get_event_types(self) -> str:
        """Get available event types for help."""
        event_types = []
        for event_type, display_name in EventType.all_choices():
            event_types.append(f"  {event_type}: {display_name}")
        
        return '\n'.join(event_types)
