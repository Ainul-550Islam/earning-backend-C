# api/offer_inventory/utils.py
import hashlib
import secrets
import logging
import requests
from typing import Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Real client IP — proxy header সহ।"""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def get_client_meta(request) -> dict:
    """Request থেকে সব client meta extract করো।"""
    from user_agents import parse as ua_parse
    ua_str = request.META.get('HTTP_USER_AGENT', '')
    try:
        ua = ua_parse(ua_str)
        device  = 'mobile' if ua.is_mobile else ('tablet' if ua.is_tablet else 'desktop')
        os_name = ua.os.family
        browser = ua.browser.family
    except Exception:
        device = os_name = browser = 'unknown'

    ip = get_client_ip(request)
    country = get_country_from_ip(ip)

    return {
        'ip_address'  : ip,
        'user_agent'  : ua_str,
        'country_code': country,
        'device_type' : device,
        'os'          : os_name,
        'browser'     : browser,
        'referrer'    : request.META.get('HTTP_REFERER', ''),
        's1'          : request.query_params.get('s1', '') if hasattr(request, 'query_params') else '',
        's2'          : request.query_params.get('s2', '') if hasattr(request, 'query_params') else '',
    }


def get_country_from_ip(ip: str) -> str:
    """IP → country code। Cache করা।"""
    if not ip or ip in ('127.0.0.1', 'localhost'):
        return 'BD'
    cache_key = f'geo_ip:{ip}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    # DB check first
    try:
        from .models import GeoData
        geo = GeoData.objects.get(ip_address=ip)
        cache.set(cache_key, geo.country_code, 3600)
        return geo.country_code
    except Exception:
        pass

    # External API fallback
    try:
        resp = requests.get(f'https://ipapi.co/{ip}/country/', timeout=3)
        if resp.status_code == 200:
            country = resp.text.strip()[:2]
            cache.set(cache_key, country, 3600)
            return country
    except Exception:
        pass

    return ''


def generate_click_token() -> str:
    return secrets.token_hex(32)


def generate_reference_id(prefix: str = 'REF') -> str:
    import uuid
    return f'{prefix}-{str(uuid.uuid4())[:8].upper()}'


def mask_account_number(account: str) -> str:
    if len(account) <= 4:
        return '****'
    return '***' + account[-4:]


def compute_fingerprint(*args) -> str:
    raw = ':'.join(str(a) for a in args)
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_decimal(value, default='0') -> 'Decimal':
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def paginate_queryset(qs, page: int, page_size: int) -> tuple:
    """Simple pagination util। Returns (items, total_count)।"""
    total = qs.count()
    start = (page - 1) * page_size
    items = list(qs[start:start + page_size])
    return items, total


def send_webhook(webhook_url: str, event: str, data: dict, secret: str = '') -> bool:
    """Outbound webhook delivery।"""
    import json
    import hmac as _hmac
    payload = json.dumps({'event': event, 'data': data, 'timestamp': str(timezone.now())})
    headers = {'Content-Type': 'application/json'}
    if secret:
        sig = _hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        headers['X-Signature'] = sig
    try:
        resp = requests.post(webhook_url, data=payload, headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f'Webhook delivery failed: {e}')
        return False


def format_currency(amount, currency: str = 'BDT') -> str:
    symbols = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£'}
    sym = symbols.get(currency, currency)
    return f'{sym}{amount:,.2f}'
