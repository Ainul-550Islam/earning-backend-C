# api/referral/tasks.py
# Top-level Celery task re-exports for autodiscovery
# All actual task logic is in tasks/ package
# ============================================================

try:
    from celery import shared_task

    # Re-export for Celery autodiscovery
    from api.referral.tasks.commission_processing_tasks import (
        process_pending_commissions_to_wallet,
        process_single_commission_event,
        create_weekly_payouts,
    )
    from api.referral.tasks.commission_hold_tasks import (
        release_expired_commission_holds,
    )
    from api.referral.tasks.fraud_scan_tasks import (
        daily_fraud_scan,
        expire_blacklist_entries,
        auto_clear_low_risk_suspicious,
    )
    from api.referral.tasks.clawback_tasks import (
        process_approved_clawbacks,
        initiate_fraud_clawbacks,
    )
    from api.referral.tasks.campaign_tasks import (
        check_campaign_schedules,
        check_campaign_budget,
    )
    from api.referral.tasks.contest_tasks import (
        update_all_contest_leaderboards,
        check_and_finalize_contests,
        update_contest_statuses,
        notify_contest_rank_changes,
    )
    from api.referral.tasks.tree_rebuild_tasks import (
        rebuild_stale_trees,
        full_tree_rebuild,
        tree_consistency_check,
        take_weekly_tree_snapshots,
    )
    from api.referral.tasks.ltv_calculation_tasks import (
        weekly_ltv_recalculation,
        flag_high_churn_risk,
        recalculate_single_ltv,
    )
    from api.referral.tasks.insight_tasks import (
        calculate_daily_insights,
        update_code_conversion_rates,
    )
    from api.referral.tasks.top_referrer_tasks import (
        daily_top_referrer_snapshot,
        weekly_top_referrer_snapshot,
        monthly_top_referrer_snapshot,
        compute_rank_changes,
    )
    from api.referral.tasks.notification_tasks import (
        check_milestone_achievements,
        notify_new_referral_async,
        send_weekly_referral_summary,
    )
    from api.referral.tasks.cleanup_tasks import (
        run_all_cleanups,
    )

except ImportError:
    pass