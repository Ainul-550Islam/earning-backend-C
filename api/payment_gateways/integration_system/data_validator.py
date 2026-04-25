# api/payment_gateways/integration_system/data_validator.py
# Data validation across all integration boundaries

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple
import re
import logging
from .integ_exceptions import DataValidationError

logger = logging.getLogger(__name__)


class IntegrationDataValidator:
    """
    Validates all data crossing integration boundaries.

    Every event payload is validated before being dispatched.
    Every response from external apps is validated before being used.
    This prevents corrupt data from propagating across modules.
    """

    # ── Schema definitions per event type ─────────────────────────────────────
    SCHEMAS = {
        'deposit.completed': {
            'required': ['user_id', 'amount', 'gateway', 'reference_id'],
            'types':    {'amount': (Decimal, float, int), 'user_id': int},
            'positive': ['amount'],
        },
        'withdrawal.processed': {
            'required': ['user_id', 'amount', 'gateway'],
            'types':    {'amount': (Decimal, float, int)},
            'positive': ['amount'],
        },
        'conversion.approved': {
            'required': ['publisher_id', 'payout', 'conversion_id'],
            'types':    {'payout': (Decimal, float, int)},
            'positive': ['payout'],
        },
    }

    def validate_event(self, event_type: str, payload: dict) -> Tuple[bool, List[str]]:
        """
        Validate event payload against schema.

        Returns:
            (is_valid: bool, errors: list[str])
        """
        errors  = []
        schema  = self.SCHEMAS.get(event_type, {})

        # Required fields
        for field in schema.get('required', []):
            if field not in payload or payload[field] is None:
                errors.append(f'Required field missing: {field}')

        if errors:
            return False, errors

        # Type checks
        for field, expected_types in schema.get('types', {}).items():
            if field in payload and payload[field] is not None:
                if not isinstance(payload[field], expected_types):
                    try:
                        Decimal(str(payload[field]))
                    except Exception:
                        errors.append(f'{field} must be numeric, got {type(payload[field]).__name__}')

        # Positive value checks
        for field in schema.get('positive', []):
            if field in payload:
                try:
                    val = Decimal(str(payload[field]))
                    if val <= 0:
                        errors.append(f'{field} must be positive, got {val}')
                except Exception:
                    pass

        return len(errors) == 0, errors

    def validate_amount(self, amount: Any, min_val: Decimal = Decimal('0'),
                         max_val: Decimal = Decimal('9999999')) -> Decimal:
        """Validate and return normalized Decimal amount."""
        try:
            val = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError):
            raise DataValidationError('amount', f'Invalid amount format: {amount}')
        if val < min_val:
            raise DataValidationError('amount', f'Amount {val} below minimum {min_val}')
        if val > max_val:
            raise DataValidationError('amount', f'Amount {val} exceeds maximum {max_val}')
        return val

    def validate_gateway(self, gateway: str) -> str:
        """Validate gateway name."""
        from api.payment_gateways.choices import ALL_GATEWAYS
        gateway = str(gateway).lower().strip()
        if gateway not in ALL_GATEWAYS:
            raise DataValidationError('gateway', f'Unknown gateway: {gateway}. Valid: {ALL_GATEWAYS}')
        return gateway

    def validate_currency(self, currency: str) -> str:
        """Validate ISO currency code."""
        SUPPORTED = {'BDT','USD','EUR','GBP','AUD','CAD','SGD','JPY','INR','USDT','BTC','ETH','USDC'}
        c = str(currency).upper().strip()
        if c not in SUPPORTED:
            raise DataValidationError('currency', f'Unsupported currency: {c}')
        return c

    def validate_reference_id(self, ref_id: str) -> str:
        """Validate reference ID format."""
        ref_id = str(ref_id).strip()
        if not ref_id:
            raise DataValidationError('reference_id', 'Reference ID cannot be empty')
        if len(ref_id) > 200:
            raise DataValidationError('reference_id', 'Reference ID too long (max 200 chars)')
        if not re.match(r'^[\w\-\.]+$', ref_id):
            raise DataValidationError('reference_id', 'Reference ID contains invalid characters')
        return ref_id

    def validate_phone_bd(self, phone: str) -> str:
        """Validate Bangladesh phone number."""
        clean = re.sub(r'[\s\-\(\)]', '', str(phone))
        if clean.startswith('+880'):
            clean = '0' + clean[4:]
        elif clean.startswith('880') and len(clean) == 13:
            clean = '0' + clean[3:]
        if not re.match(r'^01[3-9]\d{8}$', clean):
            raise DataValidationError('phone', f'Invalid BD phone number: {phone}')
        return clean

    def sanitize_payload(self, payload: dict) -> dict:
        """Remove sensitive fields from payload for logging."""
        SENSITIVE = {'password', 'api_key', 'api_secret', 'webhook_secret',
                     'card_number', 'cvv', 'pin', 'token', 'secret'}
        return {
            k: '***REDACTED***' if k.lower() in SENSITIVE else v
            for k, v in payload.items()
        }

    def validate_wallet_response(self, response: Any) -> bool:
        """Validate response from api.wallet after credit/debit."""
        if response is None:
            return False
        if isinstance(response, bool):
            return response
        if isinstance(response, dict):
            return response.get('success', response.get('status') == 'success', True)
        return True

    def validate_notification_context(self, context: dict, template: str) -> Tuple[bool, list]:
        """Validate notification context has required fields for template."""
        REQUIRED_FIELDS = {
            'payment_deposit_completed':    ['amount', 'currency', 'gateway', 'reference'],
            'payment_withdrawal_processed': ['amount', 'method', 'reference'],
            'payment_conversion_earned':    ['payout', 'offer', 'currency'],
        }
        required = REQUIRED_FIELDS.get(template, [])
        errors   = [f for f in required if f not in context]
        return len(errors) == 0, [f'Missing context field: {f}' for f in errors]
