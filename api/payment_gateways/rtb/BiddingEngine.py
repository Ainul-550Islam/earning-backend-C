# api/payment_gateways/rtb/BiddingEngine.py
# Real-time bidding engine — matches traffic to highest-paying offer
# CPAlead runs this for every publisher click to auto-optimize routing

import logging
from decimal import Decimal
from django.core.cache import cache
logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes


class BiddingEngine:
    """
    Real-time offer selection engine.

    Given a visitor's profile (country, device, OS, carrier),
    finds the BEST offer to show — highest EPC (earnings per click)
    that the visitor qualifies for.

    Features:
        - GEO targeting: match country to allowed countries
        - Device targeting: mobile / desktop / tablet
        - OS targeting: iOS / Android / Windows
        - Budget caps: skip offers over daily/monthly cap
        - Quality scoring: EPC * quality_score
        - Caching: results cached 5 min per traffic profile
    """

    def find_best_offer(self, publisher, country: str, device: str,
                        os_name: str = '', carrier: str = '',
                        offer_type: str = None, category: str = None) -> dict:
        """
        Find the best offer for this traffic profile.

        Args:
            publisher:   Publisher user object
            country:     ISO 2-letter country code (e.g. 'US', 'BD')
            device:      'mobile' | 'desktop' | 'tablet'
            os_name:     'iOS' | 'Android' | 'Windows' | ''
            carrier:     Mobile carrier name (optional)
            offer_type:  Filter by offer type (cpa/cpi/cpc/cpl)
            category:    Filter by category

        Returns:
            dict: {
                'offer': Offer | None,
                'bid':   Decimal,
                'alternatives': [Offer, ...],
            }
        """
        cache_key = f'rtb:{publisher.id}:{country}:{device}:{os_name}:{offer_type}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from offers.models import Offer
        from django.db.models import Q

        # Base queryset: active, public + allowed
        qs = Offer.objects.filter(
            status='active',
        ).filter(
            Q(is_public=True) | Q(allowed_publishers=publisher)
        ).exclude(
            blocked_publishers=publisher
        )

        # Filter by offer type
        if offer_type:
            qs = qs.filter(offer_type=offer_type)

        # Filter by category
        if category:
            qs = qs.filter(category=category)

        # GEO filtering
        qs = self._filter_geo(qs, country)

        # Device filtering
        qs = self._filter_device(qs, device, os_name)

        # Budget cap check
        qs = self._filter_capped(qs)

        # Score and rank
        offers    = list(qs.select_related('advertiser')[:50])
        ranked    = self._rank_offers(offers, country, device)

        if not ranked:
            result = {'offer': None, 'bid': Decimal('0'), 'alternatives': []}
        else:
            result = {
                'offer':        ranked[0]['offer'],
                'bid':          ranked[0]['score'],
                'alternatives': [r['offer'] for r in ranked[1:5]],
            }

        cache.set(cache_key, result, CACHE_TTL)
        logger.debug(f'RTB: pub={publisher.id} {country}/{device} → offer={result["offer"]}')
        return result

    def find_offers_for_offerwall(self, publisher, country: str, device: str,
                                   limit: int = 20) -> list:
        """
        Get ranked list of offers for offerwall display.
        Auto-optimizes for highest EPC first.
        """
        from offers.models import Offer
        from django.db.models import Q

        qs = Offer.objects.filter(
            status='active',
        ).filter(
            Q(is_public=True) | Q(allowed_publishers=publisher)
        ).exclude(blocked_publishers=publisher)

        qs = self._filter_geo(qs, country)
        qs = self._filter_device(qs, device, '')
        qs = self._filter_capped(qs)

        offers = list(qs[:100])
        ranked = self._rank_offers(offers, country, device)
        return [r['offer'] for r in ranked[:limit]]

    def _filter_geo(self, qs, country: str):
        """Filter offers that accept this country."""
        from django.db.models import Q
        if not country:
            return qs
        # Keep offers with empty target_countries (worldwide) OR that include this country
        # Exclude offers that block this country
        result = []
        for offer in qs:
            targets = offer.target_countries or []
            blocked = offer.blocked_countries or []
            if country in blocked:
                continue
            if targets and country not in targets:
                continue
            result.append(offer.id)
        return qs.filter(id__in=result)

    def _filter_device(self, qs, device: str, os_name: str):
        result = []
        for offer in qs:
            devices = offer.target_devices or []
            os_list = offer.target_os or []
            if devices and device not in devices:
                continue
            if os_list and os_name and os_name not in os_list:
                continue
            result.append(offer.id)
        return qs.filter(id__in=result)

    def _filter_capped(self, qs):
        """Remove offers that have hit their daily cap."""
        from django.utils import timezone
        from tracking.models import Conversion

        today     = timezone.now().date()
        capped_ids = []

        for offer in qs:
            if offer.daily_cap:
                today_convs = Conversion.objects.filter(
                    offer=offer,
                    status='approved',
                    created_at__date=today,
                ).count()
                if today_convs >= offer.daily_cap:
                    capped_ids.append(offer.id)

        return qs.exclude(id__in=capped_ids)

    def _rank_offers(self, offers: list, country: str, device: str) -> list:
        """
        Score and rank offers by quality-adjusted EPC.
        Formula: score = EPC * quality_weight * geo_weight * device_weight
        """
        scored = []
        for offer in offers:
            epc   = float(offer.epc or 0)
            payout = float(offer.publisher_payout)

            # If no EPC history, use payout as estimate
            base_score = epc if epc > 0 else payout * 0.1

            # Geo weight: specific GEO targeting = higher quality
            geo_weight = 1.2 if offer.target_countries else 1.0

            # Device weight: mobile targeting = premium
            dev_weight = 1.15 if 'mobile' in (offer.target_devices or []) and device == 'mobile' else 1.0

            # CPI offers get slight boost (higher payouts)
            type_weight = 1.1 if offer.offer_type == 'cpi' else 1.0

            score = base_score * geo_weight * dev_weight * type_weight

            scored.append({
                'offer': offer,
                'score': Decimal(str(round(score, 4))),
                'epc':   epc,
            })

        return sorted(scored, key=lambda x: x['score'], reverse=True)
