# api/djoyalty/tasks.py -- FIXED re-export (correct function names from actual files)
from .tasks.points_expiry_tasks import expire_points_task, send_expiry_warnings_task
from .tasks.tier_evaluation_tasks import evaluate_all_tiers_task, evaluate_single_customer_tier_task
from .tasks.streak_reset_tasks import check_broken_streaks_task, reset_all_daily_streaks_task
from .tasks.leaderboard_tasks import refresh_leaderboard_task, refresh_monthly_leaderboard_task
from .tasks.voucher_expiry_tasks import expire_vouchers_task, expire_gift_cards_task
from .tasks.redemption_tasks import auto_approve_redemptions_task, expire_old_pending_redemptions_task
from .tasks.campaign_tasks import activate_due_campaigns_task, notify_campaign_participants_task
from .tasks.fraud_check_tasks import fraud_scan_task, scan_rapid_transactions_task
from .tasks.insight_tasks import generate_daily_insight_task, generate_weekly_insight_task
from .tasks.partner_sync_tasks import sync_partners_task, check_partner_webhooks_task
from .tasks.subscription_tasks import process_subscription_renewals_task, cancel_expired_subscriptions_task
from .tasks.ai_personalization_tasks import (
    compute_rfm_scores_task, run_churn_scan_task,
    generate_birthday_offers_task, cleanup_expired_ai_offers_task,
)
from .tasks.receipt_scan_tasks import (
    process_receipt_scan_task, cleanup_old_receipt_scans_task, flag_suspicious_receipts_task,
)
from .tasks.offerwall_sync_tasks import (
    sync_cpalead_offers_task, cleanup_expired_offers_task, retry_pending_postbacks_task,
)
from .tasks.notification_tasks import send_expiry_notifications_task, send_pending_notifications_task
from .tasks.notification_delivery_tasks import (
    send_notification_task, send_bulk_notification_task, cleanup_old_notifications_task,
)
from .tasks.earn_rule_tasks import (
    deactivate_expired_earn_rules_task, activate_scheduled_earn_rules_task,
)

__all__ = [
    'expire_points_task', 'send_expiry_warnings_task',
    'evaluate_all_tiers_task', 'evaluate_single_customer_tier_task',
    'check_broken_streaks_task', 'reset_all_daily_streaks_task',
    'refresh_leaderboard_task', 'refresh_monthly_leaderboard_task',
    'expire_vouchers_task', 'expire_gift_cards_task',
    'auto_approve_redemptions_task', 'expire_old_pending_redemptions_task',
    'activate_due_campaigns_task', 'notify_campaign_participants_task',
    'fraud_scan_task', 'scan_rapid_transactions_task',
    'generate_daily_insight_task', 'generate_weekly_insight_task',
    'sync_partners_task', 'check_partner_webhooks_task',
    'process_subscription_renewals_task', 'cancel_expired_subscriptions_task',
    'compute_rfm_scores_task', 'run_churn_scan_task',
    'generate_birthday_offers_task', 'cleanup_expired_ai_offers_task',
    'process_receipt_scan_task', 'cleanup_old_receipt_scans_task',
    'flag_suspicious_receipts_task',
    'sync_cpalead_offers_task', 'cleanup_expired_offers_task', 'retry_pending_postbacks_task',
    'send_expiry_notifications_task', 'send_pending_notifications_task',
    'send_notification_task', 'send_bulk_notification_task', 'cleanup_old_notifications_task',
    'deactivate_expired_earn_rules_task', 'activate_scheduled_earn_rules_task',
]
