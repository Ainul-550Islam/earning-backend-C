"""
Backup Module Exceptions
Custom exception classes for backup operations
"""

from django.utils.translation import gettext_lazy as _


class BackupException(Exception):
    """Base exception class for all backup-related errors"""
    
    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self):
        return self.message


class BackupFailedException(BackupException):
    """Exception raised when backup operation fails"""
    
    def __init__(self, message, backup_id=None, stage=None, details=None):
        super().__init__(message, error_code='BACKUP_FAILED', details=details)
        self.backup_id = backup_id
        self.stage = stage
    
    def __str__(self):
        base_msg = self.message
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        if self.stage:
            base_msg += f" (Stage: {self.stage})"
        return base_msg


class RestoreFailedException(BackupException):
    """Exception raised when restore operation fails"""
    
    def __init__(self, message, backup_id=None, restoration_id=None, stage=None, details=None):
        super().__init__(message, error_code='RESTORE_FAILED', details=details)
        self.backup_id = backup_id
        self.restoration_id = restoration_id
        self.stage = stage
    
    def __str__(self):
        base_msg = self.message
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        if self.restoration_id:
            base_msg += f" (Restoration ID: {self.restoration_id})"
        if self.stage:
            base_msg += f" (Stage: {self.stage})"
        return base_msg


class StorageUnavailableException(BackupException):
    """Exception raised when storage backend is unavailable"""
    
    def __init__(self, message, storage_type=None, storage_location=None, details=None):
        super().__init__(message, error_code='STORAGE_UNAVAILABLE', details=details)
        self.storage_type = storage_type
        self.storage_location = storage_location
    
    def __str__(self):
        base_msg = self.message
        if self.storage_type:
            base_msg += f" (Storage Type: {self.storage_type})"
        if self.storage_location:
            base_msg += f" (Location: {self.storage_location})"
        return base_msg


class BackupCorruptedException(BackupException):
    """Exception raised when backup file is corrupted"""
    
    def __init__(self, message, backup_id=None, file_path=None, corruption_type=None, details=None):
        super().__init__(message, error_code='BACKUP_CORRUPTED', details=details)
        self.backup_id = backup_id
        self.file_path = file_path
        self.corruption_type = corruption_type
    
    def __str__(self):
        base_msg = self.message
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        if self.file_path:
            base_msg += f" (File: {self.file_path})"
        if self.corruption_type:
            base_msg += f" (Type: {self.corruption_type})"
        return base_msg


class RetentionPolicyViolation(BackupException):
    """Exception raised when retention policy is violated"""
    
    def __init__(self, message, policy_name=None, violation_type=None, details=None):
        super().__init__(message, error_code='RETENTION_POLICY_VIOLATION', details=details)
        self.policy_name = policy_name
        self.violation_type = violation_type
    
    def __str__(self):
        base_msg = self.message
        if self.policy_name:
            base_msg += f" (Policy: {self.policy_name})"
        if self.violation_type:
            base_msg += f" (Violation: {self.violation_type})"
        return base_msg


class DatabaseConnectionException(BackupException):
    """Exception raised when database connection fails"""
    
    def __init__(self, message, database_name=None, engine=None, host=None, details=None):
        super().__init__(message, error_code='DATABASE_CONNECTION_FAILED', details=details)
        self.database_name = database_name
        self.engine = engine
        self.host = host
    
    def __str__(self):
        base_msg = self.message
        if self.database_name:
            base_msg += f" (Database: {self.database_name})"
        if self.engine:
            base_msg += f" (Engine: {self.engine})"
        if self.host:
            base_msg += f" (Host: {self.host})"
        return base_msg


class BackupSizeExceededException(BackupException):
    """Exception raised when backup size exceeds limits"""
    
    def __init__(self, message, backup_size=None, max_size=None, backup_id=None, details=None):
        super().__init__(message, error_code='BACKUP_SIZE_EXCEEDED', details=details)
        self.backup_size = backup_size
        self.max_size = max_size
        self.backup_id = backup_id
    
    def __str__(self):
        base_msg = self.message
        if self.backup_size and self.max_size:
            base_msg += f" (Size: {self.backup_size} > Limit: {self.max_size})"
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        return base_msg


