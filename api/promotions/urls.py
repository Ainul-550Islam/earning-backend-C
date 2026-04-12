# =============================================================================
# api/promotions/urls.py
# =============================================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    PromotionCategoryViewSet, PlatformViewSet,
    RewardPolicyViewSet, CurrencyRateViewSet,
    CampaignViewSet,
    TaskSubmissionViewSet, DisputeViewSet,
    PromotionTransactionViewSet, EscrowWalletViewSet,
    ReferralCommissionLogViewSet,
    BlacklistViewSet, FraudReportViewSet,
    DeviceFingerprintViewSet, UserReputationViewSet,
    CampaignAnalyticsViewSet,
)

app_name = 'promotions'

router = DefaultRouter()
router.register(r'categories',           PromotionCategoryViewSet,      basename='category')
router.register(r'platforms',            PlatformViewSet,               basename='platform')
router.register(r'reward-policies',      RewardPolicyViewSet,           basename='reward-policy')
router.register(r'currency-rates',       CurrencyRateViewSet,           basename='currency-rate')
router.register(r'campaigns',            CampaignViewSet,               basename='campaign')
router.register(r'submissions',          TaskSubmissionViewSet,         basename='submission')
router.register(r'disputes',             DisputeViewSet,                basename='dispute')
router.register(r'transactions',         PromotionTransactionViewSet,   basename='transaction')
router.register(r'escrow',               EscrowWalletViewSet,           basename='escrow')
router.register(r'referral-commissions', ReferralCommissionLogViewSet,  basename='referral-commission')
router.register(r'blacklist',            BlacklistViewSet,              basename='blacklist')
router.register(r'fraud-reports',        FraudReportViewSet,            basename='fraud-report')
router.register(r'device-fingerprints',  DeviceFingerprintViewSet,      basename='device-fingerprint')
router.register(r'reputation',           UserReputationViewSet,         basename='reputation')
router.register(r'analytics',            CampaignAnalyticsViewSet,      basename='analytics')

urlpatterns = [
    # ── Standalone views (must be before router) ──────────────────────────────
    path('user-offers/',                views.user_offers,                   name='user-offers'),
    path('bidding/',                    views.bidding_list,                  name='bidding-list'),
    path('bidding/<int:pk>/resolve/',   views.bidding_resolve,               name='bidding-resolve'),
    path('quick-create/',               views.campaign_quick_create,         name='campaign-quick-create'),
    path('quick-update/<int:pk>/',      views.campaign_quick_update,         name='campaign-quick-update'),
    path('quick-delete/<int:pk>/',      views.campaign_quick_delete,         name='campaign-quick-delete'),
    path('analytics/overall/',          views.promotions_analytics_overall,  name='analytics-overall'),
    path('stats/',                      views.promotions_stats,              name='promotions-stats'),
    path('<int:pk>/sparkline/',          views.promotions_sparkline,          name='promotions-sparkline'),

    # ── Frontend shortcut aliases (/promotions/ → /promotions/campaigns/) ────
    # Frontend calls GET /api/promotions/ for list
    # We alias it to campaign list + quick create/update/delete
    path('',                            views.promotions_list_alias,         name='promotions-list'),
    path('<int:pk>/',                   views.promotions_detail_alias,       name='promotions-detail'),
    path('<int:pk>/pause/',             views.promotions_pause_alias,        name='promotions-pause'),
    path('<int:pk>/resume/',            views.promotions_resume_alias,       name='promotions-resume'),
    path('<int:pk>/archive/',           views.promotions_archive_alias,      name='promotions-archive'),

    # ── Router URLs ───────────────────────────────────────────────────────────
    path('', include(router.urls)),
]

