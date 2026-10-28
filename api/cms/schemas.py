# cms/schemas.py
"""
OpenAPI / DRF Spectacular schema customization for CMS.

v11 additions:
  - Offerwall endpoint schemas
  - Finance / Wallet / Transaction / PayoutRequest schemas
  - BusinessLogicViewSet schemas
  - PushNotificationViewSet schemas
  - SelectorViewSet schemas
  - InteractorViewSet schemas
  - RepositoryViewSet schemas
  - AdapterStatusViewSet schemas

All existing schemas are preserved exactly.
drf-spectacular is used when available; graceful stubs when not installed.
"""
from typing import Dict, List, Any, Optional, Tuple, Union

try:
    from drf_spectacular.utils import (
        extend_schema,
        OpenApiParameter,
        OpenApiResponse,
        OpenApiExample,
        inline_serializer,
    )
    from drf_spectacular.openapi import AutoSchema
    from drf_spectacular.types import OpenApiTypes
    import rest_framework.serializers as _s
    HAS_SPECTACULAR = True
except ImportError:
    HAS_SPECTACULAR = False

    def extend_schema(**kwargs):
        def decorator(func):
            return func
        return decorator

    class OpenApiParameter:
        QUERY = 'query'
        PATH  = 'path'
        def __init__(self, *a, **kw):
            pass

    class OpenApiResponse:
        def __init__(self, *a, **kw):
            pass

    class OpenApiExample:
        def __init__(self, *a, **kw):
            pass

    class OpenApiTypes:
        STR  = str
        INT  = int
        BOOL = bool
        UUID = str

    def inline_serializer(*a, **kw):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Existing Schemas (preserved exactly)
# ─────────────────────────────────────────────────────────────────────────────

def survey_list_schema():
    return extend_schema(
        summary="List Surveys",
        description="Get list of available surveys for the current user.",
        parameters=[
            OpenApiParameter(name='status',     location='query', type=str,
                             enum=['active', 'inactive', 'draft']),
            OpenApiParameter(name='difficulty', location='query', type=str,
                             enum=['easy', 'medium', 'hard']),
            OpenApiParameter(name='category',   location='query', type=str),
            OpenApiParameter(name='search',     location='query', type=str),
            OpenApiParameter(name='limit',      location='query', type=int),
        ],
        responses={200: OpenApiResponse(description="List of surveys")},
        tags=['Surveys'],
    )


def survey_start_schema():
    return extend_schema(
        summary="Start Survey",
        description="Start a survey for the current user.",
        responses={200: OpenApiResponse(description="Survey started successfully")},
        tags=['Surveys'],
    )


def survey_submit_schema():
    return extend_schema(
        summary="Submit Survey",
        description="Submit survey responses.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'responses': {'type': 'array',
                                  'items': {'type': 'object'}},
                },
                'required': ['responses'],
            }
        },
        responses={200: OpenApiResponse(description="Survey submitted successfully")},
        tags=['Surveys'],
    )


def reward_list_schema():
    return extend_schema(
        summary="List Rewards",
        description="Get list of user rewards.",
        parameters=[
            OpenApiParameter(name='status',    location='query', type=str),
            OpenApiParameter(name='reward_type', location='query', type=str),
            OpenApiParameter(name='date_from', location='query', type=str),
            OpenApiParameter(name='date_to',   location='query', type=str),
        ],
        responses={200: OpenApiResponse(description="List of rewards")},
        tags=['Rewards'],
    )


def task_list_schema():
    return extend_schema(
        summary="List Tasks",
        description="Get list of scheduled tasks.",
        parameters=[
            OpenApiParameter(name='status',    location='query', type=str),
            OpenApiParameter(name='task_type', location='query', type=str),
        ],
        responses={200: OpenApiResponse(description="List of tasks")},
        tags=['Task Management'],
    )


def task_execute_schema():
    return extend_schema(
        summary="Execute Task",
        description="Manually trigger a task execution.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {'params': {'type': 'object'}},
            }
        },
        responses={
            200: OpenApiResponse(description="Task executed successfully"),
            400: OpenApiResponse(description="Execution failed"),
        },
        tags=['Task Management'],
    )


def user_profile_schema():
    return extend_schema(
        summary="Get User Profile",
        description="Get detailed user profile information.",
        responses={200: OpenApiResponse(description="User profile data")},
        tags=['User Profile'],
    )


def user_segment_assign_schema():
    return extend_schema(
        summary="Assign User Segments",
        description="Assign users to segments for targeted campaigns.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_ids':  {'type': 'array', 'items': {'type': 'integer'}},
                    'segment':   {'type': 'string'},
                },
                'required': ['user_ids'],
            }
        },
        responses={200: OpenApiResponse(description="Users assigned successfully")},
        tags=['User Segments'],
    )


