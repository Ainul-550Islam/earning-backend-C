# utils.py — Utility functions used across the localization system
import re
import hashlib
import logging
from typing import Optional, Dict, List, Any
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


# ── Language utilities ────────────────────────────────────────────
def normalize_language_code(code: str) -> str:
    """Normalize: EN → en, en_US → en-US, zh-hans → zh-Hans"""
    if not code:
        return 'en'
    code = code.strip().replace('_', '-')
    parts = code.split('-')
    result = [parts[0].lower()]
    if len(parts) > 1:
        script_or_region = parts[1]
        if len(script_or_region) == 2:
            result.append(script_or_region.upper())
        elif len(script_or_region) == 4:
            result.append(script_or_region.capitalize())
        else:
            result.append(script_or_region)
    if len(parts) > 2:
        result.append(parts[2].upper())
    return '-'.join(result)


def get_language_from_accept_header(accept_lang: str, available_codes: List[str] = None) -> Optional[str]:
    """
    Accept-Language: bn-BD,bn;q=0.9,en;q=0.8
    → Returns best matching language code from available_codes
    """
    if not accept_lang:
        return None
    try:
        langs = []
        for part in accept_lang.split(','):
            parts = part.strip().split(';')
            lang = parts[0].strip()
            q = 1.0
            if len(parts) > 1:
                try:
                    q = float(parts[1].strip().replace('q=', ''))
                except ValueError:
                    q = 1.0
            langs.append((lang, q))
        langs.sort(key=lambda x: -x[1])
        for lang, _ in langs:
            # Exact match
            if available_codes and lang in available_codes:
                return lang
            # Base language match (bn-BD → bn)
            base = lang.split('-')[0].lower()
            if available_codes:
                if base in available_codes:
                    return base
            else:
                return base
        return langs[0][0].split('-')[0].lower() if langs else None
    except Exception as e:
        logger.error(f"Accept-Language parse error: {e}")
        return None


def is_rtl_language(language_code: str) -> bool:
    """Check if a language is RTL"""
    RTL = {'ar', 'he', 'fa', 'ur', 'ps', 'sd', 'ug', 'yi', 'ku', 'ckb', 'arc', 'az-Arab'}
    base = language_code.split('-')[0].lower()
    return base in RTL or language_code in RTL


def get_text_direction(language_code: str) -> str:
    return 'rtl' if is_rtl_language(language_code) else 'ltr'


# ── Text / Translation utilities ─────────────────────────────────
def hash_text(text: str) -> str:
    """SHA256 hash of normalized text — for TM lookups"""
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def count_words(text: str) -> int:
    """Word count across Latin, CJK, Arabic scripts"""
    if not text:
        return 0
    # CJK characters each count as a word
    cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
    # Latin/other words
    other_words = len(re.findall(r'\b\w+\b', re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)))
    return cjk_count + other_words


def extract_placeholders(text: str) -> List[str]:
    """Extract all placeholder patterns: {name}, %s, {{var}}, %(name)s"""
    patterns = [r'\{[^}]+\}', r'%\([^)]+\)[sd]', r'%[sdif]', r'{{[^}]+}}', r'<[a-z][^>]*>']
    result = []
    for p in patterns:
        result.extend(re.findall(p, text or ''))
    return result


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text cleanly at word boundary"""
    if not text or len(text) <= max_length:
        return text or ''
    truncated = text[:max_length - len(suffix)].rsplit(' ', 1)[0]
    return truncated + suffix


def clean_translation_key(key: str) -> str:
    """Normalize translation key: removes invalid chars, lowercases"""
    cleaned = re.sub(r'[^a-z0-9_.]', '_', key.lower().strip())
    cleaned = re.sub(r'_+', '_', cleaned).strip('_.')
    return cleaned


# ── Number / Currency utilities ───────────────────────────────────
def format_number_south_asian(amount: Decimal, decimal_places: int = 2) -> str:
    """Format: 110000 → 1,10,000 (South Asian grouping)"""
    try:
        integer_part = int(amount)
        decimal_part = amount - integer_part
        s = str(integer_part)
        if len(s) > 3:
            result = s[-3:]
            s = s[:-3]
            while len(s) > 2:
                result = s[-2:] + ',' + result
                s = s[:-2]
            if s:
                result = s + ',' + result
        else:
            result = s
        if decimal_places > 0:
            dec_str = f"{abs(decimal_part):.{decimal_places}f}"[1:]
            result += dec_str
        if amount < 0:
            result = '-' + result
        return result
    except Exception:
        return str(amount)


def safe_decimal(value: Any, default: Decimal = Decimal('0')) -> Decimal:
    """Safely convert any value to Decimal"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


