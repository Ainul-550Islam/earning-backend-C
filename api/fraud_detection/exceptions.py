# =============================================================================
# fraud_detection/exceptions.py
# =============================================================================
"""
Fraud Detection Custom Exceptions.

Custom exception classes for fraud detection system with
specific error handling and user-friendly messages.
"""

from __future__ import annotations

from typing import Optional, Dict, Any


class FraudDetectionException(Exception):
    """
    Base exception class for fraud detection errors.
    
    All fraud detection specific exceptions should inherit from this class
    to provide consistent error handling and logging.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details
        }


class UserBannedException(FraudDetectionException):
    """
    Exception raised when a user is banned due to fraud detection.
    
    This exception is raised when automatic or manual ban actions
    are triggered against a user account.
    """
    
    def __init__(self, user_id: int, reason: str, ban_duration: Optional[str] = None,
                 appeal_allowed: bool = True, details: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.reason = reason
        self.ban_duration = ban_duration
        self.appeal_allowed = appeal_allowed
        
        message = f"User {user_id} has been banned: {reason}"
        if ban_duration:
            message += f" (Duration: {ban_duration})"
        
        exception_details = {
            'user_id': user_id,
            'reason': reason,
            'ban_duration': ban_duration,
            'appeal_allowed': appeal_allowed,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='USER_BANNED',
            details=exception_details
        )


class HighRiskActionBlockedException(FraudDetectionException):
    """
    Exception raised when high-risk actions are blocked.
    
    This exception is raised when the fraud detection system blocks
    an action due to high risk scores or suspicious activity patterns.
    """
    
    def __init__(self, user_id: int, action: str, risk_score: float,
                 block_reason: str, additional_checks_required: bool = True,
                 details: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.action = action
        self.risk_score = risk_score
        self.block_reason = block_reason
        self.additional_checks_required = additional_checks_required
        
        message = f"Action '{action}' blocked for user {user_id} due to high risk ({risk_score}): {block_reason}"
        
        exception_details = {
            'user_id': user_id,
            'action': action,
            'risk_score': risk_score,
            'block_reason': block_reason,
            'additional_checks_required': additional_checks_required,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='HIGH_RISK_ACTION_BLOCKED',
            details=exception_details
        )


class FraudRuleViolationException(FraudDetectionException):
    """
    Exception raised when a fraud rule is violated.
    
    This exception is raised when user activity triggers
    one or more fraud detection rules.
    """
    
    def __init__(self, user_id: int, rule_name: str, rule_type: str,
                 violation_details: Dict[str, Any], severity: str = 'medium',
                 details: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.rule_name = rule_name
        self.rule_type = rule_type
        self.violation_details = violation_details
        self.severity = severity
        
        message = f"Fraud rule '{rule_name}' ({rule_type}) violated by user {user_id} (Severity: {severity})"
        
        exception_details = {
            'user_id': user_id,
            'rule_name': rule_name,
            'rule_type': rule_type,
            'violation_details': violation_details,
            'severity': severity,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='FRAUD_RULE_VIOLATION',
            details=exception_details
        )


class DeviceFingerprintException(FraudDetectionException):
    """
    Exception raised for device fingerprint related issues.
    
    This exception is raised when device fingerprint validation
    fails or suspicious device activity is detected.
    """
    
    def __init__(self, device_hash: str, issue_type: str, description: str,
                 user_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.device_hash = device_hash
        self.issue_type = issue_type
        self.description = description
        self.user_id = user_id
        
        message = f"Device fingerprint issue: {issue_type} - {description}"
        if user_id:
            message += f" (User: {user_id})"
        
        exception_details = {
            'device_hash': device_hash,
            'issue_type': issue_type,
            'description': description,
            'user_id': user_id,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='DEVICE_FINGERPRINT_ERROR',
            details=exception_details
        )


class IPReputationException(FraudDetectionException):
    """
    Exception raised for IP reputation related issues.
    
    This exception is raised when IP reputation checks fail or
    suspicious IP activity is detected.
    """
    
    def __init__(self, ip_address: str, issue_type: str, reputation_score: float,
                 description: str, user_id: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.ip_address = ip_address
        self.issue_type = issue_type
        self.reputation_score = reputation_score
        self.description = description
        self.user_id = user_id
        
        message = f"IP reputation issue: {issue_type} for {ip_address} (Score: {reputation_score}) - {description}"
        if user_id:
            message += f" (User: {user_id})"
        
        exception_details = {
            'ip_address': ip_address,
            'issue_type': issue_type,
            'reputation_score': reputation_score,
            'description': description,
            'user_id': user_id,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='IP_REPUTATION_ERROR',
            details=exception_details
        )


class MultiAccountDetectionException(FraudDetectionException):
    """
    Exception raised when multi-account fraud is detected.
    
    This exception is raised when patterns indicate multiple accounts
    being used by the same entity for fraudulent activities.
    """
    
    def __init__(self, user_ids: list[int], detection_method: str,
                 confidence_score: float, evidence: Dict[str, Any],
                 details: Optional[Dict[str, Any]] = None):
        self.user_ids = user_ids
        self.detection_method = detection_method
        self.confidence_score = confidence_score
        self.evidence = evidence
        
        message = f"Multi-account fraud detected: {detection_method} (Confidence: {confidence_score})"
        message += f" - Users: {', '.join(map(str, user_ids))}"
        
        exception_details = {
            'user_ids': user_ids,
            'detection_method': detection_method,
            'confidence_score': confidence_score,
            'evidence': evidence,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='MULTI_ACCOUNT_DETECTED',
            details=exception_details
        )


class PatternAnalysisException(FraudDetectionException):
    """
    Exception raised for pattern analysis related issues.
    
    This exception is raised when fraud pattern analysis fails
    or detects suspicious patterns requiring attention.
    """
    
    def __init__(self, pattern_type: str, anomaly_score: float, description: str,
                 affected_users: Optional[list[int]] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.pattern_type = pattern_type
        self.anomaly_score = anomaly_score
        self.description = description
        self.affected_users = affected_users or []
        
        message = f"Pattern analysis issue: {pattern_type} (Anomaly Score: {anomaly_score}) - {description}"
        if affected_users:
            message += f" - Affected Users: {', '.join(map(str, affected_users))}"
        
        exception_details = {
            'pattern_type': pattern_type,
            'anomaly_score': anomaly_score,
            'description': description,
            'affected_users': self.affected_users,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='PATTERN_ANALYSIS_ERROR',
            details=exception_details
        )


class CaseManagementException(FraudDetectionException):
    """
    Exception raised for case management related issues.
    
    This exception is raised when fraud case operations fail
    or encounter business rule violations.
    """
    
    def __init__(self, case_id: Optional[int], case_number: Optional[str],
                 operation: str, reason: str, user_id: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.case_id = case_id
        self.case_number = case_number
        self.operation = operation
        self.reason = reason
        self.user_id = user_id
        
        message = f"Case management error: {operation}"
        if case_number:
            message += f" - Case {case_number}"
        if case_id:
            message += f" (ID: {case_id})"
        message += f" - {reason}"
        if user_id:
            message += f" (User: {user_id})"
        
        exception_details = {
            'case_id': case_id,
            'case_number': case_number,
            'operation': operation,
            'reason': reason,
            'user_id': user_id,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='CASE_MANAGEMENT_ERROR',
            details=exception_details
        )


class ValidationException(FraudDetectionException):
    """
    Exception raised for validation errors in fraud detection.
    
    This exception is raised when input validation fails
    or data integrity issues are detected.
    """
    
    def __init__(self, field: str, value: Any, validation_error: str,
                 model: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.field = field
        self.value = value
        self.validation_error = validation_error
        self.model = model
        
        message = f"Validation error for field '{field}'"
        if model:
            message += f" in {model}"
        message += f": {validation_error}"
        if value is not None:
            message += f" (Value: {value})"
        
        exception_details = {
            'field': field,
            'value': value,
            'validation_error': validation_error,
            'model': model,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='VALIDATION_ERROR',
            details=exception_details
        )


class ConfigurationException(FraudDetectionException):
    """
    Exception raised for configuration related issues.
    
    This exception is raised when fraud detection system
    configuration is invalid or missing.
    """
    
    def __init__(self, config_key: str, config_value: Any, issue: str,
                 details: Optional[Dict[str, Any]] = None):
        self.config_key = config_key
        self.config_value = config_value
        self.issue = issue
        
        message = f"Configuration error for '{config_key}': {issue}"
        if config_value is not None:
            message += f" (Current value: {config_value})"
        
        exception_details = {
            'config_key': config_key,
            'config_value': config_value,
            'issue': issue,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='CONFIGURATION_ERROR',
            details=exception_details
        )


class ServiceException(FraudDetectionException):
    """
    Exception raised for service layer operations.
    
    This exception is raised when fraud detection service
    operations fail or encounter unexpected conditions.
    """
    
    def __init__(self, service_name: str, operation: str, error: str,
                 details: Optional[Dict[str, Any]] = None):
        self.service_name = service_name
        self.operation = operation
        self.error = error
        
        message = f"Service error in {service_name} during {operation}: {error}"
        
        exception_details = {
            'service_name': service_name,
            'operation': operation,
            'error': error,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='SERVICE_ERROR',
            details=exception_details
        )


class CacheException(FraudDetectionException):
    """
    Exception raised for cache related issues.
    
    This exception is raised when cache operations fail
    or cache consistency issues are detected.
    """
    
    def __init__(self, cache_key: str, operation: str, error: str,
                 details: Optional[Dict[str, Any]] = None):
        self.cache_key = cache_key
        self.operation = operation
        self.error = error
        
        message = f"Cache error for key '{cache_key}' during {operation}: {error}"
        
        exception_details = {
            'cache_key': cache_key,
            'operation': operation,
            'error': error,
        }
        if details:
            exception_details.update(details)
        
        super().__init__(
            message=message,
            error_code='CACHE_ERROR',
            details=exception_details
        )


# Exception handler utilities
def handle_fraud_exception(exception: Exception) -> Dict[str, Any]:
    """
    Handle fraud detection exceptions and return standardized response.
    
    Args:
        exception: The exception to handle
        
    Returns:
        Standardized error response dictionary
    """
    if isinstance(exception, FraudDetectionException):
        return exception.to_dict()
    else:
        return {
            'error': 'InternalServerError',
            'message': 'An unexpected error occurred',
            'error_code': 'INTERNAL_ERROR',
            'details': {}
        }


def log_fraud_exception(exception: Exception, logger, context: str = ""):
    """
    Log fraud detection exceptions with appropriate level.
    
    Args:
        exception: The exception to log
        logger: Logger instance
        context: Additional context information
    """
    if isinstance(exception, FraudDetectionException):
        if exception.error_code in ['USER_BANNED', 'HIGH_RISK_ACTION_BLOCKED']:
            logger.warning(f"Fraud detection warning in {context}: {exception.message}")
        elif exception.error_code in ['FRAUD_RULE_VIOLATION', 'MULTI_ACCOUNT_DETECTED']:
            logger.error(f"Fraud detection error in {context}: {exception.message}")
        else:
            logger.info(f"Fraud detection info in {context}: {exception.message}")
    else:
        logger.error(f"Unexpected error in {context}: {str(exception)}")


class EncryptionError(FraudDetectionException):
    """Exception raised for encryption/decryption errors."""

    def __init__(self, operation: str, reason: str, details=None):
        self.operation = operation
        self.reason = reason
        message = f"Encryption error during '{operation}': {reason}"
        super().__init__(
            message=message,
            error_code='ENCRYPTION_ERROR',
            details=details or {'operation': operation, 'reason': reason}
        )


class SelectorError(FraudDetectionException):
    """Raised when a selector query fails."""
    default_code = 'selector_error'
    status_code = 400

# Alias for backward compatibility
FraudDetectionError = FraudDetectionException

RepositoryError = ServiceException

# Aliases
IntegrityViolationError = ValidationException
RepositoryError = ServiceException

UseCaseError = ServiceException

# Additional aliases
SanctionsError = FraudDetectionException
ComplianceError = FraudDetectionException
NetworkError = FraudDetectionException
DataProcessingError = FraudDetectionException
AuthenticationError = FraudDetectionException
RateLimitError = FraudDetectionException
ExternalServiceError = FraudDetectionException
BlockchainError = FraudDetectionException
MLModelError = FraudDetectionException

# ── All missing aliases ──────────────────────────────────────
ReportingError = FraudDetectionException
AIError = FraudDetectionException
OpenAIError = FraudDetectionException
AnalyticsError = FraudDetectionException
AttachmentError = FraudDetectionException
BackgroundJobError = FraudDetectionException
CacheError = FraudDetectionException
ConsumerError = FraudDetectionException
DependencyError = FraudDetectionException
EventError = FraudDetectionException
ExportError = FraudDetectionException
FeatureFlagError = FraudDetectionException
SecurityError = FraudDetectionException
WebhookError = FraudDetectionException
IntegrationError = FraudDetectionException
HookError = FraudDetectionException
InteractorError = FraudDetectionException
MonitoringError = FraudDetectionException
NotificationError = FraudDetectionException
PaginationError = FraudDetectionException
PluginError = FraudDetectionException
QuerySetError = FraudDetectionException
RegistryError = FraudDetectionException
SearchError = FraudDetectionException
ServiceError = FraudDetectionException
ThrottlingError = FraudDetectionException
ValidationError = FraudDetectionException

# =============================================================================
# MISSING ALIASES — added to fix viewset.py + signals.py imports
# =============================================================================

class BlockedUserError(FraudDetectionException):
    """
    Raised when a blocked/banned user attempts an action.
    Mapped to HTTP 403 in viewset exception handler.
    """
    def __init__(self, user_id=None, reason="User is blocked", details=None):
        self.user_id = user_id
        message = f"Blocked user {user_id}: {reason}" if user_id else reason
        super().__init__(
            message=message,
            error_code='USER_BLOCKED',
            details=details or {'user_id': user_id, 'reason': reason},
        )


class ThrottlingError(FraudDetectionException):
    """
    Raised when a rate limit / throttle threshold is exceeded.
    Mapped to HTTP 429 in viewset exception handler.
    """
    def __init__(self, limit=None, window=None, reason="Rate limit exceeded", details=None):
        message = reason
        if limit and window:
            message = f"Rate limit exceeded: {limit} requests per {window}s"
        super().__init__(
            message=message,
            error_code='THROTTLE_EXCEEDED',
            details=details or {'limit': limit, 'window': window},
        )


class FraudRuleViolation(FraudDetectionException):
    """
    Raised when a specific fraud rule is violated.
    Mapped to HTTP 400 in viewset exception handler.
    Distinct from FraudRuleViolationException (which is more detailed).
    """
    def __init__(self, rule_name="", reason="Fraud rule violated", details=None):
        message = f"Rule '{rule_name}' violated: {reason}" if rule_name else reason
        super().__init__(
            message=message,
            error_code='FRAUD_RULE_VIOLATION',
            details=details or {'rule_name': rule_name, 'reason': reason},
        )
