# api/payment_gateways/offer_rotator.py
# Smart offer rotation for SmartLinks
import random,logging
from django.core.cache import cache
logger=logging.getLogger(__name__)

class OfferRotator:
    MODES={'random','weighted','best_epc','ab_test','geo_optimized'}
    def rotate(self,smart_link,click_data=None):
        mode=smart_link.rotation_mode
        try:
            from api.payment_gateways.smartlink.models import SmartLinkRotation
            rotations=SmartLinkRotation.objects.filter(smart_link=smart_link).select_related('offer')
            candidates=[r.offer for r in rotations if r.offer and r.offer.status=='active']
        except: return None
        if not candidates: return None
        country=click_data.get('country','') if click_data else ''
        device=click_data.get('device','') if click_data else ''
        if country:
            from api.payment_gateways.realtime_bidding import rtb_engine
            candidates=rtb_engine.filter_eligible(candidates,{'country':country,'device':device})
        if not candidates: return None
        if mode=='best_epc': return max(candidates,key=lambda o:float(o.epc or 0))
        if mode=='ab_test':
            from api.payment_gateways.smartlink.ABTestEngine import ABTestEngine
            return ABTestEngine().select_variant(smart_link,candidates)
        if mode=='geo_optimized' and country:
            from api.payment_gateways.realtime_bidding import rtb_engine
            return rtb_engine.run_auction({'country':country,'device':device},candidates)
        if mode=='weighted':
            try:
                from api.payment_gateways.smartlink.models import SmartLinkRotation
                rotations_map={r.offer_id:r.weight for r in SmartLinkRotation.objects.filter(smart_link=smart_link)}
                weights=[rotations_map.get(o.id,50) for o in candidates]
                return random.choices(candidates,weights=weights,k=1)[0]
            except: pass
        return random.choice(candidates)
offer_rotator=OfferRotator()
