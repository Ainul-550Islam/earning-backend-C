from django.urls import path
from .views_chargeback import (
    ChargebackOpenAPIView, ChargebackUpdateAPIView, ChargebackEvidenceAPIView,
    ChargebackUserRateAPIView, ChargebackStatsAPIView, ChargebackHighRiskAPIView,
)
app_name = "chargeback"
urlpatterns = [
    path("open/",                           ChargebackOpenAPIView.as_view(),       name="open"),
    path("<str:dispute_id>/status/",        ChargebackUpdateAPIView.as_view(),     name="update-status"),
    path("<str:dispute_id>/evidence/",      ChargebackEvidenceAPIView.as_view(),   name="evidence"),
    path("users/<int:user_id>/rate/",       ChargebackUserRateAPIView.as_view(),   name="user-rate"),
    path("stats/",                          ChargebackStatsAPIView.as_view(),      name="stats"),
    path("high-risk/",                      ChargebackHighRiskAPIView.as_view(),   name="high-risk"),
]
