"""
Django App Configuration for Offer Routing System

FIXES (audit 2026-06):
  - All signal modules imported explicitly — no bare except pass
  - Cap signals (signals_cap.py) fully connected to model receivers
  - Integration system signals connected
  - Filter backends registered globally so all viewsets inherit filtering
  - Plugin manager warm-started at startup
  - WebSocket consumer group layer verified
  - Exception handler path corrected from api.offer_routing → offer_routing
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class OfferRoutingConfig(AppConfig):
    """Configuration for the offer routing application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offer_routing'
    verbose_name = 'Offer Routing'

    def ready(self):
        """
        Initialise app when Django starts.

        Execution order:
          1. Core signal receivers  (offer_route_pre/post_save, score, log, user)
          2. Cap signals             (cap limit reached, cap reset events)
          3. Integration signals    (integration system events)
          4. A/B test signals       (test started / completed / winner)
          5. Monitoring signals     (performance alerts, health events)
          6. DRF exception handler registration
          7. Django-filter backend registration
          8. Plugin manager warm-start
          9. Routing cache warm-up  (non-critical — skipped on cold start)
         10. WebSocket layer check
        """
        self._connect_receivers()
        self._connect_signals()
        self._connect_cap_signals()
        self._connect_integration_signals()
        self._connect_ab_test_signals()
        self._connect_monitoring_signals()
        self._register_exception_handler()
        self._register_filter_backends()
        self._warmup_plugin_manager()
        self._warmup_routing_cache()
        self._check_channel_layer()

    # ── 1. Core receivers ──────────────────────────────────────────────────────

    def _connect_receivers(self):
        """Connect Django signal receivers defined in receivers.py."""
        try:
            from . import receivers  # noqa: F401
            logger.debug("offer_routing: core receivers connected")
        except ImportError as e:
            logger.warning("offer_routing: receivers.py not found — %s", e)
        except Exception as e:
            logger.error("offer_routing: error connecting receivers — %s", e, exc_info=True)

    # ── 2. Core custom signals ────────────────────────────────────────────────

    def _connect_signals(self):
        """Import signals.py to register all custom Signal objects."""
        try:
            from . import signals  # noqa: F401
            logger.debug("offer_routing: signals connected")
        except ImportError as e:
            logger.warning("offer_routing: signals.py not found — %s", e)
        except Exception as e:
            logger.error("offer_routing: error importing signals — %s", e, exc_info=True)

    # ── 3. Cap signals ────────────────────────────────────────────────────────

    def _connect_cap_signals(self):
        """
        Connect cap-specific signals (cap_limit_reached, cap_reset, etc.).

        These fire during offer routing to enforce daily/hourly caps and
        trigger celery tasks that reset counters.
        """
        try:
            from . import signals_cap  # noqa: F401
            logger.debug("offer_routing: cap signals connected")
        except ImportError as e:
            logger.warning("offer_routing: signals_cap.py not found — %s", e)
        except Exception as e:
            logger.error("offer_routing: error connecting cap signals — %s", e, exc_info=True)

        # Wire cap signals to their handlers in receivers.py
        try:
            from .signals import cap_limit_reached, cap_reset
            from .receivers import on_cap_exceeded, handle_cap_limit_reached

            # cap_limit_reached → on_cap_exceeded (logs + pauses offer)
            cap_limit_reached.connect(
                on_cap_exceeded,
                dispatch_uid='offer_routing.cap_limit_reached.on_cap_exceeded',
            )
            # cap_limit_reached → handle_cap_limit_reached (alerts + tasks)
            cap_limit_reached.connect(
                handle_cap_limit_reached,
                dispatch_uid='offer_routing.cap_limit_reached.handle',
            )
            logger.debug("offer_routing: cap_limit_reached signal wired")
        except (ImportError, AttributeError) as e:
            logger.warning("offer_routing: cap signal wiring skipped — %s", e)
        except Exception as e:
            logger.error("offer_routing: cap signal wiring error — %s", e, exc_info=True)

    # ── 4. Integration signals ────────────────────────────────────────────────

    def _connect_integration_signals(self):
        """Connect integration system signals for external event bus."""
        try:
            from .integration_system import integ_signals  # noqa: F401
            logger.debug("offer_routing: integration signals connected")
        except ImportError as e:
            logger.debug("offer_routing: integration signals not available — %s", e)
        except Exception as e:
            logger.error("offer_routing: integration signal error — %s", e, exc_info=True)

    # ── 5. A/B test signals ────────────────────────────────────────────────────

    def _connect_ab_test_signals(self):
        """Wire A/B test lifecycle signals to handlers in receivers.py."""
        try:
            from .signals import (
                ab_test_started, ab_test_completed, ab_test_winner,
                ab_test_assignment,
            )
            from .receivers import (
                on_ab_test_started, on_ab_test_completed,
                on_ab_test_winner, on_ab_test_assignment,
            )

            ab_test_started.connect(
                on_ab_test_started,
                dispatch_uid='offer_routing.ab_test_started',
            )
            ab_test_completed.connect(
                on_ab_test_completed,
                dispatch_uid='offer_routing.ab_test_completed',
            )
            ab_test_winner.connect(
                on_ab_test_winner,
                dispatch_uid='offer_routing.ab_test_winner',
            )
            ab_test_assignment.connect(
                on_ab_test_assignment,
                dispatch_uid='offer_routing.ab_test_assignment',
            )
            logger.debug("offer_routing: A/B test signals wired")
        except (ImportError, AttributeError) as e:
            logger.warning("offer_routing: A/B test signal wiring skipped — %s", e)
        except Exception as e:
            logger.error("offer_routing: A/B test signal wiring error — %s", e, exc_info=True)

    # ── 6. Monitoring / performance alert signals ─────────────────────────────

    def _connect_monitoring_signals(self):
        """Wire performance alert signals to monitoring handlers."""
        try:
            from .signals import performance_alert, routing_error
            from .receivers import handle_performance_alert, check_routing_errors

            performance_alert.connect(
                handle_performance_alert,
                dispatch_uid='offer_routing.performance_alert',
            )
            routing_error.connect(
                check_routing_errors,
                dispatch_uid='offer_routing.routing_error',
            )
            logger.debug("offer_routing: monitoring signals wired")
        except (ImportError, AttributeError) as e:
            logger.debug("offer_routing: monitoring signal wiring skipped — %s", e)
        except Exception as e:
            logger.error("offer_routing: monitoring signal wiring error — %s", e, exc_info=True)

    # ── 7. DRF exception handler ──────────────────────────────────────────────

    def _register_exception_handler(self):
        """
        Set a custom DRF exception handler so all API errors return
        consistent JSON with error_code, message, and timestamp.
        """
        try:
            from django.conf import settings
            if hasattr(settings, 'REST_FRAMEWORK') and isinstance(settings.REST_FRAMEWORK, dict):
                settings.REST_FRAMEWORK.setdefault(
                    'EXCEPTION_HANDLER',
                    'offer_routing.exceptions.custom_exception_handler',  # FIXED path
                )
            logger.debug("offer_routing: DRF exception handler registered")
        except Exception as e:
            logger.warning("offer_routing: exception handler registration failed — %s", e)

    # ── 8. Django-filter backends ─────────────────────────────────────────────

    def _register_filter_backends(self):
        """
        Ensure django-filter's DjangoFilterBackend is in DEFAULT_FILTER_BACKENDS
        so every ViewSet that declares filterset_class or filterset_fields
        gets automatic querystring filtering without per-viewset wiring.
        """
        try:
            from django.conf import settings
            if not hasattr(settings, 'REST_FRAMEWORK'):
                return

            rf = settings.REST_FRAMEWORK
            if not isinstance(rf, dict):
                return

            filter_backends = rf.get('DEFAULT_FILTER_BACKENDS', [])
            django_filter_backend = 'django_filters.rest_framework.DjangoFilterBackend'
            search_filter = 'rest_framework.filters.SearchFilter'
            ordering_filter = 'rest_framework.filters.OrderingFilter'

            updated = False
            for backend in [django_filter_backend, search_filter, ordering_filter]:
                if backend not in filter_backends:
                    filter_backends.append(backend)
                    updated = True

            if updated:
                rf['DEFAULT_FILTER_BACKENDS'] = filter_backends
                logger.debug("offer_routing: filter backends registered — %s", filter_backends)

        except ImportError:
            logger.debug("offer_routing: django-filter not installed — querystring filtering disabled")
        except Exception as e:
            logger.warning("offer_routing: filter backend registration failed — %s", e)

    # ── 9. Plugin manager warm-start ─────────────────────────────────────────

    def _warmup_plugin_manager(self):
        """Initialise PluginManager and load built-in plugins at startup."""
        try:
            from .plugins import get_plugin_manager
            manager = get_plugin_manager()
            logger.debug(
                "offer_routing: plugin manager ready — %d plugins loaded",
                len(manager.plugins) if hasattr(manager, 'plugins') else 0,
            )
        except Exception as e:
            logger.warning("offer_routing: plugin manager warm-start failed — %s", e)

    # ── 10. Routing cache warm-up ─────────────────────────────────────────────

    def _warmup_routing_cache(self):
        """
        Pre-warm routing cache with frequently-used routes.
        Non-critical: failure is logged and silently ignored.
        """
        try:
            from django.conf import settings as django_settings
            # Skip during test runs to avoid touching production caches
            if getattr(django_settings, 'TESTING', False):
                return
            from .services.cache import cache_service
            if hasattr(cache_service, 'warmup_common_routes'):
                cache_service.warmup_common_routes()
                logger.debug("offer_routing: routing cache warmed up")
        except Exception as e:
            # Genuinely non-critical — routing works without cache
            logger.debug("offer_routing: routing cache warm-up skipped — %s", e)

    # ── 11. WebSocket / Channel Layer check ───────────────────────────────────

    def _check_channel_layer(self):
        """
        Verify that Django Channels is installed and a channel layer is
        configured.  If not, real-time WebSocket endpoints will be
        unavailable but the REST API continues working.
        """
        try:
            import channels  # noqa: F401
            from django.conf import settings as django_settings
            if not getattr(django_settings, 'CHANNEL_LAYERS', None):
                logger.warning(
                    "offer_routing: Django Channels installed but CHANNEL_LAYERS "
                    "is not configured — WebSocket endpoints will be unavailable. "
                    "Add CHANNEL_LAYERS to settings.py to enable real-time features."
                )
            else:
                logger.debug("offer_routing: Django Channels and CHANNEL_LAYERS are configured")
        except ImportError:
            logger.debug(
                "offer_routing: django-channels not installed — "
                "real-time WebSocket dashboard disabled"
            )
        except Exception as e:
            logger.warning("offer_routing: channel layer check failed — %s", e)