# =============================================================================
# FULL URL REFERENCE:
# GET/POST   /api/promotions/                    ← alias for campaigns list/create
# GET        /api/promotions/:id/                ← campaign detail
# POST       /api/promotions/:id/pause/          ← pause
# POST       /api/promotions/:id/resume/         ← resume
# POST       /api/promotions/:id/archive/        ← archive
# GET        /api/promotions/stats/              ← dashboard stats
# GET        /api/promotions/:id/sparkline/      ← chart data
# GET/POST   /api/promotions/campaigns/          ← full campaign CRUD
# POST       /api/promotions/campaigns/:id/approve/
# POST       /api/promotions/campaigns/:id/duplicate/
# POST       /api/promotions/campaigns/:id/budget_top_up/
# GET/POST   /api/promotions/submissions/
# POST       /api/promotions/submissions/:id/approve/
# POST       /api/promotions/submissions/:id/reject/
# GET/POST   /api/promotions/disputes/
# POST       /api/promotions/disputes/:id/resolve/
# GET        /api/promotions/transactions/
# GET        /api/promotions/analytics/?campaign=1
# =============================================================================

# =============================================================================
# NEW URLs — Added for World #1 Platform
# =============================================================================

# ── Content Locking (CPAlead signature) ──────────────────────────────────────
from api.promotions.content_locking.link_locker import (
    create_locked_link, check_lock_status, record_unlock
)
from api.promotions.content_locking.file_locker import (
    create_file_lock_view, get_download_token_view, consume_download_view
)
from api.promotions.content_locking.content_locker import (
    create_content_locker_view, unlock_content_view,
    check_content_unlocked_view, get_locker_offers_view
)

# ── Publisher Portal ──────────────────────────────────────────────────────────
from api.promotions.publisher.dashboard import (
    publisher_dashboard_view, publisher_campaign_breakdown_view,
    publisher_earnings_chart_view
)
from api.promotions.publisher.earnings import (
    publisher_balance_view, request_payout_view, payout_history_view
)
from api.promotions.publisher.approval_flow import (
    apply_publisher_view, publisher_status_view, admin_approve_publisher_view
)
from api.promotions.publisher.publisher_stats import (
    publisher_epc_view, publisher_referral_stats_view
)

# ── Advertiser Portal ─────────────────────────────────────────────────────────
from api.promotions.advertiser.campaign_wizard import (
    wizard_start_view, wizard_step_view, wizard_submit_view, wizard_state_view
)
from api.promotions.advertiser.advertiser_reporting import (
    advertiser_dashboard_view, campaign_roi_view, publisher_performance_view
)
from api.promotions.advertiser.budget_manager import (
    campaign_budget_status_view, campaign_topup_view
)

# ── Leaderboard ──────────────────────────────────────────────────────────────
from api.promotions.leaderboard.publisher_leaderboard import (
    publisher_leaderboard_view, my_rank_view
)
from api.promotions.leaderboard.advertiser_leaderboard import advertiser_leaderboard_view

# ── Account Manager ───────────────────────────────────────────────────────────
from api.promotions.account_manager.am_assignment import my_tier_view, assign_am_view
from api.promotions.account_manager.am_communication import (
    create_ticket_view, my_tickets_view, reply_ticket_view
)

# ── Performance Bonus ─────────────────────────────────────────────────────────
from api.promotions.performance_bonus.milestone_bonus import (
    milestone_progress_view, check_milestones_view
)
from api.promotions.performance_bonus.tier_rewards import bonus_summary_view

# ── SmartLink ─────────────────────────────────────────────────────────────────
from api.promotions.smartlink.smartlink_router import (
    smartlink_redirect_view, create_smartlink_view
)

# ── Offerwall ────────────────────────────────────────────────────────────────
from api.promotions.offerwall.offerwall_backend import (
    offerwall_offers_view, offerwall_categories_view
)

# ── Pay Per Call ─────────────────────────────────────────────────────────────
from api.promotions.pay_per_call.call_tracking import (
    create_tracking_number_view, call_webhook_view
)

# ── Crypto Payments ──────────────────────────────────────────────────────────
from api.promotions.crypto_payments.usdt_payment import USDTPaymentProcessor

# ── Virtual Currency ─────────────────────────────────────────────────────────
from api.promotions.virtual_currency.vc_manager import (
    create_vc_config_view, get_vc_config_view, offerwall_with_vc_view
)

