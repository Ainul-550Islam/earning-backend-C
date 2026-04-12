# services/currency/CurrencyFormatService.py
"""Currency formatting — locale-aware amount display"""
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CurrencyFormatService:
    """
    Currency formatting service।
    $1,234.56 | ৳1,23,456.78 | ¥1,234 | 1.234,56 €
    Uses locale-specific rules from NumberFormat model or built-in defaults.
    """

    # Built-in locale rules (fallback when DB format not available)
    LOCALE_FORMATS = {
        'en': {'decimal': '.', 'thousands': ',', 'grouping': 3, 'secondary': 0},
        'bn': {'decimal': '.', 'thousands': ',', 'grouping': 3, 'secondary': 2},  # South Asian: 1,00,000
        'hi': {'decimal': '.', 'thousands': ',', 'grouping': 3, 'secondary': 2},
        'ne': {'decimal': '.', 'thousands': ',', 'grouping': 3, 'secondary': 2},
        'de': {'decimal': ',', 'thousands': '.', 'grouping': 3, 'secondary': 0},
        'fr': {'decimal': ',', 'thousands': ' ', 'grouping': 3, 'secondary': 0},
        'es': {'decimal': ',', 'thousands': '.', 'grouping': 3, 'secondary': 0},
        'ar': {'decimal': '.', 'thousands': ',', 'grouping': 3, 'secondary': 0},
        'tr': {'decimal': ',', 'thousands': '.', 'grouping': 3, 'secondary': 0},
        'id': {'decimal': ',', 'thousands': '.', 'grouping': 3, 'secondary': 0},
    }

    def format(self, amount, currency_code: str, language_code: str = 'en') -> str:
        """
        Amount format করে — currency symbol + locale number format।
        format(1234.50, 'BDT', 'bn') → '৳1,23,456.78' (South Asian grouping)
        format(1234.56, 'EUR', 'de') → '1.234,56 €'
        """
        try:
            amount_dec = Decimal(str(amount))
            # Get currency info
            symbol, symbol_pos, decimals = self._get_currency_info(currency_code)
            # Format number
            formatted_number = self._format_number(amount_dec, language_code, decimals)
            # Combine symbol + number
            if symbol_pos == 'before':
                return f"{symbol}{formatted_number}"
            else:
                return f"{formatted_number} {symbol}"
        except Exception as e:
            logger.error(f"format failed: {e}")
            return f"{currency_code} {amount}"

    def parse(self, formatted: str, currency_code: str) -> Decimal:
        """
        Formatted string থেকে Decimal parse করে।
        '$1,234.56' → Decimal('1234.56')
        '৳1,23,456' → Decimal('123456')
        """
        try:
            # Remove currency symbols and spaces
            cleaned = re.sub(r'[^\d.,\-]', '', formatted.strip())
            # Detect decimal separator
            if ',' in cleaned and '.' in cleaned:
                # Both present: last one is decimal
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    # European format: 1.234,56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # Standard: 1,234.56
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Could be thousands or decimal separator
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # Decimal: 1234,56
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Thousands: 1,234
                    cleaned = cleaned.replace(',', '')
            return Decimal(cleaned)
        except Exception as e:
            logger.error(f"parse failed for '{formatted}': {e}")
            return Decimal('0')

    def _get_currency_info(self, currency_code: str):
        """Currency symbol, position, decimal places"""
        cache_key = f"curr_info_{currency_code}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from ...models.core import Currency
            curr = Currency.objects.filter(code=currency_code).first()
            if curr:
                result = (curr.symbol or currency_code, curr.symbol_position or 'before', curr.decimal_digits or 2)
                cache.set(cache_key, result, 86400)
                return result
        except Exception:
            pass
        # Built-in fallbacks
        defaults = {
            'USD': ('$', 'before', 2), 'EUR': ('€', 'after', 2), 'GBP': ('£', 'before', 2),
            'BDT': ('৳', 'before', 2), 'INR': ('₹', 'before', 2), 'PKR': ('₨', 'before', 2),
            'JPY': ('¥', 'before', 0), 'KRW': ('₩', 'before', 0), 'CNY': ('¥', 'before', 2),
            'SAR': ('﷼', 'after', 2), 'AED': ('د.إ', 'after', 2), 'TRY': ('₺', 'before', 2),
            'IDR': ('Rp', 'before', 0), 'MYR': ('RM', 'before', 2), 'NPR': ('₨', 'before', 2),
            'LKR': ('₨', 'before', 2), 'NGN': ('₦', 'before', 2), 'EGP': ('£', 'before', 2),
        }
        return defaults.get(currency_code, (currency_code, 'before', 2))

    def _format_number(self, amount: Decimal, language_code: str, decimal_places: int = 2) -> str:
        """Number locale-specific format করে"""
        lang = language_code.split('-')[0].lower()
        locale_fmt = self.LOCALE_FORMATS.get(lang, self.LOCALE_FORMATS['en'])
        decimal_sep = locale_fmt['decimal']
        thousands_sep = locale_fmt['thousands']
        grouping = locale_fmt['grouping']
        secondary = locale_fmt.get('secondary', 0)

        # Split integer and decimal parts
        if decimal_places > 0:
            quantized = amount.quantize(Decimal('0.' + '0' * decimal_places))
            parts = str(abs(quantized)).split('.')
            int_part = parts[0]
            dec_part = parts[1] if len(parts) > 1 else '0' * decimal_places
        else:
            int_part = str(int(abs(amount)))
            dec_part = ''

        # Apply grouping (South Asian: 1,23,45,678 or standard: 1,234,567)
        formatted_int = self._apply_grouping(int_part, grouping, secondary, thousands_sep)
        sign = '-' if amount < 0 else ''

        if decimal_places > 0:
            return f"{sign}{formatted_int}{decimal_sep}{dec_part}"
        return f"{sign}{formatted_int}"

    def _apply_grouping(self, int_str: str, grouping: int, secondary: int, sep: str) -> str:
        """Number grouping apply করে"""
        if not int_str:
            return '0'
        if len(int_str) <= grouping:
            return int_str
        # South Asian: last 3, then groups of 2
        if secondary and secondary > 0:
            result = int_str[-grouping:]
            remaining = int_str[:-grouping]
            while remaining:
                result = remaining[-secondary:] + sep + result
                remaining = remaining[:-secondary]
            return result
        # Standard: groups of `grouping`
        result = []
        while int_str:
            result.append(int_str[-grouping:])
            int_str = int_str[:-grouping]
        return sep.join(reversed(result))
