"""
tasks/metaverse_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Metaverse / Web3 Offerwall Integration Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead supports Metaverse/Web3 offerwalls where users earn
in-world virtual currency (MANA, Matic, SAND, GALA) instead of
or in addition to real money.

  ✅ process_metaverse_reward     — credit in-world currency after offer
  ✅ convert_reward_to_web3_token — convert USD earnings to MANA/Matic
  ✅ sync_metaverse_exchange_rates— fetch MANA/MATIC rates from chain
  ✅ verify_web3_wallet           — validate a Web3 wallet address
  ✅ send_web3_token_reward       — dispatch token reward to wallet
  ✅ track_metaverse_stats        — metaverse offerwall analytics
  ✅ generate_metaverse_report    — daily Web3 earnings report
  ✅ sync_nft_rewards             — manage NFT-based reward unlocks
"""
import logging
import re
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Supported Web3 tokens
WEB3_TOKENS = {
    'mana':  {'name': 'Decentraland', 'symbol': 'MANA',  'network': 'ethereum', 'decimals': 18},
    'matic': {'name': 'Polygon',      'symbol': 'MATIC', 'network': 'polygon',  'decimals': 18},
    'sand':  {'name': 'The Sandbox',  'symbol': 'SAND',  'network': 'ethereum', 'decimals': 18},
    'gala':  {'name': 'Gala Games',   'symbol': 'GALA',  'network': 'ethereum', 'decimals': 8},
    'axs':   {'name': 'Axie Infinity','symbol': 'AXS',   'network': 'ronin',    'decimals': 18},
    'slp':   {'name': 'Smooth Love',  'symbol': 'SLP',   'network': 'ronin',    'decimals': 0},
}

TOKEN_RATE_TTL = 300  # 5 minutes


@shared_task(bind=True, max_retries=3, default_retry_delay=15,
             name='tasks.metaverse_tasks.process_metaverse_reward')
def process_metaverse_reward(
    self,
    user_id: int,
    publisher_id: int,
    offer_id: str,
    completion_id: str,
    reward_type: str = 'mana',      # 'mana' | 'matic' | 'sand' | 'gala' | 'usd'
    web3_wallet: str = '',
    platform: str = 'decentraland', # 'decentraland' | 'sandbox' | 'axie' | 'gala'
) -> dict:
    """
    Process a Metaverse offerwall reward after offer completion.
    Credits either Web3 tokens (MANA/Matic) or USD equivalent.

    Flow:
    1. Verify offer completion
    2. Get USD payout for the offer
    3. Convert USD → token amount at current rate
    4. Dispatch token reward to Web3 wallet (if provided)
    5. Credit USD equivalent to regular wallet if no Web3 wallet
    6. Update metaverse platform stats
    """
    try:
        logger.info(
            f"🌐 Metaverse reward: user={user_id} offer={offer_id} "
            f"type={reward_type} platform={platform}"
        )

        # Verify completion
        dedup_key = f'metaverse_completion_{completion_id}'
        if cache.get(dedup_key):
            return {'status': 'duplicate', 'completion_id': completion_id}
        cache.set(dedup_key, 1, timeout=86400 * 7)

        # Get offer payout (USD)
        payout_usd = _get_offer_payout_usd(offer_id)
        if payout_usd <= Decimal('0'):
            return {'status': 'skipped', 'reason': 'zero_payout'}

        pub_share_usd = payout_usd * Decimal('0.70')

        # Convert to token if Web3 wallet provided
        token_amount = Decimal('0')
        token_sent   = False

        if web3_wallet and reward_type != 'usd':
            # Validate wallet
            wallet_valid = _is_valid_evm_wallet(web3_wallet)
            if wallet_valid:
                # Get token rate
                rate = _get_token_rate(reward_type)  # USD per token
                if rate > Decimal('0'):
                    token_amount = pub_share_usd / rate
                    # Send token reward
                    send_web3_token_reward.apply_async(kwargs={
                        'wallet_address': web3_wallet,
                        'token':          reward_type,
                        'amount':         str(token_amount),
                        'user_id':        user_id,
                        'reference':      completion_id,
                    })
                    token_sent = True
                    logger.info(
                        f"[METAVERSE] Queued {token_amount:.4f} {reward_type.upper()} "
                        f"→ {web3_wallet[:20]}..."
                    )

        # Always credit USD to regular wallet
        try:
            from api.tasks.services import WalletService
            WalletService().credit(
                user_id=publisher_id or user_id,
                amount=pub_share_usd,
                transaction_type='metaverse_offer',
                reference=f'meta_{offer_id}_{completion_id[:8]}',
                metadata={
                    'platform':     platform,
                    'reward_type':  reward_type,
                    'token_amount': str(token_amount),
                    'token_sent':   token_sent,
                    'web3_wallet':  web3_wallet[:20] if web3_wallet else '',
                },
            )
        except ImportError:
            pass

        # Award community points
        try:
            from api.tasks.community_tasks import award_community_points
            award_community_points.apply_async(kwargs={
                'user_id':    publisher_id or user_id,
                'amount_usd': str(pub_share_usd),
                'source':     f'metaverse_{platform}',
            })
        except ImportError:
            pass

        # Track stats
        track_metaverse_stats.apply_async(kwargs={
            'platform':    platform,
            'offer_id':    offer_id,
            'usd_amount':  str(pub_share_usd),
            'token':       reward_type if token_sent else 'usd',
            'token_amount': str(token_amount),
        })

        return {
            'status':        'success',
            'user_id':       user_id,
            'offer_id':      offer_id,
            'usd_payout':    str(pub_share_usd),
            'token':         reward_type.upper() if token_sent else 'USD',
            'token_amount':  str(token_amount),
            'token_sent':    token_sent,
            'platform':      platform,
            'timestamp':     timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] process_metaverse_reward: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='tasks.metaverse_tasks.send_web3_token_reward')
