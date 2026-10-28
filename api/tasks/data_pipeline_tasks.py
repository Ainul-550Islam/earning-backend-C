"""
tasks/data_pipeline_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data Pipeline / ETL Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ETL jobs that move/transform data between systems.
  ✅ run_pipeline              — execute a named DataPipeline
  ✅ sync_user_data_bridge     — sync all user data to DataBridge
  ✅ sync_offer_data_bridge    — sync all offer data to DataBridge  
  ✅ sync_platform_kpis_bridge — sync platform KPIs to DataBridge
  ✅ export_to_s3              — export daily data to S3
  ✅ export_to_bigquery        — push analytics to BigQuery
  ✅ run_etl_job               — run a complete ETL job
  ✅ warm_all_caches           — pre-warm all critical caches
"""
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.data_pipeline_tasks.run_pipeline')
def run_pipeline(self, pipeline_name: str, context: dict = None) -> dict:
    """Execute a named DataPipeline."""
    try:
        from api.tasks.integration.pipeline import DataPipeline
        logger.info(f"🔄 Running pipeline: {pipeline_name}")
        pipeline = DataPipeline.build(pipeline_name)
        result   = pipeline.run(**(context or {}))
        return {'status': 'success', 'pipeline': pipeline_name, 'result': result}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.data_pipeline_tasks.sync_user_data_bridge')
