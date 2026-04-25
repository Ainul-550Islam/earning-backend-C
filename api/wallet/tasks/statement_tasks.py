# api/wallet/tasks/statement_tasks.py
import logging
from celery import shared_task
from datetime import date, timedelta

logger = logging.getLogger("wallet.tasks.statement")


@shared_task(bind=True, max_retries=2, name="wallet.generate_monthly_statements")
def generate_monthly_statements(self):
    """Generate monthly statements for all wallets — run 1st of month at 3 AM."""
    try:
        from ..models.core import Wallet
        from ..reporting.statement_generator import StatementGenerator

        today  = date.today()
        # Previous month
        first_of_month = date(today.year, today.month, 1)
        period_end     = first_of_month - timedelta(days=1)
        period_start   = date(period_end.year, period_end.month, 1)

        wallets = Wallet.objects.filter(is_locked=False)
        ok = failed = skipped = 0

        for wallet in wallets:
            try:
                result = StatementGenerator.generate(wallet, period_start, period_end)
                if result["success"]: ok += 1
                else: failed += 1
            except Exception: skipped += 1

        logger.info(f"Monthly statements: ok={ok} failed={failed} skipped={skipped}")
        return {"ok": ok, "failed": failed, "skipped": skipped, "period": str(period_start)}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2, name="wallet.generate_tax_records")
def generate_annual_tax_records(self, year: int = None):
    """Generate annual tax records — run Jan 1st at 4 AM."""
    try:
        from ..models.core import Wallet
        from ..reporting.tax_report_generator import TaxReportGenerator

        if not year:
            year = date.today().year - 1  # Previous year

        wallets = Wallet.objects.filter(total_earned__gt=0)
        ok = failed = 0

        for wallet in wallets:
            try:
                result = TaxReportGenerator.generate_annual(wallet, year)
                if result["success"]: ok += 1
                else: failed += 1
            except Exception: failed += 1

        logger.info(f"Tax records generated: year={year} ok={ok} failed={failed}")
        return {"year": year, "ok": ok, "failed": failed}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)
