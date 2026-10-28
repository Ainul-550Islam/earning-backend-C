from django.urls import path
from .views_sla import (
    SLADashboardAPIView, SLABreachedCasesAPIView, SLACaseStatusAPIView,
    SLAEscalateAPIView, SLAAutoEscalateAPIView,
)
app_name = "sla"
urlpatterns = [
    path("dashboard/",                   SLADashboardAPIView.as_view(),      name="dashboard"),
    path("breached/",                    SLABreachedCasesAPIView.as_view(),  name="breached"),
    path("cases/<int:case_id>/",         SLACaseStatusAPIView.as_view(),     name="case-status"),
    path("cases/<int:case_id>/escalate/",SLAEscalateAPIView.as_view(),       name="escalate"),
    path("auto-escalate/",               SLAAutoEscalateAPIView.as_view(),   name="auto-escalate"),
]
