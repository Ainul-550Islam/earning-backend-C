"""
Verify Backups Management Command
Comprehensive backup verification with multiple verification methods
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from django.conf import settings

from api.backup.models import Backup, BackupVerification, BackupAlert
from api.backup.services.BackupValidator import BackupValidator
from api.backup.services.factory import BackupServiceFactory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verify backup integrity with multiple verification methods'
    
    def add_arguments(self, parser):
        # Verification scope
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Verify backups from last N days (default: 7)'
        )
        
        parser.add_argument(
            '--backup-id',
            type=str,
            help='Verify specific backup by ID'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            choices=['completed', 'failed', 'all'],
            default='completed',
            help='Filter by backup status (default: completed)'
        )
        
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Filter by storage type'
        )
        
        # Verification methods
        parser.add_argument(
            '--method',
            type=str,
            choices=['hash', 'size', 'test_restore', 'full'],
            default='hash',
            help='Verification method (default: hash)'
        )
        
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Number of parallel verification processes'
        )
        
        # Actions
        parser.add_argument(
            '--create-alerts',
            action='store_true',
            help='Create alerts for failed verifications'
        )
        
        parser.add_argument(
            '--delete-invalid',
            action='store_true',
            help='Delete backups that fail verification'
        )
        
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry verification for previously failed backups'
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
            help='Log verification results to file'
        )
        
        # Test restore options
        parser.add_argument(
            '--test-db-prefix',
            type=str,
            default='test_restore_',
            help='Prefix for test restore databases'
        )
        
        parser.add_argument(
            '--cleanup-test-db',
            action='store_true',
            help='Clean up test databases after verification'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Setup logging
            self._setup_logging(options)
            
            # Get backups to verify
            backups = self._get_backups_to_verify(options)
            
            if not backups:
                self.stdout.write(self.style.WARNING('No backups found for verification'))
                return
            
            self.stdout.write(f"Found {len(backups)} backups to verify")
            
            # Perform verification
            results = self._verify_backups(backups, options)
            
            # Generate report
            self._generate_report(results, options)
            
            # Handle failed verifications
            if options.get('create_alerts'):
                self._create_alerts(results, options)
            
            if options.get('delete_invalid'):
                self._delete_invalid_backups(results, options)
            
            # Final summary
            self._print_summary(results)
            
        except KeyboardInterrupt:
            self.stderr.write(self.style.ERROR('Verification interrupted by user'))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Verification failed: {str(e)}'))
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
    
    def _get_backups_to_verify(self, options) -> List[Backup]:
        """Get list of backups to verify"""
        queryset = Backup.objects.all()
        
        # Filter by backup ID
        if options.get('backup_id'):
            queryset = queryset.filter(backup_id=options['backup_id'])
        else:
            # Filter by date range
            days = options.get('days', 7)
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        # Filter by status
        status = options.get('status', 'completed')
        if status != 'all':
            queryset = queryset.filter(status=status)
        
        # Filter by storage type
        if options.get('storage_type'):
            queryset = queryset.filter(storage_type=options['storage_type'])
        
        # Exclude already verified if not retrying
        if not options.get('retry_failed'):
            recent_verifications = BackupVerification.objects.filter(
                verified_at__gte=timezone.now() - timedelta(hours=24)
            ).values_list('backup_id', flat=True)
            queryset = queryset.exclude(id__in=recent_verifications)
        
        return list(queryset.order_by('-created_at'))
    
    def _verify_backups(self, backups: List[Backup], options) -> List[Dict]:
        """Perform backup verification"""
        results = []
        validator = BackupValidator()
        method = options.get('method', 'hash')
        parallel = options.get('parallel', 1)
        
        if parallel > 1:
            # Parallel verification
            results = self._verify_backups_parallel(backups, validator, method, options)
        else:
            # Sequential verification
            for backup in backups:
                result = self._verify_single_backup(backup, validator, method, options)
                results.append(result)
                
                if not options.get('quiet'):
                    status = "✓" if result['valid'] else "✗"
                    self.stdout.write(f"{status} {backup.name} - {result['message']}")
        
        return results
    
    def _verify_single_backup(self, backup: Backup, validator: BackupValidator, 
                            method: str, options) -> Dict:
        """Verify a single backup"""
        result = {
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'storage_type': backup.storage_type,
            'created_at': backup.created_at.isoformat(),
            'method': method,
            'valid': False,
            'message': '',
            'details': {},
            'verification_id': None,
            'error': None
        }
        
        try:
            # Create verification record
            verification = BackupVerification.objects.create(
                backup=backup,
                verification_method=method,
                verified_by=None  # Can be set to current user
            )
            result['verification_id'] = str(verification.verification_id)
            
            # Perform verification based on method
            if method == 'hash':
                success = self._verify_hash(backup, validator, verification, result)
            elif method == 'size':
                success = self._verify_size(backup, validator, verification, result)
            elif method == 'test_restore':
                success = self._verify_test_restore(backup, validator, verification, result, options)
            elif method == 'full':
                success = self._verify_full(backup, validator, verification, result, options)
            
            verification.is_valid = success
            verification.save()
            
            result['valid'] = success
            result['message'] = 'Verification passed' if success else 'Verification failed'
            
        except Exception as e:
            error_msg = str(e)
            result['error'] = error_msg
            result['message'] = f'Verification error: {error_msg}'
            
            if 'verification' in locals():
                verification.is_valid = False
                verification.error_message = error_msg
                verification.save()
            
            logger.error(f"Verification failed for {backup.name}: {error_msg}")
        
        return result
    
    def _verify_hash(self, backup: Backup, validator: BackupValidator, 
                    verification: BackupVerification, result: Dict) -> bool:
        """Verify backup file hash"""
        try:
            if not backup.file_hash:
                result['message'] = 'No file hash available'
                return False
            
            # Get storage service
            storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
            
            # Verify file integrity
            checksum_match = validator.verify_file_integrity(
                backup.storage_location,
                backup.file_hash
            )
            
            verification.checksum_match = checksum_match
            result['details']['checksum_match'] = checksum_match
            
            return checksum_match
            
        except Exception as e:
            result['details']['hash_error'] = str(e)
            return False
    
    def _verify_size(self, backup: Backup, validator: BackupValidator,
                    verification: BackupVerification, result: Dict) -> bool:
        """Verify backup file size"""
        try:
            if not backup.file_size:
                result['message'] = 'No file size available'
                return False
            
            # Get storage service
            storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
            
            # Verify file size
            size_match = validator.verify_file_size(
                backup.storage_location,
                backup.file_size
            )
            
            verification.size_match = size_match
            result['details']['size_match'] = size_match
            result['details']['expected_size'] = backup.file_size
            
            return size_match
            
        except Exception as e:
            result['details']['size_error'] = str(e)
            return False
    
    def _verify_test_restore(self, backup: Backup, validator: BackupValidator,
                           verification: BackupVerification, result: Dict, options: Dict) -> bool:
        """Test restore backup to temporary database"""
        try:
            test_db_prefix = options.get('test_db_prefix', 'test_restore_')
            cleanup = options.get('cleanup_test_db', False)
            
            # Perform test restore
            test_result = validator.test_restore_backup(
                backup,
                test_db_prefix=test_db_prefix,
                cleanup=cleanup
            )
            
            verification.verification_details = {'test_restore': test_result}
            result['details']['test_restore'] = test_result
            
            return test_result
            
        except Exception as e:
            result['details']['test_restore_error'] = str(e)
            return False
    
    def _verify_full(self, backup: Backup, validator: BackupValidator,
                    verification: BackupVerification, result: Dict, options: Dict) -> bool:
        """Perform full verification (hash + size + test restore)"""
        # Verify hash
        hash_valid = self._verify_hash(backup, validator, verification, result)
        
        # Verify size
        size_valid = self._verify_size(backup, validator, verification, result)
        
        # Test restore
        test_valid = self._verify_test_restore(backup, validator, verification, result, options)
        
        # Combined result
        overall_valid = hash_valid and size_valid and test_valid
        
        verification.checksum_match = hash_valid
        verification.size_match = size_valid
        verification.verification_details = {
            'hash_valid': hash_valid,
            'size_valid': size_valid,
            'test_restore_valid': test_valid
        }
        
        result['details']['combined'] = {
            'hash_valid': hash_valid,
            'size_valid': size_valid,
            'test_restore_valid': test_valid,
            'overall_valid': overall_valid
        }
        
        return overall_valid
    
    def _verify_backups_parallel(self, backups: List[Backup], validator: BackupValidator,
                               method: str, options: Dict) -> List[Dict]:
        """Verify backups in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        parallel = options.get('parallel', 1)
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all verification tasks
            future_to_backup = {
                executor.submit(self._verify_single_backup, backup, validator, method, options): backup
                for backup in backups
            }
            
            # Collect results
            for future in as_completed(future_to_backup):
                backup = future_to_backup[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not options.get('quiet'):
                        status = "✓" if result['valid'] else "✗"
                        self.stdout.write(f"{status} {backup.name} - {result['message']}")
                        
                except Exception as e:
                    error_result = {
                        'backup_id': str(backup.backup_id),
                        'backup_name': backup.name,
                        'valid': False,
                        'message': f'Verification error: {str(e)}',
                        'error': str(e)
                    }
                    results.append(error_result)
        
        return results
    
    def _generate_report(self, results: List[Dict], options: Dict):
        """Generate verification report"""
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
        self.stdout.write("VERIFICATION REPORT")
        self.stdout.write("="*80)
        
        # Summary
        total = len(results)
        valid = sum(1 for r in results if r['valid'])
        invalid = total - valid
        
        self.stdout.write(f"Total: {total}, Valid: {valid}, Invalid: {invalid}")
        self.stdout.write("-" * 80)
        
        # Detailed results
        for result in results:
            status = "✓ VALID" if result['valid'] else "✗ INVALID"
            self.stdout.write(f"{status} | {result['backup_name'][:30]:30} | {result['method'][:10]:10} | {result['message'][:40]:40}")
    
    def _generate_json_report(self, results: List[Dict]):
        """Generate JSON format report"""
        report = {
            'timestamp': timezone.now().isoformat(),
            'total_backups': len(results),
            'valid_backups': sum(1 for r in results if r['valid']),
            'invalid_backups': sum(1 for r in results if not r['valid']),
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
            'method', 'valid', 'message', 'error'
        ])
        
        # Data
        for result in results:
            writer.writerow([
                result['backup_id'],
                result['backup_name'],
                result['backup_type'],
                result['storage_type'],
                result['method'],
                result['valid'],
                result['message'],
                result.get('error', '')
            ])
        
        self.stdout.write(output.getvalue())
    
    def _create_alerts(self, results: List[Dict], options: Dict):
        """Create alerts for failed verifications"""
        failed_results = [r for r in results if not r['valid']]
        
        for result in failed_results:
            try:
                backup = Backup.objects.get(backup_id=result['backup_id'])
                
                BackupAlert.create_alert(
                    alert_type='verification_failed',
                    message=f"Backup verification failed: {result['message']}",
                    backup=backup,
                    severity='high',
                    metadata={
                        'verification_method': result['method'],
                        'verification_details': result['details'],
                        'error': result.get('error')
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to create alert for {result['backup_name']}: {str(e)}")
        
        if failed_results:
            self.stdout.write(f"Created {len(failed_results)} alerts for failed verifications")
    
    def _delete_invalid_backups(self, results: List[Dict], options: Dict):
        """Delete backups that failed verification"""
        failed_results = [r for r in results if not r['valid']]
        deleted_count = 0
        
        for result in failed_results:
            try:
                backup = Backup.objects.get(backup_id=result['backup_id'])
                
                # Delete backup file
                storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
                storage_service.delete_backup(backup)
                
                # Delete backup record
                backup.delete()
                deleted_count += 1
                
                if not options.get('quiet'):
                    self.stdout.write(f"Deleted invalid backup: {backup.name}")
                
            except Exception as e:
                logger.error(f"Failed to delete backup {result['backup_name']}: {str(e)}")
        
        if deleted_count > 0:
            self.stdout.write(f"Deleted {deleted_count} invalid backups")
    
    def _print_summary(self, results: List[Dict]):
        """Print verification summary"""
        total = len(results)
        valid = sum(1 for r in results if r['valid'])
        invalid = total - valid
        success_rate = (valid / total * 100) if total > 0 else 0
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("VERIFICATION SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total Backups: {total}")
        self.stdout.write(f"Valid: {valid} ({valid/total*100:.1f}%)" if total > 0 else "Valid: 0")
        self.stdout.write(f"Invalid: {invalid} ({invalid/total*100:.1f}%)" if total > 0 else "Invalid: 0")
        self.stdout.write(f"Success Rate: {success_rate:.1f}%")
        self.stdout.write("="*50)
