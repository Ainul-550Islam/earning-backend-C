# api/offer_inventory/tasks.py
"""
Celery Async Tasks।
সব heavy/delayed কাজ এখানে।
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(queue='postback', bind=True, max_retries=5, default_retry_delay=300)
def deliver_postback(self, conversion_id: str, retry: int = 0):
    """Conversion postback network-এ পাঠাও।"""
    try:
        from .services import PostbackService
        result = PostbackService.deliver(conversion_id, retry)
        if result:
            logger.info(f'Postback delivered: {conversion_id}')
        return result
    except Exception as exc:
        logger.error(f'Postback task error: {exc}')
        raise self.retry(exc=exc, countdown=300 * (retry + 1))


@shared_task(queue='analytics')
def update_daily_stats(conversion_id: str):
    """Daily stats আপডেট।"""
    try:
        from .models import Conversion
        from .repository import AnalyticsRepository
        conversion = Conversion.objects.select_related('offer', 'status').get(id=conversion_id)
        date   = conversion.created_at.date()
        tenant = conversion.tenant

        AnalyticsRepository.upsert_daily_stat(
            date=date,
            tenant=tenant,
            total_conversions=1,
            total_revenue=float(conversion.payout_amount),
            user_payouts=float(conversion.reward_amount),
            platform_profit=float(conversion.payout_amount - conversion.reward_amount),
        )
        # Invalidate dashboard cache
        cache.delete(f'dashboard_stats:{tenant}')
    except Exception as e:
        logger.error(f'update_daily_stats error: {e}')


@shared_task(queue='analytics')
def compute_click_daily_stats():
    """আজকের click stats compute।"""
    from .models import Click, DailyStat
    from django.db.models import Count
    today = timezone.now().date()
    data = Click.objects.filter(created_at__date=today).aggregate(
        total=Count('id'),
        unique=Count('ip_address', distinct=True),
        fraud=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(is_fraud=True)),
    )
    DailyStat.objects.filter(date=today).update(
        total_clicks =data['total']  or 0,
        unique_clicks=data['unique'] or 0,
        fraud_attempts=data['fraud'] or 0,
    )


@shared_task(queue='default')
def auto_expire_offers():
    """মেয়াদোত্তীর্ণ অফার expire করো।"""
    from .repository import OfferRepository
    count = OfferRepository.auto_expire_offers()
    if count > 0:
        logger.info(f'{count} offers expired.')
    return count


@shared_task(queue='default')
def sync_offer_feeds():
    """External feed থেকে নতুন অফার pull করো।"""
    from .models import OfferInventorySource
    sources = OfferInventorySource.objects.filter(is_enabled=True)
    for source in sources:
        try:
            _sync_single_feed(source)
        except Exception as e:
            logger.error(f'Feed sync error ({source.id}): {e}')
            source.error_count += 1
            source.last_error = str(e)
            source.save(update_fields=['error_count', 'last_error'])


def _sync_single_feed(source):
    import requests
    resp = requests.get(source.feed_url, headers=source.auth_headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    count = 0
    for item in data.get('offers', []):
        from .models import Offer
        Offer.objects.update_or_create(
            external_offer_id=item.get('id', ''),
            network=source.network,
            defaults={
                'title'        : item.get('name', ''),
                'description'  : item.get('description', ''),
                'offer_url'    : item.get('url', ''),
                'payout_amount': item.get('payout', 0),
                'status'       : 'active',
            }
        )
        count += 1
    source.last_synced  = timezone.now()
    source.offers_pulled= count
    source.error_count  = 0
    source.save(update_fields=['last_synced', 'offers_pulled', 'error_count'])
    logger.info(f'Feed synced: {source.id} — {count} offers')


@shared_task(queue='fraud')
def run_fraud_scan():
    """Pending conversion-গুলো fraud check করো।"""
    from .models import Conversion
    from .services import FraudService
    pending = Conversion.objects.filter(
        status__name='pending',
        created_at__gte=timezone.now() - __import__('datetime').timedelta(hours=24)
    ).select_related('offer', 'user', 'click', 'status')[:200]

    for conv in pending:
        try:
            FraudService.auto_evaluate_and_act(conv)
        except Exception as e:
            logger.error(f'Fraud scan error ({conv.id}): {e}')


@shared_task(queue='payout')
def process_payout_batch(batch_id: str):
    """Payout batch process করো।"""
    from .models import PayoutBatch, WithdrawalRequest
    try:
        batch = PayoutBatch.objects.get(id=batch_id)
        batch.status     = 'processing'
        batch.started_at = timezone.now()
        batch.save()

        requests_qs = WithdrawalRequest.objects.filter(
            payout_batch=batch, status='approved'
        ).select_related('user', 'payment_method')

        for wr in requests_qs:
            try:
                # TODO: Integrate with actual payment gateway
                wr.status       = 'completed'
                wr.processed_at = timezone.now()
                wr.save()
                batch.processed_count += 1
            except Exception as e:
                logger.error(f'Payout error ({wr.id}): {e}')
                batch.failed_count += 1

        batch.status       = 'completed'
        batch.completed_at = timezone.now()
        batch.save()
    except Exception as e:
        logger.error(f'Batch error ({batch_id}): {e}')
        PayoutBatch.objects.filter(id=batch_id).update(status='failed')


@shared_task(queue='notification')
def send_bulk_notification(user_ids: list, title: str, body: str,
                           notif_type: str = 'info', action_url: str = ''):
    """Bulk notification পাঠাও।"""
    from .models import Notification
    notifications = [
        Notification(
            user_id=uid, notif_type=notif_type,
            title=title, body=body, action_url=action_url,
        )
        for uid in user_ids
    ]
    Notification.objects.bulk_create(notifications, batch_size=500)
    logger.info(f'Bulk notification sent to {len(user_ids)} users.')


@shared_task(queue='default')
def cleanup_expired_data():
    """পুরানো data cleanup।"""
    from .models import (
        Click, PostbackLog, AuditLog, RateLimitLog,
        HoneypotLog, PixelLog,
    )
    cutoff_90  = timezone.now() - __import__('datetime').timedelta(days=90)
    cutoff_30  = timezone.now() - __import__('datetime').timedelta(days=30)
    cutoff_7   = timezone.now() - __import__('datetime').timedelta(days=7)

    r1 = Click.objects.filter(is_fraud=True, created_at__lt=cutoff_90).delete()
    r2 = PostbackLog.objects.filter(is_success=True, created_at__lt=cutoff_30).delete()
    r3 = RateLimitLog.objects.filter(created_at__lt=cutoff_7).delete()
    r4 = HoneypotLog.objects.filter(created_at__lt=cutoff_30).delete()
    r5 = PixelLog.objects.filter(is_fired=True, created_at__lt=cutoff_30).delete()

    logger.info(f'Cleanup: clicks={r1[0]}, postbacks={r2[0]}, rate={r3[0]}, '
                f'honeypot={r4[0]}, pixel={r5[0]}')


@shared_task(queue='default')
def recalculate_churn_scores():
    """User churn probability update।"""
    from .models import ChurnRecord
    from django.contrib.auth import get_user_model
    User = get_user_model()
    cutoff = timezone.now() - __import__('datetime').timedelta(days=30)

    inactive_users = User.objects.filter(last_login__lt=cutoff)
    for user in inactive_users[:1000]:
        days_inactive = (timezone.now() - (user.last_login or user.date_joined)).days
        prob = min(1.0, days_inactive / 90)
        ChurnRecord.objects.update_or_create(
            user=user,
            defaults={
                'churn_probability': prob,
                'days_inactive'    : days_inactive,
                'last_active'      : user.last_login,
                'is_churned'       : prob > 0.8,
            }
        )


@shared_task(queue='default')
def ping_all_networks():
    """সব active network ping করো।"""
    from .models import OfferNetwork, NetworkPinger
    import requests as req
    networks = OfferNetwork.objects.filter(status='active')
    for network in networks:
        try:
            start = timezone.now()
            resp  = req.get(network.base_url, timeout=5)
            ms    = (timezone.now() - start).total_seconds() * 1000
            NetworkPinger.objects.create(
                network=network, response_code=resp.status_code,
                response_time=ms, is_up=resp.ok,
            )
        except Exception as e:
            NetworkPinger.objects.create(
                network=network, response_code=0,
                response_time=0, is_up=False, error_message=str(e),
            )


@shared_task(queue='analytics')
def compute_offer_conversion_rates():
    """প্রতিটি offer-এর CVR calculate করো।"""
    from .models import Offer
    from django.db.models import Count, F, FloatField, ExpressionWrapper
    offers = Offer.objects.filter(status='active').annotate(
        click_count=Count('clicks', distinct=True),
        conv_count =Count('conversions', filter=__import__(
            'django.db.models', fromlist=['Q']
        ).Q(conversions__status__name='approved'), distinct=True),
    )
    for offer in offers:
        if offer.click_count > 0:
            cvr = (offer.conv_count / offer.click_count) * 100
            Offer.objects.filter(id=offer.id).update(conversion_rate=round(cvr, 2))


# ══════════════════════════════════════════════════════
# MARKETING TASKS
# ══════════════════════════════════════════════════════

@shared_task(queue='notification')
def send_email_batch(subject: str, template: str, user_ids: list, context: dict):
    """Send batch email campaign."""
    from django.contrib.auth import get_user_model
    from api.offer_inventory.marketing.email_marketing import EmailMarketingService
    User = get_user_model()
    emails = list(User.objects.filter(id__in=user_ids).values_list('email', flat=True))
    emails = [e for e in emails if e and '@' in e]
    try:
        from django.template.loader import render_to_string
        html_body = render_to_string(template, context)
        return EmailMarketingService.send_bulk(subject, html_body, emails)
    except Exception as e:
        logger.error(f'send_email_batch error: {e}')
        return {'error': str(e)}


@shared_task(queue='notification')
def run_reactivation_campaign():
    """Daily reactivation campaign for inactive users."""
    from api.offer_inventory.marketing.campaign_manager import MarketingCampaignService
    result = MarketingCampaignService.run_reactivation_campaign(
        inactive_days=14,
        bonus_amount=__import__('decimal', fromlist=['Decimal']).Decimal('5'),
    )
    logger.info(f'Reactivation campaign: {result}')
    return result


@shared_task(queue='default')
def auto_pause_low_performers():
    """Auto-pause underperforming offers."""
    from api.offer_inventory.ai_optimization.auto_pause_offers import AutoPauseEngine
    result = AutoPauseEngine.evaluate_and_pause()
    logger.info(f'Auto-pause run: paused={len(result["paused"])} expired={len(result["expired"])}')
    return result


@shared_task(queue='analytics')
def update_network_stats_all():
    """Update daily stats for all active networks."""
    from api.offer_inventory.models import OfferNetwork
    from api.offer_inventory.affiliate_network import AffiliateNetworkManager
    for network in OfferNetwork.objects.filter(status='active'):
        try:
            AffiliateNetworkManager.update_daily_network_stats(str(network.id))
        except Exception as e:
            logger.error(f'Network stats update error {network.id}: {e}')


@shared_task(queue='payout')
def process_approved_conversion_payout(conversion_id: str):
    """Process payout for an approved conversion."""
    from api.offer_inventory.payout_engine import PayoutEngine
    try:
        result = PayoutEngine.pay_conversion(conversion_id)
        if result:
            logger.info(f'Payout processed: {conversion_id}')
        return result
    except Exception as e:
        logger.error(f'Payout task error {conversion_id}: {e}')
        return {'error': str(e)}


@shared_task(queue='notification')
def fire_conversion_pixel(conversion_id: str):
    """Fire conversion tracking pixel."""
    from api.offer_inventory.webhooks.pixel_tracking import PixelTracker
    return PixelTracker.fire(conversion_id)


@shared_task(queue='default')
def check_and_mark_referral_converted(user_id: str):
    """Check if user's first conversion should mark referral as converted."""
    from api.offer_inventory.models import Conversion, UserReferral
    from api.offer_inventory.marketing.referral_program import ReferralProgramManager
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        # First successful conversion?
        conv_count = Conversion.objects.filter(user=user, status__name='approved').count()
        if conv_count == 1:
            ReferralProgramManager.mark_converted(user)
    except Exception as e:
        logger.error(f'Referral mark converted error: {e}')


