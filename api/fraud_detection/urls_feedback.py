from django.urls import path
from .views_feedback import (
    FeedbackSubmitAPIView, FeedbackBulkAPIView, FeedbackAnalystStatsAPIView,
    FeedbackTeamStatsAPIView, FeedbackFPRateAPIView, FeedbackAdaptiveThresholdAPIView,
)
app_name = "feedback"
urlpatterns = [
    path("submit/",                                  FeedbackSubmitAPIView.as_view(),           name="submit"),
    path("bulk/",                                    FeedbackBulkAPIView.as_view(),             name="bulk"),
    path("analysts/me/stats/",                       FeedbackAnalystStatsAPIView.as_view(),     name="analyst-stats"),
    path("analysts/team-stats/",                     FeedbackTeamStatsAPIView.as_view(),        name="team-stats"),
    path("fp-rate/",                                 FeedbackFPRateAPIView.as_view(),           name="fp-rate"),
    path("adaptive-threshold/<str:detector>/",       FeedbackAdaptiveThresholdAPIView.as_view(),name="adaptive-threshold"),
]
