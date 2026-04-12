"""
Django Management Command: Generate Alert Reports
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from alerts.models.reporting import AlertReport
from alerts.tasks.reporting import (
    generate_daily_reports, generate_weekly_reports, generate_monthly_reports,
    generate_sla_reports, generate_performance_reports
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate alert reports for specified periods'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['daily', 'weekly', 'monthly', 'sla', 'performance', 'all'],
            default='daily',
            help='Type of report to generate (default: daily)'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date for report generation (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days back from current date (default: 1)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'pdf', 'csv', 'html'],
            default='json',
            help='Report format (default: json)'
        )
        parser.add_argument(
            '--recipients',
            type=str,
            help='Comma-separated list of email recipients'
        )
        parser.add_argument(
            '--auto-distribute',
            action='store_true',
            help='Automatically distribute report to recipients'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without actually generating'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if report already exists'
        )
    
    def handle(self, *args, **options):
        report_type = options['type']
        date_str = options['date']
        days = options['days']
        format_type = options['format']
        recipients = options.get('recipients')
        auto_distribute = options['auto_distribute']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS(f'Generating {report_type} reports with format: {format_type}'))
        
        # Parse date
        if date_str:
            try:
                target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return
        else:
            target_date = timezone.now().date() - timedelta(days=days-1)
        
        # Parse recipients
        recipient_list = []
        if recipients:
            recipient_list = [email.strip() for email in recipients.split(',')]
        
        # Generate reports
        generated_count = 0
        failed_count = 0
        
        if report_type == 'all':
            report_types = ['daily', 'weekly', 'monthly', 'sla', 'performance']
        else:
            report_types = [report_type]
        
        for r_type in report_types:
            try:
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'DRY RUN - Would generate {r_type} report for {target_date}'))
                    generated_count += 1
                    continue
                
                # Check if report already exists
                if not force:
                    existing_report = AlertReport.objects.filter(
                        report_type=r_type,
                        start_date__lte=target_date,
                        end_date__gte=target_date,
                        status='completed'
                    ).first()
                    
                    if existing_report:
                        self.stdout.write(self.style.WARNING(f'Skipping {r_type} report - already exists for {target_date}'))
                        continue
                
                # Trigger appropriate task
                if r_type == 'daily':
                    generate_daily_reports.delay()
                elif r_type == 'weekly':
                    generate_weekly_reports.delay()
                elif r_type == 'monthly':
                    generate_monthly_reports.delay()
                elif r_type == 'sla':
                    generate_sla_reports.delay()
                elif r_type == 'performance':
                    generate_performance_reports.delay()
                
                generated_count += 1
                self.stdout.write(f'  - Queued {r_type} report generation for {target_date}')
                
            except Exception as e:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f'  - Failed to generate {r_type} report: {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Report generation complete:'))
        self.stdout.write(f'  - Report types: {", ".join(report_types)}')
        self.stdout.write(f'  - Target date: {target_date}')
        self.stdout.write(f'  - Format: {format_type}')
        self.stdout.write(f'  - Successfully queued: {generated_count}')
        self.stdout.write(f'  - Failed: {failed_count}')
        
        if recipient_list:
            self.stdout.write(f'  - Recipients: {", ".join(recipient_list)}')
        
        if auto_distribute:
            self.stdout.write(f'  - Auto-distribute: enabled')
        
        if generated_count > 0:
            self.stdout.write(self.style.SUCCESS('Reports have been queued for generation. Check Celery worker logs for progress.'))
