# fraud_detection/urls_mfa.py — MFA URL routing
from django.urls import path
from .views_mfa import (
    MFAEnrollInitAPIView, MFAEnrollConfirmAPIView, MFAValidateAPIView,
    MFAValidateActionAPIView, MFAStatusAPIView, MFARevokeSessionAPIView,
    MFAAdminStatusAPIView,
)
app_name = "mfa"
urlpatterns = [
    path("enroll/init/",                        MFAEnrollInitAPIView.as_view(),       name="enroll-init"),
    path("enroll/confirm/",                     MFAEnrollConfirmAPIView.as_view(),    name="enroll-confirm"),
    path("validate/",                           MFAValidateAPIView.as_view(),         name="validate"),
    path("validate-action/",                    MFAValidateActionAPIView.as_view(),   name="validate-action"),
    path("status/",                             MFAStatusAPIView.as_view(),           name="status"),
    path("revoke-session/",                     MFARevokeSessionAPIView.as_view(),    name="revoke-session"),
    path("admin/users/<int:user_id>/status/",   MFAAdminStatusAPIView.as_view(),      name="admin-user-status"),
]
