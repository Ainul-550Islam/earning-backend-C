# api/cms/helpers.py
"""
CMS Helper utilities — reusable functions used across the project.
No Django model imports here — pure utility functions only.
"""
from django.utils import timezone
import hashlib
import hmac
import logging
import os
import re
import datetime
from typing import Optional
import time
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, urljoin

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# STRING HELPERS
# ══════════════════════════════════════════════════════════════════

def slugify(text: str, max_length: int = 200) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s\-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text[:max_length]


def unique_slug(base_slug: str, model_class, slug_field: str = 'slug') -> str:
    """Generate a unique slug by appending counter if needed."""
    slug = slugify(base_slug)
    counter = 1
    while model_class.objects.filter(**{slug_field: slug}).exists():
        slug = f"{slugify(base_slug)}-{counter}"
        counter += 1
    return slug


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if not text or len(text) <= max_length:
        return text or ''
    return text[:max_length - len(suffix)].rstrip() + suffix


def strip_html_tags(html: str) -> str:
    """Remove all HTML tags from string safely (no strip_tags DoS risk)."""
    if not html:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def sanitize_html(html: str, allowed_tags: Optional[List[str]] = None) -> str:
    """
    Basic HTML sanitization — removes dangerous tags/attributes.
    For full sanitization, use bleach library in production.
    """
    if not html:
        return ''
    dangerous = re.compile(
        r'<\s*(script|iframe|object|embed|form|input|button|meta|link|style)'
        r'[^>]*>.*?<\s*/\s*\1\s*>|<\s*(script|iframe|object|embed)[^>]*/?\s*>',
        re.IGNORECASE | re.DOTALL
    )
    html = dangerous.sub('', html)
    html = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
    html = re.sub(r'\shref\s*=\s*["\']javascript:[^"\']*["\']', '', html, flags=re.IGNORECASE)
    return html


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def mask_sensitive(value: str, visible_chars: int = 4, mask_char: str = '*') -> str:
    """Mask sensitive data like email/account numbers."""
    if not value or len(value) <= visible_chars:
        return mask_char * len(value) if value else ''
    return value[:visible_chars] + mask_char * (len(value) - visible_chars)


def mask_email(email: str) -> str:
    """Mask email: us***@gmail.com"""
    if not email or '@' not in email:
        return mask_sensitive(email)
    local, domain = email.split('@', 1)
    return f"{local[:2]}{'*' * (len(local) - 2)}@{domain}"


