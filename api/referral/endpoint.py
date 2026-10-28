# api/referral/endpoint.py
# Consolidated API endpoint definitions — all referral endpoints in one place
# Use this as reference for frontend integration
# ============================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# ── Router-based endpoints (ViewSets) ─────────────────────────────────────────

router = DefaultRouter()

def get_router():
    """Return configured DRF router with all referral ViewSets registered."""
    from api.referral.viewsets.ReferralCodeViewSet import ReferralCodeViewSet
    from api.referral.viewsets.CommissionLogViewSet import CommissionLogViewSet
    from api.referral.viewsets.CommissionPayoutViewSet import CommissionPayoutViewSet
    from api.referral.viewsets.ReferralCampaignViewSet import ReferralCampaignViewSet
    from api.referral.viewsets.ReferralContestViewSet import ReferralContestViewSet
    from api.referral.viewsets.ReferralFraudViewSet import ReferralFraudViewSet
    from api.referral.viewsets.TopReferrerViewSet import TopReferrerViewSet
    from api.referral.viewsets.ReferralInsightViewSet import ReferralInsightViewSet
    from api.referral.viewsets.ReferralLTVViewSet import ReferralLTVViewSet
    from api.referral.viewsets.ReferralSettingsViewSet import ReferralSettingsViewSet
    from api.referral.viewsets.ReferralTreeViewSet import ReferralTreeViewSet
    from api.referral.viewsets.AdminReferralViewSet import AdminReferralViewSet

    r = DefaultRouter()
    r.register(r'codes',           ReferralCodeViewSet,     basename='referral-code')
    r.register(r'commissions',     CommissionLogViewSet,    basename='commission-log')
    r.register(r'payouts',         CommissionPayoutViewSet, basename='commission-payout')
    r.register(r'campaigns',       ReferralCampaignViewSet, basename='referral-campaign')
    r.register(r'contests',        ReferralContestViewSet,  basename='referral-contest')
    r.register(r'fraud',           ReferralFraudViewSet,    basename='referral-fraud')
    r.register(r'top-referrers',   TopReferrerViewSet,      basename='top-referrer')
    r.register(r'insights',        ReferralInsightViewSet,  basename='referral-insight')
    r.register(r'ltv',             ReferralLTVViewSet,      basename='referral-ltv')
    r.register(r'settings',        ReferralSettingsViewSet, basename='referral-settings')
    r.register(r'tree',            ReferralTreeViewSet,     basename='referral-tree')
    r.register(r'admin',           AdminReferralViewSet,    basename='referral-admin')
    return r


# ── Endpoint Reference Table ──────────────────────────────────────────────────
# Complete list for frontend developers

ENDPOINTS = {
    # ── User Endpoints ──────────────────────────────────────────────
    'GET  /referral/':                    'My referral stats + code + link',
    'GET  /referral/stats/':              'Detailed referral stats (L1/L2/L3)',
    'GET  /referral/my-referrals/':       'List of referred users',
    'GET  /referral/earnings/':           'Referral earning history',
    'GET  /referral/leaderboard/':        'Top referrers leaderboard',
    'GET  /referral/codes/':              'My referral codes list',
    'POST /referral/codes/':              'Create custom referral code',
    'GET  /referral/tree/':               'My referral network tree',

    # ── Sharing ──────────────────────────────────────────────────────
    'GET  /referral/share/':              'Social share URLs for all platforms',
    'POST /referral/share/':              'Record a share action (WhatsApp, etc.)',
    'GET  /referral/qr/':                 'Get QR code for referral link',
    'POST /referral/qr/':                 'Regenerate QR with custom colors',

    # ── Invitations ───────────────────────────────────────────────────
    'POST /referral/invite/email/':       'Send email invitation',
    'POST /referral/invite/bulk/':        'Bulk send email invitations',

    # ── World-class Features ─────────────────────────────────────────
    'GET  /referral/streak/':             'Current referral streak info',
    'GET  /referral/tier/':               'Commission tier & effective rates',
    'GET  /referral/credits/':            'Referral credit balance',
    'GET  /referral/viral-stats/':        'K-factor & viral coefficient (admin)',
    'GET  /referral/affiliate/':          'Affiliate profile',
    'POST /referral/affiliate/':          'Register as affiliate',

    # ── Public ────────────────────────────────────────────────────────
    'GET  /referral/go/<code>/':          'Referral link redirect (sets cookie)',
    'GET  /referral/campaigns/':          'Active referral campaigns list',
    'GET  /referral/contests/':           'Active/upcoming contests',

    # ── Admin ─────────────────────────────────────────────────────────
    'GET  /referral/admin/':              'Admin dashboard overview',
    'GET  /referral/admin/fraud/':        'Fraud review queue',
    'POST /referral/admin/fraud/clear/':  'Clear fraud flag',
    'POST /referral/admin/fraud/confirm/':'Confirm fraud + trigger clawback',
    'GET  /referral/admin/export/':       'Export referral data (CSV)',
    'GET  /referral/admin/insights/':     'Analytics insights dashboard',
    'POST /referral/admin/blacklist/':    'Add to blacklist',

    # ── Settings ──────────────────────────────────────────────────────
    'GET  /referral/settings/':           'Get referral settings',
    'PUT  /referral/settings/<id>/':      'Update referral settings (admin)',

    # ── Webhooks ──────────────────────────────────────────────────────
    'POST /referral/webhooks/offer-complete/': 'Offer completion postback',
    'POST /referral/webhooks/task-complete/':  'Task completion postback',
    'POST /referral/webhooks/signup/':         'Signup postback',
    'POST /referral/webhooks/offerwall/':      'CPAlead/offerwall postback',

    # ── Health ────────────────────────────────────────────────────────
    'GET  /referral/health/':             'System health check',

    # ── WebSocket ────────────────────────────────────────────────────
    'WS   ws/referral/leaderboard/':      'Real-time leaderboard updates',
    'WS   ws/referral/stats/':            'Real-time personal stats updates',
}


def get_endpoint_docs() -> list:
    """Return endpoint list as dicts for schema generation."""
    docs = []
    for path_str, description in ENDPOINTS.items():
        parts = path_str.strip().split()
        docs.append({
            'method': parts[0],
            'path': parts[1],
            'description': description,
        })
    return docs