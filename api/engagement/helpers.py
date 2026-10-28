# engagement/helpers.py
"""
Helper functions and utilities for engagement system.
Provides common utility functions and helper methods.
"""
import json
import math
import random
import string
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth import get_user_model

from .constants import (
    CHECKIN_BASE_COINS, CHECKIN_STREAK_BONUS_MULTIPLIER,
    SPIN_BASE_COINS, SPIN_MULTIPLIERS, LEVEL_XP_REQUIREMENTS
)


# ── Math Utilities ───────────────────────────────────────────────────────────

def calculate_level(xp):
    """Calculate user level based on XP."""
    for level, required_xp in enumerate(LEVEL_XP_REQUIREMENTS, 1):
        if xp < required_xp:
            return level - 1
    return len(LEVEL_XP_REQUIREMENTS)


def calculate_level_progress(xp, level):
    """Calculate progress towards next level."""
    if level >= len(LEVEL_XP_REQUIREMENTS):
        return 1.0
    
    current_level_xp = LEVEL_XP_REQUIREMENTS[level - 1] if level > 1 else 0
    next_level_xp = LEVEL_XP_REQUIREMENTS[level]
    
    if next_level_xp <= current_level_xp:
        return 1.0
    
    progress = (xp - current_level_xp) / (next_level_xp - current_level_xp)
    return min(max(progress, 0.0), 1.0)


def calculate_checkin_coins(streak, bonus_claimed=False, shield_used=False):
    """Calculate coins earned from check-in."""
    base_coins = CHECKIN_BASE_COINS
    
    # Streak bonus
    streak_bonus = 0
    if not shield_used and streak > 1:
        streak_bonus = base_coins * (streak - 1) * CHECKIN_STREAK_BONUS_MULTIPLIER
    
    # Bonus claim
    bonus_coins = 0
    if bonus_claimed:
        bonus_coins = base_coins * 2  # Double coins for bonus
    
    total_coins = base_coins + streak_bonus + bonus_coins
    return round(total_coins, 2)


def calculate_spin_coins(multiplier=1.0, is_boosted=False):
    """Calculate coins won from spin."""
    base_coins = SPIN_BASE_COINS * multiplier
    
    if is_boosted:
        base_coins *= 2.0  # Double for boosted spins
    
    return round(base_coins, 2)


def calculate_quest_rewards(base_coins, base_xp, difficulty_multiplier=1.0):
    """Calculate quest rewards based on difficulty."""
    coins = base_coins * difficulty_multiplier
    xp = int(base_xp * difficulty_multiplier)
    
    return {
        'coins': round(coins, 2),
        'xp': xp
    }


def calculate_achievement_progress(current_value, required_value):
    """Calculate achievement progress percentage."""
    if required_value == 0:
        return 0.0
    
    progress = (current_value / required_value) * 100
    return min(max(progress, 0.0), 100.0)


def calculate_leaderboard_rank(total_coins, period_coins):
    """Calculate leaderboard rank based on coins."""
    # This is a simplified calculation
    # In practice, this would query the actual leaderboard
    rank = int(period_coins / 100) + 1
    return max(rank, 1)


def calculate_referral_bonus(referral_count, base_bonus=10.0):
    """Calculate referral bonus based on number of referrals."""
    if referral_count <= 5:
        return base_bonus
    elif referral_count <= 10:
        return base_bonus * 1.5
    elif referral_count <= 25:
        return base_bonus * 2.0
    else:
        return base_bonus * 3.0


# ── String Utilities ───────────────────────────────────────────────────────

def generate_referral_code(length=8):
    """Generate random referral code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_achievement_id(prefix='ACH'):
    """Generate unique achievement ID."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}_{timestamp}_{random_str}"


