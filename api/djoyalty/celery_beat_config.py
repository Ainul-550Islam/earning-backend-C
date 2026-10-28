# api/djoyalty/celery_beat_config.py
"""
Djoyalty Celery Beat Schedule।
All periodic task schedules in one place।

FIXED (v3):
  - All task name strings corrected to match actual @shared_task(name=...) registrations
  - Added 15 previously unscheduled but defined tasks
  - Duplicate djoyalty.send_expiry_warnings resolved (two separate schedule entries
    with different kwargs are valid -- Celery calls the same registered task twice)
  - send_notification added (every 2 min) -- notification queue was never drained
  - FIXED docstring import path: 'djoyalty.celery_beat_config' ->
    'api.djoyalty.celery_beat_config' to match actual module location

Add to settings.py:
  from api.djoyalty.celery_beat_config import djoyalty_beat_schedule, DJOYALTY_CELERY_QUEUES
  CELERY_BEAT_SCHEDULE = djoyalty_beat_schedule()
  CELERY_TASK_QUEUES = [Queue(q, routing_key=q) for q in DJOYALTY_CELERY_QUEUES]
"""
from celery.schedules import crontab


def djoyalty_beat_schedule() -> dict:
    """Return complete Celery Beat schedule for Djoyalty।"""
    return {

        # ─── Points ──────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.points_expiry_tasks.expire_points_task'
        'djoyalty-expire-points-daily': {
            'task': 'djoyalty.expire_points',
            'schedule': crontab(hour=0, minute=5),
            'options': {'queue': 'djoyalty_points'},
        },
        # FIXED: was 'djoyalty.send_expiry_warnings' (correct) but no _task suffix needed
        # Two separate schedule entries for same task with different kwargs is intentional
        'djoyalty-send-expiry-warnings-7d': {
            'task': 'djoyalty.send_expiry_warnings',
            'schedule': crontab(hour=9, minute=0),
            'kwargs': {'days_before': 7},
            'options': {'queue': 'djoyalty_notifications'},
        },
        'djoyalty-send-expiry-warnings-3d': {
            'task': 'djoyalty.send_expiry_warnings',
            'schedule': crontab(hour=9, minute=15),
            'kwargs': {'days_before': 3},
            'options': {'queue': 'djoyalty_notifications'},
        },
        # NEW: expiry notifications (was defined but never scheduled)
        'djoyalty-send-expiry-notifications-daily': {
            'task': 'djoyalty.send_expiry_notifications',
            'schedule': crontab(hour=9, minute=30),
            'options': {'queue': 'djoyalty_notifications'},
        },

        # ─── Tiers ───────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.tier_evaluation_tasks.evaluate_all_tiers_task'
        'djoyalty-evaluate-tiers-monthly': {
            'task': 'djoyalty.evaluate_all_tiers',
            'schedule': crontab(day_of_month=1, hour=2, minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Streaks ─────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.streak_reset_tasks.reset_broken_streaks_task'
        'djoyalty-check-broken-streaks': {
            'task': 'djoyalty.check_broken_streaks',
            'schedule': crontab(hour=0, minute=30),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: reset all daily streaks at midnight (was defined but never scheduled)
        'djoyalty-reset-all-daily-streaks': {
            'task': 'djoyalty.reset_all_daily_streaks',
            'schedule': crontab(hour=0, minute=35),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Vouchers & Gift Cards ────────────────────────────────────────────
        # FIXED: was 'djoyalty.voucher_expiry_tasks.expire_vouchers_task'
        'djoyalty-expire-vouchers-daily': {
            'task': 'djoyalty.expire_vouchers',
            'schedule': crontab(hour=0, minute=10),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: expire gift cards (was defined but never scheduled)
        'djoyalty-expire-gift-cards-daily': {
            'task': 'djoyalty.expire_gift_cards',
            'schedule': crontab(hour=0, minute=12),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Campaigns ───────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.campaign_tasks.update_campaign_statuses_task'
        # Function is activate_due_campaigns_task registered as 'djoyalty.activate_due_campaigns'
        'djoyalty-activate-due-campaigns': {
            'task': 'djoyalty.activate_due_campaigns',
            'schedule': crontab(minute='*/30'),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: notify campaign participants (was defined but never scheduled)
        'djoyalty-notify-campaign-participants-daily': {
            'task': 'djoyalty.notify_campaign_participants',
            'schedule': crontab(hour=10, minute=0),
            'options': {'queue': 'djoyalty_notifications'},
        },

        # ─── Earn Rules ───────────────────────────────────────────────────────
        # NEW: deactivate expired earn rules (was defined but never scheduled)
        'djoyalty-deactivate-expired-earn-rules': {
            'task': 'djoyalty.deactivate_expired_earn_rules',
            'schedule': crontab(hour=0, minute=20),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: activate scheduled earn rules (was defined but never scheduled)
        'djoyalty-activate-scheduled-earn-rules': {
            'task': 'djoyalty.activate_scheduled_earn_rules',
            'schedule': crontab(minute='*/30'),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Redemption ───────────────────────────────────────────────────────
        # NEW: auto-approve eligible redemptions (was defined but never scheduled)
        'djoyalty-auto-approve-redemptions-hourly': {
            'task': 'djoyalty.auto_approve_redemptions',
            'schedule': crontab(minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: expire old pending redemptions (was defined but never scheduled)
        'djoyalty-expire-old-pending-redemptions': {
            'task': 'djoyalty.expire_old_pending_redemptions',
            'schedule': crontab(hour=1, minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── AI / RFM ────────────────────────────────────────────────────────
        # These were correct -- task name= matches beat string
        'djoyalty-compute-rfm-daily': {
            'task': 'djoyalty.compute_rfm_scores',
            'schedule': crontab(hour=2, minute=0),
            'options': {'queue': 'djoyalty_ai'},
        },
        'djoyalty-churn-scan-daily': {
            'task': 'djoyalty.run_churn_scan',
            'schedule': crontab(hour=3, minute=0),
            'options': {'queue': 'djoyalty_ai'},
        },
        'djoyalty-birthday-offers-daily': {
            'task': 'djoyalty.generate_birthday_offers',
            'schedule': crontab(hour=8, minute=0),
            'options': {'queue': 'djoyalty_ai'},
        },
        'djoyalty-cleanup-expired-ai-offers': {
            'task': 'djoyalty.cleanup_expired_ai_offers',
            'schedule': crontab(hour=1, minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Insights ────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.insight_tasks.generate_daily_insight_task'
        'djoyalty-generate-daily-insights': {
            'task': 'djoyalty.generate_daily_insight',
            'schedule': crontab(hour=1, minute=0),
            'options': {'queue': 'djoyalty_ai'},
        },
        # NEW: weekly insights (was defined but never scheduled)
        'djoyalty-generate-weekly-insights': {
            'task': 'djoyalty.generate_weekly_insight',
            'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday
            'options': {'queue': 'djoyalty_ai'},
        },

        # ─── Partners ────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.partner_sync_tasks.sync_all_partners_task'
        'djoyalty-sync-partners': {
            'task': 'djoyalty.sync_partners',
            'schedule': crontab(hour='*/6'),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: check partner webhooks (was defined but never scheduled)
        'djoyalty-check-partner-webhooks': {
            'task': 'djoyalty.check_partner_webhooks',
            'schedule': crontab(hour='*/4'),
            'options': {'queue': 'djoyalty_webhooks'},
        },

        # ─── Leaderboard ─────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.leaderboard_tasks.update_leaderboard_task'
        'djoyalty-refresh-leaderboard-hourly': {
            'task': 'djoyalty.refresh_leaderboard',
            'schedule': crontab(minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },
        # NEW: monthly leaderboard refresh (was defined but never scheduled)
        'djoyalty-refresh-monthly-leaderboard': {
            'task': 'djoyalty.refresh_monthly_leaderboard',
            'schedule': crontab(day_of_month=1, hour=3, minute=0),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Fraud ───────────────────────────────────────────────────────────
        # FIXED: was 'djoyalty.fraud_check_tasks.hourly_fraud_check_task'
        'djoyalty-fraud-scan-hourly': {
            'task': 'djoyalty.fraud_scan',
            'schedule': crontab(minute=0),
            'options': {'queue': 'djoyalty_critical'},
        },
        # NEW: scan rapid transactions every 5 min (was defined but never scheduled)
        'djoyalty-scan-rapid-transactions': {
            'task': 'djoyalty.scan_rapid_transactions',
            'schedule': crontab(minute='*/5'),
            'options': {'queue': 'djoyalty_critical'},
        },
        # Was correct -- keep as-is
        'djoyalty-flag-suspicious-receipts': {
            'task': 'djoyalty.flag_suspicious_receipts',
            'schedule': crontab(minute='*/30'),
            'options': {'queue': 'djoyalty_critical'},
        },

        # ─── OfferWall ───────────────────────────────────────────────────────
        # These were correct -- task name= matches beat string
        'djoyalty-cleanup-expired-offers': {
            'task': 'djoyalty.cleanup_expired_offers',
            'schedule': crontab(hour=0, minute=15),
            'options': {'queue': 'djoyalty_bulk'},
        },
        'djoyalty-retry-pending-postbacks': {
            'task': 'djoyalty.retry_pending_postbacks',
            'schedule': crontab(minute='*/15'),
            'options': {'queue': 'djoyalty_webhooks'},
        },
        # NEW: sync CPAlead offers (was defined but never scheduled)
        'djoyalty-sync-cpalead-offers': {
            'task': 'djoyalty.sync_cpalead_offers',
            'schedule': crontab(hour='*/4'),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Subscriptions ───────────────────────────────────────────────────
        # FIXED: was 'djoyalty.subscription_tasks.process_subscription_renewals_task'
        'djoyalty-subscription-renewals': {
            'task': 'djoyalty.process_subscription_renewals',
            'schedule': crontab(hour=8, minute=30),
            'options': {'queue': 'djoyalty_cashout'},
        },
        # NEW: cancel expired subscriptions (was defined but never scheduled)
        'djoyalty-cancel-expired-subscriptions': {
            'task': 'djoyalty.cancel_expired_subscriptions',
            'schedule': crontab(hour=1, minute=30),
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Notifications ───────────────────────────────────────────────────
        # CRITICAL NEW: send_notification was never scheduled -> notification queue
        # was accumulating messages with no delivery worker draining it
        'djoyalty-send-notification-frequent': {
            'task': 'djoyalty.send_notification',
            'schedule': crontab(minute='*/2'),
            'options': {'queue': 'djoyalty_notifications'},
        },
        # NEW: send pending queued notifications (was defined but never scheduled)
        'djoyalty-send-pending-notifications': {
            'task': 'djoyalty.send_pending_notifications',
            'schedule': crontab(minute='*/5'),
            'options': {'queue': 'djoyalty_notifications'},
        },
        # These were correct -- keep as-is
        'djoyalty-cleanup-old-notifications': {
            'task': 'djoyalty.cleanup_old_notifications',
            'schedule': crontab(hour=3, minute=30, day_of_week=0),  # weekly Sunday
            'kwargs': {'days': 90},
            'options': {'queue': 'djoyalty_bulk'},
        },

        # ─── Receipts ────────────────────────────────────────────────────────
        # These were correct -- keep as-is
        'djoyalty-cleanup-old-receipts': {
            'task': 'djoyalty.cleanup_old_receipt_scans',
            'schedule': crontab(hour=4, minute=0, day_of_month=1),  # monthly
            'options': {'queue': 'djoyalty_bulk'},
        },
    }


# ─── Celery Queue Configuration ──────────────────────────────────────────────
# Paste into settings.py -> CELERY_TASK_QUEUES
DJOYALTY_CELERY_QUEUES = [
    'djoyalty_notifications',
    'djoyalty_webhooks',
    'djoyalty_points',
    'djoyalty_cashout',
    'djoyalty_ai',
    'djoyalty_bulk',
    'djoyalty_critical',
]

# ─── Quick Setup (paste into settings.py) ─────────────────────────────────────
# FIXED import path: api.djoyalty.celery_beat_config (not djoyalty.celery_beat_config)
# from api.djoyalty.celery_beat_config import djoyalty_beat_schedule, DJOYALTY_CELERY_QUEUES
# CELERY_BEAT_SCHEDULE = djoyalty_beat_schedule()
# CELERY_TASK_QUEUES = [Queue(q, routing_key=q) for q in DJOYALTY_CELERY_QUEUES]
