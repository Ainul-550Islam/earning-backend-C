# FILE 92 of 257 — cache/PaymentCache.py
# Cache gateway availability status and payment session data

from django.core.cache import cache
import json, logging
logger = logging.getLogger(__name__)

GW_STATUS_TTL   = 300    # 5 minutes
SESSION_TTL     = 1800   # 30 minutes

class PaymentCache:
    """Cache gateway status, active payment sessions, and exchange rates."""

    # ── Gateway status ────────────────────────────────────────────────────────
    @staticmethod
    def get_gateway_status(gateway: str) -> dict | None:
        return cache.get(f'gw_status:{gateway}')

    @staticmethod
    def set_gateway_status(gateway: str, status: dict):
        cache.set(f'gw_status:{gateway}', status, GW_STATUS_TTL)

    @staticmethod
    def set_gateway_down(gateway: str, reason: str = ''):
        PaymentCache.set_gateway_status(gateway, {'available': False, 'reason': reason})

    @staticmethod
    def set_gateway_up(gateway: str):
        PaymentCache.set_gateway_status(gateway, {'available': True})

    # ── Payment session ───────────────────────────────────────────────────────
    @staticmethod
    def store_session(reference_id: str, data: dict):
        cache.set(f'pay_session:{reference_id}', json.dumps(data), SESSION_TTL)

    @staticmethod
    def get_session(reference_id: str) -> dict | None:
        raw = cache.get(f'pay_session:{reference_id}')
        return json.loads(raw) if raw else None

    @staticmethod
    def delete_session(reference_id: str):
        cache.delete(f'pay_session:{reference_id}')

    # ── Exchange rates ────────────────────────────────────────────────────────
    @staticmethod
    def get_exchange_rate(from_currency: str, to_currency: str) -> float | None:
        return cache.get(f'fx:{from_currency}:{to_currency}')

    @staticmethod
    def set_exchange_rate(from_currency: str, to_currency: str, rate: float):
        cache.set(f'fx:{from_currency}:{to_currency}', rate, timeout=3600)  # 1 hour
