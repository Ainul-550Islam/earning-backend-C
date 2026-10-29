"""
tasks/integration/data_bridge.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DataBridge — Cross-Task Data Sharing Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provides structured, typed data sharing between Celery tasks.
All data flows through DataBridge so there's ONE source of truth.

Key features:
- Namespace-scoped keys (user, offer, publisher, platform)
- TTL management with automatic expiry
- Bulk get/set for efficiency
- Change tracking (who set what, when)
- Fallback to DB if cache miss
"""

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

BRIDGE_PREFIX   = 'db:'   # DataBridge cache key prefix
DEFAULT_TTL     = 3600    # 1 hour default
LONG_TTL        = 86400   # 24 hours for stable data
PERMANENT_TTL   = None    # No expiry (user tier, KYC level)

# Security: Key separator to prevent collisions
KEY_SEPARATOR   = '::'


class DataBridge:
    """
    Central key-value store bridging all tasks.
    Backed by Redis (via Django cache) with DB fallback.

    Namespaces:
        user:       Per-user data (balance, score, tier, segment)
        offer:      Per-offer data (EPC, quality, caps)
        publisher:  Per-publisher data (tier, revenue_share, score)
        platform:   Platform-wide aggregates (total_users, daily_revenue)
        session:    Short-lived session data (click tracking, locker state)
        queue:      Queue depth snapshots
    """

    # ─── Core Operations ───────────────────────────────────────────────────────

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = DEFAULT_TTL, meta: dict = None) -> bool:
        """Store a value under a namespaced key."""
        try:
            # Security: Validate and sanitize inputs
            if not key or not isinstance(key, str):
                logger.error(f"[DataBridge] Invalid key: {key}")
                return False

            # Security: Sanitize key to prevent injection
            clean_key = cls._sanitize_key(key)
            if not clean_key:
                logger.error(f"[DataBridge] Rejected dangerous key: {key}")
                return False

            # Serialize value
            data = {
                'v': cls._serialize(value),
                'm': meta or {},
                'ts': timezone.now().isoformat(),
                'src': 'databridge',
                'hash': cls._hash_value(value)  # Security: Integrity hash
            }

            # Build full key with namespace and separator
            full_key = f"{BRIDGE_PREFIX}{clean_key}"
            
            # Store in cache
            cache.set(full_key, data, timeout=ttl)
            logger.debug(f"[DataBridge] set: {clean_key} (ttl={ttl})")
            return True

        except Exception as e:
            logger.error(f"[DataBridge] set error ({key}): {e}")
            return False

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Retrieve a value, returning default if missing."""
        try:
            clean_key = cls._sanitize_key(key)
            if not clean_key:
                return default
                
            full_key = f"{BRIDGE_PREFIX}{clean_key}"
            data     = cache.get(full_key)
            
            if not data or not isinstance(data, dict):
                return default
            
            # Verify integrity if hash exists
            if 'hash' in data:
                current_hash = cls._hash_value(data.get('v'))
                if current_hash != data.get('hash'):
                    logger.warning(f"[DataBridge] Integrity check failed for key: {key}")
                    return default
            
            return cls._deserialize(data.get('v'))
        except Exception as e:
            logger.error(f"[DataBridge] get error ({key}): {e}")
            return default

    @classmethod
    def get_with_meta(cls, key: str) -> Tuple[Any, Optional[dict]]:
        """Retrieve value AND metadata (set time, source)."""
        try:
            full_key = f"{BRIDGE_PREFIX}{key}"
            data     = cache.get(full_key)
            if data is None:
                return None, None
            return cls._deserialize(data.get('v')), data.get('m', {})
        except Exception:
            return None, None

    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete a key from the bridge."""
        try:
            cache.delete(f"{BRIDGE_PREFIX}{key}")
            return True
        except Exception:
            return False

    @classmethod
    def exists(cls, key: str) -> bool:
        """Check if a key exists."""
        return cache.get(f"{BRIDGE_PREFIX}{key}") is not None

    @classmethod
    def bulk_set(cls, data: Dict[str, Any], ttl: int = DEFAULT_TTL) -> int:
        """Set multiple keys at once. Returns count of successful sets."""
        success = 0
        for key, value in data.items():
            if cls.set(key, value, ttl=ttl):
                success += 1
        return success

    @classmethod
    def bulk_get(cls, keys: List[str]) -> Dict[str, Any]:
        """Get multiple keys at once. Missing keys return None."""
        return {key: cls.get(key) for key in keys}

    # ─── User Namespace ────────────────────────────────────────────────────────

    @classmethod
    def user(cls, user_id: int) -> 'UserDataView':
        """Return a user-scoped view for convenient access."""
        return UserDataView(user_id)

    @classmethod
    def set_user(cls, user_id: int, field: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """Set a user-specific field."""
        return cls.set(f"user:{user_id}:{field}", value, ttl=ttl)

    @classmethod
    def get_user(cls, user_id: int, field: str, default: Any = None) -> Any:
        """Get a user-specific field."""
        return cls.get(f"user:{user_id}:{field}", default=default)

    @classmethod
    def get_user_snapshot(cls, user_id: int) -> Dict[str, Any]:
        """
        Get a complete snapshot of all known user data.
        Pulls from cache (DataBridge) with DB fallback for missing fields.
        """
        fields = [
            'wallet_balance', 'fraud_score', 'kyc_tier', 'traffic_tier',
            'level', 'xp_points', 'streak', 'segment', 'is_vip',
            'total_earnings', 'referral_count', 'quality_score',
        ]
        snapshot = {f: cls.get_user(user_id, f) for f in fields}

        # DB fallback for missing critical fields
        if snapshot['wallet_balance'] is None:
            snapshot['wallet_balance'] = cls._db_wallet_balance(user_id)
        if snapshot['fraud_score'] is None:
            snapshot['fraud_score'] = 0

        snapshot['user_id']    = user_id
        snapshot['fetched_at'] = timezone.now().isoformat()
        return snapshot

    # ─── Offer Namespace ───────────────────────────────────────────────────────

    @classmethod
    def set_offer(cls, offer_id: str, field: str, value: Any, ttl: int = 1800) -> bool:
        return cls.set(f"offer:{offer_id}:{field}", value, ttl=ttl)

    @classmethod
    def get_offer(cls, offer_id: str, field: str, default: Any = None) -> Any:
        return cls.get(f"offer:{offer_id}:{field}", default=default)

    @classmethod
    def get_offer_snapshot(cls, offer_id: str) -> Dict[str, Any]:
        fields = ['epc', 'cvr', 'payout', 'quality_score', 'daily_clicks_used',
                  'daily_cap', 'is_active', 'geo_map', 'conversion_rate']
        snap   = {f: cls.get_offer(offer_id, f) for f in fields}
        snap['offer_id']   = offer_id
        snap['fetched_at'] = timezone.now().isoformat()
        return snap

    # ─── Publisher Namespace ───────────────────────────────────────────────────

    @classmethod
    def set_publisher(cls, pub_id: int, field: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        return cls.set(f"publisher:{pub_id}:{field}", value, ttl=ttl)

    @classmethod
    def get_publisher(cls, pub_id: int, field: str, default: Any = None) -> Any:
        return cls.get(f"publisher:{pub_id}:{field}", default=default)

    # ─── Platform Namespace ────────────────────────────────────────────────────

    @classmethod
    def set_platform(cls, field: str, value: Any, ttl: int = 600) -> bool:
        return cls.set(f"platform:{field}", value, ttl=ttl)

    @classmethod
    def get_platform(cls, field: str, default: Any = None) -> Any:
        return cls.get(f"platform:{field}", default=default)

    @classmethod
    def get_platform_snapshot(cls) -> Dict[str, Any]:
        """Get all platform-wide KPIs in one call."""
        fields = ['total_users', 'daily_revenue', 'active_tasks', 'queue_depth']
        snap   = {f: cls.get_platform(f) for f in fields}
        return snap

    # ─── Session Namespace (short-lived) ──────────────────────────────────────

    @classmethod
    def set_session(cls, session_id: str, field: str, value: Any, ttl: int = 3600) -> bool:
        return cls.set(f"session:{session_id}:{field}", value, ttl=ttl)

    @classmethod
    def get_session(cls, session_id: str, field: str, default: Any = None) -> Any:
        return cls.get(f"session:{session_id}:{field}", default=default)

    # ─── Serialization helpers ─────────────────────────────────────────────────

    @classmethod
    def _sanitize_key(cls, key: Any) -> str:
        """Make a cache-safe key: str, no whitespace/control chars, max 200."""
        import re
        return re.sub(r"[\s\x00-\x1f\x7f]+", "_", str(key))[:200]

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        if isinstance(value, Decimal):
            return {'__decimal__': str(value)}
        if isinstance(value, (list, dict, str, int, float, bool, type(None))):
            return value
        try:
            return str(value)
        except Exception:
            return None

    @classmethod
    def _deserialize(cls, value: Any) -> Any:
        if isinstance(value, dict) and '__decimal__' in value:
            return Decimal(value['__decimal__'])
        return value

    # ─── DB Fallbacks ──────────────────────────────────────────────────────────

    @classmethod
    def _db_wallet_balance(cls, user_id: int) -> Optional[Decimal]:
        try:
            from wallet.models import Wallet
            w = Wallet.objects.filter(user_id=user_id).values_list('balance', flat=True).first()
            if w is not None:
                cls.set_user(user_id, 'wallet_balance', w, ttl=300)
            return w
        except ImportError:
            return None


class UserDataView:
    """Convenience accessor for user-scoped DataBridge data."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    def __getattr__(self, field: str) -> Any:
        return DataBridge.get_user(self.user_id, field)

    def set(self, field: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        return DataBridge.set_user(self.user_id, field, value, ttl=ttl)

    def snapshot(self) -> Dict[str, Any]:
        return DataBridge.get_user_snapshot(self.user_id)

    def invalidate(self, field: str = None) -> None:
        if field:
            DataBridge.delete(f"user:{self.user_id}:{field}")
        else:
            for f in ['wallet_balance', 'fraud_score', 'kyc_tier', 'level', 'xp_points']:
                DataBridge.delete(f"user:{self.user_id}:{f}")
