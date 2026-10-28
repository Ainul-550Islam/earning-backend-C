# =============================================================================
# fraud_detection/validator.py
# =============================================================================
"""
Validator for Fraud Detection System.

Provides comprehensive validation for fraud detection data,
transactions, user profiles, and system configurations.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from api.fraud_detection.exceptions import ValidationError as FraudValidationError


logger = logging.getLogger(__name__)

User = get_user_model()


class ValidationSeverity(Enum):
    """Validation result severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Data class for validation results."""
    is_valid: bool
    severity: ValidationSeverity
    message: str
    field: Optional[str] = None
    code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    def __init__(self, name: str):
        """Initialize validator."""
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def validate(self, data: Any, context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """
        Validate data.
        
        Args:
            data: Data to validate
            context: Additional validation context
            
        Returns:
            List of validation results
        """
        pass
    
    def _create_result(self, is_valid: bool, severity: ValidationSeverity, 
                      message: str, field: Optional[str] = None,
                      code: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Create validation result."""
        return ValidationResult(
            is_valid=is_valid,
            severity=severity,
            message=message,
            field=field,
            code=code,
            metadata=metadata
        )


class TransactionValidator(BaseValidator):
    """Validator for transaction data."""
    
    def __init__(self):
        super().__init__("transaction_validator")
        self.min_amount = getattr(settings, 'FRAUD_MIN_TRANSACTION_AMOUNT', 0.01)
        self.max_amount = getattr(settings, 'FRAUD_MAX_TRANSACTION_AMOUNT', 1000000.0)
        self.supported_currencies = getattr(settings, 'FRAUD_SUPPORTED_CURRENCIES', ['USD', 'EUR', 'GBP'])
    
    def validate(self, transaction_data: Dict[str, Any], 
                context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate transaction data."""
        results = []
        
        # Validate amount
        results.extend(self._validate_amount(transaction_data))
        
        # Validate currency
        results.extend(self._validate_currency(transaction_data))
        
        # Validate transaction ID
        results.extend(self._validate_transaction_id(transaction_data))
        
        # Validate timestamp
        results.extend(self._validate_timestamp(transaction_data))
        
        # Validate merchant
        results.extend(self._validate_merchant(transaction_data))
        
        # Validate payment method
        results.extend(self._validate_payment_method(transaction_data))
        
        # Validate IP address
        results.extend(self._validate_ip_address(transaction_data))
        
        return results
    
    def _validate_amount(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate transaction amount."""
        results = []
        
        amount = data.get('amount')
        if amount is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Transaction amount is required",
                field="amount",
                code="required"
            ))
        else:
            try:
                amount = float(amount)
                
                if amount < self.min_amount:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Amount {amount} is below minimum {self.min_amount}",
                        field="amount",
                        code="min_amount"
                    ))
                
                if amount > self.max_amount:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message=f"Amount {amount} exceeds maximum {self.max_amount}",
                        field="amount",
                        code="max_amount"
                    ))
                
                if amount <= 0:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message="Amount must be positive",
                        field="amount",
                        code="positive_amount"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Amount must be a valid number",
                    field="amount",
                    code="invalid_amount"
                ))
        
        return results
    
    def _validate_currency(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate transaction currency."""
        results = []
        
        currency = data.get('currency')
        if currency is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Currency is required",
                field="currency",
                code="required"
            ))
        elif currency not in self.supported_currencies:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message=f"Currency {currency} is not supported",
                field="currency",
                code="unsupported_currency"
            ))
        
        return results
    
    def _validate_transaction_id(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate transaction ID."""
        results = []
        
        transaction_id = data.get('transaction_id')
        if transaction_id is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Transaction ID is required",
                field="transaction_id",
                code="required"
            ))
        elif not isinstance(transaction_id, str) or len(transaction_id) < 3:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Transaction ID must be a string with at least 3 characters",
                field="transaction_id",
                code="invalid_transaction_id"
            ))
        
        return results
    
    def _validate_timestamp(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate transaction timestamp."""
        results = []
        
        timestamp = data.get('timestamp')
        if timestamp is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Timestamp is required",
                field="timestamp",
                code="required"
            ))
        else:
            try:
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                elif not isinstance(timestamp, datetime):
                    raise ValueError("Invalid timestamp type")
                
                # Check if timestamp is in the future
                if timestamp > timezone.now() + timedelta(minutes=5):
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message="Transaction timestamp is in the future",
                        field="timestamp",
                        code="future_timestamp"
                    ))
                
                # Check if timestamp is too old
                if timestamp < timezone.now() - timedelta(days=30):
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message="Transaction timestamp is more than 30 days old",
                        field="timestamp",
                        code="old_timestamp"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid timestamp format",
                    field="timestamp",
                    code="invalid_timestamp"
                ))
        
        return results
    
    def _validate_merchant(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate merchant information."""
        results = []
        
        merchant_id = data.get('merchant_id')
        if merchant_id is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Merchant ID is recommended",
                field="merchant_id",
                code="missing_merchant"
            ))
        
        return results
    
    def _validate_payment_method(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate payment method."""
        results = []
        
        payment_method = data.get('payment_method')
        if payment_method is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Payment method is recommended",
                field="payment_method",
                code="missing_payment_method"
            ))
        
        return results
    
    def _validate_ip_address(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate IP address."""
        results = []
        
        ip_address = data.get('ip_address')
        if ip_address is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="IP address is recommended",
                field="ip_address",
                code="missing_ip"
            ))
        else:
            # Basic IP validation
            ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            
            if not re.match(ip_pattern, ip_address):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid IP address format",
                    field="ip_address",
                    code="invalid_ip"
                ))
        
        return results


