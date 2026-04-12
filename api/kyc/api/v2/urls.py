# kyc/api/v2/urls.py  ── WORLD #1
from django.urls import path
from . import views
from ...views import (
    kyc_status, kyc_submit, kyc_fraud_check,
    kyc_blacklist_list, kyc_blacklist_check,
    kyc_analytics_summary, kyc_audit_trail, kyc_exports,
)

urlpatterns = [
    # Enhanced v2 status
    path('status/',              views.v2_kyc_status,         name='v2-kyc-status'),
    path('submit/',              kyc_submit,                   name='v2-kyc-submit'),
    path('fraud-check/',         kyc_fraud_check,              name='v2-kyc-fraud-check'),
    # Admin dashboard v2
    path('admin/dashboard/',     views.v2_kyc_admin_dashboard, name='v2-kyc-admin-dashboard'),
    path('admin/risk-leaderboard/', views.v2_kyc_risk_leaderboard, name='v2-kyc-risk-leaderboard'),
    # Notifications
    path('notifications/<int:notif_id>/read/', views.v2_kyc_read_notification, name='v2-kyc-read-notification'),
    # Reuse v1 endpoints
    path('blacklist/',       kyc_blacklist_list,     name='v2-kyc-blacklist-list'),
    path('blacklist/check/', kyc_blacklist_check,    name='v2-kyc-blacklist-check'),
    path('admin/analytics/', kyc_analytics_summary,  name='v2-kyc-analytics'),
    path('admin/audit/',     kyc_audit_trail,         name='v2-kyc-audit'),
    path('admin/exports/',   kyc_exports,             name='v2-kyc-exports'),
]
