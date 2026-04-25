# api/payment_gateways/schemas.py
# OpenAPI schema customizations for drf-spectacular
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

DEPOSIT_SCHEMA = extend_schema(
    summary='Initiate deposit',
    description='Start a deposit via any supported gateway. Returns payment URL.',
    parameters=[
        OpenApiParameter('gateway', OpenApiTypes.STR, description='Gateway: bkash|nagad|stripe|paypal|...'),
        OpenApiParameter('amount',  OpenApiTypes.DECIMAL, description='Amount in gateway currency'),
    ],
    examples=[OpenApiExample('bKash 500 BDT', value={'gateway':'bkash','amount':'500','currency':'BDT'})]
)

WITHDRAWAL_SCHEMA = extend_schema(
    summary='Request withdrawal',
    description='Submit withdrawal request. Admin approval required unless Fast Pay enabled.',
)

GATEWAY_LIST_SCHEMA = extend_schema(
    summary='List payment gateways',
    description='Returns all active gateways with health status and limits.',
)

TRANSACTION_HISTORY_SCHEMA = extend_schema(
    summary='Transaction history',
    description='Paginated transaction history for current user.',
    parameters=[
        OpenApiParameter('gateway',  description='Filter by gateway'),
        OpenApiParameter('status',   description='Filter by status: pending|completed|failed'),
        OpenApiParameter('date_from',OpenApiTypes.DATE, description='Start date YYYY-MM-DD'),
        OpenApiParameter('date_to',  OpenApiTypes.DATE, description='End date YYYY-MM-DD'),
    ]
)

OFFER_FEED_SCHEMA = extend_schema(
    summary='Publisher offer feed',
    description='Get list of active CPA/CPI offers available for promotion.',
    parameters=[
        OpenApiParameter('type',     description='Offer type: cpa|cpi|cpc|cpl|cps'),
        OpenApiParameter('country',  description='Filter by country code: US|BD|GB|...'),
        OpenApiParameter('min_payout',OpenApiTypes.DECIMAL, description='Minimum payout filter'),
    ]
)
