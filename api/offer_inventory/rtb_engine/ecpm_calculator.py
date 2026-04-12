# api/offer_inventory/rtb_engine/ecpm_calculator.py
"""
eCPM Calculator — Calculate effective CPM for each offer in a bid request.
eCPM = (Conversions / Clicks) × Payout × 1000
Adjusted by: geo bonus, device bonus, time-of-day, user segment.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

P4 = Decimal('0.0001')
THOUSAND = Decimal('1000')


class ECPMCalculator:
    """Calculate and rank offers by eCPM for RTB."""

    @classmethod
    def score_offers(cls, offers: list, request) -> list:
        """Score all offers for a bid request. Returns [(offer, ecpm), ...]."""
        results = []
        for offer in offers:
            ecpm = cls.calculate(offer, request)
            if ecpm > 0:
                results.append((offer, ecpm))
        return sorted(results, key=lambda x: x[1], reverse=True)

    @classmethod
    def calculate(cls, offer, request) -> Decimal:
        """
        Calculate effective CPM for an offer+request combo.
        eCPM = CVR × payout × 1000 × geo_factor × device_factor × time_factor
        """
        cache_key = f'rtb:ecpm:{offer.id}:{request.country}:{request.device_type}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        cvr     = cls._get_cvr(offer)
        payout  = Decimal(str(offer.payout_amount or '0'))

        if cvr <= 0 or payout <= 0:
            cache.set(cache_key, '0', 120)
            return Decimal('0')

        base_ecpm = (cvr * payout * THOUSAND).quantize(P4)

        # Multipliers
        geo_factor    = cls._geo_factor(offer, request.country)
        device_factor = cls._device_factor(offer, request.device_type)
        time_factor   = cls._time_of_day_factor()

        final_ecpm = (base_ecpm * geo_factor * device_factor * time_factor).quantize(P4)
        cache.set(cache_key, str(final_ecpm), 120)
        return final_ecpm

    @staticmethod
    def _get_cvr(offer) -> Decimal:
        """Conversion rate (0–1) from offer stats or model field."""
        cache_key = f'rtb:cvr:{offer.id}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        # Use model field first
        cvr = Decimal(str(offer.conversion_rate or '0')) / Decimal('100')

        # Recompute from recent conversions if field is 0
        if cvr == 0:
            try:
                from api.offer_inventory.models import Click, Conversion
                since  = timezone.now() - timedelta(days=7)
                clicks = Click.objects.filter(offer=offer, created_at__gte=since, is_fraud=False).count()
                convs  = Conversion.objects.filter(offer=offer, created_at__gte=since, status__name='approved').count()
                cvr    = Decimal(str(convs)) / Decimal(str(max(clicks, 1)))
            except Exception:
                cvr = Decimal('0.02')   # 2% default

        cache.set(cache_key, str(cvr), 300)
        return cvr

    @staticmethod
    def _geo_factor(offer, country: str) -> Decimal:
        """Geo performance multiplier."""
        high_value = {'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'JP', 'SG'}
        medium     = {'IN', 'BD', 'MY', 'ID', 'PH', 'TH', 'VN', 'BR'}
        if country in high_value:
            return Decimal('1.5')
        if country in medium:
            return Decimal('1.0')
        return Decimal('0.7')

    @staticmethod
    def _device_factor(offer, device_type: str) -> Decimal:
        """Device type performance multiplier."""
        factors = {'mobile': Decimal('1.2'), 'tablet': Decimal('1.0'), 'desktop': Decimal('0.9')}
        return factors.get(device_type, Decimal('1.0'))

    @staticmethod
    def _time_of_day_factor() -> Decimal:
        """Peak/off-peak time multiplier."""
        hour = timezone.now().hour
        if 9 <= hour <= 22:   # Peak hours
            return Decimal('1.1')
        return Decimal('0.9')

    @classmethod
    def get_platform_ecpm_report(cls, days: int = 7) -> list:
        """Platform-wide eCPM by offer."""
        from api.offer_inventory.models import Offer
        from api.offer_inventory.analytics import OfferAnalytics
        results = []
        for offer in Offer.objects.filter(status='active')[:100]:
            stats = OfferAnalytics.get_offer_stats(str(offer.id), days=days)
            ecpm  = stats.get('epc', 0) * 1000
            results.append({
                'offer_id'   : str(offer.id),
                'title'      : offer.title,
                'ecpm'       : round(ecpm, 4),
                'cvr_pct'    : stats.get('cvr', 0),
                'clicks'     : stats.get('total_clicks', 0),
            })
        return sorted(results, key=lambda x: x['ecpm'], reverse=True)
