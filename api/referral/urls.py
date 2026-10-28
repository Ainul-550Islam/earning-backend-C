# api/referral/urls.py
# Complete URL configuration — পুরনো সব routes + নতুন সব routes
# ============================================================

from django.urls import path

# ── Old views (backward compat) ───────────────────────────────────────────────
from .views import (
    ReferralStatsView, MyReferralsView, ReferralEarningsView,
    ReferralLeaderboardView, get_referral_stats,
    admin_referral_overview, admin_referrals_list, admin_delete_referral,
    admin_referral_settings, admin_recent_earnings, admin_delete_earning,
    admin_stats_by_date, admin_create_referral, admin_give_bonus,
    admin_adjust_commission, admin_toggle_program, admin_search_users,
)

# ── New viewsets ──────────────────────────────────────────────────────────────
from .viewsets.ReferralSettingsViewSet import ReferralSettingsViewSet
from .viewsets.ReferralCodeViewSet import (
    ReferralCodeViewSet, ReferralCodeDetailView,
    track_code_click, validate_code,
)
from .viewsets.ReferralTreeViewSet import (
    ReferralTreeViewSet, ReferralDownlineView,
    ReferralUplineView, TreeEarningsByLevelView,
)
from .viewsets.CommissionLogViewSet import (
    CommissionLogViewSet, CommissionPendingView,
    CommissionSummaryView, AdminCommissionReleaseView, AdminBulkReleaseView,
)
from .viewsets.CommissionPayoutViewSet import (
    CommissionPayoutViewSet, AdminPayoutProcessView, AdminPayoutListView,
)
from .viewsets.ReferralCampaignViewSet import (
    ReferralCampaignViewSet, CampaignDetailView, CampaignActivateView,
)
from .viewsets.ReferralContestViewSet import (
    ReferralContestViewSet, ContestLeaderboardView,
    ContestMyRankView, AdminContestFinalizeView,
    AdminContestLeaderboardUpdateView,
)
from .viewsets.ReferralFraudViewSet import (
    ReferralFraudViewSet, FraudReviewView, FraudScanView,
    BlacklistViewSet, BlacklistDetailView,
)
from .viewsets.TopReferrerViewSet import TopReferrerViewSet
from .viewsets.ReferralInsightViewSet import (
    ReferralInsightViewSet, InsightChartView,
    InsightTodayView, InsightRecalcView, InsightDateRangeView,
)
from .viewsets.ReferralLTVViewSet import (
    ReferralLTVViewSet, LTVChurnRiskView,
    LTVUserDetailView, AdminLTVOverviewView, AdminLTVRecalcView,
)
from .viewsets.AdminReferralViewSet import (
    AdminReferralViewSet, AdminBulkTreeRecalcView, AdminBulkSnapshotView,
    AdminClawbackListView, AdminClawbackActionView,
    AdminProcessAllClawbacksView, AdminMilestoneProgressView,
    AdminExportReferralsView, AdminExportEarningsView,
    AdminExportFraudView, AdminExportTopReferrersView, MyExportLTVView,
)


# ── Webhooks ──────────────────────────────────────────────────────────────────
from .INTEGRATION_SYSTEM.health_check import health_check_view
from .INTEGRATION_SYSTEM.webhooks_integration import get_webhook_urlpatterns

from .webhooks import (
    OfferCompletionWebhook,
    TaskCompletionWebhook,
    WithdrawalWebhook,
    SignupWebhook,
)
from .views import referral_redirect, referral_redirect_with_signup

