"""
api/offerwall/webhooks/LiftoffWebhook.py

Handles Liftoff (Vungle) conversion postback callbacks.
"""
import logging
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class LiftoffWebhookView(View):
    """Handle Liftoff/Vungle postback conversion callbacks."""

    def post(self, request):
        return self._process(request)

    def get(self, request):
        return self._process(request)

    def _process(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.LiftoffService import LiftoffService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='liftoff', status='active')
            service  = LiftoffService(provider)

            # Liftoff sends JSON body for POST
            if request.method == 'POST' and request.content_type == 'application/json':
                import json
                try:
                    data = json.loads(request.body)
                except Exception:
                    data = dict({k: v[0] if isinstance(v, list) else v for k, v in request.POST.items()})
            else:
                data = {k: v[0] if isinstance(v, list) else v
                        for k, v in (request.GET or request.POST).items()}

            # Verify signature from header
            signature = request.headers.get('X-Vungle-Signature', '')
            if signature and request.body:
                try:
                    service.verify_webhook_signature(request.body, signature)
                except Exception as sig_exc:
                    logger.warning(f'[LiftoffWebhook] signature failed: {sig_exc}')
                    return JsonResponse({'error': 'invalid signature'}, status=401)

            parsed = service.parse_webhook(data)

            user_id = parsed.get('user_id', '')
            if not user_id:
                logger.warning('[LiftoffWebhook] missing ext_user_id')
                return HttpResponse('Error: missing user_id', status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f'[LiftoffWebhook] user not found: {user_id}')
                return HttpResponse('Error: user not found', status=400)

            offer = Offer.objects.filter(
                external_offer_id=parsed['offer_id'],
                provider=provider,
            ).first()

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"liftoff_{parsed['conversion_id']}",
                payout_amount=parsed['payout_amount'],
                reward_amount=parsed['reward_amount'],
                postback_data=parsed['provider_data'],
                auto_approve=True,  # Liftoff only sends approved
            )

            conv = result['conversion']
            logger.info(f"[LiftoffWebhook] conv={conv.conversion_id} created={result.get('created')}")
            return JsonResponse({'status': 'ok'}, status=200)

        except Exception as exc:
            logger.error(f'[LiftoffWebhook] error: {exc}', exc_info=True)
            return HttpResponse(f'Error: {exc}', status=400)
