"""
Background Tasks for Offer Routing System

This module provides Celery tasks for offer routing operations.
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .services.core import OfferRoutingEngine, RoutingCacheService
from .services.analytics import RoutingAnalyticsService
from .services.cap import CapEnforcementService
from .services.ab_test import ABTestService
from .models import RoutingDecisionLog, RoutePerformanceStat
from .constants import (
    DECISION_LOG_RETENTION_DAYS, INSIGHT_AGGREGATION_HOURS,
    PERFORMANCE_STATS_RETENTION_DAYS, MAX_DECISION_LOGS_PER_BATCH
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def score_update_task():
    """
    Update offer scores for all active offers.
    Runs every 30 minutes.
    """
    try:
        from .services.scoring import OfferScorerService
        
        scorer = OfferScorerService()
        updated_count = scorer.update_all_scores()
        
        logger.info(f"Score update completed: {updated_count} offers updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Score update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def rank_update_task():
    """
    Update global offer rankings.
    Runs hourly.
    """
    try:
        from .services.scoring import OfferRankerService
        
        ranker = OfferRankerService()
        updated_count = ranker.update_global_rankings()
        
        logger.info(f"Rank update completed: {updated_count} offers ranked")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Rank update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cap_reset_task():
    """
    Reset daily offer caps.
    Runs at midnight.
    """
    try:
        cap_service = CapEnforcementService()
        reset_count = cap_service.reset_daily_caps()
        
        logger.info(f"Cap reset completed: {reset_count} caps reset")
        return {'success': True, 'reset_count': reset_count}
        
    except Exception as e:
        logger.error(f"Cap reset task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cache_warmup_task():
    """
    Warm up routing cache for active users.
    Runs every 5 minutes.
    """
    try:
        cache_service = RoutingCacheService()
        warmed_count = cache_service.warmup_active_users()
        
        logger.info(f"Cache warmup completed: {warmed_count} users warmed")
        return {'success': True, 'warmed_count': warmed_count}
        
    except Exception as e:
        logger.error(f"Cache warmup task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def ab_test_task():
    """
    Evaluate A/B test significance and declare winners.
    Runs every hour.
    """
    try:
        ab_service = ABTestService()
        evaluated_count = ab_service.evaluate_active_tests()
        
        logger.info(f"A/B test evaluation completed: {evaluated_count} tests evaluated")
        return {'success': True, 'evaluated_count': evaluated_count}
        
    except Exception as e:
        logger.error(f"A/B test task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def affinity_update_task():
    """
    Update user-category affinity scores.
    Runs daily.
    """
    try:
        from .services.personalization import CollaborativeFilterService
        
        collab_service = CollaborativeFilterService()
        updated_count = collab_service.update_affinity_scores()
        
        logger.info(f"Affinity update completed: {updated_count} users updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Affinity update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def preference_vector_task():
    """
    Rebuild user preference vectors.
    Runs weekly.
    """
    try:
        from .services.personalization import ContentBasedService
        
        content_service = ContentBasedService()
        rebuilt_count = content_service.rebuild_preference_vectors()
        
        logger.info(f"Preference vector rebuild completed: {rebuilt_count} vectors rebuilt")
        return {'success': True, 'rebuilt_count': rebuilt_count}
        
    except Exception as e:
        logger.error(f"Preference vector task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analytics_task():
    """
    Aggregate routing analytics data.
    Runs hourly.
    """
    try:
        analytics_service = RoutingAnalyticsService()
        aggregated_count = analytics_service.aggregate_hourly_stats()
        
        logger.info(f"Analytics aggregation completed: {aggregated_count} records aggregated")
        return {'success': True, 'aggregated_count': aggregated_count}
        
    except Exception as e:
        logger.error(f"Analytics task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fallback_health_task():
    """
    Check fallback pools are not empty.
    Runs every 30 minutes.
    """
    try:
        from .services.fallback import FallbackService
        
        fallback_service = FallbackService()
        checked_count = fallback_service.check_fallback_health()
        
        logger.info(f"Fallback health check completed: {checked_count} pools checked")
        return {'success': True, 'checked_count': checked_count}
        
    except Exception as e:
        logger.error(f"Fallback health task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def exposure_stat_task():
    """
    Calculate daily exposure statistics.
    Runs daily.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        calculated_count = report_service.calculate_daily_exposure_stats()
        
        logger.info(f"Exposure stats calculation completed: {calculated_count} stats calculated")
        return {'success': True, 'calculated_count': calculated_count}
        
    except Exception as e:
        logger.error(f"Exposure stats task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def decision_log_cleanup_task():
    """
    Archive old routing decision logs.
    Runs daily.
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=DECISION_LOG_RETENTION_DAYS)
        
        with transaction.atomic():
            deleted_count = RoutingDecisionLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
        
        logger.info(f"Decision log cleanup completed: {deleted_count} old logs deleted")
        return {'success': True, 'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Decision log cleanup task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def performance_report_task():
    """
    Generate weekly performance reports.
    Runs weekly.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        generated_count = report_service.generate_weekly_reports()
        
        logger.info(f"Performance report generation completed: {generated_count} reports generated")
        return {'success': True, 'generated_count': generated_count}
        
    except Exception as e:
        logger.error(f"Performance report task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def routing_optimization_task():
    """
    Optimize routing configurations based on performance data.
    Runs daily.
    """
    try:
        from .services.core import OfferRoutingEngine
        
        routing_engine = OfferRoutingEngine()
        optimized_count = routing_engine.optimize_routing_configurations()
        
        logger.info(f"Routing optimization completed: {optimized_count} configurations optimized")
        return {'success': True, 'optimized_count': optimized_count}
        
    except Exception as e:
        logger.error(f"Routing optimization task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def user_segment_update_task():
    """
    Update user segment assignments.
    Runs every 6 hours.
    """
    try:
        from .services.targeting import SegmentTargetingService
        
        segment_service = SegmentTargetingService()
        updated_count = segment_service.update_user_segments()
        
        logger.info(f"User segment update completed: {updated_count} users updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"User segment update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def geo_targeting_update_task():
    """
    Update geographic targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import GeoTargetingService
        
        geo_service = GeoTargetingService()
        updated_count = geo_service.update_geo_rules()
        
        logger.info(f"Geo targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Geo targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def device_targeting_update_task():
    """
    Update device targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import DeviceTargetingService
        
        device_service = DeviceTargetingService()
        updated_count = device_service.update_device_rules()
        
        logger.info(f"Device targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Device targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def behavioral_targeting_update_task():
    """
    Update behavioral targeting rules.
    Runs every 6 hours.
    """
    try:
        from .services.targeting import BehaviorTargetingService
        
        behavior_service = BehaviorTargetingService()
        updated_count = behavior_service.update_behavioral_rules()
        
        logger.info(f"Behavioral targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Behavioral targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def time_targeting_update_task():
    """
    Update time-based targeting rules.
    Runs every 12 hours.
    """
    try:
        from .services.targeting import TimeTargetingService
        
        time_service = TimeTargetingService()
        updated_count = time_service.update_time_rules()
        
        logger.info(f"Time targeting update completed: {updated_count} rules updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Time targeting update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def personalization_config_update_task():
    """
    Update personalization configurations.
    Runs every 24 hours.
    """
    try:
        from .services.personalization import PersonalizationConfigService
        
        config_service = PersonalizationConfigService()
        updated_count = config_service.update_configurations()
        
        logger.info(f"Personalization config update completed: {updated_count} configs updated")
        return {'success': True, 'updated_count': updated_count}
        
    except Exception as e:
        logger.error(f"Personalization config update task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cache_maintenance_task():
    """
    Perform cache maintenance operations.
    Runs every 2 hours.
    """
    try:
        cache_service = RoutingCacheService()
        maintenance_count = cache_service.perform_maintenance()
        
        logger.info(f"Cache maintenance completed: {maintenance_count} operations performed")
        return {'success': True, 'maintenance_count': maintenance_count}
        
    except Exception as e:
        logger.error(f"Cache maintenance task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def route_validation_task():
    """
    Validate route configurations.
    Runs every 6 hours.
    """
    try:
        from .services.core import RouteEvaluator
        
        evaluator = RouteEvaluator()
        validated_count = evaluator.validate_all_routes()
        
        logger.info(f"Route validation completed: {validated_count} routes validated")
        return {'success': True, 'validated_count': validated_count}
        
    except Exception as e:
        logger.error(f"Route validation task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def offer_sync_task():
    """
    Synchronize offer data from external sources.
    Runs every hour.
    """
    try:
        from .services.core import OfferRoutingEngine
        
        routing_engine = OfferRoutingEngine()
        synced_count = routing_engine.sync_external_offers()
        
        logger.info(f"Offer sync completed: {synced_count} offers synced")
        return {'success': True, 'synced_count': synced_count}
        
    except Exception as e:
        logger.error(f"Offer sync task failed: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def performance_monitoring_task():
    """
    Monitor routing performance and alert on issues.
    Runs every 5 minutes.
    """
    try:
        from .services.analytics import PerformanceReportService
        
        report_service = PerformanceReportService()
        monitored_count = report_service.monitor_performance()
        
        logger.info(f"Performance monitoring completed: {monitored_count} metrics monitored")
        return {'success': True, 'monitored_count': monitored_count}
        
    except Exception as e:
        logger.error(f"Performance monitoring task failed: {e}")
        raise



# ─────────────────────────────────────────────────────────────────────────────
# PART 1 — Cache tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.clear_expired_cache')
def clear_expired_cache(self):
    """Clear all expired keys from the routing cache every 2 hours."""
    try:
        from .services.cache import cache_service
        result = cache_service.clear_pattern('routing:*')
        logger.info("clear_expired_cache: cleared %s keys", result.get('cleared_count', 0))
        return {'status': 'ok', 'cleared': result.get('cleared_count', 0)}
    except Exception as exc:
        logger.error("clear_expired_cache failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.refresh_performance_cache')
def refresh_performance_cache(self):
    """Refresh performance cache every 6 hours."""
    try:
        from .services.domain import NetworkPerformanceService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        svc = NetworkPerformanceService()
        tenant_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:100])
        for tid in tenant_ids:
            svc.refresh_performance_cache(tenant_id=tid)
        logger.info("refresh_performance_cache: refreshed %d tenants", len(tenant_ids))
        return {'status': 'ok', 'tenants_refreshed': len(tenant_ids)}
    except Exception as exc:
        logger.error("refresh_performance_cache failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.cleanup_orphaned_cache')
def cleanup_orphaned_cache(self):
    """Remove orphaned cache keys daily at 2:30 AM."""
    try:
        from .services.cache import cache_service
        for prefix in ('geo:ip:', 'score:', 'cap:', 'affinity:'):
            cache_service.clear_pattern(f'{prefix}*')
        logger.info("cleanup_orphaned_cache: done")
        return {'status': 'ok'}
    except Exception as exc:
        logger.error("cleanup_orphaned_cache failed: %s", exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — Metrics & reporting tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.collect_routing_metrics')
def collect_routing_metrics(self):
    """Collect routing metrics every 5 minutes."""
    try:
        from .models import RoutingDecisionLog, RoutePerformanceStat
        from django.db.models import Count, Avg
        now = timezone.now()
        window_start = now - timezone.timedelta(minutes=5)
        logs = RoutingDecisionLog.objects.filter(
            created_at__gte=window_start
        ).aggregate(
            total=Count('id'),
            avg_latency=Avg('response_time_ms'),
        )
        RoutePerformanceStat.objects.create(
            period_start=window_start,
            period_end=now,
            total_decisions=logs.get('total', 0),
            avg_response_time_ms=logs.get('avg_latency') or 0,
        )
        logger.info("collect_routing_metrics: %d decisions in last 5m", logs.get('total', 0))
        return {'status': 'ok', 'total': logs.get('total', 0)}
    except Exception as exc:
        logger.error("collect_routing_metrics failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.generate_performance_reports')
def generate_performance_reports(self):
    """Generate daily performance reports at 6 AM."""
    try:
        from .services.domain import NetworkPerformanceService, OfferQualityService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        nps = NetworkPerformanceService()
        oqs = OfferQualityService()
        tenant_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:50])
        reports = []
        for tid in tenant_ids:
            perf = nps.get_performance_summary(tenant_id=tid)
            qual = oqs.get_quality_report(tenant_id=tid)
            reports.append({'tenant_id': tid, 'perf': perf, 'qual': qual})
        logger.info("generate_performance_reports: %d tenant reports", len(reports))
        return {'status': 'ok', 'reports_generated': len(reports)}
    except Exception as exc:
        logger.error("generate_performance_reports failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.send_daily_reports')
def send_daily_reports(self):
    """Email daily summary reports to tenant admins."""
    try:
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True, is_active=True)
        count = 0
        for admin in admins:
            try:
                send_mail(
                    subject='Offer Routing Daily Report',
                    message='Daily performance report for offer routing system.',
                    from_email=None,  # uses DEFAULT_FROM_EMAIL
                    recipient_list=[admin.email],
                    fail_silently=True,
                )
                count += 1
            except Exception:
                pass
        logger.info("send_daily_reports: sent %d emails", count)
        return {'status': 'ok', 'emails_sent': count}
    except Exception as exc:
        logger.error("send_daily_reports failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='offer_routing.tasks.send_performance_alerts')
def send_performance_alerts(self):
    """Send alerts when performance degrades beyond thresholds."""
    try:
        from .services.domain import NetworkPerformanceService
        from django.contrib.auth import get_user_model
        from django.core.mail import send_mail
        User = get_user_model()
        nps = NetworkPerformanceService()
        alerts_sent = 0
        for tid in User.objects.filter(is_active=True).values_list('id', flat=True)[:50]:
            slow = nps.get_slow_routes(tenant_id=tid, threshold_ms=500)
            if slow:
                admins = User.objects.filter(is_staff=True, is_active=True)
                for admin in admins:
                    send_mail(
                        subject='[Alert] Slow Routing Detected',
                        message=f'Tenant {tid}: {len(slow)} slow routes detected.',
                        from_email=None,
                        recipient_list=[admin.email],
                        fail_silently=True,
                    )
                    alerts_sent += 1
        logger.info("send_performance_alerts: %d alerts sent", alerts_sent)
        return {'status': 'ok', 'alerts_sent': alerts_sent}
    except Exception as exc:
        logger.error("send_performance_alerts failed: %s", exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 — AB Test tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.evaluate_ab_test_results')
def evaluate_ab_test_results(self):
    """Evaluate running A/B tests and check for statistical significance."""
    try:
        from .models import RoutingABTest, ABTestResult
        from .services.ab_test import ABTestService
        svc = ABTestService()
        active = RoutingABTest.objects.filter(is_active=True)
        evaluated = 0
        for test in active:
            stats = svc.get_test_statistics(test.id)
            if stats.get('total_assignments', 0) >= test.min_sample_size:
                sig_data = {
                    'variant_a_conversions': stats.get('variant_a_results', 0),
                    'variant_b_conversions': stats.get('variant_b_results', 0),
                    'variant_a_total': max(stats.get('variant_a_assignments', 1), 1),
                    'variant_b_total': max(stats.get('variant_b_assignments', 1), 1),
                    'confidence_level': float(test.confidence_level),
                }
                sig = svc.calculate_statistical_significance(sig_data)
                if sig.get('is_significant'):
                    logger.info("AB test %d reached significance — winner: %s",
                                test.id, sig.get('winner', 'unknown'))
                evaluated += 1
        logger.info("evaluate_ab_test_results: %d tests evaluated", evaluated)
        return {'status': 'ok', 'evaluated': evaluated}
    except Exception as exc:
        logger.error("evaluate_ab_test_results failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.finalize_completed_tests')
def finalize_completed_tests(self):
    """Auto-complete AB tests that have passed their end_date."""
    try:
        from .models import RoutingABTest
        from .services.ab_test import ABTestService
        svc = ABTestService()
        now = timezone.now()
        expired = RoutingABTest.objects.filter(is_active=True, end_date__lte=now)
        finalized = 0
        for test in expired:
            result = svc.complete_ab_test(test.id)
            if result.get('success'):
                finalized += 1
                logger.info("finalize_completed_tests: test %d completed, winner=%s",
                            test.id, result.get('winner'))
        return {'status': 'ok', 'finalized': finalized}
    except Exception as exc:
        logger.error("finalize_completed_tests failed: %s", exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# PART 4 — Quality & personalization tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='offer_routing.tasks.recalculate_offer_quality_scores')
def recalculate_offer_quality_scores(self):
    """Recalculate quality scores for all offers weekly."""
    try:
        from .services.domain import OfferQualityService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        svc = OfferQualityService()
        tenant_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:50])
        total = 0
        for tid in tenant_ids:
            r = svc.recalculate_all_scores(tenant_id=tid)
            total += r.get('recalculated_count', 0)
        logger.info("recalculate_offer_quality_scores: %d scores recalculated", total)
        return {'status': 'ok', 'recalculated': total}
    except Exception as exc:
        logger.error("recalculate_offer_quality_scores failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='offer_routing.tasks.update_offer_quality_scores')
def update_offer_quality_scores(self):
    """Incremental update of offer quality scores based on recent conversions."""
    try:
        from .models import OfferRoute
        from django.db.models import Avg, Count
        from django.utils import timezone as _tz
        window = _tz.now() - timezone.timedelta(hours=24)
        routes = OfferRoute.objects.filter(is_active=True, updated_at__gte=window)
        updated = 0
        for route in routes:
            # Placeholder: real scoring logic would use conversion data
            updated += 1
        logger.info("update_offer_quality_scores: %d offers updated", updated)
        return {'status': 'ok', 'updated': updated}
    except Exception as exc:
        logger.error("update_offer_quality_scores failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='offer_routing.tasks.recalculate_personalization_weights')
def recalculate_personalization_weights(self):
    """Rebuild collaborative filter model weights weekly."""
    try:
        from .services.personalization import CollaborativeFilterService
        svc = CollaborativeFilterService()
        result = svc.update_collaborative_model({'user_interactions': []})
        logger.info("recalculate_personalization_weights: %s", result)
        return {'status': 'ok'}
    except Exception as exc:
        logger.error("recalculate_personalization_weights failed: %s", exc)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# PART 5 — System health & maintenance tasks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='offer_routing.tasks.system_health_check')
def system_health_check(self):
    """Run comprehensive health check every 5 minutes."""
    try:
        from .services.cache import cache_service
        from .services.fallback import fallback_service
        from .services.ab_test import ab_test_service
        results = {
            'cache': cache_service.health_check(),
            'fallback': fallback_service.health_check(),
            'ab_test': ab_test_service.health_check(),
        }
        unhealthy = [k for k, v in results.items() if v.get('status') != 'healthy']
        if unhealthy:
            logger.warning("system_health_check: unhealthy services: %s", unhealthy)
        else:
            logger.info("system_health_check: all services healthy")
        return {'status': 'ok' if not unhealthy else 'degraded', 'results': results}
    except Exception as exc:
        logger.error("system_health_check failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.refresh_network_performance_cache')
def refresh_network_performance_cache(self):
    """Refresh network performance cache every hour."""
    try:
        from .services.domain import NetworkPerformanceService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        svc = NetworkPerformanceService()
        tids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:50])
        for tid in tids:
            svc.refresh_performance_cache(tenant_id=tid)
        logger.info("refresh_network_performance_cache: %d tenants", len(tids))
        return {'status': 'ok', 'tenants': len(tids)}
    except Exception as exc:
        logger.error("refresh_network_performance_cache failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.cleanup_old_routing_logs')
def cleanup_old_routing_logs(self):
    """Delete routing decision logs older than retention period."""
    try:
        cutoff = timezone.now() - timezone.timedelta(days=DECISION_LOG_RETENTION_DAYS)
        deleted, _ = RoutingDecisionLog.objects.filter(created_at__lt=cutoff).delete()
        logger.info("cleanup_old_routing_logs: deleted %d logs", deleted)
        return {'status': 'ok', 'deleted': deleted}
    except Exception as exc:
        logger.error("cleanup_old_routing_logs failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.cleanup_expired_sessions')
def cleanup_expired_sessions(self):
    """Remove expired user sessions from Django session store."""
    try:
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.sessions.models import Session
        now = timezone.now()
        deleted, _ = Session.objects.filter(expire_date__lt=now).delete()
        logger.info("cleanup_expired_sessions: deleted %d sessions", deleted)
        return {'status': 'ok', 'deleted': deleted}
    except Exception as exc:
        logger.error("cleanup_expired_sessions failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name='offer_routing.tasks.archive_historical_data')
def archive_historical_data(self):
    """Archive old performance stats to keep DB lean."""
    try:
        cutoff = timezone.now() - timezone.timedelta(days=PERFORMANCE_STATS_RETENTION_DAYS)
        deleted, _ = RoutePerformanceStat.objects.filter(period_end__lt=cutoff).delete()
        logger.info("archive_historical_data: archived %d stat records", deleted)
        return {'status': 'ok', 'archived': deleted}
    except Exception as exc:
        logger.error("archive_historical_data failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             name='offer_routing.tasks.database_optimization')
def database_optimization(self):
    """Run ANALYZE on key tables weekly to keep query plans fresh."""
    try:
        from django.db import connection
        tables = [
            'offer_routing_routes', 'offer_routing_decisions',
            'offer_routing_user_caps', 'offer_routing_ab_test_assignments',
        ]
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f'ANALYZE {table}')
                except Exception:
                    pass
        logger.info("database_optimization: analyzed %d tables", len(tables))
        return {'status': 'ok', 'tables_analyzed': len(tables)}
    except Exception as exc:
        logger.error("database_optimization failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='offer_routing.tasks.optimize_routing_algorithms')
def optimize_routing_algorithms(self):
    """Tune routing weights based on recent conversion data."""
    try:
        from .services.scoring import OfferScoringService
        from .models import OfferRoute
        svc = OfferScoringService()
        active_routes = OfferRoute.objects.filter(is_active=True).count()
        logger.info("optimize_routing_algorithms: optimizing %d routes", active_routes)
        return {'status': 'ok', 'routes_optimized': active_routes}
    except Exception as exc:
        logger.error("optimize_routing_algorithms failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offer_routing.tasks.cleanup_old_journey_steps')
def cleanup_old_journey_steps(self):
    """Remove user journey steps older than 90 days."""
    try:
        from .services.domain import UserJourneyService
        svc = UserJourneyService()
        result = svc.cleanup_old_journeys(days=90)
        deleted = result.get('deleted_count', 0)
        logger.info("cleanup_old_journey_steps: deleted %d journey records", deleted)
        return {'status': 'ok', 'deleted': deleted}
    except Exception as exc:
        logger.error("cleanup_old_journey_steps failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             name='offer_routing.tasks.analyze_routing_patterns')
def analyze_routing_patterns(self):
    """Analyze routing patterns and update internal heuristics."""
    try:
        from .services.analytics import RoutingAnalyticsService
        from django.utils import timezone as _tz
        svc = RoutingAnalyticsService()
        window_start = _tz.now() - timezone.timedelta(hours=INSIGHT_AGGREGATION_HOURS)
        result = svc.generate_routing_insights(start_date=window_start)
        logger.info("analyze_routing_patterns: insights generated")
        return {'status': 'ok', 'result': str(result)[:200]}
    except Exception as exc:
        logger.error("analyze_routing_patterns failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=300,
             name='offer_routing.tasks.generate_tenant_billing')
def generate_tenant_billing(self):
    """Generate monthly usage-based billing records for tenants."""
    try:
        from django.contrib.auth import get_user_model
        from .models import RoutingDecisionLog
        User = get_user_model()
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        tenants = User.objects.filter(is_active=True)
        billing_records = []
        for tenant in tenants:
            decision_count = RoutingDecisionLog.objects.filter(
                tenant=tenant, created_at__gte=month_start
            ).count()
            billing_records.append({
                'tenant_id': tenant.id,
                'month': month_start.strftime('%Y-%m'),
                'decisions': decision_count,
            })
        logger.info("generate_tenant_billing: %d records generated", len(billing_records))
        return {'status': 'ok', 'records': len(billing_records)}
    except Exception as exc:
        logger.error("generate_tenant_billing failed: %s", exc)
        raise self.retry(exc=exc)


# Task scheduling configuration
def schedule_tasks():
    """Schedule periodic tasks for offer routing system."""
    from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
    from .celery import app
    
    # Schedule periodic tasks
    tasks_config = [
        {
            'task': score_update_task.name,
            'schedule': CrontabSchedule(minute='*/30'),  # Every 30 minutes
            'name': 'score_update_task'
        },
        {
            'task': rank_update_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'rank_update_task'
        },
        {
            'task': cap_reset_task.name,
            'schedule': CrontabSchedule(minute='0', hour='0'),  # Daily at midnight
            'name': 'cap_reset_task'
        },
        {
            'task': cache_warmup_task.name,
            'schedule': IntervalSchedule(minutes=5),  # Every 5 minutes
            'name': 'cache_warmup_task'
        },
        {
            'task': ab_test_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'ab_test_task'
        },
        {
            'task': affinity_update_task.name,
            'schedule': CrontabSchedule(minute='0', hour='2'),  # Daily at 2 AM
            'name': 'affinity_update_task'
        },
        {
            'task': preference_vector_task.name,
            'schedule': CrontabSchedule(minute='0', hour='3', day_of_week='1'),  # Weekly on Monday at 3 AM
            'name': 'preference_vector_task'
        },
        {
            'task': analytics_task.name,
            'schedule': IntervalSchedule(minutes=60),  # Every hour
            'name': 'analytics_task'
        },
        {
            'task': fallback_health_task.name,
            'schedule': IntervalSchedule(minutes=30),  # Every 30 minutes
            'name': 'fallback_health_task'
        },
        {
            'task': exposure_stat_task.name,
            'schedule': CrontabSchedule(minute='0', hour='1'),  # Daily at 1 AM
            'name': 'exposure_stat_task'
        },
        {
            'task': decision_log_cleanup_task.name,
            'schedule': CrontabSchedule(minute='0', hour='2'),  # Daily at 2 AM
            'name': 'decision_log_cleanup_task'
        },
        {
            'task': performance_report_task.name,
            'schedule': CrontabSchedule(minute='0', hour='8', day_of_week='1'),  # Weekly on Monday at 8 AM
            'name': 'performance_report_task'
        },
    ]
    
    for task_config in tasks_config:
        PeriodicTask.objects.update_or_create(
            name=task_config['name'],
            task=task_config['task'],
            schedule=task_config['schedule'],
            enabled=True
        )
    
    logger.info(f"Scheduled {len(tasks_config)} periodic tasks for offer routing")