# kyc/urls.py  ── WORLD #1 COMPLETE
from django.urls import path
from . import views

urlpatterns = [
    # USER (existing)
    path('',             views.kyc_status,      name='kyc-status-root'),
    path('status/',      views.kyc_status,      name='kyc-status'),
    path('submit/',      views.kyc_submit,       name='kyc-submit'),
    path('fraud-check/', views.kyc_fraud_check,  name='kyc-fraud-check'),
    path('logs/',        views.kyc_logs,         name='kyc-logs'),
    # ADMIN (existing)
    path('records/',                          views.kyc_admin_list,        name='kyc-records'),
    path('admin/list/',                       views.kyc_admin_list,        name='kyc-admin-list'),
    path('admin/stats/',                      views.kyc_admin_stats,       name='kyc-admin-stats'),
    path('admin/review/<int:kyc_id>/',        views.kyc_admin_review,      name='kyc-admin-review'),
    path('admin/delete/<int:kyc_id>/',        views.kyc_admin_delete,      name='kyc-admin-delete'),
    path('admin/reset/<int:kyc_id>/',         views.kyc_admin_reset,       name='kyc-admin-reset'),
    path('admin/logs/<int:kyc_id>/',          views.kyc_admin_logs,        name='kyc-admin-logs'),
    path('admin/add-note/<int:kyc_id>/',      views.kyc_admin_add_note,    name='kyc-admin-add-note'),
    path('admin/bulk-action/',                views.kyc_admin_bulk_action, name='kyc-admin-bulk-action'),
    # NEW
    path('health/',                            views.kyc_health,              name='kyc-health'),
    path('blacklist/',                         views.kyc_blacklist_list,      name='kyc-blacklist-list'),
    path('blacklist/<int:pk>/',               views.kyc_blacklist_detail,    name='kyc-blacklist-detail'),
    path('blacklist/check/',                   views.kyc_blacklist_check,     name='kyc-blacklist-check'),
    path('admin/risk/<int:kyc_id>/',           views.kyc_risk_profile,        name='kyc-risk-profile'),
    path('admin/risk/<int:kyc_id>/recompute/', views.kyc_risk_recompute,      name='kyc-risk-recompute'),
    path('admin/notes/<int:kyc_id>/',          views.kyc_notes_list,          name='kyc-notes-list'),
    path('admin/notes/<int:kyc_id>/<int:note_id>/', views.kyc_note_detail,   name='kyc-note-detail'),
    path('admin/rejection-templates/',         views.kyc_rejection_templates, name='kyc-rejection-templates'),
    path('admin/analytics/',                   views.kyc_analytics,           name='kyc-analytics'),
    path('admin/analytics/summary/',           views.kyc_analytics_summary,   name='kyc-analytics-summary'),
    path('admin/config/',                      views.kyc_tenant_config,       name='kyc-tenant-config'),
    path('admin/webhooks/',                    views.kyc_webhooks_list,       name='kyc-webhooks-list'),
    path('admin/webhooks/<int:pk>/',           views.kyc_webhook_detail,      name='kyc-webhook-detail'),
    path('admin/audit-trail/',                 views.kyc_audit_trail,         name='kyc-audit-trail'),
    path('admin/feature-flags/',               views.kyc_feature_flags,       name='kyc-feature-flags'),
    path('admin/feature-flags/<str:key>/toggle/', views.kyc_feature_flag_toggle, name='kyc-feature-flag-toggle'),
    path('admin/duplicates/',                  views.kyc_duplicate_groups,    name='kyc-duplicate-groups'),
    path('admin/duplicates/<int:pk>/resolve/', views.kyc_duplicate_resolve,   name='kyc-duplicate-resolve'),
    path('admin/exports/',                     views.kyc_exports,             name='kyc-exports'),
    path('notifications/my/',                  views.kyc_my_notifications,    name='kyc-my-notifications'),
    path('admin/notifications/',               views.kyc_all_notifications,   name='kyc-all-notifications'),
]
