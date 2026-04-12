# services/currency/EarningDisplayService.py
"""CPAlead earning amount display service — locale-aware format"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict
from django.core.cache import cache
logger = logging.getLogger(__name__)


class EarningDisplayService:
    """
    CPAlead earning amounts locale-aware format করার service।
    $10.50 → ৳1,155.00 (Bangladesh user), ₹873.90 (India user)
    """

    def format_earning(
        self,
        amount,
        user=None,
        language_code: str = 'en',
        currency_code: str = None,
        show_original: bool = False,
    ) -> Dict:
        """
        User-এর locale অনুযায়ী earning format করে।
        Returns dict with formatted amount + original USD amount.
        """
        try:
            amount_dec = Decimal(str(amount))

            # Determine target currency
            target_currency = currency_code
            if not target_currency and user:
                target_currency = self._get_user_currency(user)
            if not target_currency:
                target_currency = 'USD'

            # Base currency is USD (CPAlead standard)
            base_currency = 'USD'

            # Convert if needed
            converted_amount = amount_dec
            exchange_rate = Decimal('1')
            if target_currency != base_currency:
                try:
                    from .ExchangeRateService import ExchangeRateService
                    rate = ExchangeRateService().get_rate(base_currency, target_currency)
                    if rate:
                        converted_amount = amount_dec * rate
                        exchange_rate = rate
                except Exception as e:
                    logger.debug(f"Rate lookup failed: {e}")

            # Format with locale rules
            try:
                from .CurrencyFormatService import CurrencyFormatService
                formatted = CurrencyFormatService().format(
                    converted_amount, target_currency, language_code
                )
            except Exception:
                # Fallback: basic formatting
                from ..models.core import Currency
                curr = Currency.objects.filter(code=target_currency).first()
                if curr:
                    formatted = curr.format_amount(converted_amount)
                else:
                    formatted = f"{target_currency} {converted_amount:.2f}"

            result = {
                'formatted': formatted,
                'amount': float(converted_amount),
                'currency': target_currency,
                'original_usd': float(amount_dec),
                'exchange_rate': float(exchange_rate),
            }

            if show_original and target_currency != 'USD':
                try:
                    from ..models.core import Currency
                    usd = Currency.objects.filter(code='USD').first()
                    result['original_formatted'] = usd.format_amount(amount_dec) if usd else f"${amount_dec:.2f}"
                except Exception:
                    result['original_formatted'] = f"${amount_dec:.2f}"

            return result

        except (InvalidOperation, Exception) as e:
            logger.error(f"format_earning failed: {e}")
            return {
                'formatted': f"${amount}",
                'amount': float(amount) if amount else 0,
                'currency': 'USD',
                'original_usd': float(amount) if amount else 0,
            }

    def format_earning_table(self, earnings: list, user=None, language_code: str = 'en') -> list:
        """
        Earning list-এর সব amounts format করে।
        Used in earning history table.
        """
        currency = self._get_user_currency(user) if user else 'USD'
        result = []
        for earning in earnings:
            amount = earning.get('amount') or earning.get('earning') or 0
            formatted = self.format_earning(amount, language_code=language_code, currency_code=currency)
            result.append({**earning, 'formatted': formatted['formatted'], 'currency': currency})
        return result

    def _get_user_currency(self, user) -> str:
        """User-এর preferred currency code"""
        try:
            cache_key = f"user_currency_{user.pk}"
            cached = cache.get(cache_key)
            if cached:
                return cached
            from ..models.core import UserLanguagePreference
            pref = UserLanguagePreference.objects.filter(
                user=user, preferred_currency__isnull=False
            ).select_related('preferred_currency').first()
            if pref and pref.preferred_currency:
                code = pref.preferred_currency.code
                cache.set(cache_key, code, 3600)
                return code
        except Exception:
            pass
        return 'USD'

    def get_exchange_rate_display(self, from_currency: str, to_currency: str) -> str:
        """Display string for exchange rate: "1 USD = 110.50 BDT" """
        try:
            from .ExchangeRateService import ExchangeRateService
            rate = ExchangeRateService().get_rate(from_currency, to_currency)
            if rate:
                return f"1 {from_currency} = {rate:.2f} {to_currency}"
        except Exception:
            pass
        return f"1 {from_currency} = ? {to_currency}"
