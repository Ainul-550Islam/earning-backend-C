# api/djoyalty/helpers.py
"""
Djoyalty Helpers -- COMPATIBILITY SHIM (AUDIT FIX v2)।

This file is now a pure re-export shim pointing to utils.py।

AUDIT FIX (v2): helpers.py and utils.py previously duplicated 8+ utility
functions with INCOMPATIBLE signatures (see utils.py for full analysis)।
All canonical implementations now live in utils.py।

This shim re-exports every function that was previously defined here,
preserving backward compatibility for all existing import sites:
  from .helpers import format_points        # still works
  from .helpers import generate_voucher_code  # still works, now canonical

Two functions have INTENTIONAL SIGNATURE DIFFERENCES from the old helpers.py
to maintain the helpers.py "flavour" that callers expect:

  generate_voucher_code: old helpers.py default was prefix='V', length=10।
    Re-exported here with prefix='V' baked in via a local wrapper so callers
    importing from helpers continue to get the 'V' prefix without changes।
    Callers importing from utils.py get prefix='' (bare code) -- correct for
    VoucherService.generate_voucher()।

  format_points: old helpers.py default was suffix=' pts'।
    Re-exported here with suffix=' pts' baked in via a local wrapper।
    Callers importing from utils.py get suffix='' (no suffix) -- correct for
    API responses।

All other functions are direct re-exports (no wrapper needed)।
"""
# ─── Direct re-exports from utils ─────────────────────────────────────────────
from .utils import (
    # Code generation
    generate_customer_code,
    generate_referral_code,
    generate_transaction_ref,
    generate_secure_token,
    generate_secure_token_hex,
    generate_otp,
    generate_gift_card_code,
    generate_loyalty_number,
    generate_reference_id,

    # Phone / email
    normalize_bd_phone,
    is_valid_bd_phone,
    mask_phone,
    mask_email,
    is_valid_email,
    is_valid_phone,

    # Currency / points
    points_to_bdt,
    bdt_to_points,
    format_currency,

    # Date / time
    days_since,
    days_until,
    is_birthday_today,
    get_quarter,
    is_expired,
    get_expiry_date,

    # Hashing / security
    make_hmac_signature,
    verify_hmac_signature,
    hash_sensitive,
    safe_decimal,

    # Tier
    get_tier_color,
    get_tier_icon,
    get_tier_for_points,
    get_tier_multiplier,
    get_next_tier,
    get_points_needed_for_next_tier,
    get_tier_progress_percent,

    # Pagination / misc
    paginate_queryset,
    chunk_list,
    flatten_dict,
    get_client_ip,
    get_device_type,
    build_absolute_url,
    truncate,
    normalize_code,
    build_cache_key,

    # Points calc
    calculate_points_to_earn,
    calculate_points_value,
)


# ─── Wrapper: generate_voucher_code (prefix='V' default) ──────────────────────
def generate_voucher_code(prefix: str = 'V', length: int = 10) -> str:
    """
    Generate a unique voucher code like VABCD1234EF।

    helpers.py-flavour wrapper: default prefix='V', length=10।
    Use utils.generate_voucher_code(prefix='', length=12) for bare codes।
    """
    from .utils import generate_voucher_code as _gvc
    return _gvc(length=length, prefix=prefix)


# ─── Wrapper: format_points (suffix=' pts' default) ───────────────────────────
def format_points(points, suffix: str = ' pts') -> str:
    """
    Format points for display: 1,234 pts।

    helpers.py-flavour wrapper: default suffix=' pts'。
    Use utils.format_points(points, decimals=0, suffix='') for bare numbers。
    """
    from .utils import format_points as _fp
    return _fp(points, decimals=0, suffix=suffix)
