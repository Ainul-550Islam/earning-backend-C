# api/djoyalty/integration_system/integ_adapter.py
"""
Integration Adapter -- Adapter pattern for external systems।
Standardizes different external API responses into Djoyalty format।
Pattern: Adapter (GoF) + Port & Adapters (Hexagonal Architecture)।
"""
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


# ─── Abstract Ports ───────────────────────────────────────────────────────────

class PaymentAdapter(ABC):
    """Abstract port for payment integrations।"""

    @abstractmethod
    def create_payment(self, amount: Decimal, reference: str,
                        customer_phone: str = '', **kwargs) -> dict:
        """Create payment session। Returns: {payment_id, redirect_url, ...}"""
        pass

    @abstractmethod
    def verify_payment(self, payment_id: str, **kwargs) -> dict:
        """Verify payment status। Returns: {success, amount, transaction_id}"""
        pass

    @abstractmethod
    def refund(self, payment_id: str, amount: Decimal, reason: str = '') -> dict:
        """Refund payment। Returns: {success, refund_id}"""
        pass

    def to_standard_response(self, raw_response: dict) -> dict:
        """Convert provider-specific response to standard format।"""
        return {
            'success': bool(raw_response.get('success') or raw_response.get('statusCode') == '0000'),
            'payment_id': raw_response.get('paymentID') or raw_response.get('payment_id', ''),
            'transaction_id': raw_response.get('trxID') or raw_response.get('transaction_id', ''),
            'amount': raw_response.get('amount', '0'),
            'currency': raw_response.get('currency', 'BDT'),
            'status': raw_response.get('transactionStatus') or raw_response.get('status', ''),
            'raw': raw_response,
        }


class SMSAdapter(ABC):
    """Abstract port for SMS integrations।"""

    @abstractmethod
    def send(self, to: str, message: str) -> dict:
        """Send SMS। Returns: {success, message_id, error}"""
        pass

    def to_standard_response(self, raw_response: dict) -> dict:
        return {
            'success': raw_response.get('response_code') == 202
                       or raw_response.get('status') == 'success'
                       or raw_response.get('sid') is not None,
            'message_id': (
                raw_response.get('id') or
                raw_response.get('sid') or
                raw_response.get('message_id', '')
            ),
            'raw': raw_response,
        }


class PushAdapter(ABC):
    """Abstract port for push notification integrations।"""

    @abstractmethod
    def send_to_token(self, token: str, title: str, body: str, data: dict = None) -> bool:
        pass

    @abstractmethod
    def send_to_multiple(self, tokens: list, title: str, body: str, data: dict = None) -> dict:
        pass


class OCRAdapter(ABC):
    """Abstract port for OCR integrations।"""

    @abstractmethod
    def extract_text(self, image_url: str) -> str:
        pass

    def extract_receipt_data(self, image_url: str) -> dict:
        """Extract and parse receipt data।"""
        text = self.extract_text(image_url)
        return {'raw_text': text}


# ─── Concrete Adapters ────────────────────────────────────────────────────────

class BkashPaymentAdapter(PaymentAdapter):
    """bKash -> Standard PaymentAdapter।"""

    def __init__(self):
        from ..integrations.bkash import BkashIntegration
        self._client = BkashIntegration()

    def create_payment(self, amount: Decimal, reference: str,
                        customer_phone: str = '', **kwargs) -> dict:
        from django.conf import settings
        result = self._client.create_payment(
            amount=str(amount),
            reference=reference,
            callback_url=getattr(settings, 'BKASH_CALLBACK_URL', ''),
        )
        return self.to_standard_response(result)

    def verify_payment(self, payment_id: str, **kwargs) -> dict:
        result = self._client.query_payment(payment_id)
        return self.to_standard_response(result)

    def refund(self, payment_id: str, amount: Decimal, reason: str = '') -> dict:
        # bKash refund requires trxID -- get from stored payment
        return {'success': False, 'error': 'bKash refund requires manual processing'}

    def send_cashout(self, phone: str, amount: Decimal, reference: str) -> dict:
        try:
            result = self._client.send_money_b2c(
                receiver_msisdn=phone,
                amount=str(amount),
                reference=reference,
            )
            return self.to_standard_response(result)
        except Exception as e:
            return {'success': False, 'error': str(e)}


