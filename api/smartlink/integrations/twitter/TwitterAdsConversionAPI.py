"""
SmartLink — Twitter / X Ads Conversion API Integration
Fires server-side conversion events to Twitter's Conversion API (CAPI).
Supports web_site_tag events: PageView, Purchase, Lead, SignUp, Download.

Configuration (per SmartLink, stored in integrations JSON field):
    {
        "twitter": {
            "pixel_id": "...",
            "access_token": "...",
            "fire_page_view": true,
            "fire_lead": true,
            "fire_purchase": true,
            "is_active": true
        }
    }

Twitter CAPI docs: https://developer.twitter.com/en/docs/twitter-ads-api/measurement/api-reference/conversions
"""
import json
from api.smartlink.integrations.base import IntegrationBase
import logging
import threading
import time
import urllib.request
import urllib.parse
import hashlib

logger = logging.getLogger('smartlink.integrations.twitter')

TWITTER_CAPI_URL = 'https://ads-api.twitter.com/12/measurement/conversions/{pixel_id}'


class TwitterAdsConversionAPI(IntegrationBase):
    integration_name = "Twitter Ads"
    default_timeout  = 10

    """
    Fire server-side conversion events to Twitter / X Ads Conversion API.

    Methods:
        fire_page_view(pixel_id, access_token, context)   → PageView on SmartLink click
        fire_lead(pixel_id, access_token, context, value) → Lead on conversion postback
        fire_purchase(pixel_id, access_token, context, value) → Purchase on sale postback
        fire_event(pixel_id, access_token, event_name, context, value) → Generic event
    """

    def fire_page_view(self, pixel_id: str, access_token: str, context: dict):
        """Fire PageView event on SmartLink redirect."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='PageView',
            context=context,
            value=None,
        )

    def fire_lead(self, pixel_id: str, access_token: str, context: dict,
                  value: float = 0.0, currency: str = 'USD'):
        """Fire Lead event on CPA conversion."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='Lead',
            context=context,
            value=value,
            currency=currency,
        )

    def fire_purchase(self, pixel_id: str, access_token: str, context: dict,
                      value: float = 0.0, currency: str = 'USD',
                      order_id: str = ''):
        """Fire Purchase event on sale conversion."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='Purchase',
            context=context,
            value=value,
            currency=currency,
            order_id=order_id,
        )

    def fire_sign_up(self, pixel_id: str, access_token: str, context: dict):
        """Fire SignUp / Registration event."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name='SignUp',
            context=context,
            value=None,
        )

    def fire_event(self, pixel_id: str, access_token: str, event_name: str,
                   context: dict, value: float = None, currency: str = 'USD',
                   order_id: str = ''):
        """Fire any supported Twitter conversion event."""
        self._fire_async(
            pixel_id=pixel_id,
            access_token=access_token,
            event_name=event_name,
            context=context,
            value=value,
            currency=currency,
            order_id=order_id,
        )

    def _fire_async(self, **kwargs):
        """Fire the API call in a background thread (non-blocking)."""
        thread = threading.Thread(target=self._send, kwargs=kwargs, daemon=True)
        thread.start()

    def _send(self, pixel_id: str, access_token: str, event_name: str,
              context: dict, value: float = None, currency: str = 'USD',
              order_id: str = ''):
        """
        Build and send the Twitter CAPI payload.
        Hashes PII (email, phone) with SHA-256 before sending.
        """
        event_time = int(time.time())
        ip          = context.get('ip', '')
        user_agent  = context.get('user_agent', '')
        email       = context.get('email', '')
        phone       = context.get('phone', '')
        click_id    = context.get('click_id', '')
        url         = context.get('url', '')

        # Build user identification block
        identifiers = []
        if email:
            identifiers.append({
                'type': 'EMAIL',
                'value': hashlib.sha256(email.lower().strip().encode()).hexdigest(),
                'hashed': True,
            })
        if phone:
            identifiers.append({
                'type': 'PHONE_NUMBER',
                'value': hashlib.sha256(phone.strip().encode()).hexdigest(),
                'hashed': True,
            })
        # Use click_id as PARTNER_ID for deterministic matching
        if click_id:
            identifiers.append({
                'type': 'PARTNER_ID',
                'value': str(click_id),
                'hashed': False,
            })

        event = {
            'event_name':  event_name,
            'event_time':  event_time,
            'url':         url,
            'user_data': {
                'ip': ip,
                'user_agent': user_agent,
                'identifiers': identifiers,
            },
        }

        if value is not None:
            event['custom_data'] = {
                'value': str(value),
                'currency': currency,
            }
            if order_id:
                event['custom_data']['order_id'] = order_id

        payload = json.dumps({'conversions': [event]})
        url_str = TWITTER_CAPI_URL.format(pixel_id=pixel_id)

        try:
            req = urllib.request.Request(
                url_str,
                data=payload.encode(),
                headers={
                    'Content-Type':  'application/json',
                    'Authorization': f'OAuth {access_token}',
                    'User-Agent':    'SmartLink-TwitterCAPI/1.0',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                logger.info(
                    f"Twitter CAPI {event_name} → pixel={pixel_id} "
                    f"status={status_code}"
                )
        except Exception as e:
            logger.warning(
                f"Twitter CAPI failed: pixel={pixel_id} event={event_name} error={e}"
            )

    def send_via_smartlink_config(self, smartlink, event_name: str,
                                  context: dict, value: float = None,
                                  currency: str = 'USD'):
        """
        Convenience method: read config from SmartLink.integrations['twitter']
        and fire the event if the integration is active.
        """
        integrations = getattr(smartlink, 'integrations', {}) or {}
        config = integrations.get('twitter', {})
        if not config or not config.get('is_active', False):
            return

        event_to_flag = {
            'PageView': 'fire_page_view',
            'Lead':     'fire_lead',
            'Purchase': 'fire_purchase',
            'SignUp':   'fire_sign_up',
        }
        flag = event_to_flag.get(event_name)
        if flag and not config.get(flag, True):
            return  # Publisher disabled this specific event

        self.fire_event(
            pixel_id=config['pixel_id'],
            access_token=config['access_token'],
            event_name=event_name,
            context=context,
            value=value,
            currency=currency,
        )