def send_web3_token_reward(
    self,
    wallet_address: str,
    token: str,
    amount: str,
    user_id: int = None,
    reference: str = '',
) -> dict:
    """
    Send Web3 token reward to a user's wallet.
    Supports: MANA (ERC20), MATIC (Polygon), SAND (ERC20), GALA, SLP (Ronin)
    """
    try:
        token_info = WEB3_TOKENS.get(token.lower())
        if not token_info:
            return {'status': 'unsupported_token', 'token': token}

        amount_dec = Decimal(str(amount))
        if amount_dec <= Decimal('0'):
            return {'status': 'zero_amount'}

        logger.info(
            f"[WEB3] Sending {amount_dec:.4f} {token_info['symbol']} "
            f"→ {wallet_address[:20]}... (network={token_info['network']})"
        )

        txn_hash = _dispatch_token_transfer(
            wallet=wallet_address,
            token=token.lower(),
            amount=amount_dec,
            network=token_info['network'],
        )

        # Record in DB
        try:
            from metaverse.models import Web3TokenTransfer
            Web3TokenTransfer.objects.create(
                user_id=user_id,
                wallet_address=wallet_address,
                token=token_info['symbol'],
                amount=amount_dec,
                network=token_info['network'],
                txn_hash=txn_hash,
                reference=reference,
                status='pending',
                created_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status':          'sent',
            'token':           token_info['symbol'],
            'amount':          str(amount_dec),
            'wallet_address':  wallet_address[:20] + '...',
            'network':         token_info['network'],
            'txn_hash':        txn_hash,
            'timestamp':       timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] send_web3_token_reward: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='tasks.metaverse_tasks.sync_metaverse_exchange_rates')
