"""
api/tasks/viewset.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Main DRF ViewSets for the task system public API.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from api.tasks.permissions import (
    CanCompleteTask, IsNotSuspended, IsNotFraudFlagged, IsTaskOwner,
)
from api.tasks.pagination import StandardTaskPagination, CursorTaskPagination
from api.tasks.filters import MasterTaskFilter, UserTaskCompletionFilter
from api.tasks.throttling import TaskCompletionThrottle, WithdrawalThrottle
from api.tasks.mixins import (
    BulkActionMixin, CachedRetrieveMixin, ExportMixin, HealthCheckMixin,
)
from api.tasks.schemas import (
    TaskCompleteRequestSchema, CompletionStatsSchema, LeaderboardEntrySchema,
)
from api.tasks.dependencies import (
    get_client_ip, get_device_type, get_country_code, get_request_context,
)

logger = logging.getLogger(__name__)


class MasterTaskViewSet(CachedRetrieveMixin, BulkActionMixin, HealthCheckMixin,
                         ExportMixin, viewsets.ModelViewSet):
    """
    ViewSet for MasterTask CRUD and task management.
    GET  /tasks/               — List active tasks (public)
    POST /tasks/{id}/complete/ — Complete a task (authenticated)
    GET  /tasks/featured/      — Featured tasks
    GET  /tasks/categories/    — Available categories
    GET  /tasks/stats/         — Platform task stats
    """

    pagination_class  = StandardTaskPagination
    filterset_class   = MasterTaskFilter
    cache_ttl         = 300

    def get_serializer_class(self):
        try:
            from api.tasks.serializers import MasterTaskSerializer
            return MasterTaskSerializer
        except ImportError:
            from rest_framework import serializers
            class Fallback(serializers.Serializer):
                task_id = serializers.CharField()
                name    = serializers.CharField()
            return Fallback

    def get_queryset(self):
        try:
            from api.tasks.models import MasterTask
            qs = MasterTask.objects.all()
            if not self.request.user.is_staff:
                qs = qs.filter(is_active=True)
            return qs.order_by(
                '-is_featured',
                'sort_order',
                'task_id',
            )
        except Exception:
            from api.tasks.models import MasterTask
            return MasterTask.objects.none()

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'featured', 'categories'):
            return [IsAuthenticated()]
        if self.action == 'complete':
            return [IsAuthenticated(), CanCompleteTask(), IsNotSuspended()]
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                            'bulk_activate', 'bulk_deactivate', 'bulk_delete'):
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == 'complete':
            return [TaskCompletionThrottle()]
        return []

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """POST /tasks/{id}/complete/ — Complete a task."""
        schema = TaskCompleteRequestSchema(data=request.data)
        if not schema.is_valid():
            return Response(schema.errors, status=status.HTTP_400_BAD_REQUEST)

        task_id    = pk
        user_id    = request.user.pk
        ip_address = get_client_ip(request)
        device     = get_device_type(request)
        country    = get_country_code(request)

        try:
            from api.tasks.hooks import HookRegistry
            ctx = HookRegistry.run('before_task_complete', {
                'task_id':    task_id,
                'user_id':    user_id,
                'ip_address': ip_address,
                'device':     device,
                'country':    country,
            })
        except Exception as e:
            return Response({'error': str(e), 'code': 'pre_check_failed'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            from api.tasks.services.TaskService import TaskService
            result = TaskService().complete_task(
                task_id=task_id,
                user_id=user_id,
                ip_address=ip_address,
                device=device,
                country=country,
                extra_data=schema.validated_data.get('extra_data', {}),
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if result.get('status') in ('success', 'credited'):
            from api.tasks.hooks import HookRegistry
            HookRegistry.run_safe('after_task_complete', {
                **result,
                'user_id':    user_id,
                'task_id':    task_id,
                'ip_address': ip_address,
            })

        return Response(result)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """GET /tasks/featured/ — Featured tasks for display."""
        try:
            from api.tasks.models import MasterTask
            tasks   = MasterTask.objects.filter(is_active=True, is_featured=True)
            country = get_country_code(request)
            device  = get_device_type(request)
            serializer = self.get_serializer(tasks, many=True)
            return Response({'results': serializer.data, 'count': tasks.count()})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """GET /tasks/categories/ — Available task categories with counts."""
        try:
            from api.tasks.models import MasterTask
            from django.db.models import Count
            cats = (MasterTask.objects.filter(is_active=True)
                    .values('category')
                    .annotate(count=Count('id'))
                    .order_by('-count'))
            return Response({'results': list(cats)})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def my_stats(self, request):
        """GET /tasks/my_stats/ — Current user's completion stats."""
        try:
            from api.tasks.integration.shared_context import SharedContext
            ctx  = SharedContext.for_user(request.user.pk)
            return Response(ctx.to_dict())
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class UserTaskCompletionViewSet(ExportMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing task completion history.
    GET /completions/          — Current user's completions
    GET /completions/stats/    — Aggregated stats
    GET /completions/export/   — Export CSV
    """

    pagination_class  = CursorTaskPagination
    filterset_class   = UserTaskCompletionFilter

    def get_serializer_class(self):
        try:
            from api.tasks.serializers import UserTaskCompletionSerializer
            return UserTaskCompletionSerializer
        except ImportError:
            from rest_framework import serializers
            class Fallback(serializers.Serializer):
                id            = serializers.IntegerField()
                status        = serializers.CharField()
                reward_amount = serializers.DecimalField(max_digits=18, decimal_places=8)
                completed_at  = serializers.DateTimeField()
            return Fallback

    def get_queryset(self):
        try:
            from api.tasks.models import UserTaskCompletion
            qs = UserTaskCompletion.objects.select_related('task')
            if not self.request.user.is_staff:
                qs = qs.filter(user=self.request.user)
            return qs.order_by('-completed_at')
        except Exception:
            from api.tasks.models import UserTaskCompletion
            return UserTaskCompletion.objects.none()

    def get_permissions(self):
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """GET /completions/stats/ — Aggregated completion stats."""
        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Sum, Count, Avg
            from datetime import timedelta

            user_id = request.user.pk
            qs      = UserTaskCompletion.objects.filter(user_id=user_id)
            total   = qs.aggregate(
                total_completions=Count('id'),
                total_earned=Sum('reward_amount'),
                avg_reward=Avg('reward_amount'),
            )
            today      = timezone.now().date()
            week_start = timezone.now() - timedelta(days=7)

            today_stats = qs.filter(completed_at__date=today).aggregate(
                completions=Count('id'), earned=Sum('reward_amount')
            )
            week_stats = qs.filter(completed_at__gte=week_start).aggregate(
                completions=Count('id'), earned=Sum('reward_amount')
            )

            return Response({
                'total_completions':  total['total_completions'] or 0,
                'total_earned':       str(total['total_earned'] or Decimal('0')),
                'avg_reward':         str(total['avg_reward'] or Decimal('0')),
                'today_completions':  today_stats['completions'] or 0,
                'today_earned':       str(today_stats['earned'] or Decimal('0')),
                'week_completions':   week_stats['completions'] or 0,
                'week_earned':        str(week_stats['earned'] or Decimal('0')),
                'current_streak':     int(cache.get(f'user_streak_{user_id}', 0)),
                'level':              int(cache.get(f'user_level_{user_id}', 1)),
                'xp_points':          int(cache.get(f'user_xp_{user_id}', 0)),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class LeaderboardViewSet(viewsets.ViewSet):
    """
    ViewSet for leaderboard data.
    GET /leaderboard/          — Default (daily) leaderboard
    GET /leaderboard/weekly/   — Weekly leaderboard
    GET /leaderboard/monthly/  — Monthly leaderboard
    GET /leaderboard/alltime/  — All-time leaderboard
    GET /leaderboard/me/       — Current user's rank
    """

    def get_permissions(self):
        return [IsAuthenticated()]

    def list(self, request):
        period = request.query_params.get('period', 'daily')
        board  = cache.get(f'leaderboard_{period}', [])
        return Response({'period': period, 'results': board[:100]})

    @action(detail=False, methods=['get'])
    def weekly(self, request):
        return Response({'period': 'weekly', 'results': cache.get('leaderboard_weekly', [])[:100]})

    @action(detail=False, methods=['get'])
    def monthly(self, request):
        return Response({'period': 'monthly', 'results': cache.get('leaderboard_monthly', [])[:100]})

    @action(detail=False, methods=['get'])
    def alltime(self, request):
        return Response({'period': 'alltime', 'results': cache.get('leaderboard_alltime', [])[:100]})

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Return the current user's rank across all periods."""
        user_id = request.user.pk
        ranks   = {}
        for period in ('daily', 'weekly', 'monthly', 'alltime'):
            ranks[period] = cache.get(f'user_{period}_rank_{user_id}', None)
        return Response({'user_id': user_id, 'ranks': ranks})


class PlatformStatsViewSet(viewsets.ViewSet):
    """
    Admin-only: Platform KPI and stats API.
    GET /platform/stats/   — Platform KPIs
    GET /platform/health/  — System health
    """

    def get_permissions(self):
        return [IsAdminUser()]

    def list(self, request):
        try:
            from api.tasks.integration.data_bridge import DataBridge
            return Response(DataBridge.get_platform_snapshot())
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def health(self, request):
        from django.db import connection
        import time
        start = time.monotonic()
        try:
            connection.cursor().execute('SELECT 1')
            db_ok = True
        except Exception:
            db_ok = False
        cache_ok = bool(cache.get('_health_check') is not None or
                        cache.set('_health_check', 1, 5) is None)
        return Response({
            'status':     'healthy' if (db_ok and cache_ok) else 'degraded',
            'database':   'ok' if db_ok else 'error',
            'cache':      'ok' if cache_ok else 'error',
            'latency_ms': round((time.monotonic() - start) * 1000, 2),
            'timestamp':  timezone.now().isoformat(),
        })


__all__ = [
    'MasterTaskViewSet', 'UserTaskCompletionViewSet',
    'LeaderboardViewSet', 'PlatformStatsViewSet',
]
