"""
api/offerwall/webhooks/TapjoyWebhook.py

Fixes applied:
  1. OfferValidator.validate_webhook_signature() now called (was floating)
  2. OfferValidator.validate_webhook_timestamp() now called (was floating)
  3. FEATURE_AUTO_APPROVE_CONVERSIONS constant respected (was hardcoded)
  4. AlertAdapter triggered on repeated signature failures
  5. validate_payout_amount() called before processing
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

_SIGNATURE_FAIL_KEY = 'tapjoy_sig_fail_count'


@method_decorator(csrf_exempt, name='dispatch')
class TapjoyWebhookView(View):
    """Handle Tapjoy postback callbacks."""

    def post(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.TapjoyService import TapjoyService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..utils.RewardCalculator import RewardCalculator
            from ..utils.OfferValidator import OfferValidator
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='tapjoy', status='active')
            service  = TapjoyService(provider)

            data = {
                'id':       request.POST.get('id'),
                'snuid':    request.POST.get('snuid'),
                'currency': request.POST.get('currency'),
                'verifier': request.POST.get('verifier'),
                'timestamp':request.POST.get('timestamp', ''),
            }

            if not all([data['id'], data['snuid'], data['currency']]):
                return HttpResponse('Error: missing params', status=400)

            # FIX 1: validate_webhook_timestamp() was floating — now called
            if data['timestamp']:
                try:
                    OfferValidator.validate_webhook_timestamp(data['timestamp'])
                except Exception as e:
                    logger.warning(f'[TapjoyWebhook] timestamp invalid: {e}')
                    return HttpResponse(f'Error: {e}', status=400)

            # FIX 2: validate_webhook_signature() was floating — now called
            try:
                OfferValidator.validate_webhook_signature(
                    data=data,
                    signature=data.get('verifier', ''),
                    secret_key=provider.secret_key or '',
                )
            except Exception as e:
                # FIX 4: fire alert on repeated signature failures
                _fire_sig_fail_alert('tapjoy', data.get('id', ''))
                logger.warning(f'[TapjoyWebhook] signature failed: {e}')
                return HttpResponse('Error: invalid signature', status=401)

            user_id  = data['snuid']
            offer_id = data['id']
            payout   = Decimal(str(data['currency']))

            # FIX 5: validate_payout_amount
            try:
                OfferValidator.validate_payout_amount(None, payout)  # static-like
            except Exception as e:
                logger.warning(f'[TapjoyWebhook] payout invalid: {e}')
                return HttpResponse(f'Error: {e}', status=400)

            user  = User.objects.get(id=user_id)
            offer = Offer.objects.filter(
                external_offer_id=offer_id, provider=provider).first()

            calculator  = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(float(payout))

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f'tapjoy_{offer_id}_{user_id}',
                payout_amount=payout,
                reward_amount=Decimal(str(reward_data['total_reward'])),
                postback_data=data,
                # FIX 3: respect feature flag, not hardcoded provider config only
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    provider.config.get('auto_approve', False)
                ),
            )

            conv = result['conversion']
            logger.info(
                f'[TapjoyWebhook] conv={conv.conversion_id} '
                f'created={result.get("created")}')
            return HttpResponse('OK', status=200)

        except Exception as e:
            logger.error(f'[TapjoyWebhook] error: {e}', exc_info=True)
            return HttpResponse(f'Error: {e}', status=400)


def _fire_sig_fail_alert(provider_type, offer_id):
    """Fire AlertAdapter on repeated signature failures."""
    try:
        from django.core.cache import cache
        key   = f'sig_fail:{provider_type}'
        count = cache.get(key, 0) + 1
        cache.set(key, count, 3600)
        if count >= 5:
            from ..services.adapters.OfferwallAdapter import OfferwallAdapterFactory
            OfferwallAdapterFactory.get('alerts').send({
                'alert_type': 'signature_failure_spike',
                'severity':   'high',
                'message':    (f'{provider_type} webhook signature failed '
                               f'{count} times in 1 hour'),
                'metadata':   {'provider': provider_type,
                               'offer_id': offer_id, 'count': count},
            })
    except Exception:
        pass
