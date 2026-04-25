# api/payment_gateways/payout_rules.py
from decimal import Decimal
import logging
logger=logging.getLogger(__name__)

class PayoutRulesEngine:
    DEFAULT_RULES={'min_payout':Decimal('1'),'max_daily':Decimal('10000'),'max_single':Decimal('5000'),'net_days':30,'fast_pay_min_earnings':Decimal('100'),'instant_pay_min_earnings':Decimal('500')}
    def get_rules_for_user(self,user):
        rules=dict(self.DEFAULT_RULES)
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            profile=PublisherProfile.objects.get(user=user)
            if profile.tier=='gold': rules['max_daily']=Decimal('50000'); rules['max_single']=Decimal('20000')
            elif profile.tier=='silver': rules['max_daily']=Decimal('25000')
            if profile.is_fast_pay_eligible: rules['net_days']=1
        except: pass
        return {k:float(v) if isinstance(v,Decimal) else v for k,v in rules.items()}
    def can_withdraw(self,user,amount):
        rules=self.get_rules_for_user(user)
        if float(amount)<rules['min_payout']: return False,f'Minimum payout is ${rules["min_payout"]}'
        if float(amount)>rules['max_single']: return False,f'Maximum single payout is ${rules["max_single"]}'
        return True,''
    def get_next_payout_date(self,user):
        from api.payment_gateways.utils.DateUtils import DateUtils
        rules=self.get_rules_for_user(user)
        if rules['net_days']==1: return DateUtils.next_business_day()
        return DateUtils.next_payout_date(f'net{rules["net_days"]}')
    def is_fast_pay_eligible(self,user,amount):
        rules=self.get_rules_for_user(user)
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            p=PublisherProfile.objects.get(user=user)
            return p.is_fast_pay_eligible and float(amount)>=rules.get('fast_pay_min_earnings',100)
        except: return False
payout_rules=PayoutRulesEngine()
