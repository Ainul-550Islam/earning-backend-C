import os
import json
import hashlib
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from cryptography.fernet import Fernet
from .BackupValidator import BackupValidator

class BaseBackupService(ABC):
    def __init__(self, config=None):
        self.config = config or {}
        self.encryption_enabled = self.config.get('encryption', False)
        self.compression_enabled = self.config.get('compression', True)
        self.encryption_key = None
        self.validator = BackupValidator()
        
        if self.encryption_enabled:
            self.encryption_key = Fernet.generate_key()
            self.cipher = Fernet(self.encryption_key)
    
    @abstractmethod
    def save_backup(self, backup_file, backup_instance):
        pass
    
    @abstractmethod
    def delete_backup(self, backup_instance):
        pass
    
    @abstractmethod
    def list_backups(self):
        pass
    
    def _generate_filename(self, backup_instance=None):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = settings.DATABASES['default']['NAME'].split('/')[-1].replace('.', '_')
        extension = '.sql'
        
        if self.compression_enabled:
            extension = '.zip'
        if self.encryption_enabled:
            extension = '.enc'
        
        if backup_instance and hasattr(backup_instance, 'id'):
            return f"backup_{db_name}_{backup_instance.id}_{timestamp}{extension}"
        
        return f"backup_{db_name}_{timestamp}{extension}"
    
    def _compress_file(self, input_path):
        if not self.compression_enabled or input_path.endswith('.zip'):
            return input_path
        
        output_path = input_path + '.zip'
        
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(input_path, os.path.basename(input_path))
            
            os.remove(input_path)
            return output_path
            
        except Exception as e:
            raise Exception(f"কম্প্রেশন ব্যর্থ: {str(e)}")
    
    def _encrypt_file(self, input_path):
        if not self.encryption_enabled or input_path.endswith('.enc'):
            return input_path, None
        
        try:
            with open(input_path, 'rb') as f:
                original_data = f.read()
            
            encrypted_data = self.cipher.encrypt(original_data)
            output_path = input_path + '.enc'
            
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)
            
            os.remove(input_path)
            return output_path, self.encryption_key.decode()
            
        except Exception as e:
            raise Exception(f"এনক্রিপশন ব্যর্থ: {str(e)}")
    
    def _decrypt_file(self, input_path, encryption_key):
        if not input_path.endswith('.enc'):
            return input_path
        
        try:
            cipher = Fernet(encryption_key.encode())
            
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            output_path = input_path.replace('.enc', '')
            
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"ডিক্রিপশন ব্যর্থ: {str(e)}")
    
    def _calculate_file_hash(self, file_path):
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _create_metadata(self, backup_instance, file_path, encryption_key=None):
        file_size = os.path.getsize(file_path)
        file_hash = self._calculate_file_hash(file_path)
        
        metadata = {
            'backup_id': str(backup_instance.id),
            'database': settings.DATABASES['default']['NAME'],
            'created_at': datetime.now().isoformat(),
            'file_size': file_size,
            'file_hash': file_hash,
            'compression': self.compression_enabled,
            'encryption': self.encryption_enabled,
            'encryption_key': encryption_key,
            'config': self.config,
            'service': self.__class__.__name__
        }
        
        metadata_path = file_path + '.meta'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return metadata, file_size, file_hash
    
    def _process_backup_file(self, input_path):
        current_path = input_path
        encryption_key = None
        
        try:
            # প্রথমে কম্প্রেশন
            if self.compression_enabled and not current_path.endswith('.zip'):
                current_path = self._compress_file(current_path)
            
            # তারপর এনক্রিপশন
            if self.encryption_enabled and not current_path.endswith('.enc'):
                current_path, encryption_key = self._encrypt_file(current_path)
            
            return current_path, encryption_key
            
        except Exception as e:
            # ক্লিনআপ
            if os.path.exists(current_path) and current_path != input_path:
                os.remove(current_path)
            raise
    
    def _validate_backup_file(self, file_path, expected_hash=None):
        try:
            self.validator.validate_backup_file(file_path)
            
            if expected_hash:
                self.validator.validate_file_integrity(file_path, expected_hash)
            
            if self.encryption_enabled:
                metadata_path = file_path + '.meta'
                if os.path.exists(metadata_path):
                    metadata = self.validator.validate_metadata(metadata_path)
                    if metadata.get('encryption'):
                        if not self.encryption_key and metadata.get('encryption_key'):
                            self.encryption_key = metadata['encryption_key'].encode()
            
            return True
            
        except Exception as e:
            raise Exception(f"ব্যাকআপ ভ্যালিডেশন ব্যর্থ: {str(e)}")
    
    def _cleanup_old_backups(self, backup_dir, retention_days):
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            for filename in os.listdir(backup_dir):
                if any(filename.endswith(ext) for ext in ['.sql', '.zip', '.enc']):
                    file_path = os.path.join(backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    if file_time < cutoff_time:
                        os.remove(file_path)
                        
                        # মেটাডেটা ফাইলও ডিলিট করুন
                        meta_path = file_path + '.meta'
                        if os.path.exists(meta_path):
                            os.remove(meta_path)
            
        except Exception as e:
            raise Exception(f"পুরানো ব্যাকআপ ডিলিট ব্যর্থ: {str(e)}")