# ── CPC Offers ───────────────────────────────────────────────────────────────
from api.promotions.cpc_offers.cpc_manager import (
    cpc_click_view, cpc_campaigns_view, cpc_stats_view
)

# ── CPI Offers ───────────────────────────────────────────────────────────────
from api.promotions.cpi_offers.cpi_manager import (
    cpi_postback_view, create_cpi_campaign_view, cpi_offers_view
)

# ── Quiz/Survey ──────────────────────────────────────────────────────────────
from api.promotions.quiz_survey.quiz_manager import (
    get_quiz_view, start_quiz_session_view, submit_answer_view,
    complete_quiz_view, create_quiz_campaign_view
)

# ── SubID Tracking ───────────────────────────────────────────────────────────
from api.promotions.subid_tracking.subid_manager import (
    subid_report_view, generate_subid_url_view
)

# ── Publisher API ─────────────────────────────────────────────────────────────
from api.promotions.publisher_api.offer_api import (
    publisher_api_offers_view, generate_api_key_view
)

# ── First Payout Bonus ────────────────────────────────────────────────────────
from api.promotions.first_payout_bonus.bonus_system import (
    bonus_eligibility_view, claim_welcome_bonus_view
)

# ── Traffic Quality ──────────────────────────────────────────────────────────
from api.promotions.traffic_quality.quality_scorer import (
    my_quality_score_view, publisher_quality_score_view
)

