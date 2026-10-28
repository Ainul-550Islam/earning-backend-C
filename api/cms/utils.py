# api/cms/utils.py
"""Comprehensive utilities for CMS."""
import logging
import re
import uuid
import hashlib
import secrets
import json
import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
from urllib.parse import urlparse, parse_qs
from django.utils import timezone
from django.conf import settings
from django.core.validators import validate_email, URLValidator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str, force_bytes
from django.utils.text import slugify
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Original Utilities (Preserved) ─────────────────────────────────────

class Sentinel:
    """Sentinel Pattern"""
    _instances = {}
    
    def __new__(cls, name: str):
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
            cls._instances[name].name = name
        return cls._instances[name]
    
    def __bool__(self):
        return False
    
    def __repr__(self):
        return f"<Sentinel: {self.name}>"


NOT_FOUND = Sentinel("NOT_FOUND")
MISSING = Sentinel("MISSING")
INVALID = Sentinel("INVALID")
LOCKED = Sentinel("LOCKED")


def safe_int(value: Any, default: int = 0) -> int:
    """Convert to int safely"""
    if value is None or isinstance(value, Sentinel):
        return default
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return int(float(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Convert to string safely"""
    if value is None or isinstance(value, Sentinel):
        return default
    try:
        return str(value).strip()
    except Exception:
        return default


def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """[MONEY] Convert to Decimal safely"""
    if value is None or isinstance(value, Sentinel):
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """[OK] Convert to boolean safely"""
    if value is None or isinstance(value, Sentinel):
        return default
    if isinstance(value, bool):
        return value
    try:
        val = str(value).lower().strip()
        return val in ('true', '1', 'yes', 'on', 'y', 't')
    except Exception:
        return default


def safe_now() -> datetime:
    """Get current time with timezone safely"""
    try:
        return timezone.now()
    except Exception:
        from django.utils.timezone import now
        return now()


# ── Enhanced String Utilities ─────────────────────────────────────

class StringUtils:
    """String manipulation and validation utilities."""
    
    @staticmethod
    def clean_string(text: str, remove_spaces: bool = False) -> str:
        """Clean string by removing special characters."""
        if not text:
            return ""
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        if remove_spaces:
            clean_text = re.sub(r'\s+', '', clean_text)
        
        return clean_text
    
    @staticmethod
    def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
        """Truncate string to specified length."""
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def slugify_custom(text: str, max_length: int = 50) -> str:
        """Custom slugify function."""
        return slugify(text)[:max_length]
    
    @staticmethod
    def extract_numbers(text: str) -> List[str]:
        """Extract all numbers from string."""
        return re.findall(r'\d+', text)
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text."""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email address."""
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Validate URL."""
        try:
            URLValidator()(url)
            return True
        except ValidationError:
            return False
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number."""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Remove leading +1 if present (US normalization)
        if digits_only.startswith('1') and len(digits_only) == 11:
            digits_only = digits_only[1:]
        
        return digits_only
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Mask sensitive data showing only last few characters."""
        if not data or len(data) <= visible_chars:
            return data
        
        mask_length = len(data) - visible_chars
        return mask_char * mask_length + data[-visible_chars:]


# ── Enhanced Date/Time Utilities ─────────────────────────────────────

class DateUtils:
    """Date and time utilities."""
    
    @staticmethod
    def now_utc() -> datetime.datetime:
        """Get current UTC time."""
        return timezone.now()
    
    @staticmethod
    def to_utc(dt: datetime.datetime) -> datetime.datetime:
        """Convert datetime to UTC."""
        if timezone.is_aware(dt):
            return dt.astimezone(timezone.utc)
        return timezone.make_aware(dt, timezone.utc)
    
    @staticmethod
    def to_user_timezone(dt: datetime.datetime, user) -> datetime.datetime:
        """Convert datetime to user's timezone."""
        try:
            user_tz = user.profile.timezone if hasattr(user, 'profile') else 'UTC'
            return timezone.localtime(dt, timezone=user_tz)
        except Exception:
            return dt
    
    @staticmethod
    def format_datetime(dt: datetime.datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
        """Format datetime to string."""
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime(format_str)
    
    @staticmethod
    def parse_date_string(date_str: str, format_str: str = '%Y-%m-%d') -> Optional[datetime.datetime]:
        """Parse date string to datetime."""
        try:
            dt = datetime.datetime.strptime(date_str, format_str)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            return None
    
    @staticmethod
    def get_time_ago(dt: datetime.datetime) -> str:
        """Get human-readable time ago string."""
        if not dt:
            return "Never"

        now = timezone.now()
        diff = now - dt
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return "Just now"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.days < 30:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.days < 365:
            months = diff.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = diff.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"

    @staticmethod
    def get_date_range(period: str):
        """Return a (start, end) datetime tuple for the named period.

        Supported periods: 'today', 'yesterday', 'week', 'month', 'year'.
        Tests call ``DateUtils.get_date_range('today')`` and expect a 2-tuple
        of aware datetimes where ``end > start``.
        """
        now  = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        if period == 'today':
            return today_start, today_end
        elif period == 'yesterday':
            d = today_start - datetime.timedelta(days=1)
            return d, d.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start = today_start - datetime.timedelta(days=today_start.weekday())
            end   = start + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
            return start, end
        elif period == 'month':
            start = today_start.replace(day=1)
            import calendar
            last_day = calendar.monthrange(start.year, start.month)[1]
            end = start.replace(day=last_day, hour=23, minute=59, second=59)
            return start, end
        elif period == 'year':
            start = today_start.replace(month=1, day=1)
            end   = today_start.replace(month=12, day=31, hour=23, minute=59, second=59)
            return start, end
        else:
            return today_start, today_end


# ── Enhanced Number Utilities ─────────────────────────────────────

class NumberUtils:
    """Number manipulation and validation utilities."""
    
    @staticmethod
    def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
        """Safely convert value to Decimal."""
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return default
    
    @staticmethod
    def format_currency(amount: Union[float, Decimal, int], currency: str = 'USD') -> str:
        """Format amount as currency."""
        try:
            amount_decimal = Decimal(str(amount))
            formatted = f"{amount_decimal:,.2f}"
            return f"{currency} {formatted}"
        except (InvalidOperation, ValueError):
            return f"{currency} 0.00"
    
    @staticmethod
    def format_percentage(value: Union[float, Decimal], decimal_places: int = 2) -> str:
        """Format value as percentage."""
        try:
            value_decimal = Decimal(str(value))
            formatted = f"{value_decimal:.{decimal_places}f}%"
            return formatted
        except (InvalidOperation, ValueError):
            return "0.00%"
    
    @staticmethod
    def calculate_percentage(part: Union[float, Decimal], 
                         total: Union[float, Decimal], 
                         decimal_places: int = 2) -> Decimal:
        """Calculate percentage."""
        try:
            part_decimal = Decimal(str(part))
            total_decimal = Decimal(str(total))
            
            if total_decimal == 0:
                return Decimal('0')
            
            percentage = (part_decimal / total_decimal) * Decimal('100')
            return percentage.quantize(Decimal(f'0.{"0" * decimal_places}'))
        except (InvalidOperation, ValueError, ZeroDivisionError):
            return Decimal('0')
    
    @staticmethod
    def round_decimal(value: Union[float, Decimal], decimal_places: int = 2) -> Decimal:
        """Round decimal to specified places."""
        try:
            value_decimal = Decimal(str(value))
            return value_decimal.quantize(Decimal(f'0.{"0" * decimal_places}'))
        except (InvalidOperation, ValueError):
            return Decimal('0')
    
    @staticmethod
    def is_positive_number(value: Any) -> bool:
        """Check if value is positive number."""
        try:
            num = float(value)
            return num > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def generate_random_number(min_val: int, max_val: int) -> int:
        """Generate random number in range."""
        return secrets.randbelow(max_val - min_val + 1) + min_val


# ── Utility Manager ─────────────────────────────────────

class UtilityManager:
    """Central utility manager with sub-managers as properties."""

    @property
    def validation(self):
        return ValidationUtils

    @property
    def security(self):
        return SecurityUtils

    @property
    def strings(self):
        return StringUtils

    @property
    def dates(self):
        return DateUtils

    @property
    def numbers(self):
        return NumberUtils

    """Manager for accessing all utility classes."""
    
    def __init__(self):
        """Initialize utility manager."""
        self.string = StringUtils
        self.date = DateUtils
        self.number = NumberUtils
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_utility(self, utility_name: str):
        """Get utility class by name."""
        return getattr(self, utility_name, None)


# Global utility manager
utils = UtilityManager()

class ValidationUtils:
    """Validation helpers used across CMS."""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        import re
        pattern = re.compile(
            r'^(https?://)?'
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
            r'(/[^\s]*)?$'
        )
        return bool(pattern.match(url or ''))

    @staticmethod
    def is_valid_slug(slug: str) -> bool:
        import re
        return bool(re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug or ''))

    @staticmethod
    def is_valid_email(email: str) -> bool:
        import re
        return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', email or ''))

    @staticmethod
    def sanitize_html(html: str, allowed_tags: list = None) -> str:
        """Strip dangerous tags from HTML (basic)."""
        import re
        # Remove script/iframe/object tags
        clean = re.sub(r'<(script|iframe|object|embed)[^>]*>.*?</>', '', html or '', flags=re.DOTALL|re.IGNORECASE)
        clean = re.sub(r'<(script|iframe|object|embed)[^>]*/>', '', clean, flags=re.IGNORECASE)
        return clean

    @staticmethod
    def validate_file_extension(filename: str, allowed: list = None) -> bool:
        allowed = allowed or ['jpg','jpeg','png','gif','pdf','mp4','webm']
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        return ext in allowed


    @staticmethod
    def validate_phone_number(phone: str, country: str = '') -> bool | dict:
        """Validate a phone number, optionally for a specific country.

        When called with just a phone string the original boolean return is
        preserved.  When called with a country string (e.g. ``"US"``) the method
        returns a dict ``{is_valid, formatted, errors}`` matching the richer
        interface expected by ``test_validate_phone_number``.
        """
        import re
        clean = re.sub(r'[\s\-\(\)\+]', '', phone or '')
        if not country:
            return clean.isdigit() and 7 <= len(clean) <= 15

        errors: list = []
        formatted = phone
        if country == 'US':
            digits = re.sub(r'\D', '', phone or '')
            if len(digits) != 10:
                errors.append('US phone number must have 10 digits')
            else:
                formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        else:
            if not (clean.isdigit() and 7 <= len(clean) <= 15):
                errors.append('Invalid phone number')
        return {'is_valid': len(errors) == 0, 'formatted': formatted, 'errors': errors}

    @staticmethod
    def validate_username(username: str) -> dict:
        """Validate a username; return ``{is_valid, errors}``."""
        import re
        errors: list = []
        if len(username) < 3:
            errors.append('Username must be at least 3 characters')
        if len(username) > 150:
            errors.append('Username must be at most 150 characters')
        if not re.match(r'^[a-zA-Z0-9_]+$', username or ''):
            errors.append('Username can only contain letters, numbers, and underscores')
        return {'is_valid': len(errors) == 0, 'errors': errors}

    @staticmethod
    def validate_password_strength(password: str) -> dict:
        """Score password strength; return ``{is_valid, strength, score, errors}``."""
        import re
        errors: list = []
        score = 0
        if len(password) < 8:
            errors.append('Password must be at least 8 characters')
        else:
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'\d', password):
            score += 1
        if re.search(r'[^a-zA-Z0-9]', password):
            score += 1

        if score <= 1:
            strength = 'Very Weak'
        elif score == 2:
            strength = 'Weak'
        elif score == 3:
            strength = 'Fair'
        elif score == 4:
            strength = 'Good'
        else:
            strength = 'Strong'

        return {
            'is_valid': len(errors) == 0 and score >= 3,
            'strength': strength,
            'score': score,
            'errors': errors,
        }

    @staticmethod
    def validate_json(data) -> bool:
        """Return True if data is valid JSON-serialisable."""
        import json
        try:
            json.dumps(data)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def validate_date_range(start, end) -> bool:
        return start is not None and end is not None and start <= end

    @staticmethod
    def validate_positive_decimal(value) -> bool:
        from decimal import Decimal
        try:
            return Decimal(str(value)) > 0
        except Exception:
            return False

    @staticmethod
    def clamp(value, min_val, max_val):
        return max(min_val, min(max_val, value))


class SecurityUtils:
    """Security helpers for CMS."""

    @staticmethod
    def generate_token(length: int = 32) -> str:
        import secrets
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_csrf_token() -> str:
        """Generate a URL-safe CSRF token (32 random bytes → 43-char base64url string).

        Tests assert ``len(token) == 43`` and that successive calls differ.
        ``secrets.token_urlsafe(32)`` produces exactly 43 URL-safe base64 chars.
        """
        import secrets
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_nonce(length: int = 16) -> str:
        """Generate a hex nonce string.  Default ``length=16`` → 32 hex chars."""
        import secrets
        return secrets.token_hex(length)

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session identifier — 43-char URL-safe base64 string.
        Tests assert len(session_id) == 43; secrets.token_urlsafe(32) produces exactly that.
        """
        import secrets
        return secrets.token_urlsafe(32)

    @staticmethod
    def secure_compare(a: str, b: str) -> bool:
        """Constant-time string comparison (alias for constant_time_compare)."""
        import hmac
        return hmac.compare_digest(a.encode(), b.encode())

    @staticmethod
    def hash_value(value: str, salt: str = '') -> str:
        import hashlib
        return hashlib.sha256(f'{salt}{value}'.encode()).hexdigest()

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        import hmac
        return hmac.compare_digest(a.encode(), b.encode())

    @staticmethod
    def mask_email(email: str) -> str:
        if '@' not in email:
            return '***'
        name, domain = email.split('@', 1)
        masked = name[0] + '***' + (name[-1] if len(name) > 1 else '')
        return f'{masked}@{domain}'

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        import re
        return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)


# Convenience singleton alias used by some tests
utils = UtilityManager()


def time_since(dt) -> str:
    """Return human-readable time since dt."""
    from django.utils import timezone
    import math
    now = timezone.now()
    diff = now - dt
    seconds = int(diff.total_seconds())
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if seconds < 60:
        return f'{seconds} seconds ago'
    elif minutes < 60:
        return f'{minutes} minutes ago'
    elif hours < 24:
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif days < 7:
        return f'{days} day{"s" if days != 1 else ""} ago'
    else:
        return dt.strftime('%Y-%m-%d')
