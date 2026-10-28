"""
Cleanup Old Backups Management Command
Comprehensive backup cleanup based on retention policies and various criteria
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.conf import settings

from api.backup.models import Backup, BackupStorageLocation, BackupAlert, BackupSchedule
from api.backup.services.factory import BackupServiceFactory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old backups based on retention policies and criteria'
    
    def add_arguments(self, parser):
        # Cleanup criteria
        parser.add_argument(
            '--days',
            type=int,
            help='Delete backups older than N days'
        )
        
        parser.add_argument(
            '--retention-policy',
            type=str,
            help='Use specific retention policy name'
        )
        
        parser.add_argument(
            '--gfs',
            action='store_true',
            help='Use Grandfather-Father-Son (GFS) retention policy'
        )
        
        parser.add_argument(
            '--keep-weekly',
            type=int,
            default=4,
            help='Number of weekly backups to keep with GFS (default: 4)'
        )
        
        parser.add_argument(
            '--keep-monthly',
            type=int,
            default=12,
            help='Number of monthly backups to keep with GFS (default: 12)'
        )
        
        parser.add_argument(
            '--keep-yearly',
            type=int,
            default=5,
            help='Number of yearly backups to keep with GFS (default: 5)'
        )
        
        # Filter options
        parser.add_argument(
            '--backup-type',
            type=str,
            choices=['full', 'incremental', 'differential', 'partial'],
            help='Only clean specific backup types'
        )
        
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Only clean specific storage types'
        )
        
        parser.add_argument(
            '--database',
            type=str,
            help='Only clean specific databases'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            choices=['completed', 'failed', 'all'],
            default='completed',
            help='Filter by backup status (default: completed)'
        )
        
        parser.add_argument(
            '--size-greater-than',
            type=str,
            help='Clean backups larger than specified size (e.g., 1GB, 500MB)'
        )
        
        # Safety options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )
        
        parser.add_argument(
            '--keep-last',
            type=int,
            default=1,
            help='Always keep the last N backups (default: 1)'
        )
        
        parser.add_argument(
            '--exclude-permanent',
            action='store_true',
            default=True,
            help='Exclude permanent backups from cleanup (default: True)'
        )
        
        # Storage options
        parser.add_argument(
            '--check-storage',
            action='store_true',
            help='Check if backup files exist before deleting records'
        )
        
        parser.add_argument(
            '--cleanup-orphaned',
            action='store_true',
            help='Clean up orphaned backup records (files exist but records missing)'
        )
        
        # Output options
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'csv'],
            default='table',
            help='Output format (default: table)'
        )
        
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress verbose output'
        )
        
        parser.add_argument(
            '--log-file',
            type=str,
            help='Log cleanup results to file'
        )
        
        parser.add_argument(
            '--create-alerts',
            action='store_true',
            help='Create alerts for deleted backups'
        )
        
        # Performance options
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Process backups in batches (default: 100)'
        )
        
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Number of parallel deletion processes'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Setup logging
            self._setup_logging(options)
            
            # Get backups to clean
            backups_to_clean = self._get_backups_to_clean(options)
            
            if not backups_to_clean:
                self.stdout.write(self.style.SUCCESS('No backups found for cleanup'))
                return
            
            # Show summary
            self._show_cleanup_summary(backups_to_clean, options)
            
            # Confirm deletion
            if not options.get('confirm') and not options.get('dry_run'):
                if not self._confirm_cleanup(backups_to_clean):
                    self.stdout.write('Cleanup cancelled by user')
                    return
            
            # Perform cleanup
            results = self._cleanup_backups(backups_to_clean, options)
            
            # Generate report
            self._generate_report(results, options)
            
            # Create alerts if requested
            if options.get('create_alerts'):
                self._create_cleanup_alerts(results, options)
            
            # Final summary
            self._print_cleanup_summary(results)
            
        except KeyboardInterrupt:
            self.stderr.write(self.style.ERROR('Cleanup interrupted by user'))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Cleanup failed: {str(e)}'))
            if options.get('verbose'):
                import traceback
                self.stderr.write(traceback.format_exc())
            sys.exit(1)
    
    def _setup_logging(self, options):
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
    
    def _get_backups_to_clean(self, options) -> List[Backup]:
        """Get list of backups to clean up"""
        queryset = Backup.objects.all()
        
        # Apply filters
        if options.get('backup_type'):
            queryset = queryset.filter(backup_type=options['backup_type'])
        
        if options.get('storage_type'):
            queryset = queryset.filter(storage_type=options['storage_type'])
        
        if options.get('database'):
            queryset = queryset.filter(database_name=options['database'])
        
        status = options.get('status', 'completed')
        if status != 'all':
            queryset = queryset.filter(status=status)
        
        if options.get('size_greater_than'):
            size_bytes = self._parse_size_string(options['size_greater_than'])
            if size_bytes:
                queryset = queryset.filter(file_size__gte=size_bytes)
        
        # Exclude permanent backups
        if options.get('exclude_permanent', True):
            queryset = queryset.filter(is_permanent=False)
        
        # Apply retention criteria
        if options.get('days'):
            cutoff_date = timezone.now() - timedelta(days=options['days'])
            queryset = queryset.filter(created_at__lt=cutoff_date)
        elif options.get('gfs'):
            queryset = self._apply_gfs_retention(queryset, options)
        elif options.get('retention_policy'):
            queryset = self._apply_retention_policy(queryset, options['retention_policy'])
        else:
            # Default: use retention_days field
            queryset = self._apply_default_retention(queryset)
        
        # Keep last N backups
        keep_last = options.get('keep_last', 1)
        if keep_last > 0:
            latest_backups = queryset.order_by('-created_at')[:keep_last].values_list('id', flat=True)
            queryset = queryset.exclude(id__in=latest_backups)
        
        return list(queryset.order_by('-created_at'))
    
    def _apply_gfs_retention(self, queryset, options):
        """Apply Grandfather-Father-Son retention policy"""
        # Get all backups grouped by type and database
        backups = list(queryset.order_by('-created_at'))
        
        keep_weekly = options.get('keep_weekly', 4)
        keep_monthly = options.get('keep_monthly', 12)
        keep_yearly = options.get('keep_yearly', 5)
        
        # Group backups by year, month, week
        groups = {}
        for backup in backups:
            created_date = backup.created_at.date()
            year = created_date.year
            month = created_date.month
            week = created_date.isocalendar()[1]
            
            key = (backup.backup_type, backup.database_name, year, month, week)
            if key not in groups:
                groups[key] = []
            groups[key].append(backup)
        
        # Select backups to keep
        backups_to_keep = set()
        
        # Keep yearly backups
        yearly_groups = {}
        for backup in backups:
            year = backup.created_at.year
            key = (backup.backup_type, backup.database_name, year)
            if key not in yearly_groups:
                yearly_groups[key] = []
            yearly_groups[key].append(backup)
        
        for key, group_backups in yearly_groups.items():
            # Keep the newest backup for each year
            if group_backups:
                backups_to_keep.add(group_backups[0].id)
        
        # Keep monthly backups
        monthly_groups = {}
        for backup in backups:
            year = backup.created_at.year
            month = backup.created_at.month
            key = (backup.backup_type, backup.database_name, year, month)
            if key not in monthly_groups:
                monthly_groups[key] = []
            monthly_groups[key].append(backup)
        
        for key, group_backups in monthly_groups.items():
            # Keep the newest backup for each month
            if group_backups:
                backups_to_keep.add(group_backups[0].id)
        
        # Keep weekly backups
        weekly_groups = {}
        for backup in backups:
            year = backup.created_at.year
            week = backup.created_at.isocalendar()[1]
            key = (backup.backup_type, backup.database_name, year, week)
            if key not in weekly_groups:
                weekly_groups[key] = []
            weekly_groups[key].append(backup)
        
        for key, group_backups in weekly_groups.items():
            # Keep the newest backup for each week
            if group_backups:
                backups_to_keep.add(group_backups[0].id)
        
        # Return backups to delete (exclude those to keep)
        return queryset.exclude(id__in=backups_to_keep)
    
    def _apply_retention_policy(self, queryset, policy_name):
        """Apply specific retention policy"""
        # This would integrate with RetentionPolicy model
        # For now, return default retention
        return self._apply_default_retention(queryset)
    
    def _apply_default_retention(self, queryset):
        """Apply default retention based on retention_days field"""
        # Filter by retention days
        cutoff_date = timezone.now()
        backups_to_keep = set()
        
        for backup in queryset:
            if backup.retention_days:
                expiry_date = backup.created_at + timedelta(days=backup.retention_days)
                if expiry_date > cutoff_date:
                    backups_to_keep.add(backup.id)
            elif backup.expires_at and backup.expires_at > cutoff_date:
                backups_to_keep.add(backup.id)
        
        return queryset.exclude(id__in=backups_to_keep)
    
    def _parse_size_string(self, size_str):
        """Parse size string like '1GB', '500MB' to bytes"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('TB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024 * 1024)
        elif size_str.endswith('GB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        elif size_str.endswith('MB'):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith('B'):
            return int(float(size_str[:-1]))
        else:
            # Assume bytes
            return int(size_str)
    
    def _show_cleanup_summary(self, backups: List[Backup], options):
        """Show summary of backups to be cleaned"""
        total_count = len(backups)
        total_size = sum(b.file_size or 0 for b in backups)
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("CLEANUP SUMMARY")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Backups to delete: {total_count}")
        self.stdout.write(f"Total size: {self._format_size(total_size)}")
        
        if options.get('dry_run'):
            self.stdout.write("DRY RUN MODE - No files will be deleted")
        
        # Group by storage type
        storage_summary = {}
        for backup in backups:
            storage_type = backup.storage_type
            if storage_type not in storage_summary:
                storage_summary[storage_type] = {'count': 0, 'size': 0}
            storage_summary[storage_type]['count'] += 1
            storage_summary[storage_type]['size'] += backup.file_size or 0
        
        self.stdout.write("\nBy storage type:")
        for storage_type, info in storage_summary.items():
            self.stdout.write(f"  {storage_type}: {info['count']} backups ({self._format_size(info['size'])})")
        
        self.stdout.write(f"{'='*60}")
    
    def _confirm_cleanup(self, backups: List[Backup]) -> bool:
        """Confirm cleanup with user"""
        total_count = len(backups)
        total_size = sum(b.file_size or 0 for b in backups)
        
        self.stdout.write(f"\nWARNING: You are about to delete {total_count} backups")
        self.stdout.write(f"Total size to be freed: {self._format_size(total_size)}")
        self.stdout.write("This action cannot be undone!")
        
        response = input("\nAre you sure you want to continue? (yes/no): ")
        return response.lower() in ['yes', 'y']
    
    def _cleanup_backups(self, backups: List[Backup], options) -> List[Dict]:
        """Perform the actual cleanup"""
        results = []
        batch_size = options.get('batch_size', 100)
        parallel = options.get('parallel', 1)
        
        if parallel > 1:
            # Parallel cleanup
            results = self._cleanup_backups_parallel(backups, options)
        else:
            # Sequential cleanup in batches
            for i in range(0, len(backups), batch_size):
                batch = backups[i:i + batch_size]
                batch_results = self._cleanup_backup_batch(batch, options)
                results.extend(batch_results)
                
                if not options.get('quiet'):
                    self.stdout.write(f"Processed batch {i//batch_size + 1}/{(len(backups) + batch_size - 1)//batch_size}")
        
        return results
    
    def _cleanup_backup_batch(self, backups: List[Backup], options) -> List[Dict]:
        """Clean up a batch of backups"""
        results = []
        
        for backup in backups:
            result = self._cleanup_single_backup(backup, options)
            results.append(result)
            
            if not options.get('quiet'):
                status = "✓" if result['deleted'] else "✗"
                message = result['message']
                self.stdout.write(f"{status} {backup.name[:40]:40} | {message}")
        
        return results
    
    def _cleanup_single_backup(self, backup: Backup, options) -> Dict:
        """Clean up a single backup"""
        result = {
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'storage_type': backup.storage_type,
            'file_size': backup.file_size,
            'created_at': backup.created_at.isoformat(),
            'deleted': False,
            'message': '',
            'error': None
        }
        
        try:
            if options.get('dry_run'):
                result['deleted'] = True
                result['message'] = 'Would be deleted (dry run)'
                return result
            
            # Check if backup file exists
            if options.get('check_storage'):
                storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
                if not storage_service.backup_exists(backup):
                    result['message'] = 'Backup file not found - deleting record only'
                else:
                    result['message'] = 'Backup file exists - deleting file and record'
            
            # Delete backup file
            storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
            storage_service.delete_backup(backup)
            
            # Delete backup record
            backup_name = backup.name
            backup.delete()
            
            result['deleted'] = True
            result['message'] = 'Successfully deleted'
            
            logger.info(f"Deleted backup: {backup_name}")
            
        except Exception as e:
            result['error'] = str(e)
            result['message'] = f'Deletion failed: {str(e)}'
            logger.error(f"Failed to delete backup {backup.name}: {str(e)}")
        
        return result
    
    def _cleanup_backups_parallel(self, backups: List[Backup], options: Dict) -> List[Dict]:
        """Clean up backups in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        parallel = options.get('parallel', 1)
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all cleanup tasks
            future_to_backup = {
                executor.submit(self._cleanup_single_backup, backup, options): backup
                for backup in backups
            }
            
            # Collect results
            for future in as_completed(future_to_backup):
                backup = future_to_backup[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not options.get('quiet'):
                        status = "✓" if result['deleted'] else "✗"
                        message = result['message']
                        self.stdout.write(f"{status} {backup.name[:40]:40} | {message}")
                        
                except Exception as e:
                    error_result = {
                        'backup_id': str(backup.backup_id),
                        'backup_name': backup.name,
                        'deleted': False,
                        'message': f'Cleanup error: {str(e)}',
                        'error': str(e)
                    }
                    results.append(error_result)
        
        return results
    
    def _generate_report(self, results: List[Dict], options: Dict):
        """Generate cleanup report"""
        format_type = options.get('format', 'table')
        
        if format_type == 'json':
            self._generate_json_report(results)
        elif format_type == 'csv':
            self._generate_csv_report(results)
        else:
            self._generate_table_report(results)
    
    def _generate_table_report(self, results: List[Dict]):
        """Generate table format report"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write("CLEANUP REPORT")
        self.stdout.write("="*80)
        
        # Summary
        total = len(results)
        deleted = sum(1 for r in results if r['deleted'])
        failed = total - deleted
        total_size = sum(r['file_size'] or 0 for r in results if r['deleted'])
        
        self.stdout.write(f"Total: {total}, Deleted: {deleted}, Failed: {failed}")
        self.stdout.write(f"Space freed: {self._format_size(total_size)}")
        self.stdout.write("-" * 80)
        
        # Detailed results
        for result in results:
            status = "✓ DELETED" if result['deleted'] else "✗ FAILED"
            size_str = self._format_size(result['file_size']) if result['file_size'] else "N/A"
            self.stdout.write(f"{status} | {result['backup_name'][:30]:30} | {size_str[:10]:10} | {result['message'][:35]:35}")
    
    def _generate_json_report(self, results: List[Dict]):
        """Generate JSON format report"""
        total_size = sum(r['file_size'] or 0 for r in results if r['deleted'])
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'total_backups': len(results),
            'deleted_backups': sum(1 for r in results if r['deleted']),
            'failed_backups': sum(1 for r in results if not r['deleted']),
            'space_freed': total_size,
            'space_freed_human': self._format_size(total_size),
            'results': results
        }
        
        self.stdout.write(json.dumps(report, indent=2))
    
    def _generate_csv_report(self, results: List[Dict]):
        """Generate CSV format report"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'backup_id', 'backup_name', 'backup_type', 'storage_type',
            'file_size', 'created_at', 'deleted', 'message', 'error'
        ])
        
        # Data
        for result in results:
            writer.writerow([
                result['backup_id'],
                result['backup_name'],
                result['backup_type'],
                result['storage_type'],
                result['file_size'],
                result['created_at'],
                result['deleted'],
                result['message'],
                result.get('error', '')
            ])
        
        self.stdout.write(output.getvalue())
    
    def _create_cleanup_alerts(self, results: List[Dict], options: Dict):
        """Create alerts for deleted backups"""
        deleted_results = [r for r in results if r['deleted']]
        
        for result in deleted_results:
            try:
                BackupAlert.create_alert(
                    alert_type='retention_expired',
                    message=f"Backup deleted due to retention policy: {result['backup_name']}",
                    backup=None,  # Backup record is deleted
                    severity='low',
                    metadata={
                        'backup_id': result['backup_id'],
                        'backup_name': result['backup_name'],
                        'backup_type': result['backup_type'],
                        'storage_type': result['storage_type'],
                        'file_size': result['file_size'],
                        'deleted_at': timezone.now().isoformat()
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to create cleanup alert for {result['backup_name']}: {str(e)}")
        
        if deleted_results:
            self.stdout.write(f"Created {len(deleted_results)} cleanup alerts")
    
    def _print_cleanup_summary(self, results: List[Dict]):
        """Print final cleanup summary"""
        total = len(results)
        deleted = sum(1 for r in results if r['deleted'])
        failed = total - deleted
        total_size = sum(r['file_size'] or 0 for r in results if r['deleted'])
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("CLEANUP SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total Backups: {total}")
        self.stdout.write(f"Deleted: {deleted}")
        self.stdout.write(f"Failed: {failed}")
        self.stdout.write(f"Space Freed: {self._format_size(total_size)}")
        
        if failed > 0:
            self.stdout.write(f"Success Rate: {(deleted/total*100):.1f}%")
        
        self.stdout.write("="*50)
    
    def _format_size(self, size_bytes):
        """Format bytes as human readable size"""
        if not size_bytes:
            return "0 B"
        
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