def generate_token(length: int = 32) -> str:
    """Generate cryptographically secure random token."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:max(0, length - 32)]


def generate_short_id(length: int = 8) -> str:
    """Generate short uppercase ID (for referral codes etc.)."""
    import secrets
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ══════════════════════════════════════════════════════════════════
# NUMERIC / DECIMAL HELPERS
# ══════════════════════════════════════════════════════════════════

def round_decimal(value: Union[Decimal, float, str], places: int = 2) -> Decimal:
    """Round decimal to N places using ROUND_HALF_UP."""
    quantize_str = Decimal('0.' + '0' * places)
    return Decimal(str(value)).quantize(quantize_str, rounding=ROUND_HALF_UP)


def usd_to_coins(usd: Decimal, ratio: Decimal) -> Decimal:
    """Convert USD to virtual coins: $1 = ratio coins."""
    if ratio <= 0:
        return Decimal('0')
    return (usd * ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def coins_to_usd(coins: Decimal, ratio: Decimal) -> Decimal:
    """Convert virtual coins to USD."""
    if ratio <= 0:
        return Decimal('0')
    return (coins / ratio).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_fee(amount: Decimal, rate: Decimal) -> Tuple[Decimal, Decimal]:
    """Calculate fee and net amount. Returns (fee, net)."""
    fee = (amount * rate).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    net = (amount - fee).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return fee, net


def format_currency(amount: Union[Decimal, float], currency: str = 'USD',
                     symbol: str = '$') -> str:
    """Format amount as currency string."""
    try:
        val = float(amount)
        return f"{symbol}{val:,.2f} {currency}"
    except (TypeError, ValueError):
        return f"{symbol}0.00 {currency}"


def percentage(part: Union[int, float], total: Union[int, float],
               decimal_places: int = 1) -> float:
    """Calculate percentage safely."""
    if not total:
        return 0.0
    return round((part / total) * 100, decimal_places)


# ══════════════════════════════════════════════════════════════════
# DATETIME HELPERS
# ══════════════════════════════════════════════════════════════════

def get_date_range(period: str = 'week'):
    """Return (start_date, end_date) for given period."""
    from django.utils import timezone
    import datetime
    now = timezone.now()
    today = now.date()
    if period == 'today':
        return today, today
    elif period == 'yesterday':
        y = today - datetime.timedelta(days=1)
        return y, y
    elif period == 'week':
        start = today - datetime.timedelta(days=today.weekday())
        return start, today
    elif period == 'month':
        return today.replace(day=1), today
    elif period == 'year':
        return today.replace(month=1, day=1), today
    elif period == 'last_7':
        return today - datetime.timedelta(days=7), today
    elif period == 'last_30':
        return today - datetime.timedelta(days=30), today
    elif period == 'last_90':
        return today - datetime.timedelta(days=90), today
    return today, today


def time_since(dt) -> str:
    """Human-readable time since: '2 hours ago', '3 days ago'."""
    from django.utils import timezone
    import datetime
    if not dt:
        return 'never'
    now = timezone.now()
    if not timezone.is_aware(dt):
        import pytz
        dt = pytz.utc.localize(dt)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    elif seconds < 604800:
        return f"{seconds // 86400}d ago"
    elif seconds < 2592000:
        return f"{seconds // 604800}w ago"
    elif seconds < 31536000:
        return f"{seconds // 2592000}mo ago"
    return f"{seconds // 31536000}y ago"


def is_today(dt) -> bool:
    """Check if datetime is today."""
    from django.utils import timezone
    return dt.date() == timezone.now().date() if dt else False


def days_until(dt) -> int:
    """Days until a future datetime."""
    from django.utils import timezone
    if not dt:
        return 0
    return max(0, (dt.date() - timezone.now().date()).days)


# ══════════════════════════════════════════════════════════════════
# URL HELPERS
# ══════════════════════════════════════════════════════════════════

def build_url(base_url: str, path: str = '', params: Dict = None) -> str:
    """Build URL with optional path and query params."""
    url = urljoin(base_url, path) if path else base_url
    if params:
        url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"
    return url


def append_subid(url: str, subid: str) -> str:
    """Append subid to URL for CPAlead tracking."""
    if not subid:
        return url
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}subid={subid}"


def is_valid_url(url: str) -> bool:
    """Check if URL is valid http/https."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        return urlparse(url).netloc
    except Exception:
        return ''


