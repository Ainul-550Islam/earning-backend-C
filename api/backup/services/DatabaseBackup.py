import os
import subprocess
import tempfile
from datetime import datetime
from django.conf import settings
from django.core.management import call_command
from .BaseBackupService import BaseBackupService

class DatabaseBackupService(BaseBackupService):
    def __init__(self, config=None):
        super().__init__(config)
        self.db_config = settings.DATABASES['default']
        self.db_engine = self.db_config['ENGINE']
    
    def create_backup(self, backup_instance):
        try:
            # টেম্পোরারি ফাইল তৈরি
            with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as tmp:
                temp_path = tmp.name
            
            # ডাটাবেজ ব্যাকআপ
            backup_path = self._dump_database(temp_path)
            
            # ফাইল প্রসেসিং
            processed_path, encryption_key = self._process_backup_file(backup_path)
            
            # মেটাডেটা তৈরি
            metadata, file_size, file_hash = self._create_metadata(
                backup_instance, 
                processed_path, 
                encryption_key
            )
            
            # ব্যাকআপ ফাইল মডেলে সেভ
            filename = os.path.basename(processed_path)
            with open(processed_path, 'rb') as f:
                backup_instance.backup_file.save(filename, ContentFile(f.read()))
            
            # টেম্প ফাইল ডিলিট
            os.remove(processed_path)
            
            # মডেল আপডেট
            backup_instance.file_size = file_size
            backup_instance.file_hash = file_hash
            backup_instance.encryption_key = encryption_key
            backup_instance.metadata = metadata
            backup_instance.status = 'completed'
            backup_instance.save()
            
            return backup_instance
            
        except Exception as e:
            backup_instance.status = 'failed'
            backup_instance.error_message = str(e)
            backup_instance.save()
            raise
    
    def _dump_database(self, output_path):
        try:
            if 'postgresql' in self.db_engine:
                return self._dump_postgresql(output_path)
            elif 'mysql' in self.db_engine:
                return self._dump_mysql(output_path)
            elif 'sqlite' in self.db_engine:
                return self._dump_sqlite(output_path)
            else:
                return self._dump_using_django(output_path)
                
        except Exception as e:
            raise Exception(f"ডাটাবেজ ব্যাকআপ ব্যর্থ: {str(e)}")
    
    def _dump_postgresql(self, output_path):
        db = self.db_config
        env = os.environ.copy()
        
        if 'PASSWORD' in db:
            env['PGPASSWORD'] = db['PASSWORD']
        
        cmd = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', 'postgres'),
            '-d', db['NAME'],
            '-f', output_path,
            '-F', 'c'  # custom format
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"PostgreSQL ব্যাকআপ ব্যর্থ: {result.stderr}")
        
        return output_path
    
    def _dump_mysql(self, output_path):
        db = self.db_config
        
        cmd = [
            'mysqldump',
            '-h', db.get('HOST', 'localhost'),
            '-P', str(db.get('PORT', '3306')),
            '-u', db.get('USER', 'root'),
            f'--password={db.get("PASSWORD", "")}',
            db['NAME'],
            '--result-file', output_path,
            '--single-transaction',
            '--routines',
            '--triggers'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"MySQL ব্যাকআপ ব্যর্থ: {result.stderr}")
        
        return output_path
    
    def _dump_sqlite(self, output_path):
        db_path = self.db_config['NAME']
        
        if not os.path.exists(db_path):
            raise Exception(f"SQLite ডাটাবেজ পাওয়া যায়নি: {db_path}")
        
        import shutil
        shutil.copy2(db_path, output_path)
        
        return output_path
    
    def _dump_using_django(self, output_path):
        with open(output_path, 'w', encoding='utf-8') as f:
            call_command(
                'dumpdata',
                format='json',
                indent=2,
                stdout=f,
                exclude=['contenttypes', 'auth.permission', 'sessions']
            )
        
        return output_path
    
    def restore_backup(self, backup_instance, target_database=None):
        try:
            backup_file = backup_instance.backup_file.path
            
            # ফাইল ডিক্রিপ্ট ও ডিকম্প্রেস
            if backup_file.endswith('.enc') and backup_instance.encryption_key:
                backup_file = self._decrypt_file(backup_file, backup_instance.encryption_key)
            
            if backup_file.endswith('.zip'):
                backup_file = self._extract_zip(backup_file)
            
            # ডাটাবেজ রিস্টোর
            if 'postgresql' in self.db_engine:
                self._restore_postgresql(backup_file)
            elif 'mysql' in self.db_engine:
                self._restore_mysql(backup_file)
            elif 'sqlite' in self.db_engine:
                self._restore_sqlite(backup_file)
            else:
                self._restore_using_django(backup_file)
            
            return True
            
        except Exception as e:
            raise Exception(f"ডাটাবেজ রিস্টোর ব্যর্থ: {str(e)}")
    
    def _restore_postgresql(self, backup_file):
        db = self.db_config
        env = os.environ.copy()
        
        if 'PASSWORD' in db:
            env['PGPASSWORD'] = db['PASSWORD']
        
        # আগে ডাটাবেজ ড্রপ/ক্রিয়েট
        drop_cmd = [
            'psql',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', 'postgres'),
            '-c', f"DROP DATABASE IF EXISTS {db['NAME']}; CREATE DATABASE {db['NAME']};"
        ]
        
        subprocess.run(drop_cmd, env=env, capture_output=True, text=True)
        
        # রিস্টোর
        restore_cmd = [
            'pg_restore',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', 'postgres'),
            '-d', db['NAME'],
            backup_file
        ]
        
        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"PostgreSQL রিস্টোর ব্যর্থ: {result.stderr}")
    
    def _extract_zip(self, zip_path):
        import zipfile
        extract_dir = os.path.dirname(zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        extracted_files = [f for f in os.listdir(extract_dir) if f.endswith('.sql')]
        if extracted_files:
            return os.path.join(extract_dir, extracted_files[0])
        
        raise Exception("ZIP ফাইলে .sql ফাইল পাওয়া যায়নি")
    
    def save_backup(self, backup_file, backup_instance):
        pass
    
    def delete_backup(self, backup_instance):
        pass
    
    def list_backups(self):
        return []