# api/payment_gateways/tracking/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (ClickViewSet, ConversionViewSet, PostbackLogViewSet,
                    postback, click_redirect, publisher_stats)

app_name = 'tracking'
router   = DefaultRouter()
router.register(r'clicks',       ClickViewSet,       basename='click')
router.register(r'conversions',  ConversionViewSet,  basename='conversion')
router.register(r'postback-logs',PostbackLogViewSet, basename='postback-log')

urlpatterns = [
    path('', include(router.urls)),
    path('postback/',               postback,        name='postback'),
    path('postback/<int:offer_id>/', postback,       name='postback-offer'),
    path('click/<int:offer_id>/',    click_redirect, name='click-redirect'),
    path('stats/',                   publisher_stats, name='publisher-stats'),
]

# Real-time stats SSE
from .RealtimeStats import realtime_stats_stream
urlpatterns += [
    path('stats/live/', realtime_stats_stream, name='realtime-stats'),
]

# Pixel tracking endpoints
from .PixelTracker import PixelTracker
from django.views.decorators.csrf import csrf_exempt

pixel_tracker = PixelTracker()

from django.urls import path as _path
urlpatterns += [
    _path('pixel.gif',  csrf_exempt(lambda r: pixel_tracker.track_pixel(r)),    name='pixel-gif'),
    _path('pixel.js',   csrf_exempt(lambda r: pixel_tracker.track_js_pixel(r)), name='pixel-js'),
]