class BackupTimeoutException(BackupException):
    """Exception raised when backup operation times out"""
    
    def __init__(self, message, timeout_seconds=None, elapsed_seconds=None, operation=None, details=None):
        super().__init__(message, error_code='BACKUP_TIMEOUT', details=details)
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.timeout_seconds:
            base_msg += f" (Timeout: {self.timeout_seconds}s)"
        if self.elapsed_seconds:
            base_msg += f" (Elapsed: {self.elapsed_seconds}s)"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class EncryptionException(BackupException):
    """Exception raised during encryption/decryption operations"""
    
    def __init__(self, message, algorithm=None, operation=None, details=None):
        super().__init__(message, error_code='ENCRYPTION_ERROR', details=details)
        self.algorithm = algorithm
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.algorithm:
            base_msg += f" (Algorithm: {self.algorithm})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class CompressionException(BackupException):
    """Exception raised during compression/decompression operations"""
    
    def __init__(self, message, algorithm=None, operation=None, details=None):
        super().__init__(message, error_code='COMPRESSION_ERROR', details=details)
        self.algorithm = algorithm
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.algorithm:
            base_msg += f" (Algorithm: {self.algorithm})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class VerificationException(BackupException):
    """Exception raised during backup verification"""
    
    def __init__(self, message, verification_method=None, backup_id=None, details=None):
        super().__init__(message, error_code='VERIFICATION_FAILED', details=details)
        self.verification_method = verification_method
        self.backup_id = backup_id
    
    def __str__(self):
        base_msg = self.message
        if self.verification_method:
            base_msg += f" (Method: {self.verification_method})"
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        return base_msg


class ScheduleConflictException(BackupException):
    """Exception raised when backup schedule conflicts occur"""
    
    def __init__(self, message, schedule_id=None, conflict_type=None, details=None):
        super().__init__(message, error_code='SCHEDULE_CONFLICT', details=details)
        self.schedule_id = schedule_id
        self.conflict_type = conflict_type
    
    def __str__(self):
        base_msg = self.message
        if self.schedule_id:
            base_msg += f" (Schedule ID: {self.schedule_id})"
        if self.conflict_type:
            base_msg += f" (Conflict: {self.conflict_type})"
        return base_msg


class InsufficientPermissionsException(BackupException):
    """Exception raised when user lacks required permissions"""
    
    def __init__(self, message, user_id=None, required_permission=None, resource=None, details=None):
        super().__init__(message, error_code='INSUFFICIENT_PERMISSIONS', details=details)
        self.user_id = user_id
        self.required_permission = required_permission
        self.resource = resource
    
    def __str__(self):
        base_msg = self.message
        if self.user_id:
            base_msg += f" (User ID: {self.user_id})"
        if self.required_permission:
            base_msg += f" (Required: {self.required_permission})"
        if self.resource:
            base_msg += f" (Resource: {self.resource})"
        return base_msg


class BackupLockException(BackupException):
    """Exception raised when backup is locked by another operation"""
    
    def __init__(self, message, backup_id=None, lock_owner=None, lock_time=None, details=None):
        super().__init__(message, error_code='BACKUP_LOCKED', details=details)
        self.backup_id = backup_id
        self.lock_owner = lock_owner
        self.lock_time = lock_time
    
    def __str__(self):
        base_msg = self.message
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        if self.lock_owner:
            base_msg += f" (Owner: {self.lock_owner})"
        if self.lock_time:
            base_msg += f" (Locked: {self.lock_time})"
        return base_msg


class ResourceExhaustedException(BackupException):
    """Exception raised when system resources are exhausted"""
    
    def __init__(self, message, resource_type=None, current_usage=None, limit=None, details=None):
        super().__init__(message, error_code='RESOURCE_EXHAUSTED', details=details)
        self.resource_type = resource_type
        self.current_usage = current_usage
        self.limit = limit
    
    def __str__(self):
        base_msg = self.message
        if self.resource_type:
            base_msg += f" (Resource: {self.resource_type})"
        if self.current_usage and self.limit:
            base_msg += f" (Usage: {self.current_usage}/{self.limit})"
        return base_msg


class ConfigurationException(BackupException):
    """Exception raised when backup configuration is invalid"""
    
    def __init__(self, message, config_key=None, config_value=None, validation_error=None, details=None):
        super().__init__(message, error_code='CONFIGURATION_ERROR', details=details)
        self.config_key = config_key
        self.config_value = config_value
        self.validation_error = validation_error
    
    def __str__(self):
        base_msg = self.message
        if self.config_key:
            base_msg += f" (Config: {self.config_key})"
        if self.config_value:
            base_msg += f" (Value: {self.config_value})"
        if self.validation_error:
            base_msg += f" (Error: {self.validation_error})"
        return base_msg


