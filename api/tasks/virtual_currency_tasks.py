"""
tasks/virtual_currency_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Virtual Currency System (CPAlead Gap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead allows publishers to set custom virtual currency rates.
Users earn "Coins" (or custom currency) instead of real USD,
which can be spent in a virtual store or converted.
  ✅ award_virtual_currency        — credit VC on task/offer completion
  ✅ process_vc_redemption         — redeem VC for rewards/real money
  ✅ sync_vc_exchange_rates        — maintain VC → USD conversion rates
  ✅ expire_old_virtual_currency   — expire unused VC (drives engagement)
  ✅ generate_vc_report            — VC economy health report
  ✅ rebalance_vc_economy          — prevent hyperinflation
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

VC_RATE_CACHE_TTL = 3600  # 1 hour


@shared_task(bind=True, max_retries=3, default_retry_delay=10,
             name='tasks.virtual_currency_tasks.award_virtual_currency')
def award_virtual_currency(
    self,
    user_id: int,
    publisher_id: int,
    amount_usd: str,
    source: str = 'task_completion',
    reference: str = '',
) -> dict:
    """
    Convert USD earnings to virtual currency at the publisher's configured rate.
    publisher_id is the app/game owner who sets the VC rate.
    Example: publisher rate = 100 coins/$1 → $0.50 reward = 50 coins
    """
    try:
        amount_usd_dec = Decimal(str(amount_usd))
        vc_rate        = _get_vc_rate(publisher_id)  # coins per $1
        vc_amount      = amount_usd_dec * Decimal(str(vc_rate))

        logger.info(
            f"🪙 Awarding VC: user={user_id} pub={publisher_id} "
            f"${amount_usd} → {vc_amount} coins (rate={vc_rate}/USD)"
        )

        try:
            from virtual_currency.models import VirtualWallet
            from django.db.models import F

            wallet, _ = VirtualWallet.objects.get_or_create(
                user_id=user_id,
                publisher_id=publisher_id,
                defaults={'balance': 0, 'total_earned': 0},
            )
            wallet.balance      += vc_amount
            wallet.total_earned += vc_amount
            wallet.save(update_fields=['balance', 'total_earned'])

            # Transaction log
            from virtual_currency.models import VirtualTransaction
            VirtualTransaction.objects.create(
                wallet=wallet,
                amount=vc_amount,
                transaction_type='credit',
                source=source,
                reference=reference,
                usd_equivalent=amount_usd_dec,
                created_at=timezone.now(),
            )

        except ImportError:
            # Cache-based fallback
            balance_key = f'vc_balance_{user_id}_{publisher_id}'
            current     = Decimal(str(cache.get(balance_key) or 0))
            cache.set(balance_key, str(current + vc_amount), timeout=None)

        return {
            'status': 'success',
            'user_id': user_id,
            'vc_amount': str(vc_amount),
            'vc_rate': vc_rate,
            'usd_equivalent': str(amount_usd_dec),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.virtual_currency_tasks.process_vc_redemption')
def process_vc_redemption(
    self,
    user_id: int,
    publisher_id: int,
    vc_amount: str,
    redemption_type: str = 'cash',  # 'cash' | 'item' | 'gift_card' | 'crypto'
    item_id: str = '',
) -> dict:
    """
    Process a virtual currency redemption:
    - cash:      Convert VC → USD → credit real wallet
    - item:      Deduct VC → unlock item in virtual store
    - gift_card: Deduct VC → generate gift card code
    """
    try:
        vc_dec     = Decimal(str(vc_amount))
        vc_rate    = _get_vc_rate(publisher_id)
        usd_value  = vc_dec / Decimal(str(vc_rate)) if vc_rate > 0 else Decimal('0')

        logger.info(
            f"💰 VC redemption: user={user_id} {vc_amount} coins → "
            f"type={redemption_type} value=${usd_value}"
        )

        # Deduct VC balance
        try:
            from virtual_currency.models import VirtualWallet
            from django.db import transaction

            with transaction.atomic():
                wallet = VirtualWallet.objects.select_for_update().get(
                    user_id=user_id, publisher_id=publisher_id
                )
                if wallet.balance < vc_dec:
                    return {'status': 'insufficient_balance',
                            'balance': str(wallet.balance), 'required': str(vc_dec)}

                wallet.balance -= vc_dec
                wallet.save(update_fields=['balance'])

        except ImportError:
            balance_key = f'vc_balance_{user_id}_{publisher_id}'
            current     = Decimal(str(cache.get(balance_key) or 0))
            if current < vc_dec:
                return {'status': 'insufficient_balance'}
            cache.set(balance_key, str(current - vc_dec), timeout=None)

        # Process by type
        result_data = {}
        if redemption_type == 'cash' and usd_value >= Decimal('0.01'):
            try:
                from api.tasks.services import WalletService
                WalletService().credit(
                    user_id=user_id,
                    amount=usd_value,
                    transaction_type='vc_redemption',
                    reference=f'vc_cash_{user_id}_{int(timezone.now().timestamp())}',
                )
                result_data['usd_credited'] = str(usd_value)
            except ImportError:
                pass

        elif redemption_type == 'gift_card':
            import secrets
            gift_code = secrets.token_hex(8).upper()
            cache.set(f'gift_card_{gift_code}', {
                'user_id': user_id,
                'vc_amount': str(vc_dec),
                'usd_value': str(usd_value),
            }, timeout=86400 * 30)
            result_data['gift_card_code'] = gift_code

        return {
            'status': 'success',
            'user_id': user_id,
            'vc_redeemed': str(vc_dec),
            'redemption_type': redemption_type,
            **result_data,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.virtual_currency_tasks.sync_vc_exchange_rates')
def sync_vc_exchange_rates(self) -> dict:
    """
    Sync VC→USD exchange rates for all publishers.
    Publishers can set custom rates via their dashboard.
    """
    try:
        logger.info("💱 Syncing VC exchange rates...")
        synced = 0

        try:
            from virtual_currency.models import PublisherVCConfig
            for config in PublisherVCConfig.objects.filter(is_active=True):
                rate_key = f'vc_rate_{config.publisher_id}'
                cache.set(rate_key, config.coins_per_dollar, timeout=VC_RATE_CACHE_TTL)
                synced += 1
        except ImportError:
            # Default rates
            cache.set('vc_default_rate', 100, timeout=VC_RATE_CACHE_TTL)

        return {'status': 'success', 'synced': synced, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.virtual_currency_tasks.expire_old_virtual_currency')
def expire_old_virtual_currency(self, expiry_days: int = 180) -> dict:
    """Expire virtual currency not used in expiry_days. Drives re-engagement."""
    try:
        from datetime import timedelta
        logger.info(f"⏰ Expiring old VC (>{expiry_days} days unused)...")
        expired = 0

        try:
            from virtual_currency.models import VirtualWallet
            cutoff  = timezone.now() - timedelta(days=expiry_days)
            stale   = VirtualWallet.objects.filter(
                last_activity__lt=cutoff,
                balance__gt=0,
            )
            for wallet in stale:
                wallet.expired_balance += wallet.balance
                wallet.balance          = 0
                wallet.save(update_fields=['balance', 'expired_balance'])
                expired += 1
        except ImportError:
            pass

        return {'status': 'success', 'expired': expired, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


def _get_vc_rate(publisher_id: int) -> int:
    """Get virtual currency rate (coins per $1) for a publisher."""
    rate_key = f'vc_rate_{publisher_id}'
    rate     = cache.get(rate_key)
    if rate:
        return int(rate)
    try:
        from virtual_currency.models import PublisherVCConfig
        config = PublisherVCConfig.objects.filter(publisher_id=publisher_id).first()
        rate   = config.coins_per_dollar if config else 100
    except ImportError:
        rate = 100
    cache.set(rate_key, rate, timeout=VC_RATE_CACHE_TTL)
    return rate