def get_client_ip(request) -> str:
    """Get real client IP, respecting X-Forwarded-For."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded:
        ip = x_forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


# ══════════════════════════════════════════════════════════════════
# CRYPTO / SECURITY HELPERS
# ══════════════════════════════════════════════════════════════════

def hmac_sign(message: str, secret: str, algorithm: str = 'sha256') -> str:
    """Generate HMAC signature."""
    h = hmac.new(secret.encode(), message.encode(), algorithm)
    return h.hexdigest()


def hmac_verify(message: str, signature: str, secret: str,
                algorithm: str = 'sha256') -> bool:
    """Verify HMAC signature (timing-safe)."""
    expected = hmac_sign(message, secret, algorithm)
    return hmac.compare_digest(expected, signature)


def hash_value(value: str, salt: str = '', algorithm: str = 'sha256') -> str:
    """Hash a value with optional salt."""
    data = (salt + value).encode()
    return hashlib.new(algorithm, data).hexdigest()


def generate_hmac_password(subid: str, lead_id: str, payout: str,
                            secret: str) -> str:
    """Generate CPAlead-compatible postback password."""
    message = f"{subid}:{lead_id}:{payout}"
    return hmac_sign(message, secret)


# ══════════════════════════════════════════════════════════════════
# FILE HELPERS
# ══════════════════════════════════════════════════════════════════

def get_file_extension(filename: str) -> str:
    """Get lowercase file extension without dot."""
    _, ext = os.path.splitext(filename)
    return ext.lstrip('.').lower()


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


def safe_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^\w\-]', '_', name)
    return f"{name[:100]}{ext.lower()}"


def generate_upload_path(prefix: str, filename: str) -> str:
    """Generate unique upload path: prefix/YYYY/MM/uuid_filename."""
    from django.utils import timezone
    now = timezone.now()
    ext = get_file_extension(filename)
    unique = uuid.uuid4().hex[:16]
    return f"{prefix}/{now.year}/{now.month:02d}/{unique}.{ext}"


# ══════════════════════════════════════════════════════════════════
# DICT / DATA HELPERS
# ══════════════════════════════════════════════════════════════════

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dicts. Override values take precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Flatten nested dict: {'a': {'b': 1}} → {'a.b': 1}"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def pick(d: Dict, keys: List[str]) -> Dict:
    """Pick only specified keys from dict."""
    return {k: v for k, v in d.items() if k in keys}


def omit(d: Dict, keys: List[str]) -> Dict:
    """Omit specified keys from dict."""
    return {k: v for k, v in d.items() if k not in keys}


def chunk_list(lst: List, size: int) -> List[List]:
    """Split list into chunks of given size."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def remove_none(d: Dict) -> Dict:
    """Remove None values from dict."""
    return {k: v for k, v in d.items() if v is not None}


def first_non_none(*values):
    """Return first non-None value."""
    return next((v for v in values if v is not None), None)


# ══════════════════════════════════════════════════════════════════
# DEVICE / GEO HELPERS
# ══════════════════════════════════════════════════════════════════

def detect_device(user_agent: str) -> str:
    """Detect device type from User-Agent string."""
    ua = (user_agent or '').lower()
    if any(k in ua for k in ['ipad', 'tablet', 'kindle', 'playbook', 'silk']):
        return 'tablet'
    if any(k in ua for k in ['mobile', 'android', 'iphone', 'ipod', 'blackberry',
                               'windows phone', 'opera mini', 'palm']):
        return 'mobile'
    return 'desktop'


def get_country_from_ip(ip: str, db_path: str = '') -> str:
    """Get ISO country code from IP using GeoIP2."""
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return ''
    try:
        import geoip2.database
        db_path = db_path or __import__('django.conf', fromlist=['settings']).settings.GEOIP_PATH
        with geoip2.database.Reader(f"{db_path}/GeoLite2-Country.mmdb") as reader:
            response = reader.country(ip)
            return response.country.iso_code or ''
    except Exception:
        return ''


def is_tier1_country(country_code: str) -> bool:
    """Check if country is Tier 1 (US, UK, CA, AU) — higher CPAlead payouts."""
    return country_code.upper() in {'US', 'GB', 'CA', 'AU', 'NZ', 'IE'}


# ══════════════════════════════════════════════════════════════════
# RESPONSE HELPERS
# ══════════════════════════════════════════════════════════════════

def success_response(data: Any = None, message: str = '', status: int = 200) -> Dict:
    """Standard success response dict."""
    resp = {'success': True, 'status': status}
    if message:
        resp['message'] = message
    if data is not None:
        resp['data'] = data
    return resp


def error_response(message: str, code: str = 'error', status: int = 400,
                   errors: Dict = None) -> Dict:
    """Standard error response dict."""
    resp = {'success': False, 'error': {'code': code, 'message': message, 'status': status}}
    if errors:
        resp['error']['details'] = errors
    return resp


def paginated_response(results: List, count: int, page: int,
                        page_size: int, total_pages: int) -> Dict:
    """Standard paginated response."""
    return {
        'count': count,
        'total_pages': total_pages,
        'current_page': page,
        'page_size': page_size,
        'results': results,
    }


# ══════════════════════════════════════════════════════════════════
# TIMING / PERFORMANCE HELPERS
# ══════════════════════════════════════════════════════════════════

