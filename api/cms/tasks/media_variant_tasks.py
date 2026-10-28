# api/cms/tasks/media_variant_tasks.py
"""Async image resize and variant generation task."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='cms.tasks.generate_media_variants', bind=True, max_retries=3)
def generate_media_variants(self, file_id: int):
    """Generate all image variants for a media file."""
    try:
        from api.cms.models_new.media import MediaFile
        from api.cms.services_new.MediaVariantService import MediaVariantService
        media_file = MediaFile.objects.get(id=file_id)
        results = MediaVariantService.generate_all_variants(media_file)
        logger.info(f"[Task] Variants generated for file {file_id}: {results}")
        return {'status': 'success', 'file_id': file_id, 'results': results}
    except Exception as exc:
        logger.error(f"[Task] Variant generation failed for file {file_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='cms.tasks.regenerate_missing_variants', bind=True)
def regenerate_missing_variants(self):
    """Regenerate missing variants for all image files."""
    try:
        from api.cms.services_new.MediaVariantService import MediaVariantService
        stats = MediaVariantService.regenerate_missing_variants()
        logger.info(f"[Task] Missing variants regenerated: {stats}")
        return {'status': 'success', **stats}
    except Exception as exc:
        logger.error(f"[Task] Missing variant regeneration failed: {exc}", exc_info=True)
        raise
