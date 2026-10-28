"""
Enhanced Security Exceptions Module
Custom exception classes for security operations
Author: System Security Team
Version: 2.0.0
"""

import logging
from datetime import datetime
from django.utils import timezone
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class SecurityException(Exception):
    """
    Base exception class for all security-related operations
    Provides common functionality for security exceptions
    """
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None, 
                 severity: str = 'medium', user_id: int = None, ip_address: str = None):
        """
        Initialize security exception
        
        Args:
            message (str): Exception message
            error_code (str, optional): Error code for categorization
            context (Dict[str, Any], optional): Additional context information
            severity (str): Severity level (low, medium, high, critical)
            user_id (int, optional): User ID associated with the exception
            ip_address (str, optional): IP address associated with the exception
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.severity = severity
        self.user_id = user_id
        self.ip_address = ip_address
        self.timestamp = timezone.now()
        self.exception_id = f"{self.error_code}_{int(self.timestamp.timestamp())}"
        
        # Log the exception
        self._log_exception()
    
    def _log_exception(self):
        """Log the security exception with structured information"""
        log_data = {
            'exception_id': self.exception_id,
            'exception_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'severity': self.severity,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'context': self.context
        }
        
        if self.severity == 'critical':
            logger.critical(f"Security Exception: {self.message}", extra=log_data)
        elif self.severity == 'high':
            logger.error(f"Security Exception: {self.message}", extra=log_data)
        elif self.severity == 'medium':
            logger.warning(f"Security Exception: {self.message}", extra=log_data)
        else:
            logger.info(f"Security Exception: {self.message}", extra=log_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            'error': self.error_code,
            'message': self.message,
            'severity': self.severity,
            'timestamp': self.timestamp.isoformat(),
            'exception_id': self.exception_id,
            'context': self.context,
            'user_id': self.user_id,
            'ip_address': self.ip_address
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message} (Severity: {self.severity})"


class AccountLockedException(SecurityException):
    """
    Exception raised when an account is locked or banned
    Used for account lockout scenarios
    """
    
    def __init__(self, message: str, lock_type: str = 'temporary', lock_duration: int = None,
                 lock_reason: str = None, unlock_time: datetime = None, **kwargs):
        """
        Initialize account locked exception
        
        Args:
            message (str): Exception message
            lock_type (str): Type of lock (temporary, permanent, admin)
            lock_duration (int, optional): Duration in minutes
            lock_reason (str, optional): Reason for lock
            unlock_time (datetime, optional): When account will be unlocked
        """
        super().__init__(message, error_code='ACCOUNT_LOCKED', severity='high', **kwargs)
        
        self.lock_type = lock_type
        self.lock_duration = lock_duration
        self.lock_reason = lock_reason
        self.unlock_time = unlock_time
        
        # Add lock-specific context
        self.context.update({
            'lock_type': lock_type,
            'lock_duration': lock_duration,
            'lock_reason': lock_reason,
            'unlock_time': unlock_time.isoformat() if unlock_time else None
        })
    
    def get_remaining_time(self) -> Optional[int]:
        """Get remaining lock time in minutes"""
        if self.unlock_time and self.unlock_time > timezone.now():
            remaining = self.unlock_time - timezone.now()
            return int(remaining.total_seconds() / 60)
        return None
    
    def is_permanent(self) -> bool:
        """Check if lock is permanent"""
        return self.lock_type == 'permanent'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with lock-specific information"""
        data = super().to_dict()
        data.update({
            'lock_type': self.lock_type,
            'lock_duration': self.lock_duration,
            'lock_reason': self.lock_reason,
            'unlock_time': self.unlock_time.isoformat() if self.unlock_time else None,
            'remaining_minutes': self.get_remaining_time(),
            'is_permanent': self.is_permanent()
        })
        return data


