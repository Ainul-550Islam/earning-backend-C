"""Webhooks Serializers Package

All serializer classes for the webhooks module.
Each model has variants: Create, Update, Detail, List
"""

# Filter serializers
from .WebhookFilterSerializer import (
    WebhookFilterSerializer,
    WebhookFilterCreateSerializer,
    WebhookFilterUpdateSerializer,
    WebhookFilterDetailSerializer,
    WebhookFilterListSerializer,
)

# Batch serializers
from .WebhookBatchSerializer import (
    WebhookBatchSerializer,
    WebhookBatchItemSerializer,
    WebhookBatchCreateSerializer,
    WebhookBatchUpdateSerializer,
    WebhookBatchDetailSerializer,
    WebhookBatchListSerializer,
)

# Secret serializers
from .WebhookSecretSerializer import (
    WebhookSecretSerializer,
    WebhookSecretCreateSerializer,
    WebhookSecretUpdateSerializer,
    WebhookSecretDetailSerializer,
    WebhookSecretListSerializer,
)

# Template serializers
from .WebhookTemplateSerializer import (
    WebhookTemplateSerializer,
    WebhookTemplateCreateSerializer,
    WebhookTemplateUpdateSerializer,
    WebhookTemplateDetailSerializer,
    WebhookTemplateListSerializer,
)

# Inbound webhook serializers
from .InboundWebhookSerializer import (
    InboundWebhookSerializer,
    InboundWebhookCreateSerializer,
    InboundWebhookUpdateSerializer,
    InboundWebhookDetailSerializer,
    InboundWebhookListSerializer,
    InboundWebhookProcessSerializer,
    InboundWebhookValidateSerializer,
    InboundWebhookErrorSerializer,
)

# Other serializers
from .AdminWebhookSerializer import (
    AdminWebhookEndpointSerializer,
    AdminWebhookSubscriptionSerializer,
    AdminWebhookDeliveryLogSerializer,
    AdminWebhookBatchOperationSerializer,
    AdminWebhookStatsSerializer,
    AdminWebhookHealthCheckSerializer,
    AdminWebhookHealthCheckResultSerializer,
    AdminWebhookCleanupSerializer,
    AdminWebhookExportSerializer,
    AdminWebhookImportSerializer,
    AdminWebhookTestSerializer,
    AdminWebhookTestResultSerializer,
)

from .WebhookDeliveryLogSerializer import (
    WebhookDeliveryLogSerializer,
    WebhookDeliveryLogCreateSerializer,
    WebhookDeliveryLogUpdateSerializer,
    WebhookDeliveryLogDetailSerializer,
    WebhookDeliveryLogListSerializer,
    WebhookDeliveryLogRetrySerializer,
    WebhookDeliveryLogStatsSerializer,
)

# BUG FIX: this block (importing the WebhookSubscriptionCreate/Update/Detail/
# List variants from the WebhookSubscriptionSerializer.py submodule) has a
# Python import-system side effect: resolving a dotted submodule path always
# binds that submodule onto the parent package's namespace too - so it
# silently overwrites any name called `WebhookSubscriptionSerializer` that
# was bound to something else moments earlier. The actual
# WebhookSubscriptionSerializer *class* (defined in WebhookEndpointSerializer.py,
# used for simple read/list contexts) is imported explicitly by name in the
# block below, which is placed AFTER this one for exactly that reason - so it
# wins and nothing downstream re-imports from either of these two submodule
# paths again to re-clobber it. (An earlier version of this fix tried
# re-importing the class here instead of reordering; that re-import was
# itself another `from .WebhookEndpointSerializer import ...` statement,
# which would have re-triggered the *same* side effect against
# `WebhookEndpointSerializer`, the other name defined in that file - verified
# empirically before landing on this ordering-based fix instead.)
from .WebhookSubscriptionSerializer import (
    WebhookSubscriptionCreateSerializer,
    WebhookSubscriptionUpdateSerializer,
    WebhookSubscriptionDetailSerializer,
    WebhookSubscriptionListSerializer,
)

from .WebhookEndpointSerializer import (
    WebhookEndpointSerializer,
    WebhookEndpointDetailSerializer,
    SecretRotateSerializer,
    WebhookSubscriptionSerializer,
    EventTypeListAPIViewSerializer,
    WebhookTestSerializer,
)

from .WebhookEventTypeSerializer import (
    WebhookEventTypeSerializer,
    WebhookEventTypeDetailSerializer,
    WebhookEventTypeStatsSerializer,
    WebhookEventTypeFilterSerializer,
    WebhookEventTypeCreateSerializer,
    WebhookEventTypeUpdateSerializer,
    WebhookEventTypeListSerializer,
    WebhookEventTypeSubscriptionSerializer,
    WebhookEventTypeSubscriptionResultSerializer,
    WebhookEventTypePopularSerializer,
    WebhookEventTypeRecentSerializer,
    WebhookEventTypeRecommendationSerializer,
    WebhookEventTypeTrendSerializer,
    WebhookEventTypeValidateSerializer,
    WebhookEventTypeValidateResultSerializer,
)

