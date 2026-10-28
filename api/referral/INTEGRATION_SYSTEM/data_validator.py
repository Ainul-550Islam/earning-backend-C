# api/referral/INTEGRATION_SYSTEM/data_validator.py
# Input validation for all integration data
# ============================================================

import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from .integ_exceptions import ValidationError as IntegValidationError

logger = logging.getLogger(__name__)

MAX_COMMISSION_AMOUNT = Decimal('999999.99')
MIN_COMMISSION_AMOUNT = Decimal('0.0001')


class IntegrationValidator:
    """Validates all data entering the integration layer."""

    errors: List[str]

    def __init__(self):
        self.errors = []

    def _add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.debug(f'[Validator] {msg}')

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def raise_if_invalid(self) -> None:
        if not self.is_valid():
            raise IntegValidationError('; '.join(self.errors))

    # ── Field Validators ──────────────────────────────────────────────────────

    def validate_user(self, user, field: str = 'user') -> bool:
        if user is None:
            self._add_error(f'{field}: required')
            return False
        if not hasattr(user, 'pk'):
            self._add_error(f'{field}: must be a User instance')
            return False
        if not getattr(user, 'is_active', True):
            self._add_error(f'{field}: user is inactive')
            return False
        return True

    def validate_amount(
        self, value: Any, field: str = 'amount',
        allow_zero: bool = False
    ) -> bool:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            self._add_error(f'{field}: must be a valid decimal number, got {value!r}')
            return False
        if not allow_zero and amount <= 0:
            self._add_error(f'{field}: must be positive, got {amount}')
            return False
        if amount > MAX_COMMISSION_AMOUNT:
            self._add_error(f'{field}: exceeds maximum {MAX_COMMISSION_AMOUNT}')
            return False
        return True

    def validate_referral_code(self, code: str, field: str = 'referral_code') -> bool:
        if not code:
            self._add_error(f'{field}: required')
            return False
        if len(code) < 4 or len(code) > 30:
            self._add_error(f'{field}: must be 4-30 characters')
            return False
        if not re.match(r'^[A-Z0-9_-]+$', code.upper()):
            self._add_error(f'{field}: invalid characters')
            return False
        return True

    def validate_ip(self, ip: str, field: str = 'ip') -> bool:
        if not ip:
            return True  # IP is optional
        # Simple IPv4 check
        parts = ip.split('.')
        if len(parts) == 4:
            try:
                if all(0 <= int(p) <= 255 for p in parts):
                    return True
            except ValueError:
                pass
        # IPv6 - just basic check
        if ':' in ip:
            return True
        self._add_error(f'{field}: invalid IP address {ip!r}')
        return False

    def validate_level(self, level: int, field: str = 'level') -> bool:
        if level not in (1, 2, 3):
            self._add_error(f'{field}: must be 1, 2, or 3, got {level}')
            return False
        return True

    def validate_source_type(self, source_type: str, field: str = 'source_type') -> bool:
        valid = {'task', 'offer', 'withdrawal', 'deposit', 'signup', 'promotion', 'manual'}
        if source_type not in valid:
            self._add_error(f'{field}: must be one of {valid}')
            return False
        return True

    # ── Compound Validators ───────────────────────────────────────────────────

    @classmethod
    def validate_commission_payload(cls, user, amount, level, source_type) -> 'IntegrationValidator':
        v = cls()
        v.validate_user(user)
        v.validate_amount(amount)
        v.validate_level(level)
        v.validate_source_type(source_type)
        return v

    @classmethod
    def validate_signup_payload(
        cls, new_user, referrer, ip: str = ''
    ) -> 'IntegrationValidator':
        v = cls()
        v.validate_user(new_user, 'new_user')
        v.validate_user(referrer, 'referrer')
        if ip:
            v.validate_ip(ip)
        # Self-referral check
        if (new_user and referrer and
                hasattr(new_user, 'pk') and hasattr(referrer, 'pk') and
                new_user.pk == referrer.pk):
            v._add_error('new_user and referrer cannot be the same person')
        return v

    @classmethod
    def validate_webhook_payload(cls, data: Dict) -> Tuple[bool, List[str]]:
        """Validate incoming webhook payload."""
        errors = []
        if not data.get('user_id'):
            errors.append('user_id required')
        if not data.get('payout') and not data.get('amount'):
            errors.append('payout or amount required')
        try:
            payout = data.get('payout') or data.get('amount', '0')
            if float(payout) < 0:
                errors.append('payout cannot be negative')
        except (ValueError, TypeError):
            errors.append('payout must be a number')
        return len(errors) == 0, errors