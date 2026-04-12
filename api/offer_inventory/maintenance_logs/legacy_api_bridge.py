# api/offer_inventory/maintenance_logs/legacy_api_bridge.py
"""Legacy API Bridge — Backward compatibility for v1 clients."""
import logging
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

V1_TO_V2 = {
    '/api/offers/'      : '/api/offer-inventory/offers/',
    '/api/conversions/' : '/api/offer-inventory/conversions/',
    '/api/withdrawals/' : '/api/offer-inventory/withdrawals/',
    '/api/postback/'    : '/api/offer-inventory/postback/',
    '/api/wallet/'      : '/api/offer-inventory/me/wallet/',
    '/api/profile/'     : '/api/offer-inventory/me/profile/',
    '/api/stats/'       : '/api/offer-inventory/analytics/dashboard/',
}

V1_PARAM_MAP = {
    'snuid'     : 'click_id',
    'verifier'  : 'transaction_id',
    'currency'  : 'payout',
    'pub0'      : 's1',
    'pub1'      : 's2',
    'offer_id'  : 'id',
    'offer_name': 'title',
}


class LegacyAPIBridge:
    """Bridge v1 API requests to v2 equivalents."""

    @classmethod
    def get_v2_url(cls, v1_path: str) -> str:
        """Map v1 URL path to v2 equivalent."""
        for v1, v2 in V1_TO_V2.items():
            if v1_path.startswith(v1):
                return v1_path.replace(v1, v2, 1)
        return v1_path

    @classmethod
    def normalize_params(cls, params: dict) -> dict:
        """Rename legacy parameter names to v2 standard."""
        return {V1_PARAM_MAP.get(k, k): v for k, v in params.items()}

    @classmethod
    def transform_v1_offer(cls, v1: dict) -> dict:
        """Convert v1 offer format to v2."""
        return {
            'id'           : v1.get('offer_id') or v1.get('id', ''),
            'title'        : v1.get('offer_name') or v1.get('title', ''),
            'description'  : v1.get('description', ''),
            'offer_url'    : v1.get('offer_url') or v1.get('url', ''),
            'payout_amount': v1.get('payout') or v1.get('amount', 0),
            'reward_amount': v1.get('coins') or v1.get('reward', 0),
            'status'       : 'active',
        }

    @classmethod
    def transform_v1_postback(cls, params: dict) -> dict:
        """Transform v1 postback params to v2 format."""
        return {
            'click_id'      : params.get('snuid') or params.get('click_id', ''),
            'transaction_id': params.get('verifier') or params.get('transaction_id', ''),
            'payout'        : params.get('currency') or params.get('payout', 0),
            'status'        : params.get('status', 'approved'),
        }

    @staticmethod
    def redirect_response(v1_path: str) -> JsonResponse:
        """Return a deprecation redirect response."""
        v2_path = LegacyAPIBridge.get_v2_url(v1_path)
        return JsonResponse({
            'deprecated' : True,
            'message'    : f'This endpoint is deprecated. Use {v2_path} instead.',
            'redirect_to': v2_path,
            'sunset'     : 'December 31, 2025',
        }, status=301)

    @staticmethod
    def add_deprecation_headers(response):
        """Add deprecation headers to any response."""
        response['Deprecation']   = 'true'
        response['Sunset']        = 'Sat, 31 Dec 2025 23:59:59 GMT'
        response['Link']          = '</api/offer-inventory/>; rel="successor-version"'
        return response

    @staticmethod
    def get_migration_guide() -> dict:
        """Return v1→v2 migration guide."""
        return {
            'version'  : '2.0',
            'endpoints': [
                {'v1': k, 'v2': v, 'sunset': 'December 31, 2025'}
                for k, v in V1_TO_V2.items()
            ],
            'params'   : [
                {'v1': k, 'v2': v}
                for k, v in V1_PARAM_MAP.items()
            ],
        }