class NotificationException(BackupException):
    """Exception raised when notification sending fails"""
    
    def __init__(self, message, channel=None, recipient=None, details=None):
        super().__init__(message, error_code='NOTIFICATION_FAILED', details=details)
        self.channel = channel
        self.recipient = recipient
    
    def __str__(self):
        base_msg = self.message
        if self.channel:
            base_msg += f" (Channel: {self.channel})"
        if self.recipient:
            base_msg += f" (Recipient: {self.recipient})"
        return base_msg


class ValidationException(BackupException):
    """Exception raised during data validation"""
    
    def __init__(self, message, field=None, value=None, validation_rule=None, details=None):
        super().__init__(message, error_code='VALIDATION_ERROR', details=details)
        self.field = field
        self.value = value
        self.validation_rule = validation_rule
    
    def __str__(self):
        base_msg = self.message
        if self.field:
            base_msg += f" (Field: {self.field})"
        if self.value:
            base_msg += f" (Value: {self.value})"
        if self.validation_rule:
            base_msg += f" (Rule: {self.validation_rule})"
        return base_msg


class ConcurrentOperationException(BackupException):
    """Exception raised when concurrent operations conflict"""
    
    def __init__(self, message, operation_type=None, conflicting_operation=None, details=None):
        super().__init__(message, error_code='CONCURRENT_OPERATION', details=details)
        self.operation_type = operation_type
        self.conflicting_operation = conflicting_operation
    
    def __str__(self):
        base_msg = self.message
        if self.operation_type:
            base_msg += f" (Operation: {self.operation_type})"
        if self.conflicting_operation:
            base_msg += f" (Conflicting: {self.conflicting_operation})"
        return base_msg


class ServiceUnavailableException(BackupException):
    """Exception raised when a required service is unavailable"""
    
    def __init__(self, message, service_name=None, service_type=None, details=None):
        super().__init__(message, error_code='SERVICE_UNAVAILABLE', details=details)
        self.service_name = service_name
        self.service_type = service_type
    
    def __str__(self):
        base_msg = self.message
        if self.service_name:
            base_msg += f" (Service: {self.service_name})"
        if self.service_type:
            base_msg += f" (Type: {self.service_type})"
        return base_msg


class BackupStateException(BackupException):
    """Exception raised when backup is in invalid state for operation"""
    
    def __init__(self, message, current_state=None, required_state=None, backup_id=None, details=None):
        super().__init__(message, error_code='INVALID_STATE', details=details)
        self.current_state = current_state
        self.required_state = required_state
        self.backup_id = backup_id
    
    def __str__(self):
        base_msg = self.message
        if self.current_state and self.required_state:
            base_msg += f" (State: {self.current_state} -> Required: {self.required_state})"
        if self.backup_id:
            base_msg += f" (Backup ID: {self.backup_id})"
        return base_msg


# Exception mapping for error codes
EXCEPTION_MAP = {
    'BACKUP_FAILED': BackupFailedException,
    'RESTORE_FAILED': RestoreFailedException,
    'STORAGE_UNAVAILABLE': StorageUnavailableException,
    'BACKUP_CORRUPTED': BackupCorruptedException,
    'RETENTION_POLICY_VIOLATION': RetentionPolicyViolation,
    'DATABASE_CONNECTION_FAILED': DatabaseConnectionException,
    'BACKUP_SIZE_EXCEEDED': BackupSizeExceededException,
    'BACKUP_TIMEOUT': BackupTimeoutException,
    'ENCRYPTION_ERROR': EncryptionException,
    'COMPRESSION_ERROR': CompressionException,
    'VERIFICATION_FAILED': VerificationException,
    'SCHEDULE_CONFLICT': ScheduleConflictException,
    'INSUFFICIENT_PERMISSIONS': InsufficientPermissionsException,
    'BACKUP_LOCKED': BackupLockException,
    'RESOURCE_EXHAUSTED': ResourceExhaustedException,
    'CONFIGURATION_ERROR': ConfigurationException,
    'NOTIFICATION_FAILED': NotificationException,
    'VALIDATION_ERROR': ValidationException,
    'CONCURRENT_OPERATION': ConcurrentOperationException,
    'SERVICE_UNAVAILABLE': ServiceUnavailableException,
    'INVALID_STATE': BackupStateException,
}


