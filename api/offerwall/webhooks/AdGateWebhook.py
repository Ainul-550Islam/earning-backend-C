"""
api/offerwall/webhooks/AdGateWebhook.py

FIX: AdGateService.verify_postback() was registered and functional,
but NO webhook view existed — AdGate conversions were silently lost.

Endpoint: GET /api/offerwall/webhooks/adgate/

AdGate GET postback params:
  userid       — our user_id (snuid)
  adgateid     — offer's external_offer_id
  pointvalue   — payout in offer currency
  hash         — SHA-256 signature
  transaction  — unique transaction ID
  subid        — optional sub-identifier
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AdGateWebhookView(View):
    """Handle AdGate Media GET postback callbacks."""

    def get(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.AdGateService import AdGateService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..utils.RewardCalculator import RewardCalculator
            from ..utils.OfferValidator import OfferValidator
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.filter(
                provider_type='adgate', status='active').first()
            if not provider:
                logger.error('[AdGateWebhook] no active adgate provider')
                return HttpResponse('0', status=503)

            service = AdGateService(provider)

            data = {
                'userid':      request.GET.get('userid', ''),
                'adgateid':    request.GET.get('adgateid', ''),
                'pointvalue':  request.GET.get('pointvalue', ''),
                'hash':        request.GET.get('hash', ''),
                'transaction': request.GET.get('transaction', ''),
                'subid':       request.GET.get('subid', ''),
                'timestamp':   request.GET.get('timestamp', ''),
            }

            if not all([data['userid'], data['adgateid'],
                        data['pointvalue'], data['transaction']]):
                logger.warning(f'[AdGateWebhook] missing params: {data}')
                return HttpResponse('0', status=400)

            # Timestamp validation
            if data['timestamp']:
                try:
                    OfferValidator.validate_webhook_timestamp(data['timestamp'])
                except Exception as e:
                    logger.warning(f'[AdGateWebhook] timestamp invalid: {e}')
                    return HttpResponse('0', status=400)

            # Signature verification via AdGateService
            try:
                service.verify_postback(data)
            except Exception as e:
                _fire_sig_alert('adgate')
                logger.warning(f'[AdGateWebhook] sig failed: {e}')
                return HttpResponse('0', status=401)

            payout = Decimal(str(data['pointvalue']))

            # Payout validation
            try:
                OfferValidator(None).validate_payout_amount(payout)
            except Exception as e:
                logger.warning(f'[AdGateWebhook] payout invalid: {e}')
                return HttpResponse('0', status=400)

            # Resolve user + offer
            try:
                user = User.objects.get(id=int(data['userid']))
            except (User.DoesNotExist, ValueError):
                logger.warning(f'[AdGateWebhook] user not found: {data["userid"]}')
                return HttpResponse('0', status=400)

            offer = Offer.objects.filter(
                external_offer_id=str(data['adgateid']),
                provider=provider,
            ).first()

            # Calculate reward
            calc        = RewardCalculator(offer, provider)
            reward_data = calc.calculate_conversion_value(
                payout, user=user)

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"adgate_{data['transaction']}",
                payout_amount=payout,
                reward_amount=Decimal(str(reward_data.get('final_reward', 0))),
                postback_data=data,
                external_tx_id=data['transaction'],
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    provider.config.get('auto_approve', False)
                ),
            )

            logger.info(
                f"[AdGateWebhook] conv={result['conversion'].conversion_id} "
                f"user={data['userid']} created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as e:
            logger.error(f'[AdGateWebhook] unhandled error: {e}', exc_info=True)
            return HttpResponse('0', status=400)


def _fire_sig_alert(provider_type: str):
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
                'message':    f'{provider_type} sig failed {count}x/hr',
                'metadata':   {'provider': provider_type, 'count': count},
            })
    except Exception:
        pass
