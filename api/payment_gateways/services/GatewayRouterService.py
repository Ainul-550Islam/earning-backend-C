# api/payment_gateways/services/GatewayRouterService.py
# Auto-select best gateway based on amount, country, success rate

from decimal import Decimal
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class GatewayRouterService:
    """
    Intelligent gateway routing.

    Rules (priority order):
        1. User's preferred gateway (if set)
        2. Country-based routing (BD → bKash/Nagad, US → ACH, Global → Stripe)
        3. Amount-based (small → bKash, large → Wire)
        4. Success rate (highest success rate wins ties)
        5. Fallback to first available
    """

    BD_GATEWAYS     = ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay']
    GLOBAL_GATEWAYS = ['stripe', 'paypal', 'payoneer', 'wire', 'ach', 'crypto']

    # Amount thresholds
    MOBILE_BANKING_MAX = Decimal('50000')   # bKash/Nagad max
    WIRE_MIN           = Decimal('10000')   # Wire transfer minimum

    def select(self, user, amount: Decimal, country: str = 'BD',
               preferred: str = None, transaction_type: str = 'deposit') -> dict:
        """
        Select the best gateway.

        Returns:
            dict: {
                'gateway':    str,
                'fallback':   str,
                'reason':     str,
                'alternatives': [str],
            }
        """
        # 1. Use preferred if valid
        if preferred and self._is_available(preferred, amount, country):
            return {
                'gateway':    preferred,
                'fallback':   self._get_fallback(preferred, amount, country),
                'reason':     'user_preferred',
                'alternatives': [],
            }

        # 2. Country-based routing
        candidates = self._get_candidates(country, amount, transaction_type)

        # 3. Filter by availability and limits
        available = [g for g in candidates if self._is_available(g, amount, country)]

        if not available:
            available = self._get_fallback_list(amount, country)

        if not available:
            raise Exception('No payment gateway available for this transaction.')

        # 4. Rank by success rate
        ranked = self._rank_by_success_rate(available)

        best     = ranked[0]
        fallback = ranked[1] if len(ranked) > 1 else None

        return {
            'gateway':      best,
            'fallback':     fallback,
            'reason':       f'auto_selected (country={country}, amount={amount})',
            'alternatives': ranked[1:4],
        }

    def _get_candidates(self, country: str, amount: Decimal, txn_type: str) -> list:
        if country == 'BD':
            if amount <= self.MOBILE_BANKING_MAX:
                return ['bkash', 'nagad', 'sslcommerz', 'amarpay', 'upay', 'shurjopay']
            else:
                return ['sslcommerz', 'wire', 'stripe']
        elif country == 'US':
            return ['ach', 'stripe', 'paypal']
        else:
            return ['stripe', 'paypal', 'payoneer', 'wire', 'crypto']

    def _get_fallback(self, gateway: str, amount: Decimal, country: str) -> str:
        fallback_map = {
            'bkash':      'nagad',
            'nagad':      'bkash',
            'sslcommerz': 'amarpay',
            'amarpay':    'sslcommerz',
            'upay':       'shurjopay',
            'shurjopay':  'upay',
            'stripe':     'paypal',
            'paypal':     'stripe',
            'ach':        'stripe',
            'payoneer':   'paypal',
            'wire':       'stripe',
            'crypto':     'paypal',
        }
        return fallback_map.get(gateway, 'stripe')

    def _get_fallback_list(self, amount: Decimal, country: str) -> list:
        if country == 'BD':
            return ['sslcommerz', 'stripe']
        return ['stripe', 'paypal']

    def _is_available(self, gateway: str, amount: Decimal, country: str) -> bool:
        try:
            from api.payment_gateways.models import PaymentGateway
            gw = PaymentGateway.objects.get(name=gateway, status='active')
            if amount < gw.minimum_amount or amount > gw.maximum_amount:
                return False
            return True
        except Exception:
            return False

    def _rank_by_success_rate(self, gateways: list) -> list:
        rates = {}
        for gw in gateways:
            cached = cache.get(f'gw_success_rate:{gw}')
            rates[gw] = cached if cached is not None else 0.90  # Default 90%
        return sorted(gateways, key=lambda g: rates[g], reverse=True)


class GatewayFallbackService:
    """
    Handles automatic fallback when primary gateway fails.
    Tries alternative gateways in order.
    """

    def process_with_fallback(self, user, amount: Decimal, gateway: str,
                               transaction_type: str = 'deposit', **kwargs) -> dict:
        """
        Try primary gateway; if it fails, try fallback.
        Returns first successful result.
        """
        from .PaymentFactory import PaymentFactory

        router  = GatewayRouterService()
        routing = router.select(user, amount, preferred=gateway,
                                transaction_type=transaction_type)

        order = [routing['gateway']] + [routing['fallback']] if routing['fallback'] else [routing['gateway']]
        order += routing.get('alternatives', [])

        last_error = None
        for gw in order:
            try:
                processor = PaymentFactory.get_processor(gw)
                if transaction_type == 'deposit':
                    result = processor.process_deposit(user=user, amount=amount, **kwargs)
                else:
                    result = processor.process_withdrawal(
                        user=user, amount=amount,
                        payment_method=kwargs.get('payment_method'), **kwargs
                    )
                result['used_gateway'] = gw
                result['was_fallback'] = gw != gateway
                logger.info(f'Fallback service: {gw} succeeded (was {gateway})')
                return result
            except Exception as e:
                last_error = e
                logger.warning(f'Gateway {gw} failed, trying next: {e}')
                continue

        raise Exception(f'All gateways failed. Last error: {last_error}')
