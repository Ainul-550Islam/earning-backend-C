"""
api/offerwall/webhooks/MonlixWebhook.py

Handles Monlix conversion postback callbacks.
"""
import logging
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..webhooks.TapjoyWebhook import _fire_sig_fail_alert

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MonlixWebhookView(View):
    """Handle Monlix postback conversion callbacks."""

    def get(self, request):
        """Monlix sends GET postbacks."""
        return self._process(request.GET)

    def post(self, request):
        """Support POST as well for flexibility."""
        return self._process(request.POST)

    def _process(self, data):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.MonlixService import MonlixService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='monlix', status='active')
            service  = MonlixService(provider)

            parsed = service.parse_webhook(data)

            if not parsed.get('user_id') or not parsed.get('conversion_id'):
                logger.warning('[MonlixWebhook] missing required fields')
                return HttpResponse('Error: missing params', status=400)

            try:
                user = User.objects.get(id=parsed['user_id'])
            except User.DoesNotExist:
                logger.warning(f"[MonlixWebhook] user not found: {parsed['user_id']}")
                return HttpResponse('Error: user not found', status=400)

            offer = Offer.objects.filter(
                external_offer_id=parsed['offer_id'],
                provider=provider,
            ).first()

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"monlix_{parsed['conversion_id']}",
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
            logger.info(f"[MonlixWebhook] conv={conv.conversion_id} created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as exc:
            logger.error(f'[MonlixWebhook] error: {exc}', exc_info=True)
            return HttpResponse(f'Error: {exc}', status=400)
