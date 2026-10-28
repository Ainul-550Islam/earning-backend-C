"""
api/offerwall/webhooks/FyberWebhook.py

Handles Fyber (Digital Turbine) server-side reward callback.
"""
import logging
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class FyberWebhookView(View):
    """Handle Fyber server-side reward callbacks."""

    def get(self, request):
        """Fyber sends GET callbacks."""
        return self._process(request.GET, request)

    def _process(self, data, request):
        try:
            from ..models import OfferProvider, Offer
            from api.users.models import User
            from ..services.FyberService import FyberService
            from ..services.OfferwallIntegrationService import OfferwallIntegrationService
            from ..constants import FEATURE_AUTO_APPROVE_CONVERSIONS

            provider = OfferProvider.objects.get(provider_type='fyber', status='active')
            service  = FyberService(provider)

            parsed = service.parse_webhook(data)

            user_id = parsed.get('user_id', '')
            if not user_id:
                logger.warning('[FyberWebhook] missing uid')
                return HttpResponse('MISSING_UID', status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f'[FyberWebhook] user not found: {user_id}')
                return HttpResponse('USER_NOT_FOUND', status=400)

            offer = Offer.objects.filter(
                external_offer_id=parsed['offer_id'],
                provider=provider,
            ).first()

            result = OfferwallIntegrationService.process_conversion(
                offer=offer,
                user=user,
                conversion_id=f"fyber_{parsed['conversion_id']}",
                payout_amount=parsed['payout_amount'],
                reward_amount=parsed['reward_amount'],
                postback_data=parsed['provider_data'],
                auto_approve=True,  # Fyber only sends approved
            )

            conv = result['conversion']
            logger.info(f"[FyberWebhook] conv={conv.conversion_id} created={result.get('created')}")
            # Fyber expects "OK" or empty 200
            return HttpResponse('OK', status=200)

        except Exception as exc:
            logger.error(f'[FyberWebhook] error: {exc}', exc_info=True)
            return HttpResponse(f'Error: {exc}', status=400)
