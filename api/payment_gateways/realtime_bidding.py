# api/payment_gateways/realtime_bidding.py
# Real-time bidding engine
from decimal import Decimal
import logging,time
logger=logging.getLogger(__name__)

class RTBEngine:
    """Auction-based offer routing for SmartLinks."""
    def run_auction(self,click_data,candidates):
        if not candidates: return None
        country=click_data.get('country','')
        device=click_data.get('device','')
        from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine
        engine=GeoPricingEngine()
        bids=[]
        for offer in candidates:
            try:
                geo_payout=engine.calculate_geo_payout(offer.publisher_payout,country)
                bid={'offer':offer,'bid':float(geo_payout),'publisher_payout':float(offer.publisher_payout),'country':country}
                bids.append(bid)
            except: pass
        if not bids: return candidates[0] if candidates else None
        winner=max(bids,key=lambda x:x['bid'])
        logger.debug(f'RTB auction: {len(bids)} bids, winner={winner["offer"].id} bid=${winner["bid"]:.4f}')
        return winner['offer']
    def get_floor_price(self,country,offer_type='cpa'):
        from api.payment_gateways.services.GeoPricingEngine import GeoPricingEngine,VERTICAL_BENCHMARKS
        engine=GeoPricingEngine()
        tier=engine.get_country_tier(country)
        benchmarks=VERTICAL_BENCHMARKS.get(offer_type,VERTICAL_BENCHMARKS['default'])
        return float(benchmarks.get(tier,Decimal('0.10')))
    def filter_eligible(self,candidates,click_data):
        country=click_data.get('country','')
        device=click_data.get('device','')
        eligible=[]
        for offer in candidates:
            try:
                if offer.blocked_countries and country in offer.blocked_countries: continue
                if offer.target_countries and country not in offer.target_countries and offer.target_countries!=[]: continue
                if offer.target_devices and device not in offer.target_devices and offer.target_devices!=[]: continue
                from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
                if not ConversionCapEngine().check_caps(offer)['can_convert']: continue
                eligible.append(offer)
            except: eligible.append(offer)
        return eligible
rtb_engine=RTBEngine()
