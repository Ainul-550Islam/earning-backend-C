# models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
import uuid
import json
from datetime import timedelta
from django.utils import timezone
import hashlib
import logging
from django.db.models.signals import pre_delete, post_save
from django.dispatch import receiver
import socket
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


class Backup(models.Model):
    """Complete backup history with advanced tracking"""
    
    # Backup Types (Enhanced)
    BACKUP_TYPE_FULL = 'full'
    BACKUP_TYPE_PARTIAL = 'partial'
    BACKUP_TYPE_INCREMENTAL = 'incremental'
    BACKUP_TYPE_DIFFERENTIAL = 'differential'
    BACKUP_TYPE_SCHEDULED = 'scheduled'
    BACKUP_TYPE_MANUAL = 'manual'
    BACKUP_TYPE_AUTOMATED = 'automated'
    BACKUP_TYPE_DELTA = 'delta'
    
    BACKUP_TYPE_CHOICES = [
        (BACKUP_TYPE_FULL, 'Full Database Backup'),
        (BACKUP_TYPE_PARTIAL, 'Partial Backup (Selected Tables)'),
        (BACKUP_TYPE_INCREMENTAL, 'Incremental Backup'),
        (BACKUP_TYPE_DIFFERENTIAL, 'Differential Backup'),
        (BACKUP_TYPE_DELTA, 'Delta Backup (Changes Only)'),
        (BACKUP_TYPE_SCHEDULED, 'Scheduled Backup'),
        (BACKUP_TYPE_MANUAL, 'Manual Backup'),
        (BACKUP_TYPE_AUTOMATED, 'Automated Backup'),
    ]
    
    # Status (Enhanced)
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_VALIDATING = 'validating'
    STATUS_UPLOADING = 'uploading'
    STATUS_ENCRYPTING = 'encrypting'
    STATUS_COMPRESSING = 'compressing'
    STATUS_RESTORING = 'restoring'
    STATUS_VERIFYING = 'verifying'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_VALIDATING, 'Validating'),
        (STATUS_UPLOADING, 'Uploading'),
        (STATUS_ENCRYPTING, 'Encrypting'),
        (STATUS_COMPRESSING, 'Compressing'),
        (STATUS_RESTORING, 'Restoring'),
        (STATUS_VERIFYING, 'Verifying'),
    ]
    
    # Storage Types
    STORAGE_LOCAL = 'local'
    STORAGE_S3 = 's3'
    STORAGE_GCS = 'gcs'
    STORAGE_AZURE = 'azure'
    STORAGE_FTP = 'ftp'
    STORAGE_SFTP = 'sftp'
    STORAGE_DROPBOX = 'dropbox'
    STORAGE_MULTI = 'multi'
    STORAGE_REDUNDANT = 'redundant'
    
    STORAGE_CHOICES = [
        (STORAGE_LOCAL, 'Local Storage'),
        (STORAGE_S3, 'Amazon S3'),
        (STORAGE_GCS, 'Google Cloud Storage'),
        (STORAGE_AZURE, 'Azure Blob Storage'),
        (STORAGE_FTP, 'FTP Server'),
        (STORAGE_SFTP, 'SFTP Server'),
        (STORAGE_DROPBOX, 'Dropbox'),
        (STORAGE_MULTI, 'Multiple Storage'),
        (STORAGE_REDUNDANT, 'Redundant Storage (Local + Cloud)'),
    ]
    
    # Retention Policy Types
    RETENTION_GFS = 'gfs'
    RETENTION_DAILY = 'daily'
    RETENTION_WEEKLY = 'weekly'
    RETENTION_MONTHLY = 'monthly'
    RETENTION_CUSTOM = 'custom'
    
    RETENTION_CHOICES = [
        (RETENTION_GFS, 'GFS (Grandfather-Father-Son)'),
        (RETENTION_DAILY, 'Daily Retention'),
        (RETENTION_WEEKLY, 'Weekly Retention'),
        (RETENTION_MONTHLY, 'Monthly Retention'),
        (RETENTION_CUSTOM, 'Custom Policy'),
    ]
    
    
    # ৩. অ্যাডমিন প্যানেলের এরর ফিক্স করার জন্য প্রয়োজনীয় ফিল্ডগুলো নিচে দিন
    name = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=100, default='pending', null=True, blank=True)
    duration = models.FloatField(null=True, blank=True) # এরর ফিক্স হবে
    verification_hash = models.CharField(max_length=255, null=True, blank=True) # এরর ফিক্স হবে
    is_verified = models.BooleanField(default=False) # এরর ফিক্স হবে
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # 🔴 MISSING FIELDS ADDED
    backup_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name=_("Backup ID"))
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Backup Name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    backup_type = models.CharField(max_length=255, choices=BACKUP_TYPE_CHOICES, default=BACKUP_TYPE_FULL, verbose_name=_("Backup Type"))
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name=_("Status"))
    
    # --- Basic Metadata ---
    storage_type = models.CharField(max_length=100, choices=STORAGE_CHOICES, default=STORAGE_LOCAL, verbose_name=_("Storage Type"))
    database_name = models.CharField(max_length=100, verbose_name=_("Database Name"))
    file_path = models.CharField(max_length=500, null=True, blank=True, verbose_name=_("File Path"))
    file_size = models.BigIntegerField(default=0, verbose_name=_("File Size (Bytes)"))
    
    # --- Schedule & Verification (Fixes Admin Errors) ---
    is_scheduled = models.BooleanField(default=False, verbose_name=_("Is Scheduled?"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Is Verified?"))
    verification_hash = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Verification Hash"))
    duration = models.FloatField(null=True, blank=True, verbose_name=_("Duration (Seconds)"))
    
    # --- Advanced Features ---
    compression_type = models.CharField(max_length=100, default='zip', verbose_name=_("Compression"))
    encryption_type = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Encryption"))
    retention_policy = models.CharField(max_length=100, choices=RETENTION_CHOICES, default=RETENTION_DAILY, null=True, blank=True)
    
    # gfs_category এর length বাড়িয়ে ১১ এরর ফিক্স করা হলো
    gfs_category = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("GFS Category")) 
    
    # --- Statistics & Logging ---
    backup_speed = models.FloatField(default=0, verbose_name=_("Speed (MB/s)"))
    row_count = models.BigIntegerField(default=0, verbose_name=_("Total Rows"))
    
    # --- Timestamps ---
    start_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Start Time"))
    end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("End Time"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'backup_history'
        verbose_name = _('Database Backup')
        verbose_name_plural = _('Database Backups')
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['backup_id'], name='idx_backup_id_826'),
            models.Index(fields=['status'], name='idx_status_827'),
            models.Index(fields=['backup_type'], name='idx_backup_type_828'),
            models.Index(fields=['start_time'], name='idx_start_time_829'),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"
    
    
    # 🔴 CRITICAL: created_by field that was missing
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_backups',
        verbose_name=_("Created By")
    )
    
    # 🔴 File related missing fields
    backup_file = models.FileField(
        upload_to='backups/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name=_("Backup File"),
        validators=[FileExtensionValidator(allowed_extensions=['sql', 'gz', 'zip', 'tar', 'backup'])]
    )
    file_path = models.TextField(blank=True, null=True, verbose_name=_("File Path"))
    file_size = models.BigIntegerField(default=0, verbose_name=_("File Size (bytes)"))
    compressed_size = models.BigIntegerField(default=0, verbose_name=_("Compressed Size"))
    original_size = models.BigIntegerField(default=0, verbose_name=_("Original Size"))
    file_hash = models.CharField(max_length=128, blank=True, null=True, verbose_name=_("File Hash"))
    file_format = models.CharField(max_length=100, default='sql', verbose_name=_("File Format"))
    
    # 🔴 Database info missing fields
    database_name = models.CharField(max_length=255, default='default', verbose_name=_("Database Name"))
    database_engine = models.CharField(max_length=100, default='postgresql', verbose_name=_("Database Engine"))
    database_host = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Database Host"))
    database_port = models.IntegerField(default=5432, verbose_name=_("Database Port"))
    database_user = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Database User"))
    tables_included = models.JSONField(default=list, blank=True, verbose_name=_("Tables Included"))
    tables_excluded = models.JSONField(default=list, blank=True, verbose_name=_("Tables Excluded"))
    
    # 🔴 Storage info missing fields
    storage_type = models.CharField(max_length=100, choices=STORAGE_CHOICES, default=STORAGE_LOCAL, verbose_name=_("Storage Type"))
    storage_location = models.TextField(blank=True, null=True, verbose_name=_("Storage Location"))
    storage_config = models.JSONField(default=dict, blank=True, verbose_name=_("Storage Configuration"))
    
    # 🔴 Encryption & Compression missing fields
    encryption_enabled = models.BooleanField(default=False, verbose_name=_("Encryption Enabled"))
    encryption_method = models.CharField(max_length=100, default='AES-256', blank=True, verbose_name=_("Encryption Method"))
    encryption_key = models.TextField(blank=True, null=True, verbose_name=_("Encryption Key"))
    compression_enabled = models.BooleanField(default=True, verbose_name=_("Compression Enabled"))
    compression_method = models.CharField(max_length=100, default='gzip', blank=True, verbose_name=_("Compression Method"))
    compression_ratio = models.FloatField(default=0.0, verbose_name=_("Compression Ratio"))
    
    # 🔴 Timestamps missing fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    start_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Start Time"))
    end_time = models.DateTimeField(null=True, blank=True, verbose_name=_("End Time"))
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Expires At"))
    
    # 🔴 Retention missing fields
    retention_days = models.IntegerField(default=30, validators=[MinValueValidator(1)], verbose_name=_("Retention Days"))
    is_permanent = models.BooleanField(default=False, verbose_name=_("Is Permanent"))
    
    # 🔴 Error tracking missing fields
    error_message = models.TextField(blank=True, null=True, verbose_name=_("Error Message"))
    error_traceback = models.TextField(blank=True, null=True, verbose_name=_("Error Traceback"))
    retry_count = models.IntegerField(default=0, verbose_name=_("Retry Count"))
    
    # 🔴 Metadata missing fields
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))
    tags = models.JSONField(default=list, blank=True, verbose_name=_("Tags"))
    custom_fields = models.JSONField(default=dict, blank=True, verbose_name=_("Custom Fields"))
    
    # 🔴 Verification missing fields
    verified = models.BooleanField(default=False, verbose_name=_("Verified"))
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Verified At"))
    verification_notes = models.TextField(blank=True, null=True, verbose_name=_("Verification Notes"))
    
    # 🔴 আপনার NEW FIELDS (যেগুলো আগে থেকে ছিল)
    # Backup Integrity & Health
    is_healthy = models.BooleanField(default=True, help_text="Is the backup file not corrupted?")
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_check_count = models.IntegerField(default=0)
    health_score = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Health score from 0-100"
    )
    
    # Storage Redundancy
    redundancy_level = models.IntegerField(
        default=1,
        choices=[(1, 'Single Copy'), (2, 'Dual Copy'), (3, 'Triple Copy')],
        help_text="Number of copies stored"
    )
    storage_locations = models.JSONField(
        default=list,
        help_text="List of storage locations where this backup is stored"
    )
    
    # Delta Backup Support
    delta_base = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delta_children',
        help_text="Base backup for delta/incremental")
    changed_tables = models.JSONField(
        default=list,
        blank=True,
        help_text="For delta backups: list of changed tables"
    )
    changed_row_count = models.BigIntegerField(
        default=0,
        help_text="Number of rows changed since last backup"
    )
    
    # Intelligent Retention
    retention_policy = models.CharField(
        max_length=100,
        choices=RETENTION_CHOICES,
        default=RETENTION_DAILY)
    gfs_category = models.CharField(
        max_length=100,
        choices=[
            ('son', 'Son (Daily, null=True, blank=True)'),
            ('father', 'Father (Weekly)'),
            ('grandfather', 'Grandfather (Monthly)'),
        ],
        null=True,
        blank=True
    )
    
    # Notification Integration
    notification_sent = models.BooleanField(default=False)
    notification_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Channels used for notification: ['email', 'slack', 'telegram']"
    )
    
    # Performance Optimization
    chunk_size = models.IntegerField(
        default=1048576,
        help_text="Chunk size for streaming upload/download"
    )
    parallel_workers = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    
    # Auto-cleanup tracking
    auto_cleanup_enabled = models.BooleanField(default=True)
    last_cleanup_check = models.DateTimeField(null=True, blank=True)
    
    # Verification Flags
    verification_method = models.CharField(
        max_length=100,
        choices=[
            ('hash', 'Hash Verification'),
            ('size', 'Size Verification'),
            ('test_restore', 'Test Restore'),
            ('full', 'Full Verification'),
        ],
        default='hash'
    )
    
    # Additional fields for enhanced functionality
    backup_schedule = models.ForeignKey(
        'BackupSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups',
        verbose_name=_("Backup Schedule")
    )
    retention_policy_ref = models.ForeignKey(
        'RetentionPolicy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups',
        verbose_name=_("Retention Policy")
    )
    notification_config = models.ForeignKey(
        'BackupNotificationConfig',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backups',
        verbose_name=_("Notification Configuration")
    )
    parent_backup = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_backups',
        verbose_name=_("Parent Backup")
    )
    
    # Statistics
    total_records = models.BigIntegerField(default=0, verbose_name=_("Total Records"))
    backup_duration = models.FloatField(default=0.0, verbose_name=_("Backup Duration (seconds)"))
    upload_speed = models.FloatField(default=0.0, verbose_name=_("Upload Speed (MB/s)"))
    download_speed = models.FloatField(default=0.0, verbose_name=_("Download Speed (MB/s)"))
    
    # schedule alias — views.py select_related('schedule') এর জন্য
    schedule = models.ForeignKey(
        'BackupSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_backups',
        verbose_name='Schedule')

    # Verification user
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_backups',
        verbose_name='Verified By')

    # Security
    checksum = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Checksum"))
    signature = models.TextField(blank=True, null=True, verbose_name=_("Digital Signature"))
    key_id = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Encryption Key ID"))
    
    # Cost tracking
    storage_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Storage Cost")
    )
    bandwidth_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Bandwidth Cost")
    )
    
    # Audit
    last_accessed = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Accessed"))
    access_count = models.IntegerField(default=0, verbose_name=_("Access Count"))
    audit_log = models.JSONField(default=list, blank=True, verbose_name=_("Audit Log"))
    
    class Meta:
        db_table = 'backup_history'
        verbose_name = _('Database Backup')
        verbose_name_plural = _('Database Backups')
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['backup_id'], name='idx_backup_id_830'),
            models.Index(fields=['status'], name='idx_status_831'),
            models.Index(fields=['backup_type'], name='idx_backup_type_832'),
            models.Index(fields=['created_by'], name='idx_created_by_833'),
            models.Index(fields=['start_time'], name='idx_start_time_834'),
            models.Index(fields=['database_name'], name='idx_database_name_835'),
            models.Index(fields=['is_healthy'], name='idx_is_healthy_836'),
            models.Index(fields=['retention_policy'], name='idx_retention_policy_837'),
            models.Index(fields=['health_score'], name='idx_health_score_838'),
            models.Index(fields=['storage_type'], name='idx_storage_type_839'),
            models.Index(fields=['created_at'], name='idx_created_at_840'),
            models.Index(fields=['expires_at'], name='idx_expires_at_841'),
            models.Index(fields=['verified'], name='idx_verified_842'),
            models.Index(fields=['encryption_enabled'], name='idx_encryption_enabled_843'),
            models.Index(fields=['compression_enabled'], name='idx_compression_enabled_844'),
            models.Index(fields=['backup_schedule'], name='idx_backup_schedule_845'),
            models.Index(fields=['retention_policy_ref'], name='idx_retention_policy_ref_846'),
            models.Index(fields=['parent_backup'], name='idx_parent_backup_847'),
            models.Index(fields=['delta_base'], name='idx_delta_base_848'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['name', 'database_name'], name='unique_backup_name_per_database'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.backup_type}) - {self.status}"
    
    def clean(self):
        """Custom validation"""
        super().clean()
        
        if self.start_time and self.end_time:
            if self.end_time < self.start_time:
                raise ValidationError({
                    'end_time': _('End time cannot be before start time.')
                })
        
        if self.expires_at and self.start_time:
            if self.expires_at < self.start_time:
                raise ValidationError({
                    'expires_at': _('Expiry time cannot be before start time.')
                })
    
    def save(self, *args, **kwargs):
        # Auto-calculate compression ratio
        if self.original_size > 0 and self.compressed_size > 0:
            self.compression_ratio = self.original_size / self.compressed_size
        
        # Auto-set expires_at based on retention
        if self.start_time and self.retention_days and not self.expires_at and not self.is_permanent:
            self.expires_at = self.start_time + timedelta(days=self.retention_days)
        
        # Calculate backup duration
        if self.start_time and self.end_time:
            self.backup_duration = (self.end_time - self.start_time).total_seconds()
        
        # Auto-calculate file size if backup_file exists
        if self.backup_file and self.file_size == 0:
            try:
                self.file_size = self.backup_file.size
            except:
                pass
        
        # Generate file hash if not exists
        if self.backup_file and not self.file_hash:
            try:
                self.file_hash = self.calculate_file_hash()
            except:
                pass
        
        super().save(*args, **kwargs)
    
    def calculate_file_hash(self):
        """Calculate SHA256 hash of backup file"""
        if not self.backup_file:
            return None
        
        sha256 = hashlib.sha256()
        chunk_size = 8192
        
        try:
            with self.backup_file.open('rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return None
    
    @property
    def duration_formatted(self):
        """Format duration as human readable"""
        if not self.backup_duration:
            return "N/A"
        
        hours = int(self.backup_duration // 3600)
        minutes = int((self.backup_duration % 3600) // 60)
        seconds = int(self.backup_duration % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @property
    def file_size_formatted(self):
        """Format file size as human readable"""
        if not self.file_size:
            return "0 B"
        
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} EB"
    
    @property
    def compression_percentage(self):
        """Calculate compression percentage"""
        if self.original_size > 0 and self.compressed_size > 0:
            return ((self.original_size - self.compressed_size) / self.original_size) * 100
        return 0.0
    
    @property
    def age_days(self):
        """Get backup age in days"""
        if self.created_at:
            return (timezone.now() - self.created_at).days
        return 0
    
    @property
    def is_expired(self):
        """Check if backup is expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_delta_backup(self):
        """Check if this is a delta backup"""
        return self.backup_type in [self.BACKUP_TYPE_INCREMENTAL, self.BACKUP_TYPE_DELTA, self.BACKUP_TYPE_DIFFERENTIAL]
    
    def check_health(self):
        """Perform health check on backup file"""
        from .tasks import verify_backup_health_task
        verify_backup_health_task.delay(self.id)
        return True
    
    def get_redundant_copies(self):
        """Get all copies of this backup across storage locations"""
        from .models import BackupStorageLocation
        locations = []
        for location_id in self.storage_locations:
            try:
                location = BackupStorageLocation.objects.get(id=location_id)
                locations.append({
                    'id': location.id,
                    'name': location.name,
                    'type': location.storage_type,
                    'is_connected': location.is_connected
                })
            except BackupStorageLocation.DoesNotExist:
                continue
        return locations
    
    def calculate_retention_expiry(self):
        """Calculate expiry based on GFS policy"""
        if self.retention_policy == self.RETENTION_GFS:
            if self.gfs_category == 'son':
                return self.start_time + timedelta(days=7)
            elif self.gfs_category == 'father':
                return self.start_time + timedelta(days=30)
            elif self.gfs_category == 'grandfather':
                return self.start_time + timedelta(days=365)
        
        if self.start_time and self.retention_days:
            return self.start_time + timedelta(days=self.retention_days)
        return None
    
    def send_notification(self, message, level='info'):
        """Send notification through configured channels"""
        from .tasks import send_backup_notification_task
        send_backup_notification_task.delay(
            backup_id=self.id,
            message=message,
            level=level,
            channels=self.notification_channels
        )
    
    def mark_as_verified(self, notes="", verification_method='manual'):
        """Mark backup as verified"""
        self.verified = True
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.verification_method = verification_method
        self.health_score = min(100, self.health_score + 10)
        self.save()
    
    def mark_as_failed(self, error_message, traceback=None):
        """Mark backup as failed"""
        self.status = self.STATUS_FAILED
        self.end_time = timezone.now()
        self.error_message = error_message
        self.error_traceback = traceback
        self.health_score = max(0, self.health_score - 20)
        self.save()
    
    @property
    def should_auto_cleanup(self):
        """Check if this backup should be auto-cleaned"""
        if not self.auto_cleanup_enabled:
            return False
        
        if self.is_permanent:
            return False
        
        now = timezone.now()
        if self.expires_at and now > self.expires_at:
            return True
        
        calculated_expiry = self.calculate_retention_expiry()
        if calculated_expiry and now > calculated_expiry:
            return True
        
        return False
    
    def delete_backup_file(self):
        """Delete physical backup file"""
        if self.backup_file:
            try:
                storage = self.backup_file.storage
                if storage.exists(self.backup_file.name):
                    storage.delete(self.backup_file.name)
                    logger.info(f"Deleted backup file: {self.backup_file.name}")
                    return True
            except Exception as e:
                logger.error(f"Error deleting backup file: {e}")
        return False
    
    def get_backup_info(self):
        """Get comprehensive backup information"""
        return {
            'id': str(self.id),
            'backup_id': str(self.backup_id),
            'name': self.name,
            'type': self.get_backup_type_display(),
            'status': self.get_status_display(),
            'database': self.database_name,
            'engine': self.database_engine,
            'file_size': self.file_size_formatted,
            'compression_ratio': f"{self.compression_ratio:.2f}:1",
            'compression_percentage': f"{self.compression_percentage:.1f}%",
            'encryption': 'Enabled' if self.encryption_enabled else 'Disabled',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else 'N/A',
            'duration': self.duration_formatted,
            'age_days': self.age_days,
            'is_expired': self.is_expired,
            'is_healthy': self.is_healthy,
            'health_score': self.health_score,
            'verified': self.verified,
            'storage_type': self.get_storage_type_display(),
            'retention_policy': self.get_retention_policy_display(),
            'expires_at': self.expires_at.strftime('%Y-%m-%d %H:%M:%S') if self.expires_at else 'N/A',
        }
    
    def create_restoration_record(self, user, restoration_type='full', tables=None, notes=''):
        """Create a restoration record for this backup"""
        restoration = BackupRestoration.objects.create(
            backup=self,
            restoration_type=restoration_type,
            initiated_by=user,
            tables_to_restore=tables or [],
            notes=notes,
            restore_point=timezone.now()
        )
        return restoration


class BackupStorageLocation(models.Model):
    """Storage location configuration"""
    STORAGE_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
        ('full', 'Storage Full'),
    ]
    
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))
    storage_type = models.CharField(max_length=100, choices=Backup.STORAGE_CHOICES, verbose_name=_("Storage Type"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    
    # Connection details
    endpoint = models.CharField(max_length=500, blank=True, null=True, verbose_name=_("Endpoint"))
    bucket_name = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Bucket/Container Name"))
    access_key = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Access Key"))
    secret_key = models.CharField(max_length=500, blank=True, null=True, verbose_name=_("Secret Key"))
    region = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Region"))
    
    # Path configuration
    base_path = models.CharField(max_length=500, default='/backups/', verbose_name=_("Base Path"))
    folder_structure = models.CharField(
        max_length=100,
        default='{year}/{month}/{day}/',
        help_text="Folder structure template. Available variables: {year}, {month}, {day}, {hour}, {minute}, {database}, {type}",
        verbose_name=_("Folder Structure")
    )
    
    # Configuration
    config = models.JSONField(default=dict, blank=True, verbose_name=_("Configuration"))
    is_default = models.BooleanField(default=False, verbose_name=_("Is Default"))
    priority = models.IntegerField(default=1, verbose_name=_("Priority"))
    
    # Status
    status = models.CharField(max_length=100, choices=STORAGE_STATUS, default='active', verbose_name=_("Status"))
    is_connected = models.BooleanField(default=True, verbose_name=_("Is Connected"))
    last_connection_check = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Connection Check"))
    connection_error = models.TextField(blank=True, null=True, verbose_name=_("Connection Error"))
    
    # Capacity
    total_space = models.BigIntegerField(default=0, verbose_name=_("Total Space (bytes)"))
    used_space = models.BigIntegerField(default=0, verbose_name=_("Used Space (bytes)"))
    free_space = models.BigIntegerField(default=0, verbose_name=_("Free Space (bytes)"))
    space_used_percentage = models.FloatField(default=0.0, verbose_name=_("Space Used Percentage"))
    
    # Performance
    upload_speed = models.FloatField(default=0.0, verbose_name=_("Upload Speed (MB/s)"))
    download_speed = models.FloatField(default=0.0, verbose_name=_("Download Speed (MB/s)"))
    latency = models.FloatField(default=0.0, verbose_name=_("Latency (ms)"))
    
    # Cost
    storage_cost_per_gb = models.DecimalField(max_digits=10, decimal_places=4, default=0.00, verbose_name=_("Storage Cost per GB"))
    bandwidth_cost_per_gb = models.DecimalField(max_digits=10, decimal_places=4, default=0.00, verbose_name=_("Bandwidth Cost per GB"))
    monthly_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name=_("Monthly Cost"))
    
    # Security
    encryption_at_rest = models.BooleanField(default=False, verbose_name=_("Encryption at Rest"))
    encryption_in_transit = models.BooleanField(default=True, verbose_name=_("Encryption in Transit"))
    ssl_required = models.BooleanField(default=True, verbose_name=_("SSL Required"))
    
    # Redundancy
    redundancy_enabled = models.BooleanField(default=False, verbose_name=_("Redundancy Enabled"))
    replication_factor = models.IntegerField(default=1, verbose_name=_("Replication Factor"))
    geographic_redundancy = models.BooleanField(default=False, verbose_name=_("Geographic Redundancy"))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Created By"))
    tags = models.JSONField(default=list, blank=True, verbose_name=_("Tags"))
    
    # Audit
    last_backup_stored = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Backup Stored"))
    total_backups_stored = models.IntegerField(default=0, verbose_name=_("Total Backups Stored"))
    total_data_stored = models.BigIntegerField(default=0, verbose_name=_("Total Data Stored (bytes)"))
    
    # আপনার existing fields এর নিচে এগুলো যোগ করুন

    # ১. Admin খুঁজছে 'is_active', আপনার আছে 'status'. 
    # তাই একটি প্রপার্টি যোগ করি যেন এরর না দেয়।
    @property
    def is_active(self):
        return self.status == 'active'

    # ২. Admin খুঁজছে 'last_checked', আপনার আছে 'last_connection_check'.
    # এটাকে alias করে দিচ্ছি।
    @property
    def last_checked(self):
        return self.last_connection_check

    # ৩. Admin খুঁজছে 'connection_errors' (সংখ্যা), আপনার আছে 'connection_error' (টেক্সট)।
    # এরর ফিক্স করতে এই ফিল্ডটি যোগ করুন:
    connection_errors = models.PositiveIntegerField(default=0, verbose_name=_("Connection Errors Count"))

    # ৪. Admin খুঁজছে 'last_error_message', এটাকে alias করে দিন:
    @property
    def last_error_message(self):
        return self.connection_error

    # ৫. Admin খুঁজছে 'usage_percentage', আপনার আছে 'space_used_percentage'.
    @property
    def usage_percentage(self):
        return self.space_used_percentage
    
    class Meta:
        db_table = 'backup_storage_locations'
        verbose_name = _('Storage Location')
        verbose_name_plural = _('Storage Locations')
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['storage_type'], name='idx_storage_type_849'),
            models.Index(fields=['status'], name='idx_status_850'),
            models.Index(fields=['is_default'], name='idx_is_default_851'),
            models.Index(fields=['priority'], name='idx_priority_852'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_storage_type_display()})"
    
    @property
    def free_space_formatted(self):
        """Format free space as human readable"""
        if not self.free_space:
            return "0 B"
        
        size = float(self.free_space)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @property
    def used_space_formatted(self):
        """Format used space as human readable"""
        if not self.used_space:
            return "0 B"
        
        size = float(self.used_space)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @property
    def total_space_formatted(self):
        """Format total space as human readable"""
        if not self.total_space:
            return "0 B"
        
        size = float(self.total_space)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def update_space_usage(self):
        """Update space usage statistics"""
        from django.db.models import Sum
        backups = Backup.objects.filter(
            models.Q(storage_location__contains=self.id) |
            models.Q(storage_locations__contains=self.id)
        )
        
        self.total_backups_stored = backups.count()
        self.total_data_stored = backups.aggregate(total=Sum('file_size'))['total'] or 0
        self.used_space = self.total_data_stored
        
        if self.total_space > 0:
            self.space_used_percentage = (self.used_space / self.total_space) * 100
            self.free_space = self.total_space - self.used_space
        
        self.save()


class BackupSchedule(models.Model):
    """Backup schedule configuration"""
    FREQUENCY_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom Cron'),
    ]
    
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]
    
    
    # ... আপনার cron_expression এর পর থেকে ...

    # টাইম এবং ডে কনফিগারেশন
    scheduled_time = models.TimeField(default='00:00', verbose_name=_("Execution Time"))
    day_of_week = models.IntegerField(choices=DAY_CHOICES, null=True, blank=True, verbose_name=_("Day of Week"))
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Day of Month"))
    month_of_year = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True, verbose_name=_("Month of Year"))

    # ব্যাকআপ সেটিংস
    backup_type = models.CharField(max_length=100, choices=Backup.BACKUP_TYPE_CHOICES, default='full', null=True, blank=True)
    
    # 🔴 অ্যাডমিন এরর ফিক্স করার জন্য এই ফিল্ডগুলো অবশ্যই যোগ করুন
    storage_type = models.CharField(
        max_length=100, 
        choices=Backup.STORAGE_CHOICES, 
        default='local',
        verbose_name=_("Storage Type")
    )
    
    # স্ট্যাটাস এবং ট্র্যাকিং
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    # 🔴 অ্যাডমিন এরর (readonly_fields) ফিক্স করার জন্য এই ৩টি ফিল্ড লাগবেই
    successful_executions = models.PositiveIntegerField(default=0, verbose_name=_("Successful Executions"))
    last_success = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Success"))
    last_failure = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Failure"))

    # টাইমস্ট্যাম্প
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Backup Schedule")
        verbose_name_plural = _("Backup Schedules")

    def __str__(self):
        return f"{self.name} ({self.frequency})"
    
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Schedule Name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    
    # Schedule configuration
    frequency = models.CharField(max_length=100, choices=FREQUENCY_CHOICES, default='daily', verbose_name=_("Frequency"))
    cron_expression = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cron Expression"))
    
    # Daily schedule
    daily_time = models.TimeField(default='02:00:00', verbose_name=_("Daily Time"))
    
    # Weekly schedule
    weekly_day = models.IntegerField(choices=DAY_CHOICES, default=0, verbose_name=_("Weekly Day"))
    weekly_time = models.TimeField(default='02:00:00', verbose_name=_("Weekly Time"))
    
    # Monthly schedule
    monthly_day = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(31)], verbose_name=_("Monthly Day"))
    monthly_time = models.TimeField(default='02:00:00', verbose_name=_("Monthly Time"))
    
    # Hourly schedule
    hourly_minute = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(59)], verbose_name=_("Hourly Minute"))
    
    # Backup configuration
    backup_type = models.CharField(max_length=100, choices=Backup.BACKUP_TYPE_CHOICES, default='full', verbose_name=_("Backup Type"))
    databases = models.JSONField(default=list, blank=True, verbose_name=_("Databases"))
    tables_include = models.JSONField(default=list, blank=True, verbose_name=_("Tables to Include"))
    tables_exclude = models.JSONField(default=list, blank=True, verbose_name=_("Tables to Exclude"))
    
    # Storage configuration
    storage_locations = models.JSONField(default=list, blank=True, verbose_name=_("Storage Locations"))
    encryption_enabled = models.BooleanField(default=False, verbose_name=_("Encryption Enabled"))
    compression_enabled = models.BooleanField(default=True, verbose_name=_("Compression Enabled"))
    retention_days = models.IntegerField(default=30, validators=[MinValueValidator(1)], verbose_name=_("Retention Days"))
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    is_paused = models.BooleanField(default=False, verbose_name=_("Is Paused"))
    last_run = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Run"))
    next_run = models.DateTimeField(null=True, blank=True, verbose_name=_("Next Run"))
    last_run_status = models.CharField(max_length=100, choices=Backup.STATUS_CHOICES, null=True, blank=True, verbose_name=_("Last Run Status"))
    last_run_error = models.TextField(blank=True, null=True, verbose_name=_("Last Run Error"))
    
    # Statistics
    total_runs = models.IntegerField(default=0, verbose_name=_("Total Runs"))
    successful_runs = models.IntegerField(default=0, verbose_name=_("Successful Runs"))
    failed_runs = models.IntegerField(default=0, verbose_name=_("Failed Runs"))
    success_rate = models.FloatField(default=0.0, verbose_name=_("Success Rate"))
    
    # Notifications
    notify_on_success = models.BooleanField(default=True, verbose_name=_("Notify on Success"))
    notify_on_failure = models.BooleanField(default=True, verbose_name=_("Notify on Failure"))
    notification_channels = models.JSONField(default=list, blank=True, verbose_name=_("Notification Channels"))
    
    # Advanced settings
    max_parallel_backups = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name=_("Max Parallel Backups"))
    timeout_minutes = models.IntegerField(default=60, validators=[MinValueValidator(1)], verbose_name=_("Timeout (minutes)"))
    retry_on_failure = models.BooleanField(default=True, verbose_name=_("Retry on Failure"))
    retry_count = models.IntegerField(default=3, validators=[MinValueValidator(0), MaxValueValidator(10)], verbose_name=_("Retry Count"))
    retry_delay_minutes = models.IntegerField(default=5, validators=[MinValueValidator(1)], verbose_name=_("Retry Delay (minutes)"))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name=_("Created By"))
    tags = models.JSONField(default=list, blank=True, verbose_name=_("Tags"))
    
    class Meta:
        db_table = 'backup_schedules'
        verbose_name = _('Backup Schedule')
        verbose_name_plural = _('Backup Schedules')
        ordering = ['name']
        indexes = [
            models.Index(fields=['frequency'], name='idx_frequency_853'),
            models.Index(fields=['is_active'], name='idx_is_active_854'),
            models.Index(fields=['next_run'], name='idx_next_run_855'),
            models.Index(fields=['last_run_status'], name='idx_last_run_status_856'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def save(self, *args, **kwargs):
        # Calculate success rate
        if self.total_runs > 0:
            self.success_rate = (self.successful_runs / self.total_runs) * 100
        
        # Calculate next run if active
        if self.is_active and not self.is_paused:
            self.calculate_next_run()
        
        super().save(*args, **kwargs)
    
    def calculate_next_run(self):
        """Calculate next run time"""
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        now = timezone.now()
        
        if self.frequency == 'hourly':
            next_run = now.replace(minute=self.hourly_minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(hours=1)
        
        elif self.frequency == 'daily':
            next_run = datetime.combine(now.date(), self.daily_time)
            next_run = timezone.make_aware(next_run)
            if next_run <= now:
                next_run += timedelta(days=1)
        
        elif self.frequency == 'weekly':
            today = now.date()
            days_ahead = (self.weekly_day - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            next_date = today + timedelta(days=days_ahead)
            next_run = datetime.combine(next_date, self.weekly_time)
            next_run = timezone.make_aware(next_run)
        
        elif self.frequency == 'monthly':
            # Simplified monthly calculation
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            next_date = next_month.replace(day=min(self.monthly_day, 28))
            next_run = datetime.combine(next_date, self.monthly_time)
            next_run = timezone.make_aware(next_run)
        
        elif self.frequency == 'custom' and self.cron_expression:
            # Use croniter for custom cron expressions
            try:
                import croniter
                base_time = now.replace(second=0, microsecond=0)
                cron = croniter.croniter(self.cron_expression, base_time)
                next_run = cron.get_next(datetime)
                next_run = timezone.make_aware(next_run)
            except ImportError:
                logger.error("croniter not installed for custom cron expressions")
                next_run = None
            except Exception as e:
                logger.error(f"Error parsing cron expression: {e}")
                next_run = None
        else:
            next_run = None
        
        self.next_run = next_run
    
    def execute_schedule(self):
        """Execute this schedule"""
        from .tasks import execute_backup_schedule_task
        execute_backup_schedule_task.delay(self.id)
    
    def pause(self):
        """Pause the schedule"""
        self.is_paused = True
        self.next_run = None
        self.save()
    
    def resume(self):
        """Resume the schedule"""
        self.is_paused = False
        self.calculate_next_run()
        self.save()
    
    def record_run(self, status, error_message=None):
        """Record schedule run"""
        self.last_run = timezone.now()
        self.last_run_status = status
        self.last_run_error = error_message
        self.total_runs += 1
        
        if status == 'completed':
            self.successful_runs += 1
        elif status == 'failed':
            self.failed_runs += 1
        
        self.calculate_next_run()
        self.save()


class BackupRestoration(models.Model):
    """Track backup restoration history"""
    
    RESTORATION_TYPE_CHOICES = [
        ('full', 'Full Database Restoration'),
        ('partial', 'Partial Restoration'),
        ('tables', 'Specific Tables'),
        ('schema', 'Schema Only'),
        ('data', 'Data Only'),
    ]
    
    RESTORATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    
    restoration_id = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name=_("Restoration ID"))
    backup = models.ForeignKey(Backup, on_delete=models.CASCADE, related_name='restorations', verbose_name=_("Backup"))
    restoration_type = models.CharField(max_length=100, choices=RESTORATION_TYPE_CHOICES, verbose_name=_("Restoration Type"))
    status = models.CharField(max_length=100, choices=RESTORATION_STATUS_CHOICES, default='pending', verbose_name=_("Status"))
    
    # What to restore
    tables_to_restore = models.JSONField(default=list, blank=True, verbose_name=_("Tables to Restore"))
    restore_point = models.DateTimeField(help_text="Point in time to restore to", verbose_name=_("Restore Point"))
    
    # Execution details
    started_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Started At"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))
    duration = models.FloatField(default=0.0, verbose_name=_("Duration"))
    
    # User info
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='initiated_restorations', verbose_name=_("Initiated By"))
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_restorations', verbose_name=_("Reviewed By"))
    
    # Results
    success = models.BooleanField(default=False, verbose_name=_("Success"))
    error_message = models.TextField(blank=True, null=True, verbose_name=_("Error Message"))
    error_traceback = models.TextField(blank=True, null=True, verbose_name=_("Error Traceback"))
    
    # Verification
    verification_passed = models.BooleanField(default=False, verbose_name=_("Verification Passed"))
    verification_details = models.JSONField(default=dict, blank=True, verbose_name=_("Verification Details"))
    
    # Rollback capability
    rollback_enabled = models.BooleanField(default=True, verbose_name=_("Rollback Enabled"))
    rollback_performed = models.BooleanField(default=False, verbose_name=_("Rollback Performed"))
    rollback_to_backup = models.ForeignKey(Backup, on_delete=models.SET_NULL, null=True, blank=True, related_name='rollback_from', verbose_name=_("Rollback to Backup"))
    
    # Metadata
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    metadata = models.JSONField(default=dict, blank=True, verbose_name=_("Metadata"))
    
    class Meta:
        db_table = 'backup_restorations'
        verbose_name = _('Backup Restoration')
        verbose_name_plural = _('Backup Restorations')
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Restoration of {self.backup.name} - {self.status}"
    
    def save(self, *args, **kwargs):
        # Calculate duration
        if self.completed_at and self.started_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()
        super().save(*args, **kwargs)
    
    @property
    def restoration_successful(self):
        return self.status == 'completed' and self.success


class BackupLog(models.Model):
    """
    Comprehensive logging system for all backup-related activities
    Tracks every action, error, and state change in the backup system
    """
    
    # Log Levels
    LOG_LEVEL_DEBUG = 'debug'
    LOG_LEVEL_INFO = 'info'
    LOG_LEVEL_WARNING = 'warning'
    LOG_LEVEL_ERROR = 'error'
    LOG_LEVEL_CRITICAL = 'critical'
    LOG_LEVEL_AUDIT = 'audit'
    
    LOG_LEVEL_CHOICES = [
        (LOG_LEVEL_DEBUG, 'Debug'),
        (LOG_LEVEL_INFO, 'Information'),
        (LOG_LEVEL_WARNING, 'Warning'),
        (LOG_LEVEL_ERROR, 'Error'),
        (LOG_LEVEL_CRITICAL, 'Critical'),
        (LOG_LEVEL_AUDIT, 'Audit'),
    ]
    
    # Log Categories
    LOG_CATEGORY_BACKUP = 'backup'
    LOG_CATEGORY_RESTORE = 'restore'
    LOG_CATEGORY_SCHEDULE = 'schedule'
    LOG_CATEGORY_STORAGE = 'storage'
    LOG_CATEGORY_VALIDATION = 'validation'
    LOG_CATEGORY_ENCRYPTION = 'encryption'
    LOG_CATEGORY_COMPRESSION = 'compression'
    LOG_CATEGORY_NOTIFICATION = 'notification'
    LOG_CATEGORY_CLEANUP = 'cleanup'
    LOG_CATEGORY_SYSTEM = 'system'
    LOG_CATEGORY_SECURITY = 'security'
    LOG_CATEGORY_PERFORMANCE = 'performance'
    
    LOG_CATEGORY_CHOICES = [
        (LOG_CATEGORY_BACKUP, 'Backup Operation'),
        (LOG_CATEGORY_RESTORE, 'Restore Operation'),
        (LOG_CATEGORY_SCHEDULE, 'Schedule Management'),
        (LOG_CATEGORY_STORAGE, 'Storage Operation'),
        (LOG_CATEGORY_VALIDATION, 'Validation Operation'),
        (LOG_CATEGORY_ENCRYPTION, 'Encryption Operation'),
        (LOG_CATEGORY_COMPRESSION, 'Compression Operation'),
        (LOG_CATEGORY_NOTIFICATION, 'Notification Operation'),
        (LOG_CATEGORY_CLEANUP, 'Cleanup Operation'),
        (LOG_CATEGORY_SYSTEM, 'System Operation'),
        (LOG_CATEGORY_SECURITY, 'Security Operation'),
        (LOG_CATEGORY_PERFORMANCE, 'Performance Operation'),
    ]
    
    # Action Types
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_START = 'start'
    ACTION_COMPLETE = 'complete'
    ACTION_FAIL = 'fail'
    ACTION_VALIDATE = 'validate'
    ACTION_ENCRYPT = 'encrypt'
    ACTION_DECRYPT = 'decrypt'
    ACTION_COMPRESS = 'compress'
    ACTION_DECOMPRESS = 'decompress'
    ACTION_UPLOAD = 'upload'
    ACTION_DOWNLOAD = 'download'
    ACTION_VERIFY = 'verify'
    ACTION_RESTORE = 'restore'
    ACTION_ROLLBACK = 'rollback'
    ACTION_NOTIFY = 'notify'
    ACTION_CLEANUP = 'cleanup'
    ACTION_SCHEDULE = 'schedule'
    ACTION_CONFIG_CHANGE = 'config_change'
    ACTION_SECURITY_EVENT = 'security_event'
    
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_START, 'Start'),
        (ACTION_COMPLETE, 'Complete'),
        (ACTION_FAIL, 'Fail'),
        (ACTION_VALIDATE, 'Validate'),
        (ACTION_ENCRYPT, 'Encrypt'),
        (ACTION_DECRYPT, 'Decrypt'),
        (ACTION_COMPRESS, 'Compress'),
        (ACTION_DECOMPRESS, 'Decompress'),
        (ACTION_UPLOAD, 'Upload'),
        (ACTION_DOWNLOAD, 'Download'),
        (ACTION_VERIFY, 'Verify'),
        (ACTION_RESTORE, 'Restore'),
        (ACTION_ROLLBACK, 'Rollback'),
        (ACTION_NOTIFY, 'Notify'),
        (ACTION_CLEANUP, 'Cleanup'),
        (ACTION_SCHEDULE, 'Schedule'),
        (ACTION_CONFIG_CHANGE, 'Configuration Change'),
        (ACTION_SECURITY_EVENT, 'Security Event'),
    ]
    
    # Log Sources
    SOURCE_API = 'api'
    SOURCE_ADMIN = 'admin'
    SOURCE_COMMAND = 'command'
    SOURCE_TASK = 'task'
    SOURCE_SCHEDULER = 'scheduler'
    SOURCE_SYSTEM = 'system'
    SOURCE_USER = 'user'
    SOURCE_AUTO = 'auto'
    
    SOURCE_CHOICES = [
        (SOURCE_API, 'API'),
        (SOURCE_ADMIN, 'Admin Panel'),
        (SOURCE_COMMAND, 'Management Command'),
        (SOURCE_TASK, 'Background Task'),
        (SOURCE_SCHEDULER, 'Scheduler'),
        (SOURCE_SYSTEM, 'System'),
        (SOURCE_USER, 'User Action'),
        (SOURCE_AUTO, 'Automated Process'),
    ]
    
    # Primary fields
    log_id = models.UUIDField(
        default=uuid.uuid4, 
        unique=True, 
        editable=False,
        verbose_name=_("Log ID")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )
    
    # Log metadata
    level = models.CharField(
        max_length=100,
        choices=LOG_LEVEL_CHOICES,
        default=LOG_LEVEL_INFO,
        verbose_name=_("Log Level")
    )
    category = models.CharField(
        max_length=100,
        choices=LOG_CATEGORY_CHOICES,
        default=LOG_CATEGORY_SYSTEM,
        verbose_name=_("Category")
    )
    action = models.CharField(
        max_length=100,
        choices=ACTION_CHOICES,
        verbose_name=_("Action")
    )
    source = models.CharField(
        max_length=100,
        choices=SOURCE_CHOICES,
        verbose_name=_("Source")
    )
    
    # Message and details
    message = models.TextField(
        verbose_name=_("Message")
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Details")
    )
    
    # Related objects
    backup = models.ForeignKey(
        Backup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name=_("Related Backup")
    )
    schedule = models.ForeignKey(
        BackupSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name=_("Related Schedule")
    )
    restoration = models.ForeignKey(
        BackupRestoration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name=_("Related Restoration")
    )
    
    # User information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_logs',
        verbose_name=_("User")
    )
    user_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("User IP Address")
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("User Agent")
    )
    
    # Performance metrics
    duration = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)")
    )
    memory_usage = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Memory Usage (bytes)")
    )
    cpu_usage = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("CPU Usage (%)")
    )
    
    # Error information
    error_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Error Code")
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Error Message")
    )
    error_traceback = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Error Traceback")
    )
    error_context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Error Context")
    )
    
    # File/Storage information
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("File Size (bytes)")
    )
    storage_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Storage Type")
    )
    storage_location = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Storage Location")
    )
    
    # Network information
    network_speed = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Network Speed (MB/s)")
    )
    bytes_transferred = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Bytes Transferred")
    )
    transfer_duration = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Transfer Duration (seconds)")
    )
    
    # Security information
    encryption_method = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Encryption Method")
    )
    compression_method = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Compression Method")
    )
    checksum = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Checksum")
    )
    
    # System information
    hostname = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Hostname")
    )
    process_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Process ID")
    )
    thread_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Thread ID")
    )
    
    # Additional metadata
    tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Tags")
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata")
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Session ID")
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Request ID")
    )
    
    # Status flags
    is_processed = models.BooleanField(
        default=False,
        verbose_name=_("Is Processed")
    )
    is_archived = models.BooleanField(
        default=False,
        verbose_name=_("Is Archived")
    )
    requires_attention = models.BooleanField(
        default=False,
        verbose_name=_("Requires Attention")
    )
    
    class Meta:
        db_table = 'backup_logs'
        verbose_name = _('Backup Log')
        verbose_name_plural = _('Backup Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp'], name='idx_timestamp_857'),
            models.Index(fields=['level'], name='idx_level_858'),
            models.Index(fields=['category'], name='idx_category_859'),
            models.Index(fields=['action'], name='idx_action_860'),
            models.Index(fields=['source'], name='idx_source_861'),
            models.Index(fields=['backup'], name='idx_backup_862'),
            models.Index(fields=['user'], name='idx_user_863'),
            models.Index(fields=['is_processed'], name='idx_is_processed_864'),
            models.Index(fields=['requires_attention'], name='idx_requires_attention_865'),
            models.Index(fields=['error_code'], name='idx_error_code_866'),
            models.Index(fields=['storage_type'], name='idx_storage_type_867'),
            models.Index(fields=['-timestamp', 'level'], name='idx_timestamp_level_868'),
            models.Index(fields=['-timestamp', 'category'], name='idx_timestamp_category_869'),
            models.Index(fields=['-timestamp', 'backup'], name='idx_timestamp_backup_870'),
        ]
        get_latest_by = 'timestamp'
    
    def __str__(self):
        return f"[{self.get_level_display()}] {self.message[:100]}"
    
    def save(self, *args, **kwargs):
        # Auto-set requires_attention for error/critical logs
        if self.level in [self.LOG_LEVEL_ERROR, self.LOG_LEVEL_CRITICAL]:
            self.requires_attention = True
        
        # Auto-set hostname if not provided
        if not self.hostname:
            try:
                self.hostname = socket.gethostname()
            except:
                self.hostname = 'unknown'
        
        super().save(*args, **kwargs)
    
    @property
    def is_error(self):
        """Check if log is an error"""
        return self.level in [self.LOG_LEVEL_ERROR, self.LOG_LEVEL_CRITICAL]
    
    @property
    def is_warning(self):
        """Check if log is a warning"""
        return self.level == self.LOG_LEVEL_WARNING
    
    @property
    def is_success(self):
        """Check if log indicates success"""
        return self.level == self.LOG_LEVEL_INFO and self.action in [
            self.ACTION_COMPLETE, self.ACTION_CREATE, self.ACTION_UPDATE
        ]
    
    @property
    def duration_formatted(self):
        """Format duration as human readable"""
        if not self.duration:
            return "N/A"
        
        if self.duration < 1:
            return f"{self.duration*1000:.0f}ms"
        elif self.duration < 60:
            return f"{self.duration:.1f}s"
        elif self.duration < 3600:
            minutes = int(self.duration // 60)
            seconds = int(self.duration % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(self.duration // 3600)
            minutes = int((self.duration % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    @property
    def file_size_formatted(self):
        """Format file size as human readable"""
        if not self.file_size:
            return "N/A"
        
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @property
    def memory_usage_formatted(self):
        """Format memory usage as human readable"""
        if not self.memory_usage:
            return "N/A"
        
        size = float(self.memory_usage)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    @property
    def age(self):
        """Get log age in seconds"""
        return (timezone.now() - self.timestamp).total_seconds()
    
    @property
    def age_formatted(self):
        """Format age as human readable"""
        age_seconds = self.age
        
        if age_seconds < 60:
            return f"{int(age_seconds)}s ago"
        elif age_seconds < 3600:
            minutes = int(age_seconds // 60)
            return f"{minutes}m ago"
        elif age_seconds < 86400:
            hours = int(age_seconds // 3600)
            return f"{hours}h ago"
        else:
            days = int(age_seconds // 86400)
            return f"{days}d ago"
    
    def get_log_context(self):
        """Get comprehensive log context"""
        context = {
            'log_id': str(self.log_id),
            'timestamp': self.timestamp.isoformat(),
            'level': self.get_level_display(),
            'category': self.get_category_display(),
            'action': self.get_action_display(),
            'source': self.get_source_display(),
            'message': self.message,
            'details': self.details,
            'age': self.age_formatted,
            'is_error': self.is_error,
            'requires_attention': self.requires_attention,
        }
        
        if self.backup:
            context['backup'] = {
                'id': str(self.backup.id),
                'name': self.backup.name,
                'type': self.backup.get_backup_type_display(),
                'status': self.backup.get_status_display(),
            }
        
        if self.user:
            context['user'] = {
                'id': str(self.user.id),
                'username': self.user.username,
                'email': self.user.email if hasattr(self.user, 'email') else None,
            }
        
        if self.error_code or self.error_message:
            context['error'] = {
                'code': self.error_code,
                'message': self.error_message,
                'traceback': self.error_traceback[:500] if self.error_traceback else None,
            }
        
        if self.duration:
            context['performance'] = {
                'duration': self.duration_formatted,
                'memory_usage': self.memory_usage_formatted,
                'cpu_usage': f"{self.cpu_usage:.1f}%" if self.cpu_usage else None,
            }
        
        if self.bytes_transferred:
            context['transfer'] = {
                'bytes': self.bytes_transferred,
                'bytes_formatted': self.file_size_formatted,
                'speed': f"{self.network_speed:.1f} MB/s" if self.network_speed else None,
                'duration': self.transfer_duration,
            }
        
        return context
    
    def mark_as_processed(self):
        """Mark log as processed"""
        self.is_processed = True
        self.save()
    
    def mark_for_attention(self):
        """Mark log as requiring attention"""
        self.requires_attention = True
        self.save()
    
    def archive(self):
        """Archive this log"""
        self.is_archived = True
        self.save()
    
    @classmethod
    def create_log(cls, **kwargs):
        """Factory method to create logs with standardized format"""
        log = cls(**kwargs)
        log.save()
        return log
    
    @classmethod
    def log_backup_start(cls, backup, user=None, **kwargs):
        """Log backup start"""
        return cls.create_log(
            level=cls.LOG_LEVEL_INFO,
            category=cls.LOG_CATEGORY_BACKUP,
            action=cls.ACTION_START,
            source=cls.SOURCE_TASK,
            backup=backup,
            user=user,
            message=f"Backup started: {backup.name}",
            details={
                'backup_id': str(backup.id),
                'backup_name': backup.name,
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'storage_type': backup.storage_type,
            },
            **kwargs
        )
    
    @classmethod
    def log_backup_complete(cls, backup, duration=None, file_size=None, **kwargs):
        """Log backup completion"""
        return cls.create_log(
            level=cls.LOG_LEVEL_INFO,
            category=cls.LOG_CATEGORY_BACKUP,
            action=cls.ACTION_COMPLETE,
            source=cls.SOURCE_TASK,
            backup=backup,
            message=f"Backup completed: {backup.name}",
            duration=duration,
            file_size=file_size,
            details={
                'backup_id': str(backup.id),
                'backup_name': backup.name,
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'file_size': file_size,
                'duration': duration,
                'compression_enabled': backup.compression_enabled,
                'encryption_enabled': backup.encryption_enabled,
            },
            **kwargs
        )
    
    @classmethod
    def log_backup_error(cls, backup, error_message, error_traceback=None, **kwargs):
        """Log backup error"""
        return cls.create_log(
            level=cls.LOG_LEVEL_ERROR,
            category=cls.LOG_CATEGORY_BACKUP,
            action=cls.ACTION_FAIL,
            source=cls.SOURCE_TASK,
            backup=backup,
            message=f"Backup failed: {backup.name}",
            error_message=error_message,
            error_traceback=error_traceback,
            requires_attention=True,
            details={
                'backup_id': str(backup.id),
                'backup_name': backup.name,
                'backup_type': backup.backup_type,
                'database': backup.database_name,
                'error': error_message,
            },
            **kwargs
        )
    
    @classmethod
    def log_restoration_start(cls, restoration, user=None, **kwargs):
        """Log restoration start"""
        return cls.create_log(
            level=cls.LOG_LEVEL_INFO,
            category=cls.LOG_CATEGORY_RESTORE,
            action=cls.ACTION_START,
            source=cls.SOURCE_TASK,
            restoration=restoration,
            backup=restoration.backup,
            user=user,
            message=f"Restoration started: {restoration.backup.name}",
            details={
                'restoration_id': str(restoration.restoration_id),
                'backup_name': restoration.backup.name,
                'restoration_type': restoration.restoration_type,
                'initiated_by': user.username if user else 'system',
            },
            **kwargs
        )
    
    @classmethod
    def log_security_event(cls, message, user=None, ip_address=None, **kwargs):
        """Log security event"""
        return cls.create_log(
            level=cls.LOG_LEVEL_AUDIT,
            category=cls.LOG_CATEGORY_SECURITY,
            action=cls.ACTION_SECURITY_EVENT,
            source=cls.SOURCE_SYSTEM,
            user=user,
            user_ip=ip_address,
            message=message,
            requires_attention=True,
            details={
                'security_event': True,
                'user': user.username if user else 'unknown',
                'ip_address': ip_address,
            },
            **kwargs
        )
    
    @classmethod
    def log_system_event(cls, message, level=LOG_LEVEL_INFO, **kwargs):
        """Log system event"""
        return cls.create_log(
            level=level,
            category=cls.LOG_CATEGORY_SYSTEM,
            action=cls.ACTION_CONFIG_CHANGE,
            source=cls.SOURCE_SYSTEM,
            message=message,
            details={'system_event': True},
            **kwargs
        )
    
    @classmethod
    def get_recent_logs(cls, hours=24, level=None, category=None):
        """Get recent logs"""
        queryset = cls.objects.filter(
            timestamp__gte=timezone.now() - timedelta(hours=hours)
        )
        
        if level:
            queryset = queryset.filter(level=level)
        
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('-timestamp')
    
    @classmethod
    def get_error_logs(cls, days=7):
        """Get error logs from last N days"""
        return cls.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=days),
            level__in=[cls.LOG_LEVEL_ERROR, cls.LOG_LEVEL_CRITICAL]
        ).order_by('-timestamp')
    
    @classmethod
    def get_logs_requiring_attention(cls):
        """Get logs that require attention"""
        return cls.objects.filter(
            requires_attention=True,
            is_processed=False
        ).order_by('-timestamp')
    
    @classmethod
    def cleanup_old_logs(cls, days=90):
        """Cleanup logs older than N days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        old_logs = cls.objects.filter(timestamp__lt=cutoff_date)
        
        count = old_logs.count()
        old_logs.delete()
        
        return count


# Define missing models with placeholders
class RetentionPolicy(models.Model):
    """Retention policy configuration"""
    name = models.CharField(max_length=255, null=True, blank=True)
    keep_all = models.BooleanField(default=False)
    keep_weekly = models.BooleanField(default=True)
    keep_monthly = models.BooleanField(default=True)
    keep_yearly = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'retention_policies'


class BackupNotificationConfig(models.Model):
    """Notification configuration for backups"""
    name = models.CharField(max_length=255, null=True, blank=True)
    notify_on_failure = models.BooleanField(default=True)
    notify_on_warning = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Created By')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'backup_notification_configs'


# Signal handlers
@receiver(pre_delete, sender=Backup)
def backup_pre_delete(sender, instance, **kwargs):
    """Handle backup deletion"""
    logger.info(f"Deleting backup: {instance.name}")
    instance.delete_backup_file()


@receiver(post_save, sender=Backup)
def backup_post_save(sender, instance, created, **kwargs):
    """Handle backup post-save actions"""
    if created:
        logger.info(f"Created new backup: {instance.name}")
        # Send notification for new backup
        if instance.notification_channels:
            instance.send_notification(f"New backup created: {instance.name}", 'info')


@receiver(post_save, sender=BackupRestoration)
def log_restoration_status_change(sender, instance, created, **kwargs):
    """Log restoration status changes"""
    if created:
        BackupLog.log_restoration_start(instance, instance.initiated_by)
    else:
        # Log status changes
        BackupLog.create_log(
            level=BackupLog.LOG_LEVEL_INFO,
            category=BackupLog.LOG_CATEGORY_RESTORE,
            action=BackupLog.ACTION_UPDATE,
            source=BackupLog.SOURCE_SYSTEM,
            restoration=instance,
            backup=instance.backup,
            message=f"Restoration status changed to: {instance.status}",
            details={
                'new_status': instance.status,
                'restoration_id': str(instance.restoration_id),
                'backup_name': instance.backup.name if instance.backup else 'unknown',
            }
        )


@receiver(post_save, sender=BackupSchedule)
def log_schedule_change(sender, instance, created, **kwargs):
    """Log schedule changes"""
    if created:
        BackupLog.create_log(
            level=BackupLog.LOG_LEVEL_INFO,
            category=BackupLog.LOG_CATEGORY_SCHEDULE,
            action=BackupLog.ACTION_CREATE,
            source=BackupLog.SOURCE_USER,
            schedule=instance,
            message=f"Backup schedule created: {instance.name}",
            details={
                'schedule_name': instance.name,
                'frequency': instance.frequency if hasattr(instance, 'frequency') else 'unknown',
                'backup_type': instance.backup_type if hasattr(instance, 'backup_type') else 'unknown',
            }
        )
    else:
        BackupLog.create_log(
            level=BackupLog.LOG_LEVEL_INFO,
            category=BackupLog.LOG_CATEGORY_SCHEDULE,
            action=BackupLog.ACTION_UPDATE,
            source=BackupLog.SOURCE_USER,
            schedule=instance,
            message=f"Backup schedule updated: {instance.name}",
            details={
                'schedule_name': instance.name,
                'is_active': instance.is_active if hasattr(instance, 'is_active') else False,
                'next_run': instance.next_run.isoformat() if hasattr(instance, 'next_run') and instance.next_run else None,
            }
        )


# Custom managers
class HealthyBackupManager(models.Manager):
    """Manager for healthy backups"""
    def get_queryset(self):
        return super().get_queryset().filter(is_healthy=True, status=Backup.STATUS_COMPLETED)


class ExpiredBackupManager(models.Manager):
    """Manager for expired backups"""
    def get_queryset(self):
        return super().get_queryset().filter(
            expires_at__lt=timezone.now(),
            is_permanent=False
        )


# Add custom managers to Backup model
Backup.healthy_objects = HealthyBackupManager()
Backup.expired_objects = ExpiredBackupManager()



class DeltaBackupTracker(models.Model):
    """Track delta/incremental backup relationships"""
    
    parent_backup = models.ForeignKey(
        Backup,
        on_delete=models.CASCADE,
        related_name='delta_parent',
        verbose_name=_("Parent Backup")
    )
    child_backup = models.ForeignKey(
        Backup,
        on_delete=models.CASCADE,
        related_name='delta_child',
        verbose_name=_("Child Backup")
    )
    changed_tables = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Changed Tables")
    )
    changed_row_count = models.BigIntegerField(
        default=0,
        verbose_name=_("Changed Row Count")
    )
    change_percentage = models.FloatField(
        default=0.0,
        verbose_name=_("Change Percentage")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    
    class Meta:
        db_table = 'delta_backup_tracker'
        verbose_name = _('Delta Backup Tracker')
        verbose_name_plural = _('Delta Backup Trackers')
        unique_together = ['parent_backup', 'child_backup']
        indexes = [
            models.Index(fields=['parent_backup'], name='idx_parent_backup_871'),
            models.Index(fields=['child_backup'], name='idx_child_backup_872'),
        ]
    
    def __str__(self):
        return f"Delta: {self.parent_backup.name} -> {self.child_backup.name}"