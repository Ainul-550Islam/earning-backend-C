# =============================================================================
# fraud_detection/security_helpers.py  — SECURITY & CRYPTO UTILITIES
#
# Renamed from helpers.py to avoid DRY collision with utils/helpers.py.
#
# Contents: crypto, hashing, token generation, request context, risk scoring,
#           caching decorators, retry logic, JSON safe ops.
#
# REMOVED from original helpers.py (now live in validators.py):
#   - validate_email, validate_phone_number, validate_amount, validate_ip_address
#   - ValidationResult (class)  → use validators.ValidationResult instead
# =============================================================================
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import string
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.request import Request

from api.fraud_detection.constants import FRAUD_SCORE_WEIGHTS, RISK_THRESHOLDS
from api.fraud_detection.exceptions import FraudDetectionError

logger = logging.getLogger(__name__)
User   = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN / UUID GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_secure_token(length: int = 32) -> str:
    """Return a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def generate_uuid() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def generate_random_string(length: int = 8, include_digits: bool = True,
                           include_special: bool = False) -> str:
    """Return a random string of the requested length."""
    alphabet = string.ascii_letters
    if include_digits:
        alphabet += string.digits
    if include_special:
        alphabet += string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ─────────────────────────────────────────────────────────────────────────────
# HASHING / ENCRYPTION
# ─────────────────────────────────────────────────────────────────────────────

def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
    """SHA-256 hash of data with optional salt."""
    payload = f"{salt}:{data}" if salt else data
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_hash(data: str, hashed_data: str, salt: Optional[str] = None) -> bool:
    """Constant-time comparison of hash_sensitive_data output."""
    return secrets.compare_digest(hash_sensitive_data(data, salt), hashed_data)


def encrypt_sensitive_field(value: str) -> str:
    """
    Encrypt a sensitive field value.
    Uses Django's SECRET_KEY-derived key via Fernet when available;
    falls back to reversible base64 encoding for environments without
    cryptography installed.
    """
    try:
        from cryptography.fernet import Fernet
        import base64
        key_material = (settings.SECRET_KEY[:32] + "=" * 8).encode()
        key = base64.urlsafe_b64encode(key_material[:32])
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()
    except ImportError:
        import base64
        return base64.b64encode(value.encode()).decode()


def decrypt_sensitive_field(encrypted_value: str) -> str:
    """Inverse of encrypt_sensitive_field."""
    try:
        from cryptography.fernet import Fernet
        import base64
        key_material = (settings.SECRET_KEY[:32] + "=" * 8).encode()
        key = base64.urlsafe_b64encode(key_material[:32])
        f = Fernet(key)
        return f.decrypt(encrypted_value.encode()).decode()
    except ImportError:
        import base64
        return base64.b64decode(encrypted_value.encode()).decode()


# ─────────────────────────────────────────────────────────────────────────────
# CURRENCY / AMOUNT UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def normalize_currency_code(currency: str) -> str:
    return currency.strip().upper()


def format_currency_amount(amount: Union[float, Decimal], currency: str = "USD") -> str:
    return f"{normalize_currency_code(currency)} {Decimal(amount):,.2f}"


def parse_amount_from_string(amount_str: str) -> Optional[Decimal]:
    try:
        cleaned = re.sub(r"[^\d.\-]", "", str(amount_str))
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# DATETIME UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def parse_datetime_string(datetime_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    return None


def get_time_range(period: str) -> Tuple[datetime, datetime]:
    """Return (start, end) for named period: 'hour', 'day', 'week', 'month'."""
    now   = timezone.now()
    deltas = {"hour": timedelta(hours=1), "day": timedelta(days=1),
               "week": timedelta(weeks=1), "month": timedelta(days=30)}
    delta = deltas.get(period, timedelta(days=1))
    return now - delta, now


def format_duration(start_time: datetime,
                    end_time: Optional[datetime] = None) -> str:
    end  = end_time or timezone.now()
    secs = int((end - start_time).total_seconds())
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# RISK SCORING
# ─────────────────────────────────────────────────────────────────────────────

def calculate_risk_score(factors: Dict[str, Any],
                         weights: Optional[Dict[str, float]] = None) -> int:
    """Weighted sum of risk factors, clamped to [0, 100]."""
    w   = weights or FRAUD_SCORE_WEIGHTS
    raw = sum(float(factors.get(k, 0)) * float(w.get(k, 1.0)) for k in factors)
    return min(100, max(0, int(raw)))


def get_risk_level(risk_score: int) -> str:
    if risk_score >= RISK_THRESHOLDS.get("critical", 90):
        return "critical"
    if risk_score >= RISK_THRESHOLDS.get("high", 70):
        return "high"
    if risk_score >= RISK_THRESHOLDS.get("medium", 40):
        return "medium"
    return "low"


def is_high_risk(risk_score: int, threshold: Optional[int] = None) -> bool:
    return risk_score >= (threshold or RISK_THRESHOLDS.get("high", 70))


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST CONTEXT
# ─────────────────────────────────────────────────────────────────────────────

def get_client_ip(request: Union[HttpRequest, Request]) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return xff or request.META.get("REMOTE_ADDR", "0.0.0.0")


def get_user_agent(request: Union[HttpRequest, Request]) -> str:
    return request.META.get("HTTP_USER_AGENT", "")


def get_request_context(request: Union[HttpRequest, Request]) -> Dict[str, Any]:
    return {
        "ip_address":     get_client_ip(request),
        "user_agent":     get_user_agent(request),
        "method":         request.method,
        "path":           getattr(request, "path", ""),
        "user_id":        getattr(getattr(request, "user", None), "id", None),
        "timestamp":      timezone.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CACHING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def cache_key(*args, **kwargs) -> str:
    parts = [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
    raw   = "|".join(parts)
    return f"fraud:{hashlib.md5(raw.encode()).hexdigest()}"


def cached_result(timeout: int = 300, key_func: Optional[Callable] = None):
    """Decorator: cache function return value in Django's cache backend."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            k    = key_func(*args, **kwargs) if key_func else cache_key(func.__name__, *args, **kwargs)
            hit  = cache.get(k)
            if hit is not None:
                return hit
            result = func(*args, **kwargs)
            cache.set(k, result, timeout)
            return result
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# DB / TRANSACTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def atomic_transaction():
    """Context manager wrapping django.db.transaction.atomic."""
    with transaction.atomic():
        yield


