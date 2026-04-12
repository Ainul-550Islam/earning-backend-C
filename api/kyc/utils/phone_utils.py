# kyc/utils/phone_utils.py  ── WORLD #1
"""Bangladesh phone number utilities"""
import re


def normalize_bd_phone(phone: str) -> str:
    """Normalize to 11-digit format: 01XXXXXXXXX"""
    if not phone:
        return ''
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    if cleaned.startswith('880') and len(cleaned) == 13:
        return '0' + cleaned[3:]
    if cleaned.startswith('880') and len(cleaned) == 12:
        return '0' + cleaned[3:]
    if len(cleaned) == 10 and cleaned.startswith('1'):
        return '0' + cleaned
    return cleaned


def is_valid_bd_phone(phone: str) -> bool:
    normalized = normalize_bd_phone(phone)
    return bool(re.match(r'^01[3-9]\d{8}$', normalized))


def mask_phone(phone: str) -> str:
    """Mask phone for display: 0171****789"""
    if not phone or len(phone) < 8:
        return '****'
    return phone[:4] + '****' + phone[-3:]


def get_operator(phone: str) -> str:
    """Detect BD mobile operator from number."""
    normalized = normalize_bd_phone(phone)
    if not normalized or len(normalized) < 4:
        return 'unknown'
    prefix = normalized[:4]
    ops = {
        '0171': 'Grameenphone', '0170': 'Robi', '0172': 'Robi',
        '0174': 'Teletalk',    '0175': 'Teletalk',
        '0173': 'Banglalink',  '0179': 'Banglalink',
        '0176': 'Banglalink',
        '0161': 'Airtel/Robi', '0169': 'Airtel/Robi',
        '0185': 'Grameenphone','0188': 'Grameenphone',
        '0191': 'Grameenphone','0198': 'Grameenphone',
        '0193': 'Robi',
    }
    return ops.get(prefix, 'unknown')
