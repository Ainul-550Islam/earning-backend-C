"""tasks/rate_limit_tasks.py — API rate limiting and throttle management."""
import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Rate limit configs per endpoint type
RATE_LIMITS = {
    'api_general':   {'limit': 1000, 'window': 3600},   # 1000/hour
    'postback':      {'limit': 10000, 'window': 3600},  # 10K/hour
    'withdrawal':    {'limit': 5,    'window': 86400},  # 5/day
    'login':         {'limit': 10,   'window': 900},    # 10/15min
    'offer_click':   {'limit': 100,  'window': 3600},   # 100 clicks/hour
    'survey_submit': {'limit': 20,   'window': 3600},   # 20 survey submits/hour
}


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.rate_limit_tasks.check_rate_limit')
def check_rate_limit(self, identifier: str, endpoint_type: str = 'api_general') -> dict:
    """Check if an identifier (user_id or IP) has exceeded the rate limit."""
    try:
        config    = RATE_LIMITS.get(endpoint_type, RATE_LIMITS['api_general'])
        limit     = config['limit']
        window    = config['window']
        key       = f'rl_{endpoint_type}_{identifier}'
        count     = cache.get(key, 0)
        exceeded  = count >= limit

        if not exceeded:
            cache.set(key, count + 1, timeout=window)

        return {
            'status': 'exceeded' if exceeded else 'ok',
            'identifier': identifier,
            'endpoint_type': endpoint_type,
            'count': count,
            'limit': limit,
            'window_seconds': window,
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=60,
             name='tasks.rate_limit_tasks.cleanup_expired_rate_limits')
def cleanup_expired_rate_limits(self) -> dict:
    """Rate limit keys auto-expire from Redis. Just log summary."""
    logger.info("[RATE_LIMIT] Cache-based rate limits auto-expire. No cleanup needed.")
    return {'status': 'success', 'message': 'Rate limits are TTL-managed by Redis', 'timestamp': timezone.now().isoformat()}


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.rate_limit_tasks.update_rate_limit_configs')
def update_rate_limit_configs(self, new_configs: dict = None) -> dict:
    """Update rate limit thresholds and cache them."""
    try:
        if new_configs:
            RATE_LIMITS.update(new_configs)
            cache.set('rate_limit_configs', RATE_LIMITS, timeout=None)
        return {'status': 'success', 'configs': RATE_LIMITS, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)
