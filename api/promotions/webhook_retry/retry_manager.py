# =============================================================================
# promotions/webhook_retry/retry_manager.py
# Auto-retry failed postbacks with exponential backoff
# =============================================================================
from django.utils import timezone
from django.core.cache import cache
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAYS = [60, 300, 900, 3600, 21600]  # 1m, 5m, 15m, 1h, 6h


class WebhookRetryManager:
    def schedule_retry(self, webhook_id: str, url: str, payload: dict,
                        attempt: int = 1) -> dict:
        if attempt > MAX_RETRIES:
            logger.warning(f'Webhook {webhook_id} max retries exceeded')
            return {'scheduled': False, 'reason': 'max_retries'}
        delay = RETRY_DELAYS[attempt - 1]
        retry_record = {
            'webhook_id': webhook_id, 'url': url, 'payload': payload,
            'attempt': attempt, 'next_retry': timezone.now().isoformat(),
            'status': 'scheduled',
        }
        cache.set(f'webhook_retry:{webhook_id}:{attempt}', retry_record, timeout=delay * 2 + 3600)
        retry_webhook.apply_async(
            args=[webhook_id, url, payload, attempt],
            countdown=delay,
        )
        return {'scheduled': True, 'attempt': attempt, 'retry_in_seconds': delay}

    def get_retry_status(self, webhook_id: str) -> dict:
        retries = []
        for i in range(1, MAX_RETRIES + 1):
            r = cache.get(f'webhook_retry:{webhook_id}:{i}')
            if r: retries.append(r)
        return {'webhook_id': webhook_id, 'retries': retries}


@shared_task(bind=True, max_retries=5)
def retry_webhook(self, webhook_id: str, url: str, payload: dict, attempt: int):
    import urllib.request, json
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={'Content-Type': 'application/json', 'User-Agent': 'YourPlatform-Webhook/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201, 204):
                logger.info(f'Webhook retry succeeded: {webhook_id} attempt {attempt}')
                return {'success': True, 'attempt': attempt}
            raise Exception(f'HTTP {resp.status}')
    except Exception as e:
        logger.error(f'Webhook retry failed: {webhook_id} attempt {attempt}: {e}')
        mgr = WebhookRetryManager()
        mgr.schedule_retry(webhook_id, url, payload, attempt + 1)
        return {'success': False, 'attempt': attempt, 'error': str(e)}
