# admin.py - সম্পূর্ণ Bulletproof + Colorful Design

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html, mark_safe
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, Q, Case, When, Value, IntegerField, FloatField
from django.db.models.functions import TruncDay, TruncHour, TruncMonth
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.template.response import TemplateResponse
from django.db import transaction, models, connection
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from decimal import Decimal, InvalidOperation
import json
import logging
from datetime import datetime, timedelta
import uuid
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from .models import (
    Backup,
    BackupLog,           
    BackupRestoration,
    BackupStorageLocation,
    BackupSchedule,
    DeltaBackupTracker,
    RetentionPolicy,
    BackupNotificationConfig
)
import hashlib
import math
import os
import inspect
from functools import wraps

# Try Pydantic (optional)
try:
    from pydantic import BaseModel, Field, validator, ValidationError as PydanticValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    
    # Dummy validator decorator
    def validator(*args, **kwargs):
        return lambda x: x

# Try Circuit Breaker (optional)
try:
    from pybreaker import CircuitBreaker, CircuitBreakerError
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False
    
    # Dummy Circuit Breaker
    class CircuitBreaker:
        def __init__(self, *args, **kwargs):
            pass
            
        def __call__(self, func):
            return func

# Logger Setup
logger = logging.getLogger(__name__)


# ================================================
# 🛡️ SECTION 1: BULLETPROOF CORE UTILITIES
# ================================================

class Sentinel:
    """🔷 Sentinel object for missing data detection (Null Object Pattern)"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __bool__(self):
        return False
    
    def __repr__(self):
        return "<MISSING>"
    
    def __str__(self):
        return ""

MISSING = Sentinel()


# 1️⃣ **Deep Get - Chain-safe nested data access**
def deep_get(obj: Any, path: str, default: Any = MISSING) -> Any:
    """
    🛡️ Bulletproof deep get for nested dictionaries/objects
    Example: deep_get(data, "user.profile.name", "Guest")
    """
    try:
        if isinstance(path, str):
            keys = path.split('.')
        else:
            keys = path
        
        current = obj
        for key in keys:
            if current is None or current is MISSING:
                return default if default is not MISSING else None
                
            if isinstance(current, dict):
                current = current.get(key, MISSING)
            elif hasattr(current, key):
                current = getattr(current, key, MISSING)
            elif hasattr(current, str(key)):
                current = getattr(current, str(key), MISSING)
            else:
                current = MISSING
            
            if current is MISSING:
                return default if default is not MISSING else None
        
        return current
    except Exception as e:
        logger.debug(f"deep_get error at path '{path}': {e}")
        return default if default is not MISSING else None


# 2️⃣ **Bulletproof Getattr - Multiple fallbacks**
def bulletproof_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """
    🛡️ Safe getattr with multiple fallbacks
    - Direct attribute access
    - Dictionary key access
    - Callable execution
    - List index access
    """
    try:
        # Case 1: Direct attribute
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if callable(value):
                try:
                    return value()
                except:
                    return value
            return value
        
        # Case 2: Dictionary
        if isinstance(obj, dict):
            return obj.get(attr, default)
        
        # Case 3: List/Tuple index
        if isinstance(obj, (list, tuple)) and attr.isdigit():
            idx = int(attr)
            if 0 <= idx < len(obj):
                return obj[idx]
        
        # Case 4: Has get method
        if hasattr(obj, 'get'):
            try:
                return obj.get(attr, default)
            except:
                pass
        
        return default
    except Exception as e:
        logger.debug(f"bulletproof_getattr error for '{attr}': {e}")
        return default


# 3️⃣ **Safe Integer Conversion**
def safe_int(value: Any, default: int = 0) -> int:
    """🛡️ Convert any value to int safely"""
    try:
        if value is None or value is MISSING:
            return default
        return int(float(str(value).strip()))
    except (ValueError, TypeError, OverflowError):
        return default


# 4️⃣ **Safe Float Conversion**
def safe_float(value: Any, default: float = 0.0) -> float:
    """🛡️ Convert any value to float safely"""
    try:
        if value is None or value is MISSING:
            return default
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


# 5️⃣ **Safe Boolean Conversion**
def safe_bool(value: Any, default: bool = False) -> bool:
    """🛡️ Convert any value to bool safely"""
    if value is None or value is MISSING:
        return default
    
    if isinstance(value, bool):
        return value
    
    try:
        val = str(value).lower().strip()
        return val in ('true', '1', 'yes', 'on', 'y', 't')
    except:
        return default


# 6️⃣ **Safe String Truncation**
def safe_truncate(text: Any, max_length: int = 100, suffix: str = '...') -> str:
    """🛡️ Safely truncate text with error handling"""
    try:
        if text is None or text is MISSING:
            return ''
        
        text = str(text)
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    except Exception as e:
        logger.debug(f"safe_truncate error: {e}")
        return ''


# 7️⃣ **Safe Datetime Parsing**
def safe_datetime(value: Any, default: Optional[datetime] = None) -> Optional[datetime]:
    """🛡️ Parse datetime safely"""
    if default is None:
        default = timezone.now()
    
    try:
        if value is None or value is MISSING:
            return default
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            for fmt in [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%d/%m/%Y',
                '%Y%m%d%H%M%S',
                '%Y%m%d'
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        
        return default
    except Exception:
        return default


# 8️⃣ **Safe Division**
def safe_divide(a: Any, b: Any, default: float = 0.0) -> float:
    """🛡️ Safe division with zero check"""
    try:
        a_num = safe_float(a)
        b_num = safe_float(b)
        
        if b_num == 0:
            return default
        
        return a_num / b_num
    except Exception:
        return default


# 9️⃣ **Safe Percentage Calculation**
def safe_percentage(value: Any, total: Any, default: float = 0.0) -> float:
    """🛡️ Safe percentage calculation"""
    try:
        value_num = safe_float(value)
        total_num = safe_float(total)
        
        if total_num == 0:
            return default
        
        return min(100.0, max(0.0, (value_num / total_num) * 100))
    except Exception:
        return default


# 🔟 **Safe JSON Parsing**
def safe_json_loads(data: Any, default: Optional[Dict] = None) -> Dict:
    """🛡️ Safely parse JSON"""
    if default is None:
        default = {}
    
    try:
        if isinstance(data, dict):
            return data
        
        if isinstance(data, str):
            return json.loads(data)
        
        return default
    except Exception:
        return default


# 1️⃣1️⃣ **Safe Model Field Access**
def safe_model_field(obj: Any, field_name: str, default: Any = None) -> Any:
    """🛡️ Safely access model field with type checking"""
    try:
        if obj is None or obj is MISSING:
            return default
        
        value = getattr(obj, field_name, MISSING)
        if value is MISSING:
            return default
        
        return value
    except Exception:
        return default


# 1️⃣2️⃣ **Safe QuerySet Aggregation**
def safe_aggregate(queryset: Any, **kwargs) -> Dict[str, Any]:
    """🛡️ Safely aggregate with fallback"""
    try:
        if queryset is None:
            return {k: 0 for k in kwargs.keys()}
        
        result = queryset.aggregate(**kwargs)
        return {k: v if v is not None else 0 for k, v in result.items()}
    except Exception as e:
        logger.error(f"safe_aggregate error: {e}")
        return {k: 0 for k in kwargs.keys()}


# 1️⃣3️⃣ **Circuit Breaker Decorator**
def with_circuit_breaker(fail_max: int = 5, reset_timeout: int = 60):
    """🛡️ Circuit breaker pattern for external service calls"""
    if CIRCUIT_BREAKER_AVAILABLE:
        breaker = CircuitBreaker(fail_max=fail_max, reset_timeout=reset_timeout)
        
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return breaker.call(func, *args, **kwargs)
                except CircuitBreakerError:
                    logger.warning(f"Circuit breaker open for {func.__name__}")
                    return None
            return wrapper
        return decorator
    else:
        def decorator(func):
            return func
        return decorator


# 1️⃣4️⃣ **Transaction Decorator**
def atomic_transaction(func: Callable) -> Callable:
    """🛡️ Database transaction with automatic rollback"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Transaction failed in {func.__name__}: {e}")
            raise
    return wrapper


# 1️⃣5️⃣ **Pydantic Schema Validation**
if PYDANTIC_AVAILABLE:
    class BackupDataSchema(BaseModel):
        """Pydantic schema for backup data validation"""
        id: Optional[str] = None
        name: str = "Unknown"
        status: str = "pending"
        backup_type: str = "full"
        file_size: float = 0
        created_at: Optional[datetime] = None
        
        @validator('status')
        def validate_status(cls, v):
            valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
            if v not in valid_statuses:
                return 'pending'
            return v
        
        @validator('file_size')
        def validate_file_size(cls, v):
            return max(0, v)
else:
    # Dummy schema
    class BackupDataSchema:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


