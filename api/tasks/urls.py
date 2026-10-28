"""
tasks/urls.py
Complete URL configuration — all existing + all new viewset routes.
Includes: tasks, completions, admin, monitoring, queues, DLQ, workflows,
          analytics, costs, alerts, workers, health, CPAlead postback endpoints.
"""

import logging
from typing import Optional, List
from django.urls import path, include
from django.conf import settings
from django.views.generic import RedirectView
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.routers import SimpleRouter
from rest_framework import permissions
from django.db import connection

# ── Existing views ─────────────────────────────────────────────────────────
from . import views
from .models import MasterTask

# ── New viewsets ───────────────────────────────────────────────────────────
from .viewsets import (
    TaskResultViewSet,
    ScheduledTaskViewSet,
    TaskQueueViewSet,
    TaskMonitorViewSet,
    TaskPerformanceViewSet,
    WorkerHealthViewSet,
    QueueDepthViewSet,
    TaskAlertViewSet,
    DeadLetterViewSet,
    WorkflowViewSet,
    WorkflowInstanceViewSet,
    TaskInsightViewSet,
    TaskCostViewSet,
    AdminTaskViewSet,
)

logger = logging.getLogger(__name__)

API_VERSION = 'v1'
API_PREFIX  = f'api/{API_VERSION}'


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════

class BulletproofRouter(SimpleRouter):
    def __init__(self, *args, **kwargs):
        self.trailing_slash = kwargs.pop('trailing_slash', '/?')
        super().__init__(*args, **kwargs)


# ── Main router ────────────────────────────────────────────────────────────
router = BulletproofRouter(trailing_slash='/?')

# Existing viewsets (keep all)
router.register(r'tasks',       views.MasterTaskViewSet,    basename='task')
router.register(r'completions', views.TaskCompletionViewSet, basename='completion')
router.register(r'analytics',    views.AnalyticsViewSet,     basename='analytics')

# New monitoring viewsets
# ── New model ViewSets ─────────────────────────────────────────────────────
from .views_new_models import (
    TaskLockViewSet, ProofSubmissionViewSet, TaskDisputeViewSet,
    TaskEventLogViewSet, TaskDependencyViewSet, TaskInventoryViewSet,
    FraudSignalViewSet,
)
router.register(r'task-locks',        TaskLockViewSet,         basename='task-lock')
router.register(r'proof-submissions', ProofSubmissionViewSet,  basename='proof-submission')
router.register(r'disputes',          TaskDisputeViewSet,      basename='dispute')
router.register(r'event-logs',        TaskEventLogViewSet,     basename='event-log')
router.register(r'task-dependencies', TaskDependencyViewSet,   basename='task-dependency')
router.register(r'task-inventory',    TaskInventoryViewSet,    basename='task-inventory')
router.register(r'fraud-signals',     FraudSignalViewSet,      basename='fraud-signal')

router.register(r'task-results',   TaskResultViewSet,       basename='task-result')
router.register(r'task-monitors',  TaskMonitorViewSet,      basename='task-monitor')
router.register(r'task-performance', TaskPerformanceViewSet, basename='task-perf')
router.register(r'task-queues',    TaskQueueViewSet,        basename='task-queue')
router.register(r'task-alerts',    TaskAlertViewSet,        basename='task-alert')
router.register(r'task-insights',  TaskInsightViewSet,      basename='task-insight')
router.register(r'task-costs',     TaskCostViewSet,         basename='task-cost')
router.register(r'dead-letter',    DeadLetterViewSet,       basename='dead-letter')
router.register(r'worker-health',  WorkerHealthViewSet,     basename='worker-health')
router.register(r'queue-depths',   QueueDepthViewSet,       basename='queue-depth')
router.register(r'workflows',      WorkflowViewSet,         basename='workflow')
router.register(r'workflow-instances', WorkflowInstanceViewSet, basename='workflow-instance')
router.register(r'scheduled-tasks', ScheduledTaskViewSet,  basename='scheduled-task')

