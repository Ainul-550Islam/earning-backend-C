"""
api/adapters/__init__.py
Central export for all adapter view functions.
"""

from .admin_panel import (  # noqa: F401
    dashboard_stats,
    user_management,
    task_management,
    financial_overview,
)

from .ai_engine import (  # noqa: F401
    get_ai_recommendations,
    get_ai_insights,
    get_ai_analytics,
    train_ai_model,
)

from .alerts import (  # noqa: F401
    get_user_alerts,
    mark_alert_read,
    mark_all_alerts_read,
    archive_alert,
    create_alert,
    get_alert_preferences,
    update_alert_preferences,
    get_system_alerts,
    create_system_alert,
)

from .analytics import (  # noqa: F401
    user_analytics,
    revenue_analytics,
    platform_analytics,
    real_time_analytics,
)

from .audit_logs import (  # noqa: F401
    get_audit_logs,
    create_audit_log,
    get_user_audit_logs,
    get_audit_summary,
    get_security_events,
)

from .audit_trail import (  # noqa: F401
    get_audit_trail,
    create_audit_entry,
    get_audit_analytics,
    export_audit_trail,
    get_export_status,
    archive_old_entries,
)

from .authentication import (  # noqa: F401
    CustomTokenAuthentication,
    login_user,
    verify_2fa_login,
    logout_user,
    refresh_token,
    get_user_sessions,
    revoke_session,
)

from .backup import (  # noqa: F401
    get_backup_status,
    create_backup,
    get_backup_history,
    restore_backup,
    delete_backup,
    get_backup_settings,
)

from .cache import (  # noqa: F401
    get_cache_status,
    get_cache_keys,
    get_cache_value,
    set_cache_value,
    delete_cache_value,
    clear_user_cache,
    get_cache_analytics,
    optimize_cache,
)

from .cms import (  # noqa: F401
    get_content_list,
    get_content_details,
    create_content,
    update_content,
    delete_content,
    get_media_library,
    get_cms_analytics,
)

from .compliance import (  # noqa: F401
    get_compliance_dashboard,
    get_compliance_assessments,
    create_compliance_assessment,
    get_compliance_findings,
    create_compliance_finding,
    update_finding_status,
    get_compliance_analytics,
    generate_compliance_report,
)

from .djoyalty import (  # noqa: F401
    get_loyalty_profile,
    get_loyalty_rewards,
    redeem_reward,
    get_redemption_history,
    get_points_history,
    get_loyalty_analytics,
)

from .engagement import (  # noqa: F401
    get_engagement_metrics,
    get_engagement_activities,
    track_engagement_event,
    get_engagement_analytics,
)

from .fraud_detection import (  # noqa: F401
    fraud_profile,
    fraud_dashboard,
    manual_fraud_review,
    fraud_alerts,
)

from .gamification import (  # noqa: F401
    get_user_profile,
    get_leaderboard,
    get_achievements,
    get_rewards,
    purchase_reward,
    equip_reward,
)

from .integrations import (  # noqa: F401
    get_integrations,
    create_integration,
    get_integration_details,
    update_integration,
    test_integration,
    sync_integration,
    get_integration_analytics,
    get_available_integrations,
)

from .kyc import (  # noqa: F401
    get_kyc_profile,
    start_kyc_verification,
    upload_kyc_document,
    get_verification_status,
    get_kyc_analytics,
)

from .localization import (  # noqa: F401
    get_user_localization,
    update_user_localization,
    get_translations,
    get_supported_languages,
    get_currency_rates,
    get_localization_analytics,
    upload_translation_file,
)

from .maintenance import (  # noqa: F401
    get_maintenance_status,
    schedule_maintenance,
    get_maintenance_windows,
    start_maintenance,
    complete_maintenance,
    get_maintenance_analytics,
    run_health_check,
)

from .marketplace import (  # noqa: F401
    get_marketplace_listings,
    get_marketplace_details,
    create_marketplace_listing,
    purchase_marketplace_item,
    get_purchase_history,
)