@shared_task(queue='default')
def run_billing_dunning():
    """Monthly dunning run for overdue invoices."""
    from api.offer_inventory.business.billing_manager import BillingManager
    result = BillingManager.run_dunning()
    logger.info(f'Dunning: {result}')
    return result


@shared_task(queue='default')
def generate_monthly_invoices():
    """Auto-generate monthly advertiser invoices."""
    from api.offer_inventory.business.billing_manager import BillingManager
    result = BillingManager.generate_monthly_invoices()
    logger.info(f'Monthly invoices generated: {len(result)}')
    return result


@shared_task(queue='analytics')
def compute_platform_kpis():
    """Pre-compute and cache platform KPIs."""
    from api.offer_inventory.business.kpi_dashboard import KPIDashboard
    try:
        kpis = KPIDashboard.get_platform_kpis(days=30)
        logger.info(f'KPIs computed: revenue={kpis.get("gross_revenue")}')
        return kpis
    except Exception as e:
        logger.error(f'KPI compute error: {e}')
        return {}


@shared_task(queue='default')
def run_aml_check_pending_withdrawals():
    """Run AML checks on pending withdrawals."""
    from api.offer_inventory.models import WithdrawalRequest
    from api.offer_inventory.business.compliance_manager import KYCAMLChecker
    pending = WithdrawalRequest.objects.filter(status='pending').select_related('user')
    flagged = 0
    for wr in pending[:200]:
        result = KYCAMLChecker.check_withdrawal_aml(wr.user, wr.amount)
        if not result['approved']:
            wr.status        = 'rejected'
            wr.rejected_reason = f'AML flag: {result["flags"]}'
            wr.save(update_fields=['status', 'rejected_reason'])
            flagged += 1
            logger.warning(f'AML rejection: withdrawal={wr.id} flags={result["flags"]}')
    return {'checked': pending.count(), 'flagged': flagged}


