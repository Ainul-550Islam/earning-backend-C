# api/offer_inventory/maintenance_logs/clean_up_service.py
"""Cleanup Service — Periodic removal of expired/stale platform data."""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class CleanupService:
    """Periodic cleanup of old and expired DB records."""

    @classmethod
    def run_all(cls, dry_run: bool = False) -> dict:
        """Run all cleanup tasks. dry_run=True counts without deleting."""
        results = {}
        tasks   = [
            ('expired_ip_blocks',  cls._cleanup_expired_ip_blocks),
            ('pixel_logs',         cls._cleanup_pixel_logs),
            ('expired_cache_objs', cls._cleanup_cache_objects),
            ('old_impressions',    cls._cleanup_old_impressions),
            ('expired_schedules',  cls._cleanup_old_schedules),
        ]
        for name, fn in tasks:
            try:
                results[name] = fn(dry_run)
            except Exception as e:
                results[name] = f'error: {e}'
                logger.error(f'Cleanup task {name} error: {e}')

        total = sum(v for v in results.values() if isinstance(v, int))
        logger.info(f'Cleanup {"(dry-run) " if dry_run else ""}complete: {total} records')
        return {'results': results, 'total': total, 'dry_run': dry_run}

    @staticmethod
    def _cleanup_expired_ip_blocks(dry_run: bool) -> int:
        from api.offer_inventory.models import BlacklistedIP
        qs    = BlacklistedIP.objects.filter(
            is_permanent=False, expires_at__lt=timezone.now()
        )
        count = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _cleanup_pixel_logs(dry_run: bool) -> int:
        from api.offer_inventory.models import PixelLog
        cutoff = timezone.now() - timedelta(days=30)
        qs     = PixelLog.objects.filter(is_fired=True, created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _cleanup_cache_objects(dry_run: bool) -> int:
        from api.offer_inventory.models import CacheObject
        qs    = CacheObject.objects.filter(expires_at__lt=timezone.now())
        count = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _cleanup_old_impressions(dry_run: bool) -> int:
        from api.offer_inventory.models import Impression
        cutoff = timezone.now() - timedelta(days=60)
        qs     = Impression.objects.filter(created_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def _cleanup_old_schedules(dry_run: bool) -> int:
        from api.offer_inventory.models import OfferSchedule
        cutoff = timezone.now() - timedelta(days=90)
        qs     = OfferSchedule.objects.filter(is_executed=True, executed_at__lt=cutoff)
        count  = qs.count()
        if not dry_run:
            qs.delete()
        return count

    @staticmethod
    def get_cleanup_preview() -> dict:
        """Preview what would be deleted without actually deleting."""
        return CleanupService.run_all(dry_run=True)
