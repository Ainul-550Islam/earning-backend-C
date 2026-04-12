"""Redis Publisher — publishes IP risk events to Redis pub/sub channels."""
import logging, json
from django.core.cache import cache
logger = logging.getLogger(__name__)

CHANNEL_HIGH_RISK   = 'pi:high_risk'
CHANNEL_FRAUD       = 'pi:fraud'
CHANNEL_BLACKLIST   = 'pi:blacklist'

class RedisPublisher:
    """
    Publishes real-time events to Redis pub/sub.
    Requires redis-py: pip install redis
    """
    @staticmethod
    def _get_client():
        try:
            import redis
            from django.conf import settings
            url = getattr(settings,'REDIS_URL','redis://localhost:6379/0')
            return redis.from_url(url)
        except Exception as e:
            logger.debug(f"Redis connection failed: {e}")
            return None

    @classmethod
    def publish_high_risk(cls, ip_address: str, risk_score: int, flags: list):
        client = cls._get_client()
        if not client: return
        try:
            client.publish(CHANNEL_HIGH_RISK, json.dumps({
                'ip_address': ip_address, 'risk_score': risk_score, 'flags': flags
            }))
        except Exception as e:
            logger.debug(f"Redis publish failed: {e}")

    @classmethod
    def publish_fraud(cls, ip_address: str, fraud_type: str, user_id: int = None):
        client = cls._get_client()
        if not client: return
        try:
            client.publish(CHANNEL_FRAUD, json.dumps({
                'ip_address': ip_address, 'fraud_type': fraud_type, 'user_id': user_id
            }))
        except Exception as e:
            logger.debug(f"Redis publish failed: {e}")

    @classmethod
    def publish_blacklist(cls, ip_address: str, reason: str):
        client = cls._get_client()
        if not client: return
        try:
            client.publish(CHANNEL_BLACKLIST, json.dumps({
                'ip_address': ip_address, 'reason': reason
            }))
        except Exception as e:
            logger.debug(f"Redis publish failed: {e}")