def get_exception_class(error_code):
    """Get exception class by error code"""
    return EXCEPTION_MAP.get(error_code, BackupException)


def create_exception(error_code, message, **kwargs):
    """Create exception instance by error code"""
    exception_class = get_exception_class(error_code)
    return exception_class(message, **kwargs)


# Additional exception classes for comprehensive coverage
class KeyRotationException(BackupException):
    """Exception raised during encryption key rotation"""
    
    def __init__(self, message, key_id=None, rotation_stage=None, details=None):
        super().__init__(message, error_code='KEY_ROTATION_FAILED', details=details)
        self.key_id = key_id
        self.rotation_stage = rotation_stage
    
    def __str__(self):
        base_msg = self.message
        if self.key_id:
            base_msg += f" (Key ID: {self.key_id})"
        if self.rotation_stage:
            base_msg += f" (Stage: {self.rotation_stage})"
        return base_msg


class AnalyticsException(BackupException):
    """Exception raised during analytics processing"""
    
    def __init__(self, message, analytics_type=None, time_range=None, details=None):
        super().__init__(message, error_code='ANALYTICS_ERROR', details=details)
        self.analytics_type = analytics_type
        self.time_range = time_range
    
    def __str__(self):
        base_msg = self.message
        if self.analytics_type:
            base_msg += f" (Type: {self.analytics_type})"
        if self.time_range:
            base_msg += f" (Range: {self.time_range})"
        return base_msg


class MonitoringException(BackupException):
    """Exception raised during monitoring operations"""
    
    def __init__(self, message, monitor_type=None, check_name=None, details=None):
        super().__init__(message, error_code='MONITORING_ERROR', details=details)
        self.monitor_type = monitor_type
        self.check_name = check_name
    
    def __str__(self):
        base_msg = self.message
        if self.monitor_type:
            base_msg += f" (Type: {self.monitor_type})"
        if self.check_name:
            base_msg += f" (Check: {self.check_name})"
        return base_msg


class ComplianceException(BackupException):
    """Exception raised when compliance requirements are not met"""
    
    def __init__(self, message, compliance_type=None, requirement=None, details=None):
        super().__init__(message, error_code='COMPLIANCE_VIOLATION', details=details)
        self.compliance_type = compliance_type
        self.requirement = requirement
    
    def __str__(self):
        base_msg = self.message
        if self.compliance_type:
            base_msg += f" (Type: {self.compliance_type})"
        if self.requirement:
            base_msg += f" (Requirement: {self.requirement})"
        return base_msg


class PerformanceException(BackupException):
    """Exception raised when performance thresholds are exceeded"""
    
    def __init__(self, message, metric=None, threshold=None, actual_value=None, details=None):
        super().__init__(message, error_code='PERFORMANCE_THRESHOLD_EXCEEDED', details=details)
        self.metric = metric
        self.threshold = threshold
        self.actual_value = actual_value
    
    def __str__(self):
        base_msg = self.message
        if self.metric:
            base_msg += f" (Metric: {self.metric})"
        if self.threshold and self.actual_value:
            base_msg += f" (Threshold: {self.threshold}, Actual: {self.actual_value})"
        return base_msg


class CacheException(BackupException):
    """Exception raised during caching operations"""
    
    def __init__(self, message, cache_key=None, operation=None, details=None):
        super().__init__(message, error_code='CACHE_ERROR', details=details)
        self.cache_key = cache_key
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.cache_key:
            base_msg += f" (Key: {self.cache_key})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class WebhookException(BackupException):
    """Exception raised during webhook operations"""
    
    def __init__(self, message, webhook_url=None, http_status=None, details=None):
        super().__init__(message, error_code='WEBHOOK_ERROR', details=details)
        self.webhook_url = webhook_url
        self.http_status = http_status
    
    def __str__(self):
        base_msg = self.message
        if self.webhook_url:
            base_msg += f" (URL: {self.webhook_url})"
        if self.http_status:
            base_msg += f" (Status: {self.http_status})"
        return base_msg


class ImportExportException(BackupException):
    """Exception raised during import/export operations"""
    
    def __init__(self, message, operation=None, file_format=None, details=None):
        super().__init__(message, error_code='IMPORT_EXPORT_ERROR', details=details)
        self.operation = operation
        self.file_format = file_format
    
    def __str__(self):
        base_msg = self.message
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        if self.file_format:
            base_msg += f" (Format: {self.file_format})"
        return base_msg


