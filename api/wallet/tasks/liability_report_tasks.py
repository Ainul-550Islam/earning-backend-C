# api/wallet/tasks/liability_report_tasks.py
"""
Daily liability report computation.
"""
import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger("wallet.tasks.liability")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.compute_daily_liability")
def compute_daily_liability(self, report_date: str = None, currency: str = "BDT"):
    """
    Compute platform financial liability snapshot.
    Runs daily at 3 AM.
    """
    try:
        from ..services import WalletAnalyticsService
        target = date.fromisoformat(report_date) if report_date else date.today() - timedelta(days=1)
        report = WalletAnalyticsService.compute_liability(target, currency)
        logger.info(f"Liability: date={target} total={report.total_liability}")
        return {
            "date": str(target),
            "total_liability": float(report.total_liability),
            "total_wallets": report.total_wallets,
        }
    except Exception as e:
        logger.error(f"compute_daily_liability: {e}")
        raise self.retry(exc=e)
