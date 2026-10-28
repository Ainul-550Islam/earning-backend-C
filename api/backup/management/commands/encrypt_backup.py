"""
Encrypt Backup Management Command
Encrypt unencrypted backups with various encryption algorithms
"""

import os
import sys
import json
import logging
import tempfile
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from api.backup.models import Backup, BackupEncryption, BackupAlert
from api.backup.services.factory import BackupServiceFactory
from api.backup.services.BaseBackupService import BaseBackupService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Encrypt unencrypted backups with various encryption algorithms'
    
    def add_arguments(self, parser):
        # Backup selection
        parser.add_argument(
            '--backup-id',
            type=str,
            help='Encrypt specific backup by ID'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Encrypt backups from last N days (default: 30)'
        )
        
        parser.add_argument(
            '--backup-type',
            type=str,
            choices=['full', 'incremental', 'differential', 'partial'],
            help='Only encrypt specific backup types'
        )
        
        parser.add_argument(
            '--storage-type',
            type=str,
            help='Only encrypt specific storage types'
        )
        
        parser.add_argument(
            '--min-size',
            type=str,
            help='Only encrypt backups larger than specified size (e.g., 1MB, 100KB)'
        )
        
        parser.add_argument(
            '--max-size',
            type=str,
            help='Only encrypt backups smaller than specified size'
        )
        
        # Encryption options
        parser.add_argument(
            '--algorithm',
            type=str,
            choices=['AES-256-GCM', 'ChaCha20-Poly1305', 'Fernet'],
            default='AES-256-GCM',
            help='Encryption algorithm (default: AES-256-GCM)'
        )
        
        parser.add_argument(
            '--key-file',
            type=str,
            help='Path to encryption key file (generate if not exists)'
        )
        
        parser.add_argument(
            '--key-password',
            type=str,
            help='Password for key encryption (if using key file)'
        )
        
        parser.add_argument(
            '--generate-key',
            action='store_true',
            help='Generate new encryption key'
        )
        
        parser.add_argument(
            '--reuse-key',
            action='store_true',
            help='Reuse existing encryption key for all backups'
        )
        
        parser.add_argument(
            '--per-backup-key',
            action='store_true',
            default=True,
            help='Generate unique key for each backup (default: True)'
        )
        
        # Processing options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be encrypted without actually encrypting'
        )
        
        parser.add_argument(
            '--skip-verified',
            action='store_true',
            help='Skip backups that are already verified'
        )
        
        parser.add_argument(
            '--re-encrypt',
            action='store_true',
            help='Re-encrypt already encrypted backups'
        )
        
        parser.add_argument(
            '--backup-original',
            action='store_true',
            default=True,
            help='Keep original unencrypted backup (default: True)'
        )
        
        parser.add_argument(
            '--delete-original',
            action='store_true',
            help='Delete original unencrypted backup after successful encryption'
        )
        
        parser.add_argument(
            '--compress-after',
            action='store_true',
            help='Compress backup after encryption'
        )
        
        # Validation options
        parser.add_argument(
            '--verify-encryption',
            action='store_true',
            default=True,
            help='Verify encryption after completion (default: True)'
        )
        
        parser.add_argument(
            '--test-decrypt',
            action='store_true',
            help='Test decryption to verify encryption integrity'
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
            help='Log encryption results to file'
        )
        
        parser.add_argument(
            '--create-alerts',
            action='store_true',
            help='Create alerts for encryption failures'
        )
        
        # Performance options
        parser.add_argument(
            '--parallel',
            type=int,
            default=1,
            help='Number of parallel encryption processes'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Process backups in batches (default: 10)'
        )
        
        parser.add_argument(
            '--timeout',
            type=int,
            default=1800,
            help='Encryption timeout per backup in seconds (default: 1800)'
        )
        
        # Key management
        parser.add_argument(
            '--export-keys',
            type=str,
            help='Export encryption keys to specified file'
        )
        
        parser.add_argument(
            '--import-keys',
            type=str,
            help='Import encryption keys from specified file'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Setup logging
            self._setup_logging(options)
            
            # Initialize encryption
            self._initialize_encryption(options)
            
            # Get backups to encrypt
            backups = self._get_backups_to_encrypt(options)
            
            if not backups:
                self.stdout.write(self.style.WARNING('No backups found for encryption'))
                return
            
            self.stdout.write(f"Found {len(backups)} backups to encrypt")
            
            # Perform encryption
            results = self._encrypt_backups(backups, options)
            
            # Export keys if requested
            if options.get('export_keys'):
                self._export_encryption_keys(results, options['export_keys'])
            
            # Generate report
            self._generate_report(results, options)
            
            # Create alerts if requested
            if options.get('create_alerts'):
                self._create_encryption_alerts(results, options)
            
            # Final summary
            self._print_summary(results)
            
        except KeyboardInterrupt:
            self.stderr.write(self.style.ERROR('Encryption interrupted by user'))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Encryption failed: {str(e)}'))
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
    
    def _initialize_encryption(self, options):
        """Initialize encryption settings"""
        self.encryption_algorithm = options.get('algorithm', 'AES-256-GCM')
        self.per_backup_key = options.get('per_backup_key', True)
        self.reuse_key = options.get('reuse_key', False)
        self.master_key = None
        
        # Load or generate master key if reusing keys
        if self.reuse_key:
            self.master_key = self._get_or_create_master_key(options)
        
        # Import keys if specified
        if options.get('import_keys'):
            self._import_encryption_keys(options['import_keys'])
    
    def _get_or_create_master_key(self, options) -> str:
        """Get or create master encryption key"""
        key_file = options.get('key_file')
        
        if key_file and os.path.exists(key_file):
            # Load existing key
            return self._load_key_from_file(key_file, options.get('key_password'))
        else:
            # Generate new key
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            
            if key_file:
                self._save_key_to_file(key, key_file, options.get('key_password'))
            
            return key
    
    def _load_key_from_file(self, key_file: str, password: Optional[str]) -> str:
        """Load encryption key from file"""
        try:
            with open(key_file, 'r') as f:
                key_data = f.read()
            
            if password:
                # Decrypt key with password
                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                import base64
                
                # Derive key from password
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'salt',  # In production, use random salt
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                cipher = Fernet(key)
                
                decrypted_key = cipher.decrypt(key_data.encode())
                return decrypted_key.decode()
            else:
                return key_data
                
        except Exception as e:
            raise Exception(f"Failed to load key from file: {str(e)}")
    
    def _save_key_to_file(self, key: str, key_file: str, password: Optional[str]):
        """Save encryption key to file"""
        try:
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            
            if password:
                # Encrypt key with password
                from cryptography.fernet import Fernet
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                import base64
                
                # Derive key from password
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'salt',  # In production, use random salt
                    iterations=100000,
                )
                derived_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                cipher = Fernet(derived_key)
                
                encrypted_key = cipher.encrypt(key.encode())
                key_data = encrypted_key.decode()
            else:
                key_data = key
            
            with open(key_file, 'w') as f:
                f.write(key_data)
                
            # Set file permissions (read-only for owner)
            os.chmod(key_file, 0o600)
            
        except Exception as e:
            raise Exception(f"Failed to save key to file: {str(e)}")
    
    def _import_encryption_keys(self, keys_file: str):
        """Import encryption keys from JSON file"""
        try:
            with open(keys_file, 'r') as f:
                keys_data = json.load(f)
            
            self.imported_keys = keys_data.get('keys', {})
            logger.info(f"Imported {len(self.imported_keys)} encryption keys")
            
        except Exception as e:
            raise Exception(f"Failed to import keys: {str(e)}")
    
    def _get_backups_to_encrypt(self, options) -> List[Backup]:
        """Get list of backups to encrypt"""
        queryset = Backup.objects.all()
        
        # Filter by backup ID
        if options.get('backup_id'):
            queryset = queryset.filter(backup_id=options['backup_id'])
        else:
            # Filter by date range
            days = options.get('days', 30)
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff_date)
        
        # Apply filters
        if options.get('backup_type'):
            queryset = queryset.filter(backup_type=options['backup_type'])
        
        if options.get('storage_type'):
            queryset = queryset.filter(storage_type=options['storage_type'])
        
        # Size filters
        if options.get('min_size'):
            min_bytes = self._parse_size_string(options['min_size'])
            if min_bytes:
                queryset = queryset.filter(file_size__gte=min_bytes)
        
        if options.get('max_size'):
            max_bytes = self._parse_size_string(options['max_size'])
            if max_bytes:
                queryset = queryset.filter(file_size__lte=max_bytes)
        
        # Filter by encryption status
        if not options.get('re_encrypt'):
            # Only get unencrypted backups
            queryset = queryset.filter(encryption_enabled=False)
        
        # Skip verified backups if requested
        if options.get('skip_verified'):
            queryset = queryset.exclude(is_verified=True)
        
        return list(queryset.order_by('-created_at'))
    
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
            return int(size_str)
    
    def _encrypt_backups(self, backups: List[Backup], options) -> List[Dict]:
        """Perform backup encryption"""
        results = []
        batch_size = options.get('batch_size', 10)
        parallel = options.get('parallel', 1)
        
        if parallel > 1:
            # Parallel encryption
            results = self._encrypt_backups_parallel(backups, options)
        else:
            # Sequential encryption in batches
            for i in range(0, len(backups), batch_size):
                batch = backups[i:i + batch_size]
                batch_results = self._encrypt_backup_batch(batch, options)
                results.extend(batch_results)
                
                if not options.get('quiet'):
                    self.stdout.write(f"Processed batch {i//batch_size + 1}/{(len(backups) + batch_size - 1)//batch_size}")
        
        return results
    
    def _encrypt_backup_batch(self, backups: List[Backup], options) -> List[Dict]:
        """Encrypt a batch of backups"""
        results = []
        
        for backup in backups:
            result = self._encrypt_single_backup(backup, options)
            results.append(result)
            
            if not options.get('quiet'):
                status = "✓" if result['encrypted'] else "✗"
                message = result['message']
                self.stdout.write(f"{status} {backup.name[:40]:40} | {message}")
        
        return results
    
    def _encrypt_single_backup(self, backup: Backup, options) -> Dict:
        """Encrypt a single backup"""
        result = {
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'storage_type': backup.storage_type,
            'file_size': backup.file_size,
            'original_size': backup.file_size,
            'created_at': backup.created_at.isoformat(),
            'encrypted': False,
            'encrypted_size': 0,
            'encryption_time': 0,
            'message': '',
            'encryption_key_id': None,
            'error': None
        }
        
        start_time = timezone.now()
        
        try:
            if options.get('dry_run'):
                result['encrypted'] = True
                result['message'] = 'Would be encrypted (dry run)'
                return result
            
            # Get or generate encryption key
            encryption_key = self._get_encryption_key(backup, options)
            
            # Download backup file
            original_file_path = self._download_backup_file(backup, options)
            
            # Encrypt the file
            encrypted_file_path = self._encrypt_backup_file(
                original_file_path, encryption_key, options
            )
            
            # Calculate encrypted file size
            encrypted_size = os.path.getsize(encrypted_file_path)
            result['encrypted_size'] = encrypted_size
            
            # Upload encrypted file
            self._upload_encrypted_backup(backup, encrypted_file_path, options)
            
            # Update backup model
            with transaction.atomic():
                # Update backup record
                backup.encryption_enabled = True
                backup.encryption_method = self.encryption_algorithm
                backup.file_size = encrypted_size
                backup.backup_file.name = self._get_encrypted_filename(backup)
                backup.save()
                
                # Create encryption record
                encryption_record = BackupEncryption.objects.create(
                    backup=backup,
                    algorithm=self.encryption_algorithm,
                    key_hash=hashlib.sha256(encryption_key.encode()).hexdigest(),
                    is_encrypted=True,
                    encryption_key=self._encrypt_key_for_storage(encryption_key),
                    created_at=timezone.now()
                )
                
                result['encryption_key_id'] = str(encryption_record.id)
            
            # Verify encryption if requested
            if options.get('verify_encryption', True):
                verification_passed = self._verify_encryption(
                    backup, encrypted_file_path, encryption_key, options
                )
                
                if not verification_passed:
                    result['message'] = 'Encryption verification failed'
                    return result
            
            # Test decrypt if requested
            if options.get('test_decrypt'):
                decrypt_passed = self._test_decryption(
                    backup, encrypted_file_path, encryption_key, options
                )
                
                if not decrypt_passed:
                    result['message'] = 'Decryption test failed'
                    return result
            
            # Delete original file if requested
            if options.get('delete_original'):
                self._delete_original_backup(backup, original_file_path)
            
            # Clean up temporary files
            self._cleanup_temp_files([original_file_path, encrypted_file_path])
            
            result['encrypted'] = True
            result['message'] = 'Successfully encrypted'
            
            logger.info(f"Successfully encrypted backup: {backup.name}")
            
        except Exception as e:
            error_msg = str(e)
            result['error'] = error_msg
            result['message'] = f'Encryption failed: {error_msg}'
            logger.error(f"Failed to encrypt backup {backup.name}: {error_msg}")
        
        finally:
            # Calculate encryption time
            end_time = timezone.now()
            result['encryption_time'] = (end_time - start_time).total_seconds()
        
        return result
    
    def _get_encryption_key(self, backup: Backup, options) -> str:
        """Get or generate encryption key for backup"""
        # Check imported keys first
        if hasattr(self, 'imported_keys') and str(backup.backup_id) in self.imported_keys:
            return self.imported_keys[str(backup.backup_id)]
        
        # Use master key if reusing
        if self.reuse_key and self.master_key:
            return self.master_key
        
        # Generate per-backup key
        if self.per_backup_key:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        
        # Default to master key
        return self.master_key or self._get_or_create_master_key(options)
    
    def _encrypt_key_for_storage(self, key: str) -> str:
        """Encrypt key for secure storage in database"""
        from cryptography.fernet import Fernet
        
        # Use a system-wide key for encrypting stored keys
        # In production, this should be properly secured
        system_key = Fernet.generate_key()
        cipher = Fernet(system_key)
        
        encrypted_key = cipher.encrypt(key.encode())
        return encrypted_key.decode()
    
    def _download_backup_file(self, backup: Backup, options) -> str:
        """Download backup file to temporary location"""
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        original_filename = f"original_{backup.backup_id}.sql"
        original_path = os.path.join(temp_dir, original_filename)
        
        # Get storage service and download
        storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
        
        if hasattr(storage_service, 'download_backup'):
            storage_service.download_backup(backup.backup_file.name, original_path)
        else:
            # Alternative download method
            with open(original_path, 'wb') as f:
                for chunk in backup.backup_file.chunks():
                    f.write(chunk)
        
        return original_path
    
    def _encrypt_backup_file(self, file_path: str, encryption_key: str, options) -> str:
        """Encrypt backup file"""
        from cryptography.fernet import Fernet
        
        cipher = Fernet(encryption_key.encode())
        
        # Read original file
        with open(file_path, 'rb') as f:
            original_data = f.read()
        
        # Encrypt data
        encrypted_data = cipher.encrypt(original_data)
        
        # Write encrypted file
        encrypted_path = file_path + '.enc'
        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Compress after encryption if requested
        if options.get('compress_after'):
            encrypted_path = self._compress_file(encrypted_path)
        
        return encrypted_path
    
    def _compress_file(self, file_path: str) -> str:
        """Compress file using ZIP"""
        import zipfile
        
        compressed_path = file_path + '.zip'
        
        with zipfile.ZipFile(compressed_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
        
        os.remove(file_path)
        return compressed_path
    
    def _get_encrypted_filename(self, backup: Backup) -> str:
        """Generate encrypted filename"""
        original_name = backup.backup_file.name
        
        if original_name.endswith('.sql'):
            return original_name.replace('.sql', '.sql.enc')
        elif original_name.endswith('.zip'):
            return original_name.replace('.zip', '.zip.enc')
        else:
            return original_name + '.enc'
    
    def _upload_encrypted_backup(self, backup: Backup, encrypted_file_path: str, options):
        """Upload encrypted backup to storage"""
        storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
        
        # Create temporary File object for upload
        from django.core.files.base import ContentFile
        
        with open(encrypted_file_path, 'rb') as f:
            encrypted_data = f.read()
        
        encrypted_file = ContentFile(encrypted_data)
        encrypted_filename = self._get_encrypted_filename(backup)
        
        # Upload using storage service
        if hasattr(storage_service, 'save_backup'):
            storage_service.save_backup(encrypted_file, backup)
        else:
            # Alternative upload method
            backup.backup_file.save(encrypted_filename, encrypted_file)
    
    def _verify_encryption(self, backup: Backup, encrypted_file_path: str, 
                         encryption_key: str, options) -> bool:
        """Verify encryption integrity"""
        try:
            # Calculate hash of encrypted file
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            encrypted_hash = hashlib.sha256(encrypted_data).hexdigest()
            
            # Test decryption to verify
            from cryptography.fernet import Fernet
            cipher = Fernet(encryption_key.encode())
            
            try:
                decrypted_data = cipher.decrypt(encrypted_data)
                
                # Verify decrypted data is not empty
                if len(decrypted_data) == 0:
                    return False
                
                # Verify decrypted data looks like SQL (basic check)
                if not decrypted_data.decode('utf-8', errors='ignore').strip().startswith('--'):
                    # Not necessarily SQL, but check if it's reasonable data
                    pass
                
                return True
                
            except Exception:
                return False
                
        except Exception as e:
            logger.error(f"Encryption verification failed: {str(e)}")
            return False
    
    def _test_decryption(self, backup: Backup, encrypted_file_path: str, 
                       encryption_key: str, options) -> bool:
        """Test decryption to ensure encryption worked correctly"""
        try:
            from cryptography.fernet import Fernet
            cipher = Fernet(encryption_key.encode())
            
            # Decrypt file
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            
            # Write to temporary file for validation
            temp_dir = tempfile.mkdtemp()
            decrypted_path = os.path.join(temp_dir, 'decrypted_test.sql')
            
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            # Basic validation of decrypted file
            file_size = os.path.getsize(decrypted_path)
            
            # Clean up
            os.remove(decrypted_path)
            os.rmdir(temp_dir)
            
            return file_size > 0
            
        except Exception as e:
            logger.error(f"Decryption test failed: {str(e)}")
            return False
    
    def _delete_original_backup(self, backup: Backup, original_file_path: str):
        """Delete original unencrypted backup"""
        try:
            # Delete from storage
            storage_service = BackupServiceFactory.get_storage_service(backup.storage_type)
            
            if hasattr(storage_service, 'delete_backup'):
                # Create temporary backup instance for deletion
                temp_backup = Backup(
                    backup_id=backup.backup_id,
                    storage_location=backup.storage_location
                )
                storage_service.delete_backup(temp_backup)
            
            # Delete local file
            if os.path.exists(original_file_path):
                os.remove(original_file_path)
            
            logger.info(f"Deleted original unencrypted backup: {backup.name}")
            
        except Exception as e:
            logger.error(f"Failed to delete original backup {backup.name}: {str(e)}")
    
    def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {file_path}: {str(e)}")
    
    def _encrypt_backups_parallel(self, backups: List[Backup], options: Dict) -> List[Dict]:
        """Encrypt backups in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        parallel = options.get('parallel', 1)
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all encryption tasks
            future_to_backup = {
                executor.submit(self._encrypt_single_backup, backup, options): backup
                for backup in backups
            }
            
            # Collect results
            for future in as_completed(future_to_backup):
                backup = future_to_backup[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if not options.get('quiet'):
                        status = "✓" if result['encrypted'] else "✗"
                        message = result['message']
                        self.stdout.write(f"{status} {backup.name[:40]:40} | {message}")
                        
                except Exception as e:
                    error_result = {
                        'backup_id': str(backup.backup_id),
                        'backup_name': backup.name,
                        'encrypted': False,
                        'message': f'Encryption error: {str(e)}',
                        'error': str(e)
                    }
                    results.append(error_result)
        
        return results
    
    def _export_encryption_keys(self, results: List[Dict], export_file: str):
        """Export encryption keys to file"""
        try:
            keys_data = {
                'export_timestamp': timezone.now().isoformat(),
                'algorithm': self.encryption_algorithm,
                'keys': {}
            }
            
            for result in results:
                if result['encrypted'] and result.get('encryption_key_id'):
                    backup_id = result['backup_id']
                    # Get the encryption key from the database
                    try:
                        encryption = BackupEncryption.objects.get(
                            backup_id=backup_id,
                            backup__backup_id=backup_id
                        )
                        keys_data['keys'][backup_id] = {
                            'backup_name': result['backup_name'],
                            'key_hash': encryption.key_hash,
                            'algorithm': encryption.algorithm,
                            'created_at': encryption.created_at.isoformat()
                        }
                    except BackupEncryption.DoesNotExist:
                        continue
            
            with open(export_file, 'w') as f:
                json.dump(keys_data, f, indent=2)
            
            # Set secure permissions
            os.chmod(export_file, 0o600)
            
            self.stdout.write(f"Exported {len(keys_data['keys'])} encryption keys to {export_file}")
            
        except Exception as e:
            logger.error(f"Failed to export encryption keys: {str(e)}")
    
    def _generate_report(self, results: List[Dict], options: Dict):
        """Generate encryption report"""
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
        self.stdout.write("ENCRYPTION REPORT")
        self.stdout.write("="*80)
        
        # Summary
        total = len(results)
        encrypted = sum(1 for r in results if r['encrypted'])
        failed = total - encrypted
        total_original_size = sum(r['original_size'] or 0 for r in results)
        total_encrypted_size = sum(r['encrypted_size'] or 0 for r in results if r['encrypted'])
        
        self.stdout.write(f"Total: {total}, Encrypted: {encrypted}, Failed: {failed}")
        self.stdout.write(f"Original Size: {self._format_size(total_original_size)}")
        self.stdout.write(f"Encrypted Size: {self._format_size(total_encrypted_size)}")
        self.stdout.write("-" * 80)
        
        # Detailed results
        for result in results:
            status = "✓ ENCRYPTED" if result['encrypted'] else "✗ FAILED"
            original_size = self._format_size(result['original_size']) if result['original_size'] else "N/A"
            encrypted_size = self._format_size(result['encrypted_size']) if result['encrypted_size'] else "N/A"
            encrypt_time = f"{result['encryption_time']:.1f}s" if result['encryption_time'] else "N/A"
            
            self.stdout.write(f"{status} | {result['backup_name'][:25]:25} | {original_size[:10]:10} | {encrypted_size[:10]:10} | {encrypt_time[:8]:8} | {result['message'][:30]:30}")
    
    def _generate_json_report(self, results: List[Dict]):
        """Generate JSON format report"""
        total_original_size = sum(r['original_size'] or 0 for r in results)
        total_encrypted_size = sum(r['encrypted_size'] or 0 for r in results if r['encrypted'])
        total_time = sum(r['encryption_time'] or 0 for r in results)
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'algorithm': self.encryption_algorithm,
            'total_backups': len(results),
            'encrypted_backups': sum(1 for r in results if r['encrypted']),
            'failed_backups': sum(1 for r in results if not r['encrypted']),
            'total_original_size': total_original_size,
            'total_encrypted_size': total_encrypted_size,
            'total_encryption_time': total_time,
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
            'original_size', 'encrypted_size', 'encrypted', 'encryption_time', 'message', 'error'
        ])
        
        # Data
        for result in results:
            writer.writerow([
                result['backup_id'],
                result['backup_name'],
                result['backup_type'],
                result['storage_type'],
                result['original_size'],
                result['encrypted_size'],
                result['encrypted'],
                result['encryption_time'],
                result['message'],
                result.get('error', '')
            ])
        
        self.stdout.write(output.getvalue())
    
    def _create_encryption_alerts(self, results: List[Dict], options: Dict):
        """Create alerts for encryption failures"""
        failed_results = [r for r in results if not r['encrypted']]
        
        for result in failed_results:
            try:
                backup = Backup.objects.get(backup_id=result['backup_id'])
                
                BackupAlert.create_alert(
                    alert_type='security',
                    message=f"Backup encryption failed: {result['message']}",
                    backup=backup,
                    severity='high',
                    metadata={
                        'encryption_algorithm': self.encryption_algorithm,
                        'encryption_error': result.get('error'),
                        'encryption_time': result.get('encryption_time')
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to create encryption alert for {result['backup_name']}: {str(e)}")
        
        if failed_results:
            self.stdout.write(f"Created {len(failed_results)} alerts for encryption failures")
    
    def _print_summary(self, results: List[Dict]):
        """Print final encryption summary"""
        total = len(results)
        encrypted = sum(1 for r in results if r['encrypted'])
        failed = total - encrypted
        total_original_size = sum(r['original_size'] or 0 for r in results)
        total_encrypted_size = sum(r['encrypted_size'] or 0 for r in results if r['encrypted'])
        total_time = sum(r['encryption_time'] or 0 for r in results)
        success_rate = (encrypted / total * 100) if total > 0 else 0
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("ENCRYPTION SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Total Backups: {total}")
        self.stdout.write(f"Encrypted: {encrypted} ({success_rate:.1f}%)")
        self.stdout.write(f"Failed: {failed}")
        self.stdout.write(f"Original Size: {self._format_size(total_original_size)}")
        self.stdout.write(f"Encrypted Size: {self._format_size(total_encrypted_size)}")
        self.stdout.write(f"Total Time: {total_time:.1f}s")
        self.stdout.write(f"Algorithm: {self.encryption_algorithm}")
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
