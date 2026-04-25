# api/offers/integ_config.py
"""
EXAMPLE — Copy this file to your_app/integ_config.py and customize.

This is the integ_config.py for the 'offers' (CPAlead offerwall) module.
The AutoDiscovery engine reads this and wires everything automatically.
"""
from api.notifications.integration_system.module_protocol import (
    ModuleConfig, SignalMap, EventMap, WebhookMap, HealthCheck
)


class OffersIntegConfig(ModuleConfig):
    module_name = 'offers'
    version = '1.0.0'
    description = 'CPAlead Offer & Offerwall System'

    # ---------------------------------------------------------------
    # STEP 1: Which model changes trigger events?
    # ---------------------------------------------------------------
    signal_maps = [
        SignalMap(
            model_path='offers.OfferCompletion',
            field='status',
            value='completed',
            event_type='offer.completed',
            user_field='user_id',
            data_fields=['offer_id', 'offer_name', 'reward_amount', 'currency'],
        ),
        SignalMap(
            model_path='offers.OfferCompletion',
            field='status',
            value='rejected',
            event_type='offer.rejected',
            user_field='user_id',
            data_fields=['offer_id', 'offer_name', 'rejection_reason'],
        ),
        SignalMap(
            model_path='offers.Postback',
            field='status',
            value='failed',
            event_type='affiliate.postback_failed',
            notify_admin=True,
            data_fields=['offer_id', 'advertiser_id', 'error_message'],
        ),
        SignalMap(
            model_path='offers.Survey',
            field='is_active',
            value=True,
            event_type='survey.available',
            on_created=True,
            user_field=None,  # Broadcast to all
            data_fields=['survey_id', 'title', 'reward_amount'],
        ),
    ]

    # ---------------------------------------------------------------
    # STEP 2: What notification each event sends
    # ---------------------------------------------------------------
    event_maps = [
        EventMap(
            event_type='offer.completed',
            notification_type='offer_completed',
            title_template='Offer Completed! +৳{reward_amount} 🎯',
            message_template='You completed "{offer_name}". ৳{reward_amount} added to wallet.',
            channel='in_app',
            priority='high',
            send_push=True,
        ),
        EventMap(
            event_type='offer.rejected',
            notification_type='task_rejected',
            title_template='Offer Not Approved',
            message_template='"{offer_name}" was not approved. {rejection_reason}',
            channel='in_app',
            priority='medium',
        ),
    ]

    # ---------------------------------------------------------------
    # STEP 3: Inbound webhooks from affiliate networks
    # ---------------------------------------------------------------
    webhook_maps = [
        WebhookMap(
            provider='cpalead',
            event_types=['conversion', 'lead'],
            event_output='affiliate.conversion_recorded',
        ),
        WebhookMap(
            provider='cpabuild',
            event_types=['conversion'],
            event_output='affiliate.conversion_recorded',
        ),
    ]

    # ---------------------------------------------------------------
    # STEP 4: Health checks
    # ---------------------------------------------------------------
    health_checks = [
        HealthCheck(name='database', model_path='offers.Offer'),
    ]

    # ---------------------------------------------------------------
    # STEP 5: Cross-module permissions
    # ---------------------------------------------------------------
    allowed_targets = ['notifications', 'wallet', 'users', 'analytics']
