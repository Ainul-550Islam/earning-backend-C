# api/payment_gateways/rtb/urls.py
from django.urls import path
from .views import best_offer, offerwall_offers

app_name = 'rtb'
urlpatterns = [
    path('best-offer/',  best_offer,       name='best-offer'),
    path('offerwall/',   offerwall_offers,  name='offerwall'),
]
