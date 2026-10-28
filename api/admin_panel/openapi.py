# api/admin_panel/openapi.py
"""
OpenAPI / Swagger configuration for admin_panel.
Generates full API docs at /api/admin-panel/docs/
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter,
    OpenApiResponse, OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.urls import path


# ==================== SPECTACULAR SETTINGS ====================
ADMIN_PANEL_SPECTACULAR_SETTINGS = {
    'TITLE': 'Admin Panel API',
    'DESCRIPTION': (
        'World-class earning platform admin API. '
        'Controls all 50 apps: users, wallet, fraud, promotions, smartlink, RTB, KYC, AI engine.\n\n'
        '**Authentication:** Bearer JWT token\n\n'
        '**Base URL:** `/api/admin-panel/`\n\n'
        '**WebSocket:** `ws://domain/ws/admin/dashboard/`'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Real-time Dashboard', 'description': 'Live KPIs, activity feed, system health'},
        {'name': 'User Management',     'description': 'Ban, verify, search, bulk actions'},
        {'name': 'Wallet Admin',        'description': 'Balance adjust, freeze, top earners'},
        {'name': 'Payout Admin',        'description': 'Withdrawal approval, batch processing'},
        {'name': 'Fraud Control',       'description': 'Rules, IP blocking, risk scoring'},
        {'name': 'Promotions Admin',    'description': 'Offers, conversions, traffic caps'},
        {'name': 'Smartlink Admin',     'description': 'Routing, GEO stats, offer pool'},
        {'name': 'RTB Admin',           'description': 'Bid floors, demand partners, auction'},
        {'name': 'Content Locker',      'description': 'CPAlead content/file/link lockers'},
        {'name': 'Offerwall Admin',     'description': 'Offer providers, categories, sync'},
        {'name': 'KYC Admin',           'description': 'Identity verification, AML monitoring'},
        {'name': 'Loyalty Admin',       'description': 'Points, tiers, badges, leaderboard'},
        {'name': 'Advertiser Admin',    'description': 'Advertiser approval, campaigns, billing'},
        {'name': 'Publisher Admin',     'description': 'Site/app approval, earnings, traffic quality'},
        {'name': 'AI Engine Admin',     'description': 'ML models, training, predictions'},
        {'name': 'Messaging',          'description': 'Broadcasts, support threads, DMs'},
        {'name': 'Analytics Admin',    'description': 'Revenue, user, engagement analytics'},
        {'name': 'System Config',      'description': 'Runtime configuration management'},
        {'name': 'Feature Flags',      'description': 'Feature toggle and rollout'},
        {'name': 'Maintenance',        'description': 'Maintenance windows, system status'},
        {'name': 'Reports',            'description': 'Report generation, scheduling, export'},
        {'name': 'Audit & Compliance', 'description': 'GDPR, AML, audit logs'},
        {'name': 'Integration System', 'description': 'Cross-app integration health and events'},
    ],
    'SECURITY': [{'BearerAuth': []}],
    'SCHEMA_PATH_PREFIX': '/api/admin-panel/',
}

# ==================== DOC URL PATTERNS ====================
doc_urlpatterns = [
    path('schema/',   SpectacularAPIView.as_view(), name='admin-panel-schema'),
    path('docs/',     SpectacularSwaggerView.as_view(url_name='admin-panel-schema'), name='admin-panel-swagger'),
    path('redoc/',    SpectacularRedocView.as_view(url_name='admin-panel-schema'), name='admin-panel-redoc'),
]

# ==================== COMMON RESPONSE EXAMPLES ====================
SUCCESS_EXAMPLE = OpenApiExample(
    'Success Response',
    value={'success': True, 'data': {}, 'message': '', 'timestamp': '2024-01-01T00:00:00Z'},
    response_only=True,
    status_codes=['200'],
)
ERROR_EXAMPLE = OpenApiExample(
    'Error Response',
    value={'success': False, 'error': 'Description of what went wrong'},
    response_only=True,
    status_codes=['400', '403', '404'],
)