# api/djoyalty/integration_system/data_bridge.py
"""
Data Bridge -- Data transformation & mapping between systems।
Converts external API data formats ↔ Djoyalty internal formats।
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DataBridge:
    """
    Data transformation bridge।
    Maps external data formats to internal Djoyalty models।
    """

    # ─── Customer ─────────────────────────────────────────────────

    @staticmethod
    def external_to_customer(data: dict) -> dict:
        """Map external customer data to Djoyalty Customer format।"""
        return {
            'code': str(data.get('id') or data.get('customer_id') or data.get('code', '')).upper(),
            'email': data.get('email') or data.get('customer_email', ''),
            'phone': data.get('phone') or data.get('mobile') or data.get('msisdn', ''),
            'firstname': data.get('first_name') or data.get('firstname') or data.get('name', '').split()[0] if data.get('name') else '',
            'lastname': data.get('last_name') or data.get('lastname') or '',
            'metadata': {k: v for k, v in data.items()
                         if k not in ('id', 'email', 'phone', 'first_name', 'last_name')},
        }

    @staticmethod
    def customer_to_external(customer) -> dict:
        """Map Djoyalty Customer to external format।"""
        return {
            'id': customer.id,
            'code': customer.code,
            'email': customer.email or '',
            'phone': customer.phone or '',
            'first_name': customer.firstname or '',
            'last_name': customer.lastname or '',
            'loyalty_number': customer.loyalty_number or customer.code,
        }

    # ─── Transaction ──────────────────────────────────────────────

    @staticmethod
    def external_to_transaction(data: dict) -> dict:
        """Map external transaction to Djoyalty Txn format।"""
        amount = data.get('amount') or data.get('total') or data.get('value', 0)
        try:
            amount = Decimal(str(amount))
        except InvalidOperation:
            amount = Decimal('0')
        return {
            'value': amount,
            'currency': data.get('currency', 'BDT'),
            'reference_id': str(data.get('order_id') or data.get('transaction_id') or data.get('id', '')),
            'source': data.get('source') or data.get('channel', 'external'),
            'metadata': data,
        }

    # ─── Points Ledger ────────────────────────────────────────────

    @staticmethod
    def points_to_external(points_data: dict) -> dict:
        """Map points data to standard external format।"""
        return {
            'balance': str(points_data.get('balance', 0)),
            'lifetime_earned': str(points_data.get('lifetime_earned', 0)),
            'lifetime_redeemed': str(points_data.get('lifetime_redeemed', 0)),
            'currency': 'points',
        }

    # ─── Offerwall Postback ───────────────────────────────────────

    @staticmethod
    def normalize_postback(provider: str, raw_data: dict) -> dict:
        """Normalize postback data from different providers to standard format।"""
        normalizers = {
            'cpalead': DataBridge._normalize_cpalead,
            'tapjoy':  DataBridge._normalize_tapjoy,
            'xsolla':  DataBridge._normalize_xsolla,
        }
        fn = normalizers.get(provider, DataBridge._normalize_generic)
        return fn(raw_data)

    @staticmethod
    def _normalize_cpalead(data: dict) -> dict:
        return {
            'customer_ref': data.get('subid', ''),
            'offer_id': str(data.get('offer_id', '')),
            'transaction_id': data.get('transaction_id', data.get('tid', '')),
            'payout': Decimal(str(data.get('payout', 0))),
            'currency': 'USD',
            'ip': data.get('ip', ''),
        }

    @staticmethod
    def _normalize_tapjoy(data: dict) -> dict:
        return {
            'customer_ref': data.get('user_id', ''),
            'offer_id': str(data.get('offer_id', '')),
            'transaction_id': data.get('verifier', ''),
            'payout': Decimal(str(data.get('currency', 0))),
            'currency': 'USD',
            'ip': data.get('ip_address', ''),
        }

    @staticmethod
    def _normalize_xsolla(data: dict) -> dict:
        return {
            'customer_ref': data.get('user_id', ''),
            'offer_id': str(data.get('order_id', '')),
            'transaction_id': data.get('transaction', {}).get('id', ''),
            'payout': Decimal(str(data.get('purchase', {}).get('checkout', {}).get('amount', 0))),
            'currency': data.get('purchase', {}).get('checkout', {}).get('currency', 'USD'),
            'ip': '',
        }

    @staticmethod
    def _normalize_generic(data: dict) -> dict:
        return {
            'customer_ref': str(data.get('subid') or data.get('user_id') or data.get('customer_id', '')),
            'offer_id': str(data.get('offer_id', '')),
            'transaction_id': str(data.get('transaction_id') or data.get('txn_id') or data.get('id', '')),
            'payout': Decimal(str(data.get('payout') or data.get('amount', 0))),
            'currency': data.get('currency', 'USD'),
            'ip': data.get('ip') or data.get('ip_address', ''),
        }

    # ─── Webhook Payload ─────────────────────────────────────────

    @staticmethod
    def build_webhook_payload(event_type: str, customer, data: dict,
                               version: str = 'v1') -> dict:
        """Build standardized outbound webhook payload।"""
        from django.utils import timezone
        return {
            'version': version,
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'customer': DataBridge.customer_to_external(customer),
            'data': data,
        }
