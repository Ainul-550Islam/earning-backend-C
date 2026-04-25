# api/payment_gateways/webhooks/urls.py
# All 8 gateway webhook endpoints

from django.urls import path
from .BkashWebhook import bkash_webhook as bkash_callback
from .NagadWebhook import nagad_webhook as nagad_callback
from .SSLCommerzWebhook import sslcommerz_ipn as sslcommerz_ipn
from .AmarPayWebhook import amarpay_ipn as amarpay_ipn
from .UpayWebhook import upay_callback as upay_callback
from .ShurjoPayWebhook import shurjopay_callback as shurjopay_callback
from .StripeWebhook     import stripe_webhook
from .PayPalWebhook     import paypal_webhook

app_name = 'webhooks'

urlpatterns = [
    path('bkash/',      bkash_callback,     name='bkash-callback'),
    path('nagad/',      nagad_callback,     name='nagad-callback'),
    path('sslcommerz/', sslcommerz_ipn,     name='sslcommerz-ipn'),
    path('amarpay/',    amarpay_ipn,        name='amarpay-ipn'),
    path('upay/',       upay_callback,      name='upay-callback'),
    path('shurjopay/',  shurjopay_callback, name='shurjopay-callback'),
    path('stripe/',     stripe_webhook,     name='stripe-webhook'),
    path('paypal/',     paypal_webhook,     name='paypal-webhook'),
]