@shared_task(queue='default')
def award_daily_login_points(user_id: str):
    """Award daily login points for loyalty."""
    from django.contrib.auth import get_user_model
    from api.offer_inventory.marketing.loyalty_program import LoyaltyManager
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        points = LoyaltyManager.award_login_points(user)
        return {'points': points}
    except Exception as e:
        logger.error(f'Daily login points error: {e}')
        return {}


# ══════════════════════════════════════════════════════
# ADDITIONAL TASKS — new modules
# ══════════════════════════════════════════════════════

@shared_task(queue='default')
def retry_webhook_delivery(url: str, event: str, payload: dict,
                            secret: str = '', attempt: int = 1):
    """Retry a failed webhook delivery."""
    from api.offer_inventory.webhooks import WebhookDispatcher, WebhookRetryQueue
    success = WebhookDispatcher._deliver_single(url, event, payload, secret)
    if not success:
        WebhookRetryQueue.enqueue_retry(url, event, payload, secret, attempt)
    return success


@shared_task(queue='default')
def process_due_offer_schedules():
    """Execute any offer schedules that are due."""
    from api.offer_inventory.affiliate_advanced import OfferSchedulerEngine
    result = OfferSchedulerEngine.process_due_schedules()
    logger.info(f'Offer schedules processed: {result}')
    return result