def generate_session_token(length=32):
    """Generate random session token."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_webhook_secret(length=32):
    """Generate webhook secret."""
    return ''.join(random.choices(string.ascii_letters + string.digits + '!@#$%^&*', k=length))


def slugify_text(text):
    """Convert text to slug format."""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug


def truncate_text(text, max_length=50, suffix='...'):
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_number(number, decimal_places=2):
    """Format number with specified decimal places."""
    if isinstance(number, (int, float)):
        return f"{number:.{decimal_places}f}"
    elif isinstance(number, Decimal):
        return f"{number:.{decimal_places}f}"
    return str(number)


def format_currency(amount, currency='coins'):
    """Format currency amount."""
    formatted_amount = format_number(amount, 2)
    return f"{formatted_amount} {currency}"


def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h"
    else:
        days = seconds // 86400
        return f"{days}d"


def format_date_range(start_date, end_date):
    """Format date range for display."""
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    if start_date == end_date:
        return start_date.strftime('%b %d, %Y')
    
    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    else:
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"


# ── Date/Time Utilities ─────────────────────────────────────────────────────

def get_start_of_day(dt=None):
    """Get start of day for given datetime."""
    if dt is None:
        dt = timezone.now()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt=None):
    """Get end of day for given datetime."""
    if dt is None:
        dt = timezone.now()
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def get_start_of_week(dt=None):
    """Get start of week for given datetime."""
    if dt is None:
        dt = timezone.now()
    return dt - timedelta(days=dt.weekday())


def get_end_of_week(dt=None):
    """Get start of week for given datetime."""
    if dt is None:
        dt = timezone.now()
    return get_start_of_week(dt) + timedelta(days=6)


def get_start_of_month(dt=None):
    """Get start of month for given datetime."""
    if dt is None:
        dt = timezone.now()
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def get_end_of_month(dt=None):
    """Get end of month for given datetime."""
    if dt is None:
        dt = timezone.now()
    
    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1)
    
    return next_month - timedelta(seconds=1)


def get_days_ago(days):
    """Get datetime for N days ago."""
    return timezone.now() - timedelta(days=days)


def get_hours_ago(hours):
    """Get datetime for N hours ago."""
    return timezone.now() - timedelta(hours=hours)


def get_minutes_ago(minutes):
    """Get datetime for N minutes ago."""
    return timezone.now() - timedelta(minutes=minutes)


def is_today(dt):
    """Check if datetime is today."""
    return dt.date() == timezone.now().date()


def is_yesterday(dt):
    """Check if datetime is yesterday."""
    yesterday = timezone.now().date() - timedelta(days=1)
    return dt.date() == yesterday


def is_this_week(dt):
    """Check if datetime is this week."""
    start_of_week = get_start_of_week()
    return dt.date() >= start_of_week.date()


def is_this_month(dt):
    """Check if datetime is this month."""
    return dt.month == timezone.now().month and dt.year == timezone.now().year


def get_age_in_days(birth_date):
    """Get age in days from birth date."""
    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    
    today = timezone.now().date()
    return (today - birth_date).days


def get_streak_dates(start_date, end_date):
    """Get list of dates for a streak period."""
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    dates = []
    current_date = start_date
    
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    return dates


# ── Cache Utilities ─────────────────────────────────────────────────────

def get_cache_key(*parts):
    """Generate cache key from parts."""
    return ":".join(str(part) for part in parts)


def cache_result(key_func, timeout=300):
    """Decorator to cache function results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_key = key_func(*args, **kwargs)
            result = cache.get(cache_key)
            
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern):
    """Invalidate cache keys matching pattern."""
    try:
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)
    except Exception:
        pass  # Cache might not support pattern deletion


def get_user_cache_key(user_id, *parts):
    """Get user-specific cache key."""
    return get_cache_key('user', user_id, *parts)


def get_tenant_cache_key(tenant_id, *parts):
    """Get tenant-specific cache key."""
    return get_cache_key('tenant', tenant_id, *parts)


# ── Validation Utilities ─────────────────────────────────────────────────────

def validate_email(email):
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username):
    """Validate username format."""
    import re
    pattern = r'^[a-zA-Z0-9_]{3,30}$'
    return re.match(pattern, username) is not None


def validate_phone_number(phone):
    """Validate phone number format."""
    import re
    pattern = r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$'
    return re.match(pattern, phone) is not None


def validate_url(url):
    """Validate URL format."""
    import re
    pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    return re.match(pattern, url) is not None


def validate_json(data):
    """Validate JSON data."""
    try:
        json.loads(data)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def validate_uuid(uuid_string):
    """Validate UUID format."""
    import uuid
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False


# ── Security Utilities ─────────────────────────────────────────────────────

def generate_hash(data, salt=None):
    """Generate hash for data."""
    import hashlib
    
    if salt is None:
        salt = settings.SECRET_KEY.encode()
    
    hash_object = hashlib.sha256(f"{data}{salt}".encode())
    return hash_object.hexdigest()


def verify_hash(data, hash_value, salt=None):
    """Verify hash against data."""
    return generate_hash(data, salt) == hash_value


def generate_token(length=32):
    """Generate random token."""
    import secrets
    return secrets.token_urlsafe(length)


def encrypt_data(data, key=None):
    """Encrypt data using Fernet."""
    try:
        from cryptography.fernet import Fernet
        
        if key is None:
            key = settings.ENCRYPTION_KEY.encode()
        
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(data.encode())
        return encrypted_data.decode()
    except ImportError:
        return data  # Fallback if cryptography not available