# ── Admin router ───────────────────────────────────────────────────────────
admin_router = BulletproofRouter(trailing_slash='/?')
admin_router.register(r'tasks',      views.AdminTaskViewSet, basename='admin-task')
admin_router.register(r'task-admin', AdminTaskViewSet,       basename='task-admin')


# ══════════════════════════════════════════════════════════════════════════════
# SWAGGER (optional)
# ══════════════════════════════════════════════════════════════════════════════

DRF_YASG_INSTALLED = False
schema_view = None
try:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    schema_view = get_schema_view(
        openapi.Info(
            title="Task Management API",
            default_version=API_VERSION,
            description="World-class CPAlead-style task + monitoring system API",
            contact=openapi.Contact(email="admin@example.com"),
            license=openapi.License(name="Proprietary"),
        ),
        public=True,
        permission_classes=[permissions.AllowAny],
    )
    DRF_YASG_INSTALLED = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY VIEWS
# ══════════════════════════════════════════════════════════════════════════════

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        from django.core.cache import cache
        cache.set('_hc', 1, 5)
        return JsonResponse({
            'status': 'healthy',
            'version': API_VERSION,
            'timestamp': timezone.now().isoformat(),
            'services': {'api': 'ok', 'database': 'ok', 'cache': 'ok'},
        })
    except Exception as e:
        return JsonResponse({'status': 'unhealthy', 'error': str(e)}, status=500)


def robots_txt(request):
    content = "User-agent: *\nDisallow: /\n" if settings.DEBUG else "User-agent: *\nAllow: /\n"
    return HttpResponse(content, content_type='text/plain')


