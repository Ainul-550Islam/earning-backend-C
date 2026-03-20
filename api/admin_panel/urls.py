from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdminPanelViewSet, AdminActionViewSet, SystemSettingsViewSet,
    ReportViewSet, SiteContentViewSet, SiteNotificationViewSet, SystemHealthView,
    EndpointToggleViewSet
)

router = DefaultRouter()
router.register(r'endpoint-toggles', EndpointToggleViewSet, basename='endpoint-toggle')
router.register(r'dashboard',          AdminPanelViewSet,       basename='admin-dashboard')
router.register(r'actions',            AdminActionViewSet,      basename='admin-actions')
router.register(r'settings',           SystemSettingsViewSet,   basename='system-settings')
router.register(r'reports',            ReportViewSet,           basename='reports')
router.register(r'site-contents',      SiteContentViewSet,      basename='site-contents')      # Fix 12
router.register(r'site-notifications', SiteNotificationViewSet, basename='site-notifications') # Fix 9

urlpatterns = [
    path('', include(router.urls)),

    # Fix 13: by-identifier/:identifier/ custom path
    path(
        'site-contents/by-identifier/<str:identifier>/',
        SiteContentViewSet.as_view({'get': 'get_content'}),
        name='site-content-by-identifier',
    ),

    # Fix 16: /admin/dashboard/stats/
    path(
        'dashboard/stats/',
        AdminPanelViewSet.as_view({'get': 'dashboard'}),
        name='dashboard-stats',
    ),

    # Fix 17: /admin/dashboard/revenue-chart/
    path(
        'dashboard/revenue-chart/',
        AdminPanelViewSet.as_view({'get': 'revenue_stats'}),
        name='dashboard-revenue-chart',
    ),

    # Fix 18: /admin/dashboard/system-health/
    path(
        'dashboard/system-health/',
        SystemHealthView.as_view(),
        name='dashboard-system-health',
    ),
]









# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from . import views
from .views import EndpointToggleViewSet
# # from .views import AdminPanelViewSet, AdminActionViewSet, SystemSettingsViewSet, ReportViewSet
# # from api.admin_panel.views import UserProfileViewSet
# from .views import (
#     AdminPanelViewSet, AdminActionViewSet, SystemSettingsViewSet, 
#     ReportViewSet, SiteContentViewSet, SiteNotificationViewSet, SystemHealthView
# )

# router = DefaultRouter()

# urlpatterns = [
#     path('', include(router.urls)),
#         # System Settings
#     path('settings/public/', views.SystemSettingsViewSet.as_view({'get': 'public_settings'}), name='public-settings'),
#     path('settings/update/', views.SystemSettingsViewSet.as_view({'put': 'update_settings', 'patch': 'update_settings'}), name='update-settings'),
#     path('settings/maintenance/', views.SystemSettingsViewSet.as_view({'post': 'update_maintenance'}), name='update-maintenance'),
#     path('settings/test-email/', views.SystemSettingsViewSet.as_view({'post': 'test_email'}), name='test-email'),
#     path('settings/test-sms/', views.SystemSettingsViewSet.as_view({'post': 'test_sms'}), name='test-sms'),
#     path('settings/clear-cache/', views.SystemSettingsViewSet.as_view({'post': 'clear_cache'}), name='clear-cache'),
#     path('settings/stats/', views.SystemSettingsViewSet.as_view({'get': 'stats'}), name='system-stats'),
    
#     # Notifications
#     path('notifications/active/', views.SiteNotificationViewSet.as_view({'get': 'active_notifications'}), name='active-notifications'),
#     path('notifications/login/', views.SiteNotificationViewSet.as_view({'get': 'login_notifications'}), name='login-notifications'),
    
#     # Contents
#     path('contents/get/<str:identifier>/', views.SiteContentViewSet.as_view({'get': 'get_content'}), name='get-content'),
#     path('contents/by-type/', views.SiteContentViewSet.as_view({'get': 'by_type'}), name='content-by-type'),
    
#     # System Health
#     path('health/', views.SystemHealthView.as_view(), name='system-health'),

# ]