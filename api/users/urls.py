from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, admin_views
from .login_view import UserLoginView, login_user_api
from .registration_view import UserRegistrationView, register_user_api

app_name = 'users'

router = DefaultRouter()
router.register(r'',            views.AdminUserViewSet,       basename='user')
router.register(r'profile',     views.UserProfileViewSet,     basename='user-profile')
router.register(r'kyc',         views.KYCVerificationViewSet, basename='kyc')
router.register(r'devices',     views.UserDeviceViewSet,      basename='device')

urlpatterns = [
    path('register/',    views.AutoRegisterView.as_view(),    name='auto-register'),
    path('login/',       UserLoginView.as_view(),             name='user-login'),
    path('api/login/',   login_user_api,                      name='api-login'),
    path('leaderboard/', views.leaderboard_view,              name='leaderboard'),
    path('fraud-logs/',  views.fraud_logs_view,               name='fraud-logs'),
    path('ip-reputations/', views.ip_reputations_view,        name='ip-reputations'),
    path('device-fingerprints/', views.device_fingerprints_view, name='device-fingerprints'),
    path('rate-limits/', views.rate_limits_view,              name='rate-limits'),
    path('admin/fraud/dashboard/', admin_views.fraud_dashboard_overview, name='fraud-dashboard'),
    path('admin/fraud/events/',    admin_views.recent_fraud_events,      name='fraud-events'),
    path('admin/fraud/high-risk-users/', admin_views.high_risk_users,    name='high-risk-users'),
    path('admin/fraud/statistics/', admin_views.fraud_statistics,        name='fraud-statistics'),
    path('', include(router.urls)),
]
