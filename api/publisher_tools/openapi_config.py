# publisher_tools/openapi_config.py
"""
OpenAPI / Swagger configuration via drf-spectacular।

Install:
    pip install drf-spectacular

earning_backend/settings.py-তে যোগ করো:
    INSTALLED_APPS = [
        ...
        'drf_spectacular',
        'drf_spectacular_sidecar',   # optional — self-hosted Swagger UI
    ]

    REST_FRAMEWORK = {
        ...
        'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    }

earning_backend/urls.py-তে যোগ করো:
    from publisher_tools.openapi_config import publisher_tools_schema_urls
    urlpatterns += publisher_tools_schema_urls

This file provides:
  1. SPECTACULAR_SETTINGS — schema metadata
  2. publisher_tools_schema_urls — Swagger UI + ReDoc + schema JSON/YAML
  3. PublisherToolsAutoSchema — custom schema class with common extensions
"""

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from django.urls import path


# ──────────────────────────────────────────────────────────────────────────────
# 1. SPECTACULAR SETTINGS  (paste into settings.py)
# ──────────────────────────────────────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    'TITLE':       'Earnify Publisher Tools API',
    'DESCRIPTION': '''
## Publisher Tools API

Earnify publisher monetization platform-এর REST API।

### Authentication
All endpoints require `Authorization: Token <your_token>` header.

### Rate Limits
| Endpoint Type   | Limit         |
|----------------|---------------|
| Standard        | 60 req/min    |
| Fraud checks    | 30 req/min    |
| Payout request  | 5 req/min     |
| KYC submit      | 3 req/min     |
| CSV export      | 10 req/hour   |

### Base URL
`/api/publisher-tools/`
    ''',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': True,
    'ENUM_GENERATE_CHOICE_DESCRIPTION': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking':                True,
        'persistAuthorization':       True,
        'displayOperationId':         False,
        'defaultModelsExpandDepth':   1,
        'defaultModelExpandDepth':    2,
        'docExpansion':               'list',
        'filter':                     True,
    },
    'TAGS': [
        {'name': 'Analytics',      'description': 'Analytics and reporting endpoints'},
        {'name': 'Payout',         'description': 'Payout requests and payment history'},
        {'name': 'Fraud',          'description': 'Fraud detection and reporting'},
        {'name': 'Realtime',       'description': 'Live stats and real-time dashboard'},
        {'name': 'Reporting',      'description': 'Monthly/forecast/eCPM reports'},
        {'name': 'Publisher',      'description': 'Publisher profile and KYC'},
        {'name': 'Webhooks',       'description': 'Webhook management and delivery'},
        {'name': 'Sites',          'description': 'Site management'},
        {'name': 'Apps',           'description': 'App management and SDK'},
        {'name': 'AdUnits',        'description': 'Ad unit management'},
        {'name': 'Mediation',      'description': 'Mediation and waterfall'},
        {'name': 'Optimization',   'description': 'Yield and placement optimization'},
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# 2. URL PATTERNS
# ──────────────────────────────────────────────────────────────────────────────

def get_publisher_tools_schema_urls():
    """
    Returns URL patterns for schema endpoints।
    Add to earning_backend/urls.py:
        from publisher_tools.openapi_config import get_publisher_tools_schema_urls
        urlpatterns += get_publisher_tools_schema_urls()
    """
    try:
        from drf_spectacular.views import (
            SpectacularAPIView,
            SpectacularSwaggerView,
            SpectacularRedocView,
        )
        return [
            path('api/schema/',        SpectacularAPIView.as_view(),     name='schema'),
            path('api/docs/swagger/',  SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
            path('api/docs/redoc/',    SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),
        ]
    except ImportError:
        import warnings
        warnings.warn('drf-spectacular not installed. Run: pip install drf-spectacular')
        return []


publisher_tools_schema_urls = get_publisher_tools_schema_urls()


# ──────────────────────────────────────────────────────────────────────────────
# 3. COMMON OPENAPI PARAMETER DEFINITIONS  (DRY — reuse in ViewSets)
# ──────────────────────────────────────────────────────────────────────────────

PARAM_DAYS = OpenApiParameter(
    name='days', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Number of days to look back (1–365, default 30)',
    required=False, default=30,
)

PARAM_LIMIT = OpenApiParameter(
    name='limit', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Maximum records to return (1–100, default 20)',
    required=False, default=20,
)

PARAM_PERIOD = OpenApiParameter(
    name='period', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description='Time period: today | yesterday | last_7_days | last_30_days | last_90_days | this_month | last_month | this_year',
    required=False, default='last_30_days',
    enum=['today', 'yesterday', 'last_7_days', 'last_30_days', 'last_90_days', 'this_month', 'last_month', 'this_year'],
)

PARAM_SITE_ID = OpenApiParameter(
    name='site_id', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Site primary key (required)',
    required=True,
)

PARAM_UNIT_ID = OpenApiParameter(
    name='unit_id', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description='Ad unit slug/unit_id (required)',
    required=True,
)

PARAM_COUNTRY = OpenApiParameter(
    name='country', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description='ISO 3166-1 alpha-2 country code (e.g. US, BD, DE)',
    required=True,
)

PARAM_YEAR = OpenApiParameter(
    name='year', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Calendar year (default: current year)',
    required=False,
)

PARAM_MONTH = OpenApiParameter(
    name='month', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Calendar month 1–12 (default: current month)',
    required=False,
)

PARAM_DIMENSION = OpenApiParameter(
    name='dimension', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description='Revenue grouping dimension',
    required=False, default='country',
    enum=['country', 'format', 'device', 'site', 'ad_unit'],
)

PARAM_BY = OpenApiParameter(
    name='by', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description="eCPM breakdown by 'country' or 'format'",
    required=False, default='country',
    enum=['country', 'format'],
)


# ──────────────────────────────────────────────────────────────────────────────
# 4. SCHEMA DECORATORS FOR VIEWSETS  (usage examples)
# ──────────────────────────────────────────────────────────────────────────────

# Usage in views_reporting.py:
#   from .openapi_config import PARAM_DAYS, PARAM_YEAR, PARAM_MONTH
#   from drf_spectacular.utils import extend_schema
#
#   @extend_schema(
#       tags=['Reporting'],
#       parameters=[PARAM_YEAR, PARAM_MONTH],
#       summary='Monthly earnings report',
#   )
#   @action(detail=False, methods=['get'], url_path='monthly')
#   def monthly_report(self, request): ...


REPORTING_SCHEMA = {
    'monthly_report': dict(
        tags=['Reporting'],
        parameters=[PARAM_YEAR, PARAM_MONTH],
        summary='Monthly earnings report',
        description='Publisher-এর নির্দিষ্ট মাসের earnings summary।',
    ),
    'revenue_forecast': dict(
        tags=['Reporting'],
        parameters=[PARAM_DAYS],
        summary='ML-based revenue forecast',
        description='Historical data-এর উপর ভিত্তি করে ভবিষ্যতের revenue forecast।',
    ),
    'ecpm_breakdown': dict(
        tags=['Analytics'],
        parameters=[PARAM_BY, PARAM_DAYS],
        summary='eCPM breakdown by country or format',
    ),
    'top_units': dict(
        tags=['Analytics'],
        parameters=[PARAM_DAYS, PARAM_LIMIT],
        summary='Top performing ad units',
    ),
    'export_report': dict(
        tags=['Reporting'],
        summary='Export custom report (CSV or JSON)',
        description='Metric + dimension combination দিয়ে custom report export করো।',
    ),
}

PAYOUT_SCHEMA = {
    'eligibility': dict(
        tags=['Payout'],
        summary='Check payout eligibility',
    ),
    'request_payout': dict(
        tags=['Payout'],
        summary='Submit payout request',
    ),
    'withholding_tax': dict(
        tags=['Payout'],
        parameters=[],
        summary='Calculate withholding tax',
        description='Country + amount দিয়ে withholding tax calculate করো।',
    ),
    'tax_rate': dict(
        tags=['Payout'],
        parameters=[PARAM_COUNTRY],
        summary='Get tax rate for a country',
    ),
}

FRAUD_SCHEMA = {
    'fraud_report': dict(
        tags=['Fraud'],
        parameters=[PARAM_DAYS],
        summary='Publisher fraud report',
    ),
    'geo_validate': dict(
        tags=['Fraud'],
        summary='Validate IP geo vs claimed geo',
    ),
    'velocity_check': dict(
        tags=['Fraud'],
        summary='Multi-window velocity check',
    ),
    'country_risk': dict(
        tags=['Fraud'],
        parameters=[PARAM_COUNTRY],
        summary='Country fraud risk score',
    ),
}

REALTIME_SCHEMA = {
    'live_stats': dict(
        tags=['Realtime'],
        summary='Current-hour live stats (cached 60s)',
    ),
    'dashboard_summary': dict(
        tags=['Realtime'],
        parameters=[PARAM_PERIOD],
        summary='Dashboard key metrics summary',
    ),
    'realtime_fill_rate': dict(
        tags=['Realtime'],
        parameters=[PARAM_UNIT_ID],
        summary='Real-time fill rate for an ad unit',
    ),
}
