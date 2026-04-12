# api/offer_inventory/misc_features/legacy_support.py
"""
Legacy Support — Backward compatibility for older API clients.
Maps v1 API calls to v2 equivalents, transforms old data formats.
"""
import logging

logger = logging.getLogger(__name__)

V1_TO_V2_URL_MAP = {
    '/api/offers/'        : '/api/offer-inventory/offers/',
    '/api/conversions/'   : '/api/offer-inventory/conversions/',
    '/api/withdrawals/'   : '/api/offer-inventory/withdrawals/',
    '/api/postback/'      : '/api/offer-inventory/postback/',
    '/api/wallet/'        : '/api/offer-inventory/me/wallet/',
    '/api/profile/'       : '/api/offer-inventory/me/profile/',
    '/api/referrals/'     : '/api/offer-inventory/me/referrals/',
}

DEPRECATED_PARAMS = {
    'snuid'     : 'click_id',
    'verifier'  : 'transaction_id',
    'currency'  : 'payout',
    'pub0'      : 's1',
    'pub1'      : 's2',
    'offer_name': 'title',
    'offer_id'  : 'id',
}


class LegacySupport:
    """Backward compatibility helpers for older API integrations."""

    @classmethod
    def get_v2_url(cls, v1_url: str) -> str:
        """Map a v1 URL path to v2 equivalent."""
        for v1, v2 in V1_TO_V2_URL_MAP.items():
            if v1_url.startswith(v1):
                new_url = v1_url.replace(v1, v2, 1)
                logger.info(f'Legacy redirect: {v1_url} → {new_url}')
                return new_url
        return v1_url

    @classmethod
    def normalize_postback_params(cls, params: dict) -> dict:
        """Normalize legacy postback parameter names to v2 standard."""
        normalized = {}
        for key, value in params.items():
            mapped = DEPRECATED_PARAMS.get(key, key)
            normalized[mapped] = value
        return normalized

    @classmethod
    def transform_v1_offer(cls, v1_offer: dict) -> dict:
        """Transform v1 offer dict to v2 schema."""
        return {
            'id'           : v1_offer.get('offer_id') or v1_offer.get('id', ''),
            'title'        : v1_offer.get('offer_name') or v1_offer.get('name') or v1_offer.get('title', ''),
            'description'  : v1_offer.get('description', ''),
            'offer_url'    : v1_offer.get('offer_url') or v1_offer.get('url', ''),
            'payout_amount': v1_offer.get('payout') or v1_offer.get('amount', 0),
            'reward_amount': v1_offer.get('coins') or v1_offer.get('reward', 0),
            'status'       : 'active',
        }

    @classmethod
    def transform_v1_conversion(cls, v1_conv: dict) -> dict:
        """Transform v1 conversion dict to v2."""
        return {
            'click_id'      : v1_conv.get('snuid') or v1_conv.get('click_id', ''),
            'transaction_id': v1_conv.get('verifier') or v1_conv.get('transaction_id', ''),
            'payout'        : v1_conv.get('currency') or v1_conv.get('payout', 0),
            'status'        : v1_conv.get('status', 'approved'),
        }

    @staticmethod
    def get_deprecated_endpoints() -> list:
        """List all deprecated endpoints with migration guidance."""
        return [
            {
                'deprecated'  : path,
                'use_instead' : replacement,
                'removed_in'  : 'v3.0',
                'migration'   : f'Replace {path} with {replacement} in your integration.',
            }
            for path, replacement in V1_TO_V2_URL_MAP.items()
        ]

    @staticmethod
    def is_v1_client(request) -> bool:
        """Detect if request is from a legacy v1 client."""
        accept    = request.META.get('HTTP_ACCEPT', '')
        api_ver   = request.META.get('HTTP_X_API_VERSION', '')
        path      = request.path
        return (
            'version=1' in accept or
            api_ver == 'v1' or
            any(path.startswith(v1) for v1 in V1_TO_V2_URL_MAP)
        )

    @staticmethod
    def deprecation_warning_header(response):
        """Add deprecation headers to response."""
        response['Deprecation']    = 'true'
        response['Sunset']         = 'Sat, 31 Dec 2025 23:59:59 GMT'
        response['Link']           = '</api/offer-inventory/>; rel="successor-version"'
        response['X-API-Version']  = 'v1 (deprecated)'
        return response