from .notifications import (  # noqa: F401
    get_notifications,
    mark_notification_read,
    mark_all_read,
    create_notification,
    delete_notification,
    notification_settings,
    update_notification_settings,
)

from .offerwall import (  # noqa: F401
    get_offers,
    get_offer_details,
    start_offer,
    complete_offer,
    get_categories,
    search_offers,
)

from .payment_gateways import (  # noqa: F401
    get_payment_methods as get_gateway_payment_methods,
    create_withdrawal,
    withdrawal_history,
    get_transaction_history as get_gateway_transaction_history,
    update_payment_method,
)

from .postback_engine import (  # noqa: F401
    receive_postback,
    get_postback_history,
    retry_postback,
    get_postback_stats,
)

from .promotions import (  # noqa: F401
    get_promotions,
    get_promotion_details,
    claim_promotion,
    get_promotion_history,
    get_promotion_analytics,
)

from .rate_limit import (  # noqa: F401
    get_rate_limit_status,
    get_rate_limit_history,
    request_rate_limit_increase,
    get_rate_limit_requests,
    get_rate_limit_analytics,
    update_rate_limit_config,
)

from .referral import (  # noqa: F401
    referral_profile,
    create_referral,
    referral_history,
    referral_leaderboard,
)

from .reports import (  # noqa: F401
    get_available_reports,
    generate_report,
    get_report_progress,
    get_report_history,
    create_custom_report,
    get_report_analytics,
    cleanup_old_reports,
)

from .security import (  # noqa: F401
    security_profile,
    update_security_settings,
    setup_2fa,
    verify_2fa,
    security_audit_log,
    revoke_sessions,
)

from .subscription import (  # noqa: F401
    get_subscription_plans,
    get_user_subscription,
    create_subscription,
    cancel_subscription,
    upgrade_subscription,
    get_subscription_analytics,
)

from .support import (  # noqa: F401
    get_support_tickets,
    create_support_ticket,
    get_ticket_details,
    add_ticket_reply,
    rate_ticket,
    get_support_analytics,
)

from .tasks import (  # noqa: F401
    get_user_tasks,
    get_task_details,
    start_task,
    submit_task_proof,
    get_task_history,
    get_task_analytics,
)

from .users import (  # noqa: F401
    user_profile,
    update_profile,
    user_stats,
    update_preferences,
    user_activity,
)

from .wallet import (  # noqa: F401
    get_wallet_balance,
    get_transaction_history as get_wallet_transaction_history,
    create_withdrawal_request,
    get_withdrawal_history,
    get_payment_methods as get_wallet_payment_methods,
    setup_payment_method,
    get_wallet_analytics,
)

