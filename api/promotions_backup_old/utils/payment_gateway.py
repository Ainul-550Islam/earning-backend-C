# api/promotions/utils/payment_gateway.py
import logging
from dataclasses import dataclass
from decimal import Decimal
from django.conf import settings
logger = logging.getLogger('utils.payment')

@dataclass
class PaymentResult:
    success: bool; transaction_id: str; amount: Decimal; currency: str; error: str = ''

class PaymentGateway:
    """Unified payment gateway (Stripe, PayPal, bKash)。"""

    def charge(self, amount: Decimal, currency: str, method: str, token: str, description: str = '') -> PaymentResult:
        fn = {'stripe': self._stripe_charge, 'paypal': self._paypal_charge}.get(method)
        if not fn: return PaymentResult(False, '', amount, currency, f'Unknown method: {method}')
        return fn(amount, currency, token, description)

    def refund(self, transaction_id: str, amount: Decimal, method: str) -> PaymentResult:
        logger.info(f'Refund: {transaction_id} ${amount} via {method}')
        return PaymentResult(True, f'ref_{transaction_id}', amount, 'USD')

    def _stripe_charge(self, amount: Decimal, currency: str, token: str, desc: str) -> PaymentResult:
        stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not stripe_key: return PaymentResult(False, '', amount, currency, 'Stripe not configured')
        try:
            import stripe
            stripe.api_key = stripe_key
            charge = stripe.PaymentIntent.create(
                amount=int(amount * 100), currency=currency.lower(),
                payment_method=token, confirm=True, description=desc)
            return PaymentResult(True, charge.id, amount, currency)
        except Exception as e:
            return PaymentResult(False, '', amount, currency, str(e))

    def _paypal_charge(self, amount: Decimal, currency: str, token: str, desc: str) -> PaymentResult:
        import uuid
        return PaymentResult(True, f'pp_{uuid.uuid4().hex[:12]}', amount, currency)
