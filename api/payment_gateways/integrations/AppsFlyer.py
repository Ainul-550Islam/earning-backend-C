# api/payment_gateways/integrations/AppsFlyer.py
# AppsFlyer CPI campaign integration for CPI offer tracking

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class AppsFlyerIntegration:
    """
    Integrate with AppsFlyer for CPI (app install) tracking.
    Allows CPI advertisers to use AppsFlyer as their attribution platform.

    Flow:
        1. Advertiser creates AppsFlyer campaign
        2. Links it to our offer via app_id + appsflyer_dev_key
        3. AppsFlyer fires our postback URL on each install
        4. We verify and credit publisher

    Docs: https://support.appsflyer.com/hc/en-us/articles/207034486
    """

    POSTBACK_MACRO = (
        'https://yourdomain.com/api/payment/tracking/postback/'
        '?click_id={clickid}'
        '&payout={payout}'
        '&status=approved'
        '&sub1={sub1}'
        '&country={country_code}'
        '&device={device_model}'
    )

    def get_postback_url(self, offer_id: int) -> str:
        """
        Return the AppsFlyer postback URL for an offer.
        Advertiser enters this in their AppsFlyer dashboard.
        """
        return (
            f'https://yourdomain.com/api/payment/tracking/postback/'
            f'?click_id={{clickid}}'
            f'&payout={{payout}}'
            f'&status=approved'
            f'&offer_id={offer_id}'
            f'&sub1={{sub1}}'
            f'&country={{country_code}}'
        )

    def get_click_url(self, offer_id: int, af_app_id: str,
                      publisher_id: int, click_id: str) -> str:
        """
        Generate AppsFlyer tracking click URL.
        Publisher sends users to this URL — AppsFlyer tracks installs.

        Format:
        https://app.appsflyer.com/{app_id}?pid={media_source}&af_siteid={publisher_id}&clickid={click_id}
        """
        return (
            f'https://app.appsflyer.com/{af_app_id}'
            f'?pid=yourdomain_int'
            f'&af_siteid={publisher_id}'
            f'&clickid={click_id}'
            f'&af_prt=yourdomain'
        )

    def validate_install_event(self, payload: dict) -> dict:
        """
        Validate an install event received from AppsFlyer postback.
        Returns standardized conversion data.
        """
        # AppsFlyer sends: clickid, payout, country_code, device_model, etc.
        click_id = payload.get('clickid') or payload.get('af_sub1') or ''
        payout   = float(payload.get('payout', 0))
        country  = payload.get('country_code', '')
        status   = payload.get('status', 'approved')

        # AppsFlyer uses 'Organic' for unattributed — block these
        media_source = payload.get('media_source', '')
        if media_source == 'Organic':
            return {'valid': False, 'reason': 'Organic install — not attributed to publisher'}

        if not click_id:
            return {'valid': False, 'reason': 'Missing click_id (clickid parameter)'}

        return {
            'valid':    True,
            'click_id': click_id,
            'payout':   payout,
            'country':  country,
            'status':   status,
            'platform': payload.get('platform', ''),
            'app_id':   payload.get('app_id', ''),
        }

    def get_campaign_stats(self, af_dev_key: str, app_id: str,
                            date_from: str, date_to: str) -> list:
        """
        Pull campaign performance data from AppsFlyer Pull API.
        Used for reconciliation.
        """
        try:
            url = (
                f'https://hq.appsflyer.com/export/{app_id}/partners_report/v5'
                f'?api_token={af_dev_key}'
                f'&from={date_from}&to={date_to}'
            )
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            # Parse CSV response
            lines = resp.text.strip().split('\n')
            headers = lines[0].split(',') if lines else []
            return [dict(zip(headers, l.split(','))) for l in lines[1:] if l]
        except Exception as e:
            logger.error(f'AppsFlyer stats fetch failed: {e}')
            return []


class ThirdPartyTrackerService:
    """
    Universal 3rd party tracker integration.
    Supports: AppsFlyer, Adjust, Kochava, Singular, Branch

    Normalizes incoming postback formats to our standard format.
    """

    TRACKER_CONFIGS = {
        'appsflyer': {
            'click_id_param': 'clickid',
            'payout_param':   'payout',
            'status_param':   'status',
            'country_param':  'country_code',
            'device_param':   'device_model',
        },
        'adjust': {
            'click_id_param': 's2s_click_id',
            'payout_param':   'payout',
            'status_param':   'status',
            'country_param':  'country',
        },
        'kochava': {
            'click_id_param': 'kcid',
            'payout_param':   'usd_revenue',
            'status_param':   'type',
            'country_param':  'geo_cn',
        },
        'singular': {
            'click_id_param': 'singular_click_id',
            'payout_param':   'revenue',
            'status_param':   'status',
            'country_param':  'country_code',
        },
    }

    def normalize_postback(self, tracker: str, raw_params: dict) -> dict:
        """
        Normalize tracker-specific postback params to our standard format.
        """
        config   = self.TRACKER_CONFIGS.get(tracker.lower(), {})
        click_id = raw_params.get(config.get('click_id_param', 'click_id'), '')
        payout   = float(raw_params.get(config.get('payout_param', 'payout'), 0) or 0)
        country  = raw_params.get(config.get('country_param', 'country'), '')
        status   = raw_params.get(config.get('status_param', 'status'), 'approved')

        # Normalize status
        status_map = {
            'install':  'approved',
            'event':    'approved',
            'approved': 'approved',
            'rejected': 'rejected',
            'fraud':    'rejected',
        }
        status = status_map.get(status.lower(), 'approved')

        return {
            'click_id':   click_id,
            'payout':     payout,
            'country':    country,
            'status':     status,
            'tracker':    tracker,
            'raw':        raw_params,
        }

    def get_postback_template(self, tracker: str, offer_id: int) -> str:
        """Get the postback URL template for a specific tracker."""
        config    = self.TRACKER_CONFIGS.get(tracker.lower(), {})
        click_param = config.get('click_id_param', 'click_id')
        payout_param= config.get('payout_param', 'payout')

        return (
            f'https://yourdomain.com/api/payment/tracking/postback/'
            f'?click_id={{{click_param}}}'
            f'&payout={{{payout_param}}}'
            f'&status=approved'
            f'&offer_id={offer_id}'
            f'&tracker={tracker}'
        )
