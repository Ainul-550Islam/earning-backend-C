"""
api/adapters/payout_queue.py
Payout queue adapter — batches user reward credits and drains them safely.
Uses Redis sorted set keyed by scheduled_at timestamp.
"""
import logging, time
from decimal import Decimal
logger = logging.getLogger(__name__)
QUEUE_KEY = 'payout_queue:pending'

def enqueue(user_id: int, amount: Decimal, task_id: int, platform: str = '') -> bool:
    try:
        from django.core.cache import cache
        from django.utils import timezone
        score = int(time.time())
        import json
        payload = json.dumps({'user_id': user_id, 'amount': str(amount),
                              'task_id': task_id, 'platform': platform,
                              'queued_at': timezone.now().isoformat()})
        # Use sorted set via Redis client if available
        r = _get_redis()
        if r:
            r.zadd(QUEUE_KEY, {payload: score})
        else:
            # Fallback: process immediately via Celery task
            from api.tasks.earning_tasks import process_user_earning
            process_user_earning.delay(user_id=user_id, amount=str(amount), task_id=task_id)
        return True
    except Exception as e:
        logger.error('[PayoutQueue] enqueue error: %s', e)
        return False

def drain(batch_size: int = 100) -> int:
    """Process up to batch_size pending payouts. Called by a periodic Celery beat task."""
    r = _get_redis()
    if not r:
        return 0
    import json
    items = r.zrange(QUEUE_KEY, 0, batch_size - 1, withscores=False)
    processed = 0
    for raw in items:
        try:
            data = json.loads(raw)
            from api.tasks.earning_tasks import process_user_earning
            process_user_earning.delay(**{k: v for k, v in data.items() if k != 'queued_at'})
            r.zrem(QUEUE_KEY, raw)
            processed += 1
        except Exception as e:
            logger.error('[PayoutQueue] drain item error: %s', e)
    return processed

def _get_redis():
    try:
        from django.core.cache import caches
        return caches['default'].client.get_client()
    except Exception:
        return None
