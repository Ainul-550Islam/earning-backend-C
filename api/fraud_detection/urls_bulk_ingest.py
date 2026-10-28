from django.urls import path
from .views_bulk_ingest import (
    BulkTransactionIngestAPIView, BulkBatchStatusAPIView, BulkUserRiskIngestAPIView,
)
app_name = "bulk_ingest"
urlpatterns = [
    path("transactions/",                          BulkTransactionIngestAPIView.as_view(), name="transactions"),
    path("batches/<str:batch_id>/status/",         BulkBatchStatusAPIView.as_view(),       name="batch-status"),
    path("risk-scores/",                           BulkUserRiskIngestAPIView.as_view(),    name="risk-scores"),
]