def decrypt_data(encrypted_data, key=None):
    """Decrypt data using Fernet."""
    try:
        from cryptography.fernet import Fernet
        
        if key is None:
            key = settings.ENCRYPTION_KEY.encode()
        
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data.encode())
        return decrypted_data.decode()
    except ImportError:
        return encrypted_data  # Fallback if cryptography not available


def mask_sensitive_data(data, mask_char='*', visible_chars=4):
    """Mask sensitive data for logging."""
    if not data or len(data) <= visible_chars:
        return data
    
    visible_start = data[:visible_chars // 2]
    visible_end = data[-(visible_chars // 2):]
    masked_middle = mask_char * (len(data) - visible_chars)
    
    return visible_start + masked_middle + visible_end


# ── API Utilities ─────────────────────────────────────────────────────

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get user agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')


def parse_pagination_params(request):
    """Parse pagination parameters from request."""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # Validate and limit page size
        page_size = max(min(page_size, 100), 1)
        page = max(page, 1)
        
        return page, page_size
    except ValueError:
        return 1, 20


def build_pagination_response(data, page, page_size, total_count):
    """Build pagination response."""
    total_pages = math.ceil(total_count / page_size)
    has_next = page < total_pages
    has_previous = page > 1
    
    return {
        'page': page,
        'page_size': page_size,
        'total_count': total_count,
        'total_pages': total_pages,
        'has_next': has_next,
        'has_previous': has_previous,
        'data': data
    }


def format_api_response(success=True, data=None, message=None, error=None, code=None):
    """Format standard API response."""
    response = {'success': success}
    
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    if error:
        response['error'] = error
    if code:
        response['code'] = code
    
    return response


def handle_api_exception(exc):
    """Handle API exceptions and return formatted response."""
    if hasattr(exc, 'default_code'):
        return format_api_response(
            success=False,
            error=exc.detail,
            code=exc.default_code
        ), getattr(exc, 'status_code', 400)
    else:
        return format_api_response(
            success=False,
            error=str(exc),
            code='INTERNAL_ERROR'
        ), 500


# ── File Utilities ─────────────────────────────────────────────────────

def get_file_extension(filename):
    """Get file extension from filename."""
    return filename.split('.')[-1].lower() if '.' in filename else ''


def generate_safe_filename(filename):
    """Generate safe filename for upload."""
    import os
    
    # Remove directory paths
    safe_name = os.path.basename(filename)
    
    # Remove special characters
    import re
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', safe_name)
    
    # Add timestamp to avoid conflicts
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(safe_name)
    
    return f"{name}_{timestamp}{ext}"


def get_file_size_mb(size_bytes):
    """Convert file size to MB."""
    return round(size_bytes / (1024 * 1024), 2)


def is_image_file(filename):
    """Check if file is an image."""
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    extension = get_file_extension(filename)
    return extension in image_extensions


def is_document_file(filename):
    """Check if file is a document."""
    document_extensions = ['pdf', 'doc', 'docx', 'txt', 'rtf']
    extension = get_file_extension(filename)
    return extension in document_extensions


# ── Data Processing Utilities ─────────────────────────────────────────────

def chunk_list(lst, chunk_size):
    """Split list into chunks."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def flatten_dict(d, parent_key='', sep='.'):
    """Flatten nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def merge_dicts(*dicts):
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def remove_none_values(d):
    """Remove None values from dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def convert_to_decimal(value):
    """Convert value to Decimal."""
    if isinstance(value, Decimal):
        return value
    elif isinstance(value, (int, float, str)):
        return Decimal(str(value))
    else:
        return Decimal('0')


def round_decimal(value, decimal_places=2):
    """Round decimal to specified places."""
    if isinstance(value, Decimal):
        return value.quantize(Decimal(f'0.{decimal_places * "0"}'), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal(f'0.{decimal_places * "0"}'), rounding=ROUND_HALF_UP)


# ── Notification Utilities ─────────────────────────────────────────────────────

def send_push_notification(user_ids, title, body, data=None):
    """Send push notification to users."""
    try:
        from .services.notification_service import NotificationService
        
        for user_id in user_ids:
            NotificationService.send_push(
                user_id,
                title=title,
                body=body,
                data=data or {}
            )
        
        return True
    except Exception:
        return False


def send_email_notification(user_ids, subject, message, template=None):
    """Send email notification to users."""
    try:
        from .services.notification_service import NotificationService
        
        for user_id in user_ids:
            NotificationService.send_email(
                user_id,
                subject=subject,
                message=message,
                template=template
            )
        
        return True
    except Exception:
        return False


def format_notification_message(template, **kwargs):
    """Format notification message with template variables."""
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        return f"Template error: missing variable {exc}"


# ── Analytics Utilities ─────────────────────────────────────────────────────

def calculate_growth_rate(current_value, previous_value):
    """Calculate growth rate percentage."""
    if previous_value == 0:
        return 0.0
    
    growth = ((current_value - previous_value) / previous_value) * 100
    return round(growth, 2)


def calculate_percentile(values, percentile):
    """Calculate percentile value from list."""
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    
    if index.is_integer():
        return sorted_values[int(index)]
    else:
        lower_index = int(index)
        upper_index = lower_index + 1
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        
        fraction = index - lower_index
        return lower_value + (upper_value - lower_value) * fraction


def calculate_moving_average(values, window_size):
    """Calculate moving average."""
    if not values or window_size <= 0:
        return []
    
    moving_averages = []
    for i in range(len(values) - window_size + 1):
        window = values[i:i + window_size]
        average = sum(window) / window_size
        moving_averages.append(average)
    
    return moving_averages


def group_by_period(data, period='day'):
    """Group data by time period."""
    grouped = {}
    
    for item in data:
        date_field = item.get('date') or item.get('created_at')
        if not date_field:
            continue
        
        if isinstance(date_field, datetime):
            date_field = date_field.date()
        
        if period == 'day':
            key = date_field
        elif period == 'week':
            key = date_field - timedelta(days=date_field.weekday())
        elif period == 'month':
            key = date_field.replace(day=1)
        else:
            key = date_field
        
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(item)
    
    return grouped


# ── Gamification Utilities ───────────────────────────────────────────────────

def calculate_streak_bonus(streak_length, base_bonus=10):
    """Calculate streak bonus based on length."""
    if streak_length <= 1:
        return 0
    
    # Exponential growth with diminishing returns
    bonus = base_bonus * math.log(streak_length, 2)
    return round(bonus, 2)


def calculate_milestone_reward(current_milestone, next_milestone, base_reward=100):
    """Calculate milestone reward."""
    progress = (current_milestone / next_milestone) * 100
    bonus_multiplier = 1 + (progress / 100)
    
    reward = base_reward * bonus_multiplier
    return round(reward, 2)


def calculate_social_bonus(interactions, base_bonus=5):
    """Calculate social interaction bonus."""
    if interactions <= 10:
        return base_bonus * interactions
    elif interactions <= 50:
        return base_bonus * 10 + (interactions - 10) * (base_bonus * 0.5)
    else:
        return base_bonus * 30 + (interactions - 50) * (base_bonus * 0.2)


def calculate_seasonal_multiplier(season_type, base_multiplier=1.0):
    """Calculate seasonal multiplier."""
    multipliers = {
        'holiday': 1.5,
        'special': 1.25,
        'competition': 1.75,
        'community': 1.1,
        'normal': 1.0
    }
    
    return multipliers.get(season_type, base_multiplier)


# ── Utility Classes ─────────────────────────────────────────────────────

class Timer:
    """Simple timer utility."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Start timer."""
        self.start_time = timezone.now()
        return self
    
    def stop(self):
        """Stop timer."""
        self.end_time = timezone.now()
        return self
    
    def elapsed(self):
        """Get elapsed time."""
        if self.start_time is None:
            return 0
        
        end = self.end_time or timezone.now()
        return (end - self.start_time).total_seconds()


class RateLimiter:
    """Simple rate limiter."""
    
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def is_allowed(self):
        """Check if request is allowed."""
        now = timezone.now()
        
        # Remove old requests outside time window
        self.requests = [req for req in self.requests if now - req < timedelta(seconds=self.time_window)]
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False


class ProgressTracker:
    """Progress tracking utility."""
    
    def __init__(self, total_steps):
        self.total_steps = total_steps
        self.current_step = 0
        self.start_time = timezone.now()
    
    def advance(self, steps=1):
        """Advance progress."""
        self.current_step = min(self.current_step + steps, self.total_steps)
    
    def get_progress(self):
        """Get progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100
    
    def is_complete(self):
        """Check if progress is complete."""
        return self.current_step >= self.total_steps
    
    def get_eta(self):
        """Get estimated time remaining."""
        if self.current_step == 0:
            return None
        
        elapsed = (timezone.now() - self.start_time).total_seconds()
        rate = self.current_step / elapsed
        remaining_steps = self.total_steps - self.current_step
        
        if rate == 0:
            return None
        
        return timedelta(seconds=remaining_steps / rate)