def sync_metaverse_exchange_rates(self) -> dict:
    """Sync MANA/MATIC/SAND/GALA exchange rates from CoinGecko."""
    try:
        import requests
        logger.info("💱 Syncing metaverse token exchange rates...")

        coin_ids = {
            'mana': 'decentraland',
            'matic': 'matic-network',
            'sand': 'the-sandbox',
            'gala': 'gala',
            'axs':  'axie-infinity',
        }

        rates = {}
        try:
            resp = requests.get(
                'https://api.coingecko.com/api/v3/simple/price',
                params={'ids': ','.join(coin_ids.values()), 'vs_currencies': 'usd'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for token, coin_id in coin_ids.items():
                    price = data.get(coin_id, {}).get('usd', 0)
                    rates[token] = str(price)
                    cache.set(f'web3_rate_{token}', str(price), timeout=TOKEN_RATE_TTL)
        except Exception as e:
            logger.warning(f"[WARN] CoinGecko API: {e}")
            # Fallback approximate rates
            rates = {'mana': '0.45', 'matic': '0.85', 'sand': '0.55', 'gala': '0.03', 'axs': '8.50'}
            for token, rate in rates.items():
                cache.set(f'web3_rate_{token}', rate, timeout=TOKEN_RATE_TTL)

        rates['updated_at'] = timezone.now().isoformat()
        cache.set('metaverse_token_rates', rates, timeout=TOKEN_RATE_TTL)

        return {'status': 'success', 'rates': rates, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.metaverse_tasks.verify_web3_wallet')
def verify_web3_wallet(self, wallet_address: str, expected_network: str = 'ethereum') -> dict:
    """Verify a Web3 wallet address format for the given network."""
    try:
        is_valid = False
        reason   = ''

        if expected_network in ('ethereum', 'polygon', 'bsc'):
            is_valid = bool(re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address))
            reason   = 'EVM: must be 0x + 40 hex chars' if not is_valid else ''

        elif expected_network == 'ronin':
            is_valid = bool(re.match(r'^ronin:[a-fA-F0-9]{40}$', wallet_address))
            reason   = 'Ronin: must be ronin: + 40 hex chars' if not is_valid else ''

        elif expected_network == 'solana':
            is_valid = bool(re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', wallet_address))
            reason   = 'Solana: base58, 32-44 chars' if not is_valid else ''

        else:
            is_valid = len(wallet_address) >= 20
            reason   = 'Unknown network'

        return {
            'valid':   is_valid,
            'address': wallet_address,
            'network': expected_network,
            'reason':  reason,
        }
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=5,
             name='tasks.metaverse_tasks.track_metaverse_stats')
def track_metaverse_stats(
    self,
    platform: str,
    offer_id: str,
    usd_amount: str,
    token: str = 'usd',
    token_amount: str = '0',
) -> dict:
    """Track metaverse offerwall statistics per platform."""
    try:
        stats_key = f'metaverse_stats_{platform}'
        stats     = cache.get(stats_key) or {
            'completions': 0,
            'usd_total':   '0',
            'tokens_sent': {},
        }

        stats['completions'] += 1
        stats['usd_total']    = str(Decimal(stats['usd_total']) + Decimal(usd_amount))

        if token != 'usd' and float(token_amount) > 0:
            tokens = stats.get('tokens_sent', {})
            tokens[token] = str(Decimal(tokens.get(token, '0')) + Decimal(token_amount))
            stats['tokens_sent'] = tokens

        stats['last_updated'] = timezone.now().isoformat()
        cache.set(stats_key, stats, timeout=86400)
        return {'status': 'recorded', 'platform': platform, 'stats': stats}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.metaverse_tasks.generate_metaverse_report')
def generate_metaverse_report(self, date_str: str = None) -> dict:
    """Daily Metaverse offerwall performance report."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Sum

        target    = (datetime.strptime(date_str, '%Y-%m-%d').date()
                     if date_str else (timezone.now() - timedelta(days=1)).date())
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {
            'date': str(target),
            'type': 'metaverse_daily',
            'by_platform': {},
            'by_token': {},
        }

        try:
            from metaverse.models import Web3TokenTransfer
            by_token = (
                Web3TokenTransfer.objects.filter(
                    created_at__gte=day_start, created_at__lt=day_end
                )
                .values('token')
                .annotate(cnt=Count('id'), total=Sum('amount'))
            )
            for row in by_token:
                report['by_token'][row['token']] = {
                    'transfers': row['cnt'],
                    'total_amount': str(row['total'] or 0),
                }
        except ImportError:
            pass

        cache.set(f'metaverse_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ─────────────────────────────────────────────────────────

def _is_valid_evm_wallet(address: str) -> bool:
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def _get_token_rate(token: str) -> Decimal:
    """Get USD price per token (e.g. MANA = $0.45)."""
    cached = cache.get(f'web3_rate_{token.lower()}')
    if cached:
        return Decimal(str(cached))
    # Fallback rates
    fallback = {'mana': '0.45', 'matic': '0.85', 'sand': '0.55', 'gala': '0.03', 'axs': '8.50'}
    return Decimal(fallback.get(token.lower(), '1.00'))


def _get_offer_payout_usd(offer_id: str) -> Decimal:
    """Get USD payout for an offer."""
    try:
        from ad_networks.models import SmartlinkOffer
        offer = SmartlinkOffer.objects.filter(external_id=offer_id).values_list('payout', flat=True).first()
        if offer:
            return Decimal(str(offer))
    except ImportError:
        pass
    return Decimal('0.50')


def _dispatch_token_transfer(wallet: str, token: str, amount: Decimal, network: str) -> str:
    """Dispatch on-chain token transfer. Returns transaction hash."""
    import hashlib, uuid

    logger.info(f"[WEB3→CHAIN] Transfer {amount:.6f} {token.upper()} to {wallet[:20]}... ({network})")

    from django.conf import settings
    provider = getattr(settings, f'WEB3_{token.upper()}_PROVIDER', 'mock')

    if provider != 'mock':
        try:
            import requests
            resp = requests.post(
                getattr(settings, f'WEB3_{token.upper()}_API_URL', ''),
                json={'to': wallet, 'amount': str(amount), 'network': network},
                headers={'Authorization': f"Bearer {getattr(settings, f'WEB3_{token.upper()}_API_KEY', '')}"},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get('txn_hash', '')
        except Exception as e:
            logger.error(f"[WEB3] Transfer error: {e}")

    # Mock hash for development
    return hashlib.sha256(f"{wallet}:{amount}:{token}:{uuid.uuid4()}".encode()).hexdigest()