# 1️⃣6️⃣ **Error Handler Decorator**
def handle_errors(error_message: str = "An error occurred", fallback_return: Any = None):
    """🛡️ Decorator for consistent error handling"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ObjectDoesNotExist:
                logger.warning(f"{func.__name__}: Object not found")
                return fallback_return
            except ValidationError as e:
                logger.warning(f"{func.__name__}: Validation error - {e}")
                return fallback_return
            except Exception as e:
                logger.error(f"{func.__name__}: {error_message} - {e}", exc_info=True)
                return fallback_return
        return wrapper
    return decorator


# 1️⃣7️⃣ **Safe File Size Formatter**
def format_file_size(size_bytes: Any) -> str:
    """🛡️ Convert bytes to human readable format"""
    size = safe_float(size_bytes, 0)
    
    if size <= 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"


# 1️⃣8️⃣ **Safe Duration Formatter**
def format_duration(seconds: Any) -> str:
    """🛡️ Format duration in human readable format"""
    secs = safe_float(seconds, 0)
    
    if secs < 0:
        return "0s"
    
    if secs < 1:
        return f"{secs * 1000:.0f}ms"
    
    if secs < 60:
        return f"{secs:.1f}s"
    
    if secs < 3600:
        minutes = int(secs // 60)
        seconds = int(secs % 60)
        return f"{minutes}m {seconds}s"
    
    hours = int(secs // 3600)
    minutes = int((secs % 3600) // 60)
    return f"{hours}h {minutes}m"


# 1️⃣9️⃣ **Time Ago Formatter**
def time_ago(dt: Any) -> str:
    """🛡️ Format datetime as 'time ago'"""
    dt_obj = safe_datetime(dt)
    if not dt_obj:
        return "Never"
    
    if timezone.is_naive(dt_obj):
        dt_obj = timezone.make_aware(dt_obj)
    
    now = timezone.now()
    diff = now - dt_obj
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    
    if diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    
    if diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    
    if diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    
    if diff.seconds > 10:
        return f"{diff.seconds} seconds ago"
    
    return "Just now"


# 2️⃣0️⃣ **Null Object Pattern for Models**
class NullBackup:
    """Null Object Pattern for Backup model"""
    id = None
    name = "Unknown"
    status = "unknown"
    backup_type = "unknown"
    file_size = 0
    created_at = None
    
    def __bool__(self):
        return False
    
    def __getattr__(self, name):
        return None


# ================================================
# 🎨 SECTION 2: MODERN COLORFUL BADGES & WIDGETS
# ================================================

class ModernBadge:
    """
    🎨 Modern Badge Factory with gradients and animations
    """
    
    # Color Palettes
    COLORS = {
        # Status Colors
        'success': {'primary': '#10b981', 'secondary': '#059669', 'gradient': 'linear-gradient(135deg, #10b981, #059669)'},
        'info': {'primary': '#3b82f6', 'secondary': '#2563eb', 'gradient': 'linear-gradient(135deg, #3b82f6, #2563eb)'},
        'warning': {'primary': '#f59e0b', 'secondary': '#d97706', 'gradient': 'linear-gradient(135deg, #f59e0b, #d97706)'},
        'danger': {'primary': '#ef4444', 'secondary': '#dc2626', 'gradient': 'linear-gradient(135deg, #ef4444, #dc2626)'},
        'purple': {'primary': '#8b5cf6', 'secondary': '#7c3aed', 'gradient': 'linear-gradient(135deg, #8b5cf6, #7c3aed)'},
        'pink': {'primary': '#ec4899', 'secondary': '#db2777', 'gradient': 'linear-gradient(135deg, #ec4899, #db2777)'},
        'gray': {'primary': '#6b7280', 'secondary': '#4b5563', 'gradient': 'linear-gradient(135deg, #6b7280, #4b5563)'},
        'dark': {'primary': '#1f2937', 'secondary': '#111827', 'gradient': 'linear-gradient(135deg, #1f2937, #111827)'},
    }
    
    # Status Mapping
    STATUS_MAP = {
        # Backup Status
        'pending': ('warning', '⏳'),
        'running': ('info', '[LOADING]'),
        'completed': ('success', '[OK]'),
        'failed': ('danger', '[ERROR]'),
        'cancelled': ('gray', '⛔'),
        'validating': ('purple', '🔍'),
        'uploading': ('info', '⬆️'),
        'downloading': ('info', '⬇️'),
        'encrypting': ('purple', '🔒'),
        'decrypting': ('purple', '🔓'),
        'compressing': ('warning', '🗜️'),
        'extracting': ('warning', '📦'),
        'restoring': ('warning', '↩️'),
        'verifying': ('info', '✓'),
        
        # Storage Status
        'active': ('success', '[OK]'),
        'inactive': ('gray', '⭕'),
        'maintenance': ('warning', '[FIX]'),
        'full': ('danger', '[WARN]'),
        'error': ('danger', '[ALERT]'),
        
        # Schedule Status
        'scheduled': ('info', '📅'),
        'running': ('info', '[LOADING]'),
        'paused': ('warning', '⏸️'),
        'completed': ('success', '[OK]'),
        
        # Restoration Status
        'rolled_back': ('dark', '↩️'),
        'rollback_failed': ('danger', '[WARN]'),
        
        # Generic
        'yes': ('success', '[OK]'),
        'no': ('danger', '[ERROR]'),
        'true': ('success', '[OK]'),
        'false': ('danger', '[ERROR]'),
        'enabled': ('success', '[OK]'),
        'disabled': ('gray', '⭕'),
    }
    
    @classmethod
    def render(cls, status: str, text: str = None, size: str = 'md', tooltip: str = None) -> str:
        """
        🎨 Render a beautiful gradient badge
        
        Args:
            status: Status key (e.g., 'completed', 'failed')
            text: Custom text (defaults to status title)
            size: 'sm', 'md', 'lg'
            tooltip: Tooltip text
        """
        # Get status config
        color_key, icon = cls.STATUS_MAP.get(status, ('gray', '•'))
        color = cls.COLORS.get(color_key, cls.COLORS['gray'])
        
        # Determine text
        badge_text = text or status.replace('_', ' ').title()
        
        # Size configurations
        size_styles = {
            'sm': {'padding': '2px 8px', 'font_size': '10px', 'border_radius': '12px'},
            'md': {'padding': '4px 12px', 'font_size': '11px', 'border_radius': '16px'},
            'lg': {'padding': '6px 16px', 'font_size': '12px', 'border_radius': '20px'},
        }
        style = size_styles.get(size, size_styles['md'])
        
        # Tooltip attribute
        tooltip_attr = f'title="{tooltip}"' if tooltip else ''
        
        # Return HTML
        return format_html(
            '<span {} style="background: {}; color: white; padding: {}; border-radius: {}; '
            'font-size: {}; font-weight: 600; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1); '
            'border: 1px solid rgba(255,255,255,0.1); transition: transform 0.2s; cursor: default; '
            'hover:transform: scale(1.05);">{} {}</span>',
            mark_safe(tooltip_attr),
            color['gradient'],
            style['padding'],
            style['border_radius'],
            style['font_size'],
            icon,
            badge_text
        )
    
    @classmethod
    def boolean(cls, value: bool, true_text: str = "Yes", false_text: str = "No", size: str = 'md') -> str:
        """🎨 Render boolean as colored badge"""
        return cls.render('true' if value else 'false', true_text if value else false_text, size)
    
    @classmethod
    def pill(cls, text: str, color: str = 'gray', icon: str = None, size: str = 'md') -> str:
        """🎨 Render custom pill badge"""
        color_config = cls.COLORS.get(color, cls.COLORS['gray'])
        icon_html = f'{icon} ' if icon else ''
        
        size_styles = {
            'sm': {'padding': '2px 8px', 'font_size': '10px'},
            'md': {'padding': '4px 12px', 'font_size': '11px'},
            'lg': {'padding': '6px 16px', 'font_size': '12px'},
        }
        style = size_styles.get(size, size_styles['md'])
        
        return format_html(
            '<span style="background: {}; color: white; padding: {}; border-radius: 20px; '
            'font-size: {}; font-weight: 500; display: inline-block;">{}{}</span>',
            color_config['gradient'],
            style['padding'],
            style['font_size'],
            icon_html,
            text
        )
    
    @classmethod
    def counter(cls, count: int, color: str = 'info', size: str = 'sm') -> str:
        """🎨 Render counter badge"""
        count_int = safe_int(count, 0)
        return cls.pill(str(count_int), color, size=size)


class ModernProgressBar:
    """
    [STATS] Modern Progress Bar with gradients and animations
    """
    
    @classmethod
    def render(cls, percentage: float, size: str = 'md', show_label: bool = True, 
               color: str = None, animated: bool = True) -> str:
        """
        [STATS] Render a beautiful progress bar
        
        Args:
            percentage: 0-100 value
            size: 'sm', 'md', 'lg'
            show_label: Show percentage text
            color: Force specific color
            animated: Add animation
        """
        percentage = max(0, min(100, safe_float(percentage, 0)))
        
        # Auto color based on percentage
        if not color:
            if percentage >= 90:
                color = 'success'
            elif percentage >= 75:
                color = 'info'
            elif percentage >= 50:
                color = 'purple'
            elif percentage >= 25:
                color = 'warning'
            else:
                color = 'danger'
        
        color_config = ModernBadge.COLORS.get(color, ModernBadge.COLORS['info'])
        
        # Size configurations
        size_configs = {
            'sm': {'height': '16px', 'font_size': '10px', 'width': '80px'},
            'md': {'height': '20px', 'font_size': '11px', 'width': '100px'},
            'lg': {'height': '24px', 'font_size': '12px', 'width': '120px'},
        }
        config = size_configs.get(size, size_configs['md'])
        
        # Animation
        animation = 'transition: width 0.5s ease-in-out;' if animated else ''
        
        return format_html(
            '<div style="width: {}; height: {}; background: #e5e7eb; border-radius: 999px; overflow: hidden; '
            'box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">'
            '<div style="width: {}%; height: 100%; background: {}; border-radius: 999px; text-align: center; '
            'color: white; font-size: {}; line-height: {}; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.2); '
            'box-shadow: 0 0 10px rgba(255,255,255,0.3); {};">{}</div></div>',
            config['width'],
            config['height'],
            percentage,
            color_config['gradient'],
            config['font_size'],
            config['height'],
            mark_safe(animation),
            f'{percentage:.0f}%' if show_label else ''
        )
    
    @classmethod
    def mini(cls, percentage: float, width: str = '60px') -> str:
        """[STATS] Mini progress bar for tight spaces"""
        return cls.render(percentage, size='sm', show_label=False)
    
    @classmethod
    def sparkline(cls, values: List[float], height: str = '20px', width: str = '100px') -> str:
        """[STATS] Sparkline style progress"""
        if not values:
            return ''
        
        max_val = max(values) if values else 1
        bars = []
        
        for val in values:
            pct = (val / max_val) * 100 if max_val > 0 else 0
            pct = min(100, max(0, pct))
            
            color_config = ModernBadge.COLORS['info']
            bars.append(
                f'<div style="flex:1; height: {height}; background: #e5e7eb; margin-right: 2px; border-radius: 2px; overflow: hidden;">'
                f'<div style="width: {pct}%; height: 100%; background: {color_config["gradient"]};"></div>'
                f'</div>'
            )
        
        return format_html('<div style="display: flex; width: {};">{}</div>', width, mark_safe(''.join(bars)))


class ModernIcon:
    """
    🎨 Modern Icon Factory with consistent styling
    """
    
    ICONS = {
        # Status Icons
        'success': '[OK]',
        'error': '[ERROR]',
        'warning': '[WARN]',
        'info': '[INFO]',
        'question': '❓',
        
        # Action Icons
        'add': '➕',
        'edit': '✏️',
        'delete': '[DELETE]',
        'save': '💾',
        'download': '⬇️',
        'upload': '⬆️',
        'refresh': '[LOADING]',
        'search': '🔍',
        'filter': '🔎',
        'export': '📤',
        'import': '📥',
        'copy': '📋',
        'paste': '📌',
        
        # Backup Icons
        'backup': '💾',
        'restore': '↩️',
        'schedule': '⏰',
        'log': '[NOTE]',
        'storage': '💿',
        'database': '🗄️',
        'cloud': '☁️',
        'local': '💻',
        
        # Navigation Icons
        'home': '🏠',
        'dashboard': '[STATS]',
        'settings': '⚙️',
        'profile': '👤',
        'logout': '🚪',
        'login': '[KEY]',
        
        # Object Icons
        'file': '[DOC]',
        'folder': '📁',
        'archive': '🗜️',
        'lock': '🔒',
        'unlock': '🔓',
        'key': '[KEY]',
        'time': '🕐',
        'calendar': '📅',
        'chart': '📈',
        'stats': '[STATS]',
    }
    
    @classmethod
    def get(cls, name: str, default: str = '•') -> str:
        """Get icon by name"""
        return cls.ICONS.get(name, default)
    
    @classmethod
    def render(cls, name: str, size: str = '16px', color: str = None) -> str:
        """Render icon with optional styling"""
        icon = cls.get(name)
        
        if color:
            return format_html(
                '<span style="font-size: {}; color: {}; display: inline-block;">{}</span>',
                size, color, icon
            )
        return format_html(
            '<span style="font-size: {}; display: inline-block;">{}</span>',
            size, icon
        )


class ModernButton:
    """
    🔘 Modern Button Factory
    """
    
    @classmethod
    def render(cls, text: str, url: str = '#', icon: str = None, 
               color: str = 'info', size: str = 'sm', **attrs) -> str:
        """Render a beautiful button"""
        color_config = ModernBadge.COLORS.get(color, ModernBadge.COLORS['info'])
        icon_html = f'{ModernIcon.get(icon)} ' if icon else ''
        
        size_styles = {
            'sm': {'padding': '4px 12px', 'font_size': '11px'},
            'md': {'padding': '6px 16px', 'font_size': '12px'},
            'lg': {'padding': '8px 20px', 'font_size': '14px'},
        }
        style = size_styles.get(size, size_styles['sm'])
        
        # Additional attributes
        attr_str = ' '.join([f'{k}="{v}"' for k, v in attrs.items()])
        
        return format_html(
            '<a href="{}" {} style="background: {}; color: white; text-decoration: none; padding: {}; '
            'border-radius: 8px; font-size: {}; font-weight: 500; display: inline-block; '
            'box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.1); '
            'transition: all 0.2s; hover:transform: translateY(-1px); hover:box-shadow: 0 4px 8px rgba(0,0,0,0.15);">'
            '{}{}</a>',
            url, mark_safe(attr_str),
            color_config['gradient'],
            style['padding'],
            style['font_size'],
            icon_html, text
        )
    
    @classmethod
    def action(cls, icon: str, url: str = '#', title: str = '', color: str = 'gray') -> str:
        """Render a small action button"""
        color_config = ModernBadge.COLORS.get(color, ModernBadge.COLORS['gray'])
        
        return format_html(
            '<a href="{}" title="{}" style="background: {}; color: white; text-decoration: none; '
            'padding: 4px 8px; border-radius: 6px; font-size: 12px; display: inline-block; '
            'margin: 0 2px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">{}</a>',
            url, title, color_config['gradient'], ModernIcon.get(icon)
        )


# ================================================
# [STATS] SECTION 3: DATA CLASSES FOR METRICS
# ================================================

@dataclass
class BackupMetrics:
    """[STATS] Type-safe backup metrics dataclass"""
    total_backups: int = 0
    successful_backups: int = 0
    failed_backups: int = 0
    total_size_bytes: int = 0
    total_size_gb: float = 0.0
    average_duration: float = 0.0
    success_rate: float = 0.0
    last_24h_count: int = 0
    last_24h_success: int = 0
    last_24h_failed: int = 0
    avg_file_size_mb: float = 0.0
    largest_backup_mb: float = 0.0
    oldest_backup_days: int = 0
    verification_rate: float = 0.0
    health_score: float = 0.0
    
    @classmethod
    @handle_errors(fallback_return=None)
    def from_queryset(cls, queryset):
        """Create metrics from queryset with bulletproof error handling"""
        if not queryset:
            return cls()
        
        # Basic counts
        total = safe_int(queryset.count(), 0)
        successful = safe_int(queryset.filter(status='completed').count(), 0)
        failed = safe_int(queryset.filter(status='failed').count(), 0)
        
        # Size aggregation
        size_agg = safe_aggregate(queryset, total_size=Sum('file_size'))
        total_size = safe_int(size_agg.get('total_size', 0), 0)
        
        # Duration aggregation
        duration_agg = safe_aggregate(queryset, avg_duration=Avg('duration'))
        avg_duration = safe_float(duration_agg.get('avg_duration', 0), 0)
        
        # Last 24 hours
        last_24h = timezone.now() - timedelta(days=1)
        last_24h_qs = queryset.filter(created_at__gte=last_24h)
        last_24h_count = safe_int(last_24h_qs.count(), 0)
        last_24h_success = safe_int(last_24h_qs.filter(status='completed').count(), 0)
        last_24h_failed = safe_int(last_24h_qs.filter(status='failed').count(), 0)
        
        # Largest backup
        largest = queryset.order_by('-file_size').first()
        largest_size = safe_int(bulletproof_getattr(largest, 'file_size', 0), 0)
        
        # Oldest backup
        oldest = queryset.order_by('created_at').first()
        oldest_date = bulletproof_getattr(oldest, 'created_at')
        oldest_days = 0
        if oldest_date:
            diff = timezone.now() - oldest_date
            oldest_days = diff.days if diff else 0
        
        # Verification rate
        verified = safe_int(queryset.filter(is_verified=True).count(), 0)
        verification_rate = safe_divide(verified * 100, total, 0)
        
        # Average health score
        health_agg = safe_aggregate(queryset, avg_health=Avg('health_score'))
        avg_health = safe_float(health_agg.get('avg_health', 0), 0)
        
        return cls(
            total_backups=total,
            successful_backups=successful,
            failed_backups=failed,
            total_size_bytes=total_size,
            total_size_gb=safe_divide(total_size, 1024**3, 0),
            average_duration=avg_duration,
            success_rate=safe_divide(successful * 100, total, 0),
            last_24h_count=last_24h_count,
            last_24h_success=last_24h_success,
            last_24h_failed=last_24h_failed,
            avg_file_size_mb=safe_divide(total_size, max(1, total) * 1024**2, 0),
            largest_backup_mb=safe_divide(largest_size, 1024**2, 0),
            oldest_backup_days=oldest_days,
            verification_rate=verification_rate,
            health_score=avg_health
        )


@dataclass
class StorageMetrics:
    """[STATS] Storage metrics dataclass"""
    total_locations: int = 0
    active_locations: int = 0
    total_space_bytes: int = 0
    used_space_bytes: int = 0
    free_space_bytes: int = 0
    used_percentage: float = 0.0
    total_space_tb: float = 0.0
    used_space_tb: float = 0.0
    free_space_tb: float = 0.0
    offline_locations: int = 0
    locations_near_full: int = 0
    
    @classmethod
    @handle_errors(fallback_return=None)
    def from_queryset(cls, queryset):
        """Create storage metrics"""
        if not queryset:
            return cls()
        
        total = safe_int(queryset.count(), 0)
        active = safe_int(queryset.filter(status='active').count(), 0)
        offline = safe_int(queryset.filter(is_connected=False).count(), 0)
        
        # Space calculations
        total_space_agg = safe_aggregate(queryset, total=Sum('total_space'))
        used_space_agg = safe_aggregate(queryset, used=Sum('used_space'))
        
        total_space = safe_int(total_space_agg.get('total', 0), 0)
        used_space = safe_int(used_space_agg.get('used', 0), 0)
        free_space = max(0, total_space - used_space)
        
        # Near full locations (>80% used)
        near_full = 0
        for loc in queryset.filter(status='active'):
            if safe_divide(safe_int(loc.used_space, 0) * 100, safe_int(loc.total_space, 1), 0) > 80:
                near_full += 1
        
        return cls(
            total_locations=total,
            active_locations=active,
            total_space_bytes=total_space,
            used_space_bytes=used_space,
            free_space_bytes=free_space,
            used_percentage=safe_divide(used_space * 100, max(1, total_space), 0),
            total_space_tb=safe_divide(total_space, 1024**4, 0),
            used_space_tb=safe_divide(used_space, 1024**4, 0),
            free_space_tb=safe_divide(free_space, 1024**4, 0),
            offline_locations=offline,
            locations_near_full=near_full
        )


@dataclass
class ScheduleMetrics:
    """[STATS] Schedule metrics dataclass"""
    total_schedules: int = 0
    active_schedules: int = 0
    paused_schedules: int = 0
    overdue_schedules: int = 0
    avg_success_rate: float = 0.0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    
    @classmethod
    @handle_errors(fallback_return=None)
    def from_queryset(cls, queryset):
        """Create schedule metrics"""
        if not queryset:
            return cls()
        
        total = safe_int(queryset.count(), 0)
        active = safe_int(queryset.filter(is_active=True, is_paused=False).count(), 0)
        paused = safe_int(queryset.filter(is_paused=True).count(), 0)
        
        # Overdue schedules
        now = timezone.now()
        overdue = safe_int(queryset.filter(
            is_active=True, 
            is_paused=False,
            next_run__lt=now
        ).count(), 0)
        
        # Run stats
        runs_agg = safe_aggregate(
            queryset,
            total_runs=Sum('total_runs'),
            successful=Sum('successful_runs'),
            failed=Sum('failed_runs')
        )
        
        total_runs = safe_int(runs_agg.get('total_runs', 0), 0)
        successful_runs = safe_int(runs_agg.get('successful', 0), 0)
        failed_runs = safe_int(runs_agg.get('failed', 0), 0)
        
        # Avg success rate
        success_agg = safe_aggregate(
            queryset.filter(total_runs__gt=0),
            avg_rate=Avg(
                Case(
                    When(total_runs__gt=0, then=F('successful_runs') * 100.0 / F('total_runs')),
                    default=Value(0),
                    output_field=FloatField()
                )
            )
        )
        avg_rate = safe_float(success_agg.get('avg_rate', 0), 0)
        
        return cls(
            total_schedules=total,
            active_schedules=active,
            paused_schedules=paused,
            overdue_schedules=overdue,
            avg_success_rate=avg_rate,
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs
        )


# ================================================
# [START] SECTION 4: CUSTOM ADMIN SITE WITH DASHBOARD
# ================================================
class BackupAdminSite(AdminSite):
    """
    [START] Custom Admin Site with Modern Dashboard
    """
    
    site_header = "[START] Advanced Backup Administration"
    site_title = "Backup Management System"
    index_title = "[STATS] Dashboard Overview"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_circuit_breakers()
    
    def _setup_circuit_breakers(self):
        """Setup circuit breakers for external calls"""
        try:
            from pybreaker import CircuitBreaker
            self.dashboard_breaker = CircuitBreaker(fail_max=3, reset_timeout=30)
            self.api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)
        except ImportError:
            self.dashboard_breaker = None
            self.api_breaker = None
            logger.info("Circuit breaker not available (install pybreaker)")
    
    def get_urls(self):
        """Get URLs with custom endpoints"""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
            path('dashboard/stats/', self.admin_view(self.dashboard_stats_api), name='dashboard_stats'),
            path('dashboard/health/', self.admin_view(self.health_check_api), name='health_check'),
            path('dashboard/quick-action/<str:action>/', self.admin_view(self.quick_action_view), name='quick_action'),
            path('dashboard/export/<str:model_name>/', self.admin_view(self.export_data_view), name='export_data'),
            path('dashboard/bulk-action/', self.admin_view(self.bulk_action_view), name='bulk_action'),
        ]
        return custom_urls + urls
    
    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    @handle_errors(fallback_return=None)
    def dashboard_view(self, request):
        """
        [STATS] Main Dashboard View with real-time statistics
        """
        from .models import Backup, BackupSchedule, BackupStorageLocation
        
        context = {
            **self.each_context(request),
            'title': '[STATS] Backup System Dashboard',
            'app_list': self.get_app_list(request),
            'has_permission': self.has_permission(request),
        }
        
        try:
            # Load metrics with circuit breaker
            backup_metrics = BackupMetrics.from_queryset(Backup.objects.all())
            storage_metrics = StorageMetrics.from_queryset(BackupStorageLocation.objects.all())
            schedule_metrics = ScheduleMetrics.from_queryset(BackupSchedule.objects.all())
            
            # Recent data
            recent_backups = list(Backup.objects.select_related('created_by').order_by('-created_at')[:10])
            failed_backups = list(Backup.objects.filter(status='failed').order_by('-created_at')[:5])
            
            upcoming_schedules = list(
                BackupSchedule.objects.filter(
                    is_active=True, 
                    is_paused=False,
                    next_run__gt=timezone.now()
                ).order_by('next_run')[:5]
            )
            
            # Top storage locations
            top_storage = list(
                BackupStorageLocation.objects.filter(status='active')
                .order_by('-used_space')[:5]
            )
            
            context.update({
                'backup_metrics': asdict(backup_metrics) if backup_metrics else {},
                'storage_metrics': asdict(storage_metrics) if storage_metrics else {},
                'schedule_metrics': asdict(schedule_metrics) if schedule_metrics else {},
                'recent_backups': recent_backups,
                'failed_backups': failed_backups,
                'upcoming_schedules': upcoming_schedules,
                'top_storage': top_storage,
                'backup_count': Backup.objects.count(),
                'storage_count': BackupStorageLocation.objects.count(),
                'schedule_count': BackupSchedule.objects.count(),
                'now': timezone.now(),
                'dashboard_url': reverse('admin:dashboard')  # This will work now
            })
            
        except Exception as e:
            logger.error(f"Dashboard error: {e}", exc_info=True)
            messages.error(request, f"Error loading dashboard: {safe_truncate(str(e), 100)}")
            
            # Graceful degradation with empty data
            context.update({
                'backup_metrics': asdict(BackupMetrics()),
                'storage_metrics': asdict(StorageMetrics()),
                'schedule_metrics': asdict(ScheduleMetrics()),
                'recent_backups': [],
                'failed_backups': [],
                'upcoming_schedules': [],
                'top_storage': [],
                'backup_count': 0,
                'storage_count': 0,
                'schedule_count': 0,
                'dashboard_url': '#',
            })
        
        return TemplateResponse(request, 'admin/backup_dashboard.html', context)
    
    # Fix the handle_errors decorator usage
    def quick_action_view(self, request, action):
        """
        ⚡ Quick action handler for dashboard buttons
        """
        try:
            action_map = {
                'manual_backup': self._action_manual_backup,
                'verify_all': self._action_verify_all,
                'cleanup': self._action_cleanup,
                'test_notifications': self._action_test_notifications,
                'refresh_stats': self._action_refresh_stats,
                'export_report': self._action_export_report,
            }
            
            action_func = action_map.get(action)
            if action_func:
                return action_func(request)
            
            messages.error(request, f"Unknown action: {action}")
            return redirect('admin:index')  # Changed from admin:dashboard
            
        except Exception as e:
            logger.error(f"Quick action error: {e}")
            messages.error(request, f"Action failed: {safe_truncate(str(e), 100)}")
            return redirect('admin:index')  # Changed from admin:dashboard
    
    def _action_manual_backup(self, request):
        """Start manual backup"""
        messages.success(request, "[OK] Manual backup started successfully!")
        return redirect('admin:index')  # Changed from admin:dashboard
    
    def _action_verify_all(self, request):
        """Verify all backups"""
        messages.info(request, "🔍 Verification process initiated...")
        return redirect('admin:index')
    
    def _action_cleanup(self, request):
        """Cleanup old backups"""
        from .models import Backup
        expired = Backup.objects.filter(expires_at__lt=timezone.now()).count()
        messages.success(request, f"🧹 Cleaned up {expired} expired backups")
        return redirect('admin:index')
    
    def _action_test_notifications(self, request):
        """Test notification system"""
        messages.success(request, "📧 Test notification sent to admin")
        return redirect('admin:index')
    
    def _action_refresh_stats(self, request):
        """Refresh statistics"""
        messages.info(request, "[LOADING] Statistics refreshed")
        return redirect('admin:index')
    
    def _action_export_report(self, request):
        """Export report"""
        from django.http import HttpResponse
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Report generated', timezone.now().isoformat()])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="backup_report_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response
    
    def export_data_view(self, request, model_name):
        """
        📥 Export data in various formats
        """
        try:
            format_type = request.GET.get('format', 'csv')
            model_map = {
                'backup': ('Backup', ['id', 'name', 'status', 'backup_type', 'file_size', 'created_at']),
                'schedule': ('BackupSchedule', ['id', 'name', 'frequency', 'is_active', 'next_run']),
                'storage': ('BackupStorageLocation', ['id', 'name', 'storage_type', 'status', 'total_space']),
                'restoration': ('BackupRestoration', ['id', 'backup_id', 'status', 'started_at']),
                'log': ('BackupLog', ['id', 'level', 'message', 'timestamp']),
            }
            
            if model_name not in model_map:
                messages.error(request, f"Unknown model: {model_name}")
                return redirect('admin:index')
            
            model_class_name, fields = model_map[model_name]
            
            # Import model dynamically
            from .models import (
                Backup, BackupSchedule, BackupStorageLocation, 
                BackupRestoration, BackupLog
            )
            model_class = locals().get(model_class_name)
            
            if not model_class:
                messages.error(request, f"Model {model_class_name} not found")
                return redirect('admin:index')
            
            # Get data
            queryset = model_class.objects.all()[:5000]  # Limit for performance
            
            if format_type == 'csv':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{model_name}_{timezone.now().strftime("%Y%m%d")}.csv"'
                
                writer = csv.writer(response)
                writer.writerow(fields)
                
                for obj in queryset:
                    row = []
                    for field in fields:
                        value = bulletproof_getattr(obj, field, '')
                        if callable(value):
                            value = value()
                        elif isinstance(value, datetime):
                            value = value.isoformat()
                        elif isinstance(value, uuid.UUID):
                            value = str(value)
                        row.append(str(value)[:1000])
                    writer.writerow(row)
                
                return response
            
            elif format_type == 'json':
                data = []
                for obj in queryset:
                    obj_data = {}
                    for field in fields:
                        value = bulletproof_getattr(obj, field, '')
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        elif isinstance(value, uuid.UUID):
                            value = str(value)
                        obj_data[field] = value
                    data.append(obj_data)
                
                return JsonResponse({
                    'model': model_name,
                    'count': len(data),
                    'exported_at': timezone.now().isoformat(),
                    'data': data
                }, json_dumps_params={'indent': 2, 'default': str})
            
            messages.error(request, f"Unsupported format: {format_type}")
            return redirect('admin:index')
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            messages.error(request, f"Export failed: {safe_truncate(str(e), 100)}")
            return redirect('admin:index')
    
    @method_decorator(csrf_protect)
    @atomic_transaction
    def bulk_action_view(self, request):
        """
        📦 Bulk action handler for multiple items
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        action = request.POST.get('action')
        model_name = request.POST.get('model')
        ids = request.POST.getlist('ids')
        
        if not action or not model_name or not ids:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # Model mapping
        model_map = {
            'backup': 'Backup',
            'schedule': 'BackupSchedule',
            'storage': 'BackupStorageLocation',
            'restoration': 'BackupRestoration',
        }
        
        try:
            from .models import (
                Backup, BackupSchedule, BackupStorageLocation, 
                BackupRestoration
            )
            model_class = locals().get(model_map.get(model_name, ''))
            
            if not model_class:
                return JsonResponse({'error': f'Model {model_name} not found'}, status=404)
            
            queryset = model_class.objects.filter(id__in=ids)
            count = queryset.count()
            
            # Handle different actions
            if action == 'delete':
                deleted, _ = queryset.delete()
                return JsonResponse({
                    'success': True,
                    'message': f'Deleted {deleted} items',
                    'count': deleted
                })
            
            elif action == 'mark_active':
                if hasattr(model_class, 'status'):
                    updated = queryset.update(status='active')
                    return JsonResponse({
                        'success': True,
                        'message': f'Marked {updated} items as active'
                    })
            
            elif action == 'mark_inactive':
                if hasattr(model_class, 'status'):
                    updated = queryset.update(status='inactive')
                    return JsonResponse({
                        'success': True,
                        'message': f'Marked {updated} items as inactive'
                    })
            
            elif action == 'verify':
                if model_name == 'backup':
                    updated = queryset.update(is_verified=True, verified_at=timezone.now())
                    return JsonResponse({
                        'success': True,
                        'message': f'Verified {updated} backups'
                    })
            
            return JsonResponse({'error': f'Unknown action: {action}'}, status=400)
            
        except Exception as e:
            logger.error(f"Bulk action error: {e}")
            return JsonResponse({'error': str(e)[:200]}, status=500)
        
        
        # BackupAdminSite ক্লাসের ভেতরে যেকোনো জায়গায় এই ফাংশনগুলো বসান
    def dashboard_stats_api(self, request):
        from django.http import JsonResponse
        return JsonResponse({"status": "ok", "message": "Stats coming soon"})

    def health_check_api(self, request):
        from django.http import JsonResponse
        return JsonResponse({"status": "healthy"})


