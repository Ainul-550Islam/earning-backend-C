"""
api/adapters/postback.py
Postback routing adapter — dispatches incoming S2S postbacks to the
correct platform Celery task based on the 'platform' query param.
Used by the generic /postback/ endpoint in urls.py.
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)

PLATFORM_TASK_MAP = {
    'cpalead':    'tasks.cpalead_tasks.cpalead_process_postback',
    'ogads':      'tasks.tasks_platform_extensions.ogads_process_postback',
    'adgate':     'tasks.tasks_platform_extensions.adgate_process_postback',
    'offertoro':  'tasks.tasks_platform_extensions.offertoro_process_postback',
    'monlix':     'tasks.tasks_platform_extensions.monlix_process_postback',
}

def route_postback(platform: str, data: dict) -> Optional[dict]:
    """Route postback data to the correct platform task."""
    from celery import current_app
    task_path = PLATFORM_TASK_MAP.get(platform.lower())
    if not task_path:
        logger.warning('[Postback] Unknown platform: %s', platform)
        return None
    result = current_app.send_task(task_path, args=[data])
    return {'task_id': str(result.id), 'platform': platform, 'status': 'queued'}
