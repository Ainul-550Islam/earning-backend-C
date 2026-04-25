# api/wallet/tasks/export_tasks.py
import logging
from celery import shared_task

logger = logging.getLogger("wallet.tasks.export")


@shared_task(bind=True, max_retries=2, name="wallet.export_transactions_csv")
def export_transactions_csv(self, wallet_id: int, date_from=None, date_to=None,
                             user_email: str = "") -> dict:
    """Generate transaction CSV and email to user."""
    try:
        from ..reporting.export import WalletExporter
        csv_content = WalletExporter.transactions_csv(wallet_id, date_from, date_to)

        if user_email:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject="Your Wallet Transaction Export",
                message="Please find your wallet transaction export attached.",
                from_email=getattr(settings,"DEFAULT_FROM_EMAIL","noreply@wallet.com"),
                recipient_list=[user_email],
                fail_silently=True,
            )
        logger.info(f"Transactions exported: wallet={wallet_id}")
        return {"success": True, "rows": csv_content.count("\n"), "wallet_id": wallet_id}
    except Exception as e:
        raise self.retry(exc=e, countdown=120)


@shared_task(bind=True, max_retries=2, name="wallet.export_withdrawals_csv")
def export_withdrawals_csv(self, admin_email: str, date_from=None, date_to=None, status=None):
    """Generate withdrawal admin CSV and email to admin."""
    try:
        from ..reporting.export import WalletExporter
        csv_content = WalletExporter.withdrawals_csv(date_from, date_to, status)
        if admin_email:
            from django.core.mail import send_mail
            send_mail(
                subject="Withdrawal Export",
                message=f"Withdrawal export attached ({date_from} to {date_to})",
                from_email="admin@wallet.com",
                recipient_list=[admin_email],
                fail_silently=True,
            )
        return {"success": True, "rows": csv_content.count("\n")}
    except Exception as e:
        raise self.retry(exc=e, countdown=120)
