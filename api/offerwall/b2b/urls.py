"""
api/offerwall/b2b/urls.py
"""
from django.urls import path
from .views import (
    B2BPlanListView,
    B2BRegisterView,
    B2BDashboardView,
    B2BUpgradeView,
    B2BUsageHistoryView,
    B2BInvoiceView,
    B2BOnboardingStepView,
    B2BAdminClientListView,
    B2BAdminClientActionView,
    B2BAdminGenerateInvoicesView,
)

app_name = 'b2b'

urlpatterns = [
    # ── Public ──────────────────────────────────────────────
    path('plans/',                         B2BPlanListView.as_view(),           name='plan-list'),

    # ── Publisher ────────────────────────────────────────────
    path('register/',                      B2BRegisterView.as_view(),           name='register'),
    path('dashboard/',                     B2BDashboardView.as_view(),          name='dashboard'),
    path('upgrade/',                       B2BUpgradeView.as_view(),            name='upgrade'),
    path('usage/',                         B2BUsageHistoryView.as_view(),       name='usage'),
    path('invoices/',                      B2BInvoiceView.as_view(),            name='invoice-list'),
    path('invoices/<uuid:invoice_id>/',    B2BInvoiceView.as_view(),            name='invoice-detail'),
    path('onboarding/complete-step/',      B2BOnboardingStepView.as_view(),     name='onboarding-step'),

    # ── Admin ────────────────────────────────────────────────
    path('admin/clients/',                 B2BAdminClientListView.as_view(),    name='admin-client-list'),
    path('admin/clients/<uuid:client_id>/<str:action>/',
                                           B2BAdminClientActionView.as_view(),  name='admin-client-action'),
    path('admin/generate-invoices/',       B2BAdminGenerateInvoicesView.as_view(), name='admin-gen-invoices'),
]
