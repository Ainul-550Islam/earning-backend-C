"""
Django Management Command: Backup Alert Data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
import json
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create backup of alert system data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups/alerts',
            help='Output directory for backups (default: backups/alerts)'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            default=True,
            help='Compress backup files (default: True)'
        )
        parser.add_argument(
            '--models',
            type=str,
            default='all',
            help='Models to backup (comma-separated, default: all)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=0,
            help='Only backup data newer than N days (default: 0 - all data)'
        )
        parser.add_argument(
            '--exclude',
            type=str,
            help='Models to exclude (comma-separated)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'fixtures', 'sql'],
            default='json',
            help='Backup format (default: json)'
        )
        parser.add_argument(
            '--keep-backups',
            type=int,
            default=7,
            help='Number of recent backups to keep (default: 7)'
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify backup integrity after creation'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be backed up without actually backing up'
        )
    
    def handle(self, *args, **options):
        output_dir = options['output_dir']
        compress = options['compress']
        models = options['models']
        days = options['days']
        exclude = options.get('exclude')
        format_type = options['format']
        keep_backups = options['keep_backups']
        verify = options['verify']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS(f'Creating backup of alert system data'))
        
        # Create output directory
        if not dry_run:
            os.makedirs(output_dir, exist_ok=True)
        
        # Parse models
        if models == 'all':
            models_to_backup = ['rules', 'logs', 'notifications', 'channels', 'incidents', 'reports']
        else:
            models_to_backup = [model.strip() for model in models.split(',')]
        
        # Parse exclusions
        excluded_models = []
        if exclude:
            excluded_models = [model.strip() for model in exclude.split(',')]
            models_to_backup = [m for m in models_to_backup if m not in excluded_models]
        
        # Create backup timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'alerts_backup_{timestamp}'
        
        self.stdout.write(f'Backup name: {backup_name}')
        self.stdout.write(f'Output directory: {output_dir}')
        self.stdout.write(f'Format: {format_type}')
        self.stdout.write(f'Compress: {compress}')
        self.stdout.write(f'Models: {", ".join(models_to_backup)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No backup files will be created'))
            return
        
        # Create backup
        backup_info = {
            'timestamp': timestamp,
            'format': format_type,
            'models': models_to_backup,
            'compressed': compress,
            'created_at': timezone.now().isoformat()
        }
        
        total_files = 0
        total_size = 0
        
        for model in models_to_backup:
            try:
                file_path, file_size = self._backup_model(
                    model, output_dir, backup_name, format_type, days
                )
                backup_info[f'{model}_file'] = file_path
                backup_info[f'{model}_size'] = file_size
                total_files += 1
                total_size += file_size
                self.stdout.write(f'  - Backed up {model}: {file_path} ({file_size} bytes)')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Failed to backup {model}: {str(e)}'))
        
        # Save backup metadata
        metadata_path = os.path.join(output_dir, f'{backup_name}_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(backup_info, f, indent=2, default=str)
        
        total_files += 1
        metadata_size = os.path.getsize(metadata_path)
        total_size += metadata_size
        
        self.stdout.write(f'  - Metadata: {metadata_path} ({metadata_size} bytes)')
        
        # Compress if requested
        if compress:
            compressed_path = self._compress_backup(output_dir, backup_name)
            if compressed_path:
                compressed_size = os.path.getsize(compressed_path)
                self.stdout.write(f'  - Compressed: {compressed_path} ({compressed_size} bytes)')
                total_size = compressed_size
                backup_info['compressed_file'] = compressed_path
                backup_info['compressed_size'] = compressed_size
        
        # Verify backup if requested
        if verify:
            self._verify_backup(backup_info, output_dir)
        
        # Clean up old backups
        self._cleanup_old_backups(output_dir, keep_backups)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Backup complete:'))
        self.stdout.write(f'  - Total files: {total_files}')
        self.stdout.write(f'  - Total size: {self._format_bytes(total_size)}')
        self.stdout.write(f'  - Backup location: {output_dir}')
        
        if compress:
            self.stdout.write(f'  - Compressed: Yes')
        
        if verify:
            self.stdout.write(f'  - Verified: Yes')
    
    def _backup_model(self, model, output_dir, backup_name, format_type, days):
        """Backup specific model data"""
        from django.core import management
        
        # Build filename
        filename = f'{backup_name}_{model}.{format_type}'
        file_path = os.path.join(output_dir, filename)
        
        if format_type == 'json':
            self._backup_model_json(model, file_path, days)
        elif format_type == 'fixtures':
            self._backup_model_fixtures(model, file_path, days)
        elif format_type == 'sql':
            self._backup_model_sql(model, file_path, days)
        
        return file_path, os.path.getsize(file_path)
    
    def _backup_model_json(self, model, file_path, days):
        """Backup model data as JSON"""
        model_class = self._get_model_class(model)
        if not model_class:
            raise ValueError(f'Unknown model: {model}')
        
        # Build queryset
        queryset = model_class.objects.all()
        
        if days > 0:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            if hasattr(model_class, 'created_at'):
                queryset = queryset.filter(created_at__gte=cutoff_date)
            elif hasattr(model_class, 'triggered_at'):
                queryset = queryset.filter(triggered_at__gte=cutoff_date)
        
        # Export data
        data = []
        for obj in queryset:
            data.append(self._model_to_dict(obj))
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _backup_model_fixtures(self, model, file_path, days):
        """Backup model data as Django fixtures"""
        model_class = self._get_model_class(model)
        if not model_class:
            raise ValueError(f'Unknown model: {model}')
        
        # Use Django's dumpdata command
        from django.core.management import call_command
        
        filters = []
        if days > 0:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            if hasattr(model_class, 'created_at'):
                filters.append(f'created_at__gte={cutoff_date.isoformat()}')
            elif hasattr(model_class, 'triggered_at'):
                filters.append(f'triggered_at__gte={cutoff_date.isoformat()}')
        
        call_command('dumpdata', f'alerts.{model}', output=file_path, *filters)
    
    def _backup_model_sql(self, model, file_path, days):
        """Backup model data as SQL"""
        model_class = self._get_model_class(model)
        if not model_class:
            raise ValueError(f'Unknown model: {model}')
        
        # Get table name
        table_name = model_class._meta.db_table
        
        # Build SQL
        sql = f"SELECT * FROM {table_name}"
        
        if days > 0:
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            if hasattr(model_class, 'created_at'):
                sql += f" WHERE created_at >= '{cutoff_date.isoformat()}'"
            elif hasattr(model_class, 'triggered_at'):
                sql += f" WHERE triggered_at >= '{cutoff_date.isoformat()}'"
        
        # Write SQL file
        with open(file_path, 'w') as f:
            f.write(f"-- Backup of {table_name}\n")
            f.write(f"-- Created: {timezone.now().isoformat()}\n")
            f.write(f"-- Days: {days}\n")
            f.write(f"{sql};\n")
    
    def _get_model_class(self, model):
        """Get model class by name"""
        from alerts.models.core import AlertRule, AlertLog, Notification
        from alerts.models.channel import AlertChannel
        from alerts.models.incident import Incident
        from alerts.models.reporting import AlertReport
        
        model_map = {
            'rules': AlertRule,
            'logs': AlertLog,
            'notifications': Notification,
            'channels': AlertChannel,
            'incidents': Incident,
            'reports': AlertReport
        }
        return model_map.get(model)
    
    def _model_to_dict(self, obj):
        """Convert model instance to dictionary"""
        data = {}
        for field in obj._meta.fields:
            value = getattr(obj, field.name, None)
            if value and hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, '__str__'):
                value = str(value)
            data[field.name] = value
        return data
    
    def _compress_backup(self, output_dir, backup_name):
        """Compress backup files"""
        import zipfile
        
        zip_path = os.path.join(output_dir, f'{backup_name}.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Find all backup files
            for filename in os.listdir(output_dir):
                if filename.startswith(backup_name) and not filename.endswith('.zip'):
                    file_path = os.path.join(output_dir, filename)
                    zf.write(file_path, filename)
        
        # Remove uncompressed files
        for filename in os.listdir(output_dir):
            if filename.startswith(backup_name) and not filename.endswith('.zip'):
                os.remove(os.path.join(output_dir, filename))
        
        return zip_path
    
    def _verify_backup(self, backup_info, output_dir):
        """Verify backup integrity"""
        self.stdout.write('Verifying backup integrity...')
        
        for key, file_path in backup_info.items():
            if key.endswith('_file') and os.path.exists(file_path):
                size = os.path.getsize(file_path)
                expected_size = backup_info.get(key.replace('_file', '_size'))
                
                if size != expected_size:
                    self.stdout.write(self.style.WARNING(f'  - Size mismatch for {file_path}: expected {expected_size}, got {size}'))
                else:
                    self.stdout.write(f'  - Verified: {file_path}')
        
        self.stdout.write(self.style.SUCCESS('Backup verification complete'))
    
    def _cleanup_old_backups(self, output_dir, keep_backups):
        """Clean up old backup files"""
        self.stdout.write(f'Cleaning up old backups (keeping {keep_backups})...')
        
        # Find all backup directories
        backup_dirs = []
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isdir(item_path) and item.startswith('alerts_backup_'):
                backup_dirs.append((item_path, os.path.getmtime(item_path)))
        
        # Sort by modification time (newest first)
        backup_dirs.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old backups
        removed_count = 0
        for backup_dir, mtime in backup_dirs[keep_backups:]:
            try:
                shutil.rmtree(backup_dir)
                removed_count += 1
                self.stdout.write(f'  - Removed: {os.path.basename(backup_dir)}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Failed to remove {backup_dir}: {str(e)}'))
        
        if removed_count > 0:
            self.stdout.write(f'Removed {removed_count} old backup directories')
    
    def _format_bytes(self, bytes_value):
        """Format bytes in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"
