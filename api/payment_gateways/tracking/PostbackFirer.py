# api/payment_gateways/tracking/PostbackFirer.py
# Outgoing S2S postback — fires publisher's tracking URL on conversion

import requests
import re
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

MACRO_MAP = {
    '{click_id}':    lambda c: c.click_id_raw,
    '{payout}':      lambda c: str(c.payout),
    '{revenue}':     lambda c: str(c.payout),
    '{cost}':        lambda c: str(c.cost),
    '{offer_id}':    lambda c: str(c.offer_id or ''),
    '{status}':      lambda c: c.status,
    '{country}':     lambda c: c.country_code or '',
    '{device}':      lambda c: c.device_type or '',
    '{currency}':    lambda c: c.currency,
    '{sale_amount}': lambda c: str(c.sale_amount or ''),
    '{sub1}':        lambda c: c.metadata.get('sub1',''),
    '{sub2}':        lambda c: c.metadata.get('sub2',''),
    '{sub3}':        lambda c: c.metadata.get('sub3',''),
    '{transaction_id}': lambda c: c.conversion_id,
}


class PostbackFirer:
    """
    Fires outgoing S2S postback to publisher's tracking platform.
    Called asynchronously after successful conversion.

    Publisher sets their postback URL in account settings:
        https://mytracker.com/postback/?tid={click_id}&payout={payout}&status={status}

    We replace macros and fire the URL via HTTP GET.
    """

    TIMEOUT = 10   # seconds
    MAX_REDIRECTS = 3

    def fire(self, conversion) -> dict:
        """Fire postback to all configured publisher URLs."""
        publisher = conversion.publisher
        if not publisher:
            return {'fired': 0}

        # Get publisher postback URLs
        postback_urls = self._get_postback_urls(publisher, conversion)
        if not postback_urls:
            return {'fired': 0}

        fired = 0
        for url_template in postback_urls:
            try:
                final_url = self._replace_macros(url_template, conversion)
                result    = self._send(final_url)
                self._log_fire(conversion, final_url, result)
                fired += 1
                logger.info(f'Publisher postback fired: {final_url[:80]}... [{result["status_code"]}]')
            except Exception as e:
                logger.error(f'PostbackFirer error: {e}')

        return {'fired': fired}

    def _get_postback_urls(self, publisher, conversion) -> list:
        """Get postback URLs from publisher profile or offer-specific config."""
        urls = []
        # Check publisher profile
        if hasattr(publisher, 'publisher_profile'):
            profile = publisher.publisher_profile
            if hasattr(profile, 'postback_url') and profile.postback_url:
                urls.append(profile.postback_url)

        # Check offer-specific postback
        if conversion.offer and hasattr(conversion.offer, 'publisher_postback_url'):
            if conversion.offer.publisher_postback_url:
                urls.append(conversion.offer.publisher_postback_url)

        return urls

    def _replace_macros(self, url_template: str, conversion) -> str:
        """Replace all supported macros in the URL."""
        url = url_template
        for macro, fn in MACRO_MAP.items():
            try:
                url = url.replace(macro, str(fn(conversion)))
            except Exception:
                url = url.replace(macro, '')
        return url

    def _send(self, url: str) -> dict:
        try:
            resp = requests.get(
                url,
                timeout=self.TIMEOUT,
                allow_redirects=True,
                max_redirects=self.MAX_REDIRECTS,
                headers={'User-Agent': 'PaymentGateway-Postback/1.0'},
            )
            return {'status_code': resp.status_code, 'success': resp.status_code < 400}
        except requests.exceptions.Timeout:
            return {'status_code': 0, 'success': False, 'error': 'timeout'}
        except Exception as e:
            return {'status_code': 0, 'success': False, 'error': str(e)}

    def _log_fire(self, conversion, url: str, result: dict):
        from .models import PostbackLog
        try:
            PostbackLog.objects.create(
                offer=conversion.offer,
                click_id=conversion.click_id_raw,
                raw_url=url[:2000],
                status='success' if result.get('success') else 'failed',
                conversion=conversion,
                response_code=result.get('status_code', 0),
                params={'direction': 'outgoing'},
            )
        except Exception:
            pass