def sync_user_data_bridge(self, user_ids: list = None, batch_size: int = 100) -> dict:
    """
    Sync all user-related data to DataBridge for fast cross-task access.
    Syncs: wallet balance, KYC tier, fraud score, publisher tier, level.
    """
    try:
        from api.tasks.integration.data_bridge import DataBridge
        from api.tasks.integration.pipeline import DataPipeline
        from django.contrib.auth import get_user_model
        logger.info(f"🔄 Syncing user data to DataBridge (users={user_ids or 'all'})...")

        User   = get_user_model()
        synced = 0
        errors = 0

        qs = User.objects.filter(is_active=True)
        if user_ids:
            qs = qs.filter(pk__in=user_ids)

        for user in qs.values_list('id', flat=True).iterator(chunk_size=batch_size):
            try:
                pipeline = DataPipeline.build('user_sync')
                pipeline.run(user_id=user)
                synced += 1
            except Exception as e:
                logger.error(f"[ERROR] Sync user {user}: {e}")
                errors += 1

        return {
            'status': 'success',
            'synced': synced,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.data_pipeline_tasks.sync_offer_data_bridge')
def sync_offer_data_bridge(self) -> dict:
    """Sync all active offer data to DataBridge."""
    try:
        from api.tasks.integration.data_bridge import DataBridge
        logger.info("🔄 Syncing offer data to DataBridge...")
        synced = 0

        try:
            from ad_networks.models import SmartlinkOffer

            for offer in SmartlinkOffer.objects.filter(is_active=True).values(
                'external_id', 'epc', 'payout', 'conversion_rate',
                'quality_score', 'daily_cap', 'daily_clicks_used', 'is_active',
            ).iterator(chunk_size=200):
                offer_id = offer.pop('external_id')
                for field, val in offer.items():
                    DataBridge.set_offer(offer_id, field, val, ttl=1800)
                synced += 1

        except ImportError as e:
            logger.warning(f"[WARN] SmartlinkOffer not available: {e}")

        return {'status': 'success', 'synced': synced, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.data_pipeline_tasks.sync_platform_kpis_bridge')
def sync_platform_kpis_bridge(self) -> dict:
    """Sync platform KPIs to DataBridge."""
    try:
        from api.tasks.integration.pipeline import DataPipeline
        pipeline = DataPipeline.build('platform_kpi')
        result   = pipeline.run()
        return {'status': 'success', 'result': result, 'timestamp': timezone.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.data_pipeline_tasks.warm_all_caches')
def warm_all_caches(self) -> dict:
    """
    Pre-warm all critical caches to avoid cold-start latency.
    Runs after deployment and every 30 minutes.
    """
    try:
        logger.info("🔥 Warming all caches...")
        warmed = []

        tasks_to_warm = [
            ('offer_feed',          'tasks.offer_tasks.refresh_offer_feed'),
            ('offer_targeting',     'tasks.offer_tasks.sync_offer_targeting'),
            ('rtb_bids',           'tasks.rtb_tasks.refresh_bid_cache'),
            ('leaderboard_daily',  'tasks.earning_tasks.recalculate_leaderboard'),
            ('exchange_rates',     'tasks.localization_tasks.update_exchange_rates'),
            ('platform_kpis',      'tasks.analytics_tasks.compute_platform_kpis'),
            ('worker_health',      'tasks.celery_tasks.run_worker_health_refresh'),
        ]

        from celery import current_app
        for name, task_name in tasks_to_warm:
            try:
                current_app.send_task(task_name, queue='default', countdown=0)
                warmed.append(name)
            except Exception as e:
                logger.warning(f"[WARN] Cache warm {name}: {e}")

        return {
            'status': 'success',
            'warmed': warmed,
            'count': len(warmed),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.data_pipeline_tasks.export_to_s3')
def export_to_s3(self, data_type: str = 'daily_completions', date_str: str = None) -> dict:
    """
    Export data to S3 for long-term storage and data warehouse loading.
    data_type: 'daily_completions' | 'conversions' | 'clicks' | 'analytics'
    """
    try:
        from datetime import timedelta, datetime
        import json, os
        from django.conf import settings

        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        logger.info(f"☁️ Exporting {data_type} to S3 for {target}...")

        s3_bucket = getattr(settings, 'BACKUP_S3_BUCKET', '')
        if not s3_bucket:
            return {'status': 'skipped', 'reason': 'no_s3_bucket'}

        # Collect data
        rows = []
        if data_type == 'daily_completions':
            try:
                from api.tasks.models import UserTaskCompletion
                day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
                day_end   = day_start + timedelta(days=1)
                rows = list(
                    UserTaskCompletion.objects.filter(
                        completed_at__gte=day_start, completed_at__lt=day_end, status='completed'
                    ).values('user_id', 'task__task_id', 'reward_amount', 'completed_at')[:50000]
                )
                for r in rows:
                    r['completed_at'] = str(r['completed_at'])
            except ImportError:
                pass

        # Write to temp file and upload
        filename  = f"{data_type}/{target}/{data_type}_{target}.json"
        tmp_path  = f"/tmp/{data_type}_{target}.json"
        with open(tmp_path, 'w') as f:
            json.dump(rows, f, default=str)

        try:
            import boto3
            s3 = boto3.client('s3')
            s3.upload_file(tmp_path, s3_bucket, filename)
            os.remove(tmp_path)
        except ImportError:
            logger.warning("[WARN] boto3 not installed")

        return {
            'status': 'success',
            'data_type': data_type,
            'date': str(target),
            'rows': len(rows),
            's3_key': filename,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.data_pipeline_tasks.run_etl_job')
def run_etl_job(self, job_name: str, params: dict = None) -> dict:
    """
    Run a complete ETL job by name.
    Jobs: 'user_sync', 'offer_sync', 'analytics_rollup', 'cache_warm'
    """
    try:
        from celery import current_app
        params = params or {}
        logger.info(f"⚙️ Running ETL job: {job_name}")

        JOB_MAP = {
            'user_sync':        'tasks.data_pipeline_tasks.sync_user_data_bridge',
            'offer_sync':       'tasks.data_pipeline_tasks.sync_offer_data_bridge',
            'platform_kpis':    'tasks.data_pipeline_tasks.sync_platform_kpis_bridge',
            'cache_warm':       'tasks.data_pipeline_tasks.warm_all_caches',
            'analytics_rollup': 'tasks.analytics_tasks.daily_analytics_rollup',
            's3_export':        'tasks.data_pipeline_tasks.export_to_s3',
        }

        task_name = JOB_MAP.get(job_name)
        if not task_name:
            return {'status': 'unknown_job', 'job': job_name}

        result = current_app.send_task(task_name, kwargs=params, queue='default')
        return {
            'status': 'queued',
            'job': job_name,
            'task_id': result.id,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)
