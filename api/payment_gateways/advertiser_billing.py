# api/payment_gateways/advertiser_billing.py
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class AdvertiserBillingEngine:
    def charge_for_conversion(self,advertiser,offer,conversion):
        amount=Decimal(str(offer.advertiser_cost or 0))
        if amount<=0: return {'charged':False,'reason':'No advertiser cost set'}
        try:
            from api.payment_gateways.publisher.models import AdvertiserProfile
            profile=AdvertiserProfile.objects.select_for_update().get(user=advertiser)
            if profile.balance<amount: return {'charged':False,'reason':'Insufficient advertiser balance','balance':float(profile.balance),'required':float(amount)}
            AdvertiserProfile.objects.filter(id=profile.id).update(balance=profile.balance-amount,total_spent=profile.total_spent+amount)
            from api.payment_gateways.models.core import PaymentGateway
            return {'charged':True,'amount':float(amount),'new_balance':float(profile.balance-amount)}
        except Exception as e:
            logger.error(f'Advertiser billing failed: {e}')
            return {'charged':False,'error':str(e)}
    def check_balance(self,advertiser):
        try:
            from api.payment_gateways.publisher.models import AdvertiserProfile
            p=AdvertiserProfile.objects.get(user=advertiser)
            return {'balance':float(p.balance),'credit_limit':float(p.credit_limit or 0),'available':float(p.balance+(p.credit_limit or 0)),'currency':p.currency}
        except: return {'balance':0,'credit_limit':0,'available':0,'currency':'USD'}
    def add_balance(self,advertiser,amount,gateway,reference_id=''):
        from api.payment_gateways.publisher.models import AdvertiserProfile
        from django.db.models import F
        AdvertiserProfile.objects.filter(user=advertiser).update(balance=F('balance')+Decimal(str(amount)))
        logger.info(f'Advertiser balance added: {advertiser.id} +{amount} via {gateway}')
        return {'success':True,'added':float(amount)}
    def get_billing_summary(self,advertiser,days=30):
        from api.payment_gateways.tracking.models import Conversion
        from django.db.models import Sum,Count
        from django.utils import timezone
        from datetime import timedelta
        since=timezone.now()-timedelta(days=days)
        agg=Conversion.objects.filter(advertiser=advertiser,status='approved',created_at__gte=since).aggregate(spend=Sum('cost'),count=Count('id'))
        return {'period_days':days,'total_spend':float(agg['spend'] or 0),'total_conversions':agg['count'] or 0,'avg_cpa':float((agg['spend'] or 0)/max(agg['count'] or 1,1))}
advertiser_billing=AdvertiserBillingEngine()
