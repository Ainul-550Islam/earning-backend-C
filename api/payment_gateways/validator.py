# api/payment_gateways/validator.py
# Full payment validator — all validation logic in one place
# "Do not summarize or skip any logic. Provide the full code."

from decimal import Decimal, InvalidOperation
from typing import Any, Tuple, List
import re
import logging

logger = logging.getLogger(__name__)

# ── Supported values ───────────────────────────────────────────────────────────
SUPPORTED_GATEWAYS = [
    'bkash','nagad','sslcommerz','amarpay','upay','shurjopay',
    'stripe','paypal','payoneer','wire','ach','crypto',
]

SUPPORTED_CURRENCIES = {
    'BDT','USD','EUR','GBP','AUD','CAD','SGD','JPY','INR',
    'PKR','MYR','THB','PHP','VND','USDT','USDC','BTC','ETH','LTC',
}

BD_PHONE_PATTERN   = re.compile(r'^01[3-9]\d{8}$')
EMAIL_PATTERN      = re.compile(r'^[\w\.\+\-]+@[\w\-]+\.[\w\.]{2,}$')
REF_ID_PATTERN     = re.compile(r'^[\w\-\.]+$')
CRYPTO_ADDR_PATTERN= re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^0x[0-9a-fA-F]{40}$|^T[A-Za-z1-9]{33}$')

GATEWAY_LIMITS = {
    'bkash':      {'min': Decimal('10'),   'max': Decimal('50000')},
    'nagad':      {'min': Decimal('10'),   'max': Decimal('50000')},
    'sslcommerz': {'min': Decimal('10'),   'max': Decimal('500000')},
    'amarpay':    {'min': Decimal('10'),   'max': Decimal('50000')},
    'upay':       {'min': Decimal('10'),   'max': Decimal('50000')},
    'shurjopay':  {'min': Decimal('10'),   'max': Decimal('50000')},
    'stripe':     {'min': Decimal('0.50'), 'max': Decimal('999999')},
    'paypal':     {'min': Decimal('1.00'), 'max': Decimal('999999')},
    'payoneer':   {'min': Decimal('50'),   'max': Decimal('999999')},
    'wire':       {'min': Decimal('100'),  'max': Decimal('9999999')},
    'ach':        {'min': Decimal('1'),    'max': Decimal('999999')},
    'crypto':     {'min': Decimal('10'),   'max': Decimal('9999999')},
}


def validate_amount(value: Any, min_val: Decimal = Decimal('0.01'),
                    max_val: Decimal = Decimal('9999999')) -> Decimal:
    """
    Validate and return a Decimal amount.

    Args:
        value:   Input amount (str, int, float, Decimal)
        min_val: Minimum allowed value (default: 0.01)
        max_val: Maximum allowed value (default: 9,999,999)

    Returns:
        Decimal: Validated amount

    Raises:
        ValueError: If amount is invalid, below min, or above max

    Example:
        amount = validate_amount('500', min_val=Decimal('10'))  # → Decimal('500')
        amount = validate_amount(-1)  # → raises ValueError
    """
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as e:
        raise ValueError(f'Invalid amount format: {value!r}. Must be a number.')

    if amount <= 0:
        raise ValueError(f'Amount must be positive, got {amount}')
    if amount < min_val:
        raise ValueError(f'Amount {amount} is below minimum {min_val}')
    if amount > max_val:
        raise ValueError(f'Amount {amount} exceeds maximum {max_val}')

    return amount


def validate_gateway(value: str) -> str:
    """
    Validate gateway name and return normalized lowercase string.

    Args:
        value: Gateway name (case-insensitive)

    Returns:
        str: Normalized lowercase gateway name

    Raises:
        ValueError: If gateway is not supported

    Example:
        validate_gateway('BKash')     # → 'bkash'
        validate_gateway('stripe')    # → 'stripe'
        validate_gateway('unknown')   # → raises ValueError
    """
    if not value:
        raise ValueError('Gateway name cannot be empty')

    normalized = str(value).lower().strip()
    if normalized not in SUPPORTED_GATEWAYS:
        raise ValueError(
            f'Unsupported gateway: {value!r}. '
            f'Supported: {", ".join(SUPPORTED_GATEWAYS)}'
        )
    return normalized


def validate_currency(value: str) -> str:
    """
    Validate currency code and return normalized uppercase string.

    Args:
        value: ISO 4217 currency code or crypto symbol

    Returns:
        str: Normalized uppercase currency code

    Raises:
        ValueError: If currency is not supported

    Example:
        validate_currency('usd')  # → 'USD'
        validate_currency('BDT')  # → 'BDT'
        validate_currency('XYZ')  # → raises ValueError
    """
    if not value:
        raise ValueError('Currency code cannot be empty')

    normalized = str(value).upper().strip()
    if normalized not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f'Unsupported currency: {value!r}. '
            f'Supported: {", ".join(sorted(SUPPORTED_CURRENCIES))}'
        )
    return normalized


