"""
Django app configuration for Feature Flags & A/B Testing.
"""
from django.apps import AppConfig


class FeatureFlagsConfig(AppConfig):
    """
    Configuration for the Feature Flags & A/B Testing app.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    # FIX: was 'api.feature_flags', which doesn't match this package's
    # actual dotted path ('feature_flags'). Combined with the bare
    # `except ImportError: pass` below, this meant `feature_flags.signals`
    # was silently NEVER imported/registered — cache invalidation on flag
    # save, experiment initialization, and analytics tracking on
    # participant creation would not have fired in a real deployment.
    name = 'api.feature_flags'
    verbose_name = 'Feature Flags & A/B Testing'

    def ready(self):
        """
        Perform initialization when the app is ready.
        """
        # Import signals to ensure they are registered.
        import api.feature_flags.signals  # noqa: F401

        # NOTE: default Role/Permission bootstrap (admin/editor/viewer with
        # their default permission grants) is NOT done here. Querying or
        # writing to the database inside AppConfig.ready() is discouraged
        # (Django warns about it, and it can run before migrations exist,
        # before transactions are safe, multiple times under some app
        # servers, etc). Instead it's a proper data migration — see
        # feature_flags/migrations/0002_bootstrap_rbac.py — which is the
        # idiomatic, one-time, migration-state-tracked way to seed this data.