# ── IP / GeoIP utilities ──────────────────────────────────────────
def get_client_ip(request) -> str:
    """Get real client IP from request (handles proxies)"""
    try:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    except Exception:
        return ''


def is_private_ip(ip: str) -> bool:
    """Check if IP is private/local"""
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def ip_to_int(ip: str) -> int:
    """Convert IPv4 to integer for range queries"""
    try:
        import socket, struct
        return struct.unpack("!L", socket.inet_aton(ip))[0]
    except Exception:
        return 0


# ── Cache utilities ───────────────────────────────────────────────
def build_cache_key(*parts, prefix: str = 'loc') -> str:
    """Build consistent cache key from parts"""
    clean_parts = [str(p).lower().replace(' ', '_') for p in parts if p]
    key = f"{prefix}:" + ":".join(clean_parts)
    if len(key) > 200:
        key = f"{prefix}:{hash_text(key)}"
    return key


def batch_cache_get(keys: List[str]) -> Dict:
    """Batch get from cache"""
    try:
        from django.core.cache import cache
        return cache.get_many(keys)
    except Exception as e:
        logger.error(f"Batch cache get error: {e}")
        return {}


def batch_cache_set(data: Dict, timeout: int = 3600) -> bool:
    """Batch set to cache"""
    try:
        from django.core.cache import cache
        cache.set_many(data, timeout)
        return True
    except Exception as e:
        logger.error(f"Batch cache set error: {e}")
        return False


# ── Date / Time utilities ─────────────────────────────────────────
def format_relative_time(dt, language_code: str = 'en') -> str:
    """'2 hours ago', '৩ ঘন্টা আগে', 'hace 2 horas'"""
    from django.utils import timezone
    try:
        now = timezone.now()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return _relative('just now', 'এইমাত্র', language_code)
        elif seconds < 3600:
            mins = int(seconds / 60)
            return _relative(f"{mins} minutes ago", f"{mins} মিনিট আগে", language_code)
        elif seconds < 86400:
            hrs = int(seconds / 3600)
            return _relative(f"{hrs} hours ago", f"{hrs} ঘন্টা আগে", language_code)
        elif seconds < 2592000:
            days = int(seconds / 86400)
            return _relative(f"{days} days ago", f"{days} দিন আগে", language_code)
        else:
            return dt.strftime('%Y-%m-%d')
    except Exception:
        return str(dt)


def _relative(en_text: str, bn_text: str, lang: str) -> str:
    """Return language-specific relative time string"""
    if lang == 'bn':
        return bn_text
    return en_text


# ── Response utilities ────────────────────────────────────────────
def success_response(data=None, message: str = None, status_code: int = 200) -> Dict:
    """Standard success response format"""
    from django.utils import timezone
    resp = {'success': True, 'timestamp': timezone.now().isoformat()}
    if message:
        resp['message'] = message
    if data is not None:
        resp['data'] = data
    return resp


def error_response(message: str, code: str = 'error', field: str = None, status_code: int = 400) -> Dict:
    """Standard error response format"""
    from django.utils import timezone
    resp = {'success': False, 'error': message, 'code': code, 'timestamp': timezone.now().isoformat()}
    if field:
        resp['field'] = field
    return resp


def paginate_list(items: List, page: int = 1, per_page: int = 20) -> Dict:
    """Simple list pagination (no DB queryset)"""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    pages = (total + per_page - 1) // per_page if per_page else 1
    return {
        'results': items[start:end],
        'pagination': {'total': total, 'page': page, 'pages': pages, 'per_page': per_page},
    }
