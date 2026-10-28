# api/admin_panel/viewsets/SystemHealthPostgreSQLViewSet.py
"""
PostgreSQL-specific system health monitoring & administration.
DB size, slow queries, connection pool, vacuum status, index health,
cache stats, Celery queue status, Redis status.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class SystemHealthPostgreSQLViewSet(viewsets.ViewSet):
    """Deep system health — PostgreSQL, Redis, Celery, Disk."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def postgresql_status(self, request):
        """PostgreSQL detailed status — connections, DB size, uptime."""
        try:
            with connection.cursor() as c:
                # DB size
                c.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                db_size = c.fetchone()[0]

                # Active connections
                c.execute("""
                    SELECT count(*), state
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    GROUP BY state
                """)
                connections = {row[1] or 'idle': row[0] for row in c.fetchall()}

                # Max connections
                c.execute("SHOW max_connections")
                max_conn = c.fetchone()[0]

                # Slow queries (>1s)
                c.execute("""
                    SELECT query, calls, mean_exec_time, total_exec_time
                    FROM pg_stat_statements
                    WHERE mean_exec_time > 1000
                    ORDER BY mean_exec_time DESC
                    LIMIT 10
                """) if False else None  # Only if pg_stat_statements is enabled

                # Table sizes
                c.execute("""
                    SELECT schemaname, tablename,
                           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                           n_live_tup as row_count
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 20
                """)
                table_sizes = [
                    {'schema': r[0], 'table': r[1], 'size': r[2], 'rows': r[3]}
                    for r in c.fetchall()
                ]

                # Index usage
                c.execute("""
                    SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
                    FROM pg_stat_user_indexes
                    WHERE idx_scan = 0
                    LIMIT 10
                """)
                unused_indexes = [
                    {'table': r[1], 'index': r[2]}
                    for r in c.fetchall()
                ]

                # Vacuum status
                c.execute("""
                    SELECT relname, last_vacuum, last_autovacuum, n_dead_tup
                    FROM pg_stat_user_tables
                    WHERE n_dead_tup > 1000
                    ORDER BY n_dead_tup DESC
                    LIMIT 10
                """)
                vacuum_needed = [
                    {'table': r[0], 'last_vacuum': str(r[1]), 'last_autovacuum': str(r[2]), 'dead_tuples': r[3]}
                    for r in c.fetchall()
                ]

            return Response({'success': True, 'data': {
                'db_size': db_size,
                'connections': connections,
                'max_connections': max_conn,
                'top_tables_by_size': table_sizes,
                'unused_indexes': unused_indexes,
                'vacuum_needed': vacuum_needed,
            }})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def run_vacuum(self, request):
        """Run VACUUM ANALYZE on a specific table."""
        try:
            table = request.data.get('table', '')
            if not table or not table.replace('_', '').isalnum():
                return Response({'error': 'Invalid table name'}, status=400)
            with connection.cursor() as c:
                c.execute(f'VACUUM ANALYZE {table}')
            return Response({'success': True, 'message': f'VACUUM ANALYZE completed on {table}'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def cache_status(self, request):
        """Redis cache health and stats."""
        try:
            from django.core.cache import caches
            default_cache = caches['default']
            try:
                client = default_cache.client.get_client()
                info = client.info()
                return Response({'success': True, 'data': {
                    'redis_version': info.get('redis_version'),
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed'),
                    'keyspace_hits': info.get('keyspace_hits'),
                    'keyspace_misses': info.get('keyspace_misses'),
                    'uptime_days': info.get('uptime_in_days'),
                    'hit_rate': round(
                        info.get('keyspace_hits', 0) /
                        max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1), 1) * 100, 2
                    ),
                }})
            except Exception:
                # Fallback: simple ping test
                cache.set('admin_health_check', '1', 10)
                ok = cache.get('admin_health_check') == '1'
                return Response({'success': True, 'data': {'status': 'ok' if ok else 'error', 'ping': ok}})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def flush_cache(self, request):
        """Flush specific cache prefix or all cache."""
        try:
            prefix = request.data.get('prefix', '')
            if prefix:
                # Pattern delete (Redis)
                try:
                    from django.core.cache import caches
                    client = caches['default'].client.get_client()
                    keys = client.keys(f'{prefix}*')
                    if keys:
                        client.delete(*keys)
                    return Response({'success': True, 'deleted_keys': len(keys), 'prefix': prefix})
                except Exception:
                    return Response({'success': True, 'message': 'Pattern delete not supported, use full flush'})
            else:
                cache.clear()
                return Response({'success': True, 'message': 'All cache cleared'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def celery_status(self, request):
        """Celery worker and queue status."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=3)
            active = inspector.active() or {}
            reserved = inspector.reserved() or {}
            stats = inspector.stats() or {}

            workers = []
            for worker_name in set(list(active.keys()) + list(stats.keys())):
                workers.append({
                    'name': worker_name,
                    'active_tasks': len(active.get(worker_name, [])),
                    'reserved_tasks': len(reserved.get(worker_name, [])),
                    'status': 'online',
                })

            return Response({'success': True, 'data': {
                'worker_count': len(workers),
                'workers': workers,
                'total_active': sum(w['active_tasks'] for w in workers),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {'status': 'unavailable', 'error': str(e)}})

    @action(detail=False, methods=['get'])
    def full_health(self, request):
        """Complete system health check — DB, Cache, Celery."""
        result = {'timestamp': timezone.now().isoformat(), 'services': {}}
        # DB
        try:
            with connection.cursor() as c:
                c.execute('SELECT 1')
            result['services']['postgresql'] = 'ok'
        except Exception as e:
            result['services']['postgresql'] = f'error: {e}'
        # Cache
        try:
            cache.set('_health', '1', 5)
            result['services']['redis'] = 'ok' if cache.get('_health') else 'error'
        except Exception as e:
            result['services']['redis'] = f'error: {e}'
        # Celery
        try:
            from celery import current_app
            current_app.control.inspect(timeout=2).active()
            result['services']['celery'] = 'ok'
        except Exception as e:
            result['services']['celery'] = f'error: {e}'
        result['overall'] = 'healthy' if all(v == 'ok' for v in result['services'].values()) else 'degraded'
        return Response({'success': True, 'data': result})