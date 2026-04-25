# api/payment_gateways/abstracts.py
from django.db import models
from decimal import Decimal


class BasePaymentModel(models.Model):
    """Abstract base for all payment models."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata   = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class BaseTransactionModel(BasePaymentModel):
    """Abstract base for transaction-like models."""
    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    currency   = models.CharField(max_length=5, default='USD')
    status     = models.CharField(max_length=20, default='pending')
    reference_id = models.CharField(max_length=200, blank=True, db_index=True)

    class Meta:
        abstract = True

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def is_pending(self):
        return self.status in ('pending', 'processing')

    @property
    def is_failed(self):
        return self.status == 'failed'


class BaseGatewayService:
    """Abstract base for all gateway service classes."""
    gateway_name = ''

    def process_deposit(self, user, amount: Decimal, **kwargs) -> dict:
        raise NotImplementedError(f'{self.__class__.__name__}.process_deposit not implemented')

    def process_withdrawal(self, user, amount: Decimal, payment_method, **kwargs) -> dict:
        raise NotImplementedError(f'{self.__class__.__name__}.process_withdrawal not implemented')

    def verify_payment(self, session_id: str, **kwargs) -> dict:
        raise NotImplementedError(f'{self.__class__.__name__}.verify_payment not implemented')

    def process_refund(self, transaction_id: str, amount: Decimal, **kwargs) -> dict:
        raise NotImplementedError(f'{self.__class__.__name__}.process_refund not implemented')

    def validate_amount(self, amount: Decimal):
        from api.payment_gateways.choices import ALL_GATEWAYS
        from api.payment_gateways.constants import GATEWAY_FEES
        if amount <= 0:
            raise ValueError('Amount must be positive')

    def get_fee(self, amount: Decimal) -> Decimal:
        from api.payment_gateways.constants import GATEWAY_FEES
        rate = Decimal(str(GATEWAY_FEES.get(self.gateway_name, 0.015)))
        return (amount * rate).quantize(Decimal('0.01'))
