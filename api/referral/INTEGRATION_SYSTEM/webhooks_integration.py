# api/referral/INTEGRATION_SYSTEM/webhooks_integration.py
# Integrates referral module with api/postback_engine + external webhooks
# ============================================================

import hmac
import hashlib
import logging
from decimal import Decimal
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from .integ_constants import (
    SOURCE_OFFER, SOURCE_TASK, SOURCE_WITHDRAWAL, SOURCE_SIGNUP,
)

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = getattr(settings, 'REFERRAL_WEBHOOK_SECRET', '')


def _verify_signature(payload: bytes, signature: str) -> bool:
    """HMAC-SHA256 verification."""
    if not WEBHOOK_SECRET:
        return True  # No secret configured — allow all
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _get_ip(request) -> str:
    x_fw = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_fw:
        return x_fw.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ── Postback Engine Integration ───────────────────────────────────────────────

class PostbackReferralWebhook(View):
    """
    POST /api/referral/webhooks/postback/
    Receives conversion postbacks from api/postback_engine.
    Called by api/postback_engine/services.py after processing.

    Integration:
        api/postback_engine/services.py → deliver_postback()
        → fires internal postback to this endpoint
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        import json
        sig = request.headers.get('X-Referral-Signature', '')
        if not _verify_signature(request.body, sig):
            return HttpResponse('Unauthorized', status=401)

        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponse('Bad Request', status=400)

        conversion_id = data.get('conversion_id')
        user_id = data.get('user_id')
        payout = data.get('payout', '0')
        offer_id = data.get('offer_id', '')
        source = data.get('source', SOURCE_OFFER)

        if not user_id:
            return JsonResponse({'status': 'skip', 'reason': 'no_user_id'})

        try:
            from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
            bridge = get_bridge()

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

            if source == SOURCE_TASK:
                result = bridge.on_task_earned(
                    user=user, task=None,
                    amount=float(payout),
                    source_id=str(conversion_id or ''),
                )
            else:
                result = bridge.on_offer_completed(
                    user=user,
                    offer_id=str(offer_id),
                    user_net_reward=float(payout),
                )

            # Also notify api/postback_engine about commission
            _notify_postback_engine(conversion_id, result)

            return JsonResponse({'status': 'ok', **result})

        except Exception as e:
            logger.error(f'[WebhookInteg] PostbackReferralWebhook error: {e}')
            return HttpResponse('Internal Server Error', status=500)


@csrf_exempt
def offer_wall_postback(request):
    """
    POST /api/referral/webhooks/offerwall/
    CPAlead/Offerwalls postback endpoint.
    S2S (server-to-server) callback when user completes an offer.

    Parameters (GET or POST):
        user_id: platform user ID
        offer_id: offer/campaign ID
        payout: USD/BDT amount earned
        transaction_id: unique conversion ID
        status: 1=approved, 2=pending, 0=reversed
    """
    import json

    if request.method not in ('GET', 'POST'):
        return HttpResponse('Method Not Allowed', status=405)

    # Support both GET (query params) and POST (JSON/form)
    if request.method == 'GET':
        data = request.GET.dict()
    else:
        try:
            data = json.loads(request.body) if request.body else request.POST.dict()
        except Exception:
            data = request.POST.dict()

    user_id = data.get('user_id') or data.get('uid')
    offer_id = data.get('offer_id') or data.get('oid', '')
    payout = data.get('payout') or data.get('amount', '0')
    transaction_id = data.get('transaction_id') or data.get('tid', '')
    status = str(data.get('status', '1'))

    # status=0 or status=reversed → reversal
    if status in ('0', 'reversed', 'chargeback'):
        return _handle_reversal(user_id, transaction_id)

    if not user_id or not payout:
        return JsonResponse({'status': 'error', 'reason': 'missing_params'}, status=400)

    try:
        from django.contrib.auth import get_user_model
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge

        User = get_user_model()
        user = User.objects.get(id=user_id)
        bridge = get_bridge()

        result = bridge.on_offer_completed(
            user=user,
            offer_id=str(offer_id),
            user_net_reward=float(payout),
        )

        logger.info(
            f'[WebhookInteg] Offerwall postback: user={user_id} '
            f'offer={offer_id} payout={payout} → {result}'
        )
        return JsonResponse({'status': '1', 'message': 'OK'})

    except Exception as e:
        logger.error(f'[WebhookInteg] offer_wall_postback error: {e}')
        return JsonResponse({'status': '0', 'message': 'error'}, status=500)


@csrf_exempt
def signup_postback(request):
    """
    POST /api/referral/webhooks/signup/
    Called when user registers via referral link.
    """
    import json

    try:
        data = json.loads(request.body) if request.body else {}
    except Exception:
        return HttpResponse('Bad Request', status=400)

    user_id = data.get('user_id')
    referral_code = data.get('referral_code') or data.get('ref_code')

    if not user_id:
        return JsonResponse({'status': 'error', 'reason': 'no_user_id'}, status=400)

    try:
        from django.contrib.auth import get_user_model
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge

        User = get_user_model()
        user = User.objects.get(id=user_id)
        bridge = get_bridge()

        ip = _get_ip(request)
        result = bridge.on_signup(
            new_user=user, referral_code=referral_code or '', ip=ip,
        )
        return JsonResponse({'status': 'ok', **result})

    except Exception as e:
        logger.error(f'[WebhookInteg] signup_postback error: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ── Postback Engine Notification ──────────────────────────────────────────────

def _handle_reversal(user_id, transaction_id: str) -> HttpResponse:
    """Handle offer reversal — initiate clawback."""
    try:
        from django.contrib.auth import get_user_model
        from api.referral.services.CommissionClawbackService import (
            CommissionClawbackService
        )
        from api.referral.models import CommissionLog

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Find commission logs for this transaction
        logs = CommissionLog.objects.filter(
            referred_user=user,
            source_reference__contains=transaction_id,
            status='released',
        )

        initiated = 0
        for log in logs:
            result = CommissionClawbackService.initiate_clawback(
                commission_log_id=log.id,
                reason='chargeback',
                reason_detail=f'Offer reversal: transaction={transaction_id}',
            )
            if result['success']:
                initiated += 1

        return JsonResponse({'status': 'ok', 'clawbacks_initiated': initiated})

    except Exception as e:
        logger.error(f'[WebhookInteg] reversal error: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _notify_postback_engine(conversion_id, commission_result: dict) -> None:
    """Tell postback_engine about commission paid (for reporting)."""
    try:
        from api.postback_engine.models import Conversion
        if conversion_id:
            Conversion.objects.filter(id=conversion_id).update(
                metadata={
                    'referral_commission': commission_result.get('commissions', [])
                }
            )
    except Exception:
        pass


# ── URL Patterns (include in urls.py) ────────────────────────────────────────

def get_webhook_urlpatterns():
    """
    Returns URL patterns for webhook endpoints.
    Include in api/referral/urls.py:
        from api.referral.INTEGRATION_SYSTEM.webhooks_integration import get_webhook_urlpatterns
        urlpatterns += get_webhook_urlpatterns()
    """
    from django.urls import path
    return [
        path(
            'webhooks/postback/',
            PostbackReferralWebhook.as_view(),
            name='referral-postback'
        ),
        path(
            'webhooks/offerwall/',
            offer_wall_postback,
            name='referral-offerwall-postback'
        ),
        path(
            'webhooks/signup/',
            signup_postback,
            name='referral-signup-postback'
        ),
    ]