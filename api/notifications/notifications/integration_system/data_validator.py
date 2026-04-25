# integration_system/data_validator.py
"""Data Validator — Cross-module data validation with schema enforcement."""
import logging, re
from typing import Any, Dict, List, Optional, Tuple, Union
from .integ_exceptions import ValidationFailed, RequiredFieldMissing, DataTypeMismatch
logger = logging.getLogger(__name__)

TYPES = {"str": str, "int": int, "float": float, "bool": bool, "dict": dict, "list": list}

class Schema:
    def __init__(self, fields: Dict):
        self.fields = fields  # {field: {"type": str, "required": bool, "min": ..., "max": ...}}

    def validate(self, data: Dict) -> Tuple[bool, List[str]]:
        errors = []
        for field_name, rules in self.fields.items():
            value = data.get(field_name)
            required = rules.get("required", False)
            if value is None:
                if required:
                    errors.append(f"{field_name}: required")
                continue
            expected_type = TYPES.get(rules.get("type", "str"), str)
            if not isinstance(value, expected_type):
                errors.append(f"{field_name}: expected {rules["type"]}, got {type(value).__name__}")
                continue
            if "min" in rules and isinstance(value, (int, float)) and value < rules["min"]:
                errors.append(f"{field_name}: must be >= {rules["min"]}")
            if "max" in rules and isinstance(value, (int, float)) and value > rules["max"]:
                errors.append(f"{field_name}: must be <= {rules["max"]}")
            if "min_length" in rules and isinstance(value, str) and len(value) < rules["min_length"]:
                errors.append(f"{field_name}: too short (min {rules["min_length"]})")
            if "max_length" in rules and isinstance(value, str) and len(value) > rules["max_length"]:
                errors.append(f"{field_name}: too long (max {rules["max_length"]})")
            if "choices" in rules and value not in rules["choices"]:
                errors.append(f"{field_name}: invalid choice")
            if "pattern" in rules and isinstance(value, str):
                if not re.match(rules["pattern"], value):
                    errors.append(f"{field_name}: invalid format")
            if "validator" in rules:
                try:
                    ok, msg = rules["validator"](value)
                    if not ok:
                        errors.append(f"{field_name}: {msg}")
                except Exception as exc:
                    errors.append(f"{field_name}: validator error: {exc}")
        return len(errors) == 0, errors


# Pre-defined schemas for common payloads
SCHEMAS = {
    "notification": Schema({
        "user_id": {"type": "int", "required": True, "min": 1},
        "title": {"type": "str", "required": True, "max_length": 255},
        "message": {"type": "str", "required": True, "max_length": 2000},
        "notification_type": {"type": "str", "required": True},
        "channel": {"type": "str", "choices": ["in_app","push","email","sms","telegram","whatsapp","browser","all"]},
        "priority": {"type": "str", "choices": ["lowest","low","medium","high","urgent","critical"]},
    }),
    "wallet_credit": Schema({
        "user_id": {"type": "int", "required": True},
        "amount": {"type": "float", "required": True, "min": 0.01},
        "transaction_type": {"type": "str", "required": True},
    }),
    "withdrawal": Schema({
        "user_id": {"type": "int", "required": True},
        "amount": {"type": "float", "required": True, "min": 1.0},
        "payment_method": {"type": "str", "required": True},
    }),
    "event_payload": Schema({
        "user_id": {"type": "int", "required": False},
        "event_type": {"type": "str", "required": True},
    }),
    "webhook": Schema({
        "event": {"type": "str", "required": True},
    }),
}

class DataValidator:
    def validate(self, data: Dict, schema_name: str) -> Tuple[bool, List[str]]:
        schema = SCHEMAS.get(schema_name)
        if not schema:
            logger.warning(f'DataValidator: schema "{schema_name}" not found — skip validation')
            return True, []
        return schema.validate(data)

    def validate_or_raise(self, data: Dict, schema_name: str):
        ok, errors = self.validate(data, schema_name)
        if not ok:
            raise ValidationFailed(reason="; ".join(errors))

    def register_schema(self, name: str, schema: Schema):
        SCHEMAS[name] = schema

    def validate_phone_bd(self, phone: str) -> bool:
        clean = phone.strip().replace("+", "").replace("-", "").replace(" ", "")
        return bool(re.match(r"^(?:880|0088|0)?1[3-9]\d{8}$", clean))

    def validate_email(self, email: str) -> bool:
        return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))


data_validator = DataValidator()
