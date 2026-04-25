# api/payment_gateways/validators.py
from decimal import Decimal
from rest_framework.exceptions import ValidationError

def validate_amount(value, min_val=Decimal('1'), max_val=Decimal('9999999')):
    value = Decimal(str(value))
    if value < min_val:
        raise ValidationError(f'Minimum amount is {min_val}')
    if value > max_val:
        raise ValidationError(f'Maximum amount is {max_val}')
    return value

def validate_gateway(value: str) -> str:
    from api.payment_gateways.choices import ALL_GATEWAYS
    if value.lower() not in ALL_GATEWAYS:
        raise ValidationError(f'Unsupported gateway: {value}')
    return value.lower()

def validate_currency(value: str) -> str:
    allowed = {'BDT','USD','EUR','GBP','AUD','CAD','SGD','JPY','BTC','ETH','USDT'}
    if value.upper() not in allowed:
        raise ValidationError(f'Unsupported currency: {value}')
    return value.upper()

def validate_phone(value: str) -> str:
    import re
    bd   = r'^(\+880|880|0)[0-9]{10}$'
    intl = r'^\+?[1-9][0-9]{7,14}$'
    clean = value.replace(' ', '').replace('-', '')
    if re.match(bd, clean) or re.match(intl, clean):
        return clean
    raise ValidationError(f'Invalid phone number: {value}')