# NOTE: InboundWebhookLogSerializer also exists (duplicated) inside
# InboundWebhookSerializer.py, but that copy is dead/unused - nothing imports
# it and it lacks the Stats/Process/Filter/Batch variants that
# InboundWebhookLogViewSet.py actually needs. This dedicated file is canonical.
from .InboundWebhookLogSerializer import (
    InboundWebhookLogSerializer,
    InboundWebhookLogCreateSerializer,
    InboundWebhookLogUpdateSerializer,
    InboundWebhookLogDetailSerializer,
    InboundWebhookLogListSerializer,
    InboundWebhookLogProcessSerializer,
    InboundWebhookLogStatsSerializer,
    InboundWebhookLogFilterSerializer,
    InboundWebhookLogBatchSerializer,
)

from .WebhookHealthSerializer import (
    WebhookHealthLogSerializer,
    WebhookHealthLogCreateSerializer,
    WebhookHealthLogUpdateSerializer,
    WebhookHealthLogDetailSerializer,
    WebhookHealthLogListSerializer,
    WebhookHealthCheckSerializer,
    WebhookHealthCheckResultSerializer,
    WebhookHealthStatsSerializer,
    WebhookHealthTrendSerializer,
    WebhookHealthFilterSerializer,
    WebhookHealthBatchSerializer,
    WebhookHealthAlertSerializer,
)

from .WebhookAnalyticsSerializer import (
    WebhookAnalyticsSerializer,
    WebhookEventStatSerializer,
)

from .WebhookEmitSerializer import (
    WebhookEmitSerializer,
    WebhookEmitBatchSerializer,
    WebhookEmitTestSerializer,
    WebhookEmitResultSerializer,
    WebhookEmitBatchResultSerializer,
    WebhookEmitStatsSerializer,
    WebhookEmitFilterSerializer,
    WebhookEmitPreviewSerializer,
    WebhookEmitPreviewResultSerializer,
    WebhookEmitValidateSerializer,
    WebhookEmitValidateResultSerializer,
)

from .WebhookReplaySerializer import (
    WebhookReplaySerializer,
    WebhookReplayCreateSerializer,
    WebhookReplayUpdateSerializer,
    WebhookReplayDetailSerializer,
    WebhookReplayListSerializer,
    WebhookReplayBatchSerializer,
    WebhookReplayBatchCreateSerializer,
    WebhookReplayBatchDetailSerializer,
    WebhookReplayBatchListSerializer,
    WebhookReplayProcessSerializer,
    WebhookReplayStatsSerializer,
    WebhookReplayFilterSerializer,
    WebhookReplayBatchProcessSerializer,
    WebhookReplayRecommendationSerializer,
)

from .WebhookAgingSerializer import (
    WebhookAgingPolicySerializer,
    WebhookEndpointAgingSerializer,
    WebhookDeliveryAgingSerializer,
    WebhookAgingEventSerializer,
    AgingPurgeConfirmSerializer,
)

from .WebhookAnalyticsSerializer import (
    WebhookRateLimitSerializer,
    WebhookRetryAnalysisSerializer,
)

from .WebhookRateLimitSerializer import (
    WebhookReplayItemSerializer,
)

