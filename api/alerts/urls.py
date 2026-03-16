# alerts/urls.py  —  100% Complete & Fixed
from django.urls import path
from . import api_views

urlpatterns = [
    # Overview
    path('',                                    api_views.alerts_overview,          name='alerts-overview'),

    # Alert Rules CRUD
    path('rules/',                              api_views.alert_rules_list,         name='alert-rules-list'),
    path('rules/create/',                       api_views.alert_rule_create,        name='alert-rule-create'),
    path('rules/stats/',                        api_views.alert_rules_stats,        name='alert-rules-stats'),          # ✅ ADDED
    path('rules/bulk-update-status/',           api_views.alert_rule_bulk_update_status, name='alert-rule-bulk-status'), # ✅ ADDED
    path('rules/<int:rule_id>/',                api_views.alert_rule_detail,        name='alert-rule-detail'),
    path('rules/<int:rule_id>/toggle/',         api_views.alert_rule_toggle,        name='alert-rule-toggle'),
    path('rules/<int:rule_id>/test/',           api_views.alert_rule_test,          name='alert-rule-test'),

    # Alert Logs
    path('logs/',                               api_views.alert_logs_list,          name='alert-logs-list'),
    path('logs/stats/',                         api_views.alert_logs_stats,         name='alert-logs-stats'),           # ✅ ADDED
    path('logs/bulk-resolve/',                  api_views.alert_log_bulk_resolve,   name='alert-log-bulk-resolve'),
    path('logs/<int:log_id>/',                  api_views.alert_log_detail,         name='alert-log-detail'),           # ✅ ADDED
    path('logs/<int:log_id>/resolve/',          api_views.alert_log_resolve,        name='alert-log-resolve'),
    path('logs/<int:log_id>/delete/',           api_views.alert_log_delete,         name='alert-log-delete'),

    # System Health
    path('health/',                             api_views.system_health,            name='system-health'),
]