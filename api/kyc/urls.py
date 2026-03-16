# kyc/urls.py  ── 100% COMPLETE
from django.urls import path
from . import views

urlpatterns = [
    # ── USER ──────────────────────────────────────────────────
    path('',        views.kyc_status, name='kyc-status'),
    path('submit/', views.kyc_submit, name='kyc-submit'),   # GET / POST / DELETE
    path('logs/',   views.kyc_logs,   name='kyc-logs'),

    # ── ADMIN ─────────────────────────────────────────────────
    path('records/', views.kyc_admin_list, name='kyc-records'),
    path('admin/list/',                      views.kyc_admin_list,        name='kyc-admin-list'),
    path('admin/stats/',                     views.kyc_admin_stats,       name='kyc-admin-stats'),
    path('admin/review/<int:kyc_id>/',       views.kyc_admin_review,      name='kyc-admin-review'),   # GET/POST/PATCH
    path('admin/delete/<int:kyc_id>/',       views.kyc_admin_delete,      name='kyc-admin-delete'),
    path('admin/reset/<int:kyc_id>/',        views.kyc_admin_reset,       name='kyc-admin-reset'),
    path('admin/logs/<int:kyc_id>/',         views.kyc_admin_logs,        name='kyc-admin-logs'),
    path('admin/add-note/<int:kyc_id>/',     views.kyc_admin_add_note,    name='kyc-admin-add-note'),
    path('admin/bulk-action/',               views.kyc_admin_bulk_action, name='kyc-admin-bulk-action'),
]