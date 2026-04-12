# api/users/urls.py — Updated version
# পুরনো urls.py এর সাথে merge করো
# ============================================================

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter
from . import views, admin_views
from .login_view import UserLoginView, login_user_api
from .registration_view import UserRegistrationView, register_user_api

# 2FA + Session views
from .views_2fa_session import (
    TwoFASetupView,
    TwoFAConfirmView,
    TwoFADisableView,
    TwoFAStatusView,
    TwoFARegenerateBackupCodesView,
    LoginWith2FAView,
    Verify2FALoginView,
    ActiveSessionsView,
    RevokeSessionView,
    RevokeAllSessionsView,
    LogoutView,
)

app_name = 'users'

router = DefaultRouter()
router.register(r'',            views.AdminUserViewSet,       basename='user')
router.register(r'profile',     views.UserProfileViewSet,     basename='user-profile')
router.register(r'kyc',         views.KYCVerificationViewSet, basename='kyc')
router.register(r'devices',     views.UserDeviceViewSet,      basename='device')

urlpatterns = [
    # ── পুরনো routes (unchanged) ──────────────────────────
    path('register/',            views.AutoRegisterView.as_view(),       name='auto-register'),
    path('api/login/',           login_user_api,                         name='api-login'),
    path('leaderboard/',         views.leaderboard_view,                 name='leaderboard'),
    path('fraud-logs/',          views.fraud_logs_view,                  name='fraud-logs'),
    path('ip-reputations/',      views.ip_reputations_view,              name='ip-reputations'),
    path('device-fingerprints/', views.device_fingerprints_view,         name='device-fingerprints'),
    path('rate-limits/',         views.rate_limits_view,                 name='rate-limits'),
    path('check-username/',      views.check_username_availability,      name='check-username'),
    path('admin/fraud/dashboard/',     admin_views.fraud_dashboard_overview, name='fraud-dashboard'),
    path('admin/fraud/events/',        admin_views.recent_fraud_events,      name='fraud-events'),
    path('admin/fraud/high-risk-users/', admin_views.high_risk_users,      name='high-risk-users'),
    path('admin/fraud/statistics/',    admin_views.fraud_statistics,        name='fraud-statistics'),

    # ── নতুন Auth routes (2FA support সহ) ─────────────────
    path('auth/login/',          LoginWith2FAView.as_view(),             name='login-with-2fa'),
    path('auth/verify-2fa/',     Verify2FALoginView.as_view(),           name='verify-2fa-login'),
    path('auth/logout/',         LogoutView.as_view(),                   name='logout'),

    # ── 2FA management ─────────────────────────────────────
    path('2fa/setup/',           TwoFASetupView.as_view(),               name='2fa-setup'),
    path('2fa/confirm/',         TwoFAConfirmView.as_view(),             name='2fa-confirm'),
    path('2fa/disable/',         TwoFADisableView.as_view(),             name='2fa-disable'),
    path('2fa/status/',          TwoFAStatusView.as_view(),              name='2fa-status'),
    path('2fa/backup-codes/regenerate/', TwoFARegenerateBackupCodesView.as_view(), name='2fa-regen-backup'),

    # ── Session management ─────────────────────────────────
    path('sessions/',            ActiveSessionsView.as_view(),           name='active-sessions'),
    path('sessions/revoke-all/', RevokeAllSessionsView.as_view(),        name='revoke-all-sessions'),
    path('sessions/<str:session_id>/', RevokeSessionView.as_view(),      name='revoke-session'),

    # ── Router ─────────────────────────────────────────────
    path('', include(router.urls)),
]



# from django.urls import path, include
# from rest_framework.routers import SimpleRouter as DefaultRouter
# from . import views, admin_views
# from .login_view import UserLoginView, login_user_api
# from .registration_view import UserRegistrationView, register_user_api

# app_name = 'users'

# router = DefaultRouter()
# router.register(r'',            views.AdminUserViewSet,       basename='user')
# router.register(r'profile',     views.UserProfileViewSet,     basename='user-profile')
# router.register(r'kyc',         views.KYCVerificationViewSet, basename='kyc')
# router.register(r'devices',     views.UserDeviceViewSet,      basename='device')

# urlpatterns = [
#     path('register/',    views.AutoRegisterView.as_view(),    name='auto-register'),
#     path('login/',       UserLoginView.as_view(),             name='user-login'),
#     path('api/login/',   login_user_api,                      name='api-login'),
#     path('leaderboard/', views.leaderboard_view,              name='leaderboard'),
#     path('fraud-logs/',  views.fraud_logs_view,               name='fraud-logs'),
#     path('ip-reputations/', views.ip_reputations_view,        name='ip-reputations'),
#     path('device-fingerprints/', views.device_fingerprints_view, name='device-fingerprints'),
#     path('rate-limits/', views.rate_limits_view,              name='rate-limits'),
#     path('check-username/', views.check_username_availability, name='check-username'),
#     path('admin/fraud/dashboard/', admin_views.fraud_dashboard_overview, name='fraud-dashboard'),
#     path('admin/fraud/events/',    admin_views.recent_fraud_events,      name='fraud-events'),
#     path('admin/fraud/high-risk-users/', admin_views.high_risk_users,    name='high-risk-users'),
#     path('admin/fraud/statistics/', admin_views.fraud_statistics,        name='fraud-statistics'),
#     path('', include(router.urls)),
# ]
