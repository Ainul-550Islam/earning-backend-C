# api/payment_gateways/conversion_goals.py
import logging
from decimal import Decimal
logger=logging.getLogger(__name__)

class ConversionGoalTracker:
    GOAL_TYPES={'install':'app_install','registration':'user_signup','purchase':'sale','lead':'lead_form','trial':'free_trial','subscription':'subscription'}
    def record_goal(self,click,goal_type,value=None,metadata=None):
        from api.payment_gateways.tracking.models import Conversion
        from api.payment_gateways.repositories import ConversionRepository
        offer=click.offer
        if not offer: return {'success':False,'error':'No offer for this click'}
        repo=ConversionRepository()
        if repo.exists(click.click_id): return {'success':True,'duplicate':True}
        payout=value if value else (offer.publisher_payout if offer else Decimal('0'))
        cost=offer.advertiser_cost if offer else Decimal('0')
        conv=repo.create(publisher=click.publisher,offer=offer,click=click,payout=payout,cost=cost,country=click.country_code,currency=offer.currency if offer else 'USD',metadata={'goal_type':goal_type,'value':float(value or 0),'raw_metadata':metadata or {}})
        return {'success':True,'conversion_id':conv.conversion_id,'payout':float(payout)}
    def get_funnel(self,offer_id,days=30):
        from api.payment_gateways.tracking.models import Click,Conversion
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        since=timezone.now()-timedelta(days=days)
        clicks=Click.objects.filter(offer_id=offer_id,created_at__gte=since).count()
        convs=Conversion.objects.filter(offer_id=offer_id,status='approved',created_at__gte=since).count()
        cr=convs/max(clicks,1)*100
        return {'clicks':clicks,'conversions':convs,'conversion_rate':round(cr,2),'drop_off':round(100-cr,2)}
conversion_goals=ConversionGoalTracker()
