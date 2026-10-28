# api/support/urls.py  — WORLD #1 FINAL
# Original 7 URLs kept + 35+ new URLs
from django.urls import path
from .views import (
    # ── ORIGINAL (UNCHANGED) ─────────────────────────────────
    get_support_settings,
    tickets_list_create,
    ticket_detail,
    ticket_respond,
    ticket_stats,
    faqs_list_create,
    faq_detail,
    # ── NEW TICKET ACTIONS ────────────────────────────────────
    ticket_reply,
    ticket_resolve,
    ticket_close,
    ticket_rate,
    ticket_escalate,
    ticket_sla_status,
    # ── NEW FAQ ───────────────────────────────────────────────
    faq_helpful,
    # ── LIVE CHAT ─────────────────────────────────────────────
    chat_start,
    chat_detail,
    chat_send_message,
    chat_end,
    chat_rate,
    # ── KNOWLEDGE BASE ────────────────────────────────────────
    kb_categories,
    kb_articles,
    kb_article_detail,
    kb_article_helpful,
    # ── CPA DISPUTE ───────────────────────────────────────────
    submit_offer_dispute,
    my_offer_disputes,
    submit_withdrawal_dispute,
    # ── AGENT TOOLS ───────────────────────────────────────────
    canned_responses,
    announcements,
    # ── DASHBOARD & PORTAL ────────────────────────────────────
    agent_dashboard,
    user_portal,
)
from .attachment_upload_view import upload_ticket_attachment, delete_ticket_attachment

urlpatterns = [
    # ══ SETTINGS (original) ══════════════════════════════════
    path('settings/',                                   get_support_settings,       name='support-settings'),

    # ══ TICKETS (original) ═══════════════════════════════════
    path('tickets/stats/',                              ticket_stats,               name='ticket-stats'),
    path('tickets/',                                    tickets_list_create,        name='tickets-list-create'),
    path('tickets/<str:ticket_id>/',                    ticket_detail,              name='ticket-detail'),
    path('tickets/<str:ticket_id>/respond/',            ticket_respond,             name='ticket-respond'),

    # ══ TICKETS NEW ═══════════════════════════════════════════
    path('tickets/<str:ticket_id>/reply/',              ticket_reply,               name='ticket-reply'),
    path('tickets/<str:ticket_id>/resolve/',            ticket_resolve,             name='ticket-resolve'),
    path('tickets/<str:ticket_id>/close/',              ticket_close,               name='ticket-close'),
    path('tickets/<str:ticket_id>/rate/',               ticket_rate,                name='ticket-rate'),
    path('tickets/<str:ticket_id>/escalate/',           ticket_escalate,            name='ticket-escalate'),
    path('tickets/<str:ticket_id>/sla/',                ticket_sla_status,          name='ticket-sla'),
    path('tickets/<str:ticket_id>/attach/',             upload_ticket_attachment,   name='ticket-attach'),
    path('tickets/<str:ticket_id>/attach/<int:attachment_id>/', delete_ticket_attachment, name='ticket-attach-delete'),

    # ══ FAQ (original) ════════════════════════════════════════
    path('faqs/',                                       faqs_list_create,           name='faqs-list-create'),
    path('faqs/<int:faq_id>/',                          faq_detail,                 name='faq-detail'),
    path('faqs/<int:faq_id>/helpful/',                  faq_helpful,                name='faq-helpful'),

    # ══ LIVE CHAT ═════════════════════════════════════════════
    path('chat/start/',                                 chat_start,                 name='chat-start'),
    path('chat/<str:session_id>/',                      chat_detail,                name='chat-detail'),
    path('chat/<str:session_id>/message/',              chat_send_message,          name='chat-message'),
    path('chat/<str:session_id>/end/',                  chat_end,                   name='chat-end'),
    path('chat/<str:session_id>/rate/',                 chat_rate,                  name='chat-rate'),

    # ══ KNOWLEDGE BASE ════════════════════════════════════════
    path('kb/categories/',                              kb_categories,              name='kb-categories'),
    path('kb/articles/',                                kb_articles,                name='kb-articles'),
    path('kb/articles/<slug:slug>/',                    kb_article_detail,          name='kb-article-detail'),
    path('kb/articles/<slug:slug>/helpful/',            kb_article_helpful,         name='kb-article-helpful'),

    # ══ CPA DISPUTE ═══════════════════════════════════════════
    path('dispute/offer/',                              submit_offer_dispute,       name='offer-dispute'),
    path('dispute/offer/my/',                           my_offer_disputes,          name='my-offer-disputes'),
    path('dispute/withdrawal/',                         submit_withdrawal_dispute,  name='withdrawal-dispute'),

    # ══ AGENT TOOLS ═══════════════════════════════════════════
    path('canned/',                                     canned_responses,           name='canned-responses'),
    path('announcements/',                              announcements,              name='announcements'),

    # ══ DASHBOARD & PORTAL ════════════════════════════════════
    path('dashboard/',                                  agent_dashboard,            name='agent-dashboard'),
    path('portal/',                                     user_portal,                name='user-portal'),
]

# ── Integration webhook URLs ──────────────────────────────────
try:
    from .integrations.webhooks_integration import offer_completion_webhook, fraud_alert_webhook
    urlpatterns += [
        path('webhooks/offer-completed/', offer_completion_webhook, name='webhook-offer-completed'),
        path('webhooks/fraud-alert/',     fraud_alert_webhook,      name='webhook-fraud-alert'),
    ]
except ImportError:
    pass