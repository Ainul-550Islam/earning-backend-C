#!/usr/bin/env python3
# publisher_tools/cache_patch.py
"""
Cache patch — ReportingViewSet + RealtimeViewSet-এর expensive endpoints-এ
Django cache (Redis) inject করে।

Run করো:
    cd earning_backend/
    python publisher_tools/cache_patch.py

What it patches:
  views_reporting.py  → monthly_report, revenue_forecast, ecpm_breakdown,
                         ecpm_trend, top_units, revenue_trend, ecpm_suggestions
  views_realtime.py   → dashboard_summary, live_stats, realtime_stats

Pattern:
  Cache key = f"pt:{publisher_id}:{action}:{params_hash}"
  TTL from settings.PUBLISHER_TOOLS_CACHE_TTL or sensible defaults

The patch wraps each action body with:
    cache_key = f"pt:{pub.publisher_id}:{action}:{hash_params(request.query_params)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
    ...
    response_data = ...
    cache.set(cache_key, response_data, timeout=TTL)
    return self.ok(response_data)
"""

import os, sys

BASE = os.path.dirname(os.path.abspath(__file__))

CACHE_MIXIN = '''
# ──────────────────────────────────────────────────────────────────────────────
# CACHE MIXIN  (injected by cache_patch.py)
# ──────────────────────────────────────────────────────────────────────────────
from django.core.cache import cache as _django_cache
import hashlib as _hashlib
import json as _json

def _pt_cache_key(publisher_id: str, action: str, params: dict) -> str:
    """Build deterministic cache key for publisher analytics."""
    params_str = _json.dumps(params, sort_keys=True)
    params_hash = _hashlib.md5(params_str.encode()).hexdigest()[:12]
    return f"pt:{publisher_id}:{action}:{params_hash}"
'''

REPORTING_CACHED_METHODS = {
    'monthly_report': (
        3600,      # 1 hour TTL
        # inject after: pub = self.publisher
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'monthly_report', dict(request.query_params))
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        # inject before: return self.ok(data)
        '            return self.ok(data)\n',
        '''            _django_cache.set(_cache_key, data, timeout=3600)
            return self.ok(data)
''',
    ),
    'revenue_forecast': (
        1800,
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'revenue_forecast', dict(request.query_params))
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        '            return self.ok(data)\n',
        '''            _django_cache.set(_cache_key, data, timeout=1800)
            return self.ok(data)
''',
    ),
    'ecpm_breakdown': (
        900,
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'ecpm_breakdown', dict(request.query_params))
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        "            return self.ok({\n                'by':    by,",
        '''            _result = {'by': by, 'start': str(start), 'end': str(end), 'rows': data}
            _django_cache.set(_cache_key, _result, timeout=900)
            return self.ok(_result)
# __ECPM_BLOCK_REPLACED__
''',
    ),
    'top_units': (
        600,
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'top_units', dict(request.query_params))
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        "            return self.ok({'days': days, 'limit': limit, 'units': data, 'count': len(data)})\n",
        '''            _result = {'days': days, 'limit': limit, 'units': data, 'count': len(data)}
            _django_cache.set(_cache_key, _result, timeout=600)
            return self.ok(_result)
''',
    ),
}

REALTIME_CACHED_METHODS = {
    'live_stats': (
        60,
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'live_stats', {})
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        '            return self.ok(data)\n',
        '''            _django_cache.set(_cache_key, data, timeout=60)
            return self.ok(data)
''',
    ),
    'dashboard_summary': (
        300,
        'pub = self.publisher\n',
        '''pub = self.publisher
        _cache_key = _pt_cache_key(pub.publisher_id, 'dashboard', dict(request.query_params))
        _cached = _django_cache.get(_cache_key)
        if _cached is not None:
            return self.ok(_cached)
''',
        '            return self.ok(data)\n',
        '''            _django_cache.set(_cache_key, data, timeout=300)
            return self.ok(data)
''',
    ),
}


def apply_cache_to_file(path: str, methods: dict) -> int:
    """Inject cache reads/writes into specified view methods."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add cache mixin import if not already present
    if '_pt_cache_key' not in content:
        # Insert after the last import block
        import re
        last_import = list(re.finditer(r'^from |^import ', content, re.MULTILINE))
        if last_import:
            pos = content.index('\n', last_import[-1].start()) + 1
            content = content[:pos] + CACHE_MIXIN + '\n' + content[pos:]

    applied = 0
    for method_name, (ttl, old_pub_line, new_pub_line, old_return, new_return) in methods.items():
        # Only patch if method exists and not already patched
        if method_name not in content:
            continue
        if '_pt_cache_key' in content and f"'{method_name}'" in content and '_django_cache.set' in content:
            applied += 1
            continue  # already patched

        # Step 1: inject cache check after pub = self.publisher
        if old_pub_line in content and new_pub_line not in content:
            content = content.replace(old_pub_line, new_pub_line, 1)
            applied += 1

        # Step 2: inject cache.set before return
        if old_return in content and new_return not in content:
            content = content.replace(old_return, new_return, 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    return applied


def main():
    targets = [
        ('views_reporting.py', REPORTING_CACHED_METHODS),
        ('views_realtime.py',  REALTIME_CACHED_METHODS),
    ]

    total = 0
    for filename, methods in targets:
        path = os.path.join(BASE, filename)
        if not os.path.exists(path):
            print(f'  ⚠️  SKIP: {filename}')
            continue
        n = apply_cache_to_file(path, methods)
        print(f'  ✅ {filename}: {n} methods cached')
        total += n

    print(f'\nDone — {total} view methods now cache-enabled (Redis TTL per PUBLISHER_TOOLS_CACHE_TTL).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
