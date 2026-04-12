# utils_module.py — standalone utility functions (no circular imports)
"""
Module-level utils that can be imported by middleware without circular deps.
These functions have no model imports.
"""
import re
import hashlib
from typing import Optional, List


RTL_LANGUAGES = frozenset({
    'ar', 'he', 'fa', 'ur', 'ps', 'sd', 'ug', 'yi', 'ku', 'ckb', 'arc',
    'az-arab', 'fa-af', 'ks', 'mzn', 'pnb', 'skr',
})


def is_rtl_language(language_code: str) -> bool:
    """Check if a language is RTL"""
    if not language_code:
        return False
    base = language_code.lower().split('-')[0].split('_')[0]
    return base in RTL_LANGUAGES or language_code.lower() in RTL_LANGUAGES


def get_text_direction(language_code: str) -> str:
    """Return 'rtl' or 'ltr'"""
    return 'rtl' if is_rtl_language(language_code) else 'ltr'


def get_language_from_accept_header(accept_lang: str, available_codes: List[str] = None) -> Optional[str]:
    """
    Parse Accept-Language: bn-BD,bn;q=0.9,en;q=0.8
    Returns best matching language code from available_codes.
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
            if available_codes:
                # Exact match
                if lang in available_codes:
                    return lang
                # Base language match: bn-BD → bn
                base = lang.split('-')[0].lower()
                if base in available_codes:
                    return base
            else:
                return lang.split('-')[0].lower()

        return langs[0][0].split('-')[0].lower() if langs else None
    except Exception:
        return None


def normalize_language_code(code: str) -> str:
    """en_US → en-US, EN → en, zh-hans → zh-Hans"""
    if not code:
        return 'en'
    code = code.strip().replace('_', '-')
    parts = code.split('-')
    result = [parts[0].lower()]
    if len(parts) > 1:
        p = parts[1]
        if len(p) == 2:
            result.append(p.upper())
        elif len(p) == 4:
            result.append(p.capitalize())
        else:
            result.append(p)
    if len(parts) > 2:
        result.append(parts[2].upper())
    return '-'.join(result)


def hash_text(text: str) -> str:
    """SHA256 hash of normalized text"""
    normalized = ' '.join(text.lower().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def is_private_ip(ip: str) -> bool:
    """Check if IP is private/local"""
    if not ip:
        return True
    private = ('127.', '10.', '192.168.', '172.16.', '172.17.', '172.18.',
               '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
               '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
               '172.29.', '172.30.', '172.31.', '::1', 'localhost', 'fc00:', 'fd')
    return any(ip.startswith(p) for p in private)


def get_client_ip(request) -> str:
    """Get real client IP from request"""
    try:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    except Exception:
        return ''


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate at word boundary"""
    if not text or len(text) <= max_length:
        return text or ''
    truncated = text[:max_length - len(suffix)].rsplit(' ', 1)[0]
    return truncated + suffix


def count_words(text: str) -> int:
    """Word count across scripts"""
    if not text:
        return 0
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))
    other = len(re.findall(r'\b\w+\b', re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)))
    return cjk + other
