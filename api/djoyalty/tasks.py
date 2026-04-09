# api/djoyalty/tasks.py
"""
Djoyalty Celery Tasks — Root Registry.

এই ফাইলটি Celery beat schedule configuration এর জন্য।
সব tasks এখানে import করা আছে।

settings.py তে Celery beat schedule এ যোগ করুন:

CELERY_BEAT_SCHEDULE = {
    # ─── Points Expiry (daily at 01:00) ──────────────────────────
    'djoyalty-expire-points': {
        'task': 'djoyalty.expire_points',
        'schedule': crontab(hour=1, minute=0),
    },
    'djoyalty-send-expiry-warnings': {
        'task': 'djoyalty.send_expiry_warnings',
        'schedule': crontab(hour=8, minute=0),
    },
    # ─── Tier Evaluation (monthly on 1st at 02:00) ───────────────
    'djoyalty-evaluate-tiers': {
        'task': 'djoyalty.evaluate_all_tiers',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),
    },
    # ─── Streak Reset (daily at 00:05) ───────────────────────────
    'djoyalty-check-broken-streaks': {
        'task': 'djoyalty.check_broken_streaks',
        'schedule': crontab(hour=0, minute=5),
    },
    # ─── Campaigns (every 15 minutes) ────────────────────────────
    'djoyalty-activate-campaigns': {
        'task': 'djoyalty.activate_due_campaigns',
        'schedule': crontab(minute='*/15'),
    },
    # ─── Notifications (daily at 09:00) ──────────────────────────
    'djoyalty-send-expiry-notifications': {
        'task': 'djoyalty.send_expiry_notifications',
        'schedule': crontab(hour=9, minute=0),
    },
    'djoyalty-send-pending-notifications': {
        'task': 'djoyalty.send_pending_notifications',
        'schedule': crontab(minute='*/30'),
    },
    # ─── Leaderboard (every hour) ────────────────────────────────
    'djoyalty-refresh-leaderboard': {
        'task': 'djoyalty.refresh_leaderboard',
        'schedule': crontab(minute=0),
    },
    # ─── Insights (daily at 00:30) ───────────────────────────────
    'djoyalty-daily-insight': {
        'task': 'djoyalty.generate_daily_insight',
        'schedule': crontab(hour=0, minute=30),
    },
    # ─── Fraud Scan (every hour at :15) ──────────────────────────
    'djoyalty-fraud-scan': {
        'task': 'djoyalty.fraud_scan',
        'schedule': crontab(minute=15),
    },
    'djoyalty-scan-rapid-transactions': {
        'task': 'djoyalty.scan_rapid_transactions',
        'schedule': crontab(minute='*/30'),
    },
    # ─── Redemption Auto-approve (every 15 minutes) ──────────────
    'djoyalty-auto-approve-redemptions': {
        'task': 'djoyalty.auto_approve_redemptions',
        'schedule': crontab(minute='*/15'),
    },
    'djoyalty-expire-old-pending-redemptions': {
        'task': 'djoyalty.expire_old_pending_redemptions',
        'schedule': crontab(hour=3, minute=0),
    },
    # ─── Voucher & Gift Card Expiry (daily at 00:30) ─────────────
    'djoyalty-expire-vouchers': {
        'task': 'djoyalty.expire_vouchers',
        'schedule': crontab(hour=0, minute=30),
    },
    'djoyalty-expire-gift-cards': {
        'task': 'djoyalty.expire_gift_cards',
        'schedule': crontab(hour=0, minute=35),
    },
    # ─── Partner Sync (every hour) ───────────────────────────────
    'djoyalty-sync-partners': {
        'task': 'djoyalty.sync_partners',
        'schedule': crontab(minute=0),
    },
    # ─── Subscription Renewals (daily at 06:00) ──────────────────
    'djoyalty-subscription-renewals': {
        'task': 'djoyalty.process_subscription_renewals',
        'schedule': crontab(hour=6, minute=0),
    },
    'djoyalty-cancel-expired-subscriptions': {
        'task': 'djoyalty.cancel_expired_subscriptions',
        'schedule': crontab(hour=6, minute=30),
    },
    # ─── Earn Rules (daily at 00:10) ─────────────────────────────
    'djoyalty-deactivate-expired-earn-rules': {
        'task': 'djoyalty.deactivate_expired_earn_rules',
        'schedule': crontab(hour=0, minute=10),
    },
    'djoyalty-activate-scheduled-earn-rules': {
        'task': 'djoyalty.activate_scheduled_earn_rules',
        'schedule': crontab(minute='*/10'),
    },
}
"""

import logging

logger = logging.getLogger(__name__)

# ─── Import all tasks for Celery autodiscovery ──────────────────────────────

from .tasks.points_expiry_tasks import (
    expire_points_task,
    send_expiry_warnings_task,
)

from .tasks.tier_evaluation_tasks import (
    evaluate_all_tiers_task,
)

from .tasks.streak_reset_tasks import (
    check_broken_streaks_task,
)

from .tasks.campaign_tasks import (
    activate_due_campaigns_task,
)

from .tasks.notification_tasks import (
    send_expiry_notifications_task,
    send_pending_notifications_task,
)

from .tasks.leaderboard_tasks import (
    refresh_leaderboard_task,
    refresh_monthly_leaderboard_task,
)

from .tasks.insight_tasks import (
    generate_daily_insight_task,
    generate_weekly_insight_task,
)

from .tasks.fraud_check_tasks import (
    fraud_scan_task,
    scan_rapid_transactions_task,
)

from .tasks.redemption_tasks import (
    auto_approve_redemptions_task,
    expire_old_pending_redemptions_task,
)

from .tasks.voucher_expiry_tasks import (
    expire_vouchers_task,
    expire_gift_cards_task,
)

from .tasks.partner_sync_tasks import (
    sync_partners_task,
    check_partner_webhooks_task,
)

from .tasks.subscription_tasks import (
    process_subscription_renewals_task,
    cancel_expired_subscriptions_task,
)

from .tasks.earn_rule_tasks import (
    deactivate_expired_earn_rules_task,
    activate_scheduled_earn_rules_task,
)

__all__ = [
    # Points expiry
    'expire_points_task',
    'send_expiry_warnings_task',
    # Tier
    'evaluate_all_tiers_task',
    # Streak
    'check_broken_streaks_task',
    # Campaign
    'activate_due_campaigns_task',
    # Notifications
    'send_expiry_notifications_task',
    'send_pending_notifications_task',
    # Leaderboard
    'refresh_leaderboard_task',
    'refresh_monthly_leaderboard_task',
    # Insights
    'generate_daily_insight_task',
    'generate_weekly_insight_task',
    # Fraud
    'fraud_scan_task',
    'scan_rapid_transactions_task',
    # Redemption
    'auto_approve_redemptions_task',
    'expire_old_pending_redemptions_task',
    # Voucher & Gift card
    'expire_vouchers_task',
    'expire_gift_cards_task',
    # Partners
    'sync_partners_task',
    'check_partner_webhooks_task',
    # Subscriptions
    'process_subscription_renewals_task',
    'cancel_expired_subscriptions_task',
    # Earn rules
    'deactivate_expired_earn_rules_task',
    'activate_scheduled_earn_rules_task',
]

logger.debug('Djoyalty tasks module loaded: %d tasks registered', len(__all__))
