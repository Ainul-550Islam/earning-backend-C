# api/djoyalty/openapi.py
"""
OpenAPI schema customization for Djoyalty।
drf-spectacular ব্যবহার করে।
pip install drf-spectacular

settings.py এ যোগ করুন:
INSTALLED_APPS += ['drf_spectacular']
REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'
"""
import logging

logger = logging.getLogger('djoyalty.openapi')

try:
    from drf_spectacular.utils import (
        extend_schema, extend_schema_view, OpenApiParameter,
        OpenApiExample, OpenApiResponse,
    )
    from drf_spectacular.types import OpenApiTypes
    SPECTACULAR_AVAILABLE = True
except ImportError:
    SPECTACULAR_AVAILABLE = False
    logger.debug('drf-spectacular not installed. Install: pip install drf-spectacular')

    # Fallback no-op decorators
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def extend_schema_view(*args, **kwargs):
        def decorator(cls):
            return cls
        return decorator

    class OpenApiParameter:
        def __init__(self, *args, **kwargs):
            pass

    class OpenApiTypes:
        STR = str
        INT = int
        DECIMAL = float
        BOOL = bool


# ==================== COMMON PARAMETERS ====================

CUSTOMER_ID_PARAM = OpenApiParameter(
    name='customer_id',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY if SPECTACULAR_AVAILABLE else 'query',
    description='Customer ID to filter by',
    required=False,
)

TENANT_HEADER = OpenApiParameter(
    name='X-Tenant-ID',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.HEADER if SPECTACULAR_AVAILABLE else 'header',
    description='Tenant ID for multi-tenant isolation',
    required=False,
)

API_KEY_HEADER = OpenApiParameter(
    name='X-Loyalty-API-Key',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER if SPECTACULAR_AVAILABLE else 'header',
    description='Partner merchant API key (for public endpoints)',
    required=False,
)


# ==================== SCHEMA TAGS ====================

DJOYALTY_TAGS = {
    'customers': ['👥 Customers'],
    'transactions': ['💳 Transactions'],
    'events': ['📅 Events'],
    'points': ['⭐ Points'],
    'ledger': ['📒 Points Ledger'],
    'transfers': ['🔄 Points Transfers'],
    'tiers': ['🏆 Tiers'],
    'earn_rules': ['💰 Earn Rules'],
    'redemptions': ['🎁 Redemptions'],
    'vouchers': ['🎫 Vouchers'],
    'gift_cards': ['🎁 Gift Cards'],
    'streaks': ['🔥 Streaks'],
    'badges': ['🏅 Badges'],
    'challenges': ['⚡ Challenges'],
    'leaderboard': ['🏆 Leaderboard'],
    'campaigns': ['📣 Campaigns'],
    'insights': ['📊 Insights'],
    'admin_loyalty': ['🔐 Admin'],
    'public': ['🌐 Public API'],
    'health': ['❤️ Health'],
}


# ==================== SCHEMA DECORATORS ====================

def djoyalty_schema(summary: str, description: str = '', tags: list = None, **kwargs):
    """Shortcut for @extend_schema with Djoyalty defaults।"""
    return extend_schema(
        summary=summary,
        description=description or summary,
        tags=tags or ['Djoyalty'],
        **kwargs,
    )


# ==================== SPECTACULAR HOOKS ====================

def djoyalty_postprocessing_hook(result, generator, request, public):
    """
    Post-processing hook for OpenAPI schema।
    Add global security schemes, tags, etc.
    settings.py:
    SPECTACULAR_SETTINGS = {
        'POSTPROCESSING_HOOKS': ['api.djoyalty.openapi.djoyalty_postprocessing_hook'],
    }
    """
    result['info']['title'] = 'Djoyalty API'
    result['info']['version'] = '1.0.0'
    result['info']['description'] = (
        '**Djoyalty** — World-class Django Loyalty System API\n\n'
        '## Authentication\n'
        'Bearer token required for most endpoints.\n'
        'Partner endpoints require `X-Loyalty-API-Key` header.\n\n'
        '## Multi-tenancy\n'
        'Include `X-Tenant-ID` header for tenant isolation.\n\n'
        '## Rate Limits\n'
        '- Authenticated: 1000/hour\n'
        '- Anonymous: 100/hour\n'
        '- Points earn: 200/hour\n'
        '- Redemption: 20/hour\n'
    )

    # Add security schemes
    result.setdefault('components', {}).setdefault('securitySchemes', {})
    result['components']['securitySchemes']['BearerAuth'] = {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'JWT',
    }
    result['components']['securitySchemes']['ApiKeyAuth'] = {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-Loyalty-API-Key',
    }

    return result


# ==================== SPECTACULAR SETTINGS ====================

SPECTACULAR_SETTINGS = {
    'TITLE': 'Djoyalty API',
    'DESCRIPTION': 'World-class Django Loyalty System',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'api.djoyalty.openapi.djoyalty_postprocessing_hook',
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'TAGS': [
        {'name': tag[0], 'description': f'Endpoints for {name}'}
        for name, tag in DJOYALTY_TAGS.items()
    ],
}