def analytics_dashboard_schema():
    return extend_schema(
        summary="Get Dashboard Analytics",
        description="Get comprehensive dashboard analytics.",
        parameters=[
            OpenApiParameter(name='days', location='query', type=int, default=30),
        ],
        responses={200: OpenApiResponse(description="Dashboard analytics data")},
        tags=['Analytics'],
    )


def analytics_report_schema():
    return extend_schema(
        summary="Generate Report",
        description="Generate various types of reports.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'report_type': {
                        'type': 'string',
                        'enum': ['survey_completion', 'reward_transactions',
                                 'task_execution', 'user_activity'],
                    },
                    'filters': {'type': 'object'},
                    'format':  {'type': 'string', 'enum': ['csv', 'json', 'xlsx'],
                                'default': 'csv'},
                },
                'required': ['report_type'],
            }
        },
        responses={200: OpenApiResponse(description="Report generated successfully")},
        tags=['Analytics'],
    )


def cpalead_postback_schema():
    return extend_schema(
        summary="CPAlead Postback",
        description=(
            "Receives CPAlead postback when user completes offer. "
            "Required params: subid, payout, lead_id, password. "
            "Returns '1' (text/plain) on success."
        ),
        parameters=[
            OpenApiParameter(name='subid',    location='query', required=True,  type=str),
            OpenApiParameter(name='payout',   location='query', required=True,  type=str),
            OpenApiParameter(name='lead_id',  location='query', required=True,  type=str),
            OpenApiParameter(name='password', location='query', required=False, type=str),
        ],
        responses={200: OpenApiResponse(description="'1' on success, '0' on failure")},
        tags=['CPAlead'],
        auth=[],
    )


def leaderboard_schema():
    return extend_schema(
        summary="Get Leaderboard",
        parameters=[
            OpenApiParameter(name='period',   location='query', type=str,
                             enum=['daily', 'weekly', 'monthly', 'alltime']),
            OpenApiParameter(name='category', location='query', type=str,
                             enum=['earnings', 'coins', 'offers', 'referrals']),
            OpenApiParameter(name='limit',    location='query', type=int),
        ],
        tags=['Leaderboard'],
    )


def offerwall_schema():
    return extend_schema(
        summary="Get Offerwall Embed",
        description="Returns embed code, currency config, and JS src for the CPAlead offerwall.",
        tags=['CPAlead Offerwall'],
        auth=[],
    )


