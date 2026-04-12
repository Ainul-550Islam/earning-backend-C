"""
SmartLink Facebook/Meta Pixel Integration
World #1 Feature: Automatic Facebook Pixel + Conversions API (CAPI) firing.
Publishers can track conversions back to FB campaigns automatically.
"""
import hashlib
import logging
import threading
from typing import Optional
import requests
from django.conf import settings

logger = logging.getLogger('smartlink.integrations.facebook')


class FacebookPixelService:
    """
    Fire Facebook Pixel events and Meta Conversions API (server-side).
    Used when publisher has Facebook tracking enabled on their SmartLink.
    """
    CAPI_URL = "https://graph.facebook.com/v19.0/{pixel_id}/events"

    def fire_page_view(self, pixel_id: str, access_token: str, event_data: dict):
        """Fire PageView event via CAPI on SmartLink click."""
        self._fire_event_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='PageView',
            event_data=event_data,
        )

    def fire_lead(self, pixel_id: str, access_token: str, event_data: dict):
        """Fire Lead event via CAPI on conversion."""
        self._fire_event_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='Lead',
            event_data=event_data,
        )

    def fire_purchase(self, pixel_id: str, access_token: str,
                      event_data: dict, value: float, currency: str = 'USD'):
        """Fire Purchase event with payout value."""
        event_data['custom_data'] = {
            'value':    value,
            'currency': currency,
        }
        self._fire_event_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='Purchase',
            event_data=event_data,
        )

    def _fire_event_async(self, pixel_id: str, access_token: str,
                          event_name: str, event_data: dict):
        thread = threading.Thread(
            target=self._fire_event,
            args=(pixel_id, access_token, event_name, event_data),
            daemon=True,
        )
        thread.start()

    def _fire_event(self, pixel_id: str, access_token: str,
                    event_name: str, event_data: dict):
        url = self.CAPI_URL.format(pixel_id=pixel_id)

        # Build user data with hashed PII
        user_data = {}
        if event_data.get('ip'):
            user_data['client_ip_address'] = event_data['ip']
        if event_data.get('user_agent'):
            user_data['client_user_agent'] = event_data['user_agent']
        if event_data.get('email'):
            user_data['em'] = self._hash(event_data['email'])
        if event_data.get('phone'):
            user_data['ph'] = self._hash(event_data['phone'])

        import time
        payload = {
            'data': [{
                'event_name':  event_name,
                'event_time':  int(time.time()),
                'action_source': 'website',
                'event_id':    event_data.get('event_id', ''),
                'user_data':   user_data,
                'custom_data': event_data.get('custom_data', {}),
            }],
            'access_token': access_token,
            'test_event_code': event_data.get('test_code'),
        }

        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                logger.debug(f"FB CAPI fired: {event_name} pixel={pixel_id}")
            else:
                logger.warning(f"FB CAPI error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"FB CAPI request failed: {e}")

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.lower().strip().encode()).hexdigest()
