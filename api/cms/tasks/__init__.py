# api/cms/tasks/__init__.py
"""
CMS Celery Tasks Package
"""
from .sitemap_tasks import regenerate_sitemap
from .media_variant_tasks import generate_media_variants, regenerate_missing_variants
from .cdn_push_tasks import push_file_to_cdn, push_all_unpushed_to_cdn
from .popup_stats_tasks import aggregate_popup_stats, cleanup_old_popup_stats
from .blog_analytics_tasks import collect_blog_analytics, update_blog_view_counts
from .seo_audit_tasks import run_seo_audit, auto_fill_missing_seo
from .cache_invalidation_tasks import invalidate_blog_post_cache, invalidate_all_cms_caches, warm_blog_cache
from .redirect_cleanup_tasks import cleanup_unused_redirects, cleanup_expired_redirects
from .media_cleanup_tasks import delete_orphaned_media, update_folder_stats
from .content_publish_tasks import publish_scheduled_content, expire_old_content, deactivate_expired_banners
from .survey_tasks import (
    process_survey_rewards,
    update_survey_analytics,
    cleanup_expired_surveys,
    update_user_segments,
    send_survey_recommendations,
    generate_survey_report,
    validate_survey_quality,
    sync_survey_caches,
)

__all__ = [
    # Sitemap
    'regenerate_sitemap',
    # Media variants
    'generate_media_variants', 'regenerate_missing_variants',
    # CDN
    'push_file_to_cdn', 'push_all_unpushed_to_cdn',
    # Popup stats
    'aggregate_popup_stats', 'cleanup_old_popup_stats',
    # Blog analytics
    'collect_blog_analytics', 'update_blog_view_counts',
    # SEO
    'run_seo_audit', 'auto_fill_missing_seo',
    # Cache
    'invalidate_blog_post_cache', 'invalidate_all_cms_caches', 'warm_blog_cache',
    # Redirects
    'cleanup_unused_redirects', 'cleanup_expired_redirects',
    # Media cleanup
    'delete_orphaned_media', 'update_folder_stats',
    # Content publish
    'publish_scheduled_content', 'expire_old_content', 'deactivate_expired_banners',
    # Survey tasks
    'process_survey_rewards', 'update_survey_analytics', 'cleanup_expired_surveys',
    'update_user_segments', 'send_survey_recommendations', 'generate_survey_report',
    'validate_survey_quality', 'sync_survey_caches',
]

# ── Notification & CPAlead Tasks ──────────────────────────────────
from .notification_tasks import (
    send_notification,
    broadcast_announcement_task,
    cleanup_old_notifications,
    send_email_template,
    process_daily_earning_rewards,
    daily_earning_cap_reset,
    cpalead_sync,
    cleanup_expired_popup_dismissals,
)

# ── Safe Celery app shim for test environments ────────────────────
try:
    from celery import current_app as app
    app.config_from_object('django.conf:settings', namespace='CELERY')
except Exception:
    # Fallback stub when Celery is not configured (test env)
    class _AppStub:
        def task(self, *a, **kw):
            def decorator(fn):
                return fn
            return decorator
    app = _AppStub()
# ─────────────────────────────────────────────────────────────────


# ── Referral + Leaderboard + Streak tasks ────────────────────────
@app.task(name='cms.tasks.refresh_leaderboard')
def refresh_leaderboard():
    from api.cms.services_new.LeaderboardService import LeaderboardService
    for period in ['daily', 'weekly', 'monthly']:
        for cat in ['earnings', 'coins', 'offers']:
            try:
                LeaderboardService.refresh_ranks(period, cat)
            except Exception:
                pass
    return "done"

@app.task(name='cms.tasks.reset_broken_streaks')
def reset_broken_streaks():
    from api.cms.services_new.LeaderboardService import StreakService
    count = StreakService.reset_broken_streaks()
    return f"Reset {count} broken streaks"

@app.task(name='cms.tasks.sync_offer_cache')
def sync_offer_cache():
    """Refresh CPAlead offer cache from API."""
    from api.cms.services_new.CPALeadService import CPALeadService
    try:
        CPALeadService.fetch_offers(limit=100)
        return "Offer cache synced"
    except Exception as e:
        return f"Error: {e}"

# ── Core Tasks (14 missing tasks — added by v9 fix) ───────────────────────────
from .core_tasks import (
    process_cpalead_postback,
    send_reward_notification,
    send_bulk_notifications,
    update_leaderboard_rankings,
    cleanup_expired_sessions,
    process_withdrawal_batch,
    refresh_offer_cache,
    generate_daily_analytics_report,
    run_data_retention_policies,
    check_system_health,
    sync_user_segments,
    process_scheduled_content_publish,
    warm_cms_cache,
    recalculate_user_streaks,
)