__all__ = [
    # Filter
    "WebhookFilterSerializer",
    "WebhookFilterCreateSerializer",
    "WebhookFilterUpdateSerializer",
    "WebhookFilterDetailSerializer",
    "WebhookFilterListSerializer",
    
    # Batch
    "WebhookBatchSerializer",
    "WebhookBatchCreateSerializer",
    "WebhookBatchUpdateSerializer",
    "WebhookBatchDetailSerializer",
    "WebhookBatchListSerializer",
    "WebhookBatchItemSerializer",
    
    # Secret
    "WebhookSecretSerializer",
    "WebhookSecretCreateSerializer",
    "WebhookSecretUpdateSerializer",
    "WebhookSecretDetailSerializer",
    "WebhookSecretListSerializer",
    
    # Template
    "WebhookTemplateSerializer",
    "WebhookTemplateCreateSerializer",
    "WebhookTemplateUpdateSerializer",
    "WebhookTemplateDetailSerializer",
    "WebhookTemplateListSerializer",
    
    # Inbound
    "InboundWebhookSerializer",
    "InboundWebhookCreateSerializer",
    "InboundWebhookUpdateSerializer",
    "InboundWebhookDetailSerializer",
    "InboundWebhookListSerializer",
    "InboundWebhookProcessSerializer",
    "InboundWebhookValidateSerializer",
    "InboundWebhookErrorSerializer",
    "InboundWebhookLogSerializer",
    "InboundWebhookLogCreateSerializer",
    "InboundWebhookLogUpdateSerializer",
    "InboundWebhookLogDetailSerializer",
    "InboundWebhookLogListSerializer",
    "InboundWebhookLogProcessSerializer",
    "InboundWebhookLogStatsSerializer",
    "InboundWebhookLogFilterSerializer",
    "InboundWebhookLogBatchSerializer",
    
    # Admin
    "AdminWebhookEndpointSerializer",
    "AdminWebhookSubscriptionSerializer",
    "AdminWebhookDeliveryLogSerializer",
    "AdminWebhookBatchOperationSerializer",
    "AdminWebhookStatsSerializer",
    "AdminWebhookHealthCheckSerializer",
    "AdminWebhookHealthCheckResultSerializer",
    "AdminWebhookCleanupSerializer",
    "AdminWebhookExportSerializer",
    "AdminWebhookImportSerializer",
    "AdminWebhookTestSerializer",
    "AdminWebhookTestResultSerializer",
    
    # Delivery Log
    "WebhookDeliveryLogSerializer",
    "WebhookDeliveryLogCreateSerializer",
    "WebhookDeliveryLogUpdateSerializer",
    "WebhookDeliveryLogDetailSerializer",
    "WebhookDeliveryLogListSerializer",
    "WebhookDeliveryLogRetrySerializer",
    "WebhookDeliveryLogStatsSerializer",
    
    # Endpoint
    "WebhookEndpointSerializer",
    "WebhookEndpointDetailSerializer",
    "SecretRotateSerializer",
    "WebhookSubscriptionSerializer",
    "WebhookSubscriptionCreateSerializer",
    "WebhookSubscriptionUpdateSerializer",
    "WebhookSubscriptionDetailSerializer",
    "WebhookSubscriptionListSerializer",
    "EventTypeListAPIViewSerializer",
    "WebhookTestSerializer",
    
    # Event Type
    "WebhookEventTypeSerializer",
    "WebhookEventTypeDetailSerializer",
    "WebhookEventTypeStatsSerializer",
    "WebhookEventTypeFilterSerializer",
    "WebhookEventTypeCreateSerializer",
    "WebhookEventTypeUpdateSerializer",
    "WebhookEventTypeListSerializer",
    "WebhookEventTypeSubscriptionSerializer",
    "WebhookEventTypeSubscriptionResultSerializer",
    "WebhookEventTypePopularSerializer",
    "WebhookEventTypeRecentSerializer",
    "WebhookEventTypeRecommendationSerializer",
    "WebhookEventTypeTrendSerializer",
    "WebhookEventTypeValidateSerializer",
    "WebhookEventTypeValidateResultSerializer",
    
    # Health
    "WebhookHealthLogSerializer",
    "WebhookHealthLogCreateSerializer",
    "WebhookHealthLogUpdateSerializer",
    "WebhookHealthLogDetailSerializer",
    "WebhookHealthLogListSerializer",
    "WebhookHealthCheckSerializer",
    "WebhookHealthCheckResultSerializer",
    "WebhookHealthStatsSerializer",
    "WebhookHealthTrendSerializer",
    "WebhookHealthFilterSerializer",
    "WebhookHealthBatchSerializer",
    "WebhookHealthAlertSerializer",
    
    # Analytics
    "WebhookAnalyticsSerializer",
    "WebhookEventStatSerializer",
    
    # Emit
    "WebhookEmitSerializer",
    "WebhookEmitBatchSerializer",
    "WebhookEmitTestSerializer",
    "WebhookEmitResultSerializer",
    "WebhookEmitBatchResultSerializer",
    "WebhookEmitStatsSerializer",
    "WebhookEmitFilterSerializer",
    "WebhookEmitPreviewSerializer",
    "WebhookEmitPreviewResultSerializer",
    "WebhookEmitValidateSerializer",
    "WebhookEmitValidateResultSerializer",
    
    # Replay
    "WebhookReplaySerializer",
    "WebhookReplayCreateSerializer",
    "WebhookReplayUpdateSerializer",
    "WebhookReplayDetailSerializer",
    "WebhookReplayListSerializer",
    "WebhookReplayBatchSerializer",
    "WebhookReplayBatchCreateSerializer",
    "WebhookReplayBatchDetailSerializer",
    "WebhookReplayBatchListSerializer",
    "WebhookReplayProcessSerializer",
    "WebhookReplayStatsSerializer",
    "WebhookReplayFilterSerializer",
    "WebhookReplayBatchProcessSerializer",
    "WebhookReplayRecommendationSerializer",
    
    # Aging
    "WebhookAgingPolicySerializer",
    "WebhookEndpointAgingSerializer",
    "WebhookDeliveryAgingSerializer",
    "WebhookAgingEventSerializer",
    "AgingPurgeConfirmSerializer",
    
    # Rate limit / retry analysis / replay item
    "WebhookRateLimitSerializer",
    "WebhookRetryAnalysisSerializer",
    "WebhookReplayItemSerializer",
]
