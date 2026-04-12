# services/currency/CurrencyConversionService.py
"""Complete currency conversion service"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CurrencyConversionService:
    """Full currency conversion with audit logging"""

    def convert_and_log(self, amount: Decimal, from_code: str, to_code: str,
                        user=None, ip_address: str = '', request_path: str = '') -> Dict:
        """Convert করে এবং audit log রাখে"""
        try:
            from .ExchangeRateService import ExchangeRateService
            rate_service = ExchangeRateService()
            result = rate_service.convert(amount, from_code, to_code)
            if not result:
                return {'success': False, 'error': f'Could not convert {from_code} to {to_code}'}
            # Audit log
            self._log_conversion(amount, from_code, to_code, result['rate'],
                                user=user, ip_address=ip_address, request_path=request_path)
            return {
                'success': True,
                'from_amount': float(amount),
                'to_amount': float(result['converted']),
                'from_currency': from_code,
                'to_currency': to_code,
                'rate': float(result['rate']),
            }
        except Exception as e:
            logger.error(f"Conversion service failed: {e}")
            return {'success': False, 'error': str(e)}

    def _log_conversion(self, amount, from_code, to_code, rate, user=None, ip_address='', request_path=''):
        try:
            from ..models.currency import CurrencyConversionLog
            from ..models.core import Currency
            CurrencyConversionLog.objects.create(
                from_currency=Currency.objects.filter(code=from_code).first(),
                to_currency=Currency.objects.filter(code=to_code).first(),
                amount=amount,
                converted_amount=amount * rate,
                rate_used=rate,
                user=user,
                ip_address=ip_address or None,
                request_path=request_path[:500],
            )
        except Exception as e:
            logger.error(f"Conversion log failed: {e}")
