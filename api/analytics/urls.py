from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'events', views.AnalyticsEventViewSet, basename='analytics-event')
router.register(r'user-analytics', views.UserAnalyticsViewSet, basename='user-analytics')
# router.register(r'funnel',    views.FunnelAnalyticsViewSet,    basename='funnel')
# router.register(r'retention', views.RetentionAnalyticsViewSet, basename='retention')
router.register(r'revenue-analytics', views.RevenueAnalyticsViewSet, basename='revenue-analytics')
router.register(r'offer-performance', views.OfferPerformanceViewSet, basename='offer-performance')
router.register(r'dashboards', views.DashboardViewSet, basename='dashboard')
router.register(r'reports', views.ReportViewSet, basename='report')
router.register(r'alert-rules',  views.AlertRuleViewSet,          basename='alert-rule')
router.register(r'alerts',       views.AlertHistoryViewSet,        basename='alert')
router.register(r'funnel',       views.FunnelAnalyticsViewSet,     basename='funnel')     # নতুন
router.register(r'retention',    views.RetentionAnalyticsViewSet,  basename='retention')  # নতুন

app_name = 'analytics'

urlpatterns = [
    # ── Router (ViewSets) ──────────────────────────────────────────────────────
    path('', include(router.urls)),

    # ── Summary ───────────────────────────────────────────────────────────────
    path('summary/', views.AnalyticsSummaryView.as_view(), name='analytics-summary'),

    # ── Charts ────────────────────────────────────────────────────────────────
    path('charts/', views.ChartDataView.as_view(), name='chart-data'),

    # ── Real-time ─────────────────────────────────────────────────────────────
    path('realtime/metrics/',  views.RealTimeMetricsView.as_view(), name='realtime-metrics'),
    path('realtime/ws-token/', views.real_time_ws_token,            name='realtime-ws-token'),

    # ── Export ────────────────────────────────────────────────────────────────
    path('export/', views.ExportAnalyticsView.as_view(), name='export-analytics'),

    # ── Funnel & Retention (missing ছিল) ──────────────────────────────────────
    path('funnel/',    views.FunnelAnalyticsViewSet.as_view({'get': 'list'}),    name='funnel-list'),
    path('retention/', views.RetentionAnalyticsViewSet.as_view({'get': 'list'}), name='retention-list'),

    # ── Health check (dedicated view, summary নয়) ─────────────────────────────
    path('health/', views.HealthCheckView.as_view(), name='analytics-health'),
]