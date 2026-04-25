# api/payment_gateways/locker/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContentLockerViewSet, OfferWallViewSet, my_virtual_balances, my_rewards_history

app_name = 'locker'
router   = DefaultRouter()
router.register(r'lockers',     ContentLockerViewSet, basename='locker')
router.register(r'offerwalls',  OfferWallViewSet,     basename='offerwall')

urlpatterns = [
    path('', include(router.urls)),
    path('virtual-balances/',  my_virtual_balances,  name='virtual-balances'),
    path('rewards-history/',   my_rewards_history,   name='rewards-history'),
]
