# api/payment_gateways/refunds/RefundFactory.py
# FILE 58 of 257 — RefundFactory: central registry for all 8 refund processors

from .BkashRefund      import BkashRefund
from .NagadRefund      import NagadRefund
from .SSLCommerzRefund import SSLCommerzRefund
from .AmarPayRefund    import AmarPayRefund
from .UpayRefund       import UpayRefund
from .ShurjoPayRefund  import ShurjoPayRefund
from .StripeRefund     import StripeRefund
from .PayPalRefund     import PayPalRefund


class RefundFactory:
    """
    Factory class to get the correct refund processor for a given gateway.

    Usage:
        processor = RefundFactory.get_processor('bkash')
        result = processor.process_refund(transaction, amount=100, reason='customer_request')

        # Or directly from a transaction object:
        processor = RefundFactory.get_processor_for_transaction(transaction)
    """

    _PROCESSOR_MAP = {
        'bkash':      BkashRefund,
        'nagad':      NagadRefund,
        'sslcommerz': SSLCommerzRefund,
        'amarpay':    AmarPayRefund,
        'upay':       UpayRefund,
        'shurjopay':  ShurjoPayRefund,
        'stripe':     StripeRefund,
        'paypal':     PayPalRefund,
    }

    # ── Refund support metadata ───────────────────────────────────────────────
    _REFUND_META = {
        'bkash':      {'instant': True,  'partial': True,  'cancel': False, 'currency': 'BDT'},
        'nagad':      {'instant': False, 'partial': True,  'cancel': False, 'currency': 'BDT'},
        'sslcommerz': {'instant': False, 'partial': True,  'cancel': False, 'currency': 'BDT'},
        'amarpay':    {'instant': False, 'partial': True,  'cancel': False, 'currency': 'BDT'},
        'upay':       {'instant': False, 'partial': True,  'cancel': False, 'currency': 'BDT'},
        'shurjopay':  {'instant': False, 'partial': True,  'cancel': False, 'currency': 'BDT'},
        'stripe':     {'instant': False, 'partial': True,  'cancel': True,  'currency': 'multi'},
        'paypal':     {'instant': False, 'partial': True,  'cancel': False, 'currency': 'multi'},
    }

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def get_processor(gateway_name: str):
        """
        Get refund processor instance by gateway name (case-insensitive).

        Args:
            gateway_name: e.g. 'bkash', 'stripe', 'sslcommerz'

        Returns:
            RefundProcessor subclass instance

        Raises:
            ValueError: If gateway not supported for refunds
        """
        key = gateway_name.lower().strip()
        processor_class = RefundFactory._PROCESSOR_MAP.get(key)
        if not processor_class:
            supported = ', '.join(RefundFactory._PROCESSOR_MAP.keys())
            raise ValueError(
                f"No refund processor for gateway '{gateway_name}'. "
                f"Supported: {supported}"
            )
        return processor_class()

    @staticmethod
    def get_processor_for_transaction(transaction):
        """
        Convenience method — get refund processor directly from a transaction object.

        Args:
            transaction: GatewayTransaction instance

        Returns:
            RefundProcessor subclass instance
        """
        return RefundFactory.get_processor(transaction.gateway)

    @staticmethod
    def get_refund_meta(gateway_name: str) -> dict:
        """
        Get refund capability metadata for a gateway.

        Returns:
            dict: {
                'instant': bool,   # True if refund is instant
                'partial': bool,   # True if partial refund supported
                'cancel':  bool,   # True if refund can be cancelled
                'currency': str    # 'BDT' or 'multi'
            }
        """
        return RefundFactory._REFUND_META.get(gateway_name.lower(), {})

    @staticmethod
    def supports_refund(gateway_name: str) -> bool:
        """Check if a gateway supports refunds"""
        return gateway_name.lower() in RefundFactory._PROCESSOR_MAP

    @staticmethod
    def supports_partial_refund(gateway_name: str) -> bool:
        """Check if a gateway supports partial refunds"""
        meta = RefundFactory._REFUND_META.get(gateway_name.lower(), {})
        return meta.get('partial', False)

    @staticmethod
    def supports_refund_cancellation(gateway_name: str) -> bool:
        """Check if a gateway allows cancelling a pending refund"""
        meta = RefundFactory._REFUND_META.get(gateway_name.lower(), {})
        return meta.get('cancel', False)

    @staticmethod
    def get_all_supported_gateways() -> list:
        """Return list of all gateways that support refunds"""
        return list(RefundFactory._PROCESSOR_MAP.keys())

    @staticmethod
    def process_refund(gateway_name: str, transaction, amount, reason: str = 'customer_request', **kwargs) -> dict:
        """
        One-liner shortcut to process a refund.

        Usage:
            result = RefundFactory.process_refund('stripe', transaction, amount=50.00)
        """
        processor = RefundFactory.get_processor(gateway_name)
        return processor.process_refund(transaction, amount, reason, **kwargs)

    @staticmethod
    def check_refund_status(gateway_name: str, refund_request, **kwargs) -> dict:
        """
        One-liner shortcut to check refund status.

        Usage:
            status = RefundFactory.check_refund_status('stripe', refund_request)
        """
        processor = RefundFactory.get_processor(gateway_name)
        return processor.check_refund_status(refund_request, **kwargs)
