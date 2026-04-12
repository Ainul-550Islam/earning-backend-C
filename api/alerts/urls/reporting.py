# alerts/urls/reporting.py
from django.urls import path
from ..viewsets import reporting as viewsets_reporting

app_name = 'reporting'

urlpatterns = [
    # Alert Reports
    path('', viewsets_reporting.AlertReportViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-report-list'),
    path('<int:pk>/', viewsets_reporting.AlertReportViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-report-detail'),
    path('<int:pk>/generate/', viewsets_reporting.AlertReportViewSet.as_view({'post': 'generate'}), name='alert-report-generate'),
    path('<int:pk>/distribute/', viewsets_reporting.AlertReportViewSet.as_view({'post': 'distribute'}), name='alert-report-distribute'),
    path('<int:pk>/schedule_next_run/', viewsets_reporting.AlertReportViewSet.as_view({'post': 'schedule_next_run'}), name='alert-report-schedule-next-run'),
    path('by_type/<str:type>/', viewsets_reporting.AlertReportViewSet.as_view({'get': 'by_type'}), name='alert-report-by-type'),
    path('by_status/<str:status>/', viewsets_reporting.AlertReportViewSet.as_view({'get': 'by_status'}), name='alert-report-by-status'),
    path('recent/', viewsets_reporting.AlertReportViewSet.as_view({'get': 'recent'}), name='alert-report-recent'),
    path('<int:pk>/export/', viewsets_reporting.AlertReportViewSet.as_view({'post': 'export'}), name='alert-report-export'),
    
    # MTTR Metrics
    path('mttr/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'list', 'post': 'create'}), name='mttr-metric-list'),
    path('mttr/<int:pk>/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='mttr-metric-detail'),
    path('mttr/<int:pk>/calculate/', viewsets_reporting.MTTRMetricViewSet.as_view({'post': 'calculate'}), name='mttr-metric-calculate'),
    path('mttr/<int:pk>/by_severity/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'by_severity'}), name='mttr-metric-by-severity'),
    path('mttr/<int:pk>/trends/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'trends'}), name='mttr-metric-trends'),
    path('mttr/<int:pk>/compliance_badge/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'compliance_badge'}), name='mttr-metric-compliance-badge'),
    path('mttr/by_period/<int:days>/', viewsets_reporting.MTTRMetricViewSet.as_view({'get': 'by_period'}), name='mttr-metric-by-period'),
    
    # MTTD Metrics
    path('mttd/', viewsets_reporting.MTTDMetricViewSet.as_view({'get': 'list', 'post': 'create'}), name='mttd-metric-list'),
    path('mttd/<int:pk>/', viewsets_reporting.MTTDMetricViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='mttd-metric-detail'),
    path('mttd/<int:pk>/calculate/', viewsets_reporting.MTTDMetricViewSet.as_view({'post': 'calculate'}), name='mttd-metric-calculate'),
    path('mttd/<int:pk>/quality_badge/', viewsets_reporting.MTTDMetricViewSet.as_view({'get': 'quality_badge'}), name='mttd-metric-quality-badge'),
    path('mttd/<int:pk>/update_rates/', viewsets_reporting.MTTDMetricViewSet.as_view({'post': 'update_rates'}), name='mttd-metric-update-rates'),
    
    # SLA Breaches
    path('sla_breaches/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'list', 'post': 'create'}), name='sla-breach-list'),
    path('sla_breaches/<int:pk>/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='sla-breach-detail'),
    path('sla_breaches/<int:pk>/acknowledge/', viewsets_reporting.SLABreachViewSet.as_view({'post': 'acknowledge'}), name='sla-breach-acknowledge'),
    path('sla_breaches/<int:pk>/resolve/', viewsets_reporting.SLABreachViewSet.as_view({'post': 'resolve'}), name='sla-breach-resolve'),
    path('sla_breaches/<int:pk>/escalate/', viewsets_reporting.SLABreachViewSet.as_view({'post': 'escalate'}), name='sla-breach-escalate'),
    path('sla_breaches/by_severity/<str:severity>/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'by_severity'}), name='sla-breach-by-severity'),
    path('sla_breaches/by_type/<str:type>/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'by_type'}), name='sla-breach-by-type'),
    path('sla_breaches/active/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'active'}), name='sla-breach-active'),
    path('sla_breaches/statistics/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'statistics'}), name='sla-breach-statistics'),
    path('sla_breaches/<int:pk>/impact_score/', viewsets_reporting.SLABreachViewSet.as_view({'get': 'impact_score'}), name='sla-breach-impact-score'),
    
    # Reporting Dashboard
    path('dashboard/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'list'}), name='reporting-dashboard-list'),
    path('dashboard/reports_summary/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'reports_summary'}), name='reporting-dashboard-reports-summary'),
    path('dashboard/mttr_summary/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'mttr_summary'}), name='reporting-dashboard-mttr-summary'),
    path('dashboard/sla_summary/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'sla_summary'}), name='reporting-dashboard-sla-summary'),
    path('dashboard/performance_metrics/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'performance_metrics'}), name='reporting-dashboard-performance-metrics'),
    path('dashboard/recent_reports/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'recent_reports'}), name='reporting-dashboard-recent-reports'),
    path('dashboard/trending_metrics/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'trending_metrics'}), name='reporting-dashboard-trending-metrics'),
    path('dashboard/compliance/', viewsets_reporting.ReportingDashboardViewSet.as_view({'get': 'compliance'}), name='reporting-dashboard-compliance'),
    path('dashboard/export/', viewsets_reporting.ReportingDashboardViewSet.as_view({'post': 'export'}), name='reporting-dashboard-export'),
]
