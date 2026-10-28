# =============================================================================
# fraud_detection/validators.py  — SINGLE SOURCE OF TRUTH
#
# DRY merge of:
#   - validators.py   (DRF field-level validators used by serializers)
#   - validator.py    (class-based ValidationManager framework)
#
# Rule: validate_ip_address / ValidationResult / ValidationSeverity exist
# exactly ONCE here.  validator.py is deleted; anything that imported from
# validator.py must import from here instead.
# =============================================================================
from __future__ import annotations

import ipaddress
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PART A — DRF field-level validators
# Used by: serializers, model.clean(), DRF validate_<field>() hooks
# Each raises DRFValidationError on failure; returns cleaned value on success.
# ─────────────────────────────────────────────────────────────────────────────

def validate_ip_address(value: str) -> str:
    """Validate IPv4 or IPv6 address (not CIDR). Raises DRFValidationError."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    if not value:
        raise DRFValidationError("IP address is required.")
    try:
        ipaddress.ip_address(str(value).strip())
    except ValueError:
        raise DRFValidationError(f"{value!r} is not a valid IP address.")
    return str(value).strip()


def validate_risk_score(value: Any) -> int:
    """Validate integer in [0, 100]. Raises DRFValidationError."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    try:
        score = int(value)
    except (TypeError, ValueError):
        raise DRFValidationError("Risk score must be an integer.")
    if not (0 <= score <= 100):
        raise DRFValidationError("Risk score must be between 0 and 100.")
    return score


def validate_device_fingerprint(data: dict) -> dict:
    """Validate device fingerprint dict has required keys."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    required = {"device_id", "user_agent", "screen_resolution"}
    missing = required - set(data.keys())
    if missing:
        raise DRFValidationError(f"Device fingerprint missing keys: {sorted(missing)}")
    return data


def validate_fraud_rule_data(data: dict) -> dict:
    """Validate fraud rule has name, rule_type, threshold."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    for key in ("name", "rule_type", "threshold"):
        if key not in data or data[key] is None:
            raise DRFValidationError(f"Fraud rule requires '{key}'.")
    return data


def validate_evidence_data(data: dict) -> dict:
    """Validate case evidence dict."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    if not isinstance(data, dict):
        raise DRFValidationError("Evidence must be a JSON object.")
    if "evidence_type" not in data:
        raise DRFValidationError("Evidence requires 'evidence_type'.")
    return data


def validate_whitelist_data(data: dict) -> dict:
    """Validate whitelist entry."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    if not data.get("user_id") and not data.get("ip_address"):
        raise DRFValidationError("Whitelist entry requires 'user_id' or 'ip_address'.")
    return data


def validate_notification_data(data: dict) -> dict:
    """Validate notification payload."""
    from rest_framework.exceptions import ValidationError as DRFValidationError
    for key in ("notification_type", "message"):
        if not data.get(key):
            raise DRFValidationError(f"Notification requires '{key}'.")
    return data


# ─────────────────────────────────────────────────────────────────────────────
# PART B — Class-based ValidationManager framework
# Used by: services, background tasks, compliance checks, manual validation
# Does NOT raise DRFValidationError; returns ValidationResult objects instead.
# ─────────────────────────────────────────────────────────────────────────────

class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    INFO     = "info"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Structured result from class-based validators."""
    is_valid:  bool
    severity:  ValidationSeverity
    message:   str
    field:     Optional[str]           = None
    code:      Optional[str]           = None
    metadata:  Optional[Dict[str, Any]] = None
    timestamp: datetime                = dataclass_field(default_factory=timezone.now)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "is_valid":  self.is_valid,
            "severity":  self.severity.value,
            "message":   self.message,
            "field":     self.field,
            "code":      self.code,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseValidator(ABC):
    """Abstract base for all class-based validators."""

    def __init__(self, name: str):
        self.name   = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def validate(self,
                 data: Any,
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Return list of ValidationResult objects."""

    # ── helpers ──────────────────────────────────────────────────────────────
    def _ok(self, message: str = "Valid", field: str | None = None,
            code: str | None = None) -> ValidationResult:
        return ValidationResult(True, ValidationSeverity.INFO, message, field, code)

    def _warn(self, message: str, field: str | None = None,
              code: str | None = None) -> ValidationResult:
        return ValidationResult(False, ValidationSeverity.WARNING, message, field, code)

    def _err(self, message: str, field: str | None = None,
             code: str | None = None) -> ValidationResult:
        return ValidationResult(False, ValidationSeverity.ERROR, message, field, code)

    def _crit(self, message: str, field: str | None = None,
              code: str | None = None) -> ValidationResult:
        return ValidationResult(False, ValidationSeverity.CRITICAL, message, field, code)


