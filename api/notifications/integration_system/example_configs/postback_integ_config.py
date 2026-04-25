# api/postback/integ_config.py
"""
Postback Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক" — Advertiser Postback Handler
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck
)

class PostbackIntegConfig(ModuleConfig):
    module_name = 'postback'
    version = '1.0.0'
    description = 'Advertiser Postback Processing & Conversion Tracking'

    signal_maps = [
        SignalMap(
            model_path='postback.Postback',
            field='status',
            value='failed',
            event_type='affiliate.postback_failed',
            user_field=None,
            data_fields=['postback_id', 'offer_id', 'advertiser_id', 'error_message', 'attempts'],
            notify_admin=True,
            on_created=False,
            on_update=True,
        ),
        SignalMap(
            model_path='postback.Postback',
            field='status',
            value='processed',
            event_type='affiliate.conversion_recorded',
            user_field='user_id',
            data_fields=['offer_id', 'offer_name', 'payout_amount', 'currency'],
            on_created=False,
            on_update=True,
        ),
    ]

    event_maps = [
        EventMap(
            event_type='affiliate.conversion_recorded',
            notification_type='conversion_received',
            title_template='Conversion Approved! +${payout_amount}',
            message_template='Offer "{offer_name}" conversion approved. ${payout_amount} earned.',
            channel='in_app',
            priority='high',
        ),
    ]

    webhook_maps = [
        WebhookMap(
            provider='cpalead',
            event_types=['postback', 'pixel_fire', 'conversion'],
            event_output='affiliate.conversion_recorded',
        ),
    ]

    health_checks = [HealthCheck(name='postback_db', model_path='postback.Postback')]
    allowed_targets = ['notifications', 'wallet', 'offerwall', 'analytics']
