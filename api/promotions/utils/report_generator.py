# api/promotions/utils/report_generator.py
import logging
from django.core.cache import cache
logger = logging.getLogger('utils.report_gen')

class ReportGenerator:
    """On-demand report generation — async via Celery。"""

    def generate_async(self, report_type: str, params: dict, user_id: int) -> str:
        import uuid
        job_id = uuid.uuid4().hex[:12]
        cache.set(f'report:job:{job_id}', {'status':'pending','type':report_type,'params':params,'user_id':user_id}, timeout=3600)
        try:
            from api.promotions.tasks import generate_report_task
            generate_report_task.delay(job_id, report_type, params)
        except Exception as e:
            logger.error(f'Report task dispatch failed: {e}')
        return job_id

    def get_status(self, job_id: str) -> dict:
        return cache.get(f'report:job:{job_id}') or {'status':'not_found'}

    def generate_sync(self, report_type: str, params: dict) -> dict:
        """Synchronous report generation।"""
        generators = {
            'revenue':       lambda: __import__('api.promotions.reporting.revenue_report', fromlist=['RevenueReport']).RevenueReport().daily(),
            'fraud':         lambda: __import__('api.promotions.reporting.fraud_analytics', fromlist=['FraudAnalyticsReport']).FraudAnalyticsReport().summary(),
            'payout':        lambda: __import__('api.promotions.reporting.payout_summary', fromlist=['PayoutSummaryReport']).PayoutSummaryReport().summary(),
        }
        fn = generators.get(report_type)
        if not fn: return {'error': f'Unknown report type: {report_type}'}
        try:
            return fn()
        except Exception as e:
            return {'error': str(e)}