class SuspiciousActivityException(SecurityException):
    """
    Exception raised when suspicious activity is detected
    Used for various security threat scenarios
    """
    
    def __init__(self, message: str, activity_type: str = 'unknown', threat_level: str = 'medium',
                 indicators: List[str] = None, confidence: float = 0.5, **kwargs):
        """
        Initialize suspicious activity exception
        
        Args:
            message (str): Exception message
            activity_type (str): Type of suspicious activity
            threat_level (str): Threat level (low, medium, high, critical)
            indicators (List[str], optional): List of suspicious indicators
            confidence (float): Confidence level (0.0 to 1.0)
        """
        severity = 'critical' if threat_level == 'critical' else threat_level
        super().__init__(message, error_code='SUSPICIOUS_ACTIVITY', severity=severity, **kwargs)
        
        self.activity_type = activity_type
        self.threat_level = threat_level
        self.indicators = indicators or []
        self.confidence = confidence
        
        # Add activity-specific context
        self.context.update({
            'activity_type': activity_type,
            'threat_level': threat_level,
            'indicators': self.indicators,
            'confidence': self.confidence
        })
    
    def is_critical_threat(self) -> bool:
        """Check if this is a critical threat"""
        return self.threat_level == 'critical' or self.confidence >= 0.9
    
    def get_severity_score(self) -> int:
        """Get numeric severity score (1-100)"""
        threat_scores = {'low': 25, 'medium': 50, 'high': 75, 'critical': 100}
        base_score = threat_scores.get(self.threat_level, 50)
        confidence_adjustment = int(self.confidence * 20)  # 0-20 points
        return min(base_score + confidence_adjustment, 100)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with activity-specific information"""
        data = super().to_dict()
        data.update({
            'activity_type': self.activity_type,
            'threat_level': self.threat_level,
            'indicators': self.indicators,
            'confidence': self.confidence,
            'severity_score': self.get_severity_score(),
            'is_critical_threat': self.is_critical_threat()
        })
        return data


class UnauthorizedDeviceException(SecurityException):
    """
    Exception raised when unauthorized device access is detected
    Used for device authentication and trust scenarios
    """
    
    def __init__(self, message: str, device_fingerprint: str = None, device_type: str = 'unknown',
                 trust_level: str = 'untrusted', risk_score: int = 0, **kwargs):
        """
        Initialize unauthorized device exception
        
        Args:
            message (str): Exception message
            device_fingerprint (str, optional): Device fingerprint
            device_type (str): Type of device
            trust_level (str): Trust level (untrusted, low, medium, high)
            risk_score (int): Risk score (0-100)
        """
        severity = 'high' if risk_score >= 70 else 'medium'
        super().__init__(message, error_code='UNAUTHORIZED_DEVICE', severity=severity, **kwargs)
        
        self.device_fingerprint = device_fingerprint
        self.device_type = device_type
        self.trust_level = trust_level
        self.risk_score = risk_score
        
        # Add device-specific context
        self.context.update({
            'device_fingerprint': device_fingerprint,
            'device_type': device_type,
            'trust_level': trust_level,
            'risk_score': risk_score
        })
    
    def is_high_risk(self) -> bool:
        """Check if device is high risk"""
        return self.risk_score >= 70
    
    def requires_verification(self) -> bool:
        """Check if device requires additional verification"""
        return self.trust_level in ['untrusted', 'low'] or self.is_high_risk()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with device-specific information"""
        data = super().to_dict()
        data.update({
            'device_fingerprint': self.device_fingerprint,
            'device_type': self.device_type,
            'trust_level': self.trust_level,
            'risk_score': self.risk_score,
            'is_high_risk': self.is_high_risk(),
            'requires_verification': self.requires_verification()
        })
        return data


# ==================== ADDITIONAL SECURITY EXCEPTIONS ====================

class VPNProxyDetectedException(SecurityException):
    """Exception raised when VPN or proxy usage is detected"""
    
    def __init__(self, message: str, detection_type: str = 'unknown', confidence: float = 0.5,
                 vpn_provider: str = None, **kwargs):
        """
        Initialize VPN/proxy detected exception
        
        Args:
            message (str): Exception message
            detection_type (str): Type of detection (vpn, proxy, both)
            confidence (float): Detection confidence
            vpn_provider (str, optional): VPN provider name
        """
        super().__init__(message, error_code='VPN_PROXY_DETECTED', severity='medium', **kwargs)
        
        self.detection_type = detection_type
        self.confidence = confidence
        self.vpn_provider = vpn_provider
        
        self.context.update({
            'detection_type': detection_type,
            'confidence': confidence,
            'vpn_provider': vpn_provider
        })


class ThreatIntelligenceException(SecurityException):
    """Exception raised when threat intelligence indicates a threat"""
    
    def __init__(self, message: str, threat_type: str = 'unknown', threat_source: str = None,
                 severity: str = 'medium', indicators: List[str] = None, **kwargs):
        """
        Initialize threat intelligence exception
        
        Args:
            message (str): Exception message
            threat_type (str): Type of threat
            threat_source (str, optional): Source of threat intelligence
            severity (str): Threat severity
            indicators (List[str], optional): Threat indicators
        """
        super().__init__(message, error_code='THREAT_INTELLIGENCE', severity=severity, **kwargs)
        
        self.threat_type = threat_type
        self.threat_source = threat_source
        self.indicators = indicators or []
        
        self.context.update({
            'threat_type': threat_type,
            'threat_source': threat_source,
            'indicators': self.indicators
        })


