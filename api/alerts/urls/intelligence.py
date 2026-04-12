# alerts/urls/intelligence.py
from django.urls import path
from ..viewsets import intelligence as viewsets_intelligence

app_name = 'intelligence'

urlpatterns = [
    # Alert Correlations
    path('correlations/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-correlation-list'),
    path('correlations/<int:pk>/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-correlation-detail'),
    path('correlations/<int:pk>/analyze/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'post': 'analyze'}), name='alert-correlation-analyze'),
    path('correlations/<int:pk>/predict/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'post': 'predict'}), name='alert-correlation-predict'),
    path('correlations/by_type/<str:type>/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'get': 'by_type'}), name='alert-correlation-by-type'),
    path('correlations/significant/', viewsets_intelligence.AlertCorrelationViewSet.as_view({'get': 'significant'}), name='alert-correlation-significant'),
    
    # Alert Predictions
    path('predictions/', viewsets_intelligence.AlertPredictionViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-prediction-list'),
    path('predictions/<int:pk>/', viewsets_intelligence.AlertPredictionViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-prediction-detail'),
    path('predictions/<int:pk>/train/', viewsets_intelligence.AlertPredictionViewSet.as_view({'post': 'train'}), name='alert-prediction-train'),
    path('predictions/<int:pk>/predict/', viewsets_intelligence.AlertPredictionViewSet.as_view({'post': 'predict'}), name='alert-prediction-predict'),
    path('predictions/<int:pk>/evaluate/', viewsets_intelligence.AlertPredictionViewSet.as_view({'post': 'evaluate'}), name='alert-prediction-evaluate'),
    path('predictions/by_type/<str:type>/', viewsets_intelligence.AlertPredictionViewSet.as_view({'get': 'by_type'}), name='alert-prediction-by-type'),
    path('predictions/active/', viewsets_intelligence.AlertPredictionViewSet.as_view({'get': 'active'}), name='alert-prediction-active'),
    
    # Anomaly Detection Models
    path('anomaly_models/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'get': 'list', 'post': 'create'}), name='anomaly-detection-model-list'),
    path('anomaly_models/<int:pk>/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='anomaly-detection-model-detail'),
    path('anomaly_models/<int:pk>/detect/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'post': 'detect'}), name='anomaly-detection-model-detect'),
    path('anomaly_models/<int:pk>/train/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'post': 'train'}), name='anomaly-detection-model-train'),
    path('anomaly_models/<int:pk>/update_thresholds/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'post': 'update_thresholds'}), name='anomaly-detection-model-update-thresholds'),
    path('anomaly_models/by_method/<str:method>/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'get': 'by_method'}), name='anomaly-detection-model-by-method'),
    path('anomaly_models/active/', viewsets_intelligence.AnomalyDetectionModelViewSet.as_view({'get': 'active'}), name='anomaly-detection-model-active'),
    
    # Alert Noise Filters
    path('noise_filters/', viewsets_intelligence.AlertNoiseViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-noise-filter-list'),
    path('noise_filters/<int:pk>/', viewsets_intelligence.AlertNoiseViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-noise-filter-detail'),
    path('noise_filters/<int:pk>/should_filter/', viewsets_intelligence.AlertNoiseViewSet.as_view({'post': 'should_filter'}), name='alert-noise-filter-should-filter'),
    path('noise_filters/<int:pk>/filter/', viewsets_intelligence.AlertNoiseViewSet.as_view({'post': 'filter'}), name='alert-noise-filter-filter'),
    path('noise_filters/by_type/<str:type>/', viewsets_intelligence.AlertNoiseViewSet.as_view({'get': 'by_type'}), name='alert-noise-filter-by-type'),
    path('noise_filters/active/', viewsets_intelligence.AlertNoiseViewSet.as_view({'get': 'active'}), name='alert-noise-filter-active'),
    path('noise_filters/<int:pk>/effectiveness/', viewsets_intelligence.AlertNoiseViewSet.as_view({'get': 'effectiveness'}), name='alert-noise-filter-effectiveness'),
    
    # Root Cause Analysis
    path('rca/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'get': 'list', 'post': 'create'}), name='root-cause-analysis-list'),
    path('rca/<int:pk>/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='root-cause-analysis-detail'),
    path('rca/<int:pk>/analyze/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'post': 'analyze'}), name='root-cause-analysis-analyze'),
    path('rca/<int:pk>/recommendations/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'get': 'recommendations'}), name='root-cause-analysis-recommendations'),
    path('rca/<int:pk>/submit_for_review/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'post': 'submit_for_review'}), name='root-cause-analysis-submit-for-review'),
    path('rca/<int:pk>/approve/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'post': 'approve'}), name='root-cause-analysis-approve'),
    path('rca/by_method/<str:method>/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'get': 'by_method'}), name='root-cause-analysis-by-method'),
    path('rca/by_status/<str:status>/', viewsets_intelligence.RootCauseAnalysisViewSet.as_view({'get': 'by_status'}), name='root-cause-analysis-by-status'),
    
    # Intelligence Integration
    path('overview/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'get': 'list'}), name='intelligence-integration-list'),
    path('metrics/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'get': 'metrics'}), name='intelligence-integration-metrics'),
    path('analyze/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'post': 'analyze'}), name='intelligence-integration-analyze'),
    path('health/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'get': 'health'}), name='intelligence-integration-health'),
    path('recommendations/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'get': 'recommendations'}), name='intelligence-integration-recommendations'),
    path('trends/', viewsets_intelligence.IntelligenceIntegrationViewSet.as_view({'get': 'trends'}), name='intelligence-integration-trends'),
]
