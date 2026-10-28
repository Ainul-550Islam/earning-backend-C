# alerts/urls/channel.py  — FIXED: all missing viewset actions now exposed
from django.urls import path
from ..viewsets import channel as viewsets_channel

app_name = 'channel'

urlpatterns = [
    # ── Alert Channels ───────────────────────────────────────────────────────
    path('', viewsets_channel.AlertChannelViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-channel-list'),
    path('<int:pk>/', viewsets_channel.AlertChannelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-channel-detail'),
    path('<int:pk>/enable/', viewsets_channel.AlertChannelViewSet.as_view({'post': 'enable'}), name='alert-channel-enable'),
    path('<int:pk>/disable/', viewsets_channel.AlertChannelViewSet.as_view({'post': 'disable'}), name='alert-channel-disable'),
    path('<int:pk>/test/', viewsets_channel.AlertChannelViewSet.as_view({'post': 'test'}), name='alert-channel-test'),
    path('<int:pk>/health/', viewsets_channel.AlertChannelViewSet.as_view({'get': 'health'}), name='alert-channel-health'),
    path('<int:pk>/statistics/', viewsets_channel.AlertChannelViewSet.as_view({'get': 'statistics'}), name='alert-channel-statistics'),
    path('health-summary/', viewsets_channel.AlertChannelViewSet.as_view({'get': 'health_overview'}), name='alert-channel-health-summary'),    # ADDED
    path('usage-statistics/', viewsets_channel.AlertChannelViewSet.as_view({'get': 'usage_statistics'}), name='alert-channel-usage-stats'),   # ADDED

    # ── Channel Routes ───────────────────────────────────────────────────────
    path('routes/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'list', 'post': 'create'}), name='channel-route-list'),
    path('routes/<int:pk>/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='channel-route-detail'),
    path('routes/<int:pk>/activate/', viewsets_channel.ChannelRouteViewSet.as_view({'post': 'activate'}), name='channel-route-activate'),
    path('routes/<int:pk>/deactivate/', viewsets_channel.ChannelRouteViewSet.as_view({'post': 'deactivate'}), name='channel-route-deactivate'),
    path('routes/<int:pk>/test/', viewsets_channel.ChannelRouteViewSet.as_view({'post': 'test'}), name='channel-route-test'),
    path('routes/<int:pk>/test-routing/', viewsets_channel.ChannelRouteViewSet.as_view({'post': 'test_routing'}), name='channel-route-test-routing'),         # ADDED
    path('routes/<int:pk>/destinations/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'get_destination_channels'}), name='channel-route-destinations'), # ADDED
    path('routes/by_type/<str:type>/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'by_type'}), name='channel-route-by-type'),
    path('routes/active/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'active'}), name='channel-route-active'),
    path('routes/summary/', viewsets_channel.ChannelRouteViewSet.as_view({'get': 'summary'}), name='channel-route-summary'),                                   # ADDED

    # ── Channel Health Logs ──────────────────────────────────────────────────
    path('health_logs/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'list', 'post': 'create'}), name='channel-health-log-list'),
    path('health_logs/<int:pk>/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='channel-health-log-detail'),
    path('health_logs/by_channel/<int:channel_id>/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'by_channel'}), name='channel-health-log-by-channel'),
    path('health_logs/by_status/<str:status>/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'by_status'}), name='channel-health-log-by-status'),
    path('health_logs/by_type/<str:type>/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'by_type'}), name='channel-health-log-by-type'),
    path('health_logs/recent/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'recent'}), name='channel-health-log-recent'),
    path('health_logs/statistics/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'statistics'}), name='channel-health-log-statistics'),
    path('health_logs/overview/', viewsets_channel.ChannelHealthLogViewSet.as_view({'get': 'health_overview'}), name='channel-health-log-overview'),           # ADDED
    path('health_logs/<int:pk>/health-check/', viewsets_channel.ChannelHealthLogViewSet.as_view({'post': 'health_check'}), name='channel-health-log-check'),   # ADDED

    # ── Channel Rate Limits ──────────────────────────────────────────────────
    path('rate_limits/', viewsets_channel.ChannelRateLimitViewSet.as_view({'get': 'list', 'post': 'create'}), name='channel-rate-limit-list'),
    path('rate_limits/<int:pk>/', viewsets_channel.ChannelRateLimitViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='channel-rate-limit-detail'),
    path('rate_limits/<int:pk>/consume_token/', viewsets_channel.ChannelRateLimitViewSet.as_view({'post': 'consume_token'}), name='channel-rate-limit-consume-token'),
    path('rate_limits/<int:pk>/refill_tokens/', viewsets_channel.ChannelRateLimitViewSet.as_view({'post': 'refill_tokens'}), name='channel-rate-limit-refill-tokens'),
    path('rate_limits/<int:pk>/reset/', viewsets_channel.ChannelRateLimitViewSet.as_view({'post': 'reset'}), name='channel-rate-limit-reset'),
    path('rate_limits/<int:pk>/status/', viewsets_channel.ChannelRateLimitViewSet.as_view({'get': 'status'}), name='channel-rate-limit-status'),
    path('rate_limits/<int:pk>/test/', viewsets_channel.ChannelRateLimitViewSet.as_view({'post': 'test_rate_limit'}), name='channel-rate-limit-test'),          # ADDED
    path('rate_limits/by_channel/<int:channel_id>/', viewsets_channel.ChannelRateLimitViewSet.as_view({'get': 'by_channel'}), name='channel-rate-limit-by-channel'),
    path('rate_limits/by_type/<str:type>/', viewsets_channel.ChannelRateLimitViewSet.as_view({'get': 'by_type'}), name='channel-rate-limit-by-type'),

    # ── Alert Recipients ─────────────────────────────────────────────────────
    path('recipients/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'list', 'post': 'create'}), name='alert-recipient-list'),
    path('recipients/<int:pk>/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='alert-recipient-detail'),
    path('recipients/<int:pk>/activate/', viewsets_channel.AlertRecipientViewSet.as_view({'post': 'activate'}), name='alert-recipient-activate'),
    path('recipients/<int:pk>/deactivate/', viewsets_channel.AlertRecipientViewSet.as_view({'post': 'deactivate'}), name='alert-recipient-deactivate'),
    path('recipients/<int:pk>/test/', viewsets_channel.AlertRecipientViewSet.as_view({'post': 'test'}), name='alert-recipient-test'),
    path('recipients/<int:pk>/availability/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'availability', 'post': 'update_availability'}), name='alert-recipient-availability'),  # ADDED
    path('recipients/available-for-type/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'available_for_type'}), name='alert-recipient-available-for-type'),                        # ADDED
    path('recipients/by_type/<str:type>/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'by_type'}), name='alert-recipient-by-type'),
    path('recipients/active/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'active'}), name='alert-recipient-active'),
    path('recipients/by_priority/<str:priority>/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'by_priority'}), name='alert-recipient-by-priority'),
    path('recipients/<int:pk>/statistics/', viewsets_channel.AlertRecipientViewSet.as_view({'get': 'statistics'}), name='alert-recipient-statistics'),
    path('recipients/<int:pk>/reset_counters/', viewsets_channel.AlertRecipientViewSet.as_view({'post': 'reset_counters'}), name='alert-recipient-reset-counters'),
]