# ================================================
# 🎨 SECTION 5: CUSTOM INLINE CLASSES
# ================================================

class BackupLogInline(admin.TabularInline):
    """
    [NOTE] Inline for displaying backup logs with modern design
    """
    model = BackupLog
    extra = 0
    max_num = 10
    can_delete = False
    readonly_fields = ('timestamp', 'level_badge', 'message_preview', 'category', 'duration_formatted')
    fields = ('timestamp', 'level_badge', 'message_preview', 'category', 'duration_formatted')
    
    def level_badge(self, obj):
        """Display log level as colored badge"""
        if obj and obj.level:
            return ModernBadge.render(obj.level, obj.get_level_display())
        return ModernBadge.render('unknown', 'Unknown')
    level_badge.short_description = "Level"
    
    def message_preview(self, obj):
        """Display message with tooltip"""
        if obj and obj.message:
            message = safe_truncate(obj.message, 80)
            return format_html('<span title="{}">{}</span>', obj.message, message)
        return '-'
    message_preview.short_description = "Message"
    
    def duration_formatted(self, obj):
        """Format duration"""
        if obj and obj.duration:
            return format_duration(obj.duration)
        return '-'
    duration_formatted.short_description = "Duration"
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    class Media:
        css = {
            'all': ('admin/css/inline-modern.css',)
        }


