import os
import shutil
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .BaseBackupService import BaseBackupService

class LocalBackupService(BaseBackupService):
    def __init__(self, config=None):
        super().__init__(config)
        
        self.backup_dir = self.config.get(
            'backup_dir',
            os.path.join(settings.BASE_DIR, 'backups', 'database')
        )
        
        os.makedirs(self.backup_dir, exist_ok=True)
        self.storage = FileSystemStorage(location=self.backup_dir)
    
    def save_backup(self, backup_file, backup_instance):
        try:
            # ফাইলনেম জেনারেট
            filename = self._generate_filename(backup_instance)
            file_path = os.path.join(self.backup_dir, filename)
            
            # ফাইল সেভ
            with open(file_path, 'wb') as f:
                for chunk in backup_file.chunks():
                    f.write(chunk)
            
            # ভ্যালিডেশন
            self._validate_backup_file(file_path, backup_instance.file_hash)
            
            # মেটাডেটা তৈরি
            metadata, file_size, file_hash = self._create_metadata(
                backup_instance, 
                file_path, 
                backup_instance.encryption_key
            )
            
            # মডেল আপডেট
            backup_instance.file_size = file_size
            backup_instance.file_hash = file_hash
            backup_instance.metadata = metadata
            backup_instance.storage_location = file_path
            backup_instance.save()
            
            # পুরানো ব্যাকআপ ক্লিনআপ
            retention_days = self.config.get('retention_days', 30)
            self._cleanup_old_backups(self.backup_dir, retention_days)
            
            return backup_instance
            
        except Exception as e:
            backup_instance.status = 'failed'
            backup_instance.error_message = str(e)
            backup_instance.save()
            raise
    
    def delete_backup(self, backup_instance):
        try:
            if backup_instance.storage_location and os.path.exists(backup_instance.storage_location):
                os.remove(backup_instance.storage_location)
                
                # মেটাডেটা ফাইল ডিলিট
                meta_path = backup_instance.storage_location + '.meta'
                if os.path.exists(meta_path):
                    os.remove(meta_path)
            
            return True
            
        except Exception as e:
            raise Exception(f"লোকাল ব্যাকআপ ডিলিট ব্যর্থ: {str(e)}")
    
    def list_backups(self):
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if any(filename.endswith(ext) for ext in ['.sql', '.zip', '.enc']):
                file_path = os.path.join(self.backup_dir, filename)
                
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    created_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    
                    # মেটাডেটা পড়ুন
                    metadata = {}
                    meta_path = file_path + '.meta'
                    if os.path.exists(meta_path):
                        try:
                            import json
                            with open(meta_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        except:
                            pass
                    
                    backups.append({
                        'filename': filename,
                        'path': file_path,
                        'size': file_size,
                        'size_human': self._human_readable_size(file_size),
                        'created_at': created_time,
                        'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)),
                        'metadata': metadata
                    })
        
        # তারিখ অনুযায়ী সর্ট করুন
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
    
    def get_backup_info(self, filename):
        file_path = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        return {
            'filename': filename,
            'path': file_path,
            'size': os.path.getsize(file_path),
            'size_human': self._human_readable_size(os.path.getsize(file_path)),
            'created_at': datetime.fromtimestamp(os.path.getctime(file_path)),
            'modified_at': datetime.fromtimestamp(os.path.getmtime(file_path)),
            'exists': True
        }
    
    def download_backup(self, filename, download_path):
        source_path = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(source_path):
            raise Exception(f"ফাইল পাওয়া যায়নি: {filename}")
        
        try:
            shutil.copy2(source_path, download_path)
            return download_path
            
        except Exception as e:
            raise Exception(f"ডাউনলোড ব্যর্থ: {str(e)}")
    
    def restore_backup(self, filename, target_path=None):
        source_path = os.path.join(self.backup_dir, filename)
        
        if not os.path.exists(source_path):
            raise Exception(f"ফাইল পাওয়া যায়নি: {filename}")
        
        if target_path is None:
            target_path = os.path.join(settings.BASE_DIR, 'restored', filename)
        
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        try:
            shutil.copy2(source_path, target_path)
            return target_path
            
        except Exception as e:
            raise Exception(f"রিস্টোর ব্যর্থ: {str(e)}")
    
    def cleanup(self, retention_days=None):
        if retention_days is None:
            retention_days = self.config.get('retention_days', 30)
        
        try:
            self._cleanup_old_backups(self.backup_dir, retention_days)
            return True
            
        except Exception as e:
            raise Exception(f"ক্লিনআপ ব্যর্থ: {str(e)}")
    
    def _human_readable_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"