# api/payment_gateways/quota_manager.py
# Publisher/Advertiser quota management
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class QuotaManager:
    DEFAULT_QUOTAS={'max_smartlinks':10,'max_lockers':5,'max_offers':50,'max_api_calls_per_day':10000,'max_monthly_earnings':Decimal('100000'),'max_single_withdrawal':Decimal('10000')}
    def get_quotas(self,user):
        quotas=dict(self.DEFAULT_QUOTAS)
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            p=PublisherProfile.objects.get(user=user)
            if p.tier=='gold': quotas['max_smartlinks']=100; quotas['max_lockers']=50; quotas['max_api_calls_per_day']=100000
            elif p.tier=='silver': quotas['max_smartlinks']=30; quotas['max_lockers']=15
        except: pass
        return {k:float(v) if isinstance(v,Decimal) else v for k,v in quotas.items()}
    def check_quota(self,user,quota_type,current_count=None):
        quotas=self.get_quotas(user)
        limit=quotas.get(quota_type,0)
        if not limit: return True,limit
        if current_count is None:
            current_count=self._get_current_count(user,quota_type)
        if current_count>=limit: return False,f'Quota exceeded for {quota_type}: {current_count}/{limit}'
        return True,''
    def _get_current_count(self,user,quota_type):
        counts={'max_smartlinks':lambda u:self._count(u,'smartlink','SmartLink','publisher'),'max_lockers':lambda u:self._count(u,'locker','ContentLocker','publisher')}
        fn=counts.get(quota_type)
        return fn(user) if fn else 0
    def _count(self,user,module,model,field):
        try:
            from importlib import import_module
            m=import_module(f'api.payment_gateways.{module}.models')
            return getattr(m,model).objects.filter(**{field:user}).count()
        except: return 0
quota_manager=QuotaManager()