class ThrottlingException(BackupException):
    """Exception raised when rate limits are exceeded"""
    
    def __init__(self, message, limit_type=None, limit_value=None, retry_after=None, details=None):
        super().__init__(message, error_code='RATE_LIMIT_EXCEEDED', details=details)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.retry_after = retry_after
    
    def __str__(self):
        base_msg = self.message
        if self.limit_type:
            base_msg += f" (Type: {self.limit_type})"
        if self.limit_value:
            base_msg += f" (Limit: {self.limit_value})"
        if self.retry_after:
            base_msg += f" (Retry After: {self.retry_after}s)"
        return base_msg


class PluginException(BackupException):
    """Exception raised during plugin operations"""
    
    def __init__(self, message, plugin_name=None, plugin_version=None, details=None):
        super().__init__(message, error_code='PLUGIN_ERROR', details=details)
        self.plugin_name = plugin_name
        self.plugin_version = plugin_version
    
    def __str__(self):
        base_msg = self.message
        if self.plugin_name:
            base_msg += f" (Plugin: {self.plugin_name})"
        if self.plugin_version:
            base_msg += f" (Version: {self.plugin_version})"
        return base_msg


class TaskExecutionException(BackupException):
    """Exception raised during task execution"""
    
    def __init__(self, message, task_name=None, task_id=None, worker=None, details=None):
        super().__init__(message, error_code='TASK_EXECUTION_ERROR', details=details)
        self.task_name = task_name
        self.task_id = task_id
        self.worker = worker
    
    def __str__(self):
        base_msg = self.message
        if self.task_name:
            base_msg += f" (Task: {self.task_name})"
        if self.task_id:
            base_msg += f" (ID: {self.task_id})"
        if self.worker:
            base_msg += f" (Worker: {self.worker})"
        return base_msg


class FeatureFlagException(BackupException):
    """Exception raised during feature flag operations"""
    
    def __init__(self, message, flag_name=None, flag_value=None, details=None):
        super().__init__(message, error_code='FEATURE_FLAG_ERROR', details=details)
        self.flag_name = flag_name
        self.flag_value = flag_value
    
    def __str__(self):
        base_msg = self.message
        if self.flag_name:
            base_msg += f" (Flag: {self.flag_name})"
        if self.flag_value:
            base_msg += f" (Value: {self.flag_value})"
        return base_msg


class RegistryException(BackupException):
    """Exception raised during registry operations"""
    
    def __init__(self, message, registry_type=None, key=None, operation=None, details=None):
        super().__init__(message, error_code='REGISTRY_ERROR', details=details)
        self.registry_type = registry_type
        self.key = key
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.registry_type:
            base_msg += f" (Type: {self.registry_type})"
        if self.key:
            base_msg += f" (Key: {self.key})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class QuerySetException(BackupException):
    """Exception raised during QuerySet operations"""
    
    def __init__(self, message, model=None, query_type=None, details=None):
        super().__init__(message, error_code='QUERYSET_ERROR', details=details)
        self.model = model
        self.query_type = query_type
    
    def __str__(self):
        base_msg = self.message
        if self.model:
            base_msg += f" (Model: {self.model})"
        if self.query_type:
            base_msg += f" (Query: {self.query_type})"
        return base_msg


class RepositoryException(BackupException):
    """Exception raised during repository operations"""
    
    def __init__(self, message, repository_type=None, operation=None, details=None):
        super().__init__(message, error_code='REPOSITORY_ERROR', details=details)
        self.repository_type = repository_type
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.repository_type:
            base_msg += f" (Repository: {self.repository_type})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class InteractorException(BackupException):
    """Exception raised during interactor operations"""
    
    def __init__(self, message, interactor_name=None, use_case=None, details=None):
        super().__init__(message, error_code='INTERACTOR_ERROR', details=details)
        self.interactor_name = interactor_name
        self.use_case = use_case
    
    def __str__(self):
        base_msg = self.message
        if self.interactor_name:
            base_msg += f" (Interactor: {self.interactor_name})"
        if self.use_case:
            base_msg += f" (Use Case: {self.use_case})"
        return base_msg


