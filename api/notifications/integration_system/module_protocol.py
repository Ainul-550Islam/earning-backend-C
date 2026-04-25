# api/notifications/integration_system/module_protocol.py
"""
Module Protocol — Standard interface every new module must implement
for automatic integration system discovery.

HOW TO ADD A NEW MODULE (e.g. `offers`):
=========================================
1. Create `api/offers/integ_config.py` with your ModuleConfig class.
2. That's it. Zero other changes needed.

The integration system will automatically:
  ✅ Register your module's adapter
  ✅ Wire your Django model signals to the EventBus
  ✅ Create notification subscriptions for your events
  ✅ Add cross-module permissions
  ✅ Register health check
  ✅ Map your data schemas for transformation

Example integ_config.py for a new `offers` module:

    from api.notifications.integration_system.module_protocol import ModuleConfig, SignalMap, EventMap

    class OffersIntegConfig(ModuleConfig):
        module_name = 'offers'
        version = '1.0.0'
        description = 'CPAlead Offer/Offerwall System'

        # Which models to watch and what events to publish
        signal_maps = [
            SignalMap(
                model_path='offers.OfferCompletion',
                field='status',
                value='completed',
                event_type='offer.completed',
                user_field='user_id',
                data_fields=['offer_id', 'reward_amount', 'offer_name'],
            ),
            SignalMap(
                model_path='offers.Postback',
                field='status',
                value='failed',
                event_type='affiliate.postback_failed',
                user_field=None,  # admin notification
                notify_admin=True,
            ),
        ]

        # What notification each event triggers
        event_maps = [
            EventMap(
                event_type='offer.completed',
                notification_type='offer_completed',
                title_template='Offer Completed! +৳{reward_amount} 🎯',
                message_template='You completed "{offer_name}". ৳{reward_amount} credited.',
                channel='in_app',
                priority='high',
            ),
        ]

        # Which modules this module can access
        allowed_targets = ['notifications', 'wallet', 'users']

        # Health check model path
        health_check_model = 'offers.Offer'
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes for module configuration
# ---------------------------------------------------------------------------

@dataclass
class SignalMap:
    """
    Maps a Django model post_save signal to an EventBus event.

    Fields:
        model_path:    'app_label.ModelName', e.g. 'offers.OfferCompletion'
        field:         Model field to watch, e.g. 'status'
        value:         Field value that triggers the event, e.g. 'completed'
        event_type:    EventBus event key, e.g. 'offer.completed'
        user_field:    Field on the model that holds user_id. None = no user.
        data_fields:   List of model fields to include in event data.
        notify_admin:  If True, notify admin users instead of the record's user.
        condition_fn:  Optional callable(instance) → bool for extra filtering.
        on_created:    If True, only trigger on creation (not update).
        on_update:     If True, trigger on field update. Default True.
    """
    model_path: str
    field: str
    value: Any
    event_type: str
    user_field: Optional[str] = 'user_id'
    data_fields: List[str] = field(default_factory=list)
    notify_admin: bool = False
    condition_fn: Optional[Callable] = None
    on_created: bool = False
    on_update: bool = True


@dataclass
class EventMap:
    """
    Maps an EventBus event to a notification template.

    Fields:
        event_type:            EventBus event key.
        notification_type:     Notification.notification_type value.
        title_template:        Title with {field} placeholders from event.data.
        message_template:      Message with {field} placeholders.
        channel:               Notification channel.
        priority:              Notification priority.
        channels_override:     Override channel per condition.
        send_push:             Also send push notification.
        send_email:            Also send email.
        send_sms:              Also send SMS (BD only by default).
        condition_fn:          Optional callable(event) → bool.
    """
    event_type: str
    notification_type: str
    title_template: str
    message_template: str
    channel: str = 'in_app'
    priority: str = 'medium'
    send_push: bool = False
    send_email: bool = False
    send_sms: bool = False
    condition_fn: Optional[Callable] = None


@dataclass
class WebhookMap:
    """
    Maps an inbound webhook provider/event to an EventBus event.

    Fields:
        provider:      Provider name, e.g. 'bkash', 'cpalead', 'sendgrid'
        event_types:   List of provider event type strings to handle.
        event_output:  EventBus event type to publish.
        parser_fn:     Optional callable(raw_payload) → Dict to extract clean data.
        verify_sig:    Whether to verify webhook signature.
    """
    provider: str
    event_types: List[str]
    event_output: str
    parser_fn: Optional[Callable] = None
    verify_sig: bool = True


@dataclass
class HealthCheck:
    """
    Health check configuration for a module.

    Fields:
        name:          Health check name displayed in dashboard.
        model_path:    'app.Model' — do a quick DB query to verify.
        url:           Optional HTTP URL to ping.
        check_fn:      Optional callable() → HealthStatus.
    """
    name: str
    model_path: Optional[str] = None
    url: Optional[str] = None
    check_fn: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Base ModuleConfig — every module inherits this
# ---------------------------------------------------------------------------

class ModuleConfig:
    """
    Base class for module integration configuration.

    Each module that wants to integrate with the notification system
    creates `integ_config.py` with a class inheriting from ModuleConfig.

    The AutoDiscovery engine scans INSTALLED_APPS, finds integ_config.py,
    reads this class, and wires everything automatically.
    """

    # Required
    module_name: str = ''             # e.g. 'offers', 'payments', 'leaderboard'
    version: str = '1.0.0'
    description: str = ''

    # Signal → Event mappings (auto-wired to Django post_save)
    signal_maps: List[SignalMap] = []

    # Event → Notification mappings (auto-subscribed on EventBus)
    event_maps: List[EventMap] = []

    # Webhook → Event mappings (auto-registered on WebhookManager)
    webhook_maps: List[WebhookMap] = []

    # Health check config
    health_checks: List[HealthCheck] = []

    # Cross-module permissions — what modules this module can access
    allowed_targets: List[str] = ['notifications', 'users']

    # Whether this module should be enabled by default
    enabled: bool = True

    # Adapter class to use (None = use DefaultModuleAdapter)
    adapter_class: Optional[Any] = None

    # Extra configuration passed to the adapter
    adapter_config: Dict = {}

    @classmethod
    def get_adapter_class(cls):
        """Return the adapter class to use. Override for custom adapters."""
        if cls.adapter_class:
            return cls.adapter_class
        from .auto_discovery import DefaultModuleAdapter
        return DefaultModuleAdapter

    @classmethod
    def on_registered(cls):
        """
        Hook called after the module is registered.
        Override to perform custom initialization.
        """
        pass

    @classmethod
    def validate(cls) -> List[str]:
        """
        Validate the configuration. Returns list of error strings.
        Override to add custom validation.
        """
        errors = []
        if not cls.module_name:
            errors.append('module_name is required')
        for sm in cls.signal_maps:
            if '.' not in sm.model_path:
                errors.append(f'signal_map.model_path must be "app.Model", got: {sm.model_path}')
        return errors
