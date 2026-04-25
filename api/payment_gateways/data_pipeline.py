# api/payment_gateways/data_pipeline.py
# Data pipeline for ETL operations
import logging
from decimal import Decimal
logger=logging.getLogger(__name__)

class DataPipeline:
    def run_daily_etl(self):
        results={}
        results['daily_stats']=self._aggregate_daily_stats()
        results['offer_metrics']=self._update_offer_metrics()
        results['publisher_scores']=self._update_publisher_scores()
        results['exchange_rates']=self._sync_exchange_rates()
        return results
    def _aggregate_daily_stats(self):
        from api.payment_gateways.selectors import AnalyticsSelector
        from api.payment_gateways.models.reconciliation import DailyPaymentSummary
        from api.payment_gateways.models.core import GatewayTransaction
        from django.db.models import Sum,Count
        from django.utils import timezone
        today=timezone.now().date()
        gateways=['bkash','nagad','sslcommerz','stripe','paypal','amarpay','upay','shurjopay','payoneer','wire','ach','crypto']
        created=0
        for gw in gateways:
            for txn_type in ['deposit','withdrawal']:
                qs=GatewayTransaction.objects.filter(gateway=gw,transaction_type=txn_type,created_at__date=today,status='completed')
                agg=qs.aggregate(total=Sum('amount'),count=Count('id'),fees=Sum('fee'))
                if agg['count']:
                    DailyPaymentSummary.objects.update_or_create(date=today,gateway=gw,transaction_type=txn_type,defaults={'total_count':agg['count'],'total_amount':agg['total'] or 0,'total_fees':agg['fees'] or 0})
                    created+=1
        return {'rows_created':created}
    def _update_offer_metrics(self):
        from api.payment_gateways.tasks import update_offer_metrics
        return update_offer_metrics()
    def _update_publisher_scores(self):
        from api.payment_gateways.publisher_scoring import publisher_scoring
        return publisher_scoring.update_all_scores()
    def _sync_exchange_rates(self):
        from api.payment_gateways.currency_rates import currency_rates_service
        return currency_rates_service.sync_from_api()
data_pipeline=DataPipeline()
