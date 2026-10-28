"""
api/offerwall/webhooks/OGAdsWebhook.py

Handles OGAds conversion postback callbacks.
"""
import logging
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..webhooks.TapjoyWebhook import _fire_sig_fail_alert

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class OGAdsWebhookView(View):
    """Handle OGAds postback conversion callbacks."""

    def get(self, request):
        return self._process(request.GET)

    def post(self, request):
        return self._process(request.POST)

    def _process(self, data):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.OGAdsService import OGAdsService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='ogads', status='active')
            service  = OGAdsService(provider)

            try:
                parsed = service.parse_webhook(data)
            except Exception as sig_exc:
                _fire_sig_fail_alert('ogads', str(data.get('aff_sub', '')))
                logger.warning(f'[OGAdsWebhook] signature failed: {sig_exc}')
                return HttpResponse('Error: invalid signature', status=401)

            user_id = parsed.get('user_id', '')
            if not user_id:
                logger.warning('[OGAdsWebhook] missing user_id (sub1)')
                return HttpResponse('Error: missing user_id', status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f'[OGAdsWebhook] user not found: {user_id}')
                return HttpResponse('Error: user not found', status=400)

            offer = Offer.objects.filter(
                external_offer_id=parsed['offer_id'],
                provider=provider,
            ).first()

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"ogads_{parsed['conversion_id']}",
                payout_amount=parsed['payout_amount'],
                reward_amount=parsed['reward_amount'],
                postback_data=parsed['provider_data'],
                auto_approve=(
                    FEATURE_AUTO_APPROVE_CONVERSIONS or
                    parsed.get('status') == 'approved' or
                    provider.config.get('auto_approve', False)
                ),
            )

            conv = result['conversion']
            logger.info(f"[OGAdsWebhook] conv={conv.conversion_id} created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as exc:
            logger.error(f'[OGAdsWebhook] error: {exc}', exc_info=True)
            return HttpResponse(f'Error: {exc}', status=400)
