# =============================================================================
# auto_mod/management/commands/export_moderation_log.py
# =============================================================================

"""
Django management command to export moderation logs.
"""

import csv
import json
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.http import HttpResponse

from ...models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal, 
    ModerationQueue, ProofScanner, AutoApprovalRule
)
from ...choices import ModerationStatus, AppealStatus, AppealOutcome
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export moderation logs in various formats'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'json', 'excel'],
            default='csv',
            help='Export format (default: csv)'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (default: auto-generated)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Number of days to export (default: 30)'
        )
        parser.add_argument(
            '--data-type',
            type=str,
            choices=['submissions', 'decisions', 'appeals', 'queue', 'scanners', 'rules', 'all'],
            default='all',
            help='Type of data to export (default: all)'
        )
        parser.add_argument(
            '--status',
            type=str,
            action='append',
            help='Filter by status (can be used multiple times)'
        )
        parser.add_argument(
            '--submission-type',
            type=str,
            action='append',
            help='Filter by submission type (can be used multiple times)'
        )
        parser.add_argument(
            '--include-metadata',
            action='store_true',
            help='Include detailed metadata fields'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output file'
        )
        parser.add_argument(
            '--split-by-date',
            action='store_true',
            help='Split output into separate files by date'
        )
    
    def handle(self, *args, **options):
        """Execute the export command."""
        self.stdout.write(
            self.style.SUCCESS('Starting moderation log export...')
        )
        
        # Parse parameters
        export_format = options.get('format', 'csv')
        output_file = options.get('output_file')
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        days_back = options.get('days_back', 30)
        data_type = options.get('data_type', 'all')
        status_filters = options.get('status', [])
        submission_type_filters = options.get('submission_type', [])
        include_metadata = options.get('include_metadata', False)
        compress = options.get('compress', False)
        split_by_date = options.get('split_by_date', False)
        
        try:
            # Parse date range
            start_dt, end_dt = self._parse_date_range(start_date, end_date, days_back)
            
            # Generate output filename if not provided
            if not output_file:
                output_file = self._generate_output_filename(export_format, data_type, start_dt, end_dt)
            
            self.stdout.write(f'Exporting data from {start_dt.date()} to {end_dt.date()}')
            self.stdout.write(f'Output format: {export_format}')
            self.stdout.write(f'Data type: {data_type}')
            
            # Get data
            export_data = self._get_export_data(
                data_type, start_dt, end_dt, status_filters, submission_type_filters
            )
            
            if not export_data:
                self.stdout.write(
                    self.style.WARNING('No data found for the specified criteria.')
                )
                return
            
            # Export data
            if split_by_date:
                results = self._export_split_by_date(
                    export_data, export_format, output_file, include_metadata, compress
                )
            else:
                results = self._export_data(
                    export_data, export_format, output_file, include_metadata, compress
                )
            
            # Display results
            self._display_export_results(results)
            
        except Exception as exc:
            logger.error(f"Export failed: {exc}")
            raise CommandError(f"Export failed: {exc}")
    
    def _parse_date_range(self, start_date, end_date, days_back):
        """Parse and validate date range."""
        now = timezone.now()
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                start_dt = timezone.make_aware(datetime.combine(start_dt, datetime.min.time()))
            except ValueError:
                raise CommandError(f"Invalid start date format: {start_date}")
        else:
            start_dt = now - timedelta(days=days_back)
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                end_dt = timezone.make_aware(datetime.combine(end_dt, datetime.max.time()))
            except ValueError:
                raise CommandError(f"Invalid end date format: {end_date}")
        else:
            end_dt = now
        
        if start_dt >= end_dt:
            raise CommandError("Start date must be before end date")
        
        return start_dt, end_dt
    
    def _generate_output_filename(self, export_format, data_type, start_dt, end_dt):
        """Generate output filename."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        date_range = f"{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}"
        
        filename = f"moderation_log_{data_type}_{date_range}_{timestamp}.{export_format}"
        
        # Create exports directory if it doesn't exist
        exports_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        return os.path.join(exports_dir, filename)
    
    def _get_export_data(self, data_type, start_dt, end_dt, status_filters, submission_type_filters):
        """Get data for export."""
        data = {}
        
        if data_type in ['submissions', 'all']:
            data['submissions'] = self._get_submissions_data(
                start_dt, end_dt, status_filters, submission_type_filters
            )
        
        if data_type in ['decisions', 'all']:
            data['decisions'] = self._get_decisions_data(
                start_dt, end_dt, status_filters, submission_type_filters
            )
        
        if data_type in ['appeals', 'all']:
            data['appeals'] = self._get_appeals_data(
                start_dt, end_dt, status_filters, submission_type_filters
            )
        
        if data_type in ['queue', 'all']:
            data['queue'] = self._get_queue_data(
                start_dt, end_dt, status_filters, submission_type_filters
            )
        
        if data_type in ['scanners', 'all']:
            data['scanners'] = self._get_scanners_data(
                start_dt, end_dt, status_filters, submission_type_filters
            )
        
        if data_type in ['rules', 'all']:
            data['rules'] = self._get_rules_data()
        
        return data
    
    def _get_submissions_data(self, start_dt, end_dt, status_filters, submission_type_filters):
        """Get submissions data."""
        queryset = SuspiciousSubmission.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        )
        
        if status_filters:
            queryset = queryset.filter(status__in=status_filters)
        
        if submission_type_filters:
            queryset = queryset.filter(submission_type__in=submission_type_filters)
        
        submissions = []
        for sub in queryset.select_related('user').prefetch_related('decisions', 'signals'):
            data = {
                'id': str(sub.pk),
                'content_id': sub.content_id,
                'submission_type': sub.submission_type,
                'status': sub.status,
                'user_id': str(sub.user.pk),
                'username': sub.user.username,
                'created_at': sub.created_at.isoformat(),
                'updated_at': sub.updated_at.isoformat(),
                'risk_score': sub.risk_score,
                'ai_confidence': sub.ai_confidence,
                'flag_reason': sub.flag_reason,
                'decision_count': sub.decisions.count(),
                'signal_count': sub.signals.count()
            }
            
            if sub.metadata:
                data['metadata'] = sub.metadata
            
            submissions.append(data)
        
        return submissions
    
    def _get_decisions_data(self, start_dt, end_dt, status_filters, submission_type_filters):
        """Get decisions data."""
        queryset = ModerationDecision.objects.filter(
            decided_at__gte=start_dt,
            decided_at__lte=end_dt
        )
        
        if status_filters:
            queryset = queryset.filter(decision_type__in=status_filters)
        
        if submission_type_filters:
            queryset = queryset.filter(submission__submission_type__in=submission_type_filters)
        
        decisions = []
        for decision in queryset.select_related('submission', 'decided_by', 'applied_rule'):
            data = {
                'id': str(decision.pk),
                'submission_id': str(decision.submission.pk),
                'content_id': decision.submission.content_id,
                'submission_type': decision.submission.submission_type,
                'decision_type': decision.decision_type,
                'reason': decision.reason,
                'confidence': decision.confidence,
                'is_automated': decision.is_automated,
                'decided_by_id': str(decision.decided_by.pk) if decision.decided_by else None,
                'decided_by_username': decision.decided_by.username if decision.decided_by else None,
                'decided_at': decision.decided_at.isoformat(),
                'applied_rule_id': str(decision.applied_rule.pk) if decision.applied_rule else None,
                'applied_rule_name': decision.applied_rule.name if decision.applied_rule else None,
                'appeal_count': decision.appeals.count() if hasattr(decision, 'appeals') else 0
            }
            
            decisions.append(data)
        
        return decisions
    
    def _get_appeals_data(self, start_dt, end_dt, status_filters, submission_type_filters):
        """Get appeals data."""
        queryset = ModerationAppeal.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt
        )
        
        if status_filters:
            queryset = queryset.filter(status__in=status_filters)
        
        if submission_type_filters:
            queryset = queryset.filter(submission__submission_type__in=submission_type_filters)
        
        appeals = []
        for appeal in queryset.select_related('user', 'original_decision', 'submission', 'reviewed_by'):
            data = {
                'id': str(appeal.pk),
                'submission_id': str(appeal.submission.pk),
                'content_id': appeal.submission.content_id,
                'submission_type': appeal.submission.submission_type,
                'user_id': str(appeal.user.pk),
                'username': appeal.user.username,
                'original_decision_id': str(appeal.original_decision.pk),
                'original_decision_type': appeal.original_decision.decision_type,
                'reason': appeal.reason,
                'status': appeal.status,
                'final_outcome': appeal.final_outcome,
                'final_reason': appeal.final_reason,
                'reviewed_by_id': str(appeal.reviewed_by.pk) if appeal.reviewed_by else None,
                'reviewed_by_username': appeal.reviewed_by.username if appeal.reviewed_by else None,
                'created_at': appeal.created_at.isoformat(),
                'reviewed_at': appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
                'resolved_at': appeal.resolved_at.isoformat() if appeal.resolved_at else None,
                'escalation_level': appeal.escalation_level
            }
            
            if appeal.additional_data:
                data['additional_data'] = appeal.additional_data
            
            appeals.append(data)
        
        return appeals
    
    def _get_queue_data(self, start_dt, end_dt, status_filters, submission_type_filters):
        """Get queue data."""
        queryset = ModerationQueue.objects.filter(
            queued_at__gte=start_dt,
            queued_at__lte=end_dt
        )
        
        if submission_type_filters:
            queryset = queryset.filter(submission__submission_type__in=submission_type_filters)
        
        queue_items = []
        for item in queryset.select_related('submission', 'assigned_to', 'assigned_by'):
            data = {
                'id': str(item.pk),
                'submission_id': str(item.submission.pk),
                'content_id': item.submission.content_id,
                'submission_type': item.submission.submission_type,
                'priority': item.priority,
                'escalation_level': item.escalation_level,
                'assigned_to_id': str(item.assigned_to.pk) if item.assigned_to else None,
                'assigned_to_username': item.assigned_to.username if item.assigned_to else None,
                'assigned_by_id': str(item.assigned_by.pk) if item.assigned_by else None,
                'assigned_by_username': item.assigned_by.username if item.assigned_by else None,
                'queued_at': item.queued_at.isoformat(),
                'assigned_at': item.assigned_at.isoformat() if item.assigned_at else None,
                'completed_at': item.completed_at.isoformat() if item.completed_at else None,
                'due_at': item.due_at.isoformat() if item.due_at else None,
                'processing_notes': item.processing_notes,
                'is_overdue': item.is_overdue,
                'should_escalate': item.should_escalate
            }
            
            queue_items.append(data)
        
        return queue_items
    
    def _get_scanners_data(self, start_dt, end_dt, status_filters, submission_type_filters):
        """Get scanner data."""
        queryset = ProofScanner.objects.filter(
            started_at__gte=start_dt,
            started_at__lte=end_dt
        )
        
        if status_filters:
            queryset = queryset.filter(status__in=status_filters)
        
        if submission_type_filters:
            queryset = queryset.filter(submission__submission_type__in=submission_type_filters)
        
        scanners = []
        for scanner in queryset.select_related('submission', 'initiated_by'):
            data = {
                'id': str(scanner.pk),
                'submission_id': str(scanner.submission.pk),
                'content_id': scanner.submission.content_id,
                'submission_type': scanner.submission.submission_type,
                'scan_type': scanner.scan_type,
                'status': scanner.status,
                'initiated_by_id': str(scanner.initiated_by.pk) if scanner.initiated_by else None,
                'initiated_by_username': scanner.initiated_by.username if scanner.initiated_by else None,
                'started_at': scanner.started_at.isoformat(),
                'completed_at': scanner.completed_at.isoformat() if scanner.completed_at else None,
                'duration_seconds': scanner.duration_seconds,
                'result_data': scanner.result_data
            }
            
            scanners.append(data)
        
        return scanners
    
    def _get_rules_data(self):
        """Get rules data."""
        rules = []
        for rule in AutoApprovalRule.objects.select_related('created_by').all():
            data = {
                'id': str(rule.pk),
                'name': rule.name,
                'submission_type': rule.submission_type,
                'action': rule.action,
                'priority': rule.priority,
                'confidence_threshold': rule.confidence_threshold,
                'condition_count': rule.condition_count,
                'is_active': rule.is_active,
                'is_system': rule.is_system,
                'created_by_id': str(rule.created_by.pk),
                'created_by_username': rule.created_by.username,
                'created_at': rule.created_at.isoformat(),
                'updated_at': rule.updated_at.isoformat(),
                'conditions': rule.conditions
            }
            
            rules.append(data)
        
        return rules
    
    def _export_split_by_date(self, export_data, export_format, base_filename, include_metadata, compress):
        """Export data split by date."""
        results = {
            'files_created': 0,
            'total_records': 0,
            'files': []
        }
        
        # Group data by date
        for data_type, records in export_data.items():
            if not records:
                continue
            
            # Group by date
            date_groups = {}
            for record in records:
                date_key = self._extract_date_key(record, data_type)
                if date_key not in date_groups:
                    date_groups[date_key] = []
                date_groups[date_key].append(record)
            
            # Export each date group
            for date_key, date_records in date_groups.items():
                filename = self._generate_split_filename(base_filename, data_type, date_key, export_format)
                
                if export_format == 'csv':
                    self._export_csv({data_type: date_records}, filename, include_metadata)
                elif export_format == 'json':
                    self._export_json({data_type: date_records}, filename, include_metadata)
                elif export_format == 'excel':
                    self._export_excel({data_type: date_records}, filename, include_metadata)
                
                if compress:
                    filename = self._compress_file(filename)
                
                results['files_created'] += 1
                results['total_records'] += len(date_records)
                results['files'].append(filename)
                
                self.stdout.write(f"Created: {filename} ({len(date_records)} records)")
        
        return results
    
    def _extract_date_key(self, record, data_type):
        """Extract date key for grouping."""
        date_fields = {
            'submissions': 'created_at',
            'decisions': 'decided_at',
            'appeals': 'created_at',
            'queue': 'queued_at',
            'scanners': 'started_at',
            'rules': 'created_at'
        }
        
        date_field = date_fields.get(data_type, 'created_at')
        date_str = record.get(date_field, '')
        
        # Extract date part (YYYY-MM-DD)
        if date_str:
            return date_str[:10]
        else:
            return 'unknown_date'
    
    def _generate_split_filename(self, base_filename, data_type, date_key, export_format):
        """Generate filename for split export."""
        base_parts = os.path.splitext(base_filename)
        return f"{base_parts[0]}_{data_type}_{date_key}.{export_format}"
    
    def _export_data(self, export_data, export_format, output_file, include_metadata, compress):
        """Export data to single file."""
        if export_format == 'csv':
            self._export_csv(export_data, output_file, include_metadata)
        elif export_format == 'json':
            self._export_json(export_data, output_file, include_metadata)
        elif export_format == 'excel':
            self._export_excel(export_data, output_file, include_metadata)
        
        if compress:
            output_file = self._compress_file(output_file)
        
        total_records = sum(len(records) for records in export_data.values())
        
        return {
            'files_created': 1,
            'total_records': total_records,
            'files': [output_file]
        }
    
    def _export_csv(self, export_data, output_file, include_metadata):
        """Export data to CSV format."""
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            for data_type, records in export_data.items():
                if not records:
                    continue
                
                writer = csv.DictWriter(csvfile, fieldnames=self._get_csv_fields(records[0], include_metadata))
                writer.writeheader()
                
                for record in records:
                    # Flatten nested objects for CSV
                    flattened = self._flatten_record(record, include_metadata)
                    writer.writerow(flattened)
    
    def _export_json(self, export_data, output_file, include_metadata):
        """Export data to JSON format."""
        export_json = {
            'export_info': {
                'timestamp': timezone.now().isoformat(),
                'total_records': sum(len(records) for records in export_data.values()),
                'data_types': list(export_data.keys())
            },
            'data': export_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_json, jsonfile, indent=2, ensure_ascii=False)
    
    def _export_excel(self, export_data, output_file, include_metadata):
        """Export data to Excel format."""
        try:
            import pandas as pd
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                for data_type, records in export_data.items():
                    if not records:
                        continue
                    
                    # Convert records to DataFrame
                    df = pd.DataFrame(records)
                    
                    # Flatten nested objects
                    df = self._flatten_dataframe(df, include_metadata)
                    
                    # Write to Excel sheet
                    df.to_excel(writer, sheet_name=data_type[:31], index=False)
        
        except ImportError:
            raise CommandError("pandas and openpyxl are required for Excel export")
    
    def _flatten_record(self, record, include_metadata):
        """Flatten nested record for CSV export."""
        flattened = {}
        
        for key, value in record.items():
            if isinstance(value, dict):
                if include_metadata or key != 'metadata':
                    # Flatten nested dict
                    for nested_key, nested_value in value.items():
                        flattened[f"{key}_{nested_key}"] = nested_value
            elif isinstance(value, list):
                flattened[key] = str(value)  # Convert list to string
            else:
                flattened[key] = value
        
        return flattened
    
    def _flatten_dataframe(self, df, include_metadata):
        """Flatten nested DataFrame columns."""
        # This is a simplified version - in practice, you might want more sophisticated flattening
        return df
    
    def _get_csv_fields(self, sample_record, include_metadata):
        """Get CSV field names from sample record."""
        flattened = self._flatten_record(sample_record, include_metadata)
        return list(flattened.keys())
    
    def _compress_file(self, filename):
        """Compress output file."""
        import gzip
        import shutil
        
        compressed_filename = f"{filename}.gz"
        
        with open(filename, 'rb') as f_in:
            with gzip.open(compressed_filename, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove original file
        os.remove(filename)
        
        return compressed_filename
    
    def _display_export_results(self, results):
        """Display export results."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('EXPORT RESULTS'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Files created: {results['files_created']}")
        self.stdout.write(f"Total records: {results['total_records']}")
        
        if results['files']:
            self.stdout.write('\nFiles created:')
            for filename in results['files']:
                file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                self.stdout.write(f"  {filename} ({file_size:,} bytes)")
        
        self.stdout.write('='*50)
        
        # Log summary
        logger.info(
            f"Export completed: {results['files_created']} files, "
            f"{results['total_records']} total records"
        )