class Timer:
    """Context manager for timing code blocks."""
    def __init__(self, name: str = ''):
        self.name = name
        self.elapsed_ms = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
        if self.name:
            logger.debug(f"[Timer] {self.name}: {self.elapsed_ms:.2f}ms")

    def __str__(self):
        return f"{self.elapsed_ms:.2f}ms"


def retry(max_attempts: int = 3, delay_sec: float = 0.5,
          exceptions: tuple = (Exception,)):
    """Decorator to retry function on exception."""
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay_sec * (2 ** attempt))
                    logger.warning(f"[Retry] {func.__name__} attempt {attempt + 1}/{max_attempts}: {e}")
            raise last_exc
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════
# SURVEY & PROFILE HELPERS
# ══════════════════════════════════════════════════════════════════

def calculate_profile_completeness(profile_data: Dict[str, Any]) -> float:
    """Calculate profile completeness percentage."""
    required_fields = [
        'date_of_birth', 'gender', 'country', 'education',
        'income_level', 'primary_language', 'interests'
    ]
    optional_fields = [
        'state_province', 'city', 'postal_code', 'occupation',
        'industry', 'hobbies', 'additional_languages'
    ]
    
    completed_required = sum(1 for field in required_fields if profile_data.get(field))
    completed_optional = sum(1 for field in optional_fields if profile_data.get(field))
    
    required_weight = 0.7  # 70% weight for required fields
    optional_weight = 0.3  # 30% weight for optional fields
    
    required_score = (completed_required / len(required_fields)) * required_weight * 100
    optional_score = (completed_optional / len(optional_fields)) * optional_weight * 100
    
    return round(required_score + optional_score, 1)


