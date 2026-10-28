# =============================================================================
# fraud_detection/urls_resources.py — NEW FILE
#
# Connects resources.py (resource-layer APIViews) to URL paths.
# WAS FLOATING: resources.py had 10 resource classes with no URL wiring.
# Also registers schemas.py OpenAPI schema endpoint.
# Included by master urls.py under: path("resources/", include(...))
# =============================================================================
from django.urls import path
from .resources import (
    FraudCaseResource,
    FraudCaseDetailResource,
    FraudAlertResource,
    FraudDetectionResource,
    RiskAssessmentResource,
    ComplianceResource,
    AnalyticsResource,
    ThreatIntelligenceResource,
    ExportResource,
)

app_name = "resources"

urlpatterns = [
    # Fraud cases
    path("fraud-cases/",          FraudCaseResource.as_view(),        name="fraud-cases"),
    path("fraud-cases/<int:pk>/", FraudCaseDetailResource.as_view(),  name="fraud-case-detail"),
    # Alerts
    path("fraud-alerts/",         FraudAlertResource.as_view(),       name="fraud-alerts"),
    # Detection & risk
    path("fraud-detection/",      FraudDetectionResource.as_view(),   name="fraud-detection"),
    path("risk-assessment/",      RiskAssessmentResource.as_view(),   name="risk-assessment"),
    # Compliance & analytics
    path("compliance/",           ComplianceResource.as_view(),       name="compliance"),
    path("analytics/",            AnalyticsResource.as_view(),        name="analytics"),
    # Intelligence & export
    path("threat-intelligence/",  ThreatIntelligenceResource.as_view(), name="threat-intelligence"),
    path("export/",               ExportResource.as_view(),           name="export"),
]