def validate_phone(value: str, country: str = 'BD') -> str:
    """
    Validate phone number, normalize to local format.

    For BD (Bangladesh):
        Accepts: 01712345678, +8801712345678, 8801712345678
        Returns: 01712345678

    For other countries:
        Validates international format: +[country_code][number]

    Args:
        value:   Phone number string
        country: ISO country code (default: 'BD')

    Returns:
        str: Normalized phone number

    Raises:
        ValueError: If phone format is invalid
    """
    if not value:
        raise ValueError('Phone number cannot be empty')

    clean = re.sub(r'[\s\-\(\)\.]', '', str(value))

    if country == 'BD':
        # Normalize BD phone
        if clean.startswith('+880'):
            clean = '0' + clean[4:]
        elif clean.startswith('880') and len(clean) == 13:
            clean = '0' + clean[3:]
        elif clean.startswith('880') and len(clean) == 12:
            clean = '0' + clean[3:]

        if not BD_PHONE_PATTERN.match(clean):
            raise ValueError(
                f'Invalid Bangladesh phone: {value!r}. '
                f'Must be 11 digits starting with 01[3-9] '
                f'(e.g. 01712345678, +8801712345678)'
            )
        return clean
    else:
        # International format
        if not clean.startswith('+'):
            raise ValueError(f'International phone must start with +: {value!r}')
        if not re.match(r'^\+[1-9]\d{7,14}$', clean):
            raise ValueError(f'Invalid international phone: {value!r}')
        return clean


def validate_email(value: str) -> str:
    """
    Validate email address.

    Returns:
        str: Normalized lowercase email

    Raises:
        ValueError: If email format is invalid
    """
    if not value:
        raise ValueError('Email cannot be empty')

    normalized = str(value).strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise ValueError(f'Invalid email address: {value!r}')
    if len(normalized) > 254:
        raise ValueError('Email address too long (max 254 characters)')
    return normalized


def validate_reference_id(value: str, max_length: int = 200) -> str:
    """
    Validate a payment reference ID.

    Rules:
        - Not empty
        - Only alphanumeric, hyphens, underscores, dots
        - Max 200 characters

    Returns:
        str: Validated reference ID

    Raises:
        ValueError: If reference ID is invalid
    """
    if not value:
        raise ValueError('Reference ID cannot be empty')

    ref = str(value).strip()
    if len(ref) > max_length:
        raise ValueError(f'Reference ID too long: {len(ref)} chars (max {max_length})')
    if not REF_ID_PATTERN.match(ref):
        raise ValueError(
            f'Invalid reference ID {ref!r}. '
            f'Only alphanumeric characters, hyphens, underscores, dots allowed.'
        )
    return ref


def validate_account_number(value: str, gateway: str) -> str:
    """
    Validate account number for a specific gateway.

    Each gateway has its own account number format:
        bkash, nagad, upay, amarpay, shurjopay → BD phone number (01XXXXXXXXX)
        stripe     → card number or Stripe customer ID (cus_...)
        paypal     → email address
        payoneer   → email or Payoneer account ID
        wire, ach  → bank account number (alphanumeric)
        crypto     → blockchain wallet address (BTC/ETH/USDT)

    Returns:
        str: Validated account number

    Raises:
        ValueError: If account number format is invalid for the gateway
    """
    if not value:
        raise ValueError(f'Account number cannot be empty for gateway {gateway}')

    value   = str(value).strip()
    gateway = gateway.lower()

    # BD mobile banking — requires BD phone number
    BD_MOBILE_GATEWAYS = {'bkash', 'nagad', 'upay', 'amarpay', 'shurjopay'}
    if gateway in BD_MOBILE_GATEWAYS:
        return validate_phone(value, 'BD')

    # PayPal — requires email
    if gateway == 'paypal':
        return validate_email(value)

    # Payoneer — email or numeric ID
    if gateway == 'payoneer':
        if '@' in value:
            return validate_email(value)
        if not re.match(r'^\d{8,12}$', value):
            raise ValueError(f'Payoneer account must be email or 8-12 digit ID, got: {value!r}')
        return value

    # Stripe — Stripe customer ID or bank account token
    if gateway == 'stripe':
        if value.startswith('cus_') or value.startswith('ba_') or value.startswith('tok_'):
            return value
        if re.match(r'^\d{16}$', value.replace(' ', '')):
            return value.replace(' ', '')
        # Allow any alphanumeric Stripe ID
        if re.match(r'^[a-zA-Z0-9_]{5,100}$', value):
            return value
        raise ValueError(f'Invalid Stripe account/token: {value!r}')

    # Crypto — validate blockchain address
    if gateway == 'crypto':
        clean = value.strip()
        # BTC mainnet (starts with 1 or 3, 26-34 chars)
        if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', clean):
            return clean
        # ETH/ERC-20 (0x + 40 hex chars)
        if re.match(r'^0x[0-9a-fA-F]{40}$', clean):
            return clean
        # USDT TRC-20 (T + 33 base58 chars)
        if re.match(r'^T[A-Za-z1-9]{33}$', clean):
            return clean
        # Bitcoin SegWit (bc1...)
        if re.match(r'^bc1[a-zA-HJ-NP-Z0-9]{25,39}$', clean):
            return clean
        raise ValueError(
            f'Invalid crypto wallet address: {value!r}. '
            f'Supports BTC (1.../3.../bc1...), ETH (0x...), USDT TRC-20 (T...)'
        )

    # Wire transfer / ACH — bank account number
    if gateway in {'wire', 'ach', 'sslcommerz'}:
        if not re.match(r'^[a-zA-Z0-9\-\s]{4,50}$', value):
            raise ValueError(f'Invalid bank account number: {value!r}')
        return value.strip()

    # Default: allow any reasonable string
    if len(value) < 3:
        raise ValueError(f'Account number too short for gateway {gateway}')
    if len(value) > 200:
        raise ValueError(f'Account number too long for gateway {gateway}')
    return value


