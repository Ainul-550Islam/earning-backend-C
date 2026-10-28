# api/rate_limit/adapters/remaining_apps.py
"""
Remaining Apps ↔ Rate Limit Adapters
========================================
Covers all remaining 38 api/ apps in one file.

Each adapter class is small and focused.
Import pattern:
    from api.rate_limit.adapters.remaining_apps import (
        AdminPanelRateLimitAdapter,
        AnalyticsRateLimitAdapter,
        SubscriptionRateLimitAdapter,
        ...
    )
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.remaining_apps')

# ─────────────────────────────────────────────────────────────────
# Helper: quick check builder
# ─────────────────────────────────────────────────────────────────

def _check(action: str, request=None, user=None, ip: str = '', ctx: dict = None) -> RateLimitResult:
    user = user or (getattr(request, 'user', None) if request else None)
    ip = ip or (RateLimitIntegrationService._extract_ip(request) if request else '')
    return RateLimitIntegrationService.check(
        action, request=request, user=user, ip_address=ip, extra_context=ctx or {},
    )


# ─────────────────────────────────────────────────────────────────
# 1. Admin Panel
# ─────────────────────────────────────────────────────────────────

class AdminPanelRateLimitAdapter:
    """
    api/admin_panel/ ↔ rate_limit

    Where to call:
        api/admin_panel/views.py → all admin actions (login, export, bulk ops)
    """

    @staticmethod
    def check_admin_login(request) -> RateLimitResult:
        """Block brute-force admin logins."""
        return _check('security_login_attempt', request=request,
                      ip=RateLimitIntegrationService._extract_ip(request))

    @staticmethod
    def check_bulk_action(request, action_name: str = '') -> RateLimitResult:
        """Limit bulk operations (export, mass update, etc.)."""
        return _check('admin_bulk_action', request=request,
                      user=getattr(request, 'user', None),
                      ctx={'action': action_name})

    @staticmethod
    def check_export(request) -> RateLimitResult:
        """Limit data exports from admin panel."""
        return _check('tenant_export', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_user_management(request) -> RateLimitResult:
        """Limit user create/edit/delete actions."""
        return _check('admin_user_management', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 2. Advertiser Portal
# ─────────────────────────────────────────────────────────────────

class AdvertiserPortalRateLimitAdapter:
    """
    api/advertiser_portal/ ↔ rate_limit

    Where to call:
        api/advertiser_portal/views.py → campaign create, bid submit, report export
    """

    @staticmethod
    def check_campaign_create(request) -> RateLimitResult:
        return _check('advertiser_campaign_create', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_bid_submit(request, campaign_id=None) -> RateLimitResult:
        return _check('advertiser_bid_submit', request=request, user=getattr(request, 'user', None),
                      ctx={'campaign_id': str(campaign_id) if campaign_id else ''})

    @staticmethod
    def check_report_export(request) -> RateLimitResult:
        return _check('tenant_export', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_creative_upload(request) -> RateLimitResult:
        return _check('advertiser_creative_upload', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 3. AI Engine
# ─────────────────────────────────────────────────────────────────

class AIEngineRateLimitAdapter:
    """
    api/ai_engine/ ↔ rate_limit

    Where to call:
        api/ai_engine/tasks.py → AI inference tasks (expensive!)
        api/ai_engine/ → prediction endpoint
    """

    @staticmethod
    def check_inference(request=None, user=None, model_name: str = '') -> RateLimitResult:
        """Limit AI model inference calls (expensive GPU ops)."""
        return _check('ai_engine_inference', request=request, user=user,
                      ctx={'model': model_name})

    @staticmethod
    def check_batch_inference(user=None, batch_size: int = 0) -> RateLimitResult:
        """Limit batch AI inference from Celery tasks."""
        return _check('ai_engine_batch', user=user,
                      ctx={'batch_size': batch_size})


# ─────────────────────────────────────────────────────────────────
# 4. Alerts
# ─────────────────────────────────────────────────────────────────

class AlertsRateLimitAdapter:
    """
    api/alerts/ ↔ rate_limit

    Where to call:
        api/alerts/views.py → alert create, acknowledge, snooze
    """

    @staticmethod
    def check_alert_create(request) -> RateLimitResult:
        return _check('alerts_create', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_alert_acknowledge(request) -> RateLimitResult:
        return _check('alerts_acknowledge', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_notification_send(user=None, channel: str = '') -> RateLimitResult:
        """Limit outbound alert notifications."""
        return _check('message_send', user=user, ctx={'channel': channel, 'source': 'alerts'})


# ─────────────────────────────────────────────────────────────────
# 5. Analytics
# ─────────────────────────────────────────────────────────────────

class AnalyticsRateLimitAdapter:
    """
    api/analytics/ ↔ rate_limit

    Where to call:
        api/analytics/views.py → dashboard, report, export endpoints
    """

    @staticmethod
    def check_report_generate(request) -> RateLimitResult:
        """Limit expensive analytics reports."""
        return _check('analytics_report', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_export(request) -> RateLimitResult:
        return _check('tenant_export', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_dashboard_load(request) -> RateLimitResult:
        return _check('analytics_dashboard', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 6. Audit Logs
# ─────────────────────────────────────────────────────────────────

class AuditLogsRateLimitAdapter:
    """
    api/audit_logs/ ↔ rate_limit

    Where to call:
        api/audit_logs/services/LogService.py → log create
        api/audit_logs/services/LogExporter.py → export
    """

    @staticmethod
    def check_log_query(request) -> RateLimitResult:
        """Limit audit log queries (large DB reads)."""
        return _check('audit_logs_query', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_export(request) -> RateLimitResult:
        return _check('tenant_export', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 7. Auto Mod
# ─────────────────────────────────────────────────────────────────

class AutoModRateLimitAdapter:
    """
    api/auto_mod/ ↔ rate_limit

    Where to call:
        api/auto_mod/views.py → content submit, moderation action
    """

    @staticmethod
    def check_content_submit(request) -> RateLimitResult:
        return _check('auto_mod_submit', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_appeal(request) -> RateLimitResult:
        return _check('auto_mod_appeal', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 8. Backup
# ─────────────────────────────────────────────────────────────────

class BackupRateLimitAdapter:
    """
    api/backup/ ↔ rate_limit

    Where to call:
        api/backup/tasks.py → manual backup trigger
        api/backup/views.py → backup initiate endpoint
    """

    @staticmethod
    def check_backup_trigger(request=None, user=None) -> RateLimitResult:
        """Limit manual backup requests (very expensive)."""
        return _check('backup_trigger', request=request, user=user)

    @staticmethod
    def check_restore(request=None, user=None) -> RateLimitResult:
        return _check('backup_restore', request=request, user=user)


# ─────────────────────────────────────────────────────────────────
# 9. Behavior Analytics
# ─────────────────────────────────────────────────────────────────

class BehaviorAnalyticsRateLimitAdapter:
    """
    api/behavior_analytics/ ↔ rate_limit

    Where to call:
        api/behavior_analytics/viewsets.py → event track, report
    """

    @staticmethod
    def check_event_track(request) -> RateLimitResult:
        """Limit behavioral event tracking submissions."""
        ip = RateLimitIntegrationService._extract_ip(request)
        return _check('behavior_track', request=request, ip=ip)

    @staticmethod
    def check_report(request) -> RateLimitResult:
        return _check('analytics_report', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def sync_anomaly_signal(user=None, ip_address: str = '', anomaly_score: int = 0) -> dict:
        """Send anomaly signal to rate_limit fraud bridge."""
        return RateLimitIntegrationService.sync_fraud_signal(
            user=user, ip_address=ip_address,
            risk_score=anomaly_score, fraud_type='behavior_anomaly',
        )


# ─────────────────────────────────────────────────────────────────
# 10. Cache
# ─────────────────────────────────────────────────────────────────

class CacheRateLimitAdapter:
    """
    api/cache/ ↔ rate_limit

    Where to call:
        api/cache/views.py → cache flush, invalidate endpoints
    """

    @staticmethod
    def check_cache_flush(request) -> RateLimitResult:
        """Limit dangerous cache flush operations."""
        return _check('cache_flush', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_cache_query(request) -> RateLimitResult:
        return _check('api_global', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 11. CMS
# ─────────────────────────────────────────────────────────────────

class CMSRateLimitAdapter:
    """
    api/cms/ ↔ rate_limit

    Where to call:
        api/cms/views.py → content create, update, publish
    """

    @staticmethod
    def check_content_create(request) -> RateLimitResult:
        return _check('cms_content_create', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_content_publish(request) -> RateLimitResult:
        return _check('cms_publish', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_media_upload(request) -> RateLimitResult:
        return _check('cms_media_upload', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 12. Disaster Recovery / DR Integration
# ─────────────────────────────────────────────────────────────────

class DisasterRecoveryRateLimitAdapter:
    """
    api/disaster_recovery/ + api/dr_integration/ ↔ rate_limit

    Where to call:
        api/disaster_recovery/tasks.py → failover trigger
        api/dr_integration/views.py → sync endpoints
    """

    @staticmethod
    def check_failover_trigger(request=None, user=None) -> RateLimitResult:
        """Strictly limit failover triggers."""
        return _check('dr_failover', request=request, user=user)

    @staticmethod
    def check_sync(request=None, user=None) -> RateLimitResult:
        return _check('dr_sync', request=request, user=user)


# ─────────────────────────────────────────────────────────────────
# 13. Engagement
# ─────────────────────────────────────────────────────────────────

class EngagementRateLimitAdapter:
    """
    api/engagement/ ↔ rate_limit

    Where to call:
        api/engagement/views.py → reaction, like, share, comment
    """

    @staticmethod
    def check_reaction(request) -> RateLimitResult:
        return _check('message_reaction', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_share(request) -> RateLimitResult:
        return _check('engagement_share', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_comment(request) -> RateLimitResult:
        return _check('message_send', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 14. Gamification
# ─────────────────────────────────────────────────────────────────

class GamificationRateLimitAdapter:
    """
    api/gamification/ ↔ rate_limit

    Where to call:
        api/gamification/viewsets.py → achievement claim, leaderboard submit
    """

    @staticmethod
    def check_achievement_claim(request, achievement_id=None) -> RateLimitResult:
        return _check('gamification_achievement', request=request,
                      user=getattr(request, 'user', None),
                      ctx={'achievement_id': str(achievement_id) if achievement_id else ''})

    @staticmethod
    def check_score_submit(request) -> RateLimitResult:
        return _check('gamification_score', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 15. Inventory
# ─────────────────────────────────────────────────────────────────

class InventoryRateLimitAdapter:
    """
    api/inventory/ ↔ rate_limit

    Where to call:
        api/inventory/viewsets.py → item create, stock update, reservation
    """

    @staticmethod
    def check_item_create(request) -> RateLimitResult:
        return _check('inventory_create', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_stock_update(request) -> RateLimitResult:
        return _check('inventory_update', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_reservation(request) -> RateLimitResult:
        return _check('inventory_reserve', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 16. Localization
# ─────────────────────────────────────────────────────────────────

class LocalizationRateLimitAdapter:
    """
    api/localization/ ↔ rate_limit

    Where to call:
        api/localization/views.py → translation submit, language switch
    """

    @staticmethod
    def check_translation_submit(request) -> RateLimitResult:
        return _check('localization_submit', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 17. Marketplace
# ─────────────────────────────────────────────────────────────────

class MarketplaceRateLimitAdapter:
    """
    api/marketplace/ ↔ rate_limit

    Where to call:
        api/marketplace/ → product list, purchase, review submit
    """

    @staticmethod
    def check_product_purchase(request) -> RateLimitResult:
        return _check('marketplace_purchase', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_review_submit(request) -> RateLimitResult:
        return _check('marketplace_review', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_listing_create(request) -> RateLimitResult:
        return _check('marketplace_listing', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 18. Monetization Tools
# ─────────────────────────────────────────────────────────────────

class MonetizationToolsRateLimitAdapter:
    """
    api/monetization_tools/ ↔ rate_limit

    Where to call:
        api/monetization_tools/views.py → pricing rule, discount create
    """

    @staticmethod
    def check_pricing_rule(request) -> RateLimitResult:
        return _check('monetization_pricing', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_discount_apply(request) -> RateLimitResult:
        return _check('monetization_discount', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 19. Notifications
# ─────────────────────────────────────────────────────────────────

class NotificationsRateLimitAdapter:
    """
    api/notifications/ ↔ rate_limit

    Where to call:
        api/notifications/views.py → send, bulk send, subscribe
        api/notifications/tasks.py → notification celery tasks
    """

    @staticmethod
    def check_send(request=None, user=None, channel: str = '') -> RateLimitResult:
        """Limit notification sends (email/push/sms)."""
        return _check('message_send', request=request, user=user,
                      ctx={'channel': channel, 'source': 'notifications'})

    @staticmethod
    def check_bulk_send(user=None, count: int = 0) -> RateLimitResult:
        """Limit bulk notification sends."""
        return _check('notifications_bulk', user=user, ctx={'count': count})

    @staticmethod
    def check_subscribe(request) -> RateLimitResult:
        return _check('notifications_subscribe', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 20. Offer Inventory
# ─────────────────────────────────────────────────────────────────

class OfferInventoryRateLimitAdapter:
    """
    api/offer_inventory/ ↔ rate_limit

    Where to call:
        api/offer_inventory/viewsets.py → offer list, reserve, claim
    """

    @staticmethod
    def check_offer_reserve(request) -> RateLimitResult:
        return _check('offer_click', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_offer_claim(request, offer_id=None) -> RateLimitResult:
        return _check('offer_complete', request=request, user=getattr(request, 'user', None),
                      ctx={'offer_id': str(offer_id) if offer_id else ''})


# ─────────────────────────────────────────────────────────────────
# 21. Offer Routing
# ─────────────────────────────────────────────────────────────────

class OfferRoutingRateLimitAdapter:
    """
    api/offer_routing/ ↔ rate_limit

    Where to call:
        api/offer_routing/viewsets.py → route request, click track
    """

    @staticmethod
    def check_route_request(request) -> RateLimitResult:
        ip = RateLimitIntegrationService._extract_ip(request)
        return _check('postback_click', request=request, ip=ip)

    @staticmethod
    def check_click_track(request) -> RateLimitResult:
        ip = RateLimitIntegrationService._extract_ip(request)
        return _check('ad_click', request=request, ip=ip)


# ─────────────────────────────────────────────────────────────────
# 22. Payment Gateways
# ─────────────────────────────────────────────────────────────────

class PaymentGatewaysRateLimitAdapter:
    """
    api/payment_gateways/ ↔ rate_limit

    Where to call:
        api/payment_gateways/views.py → payment initiate, verify, webhook
    """

    @staticmethod
    def check_payment_initiate(request, gateway: str = '') -> RateLimitResult:
        """Critical: limit payment initiation per user."""
        return _check('wallet_payment_request', request=request,
                      user=getattr(request, 'user', None),
                      ctx={'gateway': gateway})

    @staticmethod
    def check_webhook(request, gateway: str = '') -> RateLimitResult:
        ip = RateLimitIntegrationService._extract_ip(request)
        return _check('webhook_inbound', request=request, ip=ip,
                      ctx={'gateway': gateway})

    @staticmethod
    def check_refund(request) -> RateLimitResult:
        return _check('wallet_withdrawal', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 23. Payout Queue
# ─────────────────────────────────────────────────────────────────

class PayoutQueueRateLimitAdapter:
    """
    api/payout_queue/ ↔ rate_limit

    Where to call:
        api/payout_queue/viewsets.py → payout request, retry
        api/payout_queue/services.py → process payout
    """

    @staticmethod
    def check_payout_request(request=None, user=None, amount=None) -> RateLimitResult:
        """Most critical: limit payout requests."""
        return _check('wallet_withdrawal', request=request, user=user,
                      ctx={'source': 'payout_queue', 'amount': str(amount) if amount else ''})

    @staticmethod
    def check_payout_retry(user=None, payout_id=None) -> RateLimitResult:
        return _check('webhook_retry', user=user,
                      ctx={'payout_id': str(payout_id) if payout_id else ''})


# ─────────────────────────────────────────────────────────────────
# 24. Promotions
# ─────────────────────────────────────────────────────────────────

class PromotionsRateLimitAdapter:
    """
    api/promotions/ ↔ rate_limit

    Where to call:
        api/promotions/viewsets.py → promo code apply, campaign join
    """

    @staticmethod
    def check_promo_apply(request, promo_code: str = '') -> RateLimitResult:
        return _check('promotions_apply', request=request,
                      user=getattr(request, 'user', None),
                      ctx={'promo_code': promo_code})

    @staticmethod
    def check_campaign_join(request) -> RateLimitResult:
        return _check('djoyalty_campaign', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 25. Proxy Intelligence
# ─────────────────────────────────────────────────────────────────

class ProxyIntelligenceRateLimitAdapter:
    """
    api/proxy_intelligence/ ↔ rate_limit

    Where to call:
        api/proxy_intelligence/views.py → IP check endpoint
    Bidirectional: sends VPN/proxy detections to rate_limit.
    """

    @staticmethod
    def check_ip_lookup(request) -> RateLimitResult:
        ip = RateLimitIntegrationService._extract_ip(request)
        return _check('fraud_risk_check', request=request, ip=ip)

    @staticmethod
    def report_proxy_detected(ip_address: str, user=None, confidence: int = 0) -> dict:
        """Send proxy/VPN detection to rate_limit for IP blocking."""
        return RateLimitIntegrationService.sync_fraud_signal(
            user=user, ip_address=ip_address,
            risk_score=confidence, fraud_type='proxy_vpn_detected',
            auto_block=(confidence >= 95),
        )


# ─────────────────────────────────────────────────────────────────
# 26. Publisher Tools
# ─────────────────────────────────────────────────────────────────

class PublisherToolsRateLimitAdapter:
    """
    api/publisher_tools/ ↔ rate_limit

    Where to call:
        api/publisher_tools/viewsets.py → report request, link generate
    """

    @staticmethod
    def check_report(request) -> RateLimitResult:
        return _check('analytics_report', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_link_generate(request) -> RateLimitResult:
        return _check('referral_link_generate', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 27. Smartlink
# ─────────────────────────────────────────────────────────────────

class SmartlinkRateLimitAdapter:
    """
    api/smartlink/ ↔ rate_limit

    Where to call:
        api/smartlink/tasks.py → smartlink click, redirect
    """

    @staticmethod
    def check_click(request=None, ip_address: str = '', network: str = '') -> RateLimitResult:
        ip = ip_address or (RateLimitIntegrationService._extract_ip(request) if request else '')
        return _check('ad_click', request=request, ip=ip, ctx={'network': network, 'source': 'smartlink'})

    @staticmethod
    def check_create(request) -> RateLimitResult:
        return _check('referral_link_generate', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 28. Subscription
# ─────────────────────────────────────────────────────────────────

class SubscriptionRateLimitAdapter:
    """
    api/subscription/ ↔ rate_limit

    Where to call:
        api/subscription/viewsets.py → subscribe, cancel, upgrade
    """

    @staticmethod
    def check_subscribe(request) -> RateLimitResult:
        return _check('wallet_payment_request', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_cancel(request) -> RateLimitResult:
        return _check('subscription_cancel', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def on_subscribed(user, plan: str = '') -> bool:
        """When user subscribes, upgrade rate limit tier."""
        return RateLimitIntegrationService.set_premium(user, is_premium=True)

    @staticmethod
    def on_cancelled(user) -> bool:
        """When subscription cancelled, downgrade rate limit tier."""
        return RateLimitIntegrationService.set_premium(user, is_premium=False)


# ─────────────────────────────────────────────────────────────────
# 29. Support
# ─────────────────────────────────────────────────────────────────

class SupportRateLimitAdapter:
    """
    api/support/ ↔ rate_limit

    Where to call:
        api/support/views.py → ticket create, message send
    """

    @staticmethod
    def check_ticket_create(request) -> RateLimitResult:
        return _check('support_ticket', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_message_send(request) -> RateLimitResult:
        return _check('message_send', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def reset_limits_for_user(user) -> bool:
        """Support agent resets rate limits for a user."""
        return RateLimitIntegrationService.reset_user_limits(user)


# ─────────────────────────────────────────────────────────────────
# 30. Tasks (Celery task management)
# ─────────────────────────────────────────────────────────────────

class TasksRateLimitAdapter:
    """
    api/tasks/ ↔ rate_limit

    Where to call:
        api/tasks/ → task trigger endpoint
    """

    @staticmethod
    def check_task_trigger(request=None, user=None, task_name: str = '') -> RateLimitResult:
        return _check('task_submit', request=request, user=user, ctx={'task_name': task_name})


# ─────────────────────────────────────────────────────────────────
# 31. Version Control
# ─────────────────────────────────────────────────────────────────

class VersionControlRateLimitAdapter:
    """
    api/version_control/ ↔ rate_limit

    Where to call:
        api/version_control/viewsets.py → deploy, rollback
    """

    @staticmethod
    def check_deploy(request) -> RateLimitResult:
        return _check('version_control_deploy', request=request, user=getattr(request, 'user', None))

    @staticmethod
    def check_rollback(request) -> RateLimitResult:
        return _check('version_control_rollback', request=request, user=getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────
# 32. Smartlink / Localization / CMS generic check
# ─────────────────────────────────────────────────────────────────

class GenericApiRateLimitAdapter:
    """
    Generic adapter for apps that only need global API rate limiting.
    Covers: core, dashboard_assets, management, engagement (simple).

    Where to call:
        Any view that just needs global API protection.
    """

    @staticmethod
    def check_api(request) -> RateLimitResult:
        ip = RateLimitIntegrationService._extract_ip(request)
        user = getattr(request, 'user', None)
        return _check('api_global', request=request,
                      user=user if user and getattr(user, 'is_authenticated', False) else None,
                      ip=ip)


# ─────────────────────────────────────────────────────────────────
# ACTION_CONFIG_MAP extension for all new actions
# ─────────────────────────────────────────────────────────────────

NEW_ACTION_CONFIGS = {
    # Admin Panel
    'admin_bulk_action':            'admin_bulk_action',
    'admin_user_management':        'admin_user_management',

    # Advertiser Portal
    'advertiser_campaign_create':   'advertiser_campaign_create',
    'advertiser_bid_submit':        'advertiser_bid_submit',
    'advertiser_creative_upload':   'advertiser_creative_upload',

    # AI Engine
    'ai_engine_inference':          'ai_engine_inference',
    'ai_engine_batch':              'ai_engine_batch',

    # Alerts
    'alerts_create':                'alerts_create',
    'alerts_acknowledge':           'alerts_acknowledge',

    # Analytics
    'analytics_report':             'analytics_report',
    'analytics_dashboard':          'analytics_dashboard',

    # Audit
    'audit_logs_query':             'audit_logs_query',

    # Auto Mod
    'auto_mod_submit':              'auto_mod_submit',
    'auto_mod_appeal':              'auto_mod_appeal',

    # Backup
    'backup_trigger':               'backup_trigger',
    'backup_restore':               'backup_restore',

    # Behavior
    'behavior_track':               'behavior_track',

    # Cache
    'cache_flush':                  'cache_flush',

    # CMS
    'cms_content_create':           'cms_content_create',
    'cms_publish':                  'cms_publish',
    'cms_media_upload':             'cms_media_upload',

    # DR
    'dr_failover':                  'dr_failover',
    'dr_sync':                      'dr_sync',

    # Engagement
    'engagement_share':             'engagement_share',

    # Gamification
    'gamification_achievement':     'gamification_achievement',
    'gamification_score':           'gamification_score',

    # Inventory
    'inventory_create':             'inventory_create',
    'inventory_update':             'inventory_update',
    'inventory_reserve':            'inventory_reserve',

    # Localization
    'localization_submit':          'localization_submit',

    # Marketplace
    'marketplace_purchase':         'marketplace_purchase',
    'marketplace_review':           'marketplace_review',
    'marketplace_listing':          'marketplace_listing',

    # Monetization
    'monetization_pricing':         'monetization_pricing',
    'monetization_discount':        'monetization_discount',

    # Notifications
    'notifications_bulk':           'notifications_bulk',
    'notifications_subscribe':      'notifications_subscribe',

    # Promotions
    'promotions_apply':             'promotions_apply',

    # Subscription
    'subscription_cancel':          'subscription_cancel',

    # Support
    'support_ticket':               'support_ticket',

    # Tasks
    'task_submit':                  'offerwall_task_submit',  # reuse

    # Version Control
    'version_control_deploy':       'version_control_deploy',
    'version_control_rollback':     'version_control_rollback',

    # Djoyalty
    'djoyalty_earn_points':         'djoyalty_earn_points',
    'djoyalty_redemption':          'djoyalty_redemption',
    'djoyalty_voucher_use':         'djoyalty_voucher_use',
    'djoyalty_gift_card':           'djoyalty_gift_card',
    'djoyalty_points_transfer':     'djoyalty_points_transfer',
    'djoyalty_wallet_bridge':       'djoyalty_wallet_bridge',
    'djoyalty_campaign':            'djoyalty_campaign',
}


def register_new_actions():
    """
    Register all new action → config mappings into integration_service.
    Call this once from apps.py or startup.

    from api.rate_limit.adapters.remaining_apps import register_new_actions
    register_new_actions()
    """
    from api.rate_limit.integration_service import ACTION_CONFIG_MAP
    ACTION_CONFIG_MAP.update(NEW_ACTION_CONFIGS)
    logger.info(f'[RateLimitAdapters] Registered {len(NEW_ACTION_CONFIGS)} new action configs')


__all__ = [
    'AdminPanelRateLimitAdapter',
    'AdvertiserPortalRateLimitAdapter',
    'AIEngineRateLimitAdapter',
    'AlertsRateLimitAdapter',
    'AnalyticsRateLimitAdapter',
    'AuditLogsRateLimitAdapter',
    'AutoModRateLimitAdapter',
    'BackupRateLimitAdapter',
    'BehaviorAnalyticsRateLimitAdapter',
    'CacheRateLimitAdapter',
    'CMSRateLimitAdapter',
    'DisasterRecoveryRateLimitAdapter',
    'EngagementRateLimitAdapter',
    'GamificationRateLimitAdapter',
    'InventoryRateLimitAdapter',
    'LocalizationRateLimitAdapter',
    'MarketplaceRateLimitAdapter',
    'MonetizationToolsRateLimitAdapter',
    'NotificationsRateLimitAdapter',
    'OfferInventoryRateLimitAdapter',
    'OfferRoutingRateLimitAdapter',
    'PaymentGatewaysRateLimitAdapter',
    'PayoutQueueRateLimitAdapter',
    'PromotionsRateLimitAdapter',
    'ProxyIntelligenceRateLimitAdapter',
    'PublisherToolsRateLimitAdapter',
    'SmartlinkRateLimitAdapter',
    'SubscriptionRateLimitAdapter',
    'SupportRateLimitAdapter',
    'TasksRateLimitAdapter',
    'VersionControlRateLimitAdapter',
    'GenericApiRateLimitAdapter',
    'DjoyaltyRateLimitAdapter',
    'NEW_ACTION_CONFIGS',
    'register_new_actions',
]
