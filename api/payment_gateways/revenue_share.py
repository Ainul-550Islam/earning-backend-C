# api/payment_gateways/revenue_share.py
# Revenue share calculation engine
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class RevenueShareEngine:
    DEFAULT_MARGIN=Decimal('30')
    def calculate_split(self,advertiser_cost,publisher_payout,currency='USD'):
        platform_fee=advertiser_cost-publisher_payout
        margin_pct=platform_fee/advertiser_cost*100 if advertiser_cost>0 else Decimal('0')
        return {'advertiser_cost':float(advertiser_cost),'publisher_payout':float(publisher_payout),'platform_fee':float(platform_fee),'margin_pct':float(margin_pct.quantize(Decimal('0.01'))),'currency':currency}
    def suggest_publisher_payout(self,advertiser_cost,target_margin=None):
        margin=Decimal(str(target_margin or self.DEFAULT_MARGIN))
        suggested_payout=(advertiser_cost*(100-margin)/100).quantize(Decimal('0.0001'))
        return {'suggested_payout':float(suggested_payout),'advertiser_cost':float(advertiser_cost),'platform_margin':float(margin)}
    def apply_performance_bonus(self,base_payout,publisher,performance_multiplier=1.0):
        bonus_multiplier=Decimal('1.0')
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            p=PublisherProfile.objects.get(user=publisher)
            tier_bonuses={'bronze':Decimal('1.0'),'silver':Decimal('1.05'),'gold':Decimal('1.10'),'platinum':Decimal('1.15')}
            bonus_multiplier=tier_bonuses.get(p.tier or 'bronze',Decimal('1.0'))
        except: pass
        bonus_multiplier*=Decimal(str(performance_multiplier))
        final=(base_payout*bonus_multiplier).quantize(Decimal('0.0001'))
        return {'base_payout':float(base_payout),'bonus_multiplier':float(bonus_multiplier),'final_payout':float(final)}
    def get_affiliate_tier_rates(self):
        from api.payment_gateways.bonuses.models import PerformanceTier
        try: return list(PerformanceTier.objects.values('name','min_monthly_earnings','bonus_percent').order_by('sort_order'))
        except: return []
revenue_share=RevenueShareEngine()
