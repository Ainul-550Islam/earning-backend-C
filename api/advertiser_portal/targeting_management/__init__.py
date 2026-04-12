"""
Targeting Management Package

This package contains all modules related to targeting management,
including audience segmentation, geographic targeting, device targeting,
and behavioral targeting.
"""

from .services import *
from .views import *
from .serializers import *
from .urls import *

__all__ = [
    # Services
    'TargetingService',
    'AudienceSegmentService',
    'GeographicTargetingService',
    'DeviceTargetingService',
    'BehavioralTargetingService',
    'TargetingOptimizationService',
    
    # Views
    'TargetingViewSet',
    'AudienceSegmentViewSet',
    'GeographicTargetingViewSet',
    'DeviceTargetingViewSet',
    'BehavioralTargetingViewSet',
    'TargetingOptimizationViewSet',
    
    # Serializers
    'TargetingSerializer',
    'TargetingDetailSerializer',
    'TargetingCreateSerializer',
    'TargetingUpdateSerializer',
    'AudienceSegmentSerializer',
    'GeographicTargetingSerializer',
    'DeviceTargetingSerializer',
    'BehavioralTargetingSerializer',
    'TargetingOptimizationSerializer',
    
    # URLs
    'targeting_urls',
]