@shared_task(queue='default')
def rollback_expired_payout_bumps():
    """Rollback expired payout bumps."""
    from api.offer_inventory.affiliate_advanced import PayoutBumpManager
    count = PayoutBumpManager.auto_rollback_expired()
    if count:
        logger.info(f'Payout bumps rolled back: {count}')
    return count


@shared_task(queue='analytics')
def update_user_heatmaps():
    """Update activity heatmaps for all active users."""
    from api.offer_inventory.models import Click
    from api.offer_inventory.user_behavior_analysis import ActivityHeatmapService
    from datetime import timedelta

    since   = timezone.now() - timedelta(hours=1)
    clicks  = Click.objects.filter(
        created_at__gte=since, is_fraud=False, user__isnull=False
    ).select_related('user')[:5000]

    count = 0
    for click in clicks:
        try:
            ActivityHeatmapService.update_heatmap(click.user, click.created_at)
            count += 1
        except Exception as e:
            logger.debug(f'Heatmap update error: {e}')
    return count


@shared_task(queue='analytics')
def compute_engagement_scores():
    """Batch compute engagement scores for all users."""
    from django.contrib.auth import get_user_model
    from api.offer_inventory.user_behavior_analysis import EngagementScoreCalculator
    from api.offer_inventory.models import UserProfile

    User = get_user_model()
    updated = 0
    for user in User.objects.filter(is_active=True)[:2000]:
        try:
            score = EngagementScoreCalculator.calculate(user)
            # Store in notification_prefs for now
            profile, _ = UserProfile.objects.get_or_create(user=user)
            prefs = profile.notification_prefs or {}
            prefs['engagement_score'] = score['total']
            prefs['engagement_grade'] = score['grade']
            UserProfile.objects.filter(user=user).update(notification_prefs=prefs)
            updated += 1
        except Exception as e:
            logger.debug(f'Engagement score error: {e}')
    return updated


