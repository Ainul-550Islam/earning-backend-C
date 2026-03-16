# api/cache/views.py  —  COMPLETE CRUD + 3 NEW ENDPOINTS
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.core.cache import cache as dj_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
import json
import logging

from api.cache.decorators import cache_data, cache_view
from api.cache.keys import generate_key

logger = logging.getLogger(__name__)


# ═══════════════════════════════ READ ══════════════════════════════════════════

def cache_stats_view(request):
    """GET /cache/  →  Redis stats"""
    from api.cache.manager import cache_manager
    try:
        stats  = cache_manager.get_stats()
        backend = cache_manager.config.get('default_backend', 'redis')
        healthy = cache_manager.health_check()
        return JsonResponse({
            'backend':         backend.upper(),
            'status':          'active' if healthy else 'inactive',
            'redis_version':   stats.get('redis_version'),
            'used_memory':     stats.get('used_memory'),
            'keyspace_hits':   stats.get('keyspace_hits'),
            'keyspace_misses': stats.get('keyspace_misses'),
            'uptime_seconds':  stats.get('uptime_in_seconds'),
        })
    except Exception as e:
        return JsonResponse({'backend': 'unknown', 'status': 'error', 'message': str(e)}, status=500)


@cache_view(timeout=300, vary_on_user=True)
def cached_user_profile(request, user_id):
    """GET /cache/user/<id>/profile/  →  cached user"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({'id': user.id, 'username': user.username, 'email': user.email})
    except User.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@cache_view(timeout=60, cache_anonymous_only=True)
def cached_system_stats(request):
    """GET /cache/stats/  →  total_users, leaderboard"""
    return JsonResponse(_get_system_stats())


@cache_data(timeout=60, key_prefix='system_stats')
def _get_system_stats():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        total_users = User.objects.count()
        return {'total_users': total_users}
    except Exception:
        return {'total_users': 0}


class CachedTaskView(View):
    """GET /cache/task/<id>/"""
    @method_decorator(cache_view(timeout=30, key_prefix='task_detail'))
    def get(self, request, task_id):
        try:
            from api.tasks.models import MasterTask
            task = MasterTask.objects.get(id=task_id)
            return JsonResponse({'id': task.id, 'name': task.name, 'description': task.description})
        except Exception:
            return JsonResponse({'error': 'Not found'}, status=404)


# ═══════════════════════════════ NEW: HEALTH CHECK ═════════════════════════════

def cache_health_view(request):
    """
    ✅ NEW — GET /cache/health/
    Returns detailed health status of the cache backend.
    """
    from api.cache.manager import cache_manager
    try:
        healthy = cache_manager.health_check()
        backend = cache_manager.config.get('default_backend', 'redis')
        # Try a quick set/get ping
        ping_ok = False
        try:
            dj_cache.set('_health_ping', '1', timeout=5)
            ping_ok = dj_cache.get('_health_ping') == '1'
            dj_cache.delete('_health_ping')
        except Exception:
            pass

        return JsonResponse({
            'healthy':  healthy and ping_ok,
            'backend':  backend.upper(),
            'ping':     ping_ok,
            'message':  'Cache is healthy' if (healthy and ping_ok) else 'Cache degraded or unreachable',
        })
    except Exception as e:
        return JsonResponse({'healthy': False, 'backend': 'unknown', 'message': str(e)}, status=500)


# ═══════════════════════════════ NEW: KEYS LIST ════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cache_keys_list(request):
    """
    ✅ NEW — GET /cache/keys/?pattern=user*&limit=50
    List cache keys matching a pattern (admin only).
    """
    pattern = request.query_params.get('pattern', '*')
    limit   = min(int(request.query_params.get('limit', 50)), 200)
    try:
        from django_redis import get_redis_connection
        con  = get_redis_connection('default')
        keys = [k.decode() if isinstance(k, bytes) else k
                for k in con.keys(pattern)[:limit]]
        keys.sort()
        # Optionally fetch TTL for each key
        result = []
        for key in keys:
            ttl = con.ttl(key)
            result.append({'key': key, 'ttl': ttl if ttl >= 0 else None})
        return Response({'count': len(result), 'pattern': pattern, 'keys': result})
    except Exception as e:
        # Fallback if django_redis not available
        return Response({'count': 0, 'pattern': pattern, 'keys': [], 'error': str(e)}, status=200)


# ═══════════════════════════════ NEW: DELETE SPECIFIC KEY ══════════════════════

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cache_key_delete(request):
    """
    ✅ NEW — DELETE /cache/key/
    Delete a specific key or pattern (admin only).
    Body: { "key": "user:123:profile" }
      or  { "pattern": "user:*" }
    """
    key     = request.data.get('key')
    pattern = request.data.get('pattern')

    if not key and not pattern:
        return Response({'error': 'key or pattern is required'}, status=400)

    deleted = 0
    try:
        from django_redis import get_redis_connection
        con = get_redis_connection('default')
        if key:
            deleted = con.delete(key)
        elif pattern:
            matched = con.keys(pattern)
            if matched:
                deleted = con.delete(*matched)
    except Exception:
        # Fallback to Django cache API
        if key:
            dj_cache.delete(key)
            deleted = 1

    return Response({
        'success': True,
        'deleted': deleted,
        'key':     key,
        'pattern': pattern,
    })


# ═══════════════════════════════ NEW: SET KEY (admin) ══════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cache_key_set(request):
    """
    ✅ NEW — POST /cache/set/
    Manually set a cache key (admin only).
    Body: { "key": "my_key", "value": "any_value", "timeout": 300 }
    """
    key     = request.data.get('key')
    value   = request.data.get('value')
    timeout = request.data.get('timeout', 300)

    if not key:
        return Response({'error': 'key is required'}, status=400)
    if value is None:
        return Response({'error': 'value is required'}, status=400)

    try:
        dj_cache.set(key, value, timeout=int(timeout))
        # Verify
        stored = dj_cache.get(key)
        return Response({
            'success': True,
            'key':     key,
            'timeout': timeout,
            'stored':  stored == value,
        }, status=201)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


# ═══════════════════════════════ CLEAR (existing, fixed) ═══════════════════════

@csrf_exempt
@require_POST
def cache_clear_view(request):
    """POST /cache/clear/  →  flush cache by type"""
    try:
        body       = json.loads(request.body or b'{}')
        cache_type = body.get('type', 'all')
        try:
            from django_redis import get_redis_connection
            con = get_redis_connection('default')
            if cache_type == 'all':
                con.flushdb()
            else:
                keys = con.keys(f'*{cache_type}*')
                if keys:
                    con.delete(*keys)
        except Exception:
            dj_cache.clear()
        return JsonResponse({'success': True, 'message': f'{cache_type} cache cleared'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─── Leaderboard ───────────────────────────────────────────────────────────────

try:
    from api.cache.decorators.cache_view import cache_api_method
    class CachedLeaderboardAPIView(APIView):
        @cache_api_method(timeout=60, key_prefix='leaderboard')
        def get(self, request):
            return Response(_get_leaderboard_data())
except ImportError:
    CachedLeaderboardAPIView = None


@cache_data(timeout=60, key_prefix='leaderboard_data')
def _get_leaderboard_data():
    try:
        from api.wallet.models import Wallet
        top = Wallet.objects.select_related('user').order_by('-total_earned')[:10]
        return {'leaderboard': [{'username': w.user.username, 'total_earned': str(w.total_earned)} for w in top]}
    except ImportError:
        return {'leaderboard': []}


# ─── Service layer ──────────────────────────────────────────────────────────────

class CachedUserService:
    @staticmethod
    @cache_data(timeout=300, key_func=lambda user_id: generate_key('user_profile', user_id=user_id))
    def get_user_profile(user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        return {'id': user.id, 'username': user.username, 'email': user.email}

    @staticmethod
    @cache_data(timeout=60, key_func=lambda task_id: generate_key('task_detail', task_id=task_id))
    def get_task_detail(task_id):
        from api.tasks.models import MasterTask
        return MasterTask.objects.get(id=task_id)