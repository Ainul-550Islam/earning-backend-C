"""
api/offerwall/webhooks/AppLiftWebhook.py

Handles AppLift (HasOffers/TUNE) conversion postback callbacks.
"""
import logging
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..webhooks.TapjoyWebhook import _fire_sig_fail_alert

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AppLiftWebhookView(View):
    """Handle AppLift (HasOffers) postback conversion callbacks."""

    def get(self, request):
        return self._process(request.GET)

    def post(self, request):
        return self._process(request.POST)

    def _process(self, data):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.AppLiftService import AppLiftService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='applift', status='active')
            service  = AppLiftService(provider)

            try:
                parsed = service.parse_webhook(data)
            except Exception as sig_exc:
                _fire_sig_fail_alert('applift', str(data.get('aff_sub', '')))
                logger.warning(f'[AppLiftWebhook] signature failed: {sig_exc}')
                return HttpResponse('Error: invalid signature', status=401)

            user_id = parsed.get('user_id', '')
            if not user_id:
                logger.warning('[AppLiftWebhook] missing aff_sub (user_id)')
                return HttpResponse('Error: missing user_id', status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f'[AppLiftWebhook] user not found: {user_id}')
                return HttpResponse('Error: user not found', status=400)

            offer = Offer.objects.filter(
                external_offer_id=parsed['offer_id'],
                provider=provider,
            ).first()

            auto_approve = (
                FEATURE_AUTO_APPROVE_CONVERSIONS or
                parsed.get('status') == 'approved' or
                provider.config.get('auto_approve', False)
            )

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"applift_{parsed['conversion_id']}",
                payout_amount=parsed['payout_amount'],
                reward_amount=parsed['reward_amount'],
                postback_data=parsed['provider_data'],
                auto_approve=auto_approve,
            )

            conv = result['conversion']
            logger.info(f"[AppLiftWebhook] conv={conv.conversion_id} created={result.get('created')}")
            return HttpResponse('1', status=200)

        except Exception as exc:
            logger.error(f'[AppLiftWebhook] error: {exc}', exc_info=True)
            return HttpResponse(f'Error: {exc}', status=400)