class RateLimitExceededException(SecurityException):
    """Exception raised when rate limit is exceeded"""
    
    def __init__(self, message: str, limit_type: str = 'unknown', limit_count: int = None,
                 reset_time: datetime = None, **kwargs):
        """
        Initialize rate limit exceeded exception
        
        Args:
            message (str): Exception message
            limit_type (str): Type of rate limit
            limit_count (int, optional): Limit count
            reset_time (datetime, optional): When limit resets
        """
        super().__init__(message, error_code='RATE_LIMIT_EXCEEDED', severity='medium', **kwargs)
        
        self.limit_type = limit_type
        self.limit_count = limit_count
        self.reset_time = reset_time
        
        self.context.update({
            'limit_type': limit_type,
            'limit_count': limit_count,
            'reset_time': reset_time.isoformat() if reset_time else None
        })
    
    def get_reset_seconds(self) -> Optional[int]:
        """Get seconds until limit reset"""
        if self.reset_time and self.reset_time > timezone.now():
            return int((self.reset_time - timezone.now()).total_seconds())
        return None


class PasswordPolicyViolationException(SecurityException):
    """Exception raised when password policy is violated"""
    
    def __init__(self, message: str, policy_violations: List[str] = None,
                 password_strength: str = 'weak', **kwargs):
        """
        Initialize password policy violation exception
        
        Args:
            message (str): Exception message
            policy_violations (List[str], optional): List of violated policies
            password_strength (str): Password strength assessment
        """
        super().__init__(message, error_code='PASSWORD_POLICY_VIOLATION', severity='medium', **kwargs)
        
        self.policy_violations = policy_violations or []
        self.password_strength = password_strength
        
        self.context.update({
            'policy_violations': self.policy_violations,
            'password_strength': password_strength
        })


class SecurityConfigurationException(SecurityException):
    """Exception raised when security configuration is invalid"""
    
    def __init__(self, message: str, config_key: str = None, config_value: Any = None,
                 expected_type: str = None, **kwargs):
        """
        Initialize security configuration exception
        
        Args:
            message (str): Exception message
            config_key (str, optional): Configuration key
            config_value (Any, optional): Invalid configuration value
            expected_type (str, optional): Expected type
        """
        super().__init__(message, error_code='SECURITY_CONFIGURATION', severity='high', **kwargs)
        
        self.config_key = config_key
        self.config_value = config_value
        self.expected_type = expected_type
        
        self.context.update({
            'config_key': config_key,
            'config_value': str(config_value) if config_value is not None else None,
            'expected_type': expected_type
        })


class SecurityServiceException(SecurityException):
    """Exception raised when security service operations fail"""
    
    def __init__(self, message: str, service_name: str = None, operation: str = None,
                 service_error: str = None, **kwargs):
        """
        Initialize security service exception
        
        Args:
            message (str): Exception message
            service_name (str, optional): Name of the service
            operation (str, optional): Operation that failed
            service_error (str, optional): Original service error
        """
        super().__init__(message, error_code='SECURITY_SERVICE', severity='high', **kwargs)
        
        self.service_name = service_name
        self.operation = operation
        self.service_error = service_error
        
        self.context.update({
            'service_name': service_name,
            'operation': operation,
            'service_error': service_error
        })


# ==================== EXCEPTION ENUMS AND UTILITIES ====================

class SecurityErrorCodes(Enum):
    """Enumeration of security error codes"""
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    UNAUTHORIZED_DEVICE = "UNAUTHORIZED_DEVICE"
    VPN_PROXY_DETECTED = "VPN_PROXY_DETECTED"
    THREAT_INTELLIGENCE = "THREAT_INTELLIGENCE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    PASSWORD_POLICY_VIOLATION = "PASSWORD_POLICY_VIOLATION"
    SECURITY_CONFIGURATION = "SECURITY_CONFIGURATION"
    SECURITY_SERVICE = "SECURITY_SERVICE"


class SeverityLevels(Enum):
    """Enumeration of severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LockTypes(Enum):
    """Enumeration of lock types"""
    TEMPORARY = "temporary"
    PERMANENT = "permanent"
    ADMIN = "admin"
    AUTOMATIC = "automatic"


class ThreatLevels(Enum):
    """Enumeration of threat levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== EXCEPTION FACTORY ====================

