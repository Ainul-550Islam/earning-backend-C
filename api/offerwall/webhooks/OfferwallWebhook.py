"""
api/offerwall/webhooks/OfferwallWebhook.py  (OfferToro)

Fixes applied:
  1. OfferValidator.validate_webhook_signature() wired
  2. OfferValidator.validate_webhook_timestamp() wired
  3. FEATURE_AUTO_APPROVE_CONVERSIONS respected
  4. AlertAdapter on sig failures
  5. IP whitelist validation added
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class OfferwallWebhookView(View):
    """Handle OfferToro postback."""

    def get(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.OfferwallService import OfferwallService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..utils.RewardCalculator import RewardCalculator
            from ..utils.OfferValidator import OfferValidator
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(
                provider_type='offerwall', status='active')
            service  = OfferwallService(provider)

            # FIX 5: IP whitelist validation
            if provider.ip_whitelist:
                client_ip = (
                    request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                    or request.META.get('REMOTE_ADDR', '')
                )
                try:
                    OfferValidator.validate_ip_whitelist(
                        client_ip, provider.ip_whitelist)
                except Exception as e:
                    logger.warning(f'[OfferwallWebhook] IP blocked: {client_ip}: {e}')
                    return HttpResponse('0', status=403)

            data = {
                'oid':     request.GET.get('oid'),
                'user_id': request.GET.get('user_id'),
                'amount':  request.GET.get('amount'),
                'sig':     request.GET.get('sig'),
                'ts':      request.GET.get('ts', ''),
            }

            if not all([data['oid'], data['user_id'], data['amount']]):
                return HttpResponse('0', status=400)

            # FIX 2: validate_webhook_timestamp()
            if data['ts']:
                try:
                    OfferValidator.validate_webhook_timestamp(data['ts'])
                except Exception as e:
                    logger.warning(f'[OfferwallWebhook] timestamp invalid: {e}')
                    return HttpResponse('0', status=400)

            # FIX 1: validate_webhook_signature()
            try:
                OfferValidator.validate_webhook_signature(
                    data=data,
                    signature=data.get('sig', ''),
                    secret_key=provider.secret_key or '',
                )
            except Exception as e:
                _fire_sig_fail_alert('offertoro', data.get('oid', ''))
                logger.warning(f'[OfferwallWebhook] signature failed: {e}')
                return HttpResponse('0', status=401)

            payout = Decimal(str(data['amount']))
            user   = User.objects.get(id=data['user_id'])
            offer  = Offer.objects.filter(
                external_offer_id=data['oid'],
                provider=provider).first()

            calculator  = RewardCalculator(offer, provider)
            reward_data = calculator.calculate_total_reward(float(payout))

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"offertoro_{data['oid']}_{data['user_id']}",
                payout_amount=payout,
                reward_amount=Decimal(str(reward_data['total_reward'])),
                postback_data=data,
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    provider.config.get('auto_approve', False)
                ),
            )

            logger.info(
                f"[OfferwallWebhook] conv={result['conversion'].conversion_id} "
                f"created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as e:
            logger.error(f'[OfferwallWebhook] error: {e}', exc_info=True)
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
