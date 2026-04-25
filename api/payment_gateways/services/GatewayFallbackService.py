# api/payment_gateways/services/GatewayFallbackService.py
import logging
from decimal import Decimal
logger = logging.getLogger(__name__)


class GatewayFallbackService:
    """
    Handles automatic fallback when primary gateway fails.
    Tries alternative gateways in order until one succeeds.

    Usage:
        svc = GatewayFallbackService()
        result = svc.process_with_fallback(user, amount, 'bkash', 'deposit')
    """

    FALLBACK_CHAINS = {
        'bkash':      ['nagad',    'sslcommerz', 'amarpay'],
        'nagad':      ['bkash',    'sslcommerz', 'upay'],
        'sslcommerz': ['amarpay',  'bkash',      'nagad'],
        'amarpay':    ['sslcommerz','upay',       'shurjopay'],
        'upay':       ['shurjopay','amarpay',     'sslcommerz'],
        'shurjopay':  ['upay',     'amarpay',     'sslcommerz'],
        'stripe':     ['paypal',   'payoneer',    'wire'],
        'paypal':     ['stripe',   'payoneer',    'wire'],
        'payoneer':   ['paypal',   'stripe',      'wire'],
        'ach':        ['stripe',   'wire'],
        'wire':       ['stripe',   'paypal'],
        'crypto':     ['paypal',   'stripe'],
    }

    def process_with_fallback(self, user, amount: Decimal, gateway: str,
                               transaction_type: str = 'deposit', **kwargs) -> dict:
        """
        Try primary gateway; auto-fallback on failure.

        Returns first successful result with metadata:
            result['used_gateway']   — which gateway actually processed
            result['was_fallback']   — True if fallback was used
            result['attempted']      — list of gateways tried
        """
        from .PaymentFactory import PaymentFactory
        from .GatewayRouterService import GatewayRouterService

        chain     = [gateway] + self.FALLBACK_CHAINS.get(gateway, [])
        attempted = []
        last_error = None

        for gw in chain:
            attempted.append(gw)
            try:
                processor = PaymentFactory.get_processor(gw)
                if transaction_type == 'deposit':
                    result = processor.process_deposit(user=user, amount=amount,
                                                        metadata=kwargs.get('metadata', {}))
                else:
                    result = processor.process_withdrawal(
                        user=user, amount=amount,
                        payment_method=kwargs.get('payment_method')
                    )
                result['used_gateway']  = gw
                result['was_fallback']  = (gw != gateway)
                result['attempted']     = attempted

                if gw != gateway:
                    logger.info(f'Fallback used: {gateway} → {gw} for {transaction_type}')
                return result

            except Exception as e:
                last_error = e
                logger.warning(f'Gateway {gw} failed ({transaction_type}): {e}. Trying next...')
                continue

        raise Exception(
            f'All gateways failed after trying: {attempted}. Last error: {last_error}'
        )

    def get_fallback_chain(self, gateway: str) -> list:
        """Return the fallback chain for a gateway."""
        return [gateway] + self.FALLBACK_CHAINS.get(gateway, [])

    def mark_gateway_failed(self, gateway: str, error: str = ''):
        """Temporarily mark a gateway as failed in cache."""
        from django.core.cache import cache
        cache.set(f'gw_failed:{gateway}', {'error': error}, 300)  # 5 min blackout
        logger.warning(f'Gateway {gateway} marked as failed: {error}')
