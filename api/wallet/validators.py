# api/wallet/validators.py
"""
🛡️ Bulletproof Validators for Wallet App
"""

import re
import socket
import logging
from typing import Optional, Any, Tuple
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ==========================================
# IP Address Validation
# ==========================================

# IP Regex Patterns
IPV4_PATTERN = re.compile(
    r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)

IPV6_PATTERN = re.compile(
    r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|'
    r'^::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$|'
    r'^(?:[0-9a-fA-F]{1,4}:){1,7}:$'
)


def is_valid_ipv4(ip: str) -> bool:
    """Check if IP is valid IPv4"""
    try:
        return bool(IPV4_PATTERN.match(str(ip)))
    except:
        return False


def is_valid_ipv6(ip: str) -> bool:
    """Check if IP is valid IPv6"""
    try:
        return bool(IPV6_PATTERN.match(str(ip)))
    except:
        return False


def safe_ip_address(ip: Optional[str], default: str = '0.0.0.0') -> str:
    """
    🛡️ Bulletproof IP validation
    """
    if ip is None or ip == '':
        return default
    
    try:
        ip_str = str(ip).strip()
    except:
        return default
    
    invalid_values = [
        'invalid_ip', 'invalid', 'unknown', 'none', 
        'null', 'n/a', 'na', '0', 'undefined'
    ]
    if ip_str.lower() in invalid_values:
        return default
    
    localhost_values = ['localhost', '::1', '0:0:0:0:0:0:0:1']
    if ip_str.lower() in localhost_values:
        return '127.0.0.1'
    
    if is_valid_ipv4(ip_str):
        return ip_str
    
    if is_valid_ipv6(ip_str):
        return ip_str
    
    try:
        from django.core.validators import validate_ipv46_address
        validate_ipv46_address(ip_str)
        return ip_str
    except:
        pass
    
    try:
        resolved = socket.gethostbyname(ip_str)
        if is_valid_ipv4(resolved):
            return resolved
    except:
        pass
    
    logger.warning(f"Invalid IP '{ip_str}', using default '{default}'")
    return default


def extract_client_ip(request) -> str:
    """Extract client IP from Django request"""
    headers = [
        'HTTP_X_FORWARDED_FOR',
        'HTTP_X_REAL_IP',
        'HTTP_CLIENT_IP',
        'REMOTE_ADDR',
    ]
    
    for header in headers:
        ip = request.META.get(header)
        
        if not ip:
            continue
        
        if ',' in str(ip):
            ip = ip.split(',')[0].strip()
        
        validated = safe_ip_address(ip, default=None)
        if validated and validated != '0.0.0.0':
            return validated
    
    return '127.0.0.1'


# ==========================================
# Decimal/Amount Validation
# ==========================================

def safe_decimal(value: Any, default: Decimal = Decimal('0.00')) -> Decimal:
    """Safely convert to Decimal"""
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        logger.warning(f"Failed to convert {value} to Decimal")
        return default


def validate_amount(
    amount: Any, 
    min_amount: Decimal = Decimal('0.01'),
    max_amount: Optional[Decimal] = None
) -> Tuple[bool, str, Optional[Decimal]]:
    """Validate transaction amount"""
    try:
        decimal_amount = safe_decimal(amount, default=None)
        
        if decimal_amount is None:
            return False, "Invalid amount format", None
        
        if decimal_amount <= 0:
            return False, "Amount must be greater than 0", None
        
        if decimal_amount < min_amount:
            return False, f"Minimum amount is {min_amount}", None
        
        if max_amount is not None and decimal_amount > max_amount:
            return False, f"Maximum amount is {max_amount}", None
        
        return True, "", decimal_amount
    except:
        return False, "Invalid amount format", None


# ==========================================
# Safe Type Conversions
# ==========================================

def safe_string(value: Any, default: str = '', max_length: Optional[int] = None) -> str:
    """Safely convert to string"""
    try:
        if value is None:
            return default
        result = str(value).strip()
        if max_length and len(result) > max_length:
            result = result[:max_length]
        return result
    except:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert to integer"""
    try:
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Safely convert to boolean"""
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on', 'enabled']
        return bool(value)
    except:
        return default


def safe_get(
    dictionary: dict, 
    key: str, 
    default: Any = None,
    convert_to: Optional[type] = None
) -> Any:
    """Safe dictionary access"""
    try:
        value = dictionary.get(key, default)
        
        if convert_to is None:
            return value
        
        if convert_to == int:
            return safe_int(value, default if isinstance(default, int) else 0)
        elif convert_to == str:
            return safe_string(value, default if isinstance(default, str) else '')
        elif convert_to == bool:
            return safe_bool(value, default if isinstance(default, bool) else False)
        elif convert_to == Decimal:
            return safe_decimal(value, default if isinstance(default, Decimal) else Decimal('0'))
        else:
            return convert_to(value)
    except:
        return default


# ==========================================
# Circuit Breaker
# ==========================================

class CircuitBreaker:
    """Circuit Breaker Pattern"""
    CLOSED = 'CLOSED'
    OPEN = 'OPEN'
    HALF_OPEN = 'HALF_OPEN'
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = self.CLOSED
        self.last_failure_time = None
    
    def call(self, func, *args, **kwargs):
        """Execute with circuit breaker"""
        if self.state == self.OPEN:
            if self._should_attempt_reset():
                self.state = self.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        self.failure_count = 0
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
    
    def _on_failure(self):
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
    
    def _should_attempt_reset(self):
        import time
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout