"""
tasks/celery_beat_schedule.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Complete Celery Beat Schedule — World-Class CPAlead System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Import this in settings.py:
  from api.tasks.celery_beat_schedule import CELERYBEAT_SCHEDULE
  app.conf.beat_schedule = CELERYBEAT_SCHEDULE

Or in celery.py:
  from api.tasks.celery_beat_schedule import CELERYBEAT_SCHEDULE
  app.conf.update(beat_schedule=CELERYBEAT_SCHEDULE)
"""
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {

    # ══════════════════════════════════════════════════════════════
    # SYSTEM HEALTH (every 5 minutes)
    # ══════════════════════════════════════════════════════════════
    'system-health-ping': {
        'task': 'tasks.health_check_tasks.system_health_ping',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default', 'expires': 240},
    },
    'check-database-health': {
        'task': 'tasks.health_check_tasks.check_database_health',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'check-redis-health': {
        'task': 'tasks.health_check_tasks.check_redis_health',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'check-celery-workers': {
        'task': 'tasks.health_check_tasks.check_celery_worker_health',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
    'check-disk-usage': {
        'task': 'tasks.health_check_tasks.check_disk_usage',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # WORKER & QUEUE MONITORING (every 2 minutes)
    # ══════════════════════════════════════════════════════════════
    'refresh-worker-health': {
        'task': 'tasks.celery_tasks.run_worker_health_refresh',
        'schedule': crontab(minute='*/2'),
        'options': {'queue': 'default', 'expires': 90},
    },
    'snapshot-queue-depth': {
        'task': 'tasks.celery_tasks.run_queue_depth_snapshot',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
    'evaluate-task-alerts': {
        'task': 'tasks.celery_tasks.run_alert_evaluation',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'refresh-task-monitors': {
        'task': 'tasks.celery_tasks.run_task_monitor_refresh',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # CPALEAD — CLICK & CONVERSION (real-time, every minute)
    # ══════════════════════════════════════════════════════════════
    'cpalead-check-offer-caps': {
        'task': 'tasks.cpalead_tasks.cpalead_check_offer_caps',
        'schedule': crontab(minute='*/1'),
        'options': {'queue': 'high', 'expires': 55},
    },
    'cpalead-deduplicate-clicks': {
        'task': 'tasks.cpalead_tasks.cpalead_deduplicate_clicks',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'high'},
    },
    'cpalead-fraud-scan': {
        'task': 'tasks.cpalead_tasks.cpalead_fraud_scan_conversions',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'high'},
    },
    'cpalead-rank-offers': {
        'task': 'tasks.cpalead_tasks.cpalead_rank_offers',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'cpalead-sync-publisher-stats': {
        'task': 'tasks.cpalead_tasks.cpalead_sync_publisher_stats',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # OFFER MANAGEMENT (every 30 minutes)
    # ══════════════════════════════════════════════════════════════
    'refresh-offer-feed': {
        'task': 'tasks.offer_tasks.refresh_offer_feed',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'sync-offer-targeting': {
        'task': 'tasks.offer_tasks.sync_offer_targeting',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'offer-quality-score': {
        'task': 'tasks.offer_tasks.offer_quality_score',
        'schedule': crontab(minute=30, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'auto-pause-low-cvr': {
        'task': 'tasks.offer_tasks.auto_pause_low_cvr_offers',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # CLICK TRACKING (every 5 minutes)
    # ══════════════════════════════════════════════════════════════
    'click-attribution': {
        'task': 'tasks.click_tracking_tasks.calculate_click_attribution',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'high'},
    },
    'retry-failed-postbacks': {
        'task': 'tasks.cpalead_tasks.cpalead_retry_failed_postbacks',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # PAYMENT (every 5 minutes for withdrawals, hourly for reconcile)
    # ══════════════════════════════════════════════════════════════
    'process-withdrawals': {
        'task': 'tasks.payment_tasks.process_withdrawal_requests',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'payments'},
    },
    'payment-reconcile': {
        'task': 'tasks.payment_tasks.payment_reconcile',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'payments'},
    },
    'gateway-health-check': {
        'task': 'tasks.payment_tasks.gateway_health_check',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'retry-failed-payments': {
        'task': 'tasks.payment_tasks.retry_failed_payments',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'payments'},
    },

    # ══════════════════════════════════════════════════════════════
    # WALLET (every 15 minutes)
    # ══════════════════════════════════════════════════════════════
    'wallet-balance-sync': {
        'task': 'tasks.wallet_tasks.balance_sync',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'detect-suspicious-transactions': {
        'task': 'tasks.wallet_tasks.detect_suspicious_transactions',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # FRAUD DETECTION (every 15 minutes)
    # ══════════════════════════════════════════════════════════════
    'fraud-detection-scan': {
        'task': 'tasks.fraud_detection_tasks.run_fraud_detection_scan',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'high'},
    },
    'scan-ip-reputation': {
        'task': 'tasks.fraud_detection_tasks.scan_ip_reputation',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'high'},
    },
    'flag-suspicious-withdrawals': {
        'task': 'tasks.fraud_detection_tasks.flag_suspicious_withdrawal',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'high'},
    },
    'scan-duplicate-completions': {
        'task': 'tasks.fraud_detection_tasks.scan_duplicate_completions',
        'schedule': crontab(minute='*/20'),
        'options': {'queue': 'high'},
    },

    # ══════════════════════════════════════════════════════════════
    # ML / AI (every 30 minutes)
    # ══════════════════════════════════════════════════════════════
    'ml-fraud-prediction': {
        'task': 'tasks.ml_tasks.run_fraud_prediction',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'ml'},
    },
    'ml-task-recommendations': {
        'task': 'tasks.ml_tasks.run_task_recommendation',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'ml'},
    },
    'ml-offer-ranking': {
        'task': 'tasks.ml_tasks.run_offer_ranking',
        'schedule': crontab(minute=30, hour='*/1'),
        'options': {'queue': 'ml'},
    },
    'ml-churn-prediction': {
        'task': 'tasks.ml_tasks.run_churn_prediction',
        'schedule': crontab(minute=0, hour=4),  # 4am daily
        'options': {'queue': 'ml'},
    },
    'ml-user-segments': {
        'task': 'tasks.ml_tasks.compute_user_segments',
        'schedule': crontab(minute=0, hour=3),  # 3am daily
        'options': {'queue': 'ml'},
    },

    # ══════════════════════════════════════════════════════════════
    # REFERRAL (hourly)
    # ══════════════════════════════════════════════════════════════
    'commission-processing': {
        'task': 'tasks.referral_tasks.commission_processing',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'payments'},
    },
    'referral-fraud-scan': {
        'task': 'tasks.referral_tasks.referral_fraud_scan',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'default'},
    },
    'referral-stats-rollup': {
        'task': 'tasks.referral_tasks.referral_stats_rollup',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # GAMIFICATION (every 30 minutes)
    # ══════════════════════════════════════════════════════════════
    'update-global-leaderboard': {
        'task': 'tasks.gamification_tasks.update_global_leaderboard',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'process-milestone-rewards': {
        'task': 'tasks.gamification_tasks.process_milestone_rewards',
        'args': [],
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'process-streak-rewards': {
        'task': 'tasks.earning_tasks.process_streak_rewards',
        'schedule': crontab(minute=0, hour=1),  # 1am daily
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # SMARTLINK / OFFERS (every hour)
    # ══════════════════════════════════════════════════════════════
    'recalculate-epc': {
        'task': 'tasks.smartlink_tasks.recalculate_epc',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'sync-smartlink-stats': {
        'task': 'tasks.smartlink_tasks.sync_smartlink_stats',
        'schedule': crontab(minute=30, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'reset-daily-caps': {
        'task': 'tasks.smartlink_tasks.reset_daily_caps',
        'schedule': crontab(minute=1, hour=0),  # midnight
        'options': {'queue': 'high'},
    },

    # ══════════════════════════════════════════════════════════════
    # ANALYTICS (every 5 minutes for KPIs, daily rollup at midnight)
    # ══════════════════════════════════════════════════════════════
    'compute-platform-kpis': {
        'task': 'tasks.analytics_tasks.compute_platform_kpis',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
    'compute-queue-throughput': {
        'task': 'tasks.analytics_tasks.compute_queue_throughput',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
    'daily-analytics-rollup': {
        'task': 'tasks.analytics_tasks.daily_analytics_rollup',
        'schedule': crontab(minute=5, hour=0),  # 00:05 UTC
        'options': {'queue': 'reports'},
    },
    'compute-failure-rates': {
        'task': 'tasks.analytics_tasks.compute_task_failure_rates',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },
    'refresh-analytics-cache': {
        'task': 'tasks.analytics_tasks.refresh_analytics_cache',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # REPORTS (daily)
    # ══════════════════════════════════════════════════════════════
    'daily-revenue-report': {
        'task': 'tasks.report_tasks.generate_daily_revenue_report',
        'schedule': crontab(minute=15, hour=0),  # 00:15 UTC
        'options': {'queue': 'reports'},
    },
    'daily-payment-report': {
        'task': 'tasks.payment_tasks.generate_payment_report',
        'schedule': crontab(minute=20, hour=0),
        'options': {'queue': 'reports'},
    },
    'cpalead-daily-conversion-report': {
        'task': 'tasks.cpalead_tasks.cpalead_daily_conversion_report',
        'schedule': crontab(minute=25, hour=0),
        'options': {'queue': 'reports'},
    },
    'click-daily-report': {
        'task': 'tasks.click_tracking_tasks.generate_click_report',
        'schedule': crontab(minute=30, hour=0),
        'options': {'queue': 'reports'},
    },
    'fraud-daily-report': {
        'task': 'tasks.fraud_detection_tasks.generate_fraud_report',
        'schedule': crontab(minute=35, hour=0),
        'options': {'queue': 'reports'},
    },
    'weekly-user-report': {
        'task': 'tasks.report_tasks.generate_weekly_user_report',
        'schedule': crontab(minute=0, hour=1, day_of_week=1),  # Monday 1am
        'options': {'queue': 'reports'},
    },
    'monthly-admin-report': {
        'task': 'tasks.report_tasks.generate_monthly_admin_report',
        'schedule': crontab(minute=0, hour=2, day_of_month=1),  # 1st of month
        'options': {'queue': 'reports'},
    },
    'task-performance-report': {
        'task': 'tasks.report_tasks.generate_task_performance_report',
        'schedule': crontab(minute=45, hour=0),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # NOTIFICATIONS (every 15 minutes)
    # ══════════════════════════════════════════════════════════════
    'cleanup-old-notifications': {
        'task': 'tasks.notification_tasks.cleanup_old_notifications',
        'schedule': crontab(minute=0, hour=2),  # 2am daily
        'options': {'queue': 'emails'},
    },
    'offer-expiry-notifications': {
        'task': 'tasks.offer_tasks.notify_offer_expiry',
        'schedule': crontab(minute=0, hour=9),  # 9am daily
        'options': {'queue': 'emails'},
    },

    # ══════════════════════════════════════════════════════════════
    # USER LIFECYCLE (daily)
    # ══════════════════════════════════════════════════════════════
    'send-reengagement': {
        'task': 'tasks.user_lifecycle_tasks.send_reengagement',
        'schedule': crontab(minute=0, hour=10),  # 10am daily
        'options': {'queue': 'emails'},
    },
    'identify-vip-users': {
        'task': 'tasks.user_lifecycle_tasks.identify_vip_users',
        'schedule': crontab(minute=0, hour=3),  # 3am daily
        'options': {'queue': 'default'},
    },
    'birthday-bonuses': {
        'task': 'tasks.user_lifecycle_tasks.send_birthday_bonus',
        'schedule': crontab(minute=0, hour=8),  # 8am daily
        'options': {'queue': 'emails'},
    },

    # ══════════════════════════════════════════════════════════════
    # PUBLISHER (hourly/daily)
    # ══════════════════════════════════════════════════════════════
    'publisher-scorecards': {
        'task': 'tasks.publisher_tasks.update_publisher_scorecards',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },
    'publisher-tiers': {
        'task': 'tasks.publisher_tasks.calculate_publisher_tiers',
        'schedule': crontab(minute=0, hour=2, day_of_month=1),  # Monthly
        'options': {'queue': 'default'},
    },
    'audit-publisher-traffic': {
        'task': 'tasks.publisher_tasks.audit_publisher_traffic',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'high'},
    },
    'verify-advertiser-postbacks': {
        'task': 'tasks.advertiser_tasks.verify_advertiser_postbacks',
        'schedule': crontab(minute=0, hour=6),  # 6am daily
        'options': {'queue': 'default'},
    },
    'check-advertiser-budgets': {
        'task': 'tasks.advertiser_tasks.check_advertiser_budgets',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'high'},
    },
    'process-advertiser-billing': {
        'task': 'tasks.advertiser_tasks.process_advertiser_billing',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'payments'},
    },

    # ══════════════════════════════════════════════════════════════
    # SURVEY (every 2 hours)
    # ══════════════════════════════════════════════════════════════
    'sync-survey-inventory': {
        'task': 'tasks.survey_tasks.sync_survey_inventory',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # KYC (every 30 minutes)
    # ══════════════════════════════════════════════════════════════
    'check-kyc-status': {
        'task': 'tasks.kyc_tasks.check_kyc_verification_status',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'auto-approve-basic-kyc': {
        'task': 'tasks.kyc_tasks.auto_approve_basic_kyc',
        'schedule': crontab(minute=0, hour=4),  # 4am daily
        'options': {'queue': 'default'},
    },
    'remind-kyc-incomplete': {
        'task': 'tasks.kyc_tasks.remind_kyc_incomplete',
        'schedule': crontab(minute=0, hour=9),  # 9am daily
        'options': {'queue': 'emails'},
    },
    'update-kyc-limits': {
        'task': 'tasks.kyc_tasks.update_kyc_limits',
        'schedule': crontab(minute=0, hour=1),  # 1am daily
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # LOCALIZATION (every hour)
    # ══════════════════════════════════════════════════════════════
    'update-exchange-rates': {
        'task': 'tasks.localization_tasks.update_exchange_rates',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'update-currency-display': {
        'task': 'tasks.localization_tasks.update_currency_display',
        'schedule': crontab(minute=15, hour='*/1'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # CLEANUP (daily/weekly)
    # ══════════════════════════════════════════════════════════════
    'cleanup-old-perf-logs': {
        'task': 'tasks.cleanup_tasks.cleanup_old_task_performance_logs',
        'schedule': crontab(minute=0, hour=3),  # 3am daily
        'kwargs': {'days_to_keep': 30},
        'options': {'queue': 'low'},
    },
    'cleanup-old-queue-depths': {
        'task': 'tasks.cleanup_tasks.cleanup_old_queue_depth_snapshots',
        'schedule': crontab(minute=0, hour=3),
        'kwargs': {'days_to_keep': 7},
        'options': {'queue': 'low'},
    },
    'cleanup-old-workflow-instances': {
        'task': 'tasks.cleanup_tasks.cleanup_old_workflow_instances',
        'schedule': crontab(minute=0, hour=4),
        'options': {'queue': 'low'},
    },
    'cleanup-stale-workers': {
        'task': 'tasks.cleanup_tasks.cleanup_stale_worker_records',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'cleanup-expired-sessions': {
        'task': 'tasks.cleanup_tasks.cleanup_expired_sessions',
        'schedule': crontab(minute=0, hour=2),
        'options': {'queue': 'low'},
    },
    'cleanup-old-clicks': {
        'task': 'tasks.click_tracking_tasks.cleanup_old_clicks',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),  # Sunday 5am
        'options': {'queue': 'low'},
    },
    'expire-referral-codes': {
        'task': 'tasks.referral_tasks.expire_inactive_referral_codes',
        'schedule': crontab(minute=0, hour=2, day_of_week=1),  # Monday 2am
        'options': {'queue': 'low'},
    },
    'expire-unclaimed-rewards': {
        'task': 'tasks.earning_tasks.expire_unclaimed_rewards',
        'schedule': crontab(minute=0, hour=2, day_of_month=1),  # Monthly
        'options': {'queue': 'low'},
    },
    'cleanup-expired-smartlinks': {
        'task': 'tasks.smartlink_tasks.cleanup_expired_offers',
        'schedule': crontab(minute=0, hour=1),
        'options': {'queue': 'low'},
    },
    'maintenance-cleanup': {
        'task': 'tasks.maintenance_tasks.cleanup_old_data',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),  # Sunday 3am
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # MAINTENANCE (weekly)
    # ══════════════════════════════════════════════════════════════
    'optimize-database': {
        'task': 'tasks.maintenance_tasks.optimize_database',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),  # Sunday 4am
        'options': {'queue': 'low'},
    },
    'rebuild-search-indexes': {
        'task': 'tasks.maintenance_tasks.rebuild_search_indexes',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),  # Sunday 5am
        'options': {'queue': 'low'},
    },
    'vacuum-analytics-tables': {
        'task': 'tasks.cleanup_tasks.vacuum_analytics_tables',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # BACKUP (daily)
    # ══════════════════════════════════════════════════════════════
    'backup-database': {
        'task': 'tasks.backup_tasks.backup_database',
        'schedule': crontab(minute=0, hour=1),  # 1am daily
        'kwargs': {'compress': True, 'upload_to_s3': True},
        'options': {'queue': 'low'},
    },
    'backup-media-files': {
        'task': 'tasks.backup_tasks.backup_media_files',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Weekly
        'options': {'queue': 'low'},
    },
    'cleanup-old-backups': {
        'task': 'tasks.backup_tasks.cleanup_old_backups',
        'schedule': crontab(minute=0, hour=6, day_of_week=0),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # COST ESTIMATION (daily)
    # ══════════════════════════════════════════════════════════════
    'run-cost-estimation': {
        'task': 'tasks.celery_tasks.run_cost_estimation',
        'schedule': crontab(minute=0, hour=6),
        'options': {'queue': 'low'},
    },
    'dlq-summary-email': {
        'task': 'tasks.celery_tasks.send_dlq_summary_email',
        'schedule': crontab(minute=0, hour=9),  # 9am daily
        'options': {'queue': 'emails'},
    },

    # ══════════════════════════════════════════════════════════════
    # EARNINGS (daily)
    # ══════════════════════════════════════════════════════════════
    'calculate-daily-earnings': {
        'task': 'tasks.earning_tasks.calculate_daily_user_earnings',
        'schedule': crontab(minute=10, hour=0),
        'options': {'queue': 'default'},
    },
    'distribute-daily-bonuses': {
        'task': 'tasks.earning_tasks.distribute_bonus_rewards',
        'schedule': crontab(minute=30, hour=0),
        'kwargs': {'bonus_type': 'daily'},
        'options': {'queue': 'payments'},
    },
    'distribute-weekly-bonuses': {
        'task': 'tasks.earning_tasks.distribute_bonus_rewards',
        'schedule': crontab(minute=0, hour=1, day_of_week=1),
        'kwargs': {'bonus_type': 'weekly'},
        'options': {'queue': 'payments'},
    },
    'recalculate-leaderboard': {
        'task': 'tasks.earning_tasks.recalculate_leaderboard',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'cpalead-calculate-payouts': {
        'task': 'tasks.cpalead_tasks.cpalead_calculate_payouts',
        'schedule': crontab(minute=0, hour=2),  # 2am daily
        'kwargs': {'period': 'daily'},
        'options': {'queue': 'payments'},
    },

    # ══════════════════════════════════════════════════════════════
    # FRAUD MODEL TRAINING (weekly)
    # ══════════════════════════════════════════════════════════════
    'retrain-fraud-model': {
        'task': 'tasks.ml_tasks.retrain_fraud_model',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),
        'options': {'queue': 'ml'},
    },
    'update-fraud-models': {
        'task': 'tasks.fraud_detection_tasks.update_fraud_models',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),
        'options': {'queue': 'ml'},
    },

    # ══════════════════════════════════════════════════════════════
    # INTEGRATION & DATA PIPELINE (every 5-15 minutes)
    # ══════════════════════════════════════════════════════════════
    'sync-offer-data-bridge': {
        'task': 'tasks.data_pipeline_tasks.sync_offer_data_bridge',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },
    'sync-platform-kpis-bridge': {
        'task': 'tasks.data_pipeline_tasks.sync_platform_kpis_bridge',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default'},
    },
    'warm-all-caches': {
        'task': 'tasks.data_pipeline_tasks.warm_all_caches',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'etl-s3-export': {
        'task': 'tasks.data_pipeline_tasks.export_to_s3',
        'schedule': crontab(minute=30, hour=1),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # RTB SYSTEM (every 30 seconds → every 1 minute)
    # ══════════════════════════════════════════════════════════════
    'rtb-refresh-bid-cache': {
        'task': 'tasks.rtb_tasks.refresh_bid_cache',
        'schedule': crontab(minute='*/1'),
        'options': {'queue': 'high', 'expires': 55},
    },
    'rtb-update-floor-prices': {
        'task': 'tasks.rtb_tasks.update_bid_floor_prices',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },
    'rtb-rank-advertisers': {
        'task': 'tasks.rtb_tasks.rank_advertisers_by_epc',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'rtb-detect-ivt': {
        'task': 'tasks.rtb_tasks.detect_invalid_traffic',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'high'},
    },
    'rtb-daily-report': {
        'task': 'tasks.rtb_tasks.generate_rtb_report',
        'schedule': crontab(minute=40, hour=0),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # CONTENT LOCKER (every 10 minutes)
    # ══════════════════════════════════════════════════════════════
    'rotate-locker-offers': {
        'task': 'tasks.content_locker_tasks.rotate_locker_offers',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default'},
    },
    'cleanup-locker-tokens': {
        'task': 'tasks.content_locker_tasks.cleanup_expired_unlock_tokens',
        'schedule': crontab(minute=0, hour=3),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # CPI/CPC (every 5 minutes)
    # ══════════════════════════════════════════════════════════════
    'sync-mmp-installs': {
        'task': 'tasks.cpi_tasks.sync_mmp_install_data',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'high'},
    },
    'detect-install-fraud': {
        'task': 'tasks.cpi_tasks.detect_install_fraud',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'high'},
    },
    'cpi-daily-report': {
        'task': 'tasks.cpi_tasks.generate_cpi_report',
        'schedule': crontab(minute=45, hour=0),
        'options': {'queue': 'reports'},
    },
    'cpc-daily-report': {
        'task': 'tasks.cpc_tasks.generate_cpc_report',
        'schedule': crontab(minute=50, hour=0),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # VIRTUAL CURRENCY (every hour)
    # ══════════════════════════════════════════════════════════════
    'sync-vc-exchange-rates': {
        'task': 'tasks.virtual_currency_tasks.sync_vc_exchange_rates',
        'schedule': crontab(minute=30, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'expire-old-vc': {
        'task': 'tasks.virtual_currency_tasks.expire_old_virtual_currency',
        'schedule': crontab(minute=0, hour=3, day_of_month=1),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # DAILY PAYOUT SYSTEM (daily at configurable time)
    # ══════════════════════════════════════════════════════════════
    'daily-payout-cycle': {
        'task': 'tasks.daily_payout_tasks.run_daily_payout_cycle',
        'schedule': crontab(minute=0, hour=12),  # Noon UTC daily
        'options': {'queue': 'payments'},
    },
    'verify-payout-methods': {
        'task': 'tasks.daily_payout_tasks.verify_payout_methods',
        'schedule': crontab(minute=0, hour=10),
        'options': {'queue': 'default'},
    },
    'handle-payout-failures': {
        'task': 'tasks.daily_payout_tasks.handle_payout_failures',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'payments'},
    },
    'daily-payout-report': {
        'task': 'tasks.daily_payout_tasks.generate_daily_payout_report',
        'schedule': crontab(minute=55, hour=23),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # TRAFFIC QUALITY (every 6 hours)
    # ══════════════════════════════════════════════════════════════
    'score-publisher-traffic': {
        'task': 'tasks.traffic_quality_tasks.score_publisher_traffic',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },
    'detect-proxy-traffic': {
        'task': 'tasks.traffic_quality_tasks.detect_proxy_traffic',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'high'},
    },
    'update-traffic-tiers': {
        'task': 'tasks.traffic_quality_tasks.update_traffic_tiers',
        'schedule': crontab(minute=0, hour='*/12'),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # WEBHOOK SYSTEM (every 15 minutes)
    # ══════════════════════════════════════════════════════════════
    'retry-failed-webhooks': {
        'task': 'tasks.webhook_tasks.retry_failed_webhooks',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'default'},
    },
    'cleanup-webhook-logs': {
        'task': 'tasks.webhook_tasks.cleanup_old_webhook_logs',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # A/B TESTING (hourly analysis)
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    # COMPLIANCE (daily)
    # ══════════════════════════════════════════════════════════════
    'check-data-retention': {
        'task': 'tasks.compliance_tasks.check_data_retention_policies',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),
        'options': {'queue': 'low'},
    },
    'anonymize-old-data': {
        'task': 'tasks.compliance_tasks.anonymize_old_user_data',
        'schedule': crontab(minute=0, hour=3, day_of_month=1),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # EMAIL DRIP (every 30 minutes)
    # ══════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════
    # IP MANAGEMENT (hourly)
    # ══════════════════════════════════════════════════════════════
    'sync-ip-blacklist': {
        'task': 'tasks.ip_management_tasks.sync_ip_blacklist',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'high'},
    },
    'update-geo-routing': {
        'task': 'tasks.ip_management_tasks.update_geo_routing_table',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'refresh-ip-intelligence': {
        'task': 'tasks.ip_management_tasks.refresh_ip_intelligence',
        'schedule': crontab(minute=0, hour=6, day_of_week=0),
        'options': {'queue': 'low'},
    },
    'geo-daily-report': {
        'task': 'tasks.ip_management_tasks.generate_geo_report',
        'schedule': crontab(minute=55, hour=0),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # SEARCH INDEX (daily rebuild)
    # ══════════════════════════════════════════════════════════════
    'rebuild-search-index-full': {
        'task': 'tasks.search_tasks.rebuild_search_index',
        'schedule': crontab(minute=0, hour=5, day_of_week=1),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # AFFILIATE (daily)
    # ══════════════════════════════════════════════════════════════
    'sync-affiliate-networks': {
        'task': 'tasks.affiliate_tasks.sync_affiliate_networks',
        'schedule': crontab(minute=0, hour=7),
        'options': {'queue': 'default'},
    },
    'validate-affiliate-links': {
        'task': 'tasks.affiliate_tasks.validate_affiliate_links',
        'schedule': crontab(minute=0, hour=8),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # REFUND & CHARGEBACK (every 30 minutes)
    # ══════════════════════════════════════════════════════════════
    'refund-daily-report': {
        'task': 'tasks.refund_tasks.generate_refund_report',
        'schedule': crontab(minute=50, hour=23),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # SURVEY (every 4 hours)
    # ══════════════════════════════════════════════════════════════
    'survey-daily-report': {
        'task': 'tasks.survey_tasks.generate_survey_report',
        'schedule': crontab(minute=35, hour=0),
        'options': {'queue': 'reports'},
    },

    # ══════════════════════════════════════════════════════════════
    # SESSION CLEANUP (daily)
    # ══════════════════════════════════════════════════════════════
    'cleanup-sessions': {
        'task': 'tasks.session_tasks.cleanup_expired_sessions',
        'schedule': crontab(minute=0, hour=2),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # EXPIRY TASKS (daily)
    # ══════════════════════════════════════════════════════════════
    'cleanup-expired-ips': {
        'task': 'tasks.expiry_tasks.cleanup_expired_ips_task',
        'schedule': crontab(minute=0, hour=4),
        'options': {'queue': 'low'},
    },
    'deactivate-old-ips': {
        'task': 'tasks.expiry_tasks.deactivate_old_ips_task',
        'schedule': crontab(minute=30, hour=4),
        'options': {'queue': 'low'},
    },

    # ══════════════════════════════════════════════════════════════
    # ADVERTISER (daily billing/reports)
    # ══════════════════════════════════════════════════════════════
    'verify-advertiser-postbacks': {
        'task': 'tasks.advertiser_tasks.verify_advertiser_postbacks',
        'schedule': crontab(minute=0, hour=6),
        'options': {'queue': 'default'},
    },
    'auto-approve-campaigns': {
        'task': 'tasks.advertiser_tasks.auto_approve_campaigns',
        'schedule': crontab(minute=0, hour=9),
        'options': {'queue': 'default'},
    },

    # ══════════════════════════════════════════════════════════════
    # GAMIFICATION (daily challenges)
    # ══════════════════════════════════════════════════════════════
    'update-global-leaderboard-all': {
        'task': 'tasks.gamification_tasks.update_global_leaderboard',
        'schedule': crontab(minute='*/15'),
        'kwargs': {'periods': ['daily', 'weekly', 'monthly', 'alltime']},
        'options': {'queue': 'default'},
    },

    # New tasks added in final session
    # Overlay Locker
    'expire-overlay-sessions': {
        'task': 'tasks.overlay_locker_tasks.expire_overlay_sessions',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'low'},
    },
    'overlay-daily-report': {
        'task': 'tasks.overlay_locker_tasks.generate_overlay_report',
        'schedule': crontab(minute=52, hour=0),
        'options': {'queue': 'reports'},
    },
    # Ad Units
    'update-ad-ppc-rates': {
        'task': 'tasks.ad_unit_tasks.update_ad_cpm_rates',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'high', 'expires': 290},
    },
    'rotate-ad-creatives': {
        'task': 'tasks.ad_unit_tasks.rotate_ad_creatives',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'default'},
    },
    'score-ad-quality': {
        'task': 'tasks.ad_unit_tasks.score_ad_quality',
        'schedule': crontab(minute=0, hour='*/12'),
        'options': {'queue': 'default'},
    },
    'ad-daily-report': {
        'task': 'tasks.ad_unit_tasks.generate_ad_report',
        'schedule': crontab(minute=53, hour=0),
        'options': {'queue': 'reports'},
    },
    'cleanup-old-impressions': {
        'task': 'tasks.ad_unit_tasks.cleanup_old_impressions',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),
        'options': {'queue': 'low'},
    },
    # Email Submit
    'detect-email-submit-fraud': {
        'task': 'tasks.email_submit_tasks.detect_email_fraud',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'high'},
    },
    'email-submit-daily-report': {
        'task': 'tasks.email_submit_tasks.generate_email_submit_report',
        'schedule': crontab(minute=54, hour=0),
        'options': {'queue': 'reports'},
    },
    # Community
    'update-community-leaderboard': {
        'task': 'tasks.community_tasks.update_community_leaderboard',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'default'},
    },
    'send-community-digest': {
        'task': 'tasks.community_tasks.send_community_digest',
        'schedule': crontab(minute=0, hour=9, day_of_week=1),
        'options': {'queue': 'emails'},
    },
    'reset-monthly-community-points': {
        'task': 'tasks.community_tasks.reset_monthly_points',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),
        'options': {'queue': 'default'},
    },
    # API Keys
    'rotate-api-keys': {
        'task': 'tasks.api_key_tasks.rotate_api_keys',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),
        'options': {'queue': 'low'},
    },
    # Self-serve Campaigns
    'auto-optimize-campaigns': {
        'task': 'tasks.self_serve_campaign_tasks.auto_optimize_campaign',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'default'},
    },
    # Crypto
    'sync-crypto-rates': {
        'task': 'tasks.crypto_payout_tasks.sync_crypto_exchange_rates',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default', 'expires': 290},
    },
    'monitor-crypto-txns': {
        'task': 'tasks.crypto_payout_tasks.monitor_crypto_transactions',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'high'},
    },
    'crypto-daily-report': {
        'task': 'tasks.crypto_payout_tasks.generate_crypto_payout_report',
        'schedule': crontab(minute=56, hour=0),
        'options': {'queue': 'reports'},
    },

    # Personality Quiz
    'detect-quiz-fraud': {
        'task': 'tasks.personality_quiz_tasks.detect_quiz_fraud',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'high'},
    },
    'sync-quiz-inventory': {
        'task': 'tasks.personality_quiz_tasks.sync_quiz_inventory',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'default'},
    },
    'quiz-daily-report': {
        'task': 'tasks.personality_quiz_tasks.generate_quiz_report',
        'schedule': crontab(minute=57, hour=0),
        'options': {'queue': 'reports'},
    },
    # Metaverse
    'sync-metaverse-rates': {
        'task': 'tasks.metaverse_tasks.sync_metaverse_exchange_rates',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default', 'expires': 290},
    },
    'metaverse-daily-report': {
        'task': 'tasks.metaverse_tasks.generate_metaverse_report',
        'schedule': crontab(minute=58, hour=0),
        'options': {'queue': 'reports'},
    },
    # Macro Tracking
    'sync-tracking-platforms': {
        'task': 'tasks.macro_tracking_tasks.sync_tracking_platforms',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'default'},
    },
    'macro-daily-report': {
        'task': 'tasks.macro_tracking_tasks.generate_macro_report',
        'schedule': crontab(minute=59, hour=0),
        'options': {'queue': 'reports'},
    },
}
