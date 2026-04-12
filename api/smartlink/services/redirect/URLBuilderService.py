import logging
from ...utils import build_tracking_url, sanitize_sub_id
from .TrackingPixelService import TrackingPixelService

logger = logging.getLogger('smartlink.url_builder')


class URLBuilderService:
    """
    Construct the final offer redirect URL with all tracking parameters.
    Appends sub1-sub5, click ID, and publisher tokens to the offer's base URL.
    """

    def build(self, offer, smartlink, request_context: dict) -> str:
        """
        Build the final redirect URL for an offer.

        Args:
            offer: Offer model instance
            smartlink: SmartLink model instance
            request_context: full request context dict

        Returns:
            Final URL string with all tracking params appended
        """
        base_url = offer.tracking_url or offer.url

        # Build tracking params
        params = {}

        # Publisher sub IDs
        for i in range(1, 6):
            val = request_context.get(f'sub{i}', '')
            if val:
                params[f'sub{i}'] = sanitize_sub_id(str(val))

        # SmartLink identifier
        params['sl_id'] = smartlink.slug

        # Publisher ID
        params['pub_id'] = str(smartlink.publisher_id)

        # Country + device (for offer-side tracking)
        if request_context.get('country'):
            params['geo'] = request_context['country']

        if request_context.get('device_type'):
            params['device'] = request_context['device_type']

        # Custom params passthrough
        custom_params = request_context.get('custom_params', {})
        if isinstance(custom_params, dict):
            for k, v in custom_params.items():
                if k not in params:
                    params[k] = sanitize_sub_id(str(v))

        # Build final URL
        final_url = build_tracking_url(base_url, params)

        logger.debug(
            f"URL built: offer#{offer.pk} sl=[{smartlink.slug}] "
            f"params={list(params.keys())}"
        )
        return final_url

    def build_postback_url(self, offer, click_id: int, payout: float) -> str:
        """
        Build the S2S postback URL to fire when conversion is reported.
        """
        from django.conf import settings
        base = getattr(settings, 'SMARTLINK_POSTBACK_URL', '/postback/')
        params = {
            'click_id': str(click_id),
            'payout': str(payout),
            'offer_id': str(offer.pk),
        }
        return build_tracking_url(base, params)
