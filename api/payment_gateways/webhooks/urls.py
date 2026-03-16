# api/payment_gateways/webhooks/urls.py

from django.urls import path
from . import bkash_webhook, stripe_webhook, nagad_webhook

app_name = 'payment_webhooks'

urlpatterns = [
    # bKash webhook endpoint
    path('bkash/', bkash_webhook, name='bkash_webhook'),
    path('bkash/callback/', bkash_webhook, name='bkash_webhook_callback'),
    
    # Stripe webhook endpoint
    path('stripe/', stripe_webhook, name='stripe_webhook'),
    
    # Nagad webhook endpoint
    path('nagad/', nagad_webhook, name='nagad_webhook'),
    path('nagad/callback/', nagad_webhook, name='nagad_webhook_callback'),
]