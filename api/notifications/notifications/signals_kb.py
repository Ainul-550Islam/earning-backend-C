# earning_backend/api/notifications/signals_kb.py
"""Signals KB — Signal documentation and discovery registry."""

SIGNAL_REGISTRY = {
    "notification_sent":      {"module":"notifications.events","description":"Fired after notification sent.","sender":"Notification","provides":["instance","channel","result"],"receivers":["analytics.record_send"],"fired_by":["NotificationDispatcher"]},
    "notification_delivered": {"module":"notifications.events","description":"Fired when delivery confirmed.","sender":"Notification","provides":["instance","channel","provider"],"receivers":["analytics.record_delivery"],"fired_by":["delivery_tracking_tasks"]},
    "notification_read":      {"module":"notifications.events","description":"Fired when user reads notification.","sender":"Notification","provides":["instance","user"],"receivers":["consumers.send_count_update"],"fired_by":["views.mark_read"]},
    "notification_failed":    {"module":"notifications.events","description":"Fired when all retries fail.","sender":"Notification","provides":["instance","channel","error","attempts"],"receivers":["audit.log_failure"],"fired_by":["retry_tasks"]},
    "device_token_registered":{"module":"notifications.events","description":"Fired when push device registered.","sender":"DeviceToken","provides":["device","user","is_new"],"receivers":["receivers.on_device_token_post_save"],"fired_by":["post_save"]},
    "push_token_invalid":     {"module":"notifications.events","description":"Fired when token is invalid.","sender":"None","provides":["token","provider","device"],"receivers":["token_refresh_tasks"],"fired_by":["FCMProvider"]},
    "user_opted_out":         {"module":"notifications.events","description":"Fired when user opts out.","sender":"None","provides":["user","channel","reason"],"receivers":["receivers.on_opt_out_post_save"],"fired_by":["OptOutService"]},
    "fatigue_threshold_reached":{"module":"notifications.events","description":"Fired when fatigue limit reached.","sender":"NotificationFatigue","provides":["user","sent_today","daily_limit"],"receivers":["receivers.on_fatigue_post_save"],"fired_by":["post_save"]},
    "campaign_completed":     {"module":"notifications.events","description":"Fired when campaign finishes.","sender":"NotificationCampaign","provides":["campaign","sent_count","failed_count"],"receivers":["receivers.on_campaign_completed"],"fired_by":["campaign_tasks"]},
    "integration_event":      {"module":"notifications.events","description":"Cross-module integration event.","sender":"Any","provides":["event_type","data","user_id","source_module"],"receivers":["receivers.on_integration_event"],"fired_by":["EventBus"]},
}

def get_signal_info(name): return SIGNAL_REGISTRY.get(name,{})
def list_all_signals(): return list(SIGNAL_REGISTRY.keys())
def find_signals_by_receiver(receiver): return [n for n,i in SIGNAL_REGISTRY.items() if any(receiver in r for r in i.get("receivers",[]))]
def find_signals_by_sender(sender): return [n for n,i in SIGNAL_REGISTRY.items() if sender.lower() in i.get("sender","").lower()]
def audit_signal_coverage():
    issues = []
    for name, info in SIGNAL_REGISTRY.items():
        if not info.get("receivers"): issues.append(f"{name}: no receivers")
        if not info.get("fired_by"): issues.append(f"{name}: no fire source")
    return {"total_signals":len(SIGNAL_REGISTRY),"issues":issues,"coverage_ok":len(issues)==0}
