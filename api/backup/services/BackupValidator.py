import os
import json
import hashlib
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet, InvalidToken
import zipfile

class BackupValidator:
    @staticmethod
    def validate_backup_file(file_path):
        """ব্যাকআপ ফাইল ভ্যালিডেট করুন"""
        if not os.path.exists(file_path):
            raise ValidationError("ব্যাকআপ ফাইল পাওয়া যায়নি")
        
        if os.path.getsize(file_path) == 0:
            raise ValidationError("ব্যাকআপ ফাইল খালি")
        
        return True
    
    @staticmethod
    def validate_file_integrity(file_path, expected_hash=None):
        """ফাইলের ইন্টিগ্রিটি চেক করুন"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        actual_hash = sha256_hash.hexdigest()
        
        if expected_hash and actual_hash != expected_hash:
            raise ValidationError(
                f"ফাইল ইন্টিগ্রিটি ভঙ্গ হয়েছে। "
                f"প্রত্যাশিত: {expected_hash[:16]}..., "
                f"প্রাপ্ত: {actual_hash[:16]}..."
            )
        
        return actual_hash
    
    @staticmethod
    def validate_encrypted_file(file_path, encryption_key=None):
        """এনক্রিপ্টেড ফাইল ভ্যালিডেট করুন"""
        if not encryption_key:
            raise ValidationError("এনক্রিপশন কী প্রদান করা হয়নি")
        
        try:
            cipher = Fernet(encryption_key.encode())
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            # শুধু ডিক্রিপ্ট করার চেষ্টা করুন (ভাল ভ্যালিডেশন)
            cipher.decrypt(encrypted_data)
            return True
            
        except InvalidToken:
            raise ValidationError("এনক্রিপশন কী ভুল")
        except Exception as e:
            raise ValidationError(f"এনক্রিপশন ভ্যালিডেশন ব্যর্থ: {str(e)}")
    
    @staticmethod
    def validate_compressed_file(file_path):
        """কম্প্রেসড ফাইল ভ্যালিডেট করুন"""
        if not file_path.endswith('.zip'):
            return False
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                # শুধু zip ফাইল সঠিক কিনা চেক করুন
                return zipf.testzip() is None
        except (zipfile.BadZipFile, Exception):
            return False
    
    @staticmethod
    def validate_metadata(metadata_path):
        """মেটাডেটা ফাইল ভ্যালিডেট করুন"""
        if not os.path.exists(metadata_path):
            raise ValidationError("মেটাডেটা ফাইল পাওয়া যায়নি")
        
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # প্রয়োজনীয় ফিল্ডগুলো চেক করুন
            required_fields = ['backup_id', 'database', 'created_at', 'file_size', 'file_hash']
            for field in required_fields:
                if field not in metadata:
                    raise ValidationError(f"মেটাডেটায় {field} ফিল্ড নেই")
            
            # টাইমস্ট্যাম্প ভ্যালিডেশন
            try:
                created_at = datetime.fromisoformat(metadata['created_at'])
                if created_at > datetime.now():
                    raise ValidationError("মেটাডেটা টাইমস্ট্যাম্প ভবিষ্যতের")
            except ValueError:
                raise ValidationError("অবৈধ টাইমস্ট্যাম্প ফরম্যাট")
            
            return metadata
            
        except json.JSONDecodeError:
            raise ValidationError("মেটাডেটা JSON ফরম্যাটে নয়")
    
    @staticmethod
    def validate_backup_age(backup_instance, max_age_days=30):
        """ব্যাকআপের বয়স ভ্যালিডেট করুন"""
        backup_age = datetime.now().date() - backup_instance.created_at.date()
        
        if backup_age.days > max_age_days:
            raise ValidationError(
                f"ব্যাকআপ খুব পুরানো। বয়স: {backup_age.days} দিন, "
                f"সর্বোচ্চ অনুমোদিত: {max_age_days} দিন"
            )
        
        return True
    
    @staticmethod
    def validate_storage_space(file_size, storage_path, min_free_space_gb=1):
        """স্টোরেজ স্পেস চেক করুন"""
        if not os.path.exists(storage_path):
            return True
        
        stat = os.statvfs(storage_path)
        free_space_bytes = stat.f_frsize * stat.f_bavail
        free_space_gb = free_space_bytes / (1024 ** 3)
        
        required_space_gb = (file_size / (1024 ** 3)) + min_free_space_gb
        
        if free_space_gb < required_space_gb:
            raise ValidationError(
                f"পর্যাপ্ত স্টোরেজ স্পেস নেই। "
                f"প্রয়োজন: {required_space_gb:.2f} GB, "
                f"উপলব্ধ: {free_space_gb:.2f} GB"
            )
        
        return True
    
    @staticmethod
    def validate_backup_consistency(backup_instance):
        """ব্যাকআপ কনসিসটেন্সি চেক করুন"""
        errors = []
        
        # ফাইল পাওয়া যায় কিনা চেক করুন
        if hasattr(backup_instance, 'backup_file') and backup_instance.backup_file:
            if not os.path.exists(backup_instance.backup_file.path):
                errors.append("ব্যাকআপ ফাইল সিস্টেমে নেই")
        
        # hash মিলছে কিনা চেক করুন
        if hasattr(backup_instance, 'file_hash') and backup_instance.file_hash:
            try:
                BackupValidator.validate_file_integrity(
                    backup_instance.backup_file.path,
                    backup_instance.file_hash
                )
            except ValidationError as e:
                errors.append(str(e))
        
        # এনক্রিপশন কী ভ্যালিডেশন
        if (hasattr(backup_instance, 'encryption_enabled') and 
            backup_instance.encryption_enabled and 
            backup_instance.encryption_key):
            try:
                BackupValidator.validate_encrypted_file(
                    backup_instance.backup_file.path,
                    backup_instance.encryption_key
                )
            except ValidationError as e:
                errors.append(str(e))
        
        # মেটাডেটা ভ্যালিডেশন
        metadata_path = backup_instance.backup_file.path + '.meta'
        if os.path.exists(metadata_path):
            try:
                BackupValidator.validate_metadata(metadata_path)
            except ValidationError as e:
                errors.append(f"মেটাডেটা ত্রুটি: {str(e)}")
        
        if errors:
            raise ValidationError("; ".join(errors))
        
        return True