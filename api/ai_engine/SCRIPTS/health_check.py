"""
api/ai_engine/SCRIPTS/health_check.py
======================================
AI Engine health check script।
Usage: python -m api.ai_engine.SCRIPTS.health_check
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def run_health_check():
    import django
    django.setup()

    from api.ai_engine.models import AIModel
    from django.db import connection

    checks = {}

    # 1. DB connection
    try:
        connection.ensure_connection()
        checks['database'] = {'status': 'ok'}
    except Exception as e:
        checks['database'] = {'status': 'error', 'error': str(e)}

    # 2. Deployed models count
    try:
        deployed = AIModel.objects.filter(status='deployed', is_active=True).count()
        checks['deployed_models'] = {'status': 'ok', 'count': deployed}
    except Exception as e:
        checks['deployed_models'] = {'status': 'error', 'error': str(e)}

    # 3. Cache
    try:
        from django.core.cache import cache
        cache.set('ai_health_check', 'ok', 10)
        val = cache.get('ai_health_check')
        checks['cache'] = {'status': 'ok' if val == 'ok' else 'error'}
    except Exception as e:
        checks['cache'] = {'status': 'error', 'error': str(e)}

    # 4. Celery (optional)
    try:
        from celery import current_app
        current_app.control.ping(timeout=1)
        checks['celery'] = {'status': 'ok'}
    except Exception:
        checks['celery'] = {'status': 'unavailable'}

    all_ok = all(v.get('status') in ('ok', 'unavailable') for v in checks.values())

    print("\n🔍 AI Engine Health Check")
    print("=" * 40)
    for component, result in checks.items():
        icon = "✅" if result['status'] == 'ok' else "⚠️" if result['status'] == 'unavailable' else "❌"
        print(f"{icon} {component:20} → {result['status']}")
        if 'count' in result:
            print(f"   count: {result['count']}")
    print("=" * 40)
    print(f"Overall: {'✅ HEALTHY' if all_ok else '❌ UNHEALTHY'}")

    return all_ok


if __name__ == '__main__':
    ok = run_health_check()
    sys.exit(0 if ok else 1)