class UserValidator(BaseValidator):
    """Validator for user data."""
    
    def __init__(self):
        super().__init__("user_validator")
    
    def validate(self, user_data: Dict[str, Any], 
                context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate user data."""
        results = []
        
        # Validate user ID
        results.extend(self._validate_user_id(user_data))
        
        # Validate email
        results.extend(self._validate_email(user_data))
        
        # Validate phone number
        results.extend(self._validate_phone_number(user_data))
        
        # Validate address
        results.extend(self._validate_address(user_data))
        
        # Validate account age
        results.extend(self._validate_account_age(user_data))
        
        return results
    
    def _validate_user_id(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate user ID."""
        results = []
        
        user_id = data.get('user_id')
        if user_id is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="User ID is required",
                field="user_id",
                code="required"
            ))
        
        return results
    
    def _validate_email(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate email address."""
        results = []
        
        email = data.get('email')
        if email is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Email is recommended",
                field="email",
                code="missing_email"
            ))
        else:
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if not re.match(email_pattern, email):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid email format",
                    field="email",
                    code="invalid_email"
                ))
        
        return results
    
    def _validate_phone_number(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate phone number."""
        results = []
        
        phone = data.get('phone_number')
        if phone is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.INFO,
                message="Phone number is optional",
                field="phone_number",
                code="missing_phone"
            ))
        else:
            # Basic phone validation (simplified)
            phone_pattern = r'^\+?1?\d{9,15}$'
            
            if not re.match(phone_pattern, phone.replace('-', '').replace(' ', '')):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    message="Invalid phone number format",
                    field="phone_number",
                    code="invalid_phone"
                ))
        
        return results
    
    def _validate_address(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate address information."""
        results = []
        
        address = data.get('address')
        if address is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.INFO,
                message="Address is optional",
                field="address",
                code="missing_address"
            ))
        elif not isinstance(address, dict):
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Address must be a dictionary",
                field="address",
                code="invalid_address"
            ))
        
        return results
    
    def _validate_account_age(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate account age."""
        results = []
        
        account_created = data.get('account_created')
        if account_created is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Account creation date is recommended",
                field="account_created",
                code="missing_account_created"
            ))
        else:
            try:
                if isinstance(account_created, str):
                    account_created = datetime.fromisoformat(account_created.replace('Z', '+00:00'))
                elif not isinstance(account_created, datetime):
                    raise ValueError("Invalid account_created type")
                
                # Check if account was created in the future
                if account_created > timezone.now():
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message="Account creation date is in the future",
                        field="account_created",
                        code="future_account_created"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid account creation date format",
                    field="account_created",
                    code="invalid_account_created"
                ))
        
        return results


