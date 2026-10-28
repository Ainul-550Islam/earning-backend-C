"""
api/tasks/tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"এক কাজের জন্য একটাই মালিক: api.tasks"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Master re-export file — imports ALL Celery tasks from every
task module in the system. This enables:
  • Celery autodiscovery (all tasks visible from one module)
  • Other apps to do: from api.tasks.tasks import any_task
  • Clean single-entry-point for task introspection

DO NOT add task logic here. All business logic lives in
the specific *_tasks.py files. This file ONLY imports.
"""

# ── Core task system tasks ─────────────────────────────────────────────────
from api.tasks.celery_tasks import (
    run_worker_health_refresh,
    run_queue_depth_snapshot,
    run_alert_evaluation,
    run_task_monitor_refresh,
    run_cost_estimation,
    send_dlq_summary_email,
)

# ── Offer & CPA tasks ──────────────────────────────────────────────────────
from api.tasks.offer_tasks import (
    offer_quality_score,
    rotate_underperforming_offers,
    sync_offer_targeting,
    refresh_offer_feed,
    auto_pause_low_cvr_offers,
    notify_offer_expiry,
)

from api.tasks.cpalead_tasks import (
    cpalead_process_postback,
    cpalead_credit_publisher,
    cpalead_fraud_scan_conversions,
    cpalead_rank_offers,
    cpalead_check_offer_caps,
    cpalead_sync_publisher_stats,
    cpalead_daily_conversion_report,
    cpalead_retry_failed_postbacks,
    cpalead_deduplicate_clicks,
    cpalead_calculate_payouts,
    cpalead_update_offer_stats,
)

# ── CPA / CPI / CPC tasks ─────────────────────────────────────────────────
from api.tasks.click_tracking_tasks import (
    process_click_event,
    fire_postback,
    cleanup_old_clicks,
    calculate_click_attribution,
    generate_click_report,
)

from api.tasks.cpi_tasks import (
    process_app_install_event,
    process_cpi_payout,
    sync_mmp_install_data,
    detect_install_fraud,
    generate_cpi_report,
)

from api.tasks.cpc_tasks import (
    process_cpc_click,
    generate_cpc_report,
)

# ── Survey / Quiz / Email Submit ───────────────────────────────────────────
from api.tasks.survey_tasks import (
    route_survey_to_user,
    verify_survey_completion,
    process_survey_payout,
    sync_survey_inventory,
    generate_survey_report,
)

from api.tasks.personality_quiz_tasks import (
    create_quiz_session,
    record_quiz_answer,
    complete_quiz,
    generate_quiz_result,
    process_quiz_lead,
    sync_quiz_inventory,
    detect_quiz_fraud,
    generate_quiz_report,
    share_quiz_result,
)

from api.tasks.email_submit_tasks import (
    process_email_submit,
    validate_email_quality,
    sync_email_submit_offers,
    detect_email_fraud,
    generate_email_submit_report,
)

# ── Content Lockers ───────────────────────────────────────────────────────
from api.tasks.content_locker_tasks import (
    process_content_locker_unlock,
    process_link_locker_access,
    process_file_locker_download,
    cleanup_expired_unlock_tokens,
    track_locker_stats,
    rotate_locker_offers,
    generate_locker_embed_code,
)

from api.tasks.overlay_locker_tasks import (
    create_overlay_session,
    check_overlay_access,
    expire_overlay_sessions,
    revoke_overlay_access,
    track_overlay_stats,
    generate_overlay_report,
)

# ── RTB ───────────────────────────────────────────────────────────────────
from api.tasks.rtb_tasks import (
    run_bid_auction,
    update_bid_floor_prices,
    refresh_bid_cache,
    rank_advertisers_by_epc,
    detect_invalid_traffic,
    generate_rtb_report,
)

