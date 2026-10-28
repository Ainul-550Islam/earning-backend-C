"""
api/support/urls_v2.py
FILE 66/70 FIXED — Complete URL Configuration (no broken lambdas)
"""
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


# ── Webhook stub views ─────────────────────────────────
@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        try:
            from api.support.integrations.telegram_bot import telegram_bot
            update = json.loads(request.body)
            result = telegram_bot.handle_update(update)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return HttpResponse(status=405)


@csrf_exempt
def whatsapp_webhook(request):
    try:
        from api.support.integrations.whatsapp_integration import whatsapp_api
        return whatsapp_api.handle_webhook(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def facebook_webhook(request):
    try:
        from api.support.integrations.facebook_messenger import fb_messenger
        return fb_messenger.handle_webhook(request)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── Lazy view imports (avoid circular imports) ──────────
def _view(module, name):
    """Lazy import view helper"""
    def view_func(request, *args, **kwargs):
        import importlib
        mod = importlib.import_module(module)
        return getattr(mod, name)(request, *args, **kwargs)
    view_func.__name__ = name
    return view_func


urlpatterns = [
    # ── Existing support URLs ──────────────────────────
    path('', include('support.urls')),

    # ── Customer Portal ────────────────────────────────
    path('portal/', include('support.portal.portal_urls')),

    # ── Dashboard ──────────────────────────────────────
    path('dashboard/',           _view('support.dashboard.dashboard_views', 'dashboard_full')),
    path('dashboard/overview/',  _view('support.dashboard.dashboard_views', 'dashboard_overview')),
    path('dashboard/tickets/',   _view('support.dashboard.dashboard_views', 'dashboard_ticket_queue')),
    path('dashboard/agents/',    _view('support.dashboard.dashboard_views', 'dashboard_agent_status')),
    path('dashboard/sla/',       _view('support.dashboard.dashboard_views', 'dashboard_sla')),
    path('dashboard/chat/',      _view('support.dashboard.dashboard_views', 'dashboard_chat')),
    path('dashboard/charts/',    _view('support.dashboard.dashboard_views', 'dashboard_charts')),
    path('dashboard/alerts/',    _view('support.dashboard.dashboard_views', 'dashboard_alerts')),
    path('dashboard/refresh/',   _view('support.dashboard.dashboard_views', 'dashboard_refresh')),
    path('dashboard/team/',      _view('support.dashboard.dashboard_views', 'dashboard_team_performance')),
    path('dashboard/forecast/',  _view('support.dashboard.dashboard_views', 'dashboard_forecast')),
    path('dashboard/churn/',     _view('support.dashboard.dashboard_views', 'dashboard_churn_risk')),

    # ── Chat Widget ────────────────────────────────────
    path('widget/config/',       _view('support.livechat.chat_widget_api', 'widget_config')),
    path('widget/init/',         _view('support.livechat.chat_widget_api', 'widget_init')),
    path('widget/track/',        _view('support.livechat.chat_widget_api', 'widget_track')),
    path('widget/proactive/',    _view('support.livechat.chat_widget_api', 'widget_proactive_check')),
    path('widget/bot/message/',  _view('support.livechat.chat_widget_api', 'widget_bot_message')),
    path('widget/chat/start/',   _view('support.livechat.chat_widget_api', 'widget_start_chat')),
    path('widget/chat/message/', _view('support.livechat.chat_widget_api', 'widget_send_message')),
    path('widget/chat/end/',     _view('support.livechat.chat_widget_api', 'widget_end_chat')),
    path('widget/chat/rate/',    _view('support.livechat.chat_widget_api', 'widget_rate_chat')),
    path('widget/ticket/',       _view('support.livechat.chat_widget_api', 'widget_create_ticket')),
    path('widget/chat/<str:session_id>/messages/', _view('support.livechat.chat_widget_api', 'widget_get_messages')),

    # ── Notifications ──────────────────────────────────
    path('notifications/prefs/',               _view('support.notifications.notification_prefs', 'notification_prefs_view')),
    path('notifications/prefs/<str:channel>/', _view('support.notifications.notification_prefs', 'disable_channel_view')),

    # ── Webhooks (no auth required) ────────────────────
    path('webhooks/telegram/',  telegram_webhook),
    path('webhooks/whatsapp/',  whatsapp_webhook),
    path('webhooks/facebook/',  facebook_webhook),

    # ── Ticket History ─────────────────────────────────
    path('portal/tickets/<str:ticket_id>/timeline/', _view('support.portal.ticket_history_view', 'ticket_timeline')),
    path('portal/history/',                          _view('support.portal.ticket_history_view', 'user_full_history')),
]