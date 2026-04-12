# kyc/transaction_monitoring/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    path('admin/rules/',                 views.tm_rules,        name='tm-rules'),
    path('admin/rules/<int:rule_id>/',   views.tm_rule_detail,  name='tm-rule-detail'),
    path('admin/alerts/',                views.tm_alerts,       name='tm-alerts'),
    path('admin/alerts/<int:alert_id>/action/', views.tm_alert_action, name='tm-alert-action'),
]
