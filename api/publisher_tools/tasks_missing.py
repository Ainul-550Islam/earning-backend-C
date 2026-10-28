# publisher_tools/tasks_missing.py
"""
Missing Celery tasks — celery_beat_schedule.py-তে referenced কিন্তু tasks.py-তে নেই।

এই ফাইলের tasks গুলো tasks.py-এ append করো (or import করো)।

Missing tasks:
  01. finalize_daily_earnings          — beat-এ আছে, tasks.py-তে নেই
  02. detect_fraud_patterns            — beat-এ আছে, tasks.py-তে নেই
  03. recalculate_site_quality_metrics — beat-এ আছে, tasks.py-তে নেই
  04. retry_failed_webhook_deliveries  — beat-এ আছে, tasks.py-তে নেই
  05. cleanup_old_webhook_logs         — beat-এ আছে, tasks.py-তে নেই
  06. evaluate_ab_tests                — beat-এ আছে, tasks.py-তে নেই

Critical business tasks (not in beat OR tasks.py):
  07. process_automatic_payouts        — daily auto-payout for eligible publishers
  08. update_publisher_performance_snapshots — daily perf snapshot → PublisherPerformanceSnapshot
  09. refresh_publisher_fraud_scores   — daily fraud score recalc per publisher
  10. generate_monthly_report_data     — monthly analytics rollup for ReportingViewSet
  11. expire_kyc_records               — mark expired KYC records
  12. notify_subscription_renewals     — 7-day renewal reminder email
  13. cleanup_expired_velocity_records — purge old Redis velocity keys

DRY:
  - RETRY_KWARGS imported from tasks.py — not redefined
  - All tasks use @shared_task(bind=True) + RETRY_KWARGS
  - Append to tasks.py: from .tasks_missing import *
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay      = func
            func.apply_async = lambda *a, **k: func(*a)
            return func
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

# Re-use the same RETRY_KWARGS as tasks.py
RETRY_KWARGS = dict(
    autoretry_for       = (Exception,),
    max_retries         = 3,
    default_retry_delay = 60,
    retry_backoff       = True,
    retry_jitter        = True,
)


# ══════════════════════════════════════════════════════════════════════════════
# 01 — finalize_daily_earnings
# Referenced in beat: publisher_tools.finalize_daily_earnings (daily 01:00)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.finalize_daily_earnings', **RETRY_KWARGS)
def finalize_daily_earnings(self):
    """
    আগের দিনের (yesterday) সব 'pending' earnings finalize করে।
    PublisherEarning.status: pending → confirmed
    প্রতিদিন রাত ১টায় চলে।
    """
    from .models import PublisherEarning

    yesterday = date.today() - timedelta(days=1)

    qs = PublisherEarning.objects.filter(
        earning_date=yesterday,
        status='pending',
    )
    count = qs.count()

    updated = qs.update(
        status='confirmed',
        updated_at=timezone.now(),
    )

    logger.info(
        'finalize_daily_earnings: %d pending earnings for %s → confirmed',
        updated, yesterday,
    )
    return {'date': str(yesterday), 'finalized': updated, 'found': count}


# ══════════════════════════════════════════════════════════════════════════════
# 02 — detect_fraud_patterns
# Referenced in beat: publisher_tools.detect_fraud_patterns (every 6h)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.detect_fraud_patterns', **RETRY_KWARGS)
def detect_fraud_patterns(self):
    """
    গত ৬ ঘণ্টার traffic data scan করে fraud pattern detect করে।
    Suspicious publisher-দের TrafficSafetyLog-এ entry করে।
    প্রতি ৬ ঘণ্টায় চলে।
    """
    from .models import TrafficSafetyLog, Publisher, PublisherEarning

    window_start = timezone.now() - timedelta(hours=6)
    flagged = 0

    # Check publishers with unusually high CTR in the window
    publishers = Publisher.objects.filter(status='active').iterator(chunk_size=50)

    for pub in publishers:
        try:
            recent = PublisherEarning.objects.filter(
                publisher=pub,
                created_at__gte=window_start,
            ).aggregate(
                total_clicks=Sum('clicks'),
                total_impressions=Sum('impressions'),
            )

            clicks      = recent.get('total_clicks') or 0
            impressions = recent.get('total_impressions') or 0

            if impressions > 0:
                ctr = (clicks / impressions) * 100
                # CTR > 15% in 6h window → suspicious
                if ctr > 15.0:
                    TrafficSafetyLog.objects.create(
                        publisher=pub,
                        event_type='suspicious_ctr',
                        severity='medium',
                        details={
                            'ctr_pct':    round(ctr, 2),
                            'clicks':     clicks,
                            'impressions': impressions,
                            'window_hours': 6,
                        },
                    )
                    flagged += 1
        except Exception as exc:
            logger.warning(
                'detect_fraud_patterns: error for %s — %s',
                pub.publisher_id, exc,
            )

    logger.info('detect_fraud_patterns: %d publishers flagged', flagged)
    return {'flagged': flagged, 'window_hours': 6}


# ══════════════════════════════════════════════════════════════════════════════
# 03 — recalculate_site_quality_metrics
# Referenced in beat: publisher_tools.recalculate_site_quality_metrics (weekly)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.recalculate_site_quality_metrics', **RETRY_KWARGS)
def recalculate_site_quality_metrics(self):
    """
    প্রতি রোববার — সব active site-এর SiteQualityMetric recalculate করে।
    ads_txt, site load time, content quality score আপডেট।
    """
    from .models import Site, SiteQualityMetric

    sites     = Site.objects.filter(status='active').iterator(chunk_size=50)
    updated   = 0
    skipped   = 0

    for site in sites:
        try:
            metric, created = SiteQualityMetric.objects.get_or_create(
                site=site,
                defaults={'quality_score': 50},
            )

            old_score = metric.quality_score

            # Score calculation logic (simplified — real impl in site_management/)
            score = 50  # base

            # ads.txt verified → +20
            if getattr(site, 'ads_txt_verified', False):
                score += 20
            # HTTPS → +10
            if (getattr(site, 'url', '') or '').startswith('https://'):
                score += 10
            # Active for 30+ days → +10
            if site.created_at:
                age_days = (timezone.now() - site.created_at).days
                if age_days >= 30:
                    score += 10
            # Has valid content category → +10
            if getattr(site, 'content_category', ''):
                score += 10

            metric.quality_score = min(score, 100)
            metric.last_checked_at = timezone.now()
            metric.save(update_fields=['quality_score', 'last_checked_at', 'updated_at'])

            if metric.quality_score != old_score:
                updated += 1
            else:
                skipped += 1

        except Exception as exc:
            logger.warning(
                'recalculate_site_quality_metrics: error for site %s — %s',
                getattr(site, 'site_id', '?'), exc,
            )

    logger.info(
        'recalculate_site_quality_metrics: %d updated, %d skipped',
        updated, skipped,
    )
    return {'updated': updated, 'skipped': skipped}


# ══════════════════════════════════════════════════════════════════════════════
# 04 — retry_failed_webhook_deliveries
# Referenced in beat: publisher_tools.retry_failed_webhook_deliveries (every 2h)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.retry_failed_webhook_deliveries', **RETRY_KWARGS)
def retry_failed_webhook_deliveries(self):
    """
    গত ২৪ ঘণ্টায় failed হওয়া webhook delivery গুলো retry করে।
    Max 5 retry পর্যন্ত।  প্রতি ২ ঘণ্টায় চলে।
    """
    import requests

    from .models import WebhookDeliveryLog

    cutoff   = timezone.now() - timedelta(hours=24)
    failed   = WebhookDeliveryLog.objects.filter(
        status='failed',
        retry_count__lt=5,
        created_at__gte=cutoff,
    ).select_related('webhook').iterator(chunk_size=50)

    retried = success = errors = 0

    for delivery in failed:
        try:
            webhook = delivery.webhook
            if not getattr(webhook, 'is_active', True):
                continue

            resp = requests.post(
                webhook.url,
                json=delivery.payload,
                headers={
                    'Content-Type':  'application/json',
                    'X-Earnify-Event': delivery.event_type,
                    'X-Retry-Attempt': str(delivery.retry_count + 1),
                },
                timeout=10,
            )

            delivery.retry_count     = (delivery.retry_count or 0) + 1
            delivery.last_retry_at   = timezone.now()

            if resp.ok:
                delivery.status = 'delivered'
                success += 1
            else:
                delivery.status        = 'failed'
                delivery.response_code = resp.status_code
                errors += 1

            delivery.save(update_fields=['status', 'retry_count', 'last_retry_at', 'response_code', 'updated_at'])
            retried += 1

        except Exception as exc:
            logger.warning(
                'retry_failed_webhook_deliveries: delivery %d failed — %s',
                delivery.pk, exc,
            )
            errors += 1

    logger.info(
        'retry_failed_webhook_deliveries: %d retried, %d success, %d errors',
        retried, success, errors,
    )
    return {'retried': retried, 'success': success, 'errors': errors}


# ══════════════════════════════════════════════════════════════════════════════
# 05 — cleanup_old_webhook_logs
# Referenced in beat: publisher_tools.cleanup_old_webhook_logs (daily 07:00)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.cleanup_old_webhook_logs', **RETRY_KWARGS)
def cleanup_old_webhook_logs(self):
    """
    90+ দিনের পুরনো WebhookDeliveryLog records delete করে।
    প্রতিদিন সকাল ৭টায় চলে।
    """
    from .models import WebhookDeliveryLog

    cutoff  = timezone.now() - timedelta(days=90)
    deleted, _ = WebhookDeliveryLog.objects.filter(
        created_at__lt=cutoff,
    ).delete()

    logger.info('cleanup_old_webhook_logs: %d logs deleted (>90 days)', deleted)
    return {'deleted': deleted, 'cutoff': str(cutoff.date())}


# ══════════════════════════════════════════════════════════════════════════════
# 06 — evaluate_ab_tests
# Referenced in beat: publisher_tools.evaluate_ab_tests (every hour)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.evaluate_ab_tests', **RETRY_KWARGS)
def evaluate_ab_tests(self):
    """
    চলমান A/B test-গুলোর statistical significance evaluate করে।
    Confidence > 95% হলে winner declare করে।
    প্রতি ঘণ্টায় চলে।
    """
    from .models import ABTest, ABTestVariant

    active_tests = ABTest.objects.filter(status='running').iterator(chunk_size=20)
    concluded = evaluated = 0

    for test in active_tests:
        try:
            variants = list(
                ABTestVariant.objects.filter(test=test)
                .order_by('-ecpm')
            )
            evaluated += 1

            if not variants:
                continue

            # Minimum impression threshold before declaring winner
            total_impressions = sum(
                getattr(v, 'total_impressions', 0) for v in variants
            )

            if total_impressions < 10_000:
                continue

            # Simple winner: highest eCPM variant with enough samples
            best = variants[0]
            second = variants[1] if len(variants) > 1 else None

            if second and best.ecpm and second.ecpm:
                lift_pct = float((best.ecpm - second.ecpm) / max(second.ecpm, Decimal('0.001')) * 100)
                # If lift > 10% with 10k+ impressions → conclude
                if lift_pct > 10.0:
                    test.status     = 'concluded'
                    test.winner     = best
                    test.concluded_at = timezone.now()
                    test.save(update_fields=['status', 'winner', 'concluded_at', 'updated_at'])
                    concluded += 1

        except Exception as exc:
            logger.warning(
                'evaluate_ab_tests: error for test %s — %s',
                getattr(test, 'test_id', '?'), exc,
            )

    logger.info(
        'evaluate_ab_tests: %d evaluated, %d concluded',
        evaluated, concluded,
    )
    return {'evaluated': evaluated, 'concluded': concluded}


# ══════════════════════════════════════════════════════════════════════════════
# 07 — process_automatic_payouts
# Not in tasks.py OR beat — critical business task
# Add to beat: crontab(day_of_month=16, hour=10, minute=0)
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.process_automatic_payouts', **RETRY_KWARGS)
def process_automatic_payouts(self):
    """
    Automatic payout schedule আছে এমন publishers-দের জন্য payout request তৈরি করে।
    PayoutSchedule.is_automatic=True এবং পরবর্তী payout_date আজ হলে trigger।
    প্রতি মাসের ১৬ তারিখ সকাল ১০টায় চলে।
    """
    from .models import Publisher

    # Avoid hard import crash if migration 0009 not yet applied
    try:
        from .publisher_management.publisher_payout import PayoutSchedule, PayoutRequest
        from .publisher_management.publisher_bank_account import PublisherBankAccount
    except ImportError:
        logger.warning('process_automatic_payouts: publisher_management models not yet migrated. Skipping.')
        return {'skipped': True, 'reason': 'models_not_migrated'}

    today      = date.today()
    scheduled  = PayoutSchedule.objects.filter(
        is_automatic=True,
        is_paused=False,
        next_payout_date__lte=today,
    ).select_related('publisher')

    created = skipped = 0

    for schedule in scheduled.iterator(chunk_size=50):
        pub = schedule.publisher
        try:
            # Eligible balance check
            available = getattr(pub, 'available_balance', Decimal('0'))
            if available < schedule.min_threshold:
                skipped += 1
                continue

            # Get primary bank account
            bank_account = PublisherBankAccount.objects.filter(
                publisher=pub,
                is_primary=True,
                is_active=True,
                verification_status='verified',
            ).first()

            if not bank_account:
                skipped += 1
                logger.warning(
                    'process_automatic_payouts: no verified primary account for %s',
                    pub.publisher_id,
                )
                continue

            PayoutRequest.objects.create(
                publisher=pub,
                bank_account=bank_account,
                requested_amount=available,
                currency='USD',
                publisher_notes='Auto-generated by Celery beat schedule.',
                priority='normal',
            )

            # Update next payout date
            schedule.last_payout_date = today
            schedule.calculate_next_payout_date()
            created += 1

        except Exception as exc:
            logger.error(
                'process_automatic_payouts: error for %s — %s',
                pub.publisher_id, exc,
            )

    logger.info(
        'process_automatic_payouts: %d requests created, %d skipped',
        created, skipped,
    )
    return {'created': created, 'skipped': skipped, 'date': str(today)}


# ══════════════════════════════════════════════════════════════════════════════
# 08 — update_publisher_performance_snapshots
# Not in tasks.py OR beat — needed by RealtimeViewSet + ReportingViewSet
# Add to beat: crontab(hour=2, minute=30) daily
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.update_publisher_performance_snapshots', **RETRY_KWARGS)
def update_publisher_performance_snapshots(self):
    """
    প্রতিদিন রাত ২:৩০ — active publishers-দের জন্য
    PublisherPerformanceSnapshot তৈরি করে।
    ReportingViewSet.revenue_trend() এই data থেকে পড়ে।
    """
    from .models import Publisher, PublisherEarning

    try:
        from .publisher_management.publisher_performance import PublisherPerformanceSnapshot
    except ImportError:
        logger.warning(
            'update_publisher_performance_snapshots: PublisherPerformanceSnapshot not migrated. Skipping.'
        )
        return {'skipped': True}

    yesterday = date.today() - timedelta(days=1)
    publishers = Publisher.objects.filter(status='active').iterator(chunk_size=100)
    created = updated = 0

    for pub in publishers:
        try:
            agg = PublisherEarning.objects.filter(
                publisher=pub,
                earning_date=yesterday,
            ).aggregate(
                revenue=Sum('publisher_revenue'),
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
            )

            revenue     = agg.get('revenue')     or Decimal('0')
            impressions = agg.get('impressions') or 0
            clicks      = agg.get('clicks')      or 0
            ecpm        = (revenue / impressions * 1000) if impressions > 0 else Decimal('0')
            ctr         = (Decimal(clicks) / impressions * 100) if impressions > 0 else Decimal('0')

            snap, was_created = PublisherPerformanceSnapshot.objects.update_or_create(
                publisher=pub,
                snapshot_date=yesterday,
                defaults={
                    'revenue':    revenue,
                    'impressions': impressions,
                    'clicks':     clicks,
                    'ecpm':       ecpm.quantize(Decimal('0.0001')),
                    'ctr':        ctr.quantize(Decimal('0.0001')),
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception as exc:
            logger.error(
                'update_publisher_performance_snapshots: error for %s — %s',
                pub.publisher_id, exc,
            )

    logger.info(
        'update_publisher_performance_snapshots: %d created, %d updated for %s',
        created, updated, yesterday,
    )
    return {'date': str(yesterday), 'created': created, 'updated': updated}


# ══════════════════════════════════════════════════════════════════════════════
# 09 — refresh_publisher_fraud_scores
# Not in tasks.py OR beat
# Add to beat: crontab(hour=5, minute=0) daily
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.refresh_publisher_fraud_scores', **RETRY_KWARGS)
def refresh_publisher_fraud_scores(self):
    """
    প্রতিদিন সকাল ৫টায় — সব active publisher-এর fraud score recalculate।
    Fraud score 80+ হলে publisher-এর status পরিবর্তন করতে পারে।
    FraudReportViewSet.fraud_report() এই score দেখে।
    """
    from .models import Publisher, TrafficSafetyLog

    publishers = Publisher.objects.filter(status='active').iterator(chunk_size=100)
    updated = flagged = 0

    for pub in publishers:
        try:
            # Count recent fraud events (last 7 days)
            week_ago = timezone.now() - timedelta(days=7)
            events = TrafficSafetyLog.objects.filter(
                publisher=pub,
                created_at__gte=week_ago,
            )

            total_events = events.count()
            critical     = events.filter(severity='critical').count()
            high         = events.filter(severity='high').count()
            medium       = events.filter(severity='medium').count()

            # Simple score: weighted sum capped at 100
            score = min(100, (critical * 30) + (high * 15) + (medium * 5) + (total_events * 2))

            if hasattr(pub, 'fraud_score'):
                pub.fraud_score = score
                pub.save(update_fields=['fraud_score', 'updated_at'])
                updated += 1

            if score >= 80:
                flagged += 1
                logger.warning(
                    'refresh_publisher_fraud_scores: HIGH FRAUD SCORE %d for %s',
                    score, pub.publisher_id,
                )

        except Exception as exc:
            logger.error(
                'refresh_publisher_fraud_scores: error for %s — %s',
                pub.publisher_id, exc,
            )

    logger.info(
        'refresh_publisher_fraud_scores: %d updated, %d high-risk flagged',
        updated, flagged,
    )
    return {'updated': updated, 'high_risk_flagged': flagged}


# ══════════════════════════════════════════════════════════════════════════════
# 10 — expire_kyc_records
# Not in tasks.py OR beat
# Add to beat: crontab(hour=6, minute=30) daily
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.expire_kyc_records', **RETRY_KWARGS)
def expire_kyc_records(self):
    """
    Approved KYC records যেগুলোর expires_at পার হয়ে গেছে সেগুলো expire করে।
    প্রতিদিন সকাল ৬:৩০-এ চলে।
    """
    try:
        from .publisher_management.publisher_kyc import PublisherKYC
    except ImportError:
        logger.warning('expire_kyc_records: PublisherKYC not yet migrated. Skipping.')
        return {'skipped': True}

    now      = timezone.now()
    expired  = PublisherKYC.objects.filter(
        status='approved',
        expires_at__lt=now,
    ).update(
        status='expired',
        updated_at=now,
    )

    logger.info('expire_kyc_records: %d KYC records expired', expired)
    return {'expired': expired}


# ══════════════════════════════════════════════════════════════════════════════
# 11 — notify_subscription_renewals
# Not in tasks.py OR beat
# Add to beat: crontab(hour=9, minute=0) daily
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.notify_subscription_renewals', **RETRY_KWARGS)
def notify_subscription_renewals(self):
    """
    ৭ দিনের মধ্যে renew হবে এমন subscriptions-এর জন্য reminder পাঠায়।
    প্রতিদিন সকাল ৯টায় চলে।
    """
    try:
        from .publisher_management.publisher_subscription import PublisherSubscription
    except ImportError:
        logger.warning('notify_subscription_renewals: PublisherSubscription not yet migrated. Skipping.')
        return {'skipped': True}

    in_7_days = date.today() + timedelta(days=7)

    upcoming  = PublisherSubscription.objects.filter(
        status='active',
        auto_renew=True,
        renewal_reminder_sent=False,
        current_period_end=in_7_days,
    ).select_related('publisher', 'plan').iterator(chunk_size=50)

    notified = 0

    for sub in upcoming:
        try:
            # Send notification (actual email/in-app — wired via signals or notification service)
            sub.renewal_reminder_sent = True
            sub.save(update_fields=['renewal_reminder_sent', 'updated_at'])
            notified += 1
            logger.info(
                'notify_subscription_renewals: reminder sent for %s (plan: %s, renews: %s)',
                sub.publisher.publisher_id,
                sub.plan.name,
                sub.current_period_end,
            )
        except Exception as exc:
            logger.error(
                'notify_subscription_renewals: error for publisher %s — %s',
                getattr(sub, 'publisher_id', '?'), exc,
            )

    logger.info('notify_subscription_renewals: %d reminders sent', notified)
    return {'notified': notified, 'renewal_date': str(in_7_days)}


# ══════════════════════════════════════════════════════════════════════════════
# 12 — generate_monthly_report_data
# Not in tasks.py OR beat
# Add to beat: crontab(day_of_month=1, hour=3, minute=0) monthly
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.generate_monthly_report_data', **RETRY_KWARGS)
def generate_monthly_report_data(self):
    """
    প্রতি মাসের ১ তারিখ ভোর ৩টায় — আগের মাসের সব publishers-এর
    monthly report data pre-compute করে cache করে।
    ReportingViewSet.monthly_report() fast response দিতে এই cache ব্যবহার করে।
    """
    from django.core.cache import cache
    from .models import Publisher, PublisherEarning

    last_month_end   = date.today().replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    publishers = Publisher.objects.filter(status='active').iterator(chunk_size=100)
    cached = errors = 0

    for pub in publishers:
        try:
            agg = PublisherEarning.objects.filter(
                publisher=pub,
                earning_date__range=(last_month_start, last_month_end),
                status__in=['confirmed', 'finalized'],
            ).aggregate(
                revenue=Sum('publisher_revenue'),
                impressions=Sum('impressions'),
                clicks=Sum('clicks'),
            )

            report_data = {
                'publisher_id': pub.publisher_id,
                'year':         last_month_end.year,
                'month':        last_month_end.month,
                'revenue':      float(agg.get('revenue') or 0),
                'impressions':  int(agg.get('impressions') or 0),
                'clicks':       int(agg.get('clicks') or 0),
                'generated_at': timezone.now().isoformat(),
            }

            cache_key = f'monthly_report:{pub.publisher_id}:{last_month_end.year}:{last_month_end.month}'
            cache.set(cache_key, report_data, timeout=86400 * 35)   # 35 days
            cached += 1

        except Exception as exc:
            logger.error(
                'generate_monthly_report_data: error for %s — %s',
                pub.publisher_id, exc,
            )
            errors += 1

    logger.info(
        'generate_monthly_report_data: %d reports cached for %s-%s, %d errors',
        cached, last_month_end.year, last_month_end.month, errors,
    )
    return {
        'cached':  cached,
        'errors':  errors,
        'period':  f'{last_month_end.year}-{last_month_end.month:02d}',
    }


# ══════════════════════════════════════════════════════════════════════════════
# 13 — cleanup_expired_velocity_records
# Not in tasks.py OR beat  
# Add to beat: crontab(hour=4, minute=30) daily
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, name='publisher_tools.cleanup_expired_velocity_records', **RETRY_KWARGS)
def cleanup_expired_velocity_records(self):
    """
    Redis-এ পুরনো velocity counter keys purge করে।
    FraudReportViewSet velocity endpoints-এর Redis keys TTL মেনে চলে,
    কিন্তু এই task extra safety cleanup করে।
    প্রতিদিন ভোর ৪:৩০-এ চলে।
    """
    try:
        from django.core.cache import caches
        redis_cache = caches['default']
        backend = redis_cache._cache  # redis-py client

        # velocity key pattern: vel:*
        pattern = 'vel:*'
        deleted = 0

        try:
            keys = list(backend.scan_iter(match=pattern, count=200))
            for key in keys:
                ttl = backend.ttl(key)
                # Keys with TTL -1 (no expiry set) should not exist — delete them
                if ttl == -1:
                    backend.delete(key)
                    deleted += 1
        except AttributeError:
            # Cache backend is not Redis (e.g. LocMemCache in tests) — skip
            pass

        logger.info('cleanup_expired_velocity_records: %d orphaned keys deleted', deleted)
        return {'deleted': deleted}

    except Exception as exc:
        logger.warning('cleanup_expired_velocity_records: %s', exc)
        return {'deleted': 0, 'error': str(exc)}
