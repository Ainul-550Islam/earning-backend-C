"""
api/support/cpa_urls.py
World #1 CPA-specific URL configuration
Include in urls_v2.py:
    path('', include('support.cpa_urls')),
"""
from django.urls import path
from api.support.cpa.publisher_portal import publisher_portal_home, publisher_tier, publisher_health, create_publisher_ticket
from api.support.cpa.offer_dispute import submit_offer_dispute, my_disputes
from api.support.cpa.payment_dispute import submit_payment_dispute
from api.support.forum.community_forum import forum_list, ask_question, answer_question
from api.support.status.status_page import get_status, create_incident
from api.support.ux.browser_notifications import save_push_subscription, get_vapid_key

urlpatterns = [
    # Publisher Portal
    path('publisher/home/',         publisher_portal_home,     name='publisher-home'),
    path('publisher/tier/',         publisher_tier,            name='publisher-tier'),
    path('publisher/health/',       publisher_health,          name='publisher-health'),
    path('publisher/ticket/',       create_publisher_ticket,   name='publisher-ticket'),

    # Dispute System
    path('cpa/dispute/offer/',      submit_offer_dispute,      name='offer-dispute'),
    path('cpa/dispute/payment/',    submit_payment_dispute,    name='payment-dispute'),
    path('cpa/disputes/my/',        my_disputes,               name='my-disputes'),

    # Community Forum
    path('forum/',                  forum_list,                name='forum-list'),
    path('forum/ask/',              ask_question,              name='forum-ask'),
    path('forum/<int:question_id>/answer/', answer_question,   name='forum-answer'),

    # Status Page
    path('status/',                 get_status,                name='status'),
    path('status/incident/',        create_incident,           name='create-incident'),

    # Browser Notifications
    path('push/subscribe/',         save_push_subscription,    name='push-subscribe'),
    path('push/vapid-key/',         get_vapid_key,             name='push-vapid'),
]