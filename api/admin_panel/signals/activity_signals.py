# api/admin_panel/signals/activity_signals.py
"""
Activity signals: log AdminActivity on every admin model save/delete.
Auto-tracks changes using pre_save / post_save / post_delete.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

# Models to auto-track (app_label.ModelName)
AUTO_TRACK_MODELS = [
    'admin_panel.SystemSettings',
    'admin_panel.SiteNotification',
    'admin_panel.SiteContent',
    'admin_panel.EndpointToggle',
    'admin_panel.FeatureFlag',
    'admin_panel.SystemConfig',
    'admin_panel.MaintenanceWindow',
    'admin_panel.AdminProfile',
    'admin_panel.AdminPermissionGroup',
]

# In-memory store for pre-save snapshots (keyed by instance pk)
_pre_save_snapshots = {}


def _get_snapshot(instance) -> dict:
    """Serialize model instance fields for diff tracking."""
    from ..utils import serialize_model_instance
    return serialize_model_instance(instance)


def _log_activity(action: str, instance, actor=None, changes: dict = None):
    """Create an AdminActivity record."""
    try:
        from ..models.activity import AdminActivity
        model_name = type(instance).__name__
        AdminActivity.log(
            actor=actor,
            action=action,
            model_name=model_name,
            object_id=str(instance.pk) if instance.pk else '',
            object_repr=str(instance)[:200],
            changes=changes or {},
        )
    except Exception as e:
        logger.debug(f"Activity log error for {action}: {e}")


# ==================== Auto-Track via Generic Signal ====================

def connect_auto_track_signals():
    """Connect pre_save + post_save + post_delete for all AUTO_TRACK_MODELS."""
    from django.apps import apps
    for model_str in AUTO_TRACK_MODELS:
        try:
            app_label, model_name = model_str.split('.')
            Model = apps.get_model(app_label, model_name)

            pre_save.connect(_handle_pre_save, sender=Model, weak=False,
                             dispatch_uid=f'admin_activity_pre_save_{model_str}')
            post_save.connect(_handle_post_save, sender=Model, weak=False,
                              dispatch_uid=f'admin_activity_post_save_{model_str}')
            post_delete.connect(_handle_post_delete, sender=Model, weak=False,
                                dispatch_uid=f'admin_activity_post_delete_{model_str}')
        except Exception as e:
            logger.debug(f"Could not connect auto-track signal for {model_str}: {e}")


def _handle_pre_save(sender, instance, **kwargs):
    """Store pre-save snapshot for diff calculation."""
    if instance.pk:
        try:
            existing = sender.objects.get(pk=instance.pk)
            _pre_save_snapshots[f'{sender.__name__}:{instance.pk}'] = _get_snapshot(existing)
        except sender.DoesNotExist:
            pass


def _handle_post_save(sender, instance, created, **kwargs):
    """Log create/update admin activity."""
    action = 'create' if created else 'update'
    snapshot_key = f'{sender.__name__}:{instance.pk}'
    changes = {}

    if not created and snapshot_key in _pre_save_snapshots:
        old_data = _pre_save_snapshots.pop(snapshot_key, {})
        new_data = _get_snapshot(instance)
        from ..utils import compute_model_diff
        changes = compute_model_diff(old_data, new_data)
    elif created:
        _pre_save_snapshots.pop(snapshot_key, None)

    _log_activity(action, instance, changes=changes)


def _handle_post_delete(sender, instance, **kwargs):
    """Log delete admin activity."""
    _log_activity('delete', instance)
    _pre_save_snapshots.pop(f'{sender.__name__}:{instance.pk}', None)


# Connect signals when module is loaded
try:
    connect_auto_track_signals()
except Exception as e:
    logger.debug(f"Auto-track signals deferred: {e}")