__all__ = [
    "dashboard_stats",
    "user_management",
    "task_management",
    "financial_overview",
    "get_ai_recommendations",
    "get_ai_insights",
    "get_ai_analytics",
    "train_ai_model",
    "get_user_alerts",
    "mark_alert_read",
    "mark_all_alerts_read",
    "archive_alert",
    "create_alert",
    "get_alert_preferences",
    "update_alert_preferences",
    "get_system_alerts",
    "create_system_alert",
    "user_analytics",
    "revenue_analytics",
    "platform_analytics",
    "real_time_analytics",
    "get_audit_logs",
    "create_audit_log",
    "get_user_audit_logs",
    "get_audit_summary",
    "get_security_events",
    "get_audit_trail",
    "create_audit_entry",
    "get_audit_analytics",
    "export_audit_trail",
    "get_export_status",
    "archive_old_entries",
    "CustomTokenAuthentication",
    "login_user",
    "verify_2fa_login",
    "logout_user",
    "refresh_token",
    "get_user_sessions",
    "revoke_session",
    "get_backup_status",
    "create_backup",
    "get_backup_history",
    "restore_backup",
    "delete_backup",
    "get_backup_settings",
    "get_cache_status",
    "get_cache_keys",
    "get_cache_value",
    "set_cache_value",
    "delete_cache_value",
    "clear_user_cache",
    "get_cache_analytics",
    "optimize_cache",
    "get_content_list",
    "get_content_details",
    "create_content",
    "update_content",
    "delete_content",
    "get_media_library",
    "get_cms_analytics",
    "get_compliance_dashboard",
    "get_compliance_assessments",
    "create_compliance_assessment",
    "get_compliance_findings",
    "create_compliance_finding",
    "update_finding_status",
    "get_compliance_analytics",
    "generate_compliance_report",
    "get_loyalty_profile",
    "get_loyalty_rewards",
    "redeem_reward",
    "get_redemption_history",
    "get_points_history",
    "get_loyalty_analytics",
    "get_engagement_metrics",
    "get_engagement_activities",
    "track_engagement_event",
    "get_engagement_analytics",
    "fraud_profile",
    "fraud_dashboard",
    "manual_fraud_review",
    "fraud_alerts",
    "get_user_profile",
    "get_leaderboard",
    "get_achievements",
    "get_rewards",
    "purchase_reward",
    "equip_reward",
    "get_integrations",
    "create_integration",
    "get_integration_details",
    "update_integration",
    "test_integration",
    "sync_integration",
    "get_integration_analytics",
    "get_available_integrations",
    "get_kyc_profile",
    "start_kyc_verification",
    "upload_kyc_document",
    "get_verification_status",
    "get_kyc_analytics",
    "get_user_localization",
    "update_user_localization",
    "get_translations",
    "get_supported_languages",
    "get_currency_rates",
    "get_localization_analytics",
    "upload_translation_file",
    "get_maintenance_status",
    "schedule_maintenance",
    "get_maintenance_windows",
    "start_maintenance",
    "complete_maintenance",
    "get_maintenance_analytics",
    "run_health_check",
    "get_marketplace_listings",
    "get_marketplace_details",
    "create_marketplace_listing",
    "purchase_marketplace_item",
    "get_purchase_history",
    "get_notifications",
    "mark_notification_read",
    "mark_all_read",
    "create_notification",
    "delete_notification",
    "notification_settings",
    "update_notification_settings",
    "get_offers",
    "get_offer_details",
    "start_offer",
    "complete_offer",
    "get_categories",
    "search_offers",
    "get_gateway_payment_methods",
    "create_withdrawal",
    "withdrawal_history",
    "get_gateway_transaction_history",
    "update_payment_method",
    "receive_postback",
    "get_postback_history",
    "retry_postback",
    "get_postback_stats",
    "get_promotions",
    "get_promotion_details",
    "claim_promotion",
    "get_promotion_history",
    "get_promotion_analytics",
    "get_rate_limit_status",
    "get_rate_limit_history",
    "request_rate_limit_increase",
    "get_rate_limit_requests",
    "get_rate_limit_analytics",
    "update_rate_limit_config",
    "referral_profile",
    "create_referral",
    "referral_history",
    "referral_leaderboard",
    "get_available_reports",
    "generate_report",
    "get_report_progress",
    "get_report_history",
    "create_custom_report",
    "get_report_analytics",
    "cleanup_old_reports",
    "security_profile",
    "update_security_settings",
    "setup_2fa",
    "verify_2fa",
    "security_audit_log",
    "revoke_sessions",
    "get_subscription_plans",
    "get_user_subscription",
    "create_subscription",
    "cancel_subscription",
    "upgrade_subscription",
    "get_subscription_analytics",
    "get_support_tickets",
    "create_support_ticket",
    "get_ticket_details",
    "add_ticket_reply",
    "rate_ticket",
    "get_support_analytics",
    "get_user_tasks",
    "get_task_details",
    "start_task",
    "submit_task_proof",
    "get_task_history",
    "get_task_analytics",
    "user_profile",
    "update_profile",
    "user_stats",
    "update_preferences",
    "user_activity",
    "get_wallet_balance",
    "get_wallet_transaction_history",
    "create_withdrawal_request",
    "get_withdrawal_history",
    "get_wallet_payment_methods",
    "setup_payment_method",
    "get_wallet_analytics",
]