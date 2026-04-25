# api/payment_gateways/smartlink/SmartRouter.py
# SmartLink routing engine — selects best offer per visitor

import random
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SmartRouter:
    """Routes incoming traffic to the best offer via SmartLink."""

    CACHE_TTL = 120  # 2 min cache per visitor profile

    def route(self, smart_link, country: str, device: str,
              os_name: str = '', ip: str = '') -> dict:
        """
        Select best offer for this visitor and return redirect URL.

        Returns:
            dict: {
                'offer': Offer | None,
                'redirect_url': str,
                'click_id': str,
                'used_fallback': bool,
            }
        """
        from .models import SmartLink, SmartLinkRotation
        from api.payment_gateways.blacklist.BlacklistEngine import BlacklistEngine

        # Get candidate offers
        candidates = self._get_candidates(smart_link, country, device)

        if not candidates:
            logger.info(f'SmartLink {smart_link.slug}: no candidates → fallback')
            return {
                'offer':        None,
                'redirect_url': smart_link.fallback_url or 'https://yourdomain.com',
                'click_id':     '',
                'used_fallback': True,
            }

        # Select based on rotation mode
        mode = smart_link.rotation_mode
        if mode == 'epc_optimized':
            winner = self._select_by_epc(candidates, country, device)
        elif mode == 'round_robin':
            winner = self._select_round_robin(smart_link, candidates)
        elif mode in ('weighted', 'ab_test'):
            winner = self._select_weighted(smart_link, candidates)
        elif mode == 'ctr_optimized':
            winner = self._select_by_ctr(candidates)
        else:
            winner = candidates[0] if candidates else None

        if not winner:
            return {
                'offer':        None,
                'redirect_url': smart_link.fallback_url or '',
                'click_id':     '',
                'used_fallback': True,
            }

        # Build redirect URL with click tracking
        redirect_url = self._build_url(winner, smart_link.publisher, country, device, ip)

        # Update click count
        from api.payment_gateways.smartlink.models import SmartLink as SL
        SL.objects.filter(id=smart_link.id).update(
            total_clicks=smart_link.total_clicks + 1
        )

        logger.info(f'SmartLink {smart_link.slug}: routed to offer {winner.id} [{winner.name}]')
        return {
            'offer':        winner,
            'redirect_url': redirect_url,
            'click_id':     '',
            'used_fallback': False,
        }

    def _get_candidates(self, smart_link, country: str, device: str) -> list:
        """Get eligible offers for this SmartLink + visitor profile."""
        from offers.models import Offer
        from django.db.models import Q

        # Start with manual offers if specified
        if smart_link.manual_offers.exists():
            qs = smart_link.manual_offers.filter(status='active')
        else:
            qs = Offer.objects.filter(status='active')

        # Apply SmartLink filters
        if smart_link.offer_types:
            qs = qs.filter(offer_type__in=smart_link.offer_types)
        if smart_link.categories:
            qs = qs.filter(category__in=smart_link.categories)
        if smart_link.min_payout:
            qs = qs.filter(publisher_payout__gte=smart_link.min_payout)
        if smart_link.target_countries:
            qs = qs.filter(
                Q(target_countries=[]) | Q(target_countries__contains=[country])
            )
        if smart_link.target_devices:
            qs = qs.filter(
                Q(target_devices=[]) | Q(target_devices__contains=[device])
            )

        # Exclude blocked countries per offer
        if country:
            qs = qs.exclude(blocked_countries__contains=[country])

        # Only offers the publisher is allowed to run
        qs = qs.filter(
            Q(is_public=True) | Q(allowed_publishers=smart_link.publisher)
        ).exclude(blocked_publishers=smart_link.publisher)

        return list(qs[:50])

    def _select_by_epc(self, candidates: list, country: str, device: str) -> object:
        """Select offer with highest EPC (earnings per click)."""
        if not candidates:
            return None

        def score(offer):
            epc = float(offer.epc or 0)
            if epc == 0:
                epc = float(offer.publisher_payout) * 0.05  # Estimate 5% CR

            # Bonus for exact GEO match
            geo_bonus = 1.2 if country and country in (offer.target_countries or []) else 1.0
            # Bonus for exact device match
            dev_bonus = 1.1 if device and device in (offer.target_devices or []) else 1.0

            return epc * geo_bonus * dev_bonus

        return max(candidates, key=score)

    def _select_round_robin(self, smart_link, candidates: list) -> object:
        """Round-robin distribution."""
        cache_key = f'rr:{smart_link.id}'
        idx = cache.get(cache_key, 0)
        offer = candidates[idx % len(candidates)]
        cache.set(cache_key, idx + 1, 86400)
        return offer

    def _select_weighted(self, smart_link, candidates: list) -> object:
        """Weighted random selection."""
        from .models import SmartLinkRotation
        rotations = SmartLinkRotation.objects.filter(smart_link=smart_link)
        rotation_map = {r.offer_id: r.weight for r in rotations}

        weights = []
        offers  = []
        for c in candidates:
            w = rotation_map.get(c.id, 50)
            weights.append(w)
            offers.append(c)

        if not offers:
            return candidates[0] if candidates else None

        total = sum(weights)
        rand  = random.random() * total
        running = 0
        for offer, w in zip(offers, weights):
            running += w
            if rand <= running:
                return offer
        return offers[-1]

    def _select_by_ctr(self, candidates: list) -> object:
        """Select highest CTR offer."""
        def ctr(o):
            clicks = o.total_clicks or 1
            return o.total_conversions / clicks
        return max(candidates, key=ctr)

    def _build_url(self, offer, publisher, country, device, ip) -> str:
        """Build redirect URL with click tracking."""
        from api.payment_gateways.tracking.ClickTracker import ClickTracker

        class _FakeRequest:
            META = {'REMOTE_ADDR': ip, 'HTTP_USER_AGENT': ''}

        tracker = ClickTracker()
        try:
            click, url = tracker.track(
                offer=offer, publisher=publisher,
                request=_FakeRequest(),
                extra_params={'sub1': 'smartlink', 'country': country, 'device': device}
            )
            return url
        except Exception:
            return getattr(offer, 'destination_url', '#')
