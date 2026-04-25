# earning_backend/api/notifications/extension_manager.py
"""
Extension Manager — Programmatic API for extending the notification system.

This is the SINGLE entry point for all extensions.
Instead of manually editing multiple files, use this manager.

Usage:
    from api.notifications.extension_manager import extension_manager

    # Register a new notification type
    extension_manager.register_notification_type(
        type_name='subscription_expired',
        label='Subscription Expired',
        default_channel='in_app',
        default_priority='high',
        send_push=True,
        send_email=True,
        icon='⏰',
        sound='reminder',
    )

    # Register a new provider
    extension_manager.register_provider(
        name='whatsapp_business',
        channel='whatsapp_business',
        provider_instance=my_provider,
    )

    # Register a new journey
    extension_manager.register_journey(journey_object)

    # Register a new workflow
    extension_manager.register_workflow(workflow_object)

    # Register a pre_send hook
    extension_manager.register_hook('pre_send', my_hook_fn, priority=5)

    # Register a new segment filter
    extension_manager.register_segment_filter('active_subscribers', my_filter_fn)

    # Register a webhook handler
    extension_manager.register_webhook_handler('stripe', 'customer.deleted', my_handler)

    # Enable/disable a feature
    extension_manager.set_feature_flag('MY_FEATURE', True)

    # Register an analytics aggregator
    extension_manager.register_analytics_aggregator('subscription_analytics', my_fn)
"""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationExtensionManager:
    """
    Central manager for all notification system extensions.

    Provides a clean API so developers never need to edit core files.
    All registrations are validated and logged for debugging.
    """

    def __init__(self):
        self._registered_types: Dict[str, dict] = {}
        self._registered_providers: Dict[str, Any] = {}
        self._registered_journeys: List = []
        self._registered_workflows: List = []
        self._registered_hooks: List[Dict] = []
        self._registered_segment_filters: Dict[str, Callable] = {}
        self._registered_webhook_handlers: Dict[str, Dict] = {}
        self._registered_analytics: Dict[str, Callable] = {}
        self._init_complete = False

    # ------------------------------------------------------------------
    # Notification Types
    # ------------------------------------------------------------------

    def register_notification_type(
        self,
        type_name: str,
        label: str = '',
        default_channel: str = 'in_app',
        default_priority: str = 'medium',
        send_push: bool = False,
        send_email: bool = False,
        send_sms: bool = False,
        icon: str = '🔔',
        sound: str = 'default',
        description: str = '',
    ) -> bool:
        """
        Register a new notification type dynamically.

        Args:
            type_name:        Unique identifier e.g. 'subscription_expired'
            label:            Human-readable label e.g. 'Subscription Expired'
            default_channel:  Default delivery channel
            default_priority: Default priority level
            send_push:        Also send push notification
            send_email:       Also send email
            send_sms:         Also send SMS
            icon:             Emoji icon for UI display
            sound:            Notification sound name

        Returns:
            True if registered successfully.
        """
        if type_name in self._registered_types:
            logger.warning(f'ExtensionManager: type "{type_name}" already registered.')
            return False

        config = {
            'type_name': type_name,
            'label': label or type_name.replace('_', ' ').title(),
            'channel': default_channel,
            'priority': default_priority,
            'send_push': send_push,
            'send_email': send_email,
            'send_sms': send_sms,
            'icon': icon,
            'sound': sound,
            'description': description,
        }
        self._registered_types[type_name] = config

        # Register in the type registry
        try:
            from api.notifications.registry import notification_type_registry
            notification_type_registry.register(
                type_name, default_channel, default_priority,
                send_push=send_push, send_email=send_email, send_sms=send_sms,
            )
        except Exception as exc:
            logger.warning(f'ExtensionManager.register_notification_type registry: {exc}')

        # Register icon
        try:
            from notifications import helpers
            if not hasattr(helpers, '_CUSTOM_ICONS'):
                helpers._CUSTOM_ICONS = {}
            helpers._CUSTOM_ICONS[type_name] = icon
        except Exception:
            pass

        # Register sound
        try:
            from notifications import logic
            if not hasattr(logic, '_CUSTOM_SOUNDS'):
                logic._CUSTOM_SOUNDS = {}
            logic._CUSTOM_SOUNDS[type_name] = sound
        except Exception:
            pass

        logger.info(f'ExtensionManager: notification type "{type_name}" registered')
        return True

    def get_notification_types(self) -> Dict[str, dict]:
        """Return all dynamically registered notification types."""
        return dict(self._registered_types)

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def register_provider(
        self,
        name: str,
        channel: str,
        provider_instance: Any,
        supports_bulk: bool = False,
    ) -> bool:
        """
        Register a new notification channel provider.

        Args:
            name:              Provider name e.g. 'whatsapp_business'
            channel:           Channel name e.g. 'whatsapp_business'
            provider_instance: Provider object with is_available() and send() methods
            supports_bulk:     Whether provider supports bulk sends

        Returns:
            True if registered successfully.
        """
        if not hasattr(provider_instance, 'is_available') or not hasattr(provider_instance, 'send'):
            logger.error(f'ExtensionManager: provider "{name}" must have is_available() and send() methods.')
            return False

        self._registered_providers[name] = {
            'name': name,
            'channel': channel,
            'instance': provider_instance,
            'supports_bulk': supports_bulk,
        }

        # Register in plugin system
        try:
            from api.notifications.plugins import plugin_registry, ProviderPlugin

            class DynamicPlugin(ProviderPlugin):
                _provider = provider_instance
                _channel = channel
                _name = name
                _supports_bulk = supports_bulk

                def is_available(self): return self._provider.is_available()
                def send(self, notification, **kwargs): return self._provider.send(notification, **kwargs)

            DynamicPlugin.name = name
            DynamicPlugin.channel = channel
            DynamicPlugin.supports_bulk = supports_bulk
            plugin_registry.register(DynamicPlugin(), overwrite=True)
        except Exception as exc:
            logger.warning(f'ExtensionManager.register_provider plugin: {exc}')

        # Register dispatch route
        try:
            from api.notifications.services.NotificationDispatcher import notification_dispatcher
            channel_name = channel

            def dynamic_dispatch(notification, _ch=channel_name, _prov=provider_instance):
                if not _prov.is_available():
                    return {'success': False, 'results': [], 'error': f'{_ch} not available'}
                result = _prov.send(notification)
                if result.get('success'):
                    try:
                        notification.mark_as_sent()
                    except Exception:
                        pass
                return {'success': result.get('success', False), 'results': [result]}

            notification_dispatcher._dispatch_map[channel_name] = dynamic_dispatch
        except Exception as exc:
            logger.debug(f'ExtensionManager.register_provider dispatcher: {exc}')

        logger.info(f'ExtensionManager: provider "{name}" registered for channel "{channel}"')
        return True

    def get_providers(self) -> Dict[str, dict]:
        """Return all dynamically registered providers."""
        return {k: {**v, 'instance': str(v['instance'])} for k, v in self._registered_providers.items()}

    # ------------------------------------------------------------------
    # Journeys
    # ------------------------------------------------------------------

    def register_journey(self, journey) -> bool:
        """
        Register a new multi-step notification journey.

        Args:
            journey: JourneyService.Journey instance

        Returns:
            True if registered.
        """
        try:
            from api.notifications.services.JourneyService import journey_service
            journey_service.register_journey(journey)
            self._registered_journeys.append(journey.journey_id)
            logger.info(f'ExtensionManager: journey "{journey.journey_id}" registered')
            return True
        except Exception as exc:
            logger.error(f'ExtensionManager.register_journey: {exc}')
            return False

    def register_journey_from_config(self, journey_id: str, name: str,
                                       steps: list, description: str = '') -> bool:
        """Convenience method to create and register a journey from config."""
        try:
            from api.notifications.services.JourneyService import Journey
            journey = Journey(journey_id=journey_id, name=name,
                              description=description, steps=steps)
            return self.register_journey(journey)
        except Exception as exc:
            logger.error(f'ExtensionManager.register_journey_from_config: {exc}')
            return False

    # ------------------------------------------------------------------
    # Workflows
    # ------------------------------------------------------------------

    def register_workflow(self, workflow) -> bool:
        """
        Register a new event-triggered workflow.

        Args:
            workflow: workflow.Workflow instance

        Returns:
            True if registered.
        """
        try:
            from api.notifications.workflow import workflow_engine
            workflow_engine.register(workflow)
            self._registered_workflows.append(workflow.workflow_id)
            logger.info(f'ExtensionManager: workflow "{workflow.workflow_id}" registered')
            return True
        except Exception as exc:
            logger.error(f'ExtensionManager.register_workflow: {exc}')
            return False

    def register_workflow_handler(self, workflow_id: str, name: str,
                                   handler: Callable, trigger_events: List[str] = None,
                                   cooldown_hours: int = 24, max_executions: int = 1) -> bool:
        """Register a workflow from a handler function."""
        try:
            from api.notifications.workflow import workflow_engine, Workflow
            wf = Workflow(
                workflow_id=workflow_id, name=name, handler=handler,
                trigger_events=trigger_events or [],
                cooldown_hours=cooldown_hours,
                max_executions_per_user=max_executions,
            )
            return self.register_workflow(wf)
        except Exception as exc:
            logger.error(f'ExtensionManager.register_workflow_handler: {exc}')
            return False

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    def register_hook(self, stage: str, hook_fn: Callable, priority: int = 5) -> bool:
        """
        Register a lifecycle hook for the notification send pipeline.

        Stages: pre_validate, post_validate, pre_send, post_send,
                post_deliver, pre_delete, on_failure, on_retry

        Args:
            stage:    Pipeline stage name
            hook_fn:  callable(notification, context: dict) → (notification, context) | None
            priority: Execution order (1=first, 10=last)

        Returns:
            True if registered.
        """
        try:
            from api.notifications.hooks import pipeline
            pipeline.register(stage, hook_fn, priority)
            self._registered_hooks.append({'stage': stage, 'fn': hook_fn.__name__, 'priority': priority})
            logger.info(f'ExtensionManager: hook "{hook_fn.__name__}" registered at stage "{stage}"')
            return True
        except Exception as exc:
            logger.error(f'ExtensionManager.register_hook: {exc}')
            return False

    # ------------------------------------------------------------------
    # Segment Filters
    # ------------------------------------------------------------------

    def register_segment_filter(self, filter_name: str, filter_fn: Callable) -> bool:
        """
        Register a custom segment filter function.

        filter_fn signature: filter_fn(conditions: dict) → list[user_id]

        Args:
            filter_name: Unique filter name e.g. 'active_subscribers'
            filter_fn:   Function that returns list of user IDs

        Returns:
            True if registered.
        """
        self._registered_segment_filters[filter_name] = filter_fn
        logger.info(f'ExtensionManager: segment filter "{filter_name}" registered')
        return True

    def apply_segment_filter(self, filter_name: str, conditions: dict) -> List[int]:
        """Execute a registered segment filter."""
        fn = self._registered_segment_filters.get(filter_name)
        if not fn:
            return []
        try:
            return fn(conditions)
        except Exception as exc:
            logger.error(f'ExtensionManager.apply_segment_filter {filter_name}: {exc}')
            return []

    def get_segment_filters(self) -> List[str]:
        """Return all registered segment filter names."""
        return list(self._registered_segment_filters.keys())

    # ------------------------------------------------------------------
    # Webhook Handlers
    # ------------------------------------------------------------------

    def register_webhook_handler(self, provider: str, event_type: str,
                                   handler_fn: Callable) -> bool:
        """
        Register a webhook event handler for a provider.

        handler_fn signature: handler_fn(payload: dict) → dict

        Args:
            provider:    Provider name e.g. 'stripe', 'paypal'
            event_type:  Webhook event type e.g. 'payment.success'
            handler_fn:  Function to handle the event

        Returns:
            True if registered.
        """
        key = f'{provider}:{event_type}'
        self._registered_webhook_handlers[key] = {
            'provider': provider,
            'event_type': event_type,
            'handler': handler_fn,
        }
        logger.info(f'ExtensionManager: webhook handler registered for {provider}/{event_type}')
        return True

    def handle_webhook(self, provider: str, event_type: str, payload: dict) -> Optional[dict]:
        """Dispatch a webhook to its registered handler."""
        key = f'{provider}:{event_type}'
        handler_config = self._registered_webhook_handlers.get(key)
        if not handler_config:
            return None
        try:
            return handler_config['handler'](payload)
        except Exception as exc:
            logger.error(f'ExtensionManager.handle_webhook {key}: {exc}')
            return {'error': str(exc)}

    # ------------------------------------------------------------------
    # Analytics Aggregators
    # ------------------------------------------------------------------

    def register_analytics_aggregator(self, name: str, aggregator_fn: Callable) -> bool:
        """
        Register a custom analytics aggregation function.

        aggregator_fn signature: aggregator_fn(days: int = 30) → dict

        Args:
            name:           Unique name e.g. 'subscription_analytics'
            aggregator_fn:  Function that returns analytics data dict

        Returns:
            True if registered.
        """
        self._registered_analytics[name] = aggregator_fn
        logger.info(f'ExtensionManager: analytics aggregator "{name}" registered')
        return True

    def run_analytics(self, name: str, days: int = 30) -> dict:
        """Run a registered analytics aggregator."""
        fn = self._registered_analytics.get(name)
        if not fn:
            return {'error': f'Analytics aggregator "{name}" not found'}
        try:
            return fn(days=days)
        except Exception as exc:
            logger.error(f'ExtensionManager.run_analytics {name}: {exc}')
            return {'error': str(exc)}

    def run_all_analytics(self, days: int = 30) -> dict:
        """Run all registered analytics aggregators."""
        results = {}
        for name, fn in self._registered_analytics.items():
            try:
                results[name] = fn(days=days)
            except Exception as exc:
                results[name] = {'error': str(exc)}
        return results

    def get_analytics_names(self) -> List[str]:
        """Return all registered analytics aggregator names."""
        return list(self._registered_analytics.keys())

    # ------------------------------------------------------------------
    # Feature Flags
    # ------------------------------------------------------------------

    def set_feature_flag(self, flag_name: str, enabled: bool,
                          ttl: int = 3600) -> bool:
        """
        Enable or disable a feature flag at runtime.

        Args:
            flag_name: Feature flag name
            enabled:   True to enable, False to disable
            ttl:       Cache TTL in seconds (default: 1 hour)

        Returns:
            True if set successfully.
        """
        try:
            from api.notifications.feature_flags import flags
            if enabled:
                flags.enable(flag_name, ttl)
            else:
                flags.disable(flag_name, ttl)
            return True
        except Exception as exc:
            logger.error(f'ExtensionManager.set_feature_flag: {exc}')
            return False

    def is_feature_enabled(self, flag_name: str, default: bool = True) -> bool:
        """Check if a feature flag is enabled."""
        try:
            from api.notifications.feature_flags import flags
            return flags.is_enabled(flag_name, default)
        except Exception:
            return default

    # ------------------------------------------------------------------
    # Status / Debug
    # ------------------------------------------------------------------

    def get_extension_summary(self) -> dict:
        """Return a summary of all registered extensions."""
        return {
            'notification_types': len(self._registered_types),
            'registered_types': list(self._registered_types.keys()),
            'providers': len(self._registered_providers),
            'registered_providers': list(self._registered_providers.keys()),
            'journeys': self._registered_journeys,
            'workflows': self._registered_workflows,
            'hooks': len(self._registered_hooks),
            'segment_filters': list(self._registered_segment_filters.keys()),
            'webhook_handlers': list(self._registered_webhook_handlers.keys()),
            'analytics_aggregators': list(self._registered_analytics.keys()),
        }

    def validate_all_extensions(self) -> dict:
        """Validate all registered extensions are functioning correctly."""
        results = {'valid': [], 'invalid': []}

        # Validate providers
        for name, config in self._registered_providers.items():
            try:
                available = config['instance'].is_available()
                results['valid' if available else 'invalid'].append(
                    f'provider:{name}:{"available" if available else "unavailable"}'
                )
            except Exception as exc:
                results['invalid'].append(f'provider:{name}:error:{exc}')

        # Validate hooks
        try:
            from api.notifications.hooks import pipeline
            for stage, hooks in pipeline.list_hooks().items():
                results['valid'].append(f'hooks:{stage}:{len(hooks)}_registered')
        except Exception as exc:
            results['invalid'].append(f'hooks:error:{exc}')

        return results


# Singleton — this is the main extension API
extension_manager = NotificationExtensionManager()
