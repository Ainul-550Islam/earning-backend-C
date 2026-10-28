# api/referral/schemas.py
# DRF Spectacular / OpenAPI schema definitions for referral module
# ============================================================

try:
    from drf_spectacular.utils import (
        extend_schema, extend_schema_view, OpenApiParameter,
        OpenApiResponse, OpenApiExample,
    )
    from drf_spectacular.types import OpenApiTypes

    # ── Schema Decorators ─────────────────────────────────────────────────────

    referral_stats_schema = extend_schema(
        summary='My Referral Stats',
        description='Get referral stats, code, link, and commission breakdown for the logged-in user.',
        tags=['Referral — User'],
        responses={
            200: OpenApiResponse(description='Referral stats'),
            401: OpenApiResponse(description='Unauthorized'),
        },
    )

    referral_code_schema = extend_schema(
        summary='My Referral Codes',
        description='Get all referral codes for the logged-in user.',
        tags=['Referral — User'],
        parameters=[
            OpenApiParameter('active_only', OpenApiTypes.BOOL, default=True),
        ],
    )

    leaderboard_schema = extend_schema(
        summary='Referral Leaderboard',
        description='Top referrers. Optionally filter by period.',
        tags=['Referral — Public'],
        parameters=[
            OpenApiParameter(
                'period', OpenApiTypes.STR,
                enum=['daily', 'weekly', 'monthly', 'alltime'],
                default='weekly',
            ),
            OpenApiParameter('limit', OpenApiTypes.INT, default=10),
        ],
    )

    commission_log_schema = extend_schema(
        summary='Commission History',
        description='Paginated list of referral commissions earned.',
        tags=['Referral — Commission'],
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR,
                enum=['pending', 'held', 'released', 'clawed_back']),
            OpenApiParameter('level', OpenApiTypes.INT, enum=[1, 2, 3]),
            OpenApiParameter('from_date', OpenApiTypes.DATE),
            OpenApiParameter('to_date', OpenApiTypes.DATE),
        ],
    )

    fraud_review_schema = extend_schema(
        summary='Fraud Review Queue',
        description='List suspicious referrals pending review. Admin only.',
        tags=['Referral — Admin'],
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR,
                enum=['pending', 'reviewing', 'cleared', 'fraud']),
            OpenApiParameter('min_score', OpenApiTypes.INT, default=30),
        ],
    )

    health_check_schema = extend_schema(
        summary='Referral System Health',
        description='Health check — returns status of all subsystems.',
        tags=['Referral — System'],
        responses={
            200: OpenApiResponse(description='All systems OK'),
            207: OpenApiResponse(description='Some warnings'),
            503: OpenApiResponse(description='Critical failure'),
        },
    )

    SPECTACULAR_AVAILABLE = True

except ImportError:
    # drf-spectacular not installed — use no-op decorators
    def referral_stats_schema(func): return func
    def referral_code_schema(func): return func
    def leaderboard_schema(func): return func
    def commission_log_schema(func): return func
    def fraud_review_schema(func): return func
    def health_check_schema(func): return func
    SPECTACULAR_AVAILABLE = False


# ── DRF CoreAPI Schema (fallback) ─────────────────────────────────────────────

class ReferralSchemaFields:
    """
    Manual schema field descriptions for DRF coreapi.
    Used when drf-spectacular is not installed.
    """
    REFERRAL_STATS = {
        'referral_code': 'Unique referral code (e.g. EARN1A2B3C4D)',
        'referral_link': 'Full URL with referral code',
        'total_referrals': 'Total users referred',
        'active_referrals': 'Currently active referred users',
        'level1_count': 'Direct referrals (L1)',
        'level2_count': 'Second-level referrals (L2)',
        'level3_count': 'Third-level referrals (L3)',
        'total_commission': 'Total commission earned (all time)',
        'this_month_commission': 'Commission earned this month',
        'pending_commission': 'Commission currently on hold',
    }

    COMMISSION_LOG = {
        'id': 'Commission log ID',
        'amount': 'Commission amount in local currency',
        'level': 'Commission level (1, 2, or 3)',
        'status': 'pending / held / released / clawed_back',
        'referred_user': 'Username of referred user',
        'source_type': 'task / offer / withdrawal / signup',
        'created_at': 'ISO 8601 timestamp',
    }

    LEADERBOARD_ENTRY = {
        'rank': 'Current leaderboard position',
        'username': 'Referrer username',
        'referral_count': 'Number of referrals in period',
        'commission_earned': 'Total commission in period',
        'rank_change': 'Change from previous period (+/- integer)',
    }