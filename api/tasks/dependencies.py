"""
api/tasks/dependencies.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reusable request dependencies for DRF views and viewsets.
Analogous to FastAPI Depends() — extracts and validates
common request parameters in one place.
"""

import logging
from typing import Any, Dict, Optional, Tuple
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import ValidationError, AuthenticationFailed, PermissionDenied
from rest_framework.request import Request

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP from a DRF Request.
    Handles X-Forwarded-For, CF-Connecting-IP (Cloudflare), etc.
    """
    # Cloudflare
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip().split(',')[0].strip()
    # Standard proxy header
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.strip().split(',')[0].strip()
    # X-Real-IP (nginx)
    x_real = request.META.get('HTTP_X_REAL_IP')
    if x_real:
        return x_real.strip()
    return request.META.get('REMOTE_ADDR', '')


def get_user_agent(request: Request) -> str:
    """Extract User-Agent from request."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def get_device_type(request: Request) -> str:
    """
    Infer device type from User-Agent.
    Returns: 'mobile' | 'tablet' | 'desktop'
    """
    ua = get_user_agent(request).lower()
    if 'tablet' in ua or 'ipad' in ua:
        return 'tablet'
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        return 'mobile'
    return 'desktop'


def get_country_code(request: Request) -> str:
    """
    Extract country code from request.
    Priority: CF-IPCountry header → GeoIP lookup → settings default.
    """
    # Cloudflare country header
    cf_country = request.META.get('HTTP_CF_IPCOUNTRY')
    if cf_country and len(cf_country) == 2:
        return cf_country.upper()
    # Custom header set by nginx/proxy
    country = request.META.get('HTTP_X_COUNTRY_CODE')
    if country and len(country) == 2:
        return country.upper()
    # GeoIP fallback
    ip = get_client_ip(request)
    if ip:
        cache_key = f'geoip_{ip}'
        cached    = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.tasks.helpers import extract_country_from_ip
            detected = extract_country_from_ip(ip)
            cache.set(cache_key, detected, timeout=86400)
            return detected
        except Exception:
            pass
    return getattr(settings, 'DEFAULT_COUNTRY', 'US')


def get_request_context(request: Request) -> Dict[str, Any]:
    """
    Build a complete request context dict used for fraud checks,
    targeting, and event payloads.
    """
    user_id = getattr(request.user, 'pk', None)
    return {
        'user_id':      user_id,
        'ip_address':   get_client_ip(request),
        'user_agent':   get_user_agent(request),
        'device':       get_device_type(request),
        'country':      get_country_code(request),
        'fraud_score':  int(cache.get(f'fraud_score_{user_id}', 0)) if user_id else 0,
        'timestamp':    timezone.now().isoformat(),
        'path':         request.path,
        'method':       request.method,
    }


def get_pagination_params(request: Request, default_size: int = 20,
                           max_size: int = 100) -> Tuple[int, int]:
    """
    Extract and validate pagination parameters from request.
    Returns: (page_size, page_number)
    """
    try:
        page_size = min(int(request.query_params.get('page_size', default_size)), max_size)
        page_size = max(page_size, 1)
    except (ValueError, TypeError):
        page_size = default_size

    try:
        page = max(int(request.query_params.get('page', 1)), 1)
    except (ValueError, TypeError):
        page = 1

    return page_size, page


