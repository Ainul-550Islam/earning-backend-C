# api/payment_gateways/smart_caps.py
# Smart conversion caps with auto-scaling
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class SmartCapsEngine:
    """Auto-adjusts caps based on historical performance and budget."""
    def auto_scale_cap(self,offer):
        """Suggest new cap based on performance."""
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta
        last7=Conversion.objects.filter(offer=offer,status='approved',created_at__gte=timezone.now()-timedelta(days=7)).count()
        daily_avg=last7/7
        suggested_daily=int(daily_avg*1.2)+1
        return {'current_cap':offer.daily_cap,'suggested_cap':suggested_daily,'avg_daily':round(daily_avg,1),'reason':f'Based on last 7d average of {daily_avg:.1f} conversions/day (+20% buffer)'}
    def is_approaching_cap(self,offer,threshold=0.80):
        from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
        status=ConversionCapEngine().get_cap_status(offer)
        pct=status.get('daily_pct_used',0) or 0
        return pct>=threshold*100,pct
    def get_cap_recommendation(self,advertiser,budget):
        """How to set caps for a given budget."""
        from api.payment_gateways.offers.models import Offer
        from decimal import Decimal
        avg_cost=Decimal('2.50')
        daily_budget=budget/30
        recommended_daily_cap=int(float(daily_budget)/float(avg_cost))
        return {'monthly_budget':float(budget),'daily_budget':float(daily_budget),'recommended_daily_cap':recommended_daily_cap,'avg_cost_per_conversion':float(avg_cost)}
smart_caps=SmartCapsEngine()