NEW_URLPATTERNS = [
    # Content Locking
    path('locker/link/create/',                     create_locked_link,                  name='locker-link-create'),
    path('locker/link/<str:lock_token>/status/',    check_lock_status,                   name='locker-link-status'),
    path('locker/link/<str:lock_token>/unlock/',    record_unlock,                       name='locker-link-unlock'),
    path('locker/file/create/',                     create_file_lock_view,               name='locker-file-create'),
    path('locker/file/<str:lock_id>/token/',        get_download_token_view,             name='locker-file-token'),
    path('locker/download/<str:token>/',            consume_download_view,               name='locker-download'),
    path('locker/content/create/',                  create_content_locker_view,          name='locker-content-create'),
    path('locker/content/<str:lock_id>/unlock/',    unlock_content_view,                 name='locker-content-unlock'),
    path('locker/content/<str:lock_id>/check/',     check_content_unlocked_view,         name='locker-content-check'),
    path('locker/content/<str:lock_id>/offers/',    get_locker_offers_view,              name='locker-content-offers'),

    # Publisher Portal
    path('publisher/dashboard/',                    publisher_dashboard_view,            name='publisher-dashboard'),
    path('publisher/campaigns/',                    publisher_campaign_breakdown_view,   name='publisher-campaigns'),
    path('publisher/earnings/chart/',               publisher_earnings_chart_view,       name='publisher-earnings-chart'),
    path('publisher/balance/',                      publisher_balance_view,              name='publisher-balance'),
    path('publisher/payout/request/',               request_payout_view,                 name='publisher-payout-request'),
    path('publisher/payout/history/',               payout_history_view,                 name='publisher-payout-history'),
    path('publisher/apply/',                        apply_publisher_view,                name='publisher-apply'),
    path('publisher/status/',                       publisher_status_view,               name='publisher-status'),
    path('publisher/<int:publisher_id>/approve/',   admin_approve_publisher_view,        name='publisher-approve'),
    path('publisher/epc/',                          publisher_epc_view,                  name='publisher-epc'),
    path('publisher/referrals/',                    publisher_referral_stats_view,       name='publisher-referrals'),

    # Advertiser Portal
    path('advertiser/dashboard/',                   advertiser_dashboard_view,           name='advertiser-dashboard'),
    path('advertiser/campaign/<int:campaign_id>/roi/',    campaign_roi_view,             name='advertiser-roi'),
    path('advertiser/campaign/<int:campaign_id>/publishers/', publisher_performance_view, name='advertiser-publishers'),
    path('advertiser/campaign/<int:campaign_id>/budget/',  campaign_budget_status_view,  name='campaign-budget'),
    path('advertiser/campaign/<int:campaign_id>/topup/',   campaign_topup_view,          name='campaign-topup'),
    path('advertiser/wizard/start/',                wizard_start_view,                   name='wizard-start'),
    path('advertiser/wizard/step/<int:step>/',      wizard_step_view,                    name='wizard-step'),
    path('advertiser/wizard/submit/',               wizard_submit_view,                  name='wizard-submit'),
    path('advertiser/wizard/state/',                wizard_state_view,                   name='wizard-state'),

    # Leaderboard
    path('leaderboard/publishers/',                 publisher_leaderboard_view,          name='leaderboard-publishers'),
    path('leaderboard/my-rank/',                    my_rank_view,                        name='leaderboard-my-rank'),
    path('leaderboard/advertisers/',                advertiser_leaderboard_view,         name='leaderboard-advertisers'),

    # Account Manager
    path('my/tier/',                                my_tier_view,                        name='my-tier'),
    path('admin/assign-am/<int:publisher_id>/',     assign_am_view,                      name='assign-am'),
    path('support/tickets/',                        my_tickets_view,                     name='my-tickets'),
    path('support/tickets/create/',                 create_ticket_view,                  name='create-ticket'),
    path('support/tickets/<str:ticket_id>/reply/',  reply_ticket_view,                   name='reply-ticket'),

    # Performance Bonus
    path('bonus/milestones/',                       milestone_progress_view,             name='milestone-progress'),
    path('bonus/milestones/check/',                 check_milestones_view,               name='milestone-check'),
    path('bonus/summary/',                          bonus_summary_view,                  name='bonus-summary'),
    path('bonus/eligibility/',                      bonus_eligibility_view,              name='bonus-eligibility'),
    path('bonus/welcome/',                          claim_welcome_bonus_view,            name='claim-welcome'),

    # SmartLink
    path('smartlink/create/',                       create_smartlink_view,               name='smartlink-create'),
    path('smartlink/<int:publisher_id>/<str:link_hash>/', smartlink_redirect_view,       name='smartlink-go'),

    # Offerwall
    path('offerwall/',                              offerwall_offers_view,               name='offerwall-offers'),
    path('offerwall/categories/',                   offerwall_categories_view,           name='offerwall-categories'),
    path('offerwall/vc/',                           offerwall_with_vc_view,              name='offerwall-vc'),

    # Virtual Currency
    path('virtual-currency/config/',                create_vc_config_view,               name='vc-config-create'),
    path('virtual-currency/my-config/',             get_vc_config_view,                  name='vc-config-get'),

    # CPC
    path('cpc/click/<int:campaign_id>/',            cpc_click_view,                      name='cpc-click'),
    path('cpc/campaigns/',                          cpc_campaigns_view,                  name='cpc-campaigns'),
    path('cpc/stats/',                              cpc_stats_view,                      name='cpc-stats'),

    # CPI
    path('cpi/offers/',                             cpi_offers_view,                     name='cpi-offers'),
    path('cpi/campaign/create/',                    create_cpi_campaign_view,            name='cpi-campaign-create'),
    path('cpi/postback/<str:mmp_provider>/<str:campaign_id>/', cpi_postback_view,        name='cpi-postback'),

    # Quiz/Survey
    path('quiz/create/',                            create_quiz_campaign_view,           name='quiz-create'),
    path('quiz/<str:quiz_id>/',                     get_quiz_view,                       name='quiz-get'),
    path('quiz/<str:quiz_id>/start/',               start_quiz_session_view,             name='quiz-start'),
    path('quiz/session/<str:session_id>/answer/',   submit_answer_view,                  name='quiz-answer'),
    path('quiz/session/<str:session_id>/complete/', complete_quiz_view,                  name='quiz-complete'),

    # SubID Tracking
    path('subid/report/',                           subid_report_view,                   name='subid-report'),
    path('subid/generate/',                         generate_subid_url_view,             name='subid-generate'),

    # Publisher API
    path('publisher-api/offers/',                   publisher_api_offers_view,           name='pub-api-offers'),
    path('publisher-api/generate-key/',             generate_api_key_view,               name='pub-api-key'),

    # Pay Per Call
    path('ppc/tracking-number/create/',             create_tracking_number_view,         name='ppc-create-number'),
    path('ppc/webhook/',                            call_webhook_view,                   name='ppc-webhook'),

    # Traffic Quality
    path('quality/my-score/',                       my_quality_score_view,               name='my-quality-score'),
    path('quality/publisher/<int:publisher_id>/',   publisher_quality_score_view,        name='publisher-quality'),
]

