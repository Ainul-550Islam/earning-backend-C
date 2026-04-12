import logging
from django.views import View
from django.http import HttpResponseRedirect, HttpResponse, Http404
from ..services.core.SmartLinkResolverService import SmartLinkResolverService
from ..services.redirect.RedirectService import RedirectService
from ..services.targeting.GeoTargetingService import GeoTargetingService
from ..services.targeting.DeviceTargetingService import DeviceTargetingService
from ..utils import get_client_ip, get_user_agent, get_referrer, get_accept_language, parse_accept_language
from ..exceptions import (
    SmartLinkNotFound, SmartLinkInactive, NoOfferAvailable, ClickBlocked
)

logger = logging.getLogger('smartlink.public_redirect')


class PublicRedirectView(View):
    """
    Public redirect endpoint — no authentication required.
    GET /go/<slug>/

    Flow:
    1. Extract request context (IP, UA, geo, device)
    2. SmartLinkResolverService.resolve(slug, context) → {url, offer_id, ...}
    3. Build HTTP redirect response
    4. Log redirect async

    Target: <5ms total response time.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resolver = SmartLinkResolverService()
        self.redirect_service = RedirectService()
        self.geo_service = GeoTargetingService()
        self.device_service = DeviceTargetingService()

    def get(self, request, slug: str):
        ip = get_client_ip(request)
        user_agent = get_user_agent(request)
        referrer = get_referrer(request)
        accept_language = get_accept_language(request)

        # Parse geo from IP
        geo = self.geo_service.get_country_from_ip(ip)

        # Parse device from UA
        device_info = self.device_service.parse_user_agent(user_agent)

        # Parse language
        language = parse_accept_language(accept_language) or ''

        # Build request context
        query_params = dict(request.GET)
        # Flatten single-item lists from QueryDict
        flat_params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v
                       for k, v in query_params.items()}

        context = {
            'ip': ip,
            'user_agent': user_agent,
            'referrer': referrer,
            'language': language,
            'country': geo.get('country', ''),
            'region': geo.get('region', ''),
            'city': geo.get('city', ''),
            'isp': geo.get('isp', ''),
            'asn': geo.get('asn', ''),
            'device_type': device_info.get('device_type', 'unknown'),
            'os': device_info.get('os', 'unknown'),
            'browser': device_info.get('browser', 'other'),
            'is_bot': device_info.get('is_bot', False),
            'sub1': flat_params.get('sub1', ''),
            'sub2': flat_params.get('sub2', ''),
            'sub3': flat_params.get('sub3', ''),
            'sub4': flat_params.get('sub4', ''),
            'sub5': flat_params.get('sub5', ''),
            'query_params': flat_params,
        }

        try:
            result = self.resolver.resolve(slug=slug, request_context=context)
            response = self.redirect_service.build_response(result, request)

            # Async redirect log
            self._log_async(slug, result, request)

            return response

        except SmartLinkNotFound:
            raise Http404(f"SmartLink '{slug}' not found.")

        except SmartLinkInactive:
            return HttpResponse("This link is no longer active.", status=410)

        except ClickBlocked:
            return HttpResponse("Access denied.", status=403)

        except NoOfferAvailable:
            from django.conf import settings
            fallback = getattr(settings, 'SMARTLINK_DEFAULT_FALLBACK_URL', 'https://example.com')
            return HttpResponseRedirect(fallback)

        except Exception as e:
            logger.error(f"Unexpected error resolving [{slug}]: {e}", exc_info=True)
            return HttpResponse("An error occurred.", status=500)

    def _log_async(self, slug: str, result: dict, request):
        """Log redirect asynchronously to avoid blocking response."""
        try:
            from ..tasks.click_processing_tasks import log_redirect_async
            log_redirect_async.delay(slug=slug, result=result)
        except Exception:
            pass
