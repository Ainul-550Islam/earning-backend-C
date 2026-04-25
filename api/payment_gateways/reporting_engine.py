# api/payment_gateways/reporting_engine.py
# Advanced reporting engine
import logging
from decimal import Decimal
logger=logging.getLogger(__name__)

class ReportingEngine:
    def generate_report(self,report_type,params):
        generators={'publisher_performance':self.publisher_performance,'offer_analysis':self.offer_analysis,'gateway_comparison':self.gateway_comparison,'revenue_summary':self.revenue_summary,'fraud_report':self.fraud_report}
        gen=generators.get(report_type)
        if not gen: return {'error':f'Unknown report type: {report_type}'}
        return gen(params)
    def publisher_performance(self,params):
        from api.payment_gateways.analytics import PaymentAnalyticsEngine
        from django.contrib.auth import get_user_model
        user_id=params.get('publisher_id')
        days=params.get('days',30)
        if user_id:
            User=get_user_model()
            try: user=User.objects.get(id=user_id); return PaymentAnalyticsEngine().get_publisher_analytics(user,days)
            except: return {'error':'Publisher not found'}
        return {'error':'publisher_id required'}
    def offer_analysis(self,params):
        from api.payment_gateways.analytics import PaymentAnalyticsEngine
        offer_id=params.get('offer_id'); days=params.get('days',30)
        if not offer_id: return {'error':'offer_id required'}
        return PaymentAnalyticsEngine().get_offer_analytics(offer_id,days)
    def gateway_comparison(self,params):
        from api.payment_gateways.analytics import PaymentAnalyticsEngine
        return PaymentAnalyticsEngine().get_gateway_analytics(params.get('days',30))
    def revenue_summary(self,params):
        from api.payment_gateways.analytics import PaymentAnalyticsEngine
        return PaymentAnalyticsEngine().get_revenue_summary(params.get('days',30))
    def fraud_report(self,params):
        from api.payment_gateways.analytics import PaymentAnalyticsEngine
        return PaymentAnalyticsEngine().get_fraud_analytics(params.get('days',7))
    def schedule_report(self,report_type,params,email,frequency='weekly'):
        from django.core.cache import cache
        report_id=f'report:{report_type}:{hash(str(params))}:{email}'
        cache.set(report_id,{'type':report_type,'params':params,'email':email,'frequency':frequency},86400*365)
        return {'scheduled':True,'report_id':report_id,'frequency':frequency}
reporting_engine=ReportingEngine()