@shared_task(queue='default')
def update_user_segment_counts():
    """Update dynamic user segment counts."""
    from api.offer_inventory.user_behavior_analysis import UserSegmentationService
    UserSegmentationService.update_segment_counts()


@shared_task(queue='default')
def run_security_audit():
    """Generate and cache daily security audit report."""
    from api.offer_inventory.maintenance_logs import SecurityAuditReporter
    report = SecurityAuditReporter.generate_report(days=1)
    from django.core.cache import cache
    cache.set('security_audit_daily', report, 86400)
    logger.info(f'Security audit: {report.get("fraud_attempts", 0)} fraud attempts today')
    return report


@shared_task(queue='default')
def cleanup_expired_db_backup_records():
    """Clean up old backup logs and backup files."""
    from api.offer_inventory.maintenance_logs import AutomatedDBBackup
    removed = AutomatedDBBackup.cleanup_old_backups()
    logger.info(f'Backup files cleaned: {removed}')
    return removed


@shared_task(queue='default')
def check_budget_alerts():
    """Check campaign budget alerts and notify advertisers."""
    from api.offer_inventory.affiliate_advanced import BudgetController
    from api.offer_inventory.notifications import EmailAlertSystem
    alerts = BudgetController.get_budget_alerts(warning_pct=80.0)
    if alerts:
        logger.warning(f'Budget alerts: {len(alerts)} campaigns at >80% spend')
    return {'alerts': len(alerts)}


@shared_task(queue='analytics')
def run_real_time_monitor():
    """Run real-time platform health checks."""
    from api.offer_inventory.reporting_audit import RealTimeMonitor
    result = RealTimeMonitor.check_all()
    if not result['healthy']:
        logger.warning(f'Platform health alerts: {result["alerts"]}')
    return result


# ══════════════════════════════════════════════════════
# RTB + ML + PUBLISHER TASKS
# ══════════════════════════════════════════════════════

@shared_task(queue='analytics')
def train_ml_fraud_model():
    """Nightly ML fraud model retraining (Isolation Forest)."""
    from api.offer_inventory.ml_fraud.model_trainer import FraudModelTrainer
    result = FraudModelTrainer.train(days=30, n_estimators=100)
    if result.get('success'):
        logger.info(f'ML fraud model retrained: {result}')
    else:
        logger.error(f'ML fraud model training failed: {result}')
    return result