class TransactionValidator(BaseValidator):
    """Validate transaction payloads."""

    def __init__(self):
        super().__init__("transaction_validator")
        self.min_amount         = getattr(settings, "FRAUD_MIN_TRANSACTION_AMOUNT", 0.01)
        self.max_amount         = getattr(settings, "FRAUD_MAX_TRANSACTION_AMOUNT", 1_000_000.0)
        self.supported_currencies = getattr(
            settings, "FRAUD_SUPPORTED_CURRENCIES", ["USD", "EUR", "GBP"]
        )

    def validate(self, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        results += self._check_amount(data)
        results += self._check_currency(data)
        results += self._check_transaction_id(data)
        results += self._check_timestamp(data)
        results += self._check_ip(data)
        return results

    def _check_amount(self, data):
        amt = data.get("amount")
        if amt is None:
            return [self._err("amount is required", "amount", "required")]
        try:
            amt = float(amt)
        except (TypeError, ValueError):
            return [self._err("amount must be a number", "amount", "invalid")]
        out = []
        if amt <= 0:
            out.append(self._err("amount must be positive", "amount", "non_positive"))
        if amt < self.min_amount:
            out.append(self._err(f"amount below minimum {self.min_amount}", "amount", "min_amount"))
        if amt > self.max_amount:
            out.append(self._warn(f"amount exceeds maximum {self.max_amount}", "amount", "max_amount"))
        return out

    def _check_currency(self, data):
        cur = data.get("currency")
        if cur is None:
            return [self._err("currency is required", "currency", "required")]
        if cur not in self.supported_currencies:
            return [self._warn(f"{cur} not in supported currencies", "currency", "unsupported")]
        return []

    def _check_transaction_id(self, data):
        tid = data.get("transaction_id")
        if not tid:
            return [self._err("transaction_id is required", "transaction_id", "required")]
        if not isinstance(tid, str) or len(tid) < 3:
            return [self._err("transaction_id must be ≥3 chars", "transaction_id", "too_short")]
        return []

    def _check_timestamp(self, data):
        ts = data.get("timestamp")
        if ts is None:
            return [self._err("timestamp is required", "timestamp", "required")]
        try:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if not isinstance(ts, datetime):
                raise ValueError("bad type")
        except (ValueError, TypeError):
            return [self._err("invalid timestamp format", "timestamp", "invalid")]
        out = []
        if ts > timezone.now() + timedelta(minutes=5):
            out.append(self._warn("timestamp is in the future", "timestamp", "future"))
        if ts < timezone.now() - timedelta(days=30):
            out.append(self._warn("timestamp is >30 days old", "timestamp", "stale"))
        return out

    def _check_ip(self, data):
        ip = data.get("ip_address")
        if not ip:
            return [self._warn("ip_address recommended", "ip_address", "missing")]
        try:
            ipaddress.ip_address(str(ip).strip())
        except ValueError:
            return [self._err(f"{ip!r} is not a valid IP", "ip_address", "invalid")]
        return []


class UserValidator(BaseValidator):
    """Validate user payloads."""

    def __init__(self):
        super().__init__("user_validator")

    def validate(self, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        results += self._check_user_id(data)
        results += self._check_email(data)
        results += self._check_phone(data)
        results += self._check_account_age(data)
        return results

    def _check_user_id(self, data):
        if not data.get("user_id"):
            return [self._err("user_id is required", "user_id", "required")]
        return []

    def _check_email(self, data):
        email = data.get("email")
        if not email:
            return [self._warn("email recommended", "email", "missing")]
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
            return [self._err("invalid email format", "email", "invalid")]
        return []

    def _check_phone(self, data):
        phone = data.get("phone_number")
        if not phone:
            return []  # optional
        cleaned = re.sub(r"[\s\-]", "", phone)
        if not re.match(r"^\+?\d{9,15}$", cleaned):
            return [self._warn("invalid phone format", "phone_number", "invalid")]
        return []

    def _check_account_age(self, data):
        ac = data.get("account_created")
        if not ac:
            return [self._warn("account_created recommended", "account_created", "missing")]
        try:
            if isinstance(ac, str):
                ac = datetime.fromisoformat(ac.replace("Z", "+00:00"))
            if ac > timezone.now():
                return [self._err("account_created is in the future", "account_created", "future")]
        except (ValueError, TypeError):
            return [self._err("invalid account_created format", "account_created", "invalid")]
        return []


class FraudDetectionValidator(BaseValidator):
    """Validate fraud detection payloads."""

    def __init__(self):
        super().__init__("fraud_detection_validator")
        self.max_risk = getattr(settings, "FRAUD_MAX_RISK_SCORE", 100)
        self.min_risk = getattr(settings, "FRAUD_MIN_RISK_SCORE", 0)

    def validate(self, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        results += self._check_risk_score(data)
        results += self._check_confidence(data)
        results += self._check_evidence(data)
        return results

    def _check_risk_score(self, data):
        score = data.get("risk_score")
        if score is None:
            return [self._warn("risk_score recommended", "risk_score", "missing")]
        try:
            score = int(score)
        except (TypeError, ValueError):
            return [self._err("risk_score must be integer", "risk_score", "invalid")]
        if not (self.min_risk <= score <= self.max_risk):
            return [self._err(
                f"risk_score {score} out of [{self.min_risk}, {self.max_risk}]",
                "risk_score", "out_of_range"
            )]
        return []

    def _check_confidence(self, data):
        conf = data.get("confidence_score")
        if conf is None:
            return []
        try:
            conf = float(conf)
            if not (0 <= conf <= 100):
                return [self._err("confidence_score must be 0–100", "confidence_score", "out_of_range")]
        except (TypeError, ValueError):
            return [self._err("confidence_score must be a number", "confidence_score", "invalid")]
        return []

    def _check_evidence(self, data):
        ev = data.get("evidence")
        if ev is not None and not isinstance(ev, dict):
            return [self._err("evidence must be a JSON object", "evidence", "invalid")]
        return []


class ComplianceValidator(BaseValidator):
    """Validate compliance report payloads."""

    def __init__(self):
        super().__init__("compliance_validator")

    def validate(self, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        if not data.get("report_type"):
            results.append(self._err("report_type is required", "report_type", "required"))
        pd = data.get("period_days")
        if pd is not None:
            try:
                pd = int(pd)
                if not (1 <= pd <= 365):
                    results.append(self._warn(f"period_days={pd} is unusual", "period_days"))
            except (TypeError, ValueError):
                results.append(self._err("period_days must be integer", "period_days", "invalid"))
        return results


class ValidationManager:
    """Coordinates multiple validators; single entry point for services/tasks."""

    def __init__(self):
        self._validators: Dict[str, BaseValidator] = {
            "transaction":      TransactionValidator(),
            "user":             UserValidator(),
            "fraud_detection":  FraudDetectionValidator(),
            "compliance":       ComplianceValidator(),
        }

    def validate(self, data_type: str, data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate using named validator."""
        from api.fraud_detection.exceptions import ValidationError as FraudValidationError
        if data_type not in self._validators:
            raise FraudValidationError(f"Unknown data_type: {data_type!r}")
        return self._validators[data_type].validate(data, context)

    def validate_all(self, data: Dict[str, Any],
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, List[ValidationResult]]:
        """Run all validators and aggregate results."""
        results: Dict[str, List[ValidationResult]] = {}
        for name, validator in self._validators.items():
            try:
                results[name] = validator.validate(data, context)
            except Exception as exc:
                logger.error("Validator %s failed: %s", name, exc, exc_info=True)
                results[name] = [ValidationResult(
                    False, ValidationSeverity.CRITICAL,
                    f"Validator error: {exc}", code="validator_error"
                )]
        return results

    def add_validator(self, name: str, validator: BaseValidator) -> None:
        self._validators[name] = validator

    def remove_validator(self, name: str) -> None:
        self._validators.pop(name, None)

    def get_validator_names(self) -> List[str]:
        return list(self._validators.keys())


# ── Module-level singleton ────────────────────────────────────────────────────
_validation_manager: Optional[ValidationManager] = None


def get_validation_manager() -> ValidationManager:
    """Return singleton ValidationManager."""
    global _validation_manager
    if _validation_manager is None:
        _validation_manager = ValidationManager()
    return _validation_manager


# ── Convenience wrappers ──────────────────────────────────────────────────────
def validate_transaction(data: Dict[str, Any],
                         context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    return get_validation_manager().validate("transaction", data, context)


def validate_user(data: Dict[str, Any],
                  context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    return get_validation_manager().validate("user", data, context)


def validate_fraud_detection_data(data: Dict[str, Any],
                                  context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    return get_validation_manager().validate("fraud_detection", data, context)


def validate_compliance_data(data: Dict[str, Any],
                             context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
    return get_validation_manager().validate("compliance", data, context)


# ── Result utilities ──────────────────────────────────────────────────────────
def has_errors(results: List[ValidationResult]) -> bool:
    return any(r.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for r in results)


def has_warnings(results: List[ValidationResult]) -> bool:
    return any(r.severity == ValidationSeverity.WARNING for r in results)


def format_validation_results(results: List[ValidationResult]) -> Dict[str, Any]:
    errors   = [r for r in results if r.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]
    warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]
    return {
        "is_valid":      not errors,
        "has_warnings":  bool(warnings),
        "error_count":   len(errors),
        "warning_count": len(warnings),
        "errors":   [{"field": r.field, "message": r.message, "code": r.code} for r in errors],
        "warnings": [{"field": r.field, "message": r.message, "code": r.code} for r in warnings],
    }