urlpatterns = urlpatterns + NEW_URLPATTERNS


# =============================================================================
# NEW VIEWSETS — router registration
# =============================================================================
from api.promotions.views import (
    PublisherProfileViewSet, AdvertiserProfileViewSet,
    EmailSubmitCampaignViewSet, CPCCampaignViewSet,
    CPIAppCampaignViewSet, QuizCampaignViewSet,
    SmartLinkConfigViewSet, ContentLockViewSet,
    PayoutBatchViewSet, IPBlacklistViewSet,
    TrackingDomainViewSet, SystemConfigViewSet,
)

router.register(r'publisher-profiles',   PublisherProfileViewSet,   basename='publisher-profile')
router.register(r'advertiser-profiles',  AdvertiserProfileViewSet,  basename='advertiser-profile')
router.register(r'email-submit',         EmailSubmitCampaignViewSet,basename='email-submit')
router.register(r'cpc-campaigns',        CPCCampaignViewSet,        basename='cpc-campaign')
router.register(r'cpi-campaigns',        CPIAppCampaignViewSet,     basename='cpi-campaign')
router.register(r'quiz-campaigns',       QuizCampaignViewSet,       basename='quiz-campaign')
router.register(r'smartlinks-db',        SmartLinkConfigViewSet,    basename='smartlink-db')
router.register(r'content-locks',        ContentLockViewSet,        basename='content-lock')
router.register(r'payouts',              PayoutBatchViewSet,        basename='payout')
router.register(r'ip-blacklist',         IPBlacklistViewSet,        basename='ip-blacklist')
router.register(r'tracking-domains',     TrackingDomainViewSet,     basename='tracking-domain')
router.register(r'system-config',        SystemConfigViewSet,       basename='system-config')