def withdrawal_schema():
    return extend_schema(
        summary="Request Withdrawal",
        description="Convert coins to USD and request payout via PayPal, Payoneer, USDT, etc.",
        tags=['Withdrawal'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — Offerwall App Schemas
# ─────────────────────────────────────────────────────────────────────────────

def offer_list_schema():
    return extend_schema(
        summary="List Offers",
        description=(
            "Returns paginated active offers from the offerwall. "
            "Filtered by device, country, and user level automatically."
        ),
        parameters=[
            OpenApiParameter(name='status',  location='query', type=str,
                             enum=['active', 'paused', 'expired', 'draft']),
            OpenApiParameter(name='source',  location='query', type=str,
                             enum=['cpalead', 'internal', 'partner']),
            OpenApiParameter(name='device',  location='query', type=str,
                             enum=['all', 'mobile', 'desktop']),
            OpenApiParameter(name='country', location='query', type=str,
                             description='ISO-2 country code, e.g. BD'),
            OpenApiParameter(name='limit',   location='query', type=int, default=20),
            OpenApiParameter(name='offset',  location='query', type=int, default=0),
        ],
        responses={
            200: OpenApiResponse(description="Paginated list of offers"),
            401: OpenApiResponse(description="Unauthenticated"),
        },
        tags=['Offerwall'],
    )


def offer_detail_schema():
    return extend_schema(
        summary="Get Offer Detail",
        description="Returns full offer details including analytics and targeting.",
        parameters=[
            OpenApiParameter(name='id', location='path', type=str,
                             description='UUID of the offer'),
        ],
        responses={
            200: OpenApiResponse(description="Offer detail"),
            404: OpenApiResponse(description="Offer not found"),
        },
        tags=['Offerwall'],
    )


def offer_create_schema():
    return extend_schema(
        summary="Create Offer",
        description="Admin: create a new offerwall offer.",
        responses={
            201: OpenApiResponse(description="Offer created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Offerwall'],
    )


def offer_click_schema():
    return extend_schema(
        summary="Record Offer Click",
        description=(
            "Record a click on an offer for the authenticated user. "
            "Returns the offer's click URL for redirect."
        ),
        responses={
            200: OpenApiResponse(description="Click recorded, click_url returned"),
            404: OpenApiResponse(description="Offer not found"),
        },
        tags=['Offerwall'],
    )


def offer_conversion_list_schema():
    return extend_schema(
        summary="List Offer Conversions",
        description="Admin: list all conversions. User: list own conversions.",
        parameters=[
            OpenApiParameter(name='status', location='query', type=str,
                             enum=['pending', 'approved', 'rejected']),
            OpenApiParameter(name='user_id', location='query', type=int,
                             description='Admin only: filter by user ID'),
            OpenApiParameter(name='date_from', location='query', type=str,
                             description='ISO-8601 date'),
            OpenApiParameter(name='date_to',   location='query', type=str,
                             description='ISO-8601 date'),
        ],
        responses={200: OpenApiResponse(description="Conversion list")},
        tags=['Offerwall'],
    )


def offer_conversion_status_schema():
    return extend_schema(
        summary="Update Conversion Status",
        description="Admin: approve or reject a conversion.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'enum': ['approved', 'rejected']},
                    'reason': {'type': 'string', 'description': 'Required when rejecting'},
                },
                'required': ['status'],
            }
        },
        responses={
            200: OpenApiResponse(description="Status updated"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Offerwall'],
    )


def offerwall_stats_schema():
    return extend_schema(
        summary="Offerwall Statistics",
        description="Admin: aggregated offerwall performance statistics.",
        responses={200: OpenApiResponse(description="Stats object")},
        tags=['Offerwall'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — Finance App Schemas
# ─────────────────────────────────────────────────────────────────────────────

def wallet_detail_schema():
    return extend_schema(
        summary="Get My Wallet",
        description="Returns the authenticated user's wallet balance and status.",
        responses={
            200: OpenApiResponse(description="Wallet details"),
            401: OpenApiResponse(description="Unauthenticated"),
        },
        tags=['Finance – Wallet'],
    )


def wallet_admin_list_schema():
    return extend_schema(
        summary="List All Wallets",
        description="Admin: list all user wallets with balance summary.",
        parameters=[
            OpenApiParameter(name='is_locked', location='query', type=bool),
            OpenApiParameter(name='min_balance', location='query', type=str,
                             description='Minimum USD balance'),
            OpenApiParameter(name='limit',  location='query', type=int, default=50),
            OpenApiParameter(name='offset', location='query', type=int, default=0),
        ],
        responses={200: OpenApiResponse(description="Wallet list")},
        tags=['Finance – Wallet'],
    )


def wallet_lock_schema():
    return extend_schema(
        summary="Lock / Unlock Wallet",
        description="Admin: lock or unlock a user wallet.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'is_locked':      {'type': 'boolean'},
                    'locked_reason':  {'type': 'string'},
                },
                'required': ['is_locked'],
            }
        },
        responses={
            200: OpenApiResponse(description="Wallet lock status updated"),
            400: OpenApiResponse(description="locked_reason required when locking"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Finance – Wallet'],
    )


def transaction_list_schema():
    return extend_schema(
        summary="List Transactions",
        description="Returns the authenticated user's transaction history.",
        parameters=[
            OpenApiParameter(name='transaction_type', location='query', type=str,
                             enum=['credit', 'debit', 'hold', 'release', 'reversal']),
            OpenApiParameter(name='source',  location='query', type=str,
                             enum=['offer_completion', 'survey_completion', 'bonus',
                                   'referral', 'withdrawal', 'admin_adjustment', 'refund']),
            OpenApiParameter(name='status',  location='query', type=str,
                             enum=['pending', 'completed', 'failed', 'reversed']),
            OpenApiParameter(name='date_from', location='query', type=str),
            OpenApiParameter(name='date_to',   location='query', type=str),
            OpenApiParameter(name='limit',  location='query', type=int, default=20),
            OpenApiParameter(name='offset', location='query', type=int, default=0),
        ],
        responses={200: OpenApiResponse(description="Transaction list")},
        tags=['Finance – Transactions'],
    )


def transaction_admin_create_schema():
    return extend_schema(
        summary="Create Manual Transaction",
        description="Admin: create a credit/debit/bonus transaction for a user.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user':             {'type': 'integer'},
                    'amount_usd':       {'type': 'number'},
                    'amount_virtual':   {'type': 'number'},
                    'transaction_type': {'type': 'string', 'enum': ['credit', 'debit']},
                    'source':           {'type': 'string'},
                    'description':      {'type': 'string'},
                },
                'required': ['user', 'amount_usd', 'transaction_type', 'source'],
            }
        },
        responses={
            201: OpenApiResponse(description="Transaction created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Finance – Transactions'],
    )


def payout_request_create_schema():
    return extend_schema(
        summary="Request Payout",
        description=(
            "Create a new payout request. "
            "The user must have sufficient balance and pass fraud checks."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount_requested': {'type': 'number',
                                        'description': 'Amount in USD to withdraw'},
                    'method':           {'type': 'string',
                                        'enum': ['paypal', 'stripe', 'bkash',
                                                 'nagad', 'crypto', 'bank_transfer']},
                    'destination':      {'type': 'string',
                                        'description': 'PayPal email, phone, wallet address'},
                },
                'required': ['amount_requested', 'method', 'destination'],
            }
        },
        responses={
            201: OpenApiResponse(description="Payout request created"),
            400: OpenApiResponse(description="Validation or balance error"),
            401: OpenApiResponse(description="Unauthenticated"),
        },
        tags=['Finance – Payouts'],
    )


