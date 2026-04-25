# api/payment_gateways/smartlink/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmartLinkViewSet, smartlink_redirect

app_name = 'smartlink'
router   = DefaultRouter()
router.register(r'smartlinks', SmartLinkViewSet, basename='smartlink')

urlpatterns = [
    path('', include(router.urls)),
    # Public SmartLink redirect — /go/{slug}/
    path('go/<str:slug>/', smartlink_redirect, name='smartlink-redirect'),
]
