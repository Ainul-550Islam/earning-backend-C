"""
SmartLink — Google Analytics 4 (GA4) Server-Side Integration
Fires events via GA4 Measurement Protocol API (server-side, no JS required).
Enables accurate tracking without cookie consent or ad-blocker interference.

GA4 Measurement Protocol docs:
https://developers.google.com/analytics/devguides/collection/protocol/ga4

Configuration (per SmartLink, stored in integrations JSON field):
    {
        "ga4": {
            "measurement_id": "G-XXXXXXXXXX",
            "api_secret": "...",
            "fire_page_view": true,
            "fire_generate_lead": true,
            "fire_purchase": true,
            "is_active": true
        }
    }
"""
import json
from api.smartlink.integrations.base import IntegrationBase
import logging
import threading
import time
import urllib.request
import hashlib
import uuid

logger = logging.getLogger('smartlink.integrations.ga4')

GA4_MEASUREMENT_URL = (
    'https://www.google-analytics.com/mp/collect'
    '?measurement_id={measurement_id}&api_secret={api_secret}'
)
GA4_DEBUG_URL = (
    'https://www.google-analytics.com/debug/mp/collect'
    '?measurement_id={measurement_id}&api_secret={api_secret}'
)


class GA4MeasurementProtocol(IntegrationBase):
    integration_name = "GA4"
    default_timeout  = 10

    """
    Fire server-side events to GA4 via Measurement Protocol.

    Supported events (GA4 recommended events):
        page_view         → on SmartLink redirect click
        generate_lead     → on CPA lead conversion
        purchase          → on sale conversion
        sign_up           → on registration conversion
        click             → general click event

    Methods:
        fire_page_view(measurement_id, api_secret, context)
        fire_generate_lead(measurement_id, api_secret, context, value)
        fire_purchase(measurement_id, api_secret, context, value, currency, transaction_id)
        fire_event(measurement_id, api_secret, event_name, context, params)
        validate_event(measurement_id, api_secret, event_name, context, params)  → debug mode
    """

    def fire_page_view(self, measurement_id: str, api_secret: str, context: dict):
        """Fire page_view event on SmartLink redirect."""
        self._fire_async(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name='page_view',
            context=context,
            params={
                'page_location': context.get('url', ''),
                'page_referrer': context.get('referrer', ''),
            },
        )

    def fire_generate_lead(self, measurement_id: str, api_secret: str,
                           context: dict, value: float = 0.0, currency: str = 'USD'):
        """Fire generate_lead event on CPA conversion."""
        self._fire_async(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name='generate_lead',
            context=context,
            params={
                'value': value,
                'currency': currency,
            },
        )

    def fire_purchase(self, measurement_id: str, api_secret: str,
                      context: dict, value: float = 0.0, currency: str = 'USD',
                      transaction_id: str = '', items: list = None):
        """Fire purchase event on sale conversion."""
        params = {
            'transaction_id': transaction_id or str(uuid.uuid4()),
            'value':          value,
            'currency':       currency,
        }
        if items:
            params['items'] = items
        self._fire_async(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name='purchase',
            context=context,
            params=params,
        )

    def fire_sign_up(self, measurement_id: str, api_secret: str,
                     context: dict, method: str = 'SmartLink'):
        """Fire sign_up event on registration conversion."""
        self._fire_async(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name='sign_up',
            context=context,
            params={'method': method},
        )

    def fire_event(self, measurement_id: str, api_secret: str,
                   event_name: str, context: dict, params: dict = None):
        """Fire any GA4 event with custom parameters."""
        self._fire_async(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name=event_name,
            context=context,
            params=params or {},
        )

    def validate_event(self, measurement_id: str, api_secret: str,
                       event_name: str, context: dict, params: dict = None) -> dict:
        """
        Send event to GA4 debug endpoint and return validation result.
        Use during development to check event payload before going live.
        Returns the GA4 debug response as a dict.
        """
        return self._send(
            measurement_id=measurement_id,
            api_secret=api_secret,
            event_name=event_name,
            context=context,
            params=params or {},
            debug=True,
        )

    def send_via_smartlink_config(self, smartlink, event_name: str,
                                  context: dict, value: float = None,
                                  currency: str = 'USD',
                                  transaction_id: str = ''):
        """
        Convenience method: read config from SmartLink.integrations['ga4']
        and fire the event if the integration is active.
        """
        integrations = getattr(smartlink, 'integrations', {}) or {}
        config = integrations.get('ga4', {})
        if not config or not config.get('is_active', False):
            return

        event_flag_map = {
            'page_view':     'fire_page_view',
            'generate_lead': 'fire_generate_lead',
            'purchase':      'fire_purchase',
            'sign_up':       'fire_sign_up',
        }
        flag = event_flag_map.get(event_name)
        if flag and not config.get(flag, True):
            return  # Publisher disabled this event type

        self.fire_event(
            measurement_id=config['measurement_id'],
            api_secret=config['api_secret'],
            event_name=event_name,
            context={
                **context,
                'url': smartlink.full_url,
            },
            params={
                'value':          value,
                'currency':       currency,
                'transaction_id': transaction_id,
                'sl_slug':        smartlink.slug,
            } if value is not None else {'sl_slug': smartlink.slug},
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fire_async(self, **kwargs):
        """Fire API call in a daemon thread (non-blocking)."""
        thread = threading.Thread(target=self._send, kwargs=kwargs, daemon=True)
        thread.start()

    def _send(self, measurement_id: str, api_secret: str, event_name: str,
              context: dict, params: dict, debug: bool = False) -> dict:
        """
        Build and POST the GA4 Measurement Protocol payload.
        GA4 requires: client_id (pseudo-anonymous), timestamp_micros, events list.
        """
        ip          = context.get('ip', '')
        user_agent  = context.get('user_agent', '')
        click_id    = context.get('click_id', '')

        # Derive a stable client_id from IP+UA (GDPR-safe: no raw IP sent)
        raw = f"{ip}:{user_agent}"
        client_id = str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))

        # Strip None values from params
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        # Add standard SmartLink params
        if click_id:
            clean_params['sl_click_id'] = str(click_id)
        if context.get('country'):
            clean_params['sl_country'] = context['country']
        if context.get('device_type'):
            clean_params['sl_device']  = context['device_type']

        payload = {
            'client_id':        client_id,
            'timestamp_micros': int(time.time() * 1_000_000),
            'non_personalized_ads': True,
            'events': [{
                'name':   event_name,
                'params': clean_params,
            }],
        }

        url_template = GA4_DEBUG_URL if debug else GA4_MEASUREMENT_URL
        url_str = url_template.format(
            measurement_id=measurement_id,
            api_secret=api_secret,
        )

        try:
            req = urllib.request.Request(
                url_str,
                data=json.dumps(payload).encode(),
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent':   'SmartLink-GA4/1.0',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                body = resp.read().decode()
                if debug:
                    logger.info(f"GA4 debug [{event_name}]: {body}")
                    try:
                        return json.loads(body)
                    except Exception:
                        return {'raw': body}
                else:
                    logger.info(
                        f"GA4 [{event_name}] → {measurement_id} status={status_code}"
                    )
                    return {'status': status_code}
        except Exception as e:
            logger.warning(
                f"GA4 Measurement Protocol failed: "
                f"measurement_id={measurement_id} event={event_name} error={e}"
            )
            return {'error': str(e)}
