import os
import boto3
import tempfile
from botocore.exceptions import ClientError
from django.conf import settings
from .BaseBackupService import BaseBackupService

class S3BackupService(BaseBackupService):
    def __init__(self, config=None):
        super().__init__(config)
        
        self.aws_access_key_id = self.config.get(
            'aws_access_key_id',
            getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        )
        
        self.aws_secret_access_key = self.config.get(
            'aws_secret_access_key',
            getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        )
        
        self.aws_region = self.config.get(
            'aws_region',
            getattr(settings, 'AWS_REGION', 'us-east-1')
        )
        
        self.bucket_name = self.config.get(
            'bucket_name',
            getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'backup-bucket')
        )
        
        self.s3_folder = self.config.get('s3_folder', 'database-backups')
        self.storage_class = self.config.get('storage_class', 'STANDARD')
        
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise Exception("AWS ক্রেডেনশিয়ালস কনফিগার করা হয়নি")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
    
    def save_backup(self, backup_file, backup_instance):
        try:
            # টেম্পোরারি ফাইলে সেভ
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                for chunk in backup_file.chunks():
                    tmp.write(chunk)
                temp_path = tmp.name
            
            # S3 key তৈরি
            filename = self._generate_filename(backup_instance)
            s3_key = f"{self.s3_folder}/{filename}"
            
            # S3 তে আপলোড
            self.s3_client.upload_file(
                temp_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'StorageClass': self.storage_class,
                    'Metadata': {
                        'backup_id': str(backup_instance.id),
                        'database': settings.DATABASES['default']['NAME'],
                        'encryption': str(self.encryption_enabled),
                        'compression': str(self.compression_enabled),
                        'service': 'S3BackupService'
                    }
                }
            )
            
            # মেটাডেটা আপলোড
            metadata, file_size, file_hash = self._create_metadata(
                backup_instance,
                temp_path,
                backup_instance.encryption_key
            )
            
            # মেটাডেটা S3 তে আপলোড
            meta_key = s3_key + '.meta'
            meta_content = json.dumps(metadata, indent=2).encode('utf-8')
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=meta_key,
                Body=meta_content,
                ContentType='application/json',
                StorageClass=self.storage_class
            )
            
            # টেম্প ফাইল ডিলিট
            os.remove(temp_path)
            
            # মডেল আপডেট
            backup_instance.file_size = file_size
            backup_instance.file_hash = file_hash
            backup_instance.metadata = metadata
            backup_instance.storage_location = f"s3://{self.bucket_name}/{s3_key}"
            backup_instance.save()
            
            # পুরানো ব্যাকআপ ক্লিনআপ
            retention_days = self.config.get('retention_days', 30)
            self._cleanup_old_backups_s3(retention_days)
            
            return backup_instance
            
        except ClientError as e:
            error_msg = f"S3 আপলোড ব্যর্থ: {str(e)}"
            backup_instance.status = 'failed'
            backup_instance.error_message = error_msg
            backup_instance.save()
            raise Exception(error_msg)
        except Exception as e:
            backup_instance.status = 'failed'
            backup_instance.error_message = str(e)
            backup_instance.save()
            raise
    
    def delete_backup(self, backup_instance):
        try:
            if backup_instance.storage_location:
                # S3 key এক্সট্র্যাক্ট
                s3_key = backup_instance.storage_location.replace(
                    f"s3://{self.bucket_name}/", ""
                )
                
                # ফাইল ডিলিট
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
                
                # মেটাডেটা ফাইল ডিলিট
                meta_key = s3_key + '.meta'
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=meta_key
                    )
                except:
                    pass
            
            return True
            
        except ClientError as e:
            raise Exception(f"S3 ডিলিট ব্যর্থ: {str(e)}")
    
    def list_backups(self):
        try:
            backups = []
            continuation_token = None
            
            while True:
                if continuation_token:
                    response = self.s3_client.list_objects_v2(
                        Bucket=self.bucket_name,
                        Prefix=self.s3_folder,
                        ContinuationToken=continuation_token
                    )
                else:
                    response = self.s3_client.list_objects_v2(
                        Bucket=self.bucket_name,
                        Prefix=self.s3_folder
                    )
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        
                        # শুধু ব্যাকআপ ফাইলগুলো (মেটাডেটা নয়)
                        if any(key.endswith(ext) for ext in ['.sql', '.zip', '.enc']):
                            # মেটাডেটা পড়ুন
                            metadata = {}
                            meta_key = key + '.meta'
                            
                            try:
                                meta_response = self.s3_client.get_object(
                                    Bucket=self.bucket_name,
                                    Key=meta_key
                                )
                                metadata = json.loads(meta_response['Body'].read().decode('utf-8'))
                            except:
                                pass
                            
                            backups.append({
                                'key': key,
                                'filename': os.path.basename(key),
                                'size': obj['Size'],
                                'size_human': self._human_readable_size(obj['Size']),
                                'last_modified': obj['LastModified'],
                                'storage_class': obj.get('StorageClass', 'STANDARD'),
                                'metadata': metadata,
                                'url': f"s3://{self.bucket_name}/{key}"
                            })
                
                if not response.get('IsTruncated'):
                    break
                
                continuation_token = response.get('NextContinuationToken')
            
            # সাজান
            backups.sort(key=lambda x: x['last_modified'], reverse=True)
            
            return backups
            
        except ClientError as e:
            raise Exception(f"S3 লিস্ট ব্যর্থ: {str(e)}")
    
    def download_backup(self, s3_key, local_path):
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.s3_client.download_file(
                self.bucket_name,
                s3_key,
                local_path
            )
            
            return local_path
            
        except ClientError as e:
            raise Exception(f"S3 ডাউনলোড ব্যর্থ: {str(e)}")
    
    def get_presigned_url(self, s3_key, expiration=3600):
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            return url
            
        except ClientError as e:
            raise Exception(f"প্রিসাইনড URL তৈরি ব্যর্থ: {str(e)}")
    
    def check_bucket_exists(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def create_bucket(self):
        try:
            location = {'LocationConstraint': self.aws_region}
            self.s3_client.create_bucket(
                Bucket=self.bucket_name,
                CreateBucketConfiguration=location
            )
            return True
        except ClientError as e:
            raise Exception(f"বাকেট তৈরি ব্যর্থ: {str(e)}")
    
    def _cleanup_old_backups_s3(self, retention_days):
        try:
            from datetime import datetime, timezone
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            backups = self.list_backups()
            
            for backup in backups:
                if backup['last_modified'] < cutoff_date:
                    try:
                        # ফাইল ডিলিট
                        self.s3_client.delete_object(
                            Bucket=self.bucket_name,
                            Key=backup['key']
                        )
                        
                        # মেটাডেটা ডিলিট
                        meta_key = backup['key'] + '.meta'
                        try:
                            self.s3_client.delete_object(
                                Bucket=self.bucket_name,
                                Key=meta_key
                            )
                        except:
                            pass
                            
                    except Exception as e:
                        print(f"ফাইল ডিলিট ব্যর্থ {backup['key']}: {str(e)}")
            
        except Exception as e:
            raise Exception(f"S3 ক্লিনআপ ব্যর্থ: {str(e)}")
    
    def _human_readable_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"