class FraudDetectionValidator(BaseValidator):
    """Validator for fraud detection parameters."""
    
    def __init__(self):
        super().__init__("fraud_detection_validator")
        self.max_risk_score = getattr(settings, 'FRAUD_MAX_RISK_SCORE', 100)
        self.min_risk_score = getattr(settings, 'FRAUD_MIN_RISK_SCORE', 0)
    
    def validate(self, detection_data: Dict[str, Any], 
                context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate fraud detection parameters."""
        results = []
        
        # Validate risk score
        results.extend(self._validate_risk_score(detection_data))
        
        # Validate detection method
        results.extend(self._validate_detection_method(detection_data))
        
        # Validate confidence score
        results.extend(self._validate_confidence_score(detection_data))
        
        # Validate evidence
        results.extend(self._validate_evidence(detection_data))
        
        return results
    
    def _validate_risk_score(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate risk score."""
        results = []
        
        risk_score = data.get('risk_score')
        if risk_score is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Risk score is recommended",
                field="risk_score",
                code="missing_risk_score"
            ))
        else:
            try:
                risk_score = int(risk_score)
                
                if risk_score < self.min_risk_score or risk_score > self.max_risk_score:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Risk score {risk_score} is out of range [{self.min_risk_score}, {self.max_risk_score}]",
                        field="risk_score",
                        code="out_of_range_risk_score"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Risk score must be an integer",
                    field="risk_score",
                    code="invalid_risk_score"
                ))
        
        return results
    
    def _validate_detection_method(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate detection method."""
        results = []
        
        detection_method = data.get('detection_method')
        if detection_method is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Detection method is recommended",
                field="detection_method",
                code="missing_detection_method"
            ))
        
        return results
    
    def _validate_confidence_score(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate confidence score."""
        results = []
        
        confidence_score = data.get('confidence_score')
        if confidence_score is not None:
            try:
                confidence_score = float(confidence_score)
                
                if confidence_score < 0 or confidence_score > 100:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Confidence score {confidence_score} must be between 0 and 100",
                        field="confidence_score",
                        code="out_of_range_confidence"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Confidence score must be a number",
                    field="confidence_score",
                    code="invalid_confidence"
                ))
        
        return results
    
    def _validate_evidence(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate evidence data."""
        results = []
        
        evidence = data.get('evidence')
        if evidence is not None and not isinstance(evidence, dict):
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Evidence must be a dictionary",
                field="evidence",
                code="invalid_evidence"
            ))
        
        return results


class ComplianceValidator(BaseValidator):
    """Validator for compliance data."""
    
    def __init__(self):
        super().__init__("compliance_validator")
    
    def validate(self, compliance_data: Dict[str, Any], 
                context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate compliance data."""
        results = []
        
        # Validate report type
        results.extend(self._validate_report_type(compliance_data))
        
        # Validate reporting period
        results.extend(self._validate_reporting_period(compliance_data))
        
        # Validate regulatory requirements
        results.extend(self._validate_regulatory_requirements(compliance_data))
        
        return results
    
    def _validate_report_type(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate report type."""
        results = []
        
        report_type = data.get('report_type')
        if report_type is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Report type is required",
                field="report_type",
                code="required"
            ))
        
        return results
    
    def _validate_reporting_period(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate reporting period."""
        results = []
        
        period_days = data.get('period_days')
        if period_days is not None:
            try:
                period_days = int(period_days)
                
                if period_days <= 0 or period_days > 365:
                    results.append(self._create_result(
                        is_valid=False,
                        severity=ValidationSeverity.WARNING,
                        message=f"Reporting period {period_days} days is unusual",
                        field="period_days",
                        code="unusual_period"
                    ))
                
            except (ValueError, TypeError):
                results.append(self._create_result(
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Period days must be an integer",
                    field="period_days",
                    code="invalid_period"
                ))
        
        return results
    
    def _validate_regulatory_requirements(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate regulatory requirements."""
        results = []
        
        regulatory_body = data.get('regulatory_body')
        if regulatory_body is None:
            results.append(self._create_result(
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message="Regulatory body is recommended",
                field="regulatory_body",
                code="missing_regulatory_body"
            ))
        
        return results


class ValidationManager:
    """Manager for coordinating multiple validators."""
    
    def __init__(self):
        """Initialize validation manager."""
        self.validators = {
            'transaction': TransactionValidator(),
            'user': UserValidator(),
            'fraud_detection': FraudDetectionValidator(),
            'compliance': ComplianceValidator()
        }
    
    def validate(self, data_type: str, data: Dict[str, Any], 
                context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """
        Validate data using appropriate validator.
        
        Args:
            data_type: Type of data to validate
            data: Data to validate
            context: Additional validation context
            
        Returns:
            List of validation results
        """
        if data_type not in self.validators:
            raise FraudValidationError(f"Unknown data type: {data_type}")
        
        validator = self.validators[data_type]
        return validator.validate(data, context)
    
    def validate_all(self, data: Dict[str, Any], 
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, List[ValidationResult]]:
        """
        Validate data using all applicable validators.
        
        Args:
            data: Data to validate
            context: Additional validation context
            
        Returns:
            Dictionary of validation results by validator
        """
        results = {}
        
        for validator_name, validator in self.validators.items():
            try:
                results[validator_name] = validator.validate(data, context)
            except Exception as e:
                logger.error("Validator %s failed: %s", validator_name, e, exc_info=True)
                results[validator_name] = [ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Validator failed: {e}",
                    code="validator_error"
                )]
        
        return results
    
    def add_validator(self, name: str, validator: BaseValidator):
        """Add custom validator."""
        self.validators[name] = validator
        logger.info(f"Added custom validator: {name}")
    
    def remove_validator(self, name: str):
        """Remove validator."""
        if name in self.validators:
            del self.validators[name]
            logger.info(f"Removed validator: {name}")
    
    def get_validator_names(self) -> List[str]:
        """Get list of validator names."""
        return list(self.validators.keys())


# Global validation manager
validation_manager = ValidationManager()


# Convenience functions
def validate_transaction(transaction_data: Dict[str, Any], 
                        context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    """Validate transaction data."""
    return validation_manager.validate('transaction', transaction_data, context)


def validate_user(user_data: Dict[str, Any], 
                  context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    """Validate user data."""
    return validation_manager.validate('user', user_data, context)


def validate_fraud_detection(detection_data: Dict[str, Any], 
                             context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    """Validate fraud detection data."""
    return validation_manager.validate('fraud_detection', detection_data, context)


def validate_compliance(compliance_data: Dict[str, Any], 
                       context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    """Validate compliance data."""
    return validation_manager.validate('compliance', compliance_data, context)


def validate_all(data: Dict[str, Any], 
                 context: Optional[Dict[str, Any]] = None) -> Dict[str, List[ValidationResult]]:
    """Validate data using all validators."""
    return validation_manager.validate_all(data, context)


# Validation result utilities
def has_errors(results: List[ValidationResult]) -> bool:
    """Check if validation results contain errors."""
    return any(
        result.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        for result in results
    )


def has_warnings(results: List[ValidationResult]) -> bool:
    """Check if validation results contain warnings."""
    return any(
        result.severity == ValidationSeverity.WARNING
        for result in results
    )


def get_error_messages(results: List[ValidationResult]) -> List[str]:
    """Get error messages from validation results."""
    return [
        result.message
        for result in results
        if result.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
    ]


def get_warning_messages(results: List[ValidationResult]) -> List[str]:
    """Get warning messages from validation results."""
    return [
        result.message
        for result in results
        if result.severity == ValidationSeverity.WARNING
    ]


def format_validation_results(results: List[ValidationResult]) -> Dict[str, Any]:
    """Format validation results for API responses."""
    return {
        'is_valid': not has_errors(results),
        'has_warnings': has_warnings(results),
        'error_count': len([r for r in results if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]]),
        'warning_count': len([r for r in results if r.severity == ValidationSeverity.WARNING]),
        'errors': [
            {
                'field': r.field,
                'message': r.message,
                'code': r.code
            }
            for r in results
            if r.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
        ],
        'warnings': [
            {
                'field': r.field,
                'message': r.message,
                'code': r.code
            }
            for r in results
            if r.severity == ValidationSeverity.WARNING
        ]
    }