def payout_request_list_schema():
    return extend_schema(
        summary="List Payout Requests",
        description="Admin: list all payout requests. User: list own payout history.",
        parameters=[
            OpenApiParameter(name='status',  location='query', type=str,
                             enum=['pending', 'approved', 'paid', 'rejected', 'failed']),
            OpenApiParameter(name='method',  location='query', type=str),
            OpenApiParameter(name='user_id', location='query', type=int,
                             description='Admin only'),
            OpenApiParameter(name='date_from', location='query', type=str),
            OpenApiParameter(name='date_to',   location='query', type=str),
            OpenApiParameter(name='limit',  location='query', type=int, default=20),
        ],
        responses={200: OpenApiResponse(description="Payout request list")},
        tags=['Finance – Payouts'],
    )


def payout_status_update_schema():
    return extend_schema(
        summary="Update Payout Status",
        description="Admin: approve, reject, or mark payout request as paid.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status':           {'type': 'string',
                                        'enum': ['approved', 'rejected', 'paid']},
                    'rejection_reason': {'type': 'string'},
                    'external_ref':     {'type': 'string',
                                        'description': 'Gateway transaction ID (required when paid)'},
                    'admin_notes':      {'type': 'string'},
                },
                'required': ['status'],
            }
        },
        responses={
            200: OpenApiResponse(description="Status updated"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Finance – Payouts'],
    )


def reconciliation_list_schema():
    return extend_schema(
        summary="List Reconciliation Logs",
        description="Admin: list daily financial reconciliation audit records.",
        parameters=[
            OpenApiParameter(name='is_balanced', location='query', type=bool),
            OpenApiParameter(name='date_from',   location='query', type=str),
            OpenApiParameter(name='date_to',     location='query', type=str),
        ],
        responses={200: OpenApiResponse(description="Reconciliation log list")},
        tags=['Finance – Reconciliation'],
    )


def finance_dashboard_schema():
    return extend_schema(
        summary="Finance Dashboard",
        description="Admin: aggregated financial metrics for the ops dashboard.",
        responses={200: OpenApiResponse(description="Dashboard metrics")},
        tags=['Finance – Dashboard'],
    )


def bulk_transaction_schema():
    return extend_schema(
        summary="Bulk Credit / Debit",
        description=(
            "Admin: apply a credit or debit to multiple users in a single operation. "
            "All transactions are created atomically with audit trail."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_ids':         {'type': 'array', 'items': {'type': 'integer'},
                                        'minItems': 1, 'maxItems': 1000},
                    'amount_usd':       {'type': 'number'},
                    'transaction_type': {'type': 'string', 'enum': ['credit', 'debit']},
                    'source':           {'type': 'string'},
                    'description':      {'type': 'string'},
                },
                'required': ['user_ids', 'amount_usd', 'transaction_type', 'source'],
            }
        },
        responses={
            200: OpenApiResponse(description="Bulk transaction result"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Finance – Admin'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — BusinessLogicViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def business_logic_fee_preview_schema():
    return extend_schema(
        summary="Fee Preview",
        description=(
            "Calculate the exact withdrawal fee and net amount before submitting. "
            "No database writes — pure calculation."
        ),
        parameters=[
            OpenApiParameter(name='amount', location='query', required=True,  type=str,
                             description='Withdrawal amount in USD'),
            OpenApiParameter(name='method', location='query', required=False, type=str,
                             enum=['paypal', 'stripe', 'bkash', 'nagad', 'crypto', 'bank_transfer'],
                             default='paypal'),
        ],
        responses={
            200: OpenApiResponse(description="Fee breakdown (amount_requested, fee, net_amount)"),
            400: OpenApiResponse(description="Invalid amount or method"),
        },
        tags=['Business Logic Tools'],
    )


def business_logic_coins_preview_schema():
    return extend_schema(
        summary="Coins Preview (USD → Coins)",
        description="How many coins a given USD amount converts to at the current rate.",
        parameters=[
            OpenApiParameter(name='usd', location='query', required=True, type=str,
                             description='USD amount'),
        ],
        responses={200: OpenApiResponse(description="Coins conversion result")},
        tags=['Business Logic Tools'],
    )


def business_logic_coins_to_usd_schema():
    return extend_schema(
        summary="Coins to USD Conversion",
        description="USD value of a given coin balance.",
        parameters=[
            OpenApiParameter(name='coins', location='query', required=True, type=str),
        ],
        responses={200: OpenApiResponse(description="USD conversion result")},
        tags=['Business Logic Tools'],
    )


def business_logic_my_level_schema():
    return extend_schema(
        summary="My Level",
        description="User's current level, XP, and progress towards the next level.",
        responses={200: OpenApiResponse(description="Level and progression data")},
        tags=['Business Logic Tools'],
    )


def business_logic_streak_multiplier_schema():
    return extend_schema(
        summary="Streak Multiplier",
        description="Reward multiplier for a given earning streak length.",
        parameters=[
            OpenApiParameter(name='streak_days', location='query', type=int, default=0),
        ],
        responses={200: OpenApiResponse(description="Multiplier value and bonus percentage")},
        tags=['Business Logic Tools'],
    )


def business_logic_embed_url_schema():
    return extend_schema(
        summary="Generate Offerwall Embed URL",
        description=(
            "Personalised CPAlead offerwall embed URL for the authenticated user. "
            "Use as the src of an <iframe> on the earn page."
        ),
        responses={
            200: OpenApiResponse(description="embed_url, subid, device"),
            503: OpenApiResponse(description="OfferWall not configured"),
        },
        tags=['Business Logic Tools'],
    )


def business_logic_survey_quality_schema():
    return extend_schema(
        summary="Survey Quality Score",
        description="Calculate quality score for a set of survey responses.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'responses': {'type': 'array', 'items': {'type': 'object'}},
                    'survey':    {'type': 'object'},
                },
                'required': ['responses', 'survey'],
            }
        },
        responses={
            200: OpenApiResponse(description="quality_score, quality_grade, valid"),
            400: OpenApiResponse(description="Missing parameters"),
        },
        tags=['Business Logic Tools'],
    )


