# api/wallet/tasks/bonus_expiry_tasks.py
"""
Expire unclaimed and time-limited bonus balances.
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("wallet.tasks.bonus")


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="wallet.expire_bonus_balances")
def expire_bonus_balances(self):
    """
    Expire all active bonuses that have passed their expiry datetime.
    Also clears bonus_balance on wallets with expired bonuses.
    Runs daily at midnight.
    """
    try:
        from ..services import BalanceService
        count = BalanceService.expire_bonuses()

        # Also clean up wallet-level bonus_expires_at
        from ..models import Wallet
        from decimal import Decimal
        expired_wallets = Wallet.objects.filter(
            bonus_balance__gt=0,
            bonus_expires_at__lt=timezone.now()
        )
        wallet_count = 0
        for wallet in expired_wallets:
            wallet.bonus_balance = Decimal("0")
            wallet.save(update_fields=["bonus_balance","updated_at"])
            wallet_count += 1

        logger.info(f"Bonus expiry: bonuses={count} wallets={wallet_count}")
        return {"expired_bonuses": count, "expired_wallet_bonuses": wallet_count}
    except Exception as e:
        logger.error(f"expire_bonus_balances: {e}")
        raise self.retry(exc=e)
