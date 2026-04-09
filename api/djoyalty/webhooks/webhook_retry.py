# api/djoyalty/webhooks/webhook_retry.py
"""Exponential backoff retry for webhook delivery।"""
import logging
import time
from ..constants import WEBHOOK_MAX_RETRIES, WEBHOOK_RETRY_BACKOFF_SECONDS

logger = logging.getLogger(__name__)

def deliver_with_retry(url: str, payload: dict, headers: dict = None) -> bool:
    import urllib.request
    import json
    data = json.dumps(payload).encode('utf-8')
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)
    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=data, headers=req_headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    return True
        except Exception as e:
            logger.warning('Webhook attempt %d failed for %s: %s', attempt + 1, url, e)
            if attempt < WEBHOOK_MAX_RETRIES - 1:
                backoff = WEBHOOK_RETRY_BACKOFF_SECONDS[attempt] if attempt < len(WEBHOOK_RETRY_BACKOFF_SECONDS) else 900
                time.sleep(backoff)
    return False