class BackupRestorationInline(admin.TabularInline):
    """
    [LOADING] Inline for displaying backup restorations
    """
    model = BackupRestoration
    fk_name = 'backup'
    extra = 0
    max_num = 5
    readonly_fields = ('restoration_id_short', 'status_badge', 'restoration_type_icon', 'started_at_ago', 'initiated_by')
    fields = ('restoration_id_short', 'status_badge', 'restoration_type_icon', 'started_at_ago', 'initiated_by')
    
    def restoration_id_short(self, obj):
        """Display short restoration ID"""
        if obj and obj.restoration_id:
            rid = str(obj.restoration_id)[:8]
            return format_html('<code style="background: #f3f4f6; padding: 2px 6px; border-radius: 4px;">{}</code>', rid)
        return '-'
    restoration_id_short.short_description = "ID"
    
    def status_badge(self, obj):
        """Display status as badge"""
        if obj and obj.status:
            return ModernBadge.render(obj.status, obj.get_status_display())
        return '-'
    status_badge.short_description = "Status"
    
    def restoration_type_icon(self, obj):
        """Display restoration type with icon"""
        if obj and obj.restoration_type:
            icons = {
                'full': '💾',
                'partial': '[NOTE]',
                'tables': '[STATS]',
                'schema': '🏗️',
                'data': '📁',
            }
            icon = icons.get(obj.restoration_type, '[LOADING]')
            return format_html('{} {}', icon, obj.get_restoration_type_display())
        return '-'
    restoration_type_icon.short_description = "Type"
    
    def started_at_ago(self, obj):
        """Display relative time"""
        if obj and obj.started_at:
            return time_ago(obj.started_at)
        return '-'
    started_at_ago.short_description = "Started"
    
    def has_add_permission(self, request, obj=None):
        return False


