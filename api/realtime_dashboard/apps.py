"""
Django app configuration for Real-time Dashboard Backend.

FIX (startup crash): Tags.configuration does not exist on Django's Tags
object in Django 4.x — only Tags.models, Tags.database, Tags.security,
etc. are defined. Using `Tags.configuration` raises AttributeError at
startup, preventing the entire Django process from booting.

Resolution: pass the string `'configuration'` directly to @register(),
which Django accepts as a valid tag identifier.
"""
import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RealtimeDashboardConfig(AppConfig):
    """Configuration for the Real-time Dashboard Backend app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.realtime_dashboard'
    verbose_name = 'Real-time Dashboard Backend'

    def ready(self) -> None:
        """
        Perform initialization when the app is ready.

        1. Configure structured logging (ADDED v1.4.0) — must run before
           anything below logs a line, and before signals/checks run.
        2. Initialize Sentry error tracking (ADDED v1.4.0).
        3. Import signal handlers (must happen here to avoid circular imports).
        4. Register system checks that run on `manage.py check` and at
           startup, catching misconfigurations before they cause runtime errors.

        FIXED: The previous implementation imported
        `api.apirealtime_dashboard.signals` (typo — inconsistent path).
        Combined with the bare `except ImportError: pass`, the signal was
        NEVER registered, silently disabling all WebSocket metric broadcasts.
        """
        self._configure_logging()
        self._init_sentry()
        import api.realtime_dashboard.signals  # noqa: F401
        self._register_checks()

    @staticmethod
    def _configure_logging() -> None:
        """
        Apply JSON/text structured logging (see logging_config.py) as a
        fallback for deployment paths that bypass manage.py.

        WHY HERE: django.setup() calls
        configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
        BEFORE apps.populate() (which triggers this ready() method) — but
        that only fires automatically for manage.py-based entry points.
        Daphne (`daphne config.asgi:application`, per Dockerfile) and bare
        Celery workers (`celery -A config.celery worker`) both call
        django.setup() directly without going through manage.py's
        ManagementUtility, and django.setup() itself IS what calls
        configure_logging — so this is in fact already covered for any
        path that calls django.setup(). This hook exists as the guaranteed
        single place (fires exactly once, after django.setup(), for every
        startup path including pytest) to apply OUR structured-logging
        default specifically — without it, a deployment that never set
        settings.LOGGING at all would fall back to Django's unconfigured
        logging (plain, unstructured stderr output), defeating the point
        of LOG_FORMAT=json in production.

        SAFETY: if the host project (or tests/settings.py, which sets its
        own LOGGING to keep test output quiet) already defines
        settings.LOGGING, that explicit choice is always respected and
        dictConfig() is NOT called again here — this avoids clobbering
        intentional logging configuration, most importantly in tests.
        """
        from django.conf import settings

        if getattr(settings, 'LOGGING', None):
            return

        import logging.config

        from .logging_config import get_logging_config

        logging.config.dictConfig(
            get_logging_config(
                log_format=os.environ.get('LOG_FORMAT'),
                log_level=os.environ.get('LOG_LEVEL'),
            )
        )

    @staticmethod
    def _init_sentry() -> None:
        """
        Initialize Sentry error tracking if SENTRY_DSN is set.

        Gracefully no-ops (with a log line, not an exception) when:
          - SENTRY_DSN is not set (default in .env.example — Sentry is
            opt-in, not required to run this app).
          - sentry-sdk is not installed for some reason (defense in depth;
            it is a normal requirements.txt entry as of v1.4.0).
          - sentry_sdk.init() itself raises for any other reason (a bad
            DSN format, network/proxy issues resolving the ingest host,
            etc.) — error tracking initialization must never be the
            reason the application itself fails to start.
        """
        dsn = os.environ.get('SENTRY_DSN')
        if not dsn:
            logger.info('SENTRY_DSN not set — Sentry error tracking disabled.')
            return

        try:
            import sentry_sdk
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.django import DjangoIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
        except ImportError:
            logger.warning(
                'SENTRY_DSN is set but sentry-sdk is not installed. '
                'Run `pip install sentry-sdk[django]`. Skipping Sentry init.'
            )
            return

        try:
            sentry_sdk.init(
                dsn=dsn,
                environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
                integrations=[
                    DjangoIntegration(),
                    CeleryIntegration(),
                    RedisIntegration(),
                    # LoggingIntegration turns ERROR+ log records (e.g.
                    # logger.error(..., exc_info=True) in exceptions.py)
                    # into Sentry events automatically, in addition to
                    # unhandled exceptions.
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
                traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
                # PII (user emails, IPs, request bodies) must be opted into
                # deliberately, not sent by default — this module handles
                # KYC-adjacent user data (see wallet/KYC apps in the wider
                # platform) so default-off is the safe default here.
                send_default_pii=False,
            )
            logger.info(
                'Sentry error tracking initialized (environment=%s).',
                os.environ.get('SENTRY_ENVIRONMENT', 'production'),
            )
        except Exception:
            logger.warning('sentry_sdk.init() failed — continuing without Sentry.', exc_info=True)

    @staticmethod
    def _register_checks():
        """Register Django system checks for this app."""
        # FIXED: Tags.configuration does not exist on Django 4.x Tags object.
        # Pass the string 'configuration' directly — Django accepts any string
        # as a tag identifier, and the built-in `check --tag configuration`
        # command still works with string tags.
        from django.core.checks import register, Error, Warning as W

        @register('configuration')
        def check_channel_layers(app_configs, **kwargs):
            """
            Verify that CHANNEL_LAYERS['default'] is configured.

            Without a channel layer, WebSocket consumers cannot join groups
            and broadcast_metric_update() silently does nothing — the app
            starts but real-time features are completely broken.
            """
            from django.conf import settings
            errors = []
            layers = getattr(settings, 'CHANNEL_LAYERS', {})
            if not layers.get('default'):
                errors.append(
                    Error(
                        'CHANNEL_LAYERS["default"] is not configured.',
                        hint=(
                            'Add CHANNEL_LAYERS to settings.py. '
                            'For development: use InMemoryChannelLayer. '
                            'For production: use channels_redis.core.RedisChannelLayer.'
                        ),
                        obj=settings,
                        id='realtime_dashboard.E001',
                    )
                )
            return errors

        @register('configuration')
        def check_exception_handler(app_configs, **kwargs):
            """
            Warn if REST_FRAMEWORK['EXCEPTION_HANDLER'] is not set to the
            custom handler, which means API errors won't include 'success: false'.
            """
            from django.conf import settings
            errors = []
            drf_settings = getattr(settings, 'REST_FRAMEWORK', {})
            handler = drf_settings.get('EXCEPTION_HANDLER', '')
            expected = 'api.realtime_dashboard.exceptions.custom_exception_handler'
            if handler != expected:
                errors.append(
                    W(
                        'REST_FRAMEWORK["EXCEPTION_HANDLER"] is not set to the '
                        'realtime_dashboard custom handler.',
                        hint=f'Set EXCEPTION_HANDLER = "{expected}" in REST_FRAMEWORK.',
                        obj=settings,
                        id='realtime_dashboard.W001',
                    )
                )
            return errors

        @register('configuration')
        def check_asgi_application(app_configs, **kwargs):
            """
            Warn if ASGI_APPLICATION is not configured, which means
            WebSocket routing is not wired into the server.
            """
            from django.conf import settings
            errors = []
            if not getattr(settings, 'ASGI_APPLICATION', None):
                errors.append(
                    W(
                        'ASGI_APPLICATION is not set.',
                        hint=(
                            'Set ASGI_APPLICATION = "config.asgi.application" '
                            '(or the path to your project-level asgi.py application). '
                            'Without this, WebSocket connections will not be accepted.'
                        ),
                        obj=settings,
                        id='realtime_dashboard.W002',
                    )
                )
            return errors
