# =============================================================================
# fraud_detection/urls_endpoint.py
#
# Connects endpoint.py function-based views to URL paths.
# WAS FLOATING: endpoint.py had 9 endpoint functions, all unreachable.
# Included by master urls.py under: path("external/", include(...))
# =============================================================================
from django.urls import path
from .endpoint import (
    fraud_detection_webhook,
    comprehensive_fraud_detection,
    ip_reputation_check,
    sanctions_screening,
    fraud_case_management,
    fraud_analytics,
    risk_profile_update,
    external_fraud_report,
    system_health_check,
)

app_name = "endpoint"

urlpatterns = [
    path("webhook/fraud-alert/",        fraud_detection_webhook,       name="webhook-fraud-alert"),
    path("fraud-detection/",            comprehensive_fraud_detection,  name="comprehensive-fraud-detection"),
    path("ip-reputation/",              ip_reputation_check,            name="ip-reputation-check"),
    path("sanctions/",                  sanctions_screening,            name="sanctions-screening"),
    path("fraud-case/",                 fraud_case_management,         name="fraud-case-management"),
    path("analytics/",                  fraud_analytics,               name="fraud-analytics"),
    path("risk-profile/",               risk_profile_update,           name="risk-profile-update"),
    path("external-report/",            external_fraud_report,         name="external-fraud-report"),
    path("health/",                     system_health_check,           name="system-health-check"),
]
