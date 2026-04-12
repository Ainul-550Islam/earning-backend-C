import logging
import time
from django.http import HttpResponseRedirect, HttpResponse
from ...models import RedirectLog
from ...choices import RedirectType
from ...constants import REDIRECT_TIMEOUT_SECONDS

logger = logging.getLogger('smartlink.redirect_service')


class RedirectService:
    """
    Build the final HTTP redirect response for a SmartLink.
    Supports 302, 301, meta-refresh, and JavaScript redirects.
    Also creates the RedirectLog audit record.
    """

    def build_response(self, result: dict, request=None) -> HttpResponse:
        """
        Build Django HTTP response for redirect result.

        Args:
            result: dict from SmartLinkResolverService.resolve()
            request: Django HttpRequest (optional, for logging)

        Returns:
            Django HttpResponse
        """
        url = result['url']
        redirect_type = result.get('redirect_type', RedirectType.HTTP_302)

        if redirect_type == RedirectType.HTTP_302:
            response = HttpResponseRedirect(url)
            response.status_code = 302

        elif redirect_type == RedirectType.HTTP_301:
            response = HttpResponseRedirect(url)
            response.status_code = 301

        elif redirect_type == RedirectType.META_REFRESH:
            response = HttpResponse(self._meta_refresh_html(url))
            response['Content-Type'] = 'text/html'

        elif redirect_type == RedirectType.JAVASCRIPT:
            response = HttpResponse(self._javascript_redirect_html(url))
            response['Content-Type'] = 'text/html'

        else:
            response = HttpResponseRedirect(url)
            response.status_code = 302

        # Security and performance headers
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['X-SmartLink-Offer'] = str(result.get('offer_id', ''))

        return response

    def log_redirect(self, smartlink, result: dict, request, click=None):
        """
        Create a RedirectLog audit record for this redirect.
        Called asynchronously to not block the response.
        """
        try:
            from ...utils import get_client_ip
            ip = get_client_ip(request) if request else result.get('ip', '')

            RedirectLog.objects.create(
                smartlink=smartlink,
                offer_id=result.get('offer_id'),
                click=click,
                ip=ip,
                country=result.get('country', ''),
                device_type=result.get('device_type', ''),
                redirect_type=result.get('redirect_type', '302'),
                destination_url=result['url'],
                status_code=302,
                response_time_ms=result.get('response_time_ms', 0),
                was_cached=result.get('was_cached', False),
                was_fallback=result.get('was_fallback', False),
            )
        except Exception as e:
            logger.warning(f"Failed to create redirect log: {e}")

    def _meta_refresh_html(self, url: str) -> str:
        """Generate HTML page with meta refresh redirect."""
        safe_url = url.replace('"', '%22')
        return f"""<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="0;url={safe_url}">
<title>Redirecting...</title>
</head>
<body>
<p>Redirecting... <a href="{safe_url}">Click here</a> if not redirected.</p>
</body>
</html>"""

    def _javascript_redirect_html(self, url: str) -> str:
        """Generate HTML page with JavaScript redirect."""
        safe_url = url.replace("'", "\\'")
        return f"""<!DOCTYPE html>
<html>
<head><title>Redirecting...</title></head>
<body>
<script>window.location.replace('{safe_url}');</script>
<noscript><meta http-equiv="refresh" content="0;url={safe_url}"></noscript>
</body>
</html>"""