def business_logic_survey_reward_preview_schema():
    return extend_schema(
        summary="Survey Reward Preview",
        description="Reward the user would earn for a given survey before submission.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'survey':        {'type': 'object'},
                    'quality_score': {'type': 'number', 'description': '0–100'},
                },
                'required': ['survey'],
            }
        },
        responses={200: OpenApiResponse(description="Reward estimate")},
        tags=['Business Logic Tools'],
    )


def business_logic_my_segments_schema():
    return extend_schema(
        summary="My User Segments",
        description="User's current segments based on activity and earnings.",
        responses={200: OpenApiResponse(description="segments, participation_score")},
        tags=['Business Logic Tools'],
    )


def business_logic_pool_status_schema():
    return extend_schema(
        summary="Reward Pool Status",
        description="Admin: reward pool utilisation and refill status.",
        responses={200: OpenApiResponse(description="Pool status array")},
        tags=['Business Logic Tools'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — PushNotificationViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def push_register_device_schema():
    return extend_schema(
        summary="Register Push Device",
        description="Register an FCM, APNs, or Web Push token for the current user.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'token':       {'type': 'string'},
                    'platform':    {'type': 'string', 'enum': ['fcm', 'apns', 'webpush']},
                    'device_info': {'type': 'object'},
                },
                'required': ['token', 'platform'],
            }
        },
        responses={
            201: OpenApiResponse(description="Device registered"),
            400: OpenApiResponse(description="Token or platform missing/invalid"),
        },
        tags=['Push Notifications'],
    )


def push_unregister_device_schema():
    return extend_schema(
        summary="Unregister Push Device",
        description="Remove a device push token (on logout or opt-out).",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'token':    {'type': 'string'},
                    'platform': {'type': 'string'},
                },
                'required': ['token'],
            }
        },
        responses={200: OpenApiResponse(description="Device unregistered")},
        tags=['Push Notifications'],
    )


def push_my_devices_schema():
    return extend_schema(
        summary="My Registered Devices",
        description="List all push-registered devices for the current user.",
        responses={200: OpenApiResponse(description="devices list, count")},
        tags=['Push Notifications'],
    )


def push_history_schema():
    return extend_schema(
        summary="Push Notification History",
        description="Recent push notification history for the current user.",
        parameters=[
            OpenApiParameter(name='limit', location='query', type=int, default=20),
        ],
        responses={200: OpenApiResponse(description="notifications list, count")},
        tags=['Push Notifications'],
    )


def push_unread_count_schema():
    return extend_schema(
        summary="Unread Notification Count",
        description="Number of unread notifications (for badge on nav bar).",
        responses={200: OpenApiResponse(description="unread_count integer")},
        tags=['Push Notifications'],
    )


def push_mark_all_read_schema():
    return extend_schema(
        summary="Mark All Read",
        description="Mark all notifications as read for the current user.",
        responses={200: OpenApiResponse(description="success, marked count")},
        tags=['Push Notifications'],
    )