def performance_dashboard(request):
    from time import time
    start = time()
    queries = len(connection.queries)
    query_time = sum(float(q.get('time', 0)) for q in connection.queries)
    return JsonResponse({
        'request_time': round(time() - start, 4),
        'database_queries': queries,
        'database_time': round(query_time, 4),
        'timestamp': timezone.now().isoformat(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def handler400(request, exception=None):
    return JsonResponse({'error': 'Bad Request', 'path': request.path,
                         'timestamp': timezone.now().isoformat()}, status=400)

def handler403(request, exception=None):
    return JsonResponse({'error': 'Permission Denied', 'path': request.path,
                         'timestamp': timezone.now().isoformat()}, status=403)

def handler404(request, exception=None):
    return JsonResponse({'error': 'Not Found', 'path': request.path,
                         'timestamp': timezone.now().isoformat()}, status=404)

def handler500(request):
    return JsonResponse({'error': 'Internal Server Error',
                         'path': getattr(request, 'path', ''),
                         'timestamp': timezone.now().isoformat()}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# URL CONVERTERS
# ══════════════════════════════════════════════════════════════════════════════

from django.urls import register_converter

class TaskIDConverter:
    regex = '[A-Za-z0-9_]+'
    def to_python(self, value): return str(value)
    def to_url(self, value): return str(value)

class PositiveIntConverter:
    regex = '[1-9][0-9]*'
    def to_python(self, value): return int(value)
    def to_url(self, value): return str(value)

try:
    register_converter(TaskIDConverter, 'task_id')
    register_converter(PositiveIntConverter, 'posint')
except Exception:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# URL PATTERNS
# ══════════════════════════════════════════════════════════════════════════════

urlpatterns = []

# ── Swagger / ReDoc ────────────────────────────────────────────────────────
if DRF_YASG_INSTALLED and schema_view:
    urlpatterns += [
        path('swagger/',      schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        path('redoc/',        schema_view.with_ui('redoc',   cache_timeout=0), name='schema-redoc'),
        path('swagger.json',  schema_view.without_ui(cache_timeout=0),         name='schema-json'),
    ]

# ── Health ─────────────────────────────────────────────────────────────────
urlpatterns += [
    path('health/',        views.HealthCheckView.as_view(), name='health-check'),
    path('health/simple/', health_check,                    name='simple-health'),
]

# ── Existing task-specific paths (KEEP ALL) ────────────────────────────────
urlpatterns += [
    path('tasks/dashboard-stats/',   views.task_dashboard_stats,  name='task-dashboard-stats'),
    path('tasks/bulk-activate/',     views.bulk_activate,          name='bulk-activate'),
    path('tasks/bulk-deactivate/',   views.bulk_deactivate,        name='bulk-deactivate'),
    path('admin-ledger/',            views.admin_ledger_list,       name='admin-ledger'),
    path('admin-ledger/profit-summary/', views.admin_profit_summary, name='profit-summary'),
    path('admin-ledger/daily-profit/',   views.admin_daily_profit,  name='daily-profit'),
    path('admin-ledger/by-source/',      views.admin_profit_by_source, name='profit-by-source'),
    path('statistics/',              views.TaskStatisticsView.as_view(), name='task-statistics'),
    
    # ── Analytics endpoints ────────────────────────────────────
    path('analytics/dashboard/',       views.AnalyticsViewSet.as_view({'get': 'dashboard'}),       name='analytics-dashboard'),
    path('analytics/real-time/',      views.AnalyticsViewSet.as_view({'get': 'real_time_analytics'}), name='analytics-real-time'),
    path('analytics/trends/',         views.AnalyticsViewSet.as_view({'get': 'analytics_trends'}),      name='analytics-trends'),
    path('analytics/user-behavior/', views.AnalyticsViewSet.as_view({'get': 'user_behavior_analytics'}), name='analytics-user-behavior'),
    
    # ── Advanced task endpoints ───────────────────────────────
    path('tasks/by-system/',           views.MasterTaskViewSet.as_view({'get': 'by_system'}),           name='tasks-by-system'),
    path('tasks/featured/',            views.MasterTaskViewSet.as_view({'get': 'featured_tasks'}),      name='tasks-featured'),
    path('tasks/<task_id>/check/',     views.MasterTaskViewSet.as_view({'get': 'check_availability'}), name='task-check-availability'),
    path('tasks/<task_id>/stats/',     views.MasterTaskViewSet.as_view({'get': 'task_statistics'}),      name='task-statistics'),
    path('tasks/bulk-import/',         views.MasterTaskViewSet.as_view({'post': 'bulk_import_tasks'}),    name='tasks-bulk-import'),
    
    # ── Completion endpoints ───────────────────────────────────
    path('completions/stats/',        views.TaskCompletionViewSet.as_view({'get': 'completion_stats'}),  name='completion-stats'),
    path('completions/streak/',       views.TaskCompletionViewSet.as_view({'get': 'completion_streak'}), name='completion-streak'),
    path('completions/history/',      views.TaskCompletionViewSet.as_view({'get': 'completion_history'}), name='completion-history'),
    
    # ── User dashboard endpoints ─────────────────────────────
    # FIX: Django 4+ dropped string-based view references — use callable imports
    path('user/dashboard/',    views.user_dashboard_view,    name='user-dashboard'),
    path('user/profile/',      views.user_profile_view,      name='user-profile'),
    path('user/achievements/', views.user_achievements_view, name='user-achievements'),

    # ── Admin analytics endpoints ─────────────────────────────
    path('admin/analytics/',   views.admin_analytics_view,   name='admin-analytics'),
    path('admin/performance/', views.admin_performance_view, name='admin-performance'),
    path('admin/revenue/',     views.admin_revenue_view,     name='admin-revenue'),
    path('admin/users/',       views.admin_users_view,       name='admin-users'),
]

# ── Router (all viewsets) ──────────────────────────────────────────────────
urlpatterns += [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
]

# ── Monitoring shortcuts ───────────────────────────────────────────────────
urlpatterns += [
    path('dashboard/',     AdminTaskViewSet.as_view({'get': 'dashboard'}),    name='admin-dashboard'),
    path('system-health/', AdminTaskViewSet.as_view({'get': 'health'}),        name='system-health'),
]

# ── SEO ────────────────────────────────────────────────────────────────────
if not settings.DEBUG:
    urlpatterns += [
        path('robots.txt', robots_txt, name='robots-txt'),
    ]

# ── Debug performance ──────────────────────────────────────────────────────
if settings.DEBUG:
    urlpatterns += [
        path('debug/performance/', performance_dashboard, name='performance-dashboard'),
    ]
else:
    urlpatterns += [
        path('admin/performance/', staff_member_required(performance_dashboard), name='performance-dashboard'),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE MODE MIDDLEWARE
# ══════════════════════════════════════════════════════════════════════════════

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)

    def __call__(self, request):
        if self.maintenance_mode:
            if not request.path.startswith('/admin/') and not getattr(request.user, 'is_staff', False):
                return JsonResponse({'status': 'maintenance', 'message': 'System under maintenance.'}, status=503)
        return self.get_response(request)


# ══════════════════════════════════════════════════════════════════════════════
# URL NAMES CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

class URLNames:
    # Existing
    TASK_LIST        = 'task-list'
    TASK_DETAIL      = 'task-detail'
    COMPLETION_LIST  = 'completion-list'
    COMPLETION_DETAIL = 'completion-detail'
    ADMIN_TASK_LIST  = 'admin-task-list'
    STATISTICS       = 'task-statistics'
    HEALTH_CHECK     = 'health-check'
    ANALYTICS        = 'analytics'
    ANALYTICS_DASHBOARD = 'analytics-dashboard'
    ANALYTICS_REALTIME = 'analytics-real-time'
    ANALYTICS_TRENDS = 'analytics-trends'
    ANALYTICS_BEHAVIOR = 'analytics-user-behavior'
    # New
    TASK_RESULT_LIST     = 'task-result-list'
    TASK_MONITOR_LIST    = 'task-monitor-list'
    DEAD_LETTER_LIST     = 'dead-letter-list'
    WORKFLOW_LIST        = 'workflow-list'
    TASK_INSIGHT_LIST    = 'task-insight-list'
    TASK_COST_LIST       = 'task-cost-list'
    WORKER_HEALTH_LIST   = 'worker-health-list'
    QUEUE_DEPTH_LIST     = 'queue-depth-list'
    TASK_ALERT_LIST      = 'task-alert-list'
    SCHEDULED_TASK_LIST  = 'scheduled-task-list'
    ADMIN_DASHBOARD      = 'admin-dashboard'


__all__ = [
    'urlpatterns', 'router', 'admin_router', 'URLNames',
    'handler400', 'handler403', 'handler404', 'handler500',
    'MaintenanceModeMiddleware',
]


# ══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS — Offerwall, Postbacks, WebSocket, Upload, Admin
# ══════════════════════════════════════════════════════════════════════════════

from api.tasks.endpoint import (
    offerwall_view, complete_task_view,
    user_dashboard_view, admin_platform_stats_view,
)
from api.tasks.webhooks import (
    incoming_postback, cpalead_postback, mmp_postback,
)
from api.tasks.attachment_upload_view import (
    upload_task_proof, upload_kyc_document,
)

# Append to urlpatterns
urlpatterns += [
    # Offerwall
    path('offerwall/',                    offerwall_view,            name='offerwall'),
    path('dashboard/',                    user_dashboard_view,       name='user-dashboard'),
    path('complete/<str:task_id>/',       complete_task_view,        name='complete-task'),
    path('admin/platform-stats/',         admin_platform_stats_view, name='admin-platform-stats'),

    # Postbacks
    path('postback/',                     incoming_postback,         name='postback'),
    path('cpalead/postback/',             cpalead_postback,          name='cpalead-postback'),
    path('mmp/<str:mmp>/postback/',       mmp_postback,              name='mmp-postback'),

    # ── Internet Connectivity + Aging Task Endpoints ──────────────────────
    path('connectivity/',                 views.connectivity_status_view,    name='connectivity-status'),
    path('connectivity/probe/',           views.connectivity_probe_now_view,  name='connectivity-probe'),
    path('aging-tasks/',                  views.aging_tasks_report_view,      name='aging-tasks-report'),
    path('aging-tasks/recover/',          views.aging_tasks_recover_view,     name='aging-tasks-recover'),
    path('stale-locks/',                  views.stale_locks_report_view,      name='stale-locks-report'),
    path('stale-locks/force-release/',    views.force_release_lock_view,      name='stale-locks-force-release'),

    # Platform-specific postback endpoints (OGAds, AdGate, OfferToro, Monlix)
    # Each view queues the platform-specific Celery task after basic IP/auth check
    path('postback/ogads/',       views.ogads_postback_view,      name='ogads-postback'),
    path('postback/adgate/',      views.adgate_postback_view,     name='adgate-postback'),
    path('postback/offertoro/',   views.offertoro_postback_view,  name='offertoro-postback'),
    path('postback/monlix/',      views.monlix_postback_view,     name='monlix-postback'),

    # File uploads
    path('upload/proof/',                 upload_task_proof,         name='upload-proof'),
    path('upload/kyc/',                   upload_kyc_document,       name='upload-kyc'),
]

# ViewSets for new endpoints
from rest_framework.routers import DefaultRouter as _NewRouter
from api.tasks.viewset import (
    MasterTaskViewSet, UserTaskCompletionViewSet,
    LeaderboardViewSet, PlatformStatsViewSet,
)
from api.tasks.viewset_cap import OfferCapViewSet
from api.tasks.webhooks import WebhookEndpointViewSet

_new_router = _NewRouter()
_new_router.register(r'v2/tasks',       MasterTaskViewSet,         basename='v2-task')
_new_router.register(r'v2/completions', UserTaskCompletionViewSet, basename='v2-completion')
_new_router.register(r'v2/leaderboard', LeaderboardViewSet,        basename='v2-leaderboard')
_new_router.register(r'v2/platform',    PlatformStatsViewSet,      basename='v2-platform')
_new_router.register(r'v2/caps',        OfferCapViewSet,           basename='v2-caps')
_new_router.register(r'v2/webhooks',    WebhookEndpointViewSet,    basename='v2-webhooks')

urlpatterns += _new_router.urls

# ── New viewset routes (coverage gap fix) ─────────────────────────────────────
from rest_framework.routers import DefaultRouter as _ExtRouter
from api.tasks.viewsets.DisputeEscalationViewSet import DisputeEscalationViewSet
from api.tasks.viewsets.RateLimitConfigViewSet    import RateLimitConfigViewSet
from api.tasks.viewsets.TenantViewSet             import TenantViewSet
from api.tasks.viewsets.WorkflowLogViewSet        import WorkflowLogViewSet
from api.tasks.viewsets.WorkflowTriggerViewSet    import WorkflowTriggerViewSet
from api.tasks.viewsets.TaskRetryConfigViewSet    import TaskRetryConfigViewSet
from api.tasks.viewsets.TaskFailureRateViewSet    import TaskFailureRateViewSet
from api.tasks.viewsets.TaskThroughputViewSet     import TaskThroughputViewSet
from api.tasks.viewsets.TaskPriorityViewSet       import TaskPriorityViewSet

_ext_router = _ExtRouter()
_ext_router.register(r'v2/dispute-escalations', DisputeEscalationViewSet, basename='dispute-escalation')
_ext_router.register(r'v2/rate-limit-configs',  RateLimitConfigViewSet,   basename='rate-limit-config')
_ext_router.register(r'v2/tenants',             TenantViewSet,            basename='tenant')
_ext_router.register(r'v2/workflow-logs',       WorkflowLogViewSet,       basename='workflow-log')
_ext_router.register(r'v2/workflow-triggers',   WorkflowTriggerViewSet,   basename='workflow-trigger')
_ext_router.register(r'v2/retry-configs',       TaskRetryConfigViewSet,   basename='retry-config')
_ext_router.register(r'v2/failure-rates',       TaskFailureRateViewSet,   basename='failure-rate')
_ext_router.register(r'v2/throughput',          TaskThroughputViewSet,    basename='throughput')
_ext_router.register(r'v2/task-priorities',     TaskPriorityViewSet,      basename='task-priority')

urlpatterns += _ext_router.urls
