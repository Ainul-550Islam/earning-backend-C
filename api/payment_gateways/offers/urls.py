# api/payment_gateways/offers/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OfferViewSet, CampaignViewSet, PublisherApplicationViewSet

app_name = 'offers'
router   = DefaultRouter()
router.register(r'offers',       OfferViewSet,                basename='offer')
router.register(r'campaigns',    CampaignViewSet,             basename='campaign')
router.register(r'applications', PublisherApplicationViewSet, basename='application')
urlpatterns = [path('', include(router.urls))]

# Offer API feed
from .OfferAPIView import offer_feed, offer_detail_api
urlpatterns += [
    path('api/feed/',          offer_feed,       name='offer-feed'),
    path('api/<int:offer_id>/', offer_detail_api, name='offer-detail-api'),
]
