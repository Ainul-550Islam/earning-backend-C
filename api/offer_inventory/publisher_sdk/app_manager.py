# api/offer_inventory/publisher_sdk/app_manager.py
"""App Manager — Manage publisher app registrations and placements."""
import logging
import secrets
from django.db import transaction

logger = logging.getLogger(__name__)


class AppManager:
    """Manage publisher apps and ad placements."""

    @staticmethod
    @transaction.atomic
    def register_app(publisher_id: str, app_name: str,
                      platform: str = 'android', bundle_id: str = '',
                      category: str = '') -> dict:
        """Register a new app for a publisher."""
        from api.offer_inventory.models import PublisherApp

        app = PublisherApp.objects.create(
            publisher_id=publisher_id,
            name        =app_name,
            platform    =platform,
            bundle_id   =bundle_id,
            category    =category,
            app_key     =f'app_{secrets.token_urlsafe(16)}',
            status      ='pending',
        )
        logger.info(f'App registered: {app_name} ({platform}) for publisher={publisher_id}')
        return {
            'app_id'  : str(app.id),
            'app_key' : app.app_key,
            'platform': platform,
            'status'  : 'pending_review',
        }

    @staticmethod
    def get_publisher_apps(publisher_id: str) -> list:
        """List all apps for a publisher."""
        from api.offer_inventory.models import PublisherApp
        return list(
            PublisherApp.objects.filter(publisher_id=publisher_id)
            .values('id', 'name', 'platform', 'bundle_id', 'status', 'app_key')
            .order_by('-created_at')
        )

    @staticmethod
    def create_placement(app_id: str, placement_name: str,
                          placement_type: str = 'offerwall',
                          position: str = 'main_menu') -> dict:
        """Create an ad placement within an app."""
        from api.offer_inventory.models import AppPlacement

        placement = AppPlacement.objects.create(
            app_id          =app_id,
            name            =placement_name,
            placement_type  =placement_type,
            position        =position,
            placement_id    =f'pl_{secrets.token_urlsafe(8)}',
            is_active       =True,
        )
        return {
            'placement_id': str(placement.id),
            'placement_key': placement.placement_id,
        }

    @staticmethod
    def get_app_performance(app_id: str, days: int = 30) -> dict:
        """Performance stats for a specific app."""
        from api.offer_inventory.models import BidLog
        from django.db.models import Count, Avg
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        agg   = BidLog.objects.filter(
            publisher_id=app_id, created_at__gte=since
        ).aggregate(
            requests=Count('id'),
            wins    =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_won=True)),
            avg_ecpm=Avg('ecpm'),
        )
        return {
            'app_id'      : app_id,
            'bid_requests': agg['requests'] or 0,
            'wins'        : agg['wins'] or 0,
            'fill_rate'   : round((agg['wins'] or 0) / max(agg['requests'] or 1, 1) * 100, 1),
            'avg_ecpm'    : round(float(agg['avg_ecpm'] or 0), 4),
            'days'        : days,
        }
