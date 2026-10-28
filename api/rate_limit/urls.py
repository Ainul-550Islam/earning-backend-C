from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from api.rate_limit import views

router = DefaultRouter()
router.register(r'configs', views.RateLimitConfigViewSet, basename='ratelimit-config')
router.register(r'logs', views.RateLimitLogViewSet, basename='ratelimit-log')
router.register(r'user-profiles', views.UserRateLimitProfileViewSet, basename='user-ratelimit-profile')
router.register(r'abuse-reports', views.AbuseReportViewSet, basename='abuse-report')
router.register(r'ip-blocks', views.IPBlockListViewSet, basename='ip-block')
router.register(r'insights', views.RateLimitInsightViewSet, basename='rate-limit-insight')
router.register(r'exceptions', views.RateLimitExceptionViewSet, basename='rate-limit-exception')

urlpatterns = [
    path('', include(router.urls)),
    
    # Health check
    path('health/', views.RateLimitHealthView.as_view(), name='rate-limit-health'),
    
    # Test endpoint
    path('test/', views.RateLimitTestView.as_view(), name='rate-limit-test'),
    
    # Dashboard and analytics
    path('dashboard/', views.RateLimitDashboardView.as_view(), name='rate-limit-dashboard'),
    path('analytics/', views.RateLimitAnalyticsView.as_view(), name='rate-limit-analytics'),
    path('stats/', views.RateLimitStatsView.as_view(), name='rate-limit-stats'),
    
    # User-specific endpoints
    path('user/info/', views.UserRateLimitInfoView.as_view(), name='user-rate-limit-info'),
    path('user/profile/', views.UserRateLimitProfileDetailView.as_view(), name='user-rate-limit-profile-detail'),
    path('user/reset/', views.UserRateLimitResetView.as_view(), name='user-rate-limit-reset'),
    
    # Abuse detection endpoints
    path('abuse/detect/', views.AbuseDetectionView.as_view(), name='abuse-detection'),
    path('abuse/investigate/', views.AbuseInvestigationView.as_view(), name='abuse-investigation'),
    path('abuse/report/', views.CreateAbuseReportView.as_view(), name='create-abuse-report'),
    
    # IP blocking endpoints
    path('ip/check/', views.IPBlockCheckView.as_view(), name='ip-block-check'),
    path('ip/block/', views.IPBlockCreateView.as_view(), name='ip-block-create'),
    path('ip/unblock/', views.IPBlockUnblockView.as_view(), name='ip-block-unblock'),
    path('ip/cleanup/', views.IPBlockCleanupView.as_view(), name='ip-block-cleanup'),
    
    # Rate limit insights endpoints
    path('insights/generate/', views.GenerateInsightsView.as_view(), name='generate-insights'),
    path('insights/export/', views.ExportInsightsView.as_view(), name='export-insights'),
    path('insights/weekly/', views.WeeklyInsightsView.as_view(), name='weekly-insights'),
    
    # Exception management endpoints
    path('exceptions/grant/', views.GrantExceptionView.as_view(), name='grant-exception'),
    path('exceptions/revoke/', views.RevokeExceptionView.as_view(), name='revoke-exception'),
    path('exceptions/check/', views.CheckExceptionView.as_view(), name='check-exception'),
    
    # Earning app specific endpoints
    path('earning/task-limit/', views.TaskRateLimitView.as_view(), name='task-rate-limit-check'),
    path('earning/offer-limit/', views.OfferRateLimitView.as_view(), name='offer-rate-limit-check'),
    path('earning/referral-limit/', views.ReferralRateLimitView.as_view(), name='referral-rate-limit-check'),
    path('earning/withdrawal-limit/', views.WithdrawalRateLimitView.as_view(), name='withdrawal-rate-limit-check'),
    
    # Management endpoints
    path('management/sync/', views.SyncRateLimitsView.as_view(), name='sync-rate-limits'),
    path('management/export/', views.ExportRateLimitsView.as_view(), name='export-rate-limits'),
    path('management/import/', views.ImportRateLimitsView.as_view(), name='import-rate-limits'),
    path('management/cleanup/', views.CleanupRateLimitsView.as_view(), name='cleanup-rate-limits'),
    
    # Configuration endpoints
    path('config/bulk-activate/', views.BulkActivateConfigsView.as_view(), name='bulk-activate-configs'),
    path('config/simulate/', views.SimulateImpactView.as_view(), name='simulate-impact'),
    path('config/backup/', views.BackupConfigsView.as_view(), name='backup-configs'),
    path('config/restore/', views.RestoreConfigsView.as_view(), name='restore-configs'),
]

# Webhook endpoints — receiver first, management under /manage/
from api.rate_limit.webhooks import RateLimitWebhookView
urlpatterns += [
    path('webhooks/', RateLimitWebhookView.as_view(), name='ratelimit-webhook-list'),
    path('webhooks/manage/', views.RateLimitWebhookListView.as_view(), name='ratelimit-webhook-manage'),
    path('webhooks/<str:webhook_id>/', views.RateLimitWebhookDetailView.as_view(), name='ratelimit-webhook-detail'),
]
