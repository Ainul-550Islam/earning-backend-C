# kyc/api/v1/urls.py  ── WORLD #1
from django.urls import path
from .views import (
    kyc_status, kyc_submit, kyc_fraud_check, kyc_logs,
    kyc_admin_list, kyc_admin_stats, kyc_admin_review,
    kyc_admin_delete, kyc_admin_reset, kyc_admin_logs,
    kyc_admin_add_note, kyc_admin_bulk_action,
)

urlpatterns = [
    path('status/',      kyc_status,      name='v1-kyc-status'),
    path('submit/',      kyc_submit,       name='v1-kyc-submit'),
    path('fraud-check/', kyc_fraud_check,  name='v1-kyc-fraud-check'),
    path('logs/',        kyc_logs,         name='v1-kyc-logs'),
    path('admin/list/',  kyc_admin_list,   name='v1-kyc-admin-list'),
    path('admin/stats/', kyc_admin_stats,  name='v1-kyc-admin-stats'),
    path('admin/review/<int:kyc_id>/', kyc_admin_review, name='v1-kyc-admin-review'),
    path('admin/delete/<int:kyc_id>/', kyc_admin_delete, name='v1-kyc-admin-delete'),
    path('admin/reset/<int:kyc_id>/',  kyc_admin_reset,  name='v1-kyc-admin-reset'),
    path('admin/logs/<int:kyc_id>/',   kyc_admin_logs,   name='v1-kyc-admin-logs'),
    path('admin/add-note/<int:kyc_id>/', kyc_admin_add_note, name='v1-kyc-admin-add-note'),
    path('admin/bulk-action/', kyc_admin_bulk_action, name='v1-kyc-admin-bulk-action'),
]
