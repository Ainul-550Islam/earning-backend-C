# tasks/usdt_fastpay_tasks.py
# USDT Fast Pay — CPAlead July 2025 feature
# Publishers with $25+ balance can request instant USDT payout

from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


@shared_task
def process_usdt_fastpay_requests():
    """
    Process USDT Fast Pay requests.
    Minimum: $25. Pays via USDT (TRC20 or ERC20) instantly.
    Like CPAlead's July 2025 USDT Fast Pay feature.
    """
    from api.payment_gateways.models.core import PayoutRequest
    from api.payment_gateways.services.CryptoService import CryptoService
    from decimal import Decimal

    USDT_MIN = Decimal('25.00')

    pending = PayoutRequest.objects.filter(
        payout_method='crypto',
        status='approved',
    ).filter(net_amount__gte=USDT_MIN)

    processed = 0
    for req in pending:
        try:
            svc = CryptoService()
            class _M:
                account_number = req.account_number
                account_name   = 'USDT Wallet'
                gateway        = 'crypto'
            result = svc.process_withdrawal(
                user=req.user,
                amount=req.net_amount,
                payment_method=_M(),
                coin='USDT',
            )
            req.status = 'processing'
            req.save(update_fields=['status'])
            processed += 1
        except Exception as e:
            logger.error(f'USDT FastPay failed for {req.id}: {e}')

    logger.info(f'USDT Fast Pay: processed {processed} requests')
    return {'processed': processed}


@shared_task
def process_daily_fastpay():
    """
    Process all Fast Pay eligible publishers daily.
    Any publisher with $1+ balance and Fast Pay enabled gets paid automatically.
    """
    from api.payment_gateways.publisher.models import PublisherProfile
    from api.payment_gateways.models.core import PayoutRequest
    from api.payment_gateways.schedules.ScheduleProcessor import ScheduleProcessor
    import time

    profiles = PublisherProfile.objects.filter(
        is_fast_pay_eligible=True,
        status='active',
    ).select_related('user')

    paid = 0
    for profile in profiles:
        balance = getattr(profile.user, 'balance', 0) or 0
        if balance >= float(profile.minimum_payout):
            try:
                # Create a payout request and process immediately
                from decimal import Decimal
                from api.payment_gateways.services.PaymentFactory import PaymentFactory

                method  = profile.preferred_payment or 'paypal'
                fee_pct = Decimal('0.015')
                amount  = Decimal(str(balance))
                fee     = amount * fee_pct

                payout = PayoutRequest.objects.create(
                    user           = profile.user,
                    amount         = amount,
                    fee            = fee,
                    net_amount     = amount - fee,
                    payout_method  = method,
                    account_number = profile.payment_email or profile.user.email,
                    status         = 'approved',
                    reference_id   = f'FASTPAY-{int(time.time()*1000)}',
                )
                paid += 1
                logger.info(f'Fast Pay queued: {profile.user.username} ${amount} via {method}')
            except Exception as e:
                logger.error(f'Fast Pay failed for {profile.user_id}: {e}')

    logger.info(f'Daily Fast Pay: {paid} publishers queued')
    return {'queued': paid}