def push_subscribe_topic_schema():
    return extend_schema(
        summary="Subscribe to Push Topic",
        description="Opt in to a specific notification category.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'topic': {'type': 'string',
                              'enum': ['new_offers', 'streak_reminders', 'leaderboard',
                                       'survey_recommendations', 'withdrawal_updates',
                                       'referral_bonuses', 'system_announcements']},
                },
                'required': ['topic'],
            }
        },
        responses={
            200: OpenApiResponse(description="Subscribed"),
            400: OpenApiResponse(description="Invalid topic"),
        },
        tags=['Push Notifications'],
    )


def push_send_test_schema():
    return extend_schema(
        summary="Send Test Push",
        description="Admin: send a test push notification to a specific user.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_id': {'type': 'integer'},
                    'title':   {'type': 'string'},
                    'body':    {'type': 'string'},
                    'data':    {'type': 'object'},
                },
                'required': ['user_id', 'title', 'body'],
            }
        },
        responses={
            200: OpenApiResponse(description="Push sent"),
            404: OpenApiResponse(description="User not found"),
        },
        tags=['Push Notifications'],
    )


def push_bulk_schema():
    return extend_schema(
        summary="Bulk Push Notification",
        description="Admin: send a push to multiple users or a user segment.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_ids': {'type': 'array', 'items': {'type': 'integer'}},
                    'segment':  {'type': 'string'},
                    'title':    {'type': 'string'},
                    'body':     {'type': 'string'},
                    'data':     {'type': 'object'},
                },
                'required': ['title', 'body'],
            }
        },
        responses={200: OpenApiResponse(description="sent_count, failed_count")},
        tags=['Push Notifications'],
    )


def push_stats_schema():
    return extend_schema(
        summary="Push Notification Stats",
        description="Admin: registered device counts, delivery rates.",
        responses={200: OpenApiResponse(description="Stats object")},
        tags=['Push Notifications'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — SelectorViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def selector_top_earners_schema():
    return extend_schema(
        summary="Top Earners",
        description="Leaderboard of top earners sorted by total USD earned.",
        parameters=[
            OpenApiParameter(name='limit', location='query', type=int, default=10),
        ],
        responses={200: OpenApiResponse(description="top_earners list, count")},
        tags=['Selectors'],
    )


def selector_my_stats_schema():
    return extend_schema(
        summary="My Stats",
        description="Comprehensive stats for the authenticated user.",
        responses={200: OpenApiResponse(description="User stats object")},
        tags=['Selectors'],
    )


def selector_my_balance_schema():
    return extend_schema(
        summary="My Balance",
        description="Full balance details including today's earnings (cached).",
        responses={200: OpenApiResponse(description="balance, today_earnings, recent_transactions")},
        tags=['Selectors'],
    )


def selector_conversion_stats_schema():
    return extend_schema(
        summary="Conversion Stats",
        description="Admin: aggregated conversion counts and revenue.",
        parameters=[
            OpenApiParameter(name='days', location='query', type=int, default=30),
        ],
        responses={200: OpenApiResponse(description="Conversion stats")},
        tags=['Selectors'],
    )


def selector_active_offers_schema():
    return extend_schema(
        summary="Active Offers Feed",
        description="Targeted active offers for the current user (cached by country+device).",
        parameters=[
            OpenApiParameter(name='country', location='query', type=str,
                             description='ISO-2 country code'),
            OpenApiParameter(name='device',  location='query', type=str,
                             enum=['all', 'mobile', 'desktop']),
            OpenApiParameter(name='limit',   location='query', type=int, default=20),
        ],
        responses={200: OpenApiResponse(description="offers list, count, country, device")},
        tags=['Selectors'],
    )


def selector_leaderboard_schema():
    return extend_schema(
        summary="Leaderboard (Selector)",
        description="Leaderboard entries via optimised cached LeaderboardSelector.",
        parameters=[
            OpenApiParameter(name='period', location='query', type=str,
                             enum=['daily', 'weekly', 'monthly', 'alltime'], default='weekly'),
            OpenApiParameter(name='limit',  location='query', type=int, default=10),
        ],
        responses={200: OpenApiResponse(description="entries, count, my_rank, period")},
        tags=['Selectors'],
    )


def selector_my_referral_stats_schema():
    return extend_schema(
        summary="My Referral Stats",
        description="Referral code, relationship count, and earnings.",
        responses={200: OpenApiResponse(description="referral_code, earnings, total_earnings")},
        tags=['Selectors'],
    )


def selector_pending_withdrawals_schema():
    return extend_schema(
        summary="Pending Withdrawals",
        description="Admin: pending withdrawal requests sorted by oldest first.",
        parameters=[
            OpenApiParameter(name='limit', location='query', type=int, default=50),
        ],
        responses={200: OpenApiResponse(description="withdrawals list, count")},
        tags=['Selectors'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — InteractorViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def interactor_process_postback_schema():
    return extend_schema(
        summary="Process CPAlead Postback (Full Workflow)",
        description=(
            "Full postback processing: hash verification → deduplication → "
            "fraud scoring → coin award → referral bonus → streak → level-up → "
            "push notification. All steps atomic. "
            "Preferred over legacy CPALeadWebhookView."
        ),
        parameters=[
            OpenApiParameter(name='subid',    location='query', type=str),
            OpenApiParameter(name='payout',   location='query', type=str),
            OpenApiParameter(name='lead_id',  location='query', type=str),
            OpenApiParameter(name='offer_id', location='query', type=str),
            OpenApiParameter(name='hash',     location='query', type=str),
        ],
        responses={
            200: OpenApiResponse(description="Postback processing result"),
            400: OpenApiResponse(description="Invalid parameters"),
        },
        tags=['Interactors'],
        auth=[],
    )


def interactor_onboard_user_schema():
    return extend_schema(
        summary="Onboard New User (Full Workflow)",
        description=(
            "Full registration workflow: create User → create UserProfile + "
            "VirtualBalance → process referral code → award welcome bonus → "
            "send welcome notification → fire user_registered event. "
            "Returns JWT tokens for immediate login."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username':      {'type': 'string'},
                    'email':         {'type': 'string', 'format': 'email'},
                    'password':      {'type': 'string', 'minLength': 8},
                    'referral_code': {'type': 'string'},
                    'device_token':  {'type': 'string'},
                    'platform':      {'type': 'string', 'enum': ['fcm', 'apns', 'webpush']},
                },
                'required': ['username', 'email', 'password'],
            }
        },
        responses={
            201: OpenApiResponse(description="User created; JWT tokens in response"),
            400: OpenApiResponse(description="Validation or duplicate error"),
        },
        tags=['Interactors'],
        auth=[],
    )


def interactor_approve_withdrawal_schema():
    return extend_schema(
        summary="Approve Withdrawal (Full Workflow)",
        description=(
            "Admin: full approval workflow: validate → fraud re-check → "
            "deduct balance → call payment gateway → audit trail → "
            "user notification → fire event."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'request_id': {'type': 'integer'},
                    'note':       {'type': 'string'},
                },
                'required': ['request_id'],
            }
        },
        responses={
            200: OpenApiResponse(description="Withdrawal approved"),
            400: OpenApiResponse(description="Invalid state or fraud block"),
            403: OpenApiResponse(description="Admin access required"),
        },
        tags=['Interactors'],
    )


