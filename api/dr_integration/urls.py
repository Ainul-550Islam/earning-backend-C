"""
DR Integration URL Configuration
Mount in main urls.py: path('api/dr/', include('dr_integration.urls'))
"""
from django.urls import path
from . import views

app_name = 'dr_integration'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    path('dashboard/',           views.DRDashboardView.as_view(),         name='dashboard'),

    # ── Backup Management ─────────────────────────────────────────────────
    path('backups/',             views.DRBackupListView.as_view(),         name='backup-list'),
    path('backups/<str:backup_id>/verify/',
                                 views.DRBackupVerifyView.as_view(),       name='backup-verify'),

    # ── Restore Management ────────────────────────────────────────────────
    path('restore/',             views.DRRestoreView.as_view(),            name='restore'),
    path('restore/pitr-check/',  views.DRRestorePITRCheckView.as_view(),   name='restore-pitr-check'),

    # ── Health & Failover ─────────────────────────────────────────────────
    path('health/',              views.DRHealthView.as_view(),             name='health'),
    path('failover/',            views.DRFailoverView.as_view(),           name='failover'),

    # ── Alerts ────────────────────────────────────────────────────────────
    path('alerts/',              views.DRAlertListView.as_view(),          name='alert-list'),
    path('alerts/<uuid:alert_id>/acknowledge/',
                                 views.DRAlertAcknowledgeView.as_view(),   name='alert-acknowledge'),

    # ── Monitoring ────────────────────────────────────────────────────────
    path('status/',              views.DRStatusPageView.as_view(),         name='status-page'),
    path('metrics/',             views.DRMetricsView.as_view(),            name='metrics'),

    # ── Security ──────────────────────────────────────────────────────────
    path('compliance/',          views.DRComplianceView.as_view(),         name='compliance'),
    path('security/rotate-keys/',views.DRKeyRotationView.as_view(),       name='key-rotation'),

    # ── Audit ─────────────────────────────────────────────────────────────
    path('audit/',               views.DRAuditLogView.as_view(),           name='audit-log'),
    path('audit/integrity/',     views.DRAuditIntegrityView.as_view(),     name='audit-integrity'),
]
