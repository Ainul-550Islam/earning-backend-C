"""
SmartLink TikTok Events API Integration
Server-side conversion tracking for TikTok Ads.
Publishers using TikTok traffic can track conversions automatically.
"""
import hashlib
import logging
import threading
import requests
import time
from django.conf import settings

logger = logging.getLogger('smartlink.integrations.tiktok')


class TikTokEventsAPI:
    """
    TikTok Events API (server-side pixel) integration.
    Fires Click and CompletePayment events for TikTok campaign optimization.
    """
    EVENTS_URL = "https://business-api.tiktok.com/open_api/v1.3/event/track/"

    def fire_click_event(self, pixel_id: str, access_token: str, context: dict):
        """Fire ClickButton event when SmartLink is clicked."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='ClickButton',
            context=context,
        )

    def fire_conversion_event(self, pixel_id: str, access_token: str,
                               context: dict, value: float = 0, currency: str = 'USD'):
        """Fire CompletePayment event on conversion."""
        context['value']    = value
        context['currency'] = currency
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='CompletePayment',
            context=context,
        )

    def fire_lead_event(self, pixel_id: str, access_token: str, context: dict):
        """Fire SubmitForm event for lead offers."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='SubmitForm',
            context=context,
        )

    def _fire_async(self, pixel_id: str, access_token: str,
                    event_name: str, context: dict):
        t = threading.Thread(
            target=self._fire,
            args=(pixel_id, access_token, event_name, context),
            daemon=True,
        )
        t.start()

    def _fire(self, pixel_id: str, access_token: str, event_name: str, context: dict):
        user_data = {}
        if context.get('ip'):
            user_data['ip'] = context['ip']
        if context.get('user_agent'):
            user_data['user_agent'] = context['user_agent']
        if context.get('email'):
            user_data['email'] = [self._hash(context['email'])]
        if context.get('phone'):
            user_data['phone_number'] = [self._hash(context['phone'])]
        if context.get('ttclid'):
            user_data['ttclid'] = context['ttclid']

        properties = {}
        if context.get('value'):
            properties['value']    = float(context['value'])
            properties['currency'] = context.get('currency', 'USD')

        payload = {
            'pixel_code': pixel_id,
            'event':      event_name,
            'timestamp':  str(int(time.time())),
            'context': {
                'user':     user_data,
                'ad':       {'callback': context.get('ttclid', '')},
                'page':     {'url': context.get('url', '')},
            },
            'properties': properties,
            'event_id':   context.get('event_id', ''),
        }

        headers = {
            'Access-Token': access_token,
            'Content-Type': 'application/json',
        }

        try:
            resp = requests.post(
                self.EVENTS_URL,
                json={'data': [payload]},
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0:
                    logger.debug(f"TikTok event fired: {event_name} pixel={pixel_id}")
                else:
                    logger.warning(f"TikTok API error: {data.get('message')}")
            else:
                logger.warning(f"TikTok HTTP error: {resp.status_code}")
        except Exception as e:
            logger.warning(f"TikTok event fire failed: {e}")

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.lower().strip().encode()).hexdigest()
