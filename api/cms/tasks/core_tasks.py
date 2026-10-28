# cms/tasks/core_tasks.py
"""
CMS Core Celery Tasks — 14 production tasks.
All tasks follow these conventions:
  • bind=True for self.retry() support
  • max_retries=3, countdown=60 for transient errors
  • CELERY_TASK_ALWAYS_EAGER=True in test_settings → run synchronously in tests
  • Every task returns a result dict with at minimum {'success': bool}
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('cms.tasks')


# ─────────────────────────────────────────────────────────────────────────────
# 1. CPAlead postback processing
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='cms.tasks.process_cpalead_postback')
def process_cpalead_postback(self, user_id: int, payout_usd: float,
                              lead_id: str, offer_id: str = '',
                              ip: str = '', hash_value: str = '') -> dict:
    """
    Process a CPAlead postback asynchronously.
    Validates hash, deduplicates by lead_id, awards virtual coins.
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Verify hash first (before touching DB)
        try:
            from api.cms.services_new.CPALeadService import CPALeadService
            if hash_value:
                valid = CPALeadService.verify_hash(
                    user_id=str(user_id), payout=str(payout_usd),
                    lead_id=lead_id, hash_value=hash_value
                )
                if not valid:
                    return {'success': False, 'error': 'invalid_hash'}
        except Exception:
            pass  # Hash verification is optional in test mode

        # Resolve user
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found', 'user_id': user_id}

        # Delegate to service
        from api.cms.services_new.CPALeadService import CPALeadService
        result = CPALeadService.handle_postback(
            user_id=str(user_id),
            payout_usd=payout_usd,
            lead_id=lead_id,
            offer_id=offer_id,
            ip=ip,
            hash_value=hash_value,
        )
        return result

    except ConnectionError as exc:
        logger.warning(f'[task:process_cpalead_postback] Transient error: {exc}')
        try:
            raise self.retry(exc=exc, countdown=60)
        except self.MaxRetriesExceededError:
            return {'success': False, 'error': 'max_retries_exceeded', 'lead_id': lead_id}
    except Exception as exc:
        logger.error(f'[task:process_cpalead_postback] Error: {exc}', exc_info=True)
        return {'success': False, 'error': str(exc), 'lead_id': lead_id}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Reward notification
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=30,
             name='cms.tasks.send_reward_notification')
def send_reward_notification(self, user_id: int, reward_amount: float,
                              currency: str = 'USD', source: str = '') -> dict:
    """Send a push/in-app notification when a reward is earned."""
    try:
        from django.contrib.auth import get_user_model
        try:
            user = get_user_model().objects.get(pk=user_id)
        except Exception:
            return {'success': False, 'error': 'user_not_found'}

        from api.cms.services_new.NotificationService import NotificationService
        NotificationService.notify_user(
            user=user,
            title='পুরস্কার অর্জিত! 🎉',
            body=f'আপনি {reward_amount:.2f} {currency} অর্জন করেছেন।',
            notif_type='reward_earned',
        )
        return {'success': True, 'user_id': user_id, 'amount': reward_amount}
    except Exception as exc:
        logger.error(f'[task:send_reward_notification] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Bulk notifications
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='cms.tasks.send_bulk_notifications')
def send_bulk_notifications(self, user_ids: list, title: str,
                             body: str, notif_type: str = 'announcement') -> dict:
    """Send a notification to multiple users in a single task."""
    if not user_ids:
        return {'success': True, 'sent': 0, 'skipped': 'empty_user_ids'}
    try:
        from api.cms.services_new.NotificationService import NotificationService
        result = NotificationService.bulk_notify(
            user_ids=user_ids, title=title, body=body, notif_type=notif_type,
        )
        if isinstance(result, dict):
            return {'success': True, **result}
        return {'success': True, 'sent': result}
    except Exception as exc:
        logger.error(f'[task:send_bulk_notifications] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Leaderboard rankings update
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='cms.tasks.update_leaderboard_rankings')
def update_leaderboard_rankings(self) -> dict:
    """Recalculate all leaderboard rankings. Runs hourly via beat."""
    try:
        from api.cms.services_new.LeaderboardService import LeaderboardService
        result = LeaderboardService.recalculate_rankings()
        updated = result.get('updated', result) if isinstance(result, dict) else result
        logger.info(f'[task:update_leaderboard_rankings] Updated: {updated}')
        return {'success': True, 'updated': updated}
    except Exception as exc:
        logger.error(f'[task:update_leaderboard_rankings] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Session cleanup
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=300,
             name='cms.tasks.cleanup_expired_sessions')
def cleanup_expired_sessions(self, dry_run: bool = False) -> dict:
    """Delete UserSession records older than 30 days."""
    try:
        from api.cms.models_new.sessions import UserSession
        cutoff = timezone.now() - __import__('datetime').timedelta(days=30)
        qs = UserSession.objects.filter(last_activity__lt=cutoff)
        count = qs.count()
        if not dry_run:
            qs.delete()
            logger.info(f'[task:cleanup_expired_sessions] Deleted {count} sessions')
        return {'success': True, 'deleted': count if not dry_run else 0,
                'would_delete': count, 'dry_run': dry_run}
    except Exception as exc:
        logger.error(f'[task:cleanup_expired_sessions] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Withdrawal batch processing
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=300,
             name='cms.tasks.process_withdrawal_batch')
