# api/offerwall/integ_config.py
"""
Offerwall Module — Integration Configuration
"এক কাজের জন্য একটাই মালিক" — CPAlead Offer System
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck
)

class OfferwallIntegConfig(ModuleConfig):
    module_name = 'offerwall'
    version = '1.0.0'
    description = 'CPAlead Offerwall & CPA Offer System'

    signal_maps = [
        SignalMap(
            model_path='offerwall.OfferConversion',
            field='status',
            value='approved',
            event_type='offer.completed',
            user_field='user_id',
            data_fields=['offer_id', 'offer_name', 'reward_amount', 'currency', 'provider'],
        ),
        SignalMap(
            model_path='offerwall.Offer',
            field='is_active',
            value=True,
            event_type='offer.available',
            user_field=None,
            data_fields=['offer_id', 'title', 'reward_amount', 'category', 'expires_at'],
            on_created=True,
            on_update=False,
        ),
        SignalMap(
            model_path='offerwall.OfferConversion',
            field='status',
            value='rejected',
            event_type='offer.rejected',
            user_field='user_id',
            data_fields=['offer_id', 'offer_name', 'rejection_reason'],
        ),
    ]

    event_maps = [
        EventMap(
            event_type='offer.completed',
            notification_type='offer_completed',
            title_template='Offer Completed! +৳{reward_amount} 🎯',
            message_template='"{offer_name}" সফলভাবে complete। ৳{reward_amount} wallet এ যোগ হয়েছে।',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='offer.rejected',
            notification_type='task_rejected',
            title_template='Offer Not Approved',
            message_template='"{offer_name}" approve হয়নি। কারণ: {rejection_reason}',
            channel='in_app',
            priority='medium',
        ),
    ]

    webhook_maps = [
        WebhookMap(
            provider='cpalead',
            event_types=['conversion', 'lead', 'sale'],
            event_output='offer.completed',
        ),
        WebhookMap(
            provider='cpabuild',
            event_types=['conversion'],
            event_output='offer.completed',
        ),
        WebhookMap(
            provider='maxbounty',
            event_types=['conversion'],
            event_output='offer.completed',
        ),
        WebhookMap(
            provider='admitad',
            event_types=['action_approved'],
            event_output='offer.completed',
        ),
    ]

    health_checks = [HealthCheck(name='offerwall_db', model_path='offerwall.Offer')]
    allowed_targets = ['notifications', 'wallet', 'users', 'analytics', 'postback']
