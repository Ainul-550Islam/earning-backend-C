"""
postback_handlers/impression_handler.py
─────────────────────────────────────────
Handles impression (ad view) tracking events.
Impressions are high volume — this handler is optimised for speed:
  - Minimal validation
  - Async write (no blocking DB call in hot path)
  - Redis-buffered (flush every N seconds via Celery)
"""
from __future__ import annotations
import json
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

_IMPRESSION_BUFFER_KEY = "pe:impression:buffer:{network_id}"
_BUFFER_SIZE = 100  # flush after N impressions
_BUFFER_TTL  = 60   # flush every 60 seconds max


class ImpressionHandler:
    """
    High-throughput impression handler with Redis write buffering.
    Impressions are buffered in Redis and flushed to DB in batches.
    """

    def record(
        self,
        network_key: str,
        offer_id: str,
        ip_address: str,
        user_agent: str,
        placement: str = "",
        country: str = "",
        user_id: str = "",
    ) -> bool:
        """
        Record an impression. Buffers in Redis for batch DB write.
        Returns True (always — never block the caller).
        """
        data = {
            "network_key": network_key,
            "offer_id": offer_id,
            "ip": ip_address,
            "ua": user_agent[:500],
            "placement": placement,
            "country": country,
            "user_id": user_id,
            "ts": timezone.now().isoformat(),
        }
        self._buffer(network_key, data)
        return True

    def flush_buffer(self, network_key: str) -> int:
        """
        Flush buffered impressions to DB.
        Called by Celery beat task every 60 seconds.
        Returns count flushed.
        """
        import hashlib
        net_hash = hashlib.md5(network_key.encode()).hexdigest()[:12]
        key = _IMPRESSION_BUFFER_KEY.format(network_id=net_hash)
        try:
            client = cache.client.get_client()
            items = client.lrange(key, 0, -1)
            if not items:
                return 0
            client.delete(key)

            from ..models import Impression, AdNetworkConfig
            network = AdNetworkConfig.objects.get_by_key(network_key)
            if not network:
                return 0

            impressions = []
            for raw in items:
                try:
                    d = json.loads(raw)
                    impressions.append(Impression(
                        tenant=network.tenant,
                        network=network,
                        offer_id=d.get("offer_id", ""),
                        ip_address=d.get("ip") or None,
                        user_agent=d.get("ua", ""),
                        placement=d.get("placement", ""),
                        country=d.get("country", ""),
                    ))
                except Exception:
                    continue

            if impressions:
                Impression.objects.bulk_create(impressions, ignore_conflicts=True)
            return len(impressions)
        except Exception as exc:
            logger.warning("ImpressionHandler.flush_buffer failed: %s", exc)
            return 0

    def _buffer(self, network_key: str, data: dict) -> None:
        import hashlib
        net_hash = hashlib.md5(network_key.encode()).hexdigest()[:12]
        key = _IMPRESSION_BUFFER_KEY.format(network_id=net_hash)
        try:
            client = cache.client.get_client()
            client.rpush(key, json.dumps(data))
            client.expire(key, _BUFFER_TTL)
            # Auto-flush when buffer is full
            if client.llen(key) >= _BUFFER_SIZE:
                from ..tasks import flush_impression_buffer_task
                flush_impression_buffer_task.apply_async(
                    args=[network_key], countdown=0
                )
        except Exception as exc:
            # If Redis is down, write directly to DB (slow path)
            logger.debug("ImpressionHandler buffer failed, direct write: %s", exc)
            self._direct_write(network_key, data)

    @staticmethod
    def _direct_write(network_key: str, data: dict) -> None:
        try:
            from ..models import Impression, AdNetworkConfig
            network = AdNetworkConfig.objects.get_by_key(network_key)
            if network:
                Impression.objects.create(
                    tenant=network.tenant,
                    network=network,
                    offer_id=data.get("offer_id", ""),
                    ip_address=data.get("ip") or None,
                    user_agent=data.get("ua", ""),
                    placement=data.get("placement", ""),
                    country=data.get("country", ""),
                )
        except Exception:
            pass


# Module-level singleton
impression_handler = ImpressionHandler()
