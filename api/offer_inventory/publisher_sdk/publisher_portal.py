# api/offer_inventory/publisher_sdk/publisher_portal.py
"""
Publisher Portal — Self-serve dashboard for app publishers.
Publishers embed offerwall in their apps and earn revenue share.
"""
import logging
import secrets
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Publisher revenue share (publisher gets X% of platform revenue)
PUBLISHER_REVENUE_SHARE_PCT = Decimal('30')


class PublisherPortal:
    """Full publisher lifecycle management."""

    @staticmethod
    @transaction.atomic
    def register_publisher(company_name: str, contact_email: str,
                            website: str = '', app_type: str = 'mobile',
                            tenant=None) -> dict:
        """Register a new publisher."""
        from api.offer_inventory.models import Publisher

        publisher = Publisher.objects.create(
            company_name    =company_name,
            contact_email   =contact_email,
            website         =website,
            app_type        =app_type,
            revenue_share   =PUBLISHER_REVENUE_SHARE_PCT,
            api_key         =f'pub_{secrets.token_urlsafe(32)}',
            tenant          =tenant,
            status          ='pending',
        )
        logger.info(f'Publisher registered: {company_name}')
        return {
            'publisher_id': str(publisher.id),
            'api_key'     : publisher.api_key,
            'status'      : 'pending_review',
            'message'     : 'Your publisher account is under review. Approval within 24h.',
        }

    @staticmethod
    def approve_publisher(publisher_id: str, reviewer=None) -> bool:
        """Approve a publisher account."""
        from api.offer_inventory.models import Publisher
        updated = Publisher.objects.filter(id=publisher_id).update(
            status     ='active',
            approved_at=timezone.now(),
            approved_by=reviewer,
        )
        logger.info(f'Publisher approved: {publisher_id}')
        return updated > 0

    @staticmethod
    def get_dashboard(publisher_id: str, days: int = 30) -> dict:
        """Full publisher dashboard data."""
        from api.offer_inventory.publisher_sdk.publisher_analytics import PublisherAnalytics
        return PublisherAnalytics.get_full_report(publisher_id, days=days)

    @staticmethod
    def rotate_api_key(publisher_id: str) -> str:
        """Generate a new API key for a publisher."""
        from api.offer_inventory.models import Publisher
        new_key = f'pub_{secrets.token_urlsafe(32)}'
        Publisher.objects.filter(id=publisher_id).update(api_key=new_key)
        return new_key

    @staticmethod
    def validate_api_key(api_key: str) -> dict:
        """Validate publisher API key and return publisher info."""
        from api.offer_inventory.models import Publisher
        from django.core.cache import cache

        cache_key = f'pub_key:{api_key}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        try:
            pub = Publisher.objects.get(api_key=api_key, status='active')
            result = {
                'publisher_id': str(pub.id),
                'company_name': pub.company_name,
                'revenue_share': float(pub.revenue_share),
                'valid'       : True,
            }
            cache.set(cache_key, result, 300)
            return result
        except Publisher.DoesNotExist:
            return {'valid': False, 'reason': 'invalid_api_key'}
