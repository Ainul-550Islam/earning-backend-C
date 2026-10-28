"""
api/offerwall/webhooks/AdGemWebhook.py

Fixes applied:
  1. OfferValidator.validate_webhook_signature() wired
  2. OfferValidator.validate_webhook_timestamp() wired
  3. FEATURE_AUTO_APPROVE_CONVERSIONS respected
  4. validate_payout_amount() called
  5. AlertAdapter on sig failures
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdGemWebhookView(View):
    """Handle AdGem GET postback callbacks."""

    def get(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.AdGemService import AdGemService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..utils.RewardCalculator import RewardCalculator
            from ..utils.OfferValidator import OfferValidator
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='adgem', status='active')
            service  = AdGemService(provider)

            data = {
                'user_id':        request.GET.get('user_id'),
                'offer_id':       request.GET.get('offer_id'),
                'points':         request.GET.get('points'),
                'signature':      request.GET.get('signature'),
                'transaction_id': request.GET.get('transaction_id'),
                'timestamp':      request.GET.get('timestamp', ''),
            }

            if not all([data['user_id'], data['offer_id'],
                        data['points'], data['transaction_id']]):
                return HttpResponse('0', status=400)

            # FIX 1: validate_webhook_timestamp()
            if data['timestamp']:
                try:
                    OfferValidator.validate_webhook_timestamp(data['timestamp'])
                except Exception as e:
                    logger.warning(f'[AdGemWebhook] timestamp invalid: {e}')
                    return HttpResponse('0', status=400)

            # FIX 2: validate_webhook_signature()
            try:
                OfferValidator.validate_webhook_signature(
                    data=data,
                    signature=data.get('signature', ''),
                    secret_key=provider.secret_key or '',
                )
            except Exception as e:
                _fire_sig_fail_alert('adgem', data.get('offer_id', ''))
                logger.warning(f'[AdGemWebhook] signature failed: {e}')
                return HttpResponse('0', status=401)

            payout = Decimal(str(data['points']))

            # FIX 4: validate_payout_amount()
            try:
                OfferValidator(None).validate_payout_amount(payout)
            except Exception as e:
                return HttpResponse('0', status=400)

            user  = User.objects.get(id=data['user_id'])
            offer = Offer.objects.filter(
                external_offer_id=data['offer_id'],
                provider=provider).first()

            calculator  = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(float(payout))

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"adgem_{data['transaction_id']}",
                payout_amount=payout,
                reward_amount=Decimal(str(reward_data['total_reward'])),
                postback_data=data,
                external_tx_id=data['transaction_id'],
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    provider.config.get('auto_approve', False)
                ),
            )

            logger.info(
                f"[AdGemWebhook] conv={result['conversion'].conversion_id} "
                f"created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as e:
            logger.error(f'[AdGemWebhook] error: {e}', exc_info=True)
            return HttpResponse('0', status=400)


def _fire_sig_fail_alert(provider_type, offer_id):
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
                'message':    f'{provider_type} webhook sig failed {count}x/hr',
                'metadata':   {'provider': provider_type, 'count': count},
            })
    except Exception:
        pass