# ── Payment & Wallet tasks ─────────────────────────────────────────────────
from api.tasks.payment_tasks import (
    process_withdrawal_requests,
    payment_reconcile,
    gateway_health_check,
    retry_failed_payments,
    sync_payment_status,
    generate_payment_report,
)

from api.tasks.wallet_tasks import (
    balance_sync,
    detect_suspicious_transactions,
)

from api.tasks.daily_payout_tasks import (
    run_daily_payout_cycle,
    calculate_payout_eligibility,
    queue_payout_batch,
    send_payout_confirmation,
    handle_payout_failures,
    generate_daily_payout_report,
    verify_payout_methods,
)

from api.tasks.crypto_payout_tasks import (
    process_usdt_fast_pay,
    process_crypto_withdrawal,
    verify_crypto_address,
    sync_crypto_exchange_rates,
    monitor_crypto_transactions,
    generate_crypto_payout_report,
)

from api.tasks.payout_queue_tasks import *  # noqa — payout queue management

# ── Fraud Detection ────────────────────────────────────────────────────────
from api.tasks.fraud_detection_tasks import (
    run_fraud_detection_scan,
    scan_ip_reputation,
    flag_suspicious_withdrawal,
    scan_duplicate_completions,
    generate_fraud_report,
    update_fraud_models,
    detect_account_takeover,
)

# ── Gamification ──────────────────────────────────────────────────────────
from api.tasks.gamification_tasks import (
    award_xp_points,
    level_up_check,
    award_badges,
    update_streak_status,
    process_milestone_rewards,
    update_global_leaderboard,
)

from api.tasks.community_tasks import (
    award_community_points,
    check_point_milestones,
    reset_monthly_points,
    update_community_leaderboard,
    send_community_digest,
)

# ── Earning tasks ─────────────────────────────────────────────────────────
from api.tasks.earning_tasks import (
    calculate_daily_user_earnings,
    distribute_bonus_rewards,
    recalculate_leaderboard,
    expire_unclaimed_rewards,
    process_streak_rewards,
)

# ── Publisher & Advertiser ────────────────────────────────────────────────
from api.tasks.publisher_tasks import (
    calculate_publisher_tiers,
    update_publisher_scorecards,
    process_publisher_payouts,
    send_publisher_statements,
    audit_publisher_traffic,
    rotate_publisher_api_keys,
)

from api.tasks.advertiser_tasks import (
    process_advertiser_billing,
    check_advertiser_budgets,
    send_advertiser_invoices,
    verify_advertiser_postbacks,
    auto_approve_campaigns,
)

from api.tasks.self_serve_campaign_tasks import (
    submit_campaign_for_review,
    review_campaign_auto,
    activate_campaign,
    pause_campaign,
    purchase_test_clicks,
    validate_campaign_postback,
    blacklist_traffic_source,
    auto_optimize_campaign,
)

# ── Referral & Affiliate ──────────────────────────────────────────────────
from api.tasks.referral_tasks import (
    commission_processing,
    referral_fraud_scan,
    referral_stats_rollup,
    expire_inactive_referral_codes,
)

from api.tasks.affiliate_tasks import (
    process_affiliate_commission,
    sync_affiliate_networks,
    validate_affiliate_links,
)

# ── User Lifecycle ────────────────────────────────────────────────────────
from api.tasks.user_lifecycle_tasks import (
    send_welcome_sequence,
    assign_onboarding_tasks,
    send_reengagement,
    identify_vip_users,
    send_birthday_bonus,
    auto_deactivate_dormant,
)

# ── Notification tasks ─────────────────────────────────────────────────────
from api.tasks.notification_tasks import (
    dispatch_in_app_notification,
    send_email_notification,
    send_push_notification,
    send_task_reward_notification,
    send_bulk_push_notifications,
    cleanup_old_notifications,
)

# ── KYC tasks ─────────────────────────────────────────────────────────────
from api.tasks.kyc_tasks import (
    check_kyc_verification_status,
    auto_approve_basic_kyc,
    remind_kyc_incomplete,
    update_kyc_limits,
)

