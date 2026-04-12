# api/offer_inventory/smart_link.py
"""
SmartLink Service Layer.
High-level service for creating, managing, and routing SmartLinks.
Delegates AI scoring to ai_optimization/smart_link_logic.py.
"""
import logging
from django.db.models import F
from django.utils.text import slugify
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SmartLinkService:
    """Full SmartLink lifecycle management."""

    @staticmethod
    def create(tenant, name: str, algorithm: str = 'ai_score',
               offer_ids: list = None, custom_params: dict = None) -> object:
        """Create a new SmartLink."""
        from api.offer_inventory.models import SmartLink, Offer
        import uuid

        slug   = slugify(name) + '-' + str(uuid.uuid4())[:6]
        link   = SmartLink.objects.create(
            tenant       =tenant,
            slug         =slug,
            algorithm    =algorithm,
            custom_params=custom_params or {},
        )
        if offer_ids:
            offers = Offer.objects.filter(id__in=offer_ids, status='active')
            link.offers.set(offers)

        logger.info(f'SmartLink created: {slug} algorithm={algorithm}')
        return link

    @staticmethod
    def resolve(slug: str, user=None, country: str = '',
                device: str = '', request_ip: str = '') -> dict:
        """
        Resolve a SmartLink to the best offer.
        Returns {'offer': Offer, 'redirect_url': str, 'click': Click} or None.
        """
        from api.offer_inventory.models import SmartLink
        from api.offer_inventory.ai_optimization.smart_link_logic import SmartLinkOptimizer
        from api.offer_inventory.models import RedirectLog

        try:
            link = SmartLink.objects.prefetch_related(
                'offers__caps', 'offers__visibility_rules'
            ).get(slug=slug, is_active=True)
        except SmartLink.DoesNotExist:
            logger.warning(f'SmartLink not found: {slug}')
            return None

        # Get active offers
        offers = list(link.offers.filter(status='active'))
        if not offers:
            return None

        # AI select best offer
        best = SmartLinkOptimizer.select_best_offer(
            offers   =offers,
            algorithm=link.algorithm,
            user     =user,
            country  =country,
            device   =device,
        )
        if not best:
            return None

        # Increment click count
        SmartLink.objects.filter(id=link.id).update(
            click_count=F('click_count') + 1
        )

        # Build redirect URL with tracking params
        redirect_url = SmartLinkService._build_url(best, user, request_ip)

        # Log redirect
        try:
            RedirectLog.objects.create(
                smart_link   =link,
                offer        =best,
                ip_address   =request_ip or '0.0.0.0',
                final_url    =redirect_url,
            )
        except Exception as e:
            logger.debug(f'RedirectLog error: {e}')

        return {
            'smart_link' : link,
            'offer'      : best,
            'redirect_url': redirect_url,
        }

    @staticmethod
    def _build_url(offer, user=None, ip: str = '') -> str:
        """Build final offer URL with tracking params."""
        import uuid
        base = offer.offer_url or ''
        sep  = '&' if '?' in base else '?'
        uid  = str(user.id) if user else 'anon'
        return f'{base}{sep}sl=1&uid={uid}&ip={ip}'

    @staticmethod
    def get_stats(slug: str) -> dict:
        """SmartLink performance stats."""
        from api.offer_inventory.models import SmartLink, RedirectLog
        from django.db.models import Count

        try:
            link = SmartLink.objects.get(slug=slug)
        except SmartLink.DoesNotExist:
            return {}

        offer_breakdown = list(
            RedirectLog.objects.filter(smart_link=link)
            .values('offer__title', 'offer_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        return {
            'slug'          : slug,
            'total_clicks'  : link.click_count,
            'algorithm'     : link.algorithm,
            'active_offers' : link.offers.filter(status='active').count(),
            'offer_breakdown': offer_breakdown,
        }

    @staticmethod
    def rotate_offer(link_id: str, remove_offer_id: str):
        """
        Remove a capped/expired offer from a SmartLink.
        The AI will automatically pick the next best.
        """
        from api.offer_inventory.models import SmartLink
        from api.offer_inventory.ai_optimization.smart_link_logic import CapRotationManager

        link  = SmartLink.objects.prefetch_related('offers').get(id=link_id)
        offer = link.offers.filter(id=remove_offer_id).first()
        if offer:
            CapRotationManager.invalidate_cap_cache(offer)
        logger.info(f'SmartLink {link.slug}: rotated away from offer {remove_offer_id}')

    @staticmethod
    def add_offer(link_id: str, offer_id: str):
        """Add an offer to a SmartLink."""
        from api.offer_inventory.models import SmartLink, Offer
        link  = SmartLink.objects.get(id=link_id)
        offer = Offer.objects.get(id=offer_id)
        link.offers.add(offer)

    @staticmethod
    def remove_offer(link_id: str, offer_id: str):
        """Remove an offer from a SmartLink."""
        from api.offer_inventory.models import SmartLink
        link = SmartLink.objects.get(id=link_id)
        link.offers.filter(id=offer_id).delete()
