# cms/INTEGRATION_SYSTEM/integ_constants.py
"""CMS Integration System — Event Type Constants."""


class CMSEvents:
    """All event type string constants used across the CMS."""

    # ── Rewards ───────────────────────────────────────────────────────────────
    REWARD_EARNED        = 'reward_earned'
    REWARD_APPROVED      = 'reward_approved'
    REWARD_PAID          = 'reward_paid'
    REWARD_POOL_LOW      = 'reward_pool_low'
    REWARD_POOL_REFILLED = 'reward_pool_refilled'
    REWARD_TX_CREATED    = 'reward_transaction_created'

    # ── Offers ────────────────────────────────────────────────────────────────
    OFFER_COMPLETED      = 'offer_completed'
    OFFER_CLICKED        = 'offer_clicked'
    CONTENT_LOCKED       = 'content_locked'
    CONTENT_UNLOCKED     = 'content_unlocked'
    POSTBACK_RECEIVED    = 'postback_received'
    POSTBACK_APPROVED    = 'postback_approved'
    POSTBACK_REJECTED    = 'postback_rejected'

    # ── Surveys ───────────────────────────────────────────────────────────────
    SURVEY_STARTED       = 'survey_started'
    SURVEY_COMPLETED     = 'survey_completed'
    SURVEY_RESPONSE      = 'survey_response_submitted'
    SURVEY_QUALITY       = 'survey_quality_updated'
    SURVEY_CREATED       = 'survey_created'
    SURVEY_UPDATED       = 'survey_updated'
    SURVEY_DELETED       = 'survey_deleted'

    # ── Tasks ─────────────────────────────────────────────────────────────────
    TASK_STARTED         = 'task_started'
    TASK_COMPLETED       = 'task_completed'
    TASK_FAILED          = 'task_failed'
    TASK_SCHEDULED       = 'task_scheduled'
    TASK_QUEUE_UPDATED   = 'task_queue_updated'
    TASK_TIMEOUT         = 'task_timeout'

    # ── Users ─────────────────────────────────────────────────────────────────
    USER_REGISTERED      = 'user_registered'
    USER_LOGIN           = 'user_login'
    USER_LOGOUT          = 'user_logout'
    USER_LEVEL_UP        = 'user_level_up'
    PROFILE_UPDATED      = 'profile_updated'
    SEGMENT_CHANGED      = 'user_segment_changed'

    # ── Withdrawals ───────────────────────────────────────────────────────────
    WITHDRAWAL_REQUESTED = 'withdrawal_requested'
    WITHDRAWAL_APPROVED  = 'withdrawal_approved'
    WITHDRAWAL_PAID      = 'withdrawal_paid'
    WITHDRAWAL_REJECTED  = 'withdrawal_rejected'

    # ── Gamification ─────────────────────────────────────────────────────────
    QUIZ_COMPLETED       = 'quiz_completed'
    REFERRAL_BONUS       = 'referral_bonus'
    STREAK_MILESTONE     = 'streak_milestone'

    # ── Content ───────────────────────────────────────────────────────────────
    BLOG_PUBLISHED       = 'blog_post_published'
    PAGE_PUBLISHED       = 'page_published'
    PAGE_UNPUBLISHED     = 'page_unpublished'

    # ── System ────────────────────────────────────────────────────────────────
    CACHE_INVALIDATED    = 'cache_invalidated'
    WEBHOOK_TRIGGERED    = 'webhook_triggered'
    ERROR_OCCURRED       = 'error_occurred'
    PERF_ALERT           = 'performance_alert'
    MAINTENANCE_START    = 'system_maintenance_started'
    MAINTENANCE_END      = 'system_maintenance_ended'

    # ── Analytics ─────────────────────────────────────────────────────────────
    ANALYTICS_UPDATED    = 'analytics_updated'
    REPORT_GENERATED     = 'report_generated'
    DASHBOARD_UPDATED    = 'dashboard_data_updated'
    METRICS_COLLECTED    = 'metrics_collected'

    # ── Notifications ─────────────────────────────────────────────────────────
    NOTIFICATION_CREATED = 'notification_created'
    NOTIFICATION_READ    = 'notification_read'
    BULK_NOTIF_SENT      = 'bulk_notification_sent'

    @classmethod
    def all_events(cls):
        return [v for k, v in vars(cls).items()
                if not k.startswith('_') and isinstance(v, str)]
