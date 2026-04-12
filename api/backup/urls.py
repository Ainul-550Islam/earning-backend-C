# urls.py
from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'backups', views.BackupViewSet, basename='backup')
router.register(r'schedules', views.BackupScheduleViewSet, basename='schedule')
router.register(r'storage-locations', views.BackupStorageLocationViewSet, basename='storage-location')
router.register(r'notification-configs', views.BackupNotificationConfigViewSet, basename='notification-config')
router.register(r'retention-policies', views.RetentionPolicyViewSet, basename='retention-policy')
router.register(r'delta-trackers', views.DeltaBackupTrackerViewSet, basename='delta-tracker')
router.register(r'logs', views.BackupLogViewSet, basename='log')
router.register(r'restorations', views.BackupRestorationViewSet, basename='restoration')

# API URL Patterns
api_urlpatterns = [
    # path('', views.DashboardStatsView.as_view(), name='backup-dashboard'),
    path('', include(router.urls)),
    
    # Backup operations
    path('backups/<uuid:pk>/verify/', views.BackupVerifyView.as_view(), name='backup-verify'),
    path('backups/<uuid:pk>/health-check/', views.BackupHealthCheckView.as_view(), name='backup-health-check'),
    path('backups/<uuid:pk>/download/', views.BackupDownloadView.as_view(), name='backup-download'),
    path('backups/<uuid:pk>/create-redundant/', views.CreateRedundantCopyView.as_view(), name='create-redundant'),
    path('backups/<uuid:pk>/logs/', views.BackupLogsView.as_view(), name='backup-logs'),
    path('backups/<uuid:pk>/clone/', views.CloneBackupView.as_view(), name='clone-backup'),
    
    # Task operations
    path('start-backup/', views.StartBackupView.as_view(), name='start-backup'),
    path('cancel-backup/<uuid:pk>/', views.CancelBackupView.as_view(), name='cancel-backup'),
    path('restore-backup/', views.RestoreBackupView.as_view(), name='restore-backup'),
    path('cleanup-old-backups/', views.CleanupOldBackupsView.as_view(), name='cleanup-old-backups'),
    path('test-notification/<uuid:pk>/', views.TestNotificationView.as_view(), name='test-notification'),
    
    # Status and monitoring
    path('backup-status/', views.BackupStatusView.as_view(), name='backup-status'),
    path('backup-progress/<uuid:pk>/', views.BackupProgressView.as_view(), name='backup-progress'),
    path('system-metrics/', views.SystemMetricsView.as_view(), name='system-metrics'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    
    # Maintenance
    path('maintenance-mode/', views.MaintenanceModeView.as_view(), name='maintenance-mode'),
    
    # Analytics
    path('analytics/backup-growth/', views.BackupGrowthAnalyticsView.as_view(), name='backup-growth-analytics'),
    path('analytics/storage-usage/', views.StorageUsageAnalyticsView.as_view(), name='storage-usage-analytics'),
    path('analytics/performance-metrics/', views.PerformanceMetricsView.as_view(), name='performance-metrics'),
    path('analytics/retention-analysis/', views.RetentionAnalysisView.as_view(), name='retention-analysis'),
    
    # Reports
    path('reports/backup-summary/', views.BackupSummaryReportView.as_view(), name='backup-summary-report'),
    path('reports/health-report/', views.HealthReportView.as_view(), name='health-report'),
    path('reports/compliance-report/', views.ComplianceReportView.as_view(), name='compliance-report'),
]

# Admin URL Patterns (from admin.py)
admin_urlpatterns = [
    path('backup-dashboard/', views.BackupAdminDashboardView.as_view(), name='backup_dashboard'),
    path('backup-analytics/', views.BackupAdminDashboardView.as_view(), name='backup_analytics'),
    # path('storage-management/', views.StorageManagementDashboardView.as_view(), name='storage_management'),
    # path('run-backup/', views.RunBackupWizardView.as_view(), name='run_backup'),
    # path('restore-backup/', views.RestoreBackupWizardView.as_view(), name='restore_backup'),
    # path('backup-monitoring/', views.BackupMonitoringDashboardView.as_view(), name='backup_monitoring'),
    # path('schedule-manager/', views.ScheduleManagerDashboardView.as_view(), name='schedule_manager'),
    
    # API endpoints for admin
    path('api/backup-progress/<uuid:pk>/', views.APIBackupProgressView.as_view(), name='api_backup_progress'),
    # path('api/backup-status/', views.APIBackupStatusView.as_view(), name='api_backup_status'),
    path('api/start-backup/', views.APIStartBackupView.as_view(), name='api_start_backup'),
    # path('api/cancel-backup/<uuid:pk>/', views.APICancelBackupView.as_view(), name='api_cancel_backup'),
    # path('api/maintenance-mode/', views.APIMaintenanceModeView.as_view(), name='api_maintenance_mode'),
    # path('api/verify-backup/<uuid:pk>/', views.APIVerifyBackupView.as_view(), name='api_verify_backup'),
    # path('api/cleanup-old-backups/', views.APICleanupOldBackupsView.as_view(), name='api_cleanup_old_backups'),
    # path('api/notify-backup/<uuid:pk>/', views.APINotifyBackupView.as_view(), name='api_notify_backup'),
    # path('api/health-check/<uuid:pk>/', views.APIHealthCheckView.as_view(), name='api_health_check'),
    # path('api/create-redundant/<uuid:pk>/', views.APICreateRedundantView.as_view(), name='api_create_redundant'),
    # path('api/test-notification/<uuid:pk>/', views.APITestNotificationView.as_view(), name='api_test_notification'),
    
    # Additional admin APIs
    # path('api/dashboard-stats/', views.APIDashboardStatsView.as_view(), name='api_dashboard_stats'),
    # path('api/system-metrics/', views.APISystemMetricsView.as_view(), name='api_system_metrics'),
    # path('api/quick-stats/', views.APIQuickStatsView.as_view(), name='api_quick_stats'),
]

# Main URL patterns
urlpatterns = [
    # REST API  (DashboardStatsView is already at dashboard-stats/ inside api_urlpatterns)
    path('', include(api_urlpatterns)),
    
    # Admin interface
    path('admin/backup/', include(admin_urlpatterns)),
    
    # Webhook endpoints
    path('webhooks/backup-complete/<uuid:backup_id>/', views.BackupCompleteWebhookView.as_view(), name='backup-complete-webhook'),
    path('webhooks/restore-complete/<uuid:restoration_id>/', views.RestoreCompleteWebhookView.as_view(), name='restore-complete-webhook'),
    path('webhooks/health-alert/', views.HealthAlertWebhookView.as_view(), name='health-alert-webhook'),
    
    # Public endpoints (read-only)
    path('public/backup-status/', views.PublicBackupStatusView.as_view(), name='public-backup-status'),
    path('public/health-check/', views.PublicHealthCheckView.as_view(), name='public-health-check'),
]

# Error handlers
# handler404 = 'backup.views.handler404'
# handler500 = 'backup.views.handler500'