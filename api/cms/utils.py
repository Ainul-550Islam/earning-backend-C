# ================================================
# 🛡️ CMS UTILITIES - BULLETPROOF VERSION
# ================================================

import logging
from decimal import Decimal
from typing import Any, Optional, Dict
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)


class Sentinel:
    """🔷 Sentinel Pattern"""
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
    """🔢 Convert to int safely"""
    if value is None or isinstance(value, Sentinel):
        return default
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        return int(float(str(value).strip()))
    except (ValueError, TypeError, AttributeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """[NOTE] Convert to string safely"""
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
    """⏰ Get current time with timezone safely"""
    try:
        return timezone.now()
    except Exception:
        from django.utils.timezone import now
        return now()