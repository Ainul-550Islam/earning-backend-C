# api/payment_gateways/geo_targeting.py
# GEO targeting engine for offers and SmartLinks
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class GeoTargetingEngine:
    def get_best_offers_for_country(self, country_code, device='mobile', limit=10):
        from api.payment_gateways.selectors import OfferSelector
        return OfferSelector.get_for_publisher(None, country=country_code, device=device)[:limit] if country_code else OfferSelector.get_active(limit)
    def is_offer_targeted_for(self, offer, country_code, device=''):
        if not country_code: return True
        cc = country_code.upper()
        targeted = offer.target_countries
        blocked  = offer.blocked_countries
        if blocked and cc in blocked: return False
        if targeted and cc not in targeted: return False
        if device and offer.target_devices:
            if device not in offer.target_devices: return False
        return True
    def get_payout_for_country(self, offer, country_code):
        from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine
        return GeoPricingEngine().calculate_geo_payout(offer.publisher_payout, country_code)
    def rank_offers_by_country(self, offers, country_code):
        from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine
        engine = GeoPricingEngine()
        ranked = []
        for offer in offers:
            geo_payout = engine.calculate_geo_payout(offer.publisher_payout, country_code)
            ranked.append({'offer':offer,'geo_payout':float(geo_payout),'tier':engine.get_country_tier(country_code)})
        return sorted(ranked, key=lambda x: x['geo_payout'], reverse=True)
geo_targeting = GeoTargetingEngine()