urlpatterns = [

    # ══════════════════════════════════════════════════════════
    # USER — Stats & Dashboard
    # ══════════════════════════════════════════════════════════
    path('', ReferralStatsView.as_view(), name='referral-stats'),
    path('stats/', ReferralStatsView.as_view(), name='referral-stats-alt'),
    path('my-referrals/', MyReferralsView.as_view(), name='my-referrals'),
    path('earnings/', ReferralEarningsView.as_view(), name='referral-earnings-user'),
    path('leaderboard/', ReferralLeaderboardView.as_view(), name='referral-leaderboard'),

    # ══════════════════════════════════════════════════════════
    # USER — Referral Codes
    # ══════════════════════════════════════════════════════════
    path('codes/', ReferralCodeViewSet.as_view(), name='referral-codes-list'),
    path('codes/<int:code_id>/', ReferralCodeDetailView.as_view(), name='referral-code-detail'),
    path('codes/click/<str:code_value>/', track_code_click, name='referral-code-click'),
    path('codes/validate/<str:code_value>/', validate_code, name='referral-code-validate'),

    # ══════════════════════════════════════════════════════════
    # USER — Referral Tree
    # ══════════════════════════════════════════════════════════
    path('tree/', ReferralTreeViewSet.as_view(), name='referral-tree'),
    path('tree/downline/', ReferralDownlineView.as_view(), name='referral-downline'),
    path('tree/upline/', ReferralUplineView.as_view(), name='referral-upline'),
    path('tree/earnings-by-level/', TreeEarningsByLevelView.as_view(), name='referral-tree-earnings'),

    # ══════════════════════════════════════════════════════════
    # USER — Commissions
    # ══════════════════════════════════════════════════════════
    path('commissions/', CommissionLogViewSet.as_view(), name='commission-logs'),
    path('commissions/pending/', CommissionPendingView.as_view(), name='commission-pending'),
    path('commissions/summary/', CommissionSummaryView.as_view(), name='commission-summary'),

    # ══════════════════════════════════════════════════════════
    # USER — Payouts
    # ══════════════════════════════════════════════════════════
    path('payouts/', CommissionPayoutViewSet.as_view(), name='payout-list'),

    # ══════════════════════════════════════════════════════════
    # PUBLIC — Campaigns & Contests
    # ══════════════════════════════════════════════════════════
    path('campaigns/', ReferralCampaignViewSet.as_view(), name='campaigns-list'),
    path('campaigns/<int:campaign_id>/', CampaignDetailView.as_view(), name='campaign-detail'),
    path('contests/', ReferralContestViewSet.as_view(), name='contests-list'),
    path('contests/<int:contest_id>/leaderboard/', ContestLeaderboardView.as_view(), name='contest-leaderboard'),
    path('contests/<int:contest_id>/my-rank/', ContestMyRankView.as_view(), name='contest-my-rank'),
    path('top-referrers/', TopReferrerViewSet.as_view(), name='top-referrers'),

    # ══════════════════════════════════════════════════════════
    # USER — LTV & Export
    # ══════════════════════════════════════════════════════════
    path('ltv/', ReferralLTVViewSet.as_view(), name='ltv-report'),
    path('ltv/churn-risk/', LTVChurnRiskView.as_view(), name='ltv-churn-risk'),
    path('ltv/<str:username>/', LTVUserDetailView.as_view(), name='ltv-user-detail'),
    path('export/ltv/', MyExportLTVView.as_view(), name='export-ltv'),

    # ══════════════════════════════════════════════════════════
    # ADMIN — Original backward-compat routes
    # ══════════════════════════════════════════════════════════
    path('referrals/', admin_referrals_list, name='referral-list'),
    path('referrals/<int:referral_id>/', admin_delete_referral, name='referral-detail'),
    path('settings/', admin_referral_settings, name='referral-settings'),
    path('admin/overview/', admin_referral_overview, name='referral-admin-overview'),
    path('admin/stats-by-date/', admin_stats_by_date, name='referral-stats-date'),
    path('admin/list/', admin_referrals_list, name='referral-admin-list'),
    path('admin/create/', admin_create_referral, name='referral-admin-create'),
    path('admin/delete/<int:referral_id>/', admin_delete_referral, name='referral-admin-delete'),
    path('admin/give-bonus/<int:referral_id>/', admin_give_bonus, name='referral-give-bonus'),
    path('admin/adjust-commission/<int:referral_id>/', admin_adjust_commission, name='referral-adjust-commission'),
    path('admin/earnings/', admin_recent_earnings, name='referral-admin-earnings'),
    path('admin/earnings/delete/<int:earning_id>/', admin_delete_earning, name='referral-earning-delete'),
    path('admin/settings/', admin_referral_settings, name='referral-admin-settings'),
    path('admin/toggle-program/', admin_toggle_program, name='referral-toggle-program'),
    path('admin/search-users/', admin_search_users, name='referral-search-users'),

    # ══════════════════════════════════════════════════════════
    # ADMIN — New routes
    # ══════════════════════════════════════════════════════════
    path('admin/settings/v2/', ReferralSettingsViewSet.as_view(), name='referral-settings-v2'),
    path('admin/bulk/stats/', AdminReferralViewSet.as_view(), name='admin-bulk-stats'),
    path('admin/bulk/recalc-trees/', AdminBulkTreeRecalcView.as_view(), name='admin-recalc-trees'),
    path('admin/bulk/snapshots/', AdminBulkSnapshotView.as_view(), name='admin-bulk-snapshots'),
    path('admin/commissions/<int:commission_id>/release/', AdminCommissionReleaseView.as_view(), name='admin-commission-release'),
    path('admin/commissions/bulk-release/', AdminBulkReleaseView.as_view(), name='admin-bulk-release'),
    path('admin/payouts/', AdminPayoutListView.as_view(), name='admin-payout-list'),
    path('admin/payouts/<int:payout_id>/process/', AdminPayoutProcessView.as_view(), name='admin-payout-process'),
    path('admin/campaigns/<int:campaign_id>/activate/', CampaignActivateView.as_view(), name='admin-campaign-activate'),
    path('admin/campaigns/<int:campaign_id>/end/', CampaignDetailView.as_view(), name='admin-campaign-end'),
    path('admin/contests/<int:contest_id>/finalize/', AdminContestFinalizeView.as_view(), name='admin-contest-finalize'),
    path('admin/contests/<int:contest_id>/update-leaderboard/', AdminContestLeaderboardUpdateView.as_view(), name='admin-contest-leaderboard'),
    path('admin/fraud/', ReferralFraudViewSet.as_view(), name='admin-fraud-list'),
    path('admin/fraud/scan/', FraudScanView.as_view(), name='admin-fraud-scan'),
    path('admin/fraud/<int:sr_id>/<str:action>/', FraudReviewView.as_view(), name='admin-fraud-review'),
    path('admin/blacklist/', BlacklistViewSet.as_view(), name='admin-blacklist'),
    path('admin/blacklist/<int:entry_id>/', BlacklistDetailView.as_view(), name='admin-blacklist-detail'),
    path('admin/insights/', ReferralInsightViewSet.as_view(), name='admin-insights'),
    path('admin/insights/chart/', InsightChartView.as_view(), name='admin-insights-chart'),
    path('admin/insights/today/', InsightTodayView.as_view(), name='admin-insights-today'),
    path('admin/insights/recalc/', InsightRecalcView.as_view(), name='admin-insights-recalc'),
    path('admin/insights/range/', InsightDateRangeView.as_view(), name='admin-insights-range'),
    path('admin/ltv/overview/', AdminLTVOverviewView.as_view(), name='admin-ltv-overview'),
    path('admin/ltv/recalc/', AdminLTVRecalcView.as_view(), name='admin-ltv-recalc'),
    path('admin/clawbacks/', AdminClawbackListView.as_view(), name='admin-clawbacks'),
    path('admin/clawbacks/process-all/', AdminProcessAllClawbacksView.as_view(), name='admin-clawbacks-process-all'),
    path('admin/clawbacks/<int:clawback_id>/<str:action>/', AdminClawbackActionView.as_view(), name='admin-clawback-action'),
    path('admin/milestones/', AdminMilestoneProgressView.as_view(), name='admin-milestones'),
    path('admin/export/referrals/', AdminExportReferralsView.as_view(), name='admin-export-referrals'),
    path('admin/export/earnings/', AdminExportEarningsView.as_view(), name='admin-export-earnings'),
    path('admin/export/fraud/', AdminExportFraudView.as_view(), name='admin-export-fraud'),
    path('admin/export/top-referrers/', AdminExportTopReferrersView.as_view(), name='admin-export-top-referrers'),


    # ══════════════════════════════════════════════════════════
    # REFERRAL REDIRECT (Cookie tracking)
    # ══════════════════════════════════════════════════════════
    path('go/<str:code>/', referral_redirect, name='referral-redirect'),
    path('r/<str:code>/', referral_redirect, name='referral-redirect-short'),

    # ══════════════════════════════════════════════════════════
    # WEBHOOKS (Postback from offer networks)
    # ══════════════════════════════════════════════════════════
    path('webhooks/offer-complete/', OfferCompletionWebhook.as_view(), name='webhook-offer-complete'),
    path('webhooks/task-complete/', TaskCompletionWebhook.as_view(), name='webhook-task-complete'),
    path('webhooks/withdrawal/', WithdrawalWebhook.as_view(), name='webhook-withdrawal'),
    path('webhooks/signup/', SignupWebhook.as_view(), name='webhook-signup'),
    # ── Integration System ────────────────────────────────
    path('health/', health_check_view, name='referral-health'),
]