def interactor_submit_survey_schema():
    return extend_schema(
        summary="Submit Survey (Full Workflow)",
        description=(
            "Full survey submission: validate responses → quality score → "
            "award reward coins → update streak → level-up check → "
            "fire survey_completed event → send notification."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'completion_id': {'type': 'string', 'format': 'uuid'},
                    'responses':     {'type': 'array',
                                     'items': {'type': 'object',
                                               'properties': {
                                                   'question_id': {'type': 'integer'},
                                                   'answer': {'type': 'string'},
                                               }}},
                },
                'required': ['completion_id', 'responses'],
            }
        },
        responses={
            200: OpenApiResponse(description="Survey submitted; reward awarded"),
            400: OpenApiResponse(description="Validation or quality failure"),
        },
        tags=['Interactors'],
    )


def interactor_execute_schema():
    return extend_schema(
        summary="Execute Interactor (Admin)",
        description="Admin: execute any registered interactor by name.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'interactor': {'type': 'string',
                                   'enum': ['PostbackProcessingInteractor',
                                            'UserOnboardingInteractor',
                                            'WithdrawalApprovalInteractor',
                                            'SurveyInteractionInteractor']},
                    'params':     {'type': 'object'},
                },
                'required': ['interactor'],
            }
        },
        responses={
            200: OpenApiResponse(description="Execution result"),
            400: OpenApiResponse(description="Unknown interactor"),
        },
        tags=['Interactors'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — RepositoryViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def repo_user_lookup_schema():
    return extend_schema(
        summary="User Lookup (Repository)",
        description="Admin: lookup a user via optimised UserRepository (with caching).",
        parameters=[
            OpenApiParameter(name='user_id',  location='query', type=int),
            OpenApiParameter(name='username', location='query', type=str),
        ],
        responses={
            200: OpenApiResponse(description="User data"),
            404: OpenApiResponse(description="User not found"),
        },
        tags=['Repository (Admin)'],
    )


def repo_user_balance_schema():
    return extend_schema(
        summary="User Balance (Repository)",
        description="Admin: user's virtual balance via VirtualBalanceRepository.",
        parameters=[
            OpenApiParameter(name='user_id', location='query', required=True, type=int),
        ],
        responses={200: OpenApiResponse(description="balance, total_earned")},
        tags=['Repository (Admin)'],
    )


def repo_admin_add_coins_schema():
    return extend_schema(
        summary="Add Coins (Admin)",
        description="Admin: credit coins to a user with full audit trail.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_id':     {'type': 'integer'},
                    'amount':      {'type': 'number'},
                    'description': {'type': 'string'},
                },
                'required': ['user_id', 'amount'],
            }
        },
        responses={
            200: OpenApiResponse(description="success, coins_added"),
            403: OpenApiResponse(description="Superuser access required"),
        },
        tags=['Repository (Admin)'],
    )


