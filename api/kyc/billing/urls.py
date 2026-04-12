# kyc/billing/urls.py  ── WORLD #1
from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('plans/',                   views.plans_list,         name='kyc-plans'),
    # User
    path('subscription/',            views.my_subscription,    name='kyc-my-subscription'),
    path('usage/',                   views.my_usage,           name='kyc-my-usage'),
    path('invoices/',                views.my_invoices,        name='kyc-my-invoices'),
    path('api-keys/',                views.api_keys,           name='kyc-api-keys'),
    path('api-keys/<int:key_id>/revoke/', views.revoke_api_key, name='kyc-revoke-api-key'),
    # Admin
    path('admin/subscriptions/',     views.admin_subscriptions, name='kyc-admin-subs'),
    path('admin/revenue/',           views.admin_revenue,       name='kyc-admin-revenue'),
]
