# api/support/urls.py  —  COMPLETE CRUD URLs
from django.urls import path
from .views import (
    get_support_settings,
    tickets_list_create,
    ticket_detail,
    ticket_respond,
    ticket_stats,
    faqs_list_create,
    faq_detail,
)

urlpatterns = [
    # ── Settings ───────────────────────────────────────────────────
    # ✅ FIXED: was /support-settings/ — now /settings/ to match support.js
    path('settings/',               get_support_settings,   name='support-settings'),

    # ── Tickets ────────────────────────────────────────────────────
    # ✅ FIXED: stats/ MUST come before <id>/ to avoid conflict
    path('tickets/stats/',          ticket_stats,           name='ticket-stats'),
    # ✅ FIXED: list + create on same endpoint (was split into tickets/ and create-ticket/)
    path('tickets/',                tickets_list_create,    name='tickets-list-create'),
    path('tickets/<str:ticket_id>/',ticket_detail,          name='ticket-detail'),
    # ✅ FIXED: admin respond endpoint was missing
    path('tickets/<str:ticket_id>/respond/', ticket_respond, name='ticket-respond'),

    # ── FAQ ────────────────────────────────────────────────────────
    # ✅ FIXED: full CRUD — POST, PUT, PATCH, DELETE all added
    path('faqs/',                   faqs_list_create,       name='faqs-list-create'),
    path('faqs/<int:faq_id>/',      faq_detail,             name='faq-detail'),
]