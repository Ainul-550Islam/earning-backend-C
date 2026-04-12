"""
click_tracking/click_redirect.py
──────────────────────────────────
Handles the click tracking redirect flow.

Flow:
  1. User clicks offer link → hits /pe/click/?network=cpalead&offer_id=123&sub_id={user.id}
  2. ClickRedirector generates a ClickLog with a unique click_id
  3. Builds the offer URL with {click_id} macro replaced
  4. Returns a 302 redirect to the offer URL
  5. Network embeds click_id in their tracking → returns it in postback

URL format:
  Inbound:  /api/postback_engine/click/track/?network=cpalead&offer_id=offer123
  Outbound: https://cpalead.com/offer/123?sub1=<click_id>&sub2=<user.id>
"""
from __future__ import annotations
import logging
from typing import Optional
from django.http import HttpResponseRedirect, HttpResponse
from django.utils import timezone
from ..models import AdNetworkConfig, ClickLog
from ..enums import DeviceType
from .click_handler import click_handler

logger = logging.getLogger(__name__)


class ClickRedirector:

    def redirect(
        self,
        request,
        network: AdNetworkConfig,
        offer_id: str,
        offer_url: str,
        user=None,
        sub_id: str = "",
    ) -> HttpResponse:
        """
        Main redirect handler.
        Generates click, builds URL, returns 302.
        """
        ip = self._get_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        referrer = request.META.get("HTTP_REFERER", "")
        country = self._detect_country(request)
        device_type = self._detect_device(user_agent)

        # Generate click log
        click_log = click_handler.generate(
            user=user,
            network=network,
            offer_id=offer_id,
            ip_address=ip,
            user_agent=user_agent,
            device_type=device_type,
            country=country,
            sub_id=sub_id or (str(user.id) if user else ""),
            referrer=referrer,
            utm_source=request.GET.get("utm_source", ""),
            utm_medium=request.GET.get("utm_medium", ""),
            utm_campaign=request.GET.get("utm_campaign", ""),
        )

        # Build redirect URL with macros expanded
        redirect_url = click_handler.build_offer_url(
            base_url=offer_url,
            click_log=click_log,
        )

        logger.info(
            "Click redirect: click_id=%s network=%s offer=%s ip=%s",
            click_log.click_id, network.network_key, offer_id, ip,
        )

        return HttpResponseRedirect(redirect_url)

    @staticmethod
    def _get_ip(request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    @staticmethod
    def _detect_device(user_agent: str) -> str:
        ua = user_agent.lower()
        if any(kw in ua for kw in ("iphone", "android", "mobile", "blackberry")):
            return DeviceType.MOBILE
        if any(kw in ua for kw in ("ipad", "tablet")):
            return DeviceType.TABLET
        if any(kw in ua for kw in ("smart-tv", "smarttv", "appletv", "roku")):
            return DeviceType.TV
        return DeviceType.DESKTOP

    @staticmethod
    def _detect_country(request) -> str:
        # Try CloudFlare country header
        cf_country = request.META.get("HTTP_CF_IPCOUNTRY", "")
        if cf_country and len(cf_country) == 2:
            return cf_country.upper()
        return ""


# Module-level singleton
click_redirector = ClickRedirector()