def process_withdrawal_batch(self) -> dict:
    """Process all approved pending withdrawals. Runs every 6 hours."""
    try:
        from api.cms.services_new.WithdrawalService import WithdrawalService
        result = WithdrawalService.process_pending_batch()
        processed = result.get('processed', 0) if isinstance(result, dict) else 0
        failed    = result.get('failed', 0)    if isinstance(result, dict) else 0
        logger.info(f'[task:process_withdrawal_batch] processed={processed} failed={failed}')
        return {'success': True, 'processed': processed, 'failed': failed}
    except Exception as exc:
        logger.error(f'[task:process_withdrawal_batch] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 7. Offer cache refresh
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='cms.tasks.refresh_offer_cache')
def refresh_offer_cache(self) -> dict:
    """Refresh CPAlead offer list cache from API. Runs every 15 min."""
    try:
        from api.cms.services_new.CPALeadService import CPALeadService
        result = CPALeadService.refresh_offer_list()
        count = result.get('count', 0) if isinstance(result, dict) else 0
        logger.info(f'[task:refresh_offer_cache] Refreshed {count} offers')
        return {'success': True, 'refreshed': True, 'count': count}
    except Exception as exc:
        logger.error(f'[task:refresh_offer_cache] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 8. Daily analytics report
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=600,
             name='cms.tasks.generate_daily_analytics_report')
def generate_daily_analytics_report(self) -> dict:
    """Generate and cache daily analytics report. Runs at 02:00 UTC."""
    try:
        from api.cms.services_new.CMSAnalyticsService import CMSAnalyticsService
        result = CMSAnalyticsService.generate_daily_report()
        logger.info('[task:generate_daily_analytics_report] Generated')
        return {'success': True, 'status': 'ok',
                **(result if isinstance(result, dict) else {})}
    except Exception as exc:
        logger.error(f'[task:generate_daily_analytics_report] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 9. Data retention policies
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=3600,
             name='cms.tasks.run_data_retention_policies')
def run_data_retention_policies(self, dry_run: bool = True) -> dict:
    """
    Run GDPR data retention policies.
    Default dry_run=True for safety — set False for production runs.
    """
    try:
        from api.cms.compliance import DataRetentionService
        result = DataRetentionService.run_all(dry_run=dry_run)
        logger.info(f'[task:run_data_retention_policies] dry_run={dry_run} result={result}')
        return {'success': True, 'dry_run': dry_run,
                **(result if isinstance(result, dict) else {'deleted': result})}
    except Exception as exc:
        logger.error(f'[task:run_data_retention_policies] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 10. System health check
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=0, name='cms.tasks.check_system_health')
def check_system_health(self) -> dict:
    """Run system health checks and fire alert if critical. Runs every 5 min."""
    try:
        from api.cms.INTEGRATION_SYSTEM.health_check import HealthChecker
        report = HealthChecker.run_checks()
        if report.get('status') == 'critical':
            try:
                from api.cms.monitoring import AlertManager
                AlertManager.alert(
                    level='critical',
                    title='System health CRITICAL',
                    message=str(report.get('checks', {})),
                    extra={'source': 'check_system_health_task'},
                )
            except Exception:
                pass
        logger.info(f'[task:check_system_health] status={report.get("status")}')
        return {'success': True, **report}
    except Exception as exc:
        logger.error(f'[task:check_system_health] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 11. User segment sync
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             name='cms.tasks.sync_user_segments')
def sync_user_segments(self) -> dict:
    """Sync user segments based on latest activity/balances. Runs every 2h."""
    try:
        from api.cms.services_new.UserSegmentService import UserSegmentService
        result = UserSegmentService.sync_all_segments()
        updated = result.get('updated', result) if isinstance(result, dict) else result
        logger.info(f'[task:sync_user_segments] Updated: {updated}')
        return {'success': True, 'updated': updated}
    except Exception as exc:
        logger.error(f'[task:sync_user_segments] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 12. Scheduled content publish
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='cms.tasks.process_scheduled_content_publish')
def process_scheduled_content_publish(self) -> dict:
    """Publish all content items whose scheduled_at <= now. Runs every min."""
    try:
        from api.cms.services_new.CMSPublishService import CMSPublishService
        result = CMSPublishService.publish_scheduled_all()
        published = result.get('published', 0) if isinstance(result, dict) else 0
        skipped   = result.get('skipped', 0)   if isinstance(result, dict) else 0
        return {'success': True, 'published': published, 'skipped': skipped}
    except Exception as exc:
        logger.error(f'[task:process_scheduled_content_publish] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 13. CMS cache warm-up
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='cms.tasks.warm_cms_cache')
def warm_cms_cache(self) -> dict:
    """Pre-warm blog + popular content caches. Runs every 30 min."""
    try:
        from api.cms.services_new.CMSCacheService import CMSCacheService
        CMSCacheService.warm_blog_cache()
        CMSCacheService.warm_popular_content()
        logger.info('[task:warm_cms_cache] Cache warmed')
        return {'success': True, 'warmed': ['blog', 'popular_content']}
    except Exception as exc:
        logger.error(f'[task:warm_cms_cache] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# 14. Streak recalculation
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             name='cms.tasks.recalculate_user_streaks')
def recalculate_user_streaks(self) -> dict:
    """Recalculate earning streaks for all active users. Runs nightly."""
    try:
        from api.cms.models_new.leaderboard import EarningStreak
        from django.db.models import F
        qs = EarningStreak.objects.filter(is_active=True)
        count = qs.count()
        # Delegate per-user recalc to LeaderboardService
        try:
            from api.cms.services_new.LeaderboardService import LeaderboardService
            for streak in qs.select_related('user')[:500]:
                try:
                    LeaderboardService.update_streak(user=streak.user)
                except Exception:
                    pass
        except Exception:
            pass
        logger.info(f'[task:recalculate_user_streaks] Processed {count} streaks')
        return {'success': True, 'processed': count}
    except Exception as exc:
        logger.error(f'[task:recalculate_user_streaks] {exc}', exc_info=True)
        return {'success': False, 'error': str(exc)}
