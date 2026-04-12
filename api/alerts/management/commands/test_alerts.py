"""
Django Management Command: Test Alert Rules
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from alerts.models.core import AlertRule, AlertLog
from alerts.tasks.core import test_alert_rule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test alert rules by triggering test alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--rule-id',
            type=int,
            help='Test specific rule by ID'
        )
        parser.add_argument(
            '--rule-name',
            type=str,
            help='Test specific rule by name (partial match)'
        )
        parser.add_argument(
            '--severity',
            type=str,
            choices=['low', 'medium', 'high', 'critical'],
            help='Test rules of specific severity'
        )
        parser.add_argument(
            '--type',
            type=str,
            help='Test rules of specific alert type'
        )
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='Test only active rules'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of rules to test (default: 10)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be tested without actually testing'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force test even if rule was recently tested'
        )
        parser.add_argument(
            '--threshold-multiplier',
            type=float,
            default=1.5,
            help='Multiplier for threshold value (default: 1.5)'
        )
        parser.add_argument(
            '--message',
            type=str,
            default='Test alert triggered',
            help='Custom message for test alerts'
        )
    
    def handle(self, *args, **options):
        rule_id = options['rule_id']
        rule_name = options['rule_name']
        severity = options['severity']
        alert_type = options['type']
        active_only = options['active_only']
        limit = options['limit']
        dry_run = options['dry_run']
        force = options['force']
        threshold_multiplier = options['threshold_multiplier']
        message = options['message']
        
        self.stdout.write(self.style.SUCCESS('Testing alert rules'))
        
        # Build query filters
        filters = {}
        
        if rule_id:
            filters['id'] = rule_id
        
        if rule_name:
            filters['name__icontains'] = rule_name
        
        if severity:
            filters['severity'] = severity
        
        if alert_type:
            filters['alert_type'] = alert_type
        
        if active_only:
            filters['is_active'] = True
        
        # Get rules to test
        rules = AlertRule.objects.filter(**filters)[:limit]
        
        if not rules.exists():
            self.stdout.write(self.style.WARNING('No alert rules found matching criteria'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {rules.count()} alert rules to test'))
        
        # Test each rule
        tested_count = 0
        skipped_count = 0
        failed_count = 0
        
        for rule in rules:
            try:
                # Check if recently tested (within last hour)
                if not force:
                    recent_test = AlertLog.objects.filter(
                        rule=rule,
                        details__test=True,
                        triggered_at__gte=timezone.now() - timezone.timedelta(hours=1)
                    ).exists()
                    
                    if recent_test:
                        skipped_count += 1
                        self.stdout.write(f'  - Skipped rule {rule.id}: {rule.name} (recently tested)')
                        continue
                
                if dry_run:
                    self.stdout.write(f'  - Would test rule {rule.id}: {rule.name} ({rule.get_severity_display()})')
                    tested_count += 1
                    continue
                
                # Create test alert
                test_value = rule.threshold_value * threshold_multiplier
                test_details = {
                    'test': True,
                    'triggered_by': 'management_command',
                    'threshold_multiplier': threshold_multiplier,
                    'timestamp': timezone.now().isoformat()
                }
                
                alert = AlertLog.objects.create(
                    rule=rule,
                    trigger_value=test_value,
                    threshold_value=rule.threshold_value,
                    message=f"{message}: {rule.name}",
                    details=test_details,
                    email_sent=rule.send_email,
                    telegram_sent=rule.send_telegram,
                    sms_sent=rule.send_sms
                )
                
                # Update last triggered time
                rule.last_triggered = timezone.now()
                rule.save(update_fields=['last_triggered'])
                
                # Trigger notification task
                test_alert_rule.delay(rule.id)
                
                tested_count += 1
                self.stdout.write(f'  - Tested rule {rule.id}: {rule.name} (Alert ID: {alert.id})')
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'  - Failed to test rule {rule.id}: {rule.name} - {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Test complete:'))
        self.stdout.write(f'  - Total rules found: {rules.count()}')
        self.stdout.write(f'  - Successfully tested: {tested_count}')
        self.stdout.write(f'  - Skipped: {skipped_count}')
        self.stdout.write(f'  - Failed: {failed_count}')
        
        if tested_count > 0:
            self.stdout.write(self.style.SUCCESS('Test alerts have been created and notifications have been queued.'))
            self.stdout.write(self.style.SUCCESS('Check Celery worker logs for notification delivery status.'))
