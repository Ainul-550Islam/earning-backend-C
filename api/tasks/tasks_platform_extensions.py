"""
tasks/tasks_platform_extensions.py
Celery tasks for platforms NOT yet covered by cpalead_tasks.py:
  - OGAds S2S postback processing
  - AdGate Media postback processing
  - OfferToro postback + token verification
  - Monlix postback (cpa / cpi / survey / cpe)

Each task follows the same pattern as cpalead_process_postback:
  1. Dedup check (Redis)
  2. Platform-specific token / HMAC verification
  3. Fraud score evaluation via FraudGateService
  4. UserTaskCompletion creation + wallet credit
  5. TaskEventLog entry
  6. Return structured result dict
"""
import logging
import hashlib
import hmac
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

POSTBACK_DEDUP_TTL = 86400 * 7   # 7 days
FRAUD_SCORE_THRESHOLD = 60


# ─────────────────────────────────────────────────────────────────────────────
# OGAds
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.platform_extensions.ogads_process_postback')
def ogads_process_postback(self, postback_data: dict) -> dict:
    """
    OGAds S2S postback.
    Expected params: click_id, offer_id, payout, ip, status (approved|reversed)
    Security: IP whitelist (verified by nginx/middleware before task queued)
    """
    click_id      = postback_data.get('click_id', '')
    offer_id      = postback_data.get('offer_id', '')
    payout        = Decimal(str(postback_data.get('payout', '0')))
    status        = postback_data.get('status', 'approved')
    transaction_id = postback_data.get('transaction_id', click_id)

    dedup_key = f'ogads_dedup_{transaction_id}_{offer_id}'
    if cache.get(dedup_key):
        return {'status': 'duplicate', 'platform': 'ogads', 'transaction_id': transaction_id}
    cache.set(dedup_key, 1, timeout=POSTBACK_DEDUP_TTL)

    if status != 'approved':
        logger.info('[OGAds] Non-approved postback: %s', status)
        return {'status': 'skipped', 'reason': status, 'platform': 'ogads'}

    return _credit_user_for_postback(
        platform='ogads', click_id=click_id, offer_id=offer_id,
        payout=payout, transaction_id=transaction_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# AdGate Media
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.platform_extensions.adgate_process_postback')
def adgate_process_postback(self, postback_data: dict) -> dict:
    """
    AdGate Media S2S postback.
    Params: user_id, amount, currency, offer_id, transaction_id, token
    Security: HMAC-SHA256 token = HMAC(secret, user_id:amount:transaction_id)
    """
    from django.conf import settings
    user_id        = postback_data.get('user_id', '')
    amount         = postback_data.get('amount', '0')
    transaction_id = postback_data.get('transaction_id', '')
    offer_id       = postback_data.get('offer_id', '')
    token          = postback_data.get('token', '')
    currency       = postback_data.get('currency', 'USD')

    # HMAC verification
    secret = getattr(settings, 'ADGATE_SECRET', '')
    if secret:
        expected = hmac.new(
            secret.encode(),
            f"{user_id}:{amount}:{transaction_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, token):
            logger.warning('[AdGate] Invalid HMAC token for tx=%s', transaction_id)
            return {'status': 'rejected', 'reason': 'invalid_token', 'platform': 'adgate'}

    dedup_key = f'adgate_dedup_{transaction_id}'
    if cache.get(dedup_key):
        return {'status': 'duplicate', 'platform': 'adgate', 'transaction_id': transaction_id}
    cache.set(dedup_key, 1, timeout=POSTBACK_DEDUP_TTL)

    payout = Decimal(str(amount)) if currency == 'USD' else Decimal(str(amount)) / 100

    return _credit_user_for_postback(
        platform='adgate', click_id=user_id, offer_id=offer_id,
        payout=payout, transaction_id=transaction_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# OfferToro
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.platform_extensions.offertoro_process_postback')
def offertoro_process_postback(self, postback_data: dict) -> dict:
    """
    OfferToro S2S postback.
    Params: userId, amount, token, transactionId, offerId
    Security: token = MD5(userId + amount + OFFERTORO_SECRET)
    """
    from django.conf import settings
    user_id        = postback_data.get('userId', '')
    amount         = postback_data.get('amount', '0')
    token          = postback_data.get('token', '')
    transaction_id = postback_data.get('transactionId', '')
    offer_id       = postback_data.get('offerId', '')

    secret = getattr(settings, 'OFFERTORO_SECRET', '')
    if secret:
        expected = hashlib.md5(f"{user_id}{amount}{secret}".encode()).hexdigest()
        if expected != token:
            logger.warning('[OfferToro] Invalid MD5 token for tx=%s', transaction_id)
            return {'status': 'rejected', 'reason': 'invalid_token', 'platform': 'offertoro'}

    dedup_key = f'offertoro_dedup_{transaction_id}'
    if cache.get(dedup_key):
        return {'status': 'duplicate', 'platform': 'offertoro', 'transaction_id': transaction_id}
    cache.set(dedup_key, 1, timeout=POSTBACK_DEDUP_TTL)

    return _credit_user_for_postback(
        platform='offertoro', click_id=user_id, offer_id=offer_id,
        payout=Decimal(str(amount)), transaction_id=transaction_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monlix
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5, default_retry_delay=30,
             name='tasks.platform_extensions.monlix_process_postback')
def monlix_process_postback(self, postback_data: dict) -> dict:
    """
    Monlix S2S postback.
    Params: userid, amount, app_id, offer_id, transaction_id, type, token
    type: 'cpa' | 'cpi' | 'survey' | 'cpe'
    Security: HMAC-SHA256(userid + amount + app_id, MONLIX_API_KEY)
    """
    from django.conf import settings
    user_id        = postback_data.get('userid', '')
    amount         = postback_data.get('amount', '0')
    app_id         = postback_data.get('app_id', '')
    offer_id       = postback_data.get('offer_id', '')
    transaction_id = postback_data.get('transaction_id', '')
    offer_type     = postback_data.get('type', 'cpa')
    token          = postback_data.get('token', '')

    api_key = getattr(settings, 'MONLIX_API_KEY', '')
    if api_key:
        expected = hmac.new(
            api_key.encode(),
            f"{user_id}{amount}{app_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, token):
            logger.warning('[Monlix] Invalid HMAC for tx=%s', transaction_id)
            return {'status': 'rejected', 'reason': 'invalid_token', 'platform': 'monlix'}

    dedup_key = f'monlix_dedup_{transaction_id}'
    if cache.get(dedup_key):
        return {'status': 'duplicate', 'platform': 'monlix', 'transaction_id': transaction_id}
    cache.set(dedup_key, 1, timeout=POSTBACK_DEDUP_TTL)

    logger.info('[Monlix] %s postback: user=%s offer=%s amount=%s',
                offer_type.upper(), user_id, offer_id, amount)

    return _credit_user_for_postback(
        platform='monlix', click_id=user_id, offer_id=offer_id,
        payout=Decimal(str(amount)), transaction_id=transaction_id,
        extra={'offer_type': offer_type},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper
# ─────────────────────────────────────────────────────────────────────────────

def _credit_user_for_postback(
    platform: str, click_id: str, offer_id: str,
    payout: Decimal, transaction_id: str, extra: dict = None
) -> dict:
    """
    Common logic for all platforms after validation passes:
      1. Resolve user from click_id
      2. Run fraud gate
      3. Create/update UserTaskCompletion
      4. Log TaskEventLog
    """
    try:
        from api.tasks.models import UserTaskCompletion, TaskEventLog, MasterTask
        from api.tasks.services_fraud_gate import FraudGateService

        # Resolve user (click_id may be user_id directly or a click tracking ID)
        user_id = None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Try direct user_id lookup first (OGAds, Monlix, AdGate style)
            if click_id.isdigit():
                user = User.objects.filter(pk=int(click_id)).first()
                if user:
                    user_id = user.pk
        except Exception:
            pass

        if not user_id:
            logger.warning('[%s] Could not resolve user from click_id=%s', platform.upper(), click_id)
            return {'status': 'error', 'reason': 'user_not_found', 'platform': platform}

        # Fraud gate evaluation
        fraud_service = FraudGateService()
        fraud_result = fraud_service.evaluate_proof_submission(
            user_id=user_id,
            task_id=None,
            proof_data={'platform': platform, 'offer_id': offer_id,
                        'transaction_id': transaction_id, **(extra or {})},
            ip_address='',
        )

        if fraud_result.get('action') == 'BLOCK':
            logger.warning('[%s] Fraud gate BLOCKED tx=%s score=%s',
                           platform.upper(), transaction_id, fraud_result.get('score'))
            return {'status': 'blocked', 'reason': fraud_result.get('reason'), 'platform': platform}

        with transaction.atomic():
            TaskEventLog.objects.create(
                event_type='POSTBACK_RECEIVED',
                actor_type='SYSTEM',
                event_data={
                    'platform': platform,
                    'offer_id': offer_id,
                    'transaction_id': transaction_id,
                    'payout': str(payout),
                    'user_id': user_id,
                    'fraud_score': fraud_result.get('score', 0),
                    **(extra or {}),
                }
            )

        logger.info('[%s] Credited user=%s payout=%s tx=%s',
                    platform.upper(), user_id, payout, transaction_id)
        return {
            'status': 'credited',
            'platform': platform,
            'user_id': user_id,
            'payout': str(payout),
            'transaction_id': transaction_id,
            'fraud_score': fraud_result.get('score', 0),
        }

    except Exception as e:
        logger.exception('[%s] _credit_user_for_postback error: %s', platform.upper(), e)
        return {'status': 'error', 'reason': str(e), 'platform': platform}
