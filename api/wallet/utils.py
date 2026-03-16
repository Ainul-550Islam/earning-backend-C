# api/wallet/utils.py
import ipaddress
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Any, Optional, Type, Union, Dict, List
from functools import wraps
import traceback
import uuid
from django.utils import timezone
from django.db import models
from .validators import (
    safe_ip_address,
    safe_decimal,
    safe_string,
    safe_int,
    safe_bool,
    safe_get,
    extract_client_ip,
    CircuitBreaker,
)

logger = logging.getLogger(__name__)

# ============================================
# NULL OBJECT PATTERN - আপনার models এর জন্য
# ============================================

class Sentinel:
    """Sentinel value for distinguishing between None and missing data"""
    pass

MISSING = Sentinel()

def safe_get(data: Any, key: str, default: Any = None, expected_type: Optional[Type] = None) -> Any:
    """
    Null-safe value extraction - আপনার models এর সব fields এর জন্য
    
    আপনার models এ ব্যবহার:
    - Wallet: current_balance, pending_balance, frozen_balance
    - WalletTransaction: amount, balance_before, balance_after
    - UserPaymentMethod: account_number, account_name
    - Withdrawal: amount, fee, net_amount
    """
    try:
        if data is None:
            return default
        
        if isinstance(data, dict):
            value = data.get(key, MISSING)
            if value is MISSING:
                return default
        else:
            try:
                value = getattr(data, key, MISSING)
                if value is MISSING:
                    return default
            except Exception:
                return default
        
        if value is None:
            return default
        
        # Type validation - আপনার models এর field types অনুযায়ী
        if expected_type and value is not None:
            if expected_type == Decimal:
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError, TypeError):
                    logger.warning(f"Invalid Decimal for {key}: {value}")
                    return default
            
            elif expected_type == datetime:
                if isinstance(value, str):
                    try:
                        from django.utils.dateparse import parse_datetime
                        parsed = parse_datetime(value)
                        if parsed:
                            return parsed
                    except (ValueError, TypeError):
                        pass
                    return default if not isinstance(value, datetime) else value
                return value if isinstance(value, datetime) else default
            
            elif expected_type == uuid.UUID:
                try:
                    if isinstance(value, uuid.UUID):
                        return value
                    return uuid.UUID(str(value))
                except (ValueError, TypeError):
                    return default
            
            elif not isinstance(value, expected_type):
                logger.debug(f"Type mismatch for {key}: expected {expected_type}, got {type(value)}")
                return default
        
        return value
        
    except Exception as e:
        logger.debug(f"Safe get failed for {key}: {e}")
        return default


