# =============================================================================
# fraud_detection/urls_tenant.py  — TENANT URL ROUTING
# Included in master urls.py under: path("tenant/", include(...))
# =============================================================================
from django.urls import path
from .views_tenant import (
    OrganisationListCreateAPIView,
    OrganisationDetailAPIView,
    OrganisationMembersAPIView,
    OrganisationRotateKeyAPIView,
)

app_name = "tenant"

urlpatterns = [
    path("organisations/",                                  OrganisationListCreateAPIView.as_view(), name="org-list-create"),
    path("organisations/<uuid:pk>/",                        OrganisationDetailAPIView.as_view(),     name="org-detail"),
    path("organisations/<uuid:pk>/members/",                OrganisationMembersAPIView.as_view(),    name="org-members"),
    path("organisations/<uuid:pk>/rotate-key/",             OrganisationRotateKeyAPIView.as_view(),  name="org-rotate-key"),
]