def bulk_create_with_chunks(model_class, objects: List[Any],
                            chunk_size: int = 1_000) -> int:
    """Bulk-create in chunks to avoid large INSERT statements."""
    created = 0
    for i in range(0, len(objects), chunk_size):
        chunk    = objects[i : i + chunk_size]
        created += len(model_class.objects.bulk_create(chunk, ignore_conflicts=True))
    return created


# ─────────────────────────────────────────────────────────────────────────────
# STRING UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    text = re.sub(r"[<>\"'&]", "", str(text)).strip()
    return text[:max_length] if max_length else text


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def log_fraud_event(event_type: str, user_id: Optional[Union[int, str]],
                    details: Optional[Dict[str, Any]] = None,
                    severity: str = "info") -> None:
    log = getattr(logger, severity, logger.info)
    log("FRAUD_EVENT type=%s user=%s details=%s", event_type, user_id, details or {})


def log_performance(func_name: str, duration: float,
                    details: Optional[Dict[str, Any]] = None) -> None:
    logger.debug("PERF func=%s duration=%.3fs details=%s", func_name, duration, details or {})


# ─────────────────────────────────────────────────────────────────────────────
# RETRY / TIMING DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator: retry function on exception with exponential back-off."""
    import time

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_retries:
                        raise
                    logger.warning("Attempt %d/%d failed: %s", attempt + 1, max_retries, exc)
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


def timing_decorator(func):
    """Decorator: log execution time of a function."""
    import time

    @wraps(func)
    def wrapper(*args, **kwargs):
        start  = time.perf_counter()
        result = func(*args, **kwargs)
        log_performance(func.__name__, time.perf_counter() - start)
        return result
    return wrapper