def validate_gateway_amount(amount: Any, gateway: str,
                              currency: str = 'BDT') -> Decimal:
    """
    Validate amount specifically for a gateway's min/max limits.

    Combines validate_amount() with gateway-specific limits.

    Returns:
        Decimal: Validated amount

    Raises:
        ValueError: If amount is outside gateway's allowed range
    """
    limits = GATEWAY_LIMITS.get(gateway.lower(), {
        'min': Decimal('1'), 'max': Decimal('9999999')
    })
    return validate_amount(amount, min_val=limits['min'], max_val=limits['max'])


def validate_deposit_data(data: dict) -> Tuple[bool, List[str], dict]:
    """
    Validate all fields for a deposit request.

    Args:
        data: dict with keys: gateway, amount, currency, [account_number]

    Returns:
        (is_valid: bool, errors: list[str], cleaned_data: dict)

    Example:
        is_valid, errors, clean = validate_deposit_data({
            'gateway':  'bkash',
            'amount':   '500',
            'currency': 'BDT',
        })
    """
    errors  = []
    cleaned = {}

    # Gateway
    try:
        cleaned['gateway'] = validate_gateway(data.get('gateway', ''))
    except ValueError as e:
        errors.append(str(e))

    # Amount
    gateway = cleaned.get('gateway', data.get('gateway', ''))
    try:
        cleaned['amount'] = validate_gateway_amount(
            data.get('amount', 0), gateway
        )
    except ValueError as e:
        errors.append(str(e))

    # Currency
    try:
        cleaned['currency'] = validate_currency(data.get('currency', 'BDT'))
    except ValueError as e:
        errors.append(str(e))

    # Account number (optional for deposits, required for withdrawals)
    if 'account_number' in data and data['account_number']:
        try:
            cleaned['account_number'] = validate_account_number(
                data['account_number'], gateway
            )
        except ValueError as e:
            errors.append(str(e))

    return len(errors) == 0, errors, cleaned


def validate_withdrawal_data(data: dict) -> Tuple[bool, List[str], dict]:
    """
    Validate all fields for a withdrawal/payout request.

    Args:
        data: dict with keys: gateway/payout_method, amount, currency,
              account_number, account_name

    Returns:
        (is_valid: bool, errors: list[str], cleaned_data: dict)
    """
    errors  = []
    cleaned = {}

    # Gateway/method
    method = data.get('payout_method') or data.get('gateway', '')
    try:
        cleaned['payout_method'] = validate_gateway(method)
    except ValueError as e:
        errors.append(str(e))

    # Amount
    gateway = cleaned.get('payout_method', method)
    try:
        cleaned['amount'] = validate_gateway_amount(
            data.get('amount', 0), gateway
        )
    except ValueError as e:
        errors.append(str(e))

    # Currency
    try:
        cleaned['currency'] = validate_currency(data.get('currency', 'BDT'))
    except ValueError as e:
        errors.append(str(e))

    # Account number (required for withdrawals)
    acct = data.get('account_number', '')
    if not acct:
        errors.append('account_number is required for withdrawals')
    else:
        try:
            cleaned['account_number'] = validate_account_number(acct, gateway)
        except ValueError as e:
            errors.append(str(e))

    # Account name (optional)
    if data.get('account_name'):
        name = str(data['account_name']).strip()
        if len(name) < 2:
            errors.append('account_name must be at least 2 characters')
        elif len(name) > 200:
            errors.append('account_name too long (max 200 characters)')
        else:
            cleaned['account_name'] = name

    return len(errors) == 0, errors, cleaned


# ── Convenience aliases ────────────────────────────────────────────────────────
# For: from api.payment_gateways.validator import PaymentValidator
from api.payment_gateways.services.PaymentValidator import PaymentValidator

__all__ = [
    'PaymentValidator',
    'validate_amount',
    'validate_gateway',
    'validate_currency',
    'validate_phone',
    'validate_email',
    'validate_reference_id',
    'validate_account_number',
    'validate_gateway_amount',
    'validate_deposit_data',
    'validate_withdrawal_data',
    'SUPPORTED_GATEWAYS',
    'SUPPORTED_CURRENCIES',
    'GATEWAY_LIMITS',
]
