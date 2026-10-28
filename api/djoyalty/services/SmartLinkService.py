# api/djoyalty/services/SmartLinkService.py
"""
SmartLink Service -- CPAlead-style geo-targeted short URL service।
Create, track, and route SmartLinks।
"""
import logging
import secrets
import string
from django.utils import timezone

logger = logging.getLogger(__name__)


class SmartLinkService:
    """
    SmartLink management -- create, track clicks, geo-route।

    Usage:
        link = SmartLinkService.create(customer, name='Summer Offer', default_url='https://...')
        destination = SmartLinkService.resolve(slug='ABC123', country='BD', device='android')
        SmartLinkService.record_click(slug='ABC123', ip='1.2.3.4', country='BD')
    """

    @staticmethod
    def create(customer=None, tenant=None, name: str = '',
                default_url: str = '', geo_rules: list = None,
                linked_offer_id: int = None,
                linked_campaign_id: int = None,
                slug: str = '') -> object:
        """Create a new SmartLink।"""
        from ..models.catalog import SmartLink

        if not slug:
            while True:
                slug = ''.join(
                    secrets.choice(string.ascii_uppercase + string.digits)
                    for _ in range(8)
                )
                if not SmartLink.objects.filter(slug=slug).exists():
                    break

        link = SmartLink.objects.create(
            customer=customer,
            tenant=tenant or (customer.tenant if customer else None),
            slug=slug,
            name=name or f'SmartLink-{slug}',
            default_url=default_url,
            geo_rules=geo_rules or [],
        )

        if linked_offer_id:
            try:
                from ..models.offerwall import Offer
                link.linked_offer = Offer.objects.get(id=linked_offer_id)
                link.save(update_fields=['linked_offer'])
            except Exception:
                pass

        if linked_campaign_id:
            try:
                from ..models.campaigns import LoyaltyCampaign
                link.linked_campaign = LoyaltyCampaign.objects.get(id=linked_campaign_id)
                link.save(update_fields=['linked_campaign'])
            except Exception:
                pass

        logger.info('SmartLinkService.create: %s -> %s', slug, default_url)
        return link

    @staticmethod
    def resolve(slug: str, country: str = '', device: str = '') -> str:
        """
        Get destination URL for a SmartLink।
        Applies geo/device routing rules।
        """
        from ..models.catalog import SmartLink

        try:
            link = SmartLink.objects.get(slug=slug.upper(), is_active=True)

            # Check expiry
            if link.valid_until and timezone.now() > link.valid_until:
                return link.default_url

            return link.get_destination_url(country=country, device=device)
        except SmartLink.DoesNotExist:
            return ''

    @staticmethod
    def record_click(slug: str, ip_address: str = '',
                      country_code: str = '', device_type: str = '',
                      user_agent: str = '') -> bool:
        """Record a SmartLink click।"""
        from ..models.catalog import SmartLink, SmartLinkClick

        try:
            link = SmartLink.objects.get(slug=slug.upper(), is_active=True)

            # Check uniqueness
            is_unique = not SmartLinkClick.objects.filter(
                smart_link=link, ip_address=ip_address
            ).exists()

            destination = link.get_destination_url(country=country_code, device=device_type)
            SmartLinkClick.objects.create(
                smart_link=link,
                ip_address=ip_address or None,
                country_code=country_code,
                device_type=device_type,
                user_agent=user_agent[:500],
                destination_url=destination,
                is_unique=is_unique,
            )

            # Update counters
            link.total_clicks += 1
            if is_unique:
                link.unique_clicks += 1
            link.save(update_fields=['total_clicks', 'unique_clicks'])

            return True
        except SmartLink.DoesNotExist:
            logger.warning('SmartLinkService.record_click: slug %s not found', slug)
            return False

    @staticmethod
    def get_stats(slug: str) -> dict:
        """Get click stats for a SmartLink।"""
        from ..models.catalog import SmartLink

        try:
            link = SmartLink.objects.get(slug=slug.upper())
            return {
                'slug': link.slug,
                'name': link.name,
                'total_clicks': link.total_clicks,
                'unique_clicks': link.unique_clicks,
                'total_conversions': link.total_conversions,
                'created_at': link.created_at.isoformat(),
            }
        except SmartLink.DoesNotExist:
            return {}
