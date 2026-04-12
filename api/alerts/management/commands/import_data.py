"""
Django Management Command: Import Alert Data
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import json
import csv
import logging

from alerts.models.core import AlertRule, AlertLog
from alerts.models.channel import AlertChannel
from alerts.models.incident import Incident

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import alert data from various formats'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['rules', 'logs', 'channels', 'incidents'],
            required=True,
            help='Model to import into'
        )
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Input file path'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='Input file format (default: json)'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing records instead of skipping'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for import operations (default: 100)'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate data without importing'
        )
        parser.add_argument(
            '--skip-invalid',
            action='store_true',
            help='Skip invalid records instead of failing'
        )
    
    def handle(self, *args, **options):
        model_name = options['model']
        file_path = options['file']
        format_type = options['format']
        update_existing = options['update_existing']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        validate_only = options['validate_only']
        skip_invalid = options['skip_invalid']
        
        self.stdout.write(self.style.SUCCESS(f'Importing {model_name} data from {file_path}'))
        
        # Read input file
        try:
            data = self._read_input_file(file_path, format_type)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to read input file: {str(e)}'))
            return
        
        if not data:
            self.stdout.write(self.style.WARNING('No data found in input file'))
            return
        
        self.stdout.write(f'Found {len(data)} records to import')
        
        # Validate data
        if validate_only:
            self._validate_data(data, model_name)
            return
        
        # Import data
        imported_count = 0
        skipped_count = 0
        failed_count = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            
            for record in batch:
                try:
                    if dry_run:
                        self.stdout.write(f'  - Would import: {record.get("name", record.get("id", "unknown"))}')
                        imported_count += 1
                        continue
                    
                    # Import record
                    result = self._import_record(record, model_name, update_existing, skip_invalid)
                    
                    if result == 'imported':
                        imported_count += 1
                    elif result == 'skipped':
                        skipped_count += 1
                    elif result == 'failed':
                        failed_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    if not skip_invalid:
                        self.stdout.write(self.style.ERROR(f'  - Failed to import record: {str(e)}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'  - Skipped invalid record: {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Import complete:'))
        self.stdout.write(f'  - Total records: {len(data)}')
        self.stdout.write(f'  - Imported: {imported_count}')
        self.stdout.write(f'  - Skipped: {skipped_count}')
        self.stdout.write(f'  - Failed: {failed_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No records were actually imported'))
    
    def _read_input_file(self, file_path, format_type):
        """Read input file and return data"""
        if format_type == 'json':
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif format_type == 'csv':
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        else:
            raise ValueError(f'Unsupported format: {format_type}')
    
    def _validate_data(self, data, model_name):
        """Validate data before import"""
        self.stdout.write(f'Validating {len(data)} {model_name} records...')
        
        valid_count = 0
        invalid_count = 0
        
        for i, record in enumerate(data):
            try:
                self._validate_record(record, model_name)
                valid_count += 1
            except Exception as e:
                invalid_count += 1
                self.stdout.write(self.style.WARNING(f'  - Record {i+1}: Invalid - {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Validation complete:'))
        self.stdout.write(f'  - Valid: {valid_count}')
        self.stdout.write(f'  - Invalid: {invalid_count}')
        
        if invalid_count > 0:
            self.stdout.write(self.style.WARNING('Some records failed validation. Use --skip-invalid to skip them during import.'))
    
    def _validate_record(self, record, model_name):
        """Validate individual record"""
        if model_name == 'rules':
            self._validate_rule_record(record)
        elif model_name == 'logs':
            self._validate_log_record(record)
        elif model_name == 'channels':
            self._validate_channel_record(record)
        elif model_name == 'incidents':
            self._validate_incident_record(record)
    
    def _validate_rule_record(self, record):
        """Validate alert rule record"""
        required_fields = ['name', 'alert_type', 'severity', 'threshold_value']
        for field in required_fields:
            if field not in record:
                raise ValueError(f'Missing required field: {field}')
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if record['severity'] not in valid_severities:
            raise ValueError(f'Invalid severity: {record["severity"]}')
        
        # Validate threshold value
        try:
            float(record['threshold_value'])
        except ValueError:
            raise ValueError('threshold_value must be a number')
    
    def _validate_log_record(self, record):
        """Validate alert log record"""
        required_fields = ['rule_id', 'trigger_value', 'threshold_value', 'message']
        for field in required_fields:
            if field not in record:
                raise ValueError(f'Missing required field: {field}')
        
        # Validate rule exists
        if not AlertRule.objects.filter(id=record['rule_id']).exists():
            raise ValueError(f'AlertRule with id {record["rule_id"]} does not exist')
        
        # Validate numeric fields
        try:
            float(record['trigger_value'])
            float(record['threshold_value'])
        except ValueError:
            raise ValueError('trigger_value and threshold_value must be numbers')
    
    def _validate_channel_record(self, record):
        """Validate alert channel record"""
        required_fields = ['name', 'channel_type']
        for field in required_fields:
            if field not in record:
                raise ValueError(f'Missing required field: {field}')
        
        # Validate channel type
        valid_types = ['email', 'sms', 'telegram', 'webhook', 'slack', 'discord']
        if record['channel_type'] not in valid_types:
            raise ValueError(f'Invalid channel type: {record["channel_type"]}')
    
    def _validate_incident_record(self, record):
        """Validate incident record"""
        required_fields = ['title', 'severity', 'status']
        for field in required_fields:
            if field not in record:
                raise ValueError(f'Missing required field: {field}')
        
        # Validate severity
        valid_severities = ['low', 'medium', 'high', 'critical']
        if record['severity'] not in valid_severities:
            raise ValueError(f'Invalid severity: {record["severity"]}')
        
        # Validate status
        valid_statuses = ['open', 'investigating', 'identified', 'monitoring', 'resolved', 'closed']
        if record['status'] not in valid_statuses:
            raise ValueError(f'Invalid status: {record["status"]}')
    
    def _import_record(self, record, model_name, update_existing, skip_invalid):
        """Import individual record"""
        try:
            if model_name == 'rules':
                return self._import_rule_record(record, update_existing)
            elif model_name == 'logs':
                return self._import_log_record(record, update_existing)
            elif model_name == 'channels':
                return self._import_channel_record(record, update_existing)
            elif model_name == 'incidents':
                return self._import_incident_record(record, update_existing)
        except Exception as e:
            if skip_invalid:
                return 'failed'
            else:
                raise
    
    def _import_rule_record(self, record, update_existing):
        """Import alert rule record"""
        # Check if rule already exists
        existing_rule = AlertRule.objects.filter(name=record['name']).first()
        
        if existing_rule:
            if not update_existing:
                return 'skipped'
            rule = existing_rule
        else:
            rule = AlertRule()
        
        # Set fields
        rule.name = record['name']
        rule.alert_type = record['alert_type']
        rule.severity = record['severity']
        rule.threshold_value = float(record['threshold_value'])
        rule.description = record.get('description', '')
        rule.is_active = record.get('is_active', True)
        rule.cooldown_minutes = record.get('cooldown_minutes', 30)
        
        # Additional fields
        if 'send_email' in record:
            rule.send_email = record['send_email']
        if 'send_telegram' in record:
            rule.send_telegram = record['send_telegram']
        if 'send_sms' in record:
            rule.send_sms = record['send_sms']
        
        rule.save()
        return 'imported'
    
    def _import_log_record(self, record, update_existing):
        """Import alert log record"""
        # Get rule
        try:
            rule = AlertRule.objects.get(id=record['rule_id'])
        except AlertRule.DoesNotExist:
            raise ValueError(f'AlertRule with id {record["rule_id"]} does not exist')
        
        # Create alert log
        alert_log = AlertLog(
            rule=rule,
            trigger_value=float(record['trigger_value']),
            threshold_value=float(record['threshold_value']),
            message=record['message'],
            details=record.get('details', {}),
            is_resolved=record.get('is_resolved', False)
        )
        
        # Additional fields
        if 'triggered_at' in record:
            alert_log.triggered_at = record['triggered_at']
        if 'resolved_at' in record:
            alert_log.resolved_at = record['resolved_at']
        if 'resolution_note' in record:
            alert_log.resolution_note = record['resolution_note']
        
        alert_log.save()
        return 'imported'
    
    def _import_channel_record(self, record, update_existing):
        """Import alert channel record"""
        # Check if channel already exists
        existing_channel = AlertChannel.objects.filter(name=record['name']).first()
        
        if existing_channel:
            if not update_existing:
                return 'skipped'
            channel = existing_channel
        else:
            channel = AlertChannel()
        
        # Set fields
        channel.name = record['name']
        channel.channel_type = record['channel_type']
        channel.description = record.get('description', '')
        channel.is_enabled = record.get('is_enabled', True)
        channel.priority = record.get('priority', 5)
        
        # Additional fields
        if 'config' in record:
            channel.config = record['config']
        if 'webhook_url' in record:
            channel.webhook_url = record['webhook_url']
        
        channel.save()
        return 'imported'
    
    def _import_incident_record(self, record, update_existing):
        """Import incident record"""
        # Check if incident already exists
        existing_incident = Incident.objects.filter(title=record['title']).first()
        
        if existing_incident:
            if not update_existing:
                return 'skipped'
            incident = existing_incident
        else:
            incident = Incident()
        
        # Set fields
        incident.title = record['title']
        incident.severity = record['severity']
        incident.status = record['status']
        incident.description = record.get('description', '')
        incident.impact = record.get('impact', 'minor')
        incident.urgency = record.get('urgency', 'medium')
        
        # Additional fields
        if 'detected_at' in record:
            incident.detected_at = record['detected_at']
        if 'resolved_at' in record:
            incident.resolved_at = record['resolved_at']
        if 'root_cause' in record:
            incident.root_cause = record['root_cause']
        
        incident.save()
        return 'imported'
