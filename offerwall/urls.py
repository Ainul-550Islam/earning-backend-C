# offerwall/urls.py
"""URL routing for the Offerwall app."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OfferViewSet,
    MyConversionsViewSet,
    AdminOfferViewSet,
    AdminConversionViewSet,
    OfferwallPostbackView,
)

app_name = 'offerwall'

router = DefaultRouter()
router.register(r'offers',          OfferViewSet,          basename='offer')
router.register(r'my-conversions',  MyConversionsViewSet,  basename='my-conversion')
router.register(r'admin/offers',    AdminOfferViewSet,     basename='admin-offer')
router.register(r'admin/conversions', AdminConversionViewSet, basename='admin-conversion')
router.register(r'postback',        OfferwallPostbackView, basename='postback')

urlpatterns = [
    path('', include(router.urls)),
]
