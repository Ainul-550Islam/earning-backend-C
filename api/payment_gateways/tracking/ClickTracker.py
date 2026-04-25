# api/payment_gateways/tracking/ClickTracker.py
# Records clicks and generates tracking URLs

import re
import logging
from django.utils import timezone
from .models import Click, Impression, generate_click_id
logger = logging.getLogger(__name__)

UA_PATTERNS = {
    'mobile':  r'(Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini)',
    'tablet':  r'(iPad|Android.*Tablet|Kindle|Silk)',
    'bot':     r'(bot|crawl|slurp|spider|facebookexternalhit|WhatsApp)',
}

OS_PATTERNS = {
    'iOS':     r'(iPhone|iPad|iPod)',
    'Android': r'Android',
    'Windows': r'Windows',
    'macOS':   r'(Macintosh|Mac OS)',
    'Linux':   r'Linux',
}


class ClickTracker:
    """
    Records clicks when publisher sends traffic to an offer.

    Usage:
        tracker = ClickTracker()
        click, redirect_url = tracker.track(offer, publisher, request)
        # Redirect user to redirect_url
    """

    def track(self, offer, publisher, request, extra_params: dict = None) -> tuple:
        """
        Record a click and return (Click, redirect_url).

        Args:
            offer:     Offer instance
            publisher: Publisher User instance
            request:   Django HttpRequest
            extra_params: Additional params (sub1-5, traffic_id)

        Returns:
            (Click, redirect_url): Click instance and where to redirect the user
        """
        extra_params = extra_params or {}

        # Parse request data
        ip_address  = self._get_ip(request)
        user_agent  = request.META.get('HTTP_USER_AGENT', '')
        referer     = request.META.get('HTTP_REFERER', '')
        country     = self._get_country(request)
        device_type = self._detect_device(user_agent)
        os_name     = self._detect_os(user_agent)
        is_bot      = self._is_bot(user_agent)

        # Duplicate detection: same IP + offer + publisher within 1 hour
        from datetime import timedelta
        is_duplicate = Click.objects.filter(
            offer=offer,
            publisher=publisher,
            ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).exists()

        # Create click record
        click = Click.objects.create(
            offer        = offer,
            campaign     = getattr(offer, 'active_campaign', None),
            publisher    = publisher,
            advertiser   = offer.advertiser if hasattr(offer, 'advertiser') else None,
            ip_address   = ip_address,
            user_agent   = user_agent[:500],
            referer      = referer[:1000],
            country_code = country,
            device_type  = device_type,
            os_name      = os_name,
            is_bot       = is_bot,
            is_duplicate = is_duplicate,
            sub1         = extra_params.get('sub1', ''),
            sub2         = extra_params.get('sub2', ''),
            sub3         = extra_params.get('sub3', ''),
            sub4         = extra_params.get('sub4', ''),
            sub5         = extra_params.get('sub5', ''),
            traffic_id   = extra_params.get('traffic_id', ''),
            currency     = 'USD',
        )

        # Update offer click count
        if not is_bot and not is_duplicate:
            try:
                from django.db.models import F
                type(offer).objects.filter(id=offer.id).update(total_clicks=F('total_clicks') + 1)
            except Exception:
                pass

        # Build redirect URL with click_id macro
        redirect_url = self._build_redirect_url(offer, click)

        logger.info(f'Click tracked: {click.click_id[:8]}... offer={offer.id} pub={publisher.id}')
        return click, redirect_url

    def track_impression(self, offer, publisher, request) -> Impression:
        ip         = self._get_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        return Impression.objects.create(
            offer        = offer,
            publisher    = publisher,
            ip_address   = ip,
            country_code = self._get_country(request),
            device_type  = self._detect_device(user_agent),
            is_bot       = self._is_bot(user_agent),
        )

    def _build_redirect_url(self, offer, click: Click) -> str:
        """Build advertiser URL with click_id embedded."""
        base_url = getattr(offer, 'tracking_url', '') or getattr(offer, 'destination_url', '')
        if not base_url:
            return '#'

        # Replace standard macros in tracking URL
        url = base_url
        url = url.replace('{click_id}', click.click_id)
        url = url.replace('{CLICK_ID}', click.click_id)
        url = url.replace('{aff_sub}', click.click_id)
        url = url.replace('{sub1}', click.sub1)
        url = url.replace('{country}', click.country_code)
        url = url.replace('{device}', click.device_type)

        # Append click_id if no macro found
        if click.click_id not in url:
            sep = '&' if '?' in url else '?'
            url = f'{url}{sep}click_id={click.click_id}'

        return url

    def _get_ip(self, request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

    def _get_country(self, request) -> str:
        return (
            request.META.get('HTTP_CF_IPCOUNTRY', '')     # Cloudflare
            or request.META.get('HTTP_X_COUNTRY_CODE', '') # Custom header
            or ''
        ).upper()[:2]

    def _detect_device(self, ua: str) -> str:
        if re.search(UA_PATTERNS['bot'],    ua, re.I): return 'other'
        if re.search(UA_PATTERNS['tablet'], ua, re.I): return 'tablet'
        if re.search(UA_PATTERNS['mobile'], ua, re.I): return 'mobile'
        return 'desktop'

    def _detect_os(self, ua: str) -> str:
        for os_name, pattern in OS_PATTERNS.items():
            if re.search(pattern, ua, re.I):
                return os_name
        return ''

    def _is_bot(self, ua: str) -> bool:
        return bool(re.search(UA_PATTERNS['bot'], ua, re.I))
