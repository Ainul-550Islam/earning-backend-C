"""
SmartLink S2S Postback API
Advertisers fire this endpoint when a conversion happens.
URL: /postback/?click_id=123&payout=2.50&offer_id=456&security_token=xxx
"""
from api.smartlink.utils import get_client_ip
import logging
from django.http import HttpResponse
from django.views import View
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger('smartlink.postback')


@method_decorator(csrf_exempt, name='dispatch')
class PostbackView(View):
    """
    S2S postback endpoint — no authentication, token-based security.
    Advertisers call: GET /postback/?click_id={click_id}&payout={payout}&offer_id={offer_id}&token={token}
    """

    def get(self, request):
        return self._process(request)

    def post(self, request):
        return self._process(request)

    def _process(self, request):
        params = request.GET if request.method == 'GET' else request.POST

        click_id    = params.get('click_id', '').strip()
        offer_id    = params.get('offer_id', '').strip()
        payout      = params.get('payout', '0').strip()
        status      = params.get('status', 'approved').strip()
        token       = params.get('token', '').strip()
        transaction = params.get('transaction_id', '').strip()
        sub1        = params.get('sub1', '').strip()

        # ── Security token validation ──────────────────────────────
        if not self._validate_token(offer_id, token):
            logger.warning(f"Postback rejected: invalid token for offer#{offer_id} click#{click_id}")
            return HttpResponse('INVALID_TOKEN', status=403)

        # ── Only process approved conversions ──────────────────────
        if status not in ('approved', 'confirmed', '1', 'true'):
            logger.info(f"Postback ignored: status={status} for click#{click_id}")
            return HttpResponse('IGNORED', status=200)

        # ── Parse payout ────────────────────────────────────────────
        try:
            payout_float = float(payout)
        except (ValueError, TypeError):
            payout_float = 0.0

        # ── Queue attribution task ───────────────────────────────────
        try:
            from ..tasks.click_processing_tasks import attribute_conversion
            attribute_conversion.delay(
                offer_id=int(offer_id) if offer_id.isdigit() else 0,
                sub1=sub1 or click_id,
                ip=self._get_ip(request),
                payout=payout_float,
                transaction_id=transaction,
            )
            logger.info(
                f"Postback queued: click#{click_id} offer#{offer_id} "
                f"payout=${payout_float:.4f} txn={transaction}"
            )
            return HttpResponse('OK', status=200)
        except Exception as e:
            logger.error(f"Postback task queue failed: {e}")
            return HttpResponse('ERROR', status=500)

    def _validate_token(self, offer_id: str, token: str) -> bool:
        """
        Validate postback security token.
        Token = HMAC-SHA256(offer_id + POSTBACK_SECRET_KEY)
        """
        if not token:
            return False
        import hmac, hashlib
        secret = getattr(settings, 'SMARTLINK_POSTBACK_SECRET', 'change-me-in-production')
        expected = hmac.new(
            secret.encode(),
            offer_id.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return hmac.compare_digest(token, expected)

    def _get_ip(self, request) -> str:
        # Single canonical implementation in api.smartlink.utils.get_client_ip
        return get_client_ip(request)


@method_decorator(csrf_exempt, name='dispatch')
class PostbackPixelView(View):
    """
    1×1 pixel postback — for advertisers that fire an image pixel.
    GET /pixel/?click_id=xxx&payout=1.50&offer_id=456
    Returns a 1×1 transparent GIF.

    Also handles impression pixels:
    GET /pixel/?sl=<slug>&offer=<id>&type=impression
    Records an ImpressionLog entry before returning the pixel.
    This is how pre-click view events are tracked for VTR / CTR analytics.
    """
    TRANSPARENT_GIF = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
        b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00'
        b'\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    )

    def get(self, request):
        pixel_type = request.GET.get('type', 'postback')

        if pixel_type == 'impression':
            # SmartLink impression pixel: fired by ad creative before click
            self._record_impression(request)
        else:
            # Standard conversion postback pixel
            PostbackView().get(request)

        response = HttpResponse(self.TRANSPARENT_GIF, content_type='image/gif')
        response['Cache-Control'] = 'no-store, no-cache'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    def _record_impression(self, request):
        """
        Record a pre-click impression fired by an ad creative.
        URL pattern: /pixel/?type=impression&sl=<slug>&offer=<offer_id>&sub1=...
        """
        slug     = request.GET.get('sl', '').strip()
        offer_id = request.GET.get('offer', None)
        if not slug:
            return
        try:
            from api.smartlink.models import SmartLink
            sl = SmartLink.objects.get(slug=slug, is_active=True)
            from ..services.geoip.GeoIPEnricher import GeoIPEnricher
            from ..utils import get_client_ip
            ip = get_client_ip(request)
            geo = GeoIPEnricher().enrich(ip)
            from ..services.click.BotDetectionService import BotDetectionService
            ua = request.META.get('HTTP_USER_AGENT', '')
            is_bot, _ = BotDetectionService().detect(ip, ua)
            context = {
                'ip':          ip,
                'country':     geo.get('country', ''),
                'device_type': request.GET.get('device', geo.get('device_type', '')),
                'os':          request.GET.get('os', ''),
                'browser':     request.GET.get('browser', ''),
                'referrer':    request.META.get('HTTP_REFERER', ''),
                'sub1':        request.GET.get('sub1', ''),
                'sub2':        request.GET.get('sub2', ''),
                '_is_bot':     is_bot,
            }
            from ..services.analytics.ImpressionTrackingService import ImpressionTrackingService
            ImpressionTrackingService().record(
                smartlink=sl,
                context=context,
                offer_id=int(offer_id) if offer_id and offer_id.isdigit() else None,
            )
        except Exception as e:
            import logging
            logging.getLogger('smartlink.pixel').warning(
                f"Impression pixel record failed for slug={slug}: {e}"
            )