"""
Billing Management URLs

This module contains URL patterns for billing management endpoints.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import (
    BillingProfileViewSet,
    PaymentMethodViewSet,
    InvoiceViewSet,
    TransactionViewSet,
    BillingAlertViewSet
)

# Create router for billing management
router = DefaultRouter()
router.register(r'billing-profiles', BillingProfileViewSet, basename='billing-profile')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'transactions', TransactionViewSet, basename='transaction')

app_name = 'billing_management'

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns for specific endpoints
billing_urls = [
    # Billing profile endpoints
    path('billing-profiles/', BillingProfileViewSet.as_view({'get': 'list', 'post': 'create'}), name='billing-profile-list-create'),
    path('billing-profiles/<uuid:pk>/', BillingProfileViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='billing-profile-detail-update-delete'),
    path('billing-profiles/<uuid:pk>/verify/', BillingProfileViewSet.as_view({'post': 'verify'}), name='billing-profile-verify'),
    path('billing-profiles/<uuid:pk>/calculate-tax/', BillingProfileViewSet.as_view({'post': 'calculate_tax'}), name='billing-profile-calculate-tax'),
    path('billing-profiles/<uuid:pk>/update-credit/', BillingProfileViewSet.as_view({'post': 'update_credit'}), name='billing-profile-update-credit'),
    path('billing-profiles/summary/', BillingProfileViewSet.as_view({'get': 'summary'}), name='billing-profile-summary'),
    
    # Payment method endpoints
    path('payment-methods/', PaymentMethodViewSet.as_view({'get': 'list', 'post': 'create'}), name='payment-method-list-create'),
    path('payment-methods/<uuid:pk>/', PaymentMethodViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='payment-method-detail-update-delete'),
    path('payment-methods/<uuid:pk>/verify/', PaymentMethodViewSet.as_view({'post': 'verify'}), name='payment-method-verify'),
    path('payment-methods/process-payment/', PaymentMethodViewSet.as_view({'post': 'process_payment'}), name='payment-method-process-payment'),
    path('payment-methods/by-profile/', PaymentMethodViewSet.as_view({'get': 'by_profile'}), name='payment-method-by-profile'),
    path('payment-methods/default/', PaymentMethodViewSet.as_view({'get': 'default'}), name='payment-method-default'),
    
    # Invoice endpoints
    path('invoices/', InvoiceViewSet.as_view({'get': 'list', 'post': 'create'}), name='invoice-list-create'),
    path('invoices/<uuid:pk>/', InvoiceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='invoice-detail-update-delete'),
    path('invoices/<uuid:pk>/send/', InvoiceViewSet.as_view({'post': 'send'}), name='invoice-send'),
    path('invoices/<uuid:pk>/mark-paid/', InvoiceViewSet.as_view({'post': 'mark_paid'}), name='invoice-mark-paid'),
    path('invoices/<uuid:pk>/summary/', InvoiceViewSet.as_view({'get': 'summary'}), name='invoice-summary'),
    
    # Transaction endpoints
    path('transactions/', TransactionViewSet.as_view({'get': 'list'}), name='transaction-list'),
    path('transactions/<uuid:pk>/', TransactionViewSet.as_view({'get': 'retrieve'}), name='transaction-detail'),
    path('transactions/<uuid:pk>/summary/', TransactionViewSet.as_view({'get': 'summary'}), name='transaction-summary'),
    
    # Billing alerts endpoints
    path('billing/alerts/', BillingAlertViewSet.as_view({'get': 'alerts'}), name='billing-alerts'),
]
