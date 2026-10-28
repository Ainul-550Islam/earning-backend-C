"""
URL configuration for Feature Flags & A/B Testing.

FIX: previously registered BOTH the DRF router ViewSets AND a parallel
set of traditional `views/*.py` classes at the SAME paths (e.g.
`/api/v1/feature-flags/flags/` was handled by both `FeatureFlagViewSet`
and `FeatureFlagView`). The duplicate `views/` package has been deleted
entirely (see views/ removal) and this file now registers only the
ViewSets, which is also where all validation/permissions/auditing live.

NEW: registers the audit-log viewset (read-only) added for the audit
trail feature.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .viewsets.feature_flag_viewset import FeatureFlagViewSet
from .viewsets.flag_variant_viewset import FlagVariantViewSet
from .viewsets.experiment_viewset import ExperimentViewSet
from .viewsets.experiment_participant_viewset import ExperimentParticipantViewSet
from .viewsets.rollout_rule_viewset import RolloutRuleViewSet
from .viewsets.analytics_viewset import FlagAnalyticsViewSet
from .viewsets.audit_viewset import AuditLogViewSet  # NEW
from .health import health_check  # NEW

# DRF Router — single source of truth for all routing in this app.
router = DefaultRouter()
router.register(r'flags', FeatureFlagViewSet, basename='featureflag')
router.register(r'variants', FlagVariantViewSet, basename='flagvariant')
router.register(r'experiments', ExperimentViewSet, basename='experiment')
router.register(r'participants', ExperimentParticipantViewSet, basename='experimentparticipant')
router.register(r'rollout-rules', RolloutRuleViewSet, basename='rolloutrule')
router.register(r'analytics', FlagAnalyticsViewSet, basename='flaganalytics')
router.register(r'audit-logs', AuditLogViewSet, basename='auditlog')  # NEW

urlpatterns = [
    path('api/v1/feature-flags/', include(router.urls)),

    # NEW: lightweight health check endpoint (Missing Component: Operations)
    path('api/v1/feature-flags/health/', health_check, name='health-check'),
]