class SecurityExceptionFactory:
    """Factory class for creating security exceptions"""
    
    @staticmethod
    def create_account_locked(message: str, **kwargs) -> AccountLockedException:
        """Create account locked exception"""
        return AccountLockedException(message, **kwargs)
    
    @staticmethod
    def create_suspicious_activity(message: str, **kwargs) -> SuspiciousActivityException:
        """Create suspicious activity exception"""
        return SuspiciousActivityException(message, **kwargs)
    
    @staticmethod
    def create_unauthorized_device(message: str, **kwargs) -> UnauthorizedDeviceException:
        """Create unauthorized device exception"""
        return UnauthorizedDeviceException(message, **kwargs)
    
    @staticmethod
    def create_vpn_proxy_detected(message: str, **kwargs) -> VPNProxyDetectedException:
        """Create VPN/proxy detected exception"""
        return VPNProxyDetectedException(message, **kwargs)
    
    @staticmethod
    def create_threat_intelligence(message: str, **kwargs) -> ThreatIntelligenceException:
        """Create threat intelligence exception"""
        return ThreatIntelligenceException(message, **kwargs)
    
    @staticmethod
    def create_rate_limit_exceeded(message: str, **kwargs) -> RateLimitExceededException:
        """Create rate limit exceeded exception"""
        return RateLimitExceededException(message, **kwargs)
    
    @staticmethod
    def create_password_policy_violation(message: str, **kwargs) -> PasswordPolicyViolationException:
        """Create password policy violation exception"""
        return PasswordPolicyViolationException(message, **kwargs)
    
    @staticmethod
    def create_security_configuration(message: str, **kwargs) -> SecurityConfigurationException:
        """Create security configuration exception"""
        return SecurityConfigurationException(message, **kwargs)
    
    @staticmethod
    def create_security_service(message: str, **kwargs) -> SecurityServiceException:
        """Create security service exception"""
        return SecurityServiceException(message, **kwargs)


# ==================== EXCEPTION HANDLERS ====================

class SecurityExceptionHandler:
    """Handler class for security exceptions"""
    
    @staticmethod
    def handle_exception(exception: SecurityException) -> Dict[str, Any]:
        """
        Handle security exception and return appropriate response
        
        Args:
            exception (SecurityException): Security exception to handle
            
        Returns:
            Dict[str, Any]: Response data
        """
        response_data = exception.to_dict()
        
        # Add recommended actions based on exception type
        response_data['recommended_actions'] = SecurityExceptionHandler._get_recommended_actions(exception)
        
        # Add escalation information if critical
        if exception.severity == 'critical':
            response_data['escalation_required'] = True
            response_data['escalation_reason'] = f"Critical security event: {exception.error_code}"
        
        return response_data
    
    @staticmethod
    def _get_recommended_actions(exception: SecurityException) -> List[str]:
        """Get recommended actions based on exception type"""
        actions = []
        
        if isinstance(exception, AccountLockedException):
            if exception.is_permanent():
                actions.append("Contact support for account recovery")
            else:
                actions.append("Wait for lock to expire")
                actions.append("Try password reset if available")
            actions.append("Review account security settings")
        
        elif isinstance(exception, SuspiciousActivityException):
            if exception.is_critical_threat():
                actions.append("Immediately change password")
                actions.append("Review recent account activity")
                actions.append("Enable two-factor authentication")
                actions.append("Contact support if needed")
            else:
                actions.append("Monitor account for unusual activity")
                actions.append("Consider changing password")
        
        elif isinstance(exception, UnauthorizedDeviceException):
            if exception.requires_verification():
                actions.append("Complete device verification process")
                actions.append("Check email for verification code")
            actions.append("Register device if trusted")
            actions.append("Review connected devices")
        
        elif isinstance(exception, VPNProxyDetectedException):
            actions.append("Disable VPN/proxy and try again")
            actions.append("Use direct internet connection")
            actions.append("Contact support if VPN is required")
        
        elif isinstance(exception, ThreatIntelligenceException):
            actions.append("Scan device for malware")
            actions.append("Change all passwords")
            actions.append("Review account activity")
            actions.append("Contact security team")
        
        elif isinstance(exception, RateLimitExceededException):
            actions.append("Wait before trying again")
            actions.append("Reduce request frequency")
            if exception.get_reset_seconds():
                actions.append(f"Try again in {exception.get_reset_seconds()} seconds")
        
        elif isinstance(exception, PasswordPolicyViolationException):
            actions.append("Choose a stronger password")
            for violation in exception.policy_violations:
                actions.append(f"Fix: {violation}")
        
        return actions


# ==================== DECORATORS ====================

def security_exception_handler(func):
    """
    Decorator to handle security exceptions in functions
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SecurityException as e:
            logger.error(f"Security exception in {func.__name__}: {str(e)}")
            return SecurityExceptionHandler.handle_exception(e)
        except Exception as e:
            logger.error(f"Unexpected exception in {func.__name__}: {str(e)}")
            raise
    
    return wrapper


def log_security_exceptions(func):
    """
    Decorator to log security exceptions with additional context
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SecurityException as e:
            # Additional logging context
            logger.error(
                f"Security exception in {func.__name__}",
                extra={
                    'function': func.__name__,
                    'exception_id': e.exception_id,
                    'error_code': e.error_code,
                    'severity': e.severity,
                    'context': e.context
                }
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected exception in {func.__name__}: {str(e)}")
            raise
    
    return wrapper