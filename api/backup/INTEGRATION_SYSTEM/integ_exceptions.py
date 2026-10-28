"""
Integration Exceptions
Comprehensive exception hierarchy for integration system
"""
from typing import Callable

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class IntegrationException(Exception):
    """
    Base exception for all integration-related errors
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None, 
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'cause': str(self.cause) if self.cause else None
        }


class ConfigurationException(IntegrationException):
    """Exception for configuration-related errors"""
    pass


class AdapterException(IntegrationException):
    """Exception for adapter-related errors"""
    pass


class RegistryException(IntegrationException):
    """Exception for registry-related errors"""
    pass


class BridgeException(IntegrationException):
    """Exception for bridge-related errors"""
    pass


class EventBusException(IntegrationException):
    """Exception for event bus-related errors"""
    pass


class WebhookException(IntegrationException):
    """Exception for webhook-related errors"""
    pass


class DataBridgeException(IntegrationException):
    """Exception for data bridge-related errors"""
    pass


class DataValidationException(IntegrationException):
    """Exception for data validation errors"""
    pass


class FallbackException(IntegrationException):
    """Exception for fallback logic errors"""
    pass


class AuthBridgeException(IntegrationException):
    """Exception for authentication bridge errors"""
    pass


class PerformanceMonitorException(IntegrationException):
    """Exception for performance monitoring errors"""
    pass


class AuditLogException(IntegrationException):
    """Exception for audit logging errors"""
    pass


class HealthCheckException(IntegrationException):
    """Exception for health check errors"""
    pass


class SyncManagerException(IntegrationException):
    """Exception for sync manager errors"""
    pass


class CircuitBreakerException(IntegrationException):
    """Exception for circuit breaker errors"""
    pass


class RetryException(IntegrationException):
    """Exception for retry mechanism errors"""
    pass


class TimeoutException(IntegrationException):
    """Exception for timeout errors"""
    pass


class ConnectionException(IntegrationException):
    """Exception for connection errors"""
    pass


class AuthenticationException(IntegrationException):
    """Exception for authentication errors"""
    pass


class AuthorizationException(IntegrationException):
    """Exception for authorization errors"""
    pass


class RateLimitException(IntegrationException):
    """Exception for rate limiting errors"""
    pass


class ValidationException(IntegrationException):
    """Exception for validation errors"""
    pass


class TransformationException(IntegrationException):
    """Exception for data transformation errors"""
    pass


class SerializationException(IntegrationException):
    """Exception for serialization errors"""
    pass


class DeserializationException(IntegrationException):
    """Exception for deserialization errors"""
    pass


class EncryptionException(IntegrationException):
    """Exception for encryption errors"""
    pass


class DecryptionException(IntegrationException):
    """Exception for decryption errors"""
    pass


class CompressionException(IntegrationException):
    """Exception for compression errors"""
    pass


class DecompressionException(IntegrationException):
    """Exception for decompression errors"""
    pass


class StorageException(IntegrationException):
    """Exception for storage errors"""
    pass


class NetworkException(IntegrationException):
    """Exception for network errors"""
    pass


class ProtocolException(IntegrationException):
    """Exception for protocol errors"""
    pass


class FormatException(IntegrationException):
    """Exception for format errors"""
    pass


class SchemaException(IntegrationException):
    """Exception for schema errors"""
    pass


class MappingException(IntegrationException):
    """Exception for mapping errors"""
    pass


class FilterException(IntegrationException):
    """Exception for filtering errors"""
    pass


class RoutingException(IntegrationException):
    """Exception for routing errors"""
    pass


class AggregationException(IntegrationException):
    """Exception for aggregation errors"""
    pass


class SplitException(IntegrationException):
    """Exception for splitting errors"""
    pass


class MergeException(IntegrationException):
    """Exception for merging errors"""
    pass


class DuplicateException(IntegrationException):
    """Exception for duplicate errors"""
    pass


class ConflictException(IntegrationException):
    """Exception for conflict errors"""
    pass


class ConsistencyException(IntegrationException):
    """Exception for consistency errors"""
    pass


class IntegrityException(IntegrationException):
    """Exception for integrity errors"""
    pass


class CorrelationException(IntegrationException):
    """Exception for correlation errors"""
    pass


class OrphanException(IntegrationException):
    """Exception for orphan errors"""
    pass


class DependencyException(IntegrationException):
    """Exception for dependency errors"""
    pass


class VersionException(IntegrationException):
    """Exception for version errors"""
    pass


class CompatibilityException(IntegrationException):
    """Exception for compatibility errors"""
    pass


class MigrationException(IntegrationException):
    """Exception for migration errors"""
    pass


class BackupException(IntegrationException):
    """Exception for backup errors"""
    pass


class RestoreException(IntegrationException):
    """Exception for restore errors"""
    pass


class VerificationException(IntegrationException):
    """Exception for verification errors"""
    pass


class CleanupException(IntegrationException):
    """Exception for cleanup errors"""
    pass


class MaintenanceException(IntegrationException):
    """Exception for maintenance errors"""
    pass


class DeploymentException(IntegrationException):
    """Exception for deployment errors"""
    pass


class ConfigurationException(IntegrationException):
    """Exception for configuration errors"""
    pass


class EnvironmentException(IntegrationException):
    """Exception for environment errors"""
    pass


class ResourceException(IntegrationException):
    """Exception for resource errors"""
    pass


class QuotaException(IntegrationException):
    """Exception for quota errors"""
    pass


class CapacityException(IntegrationException):
    """Exception for capacity errors"""
    pass


class ScalabilityException(IntegrationException):
    """Exception for scalability errors"""
    pass


class AvailabilityException(IntegrationException):
    """Exception for availability errors"""
    pass


class ReliabilityException(IntegrationException):
    """Exception for reliability errors"""
    pass


class PerformanceException(IntegrationException):
    """Exception for performance errors"""
    pass


class LatencyException(IntegrationException):
    """Exception for latency errors"""
    pass


class ThroughputException(IntegrationException):
    """Exception for throughput errors"""
    pass


class MemoryException(IntegrationException):
    """Exception for memory errors"""
    pass


class CPUException(IntegrationException):
    """Exception for CPU errors"""
    pass


class DiskException(IntegrationException):
    """Exception for disk errors"""
    pass


class BandwidthException(IntegrationException):
    """Exception for bandwidth errors"""
    pass


class ConcurrencyException(IntegrationException):
    """Exception for concurrency errors"""
    pass


class ThreadException(IntegrationException):
    """Exception for thread errors"""
    pass


class ProcessException(IntegrationException):
    """Exception for process errors"""
    pass


class DeadlockException(IntegrationException):
    """Exception for deadlock errors"""
    pass


class RaceConditionException(IntegrationException):
    """Exception for race condition errors"""
    pass


class SynchronizationException(IntegrationException):
    """Exception for synchronization errors"""
    pass


class LockException(IntegrationException):
    """Exception for lock errors"""
    pass


class SemaphoreException(IntegrationException):
    """Exception for semaphore errors"""
    pass


class QueueException(IntegrationException):
    """Exception for queue errors"""
    pass


class BufferException(IntegrationException):
    """Exception for buffer errors"""
    pass


class CacheException(IntegrationException):
    """Exception for cache errors"""
    pass


class SessionException(IntegrationException):
    """Exception for session errors"""
    pass


class StateException(IntegrationException):
    """Exception for state errors"""
    pass


class TransactionException(IntegrationException):
    """Exception for transaction errors"""
    pass


class RollbackException(IntegrationException):
    """Exception for rollback errors"""
    pass


class CommitException(IntegrationException):
    """Exception for commit errors"""
    pass


class IsolationException(IntegrationException):
    """Exception for isolation errors"""
    pass


class ACIDException(IntegrationException):
    """Exception for ACID property errors"""
    pass


class ConsistencyException(IntegrationException):
    """Exception for consistency errors"""
    pass


class DurabilityException(IntegrationException):
    """Exception for durability errors"""
    pass


class AtomicityException(IntegrationException):
    """Exception for atomicity errors"""
    pass


@dataclass
class ErrorContext:
    """Error context for detailed error reporting"""
    system: str
    component: str
    operation: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    tenant_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            'system': self.system,
            'component': self.component,
            'operation': self.operation,
            'user_id': self.user_id,
            'request_id': self.request_id,
            'session_id': self.session_id,
            'tenant_id': self.tenant_id,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ErrorReport:
    """Comprehensive error report"""
    error_id: str
    exception: IntegrationException
    context: ErrorContext
    stack_trace: List[str] = field(default_factory=list)
    severity: str = "error"
    category: str = "integration"
    tags: List[str] = field(default_factory=list)
    resolved: bool = False
    resolution_notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary"""
        return {
            'error_id': self.error_id,
            'exception': self.exception.to_dict(),
            'context': self.context.to_dict(),
            'stack_trace': self.stack_trace,
            'severity': self.severity,
            'category': self.category,
            'tags': self.tags,
            'resolved': self.resolved,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class ExceptionHandler:
    """
    Central exception handler for the integration system
    """
    
    def __init__(self):
        self.error_reports: Dict[str, ErrorReport] = {}
        self.error_handlers: Dict[type, Callable] = {}
        self.error_stats = {
            'total_errors': 0,
            'errors_by_type': {},
            'errors_by_severity': {},
            'resolved_errors': 0,
            'unresolved_errors': 0
        }
    
    def handle_exception(self, exception: IntegrationException, 
                        context: ErrorContext, 
                        stack_trace: Optional[List[str]] = None) -> ErrorReport:
        """
        Handle an exception and create an error report
        
        Args:
            exception: The exception to handle
            context: Error context
            stack_trace: Stack trace (optional)
            
        Returns:
            Error report
        """
        import uuid
        
        error_id = str(uuid.uuid4())
        
        # Create error report
        report = ErrorReport(
            error_id=error_id,
            exception=exception,
            context=context,
            stack_trace=stack_trace or [],
            severity=self._determine_severity(exception),
            category=self._determine_category(exception),
            tags=self._generate_tags(exception, context)
        )
        
        # Store report
        self.error_reports[error_id] = report
        
        # Update statistics
        self._update_stats(exception, report)
        
        # Log the error
        logger.error(f"Integration error: {exception.message}", extra={
            'error_id': error_id,
            'error_type': exception.__class__.__name__,
            'context': context.to_dict()
        })
        
        # Call custom handler if available
        handler = self.error_handlers.get(type(exception))
        if handler:
            try:
                handler(exception, context, report)
            except Exception as e:
                logger.error(f"Error in custom exception handler: {e}")
        
        return report
    
    def register_handler(self, exception_type: type, handler: Callable):
        """Register a custom exception handler"""
        self.error_handlers[exception_type] = handler
    
    def get_error_report(self, error_id: str) -> Optional[ErrorReport]:
        """Get error report by ID"""
        return self.error_reports.get(error_id)
    
    def list_error_reports(self, resolved: Optional[bool] = None, 
                          severity: Optional[str] = None,
                          category: Optional[str] = None,
                          limit: int = 100) -> List[ErrorReport]:
        """List error reports with filters"""
        reports = list(self.error_reports.values())
        
        # Apply filters
        if resolved is not None:
            reports = [r for r in reports if r.resolved == resolved]
        
        if severity:
            reports = [r for r in reports if r.severity == severity]
        
        if category:
            reports = [r for r in reports if r.category == category]
        
        # Sort by created date (newest first) and limit
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    def resolve_error(self, error_id: str, resolution_notes: Optional[str] = None) -> bool:
        """Resolve an error report"""
        report = self.error_reports.get(error_id)
        if not report:
            return False
        
        report.resolved = True
        report.resolution_notes = resolution_notes
        report.resolved_at = datetime.utcnow()
        
        # Update statistics
        self.error_stats['resolved_errors'] += 1
        self.error_stats['unresolved_errors'] -= 1
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        return self.error_stats.copy()
    
    def _determine_severity(self, exception: IntegrationException) -> str:
        """Determine error severity based on exception type"""
        severity_mapping = {
            CircuitBreakerException: "critical",
            AuthenticationException: "critical",
            AuthorizationException: "critical",
            SecurityException: "critical",
            DataIntegrityException: "high",
            ConsistencyException: "high",
            ConnectionException: "medium",
            TimeoutException: "medium",
            ValidationException: "low",
            ConfigurationException: "medium"
        }
        
        return severity_mapping.get(type(exception), "medium")
    
    def _determine_category(self, exception: IntegrationException) -> str:
        """Determine error category based on exception type"""
        category_mapping = {
            AdapterException: "adapter",
            BridgeException: "bridge",
            EventBusException: "event_bus",
            WebhookException: "webhook",
            DataBridgeException: "data_bridge",
            DataValidationException: "validation",
            AuthBridgeException: "authentication",
            PerformanceMonitorException: "monitoring",
            AuditLogException: "audit",
            HealthCheckException: "health",
            SyncManagerException: "sync"
        }
        
        return category_mapping.get(type(exception), "integration")
    
    def _generate_tags(self, exception: IntegrationException, 
                      context: ErrorContext) -> List[str]:
        """Generate tags for error categorization"""
        tags = [
            exception.__class__.__name__.lower().replace('exception', ''),
            context.system.lower(),
            context.component.lower(),
            context.operation.lower()
        ]
        
        # Add tenant tag if available
        if context.tenant_id:
            tags.append(f"tenant:{context.tenant_id}")
        
        # Add user tag if available
        if context.user_id:
            tags.append(f"user:{context.user_id}")
        
        return tags
    
    def _update_stats(self, exception: IntegrationException, report: ErrorReport):
        """Update error statistics"""
        self.error_stats['total_errors'] += 1
        self.error_stats['unresolved_errors'] += 1
        
        # Update by type
        exc_type = exception.__class__.__name__
        self.error_stats['errors_by_type'][exc_type] = (
            self.error_stats['errors_by_type'].get(exc_type, 0) + 1
        )
        
        # Update by severity
        self.error_stats['errors_by_severity'][report.severity] = (
            self.error_stats['errors_by_severity'].get(report.severity, 0) + 1
        )


# Global exception handler instance
_exception_handler = None


def get_exception_handler() -> ExceptionHandler:
    """Get the global exception handler instance"""
    global _exception_handler
    if _exception_handler is None:
        _exception_handler = ExceptionHandler()
    return _exception_handler


def initialize_exception_handler() -> ExceptionHandler:
    """Initialize the global exception handler"""
    global _exception_handler
    _exception_handler = ExceptionHandler()
    return _exception_handler


def handle_integration_error(exception: IntegrationException, 
                             system: str, component: str, operation: str,
                             **context_kwargs) -> ErrorReport:
    """
    Convenience function to handle integration errors
    
    Args:
        exception: The exception to handle
        system: System name
        component: Component name
        operation: Operation name
        **context_kwargs: Additional context parameters
        
    Returns:
        Error report
    """
    context = ErrorContext(
        system=system,
        component=component,
        operation=operation,
        **context_kwargs
    )
    
    handler = get_exception_handler()
    return handler.handle_exception(exception, context)


# Export main classes and functions
__all__ = [
    'IntegrationException',
    'ConfigurationException',
    'AdapterException',
    'RegistryException',
    'BridgeException',
    'EventBusException',
    'WebhookException',
    'DataBridgeException',
    'DataValidationException',
    'FallbackException',
    'AuthBridgeException',
    'PerformanceMonitorException',
    'AuditLogException',
    'HealthCheckException',
    'SyncManagerException',
    'CircuitBreakerException',
    'RetryException',
    'TimeoutException',
    'ConnectionException',
    'AuthenticationException',
    'AuthorizationException',
    'RateLimitException',
    'ValidationException',
    'TransformationException',
    'SerializationException',
    'DeserializationException',
    'EncryptionException',
    'DecryptionException',
    'CompressionException',
    'DecompressionException',
    'StorageException',
    'NetworkException',
    'ProtocolException',
    'FormatException',
    'SchemaException',
    'MappingException',
    'FilterException',
    'RoutingException',
    'AggregationException',
    'SplitException',
    'MergeException',
    'DuplicateException',
    'ConflictException',
    'ConsistencyException',
    'IntegrityException',
    'CorrelationException',
    'OrphanException',
    'DependencyException',
    'VersionException',
    'CompatibilityException',
    'MigrationException',
    'BackupException',
    'RestoreException',
    'VerificationException',
    'CleanupException',
    'MaintenanceException',
    'DeploymentException',
    'EnvironmentException',
    'ResourceException',
    'QuotaException',
    'CapacityException',
    'ScalabilityException',
    'AvailabilityException',
    'ReliabilityException',
    'PerformanceException',
    'LatencyException',
    'ThroughputException',
    'MemoryException',
    'CPUException',
    'DiskException',
    'BandwidthException',
    'ConcurrencyException',
    'ThreadException',
    'ProcessException',
    'DeadlockException',
    'RaceConditionException',
    'SynchronizationException',
    'LockException',
    'SemaphoreException',
    'QueueException',
    'BufferException',
    'CacheException',
    'SessionException',
    'StateException',
    'TransactionException',
    'RollbackException',
    'CommitException',
    'IsolationException',
    'ACIDException',
    'DurabilityException',
    'AtomicityException',
    'ErrorContext',
    'ErrorReport',
    'ExceptionHandler',
    'get_exception_handler',
    'initialize_exception_handler',
    'handle_integration_error',
]
