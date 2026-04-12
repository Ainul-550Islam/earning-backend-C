"""
Django Management Command: Export Alert Data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import json
import csv
import logging

from alerts.models.core import AlertRule, AlertLog, Notification
from alerts.models.channel import AlertChannel, ChannelHealthLog
from alerts.models.incident import Incident, IncidentTimeline
from alerts.models.reporting import AlertReport

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export alert data to various formats'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['rules', 'logs', 'notifications', 'channels', 'incidents', 'reports', 'all'],
            default='all',
            help='Model to export (default: all)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv', 'xlsx'],
            default='json',
            help='Export format (default: json)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Export data from last N days (default: 30)'
        )
        parser.add_argument(
            '--fields',
            type=str,
            help='Comma-separated list of fields to export'
        )
        parser.add_argument(
            '--filters',
            type=str,
            help='JSON string of filters to apply'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to export'
        )
        parser.add_argument(
            '--include-relations',
            action='store_true',
            help='Include related model fields'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress output file'
        )
    
    def handle(self, *args, **options):
        model = options['model']
        format_type = options['format']
        output_path = options.get('output')
        days = options['days']
        fields = options.get('fields')
        filters = options.get('filters')
        limit = options.get('limit')
        include_relations = options['include_relations']
        compress = options['compress']
        
        self.stdout.write(self.style.SUCCESS(f'Exporting {model} data in {format_type} format'))
        
        # Parse filters
        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR('Invalid JSON in filters parameter'))
                return
        
        # Parse fields
        field_list = None
        if fields:
            field_list = [field.strip() for field in fields.split(',')]
        
        # Set time filter
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Export data
        total_exported = 0
        
        if model == 'all':
            models_to_export = ['rules', 'logs', 'notifications', 'channels', 'incidents', 'reports']
        else:
            models_to_export = [model]
        
        for export_model in models_to_export:
            try:
                exported_count = self._export_model(
                    export_model, format_type, output_path, cutoff_date,
                    filter_dict, field_list, limit, include_relations, compress
                )
                total_exported += exported_count
                self.stdout.write(f'  - Exported {exported_count} {export_model} records')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Failed to export {export_model}: {str(e)}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Export complete:'))
        self.stdout.write(f'  - Total records exported: {total_exported}')
        self.stdout.write(f'  - Format: {format_type}')
        self.stdout.write(f'  - Period: Last {days} days')
        
        if output_path:
            self.stdout.write(f'  - Output: {output_path}')
        else:
            self.stdout.write(f'  - Output: stdout')
    
    def _export_model(self, model_name, format_type, output_path, cutoff_date, filters, fields, limit, include_relations, compress):
        """Export specific model data"""
        
        # Get model class
        model_class = self._get_model_class(model_name)
        if not model_class:
            raise ValueError(f'Unknown model: {model_name}')
        
        # Build queryset
        queryset = self._build_queryset(model_class, cutoff_date, filters, limit, include_relations)
        
        # Get data
        if format_type == 'json':
            data = self._export_to_json(queryset, fields, include_relations)
        elif format_type == 'csv':
            data = self._export_to_csv(queryset, fields, include_relations, model_name)
        elif format_type == 'xlsx':
            data = self._export_to_xlsx(queryset, fields, include_relations, model_name)
        else:
            raise ValueError(f'Unsupported format: {format_type}')
        
        # Write output
        if output_path:
            self._write_to_file(data, output_path, compress)
        else:
            self.stdout.write(data)
        
        return queryset.count()
    
    def _get_model_class(self, model_name):
        """Get model class by name"""
        model_map = {
            'rules': AlertRule,
            'logs': AlertLog,
            'notifications': Notification,
            'channels': AlertChannel,
            'incidents': Incident,
            'reports': AlertReport
        }
        return model_map.get(model_name)
    
    def _build_queryset(self, model_class, cutoff_date, filters, limit, include_relations):
        """Build queryset for export"""
        queryset = model_class.objects.all()
        
        # Apply time filter
        if cutoff_date:
            if hasattr(model_class, 'triggered_at'):
                queryset = queryset.filter(triggered_at__gte=cutoff_date)
            elif hasattr(model_class, 'created_at'):
                queryset = queryset.filter(created_at__gte=cutoff_date)
            elif hasattr(model_class, 'detected_at'):
                queryset = queryset.filter(detected_at__gte=cutoff_date)
        
        # Apply custom filters
        for key, value in filters.items():
            queryset = queryset.filter(**{key: value})
        
        # Include relations
        if include_relations:
            if model_class == AlertLog:
                queryset = queryset.select_related('rule', 'resolved_by')
            elif model_class == Notification:
                queryset = queryset.select_related('alert_log', 'alert_log__rule')
            elif model_class == Incident:
                queryset = queryset.select_related('assigned_to')
        
        # Apply limit
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def _export_to_json(self, queryset, fields, include_relations):
        """Export data to JSON format"""
        data = []
        
        for obj in queryset:
            if fields:
                # Export specific fields
                item = {}
                for field in fields:
                    value = getattr(obj, field, None)
                    if value and hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    item[field] = value
            else:
                # Export all fields
                item = self._model_to_dict(obj, include_relations)
            
            data.append(item)
        
        return json.dumps(data, indent=2, default=str)
    
    def _export_to_csv(self, queryset, fields, include_relations, model_name):
        """Export data to CSV format"""
        import io
        
        output = io.StringIO()
        
        if not fields:
            # Get fields from model
            fields = [field.name for field in queryset.model._meta.fields]
            if include_relations:
                fields.extend(['rule_name', 'resolved_by_username'])
        
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for obj in queryset:
            row = {}
            for field in fields:
                value = getattr(obj, field, None)
                if value and hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif hasattr(value, '__str__'):
                    value = str(value)
                row[field] = value
            writer.writerow(row)
        
        return output.getvalue()
    
    def _export_to_xlsx(self, queryset, fields, include_relations, model_name):
        """Export data to Excel format"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError('pandas is required for Excel export')
        
        # Convert to DataFrame
        data = []
        for obj in queryset:
            if fields:
                row = {}
                for field in fields:
                    value = getattr(obj, field, None)
                    if value and hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    row[field] = value
            else:
                row = self._model_to_dict(obj, include_relations)
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Save to Excel
        import io
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        
        return output.getvalue()
    
    def _model_to_dict(self, obj, include_relations):
        """Convert model instance to dictionary"""
        data = {}
        
        for field in obj._meta.fields:
            value = getattr(obj, field.name, None)
            if value and hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, '__str__'):
                value = str(value)
            data[field.name] = value
        
        if include_relations:
            # Add related fields
            if hasattr(obj, 'rule') and obj.rule:
                data['rule_name'] = obj.rule.name
            if hasattr(obj, 'resolved_by') and obj.resolved_by:
                data['resolved_by_username'] = obj.resolved_by.username
            if hasattr(obj, 'assigned_to') and obj.assigned_to:
                data['assigned_to_username'] = obj.assigned_to.username
        
        return data
    
    def _write_to_file(self, data, output_path, compress):
        """Write data to file"""
        if compress:
            import gzip
            filename = f"{output_path}.gz"
            with gzip.open(filename, 'wt') as f:
                f.write(data)
        else:
            with open(output_path, 'w') as f:
                f.write(data)