def get_date_range_params(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract date range parameters from request query params.
    Returns: (date_from, date_to) as ISO strings or None.
    """
    date_from = request.query_params.get('date_from') or request.query_params.get('from')
    date_to   = request.query_params.get('date_to') or request.query_params.get('to')
    return date_from, date_to


def get_ordering_params(request: Request, allowed_fields: list = None,
                         default: str = '-created_at') -> str:
    """
    Extract and validate ordering parameter.
    Returns a safe ordering string for ORM use.
    """
    ordering = request.query_params.get('ordering', default)
    if not allowed_fields:
        return ordering

    field = ordering.lstrip('-')
    if field not in allowed_fields:
        return default
    return ordering


# ══════════════════════════════════════════════════════════════════════════════
# AUTH DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════

def require_authenticated(request: Request) -> Any:
    """
    Raise AuthenticationFailed if user is not authenticated.
    Returns the user object.
    """
    if not request.user.is_authenticated:
        raise AuthenticationFailed('Authentication required.')
    return request.user


def require_staff(request: Request) -> Any:
    """
    Raise PermissionDenied if user is not staff.
    Returns the user object.
    """
    user = require_authenticated(request)
    if not user.is_staff:
        raise PermissionDenied('Staff access required.')
    return user


def require_not_suspended(request: Request) -> None:
    """Raise PermissionDenied if user account is suspended."""
    user_id = getattr(request.user, 'pk', None)
    if user_id and cache.get(f'user_suspended_{user_id}'):
        raise PermissionDenied('Your account has been suspended.')


def require_low_fraud_score(request: Request, threshold: int = 60) -> int:
    """
    Raise PermissionDenied if user's fraud score exceeds threshold.
    Returns current fraud score.
    """
    user_id = getattr(request.user, 'pk', None)
    score   = int(cache.get(f'fraud_score_{user_id}', 0)) if user_id else 0
    if score >= threshold:
        raise PermissionDenied('Account flagged for suspicious activity.')
    return score


def require_kyc(request: Request, min_tier: str = 'basic') -> str:
    """
    Raise PermissionDenied if user's KYC tier is below required.
    Returns the user's current KYC tier.
    """
    TIER_ORDER = {'none': 0, 'basic': 1, 'standard': 2, 'full': 3, 'edd': 4}
    user_id = getattr(request.user, 'pk', None)
    if not user_id:
        raise PermissionDenied('Authentication required.')

    current_tier    = cache.get(f'kyc_tier_{user_id}', 'none')
    required_level  = TIER_ORDER.get(min_tier, 1)
    current_level   = TIER_ORDER.get(current_tier, 0)

    if current_level < required_level:
        raise PermissionDenied(f'KYC verification required (minimum tier: {min_tier}).')
    return current_tier


def require_valid_ip(request: Request) -> str:
    """
    Raise PermissionDenied if client IP is in the blocklist.
    Returns the client IP.
    """
    import hashlib
    ip      = get_client_ip(request)
    ip_hash = hashlib.md5(ip.encode()).hexdigest()
    if cache.get(f'ip_blocked_{ip_hash}'):
        raise PermissionDenied('Access denied from this IP address.')
    return ip


# ══════════════════════════════════════════════════════════════════════════════
# PAYLOAD EXTRACTORS
# ══════════════════════════════════════════════════════════════════════════════

def extract_withdrawal_data(request: Request) -> Dict[str, Any]:
    """
    Extract and validate withdrawal request data.
    Returns validated dict ready for WalletService.
    """
    data   = request.data
    amount = data.get('amount')
    method = data.get('payment_method', 'default')
    wallet = data.get('wallet_address', '')

    if not amount:
        raise ValidationError({'amount': 'Amount is required.'})

    try:
        amount_dec = Decimal(str(amount))
    except Exception:
        raise ValidationError({'amount': 'Invalid amount format.'})

    if amount_dec <= Decimal('0'):
        raise ValidationError({'amount': 'Amount must be positive.'})

    from api.tasks.constants import MIN_PAYOUT
    min_payout = MIN_PAYOUT.get(method, MIN_PAYOUT['default'])
    if amount_dec < min_payout:
        raise ValidationError({
            'amount': f'Minimum withdrawal for {method} is ${min_payout}.'
        })

    return {
        'amount':         amount_dec,
        'payment_method': method,
        'wallet_address': wallet,
        'ip_address':     get_client_ip(request),
        'user_agent':     get_user_agent(request),
        'country':        get_country_code(request),
    }


def extract_task_completion_data(request: Request, task_id: str) -> Dict[str, Any]:
    """
    Extract task completion data from request.
    Validates required fields and builds submission dict.
    """
    data = request.data if hasattr(request, 'data') else {}
    return {
        'task_id':      task_id,
        'user_id':      getattr(request.user, 'pk', None),
        'ip_address':   get_client_ip(request),
        'user_agent':   get_user_agent(request),
        'device':       get_device_type(request),
        'country':      get_country_code(request),
        'proof':        data.get('proof', ''),
        'extra_data':   data.get('extra_data', {}),
        'submitted_at': timezone.now().isoformat(),
    }


def extract_postback_data(request: Request) -> Dict[str, Any]:
    """
    Extract and validate S2S postback data from request.
    Handles both GET query params and POST body.
    """
    params = dict(request.query_params)
    if request.method == 'POST':
        params.update(dict(request.data) if hasattr(request, 'data') else {})

    # Flatten single-value lists from QueryDict
    flat = {k: (v[0] if isinstance(v, list) and len(v) == 1 else v)
            for k, v in params.items()}

    required = ['click_id', 'offer_id']
    missing  = [f for f in required if not flat.get(f)]
    if missing:
        raise ValidationError({f: 'Required' for f in missing})

    return {
        'click_id':       flat.get('click_id', ''),
        'offer_id':       flat.get('offer_id', ''),
        'transaction_id': flat.get('transaction_id', flat.get('txn_id', '')),
        'payout':         flat.get('payout', flat.get('amount', '0')),
        'status':         flat.get('status', 'approved'),
        'pub_id':         flat.get('pub_id', flat.get('publisher_id', '')),
        'ip':             flat.get('ip', get_client_ip(request)),
        'country':        flat.get('country', get_country_code(request)),
        'device':         flat.get('device', ''),
        'user_agent':     flat.get('user_agent', get_user_agent(request)),
        'raw_params':     flat,
    }


def extract_crypto_withdrawal_data(request: Request) -> Dict[str, Any]:
    """Extract and validate crypto withdrawal request data."""
    data        = request.data
    amount      = data.get('amount')
    crypto_type = data.get('crypto_type', 'usdt_trc20')
    wallet_addr = data.get('wallet_address', '')
    network     = data.get('network', 'trc20')

    if not amount:
        raise ValidationError({'amount': 'Amount is required.'})
    if not wallet_addr:
        raise ValidationError({'wallet_address': 'Wallet address is required.'})

    from api.tasks.helpers import validate_crypto_address
    is_valid, error_msg = validate_crypto_address(wallet_addr, crypto_type)
    if not is_valid:
        raise ValidationError({'wallet_address': error_msg})

    try:
        amount_dec = Decimal(str(amount))
    except Exception:
        raise ValidationError({'amount': 'Invalid amount format.'})

    from api.tasks.constants import MIN_PAYOUT
    min_payout = MIN_PAYOUT.get(crypto_type, Decimal('25'))
    if amount_dec < min_payout:
        raise ValidationError({
            'amount': f'Minimum {crypto_type.upper()} withdrawal is ${min_payout}.'
        })

    return {
        'amount_usd':    amount_dec,
        'crypto_type':   crypto_type,
        'wallet_address': wallet_addr,
        'network':       network,
        'user_id':       getattr(request.user, 'pk', None),
        'ip_address':    get_client_ip(request),
    }


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT HELPER
# ══════════════════════════════════════════════════════════════════════════════

def check_rate_limit(request: Request, scope: str, limit: int,
                      window: int = 3600) -> None:
    """
    Check and increment rate limit counter. Raises PermissionDenied if exceeded.
    """
    user_id = getattr(request.user, 'pk', None)
    ip      = get_client_ip(request)
    key     = f'rl_{scope}_{user_id or ip}'
    count   = cache.get(key, 0)

    if count >= limit:
        raise PermissionDenied(
            f'Rate limit exceeded for {scope}. Try again later.'
        )
    cache.set(key, count + 1, timeout=window)


__all__ = [
    # Request extractors
    'get_client_ip', 'get_user_agent', 'get_device_type', 'get_country_code',
    'get_request_context', 'get_pagination_params', 'get_date_range_params',
    'get_ordering_params',
    # Auth
    'require_authenticated', 'require_staff', 'require_not_suspended',
    'require_low_fraud_score', 'require_kyc', 'require_valid_ip',
    # Payload
    'extract_withdrawal_data', 'extract_task_completion_data',
    'extract_postback_data', 'extract_crypto_withdrawal_data',
    # Rate limit
    'check_rate_limit',
]
