# integration_system/integ_signals.py
"""
Integration Signals — Cross-module Django signals.
Bridges Django's built-in signal system to the EventBus.
"""
import logging
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save
from .event_bus import event_bus
from .integ_constants import Events

logger = logging.getLogger(__name__)

# Custom integration signals
integration_event = Signal()           # Generic integration event
integration_error = Signal()           # Integration error occurred
integration_recovered = Signal()       # Integration recovered after error
health_status_changed = Signal()       # Service health changed
sync_conflict_detected = Signal()      # Data sync conflict found
rate_limit_hit = Signal()              # Rate limit exceeded


def wire_django_signals():
    """
    Connect Django model signals to the EventBus.
    Called once in apps.py ready().
    Auto-discovers signals by trying common model paths.
    """

    # Map: (app.Model, field, value) → event to publish
    signal_map = {
        # Withdrawals
        ('withdrawals.Withdrawal', 'status', 'completed'): Events.WITHDRAWAL_COMPLETED,
        ('withdrawals.Withdrawal', 'status', 'approved'):  Events.WITHDRAWAL_APPROVED,
        ('withdrawals.Withdrawal', 'status', 'rejected'):  Events.WITHDRAWAL_REJECTED,
        ('withdrawals.Withdrawal', 'status', 'failed'):    Events.WITHDRAWAL_FAILED,

        # Tasks
        ('tasks.TaskSubmission', 'status', 'approved'):    Events.TASK_APPROVED,
        ('tasks.TaskSubmission', 'status', 'rejected'):    Events.TASK_REJECTED,
        ('tasks.TaskSubmission', 'status', 'completed'):   Events.OFFER_COMPLETED,

        # KYC
        ('users.KYCDocument', 'status', 'approved'):       Events.KYC_APPROVED,
        ('users.KYCDocument', 'status', 'rejected'):       Events.KYC_REJECTED,

        # Referrals
        ('referrals.Referral', 'status', 'completed'):     Events.REFERRAL_COMPLETED,
    }

    for (app_model, field, value), event_type in signal_map.items():
        _try_wire_signal(app_model, field, value, event_type)

    logger.info('IntegSignals: Django signals wired to EventBus')


def _try_wire_signal(app_model: str, field: str, value: str, event_type: Events):
    """Attempt to wire a signal for an app model."""
    try:
        from django.apps import apps
        app_label, model_name = app_model.split('.')
        Model = apps.get_model(app_label, model_name)

        @receiver(post_save, sender=Model, weak=False)
        def _handler(sender, instance, created, **kwargs):
            current_val = getattr(instance, field, None)
            if current_val == value:
                update_fields = kwargs.get('update_fields')
                if update_fields and field not in update_fields:
                    return  # Field wasn't updated — skip
                try:
                    event_bus.publish(
                        event_type=event_type,
                        data=_extract_event_data(instance),
                        user_id=getattr(instance, 'user_id', None) or
                                getattr(getattr(instance, 'user', None), 'pk', None),
                        source_module=app_label,
                    )
                except Exception as exc:
                    logger.warning(f'IntegSignals._handler {app_model}: {exc}')

        logger.debug(f'IntegSignals: wired {app_model}.{field}={value} → {event_type}')

    except (LookupError, ValueError):
        logger.debug(f'IntegSignals: model {app_model} not found — skipping')
    except Exception as exc:
        logger.warning(f'IntegSignals._try_wire_signal {app_model}: {exc}')


def _extract_event_data(instance) -> dict:
    """Extract common fields from a model instance for event data."""
    data = {'id': getattr(instance, 'pk', None)}
    for field in ('amount', 'status', 'reward_amount', 'bonus_amount',
                  'reason', 'rejection_reason', 'offer_name', 'task_title',
                  'currency', 'transaction_id', 'new_level', 'level'):
        val = getattr(instance, field, None)
        if val is not None:
            data[field] = str(val) if hasattr(val, '__str__') else val
    return data
