# api/offer_inventory/schemas.py
"""
OpenAPI Schema Extensions.
Custom schema descriptions for drf-spectacular.
Auto-generates Swagger/OpenAPI docs for all endpoints.
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiResponse,
    OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


# ── Common Parameters ─────────────────────────────────────────────

DAYS_PARAM = OpenApiParameter(
    name='days', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Number of days for the report period (default: 30)',
    default=30, required=False,
)

FORMAT_PARAM = OpenApiParameter(
    name='format', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description='Response format: json or csv',
    enum=['json', 'csv'], default='json', required=False,
)

PAGE_PARAM = OpenApiParameter(
    name='page', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Page number (default: 1)',
    default=1, required=False,
)

PAGE_SIZE_PARAM = OpenApiParameter(
    name='page_size', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description='Results per page (max: 100)',
    default=20, required=False,
)

TENANT_HEADER = OpenApiParameter(
    name='X-Tenant-ID', type=OpenApiTypes.STR, location=OpenApiParameter.HEADER,
    description='Tenant identifier (multi-tenant deployments)',
    required=False,
)

API_KEY_HEADER = OpenApiParameter(
    name='X-API-Key', type=OpenApiTypes.STR, location=OpenApiParameter.HEADER,
    description='API key for external integrations',
    required=False,
)

# ── Schema Decorators ─────────────────────────────────────────────

OFFER_LIST_SCHEMA = extend_schema(
    summary='List active offers',
    description=(
        'Returns a paginated list of active offers filtered by geo, device, '
        'and visibility rules. Offers are sorted by featured status and reward amount.'
    ),
    parameters=[
        PAGE_PARAM, PAGE_SIZE_PARAM, TENANT_HEADER,
        OpenApiParameter('status', OpenApiTypes.STR, description='Filter by status (active, paused)'),
        OpenApiParameter('category', OpenApiTypes.STR, description='Filter by category slug'),
        OpenApiParameter('min_reward', OpenApiTypes.FLOAT, description='Minimum reward amount'),
    ],
    responses={
        200: OpenApiResponse(description='Paginated offer list'),
        401: OpenApiResponse(description='Authentication required'),
        403: OpenApiResponse(description='Access denied (IP blocked, suspended account)'),
    },
)

OFFER_CLICK_SCHEMA = extend_schema(
    summary='Record an offer click',
    description=(
        'Records a click on an offer and returns a signed click token. '
        'Performs bot detection, IP check, duplicate check, and rate limiting.'
    ),
    responses={
        200: OpenApiResponse(
            description='Click recorded successfully',
            examples=[OpenApiExample(
                'Success',
                value={'click_token': 'abc123...', 'offer_url': 'https://...'},
            )],
        ),
        403: OpenApiResponse(description='Blocked: IP blocked, bot detected, or fraud'),
        429: OpenApiResponse(description='Rate limit exceeded'),
    },
)

POSTBACK_SCHEMA = extend_schema(
    summary='S2S Postback endpoint',
    description=(
        'Receives server-to-server conversion postbacks from ad networks. '
        'Validates IP whitelist, HMAC signature, and timestamp freshness. '
        'Creates conversion records and triggers reward payouts.'
    ),
    parameters=[
        OpenApiParameter('click_id', OpenApiTypes.STR, description='Click identifier (required)'),
        OpenApiParameter('transaction_id', OpenApiTypes.STR, description='Unique transaction ID'),
        OpenApiParameter('payout', OpenApiTypes.FLOAT, description='Payout amount'),
        OpenApiParameter('status', OpenApiTypes.STR, description='Conversion status'),
        OpenApiParameter('signature', OpenApiTypes.STR, description='HMAC-SHA256 signature'),
    ],
    auth=[],   # No auth - uses IP whitelist + HMAC
    responses={
        200: OpenApiResponse(description='Conversion processed'),
        400: OpenApiResponse(description='Invalid postback data'),
        403: OpenApiResponse(description='IP not whitelisted or invalid signature'),
    },
)

WITHDRAWAL_CREATE_SCHEMA = extend_schema(
    summary='Request a withdrawal',
    description=(
        'Creates a withdrawal request. '
        'Validates: minimum amount (৳50), KYC status, wallet balance, AML checks. '
        'Debits wallet immediately and creates pending request.'
    ),
    responses={
        201: OpenApiResponse(description='Withdrawal request created'),
        400: OpenApiResponse(description='Validation failed (insufficient balance, below minimum)'),
        403: OpenApiResponse(description='KYC required or wallet locked'),
    },
)

DASHBOARD_KPI_SCHEMA = extend_schema(
    summary='Platform KPI dashboard',
    description=(
        'Returns comprehensive platform KPIs including: '
        'user metrics (DAU/MAU/retention), click metrics, '
        'conversion rates, revenue breakdown, withdrawal stats.'
    ),
    parameters=[DAYS_PARAM, TENANT_HEADER],
    responses={200: OpenApiResponse(description='KPI data')},
)

GDPR_EXPORT_SCHEMA = extend_schema(
    summary='GDPR data export (Article 20)',
    description=(
        'Returns all personal data held about the authenticated user. '
        'Includes: profile, clicks, conversions, withdrawals, wallet history, referrals.'
    ),
    responses={200: OpenApiResponse(description='User data export')},
)

GDPR_DELETE_SCHEMA = extend_schema(
    summary='GDPR erasure request (Article 17)',
    description=(
        'Anonymizes all personal data for the authenticated user. '
        'Financial audit records are preserved (legal obligation). '
        'Action is irreversible.'
    ),
    responses={200: OpenApiResponse(description='Data anonymized')},
)

HEALTH_SCHEMA = extend_schema(
    summary='System health check',
    description='Returns health status of DB, Redis, Celery, and storage.',
    auth=[],
    responses={
        200: OpenApiResponse(description='All systems healthy'),
        207: OpenApiResponse(description='Degraded — some components unhealthy'),
    },
)

SMARTLINK_SCHEMA = extend_schema(
    summary='SmartLink redirect',
    description=(
        'Resolves a SmartLink to the best available offer using AI scoring '
        '(EPC × CVR × Availability). Auto-rotates if best offer is capped.'
    ),
    auth=[],
    responses={
        302: OpenApiResponse(description='Redirect to offer URL'),
        404: OpenApiResponse(description='SmartLink not found or no offers available'),
    },
)

REVENUE_REPORT_SCHEMA = extend_schema(
    summary='Revenue report',
    description='Daily revenue breakdown. Use ?format=csv to download CSV.',
    parameters=[DAYS_PARAM, FORMAT_PARAM, TENANT_HEADER],
    responses={200: OpenApiResponse(description='Revenue data (JSON or CSV)')},
)

MARKETING_CAMPAIGN_SCHEMA = extend_schema(
    summary='Send marketing campaign',
    description=(
        'Sends a targeted campaign to a user segment. '
        'Channels: in_app (instant), push (Web Push), email (queued). '
        'Criteria filters: min_earnings, country, loyalty_level, inactive days.'
    ),
    responses={
        200: OpenApiResponse(description='Campaign sent'),
        400: OpenApiResponse(description='No users match criteria or invalid channel'),
    },
)

# ── Tag Groups ────────────────────────────────────────────────────

SPECTACULAR_TAGS = [
    {'name': 'Offers',       'description': 'Offer management and discovery'},
    {'name': 'Conversions',  'description': 'Conversion tracking and postback'},
    {'name': 'Wallet',       'description': 'Wallet, withdrawals, transactions'},
    {'name': 'User',         'description': 'User profile, KYC, achievements'},
    {'name': 'Marketing',    'description': 'Campaigns, push, loyalty, referral'},
    {'name': 'Analytics',    'description': 'KPIs, reports, forecasts'},
    {'name': 'Business',     'description': 'Advertiser portal, billing, compliance'},
    {'name': 'Fraud',        'description': 'Fraud detection and security'},
    {'name': 'System',       'description': 'Health check, circuits, bulk ops'},
]

# ── OpenAPI Settings for drf-spectacular ─────────────────────────

SPECTACULAR_SETTINGS = {
    'TITLE'      : 'Offer Inventory API',
    'DESCRIPTION': (
        '## Offer Inventory — Production API v2\n\n'
        'Complete earning platform offer management system.\n\n'
        '### Authentication\n'
        '- **JWT Bearer**: `Authorization: Bearer <token>`\n'
        '- **API Key**: `X-API-Key: oi_<key>` (for integrations)\n\n'
        '### Rate Limits\n'
        '- Default: 1000 req/min per API key\n'
        '- Clicks: 100/min per IP\n'
        '- Withdrawals: 3/hour per user\n\n'
        '### Postback Security\n'
        '- IP Whitelist (CIDR supported)\n'
        '- HMAC-SHA256 signature\n'
        '- Timestamp freshness (±5 min)\n'
    ),
    'VERSION'    : '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking'   : True,
        'persistAuthorization': True,
        'displayOperationId': False,
    },
    'TAGS': SPECTACULAR_TAGS,
    'CONTACT': {
        'name'  : 'API Support',
        'email' : 'api@yourplatform.com',
    },
    'LICENSE': {
        'name': 'Proprietary',
    },
}
