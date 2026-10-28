# api/cms/services/RedirectService.py
"""
RedirectService: 301 redirect management, bulk import, cleanup.
"""
import logging
from typing import List, Dict, Optional, Tuple, Any

from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RedirectService:
    """Service for managing 301/302 redirects."""

    @staticmethod
    def find(from_url: str) -> Optional[Any]:
        """Find active redirect for URL."""
        from api.cms.models_new.seo import Redirect301
        return Redirect301.find_redirect(from_url)

    @staticmethod
    def create(from_url: str, to_url: str, redirect_type: int = 301, user=None, notes: str = '') -> Optional[Any]:
        """Create a new redirect."""
        from api.cms.models_new.seo import Redirect301
        try:
            redirect, _ = Redirect301.objects.update_or_create(
                from_url=from_url,
                defaults={
                    'to_url': to_url,
                    'redirect_type': redirect_type,
                    'is_active': True,
                    'created_by': user,
                    'notes': notes,
                }
            )
            cache.delete(f'redirect_{from_url}')
            return redirect
        except Exception as e:
            logger.error(f"Error creating redirect: {e}", exc_info=True)
            return None

    @staticmethod
    def delete_redirect(redirect) -> bool:
        """Delete a redirect."""
        try:
            from_url = redirect.from_url
            redirect.delete()
            cache.delete(f'redirect_{from_url}')
            return True
        except Exception as e:
            logger.error(f"Error deleting redirect: {e}", exc_info=True)
            return False

    @staticmethod
    def bulk_import_csv(csv_content: str, user=None) -> Tuple[int, List[str]]:
        """Bulk import redirects from CSV."""
        from api.cms.models_new.seo import Redirect301
        return Redirect301.bulk_create_from_csv(csv_content, user=user)

    @staticmethod
    def cleanup_unused(days: int = 90) -> int:
        """Remove redirects with no hits in last N days."""
        from api.cms.models_new.seo import Redirect301
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = Redirect301.objects.filter(
            hit_count=0, created_at__lt=cutoff
        ).delete()
        logger.info(f"Cleaned up {deleted} unused redirects")
        return deleted

    @staticmethod
    def cleanup_expired() -> int:
        """Deactivate expired redirects."""
        from api.cms.models_new.seo import Redirect301
        expired = Redirect301.objects.filter(
            expires_at__lt=timezone.now(), is_active=True
        )
        count = expired.update(is_active=False)
        logger.info(f"Deactivated {count} expired redirects")
        return count

    @staticmethod
    def record_hit(redirect) -> None:
        """Record a redirect hit."""
        redirect.record_hit()

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get redirect statistics."""
        from api.cms.models_new.seo import Redirect301
        from django.db.models import Sum, Count, Avg
        try:
            stats = Redirect301.objects.filter(is_active=True).aggregate(
                total=Count('id'),
                total_hits=Sum('hit_count'),
                avg_hits=Avg('hit_count'),
            )
            top_redirects = list(
                Redirect301.objects.filter(is_active=True)
                .order_by('-hit_count')[:10]
                .values('from_url', 'to_url', 'hit_count', 'redirect_type')
            )
            return {
                'total_redirects': stats['total'] or 0,
                'total_hits': stats['total_hits'] or 0,
                'avg_hits': round(stats['avg_hits'] or 0, 1),
                'top_redirects': top_redirects,
            }
        except Exception as e:
            logger.error(f"Error getting redirect statistics: {e}", exc_info=True)
            return {}