class SelectorException(BackupException):
    """Exception raised during selector operations"""
    
    def __init__(self, message, selector_name=None, criteria=None, details=None):
        super().__init__(message, error_code='SELECTOR_ERROR', details=details)
        self.selector_name = selector_name
        self.criteria = criteria
    
    def __str__(self):
        base_msg = self.message
        if self.selector_name:
            base_msg += f" (Selector: {self.selector_name})"
        if self.criteria:
            base_msg += f" (Criteria: {self.criteria})"
        return base_msg


class UseCaseException(BackupException):
    """Exception raised during use case operations"""
    
    def __init__(self, message, use_case_name=None, actor=None, details=None):
        super().__init__(message, error_code='USE_CASE_ERROR', details=details)
        self.use_case_name = use_case_name
        self.actor = actor
    
    def __str__(self):
        base_msg = self.message
        if self.use_case_name:
            base_msg += f" (Use Case: {self.use_case_name})"
        if self.actor:
            base_msg += f" (Actor: {self.actor})"
        return base_msg


class MiddlewareException(BackupException):
    """Exception raised during middleware operations"""
    
    def __init__(self, message, middleware_name=None, request_path=None, details=None):
        super().__init__(message, error_code='MIDDLEWARE_ERROR', details=details)
        self.middleware_name = middleware_name
        self.request_path = request_path
    
    def __str__(self):
        base_msg = self.message
        if self.middleware_name:
            base_msg += f" (Middleware: {self.middleware_name})"
        if self.request_path:
            base_msg += f" (Path: {self.request_path})"
        return base_msg


class PermissionException(BackupException):
    """Exception raised during permission checks"""
    
    def __init__(self, message, permission_name=None, user_id=None, resource=None, details=None):
        super().__init__(message, error_code='PERMISSION_DENIED', details=details)
        self.permission_name = permission_name
        self.user_id = user_id
        self.resource = resource
    
    def __str__(self):
        base_msg = self.message
        if self.permission_name:
            base_msg += f" (Permission: {self.permission_name})"
        if self.user_id:
            base_msg += f" (User ID: {self.user_id})"
        if self.resource:
            base_msg += f" (Resource: {self.resource})"
        return base_msg


class PaginationException(BackupException):
    """Exception raised during pagination operations"""
    
    def __init__(self, message, page_number=None, page_size=None, total_items=None, details=None):
        super().__init__(message, error_code='PAGINATION_ERROR', details=details)
        self.page_number = page_number
        self.page_size = page_size
        self.total_items = total_items
    
    def __str__(self):
        base_msg = self.message
        if self.page_number:
            base_msg += f" (Page: {self.page_number})"
        if self.page_size:
            base_msg += f" (Size: {self.page_size})"
        if self.total_items:
            base_msg += f" (Total: {self.total_items})"
        return base_msg


class FilterException(BackupException):
    """Exception raised during filtering operations"""
    
    def __init__(self, message, filter_name=None, filter_value=None, details=None):
        super().__init__(message, error_code='FILTER_ERROR', details=details)
        self.filter_name = filter_name
        self.filter_value = filter_value
    
    def __str__(self):
        base_msg = self.message
        if self.filter_name:
            base_msg += f" (Filter: {self.filter_name})"
        if self.filter_value:
            base_msg += f" (Value: {self.filter_value})"
        return base_msg


class DecoratorException(BackupException):
    """Exception raised during decorator operations"""
    
    def __init__(self, message, decorator_name=None, function_name=None, details=None):
        super().__init__(message, error_code='DECORATOR_ERROR', details=details)
        self.decorator_name = decorator_name
        self.function_name = function_name
    
    def __str__(self):
        base_msg = self.message
        if self.decorator_name:
            base_msg += f" (Decorator: {self.decorator_name})"
        if self.function_name:
            base_msg += f" (Function: {self.function_name})"
        return base_msg


class ManagerException(BackupException):
    """Exception raised during manager operations"""
    
    def __init__(self, message, manager_name=None, model=None, operation=None, details=None):
        super().__init__(message, error_code='MANAGER_ERROR', details=details)
        self.manager_name = manager_name
        self.model = model
        self.operation = operation
    
    def __str__(self):
        base_msg = self.message
        if self.manager_name:
            base_msg += f" (Manager: {self.manager_name})"
        if self.model:
            base_msg += f" (Model: {self.model})"
        if self.operation:
            base_msg += f" (Operation: {self.operation})"
        return base_msg


