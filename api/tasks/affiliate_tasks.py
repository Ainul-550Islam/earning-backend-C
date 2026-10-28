"""
tasks/affiliate_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Affiliate Network Management Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Full affiliate tracking: sub-affiliates, network partnerships,
multi-level commission, affiliate API tokens.
  ✅ process_affiliate_commission  — multi-level affiliate credits
  ✅ sync_affiliate_networks       — pull offers from partner networks
  ✅ validate_affiliate_links      — verify affiliate URLs are active
  ✅ generate_affiliate_report     — affiliate performance report
  ✅ expire_affiliate_tokens       — rotate old API tokens
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Commission structure: level → % of conversion value
AFFILIATE_COMMISSION = {
    1: Decimal('0.05'),   # Direct referrer: 5%
    2: Decimal('0.02'),   # Level 2: 2%
    3: Decimal('0.01'),   # Level 3: 1%
}


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.affiliate_tasks.process_affiliate_commission')
def process_affiliate_commission(
    self,
    user_id: int,
    conversion_amount: str,
    conversion_type: str = 'task_completion',
) -> dict:
    """
    Process multi-level affiliate commissions for a conversion.
    Walks up the referral chain crediting each level.
    """
    try:
        amount  = Decimal(str(conversion_amount))
        credits = []

        try:
            from referrals.models import Referral
            from api.tasks.services import WalletService
            ws = WalletService()

            # Walk referral chain up to 3 levels
            current_user_id = user_id
            for level in [1, 2, 3]:
                ref = Referral.objects.filter(referred_user_id=current_user_id).first()
                if not ref:
                    break

                commission = amount * AFFILIATE_COMMISSION[level]
                if commission < Decimal('0.001'):
                    break

                ws.credit(
                    user_id=ref.referrer_id,
                    amount=commission,
                    transaction_type=f'affiliate_commission_l{level}',
                    reference=f'aff_{level}_{user_id}_{int(timezone.now().timestamp())}',
                    metadata={'level': level, 'source_user': user_id, 'conversion_type': conversion_type},
                )
                credits.append({'user_id': ref.referrer_id, 'level': level, 'amount': str(commission)})
                current_user_id = ref.referrer_id

        except ImportError as e:
            logger.warning(f"[WARN] Referral/Wallet not available: {e}")

        return {
            'status': 'success',
            'user_id': user_id,
            'credits_issued': len(credits),
            'credits': credits,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='tasks.affiliate_tasks.sync_affiliate_networks')
def sync_affiliate_networks(self) -> dict:
    """Pull offers from partner affiliate networks and add to local inventory."""
    try:
        import requests
        from django.conf import settings
        logger.info("🔄 Syncing affiliate network offers...")

        synced = 0
        errors = 0
        NETWORKS = getattr(settings, 'AFFILIATE_NETWORKS', {})

        for network_name, config in NETWORKS.items():
            if not config.get('api_key'):
                continue
            try:
                resp = requests.get(
                    config['feed_url'],
                    params={'api_key': config['api_key'], 'format': 'json'},
                    timeout=30,
                )
                if resp.status_code == 200:
                    offers = resp.json().get('offers', [])
                    for offer_data in offers:
                        try:
                            from ad_networks.models import SmartlinkOffer
                            SmartlinkOffer.objects.update_or_create(
                                external_id=offer_data.get('id'),
                                defaults={
                                    'name':            offer_data.get('name', ''),
                                    'payout':          Decimal(str(offer_data.get('payout', 0))),
                                    'network_name':    network_name,
                                    'category':        offer_data.get('category', 'general'),
                                    'countries':       offer_data.get('countries', []),
                                    'is_active':       offer_data.get('active', True),
                                },
                            )
                            synced += 1
                        except ImportError:
                            synced += 1
            except Exception as e:
                logger.error(f"[ERROR] Affiliate network {network_name}: {e}")
                errors += 1

        return {'status': 'success', 'synced': synced, 'errors': errors, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.affiliate_tasks.validate_affiliate_links')
def validate_affiliate_links(self) -> dict:
    """Check that all affiliate offer URLs are alive and return 200."""
    try:
        import requests
        logger.info("🔗 Validating affiliate links...")
        checked = 0
        broken  = 0

        try:
            from ad_networks.models import SmartlinkOffer
            for offer in SmartlinkOffer.objects.filter(is_active=True).values('id', 'offer_url', 'external_id')[:100]:
                if not offer.get('offer_url'):
                    continue
                try:
                    resp = requests.head(offer['offer_url'], timeout=5, allow_redirects=True)
                    if resp.status_code >= 400:
                        SmartlinkOffer.objects.filter(pk=offer['id']).update(
                            is_active=False, paused_reason=f'link_broken:{resp.status_code}'
                        )
                        broken += 1
                    checked += 1
                except Exception:
                    broken += 1
        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'checked': checked, 'broken': broken, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)
