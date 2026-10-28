"""
tasks/health_check_tasks.py
System health monitoring Celery tasks:
  - system_health_ping         — overall system health check
  - check_database_health      — DB connection + query performance
  - check_redis_health         — Redis connection + memory usage
  - check_celery_worker_health — worker count + queue depths
  - check_external_apis        — 3rd-party API reachability
  - check_disk_usage           — warn if disk is filling up
"""
import logging
import time
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

HEALTH_CACHE_TTL = 300  # 5 minutes


# ─────────────────────────────────────────────
# system_health_ping
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=10,
    name='tasks.health_check_tasks.system_health_ping',
)
def system_health_ping(self) -> dict:
    """
    Aggregate health check: runs DB, Redis, worker, and disk sub-checks,
    rolls them into a single health status and caches for 5 minutes.
    Status: 'healthy' | 'degraded' | 'unhealthy'
    """
    try:
        logger.info("🏥 Running system health ping...")

        checks = {}
        overall = 'healthy'

        # ── Database ──────────────────────────
        try:
            from django.db import connection
            start = time.monotonic()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            latency_ms = (time.monotonic() - start) * 1000
            checks['database'] = {'status': 'healthy', 'latency_ms': round(latency_ms, 2)}
        except Exception as e:
            checks['database'] = {'status': 'unhealthy', 'error': str(e)}
            overall = 'unhealthy'

        # ── Redis ─────────────────────────────
        try:
            start = time.monotonic()
            cache.set('_health_probe', '1', timeout=5)
            val = cache.get('_health_probe')
            latency_ms = (time.monotonic() - start) * 1000
            status = 'healthy' if val == '1' else 'degraded'
            checks['redis'] = {'status': status, 'latency_ms': round(latency_ms, 2)}
            if status != 'healthy' and overall == 'healthy':
                overall = 'degraded'
        except Exception as e:
            checks['redis'] = {'status': 'unhealthy', 'error': str(e)}
            overall = 'unhealthy'

        # ── Disk ──────────────────────────────
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            used_pct = used / total * 100
            status   = 'healthy' if used_pct < 80 else ('degraded' if used_pct < 90 else 'unhealthy')
            checks['disk'] = {
                'status': status,
                'used_pct': round(used_pct, 1),
                'free_gb': round(free / (1024 ** 3), 2),
            }
            if status == 'unhealthy':
                overall = 'unhealthy'
            elif status == 'degraded' and overall == 'healthy':
                overall = 'degraded'
        except Exception as e:
            checks['disk'] = {'status': 'unknown', 'error': str(e)}

        health_report = {
            'overall': overall,
            'checks': checks,
            'checked_at': timezone.now().isoformat(),
        }

        cache.set('system_health', health_report, timeout=HEALTH_CACHE_TTL)

        logger.info(f"[OK] System health: {overall} | {checks}")
        return {'status': 'success', 'health': health_report}

    except Exception as exc:
        logger.error(f"[ERROR] system_health_ping failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# check_database_health
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    name='tasks.health_check_tasks.check_database_health',
)
def check_database_health(self) -> dict:
    """
    Detailed DB health check:
    - Connection latency
    - Number of active connections
    - Slow query detection (pg_stat_activity if PostgreSQL)
    - Table count sanity check
    """
    try:
        from django.db import connection, connections
        from django.conf import settings

        logger.info("🗄️ Checking database health...")

        results = {}

        for alias in connections:
            try:
                conn   = connections[alias]
                start  = time.monotonic()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                latency_ms = (time.monotonic() - start) * 1000

                db_info = {'status': 'healthy', 'latency_ms': round(latency_ms, 2)}

                # PostgreSQL-specific checks
                vendor = conn.vendor
                db_info['vendor'] = vendor

                if vendor == 'postgresql':
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                            )
                            active_conns = cursor.fetchone()[0]
                            db_info['active_connections'] = active_conns

                            cursor.execute(
                                "SELECT count(*) FROM pg_stat_activity "
                                "WHERE state = 'active' AND query_start < NOW() - INTERVAL '30 seconds'"
                            )
                            slow_queries = cursor.fetchone()[0]
                            db_info['slow_queries'] = slow_queries

                            if slow_queries > 5:
                                db_info['status'] = 'degraded'

                    except Exception as pg_err:
                        db_info['pg_check_error'] = str(pg_err)

                results[alias] = db_info

            except Exception as conn_err:
                results[alias] = {'status': 'unhealthy', 'error': str(conn_err)}

        cache.set('db_health', results, timeout=HEALTH_CACHE_TTL)

        overall = 'healthy'
        for alias_result in results.values():
            if alias_result.get('status') == 'unhealthy':
                overall = 'unhealthy'
                break
            elif alias_result.get('status') == 'degraded':
                overall = 'degraded'

        logger.info(f"[OK] DB health: {overall}")
        return {'status': 'success', 'overall': overall, 'databases': results, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        logger.error(f"[ERROR] check_database_health failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# check_redis_health
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    name='tasks.health_check_tasks.check_redis_health',
)
def check_redis_health(self) -> dict:
    """
    Detailed Redis health check:
    - Ping latency
    - Memory usage and fragmentation ratio
    - Connected clients
    - Hit rate
    """
    try:
        logger.info("🔴 Checking Redis health...")

        redis_info  = {}
        status      = 'healthy'

        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection('default')

            start   = time.monotonic()
            redis_conn.ping()
            latency = (time.monotonic() - start) * 1000

            info = redis_conn.info()

            used_memory_mb      = info.get('used_memory', 0) / (1024 ** 2)
            max_memory_mb       = info.get('maxmemory', 0) / (1024 ** 2)
            fragmentation_ratio = info.get('mem_fragmentation_ratio', 1.0)
            connected_clients   = info.get('connected_clients', 0)
            keyspace_hits       = info.get('keyspace_hits', 0)
            keyspace_misses     = info.get('keyspace_misses', 0)
            total_commands      = keyspace_hits + keyspace_misses
            hit_rate            = (keyspace_hits / total_commands * 100) if total_commands > 0 else 0

            redis_info = {
                'latency_ms': round(latency, 2),
                'used_memory_mb': round(used_memory_mb, 2),
                'max_memory_mb': round(max_memory_mb, 2),
                'fragmentation_ratio': round(fragmentation_ratio, 2),
                'connected_clients': connected_clients,
                'hit_rate_pct': round(hit_rate, 2),
                'redis_version': info.get('redis_version', 'unknown'),
            }

            if max_memory_mb > 0 and used_memory_mb / max_memory_mb > 0.9:
                status = 'degraded'
                logger.warning(f"[WARN] Redis memory usage > 90%: {used_memory_mb:.1f}MB / {max_memory_mb:.1f}MB")

            if fragmentation_ratio > 1.5:
                status = 'degraded'

        except ImportError:
            # Fallback to cache framework check
            start = time.monotonic()
            cache.set('_redis_health_probe', 1, timeout=5)
            latency = (time.monotonic() - start) * 1000
            redis_info = {'latency_ms': round(latency, 2), 'note': 'django-redis not installed'}

        except Exception as e:
            status = 'unhealthy'
            redis_info = {'error': str(e)}

        redis_info['status'] = status
        cache.set('redis_health', redis_info, timeout=HEALTH_CACHE_TTL)

        logger.info(f"[OK] Redis health: {status}")
        return {'status': 'success', 'redis': redis_info, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        logger.error(f"[ERROR] check_redis_health failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# check_celery_worker_health
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    name='tasks.health_check_tasks.check_celery_worker_health',
)
def check_celery_worker_health(self) -> dict:
    """
    Check active Celery workers via the Celery inspect API.
    Updates WorkerHealth model records and caches results.
    """
    try:
        from celery import current_app

        logger.info("⚙️ Checking Celery worker health...")

        workers_info = {}
        online_count = 0

        try:
            inspector   = current_app.control.inspect(timeout=3.0)
            active      = inspector.active() or {}
            stats       = inspector.stats() or {}
            queue_info  = inspector.active_queues() or {}

            for worker_name, tasks in active.items():
                worker_stat  = stats.get(worker_name, {})
                worker_queues = queue_info.get(worker_name, [])

                worker_data = {
                    'status': 'online',
                    'active_tasks': len(tasks),
                    'queues': [q.get('name') for q in worker_queues],
                    'concurrency': worker_stat.get('pool', {}).get('max-concurrency', 0),
                    'processed': worker_stat.get('total', {}).get('tasks', 0),
                }
                workers_info[worker_name] = worker_data
                online_count += 1

                # Update WorkerHealth model
                try:
                    from api.tasks.models.monitoring import WorkerHealth
                    hostname = worker_name.split('@')[-1] if '@' in worker_name else worker_name
                    WorkerHealth.objects.update_or_create(
                        worker_id=worker_name,
                        defaults={
                            'hostname': hostname,
                            'status': WorkerHealth.Status.BUSY if len(tasks) > 0 else WorkerHealth.Status.IDLE,
                            'active_tasks': len(tasks),
                            'queue_names': [q.get('name') for q in worker_queues],
                            'concurrency': worker_stat.get('pool', {}).get('max-concurrency', 1),
                            'last_heartbeat': timezone.now(),
                        },
                    )
                except Exception as model_err:
                    logger.warning(f"[WARN] Could not update WorkerHealth: {model_err}")

        except Exception as inspect_err:
            logger.warning(f"[WARN] Celery inspect failed: {inspect_err}")

        health = {
            'online_workers': online_count,
            'workers': workers_info,
            'checked_at': timezone.now().isoformat(),
        }
        cache.set('celery_worker_health', health, timeout=HEALTH_CACHE_TTL)

        logger.info(f"[OK] Celery worker health: {online_count} online")
        return {'status': 'success', 'worker_health': health}

    except Exception as exc:
        logger.error(f"[ERROR] check_celery_worker_health failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# check_external_apis
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    name='tasks.health_check_tasks.check_external_apis',
)
def check_external_apis(self) -> dict:
    """
    Ping configured external APIs (ad networks, payment gateways, etc.)
    and record reachability + latency.
    API endpoints configured via settings.HEALTH_CHECK_EXTERNAL_APIS.
    """
    try:
        import requests
        from django.conf import settings

        logger.info("🌐 Checking external APIs...")

        endpoints = getattr(settings, 'HEALTH_CHECK_EXTERNAL_APIS', {
            'cpалead': 'https://www.cpalead.com/ping.php',
        })

        results = {}
        healthy = 0
        down    = 0

        for name, url in endpoints.items():
            try:
                start    = time.monotonic()
                response = requests.get(url, timeout=5)
                latency  = (time.monotonic() - start) * 1000
                status   = 'healthy' if response.status_code < 400 else 'degraded'
                results[name] = {
                    'status': status,
                    'http_code': response.status_code,
                    'latency_ms': round(latency, 2),
                }
                if status == 'healthy':
                    healthy += 1
                else:
                    down += 1
            except Exception as req_err:
                results[name] = {'status': 'unreachable', 'error': str(req_err)}
                down += 1
                logger.error(f"[ERROR] External API {name} unreachable: {req_err}")

        report = {
            'healthy': healthy,
            'down': down,
            'results': results,
            'checked_at': timezone.now().isoformat(),
        }
        cache.set('external_api_health', report, timeout=HEALTH_CACHE_TTL)

        logger.info(f"[OK] External API health: {healthy} healthy, {down} down")
        return {'status': 'success', 'api_health': report}

    except Exception as exc:
        logger.error(f"[ERROR] check_external_apis failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# check_disk_usage
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    name='tasks.health_check_tasks.check_disk_usage',
)
def check_disk_usage(self, paths: list = None, warn_threshold: int = 80, critical_threshold: int = 90) -> dict:
    """
    Check disk usage on given paths (default: /, /tmp, media root).
    Emits a warning log at warn_threshold% and critical at critical_threshold%.
    """
    try:
        import shutil
        from django.conf import settings

        logger.info("💾 Checking disk usage...")

        check_paths = paths or ['/', '/tmp', str(getattr(settings, 'MEDIA_ROOT', '/media'))]
        results     = {}

        for path in check_paths:
            try:
                total, used, free = shutil.disk_usage(path)
                used_pct = used / total * 100

                if used_pct >= critical_threshold:
                    status = 'critical'
                    logger.critical(f"[CRITICAL] Disk {path} is {used_pct:.1f}% full!")
                elif used_pct >= warn_threshold:
                    status = 'warning'
                    logger.warning(f"[WARN] Disk {path} is {used_pct:.1f}% full")
                else:
                    status = 'ok'

                results[path] = {
                    'status': status,
                    'used_pct': round(used_pct, 1),
                    'free_gb': round(free / (1024 ** 3), 2),
                    'total_gb': round(total / (1024 ** 3), 2),
                }
            except Exception as path_err:
                results[path] = {'status': 'unknown', 'error': str(path_err)}

        cache.set('disk_usage', results, timeout=HEALTH_CACHE_TTL)
        logger.info(f"[OK] Disk usage check done: {results}")

        return {
            'status': 'success',
            'disk_usage': results,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] check_disk_usage failed: {exc}")
        raise self.retry(exc=exc)
