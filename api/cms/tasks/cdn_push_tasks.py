# api/cms/tasks/cdn_push_tasks.py
"""Push media files to CDN."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.push_file_to_cdn', bind=True, max_retries=3)
def push_file_to_cdn(self, file_id: int):
    """Push a single media file to CDN."""
    try:
        from api.cms.models_new.media import MediaFile
        from api.cms.services_new.MediaService import MediaService
        media_file = MediaFile.objects.get(id=file_id)
        if media_file.cdn_url:
            return {'status': 'skipped', 'reason': 'Already on CDN'}
        success = MediaService.push_to_cdn(media_file)
        if success:
            logger.info(f"[Task] File {file_id} pushed to CDN: {media_file.cdn_url}")
            return {'status': 'success', 'cdn_url': media_file.cdn_url}
        return {'status': 'failed'}
    except Exception as exc:
        logger.error(f"[Task] CDN push failed for file {file_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)


@shared_task(name='cms.tasks.push_all_unpushed_to_cdn', bind=True)
def push_all_unpushed_to_cdn(self):
    """Push all media files not yet on CDN."""
    try:
        from api.cms.models_new.media import MediaFile
        from api.cms.services_new.MediaService import MediaService
        files = MediaFile.objects.filter(is_active=True, cdn_url='')
        count = 0
        for f in files:
            if MediaService.push_to_cdn(f):
                count += 1
        logger.info(f"[Task] Pushed {count} files to CDN")
        return {'status': 'success', 'pushed': count}
    except Exception as exc:
        logger.error(f"[Task] Bulk CDN push failed: {exc}", exc_info=True)
        raise