# ── Analytics & Reporting ─────────────────────────────────────────────────
from api.tasks.analytics_tasks import (
    compute_platform_kpis,
    compute_queue_throughput,
    daily_analytics_rollup,
    compute_task_failure_rates,
    refresh_analytics_cache,
)

from api.tasks.report_tasks import (
    generate_daily_revenue_report,
    generate_weekly_user_report,
    generate_monthly_admin_report,
    generate_task_performance_report,
)

# ── Smartlink tasks ───────────────────────────────────────────────────────
from api.tasks.smartlink_tasks import (
    recalculate_epc,
    sync_smartlink_stats,
    reset_daily_caps,
    cleanup_expired_offers,
)

# ── Traffic Quality ───────────────────────────────────────────────────────
from api.tasks.traffic_quality_tasks import (
    score_publisher_traffic,
    detect_proxy_traffic,
    update_traffic_tiers,
    generate_traffic_report,
)

# ── ML / AI tasks ─────────────────────────────────────────────────────────
from api.tasks.ml_tasks import (
    run_fraud_prediction,
    run_task_recommendation,
    run_offer_ranking,
    run_churn_prediction,
    compute_user_segments,
    retrain_fraud_model,
)

# ── Email Drip ───────────────────────────────────────────────────────────
from api.tasks.email_drip_tasks import (
    enroll_user_in_drip,
    send_drip_step,
    pause_drip,
    cancel_drip,
)

# ── Virtual Currency & Metaverse ──────────────────────────────────────────
from api.tasks.virtual_currency_tasks import (
    award_virtual_currency,
    process_vc_redemption,
    sync_vc_exchange_rates,
    expire_old_virtual_currency,
)

from api.tasks.metaverse_tasks import (
    process_metaverse_reward,
    send_web3_token_reward,
    sync_metaverse_exchange_rates,
    verify_web3_wallet,
    track_metaverse_stats,
    generate_metaverse_report,
)

# ── Macro Tracking ────────────────────────────────────────────────────────
from api.tasks.macro_tracking_tasks import (
    resolve_macro_params,
    process_macro_postback,
    track_traffic_source,
    sync_tracking_platforms,
    validate_tracking_url,
    generate_macro_report,
)

# ── A/B Testing ───────────────────────────────────────────────────────────
from api.tasks.ab_testing_tasks import (
    assign_ab_variant,
    record_ab_event,
    analyze_ab_results,
    auto_pick_winner,
)

# ── Compliance & GDPR ─────────────────────────────────────────────────────
from api.tasks.compliance_tasks import (
    process_data_deletion_request,
    export_user_data,
    anonymize_old_user_data,
    check_data_retention_policies,
)

# ── Ad Units ──────────────────────────────────────────────────────────────
from api.tasks.ad_unit_tasks import (
    serve_ad_unit,
    track_ad_impression,
    track_ad_click,
    rotate_ad_creatives,
    update_ad_cpm_rates,
    score_ad_quality,
    generate_ad_report,
    cleanup_old_impressions,
)

# ── Webhook tasks ─────────────────────────────────────────────────────────
from api.tasks.webhook_tasks import (
    dispatch_webhook,
    process_incoming_webhook,
    retry_failed_webhooks,
    test_webhook_endpoint,
    cleanup_old_webhook_logs,
)

# ── CAP Management ───────────────────────────────────────────────────────
from api.tasks.tasks_cap import (
    check_all_offer_caps,
    check_campaign_budgets,
    reset_daily_caps,
    sync_cap_counters_to_bridge,
)

# ── Data Pipeline ─────────────────────────────────────────────────────────
from api.tasks.data_pipeline_tasks import (
    run_pipeline,
    sync_user_data_bridge,
    sync_offer_data_bridge,
    sync_platform_kpis_bridge,
    warm_all_caches,
    export_to_s3,
    run_etl_job,
)

