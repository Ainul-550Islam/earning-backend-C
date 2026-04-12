"""
SmartLink Snapchat Conversions API Integration
Server-side conversion tracking for Snapchat Ads.
"""
import hashlib
import logging
import threading
import requests
import time
from django.conf import settings

logger = logging.getLogger('smartlink.integrations.snapchat')


class SnapchatConversionsAPI:
    """Fire conversion events to Snapchat CAPI for publisher campaign tracking."""

    CAPI_URL = "https://tr.snapchat.com/v2/conversion"

    def fire_page_view(self, pixel_id: str, token: str, context: dict):
        self._fire_async('PAGE_VIEW', pixel_id, token, context)

    def fire_purchase(self, pixel_id: str, token: str, context: dict,
                       value: float = 0, currency: str = 'USD'):
        context.update({'value': value, 'currency': currency})
        self._fire_async('PURCHASE', pixel_id, token, context)

    def fire_sign_up(self, pixel_id: str, token: str, context: dict):
        self._fire_async('SIGN_UP', pixel_id, token, context)

    def _fire_async(self, event_type: str, pixel_id: str, token: str, context: dict):
        t = threading.Thread(
            target=self._fire,
            args=(event_type, pixel_id, token, context),
            daemon=True,
        )
        t.start()

    def _fire(self, event_type: str, pixel_id: str, token: str, context: dict):
        hashed_email = self._hash(context.get('email', ''))
        hashed_phone = self._hash(context.get('phone', ''))
        hashed_ip    = self._hash(context.get('ip', ''))

        payload = {
            'pixel_id':  pixel_id,
            'timestamp': int(time.time() * 1000),
            'event_conversion_type': 'WEB',
            'event_type': event_type,
            'hashed_email':  hashed_email,
            'hashed_phone_number': hashed_phone,
            'hashed_ip_address':   hashed_ip,
            'user_agent':  context.get('user_agent', ''),
            'page_url':    context.get('url', ''),
        }

        if context.get('value'):
            payload['price']    = float(context['value'])
            payload['currency'] = context.get('currency', 'USD')

        if context.get('snap_click_id'):
            payload['click_id'] = context['snap_click_id']

        try:
            resp = requests.post(
                self.CAPI_URL,
                json={'data': [payload]},
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                },
                timeout=5,
            )
            if resp.status_code == 200:
                logger.debug(f"Snapchat CAPI fired: {event_type}")
            else:
                logger.warning(f"Snapchat CAPI error: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"Snapchat CAPI failed: {e}")

    def _hash(self, value: str) -> str:
        if not value:
            return ''
        return hashlib.sha256(value.lower().strip().encode()).hexdigest()