# =============================================================================
# ALL SUB-MODULE URLS — email_submit, cpc, cpi, quiz, vc, white_label etc.
# =============================================================================
from api.promotions.email_submit.email_submit_manager import (
    email_submit_view, doi_confirm_view, create_email_submit_campaign_view,
)
from api.promotions.cpc_offers.cpc_manager import (
    cpc_click_view, cpc_campaigns_view, cpc_stats_view,
)
from api.promotions.cpi_offers.cpi_manager import (
    cpi_postback_view, create_cpi_campaign_view, cpi_offers_view,
)
from api.promotions.quiz_survey.quiz_manager import (
    get_quiz_view, start_quiz_session_view, submit_answer_view,
    complete_quiz_view, create_quiz_campaign_view,
)
from api.promotions.virtual_currency.vc_manager import (
    create_vc_config_view, get_vc_config_view, offerwall_with_vc_view,
)
from api.promotions.white_label.white_label_manager import (
    create_white_label_view, my_white_label_view,
)
from api.promotions.postback_tools.postback_tester import (
    test_postback_view, postback_logs_view,
    postback_template_view, validate_postback_url_view,
)
from api.promotions.postback_tools.postback_debugger import my_postback_log_view
from api.promotions.api_keys.api_key_manager import (
    create_api_key_view, list_api_keys_view, revoke_api_key_view,
)
from api.promotions.webhook_config.webhook_config_manager import (
    set_webhook_view, my_webhooks_view, webhook_events_view,
)
from api.promotions.creative_manager.creative_service import (
    upload_creative_view, campaign_creatives_view, standard_sizes_view,
)
from api.promotions.landing_page.lp_rotator import (
    create_rotator_view, rotator_redirect_view, rotator_stats_view,
)
from api.promotions.first_payout_bonus.bonus_system import (
    bonus_eligibility_view, claim_welcome_bonus_view,
)
from api.promotions.traffic_quality.quality_scorer import (
    my_quality_score_view, publisher_quality_score_view,
)
from api.promotions.pay_per_call.call_tracking import (
    create_tracking_number_view, call_webhook_view,
)
from api.promotions.publisher_api.offer_api import (
    publisher_api_offers_view, generate_api_key_view,
)
from api.promotions.subid_tracking.subid_manager import (
    subid_report_view, generate_subid_url_view,
)
from api.promotions.publisher.dashboard import (
    publisher_dashboard_view, publisher_campaign_breakdown_view,
    publisher_earnings_chart_view,
)
from api.promotions.publisher.earnings import (
    publisher_balance_view, request_payout_view, payout_history_view,
)
from api.promotions.publisher.approval_flow import (
    apply_publisher_view, publisher_status_view, admin_approve_publisher_view,
)
from api.promotions.publisher.publisher_stats import (
    publisher_epc_view, publisher_referral_stats_view,
)
from api.promotions.advertiser.campaign_wizard import (
    wizard_start_view, wizard_step_view, wizard_submit_view, wizard_state_view,
)
from api.promotions.advertiser.advertiser_reporting import (
    advertiser_dashboard_view, campaign_roi_view, publisher_performance_view,
)
from api.promotions.advertiser.budget_manager import (
    campaign_budget_status_view, campaign_topup_view,
)
from api.promotions.leaderboard.publisher_leaderboard import (
    publisher_leaderboard_view, my_rank_view,
)
from api.promotions.leaderboard.advertiser_leaderboard import advertiser_leaderboard_view
from api.promotions.account_manager.am_assignment import my_tier_view, assign_am_view
from api.promotions.account_manager.am_communication import (
    create_ticket_view, my_tickets_view, reply_ticket_view,
)
from api.promotions.performance_bonus.milestone_bonus import (
    milestone_progress_view, check_milestones_view,
)
from api.promotions.performance_bonus.tier_rewards import bonus_summary_view
from api.promotions.smartlink.smartlink_router import (
    smartlink_redirect_view, create_smartlink_view,
)
from api.promotions.offerwall.offerwall_backend import (
    offerwall_offers_view, offerwall_categories_view,
)
from api.promotions.content_locking.link_locker import (
    create_locked_link, check_lock_status, record_unlock,
)
from api.promotions.content_locking.file_locker import (
    create_file_lock_view, get_download_token_view, consume_download_view,
)
from api.promotions.content_locking.content_locker import (
    create_content_locker_view, unlock_content_view,
    check_content_unlocked_view, get_locker_offers_view,
)
from api.promotions.crypto_payments.usdt_payment import USDTPaymentProcessor

