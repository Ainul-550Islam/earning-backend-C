# api/offer_inventory/routes.py
"""
Route Helpers — Centralized URL building and API versioning.
Provides URL name → full path mappings for internal use.
"""
from django.urls import reverse


# ── API Version Prefixes ───────────────────────────────────────────
API_V1_PREFIX = '/api/'
API_V2_PREFIX = '/api/offer-inventory/'

# ── Named Route Registry ───────────────────────────────────────────
ROUTE_MAP = {
    # Offers
    'offer_list'         : f'{API_V2_PREFIX}offers/',
    'offer_detail'       : f'{API_V2_PREFIX}offers/{{id}}/',
    'offer_click'        : f'{API_V2_PREFIX}offers/{{id}}/click/',
    'offer_featured'     : f'{API_V2_PREFIX}offers/featured/',
    # Postback & Pixel
    'postback'           : f'{API_V2_PREFIX}postback/',
    'postback_network'   : f'{API_V2_PREFIX}postback/{{network_slug}}/',
    'pixel_impression'   : f'{API_V2_PREFIX}pixel/impression/{{offer_id}}/',
    'pixel_conversion'   : f'{API_V2_PREFIX}pixel/conversion/{{token}}/',
    'smartlink_redirect' : f'{API_V2_PREFIX}go/{{slug}}/',
    # User
    'my_profile'         : f'{API_V2_PREFIX}me/profile/',
    'my_kyc'             : f'{API_V2_PREFIX}me/kyc/',
    'my_conversions'     : f'{API_V2_PREFIX}me/conversions/',
    'my_transactions'    : f'{API_V2_PREFIX}me/transactions/',
    'my_wallet'          : f'{API_V2_PREFIX}me/wallet/',
    'my_referrals'       : f'{API_V2_PREFIX}me/referrals/',
    'my_achievements'    : f'{API_V2_PREFIX}me/achievements/',
    # Wallet
    'withdrawals'        : f'{API_V2_PREFIX}withdrawals/',
    'payment_methods'    : f'{API_V2_PREFIX}payment-methods/',
    # Marketing
    'marketing_campaign' : f'{API_V2_PREFIX}marketing/campaign/',
    'promo_redeem'       : f'{API_V2_PREFIX}marketing/promo/redeem/',
    'push_subscribe'     : f'{API_V2_PREFIX}marketing/push/subscribe/',
    'push_unsubscribe'   : f'{API_V2_PREFIX}marketing/push/unsubscribe/',
    'leaderboard'        : f'{API_V2_PREFIX}marketing/leaderboard/',
    # Analytics
    'dashboard'          : f'{API_V2_PREFIX}analytics/dashboard/',
    'kpis'               : f'{API_V2_PREFIX}analytics/kpis/',
    'revenue_forecast'   : f'{API_V2_PREFIX}analytics/revenue-forecast/',
    'cohorts'            : f'{API_V2_PREFIX}analytics/cohorts/',
    'network_roi'        : f'{API_V2_PREFIX}analytics/network-roi/',
    # Reports
    'report_revenue'     : f'{API_V2_PREFIX}reports/revenue/',
    'report_conversions' : f'{API_V2_PREFIX}reports/conversions/',
    'report_withdrawals' : f'{API_V2_PREFIX}reports/withdrawals/',
    'report_fraud'       : f'{API_V2_PREFIX}reports/fraud/',
    'report_networks'    : f'{API_V2_PREFIX}reports/networks/',
    # Business
    'executive_summary'  : f'{API_V2_PREFIX}business/executive-summary/',
    'advertiser'         : f'{API_V2_PREFIX}business/advertiser/',
    'billing'            : f'{API_V2_PREFIX}business/billing/',
    'gdpr'               : f'{API_V2_PREFIX}business/compliance/gdpr/',
    # System
    'health'             : f'{API_V2_PREFIX}health/',
    'circuits'           : f'{API_V2_PREFIX}circuits/',
}


def get_url(route_name: str, **kwargs) -> str:
    """Get URL for a named route with optional path params."""
    url = ROUTE_MAP.get(route_name, '')
    for key, value in kwargs.items():
        url = url.replace(f'{{{key}}}', str(value))
    return url


def build_offer_url(offer_id: str) -> str:
    return get_url('offer_detail', id=offer_id)


def build_click_url(offer_id: str) -> str:
    return get_url('offer_click', id=offer_id)


def build_postback_url(base_url: str, network_slug: str = None) -> str:
    """Build full postback URL for network configuration."""
    route = 'postback_network' if network_slug else 'postback'
    path  = get_url(route, network_slug=network_slug or '')
    return f'{base_url.rstrip("/")}{path}'


def build_pixel_url(offer_id: str, base_url: str = '') -> str:
    """Build pixel impression URL for embedding."""
    path = get_url('pixel_impression', offer_id=offer_id)
    return f'{base_url.rstrip("/")}{path}'


def build_smartlink_url(slug: str, base_url: str = '') -> str:
    """Build SmartLink redirect URL."""
    path = get_url('smartlink_redirect', slug=slug)
    return f'{base_url.rstrip("/")}{path}'


class APIVersionRouter:
    """
    API versioning helper.
    Routes requests to appropriate handler based on version header.
    """

    SUPPORTED_VERSIONS = ['v1', 'v2']
    DEFAULT_VERSION    = 'v2'

    @staticmethod
    def get_version(request) -> str:
        """Extract API version from request."""
        # Check Accept header: application/json; version=2
        accept = request.META.get('HTTP_ACCEPT', '')
        if 'version=1' in accept:
            return 'v1'
        if 'version=2' in accept:
            return 'v2'
        # Check custom header
        version = request.META.get('HTTP_X_API_VERSION', '')
        if version in APIVersionRouter.SUPPORTED_VERSIONS:
            return version
        return APIVersionRouter.DEFAULT_VERSION

    @staticmethod
    def is_deprecated(version: str) -> bool:
        return version == 'v1'

    @staticmethod
    def get_deprecation_header() -> dict:
        return {
            'Deprecation'  : 'true',
            'Sunset'       : 'Sat, 31 Dec 2025 23:59:59 GMT',
            'Link'         : '</api/offer-inventory/>; rel="successor-version"',
        }
