# api/payment_gateways/rate_limiting.py
# Advanced rate limiting per user/IP/gateway
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle
import time, logging
logger = logging.getLogger(__name__)

class PaymentRateLimiter:
    LIMITS = {
        'deposit':      {'count': 10, 'window': 3600},
        'withdrawal':   {'count': 3,  'window': 3600},
        'postback':     {'count': 1000,'window': 60},
        'api':          {'count': 500, 'window': 3600},
        'conversion':   {'count': 100, 'window': 60},
        'smartlink':    {'count': 10000,'window': 3600},
    }
    def check(self, key, operation='api'):
        cfg = self.LIMITS.get(operation, {'count':100,'window':3600})
        cache_key = f"rl:{operation}:{key}"
        count = cache.get(cache_key, 0)
        if count >= cfg['count']:
            return False, count, cfg['count']
        try:
            from django_redis import get_redis_connection
            conn = get_redis_connection('default')
            new_count = conn.incr(cache_key)
            if new_count == 1: conn.expire(cache_key, cfg['window'])
            return new_count <= cfg['count'], new_count, cfg['count']
        except:
            new_count = count + 1
            cache.set(cache_key, new_count, cfg['window'])
            return new_count <= cfg['count'], new_count, cfg['count']
    def is_ip_blocked(self, ip):
        return bool(cache.get(f"ip_block:{ip}"))
    def block_ip(self, ip, duration=3600, reason=''):
        cache.set(f"ip_block:{ip}", {'reason':reason,'at':time.time()}, duration)
        logger.warning(f"IP blocked: {ip} reason={reason}")
    def get_limits_for_user(self, user):
        return {op: self.check(f"user:{user.id}", op) for op in self.LIMITS}
rate_limiter = PaymentRateLimiter()
