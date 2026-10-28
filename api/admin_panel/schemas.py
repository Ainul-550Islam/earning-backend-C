# api/admin_panel/schemas.py
"""
OpenAPI/DRF Spectacular schemas for admin_panel API documentation.
Auto-generates Swagger UI docs for all admin endpoints.
"""
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers


# ==================== RESPONSE SCHEMAS ====================

class AdminSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField(allow_blank=True)
    data     = serializers.DictField(allow_null=True)
    timestamp = serializers.DateTimeField()


class AdminErrorResponseSerializer(serializers.Serializer):
    success  = serializers.BooleanField(default=False)
    error    = serializers.CharField()
    errors   = serializers.ListField(child=serializers.DictField(), required=False)
    timestamp = serializers.DateTimeField()


class PaginatedResponseSerializer(serializers.Serializer):
    count    = serializers.IntegerField()
    next     = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results  = serializers.ListField()


# ==================== COMMON PARAMETERS ====================

COMMON_PARAMS = {
    'page': OpenApiParameter('page', OpenApiTypes.INT, description='Page number (default: 1)'),
    'page_size': OpenApiParameter('page_size', OpenApiTypes.INT, description='Results per page (default: 25, max: 200)'),
    'search': OpenApiParameter('q', OpenApiTypes.STR, description='Search query (min 2 chars)'),
    'start_date': OpenApiParameter('start_date', OpenApiTypes.DATE, description='Filter from date (YYYY-MM-DD)'),
    'end_date': OpenApiParameter('end_date', OpenApiTypes.DATE, description='Filter to date (YYYY-MM-DD)'),
    'days': OpenApiParameter('days', OpenApiTypes.INT, description='Last N days (default: 7)'),
    'force': OpenApiParameter('force', OpenApiTypes.BOOL, description='Bypass cache and fetch fresh data'),
}

# ==================== SCHEMA DECORATORS ====================

live_kpis_schema = extend_schema(
    summary='Live KPIs',
    description='Real-time admin dashboard KPIs — users, wallet, conversions, withdrawals, fraud. Cache: 30s.',
    responses={200: AdminSuccessResponseSerializer},
    tags=['Real-time Dashboard'],
)

fraud_rules_schema = extend_schema(
    summary='List Fraud Rules',
    description='All configured fraud detection rules with severity and action.',
    parameters=[COMMON_PARAMS['page'], COMMON_PARAMS['page_size']],
    responses={200: AdminSuccessResponseSerializer},
    tags=['Fraud Control'],
)

approve_withdrawal_schema = extend_schema(
    summary='Approve Withdrawal',
    description='Approve a single pending withdrawal request. Optionally attach transaction reference.',
    request={'application/json': {'type': 'object', 'properties': {
        'item_id': {'type': 'integer'},
        'transaction_ref': {'type': 'string'},
    }, 'required': ['item_id']}},
    responses={200: AdminSuccessResponseSerializer, 400: AdminErrorResponseSerializer},
    tags=['Payout Admin'],
)

ban_user_schema = extend_schema(
    summary='Ban User',
    description='Ban a user — disables account, optionally freezes wallet and cancels pending payouts.',
    request={'application/json': {'type': 'object', 'properties': {
        'user_id': {'type': 'integer'},
        'reason': {'type': 'string'},
        'freeze_wallet': {'type': 'boolean', 'default': True},
    }, 'required': ['user_id', 'reason']}},
    responses={200: AdminSuccessResponseSerializer, 404: AdminErrorResponseSerializer},
    tags=['User Management'],
)

send_broadcast_schema = extend_schema(
    summary='Send Admin Broadcast',
    description='Send in-app notification to all or filtered users.',
    request={'application/json': {'type': 'object', 'properties': {
        'title': {'type': 'string'},
        'body': {'type': 'string'},
        'audience_type': {'type': 'string', 'enum': ['all', 'active', 'premium', 'filtered']},
    }, 'required': ['title', 'body']}},
    responses={200: AdminSuccessResponseSerializer},
    tags=['Messaging'],
)