@shared_task(queue='fraud')
def auto_block_ml_anomalies():
    """Auto-block click farms detected by ML anomaly detector."""
    from api.offer_inventory.ml_fraud.anomaly_detector import AnomalyDetector
    result = AnomalyDetector.auto_block_detected(dry_run=False)
    logger.info(f'ML auto-block: {result}')
    return result


@shared_task(queue='analytics')
def update_publisher_daily_stats():
    """Update daily publisher revenue stats from BidLog."""
    from api.offer_inventory.models import Publisher, BidLog, PublisherRevenue
    from django.db.models import Count, Sum, Avg
    from django.utils import timezone as tz
    today = tz.now().date()
    for pub in Publisher.objects.filter(status='active'):
        try:
            agg = BidLog.objects.filter(
                publisher_id=str(pub.id),
                created_at__date=today,
                is_won=True,
            ).aggregate(
                impressions=Count('id'),
                revenue    =Sum('clearing_price'),
                ecpm       =Avg('ecpm'),
            )
            PublisherRevenue.objects.update_or_create(
                publisher=pub, date=today,
                defaults={
                    'impressions'    : agg['impressions'] or 0,
                    'gross_revenue'  : agg['revenue'] or 0,
                    'publisher_share': (agg['revenue'] or 0) * Decimal('0.30'),
                    'ecpm'           : agg['ecpm'] or 0,
                }
            )
        except Exception as e:
            logger.error(f'Publisher stats error {pub.id}: {e}')


@shared_task(queue='analytics')
def compute_ecpm_scores():
    """Recompute and cache eCPM scores for all active offers."""
    from api.offer_inventory.models import Offer
    from api.offer_inventory.rtb_engine.ecpm_calculator import ECPMCalculator
    from django.core.cache import cache
    count = 0
    for offer in Offer.objects.filter(status='active'):
        # Clear stale eCPM cache to force recomputation
        cache.delete(f'rtb:cvr:{offer.id}')
        count += 1
    logger.info(f'eCPM cache cleared for {count} offers')
    return count


@shared_task(queue='default')
def auto_pause_budget_depleted_campaigns():
    """Auto-pause campaigns that have run out of budget."""
    from api.offer_inventory.affiliate_advanced.budget_control import BudgetController
    paused = BudgetController.auto_pause_depleted()
    if paused > 0:
        logger.info(f'Auto-paused {paused} budget-depleted campaigns')
    return paused


@shared_task(queue='default')
def process_due_offer_schedules():
    """Process all due offer activation/deactivation schedules."""
    from api.offer_inventory.affiliate_advanced.offer_scheduler import OfferSchedulerEngine
    result = OfferSchedulerEngine.process_due_schedules()
    if sum(result.values()) > 0:
        logger.info(f'Offer schedules processed: {result}')
    return result


@shared_task(queue='default')
def rotate_expired_payout_bumps():
    """Roll back expired payout bumps automatically."""
    from api.offer_inventory.affiliate_advanced.payout_bump_logic import PayoutBumpManager
    count = PayoutBumpManager.rollback_all_expired()
    if count > 0:
        logger.info(f'Rolled back {count} expired payout bumps')
    return count


@shared_task(queue='analytics')
def refresh_exchange_rates():
    """Refresh all currency exchange rates from external API."""
    from api.offer_inventory.finance_payment.currency_converter_v2 import CurrencyConverterV2
    result = CurrencyConverterV2.refresh_rates()
    logger.info(f'Exchange rates refreshed: {result}')
    return result


@shared_task(queue='analytics')
def compute_churn_scores():
    """Batch compute churn probability for all active users."""
    from api.offer_inventory.user_behavior_analysis.churn_prediction import ChurnPredictor
    count = ChurnPredictor.update_all_churn_scores(limit=5000)
    logger.info(f'Churn scores updated: {count} users')
    return count


