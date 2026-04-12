# api/promotions/auditing/report_archiver.py
# Report Archiver — Daily/monthly reports archive করে
import json, logging
from datetime import date, timedelta
from django.core.cache import cache
logger = logging.getLogger('auditing.archiver')

class ReportArchiver:
    """Daily/weekly/monthly business reports generate ও archive করে।"""

    def generate_daily_report(self, report_date: date = None) -> dict:
        from django.utils import timezone
        report_date = report_date or timezone.now().date() - timedelta(days=1)
        cache_key   = f'audit:report:daily:{report_date}'
        cached      = cache.get(cache_key)
        if cached:
            return cached

        report = self._compile_daily(report_date)
        cache.set(cache_key, report, timeout=86400 * 7)
        self._save_to_db(report_date, 'daily', report)
        logger.info(f'Daily report archived: {report_date}')
        return report

    def generate_monthly_report(self, year: int, month: int) -> dict:
        cache_key = f'audit:report:monthly:{year}-{month:02d}'
        cached    = cache.get(cache_key)
        if cached:
            return cached
        report = self._compile_monthly(year, month)
        cache.set(cache_key, report, timeout=86400 * 30)
        return report

    def _compile_daily(self, d: date) -> dict:
        from django.db.models import Sum, Count, Avg
        from api.promotions.models import TaskSubmission, AdminCommissionLog, PromotionTransaction
        from api.promotions.choices import SubmissionStatus
        try:
            subs  = TaskSubmission.objects.filter(submitted_at__date=d)
            rev   = AdminCommissionLog.objects.filter(created_at__date=d)
            stats = {
                'date':              str(d),
                'submissions':       subs.count(),
                'approved':          subs.filter(status=SubmissionStatus.APPROVED).count(),
                'rejected':          subs.filter(status=SubmissionStatus.REJECTED).count(),
                'revenue_usd':       float(rev.aggregate(t=Sum('total_amount_usd'))['t'] or 0),
                'commission_usd':    float(rev.aggregate(t=Sum('commission_usd'))['t'] or 0),
                'unique_workers':    subs.values('worker_id').distinct().count(),
            }
        except Exception:
            stats = {'date': str(d), 'error': 'data_unavailable'}
        return stats

    def _compile_monthly(self, year: int, month: int) -> dict:
        from django.db.models import Sum, Count
        from api.promotions.models import AdminCommissionLog, Campaign
        from api.promotions.choices import CampaignStatus
        try:
            rev = AdminCommissionLog.objects.filter(created_at__year=year, created_at__month=month)
            return {
                'year': year, 'month': month,
                'revenue_usd':    float(rev.aggregate(t=Sum('total_amount_usd'))['t'] or 0),
                'transactions':   rev.count(),
                'new_campaigns':  Campaign.objects.filter(created_at__year=year, created_at__month=month).count(),
            }
        except Exception:
            return {'year': year, 'month': month, 'error': 'data_unavailable'}

    def _save_to_db(self, report_date, report_type: str, data: dict):
        try:
            from api.promotions.models import ArchivedReport
            ArchivedReport.objects.update_or_create(
                report_date=report_date, report_type=report_type,
                defaults={'data': data},
            )
        except Exception as e:
            logger.error(f'Report DB save failed: {e}')