def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """Safe Decimal conversion - Wallet balance fields এর জন্য"""
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safe integer conversion"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = '') -> str:
    """Safe string conversion - TextField, CharField এর জন্য"""
    try:
        if value is None:
            return default
        return str(value).strip()
    except Exception:
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safe boolean conversion - BooleanField এর জন্য"""
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on', 'approved', 'completed']
        return bool(value)
    except Exception:
        return default


def safe_uuid(value: Any, default: Optional[uuid.UUID] = None) -> Optional[uuid.UUID]:
    """
    Safe UUID conversion - আপনার models এর জন্য:
    - WalletTransaction.walletTransaction_id
    - Withdrawal.withdrawal_id
    """
    try:
        if value is None:
            return default
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return default


def safe_ip(ip_string: Any, default: str = '127.0.0.1') -> str:
    """
    Safe IP address validation - আপনার database error fix করবে
    WalletWebhookLog এ IP address save করার সময় ব্যবহার হবে
    """
    try:
        if ip_string is None:
            return default
        
        ip_str = str(ip_string).strip()
        
        # Check for invalid values - এইটাই আপনার error fix করবে
        if not ip_str or ip_str == 'invalid_ip' or ip_str == 'None':
            logger.warning(f"Invalid IP detected: {ip_string}, using {default}")
            return default
        
        # Validate IP format
        ipaddress.ip_address(ip_str)
        return ip_str
        
    except (ValueError, AttributeError, ipaddress.AddressValueError) as e:
        logger.debug(f"Invalid IP address: {ip_string}, using default. Error: {e}")
        return default


# ============================================
# DEEP GET - JSONField এর জন্য (WalletTransaction.metadata, Withdrawal.gateway_response)
# ============================================

def deep_get(data: Any, path: str, default: Any = None) -> Any:
    """
    Nested data extraction - JSONField এর জন্য
    
    আপনার models এ ব্যবহার:
    - WalletTransaction.metadata থেকে data extract করতে
    - Withdrawal.gateway_response থেকে data extract করতে
    - WalletWebhookLog.payload থেকে data extract করতে
    
    Example:
        metadata = {'payment': {'bkash': {'trx_id': 'ABC123'}}}
        trx_id = deep_get(metadata, 'payment.bkash.trx_id', '')
    """
    try:
        if data is None:
            return default
        
        current = data
        for key in path.split('.'):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, (list, tuple)) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return default
            else:
                current = getattr(current, key, MISSING)
                if current is MISSING:
                    return default
            
            if current is None:
                return default
        
        return current
        
    except Exception as e:
        logger.debug(f"Deep get failed for path {path}: {e}")
        return default


# ============================================
# MODEL VALIDATION - আপনার models এর constraints এর জন্য
# ============================================

def validate_decimal_positive(value: Decimal, field_name: str = 'amount') -> bool:
    """
    Validate decimal is positive - amount fields এর জন্য
    WalletTransaction.amount, Withdrawal.amount
    """
    try:
        val = safe_decimal(value)
        if val <= 0:
            logger.warning(f"{field_name} must be positive: {val}")
            return False
        return True
    except Exception:
        return False


def validate_decimal_range(value: Decimal, min_val: Decimal, max_val: Decimal, field_name: str = 'amount') -> bool:
    """
    Validate decimal is within range - balance fields এর জন্য
    Wallet.current_balance, Wallet.frozen_balance
    """
    try:
        val = safe_decimal(value)
        if val < min_val or val > max_val:
            logger.warning(f"{field_name} {val} outside range [{min_val}, {max_val}]")
            return False
        return True
    except Exception:
        return False


def validate_choice(value: Any, choices: List[tuple], field_name: str = 'field') -> bool:
    """
    Validate value is in choices - CharField with choices এর জন্য
    
    আপনার models এ ব্যবহার:
    - WalletTransaction.type
    - WalletTransaction.status
    - UserPaymentMethod.method_type
    - Withdrawal.status
    - WalletWebhookLog.webhook_type
    """
    if not choices:
        return True
    
    valid_values = [choice[0] for choice in choices]
    if value not in valid_values:
        logger.warning(f"{field_name} '{value}' not in valid choices: {valid_values}")
        return False
    return True


# ============================================
# WALLET-SPECIFIC HELPER FUNCTIONS
# ============================================

def calculate_withdrawal_fee(amount: Decimal, fee_percentage: Decimal = Decimal('0.015'), 
                            min_fee: Decimal = Decimal('10'), max_fee: Decimal = Decimal('500')) -> Decimal:
    """
    Withdrawal fee calculation - আপনার Withdrawal model এর জন্য
    
    আপনার model এ যেমন আছে:
    fee = models.DecimalField(default=0)
    
    Rules:
    - 1.5% fee (0.015)
    - Minimum fee 10 BDT
    - Maximum fee 500 BDT
    """
    try:
        amount = safe_decimal(amount)
        if amount <= 0:
            return Decimal('0')
        
        fee = amount * fee_percentage
        fee = max(fee, min_fee)
        fee = min(fee, max_fee)
        
        return fee.quantize(Decimal('0.01'))
        
    except Exception as e:
        logger.error(f"Fee calculation error: {e}")
        return min_fee


def format_currency(amount: Decimal, currency: str = 'BDT') -> str:
    """Format currency for display - __str__ methods এর জন্য"""
    try:
        amount = safe_decimal(amount)
        return f"{amount:,.2f} {currency}"
    except Exception:
        return f"0.00 {currency}"


def mask_account_number(account_number: str, visible_digits: int = 4) -> str:
    """
    Mask account number for security - UserPaymentModel এর জন্য
    
    Example: '01712345678' -> '****5678'
    """
    try:
        account = safe_str(account_number)
        if len(account) <= visible_digits:
            return account
        
        masked = '*' * (len(account) - visible_digits) + account[-visible_digits:]
        return masked
    except Exception:
        return '****'


# ============================================
# CIRCUIT BREAKER PATTERN - Payment Gateway calls এর জন্য
# ============================================

class CircuitBreaker:
    """
    Circuit Breaker for external API calls (bKash, Nagad, SSLCommerz)
    
    আপনার models এ ব্যবহার:
    - Withdrawal processing এ payment gateway call
    - WalletWebhookLog handling এ
    """
    
    CLOSED = 'CLOSED'      # Normal operation
    OPEN = 'OPEN'          # Failing, don't try
    HALF_OPEN = 'HALF_OPEN'  # Testing if recovered
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, name: str = 'default'):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failures = 0
        self.last_failure_time = None
        self.state = self.CLOSED
    
    def __enter__(self):
        if self.state == self.OPEN:
            if self._should_try_recovery():
                logger.info(f"Circuit {self.name} moving to HALF_OPEN")
                self.state = self.HALF_OPEN
            else:
                raise ConnectionError(f"Service {self.name} unavailable (circuit open)")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._record_failure()
            return False
        else:
            self._record_success()
            return True
    
    def _should_try_recovery(self) -> bool:
        if not self.last_failure_time:
            return True
        elapsed = (timezone.now() - self.last_failure_time).total_seconds()
        return elapsed > self.recovery_timeout
    
    def _record_failure(self):
        self.failures += 1
        self.last_failure_time = timezone.now()
        if self.failures >= self.failure_threshold:
            self.state = self.OPEN
            logger.error(f"Circuit {self.name} OPEN after {self.failures} failures")
    
    def _record_success(self):
        self.failures = 0
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            logger.info(f"Circuit {self.name} recovered")


# ============================================
# DJANGO-SPECIFIC BULLETPROOF FUNCTIONS
# ============================================

def queryset_exists_safe(queryset) -> bool:
    """Safe queryset.exists() check"""
    try:
        return queryset.exists() if queryset is not None else False
    except Exception:
        return False


def queryset_count_safe(queryset) -> int:
    """Safe queryset.count() check"""
    try:
        return queryset.count() if queryset is not None else 0
    except Exception:
        return 0


def get_object_or_none(model_class, **kwargs):
    """
    Get object or return None - 404 error এড়াতে
    
    আপনার models এ ব্যবহার:
    - Wallet.objects.get(user=user) -> None if not exists
    - UserPaymentMethod.objects.get(id=id) -> None if not exists
    """
    try:
        return model_class.objects.get(**kwargs)
    except (model_class.DoesNotExist, model_class.MultipleObjectsReturned, Exception):
        return None
    
    


# Alias
safe_ip = safe_ip_address

__all__ = [
    'safe_ip',
    'safe_ip_address',
    'safe_decimal',
    'safe_string',
    'safe_int',
    'safe_bool',
    'safe_get',
    'extract_client_ip',
    'CircuitBreaker',
]