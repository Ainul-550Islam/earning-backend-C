# alerts/urls/threshold.py
from django.urls import path
from ..viewsets import threshold as viewsets_threshold

app_name = 'threshold'

urlpatterns = [
    # Threshold Configs
    path('configs/', viewsets_threshold.ThresholdConfigViewSet.as_view({'get': 'list', 'post': 'create'}), name='threshold-config-list'),
    path('configs/<int:pk>/', viewsets_threshold.ThresholdConfigViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='threshold-config-detail'),
    path('configs/<int:pk>/evaluate/', viewsets_threshold.ThresholdConfigViewSet.as_view({'post': 'evaluate'}), name='threshold-config-evaluate'),
    path('configs/<int:pk>/effectiveness/', viewsets_threshold.ThresholdConfigViewSet.as_view({'get': 'effectiveness'}), name='threshold-config-effectiveness'),
    path('configs/<int:pk>/optimize/', viewsets_threshold.ThresholdConfigViewSet.as_view({'post': 'optimize'}), name='threshold-config-optimize'),
    
    # Threshold Breaches
    path('breaches/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'list', 'post': 'create'}), name='threshold-breach-list'),
    path('breaches/<int:pk>/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='threshold-breach-detail'),
    path('breaches/<int:pk>/resolve/', viewsets_threshold.ThresholdBreachViewSet.as_view({'post': 'resolve'}), name='threshold-breach-resolve'),
    path('breaches/by_severity/<str:severity>/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'by_severity'}), name='threshold-breach-by-severity'),
    path('breaches/active/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'active'}), name='threshold-breach-active'),
    path('breaches/statistics/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'statistics'}), name='threshold-breach-statistics'),
    path('breaches/trends/', viewsets_threshold.ThresholdBreachViewSet.as_view({'get': 'trends'}), name='threshold-breach-trends'),
    
    # Adaptive Thresholds
    path('adaptive/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'get': 'list', 'post': 'create'}), name='adaptive-threshold-list'),
    path('adaptive/<int:pk>/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='adaptive-threshold-detail'),
    path('adaptive/<int:pk>/train/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'post': 'train'}), name='adaptive-threshold-train'),
    path('adaptive/<int:pk>/adapt/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'post': 'adapt'}), name='adaptive-threshold-adapt'),
    path('adaptive/<int:pk>/history/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'get': 'history'}), name='adaptive-threshold-history'),
    path('adaptive/<int:pk>/training_status/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'get': 'training_status'}), name='adaptive-threshold-training-status'),
    path('adaptive/<int:pk>/reset/', viewsets_threshold.AdaptiveThresholdViewSet.as_view({'post': 'reset'}), name='adaptive-threshold-reset'),
    
    # Threshold History
    path('history/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'list', 'post': 'create'}), name='threshold-history-list'),
    path('history/<int:pk>/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='threshold-history-detail'),
    path('history/by_type/<str:type>/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'by_type'}), name='threshold-history-by-type'),
    path('history/by_adaptive/<int:adaptive_id>/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'by_adaptive'}), name='threshold-history-by-adaptive'),
    path('history/trends/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'trends'}), name='threshold-history-trends'),
    path('history/frequency/<int:config_id>/', viewsets_threshold.ThresholdHistoryViewSet.as_view({'get': 'frequency'}), name='threshold-history-frequency'),
    
    # Threshold Profiles
    path('profiles/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'list', 'post': 'create'}), name='threshold-profile-list'),
    path('profiles/<int:pk>/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='threshold-profile-detail'),
    path('profiles/<int:pk>/apply/', viewsets_threshold.ThresholdProfileViewSet.as_view({'post': 'apply'}), name='threshold-profile-apply'),
    path('profiles/<int:pk>/thresholds/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'thresholds'}), name='threshold-profile-thresholds'),
    path('profiles/<int:pk>/mappings/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'mappings'}), name='threshold-profile-mappings'),
    path('profiles/<int:pk>/validate/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'validate'}), name='threshold-profile-validate'),
    path('profiles/<int:pk>/clone/', viewsets_threshold.ThresholdProfileViewSet.as_view({'post': 'clone'}), name='threshold-profile-clone'),
    path('profiles/<int:pk>/export/', viewsets_threshold.ThresholdProfileViewSet.as_view({'get': 'export'}), name='threshold-profile-export'),
    path('profiles/import/', viewsets_threshold.ThresholdProfileViewSet.as_view({'post': 'import'}), name='threshold-profile-import'),
]
