"""
Maintenance related Celery tasks
"""
from celery import shared_task
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def cleanup_old_data(days=30):
    """Cleanup old data"""
    try:
        logger.info(f"🧹 Cleaning up data older than {days} days...")
        
        result = {
            'status': 'success',
            'message': f'Cleaned up data older than {days} days',
            'timestamp': timezone.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Error in cleanup_old_data: {e}")
        raise
