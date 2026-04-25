# api/payment_gateways/fraud/RiskRules.py
# FILE 81 of 257

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging
logger = logging.getLogger(__name__)

def _count_failed(user):
    try:
        from api.payment_gateways.models import GatewayTransaction
        return GatewayTransaction.objects.filter(user=user, status='failed',
            created_at__gte=timezone.now()-timedelta(hours=24)).count()
    except Exception:
        return 0

class RiskRules:
    DEFAULT_RULES = [
        {'name':'max_single','score':30,'reason':'Amount > 100k BDT',
         'condition': lambda u,a,g,ip,m: a > Decimal('100000')},
        {'name':'blacklisted_country','score':50,'reason':'Sanctioned country',
         'condition': lambda u,a,g,ip,m: m.get('country') in ('KP','IR','SY','CU')},
        {'name':'unverified_large','score':20,'reason':'Unverified user, large amount',
         'condition': lambda u,a,g,ip,m: a > Decimal('10000') and not getattr(u,'is_verified',True)},
        {'name':'many_failed','score':25,'reason':'5+ failed txns in 24h',
         'condition': lambda u,a,g,ip,m: _count_failed(u) >= 5},
        {'name':'intl_gateway_large','score':15,'reason':'Large amount via international gateway',
         'condition': lambda u,a,g,ip,m: g in ('stripe','paypal') and a > Decimal('50000')},
    ]

    def evaluate(self, user, amount, gateway, ip_address=None, metadata=None):
        metadata = metadata or {}
        risk_score = 0; reasons = []
        for rule in self.DEFAULT_RULES:
            try:
                if rule['condition'](user, amount, gateway, ip_address, metadata):
                    risk_score += rule['score']; reasons.append(rule['reason'])
            except Exception as e:
                logger.warning(f"Rule {rule['name']} error: {e}")
        try:
            from .models import RiskRule
            for r in RiskRule.objects.filter(is_active=True).order_by('priority'):
                if self._eval_db(r, user, amount, gateway, metadata):
                    risk_score += r.score; reasons.append(r.reason)
        except Exception: pass
        return {'risk_score': min(50, risk_score), 'reasons': reasons}

    def _eval_db(self, rule, user, amount, gateway, metadata):
        try:
            ct = rule.condition_type; cv = rule.condition_value or ''
            if ct == 'amount_gt': return amount > Decimal(cv)
            if ct == 'amount_lt': return amount < Decimal(cv)
            if ct == 'gateway_is': return gateway == cv
        except Exception: pass
        return False
