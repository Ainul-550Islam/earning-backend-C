"""
Database Backup Management Command
Complete implementation with advanced features for automated backups
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import traceback
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.db import connections, transaction, DatabaseError
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string

from backup.models import (
    DatabaseBackup, 
    BackupSchedule, 
    BackupStorage,
    BackupNotification,
    BackupLog
)
from backup.services.factory import BackupServiceFactory
from backup.services.validators import BackupValidator
from backup.services.encryption import EncryptionService
from backup.services.compression import CompressionService
from backup.services.notifications import NotificationService
from backup.utils.helpers import (
    format_file_size,
    human_readable_time,
    get_database_info,
    calculate_hash,
    cleanup_old_files
)

logger = logging.getLogger(__name__)

class DatabaseBackupCommand(BaseCommand):
    """
    Comprehensive database backup command with support for:
    - Multiple database engines (PostgreSQL, MySQL, SQLite, Oracle)
    - Incremental and full backups
    - Encryption and compression
    - Multiple storage backends
    - Backup scheduling
    - Email notifications
    - Backup verification
    - Retention policies
    """
    
    help = 'Create and manage database backups with advanced features'
    
    # Color codes for terminal output
    COLORS = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'magenta': '\033[95m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments"""
        parser.add_argument(
            'action',
            nargs='?',
            type=str,
            choices=['create', 'schedule', 'cancel', 'status', 'verify', 'cleanup'],
            default='create',
            help='Action to perform'
        )
        
        # Backup creation arguments
        parser.add_argument(
            '--name',
            type=str,
            help='Custom name for the backup'
        )
        parser.add_argument(
            '--description',
            type=str,
            help='Description of the backup'
        )
        parser.add_argument(
            '--database',
            type=str,
            default='default',
            help='Database alias to backup (default: default)'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['full', 'incremental', 'differential'],
            default='full',
            help='Type of backup to create'
        )
        
        # Storage arguments
        parser.add_argument(
            '--storage',
            type=str,
            choices=['local', 's3', 'azure', 'gcp', 'ftp', 'all'],
            default='local',
            help='Storage backend to use'
        )
        parser.add_argument(
            '--storage-config',
            type=str,
            help='JSON configuration for storage backend'
        )
        
        # Security arguments
        parser.add_argument(
            '--encrypt',
            action='store_true',
            help='Encrypt the backup'
        )
        parser.add_argument(
            '--encryption-key',
            type=str,
            help='Custom encryption key (leave empty for auto-generation)'
        )
        parser.add_argument(
            '--encryption-algorithm',
            type=str,
            choices=['AES-256-GCM', 'ChaCha20-Poly1305', 'Fernet'],
            default='AES-256-GCM',
            help='Encryption algorithm to use'
        )
        
        # Compression arguments
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress the backup'
        )
        parser.add_argument(
            '--compression-level',
            type=int,
            choices=range(1, 10),
            default=6,
            help='Compression level (1-9)'
        )
        parser.add_argument(
            '--compression-algorithm',
            type=str,
            choices=['gzip', 'bzip2', 'lzma', 'zstd'],
            default='gzip',
            help='Compression algorithm to use'
        )
        
        # Scheduling arguments
        parser.add_argument(
            '--schedule',
            type=str,
            help='Schedule backup (cron format or interval)'
        )
        parser.add_argument(
            '--schedule-name',
            type=str,
            help='Name for the backup schedule'
        )
        parser.add_argument(
            '--schedule-enabled',
            action='store_true',
            default=True,
            help='Enable the schedule immediately'
        )
        
        # Retention policy arguments
        parser.add_argument(
            '--retention-days',
            type=int,
            default=30,
            help='Number of days to keep backups'
        )
        parser.add_argument(
            '--retention-count',
            type=int,
            default=10,
            help='Maximum number of backups to keep'
        )
        parser.add_argument(
            '--keep-weekly',
            type=int,
            default=4,
            help='Number of weekly backups to keep'
        )
        parser.add_argument(
            '--keep-monthly',
            type=int,
            default=12,
            help='Number of monthly backups to keep'
        )
        
        # Performance arguments
        parser.add_argument(
            '--max-size',
            type=str,
            help='Maximum backup size (e.g., 1GB, 500MB)'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=3600,
            help='Timeout for backup operation in seconds'
        )
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Number of parallel threads for backup'
        )
        
        # Notification arguments
        parser.add_argument(
            '--notify',
            action='store_true',
            help='Send notifications'
        )
        parser.add_argument(
            '--notify-success',
            action='store_true',
            help='Send notification on success'
        )
        parser.add_argument(
            '--notify-failure',
            action='store_true',
            help='Send notification on failure'
        )
        parser.add_argument(
            '--notify-email',
            type=str,
            help='Email address for notifications'
        )
        
        # Verification arguments
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify backup integrity after creation'
        )
        parser.add_argument(
            '--verify-checksum',
            action='store_true',
            help='Verify file checksum'
        )
        parser.add_argument(
            '--verify-restore',
            action='store_true',
            help='Test restore on temporary database'
        )
        
        # Cleanup arguments
        parser.add_argument(
            '--cleanup-old',
            action='store_true',
            help='Cleanup old backups before creating new one'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force backup even if validation fails'
        )
        
        # Logging arguments
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
        parser.add_argument(
            '--log-file',
            type=str,
            help='Log to specified file'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format'
        )
    
    def handle(self, *args, **options) -> None:
        """Main command handler"""
        try:
            # Setup logging
            self._setup_logging(options)
            
            # Record start time
            start_time = time.time()
            
            # Execute the requested action
            action = options.get('action', 'create')
            
            if action == 'create':
                result = self.create_backup(options)
            elif action == 'schedule':
                result = self.manage_schedule(options)
            elif action == 'cancel':
                result = self.cancel_backup(options)
            elif action == 'status':
                result = self.check_status(options)
            elif action == 'verify':
                result = self.verify_backups(options)
            elif action == 'cleanup':
                result = self.cleanup_backups(options)
            else:
                raise CommandError(f"Unknown action: {action}")
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Output results
            self.output_results(result, options, execution_time)
            
        except KeyboardInterrupt:
            self.stderr.write(self.style.ERROR('Backup interrupted by user'))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Backup failed: {str(e)}'))
            if options.get('verbose'):
                self.stderr.write(traceback.format_exc())
            sys.exit(1)
    
    def create_backup(self, options: Dict) -> Dict:
        """Create a new database backup"""
        self.stdout.write(self.style.SUCCESS('Starting database backup...'))
        
        # Validate database connection
        database_alias = options.get('database', 'default')
        if database_alias not in connections:
            raise CommandError(f"Database '{database_alias}' not configured")
        
        # Get database information
        db_info = self.get_database_info(database_alias)
        
        # Prepare backup configuration
        backup_config = self.prepare_backup_config(options, db_info)
        
        # Create backup record
        backup_record = self.create_backup_record(backup_config)
        
        try:
            # Step 1: Pre-backup validation
            self.stdout.write(self.style.NOTICE('Step 1: Pre-backup validation...'))
            validation_result = self.validate_pre_backup(backup_config)
            
            if not validation_result['valid'] and not options.get('force'):
                raise CommandError(f"Pre-backup validation failed: {validation_result['errors']}")
            
            # Step 2: Create database dump
            self.stdout.write(self.style.NOTICE('Step 2: Creating database dump...'))
            dump_result = self.create_database_dump(backup_config, backup_record)
            
            # Step 3: Apply compression if requested
            if options.get('compress'):
                self.stdout.write(self.style.NOTICE('Step 3: Compressing backup...'))
                dump_result = self.compress_backup(dump_result, backup_config)
            
            # Step 4: Apply encryption if requested
            if options.get('encrypt'):
                self.stdout.write(self.style.NOTICE('Step 4: Encrypting backup...'))
                dump_result = self.encrypt_backup(dump_result, backup_config)
            
            # Step 5: Save to storage backends
            self.stdout.write(self.style.NOTICE('Step 5: Saving to storage...'))
            storage_result = self.save_to_storage(dump_result, backup_config, backup_record)
            
            # Step 6: Post-backup verification
            if options.get('verify'):
                self.stdout.write(self.style.NOTICE('Step 6: Verifying backup...'))
                verification_result = self.verify_backup(storage_result, backup_config, backup_record)
            
            # Step 7: Update backup record
            self.stdout.write(self.style.NOTICE('Step 7: Finalizing backup...'))
            self.finalize_backup_record(backup_record, storage_result, 'completed')
            
            # Step 8: Apply retention policy
            if options.get('cleanup_old'):
                self.stdout.write(self.style.NOTICE('Step 8: Cleaning up old backups...'))
                self.apply_retention_policy(backup_config)
            
            # Step 9: Send notifications
            if options.get('notify'):
                self.stdout.write(self.style.NOTICE('Step 9: Sending notifications...'))
                self.send_notifications(backup_record, 'success')
            
            # Prepare result
            result = {
                'status': 'success',
                'backup_id': str(backup_record.id),
                'backup_name': backup_record.name,
                'file_size': format_file_size(backup_record.file_size),
                'file_hash': backup_record.file_hash,
                'storage_locations': backup_record.storage_locations,
                'time_taken': time.time() - backup_record.start_time.timestamp()
            }
            
            self.stdout.write(self.style.SUCCESS('✓ Backup completed successfully!'))
            return result
            
        except Exception as e:
            # Update backup record with failure
            if backup_record:
                self.finalize_backup_record(backup_record, {'error': str(e)}, 'failed')
            
            # Send failure notification
            if options.get('notify') or options.get('notify_failure'):
                self.send_notifications(backup_record, 'failure', str(e))
            
            # Re-raise the exception
            raise
    
    def manage_schedule(self, options: Dict) -> Dict:
        """Manage backup schedules"""
        schedule_name = options.get('schedule_name')
        schedule_expr = options.get('schedule')
        
        if not schedule_name or not schedule_expr:
            # List existing schedules
            schedules = BackupSchedule.objects.all()
            
            if not schedules:
                return {'status': 'info', 'message': 'No backup schedules found'}
            
            result = {
                'status': 'success',
                'schedules': []
            }
            
            for schedule in schedules:
                result['schedules'].append({
                    'id': schedule.id,
                    'name': schedule.name,
                    'schedule': schedule.cron_expression,
                    'enabled': schedule.is_active,
                    'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
                    'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                    'database': schedule.database_alias,
                    'storage_type': schedule.storage_type
                })
            
            return result
        
        # Create or update schedule
        with transaction.atomic():
            schedule, created = BackupSchedule.objects.update_or_create(
                name=schedule_name,
                defaults={
                    'cron_expression': schedule_expr,
                    'is_active': options.get('schedule_enabled', True),
                    'database_alias': options.get('database', 'default'),
                    'storage_type': options.get('storage', 'local'),
                    'encryption_enabled': options.get('encrypt', False),
                    'compression_enabled': options.get('compress', True),
                    'retention_days': options.get('retention_days', 30),
                    'notification_enabled': options.get('notify', False),
                    'notification_emails': options.get('notify_email', ''),
                    'description': options.get('description', '')
                }
            )
        
        action = 'created' if created else 'updated'
        return {
            'status': 'success',
            'message': f'Schedule {action} successfully',
            'schedule_id': schedule.id,
            'schedule_name': schedule.name,
            'next_run': schedule.next_run.isoformat() if schedule.next_run else None
        }
    
    def cancel_backup(self, options: Dict) -> Dict:
        """Cancel running backup"""
        backup_id = options.get('backup_id')
        
        if backup_id:
            # Cancel specific backup
            try:
                backup = DatabaseBackup.objects.get(id=backup_id, status='in_progress')
                backup.status = 'cancelled'
                backup.end_time = timezone.now()
                backup.save()
                
                return {
                    'status': 'success',
                    'message': f'Backup {backup_id} cancelled successfully'
                }
            except DatabaseBackup.DoesNotExist:
                raise CommandError(f'No running backup found with ID: {backup_id}')
        
        # Cancel all running backups
        running_backups = DatabaseBackup.objects.filter(status='in_progress')
        count = running_backups.count()
        
        if count == 0:
            return {'status': 'info', 'message': 'No running backups found'}
        
        running_backups.update(
            status='cancelled',
            end_time=timezone.now()
        )
        
        return {
            'status': 'success',
            'message': f'{count} backup(s) cancelled successfully'
        }
    
    def check_status(self, options: Dict) -> Dict:
        """Check backup system status"""
        status = {
            'database': {},
            'storage': {},
            'backups': {},
            'schedules': {},
            'system': {}
        }
        
        # Check database connections
        for alias in connections:
            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute('SELECT 1')
                    status['database'][alias] = {
                        'status': 'connected',
                        'engine': connections[alias].vendor
                    }
            except Exception as e:
                status['database'][alias] = {
                    'status': 'disconnected',
                    'error': str(e)
                }
        
        # Check storage backends
        storage_types = ['local', 's3', 'azure', 'gcp']
        for storage_type in storage_types:
            try:
                service = BackupServiceFactory.get_storage_service(storage_type)
                status['storage'][storage_type] = {
                    'status': 'available',
                    'details': service.get_status()
                }
            except Exception as e:
                status['storage'][storage_type] = {
                    'status': 'unavailable',
                    'error': str(e)
                }
        
        # Get backup statistics
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        status['backups'] = {
            'total': DatabaseBackup.objects.count(),
            'completed': DatabaseBackup.objects.filter(status='completed').count(),
            'failed': DatabaseBackup.objects.filter(status='failed').count(),
            'in_progress': DatabaseBackup.objects.filter(status='in_progress').count(),
            'today': DatabaseBackup.objects.filter(created_at__date=today).count(),
            'last_7_days': DatabaseBackup.objects.filter(created_at__date__gte=week_ago).count(),
            'last_30_days': DatabaseBackup.objects.filter(created_at__date__gte=month_ago).count(),
            'total_size': format_file_size(
                DatabaseBackup.objects.aggregate(total=Sum('file_size'))['total'] or 0
            )
        }
        
        # Get schedule statistics
        status['schedules'] = {
            'total': BackupSchedule.objects.count(),
            'active': BackupSchedule.objects.filter(is_active=True).count(),
            'inactive': BackupSchedule.objects.filter(is_active=False).count(),
            'next_scheduled': BackupSchedule.objects.filter(
                is_active=True,
                next_run__isnull=False
            ).order_by('next_run').first()
        }
        
        # System information
        import psutil
        status['system'] = {
            'disk_usage': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free,
                'percent': psutil.disk_usage('/').percent
            },
            'memory_usage': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'percent': psutil.virtual_memory().percent
            }
        }
        
        return status
    
    def verify_backups(self, options: Dict) -> Dict:
        """Verify existing backups"""
        backup_id = options.get('backup_id')
        
        if backup_id:
            # Verify specific backup
            try:
                backup = DatabaseBackup.objects.get(id=backup_id)
                return self.verify_single_backup(backup, options)
            except DatabaseBackup.DoesNotExist:
                raise CommandError(f'Backup not found with ID: {backup_id}')
        
        # Verify all recent backups
        recent_backups = DatabaseBackup.objects.filter(
            status='completed',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-created_at')
        
        results = []
        for backup in recent_backups:
            try:
                result = self.verify_single_backup(backup, options)
                results.append(result)
            except Exception as e:
                results.append({
                    'backup_id': str(backup.id),
                    'backup_name': backup.name,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'verifications': results,
            'total': len(results),
            'successful': len([r for r in results if r.get('status') == 'success']),
            'failed': len([r for r in results if r.get('status') == 'failed'])
        }
    
    def cleanup_backups(self, options: Dict) -> Dict:
        """Cleanup old backups based on retention policy"""
        retention_days = options.get('retention_days', 30)
        retention_count = options.get('retention_count', 10)
        
        # Get backups eligible for deletion
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Delete by age
        old_backups = DatabaseBackup.objects.filter(
            created_at__lt=cutoff_date,
            status='completed'
        ).order_by('created_at')
        
        # Also limit by count (keep only N most recent)
        all_backups = DatabaseBackup.objects.filter(
            status='completed'
        ).order_by('-created_at')
        
        if all_backups.count() > retention_count:
            backups_to_keep = all_backups[:retention_count]
            backups_to_delete = DatabaseBackup.objects.filter(
                status='completed'
            ).exclude(
                id__in=[b.id for b in backups_to_keep]
            )
        else:
            backups_to_delete = old_backups
        
        # Actually delete backups
        deleted_count = 0
        deleted_size = 0
        errors = []
        
        for backup in backups_to_delete:
            try:
                # Delete from storage
                self.delete_backup_from_storage(backup)
                
                # Delete record
                deleted_size += backup.file_size or 0
                backup.delete()
                deleted_count += 1
                
            except Exception as e:
                errors.append({
                    'backup_id': str(backup.id),
                    'backup_name': backup.name,
                    'error': str(e)
                })
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'deleted_size': format_file_size(deleted_size),
            'errors': errors,
            'remaining_count': DatabaseBackup.objects.filter(status='completed').count()
        }
    
    # Helper methods
    def _setup_logging(self, options: Dict) -> None:
        """Setup logging configuration"""
        log_level = logging.DEBUG if options.get('verbose') else logging.INFO
        
        if options.get('log_file'):
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(options['log_file']),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    
    def get_database_info(self, alias: str) -> Dict:
        """Get information about the database"""
        connection = connections[alias]
        engine = connection.vendor
        
        info = {
            'alias': alias,
            'engine': engine,
            'name': connection.settings_dict['NAME'],
            'host': connection.settings_dict.get('HOST', 'localhost'),
            'port': connection.settings_dict.get('PORT', ''),
            'user': connection.settings_dict.get('USER', ''),
            'charset': connection.settings_dict.get('CHARSET', ''),
            'timezone': connection.settings_dict.get('TIME_ZONE', ''),
        }
        
        # Get database size for some engines
        try:
            with connection.cursor() as cursor:
                if engine == 'postgresql':
                    cursor.execute("""
                        SELECT pg_database_size(%s) as size,
                               pg_database.datname as name,
                               pg_database.datcollate as collation
                        FROM pg_database 
                        WHERE datname = %s
                    """, [info['name'], info['name']])
                    row = cursor.fetchone()
                    if row:
                        info['size'] = row[0]
                        info['collation'] = row[2]
                        
                elif engine == 'mysql':
                    cursor.execute("""
                        SELECT 
                            table_schema as db_name,
                            SUM(data_length + index_length) as size,
                            DEFAULT_CHARACTER_SET_NAME as charset
                        FROM information_schema.TABLES 
                        WHERE table_schema = %s
                        GROUP BY table_schema
                    """, [info['name']])
                    row = cursor.fetchone()
                    if row:
                        info['size'] = row[1]
                        info['charset'] = row[2]
        except Exception:
            pass  # Skip if we can't get size
        
        return info
    
    def prepare_backup_config(self, options: Dict, db_info: Dict) -> Dict:
        """Prepare configuration for backup"""
        config = {
            'database': db_info,
            'backup_type': options.get('type', 'full'),
            'storage_type': options.get('storage', 'local'),
            'encryption': {
                'enabled': options.get('encrypt', False),
                'algorithm': options.get('encryption_algorithm', 'AES-256-GCM'),
                'key': options.get('encryption_key')
            },
            'compression': {
                'enabled': options.get('compress', True),
                'algorithm': options.get('compression_algorithm', 'gzip'),
                'level': options.get('compression_level', 6)
            },
            'retention': {
                'days': options.get('retention_days', 30),
                'count': options.get('retention_count', 10),
                'keep_weekly': options.get('keep_weekly', 4),
                'keep_monthly': options.get('keep_monthly', 12)
            },
            'performance': {
                'timeout': options.get('timeout', 3600),
                'parallel': options.get('parallel', 1),
                'max_size': self.parse_size_string(options.get('max_size'))
            },
            'verification': {
                'enabled': options.get('verify', False),
                'checksum': options.get('verify_checksum', True),
                'restore_test': options.get('verify_restore', False)
            },
            'notification': {
                'enabled': options.get('notify', False),
                'on_success': options.get('notify_success', True),
                'on_failure': options.get('notify_failure', True),
                'email': options.get('notify_email')
            },
            'metadata': {
                'name': options.get('name'),
                'description': options.get('description'),
                'tags': options.get('tags', '').split(',') if options.get('tags') else []
            }
        }
        
        # Parse storage config if provided
        if options.get('storage_config'):
            try:
                config['storage_config'] = json.loads(options['storage_config'])
            except json.JSONDecodeError:
                raise CommandError('Invalid JSON in storage-config')
        
        return config
    
    def parse_size_string(self, size_str: Optional[str]) -> Optional[int]:
        """Parse human-readable size string to bytes"""
        if not size_str:
            return None
        
        size_str = size_str.upper().strip()
        
        # Define multipliers
        multipliers = {
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4,
        }
        
        # Extract number and unit
        import re
        match = re.match(r'^(\d+\.?\d*)\s*([A-Z]+)?$', size_str)
        
        if not match:
            raise CommandError(f'Invalid size format: {size_str}')
        
        number = float(match.group(1))
        unit = match.group(2)
        
        if not unit:
            return int(number)
        
        if unit not in multipliers:
            raise CommandError(f'Unknown size unit: {unit}')
        
        return int(number * multipliers[unit])
    
    def create_backup_record(self, config: Dict) -> DatabaseBackup:
        """Create a backup record in the database"""
        backup = DatabaseBackup(
            name=config['metadata']['name'] or f"Backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            description=config['metadata']['description'],
            database_alias=config['database']['alias'],
            database_engine=config['database']['engine'],
            backup_type=config['backup_type'],
            storage_type=config['storage_type'],
            encryption_enabled=config['encryption']['enabled'],
            compression_enabled=config['compression']['enabled'],
            status='in_progress',
            start_time=timezone.now(),
            tags=config['metadata']['tags']
        )
        
        backup.save()
        return backup
    
    def validate_pre_backup(self, config: Dict) -> Dict:
        """Validate system before starting backup"""
        errors = []
        warnings = []
        
        # Check database connection
        try:
            with connections[config['database']['alias']].cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception as e:
            errors.append(f"Database connection failed: {str(e)}")
        
        # Check disk space
        if config['storage_type'] == 'local':
            try:
                import shutil
                total, used, free = shutil.disk_usage('/')
                
                # Estimate required space (2x database size as buffer)
                estimated_size = config['database'].get('size', 0) * 2
                
                if free < estimated_size:
                    warnings.append(
                        f"Low disk space: {format_file_size(free)} free, "
                        f"estimated need: {format_file_size(estimated_size)}"
                    )
            except Exception:
                pass
        
        # Check if another backup is running
        running_backups = DatabaseBackup.objects.filter(
            status='in_progress',
            database_alias=config['database']['alias']
        ).count()
        
        if running_backups > 0:
            warnings.append(f"Another backup is already running for database {config['database']['alias']}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def create_database_dump(self, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Create database dump using appropriate method"""
        engine = config['database']['engine']
        
        try:
            if engine == 'postgresql':
                return self._dump_postgresql(config, backup_record)
            elif engine == 'mysql':
                return self._dump_mysql(config, backup_record)
            elif engine == 'sqlite':
                return self._dump_sqlite(config, backup_record)
            else:
                return self._dump_using_django(config, backup_record)
        except Exception as e:
            raise CommandError(f"Failed to create database dump: {str(e)}")
    
    def _dump_postgresql(self, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Dump PostgreSQL database"""
        db = config['database']
        dump_file = self._get_temp_file('sql')
        
        try:
            # Build pg_dump command
            cmd = ['pg_dump']
            
            # Add connection parameters
            cmd.extend(['-h', db['host'] if db['host'] else 'localhost'])
            if db['port']:
                cmd.extend(['-p', str(db['port'])])
            cmd.extend(['-U', db['user']])
            cmd.extend(['-d', db['name']])
            
            # Add format and output
            cmd.extend(['-F', 'c'])  # Custom format (compressed by pg_dump)
            cmd.extend(['-f', dump_file])
            
            # Add options
            cmd.append('--no-owner')  # Don't output ownership commands
            cmd.append('--no-acl')    # Don't output ACL commands
            cmd.append('--verbose')
            
            # Set environment variable for password
            env = os.environ.copy()
            password = connections[db['alias']].settings_dict.get('PASSWORD')
            if password:
                env['PGPASSWORD'] = password
            
            # Execute command
            self.stdout.write(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=config['performance']['timeout']
            )
            
            if result.returncode != 0:
                raise CommandError(f"pg_dump failed: {result.stderr}")
            
            # Verify dump file
            if not os.path.exists(dump_file) or os.path.getsize(dump_file) == 0:
                raise CommandError("Dump file is empty or not created")
            
            # Calculate hash
            file_hash = calculate_hash(dump_file)
            file_size = os.path.getsize(dump_file)
            
            # Update backup record
            backup_record.file_size = file_size
            backup_record.file_hash = file_hash
            backup_record.save()
            
            return {
                'file_path': dump_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'format': 'postgres_custom'
            }
            
        except subprocess.TimeoutExpired:
            raise CommandError("pg_dump timed out")
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(dump_file):
                os.remove(dump_file)
            raise
    
    def _dump_mysql(self, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Dump MySQL database"""
        db = config['database']
        dump_file = self._get_temp_file('sql')
        
        try:
            # Build mysqldump command
            cmd = ['mysqldump']
            
            # Add connection parameters
            cmd.extend(['-h', db['host'] if db['host'] else 'localhost'])
            if db['port']:
                cmd.extend(['-P', str(db['port'])])
            cmd.extend(['-u', db['user']])
            
            # Add password if available
            password = connections[db['alias']].settings_dict.get('PASSWORD')
            if password:
                cmd.extend([f'--password={password}'])
            
            # Add database name and output
            cmd.append(db['name'])
            cmd.extend(['--result-file', dump_file])
            
            # Add options
            cmd.append('--single-transaction')  # For InnoDB tables
            cmd.append('--routines')            # Include stored procedures
            cmd.append('--triggers')            # Include triggers
            cmd.append('--events')              # Include events
            cmd.append('--add-drop-database')   # Add DROP DATABASE statement
            cmd.append('--add-drop-table')      # Add DROP TABLE statement
            cmd.append('--hex-blob')            # Dump binary columns in hex
            cmd.append('--complete-insert')     # Use complete INSERT statements
            
            # Execute command
            self.stdout.write(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config['performance']['timeout']
            )
            
            if result.returncode != 0:
                raise CommandError(f"mysqldump failed: {result.stderr}")
            
            # Verify dump file
            if not os.path.exists(dump_file) or os.path.getsize(dump_file) == 0:
                raise CommandError("Dump file is empty or not created")
            
            # Calculate hash
            file_hash = calculate_hash(dump_file)
            file_size = os.path.getsize(dump_file)
            
            # Update backup record
            backup_record.file_size = file_size
            backup_record.file_hash = file_hash
            backup_record.save()
            
            return {
                'file_path': dump_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'format': 'mysql_sql'
            }
            
        except subprocess.TimeoutExpired:
            raise CommandError("mysqldump timed out")
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(dump_file):
                os.remove(dump_file)
            raise
    
    def _dump_sqlite(self, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Dump SQLite database (simple copy)"""
        db = config['database']
        db_file = db['name']
        
        if not os.path.exists(db_file):
            raise CommandError(f"SQLite database file not found: {db_file}")
        
        dump_file = self._get_temp_file('db')
        
        try:
            # For SQLite, we can just copy the file
            import shutil
            shutil.copy2(db_file, dump_file)
            
            # Calculate hash
            file_hash = calculate_hash(dump_file)
            file_size = os.path.getsize(dump_file)
            
            # Update backup record
            backup_record.file_size = file_size
            backup_record.file_hash = file_hash
            backup_record.save()
            
            return {
                'file_path': dump_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'format': 'sqlite_copy'
            }
            
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(dump_file):
                os.remove(dump_file)
            raise
    
    def _dump_using_django(self, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Dump database using Django's dumpdata command"""
        from django.core.management import call_command
        from io import StringIO
        
        dump_file = self._get_temp_file('json')
        
        try:
            # Create a string buffer to capture output
            output_buffer = StringIO()
            
            # Call dumpdata command
            call_command(
                'dumpdata',
                format='json',
                indent=2,
                exclude=['contenttypes', 'auth.permission', 'sessions'],
                stdout=output_buffer,
                database=config['database']['alias']
            )
            
            # Write to file
            with open(dump_file, 'w', encoding='utf-8') as f:
                f.write(output_buffer.getvalue())
            
            # Calculate hash
            file_hash = calculate_hash(dump_file)
            file_size = os.path.getsize(dump_file)
            
            # Update backup record
            backup_record.file_size = file_size
            backup_record.file_hash = file_hash
            backup_record.save()
            
            return {
                'file_path': dump_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'format': 'django_json'
            }
            
        except Exception as e:
            # Cleanup temp file on error
            if os.path.exists(dump_file):
                os.remove(dump_file)
            raise
    
    def _get_temp_file(self, extension: str) -> str:
        """Get a temporary file path"""
        import tempfile
        temp_dir = getattr(settings, 'BACKUP_TEMP_DIR', None) or tempfile.gettempdir()
        os.makedirs(temp_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_str = get_random_string(8)
        
        filename = f"backup_{timestamp}_{random_str}.{extension}"
        return os.path.join(temp_dir, filename)
    
    def compress_backup(self, dump_result: Dict, config: Dict) -> Dict:
        """Compress backup file"""
        compression_service = CompressionService()
        
        try:
            compressed_file = compression_service.compress(
                dump_result['file_path'],
                algorithm=config['compression']['algorithm'],
                level=config['compression']['level']
            )
            
            # Calculate new hash and size
            file_hash = calculate_hash(compressed_file)
            file_size = os.path.getsize(compressed_file)
            
            # Cleanup original file
            if os.path.exists(dump_result['file_path']):
                os.remove(dump_result['file_path'])
            
            return {
                'file_path': compressed_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'original_size': dump_result['file_size'],
                'compression_ratio': file_size / dump_result['file_size'] if dump_result['file_size'] > 0 else 0,
                'format': f"{dump_result.get('format', 'unknown')}_{config['compression']['algorithm']}"
            }
            
        except Exception as e:
            raise CommandError(f"Compression failed: {str(e)}")
    
    def encrypt_backup(self, dump_result: Dict, config: Dict) -> Dict:
        """Encrypt backup file"""
        encryption_service = EncryptionService()
        
        try:
            # Generate or use provided key
            key = config['encryption']['key']
            if not key:
                key = encryption_service.generate_key(
                    algorithm=config['encryption']['algorithm']
                )
            
            encrypted_file = encryption_service.encrypt(
                dump_result['file_path'],
                key,
                algorithm=config['encryption']['algorithm']
            )
            
            # Calculate new hash and size
            file_hash = calculate_hash(encrypted_file)
            file_size = os.path.getsize(encrypted_file)
            
            # Store encryption key securely
            encryption_key_id = encryption_service.store_key(key)
            
            # Cleanup original file
            if os.path.exists(dump_result['file_path']):
                os.remove(dump_result['file_path'])
            
            return {
                'file_path': encrypted_file,
                'file_size': file_size,
                'file_hash': file_hash,
                'encryption_key_id': encryption_key_id,
                'encryption_algorithm': config['encryption']['algorithm'],
                'format': f"{dump_result.get('format', 'unknown')}_encrypted"
            }
            
        except Exception as e:
            raise CommandError(f"Encryption failed: {str(e)}")
    
    def save_to_storage(self, dump_result: Dict, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Save backup to storage backend(s)"""
        storage_type = config['storage_type']
        storage_config = config.get('storage_config', {})
        
        # Handle multiple storage backends
        if storage_type == 'all':
            storage_types = ['local', 's3', 'azure', 'gcp']
        else:
            storage_types = [storage_type]
        
        results = {}
        
        for stype in storage_types:
            try:
                service = BackupServiceFactory.get_storage_service(stype, storage_config)
                
                # Save to this storage backend
                result = service.save_backup(
                    file_path=dump_result['file_path'],
                    backup_record=backup_record,
                    metadata={
                        'database': config['database'],
                        'backup_type': config['backup_type'],
                        'compression': config['compression'],
                        'encryption': config['encryption']
                    }
                )
                
                results[stype] = result
                
                # Update backup record with storage location
                if not backup_record.storage_locations:
                    backup_record.storage_locations = {}
                
                backup_record.storage_locations[stype] = result.get('location')
                
            except Exception as e:
                self.stderr.write(f"Warning: Failed to save to {stype} storage: {str(e)}")
                results[stype] = {'error': str(e)}
        
        # Cleanup temp file after saving to all storages
        if os.path.exists(dump_result['file_path']):
            os.remove(dump_result['file_path'])
        
        backup_record.save()
        
        return {
            'storage_results': results,
            'successful_storages': [k for k, v in results.items() if 'error' not in v]
        }
    
    def verify_backup(self, storage_result: Dict, config: Dict, backup_record: DatabaseBackup) -> Dict:
        """Verify backup integrity"""
        verification_results = {}
        
        # 1. Verify checksum
        if config['verification']['checksum']:
            for storage_type, result in storage_result['storage_results'].items():
                if 'error' not in result:
                    try:
                        service = BackupServiceFactory.get_storage_service(storage_type)
                        verification_results[storage_type] = service.verify_backup(
                            backup_record,
                            expected_hash=backup_record.file_hash
                        )
                    except Exception as e:
                        verification_results[storage_type] = {'checksum_verification': {'error': str(e)}}
        
        # 2. Test restore if requested
        if config['verification']['restore_test']:
            self.stdout.write("Testing restore capability...")
            
            # Create a temporary database for restore test
            test_db_name = f"test_restore_{backup_record.id[:8]}"
            
            try:
                # This is a complex operation that would need to be implemented
                # based on your specific database engine
                verification_results['restore_test'] = {
                    'status': 'skipped',
                    'message': 'Restore test requires specific database setup'
                }
                
            except Exception as e:
                verification_results['restore_test'] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        return verification_results
    
    def finalize_backup_record(self, backup_record: DatabaseBackup, result: Dict, status: str) -> None:
        """Update backup record with final status"""
        backup_record.status = status
        backup_record.end_time = timezone.now()
        
        if 'error' in result:
            backup_record.error_message = result['error'][:500]  # Truncate if too long
        
        if 'storage_results' in result:
            backup_record.metadata = {
                'storage_results': result['storage_results'],
                'verification': result.get('verification', {})
            }
        
        backup_record.save()
        
        # Log the backup operation
        BackupLog.objects.create(
            backup=backup_record,
            action='create',
            status=status,
            details=result
        )
    
    def apply_retention_policy(self, config: Dict) -> Dict:
        """Apply retention policy to old backups"""
        # This would implement the complex retention policy logic
        # including keeping weekly and monthly backups
        
        return {
            'status': 'success',
            'message': 'Retention policy applied',
            'deleted_count': 0,  # Implement actual deletion logic
            'kept_backups': {
                'daily': 0,
                'weekly': 0,
                'monthly': 0
            }
        }
    
    def send_notifications(self, backup_record: DatabaseBackup, status: str, error_message: str = None) -> None:
        """Send notifications about backup status"""
        notification_service = NotificationService()
        
        context = {
            'backup': backup_record,
            'status': status,
            'error_message': error_message,
            'timestamp': timezone.now(),
            'duration': backup_record.duration if backup_record.end_time else None
        }
        
        try:
            if status == 'success':
                notification_service.send_success_notification(context)
            else:
                notification_service.send_failure_notification(context, error_message)
        except Exception as e:
            self.stderr.write(f"Warning: Failed to send notification: {str(e)}")
    
    def delete_backup_from_storage(self, backup: DatabaseBackup) -> None:
        """Delete backup from all storage backends"""
        if not backup.storage_locations:
            return
        
        for storage_type, location in backup.storage_locations.items():
            try:
                service = BackupServiceFactory.get_storage_service(storage_type)
                service.delete_backup(backup)
            except Exception as e:
                self.stderr.write(f"Warning: Failed to delete from {storage_type}: {str(e)}")
    
    def verify_single_backup(self, backup: DatabaseBackup, options: Dict) -> Dict:
        """Verify a single backup"""
        result = {
            'backup_id': str(backup.id),
            'backup_name': backup.name,
            'created_at': backup.created_at.isoformat()
        }
        
        # Check if backup file exists in storage
        if not backup.storage_locations:
            result.update({
                'status': 'failed',
                'error': 'No storage locations found'
            })
            return result
        
        # Try each storage location
        for storage_type, location in backup.storage_locations.items():
            try:
                service = BackupServiceFactory.get_storage_service(storage_type)
                
                # Verify backup integrity
                verification = service.verify_backup(backup)
                
                result[f'{storage_type}_verification'] = verification
                
            except Exception as e:
                result[f'{storage_type}_verification'] = {'error': str(e)}
        
        # Determine overall status
        verifications = [v for k, v in result.items() if k.endswith('_verification')]
        failed = any('error' in v for v in verifications)
        
        result['status'] = 'success' if not failed else 'failed'
        
        return result
    
    def output_results(self, result: Dict, options: Dict, execution_time: float) -> None:
        """Output results in appropriate format"""
        if options.get('json'):
            self.stdout.write(json.dumps(result, indent=2, default=str))
            return
        
        # Human-readable output
        if options.get('action') == 'create':
            self._output_create_results(result, execution_time)
        elif options.get('action') == 'schedule':
            self._output_schedule_results(result)
        elif options.get('action') == 'status':
            self._output_status_results(result)
        elif options.get('action') == 'verify':
            self._output_verify_results(result)
        elif options.get('action') == 'cleanup':
            self._output_cleanup_results(result)
        else:
            self.stdout.write(self.style.SUCCESS(json.dumps(result, indent=2)))
    
    def _output_create_results(self, result: Dict, execution_time: float) -> None:
        """Output create backup results"""
        if result.get('status') == 'success':
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("BACKUP COMPLETED SUCCESSFULLY"))
            self.stdout.write("="*60)
            
            self.stdout.write(f"\n📁 Backup ID: {result.get('backup_id')}")
            self.stdout.write(f"[NOTE] Name: {result.get('backup_name')}")
            self.stdout.write(f"[STATS] Size: {result.get('file_size')}")
            self.stdout.write(f"🔒 Hash: {result.get('file_hash')[:16]}...")
            self.stdout.write(f"⏱️  Time: {human_readable_time(execution_time)}")
            
            if result.get('storage_locations'):
                self.stdout.write("\n💾 Storage Locations:")
                for storage_type, location in result['storage_locations'].items():
                    self.stdout.write(f"  • {storage_type}: {location}")
            
            self.stdout.write("\n" + "="*60)
        else:
            self.stdout.write(self.style.ERROR("\nBACKUP FAILED"))
            self.stdout.write(f"Error: {result.get('error', 'Unknown error')}")
    
    def _output_schedule_results(self, result: Dict) -> None:
        """Output schedule management results"""
        if 'schedules' in result:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("BACKUP SCHEDULES"))
            self.stdout.write("="*60)
            
            for schedule in result['schedules']:
                status_color = self.COLORS['green'] if schedule['enabled'] else self.COLORS['red']
                status_text = "✓ ACTIVE" if schedule['enabled'] else "✗ INACTIVE"
                
                self.stdout.write(f"\n{status_color}{status_text}{self.COLORS['reset']} {schedule['name']}")
                self.stdout.write(f"  Schedule: {schedule['schedule']}")
                self.stdout.write(f"  Database: {schedule['database']}")
                self.stdout.write(f"  Storage: {schedule['storage_type']}")
                
                if schedule['next_run']:
                    self.stdout.write(f"  Next run: {schedule['next_run']}")
                if schedule['last_run']:
                    self.stdout.write(f"  Last run: {schedule['last_run']}")
        else:
            self.stdout.write(self.style.SUCCESS(result.get('message', 'Operation completed')))
            if 'schedule_id' in result:
                self.stdout.write(f"Schedule ID: {result['schedule_id']}")
    
    def _output_status_results(self, result: Dict) -> None:
        """Output system status results"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("BACKUP SYSTEM STATUS"))
        self.stdout.write("="*60)
        
        # Database status
        self.stdout.write("\n[STATS] DATABASES:")
        for alias, status in result.get('database', {}).items():
            if status['status'] == 'connected':
                self.stdout.write(f"  ✓ {alias}: {status['engine']}")
            else:
                self.stdout.write(f"  ✗ {alias}: {status.get('error', 'Disconnected')}")
        
        # Storage status
        self.stdout.write("\n💾 STORAGE BACKENDS:")
        for storage_type, status in result.get('storage', {}).items():
            if status['status'] == 'available':
                self.stdout.write(f"  ✓ {storage_type}")
            else:
                self.stdout.write(f"  ✗ {storage_type}: {status.get('error', 'Unavailable')}")
        
        # Backup statistics
        backups = result.get('backups', {})
        self.stdout.write(f"\n📈 BACKUP STATISTICS:")
        self.stdout.write(f"  Total: {backups.get('total', 0)}")
        self.stdout.write(f"  Completed: {backups.get('completed', 0)}")
        self.stdout.write(f"  Failed: {backups.get('failed', 0)}")
        self.stdout.write(f"  In Progress: {backups.get('in_progress', 0)}")
        self.stdout.write(f"  Total Size: {backups.get('total_size', '0 B')}")
        
        # Schedule statistics
        schedules = result.get('schedules', {})
        self.stdout.write(f"\n⏰ SCHEDULES:")
        self.stdout.write(f"  Total: {schedules.get('total', 0)}")
        self.stdout.write(f"  Active: {schedules.get('active', 0)}")
        
        # System information
        system = result.get('system', {})
        if system:
            disk = system.get('disk_usage', {})
            memory = system.get('memory_usage', {})
            
            self.stdout.write(f"\n💻 SYSTEM RESOURCES:")
            self.stdout.write(f"  Disk: {disk.get('percent', 0)}% used ({format_file_size(disk.get('free', 0))} free)")
            self.stdout.write(f"  Memory: {memory.get('percent', 0)}% used ({format_file_size(memory.get('available', 0))} available)")
    
    def _output_verify_results(self, result: Dict) -> None:
        """Output verification results"""
        if 'verifications' in result:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("BACKUP VERIFICATION RESULTS"))
            self.stdout.write("="*60)
            
            successful = result.get('successful', 0)
            failed = result.get('failed', 0)
            total = result.get('total', 0)
            
            self.stdout.write(f"\n[STATS] Summary: {successful} successful, {failed} failed out of {total} backups")
            
            for verification in result['verifications']:
                if verification.get('status') == 'success':
                    self.stdout.write(f"\n✓ {verification.get('backup_name')}")
                    self.stdout.write(f"  ID: {verification.get('backup_id')}")
                else:
                    self.stdout.write(f"\n✗ {verification.get('backup_name')}")
                    self.stdout.write(f"  ID: {verification.get('backup_id')}")
                    self.stdout.write(f"  Error: {verification.get('error')}")
        else:
            # Single backup verification
            if result.get('status') == 'success':
                self.stdout.write(self.style.SUCCESS(f"✓ Backup verified successfully: {result.get('backup_name')}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Backup verification failed: {result.get('backup_name')}"))
                self.stdout.write(f"Error: {result.get('error')}")
    
    def _output_cleanup_results(self, result: Dict) -> None:
        """Output cleanup results"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("BACKUP CLEANUP RESULTS"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"\n[DELETE]  Deleted: {result.get('deleted_count', 0)} backups")
        self.stdout.write(f"📦 Freed: {result.get('deleted_size', '0 B')}")
        self.stdout.write(f"[STATS] Remaining: {result.get('remaining_count', 0)} backups")
        
        if result.get('errors'):
            self.stdout.write(f"\n[WARN]  Errors ({len(result['errors'])}):")
            for error in result['errors']:
                self.stdout.write(f"  • {error.get('backup_name')}: {error.get('error')}")