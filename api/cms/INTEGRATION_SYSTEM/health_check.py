"""Health check stub."""
from django.core.cache import cache


class HealthChecker:
    @staticmethod
    def get_cached_health(ttl: int = 60) -> dict:
        cached = cache.get('cms:health')
        if cached:
            return cached
        report = HealthChecker.check()
        cache.set('cms:health', report, ttl)
        return report

    @staticmethod
    def check() -> dict:
        checks = {}
        # DB
        try:
            from django.db import connection
            connection.ensure_connection()
            checks['db'] = 'ok'
        except Exception as e:
            checks['db'] = str(e)
        # Cache
        try:
            cache.set('_health_ping', 1, 5)
            checks['cache'] = 'ok' if cache.get('_health_ping') else 'miss'
        except Exception as e:
            checks['cache'] = str(e)

        overall = 'ok' if all(v == 'ok' for v in checks.values()) else 'warn'
        return {'status': overall, 'checks': checks}
