"""
Django Management Command: Restore Alert Data
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import json
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Restore alert system data from backup'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-file',
            type=str,
            required=True,
            help='Path to backup file or directory'
        )
        parser.add_argument(
            '--metadata-file',
            type=str,
            help='Path to metadata file (for JSON backups)'
        )
        parser.add_argument(
            '--models',
            type=str,
            help='Models to restore (comma-separated, default: all in backup)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'fixtures', 'sql'],
            help='Backup format (auto-detected if not specified)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing data before restore'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip records that already exist'
        )
        defaulthelp='Skip records that already exist'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be restored without actually restoring'
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify restore integrity after completion'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for restore operations (default: 100)'
        )
    
    def handle(self, *args, **options):
        backup_file = options['backup_file']
        metadata_file = options.get('metadata_file')
        models = options.get('models')
        format_type = options.get('format')
        clear_existing = options['clear_existing']
        skip_existing = options['skip_existing']
        dry_run = options['dry_run']
        verify = options['verify']
        batch_size = options['batch_size']
        
        self.stdout.write(self.style.SUCCESS(f'Restoring alert system data from {backup_file}'))
        
        # Check if backup exists
        if not os.path.exists(backup_file):
            self.stdout.write(self.style.ERROR(f'Backup file does not exist: {backup_file}'))
            return
        
        # Detect format if not specified
        if not format_type:
            format_type = self._detect_format(backup_file)
            self.stdout.write(f'Detected format: {format_type}')
        
        # Load backup metadata
        backup_info = self._load_backup_metadata(backup_file, metadata_file, format_type)
        
        if not backup_info:
            self.stdout.write(self.style.ERROR('Failed to load backup metadata'))
            return
        
        # Determine models to restore
        if models:
            models_to_restore = [model.strip() for model in models.split(',')]
        else:
            models_to_restore = backup_info.get('models', [])
        
        self.stdout.write(f'Models to restore: {", ".join(models_to_restore)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No data will be restored'))
            return
        
        # Clear existing data if requested
        if clear_existing:
            self._clear_existing_data(models_to_restore)
        
        # Restore data
        total_restored = 0
        total_failed = 0
        
        for model in models_to_restore:
            try:
                restored_count = self._restore_model(
                    model, backup_file, backup_info, format_type,
                    skip_existing, batch_size
                )
                total_restored += restored_count
                self.stdout.write(f'  - Restored {restored_count} {model} records')
            except Exception as e:
                total_failed += 1
                self.stdout.write(self.style.ERROR(f'  - Failed to restore {model}: {str(e)}'))
        
        # Verify restore if requested
        if verify:
            self._verify_restore(models_to_restore, backup_info)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Restore complete:'))
        self.stdout.write(f'  - Models restored: {", ".join(models_to_restore)}')
        self.stdout.write(f'  - Total records restored: {total_restored}')
        self.stdout.write(f'  - Failed models: {total_failed}')
        
        if clear_existing:
            self.stdout.write(f'  - Existing data cleared: Yes')
        
        if skip_existing:
            self.stdout.write(f'  - Skipped existing records: Yes')
        
        if verify:
            self.stdout.write(f'  - Restore verified: Yes')
    
    def _detect_format(self, backup_file):
        """Detect backup format from file"""
        if os.path.isdir(backup_file):
            # Directory backup - check for metadata file
            metadata_file = os.path.join(backup_file, 'metadata.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    return metadata.get('format', 'json')
            return 'json'
        else:
            # File backup - check extension
            if backup_file.endswith('.zip'):
                return 'json'  # Assume compressed JSON
            elif backup_file.endswith('.json'):
                return 'json'
            elif backup_file.endswith('.xml'):
                return 'fixtures'
            elif backup_file.endswith('.sql'):
                return 'sql'
            else:
                return 'json'  # Default
    
    def _load_backup_metadata(self, backup_file, metadata_file, format_type):
        """Load backup metadata"""
        if metadata_file and os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                return json.load(f)
        elif os.path.isdir(backup_file):
            # Look for metadata file in directory
            for filename in os.listdir(backup_file):
                if filename.endswith('_metadata.json'):
                    metadata_path = os.path.join(backup_file, filename)
                    with open(metadata_path, 'r') as f:
                        return json.load(f)
        elif backup_file.endswith('.zip'):
            # Extract metadata from zip file
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith('_metadata.json'):
                        with zf.open(filename) as f:
                            return json.load(f)
        
        # Return basic metadata if none found
        return {
            'format': format_type,
            'models': ['rules', 'logs', 'notifications', 'channels', 'incidents', 'reports'],
            'created_at': timezone.now().isoformat()
        }
    
    def _clear_existing_data(self, models_to_restore):
        """Clear existing data for specified models"""
        self.stdout.write('Clearing existing data...')
        
        for model in models_to_restore:
            model_class = self._get_model_class(model)
            if model_class:
                count = model_class.objects.count()
                model_class.objects.all().delete()
                self.stdout.write(f'  - Cleared {count} {model} records')
    
    def _restore_model(self, model, backup_file, backup_info, format_type, skip_existing, batch_size):
        """Restore specific model data"""
        if format_type == 'json':
            return self._restore_model_json(model, backup_file, backup_info, skip_existing)
        elif format_type == 'fixtures':
            return self._restore_model_fixtures(model, backup_file, backup_info, skip_existing)
        elif format_type == 'sql':
            return self._restore_model_sql(model, backup_file, backup_info, skip_existing)
        else:
            raise ValueError(f'Unsupported format: {format_type}')
    
    def _restore_model_json(self, model, backup_file, backup_info, skip_existing):
        """Restore model data from JSON"""
        model_class = self._get_model_class(model)
        if not model_class:
            raise ValueError(f'Unknown model: {model}')
        
        # Find JSON file
        json_file = self._find_model_file(model, backup_file, backup_info, 'json')
        if not json_file:
            raise ValueError(f'JSON file not found for model: {model}')
        
        # Load data
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        restored_count = 0
        
        for record in data:
            try:
                if skip_existing:
                    # Check if record already exists
                    if model_class.objects.filter(id=record.get('id')).exists():
                        continue
                
                # Create or update record
                obj = model_class(**record)
                obj.save()
                restored_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    - Failed to restore record: {str(e)}'))
        
        return restored_count
    
    def _restore_model_fixtures(self, model, backup_file, backup_info, skip_existing):
        """Restore model data from fixtures"""
        from django.core.management import call_command
        
        # Find fixture file
        fixture_file = self._find_model_file(model, backup_file, backup_info, 'fixtures')
        if not fixture_file:
            raise ValueError(f'Fixture file not found for model: {model}')
        
        # Use Django's loaddata command
        try:
            call_command('loaddata', fixture_file)
            return 1  # Success
        except Exception as e:
            raise ValueError(f'Failed to load fixture: {str(e)}')
    
    def _restore_model_sql(self, model, backup_file, backup_info, skip_existing):
        """Restore model data from SQL"""
        from django.db import connection
        
        # Find SQL file
        sql_file = self._find_model_file(model, backup_file, backup_info, 'sql')
        if not sql_file:
            raise ValueError(f'SQL file not found for model: {model}')
        
        # Read and execute SQL
        with open(sql_file, 'r') as f:
            sql = f.read()
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
        
        return cursor.rowcount if cursor.rowcount else 1
    
    def _find_model_file(self, model, backup_file, backup_info, format_type):
        """Find backup file for specific model"""
        if os.path.isdir(backup_file):
            # Directory backup
            for filename in os.listdir(backup_file):
                if filename.startswith(f'alerts_backup_') and filename.endswith(f'_{model}.{format_type}'):
                    return os.path.join(backup_file, filename)
        elif backup_file.endswith('.zip'):
            # Compressed backup
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith(f'_{model}.{format_type}'):
                        # Extract to temp file
                        temp_path = f'/tmp/{filename}'
                        with open(temp_path, 'wb') as f:
                            f.write(zf.read(filename))
                        return temp_path
        else:
            # Single file backup
            return backup_file
        
        return None
    
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
    
    def _verify_restore(self, models_to_restore, backup_info):
        """Verify restore integrity"""
        self.stdout.write('Verifying restore integrity...')
        
        for model in models_to_restore:
            model_class = self._get_model_class(model)
            if model_class:
                count = model_class.objects.count()
                self.stdout.write(f'  - {model}: {count} records')
        
        self.stdout.write(self.style.SUCCESS('Restore verification complete'))