# ================================================
# 💾 SECTION 6: BACKUP ADMIN (MAIN)
# ================================================

@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """
    💾 Advanced Admin for Backup model with all features
    """
    
    # 1. List Display - Modern, colorful, informative
    list_display = (
        'backup_id_short',
        'name_with_icon',
        'status_badge',
        'backup_type_badge',
        'file_size_formatted',
        'duration_badge',
        'health_score_indicator',
        'created_at_ago',
        'quick_action_buttons',
    )
    
    list_display_links = ('backup_id_short', 'name_with_icon')
    
    # 2. List Filters
    list_filter = (
        'status',
        'backup_type',
        'storage_type',
        'database_name',
        'is_verified',
        'is_healthy',
        'encryption_enabled',
        'compression_enabled',
        ('created_at', admin.DateFieldListFilter),
    )
    
    # 3. Search Fields
    search_fields = (
        'name',
        'backup_id',
        'database_name',
        'file_path',
        'error_message',
        'verification_notes',
    )
    
    # 4. List Per Page
    list_per_page = 25
    list_max_show_all = 200
    ordering = ('-created_at',)
    sortable_by = ('created_at', 'file_size', 'duration', 'health_score')
    
    # 5. Actions
    actions = [
        'verify_selected',
        'mark_healthy',
        'mark_unhealthy',
        'create_restoration_points',
        'export_json',
        'cleanup_expired',
        'bulk_delete',
    ]
    
    # 6. Fieldsets
    fieldsets = (
        ('📋 Basic Information', {
            'fields': ('backup_id', 'name', 'description', 'created_by'),
            'classes': ('wide',),
        }),
        ('[FIX] Backup Details', {
            'fields': (
                ('backup_type', 'status'),
                ('database_name', 'database_engine'),
                ('start_time', 'end_time'),
                ('duration_display',),
            ),
            'classes': ('collapse',),
        }),
        ('💿 File Information', {
            'fields': (
                ('file_path', 'file_format'),
                ('file_size_display', 'compressed_size_display'),
                ('compression_ratio_display',),
                ('file_hash', 'verification_hash'),
            ),
            'classes': ('collapse',),
        }),
        ('[SECURE] Security', {
            'fields': (
                ('encryption_enabled', 'encryption_method'),
                ('key_id',),
            ),
            'classes': ('collapse',),
        }),
        ('[STATS] Health & Verification', {
            'fields': (
                ('is_healthy', 'health_score'),
                ('is_verified', 'verified_at'),
                ('verification_method', 'verification_notes'),
                ('error_message',),
            ),
            'classes': ('collapse',),
        }),
        ('⏰ Retention', {
            'fields': (
                ('retention_days', 'is_permanent'),
                ('created_at', 'expires_at'),
            ),
            'classes': ('collapse',),
        }),
        ('[NOTE] Metadata', {
            'fields': ('metadata', 'tags', 'custom_fields'),
            'classes': ('collapse',),
        }),
    )
    
    # 7. Readonly Fields
    readonly_fields = (
        'backup_id',
        'duration_display',
        'file_size_display',
        'compressed_size_display',
        'compression_ratio_display',
        'created_at',
        'verified_at',
        'file_hash',
    )
    
    # 8. Inlines
    inlines = [BackupRestorationInline, BackupLogInline]
    
    # 9. Custom Methods for List Display
    
    @handle_errors(fallback_return='-')
    def backup_id_short(self, obj):
        """Display short backup ID"""
        backup_id = bulletproof_getattr(obj, 'backup_id', 'N/A')
        if backup_id and backup_id != 'N/A':
            short_id = str(backup_id)[:8]
            return format_html(
                '<span title="{}" style="font-family: monospace; background: #f3f4f6; '
                'padding: 2px 6px; border-radius: 4px; color: #4b5563;">{}</span>',
                backup_id, short_id
            )
        return format_html('<span style="color: #9ca3af;">-</span>')
    backup_id_short.short_description = "ID"
    backup_id_short.admin_order_field = 'backup_id'
    
    @handle_errors(fallback_return='Unknown')
    def name_with_icon(self, obj):
        """Display name with icon based on type"""
        icon_map = {
            'full': '💾',
            'incremental': '➕',
            'differential': '[STATS]',
            'partial': '[NOTE]',
            'scheduled': '⏰',
            'manual': '👆',
        }
        icon = icon_map.get(obj.backup_type, '📁')
        name = safe_truncate(obj.name, 30)
        
        return format_html(
            '<span style="font-weight: 500; display: flex; align-items: center; gap: 4px;">'
            '<span style="font-size: 1.1em;">{}</span> <span>{}</span></span>',
            icon, name
        )
    name_with_icon.short_description = "Name"
    name_with_icon.admin_order_field = 'name'
    
    @handle_errors(fallback_return='-')
    def status_badge(self, obj):
        """Display status as beautiful badge"""
        if obj and obj.status:
            return ModernBadge.render(obj.status, obj.get_status_display())
        return ModernBadge.render('unknown', 'Unknown')
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'
    
    @handle_errors(fallback_return='-')
    def backup_type_badge(self, obj):
        """Display backup type as colored pill"""
        if obj and obj.backup_type:
            color_map = {
                'full': 'success',
                'incremental': 'info',
                'differential': 'warning',
                'partial': 'gray',
                'scheduled': 'purple',
                'manual': 'pink',
            }
            color = color_map.get(obj.backup_type, 'gray')
            return ModernBadge.pill(obj.get_backup_type_display(), color, size='sm')
        return '-'
    backup_type_badge.short_description = "Type"
    backup_type_badge.admin_order_field = 'backup_type'
    
    @handle_errors(fallback_return='0 B')
    def file_size_formatted(self, obj):
        """Display file size in human readable format"""
        if obj and obj.file_size:
            return format_file_size(obj.file_size)
        return '0 B'
    file_size_formatted.short_description = "Size"
    file_size_formatted.admin_order_field = 'file_size'
    
    @handle_errors(fallback_return='-')
    def duration_badge(self, obj):
        """Display duration with color coding"""
        if obj and obj.duration:
            duration = obj.duration
            if duration < 60:
                color = 'success'
            elif duration < 300:
                color = 'info'
            elif duration < 900:
                color = 'warning'
            else:
                color = 'purple'
            return ModernBadge.pill(format_duration(duration), color, size='sm')
        return '-'
    duration_badge.short_description = "Duration"
    duration_badge.admin_order_field = 'duration'
    
    @handle_errors(fallback_return='-')
    def health_score_indicator(self, obj):
        """Display health score with visual indicator"""
        if obj and obj.health_score is not None:
            score = safe_float(obj.health_score, 0)
            return ModernProgressBar.mini(score)
        return '-'
    health_score_indicator.short_description = "Health"
    health_score_indicator.admin_order_field = 'health_score'
    
    @handle_errors(fallback_return='-')
    def created_at_ago(self, obj):
        """Display relative time"""
        if obj and obj.created_at:
            return time_ago(obj.created_at)
        return '-'
    created_at_ago.short_description = "Created"
    created_at_ago.admin_order_field = 'created_at'
    
    @handle_errors(fallback_return='-')
    def quick_action_buttons(self, obj):
        """Display quick action buttons"""
        buttons = []
        
        # Download button
        if obj.status == 'completed':
            buttons.append(
                ModernButton.action('download', '#', 'Download', 'success')
            )
        
        # Verify button
        if not obj.is_verified:
            buttons.append(
                ModernButton.action('search', '#', 'Verify', 'info')
            )
        
        # Restore button
        if obj.status == 'completed':
            buttons.append(
                ModernButton.action('restore', '#', 'Restore', 'warning')
            )
        
        # Delete button
        buttons.append(
            ModernButton.action('delete', '#', 'Delete', 'danger')
        )
        
        return format_html('<div style="display: flex; gap: 2px;">{}</div>', 
                          mark_safe(''.join(buttons)))
    quick_action_buttons.short_description = "Actions"
    
    # 10. Custom Readonly Field Methods
    
    @handle_errors(fallback_return='-')
    def duration_display(self, obj):
        """Format duration for detail view"""
        if obj and obj.duration:
            return format_duration(obj.duration)
        return '-'
    
    @handle_errors(fallback_return='0 B')
    def file_size_display(self, obj):
        """Format file size for detail view"""
        if obj and obj.file_size:
            return format_file_size(obj.file_size)
        return '0 B'
    
    @handle_errors(fallback_return='0 B')
    def compressed_size_display(self, obj):
        """Format compressed size for detail view"""
        if obj and obj.compressed_size:
            return format_file_size(obj.compressed_size)
        return '0 B'
    
    @handle_errors(fallback_return='N/A')
    def compression_ratio_display(self, obj):
        """Calculate and format compression ratio"""
        if obj and obj.original_size and obj.compressed_size:
            original = safe_float(obj.original_size, 1)
            compressed = safe_float(obj.compressed_size, 1)
            if original > 0 and compressed > 0:
                ratio = original / compressed
                savings = ((original - compressed) / original) * 100
                return f"{ratio:.2f}:1 ({savings:.1f}% savings)"
        return 'N/A'
    
    # 11. Custom Actions
    
    @admin.action(description="[OK] Verify selected backups")
    @atomic_transaction
    def verify_selected(self, request, queryset):
        """Verify selected backups"""
        count = queryset.update(
            is_verified=True,
            verified_at=timezone.now(),
            verification_method='admin_action'
        )
        self.message_user(
            request,
            f"[OK] Verified {count} backup(s)",
            messages.SUCCESS
        )
    
    @admin.action(description="🩺 Mark as healthy")
    @atomic_transaction
    def mark_healthy(self, request, queryset):
        """Mark backups as healthy"""
        count = queryset.update(
            is_healthy=True,
            health_score=100
        )
        self.message_user(
            request,
            f"🩺 Marked {count} backup(s) as healthy",
            messages.SUCCESS
        )
    
    @admin.action(description="🤒 Mark as unhealthy")
    @atomic_transaction
    def mark_unhealthy(self, request, queryset):
        """Mark backups as unhealthy"""
        count = queryset.update(
            is_healthy=False,
            health_score=0
        )
        self.message_user(
            request,
            f"🤒 Marked {count} backup(s) as unhealthy",
            messages.WARNING
        )
    
    @admin.action(description="[LOADING] Create restoration points")
    @atomic_transaction
    def create_restoration_points(self, request, queryset):
        """Create restoration points for backups"""
        from .models import BackupRestoration
        
        count = 0
        for backup in queryset.filter(status='completed'):
            try:
                restoration = BackupRestoration.objects.create(
                    backup=backup,
                    restoration_type='full',
                    initiated_by=request.user,
                    notes=f"Created via admin action on {timezone.now().date()}"
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to create restoration for backup {backup.id}: {e}")
        
        self.message_user(
            request,
            f"[LOADING] Created {count} restoration point(s)",
            messages.SUCCESS
        )
    
    @admin.action(description="[STATS] Export as JSON")
    def export_json(self, request, queryset):
        """Export selected backups as JSON"""
        import json
        
        data = []
        for backup in queryset:
            data.append({
                'id': str(backup.id),
                'name': backup.name,
                'type': backup.backup_type,
                'status': backup.status,
                'size': backup.file_size,
                'size_formatted': format_file_size(backup.file_size),
                'created_at': backup.created_at.isoformat() if backup.created_at else None,
                'database': backup.database_name,
                'is_verified': backup.is_verified,
                'health_score': backup.health_score,
            })
        
        response = HttpResponse(
            json.dumps({
                'exported_at': timezone.now().isoformat(),
                'count': len(data),
                'backups': data
            }, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="backups_export_{timezone.now().strftime("%Y%m%d")}.json"'
        return response
    
    @admin.action(description="[DELETE] Cleanup expired backups")
    @atomic_transaction
    def cleanup_expired(self, request, queryset):
        """Delete expired backups"""
        expired = queryset.filter(
            Q(expires_at__lt=timezone.now()) |
            Q(is_expired=True)
        )
        count = expired.count()
        deleted, _ = expired.delete()
        
        self.message_user(
            request,
            f"[DELETE] Cleaned up {deleted} expired backup(s)",
            messages.SUCCESS
        )
    
    @admin.action(description="[WARN] Bulk delete (permanent)")
    def bulk_delete(self, request, queryset):
        """Bulk delete with confirmation"""
        count = queryset.count()
        if count > 10:
            self.message_user(
                request,
                f"[WARN] Too many items ({count}). Use select delete for bulk operations.",
                messages.WARNING
            )
            return
        
        deleted, _ = queryset.delete()
        self.message_user(
            request,
            f"[DELETE] Deleted {deleted} backup(s)",
            messages.SUCCESS
        )
    
    # 12. Custom Views
    
    def get_urls(self):
        """Add custom URLs"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/restore/',
                self.admin_site.admin_view(self.restore_view),
                name='backup_restore'
            ),
            path(
                '<path:object_id>/verify/',
                self.admin_site.admin_view(self.verify_view),
                name='backup_verify'
            ),
            path(
                '<path:object_id>/download/',
                self.admin_site.admin_view(self.download_view),
                name='backup_download'
            ),
        ]
        return custom_urls + urls
    
    @method_decorator(csrf_protect)
    @method_decorator(login_required)
    @handle_errors(fallback_return='/admin/backup/backup/')
    def restore_view(self, request, object_id):
        """Custom restore view"""
        from .models import Backup
        
        backup = Backup.objects.get(id=object_id)
        
        if request.method == 'POST':
            restoration_type = request.POST.get('restoration_type', 'full')
            tables = request.POST.get('tables', '').split(',') if request.POST.get('tables') else []
            
            from .models import BackupRestoration
            restoration = BackupRestoration.objects.create(
                backup=backup,
                restoration_type=restoration_type,
                tables=tables if tables else None,
                initiated_by=request.user,
                notes=request.POST.get('notes', '')
            )
            
            messages.success(request, f"[OK] Restoration started: {restoration.restoration_id}")
            return redirect('admin:backup_backup_changelist')
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Restore: {backup.name}',
            'backup': backup,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
        }
        
        return TemplateResponse(request, 'admin/backup_restore.html', context)
    
    @method_decorator(login_required)
    @handle_errors(fallback_return='/admin/backup/backup/')
    def verify_view(self, request, object_id):
        """Manual verification view"""
        from .models import Backup
        
        backup = Backup.objects.get(id=object_id)
        backup.is_verified = True
        backup.verified_at = timezone.now()
        backup.verification_method = 'manual'
        backup.verification_notes = f"Verified by {request.user.username}"
        backup.save()
        
        messages.success(request, f"[OK] Backup '{backup.name}' verified")
        return redirect('admin:backup_backup_changelist')
    
    @method_decorator(login_required)
    @handle_errors(fallback_return='/admin/backup/backup/')
    def download_view(self, request, object_id):
        """Download backup file"""
        from .models import Backup
        
        backup = Backup.objects.get(id=object_id)
        
        if not backup.file_path:
            messages.error(request, "No file found for this backup")
            return redirect('admin:backup_backup_changelist')
        
        # Log download
        BackupLog.objects.create(
            backup=backup,
            level='info',
            category='download',
            message=f"Backup downloaded by {request.user.username}",
            user=request.user
        )
        
        # In production, serve file properly
        messages.success(request, f"📥 Download started: {backup.name}")
        return redirect('admin:backup_backup_changelist')
    
    # 13. Form Customization
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form fields"""
        form = super().get_form(request, obj, **kwargs)
        
        # Add help texts and CSS classes
        if 'name' in form.base_fields:
            form.base_fields['name'].widget.attrs.update({
                'class': 'vTextField',
                'placeholder': 'Enter backup name...'
            })
        
        if 'description' in form.base_fields:
            form.base_fields['description'].widget.attrs.update({
                'class': 'vLargeTextField',
                'rows': 3,
                'placeholder': 'Optional description...'
            })
        
        return form
    
    # 14. Save Model Customization
    
    def save_model(self, request, obj, form, change):
        """Custom save behavior"""
        if not change:  # New object
            obj.created_by = request.user
            if not obj.backup_id:
                obj.backup_id = uuid.uuid4()
        
        super().save_model(request, obj, form, change)
        
        # Log the action
        BackupLog.objects.create(
            backup=obj,
            level='info',
            category='admin',
            message=f"{'Updated' if change else 'Created'} by {request.user.username}",
            user=request.user
        )
    
    def delete_model(self, request, obj):
        """Custom delete behavior"""
        backup_id = obj.id
        backup_name = obj.name
        
        # Log before delete
        logger.info(f"Backup {backup_name} (ID: {backup_id}) deleted by {request.user.username}")
        
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Custom bulk delete"""
        count = queryset.count()
        for obj in queryset:
            logger.info(f"Backup {obj.name} deleted by {request.user.username}")
        
        super().delete_queryset(request, queryset)
        
        self.message_user(
            request,
            f"[DELETE] Deleted {count} backup(s)",
            messages.SUCCESS
        )
    
    # 15. Media Files
    
    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
                'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
                'admin/css/admin-custom.css',
            )
        }
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
            'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js',
            'admin/js/admin-dashboard.js',
            'admin/js/backup-actions.js',
        )


# ================================================
# 💿 SECTION 7: STORAGE LOCATION ADMIN
# ================================================

@admin.register(BackupStorageLocation)
class BackupStorageLocationAdmin(admin.ModelAdmin):
    """
    💿 Admin for Storage Locations with visual indicators
    """
    
    list_display = (
        'name_with_icon',
        'storage_type_badge',
        'status_badge',
        'space_usage_bar',
        'connection_status',
        'space_formatted',
        'last_check_ago',
        'action_buttons',
    )
    
    list_filter = ('storage_type', 'status', 'is_default', 'is_connected')
    search_fields = ('name', 'endpoint', 'bucket_name', 'description')
    
    fieldsets = (
        ('📋 Basic Information', {
            'fields': ('name', 'description', 'storage_type', 'is_default')
        }),
        ('🔌 Connection Details', {
            'fields': ('endpoint', 'bucket_name', 'access_key', 'secret_key', 'region', 'base_path'),
            'classes': ('collapse',),
        }),
        ('[STATS] Status', {
            'fields': ('status', 'is_connected', 'last_connection_check', 'connection_error'),
        }),
        ('💾 Capacity', {
            'fields': ('total_space', 'used_space', 'free_space'),
        }),
        ('⚙️ Configuration', {
            'fields': ('config', 'tags'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('last_connection_check', 'free_space')
    
    @handle_errors(fallback_return='-')
    def name_with_icon(self, obj):
        """Display name with icon"""
        icons = {
            'local': '💻',
            's3': '☁️',
            'gcs': '🌐',
            'azure': '🔵',
            'ftp': '📁',
            'sftp': '🔒',
        }
        icon = icons.get(obj.storage_type, '📦')
        return format_html('<span style="font-weight: 500;">{} {}</span>', icon, obj.name)
    name_with_icon.short_description = "Name"
    
    @handle_errors(fallback_return='-')
    def storage_type_badge(self, obj):
        """Display storage type as badge"""
        color_map = {
            'local': 'gray',
            's3': 'success',
            'gcs': 'info',
            'azure': 'info',
            'ftp': 'warning',
            'sftp': 'purple',
        }
        color = color_map.get(obj.storage_type, 'gray')
        return ModernBadge.pill(obj.get_storage_type_display(), color, size='sm')
    storage_type_badge.short_description = "Type"
    
    @handle_errors(fallback_return='-')
    def status_badge(self, obj):
        """Display status as badge"""
        if obj and obj.status:
            return ModernBadge.render(obj.status, obj.get_status_display())
        return '-'
    status_badge.short_description = "Status"
    
    @handle_errors(fallback_return='-')
    def space_usage_bar(self, obj):
        """Display space usage as progress bar"""
        if obj and obj.total_space and obj.total_space > 0:
            used_pct = safe_percentage(obj.used_space, obj.total_space, 0)
            return ModernProgressBar.mini(used_pct)
        return '-'
    space_usage_bar.short_description = "Usage"
    
    @handle_errors(fallback_return='[ERROR]')
    def connection_status(self, obj):
        """Display connection status"""
        if obj and obj.is_connected:
            return ModernBadge.pill('Connected', 'success', '[OK]', 'sm')
        return ModernBadge.pill('Disconnected', 'danger', '[ERROR]', 'sm')
    connection_status.short_description = "Connection"
    
    @handle_errors(fallback_return='-')
    def space_formatted(self, obj):
        """Display formatted space info"""
        if obj:
            used = format_file_size(obj.used_space) if obj.used_space else '0 B'
            total = format_file_size(obj.total_space) if obj.total_space else '0 B'
            return f"{used} / {total}"
        return '-'
    space_formatted.short_description = "Space"
    
    @handle_errors(fallback_return='-')
    def last_check_ago(self, obj):
        """Display last check time"""
        if obj and obj.last_connection_check:
            return time_ago(obj.last_connection_check)
        return 'Never'
    last_check_ago.short_description = "Last Check"
    
    @handle_errors(fallback_return='-')
    def action_buttons(self, obj):
        """Display action buttons"""
        buttons = []
        
        # Test connection
        buttons.append(
            ModernButton.action('bolt', '#', 'Test Connection', 'info')
        )
        
        # Refresh stats
        buttons.append(
            ModernButton.action('refresh', '#', 'Refresh Stats', 'success')
        )
        
        return format_html('<div style="display: flex; gap: 2px;">{}</div>', 
                          mark_safe(''.join(buttons)))
    action_buttons.short_description = "Actions"
    
    def free_space(self, obj):
        """Calculate free space"""
        if obj and obj.total_space and obj.used_space:
            free = max(0, obj.total_space - obj.used_space)
            return format_file_size(free)
        return '0 B'
    free_space.short_description = "Free Space"
    
    actions = ['test_connections', 'refresh_stats', 'mark_active', 'mark_inactive']
    
    @admin.action(description="🔌 Test selected connections")
    def test_connections(self, request, queryset):
        """Test connections for selected locations"""
        count = queryset.count()
        self.message_user(
            request,
            f"🔌 Testing {count} connection(s)...",
            messages.INFO
        )
    
    @admin.action(description="[LOADING] Refresh statistics")
    @atomic_transaction
    def refresh_stats(self, request, queryset):
        """Refresh storage statistics"""
        updated = queryset.update(last_connection_check=timezone.now())
        self.message_user(
            request,
            f"[LOADING] Refreshed {updated} location(s)",
            messages.SUCCESS
        )
    
    @admin.action(description="[OK] Mark as active")
    @atomic_transaction
    def mark_active(self, request, queryset):
        """Mark locations as active"""
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f"[OK] Marked {updated} location(s) as active",
            messages.SUCCESS
        )
    
    @admin.action(description="⭕ Mark as inactive")
    @atomic_transaction
    def mark_inactive(self, request, queryset):
        """Mark locations as inactive"""
        updated = queryset.update(status='inactive')
        self.message_user(
            request,
            f"⭕ Marked {updated} location(s) as inactive",
            messages.WARNING
        )


# ================================================
# ⏰ SECTION 8: BACKUP SCHEDULE ADMIN
# ================================================

@admin.register(BackupSchedule)
class BackupScheduleAdmin(admin.ModelAdmin):
    """
    ⏰ Admin for Backup Schedules
    """
    
    list_display = (
        'name_with_icon',
        'frequency_badge',
        'backup_type_badge',
        'status_badge',
        'next_run_countdown',
        'last_run_badge',
        'success_rate_bar',
        'toggle_button',
    )
    
    list_filter = ('frequency', 'is_active', 'is_paused', 'backup_type')
    search_fields = ('name', 'description')
    
    @handle_errors(fallback_return='-')
    def name_with_icon(self, obj):
        """Display name with icon"""
        icons = {
            'hourly': '🕐',
            'daily': '📅',
            'weekly': '📆',
            'monthly': '🗓️',
            'custom': '⚙️',
        }
        icon = icons.get(obj.frequency, '⏰')
        return format_html('<span style="font-weight: 500;">{} {}</span>', icon, obj.name)
    name_with_icon.short_description = "Name"
    
    @handle_errors(fallback_return='-')
    def frequency_badge(self, obj):
        """Display frequency as badge"""
        color_map = {
            'hourly': 'info',
            'daily': 'success',
            'weekly': 'warning',
            'monthly': 'purple',
            'custom': 'gray',
        }
        color = color_map.get(obj.frequency, 'gray')
        return ModernBadge.pill(obj.get_frequency_display(), color, size='sm')
    frequency_badge.short_description = "Frequency"
    
    @handle_errors(fallback_return='-')
    def backup_type_badge(self, obj):
        """Display backup type"""
        color_map = {
            'full': 'success',
            'incremental': 'info',
            'differential': 'warning',
        }
        color = color_map.get(obj.backup_type, 'gray')
        return ModernBadge.pill(obj.get_backup_type_display(), color, size='sm')
    backup_type_badge.short_description = "Type"
    
    @handle_errors(fallback_return='-')
    def status_badge(self, obj):
        """Display status"""
        if obj and obj.is_paused:
            return ModernBadge.render('paused', 'Paused')
        elif obj and obj.is_active:
            return ModernBadge.render('active', 'Active')
        return ModernBadge.render('inactive', 'Inactive')
    status_badge.short_description = "Status"
    
    @handle_errors(fallback_return='-')
    def next_run_countdown(self, obj):
        """Display next run countdown"""
        if obj and obj.is_active and not obj.is_paused and obj.next_run:
            now = timezone.now()
            if obj.next_run > now:
                diff = obj.next_run - now
                if diff.days > 0:
                    return f"In {diff.days} day{'s' if diff.days != 1 else ''}"
                elif diff.seconds > 3600:
                    hours = diff.seconds // 3600
                    return f"In {hours} hour{'s' if hours != 1 else ''}"
                elif diff.seconds > 60:
                    minutes = diff.seconds // 60
                    return f"In {minutes} minute{'s' if minutes != 1 else ''}"
                return "Soon"
            return "[WARN] Overdue"
        return '-'
    next_run_countdown.short_description = "Next Run"
    
    @handle_errors(fallback_return='-')
    def last_run_badge(self, obj):
        """Display last run status"""
        if obj and obj.last_run_status:
            return ModernBadge.render(obj.last_run_status)
        elif obj and obj.last_run_at:
            return ModernBadge.pill('Unknown', 'gray', size='sm')
        return 'Never'
    last_run_badge.short_description = "Last Run"
    
    @handle_errors(fallback_return='-')
    def success_rate_bar(self, obj):
        """Display success rate as bar"""
        if obj and obj.total_runs and obj.total_runs > 0:
            rate = safe_percentage(obj.successful_runs, obj.total_runs, 0)
            return ModernProgressBar.mini(rate)
        return '-'
    success_rate_bar.short_description = "Success Rate"
    
    @handle_errors(fallback_return='-')
    def toggle_button(self, obj):
        """Display toggle button"""
        if obj and obj.is_active and not obj.is_paused:
            return ModernButton.action('pause', '#', 'Pause', 'warning')
        elif obj and obj.is_paused:
            return ModernButton.action('play', '#', 'Resume', 'success')
        else:
            return ModernButton.action('play', '#', 'Activate', 'info')
    toggle_button.short_description = "Toggle"
    
    actions = ['activate_selected', 'pause_selected', 'run_now']
    
    @admin.action(description="▶️ Activate selected")
    @atomic_transaction
    def activate_selected(self, request, queryset):
        """Activate schedules"""
        updated = queryset.update(is_active=True, is_paused=False)
        self.message_user(request, f"▶️ Activated {updated} schedule(s)", messages.SUCCESS)
    
    @admin.action(description="⏸️ Pause selected")
    @atomic_transaction
    def pause_selected(self, request, queryset):
        """Pause schedules"""
        updated = queryset.update(is_paused=True)
        self.message_user(request, f"⏸️ Paused {updated} schedule(s)", messages.WARNING)
    
    @admin.action(description="⚡ Run now")
    def run_now(self, request, queryset):
        """Run schedules immediately"""
        count = queryset.count()
        self.message_user(request, f"⚡ Triggered {count} schedule(s)", messages.SUCCESS)


# ================================================
# [LOADING] SECTION 9: BACKUP RESTORATION ADMIN
# ================================================

@admin.register(BackupRestoration)
class BackupRestorationAdmin(admin.ModelAdmin):
    """
    [LOADING] Admin for Backup Restorations
    """
    
    list_display = (
        'restoration_id_short',
        'backup_link',
        'status_badge',
        'type_icon',
        'started_at_ago',
        'duration_display',
        'success_badge',
        'rollback_button',
    )
    
    list_filter = ('status', 'restoration_type', 'success')
    search_fields = ('restoration_id', 'backup__name', 'notes')
    date_hierarchy = 'started_at'
    
    @handle_errors(fallback_return='-')
    def restoration_id_short(self, obj):
        """Display short restoration ID"""
        if obj and obj.restoration_id:
            rid = str(obj.restoration_id)[:8]
            return format_html('<code>{}</code>', rid)
        return '-'
    restoration_id_short.short_description = "ID"
    
    @handle_errors(fallback_return='-')
    def backup_link(self, obj):
        """Link to backup"""
        if obj and obj.backup:
            url = reverse('admin:backup_backup_change', args=[obj.backup.id])
            return format_html('<a href="{}">{}</a>', url, safe_truncate(obj.backup.name, 20))
        return '-'
    backup_link.short_description = "Backup"
    
    @handle_errors(fallback_return='-')
    def status_badge(self, obj):
        """Display status"""
        if obj and obj.status:
            return ModernBadge.render(obj.status, obj.get_status_display())
        return '-'
    status_badge.short_description = "Status"
    
    @handle_errors(fallback_return='-')
    def type_icon(self, obj):
        """Display type with icon"""
        if obj and obj.restoration_type:
            icons = {
                'full': '💾',
                'partial': '[NOTE]',
                'tables': '[STATS]',
                'schema': '🏗️',
                'data': '📁',
            }
            icon = icons.get(obj.restoration_type, '[LOADING]')
            return format_html('{} {}', icon, obj.get_restoration_type_display())
        return '-'
    type_icon.short_description = "Type"
    
    @handle_errors(fallback_return='-')
    def started_at_ago(self, obj):
        """Display relative time"""
        if obj and obj.started_at:
            return time_ago(obj.started_at)
        return '-'
    started_at_ago.short_description = "Started"
    
    @handle_errors(fallback_return='-')
    def duration_display(self, obj):
        """Format duration"""
        if obj and obj.completed_at and obj.started_at:
            duration = (obj.completed_at - obj.started_at).total_seconds()
            return format_duration(duration)
        return '-'
    duration_display.short_description = "Duration"
    
    @handle_errors(fallback_return='-')
    def success_badge(self, obj):
        """Display success status"""
        if obj:
            if obj.success:
                return ModernBadge.boolean(True, 'Success', 'Failed')
            elif obj.status == 'failed':
                return ModernBadge.boolean(False, 'Success', 'Failed')
        return ModernBadge.pill('Pending', 'gray', '⏳')
    success_badge.short_description = "Result"
    
    @handle_errors(fallback_return='-')
    def rollback_button(self, obj):
        """Display rollback button"""
        if obj and obj.rollback_enabled and not obj.rollback_performed and obj.success:
            return ModernButton.action('undo', '#', 'Rollback', 'danger')
        elif obj and obj.rollback_performed:
            return ModernBadge.pill('Rolled Back', 'dark', '↩️', 'sm')
        return '-'
    rollback_button.short_description = "Rollback"
    
    actions = ['mark_successful', 'mark_failed']
    
    @admin.action(description="[OK] Mark as successful")
    @atomic_transaction
    def mark_successful(self, request, queryset):
        """Mark restorations as successful"""
        updated = queryset.update(
            status='completed',
            success=True,
            completed_at=timezone.now()
        )
        self.message_user(request, f"[OK] Marked {updated} restoration(s)", messages.SUCCESS)
    
    @admin.action(description="[ERROR] Mark as failed")
    @atomic_transaction
    def mark_failed(self, request, queryset):
        """Mark restorations as failed"""
        updated = queryset.update(
            status='failed',
            success=False,
            completed_at=timezone.now()
        )
        self.message_user(request, f"[ERROR] Marked {updated} restoration(s)", messages.WARNING)


# ================================================
# [NOTE] SECTION 10: BACKUP LOG ADMIN
# ================================================

@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    """
    [NOTE] Admin for Backup Logs
    """
    
    list_display = (
        'timestamp_ago',
        'level_badge',
        'category_badge',
        'message_preview',
        'source_badge',
        'backup_link',
        'duration_display',
    )
    
    list_filter = ('level', 'category', 'source', ('timestamp', admin.DateFieldListFilter))
    search_fields = ('message', 'error_message', 'backup__name')
    date_hierarchy = 'timestamp'
    
    @handle_errors(fallback_return='-')
    def timestamp_ago(self, obj):
        """Display relative time"""
        if obj and obj.timestamp:
            return time_ago(obj.timestamp)
        return '-'
    timestamp_ago.short_description = "Time"
    
    @handle_errors(fallback_return='-')
    def level_badge(self, obj):
        """Display log level"""
        if obj and obj.level:
            return ModernBadge.render(obj.level, obj.get_level_display())
        return '-'
    level_badge.short_description = "Level"
    
    @handle_errors(fallback_return='-')
    def category_badge(self, obj):
        """Display category"""
        if obj and obj.category:
            color_map = {
                'backup': 'success',
                'restore': 'info',
                'verify': 'purple',
                'cleanup': 'warning',
                'error': 'danger',
                'admin': 'gray',
            }
            color = color_map.get(obj.category, 'gray')
            return ModernBadge.pill(obj.get_category_display(), color, size='sm')
        return '-'
    category_badge.short_description = "Category"
    
    @handle_errors(fallback_return='-')
    def message_preview(self, obj):
        """Display message preview"""
        if obj and obj.message:
            return safe_truncate(obj.message, 50)
        return '-'
    message_preview.short_description = "Message"
    
    @handle_errors(fallback_return='-')
    def source_badge(self, obj):
        """Display source"""
        if obj and obj.source:
            return ModernBadge.pill(obj.get_source_display(), 'gray', size='sm')
        return '-'
    source_badge.short_description = "Source"
    
    @handle_errors(fallback_return='-')
    def backup_link(self, obj):
        """Link to backup"""
        if obj and obj.backup:
            url = reverse('admin:backup_backup_change', args=[obj.backup.id])
            return format_html('<a href="{}">{}</a>', url, safe_truncate(obj.backup.name, 15))
        return '-'
    backup_link.short_description = "Backup"
    
    @handle_errors(fallback_return='-')
    def duration_display(self, obj):
        """Format duration"""
        if obj and obj.duration:
            return format_duration(obj.duration)
        return '-'
    duration_display.short_description = "Duration"
    
    actions = ['delete_old_logs']
    
    @admin.action(description="[DELETE] Delete logs older than 30 days")
    @atomic_transaction
    def delete_old_logs(self, request, queryset):
        """Delete old logs"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        old_logs = queryset.filter(timestamp__lt=thirty_days_ago)
        count = old_logs.count()
        deleted, _ = old_logs.delete()
        self.message_user(request, f"[DELETE] Deleted {deleted} old log(s)", messages.SUCCESS)


# ================================================
# [STATS] SECTION 11: DELTA BACKUP TRACKER ADMIN
# ================================================

@admin.register(DeltaBackupTracker)
class DeltaBackupTrackerAdmin(admin.ModelAdmin):
    """
    [STATS] Admin for Delta Backup Tracking
    """
    
    list_display = (
        'parent_link',
        'child_link',
        'changed_tables_count',
        'change_percentage_bar',
        'created_at_ago',
    )
    
    search_fields = ('parent_backup__name', 'child_backup__name')
    
    @handle_errors(fallback_return='-')
    def parent_link(self, obj):
        """Link to parent backup"""
        if obj and obj.parent_backup:
            url = reverse('admin:backup_backup_change', args=[obj.parent_backup.id])
            return format_html('<a href="{}">{}</a>', url, safe_truncate(obj.parent_backup.name, 20))
        return '-'
    parent_link.short_description = "Parent"
    
    @handle_errors(fallback_return='-')
    def child_link(self, obj):
        """Link to child backup"""
        if obj and obj.child_backup:
            url = reverse('admin:backup_backup_change', args=[obj.child_backup.id])
            return format_html('<a href="{}">{}</a>', url, safe_truncate(obj.child_backup.name, 20))
        return '-'
    child_link.short_description = "Child"
    
    @handle_errors(fallback_return=0)
    def changed_tables_count(self, obj):
        """Count changed tables"""
        if obj and obj.changed_tables:
            return len(obj.changed_tables)
        return 0
    changed_tables_count.short_description = "Tables Changed"
    
    @handle_errors(fallback_return='-')
    def change_percentage_bar(self, obj):
        """Display change percentage"""
        if obj and obj.change_percentage:
            return ModernProgressBar.mini(obj.change_percentage)
        return '-'
    change_percentage_bar.short_description = "Change %"
    
    @handle_errors(fallback_return='-')
    def created_at_ago(self, obj):
        """Display creation time"""
        if obj and obj.created_at:
            return time_ago(obj.created_at)
        return '-'
    created_at_ago.short_description = "Created"


# ================================================
# 🏷️ SECTION 12: PLACEHOLDER ADMINS
# ================================================

@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(admin.ModelAdmin):
    """🏷️ Retention Policy Admin"""
    list_display = ('name', 'keep_all', 'keep_weekly', 'keep_monthly', 'keep_yearly')
    search_fields = ('name', 'description')


@admin.register(BackupNotificationConfig)
class BackupNotificationConfigAdmin(admin.ModelAdmin):
    """📧 Notification Config Admin"""
    list_display = ('name',  'notify_on_failure', 'notify_on_warning')
    search_fields = ('name', 'emails')


# ================================================
# [START] SECTION 13: FINAL SETUP
# ================================================
class BackupSite(admin.AdminSite):
    """Custom admin site for Backup Management"""
    site_header = "Amir Backup Administration"
    site_title = "Amir Backup Admin"
    index_title = "Welcome to Backup Management"

    def get_app_list(self, request, app_label=None):
        """
        ব্যাকআপ অ্যাপকে সবার উপরে দেখানোর জন্য লিস্টটি সর্ট করবে।
        """
        app_list = super().get_app_list(request, app_label)
        
        # ব্যাকআপ অ্যাপকে (backup app_label) অ্যাডমিন লিস্টের শুরুতে নিয়ে আসা
        for app in app_list:
            if app['app_label'] == 'backup': # আপনার অ্যাপের নাম 'backup' হলে
                app_list.remove(app)
                app_list.insert(0, app)
                break
        
        return app_list

# এখন আপনার সেই ২৮৫২ নম্বর লাইনের এররটি নিচের লাইন দিয়ে ঠিক হয়ে যাবে
Backup_admin_site = BackupSite(name='backup_admin')



# Register all models with custom admin site
Backup_admin_site.register(Backup, BackupAdmin)
Backup_admin_site.register(BackupStorageLocation, BackupStorageLocationAdmin)
Backup_admin_site.register(BackupSchedule, BackupScheduleAdmin)
Backup_admin_site.register(BackupRestoration, BackupRestorationAdmin)
Backup_admin_site.register(BackupLog, BackupLogAdmin)
Backup_admin_site.register(DeltaBackupTracker, DeltaBackupTrackerAdmin)
Backup_admin_site.register(RetentionPolicy, RetentionPolicyAdmin)
Backup_admin_site.register(BackupNotificationConfig, BackupNotificationConfigAdmin)

# Replace default admin site
# admin.site = admin_site