class ConsumerException(BackupException):
    """Exception raised during consumer operations"""
    
    def __init__(self, message, consumer_name=None, channel=None, details=None):
        super().__init__(message, error_code='CONSUMER_ERROR', details=details)
        self.consumer_name = consumer_name
        self.channel = channel
    
    def __str__(self):
        base_msg = self.message
        if self.consumer_name:
            base_msg += f" (Consumer: {self.consumer_name})"
        if self.channel:
            base_msg += f" (Channel: {self.channel})"
        return base_msg


class DependencyException(BackupException):
    """Exception raised during dependency resolution"""
    
    def __init__(self, message, dependency_name=None, version=None, details=None):
        super().__init__(message, error_code='DEPENDENCY_ERROR', details=details)
        self.dependency_name = dependency_name
        self.version = version
    
    def __str__(self):
        base_msg = self.message
        if self.dependency_name:
            base_msg += f" (Dependency: {self.dependency_name})"
        if self.version:
            base_msg += f" (Version: {self.version})"
        return base_msg


class ReceiverException(BackupException):
    """Exception raised during signal receiver operations"""
    
    def __init__(self, message, signal_name=None, sender=None, details=None):
        super().__init__(message, error_code='RECEIVER_ERROR', details=details)
        self.signal_name = signal_name
        self.sender = sender
    
    def __str__(self):
        base_msg = self.message
        if self.signal_name:
            base_msg += f" (Signal: {self.signal_name})"
        if self.sender:
            base_msg += f" (Sender: {self.sender})"
        return base_msg


class AttachmentException(BackupException):
    """Exception raised during attachment operations"""
    
    def __init__(self, message, attachment_name=None, file_size=None, mime_type=None, details=None):
        super().__init__(message, error_code='ATTACHMENT_ERROR', details=details)
        self.attachment_name = attachment_name
        self.file_size = file_size
        self.mime_type = mime_type
    
    def __str__(self):
        base_msg = self.message
        if self.attachment_name:
            base_msg += f" (Attachment: {self.attachment_name})"
        if self.file_size:
            base_msg += f" (Size: {self.file_size})"
        if self.mime_type:
            base_msg += f" (MIME: {self.mime_type})"
        return base_msg


class CeleryBeatException(BackupException):
    """Exception raised during Celery Beat operations"""
    
    def __init__(self, message, task_name=None, schedule=None, details=None):
        super().__init__(message, error_code='CELERY_BEAT_ERROR', details=details)
        self.task_name = task_name
        self.schedule = schedule
    
    def __str__(self):
        base_msg = self.message
        if self.task_name:
            base_msg += f" (Task: {self.task_name})"
        if self.schedule:
            base_msg += f" (Schedule: {self.schedule})"
        return base_msg


# Update exception mapping with new exceptions
EXCEPTION_MAP.update({
    'KEY_ROTATION_FAILED': KeyRotationException,
    'ANALYTICS_ERROR': AnalyticsException,
    'MONITORING_ERROR': MonitoringException,
    'COMPLIANCE_VIOLATION': ComplianceException,
    'PERFORMANCE_THRESHOLD_EXCEEDED': PerformanceException,
    'CACHE_ERROR': CacheException,
    'WEBHOOK_ERROR': WebhookException,
    'IMPORT_EXPORT_ERROR': ImportExportException,
    'RATE_LIMIT_EXCEEDED': ThrottlingException,
    'PLUGIN_ERROR': PluginException,
    'TASK_EXECUTION_ERROR': TaskExecutionException,
    'FEATURE_FLAG_ERROR': FeatureFlagException,
    'REGISTRY_ERROR': RegistryException,
    'QUERYSET_ERROR': QuerySetException,
    'REPOSITORY_ERROR': RepositoryException,
    'INTERACTOR_ERROR': InteractorException,
    'SELECTOR_ERROR': SelectorException,
    'USE_CASE_ERROR': UseCaseException,
    'MIDDLEWARE_ERROR': MiddlewareException,
    'PERMISSION_DENIED': PermissionException,
    'PAGINATION_ERROR': PaginationException,
    'FILTER_ERROR': FilterException,
    'DECORATOR_ERROR': DecoratorException,
    'MANAGER_ERROR': ManagerException,
    'CONSUMER_ERROR': ConsumerException,
    'DEPENDENCY_ERROR': DependencyException,
    'RECEIVER_ERROR': ReceiverException,
    'ATTACHMENT_ERROR': AttachmentException,
    'CELERY_BEAT_ERROR': CeleryBeatException,
})
