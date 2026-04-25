# api/payment_gateways/utils/PhoneUtils.py
# Phone number validation and formatting for BD mobile banking

import re
from typing import Tuple


class PhoneUtils:
    """
    Phone number utilities for Bangladesh mobile banking.
    bKash, Nagad, Upay, AmarPay all require BD phone numbers.
    """

    BD_OPERATORS = {
        '017': 'Grameenphone (GP)',
        '013': 'Grameenphone (GP)',
        '018': 'Robi',
        '016': 'Airtel (Robi)',
        '019': 'Banglalink',
        '014': 'Banglalink',
        '015': 'Teletalk',
        '011': 'Teletalk',
    }

    BKASH_OPERATORS   = ['017', '013', '018', '016', '019', '014']
    NAGAD_OPERATORS   = ['017', '013', '018', '016', '019', '014', '015']
    UPAY_OPERATORS    = ['017', '013', '018', '016', '019', '014']

    @staticmethod
    def validate_bd(phone: str) -> Tuple[bool, str]:
        """
        Validate a Bangladesh phone number.

        Accepts:
            01712345678
            +8801712345678
            8801712345678

        Returns:
            (is_valid: bool, message: str)
        """
        clean = re.sub(r'[\s\-\(\)]', '', str(phone))

        # Remove country code
        if clean.startswith('+880'):
            clean = '0' + clean[4:]
        elif clean.startswith('880') and len(clean) == 13:
            clean = '0' + clean[3:]

        # Must be 11 digits starting with 01
        if not re.match(r'^01[3-9]\d{8}$', clean):
            return False, f'Invalid BD phone number: {phone}'

        return True, clean

    @staticmethod
    def normalize_bd(phone: str) -> str:
        """
        Normalize BD phone to 11-digit format (01XXXXXXXXX).
        Returns empty string if invalid.
        """
        valid, result = PhoneUtils.validate_bd(phone)
        return result if valid else ''

    @staticmethod
    def to_international(phone: str) -> str:
        """Convert BD phone to international format: +8801712345678"""
        normalized = PhoneUtils.normalize_bd(phone)
        if not normalized:
            return phone
        return '+880' + normalized[1:]

    @staticmethod
    def get_operator(phone: str) -> str:
        """Get mobile operator name from phone number."""
        normalized = PhoneUtils.normalize_bd(phone)
        if not normalized:
            return 'Unknown'
        prefix = normalized[:3]
        return PhoneUtils.BD_OPERATORS.get(prefix, 'Unknown')

    @staticmethod
    def is_bkash_eligible(phone: str) -> bool:
        """Check if phone number can receive bKash payments."""
        normalized = PhoneUtils.normalize_bd(phone)
        if not normalized:
            return False
        return normalized[:3] in PhoneUtils.BKASH_OPERATORS

    @staticmethod
    def is_nagad_eligible(phone: str) -> bool:
        """Check if phone number can receive Nagad payments."""
        normalized = PhoneUtils.normalize_bd(phone)
        if not normalized:
            return False
        return normalized[:3] in PhoneUtils.NAGAD_OPERATORS

    @staticmethod
    def mask(phone: str) -> str:
        """Mask phone for display: 01712345678 → 0171****678"""
        normalized = PhoneUtils.normalize_bd(phone)
        if not normalized or len(normalized) < 8:
            return phone
        return normalized[:4] + '****' + normalized[-3:]

    @staticmethod
    def validate_for_gateway(phone: str, gateway: str) -> Tuple[bool, str]:
        """
        Validate phone for specific gateway requirements.

        Returns:
            (is_valid: bool, reason: str)
        """
        valid, normalized = PhoneUtils.validate_bd(phone)
        if not valid:
            return False, 'Invalid phone number format'

        gateway = gateway.lower()
        if gateway == 'bkash' and not PhoneUtils.is_bkash_eligible(normalized):
            op = PhoneUtils.get_operator(normalized)
            return False, f'bKash does not support {op} numbers'

        if gateway == 'nagad' and not PhoneUtils.is_nagad_eligible(normalized):
            op = PhoneUtils.get_operator(normalized)
            return False, f'Nagad does not support {op} numbers'

        return True, normalized