def repo_lead_exists_schema():
    return extend_schema(
        summary="Lead ID Deduplication Check",
        description="Check if a CPAlead lead_id has already been processed.",
        parameters=[
            OpenApiParameter(name='lead_id', location='query', required=True, type=str),
        ],
        responses={200: OpenApiResponse(description="lead_id, already_processed")},
        tags=['Repository (Admin)'],
    )


def repo_click_ip_count_schema():
    return extend_schema(
        summary="Click IP Count (Fraud Detection)",
        description="Number of clicks from a given IP in the last N hours.",
        parameters=[
            OpenApiParameter(name='ip',    location='query', required=True, type=str),
            OpenApiParameter(name='hours', location='query', type=int, default=1),
        ],
        responses={200: OpenApiResponse(description="click_count, suspicious flag")},
        tags=['Repository (Admin)'],
    )


def repo_health_schema():
    return extend_schema(
        summary="Repository Layer Health",
        description="Admin: health status of all registered repositories.",
        responses={200: OpenApiResponse(description="status, repositories dict, healthy count")},
        tags=['Repository (Admin)'],
    )


# ─────────────────────────────────────────────────────────────────────────────
# NEW v11 — AdapterStatusViewSet Schemas
# ─────────────────────────────────────────────────────────────────────────────

def adapter_status_schema():
    return extend_schema(
        summary="All Adapter Status",
        description=(
            "Admin: health status of all 12 adapter modules "
            "(payment, notifications, analytics, fraud, offerwall, etc.)."
        ),
        responses={
            200: OpenApiResponse(
                description="overall status, summary counts, per-adapter detail"
            ),
        },
        tags=['Adapters (Admin)'],
    )


def adapter_detail_schema():
    return extend_schema(
        summary="Single Adapter Status",
        description="Admin: detailed status for one named adapter.",
        parameters=[
            OpenApiParameter(name='adapter_name', location='path', type=str,
                             enum=['ad_offerwall', 'analytics', 'fraud_security',
                                   'gamification', 'notifications', 'offer_systems',
                                   'payment_tenants', 'platform', 'platform_extras',
                                   'support_ratelimit', 'user_wallet']),
        ],
        responses={
            200: OpenApiResponse(description="adapter status and details"),
            404: OpenApiResponse(description="Unknown adapter name"),
        },
        tags=['Adapters (Admin)'],
    )


def adapter_test_payment_schema():
    return extend_schema(
        summary="Test Payment Gateway",
        description="Admin: ping a payment gateway in sandbox mode (no real charge).",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'gateway': {'type': 'string',
                                'enum': ['paypal', 'bkash', 'nagad', 'stripe']},
                },
                'required': ['gateway'],
            }
        },
        responses={200: OpenApiResponse(description="reachable, gateway, details")},
        tags=['Adapters (Admin)'],
    )


def adapter_config_schema():
    return extend_schema(
        summary="Adapter Configuration",
        description=(
            "Admin: view sanitised adapter configuration "
            "(no API keys/passwords; shows sandbox vs production mode)."
        ),
        responses={200: OpenApiResponse(description="Sanitised config object")},
        tags=['Adapters (Admin)'],
    )


def adapter_reload_schema():
    return extend_schema(
        summary="Reload Adapters",
        description=(
            "Admin (superuser): force adapter re-initialisation. "
            "Use after changing API keys or gateway mode."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'adapter': {'type': 'string',
                                'description': "Adapter name or 'all'",
                                'default': 'all'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description="reloaded list, failed list, success"),
            403: OpenApiResponse(description="Superuser access required"),
        },
        tags=['Adapters (Admin)'],
    )


def adapter_rate_limiter_stats_schema():
    return extend_schema(
        summary="Rate Limiter Stats",
        description="Admin: current rate limiter stats (active throttles, flagged IPs).",
        responses={200: OpenApiResponse(description="Rate limiter stats object")},
        tags=['Adapters (Admin)'],
    )


def adapter_clear_rate_limit_schema():
    return extend_schema(
        summary="Clear Rate Limit",
        description="Admin: manually clear rate limit for an IP address or user ID.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'ip':      {'type': 'string', 'description': 'IP address to clear'},
                    'user_id': {'type': 'integer', 'description': 'User ID to clear'},
                },
            }
        },
        responses={
            200: OpenApiResponse(description="success flag"),
            400: OpenApiResponse(description="ip or user_id required"),
        },
        tags=['Adapters (Admin)'],
    )
