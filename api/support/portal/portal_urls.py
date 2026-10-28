"""
api/support/portal/portal_urls.py
FILE 38/70 — Customer Portal URL Configuration

Include in main urls.py:
    path('api/support/portal/', include('support.portal.portal_urls')),
"""
from django.urls import path
from api.support.portal.customer_portal_views import (
    portal_home,
    portal_tickets,
    portal_ticket_detail,
    portal_ticket_reply,
    portal_ticket_rate,
    portal_ticket_reopen,
    portal_ticket_close,
    portal_kb,
    portal_kb_search,
    portal_kb_article,
    portal_profile,
    portal_update_prefs,
    portal_stats,
)

urlpatterns = [
    # Home
    path('',                                     portal_home,           name='portal-home'),

    # My Tickets
    path('tickets/',                             portal_tickets,        name='portal-tickets'),
    path('tickets/<str:ticket_id>/',             portal_ticket_detail,  name='portal-ticket-detail'),
    path('tickets/<str:ticket_id>/reply/',       portal_ticket_reply,   name='portal-ticket-reply'),
    path('tickets/<str:ticket_id>/rate/',        portal_ticket_rate,    name='portal-ticket-rate'),
    path('tickets/<str:ticket_id>/reopen/',      portal_ticket_reopen,  name='portal-ticket-reopen'),
    path('tickets/<str:ticket_id>/close/',       portal_ticket_close,   name='portal-ticket-close'),

    # Knowledge Base
    path('kb/',                                  portal_kb,             name='portal-kb'),
    path('kb/search/',                           portal_kb_search,      name='portal-kb-search'),
    path('kb/<slug:slug>/',                      portal_kb_article,     name='portal-kb-article'),

    # Profile & Preferences
    path('profile/',                             portal_profile,        name='portal-profile'),
    path('profile/prefs/',                       portal_update_prefs,   name='portal-prefs'),

    # Stats
    path('stats/',                               portal_stats,          name='portal-stats'),
]