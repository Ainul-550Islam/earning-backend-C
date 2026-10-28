"""
Django signals for Feature Flags & A/B Testing.

NEW: now also writes an AuditLog entry and a FeatureFlagVersion snapshot
on every FeatureFlag create/update/delete (Missing Components #3 Audit
Trail and #7 Versioning/Rollback) — previously there was no record of
who changed a flag or any way to revert one.

DRY FIX: cache invalidation now goes through `FlagEngine.clear_flag_cache`
(which itself delegates to the single `FlagCacheManager` — see
flag_engine.py / utils/cache_manager.py) instead of each signal building
its own cache key string.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.utils import timezone

from .models.feature_flag import FeatureFlag
from .models.experiment import Experiment
from .models.experiment_participant import ExperimentParticipant
from .models.audit import AuditLog
from .models.versioning import FeatureFlagVersion

# Thread-local-ish stash of "current user" for signal handlers. Populated
# by CurrentUserMiddleware (see middleware additions below) when available;
# falls back to None (system-initiated change) otherwise. This avoids
# requiring every signal handler to thread a `request` object through
# Django's signal dispatch, which doesn't carry one natively.
_current_user_holder = {'user': None}


def set_current_user(user):
    """Called by viewsets (perform_create/update/destroy) right before
    save()/delete() so the post_save signal can attribute the change."""
    _current_user_holder['user'] = user


def get_current_user():
    return _current_user_holder.get('user')


def _flag_snapshot(instance: FeatureFlag) -> dict:
    """JSON-safe snapshot of a flag's fields, for audit/version storage."""
    data = model_to_dict(instance, exclude=['id'])
    return data


@receiver(pre_save, sender=FeatureFlag)
def stash_old_flag_values(sender, instance, **kwargs):
    """Stash the pre-save DB state on the instance so post_save can diff it."""
    if instance.pk:
        try:
            instance._old_values = _flag_snapshot(FeatureFlag.objects.get(pk=instance.pk))
        except FeatureFlag.DoesNotExist:
            instance._old_values = None
    else:
        instance._old_values = None


@receiver(post_save, sender=FeatureFlag)
def flag_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle flag creation or update: invalidate cache, write an audit log
    entry, and snapshot a new version row.
    """
    from .flag_engine import FlagEngine
    engine = FlagEngine()
    engine.clear_flag_cache(instance.name, instance.environment)

    new_values = _flag_snapshot(instance)
    old_values = getattr(instance, '_old_values', None)

    AuditLog.objects.create(
        user=get_current_user(),
        flag=instance,
        flag_name_snapshot=instance.name,
        action=AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE,
        old_values=old_values,
        new_values=new_values,
    )

    latest = FeatureFlagVersion.objects.filter(flag=instance).order_by('-version_number').first()
    next_version = 1 if latest is None else latest.version_number + 1
    FeatureFlagVersion.objects.create(
        flag=instance,
        version_number=next_version,
        config=new_values,
        created_by=get_current_user(),
    )


@receiver(post_delete, sender=FeatureFlag)
def flag_deleted(sender, instance, **kwargs):
    """Record deletion in the audit log (version rows cascade-delete with the flag)."""
    from .flag_engine import FlagEngine
    engine = FlagEngine()
    engine.clear_flag_cache(instance.name, instance.environment)

    AuditLog.objects.create(
        user=get_current_user(),
        flag=None,  # flag row is gone; flag_name_snapshot preserves the name
        flag_name_snapshot=instance.name,
        action=AuditLog.Action.DELETE,
        old_values=_flag_snapshot(instance),
        new_values=None,
    )


@receiver(post_save, sender=Experiment)
def experiment_created_or_updated(sender, instance, created, **kwargs):
    """
    Handle experiment creation or update.
    """
    from .experiment_runner import ExperimentRunner
    runner = ExperimentRunner()

    if created:
        runner.initialize_experiment(instance)
    elif instance.status == Experiment.Status.RUNNING:
        runner.start_experiment(instance)


@receiver(post_save, sender=ExperimentParticipant)
def participant_created(sender, instance, created, **kwargs):
    """
    Handle participant creation: update analytics.
    """
    if created:
        from .utils import update_flag_analytics
        update_flag_analytics(instance.experiment.flag, instance.variant, instance.user_id)


@receiver(pre_save, sender=ExperimentParticipant)
def participant_conversion_check(sender, instance, **kwargs):
    """
    Check for participant conversion before save.
    """
    if instance.pk:
        try:
            old_instance = ExperimentParticipant.objects.get(pk=instance.pk)
        except ExperimentParticipant.DoesNotExist:
            return

        if instance.converted and not old_instance.converted:
            instance.converted_at = timezone.now()
