# api/wallet/tasks/insight_tasks.py
"""
Daily analytics insight computation tasks.
"""
import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger("wallet.tasks.insights")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.compute_daily_insights")
def compute_daily_insights(self, insight_date: str = None):
    """
    Compute per-wallet daily insights for all wallets.
    Runs daily at 1:30 AM.
    """
    try:
        from ..services import WalletAnalyticsService
        target = date.fromisoformat(insight_date) if insight_date else date.today() - timedelta(days=1)
        result = WalletAnalyticsService.compute_all_wallet_insights(target)
        logger.info(f"Wallet insights: {result}")
        return result
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.compute_withdrawal_insights")
def compute_withdrawal_insights(self, insight_date: str = None):
    """Platform-wide withdrawal analytics. Runs daily at 2 AM."""
    try:
        from ..services import WalletAnalyticsService
        target = date.fromisoformat(insight_date) if insight_date else date.today() - timedelta(days=1)
        result = WalletAnalyticsService.compute_withdrawal_insight(target)
        return {"date": str(target), "total_requested": float(result.total_requested)}
    except Exception as e:
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.compute_earning_insights")
def compute_earning_insights(self, insight_date: str = None):
    """Platform-wide earning analytics. Runs daily at 2:30 AM."""
    try:
        from ..services import WalletAnalyticsService
        target = date.fromisoformat(insight_date) if insight_date else date.today() - timedelta(days=1)
        result = WalletAnalyticsService.compute_earning_insight(target)
        return {"date": str(target), "total_earned": float(result.total_earned)}
    except Exception as e:
        raise self.retry(exc=e)
