"""
SmartLink Public Redirect View
================================
GET /go/<slug>/

The only public (no-auth) entry point into the SmartLink platform.

Redirect flow:
  1. Extract request context (IP, UA, geo, device, sub-IDs)
  2. SmartLinkResolverService.resolve(slug, context) → {url, offer_id, ...}
  3. Check SmartLink-level gates: expiry, password protection
  4. Pre-lander gate: if SmartLink has an active pre-lander, redirect there first
     (pre-lander passes through to the offer via its own pass-through URL)
  5. Landing page A/B split: if configured, route to selected landing page
  6. Build HTTP redirect response (302/301/meta-refresh/JS)
  7. Log redirect asynchronously

Target: <5ms total response time (step 7 is async, never blocks).
"""
import logging
from django.views import View
from django.http import HttpResponseRedirect, HttpResponse, Http404

from api.smartlink.services.core.SmartLinkResolverService import SmartLinkResolverService
from ..services.redirect.RedirectService import RedirectService
from ..services.redirect.LandingPageService import LandingPageService
from ..services.targeting.GeoTargetingService import GeoTargetingService
from ..services.targeting.DeviceTargetingService import DeviceTargetingService
from api.smartlink.utils import (
    get_client_ip, get_user_agent, get_referrer,
    get_accept_language, parse_accept_language,
)
from api.smartlink.exceptions import (
    SmartLinkNotFound, SmartLinkInactive, NoOfferAvailable, ClickBlocked,
)


# Push network detection
try:
    from api.smartlink.integrations.push_networks.PushNotificationRouter import (
        PushNotificationRouter as _PushRouter,
    )
    _push_router = _PushRouter()
except Exception:
    _push_router = None
logger = logging.getLogger('smartlink.public_redirect')


