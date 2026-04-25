# api/payment_gateways/tracking/PixelTracker.py
# Pixel-based conversion tracking (1x1 image pixel + JS pixel)
# Used when advertisers can't do S2S postback — like Facebook Pixel equivalent

from django.http import HttpResponse
import logging, base64

logger = logging.getLogger(__name__)

# 1x1 transparent GIF pixel (43 bytes)
TRANSPARENT_PIXEL = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)


class PixelTracker:
    """
    JavaScript and image pixel tracking for advertisers.

    Types:
        1. Image pixel:  <img src="/pixel/track/?click_id=XXX&event=purchase">
        2. JS pixel:     <script src="/pixel/js/?click_id=XXX"></script>
        3. Postback URL: Direct server-to-server call

    Used when:
        - Advertiser can't do server-side postback
        - eCommerce stores use JS pixel on thank-you page
        - Mobile apps use image pixel after install

    Advertiser adds to their thank-you/confirmation page:
        <img src="https://yourdomain.com/api/payment/tracking/pixel.gif?click_id=CLICK_ID&event=purchase&amount=AMOUNT" width="1" height="1">
    """

    def track_pixel(self, request) -> HttpResponse:
        """
        Process a 1x1 pixel tracking hit.
        Returns a transparent 1x1 GIF image.

        GET /tracking/pixel.gif?click_id=XXX&event=purchase&amount=99.99
        """
        params   = request.GET
        click_id = params.get('click_id', '')
        event    = params.get('event', 'conversion')
        amount   = params.get('amount', '0')
        status   = params.get('status', 'approved')
        sub1     = params.get('sub1', '')

        if click_id:
            self._process_pixel_event(
                click_id=click_id,
                event=event,
                amount=amount,
                status=status,
                sub1=sub1,
                ip=self._get_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

        # Always return pixel (even if invalid — don't break advertiser's page)
        response = HttpResponse(TRANSPARENT_PIXEL, content_type='image/gif')
        response['Cache-Control']  = 'no-cache, no-store, must-revalidate'
        response['Pragma']         = 'no-cache'
        response['Expires']        = '0'
        response['Content-Length'] = str(len(TRANSPARENT_PIXEL))
        return response

    def track_js_pixel(self, request) -> HttpResponse:
        """
        Returns a JavaScript snippet that fires conversion tracking.
        Advertiser loads this script on their conversion page.

        GET /tracking/pixel.js?click_id=XXX&event=purchase
        """
        click_id = request.GET.get('click_id', '')
        event    = request.GET.get('event', 'conversion')
        amount   = request.GET.get('amount', '0')

        js_code = f'''
(function() {{
  var img = new Image(1,1);
  img.src = '/api/payment/tracking/pixel.gif?click_id={click_id}&event={event}&amount={amount}&ts='+Date.now();
  img.style.display = 'none';
  document.body.appendChild(img);
  // Fire postback
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/payment/tracking/postback/?click_id={click_id}&payout=0&status=approved');
  xhr.send();
}})();
'''
        response = HttpResponse(js_code, content_type='application/javascript')
        response['Cache-Control'] = 'no-cache'
        return response

    def get_pixel_code(self, click_id: str, event: str = 'purchase') -> dict:
        """
        Generate pixel codes for advertiser to embed.
        Returns both image pixel and JavaScript pixel code.
        """
        base_url = 'https://yourdomain.com/api/payment/tracking'

        return {
            'image_pixel': (
                f'<img src="{base_url}/pixel.gif?click_id={{{click_id}}}&event={event}&amount={{AMOUNT}}" '
                f'width="1" height="1" style="display:none;" />'
            ),
            'js_pixel': (
                f'<script src="{base_url}/pixel.js?click_id={{{click_id}}}&event={event}&amount={{AMOUNT}}">'
                f'</script>'
            ),
            'postback_url': (
                f'{base_url}/postback/?click_id={{{click_id}}}&payout={{PAYOUT}}&status=approved'
            ),
            'instructions': [
                'Replace {CLICK_ID} with the actual click_id you received.',
                'Replace {AMOUNT} with the sale amount (for CPS) or 0 for CPA/CPI.',
                'Replace {PAYOUT} with the payout amount, or leave as {payout} for auto.',
                'Add the code to your thank-you/confirmation page.',
                'Test with a real conversion to verify tracking.',
            ],
        }

    def _process_pixel_event(self, click_id: str, event: str, amount: str,
                               status: str, sub1: str, ip: str, user_agent: str):
        """Process pixel event as a postback."""
        from api.payment_gateways.tracking.PostbackEngine import PostbackEngine
        engine = PostbackEngine()
        try:
            engine.process(
                request_params={
                    'click_id': click_id,
                    'payout':   amount,
                    'status':   status,
                    'sub1':     sub1,
                    'event':    event,
                },
                raw_url=f'/pixel.gif?click_id={click_id}&event={event}',
                ip_address=ip,
            )
        except Exception as e:
            logger.warning(f'Pixel tracking failed for click_id={click_id}: {e}')

    def _get_ip(self, request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
