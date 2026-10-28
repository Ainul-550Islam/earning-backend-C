# api/cms/tasks/media_cleanup_tasks.py
"""Delete orphaned media files task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.delete_orphaned_media', bind=True)
def delete_orphaned_media(self, days_unused: int = 30):
    """Delete media files not used anywhere in last N days."""
    try:
        from api.cms.services_new.MediaService import MediaService
        count = MediaService.delete_orphaned_files(days_unused=days_unused)
        logger.info(f"[Task] Deleted {count} orphaned media files")
        return {'status': 'success', 'deleted': count}
    except Exception as exc:
        logger.error(f"[Task] Orphaned media cleanup failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name='cms.tasks.update_folder_stats', bind=True)
def update_folder_stats(self):
    """Update file count and total size for all media folders."""
    try:
        from api.cms.models_new.media import MediaFolder
        folders = MediaFolder.objects.filter(is_active=True)
        for folder in folders:
            folder.update_stats()
        logger.info(f"[Task] Updated stats for {folders.count()} media folders")
        return {'status': 'success', 'folders': folders.count()}
    except Exception as exc:
        logger.error(f"[Task] Folder stats update failed: {exc}", exc_info=True)
        raise
