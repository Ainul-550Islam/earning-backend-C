from django.urls import path
from .views_reports import (
    ReportRequestAPIView, ReportStatusAPIView, ReportDownloadAPIView,
    ReportListAPIView, ReportScheduleRunAPIView,
)
app_name = "reports"
urlpatterns = [
    path("",                                  ReportListAPIView.as_view(),        name="list"),
    path("request/",                          ReportRequestAPIView.as_view(),     name="request"),
    path("<str:report_id>/status/",           ReportStatusAPIView.as_view(),      name="status"),
    path("<str:report_id>/download/",         ReportDownloadAPIView.as_view(),    name="download"),
    path("schedule/run/",                     ReportScheduleRunAPIView.as_view(), name="schedule-run"),
]