ALL_SUB_MODULE_URLS = [
    # Email Submit
    path('email-submit/<str:campaign_id>/submit/',   email_submit_view,                    name='email-submit-process'),
    path('email-submit/confirm/<str:token>/',        doi_confirm_view,                     name='email-doi-confirm'),
    path('email-submit/campaign/create/',            create_email_submit_campaign_view,    name='email-submit-create'),

    # CPC
    path('cpc/click/<int:campaign_id>/',             cpc_click_view,                       name='cpc-click'),
    path('cpc/campaigns/list/',                      cpc_campaigns_view,                   name='cpc-campaigns-list'),
    path('cpc/stats/',                               cpc_stats_view,                       name='cpc-stats'),

    # CPI
    path('cpi/offers/list/',                         cpi_offers_view,                      name='cpi-offers-list'),
    path('cpi/postback/<str:mmp_provider>/<str:campaign_id>/', cpi_postback_view,          name='cpi-postback'),

    # Quiz
    path('quiz/<str:quiz_id>/view/',                 get_quiz_view,                        name='quiz-get'),
    path('quiz/<str:quiz_id>/start/',                start_quiz_session_view,              name='quiz-start'),
    path('quiz/session/<str:session_id>/answer/',    submit_answer_view,                   name='quiz-answer'),
    path('quiz/session/<str:session_id>/complete/',  complete_quiz_view,                   name='quiz-complete'),

    # Virtual Currency
    path('vc/config/',                               create_vc_config_view,                name='vc-config-create'),
    path('vc/my-config/',                            get_vc_config_view,                   name='vc-config-get'),
    path('offerwall/vc/',                            offerwall_with_vc_view,               name='offerwall-vc'),

    # White Label
    path('white-label/create/',                      create_white_label_view,              name='wl-create'),
    path('white-label/my/',                          my_white_label_view,                  name='wl-get'),

    # Postback Tools
    path('postback-tools/test/',                     test_postback_view,                   name='postback-test'),
    path('postback-tools/logs/',                     postback_logs_view,                   name='postback-logs'),
    path('postback-tools/template/',                 postback_template_view,               name='postback-template'),
    path('postback-tools/validate/',                 validate_postback_url_view,           name='postback-validate'),
    path('postback-tools/incoming/',                 my_postback_log_view,                 name='postback-incoming'),

    # API Keys
    path('api-keys/create/',                         create_api_key_view,                  name='api-key-create'),
    path('api-keys/list/',                           list_api_keys_view,                   name='api-key-list'),
    path('api-keys/<str:key_hash>/revoke/',          revoke_api_key_view,                  name='api-key-revoke'),

    # Webhook Config
    path('webhooks/set/',                            set_webhook_view,                     name='webhook-set'),
    path('webhooks/my/',                             my_webhooks_view,                     name='webhook-my'),
    path('webhooks/events/',                         webhook_events_view,                  name='webhook-events'),

    # Creative Manager
    path('creatives/upload/',                        upload_creative_view,                 name='creative-upload'),
    path('creatives/campaign/<int:campaign_id>/',    campaign_creatives_view,              name='creatives-list'),
    path('creatives/sizes/',                         standard_sizes_view,                  name='creative-sizes'),

    # Landing Page Rotator
    path('lp-rotator/create/',                       create_rotator_view,                  name='lp-create'),
    path('lp-rotator/<str:rotator_id>/go/',          rotator_redirect_view,                name='lp-go'),
    path('lp-rotator/<str:rotator_id>/stats/',       rotator_stats_view,                   name='lp-stats'),

    # Publisher Portal
    path('publisher/dashboard/',                     publisher_dashboard_view,             name='publisher-dashboard'),
    path('publisher/campaigns/',                     publisher_campaign_breakdown_view,    name='publisher-campaign-breakdown'),
    path('publisher/earnings/chart/',                publisher_earnings_chart_view,        name='publisher-earnings-chart'),
    path('publisher/balance/',                       publisher_balance_view,               name='publisher-balance'),
    path('publisher/payout/request/',                request_payout_view,                  name='publisher-payout-request'),
    path('publisher/payout/history/',                payout_history_view,                  name='publisher-payout-history'),
    path('publisher/apply/',                         apply_publisher_view,                 name='publisher-apply'),
    path('publisher/status/',                        publisher_status_view,                name='publisher-status'),
    path('publisher/<int:publisher_id>/approve/',    admin_approve_publisher_view,         name='publisher-approve'),
    path('publisher/epc/',                           publisher_epc_view,                   name='publisher-epc'),
    path('publisher/referrals/',                     publisher_referral_stats_view,        name='publisher-referrals'),

    # Advertiser Portal
    path('advertiser/dashboard/',                    advertiser_dashboard_view,            name='advertiser-dashboard'),
    path('advertiser/campaign/<int:campaign_id>/roi/',   campaign_roi_view,                name='advertiser-roi'),
    path('advertiser/campaign/<int:campaign_id>/publishers/', publisher_performance_view,  name='advertiser-publishers'),
    path('advertiser/campaign/<int:campaign_id>/budget/', campaign_budget_status_view,     name='campaign-budget'),
    path('advertiser/campaign/<int:campaign_id>/topup/',  campaign_topup_view,             name='campaign-topup'),
    path('advertiser/wizard/start/',                 wizard_start_view,                    name='wizard-start'),
    path('advertiser/wizard/step/<int:step>/',       wizard_step_view,                     name='wizard-step'),
    path('advertiser/wizard/submit/',                wizard_submit_view,                   name='wizard-submit'),
    path('advertiser/wizard/state/',                 wizard_state_view,                    name='wizard-state'),

    # Leaderboard
    path('leaderboard/publishers/',                  publisher_leaderboard_view,           name='leaderboard-publishers'),
    path('leaderboard/my-rank/',                     my_rank_view,                         name='my-rank'),
    path('leaderboard/advertisers/',                 advertiser_leaderboard_view,          name='leaderboard-advertisers'),

    # Account Manager
    path('my/tier/',                                 my_tier_view,                         name='my-tier'),
    path('admin/assign-am/<int:publisher_id>/',      assign_am_view,                       name='assign-am'),
    path('support/tickets/',                         my_tickets_view,                      name='my-tickets'),
    path('support/tickets/create/',                  create_ticket_view,                   name='create-ticket'),
    path('support/tickets/<str:ticket_id>/reply/',   reply_ticket_view,                    name='reply-ticket'),

    # Bonuses
    path('bonus/milestones/',                        milestone_progress_view,              name='milestone-progress'),
    path('bonus/milestones/check/',                  check_milestones_view,                name='milestone-check'),
    path('bonus/summary/',                           bonus_summary_view,                   name='bonus-summary'),
    path('bonus/eligibility/',                       bonus_eligibility_view,               name='bonus-eligibility'),
    path('bonus/welcome/',                           claim_welcome_bonus_view,             name='claim-welcome'),

    # SmartLink
    path('smartlink/create/',                        create_smartlink_view,                name='smartlink-create'),
    path('smartlink/<int:publisher_id>/<str:link_hash>/', smartlink_redirect_view,         name='smartlink-go'),

    # Offerwall
    path('offerwall/',                               offerwall_offers_view,                name='offerwall-offers'),
    path('offerwall/categories/',                    offerwall_categories_view,            name='offerwall-categories'),

    # Content Locking
    path('locker/link/create/',                      create_locked_link,                   name='locker-link-create'),
    path('locker/link/<str:lock_token>/status/',     check_lock_status,                    name='locker-link-status'),
    path('locker/link/<str:lock_token>/unlock/',     record_unlock,                        name='locker-link-unlock'),
    path('locker/file/create/',                      create_file_lock_view,                name='locker-file-create'),
    path('locker/file/<str:lock_id>/token/',         get_download_token_view,              name='locker-file-token'),
    path('locker/download/<str:token>/',             consume_download_view,                name='locker-download'),
    path('locker/content/create/',                   create_content_locker_view,           name='locker-content-create'),
    path('locker/content/<str:lock_id>/unlock/',     unlock_content_view,                  name='locker-content-unlock'),
    path('locker/content/<str:lock_id>/check/',      check_content_unlocked_view,          name='locker-content-check'),
    path('locker/content/<str:lock_id>/offers/',     get_locker_offers_view,               name='locker-content-offers'),

    # SubID Tracking
    path('subid/report/',                            subid_report_view,                    name='subid-report'),
    path('subid/generate/',                          generate_subid_url_view,              name='subid-generate'),

    # Publisher API (external)
    path('ext/offers/',                              publisher_api_offers_view,            name='pub-api-offers'),
    path('ext/generate-key/',                        generate_api_key_view,                name='pub-api-key-gen'),

    # Pay Per Call
    path('ppc/number/create/',                       create_tracking_number_view,          name='ppc-create-number'),
    path('ppc/webhook/',                             call_webhook_view,                    name='ppc-webhook'),

    # Quality Score
    path('quality/my-score/',                        my_quality_score_view,                name='my-quality-score'),
    path('quality/publisher/<int:publisher_id>/',    publisher_quality_score_view,         name='publisher-quality'),
]

urlpatterns = urlpatterns + ALL_SUB_MODULE_URLS
