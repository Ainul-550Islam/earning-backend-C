"""
Django Management Command: Process Pending Alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from alerts.models.core import AlertLog
from alerts.tasks.core import process_pending_alerts

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process pending alerts using Celery task'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Number of alerts to process (default: 100)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Only process alerts from last N hours (default: 24)'
        )
        parser.add_argument(
            '--severity',
            type=str,
            choices=['low', 'medium', 'high', 'critical'],
            help='Only process alerts of specified severity'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually processing'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing even if alerts are already being processed'
        )
    
    def handle(self, *args, **options):
        limit = options['limit']
        hours = options['hours']
        severity = options['severity']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS(f'Processing alerts with options: limit={limit}, hours={hours}, severity={severity}'))
        
        # Build query filters
        filters = {
            'is_resolved': False,
            'triggered_at__gte': timezone.now() - timedelta(hours=hours)
        }
        
        if severity:
            filters['rule__severity'] = severity
        
        # Get pending alerts
        pending_alerts = AlertLog.objects.filter(**filters).select_related('rule')[:limit]
        
        if not pending_alerts.exists():
            self.stdout.write(self.style.WARNING('No pending alerts found matching criteria'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {pending_alerts.count()} pending alerts'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No alerts will be processed'))
            for alert in pending_alerts:
                self.stdout.write(f'  - Alert {alert.id}: {alert.rule.name} ({alert.rule.get_severity_display()})')
            return
        
        # Process alerts
        processed_count = 0
        failed_count = 0
        
        for alert in pending_alerts:
            try:
                if force or not alert.is_being_processed():
                    # Trigger Celery task
                    process_pending_alerts.delay(alert.id)
                    processed_count += 1
                    self.stdout.write(f'  - Queued alert {alert.id}: {alert.rule.name}')
                else:
                    self.stdout.write(self.style.WARNING(f'  - Skipped alert {alert.id}: already being processed'))
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'  - Failed to queue alert {alert.id}: {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Processing complete:'))
        self.stdout.write(f'  - Total alerts found: {pending_alerts.count()}')
        self.stdout.write(f'  - Successfully queued: {processed_count}')
        self.stdout.write(f'  - Failed: {failed_count}')
        
        if processed_count > 0:
            self.stdout.write(self.style.SUCCESS('Alerts have been queued for processing. Check Celery worker logs for progress.'))