def validate_survey_response(response_data: Dict[str, Any], 
                        question_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate survey response against question requirements."""
    errors = []
    question_type = question_data.get('question_type', 'text')
    is_required = question_data.get('is_required', False)
    
    # Check if required question is answered
    if is_required and not response_data.get('answer'):
        errors.append("This question is required")
        return False, errors
    
    answer = response_data.get('answer')
    if not answer:
        return True, errors
    
    # Type-specific validation
    if question_type == 'multiple_choice':
        valid_options = question_data.get('options', [])
        if answer not in valid_options:
            errors.append(f"Invalid option. Valid options: {valid_options}")
    
    elif question_type == 'multiple_select':
        valid_options = question_data.get('options', [])
        if not isinstance(answer, list):
            errors.append("Multiple select answers must be a list")
        else:
            for option in answer:
                if option not in valid_options:
                    errors.append(f"Invalid option: {option}")
    
    elif question_type == 'number':
        try:
            num_answer = float(answer)
            min_val = question_data.get('min_value')
            max_val = question_data.get('max_value')
            
            if min_val is not None and num_answer < min_val:
                errors.append(f"Value must be at least {min_val}")
            if max_val is not None and num_answer > max_val:
                errors.append(f"Value must be at most {max_val}")
        except ValueError:
            errors.append("Invalid number format")
    
    elif question_type == 'email':
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, answer):
            errors.append("Invalid email format")
    
    elif question_type == 'url':
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, answer):
            errors.append("Invalid URL format")
    
    return len(errors) == 0, errors


def calculate_survey_quality_score(responses: List[Dict[str, Any]], 
                             time_spent_seconds: int) -> float:
    """Calculate quality score for survey completion."""
    if not responses:
        return 0.0
    
    score_components = []
    
    # Component 1: Answer completeness (40%)
    answered_questions = len([r for r in responses if r.get('answer')])
    total_questions = len(responses)
    completeness_score = (answered_questions / total_questions) * 40
    score_components.append(completeness_score)
    
    # Component 2: Time appropriateness (30%)
    avg_time_per_question = time_spent_seconds / total_questions if total_questions > 0 else 0
    # Assume 30 seconds per question is optimal
    optimal_time = 30
    time_score = max(0, 30 - abs(avg_time_per_question - optimal_time)) / 30 * 30
    score_components.append(time_score)
    
    # Component 3: Answer consistency (20%)
    # This would need more complex logic based on question patterns
    consistency_score = 20.0  # Placeholder
    score_components.append(consistency_score)
    
    # Component 4: No suspicious patterns (10%)
    # Check for straight-lining, random patterns, etc.
    pattern_score = 10.0  # Placeholder
    score_components.append(pattern_score)
    
    return round(sum(score_components), 2)


def match_user_to_segment(user_profile: Dict[str, Any], 
                        segment_criteria: Dict[str, Any]) -> bool:
    """Check if user profile matches segment criteria."""
    # Age matching
    user_age = user_profile.get('age')
    if user_age and segment_criteria.get('age_min') and user_age < segment_criteria['age_min']:
        return False
    if user_age and segment_criteria.get('age_max') and user_age > segment_criteria['age_max']:
        return False
    
    # Gender matching
    user_gender = user_profile.get('gender')
    segment_genders = segment_criteria.get('genders', [])
    if segment_genders and user_gender not in segment_genders:
        return False
    
    # Country matching
    user_country = user_profile.get('country')
    segment_countries = segment_criteria.get('countries', [])
    if segment_countries and user_country not in segment_countries:
        return False
    
    # Education matching
    user_education = user_profile.get('education')
    segment_education = segment_criteria.get('education_levels', [])
    if segment_education and user_education not in segment_education:
        return False
    
    # Income level matching
    user_income = user_profile.get('income_level')
    segment_income = segment_criteria.get('income_levels', [])
    if segment_income and user_income not in segment_income:
        return False
    
    # Interest matching (at least one matching interest)
    user_interests = user_profile.get('interests', [])
    segment_interests = segment_criteria.get('interests', [])
    if segment_interests and not any(interest in user_interests for interest in segment_interests):
        return False
    
    # Score thresholds
    user_participation = user_profile.get('survey_participation_score', 0)
    min_participation = segment_criteria.get('min_participation_score', 0)
    if user_participation < min_participation:
        return False
    
    user_quality = user_profile.get('quality_score', 0)
    min_quality = segment_criteria.get('min_quality_score', 0)
    if user_quality < min_quality:
        return False
    
    return True


# ══════════════════════════════════════════════════════════════════
# REWARD CALCULATION HELPERS
# ══════════════════════════════════════════════════════════════════

def calculate_survey_reward(base_amount: Decimal, 
                         quality_score: float,
                         reward_config: Dict[str, Any]) -> Decimal:
    """Calculate survey reward based on quality and configuration."""
    reward_type = reward_config.get('reward_type', 'fixed')
    
    if reward_type == 'fixed':
        return base_amount
    
    elif reward_type == 'tiered':
        # Apply bonus based on quality score
        bonus_threshold = reward_config.get('min_quality_for_bonus', 0.8)
        bonus_amount = reward_config.get('bonus_amount', Decimal('0.00'))
        
        if quality_score >= bonus_threshold:
            return base_amount + bonus_amount
        return base_amount
    
    elif reward_type == 'performance':
        # Scale reward based on quality score
        multiplier = Decimal(str(quality_score))
        return (base_amount * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return base_amount


def apply_reward_penalties(base_reward: Decimal, 
                        completion_data: Dict[str, Any]) -> Decimal:
    """Apply penalties to reward based on completion behavior."""
    final_reward = base_reward
    
    # Speeding penalty (50% reduction)
    if completion_data.get('flagged_for_speeding'):
        final_reward *= Decimal('0.5')
    
    # Failed attention checks (10% per failed check)
    failed_checks = completion_data.get('failed_attention_checks', 0)
    if failed_checks > 0:
        penalty_rate = Decimal('0.10') * failed_checks
        final_reward *= (Decimal('1.00') - penalty_rate)
    
    # Ensure reward doesn't go negative
    return max(final_reward, Decimal('0.00'))


def format_currency_amount(amount: Decimal, currency_symbol: str = '$') -> str:
    """Format currency amount with proper formatting."""
    if amount is None:
        return f"{currency_symbol}0.00"
    
    # Ensure we have exactly 2 decimal places
    formatted_amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Add thousands separator
    amount_str = f"{formatted_amount:,.2f}"
    
    return f"{currency_symbol}{amount_str}"


def calculate_reward_pool_utilization(pool_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate reward pool utilization metrics."""
    total_budget = pool_data.get('total_budget', Decimal('0.00'))
    allocated_amount = pool_data.get('allocated_amount', Decimal('0.00'))
    paid_amount = pool_data.get('paid_amount', Decimal('0.00'))
    
    utilization_rate = 0.0
    if total_budget > 0:
        utilization_rate = float((allocated_amount / total_budget) * 100)
    
    remaining_budget = total_budget - allocated_amount
    available_budget = remaining_budget - paid_amount
    
    # Determine status based on utilization
    if utilization_rate >= 90:
        status = 'critical'
    elif utilization_rate >= 70:
        status = 'warning'
    elif utilization_rate >= 50:
        status = 'moderate'
    else:
        status = 'healthy'
    
    return {
        'utilization_rate': round(utilization_rate, 2),
        'remaining_budget': remaining_budget,
        'available_budget': available_budget,
        'status': status,
        'needs_refill': utilization_rate >= pool_data.get('refill_threshold', 20)
    }


# ══════════════════════════════════════════════════════════════════
# TASK MANAGEMENT HELPERS
# ══════════════════════════════════════════════════════════════════

def parse_cron_expression(cron_expr: str) -> Dict[str, Any]:
    """Parse cron expression into components."""
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Invalid cron expression: must have 5 parts")
    
    return {
        'minute': parts[0],
        'hour': parts[1],
        'day': parts[2],
        'month': parts[3],
        'day_of_week': parts[4]
    }


def calculate_next_run_time(cron_expr: str, 
                         timezone_str: str = 'UTC') -> Optional[datetime]:
    """Calculate next run time from cron expression."""
    try:
        from croniter import croniter
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        
        cron = croniter(cron_expr, now)
        next_run = cron.get_next(datetime)
        
        return next_run
    except ImportError:
        logger.warning("croniter not available, using simple calculation")
        return None
    except Exception as e:
        logger.error(f"Error calculating next run time: {e}")
        return None


def format_task_duration(seconds: int) -> str:
    """Format task duration in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"


def generate_task_lock_key(task_name: str, task_id: str = None) -> str:
    """Generate unique lock key for task."""
    if task_id:
        return f"task_lock:{task_name}:{task_id}"
    return f"task_lock:{task_name}"


def is_task_ready_to_run(task_data: Dict[str, Any]) -> bool:
    """Check if task is ready to run based on schedule and dependencies."""
    # Check status
    if task_data.get('status') != 'active':
        return False
    
    # Check next run time
    next_run = task_data.get('next_run')
    if next_run and next_run > timezone.now():
        return False
    
    # Check dependencies
    depends_on = task_data.get('depends_on', [])
    for dependency in depends_on:
        if dependency.get('status') != 'completed':
            return False
    
    return True


def calculate_task_success_rate(task_executions: List[Dict[str, Any]]) -> float:
    """Calculate success rate for a task."""
    if not task_executions:
        return 0.0
    
    successful_runs = len([e for e in task_executions if e.get('status') == 'success'])
    total_runs = len(task_executions)
    
    return round((successful_runs / total_runs) * 100, 2)


def get_task_priority_value(priority: str) -> int:
    """Convert priority string to numeric value for comparison."""
    priority_map = {
        'low': 1,
        'normal': 2,
        'high': 3,
        'critical': 4
    }
    return priority_map.get(priority.lower(), 2)


def format_task_status(status: str) -> str:
    """Format task status for display."""
    status_map = {
        'pending': 'Pending',
        'running': 'Running',
        'success': 'Success',
        'failure': 'Failed',
        'timeout': 'Timeout',
        'cancelled': 'Cancelled',
        'retry': 'Retry'
    }
    return status_map.get(status, status.title())
