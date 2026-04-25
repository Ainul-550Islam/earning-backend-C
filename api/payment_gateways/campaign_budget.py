# api/payment_gateways/campaign_budget.py
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class CampaignBudgetManager:
    def check_budget(self,campaign):
        if not campaign.total_budget: return {'can_convert':True,'reason':''}
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum
        spent=Conversion.objects.filter(offer__campaign=campaign,status='approved').aggregate(s=Sum('cost'))['s'] or Decimal('0')
        if spent>=campaign.total_budget: return {'can_convert':False,'reason':f'Campaign budget exhausted (${campaign.total_budget})'}
        remaining=campaign.total_budget-spent
        return {'can_convert':True,'reason':'','remaining':float(remaining),'spent':float(spent),'budget':float(campaign.total_budget),'pct_used':round(float(spent/campaign.total_budget*100),1)}
    def deduct(self,campaign,amount):
        from api.payment_gateways.offers.models import Campaign
        from django.db.models import F
        Campaign.objects.filter(id=campaign.id).update(spent=F('spent')+Decimal(str(amount)))
        return True
    def set_daily_limit(self,campaign,daily_limit):
        from api.payment_gateways.offers.models import Campaign
        Campaign.objects.filter(id=campaign.id).update(daily_budget=Decimal(str(daily_limit)))
    def get_budget_utilization(self,campaign_id):
        from api.payment_gateways.offers.models import Campaign
        try:
            c=Campaign.objects.get(id=campaign_id)
            result=self.check_budget(c)
            return {**result,'campaign_id':campaign_id,'name':c.name,'status':c.status}
        except: return {}
campaign_budget_manager=CampaignBudgetManager()
