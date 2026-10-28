# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Main API Router
router = DefaultRouter()
router.register(r'backups', views.BackupViewSet, basename='backup')
router.register(r'schedules', views.BackupScheduleViewSet, basename='schedule')
router.register(r'storage-locations', views.BackupStorageLocationViewSet, basename='storage-location')
router.register(r'notification-configs', views.BackupNotificationConfigViewSet, basename='notification-config')
router.register(r'retention-policies', views.RetentionPolicyViewSet, basename='retention-policy')
router.register(r'delta-trackers', views.DeltaBackupTrackerViewSet, basename='delta-tracker')
router.register(r'logs', views.BackupLogViewSet, basename='log')
router.register(r'restorations', views.BackupRestorationViewSet, basename='restoration')
router.register(r'verifications', views.BackupVerificationViewSet, basename='verification')
router.register(r'encryption', views.BackupEncryptionViewSet, basename='encryption')
router.register(r'alerts', views.BackupAlertViewSet, basename='alert')

# API URL Patterns
api_urlpatterns = [
    # Main API endpoints
    path('', include(router.urls)),
    
    # Backup operations
    path('backups/<uuid:pk>/verify/', views.BackupVerifyView.as_view(), name='backup-verify'),
    path('backups/<uuid:pk>/health-check/', views.BackupHealthCheckView.as_view(), name='backup-health-check'),
    path('backups/<uuid:pk>/download/', views.BackupDownloadView.as_view(), name='backup-download'),
    path('backups/<uuid:pk>/create-redundant/', views.CreateRedundantCopyView.as_view(), name='create-redundant'),
    path('backups/<uuid:pk>/logs/', views.BackupLogsView.as_view(), name='backup-logs'),
    path('backups/<uuid:pk>/clone/', views.CloneBackupView.as_view(), name='clone-backup'),
    path('backups/<uuid:pk>/encrypt/', views.BackupEncryptView.as_view(), name='backup-encrypt'),
    path('backups/<uuid:pk>/compress/', views.BackupCompressView.as_view(), name='backup-compress'),
    path('backups/<uuid:pk>/move/', views.BackupMoveView.as_view(), name='backup-move'),
    path('backups/<uuid:pk>/archive/', views.BackupArchiveView.as_view(), name='backup-archive'),
    # path('backups/<uuid:pk>/restore/', views.BackupRestoration.as_view(), name='backup-restore'),
    
    # Schedule operations
    path('schedules/<uuid:pk>/run-now/', views.ScheduleRunNowView.as_view(), name='schedule-run-now'),
    path('schedules/<uuid:pk>/pause/', views.SchedulePauseView.as_view(), name='schedule-pause'),
    path('schedules/<uuid:pk>/resume/', views.ScheduleResumeView.as_view(), name='schedule-resume'),
    path('schedules/<uuid:pk>/next-run/', views.ScheduleNextRunView.as_view(), name='schedule-next-run'),
    
    # Storage operations
    path('storage-locations/<uuid:pk>/test-connection/', views.StorageTestConnectionView.as_view(), name='storage-test-connection'),
    path('storage-locations/<uuid:pk>/sync/', views.StorageSyncView.as_view(), name='storage-sync'),
    path('storage-locations/<uuid:pk>/cleanup/', views.StorageCleanupView.as_view(), name='storage-cleanup'),
    path('storage-locations/<uuid:pk>/metrics/', views.StorageMetricsView.as_view(), name='storage-metrics'),
    
    # Task operations
    path('start-backup/', views.StartBackupView.as_view(), name='start-backup'),
    path('cancel-backup/<uuid:pk>/', views.CancelBackupView.as_view(), name='cancel-backup'),
    path('restore-backup/', views.RestoreBackupView.as_view(), name='restore-backup'),
    path('cleanup-old-backups/', views.CleanupOldBackupsView.as_view(), name='cleanup-old-backups'),
    path('test-notification/<uuid:pk>/', views.TestNotificationView.as_view(), name='test-notification'),
    path('batch-operations/', views.BatchOperationsView.as_view(), name='batch-operations'),
    path('bulk-actions/', views.BulkActionsView.as_view(), name='bulk-actions'),
    
    # Status and monitoring
    path('backup-status/', views.BackupStatusView.as_view(), name='backup-status'),
    path('backup-progress/<uuid:pk>/', views.BackupProgressView.as_view(), name='backup-progress'),
    path('system-metrics/', views.SystemMetricsView.as_view(), name='system-metrics'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
    path('health-check/', views.SystemHealthCheckView.as_view(), name='system-health-check'),
    path('service-status/', views.ServiceStatusView.as_view(), name='service-status'),
    
    # Maintenance
    path('maintenance-mode/', views.MaintenanceModeView.as_view(), name='maintenance-mode'),
    path('system-info/', views.SystemInfoView.as_view(), name='system-info'),
    path('logs/stream/', views.LogStreamView.as_view(), name='log-stream'),
    
    # Analytics
    path('analytics/backup-growth/', views.BackupGrowthAnalyticsView.as_view(), name='backup-growth-analytics'),
    path('analytics/storage-usage/', views.StorageUsageAnalyticsView.as_view(), name='storage-usage-analytics'),
    path('analytics/performance-metrics/', views.PerformanceMetricsView.as_view(), name='performance-metrics'),
    path('analytics/retention-analysis/', views.RetentionAnalysisView.as_view(), name='retention-analysis'),
#     path('analytics/backup-trends/', views.BackupTrendsAnalyticsView.as_view(), name='backup-trends-analytics'),
#     path('analytics/failure-analysis/', views.FailureAnalysisView.as_view(), name='failure-analysis'),
    
    # Reports
    path('reports/backup-summary/', views.BackupSummaryReportView.as_view(), name='backup-summary-report'),
    path('reports/health-report/', views.HealthReportView.as_view(), name='health-report'),
    path('reports/compliance-report/', views.ComplianceReportView.as_view(), name='compliance-report'),
#     path('reports/usage-report/', views.UsageReportView.as_view(), name='usage-report'),
#     path('reports/cost-analysis/', views.CostAnalysisView.as_view(), name='cost-analysis'),
    
    # Notifications
#     path('notifications/send/', views.SendNotificationView.as_view(), name='send-notification'),
    path('notifications/test/', views.TestNotificationView.as_view(), name='test-notification'),
#     path('notifications/configs/<uuid:pk>/test/', views.TestNotificationConfigView.as_view(), name='test-notification-config'),
    
    # Verification
    path('verifications/batch/', views.BatchVerificationView.as_view(), name='batch-verification'),
    path('verifications/schedule/', views.ScheduleVerificationView.as_view(), name='schedule-verification'),
    
    # Encryption
    path('encryption/keys/', views.EncryptionKeysView.as_view(), name='encryption-keys'),
    path('encryption/rotate/', views.EncryptionRotateView.as_view(), name='encryption-rotate'),
    
    # Import/Export
    path('import/', views.ImportBackupView.as_view(), name='import-backup'),
    path('export/', views.ExportBackupView.as_view(), name='export-backup'),
    
    # Search
    path('search/', views.BackupSearchView.as_view(), name='backup-search'),
    path('search/advanced/', views.AdvancedSearchView.as_view(), name='advanced-search'),
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

    # Dashboard stats (was missing from url registration)
    path('dashboard/stats/', views.BackupDashboardStatsView.as_view(), name='backup-dashboard-stats'),
]

# Error handlers
# handler404 = 'backup.views.handler404'
# handler500 = 'backup.views.handler500'