@shared_task(queue='analytics')
def update_segment_counts():
    """Recompute user count for all dynamic user segments."""
    from api.offer_inventory.user_behavior_analysis.user_segmentation import UserSegmentationService
    UserSegmentationService.update_segment_counts()
    logger.info('User segment counts updated')


@shared_task(queue='default')
def cleanup_old_records():
    """Periodic DB cleanup of old log records."""
    from api.offer_inventory.system_devops.log_rotator import LogRotator
    result = LogRotator.rotate_all(dry_run=False)
    logger.info(f'Log rotation complete: {result}')
    return result


@shared_task(queue='default')
def send_daily_platform_summary():
    """Send daily performance summary to Slack + admin email."""
    from api.offer_inventory.business.kpi_dashboard import KPIDashboard
    from api.offer_inventory.notifications.slack_webhook import SlackNotifier
    stats = KPIDashboard.get_platform_kpis(days=1)
    SlackNotifier().daily_summary({
        'date'             : str(__import__('django.utils.timezone', fromlist=['timezone']).timezone.now().date()),
        'gross_revenue'    : stats.get('gross_revenue', 0),
        'total_conversions': stats.get('total_conversions', 0),
        'total_clicks'     : stats.get('total_clicks', 0),
        'cvr_pct'          : stats.get('cvr_pct', 0),
        'fraud_rate_pct'   : stats.get('fraud_rate_pct', 0),
        'new_users'        : stats.get('new_users_today', 0),
    })
    logger.info('Daily summary sent')


# ── Celery Beat Schedule ────────────────────────────────────────────────────
CELERYBEAT_SCHEDULE = {
    # Every minute
    'process-due-schedules'      : {'task': 'api.offer_inventory.tasks.process_due_offer_schedules',   'schedule': 60},
    'rotate-expired-bumps'       : {'task': 'api.offer_inventory.tasks.rotate_expired_payout_bumps',   'schedule': 300},

    # Every 5 minutes
    'deliver-failed-postbacks'   : {'task': 'api.offer_inventory.tasks.retry_failed_postbacks',        'schedule': 300},

    # Every 30 minutes
    'auto-block-ml-anomalies'    : {'task': 'api.offer_inventory.tasks.auto_block_ml_anomalies',       'schedule': 1800},
    'compute-ecpm-scores'        : {'task': 'api.offer_inventory.tasks.compute_ecpm_scores',           'schedule': 1800},

    # Every hour
    'refresh-exchange-rates'     : {'task': 'api.offer_inventory.tasks.refresh_exchange_rates',        'schedule': 3600},
    'update-publisher-stats'     : {'task': 'api.offer_inventory.tasks.update_publisher_daily_stats',  'schedule': 3600},
    'pause-depleted-campaigns'   : {'task': 'api.offer_inventory.tasks.auto_pause_budget_depleted_campaigns', 'schedule': 3600},

    # Every 6 hours
    'network-stats-update'       : {'task': 'api.offer_inventory.tasks.update_all_network_stats',      'schedule': 21600},
    'cleanup-old-records'        : {'task': 'api.offer_inventory.tasks.cleanup_old_records',           'schedule': 21600},

    # Daily (midnight)
    'train-ml-fraud-model'       : {'task': 'api.offer_inventory.tasks.train_ml_fraud_model',          'schedule': 86400},
    'compute-churn-scores'       : {'task': 'api.offer_inventory.tasks.compute_churn_scores',          'schedule': 86400},
    'update-segment-counts'      : {'task': 'api.offer_inventory.tasks.update_segment_counts',         'schedule': 86400},
    'daily-summary'              : {'task': 'api.offer_inventory.tasks.send_daily_platform_summary',   'schedule': 86400},
    'auto-expire-offers'         : {'task': 'api.offer_inventory.tasks.auto_expire_offers',            'schedule': 86400},
    'generate-daily-stats'       : {'task': 'api.offer_inventory.tasks.generate_daily_stats',          'schedule': 86400},
}
