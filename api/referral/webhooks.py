# api/referral/webhooks.py
# Postback / Webhook handlers for referral commission events
# CPAlead style: offer completion → commission trigger
# ============================================================

import hmac
import hashlib
import logging
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = getattr(settings, 'REFERRAL_WEBHOOK_SECRET', 'changeme')


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """HMAC-SHA256 signature verify করো।"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@method_decorator(csrf_exempt, name='dispatch')
class OfferCompletionWebhook(View):
    """
    POST /api/referral/webhooks/offer-complete/
    
    Offer network (CPAlead, MaxBounty, etc.) থেকে postback পাঠায়।
    User offer complete করলে commission trigger করো।
    
    Expected payload:
    {
        "user_id": 123,
        "offer_id": "offer_456",
        "payout": "5.00",
        "currency": "USD",
        "transaction_id": "txn_789",
        "signature": "hmac_sig"
    }
    """

    def post(self, request, *args, **kwargs):
        import json

        # Signature verify
        signature = request.headers.get('X-Webhook-Signature', '')
        if WEBHOOK_SECRET != 'changeme' and signature:
            if not verify_webhook_signature(request.body, signature):
                logger.warning('[Webhook] Invalid signature')
                return HttpResponse('Unauthorized', status=401)

        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponse('Bad Request', status=400)

        user_id = data.get('user_id')
        offer_id = data.get('offer_id', '')
        payout = data.get('payout', '0')
        transaction_id = data.get('transaction_id', '')

        if not user_id:
            return HttpResponse('Missing user_id', status=400)

        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralService import ReferralService

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Commission trigger
            earned = Decimal(str(payout))
            results = ReferralService.process_multilevel_commission(
                earner=user,
                earned_amount=earned,
                source_type='offer',
                source_id=str(offer_id),
            )

            logger.info(
                f'[Webhook] Offer complete: user={user_id} '
                f'offer={offer_id} payout={payout} '
                f'commissions={len(results)}'
            )

            return JsonResponse({
                'status': 'ok',
                'commissions_processed': len(results),
            })

        except Exception as e:
            logger.error(f'[Webhook] Error: {e}')
            return HttpResponse('Internal Server Error', status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TaskCompletionWebhook(View):
    """
    POST /api/referral/webhooks/task-complete/
    Internal task completion → commission trigger।
    """

    def post(self, request, *args, **kwargs):
        import json

        # Internal only: check IP whitelist
        client_ip = request.META.get('REMOTE_ADDR', '')
        allowed_ips = getattr(settings, 'REFERRAL_WEBHOOK_ALLOWED_IPS', ['127.0.0.1'])
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning(f'[Webhook] Blocked IP: {client_ip}')
            return HttpResponse('Forbidden', status=403)

        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponse('Bad Request', status=400)

        user_id = data.get('user_id')
        task_id = data.get('task_id', '')
        earned_amount = data.get('earned_amount', '0')

        if not user_id or not earned_amount:
            return HttpResponse('Missing fields', status=400)

        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralService import ReferralService

            User = get_user_model()
            user = User.objects.get(id=user_id)

            results = ReferralService.process_multilevel_commission(
                earner=user,
                earned_amount=Decimal(str(earned_amount)),
                source_type='task',
                source_id=str(task_id),
            )

            return JsonResponse({
                'status': 'ok',
                'commissions_processed': len(results),
            })

        except Exception as e:
            logger.error(f'[Webhook] Task commission error: {e}')
            return HttpResponse('Internal Server Error', status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WithdrawalWebhook(View):
    """
    POST /api/referral/webhooks/withdrawal/
    User withdrawal এ commission trigger করো।
    """

    def post(self, request, *args, **kwargs):
        import json

        client_ip = request.META.get('REMOTE_ADDR', '')
        allowed_ips = getattr(settings, 'REFERRAL_WEBHOOK_ALLOWED_IPS', ['127.0.0.1'])
        if allowed_ips and client_ip not in allowed_ips:
            return HttpResponse('Forbidden', status=403)

        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponse('Bad Request', status=400)

        user_id = data.get('user_id')
        amount = data.get('amount', '0')
        transaction_id = data.get('transaction_id', '')

        if not user_id:
            return HttpResponse('Missing user_id', status=400)

        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralService import ReferralService

            User = get_user_model()
            user = User.objects.get(id=user_id)

            results = ReferralService.process_multilevel_commission(
                earner=user,
                earned_amount=Decimal(str(amount)),
                source_type='withdrawal',
                source_id=str(transaction_id),
            )

            return JsonResponse({
                'status': 'ok',
                'commissions_processed': len(results),
            })

        except Exception as e:
            logger.error(f'[Webhook] Withdrawal commission error: {e}')
            return HttpResponse('Internal Server Error', status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SignupWebhook(View):
    """
    POST /api/referral/webhooks/signup/
    External signup notification → referral process করো।
    """

    def post(self, request, *args, **kwargs):
        import json

        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponse('Bad Request', status=400)

        user_id = data.get('user_id')
        referral_code = data.get('referral_code')

        if not user_id or not referral_code:
            return HttpResponse('Missing fields', status=400)

        try:
            from django.contrib.auth import get_user_model
            from api.referral.services.ReferralCodeService import ReferralCodeService
            from api.referral.services.ReferralService import ReferralService

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Validate code
            result = ReferralCodeService.validate_code(referral_code)
            if not result['valid']:
                return JsonResponse({
                    'status': 'error',
                    'reason': result.get('error', 'Invalid code'),
                }, status=400)

            referrer = result['user']
            ip = request.META.get('REMOTE_ADDR', '')

            signup_result = ReferralService.process_signup_with_fraud_check(
                new_user=user,
                referrer=referrer,
                new_user_ip=ip,
                referrer_ip=None,
            )

            return JsonResponse({'status': 'ok', **signup_result})

        except Exception as e:
            logger.error(f'[Webhook] Signup error: {e}')
            return HttpResponse('Internal Server Error', status=500)