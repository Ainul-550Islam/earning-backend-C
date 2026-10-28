"""
api/offerwall/webhooks/PersonaWebhook.py

FIX: PersonaService.verify_postback() existed and was registered
but NO webhook view existed — Persona survey conversions were lost.

Endpoint: GET /api/offerwall/webhooks/persona/

Persona.ly GET postback params:
  user_id    — our user identifier
  survey_id  — Persona survey ID
  payout     — payout amount in USD
  hash       — MD5 signature
  status     — 'complete' | 'screenout' | 'quota_full'
"""
import logging
from decimal import Decimal

from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

BILLABLE_STATUSES = {'complete', 'approved'}


@method_decorator(csrf_exempt, name='dispatch')
class PersonaWebhookView(View):
    """Handle Persona.ly survey postback callbacks."""

    def get(self, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.PersonaService import PersonaService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..utils.RewardCalculator import RewardCalculator
            from ..utils.OfferValidator import OfferValidator
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.filter(
                provider_type='persona', status='active').first()
            if not provider:
                logger.error('[PersonaWebhook] no active persona provider')
                return HttpResponse('0', status=503)

            service = PersonaService(provider)

            data = {
                'user_id':   request.GET.get('user_id', ''),
                'survey_id': request.GET.get('survey_id', ''),
                'payout':    request.GET.get('payout', '0'),
                'hash':      request.GET.get('hash', ''),
                'status':    request.GET.get('status', 'complete'),
                'timestamp': request.GET.get('timestamp', ''),
            }

            if not all([data['user_id'], data['survey_id']]):
                return HttpResponse('0', status=400)

            # Only process billable completions
            if data['status'] not in BILLABLE_STATUSES:
                logger.info(
                    f"[PersonaWebhook] non-billable status={data['status']} "
                    f"user={data['user_id']} survey={data['survey_id']}")
                return HttpResponse('1', status=200)  # acknowledge, don't credit

            # Timestamp validation
            if data['timestamp']:
                try:
                    OfferValidator.validate_webhook_timestamp(data['timestamp'])
                except Exception as e:
                    return HttpResponse('0', status=400)

            # Signature verification
            try:
                service.verify_postback(data)
            except Exception as e:
                logger.warning(f'[PersonaWebhook] sig failed: {e}')
                return HttpResponse('0', status=401)

            payout = Decimal(str(data['payout']))

            try:
                user = User.objects.get(id=int(data['user_id']))
            except (User.DoesNotExist, ValueError):
                return HttpResponse('0', status=400)

            # Try to match to an Offer; create ephemeral record if not found
            offer = Offer.objects.filter(
                external_offer_id=str(data['survey_id']),
                provider=provider,
            ).first()

            calc        = RewardCalculator(offer, provider)
            reward_data = calc.calculate_conversion_value(payout, user=user)

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"persona_{data['survey_id']}_{data['user_id']}",
                payout_amount=payout,
                reward_amount=Decimal(str(reward_data.get('final_reward', 0))),
                postback_data=data,
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    provider.config.get('auto_approve', False)
                ),
            )

            logger.info(
                f"[PersonaWebhook] conv={result['conversion'].conversion_id} "
                f"user={data['user_id']} created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as e:
            logger.error(f'[PersonaWebhook] error: {e}', exc_info=True)
            return HttpResponse('0', status=400)