class PublicRedirectView(View):
    """
    Public redirect endpoint — no authentication required.
    GET /go/<slug>/

    Handles:
      - Bot detection + fraud scoring (via SmartLinkResolverService)
      - Geo/device targeting evaluation
      - Offer rotation / cap management
      - Pre-lander intercept (show landing page before offer redirect)
      - Password protection gate
      - Expiry check
      - 302/301/meta/JS redirect types
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resolver          = SmartLinkResolverService()
        self.redirect_service  = RedirectService()
        self.landing_page_svc  = LandingPageService()
        self.geo_service       = GeoTargetingService()
        self.device_service    = DeviceTargetingService()

    def get(self, request, slug: str):
        ip             = get_client_ip(request)
        user_agent     = get_user_agent(request)
        referrer       = get_referrer(request)
        accept_language = get_accept_language(request)

        # Parse geo from IP
        geo = self.geo_service.get_country_from_ip(ip)

        # Parse device from UA
        device_info = self.device_service.parse_user_agent(user_agent)

        # Parse language
        language = parse_accept_language(accept_language) or ''

        # Flatten QueryDict → plain dict
        query_params = dict(request.GET)
        flat_params = {
            k: v[0] if isinstance(v, list) and len(v) == 1 else v
            for k, v in query_params.items()
        }

        # Build full request context
        context = {
            'ip':          ip,
            'user_agent':  user_agent,
            'referrer':    referrer,
            'language':    language,
            'country':     geo.get('country', ''),
            'region':      geo.get('region', ''),
            'city':        geo.get('city', ''),
            'isp':         geo.get('isp', ''),
            'asn':         geo.get('asn', ''),
            'device_type': device_info.get('device_type', 'unknown'),
            'os':          device_info.get('os', 'unknown'),
            'browser':     device_info.get('browser', 'other'),
            'is_bot':      device_info.get('is_bot', False),
            'sub1':        flat_params.get('sub1', ''),
            'sub2':        flat_params.get('sub2', ''),
            'sub3':        flat_params.get('sub3', ''),
            'sub4':        flat_params.get('sub4', ''),
            'sub5':        flat_params.get('sub5', ''),
            'gclid':       flat_params.get('gclid', ''),
            'fbclid':      flat_params.get('fbclid', ''),
            'ttclid':      flat_params.get('ttclid', ''),
            'query_params': flat_params,
            'slug':        slug,
        }

        # Detect push network traffic and enrich context
        if _push_router is not None:
            try:
                push_info = _push_router.detect_push_traffic(flat_params, context)
                if push_info.get('is_push'):
                    context['traffic_source']   = push_info.get('network', 'push')
                    context['push_click_id']    = push_info.get('click_id', '')
                    context['is_push_traffic']  = True
            except Exception:
                pass

        try:
            result     = self.resolver.resolve(slug=slug, request_context=context)
            smartlink  = result.get('_smartlink')

            # ── Gate 1: Expiry ────────────────────────────────────────────────
            if smartlink and smartlink.is_expired:
                return HttpResponse(
                    "This link has expired.",
                    status=410,
                    content_type='text/plain',
                )

            # ── Gate 2: Password protection ───────────────────────────────────
            if smartlink and smartlink.is_password_protected:
                submitted = (
                    request.GET.get('p', '')
                    or request.META.get('HTTP_X_SMARTLINK_PASS', '')
                )
                if not smartlink.check_access_password(submitted):
                    return HttpResponse(
                        'Password required. Add ?p=<password> to the URL.',
                        status=401,
                        content_type='text/plain',
                    )

            # ── Gate 3: Pre-lander intercept ──────────────────────────────────
            # If the SmartLink has an active pre-lander, redirect the visitor
            # there first. The pre-lander then passes through to the final offer
            # URL via its own mechanism. This allows custom landing pages,
            # pre-sell pages, survey funnels, etc., to run before the offer.
            #
            # Bypass the pre-lander if:
            #   - The request carries ?skip_prelander=1 (for pass-through)
            #   - The result is already a fallback URL (no offer matched)
            if (
                smartlink
                and not result.get('was_fallback', False)
                and not flat_params.get('skip_prelander')
            ):
                pre_lander = self.landing_page_svc.select_pre_lander(smartlink)
                if pre_lander:
                    # Record view async
                    self._record_pre_lander_view_async(pre_lander.pk)
                    # Build pre-lander URL with tracking params
                    pre_lander_url = self.landing_page_svc.build_pre_lander_url(
                        pre_lander, {**context, 'slug': slug}
                    )
                    logger.debug(
                        f"Pre-lander intercept: [{slug}] → {pre_lander_url[:80]}"
                    )
                    response = HttpResponseRedirect(pre_lander_url)
                    response['Cache-Control'] = 'no-store, no-cache'
                    response['X-Robots-Tag']  = 'noindex, nofollow'
                    return response

            # ── Gate 4: Landing page A/B split ────────────────────────────────
            # If the SmartLink has multiple landing pages configured (A/B split),
            # route the visitor to the selected one instead of the offer URL.
            # The landing page then redirects to the offer via its own CTA.
            #
            # Only applies when the SmartLink has landing_pages configured AND
            # the result is not a fallback (we have a real offer to land on).
            if (
                smartlink
                and not result.get('was_fallback', False)
                and not flat_params.get('skip_landing')
            ):
                landing_page = self.landing_page_svc.select_landing_page(smartlink)
                if landing_page:
                    # Record view async
                    self._record_landing_page_view_async(landing_page.pk)
                    # Build landing page URL
                    landing_url = self.landing_page_svc.build_landing_page_url(
                        landing_page, {**context, 'slug': slug}
                    )
                    logger.debug(
                        f"Landing page A/B: [{slug}] → {landing_url[:80]}"
                    )
                    response = HttpResponseRedirect(landing_url)
                    response['Cache-Control'] = 'no-store, no-cache'
                    response['X-Robots-Tag']  = 'noindex, nofollow'
                    return response

            # ── Final: Build redirect response ────────────────────────────────
            response = self.redirect_service.build_response(result, request)

            # Log redirect asynchronously (never blocks response)
            self._log_redirect_async(slug, result, request)

            return response

        except SmartLinkNotFound:
            raise Http404(f"SmartLink '{slug}' not found.")

        except SmartLinkInactive:
            return HttpResponse(
                "This link is no longer active.",
                status=410,
                content_type='text/plain',
            )

        except ClickBlocked:
            return HttpResponse(
                "Access denied.",
                status=403,
                content_type='text/plain',
            )

        except NoOfferAvailable:
            from django.conf import settings
            fallback = getattr(
                settings, 'SMARTLINK_DEFAULT_FALLBACK_URL', 'https://example.com'
            )
            return HttpResponseRedirect(fallback)

        except Exception as exc:
            logger.error(
                f"Unexpected error resolving [{slug}]: {exc}",
                exc_info=True,
            )
            return HttpResponse(
                "An error occurred.",
                status=500,
                content_type='text/plain',
            )

    # ── Async helpers (fire-and-forget) ───────────────────────────────────────

    def _log_redirect_async(self, slug: str, result: dict, request):
        """Log redirect to DB asynchronously via Celery."""
        try:
            from api.smartlink.tasks.click_processing_tasks import log_redirect_async
            log_redirect_async.delay(slug=slug, result=result)
        except Exception as exc:
            logger.debug(f"Redirect log task failed: {exc}")

    def _record_pre_lander_view_async(self, pre_lander_pk: int):
        """Increment pre-lander view counter without blocking the response."""
        try:
            from api.smartlink.models.redirect import PreLander
            from django.db.models import F
            PreLander.objects.filter(pk=pre_lander_pk).update(
                views=F('views') + 1
            )
        except Exception as exc:
            logger.debug(f"Pre-lander view count update failed: {exc}")

    def _record_landing_page_view_async(self, landing_page_pk: int):
        """Increment landing page view counter without blocking the response."""
        try:
            from api.smartlink.models.redirect import LandingPage
            from django.db.models import F
            LandingPage.objects.filter(pk=landing_page_pk).update(
                views=F('views') + 1
            )
        except Exception as exc:
            logger.debug(f"Landing page view count update failed: {exc}")