class NagadPaymentAdapter(PaymentAdapter):
    """Nagad -> Standard PaymentAdapter।"""

    def __init__(self):
        from ..integrations.nagad import NagadIntegration
        self._client = NagadIntegration()

    def create_payment(self, amount: Decimal, reference: str,
                        customer_phone: str = '', **kwargs) -> dict:
        try:
            result = self._client.init_payment(
                order_id=reference,
                amount=str(amount),
            )
            return {
                'success': True,
                'payment_ref_id': result.get('paymentReferenceId', ''),
                'redirect_url': result.get('callBackUrl', ''),
                'raw': result,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def verify_payment(self, payment_id: str, **kwargs) -> dict:
        result = self._client.verify_payment(payment_id)
        return {
            'success': result.get('status') == 'Success',
            'transaction_id': result.get('merchantOrderId', ''),
            'raw': result,
        }

    def refund(self, payment_id: str, amount: Decimal, reason: str = '') -> dict:
        return {'success': False, 'error': 'Nagad refund requires manual processing'}


class SSLCommerzAdapter(PaymentAdapter):
    """SSLCommerz -> Standard PaymentAdapter।"""

    def __init__(self):
        from ..integrations.sslcommerz import SSLCommerzIntegration
        self._client = SSLCommerzIntegration()

    def create_payment(self, amount: Decimal, reference: str,
                        customer_phone: str = '', customer: dict = None, **kwargs) -> dict:
        from django.conf import settings
        result = self._client.init_payment(
            order_id=reference,
            amount=float(amount),
            customer=customer or {'phone': customer_phone},
            success_url=getattr(settings, 'SSLCOMMERZ_SUCCESS_URL', ''),
            fail_url=getattr(settings, 'SSLCOMMERZ_FAIL_URL', ''),
        )
        return {
            'success': result.get('status') == 'SUCCESS',
            'redirect_url': result.get('GatewayPageURL', ''),
            'session_key': result.get('sessionkey', ''),
            'raw': result,
        }

    def verify_payment(self, payment_id: str, **kwargs) -> dict:
        result = self._client.validate_payment(payment_id)
        return {
            'success': result.get('status') == 'VALID',
            'transaction_id': result.get('bank_tran_id', ''),
            'amount': result.get('amount', '0'),
            'raw': result,
        }

    def refund(self, payment_id: str, amount: Decimal, reason: str = '') -> dict:
        result = self._client.refund(payment_id, float(amount), reason)
        return {'success': True, 'raw': result}


# ─── Adapter Factory ─────────────────────────────────────────────────────────

class AdapterFactory:
    """
    Factory for creating adapters।
    Selects correct adapter based on method/provider name।
    """

    _payment_adapters: Dict[str, type] = {
        'bkash':      BkashPaymentAdapter,
        'nagad':      NagadPaymentAdapter,
        'sslcommerz': SSLCommerzAdapter,
        'bank_transfer': SSLCommerzAdapter,
    }

    @classmethod
    def get_payment_adapter(cls, method: str) -> Optional[PaymentAdapter]:
        """Get payment adapter by method name।"""
        adapter_cls = cls._payment_adapters.get(method)
        if not adapter_cls:
            logger.warning('AdapterFactory: no payment adapter for %s', method)
            return None
        try:
            return adapter_cls()
        except Exception as e:
            logger.error('AdapterFactory.get_payment_adapter[%s] error: %s', method, e)
            return None

    @classmethod
    def register_payment_adapter(cls, method: str, adapter_cls: type):
        """Register custom payment adapter।"""
        cls._payment_adapters[method] = adapter_cls
        logger.info('AdapterFactory: registered payment adapter for %s', method)
