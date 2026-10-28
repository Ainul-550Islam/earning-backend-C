# api/admin_panel/INTEGRATION_SYSTEM/data_validator.py
"""
DataValidator — Validates all data flowing through the integration system.
Schema validation, type checking, range validation, sanitization.
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# ==================== FIELD SCHEMAS ====================

SCHEMAS = {
    'adjust_wallet': {
        'user_id': {'type': int, 'required': True, 'min': 1},
        'amount': {'type': float, 'required': True},
        'reason': {'type': str, 'required': False, 'max_length': 500},
    },
    'ban_user': {
        'user_id': {'type': int, 'required': True, 'min': 1},
        'reason': {'type': str, 'required': True, 'min_length': 3, 'max_length': 500},
    },
    'block_ip': {
        'ip': {'type': str, 'required': True, 'pattern': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'},
        'reason': {'type': str, 'required': True, 'min_length': 3},
    },
    'approve_withdrawal': {
        'item_id': {'type': int, 'required': True, 'min': 1},
        'transaction_ref': {'type': str, 'required': False, 'max_length': 200},
    },
    'kyc_approve': {
        'kyc_id': {'type': int, 'required': True, 'min': 1},
    },
    'send_broadcast': {
        'title': {'type': str, 'required': True, 'min_length': 3, 'max_length': 200},
        'body': {'type': str, 'required': True, 'min_length': 10, 'max_length': 5000},
        'audience_type': {'type': str, 'required': False, 'choices': ['all', 'active', 'premium', 'filtered']},
    },
    'grant_points': {
        'user_id': {'type': int, 'required': True, 'min': 1},
        'amount': {'type': float, 'required': True, 'min': 0.01, 'max': 1000000},
        'reason': {'type': str, 'required': True, 'min_length': 3},
    },
}


class ValidationError(Exception):
    def __init__(self, message: str, field: str = '', errors: list = None):
        super().__init__(message)
        self.field = field
        self.errors = errors or [{'field': field, 'message': message}]


class DataValidator:
    """Validates integration data payloads against defined schemas."""

    @classmethod
    def validate(cls, schema_name: str, data: dict) -> Tuple[bool, List[Dict]]:
        """
        Validate data against a named schema.
        Returns: (is_valid: bool, errors: list)
        """
        schema = SCHEMAS.get(schema_name)
        if not schema:
            logger.warning(f"[DataValidator] No schema for: {schema_name}")
            return True, []  # No schema = pass through

        errors = []
        for field, rules in schema.items():
            value = data.get(field)
            field_errors = cls._validate_field(field, value, rules)
            errors.extend(field_errors)

        return len(errors) == 0, errors

    @classmethod
    def validate_or_raise(cls, schema_name: str, data: dict):
        """Validate and raise ValidationError if invalid."""
        is_valid, errors = cls.validate(schema_name, data)
        if not is_valid:
            raise ValidationError(
                f"Validation failed for schema '{schema_name}'",
                errors=errors,
            )

    @classmethod
    def _validate_field(cls, field: str, value: Any, rules: dict) -> List[Dict]:
        errors = []
        required = rules.get('required', False)

        # Required check
        if required and (value is None or value == ''):
            errors.append({'field': field, 'message': f'{field} is required'})
            return errors

        if value is None:
            return errors  # Optional field, skip further checks

        # Type check
        expected_type = rules.get('type')
        if expected_type:
            try:
                if expected_type == float:
                    float(value)
                elif expected_type == int:
                    int(value)
                elif expected_type == str:
                    str(value)
                elif expected_type == bool:
                    if not isinstance(value, bool):
                        errors.append({'field': field, 'message': f'{field} must be boolean'})
            except (TypeError, ValueError):
                errors.append({'field': field, 'message': f'{field} must be {expected_type.__name__}'})
                return errors

        # Min/Max for numbers
        if isinstance(value, (int, float)):
            if 'min' in rules and value < rules['min']:
                errors.append({'field': field, 'message': f'{field} must be >= {rules["min"]}'})
            if 'max' in rules and value > rules['max']:
                errors.append({'field': field, 'message': f'{field} must be <= {rules["max"]}'})

        # Min/Max length for strings
        if isinstance(value, str):
            if 'min_length' in rules and len(value) < rules['min_length']:
                errors.append({'field': field, 'message': f'{field} must be at least {rules["min_length"]} chars'})
            if 'max_length' in rules and len(value) > rules['max_length']:
                errors.append({'field': field, 'message': f'{field} must be at most {rules["max_length"]} chars'})
            if 'pattern' in rules and not re.match(rules['pattern'], value):
                errors.append({'field': field, 'message': f'{field} format is invalid'})

        # Choices
        if 'choices' in rules and value not in rules['choices']:
            errors.append({'field': field, 'message': f'{field} must be one of: {rules["choices"]}'})

        return errors

    @classmethod
    def sanitize(cls, data: dict) -> dict:
        """Sanitize data — strip dangerous keys, truncate long strings."""
        dangerous_keys = {'password', 'token', 'secret', 'api_key', 'private_key', '__proto__'}
        sanitized = {}
        for k, v in data.items():
            if k.lower() in dangerous_keys:
                continue
            if isinstance(v, str) and len(v) > 10000:
                v = v[:10000]
            sanitized[k] = v
        return sanitized

    @classmethod
    def is_valid_ip(cls, ip: str) -> bool:
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, ip):
            return False
        parts = ip.split('.')
        return all(0 <= int(p) <= 255 for p in parts)

    @classmethod
    def is_valid_amount(cls, amount: Any, min_val: float = 0.01, max_val: float = 1e9) -> bool:
        try:
            val = float(amount)
            return min_val <= val <= max_val
        except (TypeError, ValueError):
            return False