"""
Backup Module Choices
Constants and choices for backup models and forms
"""

from django.utils.translation import gettext_lazy as _


class BackupType:
    """Backup type choices"""
    FULL = 'full'
    INCREMENTAL = 'incremental'
    DIFFERENTIAL = 'differential'
    DELTA = 'delta'
    SCHEDULED = 'scheduled'
    MANUAL = 'manual'
    AUTOMATED = 'automated'
    
    CHOICES = [
        (FULL, _('Full Backup')),
        (INCREMENTAL, _('Incremental Backup')),
        (DIFFERENTIAL, _('Differential Backup')),
        (DELTA, _('Delta Backup')),
        (SCHEDULED, _('Scheduled Backup')),
        (MANUAL, _('Manual Backup')),
        (AUTOMATED, _('Automated Backup')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for backup type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class BackupStatus:
    """Backup status choices"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CORRUPTED = 'corrupted'
    CANCELLED = 'cancelled'
    VERIFYING = 'verifying'
    RESTORING = 'restoring'
    ARCHIVED = 'archived'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (RUNNING, _('Running')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
        (CORRUPTED, _('Corrupted')),
        (CANCELLED, _('Cancelled')),
        (VERIFYING, _('Verifying')),
        (RESTORING, _('Restoring')),
        (ARCHIVED, _('Archived')),
    ]
    
    # Status flow groups
    ACTIVE_STATUSES = [PENDING, RUNNING, VERIFYING, RESTORING]
    FINAL_STATUSES = [COMPLETED, FAILED, CORRUPTED, CANCELLED, ARCHIVED]
    SUCCESS_STATUSES = [COMPLETED, ARCHIVED]
    FAILURE_STATUSES = [FAILED, CORRUPTED, CANCELLED]
    
    @classmethod
    def is_active(cls, status):
        """Check if status is active (not final)"""
        return status in cls.ACTIVE_STATUSES
    
    @classmethod
    def is_final(cls, status):
        """Check if status is final"""
        return status in cls.FINAL_STATUSES
    
    @classmethod
    def is_success(cls, status):
        """Check if status indicates success"""
        return status in cls.SUCCESS_STATUSES
    
    @classmethod
    def is_failure(cls, status):
        """Check if status indicates failure"""
        return status in cls.FAILURE_STATUSES
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for backup status"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class StorageType:
    """Storage type choices"""
    LOCAL = 'local'
    S3 = 's3'
    GCS = 'gcs'
    AZURE = 'azure'
    FTP = 'ftp'
    SFTP = 'sftp'
    DROPBOX = 'dropbox'
    MULTI = 'multi'
    REDUNDANT = 'redundant'
    
    CHOICES = [
        (LOCAL, _('Local Storage')),
        (S3, _('Amazon S3')),
        (GCS, _('Google Cloud Storage')),
        (AZURE, _('Azure Blob Storage')),
        (FTP, _('FTP')),
        (SFTP, _('SFTP')),
        (DROPBOX, _('Dropbox')),
        (MULTI, _('Multi-Cloud')),
        (REDUNDANT, _('Redundant Storage')),
    ]
    
    # Cloud storage types
    CLOUD_STORAGE = [S3, GCS, AZURE, DROPBOX]
    NETWORK_STORAGE = [FTP, SFTP]
    LOCAL_STORAGE = [LOCAL]
    
    @classmethod
    def is_cloud_storage(cls, storage_type):
        """Check if storage type is cloud-based"""
        return storage_type in cls.CLOUD_STORAGE
    
    @classmethod
    def is_network_storage(cls, storage_type):
        """Check if storage type is network-based"""
        return storage_type in cls.NETWORK_STORAGE
    
    @classmethod
    def is_local_storage(cls, storage_type):
        """Check if storage type is local"""
        return storage_type in cls.LOCAL_STORAGE
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for storage type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class RestoreStatus:
    """Restore status choices"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    ROLLING_BACK = 'rolling_back'
    ROLLED_BACK = 'rolled_back'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (RUNNING, _('Running')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
        (CANCELLED, _('Cancelled')),
        (ROLLING_BACK, _('Rolling Back')),
        (ROLLED_BACK, _('Rolled Back')),
    ]
    
    # Status flow groups
    ACTIVE_STATUSES = [PENDING, RUNNING, ROLLING_BACK]
    FINAL_STATUSES = [COMPLETED, FAILED, CANCELLED, ROLLED_BACK]
    SUCCESS_STATUSES = [COMPLETED, ROLLED_BACK]
    FAILURE_STATUSES = [FAILED, CANCELLED]
    
    @classmethod
    def is_active(cls, status):
        """Check if status is active (not final)"""
        return status in cls.ACTIVE_STATUSES
    
    @classmethod
    def is_final(cls, status):
        """Check if status is final"""
        return status in cls.FINAL_STATUSES
    
    @classmethod
    def is_success(cls, status):
        """Check if status indicates success"""
        return status in cls.SUCCESS_STATUSES
    
    @classmethod
    def is_failure(cls, status):
        """Check if status indicates failure"""
        return status in cls.FAILURE_STATUSES
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for restore status"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class DatabaseEngine:
    """Database engine choices"""
    POSTGRESQL = 'postgresql'
    MYSQL = 'mysql'
    SQLITE = 'sqlite'
    ORACLE = 'oracle'
    MONGODB = 'mongodb'
    
    CHOICES = [
        (POSTGRESQL, _('PostgreSQL')),
        (MYSQL, _('MySQL')),
        (SQLITE, _('SQLite')),
        (ORACLE, _('Oracle')),
        (MONGODB, _('MongoDB')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for database engine"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class EncryptionType:
    """Encryption type choices"""
    NONE = 'none'
    AES256_GCM = 'AES-256-GCM'
    AES256_CBC = 'AES-256-CBC'
    CHACHA20_POLY1305 = 'ChaCha20-Poly1305'
    FERNET = 'Fernet'
    
    CHOICES = [
        (NONE, _('No Encryption')),
        (AES256_GCM, _('AES-256-GCM')),
        (AES256_CBC, _('AES-256-CBC')),
        (CHACHA20_POLY1305, _('ChaCha20-Poly1305')),
        (FERNET, _('Fernet')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for encryption type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class CompressionType:
    """Compression type choices"""
    NONE = 'none'
    GZIP = 'gzip'
    BZIP2 = 'bzip2'
    LZMA = 'lzma'
    ZIP = 'zip'
    ZSTD = 'zstd'
    
    CHOICES = [
        (NONE, _('No Compression')),
        (GZIP, _('Gzip')),
        (BZIP2, _('Bzip2')),
        (LZMA, _('LZMA')),
        (ZIP, _('ZIP')),
        (ZSTD, _('Zstandard')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for compression type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class ScheduleFrequency:
    """Schedule frequency choices"""
    HOURLY = 'hourly'
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    CUSTOM = 'custom'
    
    CHOICES = [
        (HOURLY, _('Hourly')),
        (DAILY, _('Daily')),
        (WEEKLY, _('Weekly')),
        (MONTHLY, _('Monthly')),
        (YEARLY, _('Yearly')),
        (CUSTOM, _('Custom (Cron)')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for schedule frequency"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class LogLevel:
    """Log level choices"""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'
    AUDIT = 'audit'
    
    CHOICES = [
        (DEBUG, _('Debug')),
        (INFO, _('Info')),
        (WARNING, _('Warning')),
        (ERROR, _('Error')),
        (CRITICAL, _('Critical')),
        (AUDIT, _('Audit')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for log level"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class VerificationMethod:
    """Verification method choices"""
    HASH = 'hash'
    SIZE = 'size'
    TEST_RESTORE = 'test_restore'
    FULL = 'full'
    
    CHOICES = [
        (HASH, _('Hash Check')),
        (SIZE, _('Size Check')),
        (TEST_RESTORE, _('Test Restore')),
        (FULL, _('Full Verification')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for verification method"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class AlertSeverity:
    """Alert severity choices"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, _('Low')),
        (MEDIUM, _('Medium')),
        (HIGH, _('High')),
        (CRITICAL, _('Critical')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for alert severity"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class AlertType:
    """Alert type choices"""
    FAILED = 'failed'
    SIZE_EXCEEDED = 'size_exceeded'
    SCHEDULE_MISSED = 'schedule_missed'
    STORAGE_FULL = 'storage_full'
    VERIFICATION_FAILED = 'verification_failed'
    RETENTION_EXPIRED = 'retention_expired'
    SECURITY = 'security'
    
    CHOICES = [
        (FAILED, _('Backup Failed')),
        (SIZE_EXCEEDED, _('Size Exceeded')),
        (SCHEDULE_MISSED, _('Schedule Missed')),
        (STORAGE_FULL, _('Storage Full')),
        (VERIFICATION_FAILED, _('Verification Failed')),
        (RETENTION_EXPIRED, _('Retention Expired')),
        (SECURITY, _('Security Alert')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for alert type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class RestorationType:
    """Restoration type choices"""
    FULL = 'full'
    PARTIAL = 'partial'
    SCHEMA_ONLY = 'schema_only'
    DATA_ONLY = 'data_only'
    TABLES = 'tables'
    
    CHOICES = [
        (FULL, _('Full Restoration')),
        (PARTIAL, _('Partial Restoration')),
        (SCHEMA_ONLY, _('Schema Only')),
        (DATA_ONLY, _('Data Only')),
        (TABLES, _('Specific Tables')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for restoration type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class LogCategory:
    """Log category choices"""
    BACKUP = 'backup'
    RESTORE = 'restore'
    SCHEDULE = 'schedule'
    STORAGE = 'storage'
    VALIDATION = 'validation'
    ENCRYPTION = 'encryption'
    COMPRESSION = 'compression'
    NOTIFICATION = 'notification'
    CLEANUP = 'cleanup'
    SYSTEM = 'system'
    SECURITY = 'security'
    PERFORMANCE = 'performance'
    
    CHOICES = [
        (BACKUP, _('Backup')),
        (RESTORE, _('Restore')),
        (SCHEDULE, _('Schedule')),
        (STORAGE, _('Storage')),
        (VALIDATION, _('Validation')),
        (ENCRYPTION, _('Encryption')),
        (COMPRESSION, _('Compression')),
        (NOTIFICATION, _('Notification')),
        (CLEANUP, _('Cleanup')),
        (SYSTEM, _('System')),
        (SECURITY, _('Security')),
        (PERFORMANCE, _('Performance')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for log category"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class LogAction:
    """Log action choices"""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    START = 'start'
    COMPLETE = 'complete'
    FAIL = 'fail'
    VALIDATE = 'validate'
    ENCRYPT = 'encrypt'
    DECRYPT = 'decrypt'
    COMPRESS = 'compress'
    DECOMPRESS = 'decompress'
    UPLOAD = 'upload'
    DOWNLOAD = 'download'
    VERIFY = 'verify'
    RESTORE = 'restore'
    ROLLBACK = 'rollback'
    NOTIFY = 'notify'
    CLEANUP = 'cleanup'
    SCHEDULE = 'schedule'
    CONFIG_CHANGE = 'config_change'
    SECURITY_EVENT = 'security_event'
    
    CHOICES = [
        (CREATE, _('Create')),
        (UPDATE, _('Update')),
        (DELETE, _('Delete')),
        (START, _('Start')),
        (COMPLETE, _('Complete')),
        (FAIL, _('Fail')),
        (VALIDATE, _('Validate')),
        (ENCRYPT, _('Encrypt')),
        (DECRYPT, _('Decrypt')),
        (COMPRESS, _('Compress')),
        (DECOMPRESS, _('Decompress')),
        (UPLOAD, _('Upload')),
        (DOWNLOAD, _('Download')),
        (VERIFY, _('Verify')),
        (RESTORE, _('Restore')),
        (ROLLBACK, _('Rollback')),
        (NOTIFY, _('Notify')),
        (CLEANUP, _('Cleanup')),
        (SCHEDULE, _('Schedule')),
        (CONFIG_CHANGE, _('Config Change')),
        (SECURITY_EVENT, _('Security Event')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for log action"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class LogSource:
    """Log source choices"""
    API = 'api'
    ADMIN = 'admin'
    COMMAND = 'command'
    TASK = 'task'
    SCHEDULER = 'scheduler'
    SYSTEM = 'system'
    USER = 'user'
    AUTO = 'auto'
    
    CHOICES = [
        (API, _('API')),
        (ADMIN, _('Admin')),
        (COMMAND, _('Command')),
        (TASK, _('Task')),
        (SCHEDULER, _('Scheduler')),
        (SYSTEM, _('System')),
        (USER, _('User')),
        (AUTO, _('Auto')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for log source"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class RetentionType:
    """Retention policy type choices"""
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    GFS = 'gfs'
    CUSTOM = 'custom'
    
    CHOICES = [
        (DAILY, _('Daily')),
        (WEEKLY, _('Weekly')),
        (MONTHLY, _('Monthly')),
        (YEARLY, _('Yearly')),
        (GFS, _('Grandfather-Father-Son')),
        (CUSTOM, _('Custom')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for retention type"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class NotificationChannel:
    """Notification channel choices"""
    EMAIL = 'email'
    SMS = 'sms'
    SLACK = 'slack'
    TELEGRAM = 'telegram'
    WEBHOOK = 'webhook'
    PUSH = 'push'
    IN_APP = 'in_app'
    CONSOLE = 'console'
    
    CHOICES = [
        (EMAIL, _('Email')),
        (SMS, _('SMS')),
        (SLACK, _('Slack')),
        (TELEGRAM, _('Telegram')),
        (WEBHOOK, _('Webhook')),
        (PUSH, _('Push Notification')),
        (IN_APP, _('In-App')),
        (CONSOLE, _('Console')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for notification channel"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class StorageClass:
    """S3 storage class choices"""
    STANDARD = 'STANDARD'
    STANDARD_IA = 'STANDARD_IA'
    ONEZONE_IA = 'ONEZONE_IA'
    GLACIER = 'GLACIER'
    DEEP_ARCHIVE = 'DEEP_ARCHIVE'
    INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
    
    CHOICES = [
        (STANDARD, _('Standard')),
        (STANDARD_IA, _('Standard-IA')),
        (ONEZONE_IA, _('OneZone-IA')),
        (GLACIER, _('Glacier')),
        (DEEP_ARCHIVE, _('Deep Archive')),
        (INTELLIGENT_TIERING, _('Intelligent-Tiering')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for storage class"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class HealthStatus:
    """Health status choices"""
    HEALTHY = 'healthy'
    WARNING = 'warning'
    CRITICAL = 'critical'
    UNKNOWN = 'unknown'
    
    CHOICES = [
        (HEALTHY, _('Healthy')),
        (WARNING, _('Warning')),
        (CRITICAL, _('Critical')),
        (UNKNOWN, _('Unknown')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for health status"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class PriorityLevel:
    """Priority level choices"""
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'
    
    CHOICES = [
        (LOW, _('Low')),
        (NORMAL, _('Normal')),
        (HIGH, _('High')),
        (URGENT, _('Urgent')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for priority level"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class TaskStatus:
    """Task status choices"""
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILURE = 'failure'
    RETRY = 'retry'
    REVOKED = 'revoked'
    
    CHOICES = [
        (PENDING, _('Pending')),
        (RUNNING, _('Running')),
        (SUCCESS, _('Success')),
        (FAILURE, _('Failure')),
        (RETRY, _('Retry')),
        (REVOKED, _('Revoked')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for task status"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value


class ComplianceLevel:
    """Compliance level choices"""
    NONE = 'none'
    BASIC = 'basic'
    STANDARD = 'standard'
    ENHANCED = 'enhanced'
    STRICT = 'strict'
    
    CHOICES = [
        (NONE, _('None')),
        (BASIC, _('Basic')),
        (STANDARD, _('Standard')),
        (ENHANCED, _('Enhanced')),
        (STRICT, _('Strict')),
    ]
    
    @classmethod
    def get_display_name(cls, value):
        """Get display name for compliance level"""
        for choice_value, choice_display in cls.CHOICES:
            if choice_value == value:
                return choice_display
        return value
