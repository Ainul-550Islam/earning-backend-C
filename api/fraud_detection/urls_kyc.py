# fraud_detection/urls_kyc.py — KYC URL routing
from django.urls import path
from .views_kyc import (
    KYCSubmitAPIView, KYCStatusAPIView, KYCUserStatusAPIView,
    KYCBulkStatusAPIView, KYCDecisionAPIView,
    KYCUnverifiedHighRiskAPIView, KYCVerifyCheckAPIView,
)

app_name = "kyc"

urlpatterns = [
    path("submit/",                               KYCSubmitAPIView.as_view(),              name="submit"),
    path("status/",                               KYCStatusAPIView.as_view(),              name="my-status"),
    path("users/<int:user_id>/status/",           KYCUserStatusAPIView.as_view(),          name="user-status"),
    path("bulk-status/",                          KYCBulkStatusAPIView.as_view(),          name="bulk-status"),
    path("submissions/<str:submission_id>/decide/", KYCDecisionAPIView.as_view(),          name="decision"),
    path("unverified-high-risk/",                 KYCUnverifiedHighRiskAPIView.as_view(),  name="unverified-high-risk"),
    path("verify/<int:user_id>/",                 KYCVerifyCheckAPIView.as_view(),         name="verify-check"),
]