# ── Integration tasks ─────────────────────────────────────────────────────
from api.tasks.integration.integration_tasks import (
    on_task_completed,
    on_user_registered,
    on_offer_converted,
    on_fraud_detected,
    on_payment_withdrawal_requested,
)

# ── Health & Maintenance ──────────────────────────────────────────────────
from api.tasks.health_check_tasks import (
    system_health_ping,
    check_database_health,
    check_redis_health,
    check_celery_worker_health,
    check_disk_usage,
)

from api.tasks.backup_tasks import (
    backup_database,
    backup_media_files,
    cleanup_old_backups,
)

from api.tasks.cleanup_tasks import (
    cleanup_old_task_performance_logs,
    cleanup_old_queue_depth_snapshots,
    cleanup_old_workflow_instances,
    cleanup_stale_worker_records,
    cleanup_expired_sessions,
    vacuum_analytics_tables,
)

from api.tasks.maintenance_tasks import (
    cleanup_old_data,
    optimize_database,
    rebuild_search_indexes,
)

# ── Session & Rate Limit ──────────────────────────────────────────────────
from api.tasks.session_tasks import (
    create_user_session,
    cleanup_expired_sessions,
    track_user_activity,
)

# ── Search ────────────────────────────────────────────────────────────────
from api.tasks.search_tasks import (
    index_tasks,
    index_offers,
    rebuild_search_index,
)

# ── Localization ──────────────────────────────────────────────────────────
from api.tasks.localization_tasks import (
    update_exchange_rates,
    update_currency_display,
)

# ── API Key tasks ─────────────────────────────────────────────────────────
from api.tasks.api_key_tasks import (
    generate_api_key,
    rotate_api_keys,
    revoke_api_key,
    audit_api_usage,
)

# ── IP Management ─────────────────────────────────────────────────────────
from api.tasks.ip_management_tasks import (
    sync_ip_blacklist,
    update_geo_routing_table,
    block_ip_range,
    unblock_ip,
    refresh_ip_intelligence,
    generate_geo_report,
)

# ── Postback / S2S ───────────────────────────────────────────────────────
from api.tasks.postback_tasks import *  # noqa

# ── Export / Import tasks ─────────────────────────────────────────────────
from api.tasks.export_tasks import *  # noqa

# ── Blacklist tasks ───────────────────────────────────────────────────────
from api.tasks.blacklist_tasks import *  # noqa

# ── Loyalty / Points ─────────────────────────────────────────────────────
from api.tasks.loyalty_tasks import *  # noqa

# ── Disaster Recovery ────────────────────────────────────────────────────
from api.tasks.disaster_recovery_tasks import *  # noqa

# ── Version Control ───────────────────────────────────────────────────────
from api.tasks.version_control_tasks import *  # noqa

# ── Marketplace ──────────────────────────────────────────────────────────
from api.tasks.marketplace_tasks import *  # noqa

# ── Promotions ───────────────────────────────────────────────────────────
from api.tasks.promotions_tasks import *  # noqa

# ── Subscription ─────────────────────────────────────────────────────────
from api.tasks.subscription_tasks import *  # noqa

# ── Messaging ────────────────────────────────────────────────────────────
from api.tasks.messaging_tasks import *  # noqa

# ── Auto-Mod ─────────────────────────────────────────────────────────────
from api.tasks.auto_mod_tasks import *  # noqa

# ── Inventory ────────────────────────────────────────────────────────────
from api.tasks.inventory_tasks import *  # noqa

# ── Monetization ─────────────────────────────────────────────────────────
from api.tasks.monetization_tasks import *  # noqa

# ── Offer Inventory ───────────────────────────────────────────────────────
from api.tasks.offer_inventory_tasks import *  # noqa

# ── Refund ───────────────────────────────────────────────────────────────
from api.tasks.refund_tasks import (
    process_refund_request,
    handle_chargeback,
    generate_refund_report,
)
