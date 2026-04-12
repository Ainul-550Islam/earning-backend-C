from django.urls import re_path
from .consumers import SmartLinkLiveConsumer, PublisherDashboardConsumer

websocket_urlpatterns = [
    re_path(r'ws/smartlink/(?P<slug>[a-z0-9_-]+)/live/$', SmartLinkLiveConsumer.as_asgi()),
    re_path(r'ws/publisher/dashboard/$', PublisherDashboardConsumer.as_asgi()),
]
