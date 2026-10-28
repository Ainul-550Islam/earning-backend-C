# api/djoyalty/tasks/__init__.py
"""
Djoyalty Celery tasks package।

FIXED: many task functions were defined but not exported here,
meaning `from djoyalty.tasks import X` failed silently।
All task functions from all task submodules are exported below।

Also: tasks_cap.py was an orphan -- loyalty_task decorator and
LoyaltyTaskMonitor are now imported here so they're accessible।
"""

# ─── Points Expiry ────────────────────────────────────────────────────────────
from .points_expiry_tasks import (
    expire_points_task,
    send_expiry_warnings_task,
)

# ─── Tier Evaluation ──────────────────────────────────────────────────────────
from .tier_evaluation_tasks import (
    evaluate_all_tiers_task,
    evaluate_single_customer_tier_task,
)

# ─── Streaks ──────────────────────────────────────────────────────────────────
from .streak_reset_tasks import (
    check_broken_streaks_task,
    reset_all_daily_streaks_task,
)

# ─── Campaigns ────────────────────────────────────────────────────────────────
from .campaign_tasks import (
    activate_due_campaigns_task,
    notify_campaign_participants_task,
)

# ─── Notifications ────────────────────────────────────────────────────────────
from .notification_tasks import (
    send_expiry_notifications_task,
    send_pending_notifications_task,
)
from .notification_delivery_tasks import (
    send_notification_task,
    send_bulk_notification_task,
    cleanup_old_notifications_task,
    process_queued_message,
)

# ─── Leaderboard ──────────────────────────────────────────────────────────────
from .leaderboard_tasks import (
    refresh_leaderboard_task,
    refresh_monthly_leaderboard_task,
)

# ─── Insights ─────────────────────────────────────────────────────────────────
from .insight_tasks import (
    generate_daily_insight_task,
    generate_weekly_insight_task,
)

# ─── Fraud ────────────────────────────────────────────────────────────────────
from .fraud_check_tasks import (
    fraud_scan_task,
    scan_rapid_transactions_task,
)

# ─── Redemption ───────────────────────────────────────────────────────────────
from .redemption_tasks import (
    auto_approve_redemptions_task,
    expire_old_pending_redemptions_task,
)

# ─── Vouchers / Gift Cards ────────────────────────────────────────────────────
from .voucher_expiry_tasks import (
    expire_vouchers_task,
    expire_gift_cards_task,
)

# ─── Partner Sync ─────────────────────────────────────────────────────────────
from .partner_sync_tasks import (
    sync_partners_task,
    check_partner_webhooks_task,
)

# ─── Subscriptions ────────────────────────────────────────────────────────────
from .subscription_tasks import (
    process_subscription_renewals_task,
    cancel_expired_subscriptions_task,
)

# ─── Earn Rules ───────────────────────────────────────────────────────────────
from .earn_rule_tasks import (
    deactivate_expired_earn_rules_task,
    activate_scheduled_earn_rules_task,
)

# ─── AI Personalization ───────────────────────────────────────────────────────
from .ai_personalization_tasks import (
    compute_rfm_scores_task,
    run_churn_scan_task,
    generate_birthday_offers_task,
    cleanup_expired_ai_offers_task,
)

# ─── Receipt Scan ─────────────────────────────────────────────────────────────
from .receipt_scan_tasks import (
    process_receipt_scan_task,
    cleanup_old_receipt_scans_task,
    flag_suspicious_receipts_task,
)

# ─── OfferWall ────────────────────────────────────────────────────────────────
from .offerwall_sync_tasks import (
    sync_cpalead_offers_task,
    cleanup_expired_offers_task,
    retry_pending_postbacks_task,
)

# ─── Task helpers from tasks_cap.py (previously orphan) ─────────────────────
# FIXED: tasks_cap.py defined loyalty_task decorator and LoyaltyTaskMonitor
# but was never imported anywhere। Now accessible via djoyalty.tasks।
try:
    from ..tasks_cap import loyalty_task, LoyaltyTaskMonitor, TaskRetryStrategy
except ImportError:
    pass

__all__ = [
    # Points expiry
    'expire_points_task', 'send_expiry_warnings_task',
    # Tiers
    'evaluate_all_tiers_task', 'evaluate_single_customer_tier_task',
    # Streaks
    'check_broken_streaks_task', 'reset_all_daily_streaks_task',
    # Campaigns
    'activate_due_campaigns_task', 'notify_campaign_participants_task',
    # Notifications
    'send_expiry_notifications_task', 'send_pending_notifications_task',
    'send_notification_task', 'send_bulk_notification_task',
    'cleanup_old_notifications_task', 'process_queued_message',
    # Leaderboard
    'refresh_leaderboard_task', 'refresh_monthly_leaderboard_task',
    # Insights
    'generate_daily_insight_task', 'generate_weekly_insight_task',
    # Fraud
    'fraud_scan_task', 'scan_rapid_transactions_task',
    # Redemption
    'auto_approve_redemptions_task', 'expire_old_pending_redemptions_task',
    # Vouchers
    'expire_vouchers_task', 'expire_gift_cards_task',
    # Partners
    'sync_partners_task', 'check_partner_webhooks_task',
    # Subscriptions
    'process_subscription_renewals_task', 'cancel_expired_subscriptions_task',
    # Earn rules
    'deactivate_expired_earn_rules_task', 'activate_scheduled_earn_rules_task',
    # AI
    'compute_rfm_scores_task', 'run_churn_scan_task',
    'generate_birthday_offers_task', 'cleanup_expired_ai_offers_task',
    # Receipts
    'process_receipt_scan_task', 'cleanup_old_receipt_scans_task',
    'flag_suspicious_receipts_task',
    # OfferWall
    'sync_cpalead_offers_task', 'cleanup_expired_offers_task',
    'retry_pending_postbacks_task',
]
