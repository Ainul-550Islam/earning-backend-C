"""tasks/session_tasks.py — User session management."""
import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=15,
             name='tasks.session_tasks.create_user_session')
def create_user_session(self, user_id: int, ip: str, user_agent: str, device: str = 'unknown') -> dict:
    """Create/refresh a user session record and sync DataBridge."""
    try:
        session_key = f'session_user_{user_id}'
        session_data = {
            'user_id': user_id, 'ip': ip, 'device': device,
            'user_agent': user_agent[:200], 'started_at': timezone.now().isoformat(),
        }
        cache.set(session_key, session_data, timeout=86400)

        # Sync full user data to DataBridge on login
        from api.tasks.data_pipeline_tasks import sync_user_data_bridge
        sync_user_data_bridge.apply_async(kwargs={'user_ids': [user_id]})

        return {'status': 'success', 'user_id': user_id, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.session_tasks.cleanup_expired_sessions')
def cleanup_expired_sessions(self) -> dict:
    """Purge expired session records from DB."""
    try:
        deleted = 0
        try:
            from django.contrib.sessions.models import Session
            deleted, _ = Session.objects.filter(expire_date__lt=timezone.now()).delete()
        except Exception:
            pass
        return {'status': 'success', 'deleted': deleted, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=10,
             name='tasks.session_tasks.track_user_activity')
def track_user_activity(self, user_id: int, action: str, metadata: dict = None) -> dict:
    """Track user activity for analytics and re-engagement scoring."""
    try:
        activity_key = f'last_activity_{user_id}'
        cache.set(activity_key, {
            'action': action, 'metadata': metadata or {},
            'at': timezone.now().isoformat(),
        }, timeout=86400 * 7)
        return {'status': 'success', 'user_id': user_id, 'action': action}
    except Exception as exc:
        raise self.retry(exc=exc)
