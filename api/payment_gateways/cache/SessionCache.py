# FILE 93 of 257 — cache/SessionCache.py
# User payment session management

from django.core.cache import cache
import uuid, json

class SessionCache:
    """Manage short-lived payment sessions for redirect-based gateways."""
    TTL = 1800  # 30 min

    @staticmethod
    def create(user_id: int, gateway: str, amount: float, metadata: dict = None) -> str:
        session_id = str(uuid.uuid4())
        data = {
            'user_id':    user_id,
            'gateway':    gateway,
            'amount':     str(amount),
            'metadata':   metadata or {},
        }
        cache.set(f'pay_sess:{session_id}', json.dumps(data), SessionCache.TTL)
        return session_id

    @staticmethod
    def get(session_id: str) -> dict | None:
        raw = cache.get(f'pay_sess:{session_id}')
        return json.loads(raw) if raw else None

    @staticmethod
    def consume(session_id: str) -> dict | None:
        """Get and delete session (one-time use)."""
        data = SessionCache.get(session_id)
        if data:
            cache.delete(f'pay_sess:{session_id}')
        return data
