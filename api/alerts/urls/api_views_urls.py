"""
urls/api_views_urls.py — NEWLY CREATED
Registers all 15 function-based views from api_views.py.
Previously these were defined but had ZERO URL registration — total dead code.
Now accessible under /api/v1/apiv/ prefix.
"""
from django.urls import path
from api.alerts import api_views

app_name = 'apiv'

urlpatterns = [
    # ── Overview ───────────────────────────────────────────────────────
    path('overview/',
         api_views.alerts_overview,
         name='overview'),

    # ── Alert Rules ────────────────────────────────────────────────────
    path('rules/',
         api_views.alert_rules_list,
         name='rules-list'),
    path('rules/stats/',
         api_views.alert_rules_stats,
         name='rules-stats'),
    path('rules/create/',
         api_views.alert_rule_create,
         name='rules-create'),
    path('rules/<int:rule_id>/',
         api_views.alert_rule_detail,
         name='rules-detail'),
    path('rules/bulk/status/',
         api_views.alert_rule_bulk_update_status,
         name='rules-bulk-status'),
    path('rules/<int:rule_id>/toggle/',
         api_views.alert_rule_toggle,
         name='rules-toggle'),
    path('rules/<int:rule_id>/test/',
         api_views.alert_rule_test,
         name='rules-test'),

    # ── Alert Logs ─────────────────────────────────────────────────────
    path('logs/',
         api_views.alert_logs_list,
         name='logs-list'),
    path('logs/stats/',
         api_views.alert_logs_stats,
         name='logs-stats'),
    path('logs/<int:log_id>/',
         api_views.alert_log_detail,
         name='logs-detail'),
    path('logs/<int:log_id>/resolve/',
         api_views.alert_log_resolve,
         name='logs-resolve'),
    path('logs/bulk/resolve/',
         api_views.alert_log_bulk_resolve,
         name='logs-bulk-resolve'),
    path('logs/<int:log_id>/delete/',
         api_views.alert_log_delete,
         name='logs-delete'),

    # ── System Health ──────────────────────────────────────────────────
    path('system/health/',
         api_views.system_health,
         name='system-health'),
]
